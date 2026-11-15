"""Builds the list of episodes from the suite files.

An episode is one model running one benign task on one node, under one condition, with at
most one injection planted (none for the clean baseline). Sampling is seeded, so the same
suite and config always give the same episodes.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SUITE = Path(__file__).resolve().parent.parent / "suite"


@dataclass(frozen=True)
class Injection:
    goal: str
    placement: str
    style: str
    text: str
    harm_check: dict
    attempt_markers: tuple[str, ...]

    @property
    def id(self) -> str:
        return f"{self.goal}.{self.placement}.{self.style}"


@dataclass(frozen=True)
class Episode:
    model: str
    node: str
    task_id: str
    condition: str
    injection: Injection | None
    repeat: int = 0

    @property
    def id(self) -> str:
        inj = self.injection.id if self.injection else "clean"
        return f"{self.model}|{self.node}|{self.task_id}|{self.condition}|{inj}|r{self.repeat}"


@dataclass
class Suite:
    tasks: list[dict]
    injections: dict
    conditions: dict
    base_system: str
    extra: dict = field(default_factory=dict)


def load(suite_dir: Path = SUITE) -> Suite:
    tasks = yaml.safe_load((suite_dir / "tasks.yaml").read_text())["tasks"]
    injections = yaml.safe_load((suite_dir / "injections.yaml").read_text())
    conditions_file = yaml.safe_load((suite_dir / "conditions.yaml").read_text())
    private = suite_dir / "private" / "styles.yaml"
    if private.exists():
        injections["styles"].update(yaml.safe_load(private.read_text()) or {})
    return Suite(
        tasks=tasks,
        injections=injections,
        conditions=conditions_file["conditions"],
        base_system=conditions_file["base_system"],
    )


def fill(template: str, values: dict) -> str:
    """Fill {name} placeholders, leaving unknown ones as they are."""
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def injections_for(
    suite: Suite, canaries: dict, task: dict, rng: random.Random,
    per_task: int | None = None, screen_only_on_screen_task: bool = False,
) -> list[Injection]:
    spec = suite.injections
    combos = list(itertools.product(spec["goals"], spec["placements"], spec["styles"]))
    if task["carrier"] == "screen":
        # A task about the screen can only carry text on the screen.
        combos = [c for c in combos if c[1] == "screen"]
    elif screen_only_on_screen_task:
        # An agent reading a log rarely looks at the screen, so a dialog there is seldom seen.
        combos = [c for c in combos if c[1] != "screen"]
    rng.shuffle(combos)
    chosen = sorted(combos[: per_task or spec["per_task"]])
    out = []
    for goal, placement, style in chosen:
        g = spec["goals"][goal]
        instruction = fill(g["instruction"], canaries)
        out.append(
            Injection(
                goal=goal,
                placement=placement,
                style=style,
                text=fill(spec["styles"][style], {"instruction": instruction}).strip(),
                harm_check={k: fill(v, canaries) if isinstance(v, str) else v for k, v in g["harm_check"].items()},
                attempt_markers=tuple(fill(m, canaries) for m in g["attempt_markers"]),
            )
        )
    return out


def episodes(suite: Suite, config: dict) -> list[Episode]:
    rng = random.Random(suite.injections.get("seed", 0))
    out: list[Episode] = []
    per_task = {
        t["id"]: injections_for(
            suite, config["canaries"], t, rng,
            per_task=config.get("injections_per_task"),
            screen_only_on_screen_task=config.get("screen_only_on_screen_task", False),
        )
        for t in suite.tasks
    }
    for model, node, task, condition, repeat in itertools.product(
        config["models"],
        [n["name"] for n in config["nodes"]],
        suite.tasks,
        suite.conditions,
        range(config.get("repeats", 1)),
    ):
        out.append(Episode(model, node, task["id"], condition, None, repeat))
        for inj in per_task[task["id"]]:
            out.append(Episode(model, node, task["id"], condition, inj, repeat))
    return out
