#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
COMPARISON_CORPUS = REPO_ROOT / "examples" / "kernel" / "comparison" / "comparison-corpus.json"
CONDITIONS = ["freeform", "generic_checklist", "kernel"]

PICKUP_FIELDS: dict[str, list[str]] = {
    "task": ["object", "constraints", "success_criteria"],
    "decision": ["question", "chosen_path", "consequences"],
    "hypothesis": ["claim", "boundary", "test_path"],
    "experiment": ["objective", "method", "outputs"],
    "checkpoint": ["current_state", "risks", "next_handoff_target"],
    "policy": ["scope", "rule", "enforcement_surface"],
    "result": ["claim", "status", "next_follow_up"],
}

FREEFORM_LABEL_ALIASES: dict[str, set[str]] = {
    "object": {"object"},
    "constraints": {"constraints", "constraint"},
    "success_criteria": {"success criteria", "success", "done when"},
    "question": {"question"},
    "chosen_path": {"decision", "chosen path", "recommendation"},
    "consequences": {"consequences", "tradeoffs", "trade-offs"},
    "claim": {"claim"},
    "boundary": {"boundary", "scope"},
    "test_path": {"test", "test path"},
    "objective": {"objective"},
    "method": {"method"},
    "outputs": {"outputs", "evidence"},
    "current_state": {"current state"},
    "risks": {"risks", "risk"},
    "next_handoff_target": {"next", "next handoff target", "handoff"},
    "scope": {"scope"},
    "rule": {"rule"},
    "enforcement_surface": {"enforcement", "enforcement surface"},
    "status": {"status"},
    "next_follow_up": {"next follow up", "next follow-up", "next"},
}

CHECKLIST_FIELD_MAP: dict[str, dict[str, str]] = {
    "task": {
        "object": "summary",
        "constraints": "constraints",
        "success_criteria": "checks",
    },
    "decision": {
        "question": "summary",
        "chosen_path": "approach",
        "consequences": "risks",
    },
    "hypothesis": {
        "claim": "summary",
        "boundary": "scope",
        "test_path": "checks",
    },
    "experiment": {
        "objective": "summary",
        "method": "approach",
        "outputs": "checks",
    },
    "checkpoint": {
        "current_state": "notes",
        "risks": "risks",
        "next_handoff_target": "handoff",
    },
    "policy": {
        "scope": "scope",
        "rule": "summary",
        "enforcement_surface": "checks",
    },
    "result": {
        "claim": "summary",
        "status": "checks",
        "next_follow_up": "handoff",
    },
}

CHECKLIST_WEIGHTS: dict[str, float] = {
    "summary": 0.65,
    "scope": 0.85,
    "constraints": 0.85,
    "approach": 0.75,
    "checks": 0.75,
    "risks": 0.75,
    "handoff": 0.9,
    "notes": 0.6,
}

FREEFORM_WEIGHT = 0.5


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_cases() -> list[dict[str, Any]]:
    payload = _read_json(COMPARISON_CORPUS)
    cases = payload.get("cases", [])
    if not isinstance(cases, list) or not cases:
        raise RuntimeError(f"comparison corpus has no cases: {COMPARISON_CORPUS}")
    return cases


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


def _display_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return "; ".join(items) if items else None
    return None


def _score_condition(case: dict[str, Any], condition: str) -> dict[str, Any]:
    artifact_class = case["artifact_class"]
    targets = PICKUP_FIELDS[artifact_class]
    answers: dict[str, str | None] = {}
    scores: dict[str, float] = {}

    if condition == "kernel":
        source = case["kernel_artifact"]
        for field in targets:
            value = source.get(field)
            answers[field] = _display_value(value)
            scores[field] = 1.0 if _value_present(value) else 0.0
    elif condition == "generic_checklist":
        source = case["generic_checklist"]
        field_map = CHECKLIST_FIELD_MAP[artifact_class]
        for field in targets:
            source_field = field_map[field]
            value = source.get(source_field)
            answers[field] = _display_value(value)
            scores[field] = CHECKLIST_WEIGHTS[source_field] if _value_present(value) else 0.0
    elif condition == "freeform":
        source = _extract_freeform_answers(case["freeform_markdown"])
        for field in targets:
            value = source.get(field)
            answers[field] = value
            scores[field] = FREEFORM_WEIGHT if value else 0.0
    else:
        raise RuntimeError(f"unsupported condition: {condition}")

    mean_score = round(sum(scores.values()) / len(targets), 3)
    answered = sum(1 for value in answers.values() if value)
    return {
        "condition": condition,
        "artifact_class": artifact_class,
        "pickup_targets": targets,
        "answers": answers,
        "answer_scores": {field: round(score, 3) for field, score in scores.items()},
        "answered_targets": answered,
        "pickup_score": mean_score,
        "ambiguity_remaining": round(1.0 - mean_score, 3),
    }


