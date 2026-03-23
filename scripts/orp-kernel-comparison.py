#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = ["node", "bin/orp.js"]
COMPARISON_CORPUS = REPO_ROOT / "examples" / "kernel" / "comparison" / "comparison-corpus.json"
KERNEL_SCHEMA = REPO_ROOT / "spec" / "v1" / "kernel.schema.json"
CONDITIONS = ["freeform", "generic_checklist", "kernel"]

FREEFORM_LABEL_ALIASES: dict[str, set[str]] = {
    "artifact_type": {"artifact type", "type"},
    "object": {"object"},
    "goal": {"goal"},
    "boundary": {"boundary", "scope"},
    "constraints": {"constraints", "constraint"},
    "success_criteria": {"success criteria", "success", "done when"},
    "question": {"question"},
    "chosen_path": {"decision", "chosen path", "recommendation"},
    "rejected_alternatives": {"rejected alternatives", "alternatives"},
    "rationale": {"why", "rationale"},
    "consequences": {"consequences", "tradeoffs", "trade-offs"},
    "claim": {"claim"},
    "assumptions": {"assumptions"},
    "test_path": {"test", "test path"},
    "falsifiers": {"falsifiers", "would fail if"},
    "objective": {"objective"},
    "method": {"method"},
    "inputs": {"inputs"},
    "outputs": {"outputs"},
    "evidence_expectations": {"evidence expectations"},
    "interpretation_limits": {"limits", "interpretation limits"},
    "completed_unit": {"completed", "completed unit"},
    "current_state": {"current state"},
    "risks": {"risks", "risk"},
    "next_handoff_target": {"next", "next handoff target", "handoff"},
    "artifact_refs": {"artifact refs", "artifacts", "references"},
    "scope": {"scope"},
    "rule": {"rule"},
    "invariants": {"invariants"},
    "enforcement_surface": {"enforcement", "enforcement surface"},
    "evidence_paths": {"evidence", "evidence paths"},
    "status": {"status"},
    "next_follow_up": {"next follow up", "next follow-up", "next"},
}

CHECKLIST_FIELD_MAP: dict[str, dict[str, str]] = {
    "task": {
        "object": "summary",
        "goal": "summary",
        "boundary": "scope",
        "constraints": "constraints",
        "success_criteria": "checks",
    },
    "decision": {
        "question": "summary",
        "chosen_path": "approach",
        "rejected_alternatives": "notes",
        "rationale": "notes",
        "consequences": "risks",
    },
    "hypothesis": {
        "claim": "summary",
        "boundary": "scope",
        "assumptions": "notes",
        "test_path": "checks",
        "falsifiers": "risks",
    },
    "experiment": {
        "objective": "summary",
        "method": "approach",
        "inputs": "scope",
        "outputs": "checks",
        "evidence_expectations": "evidence",
        "interpretation_limits": "risks",
    },
    "checkpoint": {
        "completed_unit": "summary",
        "current_state": "notes",
        "risks": "risks",
        "next_handoff_target": "handoff",
        "artifact_refs": "evidence",
    },
    "policy": {
        "scope": "scope",
        "rule": "summary",
        "rationale": "notes",
        "invariants": "constraints",
        "enforcement_surface": "checks",
    },
    "result": {
        "claim": "summary",
        "evidence_paths": "evidence",
        "status": "checks",
        "interpretation_limits": "risks",
        "next_follow_up": "handoff",
    },
}

OBJECTIVE_FIELDS: dict[str, list[str]] = {
    "task": ["object", "goal"],
    "decision": ["question", "chosen_path"],
    "hypothesis": ["claim"],
    "experiment": ["objective", "method"],
    "checkpoint": ["completed_unit", "current_state"],
    "policy": ["rule", "scope"],
    "result": ["claim", "status"],
}

LIMIT_FIELDS: dict[str, list[str]] = {
    "task": ["boundary", "constraints"],
    "decision": ["rejected_alternatives", "consequences"],
    "hypothesis": ["boundary", "assumptions"],
    "experiment": ["inputs", "interpretation_limits"],
    "checkpoint": ["risks"],
    "policy": ["invariants"],
    "result": ["interpretation_limits"],
}

EVALUATION_FIELDS: dict[str, list[str]] = {
    "task": ["success_criteria"],
    "decision": ["rationale"],
    "hypothesis": ["test_path", "falsifiers"],
    "experiment": ["outputs", "evidence_expectations"],
    "checkpoint": ["artifact_refs"],
    "policy": ["enforcement_surface", "rationale"],
    "result": ["evidence_paths"],
}

