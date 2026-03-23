from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"
CORPUS_ROOT = REPO_ROOT / "examples" / "kernel" / "corpus"
VALID_REQUIREMENT_FIXTURES = {
    "task": {
        "schema_version": "1.0.0",
        "artifact_class": "task",
        "object": "terminal trace widget",
        "goal": "surface lane drift",
        "boundary": "terminal-first lane visibility",
        "constraints": ["low friction"],
        "success_criteria": ["operator spots drift quickly"],
    },
    "decision": {
        "schema_version": "1.0.0",
        "artifact_class": "decision",
        "question": "what should the home screen emphasize first?",
        "chosen_path": "linked projects first",
        "rejected_alternatives": ["idea board default"],
        "rationale": "active work should be foregrounded",
        "consequences": ["idea browsing becomes secondary navigation"],
    },
    "hypothesis": {
        "schema_version": "1.0.0",
        "artifact_class": "hypothesis",
        "claim": "drift summaries reduce missed stalled lanes",
        "boundary": "terminal-first multi-lane workflows",
        "assumptions": ["operators consult summaries while working"],
        "test_path": "compare stalled-lane detection with and without summaries",
        "falsifiers": ["no measurable pickup improvement"],
    },
    "experiment": {
        "schema_version": "1.0.0",
        "artifact_class": "experiment",
        "objective": "measure whether kernel tasks improve handoff pickup",
        "method": "run matched handoff trials",
        "inputs": ["task prompts", "reviewers"],
        "outputs": ["pickup scores", "clarification counts"],
        "evidence_expectations": ["ratings", "artifact corpus"],
        "interpretation_limits": ["small internal sample"],
    },
    "checkpoint": {
        "schema_version": "1.0.0",
        "artifact_class": "checkpoint",
        "completed_unit": "restored canonical runner routing",
        "current_state": "linked project and session are synchronized",
        "risks": ["inactive machines may still need a sync"],
        "next_handoff_target": "rerun runner sync on active machines",
        "artifact_refs": [".git/orp/link/project.json", "orp/HANDOFF.md"],
    },
    "policy": {
        "schema_version": "1.0.0",
        "artifact_class": "policy",
        "scope": "hosted runner job pickup",
        "rule": "route only to linked projects with routeable local sessions",
        "rationale": "prevent unroutable job claims",
        "invariants": ["claimed jobs must have a real local execution target"],
        "enforcement_surface": "runner sync poll and work lifecycle",
    },
    "result": {
        "schema_version": "1.0.0",
        "artifact_class": "result",
        "claim": "ORP ships a real reasoning kernel with enforceable promotion semantics",
        "evidence_paths": [
            "docs/ORP_REASONING_KERNEL_V0_1.md",
            "docs/ORP_REASONING_KERNEL_TECHNICAL_VALIDATION.md",
        ],
        "status": "shipped in ORP CLI",
        "interpretation_limits": ["comparative superiority is not yet proven"],
        "next_follow_up": "run comparative artifact and handoff studies",
    },
}


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_kernel_tests", CLI)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load CLI module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_cli(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [sys.executable, str(CLI), "--repo-root", str(root), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr + "\n" + proc.stdout)
    return proc


