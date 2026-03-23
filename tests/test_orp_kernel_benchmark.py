from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-kernel-benchmark.py"


class OrpKernelBenchmarkTests(unittest.TestCase):
    def test_quick_kernel_benchmark_report_passes_and_has_expected_shape(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--quick"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["kind"], "orp_reasoning_kernel_validation_report")
        self.assertTrue(payload["summary"]["all_claims_pass"])
        self.assertEqual(payload["summary"]["artifact_classes_total"], 7)
        self.assertIn("init_starter_kernel", payload["benchmarks"])
        self.assertIn("artifact_roundtrip", payload["benchmarks"])
        self.assertIn("gate_modes", payload["benchmarks"])
        self.assertIn("schema_alignment", payload["benchmarks"])
        self.assertIn("cross_domain_corpus", payload["benchmarks"])
        self.assertIn("requirement_enforcement", payload["benchmarks"])
        self.assertIn("representation_invariance", payload["benchmarks"])
        self.assertIn("mutation_stress", payload["benchmarks"])
        self.assertGreaterEqual(payload["summary"]["cross_domain_corpus_domains_total"], 5)


if __name__ == "__main__":
    unittest.main()
