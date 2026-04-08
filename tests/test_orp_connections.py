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
from contextlib import redirect_stdout
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_connections_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpConnectionsTests(unittest.TestCase):
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

    def _connections_env(self, td: str) -> dict[str, str]:
        return {
            "ORP_CONNECTIONS_REGISTRY_PATH": str(Path(td) / "connections.json"),
        }

    def test_providers_add_show_update_remove_connection(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env = self._connections_env(td)

            providers_proc = self.run_cli("connections", "providers", "--json", env=env)
            self.assertEqual(providers_proc.returncode, 0, msg=providers_proc.stderr + "\n" + providers_proc.stdout)
            providers_payload = json.loads(providers_proc.stdout)
            providers = {row["provider"] for row in providers_payload["providers"]}
            self.assertIn("github", providers)
            self.assertIn("zenodo", providers)
            self.assertIn("openalex", providers)
            self.assertIn("custom", providers)

            add_proc = self.run_cli(
                "connections",
                "add",
                "github-main",
                "--provider",
                "github",
                "--label",
                "GitHub Main",
                "--account",
                "cody",
                "--organization",
                "sproutseeds",
                "--auth-secret-alias",
                "github-main",
                "--secret-binding",
                "releases=github-releases",
                "--secret-binding",
                "issues=github-issues",
                "--capability",
                "repo-read",
                "--capability",
                "repo-write",
                "--capability",
                "issues",
                "--tag",
                "publishing",
                "--notes",
                "Primary code host and showcase surface.",
                "--json",
                env=env,
            )
            self.assertEqual(add_proc.returncode, 0, msg=add_proc.stderr + "\n" + add_proc.stdout)
            add_payload = json.loads(add_proc.stdout)
            self.assertEqual(add_payload["connection"]["provider"], "github")
            self.assertEqual(add_payload["connection"]["auth_secret_alias"], "github-main")
            self.assertEqual(add_payload["connection"]["kind"], "code_host")
            self.assertEqual(
                add_payload["connection"]["secret_bindings"],
                [
                    {"binding_id": "primary", "label": "Primary", "secret_alias": "github-main", "auth_kind": "token"},
                    {"binding_id": "releases", "label": "releases", "secret_alias": "github-releases", "auth_kind": "token"},
                    {"binding_id": "issues", "label": "issues", "secret_alias": "github-issues", "auth_kind": "token"},
                ],
            )

            show_proc = self.run_cli("connections", "show", "github-main", "--json", env=env)
            self.assertEqual(show_proc.returncode, 0, msg=show_proc.stderr + "\n" + show_proc.stdout)
            show_payload = json.loads(show_proc.stdout)
            self.assertEqual(show_payload["connection"]["organization"], "sproutseeds")
            self.assertEqual(show_payload["connection"]["capabilities"], ["repo-read", "repo-write", "issues"])
            self.assertEqual(show_payload["connection"]["secret_bindings"][1]["binding_id"], "releases")
            self.assertEqual(show_payload["connection"]["secret_bindings"][1]["secret_alias"], "github-releases")

            update_proc = self.run_cli(
                "connections",
                "update",
                "github-main",
                "--status",
                "paused",
                "--secret-binding",
                "primary=github-main-v2",
                "--secret-binding",
                "archive=github-archive",
                "--capability",
                "repo-read",
                "--capability",
                "releases",
                "--tag",
                "archive",
                "--json",
                env=env,
            )
            self.assertEqual(update_proc.returncode, 0, msg=update_proc.stderr + "\n" + update_proc.stdout)
            update_payload = json.loads(update_proc.stdout)
            self.assertEqual(update_payload["connection"]["status"], "paused")
            self.assertEqual(update_payload["connection"]["capabilities"], ["repo-read", "releases"])
            self.assertEqual(update_payload["connection"]["tags"], ["archive"])
            self.assertEqual(update_payload["connection"]["auth_secret_alias"], "github-main-v2")
            self.assertEqual(
                update_payload["connection"]["secret_bindings"],
                [
                    {"binding_id": "primary", "label": "primary", "secret_alias": "github-main-v2", "auth_kind": "token"},
                    {"binding_id": "archive", "label": "archive", "secret_alias": "github-archive", "auth_kind": "token"},
                ],
            )

            list_proc = self.run_cli("connections", "list", "--json", env=env)
            self.assertEqual(list_proc.returncode, 0, msg=list_proc.stderr + "\n" + list_proc.stdout)
            list_payload = json.loads(list_proc.stdout)
            self.assertEqual(len(list_payload["connections"]), 1)
            self.assertEqual(list_payload["connections"][0]["connection_id"], "github-main")
            self.assertEqual(list_payload["connections"][0]["secret_bindings"][0]["secret_alias"], "github-main-v2")

            remove_proc = self.run_cli("connections", "remove", "github-main", "--json", env=env)
            self.assertEqual(remove_proc.returncode, 0, msg=remove_proc.stderr + "\n" + remove_proc.stdout)
            remove_payload = json.loads(remove_proc.stdout)
            self.assertEqual(remove_payload["connection"]["connection_id"], "github-main")

            list_after_remove = self.run_cli("connections", "list", "--json", env=env)
            self.assertEqual(list_after_remove.returncode, 0, msg=list_after_remove.stderr + "\n" + list_after_remove.stdout)
            self.assertEqual(json.loads(list_after_remove.stdout)["connections"], [])


class HostedConnectionsMirrorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_xdg = os.environ.get("XDG_CONFIG_HOME")
        self._old_registry = os.environ.get("ORP_CONNECTIONS_REGISTRY_PATH")
        self.addCleanup(self._restore_env)

    def _restore_env(self) -> None:
        if self._old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self._old_xdg
        if self._old_registry is None:
            os.environ.pop("ORP_CONNECTIONS_REGISTRY_PATH", None)
        else:
            os.environ["ORP_CONNECTIONS_REGISTRY_PATH"] = self._old_registry

    def _prepare_env(self, module, td: str) -> Path:
        os.environ["XDG_CONFIG_HOME"] = td
        registry_path = Path(td) / "connections.json"
        os.environ["ORP_CONNECTIONS_REGISTRY_PATH"] = str(registry_path)
        module._save_hosted_session(
            {
                "base_url": "https://orp.earth",
                "email": "cody@example.com",
                "token": "tok_live_123",
                "user": {"id": "user_123", "email": "cody@example.com", "name": "Cody"},
                "pending_verification": None,
            }
        )
        return registry_path

    def test_sync_creates_hosted_connections_registry(self) -> None:
        module = load_cli_module()

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            if method == "GET" and path == "/api/cli/ideas?limit=200":
                return {"ok": True, "ideas": []}
            if method == "POST" and path == "/api/cli/ideas":
                self.assertEqual(body["title"], "ORP Connections")
                self.assertEqual(body["linkLabel"], "orp-connections")
                self.assertIn("```orp-connections", str(body["notes"]))
                self.assertIn("github-main", str(body["notes"]))
                return {
                    "ok": True,
                    "id": "idea_conn_123",
                    "title": "ORP Connections",
                    "notes": body["notes"],
                    "visibility": "private",
                    "updatedAt": "2026-04-07T14:00:00Z",
                }
            raise AssertionError(f"unexpected request: {method} {path}")

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td:
            registry_path = self._prepare_env(module, td)
            module._save_connections_registry(
                {
                    "schema_version": module.CONNECTIONS_REGISTRY_SCHEMA_VERSION,
                    "hosted_mirror": {},
                    "connections": [
                        {
                            "connection_id": "github-main",
                            "provider": "github",
                            "label": "GitHub Main",
                            "kind": "code_host",
                            "account": "cody",
                            "organization": "sproutseeds",
                            "url": "https://github.com/cody",
                            "auth_secret_alias": "github-main",
                            "auth_kind": "token",
                            "secret_bindings": [
                                {"binding_id": "primary", "label": "Primary", "secret_alias": "github-main", "auth_kind": "token"},
                                {"binding_id": "releases", "label": "Releases", "secret_alias": "github-releases", "auth_kind": "token"},
                            ],
                            "capabilities": ["repo-read", "repo-write"],
                            "tags": ["publishing"],
                            "notes": "Primary GitHub surface.",
                            "status": "active",
                            "created_at_utc": "2026-04-07T13:00:00Z",
                            "updated_at_utc": "2026-04-07T13:00:00Z",
                        }
                    ],
                }
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_connections_sync(
                    argparse.Namespace(
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["hosted_mirror"]["idea_id"], "idea_conn_123")
            saved = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["hosted_mirror"]["idea_id"], "idea_conn_123")
            self.assertEqual(saved["connections"][0]["secret_bindings"][1]["secret_alias"], "github-releases")

    def test_pull_restores_connections_registry_from_hosted(self) -> None:
        module = load_cli_module()
        hosted_notes = """```orp-connections
{
  "version": "1",
  "connections": [
    {
      "connection_id": "zenodo-main",
      "provider": "zenodo",
      "label": "Zenodo Main",
      "kind": "research_archive",
      "account": "cody",
      "organization": "",
      "url": "https://zenodo.org",
      "auth_secret_alias": "zenodo-main",
      "auth_kind": "token",
      "secret_bindings": [
        {"binding_id": "primary", "label": "Primary", "secret_alias": "zenodo-main", "auth_kind": "token"},
        {"binding_id": "sandbox", "label": "Sandbox", "secret_alias": "zenodo-sandbox", "auth_kind": "token"}
      ],
      "capabilities": ["publish", "doi"],
      "tags": ["papers"],
      "notes": "Main archive destination.",
      "status": "active",
      "created_at_utc": "2026-04-07T13:00:00Z",
      "updated_at_utc": "2026-04-07T14:00:00Z"
    }
  ]
}
```"""

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            self.assertEqual(method, "GET")
            if path == "/api/cli/ideas?limit=200":
                return {
                    "ok": True,
                    "ideas": [
                        {
                            "id": "idea_conn_123",
                            "title": "ORP Connections",
                            "notes": hosted_notes,
                            "visibility": "private",
                            "updatedAt": "2026-04-07T14:00:00Z",
                        }
                    ],
                }
            raise AssertionError(f"unexpected request: {method} {path}")

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td:
            registry_path = self._prepare_env(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_connections_pull(
                    argparse.Namespace(
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["hosted_mirror"]["idea_id"], "idea_conn_123")
            saved = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["connections"][0]["connection_id"], "zenodo-main")
            self.assertEqual(saved["connections"][0]["provider"], "zenodo")
            self.assertEqual(saved["connections"][0]["secret_bindings"][1]["secret_alias"], "zenodo-sandbox")


if __name__ == "__main__":
    unittest.main()
