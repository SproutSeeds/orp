from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
BIN = REPO_ROOT / "bin" / "orp.js"


class NpmBinWrapperTests(unittest.TestCase):
    def test_node_wrapper_invokes_cli_help(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node not found on PATH")

        proc = subprocess.run(
            ["node", str(BIN), "-h"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        self.assertIn("ORP CLI", proc.stdout)
        self.assertIn("{home,about,discover,collaborate,init,gate,packet,erdos,pack,report}", proc.stdout)


if __name__ == "__main__":
    unittest.main()
