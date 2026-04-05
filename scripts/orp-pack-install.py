#!/usr/bin/env python3
"""Install ORP profile-pack templates into a target repository.

This script keeps ORP core generic while making pack adoption easy:
- render selected pack templates to concrete config files,
- optionally scaffold starter adapters for install-and-go usage,
- audit expected adapter dependencies in the target repo,
- write an install report with next steps.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import yaml


LEGACY_PACK_SPECS: dict[str, dict[str, Any]] = {
    "erdos-open-problems": {
        "default_includes": ["catalog", "live_compare", "problem857"],
        "report_name": "orp.erdos.pack-install-report.md",
        "components": {
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
                    "orchestrator/problem857_public_spec_check.py",
                    "scripts/problem857_ops_board.py",
                    "scripts/frontier_status.py",
                    "sunflower_lean",
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
        },
    },
    "external-pr-governance": {
        "default_includes": ["governance", "feedback_hardening"],
        "report_name": "orp.external-pr.pack-install-report.md",
        "components": {
            "governance": {
                "template_id": "oss_pr_governance",
                "output_name": "orp.external-pr-governance.yml",
                "description": "Generic external contribution governance profiles (watch/select through draft lifecycle).",
                "required_paths": ["analysis/PR_DRAFT_BODY.md"],
            },
            "feedback_hardening": {
                "template_id": "oss_feedback_hardening",
                "output_name": "orp.external-pr-feedback-hardening.yml",
                "description": "Maintainer-feedback hardening profile.",
                "required_paths": [],
            },
        },
    },
    "issue-smashers": {
        "default_includes": ["workspace", "feedback_hardening"],
        "report_name": "orp.issue-smashers.pack-install-report.md",
        "components": {
            "workspace": {
                "template_id": "issue_smashers_workspace",
                "output_name": "orp.issue-smashers.yml",
                "description": "Opinionated issue-smashers workspace and external contribution governance profiles.",
                "required_paths": [
                    "issue-smashers/README.md",
                    "issue-smashers/WORKSPACE_RULES.md",
                    "issue-smashers/setup-issue-smashers.sh",
                    "issue-smashers/analysis/ISSUE_SMASHERS_WATCHLIST.json",
                    "issue-smashers/analysis/ISSUE_SMASHERS_STATUS.md",
                    "issue-smashers/analysis/PR_DRAFT_BODY.md",
                ],
            },
            "feedback_hardening": {
                "template_id": "issue_smashers_feedback_hardening",
                "output_name": "orp.issue-smashers-feedback-hardening.yml",
                "description": "Issue-smashers feedback hardening profile.",
                "required_paths": [
                    "issue-smashers/WORKSPACE_RULES.md",
                    "issue-smashers/analysis/ISSUE_SMASHERS_STATUS.md",
                ],
            },
        },
    },
}

BOARD_PATHS = {
    857: "analysis/problem857_counting_gateboard.json",
    20: "analysis/problem20_k3_gateboard.json",
    367: "analysis/problem367_sharp_gateboard.json",
}

BOARD_MD_PATHS = {
    857: "docs/PROBLEM857_COUNTING_OPS_BOARD.md",
    20: "docs/PROBLEM20_K3_OPS_BOARD.md",
    367: "docs/PROBLEM367_SHARP_OPS_BOARD.md",
}

BOARD_SEEDS: dict[int, dict[str, Any]] = {
    857: {
        "board_id": "problem857_counting_gateboard",
        "problem_id": 857,
        "updated_utc": "",
        "starter_scaffold": True,
        "starter_note": "starter board generated by ORP pack install",
        "route_status": [
            {"route": "counting_uniform", "loose_done": 7, "loose_total": 7, "strict_done": 7, "strict_total": 7},
            {"route": "container_v2", "loose_done": 5, "loose_total": 5, "strict_done": 5, "strict_total": 5},
        ],
        "tickets": [
            {"ticket": "T1", "leaf": "CountingUniformCore", "leaf_strict": "done", "gates_done": 5, "gates_total": 5, "atoms_done": 14, "atoms_total": 14},
            {"ticket": "T6", "leaf": "ContainerLift", "leaf_strict": "open", "gates_done": 5, "gates_total": 5, "atoms_done": 32, "atoms_total": 32},
        ],
        "ready_atoms": 0,
        "no_go_active": [],
    },
    20: {
        "board_id": "problem20_k3_gateboard",
        "problem_id": 20,
        "updated_utc": "",
        "starter_scaffold": True,
        "starter_note": "starter board generated by ORP pack install",
        "route_status": [
            {"route": "uniform_prize", "loose_done": 7, "loose_total": 7, "strict_done": 7, "strict_total": 7},
            {"route": "uniform_prize_final_k3", "loose_done": 5, "loose_total": 5, "strict_done": 5, "strict_total": 5},
            {"route": "uniform_prize_full_all_k", "loose_done": 0, "loose_total": 1, "strict_done": 0, "strict_total": 1},
        ],
        "tickets": [
            {"ticket": "T1", "leaf": "UniformBoundF3Global", "leaf_strict": "done", "gates_done": 5, "gates_total": 5, "atoms_done": 16, "atoms_total": 16},
            {"ticket": "T6", "leaf": "UniformK3From7BaseRangeHyp", "leaf_strict": "open", "gates_done": 5, "gates_total": 5, "atoms_done": 77, "atoms_total": 77},
        ],
        "ready_atoms": 0,
        "no_go_active": [],
    },
    367: {
        "board_id": "problem367_sharp_gateboard",
        "problem_id": 367,
        "updated_utc": "",
        "starter_scaffold": True,
        "starter_note": "starter board generated by ORP pack install",
        "route_status": [
            {"route": "sieve_weighted_tail", "loose_done": 5, "loose_total": 5, "strict_done": 5, "strict_total": 5},
            {"route": "full", "loose_done": 9, "loose_total": 9, "strict_done": 8, "strict_total": 9},
            {"route": "sieve", "loose_done": 5, "loose_total": 5, "strict_done": 4, "strict_total": 5},
        ],
        "tickets": [
            {"ticket": "T1", "leaf": "LargeTwoFullPartRarity", "leaf_strict": "open", "gates_done": 5, "gates_total": 5, "atoms_done": 15, "atoms_total": 15},
            {"ticket": "T5", "leaf": "LargeTwoFullPartRarity", "leaf_strict": "open", "gates_done": 5, "gates_total": 5, "atoms_done": 15, "atoms_total": 15},
        ],
        "ready_atoms": 0,
        "no_go_active": [
            "not_FilteredDyadicLargeRadCardBound10_6",
            "not_FilteredDyadicSmallRadCardBound10_4",
            "not_WeightedTailSeriesBoundOnLeFilteredDyadic10SplitBudgetAtoms",
        ],
    },
}

STARTER_RUNTIME = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
from typing import Any

BOARD_PATHS = {
    857: "analysis/problem857_counting_gateboard.json",
    20: "analysis/problem20_k3_gateboard.json",
    367: "analysis/problem367_sharp_gateboard.json",
}

BOARD_MD_PATHS = {
    857: "docs/PROBLEM857_COUNTING_OPS_BOARD.md",
    20: "docs/PROBLEM20_K3_OPS_BOARD.md",
    367: "docs/PROBLEM367_SHARP_OPS_BOARD.md",
}

BOARD_SEEDS = {
    857: {
        "board_id": "problem857_counting_gateboard",
        "problem_id": 857,
        "updated_utc": "",
        "starter_scaffold": True,
        "starter_note": "starter board generated by ORP pack install",
        "route_status": [
            {"route": "counting_uniform", "loose_done": 7, "loose_total": 7, "strict_done": 7, "strict_total": 7},
            {"route": "container_v2", "loose_done": 5, "loose_total": 5, "strict_done": 5, "strict_total": 5},
        ],
        "tickets": [
            {"ticket": "T1", "leaf": "CountingUniformCore", "leaf_strict": "done", "gates_done": 5, "gates_total": 5, "atoms_done": 14, "atoms_total": 14},
            {"ticket": "T6", "leaf": "ContainerLift", "leaf_strict": "open", "gates_done": 5, "gates_total": 5, "atoms_done": 32, "atoms_total": 32},
        ],
        "ready_atoms": 0,
        "no_go_active": [],
    },
    20: {
        "board_id": "problem20_k3_gateboard",
        "problem_id": 20,
        "updated_utc": "",
        "starter_scaffold": True,
        "starter_note": "starter board generated by ORP pack install",
        "route_status": [
            {"route": "uniform_prize", "loose_done": 7, "loose_total": 7, "strict_done": 7, "strict_total": 7},
            {"route": "uniform_prize_final_k3", "loose_done": 5, "loose_total": 5, "strict_done": 5, "strict_total": 5},
            {"route": "uniform_prize_full_all_k", "loose_done": 0, "loose_total": 1, "strict_done": 0, "strict_total": 1},
        ],
        "tickets": [
            {"ticket": "T1", "leaf": "UniformBoundF3Global", "leaf_strict": "done", "gates_done": 5, "gates_total": 5, "atoms_done": 16, "atoms_total": 16},
            {"ticket": "T6", "leaf": "UniformK3From7BaseRangeHyp", "leaf_strict": "open", "gates_done": 5, "gates_total": 5, "atoms_done": 77, "atoms_total": 77},
        ],
        "ready_atoms": 0,
        "no_go_active": [],
    },
    367: {
        "board_id": "problem367_sharp_gateboard",
        "problem_id": 367,
        "updated_utc": "",
        "starter_scaffold": True,
        "starter_note": "starter board generated by ORP pack install",
        "route_status": [
            {"route": "sieve_weighted_tail", "loose_done": 5, "loose_total": 5, "strict_done": 5, "strict_total": 5},
            {"route": "full", "loose_done": 9, "loose_total": 9, "strict_done": 8, "strict_total": 9},
            {"route": "sieve", "loose_done": 5, "loose_total": 5, "strict_done": 4, "strict_total": 5},
        ],
        "tickets": [
            {"ticket": "T1", "leaf": "LargeTwoFullPartRarity", "leaf_strict": "open", "gates_done": 5, "gates_total": 5, "atoms_done": 15, "atoms_total": 15},
            {"ticket": "T5", "leaf": "LargeTwoFullPartRarity", "leaf_strict": "open", "gates_done": 5, "gates_total": 5, "atoms_done": 15, "atoms_total": 15},
        ],
        "ready_atoms": 0,
        "no_go_active": [
            "not_FilteredDyadicLargeRadCardBound10_6",
            "not_FilteredDyadicSmallRadCardBound10_4",
            "not_WeightedTailSeriesBoundOnLeFilteredDyadic10SplitBudgetAtoms",
        ],
    },
}


def _now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _board_path(root: Path, problem: int) -> Path:
    return root / BOARD_PATHS[problem]


def _board_md_path(root: Path, problem: int) -> Path:
    return root / BOARD_MD_PATHS[problem]


def _seed(problem: int) -> dict[str, Any]:
    payload = json.loads(json.dumps(BOARD_SEEDS[problem]))
    payload["updated_utc"] = _now_utc()
    return payload


def _load_board(root: Path, problem: int) -> dict[str, Any]:
    path = _board_path(root, problem)
    if not path.exists():
        board = _seed(problem)
        _save_board(root, problem, board)
        return board
    return json.loads(path.read_text(encoding="utf-8"))


def _save_board(root: Path, problem: int, board: dict[str, Any]) -> None:
    path = _board_path(root, problem)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, indent=2) + "\\n", encoding="utf-8")


def _atoms(board: dict[str, Any]) -> dict[str, Any]:
    atoms = board.get("atoms", {})
    if isinstance(atoms, dict):
        return atoms
    return {}


def _ready_atom_ids(board: dict[str, Any]) -> list[str]:
    ready_ids: list[str] = []
    for atom_id, payload in _atoms(board).items():
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status", "")).strip().lower()
        if status == "ready":
            ready_ids.append(str(atom_id))
    return sorted(ready_ids)


def _sync_ready_atoms(board: dict[str, Any]) -> None:
    board["ready_atoms"] = len(_ready_atom_ids(board))


def _write_board_md(root: Path, problem: int, board: dict[str, Any]) -> None:
    _sync_ready_atoms(board)
    lines = []
    lines.append(f"# Problem {problem} Ops Board")
    lines.append("")
    lines.append(f"- updated_utc: `{board.get('updated_utc', '')}`")
    lines.append(f"- ready_atoms: `{int(board.get('ready_atoms', 0))}`")
    public_repo = board.get("public_repo", {})
    if isinstance(public_repo, dict) and public_repo:
        lines.append(f"- public_repo_url: `{public_repo.get('url', '')}`")
        lines.append(f"- public_repo_ref: `{public_repo.get('ref', '')}`")
        lines.append(f"- public_repo_sync_root: `{public_repo.get('sync_root', '')}`")
    lines.append("")
    lines.append("## Routes")
    lines.append("")
    for row in board.get("route_status", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "- route={route} loose={ld}/{lt} strict={sd}/{st}".format(
                route=row.get("route", ""),
                ld=row.get("loose_done", 0),
                lt=row.get("loose_total", 0),
                sd=row.get("strict_done", 0),
                st=row.get("strict_total", 0),
            )
        )
    lines.append("")
    lines.append("## Tickets")
    lines.append("")
    for row in board.get("tickets", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "- ticket={ticket} leaf={leaf} leaf_strict={leaf_strict} gates={gd}/{gt} atoms={ad}/{at}".format(
                ticket=row.get("ticket", ""),
                leaf=row.get("leaf", ""),
                leaf_strict=row.get("leaf_strict", ""),
                gd=row.get("gates_done", 0),
                gt=row.get("gates_total", 0),
                ad=row.get("atoms_done", 0),
                at=row.get("atoms_total", 0),
            )
        )

    atoms = _atoms(board)
    if atoms:
        lines.append("")
        lines.append("## Atom States")
        lines.append("")
        for atom_id in sorted(atoms):
            payload = atoms.get(atom_id, {})
            status = payload.get("status", "") if isinstance(payload, dict) else ""
            lines.append(f"- atom={atom_id} status={status}")

    out_path = _board_md_path(root, problem)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def _print_show(board: dict[str, Any]) -> None:
    _sync_ready_atoms(board)
    print(f"updated_utc={board.get('updated_utc', '')}")
    for row in board.get("route_status", []):
        if not isinstance(row, dict):
            continue
        print(
            "route={route} loose={ld}/{lt} strict={sd}/{st}".format(
                route=row.get("route", ""),
                ld=row.get("loose_done", 0),
                lt=row.get("loose_total", 0),
                sd=row.get("strict_done", 0),
                st=row.get("strict_total", 0),
            )
        )
    for row in board.get("tickets", []):
        if not isinstance(row, dict):
            continue
        print(
            "ticket={ticket} leaf={leaf} leaf_strict={leaf_strict} gates={gd}/{gt} atoms={ad}/{at}".format(
                ticket=row.get("ticket", ""),
                leaf=row.get("leaf", ""),
                leaf_strict=row.get("leaf_strict", ""),
                gd=row.get("gates_done", 0),
                gt=row.get("gates_total", 0),
                ad=row.get("atoms_done", 0),
                at=row.get("atoms_total", 0),
            )
        )
    atoms = _atoms(board)
    for atom_id in sorted(atoms):
        payload = atoms.get(atom_id, {})
        status = payload.get("status", "") if isinstance(payload, dict) else ""
        print(f"atom={atom_id} status={status}")
    print(f"ready_atoms={int(board.get('ready_atoms', 0))}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Starter atomic board ops runtime")
    parser.add_argument("--problem", required=True, type=int, choices=[857, 20, 367])
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("show")

    ready = sub.add_parser("ready")
    ready.add_argument("--allow-no-go", action="store_true")

    refresh = sub.add_parser("refresh")
    refresh.add_argument("--write-md", action="store_true")
    refresh.add_argument("--sync-json", action="store_true")

    set_atom = sub.add_parser("set-atom")
    set_atom.add_argument("atom_id")
    set_atom.add_argument("--status", required=True)

    args = parser.parse_args()

    root = Path(".").resolve()
    board = _load_board(root, args.problem)

    if args.cmd == "show":
        _print_show(board)
        return 0

    if args.cmd == "ready":
        _sync_ready_atoms(board)
        atoms = _atoms(board)
        if args.problem == 367:
            no_go = board.get("no_go_active", [])
            if isinstance(no_go, list):
                print("no_go_active=" + ",".join(str(x) for x in no_go))
            else:
                print("no_go_active=")
        for atom_id in _ready_atom_ids(board):
            payload = atoms.get(atom_id, {})
            ticket = "starter"
            gate = "ready"
            deps = "root"
            if isinstance(payload, dict):
                raw_ticket = str(payload.get("ticket_id", "")).strip()
                raw_gate = str(payload.get("gate_id", "")).strip()
                raw_deps = payload.get("deps", "root")
                if raw_ticket:
                    ticket = raw_ticket
                if raw_gate:
                    gate = raw_gate
                if isinstance(raw_deps, list):
                    deps_items = [str(x).strip() for x in raw_deps if str(x).strip()]
                    deps = ",".join(deps_items) if deps_items else "root"
                else:
                    deps_text = str(raw_deps).strip()
                    deps = deps_text or "root"
            print(f"ready={atom_id} ticket={ticket} gate={gate} deps={deps}")
        print(f"ready_atoms={int(board.get('ready_atoms', 0))}")
        return 0

    if args.cmd == "refresh":
        board["updated_utc"] = _now_utc()
        _sync_ready_atoms(board)
        _save_board(root, args.problem, board)
        if args.write_md:
            _write_board_md(root, args.problem, board)
        print(f"refreshed_board={_board_path(root, args.problem)}")
        if args.write_md:
            print(f"refreshed_board_md={_board_md_path(root, args.problem)}")
        return 0

    if args.cmd == "set-atom":
        atoms = board.setdefault("atoms", {})
        if not isinstance(atoms, dict):
            atoms = {}
            board["atoms"] = atoms
        atoms[args.atom_id] = {"status": args.status}
        board["updated_utc"] = _now_utc()
        _sync_ready_atoms(board)
        _save_board(root, args.problem, board)
        print(f"atom_id={args.atom_id}")
        print(f"atom_status={args.status}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
"""

