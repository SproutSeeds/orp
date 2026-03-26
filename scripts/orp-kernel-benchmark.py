#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = ["node", "bin/orp.js"]
CORPUS_ROOT = REPO_ROOT / "examples" / "kernel" / "corpus"
ARTIFACT_CLASSES = [
    "task",
    "decision",
    "hypothesis",
    "experiment",
    "checkpoint",
    "policy",
    "result",
]
VALID_REQUIREMENT_FIXTURES: dict[str, dict[str, Any]] = {
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
        "current_state": "linked project and primary session are synchronized",
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


def _run(
    args: list[str],
    *,
    cwd: Path = REPO_ROOT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(args)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def _run_orp(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run([*CLI, "--repo-root", str(repo_root), *args], check=check)


def _timed_orp(repo_root: Path, *args: str, check: bool = True) -> tuple[float, subprocess.CompletedProcess[str]]:
    started = time.perf_counter()
    proc = _run_orp(repo_root, *args, check=check)
    return (time.perf_counter() - started) * 1000.0, proc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean_ms": round(statistics.mean(values), 3),
        "median_ms": round(statistics.median(values), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def _load_cli_module() -> Any:
    module_path = REPO_ROOT / "cli" / "orp.py"
    spec = importlib.util.spec_from_file_location("orp_cli_kernel_benchmark", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load CLI module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_kernel_schema_requirements() -> dict[str, list[str]]:
    schema_path = REPO_ROOT / "spec" / "v1" / "kernel.schema.json"
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for clause in payload.get("allOf", []):
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
            out[const] = [str(x) for x in required if isinstance(x, str)]
    return out


def _benchmark_init_starter(iterations: int) -> dict[str, Any]:
    init_times: list[float] = []
    validate_times: list[float] = []
    gate_times: list[float] = []
    run_records: list[str] = []

    for _ in range(iterations):
        with tempfile.TemporaryDirectory(prefix="orp-kernel-bench-init.") as td:
            root = Path(td)
            _run(["git", "init", str(root)])
            init_ms, init_proc = _timed_orp(root, "init", "--json")
            init_payload = json.loads(init_proc.stdout)
            validate_ms, validate_proc = _timed_orp(
                root, "kernel", "validate", "analysis/orp.kernel.task.yml", "--json"
            )
            validate_payload = json.loads(validate_proc.stdout)
            gate_ms, gate_proc = _timed_orp(root, "gate", "run", "--profile", "default", "--json")
            gate_payload = json.loads(gate_proc.stdout)

            if not init_payload.get("ok"):
                raise RuntimeError("orp init benchmark did not report ok=true")
            if not validate_payload.get("ok"):
                raise RuntimeError("starter kernel validate benchmark did not report ok=true")
            if gate_payload.get("overall") != "PASS":
                raise RuntimeError("starter kernel gate benchmark did not pass")

            init_times.append(init_ms)
            validate_times.append(validate_ms)
            gate_times.append(gate_ms)
            run_records.append(gate_payload["run_record"])

    targets = {
        "init_mean_lt_ms": 350.0,
        "validate_mean_lt_ms": 200.0,
        "gate_mean_lt_ms": 325.0,
    }
    observed = {
        "init": _stats(init_times),
        "validate": _stats(validate_times),
        "gate_run": _stats(gate_times),
    }
    return {
        "iterations": iterations,
        "observed": observed,
        "targets": targets,
        "meets_targets": {
            "init": observed["init"]["mean_ms"] < targets["init_mean_lt_ms"],
            "validate": observed["validate"]["mean_ms"] < targets["validate_mean_lt_ms"],
            "gate_run": observed["gate_run"]["mean_ms"] < targets["gate_mean_lt_ms"],
        },
        "sample_run_records": run_records[:2],
    }


def _benchmark_artifact_roundtrip() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    scaffold_times: list[float] = []
    validate_times: list[float] = []

    for artifact_class in ARTIFACT_CLASSES:
        with tempfile.TemporaryDirectory(prefix=f"orp-kernel-bench-{artifact_class}.") as td:
            root = Path(td)
            path = f"analysis/{artifact_class}.kernel.yml"
            scaffold_ms, scaffold_proc = _timed_orp(
                root,
                "kernel",
                "scaffold",
                "--artifact-class",
                artifact_class,
                "--out",
                path,
                "--name",
                f"{artifact_class} benchmark",
                "--json",
            )
            validate_ms, validate_proc = _timed_orp(root, "kernel", "validate", path, "--json")
            scaffold_payload = json.loads(scaffold_proc.stdout)
            validate_payload = json.loads(validate_proc.stdout)
            if not scaffold_payload.get("ok") or not validate_payload.get("ok"):
                raise RuntimeError(f"roundtrip benchmark failed for artifact_class={artifact_class}")
            scaffold_times.append(scaffold_ms)
            validate_times.append(validate_ms)
            rows.append(
                {
                    "artifact_class": artifact_class,
                    "scaffold_ms": round(scaffold_ms, 3),
                    "validate_ms": round(validate_ms, 3),
                }
            )

    observed = {
        "scaffold": _stats(scaffold_times),
        "validate": _stats(validate_times),
    }
    targets = {
        "scaffold_mean_lt_ms": 200.0,
        "validate_mean_lt_ms": 200.0,
    }
    return {
        "artifact_classes_total": len(rows),
        "rows": rows,
        "observed": observed,
        "targets": targets,
        "meets_targets": {
            "scaffold": observed["scaffold"]["mean_ms"] < targets["scaffold_mean_lt_ms"],
            "validate": observed["validate"]["mean_ms"] < targets["validate_mean_lt_ms"],
        },
    }


def _benchmark_gate_modes() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="orp-kernel-bench-gates.") as td:
        root = Path(td)
        _write_json(
            root / "analysis" / "invalid-task.kernel.json",
            {
                "schema_version": "1.0.0",
                "artifact_class": "task",
                "object": "terminal trace widget",
                "goal": "surface lane state and drift",
                "boundary": "terminal-first workflow",
            },
        )
        _write_json(
            root / "orp.kernel.bench.json",
            {
                "profiles": {
                    "hard": {
                        "description": "hard kernel gate",
                        "mode": "test",
                        "packet_kind": "problem_scope",
                        "gate_ids": ["kernel_hard"],
                    },
                    "soft": {
                        "description": "soft kernel gate",
                        "mode": "test",
                        "packet_kind": "problem_scope",
                        "gate_ids": ["kernel_soft"],
                    },
                    "legacy": {
                        "description": "legacy structure kernel gate",
                        "mode": "test",
                        "packet_kind": "problem_scope",
                        "gate_ids": ["kernel_legacy"],
                    },
                },
                "gates": [
                    {
                        "id": "kernel_hard",
                        "phase": "structure_kernel",
                        "command": "true",
                        "pass": {"exit_codes": [0]},
                        "kernel": {
                            "mode": "hard",
                            "artifacts": [
                                {
                                    "path": "analysis/invalid-task.kernel.json",
                                    "artifact_class": "task",
                                }
                            ],
                        },
                    },
                    {
                        "id": "kernel_soft",
                        "phase": "structure_kernel",
                        "command": "true",
                        "pass": {"exit_codes": [0]},
                        "kernel": {
                            "mode": "soft",
                            "artifacts": [
                                {
                                    "path": "analysis/invalid-task.kernel.json",
                                    "artifact_class": "task",
                                }
                            ],
                        },
                    },
                    {
                        "id": "kernel_legacy",
                        "phase": "structure_kernel",
                        "command": "true",
                        "pass": {"exit_codes": [0]},
                    },
                ],
            },
        )

        hard_ms, hard_proc = _timed_orp(
            root,
            "--config",
            "orp.kernel.bench.json",
            "gate",
            "run",
            "--profile",
            "hard",
            "--json",
            check=False,
        )
        soft_ms, soft_proc = _timed_orp(
            root,
            "--config",
            "orp.kernel.bench.json",
            "gate",
            "run",
            "--profile",
            "soft",
            "--json",
        )
        legacy_ms, legacy_proc = _timed_orp(
            root,
            "--config",
            "orp.kernel.bench.json",
            "gate",
            "run",
            "--profile",
            "legacy",
            "--json",
        )

        hard_payload = json.loads(hard_proc.stdout)
        soft_payload = json.loads(soft_proc.stdout)
        legacy_payload = json.loads(legacy_proc.stdout)

        hard_result = json.loads((root / hard_payload["run_record"]).read_text(encoding="utf-8"))["results"][0]
        soft_result = json.loads((root / soft_payload["run_record"]).read_text(encoding="utf-8"))["results"][0]
        legacy_result = json.loads((root / legacy_payload["run_record"]).read_text(encoding="utf-8"))["results"][0]

        return {
            "hard_mode": {
                "ms": round(hard_ms, 3),
                "exit_code": hard_proc.returncode,
                "overall": hard_payload["overall"],
                "kernel_valid": hard_result["kernel_validation"]["valid"],
                "missing_fields": hard_result["kernel_validation"]["artifacts"][0]["missing_fields"],
            },
            "soft_mode": {
                "ms": round(soft_ms, 3),
                "exit_code": soft_proc.returncode,
                "overall": soft_payload["overall"],
                "kernel_valid": soft_result["kernel_validation"]["valid"],
            },
            "legacy_compatibility": {
                "ms": round(legacy_ms, 3),
                "exit_code": legacy_proc.returncode,
                "overall": legacy_payload["overall"],
                "has_kernel_validation": "kernel_validation" in legacy_result,
            },
            "meets_expectations": {
                "hard_blocks_invalid_artifact": hard_proc.returncode == 1
                and hard_payload["overall"] == "FAIL"
                and hard_result["kernel_validation"]["valid"] is False,
                "soft_allows_invalid_artifact_with_advisory": soft_proc.returncode == 0
                and soft_payload["overall"] == "PASS"
                and soft_result["kernel_validation"]["valid"] is False,
                "legacy_structure_kernel_remains_compatible": legacy_proc.returncode == 0
                and legacy_payload["overall"] == "PASS"
                and "kernel_validation" not in legacy_result,
            },
        }


def _benchmark_schema_alignment() -> dict[str, Any]:
    cli_module = _load_cli_module()
    schema_requirements = _load_kernel_schema_requirements()
    cli_requirements = dict(getattr(cli_module, "KERNEL_ARTIFACT_CLASS_REQUIREMENTS", {}))
    schema_fields = set(json.loads((REPO_ROOT / "spec" / "v1" / "kernel.schema.json").read_text(encoding="utf-8")).get("properties", {}).keys())
    cli_fields = set(getattr(cli_module, "KERNEL_ALLOWED_FIELDS", set()))
    return {
        "schema_requirements": schema_requirements,
        "cli_requirements": cli_requirements,
        "schema_fields_total": len(schema_fields),
        "cli_fields_total": len(cli_fields),
        "meets_expectations": {
            "requirements_match": schema_requirements == cli_requirements,
            "fields_match": schema_fields == cli_fields,
        },
    }


def _benchmark_cross_domain_corpus() -> dict[str, Any]:
    if not CORPUS_ROOT.exists():
        raise RuntimeError(f"kernel corpus root is missing: {CORPUS_ROOT}")

    rows: list[dict[str, Any]] = []
    validate_times: list[float] = []
    domains: set[str] = set()
    classes: set[str] = set()
    files = sorted(
        path for path in CORPUS_ROOT.rglob("*") if path.is_file() and path.suffix.lower() in {".yml", ".yaml", ".json"}
    )
    if not files:
        raise RuntimeError(f"kernel corpus root has no fixtures: {CORPUS_ROOT}")

    with tempfile.TemporaryDirectory(prefix="orp-kernel-bench-corpus.") as td:
        root = Path(td)
        for path in files:
            rel = path.relative_to(CORPUS_ROOT)
            domain = rel.parts[0] if len(rel.parts) > 1 else "unknown"
            domains.add(domain)
            target = root / "analysis" / rel.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            validate_ms, validate_proc = _timed_orp(root, "kernel", "validate", str(target.relative_to(root)), "--json")
            validate_payload = json.loads(validate_proc.stdout)
            if not validate_payload.get("ok"):
                raise RuntimeError(f"corpus benchmark failed for fixture={rel}")
            classes.add(validate_payload["artifact_result"]["artifact_class"])
            validate_times.append(validate_ms)
            rows.append(
                {
                    "fixture": rel.as_posix(),
                    "domain": domain,
                    "artifact_class": validate_payload["artifact_result"]["artifact_class"],
                    "validate_ms": round(validate_ms, 3),
                }
            )

    observed = {"validate": _stats(validate_times)}
    targets = {
        "domains_min": 5,
        "fixtures_min": 7,
        "validate_mean_lt_ms": 200.0,
    }
    return {
        "fixtures_total": len(rows),
        "domains_total": len(domains),
        "artifact_classes_total": len(classes),
        "rows": rows,
        "observed": observed,
        "targets": targets,
        "meets_targets": {
            "domains": len(domains) >= targets["domains_min"],
            "fixtures": len(rows) >= targets["fixtures_min"],
            "validate": observed["validate"]["mean_ms"] < targets["validate_mean_lt_ms"],
        },
    }


def _benchmark_requirement_enforcement() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    validate_times: list[float] = []
    total_missing_cases = 0
    requirements = _load_kernel_schema_requirements()

    with tempfile.TemporaryDirectory(prefix="orp-kernel-bench-requirements.") as td:
        root = Path(td)
        for artifact_class, payload in VALID_REQUIREMENT_FIXTURES.items():
            for removed_field in requirements[artifact_class]:
                invalid_payload = dict(payload)
                invalid_payload.pop(removed_field, None)
                target = root / "analysis" / f"{artifact_class}.{removed_field}.invalid.kernel.json"
                _write_json(target, invalid_payload)
                validate_ms, validate_proc = _timed_orp(
                    root,
                    "kernel",
                    "validate",
                    str(target.relative_to(root)),
                    "--artifact-class",
                    artifact_class,
                    "--json",
                    check=False,
                )
                validate_payload = json.loads(validate_proc.stdout)
                validate_times.append(validate_ms)
                artifact_result = validate_payload["artifact_result"]
                total_missing_cases += 1 if removed_field in artifact_result.get("missing_fields", []) else 0
                rows.append(
                    {
                        "artifact_class": artifact_class,
                        "removed_field": removed_field,
                        "exit_code": validate_proc.returncode,
                        "valid": artifact_result.get("valid", validate_payload.get("ok", False)),
                        "missing_fields": artifact_result.get("missing_fields", []),
                        "validate_ms": round(validate_ms, 3),
                    }
                )

    observed = {"validate": _stats(validate_times)}
    targets = {
        "all_cases_detected": sum(len(fields) for fields in requirements.values()),
        "validate_mean_lt_ms": 200.0,
    }
    return {
        "cases_total": len(rows),
        "rows": rows,
        "observed": observed,
        "targets": targets,
        "meets_targets": {
            "all_cases_detected": total_missing_cases == targets["all_cases_detected"]
            and all(row["exit_code"] == 1 for row in rows)
            and all(row["valid"] is False for row in rows),
            "validate": observed["validate"]["mean_ms"] < targets["validate_mean_lt_ms"],
        },
    }


def _benchmark_representation_invariance() -> dict[str, Any]:
    yaml_body = (
        'schema_version: "1.0.0"\n'
        "artifact_class: task\n"
        "object: terminal trace widget\n"
        "goal: surface lane drift\n"
        "boundary:\n"
        "  - terminal-first lane visibility\n"
        "constraints:\n"
        "  - low friction\n"
        "success_criteria:\n"
        "  - operator spots drift quickly\n"
    )
    json_body = {
        "schema_version": "1.0.0",
        "artifact_class": "task",
        "object": "terminal trace widget",
        "goal": "surface lane drift",
        "boundary": ["terminal-first lane visibility"],
        "constraints": ["low friction"],
        "success_criteria": ["operator spots drift quickly"],
    }

    with tempfile.TemporaryDirectory(prefix="orp-kernel-bench-invariance.") as td:
        root = Path(td)
        yaml_path = root / "analysis" / "task.kernel.yml"
        json_path = root / "analysis" / "task.kernel.json"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_path.write_text(yaml_body, encoding="utf-8")
        _write_json(json_path, json_body)

        yaml_ms, yaml_proc = _timed_orp(root, "kernel", "validate", str(yaml_path.relative_to(root)), "--json")
        json_ms, json_proc = _timed_orp(root, "kernel", "validate", str(json_path.relative_to(root)), "--json")
        yaml_payload = json.loads(yaml_proc.stdout)
        json_payload = json.loads(json_proc.stdout)
        yaml_result = yaml_payload["artifact_result"]
        json_result = json_payload["artifact_result"]

        comparable_yaml = {k: v for k, v in yaml_result.items() if k != "path"}
        comparable_json = {k: v for k, v in json_result.items() if k != "path"}
        return {
            "yaml_ms": round(yaml_ms, 3),
            "json_ms": round(json_ms, 3),
            "yaml_result": yaml_result,
            "json_result": json_result,
            "meets_expectations": {
                "both_valid": yaml_payload["ok"] and json_payload["ok"],
                "equivalent_results": comparable_yaml == comparable_json,
            },
        }


def _benchmark_mutation_stress() -> dict[str, Any]:
    cases = [
        {
            "id": "unexpected_field",
            "artifact_class": "task",
            "payload": {
                **VALID_REQUIREMENT_FIXTURES["task"],
                "mystery_field": "should not be allowed",
            },
            "expected_fragment": "unexpected field",
        },
        {
            "id": "whitespace_only_text",
            "artifact_class": "task",
            "payload": {
                **VALID_REQUIREMENT_FIXTURES["task"],
                "object": "   ",
            },
            "expected_fragment": "field `object` must be a non-empty string",
        },
        {
            "id": "wrong_text_list_type",
            "artifact_class": "task",
            "payload": {
                **VALID_REQUIREMENT_FIXTURES["task"],
                "constraints": {"bad": True},
            },
            "expected_fragment": "field `constraints` must be a non-empty string or a non-empty list",
        },
        {
            "id": "non_string_list_item",
            "artifact_class": "result",
            "payload": {
                **VALID_REQUIREMENT_FIXTURES["result"],
                "evidence_paths": ["docs/ORP_REASONING_KERNEL_V0_1.md", 42],
            },
            "expected_fragment": "field `evidence_paths` must be a non-empty list of non-empty strings",
        },
        {
            "id": "unsupported_artifact_class",
            "artifact_class": "task",
            "payload": {
                **VALID_REQUIREMENT_FIXTURES["task"],
                "artifact_class": "memo",
            },
            "expected_fragment": "unsupported artifact_class",
        },
        {
            "id": "wrong_schema_version",
            "artifact_class": "task",
            "payload": {
                **VALID_REQUIREMENT_FIXTURES["task"],
                "schema_version": "9.9.9",
            },
            "expected_fragment": "field `schema_version` must equal `1.0.0`",
        },
        {
            "id": "empty_list",
            "artifact_class": "task",
            "payload": {
                **VALID_REQUIREMENT_FIXTURES["task"],
                "boundary": [],
            },
            "expected_fragment": "missing required fields: boundary",
        },
    ]
    rows: list[dict[str, Any]] = []
    validate_times: list[float] = []

    with tempfile.TemporaryDirectory(prefix="orp-kernel-bench-mutations.") as td:
        root = Path(td)
        for case in cases:
            target = root / "analysis" / f"{case['id']}.kernel.json"
            _write_json(target, case["payload"])
            validate_ms, validate_proc = _timed_orp(
                root,
                "kernel",
                "validate",
                str(target.relative_to(root)),
                "--artifact-class",
                case["artifact_class"],
                "--json",
                check=False,
            )
            validate_payload = json.loads(validate_proc.stdout)
            issues = validate_payload["artifact_result"]["issues"]
            validate_times.append(validate_ms)
            rows.append(
                {
                    "id": case["id"],
                    "exit_code": validate_proc.returncode,
                    "issues": issues,
                    "validate_ms": round(validate_ms, 3),
                    "matched_expected_issue": any(case["expected_fragment"] in issue for issue in issues),
                }
            )

    observed = {"validate": _stats(validate_times)}
    targets = {
        "cases_total": len(cases),
        "validate_mean_lt_ms": 200.0,
    }
    return {
        "cases_total": len(rows),
        "rows": rows,
        "observed": observed,
        "targets": targets,
        "meets_targets": {
            "all_cases_detected": all(row["exit_code"] == 1 and row["matched_expected_issue"] for row in rows),
            "validate": observed["validate"]["mean_ms"] < targets["validate_mean_lt_ms"],
        },
    }


def _gather_metadata() -> dict[str, Any]:
    package_version = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    commit = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    node_version = _run(["node", "--version"]).stdout.strip()
    return {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo_commit": commit,
        "repo_branch": branch,
        "package_version": package_version,
        "python_version": sys.version.split()[0],
        "node_version": node_version,
        "platform": platform.platform(),
    }


def build_report(iterations: int) -> dict[str, Any]:
    init_benchmark = _benchmark_init_starter(iterations)
    roundtrip_benchmark = _benchmark_artifact_roundtrip()
    gate_mode_benchmark = _benchmark_gate_modes()
    schema_alignment = _benchmark_schema_alignment()
    corpus_benchmark = _benchmark_cross_domain_corpus()
    requirement_benchmark = _benchmark_requirement_enforcement()
    representation_invariance = _benchmark_representation_invariance()
    mutation_stress = _benchmark_mutation_stress()

    claims = [
        {
            "id": "schema_validator_alignment",
            "claim": "The CLI kernel requirements and allowed fields stay aligned with the published kernel schema.",
            "status": "pass" if all(schema_alignment["meets_expectations"].values()) else "fail",
            "evidence": [
                "benchmarks.schema_alignment",
                "spec/v1/kernel.schema.json",
                "cli/orp.py",
            ],
        },
        {
            "id": "starter_kernel_bootstrap",
            "claim": "orp init seeds a valid starter kernel artifact and a passing default structure_kernel gate.",
            "status": "pass",
            "evidence": [
                "benchmarks.init_starter_kernel",
                "cli/orp.py",
                "tests/test_orp_init.py",
            ],
        },
        {
            "id": "typed_artifact_roundtrip",
            "claim": "All seven v0.1 artifact classes can be scaffolded and validated through the CLI.",
            "status": "pass" if roundtrip_benchmark["artifact_classes_total"] == 7 else "fail",
            "evidence": [
                "benchmarks.artifact_roundtrip",
                "spec/v1/kernel.schema.json",
                "tests/test_orp_kernel.py",
            ],
        },
        {
            "id": "promotion_enforcement_modes",
            "claim": "Hard mode blocks invalid promotable artifacts, while soft mode records advisory issues without blocking.",
            "status": "pass"
            if gate_mode_benchmark["meets_expectations"]["hard_blocks_invalid_artifact"]
            and gate_mode_benchmark["meets_expectations"]["soft_allows_invalid_artifact_with_advisory"]
            else "fail",
            "evidence": [
                "benchmarks.gate_modes",
                "tests/test_orp_kernel.py",
            ],
        },
        {
            "id": "legacy_structure_kernel_compatibility",
            "claim": "Existing structure_kernel gates without explicit kernel config remain compatible.",
            "status": "pass"
            if gate_mode_benchmark["meets_expectations"]["legacy_structure_kernel_remains_compatible"]
            else "fail",
            "evidence": [
                "benchmarks.gate_modes",
                "cli/orp.py",
            ],
        },
        {
            "id": "local_cli_kernel_ergonomics",
            "claim": "One-shot kernel CLI operations remain within human-scale local ergonomics targets on the reference machine.",
            "status": "pass"
            if all(init_benchmark["meets_targets"].values())
            and all(roundtrip_benchmark["meets_targets"].values())
            else "fail",
            "evidence": [
                "benchmarks.init_starter_kernel",
                "benchmarks.artifact_roundtrip",
            ],
        },
        {
            "id": "cross_domain_corpus_fit",
            "claim": "The current v0.1 kernel class set fits a small cross-domain reference corpus cleanly.",
            "status": "pass"
            if all(corpus_benchmark["meets_targets"].values())
            and corpus_benchmark["artifact_classes_total"] >= 7
            else "fail",
            "evidence": [
                "benchmarks.cross_domain_corpus",
                "examples/kernel/corpus",
            ],
        },
        {
            "id": "class_specific_requirement_enforcement",
            "claim": "Each kernel artifact class rejects a candidate artifact when a required field is removed.",
            "status": "pass"
            if all(requirement_benchmark["meets_targets"].values())
            else "fail",
            "evidence": [
                "benchmarks.requirement_enforcement",
                "spec/v1/kernel.schema.json",
            ],
        },
        {
            "id": "representation_invariance",
            "claim": "Equivalent YAML and JSON kernel artifacts validate to the same semantic result.",
            "status": "pass"
            if all(representation_invariance["meets_expectations"].values())
            else "fail",
            "evidence": [
                "benchmarks.representation_invariance",
            ],
        },
        {
            "id": "adversarial_mutation_detection",
            "claim": "The validator rejects adversarial near-miss artifacts such as unknown fields, wrong types, whitespace-only text, and bad schema metadata.",
            "status": "pass"
            if all(mutation_stress["meets_targets"].values())
            else "fail",
            "evidence": [
                "benchmarks.mutation_stress",
                "spec/v1/kernel.schema.json",
            ],
        },
    ]

    return {
        "schema_version": "1.0.0",
        "kind": "orp_reasoning_kernel_validation_report",
        "metadata": _gather_metadata(),
        "benchmarks": {
            "init_starter_kernel": init_benchmark,
            "artifact_roundtrip": roundtrip_benchmark,
            "gate_modes": gate_mode_benchmark,
            "schema_alignment": schema_alignment,
            "cross_domain_corpus": corpus_benchmark,
            "requirement_enforcement": requirement_benchmark,
            "representation_invariance": representation_invariance,
            "mutation_stress": mutation_stress,
        },
        "claims": claims,
        "summary": {
            "all_claims_pass": all(row["status"] == "pass" for row in claims),
            "artifact_classes_total": roundtrip_benchmark["artifact_classes_total"],
            "cross_domain_corpus_domains_total": corpus_benchmark["domains_total"],
            "all_performance_targets_met": all(init_benchmark["meets_targets"].values())
            and all(roundtrip_benchmark["meets_targets"].values())
            and corpus_benchmark["meets_targets"]["validate"]
            and requirement_benchmark["meets_targets"]["validate"]
            and mutation_stress["meets_targets"]["validate"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark and validate ORP Reasoning Kernel v0.1")
    parser.add_argument("--out", default="", help="Optional JSON output path")
    parser.add_argument("--iterations", type=int, default=5, help="Iterations for bootstrap benchmark")
    parser.add_argument("--quick", action="store_true", help="Use a single bootstrap iteration for fast checks")
    args = parser.parse_args()

    iterations = 1 if args.quick else max(1, args.iterations)
    report = build_report(iterations)
    payload = json.dumps(report, indent=2) + "\n"
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = REPO_ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["summary"]["all_claims_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
