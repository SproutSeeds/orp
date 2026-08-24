from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
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
    def test_local_secret_uses_native_keychain_without_process_arguments(self) -> None:
        module = load_cli_module()
        captured = {}
        module._keychain_store_password = lambda **kwargs: captured.update(kwargs)
        self.assertFalse(hasattr(module, "_run_keychain_command"))

        coordinates = module._store_keychain_secret_value(
            {
                "id": "local-test",
                "alias": "long-test-secret",
                "label": "Long test secret",
                "provider": "example",
                "envVarName": "EXAMPLE_TOKEN",
            },
            "s" * 256,
        )

        self.assertEqual(captured["service"], "orp.secret.example")
        self.assertEqual(captured["account"], "long-test-secret")
        self.assertEqual(captured["value"], "s" * 256)
        self.assertEqual(coordinates["keychain_service"], "orp.secret.example")

    def test_hosted_credentials_use_native_keychain_without_subprocess_arguments(self) -> None:
        module = load_cli_module()
        captured = {}

        def fake_store_password(**kwargs):
            captured.update(kwargs)

        module._keychain_store_password = fake_store_password
        self.assertFalse(hasattr(module, "_run_keychain_command"))
        coordinates = module._store_hosted_credentials("https://orp.earth", {
            "access_token": "access-secret",
            "refresh_token": "refresh-secret",
            "token_type": "Bearer",
            "expires_in": 600,
            "scope": "profile:read",
        })

        self.assertEqual(captured["service"], "earth.orp.cli.auth")
        self.assertEqual(captured["value"].count("access-secret"), 1)
        self.assertEqual(captured["value"].count("refresh-secret"), 1)
        self.assertEqual(coordinates["service"], "earth.orp.cli.auth")

    def test_auth_devices_lists_scoped_device_metadata(self) -> None:
        module = load_cli_module()
        module._require_hosted_session = lambda _args: {
            "token": "access-secret",
            "base_url": "https://orp.earth",
        }

        def fake_request_hosted_json(**kwargs):
            self.assertEqual(kwargs["path"], "/api/auth/devices")
            self.assertEqual(kwargs["token"], "access-secret")
            return {
                "ok": True,
                "devices": [
                    {
                        "id": "device-1",
                        "name": "Studio",
                        "status": "active",
                        "current": True,
                        "scopes": ["devices:manage"],
                    }
                ],
            }

        module._request_hosted_json = fake_request_hosted_json
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = module.cmd_auth_devices(
                argparse.Namespace(base_url="", json_output=True)
            )
        self.assertEqual(result, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["devices"][0]["id"], "device-1")
        self.assertNotIn("access-secret", buffer.getvalue())

    def test_auth_revoke_current_device_clears_local_credentials(self) -> None:
        module = load_cli_module()
        stored_session = {
            "token": "",
            "base_url": "https://orp.earth",
            "email": "person@example.com",
            "credential": {"service": "service", "account": "account"},
        }
        active_session = {**stored_session, "token": "access-secret"}
        saved = []
        module._load_hosted_session = lambda: stored_session
        module._require_hosted_session = lambda _args: active_session
        module._delete_hosted_credentials = lambda _session: True
        module._save_hosted_session = lambda payload: saved.append(payload)

        def fake_request_hosted_json(**kwargs):
            self.assertEqual(kwargs["path"], "/api/auth/devices/device-1")
            self.assertEqual(kwargs["method"], "DELETE")
            self.assertEqual(kwargs["token"], "access-secret")
            return {"ok": True, "status": "revoked", "current": True}

        module._request_hosted_json = fake_request_hosted_json
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = module.cmd_auth_revoke_device(
                argparse.Namespace(device_id="device-1", base_url="", json_output=True)
            )
        self.assertEqual(result, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["current"])
        self.assertTrue(payload["local_credentials_removed"])
        self.assertIsNone(saved[0]["credential"])
        self.assertNotIn("access-secret", buffer.getvalue())

    def test_auth_login_uses_browser_device_flow_and_keeps_tokens_out_of_state(self) -> None:
        module = load_cli_module()
        requests = []
        stored = {}
        token_polls = 0

        def fake_request_hosted_json(**kwargs):
            nonlocal token_polls
            requests.append(kwargs)
            if kwargs["path"] == "/api/auth/device/start":
                return {
                    "device_code": "orp_dc_one_time_secret",
                    "user_code": "ABCD-EFGH",
                    "verification_uri": "https://orp.earth/device",
                    "verification_uri_complete": "https://orp.earth/device?user_code=ABCD-EFGH",
                    "expires_in": 600,
                    "interval": 1,
                }
            if kwargs["path"] == "/api/auth/device/token":
                token_polls += 1
                if token_polls == 1:
                    raise module.HostedApiError("pending", code="authorization_pending", status=400)
                return {
                    "access_token": "access-secret",
                    "refresh_token": "refresh-secret",
                    "token_type": "Bearer",
                    "expires_in": 600,
                    "scope": "profile:read workspaces:read",
                }
            self.assertEqual(kwargs["path"], "/api/cli/me")
            self.assertEqual(kwargs["token"], "access-secret")
            return {"ok": True, "user": {"id": "user-1", "email": "cody@example.com", "name": "Cody"}}

        def fake_store(base_url, payload):
            stored.update({"base_url": base_url, "payload": payload})
            return {"service": "earth.orp.cli.auth", "account": "orp-cli-test"}

        module._request_hosted_json = fake_request_hosted_json
        module._store_hosted_credentials = fake_store
        module.time.sleep = lambda _seconds: None
        module.webbrowser.open = lambda *_args, **_kwargs: True

        with tempfile.TemporaryDirectory() as td:
            stdout = io.StringIO()
            stderr = io.StringIO()
            try:
                os.environ["XDG_CONFIG_HOME"] = td
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    result = module.cmd_auth_login(
                        argparse.Namespace(
                            device_name="Cody laptop",
                            scopes=["profile:read", "workspaces:read"],
                            no_browser=False,
                            timeout=30,
                            base_url="",
                            json_output=True,
                        )
                    )
            finally:
                os.environ.pop("XDG_CONFIG_HOME", None)

            self.assertEqual(result, 0)
            self.assertEqual([request["path"] for request in requests], [
                "/api/auth/device/start",
                "/api/auth/device/token",
                "/api/auth/device/token",
                "/api/cli/me",
            ])
            self.assertEqual(stored["payload"]["refresh_token"], "refresh-secret")
            self.assertIn("ABCD-EFGH", stderr.getvalue())

            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["connected"])
            self.assertEqual(payload["credential_storage"], "macos_keychain")

            session_path = Path(td) / "orp" / "remote-session.json"
            session = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(session["email"], "cody@example.com")
            self.assertEqual(session["token"], "")
            self.assertEqual(session["auth_mode"], "device_authorization")
            encoded = session_path.read_text(encoding="utf-8")
            self.assertNotIn("access-secret", encoded)
            self.assertNotIn("refresh-secret", encoded)
            self.assertNotIn("one_time_secret", encoded)

    def test_hosted_session_refresh_rotates_the_keychain_bundle(self) -> None:
        module = load_cli_module()
        reads = iter([
            {"schema_version": "orp.hosted_credential/1", "access_token": "old", "refresh_token": "refresh-old", "access_expires_at": 1},
            {"schema_version": "orp.hosted_credential/1", "access_token": "new", "refresh_token": "refresh-new", "access_expires_at": int(module.time.time()) + 600},
        ])
        module._read_hosted_credentials = lambda _session: next(reads)
        captured = {}
        module._request_hosted_json = lambda **kwargs: captured.update(kwargs) or {
            "access_token": "new",
            "refresh_token": "refresh-new",
            "expires_in": 600,
        }
        module._store_hosted_credentials = lambda _base, _payload: {"service": "service", "account": "account"}
        module._save_hosted_session = lambda payload: captured.update({"saved": payload})
        hydrated = module._hydrate_hosted_session({
            "base_url": "https://orp.earth",
            "auth_mode": "device_authorization",
            "credential": {"service": "service", "account": "account"},
        }, refresh=True)
        self.assertEqual(captured["path"], "/api/auth/device/token")
        self.assertEqual(captured["body"]["refresh_token"], "refresh-old")
        self.assertEqual(hydrated["token"], "new")

    def test_auth_login_verifies_identity_before_writing_keychain(self) -> None:
        module = load_cli_module()
        stored = []

        def fake_request_hosted_json(**kwargs):
            if kwargs["path"] == "/api/auth/device/start":
                return {
                    "device_code": "one-time-device-code",
                    "user_code": "ABCD-EFGH",
                    "verification_uri": "https://orp.earth/device",
                    "expires_in": 600,
                    "interval": 1,
                }
            if kwargs["path"] == "/api/auth/device/token":
                return {
                    "access_token": "access-secret",
                    "refresh_token": "refresh-secret",
                    "expires_in": 600,
                }
            raise module.HostedApiError("Identity check failed", code="unauthorized", status=401)

        module._request_hosted_json = fake_request_hosted_json
        module._store_hosted_credentials = lambda *_args, **_kwargs: stored.append(True)

        with self.assertRaisesRegex(module.HostedApiError, "Identity check failed"):
            module.cmd_auth_login(argparse.Namespace(
                device_name="Test",
                scopes=[],
                no_browser=True,
                timeout=30,
                base_url="https://orp.earth",
                json_output=True,
            ))
        self.assertEqual(stored, [])

    def test_device_session_save_never_persists_new_credentials(self) -> None:
        module = load_cli_module()
        with tempfile.TemporaryDirectory() as td:
            try:
                os.environ["XDG_CONFIG_HOME"] = td
                module._save_hosted_session({
                    "base_url": "https://orp.earth",
                    "auth_mode": "device_authorization",
                    "token": "access-secret",
                    "refresh_token": "refresh-secret",
                    "device_code": "device-secret",
                    "credential": {"service": "service", "account": "account"},
                })
                encoded = (Path(td) / "orp" / "remote-session.json").read_text(encoding="utf-8")
            finally:
                os.environ.pop("XDG_CONFIG_HOME", None)
        self.assertNotIn("access-secret", encoded)
        self.assertNotIn("refresh-secret", encoded)
        self.assertNotIn("device-secret", encoded)

    def test_auth_verify_is_retired(self) -> None:
        module = load_cli_module()
        with self.assertRaisesRegex(RuntimeError, "retired"):
            module.cmd_auth_verify(argparse.Namespace())

    def test_oauth_error_contract_is_parsed_without_reflecting_request_credentials(self) -> None:
        module = load_cli_module()
        error = module._hosted_api_error(
            base_url="https://orp.earth",
            path="/api/auth/device/token",
            method="POST",
            status=400,
            payload={"error": "authorization_pending", "error_description": "Authorization is still pending."},
        )
        self.assertEqual(error.code, "authorization_pending")
        self.assertIn("Authorization is still pending", str(error))


if __name__ == "__main__":
    unittest.main()
