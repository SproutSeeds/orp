from __future__ import annotations

import argparse
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_mode_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpModeTests(unittest.TestCase):
    def test_mode_list_includes_sleek_minimal_progressive(self) -> None:
        module = load_cli_module()
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = module.cmd_mode_list(
                argparse.Namespace(
                    json_output=True,
                )
            )
        self.assertEqual(result, 0)
        payload = json.loads(buf.getvalue())
        ids = {row["id"] for row in payload["items"]}
        self.assertIn("sleek-minimal-progressive", ids)
        self.assertIn("ruthless-simplification", ids)
        self.assertIn("systems-constellation", ids)
        self.assertIn("bold-concept-generation", ids)

    def test_mode_show_accepts_typo_alias(self) -> None:
        module = load_cli_module()
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = module.cmd_mode_show(
                argparse.Namespace(
                    mode_ref="sleak-minimal-progressive",
                    json_output=True,
                )
            )
        self.assertEqual(result, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["mode"]["id"], "sleek-minimal-progressive")
        self.assertIn("smp", payload["mode"]["aliases"])
        self.assertTrue(payload["mode"]["invocation_style"].startswith("Optional"))
        self.assertGreaterEqual(len(payload["mode"]["perspective_shifts"]), 4)

    def test_mode_nudge_is_deterministic_for_seed(self) -> None:
        module = load_cli_module()
        first_buf = io.StringIO()
        with redirect_stdout(first_buf):
            first_result = module.cmd_mode_nudge(
                argparse.Namespace(
                    mode_ref="sleek-minimal-progressive",
                    seed="morning-pass",
                    json_output=True,
                )
            )
        second_buf = io.StringIO()
        with redirect_stdout(second_buf):
            second_result = module.cmd_mode_nudge(
                argparse.Namespace(
                    mode_ref="sleek-minimal-progressive",
                    seed="morning-pass",
                    json_output=True,
                )
            )
        self.assertEqual(first_result, 0)
        self.assertEqual(second_result, 0)
        first_payload = json.loads(first_buf.getvalue())
        second_payload = json.loads(second_buf.getvalue())
        self.assertEqual(first_payload["seed"], "morning-pass")
        self.assertEqual(first_payload["card_index"], second_payload["card_index"])
        self.assertEqual(first_payload["card"]["title"], second_payload["card"]["title"])

    def test_mode_show_supports_systems_constellation(self) -> None:
        module = load_cli_module()
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = module.cmd_mode_show(
                argparse.Namespace(
                    mode_ref="systems-constellation",
                    json_output=True,
                )
            )
        self.assertEqual(result, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["mode"]["label"], "Systems Constellation")
        self.assertGreaterEqual(payload["mode"]["nudge_card_count"], 4)


if __name__ == "__main__":
    unittest.main()
