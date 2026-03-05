from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-pack-install.py"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))


class OrpPackInstallTests(unittest.TestCase):
    def test_catalog_install_renders_config_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            proc = _run(
                [
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "catalog",
                ]
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            cfg = target / "orp.erdos-catalog-sync.yml"
            report = target / "orp.erdos.pack-install-report.md"
            self.assertTrue(cfg.exists(), msg=f"missing rendered config: {cfg}")
            self.assertTrue(report.exists(), msg=f"missing report: {report}")
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("`catalog`", report_text)
            self.assertIn("## Dependency Audit", report_text)
            self.assertIn("deps.missing_total=0", proc.stdout)

    def test_live_compare_strict_deps_fails_on_missing_private_wiring(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            proc = _run(
                [
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "live_compare",
                    "--strict-deps",
                ]
            )
            self.assertEqual(proc.returncode, 3, msg=proc.stderr)
            report = target / "orp.erdos.pack-install-report.md"
            self.assertTrue(report.exists(), msg=f"missing report: {report}")
            text = report.read_text(encoding="utf-8")
            self.assertIn("analysis/problem857_counting_gateboard.json", text)
            self.assertIn("scripts/problem857_ops_board.py", text)


if __name__ == "__main__":
    unittest.main()

