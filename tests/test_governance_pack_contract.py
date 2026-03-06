from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "packs" / "erdos-open-problems" / "profiles" / "sunflower-mathlib-pr-governance.yml.tmpl"
EXAMPLE = REPO_ROOT / "examples" / "orp.sunflower-coda.pr-governance.yml"
PACK_README = REPO_ROOT / "packs" / "erdos-open-problems" / "README.md"
PROFILE_DOC = REPO_ROOT / "docs" / "PROFILE_PACKS.md"
MAPPING_DOC = REPO_ROOT / "docs" / "SUNFLOWER_CODA_PR_GOVERNANCE_MAPPING.md"

REQUIRED_MODULE_EXPR = '${ORP_NATURALITY_MODULE:?set ORP_NATURALITY_MODULE}'
LEGACY_TODO_EXPR = '${ORP_NATURALITY_MODULE:-TODO}'


class GovernancePackContractTests(unittest.TestCase):
    def test_naturality_module_is_required_in_template_and_example(self) -> None:
        template_text = TEMPLATE.read_text(encoding="utf-8")
        example_text = EXAMPLE.read_text(encoding="utf-8")

        self.assertIn(REQUIRED_MODULE_EXPR, template_text)
        self.assertIn(REQUIRED_MODULE_EXPR, example_text)
        self.assertNotIn(LEGACY_TODO_EXPR, template_text)
        self.assertNotIn(LEGACY_TODO_EXPR, example_text)

    def test_docs_surface_naturality_module_requirement(self) -> None:
        for path in (PACK_README, PROFILE_DOC, MAPPING_DOC):
            text = path.read_text(encoding="utf-8")
            self.assertIn("ORP_NATURALITY_MODULE", text, msg=f"missing ORP_NATURALITY_MODULE in {path}")


if __name__ == "__main__":
    unittest.main()
