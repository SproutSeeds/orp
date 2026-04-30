from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def _run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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


class OrpAgentsTests(unittest.TestCase):
    def test_agents_codex_audit_reports_missing_then_sync_bootstraps_global_layer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            codex_home = Path(td) / "codex-home"

            audit_before = _run_cli("agents", "codex", "audit", "--codex-home", str(codex_home), "--json")
            self.assertEqual(audit_before.returncode, 1, msg=audit_before.stderr + "\n" + audit_before.stdout)
            before_payload = json.loads(audit_before.stdout)
            self.assertFalse(before_payload["ok"])
            self.assertEqual(before_payload["checks"]["global_agents"]["status"], "needs_sync")
            self.assertIn("orp agents codex sync", before_payload["next_actions"][0])

            sync_proc = _run_cli("agents", "codex", "sync", "--codex-home", str(codex_home), "--json")
            self.assertEqual(sync_proc.returncode, 0, msg=sync_proc.stderr + "\n" + sync_proc.stdout)
            sync_payload = json.loads(sync_proc.stdout)
            self.assertTrue(sync_payload["ok"])

            agents_path = codex_home / "AGENTS.md"
            config_path = codex_home / "config.toml"
            hooks_path = codex_home / "hooks.json"
            script_path = codex_home / "hooks" / "orp_codex_session_start.py"
            self.assertTrue(agents_path.exists())
            self.assertTrue(config_path.exists())
            self.assertTrue(hooks_path.exists())
            self.assertTrue(script_path.exists())
            self.assertIn("<!-- ORP:CODEX_GLOBAL:BEGIN -->", agents_path.read_text(encoding="utf-8"))
            self.assertIn("codex_hooks = true", config_path.read_text(encoding="utf-8"))

            hooks_payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            self.assertIn("SessionStart", hooks_payload["hooks"])
            hook_commands = [
                handler["command"]
                for group in hooks_payload["hooks"]["SessionStart"]
                for handler in group.get("hooks", [])
            ]
            self.assertTrue(any(str(script_path) in command for command in hook_commands))
            self.assertIn("ORP-managed Codex SessionStart hook", script_path.read_text(encoding="utf-8"))

            audit_after = _run_cli("agents", "codex", "audit", "--codex-home", str(codex_home), "--json")
            self.assertEqual(audit_after.returncode, 0, msg=audit_after.stderr + "\n" + audit_after.stdout)
            after_payload = json.loads(audit_after.stdout)
            self.assertTrue(after_payload["ok"])

    def test_agents_codex_sync_preserves_human_content_and_existing_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            codex_home = Path(td) / "codex-home"
            codex_home.mkdir(parents=True)
            (codex_home / "AGENTS.md").write_text(
                "# My Codex Defaults\n\nHuman preference that should stay.\n",
                encoding="utf-8",
            )
            (codex_home / "config.toml").write_text("[features]\njs_repl = true\n", encoding="utf-8")
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "/bin/true",
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            sync_proc = _run_cli("agents", "codex", "sync", "--codex-home", str(codex_home), "--json")
            self.assertEqual(sync_proc.returncode, 0, msg=sync_proc.stderr + "\n" + sync_proc.stdout)

            agents_text = (codex_home / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Human preference that should stay.", agents_text)
            self.assertIn("<!-- ORP:CODEX_GLOBAL:BEGIN -->", agents_text)

            config_text = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn("js_repl = true", config_text)
            self.assertIn("codex_hooks = true", config_text)

            hooks_payload = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
            self.assertIn("Stop", hooks_payload["hooks"])
            self.assertIn("SessionStart", hooks_payload["hooks"])

    def test_agents_root_set_creates_registry_and_umbrella_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            projects_root = temp_root / "projects"
            registry_path = temp_root / "agents.json"

            proc = _run_cli(
                "agents",
                "root",
                "set",
                str(projects_root),
                "--json",
                env={"ORP_AGENTS_REGISTRY_PATH": str(registry_path)},
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["projects_root"], str(projects_root.resolve()))
            self.assertTrue(registry_path.exists())
            self.assertEqual(payload["sync"]["role"], "umbrella")
            self.assertTrue((projects_root / "AGENTS.md").exists())
            self.assertTrue((projects_root / "CLAUDE.md").exists())

            agents_text = (projects_root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("shared parent for many projects", agents_text)
            self.assertIn("<!-- ORP:AGENT_GUIDE:BEGIN -->", agents_text)
            self.assertIn("<!-- ORP:BEGIN -->", agents_text)

    def test_agents_sync_preserves_existing_human_content_and_links_parent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            projects_root = temp_root / "projects"
            repo_root = projects_root / "demo-repo"
            repo_root.mkdir(parents=True, exist_ok=True)

            existing = (
                "# AGENTS.md\n\n"
                "Human intro that should stay.\n\n"
                "## Local Notes\n"
                "- Keep this custom section.\n"
            )
            (repo_root / "AGENTS.md").write_text(existing, encoding="utf-8")

            proc = _run_cli(
                "--repo-root",
                str(repo_root),
                "agents",
                "sync",
                "--projects-root",
                str(projects_root),
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["role"], "project")
            self.assertEqual(payload["parent_root"], str(projects_root.resolve()))

            agents_text = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Human intro that should stay.", agents_text)
            self.assertIn("## Local Notes", agents_text)
            self.assertIn("Parent umbrella root", agents_text)
            self.assertIn("Read the parent files for the high-level north star", agents_text)
            self.assertIn("<!-- ORP:AGENT_GUIDE:BEGIN -->", agents_text)
            self.assertIn("<!-- ORP:BEGIN -->", agents_text)
            self.assertTrue((repo_root / "CLAUDE.md").exists())

    def test_agents_audit_reports_missing_then_ok_after_sync(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            projects_root = temp_root / "projects"
            repo_root = projects_root / "demo-repo"
            repo_root.mkdir(parents=True, exist_ok=True)

            audit_before = _run_cli(
                "--repo-root",
                str(repo_root),
                "agents",
                "audit",
                "--projects-root",
                str(projects_root),
                "--json",
            )
            self.assertEqual(audit_before.returncode, 1, msg=audit_before.stderr + "\n" + audit_before.stdout)
            before_payload = json.loads(audit_before.stdout)
            self.assertFalse(before_payload["ok"])
            statuses = {row["status"] for row in before_payload["files"]}
            self.assertIn("missing", statuses)

            sync_proc = _run_cli(
                "--repo-root",
                str(repo_root),
                "agents",
                "sync",
                "--projects-root",
                str(projects_root),
                "--json",
            )
            self.assertEqual(sync_proc.returncode, 0, msg=sync_proc.stderr + "\n" + sync_proc.stdout)

            audit_after = _run_cli(
                "--repo-root",
                str(repo_root),
                "agents",
                "audit",
                "--projects-root",
                str(projects_root),
                "--json",
            )
            self.assertEqual(audit_after.returncode, 0, msg=audit_after.stderr + "\n" + audit_after.stdout)
            after_payload = json.loads(audit_after.stdout)
            self.assertTrue(after_payload["ok"])
            self.assertTrue(all(row["status"] == "ok" for row in after_payload["files"]))


if __name__ == "__main__":
    unittest.main()
