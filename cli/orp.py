#!/usr/bin/env python3
"""Minimal ORP CLI runtime skeleton.

Commands:
- init
- gate run
- packet emit
- erdos sync
- pack list
- pack fetch
- pack install
- report summary

Design goals:
- Local-first
- Low dependency surface
- Deterministic artifact layout
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


def _now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return "run-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _tool_version() -> str:
    env_version = os.environ.get("ORP_VERSION", "").strip()
    if env_version:
        return env_version

    package_json = Path(__file__).resolve().parent.parent / "package.json"
    if not package_json.exists():
        return "unknown"

    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
    except Exception:
        return "unknown"

    version = payload.get("version")
    if isinstance(version, str) and version.strip():
        return version.strip()
    return "unknown"


ORP_TOOL_VERSION = _tool_version()


def _path_for_state(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except Exception:
        return str(path)


def _load_config(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    if path.suffix.lower() in {".json"}:
        return json.loads(text)

    # YAML path (orp.yml / orp.yaml)
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "YAML config requires PyYAML. Install it or provide JSON config."
        ) from exc
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Config root must be an object: {path}")
    return loaded


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(_read_text(path))


def _ensure_dirs(repo_root: Path) -> None:
    (repo_root / "orp" / "packets").mkdir(parents=True, exist_ok=True)
    (repo_root / "orp" / "artifacts").mkdir(parents=True, exist_ok=True)
    state_path = repo_root / "orp" / "state.json"
    if not state_path.exists():
        _write_json(
            state_path,
            {
                "last_run_id": "",
                "last_packet_id": "",
                "runs": {},
            },
        )


def _replace_vars(s: str, values: dict[str, str]) -> str:
    out = s
    for key, val in values.items():
        out = out.replace("{" + key + "}", val)
    return out


def _sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    return "sha256:" + h.hexdigest()


def _eval_rule(text: str, must_contain: list[str] | None, must_not_contain: list[str] | None) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if must_contain:
        for needle in must_contain:
            if needle not in text:
                issues.append(f"missing required substring: {needle}")
    if must_not_contain:
        for needle in must_not_contain:
            if needle in text:
                issues.append(f"forbidden substring present: {needle}")
    return (len(issues) == 0, issues)


def _collect_atomic_context(config: dict[str, Any], repo_root: Path, run: dict[str, Any] | None = None) -> dict[str, Any] | None:
    board_cfg = config.get("atomic_board")
    if not isinstance(board_cfg, dict) or not board_cfg.get("enabled"):
        return None

    board_path = board_cfg.get("board_path")
    if not isinstance(board_path, str):
        return None
    full = repo_root / board_path
    if not full.exists():
        return None

    try:
        board = _read_json(full)
    except Exception:
        return None

    route_status: dict[str, Any] = {}
    live = board.get("live_snapshot", {}) if isinstance(board, dict) else {}
    route_rows = []
    if isinstance(live, dict):
        # Some boards store this as "routes", others as "route_status".
        route_rows = live.get("route_status", live.get("routes", []))
    if isinstance(route_rows, list):
        for row in route_rows:
            if not isinstance(row, dict):
                continue
            route_name = str(row.get("route", "")).strip()
            if not route_name:
                continue
            route_status[route_name] = {
                "done": int(row.get("loose_done", 0)),
                "total": int(row.get("loose_total", 0)),
                "strict_done": int(row.get("strict_done", 0)),
                "strict_total": int(row.get("strict_total", 0)),
            }

    ticket_id = ""
    gate_id = ""
    atom_id = ""
    deps: list[str] = []
    ready_queue_size = 0

    # Best-effort extraction from run gate logs (typically a "*ready*" gate).
    if isinstance(run, dict):
        results = run.get("results", [])
        if isinstance(results, list):
            for gate_res in results:
                if not isinstance(gate_res, dict):
                    continue
                gid = str(gate_res.get("gate_id", ""))
                cmd = str(gate_res.get("command", ""))
                if "ready" not in gid.lower() and " ready" not in cmd and ".py ready" not in cmd:
                    continue
                stdout_rel = gate_res.get("stdout_path")
                if not isinstance(stdout_rel, str) or not stdout_rel:
                    continue
                stdout_path = repo_root / stdout_rel
                if not stdout_path.exists():
                    continue
                content = stdout_path.read_text(encoding="utf-8")
                m_count = re.search(r"^ready_atoms=(\d+)$", content, flags=re.MULTILINE)
                if m_count:
                    ready_queue_size = int(m_count.group(1))
                m_row = re.search(
                    r"^(?P<atom>\S+).*ticket=(?P<ticket>\S+)\s+gate=(?P<gate>\S+).*deps=(?P<deps>\S+)",
                    content,
                    flags=re.MULTILINE,
                )
                if m_row:
                    atom_id = m_row.group("atom")
                    ticket_id = m_row.group("ticket")
                    gate_id = m_row.group("gate")
                    dep_text = m_row.group("deps")
                    if dep_text and dep_text != "root":
                        deps = [x for x in dep_text.split(",") if x]
                break

    return {
        "board_id": str(board.get("board_id", "")),
        "problem_id": str(board.get("problem_id", "")),
        "ticket_id": ticket_id,
        "gate_id": gate_id,
        "atom_id": atom_id,
        "dependencies": deps,
        "ready_queue_size": ready_queue_size,
        "board_snapshot_path": board_path,
        "route_status": route_status,
    }


def cmd_init(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    _ensure_dirs(repo_root)

    config_path = repo_root / args.config
    if not config_path.exists():
        starter = (
            'version: "1"\n'
            "project:\n"
            "  name: my-project\n"
            "  repo_root: .\n"
            "  canonical_paths:\n"
            "    code: src/\n"
            "    analysis: analysis/\n"
            "lifecycle:\n"
            "  claim_status_map:\n"
            "    Draft: draft\n"
            "    In review: ready\n"
            "    Verified: reviewed\n"
            "    Blocked: blocked\n"
            "    Retracted: retracted\n"
            "  atom_status_map:\n"
            "    todo: draft\n"
            "    in_progress: ready\n"
            "    blocked: blocked\n"
            "    done: reviewed\n"
            "gates:\n"
            "  - id: smoke\n"
            "    description: Basic smoke gate\n"
            "    phase: verification\n"
            "    command: echo ORP_SMOKE\n"
            "    pass:\n"
            "      exit_codes: [0]\n"
            "      stdout_must_contain:\n"
            "        - ORP_SMOKE\n"
            "profiles:\n"
            "  default:\n"
            "    description: Minimal starter profile\n"
            "    mode: discovery\n"
            "    packet_kind: problem_scope\n"
            "    gate_ids:\n"
            "      - smoke\n"
        )
        config_path.write_text(starter, encoding="utf-8")
        print(f"created {config_path}")
    else:
        print(f"kept existing {config_path}")

    print(f"initialized ORP runtime dirs under {repo_root / 'orp'}")
    return 0


def _load_profile(config: dict[str, Any], name: str) -> dict[str, Any]:
    profiles = config.get("profiles")
    if not isinstance(profiles, dict):
        raise RuntimeError("config missing profiles object")
    profile = profiles.get(name)
    if not isinstance(profile, dict):
        raise RuntimeError(f"profile not found: {name}")
    return profile


def _gate_map(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = config.get("gates")
    if not isinstance(raw, list):
        raise RuntimeError("config missing gates list")
    out: dict[str, dict[str, Any]] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        gid = row.get("id")
        if isinstance(gid, str):
            out[gid] = row
    return out


def cmd_gate_run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    _ensure_dirs(repo_root)

    config_path = (repo_root / args.config).resolve()
    config = _load_config(config_path)
    profile = _load_profile(config, args.profile)
    gate_ids = profile.get("gate_ids")
    if not isinstance(gate_ids, list) or not all(isinstance(x, str) for x in gate_ids):
        raise RuntimeError("profile gate_ids must be list[str]")

    gid_to_gate = _gate_map(config)

    run_id = args.run_id or _run_id()
    started = _now_utc()
    run_artifacts = repo_root / "orp" / "artifacts" / run_id
    run_artifacts.mkdir(parents=True, exist_ok=True)

    run_results: list[dict[str, Any]] = []
    stop_now = False
    vars_map = {"run_id": run_id}
    shell = config.get("runtime", {}).get("shell", "/bin/bash")

    # Deterministic input hash for current config + profile
    det_hash = _sha256_text(json.dumps({"config": config, "profile": profile}, sort_keys=True))

    for gate_id in gate_ids:
        gate = gid_to_gate.get(gate_id)
        if gate is None:
            raise RuntimeError(f"unknown gate in profile: {gate_id}")

        if stop_now:
            run_results.append(
                {
                    "gate_id": gate_id,
                    "phase": gate.get("phase", "custom"),
                    "command": str(gate.get("command", "")),
                    "status": "skipped",
                    "exit_code": 0,
                    "duration_ms": 0,
                    "stdout_path": "",
                    "stderr_path": "",
                    "rule_issues": ["skipped after previous gate stop"],
                }
            )
            continue

        cmd = _replace_vars(str(gate.get("command", "")), vars_map)
        workdir = gate.get("working_dir")
        cwd = repo_root / workdir if isinstance(workdir, str) else repo_root
        timeout_sec = int(gate.get("timeout_sec", config.get("runtime", {}).get("default_timeout_sec", 900)))

        t0 = dt.datetime.now(dt.timezone.utc)
        try:
            proc = subprocess.run(
                [str(shell), "-lc", cmd],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            rc = int(proc.returncode)
            out = proc.stdout or ""
            err = proc.stderr or ""
            exec_status = "ok"
        except subprocess.TimeoutExpired as exc:
            rc = 124
            out = exc.stdout or ""
            err = (exc.stderr or "") + f"\nERROR: gate timeout after {timeout_sec}s\n"
            exec_status = "timeout"

        t1 = dt.datetime.now(dt.timezone.utc)
        dur_ms = int((t1 - t0).total_seconds() * 1000)
        stdout_path = run_artifacts / f"{gate_id}.stdout.log"
        stderr_path = run_artifacts / f"{gate_id}.stderr.log"
        stdout_path.write_text(out, encoding="utf-8")
        stderr_path.write_text(err, encoding="utf-8")

        pass_cfg = gate.get("pass", {})
        exit_codes = pass_cfg.get("exit_codes", [0]) if isinstance(pass_cfg, dict) else [0]
        if not isinstance(exit_codes, list):
            exit_codes = [0]

        ok_exit = rc in [int(x) for x in exit_codes]
        ok_out, out_issues = _eval_rule(
            out,
            pass_cfg.get("stdout_must_contain", []) if isinstance(pass_cfg, dict) else [],
            pass_cfg.get("stdout_must_not_contain", []) if isinstance(pass_cfg, dict) else [],
        )
        ok_err, err_issues = _eval_rule(
            err,
            pass_cfg.get("stderr_must_contain", []) if isinstance(pass_cfg, dict) else [],
            pass_cfg.get("stderr_must_not_contain", []) if isinstance(pass_cfg, dict) else [],
        )

        file_issues: list[str] = []
        fm_exist = pass_cfg.get("file_must_exist", []) if isinstance(pass_cfg, dict) else []
        if isinstance(fm_exist, list):
            for rel in fm_exist:
                if not isinstance(rel, str):
                    continue
                rel = _replace_vars(rel, vars_map)
                if not (repo_root / rel).exists():
                    file_issues.append(f"required file missing: {rel}")

        passed = ok_exit and ok_out and ok_err and (len(file_issues) == 0) and (exec_status == "ok")
        status = "pass" if passed else "fail"
        issues = []
        if not ok_exit:
            issues.append(f"exit code {rc} not in {exit_codes}")
        issues.extend(out_issues)
        issues.extend(err_issues)
        issues.extend(file_issues)
        if exec_status != "ok":
            issues.append(exec_status)

        run_results.append(
            {
                "gate_id": gate_id,
                "phase": gate.get("phase", "custom"),
                "command": cmd,
                "status": status,
                "exit_code": rc,
                "duration_ms": dur_ms,
                "stdout_path": str(stdout_path.relative_to(repo_root)),
                "stderr_path": str(stderr_path.relative_to(repo_root)),
                "rule_issues": issues,
                "evidence_paths": gate.get("evidence", {}).get("paths", []) if isinstance(gate.get("evidence"), dict) else [],
            }
        )

        if not passed:
            on_fail = str(gate.get("on_fail", "stop"))
            if on_fail in {"stop", "mark_blocked"}:
                stop_now = True

    ended = _now_utc()
    gates_passed = sum(1 for g in run_results if g["status"] == "pass")
    gates_failed = sum(1 for g in run_results if g["status"] == "fail")
    gates_total = len(run_results)
    overall = "PASS" if gates_failed == 0 else "FAIL"

    run_record = {
        "run_id": run_id,
        "config_path": _path_for_state(config_path, repo_root),
        "profile": args.profile,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "deterministic_input_hash": det_hash,
        "results": run_results,
        "summary": {
            "overall_result": overall,
            "gates_passed": gates_passed,
            "gates_failed": gates_failed,
            "gates_total": gates_total,
        },
    }

    run_json_path = run_artifacts / "RUN.json"
    _write_json(run_json_path, run_record)

    state_path = repo_root / "orp" / "state.json"
    state = _read_json(state_path)
    runs = state.setdefault("runs", {})
    if isinstance(runs, dict):
        runs[run_id] = str(run_json_path.relative_to(repo_root))
    state["last_run_id"] = run_id
    _write_json(state_path, state)

    print(f"run_id={run_id}")
    print(f"overall={overall} passed={gates_passed} failed={gates_failed} total={gates_total}")
    print(f"run_record={run_json_path.relative_to(repo_root)}")
    return 0 if overall == "PASS" else 1


def _packet_id(kind: str, run_id: str) -> str:
    return f"pkt-{kind}-{run_id}"


def _workflow_state_from_run(config: dict[str, Any], run: dict[str, Any]) -> tuple[str, str]:
    overall = run.get("summary", {}).get("overall_result", "INCONCLUSIVE")
    if overall == "PASS":
        return "reviewed", "done"
    if overall == "FAIL":
        return "blocked", "blocked"
    return "ready", "in_progress"


def cmd_packet_emit(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    _ensure_dirs(repo_root)
    config_path = (repo_root / args.config).resolve()
    config = _load_config(config_path)
    profile = _load_profile(config, args.profile)
    effective_config = dict(config)
    profile_atomic = profile.get("atomic_board")
    if isinstance(profile_atomic, dict):
        effective_config["atomic_board"] = profile_atomic

    state = _read_json(repo_root / "orp" / "state.json")
    run_id = args.run_id or state.get("last_run_id", "")
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError("no run_id found; run `orp gate run` first or pass --run-id")

    run_ref = state.get("runs", {}).get(run_id, f"orp/artifacts/{run_id}/RUN.json")
    run_json_path = repo_root / str(run_ref)
    if not run_json_path.exists():
        run_json_path = repo_root / "orp" / "artifacts" / run_id / "RUN.json"
    run = _read_json(run_json_path)

    kind = args.kind or profile.get("packet_kind") or config.get("packet", {}).get("default_kind", "problem_scope")
    if not isinstance(kind, str):
        kind = "problem_scope"

    packet_id = _packet_id(kind, run_id)
    wf_state, atom_status = _workflow_state_from_run(config, run)
    now = _now_utc()

    git_remote = ""
    git_branch = ""
    git_commit = ""
    try:
        git_remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass
    try:
        git_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass

    atomic_context = _collect_atomic_context(effective_config, repo_root, run=run)

    packet = {
        "schema_version": "1.0.0",
        "packet_id": packet_id,
        "kind": kind,
        "created_at_utc": now,
        "protocol_boundary": {
            "process_only": True,
            "evidence_paths": [],
            "note": "Packet is process metadata. Evidence remains in canonical artifact paths.",
        },
        "repo": {
            "root_path": str(repo_root),
            "git": {
                "remote": git_remote,
                "branch": git_branch,
                "commit": git_commit,
            },
        },
        "run": {
            "run_id": run_id,
            "tool": {"name": "orp", "version": ORP_TOOL_VERSION},
            "deterministic_input_hash": run.get("deterministic_input_hash", ""),
            "started_at_utc": run.get("started_at_utc", now),
            "ended_at_utc": run.get("ended_at_utc", now),
            "duration_ms": _duration_ms(run.get("started_at_utc"), run.get("ended_at_utc")),
        },
        "lifecycle": {
            "workflow_state": wf_state,
            "atom_status": atom_status,
            "state_note": f"derived from run summary: {run.get('summary', {}).get('overall_result', 'INCONCLUSIVE')}",
        },
        "gates": run.get("results", []),
        "summary": run.get("summary", {"overall_result": "INCONCLUSIVE", "gates_passed": 0, "gates_failed": 0, "gates_total": 0}),
        "artifacts": {
            "packet_json_path": f"orp/packets/{packet_id}.json",
            "packet_md_path": f"orp/packets/{packet_id}.md",
            "artifact_root": f"orp/artifacts/{run_id}",
            "extra_paths": [],
        },
    }
    if atomic_context is not None and kind in {"problem_scope", "atom_pass"}:
        packet["atomic_context"] = atomic_context

    packets_dir = repo_root / "orp" / "packets"
    packets_dir.mkdir(parents=True, exist_ok=True)
    packet_json_path = packets_dir / f"{packet_id}.json"
    _write_json(packet_json_path, packet)

    packet_md_path = packets_dir / f"{packet_id}.md"
    packet_md = _render_packet_md(packet)
    packet_md_path.write_text(packet_md, encoding="utf-8")

    state["last_packet_id"] = packet_id
    _write_json(repo_root / "orp" / "state.json", state)

    print(f"packet_id={packet_id}")
    print(f"packet_json={packet_json_path.relative_to(repo_root)}")
    print(f"packet_md={packet_md_path.relative_to(repo_root)}")
    return 0


def cmd_pack_list(args: argparse.Namespace) -> int:
    _ = args
    orp_repo_root = Path(__file__).resolve().parent.parent
    packs_root = orp_repo_root / "packs"
    if not packs_root.exists():
        print(f"packs_root={packs_root}")
        print("packs.count=0")
        return 0

    count = 0
    for child in sorted(packs_root.iterdir()):
        if not child.is_dir():
            continue
        meta_path = child / "pack.yml"
        if not meta_path.exists():
            continue
        try:
            meta = _load_config(meta_path)
        except Exception:
            meta = {}
        pack_id = str(meta.get("pack_id", child.name)) if isinstance(meta, dict) else child.name
        version = str(meta.get("version", "unknown")) if isinstance(meta, dict) else "unknown"
        name = str(meta.get("name", "")) if isinstance(meta, dict) else ""
        print(f"pack.id={pack_id}")
        print(f"pack.version={version}")
        print(f"pack.path={child}")
        if name:
            print(f"pack.name={name}")
        print("---")
        count += 1

    print(f"packs_root={packs_root}")
    print(f"packs.count={count}")
    return 0


def cmd_pack_install(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "orp-pack-install.py"
    if not script_path.exists():
        raise RuntimeError(f"missing pack install script: {script_path}")

    forwarded: list[str] = [
        "--pack-id",
        args.pack_id,
        "--target-repo-root",
        args.target_repo_root,
    ]
    if args.pack_path:
        forwarded.extend(["--pack-path", args.pack_path])
    if args.orp_repo_root:
        forwarded.extend(["--orp-repo-root", args.orp_repo_root])
    for comp in args.include or []:
        forwarded.extend(["--include", str(comp)])
    for raw in args.var or []:
        forwarded.extend(["--var", str(raw)])
    if args.report:
        forwarded.extend(["--report", args.report])
    if args.strict_deps:
        forwarded.append("--strict-deps")
    if not args.bootstrap:
        forwarded.append("--no-bootstrap")
    if args.overwrite_bootstrap:
        forwarded.append("--overwrite-bootstrap")

    cmd = [sys.executable, str(script_path), *forwarded]
    proc = subprocess.run(cmd, cwd=str(repo_root))
    return int(proc.returncode)


def _parse_kv_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def cmd_pack_fetch(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    fetch_script = Path(__file__).resolve().parent.parent / "scripts" / "orp-pack-fetch.py"
    install_script = Path(__file__).resolve().parent.parent / "scripts" / "orp-pack-install.py"
    if not fetch_script.exists():
        raise RuntimeError(f"missing pack fetch script: {fetch_script}")

    fetch_cmd: list[str] = [sys.executable, str(fetch_script), "--source", args.source]
    if args.pack_id:
        fetch_cmd.extend(["--pack-id", args.pack_id])
    if args.ref:
        fetch_cmd.extend(["--ref", args.ref])
    if args.cache_root:
        fetch_cmd.extend(["--cache-root", args.cache_root])
    if args.name:
        fetch_cmd.extend(["--name", args.name])

    proc = subprocess.run(fetch_cmd, cwd=str(repo_root), capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, file=sys.stderr, end="")
        return int(proc.returncode)

    if not args.install_target:
        return 0
    if not install_script.exists():
        raise RuntimeError(f"missing pack install script: {install_script}")

    kv = _parse_kv_lines(proc.stdout)
    pack_path = kv.get("pack_path", "").strip()
    if not pack_path:
        raise RuntimeError("pack fetch did not return pack_path")

    install_cmd: list[str] = [
        sys.executable,
        str(install_script),
        "--pack-path",
        pack_path,
        "--target-repo-root",
        args.install_target,
    ]
    # preserve discovered pack id for reporting consistency when available
    fetched_pack_id = kv.get("pack_id", "").strip()
    if fetched_pack_id:
        install_cmd.extend(["--pack-id", fetched_pack_id])
    if args.orp_repo_root:
        install_cmd.extend(["--orp-repo-root", args.orp_repo_root])
    for comp in args.include or []:
        install_cmd.extend(["--include", str(comp)])
    for raw in args.var or []:
        install_cmd.extend(["--var", str(raw)])
    if args.report:
        install_cmd.extend(["--report", args.report])
    if args.strict_deps:
        install_cmd.append("--strict-deps")
    if args.no_bootstrap:
        install_cmd.append("--no-bootstrap")
    if args.overwrite_bootstrap:
        install_cmd.append("--overwrite-bootstrap")

    proc_install = subprocess.run(install_cmd, cwd=str(repo_root))
    return int(proc_install.returncode)


def cmd_erdos_sync(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "orp-erdos-problems-sync.py"
    if not script_path.exists():
        raise RuntimeError(f"missing sync script: {script_path}")

    forwarded: list[str] = []
    if args.source_url is not None:
        forwarded.extend(["--source-url", args.source_url])
    if args.input_html is not None:
        forwarded.extend(["--input-html", args.input_html])
    if args.write_html_snapshot is not None:
        forwarded.extend(["--write-html-snapshot", args.write_html_snapshot])
    if args.timeout_sec is not None:
        forwarded.extend(["--timeout-sec", str(args.timeout_sec)])
    if args.user_agent is not None:
        forwarded.extend(["--user-agent", args.user_agent])
    if args.active_status is not None:
        forwarded.extend(["--active-status", args.active_status])
    if args.allow_count_mismatch:
        forwarded.append("--allow-count-mismatch")
    if args.out_all is not None:
        forwarded.extend(["--out-all", args.out_all])
    if args.out_open is not None:
        forwarded.extend(["--out-open", args.out_open])
    if args.out_closed is not None:
        forwarded.extend(["--out-closed", args.out_closed])
    if args.out_active is not None:
        forwarded.extend(["--out-active", args.out_active])
    if args.out_open_list is not None:
        forwarded.extend(["--out-open-list", args.out_open_list])
    if args.open_list_max_statement_chars is not None:
        forwarded.extend(
            ["--open-list-max-statement-chars", str(args.open_list_max_statement_chars)]
        )
    for pid in args.problem_id or []:
        forwarded.extend(["--problem-id", str(pid)])
    if args.out_problem_dir is not None:
        forwarded.extend(["--out-problem-dir", args.out_problem_dir])

    forwarded.extend(list(args.sync_args or []))
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]

    cmd = [sys.executable, str(script_path), *forwarded]
    proc = subprocess.run(cmd, cwd=str(repo_root))
    return int(proc.returncode)


def _resolve_run_json_path(
    *,
    repo_root: Path,
    run_id_arg: str,
    run_json_arg: str,
) -> tuple[str, Path]:
    if run_json_arg:
        run_json = Path(run_json_arg)
        if not run_json.is_absolute():
            run_json = repo_root / run_json
        run_json = run_json.resolve()
        if not run_json.exists():
            raise RuntimeError(f"run json not found: {run_json}")
        run = _read_json(run_json)
        run_id = str(run.get("run_id", "")).strip()
        if not run_id:
            run_id = run_json.parent.name
        return run_id, run_json

    state_path = repo_root / "orp" / "state.json"
    state: dict[str, Any] = {}
    if state_path.exists():
        state = _read_json(state_path)

    run_id = run_id_arg.strip()
    if not run_id:
        run_id = str(state.get("last_run_id", "")).strip()
    if not run_id:
        raise RuntimeError("no run_id found; pass --run-id or --run-json")

    run_json = None
    runs = state.get("runs")
    if isinstance(runs, dict):
        run_ref = runs.get(run_id)
        if isinstance(run_ref, str) and run_ref:
            candidate = (repo_root / run_ref).resolve()
            if candidate.exists():
                run_json = candidate

    if run_json is None:
        candidate = (repo_root / "orp" / "artifacts" / run_id / "RUN.json").resolve()
        if candidate.exists():
            run_json = candidate

    if run_json is None:
        raise RuntimeError(f"run json not found for run_id={run_id}")
    return run_id, run_json


def _run_duration_ms_from_record(run: dict[str, Any]) -> int:
    started = run.get("started_at_utc")
    ended = run.get("ended_at_utc")
    duration = _duration_ms(started, ended)
    if duration > 0:
        return duration
    results = run.get("results", [])
    if not isinstance(results, list):
        return 0
    total = 0
    for row in results:
        if not isinstance(row, dict):
            continue
        try:
            total += int(row.get("duration_ms", 0))
        except Exception:
            continue
    return max(0, total)


def _one_line(s: str, max_len: int = 88) -> str:
    collapsed = re.sub(r"\s+", " ", s).strip()
    if len(collapsed) <= max_len:
        return collapsed
    if max_len <= 3:
        return collapsed[:max_len]
    return collapsed[: max_len - 3].rstrip() + "..."


def _render_run_summary_md(run: dict[str, Any]) -> str:
    run_id = str(run.get("run_id", "")).strip()
    profile = str(run.get("profile", "")).strip()
    config_path = str(run.get("config_path", "")).strip()
    started = str(run.get("started_at_utc", "")).strip()
    ended = str(run.get("ended_at_utc", "")).strip()
    det_hash = str(run.get("deterministic_input_hash", "")).strip()

    summary = run.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    overall = str(summary.get("overall_result", "INCONCLUSIVE")).strip() or "INCONCLUSIVE"
    passed = int(summary.get("gates_passed", 0) or 0)
    failed = int(summary.get("gates_failed", 0) or 0)
    total = int(summary.get("gates_total", 0) or 0)
    duration_ms = _run_duration_ms_from_record(run)

    results = run.get("results", [])
    if not isinstance(results, list):
        results = []

    lines: list[str] = []
    lines.append(f"# ORP Run Summary `{run_id}`")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- overall_result: `{overall}`")
    lines.append(f"- profile: `{profile}`")
    lines.append(f"- gates: `{passed} passed / {failed} failed / {total} total`")
    lines.append(f"- duration_ms: `{duration_ms}`")
    lines.append(f"- started_at_utc: `{started}`")
    lines.append(f"- ended_at_utc: `{ended}`")
    lines.append(f"- config_path: `{config_path}`")
    lines.append("")
    lines.append("## What This Report Shows")
    lines.append("")
    lines.append("- Which gates ran, in what order, and with what command.")
    lines.append("- Whether each gate passed or failed, with exit code and timing.")
    lines.append("- Where to inspect raw evidence (`stdout` / `stderr`) for each gate.")
    lines.append("- A deterministic input hash so teams can compare runs reliably.")
    lines.append("")
    lines.append("## Gate Results")
    lines.append("")
    lines.append("| Gate | Status | Exit | Duration ms | Command |")
    lines.append("|---|---:|---:|---:|---|")

    for row in results:
        if not isinstance(row, dict):
            continue
        gate_id = str(row.get("gate_id", ""))
        status = str(row.get("status", ""))
        exit_code = str(row.get("exit_code", ""))
        gate_dur = str(row.get("duration_ms", ""))
        command = _one_line(str(row.get("command", "")))
        lines.append(
            f"| `{gate_id}` | `{status}` | {exit_code} | {gate_dur} | `{command}` |"
        )

    failing_rows = [
        row
        for row in results
        if isinstance(row, dict) and str(row.get("status", "")).lower() == "fail"
    ]
    if failing_rows:
        lines.append("")
        lines.append("## Failing Conditions")
        lines.append("")
        for row in failing_rows:
            gate_id = str(row.get("gate_id", ""))
            lines.append(f"- `{gate_id}`")
            issues = row.get("rule_issues", [])
            if isinstance(issues, list) and issues:
                for issue in issues:
                    lines.append(f"  - {issue}")
            else:
                lines.append("  - no explicit rule issues recorded")

    lines.append("")
    lines.append("## Evidence Pointers")
    lines.append("")
    for row in results:
        if not isinstance(row, dict):
            continue
        gate_id = str(row.get("gate_id", ""))
        stdout_path = str(row.get("stdout_path", "")).strip()
        stderr_path = str(row.get("stderr_path", "")).strip()
        lines.append(
            f"- `{gate_id}`: stdout=`{stdout_path or '(none)'}` stderr=`{stderr_path or '(none)'}`"
        )

    lines.append("")
    lines.append("## Reproducibility")
    lines.append("")
    lines.append(f"- deterministic_input_hash: `{det_hash}`")
    lines.append("- rerun with the same profile/config and compare this hash + gate outputs.")
    lines.append("")
    return "\n".join(lines)


def cmd_report_summary(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    _ensure_dirs(repo_root)

    run_id, run_json_path = _resolve_run_json_path(
        repo_root=repo_root,
        run_id_arg=args.run_id,
        run_json_arg=args.run_json,
    )
    run = _read_json(run_json_path)
    summary_md = _render_run_summary_md(run)

    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = repo_root / out_path
        out_path = out_path.resolve()
    else:
        out_path = run_json_path.parent / "RUN_SUMMARY.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(summary_md, encoding="utf-8")

    print(f"run_id={run_id}")
    print(f"run_json={_path_for_state(run_json_path, repo_root)}")
    print(f"summary_md={_path_for_state(out_path, repo_root)}")
    if args.print_stdout:
        print("---")
        print(summary_md)
    return 0


def _duration_ms(started: Any, ended: Any) -> int:
    try:
        s = dt.datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        e = dt.datetime.fromisoformat(str(ended).replace("Z", "+00:00"))
        return max(0, int((e - s).total_seconds() * 1000))
    except Exception:
        return 0


def _render_packet_md(packet: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# ORP Packet `{packet.get('packet_id', '')}`")
    lines.append("")
    lines.append(f"- Kind: `{packet.get('kind', '')}`")
    lines.append(f"- Created (UTC): `{packet.get('created_at_utc', '')}`")
    lines.append(f"- Workflow state: `{packet.get('lifecycle', {}).get('workflow_state', '')}`")
    lines.append(f"- Overall result: `{packet.get('summary', {}).get('overall_result', '')}`")
    lines.append("")
    lines.append("## Gate Results")
    lines.append("")
    lines.append("| Gate | Phase | Status | Exit | Duration ms |")
    lines.append("|---|---|---:|---:|---:|")
    for gate in packet.get("gates", []):
        if not isinstance(gate, dict):
            continue
        lines.append(
            f"| `{gate.get('gate_id', '')}` | `{gate.get('phase', '')}` | `{gate.get('status', '')}` | "
            f"{gate.get('exit_code', '')} | {gate.get('duration_ms', '')} |"
        )

    atomic = packet.get("atomic_context")
    if isinstance(atomic, dict):
        lines.append("")
        lines.append("## Atomic Context")
        lines.append("")
        lines.append(f"- Board: `{atomic.get('board_id', '')}`")
        lines.append(f"- Problem: `{atomic.get('problem_id', '')}`")
        lines.append(f"- Snapshot: `{atomic.get('board_snapshot_path', '')}`")

    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append("- This packet is process metadata only.")
    lines.append("- Evidence remains in canonical artifact paths.")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ORP CLI (minimal runtime skeleton)")
    p.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    p.add_argument("--config", default="orp.yml", help="Config path relative to repo root (default: orp.yml)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s_init = sub.add_parser("init", help="Initialize runtime folders and starter config")
    s_init.set_defaults(func=cmd_init)

    s_gate = sub.add_parser("gate", help="Gate operations")
    gate_sub = s_gate.add_subparsers(dest="gate_cmd", required=True)
    s_run = gate_sub.add_parser("run", help="Run configured gates for a profile")
    s_run.add_argument("--profile", required=True, help="Profile name from config")
    s_run.add_argument("--run-id", default="", help="Optional run id override")
    s_run.set_defaults(func=cmd_gate_run)

    s_packet = sub.add_parser("packet", help="Packet operations")
    packet_sub = s_packet.add_subparsers(dest="packet_cmd", required=True)
    s_emit = packet_sub.add_parser("emit", help="Emit packet from latest or specified run")
    s_emit.add_argument("--profile", required=True, help="Profile name from config")
    s_emit.add_argument("--run-id", default="", help="Run id (defaults to last run)")
    s_emit.add_argument("--kind", default="", help="Packet kind override")
    s_emit.set_defaults(func=cmd_packet_emit)

    s_erdos = sub.add_parser("erdos", help="Erdos catalog operations")
    erdos_sub = s_erdos.add_subparsers(dest="erdos_cmd", required=True)
    s_erdos_sync = erdos_sub.add_parser("sync", help="Sync Erdos problems catalog")
    s_erdos_sync.add_argument("--source-url", default=None, help="Override source URL")
    s_erdos_sync.add_argument("--input-html", default=None, help="Read from local HTML file")
    s_erdos_sync.add_argument(
        "--write-html-snapshot",
        default=None,
        help="Write fetched HTML snapshot path",
    )
    s_erdos_sync.add_argument("--timeout-sec", type=int, default=None, help="HTTP timeout seconds")
    s_erdos_sync.add_argument("--user-agent", default=None, help="HTTP user-agent")
    s_erdos_sync.add_argument(
        "--active-status",
        choices=["open", "closed", "all"],
        default=None,
        help="Active subset (open|closed|all)",
    )
    s_erdos_sync.add_argument(
        "--allow-count-mismatch",
        action="store_true",
        help="Allow parsed count mismatch vs site banner",
    )
    s_erdos_sync.add_argument("--out-all", default=None, help="Output all-problems JSON path")
    s_erdos_sync.add_argument("--out-open", default=None, help="Output open-problems JSON path")
    s_erdos_sync.add_argument(
        "--out-closed", default=None, help="Output closed-problems JSON path"
    )
    s_erdos_sync.add_argument(
        "--out-active", default=None, help="Output active-problems JSON path"
    )
    s_erdos_sync.add_argument(
        "--out-open-list",
        default=None,
        help="Output open-problems markdown list path",
    )
    s_erdos_sync.add_argument(
        "--open-list-max-statement-chars",
        type=int,
        default=None,
        help="Open-list statement preview char cap",
    )
    s_erdos_sync.add_argument(
        "--problem-id",
        action="append",
        type=int,
        default=[],
        help="Problem id to print direct link/status for (repeatable)",
    )
    s_erdos_sync.add_argument(
        "--out-problem-dir",
        default=None,
        help="Write selected problem payloads to this directory",
    )
    s_erdos_sync.add_argument(
        "sync_args",
        nargs=argparse.REMAINDER,
        help="Additional args forwarded to scripts/orp-erdos-problems-sync.py",
    )
    s_erdos_sync.set_defaults(func=cmd_erdos_sync)

    s_pack = sub.add_parser("pack", help="Profile pack operations")
    pack_sub = s_pack.add_subparsers(dest="pack_cmd", required=True)

    s_pack_list = pack_sub.add_parser("list", help="List available local ORP packs")
    s_pack_list.set_defaults(func=cmd_pack_list)

    s_pack_install = pack_sub.add_parser(
        "install",
        help="Install/render pack templates into a target repository with dependency audit",
    )
    s_pack_install.add_argument(
        "--pack-id",
        default="erdos-open-problems",
        help="Pack id under ORP packs/ (default: erdos-open-problems)",
    )
    s_pack_install.add_argument(
        "--pack-path",
        default="",
        help="Explicit pack root path containing pack.yml (overrides --pack-id lookup)",
    )
    s_pack_install.add_argument(
        "--target-repo-root",
        default=".",
        help="Target repository root for rendered config files (default: current directory)",
    )
    s_pack_install.add_argument(
        "--orp-repo-root",
        default="",
        help="Optional ORP repo root override (default: current ORP checkout)",
    )
    s_pack_install.add_argument(
        "--include",
        action="append",
        choices=["catalog", "live_compare", "problem857", "governance"],
        default=[],
        help=(
            "Component to install (repeatable). "
            "Default when omitted: catalog + live_compare + problem857."
        ),
    )
    s_pack_install.add_argument(
        "--var",
        action="append",
        default=[],
        help="Extra template variable KEY=VALUE (repeatable)",
    )
    s_pack_install.add_argument(
        "--report",
        default="",
        help="Install report output path (default: <target>/orp.erdos.pack-install-report.md)",
    )
    s_pack_install.add_argument(
        "--strict-deps",
        action="store_true",
        help="Exit non-zero if dependency audit finds missing paths",
    )
    s_pack_install.add_argument(
        "--no-bootstrap",
        dest="bootstrap",
        action="store_false",
        help="Disable starter adapter scaffolding",
    )
    s_pack_install.add_argument(
        "--overwrite-bootstrap",
        action="store_true",
        help="Allow bootstrap to overwrite existing scaffolded files",
    )
    s_pack_install.set_defaults(bootstrap=True)
    s_pack_install.set_defaults(func=cmd_pack_install)

    s_pack_fetch = pack_sub.add_parser(
        "fetch",
        help="Fetch pack repo from git and optionally install into a target repo",
    )
    s_pack_fetch.add_argument("--source", required=True, help="Git URL or local git repo path")
    s_pack_fetch.add_argument(
        "--pack-id",
        default="",
        help="Pack id to select when source repo contains multiple packs",
    )
    s_pack_fetch.add_argument("--ref", default="", help="Optional branch/tag/commit checkout")
    s_pack_fetch.add_argument("--cache-root", default="", help="Local cache root (default: ~/.orp/packs)")
    s_pack_fetch.add_argument("--name", default="", help="Optional cache directory name override")
    s_pack_fetch.add_argument(
        "--install-target",
        default="",
        help="If set, install fetched pack into this target repo root",
    )
    s_pack_fetch.add_argument(
        "--orp-repo-root",
        default="",
        help="Optional ORP repo root override for install step",
    )
    s_pack_fetch.add_argument(
        "--include",
        action="append",
        choices=["catalog", "live_compare", "problem857", "governance"],
        default=[],
        help="Install component to include (repeatable, install mode only)",
    )
    s_pack_fetch.add_argument(
        "--var",
        action="append",
        default=[],
        help="Template variable KEY=VALUE (install mode only, repeatable)",
    )
    s_pack_fetch.add_argument(
        "--report",
        default="",
        help="Install report output path (install mode only)",
    )
    s_pack_fetch.add_argument(
        "--strict-deps",
        action="store_true",
        help="Fail install if dependency audit has missing paths",
    )
    s_pack_fetch.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="Disable starter scaffolding during install",
    )
    s_pack_fetch.add_argument(
        "--overwrite-bootstrap",
        action="store_true",
        help="Allow overwriting starter scaffold files during install",
    )
    s_pack_fetch.set_defaults(func=cmd_pack_fetch)

    s_report = sub.add_parser("report", help="Run report operations")
    report_sub = s_report.add_subparsers(dest="report_cmd", required=True)
    s_report_summary = report_sub.add_parser(
        "summary",
        help="Render one-page markdown summary from RUN.json",
    )
    s_report_summary.add_argument(
        "--run-id",
        default="",
        help="Run id (defaults to last run in orp/state.json)",
    )
    s_report_summary.add_argument(
        "--run-json",
        default="",
        help="Explicit path to RUN.json (absolute or relative to --repo-root)",
    )
    s_report_summary.add_argument(
        "--out",
        default="",
        help="Output markdown path (default: alongside RUN.json as RUN_SUMMARY.md)",
    )
    s_report_summary.add_argument(
        "--print",
        dest="print_stdout",
        action="store_true",
        help="Also print markdown summary to stdout",
    )
    s_report_summary.set_defaults(func=cmd_report_summary)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
