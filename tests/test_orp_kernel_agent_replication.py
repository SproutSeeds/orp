from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-kernel-agent-replication.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("orp_kernel_agent_replication_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpKernelAgentReplicationTests(unittest.TestCase):
    def test_build_report_aggregates_repeated_runs(self) -> None:
        module = _load_module()

        reports = [
            {
                "summary": {
                    "kernel_mean_pickup_score": 1.0,
                    "generic_checklist_mean_pickup_score": 0.8,
                    "freeform_mean_pickup_score": 0.6,
                    "kernel_mean_invention_rate": 0.0,
                    "generic_checklist_mean_invention_rate": 0.1,
                    "freeform_mean_invention_rate": 0.2,
                },
                "conditions": {
                    "kernel": {
                        "mean_pickup_score": 1.0,
                        "mean_invention_rate": 0.0,
                        "mean_confidence": 0.99,
                        "mean_elapsed_ms": 20.0,
                        "rows": [
                            {
                                "artifact_class": "task",
                                "answers": {
                                    "object": "terminal trace widget",
                                    "goal": "surface lane drift",
                                },
                                "expected_present_fields": ["object", "goal"],
                                "invented_fields": [],
                            }
                        ],
                    },
                    "generic_checklist": {
                        "mean_pickup_score": 0.8,
                        "mean_invention_rate": 0.1,
                        "mean_confidence": 0.9,
                        "mean_elapsed_ms": 25.0,
                        "rows": [
                            {
                                "artifact_class": "task",
                                "answers": {
                                    "object": "terminal trace widget",
                                    "goal": None,
                                },
                                "expected_present_fields": ["object"],
                                "invented_fields": [],
                            }
                        ],
                    },
                    "freeform": {
                        "mean_pickup_score": 0.6,
                        "mean_invention_rate": 0.2,
                        "mean_confidence": 0.95,
                        "mean_elapsed_ms": 15.0,
                        "rows": [
                            {
                                "artifact_class": "task",
                                "answers": {
                                    "object": "terminal trace widget",
                                    "goal": "guessed goal",
                                },
                                "expected_present_fields": ["object"],
                                "invented_fields": ["goal"],
                            }
                        ],
                    },
                },
                "pairwise": {},
            },
            {
                "summary": {
                    "kernel_mean_pickup_score": 0.95,
                    "generic_checklist_mean_pickup_score": 0.75,
                    "freeform_mean_pickup_score": 0.55,
                    "kernel_mean_invention_rate": 0.0,
                    "generic_checklist_mean_invention_rate": 0.05,
                    "freeform_mean_invention_rate": 0.25,
                },
                "conditions": {
                    "kernel": {
                        "mean_pickup_score": 0.95,
                        "mean_invention_rate": 0.0,
                        "mean_confidence": 0.98,
                        "mean_elapsed_ms": 22.0,
                        "rows": [
                            {
                                "artifact_class": "task",
                                "answers": {
                                    "object": "terminal trace widget",
                                    "goal": "surface lane drift",
                                },
                                "expected_present_fields": ["object", "goal"],
                                "invented_fields": [],
                            }
                        ],
                    },
                    "generic_checklist": {
                        "mean_pickup_score": 0.75,
                        "mean_invention_rate": 0.05,
                        "mean_confidence": 0.88,
                        "mean_elapsed_ms": 26.0,
                        "rows": [
                            {
                                "artifact_class": "task",
                                "answers": {
                                    "object": "terminal trace widget",
                                    "goal": "surface lane drift",
                                },
                                "expected_present_fields": ["object"],
                                "invented_fields": ["goal"],
                            }
                        ],
                    },
                    "freeform": {
                        "mean_pickup_score": 0.55,
                        "mean_invention_rate": 0.25,
                        "mean_confidence": 0.94,
                        "mean_elapsed_ms": 16.0,
                        "rows": [
                            {
                                "artifact_class": "task",
                                "answers": {
                                    "object": "terminal trace widget",
                                    "goal": None,
                                },
                                "expected_present_fields": ["object"],
                                "invented_fields": [],
                            }
                        ],
                    },
                },
                "pairwise": {},
            },
        ]

        with mock.patch.object(module.AGENT_PILOT_MODULE, "build_report", side_effect=reports):
            report = module.build_report(model="", repeats=2, case_ids={"software_trace_widget"})

        self.assertTrue(report["summary"]["all_claims_pass"])
        self.assertEqual(report["conditions"]["kernel"]["mean_pickup_score"], 0.975)
        self.assertEqual(report["conditions"]["kernel"]["mean_invention_rate"], 0.0)
        self.assertGreater(
            report["conditions"]["kernel"]["mean_pickup_score"],
            report["conditions"]["generic_checklist"]["mean_pickup_score"],
        )
        kernel_rows = report["per_field_stability"]["kernel"]
        self.assertTrue(any(row["field"] == "object" for row in kernel_rows))
        self.assertTrue(any(row["field"] == "goal" for row in kernel_rows))

    def test_merge_reports_combines_runs(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "first.json"
            second = root / "second.json"
            first.write_text(
                json.dumps(
                    {
                        "runs": [
                            {
                                "run_index": 1,
                                "summary": {
                                    "kernel_mean_pickup_score": 1.0,
                                    "generic_checklist_mean_pickup_score": 0.8,
                                    "freeform_mean_pickup_score": 0.6,
                                    "kernel_mean_invention_rate": 0.0,
                                    "generic_checklist_mean_invention_rate": 0.1,
                                    "freeform_mean_invention_rate": 0.2,
                                },
                                "conditions": {
                                    "kernel": {"mean_pickup_score": 1.0, "mean_invention_rate": 0.0, "mean_confidence": 0.99, "mean_elapsed_ms": 20.0, "rows": []},
                                    "generic_checklist": {"mean_pickup_score": 0.8, "mean_invention_rate": 0.1, "mean_confidence": 0.9, "mean_elapsed_ms": 25.0, "rows": []},
                                    "freeform": {"mean_pickup_score": 0.6, "mean_invention_rate": 0.2, "mean_confidence": 0.95, "mean_elapsed_ms": 15.0, "rows": []},
                                },
                                "pairwise": {},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            second.write_text(
                json.dumps(
                    {
                        "runs": [
                            {
                                "run_index": 1,
                                "summary": {
                                    "kernel_mean_pickup_score": 0.95,
                                    "generic_checklist_mean_pickup_score": 0.75,
                                    "freeform_mean_pickup_score": 0.55,
                                    "kernel_mean_invention_rate": 0.0,
                                    "generic_checklist_mean_invention_rate": 0.05,
                                    "freeform_mean_invention_rate": 0.25,
                                },
                                "conditions": {
                                    "kernel": {"mean_pickup_score": 0.95, "mean_invention_rate": 0.0, "mean_confidence": 0.98, "mean_elapsed_ms": 22.0, "rows": []},
                                    "generic_checklist": {"mean_pickup_score": 0.75, "mean_invention_rate": 0.05, "mean_confidence": 0.88, "mean_elapsed_ms": 26.0, "rows": []},
                                    "freeform": {"mean_pickup_score": 0.55, "mean_invention_rate": 0.25, "mean_confidence": 0.94, "mean_elapsed_ms": 16.0, "rows": []},
                                },
                                "pairwise": {},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            report = module.merge_reports([first, second], model="")
        self.assertEqual(len(report["runs"]), 2)
        self.assertEqual(report["conditions"]["kernel"]["mean_pickup_score"], 0.975)
        self.assertEqual(report["metadata"]["source_reports"], [str(first), str(second)])


if __name__ == "__main__":
    unittest.main()
