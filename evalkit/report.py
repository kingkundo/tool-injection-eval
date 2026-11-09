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
        for metric in ("attempted", "harmed", "detected", "refused"):
            k = sum(1 for r in rs if r["score"][metric])
            p, lo, hi = wilson(k, n)
            entry[metric] = f"{p:.0%} [{lo:.0%}, {hi:.0%}]"
        out.append(entry)
    return out


def markdown(entries: list[dict]) -> str:
    if not entries:
        return "_no injected episodes_\n"
    cols = list(entries[0])
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(e[c]) for c in cols) + " |" for e in entries]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="main")
    ap.add_argument("--csv")
    args = ap.parse_args(argv)
    data = rows(HERE / "results" / args.run / "episodes.jsonl")
    errors = sum(1 for r in data if "harness_error" in r)
    clean = [r for r in data if r.get("injection") is None and "score" in r]
    print(f"{len(data)} episodes, {errors} harness errors, {len(clean)} clean baselines\n")
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
