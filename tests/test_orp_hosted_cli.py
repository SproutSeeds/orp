from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_hosted_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HostedCliShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_xdg = os.environ.get("XDG_CONFIG_HOME")
        self.addCleanup(self._restore_xdg)

    def _restore_xdg(self) -> None:
        if self._old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self._old_xdg

    def _prepare_session(self, module, td: str) -> None:
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

    def test_hosted_html_404_is_reported_without_dumping_page(self) -> None:
        module = load_cli_module()
        error = module._hosted_api_error(
            base_url="https://orp.earth",
            path="/api/cli/secrets",
            method="GET",
            status=404,
            payload={"error": "<!DOCTYPE html><html><body>not found</body></html>"},
        )

        message = str(error)
        self.assertIn("Hosted ORP returned an HTML error page instead of JSON", message)
        self.assertIn("path=/api/cli/secrets", message)
        self.assertIn("hosted API route may not be deployed", message)
        self.assertNotIn("<!DOCTYPE html>", message)

    def test_ideas_list_accepts_items_and_next_cursor_shape(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(path, "/api/cli/ideas?limit=5")
            self.assertEqual(token, "tok_live_123")
            return {
                "ok": True,
                "items": [
                    {
                        "id": "idea_123",
                        "title": "Release smoke",
                        "visibility": "private",
                        "updatedAt": "2026-03-15T00:00:00Z",
                    }
                ],
                "nextCursor": "cursor_123",
                "sort": "updated_desc",
                "limit": 5,
            }

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_ideas_list(
                    argparse.Namespace(
                        limit=5,
                        cursor="",
                        sort="",
                        deleted=False,
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["cursor"], "cursor_123")
            self.assertTrue(payload["has_more"])
            self.assertEqual(payload["sort"], "updated_desc")
            self.assertEqual(len(payload["ideas"]), 1)
            self.assertEqual(payload["ideas"][0]["id"], "idea_123")

    def test_ideas_list_treats_null_next_cursor_as_empty(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(path, "/api/cli/ideas?limit=5")
            self.assertEqual(token, "tok_live_123")
            return {
                "ok": True,
                "items": [],
                "nextCursor": None,
                "sort": "updated_desc",
                "limit": 5,
            }

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_ideas_list(
                    argparse.Namespace(
                        limit=5,
                        cursor="",
                        sort="",
                        deleted=False,
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["cursor"], "")
            self.assertFalse(payload["has_more"])

    def test_idea_show_normalizes_wrapped_payload(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(path, "/api/cli/ideas/idea_123")
            self.assertEqual(token, "tok_live_123")
            return {
                "ok": True,
                "idea": {
                    "id": "idea_123",
                    "title": "Release smoke",
                    "visibility": "private",
                    "updatedAt": "2026-03-15T00:00:00Z",
                },
                "features": [{"id": "feat_1", "title": "One"}],
            }

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_idea_show(
                    argparse.Namespace(
                        idea_id="idea_123",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["idea"]["id"], "idea_123")
            self.assertEqual(payload["features"][0]["id"], "feat_1")
            self.assertEqual(payload["idea"]["features"][0]["id"], "feat_1")

    def test_feature_list_uses_wrapped_idea_payload(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(path, "/api/cli/ideas/idea_123")
            self.assertEqual(token, "tok_live_123")
            return {
                "ok": True,
                "idea": {
                    "id": "idea_123",
                    "title": "Release smoke",
                    "visibility": "private",
                },
                "features": [{"id": "feat_1", "title": "One"}],
            }

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_feature_list(
                    argparse.Namespace(
                        idea_id="idea_123",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["idea_id"], "idea_123")
            self.assertEqual(payload["idea_title"], "Release smoke")
            self.assertEqual(payload["features"][0]["id"], "feat_1")

    def test_idea_update_uses_wrapped_updated_at(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            if method == "GET":
                return {
                    "ok": True,
                    "idea": {
                        "id": "idea_123",
                        "title": "Release smoke",
                        "notes": "before",
                        "updatedAt": "2026-03-15T00:00:00Z",
                        "visibility": "private",
                    },
                    "features": [],
                }
            return {
                "ok": True,
                "id": "idea_123",
                "title": "Release smoke updated",
                "notes": "after",
                "updatedAt": "2026-03-15T00:01:00Z",
                "visibility": "private",
            }

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_idea_update(
                    argparse.Namespace(
                        idea_id="idea_123",
                        title="Release smoke updated",
                        notes="after",
                        summary=None,
                        github_url=None,
                        link_label=None,
                        visibility=None,
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            self.assertEqual(calls[0][0], "GET")
            self.assertEqual(calls[1][0], "PATCH")
            self.assertEqual(calls[1][1], "/api/cli/ideas/idea_123")
            self.assertEqual(calls[1][2]["updatedAt"], "2026-03-15T00:00:00Z")
            self.assertEqual(calls[1][2]["title"], "Release smoke updated")

    def test_secrets_list_uses_current_project_scope(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"
        idea_id = "22222222-2222-4222-8222-222222222222"

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            self.assertEqual(method, "GET")
            self.assertEqual(
                path,
                f"/api/cli/secrets?provider=openai&worldId={world_id}&ideaId={idea_id}",
            )
            self.assertIsNone(body)
            return {
                "ok": True,
                "items": [{"id": "secret_123", "alias": "openai-primary"}],
            }

        module._request_hosted_json = fake_request_hosted_json
        module._read_link_project = lambda repo_root: {
            "world_id": world_id,
            "idea_id": idea_id,
        }

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_list(
                    argparse.Namespace(
                        provider="openai",
                        world_id="",
                        idea_id="",
                        current_project=True,
                        archived=False,
                        base_url="",
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["world_id"], world_id)
            self.assertEqual(payload["idea_id"], idea_id)
            self.assertEqual(payload["items"][0]["alias"], "openai-primary")

    def test_secrets_add_posts_binding_for_current_project(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            self.assertEqual(method, "POST")
            self.assertEqual(path, "/api/cli/secrets")
            self.assertEqual(body["alias"], "openai-primary")
            self.assertEqual(body["label"], "OpenAI Primary")
            self.assertEqual(body["provider"], "openai")
            self.assertEqual(body["username"], "cody")
            self.assertEqual(body["value"], "sk-test")
            self.assertEqual(
                body["bindings"],
                [
                    {
                        "worldId": world_id,
                        "purpose": "agent work",
                        "isPrimary": True,
                    }
                ],
            )
            return {
                "ok": True,
                "secret": {
                    "id": "secret_123",
                    "alias": "openai-primary",
                    "bindings": body["bindings"],
                },
            }

        module._request_hosted_json = fake_request_hosted_json
        module._read_link_project = lambda repo_root: {
            "world_id": world_id,
            "idea_id": "",
        }

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_add(
                    argparse.Namespace(
                        alias="openai-primary",
                        label="OpenAI Primary",
                        provider="openai",
                        kind="api_key",
                        username="cody",
                        env_var_name="OPENAI_API_KEY",
                        value="sk-test",
                        value_stdin=False,
                        notes="main key",
                        world_id="",
                        idea_id="",
                        current_project=True,
                        purpose="agent work",
                        primary=True,
                        base_url="",
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["secret"]["id"], "secret_123")

    def test_secrets_ensure_reuses_existing_secret_and_binding(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"
        idea_id = "22222222-2222-4222-8222-222222222222"
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            if method == "GET":
                self.assertEqual(path, "/api/cli/secrets/openai-primary")
                return {
                    "ok": True,
                    "secret": {
                        "id": "secret_123",
                        "alias": "openai-primary",
                        "provider": "openai",
                        "bindings": [
                            {
                                "id": "binding_123",
                                "worldId": world_id,
                                "ideaId": idea_id,
                                "isPrimary": True,
                            }
                        ],
                    },
                }
            self.assertEqual(path, "/api/cli/secrets/resolve")
            self.assertEqual(
                body,
                {
                    "reveal": True,
                    "alias": "openai-primary",
                    "worldId": world_id,
                    "ideaId": idea_id,
                },
            )
            return {
                "ok": True,
                "secret": {
                    "id": "secret_123",
                    "alias": "openai-primary",
                    "provider": "openai",
                    "bindings": [],
                },
                "binding": {
                    "id": "binding_123",
                    "worldId": world_id,
                    "ideaId": idea_id,
                    "isPrimary": True,
                },
                "value": "sk-live",
                "matchedBy": "alias+project",
            }

        module._request_hosted_json = fake_request_hosted_json
        module._read_link_project = lambda repo_root: {
            "world_id": world_id,
            "idea_id": idea_id,
        }

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_ensure(
                    argparse.Namespace(
                        alias="openai-primary",
                        label="",
                        provider="openai",
                        kind="api_key",
                        env_var_name="OPENAI_API_KEY",
                        value=None,
                        value_stdin=False,
                        notes=None,
                        world_id="",
                        idea_id="",
                        current_project=True,
                        purpose="",
                        primary=False,
                        reveal=True,
                        base_url="",
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertFalse(payload["created"])
            self.assertFalse(payload["binding_created"])
            self.assertTrue(payload["binding_reused"])
            self.assertEqual(payload["value"], "sk-live")
            self.assertEqual(len(calls), 2)

    def test_secrets_ensure_creates_missing_secret_and_binding(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            if method == "GET":
                raise module.HostedApiError("Secret not found (status=404 path=/api/cli/secrets/openai-primary).")
            self.assertEqual(method, "POST")
            self.assertEqual(path, "/api/cli/secrets")
            self.assertEqual(body["alias"], "openai-primary")
            self.assertEqual(body["label"], "OpenAI Primary")
            self.assertEqual(body["provider"], "openai")
            self.assertEqual(body["username"], "cody")
            self.assertEqual(body["value"], "sk-test")
            self.assertEqual(
                body["bindings"],
                [
                    {
                        "worldId": world_id,
                        "purpose": "agent work",
                        "isPrimary": True,
                    }
                ],
            )
            return {
                "ok": True,
                "secret": {
                    "id": "secret_123",
                    "alias": "openai-primary",
                    "provider": "openai",
                    "bindings": body["bindings"],
                },
            }

        module._request_hosted_json = fake_request_hosted_json
        module._read_link_project = lambda repo_root: {
            "world_id": world_id,
            "idea_id": "",
        }

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_ensure(
                    argparse.Namespace(
                        alias="openai-primary",
                        label="OpenAI Primary",
                        provider="openai",
                        kind="api_key",
                        username="cody",
                        env_var_name="OPENAI_API_KEY",
                        value="sk-test",
                        value_stdin=False,
                        notes="main key",
                        world_id="",
                        idea_id="",
                        current_project=True,
                        purpose="agent work",
                        primary=True,
                        reveal=False,
                        base_url="",
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["created"])
            self.assertTrue(payload["binding_created"])
            self.assertFalse(payload["binding_reused"])
            self.assertEqual(payload["secret"]["alias"], "openai-primary")

    def test_secrets_ensure_creates_binding_for_existing_secret_when_missing(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"
        idea_id = "22222222-2222-4222-8222-222222222222"
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            if method == "GET":
                return {
                    "ok": True,
                    "secret": {
                        "id": "secret_123",
                        "alias": "openai-primary",
                        "provider": "openai",
                        "bindings": [],
                    },
                }
            self.assertEqual(path, "/api/cli/secrets/bindings")
            self.assertEqual(
                body,
                {
                    "worldId": world_id,
                    "ideaId": idea_id,
                    "purpose": "embeddings",
                    "secretAlias": "openai-primary",
                },
            )
            return {
                "ok": True,
                "binding": {
                    "id": "binding_456",
                    "worldId": world_id,
                    "ideaId": idea_id,
                    "purpose": "embeddings",
                    "secretId": "secret_123",
                },
            }

        module._request_hosted_json = fake_request_hosted_json
        module._read_link_project = lambda repo_root: {
            "world_id": world_id,
            "idea_id": idea_id,
        }

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_ensure(
                    argparse.Namespace(
                        alias="openai-primary",
                        label="",
                        provider="openai",
                        kind="api_key",
                        env_var_name=None,
                        value=None,
                        value_stdin=False,
                        notes=None,
                        world_id="",
                        idea_id="",
                        current_project=True,
                        purpose="embeddings",
                        primary=False,
                        reveal=False,
                        base_url="",
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertFalse(payload["created"])
            self.assertTrue(payload["binding_created"])
            self.assertFalse(payload["binding_reused"])
            self.assertEqual(payload["binding"]["id"], "binding_456")

    def test_secrets_sync_keychain_stores_hosted_secret_locally(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            self.assertEqual(method, "POST")
            self.assertEqual(path, "/api/cli/secrets/resolve")
            self.assertEqual(body["alias"], "openai-primary")
            self.assertTrue(body["reveal"])
            return {
                "ok": True,
                "secret": {
                    "id": "secret_123",
                    "alias": "openai-primary",
                    "label": "OpenAI Primary",
                    "provider": "openai",
                    "kind": "api_key",
                    "username": "cody",
                    "envVarName": "OPENAI_API_KEY",
                    "bindings": [],
                },
                "binding": {
                    "id": "binding_123",
                    "worldId": world_id,
                    "isPrimary": True,
                },
                "value": "sk-live",
                "matchedBy": "alias+project",
            }

        module._request_hosted_json = fake_request_hosted_json
        module._read_link_project = lambda repo_root: {
            "world_id": world_id,
            "idea_id": "",
        }
        module._keychain_supported = lambda: True
        module._ensure_keychain_supported = lambda: None
        module._run_keychain_command = lambda args, input_text=None: subprocess.CompletedProcess(
            ["security", *args],
            0,
            "",
            "",
        )

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_sync_keychain(
                    argparse.Namespace(
                        secret_ref="openai-primary",
                        provider="",
                        world_id="",
                        idea_id="",
                        current_project=True,
                        all=False,
                        base_url="",
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["count"], 1)
            entry = payload["items"][0]
            self.assertEqual(entry["alias"], "openai-primary")
            self.assertEqual(entry["provider"], "openai")
            self.assertEqual(entry["username"], "cody")
            self.assertEqual(entry["keychain_service"], "orp.secret.openai")
            registry_path = Path(td) / "orp" / "secrets-keychain.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(registry["items"][0]["alias"], "openai-primary")
            self.assertEqual(registry["items"][0]["username"], "cody")

    def test_secrets_keychain_add_stores_local_secret_without_hosted_api(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"
        stored: dict[str, object] = {}

        def fake_store_keychain_secret_value(secret, value):
            stored["secret"] = secret
            stored["value"] = value
            return {
                "keychain_service": "orp.secret.openai",
                "keychain_account": "openai-primary",
                "keychain_label": "OpenAI Primary",
            }

        def fail_hosted_request(*args, **kwargs):
            raise AssertionError("local keychain-add should not call the hosted secret API")

        module._request_secret_payload = fail_hosted_request
        module._ensure_keychain_supported = lambda: None
        module._store_keychain_secret_value = fake_store_keychain_secret_value

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            os.environ["XDG_CONFIG_HOME"] = td
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_keychain_add(
                    argparse.Namespace(
                        alias="openai-primary",
                        label="OpenAI Primary",
                        provider="openai",
                        kind="api_key",
                        username=None,
                        env_var_name="OPENAI_API_KEY",
                        value="sk-local",
                        value_stdin=False,
                        from_env=False,
                        daily_spend_cap_usd=5.0,
                        dashboard_spend_cap_status="confirmed",
                        dashboard_project_id="proj_openai_test",
                        dashboard_url="https://platform.openai.com/settings/organization/limits",
                        world_id=world_id,
                        idea_id="",
                        current_project=False,
                        purpose="research",
                        primary=True,
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["created"])
            self.assertEqual(payload["source"], "keychain")
            self.assertEqual(payload["secret"]["alias"], "openai-primary")
            self.assertEqual(payload["secret"]["provider"], "openai")
            self.assertEqual(payload["secret"]["envVarName"], "OPENAI_API_KEY")
            self.assertEqual(payload["secret"]["spendPolicy"]["dailyCapUsd"], 5.0)
            self.assertEqual(payload["secret"]["spendPolicy"]["dashboardLimit"]["status"], "confirmed")
            self.assertEqual(payload["secret"]["spendPolicy"]["dashboardLimit"]["projectId"], "proj_openai_test")
            self.assertEqual(payload["keychain_service"], "orp.secret.openai")
            self.assertEqual(stored["value"], "sk-local")
            self.assertNotIn("sk-local", json.dumps(payload))
            registry_path = Path(td) / "orp" / "secrets-keychain.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            entry = registry["items"][0]
            self.assertEqual(entry["alias"], "openai-primary")
            self.assertEqual(entry["value_preview"], "stored in local Keychain")
            self.assertEqual(entry["spend_policy"]["daily_cap_usd"], 5.0)
            self.assertEqual(entry["spend_policy"]["dashboard_limit"]["status"], "confirmed")
            self.assertNotIn("sk-local", json.dumps(registry))
            self.assertEqual(entry["bindings"][0]["world_id"], world_id)
            self.assertTrue(entry["bindings"][0]["primary"])

    def test_secrets_keychain_spend_policy_updates_metadata_without_secret_value(self) -> None:
        module = load_cli_module()

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            os.environ["XDG_CONFIG_HOME"] = td
            module._save_keychain_secret_registry(
                {
                    "schema_version": "1.0.0",
                    "items": [
                        {
                            "secret_id": "local-openai",
                            "alias": "openai-primary",
                            "label": "OpenAI Primary",
                            "provider": "openai",
                            "kind": "api_key",
                            "username": "",
                            "env_var_name": "OPENAI_API_KEY",
                            "status": "active",
                            "value_version": "local:2026-04-17T00:00:00Z",
                            "value_preview": "stored in local Keychain",
                            "keychain_service": "orp.secret.openai",
                            "keychain_account": "openai-primary",
                            "keychain_label": "OpenAI Primary",
                            "bindings": [],
                            "last_synced_at_utc": "2026-04-17T00:00:00Z",
                        }
                    ],
                }
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_keychain_spend_policy(
                    argparse.Namespace(
                        secret_ref="openai-primary",
                        daily_spend_cap_usd=5.0,
                        dashboard_spend_cap_status="unconfirmed",
                        dashboard_project_id="",
                        dashboard_url="https://platform.openai.com/settings/organization/limits",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["secret"]["spendPolicy"]["dailyCapUsd"], 5.0)
            self.assertEqual(payload["secret"]["spendPolicy"]["dashboardLimit"]["status"], "unconfirmed")
            self.assertEqual(
                payload["secret"]["spendPolicy"]["dashboardLimit"]["dashboardUrl"],
                "https://platform.openai.com/settings/organization/limits",
            )
            self.assertNotIn("value", payload)
            registry = json.loads((Path(td) / "orp" / "secrets-keychain.json").read_text(encoding="utf-8"))
            entry = registry["items"][0]
            self.assertEqual(entry["spend_policy"]["daily_cap_usd"], 5.0)
            self.assertEqual(entry["keychain_account"], "openai-primary")

    def test_secrets_keychain_list_filters_current_project(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"
        idea_id = "22222222-2222-4222-8222-222222222222"
        module._read_link_project = lambda repo_root: {
            "world_id": world_id,
            "idea_id": idea_id,
        }

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            os.environ["XDG_CONFIG_HOME"] = td
            module._save_keychain_secret_registry(
                {
                    "schema_version": "1.0.0",
                    "items": [
                        {
                            "secret_id": "secret_123",
                            "alias": "openai-primary",
                            "label": "OpenAI Primary",
                            "provider": "openai",
                            "kind": "api_key",
                            "username": "cody",
                            "env_var_name": "OPENAI_API_KEY",
                            "status": "active",
                            "keychain_service": "orp.secret.openai",
                            "keychain_account": "openai-primary",
                            "keychain_label": "OpenAI Primary",
                            "bindings": [
                                {
                                    "binding_id": "binding_123",
                                    "world_id": world_id,
                                    "idea_id": idea_id,
                                    "purpose": "agent work",
                                    "primary": True,
                                }
                            ],
                            "last_synced_at_utc": "2026-03-30T12:00:00Z",
                        },
                        {
                            "secret_id": "secret_456",
                            "alias": "anthropic-primary",
                            "label": "Anthropic Primary",
                            "provider": "anthropic",
                            "kind": "api_key",
                            "username": "anthropic-user",
                            "env_var_name": "ANTHROPIC_API_KEY",
                            "status": "active",
                            "keychain_service": "orp.secret.anthropic",
                            "keychain_account": "anthropic-primary",
                            "keychain_label": "Anthropic Primary",
                            "bindings": [],
                            "last_synced_at_utc": "2026-03-30T12:05:00Z",
                        },
                    ],
                }
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_keychain_list(
                    argparse.Namespace(
                        provider="openai",
                        world_id="",
                        idea_id="",
                        current_project=True,
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["provider"], "openai")
            self.assertEqual(payload["world_id"], world_id)
            self.assertEqual(len(payload["items"]), 1)
            self.assertEqual(payload["items"][0]["alias"], "openai-primary")

    def test_secrets_keychain_show_reveals_local_value(self) -> None:
        module = load_cli_module()
        module._read_keychain_secret_value = lambda entry: "sk-local"

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            os.environ["XDG_CONFIG_HOME"] = td
            module._save_keychain_secret_registry(
                {
                    "schema_version": "1.0.0",
                    "items": [
                        {
                            "secret_id": "secret_123",
                            "alias": "openai-primary",
                            "label": "OpenAI Primary",
                            "provider": "openai",
                            "kind": "api_key",
                            "username": "cody",
                            "env_var_name": "OPENAI_API_KEY",
                            "status": "active",
                            "keychain_service": "orp.secret.openai",
                            "keychain_account": "openai-primary",
                            "keychain_label": "OpenAI Primary",
                            "bindings": [],
                            "last_synced_at_utc": "2026-03-30T12:00:00Z",
                        }
                    ],
                }
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_keychain_show(
                    argparse.Namespace(
                        secret_ref="openai-primary",
                        reveal=True,
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["source"], "keychain")
            self.assertEqual(payload["secret"]["alias"], "openai-primary")
            self.assertEqual(payload["secret"]["username"], "cody")
            self.assertEqual(payload["value"], "sk-local")

    def test_secrets_resolve_local_first_uses_keychain_cache(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"
        idea_id = "22222222-2222-4222-8222-222222222222"

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            raise AssertionError("hosted secret store should not be queried when local Keychain cache satisfies the request")

        module._request_hosted_json = fake_request_hosted_json
        module._read_link_project = lambda repo_root: {
            "world_id": world_id,
            "idea_id": idea_id,
        }
        module._keychain_supported = lambda: True
        module._read_keychain_secret_value = lambda entry: "sk-local"

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            os.environ["XDG_CONFIG_HOME"] = td
            module._save_keychain_secret_registry(
                {
                    "schema_version": "1.0.0",
                    "items": [
                        {
                            "secret_id": "secret_123",
                            "alias": "openai-primary",
                            "label": "OpenAI Primary",
                            "provider": "openai",
                            "kind": "api_key",
                            "username": "cody",
                            "env_var_name": "OPENAI_API_KEY",
                            "status": "active",
                            "value_version": "",
                            "value_preview": "",
                            "keychain_service": "orp.secret.openai",
                            "keychain_account": "openai-primary",
                            "keychain_label": "OpenAI Primary",
                            "bindings": [
                                {
                                    "binding_id": "binding_123",
                                    "world_id": world_id,
                                    "idea_id": idea_id,
                                    "purpose": "agent work",
                                    "primary": True,
                                }
                            ],
                            "last_synced_at_utc": "2026-03-30T12:00:00Z",
                        }
                    ],
                }
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_resolve(
                    argparse.Namespace(
                        secret_ref="",
                        provider="openai",
                        world_id="",
                        idea_id="",
                        current_project=True,
                        reveal=True,
                        local_first=True,
                        local_only=False,
                        sync_keychain=False,
                        base_url="",
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["source"], "keychain")
            self.assertEqual(payload["value"], "sk-local")
            self.assertEqual(payload["matched_by"], "keychain+provider+project")

    def test_secrets_bind_uses_alias_and_current_project_scope(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"
        idea_id = "22222222-2222-4222-8222-222222222222"

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            self.assertEqual(method, "POST")
            self.assertEqual(path, "/api/cli/secrets/bindings")
            self.assertEqual(body["secretAlias"], "openai-primary")
            self.assertEqual(body["worldId"], world_id)
            self.assertEqual(body["ideaId"], idea_id)
            self.assertEqual(body["purpose"], "embeddings")
            self.assertTrue(body["isPrimary"])
            return {
                "ok": True,
                "binding": {
                    "id": "binding_123",
                    "secretId": "secret_123",
                    "worldId": world_id,
                    "ideaId": idea_id,
                    "isPrimary": True,
                },
            }

        module._request_hosted_json = fake_request_hosted_json
        module._read_link_project = lambda repo_root: {
            "world_id": world_id,
            "idea_id": idea_id,
        }

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_bind(
                    argparse.Namespace(
                        secret_ref="openai-primary",
                        world_id="",
                        idea_id="",
                        current_project=True,
                        purpose="embeddings",
                        primary=True,
                        base_url="",
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["binding"]["id"], "binding_123")

    def test_secrets_resolve_reveals_value_from_provider_and_project_scope(self) -> None:
        module = load_cli_module()
        world_id = "11111111-1111-4111-8111-111111111111"
        idea_id = "22222222-2222-4222-8222-222222222222"

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            self.assertEqual(method, "POST")
            self.assertEqual(path, "/api/cli/secrets/resolve")
            self.assertEqual(
                body,
                {
                    "reveal": True,
                    "provider": "openai",
                    "worldId": world_id,
                    "ideaId": idea_id,
                },
            )
            return {
                "ok": True,
                "secret": {
                    "id": "secret_123",
                    "alias": "openai-primary",
                    "provider": "openai",
                    "bindings": [],
                },
                "binding": {
                    "id": "binding_123",
                    "worldId": world_id,
                    "ideaId": idea_id,
                },
                "value": "sk-live",
                "matchedBy": "provider+project",
            }

        module._request_hosted_json = fake_request_hosted_json
        module._read_link_project = lambda repo_root: {
            "world_id": world_id,
            "idea_id": idea_id,
        }

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_secrets_resolve(
                    argparse.Namespace(
                        secret_ref="",
                        provider="openai",
                        world_id="",
                        idea_id="",
                        current_project=True,
                        reveal=True,
                        base_url="",
                        json_output=True,
                        repo_root=td,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["value"], "sk-live")
            self.assertEqual(payload["matched_by"], "provider+project")


if __name__ == "__main__":
    unittest.main()
