from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"
PACKAGE_JSON = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
PACKAGE_NAME = PACKAGE_JSON["name"]
PACKAGE_VERSION = PACKAGE_JSON["version"]


def load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_update_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpUpdateTests(unittest.TestCase):
    def run_update(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            [sys.executable, str(CLI), "update", *args],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=merged_env,
        )

    def test_update_json_reports_source_checkout_safely(self) -> None:
        proc = self.run_update(
            "--json",
            env={
                "ORP_UPDATE_LATEST_VERSION": "9.9.9",
                "ORP_UPDATE_SOURCE_READY": "0",
                "ORP_UPDATE_SOURCE_REASON": "Source checkout is not in a safe auto-pull state.",
            },
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "update_available")
        self.assertEqual(payload["install_kind"], "source-checkout")
        self.assertFalse(payload["can_apply"])
        self.assertIn("git -C", payload["recommended_command"])
        self.assertIn("source_readiness", payload)

    def test_update_json_can_simulate_npm_install_upgrade_path(self) -> None:
        proc = self.run_update(
            "--json",
            env={
                "ORP_UPDATE_INSTALL_KIND": "npm-global",
                "ORP_UPDATE_LATEST_VERSION": "9.9.9",
            },
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "update_available")
        self.assertEqual(payload["install_kind"], "npm-global")
        self.assertTrue(payload["can_apply"])
        self.assertEqual(payload["recommended_command"], f"npm install -g {PACKAGE_NAME}@latest")

    def test_update_json_can_mark_source_checkout_as_safe_to_auto_pull(self) -> None:
        proc = self.run_update(
            "--json",
            env={
                "ORP_UPDATE_LATEST_VERSION": "9.9.9",
                "ORP_UPDATE_SOURCE_READY": "1",
                "ORP_UPDATE_SOURCE_BRANCH": "main",
                "ORP_UPDATE_SOURCE_UPSTREAM": "origin/main",
            },
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["install_kind"], "source-checkout")
        self.assertTrue(payload["can_apply"])
        self.assertEqual(payload["source_readiness"]["branch"], "main")
        self.assertEqual(payload["source_readiness"]["upstream"], "origin/main")

    def test_update_human_output_reports_when_current_version_is_up_to_date(self) -> None:
        proc = self.run_update(env={"ORP_UPDATE_LATEST_VERSION": PACKAGE_VERSION})
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        self.assertIn("ORP Update", proc.stdout)
        self.assertIn("Status: Up to date", proc.stdout)
        self.assertIn(f"Current version: {PACKAGE_VERSION}", proc.stdout)

    def test_update_yes_refuses_when_source_checkout_is_not_safe_to_pull(self) -> None:
        proc = self.run_update(
            "--json",
            "--yes",
            env={
                "ORP_UPDATE_LATEST_VERSION": "9.9.9",
                "ORP_UPDATE_SOURCE_READY": "0",
                "ORP_UPDATE_SOURCE_REASON": "Source checkout is not in a safe auto-pull state.",
            },
        )
        self.assertEqual(proc.returncode, 1, msg=proc.stderr + "\n" + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["apply"]["ok"])
        self.assertTrue(payload["apply"]["message"])

    def test_update_yes_can_apply_safe_source_checkout_via_forced_test_hook(self) -> None:
        proc = self.run_update(
            "--json",
            "--yes",
            env={
                "ORP_UPDATE_LATEST_VERSION": "9.9.9",
                "ORP_UPDATE_SOURCE_READY": "1",
                "ORP_UPDATE_SOURCE_BRANCH": "main",
                "ORP_UPDATE_SOURCE_UPSTREAM": "origin/main",
                "ORP_UPDATE_APPLY_OK": "1",
                "ORP_UPDATE_APPLY_MESSAGE": "Already up to date after pull.",
            },
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["apply"]["ok"])
        self.assertTrue(payload["apply"]["applied"])
        self.assertEqual(payload["apply"]["message"], "Already up to date after pull.")

    def test_source_checkout_readiness_translates_launchd_runtime_git_errors(self) -> None:
        module = load_cli_module()
        old_runtime_root = os.environ.get("ORP_LAUNCH_RUNTIME_ROOT")
        self.addCleanup(
            lambda: (
                os.environ.pop("ORP_LAUNCH_RUNTIME_ROOT", None)
                if old_runtime_root is None
                else os.environ.__setitem__("ORP_LAUNCH_RUNTIME_ROOT", old_runtime_root)
            )
        )
        os.environ["ORP_LAUNCH_RUNTIME_ROOT"] = "/tmp/orp-launch-runtime-test"

        def fake_run_git_at(package_root, *args, timeout_sec=5):
            return subprocess.CompletedProcess(
                ["git", *args],
                128,
                "",
                "fatal: not a git repository: '/Volumes/Code_2TB/code/orp/.git'",
            )

        module._run_git_at = fake_run_git_at
        readiness = module._source_checkout_update_readiness(REPO_ROOT)
        self.assertFalse(readiness["ok"])
        self.assertIn("background launchd runtime", readiness["reason"])
        self.assertIn("orp update", readiness["reason"])


if __name__ == "__main__":
    unittest.main()
