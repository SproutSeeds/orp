from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-kernel-pickup.py"


class OrpKernelPickupTests(unittest.TestCase):
    def test_pickup_report_has_expected_shape_and_ordering(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["kind"], "orp_reasoning_kernel_pickup_report")
        self.assertTrue(payload["summary"]["all_claims_pass"])

        kernel_score = payload["summary"]["kernel_mean_pickup_score"]
        checklist_score = payload["summary"]["generic_checklist_mean_pickup_score"]
        freeform_score = payload["summary"]["freeform_mean_pickup_score"]

        self.assertGreater(kernel_score, checklist_score)
        self.assertGreater(checklist_score, freeform_score)
        self.assertEqual(payload["pairwise"]["kernel_vs_generic_checklist"]["losses"], 0)
        self.assertEqual(payload["pairwise"]["kernel_vs_freeform"]["losses"], 0)
        self.assertEqual(payload["pairwise"]["generic_checklist_vs_freeform"]["losses"], 0)


if __name__ == "__main__":
    unittest.main()
