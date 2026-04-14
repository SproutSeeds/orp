from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-kernel-benchmark.py"


def load_benchmark_module():
    spec = importlib.util.spec_from_file_location("orp_kernel_benchmark_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpKernelBenchmarkTests(unittest.TestCase):
    def test_kernel_benchmark_cli_help_loads(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        self.assertIn("--quick", proc.stdout)

    def test_quick_kernel_benchmark_report_has_expected_shape_and_functional_claims(self) -> None:
        module = load_benchmark_module()

        def stats(mean_ms: float) -> dict[str, float]:
            return {
                "mean_ms": mean_ms,
                "median_ms": mean_ms,
                "min_ms": mean_ms,
                "max_ms": mean_ms,
            }

        def timing_targets() -> dict[str, float]:
            return {
                "scaffold_mean_lt_ms": 100.0,
                "validate_mean_lt_ms": 100.0,
            }

        module._gather_metadata = lambda: {
            "generated_at_utc": "2026-04-14T00:00:00Z",
            "repo_commit": "test",
            "repo_branch": "test",
            "package_version": "0.0.0",
            "python_version": "test",
            "node_version": "test",
            "platform": "test",
        }
        module._benchmark_init_starter = lambda iterations: {
            "iterations": iterations,
            "observed": {
                "init": stats(200.0),
                "validate": stats(200.0),
                "gate_run": stats(200.0),
            },
            "targets": {
                "init_mean_lt_ms": 100.0,
                "validate_mean_lt_ms": 100.0,
                "gate_mean_lt_ms": 100.0,
            },
            "meets_targets": {
                "init": False,
                "validate": False,
                "gate_run": False,
            },
            "sample_run_records": [],
        }
        module._benchmark_artifact_roundtrip = lambda: {
            "artifact_classes_total": 7,
            "rows": [],
            "observed": {
                "scaffold": stats(200.0),
                "validate": stats(200.0),
            },
            "targets": timing_targets(),
            "meets_targets": {
                "scaffold": False,
                "validate": False,
            },
        }
        module._benchmark_gate_modes = lambda: {
            "meets_expectations": {
                "hard_blocks_invalid_artifact": True,
                "soft_allows_invalid_artifact_with_advisory": True,
                "legacy_structure_kernel_remains_compatible": True,
            },
        }
        module._benchmark_schema_alignment = lambda: {
            "meets_expectations": {
                "requirements_match": True,
                "fields_match": True,
            },
        }
        module._benchmark_cross_domain_corpus = lambda: {
            "fixtures_total": 7,
            "domains_total": 5,
            "artifact_classes_total": 7,
            "rows": [],
            "observed": {
                "validate": stats(200.0),
            },
            "targets": {
                "domains_min": 5,
                "fixtures_min": 7,
                "validate_mean_lt_ms": 100.0,
            },
            "meets_targets": {
                "domains": True,
                "fixtures": True,
                "validate": False,
            },
        }
        module._benchmark_requirement_enforcement = lambda: {
            "cases_total": 36,
            "rows": [],
            "observed": {
                "validate": stats(200.0),
            },
            "targets": {
                "cases_total": 36,
                "validate_mean_lt_ms": 100.0,
            },
            "meets_targets": {
                "all_cases_detected": True,
                "validate": False,
            },
        }
        module._benchmark_representation_invariance = lambda: {
            "meets_expectations": {
                "both_valid": True,
                "equivalent_results": True,
            },
        }
        module._benchmark_mutation_stress = lambda: {
            "cases_total": 7,
            "rows": [],
            "observed": {
                "validate": stats(200.0),
            },
            "targets": {
                "cases_total": 7,
                "validate_mean_lt_ms": 100.0,
            },
            "meets_targets": {
                "all_cases_detected": True,
                "validate": False,
            },
        }

        payload = module.build_report(iterations=1, quick=True)

        self.assertEqual(payload["kind"], "orp_reasoning_kernel_validation_report")
        self.assertEqual(payload["summary"]["artifact_classes_total"], 7)
        for key in (
            "init_starter_kernel",
            "artifact_roundtrip",
            "gate_modes",
            "schema_alignment",
            "cross_domain_corpus",
            "requirement_enforcement",
            "representation_invariance",
            "mutation_stress",
        ):
            self.assertIn(key, payload["benchmarks"])
        self.assertGreaterEqual(payload["summary"]["cross_domain_corpus_domains_total"], 5)

        # Live benchmark timing is intentionally reported, but the unit suite
        # should fail only for broken functional evidence. Committed benchmark
        # artifact thresholds are checked separately by scripts/orp-kernel-ci-check.py.
        allowed_timing_claims = {
            "local_cli_kernel_ergonomics",
            "cross_domain_corpus_fit",
            "class_specific_requirement_enforcement",
            "adversarial_mutation_detection",
        }
        failed_claims = {
            str(row.get("id", ""))
            for row in payload["claims"]
            if str(row.get("status", "")).lower() != "pass"
        }
        self.assertFalse(failed_claims - allowed_timing_claims)

        corpus = payload["benchmarks"]["cross_domain_corpus"]
        self.assertTrue(corpus["meets_targets"]["domains"])
        self.assertTrue(corpus["meets_targets"]["fixtures"])
        self.assertGreaterEqual(corpus["artifact_classes_total"], 7)

        requirements = payload["benchmarks"]["requirement_enforcement"]
        self.assertTrue(requirements["meets_targets"]["all_cases_detected"])

        mutations = payload["benchmarks"]["mutation_stress"]
        self.assertTrue(mutations["meets_targets"]["all_cases_detected"])


if __name__ == "__main__":
    unittest.main()
