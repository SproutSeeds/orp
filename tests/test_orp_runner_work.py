from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from contextlib import redirect_stdout


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_runner_work_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


class OrpRunnerWorkTests(unittest.TestCase):
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

    def _prepare_linked_repo(self, module, root: Path) -> None:
        module._write_link_project(
            root,
            {
                "idea_id": "idea_123",
                "idea_title": "Idea Demo",
                "world_id": "world_123",
                "world_name": "World Demo",
                "project_root": str(root),
                "github_url": "https://github.com/example/demo.git",
                "linked_at_utc": "2026-03-16T01:00:00Z",
                "linked_email": "cody@example.com",
                "source": "cli",
            },
        )
        module._save_runner_machine({"runner_enabled": True})
        module._write_runner_repo_state(root, module._load_runner_machine())

    def test_runner_work_once_processes_prompt_job_and_syncs(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            if path.startswith("/api/cli/runner/jobs/poll"):
                return {
                    "leaseId": "lease_123",
                    "leaseExpiresAt": "2026-03-16T02:00:00Z",
                    "job": {
                        "id": "job_123",
                        "kind": "session.prompt",
                        "ideaId": "idea_123",
                        "payload": {
                            "prompt": "Please review the patch.",
                        },
                    }
                }
            return {"ok": True}

        def fake_run_runner_codex_job(*, job, repo_root, selected_session, args):
            self.assertEqual(job["id"], "job_123")
            self.assertEqual(selected_session["orp_session_id"], "session-primary")
            return {
                "ok": True,
                "exitCode": 0,
                "stdout": "runner stdout\n",
                "stderr": "",
                "body": "Prompt handled successfully.\n",
                "summary": "Prompt handled successfully.",
                "command": "codex exec resume ...",
            }

        module._request_hosted_json = fake_request_hosted_json
        module._run_runner_codex_job = fake_run_runner_codex_job

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)
            self._prepare_linked_repo(module, root)
            module._write_link_session(
                root,
                {
                    "orp_session_id": "session-primary",
                    "label": "Primary Session",
                    "state": "active",
                    "project_root": str(root),
                    "codex_session_id": "codex-primary",
                    "created_at_utc": "2026-03-16T01:10:00Z",
                    "last_active_at_utc": "2026-03-16T01:15:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_work(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                        once=True,
                        dry_run=False,
                        poll_interval=30,
                        codex_bin="",
                        codex_config_profile="",
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["claimed"])
            self.assertEqual(payload["lease"]["lease_id"], "lease_123")
            self.assertEqual(payload["selection"]["source"], "primary_session")
            self.assertEqual(payload["selected_session"]["orp_session_id"], "session-primary")
            self.assertEqual(payload["worker"]["summary"], "Prompt handled successfully.")
            self.assertEqual(payload["sync_result"]["sync_payload"]["linkedProjects"][0]["ideaId"], "idea_123")
            self.assertEqual(payload["sync_result"]["sync_payload"]["sessions"][0]["orpSessionId"], "session-primary")
            self.assertEqual(payload["selected_session"]["last_active_at_utc"], payload["sync_result"]["synced_at_utc"])
            self.assertEqual(payload["runtime"]["status"], "idle")
            self.assertEqual(payload["runtime"]["last_job"]["lease_id"], "lease_123")
            self.assertEqual(payload["runtime"]["last_job"]["status"], "completed")

            paths = [path for _, path, _ in calls]
            self.assertTrue(any(path.startswith("/api/cli/runner/jobs/poll") for path in paths))
            self.assertIn("/api/cli/runner/jobs/job_123/start", paths)
            self.assertIn("/api/cli/runner/jobs/job_123/messages", paths)
            self.assertIn("/api/cli/runner/jobs/job_123/logs", paths)
            self.assertIn("/api/cli/runner/jobs/job_123/complete", paths)
            self.assertIn("/api/cli/runner/sync", paths)
            for method, path, body in calls:
                if path in {
                    "/api/cli/runner/jobs/job_123/start",
                    "/api/cli/runner/jobs/job_123/messages",
                    "/api/cli/runner/jobs/job_123/logs",
                    "/api/cli/runner/jobs/job_123/complete",
                }:
                    self.assertEqual(body["leaseId"], "lease_123")

            runtime_payload = json.loads((root / ".git" / "orp" / "link" / "runtime.json").read_text(encoding="utf-8"))
            self.assertEqual(runtime_payload["last_job"]["job_id"], "job_123")
            self.assertEqual(runtime_payload["last_job"]["lease_id"], "lease_123")
            self.assertEqual(runtime_payload["last_job"]["status"], "completed")
            self.assertEqual(runtime_payload["active_job"], {})

    def test_runner_work_once_processes_checkpoint_job_kind(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            if path.startswith("/api/cli/runner/jobs/poll"):
                return {
                    "leaseId": "lease_checkpoint_123",
                    "leaseExpiresAt": "2026-03-16T02:00:00Z",
                    "job": {
                        "id": "job_checkpoint_123",
                        "kind": "idea.checkpoint",
                        "checkpointId": "checkpoint_123",
                        "ideaId": "idea_123",
                        "payload": {
                            "prompt": "Review this queued checkpoint.",
                            "checkpointId": "checkpoint_123",
                        },
                    },
                }
            return {"ok": True}

        def fake_run_runner_codex_job(*, job, repo_root, selected_session, args):
            self.assertEqual(job["kind"], "idea.checkpoint")
            self.assertEqual(job["checkpointId"], "checkpoint_123")
            self.assertEqual(selected_session["orp_session_id"], "session-primary")
            return {
                "ok": True,
                "exitCode": 0,
                "stdout": "checkpoint stdout\n",
                "stderr": "",
                "body": "Checkpoint handled successfully.\n",
                "summary": "Checkpoint handled successfully.",
                "command": "codex exec resume ...",
            }

        module._request_hosted_json = fake_request_hosted_json
        module._run_runner_codex_job = fake_run_runner_codex_job

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)
            self._prepare_linked_repo(module, root)
            module._write_link_session(
                root,
                {
                    "orp_session_id": "session-primary",
                    "label": "Primary Session",
                    "state": "active",
                    "project_root": str(root),
                    "codex_session_id": "codex-primary",
                    "created_at_utc": "2026-03-16T01:10:00Z",
                    "last_active_at_utc": "2026-03-16T01:15:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_work(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                        once=True,
                        dry_run=False,
                        poll_interval=30,
                        codex_bin="",
                        codex_config_profile="",
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["job"]["kind"], "idea.checkpoint")
            self.assertEqual(payload["job"]["checkpointId"], "checkpoint_123")
            self.assertEqual(payload["runtime"]["last_job"]["job_kind"], "idea.checkpoint")
            self.assertEqual(payload["runtime"]["last_job"]["checkpoint_id"], "checkpoint_123")
            complete_call = next(body for _, path, body in calls if path == "/api/cli/runner/jobs/job_checkpoint_123/complete")
            self.assertEqual(complete_call["leaseId"], "lease_checkpoint_123")
            self.assertEqual(complete_call["summary"], "Checkpoint handled successfully.")

    def test_runner_work_once_prefers_explicit_target_session(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            if path.startswith("/api/cli/runner/jobs/poll"):
                return {
                    "job": {
                        "id": "job_456",
                        "kind": "session.prompt",
                        "ideaId": "idea_123",
                        "payload": {
                            "prompt": "Target the secondary session.",
                            "orpSessionId": "session-secondary",
                        },
                    }
                }
            return {"ok": True}

        module._request_hosted_json = fake_request_hosted_json
        module._run_runner_codex_job = lambda **kwargs: {
            "ok": True,
            "exitCode": 0,
            "stdout": "",
            "stderr": "",
            "body": "done",
            "summary": "done",
            "command": "codex exec resume ...",
        }

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)
            self._prepare_linked_repo(module, root)
            module._write_link_session(
                root,
                {
                    "orp_session_id": "session-primary",
                    "label": "Primary Session",
                    "state": "active",
                    "project_root": str(root),
                    "codex_session_id": "codex-primary",
                    "created_at_utc": "2026-03-16T01:10:00Z",
                    "last_active_at_utc": "2026-03-16T01:15:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )
            module._write_link_session(
                root,
                {
                    "orp_session_id": "session-secondary",
                    "label": "Secondary Session",
                    "state": "active",
                    "project_root": str(root),
                    "codex_session_id": "codex-secondary",
                    "created_at_utc": "2026-03-16T01:11:00Z",
                    "last_active_at_utc": "2026-03-16T01:16:00Z",
                    "archived": False,
                    "primary": False,
                    "source": "cli",
                },
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_work(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                        once=True,
                        dry_run=False,
                        poll_interval=30,
                        codex_bin="",
                        codex_config_profile="",
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["selection"]["source"], "explicit_orp_session_id")
            self.assertEqual(payload["selected_session"]["orp_session_id"], "session-secondary")

    def test_runner_work_once_fails_mismatched_repo_job(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            calls.append((method, path, body))
            if path.startswith("/api/cli/runner/jobs/poll"):
                return {
                    "job": {
                        "id": "job_789",
                        "kind": "session.prompt",
                        "ideaId": "idea_other",
                        "payload": {
                            "prompt": "This is for another repo.",
                        },
                    }
                }
            return {"ok": True}

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)
            self._prepare_linked_repo(module, root)
            module._write_link_session(
                root,
                {
                    "orp_session_id": "session-primary",
                    "label": "Primary Session",
                    "state": "active",
                    "project_root": str(root),
                    "codex_session_id": "codex-primary",
                    "created_at_utc": "2026-03-16T01:10:00Z",
                    "last_active_at_utc": "2026-03-16T01:15:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_work(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                        once=True,
                        dry_run=False,
                        poll_interval=30,
                        codex_bin="",
                        codex_config_profile="",
                    )
                )
            self.assertEqual(result, 1)
            payload = json.loads(buf.getvalue())
            self.assertFalse(payload["ok"])
            self.assertTrue(payload["claimed"])
            self.assertIn("does not target any linked repo on this machine", payload["error"])
            paths = [path for _, path, _ in calls]
            self.assertIn("/api/cli/runner/jobs/job_789/start", paths)
            self.assertIn("/api/cli/runner/jobs/job_789/complete", paths)

    def test_runner_work_falls_back_to_primary_when_targeted_session_is_missing(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            calls.append((method, path, body))
            if path.startswith("/api/cli/runner/jobs/poll"):
                return {
                    "job": {
                        "id": "job_missing_target",
                        "kind": "session.prompt",
                        "ideaId": "idea_123",
                        "payload": {
                            "prompt": "Use the best available session.",
                            "orpSessionId": "session-stale",
                        },
                    }
                }
            return {"ok": True}

        def fake_run_runner_codex_job(*, job, repo_root, selected_session, args):
            self.assertEqual(job["id"], "job_missing_target")
            self.assertEqual(selected_session["orp_session_id"], "session-primary")
            return {
                "ok": True,
                "exitCode": 0,
                "stdout": "",
                "stderr": "",
                "body": "Primary session handled the prompt.\n",
                "summary": "Primary session handled the prompt.",
                "command": "codex exec resume ...",
            }

        module._request_hosted_json = fake_request_hosted_json
        module._run_runner_codex_job = fake_run_runner_codex_job

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)
            self._prepare_linked_repo(module, root)
            module._write_link_session(
                root,
                {
                    "orp_session_id": "session-primary",
                    "label": "Primary Session",
                    "state": "active",
                    "project_root": str(root),
                    "codex_session_id": "codex-primary",
                    "created_at_utc": "2026-03-16T01:10:00Z",
                    "last_active_at_utc": "2026-03-16T01:15:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_work(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                        once=True,
                        dry_run=False,
                        poll_interval=30,
                        heartbeat_interval=20,
                        codex_bin="",
                        codex_config_profile="",
                        continuous=False,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["selected_session"]["orp_session_id"], "session-primary")
            self.assertEqual(payload["selection"]["source"], "primary_session_fallback")
            self.assertEqual(payload["selection"]["fallback_reason"], "missing_target_session")
            self.assertEqual(payload["selection"]["requested_orp_session_id"], "session-stale")
            paths = [path for _, path, _ in calls]
            self.assertIn("/api/cli/runner/jobs/job_missing_target/start", paths)
            self.assertIn("/api/cli/runner/jobs/job_missing_target/complete", paths)

    def test_runner_work_sends_periodic_heartbeats_while_executing(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            calls.append((method, path, body))
            if path.startswith("/api/cli/runner/jobs/poll"):
                return {
                    "job": {
                        "id": "job_heartbeat",
                        "kind": "session.prompt",
                        "ideaId": "idea_123",
                        "payload": {
                            "prompt": "Long running prompt.",
                        },
                    }
                }
            return {"ok": True}

        def slow_run_runner_codex_job(*, job, repo_root, selected_session, args):
            time.sleep(2.2)
            return {
                "ok": True,
                "exitCode": 0,
                "stdout": "",
                "stderr": "",
                "body": "done",
                "summary": "done",
                "command": "codex exec resume ...",
            }

        module._request_hosted_json = fake_request_hosted_json
        module._run_runner_codex_job = slow_run_runner_codex_job

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            root = Path(td)
            _git_init_main(root)
            self._prepare_hosted_session(module, config_td)
            self._prepare_linked_repo(module, root)
            module._write_link_session(
                root,
                {
                    "orp_session_id": "session-primary",
                    "label": "Primary Session",
                    "state": "active",
                    "project_root": str(root),
                    "codex_session_id": "codex-primary",
                    "created_at_utc": "2026-03-16T01:10:00Z",
                    "last_active_at_utc": "2026-03-16T01:15:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_work(
                    argparse.Namespace(
                        repo_root=str(root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                        once=True,
                        dry_run=False,
                        poll_interval=30,
                        heartbeat_interval=1,
                        codex_bin="",
                        codex_config_profile="",
                        continuous=False,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            heartbeat_paths = [path for _, path, _ in calls if path == "/api/cli/runner/heartbeat"]
            self.assertGreaterEqual(len(heartbeat_paths), 2)
            self.assertEqual(payload["heartbeat"]["response"]["ok"], True)

    def test_wait_for_runner_signal_via_sse_returns_terminal_event(self) -> None:
        module = load_cli_module()

        class FakeSseResponse:
            def __init__(self, lines: list[bytes]) -> None:
                self._lines = lines

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def __iter__(self):
                return iter(self._lines)

        requests: list[tuple[str, dict[str, str], int]] = []

        def fake_urlopen(request, timeout=0):
            requests.append((request.full_url, dict(request.header_items()), timeout))
            return FakeSseResponse(
                [
                    b"event: ready\n",
                    b"data: {\"ok\": true}\n",
                    b"\n",
                    b": keep-alive\n",
                    b"\n",
                    b"event: job.available\n",
                    b"data: {\"ok\": true, \"jobAvailable\": true, \"reason\": \"available\", \"waitedMs\": 850}\n",
                    b"\n",
                ]
            )

        with tempfile.TemporaryDirectory() as config_td:
            self._prepare_hosted_session(module, config_td)
            module._save_runner_machine(
                {
                    "machine_id": "machine_live_123",
                    "machine_name": "Mac",
                    "runner_enabled": True,
                }
            )
            original_urlopen = module.urlrequest.urlopen
            module.urlrequest.urlopen = fake_urlopen
            try:
                signal = module._wait_for_runner_signal_via_sse(
                    argparse.Namespace(base_url="", transport="auto"),
                    12,
                )
            finally:
                module.urlrequest.urlopen = original_urlopen

        self.assertEqual(signal["transport"], "sse")
        self.assertEqual(signal["event"], "job.available")
        self.assertTrue(signal["jobAvailable"])
        self.assertEqual(signal["machine_id"], "machine_live_123")
        self.assertEqual(signal["wait_seconds"], 12)
        self.assertEqual(requests[0][0], "https://orp.earth/api/cli/runner/events/stream?machineId=machine_live_123&waitSeconds=12")
        self.assertEqual(requests[0][2], 30)
        self.assertEqual(requests[0][1]["Accept"], "text/event-stream")
        self.assertEqual(requests[0][1]["Authorization"], "Bearer tok_live_123")

    def test_runner_work_can_route_job_to_secondary_linked_repo(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            calls.append((method, path, body))
            if path.startswith("/api/cli/runner/jobs/poll"):
                return {
                    "job": {
                        "id": "job_multi",
                        "kind": "session.prompt",
                        "ideaId": "idea_secondary",
                        "payload": {
                            "prompt": "Send this to the secondary repo.",
                        },
                    }
                }
            return {"ok": True}

        def fake_run_runner_codex_job(*, job, repo_root, selected_session, args):
            self.assertEqual(job["id"], "job_multi")
            self.assertEqual(selected_session["orp_session_id"], "session-secondary")
            return {
                "ok": True,
                "exitCode": 0,
                "stdout": "secondary stdout\n",
                "stderr": "",
                "body": "Secondary repo handled the prompt.\n",
                "summary": "Secondary repo handled the prompt.",
                "command": "codex exec resume ...",
            }

        module._request_hosted_json = fake_request_hosted_json
        module._run_runner_codex_job = fake_run_runner_codex_job

        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as config_td:
            primary_root = Path(td) / "primary"
            secondary_root = Path(td) / "secondary"
            primary_root.mkdir(parents=True, exist_ok=True)
            secondary_root.mkdir(parents=True, exist_ok=True)
            _git_init_main(primary_root)
            _git_init_main(secondary_root)
            self._prepare_hosted_session(module, config_td)

            module._write_link_project(
                primary_root,
                {
                    "idea_id": "idea_primary",
                    "idea_title": "Primary Idea",
                    "world_id": "world_primary",
                    "world_name": "Primary World",
                    "project_root": str(primary_root),
                    "github_url": "https://github.com/example/primary.git",
                    "linked_at_utc": "2026-03-16T01:00:00Z",
                    "linked_email": "cody@example.com",
                    "source": "cli",
                },
            )
            module._write_link_session(
                primary_root,
                {
                    "orp_session_id": "session-primary",
                    "label": "Primary Session",
                    "state": "active",
                    "project_root": str(primary_root),
                    "codex_session_id": "codex-primary",
                    "created_at_utc": "2026-03-16T01:10:00Z",
                    "last_active_at_utc": "2026-03-16T01:15:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )
            module._write_link_project(
                secondary_root,
                {
                    "idea_id": "idea_secondary",
                    "idea_title": "Secondary Idea",
                    "world_id": "world_secondary",
                    "world_name": "Secondary World",
                    "project_root": str(secondary_root),
                    "github_url": "https://github.com/example/secondary.git",
                    "linked_at_utc": "2026-03-16T02:00:00Z",
                    "linked_email": "cody@example.com",
                    "source": "cli",
                },
            )
            module._write_link_session(
                secondary_root,
                {
                    "orp_session_id": "session-secondary",
                    "label": "Secondary Session",
                    "state": "active",
                    "project_root": str(secondary_root),
                    "codex_session_id": "codex-secondary",
                    "created_at_utc": "2026-03-16T02:10:00Z",
                    "last_active_at_utc": "2026-03-16T02:15:00Z",
                    "archived": False,
                    "primary": True,
                    "source": "cli",
                },
            )
            module._save_runner_machine({"runner_enabled": True})
            module._write_runner_repo_state(primary_root, module._load_runner_machine())

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_runner_work(
                    argparse.Namespace(
                        repo_root=str(primary_root),
                        config="orp.yml",
                        base_url="",
                        json_output=True,
                        once=True,
                        dry_run=False,
                        poll_interval=30,
                        heartbeat_interval=20,
                        codex_bin="",
                        codex_config_profile="",
                        linked_project_roots=[str(secondary_root)],
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["selected_repo_root"], str(secondary_root.resolve()))
            self.assertEqual(payload["selected_session"]["orp_session_id"], "session-secondary")
            self.assertEqual(payload["repo_selection"]["source"], "job_target_match")
            self.assertEqual(payload["repo_selection"]["matched_fields"], ["idea_id"])
            self.assertEqual(len(payload["sync_result"]["sync_payload"]["linkedProjects"]), 2)
            self.assertEqual(
                {row["ideaId"] for row in payload["sync_result"]["sync_payload"]["linkedProjects"]},
                {"idea_primary", "idea_secondary"},
            )
            self.assertEqual(
                {row["orpSessionId"] for row in payload["sync_result"]["sync_payload"]["sessions"]},
                {"session-primary", "session-secondary"},
            )
            paths = [path for _, path, _ in calls]
            self.assertIn("/api/cli/runner/jobs/job_multi/start", paths)
            self.assertIn("/api/cli/runner/jobs/job_multi/complete", paths)


if __name__ == "__main__":
    unittest.main()
