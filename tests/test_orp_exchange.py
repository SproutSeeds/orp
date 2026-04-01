from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


class OrpExchangeTests(unittest.TestCase):
    def test_exchange_repo_synthesize_bootstraps_local_directory_when_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as host_td, tempfile.TemporaryDirectory() as source_td:
            host_root = Path(host_td)
            source_root = Path(source_td)
            (source_root / "README.md").write_text("# Source Repo\n", encoding="utf-8")
            (source_root / "package.json").write_text('{"name":"source-repo"}\n', encoding="utf-8")
            (source_root / "src").mkdir()
            (source_root / "src" / "index.js").write_text("console.log('hi')\n", encoding="utf-8")
            (source_root / "docs").mkdir()
            (source_root / "docs" / "ARCHITECTURE.md").write_text("# Architecture\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(host_root),
                    "exchange",
                    "repo",
                    "synthesize",
                    str(source_root),
                    "--allow-git-init",
                    "--exchange-id",
                    "exchange-local",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["exchange_id"], "exchange-local")
            self.assertEqual(payload["source"]["mode"], "local_git")
            self.assertTrue(payload["source"]["git_present"])
            self.assertTrue(payload["source"]["git_initialized_by_orp"])
            self.assertTrue((source_root / ".git").exists())
            exchange_json = host_root / payload["artifacts"]["exchange_json"]
            summary_md = host_root / payload["artifacts"]["summary_md"]
            transfer_map_md = host_root / payload["artifacts"]["transfer_map_md"]
            self.assertTrue(exchange_json.exists())
            self.assertTrue(summary_md.exists())
            self.assertTrue(transfer_map_md.exists())
            exchange_payload = json.loads(exchange_json.read_text(encoding="utf-8"))
            self.assertEqual(exchange_payload["kind"], "exchange_report")
            self.assertEqual(exchange_payload["source"]["mode"], "local_git")
            self.assertIn("package.json", "\n".join(exchange_payload["inventory"]["manifest_files"]))
            self.assertIn("## Relationship To Current Project", summary_md.read_text(encoding="utf-8"))
            self.assertIn("## How This Could Help Us", transfer_map_md.read_text(encoding="utf-8"))

    def test_exchange_repo_synthesize_existing_git_repo_keeps_git_state(self) -> None:
        with tempfile.TemporaryDirectory() as host_td, tempfile.TemporaryDirectory() as source_td:
            host_root = Path(host_td)
            source_root = Path(source_td)
            (source_root / "README.md").write_text("# Source Repo\n", encoding="utf-8")
            (source_root / "pyproject.toml").write_text("[project]\nname='source-repo'\n", encoding="utf-8")
            git_proc = subprocess.run(["git", "init"], cwd=str(source_root), capture_output=True, text=True)
            self.assertEqual(git_proc.returncode, 0, msg=git_proc.stderr + "\n" + git_proc.stdout)

            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(host_root),
                    "exchange",
                    "repo",
                    "synthesize",
                    str(source_root),
                    "--exchange-id",
                    "exchange-git",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["source"]["mode"], "local_git")
            self.assertFalse(payload["source"]["git_initialized_by_orp"])


if __name__ == "__main__":
    unittest.main()
