from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"
PACKAGE_JSON = REPO_ROOT / "package.json"
PACKAGE_METADATA = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
PACKAGE_VERSION = PACKAGE_METADATA["version"]
PACKAGE_NAME = PACKAGE_METADATA["name"]


class OrpAboutTests(unittest.TestCase):
    def test_about_json_reports_agent_discovery_surfaces(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(CLI), "about", "--json"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

        payload = json.loads(proc.stdout)
        self.assertEqual(payload["tool"]["name"], "orp")
        self.assertEqual(payload["tool"]["package"], PACKAGE_NAME)
        self.assertEqual(payload["tool"]["version"], PACKAGE_VERSION)
        self.assertTrue(payload["tool"]["agent_friendly"])
        self.assertEqual(payload["discovery"]["llms_txt"], "llms.txt")
        self.assertEqual(payload["discovery"]["start_here"], "docs/START_HERE.md")
        self.assertEqual(payload["discovery"]["agent_loop"], "docs/AGENT_LOOP.md")
        self.assertEqual(payload["discovery"]["discover"], "docs/DISCOVER.md")
        self.assertEqual(payload["discovery"]["exchange"], "docs/EXCHANGE.md")
        self.assertEqual(payload["schemas"]["packet"], "spec/v1/packet.schema.json")
        self.assertEqual(payload["schemas"]["kernel"], "spec/v1/kernel.schema.json")
        self.assertEqual(payload["schemas"]["kernel_proposal"], "spec/v1/kernel-proposal.schema.json")
        self.assertEqual(payload["schemas"]["kernel_extension"], "spec/v1/kernel-extension.schema.json")
        self.assertEqual(payload["schemas"]["youtube_source"], "spec/v1/youtube-source.schema.json")
        self.assertEqual(payload["schemas"]["exchange_report"], "spec/v1/exchange-report.schema.json")
        self.assertEqual(payload["schemas"]["link_project"], "spec/v1/link-project.schema.json")
        self.assertEqual(payload["schemas"]["link_session"], "spec/v1/link-session.schema.json")
        self.assertEqual(payload["schemas"]["runner_machine"], "spec/v1/runner-machine.schema.json")
        self.assertEqual(payload["schemas"]["runner_runtime"], "spec/v1/runner-runtime.schema.json")
        ability_ids = {row["id"] for row in payload["abilities"]}
        self.assertIn("kernel", ability_ids)
        self.assertIn("youtube", ability_ids)
        self.assertIn("workspace", ability_ids)
        self.assertIn("secrets", ability_ids)
        self.assertIn("linking", ability_ids)
        self.assertIn("runner", ability_ids)
        self.assertIn("maintenance", ability_ids)
        self.assertIn("schedule", ability_ids)
        self.assertIn("discover", ability_ids)
        self.assertIn("exchange", ability_ids)
        self.assertIn("collaborate", ability_ids)
        self.assertIn("governance", ability_ids)
        self.assertIn("frontier", ability_ids)
        self.assertIn("erdos", ability_ids)
        self.assertIn("packs", ability_ids)
        command_names = {row["name"] for row in payload["commands"]}
        self.assertIn("home", command_names)
        self.assertIn("about", command_names)
        self.assertIn("update", command_names)
        self.assertIn("maintenance_check", command_names)
        self.assertIn("maintenance_status", command_names)
        self.assertIn("maintenance_enable", command_names)
        self.assertIn("maintenance_disable", command_names)
        self.assertIn("schedule_add_codex", command_names)
        self.assertIn("schedule_list", command_names)
        self.assertIn("schedule_show", command_names)
        self.assertIn("schedule_run", command_names)
        self.assertIn("schedule_enable", command_names)
        self.assertIn("schedule_disable", command_names)
        self.assertIn("kernel_validate", command_names)
        self.assertIn("kernel_scaffold", command_names)
        self.assertIn("kernel_stats", command_names)
        self.assertIn("kernel_propose", command_names)
        self.assertIn("kernel_migrate", command_names)
        self.assertIn("youtube_inspect", command_names)
        self.assertIn("auth_login", command_names)
        self.assertIn("auth_verify", command_names)
        self.assertIn("auth_logout", command_names)
        self.assertIn("whoami", command_names)
        self.assertIn("mode_list", command_names)
        self.assertIn("mode_show", command_names)
        self.assertIn("mode_nudge", command_names)
        self.assertIn("secrets_list", command_names)
        self.assertIn("secrets_show", command_names)
        self.assertIn("secrets_add", command_names)
        self.assertIn("secrets_ensure", command_names)
        self.assertIn("secrets_keychain_list", command_names)
        self.assertIn("secrets_keychain_show", command_names)
        self.assertIn("secrets_sync_keychain", command_names)
        self.assertIn("secrets_update", command_names)
        self.assertIn("secrets_archive", command_names)
        self.assertIn("secrets_bind", command_names)
        self.assertIn("secrets_unbind", command_names)
        self.assertIn("secrets_resolve", command_names)
        self.assertIn("workspaces_list", command_names)
        self.assertIn("workspaces_show", command_names)
        self.assertIn("workspaces_tabs", command_names)
        self.assertIn("workspaces_timeline", command_names)
        self.assertIn("workspaces_add", command_names)
        self.assertIn("workspaces_update", command_names)
        self.assertIn("workspaces_push_state", command_names)
        self.assertIn("workspaces_add_event", command_names)
        self.assertIn("ideas_list", command_names)
        self.assertIn("idea_show", command_names)
        self.assertIn("idea_add", command_names)
        self.assertIn("idea_update", command_names)
        self.assertIn("idea_remove", command_names)
        self.assertIn("idea_restore", command_names)
        self.assertIn("feature_list", command_names)
        self.assertIn("feature_show", command_names)
        self.assertIn("feature_add", command_names)
        self.assertIn("feature_update", command_names)
        self.assertIn("feature_remove", command_names)
        self.assertIn("world_show", command_names)
        self.assertIn("world_bind", command_names)
        self.assertIn("link_project_bind", command_names)
        self.assertIn("link_project_show", command_names)
        self.assertIn("link_project_status", command_names)
        self.assertIn("link_project_unbind", command_names)
        self.assertIn("link_session_register", command_names)
        self.assertIn("link_session_list", command_names)
        self.assertIn("link_session_show", command_names)
        self.assertIn("link_session_set_primary", command_names)
        self.assertIn("link_session_archive", command_names)
        self.assertIn("link_session_unarchive", command_names)
        self.assertIn("link_session_remove", command_names)
        self.assertIn("link_session_import_rust", command_names)
        self.assertIn("link_status", command_names)
        self.assertIn("link_doctor", command_names)
        self.assertIn("runner_status", command_names)
        self.assertIn("runner_enable", command_names)
        self.assertIn("runner_disable", command_names)
        self.assertIn("runner_heartbeat", command_names)
        self.assertIn("runner_sync", command_names)
        self.assertIn("runner_work", command_names)
        self.assertIn("runner_cancel", command_names)
        self.assertIn("runner_retry", command_names)
        self.assertIn("checkpoint_queue", command_names)
        self.assertIn("checkpoint_create", command_names)
        self.assertIn("backup", command_names)
        self.assertIn("agent_work", command_names)
        self.assertIn("discover_profile_init", command_names)
        self.assertIn("discover_github_scan", command_names)
        self.assertIn("exchange_repo_synthesize", command_names)
        self.assertIn("collaborate_init", command_names)
        self.assertIn("collaborate_workflows", command_names)
        self.assertIn("collaborate_gates", command_names)
        self.assertIn("collaborate_run", command_names)
        self.assertIn("status", command_names)
        self.assertIn("branch_start", command_names)
        self.assertIn("ready", command_names)
        self.assertIn("doctor", command_names)
        self.assertIn("cleanup", command_names)
        self.assertIn("frontier_init", command_names)
        self.assertIn("frontier_state", command_names)
        self.assertIn("frontier_roadmap", command_names)
        self.assertIn("frontier_checklist", command_names)
        self.assertIn("frontier_stack", command_names)
        self.assertIn("frontier_add_version", command_names)
        self.assertIn("frontier_add_milestone", command_names)
        self.assertIn("frontier_add_phase", command_names)
        self.assertIn("frontier_set_live", command_names)
        self.assertIn("frontier_render", command_names)
        self.assertIn("frontier_doctor", command_names)
        self.assertIn("gate_run", command_names)
        self.assertIn("erdos_sync", command_names)
        self.assertIn("pack_install", command_names)
        self.assertIn("pack_fetch", command_names)
        json_commands = {row["name"] for row in payload["commands"] if row["json_output"]}
        self.assertIn("kernel_validate", json_commands)
        self.assertIn("update", json_commands)
        self.assertIn("maintenance_check", json_commands)
        self.assertIn("maintenance_status", json_commands)
        self.assertIn("maintenance_enable", json_commands)
        self.assertIn("maintenance_disable", json_commands)
        self.assertIn("schedule_add_codex", json_commands)
        self.assertIn("schedule_list", json_commands)
        self.assertIn("schedule_show", json_commands)
        self.assertIn("schedule_run", json_commands)
        self.assertIn("schedule_enable", json_commands)
        self.assertIn("schedule_disable", json_commands)
        self.assertIn("kernel_scaffold", json_commands)
        self.assertIn("kernel_stats", json_commands)
        self.assertIn("kernel_propose", json_commands)
        self.assertIn("kernel_migrate", json_commands)
        self.assertIn("youtube_inspect", json_commands)
        self.assertIn("home", json_commands)
        self.assertIn("auth_login", json_commands)
        self.assertIn("auth_verify", json_commands)
        self.assertIn("auth_logout", json_commands)
        self.assertIn("whoami", json_commands)
        self.assertIn("mode_list", json_commands)
        self.assertIn("mode_show", json_commands)
        self.assertIn("mode_nudge", json_commands)
        self.assertIn("secrets_list", json_commands)
        self.assertIn("secrets_show", json_commands)
        self.assertIn("secrets_add", json_commands)
        self.assertIn("secrets_ensure", json_commands)
        self.assertIn("secrets_keychain_list", json_commands)
        self.assertIn("secrets_keychain_show", json_commands)
        self.assertIn("secrets_sync_keychain", json_commands)
        self.assertIn("secrets_update", json_commands)
        self.assertIn("secrets_archive", json_commands)
        self.assertIn("secrets_bind", json_commands)
        self.assertIn("secrets_unbind", json_commands)
        self.assertIn("secrets_resolve", json_commands)
        self.assertIn("workspaces_list", json_commands)
        self.assertIn("workspaces_show", json_commands)
        self.assertIn("workspaces_tabs", json_commands)
        self.assertIn("workspaces_timeline", json_commands)
        self.assertIn("workspaces_add", json_commands)
        self.assertIn("workspaces_update", json_commands)
        self.assertIn("workspaces_push_state", json_commands)
        self.assertIn("workspaces_add_event", json_commands)
        self.assertIn("ideas_list", json_commands)
        self.assertIn("idea_show", json_commands)
        self.assertIn("idea_add", json_commands)
        self.assertIn("idea_update", json_commands)
        self.assertIn("idea_remove", json_commands)
        self.assertIn("idea_restore", json_commands)
        self.assertIn("feature_list", json_commands)
        self.assertIn("feature_show", json_commands)
        self.assertIn("feature_add", json_commands)
        self.assertIn("feature_update", json_commands)
        self.assertIn("feature_remove", json_commands)
        self.assertIn("world_show", json_commands)
        self.assertIn("world_bind", json_commands)
        self.assertIn("link_project_bind", json_commands)
        self.assertIn("link_project_show", json_commands)
        self.assertIn("link_project_status", json_commands)
        self.assertIn("link_project_unbind", json_commands)
        self.assertIn("link_session_register", json_commands)
        self.assertIn("link_session_list", json_commands)
        self.assertIn("link_session_show", json_commands)
        self.assertIn("link_session_set_primary", json_commands)
        self.assertIn("link_session_archive", json_commands)
        self.assertIn("link_session_unarchive", json_commands)
        self.assertIn("link_session_remove", json_commands)
        self.assertIn("link_session_import_rust", json_commands)
        self.assertIn("link_status", json_commands)
        self.assertIn("link_doctor", json_commands)
        self.assertIn("runner_status", json_commands)
        self.assertIn("runner_enable", json_commands)
        self.assertIn("runner_disable", json_commands)
        self.assertIn("runner_heartbeat", json_commands)
        self.assertIn("runner_sync", json_commands)
        self.assertIn("runner_work", json_commands)
        self.assertIn("runner_cancel", json_commands)
        self.assertIn("runner_retry", json_commands)
        self.assertIn("checkpoint_queue", json_commands)
        self.assertIn("checkpoint_create", json_commands)
        self.assertIn("backup", json_commands)
        self.assertIn("agent_work", json_commands)
        self.assertIn("discover_profile_init", json_commands)
        self.assertIn("discover_github_scan", json_commands)
        self.assertIn("exchange_repo_synthesize", json_commands)
        self.assertIn("collaborate_init", json_commands)
        self.assertIn("collaborate_workflows", json_commands)
        self.assertIn("collaborate_gates", json_commands)
        self.assertIn("collaborate_run", json_commands)
        self.assertIn("status", json_commands)
        self.assertIn("branch_start", json_commands)
        self.assertIn("ready", json_commands)
        self.assertIn("doctor", json_commands)
        self.assertIn("cleanup", json_commands)
        self.assertIn("frontier_init", json_commands)
        self.assertIn("frontier_state", json_commands)
        self.assertIn("frontier_roadmap", json_commands)
        self.assertIn("frontier_checklist", json_commands)
        self.assertIn("frontier_stack", json_commands)
        self.assertIn("frontier_add_version", json_commands)
        self.assertIn("frontier_add_milestone", json_commands)
        self.assertIn("frontier_add_phase", json_commands)
        self.assertIn("frontier_set_live", json_commands)
        self.assertIn("frontier_render", json_commands)
        self.assertIn("frontier_doctor", json_commands)
        self.assertIn("erdos_sync", json_commands)
        self.assertIn("pack_install", json_commands)
        self.assertIn("pack_fetch", json_commands)
        pack_ids = {row["id"] for row in payload["packs"]}
        self.assertIn("erdos-open-problems", pack_ids)
        self.assertIn("issue-smashers", pack_ids)

    def test_home_json_reports_repo_runtime_and_pack_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "home",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertEqual(payload["tool"]["version"], PACKAGE_VERSION)
            self.assertEqual(payload["repo"]["root_path"], str(root.resolve()))
            self.assertEqual(payload["repo"]["config_path"], "orp.yml")
            self.assertFalse(payload["repo"]["config_exists"])
            self.assertFalse(payload["runtime"]["state_exists"])
            self.assertFalse(payload["runtime"]["initialized"])
            pack_ids = {row["id"] for row in payload["packs"]}
            self.assertIn("issue-smashers", pack_ids)
            ability_ids = {row["id"] for row in payload["abilities"]}
            self.assertIn("workspace", ability_ids)
            self.assertIn("modes", ability_ids)
            self.assertIn("secrets", ability_ids)
            self.assertIn("schedule", ability_ids)
            self.assertIn("linking", ability_ids)
            self.assertIn("runner", ability_ids)
            self.assertIn("maintenance", ability_ids)
            self.assertIn("discover", ability_ids)
            self.assertIn("exchange", ability_ids)
            self.assertIn("collaborate", ability_ids)
            self.assertIn("governance", ability_ids)
            self.assertIn("frontier", ability_ids)
            commands = {row["command"] for row in payload["quick_actions"]}
            self.assertIn("orp auth login", commands)
            self.assertIn("orp whoami --json", commands)
            self.assertIn("orp mode nudge sleek-minimal-progressive --json", commands)
            self.assertIn("orp workspaces list --json", commands)
            self.assertIn("orp secrets list --json", commands)
            self.assertIn('orp secrets add --alias <alias> --label "<label>" --provider <provider>', commands)
            self.assertIn("orp secrets ensure --alias <alias> --provider <provider> --current-project --json", commands)
            self.assertIn("orp secrets keychain-list --json", commands)
            self.assertIn("orp secrets sync-keychain <alias-or-id> --json", commands)
            self.assertIn("orp secrets resolve --provider openai --reveal --local-first --json", commands)
            self.assertIn("orp youtube inspect https://www.youtube.com/watch?v=<video_id> --json", commands)
            self.assertIn("orp ideas list --json", commands)
            self.assertIn("orp link status --json", commands)
            self.assertIn("orp runner status --json", commands)
            self.assertIn("orp discover profile init --json", commands)
            self.assertIn("orp exchange repo synthesize /path/to/source --json", commands)
            self.assertIn("orp status --json", commands)
            self.assertIn("orp frontier init --program-id <program-id> --json", commands)
            self.assertIn("orp collaborate init", commands)
            self.assertIn("orp collaborate workflows --json", commands)
            self.assertIn("orp maintenance status --json", commands)
            self.assertIn("orp maintenance check --json", commands)
            self.assertIn("maintenance", payload)
            self.assertIn("check_due", payload["maintenance"])

    def test_home_json_initialized_repo_includes_backup_quick_action(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "init",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            home_proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "home",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(home_proc.returncode, 0, msg=home_proc.stderr + "\n" + home_proc.stdout)

            payload = json.loads(home_proc.stdout)
            commands = {row["command"] for row in payload["quick_actions"]}
            self.assertIn("orp kernel validate analysis/orp.kernel.task.yml --json", commands)
            self.assertIn("orp frontier state --json", commands)
            self.assertIn("orp frontier roadmap --json", commands)
            self.assertIn('orp backup -m "backup current work" --json', commands)

    def test_cli_without_args_shows_home_screen(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            self.assertIn(
                "Agent-first CLI for workspace ledgers, secrets, scheduling, governed execution, and research workflows.",
                proc.stdout,
            )
            self.assertIn("Daily Loop", proc.stdout)
            self.assertIn("Command Families", proc.stdout)
            self.assertIn("workspace", proc.stdout)
            self.assertIn("Collaboration", proc.stdout)
            self.assertIn("orp collaborate init", proc.stdout)
            self.assertIn("orp workspace tabs main", proc.stdout)
            self.assertIn("orp frontier init --program-id <program-id> --json", proc.stdout)
            self.assertIn("Quick Actions", proc.stdout)

    def test_secrets_help_teaches_interactive_and_stdin_flows(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(CLI), "secrets", "-h"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        self.assertIn("saved keys and tokens", proc.stdout)
        self.assertIn("Run `orp secrets add ...`", proc.stdout)
        self.assertIn("--value-stdin", proc.stdout)
        self.assertIn('orp secrets add --alias openai-primary --label "OpenAI Primary" --provider openai', proc.stdout)

    def test_gate_run_json_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = {
                "epistemic_status": {
                    "overall": "starter_scaffold",
                    "starter_scaffold": True,
                    "notes": ["starter lane"],
                },
                "profiles": {
                    "default": {
                        "packet_kind": "problem_scope",
                        "gate_ids": ["smoke"],
                    }
                },
                "gates": [
                    {
                        "id": "smoke",
                        "phase": "verification",
                        "command": "echo ORP_SMOKE",
                        "pass": {
                            "exit_codes": [0],
                            "stdout_must_contain": ["ORP_SMOKE"],
                        },
                        "evidence": {
                            "status": "starter_stub",
                            "note": "stub gate",
                            "paths": ["analysis/stub.txt"],
                        },
                    }
                ],
            }
            (root / "orp.sample.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "--config",
                    "orp.sample.json",
                    "gate",
                    "run",
                    "--profile",
                    "default",
                    "--run-id",
                    "run-json-gate",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertEqual(payload["run_id"], "run-json-gate")
            self.assertEqual(payload["overall"], "PASS")
            self.assertEqual(payload["gates_passed"], 1)
            self.assertEqual(payload["gates_failed"], 0)
            self.assertEqual(payload["gates_total"], 1)
            self.assertEqual(payload["run_record"], "orp/artifacts/run-json-gate/RUN.json")

            run_record = json.loads((root / payload["run_record"]).read_text(encoding="utf-8"))
            self.assertEqual(run_record["results"][0]["evidence_status"], "starter_stub")
            self.assertEqual(run_record["results"][0]["evidence_note"], "stub gate")
            self.assertEqual(
                run_record["results"][0]["evidence_paths"],
                ["analysis/stub.txt"],
            )
            self.assertEqual(run_record["epistemic_status"]["overall"], "starter_scaffold")
            self.assertTrue(run_record["epistemic_status"]["starter_scaffold"])
            self.assertEqual(run_record["epistemic_status"]["stub_gates"], ["smoke"])

    def test_gate_run_generates_distinct_default_run_ids_back_to_back(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = {
                "profiles": {
                    "default": {
                        "packet_kind": "problem_scope",
                        "gate_ids": ["smoke"],
                    }
                },
                "gates": [
                    {
                        "id": "smoke",
                        "phase": "verification",
                        "command": "echo ORP_SMOKE",
                        "pass": {
                            "exit_codes": [0],
                            "stdout_must_contain": ["ORP_SMOKE"],
                        },
                    }
                ],
            }
            (root / "orp.sample.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            run_ids: list[str] = []
            for _ in range(2):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(CLI),
                        "--repo-root",
                        str(root),
                        "--config",
                        "orp.sample.json",
                        "gate",
                        "run",
                        "--profile",
                        "default",
                        "--json",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=str(REPO_ROOT),
                )
                self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
                payload = json.loads(proc.stdout)
                run_ids.append(str(payload["run_id"]))

            self.assertEqual(len(run_ids), 2)
            self.assertNotEqual(run_ids[0], run_ids[1])


if __name__ == "__main__":
    unittest.main()
