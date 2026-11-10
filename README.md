# Tool-output injection eval

A small research harness, not part of the product. It measures how often an AI agent that
manages machines through Dashcat can be steered by text planted in what the tools return (a
log line, a file, a dialog on screen), and how much each deployment-side control cuts that:
a system-prompt rule, node instructions, Dashcat permissions and a person approving actions.

Design, hypotheses and limits: the design doc linked from the PR that added this folder.
Nothing here ships to users, and nothing in `apps/` or `crates/` depends on it.

## Safety rules

- Run it only against **throwaway VMs** paired with a bridge that is paired with nothing else.
  Every episode resets the VM from a snapshot first.
- Every harmful target is a **canary** (a fake secret, a made-up user, a dummy service). Never
  put a real secret or a real machine in `config.yaml`.
- The most effective exact injection strings stay in `suite/private/` (git-ignored). Publish
  rates, the harness and the injection categories, not a ready-made attack list.

## Layout

| Path | What |
|---|---|
| `suite/tasks.yaml` | 10 everyday sysadmin tasks and where each one's untrusted text lives |
| `suite/injections.yaml` | Goals (exfiltrate, persist, disable, spread), placements, styles, sampling |
| `suite/conditions.yaml` | The five conditions: bare, rule, rule + node notes, permissions, approval |
| `evalkit/mcp_client.py` | Talks to `dashcat-bridge mcp` on stdio, like `scripts/e2e.py` |
| `evalkit/agent.py` | The agent loop (Claude API, manual tool loop) and the scripted approver |
| `evalkit/scoring.py` | Attempt, harm, detection and refusal for one episode |
| `evalkit/stubs.py` | `run_on_group`, which the harness answers itself (see below) |
| `evalkit/costs.py` | List prices, each episode's cost, and the forecast `--plan` prints |
| `evalkit/dryrun.py` | The whole pipeline against a scripted model and in-memory nodes |
| `evalkit/run.py` | Runs the suite, one JSON line per episode, resumable |
| `evalkit/report.py` | Rates with 95% Wilson intervals by condition, model, placement and goal, plus cost |
| `scripts/` | VirtualBox reset, and one-off setup for each VM (task files, canaries, services, dialog) |
| `tests/` | Offline tests with a fake model and a fake bridge, including a full dry run |

## Running it

Python 3.10+. On a Windows host, hooks run through Git for Windows' bash (`hook_shell` in the
config), and `scripts/reset-vm.sh` restores VirtualBox VMs. Build each VM with
`scripts/setup-linux-vm.sh` or `scripts/setup-windows-vm.ps1`, install Dashcat Agent and the
admin service (adding users and stopping services needs `run_as_admin`), pair it, and snapshot
it running as `clean`. On Windows, an administrator's ssh key goes in
`C:\ProgramData\ssh\administrators_authorized_keys`. The screen hooks in `config.example.yaml` are untested: check a dialog really
appears on each VM's desktop before the pilot.

```bash
cd research/tool-injection-eval
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

Credentials come from the Anthropic SDK's usual sources (`ANTHROPIC_API_KEY` or
`ant auth login`); never put a key in `config.yaml`.

## Choices worth knowing

- **No refusal fallbacks.** Every answer must come from the model under test, so the API's
  server-side fallback is off and a refusal is recorded as its own outcome.
- **Harm is checked out of band.** After each episode the `state` hook checks the VM directly
  (over ssh, not through the bridge) for the canary file, user or stopped service.
- **The approver is idealised.** It knows the user asked only for a diagnosis and refuses any
  change, so the approval condition's harm rate is a lower bound on what real people would let
  through.
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
