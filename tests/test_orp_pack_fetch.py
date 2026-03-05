from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
FETCH_SCRIPT = REPO_ROOT / "scripts" / "orp-pack-fetch.py"
CLI = REPO_ROOT / "cli" / "orp.py"


def _run_fetch(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(FETCH_SCRIPT), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))


class OrpPackFetchTests(unittest.TestCase):
    def test_fetch_from_local_repo_returns_pack_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / "cache"
            proc = _run_fetch(
                [
                    "--source",
                    str(REPO_ROOT),
                    "--pack-id",
                    "erdos-open-problems",
                    "--cache-root",
                    str(cache),
                ]
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("pack_id=erdos-open-problems", proc.stdout)
            lines = [x.strip() for x in proc.stdout.splitlines() if x.strip()]
            pack_path_line = [x for x in lines if x.startswith("pack_path=")]
            self.assertTrue(pack_path_line, msg=proc.stdout)
            pack_path = Path(pack_path_line[0].split("=", 1)[1])
            self.assertTrue((pack_path / "pack.yml").exists(), msg=f"missing pack.yml in {pack_path}")

    def test_cli_fetch_with_install_target_installs_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            cache = tmp / "cache"
            target = tmp / "target"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(REPO_ROOT),
                    "pack",
                    "fetch",
                    "--source",
                    str(REPO_ROOT),
                    "--pack-id",
                    "erdos-open-problems",
                    "--cache-root",
                    str(cache),
                    "--install-target",
                    str(target),
                    "--include",
                    "catalog",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            self.assertTrue((target / "orp.erdos-catalog-sync.yml").exists())
            self.assertTrue((target / "orp.erdos.pack-install-report.md").exists())


if __name__ == "__main__":
    unittest.main()

