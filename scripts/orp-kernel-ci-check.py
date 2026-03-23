#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


DEFAULTS = {
    "comparison": "docs/benchmarks/orp_reasoning_kernel_comparison_v0_1.json",
    "pickup": "docs/benchmarks/orp_reasoning_kernel_pickup_v0_1.json",
    "agent_pilot": "docs/benchmarks/orp_reasoning_kernel_agent_pilot_v0_1.json",
    "replication": "docs/benchmarks/orp_reasoning_kernel_agent_replication_v0_2.json",
    "canonical_continuation": "docs/benchmarks/orp_reasoning_kernel_canonical_continuation_v0_1.json",
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"benchmark root must be an object: {path}")
    return payload


def _summary_score(payload: dict[str, Any], key: str) -> float:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise RuntimeError("benchmark summary is missing")
    value = summary.get(key)
    if not isinstance(value, (int, float)):
        raise RuntimeError(f"benchmark summary key is missing or non-numeric: {key}")
    return float(value)


def _claim_failed(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    claims = payload.get("claims")
    if not isinstance(claims, list):
        return failures
    for row in claims:
        if not isinstance(row, dict):
            continue
        if str(row.get("status", "")).strip().lower() != "pass":
            failures.append(str(row.get("id", "(unknown)")).strip() or "(unknown)")
    return failures


def evaluate(paths: dict[str, Path]) -> tuple[bool, list[str]]:
    comparison = _load_json(paths["comparison"])
    pickup = _load_json(paths["pickup"])
    agent_pilot = _load_json(paths["agent_pilot"])
    replication = _load_json(paths["replication"])
    canonical = _load_json(paths["canonical_continuation"])

    notes: list[str] = []
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        (notes if condition else failures).append(message)

    comparison_failed = _claim_failed(comparison)
    pickup_failed = _claim_failed(pickup)
    agent_failed = _claim_failed(agent_pilot)
    replication_failed = _claim_failed(replication)

    check(not comparison_failed, f"comparison claims pass ({', '.join(comparison_failed) or 'ok'})")
    check(not pickup_failed, f"pickup claims pass ({', '.join(pickup_failed) or 'ok'})")
    check(not agent_failed, f"agent pilot claims pass ({', '.join(agent_failed) or 'ok'})")
    check(not replication_failed, f"replication claims pass ({', '.join(replication_failed) or 'ok'})")

    check(
        _summary_score(comparison, "kernel_mean_total_score")
        > _summary_score(comparison, "generic_checklist_mean_total_score")
        > _summary_score(comparison, "freeform_mean_total_score"),
        "comparison summary preserves kernel > checklist > free-form",
    )
    check(
        _summary_score(pickup, "kernel_mean_pickup_score")
        > _summary_score(pickup, "generic_checklist_mean_pickup_score")
        > _summary_score(pickup, "freeform_mean_pickup_score"),
        "pickup summary preserves kernel > checklist > free-form",
    )
    check(
        _summary_score(agent_pilot, "kernel_mean_pickup_score")
        > _summary_score(agent_pilot, "generic_checklist_mean_pickup_score")
        > _summary_score(agent_pilot, "freeform_mean_pickup_score"),
        "agent pilot summary preserves kernel > checklist > free-form",
    )
    check(
        _summary_score(replication, "kernel_mean_pickup_score")
        > _summary_score(replication, "generic_checklist_mean_pickup_score")
        > _summary_score(replication, "freeform_mean_pickup_score"),
        "replication summary preserves kernel > checklist > free-form",
    )
    check(
        _summary_score(replication, "kernel_mean_invention_rate")
        <= _summary_score(replication, "generic_checklist_mean_invention_rate")
        and _summary_score(replication, "kernel_mean_invention_rate")
        <= _summary_score(replication, "freeform_mean_invention_rate"),
        "replication keeps kernel invention at or below the other conditions",
    )
    check(
        _summary_score(canonical, "kernel_mean_total_score")
        > _summary_score(canonical, "generic_checklist_mean_total_score")
        > _summary_score(canonical, "freeform_mean_total_score"),
        "canonical continuation keeps kernel > checklist > free-form on mean total score",
    )
    check(
        _summary_score(canonical, "kernel_mean_invention_rate")
        < _summary_score(canonical, "generic_checklist_mean_invention_rate")
        < _summary_score(canonical, "freeform_mean_invention_rate"),
        "canonical continuation keeps kernel < checklist < free-form on invention rate",
    )

    messages = notes + [f"FAIL: {row}" for row in failures]
    return (len(failures) == 0, messages)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check committed ORP kernel benchmark artifacts against CI safety thresholds.")
    for key, default in DEFAULTS.items():
        parser.add_argument(f"--{key.replace('_', '-')}", default=default, help=f"Path to the {key} benchmark JSON")
    args = parser.parse_args(argv)

    paths = {
        key: Path(getattr(args, key)).resolve()
        for key in DEFAULTS
    }
    ok, messages = evaluate(paths)
    for row in messages:
        print(row)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
