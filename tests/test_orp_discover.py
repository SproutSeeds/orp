from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"
REPOS_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "github_discover_repos.json"
ISSUES_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "github_discover_issues.json"


class OrpDiscoverTests(unittest.TestCase):
    def test_discover_profile_init_json_writes_profile_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "discover",
                    "profile",
                    "init",
                    "--owner",
                    "SproutSeeds",
                    "--owner-type",
                    "org",
                    "--profile-id",
                    "sunflower-focus",
                    "--keyword",
                    "sunflower",
                    "--topic",
                    "formalization",
                    "--language",
                    "Lean",
                    "--area",
                    "balance",
                    "--person",
                    "alice",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["profile_id"], "sunflower-focus")
            profile_path = root / payload["profile_path"]
            self.assertTrue(profile_path.exists())
            written = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(written["discover"]["github"]["owner"]["login"], "SproutSeeds")
            self.assertEqual(written["discover"]["github"]["signals"]["languages"], ["Lean"])

    def test_discover_github_scan_json_ranks_repos_issues_and_people(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            profile = {
                "schema_version": "1.0.0",
                "profile_id": "sunflower-focus",
                "discover": {
                    "github": {
                        "owner": {
                            "login": "SproutSeeds",
                            "type": "org",
                        },
                        "signals": {
                            "keywords": ["sunflower", "lean", "balance"],
                            "repo_topics": ["formalization", "math"],
                            "languages": ["Lean"],
                            "areas": ["balance", "container"],
                            "people": ["alice"],
                        },
                        "filters": {
                            "include_repos": [],
                            "exclude_repos": [],
                            "issue_states": ["open"],
                            "labels_any": [],
                            "exclude_labels": [],
                            "updated_within_days": 365,
                        },
                        "ranking": {
                            "repo_sample_size": 10,
                            "max_repos": 5,
                            "max_issues": 5,
                            "max_people": 5,
                            "issues_per_repo": 10,
                        },
                    }
                },
            }
            profile_path = root / "orp.profile.default.json"
            profile_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "discover",
                    "github",
                    "scan",
                    "--profile",
                    str(profile_path),
                    "--scan-id",
                    "scan-fixture",
                    "--repos-fixture",
                    str(REPOS_FIXTURE),
                    "--issues-fixture",
                    str(ISSUES_FIXTURE),
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["scan_id"], "scan-fixture")
            self.assertEqual(payload["owner"]["login"], "SproutSeeds")
            self.assertEqual(payload["repos"][0]["full_name"], "SproutSeeds/sunflower-lean")
            self.assertEqual(payload["issues"][0]["number"], 857)
            people = {row["login"] for row in payload["people"]}
            self.assertIn("alice", people)

            scan_json = root / payload["artifacts"]["scan_json"]
            summary_md = root / payload["artifacts"]["summary_md"]
            self.assertTrue(scan_json.exists())
            self.assertTrue(summary_md.exists())
            summary_text = summary_md.read_text(encoding="utf-8")
            self.assertIn("SproutSeeds/sunflower-lean", summary_text)
            self.assertIn("orp collaborate init --github-repo SproutSeeds/sunflower-lean", summary_text)

            state = json.loads((root / "orp" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["last_discover_scan_id"], "scan-fixture")
            self.assertIn("scan-fixture", state["discovery_scans"])


if __name__ == "__main__":
    unittest.main()
