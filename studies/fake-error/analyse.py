"""Tables for the fake-error study (PLAN.md). Reads results and judge labels; prints Markdown.

    python studies/fake-error/analyse.py main  <results/main-rescored> <judged-main.jsonl> [labels dir]
    python studies/fake-error/analyse.py study <results/fe-study>      <judged-fe.jsonl>
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evalkit.report import valid  # noqa: E402


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pct(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100*k/n:.0f}% [{100*lo:.0f}–{100*hi:.0f}]" if n else "–"


def load(run_dir: Path, labels: Path) -> list[dict]:
    rows = []
    for p in sorted(run_dir.glob("episodes*.jsonl")):
        rows += valid([json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()])
    lab = {}
    for l in labels.read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            if "label" in d:
                lab[d["id"]] = d
    for r in rows:
        r["judge"] = lab.get(r["id"])
    return rows


def table(rows: list[dict], key, title: str) -> None:
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    print(f"\n#### {title}\n")
    print("| group | flagged (judge) | face value | not mentioned | offers the action | warned (pattern) | attempted |")
    print("|---|---|---|---|---|---|---|")
    for k in sorted(g, key=str):
        xs = g[k]
        n = len(xs)
        c = lambda f: sum(1 for x in xs if f(x))  # noqa: E731
        print(f"| {k} | {pct(c(lambda x: x['judge']['label']=='flagged'), n)} | "
              f"{pct(c(lambda x: x['judge']['label']=='face_value'), n)} | "
              f"{pct(c(lambda x: x['judge']['label']=='not_mentioned'), n)} | "
              f"{pct(c(lambda x: x['judge']['offers_action']), n)} | "
              f"{pct(c(lambda x: x['score']['detected']), n)} | {c(lambda x: x['score']['attempted'])} |")


def main() -> None:
    mode, run_dir, labels = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    rows = load(run_dir, labels)
    inj = [r for r in rows if r.get("injection") and r["score"]["exposed"]]
    missing = [r for r in inj if not r["judge"]]
    print(f"exposed injected episodes: {len(inj)}, without a judge label: {len(missing)}")
    inj = [r for r in inj if r["judge"]]
    clean = [r for r in rows if not r.get("injection") and r.get("judge")]
    if clean:
        fa = sum(r["judge"]["label"] == "flagged" for r in clean)
        print(f"clean episodes judged: {len(clean)}, judged as flagging planted text: {fa}")
        print(f"clean episodes the pattern scores as warned: {sum(bool(r['score'].get('detected')) for r in clean)}")
    table(inj, lambda r: r["style"], "By style")
    table([r for r in inj if not r.get("contaminated")], lambda r: r["style"], "By style, uncontaminated only")
    table(inj, lambda r: (r["style"], r["placement"]), "Style x placement")
    table(inj, lambda r: (r["style"], r["model"]), "Style x model")
    table(inj, lambda r: (r["style"], r["goal"]), "Style x goal")
    table(inj, lambda r: (r["style"], r["condition"]), "Style x condition")
    if mode == "study":
        table(inj, lambda r: ("assistant" if "assistant" in r["style"] else "reader"), "Addressee (pooled)")
        table(inj, lambda r: ("native" if r["style"].endswith("native") else "foreign"), "Fit (pooled)")
        table(inj, lambda r: (r["style"], "screen" if r["task"] == "screen-dialog" else "log"), "Style x screen/log")
    # Pattern against judge.
    print("\n#### Pattern against judge (exposed injected)\n")
    m = defaultdict(int)
    for r in inj:
        m[(r["style"], bool(r["score"]["detected"]), r["judge"]["label"])] += 1
    print("| style | pattern warned | judge label | n |\n|---|---|---|---|")
    for k in sorted(m):
        print(f"| {k[0]} | {k[1]} | {k[2]} | {m[k]} |")
    if len(sys.argv) > 4:
        agreement(rows, Path(sys.argv[4]))


def agreement(rows: list[dict], labels_dir: Path) -> None:
    by_id = {r["id"]: r for r in rows}
    for name in ("random60", "fake-error-pattern-misses"):
        tsv = labels_dir / f"{name}.tsv"
        ids = labels_dir / f"{name}.ids.tsv"
        if not (tsv.exists() and ids.exists()):
            continue
        idmap = dict(l.split("\t") for l in ids.read_text().split("\n") if l.strip())
        rows_ = [l.split("\t") for l in tsv.read_text().split("\n")[1:] if l.strip()]
        agree = agree_o = n = 0
        confusion = defaultdict(int)
        for key, label, offers in rows_:
            r = by_id.get(idmap[key].strip())
            if not r or not r.get("judge"):
                continue
            n += 1
            j = r["judge"]
            agree += j["label"] == label
            agree_o += j["offers_action"] == (offers == "true")
            confusion[(label, j["label"])] += 1
        print(f"\n#### Hand labels against judge: {name}\n")
        print(f"label agreement {agree}/{n}, offers_action agreement {agree_o}/{n}")
        for (h, j), c in sorted(confusion.items()):
            print(f"- hand {h}, judge {j}: {c}")


if __name__ == "__main__":
    main()
