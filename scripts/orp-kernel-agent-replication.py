#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_PILOT = REPO_ROOT / "scripts" / "orp-kernel-agent-pilot.py"
CONDITIONS = ["freeform", "generic_checklist", "kernel"]


def _load_agent_pilot():
    spec = importlib.util.spec_from_file_location("orp_kernel_agent_pilot_runtime", AGENT_PILOT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load agent pilot from {AGENT_PILOT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AGENT_PILOT_MODULE = _load_agent_pilot()


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _pstdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return round(statistics.pstdev(values), 3)


def _ci95_half_width(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return round(1.96 * statistics.pstdev(values) / math.sqrt(len(values)), 3)


def _gather_metadata(model: str, repeats: int) -> dict[str, Any]:
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
        "repeats": repeats,
    }


def _aggregate_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for condition in CONDITIONS:
        pickup_scores = [run["conditions"][condition]["mean_pickup_score"] for run in runs]
        invention_rates = [run["conditions"][condition]["mean_invention_rate"] for run in runs]
        confidence = [run["conditions"][condition]["mean_confidence"] for run in runs]
        elapsed = [run["conditions"][condition]["mean_elapsed_ms"] for run in runs]
        out[condition] = {
            "mean_pickup_score": _mean(pickup_scores),
            "pickup_score_stdev": _pstdev(pickup_scores),
            "pickup_score_ci95_half_width": _ci95_half_width(pickup_scores),
            "mean_invention_rate": _mean(invention_rates),
            "invention_rate_stdev": _pstdev(invention_rates),
            "invention_rate_ci95_half_width": _ci95_half_width(invention_rates),
            "mean_confidence": _mean(confidence),
            "confidence_stdev": _pstdev(confidence),
            "mean_elapsed_ms": _mean(elapsed),
            "elapsed_ms_stdev": _pstdev(elapsed),
        }
    return out


def _aggregate_per_field_stability(runs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for condition in CONDITIONS:
        buckets: dict[tuple[str, str], dict[str, Any]] = {}
        for run in runs:
            condition_rows = run["conditions"][condition].get("rows", [])
            for row in condition_rows:
                artifact_class = row["artifact_class"]
                answers = row["answers"]
                invented_fields = set(row.get("invented_fields", []))
                expected_present = set(row.get("expected_present_fields", []))
                for field in sorted(answers):
                    key = (artifact_class, field)
                    bucket = buckets.setdefault(
                        key,
                        {
                            "artifact_class": artifact_class,
                            "field": field,
                            "case_count": 0,
                            "expected_present_count": 0,
                            "answered_count": 0,
                            "invented_count": 0,
                        },
                    )
                    bucket["case_count"] += 1
                    if field in expected_present:
                        bucket["expected_present_count"] += 1
                    if answers.get(field):
                        bucket["answered_count"] += 1
                    if field in invented_fields:
                        bucket["invented_count"] += 1
        rows = []
        for key in sorted(buckets):
            bucket = buckets[key]
            case_count = bucket["case_count"]
            rows.append(
                {
                    "artifact_class": bucket["artifact_class"],
                    "field": bucket["field"],
                    "expected_present_rate": round(bucket["expected_present_count"] / case_count, 3) if case_count else 0.0,
                    "answered_rate": round(bucket["answered_count"] / case_count, 3) if case_count else 0.0,
                    "invented_rate": round(bucket["invented_count"] / case_count, 3) if case_count else 0.0,
                    "stability_gap": round((bucket["answered_count"] - bucket["expected_present_count"]) / case_count, 3) if case_count else 0.0,
                }
            )
        out[condition] = rows
    return out


def _build_report_from_runs(*, runs: list[dict[str, Any]], model: str) -> dict[str, Any]:
    condition_summary = _aggregate_runs(runs)
    per_field_stability = _aggregate_per_field_stability(runs)
    claims = [
        {
            "id": "kernel_stays_above_generic_checklist_across_replication",
            "claim": "Across repeated live Codex runs, kernel mean pickup stays at or above generic checklist mean pickup, and above it on the aggregated sample.",
            "status": "pass"
            if all(
                run["summary"]["kernel_mean_pickup_score"]
                >= run["summary"]["generic_checklist_mean_pickup_score"]
                for run in runs
            )
            and condition_summary["kernel"]["mean_pickup_score"]
            > condition_summary["generic_checklist"]["mean_pickup_score"]
            else "fail",
        },
        {
            "id": "kernel_stays_above_freeform_across_replication",
            "claim": "Across repeated live Codex runs, kernel mean pickup stays above free-form mean pickup.",
            "status": "pass"
            if all(
                run["summary"]["kernel_mean_pickup_score"]
                > run["summary"]["freeform_mean_pickup_score"]
                for run in runs
            )
            else "fail",
        },
        {
            "id": "kernel_keeps_lowest_or_equal_invention_rate_across_replication",
            "claim": "Across repeated live Codex runs, kernel mean invention rate stays at or below the other conditions.",
            "status": "pass"
            if all(
                run["summary"]["kernel_mean_invention_rate"]
                <= run["summary"]["generic_checklist_mean_invention_rate"]
                and run["summary"]["kernel_mean_invention_rate"]
                <= run["summary"]["freeform_mean_invention_rate"]
                for run in runs
            )
            else "fail",
        },
    ]
    return {
        "schema_version": "1.0.0",
        "kind": "orp_reasoning_kernel_agent_replication_report",
        "metadata": _gather_metadata(model, len(runs)),
        "runs": runs,
        "conditions": condition_summary,
        "per_field_stability": per_field_stability,
        "claims": claims,
        "summary": {
            "all_claims_pass": all(claim["status"] == "pass" for claim in claims),
            "kernel_mean_pickup_score": condition_summary["kernel"]["mean_pickup_score"],
            "generic_checklist_mean_pickup_score": condition_summary["generic_checklist"]["mean_pickup_score"],
            "freeform_mean_pickup_score": condition_summary["freeform"]["mean_pickup_score"],
            "kernel_mean_invention_rate": condition_summary["kernel"]["mean_invention_rate"],
            "generic_checklist_mean_invention_rate": condition_summary["generic_checklist"]["mean_invention_rate"],
            "freeform_mean_invention_rate": condition_summary["freeform"]["mean_invention_rate"],
        },
    }


def build_report(
    *,
    model: str,
    repeats: int,
    case_ids: set[str] | None = None,
    progress: bool = False,
) -> dict[str, Any]:
    runs = []
    for index in range(repeats):
        run = AGENT_PILOT_MODULE.build_report(model=model, case_ids=case_ids)
        runs.append(
            {
                "run_index": index + 1,
                "summary": run["summary"],
                "conditions": run["conditions"],
                "pairwise": run["pairwise"],
            }
        )
        if progress:
            print(
                f"[orp-kernel-agent-replication] completed repeat {index + 1}/{repeats}",
                file=sys.stderr,
                flush=True,
            )
    return _build_report_from_runs(runs=runs, model=model)


def merge_reports(paths: list[Path], *, model: str) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload_runs = payload.get("runs", [])
        if not isinstance(payload_runs, list):
            raise RuntimeError(f"replication report has no runs list: {path}")
        for run in payload_runs:
            if not isinstance(run, dict):
                continue
            runs.append(
                {
                    "run_index": len(runs) + 1,
                    "summary": run["summary"],
                    "conditions": run["conditions"],
                    "pairwise": run["pairwise"],
                }
            )
    if not runs:
        raise RuntimeError("no runs found across merged replication reports")
    report = _build_report_from_runs(runs=runs, model=model)
    report["metadata"]["source_reports"] = [str(path) for path in paths]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run repeated live Codex kernel pickup simulations and summarize stability."
    )
    parser.add_argument("--out", default="", help="Optional JSON output path")
    parser.add_argument("--model", default="", help="Optional Codex model override")
    parser.add_argument("--repeats", type=int, default=3, help="Number of repeated live runs. Default: 3")
    parser.add_argument(
        "--merge-report",
        action="append",
        default=[],
        help="Merge existing replication JSON reports instead of running live repeats (repeatable).",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Print per-repeat progress lines to stderr during live runs.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case id to evaluate (repeatable). Default: all cases.",
    )
    args = parser.parse_args()
    if args.merge_report and args.repeats != 3:
        raise SystemExit("--repeats cannot be combined with --merge-report")
    if not args.merge_report and args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")

    if args.merge_report:
        report = merge_reports(
            [Path(path) if Path(path).is_absolute() else REPO_ROOT / path for path in args.merge_report],
            model=args.model,
        )
    else:
        report = build_report(
            model=args.model,
            repeats=args.repeats,
            case_ids=set(args.case_id) or None,
            progress=args.progress,
        )
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
