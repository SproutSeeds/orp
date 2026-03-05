#!/usr/bin/env python3
"""Install ORP profile-pack templates into a target repository.

This script keeps ORP core generic while making pack adoption easy:
- render selected pack templates to concrete config files,
- audit expected adapter dependencies in the target repo,
- write an install report with next steps.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import subprocess
import sys
from typing import Any

import yaml


COMPONENTS: dict[str, dict[str, Any]] = {
    "catalog": {
        "template_id": "erdos_problems_catalog_sync",
        "output_name": "orp.erdos-catalog-sync.yml",
        "description": "Erdos catalog sync (all/open/closed/active snapshots).",
        "required_paths": [],
    },
    "live_compare": {
        "template_id": "sunflower_live_compare_suite",
        "output_name": "orp.erdos-live-compare.yml",
        "description": "Side-by-side atomic-board compare for Problems 857/20/367.",
        "required_paths": [
            "analysis/problem857_counting_gateboard.json",
            "analysis/problem20_k3_gateboard.json",
            "analysis/problem367_sharp_gateboard.json",
            "scripts/problem857_ops_board.py",
            "scripts/problem20_ops_board.py",
            "scripts/problem367_ops_board.py",
            "scripts/frontier_status.py",
        ],
    },
    "problem857": {
        "template_id": "sunflower_problem857_discovery",
        "output_name": "orp.erdos-problem857.yml",
        "description": "Problem 857 discovery profile (board refresh/ready/spec/lean/frontier).",
        "required_paths": [
            "analysis/problem857_counting_gateboard.json",
            "docs/PROBLEM857_COUNTING_OPS_BOARD.md",
            "orchestrator/v2/scopes/problem_857.yaml",
            "orchestrator/spec_check.py",
            "scripts/problem857_ops_board.py",
            "scripts/frontier_status.py",
            "sunflower_lean/lakefile.lean",
        ],
    },
    "governance": {
        "template_id": "sunflower_mathlib_pr_governance",
        "output_name": "orp.erdos-mathlib-pr-governance.yml",
        "description": "Mathlib PR governance profile set (pre-open, draft-readiness, full flow).",
        "required_paths": [
            "docs/MATHLIB_SUBMISSION_CHECKLIST.md",
            "docs/MATHLIB_DRAFT_PR_TEMPLATE.md",
            "docs/MATHLIB_ISSUE_VIABILITY_GATE.md",
            "docs/UPSTREAM_PR_LANE.md",
            "analysis/UPSTREAM_PR_PLAN.yaml",
            "scripts/upstream-pr-plan.py",
            "scripts/upstream-pr-lane.sh",
            "scripts/mathlib-issue-viability-gate.py",
            "scripts/mathlib-naturality-snippet.sh",
            "scripts/mathlib-issue-local-gate.sh",
            "scripts/mathlib-tighten-fine-tooth-gate.sh",
            "scripts/mathlib-ready-to-draft-gate.sh",
            "scripts/mathlib-pr-body-preflight.py",
        ],
    },
}


def _now_utc() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"yaml root must be object: {path}")
    return payload


def _validate_var(raw: str) -> str:
    if "=" not in raw:
        raise RuntimeError(f"invalid --var, expected KEY=VALUE: {raw}")
    key, _value = raw.split("=", 1)
    if not key or not all(c.isupper() or c.isdigit() or c == "_" for c in key):
        raise RuntimeError(f"invalid variable key: {key}")
    return raw


def _render_component(
    *,
    orp_repo_root: Path,
    pack_root: Path,
    target_repo_root: Path,
    component_key: str,
    extra_vars: list[str],
) -> Path:
    comp = COMPONENTS[component_key]
    out_path = target_repo_root / str(comp["output_name"])
    render_script = orp_repo_root / "scripts" / "orp-pack-render.py"
    if not render_script.exists():
        raise RuntimeError(f"missing renderer script: {render_script}")

    cmd = [
        sys.executable,
        str(render_script),
        "--pack",
        str(pack_root),
        "--template",
        str(comp["template_id"]),
        "--var",
        f"TARGET_REPO_ROOT={target_repo_root}",
        "--var",
        f"ORP_REPO_ROOT={orp_repo_root}",
        "--out",
        str(out_path),
    ]
    for raw in extra_vars:
        cmd.extend(["--var", _validate_var(raw)])

    proc = subprocess.run(cmd, cwd=str(orp_repo_root), capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        msg = stderr or stdout or "unknown renderer failure"
        raise RuntimeError(f"render failed for {component_key}: {msg}")
    return out_path


def _check_dependencies(target_repo_root: Path, component_key: str) -> tuple[list[str], list[str]]:
    comp = COMPONENTS[component_key]
    required = [str(x) for x in comp.get("required_paths", [])]
    present: list[str] = []
    missing: list[str] = []
    for rel in required:
        p = target_repo_root / rel
        if p.exists():
            present.append(rel)
        else:
            missing.append(rel)
    return present, missing


def _write_report(
    *,
    report_path: Path,
    generated_at_utc: str,
    pack_id: str,
    pack_version: str,
    target_repo_root: Path,
    rendered: dict[str, Path],
    dep_summary: dict[str, dict[str, Any]],
) -> None:
    lines: list[str] = []
    lines.append("# ORP Pack Install Report")
    lines.append("")
    lines.append(f"- generated_at_utc: `{generated_at_utc}`")
    lines.append(f"- pack_id: `{pack_id}`")
    lines.append(f"- pack_version: `{pack_version}`")
    lines.append(f"- target_repo_root: `{target_repo_root}`")
    lines.append("")
    lines.append("## Rendered Configs")
    lines.append("")
    lines.append("| Component | Template | Output |")
    lines.append("|---|---|---|")
    for key, out_path in rendered.items():
        template_id = str(COMPONENTS[key]["template_id"])
        lines.append(f"| `{key}` | `{template_id}` | `{out_path}` |")
    lines.append("")
    lines.append("## Dependency Audit")
    lines.append("")
    lines.append("| Component | Required | Present | Missing |")
    lines.append("|---|---:|---:|---:|")
    for key, row in dep_summary.items():
        required = int(row["required"])
        present = int(row["present"])
        missing = int(row["missing"])
        lines.append(f"| `{key}` | {required} | {present} | {missing} |")

    lines.append("")
    lines.append("## Missing Paths")
    lines.append("")
    any_missing = False
    for key, row in dep_summary.items():
        missing_paths = row.get("missing_paths", [])
        if not missing_paths:
            continue
        any_missing = True
        lines.append(f"- `{key}`")
        for rel in missing_paths:
            lines.append(f"  - {rel}")
    if not any_missing:
        lines.append("- none")

    lines.append("")
    lines.append("## Next Steps")
    lines.append("")
    lines.append("- Run selected ORP profiles with `./scripts/orp --config <rendered-config> gate run --profile <profile>`.")
    lines.append("- Generate one-page run digest with `./scripts/orp report summary --run-id <run_id>`.")
    lines.append("- Keep ORP core generic; treat this pack as optional domain wiring.")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Install ORP pack templates into a target repo")
    p.add_argument(
        "--orp-repo-root",
        default="",
        help="ORP repo root (default: auto-detect from script location)",
    )
    p.add_argument(
        "--pack-id",
        default="erdos-open-problems",
        help="Pack id under ORP packs/ (default: erdos-open-problems)",
    )
    p.add_argument(
        "--target-repo-root",
        required=True,
        help="Target repository root where rendered ORP configs are written",
    )
    p.add_argument(
        "--include",
        action="append",
        choices=sorted(COMPONENTS.keys()),
        default=[],
        help=(
            "Component to install (repeatable). "
            "Choices: catalog, live_compare, problem857, governance. "
            "Default when omitted: all."
        ),
    )
    p.add_argument(
        "--var",
        action="append",
        default=[],
        help="Extra template variable KEY=VALUE (repeatable)",
    )
    p.add_argument(
        "--report",
        default="",
        help="Install report output path (default: <target>/orp.erdos.pack-install-report.md)",
    )
    p.add_argument(
        "--strict-deps",
        action="store_true",
        help="Exit non-zero if dependency audit finds missing paths.",
    )
    return p


def main() -> int:
    args = _build_parser().parse_args()

    if args.orp_repo_root:
        orp_repo_root = Path(args.orp_repo_root).resolve()
    else:
        orp_repo_root = Path(__file__).resolve().parent.parent
    target_repo_root = Path(args.target_repo_root).resolve()
    target_repo_root.mkdir(parents=True, exist_ok=True)

    pack_root = orp_repo_root / "packs" / args.pack_id
    pack_yml = pack_root / "pack.yml"
    if not pack_yml.exists():
        print(f"error: pack not found: {pack_root}", file=sys.stderr)
        return 2

    pack_meta = _load_yaml(pack_yml)
    pack_id = str(pack_meta.get("pack_id", args.pack_id))
    pack_version = str(pack_meta.get("version", "unknown"))
    generated_at_utc = _now_utc()

    includes = list(args.include or [])
    if not includes:
        includes = ["catalog", "live_compare", "problem857", "governance"]

    rendered: dict[str, Path] = {}
    for key in includes:
        out_path = _render_component(
            orp_repo_root=orp_repo_root,
            pack_root=pack_root,
            target_repo_root=target_repo_root,
            component_key=key,
            extra_vars=list(args.var or []),
        )
        rendered[key] = out_path

    dep_summary: dict[str, dict[str, Any]] = {}
    total_missing = 0
    for key in includes:
        present_paths, missing_paths = _check_dependencies(target_repo_root, key)
        dep_summary[key] = {
            "required": len(present_paths) + len(missing_paths),
            "present": len(present_paths),
            "missing": len(missing_paths),
            "missing_paths": missing_paths,
        }
        total_missing += len(missing_paths)

    if args.report.strip():
        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = (target_repo_root / report_path).resolve()
        else:
            report_path = report_path.resolve()
    else:
        report_path = (target_repo_root / "orp.erdos.pack-install-report.md").resolve()

    _write_report(
        report_path=report_path,
        generated_at_utc=generated_at_utc,
        pack_id=pack_id,
        pack_version=pack_version,
        target_repo_root=target_repo_root,
        rendered=rendered,
        dep_summary=dep_summary,
    )

    print(f"pack_id={pack_id}")
    print(f"pack_version={pack_version}")
    print(f"target_repo_root={target_repo_root}")
    print(f"included_components={','.join(includes)}")
    for key, out_path in rendered.items():
        print(f"rendered.{key}={out_path}")
    print(f"deps.missing_total={total_missing}")
    print(f"report={report_path}")

    if total_missing > 0 and args.strict_deps:
        return 3
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)

