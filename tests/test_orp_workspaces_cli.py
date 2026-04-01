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
    spec = importlib.util.spec_from_file_location("orp_cli_workspaces_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HostedWorkspacesCliTests(unittest.TestCase):
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

    def test_build_remote_workspace_body_requires_slug_title(self) -> None:
        module = load_cli_module()

        body = module._build_remote_workspace_body(
            argparse.Namespace(
                title="main-cody-1",
                description=None,
                visibility=None,
                idea_id=None,
            ),
            None,
        )
        self.assertEqual(body["title"], "main-cody-1")

        with self.assertRaisesRegex(RuntimeError, "main-cody-1"):
            module._build_remote_workspace_body(
                argparse.Namespace(
                    title="Main Cody 1",
                    description=None,
                    visibility=None,
                    idea_id=None,
                ),
                None,
            )

    def test_workspaces_list_accepts_items_and_next_cursor_shape(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(path, "/api/cli/workspaces?limit=3")
            self.assertEqual(token, "tok_live_123")
            return {
                "ok": True,
                "items": [
                    {
                        "workspace_id": "ws_orp_main",
                        "title": "ORP Main",
                        "updatedAt": "2026-03-29T10:00:00Z",
                        "metrics": {"tabCount": 4},
                    }
                ],
                "nextCursor": "cursor_ws_123",
            }

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_workspaces_list(
                    argparse.Namespace(
                        limit=3,
                        cursor="",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["cursor"], "cursor_ws_123")
            self.assertTrue(payload["has_more"])
            self.assertEqual(payload["workspaces"][0]["workspace_id"], "ws_orp_main")
            self.assertEqual(payload["source"], "hosted")

    def test_workspaces_list_falls_back_to_idea_backed_saved_workspaces_when_route_is_missing(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            if path == "/api/cli/workspaces?limit=2":
                raise module.HostedApiError("Request failed: 404 (status=404 path=/api/cli/workspaces?limit=2).")
            if path == "/api/cli/ideas?limit=2":
                return {
                    "ok": True,
                    "ideas": [
                        {
                            "id": "idea_123",
                            "title": "Terminal paths and codex sessions 03-26-2026",
                            "visibility": "private",
                            "updatedAt": "2026-03-30T12:00:00Z",
                            "notes": """
```orp-workspace
{
  "version": "1",
  "workspaceId": "main-cody-1",
  "title": "Main Cody 1",
  "tabs": [
    { "title": "orp", "path": "/Volumes/Code_2TB/code/orp", "codexSessionId": "sess_123" },
    { "title": "web", "path": "/Volumes/Code_2TB/code/orp-web-app" }
  ]
}
```
""",
                        }
                    ],
                }
            raise AssertionError(f"unexpected path: {path}")

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_workspaces_list(
                    argparse.Namespace(
                        limit=2,
                        cursor="",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["source"], "idea_bridge")
            self.assertEqual(payload["workspaces"][0]["workspace_id"], "main-cody-1")
            self.assertEqual(payload["workspaces"][0]["title"], "Main Cody 1")
            self.assertEqual(payload["workspaces"][0]["linkedIdea"]["ideaId"], "idea_123")
            self.assertEqual(payload["workspaces"][0]["metrics"]["tabCount"], 2)

    def test_workspaces_show_normalizes_wrapped_payload(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            if path == "/api/cli/workspaces?limit=200":
                return {
                    "ok": True,
                    "items": [
                        {
                            "workspace_id": "ws_orp_main",
                            "title": "ORP Main",
                        }
                    ],
                }
            self.assertEqual(path, "/api/cli/workspaces/ws_orp_main")
            return {
                "ok": True,
                "workspace": {
                    "workspace_id": "ws_orp_main",
                    "title": "ORP Main",
                    "visibility": "private",
                    "state": {
                        "state_version": 2,
                        "snapshot_id": "snapshot_123",
                        "updated_at_utc": "2026-03-29T10:00:00Z",
                        "tab_count": 2,
                        "tabs": [
                            {
                                "tab_id": "tab_1",
                                "order_index": 0,
                                "project_root": "/Volumes/Code_2TB/code/orp",
                                "status": "active",
                            }
                        ],
                    },
                },
            }

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_workspaces_show(
                    argparse.Namespace(
                        workspace_id="ws_orp_main",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["workspace"]["workspace_id"], "ws_orp_main")
            self.assertEqual(payload["workspace"]["state"]["tabs"][0]["project_root"], "/Volumes/Code_2TB/code/orp")

    def test_workspaces_tabs_can_resolve_idea_bridge_workspace_by_title(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            if path == "/api/cli/workspaces?limit=200":
                raise module.HostedApiError("Request failed: 404 (status=404 path=/api/cli/workspaces?limit=200).")
            if path == "/api/cli/ideas?limit=200":
                return {
                    "ok": True,
                    "ideas": [
                        {
                            "id": "idea_123",
                            "title": "Terminal paths and codex sessions 03-26-2026",
                            "visibility": "private",
                            "updatedAt": "2026-03-30T12:00:00Z",
                            "notes": """
```orp-workspace
{
  "version": "1",
  "workspaceId": "main-cody-1",
  "title": "Main Cody 1",
  "tabs": [
    { "title": "orp", "path": "/Volumes/Code_2TB/code/orp", "codexSessionId": "sess_123", "tmuxSessionName": "orp-orp-123" },
    { "title": "web", "path": "/Volumes/Code_2TB/code/orp-web-app" }
  ]
}
```
""",
                        }
                    ],
                }
            raise AssertionError(f"unexpected path: {path}")

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_workspaces_tabs(
                    argparse.Namespace(
                        workspace_id="Main Cody 1",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["workspace_id"], "main-cody-1")
            self.assertEqual(payload["source"], "idea_bridge")
            self.assertEqual(payload["tabs"][0]["project_root"], "/Volumes/Code_2TB/code/orp")
            self.assertEqual(payload["tabs"][0]["codex_session_id"], "sess_123")

    def test_workspaces_tabs_uses_tabs_endpoint(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            if path == "/api/cli/workspaces?limit=200":
                return {
                    "ok": True,
                    "items": [
                        {
                            "workspace_id": "ws_orp_main",
                            "title": "ORP Main",
                        }
                    ],
                }
            if path == "/api/cli/workspaces/ws_orp_main":
                return {
                    "ok": True,
                    "workspace": {
                        "workspace_id": "ws_orp_main",
                        "title": "ORP Main",
                    },
                }
            self.assertEqual(path, "/api/cli/workspaces/ws_orp_main/tabs")
            return {
                "ok": True,
                "workspace_id": "ws_orp_main",
                "title": "ORP Main",
                "tabs": [
                    {
                        "tab_id": "tab_1",
                        "order_index": 0,
                        "title": "orp",
                        "project_root": "/Volumes/Code_2TB/code/orp",
                        "codex_session_id": "sess_123",
                        "tmux_session_name": "orp-orp-123456",
                        "status": "active",
                    }
                ],
            }

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_workspaces_tabs(
                    argparse.Namespace(
                        workspace_id="ws_orp_main",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["workspace_id"], "ws_orp_main")
            self.assertEqual(payload["tabs"][0]["project_root"], "/Volumes/Code_2TB/code/orp")

    def test_workspaces_push_state_posts_json_file_payload(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            return {"ok": True}

        module._request_hosted_json = fake_request_hosted_json

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as td:
            self._prepare_session(module, td)
            state_path = Path(td) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "state_version": 3,
                        "snapshot_id": "snapshot_abc",
                        "updated_at_utc": "2026-03-29T12:00:00Z",
                        "tab_count": 1,
                        "tabs": [
                            {
                                "tab_id": "tab_1",
                                "order_index": 0,
                                "project_root": "/Volumes/Code_2TB/code/orp",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_workspaces_push_state(
                    argparse.Namespace(
                        workspace_id="ws_orp_main",
                        state_file=str(state_path),
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(calls[0][0], "POST")
            self.assertEqual(calls[0][1], "/api/cli/workspaces/ws_orp_main/state")
            assert calls[0][2] is not None
            self.assertEqual(calls[0][2]["snapshot_id"], "snapshot_abc")


if __name__ == "__main__":
    unittest.main()
