from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_link_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_cli(root: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
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
        env=merged_env,
    )


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=str(root),
    )


def _git_init_main(root: Path) -> None:
    proc = _run_git(root, "init", "-b", "main")
    if proc.returncode == 0:
        return
    proc = _run_git(root, "init")
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + "\n" + proc.stdout)
    proc = _run_git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + "\n" + proc.stdout)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class OrpLinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_xdg = os.environ.get("XDG_CONFIG_HOME")
        self.addCleanup(self._restore_xdg)

    def _restore_xdg(self) -> None:
        if self._old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self._old_xdg

    def _prepare_hosted_session(self, module, td: str) -> None:
        os.environ["XDG_CONFIG_HOME"] = td
        module._save_hosted_session(
            {
                "base_url": "https://orp.earth",
                "email": "cody@example.com",
                "token": "tok_live_123",
                "user": {"id": "user_123", "email": "cody@example.com", "name": "Cody"},
                "pending_verification": None,
            }
        )

    def test_link_project_bind_writes_local_project_record(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            return {
                "ok": True,
                "world": {
                    "id": "world_123",
                    "name": "Demo World",
                    "projectRoot": str(body["projectRoot"]),
                    "githubUrl": "https://github.com/example/demo.git",
                    "codexSessionId": "codex_primary_123",
                    "status": "active",
                },
            }

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_link_project_bind(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        idea_id="idea_123",
                        idea_title="Demo Idea",
                        name="",
                        project_root="",
                        github_url="",
                        codex_session_id="codex_primary_123",
                        notes="Imported from test",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["project_link"]["idea_id"], "idea_123")
            self.assertEqual(payload["project_link"]["idea_title"], "Demo Idea")
            self.assertEqual(payload["project_link"]["world_id"], "world_123")
            self.assertEqual(payload["project_link"]["world_name"], "Demo World")
            self.assertEqual(payload["project_link"]["project_root"], str(root.resolve()))
            self.assertEqual(payload["project_link"]["source"], "cli")
            self.assertEqual(payload["project_link"]["linked_email"], "cody@example.com")
            self.assertEqual(payload["project_link_path"], ".git/orp/link/project.json")
            self.assertEqual(calls[0][0], "PUT")
            self.assertEqual(calls[0][1], "/api/cli/ideas/idea_123/world")

            saved = json.loads((root / ".git" / "orp" / "link" / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["idea_id"], "idea_123")
            self.assertEqual(saved["world_id"], "world_123")
            self.assertEqual(saved["notes"], "Imported from test")

    def test_link_session_register_archive_remove_and_primary_rebalance(self) -> None:
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            env = {"XDG_CONFIG_HOME": config_td}

            register_primary = _run_cli(
                root,
                "link",
                "session",
                "register",
                "--orp-session-id",
                "session-1",
                "--label",
                "Planner",
                "--codex-session-id",
                "codex-1",
                "--primary",
                "--json",
                env=env,
            )
            self.assertEqual(register_primary.returncode, 0, msg=register_primary.stderr + "\n" + register_primary.stdout)
            first_payload = json.loads(register_primary.stdout)
            self.assertTrue(first_payload["session"]["primary"])

            register_second = _run_cli(
                root,
                "link",
                "session",
                "register",
                "--orp-session-id",
                "session-2",
                "--label",
                "Reviewer",
                "--codex-session-id",
                "codex-2",
                "--json",
                env=env,
            )
            self.assertEqual(register_second.returncode, 0, msg=register_second.stderr + "\n" + register_second.stdout)

            set_primary = _run_cli(root, "link", "session", "set-primary", "session-2", "--json", env=env)
            self.assertEqual(set_primary.returncode, 0, msg=set_primary.stderr + "\n" + set_primary.stdout)
            set_primary_payload = json.loads(set_primary.stdout)
            self.assertEqual(set_primary_payload["primary_session"]["orp_session_id"], "session-2")

            archive_primary = _run_cli(root, "link", "session", "archive", "session-2", "--json", env=env)
            self.assertEqual(archive_primary.returncode, 0, msg=archive_primary.stderr + "\n" + archive_primary.stdout)
            archive_payload = json.loads(archive_primary.stdout)
            self.assertTrue(archive_payload["session"]["archived"])
            self.assertEqual(archive_payload["primary_session"]["orp_session_id"], "session-1")

            remove_first = _run_cli(root, "link", "session", "remove", "session-1", "--json", env=env)
            self.assertEqual(remove_first.returncode, 0, msg=remove_first.stderr + "\n" + remove_first.stdout)
            remove_payload = json.loads(remove_first.stdout)
            self.assertTrue(remove_payload["removed"])
            self.assertEqual(remove_payload["session_counts"]["total"], 1)
            self.assertEqual(remove_payload["session_counts"]["archived"], 1)
            self.assertEqual(remove_payload["primary_session"], {})

            listed = _run_cli(root, "link", "session", "list", "--json", env=env)
            self.assertEqual(listed.returncode, 0, msg=listed.stderr + "\n" + listed.stdout)
            listed_payload = json.loads(listed.stdout)
            self.assertEqual(listed_payload["session_counts"]["total"], 1)
            self.assertEqual(listed_payload["sessions"][0]["orp_session_id"], "session-2")
            self.assertTrue(listed_payload["sessions"][0]["archived"])

    def test_link_session_import_rust_imports_project_and_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            env = {"XDG_CONFIG_HOME": config_td}

            _write_json(
                root / ".orp" / "project.json",
                {
                    "project_id": "00000000-0000-0000-0000-000000000001",
                    "project_name": "demo-project",
                    "project_path": str(root),
                    "created_at": "2026-03-15T01:00:00Z",
                    "last_opened_at": "2026-03-15T02:00:00Z",
                    "created_with_orp": True,
                    "github_remote": "https://github.com/example/demo.git",
                    "last_seen_commit": None,
                    "hosted_link": {
                        "idea_id": "idea_123",
                        "idea_title": "Idea Demo",
                        "world_id": "world_123",
                        "world_name": "World Demo",
                        "linked_at": "2026-03-15T02:05:00Z",
                        "linked_email": "cody@example.com",
                    },
                    "archived_codex_session_ids": [],
                    "ignored_codex_session_ids": ["codex-ignored"],
                    "archived_session_ids": ["session-2"],
                    "session_order": ["session-1", "session-2"],
                },
            )
            _write_json(
                root / ".orp" / "sessions" / "session-1.json",
                {
                    "session_id": "session-1",
                    "label": "Main Session",
                    "created_at": "2026-03-15T02:10:00Z",
                    "last_active_at": "2026-03-15T02:20:00Z",
                    "project_path": str(root),
                    "codex_session_id": "codex-1",
                    "terminal_target": {"window_id": 7, "tab_number": 3},
                    "state": "active",
                },
            )
            _write_json(
                root / ".orp" / "sessions" / "session-2.json",
                {
                    "session_id": "session-2",
                    "label": "Archived Session",
                    "created_at": "2026-03-15T02:11:00Z",
                    "last_active_at": "2026-03-15T02:12:00Z",
                    "project_path": str(root),
                    "codex_session_id": "codex-2",
                    "state": "closed",
                },
            )

            proc = _run_cli(root, "link", "session", "import-rust", "--json", env=env)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["imported_project"])
            self.assertEqual(payload["project_link"]["idea_id"], "idea_123")
            self.assertEqual(payload["project_link"]["world_id"], "world_123")
            self.assertEqual(payload["project_link"]["source"], "import-rust")
            self.assertEqual(payload["imported_session_count"], 2)
            self.assertEqual(payload["primary_session"]["orp_session_id"], "session-1")
            self.assertEqual(payload["ignored_codex_session_ids"], ["codex-ignored"])

            sessions = _run_cli(root, "link", "session", "list", "--json", env=env)
            self.assertEqual(sessions.returncode, 0, msg=sessions.stderr + "\n" + sessions.stdout)
            session_payload = json.loads(sessions.stdout)
            by_id = {row["orp_session_id"]: row for row in session_payload["sessions"]}
            self.assertTrue(by_id["session-1"]["primary"])
            self.assertEqual(by_id["session-1"]["terminal_target"]["window_id"], 7)
            self.assertTrue(by_id["session-2"]["archived"])
            self.assertFalse(by_id["session-2"]["primary"])

    def test_link_import_rust_all_alias_imports_full_rust_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            env = {"XDG_CONFIG_HOME": config_td}

            _write_json(
                root / ".orp" / "project.json",
                {
                    "project_id": "00000000-0000-0000-0000-000000000002",
                    "project_name": "demo-project",
                    "project_path": str(root),
                    "created_at": "2026-03-15T01:00:00Z",
                    "last_opened_at": "2026-03-15T02:00:00Z",
                    "created_with_orp": True,
                    "hosted_link": {
                        "idea_id": "idea_alias",
                        "idea_title": "Alias Import",
                        "world_id": "world_alias",
                        "world_name": "Alias World",
                        "linked_at": "2026-03-15T02:05:00Z",
                        "linked_email": "cody@example.com",
                    },
                    "archived_codex_session_ids": [],
                    "ignored_codex_session_ids": [],
                    "archived_session_ids": [],
                    "session_order": ["session-a"],
                },
            )
            _write_json(
                root / ".orp" / "sessions" / "session-a.json",
                {
                    "session_id": "session-a",
                    "label": "Alias Session",
                    "created_at": "2026-03-15T02:10:00Z",
                    "last_active_at": "2026-03-15T02:20:00Z",
                    "project_path": str(root),
                    "codex_session_id": "codex-a",
                    "state": "active",
                },
            )

            missing_flag = _run_cli(root, "link", "import-rust", "--json", env=env)
            self.assertNotEqual(missing_flag.returncode, 0, msg=missing_flag.stderr + "\n" + missing_flag.stdout)
            self.assertIn("requires `--all`", missing_flag.stderr)

            proc = _run_cli(root, "link", "import-rust", "--all", "--json", env=env)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["imported_project"])
            self.assertEqual(payload["project_link"]["idea_id"], "idea_alias")
            self.assertEqual(payload["project_link"]["world_id"], "world_alias")
            self.assertEqual(payload["imported_session_count"], 1)
            self.assertEqual(payload["primary_session"]["orp_session_id"], "session-a")

    def test_link_status_and_doctor_report_missing_auth_and_session_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            env = {"XDG_CONFIG_HOME": config_td}

            _write_json(
                root / ".orp" / "project.json",
                {
                    "project_id": "00000000-0000-0000-0000-000000000001",
                    "project_name": "demo-project",
                    "project_path": str(root),
                    "created_at": "2026-03-15T01:00:00Z",
                    "last_opened_at": "2026-03-15T02:00:00Z",
                    "created_with_orp": True,
                    "github_remote": "https://github.com/example/demo.git",
                    "last_seen_commit": None,
                    "hosted_link": {
                        "idea_id": "idea_987",
                        "idea_title": "Idea Demo",
                        "world_id": "world_987",
                        "world_name": "World Demo",
                        "linked_at": "2026-03-15T02:05:00Z",
                        "linked_email": "cody@example.com",
                    },
                    "archived_codex_session_ids": [],
                    "ignored_codex_session_ids": [],
                    "archived_session_ids": [],
                    "session_order": ["session-1"],
                },
            )
            _write_json(
                root / ".orp" / "sessions" / "session-1.json",
                {
                    "session_id": "session-1",
                    "label": "Main Session",
                    "created_at": "2026-03-15T02:10:00Z",
                    "last_active_at": "2026-03-15T02:20:00Z",
                    "project_path": str(root),
                    "codex_session_id": "",
                    "state": "active",
                },
            )
            import_proc = _run_cli(root, "link", "session", "import-rust", "--json", env=env)
            self.assertEqual(import_proc.returncode, 0, msg=import_proc.stderr + "\n" + import_proc.stdout)

            status_proc = _run_cli(root, "link", "status", "--json", env=env)
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            status_payload = json.loads(status_proc.stdout)
            self.assertTrue(status_payload["project_link_exists"])
            self.assertEqual(status_payload["session_counts"]["total"], 1)
            self.assertFalse(status_payload["routing_ready"])
            self.assertTrue(any("hosted auth is not connected" in row for row in status_payload["warnings"]))

            doctor_proc = _run_cli(root, "link", "doctor", "--json", env=env)
            self.assertEqual(doctor_proc.returncode, 0, msg=doctor_proc.stderr + "\n" + doctor_proc.stdout)
            doctor_payload = json.loads(doctor_proc.stdout)
            codes = {row["code"] for row in doctor_payload["issues"]}
            self.assertIn("missing_hosted_auth", codes)
            self.assertIn("missing_codex_session_id", codes)

            strict_proc = _run_cli(root, "link", "doctor", "--strict", "--json", env=env)
            self.assertEqual(strict_proc.returncode, 1, msg=strict_proc.stderr + "\n" + strict_proc.stdout)


if __name__ == "__main__":
    unittest.main()