HANDOFF_FIELDS: dict[str, list[str]] = {
    "task": ["object", "goal", "success_criteria"],
    "decision": ["question", "chosen_path", "consequences"],
    "hypothesis": ["claim", "boundary", "test_path"],
    "experiment": ["objective", "method", "outputs"],
    "checkpoint": ["current_state", "next_handoff_target"],
    "policy": ["rule", "scope", "enforcement_surface"],
    "result": ["claim", "status", "next_follow_up"],
}

CHECKLIST_SOURCE_WEIGHTS: dict[str, float] = {
    "summary": 0.55,
    "scope": 0.8,
    "constraints": 0.8,
    "approach": 0.7,
    "checks": 0.7,
    "risks": 0.65,
    "evidence": 0.75,
    "handoff": 0.8,
    "notes": 0.5,
}

FREEFORM_FIELD_WEIGHT = 0.45
FREEFORM_TYPE_WEIGHT = 0.35
CHECKLIST_TYPE_WEIGHT = 0.85


def _run(args: list[str], *, cwd: Path = REPO_ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
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


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_cases() -> list[dict[str, Any]]:
    payload = _read_json(COMPARISON_CORPUS)
    cases = payload.get("cases", [])
    if not isinstance(cases, list) or not cases:
        raise RuntimeError(f"comparison corpus has no cases: {COMPARISON_CORPUS}")
    return cases


def _load_kernel_requirements() -> dict[str, list[str]]:
    payload = _read_json(KERNEL_SCHEMA)
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


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _value_present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        if not value:
            return False
        return all(isinstance(item, str) and item.strip() for item in value)
    return False


def _coverage(fields: list[str], present_map: dict[str, float]) -> float:
    if not fields:
        return 1.0
    hits = sum(present_map.get(field, 0.0) for field in fields)
    return hits / len(fields)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _score_dimensions(artifact_class: str, present_map: dict[str, float], *, type_clarity: float) -> dict[str, float]:
    required = KERNEL_REQUIREMENTS[artifact_class]
    dimensions = {
        "artifact_type_clarity": round(type_clarity, 3),
        "objective_clarity": round(_coverage(OBJECTIVE_FIELDS[artifact_class], present_map), 3),
        "limits_clarity": round(_coverage(LIMIT_FIELDS[artifact_class], present_map), 3),
        "evaluation_clarity": round(_coverage(EVALUATION_FIELDS[artifact_class], present_map), 3),
        "handoff_readiness": round(_coverage(HANDOFF_FIELDS[artifact_class], present_map), 3),
        "class_specific_completeness": round(_coverage(required, present_map), 3),
    }
    dimensions["total_score"] = round(
        sum(dimensions[key] for key in [
            "artifact_type_clarity",
            "objective_clarity",
            "limits_clarity",
            "evaluation_clarity",
            "handoff_readiness",
            "class_specific_completeness",
        ])
        / 6.0,
        3,
    )
    dimensions["ambiguity_remaining"] = round(1.0 - dimensions["class_specific_completeness"], 3)
    return dimensions


def _parse_freeform_fields(body: str) -> dict[str, bool]:
    found: dict[str, bool] = {}
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^[#>*\-\s]*([A-Za-z][A-Za-z \-_/]+):\s*(.+?)\s*$", raw_line)
        if not match:
            continue
        label = _normalize_label(match.group(1))
        value = match.group(2).strip()
        if not value:
            continue
        for field, aliases in FREEFORM_LABEL_ALIASES.items():
            if label in aliases:
                found[field] = True
    return found


def _score_freeform(case: dict[str, Any]) -> dict[str, Any]:
    artifact_class = case["artifact_class"]
    body = case["freeform_markdown"]
    parsed = _parse_freeform_fields(body)
    present = {
        field: (FREEFORM_FIELD_WEIGHT if parsed.get(field, False) else 0.0)
        for field in KERNEL_REQUIREMENTS[artifact_class]
    }
    type_clarity = FREEFORM_TYPE_WEIGHT if parsed.get("artifact_type", False) else 0.0
    dimensions = _score_dimensions(artifact_class, present, type_clarity=type_clarity)
    return {
        "condition": "freeform",
        "artifact_class": artifact_class,
        "present_fields": sorted(field for field, score in present.items() if score > 0),
        "missing_fields": [field for field in KERNEL_REQUIREMENTS[artifact_class] if present.get(field, 0.0) == 0.0],
        "field_scores": {field: round(score, 3) for field, score in present.items()},
        "dimensions": dimensions,
    }


def _score_checklist(case: dict[str, Any]) -> dict[str, Any]:
    artifact_class = case["artifact_class"]
    checklist = case["generic_checklist"]
    present = {field: 0.0 for field in KERNEL_REQUIREMENTS[artifact_class]}
    mapping = CHECKLIST_FIELD_MAP[artifact_class]
    for field in KERNEL_REQUIREMENTS[artifact_class]:
        source_field = mapping.get(field, "")
        if source_field and _value_present(checklist.get(source_field)):
            present[field] = CHECKLIST_SOURCE_WEIGHTS.get(source_field, 0.5)
    type_clarity = CHECKLIST_TYPE_WEIGHT if checklist.get("artifact_type") == artifact_class else 0.0
    dimensions = _score_dimensions(artifact_class, present, type_clarity=type_clarity)
    return {
        "condition": "generic_checklist",
        "artifact_class": artifact_class,
        "present_fields": sorted(field for field, score in present.items() if score > 0),
        "missing_fields": [field for field in KERNEL_REQUIREMENTS[artifact_class] if present.get(field, 0.0) == 0.0],
        "field_scores": {field: round(score, 3) for field, score in present.items()},
        "dimensions": dimensions,
    }


def _score_kernel(case: dict[str, Any]) -> dict[str, Any]:
    artifact_class = case["artifact_class"]
    kernel_artifact = case["kernel_artifact"]
    with tempfile.TemporaryDirectory(prefix="orp-kernel-comparison.") as td:
        root = Path(td)
        target = root / "analysis" / f"{case['id']}.kernel.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(kernel_artifact, indent=2) + "\n", encoding="utf-8")
        validate_ms, proc = _timed_orp(
            root,
            "kernel",
            "validate",
            str(target.relative_to(root)),
            "--artifact-class",
            artifact_class,
            "--json",
            check=False,
        )
        payload = json.loads(proc.stdout)
        artifact_result = payload["artifact_result"]
        present = {
            field: (1.0 if _value_present(kernel_artifact.get(field)) else 0.0)
            for field in KERNEL_REQUIREMENTS[artifact_class]
        }
        dimensions = _score_dimensions(
            artifact_class,
            present,
            type_clarity=1.0 if artifact_result["artifact_class"] == artifact_class else 0.0,
        )
        return {
            "condition": "kernel",
            "artifact_class": artifact_class,
            "present_fields": sorted(field for field, score in present.items() if score > 0),
            "missing_fields": artifact_result.get("missing_fields", []),
            "field_scores": {field: round(score, 3) for field, score in present.items()},
            "dimensions": dimensions,
            "validate_ms": round(validate_ms, 3),
            "valid": bool(payload.get("ok")),
            "issues": artifact_result.get("issues", []),
            "exit_code": proc.returncode,
        }


def _score_case(case: dict[str, Any]) -> dict[str, Any]:
    freeform = _score_freeform(case)
    checklist = _score_checklist(case)
    kernel = _score_kernel(case)
    return {
        "id": case["id"],
        "domain": case["domain"],
        "artifact_class": case["artifact_class"],
        "prompt": case["prompt"],
        "conditions": {
            "freeform": freeform,
            "generic_checklist": checklist,
            "kernel": kernel,
        },
    }


def _aggregate_condition(cases: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    totals: list[float] = []
    completeness: list[float] = []
    ambiguity: list[float] = []
    dims: dict[str, list[float]] = {
        "artifact_type_clarity": [],
        "objective_clarity": [],
        "limits_clarity": [],
        "evaluation_clarity": [],
        "handoff_readiness": [],
        "class_specific_completeness": [],
    }
    for case in cases:
        row = case["conditions"][condition]
        rows.append(
            {
                "id": case["id"],
                "domain": case["domain"],
                "artifact_class": case["artifact_class"],
                "total_score": row["dimensions"]["total_score"],
                "class_specific_completeness": row["dimensions"]["class_specific_completeness"],
                "ambiguity_remaining": row["dimensions"]["ambiguity_remaining"],
                "present_fields": row["present_fields"],
                "missing_fields": row["missing_fields"],
            }
        )
        totals.append(row["dimensions"]["total_score"])
        completeness.append(row["dimensions"]["class_specific_completeness"])
        ambiguity.append(row["dimensions"]["ambiguity_remaining"])
        for key in dims:
            dims[key].append(row["dimensions"][key])
    return {
        "condition": condition,
        "cases_total": len(rows),
        "rows": rows,
        "mean_total_score": _mean(totals),
        "mean_class_specific_completeness": _mean(completeness),
        "mean_ambiguity_remaining": _mean(ambiguity),
        "mean_dimension_scores": {key: _mean(values) for key, values in dims.items()},
    }


def _pairwise(cases: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    wins = 0
    ties = 0
    losses = 0
    deltas: list[float] = []
    by_case: list[dict[str, Any]] = []
    for case in cases:
        left_score = case["conditions"][left]["dimensions"]["total_score"]
        right_score = case["conditions"][right]["dimensions"]["total_score"]
        delta = round(left_score - right_score, 3)
        deltas.append(delta)
        if delta > 0:
            wins += 1
            outcome = "win"
        elif delta < 0:
            losses += 1
            outcome = "loss"
        else:
            ties += 1
            outcome = "tie"
        by_case.append(
            {
                "id": case["id"],
                "domain": case["domain"],
                "artifact_class": case["artifact_class"],
                "left_score": left_score,
                "right_score": right_score,
                "delta": delta,
                "outcome": outcome,
            }
        )
    return {
        "left": left,
        "right": right,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "mean_total_score_delta": _mean(deltas),
        "by_case": by_case,
    }


def _gather_metadata() -> dict[str, Any]:
    package_version = _read_json(REPO_ROOT / "package.json")["version"]
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


def build_report() -> dict[str, Any]:
    cases = [_score_case(case) for case in _load_cases()]
    domains = sorted({case["domain"] for case in cases})
    classes = sorted({case["artifact_class"] for case in cases})

    conditions = {condition: _aggregate_condition(cases, condition) for condition in CONDITIONS}
    pairwise = {
        "kernel_vs_generic_checklist": _pairwise(cases, "kernel", "generic_checklist"),
        "kernel_vs_freeform": _pairwise(cases, "kernel", "freeform"),
        "generic_checklist_vs_freeform": _pairwise(cases, "generic_checklist", "freeform"),
    }

    claims = [
        {
            "id": "matched_internal_corpus_exists",
            "claim": "ORP has a matched internal comparison corpus spanning multiple domains and all seven kernel artifact classes.",
            "status": "pass" if len(cases) >= 7 and len(domains) >= 5 and len(classes) >= 7 else "fail",
        },
        {
            "id": "kernel_outscores_generic_checklist_on_matched_corpus",
            "claim": "On the matched internal comparison corpus, kernel artifacts achieve higher mean structural scores than generic checklist artifacts.",
            "status": "pass"
            if conditions["kernel"]["mean_total_score"] > conditions["generic_checklist"]["mean_total_score"]
            and pairwise["kernel_vs_generic_checklist"]["losses"] == 0
            else "fail",
        },
        {
            "id": "kernel_outscores_freeform_on_matched_corpus",
            "claim": "On the matched internal comparison corpus, kernel artifacts achieve higher mean structural scores than free-form artifacts.",
            "status": "pass"
            if conditions["kernel"]["mean_total_score"] > conditions["freeform"]["mean_total_score"]
            and pairwise["kernel_vs_freeform"]["losses"] == 0
            else "fail",
        },
        {
            "id": "generic_checklist_improves_on_freeform_for_structure",
            "claim": "On the matched internal comparison corpus, a generic checklist condition improves structural scores over free-form artifacts.",
            "status": "pass"
            if conditions["generic_checklist"]["mean_total_score"] > conditions["freeform"]["mean_total_score"]
            and pairwise["generic_checklist_vs_freeform"]["losses"] == 0
            else "fail",
        },
        {
            "id": "kernel_preserves_full_required_coverage",
            "claim": "On the matched internal comparison corpus, kernel artifacts preserve full class-specific required-field coverage.",
            "status": "pass"
            if conditions["kernel"]["mean_class_specific_completeness"] == 1.0
            else "fail",
        },
    ]

    return {
        "schema_version": "1.0.0",
        "kind": "orp_reasoning_kernel_comparison_report",
        "metadata": _gather_metadata(),
        "corpus": {
            "source": str(COMPARISON_CORPUS.relative_to(REPO_ROOT)),
            "cases_total": len(cases),
            "domains_total": len(domains),
            "domains": domains,
            "artifact_classes_total": len(classes),
            "artifact_classes": classes,
        },
        "conditions": conditions,
        "pairwise": pairwise,
        "claims": claims,
        "summary": {
            "all_claims_pass": all(claim["status"] == "pass" for claim in claims),
            "kernel_mean_total_score": conditions["kernel"]["mean_total_score"],
            "generic_checklist_mean_total_score": conditions["generic_checklist"]["mean_total_score"],
            "freeform_mean_total_score": conditions["freeform"]["mean_total_score"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a matched internal comparison between free-form, generic checklist, and ORP kernel artifacts."
    )
    parser.add_argument("--out", default="", help="Optional JSON output path")
    args = parser.parse_args()

    report = build_report()
    payload = json.dumps(report, indent=2) + "\n"
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = REPO_ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["summary"]["all_claims_pass"] else 1


KERNEL_REQUIREMENTS = _load_kernel_requirements()


if __name__ == "__main__":
    raise SystemExit(main())
