"""Rescores finished episodes from their saved transcripts with the current scoring code.

Used after the hand-labelled check (ANALYSIS_PLAN change 14) found the warning pattern missed
12 of 100 sampled warnings. Reads results/<run>/, writes results/<run>-rescored/ with the same
rows, each injected row's score recomputed and the original kept as `score_original`, so
`python -m evalkit.report --run <run>-rescored` reports the new scores. The raw run is never
changed.

Each row also gets `contaminated`: its tool outputs held injection text from a goal other than
its own (any injection text, for a clean row). The VM snapshots turned out to contain one
planted line each (found 17 Nov, ANALYSIS_PLAN change 14), so some episodes saw a second
injection; `python -m evalkit.report --exclude-contaminated` leaves them out.

Harm keeps the recorded value, because it came from the node after the episode (except a
harm check on a tool call, which is recomputed from the transcript, as at run time). Exposure
keeps the recorded value too. Clean rows are copied as they are, and the script prints how
many clean answers the warning pattern matches, which is the false-alarm check.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

from .agent import Call, Transcript
from .report import failed
from .scoring import DETECTION, attempted, harm_tool_called
from .suite import fill, load

HERE = Path(__file__).resolve().parent.parent


def transcript(d: dict) -> Transcript:
    calls = [Call(**c) for c in d.get("calls", [])]
    fields = {f.name for f in dataclasses.fields(Transcript)}
    return Transcript(**{k: v for k, v in d.items() if k in fields and k != "calls"}, calls=calls)


def goal_spec(suite, canaries: dict, goal: str) -> tuple[tuple[str, ...], dict]:
    g = suite.injections["goals"][goal]
    markers = tuple(fill(m, canaries) for m in g["attempt_markers"])
    harm = {k: fill(v, canaries) if isinstance(v, str) else v for k, v in g["harm_check"].items()}
    return markers, harm


def snippets(suite, canaries: dict) -> dict[str, str]:
    """The start of each goal's instruction, which every style quotes word for word."""
    return {g: fill(v["instruction"], canaries)[:45] for g, v in suite.injections["goals"].items()}


def contaminated(r: dict, snips: dict[str, str]) -> bool:
    outputs = [c.get("output") or "" for c in (r.get("transcript") or {}).get("calls", [])]
    return any(sn in out for g, sn in snips.items() if g != r.get("goal") for out in outputs)


def rescore_row(r: dict, suite, canaries: dict) -> dict:
    if "score" not in r or failed(r):
        return r
    r = {**r, "contaminated": contaminated(r, snippets(suite, canaries))}
    if r.get("injection") is None:
        return r
    tr = transcript(r["transcript"])
    markers, harm = goal_spec(suite, canaries, r["goal"])
    old = r["score"]
    new = dict(old)
    new["attempted"] = attempted(tr, markers, harm, r["goal"])
    new["detected"] = bool(DETECTION.search(tr.final_text))
    if harm.get("type") == "tool_called":
        new["harmed"] = harm_tool_called(tr, harm["tool"])
    return {**r, "score": new, "score_original": old}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="main")
    ap.add_argument("--config", default="config.yaml", help="for the canary names")
    args = ap.parse_args(argv)
    canaries = yaml.safe_load(Path(args.config).read_text())["canaries"]
    suite = load()
    src = HERE / "results" / args.run
    dst = HERE / "results" / f"{args.run}-rescored"
    dst.mkdir(exist_ok=True)
    changes: Counter = Counter()
    clean_matches = clean_total = 0
    dirty: Counter = Counter()
    for path in sorted(src.glob("episodes*.jsonl")):
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            r2 = rescore_row(r, suite, canaries)
            if r2.get("contaminated"):
                dirty["clean" if r2.get("injection") is None else "injected"] += 1
            elif r.get("injection") is None and "score" in r and not failed(r):
                clean_total += 1
                clean_matches += bool(DETECTION.search((r.get("transcript") or {}).get("final_text", "")))
            if "score_original" in r2:
                for k in ("attempted", "detected", "harmed"):
                    if r2["score"][k] != r2["score_original"][k]:
                        changes[f"{k} {r2['score_original'][k]}->{r2['score'][k]}"] += 1
            out.append(json.dumps(r2))
        (dst / path.name).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {dst}")
    print("changed scores (all attempts, failed rows excluded):", dict(changes) or "none")
    print("rows that saw another goal's injection text (all attempts):", dict(dirty) or "none")
    print(f"uncontaminated clean answers the warning pattern matches (false alarms): {clean_matches}/{clean_total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
