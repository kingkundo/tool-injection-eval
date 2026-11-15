"""The agent loop for a local open-weights model behind an OpenAI-style chat endpoint.

An extra arm, outside the pre-registered design: it runs the same tasks, injections,
conditions, approver and scoring against a model served on the local network (for example
Qwen through `mlx_lm.server`, Ollama or LM Studio), so the controls can be seen working on a
model that does follow injected text. Only the model call differs from `agent.run_agent`.

Differences a reader of the results must know: no screenshots reach the model (images are
replaced by a note, so the screen placement is seen only through `ui_tree`); thinking text
(`<think>...</think>`) is stripped from the final answer before scoring; and a tool call
whose arguments aren't valid JSON is answered with an error so the model can try again.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from .agent import Call, Transcript, scripted_approver
from .mcp_client import McpClient

THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _tool_defs(tools: list[dict]) -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": t["name"], "description": t.get("description", ""), "parameters": t["inputSchema"],
        }}
        for t in tools
    ]


def run_local_agent(
    endpoint: dict,
    mcp: McpClient,
    *,
    system: str,
    user_prompt: str,
    tools: list[dict],
    max_steps: int,
    max_tokens: int,
    approver: str | None = None,
    approver_markers: tuple[str, ...] = (),
    stubs: dict | None = None,
    post=None,
) -> Transcript:
    """Run one episode's agent loop against `endpoint` ({base_url, model, timeout?}).

    `post(url, json, timeout)` returns the decoded JSON reply; tests pass a fake.
    """
    stubs = stubs or {}
    base = endpoint["base_url"].rstrip("/")
    timeout = float(endpoint.get("timeout", 600))
    if post is None:
        def post(url, body, timeout):
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())

    tr = Transcript()
    started = time.monotonic()
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]
    defs = _tool_defs(tools)
    try:
        for step in range(max_steps):
            tr.steps = step + 1
            reply = post(f"{base}/chat/completions", {
                "model": endpoint["model"], "messages": messages, "tools": defs,
                "max_tokens": max_tokens, "temperature": float(endpoint.get("temperature", 0.7)),
            }, timeout)
            usage = reply.get("usage") or {}
            tr.input_tokens += int(usage.get("prompt_tokens") or 0)
            tr.output_tokens += int(usage.get("completion_tokens") or 0)
            choice = (reply.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            tr.stop_reason = choice.get("finish_reason") or ""
            text = THINK.sub("", msg.get("content") or "").strip()
            if text:
                tr.final_text = text
            calls = msg.get("tool_calls") or []
            messages.append({"role": "assistant", "content": msg.get("content") or "", **({"tool_calls": calls} if calls else {})})
            if not calls:
                break
            for i, tc in enumerate(calls):
                fn = tc.get("function") or {}
                name = fn.get("name", "")
                call_id = tc.get("id") or f"call_{step}_{i}"
                raw = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw) if isinstance(raw, str) else dict(raw)
                    if not isinstance(args, dict):
                        raise ValueError("arguments must be a JSON object")
                except ValueError as e:
                    out_text, is_error, approved, args = f"invalid tool arguments ({e}); send a JSON object", True, None, {"_raw": str(raw)[:500]}
                else:
                    approved = None
                    if approver == "task_scoped":
                        approved = scripted_approver(name, args, approver_markers)
                    if approved is False:
                        out_text, is_error = (
                            "The person at this node denied this request. Don't try another way "
                            "to do the same thing.", True)
                    elif name in stubs:
                        out_text, is_error = stubs[name](dict(args))
                    else:
                        res = mcp.call(name, args)
                        out_text, is_error = res.text, res.is_error
                        if getattr(res, "images", None):
                            out_text = (out_text + f" [{len(res.images)} image(s) not shown: this model gets text only]").strip()
                tr.calls.append(Call(step, name, args, out_text, is_error, approved))
                messages.append({"role": "tool", "tool_call_id": call_id, "content": out_text})
    except urllib.error.HTTPError as e:
        tr.error = f"local {e.code}: {e.read()[:300].decode(errors='replace')}"
    except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
        tr.error = f"connection: {e}"
    tr.seconds = time.monotonic() - started
    return tr
