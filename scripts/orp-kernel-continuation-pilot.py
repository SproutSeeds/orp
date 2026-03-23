#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PILOT = REPO_ROOT / "scripts" / "orp-kernel-agent-pilot.py"
CONDITIONS = ["freeform", "generic_checklist", "kernel"]

HANDOFF_FIELDS: dict[str, list[str]] = {
    "task": ["object", "constraints", "success_criteria"],
    "decision": ["question", "chosen_path", "consequences"],
    "hypothesis": ["claim", "boundary", "test_path"],
    "experiment": ["objective", "method", "outputs"],
    "checkpoint": ["current_state", "risks", "next_handoff_target"],
    "policy": ["scope", "rule", "enforcement_surface"],
    "result": ["claim", "status", "next_follow_up"],
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


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "artifact_type_guess": {"type": "string"},
            "recommended_next_action": {"type": "string"},
            "carry_forward": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field": {"type": "string"},
                        "value": {"type": ["string", "null"]},
                    },
                    "required": ["field", "value"],
                },
            },
            "explicitly_missing": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
        },
        "required": [
            "artifact_type_guess",
            "recommended_next_action",
            "carry_forward",
            "explicitly_missing",
            "confidence",
        ],
    }


def _build_prompt(case: dict[str, Any], condition: str) -> str:
    targets = HANDOFF_FIELDS[case["artifact_class"]]
    artifact = AGENT_PILOT_MODULE._render_artifact(case, condition)
    target_list = ", ".join(targets)
    return (
        "You are simulating a fresh downstream Codex session that must continue the work safely.\n"
        "Using only the artifact below, propose the next action and identify the key fields that must be carried forward.\n"
        "Return JSON matching the provided schema.\n"
        f"In `carry_forward`, include one entry for each of these handoff-critical fields: {target_list}.\n"
        "Use a string only when the artifact makes the field explicit enough to carry forward safely. Otherwise use null.\n"
        "Do not invent missing structure. If information is missing, put it in `explicitly_missing` rather than fabricating it.\n\n"
        f"Artifact:\n{artifact}\n"
    )


def _run_codex_continuation(case: dict[str, Any], condition: str, *, model: str) -> dict[str, Any]:
    prompt = _build_prompt(case, condition)
    with tempfile.TemporaryDirectory(prefix="orp-kernel-continuation.") as td:
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


def _score_continuation(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    targets = HANDOFF_FIELDS[case["artifact_class"]]
    expected_present = AGENT_PILOT_MODULE._expected_explicit_fields(case, response.get("_condition", "kernel"))
    entries = response.get("carry_forward", [])
    carry_forward: dict[str, str | None] = {}
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            field = entry.get("field")
            if isinstance(field, str):
                value = entry.get("value")
                carry_forward[field] = value.strip() if isinstance(value, str) and value.strip() else None

    answered = 0
    answers: dict[str, str | None] = {}
    for field in targets:
        value = carry_forward.get(field)
        answers[field] = value
        if value is not None:
            answered += 1
    invented_fields = [
        field
        for field, value in answers.items()
        if value is not None and field not in expected_present
    ]
    carry_forward_score = round(answered / len(targets), 3)
    invention_rate = round(len(invented_fields) / answered, 3) if answered else 0.0
    next_action_present = bool(response.get("recommended_next_action", "").strip())
    continuation_score = round(
        (carry_forward_score + (1.0 - invention_rate) + (1.0 if next_action_present else 0.0)) / 3.0,
        3,
    )
    return {
        "handoff_fields": targets,
        "expected_present_fields": sorted(field for field in targets if field in expected_present),
        "answers": answers,
        "answered_targets": answered,
        "handoff_fields_total": len(targets),
        "carry_forward_score": carry_forward_score,
        "invented_fields": invented_fields,
        "invented_fields_count": len(invented_fields),
        "invention_rate": invention_rate,
        "next_action_present": next_action_present,
        "continuation_score": continuation_score,
        "explicitly_missing_count": len(response.get("explicitly_missing", [])),
        "confidence": response["confidence"],
    }


def _evaluate_case(case: dict[str, Any], *, model: str) -> dict[str, Any]:
    conditions: dict[str, Any] = {}
    for condition in CONDITIONS:
        result = _run_codex_continuation(case, condition, model=model)
        score = _score_continuation(case, {**result["raw_response"], "_condition": condition})
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
    continuation_scores: list[float] = []
    carry_forward_scores: list[float] = []
    invention_rates: list[float] = []
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
                "continuation_score": score["continuation_score"],
                "carry_forward_score": score["carry_forward_score"],
                "invention_rate": score["invention_rate"],
                "next_action_present": score["next_action_present"],
                "answers": score["answers"],
                "explicitly_missing_count": score["explicitly_missing_count"],
                "recommended_next_action": row["response"]["recommended_next_action"],
            }
        )
        continuation_scores.append(score["continuation_score"])
        carry_forward_scores.append(score["carry_forward_score"])
        invention_rates.append(score["invention_rate"])
        confidence.append(score["confidence"])
        elapsed.append(row["elapsed_ms"])
    return {
        "condition": condition,
        "cases_total": len(rows),
        "rows": rows,
        "mean_continuation_score": _mean(continuation_scores),
        "mean_carry_forward_score": _mean(carry_forward_scores),
        "mean_invention_rate": _mean(invention_rates),
        "mean_confidence": _mean(confidence),
        "mean_elapsed_ms": _mean(elapsed),
    }


