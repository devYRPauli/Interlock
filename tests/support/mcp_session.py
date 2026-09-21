"""Subprocess MCP client shared by proxy integration tests."""

import json
import os
import queue
import signal
import subprocess
import sys
import threading
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])
FAKE = os.path.join(ROOT, "tests", "fake_mcp_server.py")


PAYMENTS_CONFIG = {
    "journal_dir": "journal",
    "claim_ttl": 1,  # a killed proxy's claim expires quickly, so the restart can recover it
    "tools": {
        "create_refund": {
            "key": ["order_id"],
            "premises": {
                "tool": "get_order",
                "arguments": {"order_id": "order_id"},
                "fields": ["refunded_total"],
            },
            "lookup": {
                "tool": "find_refund",
                "arguments": {"reference": "$effect_id"},
                "found": "found",
            },
            "idempotency_argument": "reference",
        }
    },
}


class Session:
    """One proxy process (and its upstream child) in its own process group, with a line reader."""

    def __init__(self, cwd, state, slow=0, slow_before=0, modern=False, stderr=None, server=None):
        """modern: no handshake; every request carries the 2026-07-28 protocol envelope in _meta, as the spec says."""
        env = {
            **os.environ,
            "FAKE_STATE": state,
            "FAKE_SLOW": str(slow),
            "FAKE_SLOW_BEFORE": str(slow_before),
            "PYTHONPATH": ROOT,
            "FAKE_LOG": os.path.join(cwd, "calls.jsonl"),
        }
        self.stderr = open(stderr, "a") if stderr else subprocess.DEVNULL
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "interlock.mcp_proxy",
                "--config",
                "config.json",
                "--",
                sys.executable,
                server or FAKE,
            ],
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        self.lines = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.ids, self.modern = 0, modern
        if not modern:
            self.request(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            )
            self.write({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _read(self):
        try:
            for line in self.proc.stdout:
                if line.strip():
                    self.lines.put(json.loads(line))
        except (ValueError, OSError):
            pass

    def _release(self):
        self.reader.join(timeout=5)
        for pipe in (
            self.proc.stdin,
            self.proc.stdout,
            None if self.stderr == subprocess.DEVNULL else self.stderr,
        ):
            if pipe is None:
                continue
            try:
                pipe.close()
            except (ValueError, OSError):
                pass

    def write(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def request(self, method, params, wait=True):
        self.ids += 1
        if self.modern:
            params = {
                **params,
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                    "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
                },
            }
        self.write({"jsonrpc": "2.0", "id": self.ids, "method": method, "params": params})
        if not wait:
            return None
        while True:
            msg = self.lines.get(timeout=20)
            if msg.get("id") == self.ids:
                return msg["result"]

    def refund(self, order_id, amount, wait=True):
        return self.request(
            "tools/call",
            {"name": "create_refund", "arguments": {"order_id": order_id, "amount": amount}},
            wait,
        )

    def kill(self):
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        else:
            os.killpg(self.proc.pid, signal.SIGKILL)
        self.proc.wait()
        self._release()

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=20)
        self._release()
