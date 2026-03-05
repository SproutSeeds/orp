from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def _write_run_json(repo_root: Path, run_id: str, *, fail: bool) -> Path:
    run_dir = repo_root / "orp" / "artifacts" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_payload = {
        "run_id": run_id,
        "config_path": "orp.sample.yml",
        "profile": "sunflower_live_compare_20",
        "started_at_utc": "2026-03-05T16:00:24Z",
        "ended_at_utc": "2026-03-05T16:00:30Z",
        "deterministic_input_hash": "sha256:test-hash",
        "results": [
            {
                "gate_id": "gate_a",
                "phase": "verification",
                "command": "python3 scripts/gate_a.py",
                "status": "fail" if fail else "pass",
                "exit_code": 1 if fail else 0,
                "duration_ms": 1234,
                "stdout_path": f"orp/artifacts/{run_id}/gate_a.stdout.log",
                "stderr_path": f"orp/artifacts/{run_id}/gate_a.stderr.log",
                "rule_issues": ["missing required substring: ready_atoms="] if fail else [],
            }
        ],
        "summary": {
            "overall_result": "FAIL" if fail else "PASS",
            "gates_passed": 0 if fail else 1,
            "gates_failed": 1 if fail else 0,
            "gates_total": 1,
        },
    }
    run_json = run_dir / "RUN.json"
    run_json.write_text(json.dumps(run_payload, indent=2) + "\n", encoding="utf-8")
    return run_json


def _run_cli(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(CLI), "--repo-root", str(repo_root), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))


class OrpReportSummaryTests(unittest.TestCase):
    def test_report_summary_from_run_id_writes_default_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_id = "run-20260305-160024"
            _write_run_json(root, run_id, fail=False)
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

            proc = _run_cli(root, ["report", "summary", "--run-id", run_id])
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn(f"run_id={run_id}", proc.stdout)

            summary_md = root / "orp" / "artifacts" / run_id / "RUN_SUMMARY.md"
            self.assertTrue(summary_md.exists())
            text = summary_md.read_text(encoding="utf-8")
            self.assertIn("What This Report Shows", text)
            self.assertIn("overall_result: `PASS`", text)

    def test_report_summary_from_run_json_renders_failure_issues(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_json = _write_run_json(root, "run-20260305-160900", fail=True)
            out_md = root / "report.md"

            proc = _run_cli(
                root,
                [
                    "report",
                    "summary",
                    "--run-json",
                    str(run_json),
                    "--out",
                    str(out_md),
                ],
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertTrue(out_md.exists())
            text = out_md.read_text(encoding="utf-8")
            self.assertIn("overall_result: `FAIL`", text)
            self.assertIn("## Failing Conditions", text)
            self.assertIn("missing required substring: ready_atoms=", text)


if __name__ == "__main__":
    unittest.main()

