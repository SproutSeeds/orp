from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
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
