#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
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
AGENT_PILOT = REPO_ROOT / "scripts" / "orp-kernel-agent-pilot.py"
EXPECTED_TASKS = REPO_ROOT / "examples" / "kernel" / "comparison" / "next-task-continuation.json"
CONDITIONS = ["freeform", "generic_checklist", "kernel"]
TASK_FIELDS = ["object", "goal", "boundary", "constraints", "success_criteria"]
STOPWORDS = {
    "a", "an", "and", "the", "to", "of", "for", "in", "on", "with", "without",
    "is", "are", "be", "by", "or", "as", "that", "this", "it", "into", "from",
    "than", "at", "all", "one", "through",
}


def _load_agent_pilot():
    spec = importlib.util.spec_from_file_location("orp_kernel_agent_pilot_runtime", AGENT_PILOT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load agent pilot from {AGENT_PILOT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AGENT_PILOT_MODULE = _load_agent_pilot()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_expected_tasks() -> dict[str, dict[str, str]]:
    payload = _read_json(EXPECTED_TASKS)
    cases = payload.get("cases")
    if not isinstance(cases, dict):
        raise RuntimeError(f"expected task continuation cases missing: {EXPECTED_TASKS}")
    return {str(key): {str(f): str(v) for f, v in value.items()} for key, value in cases.items() if isinstance(value, dict)}


EXPECTED_TASK_MAP = _load_expected_tasks()


def _response_schema() -> dict[str, Any]:
    properties = {
        "artifact_class": {"type": "string", "const": "task"},
        "confidence": {"type": "number"},
        "missing_required_fields": {"type": "array", "items": {"type": "string"}},
    }
    required = ["artifact_class", "confidence", "missing_required_fields"]
    for field in TASK_FIELDS:
        properties[field] = {"type": ["string", "null"]}
        required.append(field)
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def _build_prompt(case: dict[str, Any], condition: str) -> str:
    artifact = AGENT_PILOT_MODULE._render_artifact(case, condition)
    target_list = ", ".join(TASK_FIELDS)
    return (
        "You are simulating a fresh downstream Codex session that must convert the source artifact into the next canonical task artifact.\n"
        "Using only the artifact below, produce a JSON object for a kernel task artifact.\n"
        f"The task artifact must include these required fields: {target_list}.\n"
        "Use a string only when the source artifact gives enough support to carry the field forward safely into a task artifact.\n"
        "If the source artifact does not support a required field strongly enough, set that field to null and include it in `missing_required_fields`.\n"
        "Do not invent unsupported constraints, boundaries, or success criteria.\n\n"
        f"Artifact:\n{artifact}\n"
    )


def _run_codex(case: dict[str, Any], condition: str, *, model: str) -> dict[str, Any]:
    prompt = _build_prompt(case, condition)
    with tempfile.TemporaryDirectory(prefix="orp-kernel-canonical-continuation.") as td:
        root = Path(td)
        schema_path = root / "schema.json"
        out_path = root / "out.json"
        schema_path.write_text(json.dumps(_response_schema(), indent=2) + "\n", encoding="utf-8")
        args = [
            "codex",
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "-C",
            str(root),
            "--output-schema",
            str(schema_path),
            "-o",
            str(out_path),
        ]
        if model:
            args.extend(["--model", model])
        args.append("-")
        started = time.perf_counter()
        proc = AGENT_PILOT_MODULE._run_codex_exec(args, cwd=REPO_ROOT, stdin=prompt)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        if proc.returncode != 0:
            raise RuntimeError(
                f"codex exec failed for case={case['id']} condition={condition}\n"
                f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
            )
        payload = _read_json(out_path)
        return {
            "raw_response": payload,
            "elapsed_ms": elapsed_ms,
            "session_id": AGENT_PILOT_MODULE._extract_session_id(proc.stdout),
            "tokens_used": AGENT_PILOT_MODULE._extract_tokens_used(proc.stdout),
        }


def _tokenize(value: str) -> set[str]:
    parts = re.findall(r"[a-z0-9]+", value.lower())
    return {part for part in parts if part not in STOPWORDS and len(part) > 2}


def _similarity(answer: str | None, expected: str) -> float:
    if not answer:
        return 0.0
    answer_tokens = _tokenize(answer)
    expected_tokens = _tokenize(expected)
    if not answer_tokens or not expected_tokens:
        return 0.0
    overlap = answer_tokens & expected_tokens
    return round(len(overlap) / len(expected_tokens), 3)


def _score_case(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    expected = EXPECTED_TASK_MAP[case["id"]]
    answers: dict[str, str | None] = {}
    field_similarity: dict[str, float] = {}
    aligned = 0
    misaligned = 0
    for field in TASK_FIELDS:
        value = response.get(field)
        normalized = value.strip() if isinstance(value, str) and value.strip() else None
        answers[field] = normalized
        similarity = _similarity(normalized, expected[field])
        field_similarity[field] = similarity
        if similarity >= 0.45:
            aligned += 1
        elif normalized is not None:
            misaligned += 1
    alignment_score = round(aligned / len(TASK_FIELDS), 3)
    invention_rate = round(misaligned / len([v for v in answers.values() if v is not None]), 3) if any(answers.values()) else 0.0
    missing_declared = set(response.get("missing_required_fields", []))
    missing_expected = {field for field, value in answers.items() if value is None}
    missing_list_match = round(len(missing_declared & missing_expected) / len(missing_expected), 3) if missing_expected else 1.0
    total_score = round((alignment_score + (1.0 - invention_rate) + missing_list_match) / 3.0, 3)
    return {
        "answers": answers,
        "expected": expected,
        "field_similarity": field_similarity,
        "aligned_fields": aligned,
        "alignment_score": alignment_score,
        "misaligned_fields": misaligned,
        "invention_rate": invention_rate,
        "missing_declared": sorted(missing_declared),
        "missing_expected": sorted(missing_expected),
        "missing_list_match": missing_list_match,
        "total_score": total_score,
        "confidence": response["confidence"],
    }


def _evaluate_case(case: dict[str, Any], *, model: str) -> dict[str, Any]:
    conditions: dict[str, Any] = {}
    for condition in CONDITIONS:
        result = _run_codex(case, condition, model=model)
        score = _score_case(case, result["raw_response"])
        conditions[condition] = {
            "response": result["raw_response"],
            "score": score,
            "elapsed_ms": result["elapsed_ms"],
            "session_id": result["session_id"],
            "tokens_used": result["tokens_used"],
        }
    return {
        "id": case["id"],
        "domain": case["domain"],
        "artifact_class": case["artifact_class"],
        "prompt": case["prompt"],
        "conditions": conditions,
    }


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _aggregate(cases: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    rows = []
    total_scores: list[float] = []
    alignment_scores: list[float] = []
    invention_rates: list[float] = []
    missing_match: list[float] = []
    confidence: list[float] = []
    elapsed: list[float] = []
    for case in cases:
        row = case["conditions"][condition]
        score = row["score"]
        rows.append(
            {
                "id": case["id"],
                "domain": case["domain"],
                "artifact_class": case["artifact_class"],
                "total_score": score["total_score"],
                "alignment_score": score["alignment_score"],
                "invention_rate": score["invention_rate"],
                "missing_list_match": score["missing_list_match"],
                "answers": score["answers"],
                "field_similarity": score["field_similarity"],
            }
        )
        total_scores.append(score["total_score"])
        alignment_scores.append(score["alignment_score"])
        invention_rates.append(score["invention_rate"])
        missing_match.append(score["missing_list_match"])
        confidence.append(score["confidence"])
        elapsed.append(row["elapsed_ms"])
    return {
        "condition": condition,
        "cases_total": len(rows),
        "rows": rows,
        "mean_total_score": _mean(total_scores),
        "mean_alignment_score": _mean(alignment_scores),
        "mean_invention_rate": _mean(invention_rates),
        "mean_missing_list_match": _mean(missing_match),
        "mean_confidence": _mean(confidence),
        "mean_elapsed_ms": _mean(elapsed),
    }


def _pairwise(cases: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    wins = 0
    ties = 0
    losses = 0
    deltas: list[float] = []
    for case in cases:
        left_score = case["conditions"][left]["score"]["total_score"]
        right_score = case["conditions"][right]["score"]["total_score"]
        delta = round(left_score - right_score, 3)
        deltas.append(delta)
        if delta > 0:
            wins += 1
        elif delta < 0:
            losses += 1
        else:
            ties += 1
    return {
        "left": left,
        "right": right,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "mean_total_score_delta": _mean(deltas),
    }


def _gather_metadata(model: str) -> dict[str, Any]:
    package_version = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True).stdout.strip()
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True).stdout.strip()
    codex_version = subprocess.run(["codex", "--version"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True).stdout.strip()
    return {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo_commit": commit,
        "repo_branch": branch,
        "package_version": package_version,
        "python_version": sys.version.split()[0],
        "codex_version": codex_version,
        "platform": platform.platform(),
        "model": model or "default",
    }


def build_report(*, model: str, case_ids: set[str] | None = None) -> dict[str, Any]:
    cases = AGENT_PILOT_MODULE._load_cases()
    if case_ids:
        cases = [case for case in cases if case["id"] in case_ids]
        if not cases:
            raise RuntimeError("no comparison cases matched the requested ids")
    evaluated = [_evaluate_case(case, model=model) for case in cases]
    conditions = {condition: _aggregate(evaluated, condition) for condition in CONDITIONS}
    pairwise = {
        "kernel_vs_generic_checklist": _pairwise(evaluated, "kernel", "generic_checklist"),
        "kernel_vs_freeform": _pairwise(evaluated, "kernel", "freeform"),
    }
    claims = [
        {
            "id": "kernel_outscores_generic_checklist_on_canonical_task_continuation",
            "claim": "On the matched live canonical-task continuation benchmark, kernel artifacts produce task artifacts that meet or exceed generic checklist quality without a higher invention rate.",
            "status": "pass"
            if conditions["kernel"]["mean_total_score"] >= conditions["generic_checklist"]["mean_total_score"]
            and pairwise["kernel_vs_generic_checklist"]["losses"] == 0
            and conditions["kernel"]["mean_invention_rate"] <= conditions["generic_checklist"]["mean_invention_rate"]
            else "fail",
        },
        {
            "id": "kernel_outscores_freeform_on_canonical_task_continuation",
            "claim": "On the matched live canonical-task continuation benchmark, kernel artifacts produce stronger next-task artifacts than free-form artifacts.",
            "status": "pass"
            if conditions["kernel"]["mean_total_score"] > conditions["freeform"]["mean_total_score"]
            and pairwise["kernel_vs_freeform"]["losses"] == 0
            else "fail",
        },
        {
            "id": "kernel_minimizes_invention_on_canonical_task_continuation",
            "claim": "On the matched live canonical-task continuation benchmark, kernel artifacts minimize unsupported task-field invention.",
            "status": "pass"
            if conditions["kernel"]["mean_invention_rate"] <= conditions["generic_checklist"]["mean_invention_rate"]
            and conditions["kernel"]["mean_invention_rate"] <= conditions["freeform"]["mean_invention_rate"]
            else "fail",
        },
    ]
    return {
        "schema_version": "1.0.0",
        "kind": "orp_reasoning_kernel_canonical_continuation_report",
        "metadata": _gather_metadata(model),
        "corpus": {
            "cases_total": len(evaluated),
            "domains": sorted({case["domain"] for case in evaluated}),
            "artifact_classes": sorted({case["artifact_class"] for case in evaluated}),
        },
        "conditions": conditions,
        "pairwise": pairwise,
        "claims": claims,
        "summary": {
            "all_claims_pass": all(claim["status"] == "pass" for claim in claims),
            "kernel_mean_total_score": conditions["kernel"]["mean_total_score"],
            "generic_checklist_mean_total_score": conditions["generic_checklist"]["mean_total_score"],
            "freeform_mean_total_score": conditions["freeform"]["mean_total_score"],
            "kernel_mean_invention_rate": conditions["kernel"]["mean_invention_rate"],
            "generic_checklist_mean_invention_rate": conditions["generic_checklist"]["mean_invention_rate"],
            "freeform_mean_invention_rate": conditions["freeform"]["mean_invention_rate"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a live Codex canonical-task continuation benchmark across free-form, generic checklist, and kernel artifacts."
    )
    parser.add_argument("--out", default="", help="Optional JSON output path")
    parser.add_argument("--model", default="", help="Optional Codex model override")
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case id to evaluate (repeatable). Default: all cases.",
    )
    args = parser.parse_args()
    report = build_report(model=args.model, case_ids=set(args.case_id) or None)
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