class OrpKernelCorpusTests(unittest.TestCase):
    def test_schema_and_cli_requirements_stay_aligned(self) -> None:
        schema = json.loads((REPO_ROOT / "spec" / "v1" / "kernel.schema.json").read_text(encoding="utf-8"))
        schema_requirements = {}
        for clause in schema.get("allOf", []):
            if not isinstance(clause, dict):
                continue
            const = (
                clause.get("if", {})
                .get("properties", {})
                .get("artifact_class", {})
                .get("const")
            )
            required = clause.get("then", {}).get("required")
            if isinstance(const, str) and isinstance(required, list):
                schema_requirements[const] = [str(x) for x in required if isinstance(x, str)]

        cli_module = _load_cli_module()
        self.assertEqual(schema_requirements, dict(cli_module.KERNEL_ARTIFACT_CLASS_REQUIREMENTS))
        self.assertEqual(set(schema.get("properties", {}).keys()), set(cli_module.KERNEL_ALLOWED_FIELDS))

    def test_cross_domain_corpus_examples_validate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixtures = sorted(
                path for path in CORPUS_ROOT.rglob("*") if path.is_file() and path.suffix.lower() in {".yml", ".yaml", ".json"}
            )
            self.assertGreaterEqual(len(fixtures), 7)
            domains = set()
            artifact_classes = set()
            for fixture in fixtures:
                rel = fixture.relative_to(CORPUS_ROOT)
                domains.add(rel.parts[0])
                target = root / "analysis" / rel.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
                proc = _run_cli(root, "kernel", "validate", str(target.relative_to(root)), "--json")
                payload = json.loads(proc.stdout)
                self.assertTrue(payload["ok"], msg=proc.stderr + "\n" + proc.stdout)
                artifact_classes.add(payload["artifact_result"]["artifact_class"])

            self.assertGreaterEqual(len(domains), 5)
            self.assertEqual(artifact_classes, set(VALID_REQUIREMENT_FIXTURES.keys()))

    def test_each_artifact_class_detects_missing_required_field(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for artifact_class, payload in VALID_REQUIREMENT_FIXTURES.items():
                required_fields = [field for field in payload.keys() if field not in {"schema_version", "artifact_class"}]
                removed_field = required_fields[-1]
                invalid_payload = dict(payload)
                invalid_payload.pop(removed_field, None)
                target = root / "analysis" / f"{artifact_class}.invalid.kernel.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(invalid_payload, indent=2) + "\n", encoding="utf-8")
                proc = _run_cli(
                    root,
                    "kernel",
                    "validate",
                    str(target.relative_to(root)),
                    "--artifact-class",
                    artifact_class,
                    "--json",
                    check=False,
                )
                self.assertEqual(proc.returncode, 1, msg=proc.stderr + "\n" + proc.stdout)
                payload_out = json.loads(proc.stdout)
                self.assertFalse(payload_out["ok"])
                self.assertIn(removed_field, payload_out["artifact_result"]["missing_fields"])

    def test_kernel_validate_rejects_unknown_field_and_bad_shape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "analysis" / "bad-task.kernel.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                **VALID_REQUIREMENT_FIXTURES["task"],
                "constraints": {"bad": True},
                "mystery_field": "nope",
            }
            target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            proc = _run_cli(
                root,
                "kernel",
                "validate",
                str(target.relative_to(root)),
                "--artifact-class",
                "task",
                "--json",
                check=False,
            )
            self.assertEqual(proc.returncode, 1, msg=proc.stderr + "\n" + proc.stdout)
            payload_out = json.loads(proc.stdout)
            issues = payload_out["artifact_result"]["issues"]
            self.assertTrue(any("unexpected field" in issue for issue in issues))
            self.assertTrue(any("field `constraints`" in issue for issue in issues))

    def test_yaml_and_json_equivalent_artifacts_validate_the_same(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            yaml_path = root / "analysis" / "task.kernel.yml"
            json_path = root / "analysis" / "task.kernel.json"
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text(
                'schema_version: "1.0.0"\n'
                "artifact_class: task\n"
                "object: terminal trace widget\n"
                "goal: surface lane drift\n"
                "boundary:\n"
                "  - terminal-first lane visibility\n"
                "constraints:\n"
                "  - low friction\n"
                "success_criteria:\n"
                "  - operator spots drift quickly\n",
                encoding="utf-8",
            )
            json_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "artifact_class": "task",
                        "object": "terminal trace widget",
                        "goal": "surface lane drift",
                        "boundary": ["terminal-first lane visibility"],
                        "constraints": ["low friction"],
                        "success_criteria": ["operator spots drift quickly"],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            yaml_proc = _run_cli(root, "kernel", "validate", str(yaml_path.relative_to(root)), "--json")
            json_proc = _run_cli(root, "kernel", "validate", str(json_path.relative_to(root)), "--json")
            yaml_payload = json.loads(yaml_proc.stdout)
            json_payload = json.loads(json_proc.stdout)
            yaml_result = {k: v for k, v in yaml_payload["artifact_result"].items() if k != "path"}
            json_result = {k: v for k, v in json_payload["artifact_result"].items() if k != "path"}
            self.assertTrue(yaml_payload["ok"])
            self.assertTrue(json_payload["ok"])
            self.assertEqual(yaml_result, json_result)


if __name__ == "__main__":
    unittest.main()
