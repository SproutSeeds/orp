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
        self.assertIn(
            "{home,about,mode,update,maintenance,schedule,agenda,agents,opportunities,connections,auth,whoami,ideas,workspaces,idea,feature,world,youtube,secrets,link,runner,checkpoint,agent,discover,exchange,collaborate,init,status,branch,backup,ready,doctor,cleanup,frontier,kernel,gate,packet,erdos,pack,report}",
            proc.stdout,
        )
        self.assertIn("orp compute -h", proc.stdout)
        self.assertIn("orp workspace tabs -h", proc.stdout)

    def test_node_wrapper_exposes_agents_help(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node not found on PATH")

        proc = subprocess.run(
            ["node", str(BIN), "agents", "-h"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        self.assertIn("AGENTS.md", proc.stdout)
        self.assertIn("orp agents root set /absolute/path/to/projects", proc.stdout)
        self.assertIn("orp agents sync", proc.stdout)
        self.assertIn("orp init --projects-root /absolute/path/to/projects", proc.stdout)

    def test_node_wrapper_exposes_workspace_help(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node not found on PATH")

        proc = subprocess.run(
            ["node", str(BIN), "workspace", "-h"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        self.assertIn("ORP workspace", proc.stdout)
        self.assertIn("orp workspace tabs <name-or-id>", proc.stdout)
        self.assertIn("orp workspace ledger <name-or-id>", proc.stdout)
        self.assertIn("orp workspace ledger add <name-or-id>", proc.stdout)
        self.assertIn("orp workspace tabs --hosted-workspace-id <workspace-id>", proc.stdout)
        self.assertIn("orp workspace list", proc.stdout)
        self.assertIn("orp workspace sync <name-or-id>", proc.stdout)


if __name__ == "__main__":
    unittest.main()
