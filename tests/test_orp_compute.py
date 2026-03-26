from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
BIN = REPO_ROOT / "bin" / "orp.js"
BREAKTHROUGHS_DEP = REPO_ROOT / "node_modules" / "breakthroughs"


class OrpComputeTests(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node not found on PATH")
        if not BREAKTHROUGHS_DEP.exists():
            self.skipTest("breakthroughs dependency not installed; run npm install first")

    def _write_json(self, root: Path, name: str, payload: dict) -> Path:
        path = root / name
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def test_compute_decide_allows_local_unmetered_rung(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orp-compute-decide-local.") as td:
            root = Path(td)
            input_path = self._write_json(
                root,
                "compute-input.json",
                {
                    "decision": {
                        "id": "adult-vs-developmental-rgc",
                        "question": "Can the route generalize on an adult holdout?",
                        "requiredOutputs": ["metrics.csv", "impact.md"],
                    },
                    "rung": {
                        "id": "local-4090-scout",
                        "label": "Local 4090 scout",
                        "spendClass": "local_unmetered",
                        "admitted": True,
                    },
                    "policy": {
                        "local": {"defaultAction": "allow"},
                        "paid": {"defaultAction": "require_explicit_approval", "approvedRungs": []},
                    },
                    "packet": {
                        "id": "wave-1-promotion-evidence",
                        "decisionId": "adult-vs-developmental-rgc",
                        "rungId": "local-4090-scout",
                        "question": "Run the first admissible adult holdout wave.",
                        "stopCondition": "Hold if signal collapses on adult holdout.",
                        "requiredOutputs": ["metrics.csv", "impact.md"],
                    },
                },
            )
            packet_out = root / "orp-compute-packet.json"
            proc = subprocess.run(
                [
                    "node",
                    str(BIN),
                    "compute",
                    "decide",
                    "--input",
                    str(input_path),
                    "--packet-out",
                    str(packet_out),
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["dispatch_result"]["action"], "run_local")
            packet_payload = json.loads(packet_out.read_text(encoding="utf-8"))
            self.assertEqual(packet_payload["kind"], "problem_scope")
            self.assertEqual(packet_payload["summary"]["overall_result"], "PASS")

    def test_compute_decide_requests_paid_approval_for_metered_rung(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orp-compute-decide-paid.") as td:
            root = Path(td)
            input_path = self._write_json(
                root,
                "compute-input.json",
                {
                    "decision": {
                        "id": "adult-vs-developmental-rgc",
                        "question": "Can the route generalize on an adult holdout?",
                        "requiredOutputs": ["metrics.csv", "impact.md"],
                    },
                    "rung": {
                        "id": "h100-transfer",
                        "label": "Paid H100 transfer",
                        "spendClass": "paid_metered",
                        "admitted": True,
                    },
                    "policy": {
                        "local": {"defaultAction": "allow"},
                        "paid": {"defaultAction": "require_explicit_approval", "approvedRungs": []},
                    },
                    "packet": {
                        "id": "wave-h100-transfer",
                        "decisionId": "adult-vs-developmental-rgc",
                        "rungId": "h100-transfer",
                        "question": "Escalate to paid transfer if scout wins.",
                        "stopCondition": "Hold if scout baselines already answer the question.",
                        "requiredOutputs": ["metrics.csv", "impact.md"],
                    },
                },
            )
            proc = subprocess.run(
                [
                    "node",
                    str(BIN),
                    "compute",
                    "decide",
                    "--input",
                    str(input_path),
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["dispatch_result"]["action"], "request_paid_approval")
            self.assertEqual(payload["gate_result"]["status"], "hold")

    def test_compute_run_local_executes_command_and_writes_receipts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orp-compute-run-local.") as td:
            root = Path(td)
            input_path = self._write_json(
                root,
                "compute-input.json",
                {
                    "decision": {
                        "id": "adult-vs-developmental-rgc",
                        "question": "Can the route generalize on an adult holdout?",
                        "requiredOutputs": ["metrics.csv", "impact.md"],
                    },
                    "rung": {
                        "id": "local-4090-scout",
                        "label": "Local 4090 scout",
                        "spendClass": "local_unmetered",
                        "admitted": True,
                    },
                    "policy": {
                        "local": {"defaultAction": "allow"},
                        "paid": {"defaultAction": "require_explicit_approval", "approvedRungs": []},
                    },
                    "packet": {
                        "id": "wave-1-promotion-evidence",
                        "decisionId": "adult-vs-developmental-rgc",
                        "rungId": "local-4090-scout",
                        "question": "Run the first admissible adult holdout wave.",
                        "stopCondition": "Hold if signal collapses on adult holdout.",
                        "requiredOutputs": ["metrics.csv", "impact.md"],
                    },
                    "repo": {
                        "rootPath": str(REPO_ROOT),
                        "git": {"branch": "main", "commit": "local-test"},
                    },
                    "orp": {
                        "boardId": "targeted_compute",
                        "problemId": "adult-vs-developmental-rgc",
                        "artifactRoot": "orp/artifacts",
                    },
                },
            )
            task_path = self._write_json(
                root,
                "task.json",
                {
                    "command": "node",
                    "args": ["-e", "process.stdout.write('hello compute')"],
                    "cwd": str(REPO_ROOT),
                    "timeoutMs": 5000,
                },
            )
            receipt_out = root / "execution-receipt.json"
            packet_out = root / "orp-compute-packet.json"
            proc = subprocess.run(
                [
                    "node",
                    str(BIN),
                    "compute",
                    "run-local",
                    "--input",
                    str(input_path),
                    "--task",
                    str(task_path),
                    "--receipt-out",
                    str(receipt_out),
                    "--packet-out",
                    str(packet_out),
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["dispatch_result"]["action"], "run_local")
            self.assertEqual(payload["execution_receipt"]["status"], "pass")
            self.assertEqual(payload["execution_receipt"]["stdout"], "hello compute")
            self.assertTrue(receipt_out.exists())
            self.assertTrue(packet_out.exists())
            packet_payload = json.loads(packet_out.read_text(encoding="utf-8"))
            self.assertEqual(packet_payload["kind"], "problem_scope")
            self.assertEqual(packet_payload["summary"]["overall_result"], "PASS")


if __name__ == "__main__":
    unittest.main()
