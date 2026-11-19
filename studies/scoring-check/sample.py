"""Draws the plan's blind scoring-check samples and compares labels with the automatic scores.

    python studies/scoring-check/sample.py draw    <results dir> <out dir> [--round 2]
    python studies/scoring-check/sample.py show    <results dir> <out dir> <from> <to> [--round 2]
    python studies/scoring-check/sample.py compare <results dir> <labels .tsv>

Round 1 (ANALYSIS_PLAN.md, change 14): 100 injected episodes from results/main, 20 per
condition, seed 20261117. Round 2: 50 from results/main-rescored, 10 per condition, seed
20261118, none from round 1. `draw` writes the ids and, separately, the automatic scores (the
key, read only after labelling); `show` prints episodes without their scores, for labelling.
The labels used are in labels-round1.tsv and labels-round2.tsv.
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

SEEDS = {1: 20261117, 2: 20261118}
PER_CONDITION = {1: 20, 2: 10}
HERE = Path(__file__).resolve().parent


def valid_injected(results: Path) -> dict:
    """The last attempt of each episode that didn't fail, as evalkit.report counts them."""
    last = {}
    for p in sorted(results.glob("episodes*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("harness_error") or (r.get("transcript") or {}).get("error"):
                continue
            last[r["id"]] = r
    return {k: r for k, r in last.items() if r.get("injection")}


def draw(results: Path, out: Path, rnd: int) -> None:
    rows = sorted(valid_injected(results).values(), key=lambda r: r["id"])
    skip = set()
    if rnd == 2:
        skip = {l.split("\t")[0] for l in (HERE / "labels-round1.tsv").read_text().splitlines()[1:]}
    by = defaultdict(list)
    for r in rows:
        if r["id"] not in skip:
            by[r["condition"]].append(r)
    rng = random.Random(SEEDS[rnd])
    pick = []
    for cond in sorted(by):
        pick += rng.sample(by[cond], PER_CONDITION[rnd])
    rng.shuffle(pick)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"sample{rnd}.json").write_text(json.dumps([r["id"] for r in pick], indent=1))
    (out / f"key{rnd}.json").write_text(json.dumps({r["id"]: r["score"] for r in pick}, indent=1))
    print(f"drew {len(pick)} of {len(rows)} valid injected episodes; seed {SEEDS[rnd]}")


def show(results: Path, out: Path, rnd: int, a: int, b: int) -> None:
    ids = json.loads((out / f"sample{rnd}.json").read_text())
    rows = valid_injected(results)
    for i in range(a, min(b, len(ids))):
        r = rows[ids[i]]
        tr = r["transcript"]
        print(f"##### #{i} goal={r['goal']} placement={r['placement']} task={r['task']} node={r['node']}")
        for c in tr.get("calls", []):
            args = json.dumps(c.get("input"), ensure_ascii=False)
            print(f"  > {c.get('name')} {args[:160]}" + (" [DENIED]" if c.get("approved") is False else ""))
        ans = (tr.get("final_text") or "").replace("\n", " ")
        print(f"  ANSWER: {ans[:1600]}" + (f" [...] {ans[-1400:]}" if len(ans) > 3000 else ans[1600:3000]))


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n
    pb = sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan")


def compare(results: Path, labels: Path) -> None:
    rows = valid_injected(results)
    lines = [l.split("\t") for l in labels.read_text(encoding="utf-8").splitlines()[1:] if l.strip()]
    for field, col in (("attempted", 1), ("detected", 2)):
        pairs = [(int(l[col]), int(bool(rows[l[0]]["score"][field]))) for l in lines]
        po, k = kappa(pairs)
        print(f"{field}: agreement {po:.0%} ({sum(a == b for a, b in pairs)}/{len(pairs)}), kappa {k:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["draw", "show", "compare"])
    ap.add_argument("results", type=Path)
    ap.add_argument("path", type=Path, help="output dir (draw, show) or labels .tsv (compare)")
    ap.add_argument("range", nargs="*", type=int)
    ap.add_argument("--round", type=int, default=1, choices=[1, 2])
    a = ap.parse_args()
    if a.action == "draw":
        draw(a.results, a.path, a.round)
    elif a.action == "show":
        show(a.results, a.path, a.round, *a.range)
    else:
        compare(a.results, a.path)
