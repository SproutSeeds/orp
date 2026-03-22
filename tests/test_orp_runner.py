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
    spec = importlib.util.spec_from_file_location("orp_cli_runner_test", CLI)
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


class OrpRunnerTests(unittest.TestCase):
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

    def test_runner_enable_and_disable_persist_machine_state(self) -> None:
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            env = {"XDG_CONFIG_HOME": config_td}

            enable = _run_cli(root, "runner", "enable", "--json", env=env)
            self.assertEqual(enable.returncode, 0, msg=enable.stderr + "\n" + enable.stdout)
            enable_payload = json.loads(enable.stdout)
            self.assertTrue(enable_payload["machine"]["runner_enabled"])
            self.assertEqual(enable_payload["repo_runner_path"], ".git/orp/link/runner.json")

            machine_path = Path(enable_payload["machine_path"])
            self.assertTrue(machine_path.exists())
            repo_runner_path = root / ".git" / "orp" / "link" / "runner.json"
            self.assertTrue(repo_runner_path.exists())
            saved_machine = json.loads(machine_path.read_text(encoding="utf-8"))
            self.assertTrue(saved_machine["runner_enabled"])

            disable = _run_cli(root, "runner", "disable", "--json", env=env)
            self.assertEqual(disable.returncode, 0, msg=disable.stderr + "\n" + disable.stdout)
            disable_payload = json.loads(disable.stdout)
            self.assertFalse(disable_payload["machine"]["runner_enabled"])
            saved_machine = json.loads(machine_path.read_text(encoding="utf-8"))
            self.assertFalse(saved_machine["runner_enabled"])
            saved_repo_runner = json.loads(repo_runner_path.read_text(encoding="utf-8"))
            self.assertFalse(saved_repo_runner["runner_enabled"])

    def test_runner_heartbeat_posts_and_persists_timestamp(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(path, "/api/cli/runner/heartbeat")
            self.assertEqual(method, "POST")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            return {"ok": True}

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)
            module._save_runner_machine({"runner_enabled": True})
            module._write_runner_repo_state(root, module._load_runner_machine())

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_heartbeat(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertIn("heartbeat_at_utc", payload)
            self.assertEqual(payload["repo_runner_path"], ".git/orp/link/runner.json")
            self.assertEqual(calls[0][2]["machineId"], payload["machine"]["machine_id"])
            self.assertEqual(calls[0][2]["machineName"], payload["machine"]["machine_name"])

            machine = module._load_runner_machine()
            self.assertEqual(machine["last_heartbeat_at_utc"], payload["heartbeat_at_utc"])
            repo_runner = json.loads((root / ".git" / "orp" / "link" / "runner.json").read_text(encoding="utf-8"))
            self.assertEqual(repo_runner["last_heartbeat_at_utc"], payload["heartbeat_at_utc"])

    def test_runner_status_reports_routeable_sessions_and_missing_auth(self) -> None:
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
                    "codex_session_id": "codex-1",
                    "state": "active",
                },
            )
            import_proc = _run_cli(root, "link", "session", "import-rust", "--json", env=env)
            self.assertEqual(import_proc.returncode, 0, msg=import_proc.stderr + "\n" + import_proc.stdout)
            enable_proc = _run_cli(root, "runner", "enable", "--json", env=env)
            self.assertEqual(enable_proc.returncode, 0, msg=enable_proc.stderr + "\n" + enable_proc.stdout)

            status_proc = _run_cli(root, "runner", "status", "--json", env=env)
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            payload = json.loads(status_proc.stdout)
            self.assertTrue(payload["machine"]["runner_enabled"])
            self.assertEqual(payload["session_counts"]["routeable"], 1)
            self.assertFalse(payload["sync_ready"])
            self.assertFalse(payload["work_ready"])
            self.assertTrue(any("hosted auth is not connected" in row for row in payload["warnings"]))

    def test_runner_status_reports_stale_active_lease(self) -> None:
        module = load_cli_module()

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)
            module._save_runner_machine(
                {
                    "runner_enabled": True,
                    "last_heartbeat_at_utc": "2026-03-16T00:00:00Z",
                }
            )
            module._write_runner_repo_state(root, module._load_runner_machine())
            module._write_runner_runtime(
                root,
                {
                    "status": "running",
                    "active_job": {
                        "job_id": "job_live",
                        "job_kind": "session.prompt",
                        "lease_id": "lease_live",
                        "project_root": str(root),
                        "repo_root": str(root),
                        "status": "running",
                        "started_at_utc": "2026-03-16T00:00:00Z",
                        "last_heartbeat_at_utc": "2026-03-16T00:00:00Z",
                    },
                },
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_status(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["repo_runtime"]["active_job"]["job_id"], "job_live")
            self.assertTrue(payload["active_lease"]["has_active_job"])
            self.assertTrue(payload["active_lease"]["stale"])
            self.assertTrue(any("lease appears stale" in row for row in payload["warnings"]))
            self.assertEqual(payload["repo_runtime_path"], ".git/orp/link/runtime.json")

    def test_runner_cancel_and_retry_use_runtime_job_context(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            self.assertEqual(method, "POST")
            calls.append((method, path, body))
            return {"ok": True}

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)
            module._save_runner_machine({"runner_enabled": True})
            module._write_runner_repo_state(root, module._load_runner_machine())
            module._write_runner_runtime(
                root,
                {
                    "status": "running",
                    "active_job": {
                        "job_id": "job_active",
                        "job_kind": "session.prompt",
                        "lease_id": "lease_active",
                        "idea_id": "idea_123",
                        "project_root": str(root),
                        "repo_root": str(root),
                        "status": "running",
                        "claimed_at_utc": "2026-03-16T02:00:00Z",
                        "started_at_utc": "2026-03-16T02:01:00Z",
                        "last_heartbeat_at_utc": "2026-03-16T02:02:00Z",
                    },
                    "last_job": {
                        "job_id": "job_old",
                        "job_kind": "session.prompt",
                        "lease_id": "lease_old",
                        "status": "failed",
                        "finished_at_utc": "2026-03-16T01:00:00Z",
                    },
                },
            )

            cancel_buf = io.StringIO()
            with redirect_stdout(cancel_buf):
                cancel_result = module.cmd_runner_cancel(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                        job_id="",
                        lease_id="",
                        reason="manual stop",
                        linked_project_roots=[],
                    )
                )
            self.assertEqual(cancel_result, 0)
            cancel_payload = json.loads(cancel_buf.getvalue())
            self.assertEqual(cancel_payload["job_id"], "job_active")
            self.assertEqual(cancel_payload["lease_id"], "lease_active")
            self.assertEqual(cancel_payload["runtime"]["status"], "idle")
            self.assertEqual(cancel_payload["runtime"]["last_job"]["status"], "cancelled")
            self.assertEqual(cancel_payload["runtime"]["active_job"], {})

            retry_buf = io.StringIO()
            with redirect_stdout(retry_buf):
                retry_result = module.cmd_runner_retry(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                        job_id="",
                        lease_id="",
                        reason="retry after fix",
                        linked_project_roots=[],
                    )
                )
            self.assertEqual(retry_result, 0)
            retry_payload = json.loads(retry_buf.getvalue())
            self.assertEqual(retry_payload["job_id"], "job_active")
            self.assertEqual(retry_payload["runtime"]["last_job"]["status"], "retried")
            self.assertEqual(calls[0][1], "/api/cli/runner/jobs/job_active/cancel")
            self.assertEqual(calls[0][2]["leaseId"], "lease_active")
            self.assertEqual(calls[1][1], "/api/cli/runner/jobs/job_active/retry")
            self.assertEqual(calls[1][2]["leaseId"], "lease_active")

    def test_runner_sync_posts_rust_compatible_payload(self) -> None:
        module = load_cli_module()
        captured: dict[str, object] = {}

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(path, "/api/cli/runner/sync")
            self.assertEqual(method, "POST")
            self.assertEqual(token, "tok_live_123")
            captured["body"] = body
            return {"ok": True}

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)

            module._write_link_project(
                root,
                {
                    "idea_id": "idea_123",
                    "idea_title": "Idea Demo",
                    "world_id": "world_123",
                    "world_name": "World Demo",
                    "project_root": str(root),
                    "github_url": "https://github.com/example/demo.git",
                    "linked_at_utc": "2026-03-15T02:05:00Z",
                    "linked_email": "cody@example.com",
                    "source": "cli",
                },
            )
            module._write_link_session(
                root,
                {
                    "orp_session_id": "session-1",
                    "label": "Main Session",
                    "state": "active",
                    "project_root": str(root),
                    "codex_session_id": "codex-1",
                    "created_at_utc": "2026-03-15T02:10:00Z",
                    "last_active_at_utc": "2026-03-15T02:20:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )
            module._write_link_session(
                root,
                {
                    "orp_session_id": "session-2",
                    "label": "Archived Session",
                    "state": "closed",
                    "project_root": str(root),
                    "codex_session_id": "codex-2",
                    "created_at_utc": "2026-03-15T02:11:00Z",
                    "last_active_at_utc": "2026-03-15T02:12:00Z",
                    "archived": True,
                    "primary": False,
                    "source": "cli",
                },
            )
            module._save_runner_machine({"runner_enabled": True})
            module._write_runner_repo_state(root, module._load_runner_machine())

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_sync(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["linked_projects"], 1)
            self.assertEqual(payload["sessions"], 1)
            self.assertEqual(payload["routeable_sessions"], 1)

            body = captured["body"]
            assert isinstance(body, dict)
            self.assertIn("machineId", body)
            self.assertIn("machineName", body)
            self.assertEqual(body["platform"], module._runner_platform_name())
            self.assertEqual(body["appVersion"], module.ORP_TOOL_VERSION)
            self.assertEqual(len(body["linkedProjects"]), 1)
            self.assertEqual(body["linkedProjects"][0]["ideaId"], "idea_123")
            self.assertEqual(body["linkedProjects"][0]["worldId"], "world_123")
            self.assertEqual(body["linkedProjects"][0]["projectName"], root.name)
            self.assertEqual(len(body["sessions"]), 1)
            self.assertEqual(body["sessions"][0]["orpSessionId"], "session-1")
            self.assertEqual(body["sessions"][0]["codexSessionId"], "codex-1")
            self.assertTrue(body["sessions"][0]["primary"])

            machine = module._load_runner_machine()
            self.assertTrue(machine["runner_enabled"])
            self.assertEqual(machine["linked_email"], "cody@example.com")
            self.assertIn("last_sync_at_utc", machine)
            self.assertTrue((root / ".git" / "orp" / "link" / "runner.json").exists())

    def test_runner_sync_can_include_multiple_linked_project_roots(self) -> None:
        module = load_cli_module()
        captured: dict[str, object] = {}

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(path, "/api/cli/runner/sync")
            self.assertEqual(method, "POST")
            self.assertEqual(token, "tok_live_123")
            captured["body"] = body
            return {"ok": True}

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td) / "primary"
            other_root = Path(td) / "secondary"
            skipped_root = Path(td) / "unlinked"
            root.mkdir(parents=True, exist_ok=True)
            other_root.mkdir(parents=True, exist_ok=True)
            skipped_root.mkdir(parents=True, exist_ok=True)
            resolved_root = str(root.resolve())
            resolved_other_root = str(other_root.resolve())
            resolved_skipped_root = str(skipped_root.resolve())
            _git_init_main(root)
            _git_init_main(other_root)
            _git_init_main(skipped_root)
            self._prepare_hosted_session(module, config_td)

            module._write_link_project(
                root,
                {
                    "idea_id": "idea_primary",
                    "idea_title": "Primary Idea",
                    "world_id": "world_primary",
                    "world_name": "Primary World",
                    "project_root": str(root),
                    "github_url": "https://github.com/example/primary.git",
                    "linked_at_utc": "2026-03-15T02:05:00Z",
                    "linked_email": "cody@example.com",
                    "source": "cli",
                },
            )
            module._write_link_session(
                root,
                {
                    "orp_session_id": "session-primary",
                    "label": "Primary Session",
                    "state": "active",
                    "project_root": str(root),
                    "codex_session_id": "codex-primary",
                    "created_at_utc": "2026-03-15T02:10:00Z",
                    "last_active_at_utc": "2026-03-15T02:20:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )

            module._write_link_project(
                other_root,
                {
                    "idea_id": "idea_secondary",
                    "idea_title": "Secondary Idea",
                    "world_id": "world_secondary",
                    "world_name": "Secondary World",
                    "project_root": str(other_root),
                    "github_url": "https://github.com/example/secondary.git",
                    "linked_at_utc": "2026-03-15T03:05:00Z",
                    "linked_email": "cody@example.com",
                    "source": "cli",
                },
            )
            module._write_link_session(
                other_root,
                {
                    "orp_session_id": "session-secondary",
                    "label": "Secondary Session",
                    "state": "active",
                    "project_root": str(other_root),
                    "codex_session_id": "codex-secondary",
                    "created_at_utc": "2026-03-15T03:10:00Z",
                    "last_active_at_utc": "2026-03-15T03:20:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )

            module._save_runner_machine({"runner_enabled": True})
            module._write_runner_repo_state(root, module._load_runner_machine())

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_sync(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                        linked_project_roots=[str(other_root), str(skipped_root)],
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["linked_projects"], 2)
            self.assertEqual(payload["sessions"], 2)
            self.assertEqual(payload["routeable_sessions"], 2)
            self.assertEqual(payload["included_project_roots"], [resolved_root, resolved_other_root])
            self.assertEqual(
                payload["skipped_project_roots"],
                [{"project_root": resolved_skipped_root, "reason": "not_linked"}],
            )

            body = captured["body"]
            assert isinstance(body, dict)
            self.assertEqual(len(body["linkedProjects"]), 2)
            self.assertEqual(
                {row["projectRoot"] for row in body["linkedProjects"]},
                {resolved_root, resolved_other_root},
            )
            self.assertEqual(len(body["sessions"]), 2)
            self.assertEqual(
                {row["orpSessionId"] for row in body["sessions"]},
                {"session-primary", "session-secondary"},
            )
            self.assertTrue(all(row["primary"] for row in body["sessions"]))


if __name__ == "__main__":
    unittest.main()
