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
    spec = importlib.util.spec_from_file_location("orp_cli_opportunities_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpOpportunitiesTests(unittest.TestCase):
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

    def _opportunities_env(self, td: str) -> dict[str, str]:
        return {
            "ORP_OPPORTUNITIES_REGISTRY_PATH": str(Path(td) / "opportunities.json"),
        }

    def test_create_add_show_update_and_remove_opportunity_item(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env = self._opportunities_env(td)

            create_proc = self.run_cli(
                "opportunities",
                "create",
                "main-opportunities",
                "--label",
                "Main Opportunities",
                "--description",
                "Contests, programs, and grants worth tracking.",
                "--json",
                env=env,
            )
            self.assertEqual(create_proc.returncode, 0, msg=create_proc.stderr + "\n" + create_proc.stdout)
            create_payload = json.loads(create_proc.stdout)
            self.assertEqual(create_payload["board"]["title"], "main-opportunities")
            self.assertEqual(create_payload["board"]["label"], "Main Opportunities")

            add_proc = self.run_cli(
                "opportunities",
                "add",
                "main-opportunities",
                "--title",
                "Vision Prize",
                "--kind",
                "contest",
                "--section",
                "ocular-longevity",
                "--priority",
                "high",
                "--status",
                "active",
                "--url",
                "https://example.com/vision-prize",
                "--summary",
                "Prize program around retinal longevity and translation.",
                "--notes",
                "Needs a quick competitive scan.",
                "--tag",
                "ocular",
                "--tag",
                "retinal",
                "--json",
                env=env,
            )
            self.assertEqual(add_proc.returncode, 0, msg=add_proc.stderr + "\n" + add_proc.stdout)
            add_payload = json.loads(add_proc.stdout)
            self.assertEqual(add_payload["item"]["item_id"], "vision-prize")
            self.assertEqual(add_payload["item"]["kind"], "contest")
            self.assertEqual(add_payload["item"]["section"], "ocular-longevity")
            self.assertEqual(add_payload["item"]["priority"], "high")
            self.assertEqual(add_payload["item"]["tags"], ["ocular", "retinal"])

            show_proc = self.run_cli("opportunities", "show", "main-opportunities", "--json", env=env)
            self.assertEqual(show_proc.returncode, 0, msg=show_proc.stderr + "\n" + show_proc.stdout)
            show_payload = json.loads(show_proc.stdout)
            self.assertEqual(show_payload["board"]["item_count"], 1)
            self.assertEqual(show_payload["items"][0]["item_id"], "vision-prize")
            self.assertEqual(show_payload["items"][0]["url"], "https://example.com/vision-prize")

            update_proc = self.run_cli(
                "opportunities",
                "update",
                "main-opportunities",
                "vision-prize",
                "--status",
                "submitted",
                "--priority",
                "critical",
                "--tag",
                "ocular",
                "--tag",
                "longevity",
                "--json",
                env=env,
            )
            self.assertEqual(update_proc.returncode, 0, msg=update_proc.stderr + "\n" + update_proc.stdout)
            update_payload = json.loads(update_proc.stdout)
            self.assertEqual(update_payload["item"]["status"], "submitted")
            self.assertEqual(update_payload["item"]["priority"], "critical")
            self.assertEqual(update_payload["item"]["tags"], ["ocular", "longevity"])

            list_proc = self.run_cli("opportunities", "list", "--json", env=env)
            self.assertEqual(list_proc.returncode, 0, msg=list_proc.stderr + "\n" + list_proc.stdout)
            list_payload = json.loads(list_proc.stdout)
            self.assertEqual(len(list_payload["boards"]), 1)
            self.assertEqual(list_payload["boards"][0]["title"], "main-opportunities")
            self.assertEqual(list_payload["boards"][0]["item_count"], 1)
            self.assertEqual(list_payload["boards"][0]["kind_counts"]["contest"], 1)
            self.assertEqual(list_payload["boards"][0]["sections"], ["ocular-longevity"])

            focus_proc = self.run_cli(
                "opportunities",
                "focus",
                "main-opportunities",
                "--priority-at-least",
                "critical",
                "--json",
                env=env,
            )
            self.assertEqual(focus_proc.returncode, 0, msg=focus_proc.stderr + "\n" + focus_proc.stdout)
            focus_payload = json.loads(focus_proc.stdout)
            self.assertEqual(len(focus_payload["items"]), 1)
            self.assertEqual(focus_payload["items"][0]["item_id"], "vision-prize")
            self.assertEqual(focus_payload["items"][0]["priority"], "critical")

            remove_proc = self.run_cli(
                "opportunities",
                "remove",
                "main-opportunities",
                "vision-prize",
                "--json",
                env=env,
            )
            self.assertEqual(remove_proc.returncode, 0, msg=remove_proc.stderr + "\n" + remove_proc.stdout)
            remove_payload = json.loads(remove_proc.stdout)
            self.assertEqual(remove_payload["removed_item"]["item_id"], "vision-prize")

            show_after_remove = self.run_cli("opportunities", "show", "main-opportunities", "--json", env=env)
            self.assertEqual(show_after_remove.returncode, 0, msg=show_after_remove.stderr + "\n" + show_after_remove.stdout)
            after_payload = json.loads(show_after_remove.stdout)
            self.assertEqual(after_payload["board"]["item_count"], 0)
            self.assertEqual(after_payload["items"], [])


class HostedOpportunityMirrorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_xdg = os.environ.get("XDG_CONFIG_HOME")
        self._old_registry = os.environ.get("ORP_OPPORTUNITIES_REGISTRY_PATH")
        self.addCleanup(self._restore_env)

    def _restore_env(self) -> None:
        if self._old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self._old_xdg
        if self._old_registry is None:
            os.environ.pop("ORP_OPPORTUNITIES_REGISTRY_PATH", None)
        else:
            os.environ["ORP_OPPORTUNITIES_REGISTRY_PATH"] = self._old_registry

    def _prepare_env(self, module, td: str) -> Path:
        os.environ["XDG_CONFIG_HOME"] = td
        registry_path = Path(td) / "opportunities.json"
        os.environ["ORP_OPPORTUNITIES_REGISTRY_PATH"] = str(registry_path)
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

    def test_sync_creates_hosted_mirror_and_persists_metadata(self) -> None:
        module = load_cli_module()
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request_hosted_json(*, base_url, path, token, method="GET", body=None):
            self.assertEqual(base_url, "https://orp.earth")
            self.assertEqual(token, "tok_live_123")
            calls.append((method, path, body))
            if method == "GET" and path == "/api/cli/ideas?limit=200":
                return {"ok": True, "ideas": []}
            if method == "POST" and path == "/api/cli/ideas":
                self.assertEqual(body["title"], "ORP Opportunities · main-opportunities")
                self.assertEqual(body["linkLabel"], "orp-opportunities")
                self.assertIn("```orp-opportunities", str(body["notes"]))
                self.assertIn("Vision Prize", str(body["notes"]))
                return {
                    "ok": True,
                    "id": "idea_opp_123",
                    "title": "ORP Opportunities · main-opportunities",
                    "notes": body["notes"],
                    "visibility": "private",
                    "updatedAt": "2026-04-07T12:00:00Z",
                }
            raise AssertionError(f"unexpected hosted request: {method} {path}")

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td:
            registry_path = self._prepare_env(module, td)
            registry = {
                "schema_version": module.OPPORTUNITIES_REGISTRY_SCHEMA_VERSION,
                "boards": [
                    {
                        "board_id": "main-opportunities",
                        "title": "main-opportunities",
                        "label": "Main Opportunities",
                        "description": "Tracked openings worth pursuing.",
                        "created_at_utc": "2026-04-07T11:00:00Z",
                        "updated_at_utc": "2026-04-07T11:00:00Z",
                        "items": [
                            {
                                "item_id": "vision-prize",
                                "title": "Vision Prize",
                                "kind": "contest",
                                "section": "ocular-longevity",
                                "priority": "high",
                                "status": "active",
                                "summary": "Retinal longevity contest.",
                                "notes": "",
                                "url": "https://example.com/vision-prize",
                                "tags": ["ocular"],
                                "created_at_utc": "2026-04-07T11:00:00Z",
                                "updated_at_utc": "2026-04-07T11:00:00Z",
                            }
                        ],
                    }
                ],
            }
            module._save_opportunities_registry(registry)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_opportunities_sync(
                    argparse.Namespace(
                        board_ref="main-opportunities",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["hosted"]["idea_id"], "idea_opp_123")
            self.assertEqual(payload["hosted"]["board_id"], "main-opportunities")
            saved = json.loads(registry_path.read_text(encoding="utf-8"))
            mirror = saved["boards"][0]["hosted_mirror"]
            self.assertEqual(mirror["idea_id"], "idea_opp_123")
            self.assertEqual(mirror["idea_title"], "ORP Opportunities · main-opportunities")
            self.assertEqual(calls[-1][0], "POST")
            self.assertEqual(calls[-1][1], "/api/cli/ideas")

    def test_pull_restores_local_board_from_hosted_mirror(self) -> None:
        module = load_cli_module()
        hosted_notes = """```orp-opportunities
{
  "version": "1",
  "boardId": "main-opportunities",
  "title": "main-opportunities",
  "label": "Main Opportunities",
  "description": "Tracked openings worth pursuing.",
  "createdAt": "2026-04-07T11:00:00Z",
  "updatedAt": "2026-04-07T12:00:00Z",
  "items": [
    {
      "item_id": "vision-prize",
      "title": "Vision Prize",
      "kind": "contest",
      "section": "ocular-longevity",
      "priority": "high",
      "status": "active",
      "summary": "Retinal longevity contest.",
      "notes": "",
      "url": "https://example.com/vision-prize",
      "tags": ["ocular"],
      "created_at_utc": "2026-04-07T11:00:00Z",
      "updated_at_utc": "2026-04-07T12:00:00Z"
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
                            "id": "idea_opp_123",
                            "title": "ORP Opportunities · main-opportunities",
                            "notes": hosted_notes,
                            "visibility": "private",
                            "updatedAt": "2026-04-07T12:00:00Z",
                        }
                    ],
                }
            raise AssertionError(f"unexpected hosted request: {method} {path}")

        module._request_hosted_json = fake_request_hosted_json

        with tempfile.TemporaryDirectory() as td:
            registry_path = self._prepare_env(module, td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_opportunities_pull(
                    argparse.Namespace(
                        board_ref="main-opportunities",
                        base_url="",
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["board"]["title"], "main-opportunities")
            self.assertEqual(payload["hosted"]["idea_id"], "idea_opp_123")
            saved = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["boards"][0]["board_id"], "main-opportunities")
            self.assertEqual(saved["boards"][0]["items"][0]["item_id"], "vision-prize")
            self.assertEqual(saved["boards"][0]["hosted_mirror"]["idea_id"], "idea_opp_123")


if __name__ == "__main__":
    unittest.main()
