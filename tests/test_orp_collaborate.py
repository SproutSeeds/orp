from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


class OrpCollaborateTests(unittest.TestCase):
    def test_collaborate_workflows_json_lists_built_in_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "collaborate",
                    "workflows",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["workspace_ready"])
            self.assertEqual(payload["recommended_init_command"], "orp collaborate init")
            workflows = {row["id"]: row for row in payload["workflows"]}
            self.assertIn("full_flow", workflows)
            self.assertIn("feedback_hardening", workflows)
            self.assertEqual(
                workflows["full_flow"]["gate_ids"],
                [
                    "watch_select",
                    "viability_gate",
                    "overlap_gate",
                    "local_gate",
                    "ready_to_draft",
                    "pr_body_preflight",
                    "draft_pr_transition",
                    "draft_ci",
                    "ready_for_review",
                ],
            )
            self.assertFalse(workflows["full_flow"]["config_exists"])

    def test_collaborate_init_json_scaffolds_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "collaborate",
                    "init",
                    "--github-repo",
                    "owner/repo",
                    "--github-author",
                    "tester",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["workspace_root"], "issue-smashers")
            self.assertEqual(payload["config"], "orp.issue-smashers.yml")
            self.assertEqual(payload["feedback_config"], "orp.issue-smashers-feedback-hardening.yml")
            self.assertTrue((root / "orp" / "state.json").exists())
            self.assertTrue((root / "orp.issue-smashers.yml").exists())
            self.assertTrue((root / "orp.issue-smashers-feedback-hardening.yml").exists())
            self.assertTrue((root / "issue-smashers" / "README.md").exists())
            self.assertTrue((root / "issue-smashers" / "analysis" / "ISSUE_SMASHERS_WATCHLIST.json").exists())

    def test_collaborate_gates_and_run_use_built_in_workflow_surface(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "collaborate",
                    "init",
                    "--json",
                    "--var",
                    "WATCH_SELECT_COMMAND=printf 'selection=PASS\\n'",
                    "--var",
                    "VIABILITY_COMMAND=printf 'decision=PASS\\n'",
                    "--var",
                    "OVERLAP_COMMAND=printf 'overlap=PASS\\n'",
                    "--var",
                    "LOCAL_GATE_COMMAND=printf 'gate=PASS\\n'",
                    "--var",
                    "READY_TO_DRAFT_COMMAND=printf 'ready_to_draft=PASS\\n'",
                    "--var",
                    "PR_BODY_PREFLIGHT_COMMAND=printf 'gate=PASS\\n'",
                    "--var",
                    "DRAFT_PR_TRANSITION_COMMAND=printf 'draft_pr=PASS\\n'",
                    "--var",
                    "DRAFT_CI_COMMAND=printf 'draft_ci=PASS\\n'",
                    "--var",
                    "READY_FOR_REVIEW_COMMAND=printf 'ready_for_review=PASS\\n'",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            gates_proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "collaborate",
                    "gates",
                    "--workflow",
                    "full_flow",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(gates_proc.returncode, 0, msg=gates_proc.stderr + "\n" + gates_proc.stdout)
            gates_payload = json.loads(gates_proc.stdout)
            self.assertEqual(gates_payload["workflow"], "full_flow")
            self.assertEqual(gates_payload["profile"], "issue_smashers_full_flow")
            self.assertTrue(gates_payload["config_exists"])

            run_proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "collaborate",
                    "run",
                    "--workflow",
                    "full_flow",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(run_proc.returncode, 0, msg=run_proc.stderr + "\n" + run_proc.stdout)
            run_payload = json.loads(run_proc.stdout)
            self.assertEqual(run_payload["overall"], "PASS")
            self.assertEqual(run_payload["gates_total"], 9)


if __name__ == "__main__":
    unittest.main()