STARTER_FRONTIER = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

BOARD_PATHS = {
    857: "analysis/problem857_counting_gateboard.json",
    20: "analysis/problem20_k3_gateboard.json",
    367: "analysis/problem367_sharp_gateboard.json",
}


def _load_board(root: Path, problem: int) -> dict[str, Any]:
    path = root / BOARD_PATHS[problem]
    if not path.exists():
        return {"route_status": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _pct(done: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(round((100.0 * done) / total))


def main() -> int:
    parser = argparse.ArgumentParser(description="Starter frontier status")
    parser.add_argument("--problem", required=True, type=int, choices=[857, 20, 367])
    args = parser.parse_args()

    board = _load_board(Path(".").resolve(), args.problem)
    routes = board.get("route_status", [])
    if not isinstance(routes, list):
        routes = []

    print(f"== Loose Routes ({args.problem}) ==")
    best_name = ""
    best_pct = -1
    for row in routes:
        if not isinstance(row, dict):
            continue
        name = str(row.get("route", "")).strip()
        ld = int(row.get("loose_done", 0) or 0)
        lt = int(row.get("loose_total", 0) or 0)
        print(f"{name}: {ld}/{lt}")
        pct = _pct(ld, lt)
        if pct > best_pct:
            best_pct = pct
            best_name = name

    print("")
    print(f"== Strict Routes ({args.problem}) ==")
    for row in routes:
        if not isinstance(row, dict):
            continue
        name = str(row.get("route", "")).strip()
        sd = int(row.get("strict_done", 0) or 0)
        st = int(row.get("strict_total", 0) or 0)
        print(f"{name}: {sd}/{st}")

    print("")
    print("== Next Focus ==")
    if best_name:
        print(f"Best loose route: {best_name} ({best_pct}%)")
    else:
        print("Best loose route: (none) (0%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

STARTER_WRAPPER = """#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parent
    cmd = [sys.executable, str(root / "orp_atomic_board_runtime.py"), "--problem", "{PROBLEM}", *sys.argv[1:]]
    return int(subprocess.call(cmd))


if __name__ == "__main__":
    raise SystemExit(main())
"""

STARTER_SPEC_CHECK = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
from typing import Any


PROBLEM_ID = 857
DEFAULT_SELECTED_PROBLEM = "analysis/erdos_problems/selected/erdos_problem.857.json"
LEGACY_SELECTED_PROBLEM = "analysis/selected/erdos_problem.857.json"
DEFAULT_SCOPE = "orchestrator/v2/scopes/problem_857.yaml"
DEFAULT_BOARD = "analysis/problem857_counting_gateboard.json"


def _now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(Path(".").resolve()))
    except Exception:
        return str(path)


def _coerce_scalar(text: str) -> Any:
    raw = text.strip()
    if not raw:
        return ""
    if raw.startswith(("'", '"')) and raw.endswith(("'", '"')) and len(raw) >= 2:
        raw = raw[1:-1]
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if raw.isdigit():
        return int(raw)
    return raw


def _load_scope(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None  # type: ignore[assignment]

    if yaml is not None:
        loaded = yaml.safe_load(text)
        if isinstance(loaded, dict):
            return loaded

    payload: dict[str, Any] = {}
    active_list: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if active_list and raw_line.startswith("  - "):
            values = payload.setdefault(active_list, [])
            if isinstance(values, list):
                values.append(_coerce_scalar(raw_line.split("- ", 1)[1]))
            continue
        active_list = None
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            payload[key] = []
            active_list = key
            continue
        payload[key] = _coerce_scalar(value)
    return payload


def _add_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    ok: bool,
    detail: str,
    path: Path | None = None,
    expected: Any = None,
    actual: Any = None,
) -> bool:
    row: dict[str, Any] = {
        "id": check_id,
        "status": "PASS" if ok else "FAIL",
        "detail": detail,
    }
    if path is not None:
        row["path"] = _rel(path)
    if expected is not None:
        row["expected"] = expected
    if actual is not None:
        row["actual"] = actual
    checks.append(row)
    return ok


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"json root must be object: {path}")
    return payload


def _candidate_paths(raw: list[str]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for entry in raw:
        value = entry.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(Path(value))
    return out


def _first_existing(paths: list[Path]) -> Path | None:
    root = Path(".").resolve()
    for candidate in paths:
        full = candidate if candidate.is_absolute() else root / candidate
        if full.exists():
            return full
    return None


def _problem_id_from_value(value: Any) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return 0
    try:
        return int(text)
    except Exception:
        match = re.search(r"(\\d+)", text)
        if match:
            return int(match.group(1))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate public Problem 857 scope consistency against synced Erdos data"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--problem-id", type=int, default=PROBLEM_ID)
    parser.add_argument(
        "--scope-mode",
        default="starter",
        help="Scope schema mode to validate (starter|public_repo).",
    )
    parser.add_argument(
        "--expect-starter-scaffold",
        default="true",
        help="Whether the board is expected to be marked starter_scaffold (true|false).",
    )
    parser.add_argument(
        "--selected-problem",
        action="append",
        default=[],
        help="Selected problem JSON path (repeatable; first existing path wins).",
    )
    parser.add_argument("--scope", default=DEFAULT_SCOPE, help="Scope YAML path.")
    parser.add_argument("--board", default=DEFAULT_BOARD, help="Board JSON path.")
    args = parser.parse_args()
    scope_mode = str(args.scope_mode).strip().lower()
    if scope_mode not in {"starter", "public_repo"}:
        raise RuntimeError(f"unsupported --scope-mode: {scope_mode}")
    expected_starter_scaffold = str(args.expect_starter_scaffold).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    checks: list[dict[str, Any]] = []
    selected_candidates = _candidate_paths(
        list(args.selected_problem) or [DEFAULT_SELECTED_PROBLEM, LEGACY_SELECTED_PROBLEM]
    )
    selected_path = _first_existing(selected_candidates)
    scope_path = Path(args.scope).resolve()
    board_path = Path(args.board).resolve()

    selected_payload: dict[str, Any] = {}
    if selected_path is None:
        checked = ", ".join(str(path) for path in selected_candidates)
        _add_check(
            checks,
            check_id="selected_problem_exists",
            ok=False,
            detail=f"selected problem JSON not found; checked: {checked}",
        )
    else:
        try:
            selected_payload = _load_json(selected_path)
        except Exception as exc:
            _add_check(
                checks,
                check_id="selected_problem_json_valid",
                ok=False,
                detail=f"failed to parse selected problem JSON: {exc}",
                path=selected_path,
            )
        else:
            _add_check(
                checks,
                check_id="selected_problem_exists",
                ok=True,
                detail="selected problem JSON is present",
                path=selected_path,
            )

    problem_payload = (
        selected_payload.get("problem", {})
        if isinstance(selected_payload.get("problem"), dict)
        else {}
    )
    source_payload = (
        selected_payload.get("source", {})
        if isinstance(selected_payload.get("source"), dict)
        else {}
    )

    public_problem_id = _problem_id_from_value(problem_payload.get("problem_id", 0))
    _add_check(
        checks,
        check_id="selected_problem_id_matches",
        ok=public_problem_id == int(args.problem_id),
        detail="public selected problem id matches workflow problem id",
        path=selected_path,
        expected=int(args.problem_id),
        actual=public_problem_id,
    )
    public_status = str(problem_payload.get("status_bucket", "")).strip()
    _add_check(
        checks,
        check_id="selected_problem_status_present",
        ok=bool(public_status),
        detail="public selected problem includes status_bucket",
        path=selected_path,
        actual=public_status,
    )
    source_ok = (
        str(source_payload.get("site", "")).strip() == "erdosproblems.com"
        and bool(str(source_payload.get("url", "")).strip())
        and bool(str(source_payload.get("source_sha256", "")).strip())
    )
    _add_check(
        checks,
        check_id="selected_problem_source_metadata_present",
        ok=source_ok,
        detail="public selected problem records Erdos source metadata",
        path=selected_path,
        expected="site=erdosproblems.com with url and source_sha256",
        actual={
            "site": str(source_payload.get("site", "")).strip(),
            "url": str(source_payload.get("url", "")).strip(),
            "source_sha256": str(source_payload.get("source_sha256", "")).strip(),
        },
    )
    statement = str(problem_payload.get("statement", "")).strip()
    _add_check(
        checks,
        check_id="selected_problem_statement_present",
        ok=bool(statement),
        detail="public selected problem includes a non-empty statement",
        path=selected_path,
    )

    scope_payload: dict[str, Any] = {}
    if not scope_path.exists():
        _add_check(
            checks,
            check_id="scope_exists",
            ok=False,
            detail="installed Problem 857 scope YAML is missing",
            path=scope_path,
        )
    else:
        try:
            scope_payload = _load_scope(scope_path)
        except Exception as exc:
            _add_check(
                checks,
                check_id="scope_yaml_valid",
                ok=False,
                detail=f"failed to parse scope YAML: {exc}",
                path=scope_path,
            )
        else:
            _add_check(
                checks,
                check_id="scope_exists",
                ok=True,
                detail="installed Problem 857 scope YAML is present",
                path=scope_path,
            )

    scope_problem_id = _problem_id_from_value(scope_payload.get("problem_id", 0))
    _add_check(
        checks,
        check_id="scope_problem_id_matches",
        ok=scope_problem_id == int(args.problem_id),
        detail="scope problem id matches workflow problem id",
        path=scope_path,
        expected=int(args.problem_id),
        actual=scope_problem_id,
    )
    if scope_mode == "starter":
        scope_status = str(scope_payload.get("status", "")).strip()
        _add_check(
            checks,
            check_id="scope_status_matches_public_status",
            ok=bool(scope_status) and bool(public_status) and scope_status == public_status,
            detail="scope status matches public selected problem status",
            path=scope_path,
            expected=public_status or "(non-empty public status)",
            actual=scope_status,
        )
        scope_name = str(scope_payload.get("name", "")).strip()
        _add_check(
            checks,
            check_id="scope_name_mentions_problem",
            ok=str(args.problem_id) in scope_name,
            detail="scope name mentions the workflow problem id",
            path=scope_path,
            expected=f"contains {args.problem_id}",
            actual=scope_name,
        )
    else:
        scope_display_name = str(scope_payload.get("display_name", scope_payload.get("name", ""))).strip()
        _add_check(
            checks,
            check_id="scope_display_name_mentions_problem",
            ok=str(args.problem_id) in scope_display_name,
            detail="public scope display name mentions the workflow problem id",
            path=scope_path,
            expected=f"contains {args.problem_id}",
            actual=scope_display_name,
        )
        lean_files = scope_payload.get("lean_files", [])
        _add_check(
            checks,
            check_id="scope_lean_files_present",
            ok=isinstance(lean_files, list) and len(lean_files) > 0,
            detail="public scope lists Lean files for the problem workspace",
            path=scope_path,
            expected="non-empty list",
            actual=f"{len(lean_files) if isinstance(lean_files, list) else 0} files",
        )
        north_star = str(scope_payload.get("north_star_lane", "")).strip()
        reduction_route = str(scope_payload.get("reduction_route", "")).strip()
        _add_check(
            checks,
            check_id="scope_routes_present",
            ok=bool(north_star or reduction_route),
            detail="public scope records an active route or north-star lane",
            path=scope_path,
            expected="north_star_lane or reduction_route",
            actual={"north_star_lane": north_star, "reduction_route": reduction_route},
        )

    board_payload: dict[str, Any] = {}
    if not board_path.exists():
        _add_check(
            checks,
            check_id="board_exists",
            ok=False,
            detail="starter board JSON is missing",
            path=board_path,
        )
    else:
        try:
            board_payload = _load_json(board_path)
        except Exception as exc:
            _add_check(
                checks,
                check_id="board_json_valid",
                ok=False,
                detail=f"failed to parse board JSON: {exc}",
                path=board_path,
            )
        else:
            _add_check(
                checks,
                check_id="board_exists",
                ok=True,
                detail="starter board JSON is present",
                path=board_path,
            )

    board_problem_id = _problem_id_from_value(board_payload.get("problem_id", 0))
    _add_check(
        checks,
        check_id="board_problem_id_matches",
        ok=board_problem_id == int(args.problem_id),
        detail="board problem id matches workflow problem id",
        path=board_path,
        expected=int(args.problem_id),
        actual=board_problem_id,
    )
    _add_check(
        checks,
        check_id="board_starter_scaffold_matches_mode",
        ok=bool(board_payload.get("starter_scaffold", False)) == expected_starter_scaffold,
        detail="board starter_scaffold flag matches the expected workflow mode",
        path=board_path,
        expected=expected_starter_scaffold,
        actual=bool(board_payload.get("starter_scaffold", False)),
    )
    live_payload = board_payload.get("live_snapshot", board_payload.get("live", {}))
    if not isinstance(live_payload, dict):
        live_payload = {}
    route_status = board_payload.get("route_status", live_payload.get("routes", []))
    _add_check(
        checks,
        check_id="board_route_status_present",
        ok=isinstance(route_status, list) and len(route_status) > 0,
        detail="board includes route status rows",
        path=board_path,
        expected="non-empty list",
        actual=f"{len(route_status) if isinstance(route_status, list) else 0} rows",
    )

    failures = [row for row in checks if row.get("status") == "FAIL"]
    status = "PASS" if not failures else "FAIL"
    out_path = Path("orchestrator") / "logs" / args.run_id / "SPEC_CHECK.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "checker": "problem857_public_spec_check",
        "run_id": args.run_id,
        "problem_id": int(args.problem_id),
        "scope_mode": scope_mode,
        "checked_at_utc": _now_utc(),
        "note": (
            "Validates that the synced public Problem 857 payload, installed scope, "
            "and board agree on the target problem."
        ),
        "starter_scaffold": bool(board_payload.get("starter_scaffold", False)),
        "selected_problem_path": _rel(selected_path) if selected_path is not None else "",
        "scope_path": _rel(scope_path),
        "board_path": _rel(board_path),
        "summary": {
            "passed": len(checks) - len(failures),
            "failed": len(failures),
            "total": len(checks),
        },
        "public_problem": {
            "problem_id": public_problem_id,
            "status_bucket": public_status,
            "status_label": str(problem_payload.get("status_label", "")).strip(),
            "problem_url": str(problem_payload.get("problem_url", "")).strip(),
        },
        "checks": checks,
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\\n", encoding="utf-8")

    print(f"spec_check={status}")
    if selected_path is not None:
        print(f"selected_problem_json={_rel(selected_path)}")
    print(f"scope_yaml={_rel(scope_path)}")
    print(f"board_json={_rel(board_path)}")
    print(f"spec_check_json={out_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
"""

STARTER_LEAN_STUB = """#!/usr/bin/env python3
from __future__ import annotations

import sys


def main() -> int:
    target = ""
    if len(sys.argv) > 1:
        target = sys.argv[1]
    print(f"lean_build_stub=PASS target={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

STARTER_PROBLEM857_SCOPE = """problem_id: 857
name: Erdos Problem 857 Starter Scope
status: open
notes:
  - starter scope generated by ORP pack install
"""

STARTER_LAKEFILE = """import Lake
open Lake DSL

package SunflowerLean where

@[default_target]
lean_lib SunflowerLean where
"""

STARTER_EXTERNAL_PR_BODY = """# Draft PR Body

## Summary

- TODO: summarize the proposed upstream contribution.

## Local Verification

- TODO: record the local gate outputs and any follow-up notes.

## Coordination

- TODO: note any overlap checks, issue references, or reviewer context.
"""

STARTER_ISSUE_SMASHERS_SETUP = """#!/usr/bin/env bash
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

mkdir -p \
  "$ROOT/analysis" \
  "$ROOT/repos" \
  "$ROOT/worktrees" \
  "$ROOT/scratch" \
  "$ROOT/archive"

printf 'workspace_root=%s\\n' "$ROOT"
printf 'ensured=analysis\\n'
printf 'ensured=repos\\n'
printf 'ensured=worktrees\\n'
printf 'ensured=scratch\\n'
printf 'ensured=archive\\n'
"""

PROBLEM857_PUBLIC_WORKSPACE_PATHS = [
    "analysis/problem857_counting_gateboard.json",
    "docs/PROBLEM857_COUNTING_OPS_BOARD.md",
    "scripts/problem857_ops_board.py",
    "scripts/frontier_status.py",
    "orchestrator/reduction_graph.yaml",
    "orchestrator/v2",
    "sunflower_lean",
]

PROBLEM857_PUBLIC_SYNC_IGNORES = {
    ".git",
    ".lake",
    "__pycache__",
    ".pytest_cache",
    "build",
}

PROBLEM857_PUBLIC_LEAN_REPO_MARKERS = [
    "SunflowerLean.lean",
    "SunflowerLean/Balance.lean",
    "lakefile.toml",
    "lean-toolchain",
]

PROBLEM857_PUBLIC_LEAN_COPY_PREFIX = Path("sunflower_lean")

PROBLEM857_PUBLIC_LEAN_SCOPE_FILES = [
    "SunflowerLean/Balance.lean",
    "SunflowerLean/BalanceCore.lean",
    "SunflowerLean/BalanceCasesA.lean",
    "SunflowerLean/BalanceCasesB.lean",
    "SunflowerLean/BalanceCandidatesA.lean",
    "SunflowerLean/BalanceCandidatesB.lean",
    "SunflowerLean/Container.lean",
    "SunflowerLean/LocalTuran.lean",
    "SunflowerLean/Obstruction.lean",
    "SunflowerLean/SATBridge.lean",
    "SunflowerLean/UnionBounds.lean",
]

PROBLEM857_PUBLIC_ROUTE_GROUPS = [
    {
        "route": "balance_core",
        "ticket": "P857_BALANCE_CORE",
        "leaf": "SunflowerLean.Balance",
        "files": [
            "SunflowerLean/Balance.lean",
            "SunflowerLean/BalanceCore.lean",
            "SunflowerLean/LocalTuran.lean",
            "SunflowerLean/UnionBounds.lean",
        ],
    },
    {
        "route": "balance_cases",
        "ticket": "P857_BALANCE_CASES",
        "leaf": "SunflowerLean.BalanceCases",
        "files": [
            "SunflowerLean/BalanceCasesA.lean",
            "SunflowerLean/BalanceCasesB.lean",
            "SunflowerLean/BalanceCandidatesA.lean",
            "SunflowerLean/BalanceCandidatesB.lean",
        ],
    },
    {
        "route": "support_modules",
        "ticket": "P857_SUPPORT",
        "leaf": "SunflowerLean.Support",
        "files": [
            "SunflowerLean/Container.lean",
            "SunflowerLean/Obstruction.lean",
            "SunflowerLean/SATBridge.lean",
        ],
    },
]


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


def _legacy_pack_spec(pack_id: str) -> dict[str, Any]:
    spec = LEGACY_PACK_SPECS.get(pack_id)
    if not isinstance(spec, dict):
        raise RuntimeError(f"unsupported pack for install flow: {pack_id}")
    return spec


def _pack_install_spec(pack_meta: dict[str, Any], pack_id: str) -> dict[str, Any]:
    install = pack_meta.get("install")
    if isinstance(install, dict):
        return install
    return _legacy_pack_spec(pack_id)


def _pack_templates(pack_meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = pack_meta.get("templates", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, dict):
            out[key] = value
    return out


def _normalize_install_component(
    component_key: str,
    raw_component: dict[str, Any],
    *,
    templates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    template_id = str(raw_component.get("template_id", "")).strip()
    if not template_id:
        raise RuntimeError(f"install component missing template_id: {component_key}")

    template_meta = templates.get(template_id)
    if not isinstance(template_meta, dict):
        raise RuntimeError(
            f"install component {component_key} references unknown template_id: {template_id}"
        )

    output_name = str(raw_component.get("output_name") or template_meta.get("output_hint") or "").strip()
    if not output_name:
        raise RuntimeError(
            f"install component {component_key} is missing output_name and template {template_id} has no output_hint"
        )

    description = str(raw_component.get("description") or template_meta.get("description") or "").strip()
    required_paths_raw = raw_component.get("required_paths", [])
    if required_paths_raw is None:
        required_paths: list[str] = []
    elif isinstance(required_paths_raw, list):
        required_paths = [str(path) for path in required_paths_raw]
    else:
        raise RuntimeError(f"install component required_paths must be a list: {component_key}")

    return {
        "template_id": template_id,
        "output_name": output_name,
        "description": description,
        "required_paths": required_paths,
    }


def _pack_components(pack_meta: dict[str, Any], pack_id: str) -> dict[str, dict[str, Any]]:
    install = _pack_install_spec(pack_meta, pack_id)
    components = install.get("components", {})
    if not isinstance(components, dict) or not components:
        raise RuntimeError(f"pack has no installable components: {pack_id}")

    templates = _pack_templates(pack_meta)
    out: dict[str, dict[str, Any]] = {}
    for key, value in components.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise RuntimeError(f"invalid install component entry in pack {pack_id}: {key!r}")
        out[key] = _normalize_install_component(key, value, templates=templates)
    return out


def _pack_default_includes(pack_meta: dict[str, Any], pack_id: str) -> list[str]:
    install = _pack_install_spec(pack_meta, pack_id)
    raw = install.get("default_includes", [])
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if isinstance(x, str)]


def _pack_report_name(pack_meta: dict[str, Any], pack_id: str) -> str:
    install = _pack_install_spec(pack_meta, pack_id)
    raw = install.get("report_name")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return f"orp.{pack_id}.pack-install-report.md"


def _validate_var(raw: str) -> str:
    if "=" not in raw:
        raise RuntimeError(f"invalid --var, expected KEY=VALUE: {raw}")
    key, _value = raw.split("=", 1)
    if not key or not all(c.isupper() or c.isdigit() or c == "_" for c in key):
        raise RuntimeError(f"invalid variable key: {key}")
    return raw


def _write_text(path: Path, text: str, *, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _write_json(path: Path, payload: dict[str, Any], *, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True


def _vars_defaults(pack_meta: dict[str, Any]) -> dict[str, str]:
    raw = pack_meta.get("variables", {})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, meta in raw.items():
        if not isinstance(key, str) or not isinstance(meta, dict):
            continue
        default = meta.get("default")
        if isinstance(default, str):
            out[key] = default
    return out


def _vars_map(pack_meta: dict[str, Any], extra_vars: list[str]) -> dict[str, str]:
    out = _vars_defaults(pack_meta)
    for raw in extra_vars:
        validated = _validate_var(raw)
        key, value = validated.split("=", 1)
        out[key] = value
    return out


def _problem857_source_mode(vars_map: dict[str, str]) -> str:
    mode = vars_map.get("PROBLEM857_SOURCE_MODE", "starter").strip().lower()
    if mode not in {"starter", "public_repo"}:
        raise RuntimeError(f"unsupported PROBLEM857_SOURCE_MODE: {mode}")
    return mode


def _issue_smashers_workspace_readme(
    *,
    workspace_root_rel: str,
    repos_rel: str,
    worktrees_rel: str,
    scratch_rel: str,
    archive_rel: str,
    watchlist_rel: str,
    status_rel: str,
    pr_body_rel: str,
) -> str:
    return (
        "# Issue Smashers Workspace\n\n"
        "This directory is the operator-facing workspace scaffold installed by the ORP "
        "`issue-smashers` pack.\n\n"
        "## Layout\n\n"
        f"- `{repos_rel}` - base clones for target projects\n"
        f"- `{worktrees_rel}` - one active worktree per issue lane\n"
        f"- `{scratch_rel}` - disposable notes and experiments\n"
        f"- `{archive_rel}` - optional non-canonical archive space\n"
        f"- `{watchlist_rel}` - machine-readable watchlist\n"
        f"- `{status_rel}` - human-readable lane/status board\n"
        f"- `{pr_body_rel}` - default public PR draft body\n\n"
        "## Usage\n\n"
        "1. Keep ORP outside this workspace as the protocol/runtime.\n"
        "2. Put base clones under `repos/`.\n"
        "3. Put one active lane per issue under `worktrees/`.\n"
        "4. Use the rendered ORP configs at the install target root to run governance.\n"
        "5. Treat this workspace as process-only; it coordinates contribution work but is not evidence.\n\n"
        "## First step\n\n"
        "Run `bash setup-issue-smashers.sh` inside this directory if you want to re-ensure the "
        "workspace folders exist.\n"
    )


def _issue_smashers_workspace_rules(
    *,
    workspace_root_rel: str,
    repos_rel: str,
    worktrees_rel: str,
    scratch_rel: str,
    archive_rel: str,
) -> str:
    return (
        "# Issue Smashers Workspace Rules\n\n"
        f"- workspace root: `{workspace_root_rel}`\n"
        f"- base clones live under `{repos_rel}`\n"
        f"- active issue work lives under `{worktrees_rel}`\n"
        f"- scratch space lives under `{scratch_rel}` and is disposable\n"
        f"- archive space lives under `{archive_rel}` and is optional\n\n"
        "## Rules\n\n"
        "1. `issue-smashers/` is a plain directory, not the ORP source repo.\n"
        "2. Base clones live under `repos/`.\n"
        "3. Active issue work lives under `worktrees/`.\n"
        "4. One worktree per issue lane.\n"
        "5. `scratch/` is disposable.\n"
        "6. `archive/` is non-canonical and optional.\n"
        "7. `origin` should point at the operator fork when host repo policy allows it.\n"
        "8. `upstream` should point at the canonical target repo.\n"
        "9. ORP stays outside the workspace as the protocol/runtime.\n"
    )


def _issue_smashers_status_markdown(
    *,
    watchlist_rel: str,
    pr_body_rel: str,
) -> str:
    return (
        "# Issue Smashers Status\n\n"
        "- active_lanes: `0`\n"
        f"- watchlist_json: `{watchlist_rel}`\n"
        f"- default_pr_body: `{pr_body_rel}`\n\n"
        "## Queue\n\n"
        "- none yet\n"
    )


def _issue_smashers_watchlist_payload(*, workspace_root_rel: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_at_utc": _now_utc(),
        "workspace_root": workspace_root_rel,
        "lanes": [],
        "notes": [
            "Issue Smashers watchlist is process-only.",
            "Keep one active worktree per issue lane.",
        ],
    }


def _run_checked(cmd: list[str], *, cwd: Path | None = None) -> None:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "command failed").strip()
        raise RuntimeError(f"{' '.join(cmd)}: {msg}")


def _copy_repo_path(src_root: Path, dst_root: Path, rel: str, *, overwrite: bool) -> list[str]:
    src = src_root / rel
    if not src.exists():
        raise RuntimeError(f"missing public Problem 857 sync path in source repo: {rel}")

    created: list[str] = []
    dst = dst_root / rel

    if src.is_dir():
        for child in sorted(src.rglob("*")):
            parts = set(child.relative_to(src).parts)
            if parts & PROBLEM857_PUBLIC_SYNC_IGNORES:
                continue
            if child.is_dir():
                continue
            rel_child = child.relative_to(src_root)
            target = dst_root / rel_child
            if target.exists() and not overwrite:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, target)
            created.append(str(rel_child))
        return created

    if dst.exists() and not overwrite:
        return created
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    created.append(rel)
    return created


def _copy_repo_tree(
    src_root: Path,
    target_repo_root: Path,
    dst_prefix: Path,
    *,
    overwrite: bool,
) -> list[str]:
    created: list[str] = []
    for child in sorted(src_root.rglob("*")):
        rel_child = child.relative_to(src_root)
        parts = set(rel_child.parts)
        if parts & PROBLEM857_PUBLIC_SYNC_IGNORES:
            continue
        if child.is_dir():
            continue
        out_rel = dst_prefix / rel_child
        target = target_repo_root / out_rel
        if target.exists() and not overwrite:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(child, target)
        created.append(out_rel.as_posix())
    return created


def _has_problem857_public_workspace_shape(repo_path: Path) -> bool:
    return (repo_path / "analysis/problem857_counting_gateboard.json").exists()


def _has_problem857_public_lean_shape(repo_path: Path) -> bool:
    return all((repo_path / rel).exists() for rel in PROBLEM857_PUBLIC_LEAN_REPO_MARKERS)


def _problem857_public_sync_note(source: str, ref: str) -> str:
    clean_ref = ref.strip() or "HEAD"
    return (
        "ORP-generated public bridge over synced sunflower-lean repository "
        f"({source}@{clean_ref}); board routes summarize public module inventory, not proof completion."
    )


def _problem857_public_scope_text(source_repo_url: str, ref: str, repo_path: Path) -> str:
    lean_files = [
        f"sunflower_lean/{rel}"
        for rel in PROBLEM857_PUBLIC_LEAN_SCOPE_FILES
        if (repo_path / rel).exists()
    ]
    if not lean_files:
        lean_files = ["sunflower_lean/SunflowerLean/Balance.lean"]
    lines = [
        "problem_id: 857",
        'display_name: "Sunflower Problem 857 Public Lean Scope"',
        "source_mode: public_repo",
        f"public_repo_url: {json.dumps(source_repo_url)}",
        f"public_repo_ref: {json.dumps(ref.strip() or 'main')}",
        "lean_root: sunflower_lean",
        "lean_entrypoint: sunflower_lean/SunflowerLean/Balance.lean",
        "north_star_lane: balance_core",
        "reduction_route: balance_core",
        "lean_files:",
    ]
    for rel in lean_files:
        lines.append(f"  - {rel}")
    lines.extend(
        [
            "notes:",
            '  - "ORP-generated scope over the synced public sunflower-lean repo."',
            '  - "These files are public evidence inputs; ORP board/frontier files are derived process views."',
        ]
    )
    return "\n".join(lines) + "\n"


def _problem857_public_reduction_graph_text(source_repo_url: str, ref: str, repo_path: Path) -> str:
    lines = [
        "problem_id: 857",
        "source_mode: public_repo",
        f"public_repo_url: {json.dumps(source_repo_url)}",
        f"public_repo_ref: {json.dumps(ref.strip() or 'main')}",
        "routes:",
    ]
    for group in PROBLEM857_PUBLIC_ROUTE_GROUPS:
        files = [rel for rel in group["files"] if (repo_path / rel).exists()]
        lines.append(f"  {group['route']}:")
        lines.append(f"    ticket: {group['ticket']}")
        lines.append(f"    leaf: {group['leaf']}")
        lines.append("    lean_files:")
        for rel in files:
            lines.append(f"      - sunflower_lean/{rel}")
    return "\n".join(lines) + "\n"


def _problem857_public_board_payload(source_repo_url: str, ref: str, repo_path: Path) -> dict[str, Any]:
    route_status: list[dict[str, Any]] = []
    tickets: list[dict[str, Any]] = []
    for group in PROBLEM857_PUBLIC_ROUTE_GROUPS:
        existing = [rel for rel in group["files"] if (repo_path / rel).exists()]
        total = len(group["files"])
        done = len(existing)
        route_status.append(
            {
                "route": group["route"],
                "loose_done": done,
                "loose_total": total,
                "strict_done": done,
                "strict_total": total,
            }
        )
        tickets.append(
            {
                "ticket": group["ticket"],
                "leaf": group["leaf"],
                "leaf_strict": "synced" if done == total else "partial",
                "gates_done": done,
                "gates_total": total,
                "atoms_done": done,
                "atoms_total": total,
            }
        )
    payload = {
        "board_id": "problem857_public_repo_board",
        "problem_id": 857,
        "updated_utc": _now_utc(),
        "starter_scaffold": False,
        "starter_note": _problem857_public_sync_note(source_repo_url, ref),
        "public_repo": {
            "url": source_repo_url,
            "ref": ref.strip() or "main",
            "sync_root": "sunflower_lean",
            "entrypoint": "sunflower_lean/SunflowerLean/Balance.lean",
        },
        "route_status": route_status,
        "tickets": tickets,
        "atoms": {
            "A_public_balance_build": {
                "status": "ready",
                "ticket_id": "P857_BALANCE_CORE",
                "gate_id": "lean_build_balance",
                "deps": ["spec_faithfulness"],
            }
        },
        "ready_atoms": 1,
        "no_go_active": [],
    }
    return payload


def _problem857_public_board_markdown(board: dict[str, Any]) -> str:
    lines = [
        "# Problem 857 Ops Board",
        "",
        f"- updated_utc: `{board.get('updated_utc', '')}`",
        f"- ready_atoms: `{int(board.get('ready_atoms', 0) or 0)}`",
    ]
    public_repo = board.get("public_repo", {})
    if isinstance(public_repo, dict):
        lines.append(f"- public_repo_url: `{public_repo.get('url', '')}`")
        lines.append(f"- public_repo_ref: `{public_repo.get('ref', '')}`")
    lines.extend(["", "## Routes", ""])
    for row in board.get("route_status", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "- route={route} loose={ld}/{lt} strict={sd}/{st}".format(
                route=row.get("route", ""),
                ld=row.get("loose_done", 0),
                lt=row.get("loose_total", 0),
                sd=row.get("strict_done", 0),
                st=row.get("strict_total", 0),
            )
        )
    lines.extend(
        [
            "",
            "## Note",
            "",
            "- This board is ORP-derived from the synced public sunflower-lean repo.",
            "- It tracks public module inventory for the Problem 857 workflow, not proof completion.",
            "",
        ]
    )
    return "\n".join(lines)


def _sync_problem857_public_lean_repo(
    *,
    target_repo_root: Path,
    repo_path: Path,
    source: str,
    ref: str,
    overwrite: bool,
) -> list[str]:
    created = _copy_repo_tree(
        repo_path,
        target_repo_root,
        PROBLEM857_PUBLIC_LEAN_COPY_PREFIX,
        overwrite=overwrite,
    )
    board_payload = _problem857_public_board_payload(source, ref, repo_path)
    board_path = target_repo_root / "analysis/problem857_counting_gateboard.json"
    if _write_json(board_path, board_payload, overwrite=overwrite):
        created.append(str(board_path.relative_to(target_repo_root)))
    board_md_path = target_repo_root / "docs/PROBLEM857_COUNTING_OPS_BOARD.md"
    if _write_text(board_md_path, _problem857_public_board_markdown(board_payload), overwrite=overwrite):
        created.append(str(board_md_path.relative_to(target_repo_root)))
    reduction_graph_path = target_repo_root / "orchestrator/reduction_graph.yaml"
    if _write_text(
        reduction_graph_path,
        _problem857_public_reduction_graph_text(source, ref, repo_path),
        overwrite=overwrite,
    ):
        created.append(str(reduction_graph_path.relative_to(target_repo_root)))
    scope_path = target_repo_root / "orchestrator/v2/scopes/problem_857.yaml"
    if _write_text(scope_path, _problem857_public_scope_text(source, ref, repo_path), overwrite=overwrite):
        created.append(str(scope_path.relative_to(target_repo_root)))
    return sorted(set(created))


def _sync_problem857_public_repo(
    *,
    target_repo_root: Path,
    source: str,
    ref: str,
    overwrite: bool,
) -> list[str]:
    created: list[str] = []
    with tempfile.TemporaryDirectory(prefix="orp-problem857-public-") as td:
        repo_path = Path(td) / "repo"
        _run_checked(["git", "clone", source, str(repo_path)])
        if ref.strip():
            _run_checked(["git", "-C", str(repo_path), "checkout", ref.strip()])
        if _has_problem857_public_workspace_shape(repo_path):
            for rel in PROBLEM857_PUBLIC_WORKSPACE_PATHS:
                created.extend(_copy_repo_path(repo_path, target_repo_root, rel, overwrite=overwrite))
        elif _has_problem857_public_lean_shape(repo_path):
            created.extend(
                _sync_problem857_public_lean_repo(
                    target_repo_root=target_repo_root,
                    repo_path=repo_path,
                    source=source,
                    ref=ref,
                    overwrite=overwrite,
                )
            )
        else:
            raise RuntimeError(
                "public Problem 857 repo did not match a supported shape; expected either "
                "a workspace repo with analysis/docs/scripts/orchestrator paths or a public "
                "sunflower-lean repo with SunflowerLean/Balance.lean and lakefile.toml"
            )
    return sorted(set(created))


def _install_starter_adapters(
    *,
    pack_id: str,
    pack_meta: dict[str, Any],
    target_repo_root: Path,
    includes: list[str],
    extra_vars: list[str],
    overwrite: bool,
) -> list[str]:
    created: list[str] = []
    vars_map = _vars_map(pack_meta, extra_vars)
    problem857_source_mode = _problem857_source_mode(vars_map)
    public_repo_requested = "problem857" in includes and problem857_source_mode == "public_repo"

    if pack_id == "external-pr-governance":
        if "governance" not in includes:
            return created
        draft_body = target_repo_root / "analysis/PR_DRAFT_BODY.md"
        if _write_text(draft_body, STARTER_EXTERNAL_PR_BODY, overwrite=overwrite):
            created.append(str(draft_body.relative_to(target_repo_root)))
        return created

    if pack_id == "issue-smashers":
        workspace_root_rel = vars_map.get("ISSUE_SMASHERS_ROOT", "issue-smashers").strip() or "issue-smashers"
        repos_rel = vars_map.get("ISSUE_SMASHERS_REPOS_DIR", f"{workspace_root_rel}/repos").strip() or f"{workspace_root_rel}/repos"
        worktrees_rel = vars_map.get(
            "ISSUE_SMASHERS_WORKTREES_DIR", f"{workspace_root_rel}/worktrees"
        ).strip() or f"{workspace_root_rel}/worktrees"
        scratch_rel = vars_map.get("ISSUE_SMASHERS_SCRATCH_DIR", f"{workspace_root_rel}/scratch").strip() or f"{workspace_root_rel}/scratch"
        archive_rel = vars_map.get("ISSUE_SMASHERS_ARCHIVE_DIR", f"{workspace_root_rel}/archive").strip() or f"{workspace_root_rel}/archive"
        watchlist_rel = vars_map.get(
            "WATCHLIST_FILE", f"{workspace_root_rel}/analysis/ISSUE_SMASHERS_WATCHLIST.json"
        ).strip() or f"{workspace_root_rel}/analysis/ISSUE_SMASHERS_WATCHLIST.json"
        status_rel = vars_map.get(
            "STATUS_FILE", f"{workspace_root_rel}/analysis/ISSUE_SMASHERS_STATUS.md"
        ).strip() or f"{workspace_root_rel}/analysis/ISSUE_SMASHERS_STATUS.md"
        rules_rel = vars_map.get("WORKSPACE_RULES_FILE", f"{workspace_root_rel}/WORKSPACE_RULES.md").strip() or f"{workspace_root_rel}/WORKSPACE_RULES.md"
        pr_body_rel = vars_map.get(
            "DEFAULT_PR_BODY_FILE", f"{workspace_root_rel}/analysis/PR_DRAFT_BODY.md"
        ).strip() or f"{workspace_root_rel}/analysis/PR_DRAFT_BODY.md"

        workspace_files: list[tuple[Path, str]] = [
            (
                target_repo_root / workspace_root_rel / "README.md",
                _issue_smashers_workspace_readme(
                    workspace_root_rel=workspace_root_rel,
                    repos_rel=repos_rel,
                    worktrees_rel=worktrees_rel,
                    scratch_rel=scratch_rel,
                    archive_rel=archive_rel,
                    watchlist_rel=watchlist_rel,
                    status_rel=status_rel,
                    pr_body_rel=pr_body_rel,
                ),
            ),
            (
                target_repo_root / rules_rel,
                _issue_smashers_workspace_rules(
                    workspace_root_rel=workspace_root_rel,
                    repos_rel=repos_rel,
                    worktrees_rel=worktrees_rel,
                    scratch_rel=scratch_rel,
                    archive_rel=archive_rel,
                ),
            ),
            (target_repo_root / workspace_root_rel / "setup-issue-smashers.sh", STARTER_ISSUE_SMASHERS_SETUP),
            (target_repo_root / status_rel, _issue_smashers_status_markdown(watchlist_rel=watchlist_rel, pr_body_rel=pr_body_rel)),
            (target_repo_root / pr_body_rel, STARTER_EXTERNAL_PR_BODY),
        ]
        for path, text in workspace_files:
            if _write_text(path, text, overwrite=overwrite):
                created.append(str(path.relative_to(target_repo_root)))

        watchlist_path = target_repo_root / watchlist_rel
        if _write_json(
            watchlist_path,
            _issue_smashers_watchlist_payload(workspace_root_rel=workspace_root_rel),
            overwrite=overwrite,
        ):
            created.append(str(watchlist_path.relative_to(target_repo_root)))

        for rel in [repos_rel, worktrees_rel, scratch_rel, archive_rel]:
            placeholder = target_repo_root / rel / ".gitkeep"
            if _write_text(placeholder, "", overwrite=overwrite):
                created.append(str(placeholder.relative_to(target_repo_root)))
        return sorted(set(created))

    if public_repo_requested:
        source = vars_map.get("PROBLEM857_PUBLIC_REPO_URL", "").strip()
        ref = vars_map.get("PROBLEM857_PUBLIC_REPO_REF", "").strip()
        if not source:
            raise RuntimeError("PROBLEM857_PUBLIC_REPO_URL cannot be empty in public_repo mode")
        created.extend(
            _sync_problem857_public_repo(
                target_repo_root=target_repo_root,
                source=source,
                ref=ref,
                overwrite=overwrite,
            )
        )

    needs_atomic = "live_compare" in includes or "problem857" in includes
    if not needs_atomic:
        return sorted(set(created))

    # Shared starter runtime and wrappers for 857/20/367.
    files: list[tuple[Path, str]] = [(target_repo_root / "scripts/orp_atomic_board_runtime.py", STARTER_RUNTIME)]
    if "live_compare" in includes or "problem857" in includes:
        files.extend(
            [
                (target_repo_root / "scripts/frontier_status.py", STARTER_FRONTIER),
                (target_repo_root / "scripts/problem857_ops_board.py", STARTER_WRAPPER.replace("{PROBLEM}", "857")),
            ]
        )
    if "live_compare" in includes:
        files.extend(
            [
                (target_repo_root / "scripts/problem20_ops_board.py", STARTER_WRAPPER.replace("{PROBLEM}", "20")),
                (target_repo_root / "scripts/problem367_ops_board.py", STARTER_WRAPPER.replace("{PROBLEM}", "367")),
            ]
        )
    for path, text in files:
        if _write_text(path, text, overwrite=overwrite):
            created.append(str(path.relative_to(target_repo_root)))

    # Seed board JSON + markdown so live_compare is runnable immediately.
    stamped = _now_utc()
    for problem, seed in BOARD_SEEDS.items():
        if problem == 857 and public_repo_requested:
            continue
        if problem in {20, 367} and "live_compare" not in includes:
            continue
        payload = json.loads(json.dumps(seed))
        payload["updated_utc"] = stamped
        board_path = target_repo_root / BOARD_PATHS[problem]
        if _write_json(board_path, payload, overwrite=overwrite):
            created.append(str(board_path.relative_to(target_repo_root)))

        md_path = target_repo_root / BOARD_MD_PATHS[problem]
        md = (
            f"# Problem {problem} Ops Board\\n\\n"
            f"- updated_utc: `{stamped}`\\n"
            f"- note: starter board generated by ORP pack install\\n"
        )
        if _write_text(md_path, md, overwrite=overwrite):
            created.append(str(md_path.relative_to(target_repo_root)))

    if "problem857" in includes and problem857_source_mode != "public_repo":
        extra_files: list[tuple[Path, str]] = [
            (target_repo_root / "orchestrator/problem857_public_spec_check.py", STARTER_SPEC_CHECK),
            (target_repo_root / "scripts/orp-lean-build-stub.py", STARTER_LEAN_STUB),
            (target_repo_root / "orchestrator/v2/scopes/problem_857.yaml", STARTER_PROBLEM857_SCOPE),
            (target_repo_root / "sunflower_lean/lakefile.lean", STARTER_LAKEFILE),
        ]
        for path, text in extra_files:
            if _write_text(path, text, overwrite=overwrite):
                created.append(str(path.relative_to(target_repo_root)))

    if "problem857" in includes and problem857_source_mode == "public_repo":
        checker_path = target_repo_root / "orchestrator/problem857_public_spec_check.py"
        if _write_text(checker_path, STARTER_SPEC_CHECK, overwrite=overwrite):
            created.append(str(checker_path.relative_to(target_repo_root)))

    return sorted(set(created))


def _render_component(
    *,
    orp_repo_root: Path,
    pack_root: Path,
    target_repo_root: Path,
    components: dict[str, dict[str, Any]],
    component_key: str,
    extra_vars: list[str],
    internal_vars: list[str],
    template_id_override: str = "",
) -> Path:
    comp = components[component_key]
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
        template_id_override or str(comp["template_id"]),
        "--var",
        f"TARGET_REPO_ROOT={target_repo_root}",
        "--var",
        f"ORP_REPO_ROOT={orp_repo_root}",
        "--out",
        str(out_path),
    ]

    # Internal vars first, user vars last so users can override defaults.
    for raw in internal_vars:
        cmd.extend(["--var", _validate_var(raw)])
    for raw in extra_vars:
        cmd.extend(["--var", _validate_var(raw)])

    proc = subprocess.run(cmd, cwd=str(orp_repo_root), capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        msg = stderr or stdout or "unknown renderer failure"
        raise RuntimeError(f"render failed for {component_key}: {msg}")
    return out_path


def _check_dependencies(
    target_repo_root: Path,
    components: dict[str, dict[str, Any]],
    component_key: str,
) -> tuple[list[str], list[str]]:
    comp = components[component_key]
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
    components: dict[str, dict[str, Any]],
    rendered: dict[str, Path],
    dep_summary: dict[str, dict[str, Any]],
    bootstrap_enabled: bool,
    bootstrap_created: list[str],
) -> None:
    lines: list[str] = []
    lines.append("# ORP Pack Install Report")
    lines.append("")
    lines.append(f"- generated_at_utc: `{generated_at_utc}`")
    lines.append(f"- pack_id: `{pack_id}`")
    lines.append(f"- pack_version: `{pack_version}`")
    lines.append(f"- target_repo_root: `{target_repo_root}`")
    lines.append(f"- bootstrap_enabled: `{bootstrap_enabled}`")
    lines.append("")
    lines.append("## Rendered Configs")
    lines.append("")
    lines.append("| Component | Template | Output |")
    lines.append("|---|---|---|")
    for key, out_path in rendered.items():
        template_id = str(components[key]["template_id"])
        lines.append(f"| `{key}` | `{template_id}` | `{out_path}` |")

    lines.append("")
    lines.append("## Starter Bootstrap")
    lines.append("")
    lines.append(f"- created_files: `{len(bootstrap_created)}`")
    if bootstrap_created:
        for rel in bootstrap_created:
            lines.append(f"- `{rel}`")

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
    if pack_id == "erdos-open-problems" and "problem857" in rendered:
        lines.append(
            "- Sync public Problem 857 data first with `orp erdos sync --problem-id 857 --out-problem-dir analysis/erdos_problems/selected`."
        )
        lines.append(
            "- For a real host workspace instead of starter scaffolding, install with `--var PROBLEM857_SOURCE_MODE=public_repo` (and optionally `--var PROBLEM857_PUBLIC_REPO_URL=<git-url>`)."
        )
    if pack_id == "external-pr-governance":
        lines.append(
            "- Replace the placeholder commands and repo metadata in the rendered configs before treating any governance run as meaningful."
        )
        if "governance" in rendered:
            lines.append(
                "- Run the lifecycle in order: `external_watch_select`, `external_pre_open`, `external_local_readiness`, `external_draft_transition`, then `external_draft_lifecycle`."
            )
        if "feedback_hardening" in rendered:
            lines.append(
                "- Use `external_feedback_hardening` when maintainer feedback reveals a missed check that should become a reusable guard."
            )
    if pack_id == "issue-smashers":
        lines.append(
            "- Treat `issue-smashers/` as a plain workspace scaffold, not as a replacement for ORP core or as a monorepo of cloned projects."
        )
        lines.append(
            "- Replace the placeholder commands in the rendered configs before treating any governance run as meaningful."
        )
        lines.append(
            "- Use `issue_smashers_full_flow` for the main lifecycle and `issue_smashers_feedback_hardening` when maintainer feedback should become a reusable guard."
        )
        lines.append(
            "- Keep base clones in `issue-smashers/repos/` and one active worktree per issue lane in `issue-smashers/worktrees/`."
        )
    lines.append("- Run selected ORP profiles with `orp --config <rendered-config> gate run --profile <profile>`.")
    lines.append("- If developing ORP locally, the equivalent command is `./scripts/orp --config <rendered-config> gate run --profile <profile>`.")
    lines.append("- Emit process packets with `orp --config <rendered-config> packet emit --profile <profile> --run-id <run_id>`.")
    lines.append("- Generate one-page run digest with `orp report summary --run-id <run_id>`.")
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
        "--pack-path",
        default="",
        help="Explicit pack root path containing pack.yml (overrides --pack-id lookup)",
    )
    p.add_argument(
        "--target-repo-root",
        default=".",
        help="Target repository root where rendered ORP configs are written (default: current directory)",
    )
    p.add_argument(
        "--include",
        action="append",
        default=[],
        help=(
            "Component to install (repeatable). "
            "Valid values depend on the selected pack. "
            "Examples: erdos-open-problems -> catalog/live_compare/problem857/governance; "
            "external-pr-governance -> governance/feedback_hardening; "
            "issue-smashers -> workspace/feedback_hardening."
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
        help="Install report output path (default depends on selected pack)",
    )
    p.add_argument(
        "--strict-deps",
        action="store_true",
        help="Exit non-zero if dependency audit finds missing paths.",
    )
    p.add_argument(
        "--no-bootstrap",
        dest="bootstrap",
        action="store_false",
        help="Disable starter adapter scaffolding",
    )
    p.add_argument(
        "--overwrite-bootstrap",
        action="store_true",
        help="Allow bootstrap to overwrite existing scaffolded files",
    )
    p.set_defaults(bootstrap=True)
    return p


def main() -> int:
    args = _build_parser().parse_args()

    if args.orp_repo_root:
        orp_repo_root = Path(args.orp_repo_root).resolve()
    else:
        orp_repo_root = Path(__file__).resolve().parent.parent
    target_repo_root = Path(args.target_repo_root).resolve()
    target_repo_root.mkdir(parents=True, exist_ok=True)

    if args.pack_path.strip():
        pack_root = Path(args.pack_path).resolve()
    else:
        pack_root = orp_repo_root / "packs" / args.pack_id
    pack_yml = pack_root / "pack.yml"
    if not pack_yml.exists():
        print(f"error: pack not found: {pack_root}", file=sys.stderr)
        return 2

    pack_meta = _load_yaml(pack_yml)
    pack_id = str(pack_meta.get("pack_id", args.pack_id))
    pack_version = str(pack_meta.get("version", "unknown"))
    generated_at_utc = _now_utc()
    components = _pack_components(pack_meta, pack_id)
    effective_vars = _vars_map(pack_meta, list(args.var or []))
    problem857_source_mode = _problem857_source_mode(effective_vars)

    includes = list(args.include or [])
    if not includes:
        includes = _pack_default_includes(pack_meta, pack_id)
    if not includes:
        includes = sorted(components.keys())

    unknown = [key for key in includes if key not in components]
    if unknown:
        valid = ", ".join(sorted(components.keys()))
        print(
            f"error: unknown component(s) for pack {pack_id}: {', '.join(unknown)}; valid: {valid}",
            file=sys.stderr,
        )
        return 2

    bootstrap_created: list[str] = []
    if args.bootstrap:
        bootstrap_created = _install_starter_adapters(
            pack_id=pack_id,
            pack_meta=pack_meta,
            target_repo_root=target_repo_root,
            includes=includes,
            extra_vars=list(args.var or []),
            overwrite=bool(args.overwrite_bootstrap),
        )

    rendered: dict[str, Path] = {}
    for key in includes:
        internal_vars: list[str] = []
        template_id_override = ""
        if key == "problem857":
            if problem857_source_mode == "public_repo":
                template_id_override = "sunflower_problem857_discovery_public_repo"
            elif args.bootstrap:
                internal_vars.append(
                    "PROBLEM857_LEAN_BUILD_COMMAND=python3 ../scripts/orp-lean-build-stub.py SunflowerLean.Balance"
                )
        out_path = _render_component(
            orp_repo_root=orp_repo_root,
            pack_root=pack_root,
            target_repo_root=target_repo_root,
            components=components,
            component_key=key,
            extra_vars=list(args.var or []),
            internal_vars=internal_vars,
            template_id_override=template_id_override,
        )
        rendered[key] = out_path

    dep_summary: dict[str, dict[str, Any]] = {}
    total_missing = 0
    for key in includes:
        present_paths, missing_paths = _check_dependencies(target_repo_root, components, key)
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
        report_name = _pack_report_name(pack_meta, pack_id)
        report_path = (target_repo_root / report_name).resolve()

    _write_report(
        report_path=report_path,
        generated_at_utc=generated_at_utc,
        pack_id=pack_id,
        pack_version=pack_version,
        target_repo_root=target_repo_root,
        components=components,
        rendered=rendered,
        dep_summary=dep_summary,
        bootstrap_enabled=bool(args.bootstrap),
        bootstrap_created=bootstrap_created,
    )

    print(f"pack_id={pack_id}")
    print(f"pack_version={pack_version}")
    print(f"pack_root={pack_root}")
    print(f"target_repo_root={target_repo_root}")
    print(f"included_components={','.join(includes)}")
    print(f"bootstrap.enabled={bool(args.bootstrap)}")
    print(f"bootstrap.created={len(bootstrap_created)}")
    if "problem857" in includes:
        print(f"problem857.source_mode={problem857_source_mode}")
        if problem857_source_mode == "public_repo":
            print(f"problem857.public_repo_url={effective_vars.get('PROBLEM857_PUBLIC_REPO_URL', '')}")
            print(f"problem857.public_repo_ref={effective_vars.get('PROBLEM857_PUBLIC_REPO_REF', '')}")
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
