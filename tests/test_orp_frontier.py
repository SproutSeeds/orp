from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


class OrpFrontierTests(unittest.TestCase):
    def _run(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), "--repo-root", str(root), *args],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )

    def test_frontier_init_scaffolds_control_surface(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orp-frontier-init.") as td:
            root = Path(td)
            proc = self._run(
                root,
                "frontier",
                "init",
                "--program-id",
                "ocular-controller",
                "--label",
                "Ocular Controller",
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["program_id"], "ocular-controller")
            self.assertTrue((root / "orp" / "frontier" / "state.json").exists())
            self.assertTrue((root / "orp" / "frontier" / "roadmap.json").exists())
            self.assertTrue((root / "orp" / "frontier" / "checklist.json").exists())
            self.assertTrue((root / "orp" / "frontier" / "version-stack.json").exists())
            self.assertTrue((root / "orp" / "frontier" / "additional-items.json").exists())
            self.assertTrue((root / "orp" / "frontier" / "STATE.md").exists())
            self.assertTrue((root / "orp" / "frontier" / "ROADMAP.md").exists())
            self.assertTrue((root / "orp" / "frontier" / "CHECKLIST.md").exists())
            self.assertTrue((root / "orp" / "frontier" / "VERSION_STACK.md").exists())
            self.assertTrue((root / "orp" / "frontier" / "ADDITIONAL_ITEMS.md").exists())

    def test_frontier_can_model_version_milestone_phase_and_live_pointer(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orp-frontier-live.") as td:
            root = Path(td)
            init_proc = self._run(
                root,
                "frontier",
                "init",
                "--program-id",
                "ocular-controller",
                "--label",
                "Ocular Controller",
                "--json",
            )
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            add_version = self._run(
                root,
                "frontier",
                "add-version",
                "--id",
                "v10",
                "--label",
                "Certified Generalization Era",
                "--json",
            )
            self.assertEqual(add_version.returncode, 0, msg=add_version.stderr + "\n" + add_version.stdout)

            add_milestone = self._run(
                root,
                "frontier",
                "add-milestone",
                "--version",
                "v10",
                "--id",
                "v10.3",
                "--label",
                "Figure And Supplement Execution",
                "--band",
                "exact",
                "--success-criterion",
                "freeze figure specification",
                "--json",
            )
            self.assertEqual(add_milestone.returncode, 0, msg=add_milestone.stderr + "\n" + add_milestone.stdout)

            add_phase = self._run(
                root,
                "frontier",
                "add-phase",
                "--milestone",
                "v10.3",
                "--id",
                "395",
                "--label",
                "Figure Specification And Data Contract Freeze",
                "--goal",
                "freeze one exact figure set and one data-contract surface",
                "--plan",
                "395-01",
                "--compute-point-id",
                "adult-vs-developmental-rgc-opponent",
                "--allowed-rung",
                "local-4090-scout",
                "--allowed-rung",
                "paid-h100-transfer",
                "--paid-requires-user-approval",
                "--json",
            )
            self.assertEqual(add_phase.returncode, 0, msg=add_phase.stderr + "\n" + add_phase.stdout)

            set_live = self._run(
                root,
                "frontier",
                "set-live",
                "--version",
                "v10",
                "--milestone",
                "v10.3",
                "--phase",
                "395",
                "--next-action",
                "execute phase 395",
                "--json",
            )
            self.assertEqual(set_live.returncode, 0, msg=set_live.stderr + "\n" + set_live.stdout)

            state_proc = self._run(root, "frontier", "state", "--json")
            self.assertEqual(state_proc.returncode, 0, msg=state_proc.stderr + "\n" + state_proc.stdout)
            state = json.loads(state_proc.stdout)
            self.assertEqual(state["active_version"], "v10")
            self.assertEqual(state["active_milestone"], "v10.3")
            self.assertEqual(state["active_phase"], "395")

            roadmap_proc = self._run(root, "frontier", "roadmap", "--json")
            self.assertEqual(roadmap_proc.returncode, 0, msg=roadmap_proc.stderr + "\n" + roadmap_proc.stdout)
            roadmap = json.loads(roadmap_proc.stdout)
            self.assertEqual(roadmap["active_milestone"], "v10.3")
            self.assertEqual(len(roadmap["phases"]), 1)
            self.assertEqual(
                roadmap["phases"][0]["compute_hooks"][0]["compute_point_id"],
                "adult-vs-developmental-rgc-opponent",
            )

            checklist_proc = self._run(root, "frontier", "checklist", "--json")
            self.assertEqual(checklist_proc.returncode, 0, msg=checklist_proc.stderr + "\n" + checklist_proc.stdout)
            checklist = json.loads(checklist_proc.stdout)
            self.assertEqual(len(checklist["exact"]), 1)
            self.assertEqual(checklist["exact"][0]["milestone_id"], "v10.3")

            doctor_proc = self._run(root, "frontier", "doctor", "--json")
            self.assertEqual(doctor_proc.returncode, 0, msg=doctor_proc.stderr + "\n" + doctor_proc.stdout)
            doctor = json.loads(doctor_proc.stdout)
            self.assertTrue(doctor["ok"])

    def test_frontier_additional_items_queue_activates_and_completes_in_order(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orp-frontier-additional.") as td:
            root = Path(td)
            init_proc = self._run(
                root,
                "frontier",
                "init",
                "--program-id",
                "ocular-controller",
                "--label",
                "Ocular Controller",
                "--json",
            )
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            add_list = self._run(
                root,
                "frontier",
                "additional",
                "add-list",
                "--id",
                "additional-1",
                "--label",
                "Post-run ideas",
                "--json",
            )
            self.assertEqual(add_list.returncode, 0, msg=add_list.stderr + "\n" + add_list.stdout)

            first_item = self._run(
                root,
                "frontier",
                "additional",
                "add-item",
                "--list",
                "additional-1",
                "--id",
                "item-1",
                "--label",
                "Add compact report",
                "--goal",
                "Produce a small report with warnings.",
                "--success-criterion",
                "Reports warn on weak generalization.",
                "--json",
            )
            self.assertEqual(first_item.returncode, 0, msg=first_item.stderr + "\n" + first_item.stdout)

            second_item = self._run(
                root,
                "frontier",
                "additional",
                "add-item",
                "--list",
                "additional-1",
                "--id",
                "item-2",
                "--label",
                "Document report command",
                "--json",
            )
            self.assertEqual(second_item.returncode, 0, msg=second_item.stderr + "\n" + second_item.stdout)

            activate_first = self._run(root, "frontier", "additional", "activate-next", "--json")
            self.assertEqual(activate_first.returncode, 0, msg=activate_first.stderr + "\n" + activate_first.stdout)
            first_payload = json.loads(activate_first.stdout)
            self.assertTrue(first_payload["activated"])
            self.assertEqual(first_payload["active_list_id"], "additional-1")
            self.assertEqual(first_payload["active_item_id"], "item-1")
            self.assertIn("Add compact report", first_payload["next_action"])

            complete_first = self._run(root, "frontier", "additional", "complete-active", "--json")
            self.assertEqual(complete_first.returncode, 0, msg=complete_first.stderr + "\n" + complete_first.stdout)
            self.assertTrue(json.loads(complete_first.stdout)["completed"])

            activate_second = self._run(root, "frontier", "additional", "activate-next", "--json")
            self.assertEqual(activate_second.returncode, 0, msg=activate_second.stderr + "\n" + activate_second.stdout)
            second_payload = json.loads(activate_second.stdout)
            self.assertTrue(second_payload["activated"])
            self.assertEqual(second_payload["active_item_id"], "item-2")

            complete_second = self._run(root, "frontier", "additional", "complete-active", "--json")
            self.assertEqual(complete_second.returncode, 0, msg=complete_second.stderr + "\n" + complete_second.stdout)
            self.assertTrue(json.loads(complete_second.stdout)["list_completed"])

            no_more = self._run(root, "frontier", "additional", "activate-next", "--json")
            self.assertEqual(no_more.returncode, 0, msg=no_more.stderr + "\n" + no_more.stdout)
            self.assertFalse(json.loads(no_more.stdout)["activated"])

            list_proc = self._run(root, "frontier", "additional", "list", "--json")
            self.assertEqual(list_proc.returncode, 0, msg=list_proc.stderr + "\n" + list_proc.stdout)
            summary = json.loads(list_proc.stdout)["summary"]
            self.assertEqual(summary["complete_items"], 2)
            self.assertEqual(summary["pending_items"], 0)
            self.assertTrue((root / "orp" / "frontier" / "ADDITIONAL_ITEMS.md").exists())

    def test_frontier_preflight_requires_active_additional_item_before_queue_delegation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orp-frontier-preflight-additional.") as td:
            root = Path(td)
            init_proc = self._run(root, "frontier", "init", "--program-id", "blood-cancer", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)
            self.assertEqual(
                self._run(root, "frontier", "additional", "add-list", "--id", "frontier", "--label", "Frontier queue").returncode,
                0,
            )
            self.assertEqual(
                self._run(
                    root,
                    "frontier",
                    "additional",
                    "add-item",
                    "--list",
                    "frontier",
                    "--id",
                    "case-intake",
                    "--label",
                    "Build caregiver intake",
                ).returncode,
                0,
            )

            preflight = self._run(root, "frontier", "preflight-delegate", "--json")
            self.assertEqual(preflight.returncode, 1, msg=preflight.stderr + "\n" + preflight.stdout)
            payload = json.loads(preflight.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("pending_additional_without_active_pointer", {issue["code"] for issue in payload["issues"]})
            self.assertEqual(payload["continuation"]["suggested_next_command"], "orp frontier additional activate-next --json")

            activate = self._run(root, "frontier", "additional", "activate-next", "--json")
            self.assertEqual(activate.returncode, 0, msg=activate.stderr + "\n" + activate.stdout)
            ready = self._run(root, "frontier", "preflight-delegate", "--json")
            self.assertEqual(ready.returncode, 0, msg=ready.stderr + "\n" + ready.stdout)
            self.assertTrue(json.loads(ready.stdout)["ok"])

    def test_frontier_doctor_catches_completed_live_phase_as_stale_continuation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orp-frontier-stale-phase.") as td:
            root = Path(td)
            self.assertEqual(self._run(root, "frontier", "init", "--program-id", "blood-cancer").returncode, 0)
            self.assertEqual(self._run(root, "frontier", "add-version", "--id", "v1", "--label", "Version 1").returncode, 0)
            self.assertEqual(
                self._run(
                    root,
                    "frontier",
                    "add-milestone",
                    "--version",
                    "v1",
                    "--id",
                    "m1",
                    "--label",
                    "Milestone 1",
                    "--band",
                    "exact",
                ).returncode,
                0,
            )
            self.assertEqual(
                self._run(
                    root,
                    "frontier",
                    "add-phase",
                    "--milestone",
                    "m1",
                    "--id",
                    "p1",
                    "--label",
                    "Phase 1",
                ).returncode,
                0,
            )
            self.assertEqual(
                self._run(root, "frontier", "set-live", "--version", "v1", "--milestone", "m1", "--phase", "p1").returncode,
                0,
            )
            stack_path = root / "orp" / "frontier" / "version-stack.json"
            stack = json.loads(stack_path.read_text(encoding="utf-8"))
            stack["versions"][0]["milestones"][0]["phases"][0]["status"] = "complete"
            stack_path.write_text(json.dumps(stack, indent=2) + "\n", encoding="utf-8")

            doctor = self._run(root, "frontier", "doctor", "--json")
            self.assertEqual(doctor.returncode, 1, msg=doctor.stderr + "\n" + doctor.stdout)
            payload = json.loads(doctor.stdout)
            self.assertIn("stale_active_phase_complete", {issue["code"] for issue in payload["issues"]})

    def test_frontier_doctor_strict_fails_on_continuation_warnings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orp-frontier-strict.") as td:
            root = Path(td)
            self.assertEqual(self._run(root, "frontier", "init", "--program-id", "blood-cancer").returncode, 0)
            self.assertEqual(self._run(root, "frontier", "add-version", "--id", "v1", "--label", "Version 1").returncode, 0)
            self.assertEqual(
                self._run(
                    root,
                    "frontier",
                    "add-milestone",
                    "--version",
                    "v1",
                    "--id",
                    "m1",
                    "--label",
                    "Milestone 1",
                    "--band",
                    "exact",
                ).returncode,
                0,
            )
            self.assertEqual(
                self._run(
                    root,
                    "frontier",
                    "add-milestone",
                    "--version",
                    "v1",
                    "--id",
                    "m2",
                    "--label",
                    "Milestone 2",
                    "--band",
                    "exact",
                ).returncode,
                0,
            )
            self.assertEqual(self._run(root, "frontier", "set-live", "--version", "v1", "--milestone", "m2").returncode, 0)

            loose = self._run(root, "frontier", "doctor", "--json")
            self.assertEqual(loose.returncode, 0, msg=loose.stderr + "\n" + loose.stdout)
            loose_payload = json.loads(loose.stdout)
            self.assertTrue(loose_payload["ok"])
            self.assertIn("multiple_exact_milestones", {issue["code"] for issue in loose_payload["issues"]})

            strict = self._run(root, "frontier", "doctor", "--strict", "--json")
            self.assertEqual(strict.returncode, 1, msg=strict.stderr + "\n" + strict.stdout)
            self.assertFalse(json.loads(strict.stdout)["ok"])

    def test_frontier_doctor_catches_stale_active_additional_item(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orp-frontier-stale-additional.") as td:
            root = Path(td)
            self.assertEqual(self._run(root, "frontier", "init", "--program-id", "blood-cancer").returncode, 0)
            self.assertEqual(self._run(root, "frontier", "additional", "add-list", "--id", "queue", "--label", "Queue").returncode, 0)
            self.assertEqual(
                self._run(
                    root,
                    "frontier",
                    "additional",
                    "add-item",
                    "--list",
                    "queue",
                    "--id",
                    "one",
                    "--label",
                    "First item",
                ).returncode,
                0,
            )
            self.assertEqual(self._run(root, "frontier", "additional", "activate-next").returncode, 0)

            additional_path = root / "orp" / "frontier" / "additional-items.json"
            additional = json.loads(additional_path.read_text(encoding="utf-8"))
            additional["lists"][0]["items"][0]["status"] = "complete"
            additional_path.write_text(json.dumps(additional, indent=2) + "\n", encoding="utf-8")

            doctor = self._run(root, "frontier", "doctor", "--json")
            self.assertEqual(doctor.returncode, 1, msg=doctor.stderr + "\n" + doctor.stdout)
            self.assertIn("stale_active_additional_item", {issue["code"] for issue in json.loads(doctor.stdout)["issues"]})


if __name__ == "__main__":
    unittest.main()
