from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-erdos-problems-sync.py"
CLI = REPO_ROOT / "cli" / "orp.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "erdos_sample.html"


def _run_sync(tmp: Path, extra: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--input-html",
        str(FIXTURE),
        "--out-all",
        str(tmp / "all.json"),
        "--out-open",
        str(tmp / "open.json"),
        "--out-closed",
        str(tmp / "closed.json"),
        "--out-active",
        str(tmp / "active.json"),
        "--out-open-list",
        str(tmp / "open.md"),
        *extra,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))


class ErdosProblemsSyncTests(unittest.TestCase):
    def test_parses_status_and_counts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            proc = _run_sync(tmp, [])
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)

            all_payload = json.loads((tmp / "all.json").read_text(encoding="utf-8"))
            open_payload = json.loads((tmp / "open.json").read_text(encoding="utf-8"))
            closed_payload = json.loads((tmp / "closed.json").read_text(encoding="utf-8"))
            active_payload = json.loads((tmp / "active.json").read_text(encoding="utf-8"))
            open_md = (tmp / "open.md").read_text(encoding="utf-8")

            self.assertEqual(all_payload["summary"]["total"], 2)
            self.assertEqual(all_payload["summary"]["open"], 1)
            self.assertEqual(all_payload["summary"]["closed"], 1)
            self.assertEqual(all_payload["summary"]["unknown"], 0)

            self.assertEqual(open_payload["problem_ids"], [20])
            self.assertEqual(closed_payload["problem_ids"], [2])
            self.assertEqual(active_payload["summary"]["total"], 1)

            self.assertIn("https://erdosproblems.com/20", open_md)
            self.assertNotIn("[#2](", open_md)

    def test_count_mismatch_fails_without_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            mismatch_html = (tmp / "mismatch.html")
            text = FIXTURE.read_text(encoding="utf-8").replace(
                "1 solved out of 2 shown",
                "1 solved out of 3 shown",
            )
            mismatch_html.write_text(text, encoding="utf-8")

            cmd = [
                sys.executable,
                str(SCRIPT),
                "--input-html",
                str(mismatch_html),
                "--out-all",
                str(tmp / "all.json"),
                "--out-open",
                str(tmp / "open.json"),
                "--out-closed",
                str(tmp / "closed.json"),
                "--out-active",
                str(tmp / "active.json"),
                "--out-open-list",
                str(tmp / "open.md"),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
            self.assertEqual(proc.returncode, 3)
            self.assertIn("parsed problem count does not match", proc.stderr)

    def test_problem_id_lookup_prints_link_and_writes_selected_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            selected_dir = tmp / "selected"
            proc = _run_sync(
                tmp,
                [
                    "--problem-id",
                    "20",
                    "--problem-id",
                    "2",
                    "--out-problem-dir",
                    str(selected_dir),
                ],
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("selected.url=https://erdosproblems.com/20", proc.stdout)
            self.assertIn("selected.url=https://erdosproblems.com/2", proc.stdout)
            self.assertTrue((selected_dir / "erdos_problem.20.json").exists())
            self.assertTrue((selected_dir / "erdos_problem.2.json").exists())

    def test_problem_id_lookup_missing_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            proc = _run_sync(tmp, ["--problem-id", "999999"])
            self.assertEqual(proc.returncode, 4)
            self.assertIn("selected.missing=999999", proc.stdout)

    def test_cli_json_output_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            selected_dir = tmp / "selected"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(tmp),
                    "erdos",
                    "sync",
                    "--input-html",
                    str(FIXTURE),
                    "--out-all",
                    str(tmp / "all.json"),
                    "--out-open",
                    str(tmp / "open.json"),
                    "--out-closed",
                    str(tmp / "closed.json"),
                    "--out-active",
                    str(tmp / "active.json"),
                    "--out-open-list",
                    str(tmp / "open.md"),
                    "--problem-id",
                    "20",
                    "--out-problem-dir",
                    str(selected_dir),
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["returncode"], 0)
            self.assertEqual(payload["summary"]["open"], 1)
            self.assertEqual(payload["summary"]["closed"], 1)
            self.assertEqual(payload["selected_count"], 1)
            self.assertEqual(payload["selected"][0]["problem_id"], 20)
            self.assertEqual(payload["selected"][0]["url"], "https://erdosproblems.com/20")


if __name__ == "__main__":
    unittest.main()
