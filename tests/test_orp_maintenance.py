from __future__ import annotations

import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"
PACKAGE_VERSION = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))["version"]


class OrpMaintenanceTests(unittest.TestCase):
    def run_cli(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=merged_env,
        )

    def test_maintenance_check_writes_cached_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "maintenance.json"
            proc = self.run_cli(
                "maintenance",
                "check",
                "--json",
                env={
                    "ORP_MAINTENANCE_STATE_PATH": str(state_path),
                    "ORP_UPDATE_LATEST_VERSION": PACKAGE_VERSION,
                    "ORP_MAINTENANCE_ALLOW_NON_DARWIN": "1",
                    "ORP_MAINTENANCE_LAUNCH_AGENTS_DIR": str(Path(td) / "LaunchAgents"),
                    "ORP_LAUNCH_RUNTIME_ROOT": str(Path(td) / "launch-runtime"),
                    "ORP_MAINTENANCE_SKIP_LAUNCHCTL": "1",
                },
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["update"]["status"], "up_to_date")
            self.assertTrue(state_path.exists())
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["update"]["status"], "up_to_date")
            self.assertEqual(state["source"], "manual")

    def test_maintenance_enable_and_disable_manage_launch_agent_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "maintenance.json"
            launch_agents_dir = Path(td) / "LaunchAgents"
            env = {
                "ORP_MAINTENANCE_STATE_PATH": str(state_path),
                "ORP_MAINTENANCE_LAUNCH_AGENTS_DIR": str(launch_agents_dir),
                "ORP_MAINTENANCE_LOGS_DIR": str(Path(td) / "logs"),
                "ORP_LAUNCH_RUNTIME_ROOT": str(Path(td) / "launch-runtime"),
                "ORP_MAINTENANCE_ALLOW_NON_DARWIN": "1",
                "ORP_MAINTENANCE_SKIP_LAUNCHCTL": "1",
                "ORP_UPDATE_LATEST_VERSION": PACKAGE_VERSION,
            }

            enable_proc = self.run_cli("maintenance", "enable", "--hour", "7", "--minute", "45", "--json", env=env)
            self.assertEqual(enable_proc.returncode, 0, msg=enable_proc.stderr + "\n" + enable_proc.stdout)
            enable_payload = json.loads(enable_proc.stdout)
            self.assertTrue(enable_payload["ok"])
            plist_path = Path(enable_payload["plist_path"])
            self.assertTrue(plist_path.exists())
            with plist_path.open("rb") as handle:
                plist_payload = plistlib.load(handle)
            self.assertEqual(plist_payload["StartCalendarInterval"]["Hour"], 7)
            self.assertEqual(plist_payload["StartCalendarInterval"]["Minute"], 45)
            self.assertEqual(plist_payload["ProgramArguments"][0], sys.executable)
            self.assertIn(str(Path(td) / "launch-runtime"), plist_payload["ProgramArguments"][1])
            self.assertTrue(Path(plist_payload["ProgramArguments"][1]).exists())
            self.assertEqual(plist_payload["WorkingDirectory"], str((Path(td) / "launch-runtime").resolve()))

            status_proc = self.run_cli("maintenance", "status", "--json", env=env)
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            status_payload = json.loads(status_proc.stdout)
            self.assertTrue(status_payload["enabled"])
            self.assertEqual(status_payload["schedule"]["hour"], 7)
            self.assertEqual(status_payload["schedule"]["minute"], 45)

            disable_proc = self.run_cli("maintenance", "disable", "--json", env=env)
            self.assertEqual(disable_proc.returncode, 0, msg=disable_proc.stderr + "\n" + disable_proc.stdout)
            disable_payload = json.loads(disable_proc.stdout)
            self.assertTrue(disable_payload["ok"])
            self.assertFalse(plist_path.exists())

    def test_home_json_surfaces_cached_maintenance_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "maintenance.json"
            cached_state = {
                "schema_version": "1.0.0",
                "checked_at": "2026-03-29T12:00:00Z",
                "source": "manual",
                "platform": "macos",
                "update": {
                    "ok": True,
                    "status": "update_available",
                    "update_available": True,
                    "tool": {
                        "current_version": PACKAGE_VERSION,
                        "latest_version": "9.9.9",
                    },
                    "recommended_command": "npm install -g open-research-protocol@latest",
                },
                "launchd": {
                    "enabled": False,
                },
            }
            state_path.write_text(json.dumps(cached_state, indent=2) + "\n", encoding="utf-8")
            proc = self.run_cli(
                "--repo-root",
                td,
                "home",
                "--json",
                env={
                    "ORP_MAINTENANCE_STATE_PATH": str(state_path),
                    "ORP_MAINTENANCE_LAUNCH_AGENTS_DIR": str(Path(td) / "LaunchAgents"),
                    "ORP_MAINTENANCE_LOGS_DIR": str(Path(td) / "logs"),
                    "ORP_LAUNCH_RUNTIME_ROOT": str(Path(td) / "launch-runtime"),
                    "ORP_MAINTENANCE_ALLOW_NON_DARWIN": "1",
                    "ORP_MAINTENANCE_SKIP_LAUNCHCTL": "1",
                },
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["maintenance"]["cached_update_available"])
            commands = {row["command"] for row in payload["quick_actions"]}
            self.assertIn("orp update --yes", commands)
            self.assertIn("orp maintenance enable --json", commands)

    def test_maintenance_launch_program_arguments_run_from_snapshot_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "maintenance.json"
            env = {
                "ORP_MAINTENANCE_STATE_PATH": str(state_path),
                "ORP_MAINTENANCE_LAUNCH_AGENTS_DIR": str(Path(td) / "LaunchAgents"),
                "ORP_MAINTENANCE_LOGS_DIR": str(Path(td) / "logs"),
                "ORP_LAUNCH_RUNTIME_ROOT": str(Path(td) / "launch-runtime"),
                "ORP_MAINTENANCE_ALLOW_NON_DARWIN": "1",
                "ORP_MAINTENANCE_SKIP_LAUNCHCTL": "1",
                "ORP_UPDATE_LATEST_VERSION": PACKAGE_VERSION,
            }

            enable_proc = self.run_cli("maintenance", "enable", "--hour", "9", "--minute", "5", "--json", env=env)
            self.assertEqual(enable_proc.returncode, 0, msg=enable_proc.stderr + "\n" + enable_proc.stdout)
            enable_payload = json.loads(enable_proc.stdout)
            plist_path = Path(enable_payload["plist_path"])
            with plist_path.open("rb") as handle:
                plist_payload = plistlib.load(handle)

            child_env = os.environ.copy()
            child_env.update(plist_payload["EnvironmentVariables"])
            run_proc = subprocess.run(
                plist_payload["ProgramArguments"],
                capture_output=True,
                text=True,
                cwd=plist_payload["WorkingDirectory"],
                env=child_env,
            )
            self.assertEqual(run_proc.returncode, 0, msg=run_proc.stderr + "\n" + run_proc.stdout)
            payload = json.loads(run_proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["update"]["status"], "up_to_date")
            self.assertTrue(state_path.exists())


if __name__ == "__main__":
    unittest.main()
