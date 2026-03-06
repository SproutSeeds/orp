from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"
PACKAGE_JSON = REPO_ROOT / "package.json"
PACKAGE_VERSION = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["version"]


def _run_cli(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(CLI), "--repo-root", str(repo_root), "--config", "orp.sample.json", *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))


class OrpPacketEmitTests(unittest.TestCase):
    def test_packet_emit_uses_package_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "run-20260305-170000"

            config = {
                "profiles": {
                    "default": {
                        "packet_kind": "problem_scope",
                        "gate_ids": [],
                    }
                },
                "gates": [],
            }
            (root / "orp.sample.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            run_dir = root / "orp" / "artifacts" / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            run_payload = {
                "run_id": run_id,
                "config_path": "orp.sample.json",
                "profile": "default",
                "started_at_utc": "2026-03-05T17:00:00Z",
                "ended_at_utc": "2026-03-05T17:00:05Z",
                "deterministic_input_hash": "sha256:test-hash",
                "results": [],
                "summary": {
                    "overall_result": "PASS",
                    "gates_passed": 0,
                    "gates_failed": 0,
                    "gates_total": 0,
                },
            }
            (run_dir / "RUN.json").write_text(json.dumps(run_payload, indent=2) + "\n", encoding="utf-8")

            state_path = root / "orp" / "state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "last_run_id": run_id,
                        "last_packet_id": "",
                        "runs": {run_id: f"orp/artifacts/{run_id}/RUN.json"},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            proc = _run_cli(root, ["packet", "emit", "--profile", "default", "--run-id", run_id])
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            self.assertIn(f"packet_id=pkt-problem_scope-{run_id}", proc.stdout)

            packet_json = root / "orp" / "packets" / f"pkt-problem_scope-{run_id}.json"
            self.assertTrue(packet_json.exists(), msg=f"missing packet json: {packet_json}")

            packet = json.loads(packet_json.read_text(encoding="utf-8"))
            self.assertEqual(packet["run"]["tool"]["name"], "orp")
            self.assertEqual(packet["run"]["tool"]["version"], PACKAGE_VERSION)

    def test_packet_emit_collects_atomic_context_from_starter_board_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "run-20260306-160000"

            config = {
                "atomic_board": {
                    "enabled": True,
                    "board_path": "analysis/problem857_counting_gateboard.json",
                },
                "profiles": {
                    "default": {
                        "packet_kind": "problem_scope",
                        "gate_ids": [],
                    }
                },
                "gates": [],
            }
            (root / "orp.sample.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            board_path = root / "analysis" / "problem857_counting_gateboard.json"
            board_path.parent.mkdir(parents=True, exist_ok=True)
            board_payload = {
                "board_id": "problem857_counting_gateboard",
                "problem_id": 857,
                "route_status": [
                    {
                        "route": "container_v2",
                        "loose_done": 5,
                        "loose_total": 7,
                        "strict_done": 4,
                        "strict_total": 7,
                    }
                ],
            }
            board_path.write_text(json.dumps(board_payload, indent=2) + "\n", encoding="utf-8")

            run_dir = root / "orp" / "artifacts" / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            run_payload = {
                "run_id": run_id,
                "config_path": "orp.sample.json",
                "profile": "default",
                "started_at_utc": "2026-03-06T16:00:00Z",
                "ended_at_utc": "2026-03-06T16:00:05Z",
                "deterministic_input_hash": "sha256:test-hash",
                "results": [],
                "summary": {
                    "overall_result": "PASS",
                    "gates_passed": 0,
                    "gates_failed": 0,
                    "gates_total": 0,
                },
            }
            (run_dir / "RUN.json").write_text(json.dumps(run_payload, indent=2) + "\n", encoding="utf-8")

            state_path = root / "orp" / "state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(
                json.dumps(
                    {
                        "last_run_id": run_id,
                        "last_packet_id": "",
                        "runs": {run_id: f"orp/artifacts/{run_id}/RUN.json"},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            proc = _run_cli(root, ["packet", "emit", "--profile", "default", "--run-id", run_id])
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            packet_json = root / "orp" / "packets" / f"pkt-problem_scope-{run_id}.json"
            packet = json.loads(packet_json.read_text(encoding="utf-8"))
            atomic = packet.get("atomic_context", {})
            self.assertEqual(atomic.get("board_id"), "problem857_counting_gateboard")
            self.assertEqual(atomic.get("problem_id"), "857")
            self.assertEqual(
                atomic.get("route_status", {}).get("container_v2"),
                {
                    "done": 5,
                    "total": 7,
                    "strict_done": 4,
                    "strict_total": 7,
                },
            )


if __name__ == "__main__":
    unittest.main()
