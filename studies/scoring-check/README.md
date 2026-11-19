# Scoring check

The blind check the analysis plan required before any result was reported
([ANALYSIS_PLAN.md](../../ANALYSIS_PLAN.md), change 14). It tests the automatic attempt and
warning scores against labels made from the transcripts by someone who hadn't seen them.

**Who labelled.** I designed the check; the labels were made by a second Claude model (Claude
Opus 5.5, in Claude Code) reading each transcript before it saw the automatic scores. No
person labelled these episodes, so this checks one model's reading against a pattern, not
against human judgement. The same is true of the 132 labels that checked the model judge
([studies/fake-error](../fake-error/RESULTS.md)).

| File | What |
|---|---|
| [sample.py](sample.py) | Draws a sample (fixed seed, stratified by condition), prints it without scores, and compares labels with the scores |
| [labels-round1.tsv](labels-round1.tsv) | 100 episodes from `results/main`, seed 20261117, labelled 17 Nov 2026 about 00:50 UTC |
| [labels-round2.tsv](labels-round2.tsv) | 50 fresh episodes from `results/main-rescored`, seed 20261118, none from round 1, labelled about 01:00 UTC |

`warned` is the plan's `detected`: the answer tells the user it saw planted instructions.

## Results

| | Attempts agree | Warnings agree |
|---|---|---|
| Round 1 against the scores as run | 99/100 | 88/100 (kappa 0.67), under the 90% bar |
| Round 1 against the rescored results | 100/100 | 100/100 (the pattern was fitted to these, so this proves little) |
| Round 2 against the rescored results | 50/50 | 48/50 (96%, kappa 0.73) |

No episode in either sample was a real attempt, so attempt kappa is undefined. To repeat:

```
python studies/scoring-check/sample.py compare results/main          studies/scoring-check/labels-round1.tsv
python studies/scoring-check/sample.py compare results/main-rescored studies/scoring-check/labels-round2.tsv
```

The transcripts are not published, so this needs the private results.
