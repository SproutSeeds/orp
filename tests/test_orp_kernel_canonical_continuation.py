from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-kernel-canonical-continuation.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("orp_kernel_canonical_continuation_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpKernelCanonicalContinuationTests(unittest.TestCase):
    def test_score_case_penalizes_misaligned_fields(self) -> None:
        module = _load_module()
        case = {
            "id": "software_trace_widget",
        }
        response = {
            "object": "terminal trace widget",
            "goal": "surface lane drift and state clearly for operators",
            "boundary": "all sessions everywhere",
            "constraints": "low friction and no GUI dependency",
            "success_criteria": None,
            "missing_required_fields": ["success_criteria"],
            "confidence": 0.8,
        }
        scored = module._score_case(case, response)
        self.assertEqual(scored["aligned_fields"], 3)
        self.assertEqual(scored["misaligned_fields"], 1)
        self.assertEqual(scored["invention_rate"], 0.25)
        self.assertLess(scored["total_score"], 1.0)

    def test_build_report_aggregates_stubbed_results(self) -> None:
        module = _load_module()

        def fake_run(case, condition, *, model):
            answers = {
                "kernel": {
                    "object": "terminal trace widget",
                    "goal": "surface lane drift and state clearly for operators",
                    "boundary": "terminal-first lane visibility in active ORP sessions",
                    "constraints": "low friction and no GUI dependency",
                    "success_criteria": "operators identify a drifting lane within 10 seconds without overloading the terminal surface",
                },
                "generic_checklist": {
                    "object": "terminal trace widget",
                    "goal": "build the terminal trace widget for lane monitoring",
                    "boundary": "terminal-first lane visibility in active ORP sessions",
                    "constraints": "low friction and no GUI dependency",
                    "success_criteria": None,
                },
                "freeform": {
                    "object": "terminal trace widget",
                    "goal": "build something useful",
                    "boundary": None,
                    "constraints": "low friction",
                    "success_criteria": None,
                },
            }[condition]
            return {
                "raw_response": {
                    "artifact_class": "task",
                    **answers,
                    "missing_required_fields": [field for field, value in answers.items() if value is None],
                    "confidence": 0.9,
                },
                "elapsed_ms": 100.0,
                "session_id": "session-123",
                "tokens_used": 1000,
            }

        with mock.patch.object(module, "_run_codex", side_effect=fake_run):
            report = module.build_report(model="", case_ids={"software_trace_widget"})

        self.assertTrue(report["summary"]["all_claims_pass"])
        self.assertGreater(
            report["conditions"]["kernel"]["mean_total_score"],
            report["conditions"]["freeform"]["mean_total_score"],
        )
        self.assertGreaterEqual(
            report["conditions"]["kernel"]["mean_total_score"],
            report["conditions"]["generic_checklist"]["mean_total_score"],
        )


if __name__ == "__main__":
    unittest.main()
