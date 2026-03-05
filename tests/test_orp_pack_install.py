from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-pack-install.py"
CLI = REPO_ROOT / "cli" / "orp.py"


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

    def test_live_compare_strict_deps_fails_when_bootstrap_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            proc = _run(
                [
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "live_compare",
                    "--strict-deps",
                    "--no-bootstrap",
                ]
            )
            self.assertEqual(proc.returncode, 3, msg=proc.stderr)
            report = target / "orp.erdos.pack-install-report.md"
            self.assertTrue(report.exists(), msg=f"missing report: {report}")
            text = report.read_text(encoding="utf-8")
            self.assertIn("analysis/problem857_counting_gateboard.json", text)
            self.assertIn("scripts/problem857_ops_board.py", text)

    def test_live_compare_bootstrap_is_install_and_go(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            install = _run(
                [
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "live_compare",
                ]
            )
            self.assertEqual(install.returncode, 0, msg=install.stderr)
            self.assertIn("deps.missing_total=0", install.stdout)

            cfg = target / "orp.erdos-live-compare.yml"
            self.assertTrue(cfg.exists(), msg=f"missing rendered config: {cfg}")

            run = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(target),
                    "--config",
                    str(cfg),
                    "gate",
                    "run",
                    "--profile",
                    "sunflower_live_compare_857",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr + "\n" + run.stdout)
            self.assertIn("overall=PASS", run.stdout)

            m = re.search(r"run_id=([A-Za-z0-9\\-]+)", run.stdout)
            self.assertIsNotNone(m, msg=f"missing run_id in stdout: {run.stdout}")
            run_id = str(m.group(1))
            run_json = target / "orp" / "artifacts" / run_id / "RUN.json"
            self.assertTrue(run_json.exists(), msg=f"missing run json: {run_json}")


if __name__ == "__main__":
    unittest.main()
