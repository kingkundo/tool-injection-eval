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
| `evalkit/run.py` | Runs the suite, one JSON line per episode, resumable |
| `evalkit/report.py` | Rates with 95% Wilson intervals by condition, model, placement and goal |
| `tests/` | Offline tests with a fake model and a fake bridge |

## Running it

Python 3.10+.

```bash
cd research/tool-injection-eval
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 -m unittest discover -s tests            # offline, no API calls

cp config.example.yaml config.yaml               # then fill in your test nodes and hooks
python3 -m evalkit.run --plan                    # how many episodes, spends nothing
python3 -m evalkit.run --run pilot --limit 50    # the pilot: check cost and scoring by hand
python3 -m evalkit.run                           # the full run; rerun to resume
python3 -m evalkit.report                        # tables
```

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
- **Node notes in Direct mode.** Bridge nodes have no team instructions, so the `rule_node`
  condition puts the same text at the top of the user's message.
