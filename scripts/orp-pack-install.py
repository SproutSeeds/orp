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
import subprocess
import sys
from typing import Any

import yaml


PACK_SPECS: dict[str, dict[str, Any]] = {
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
                    "orchestrator/spec_check.py",
                    "scripts/problem857_ops_board.py",
                    "scripts/frontier_status.py",
                    "scripts/orp-lean-build-stub.py",
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
        if args.problem == 367:
            no_go = board.get("no_go_active", [])
            if isinstance(no_go, list):
                print("no_go_active=" + ",".join(str(x) for x in no_go))
            else:
                print("no_go_active=")
        for atom_id in _ready_atom_ids(board):
            print(f"{atom_id} ticket=starter gate=ready deps=root")
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate public Problem 857 scope consistency against synced Erdos data"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--problem-id", type=int, default=PROBLEM_ID)
    parser.add_argument(
        "--selected-problem",
        action="append",
        default=[],
        help="Selected problem JSON path (repeatable; first existing path wins).",
    )
    parser.add_argument("--scope", default=DEFAULT_SCOPE, help="Scope YAML path.")
    parser.add_argument("--board", default=DEFAULT_BOARD, help="Board JSON path.")
    args = parser.parse_args()

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

    public_problem_id = int(problem_payload.get("problem_id", 0) or 0)
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

    scope_problem_id = int(scope_payload.get("problem_id", 0) or 0)
    _add_check(
        checks,
        check_id="scope_problem_id_matches",
        ok=scope_problem_id == int(args.problem_id),
        detail="scope problem id matches workflow problem id",
        path=scope_path,
        expected=int(args.problem_id),
        actual=scope_problem_id,
    )
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

    board_problem_id = int(board_payload.get("problem_id", 0) or 0)
    _add_check(
        checks,
        check_id="board_problem_id_matches",
        ok=board_problem_id == int(args.problem_id),
        detail="starter board problem id matches workflow problem id",
        path=board_path,
        expected=int(args.problem_id),
        actual=board_problem_id,
    )
    _add_check(
        checks,
        check_id="board_marked_starter_scaffold",
        ok=bool(board_payload.get("starter_scaffold", False)),
        detail="starter board explicitly marks itself as starter scaffolding",
        path=board_path,
        expected=True,
        actual=bool(board_payload.get("starter_scaffold", False)),
    )
    route_status = board_payload.get("route_status", [])
    _add_check(
        checks,
        check_id="board_route_status_present",
        ok=isinstance(route_status, list) and len(route_status) > 0,
        detail="starter board includes route status rows",
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
        "checked_at_utc": _now_utc(),
        "note": (
            "Validates that the synced public Problem 857 payload, installed scope, "
            "and starter board agree on the target problem."
        ),
        "starter_scaffold": True,
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


def _pack_spec(pack_id: str) -> dict[str, Any]:
    spec = PACK_SPECS.get(pack_id)
    if not isinstance(spec, dict):
        raise RuntimeError(f"unsupported pack for install flow: {pack_id}")
    return spec


def _pack_components(pack_id: str) -> dict[str, dict[str, Any]]:
    components = _pack_spec(pack_id).get("components", {})
    if not isinstance(components, dict) or not components:
        raise RuntimeError(f"pack has no installable components: {pack_id}")
    return components


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


def _install_starter_adapters(
    *,
    pack_id: str,
    target_repo_root: Path,
    includes: list[str],
    overwrite: bool,
) -> list[str]:
    created: list[str] = []

    if pack_id == "external-pr-governance":
        if "governance" not in includes:
            return created
        draft_body = target_repo_root / "analysis/PR_DRAFT_BODY.md"
        if _write_text(draft_body, STARTER_EXTERNAL_PR_BODY, overwrite=overwrite):
            created.append(str(draft_body.relative_to(target_repo_root)))
        return created

    needs_atomic = any(x in includes for x in ["live_compare", "problem857"])
    if not needs_atomic:
        return created

    # Shared starter runtime and wrappers for 857/20/367.
    files: list[tuple[Path, str]] = [
        (target_repo_root / "scripts/orp_atomic_board_runtime.py", STARTER_RUNTIME),
        (target_repo_root / "scripts/frontier_status.py", STARTER_FRONTIER),
        (target_repo_root / "scripts/problem857_ops_board.py", STARTER_WRAPPER.replace("{PROBLEM}", "857")),
        (target_repo_root / "scripts/problem20_ops_board.py", STARTER_WRAPPER.replace("{PROBLEM}", "20")),
        (target_repo_root / "scripts/problem367_ops_board.py", STARTER_WRAPPER.replace("{PROBLEM}", "367")),
    ]
    for path, text in files:
        if _write_text(path, text, overwrite=overwrite):
            created.append(str(path.relative_to(target_repo_root)))

    # Seed board JSON + markdown so live_compare is runnable immediately.
    stamped = _now_utc()
    for problem, seed in BOARD_SEEDS.items():
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

    if "problem857" in includes:
        extra_files: list[tuple[Path, str]] = [
            (target_repo_root / "orchestrator/spec_check.py", STARTER_SPEC_CHECK),
            (target_repo_root / "scripts/orp-lean-build-stub.py", STARTER_LEAN_STUB),
            (target_repo_root / "orchestrator/v2/scopes/problem_857.yaml", STARTER_PROBLEM857_SCOPE),
            (target_repo_root / "sunflower_lean/lakefile.lean", STARTER_LAKEFILE),
        ]
        for path, text in extra_files:
            if _write_text(path, text, overwrite=overwrite):
                created.append(str(path.relative_to(target_repo_root)))

    return created


def _render_component(
    *,
    orp_repo_root: Path,
    pack_root: Path,
    target_repo_root: Path,
    components: dict[str, dict[str, Any]],
    component_key: str,
    extra_vars: list[str],
    internal_vars: list[str],
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
        str(comp["template_id"]),
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
            "external-pr-governance -> governance/feedback_hardening."
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
    components = _pack_components(pack_id)

    includes = list(args.include or [])
    if not includes:
        default_includes = _pack_spec(pack_id).get("default_includes", [])
        if isinstance(default_includes, list):
            includes = [str(x) for x in default_includes if isinstance(x, str)]
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
            target_repo_root=target_repo_root,
            includes=includes,
            overwrite=bool(args.overwrite_bootstrap),
        )

    rendered: dict[str, Path] = {}
    for key in includes:
        internal_vars: list[str] = []
        if args.bootstrap and key == "problem857":
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
        report_name = str(_pack_spec(pack_id).get("report_name", f"orp.{pack_id}.pack-install-report.md"))
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
