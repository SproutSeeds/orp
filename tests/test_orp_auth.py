from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_auth_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpAuthTests(unittest.TestCase):
    def test_auth_login_reads_password_from_stdin(self) -> None:
        module = load_cli_module()
        captured = {}

        def fake_request_hosted_json(*, base_url, path, method, body):
            captured.update(
                {
                    "base_url": base_url,
                    "path": path,
                    "method": method,
                    "body": body,
                }
            )
            return {
                "success": True,
                "message": "Verification code sent",
                "email": "co***@example.com",
                "expiresAt": "2026-03-14T00:00:00Z",
            }

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td:
            original_stdin = sys.stdin
            stdout = io.StringIO()
            try:
                os.environ["XDG_CONFIG_HOME"] = td
                sys.stdin = io.StringIO("correct horse battery staple\n")
                with redirect_stdout(stdout):
                    result = module.cmd_auth_login(
                        argparse.Namespace(
                            email="cody@example.com",
                            password="",
                            password_stdin=True,
                            base_url="",
                            json_output=True,
                        )
                    )
            finally:
                sys.stdin = original_stdin
                os.environ.pop("XDG_CONFIG_HOME", None)

            self.assertEqual(result, 0)
            self.assertEqual(captured["path"], "/api/auth/device-login")
            self.assertEqual(captured["method"], "POST")
            self.assertEqual(
                captured["body"],
                {
                    "email": "cody@example.com",
                    "password": "correct horse battery staple",
                },
            )

            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["pending_verification"])
            self.assertEqual(payload["email"], "co**@example.com")

            session_path = Path(td) / "orp" / "remote-session.json"
            session = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(session["email"], "cody@example.com")
            self.assertEqual(session["token"], "")
            self.assertIsNone(session["user"])
            self.assertEqual(
                session["pending_verification"]["expiresAt"],
                "2026-03-14T00:00:00Z",
            )

    def test_auth_verify_reads_code_from_stdin(self) -> None:
        module = load_cli_module()
        captured = {}

        def fake_request_hosted_json(*, base_url, path, method, body):
            captured.update(
                {
                    "base_url": base_url,
                    "path": path,
                    "method": method,
                    "body": body,
                }
            )
            return {
                "token": "tok_live_123",
                "userId": "user_123",
                "email": "cody@example.com",
                "name": "Cody",
            }

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td:
            original_stdin = sys.stdin
            stdout = io.StringIO()
            try:
                os.environ["XDG_CONFIG_HOME"] = td
                module._save_hosted_session(
                    {
                        "base_url": "https://orp.earth",
                        "email": "cody@example.com",
                        "token": "",
                        "user": None,
                        "pending_verification": {"expiresAt": "2026-03-14T00:00:00Z"},
                    }
                )
                sys.stdin = io.StringIO("713302\n")
                with redirect_stdout(stdout):
                    result = module.cmd_auth_verify(
                        argparse.Namespace(
                            email="",
                            code="",
                            code_stdin=True,
                            base_url="",
                            json_output=True,
                        )
                    )
            finally:
                sys.stdin = original_stdin
                os.environ.pop("XDG_CONFIG_HOME", None)

            self.assertEqual(result, 0)
            self.assertEqual(captured["path"], "/api/auth/device-verify")
            self.assertEqual(captured["method"], "POST")
            self.assertEqual(
                captured["body"],
                {
                    "email": "cody@example.com",
                    "code": "713302",
                },
            )

            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["connected"])
            self.assertEqual(payload["email"], "cody@example.com")
            self.assertEqual(payload["user_id"], "user_123")

            session_path = Path(td) / "orp" / "remote-session.json"
            session = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(session["token"], "tok_live_123")
            self.assertEqual(session["user"]["name"], "Cody")
            self.assertIsNone(session["pending_verification"])

    def test_auth_login_accepts_immediate_connected_session(self) -> None:
        module = load_cli_module()
        captured = {}

        def fake_request_hosted_json(*, base_url, path, method, body):
            captured.update(
                {
                    "base_url": base_url,
                    "path": path,
                    "method": method,
                    "body": body,
                }
            )
            return {
                "token": "tok_live_456",
                "userId": "user_456",
                "email": "cody@example.com",
                "name": "Cody",
            }

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td:
            original_stdin = sys.stdin
            stdout = io.StringIO()
            try:
                os.environ["XDG_CONFIG_HOME"] = td
                sys.stdin = io.StringIO("correct horse battery staple\n")
                with redirect_stdout(stdout):
                    result = module.cmd_auth_login(
                        argparse.Namespace(
                            email="cody@example.com",
                            password="",
                            password_stdin=True,
                            base_url="",
                            json_output=True,
                        )
                    )
            finally:
                sys.stdin = original_stdin
                os.environ.pop("XDG_CONFIG_HOME", None)

            self.assertEqual(result, 0)
            self.assertEqual(captured["path"], "/api/auth/device-login")
            self.assertEqual(
                captured["body"],
                {
                    "email": "cody@example.com",
                    "password": "correct horse battery staple",
                },
            )

            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["connected"])
            self.assertEqual(payload["email"], "cody@example.com")
            self.assertEqual(payload["user_id"], "user_456")

            session_path = Path(td) / "orp" / "remote-session.json"
            session = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(session["token"], "tok_live_456")
            self.assertEqual(session["user"]["name"], "Cody")
            self.assertIsNone(session["pending_verification"])

    def test_auth_login_rejects_password_arg_with_password_stdin(self) -> None:
        module = load_cli_module()
        with self.assertRaisesRegex(
            RuntimeError,
            "Use either --password or --password-stdin, not both.",
        ):
            module.cmd_auth_login(
                argparse.Namespace(
                    email="cody@example.com",
                    password="secret",
                    password_stdin=True,
                    base_url="",
                    json_output=True,
                )
            )

    def test_auth_verify_rejects_code_arg_with_code_stdin(self) -> None:
        module = load_cli_module()
        with self.assertRaisesRegex(
            RuntimeError,
            "Use either --code or --code-stdin, not both.",
        ):
            module.cmd_auth_verify(
                argparse.Namespace(
                    email="cody@example.com",
                    code="123456",
                    code_stdin=True,
                    base_url="",
                    json_output=True,
                )
            )


if __name__ == "__main__":
    unittest.main()
