from __future__ import annotations

import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


class OrpAgendaTests(unittest.TestCase):
    def run_cli(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        base_env = os.environ.copy()
        if env:
            base_env.update(env)
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=base_env,
        )

    def _agenda_env(self, td: str) -> dict[str, str]:
        root = Path(td)
        return {
            "ORP_AGENDA_REGISTRY_PATH": str(root / "agenda.json"),
            "ORP_CONNECTIONS_REGISTRY_PATH": str(root / "connections.json"),
            "ORP_OPPORTUNITIES_REGISTRY_PATH": str(root / "opportunities.json"),
            "ORP_SCHEDULE_REGISTRY_PATH": str(root / "schedules.json"),
            "ORP_SCHEDULE_LAUNCH_AGENTS_DIR": str(root / "LaunchAgents"),
            "ORP_SCHEDULE_LOGS_DIR": str(root / "schedule-logs"),
            "ORP_LAUNCH_RUNTIME_ROOT": str(root / "launch-runtime"),
            "ORP_SCHEDULE_ALLOW_NON_DARWIN": "1",
            "ORP_SCHEDULE_SKIP_LAUNCHCTL": "1",
        }

    def test_refresh_with_fixtures_persists_actions_and_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env = self._agenda_env(td)

            (root / "connections.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "hosted_mirror": {},
                        "connections": [
                            {
                                "connection_id": "github-main",
                                "provider": "github",
                                "label": "GitHub Main",
                                "kind": "code_host",
                                "account": "cody",
                                "organization": "sproutseeds",
                                "url": "https://github.com/sproutseeds",
                                "auth_secret_alias": "github-main",
                                "auth_kind": "token",
                                "secret_bindings": [
                                    {
                                        "binding_id": "primary",
                                        "label": "Primary",
                                        "secret_alias": "github-main",
                                        "auth_kind": "token",
                                    }
                                ],
                                "capabilities": ["repo-read", "prs", "issues"],
                                "tags": ["publishing"],
                                "notes": "",
                                "status": "active",
                                "created_at_utc": "2026-04-08T10:00:00Z",
                                "updated_at_utc": "2026-04-08T10:00:00Z",
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "opportunities.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "boards": [
                            {
                                "board_id": "main-opportunities",
                                "title": "main-opportunities",
                                "label": "Main Opportunities",
                                "description": "Tracked openings.",
                                "created_at_utc": "2026-04-08T10:00:00Z",
                                "updated_at_utc": "2026-04-08T10:00:00Z",
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
                                        "created_at_utc": "2026-04-08T10:00:00Z",
                                        "updated_at_utc": "2026-04-08T10:00:00Z",
                                    }
                                ],
                                "hosted_mirror": {},
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            workspace_fixture = root / "workspace-tabs.json"
            workspace_fixture.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "workspace": {"title": "main"},
                        "tabCount": 2,
                        "tabs": [
                            {
                                "index": 1,
                                "title": "orp",
                                "path": str(REPO_ROOT),
                                "resume": f"cd '{REPO_ROOT}' && codex resume 019d-demo-orp",
                                "remoteUrl": "git@github.com:SproutSeeds/orp.git",
                                "bootstrapCommand": "npm install",
                            },
                            {
                                "index": 2,
                                "title": "orp-web-app",
                                "path": "/Volumes/Code_2TB/code/orp-web-app",
                                "resume": "cd '/Volumes/Code_2TB/code/orp-web-app' && claude --resume 469d99b2-2997-42bf-a8f5-3812c808ef29",
                                "remoteUrl": "git@github.com:SproutSeeds/orp-web-app.git",
                                "bootstrapCommand": "npm install",
                            },
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            github_fixture = root / "github-notifications.json"
            github_fixture.write_text(
                json.dumps(
                    [
                        {
                            "id": "1",
                            "reason": "review_requested",
                            "unread": True,
                            "updated_at": "2026-04-08T11:00:00Z",
                            "repository": {"full_name": "SproutSeeds/orp-web-app", "name": "orp-web-app"},
                            "subject": {
                                "title": "Review the agenda refresh UX",
                                "type": "PullRequest",
                                "url": "https://api.github.com/repos/SproutSeeds/orp-web-app/pulls/52",
                            },
                        }
                    ],
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            response_fixture = root / "agenda-response.json"
            response_fixture.write_text(
                json.dumps(
                    {
                        "north_star": "Advance the ORP and ocular-controller ecosystems with the highest leverage moves first.",
                        "actions": [
                            {
                                "title": "Reply to the review-requested ORP web app PR",
                                "kind": "review-request",
                                "priority": "critical",
                                "status": "active",
                                "project": "orp-web-app",
                                "source_kind": "github",
                                "source_ref": "SproutSeeds/orp-web-app#52",
                                "url": "https://github.com/SproutSeeds/orp-web-app/pull/52",
                                "why": "A collaborator is waiting on review feedback in active product work.",
                                "next_step": "Open the PR, address the requested feedback, and reply on the thread.",
                                "rank": 1,
                            }
                        ],
                        "suggestions": [
                            {
                                "title": "Turn the top ocular opportunities into a shortlist with next artifacts",
                                "kind": "expand",
                                "priority": "high",
                                "status": "active",
                                "project": "longgevity-research",
                                "source_kind": "opportunities",
                                "source_ref": "main-opportunities",
                                "url": "https://example.com/vision-prize",
                                "why": "The current opportunity board already shows active retinal longevity openings worth converting into a tighter plan.",
                                "next_step": "Rank the top three openings and note the next artifact required for each.",
                                "rank": 1,
                            }
                        ],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            refresh_proc = self.run_cli(
                "agenda",
                "refresh",
                "--workspace-fixture",
                str(workspace_fixture),
                "--github-fixture",
                str(github_fixture),
                "--response-fixture",
                str(response_fixture),
                "--json",
                env=env,
            )
            self.assertEqual(refresh_proc.returncode, 0, msg=refresh_proc.stderr + "\n" + refresh_proc.stdout)
            refresh_payload = json.loads(refresh_proc.stdout)
            self.assertEqual(refresh_payload["north_star_source"], "inferred")
            self.assertEqual(len(refresh_payload["actions"]), 1)
            self.assertEqual(len(refresh_payload["suggestions"]), 1)
            self.assertEqual(refresh_payload["actions"][0]["project"], "orp-web-app")
            self.assertEqual(refresh_payload["suggestions"][0]["source_ref"], "main-opportunities")

            saved = json.loads((root / "agenda.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["actions"][0]["title"], "Reply to the review-requested ORP web app PR")
            self.assertEqual(saved["suggestions"][0]["title"], "Turn the top ocular opportunities into a shortlist with next artifacts")
            self.assertEqual(saved["refresh_context"]["github"]["notification_count"], 1)
            self.assertEqual(saved["refresh_context"]["workspace"]["tab_count"], 2)

            actions_proc = self.run_cli("agenda", "actions", "--json", env=env)
            self.assertEqual(actions_proc.returncode, 0, msg=actions_proc.stderr + "\n" + actions_proc.stdout)
            actions_payload = json.loads(actions_proc.stdout)
            self.assertEqual(actions_payload["items"][0]["title"], "Reply to the review-requested ORP web app PR")

            suggestions_proc = self.run_cli("agenda", "suggestions", "--json", env=env)
            self.assertEqual(suggestions_proc.returncode, 0, msg=suggestions_proc.stderr + "\n" + suggestions_proc.stdout)
            suggestions_payload = json.loads(suggestions_proc.stdout)
            self.assertEqual(
                suggestions_payload["items"][0]["title"],
                "Turn the top ocular opportunities into a shortlist with next artifacts",
            )

            focus_proc = self.run_cli("agenda", "focus", "--json", env=env)
            self.assertEqual(focus_proc.returncode, 0, msg=focus_proc.stderr + "\n" + focus_proc.stdout)
            focus_payload = json.loads(focus_proc.stdout)
            self.assertEqual(len(focus_payload["actions"]), 1)
            self.assertEqual(len(focus_payload["suggestions"]), 1)

    def test_set_north_star_persists_for_future_refreshes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env = self._agenda_env(td)
            proc = self.run_cli(
                "agenda",
                "set-north-star",
                "Advance the ocular controller and ORP ecosystems together.",
                "--json",
                env=env,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["north_star_source"], "explicit")
            saved = json.loads((Path(td) / "agenda.json").read_text(encoding="utf-8"))
            self.assertEqual(
                saved["north_star"],
                "Advance the ocular controller and ORP ecosystems together.",
            )

    def test_refresh_status_is_disabled_by_default_until_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env = self._agenda_env(td)
            proc = self.run_cli("agenda", "refresh-status", "--json", env=env)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["enabled"])
            self.assertFalse(payload["fully_enabled"])
            self.assertEqual(payload["defaults"]["morning"], "09:00")
            self.assertEqual(payload["defaults"]["afternoon"], "14:00")
            self.assertEqual(payload["defaults"]["evening"], "19:00")
            self.assertEqual([row["window"] for row in payload["windows"]], ["morning", "afternoon", "evening"])
            self.assertTrue(all(not row["enabled"] for row in payload["windows"]))

    def test_enable_refreshes_creates_three_opt_in_schedule_jobs_with_custom_times(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env = self._agenda_env(td)
            proc = self.run_cli(
                "agenda",
                "enable-refreshes",
                "--workspace-ref",
                "main",
                "--board-ref",
                "main-opportunities",
                "--morning",
                "08:30",
                "--afternoon",
                "13:15",
                "--evening",
                "18:45",
                "--json",
                env=env,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(len(payload["windows"]), 3)
            self.assertEqual([row["time"] for row in payload["windows"]], ["08:30", "13:15", "18:45"])

            registry = json.loads((Path(td) / "schedules.json").read_text(encoding="utf-8"))
            jobs = registry["jobs"]
            self.assertEqual([job["name"] for job in jobs], ["agenda-refresh-morning", "agenda-refresh-afternoon", "agenda-refresh-evening"])
            self.assertTrue(all(job["kind"] == "agenda_refresh" for job in jobs))
            self.assertEqual(jobs[0]["schedule"], {"hour": 8, "minute": 30})
            self.assertEqual(jobs[1]["schedule"], {"hour": 13, "minute": 15})
            self.assertEqual(jobs[2]["schedule"], {"hour": 18, "minute": 45})
            self.assertEqual(jobs[0]["config"]["workspace_ref"], "main")
            self.assertEqual(jobs[0]["config"]["board_ref"], "main-opportunities")
            self.assertIn("orp agenda refresh", jobs[0]["config"]["command_preview"])

            plist_path = Path(payload["windows"][0]["job"]["plist_path"])
            self.assertTrue(plist_path.exists())
            with plist_path.open("rb") as handle:
                plist_payload = plistlib.load(handle)
            self.assertEqual(plist_payload["StartCalendarInterval"]["Hour"], 8)
            self.assertEqual(plist_payload["StartCalendarInterval"]["Minute"], 30)

            status_proc = self.run_cli("agenda", "refresh-status", "--json", env=env)
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            status_payload = json.loads(status_proc.stdout)
            self.assertTrue(status_payload["enabled"])
            self.assertTrue(status_payload["fully_enabled"])
            self.assertEqual([row["configured_time"] for row in status_payload["windows"]], ["08:30", "13:15", "18:45"])

    def test_disable_refreshes_turns_off_all_windows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env = self._agenda_env(td)
            enable_proc = self.run_cli("agenda", "enable-refreshes", "--json", env=env)
            self.assertEqual(enable_proc.returncode, 0, msg=enable_proc.stderr + "\n" + enable_proc.stdout)

            disable_proc = self.run_cli("agenda", "disable-refreshes", "--json", env=env)
            self.assertEqual(disable_proc.returncode, 0, msg=disable_proc.stderr + "\n" + disable_proc.stdout)
            payload = json.loads(disable_proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(len(payload["windows"]), 3)
            self.assertTrue(all(row["ok"] for row in payload["windows"]))

            launch_agents = Path(td) / "LaunchAgents"
            self.assertFalse(any(launch_agents.glob("*.plist")))

            status_proc = self.run_cli("agenda", "refresh-status", "--json", env=env)
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            status_payload = json.loads(status_proc.stdout)
            self.assertFalse(status_payload["enabled"])
            self.assertFalse(status_payload["fully_enabled"])
            self.assertTrue(all(not row["enabled"] for row in status_payload["windows"]))


if __name__ == "__main__":
    unittest.main()
