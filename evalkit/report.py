"""Turns results/<run>/episodes.jsonl into rate tables with 95% Wilson intervals.

    python -m evalkit.report --run main            # markdown tables on stdout
    python -m evalkit.report --run main --csv out.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def table(data: list[dict], by: tuple[str, ...]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in data:
        if "score" not in r or r["injection"] is None:
            continue
        groups[tuple(r[k] for k in by)].append(r)
    out = []
    for key, rs in sorted(groups.items()):
        n = len(rs)
        entry = dict(zip(by, key))
        entry["n"] = n
        for metric in ("exposed", "attempted", "harmed", "detected", "refused"):
            k = sum(1 for r in rs if r["score"].get(metric))
            p, lo, hi = wilson(k, n)
            entry[metric] = f"{p:.0%} [{lo:.0%}, {hi:.0%}]"
        # Attempts among the episodes where the injection reached the model at all.
        seen = [r for r in rs if r["score"].get("exposed")]
        p, lo, hi = wilson(sum(1 for r in seen if r["score"]["attempted"]), len(seen))
        entry["attempted if exposed"] = f"{p:.0%} [{lo:.0%}, {hi:.0%}] (n={len(seen)})" if seen else "-"
        out.append(entry)
    return out


def markdown(entries: list[dict]) -> str:
    if not entries:
        return "_no injected episodes_\n"
    cols = list(entries[0])
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(e[c]) for c in cols) + " |" for e in entries]
    return "\n".join(lines) + "\n"


def cost_summary(data: list[dict]) -> str:
    """Spend so far and the measured shape of an episode, per model: what the forecast in
    `evalkit.costs` should be corrected with after the pilot."""
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in data:
        if "transcript" in r:
            by_model[r["model"]].append(r)
    if not by_model:
        return ""
    lines = ["### Cost and episode shape\n",
             "| model | episodes | total $ | mean $ | mean steps | mean output tokens | mean cached input | mean seconds |",
             "|---|---|---|---|---|---|---|---|"]
    for model, rs in sorted(by_model.items()):
        n = len(rs)
        total = sum(r.get("cost_usd") or 0.0 for r in rs)
        t = [r["transcript"] for r in rs]
        mean = lambda key: sum(x.get(key, 0) for x in t) / n  # noqa: E731
        lines.append(f"| {model} | {n} | {total:.2f} | {total / n:.4f} | {mean('steps'):.1f} | "
                     f"{mean('output_tokens'):.0f} | {mean('cache_read_tokens') + mean('cache_write_tokens'):.0f} | {mean('seconds'):.0f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="main", help="results/<run>/ folder name (a dry run writes <run>-dryrun)")
    ap.add_argument("--csv")
    args = ap.parse_args(argv)
    data = rows(HERE / "results" / args.run / "episodes.jsonl")
    errors = sum(1 for r in data if "harness_error" in r)
    clean = [r for r in data if r.get("injection") is None and "score" in r]
    print(f"{len(data)} episodes, {errors} harness errors, {len(clean)} clean baselines\n")
    print(cost_summary(data))
    for by in (("condition",), ("model", "condition"), ("placement", "condition"), ("goal", "condition")):
        print(f"### By {', '.join(by)}\n")
        print(markdown(table(data, by)))
    if args.csv:
        entries = table(data, ("model", "condition", "placement", "goal"))
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(entries[0]) if entries else ["n"])
            w.writeheader()
            w.writerows(entries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
