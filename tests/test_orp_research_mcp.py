from __future__ import annotations

import json
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MCP = REPO_ROOT / "scripts" / "orp-mcp"


def rpc(proc: subprocess.Popen[str], payload: dict[str, object]) -> dict[str, object]:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    ready, _, _ = select.select([proc.stdout], [], [], 5)
    if not ready:
        raise AssertionError("timed out waiting for MCP response")
    line = proc.stdout.readline()
    return json.loads(line)


class OrpResearchMcpTests(unittest.TestCase):
    def test_mcp_lists_and_calls_research_ask(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = subprocess.Popen(
                [sys.executable, str(MCP)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(REPO_ROOT),
            )
            try:
                init = rpc(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"},
                    },
                )
                self.assertEqual(init["result"]["serverInfo"]["name"], "orp-research")

                tools = rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
                tool_names = {row["name"] for row in tools["result"]["tools"]}
                self.assertIn("orp_research_ask", tool_names)
                self.assertIn("orp_research_status", tool_names)
                self.assertIn("orp_research_show", tool_names)

                call = rpc(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "orp_research_ask",
                            "arguments": {
                                "repo_root": str(root),
                                "question": "Can ORP expose this as a Codex tool?",
                                "run_id": "research-mcp",
                            },
                        },
                    },
                )
                self.assertFalse(call["result"].get("isError", False))
                text = call["result"]["content"][0]["text"]
                result_payload = json.loads(text)
                self.assertEqual(result_payload["run_id"], "research-mcp")
                self.assertEqual(result_payload["status"], "planned")
                self.assertTrue((root / result_payload["artifacts"]["answer_json"]).exists())
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    unittest.main()
