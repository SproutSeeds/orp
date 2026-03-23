from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def _run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--repo-root",
            str(root),
            *args,
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class OrpKernelTests(unittest.TestCase):
    def test_kernel_scaffold_writes_task_template_and_validate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            scaffold = _run_cli(
                root,
                "kernel",
                "scaffold",
                "--artifact-class",
                "task",
                "--out",
                "analysis/my-task.kernel.yml",
                "--name",
                "trace widget",
                "--json",
            )
            self.assertEqual(scaffold.returncode, 0, msg=scaffold.stderr + "\n" + scaffold.stdout)
            scaffold_payload = json.loads(scaffold.stdout)
            self.assertTrue(scaffold_payload["ok"])
            self.assertEqual(scaffold_payload["artifact_class"], "task")
            self.assertEqual(scaffold_payload["path"], "analysis/my-task.kernel.yml")
            self.assertTrue((root / "analysis" / "my-task.kernel.yml").exists())

            validate = _run_cli(root, "kernel", "validate", "analysis/my-task.kernel.yml", "--json")
            self.assertEqual(validate.returncode, 0, msg=validate.stderr + "\n" + validate.stdout)
            validate_payload = json.loads(validate.stdout)
            self.assertTrue(validate_payload["ok"])
            self.assertEqual(validate_payload["artifact_result"]["artifact_class"], "task")

    def test_kernel_validate_detects_artifact_class_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_json(
                root / "analysis" / "decision.kernel.json",
                {
                    "schema_version": "1.0.0",
                    "artifact_class": "decision",
                    "question": "what path should we choose?",
                    "chosen_path": "ship the terminal trace widget",
                    "rejected_alternatives": ["do nothing"],
                    "rationale": "we need visibility now",
                    "consequences": ["extra implementation work"],
                },
            )
            proc = _run_cli(
                root,
                "kernel",
                "validate",
                "analysis/decision.kernel.json",
                "--artifact-class",
                "task",
                "--json",
            )
            self.assertEqual(proc.returncode, 1, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["ok"])
            issues = payload["artifact_result"]["issues"]
            self.assertTrue(any("artifact_class mismatch" in issue for issue in issues))

    def test_structure_kernel_gate_passes_with_valid_task_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_json(
                root / "analysis" / "trace-widget.kernel.json",
                {
                    "schema_version": "1.0.0",
                    "artifact_class": "task",
                    "object": "terminal trace widget",
                    "goal": "surface lane state and drift",
                    "boundary": "terminal-first operator workflow",
                    "constraints": ["low friction", "local-first"],
                    "success_criteria": "operator spots a drifting lane within ten seconds",
                },
            )
            _write_json(
                root / "orp.kernel.sample.json",
                {
                    "profiles": {
                        "default": {
                            "description": "kernel gate",
                            "mode": "test",
                            "packet_kind": "problem_scope",
                            "gate_ids": ["kernel"],
                        }
                    },
                    "gates": [
                        {
                            "id": "kernel",
                            "description": "validate task artifact shape",
                            "phase": "structure_kernel",
                            "command": "true",
                            "pass": {"exit_codes": [0]},
                            "kernel": {
                                "mode": "hard",
                                "artifacts": [
                                    {
                                        "path": "analysis/trace-widget.kernel.json",
                                        "artifact_class": "task",
                                    }
                                ],
                            },
                        }
                    ],
                },
            )

            proc = _run_cli(
                root,
                "--config",
                "orp.kernel.sample.json",
                "gate",
                "run",
                "--profile",
                "default",
                "--run-id",
                "kernel-pass",
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertEqual(payload["overall"], "PASS")
            run_record = json.loads((root / payload["run_record"]).read_text(encoding="utf-8"))
            result = run_record["results"][0]
            self.assertEqual(result["phase"], "structure_kernel")
            self.assertEqual(result["status"], "pass")
            self.assertTrue(result["kernel_validation"]["valid"])
            self.assertEqual(result["kernel_validation"]["artifacts_total"], 1)
            self.assertEqual(result["kernel_validation"]["artifacts_valid"], 1)

    def test_structure_kernel_gate_fails_in_hard_mode_when_fields_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_json(
                root / "analysis" / "trace-widget.kernel.json",
                {
                    "schema_version": "1.0.0",
                    "artifact_class": "task",
                    "object": "terminal trace widget",
                    "goal": "surface lane state and drift",
                    "boundary": "terminal-first operator workflow",
                },
            )
            _write_json(
                root / "orp.kernel.sample.json",
                {
                    "profiles": {
                        "default": {
                            "description": "kernel gate",
                            "mode": "test",
                            "packet_kind": "problem_scope",
                            "gate_ids": ["kernel"],
                        }
                    },
                    "gates": [
                        {
                            "id": "kernel",
                            "description": "validate task artifact shape",
                            "phase": "structure_kernel",
                            "command": "true",
                            "pass": {"exit_codes": [0]},
                            "kernel": {
                                "mode": "hard",
                                "artifacts": [
                                    {
                                        "path": "analysis/trace-widget.kernel.json",
                                        "artifact_class": "task",
                                    }
                                ],
                            },
                        }
                    ],
                },
            )

            proc = _run_cli(
                root,
                "--config",
                "orp.kernel.sample.json",
                "gate",
                "run",
                "--profile",
                "default",
                "--run-id",
                "kernel-fail",
                "--json",
            )
            self.assertEqual(proc.returncode, 1, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertEqual(payload["overall"], "FAIL")
            run_record = json.loads((root / payload["run_record"]).read_text(encoding="utf-8"))
            result = run_record["results"][0]
            self.assertEqual(result["status"], "fail")
            self.assertFalse(result["kernel_validation"]["valid"])
            self.assertIn("constraints", result["kernel_validation"]["artifacts"][0]["missing_fields"])
            self.assertIn("success_criteria", result["kernel_validation"]["artifacts"][0]["missing_fields"])

    def test_structure_kernel_gate_soft_mode_records_issues_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_json(
                root / "analysis" / "trace-widget.kernel.json",
                {
                    "schema_version": "1.0.0",
                    "artifact_class": "task",
                    "object": "terminal trace widget",
                    "goal": "surface lane state and drift",
                    "boundary": "terminal-first operator workflow",
                },
            )
            _write_json(
                root / "orp.kernel.sample.json",
                {
                    "profiles": {
                        "default": {
                            "description": "kernel gate",
                            "mode": "test",
                            "packet_kind": "problem_scope",
                            "gate_ids": ["kernel"],
                        }
                    },
                    "gates": [
                        {
                            "id": "kernel",
                            "description": "validate task artifact shape",
                            "phase": "structure_kernel",
                            "command": "true",
                            "pass": {"exit_codes": [0]},
                            "kernel": {
                                "mode": "soft",
                                "artifacts": [
                                    {
                                        "path": "analysis/trace-widget.kernel.json",
                                        "artifact_class": "task",
                                    }
                                ],
                            },
                        }
                    ],
                },
            )

            proc = _run_cli(
                root,
                "--config",
                "orp.kernel.sample.json",
                "gate",
                "run",
                "--profile",
                "default",
                "--run-id",
                "kernel-soft",
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertEqual(payload["overall"], "PASS")
            run_record = json.loads((root / payload["run_record"]).read_text(encoding="utf-8"))
            result = run_record["results"][0]
            self.assertEqual(result["status"], "pass")
            self.assertFalse(result["kernel_validation"]["valid"])
            self.assertEqual(result["kernel_validation"]["mode"], "soft")

    def test_kernel_stats_reports_observed_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_json(
                root / "orp" / "artifacts" / "run-kernel-stats" / "RUN.json",
                {
                    "run_id": "run-kernel-stats",
                    "results": [
                        {
                            "phase": "structure_kernel",
                            "kernel_validation": {
                                "mode": "hard",
                                "valid": False,
                                "artifacts": [
                                    {
                                        "path": "analysis/task.kernel.yml",
                                        "valid": False,
                                        "artifact_class": "task",
                                        "expected_artifact_class": "task",
                                        "missing_fields": ["constraints", "success_criteria"],
                                        "issues": [
                                            "missing required fields: constraints, success_criteria",
                                        ],
                                    }
                                ],
                            },
                        }
                    ],
                },
            )

            proc = _run_cli(root, "kernel", "stats", "--json")
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["runs_scanned"], 1)
            self.assertEqual(payload["runs_with_kernel_validation"], 1)
            self.assertEqual(payload["artifacts_invalid"], 1)
            self.assertEqual(payload["artifact_class_counts"]["task"], 1)
            top_missing = {row["field"]: row["count"] for row in payload["top_missing_fields"]}
            self.assertEqual(top_missing["constraints"], 1)
            self.assertEqual(top_missing["success_criteria"], 1)

    def test_kernel_propose_scaffolds_default_proposal_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = _run_cli(
                root,
                "kernel",
                "propose",
                "--kind",
                "add_field",
                "--title",
                "Add rollback path",
                "--artifact-class",
                "policy",
                "--field",
                "rollback_path",
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["proposal_kind"], "add_field")
            self.assertEqual(payload["path"], "analysis/kernel-proposals/add-rollback-path.yml")
            proposal_path = root / "analysis" / "kernel-proposals" / "add-rollback-path.yml"
            self.assertTrue(proposal_path.exists())
            proposal = _run_cli(root, "kernel", "validate", "analysis/kernel-proposals/add-rollback-path.yml", "--json")
            self.assertEqual(proposal.returncode, 1)
            text = proposal_path.read_text(encoding="utf-8")
            self.assertIn("proposal_kind: add_field", text)
            self.assertIn("rollback_path", text)

    def test_kernel_migrate_canonicalizes_and_drops_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact_path = root / "analysis" / "decision.kernel.json"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(
                json.dumps(
                    {
                        "rationale": "keep active work front and center",
                        "artifact_class": "decision",
                        "unknown_field": "drop me",
                        "consequences": ["linked projects become the home"],
                        "question": "what should the home screen foreground?",
                        "schema_version": "0.9.0",
                        "chosen_path": "foreground linked projects",
                        "rejected_alternatives": ["keep the old idea board"],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            proc = _run_cli(
                root,
                "kernel",
                "migrate",
                "analysis/decision.kernel.json",
                "--drop-unknown-fields",
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["schema_version_updated"])
            self.assertEqual(payload["schema_version_after"], "1.0.0")
            self.assertEqual(payload["dropped_unknown_fields"], ["unknown_field"])
            self.assertTrue(payload["validation"]["valid"])

            migrated = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(list(migrated.keys())[:3], ["schema_version", "artifact_class", "question"])
            self.assertNotIn("unknown_field", migrated)
            self.assertEqual(migrated["schema_version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
