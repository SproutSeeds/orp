from __future__ import annotations

from pathlib import Path
import json
import unittest
from jsonschema import Draft202012Validator, FormatChecker
from orp_test_support import IsolatedTestCase


REPO_ROOT = Path(__file__).resolve().parents[1]


class HostedWorkspaceContractTests(IsolatedTestCase):
    def test_v2_golden_payloads_validate_and_invalid_payloads_fail(self):
        schema = json.loads((REPO_ROOT / "spec/v2/hosted-workspace-state.schema.json").read_text())
        compatibility = json.loads((REPO_ROOT / "spec/v1/hosted-workspace-state-v2.schema.json").read_text())
        compatibility["$id"] = schema["$id"]
        self.assertEqual(compatibility, schema)
        fixtures = json.loads((REPO_ROOT / "tests/fixtures/hosted-workspace-v2.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for case in fixtures["valid"]:
            with self.subTest(case=case["name"]):
                validator.validate(case["state"])
        for case in fixtures["invalid"]:
            with self.subTest(case=case["name"]):
                self.assertTrue(list(validator.iter_errors(case["state"])))

    def test_hosted_workspace_schema_exists_and_has_expected_core_fields(self) -> None:
        path = REPO_ROOT / "spec" / "v1" / "hosted-workspace.schema.json"
        payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["$id"],
            "https://openresearchprotocol.com/spec/v1/hosted-workspace.schema.json",
        )
        self.assertEqual(payload["title"], "ORP Hosted Workspace")
        self.assertIn("workspace_id", payload["required"])
        self.assertIn("state", payload["required"])
        self.assertIn("linked_idea", payload["properties"])
        self.assertIn("current_state", payload["$defs"])
        self.assertIn("tab", payload["$defs"])

    def test_hosted_workspace_event_schema_exists_and_has_expected_core_fields(self) -> None:
        path = REPO_ROOT / "spec" / "v1" / "hosted-workspace-event.schema.json"
        payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["$id"],
            "https://openresearchprotocol.com/spec/v1/hosted-workspace-event.schema.json",
        )
        self.assertEqual(payload["title"], "ORP Hosted Workspace Event")
        self.assertIn("workspace_id", payload["required"])
        self.assertIn("event_type", payload["required"])
        self.assertIn("actor", payload["required"])

    def test_hosted_workspace_contract_doc_declares_cli_and_api_boundary(self) -> None:
        path = REPO_ROOT / "docs" / "ORP_HOSTED_WORKSPACE_CONTRACT.md"
        text = path.read_text(encoding="utf-8")

        self.assertIn("orp workspace sync main --json", text)
        self.assertIn("GET    /api/cli/workspaces", text)
        self.assertIn("POST   /api/cli/workspaces/:id/state", text)
        self.assertIn("workspaces:write", text)
        self.assertIn("The CLI and server both enforce this boundary.", text)


if __name__ == "__main__":
    unittest.main()