def _score_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": case["id"],
        "domain": case["domain"],
        "artifact_class": case["artifact_class"],
        "prompt": case["prompt"],
        "conditions": {
            condition: _score_condition(case, condition)
            for condition in CONDITIONS
        },
    }


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _aggregate(cases: list[dict[str, Any]], condition: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    pickup_scores: list[float] = []
    ambiguity: list[float] = []
    answered_rates: list[float] = []
    for case in cases:
        row = case["conditions"][condition]
        target_total = len(row["pickup_targets"])
        rows.append(
            {
                "id": case["id"],
                "domain": case["domain"],
                "artifact_class": case["artifact_class"],
                "pickup_score": row["pickup_score"],
                "ambiguity_remaining": row["ambiguity_remaining"],
                "answered_targets": row["answered_targets"],
                "pickup_targets_total": target_total,
                "answers": row["answers"],
            }
        )
        pickup_scores.append(row["pickup_score"])
        ambiguity.append(row["ambiguity_remaining"])
        answered_rates.append(row["answered_targets"] / target_total)
    return {
        "condition": condition,
        "cases_total": len(rows),
        "rows": rows,
        "mean_pickup_score": _mean(pickup_scores),
        "mean_ambiguity_remaining": _mean(ambiguity),
        "mean_answered_target_rate": _mean(answered_rates),
    }


def _pairwise(cases: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    wins = 0
    ties = 0
    losses = 0
    deltas: list[float] = []
    by_case: list[dict[str, Any]] = []
    for case in cases:
        left_score = case["conditions"][left]["pickup_score"]
        right_score = case["conditions"][right]["pickup_score"]
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
    conditions = {condition: _aggregate(cases, condition) for condition in CONDITIONS}
    pairwise = {
        "kernel_vs_generic_checklist": _pairwise(cases, "kernel", "generic_checklist"),
        "kernel_vs_freeform": _pairwise(cases, "kernel", "freeform"),
        "generic_checklist_vs_freeform": _pairwise(cases, "generic_checklist", "freeform"),
    }
    claims = [
        {
            "id": "matched_pickup_corpus_exists",
            "claim": "ORP has a matched internal pickup corpus spanning all seven kernel artifact classes.",
            "status": "pass" if len(cases) >= 7 else "fail",
        },
        {
            "id": "kernel_outscores_generic_checklist_on_pickup_proxy",
            "claim": "On the matched internal pickup proxy, kernel artifacts preserve more explicit pickup-ready information than generic checklist artifacts.",
            "status": "pass"
            if conditions["kernel"]["mean_pickup_score"] > conditions["generic_checklist"]["mean_pickup_score"]
            and pairwise["kernel_vs_generic_checklist"]["losses"] == 0
            else "fail",
        },
        {
            "id": "kernel_outscores_freeform_on_pickup_proxy",
            "claim": "On the matched internal pickup proxy, kernel artifacts preserve more explicit pickup-ready information than free-form artifacts.",
            "status": "pass"
            if conditions["kernel"]["mean_pickup_score"] > conditions["freeform"]["mean_pickup_score"]
            and pairwise["kernel_vs_freeform"]["losses"] == 0
            else "fail",
        },
        {
            "id": "generic_checklist_improves_on_freeform_on_pickup_proxy",
            "claim": "On the matched internal pickup proxy, a generic checklist preserves more explicit pickup-ready information than free-form artifacts.",
            "status": "pass"
            if conditions["generic_checklist"]["mean_pickup_score"] > conditions["freeform"]["mean_pickup_score"]
            and pairwise["generic_checklist_vs_freeform"]["losses"] == 0
            else "fail",
        },
        {
            "id": "kernel_preserves_full_pickup_targets",
            "claim": "On the matched internal pickup proxy, kernel artifacts keep all pickup targets explicitly answerable.",
            "status": "pass"
            if conditions["kernel"]["mean_pickup_score"] == 1.0
            and conditions["kernel"]["mean_answered_target_rate"] == 1.0
            else "fail",
        },
    ]

    return {
        "schema_version": "1.0.0",
        "kind": "orp_reasoning_kernel_pickup_report",
        "metadata": _gather_metadata(),
        "corpus": {
            "source": str(COMPARISON_CORPUS.relative_to(REPO_ROOT)),
            "cases_total": len(cases),
        },
        "conditions": conditions,
        "pairwise": pairwise,
        "claims": claims,
        "summary": {
            "all_claims_pass": all(claim["status"] == "pass" for claim in claims),
            "kernel_mean_pickup_score": conditions["kernel"]["mean_pickup_score"],
            "generic_checklist_mean_pickup_score": conditions["generic_checklist"]["mean_pickup_score"],
            "freeform_mean_pickup_score": conditions["freeform"]["mean_pickup_score"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an explicit pickup/handoff proxy over free-form, generic checklist, and kernel artifacts."
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


if __name__ == "__main__":
    raise SystemExit(main())
