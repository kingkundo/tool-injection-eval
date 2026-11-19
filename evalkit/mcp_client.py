"""A minimal MCP client for `dashcat-bridge mcp`: newline-delimited JSON-RPC on stdio.

No MCP library is needed, and the harness talks to the bridge exactly as an AI app does.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field


class McpError(RuntimeError):
    pass


@dataclass
class ToolResult:
    text: str
    is_error: bool
    # (media type, base64 data) for each image part, such as a screenshot's.
    images: list[tuple[str, str]] = field(default_factory=list)


class McpClient:
    def __init__(self, command: list[str], timeout: float = 240.0) -> None:
        self.timeout = timeout
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._lines: queue.Queue[bytes] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self._next_id = 0
        self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "tool-injection-eval", "version": "0"},
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _read(self) -> None:
        assert self.proc.stdout
        for line in self.proc.stdout:
            self._lines.put(line)

    def _send(self, message: dict) -> None:
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(message).encode() + b"\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict, timeout: float | None = None) -> dict:
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params})
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            try:
                line = self._lines.get(timeout=max(0.0, deadline - time.monotonic()))
            except queue.Empty:
                raise McpError(f"no reply to {method} within {timeout or self.timeout:.0f}s") from None
            message = json.loads(line)
            if message.get("id") == self._next_id:
                if "error" in message:
                    raise McpError(f"{method} failed: {message['error']}")
                return message["result"]

    def list_tools(self) -> list[dict]:
        return self.request("tools/list", {})["tools"]

    def call(self, name: str, arguments: dict) -> ToolResult:
        # A command the agent gives a long timeout (Windows disk scans take minutes) must not
        # outlast the client's wait: in the pilot that failed whole episodes at 120 s.
        wait = self.timeout
        if isinstance(arguments.get("timeout_secs"), (int, float)):
            wait = max(wait, float(arguments["timeout_secs"]) + 30)
        result = self.request("tools/call", {"name": name, "arguments": arguments}, timeout=wait)
        parts = result.get("content", [])
        text = "".join(part.get("text", "") for part in parts if part.get("type", "text") == "text")
        images = [(part.get("mimeType", "image/png"), part["data"]) for part in parts if part.get("type") == "image" and part.get("data")]
        return ToolResult(text=text, is_error=bool(result.get("isError")), images=images)

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def __enter__(self) -> McpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
