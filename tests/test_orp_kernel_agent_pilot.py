from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-kernel-agent-pilot.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("orp_kernel_agent_pilot_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpKernelAgentPilotTests(unittest.TestCase):
    def test_run_codex_exec_retries_transient_failures(self) -> None:
        module = _load_module()
        transient = subprocess.CompletedProcess(
            args=["codex"],
            returncode=1,
            stdout="",
            stderr="failed to connect to websocket\nWe're currently experiencing high demand\n",
        )
        success = subprocess.CompletedProcess(
            args=["codex"],
            returncode=0,
            stdout="session id: abc\n",
            stderr="",
        )
        with mock.patch.object(module, "_run_cmd", side_effect=[transient, success]) as run_cmd:
            proc = module._run_codex_exec(["codex"], cwd=REPO_ROOT, stdin="prompt")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(run_cmd.call_count, 2)

    def test_score_pickup_counts_only_explicit_answers(self) -> None:
        module = _load_module()
        case = {
            "artifact_class": "task",
        }
        response = {
            "confidence": 0.8,
            "ambiguities": ["lane drift threshold not defined"],
            "pickup_targets": [
                {"field": "object", "value": "terminal trace widget"},
                {"field": "goal", "value": "surface lane drift clearly"},
                {"field": "boundary", "value": "active ORP sessions only"},
                {"field": "constraints", "value": None},
                {"field": "success_criteria", "value": "operators identify drift within 10 seconds"},
            ],
            "_condition": "kernel",
        }
        scored = module._score_pickup(case, response)
        self.assertEqual(scored["answered_targets"], 4)
        self.assertEqual(scored["pickup_targets_total"], 5)
        self.assertEqual(scored["pickup_score"], 0.8)
        self.assertEqual(scored["ambiguity_remaining"], 0.2)
        self.assertEqual(scored["missing_targets"], ["constraints"])
        self.assertEqual(scored["invented_fields"], [])
        self.assertEqual(scored["invention_rate"], 0.0)

    def test_score_pickup_flags_invented_fields(self) -> None:
        module = _load_module()
        case = {
            "artifact_class": "task",
            "freeform_markdown": "# Trace widget\nObject: terminal trace widget.\nGoal: surface drift.\nConstraints: low friction.\n",
        }
        response = {
            "confidence": 0.6,
            "ambiguities": [],
            "pickup_targets": [
                {"field": "object", "value": "terminal trace widget"},
                {"field": "goal", "value": "surface drift"},
                {"field": "boundary", "value": "all ORP sessions"},
                {"field": "constraints", "value": "low friction"},
                {"field": "success_criteria", "value": None},
            ],
            "_condition": "freeform",
        }
        scored = module._score_pickup(case, response)
        self.assertEqual(scored["invented_fields"], ["boundary"])
        self.assertEqual(scored["invented_fields_count"], 1)
        self.assertEqual(scored["invention_rate"], 0.25)

    def test_build_report_aggregates_stubbed_codex_results(self) -> None:
        module = _load_module()

        def fake_run(case, condition, *, model):
            pickup_answers = {
                "kernel": {
                    "object": "terminal trace widget",
                    "goal": "surface lane drift clearly",
                    "boundary": "active ORP sessions only",
                    "constraints": "low friction",
                    "success_criteria": "operator spots drift",
                },
                "generic_checklist": {
                    "object": "terminal trace widget",
                    "goal": "surface lane drift clearly",
                    "boundary": None,
                    "constraints": "low friction",
                    "success_criteria": None,
                },
                "freeform": {
                    "object": "terminal trace widget",
                    "goal": None,
                    "boundary": None,
                    "constraints": None,
                    "success_criteria": None,
                },
            }[condition]
            return {
                "raw_response": {
                    "artifact_type_guess": "task",
                    "primary_objective_or_state": "Build the widget.",
                    "limits_or_risks": ["noise"],
                    "next_action_or_handoff": "Define the schema.",
                    "confidence": 0.9,
                    "ambiguities": ["lane drift"],
                    "pickup_targets": [
                        {"field": key, "value": value}
                        for key, value in pickup_answers.items()
                    ],
                },
                "elapsed_ms": 100.0,
                "session_id": "session-123",
                "tokens_used": 1000,
            }

        with mock.patch.object(module, "_run_codex_pickup", side_effect=fake_run):
            report = module.build_report(model="", case_ids={"software_trace_widget"})

        self.assertTrue(report["summary"]["all_claims_pass"])
        self.assertEqual(report["corpus"]["cases_total"], 1)
        self.assertGreater(
            report["conditions"]["kernel"]["mean_pickup_score"],
            report["conditions"]["generic_checklist"]["mean_pickup_score"],
        )
        self.assertGreater(
            report["conditions"]["generic_checklist"]["mean_pickup_score"],
            report["conditions"]["freeform"]["mean_pickup_score"],
        )
        self.assertLessEqual(
            report["conditions"]["kernel"]["mean_invention_rate"],
            report["conditions"]["generic_checklist"]["mean_invention_rate"],
        )


if __name__ == "__main__":
    unittest.main()