def _pairwise(cases: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    wins = 0
    ties = 0
    losses = 0
    deltas: list[float] = []
    for case in cases:
        left_score = case["conditions"][left]["score"]["continuation_score"]
        right_score = case["conditions"][right]["score"]["continuation_score"]
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
        "mean_continuation_score_delta": _mean(deltas),
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
            "id": "kernel_outscores_generic_checklist_on_continuation",
            "claim": "On the matched live continuation simulation, kernel artifacts support a downstream continuation score that meets or exceeds generic checklist artifacts without a higher invention rate.",
            "status": "pass"
            if conditions["kernel"]["mean_continuation_score"] >= conditions["generic_checklist"]["mean_continuation_score"]
            and pairwise["kernel_vs_generic_checklist"]["losses"] == 0
            and conditions["kernel"]["mean_invention_rate"] <= conditions["generic_checklist"]["mean_invention_rate"]
            else "fail",
        },
        {
            "id": "kernel_outscores_freeform_on_continuation",
            "claim": "On the matched live continuation simulation, kernel artifacts support a stronger downstream continuation score than free-form artifacts.",
            "status": "pass"
            if conditions["kernel"]["mean_continuation_score"] > conditions["freeform"]["mean_continuation_score"]
            and pairwise["kernel_vs_freeform"]["losses"] == 0
            else "fail",
        },
        {
            "id": "kernel_minimizes_continuation_invention",
            "claim": "On the matched live continuation simulation, kernel artifacts minimize unsupported carry-forward invention.",
            "status": "pass"
            if conditions["kernel"]["mean_invention_rate"] <= conditions["generic_checklist"]["mean_invention_rate"]
            and conditions["kernel"]["mean_invention_rate"] <= conditions["freeform"]["mean_invention_rate"]
            else "fail",
        },
    ]
    return {
        "schema_version": "1.0.0",
        "kind": "orp_reasoning_kernel_continuation_pilot_report",
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
            "kernel_mean_continuation_score": conditions["kernel"]["mean_continuation_score"],
            "generic_checklist_mean_continuation_score": conditions["generic_checklist"]["mean_continuation_score"],
            "freeform_mean_continuation_score": conditions["freeform"]["mean_continuation_score"],
            "kernel_mean_invention_rate": conditions["kernel"]["mean_invention_rate"],
            "generic_checklist_mean_invention_rate": conditions["generic_checklist"]["mean_invention_rate"],
            "freeform_mean_invention_rate": conditions["freeform"]["mean_invention_rate"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a live Codex continuation simulation across free-form, generic checklist, and kernel artifacts."
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
