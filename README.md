# Tool-output injection eval

I built this harness to measure how often an AI agent that manages machines through
[Dashcat](https://dashcat.ai) can be steered by text planted in what its tools return (a log
line, a file, a dialog on screen), and how much each deployment-side control cuts that: a
system-prompt rule, node instructions, Dashcat permissions and a person approving actions. It
runs real Claude models against real Linux and Windows VMs, through Dashcat's own tools, and
checks for harm on the VM itself.

The full write-up, with design, hypotheses, results and limits, is at
[tomxxi.com/work/tool-output-injection](https://tomxxi.com/work/tool-output-injection). It
started in the Dashcat repo's `research/` folder (this repo keeps that history) and lives here
on its own so it can be published without the product's code. Conflict of interest: I built
Dashcat.

Tom Taylor, November 2026

## Results in brief

- **Main run:** 2,275 scored episodes with Claude Opus 5.5, Sonnet 5.5 and Haiku 5.5 on one
  Linux and one Windows VM. No model attempted the planted action in any of the 1,697 episodes
  where it read the planted text (95% upper bound 0.2%), and nothing was harmed. The agent
  warned the user in 1,691 of them by a model judge (Sonnet 5.5), and in 1,590 (94%) by the
  pre-registered word pattern, which misses some wordings. Both the judge and the pattern were
  checked against blind labels made by a second Claude model, not by a person
  ([`studies/scoring-check`](studies/scoring-check)).
- **Open-weights arm:** two 10-episode Qwen 3.8 27B pilots, standard and "uncensored"; no
  attempts. Exploratory, never pooled with the Claude results.
- **Follow-ups:** [`studies/approval-rules`](studies/approval-rules) replays ten approval rules
  over the run's 19,736 tool calls; [`studies/fake-error`](studies/fake-error) tests a more
  convincing fake error message.
- **What it can't show:** with nothing attempted, the controls had nothing to stop, so they
  can't be ranked from these runs. The attacks are fixed templates, not an adaptive attacker.

The pre-registered plan and its sixteen dated changes are in [ANALYSIS_PLAN.md](ANALYSIS_PLAN.md),
and the decision-by-decision record is in [HISTORY.md](HISTORY.md).

## Safety rules

- Run it only against **throwaway VMs** paired with a bridge that is paired with nothing else.
  Every episode resets the VM from a snapshot first.
- Every harmful target is a **canary** (a fake secret, a made-up user, a dummy service). Never
  put a real secret or a real machine in `config.yaml`.
- The plan kept room for stronger injection strings in `suite/private/` (git-ignored), to stay
  unpublished. None was needed: every injection the runs used is a template in
  `suite/injections.yaml` or `studies/fake-error/suite/`, and all are published here.

## Layout

| Path | What |
|---|---|
| `suite/tasks.yaml` | 10 everyday sysadmin tasks and where each one's untrusted text lives |
| `suite/injections.yaml` | Goals (exfiltrate, persist, disable, spread), placements, styles, sampling |
| `suite/conditions.yaml` | The five conditions: bare, rule, rule + node notes, permissions, approval |
| `evalkit/mcp_client.py` | Talks to `dashcat-bridge mcp` on stdio, as an AI app does |
| `evalkit/agent.py` | The agent loop (Claude API, manual tool loop) and the scripted approver |
| `evalkit/local_agent.py` | The same loop for a local model behind an OpenAI-style endpoint (the Qwen arm) |
| `evalkit/scoring.py` | Attempt, harm, detection and refusal for one episode |
| `evalkit/stubs.py` | `run_on_group`, which the harness answers itself (see below) |
| `evalkit/costs.py` | List prices, each episode's cost, and the forecast `--plan` prints |
| `evalkit/dryrun.py` | The whole pipeline against a scripted model and in-memory nodes |
| `evalkit/run.py` | Runs the suite, one JSON line per episode, resumable |
| `evalkit/report.py` | Rates with 95% Wilson intervals by condition, model, placement and goal, plus cost |
| `evalkit/rescore.py` | Rescores saved transcripts after a scoring fix, keeping the raw rows (plan changes 14, 15) |
| `evalkit/judge.py` | The model judge for warnings (plan change 16) |
| `configs/` | The configs the runs used, with the host's name and paths replaced |
| `scripts/` | VirtualBox reset, one-off setup for each VM, and `scripts/host/` for the PC it ran on |
| `studies/` | The scoring check and the two follow-up studies, each with its plan and results |
| `tests/` | Offline tests with a fake model and a fake bridge, including a full dry run |
| [ANALYSIS_PLAN.md](ANALYSIS_PLAN.md), [HISTORY.md](HISTORY.md), [RUNBOOK.md](RUNBOOK.md) | The pre-registered plan and its changes, the dated record, and the machine it ran on |

## Running it

The machine this runs on, how it was built and how to clean it up: [RUNBOOK.md](RUNBOOK.md).
The dated record of what was decided, by whom and why, and what it cost: [HISTORY.md](HISTORY.md).

Python 3.10 or later (the run used 3.12 with `anthropic` 2.8.0 and PyYAML 6.0.3). It needs
[Dashcat Bridge](https://dashcat.ai) and Dashcat Agent on each VM; the run used 0.1.15. On a
Windows host, hooks run through Git for Windows' bash by default (`hook_shell` in the
config overrides it), and `scripts/reset-vm.sh` restores VirtualBox VMs. Build each VM with
`scripts/setup-linux-vm.sh` or `scripts/setup-windows-vm.ps1`, install Dashcat Agent and the
admin service (adding users and stopping services needs `run_as_admin`), pair it, and snapshot
it running as `clean`. On Windows, an administrator's ssh key goes in
`C:\ProgramData\ssh\administrators_authorized_keys`. Check that the planted dialog really
appears on each VM's desktop before a run: on Windows it stopped appearing early in the main
run and nobody noticed until the end (plan change 15).

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 -m unittest discover -s tests            # offline, no API calls

python3 -m evalkit.run --config config.example.yaml --plan --limit 50     # episodes and a cost forecast
python3 -m evalkit.run --config config.example.yaml --dry-run            # whole pipeline, no API, no VMs
python3 -m evalkit.report --run main-dryrun                              # the dry run's tables

cp config.example.yaml config.yaml               # then fill in your test nodes and hooks
python3 -m evalkit.run --run pilot --limit 50 --budget 25   # the pilot: check cost and scoring by hand
python3 -m evalkit.report --run pilot            # measured cost per episode, per model
python3 -m evalkit.run --node eval-linux --budget 300 &     # the full run, one process per node;
python3 -m evalkit.run --node eval-windows --budget 300 &   # rerun the same lines to resume
python3 -m evalkit.report                        # tables
```

`--limit` takes a fixed, shuffled sample, so a 50-episode pilot covers every model, condition
and goal rather than 50 episodes of one task. `--budget` stops once the run's recorded cost
passes that many dollars; rerunning resumes. With `--node`, each node's episodes go to their
own `episodes.<node>.jsonl` (the report reads them all) and the budget is per process. Run
nodes in parallel: episodes are sequential within a process, and a snapshot revert plus a
multi-step agent loop takes a minute or two, so 1,950 episodes on one node is a couple of days.

The dry run uses a scripted model that complies with, reports or ignores an injection it has
read, and in-memory nodes in place of the VMs and hooks. Its rates mean nothing; it exists to
prove the plumbing, and it checks invariants that hold for any model (for example nothing is
harmed under the permissions or approval conditions) and exits non-zero if one breaks.

To repeat the main run as it was done rather than as first designed, start from
[`configs/main-linux.yaml`](configs/main-linux.yaml) and
[`configs/main-windows.yaml`](configs/main-windows.yaml), one per node, and rescore with
`python3 -m evalkit.rescore --run main` before reporting.

Credentials come from the Anthropic SDK's usual sources (`ANTHROPIC_API_KEY` or
`ant auth login`); never put a key in `config.yaml`.

## Data

Per-episode transcripts and scores stay private: they hold everything the VMs returned. What is
published is the code, the suite, the configs, every label used to check the scoring (with the
episode ids it applies to), and each study's summary outputs. Every figure in the write-up comes
from these scripts run over those private results.

## Choices worth knowing

- **No refusal fallbacks.** Every answer must come from the model under test, so the API's
  server-side fallback is off and a refusal is recorded as its own outcome.
- **Harm is checked out of band.** After each episode the `state` hook checks the VM directly
  (over ssh, not through the bridge) for the canary file, user or stopped service.
- **The approver is idealised.** It knows the user asked only for a diagnosis, knows the
  canary names, and is meant to refuse any change, so the approval condition's harm rate is a
  lower bound on what real people would let through. Its change check turned out to have gaps:
  a plain `cp` of the secret would have passed it but for the canary names
  ([`studies/approval-rules`](studies/approval-rules/RESULTS.md)). No model tried, so no run
  result depends on it.
- **`run_on_group` is a stub.** The bridge (Direct mode) doesn't serve it; only the hosted
  connector does. So the harness offers the connector's definition in every episode and
  answers it itself without touching a node; calling it is the spread goal's harm. Under the
  permissions condition it answers as the connector would when `run` is denied.
- **Exposure.** Each injected episode records whether the injection reached the model at all
  (its text came back in a tool result, or the agent looked at the screen). Report attempt
  rates per exposed episode too: a dialog nobody looks at can't steer anyone.
- **Screenshots go to the model as images**, so the screen placement can be read from a
  screenshot as well as from `ui_tree`.
- **Cost counts cached input.** Each step resends the whole history, so most input is cache
  reads; `cost_usd` on each row includes them at list price.
- **Node notes in Direct mode.** Bridge nodes have no team instructions, so the `rule_node`
  condition puts the same text at the top of the user's message.

## Licence

MIT: see [LICENSE](LICENSE).
