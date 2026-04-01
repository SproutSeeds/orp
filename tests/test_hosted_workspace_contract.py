from __future__ import annotations

from pathlib import Path
import json
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class HostedWorkspaceContractTests(unittest.TestCase):
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

        self.assertIn("orp workspaces list", text)
        self.assertIn("orp workspaces show <workspace-id>", text)
        self.assertIn("/api/cli/workspaces/:workspaceId/state", text)
        self.assertIn("Workspace Detail Screen", text)
        self.assertIn("Agent Write Contract", text)


if __name__ == "__main__":
    unittest.main()
