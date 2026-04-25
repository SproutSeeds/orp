from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def _run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--repo-root",
            str(root),
            *args,
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class OrpHygieneTests(unittest.TestCase):
    def _init_repo(self, root: Path) -> dict:
        proc = _run_cli(root, "init", "--json")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        return json.loads(proc.stdout)

    def _hygiene(self, root: Path) -> dict:
        proc = _run_cli(root, "hygiene", "--json")
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        return json.loads(proc.stdout)

    def test_init_scaffolds_hygiene_policy_and_agent_stop_rule(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = self._init_repo(root)

            self.assertEqual(payload["files"]["hygiene_policy"]["path"], "orp/hygiene-policy.json")
            self.assertEqual(payload["hygiene_policy"]["path"], "orp/hygiene-policy.json")
            self.assertTrue(payload["hygiene_policy"]["non_destructive"])
            self.assertTrue(payload["hygiene_policy"]["stop_on_unclassified"])

            policy = json.loads((root / "orp" / "hygiene-policy.json").read_text(encoding="utf-8"))
            self.assertEqual(policy["kind"], "orp_hygiene_policy")
            self.assertTrue(policy["non_destructive"])
            self.assertTrue(policy["stop_on_unclassified"])
            self.assertIn("classification_rules", policy)

            project = json.loads((root / "orp" / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project["hygiene_policy"]["command"], "orp hygiene --json")
            self.assertIn("before remote side effects or unbudgeted paid compute", project["hygiene_policy"]["run_moments"])
            self.assertIn("Do not hard-stop solely", project["hygiene_policy"]["budgeted_research_spend_rule"])
            self.assertIn("orp hygiene --json", project["next_actions"])

            agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("orp hygiene --json", agents_text)
            self.assertIn("dirty_unclassified", agents_text)
            self.assertIn("before remote side effects or unbudgeted paid compute", agents_text)
            self.assertIn("Do not hard-stop solely because an OpenAI research lane is paid", agents_text)
            self.assertIn("never reset, checkout, or delete files", agents_text)

            handoff_text = (root / "orp" / "HANDOFF.md").read_text(encoding="utf-8")
            self.assertIn("orp hygiene --json", handoff_text)
            self.assertIn("dirty_unclassified", handoff_text)

    def test_fresh_init_dirty_state_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)

            payload = self._hygiene(root)
            self.assertEqual(payload["status"], "dirty_classified")
            self.assertGreater(payload["dirty_count"], 0)
            self.assertEqual(payload["unclassified_count"], 0)
            self.assertEqual(payload["scratch_count"], 0)
            self.assertTrue(payload["safe_to_expand"])
            self.assertFalse(payload["destructive_cleanup_performed"])

            by_path = {entry["path"]: entry for entry in payload["entries"]}
            self.assertEqual(by_path["orp/"]["category"], "runtime_research_artifact")
            self.assertEqual(by_path["analysis/"]["category"], "canonical_artifact")
            self.assertIn("runtime_research_artifact", payload["categories"])
            self.assertIn("canonical_artifact", payload["categories"])

    def test_unclassified_dirty_state_stops_expansion_without_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            mystery_path = root / "mystery.bin"
            _write_file(mystery_path, "unknown artifact\n")

            payload = self._hygiene(root)
            self.assertEqual(payload["status"], "dirty_unclassified")
            self.assertEqual(payload["unclassified_count"], 1)
            self.assertTrue(payload["stop_condition"])
            self.assertFalse(payload["safe_to_expand"])
            self.assertIn("Stop long-running expansion", payload["required_action"])
            self.assertTrue(mystery_path.exists())

            by_path = {entry["path"]: entry for entry in payload["entries"]}
            self.assertEqual(by_path["mystery.bin"]["category"], "unclassified")

    def test_scratch_dirty_state_is_classified_but_called_out(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._init_repo(root)
            _write_file(root / "scratch" / "note.txt", "temporary observation\n")

            payload = self._hygiene(root)
            self.assertEqual(payload["status"], "dirty_with_scratch")
            self.assertEqual(payload["unclassified_count"], 0)
            self.assertGreaterEqual(payload["scratch_count"], 1)
            self.assertTrue(payload["safe_to_expand"])
            self.assertIn("scratch/output exists", payload["required_action"])

            by_path = {entry["path"]: entry for entry in payload["entries"]}
            self.assertEqual(by_path["scratch/"]["category"], "scratch_or_output_artifact")


if __name__ == "__main__":
    unittest.main()
