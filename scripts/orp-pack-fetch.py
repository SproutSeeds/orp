#!/usr/bin/env python3
"""Fetch ORP profile packs from git sources into a local cache."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import yaml


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "command failed").strip()
        raise RuntimeError(f"{' '.join(cmd)}: {msg}")


def _safe_slug(source: str) -> str:
    s = source.strip().rstrip("/")
    s = s.split("/")[-1]
    if s.endswith(".git"):
        s = s[:-4]
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s)
    s = s.strip("-._")
    return s or "pack-source"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"yaml root must be object: {path}")
    return payload


def _discover_pack_root(repo_path: Path, pack_id: str) -> tuple[Path, str]:
    candidates: list[tuple[Path, str]] = []

    root_pack = repo_path / "pack.yml"
    if root_pack.exists():
        meta = _load_yaml(root_pack)
        pid = str(meta.get("pack_id", repo_path.name))
        candidates.append((repo_path, pid))

    packs_dir = repo_path / "packs"
    if packs_dir.exists():
        for child in sorted(packs_dir.iterdir()):
            if not child.is_dir():
                continue
            yml = child / "pack.yml"
            if not yml.exists():
                continue
            meta = _load_yaml(yml)
            pid = str(meta.get("pack_id", child.name))
            candidates.append((child, pid))

    if not candidates:
        raise RuntimeError(f"no pack.yml found in repo: {repo_path}")

    if pack_id:
        for root, pid in candidates:
            if pid == pack_id or root.name == pack_id:
                return root, pid
        ids = ", ".join(sorted({pid for _, pid in candidates}))
        raise RuntimeError(f"pack_id not found: {pack_id} (available: {ids})")

    unique = {(str(root), pid) for root, pid in candidates}
    if len(unique) == 1:
        root, pid = candidates[0]
        return root, pid

    ids = ", ".join(sorted({pid for _, pid in candidates}))
    raise RuntimeError(f"multiple packs found; pass --pack-id ({ids})")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fetch ORP profile packs from git")
    p.add_argument("--source", required=True, help="Git URL or local git repo path")
    p.add_argument("--pack-id", default="", help="Pack id to select (required when repo has multiple packs)")
    p.add_argument("--ref", default="", help="Optional branch/tag/commit to checkout")
    p.add_argument(
        "--cache-root",
        default="",
        help="Cache root directory (default: ~/.orp/packs)",
    )
    p.add_argument(
        "--name",
        default="",
        help="Optional cache directory name (default: derived from --source)",
    )
    return p


def main() -> int:
    args = _build_parser().parse_args()

    source = args.source.strip()
    if not source:
        raise RuntimeError("--source cannot be empty")

    if args.cache_root.strip():
        cache_root = Path(args.cache_root).expanduser().resolve()
    else:
        cache_root = (Path.home() / ".orp" / "packs").resolve()
    cache_root.mkdir(parents=True, exist_ok=True)

    repo_name = args.name.strip() or _safe_slug(source)
    repo_path = (cache_root / repo_name).resolve()

    if not repo_path.exists():
        _run(["git", "clone", source, str(repo_path)])
    else:
        _run(["git", "-C", str(repo_path), "fetch", "--all", "--tags", "--prune"])
        # best-effort fast-forward; repo may be detached by design
        subprocess.run(
            ["git", "-C", str(repo_path), "pull", "--ff-only"],
            capture_output=True,
            text=True,
        )

    if args.ref.strip():
        _run(["git", "-C", str(repo_path), "checkout", args.ref.strip()])

    head = subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()

    pack_root, discovered_pack_id = _discover_pack_root(repo_path, args.pack_id.strip())

    print(f"source={source}")
    print(f"cache_root={cache_root}")
    print(f"repo_path={repo_path}")
    print(f"repo_head={head}")
    print(f"pack_id={discovered_pack_id}")
    print(f"pack_path={pack_root}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)

