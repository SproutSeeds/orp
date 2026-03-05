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


def _write_board_md(root: Path, problem: int, board: dict[str, Any]) -> None:
    lines = []
    lines.append(f"# Problem {problem} Ops Board")
    lines.append("")
    lines.append(f"- updated_utc: `{board.get('updated_utc', '')}`")
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

    out_path = _board_md_path(root, problem)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def _print_show(board: dict[str, Any]) -> None:
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
        if args.problem == 367:
            no_go = board.get("no_go_active", [])
            if isinstance(no_go, list):
                print("no_go_active=" + ",".join(str(x) for x in no_go))
            else:
                print("no_go_active=")
        print(f"ready_atoms={int(board.get('ready_atoms', 0))}")
        return 0

    if args.cmd == "refresh":
        board["updated_utc"] = _now_utc()
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


def _now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Starter spec-check stub")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    out_path = Path("orchestrator") / "logs" / args.run_id / "SPEC_CHECK.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "PASS",
        "run_id": args.run_id,
        "checked_at_utc": _now_utc(),
        "note": "starter stub: replace with real spec_check.py when available",
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\\n", encoding="utf-8")

    print("spec_check=PASS")
    print(f"spec_check_json={out_path}")
    return 0


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
    target_repo_root: Path,
    includes: list[str],
    overwrite: bool,
) -> list[str]:
    created: list[str] = []

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
    component_key: str,
    extra_vars: list[str],
    internal_vars: list[str],
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
        template_id = str(COMPONENTS[key]["template_id"])
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
        default=".",
        help="Target repository root where rendered ORP configs are written (default: current directory)",
    )
    p.add_argument(
        "--include",
        action="append",
        choices=sorted(COMPONENTS.keys()),
        default=[],
        help=(
            "Component to install (repeatable). "
            "Choices: catalog, live_compare, problem857, governance. "
            "Default when omitted: catalog + live_compare + problem857."
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
        includes = ["catalog", "live_compare", "problem857"]

    bootstrap_created: list[str] = []
    if args.bootstrap:
        bootstrap_created = _install_starter_adapters(
            target_repo_root=target_repo_root,
            includes=includes,
            overwrite=bool(args.overwrite_bootstrap),
        )

    rendered: dict[str, Path] = {}
    for key in includes:
        internal_vars: list[str] = []
        if args.bootstrap and key == "problem857":
            internal_vars.append(
                "PROBLEM857_LEAN_BUILD_COMMAND=python3 scripts/orp-lean-build-stub.py SunflowerLean.Balance"
            )
        out_path = _render_component(
            orp_repo_root=orp_repo_root,
            pack_root=pack_root,
            target_repo_root=target_repo_root,
            component_key=key,
            extra_vars=list(args.var or []),
            internal_vars=internal_vars,
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
        bootstrap_enabled=bool(args.bootstrap),
        bootstrap_created=bootstrap_created,
    )

    print(f"pack_id={pack_id}")
    print(f"pack_version={pack_version}")
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
