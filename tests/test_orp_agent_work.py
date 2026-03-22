from __future__ import annotations

import argparse
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_agent_work_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpAgentWorkTests(unittest.TestCase):
    def test_agent_work_prefers_runner_primary_path(self) -> None:
        module = load_cli_module()
        repo_root = "/tmp/rust-smoke-linked-repo"

        def fake_runner_work_once(args):
            self.assertEqual(args.repo_root, repo_root)
            return {
                "ok": True,
                "claimed": True,
                "job": {
                    "id": "job_runner_123",
                    "kind": "idea.checkpoint",
                    "checkpointId": "checkpoint_runner_123",
                    "payload": {
                        "checkpointId": "checkpoint_runner_123",
                    },
                },
                "complete_response": {"ok": True},
            }

        def fail_legacy_worker(args):
            raise AssertionError("legacy worker should not run when runner work succeeds")

        module._run_runner_work_once = fake_runner_work_once
        module._run_worker_once = fail_legacy_worker

        buf = io.StringIO()
        with redirect_stdout(buf):
            result = module.cmd_agent_work(
                argparse.Namespace(
                    base_url="",
                json_output=True,
                once=True,
                dry_run=False,
                repo_root=repo_root,
                poll_interval=30,
                codex_bin="",
                codex_config_profile="",
                    agent="",
                )
            )

        self.assertEqual(result, 0)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["job"]["kind"], "idea.checkpoint")
        self.assertEqual(payload["compatibility"]["mode"], "runner-primary")
        self.assertFalse(payload["compatibility"]["legacy_fallback"])

    def test_agent_work_falls_back_to_legacy_checkpoint_worker(self) -> None:
        module = load_cli_module()

        def fail_runner_work_once(args):
            raise RuntimeError("No linked repo is available for runner work. Run `orp link project bind --idea-id <idea-id> --json` first.")

        def fake_legacy_worker(args):
            return {
                "ok": True,
                "claimed": True,
                "job": {
                    "checkpoint": {
                        "id": "checkpoint_legacy_123",
                    },
                },
                "response": {
                    "id": "response_legacy_123",
                },
            }

        module._run_runner_work_once = fail_runner_work_once
        module._run_worker_once = fake_legacy_worker

        buf = io.StringIO()
        with redirect_stdout(buf):
            result = module.cmd_agent_work(
                argparse.Namespace(
                    base_url="",
                json_output=True,
                once=True,
                dry_run=False,
                repo_root="/tmp/no-linked-runner-repo",
                poll_interval=30,
                codex_bin="",
                codex_config_profile="",
                    agent="",
                )
            )

        self.assertEqual(result, 0)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["response"]["id"], "response_legacy_123")
        self.assertEqual(payload["compatibility"]["mode"], "legacy-checkpoint-fallback")
        self.assertTrue(payload["compatibility"]["legacy_fallback"])
        self.assertIn("No linked repo is available for runner work", payload["compatibility"]["reason"])


if __name__ == "__main__":
    unittest.main()
