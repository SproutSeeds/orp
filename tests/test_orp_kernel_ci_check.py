from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-kernel-ci-check.py"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class OrpKernelCiCheckTests(unittest.TestCase):
    def test_ci_check_passes_with_expected_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = {
                "comparison": root / "comparison.json",
                "pickup": root / "pickup.json",
                "agent_pilot": root / "agent.json",
                "replication": root / "replication.json",
                "canonical_continuation": root / "canonical.json",
            }
            shared_claims = [{"id": "ok", "status": "pass"}]
            _write_json(paths["comparison"], {"summary": {"kernel_mean_total_score": 1.0, "generic_checklist_mean_total_score": 0.8, "freeform_mean_total_score": 0.4}, "claims": shared_claims})
            _write_json(paths["pickup"], {"summary": {"kernel_mean_pickup_score": 1.0, "generic_checklist_mean_pickup_score": 0.8, "freeform_mean_pickup_score": 0.4}, "claims": shared_claims})
            _write_json(paths["agent_pilot"], {"summary": {"kernel_mean_pickup_score": 1.0, "generic_checklist_mean_pickup_score": 0.8, "freeform_mean_pickup_score": 0.4}, "claims": shared_claims})
            _write_json(paths["replication"], {"summary": {"kernel_mean_pickup_score": 1.0, "generic_checklist_mean_pickup_score": 0.8, "freeform_mean_pickup_score": 0.4, "kernel_mean_invention_rate": 0.0, "generic_checklist_mean_invention_rate": 0.0, "freeform_mean_invention_rate": 0.1}, "claims": shared_claims})
            _write_json(paths["canonical_continuation"], {"summary": {"kernel_mean_total_score": 0.8, "generic_checklist_mean_total_score": 0.7, "freeform_mean_total_score": 0.5, "kernel_mean_invention_rate": 0.1, "generic_checklist_mean_invention_rate": 0.2, "freeform_mean_invention_rate": 0.3}, "claims": [{"id": "nuanced", "status": "fail"}]})

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--comparison",
                    str(paths["comparison"]),
                    "--pickup",
                    str(paths["pickup"]),
                    "--agent-pilot",
                    str(paths["agent_pilot"]),
                    "--replication",
                    str(paths["replication"]),
                    "--canonical-continuation",
                    str(paths["canonical_continuation"]),
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

    def test_ci_check_fails_when_kernel_drops_below_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = {
                "comparison": root / "comparison.json",
                "pickup": root / "pickup.json",
                "agent_pilot": root / "agent.json",
                "replication": root / "replication.json",
                "canonical_continuation": root / "canonical.json",
            }
            shared_claims = [{"id": "ok", "status": "pass"}]
            _write_json(paths["comparison"], {"summary": {"kernel_mean_total_score": 1.0, "generic_checklist_mean_total_score": 0.8, "freeform_mean_total_score": 0.4}, "claims": shared_claims})
            _write_json(paths["pickup"], {"summary": {"kernel_mean_pickup_score": 1.0, "generic_checklist_mean_pickup_score": 0.8, "freeform_mean_pickup_score": 0.4}, "claims": shared_claims})
            _write_json(paths["agent_pilot"], {"summary": {"kernel_mean_pickup_score": 1.0, "generic_checklist_mean_pickup_score": 0.8, "freeform_mean_pickup_score": 0.4}, "claims": shared_claims})
            _write_json(paths["replication"], {"summary": {"kernel_mean_pickup_score": 0.7, "generic_checklist_mean_pickup_score": 0.8, "freeform_mean_pickup_score": 0.4, "kernel_mean_invention_rate": 0.0, "generic_checklist_mean_invention_rate": 0.0, "freeform_mean_invention_rate": 0.1}, "claims": shared_claims})
            _write_json(paths["canonical_continuation"], {"summary": {"kernel_mean_total_score": 0.8, "generic_checklist_mean_total_score": 0.7, "freeform_mean_total_score": 0.5, "kernel_mean_invention_rate": 0.1, "generic_checklist_mean_invention_rate": 0.2, "freeform_mean_invention_rate": 0.3}, "claims": [{"id": "nuanced", "status": "fail"}]})

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--comparison",
                    str(paths["comparison"]),
                    "--pickup",
                    str(paths["pickup"]),
                    "--agent-pilot",
                    str(paths["agent_pilot"]),
                    "--replication",
                    str(paths["replication"]),
                    "--canonical-continuation",
                    str(paths["canonical_continuation"]),
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("replication summary preserves kernel > checklist > free-form", proc.stdout)


if __name__ == "__main__":
    unittest.main()
