#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
ARTIFACT_CLASSES = [
    "task",
    "decision",
    "hypothesis",
    "experiment",
    "checkpoint",
    "policy",
    "result",
]


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
        "gate_mean_lt_ms": 300.0,
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

    claims = [
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
    ]

    return {
        "schema_version": "1.0.0",
        "kind": "orp_reasoning_kernel_validation_report",
        "metadata": _gather_metadata(),
        "benchmarks": {
            "init_starter_kernel": init_benchmark,
            "artifact_roundtrip": roundtrip_benchmark,
            "gate_modes": gate_mode_benchmark,
        },
        "claims": claims,
        "summary": {
            "all_claims_pass": all(row["status"] == "pass" for row in claims),
            "artifact_classes_total": roundtrip_benchmark["artifact_classes_total"],
            "all_performance_targets_met": all(init_benchmark["meets_targets"].values())
            and all(roundtrip_benchmark["meets_targets"].values()),
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
