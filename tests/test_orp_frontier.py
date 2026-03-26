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
            self.assertTrue((root / "orp" / "frontier" / "STATE.md").exists())
            self.assertTrue((root / "orp" / "frontier" / "ROADMAP.md").exists())
            self.assertTrue((root / "orp" / "frontier" / "CHECKLIST.md").exists())
            self.assertTrue((root / "orp" / "frontier" / "VERSION_STACK.md").exists())

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


if __name__ == "__main__":
    unittest.main()
