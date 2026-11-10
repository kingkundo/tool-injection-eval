"""What episodes cost: list prices, the cost of a finished episode, and a forecast before a run.

Prices are US dollars per million tokens, first-party Claude API list prices as of November
2026. Cache writes use the 5-minute TTL (1.25x input). Haiku 5.5's cache prices are assumed
from the usual ratios (0.1x and 1.25x input); its input price also rises past 100K tokens,
which an episode never reaches. Check them against the pricing page
before quoting a number, and update them here when they change.

The forecast is only as good as its per-episode assumptions (`PROFILES`). They come from the
size of the real tool list and a guess at how many steps a diagnosis takes; the pilot replaces
the guess with measured numbers (`python -m evalkit.report` prints them).
"""

from __future__ import annotations

from dataclasses import dataclass

PRICES = {
    #                   input  output  cache read  cache write (5 min)
    "claude-opus-5-5":   (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-haiku-5-5":  (0.10, 0.50, 0.01, 0.125),
}


def episode_cost(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float | None:
    p = PRICES.get(model)
    if p is None:
        return None
    return (input_tokens * p[0] + output_tokens * p[1] + cache_read * p[2] + cache_write * p[3]) / 1_000_000


@dataclass(frozen=True)
class Profile:
    """A guess at one episode's shape, before the pilot measures it."""

    steps: float               # model calls per episode
    prefix_tokens: int         # tool definitions + system prompt + task, sent every step
    growth_per_step: int       # tool output + the model's own turn added each step
    output_per_step: int       # thinking + text + tool call per step

    def tokens(self) -> dict:
        """Input split into cache reads and writes, assuming every step hits the cache for
        everything before its own new turn (top-level automatic caching)."""
        n = round(self.steps)
        reads = writes = 0
        for k in range(n):
            if k == 0:
                writes += self.prefix_tokens
            else:
                reads += self.prefix_tokens + (k - 1) * self.growth_per_step
                writes += self.growth_per_step
        return {"cache_read": reads, "cache_write": writes, "input": 50 * n, "output": n * self.output_per_step}


# The bridge's 27 tools serialise to about 29.6 KB of JSON (about 8,000 tokens), plus
# run_on_group, the system prompt and the task.
PREFIX = 9_000
PROFILES = {
    "low": Profile(steps=4, prefix_tokens=PREFIX, growth_per_step=1_200, output_per_step=600),
    "mid": Profile(steps=7, prefix_tokens=PREFIX, growth_per_step=2_000, output_per_step=1_200),
    "high": Profile(steps=12, prefix_tokens=PREFIX, growth_per_step=3_000, output_per_step=2_500),
}


def forecast(episodes_per_model: dict[str, int]) -> list[dict]:
    rows = []
    for name, profile in PROFILES.items():
        t = profile.tokens()
        total = 0.0
        per_model = {}
        for model, n in episodes_per_model.items():
            c = episode_cost(model, t["input"], t["output"], t["cache_read"], t["cache_write"])
            per_model[model] = c
            total += (c or 0.0) * n
        rows.append({"profile": name, "per_episode": per_model, "total": total})
    return rows
