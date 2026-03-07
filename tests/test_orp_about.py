from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"
PACKAGE_JSON = REPO_ROOT / "package.json"
PACKAGE_VERSION = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["version"]


class OrpAboutTests(unittest.TestCase):
    def test_about_json_reports_agent_discovery_surfaces(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(CLI), "about", "--json"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

        payload = json.loads(proc.stdout)
        self.assertEqual(payload["tool"]["name"], "orp")
        self.assertEqual(payload["tool"]["version"], PACKAGE_VERSION)
        self.assertTrue(payload["tool"]["agent_friendly"])
        self.assertEqual(payload["discovery"]["llms_txt"], "llms.txt")
        self.assertEqual(payload["discovery"]["agent_loop"], "docs/AGENT_LOOP.md")
        self.assertEqual(payload["schemas"]["packet"], "spec/v1/packet.schema.json")
        command_names = {row["name"] for row in payload["commands"]}
        self.assertIn("about", command_names)
        self.assertIn("gate_run", command_names)
        self.assertIn("erdos_sync", command_names)
        self.assertIn("pack_install", command_names)
        self.assertIn("pack_fetch", command_names)
        json_commands = {row["name"] for row in payload["commands"] if row["json_output"]}
        self.assertIn("erdos_sync", json_commands)
        self.assertIn("pack_install", json_commands)
        self.assertIn("pack_fetch", json_commands)
        pack_ids = {row["id"] for row in payload["packs"]}
        self.assertIn("erdos-open-problems", pack_ids)

    def test_gate_run_json_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = {
                "profiles": {
                    "default": {
                        "packet_kind": "problem_scope",
                        "gate_ids": ["smoke"],
                    }
                },
                "gates": [
                    {
                        "id": "smoke",
                        "phase": "verification",
                        "command": "echo ORP_SMOKE",
                        "pass": {
                            "exit_codes": [0],
                            "stdout_must_contain": ["ORP_SMOKE"],
                        },
                    }
                ],
            }
            (root / "orp.sample.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(root),
                    "--config",
                    "orp.sample.json",
                    "gate",
                    "run",
                    "--profile",
                    "default",
                    "--run-id",
                    "run-json-gate",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertEqual(payload["run_id"], "run-json-gate")
            self.assertEqual(payload["overall"], "PASS")
            self.assertEqual(payload["gates_passed"], 1)
            self.assertEqual(payload["gates_failed"], 0)
            self.assertEqual(payload["gates_total"], 1)
            self.assertEqual(payload["run_record"], "orp/artifacts/run-json-gate/RUN.json")


if __name__ == "__main__":
    unittest.main()
