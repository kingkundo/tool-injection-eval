# Approval rules study

A small AI Control study on the main run's data: can a rule that approves or refuses an AI's
tool calls refuse fewer harmless calls without letting more harmful ones through? It replays
ten rules offline over the 19,736 tool calls recorded in the main run, plus hand-written attack
sets. No new agent runs.

| File | What |
|---|---|
| [PLAN.md](PLAN.md) | Pre-registered plan and hypotheses, with every later change logged |
| [RESULTS.md](RESULTS.md) | Results, what they show, limits |
| [rules.py](rules.py) | The rules (R0 is the main run's approver) |
| [replay.py](replay.py) | Runs every rule over the transcripts and attack sets |
| [attacks.yaml](attacks.yaml), [attacks-holdout.yaml](attacks-holdout.yaml) | Synthetic attacks; the held-out set was written before any rule saw it |
| `output/` | Summary numbers and per-attack decisions (no transcript text) |

The study was committed in five commits, in the order the work was done: plan, then attacks,
then frozen rules, then fixes and the held-out set, then results. All five were made within ten
minutes at the end of the session (18 Nov, 20:57 to 21:06 UTC), so they record the order but
don't on their own prove the plan came before the replay. The clock times written in PLAN.md
were noted while working and run up to about 25 minutes later than those commits; treat them
as approximate.
