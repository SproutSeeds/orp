from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-kernel-continuation-pilot.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("orp_kernel_continuation_pilot_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpKernelContinuationPilotTests(unittest.TestCase):
    def test_score_continuation_accounts_for_invention(self) -> None:
        module = _load_module()
        case = {
            "artifact_class": "task",
            "freeform_markdown": "# Trace widget\nObject: terminal trace widget.\nConstraints: low friction.\n",
        }
        response = {
            "recommended_next_action": "Define the event schema.",
            "carry_forward": [
                {"field": "object", "value": "terminal trace widget"},
                {"field": "constraints", "value": "low friction"},
                {"field": "success_criteria", "value": "spot drift within 10 seconds"},
            ],
            "explicitly_missing": ["success_criteria"],
            "confidence": 0.8,
            "_condition": "freeform",
        }
        scored = module._score_continuation(case, response)
        self.assertEqual(scored["carry_forward_score"], 1.0)
        self.assertEqual(scored["invented_fields"], ["success_criteria"])
        self.assertEqual(scored["invention_rate"], 0.333)
        self.assertTrue(scored["next_action_present"])
        self.assertLess(scored["continuation_score"], 1.0)

    def test_build_report_aggregates_stubbed_continuations(self) -> None:
        module = _load_module()

        def fake_run(case, condition, *, model):
            carry_forward = {
                "kernel": {
                    "object": "terminal trace widget",
                    "constraints": "low friction",
                    "success_criteria": "spot drift within 10 seconds",
                },
                "generic_checklist": {
                    "object": None,
                    "constraints": "low friction",
                    "success_criteria": "spot drift quickly",
                },
                "freeform": {
                    "object": "terminal trace widget",
                    "constraints": "low friction",
                    "success_criteria": None,
                },
            }[condition]
            return {
                "raw_response": {
                    "artifact_type_guess": "task",
                    "recommended_next_action": "Define the event schema.",
                    "carry_forward": [
                        {"field": field, "value": value}
                        for field, value in carry_forward.items()
                    ],
                    "explicitly_missing": [],
                    "confidence": 0.9,
                },
                "elapsed_ms": 100.0,
                "session_id": "session-123",
                "tokens_used": 1000,
            }

        with mock.patch.object(module, "_run_codex_continuation", side_effect=fake_run):
            report = module.build_report(model="", case_ids={"software_trace_widget"})

        self.assertTrue(report["summary"]["all_claims_pass"])
        self.assertGreater(
            report["conditions"]["kernel"]["mean_continuation_score"],
            report["conditions"]["generic_checklist"]["mean_continuation_score"],
        )
        self.assertGreater(
            report["conditions"]["kernel"]["mean_continuation_score"],
            report["conditions"]["freeform"]["mean_continuation_score"],
        )


if __name__ == "__main__":
    unittest.main()
