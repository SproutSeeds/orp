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
COMPARISON_CORPUS = REPO_ROOT / "examples" / "kernel" / "comparison" / "comparison-corpus.json"
KERNEL_SCHEMA = REPO_ROOT / "spec" / "v1" / "kernel.schema.json"
CONDITIONS = ["freeform", "generic_checklist", "kernel"]
TRANSIENT_CODEX_FAILURE_SNIPPETS = [
    "We're currently experiencing high demand",
    "unexpected status 401 Unauthorized: Missing bearer or basic authentication in header",
    "failed to connect to websocket",
    "Warning: no last agent message; wrote empty content",
]

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
    "outputs": {"outputs", "evidence"},
    "evidence_expectations": {"evidence expectations", "evidence"},
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


KERNEL_REQUIREMENTS = _load_kernel_requirements()


def _render_artifact(case: dict[str, Any], condition: str) -> str:
    if condition == "freeform":
        return case["freeform_markdown"].strip()
    if condition == "generic_checklist":
        return json.dumps(case["generic_checklist"], indent=2)
    if condition == "kernel":
        return json.dumps(case["kernel_artifact"], indent=2)
    raise RuntimeError(f"unsupported condition: {condition}")


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "artifact_type_guess": {"type": "string"},
            "primary_objective_or_state": {"type": "string"},
            "limits_or_risks": {"type": "array", "items": {"type": "string"}},
            "next_action_or_handoff": {"type": "string"},
            "confidence": {"type": "number"},
            "ambiguities": {"type": "array", "items": {"type": "string"}},
            "pickup_targets": {
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
        },
        "required": [
            "artifact_type_guess",
            "primary_objective_or_state",
            "limits_or_risks",
            "next_action_or_handoff",
            "confidence",
            "ambiguities",
            "pickup_targets",
        ],
    }


def _build_prompt(case: dict[str, Any], condition: str) -> str:
    required_fields = KERNEL_REQUIREMENTS[case["artifact_class"]]
    artifact = _render_artifact(case, condition)
    target_list = ", ".join(required_fields)
    return (
        "You are simulating a fresh downstream Codex session with no repo context.\n"
        "Using only the artifact below, recover the required artifact fields for handoff.\n"
        "Return JSON matching the provided schema.\n"
        f"In `pickup_targets`, include one entry for each of these required fields: {target_list}.\n"
        "Each entry must have `field` and `value` keys.\n"
        "For each required field, use a string only when the artifact makes that field explicit enough "
        "to carry forward directly into a canonical artifact. If the artifact does not make it explicit, use null.\n"
        "A value counts as explicit only when the artifact states it directly as a dedicated field, statement, or close field-level synonym.\n"
        "If the value would require synthesis across multiple hints, extrapolation from likely intent, or filling in a structurally missing field, use null.\n"
        "Do not infer missing values from general world knowledge. Do not invent missing structure from likely intent.\n\n"
        f"Artifact:\n{artifact}\n"
    )


def _run_cmd(
    args: list[str],
    *,
    cwd: Path,
    stdin: str | None = None,
    timeout_seconds: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        input=stdin,
        check=False,
        timeout=timeout_seconds,
    )


def _is_transient_codex_failure(proc: subprocess.CompletedProcess[str]) -> bool:
    combined = f"{proc.stdout}\n{proc.stderr}"
    return any(snippet in combined for snippet in TRANSIENT_CODEX_FAILURE_SNIPPETS)


