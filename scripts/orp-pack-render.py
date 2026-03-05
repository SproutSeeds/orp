#!/usr/bin/env python3
"""Render ORP profile-pack templates into concrete config files."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Any

import yaml


VAR_PATTERN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"YAML root must be object: {path}")
    return data


def _parse_kv(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise RuntimeError(f"invalid --var, expected KEY=VALUE: {raw}")
        key, val = raw.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z0-9_]+", key):
            raise RuntimeError(f"invalid variable key: {key}")
        out[key] = val
    return out


def _load_pack(pack_root: Path) -> tuple[Path, dict[str, Any]]:
    pack_yml = pack_root / "pack.yml"
    if not pack_yml.exists():
        raise RuntimeError(f"missing pack metadata: {pack_yml}")
    return pack_yml, _load_yaml(pack_yml)


def _template_info(pack: dict[str, Any], template_id: str) -> dict[str, Any]:
    templates = pack.get("templates")
    if not isinstance(templates, dict):
        raise RuntimeError("pack.yml missing templates object")
    info = templates.get(template_id)
    if not isinstance(info, dict):
        raise RuntimeError(f"template not found: {template_id}")
    return info


def _variables(pack: dict[str, Any], cli_vars: dict[str, str]) -> dict[str, str]:
    spec = pack.get("variables", {})
    if spec is None:
        spec = {}
    if not isinstance(spec, dict):
        raise RuntimeError("pack.yml variables must be an object")

    out: dict[str, str] = {}
    for key, meta in spec.items():
        if not isinstance(key, str) or not isinstance(meta, dict):
            continue
        default = meta.get("default")
        if isinstance(default, str):
            out[key] = default

    out.update(cli_vars)

    missing: list[str] = []
    for key, meta in spec.items():
        if not isinstance(meta, dict):
            continue
        required = bool(meta.get("required", False))
        if required and (key not in out or out[key] == ""):
            missing.append(key)
    if missing:
        raise RuntimeError("missing required variables: " + ", ".join(sorted(missing)))

    return out


def _render_text(text: str, vars_map: dict[str, str]) -> str:
    rendered = text
    for key, value in vars_map.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    unresolved = sorted(set(VAR_PATTERN.findall(rendered)))
    if unresolved:
        raise RuntimeError("unresolved template variables: " + ", ".join(unresolved))
    return rendered


def cmd_list(args: argparse.Namespace) -> int:
    pack_root = Path(args.pack).resolve()
    pack_path, pack = _load_pack(pack_root)
    print(f"pack: {pack.get('pack_id', '(unknown)')} ({pack_path})")
    print(f"description: {pack.get('description', '')}")

    variables = pack.get("variables", {})
    if isinstance(variables, dict) and variables:
        print("\nvariables:")
        for key in sorted(variables):
            meta = variables.get(key, {})
            if not isinstance(meta, dict):
                continue
            req = "required" if bool(meta.get("required", False)) else "optional"
            default = meta.get("default", "")
            default_part = f" default={default}" if isinstance(default, str) and default != "" else ""
            desc = str(meta.get("description", ""))
            print(f"- {key} ({req}{default_part}): {desc}")

    templates = pack.get("templates", {})
    if not isinstance(templates, dict) or not templates:
        print("\ntemplates: (none)")
        return 0

    print("\ntemplates:")
    for tid, info in templates.items():
        if not isinstance(info, dict):
            continue
        print(f"- {tid}")
        print(f"  path: {info.get('path', '')}")
        print(f"  description: {info.get('description', '')}")
        if "output_hint" in info:
            print(f"  output_hint: {info.get('output_hint', '')}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    pack_root = Path(args.pack).resolve()
    _pack_path, pack = _load_pack(pack_root)
    info = _template_info(pack, args.template)

    rel_path = info.get("path")
    if not isinstance(rel_path, str) or rel_path.strip() == "":
        raise RuntimeError(f"template path missing for {args.template}")
    template_path = (pack_root / rel_path).resolve()
    if not template_path.exists():
        raise RuntimeError(f"template file not found: {template_path}")

    cli_vars = _parse_kv(args.var or [])
    vars_map = _variables(pack, cli_vars)

    template_text = template_path.read_text(encoding="utf-8")
    rendered = _render_text(template_text, vars_map)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")

    print(f"rendered template: {args.template}")
    print(f"source: {template_path}")
    print(f"output: {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Render ORP profile-pack templates")
    p.add_argument("--pack", required=True, help="Pack root directory containing pack.yml")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="List pack templates and variables")
    mode.add_argument("--template", help="Template id to render")

    p.add_argument("--var", action="append", default=[], help="Template variable KEY=VALUE (repeatable)")
    p.add_argument("--out", default="", help="Output file path (required for render mode)")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.list:
        return cmd_list(args)
    if args.template:
        if args.out.strip() == "":
            raise RuntimeError("--out is required when rendering a template")
        return cmd_render(args)
    raise RuntimeError("invalid mode")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
