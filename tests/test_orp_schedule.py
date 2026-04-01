from __future__ import annotations

import json
import os
from pathlib import Path
import plistlib
import stat
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


class OrpScheduleTests(unittest.TestCase):
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

    def _schedule_env(self, td: str) -> dict[str, str]:
        return {
            "ORP_SCHEDULE_REGISTRY_PATH": str(Path(td) / "schedules.json"),
            "ORP_SCHEDULE_LAUNCH_AGENTS_DIR": str(Path(td) / "LaunchAgents"),
            "ORP_SCHEDULE_LOGS_DIR": str(Path(td) / "schedule-logs"),
            "ORP_LAUNCH_RUNTIME_ROOT": str(Path(td) / "launch-runtime"),
            "ORP_SCHEDULE_ALLOW_NON_DARWIN": "1",
            "ORP_SCHEDULE_SKIP_LAUNCHCTL": "1",
        }

    def _write_fake_codex(self, root: Path) -> Path:
        script = root / "fake-codex.sh"
        script.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    'OUT=""',
                    'EXPECT_OUT=0',
                    'for arg in "$@"; do',
                    '  if [ "$EXPECT_OUT" = "1" ]; then',
                    '    OUT="$arg"',
                    '    EXPECT_OUT=0',
                    "    continue",
                    "  fi",
                    '  if [ "$arg" = "--output-last-message" ]; then',
                    '    EXPECT_OUT=1',
                    "  fi",
                    "done",
                    "cat >/dev/null",
                    'if [ -n "$OUT" ]; then',
                    '  printf "Scheduled summary from fake codex.\\n" > "$OUT"',
                    "fi",
                    'printf "fake codex stdout\\n"',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def test_schedule_add_and_list_codex_job(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "repo"
            repo_root.mkdir()
            env = self._schedule_env(td)
            add_proc = self.run_cli(
                "schedule",
                "add",
                "codex",
                "--name",
                "morning-summary",
                "--repo-root",
                str(repo_root),
                "--prompt",
                "Summarize the repo status.",
                "--hour",
                "8",
                "--minute",
                "30",
                "--json",
                env=env,
            )
            self.assertEqual(add_proc.returncode, 0, msg=add_proc.stderr + "\n" + add_proc.stdout)
            add_payload = json.loads(add_proc.stdout)
            self.assertEqual(add_payload["name"], "morning-summary")
            self.assertEqual(add_payload["kind"], "codex")
            self.assertEqual(add_payload["repo_root"], str(repo_root.resolve()))
            self.assertEqual(add_payload["schedule"]["hour"], 8)
            self.assertEqual(add_payload["schedule"]["minute"], 30)
            self.assertFalse(add_payload["enabled"])
            self.assertEqual(add_payload["codex_session_id"], "")

            list_proc = self.run_cli("schedule", "list", "--json", env=env)
            self.assertEqual(list_proc.returncode, 0, msg=list_proc.stderr + "\n" + list_proc.stdout)
            list_payload = json.loads(list_proc.stdout)
            self.assertEqual(len(list_payload["jobs"]), 1)
            self.assertEqual(list_payload["jobs"][0]["name"], "morning-summary")
            self.assertFalse(list_payload["jobs"][0]["enabled"])
            self.assertEqual(list_payload["jobs"][0]["prompt_source"], "inline")

    def test_schedule_show_returns_prompt_repo_and_session_details(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "repo"
            repo_root.mkdir()
            env = self._schedule_env(td)
            add_proc = self.run_cli(
                "schedule",
                "add",
                "codex",
                "--name",
                "session-summary",
                "--repo-root",
                str(repo_root),
                "--prompt",
                "Summarize this named session.",
                "--codex-session-id",
                "sess_12345",
                "--json",
                env=env,
            )
            self.assertEqual(add_proc.returncode, 0, msg=add_proc.stderr + "\n" + add_proc.stdout)

            show_proc = self.run_cli("schedule", "show", "session-summary", "--json", env=env)
            self.assertEqual(show_proc.returncode, 0, msg=show_proc.stderr + "\n" + show_proc.stdout)
            show_payload = json.loads(show_proc.stdout)
            self.assertEqual(show_payload["name"], "session-summary")
            self.assertEqual(show_payload["repo_root"], str(repo_root.resolve()))
            self.assertEqual(show_payload["codex_session_id"], "sess_12345")
            self.assertTrue(show_payload["uses_session_resume"])
            self.assertEqual(show_payload["resolved_prompt"], "Summarize this named session.")
            self.assertEqual(show_payload["prompt_error"], "")

    def test_schedule_run_executes_codex_job_and_records_last_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "repo"
            repo_root.mkdir()
            fake_codex = self._write_fake_codex(Path(td))
            env = self._schedule_env(td)

            add_proc = self.run_cli(
                "schedule",
                "add",
                "codex",
                "--name",
                "nightly-summary",
                "--repo-root",
                str(repo_root),
                "--prompt",
                "Summarize what changed today.",
                "--codex-bin",
                str(fake_codex),
                "--json",
                env=env,
            )
            self.assertEqual(add_proc.returncode, 0, msg=add_proc.stderr + "\n" + add_proc.stdout)

            run_proc = self.run_cli("schedule", "run", "nightly-summary", "--json", env=env)
            self.assertEqual(run_proc.returncode, 0, msg=run_proc.stderr + "\n" + run_proc.stdout)
            run_payload = json.loads(run_proc.stdout)
            self.assertTrue(run_payload["ok"])
            self.assertEqual(run_payload["job"]["name"], "nightly-summary")
            self.assertEqual(run_payload["run"]["summary"], "Scheduled summary from fake codex.")
            self.assertFalse(run_payload["run"]["uses_session_resume"])

            registry = json.loads((Path(td) / "schedules.json").read_text(encoding="utf-8"))
            last_run = registry["jobs"][0]["last_run"]
            self.assertTrue(last_run["ok"])
            self.assertEqual(last_run["summary"], "Scheduled summary from fake codex.")

    def test_schedule_run_can_resume_specific_codex_session(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "repo"
            repo_root.mkdir()
            fake_codex = self._write_fake_codex(Path(td))
            env = self._schedule_env(td)

            add_proc = self.run_cli(
                "schedule",
                "add",
                "codex",
                "--name",
                "resume-summary",
                "--repo-root",
                str(repo_root),
                "--prompt",
                "Continue the saved session.",
                "--codex-session-id",
                "session-resume-123",
                "--codex-bin",
                str(fake_codex),
                "--json",
                env=env,
            )
            self.assertEqual(add_proc.returncode, 0, msg=add_proc.stderr + "\n" + add_proc.stdout)

            run_proc = self.run_cli("schedule", "run", "resume-summary", "--json", env=env)
            self.assertEqual(run_proc.returncode, 0, msg=run_proc.stderr + "\n" + run_proc.stdout)
            run_payload = json.loads(run_proc.stdout)
            self.assertTrue(run_payload["ok"])
            self.assertTrue(run_payload["run"]["uses_session_resume"])
            self.assertEqual(run_payload["run"]["codex_session_id"], "session-resume-123")
            self.assertIn("exec resume", run_payload["run"]["command"])
            self.assertIn("session-resume-123", run_payload["run"]["command"])

    def test_schedule_enable_and_disable_manage_launch_agent_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "repo"
            repo_root.mkdir()
            env = self._schedule_env(td)

            add_proc = self.run_cli(
                "schedule",
                "add",
                "codex",
                "--name",
                "daily-codex",
                "--repo-root",
                str(repo_root),
                "--prompt",
                "Summarize the repo.",
                "--hour",
                "7",
                "--minute",
                "45",
                "--json",
                env=env,
            )
            self.assertEqual(add_proc.returncode, 0, msg=add_proc.stderr + "\n" + add_proc.stdout)

            enable_proc = self.run_cli("schedule", "enable", "daily-codex", "--json", env=env)
            self.assertEqual(enable_proc.returncode, 0, msg=enable_proc.stderr + "\n" + enable_proc.stdout)
            enable_payload = json.loads(enable_proc.stdout)
            self.assertTrue(enable_payload["ok"])
            plist_path = Path(enable_payload["job"]["plist_path"])
            self.assertTrue(plist_path.exists())
            with plist_path.open("rb") as handle:
                plist_payload = plistlib.load(handle)
            self.assertEqual(plist_payload["StartCalendarInterval"]["Hour"], 7)
            self.assertEqual(plist_payload["StartCalendarInterval"]["Minute"], 45)
            self.assertFalse(plist_payload["RunAtLoad"])
            self.assertEqual(plist_payload["ProgramArguments"][0], sys.executable)
            self.assertIn(str(Path(td) / "launch-runtime"), plist_payload["ProgramArguments"][1])
            self.assertTrue(Path(plist_payload["ProgramArguments"][1]).exists())
            self.assertEqual(plist_payload["WorkingDirectory"], str((Path(td) / "launch-runtime").resolve()))

            list_proc = self.run_cli("schedule", "list", "--json", env=env)
            self.assertEqual(list_proc.returncode, 0, msg=list_proc.stderr + "\n" + list_proc.stdout)
            list_payload = json.loads(list_proc.stdout)
            self.assertTrue(list_payload["jobs"][0]["enabled"])

            disable_proc = self.run_cli("schedule", "disable", "daily-codex", "--json", env=env)
            self.assertEqual(disable_proc.returncode, 0, msg=disable_proc.stderr + "\n" + disable_proc.stdout)
            disable_payload = json.loads(disable_proc.stdout)
            self.assertTrue(disable_payload["ok"])
            self.assertFalse(plist_path.exists())

    def test_schedule_launch_program_arguments_run_from_snapshot_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo_root = Path(td) / "repo"
            repo_root.mkdir()
            fake_codex = self._write_fake_codex(Path(td))
            env = self._schedule_env(td)

            add_proc = self.run_cli(
                "schedule",
                "add",
                "codex",
                "--name",
                "snapshot-codex",
                "--repo-root",
                str(repo_root),
                "--prompt",
                "Summarize the repo from launchd.",
                "--codex-bin",
                str(fake_codex),
                "--json",
                env=env,
            )
            self.assertEqual(add_proc.returncode, 0, msg=add_proc.stderr + "\n" + add_proc.stdout)

            enable_proc = self.run_cli("schedule", "enable", "snapshot-codex", "--json", env=env)
            self.assertEqual(enable_proc.returncode, 0, msg=enable_proc.stderr + "\n" + enable_proc.stdout)
            enable_payload = json.loads(enable_proc.stdout)
            plist_path = Path(enable_payload["job"]["plist_path"])
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
            self.assertEqual(payload["job"]["name"], "snapshot-codex")
            self.assertEqual(payload["run"]["summary"], "Scheduled summary from fake codex.")


if __name__ == "__main__":
    unittest.main()