def _run_codex_exec(
    args: list[str],
    *,
    cwd: Path,
    stdin: str,
    attempts: int = 6,
    timeout_seconds: int = 600,
) -> subprocess.CompletedProcess[str]:
    last_proc: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, attempts + 1):
        try:
            proc = _run_cmd(args, cwd=cwd, stdin=stdin, timeout_seconds=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            if attempt == attempts:
                raise RuntimeError(
                    f"codex exec timed out after {timeout_seconds}s on attempt {attempt}/{attempts}"
                ) from exc
            time.sleep(float(min(30, 2 ** (attempt - 1))))
            continue
        if proc.returncode == 0:
            return proc
        last_proc = proc
        if attempt == attempts or not _is_transient_codex_failure(proc):
            return proc
        time.sleep(float(min(30, 2 ** (attempt - 1))))
    if last_proc is None:
        raise RuntimeError("codex exec produced no process result")
    return last_proc


def _extract_session_id(stdout: str) -> str:
    match = re.search(r"session id:\s*([a-z0-9-]+)", stdout, re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_tokens_used(stdout: str) -> int | None:
    match = re.search(r"tokens used\s*\n([0-9,]+)", stdout, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _extract_freeform_answers(body: str) -> dict[str, str]:
    answers: dict[str, str] = {}
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
                answers[field] = value
    return answers


def _value_present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        if not value:
            return False
        return all(isinstance(item, str) and item.strip() for item in value)
    return False


def _expected_explicit_fields(case: dict[str, Any], condition: str) -> set[str]:
    targets = set(KERNEL_REQUIREMENTS[case["artifact_class"]])
    if condition == "kernel":
        return set(targets)
    if condition == "generic_checklist":
        checklist = case["generic_checklist"]
        field_map = CHECKLIST_FIELD_MAP[case["artifact_class"]]
        return {
            field
            for field in targets
            if _value_present(checklist.get(field_map.get(field, "")))
        }
    if condition == "freeform":
        parsed = _extract_freeform_answers(case["freeform_markdown"])
        return {field for field in targets if parsed.get(field)}
    raise RuntimeError(f"unsupported condition: {condition}")


def _run_codex_pickup(case: dict[str, Any], condition: str, *, model: str) -> dict[str, Any]:
    prompt = _build_prompt(case, condition)
    with tempfile.TemporaryDirectory(prefix="orp-kernel-agent-pilot.") as td:
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
        proc = _run_codex_exec(args, cwd=REPO_ROOT, stdin=prompt)
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
            "session_id": _extract_session_id(proc.stdout),
            "tokens_used": _extract_tokens_used(proc.stdout),
        }


def _score_pickup(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    targets = KERNEL_REQUIREMENTS[case["artifact_class"]]
    pickup_target_entries = response.get("pickup_targets", [])
    pickup_targets: dict[str, Any] = {}
    if isinstance(pickup_target_entries, list):
        for entry in pickup_target_entries:
            if not isinstance(entry, dict):
                continue
            field = entry.get("field")
            if isinstance(field, str):
                pickup_targets[field] = entry.get("value")
    answered = 0
    answers: dict[str, str | None] = {}
    expected_present = _expected_explicit_fields(case, response.get("_condition", "kernel"))
    for field in targets:
        value = pickup_targets.get(field)
        normalized = value.strip() if isinstance(value, str) and value.strip() else None
        answers[field] = normalized
        if normalized is not None:
            answered += 1
    invented_fields = [
        field
        for field, value in answers.items()
        if value is not None and field not in expected_present
    ]
    pickup_score = round(answered / len(targets), 3)
    invention_rate = round(len(invented_fields) / answered, 3) if answered else 0.0
    return {
        "pickup_targets": targets,
        "expected_present_fields": sorted(expected_present),
        "answers": answers,
        "answered_targets": answered,
        "pickup_targets_total": len(targets),
        "pickup_score": pickup_score,
        "missing_targets": [field for field, value in answers.items() if value is None],
        "invented_fields": invented_fields,
        "invented_fields_count": len(invented_fields),
        "invention_rate": invention_rate,
        "ambiguity_remaining": round(1.0 - pickup_score, 3),
        "confidence": response["confidence"],
        "ambiguities_count": len(response["ambiguities"]),
    }


def _evaluate_case(case: dict[str, Any], *, model: str) -> dict[str, Any]:
    conditions: dict[str, Any] = {}
    for condition in CONDITIONS:
        result = _run_codex_pickup(case, condition, model=model)
        score = _score_pickup(case, {**result["raw_response"], "_condition": condition})
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
    rows: list[dict[str, Any]] = []
    pickup_scores: list[float] = []
    ambiguity: list[float] = []
    confidence: list[float] = []
    ambiguity_counts: list[float] = []
    invention_rates: list[float] = []
    elapsed: list[float] = []
    tokens: list[float] = []
    answered_rates: list[float] = []
    for case in cases:
        row = case["conditions"][condition]
        score = row["score"]
        rows.append(
            {
                "id": case["id"],
                "domain": case["domain"],
                "artifact_class": case["artifact_class"],
                "pickup_score": score["pickup_score"],
                "ambiguity_remaining": score["ambiguity_remaining"],
                "answered_targets": score["answered_targets"],
                "pickup_targets_total": score["pickup_targets_total"],
                "expected_present_fields": score["expected_present_fields"],
                "answers": score["answers"],
                "invented_fields": score["invented_fields"],
                "invention_rate": score["invention_rate"],
                "artifact_type_guess": row["response"]["artifact_type_guess"],
                "confidence": score["confidence"],
                "ambiguities_count": score["ambiguities_count"],
                "elapsed_ms": row["elapsed_ms"],
                "tokens_used": row["tokens_used"],
                "session_id": row["session_id"],
            }
        )
        pickup_scores.append(score["pickup_score"])
        ambiguity.append(score["ambiguity_remaining"])
        confidence.append(score["confidence"])
        ambiguity_counts.append(score["ambiguities_count"])
        invention_rates.append(score["invention_rate"])
        elapsed.append(row["elapsed_ms"])
        if row["tokens_used"] is not None:
            tokens.append(float(row["tokens_used"]))
        answered_rates.append(score["answered_targets"] / score["pickup_targets_total"])
    return {
        "condition": condition,
        "cases_total": len(rows),
        "rows": rows,
        "mean_pickup_score": _mean(pickup_scores),
        "mean_ambiguity_remaining": _mean(ambiguity),
        "mean_answered_target_rate": _mean(answered_rates),
        "mean_confidence": _mean(confidence),
        "mean_ambiguities_count": _mean(ambiguity_counts),
        "mean_invention_rate": _mean(invention_rates),
        "mean_elapsed_ms": _mean(elapsed),
        "mean_tokens_used": _mean(tokens) if tokens else None,
    }


def _pairwise(cases: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    wins = 0
    ties = 0
    losses = 0
    deltas: list[float] = []
    by_case: list[dict[str, Any]] = []
    for case in cases:
        left_score = case["conditions"][left]["score"]["pickup_score"]
        right_score = case["conditions"][right]["score"]["pickup_score"]
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
        "mean_pickup_score_delta": _mean(deltas),
        "by_case": by_case,
    }


def _gather_metadata(model: str) -> dict[str, Any]:
    package_version = _read_json(REPO_ROOT / "package.json")["version"]
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
    cases = _load_cases()
    if case_ids:
        cases = [case for case in cases if case["id"] in case_ids]
        if not cases:
            raise RuntimeError("no comparison cases matched the requested ids")
    evaluated = [_evaluate_case(case, model=model) for case in cases]
    domains = sorted({case["domain"] for case in evaluated})
    classes = sorted({case["artifact_class"] for case in evaluated})
    conditions = {condition: _aggregate(evaluated, condition) for condition in CONDITIONS}
    pairwise = {
        "kernel_vs_generic_checklist": _pairwise(evaluated, "kernel", "generic_checklist"),
        "kernel_vs_freeform": _pairwise(evaluated, "kernel", "freeform"),
        "generic_checklist_vs_freeform": _pairwise(evaluated, "generic_checklist", "freeform"),
    }
    claims = [
        {
            "id": "matched_agent_pilot_corpus_exists",
            "claim": "ORP ran a matched Codex pickup simulation corpus spanning the requested artifact classes and domains.",
            "status": "pass" if evaluated else "fail",
        },
        {
            "id": "kernel_outscores_generic_checklist_on_agent_pickup",
            "claim": "On the matched Codex recoverability simulation, kernel artifacts preserve more explicit required-field recoverability than generic checklist artifacts.",
            "status": "pass"
            if conditions["kernel"]["mean_pickup_score"] > conditions["generic_checklist"]["mean_pickup_score"]
            and pairwise["kernel_vs_generic_checklist"]["losses"] == 0
            else "fail",
        },
        {
            "id": "kernel_outscores_freeform_on_agent_pickup",
            "claim": "On the matched Codex recoverability simulation, kernel artifacts preserve more explicit required-field recoverability than free-form artifacts.",
            "status": "pass"
            if conditions["kernel"]["mean_pickup_score"] > conditions["freeform"]["mean_pickup_score"]
            and pairwise["kernel_vs_freeform"]["losses"] == 0
            else "fail",
        },
        {
            "id": "generic_checklist_improves_on_freeform_on_agent_pickup",
            "claim": "On the matched Codex recoverability simulation, a generic checklist preserves more explicit required-field recoverability on average than free-form artifacts, but not uniformly case by case.",
            "status": "pass"
            if conditions["generic_checklist"]["mean_pickup_score"] > conditions["freeform"]["mean_pickup_score"]
            else "fail",
        },
        {
            "id": "kernel_preserves_full_pickup_targets_in_agent_simulation",
            "claim": "On the matched Codex recoverability simulation, kernel artifacts keep all required fields explicitly recoverable.",
            "status": "pass"
            if conditions["kernel"]["mean_pickup_score"] == 1.0
            and conditions["kernel"]["mean_answered_target_rate"] == 1.0
            else "fail",
        },
        {
            "id": "kernel_minimizes_invention_on_agent_pickup",
            "claim": "On the matched Codex recoverability simulation, kernel artifacts minimize unsupported field invention relative to free-form and generic checklist artifacts.",
            "status": "pass"
            if conditions["kernel"]["mean_invention_rate"] <= conditions["generic_checklist"]["mean_invention_rate"]
            and conditions["kernel"]["mean_invention_rate"] <= conditions["freeform"]["mean_invention_rate"]
            else "fail",
        },
    ]
    return {
        "schema_version": "1.0.0",
        "kind": "orp_reasoning_kernel_agent_pilot_report",
        "metadata": _gather_metadata(model),
        "corpus": {
            "source": str(COMPARISON_CORPUS.relative_to(REPO_ROOT)),
            "cases_total": len(evaluated),
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
            "kernel_mean_pickup_score": conditions["kernel"]["mean_pickup_score"],
            "generic_checklist_mean_pickup_score": conditions["generic_checklist"]["mean_pickup_score"],
            "freeform_mean_pickup_score": conditions["freeform"]["mean_pickup_score"],
            "kernel_mean_invention_rate": conditions["kernel"]["mean_invention_rate"],
            "generic_checklist_mean_invention_rate": conditions["generic_checklist"]["mean_invention_rate"],
            "freeform_mean_invention_rate": conditions["freeform"]["mean_invention_rate"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a live Codex recoverability simulation across free-form, generic checklist, and kernel artifacts."
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
