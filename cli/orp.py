#!/usr/bin/env python3
"""ORP CLI.

Public shape:
- home
- about
- discover
- collaborate
- init
- gate run
- packet emit
- erdos sync
- report summary

Advanced/internal:
- pack list
- pack install
- pack fetch

Design goals:
- local-first
- low dependency surface
- deterministic artifact layout
- built-in abilities over heavyweight mode switches
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import html
import json
import os
import platform
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Sequence
import uuid
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest
import xml.etree.ElementTree as ET

RUNNER_LEASE_STALE_SECONDS = 120


def _now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return "run-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=False))


def _tool_version() -> str:
    env_version = os.environ.get("ORP_VERSION", "").strip()
    if env_version:
        return env_version

    package_root_override = os.environ.get("ORP_TOOL_PACKAGE_ROOT", "").strip()
    package_json = (
        Path(package_root_override).expanduser().resolve() / "package.json"
        if package_root_override
        else Path(__file__).resolve().parent.parent / "package.json"
    )
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


def _tool_package_name() -> str:
    env_name = os.environ.get("ORP_PACKAGE_NAME", "").strip()
    if env_name:
        return env_name

    package_root_override = os.environ.get("ORP_TOOL_PACKAGE_ROOT", "").strip()
    package_json = (
        Path(package_root_override).expanduser().resolve() / "package.json"
        if package_root_override
        else Path(__file__).resolve().parent.parent / "package.json"
    )
    if not package_json.exists():
        return "unknown"

    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
    except Exception:
        return "unknown"

    name = payload.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "unknown"


ORP_TOOL_VERSION = _tool_version()
ORP_PACKAGE_NAME = _tool_package_name()
DEFAULT_DISCOVER_PROFILE = "orp.profile.default.json"
DEFAULT_DISCOVER_SCAN_ROOT = "orp/discovery/github"
DEFAULT_HOSTED_BASE_URL = "https://orp.earth"
KERNEL_SCHEMA_VERSION = "1.0.0"
FRONTIER_SCHEMA_VERSION = "1.0.0"
FRONTIER_BANDS = ("exact", "structured", "horizon")
YOUTUBE_SOURCE_SCHEMA_VERSION = "1.0.0"
EXCHANGE_REPORT_SCHEMA_VERSION = "1.0.0"
MAINTENANCE_STATE_SCHEMA_VERSION = "1.0.0"
SCHEDULE_REGISTRY_SCHEMA_VERSION = "1.0.0"
KEYCHAIN_SECRET_REGISTRY_SCHEMA_VERSION = "1.0.0"
YOUTUBE_ANDROID_CLIENT_VERSION = "20.10.38"
YOUTUBE_ANDROID_USER_AGENT = (
    f"com.google.android.youtube/{YOUTUBE_ANDROID_CLIENT_VERSION} (Linux; U; Android 14)"
)
AGENT_MODE_REGISTRY_VERSION = "1.0.0"
AGENT_MODES: list[dict[str, Any]] = [
    {
        "id": "sleek-minimal-progressive",
        "aliases": ["sleak-minimal-progressive", "smp"],
        "label": "Sleek Minimal Progressive",
        "summary": "An optional perspective-shift overlay for fresh thinking, playful movement, and elegant forward motion.",
        "operator_reminder": "Use this when the work feels flat, trapped, overfitted, or too linear. It is a paint color, not a permanent operating system.",
        "activation_phrase": "Clean line, live spark, forward motion.",
        "invocation_style": "Optional. Call it when the user or agent wants a fresh lens, not by obligation.",
        "when_to_use": [
            "When a project feels stuck inside one framing.",
            "When the current answer is competent but lifeless.",
            "When you need to zoom in, step back, or rotate the angle before committing.",
            "When a little playfulness could reveal a better path.",
        ],
        "perspective_shifts": [
            "Go deeper into one seam that may be hiding the real leverage.",
            "Step back top-down and redraw the shape of the whole system.",
            "Zoom out wider and ask what the work connects to beyond the immediate task.",
            "Rotate the angle and inspect the problem from another dimension, audience, or timeframe.",
        ],
        "principles": [
            "Reduce friction before adding ornament.",
            "Keep one surprising move alive long enough to evaluate it honestly.",
            "Let the next step feel inevitable instead of overdesigned.",
            "Favor freshness with structure over chaos with flair.",
        ],
        "ritual": [
            "Sketch three lanes: sleek, playful, progressive.",
            "Subtract one unnecessary element.",
            "Add one tasteful surprise.",
            "Name the next concrete move.",
        ],
        "questions": [
            "What would make this feel lighter without making it bland?",
            "What is one unexpected angle worth trying for five minutes?",
            "What would make the next collaborator smile and move faster?",
            "What trajectory is this already hinting at if we let it breathe?",
            "Do we need to dive deeper here, or pull higher and wider first?",
        ],
        "anti_patterns": [
            "Defaulting to the safest generic pattern too early.",
            "Adding cleverness that hides the next move.",
            "Over-explaining instead of letting the shape carry some meaning.",
            "Treating the mode like a mandatory aesthetic instead of a chosen lens.",
        ],
        "nudge_cards": [
            {
                "title": "Three Lanes",
                "prompt": "Produce one elegant option, one weird option, and one quietly ambitious option before choosing.",
                "twist": "Do not let the first workable answer win by inertia.",
                "release": "A short divergence now can save a long mediocre path later.",
            },
            {
                "title": "Depth Dive",
                "prompt": "Choose one small area that feels glossed over and go a layer deeper before redesigning the whole thing.",
                "twist": "Assume the hidden leverage might be inside the overlooked seam.",
                "release": "Sometimes the right wide move only becomes visible after one honest deep move.",
            },
            {
                "title": "Top-Down Reset",
                "prompt": "Step back and restate the whole shape from above in one clean paragraph or sketch before touching details again.",
                "twist": "Reframe the system, not just the symptoms.",
                "release": "A higher vantage point can make local confusion feel obvious.",
            },
            {
                "title": "Wider Orbit",
                "prompt": "Zoom out and ask what adjacent project, audience, or future state this work actually wants to connect to.",
                "twist": "Look for trajectory, not just local polish.",
                "release": "Freshness often appears when the frame gets larger.",
            },
            {
                "title": "Subtractive Spark",
                "prompt": "Remove one element first, then add one move that feels lightly impossible but still testable.",
                "twist": "Make the surprise structural, not decorative.",
                "release": "Simplicity gets more interesting when it earns its restraint.",
            },
            {
                "title": "Gentle Edge",
                "prompt": "Keep the surface calm, but let one edge suggest a bigger horizon or bolder taste.",
                "twist": "The signal should feel intentional, not loud.",
                "release": "Progressive work often whispers before it becomes obvious.",
            },
            {
                "title": "Playful Constraint",
                "prompt": "Impose a tiny playful rule for the next draft, then see whether it unlocks a better shape.",
                "twist": "Examples: one vivid noun, one unexpected contrast, one generous shortcut.",
                "release": "Constraints can create style when they are chosen with curiosity.",
            },
            {
                "title": "Next-Step Glow",
                "prompt": "Ask what version of this would make the next handoff feel exciting instead of dutiful.",
                "twist": "Optimize for momentum, not maximum explanation.",
                "release": "Good creative work leaves behind a path someone wants to continue.",
            },
        ],
    },
    {
        "id": "ruthless-simplification",
        "aliases": ["clarity-blade", "simplify-hard"],
        "label": "Ruthless Simplification",
        "summary": "An optional clarity overlay for stripping noise, collapsing branches, and finding the shortest honest shape.",
        "operator_reminder": "Use this when the work is swollen, muddy, or overexplained. Cut down to the live core without flattening what matters.",
        "activation_phrase": "Cut noise, keep signal.",
        "invocation_style": "Optional. Call it when complexity is obscuring leverage or momentum.",
        "when_to_use": [
            "When too many moving parts are hiding the actual problem.",
            "When explanation is growing faster than understanding.",
            "When several competing branches should probably collapse into one cleaner path.",
            "When the work needs courage to remove, not courage to add.",
        ],
        "perspective_shifts": [
            "Ask what remains if half the structure disappears.",
            "Find the center of gravity and organize around it.",
            "Prefer one honest path over three defensive variants.",
            "Treat every extra sentence, layer, or feature as guilty until proven useful.",
        ],
        "principles": [
            "Signal deserves breathing room.",
            "One clear move beats five hedged ones.",
            "If a detail does not change the decision, it may not belong yet.",
            "Clarity is not sterility; keep the living edge.",
        ],
        "ritual": [
            "Name the core job in one sentence.",
            "Delete or defer everything that does not serve that job.",
            "Rewrite the surviving shape more plainly.",
            "Check that the cut version is still truthful and humane.",
        ],
        "questions": [
            "What is the real sentence underneath all of this?",
            "If I had to keep only one move, which one would survive?",
            "What is ornamental, defensive, or repetitive here?",
            "What would make this easier to continue tomorrow?",
        ],
        "anti_patterns": [
            "Mistaking bluntness for clarity.",
            "Removing the nuance that actually carries the truth.",
            "Keeping complexity just because effort has already been spent.",
            "Turning a clean structure into an emotionally flat one.",
        ],
        "nudge_cards": [
            {
                "title": "One Sentence Core",
                "prompt": "Restate the real job in one sentence, then delete anything that does not serve it.",
                "twist": "Do not protect a piece just because it took time to make.",
                "release": "A clean center often exposes the right next move immediately.",
            },
            {
                "title": "Half-Cut Test",
                "prompt": "Imagine removing half the structure. What is the smallest version that still tells the truth?",
                "twist": "Let the cut reveal the design, not just shrink it.",
                "release": "Compression can uncover hidden shape.",
            },
            {
                "title": "Branch Collapse",
                "prompt": "Choose the branch with the most honest leverage and collapse the rest into notes or follow-ups.",
                "twist": "Optimization is sometimes a choice, not a comparison table.",
                "release": "Momentum returns when indecision stops pretending to be rigor.",
            },
            {
                "title": "Plain-Language Pass",
                "prompt": "Rewrite the core in language that a sharp outsider could follow in one pass.",
                "twist": "Simplify the thinking, not just the wording.",
                "release": "If it cannot be said plainly yet, it may not be understood cleanly.",
            },
        ],
    },
    {
        "id": "systems-constellation",
        "aliases": ["topout-systems", "wider-systems"],
        "label": "Systems Constellation",
        "summary": "An optional systems-thinking overlay for mapping relationships, constraints, feedback loops, and downstream consequences.",
        "operator_reminder": "Use this when local work feels disconnected from the larger field. Step out of the component and see the pattern of forces around it.",
        "activation_phrase": "See the field, then move.",
        "invocation_style": "Optional. Call it when wider context or top-down structure matters more than local polish.",
        "when_to_use": [
            "When a fix may create second-order effects elsewhere.",
            "When the local task makes sense, but the broader trajectory does not.",
            "When multiple stakeholders, repos, systems, or timescales are involved.",
            "When you need to understand dependencies before changing the center.",
        ],
        "perspective_shifts": [
            "Map upstream causes and downstream consequences.",
            "Look for reinforcing and balancing feedback loops.",
            "Inspect the work across user, operator, system, and time horizons.",
            "Translate the local decision into network effects, maintenance cost, and future optionality.",
        ],
        "principles": [
            "A local optimum can still be a global mistake.",
            "Constraints shape behavior more than intentions do.",
            "Interfaces are often where the truth leaks out.",
            "Good system moves respect time, not just topology.",
        ],
        "ritual": [
            "Name the central node or decision.",
            "List the immediate upstreams and downstreams.",
            "Sketch the likely feedback loops or hidden constraints.",
            "Choose the move that improves the system, not just the local patch.",
        ],
        "questions": [
            "What else changes if this changes?",
            "Where is the real bottleneck: code, policy, attention, trust, or time?",
            "Which actor or subsystem is paying the hidden cost here?",
            "What does this choice optimize three steps from now?",
        ],
        "anti_patterns": [
            "Treating isolated correctness as whole-system health.",
            "Ignoring maintenance or coordination costs because the local win feels neat.",
            "Drawing a giant map without extracting a decision from it.",
            "Confusing complexity theater with actual systems understanding.",
        ],
        "nudge_cards": [
            {
                "title": "Upstream / Downstream",
                "prompt": "Write the immediate upstream causes and downstream effects before changing the local piece.",
                "twist": "At least one consequence should be about coordination or maintenance, not just runtime behavior.",
                "release": "Systems clarity often saves you from elegant local mistakes.",
            },
            {
                "title": "Feedback Loop Check",
                "prompt": "Ask what behavior this choice reinforces over time and what it silently penalizes.",
                "twist": "Think in loops, not one-off events.",
                "release": "The future shape of the system is already hiding inside today's incentives.",
            },
            {
                "title": "Constraint Lens",
                "prompt": "Name the real constraint in one word, then redesign the move around that constraint instead of around preferences.",
                "twist": "If you name the wrong constraint, the plan will stay decorative.",
                "release": "A true constraint simplifies the map fast.",
            },
            {
                "title": "Time Horizon Shift",
                "prompt": "Look at this choice as if you have to maintain it for six months with incomplete context.",
                "twist": "Durability matters as much as local cleverness.",
                "release": "Longer time horizons often reveal the cleaner system move.",
            },
        ],
    },
    {
        "id": "bold-concept-generation",
        "aliases": ["idea-sprinter", "wild-arc"],
        "label": "Bold Concept Generation",
        "summary": "An optional ideation overlay for generating stronger, stranger, and more future-facing directions before they get prematurely domesticated.",
        "operator_reminder": "Use this when you need possibilities, not just polish. Push the edge first, then evaluate what deserves to survive.",
        "activation_phrase": "Push the edge before you prune.",
        "invocation_style": "Optional. Call it when the work needs new directions, bigger bets, or less timid first drafts.",
        "when_to_use": [
            "When the current option set feels too safe or too converged.",
            "When the user wants something memorable rather than merely correct.",
            "When a project needs a new conceptual frame before detailed execution.",
            "When the right answer might require a category jump.",
        ],
        "perspective_shifts": [
            "Jump categories and import a principle from somewhere unexpected.",
            "Generate futures first, then backsolve feasibility.",
            "Treat constraints as design material instead of just fences.",
            "Search for moves that feel slightly unreasonable but still testable.",
        ],
        "principles": [
            "A brave draft can be edited down; a timid draft rarely grows teeth later.",
            "Novelty earns its place by opening real options.",
            "The best big idea usually has one clean handle.",
            "Wildness is useful when it still leaves a trail back to execution.",
        ],
        "ritual": [
            "Generate at least three directions that are meaningfully different, not cosmetically varied.",
            "Keep the boldest one alive long enough to inspect it fairly.",
            "Extract the usable principle even if the whole concept does not survive.",
            "Only then decide what to prune or ground.",
        ],
        "questions": [
            "What would the bolder version of this try first?",
            "If we were not trying to look reasonable immediately, what would we explore?",
            "What adjacent field has already solved an analogous problem more imaginatively?",
            "Which idea here feels alive enough to justify a quick experiment?",
        ],
        "anti_patterns": [
            "Killing the interesting idea before it gets one honest pass.",
            "Confusing loudness with originality.",
            "Generating variations that are basically the same safe answer.",
            "Leaving a big idea too abstract to ever test.",
        ],
        "nudge_cards": [
            {
                "title": "Category Hop",
                "prompt": "Borrow one principle from a totally different field and force it into this problem for ten minutes.",
                "twist": "The goal is not to be right immediately; it is to change the shape of the option space.",
                "release": "A category jump can reveal a route the local vocabulary was hiding.",
            },
            {
                "title": "Impossible but Testable",
                "prompt": "State the version that sounds too ambitious, then reduce it only until it becomes testable instead of impossible.",
                "twist": "Do not sand it down into mediocrity on the first pass.",
                "release": "Some of the best concepts start slightly past the comfort boundary.",
            },
            {
                "title": "Future Artifact",
                "prompt": "Describe the artifact, interface, or experience as if it already exists in its strongest form.",
                "twist": "Backsolve the first believable step afterward.",
                "release": "Future-first thinking can free you from today's cramped assumptions.",
            },
            {
                "title": "Principle Theft",
                "prompt": "Identify one beautiful property you admire elsewhere and redesign this work to inherit that property.",
                "twist": "Copy the principle, not the surface aesthetic.",
                "release": "Transferring a deep property is often more generative than copying a format.",
            },
        ],
    },
]


class HostedApiError(RuntimeError):
    """Raised when the hosted ORP app returns an API error."""


def _agent_mode_map() -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for mode in AGENT_MODES:
        lookup[str(mode["id"]).strip()] = mode
        for alias in mode.get("aliases", []):
            alias_text = str(alias).strip()
            if alias_text:
                lookup[alias_text] = mode
    return lookup


def _agent_mode(mode_ref: str) -> dict[str, Any]:
    ref = str(mode_ref or "").strip()
    if not ref:
        raise RuntimeError("Mode id is required.")
    mode = _agent_mode_map().get(ref)
    if mode is None:
        raise RuntimeError(f"Unknown mode: {ref}")
    return mode


def _agent_mode_public_payload(mode: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(mode.get("id", "")).strip(),
        "aliases": [str(row).strip() for row in mode.get("aliases", []) if str(row).strip()],
        "label": str(mode.get("label", "")).strip(),
        "summary": str(mode.get("summary", "")).strip(),
        "operator_reminder": str(mode.get("operator_reminder", "")).strip(),
        "activation_phrase": str(mode.get("activation_phrase", "")).strip(),
        "invocation_style": str(mode.get("invocation_style", "")).strip(),
        "when_to_use": [str(row).strip() for row in mode.get("when_to_use", []) if str(row).strip()],
        "perspective_shifts": [str(row).strip() for row in mode.get("perspective_shifts", []) if str(row).strip()],
        "principles": [str(row).strip() for row in mode.get("principles", []) if str(row).strip()],
        "ritual": [str(row).strip() for row in mode.get("ritual", []) if str(row).strip()],
        "questions": [str(row).strip() for row in mode.get("questions", []) if str(row).strip()],
        "anti_patterns": [str(row).strip() for row in mode.get("anti_patterns", []) if str(row).strip()],
        "nudge_card_count": len(mode.get("nudge_cards", [])) if isinstance(mode.get("nudge_cards"), list) else 0,
    }


def _agent_mode_seed(seed: str) -> str:
    text = str(seed or "").strip()
    if text:
        return text
    return dt.datetime.now().astimezone().date().isoformat()


def _agent_mode_nudge(mode: dict[str, Any], *, seed: str = "") -> dict[str, Any]:
    cards = mode.get("nudge_cards", [])
    if not isinstance(cards, list) or not cards:
        raise RuntimeError("This mode does not define any nudge cards.")
    effective_seed = _agent_mode_seed(seed)
    digest = hashlib.sha256(f"{mode['id']}::{effective_seed}".encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(cards)
    card = cards[index]
    return {
        "mode": _agent_mode_public_payload(mode),
        "seed": effective_seed,
        "card_index": index,
        "card": {
            "title": str(card.get("title", "")).strip(),
            "prompt": str(card.get("prompt", "")).strip(),
            "twist": str(card.get("twist", "")).strip(),
            "release": str(card.get("release", "")).strip(),
        },
        "micro_loop": [
            "Choose the right lens first: deeper, higher, wider, or rotated.",
            "Make one pass sleeker by removing friction and generic weight.",
            "Make one pass playful or progressive by trying one meaningful shift in angle.",
        ],
    }


def _config_home() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg_config_home:
        return Path(xdg_config_home).expanduser()
    return Path.home() / ".config"


def _orp_user_dir() -> Path:
    return _config_home() / "orp"


def _keychain_secret_registry_path() -> Path:
    return _orp_user_dir() / "secrets-keychain.json"


def _keychain_supported() -> bool:
    return sys.platform == "darwin" or os.environ.get("ORP_KEYCHAIN_ALLOW_NON_DARWIN", "").strip() == "1"


def _ensure_keychain_supported() -> None:
    if not _keychain_supported():
        raise RuntimeError("macOS Keychain integration is only available on macOS.")
    if shutil.which("security") is None:
        raise RuntimeError("The macOS `security` command is not available on PATH.")


def _keychain_registry_template() -> dict[str, Any]:
    return {
        "schema_version": KEYCHAIN_SECRET_REGISTRY_SCHEMA_VERSION,
        "items": [],
    }


def _load_keychain_secret_registry() -> dict[str, Any]:
    path = _keychain_secret_registry_path()
    if not path.exists():
        return _keychain_registry_template()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _keychain_registry_template()
    if not isinstance(payload, dict):
        return _keychain_registry_template()
    items = payload.get("items")
    return {
        "schema_version": str(payload.get("schema_version", KEYCHAIN_SECRET_REGISTRY_SCHEMA_VERSION)).strip()
        or KEYCHAIN_SECRET_REGISTRY_SCHEMA_VERSION,
        "items": [row for row in items if isinstance(row, dict)] if isinstance(items, list) else [],
    }


def _save_keychain_secret_registry(payload: dict[str, Any]) -> None:
    merged = {
        **_keychain_registry_template(),
        **payload,
    }
    _write_json(_keychain_secret_registry_path(), merged)


def _run_keychain_command(args: Sequence[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    _ensure_keychain_supported()
    return subprocess.run(
        ["security", *args],
        capture_output=True,
        text=True,
        input=input_text,
    )


def _tool_package_root() -> Path:
    override = os.environ.get("ORP_TOOL_PACKAGE_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def _launch_runtime_root() -> Path:
    override = os.environ.get("ORP_LAUNCH_RUNTIME_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _orp_user_dir() / "launch-runtime"


def _launch_working_directory() -> Path:
    path = _launch_runtime_root()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _launch_runtime_signature() -> str:
    package_root = _tool_package_root()
    digest = hashlib.sha256()
    sources = [
        package_root / "cli" / "orp.py",
        package_root / "package.json",
    ]
    spec_root = package_root / "spec"
    if spec_root.exists():
        sources.extend(path for path in sorted(spec_root.rglob("*")) if path.is_file())
    for path in sources:
        if not path.exists() or not path.is_file():
            continue
        try:
            relative = path.relative_to(package_root).as_posix()
        except Exception:
            relative = path.name
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


def _copy_launch_runtime_tree(src: Path, dest: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _ensure_launch_runtime_snapshot() -> Path:
    package_root = _tool_package_root()
    snapshot_root = _launch_runtime_root() / _launch_runtime_signature()
    snapshot_cli = snapshot_root / "cli" / "orp.py"
    if snapshot_cli.exists():
        return snapshot_cli

    temp_root = snapshot_root.parent / f".{snapshot_root.name}.tmp-{uuid.uuid4().hex[:8]}"
    if temp_root.exists():
        shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    try:
        for relative in (Path("cli") / "orp.py", Path("package.json"), Path("spec")):
            src = package_root / relative
            if not src.exists():
                continue
            _copy_launch_runtime_tree(src, temp_root / relative)
        metadata = {
            "generated_at": _now_utc(),
            "source_package_root": str(package_root),
            "tool_version": ORP_TOOL_VERSION,
            "package_name": ORP_PACKAGE_NAME,
            "signature": snapshot_root.name,
        }
        _write_json(temp_root / "runtime.json", metadata)
        temp_root.replace(snapshot_root)
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
    return snapshot_cli


def _resolved_orp_binary() -> str:
    override = os.environ.get("ORP_LAUNCH_ORP_BIN", "").strip()
    if override:
        return str(Path(override).expanduser().resolve())
    resolved = shutil.which("orp")
    return str(Path(resolved).resolve()) if resolved else ""


def _launch_program_arguments(*argv: str) -> list[str]:
    if _update_install_kind() == "npm-global":
        orp_bin = _resolved_orp_binary()
        if orp_bin:
            return [orp_bin, *argv]
    snapshot_cli = _ensure_launch_runtime_snapshot()
    return [
        sys.executable,
        str(snapshot_cli),
        *argv,
    ]


def _env_truthy(name: str) -> bool:
    value = str(os.environ.get(name, "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _update_install_kind() -> str:
    override = str(os.environ.get("ORP_UPDATE_INSTALL_KIND", "")).strip().lower()
    if override in {"source-checkout", "npm-global", "unknown"}:
        return override

    package_root = _tool_package_root()
    if (package_root / ".git").exists():
        return "source-checkout"
    return "npm-global"


def _version_key(version: str) -> tuple[int, ...]:
    parts = [int(part) for part in re.findall(r"\d+", str(version))]
    return tuple(parts) if parts else (0,)


def _compare_versions(left: str, right: str) -> int:
    left_key = _version_key(left)
    right_key = _version_key(right)
    width = max(len(left_key), len(right_key))
    padded_left = left_key + (0,) * (width - len(left_key))
    padded_right = right_key + (0,) * (width - len(right_key))
    if padded_left < padded_right:
        return -1
    if padded_left > padded_right:
        return 1
    return 0


def _fetch_latest_npm_version(*, timeout_sec: int = 8) -> tuple[str, str]:
    override = str(os.environ.get("ORP_UPDATE_LATEST_VERSION", "")).strip()
    if override:
        return override, ""

    try:
        proc = subprocess.run(
            ["npm", "view", ORP_PACKAGE_NAME, "version", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except FileNotFoundError:
        return "", "npm not found on PATH."
    except subprocess.TimeoutExpired:
        return "", "Timed out while checking npm for the latest ORP version."
    except Exception as exc:
        return "", f"Unable to check npm for the latest ORP version: {exc}"

    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip() or "npm view returned a non-zero exit status."
        return "", message

    raw = (proc.stdout or "").strip()
    if not raw:
        return "", "npm returned an empty version string."

    try:
        payload = json.loads(raw)
    except Exception:
        payload = raw

    if isinstance(payload, str):
        version = payload.strip()
    elif isinstance(payload, dict):
        version = str(payload.get("version", "")).strip()
    else:
        version = str(payload).strip()

    if not version:
        return "", "Unable to parse the latest ORP version from npm."
    return version, ""


def _recommended_update_command(install_kind: str) -> str:
    if install_kind == "source-checkout":
        return f"git -C {shlex.quote(str(_tool_package_root()))} pull --ff-only"
    return f"npm install -g {ORP_PACKAGE_NAME}@latest"


def _run_text_command(command: Sequence[str], *, cwd: Path | None = None, timeout_sec: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
        timeout=timeout_sec,
    )


def _resolve_git_dir(package_root: Path) -> Path:
    dotgit = package_root / ".git"
    if dotgit.is_dir():
        return dotgit.resolve()
    if dotgit.is_file():
        try:
            first_line = dotgit.read_text(encoding="utf-8").splitlines()[0].strip()
        except Exception:
            return dotgit.resolve()
        if first_line.lower().startswith("gitdir:"):
            raw = first_line.split(":", 1)[1].strip()
            resolved = Path(raw).expanduser()
            if not resolved.is_absolute():
                resolved = (package_root / resolved).resolve()
            return resolved
    return dotgit.resolve()


def _run_git_at(package_root: Path, *args: str, timeout_sec: int = 5) -> subprocess.CompletedProcess[str]:
    git_dir = _resolve_git_dir(package_root)
    return _run_text_command(
        [
            "git",
            f"--git-dir={git_dir}",
            f"--work-tree={package_root}",
            *args,
        ],
        cwd=_launch_working_directory(),
        timeout_sec=timeout_sec,
    )


def _normalize_source_checkout_readiness_error(message: str) -> str:
    clean = str(message or "").strip()
    if not clean:
        return clean
    if (
        os.environ.get("ORP_LAUNCH_RUNTIME_ROOT", "").strip()
        and (
            "Unable to read current working directory" in clean
            or "not a git repository" in clean
        )
    ):
        return (
            "Source checkout auto-update readiness is unavailable from the background launchd runtime "
            "for this checkout. Run `orp update` interactively when you want to update a source checkout."
        )
    return clean


def _source_checkout_update_readiness(package_root: Path) -> dict[str, Any]:
    forced_ready = str(os.environ.get("ORP_UPDATE_SOURCE_READY", "")).strip().lower()
    if forced_ready in {"0", "1", "false", "true", "no", "yes"}:
        ok = forced_ready in {"1", "true", "yes"}
        branch = str(os.environ.get("ORP_UPDATE_SOURCE_BRANCH", "main")).strip() or "main"
        upstream = str(os.environ.get("ORP_UPDATE_SOURCE_UPSTREAM", "origin/main")).strip() or "origin/main"
        reason = str(os.environ.get("ORP_UPDATE_SOURCE_REASON", "")).strip()
        if not reason:
            if ok:
                reason = "Current branch looks safe to fast-forward."
            else:
                reason = "Source checkout is not in a safe auto-pull state."
        return {
            "ok": ok,
            "branch": branch,
            "upstream": upstream,
            "reason": reason,
        }

    try:
        status_proc = _run_git_at(package_root, "status", "--short", timeout_sec=5)
    except FileNotFoundError:
        return {
            "ok": False,
            "branch": "",
            "upstream": "",
            "reason": "git not found on PATH.",
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "branch": "",
            "upstream": "",
            "reason": "Timed out while checking git status for the source checkout.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "branch": "",
            "upstream": "",
            "reason": f"Unable to inspect the source checkout: {exc}",
        }

    if status_proc.returncode != 0:
        message = _normalize_source_checkout_readiness_error(
            (status_proc.stderr or status_proc.stdout or "").strip() or "git status failed."
        )
        return {
            "ok": False,
            "branch": "",
            "upstream": "",
            "reason": message,
        }

    if (status_proc.stdout or "").strip():
        return {
            "ok": False,
            "branch": "",
            "upstream": "",
            "reason": "Source checkout has local changes. Commit or stash them before auto-updating.",
        }

    branch_proc = _run_git_at(package_root, "rev-parse", "--abbrev-ref", "HEAD", timeout_sec=5)
    branch = (branch_proc.stdout or "").strip() if branch_proc.returncode == 0 else ""
    if not branch or branch == "HEAD":
        return {
            "ok": False,
            "branch": branch,
            "upstream": "",
            "reason": "Source checkout is not on a named branch, so ORP will not auto-pull it.",
        }

    upstream_proc = _run_git_at(
        package_root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
        timeout_sec=5,
    )
    upstream = (upstream_proc.stdout or "").strip() if upstream_proc.returncode == 0 else ""
    if not upstream:
        message = _normalize_source_checkout_readiness_error((upstream_proc.stderr or upstream_proc.stdout or "").strip())
        return {
            "ok": False,
            "branch": branch,
            "upstream": "",
            "reason": message or f"Branch '{branch}' has no upstream configured for `git pull --ff-only`.",
        }

    return {
        "ok": True,
        "branch": branch,
        "upstream": upstream,
        "reason": "Current branch looks safe to fast-forward.",
    }


def _update_payload() -> dict[str, Any]:
    install_kind = _update_install_kind()
    package_root = _tool_package_root()
    current_version = ORP_TOOL_VERSION
    latest_version, check_error = _fetch_latest_npm_version()
    source_readiness = _source_checkout_update_readiness(package_root) if install_kind == "source-checkout" else None
    comparison = 0
    if latest_version and current_version != "unknown":
        comparison = _compare_versions(latest_version, current_version)

    if check_error:
        status = "check_failed"
    elif comparison > 0:
        status = "update_available"
    elif comparison < 0:
        status = "ahead_of_published"
    else:
        status = "up_to_date"

    update_available = status == "update_available"
    recommended_command = _recommended_update_command(install_kind) if update_available else ""
    if not update_available:
        can_apply = False
    elif install_kind == "npm-global":
        can_apply = True
    elif install_kind == "source-checkout":
        can_apply = bool(source_readiness and source_readiness.get("ok"))
    else:
        can_apply = False

    notes: list[str] = []
    if install_kind == "source-checkout":
        notes.append("ORP appears to be running from a source checkout.")
        if can_apply:
            notes.append("This checkout looks safe to fast-forward, so `orp update --yes` can run the pull for you.")
        else:
            notes.append("ORP will only auto-pull a source checkout when the worktree is clean and the current branch has an upstream.")
        notes.append("Pull the repo forward first, then rerun your local install or link step if you use one.")
    elif install_kind == "npm-global":
        notes.append("ORP appears to be running from an npm-managed install.")
    else:
        notes.append("ORP could not confidently determine how this install is managed.")

    if status == "ahead_of_published":
        notes.append("This checkout appears newer than the currently published npm release.")
    if check_error:
        notes.append("The update check could not reach npm cleanly.")

    return {
        "ok": not bool(check_error),
        "tool": {
            "name": "orp",
            "package": ORP_PACKAGE_NAME,
            "current_version": current_version,
            "latest_version": latest_version or "",
        },
        "status": status,
        "install_kind": install_kind,
        "package_root": str(package_root),
        "update_available": update_available,
        "can_apply": can_apply,
        "recommended_command": recommended_command,
        "check_error": check_error,
        "source_readiness": source_readiness,
        "notes": notes,
    }


def _apply_update(payload: dict[str, Any]) -> dict[str, Any]:
    forced_apply = str(os.environ.get("ORP_UPDATE_APPLY_OK", "")).strip().lower()
    if forced_apply in {"0", "1", "false", "true", "no", "yes"}:
        ok = forced_apply in {"1", "true", "yes"}
        message = str(os.environ.get("ORP_UPDATE_APPLY_MESSAGE", "")).strip() or (
            "Update command completed." if ok else "Update command failed."
        )
        return {
            "ok": ok,
            "applied": ok,
            "message": message,
            "returncode": 0 if ok else 1,
        }

    if str(payload.get("status", "")).strip() != "update_available":
        return {
            "ok": True,
            "applied": False,
            "message": "ORP is already up to date.",
        }

    install_kind = str(payload.get("install_kind", "")).strip()
    if install_kind == "source-checkout":
        readiness = payload.get("source_readiness") or {}
        if not bool(readiness.get("ok")):
            return {
                "ok": False,
                "applied": False,
                "message": str(readiness.get("reason") or "Source checkout is not in a safe auto-pull state."),
            }

        try:
            proc = subprocess.run(
                ["git", "-C", str(_tool_package_root()), "pull", "--ff-only"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return {
                "ok": False,
                "applied": False,
                "message": "git not found on PATH.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "applied": False,
                "message": f"Unable to run git pull: {exc}",
            }

        return {
            "ok": proc.returncode == 0,
            "applied": proc.returncode == 0,
            "message": (proc.stdout or proc.stderr or "").strip(),
            "returncode": proc.returncode,
        }

    if install_kind != "npm-global":
        return {
            "ok": False,
            "applied": False,
            "message": "Automatic update is only supported for npm-managed installs or safe source checkouts right now.",
        }

    try:
        proc = subprocess.run(
            ["npm", "install", "-g", f"{ORP_PACKAGE_NAME}@latest"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "applied": False,
            "message": "npm not found on PATH.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "applied": False,
            "message": f"Unable to run npm install: {exc}",
        }

    return {
        "ok": proc.returncode == 0,
        "applied": proc.returncode == 0,
        "message": (proc.stdout or proc.stderr or "").strip(),
        "returncode": proc.returncode,
    }


def _render_update_report(payload: dict[str, Any]) -> str:
    tool = payload.get("tool", {}) if isinstance(payload.get("tool"), dict) else {}
    current_version = str(tool.get("current_version", "")).strip() or "unknown"
    latest_version = str(tool.get("latest_version", "")).strip() or "unknown"
    status = str(payload.get("status", "")).strip()
    install_kind = str(payload.get("install_kind", "")).strip() or "unknown"

    status_label = {
        "update_available": "Update available",
        "up_to_date": "Up to date",
        "ahead_of_published": "Ahead of published release",
        "check_failed": "Update check failed",
    }.get(status, status or "Unknown")

    install_label = {
        "source-checkout": "Source checkout",
        "npm-global": "npm-managed install",
        "unknown": "Unknown install type",
    }.get(install_kind, install_kind)

    lines = [
        "ORP Update",
        "",
        f"Current version: {current_version}",
        f"Latest published version: {latest_version}",
        f"Status: {status_label}",
        f"Install type: {install_label}",
    ]

    source_readiness = payload.get("source_readiness")
    if isinstance(source_readiness, dict):
        branch = str(source_readiness.get("branch", "")).strip()
        upstream = str(source_readiness.get("upstream", "")).strip()
        if branch:
            lines.append(f"Branch: {branch}")
        if upstream:
            lines.append(f"Upstream: {upstream}")

    if payload.get("check_error"):
        lines.append(f"Check error: {payload['check_error']}")

    recommended_command = str(payload.get("recommended_command", "")).strip()
    if recommended_command:
        lines.append("")
        lines.append("Recommended next step:")
        lines.append(f"  {recommended_command}")
        if bool(payload.get("can_apply")):
            lines.append("You can let ORP run that for you with `orp update --yes`.")
        elif install_kind == "source-checkout" and isinstance(source_readiness, dict):
            reason = str(source_readiness.get("reason", "")).strip()
            if reason:
                lines.append(f"Auto-apply is blocked right now: {reason}")

    for note in payload.get("notes", []):
        if isinstance(note, str) and note.strip():
            lines.append(f"Note: {note.strip()}")

    apply_payload = payload.get("apply")
    if isinstance(apply_payload, dict):
        lines.append("")
        lines.append("Apply result:")
        lines.append("  Success" if bool(apply_payload.get("ok")) else "  Failed")
        message = str(apply_payload.get("message", "")).strip()
        if message:
            lines.append(f"  {message}")

    return "\n".join(lines)


def _maintenance_state_path() -> Path:
    override = str(os.environ.get("ORP_MAINTENANCE_STATE_PATH", "")).strip()
    if override:
        return Path(override).expanduser()
    return _orp_user_dir() / "maintenance.json"


def _maintenance_label() -> str:
    override = str(os.environ.get("ORP_MAINTENANCE_LABEL", "")).strip()
    return override or "dev.orp.daily-maintenance"


def _maintenance_launch_agents_dir() -> Path:
    override = str(os.environ.get("ORP_MAINTENANCE_LAUNCH_AGENTS_DIR", "")).strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "LaunchAgents"


def _maintenance_plist_path() -> Path:
    return _maintenance_launch_agents_dir() / f"{_maintenance_label()}.plist"


def _maintenance_logs_dir() -> Path:
    override = str(os.environ.get("ORP_MAINTENANCE_LOGS_DIR", "")).strip()
    if override:
        return Path(override).expanduser()
    return _maintenance_state_path().parent / "logs"


def _maintenance_stdout_path() -> Path:
    return _maintenance_logs_dir() / "maintenance.stdout.log"


def _maintenance_stderr_path() -> Path:
    return _maintenance_logs_dir() / "maintenance.stderr.log"


def _maintenance_platform_supported() -> bool:
    return platform.system().strip().lower() == "darwin" or _env_truthy("ORP_MAINTENANCE_ALLOW_NON_DARWIN")


def _maintenance_schedule(hour: int, minute: int) -> dict[str, int]:
    return {
        "Hour": hour,
        "Minute": minute,
    }


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_maintenance_state() -> dict[str, Any]:
    return _read_json_if_exists(_maintenance_state_path())


def _save_maintenance_state(payload: dict[str, Any]) -> Path:
    path = _maintenance_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path


def _maintenance_check_payload(*, source: str) -> dict[str, Any]:
    checked_at = _now_utc()
    update = _update_payload()
    launchd = _maintenance_agent_status()
    state_payload = {
        "schema_version": MAINTENANCE_STATE_SCHEMA_VERSION,
        "checked_at": checked_at,
        "source": source,
        "platform": _runner_platform_name(),
        "update": update,
        "launchd": launchd,
    }
    state_path = _save_maintenance_state(state_payload)
    return {
        "ok": bool(update.get("ok")),
        "checked_at": checked_at,
        "source": source,
        "state_path": str(state_path),
        "update": update,
        "launchd": launchd,
    }


def _maintenance_check_due(checked_at: str, *, max_age_hours: int = 30) -> bool:
    stamp = str(checked_at or "").strip()
    if not stamp:
        return True
    try:
        observed = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except Exception:
        return True
    now = dt.datetime.now(dt.timezone.utc)
    return (now - observed).total_seconds() > max_age_hours * 3600


def _maintenance_program_arguments() -> list[str]:
    return _launch_program_arguments("maintenance", "check", "--json")


def _maintenance_environment_variables() -> dict[str, str]:
    result = {
        "PATH": os.environ.get("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"),
        "ORP_VERSION": ORP_TOOL_VERSION,
        "ORP_PACKAGE_NAME": ORP_PACKAGE_NAME,
        "ORP_TOOL_PACKAGE_ROOT": str(_tool_package_root()),
    }
    for key in (
        "XDG_CONFIG_HOME",
        "ORP_LAUNCH_RUNTIME_ROOT",
        "ORP_LAUNCH_ORP_BIN",
        "ORP_UPDATE_INSTALL_KIND",
        "ORP_UPDATE_LATEST_VERSION",
        "ORP_UPDATE_SOURCE_READY",
        "ORP_UPDATE_SOURCE_BRANCH",
        "ORP_UPDATE_SOURCE_UPSTREAM",
        "ORP_MAINTENANCE_STATE_PATH",
        "ORP_MAINTENANCE_LABEL",
        "ORP_MAINTENANCE_LAUNCH_AGENTS_DIR",
        "ORP_MAINTENANCE_LOGS_DIR",
        "ORP_MAINTENANCE_ALLOW_NON_DARWIN",
    ):
        value = str(os.environ.get(key, "")).strip()
        if value:
            result[key] = value
    return result


def _maintenance_plist_payload(*, hour: int, minute: int) -> dict[str, Any]:
    return {
        "Label": _maintenance_label(),
        "ProgramArguments": _maintenance_program_arguments(),
        "StartCalendarInterval": _maintenance_schedule(hour, minute),
        "RunAtLoad": True,
        "StandardOutPath": str(_maintenance_stdout_path()),
        "StandardErrorPath": str(_maintenance_stderr_path()),
        "WorkingDirectory": str(_launch_working_directory()),
        "EnvironmentVariables": _maintenance_environment_variables(),
    }


def _read_maintenance_plist() -> dict[str, Any]:
    path = _maintenance_plist_path()
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            payload = plistlib.load(handle)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _maintenance_agent_status() -> dict[str, Any]:
    plist_path = _maintenance_plist_path()
    plist_payload = _read_maintenance_plist()
    start_interval = plist_payload.get("StartCalendarInterval", {}) if isinstance(plist_payload, dict) else {}
    state = _load_maintenance_state()
    checked_at = str(state.get("checked_at", "")).strip()
    update = state.get("update", {}) if isinstance(state.get("update"), dict) else {}
    logs = {
        "stdout": str(_maintenance_stdout_path()),
        "stderr": str(_maintenance_stderr_path()),
    }

    return {
        "platform_supported": _maintenance_platform_supported(),
        "label": _maintenance_label(),
        "plist_path": str(plist_path),
        "enabled": plist_path.exists(),
        "schedule": {
            "hour": int(start_interval.get("Hour", 0)) if str(start_interval.get("Hour", "")).strip() else None,
            "minute": int(start_interval.get("Minute", 0)) if str(start_interval.get("Minute", "")).strip() else None,
        },
        "logs": logs,
        "last_checked_at": checked_at,
        "check_due": _maintenance_check_due(checked_at),
        "cached_update_available": bool(update.get("update_available")),
        "cached_latest_version": str((update.get("tool") or {}).get("latest_version", "")).strip()
        if isinstance(update.get("tool"), dict)
        else "",
        "state_path": str(_maintenance_state_path()),
    }


def _maintenance_launchctl_domain() -> str:
    return f"gui/{os.getuid()}"


def _maybe_run_launchctl(args: Sequence[str]) -> tuple[bool, str]:
    if _env_truthy("ORP_MAINTENANCE_SKIP_LAUNCHCTL"):
        return True, "launchctl skipped by ORP_MAINTENANCE_SKIP_LAUNCHCTL"
    try:
        proc = _run_text_command(["launchctl", *args], timeout_sec=10)
    except FileNotFoundError:
        return False, "launchctl not found on PATH."
    except subprocess.TimeoutExpired:
        return False, "Timed out while running launchctl."
    except Exception as exc:
        return False, f"Unable to run launchctl: {exc}"

    output = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode != 0:
        return False, output or f"launchctl {' '.join(args)} failed."
    return True, output


def _enable_maintenance_agent(*, hour: int, minute: int) -> dict[str, Any]:
    if not _maintenance_platform_supported():
        return {
            "ok": False,
            "message": "Maintenance scheduling is only supported on macOS right now.",
        }

    plist_path = _maintenance_plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    _maintenance_logs_dir().mkdir(parents=True, exist_ok=True)
    plist_payload = _maintenance_plist_payload(hour=hour, minute=minute)
    with plist_path.open("wb") as handle:
        plistlib.dump(plist_payload, handle)

    bootout_ok, bootout_message = _maybe_run_launchctl(["bootout", _maintenance_launchctl_domain(), str(plist_path)])
    bootstrap_ok, bootstrap_message = _maybe_run_launchctl(["bootstrap", _maintenance_launchctl_domain(), str(plist_path)])
    enable_ok, enable_message = _maybe_run_launchctl(
        ["enable", f"{_maintenance_launchctl_domain()}/{_maintenance_label()}"]
    )
    kickstart_ok, kickstart_message = _maybe_run_launchctl(
        ["kickstart", "-k", f"{_maintenance_launchctl_domain()}/{_maintenance_label()}"]
    )
    kickstart_soft_ok = (
        not kickstart_ok
        and bootstrap_ok
        and enable_ok
        and "Timed out while running launchctl." in str(kickstart_message)
    )
    overall_ok = bootstrap_ok and enable_ok and (kickstart_ok or kickstart_soft_ok)
    message = "Enabled daily ORP maintenance."
    if kickstart_soft_ok:
        message = "Enabled daily ORP maintenance. Initial launchd run is still in progress."
    elif not overall_ok:
        message = bootstrap_message or enable_message or kickstart_message

    return {
        "ok": overall_ok,
        "plist_path": str(plist_path),
        "schedule": {
            "hour": hour,
            "minute": minute,
        },
        "launchctl": {
            "bootout": {"ok": bootout_ok, "message": bootout_message},
            "bootstrap": {"ok": bootstrap_ok, "message": bootstrap_message},
            "enable": {"ok": enable_ok, "message": enable_message},
            "kickstart": {"ok": kickstart_ok or kickstart_soft_ok, "message": kickstart_message},
        },
        "message": message,
    }


def _disable_maintenance_agent() -> dict[str, Any]:
    plist_path = _maintenance_plist_path()
    status = _maintenance_agent_status()
    if not plist_path.exists():
        return {
            "ok": True,
            "removed": False,
            "message": "Maintenance agent is already disabled.",
            "status": status,
        }

    bootout_ok, bootout_message = _maybe_run_launchctl(["bootout", _maintenance_launchctl_domain(), str(plist_path)])
    try:
        plist_path.unlink()
    except Exception as exc:
        return {
            "ok": False,
            "removed": False,
            "message": f"Unable to remove maintenance plist: {exc}",
            "launchctl": {"bootout": {"ok": bootout_ok, "message": bootout_message}},
        }

    return {
        "ok": True,
        "removed": True,
        "message": "Disabled daily ORP maintenance.",
        "launchctl": {"bootout": {"ok": bootout_ok, "message": bootout_message}},
    }


def _schedule_registry_path() -> Path:
    override = os.environ.get("ORP_SCHEDULE_REGISTRY_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return _orp_user_dir() / "schedules.json"


def _schedule_logs_dir() -> Path:
    override = os.environ.get("ORP_SCHEDULE_LOGS_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return _schedule_registry_path().parent / "schedule-logs"


def _schedule_launch_agents_dir() -> Path:
    override = os.environ.get("ORP_SCHEDULE_LAUNCH_AGENTS_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return _maintenance_launch_agents_dir()


def _schedule_platform_supported() -> bool:
    return platform.system() == "Darwin" or _env_truthy("ORP_SCHEDULE_ALLOW_NON_DARWIN")


def _load_schedule_registry() -> dict[str, Any]:
    payload = _read_json_if_exists(_schedule_registry_path())
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        jobs = []
    normalized_jobs = [job for job in jobs if isinstance(job, dict)]
    return {
        "schema_version": str(payload.get("schema_version", SCHEDULE_REGISTRY_SCHEMA_VERSION)).strip()
        or SCHEDULE_REGISTRY_SCHEMA_VERSION,
        "jobs": normalized_jobs,
    }


def _save_schedule_registry(payload: dict[str, Any]) -> Path:
    path = _schedule_registry_path()
    _write_json(path, payload)
    return path


def _slugify_value(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug or "job"


def _normalize_workspace_title_input(value: Any, *, field_label: str = "--title") -> str:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"{field_label} is required and must use lowercase letters, numbers, and dashes only.")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", text):
        raise RuntimeError(
            f"{field_label} must use lowercase letters, numbers, and single dashes only, like main-cody-1."
        )
    return text


def _validate_schedule_time(hour: int, minute: int) -> None:
    if hour < 0 or hour > 23:
        raise RuntimeError("--hour must be between 0 and 23.")
    if minute < 0 or minute > 59:
        raise RuntimeError("--minute must be between 0 and 59.")


def _schedule_job_label(job: dict[str, Any]) -> str:
    job_id = str(job.get("id", "")).strip() or "job"
    name = str(job.get("name", "")).strip() or job_id
    return f"dev.orp.schedule.{_slugify_value(name)}.{_slugify_value(job_id)[:8]}"


def _schedule_job_plist_path(job: dict[str, Any]) -> Path:
    return _schedule_launch_agents_dir() / f"{_schedule_job_label(job)}.plist"


def _schedule_job_stdout_path(job: dict[str, Any]) -> Path:
    return _schedule_logs_dir() / f"{str(job.get('id', '')).strip() or 'job'}.stdout.log"


def _schedule_job_stderr_path(job: dict[str, Any]) -> Path:
    return _schedule_logs_dir() / f"{str(job.get('id', '')).strip() or 'job'}.stderr.log"


def _read_schedule_job_plist(job: dict[str, Any]) -> dict[str, Any]:
    path = _schedule_job_plist_path(job)
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            payload = plistlib.load(handle)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _schedule_environment_variables() -> dict[str, str]:
    result = {
        "PATH": os.environ.get("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"),
        "ORP_VERSION": ORP_TOOL_VERSION,
        "ORP_PACKAGE_NAME": ORP_PACKAGE_NAME,
        "ORP_TOOL_PACKAGE_ROOT": str(_tool_package_root()),
    }
    for key in (
        "XDG_CONFIG_HOME",
        "CODEX_HOME",
        "CODEX_BIN",
        "ORP_LAUNCH_RUNTIME_ROOT",
        "ORP_LAUNCH_ORP_BIN",
        "ORP_SCHEDULE_REGISTRY_PATH",
        "ORP_SCHEDULE_LAUNCH_AGENTS_DIR",
        "ORP_SCHEDULE_LOGS_DIR",
        "ORP_SCHEDULE_ALLOW_NON_DARWIN",
        "ORP_SCHEDULE_SKIP_LAUNCHCTL",
    ):
        value = str(os.environ.get(key, "")).strip()
        if value:
            result[key] = value
    return result


def _schedule_program_arguments(job: dict[str, Any]) -> list[str]:
    return _launch_program_arguments(
        "schedule",
        "run",
        str(job.get("id", "")).strip(),
        "--json",
    )


def _schedule_job_schedule(job: dict[str, Any]) -> dict[str, int]:
    raw = job.get("schedule", {}) if isinstance(job.get("schedule"), dict) else {}
    hour = int(raw.get("hour", 9))
    minute = int(raw.get("minute", 0))
    _validate_schedule_time(hour, minute)
    return {"hour": hour, "minute": minute}


def _schedule_plist_payload(job: dict[str, Any], *, hour: int, minute: int) -> dict[str, Any]:
    return {
        "Label": _schedule_job_label(job),
        "ProgramArguments": _schedule_program_arguments(job),
        "StartCalendarInterval": _maintenance_schedule(hour, minute),
        "RunAtLoad": False,
        "StandardOutPath": str(_schedule_job_stdout_path(job)),
        "StandardErrorPath": str(_schedule_job_stderr_path(job)),
        "WorkingDirectory": str(_launch_working_directory()),
        "EnvironmentVariables": _schedule_environment_variables(),
    }


def _maybe_run_schedule_launchctl(args: Sequence[str]) -> tuple[bool, str]:
    if _env_truthy("ORP_SCHEDULE_SKIP_LAUNCHCTL"):
        return True, "launchctl skipped by ORP_SCHEDULE_SKIP_LAUNCHCTL"
    return _maybe_run_launchctl(args)


def _schedule_job_runtime_payload(job: dict[str, Any]) -> dict[str, Any]:
    config = job.get("config", {}) if isinstance(job.get("config"), dict) else {}
    plist_path = _schedule_job_plist_path(job)
    plist_payload = _read_schedule_job_plist(job)
    prompt_file = str(config.get("prompt_file", "")).strip()
    prompt_inline = str(config.get("prompt", ""))
    codex_session_id = str(config.get("codex_session_id", "")).strip()
    start_interval = plist_payload.get("StartCalendarInterval", {}) if isinstance(plist_payload, dict) else {}
    stored_schedule = _schedule_job_schedule(job)
    effective_hour = (
        int(start_interval.get("Hour", stored_schedule["hour"]))
        if str(start_interval.get("Hour", "")).strip()
        else stored_schedule["hour"]
    )
    effective_minute = (
        int(start_interval.get("Minute", stored_schedule["minute"]))
        if str(start_interval.get("Minute", "")).strip()
        else stored_schedule["minute"]
    )
    return {
        **job,
        "label": _schedule_job_label(job),
        "enabled": plist_path.exists(),
        "plist_path": str(plist_path),
        "schedule": {"hour": effective_hour, "minute": effective_minute},
        "logs": {
            "stdout": str(_schedule_job_stdout_path(job)),
            "stderr": str(_schedule_job_stderr_path(job)),
        },
        "repo_root": str(config.get("repo_root", "")).strip(),
        "sandbox": str(config.get("sandbox", "read-only")).strip() or "read-only",
        "prompt_file": prompt_file,
        "prompt_source": "file" if prompt_file else "inline",
        "prompt_preview": _summarize_checkpoint_response(prompt_inline) if prompt_inline.strip() else "",
        "codex_session_id": codex_session_id,
        "uses_session_resume": bool(codex_session_id),
    }


def _find_schedule_job_index(registry: dict[str, Any], target: str) -> tuple[int, dict[str, Any]]:
    needle = str(target or "").strip()
    if not needle:
        raise RuntimeError("Schedule target is required.")
    jobs = registry.get("jobs", []) if isinstance(registry.get("jobs"), list) else []
    for index, job in enumerate(jobs):
        if str(job.get("id", "")).strip() == needle:
            return index, job
    for index, job in enumerate(jobs):
        if str(job.get("name", "")).strip() == needle:
            return index, job
    raise RuntimeError(f"Scheduled job not found: {needle}")


def _read_schedule_prompt(job: dict[str, Any]) -> str:
    config = job.get("config", {}) if isinstance(job.get("config"), dict) else {}
    prompt_file = str(config.get("prompt_file", "")).strip()
    if prompt_file:
        path = Path(prompt_file).expanduser()
        if not path.exists():
            raise RuntimeError(f"Prompt file not found for scheduled job: {path}")
        return path.read_text(encoding="utf-8")
    prompt = str(config.get("prompt", ""))
    if not prompt.strip():
        raise RuntimeError("Scheduled Codex job is missing a prompt.")
    return prompt


def _schedule_job_show_payload(job: dict[str, Any]) -> dict[str, Any]:
    payload = _schedule_job_runtime_payload(job)
    prompt_file = str(payload.get("prompt_file", "")).strip()
    payload["prompt_file_exists"] = Path(prompt_file).exists() if prompt_file else False
    try:
        payload["resolved_prompt"] = _read_schedule_prompt(job)
        payload["prompt_error"] = ""
    except RuntimeError as exc:
        payload["resolved_prompt"] = ""
        payload["prompt_error"] = str(exc)
    return payload


def _run_schedule_codex_job(job: dict[str, Any]) -> dict[str, Any]:
    config = job.get("config", {}) if isinstance(job.get("config"), dict) else {}
    repo_root = Path(str(config.get("repo_root", "")).strip() or ".").expanduser().resolve()
    if not repo_root.exists():
        raise RuntimeError(f"Scheduled job repo root does not exist: {repo_root}")

    prompt = _read_schedule_prompt(job)
    output_path = Path(tempfile.gettempdir()) / f"orp-schedule-response-{str(job.get('id', 'job')).strip() or 'job'}.txt"
    codex_bin = str(config.get("codex_bin", "")).strip() or os.environ.get("CODEX_BIN", "").strip() or "codex"
    sandbox = str(config.get("sandbox", "read-only")).strip() or "read-only"
    codex_session_id = str(config.get("codex_session_id", "")).strip()
    if codex_session_id:
        cmd = [
            codex_bin,
            "exec",
            "resume",
            "--skip-git-repo-check",
            "--output-last-message",
            str(output_path),
            codex_session_id,
            "-",
        ]
    else:
        cmd = [
            codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--output-last-message",
            str(output_path),
            "--sandbox",
            sandbox,
            "-c",
            "approval_policy=never",
            "-",
        ]
    env = dict(os.environ)
    profile = str(config.get("codex_config_profile", "")).strip()
    if profile:
        env["CODEX_PROFILE"] = profile

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            input=prompt,
            capture_output=True,
            text=True,
            env=env,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "exitCode": 127,
            "stdout": "",
            "stderr": f"{codex_bin} not found on PATH.",
            "body": "",
            "summary": f"{codex_bin} not found on PATH.",
            "command": " ".join(cmd),
        }
    except Exception as exc:
        return {
            "ok": False,
            "exitCode": 1,
            "stdout": "",
            "stderr": str(exc),
            "body": "",
            "summary": f"Unable to run scheduled Codex job: {exc}",
            "command": " ".join(cmd),
        }

    body = ""
    if output_path.exists():
        try:
            body = output_path.read_text(encoding="utf-8")
        finally:
            try:
                output_path.unlink()
            except Exception:
                pass
    if not body:
        body = proc.stdout or proc.stderr or ""

    return {
        "ok": proc.returncode == 0,
        "exitCode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "body": body,
        "summary": _summarize_checkpoint_response(body),
        "command": " ".join(cmd),
        "uses_session_resume": bool(codex_session_id),
        "codex_session_id": codex_session_id,
    }


def _record_schedule_run_result(job_id: str, run_payload: dict[str, Any]) -> dict[str, Any]:
    registry = _load_schedule_registry()
    index, job = _find_schedule_job_index(registry, job_id)
    updated_job = dict(job)
    updated_job["updated_at"] = _now_utc()
    updated_job["last_run"] = run_payload
    registry["jobs"][index] = updated_job
    _save_schedule_registry(registry)
    return updated_job


def _create_schedule_codex_job(args: argparse.Namespace) -> dict[str, Any]:
    prompt = str(getattr(args, "prompt", "")).strip()
    prompt_file = str(getattr(args, "prompt_file", "")).strip()
    if bool(prompt) == bool(prompt_file):
        raise RuntimeError("Provide exactly one of --prompt or --prompt-file.")

    name = str(getattr(args, "name", "")).strip()
    if not name:
        raise RuntimeError("--name is required.")

    repo_root = Path(str(getattr(args, "repo_root", "")).strip() or str(Path.cwd())).expanduser().resolve()
    hour = int(getattr(args, "hour", 9))
    minute = int(getattr(args, "minute", 0))
    _validate_schedule_time(hour, minute)

    registry = _load_schedule_registry()
    existing_names = {str(job.get("name", "")).strip() for job in registry.get("jobs", []) if isinstance(job, dict)}
    if name in existing_names:
        raise RuntimeError(f"A scheduled job named '{name}' already exists.")

    job = {
        "id": "sched-" + uuid.uuid4().hex[:12],
        "name": name,
        "kind": "codex",
        "created_at": _now_utc(),
        "updated_at": _now_utc(),
        "schedule": {"hour": hour, "minute": minute},
        "config": {
            "repo_root": str(repo_root),
            "prompt": prompt,
            "prompt_file": str(Path(prompt_file).expanduser().resolve()) if prompt_file else "",
            "sandbox": str(getattr(args, "sandbox", "read-only")).strip() or "read-only",
            "codex_bin": str(getattr(args, "codex_bin", "")).strip(),
            "codex_config_profile": str(getattr(args, "codex_config_profile", "")).strip(),
            "codex_session_id": str(getattr(args, "codex_session_id", "")).strip(),
        },
        "last_run": {},
    }
    registry["jobs"].append(job)
    path = _save_schedule_registry(registry)
    payload = _schedule_job_runtime_payload(job)
    payload["registry_path"] = str(path)
    return payload


def _list_schedule_jobs_payload() -> dict[str, Any]:
    registry = _load_schedule_registry()
    jobs = [_schedule_job_runtime_payload(job) for job in registry.get("jobs", []) if isinstance(job, dict)]
    jobs.sort(key=lambda row: (str(row.get("name", "")).lower(), str(row.get("id", "")).lower()))
    return {
        "registry_path": str(_schedule_registry_path()),
        "jobs": jobs,
    }


def _show_schedule_job_payload(target: str) -> dict[str, Any]:
    registry = _load_schedule_registry()
    _, job = _find_schedule_job_index(registry, target)
    payload = _schedule_job_show_payload(job)
    payload["registry_path"] = str(_schedule_registry_path())
    return payload


def _enable_schedule_job(job: dict[str, Any], *, hour: int | None = None, minute: int | None = None) -> dict[str, Any]:
    if not _schedule_platform_supported():
        return {
            "ok": False,
            "message": "Scheduled jobs are only supported on macOS right now.",
        }

    stored_schedule = _schedule_job_schedule(job)
    effective_hour = stored_schedule["hour"] if hour is None else hour
    effective_minute = stored_schedule["minute"] if minute is None else minute
    _validate_schedule_time(effective_hour, effective_minute)

    plist_path = _schedule_job_plist_path(job)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    _schedule_logs_dir().mkdir(parents=True, exist_ok=True)
    plist_payload = _schedule_plist_payload(job, hour=effective_hour, minute=effective_minute)
    with plist_path.open("wb") as handle:
        plistlib.dump(plist_payload, handle)

    bootout_ok, bootout_message = _maybe_run_schedule_launchctl(
        ["bootout", _maintenance_launchctl_domain(), str(plist_path)]
    )
    bootstrap_ok, bootstrap_message = _maybe_run_schedule_launchctl(
        ["bootstrap", _maintenance_launchctl_domain(), str(plist_path)]
    )
    enable_ok, enable_message = _maybe_run_schedule_launchctl(
        ["enable", f"{_maintenance_launchctl_domain()}/{_schedule_job_label(job)}"]
    )

    registry = _load_schedule_registry()
    index, stored_job = _find_schedule_job_index(registry, str(job.get("id", "")).strip())
    updated_job = dict(stored_job)
    updated_job["schedule"] = {"hour": effective_hour, "minute": effective_minute}
    updated_job["updated_at"] = _now_utc()
    registry["jobs"][index] = updated_job
    _save_schedule_registry(registry)

    return {
        "ok": bootstrap_ok and enable_ok,
        "job": _schedule_job_runtime_payload(updated_job),
        "launchctl": {
            "bootout": {"ok": bootout_ok, "message": bootout_message},
            "bootstrap": {"ok": bootstrap_ok, "message": bootstrap_message},
            "enable": {"ok": enable_ok, "message": enable_message},
        },
        "message": "Enabled scheduled job." if (bootstrap_ok and enable_ok) else bootstrap_message or enable_message,
    }


def _disable_schedule_job(job: dict[str, Any]) -> dict[str, Any]:
    plist_path = _schedule_job_plist_path(job)
    if not plist_path.exists():
        return {
            "ok": True,
            "removed": False,
            "job": _schedule_job_runtime_payload(job),
            "message": "Scheduled job is already disabled.",
        }

    bootout_ok, bootout_message = _maybe_run_schedule_launchctl(
        ["bootout", _maintenance_launchctl_domain(), str(plist_path)]
    )
    try:
        plist_path.unlink()
    except Exception as exc:
        return {
            "ok": False,
            "removed": False,
            "job": _schedule_job_runtime_payload(job),
            "message": f"Unable to remove scheduled job plist: {exc}",
            "launchctl": {"bootout": {"ok": bootout_ok, "message": bootout_message}},
        }

    return {
        "ok": True,
        "removed": True,
        "job": _schedule_job_runtime_payload(job),
        "message": "Disabled scheduled job.",
        "launchctl": {"bootout": {"ok": bootout_ok, "message": bootout_message}},
    }


def _run_schedule_job_once(job: dict[str, Any]) -> dict[str, Any]:
    started_at = _now_utc()
    result = _run_schedule_codex_job(job)
    finished_at = _now_utc()
    run_payload = {
        "started_at": started_at,
        "finished_at": finished_at,
        "ok": bool(result.get("ok")),
        "exit_code": int(result.get("exitCode", 0)),
        "summary": str(result.get("summary", "")).strip(),
    }
    updated_job = _record_schedule_run_result(str(job.get("id", "")).strip(), run_payload)
    return {
        "ok": bool(result.get("ok")),
        "job": _schedule_job_runtime_payload(updated_job),
        "run": result,
    }


def _render_schedule_add_report(payload: dict[str, Any]) -> str:
    schedule = payload.get("schedule", {}) if isinstance(payload.get("schedule"), dict) else {}
    lines = [
        "ORP Scheduled Job Created",
        "",
        f"Name: {payload.get('name', '')}",
        f"Job id: {payload.get('id', '')}",
        f"Kind: {payload.get('kind', '')}",
        f"Repo: {payload.get('repo_root', '')}",
        f"Schedule: daily at {int(schedule.get('hour', 0)):02d}:{int(schedule.get('minute', 0)):02d}",
        f"Prompt source: {payload.get('prompt_source', '')}",
        f"Codex session id: {payload.get('codex_session_id', '') or 'none'}",
        f"Registry: {payload.get('registry_path', '')}",
        "",
        "Next steps:",
        f"  orp schedule show {payload.get('name', '')}",
        f"  orp schedule run {payload.get('name', '')}",
        f"  orp schedule enable {payload.get('name', '')}",
    ]
    return "\n".join(lines)


def _render_schedule_list_report(payload: dict[str, Any]) -> str:
    jobs = payload.get("jobs", []) if isinstance(payload.get("jobs"), list) else []
    if not jobs:
        return "No local scheduled jobs are configured."
    lines = [
        "ORP Scheduled Jobs",
        "",
        f"Registry: {payload.get('registry_path', '')}",
    ]
    for job in jobs:
        schedule = job.get("schedule", {}) if isinstance(job.get("schedule"), dict) else {}
        lines.extend(
            [
                "",
                f"- {job.get('name', '')} ({job.get('id', '')})",
                f"  kind: {job.get('kind', '')}",
                f"  enabled: {'yes' if job.get('enabled') else 'no'}",
                f"  repo: {job.get('repo_root', '')}",
                f"  schedule: {int(schedule.get('hour', 0)):02d}:{int(schedule.get('minute', 0)):02d}",
                f"  prompt: {job.get('prompt_source', 'inline')}",
                f"  codex session: {job.get('codex_session_id', '') or 'none'}",
            ]
        )
        last_run = job.get("last_run", {}) if isinstance(job.get("last_run"), dict) else {}
        if last_run:
            lines.append(
                f"  last run: {last_run.get('finished_at', '') or last_run.get('started_at', '')} ({'ok' if last_run.get('ok') else 'failed'})"
            )
    return "\n".join(lines)


def _render_schedule_show_report(payload: dict[str, Any]) -> str:
    schedule = payload.get("schedule", {}) if isinstance(payload.get("schedule"), dict) else {}
    lines = [
        "ORP Scheduled Job",
        "",
        f"Name: {payload.get('name', '')}",
        f"Job id: {payload.get('id', '')}",
        f"Kind: {payload.get('kind', '')}",
        f"Enabled: {'yes' if payload.get('enabled') else 'no'}",
        f"Repo: {payload.get('repo_root', '')}",
        f"Schedule: daily at {int(schedule.get('hour', 0)):02d}:{int(schedule.get('minute', 0)):02d}",
        f"Prompt source: {payload.get('prompt_source', '')}",
        f"Prompt file: {payload.get('prompt_file', '') or 'none'}",
        f"Codex session id: {payload.get('codex_session_id', '') or 'none'}",
        f"Registry: {payload.get('registry_path', '')}",
    ]
    prompt_error = str(payload.get("prompt_error", "")).strip()
    if prompt_error:
        lines.append(f"Prompt error: {prompt_error}")
    prompt = str(payload.get("resolved_prompt", "")).strip()
    if prompt:
        lines.extend(["", "Prompt:", prompt])
    return "\n".join(lines)


def _render_schedule_run_report(payload: dict[str, Any]) -> str:
    job = payload.get("job", {}) if isinstance(payload.get("job"), dict) else {}
    run = payload.get("run", {}) if isinstance(payload.get("run"), dict) else {}
    lines = [
        "ORP Scheduled Job Run",
        "",
        f"Name: {job.get('name', '')}",
        f"Job id: {job.get('id', '')}",
        f"Status: {'ok' if payload.get('ok') else 'failed'}",
        f"Command: {run.get('command', '')}",
    ]
    summary = str(run.get("summary", "")).strip()
    if summary:
        lines.append(f"Summary: {summary}")
    return "\n".join(lines)


def _render_schedule_enable_report(payload: dict[str, Any]) -> str:
    job = payload.get("job", {}) if isinstance(payload.get("job"), dict) else {}
    schedule = job.get("schedule", {}) if isinstance(job.get("schedule"), dict) else {}
    lines = [
        "ORP Scheduled Job Enabled",
        "",
        f"Name: {job.get('name', '')}",
        f"Job id: {job.get('id', '')}",
        f"Schedule: daily at {int(schedule.get('hour', 0)):02d}:{int(schedule.get('minute', 0)):02d}",
        f"Plist: {job.get('plist_path', '')}",
        f"Message: {payload.get('message', '')}",
    ]
    return "\n".join(lines)


def _render_schedule_disable_report(payload: dict[str, Any]) -> str:
    job = payload.get("job", {}) if isinstance(payload.get("job"), dict) else {}
    lines = [
        "ORP Scheduled Job Disabled",
        "",
        f"Name: {job.get('name', '')}",
        f"Job id: {job.get('id', '')}",
        f"Message: {payload.get('message', '')}",
    ]
    return "\n".join(lines)


def _render_maintenance_check_report(payload: dict[str, Any]) -> str:
    update = payload.get("update", {}) if isinstance(payload.get("update"), dict) else {}
    launchd = payload.get("launchd", {}) if isinstance(payload.get("launchd"), dict) else {}
    tool = update.get("tool", {}) if isinstance(update.get("tool"), dict) else {}
    lines = [
        "ORP Maintenance Check",
        "",
        f"Checked at: {payload.get('checked_at', '')}",
        f"Current version: {tool.get('current_version', 'unknown')}",
        f"Latest published version: {tool.get('latest_version', 'unknown')}",
        f"Update status: {str(update.get('status', 'unknown')).replace('_', ' ')}",
        f"State file: {payload.get('state_path', '')}",
    ]
    if launchd.get("enabled"):
        schedule = launchd.get("schedule", {}) if isinstance(launchd.get("schedule"), dict) else {}
        lines.append(
            f"Daily maintenance: enabled at {int(schedule.get('hour', 0)):02d}:{int(schedule.get('minute', 0)):02d}"
        )
    else:
        lines.append("Daily maintenance: not enabled")
        lines.append("Recommended next step: orp maintenance enable --json")
    if update.get("update_available"):
        lines.append(f"Recommended update: {update.get('recommended_command', '')}")
    return "\n".join(lines)


def _render_maintenance_status_report(payload: dict[str, Any]) -> str:
    lines = [
        "ORP Maintenance Status",
        "",
        f"Platform supported: {'yes' if payload.get('platform_supported') else 'no'}",
        f"Enabled: {'yes' if payload.get('enabled') else 'no'}",
        f"Label: {payload.get('label', '')}",
        f"LaunchAgent: {payload.get('plist_path', '')}",
        f"State file: {payload.get('state_path', '')}",
        f"Last checked at: {payload.get('last_checked_at', '') or 'never'}",
        f"Check due: {'yes' if payload.get('check_due') else 'no'}",
    ]
    schedule = payload.get("schedule", {}) if isinstance(payload.get("schedule"), dict) else {}
    if schedule.get("hour") is not None and schedule.get("minute") is not None:
        lines.append(f"Schedule: daily at {int(schedule['hour']):02d}:{int(schedule['minute']):02d}")
    if payload.get("cached_update_available"):
        lines.append(f"Cached update available: yes ({payload.get('cached_latest_version', '')})")
    else:
        lines.append("Cached update available: no")
    return "\n".join(lines)


def _render_maintenance_enable_report(payload: dict[str, Any]) -> str:
    lines = [
        "ORP Maintenance Enable",
        "",
        payload.get("message", ""),
        f"LaunchAgent: {payload.get('plist_path', '')}",
    ]
    schedule = payload.get("schedule", {}) if isinstance(payload.get("schedule"), dict) else {}
    if schedule.get("hour") is not None and schedule.get("minute") is not None:
        lines.append(f"Schedule: daily at {int(schedule['hour']):02d}:{int(schedule['minute']):02d}")
    return "\n".join([line for line in lines if line])


def _render_maintenance_disable_report(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "ORP Maintenance Disable",
            "",
            str(payload.get("message", "")).strip(),
        ]
    ).strip()


def _hosted_session_path() -> Path:
    return _orp_user_dir() / "remote-session.json"


def _hosted_session_template() -> dict[str, Any]:
    return {
        "base_url": "",
        "email": "",
        "token": "",
        "user": None,
        "pending_verification": None,
    }


def _load_hosted_session() -> dict[str, Any]:
    path = _hosted_session_path()
    if not path.exists():
        return _hosted_session_template()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _hosted_session_template()
    if not isinstance(payload, dict):
        return _hosted_session_template()
    return {
        **_hosted_session_template(),
        **payload,
    }


def _save_hosted_session(payload: dict[str, Any]) -> None:
    merged = {
        **_hosted_session_template(),
        **payload,
    }
    _write_json(_hosted_session_path(), merged)


def _normalize_base_url(raw: str) -> str:
    return str(raw or "").strip().rstrip("/")


def _default_hosted_base_url() -> str:
    for key in ("ORP_BASE_URL", "CODA_BASE_URL"):
        value = _normalize_base_url(os.environ.get(key, ""))
        if value:
            return value
    return DEFAULT_HOSTED_BASE_URL


def _resolve_hosted_base_url(
    args: argparse.Namespace | None,
    session: dict[str, Any] | None = None,
) -> str:
    explicit = _normalize_base_url(getattr(args, "base_url", "") if args is not None else "")
    if explicit:
        return explicit
    prior = _normalize_base_url((session or {}).get("base_url", ""))
    if prior:
        return prior
    return _default_hosted_base_url()


def _get_bypass_token() -> str:
    for key in ("ORP_VERCEL_BYPASS_TOKEN", "CODA_VERCEL_BYPASS_TOKEN", "VERCEL_AUTOMATION_BYPASS_SECRET"):
        value = str(os.environ.get(key, "")).strip()
        if value:
            return value
    return ""


def _read_json_safe(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        text = raw.decode("utf-8", errors="replace").strip()
        return {"error": text} if text else {}
    if isinstance(payload, dict):
        return payload
    return {"payload": payload}


def _hosted_api_error(
    *,
    base_url: str,
    path: str,
    method: str,
    status: int,
    payload: dict[str, Any] | None,
) -> HostedApiError:
    message = str((payload or {}).get("error") or (payload or {}).get("message") or f"Request failed: {status}")
    suffix = f" (status={status} path={path})"
    hint = ""
    if status == 401:
        hint = " Run `orp auth login` and `orp auth verify` again to refresh the hosted session."
    elif status == 403:
        hint = " The hosted ORP app rejected the operation. Check permissions on the target record."
    elif status == 404:
        hint = " The hosted record may have changed. Re-list the resource and retry."
    elif status == 409:
        hint = " The hosted record changed since you last fetched it. Re-open it and retry the update."
    return HostedApiError(f"{message}{suffix}.{hint}".replace("..", "."))


def _request_hosted_json(
    *,
    base_url: str,
    path: str,
    method: str = "GET",
    token: str = "",
    body: dict[str, Any] | None = None,
    timeout_sec: int = 30,
) -> dict[str, Any]:
    url = _normalize_base_url(base_url) + path
    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    bypass_token = _get_bypass_token()
    if bypass_token:
        headers["x-vercel-protection-bypass"] = bypass_token
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urlrequest.Request(url, data=data, headers=headers, method=method)
    try:
        with urlrequest.urlopen(request, timeout=timeout_sec) as response:
            payload = _read_json_safe(response.read())
            return payload
    except urlerror.HTTPError as exc:
        payload = _read_json_safe(exc.read())
        raise _hosted_api_error(
            base_url=base_url,
            path=path,
            method=method,
            status=int(exc.code),
            payload=payload,
        ) from exc
    except urlerror.URLError as exc:
        raise HostedApiError(
            f"Could not reach hosted ORP app at {_normalize_base_url(base_url)}{path}: {exc.reason}"
        ) from exc


def _request_hosted_sse_event(
    *,
    base_url: str,
    path: str,
    token: str = "",
    timeout_sec: int = 45,
) -> dict[str, Any]:
    url = _normalize_base_url(base_url) + path
    headers = {
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    bypass_token = _get_bypass_token()
    if bypass_token:
        headers["x-vercel-protection-bypass"] = bypass_token
    request = urlrequest.Request(url, headers=headers, method="GET")
    event_name = "message"
    data_lines: list[str] = []
    try:
        with urlrequest.urlopen(request, timeout=timeout_sec) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not line:
                    if data_lines:
                        payload = _read_json_safe("\n".join(data_lines).encode("utf-8"))
                        terminal_event = {
                            "event": event_name or "message",
                            "data": payload,
                        }
                        if terminal_event["event"] in {"job.available", "timeout", "error"}:
                            return terminal_event
                    event_name = "message"
                    data_lines = []
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event_name = line.partition(":")[2].strip() or "message"
                    continue
                if line.startswith("data:"):
                    data_lines.append(line.partition(":")[2].lstrip())
                    continue
        raise HostedApiError(
            f"Hosted runner event stream ended before delivering a terminal event (path={path})."
        )
    except urlerror.HTTPError as exc:
        payload = _read_json_safe(exc.read())
        raise _hosted_api_error(
            base_url=base_url,
            path=path,
            method="GET",
            status=int(exc.code),
            payload=payload,
        ) from exc
    except urlerror.URLError as exc:
        raise HostedApiError(
            f"Could not reach hosted ORP app at {_normalize_base_url(base_url)}{path}: {exc.reason}"
        ) from exc


def _http_get_text(url: str, *, headers: dict[str, str] | None = None, timeout_sec: int = 20) -> str:
    request = urlrequest.Request(url, headers=headers or {}, method="GET")
    try:
        with urlrequest.urlopen(request, timeout=timeout_sec) as response:
            return response.read().decode("utf-8", errors="replace")
    except urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"HTTP {exc.code} while fetching {url}: {body or exc.reason}") from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc


def _http_get_json(url: str, *, headers: dict[str, str] | None = None, timeout_sec: int = 20) -> dict[str, Any]:
    text = _http_get_text(url, headers=headers, timeout_sec=timeout_sec)
    try:
        payload = json.loads(text)
    except Exception as exc:
        raise RuntimeError(f"Response from {url} was not valid JSON.") from exc
    if isinstance(payload, dict):
        return payload
    raise RuntimeError(f"Response from {url} was not a JSON object.")


def _http_post_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout_sec: int = 20,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    request = urlrequest.Request(url, data=body, headers=merged_headers, method="POST")
    try:
        with urlrequest.urlopen(request, timeout=timeout_sec) as response:
            text = response.read().decode("utf-8", errors="replace")
    except urlerror.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"HTTP {exc.code} while fetching {url}: {body_text or exc.reason}") from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f"Could not reach {url}: {exc.reason}") from exc
    try:
        parsed = json.loads(text)
    except Exception as exc:
        raise RuntimeError(f"Response from {url} was not valid JSON.") from exc
    if isinstance(parsed, dict):
        return parsed
    raise RuntimeError(f"Response from {url} was not a JSON object.")


def _youtube_request_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }


def _youtube_android_request_headers() -> dict[str, str]:
    return {
        "User-Agent": YOUTUBE_ANDROID_USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
    }


def _youtube_source_schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "spec" / "v1" / "youtube-source.schema.json"


def _youtube_video_id_from_url(raw_url: str) -> str:
    text = str(raw_url or "").strip()
    if not text:
        raise RuntimeError("YouTube URL is required.")
    if re.fullmatch(r"[\w-]{11}", text):
        return text

    parsed = urlparse.urlparse(text)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    if host.endswith("youtu.be"):
        if path_parts:
            return path_parts[0]
    if any(host.endswith(suffix) for suffix in ("youtube.com", "youtube-nocookie.com", "music.youtube.com")):
        if parsed.path == "/watch":
            video_id = urlparse.parse_qs(parsed.query).get("v", [""])[0].strip()
            if video_id:
                return video_id
        if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live", "v"}:
            return path_parts[1]
    raise RuntimeError(f"Could not extract a YouTube video id from: {text}")


def _youtube_canonical_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _extract_json_object_after_marker(text: str, marker: str) -> dict[str, Any] | None:
    index = text.find(marker)
    if index < 0:
        return None
    start = text.find("{", index)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for pos in range(start, len(text)):
        ch = text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : pos + 1]
                try:
                    payload = json.loads(candidate)
                except Exception:
                    return None
                return payload if isinstance(payload, dict) else None
    return None


def _youtube_track_label(track: dict[str, Any]) -> str:
    name = track.get("name")
    if isinstance(name, dict):
        simple = str(name.get("simpleText", "")).strip()
        if simple:
            return simple
        runs = name.get("runs")
        if isinstance(runs, list):
            pieces = [
                str(row.get("text", "")).strip()
                for row in runs
                if isinstance(row, dict) and str(row.get("text", "")).strip()
            ]
            if pieces:
                return "".join(pieces)
    return str(track.get("languageCode", "")).strip()


def _youtube_track_source(track: dict[str, Any]) -> str:
    return str(track.get("_orp_source", "") or "unknown").strip()


def _youtube_track_inventory(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for track in tracks:
        if not isinstance(track, dict):
            continue
        language_code = str(track.get("languageCode", "")).strip()
        label = _youtube_track_label(track)
        kind = "auto" if str(track.get("kind", "")).strip().lower() == "asr" else "manual"
        source = _youtube_track_source(track)
        key = (language_code, label, kind, source)
        if key in seen:
            continue
        seen.add(key)
        inventory.append(
            {
                "language_code": language_code,
                "name": label,
                "kind": kind,
                "source": source,
            }
        )
    return inventory


def _youtube_caption_track_sort_key(track: dict[str, Any], preferred_lang: str = "") -> tuple[int, int]:
    preferred = str(preferred_lang or "").strip().lower()
    code = str(track.get("languageCode", "")).strip().lower()
    kind = str(track.get("kind", "")).strip().lower()
    auto = 1 if kind == "asr" else 0
    source = _youtube_track_source(track)
    source_bias = 15 if source == "android_player" else 0
    exact = 1 if preferred and code == preferred else 0
    prefix = 1 if preferred and code.startswith(preferred + "-") else 0
    english = 1 if code.startswith("en") else 0
    return (exact * 100 + prefix * 80 + english * 20 + source_bias - auto * 5, -auto)


def _pick_youtube_caption_track(tracks: list[dict[str, Any]], preferred_lang: str = "") -> dict[str, Any] | None:
    if not tracks:
        return None
    ranked = sorted(tracks, key=lambda track: _youtube_caption_track_sort_key(track, preferred_lang), reverse=True)
    return ranked[0] if ranked else None


def _youtube_add_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse.urlsplit(url)
    query = dict(urlparse.parse_qsl(parsed.query, keep_blank_values=True))
    query[key] = value
    return urlparse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlparse.urlencode(query),
            parsed.fragment,
        )
    )


def _parse_youtube_transcript_json3(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    events = payload.get("events")
    if not isinstance(events, list):
        return ("", [])
    segments: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        segs = event.get("segs")
        if not isinstance(segs, list):
            continue
        pieces: list[str] = []
        for seg in segs:
            if not isinstance(seg, dict):
                continue
            text = html.unescape(str(seg.get("utf8", "")))
            if text:
                pieces.append(text)
        merged = re.sub(r"\s+", " ", "".join(pieces)).strip()
        if not merged:
            continue
        segments.append(
            {
                "start_ms": int(event.get("tStartMs", 0) or 0),
                "duration_ms": int(event.get("dDurationMs", 0) or 0),
                "text": merged,
            }
        )
    transcript_text = "\n".join(str(row["text"]) for row in segments)
    return transcript_text, segments


def _parse_youtube_transcript_xml(text: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        root = ET.fromstring(text)
    except Exception:
        return ("", [])
    segments: list[dict[str, Any]] = []
    for node in root.findall(".//text"):
        body = html.unescape("".join(node.itertext() or []))
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            continue
        start = float(node.attrib.get("start", "0") or "0")
        duration = float(node.attrib.get("dur", "0") or "0")
        segments.append(
            {
                "start_ms": int(start * 1000),
                "duration_ms": int(duration * 1000),
                "text": body,
            }
        )
    if not segments:
        for node in root.findall(".//p"):
            body = html.unescape("".join(node.itertext() or []))
            body = re.sub(r"\s+", " ", body).strip()
            if not body:
                continue
            segments.append(
                {
                    "start_ms": int(node.attrib.get("t", "0") or "0"),
                    "duration_ms": int(node.attrib.get("d", "0") or "0"),
                    "text": body,
                }
            )
    transcript_text = "\n".join(str(row["text"]) for row in segments)
    return transcript_text, segments


def _youtube_fetch_oembed(canonical_url: str) -> dict[str, Any]:
    endpoint = "https://www.youtube.com/oembed?" + urlparse.urlencode({"url": canonical_url, "format": "json"})
    try:
        return _http_get_json(endpoint, headers=_youtube_request_headers(), timeout_sec=20)
    except Exception:
        return {}


def _youtube_fetch_watch_state(video_id: str) -> dict[str, Any]:
    url = _youtube_canonical_url(video_id) + "&hl=en&persist_hl=1"
    html_text = _http_get_text(url, headers=_youtube_request_headers(), timeout_sec=25)
    markers = [
        "var ytInitialPlayerResponse = ",
        "ytInitialPlayerResponse = ",
        "window['ytInitialPlayerResponse'] = ",
        'window["ytInitialPlayerResponse"] = ',
    ]
    player_response: dict[str, Any] | None = None
    for marker in markers:
        player_response = _extract_json_object_after_marker(html_text, marker)
        if player_response:
            break
    if not player_response:
        raise RuntimeError("Could not parse YouTube player response from the watch page.")
    captions = (
        player_response.get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks", [])
    )
    tracks = captions if isinstance(captions, list) else []
    normalized_tracks = [{**row, "_orp_source": "watch_page"} for row in tracks if isinstance(row, dict)]
    return {
        "player_response": player_response,
        "video_details": player_response.get("videoDetails", {}) if isinstance(player_response.get("videoDetails"), dict) else {},
        "microformat": (
            player_response.get("microformat", {}).get("playerMicroformatRenderer", {})
            if isinstance(player_response.get("microformat"), dict)
            else {}
        ),
        "playability_status": (
            player_response.get("playabilityStatus", {})
            if isinstance(player_response.get("playabilityStatus"), dict)
            else {}
        ),
        "caption_tracks": normalized_tracks,
    }


def _youtube_fetch_android_player_state(video_id: str) -> dict[str, Any]:
    payload = _http_post_json(
        "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
        {
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": YOUTUBE_ANDROID_CLIENT_VERSION,
                }
            },
            "videoId": video_id,
        },
        headers=_youtube_android_request_headers(),
        timeout_sec=25,
    )
    captions = (
        payload.get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks", [])
    )
    tracks = captions if isinstance(captions, list) else []
    normalized_tracks = [{**row, "_orp_source": "android_player"} for row in tracks if isinstance(row, dict)]
    return {
        "player_response": payload,
        "video_details": payload.get("videoDetails", {}) if isinstance(payload.get("videoDetails"), dict) else {},
        "microformat": {},
        "playability_status": payload.get("playabilityStatus", {}) if isinstance(payload.get("playabilityStatus"), dict) else {},
        "caption_tracks": normalized_tracks,
    }


def _youtube_ranked_caption_tracks(
    watch_tracks: list[dict[str, Any]],
    android_tracks: list[dict[str, Any]],
    preferred_lang: str = "",
) -> list[dict[str, Any]]:
    ranked = sorted(
        [track for track in android_tracks if isinstance(track, dict)]
        + [track for track in watch_tracks if isinstance(track, dict)],
        key=lambda track: _youtube_caption_track_sort_key(track, preferred_lang),
        reverse=True,
    )
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for track in ranked:
        key = (
            str(track.get("languageCode", "")).strip(),
            _youtube_track_label(track),
            str(track.get("kind", "")).strip().lower(),
            _youtube_track_source(track),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(track)
    return unique


def _youtube_parse_transcript_response(text: str) -> tuple[str, list[dict[str, Any]], str]:
    stripped = str(text or "").lstrip()
    if not stripped:
        return ("", [], "empty")
    if stripped.startswith("{"):
        try:
            payload = json.loads(text)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            transcript_text, segments = _parse_youtube_transcript_json3(payload)
            if transcript_text:
                return (transcript_text, segments, "json3")
    transcript_text, segments = _parse_youtube_transcript_xml(text)
    if transcript_text:
        return (transcript_text, segments, "xml")
    return ("", [], "unparsed")


def _youtube_fetch_transcript_from_track(track: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str]:
    base_url = str(track.get("baseUrl", "")).strip()
    if not base_url:
        return ("", [], "missing_track_url")
    source = _youtube_track_source(track) or "unknown"
    candidate_urls = [
        ("base", base_url),
        ("json3", _youtube_add_query_param(base_url, "fmt", "json3")),
        ("srv3", _youtube_add_query_param(base_url, "fmt", "srv3")),
    ]
    seen_urls: set[str] = set()
    for mode, candidate_url in candidate_urls:
        if candidate_url in seen_urls:
            continue
        seen_urls.add(candidate_url)
        try:
            response_text = _http_get_text(candidate_url, headers=_youtube_request_headers(), timeout_sec=25)
        except Exception:
            continue
        transcript_text, segments, parsed_mode = _youtube_parse_transcript_response(response_text)
        if transcript_text:
            final_mode = parsed_mode if mode == "base" else f"{mode}_{parsed_mode}"
            return transcript_text, segments, f"{source}_{final_mode}"
    return ("", [], "unavailable")


def _youtube_text_bundle(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    title = str(payload.get("title", "")).strip()
    if title:
        parts.append(f"Title: {title}")
    author_name = str(payload.get("author_name", "")).strip()
    if author_name:
        parts.append(f"Author: {author_name}")
    duration_seconds = payload.get("duration_seconds")
    if isinstance(duration_seconds, int) and duration_seconds > 0:
        parts.append(f"Duration seconds: {duration_seconds}")
    description = str(payload.get("description", "")).strip()
    if description:
        parts.append("Description:\n" + description)
    transcript_text = str(payload.get("transcript_text", "")).strip()
    if transcript_text:
        parts.append("Transcript:\n" + transcript_text)
    return "\n\n".join(parts)


def _youtube_inspect_payload(raw_url: str, preferred_lang: str = "") -> dict[str, Any]:
    video_id = _youtube_video_id_from_url(raw_url)
    canonical_url = _youtube_canonical_url(video_id)
    warnings: list[str] = []
    oembed = _youtube_fetch_oembed(canonical_url)

    watch_state: dict[str, Any] = {}
    try:
        watch_state = _youtube_fetch_watch_state(video_id)
    except Exception as exc:
        warnings.append(str(exc))
    android_state: dict[str, Any] = {}
    try:
        android_state = _youtube_fetch_android_player_state(video_id)
    except Exception as exc:
        warnings.append(str(exc))

    watch_video_details = watch_state.get("video_details", {}) if isinstance(watch_state.get("video_details"), dict) else {}
    android_video_details = (
        android_state.get("video_details", {}) if isinstance(android_state.get("video_details"), dict) else {}
    )
    video_details = watch_video_details or android_video_details
    microformat = watch_state.get("microformat", {}) if isinstance(watch_state.get("microformat"), dict) else {}
    playability = watch_state.get("playability_status", {}) if isinstance(watch_state.get("playability_status"), dict) else {}
    if not playability:
        playability = android_state.get("playability_status", {}) if isinstance(android_state.get("playability_status"), dict) else {}
    watch_tracks = [row for row in watch_state.get("caption_tracks", []) if isinstance(row, dict)]
    android_tracks = [row for row in android_state.get("caption_tracks", []) if isinstance(row, dict)]
    tracks = _youtube_ranked_caption_tracks(watch_tracks, android_tracks, preferred_lang)
    available_tracks = _youtube_track_inventory(tracks)
    transcript_text = ""
    transcript_segments: list[dict[str, Any]] = []
    transcript_fetch_mode = "none"
    transcript_available = False
    transcript_language = ""
    transcript_track_name = ""
    transcript_track_source = ""
    transcript_kind = "none"
    transcript_sources_tried: list[str] = []
    chosen_track: dict[str, Any] | None = None
    for candidate in tracks:
        transcript_sources_tried.append(
            ":".join(
                part
                for part in [
                    _youtube_track_source(candidate),
                    str(candidate.get("languageCode", "")).strip(),
                    _youtube_track_label(candidate),
                ]
                if part
            )
        )
        transcript_text, transcript_segments, transcript_fetch_mode = _youtube_fetch_transcript_from_track(candidate)
        if transcript_text.strip():
            transcript_available = True
            chosen_track = candidate
            break
    if chosen_track is not None:
        transcript_language = str(chosen_track.get("languageCode", "")).strip()
        transcript_track_name = _youtube_track_label(chosen_track)
        transcript_track_source = _youtube_track_source(chosen_track)
        transcript_kind = "auto" if str(chosen_track.get("kind", "")).strip().lower() == "asr" else "manual"
    if tracks:
        if not transcript_available:
            warnings.append("A caption track was found, but transcript text could not be fetched.")
    elif watch_state or android_state:
        warnings.append("No caption tracks were available for this video.")

    title = str(video_details.get("title") or oembed.get("title") or "").strip()
    author_name = str(video_details.get("author") or oembed.get("author_name") or "").strip()
    author_url = str(oembed.get("author_url") or "").strip()
    thumbnail_url = str(oembed.get("thumbnail_url") or "").strip()
    description = str(video_details.get("shortDescription") or microformat.get("description", {}).get("simpleText", "") or "").strip()
    channel_id = str(video_details.get("channelId") or "").strip()
    duration_seconds = 0
    raw_duration = video_details.get("lengthSeconds")
    if isinstance(raw_duration, str) and raw_duration.isdigit():
        duration_seconds = int(raw_duration)
    published_at = str(microformat.get("publishDate") or "").strip()
    payload = {
        "schema_version": YOUTUBE_SOURCE_SCHEMA_VERSION,
        "kind": "youtube_source",
        "retrieved_at_utc": _now_utc(),
        "source_url": str(raw_url).strip(),
        "canonical_url": canonical_url,
        "video_id": video_id,
        "title": title,
        "author_name": author_name,
        "author_url": author_url,
        "thumbnail_url": thumbnail_url,
        "channel_id": channel_id,
        "description": description,
        "duration_seconds": duration_seconds or None,
        "published_at": published_at,
        "playability_status": str(playability.get("status", "")).strip(),
        "transcript_track_count": len(available_tracks),
        "available_transcript_tracks": available_tracks,
        "transcript_available": transcript_available,
        "transcript_language": transcript_language,
        "transcript_track_name": transcript_track_name,
        "transcript_track_source": transcript_track_source,
        "transcript_kind": transcript_kind,
        "transcript_fetch_mode": transcript_fetch_mode,
        "transcript_text": transcript_text,
        "transcript_segments": transcript_segments,
        "transcript_sources_tried": transcript_sources_tried,
        "warnings": _unique_strings(warnings),
    }
    payload["text_bundle"] = _youtube_text_bundle(payload)
    return payload


def _default_youtube_artifact_path(repo_root: Path, video_id: str) -> Path:
    return repo_root / "orp" / "external" / "youtube" / f"{video_id}.json"


def cmd_youtube_inspect(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    preferred_lang = str(getattr(args, "lang", "") or "").strip()
    payload = _youtube_inspect_payload(args.url, preferred_lang=preferred_lang)

    out_raw = str(getattr(args, "out", "") or "").strip()
    should_save = bool(getattr(args, "save", False) or out_raw)
    out_path: Path | None = None
    emitted_format = ""
    if should_save:
        if out_raw:
            out_path = _resolve_cli_path(out_raw, repo_root)
        else:
            _ensure_dirs(repo_root)
            out_path = _default_youtube_artifact_path(repo_root, str(payload.get("video_id", "")).strip())
        if out_path.exists() and not bool(getattr(args, "force", False)):
            raise RuntimeError(
                f"output path already exists: {_path_for_state(out_path, repo_root)}. Use --force to overwrite."
            )
        emitted_format = _write_structured_payload(out_path, payload, format_hint=str(getattr(args, "format", "") or ""))

    result = {
        "ok": True,
        "saved": out_path is not None,
        "path": _path_for_state(out_path, repo_root) if out_path is not None else "",
        "format": emitted_format,
        "schema_path": "spec/v1/youtube-source.schema.json",
        "source": payload,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("ok", "true"),
                ("video.id", str(payload.get("video_id", "")).strip()),
                ("video.title", str(payload.get("title", "")).strip()),
                ("video.author", str(payload.get("author_name", "")).strip()),
                ("video.duration_seconds", payload.get("duration_seconds") or ""),
                ("transcript.track_count", payload.get("transcript_track_count") or 0),
                ("transcript.available", str(bool(payload.get("transcript_available", False))).lower()),
                ("transcript.language", str(payload.get("transcript_language", "")).strip()),
                ("transcript.track_source", str(payload.get("transcript_track_source", "")).strip()),
                ("transcript.kind", str(payload.get("transcript_kind", "")).strip()),
                ("saved", str(bool(out_path is not None)).lower()),
                ("path", _path_for_state(out_path, repo_root) if out_path is not None else ""),
            ]
        )
        bundle = str(payload.get("text_bundle", "")).strip()
        warnings = payload.get("warnings", []) if isinstance(payload.get("warnings"), list) else []
        if bundle:
            print("")
            print(bundle)
        if warnings:
            print("")
            for warning in warnings:
                text = str(warning).strip()
                if text:
                    print(f"warning={text}")
    return 0


def _runner_transport_mode(args: argparse.Namespace) -> str:
    mode = str(getattr(args, "transport", "auto") or "auto").strip().lower()
    if mode in {"poll", "sse"}:
        return mode
    return "auto"


def _wait_for_runner_signal_via_sse(args: argparse.Namespace, wait_seconds: int) -> dict[str, Any]:
    session = _load_hosted_session()
    token = str(session.get("token", "")).strip()
    if not token:
        raise HostedApiError("Run `orp auth login` and `orp auth verify` before waiting on hosted runner events.")
    machine = _load_runner_machine()
    machine_id = str(machine.get("machine_id", "")).strip()
    if not machine_id:
        raise RuntimeError("runner is disabled")
    base_url = _resolve_hosted_base_url(args, session)
    wait_seconds = max(1, int(wait_seconds))
    signal = _request_hosted_sse_event(
        base_url=base_url,
        path=(
            f"/api/cli/runner/events/stream?machineId={urlparse.quote(machine_id)}"
            f"&waitSeconds={wait_seconds}"
        ),
        token=token,
        timeout_sec=max(wait_seconds + 15, 30),
    )
    event_name = str(signal.get("event", "")).strip()
    payload = signal.get("data", {}) if isinstance(signal.get("data"), dict) else {}
    if event_name == "error":
        message = str(payload.get("error") or payload.get("message") or "runner event stream failed").strip()
        raise HostedApiError(message)
    return {
        "transport": "sse",
        "event": event_name,
        "machine_id": machine_id,
        "wait_seconds": wait_seconds,
        **payload,
    }


def _wait_for_next_runner_cycle(args: argparse.Namespace, wait_seconds: int) -> dict[str, Any]:
    transport = _runner_transport_mode(args)
    if transport == "poll":
        time.sleep(max(1, int(wait_seconds)))
        return {
            "transport": "poll",
            "wait_seconds": max(1, int(wait_seconds)),
            "jobAvailable": False,
            "reason": "poll_interval_sleep",
        }
    try:
        return _wait_for_runner_signal_via_sse(args, wait_seconds)
    except Exception as exc:
        if transport == "sse":
            raise
        time.sleep(max(1, int(wait_seconds)))
        return {
            "transport": "poll-fallback",
            "wait_seconds": max(1, int(wait_seconds)),
            "jobAvailable": False,
            "reason": "sse_fallback",
            "error": str(exc),
        }


def _can_prompt() -> bool:
    return bool(sys.stdin.isatty() and sys.stderr.isatty())


def _prompt_value(label: str, *, secret: bool = False) -> str:
    if not _can_prompt():
        return ""
    if secret:
        return getpass.getpass(f"{label}: ").strip()
    return input(f"{label}: ").strip()


def _read_value_from_stdin() -> str:
    try:
        raw = sys.stdin.read()
    except Exception:
        return ""
    return raw.rstrip("\r\n")


def _session_summary(session: dict[str, Any]) -> dict[str, Any]:
    user = session.get("user") if isinstance(session.get("user"), dict) else None
    pending = session.get("pending_verification")
    pending = pending if isinstance(pending, dict) else None
    return {
        "base_url": _normalize_base_url(session.get("base_url", "")),
        "email": str(session.get("email", "")).strip(),
        "user": user,
        "connected": bool(str(session.get("token", "")).strip()),
        "pending_verification": pending,
    }


def _require_hosted_session(args: argparse.Namespace) -> dict[str, Any]:
    session = _load_hosted_session()
    session["base_url"] = _resolve_hosted_base_url(args, session)
    if not str(session.get("token", "")).strip():
        raise RuntimeError("No hosted ORP session found. Run `orp auth login` and `orp auth verify` first.")
    return session


def _print_pairs(rows: list[tuple[str, Any]]) -> None:
    for key, value in rows:
        if value is None:
            value = ""
        print(f"{key}={value}")


def _mask_email(email: str) -> str:
    text = str(email).strip()
    if "@" not in text:
        return text
    local, domain = text.split("@", 1)
    if len(local) <= 2:
        masked = "*" * len(local)
    else:
        masked = local[:2] + ("*" * max(1, len(local) - 2))
    return f"{masked}@{domain}"


def _looks_like_uuid(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        uuid.UUID(text)
    except Exception:
        return False
    return True


def _extract_detail_sections_value(raw: Any, source_label: str) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if isinstance(raw.get("detailSections"), list):
            return list(raw["detailSections"])
        if isinstance(raw.get("details"), list):
            return list(raw["details"])
        if any(key in raw for key in {"body", "detail", "label", "detailLabel", "id"}):
            return [raw]
    if isinstance(raw, str):
        return [raw]
    raise RuntimeError(
        f"{source_label} must be a JSON array, a detail object, or an object with detailSections/details."
    )


def _normalize_feature_detail_section(raw: Any, index: int, source_label: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        return {
            "label": "Detail",
            "body": text,
        }
    if not isinstance(raw, dict):
        raise RuntimeError(f"{source_label} entry #{index + 1} must be an object or string.")

    label = str(raw.get("label", raw.get("detailLabel", "Detail"))).strip() or "Detail"
    body = str(raw.get("body", raw.get("detail", "")))
    result: dict[str, Any] = {
        "label": label,
        "body": body,
    }
    section_id = str(raw.get("id", "")).strip()
    if section_id:
        result["id"] = section_id
    if not body.strip() and "id" not in result:
        return None
    return result


def _normalize_detail_sections(raw: Any, source_label: str) -> list[dict[str, Any]]:
    values = _extract_detail_sections_value(raw, source_label)
    normalized: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        section = _normalize_feature_detail_section(value, index, source_label)
        if section:
            normalized.append(section)
    return normalized


def _primary_detail_section(feature: dict[str, Any] | None = None) -> dict[str, Any] | None:
    feature = feature if isinstance(feature, dict) else {}
    detail_sections = feature.get("detailSections")
    if isinstance(detail_sections, list) and detail_sections:
        first = detail_sections[0]
        if isinstance(first, dict):
            return dict(first)
    if feature.get("detail") or feature.get("detailLabel"):
        return {
            "label": str(feature.get("detailLabel", "Detail")).strip() or "Detail",
            "body": str(feature.get("detail", "")),
        }
    return None


def _resolve_feature_detail_sections_input(
    args: argparse.Namespace,
    current_feature: dict[str, Any] | None = None,
) -> list[dict[str, Any]] | None:
    if bool(getattr(args, "clear_details", False)):
        return []
    details_file = str(getattr(args, "details_file", "")).strip()
    if details_file:
        path = Path(details_file).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return _normalize_detail_sections(_read_json(path.resolve()), f"Feature details file {details_file}")
    details_json = getattr(args, "details_json", "")
    if details_json:
        try:
            parsed = json.loads(str(details_json))
        except Exception as exc:
            raise RuntimeError(f"Invalid --details-json payload: {exc}") from exc
        return _normalize_detail_sections(parsed, "--details-json")
    if getattr(args, "detail", None) is not None or getattr(args, "detail_label", None) is not None:
        current_primary = _primary_detail_section(current_feature)
        return _normalize_detail_sections(
            [
                {
                    **({"id": current_primary["id"]} if current_primary and current_primary.get("id") else {}),
                    "label": (
                        str(getattr(args, "detail_label", "")).strip()
                        if getattr(args, "detail_label", None) is not None
                        else str((current_primary or {}).get("label", "Detail")).strip()
                    )
                    or "Detail",
                    "body": (
                        str(getattr(args, "detail", ""))
                        if getattr(args, "detail", None) is not None
                        else str((current_primary or {}).get("body", ""))
                    ),
                }
            ],
            "feature detail input",
        )
    return None


def _collect_detail_section_refs(values: list[str]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for value in _unique_strings(values):
        feature_id, sep, detail_section_id = str(value).partition(":")
        if not sep or not feature_id.strip() or not detail_section_id.strip():
            raise RuntimeError("Detail section refs must use <feature-id>:<detail-section-id>.")
        refs.append(
            {
                "featureId": feature_id.strip(),
                "detailSectionId": detail_section_id.strip(),
            }
        )
    return refs


def _build_checkpoint_context_selection(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "includeIdeaTitle": not bool(getattr(args, "skip_idea_title", False)),
        "includeCorePlan": not bool(getattr(args, "skip_core_plan", False)),
        "includeGithub": not bool(getattr(args, "skip_github", False)),
        "includeRepoBinding": not bool(getattr(args, "skip_repo_binding", False)),
        "includePreviousResponseSummaries": bool(getattr(args, "include_previous_response_summaries", False)),
        "featureIds": _unique_strings(list(getattr(args, "feature_id", []) or [])),
        "detailSectionRefs": _collect_detail_section_refs(list(getattr(args, "detail_section", []) or [])),
        "userNote": str(getattr(args, "user_note", "")).strip(),
    }


def _split_structured_list(text: str) -> list[str]:
    lines = [line.strip() for line in str(text).splitlines() if line.strip()]
    bullets = [
        re.sub(r"^[-*•]\s+|^\d+\.\s+", "", line).strip()
        for line in lines
    ]
    bullets = [line for line in bullets if line]
    if bullets:
        return bullets
    text = str(text).strip()
    return [text] if text else []


def _parse_checkpoint_structured_response(body: str) -> dict[str, Any]:
    text = str(body or "").replace("\r\n", "\n")
    matches = list(
        re.finditer(
            r"^(?:#{1,6}\s*)?(Previous state|Current state|Heading state|Review notes|Action items)\s*:?\s*$",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    )
    sections: dict[str, Any] = {
        "previousState": None,
        "currentState": None,
        "headingState": None,
        "reviewNotes": [],
        "actionItems": [],
    }
    if not matches:
        return sections

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        heading = str(match.group(1) or "").strip().lower()
        if heading == "previous state":
            sections["previousState"] = content or None
        elif heading == "current state":
            sections["currentState"] = content or None
        elif heading == "heading state":
            sections["headingState"] = content or None
        elif heading == "review notes":
            sections["reviewNotes"] = _split_structured_list(content)
        elif heading == "action items":
            sections["actionItems"] = _split_structured_list(content)
    return sections


def _summarize_checkpoint_response(body: str) -> str:
    for line in str(body or "").splitlines():
        text = line.strip()
        if text:
            return text[:280]
    return ""


def _summarize_checkpoint_response_from_structured(body: str, structured: dict[str, Any]) -> str:
    for key in ("currentState", "headingState", "previousState"):
        value = structured.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:280]
    return _summarize_checkpoint_response(body)


def _build_remote_world_body(args: argparse.Namespace) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if getattr(args, "name", None) is not None:
        body["name"] = str(getattr(args, "name", "")).strip()
    if getattr(args, "project_root", None) is not None:
        text = str(getattr(args, "project_root", "")).strip()
        body["projectRoot"] = text or None
    if getattr(args, "github_url", None) is not None:
        text = str(getattr(args, "github_url", "")).strip()
        body["githubUrl"] = text or None
    if getattr(args, "codex_session_id", None) is not None:
        text = str(getattr(args, "codex_session_id", "")).strip()
        body["codexSessionId"] = text or None
    return body


def _build_remote_idea_body(
    args: argparse.Namespace,
    current_idea: dict[str, Any] | None = None,
    *,
    require_notes: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    title = getattr(args, "title", None)
    notes = getattr(args, "notes", None)
    summary = getattr(args, "summary", None)
    github_url = getattr(args, "github_url", None)
    link_label = getattr(args, "link_label", None)
    visibility = getattr(args, "visibility", None)

    if title is not None:
        text = str(title).strip()
        if text:
            body["title"] = text
    if notes is not None:
        body["notes"] = str(notes)
    elif summary is not None:
        body["notes"] = str(summary)
    elif current_idea is None and require_notes:
        body["notes"] = ""
    if github_url is not None:
        text = str(github_url).strip()
        body["githubUrl"] = text or None
    if link_label is not None:
        text = str(link_label).strip()
        body["linkLabel"] = text or None
    if visibility is not None:
        text = str(visibility).strip()
        if text:
            body["visibility"] = text
    return body


def _build_remote_feature_body(
    args: argparse.Namespace,
    idea_id: str,
    current_feature: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "ideaId": idea_id,
    }
    if getattr(args, "title", None) is not None:
        body["title"] = str(getattr(args, "title", "")).strip()
    if getattr(args, "notes", None) is not None:
        body["notes"] = str(getattr(args, "notes", ""))
    if getattr(args, "detail", None) is not None:
        body["detail"] = str(getattr(args, "detail", ""))
    if getattr(args, "detail_label", None) is not None:
        body["detailLabel"] = str(getattr(args, "detail_label", ""))
    detail_sections = _resolve_feature_detail_sections_input(args, current_feature)
    if detail_sections is not None:
        body["details"] = detail_sections
    if getattr(args, "starred", False):
        body["starred"] = True
    if getattr(args, "super_starred", False):
        body["superStarred"] = True
    if getattr(args, "visibility", None) is not None:
        body["visibility"] = str(getattr(args, "visibility", "")).strip()
    return body


def _resolve_codex_bin(args: argparse.Namespace) -> str:
    explicit = str(getattr(args, "codex_bin", "")).strip()
    if explicit:
        return explicit
    env_bin = os.environ.get("CODEX_BIN", "").strip()
    if env_bin:
        return env_bin
    return "codex"


def _run_checkpoint_codex_job(job: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    world = job.get("world")
    checkpoint = job.get("checkpoint")
    if not isinstance(world, dict) or not isinstance(checkpoint, dict):
        raise RuntimeError("Invalid checkpoint job payload: missing world/checkpoint.")

    project_root = str(world.get("projectRoot", "")).strip()
    codex_session_id = str(world.get("codexSessionId", "")).strip()
    prompt = str(job.get("prompt", ""))
    if not project_root:
        raise RuntimeError("Checkpoint job world is missing projectRoot.")
    if not codex_session_id:
        raise RuntimeError("Checkpoint job world is missing codexSessionId.")

    output_path = Path(tempfile.gettempdir()) / f"orp-checkpoint-response-{checkpoint.get('id', 'job')}.txt"
    codex_bin = _resolve_codex_bin(args)
    cmd = [
        codex_bin,
        "exec",
        "resume",
        "--skip-git-repo-check",
        "--output-last-message",
        str(output_path),
        codex_session_id,
        "-",
    ]
    env = dict(os.environ)
    profile = str(getattr(args, "codex_config_profile", "")).strip()
    if profile:
        env["CODEX_PROFILE"] = profile

    proc = subprocess.run(
        cmd,
        cwd=project_root,
        input=prompt,
        capture_output=True,
        text=True,
        env=env,
    )

    body = ""
    if output_path.exists():
        try:
            body = output_path.read_text(encoding="utf-8")
        finally:
            try:
                output_path.unlink()
            except Exception:
                pass
    if not body:
        body = proc.stdout or proc.stderr or ""

    structured = _parse_checkpoint_structured_response(body)
    return {
        "ok": proc.returncode == 0,
        "exitCode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "body": body,
        "summary": _summarize_checkpoint_response_from_structured(body, structured),
        "command": " ".join(cmd),
        "structured": structured,
    }

COLLABORATION_WORKFLOWS: list[dict[str, Any]] = [
    {
        "id": "watch_select",
        "profile": "issue_smashers_watch_select",
        "config": "orp.issue-smashers.yml",
        "description": "Select a candidate issue lane and record why it is worth pursuing.",
        "gate_ids": ["watch_select"],
    },
    {
        "id": "pre_open",
        "profile": "issue_smashers_pre_open",
        "config": "orp.issue-smashers.yml",
        "description": "Run viability and overlap checks before implementation or public PR work.",
        "gate_ids": ["viability_gate", "overlap_gate"],
    },
    {
        "id": "local_readiness",
        "profile": "issue_smashers_local_readiness",
        "config": "orp.issue-smashers.yml",
        "description": "Run local verification, freeze same-head readiness, and preflight PR text.",
        "gate_ids": ["local_gate", "ready_to_draft", "pr_body_preflight"],
    },
    {
        "id": "draft_transition",
        "profile": "issue_smashers_draft_transition",
        "config": "orp.issue-smashers.yml",
        "description": "Open or update the draft PR after readiness passes.",
        "gate_ids": ["draft_pr_transition"],
    },
    {
        "id": "draft_lifecycle",
        "profile": "issue_smashers_draft_lifecycle",
        "config": "orp.issue-smashers.yml",
        "description": "Check draft CI and ready-for-review status.",
        "gate_ids": ["draft_ci", "ready_for_review"],
    },
    {
        "id": "full_flow",
        "profile": "issue_smashers_full_flow",
        "config": "orp.issue-smashers.yml",
        "description": "End-to-end collaboration lifecycle from watch/select through ready-for-review.",
        "gate_ids": [
            "watch_select",
            "viability_gate",
            "overlap_gate",
            "local_gate",
            "ready_to_draft",
            "pr_body_preflight",
            "draft_pr_transition",
            "draft_ci",
            "ready_for_review",
        ],
    },
    {
        "id": "feedback_hardening",
        "profile": "issue_smashers_feedback_hardening",
        "config": "orp.issue-smashers-feedback-hardening.yml",
        "description": "Turn maintainer feedback into validated guards and synced docs.",
        "gate_ids": ["feedback_record", "guard_validation", "docs_sync"],
    },
]


def _scan_id() -> str:
    return "scan-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _coerce_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
            if text:
                values.append(text)
    return _unique_strings(values)


def _resolve_cli_path(raw: str, repo_root: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    return path


def _discover_profile_template(
    *,
    profile_id: str,
    owner: str,
    owner_type: str,
    keywords: list[str],
    topics: list[str],
    languages: list[str],
    areas: list[str],
    people: list[str],
) -> dict[str, Any]:
    owner_value = owner.strip() or "YOUR_GITHUB_OWNER"
    return {
        "schema_version": "1.0.0",
        "profile_id": profile_id,
        "notes": [
            "ORP owns the portable discovery profile format and scan artifacts.",
            "ORP also owns active discovery profile selection and scanning context.",
            "Discovery outputs are process-only recommendations, not evidence.",
        ],
        "discover": {
            "github": {
                "owner": {
                    "login": owner_value,
                    "type": owner_type,
                },
                "signals": {
                    "keywords": keywords,
                    "repo_topics": topics,
                    "languages": languages,
                    "areas": areas,
                    "people": people,
                },
                "filters": {
                    "include_repos": [],
                    "exclude_repos": [],
                    "issue_states": ["open"],
                    "labels_any": [],
                    "exclude_labels": [],
                    "updated_within_days": 180,
                },
                "ranking": {
                    "repo_sample_size": 30,
                    "max_repos": 12,
                    "max_issues": 24,
                    "max_people": 12,
                    "issues_per_repo": 30,
                },
            }
        },
    }


def _normalize_discover_profile(raw: dict[str, Any]) -> dict[str, Any]:
    discover = raw.get("discover")
    github = discover.get("github") if isinstance(discover, dict) else {}
    github = github if isinstance(github, dict) else {}
    owner = github.get("owner")
    owner = owner if isinstance(owner, dict) else {}
    signals = github.get("signals")
    signals = signals if isinstance(signals, dict) else {}
    filters = github.get("filters")
    filters = filters if isinstance(filters, dict) else {}
    ranking = github.get("ranking")
    ranking = ranking if isinstance(ranking, dict) else {}
    owner_type = str(owner.get("type", "auto")).strip().lower() or "auto"
    if owner_type not in {"auto", "user", "org"}:
        owner_type = "auto"
    def _positive_int(value: Any, default: int) -> int:
        try:
            out = int(value)
        except Exception:
            return default
        return out if out > 0 else default

    issue_states = [state for state in _coerce_string_list(filters.get("issue_states")) if state in {"open", "closed", "all"}]
    if not issue_states:
        issue_states = ["open"]

    return {
        "schema_version": str(raw.get("schema_version", "1.0.0")).strip() or "1.0.0",
        "profile_id": str(raw.get("profile_id", "default")).strip() or "default",
        "notes": _coerce_string_list(raw.get("notes")),
        "github": {
            "owner": {
                "login": str(owner.get("login", "")).strip(),
                "type": owner_type,
            },
            "signals": {
                "keywords": _coerce_string_list(signals.get("keywords")),
                "repo_topics": _coerce_string_list(signals.get("repo_topics")),
                "languages": _coerce_string_list(signals.get("languages")),
                "areas": _coerce_string_list(signals.get("areas")),
                "people": _coerce_string_list(signals.get("people")),
            },
            "filters": {
                "include_repos": _coerce_string_list(filters.get("include_repos")),
                "exclude_repos": _coerce_string_list(filters.get("exclude_repos")),
                "issue_states": issue_states,
                "labels_any": _coerce_string_list(filters.get("labels_any")),
                "exclude_labels": _coerce_string_list(filters.get("exclude_labels")),
                "updated_within_days": _positive_int(filters.get("updated_within_days", 180), 180),
            },
            "ranking": {
                "repo_sample_size": _positive_int(ranking.get("repo_sample_size", 30), 30),
                "max_repos": _positive_int(ranking.get("max_repos", 12), 12),
                "max_issues": _positive_int(ranking.get("max_issues", 24), 24),
                "max_people": _positive_int(ranking.get("max_people", 12), 12),
                "issues_per_repo": _positive_int(ranking.get("issues_per_repo", 30), 30),
            },
        },
    }


def _github_token_context() -> dict[str, str]:
    for env_name in ["GITHUB_TOKEN", "GH_TOKEN"]:
        token = os.environ.get(env_name, "").strip()
        if token:
            return {"token": token, "source": env_name}
    return {"token": "", "source": "anonymous"}


def _github_headers(token: str) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ORP-Discover/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_json_get(url: str, headers: dict[str, str]) -> Any:
    request = urlrequest.Request(url, headers=headers)
    with urlrequest.urlopen(request, timeout=30) as response:
        text = response.read().decode("utf-8")
    return json.loads(text)


def _github_detect_owner_type(owner_login: str, headers: dict[str, str]) -> str:
    payload = _http_json_get(f"https://api.github.com/users/{urlparse.quote(owner_login)}", headers)
    if isinstance(payload, dict):
        owner_type = str(payload.get("type", "")).strip().lower()
        if owner_type == "organization":
            return "org"
        if owner_type == "user":
            return "user"
    return "user"


def _github_list_repos(owner_login: str, owner_type: str, limit: int, headers: dict[str, str]) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    page = 1
    while len(repos) < limit:
        params = {"per_page": min(100, max(limit, 1)), "page": page, "sort": "updated"}
        if owner_type == "org":
            params["type"] = "public"
            url = f"https://api.github.com/orgs/{urlparse.quote(owner_login)}/repos?{urlparse.urlencode(params)}"
        else:
            params["type"] = "owner"
            url = f"https://api.github.com/users/{urlparse.quote(owner_login)}/repos?{urlparse.urlencode(params)}"
        payload = _http_json_get(url, headers)
        if not isinstance(payload, list) or not payload:
            break
        repos.extend([row for row in payload if isinstance(row, dict)])
        if len(payload) < params["per_page"]:
            break
        page += 1
    return repos[:limit]


def _github_list_issues(owner_login: str, repo_name: str, states: list[str], per_repo_limit: int, headers: dict[str, str]) -> list[dict[str, Any]]:
    state = "all" if "all" in states else ("closed" if states == ["closed"] else "open")
    issues: list[dict[str, Any]] = []
    page = 1
    while len(issues) < per_repo_limit:
        params = {
            "state": state,
            "per_page": min(100, max(per_repo_limit, 1)),
            "page": page,
            "sort": "updated",
            "direction": "desc",
        }
        url = (
            f"https://api.github.com/repos/{urlparse.quote(owner_login)}/{urlparse.quote(repo_name)}"
            f"/issues?{urlparse.urlencode(params)}"
        )
        payload = _http_json_get(url, headers)
        if not isinstance(payload, list) or not payload:
            break
        cleaned = [row for row in payload if isinstance(row, dict) and "pull_request" not in row]
        issues.extend(cleaned)
        if len(payload) < params["per_page"]:
            break
        page += 1
    return issues[:per_repo_limit]


def _days_since_iso(iso_text: str) -> int | None:
    text = iso_text.strip()
    if not text:
        return None
    try:
        stamp = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    delta = now - stamp.astimezone(dt.timezone.utc)
    return max(0, int(delta.total_seconds() // 86400))


def _recency_sort_key(iso_text: str) -> int:
    days = _days_since_iso(iso_text)
    if days is None:
        return 10**9
    return days


def _text_contains_any(text: str, needles: list[str]) -> list[str]:
    hay = text.lower()
    matches: list[str] = []
    for raw in needles:
        needle = raw.strip().lower()
        if needle and needle in hay:
            matches.append(raw)
    return _unique_strings(matches)


def _score_repo(repo: dict[str, Any], profile: dict[str, Any]) -> tuple[int, list[str]]:
    github = profile["github"]
    signals = github["signals"]
    filters = github["filters"]
    repo_name = str(repo.get("name", "")).strip()
    full_name = str(repo.get("full_name", "")).strip()
    description = str(repo.get("description", "") or "").strip()
    language = str(repo.get("language", "") or "").strip()
    topics = [str(item).strip() for item in repo.get("topics", []) if isinstance(item, str)]
    searchable = " ".join([repo_name, full_name, description, language, " ".join(topics)]).lower()
    reasons: list[str] = []
    score = 0

    if repo_name in filters["exclude_repos"] or full_name in filters["exclude_repos"]:
        return (-1, ["excluded_repo"])
    if filters["include_repos"] and repo_name not in filters["include_repos"] and full_name not in filters["include_repos"]:
        return (0, ["not_included"])
    if repo_name in filters["include_repos"] or full_name in filters["include_repos"]:
        score += 100
        reasons.append("include_repo")

    keyword_matches = _text_contains_any(searchable, signals["keywords"])
    score += 5 * len(keyword_matches)
    reasons.extend([f"keyword:{item}" for item in keyword_matches])

    area_matches = _text_contains_any(searchable, signals["areas"])
    score += 3 * len(area_matches)
    reasons.extend([f"area:{item}" for item in area_matches])

    if language and language in signals["languages"]:
        score += 6
        reasons.append(f"language:{language}")

    topic_set = {topic.lower(): topic for topic in topics}
    for raw in signals["repo_topics"]:
        key = raw.lower()
        if key in topic_set:
            score += 8
            reasons.append(f"topic:{topic_set[key]}")

    updated_days = _days_since_iso(str(repo.get("updated_at", "") or ""))
    if updated_days is not None and updated_days <= int(github["filters"]["updated_within_days"]):
        score += 2
        reasons.append("recent_repo_activity")

    if score == 0:
        score = 1
        reasons.append("baseline_repo")
    return (score, _unique_strings(reasons))


def _score_issue(issue: dict[str, Any], repo_row: dict[str, Any], profile: dict[str, Any]) -> tuple[int, list[str]]:
    github = profile["github"]
    signals = github["signals"]
    filters = github["filters"]
    title = str(issue.get("title", "") or "").strip()
    body = str(issue.get("body", "") or "").strip()
    labels = [str(row.get("name", "")).strip() for row in issue.get("labels", []) if isinstance(row, dict)]
    assignees = [str(row.get("login", "")).strip() for row in issue.get("assignees", []) if isinstance(row, dict)]
    author = str((issue.get("user") or {}).get("login", "")).strip() if isinstance(issue.get("user"), dict) else ""
    searchable = " ".join([title, body, " ".join(labels)]).lower()
    reasons = [f"repo:{repo_row['full_name']}"]
    score = int(repo_row["score"])

    if any(label in filters["exclude_labels"] for label in labels):
        return (-1, ["excluded_label"])

    keyword_matches = _text_contains_any(searchable, signals["keywords"])
    score += 6 * len(keyword_matches)
    reasons.extend([f"keyword:{item}" for item in keyword_matches])

    area_matches = _text_contains_any(searchable, signals["areas"])
    score += 5 * len(area_matches)
    reasons.extend([f"area:{item}" for item in area_matches])

    label_matches = [label for label in labels if label in filters["labels_any"]]
    score += 4 * len(label_matches)
    reasons.extend([f"label:{item}" for item in label_matches])

    people_matches = [person for person in signals["people"] if person in assignees or person == author]
    score += 4 * len(people_matches)
    reasons.extend([f"person:{item}" for item in people_matches])

    updated_days = _days_since_iso(str(issue.get("updated_at", "") or ""))
    if updated_days is not None and updated_days <= int(filters["updated_within_days"]):
        score += 1
        reasons.append("recent_issue_activity")

    return (score, _unique_strings(reasons))


def _load_fixture_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _render_discover_scan_summary(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# ORP GitHub Discovery Scan `{payload['scan_id']}`")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- owner: `{payload['owner']['login']}`")
    lines.append(f"- owner_type: `{payload['owner']['type']}`")
    lines.append(f"- profile_id: `{payload['profile']['profile_id']}`")
    lines.append(f"- auth: `{payload['auth']['source']}`")
    lines.append(f"- repos_considered: `{payload['counts']['repos_considered']}`")
    lines.append(f"- issues_considered: `{payload['counts']['issues_considered']}`")
    lines.append("")
    lines.append("## Top Repo Matches")
    lines.append("")
    lines.append("| Repo | Score | Why |")
    lines.append("|---|---:|---|")
    for row in payload.get("repos", [])[:10]:
        reasons = ", ".join(row.get("reasons", [])[:4]) or "baseline_repo"
        lines.append(f"| `{row['full_name']}` | {row['score']} | {reasons} |")
    lines.append("")
    lines.append("## Top Issue Matches")
    lines.append("")
    lines.append("| Issue | Repo | Score | People | Why |")
    lines.append("|---|---|---:|---|---|")
    for row in payload.get("issues", [])[:12]:
        people = ", ".join(row.get("people", [])[:3]) or "-"
        reasons = ", ".join(row.get("reasons", [])[:4]) or "repo_match"
        lines.append(
            f"| `#{row['number']} {row['title']}` | `{row['repo']}` | {row['score']} | {people} | {reasons} |"
        )
    lines.append("")
    lines.append("## Active People Signals")
    lines.append("")
    lines.append("| Login | Score | Issue Count | Repos |")
    lines.append("|---|---:|---:|---|")
    for row in payload.get("people", [])[:10]:
        repos = ", ".join(row.get("repos", [])[:3]) or "-"
        lines.append(f"| `{row['login']}` | {row['score']} | {row['matched_issue_count']} | {repos} |")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Discovery scans are recommendation artifacts, not evidence.")
    lines.append("- GitHub public issue metadata shows authors, assignees, labels, and recency, but not full code ownership.")
    if payload.get("repos"):
        top_repo = payload["repos"][0]["full_name"]
        lines.append(f"- Suggested handoff: `orp collaborate init --github-repo {top_repo}`")
    return "\n".join(lines) + "\n"


def _exchange_report_schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "spec" / "v1" / "exchange-report.schema.json"


def _exchange_id() -> str:
    return "exchange-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def _exchange_root(repo_root: Path) -> Path:
    return repo_root / "orp" / "exchange"


def _exchange_paths(repo_root: Path, exchange_id: str) -> dict[str, Path]:
    root = _exchange_root(repo_root) / exchange_id
    return {
        "root": root,
        "exchange_json": root / "EXCHANGE.json",
        "summary_md": root / "EXCHANGE_SUMMARY.md",
        "transfer_map_md": root / "TRANSFER_MAP.md",
    }


def _exchange_source_workspace(repo_root: Path, source_slug: str) -> Path:
    return _exchange_root(repo_root) / "_sources" / source_slug


def _exchange_local_source_path(raw: str, repo_root: Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    return path


def _exchange_looks_like_remote_source(raw: str) -> bool:
    text = str(raw or "").strip()
    if not text:
        return False
    if "://" in text or text.startswith("git@") or text.endswith(".git"):
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text))


def _exchange_remote_url(raw: str) -> str:
    text = str(raw or "").strip()
    if "://" in text or text.startswith("git@") or text.endswith(".git"):
        return text
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text):
        return f"https://github.com/{text}.git"
    raise RuntimeError(f"unsupported exchange source: {text}")


def _exchange_run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("git is required for repository exchange but was not found on PATH.") from exc


def _exchange_init_git(source_root: Path) -> None:
    proc = _exchange_run_git(["git", "init"], cwd=source_root)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git init failed").strip())


EXCHANGE_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "target",
    ".next",
    ".turbo",
    ".idea",
    ".vscode",
}

EXCHANGE_MANIFEST_BASENAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "Makefile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    "README.md",
    "README",
}


def _exchange_language_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    mapping = {
        ".py": "Python",
        ".js": "JavaScript",
        ".mjs": "JavaScript",
        ".cjs": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".jsx": "JavaScript",
        ".rs": "Rust",
        ".go": "Go",
        ".java": "Java",
        ".kt": "Kotlin",
        ".swift": "Swift",
        ".rb": "Ruby",
        ".php": "PHP",
        ".sh": "Shell",
        ".bash": "Shell",
        ".zsh": "Shell",
        ".md": "Markdown",
        ".json": "JSON",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".toml": "TOML",
        ".html": "HTML",
        ".css": "CSS",
        ".cpp": "C++",
        ".cc": "C++",
        ".cxx": "C++",
        ".c": "C",
        ".h": "C/C++ Header",
    }
    return mapping.get(suffix, "")


def _exchange_inventory(root: Path) -> dict[str, Any]:
    top_level_entries: list[dict[str, Any]] = []
    manifest_files: list[str] = []
    docs_paths: list[str] = []
    test_paths: list[str] = []
    language_counts: dict[str, int] = {}
    files_scanned = 0
    dirs_scanned = 0

    if root.exists():
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if child.name in EXCHANGE_SKIP_DIR_NAMES:
                continue
            top_level_entries.append({"name": child.name, "kind": "dir" if child.is_dir() else "file"})

    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCHANGE_SKIP_DIR_NAMES]
        dirs_scanned += len(dirs)
        current_path = Path(current_root)
        for filename in files:
            if filename in {".DS_Store"}:
                continue
            full = current_path / filename
            rel = str(full.relative_to(root))
            files_scanned += 1
            if filename in EXCHANGE_MANIFEST_BASENAMES:
                manifest_files.append(rel)
            lower_rel = rel.lower()
            if filename.lower().startswith("readme") or lower_rel.startswith("docs/") or lower_rel.endswith(".md"):
                docs_paths.append(rel)
            rel_parts = [part.lower() for part in full.relative_to(root).parts]
            if "tests" in rel_parts or "__tests__" in rel_parts or filename.lower().startswith("test_"):
                test_paths.append(rel)
            language = _exchange_language_for_path(full)
            if language:
                language_counts[language] = int(language_counts.get(language, 0)) + 1

    top_languages = sorted(
        [{"language": key, "count": value} for key, value in language_counts.items()],
        key=lambda row: (-int(row["count"]), str(row["language"])),
    )
    return {
        "top_level_entries": top_level_entries[:40],
        "manifest_files": sorted(_unique_strings(manifest_files))[:40],
        "docs_paths": sorted(_unique_strings(docs_paths))[:40],
        "test_paths": sorted(_unique_strings(test_paths))[:40],
        "languages": top_languages[:20],
        "files_scanned": files_scanned,
        "dirs_scanned": dirs_scanned,
    }


def _exchange_manifest_types(paths: list[str]) -> list[str]:
    manifest_types: list[str] = []
    basenames = {Path(path).name for path in paths}
    if "package.json" in basenames:
        manifest_types.append("node")
    if "pyproject.toml" in basenames or "requirements.txt" in basenames:
        manifest_types.append("python")
    if "Cargo.toml" in basenames:
        manifest_types.append("rust")
    if "go.mod" in basenames:
        manifest_types.append("go")
    if "Dockerfile" in basenames or "docker-compose.yml" in basenames or "docker-compose.yaml" in basenames:
        manifest_types.append("container")
    return manifest_types


def _exchange_relation(host_root: Path, source_root: Path, source_inventory: dict[str, Any]) -> dict[str, Any]:
    if host_root.resolve() == source_root.resolve():
        return {
            "host_repo_name": host_root.name,
            "source_repo_name": source_root.name,
            "same_root": True,
            "shared_languages": [row.get("language", "") for row in source_inventory.get("languages", []) if row.get("language")],
            "shared_manifest_types": _exchange_manifest_types(source_inventory.get("manifest_files", [])),
            "shared_top_level_entries": [row.get("name", "") for row in source_inventory.get("top_level_entries", []) if row.get("name")],
        }

    host_inventory = _exchange_inventory(host_root)
    source_languages = {str(row.get("language", "")).strip() for row in source_inventory.get("languages", []) if str(row.get("language", "")).strip()}
    host_languages = {str(row.get("language", "")).strip() for row in host_inventory.get("languages", []) if str(row.get("language", "")).strip()}
    source_manifests = set(_exchange_manifest_types(source_inventory.get("manifest_files", [])))
    host_manifests = set(_exchange_manifest_types(host_inventory.get("manifest_files", [])))
    source_top = {str(row.get("name", "")).strip() for row in source_inventory.get("top_level_entries", []) if str(row.get("name", "")).strip()}
    host_top = {str(row.get("name", "")).strip() for row in host_inventory.get("top_level_entries", []) if str(row.get("name", "")).strip()}
    return {
        "host_repo_name": host_root.name,
        "source_repo_name": source_root.name,
        "same_root": False,
        "shared_languages": sorted(source_languages & host_languages),
        "shared_manifest_types": sorted(source_manifests & host_manifests),
        "shared_top_level_entries": sorted(source_top & host_top)[:20],
    }


def _exchange_suggested_focus(source_inventory: dict[str, Any], relation: dict[str, Any]) -> list[str]:
    focus: list[str] = [
        "Capture the repo thesis and what problem the source project is solving.",
        "Map the source project's architecture, boundaries, and major modules.",
        "Identify reusable workflow, governance, or artifact patterns.",
        "Record how the source sharpens the current project's direction and momentum.",
    ]
    if relation.get("shared_languages"):
        focus.append("Compare implementation patterns in the shared language stack.")
    if relation.get("shared_manifest_types"):
        focus.append("Compare build, test, and runtime surfaces across the shared toolchain.")
    if source_inventory.get("test_paths"):
        focus.append("Inspect how the source project expresses validation and testing discipline.")
    if source_inventory.get("docs_paths"):
        focus.append("Extract durable knowledge from the source project's docs and internal explanations.")
    return _unique_strings(focus)


def _exchange_summary_markdown(payload: dict[str, Any]) -> str:
    source = payload.get("source", {}) if isinstance(payload.get("source"), dict) else {}
    inventory = payload.get("inventory", {}) if isinstance(payload.get("inventory"), dict) else {}
    relation = payload.get("relation", {}) if isinstance(payload.get("relation"), dict) else {}
    lines: list[str] = []
    lines.append(f"# ORP Knowledge Exchange `{payload.get('exchange_id', '')}`")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- source: `{source.get('requested', '')}`")
    lines.append(f"- mode: `{source.get('mode', '')}`")
    lines.append(f"- local_path: `{source.get('local_path', '')}`")
    lines.append(f"- git_present: `{str(bool(source.get('git_present'))).lower()}`")
    lines.append(f"- git_initialized_by_orp: `{str(bool(source.get('git_initialized_by_orp'))).lower()}`")
    lines.append(f"- files_scanned: `{inventory.get('files_scanned', 0)}`")
    lines.append(f"- dirs_scanned: `{inventory.get('dirs_scanned', 0)}`")
    lines.append("")
    lines.append("## Inventory")
    lines.append("")
    top_languages = inventory.get("languages", [])
    if isinstance(top_languages, list) and top_languages:
        lines.append("- top_languages:")
        for row in top_languages[:8]:
            if not isinstance(row, dict):
                continue
            lines.append(f"  - `{row.get('language', '')}`: {row.get('count', 0)} files")
    manifests = inventory.get("manifest_files", [])
    if isinstance(manifests, list) and manifests:
        lines.append("- manifest_files:")
        for path in manifests[:10]:
            lines.append(f"  - `{path}`")
    docs_paths = inventory.get("docs_paths", [])
    if isinstance(docs_paths, list) and docs_paths:
        lines.append("- docs_paths:")
        for path in docs_paths[:10]:
            lines.append(f"  - `{path}`")
    test_paths = inventory.get("test_paths", [])
    if isinstance(test_paths, list) and test_paths:
        lines.append("- test_paths:")
        for path in test_paths[:10]:
            lines.append(f"  - `{path}`")
    lines.append("")
    lines.append("## Relationship To Current Project")
    lines.append("")
    lines.append(f"- current_project: `{relation.get('host_repo_name', '')}`")
    shared_languages = relation.get("shared_languages", [])
    shared_manifest_types = relation.get("shared_manifest_types", [])
    shared_top = relation.get("shared_top_level_entries", [])
    lines.append(f"- shared_languages: `{', '.join(shared_languages) or 'none'}`")
    lines.append(f"- shared_manifest_types: `{', '.join(shared_manifest_types) or 'none'}`")
    lines.append(f"- shared_top_level_entries: `{', '.join(shared_top) or 'none'}`")
    lines.append("")
    lines.append("## Suggested Focus")
    lines.append("")
    for row in payload.get("suggested_focus", [])[:10]:
        lines.append(f"- {row}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Exchange artifacts are structured synthesis aids, not evidence by themselves.")
    lines.append("- The point is depth: what this repo knows, how it is organized, and what can transfer.")
    return "\n".join(lines).rstrip() + "\n"


def _exchange_transfer_map_markdown(payload: dict[str, Any]) -> str:
    source = payload.get("source", {}) if isinstance(payload.get("source"), dict) else {}
    relation = payload.get("relation", {}) if isinstance(payload.get("relation"), dict) else {}
    inventory = payload.get("inventory", {}) if isinstance(payload.get("inventory"), dict) else {}
    lines: list[str] = []
    lines.append(f"# Transfer Map: {relation.get('source_repo_name', source.get('label', 'source'))}")
    lines.append("")
    lines.append("## How This Could Help Us")
    lines.append("")
    lines.append("_Use this note to capture what the source repository teaches, what patterns can transfer, and what momentum it gives the current project._")
    lines.append("")
    lines.append("## Shared Ground")
    lines.append("")
    lines.append(f"- shared_languages: `{', '.join(relation.get('shared_languages', [])) or 'none'}`")
    lines.append(f"- shared_manifest_types: `{', '.join(relation.get('shared_manifest_types', [])) or 'none'}`")
    lines.append(f"- shared_top_level_entries: `{', '.join(relation.get('shared_top_level_entries', [])) or 'none'}`")
    lines.append("")
    lines.append("## Source Strengths To Inspect")
    lines.append("")
    if inventory.get("docs_paths"):
        lines.append("- documentation and explanation surfaces")
    if inventory.get("test_paths"):
        lines.append("- validation and testing discipline")
    if inventory.get("manifest_files"):
        lines.append("- runtime, build, and dependency surfaces")
    lines.append("- architecture, boundaries, and module layout")
    lines.append("- workflow and governance choices")
    lines.append("")
    lines.append("## Project Momentum")
    lines.append("")
    lines.append("_What does this repository suggest about where our current project could go next? What does it sharpen, validate, or challenge?_")
    lines.append("")
    lines.append("## Optional Action Paths")
    lines.append("")
    lines.append("_Capture implications for context. Do not execute automatically unless explicitly requested._")
    return "\n".join(lines).rstrip() + "\n"


def _exchange_source_payload(repo_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    requested = str(args.source).strip()
    local_candidate = _exchange_local_source_path(requested, repo_root)
    git_initialized_by_orp = False
    cloned_by_orp = False
    remote_url = ""

    if local_candidate.exists():
        if not local_candidate.is_dir():
            raise RuntimeError(f"exchange source is not a directory: {local_candidate}")
        local_path = local_candidate
        git_present = _git_repo_present(local_path)
        mode = "local_git" if git_present else "local_directory"
        if not git_present and bool(getattr(args, "allow_git_init", False)):
            _exchange_init_git(local_path)
            git_present = _git_repo_present(local_path)
            git_initialized_by_orp = git_present
            if git_present:
                mode = "local_git"
    elif _exchange_looks_like_remote_source(requested):
        remote_url = _exchange_remote_url(requested)
        source_slug = _slug_token(requested, fallback="source")
        local_path = _exchange_source_workspace(repo_root, source_slug)
        if not local_path.exists():
            proc = _exchange_run_git(["git", "clone", "--depth", "1", remote_url, str(local_path)], cwd=repo_root)
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "git clone failed").strip())
            cloned_by_orp = True
        mode = "remote_git"
        git_present = _git_repo_present(local_path)
    else:
        raise RuntimeError(f"source does not exist locally and is not a supported remote git reference: {requested}")

    git_context = _git_home_context(local_path)
    return {
        "requested": requested,
        "mode": mode,
        "label": local_path.name,
        "local_path": str(local_path),
        "remote_url": remote_url,
        "git_present": git_present,
        "git_initialized_by_orp": git_initialized_by_orp,
        "cloned_by_orp": cloned_by_orp,
        "git": git_context,
    }


def _orp_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


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


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = _read_json(path)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _default_state_payload() -> dict[str, Any]:
    return {
        "last_run_id": "",
        "last_packet_id": "",
        "runs": {},
        "last_erdos_sync": {},
        "last_discover_scan_id": "",
        "discovery_scans": {},
        "governance": {},
    }


def _ensure_dirs(repo_root: Path) -> None:
    (repo_root / "orp" / "packets").mkdir(parents=True, exist_ok=True)
    (repo_root / "orp" / "artifacts").mkdir(parents=True, exist_ok=True)
    (repo_root / "orp" / "discovery" / "github").mkdir(parents=True, exist_ok=True)
    (repo_root / "orp" / "checkpoints").mkdir(parents=True, exist_ok=True)
    (repo_root / "orp" / "handoffs").mkdir(parents=True, exist_ok=True)
    state_path = repo_root / "orp" / "state.json"
    if not state_path.exists():
        _write_json(state_path, _default_state_payload())


def _frontier_root(repo_root: Path) -> Path:
    return repo_root / "orp" / "frontier"


def _frontier_paths(repo_root: Path) -> dict[str, Path]:
    root = _frontier_root(repo_root)
    return {
        "root": root,
        "state_json": root / "state.json",
        "roadmap_json": root / "roadmap.json",
        "checklist_json": root / "checklist.json",
        "stack_json": root / "version-stack.json",
        "state_md": root / "STATE.md",
        "roadmap_md": root / "ROADMAP.md",
        "checklist_md": root / "CHECKLIST.md",
        "stack_md": root / "VERSION_STACK.md",
    }


def _frontier_band_rules() -> dict[str, dict[str, Any]]:
    return {
        "exact": {
            "description": "Only the live milestone should be exact.",
            "max_active_milestones": 1,
        },
        "structured": {
            "description": "The next 2-3 milestones or versions should be specifically structured but still revisable.",
        },
        "horizon": {
            "description": "Farther milestones keep intent exact while phase detail stays light.",
        },
    }


def _default_frontier_state_payload() -> dict[str, Any]:
    return {
        "schema_version": FRONTIER_SCHEMA_VERSION,
        "kind": "orp_frontier_state",
        "active_version": "",
        "active_milestone": "",
        "active_phase": "",
        "band": "",
        "next_action": "",
        "blocked_by": [],
    }


def _default_frontier_stack_payload(program_id: str, label: str) -> dict[str, Any]:
    return {
        "schema_version": FRONTIER_SCHEMA_VERSION,
        "kind": "orp_frontier_version_stack",
        "program_id": str(program_id).strip(),
        "label": str(label).strip(),
        "band_rules": _frontier_band_rules(),
        "current_frontier": {
            "active_version": "",
            "active_milestone": "",
            "active_phase": "",
            "band": "",
            "next_action": "",
            "blocked_by": [],
        },
        "versions": [],
    }


def _frontier_load_stack(repo_root: Path) -> dict[str, Any]:
    payload = _read_json_if_exists(_frontier_paths(repo_root)["stack_json"])
    if not payload:
        raise RuntimeError("frontier stack is missing. Run `orp frontier init` first.")
    return payload


def _frontier_load_state(repo_root: Path) -> dict[str, Any]:
    payload = _read_json_if_exists(_frontier_paths(repo_root)["state_json"])
    if not payload:
        raise RuntimeError("frontier state is missing. Run `orp frontier init` first.")
    return payload


def _frontier_find_version(stack: dict[str, Any], version_id: str) -> dict[str, Any] | None:
    versions = stack.get("versions")
    if not isinstance(versions, list):
        return None
    for version in versions:
        if isinstance(version, dict) and str(version.get("id", "")).strip() == version_id:
            return version
    return None


def _frontier_find_milestone(stack: dict[str, Any], milestone_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    versions = stack.get("versions")
    if not isinstance(versions, list):
        return (None, None)
    for version in versions:
        if not isinstance(version, dict):
            continue
        milestones = version.get("milestones")
        if not isinstance(milestones, list):
            continue
        for milestone in milestones:
            if isinstance(milestone, dict) and str(milestone.get("id", "")).strip() == milestone_id:
                return (version, milestone)
    return (None, None)


def _frontier_find_phase(
    milestone: dict[str, Any],
    phase_id: str,
) -> dict[str, Any] | None:
    phases = milestone.get("phases")
    if not isinstance(phases, list):
        return None
    for phase in phases:
        if isinstance(phase, dict) and str(phase.get("id", "")).strip() == phase_id:
            return phase
    return None


def _frontier_set_current_frontier(stack: dict[str, Any], state: dict[str, Any]) -> None:
    stack["current_frontier"] = {
        "active_version": str(state.get("active_version", "")).strip(),
        "active_milestone": str(state.get("active_milestone", "")).strip(),
        "active_phase": str(state.get("active_phase", "")).strip(),
        "band": str(state.get("band", "")).strip(),
        "next_action": str(state.get("next_action", "")).strip(),
        "blocked_by": _coerce_string_list(state.get("blocked_by")),
    }


def _frontier_build_roadmap_payload(stack: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    active_version = str(state.get("active_version", "")).strip()
    active_milestone = str(state.get("active_milestone", "")).strip()
    version = _frontier_find_version(stack, active_version) if active_version else None
    _, milestone = _frontier_find_milestone(stack, active_milestone) if active_milestone else (None, None)
    phases = []
    if isinstance(milestone, dict):
        for phase in milestone.get("phases", []) if isinstance(milestone.get("phases"), list) else []:
            if not isinstance(phase, dict):
                continue
            phases.append(
                {
                    "id": str(phase.get("id", "")).strip(),
                    "label": str(phase.get("label", "")).strip(),
                    "status": str(phase.get("status", "")).strip() or "planned",
                    "goal": str(phase.get("goal", "")).strip(),
                    "compute_hooks": list(phase.get("compute_hooks", [])) if isinstance(phase.get("compute_hooks"), list) else [],
                }
            )
    return {
        "schema_version": FRONTIER_SCHEMA_VERSION,
        "kind": "orp_frontier_roadmap",
        "program_id": str(stack.get("program_id", "")).strip(),
        "label": str(stack.get("label", "")).strip(),
        "active_version": active_version,
        "active_version_label": str(version.get("label", "")).strip() if isinstance(version, dict) else "",
        "active_milestone": active_milestone,
        "active_milestone_label": str(milestone.get("label", "")).strip() if isinstance(milestone, dict) else "",
        "band": str(state.get("band", "")).strip(),
        "next_action": str(state.get("next_action", "")).strip(),
        "phases": phases,
    }


def _frontier_build_checklist_payload(stack: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {band: [] for band in FRONTIER_BANDS}
    versions = stack.get("versions")
    if isinstance(versions, list):
        for version in versions:
            if not isinstance(version, dict):
                continue
            milestones = version.get("milestones")
            if not isinstance(milestones, list):
                continue
            for milestone in milestones:
                if not isinstance(milestone, dict):
                    continue
                band = str(milestone.get("band", "")).strip() or "structured"
                if band not in grouped:
                    grouped[band] = []
                phases = milestone.get("phases")
                phase_ids = []
                if isinstance(phases, list):
                    phase_ids = [
                        str(phase.get("id", "")).strip()
                        for phase in phases
                        if isinstance(phase, dict) and str(phase.get("id", "")).strip()
                    ]
                grouped[band].append(
                    {
                        "version_id": str(version.get("id", "")).strip(),
                        "version_label": str(version.get("label", "")).strip(),
                        "milestone_id": str(milestone.get("id", "")).strip(),
                        "milestone_label": str(milestone.get("label", "")).strip(),
                        "band": band,
                        "status": str(milestone.get("status", "")).strip() or "planned",
                        "phase_ids": phase_ids,
                        "is_active": str(milestone.get("id", "")).strip() == str(state.get("active_milestone", "")).strip(),
                    }
                )
    return {
        "schema_version": FRONTIER_SCHEMA_VERSION,
        "kind": "orp_frontier_checklist",
        "program_id": str(stack.get("program_id", "")).strip(),
        "label": str(stack.get("label", "")).strip(),
        "active_version": str(state.get("active_version", "")).strip(),
        "active_milestone": str(state.get("active_milestone", "")).strip(),
        "exact": grouped.get("exact", []),
        "structured": grouped.get("structured", []),
        "horizon": grouped.get("horizon", []),
    }


def _render_frontier_state_md(state: dict[str, Any], stack: dict[str, Any]) -> str:
    lines = [
        f"# Frontier State: {str(stack.get('label', '')).strip() or str(stack.get('program_id', '')).strip()}",
        "",
        f"- active_version: `{str(state.get('active_version', '')).strip() or '(unset)'}`",
        f"- active_milestone: `{str(state.get('active_milestone', '')).strip() or '(unset)'}`",
        f"- active_phase: `{str(state.get('active_phase', '')).strip() or '(unset)'}`",
        f"- band: `{str(state.get('band', '')).strip() or '(unset)'}`",
        f"- next_action: `{str(state.get('next_action', '')).strip() or '(unset)'}`",
    ]
    blockers = _coerce_string_list(state.get("blocked_by"))
    lines.append("- blocked_by:")
    if blockers:
        lines.extend([f"  - `{item}`" for item in blockers])
    else:
        lines.append("  - `(none)`")
    lines.append("")
    return "\n".join(lines)


def _render_frontier_roadmap_md(payload: dict[str, Any]) -> str:
    lines = [
        f"# Roadmap: {payload.get('active_milestone_label') or payload.get('active_milestone') or 'Frontier milestone not set'}",
        "",
        f"- active_version: `{payload.get('active_version', '') or '(unset)'}`",
        f"- active_milestone: `{payload.get('active_milestone', '') or '(unset)'}`",
        f"- band: `{payload.get('band', '') or '(unset)'}`",
        f"- next_action: `{payload.get('next_action', '') or '(unset)'}`",
        "",
        "## Phases",
        "",
    ]
    phases = payload.get("phases", [])
    if isinstance(phases, list) and phases:
        for phase in phases:
            if not isinstance(phase, dict):
                continue
            lines.append(
                f"- [ ] **Phase {phase.get('id', '')}: {phase.get('label', '')}** - {phase.get('goal', '') or 'goal not yet specified'}"
            )
    else:
        lines.append("- `(no active milestone phases yet)`")
    lines.append("")
    return "\n".join(lines)


def _render_frontier_checklist_md(payload: dict[str, Any]) -> str:
    lines = [
        f"# Frontier Checklist: {payload.get('label', '') or payload.get('program_id', '')}",
        "",
    ]
    for band in FRONTIER_BANDS:
        rows = payload.get(band, [])
        lines.append(f"## {band.title()}")
        lines.append("")
        if isinstance(rows, list) and rows:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                active = " active" if row.get("is_active") else ""
                lines.append(
                    f"- [ ] `{row.get('milestone_id', '')}` {row.get('milestone_label', '')} (`{row.get('version_id', '')}` / `{row.get('status', '')}`{active})"
                )
        else:
            lines.append("- `(none)`")
        lines.append("")
    return "\n".join(lines)


def _render_frontier_stack_md(stack: dict[str, Any]) -> str:
    lines = [
        f"# Version Stack: {str(stack.get('label', '')).strip() or str(stack.get('program_id', '')).strip()}",
        "",
    ]
    versions = stack.get("versions")
    if isinstance(versions, list) and versions:
        for version in versions:
            if not isinstance(version, dict):
                continue
            lines.append(f"## `{version.get('id', '')}` {version.get('label', '')}")
            lines.append("")
            lines.append(f"- status: `{version.get('status', '') or 'planned'}`")
            intent = str(version.get("intent", "")).strip()
            if intent:
                lines.append(f"- intent: `{intent}`")
            milestones = version.get("milestones")
            lines.append("- milestones:")
            if isinstance(milestones, list) and milestones:
                for milestone in milestones:
                    if not isinstance(milestone, dict):
                        continue
                    lines.append(
                        f"  - `{milestone.get('id', '')}` {milestone.get('label', '')} (`{milestone.get('band', '')}` / `{milestone.get('status', '') or 'planned'}`)"
                    )
            else:
                lines.append("  - `(none)`")
            lines.append("")
    else:
        lines.append("- `(no versions yet)`")
        lines.append("")
    return "\n".join(lines)


def _frontier_write_materialized_views(repo_root: Path, stack: dict[str, Any], state: dict[str, Any]) -> dict[str, str]:
    paths = _frontier_paths(repo_root)
    paths["root"].mkdir(parents=True, exist_ok=True)
    _frontier_set_current_frontier(stack, state)
    roadmap = _frontier_build_roadmap_payload(stack, state)
    checklist = _frontier_build_checklist_payload(stack, state)
    _write_json(paths["state_json"], state)
    _write_json(paths["stack_json"], stack)
    _write_json(paths["roadmap_json"], roadmap)
    _write_json(paths["checklist_json"], checklist)
    _write_text(paths["state_md"], _render_frontier_state_md(state, stack) + "\n")
    _write_text(paths["roadmap_md"], _render_frontier_roadmap_md(roadmap) + "\n")
    _write_text(paths["checklist_md"], _render_frontier_checklist_md(checklist) + "\n")
    _write_text(paths["stack_md"], _render_frontier_stack_md(stack) + "\n")
    return {key: _path_for_state(value, repo_root) for key, value in paths.items() if key != "root"}


def _frontier_default_label(repo_root: Path, program_id: str) -> str:
    clean = str(program_id).strip()
    if clean:
        return clean.replace("-", " ").replace("_", " ").title()
    return f"{repo_root.name or 'Repo'} Frontier"


def _frontier_doctor_payload(repo_root: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    paths = _frontier_paths(repo_root)
    stack = _read_json_if_exists(paths["stack_json"])
    state = _read_json_if_exists(paths["state_json"])

    if not stack:
        issues.append({"severity": "error", "code": "missing_stack", "message": "frontier version stack is missing."})
    if not state:
        issues.append({"severity": "error", "code": "missing_state", "message": "frontier state is missing."})

    if stack and state:
        active_version = str(state.get("active_version", "")).strip()
        active_milestone = str(state.get("active_milestone", "")).strip()
        active_phase = str(state.get("active_phase", "")).strip()
        version = _frontier_find_version(stack, active_version) if active_version else None
        _, milestone = _frontier_find_milestone(stack, active_milestone) if active_milestone else (None, None)
        if active_version and version is None:
            issues.append(
                {"severity": "error", "code": "missing_active_version", "message": f"active version `{active_version}` does not exist in version stack."}
            )
        if active_milestone and milestone is None:
            issues.append(
                {"severity": "error", "code": "missing_active_milestone", "message": f"active milestone `{active_milestone}` does not exist in version stack."}
            )
        if active_phase and isinstance(milestone, dict) and _frontier_find_phase(milestone, active_phase) is None:
            issues.append(
                {"severity": "error", "code": "missing_active_phase", "message": f"active phase `{active_phase}` does not exist in active milestone `{active_milestone}`."}
            )
        versions = stack.get("versions")
        if isinstance(versions, list):
            exact_milestones = 0
            for version_row in versions:
                if not isinstance(version_row, dict):
                    continue
                milestones = version_row.get("milestones")
                if not isinstance(milestones, list):
                    continue
                for milestone_row in milestones:
                    if not isinstance(milestone_row, dict):
                        continue
                    band = str(milestone_row.get("band", "")).strip()
                    if band and band not in FRONTIER_BANDS:
                        issues.append(
                            {"severity": "error", "code": "invalid_band", "message": f"milestone `{milestone_row.get('id', '')}` uses unsupported band `{band}`."}
                        )
                    if band == "exact":
                        exact_milestones += 1
            if exact_milestones > 1:
                issues.append(
                    {"severity": "warning", "code": "multiple_exact_milestones", "message": f"{exact_milestones} milestones are marked exact; the planning rule expects only one live exact milestone."}
                )

    return {
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "issues": issues,
        "paths": {key: _path_for_state(value, repo_root) for key, value in paths.items()},
    }


def _write_text_if_missing(path: Path, text: str) -> str:
    if path.exists():
        return "kept"
    _write_text(path, text)
    return "created"


def _git_run(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git is required for ORP repo governance but was not found on PATH.") from exc


def _git_stdout(repo_root: Path, args: list[str]) -> str:
    proc = _git_run(repo_root, args)
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _git_error_detail(proc: subprocess.CompletedProcess[str]) -> str:
    return proc.stderr.strip() or proc.stdout.strip() or "git command failed"


def _git_require_success(repo_root: Path, args: list[str], *, context: str) -> subprocess.CompletedProcess[str]:
    proc = _git_run(repo_root, args)
    if proc.returncode != 0:
        raise RuntimeError(f"{context}: {_git_error_detail(proc)}")
    return proc


def _git_repo_present(repo_root: Path) -> bool:
    return _git_stdout(repo_root, ["rev-parse", "--is-inside-work-tree"]) == "true"


def _git_dir_path(repo_root: Path) -> Path | None:
    raw = _git_stdout(repo_root, ["rev-parse", "--git-dir"])
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    return path


def _git_current_branch(repo_root: Path) -> str:
    branch = _git_stdout(repo_root, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    if branch:
        return branch
    branch = _git_stdout(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch == "HEAD":
        return ""
    return branch


def _git_has_commits(repo_root: Path) -> bool:
    proc = _git_run(repo_root, ["rev-parse", "--verify", "HEAD"])
    return proc.returncode == 0


def _git_status_lines(repo_root: Path) -> list[str]:
    proc = _git_run(repo_root, ["status", "--short"])
    if proc.returncode != 0:
        return []
    return [line.rstrip() for line in proc.stdout.splitlines() if line.strip()]


def _git_branch_exists(repo_root: Path, branch_name: str) -> bool:
    proc = _git_run(repo_root, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"])
    return proc.returncode == 0


def _git_commit_exists(repo_root: Path) -> bool:
    return _git_has_commits(repo_root)


def _parse_iso8601_utc(raw: Any) -> dt.datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _git_upstream_branch(repo_root: Path) -> str:
    return _git_stdout(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])


def _git_remote_default_branch(repo_root: Path, remote_name: str) -> str:
    if not remote_name:
        return ""
    ref = _git_stdout(repo_root, ["symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote_name}/HEAD"])
    if not ref:
        return ""
    prefix = f"{remote_name}/"
    if ref.startswith(prefix):
        return ref[len(prefix) :]
    return ref


def _git_remote_branch_exists(repo_root: Path, remote_name: str, branch_name: str) -> bool:
    if not remote_name or not branch_name:
        return False
    proc = _git_run(repo_root, ["show-ref", "--verify", "--quiet", f"refs/remotes/{remote_name}/{branch_name}"])
    return proc.returncode == 0


def _git_ahead_behind(repo_root: Path, left_ref: str, right_ref: str) -> tuple[int, int] | None:
    if not left_ref or not right_ref:
        return None
    proc = _git_run(repo_root, ["rev-list", "--left-right", "--count", f"{left_ref}...{right_ref}"])
    if proc.returncode != 0:
        return None
    parts = proc.stdout.strip().split()
    if len(parts) != 2:
        return None
    try:
        ahead = int(parts[0])
        behind = int(parts[1])
    except Exception:
        return None
    return ahead, behind


def _git_branch_inventory(repo_root: Path) -> list[dict[str, Any]]:
    proc = _git_run(
        repo_root,
        [
            "for-each-ref",
            "refs/heads",
            "--format=%(refname:short)\t%(objectname:short)\t%(upstream:short)\t%(upstream:track)\t%(committerdate:iso-strict)\t%(subject)",
        ],
    )
    if proc.returncode != 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 6:
            continue
        rows.append(
            {
                "name": parts[0],
                "commit": parts[1],
                "upstream": parts[2],
                "track": parts[3],
                "committed_at_utc": parts[4],
                "subject": parts[5],
            }
        )
    return rows


def _default_git_runtime_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "initialized_at_utc": "",
        "last_init": {},
        "last_branch_action": {},
        "branch_transitions": [],
        "last_checkpoint": {},
        "checkpoint_history": [],
        "last_backup": {},
        "backup_history": [],
        "last_ready": {},
        "ready_history": [],
        "last_doctor": {},
        "doctor_history": [],
        "last_cleanup": {},
        "cleanup_history": [],
    }


def _git_runtime_path(repo_root: Path) -> Path | None:
    git_dir = _git_dir_path(repo_root)
    if git_dir is None:
        return None
    return git_dir / "orp" / "runtime.json"


def _read_git_runtime(repo_root: Path) -> dict[str, Any]:
    path = _git_runtime_path(repo_root)
    if path is None:
        return _default_git_runtime_payload()
    payload = _read_json_if_exists(path)
    return {
        **_default_git_runtime_payload(),
        **payload,
    }


def _write_git_runtime(repo_root: Path, payload: dict[str, Any]) -> None:
    path = _git_runtime_path(repo_root)
    if path is None:
        return
    merged = {
        **_default_git_runtime_payload(),
        **payload,
    }
    _write_json(path, merged)


def _normalize_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    text = str(raw or "").strip().lower()
    return text in {"1", "true", "yes", "on"}


def _normalize_timestamp_utc(raw: Any, *, fallback: str = "") -> str:
    parsed = _parse_iso8601_utc(raw)
    if parsed is None:
        return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    else:
        parsed = parsed.astimezone(dt.timezone.utc)
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_local_path(raw: Any, repo_root: Path, *, fallback: str = "") -> str:
    text = str(raw or "").strip() or str(fallback or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    else:
        path = path.resolve()
    return str(path)


def _link_root_path(repo_root: Path) -> Path | None:
    git_dir = _git_dir_path(repo_root)
    if git_dir is None:
        return None
    return git_dir / "orp" / "link"


def _require_link_root(repo_root: Path) -> Path:
    path = _link_root_path(repo_root)
    if path is None:
        raise RuntimeError("git repository not detected. Run `orp init` or `git init` first.")
    return path


def _link_project_path(repo_root: Path) -> Path | None:
    root = _link_root_path(repo_root)
    if root is None:
        return None
    return root / "project.json"


def _link_sessions_dir(repo_root: Path) -> Path | None:
    root = _link_root_path(repo_root)
    if root is None:
        return None
    return root / "sessions"


def _link_session_filename(orp_session_id: str) -> str:
    session_id = str(orp_session_id).strip()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", session_id).strip("._-") or "session"
    digest = hashlib.sha1(session_id.encode("utf-8")).hexdigest()[:12]
    return f"{safe}-{digest}.json"


def _link_session_path(repo_root: Path, orp_session_id: str) -> Path | None:
    sessions_dir = _link_sessions_dir(repo_root)
    if sessions_dir is None:
        return None
    return sessions_dir / _link_session_filename(orp_session_id)


def _normalize_terminal_target(raw: Any) -> dict[str, int] | None:
    if not isinstance(raw, dict):
        return None
    try:
        window_id = int(raw.get("window_id", raw.get("windowId")))
        tab_number = int(raw.get("tab_number", raw.get("tabNumber")))
    except Exception:
        return None
    return {
        "window_id": window_id,
        "tab_number": tab_number,
    }


def _normalize_link_project_payload(
    raw: dict[str, Any],
    repo_root: Path,
    *,
    default_source: str = "cli",
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError("linked project payload must be an object.")
    idea_id = str(raw.get("idea_id", raw.get("ideaId", ""))).strip()
    if not idea_id:
        raise RuntimeError("linked project requires idea_id.")
    project_root = _normalize_local_path(
        raw.get("project_root", raw.get("projectRoot", str(repo_root))),
        repo_root,
        fallback=str(repo_root),
    )
    if not project_root:
        raise RuntimeError("linked project requires project_root.")
    source = str(raw.get("source", default_source)).strip()
    if source not in {"cli", "rust-app", "import-rust"}:
        source = default_source
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "idea_id": idea_id,
        "project_root": project_root,
        "linked_at_utc": _normalize_timestamp_utc(
            raw.get("linked_at_utc", raw.get("linkedAt", raw.get("linked_at"))),
            fallback=_now_utc(),
        ),
    }
    for key, aliases in {
        "idea_title": ["idea_title", "ideaTitle"],
        "world_id": ["world_id", "worldId"],
        "world_name": ["world_name", "worldName", "name"],
        "github_url": ["github_url", "githubUrl"],
        "linked_email": ["linked_email", "linkedEmail"],
        "notes": ["notes"],
    }.items():
        value = ""
        for alias in aliases:
            value = str(raw.get(alias, "")).strip()
            if value:
                break
        if value:
            payload[key] = value
    payload["source"] = source
    return payload


def _normalize_link_session_payload(
    raw: dict[str, Any],
    repo_root: Path,
    *,
    default_source: str = "cli",
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError("linked session payload must be an object.")
    orp_session_id = str(
        raw.get("orp_session_id", raw.get("orpSessionId", raw.get("session_id", raw.get("sessionId", ""))))
    ).strip()
    if not orp_session_id:
        raise RuntimeError("linked session requires orp_session_id.")
    label = str(raw.get("label", "")).strip()
    if not label:
        raise RuntimeError("linked session requires label.")
    project_root = _normalize_local_path(
        raw.get(
            "project_root",
            raw.get("projectRoot", raw.get("project_path", raw.get("projectPath", str(repo_root)))),
        ),
        repo_root,
        fallback=str(repo_root),
    )
    if not project_root:
        raise RuntimeError("linked session requires project_root.")
    state = str(raw.get("state", "active")).strip().lower() or "active"
    if state not in {"active", "closed"}:
        state = "active"
    created_at_utc = _normalize_timestamp_utc(
        raw.get("created_at_utc", raw.get("createdAt", raw.get("created_at"))),
        fallback=_now_utc(),
    )
    last_active_at_utc = _normalize_timestamp_utc(
        raw.get("last_active_at_utc", raw.get("lastActiveAt", raw.get("last_active_at"))),
        fallback=created_at_utc,
    )
    archived = _normalize_bool(raw.get("archived", False))
    primary = _normalize_bool(raw.get("primary", False)) and not archived
    source = str(raw.get("source", default_source)).strip()
    if source not in {"cli", "rust-app", "import-rust"}:
        source = default_source
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "orp_session_id": orp_session_id,
        "label": label,
        "state": state,
        "project_root": project_root,
        "created_at_utc": created_at_utc,
        "last_active_at_utc": last_active_at_utc,
        "archived": archived,
        "primary": primary,
        "source": source,
    }
    codex_session_id = str(raw.get("codex_session_id", raw.get("codexSessionId", ""))).strip()
    if codex_session_id:
        payload["codex_session_id"] = codex_session_id
    role = str(raw.get("role", "")).strip().lower()
    if role in {"primary", "secondary", "review", "exploration", "other"}:
        payload["role"] = role
    terminal_target = _normalize_terminal_target(raw.get("terminal_target", raw.get("terminalTarget")))
    if terminal_target is not None:
        payload["terminal_target"] = terminal_target
    notes = str(raw.get("notes", "")).strip()
    if notes:
        payload["notes"] = notes
    return payload


def _read_link_project(repo_root: Path) -> dict[str, Any]:
    path = _link_project_path(repo_root)
    if path is None or not path.exists():
        return {}
    raw = _read_json_if_exists(path)
    if not raw:
        return {}
    try:
        return _normalize_link_project_payload(raw, repo_root, default_source=str(raw.get("source", "cli")).strip() or "cli")
    except RuntimeError:
        return {}


def _write_link_project(repo_root: Path, payload: dict[str, Any]) -> Path:
    path = _require_link_root(repo_root) / "project.json"
    normalized = _normalize_link_project_payload(payload, repo_root)
    _write_json(path, normalized)
    return path


def _delete_link_project(repo_root: Path) -> Path | None:
    path = _link_project_path(repo_root)
    if path is None or not path.exists():
        return None
    path.unlink()
    return path


def _link_session_sort_key(payload: dict[str, Any]) -> tuple[bool, bool, bool, float, str]:
    timestamp = _parse_iso8601_utc(payload.get("last_active_at_utc"))
    ts_value = timestamp.timestamp() if timestamp is not None else 0.0
    return (
        not bool(payload.get("primary", False)),
        bool(payload.get("archived", False)),
        str(payload.get("state", "active")).strip() != "active",
        -ts_value,
        str(payload.get("label", "")).strip().lower(),
    )


def _read_link_session(repo_root: Path, orp_session_id: str) -> dict[str, Any]:
    path = _link_session_path(repo_root, orp_session_id)
    if path is None or not path.exists():
        return {}
    raw = _read_json_if_exists(path)
    if not raw:
        return {}
    try:
        payload = _normalize_link_session_payload(raw, repo_root, default_source=str(raw.get("source", "cli")).strip() or "cli")
    except RuntimeError:
        return {}
    payload["path"] = _path_for_state(path, repo_root)
    return payload


def _list_link_sessions(repo_root: Path) -> list[dict[str, Any]]:
    sessions_dir = _link_sessions_dir(repo_root)
    if sessions_dir is None or not sessions_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(sessions_dir.glob("*.json")):
        raw = _read_json_if_exists(path)
        if not raw:
            continue
        try:
            payload = _normalize_link_session_payload(
                raw,
                repo_root,
                default_source=str(raw.get("source", "cli")).strip() or "cli",
            )
        except RuntimeError:
            continue
        payload["path"] = _path_for_state(path, repo_root)
        rows.append(payload)
    return sorted(rows, key=_link_session_sort_key)


def _write_link_session(repo_root: Path, payload: dict[str, Any]) -> Path:
    normalized = _normalize_link_session_payload(payload, repo_root)
    path = _require_link_root(repo_root) / "sessions" / _link_session_filename(normalized["orp_session_id"])
    _write_json(path, normalized)
    return path


def _delete_link_session(repo_root: Path, orp_session_id: str) -> Path | None:
    path = _link_session_path(repo_root, orp_session_id)
    if path is None or not path.exists():
        return None
    path.unlink()
    return path


def _set_primary_link_session(repo_root: Path, orp_session_id: str) -> None:
    sessions_dir = _link_sessions_dir(repo_root)
    if sessions_dir is None or not sessions_dir.exists():
        return
    for path in sorted(sessions_dir.glob("*.json")):
        raw = _read_json_if_exists(path)
        if not raw:
            continue
        try:
            payload = _normalize_link_session_payload(
                raw,
                repo_root,
                default_source=str(raw.get("source", "cli")).strip() or "cli",
            )
        except RuntimeError:
            continue
        payload["primary"] = payload["orp_session_id"] == orp_session_id and not payload["archived"]
        _write_json(path, payload)


def _rebalance_primary_link_session(repo_root: Path) -> dict[str, Any]:
    sessions = _list_link_sessions(repo_root)
    eligible = [row for row in sessions if not row.get("archived")]
    current_primaries = [row for row in eligible if row.get("primary")]
    if len(current_primaries) == 1:
        return current_primaries[0]
    target = {}
    if len(current_primaries) > 1:
        target = current_primaries[0]
    elif eligible:
        active = [row for row in eligible if str(row.get("state", "active")).strip() == "active"]
        target = active[0] if active else eligible[0]
    if target:
        _set_primary_link_session(repo_root, str(target.get("orp_session_id", "")).strip())
        return _read_link_session(repo_root, str(target.get("orp_session_id", "")).strip())
    for row in sessions:
        path = _link_session_path(repo_root, str(row.get("orp_session_id", "")).strip())
        if path is None:
            continue
        payload = dict(row)
        payload.pop("path", None)
        payload["primary"] = False
        _write_json(path, payload)
    return {}


def _normalize_remote_world_payload(payload: dict[str, Any]) -> dict[str, Any]:
    world = payload.get("world") if isinstance(payload.get("world"), dict) else payload
    if not isinstance(world, dict):
        raise RuntimeError("Hosted ORP returned an invalid world payload.")
    return {
        "ok": bool(payload.get("ok", True)),
        "world": dict(world),
    }


def _link_session_counts(sessions: list[dict[str, Any]]) -> dict[str, int]:
    active = [row for row in sessions if not row.get("archived") and str(row.get("state", "active")).strip() == "active"]
    archived = [row for row in sessions if row.get("archived")]
    routeable = [row for row in active if str(row.get("codex_session_id", "")).strip()]
    primary = [row for row in sessions if row.get("primary")]
    return {
        "total": len(sessions),
        "active": len(active),
        "archived": len(archived),
        "routeable": len(routeable),
        "primary": len(primary),
    }


def _link_status_payload(repo_root: Path, args: argparse.Namespace, *, refresh_remote_world: bool = True) -> dict[str, Any]:
    project_link = _read_link_project(repo_root)
    project_link_path = _link_project_path(repo_root)
    sessions = _list_link_sessions(repo_root)
    primary_session = next((row for row in sessions if row.get("primary")), {})
    governance = _governance_status_payload(repo_root, args.config)
    hosted_session = _load_hosted_session()
    hosted_session["base_url"] = _resolve_hosted_base_url(args, hosted_session)
    hosted_auth = _session_summary(hosted_session)
    hosted_world: dict[str, Any] = {}
    hosted_world_error = ""
    if project_link and hosted_auth.get("connected") and refresh_remote_world:
        try:
            payload = _request_hosted_json(
                base_url=_resolve_hosted_base_url(args, hosted_session),
                path=f"/api/cli/ideas/{urlparse.quote(str(project_link.get('idea_id', '')).strip())}/world",
                token=str(hosted_session.get("token", "")).strip(),
            )
            if isinstance(payload, dict):
                hosted_world = _normalize_remote_world_payload(payload)["world"]
        except Exception as exc:
            hosted_world_error = str(exc)

    warnings: list[str] = []
    notes: list[str] = []
    next_actions: list[str] = []
    if not governance.get("orp_governed"):
        notes.append("repo governance is not initialized yet.")
        next_actions.append("orp init")
    if not governance.get("git", {}).get("present"):
        warnings.append("git repository not detected for local link/session state.")
        next_actions.append("orp init")
    if not project_link:
        warnings.append("project is not linked to a hosted idea/world yet.")
        next_actions.append("orp link project bind --idea-id <idea-id> --json")
    if not sessions:
        warnings.append("no linked sessions are registered for this repo.")
        next_actions.append(
            "orp link session register --orp-session-id <session-id> --label <label> --codex-session-id <codex-session-id> --primary --json"
        )
    if sessions and not primary_session:
        warnings.append("no primary linked session is selected.")
        next_actions.append("orp link session set-primary <orp_session_id> --json")
    if primary_session and not str(primary_session.get("codex_session_id", "")).strip():
        warnings.append(
            f"primary session `{primary_session.get('orp_session_id', '')}` is missing a Codex session id."
        )
        next_actions.append(
            f"orp link session register --orp-session-id {primary_session.get('orp_session_id', '')} --label \"{primary_session.get('label', '')}\" --codex-session-id <codex-session-id> --json"
        )
    if project_link and not hosted_auth.get("connected"):
        warnings.append("hosted auth is not connected; remote link sync and delivery are unavailable.")
        next_actions.append("orp auth login")
    if hosted_world_error:
        warnings.append(f"unable to refresh hosted world state: {hosted_world_error}")
    if hosted_world and project_link:
        remote_root = _normalize_local_path(hosted_world.get("projectRoot", ""), repo_root)
        local_root = str(project_link.get("project_root", "")).strip()
        if remote_root and local_root and remote_root != local_root:
            warnings.append("hosted world project root does not match the local linked project root.")
        remote_codex_session_id = str(hosted_world.get("codexSessionId", "")).strip()
        primary_codex_session_id = str(primary_session.get("codex_session_id", "")).strip()
        if remote_codex_session_id and primary_codex_session_id and remote_codex_session_id != primary_codex_session_id:
            warnings.append("hosted world primary Codex session id does not match the local primary linked session.")
        world_id = str(project_link.get("world_id", "")).strip()
        remote_world_id = str(hosted_world.get("id", "")).strip()
        if world_id and remote_world_id and world_id != remote_world_id:
            warnings.append("hosted world id does not match the locally recorded linked world id.")

    session_counts = _link_session_counts(sessions)
    routeable_sessions = [
        row
        for row in sessions
        if not row.get("archived")
        and str(row.get("state", "active")).strip() == "active"
        and str(row.get("codex_session_id", "")).strip()
    ]
    return {
        "ok": True,
        "repo_root": str(repo_root),
        "project_link_path": _path_for_state(project_link_path, repo_root) if project_link_path is not None else "",
        "project_link_exists": bool(project_link),
        "project_link": project_link,
        "sessions": sessions,
        "session_counts": session_counts,
        "primary_session": primary_session,
        "routeable_sessions": routeable_sessions,
        "routing_ready": bool(project_link) and bool(primary_session) and bool(routeable_sessions),
        "hosted_auth": hosted_auth,
        "hosted_world": hosted_world,
        "hosted_world_error": hosted_world_error,
        "governance": governance,
        "warnings": _unique_strings(warnings),
        "notes": _unique_strings(notes),
        "next_actions": _unique_strings(next_actions),
    }


def _runner_machine_path() -> Path:
    return _orp_user_dir() / "machine.json"


def _runner_repo_path(repo_root: Path) -> Path | None:
    root = _link_root_path(repo_root)
    if root is None:
        return None
    return root / "runner.json"


def _runner_runtime_path(repo_root: Path) -> Path | None:
    root = _link_root_path(repo_root)
    if root is None:
        return None
    return root / "runtime.json"


def _runner_platform_name() -> str:
    system = platform.system().strip().lower()
    if system == "darwin":
        return "macos"
    if system.startswith("win"):
        return "windows"
    if system:
        return system
    return sys.platform.strip().lower() or "unknown"


def _default_runner_machine_payload(*, machine_id: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "machine_id": machine_id or str(uuid.uuid4()),
        "machine_name": platform.node().strip() or "This Machine",
        "platform": _runner_platform_name(),
        "app_version": ORP_TOOL_VERSION,
        "runner_enabled": False,
    }
    return payload


def _default_runner_runtime_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "status": "idle",
        "updated_at_utc": "",
        "active_job": {},
        "last_job": {},
        "recent_events": [],
    }


def _normalize_runner_runtime_job(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key in (
        "job_id",
        "job_kind",
        "lease_id",
        "checkpoint_id",
        "idea_id",
        "world_id",
        "project_root",
        "repo_root",
        "orp_session_id",
        "codex_session_id",
        "status",
        "summary",
        "error",
    ):
        value = str(raw.get(key, "")).strip()
        if value:
            normalized[key] = value
    for key in (
        "claimed_at_utc",
        "started_at_utc",
        "last_heartbeat_at_utc",
        "lease_expires_at_utc",
        "finished_at_utc",
    ):
        value = _normalize_timestamp_utc(raw.get(key), fallback="")
        if value:
            normalized[key] = value
    return normalized


def _normalize_runner_runtime_event(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    event: dict[str, Any] = {}
    timestamp = _normalize_timestamp_utc(raw.get("timestamp_utc"), fallback="")
    if timestamp:
        event["timestamp_utc"] = timestamp
    for key in ("status", "job_id", "lease_id", "message"):
        value = str(raw.get(key, "")).strip()
        if value:
            event[key] = value
    return event


def _normalize_runner_runtime_payload(raw: Any) -> dict[str, Any]:
    payload = _default_runner_runtime_payload()
    if not isinstance(raw, dict):
        return payload
    recent_rows = raw.get("recent_events", raw.get("recentEvents", []))
    if not isinstance(recent_rows, list):
        recent_rows = []
    normalized = {
        "schema_version": "1.0.0",
        "status": str(raw.get("status", "idle")).strip().lower() or "idle",
        "updated_at_utc": _normalize_timestamp_utc(raw.get("updated_at_utc"), fallback=""),
        "active_job": _normalize_runner_runtime_job(raw.get("active_job", raw.get("activeJob"))),
        "last_job": _normalize_runner_runtime_job(raw.get("last_job", raw.get("lastJob"))),
        "recent_events": [
            event for event in (_normalize_runner_runtime_event(row) for row in recent_rows)
            if event
        ][-25:],
    }
    if normalized["status"] not in {"idle", "claimed", "running"}:
        normalized["status"] = "idle"
    if not normalized["active_job"]:
        normalized["status"] = "idle"
    return normalized


def _normalize_runner_machine_payload(
    raw: dict[str, Any],
    *,
    default_machine_id: str = "",
    default_machine_name: str = "",
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError("runner machine payload must be an object.")
    payload = _default_runner_machine_payload(machine_id=default_machine_id)
    machine_id = str(raw.get("machine_id", raw.get("machineId", payload["machine_id"]))).strip() or payload["machine_id"]
    machine_name = (
        str(raw.get("machine_name", raw.get("machineName", default_machine_name or payload["machine_name"]))).strip()
        or default_machine_name
        or payload["machine_name"]
    )
    normalized: dict[str, Any] = {
        "schema_version": "1.0.0",
        "machine_id": machine_id,
        "machine_name": machine_name,
        "platform": str(raw.get("platform", payload["platform"])).strip() or payload["platform"],
        "app_version": str(raw.get("app_version", raw.get("appVersion", ORP_TOOL_VERSION))).strip() or ORP_TOOL_VERSION,
        "runner_enabled": _normalize_bool(raw.get("runner_enabled", raw.get("runnerEnabled", False))),
    }
    linked_email = str(raw.get("linked_email", raw.get("linkedEmail", ""))).strip()
    if linked_email:
        normalized["linked_email"] = linked_email
    last_heartbeat = _normalize_timestamp_utc(
        raw.get("last_heartbeat_at_utc", raw.get("lastHeartbeatAt")),
        fallback="",
    )
    if last_heartbeat:
        normalized["last_heartbeat_at_utc"] = last_heartbeat
    last_sync = _normalize_timestamp_utc(
        raw.get("last_sync_at_utc", raw.get("lastSyncAt")),
        fallback="",
    )
    if last_sync:
        normalized["last_sync_at_utc"] = last_sync
    return normalized


def _load_runner_machine() -> dict[str, Any]:
    path = _runner_machine_path()
    raw = _read_json_if_exists(path)
    default_payload = _default_runner_machine_payload()
    if raw:
        try:
            payload = _normalize_runner_machine_payload(
                raw,
                default_machine_id=str(default_payload["machine_id"]),
                default_machine_name=str(default_payload["machine_name"]),
            )
        except RuntimeError:
            payload = default_payload
    else:
        payload = default_payload
    if not path.exists() or not raw:
        _write_json(path, payload)
    return payload


def _save_runner_machine(payload: dict[str, Any]) -> Path:
    path = _runner_machine_path()
    current = _load_runner_machine()
    normalized = _normalize_runner_machine_payload(
        {**current, **payload},
        default_machine_id=str(current.get("machine_id", "")),
        default_machine_name=str(current.get("machine_name", "")),
    )
    _write_json(path, normalized)
    return path


def _read_runner_runtime(repo_root: Path) -> dict[str, Any]:
    path = _runner_runtime_path(repo_root)
    if path is None or not path.exists():
        return _default_runner_runtime_payload()
    raw = _read_json_if_exists(path)
    if not raw:
        return _default_runner_runtime_payload()
    return _normalize_runner_runtime_payload(raw)


def _write_runner_runtime(repo_root: Path, payload: dict[str, Any]) -> Path:
    path = _runner_runtime_path(repo_root)
    if path is None:
        raise RuntimeError("git repository not detected. Run `orp init` or `git init` first.")
    current = _read_runner_runtime(repo_root)
    normalized = _normalize_runner_runtime_payload({**current, **payload})
    normalized["updated_at_utc"] = _normalize_timestamp_utc(
        normalized.get("updated_at_utc"),
        fallback=_now_utc(),
    )
    _write_json(path, normalized)
    return path


def _update_runner_runtime(
    repo_root: Path,
    *,
    status: str | None = None,
    active_job: dict[str, Any] | None = None,
    last_job: dict[str, Any] | None = None,
    clear_active: bool = False,
    event: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Path]:
    current = _read_runner_runtime(repo_root)
    payload = {
        "schema_version": "1.0.0",
        "status": current.get("status", "idle"),
        "updated_at_utc": _now_utc(),
        "active_job": current.get("active_job", {}),
        "last_job": current.get("last_job", {}),
        "recent_events": list(current.get("recent_events", [])),
    }
    if status is not None:
        payload["status"] = str(status).strip().lower() or payload["status"]
    if clear_active:
        payload["active_job"] = {}
    if active_job is not None:
        payload["active_job"] = active_job
    if last_job is not None:
        payload["last_job"] = last_job
    if event:
        _append_bounded_event_list(payload, "recent_events", event)
    path = _write_runner_runtime(repo_root, payload)
    return _read_runner_runtime(repo_root), path


def _read_runner_repo_state(repo_root: Path) -> dict[str, Any]:
    path = _runner_repo_path(repo_root)
    if path is None or not path.exists():
        return {}
    raw = _read_json_if_exists(path)
    if not raw:
        return {}
    machine = _load_runner_machine()
    try:
        return _normalize_runner_machine_payload(
            raw,
            default_machine_id=str(machine.get("machine_id", "")),
            default_machine_name=str(machine.get("machine_name", "")),
        )
    except RuntimeError:
        return {}


def _write_runner_repo_state(repo_root: Path, payload: dict[str, Any]) -> Path:
    path = _runner_repo_path(repo_root)
    if path is None:
        raise RuntimeError("git repository not detected. Run `orp init` or `git init` first.")
    machine = _load_runner_machine()
    normalized = _normalize_runner_machine_payload(
        {**machine, **payload},
        default_machine_id=str(machine.get("machine_id", "")),
        default_machine_name=str(machine.get("machine_name", "")),
    )
    _write_json(path, normalized)
    return path


def _runner_runtime_event(
    *,
    status: str,
    message: str = "",
    job_id: str = "",
    lease_id: str = "",
    timestamp_utc: str = "",
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "status": str(status).strip().lower() or "idle",
        "timestamp_utc": _normalize_timestamp_utc(timestamp_utc, fallback=_now_utc()),
    }
    if str(job_id).strip():
        event["job_id"] = str(job_id).strip()
    if str(lease_id).strip():
        event["lease_id"] = str(lease_id).strip()
    if str(message).strip():
        event["message"] = str(message).strip()
    return event


def _runner_sync_payload_for_repo(
    repo_root: Path,
    machine: dict[str, Any],
    link_status: dict[str, Any],
    *,
    synced_at_utc: str = "",
) -> dict[str, Any]:
    synced_at_value = _normalize_timestamp_utc(synced_at_utc, fallback=_now_utc())
    project_link = link_status.get("project_link", {}) if isinstance(link_status.get("project_link"), dict) else {}
    idea_id = str(project_link.get("idea_id", "")).strip()
    world_id = str(project_link.get("world_id", "")).strip() or None
    project_root = str(project_link.get("project_root", str(repo_root))).strip() or str(repo_root)
    linked_projects: list[dict[str, Any]] = []
    if idea_id:
        linked_projects.append(
            {
                "ideaId": idea_id,
                "ideaTitle": str(project_link.get("idea_title", "")).strip() or repo_root.name,
                "worldId": world_id,
                "worldName": str(project_link.get("world_name", "")).strip() or None,
                "projectName": repo_root.name,
                "projectRoot": project_root,
                "githubUrl": str(project_link.get("github_url", "")).strip() or None,
                "lastOpenedAt": _now_utc(),
            }
        )

    sessions: list[dict[str, Any]] = []
    for row in link_status.get("sessions", []):
        if not isinstance(row, dict) or row.get("archived"):
            continue
        sessions.append(
            {
                "ideaId": idea_id,
                "worldId": world_id,
                "projectRoot": str(row.get("project_root", project_root)).strip() or project_root,
                "orpSessionId": str(row.get("orp_session_id", "")).strip(),
                "codexSessionId": str(row.get("codex_session_id", "")).strip() or None,
                "label": str(row.get("label", "")).strip(),
                "state": str(row.get("state", "active")).strip() or "active",
                "primary": bool(row.get("primary")),
                "lastActiveAt": str(row.get("last_active_at_utc", "")).strip() or None,
            }
        )

    return {
        "machineId": str(machine.get("machine_id", "")).strip(),
        "machineName": str(machine.get("machine_name", "")).strip(),
        "platform": str(machine.get("platform", _runner_platform_name())).strip() or _runner_platform_name(),
        "appVersion": str(machine.get("app_version", ORP_TOOL_VERSION)).strip() or ORP_TOOL_VERSION,
        "syncedAt": synced_at_value,
        "linkedProjects": linked_projects,
        "sessions": sessions,
    }


def _normalize_runner_sync_roots(repo_root: Path, raw_roots: Sequence[str] | None) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()

    def add_root(raw_value: str | Path) -> None:
        text = str(raw_value).strip()
        if not text:
            return
        try:
            candidate = Path(text).expanduser().resolve()
        except Exception:
            candidate = Path(text).expanduser()
        key = str(candidate)
        if key in seen:
            return
        seen.add(key)
        roots.append(candidate)

    add_root(repo_root)
    for raw_value in raw_roots or []:
        add_root(raw_value)
    return roots


def _linked_email_matches(project_link: dict[str, Any], linked_email: str) -> bool:
    current_email = linked_email.strip().lower()
    if not current_email:
        return True
    project_email = str(project_link.get("linked_email", "")).strip().lower()
    if not project_email:
        return True
    return project_email == current_email


def _runner_sync_payload_for_roots(
    repo_roots: Sequence[Path],
    machine: dict[str, Any],
    args: argparse.Namespace,
    *,
    linked_email: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    synced_at_utc = _now_utc()
    linked_projects: list[dict[str, Any]] = []
    sessions: list[dict[str, Any]] = []
    included_project_roots: list[str] = []
    skipped_project_roots: list[dict[str, Any]] = []
    seen_project_keys: set[tuple[str, str, str]] = set()
    routeable_sessions = 0

    for repo_root in repo_roots:
        root_display = str(repo_root)
        if not repo_root.exists():
            skipped_project_roots.append(
                {
                    "project_root": root_display,
                    "reason": "missing",
                }
            )
            continue
        if not _git_repo_present(repo_root):
            skipped_project_roots.append(
                {
                    "project_root": root_display,
                    "reason": "not_git_repo",
                }
            )
            continue

        link_status = _link_status_payload(repo_root, args, refresh_remote_world=False)
        if not link_status.get("project_link_exists"):
            skipped_project_roots.append(
                {
                    "project_root": root_display,
                    "reason": "not_linked",
                }
            )
            continue

        project_link = link_status.get("project_link", {}) if isinstance(link_status.get("project_link"), dict) else {}
        if not _linked_email_matches(project_link, linked_email):
            skipped_project_roots.append(
                {
                    "project_root": root_display,
                    "reason": "linked_email_mismatch",
                }
            )
            continue

        repo_payload = _runner_sync_payload_for_repo(
            repo_root,
            machine,
            link_status,
            synced_at_utc=synced_at_utc,
        )
        for row in repo_payload.get("linkedProjects", []):
            if not isinstance(row, dict):
                continue
            key = (
                str(row.get("projectRoot", "")).strip(),
                str(row.get("ideaId", "")).strip(),
                str(row.get("worldId", "")).strip(),
            )
            if key in seen_project_keys:
                continue
            seen_project_keys.add(key)
            linked_projects.append(row)

        for row in repo_payload.get("sessions", []):
            if isinstance(row, dict):
                sessions.append(row)

        routeable_sessions += int(link_status.get("session_counts", {}).get("routeable", 0) or 0)
        included_project_roots.append(root_display)

    sync_payload = {
        "machineId": str(machine.get("machine_id", "")).strip(),
        "machineName": str(machine.get("machine_name", "")).strip(),
        "platform": str(machine.get("platform", _runner_platform_name())).strip() or _runner_platform_name(),
        "appVersion": str(machine.get("app_version", ORP_TOOL_VERSION)).strip() or ORP_TOOL_VERSION,
        "syncedAt": synced_at_utc,
        "linkedProjects": linked_projects,
        "sessions": sessions,
    }
    summary = {
        "included_project_roots": included_project_roots,
        "skipped_project_roots": skipped_project_roots,
        "routeable_sessions": routeable_sessions,
    }
    return sync_payload, summary


def _runner_status_payload(repo_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    machine = _load_runner_machine()
    machine_path = _runner_machine_path()
    repo_has_git = _git_repo_present(repo_root)
    repo_runner_path = _runner_repo_path(repo_root)
    repo_runtime_path = _runner_runtime_path(repo_root)
    repo_runner = _read_runner_repo_state(repo_root) if repo_has_git else {}
    repo_runtime = _read_runner_runtime(repo_root) if repo_has_git else _default_runner_runtime_payload()
    hosted_session = _load_hosted_session()
    hosted_session["base_url"] = _resolve_hosted_base_url(args, hosted_session)
    hosted_auth = _session_summary(hosted_session)
    link_status = _link_status_payload(repo_root, args, refresh_remote_world=False) if repo_has_git else {
        "project_link_exists": False,
        "project_link": {},
        "sessions": [],
        "session_counts": {
            "total": 0,
            "active": 0,
            "archived": 0,
            "routeable": 0,
            "primary": 0,
        },
        "routing_ready": False,
        "warnings": ["git repository not detected for local link/session state."],
        "notes": [],
        "next_actions": ["orp init"],
        "hosted_auth": hosted_auth,
    }
    session_counts = link_status.get("session_counts", {}) if isinstance(link_status.get("session_counts"), dict) else {}
    project_link_exists = bool(link_status.get("project_link_exists"))
    sync_ready = bool(machine.get("runner_enabled")) and repo_has_git and project_link_exists and bool(hosted_auth.get("connected"))
    work_ready = sync_ready and int(session_counts.get("routeable", 0) or 0) > 0
    lease_health = _runner_active_lease_health(repo_runtime, machine)
    active_job = repo_runtime.get("active_job", {}) if isinstance(repo_runtime.get("active_job"), dict) else {}
    last_job = repo_runtime.get("last_job", {}) if isinstance(repo_runtime.get("last_job"), dict) else {}

    warnings: list[str] = []
    notes: list[str] = []
    next_actions: list[str] = []
    if not machine.get("runner_enabled"):
        warnings.append("runner is disabled on this machine.")
        next_actions.append("orp runner enable --json")
    elif not str(machine.get("last_heartbeat_at_utc", "")).strip():
        warnings.append("runner has not sent a heartbeat yet.")
        next_actions.append("orp runner heartbeat --json")
    if not repo_has_git:
        warnings.append("git repository not detected for the current repo.")
        next_actions.append("orp init")
    if repo_has_git and not project_link_exists:
        warnings.append("current repo is not linked to a hosted idea/world yet.")
        next_actions.append("orp link project bind --idea-id <idea-id> --json")
    if repo_has_git and project_link_exists and int(session_counts.get("total", 0) or 0) == 0:
        warnings.append("current repo has no linked sessions to advertise.")
        next_actions.append(
            "orp link session register --orp-session-id <session-id> --label <label> --codex-session-id <codex-session-id> --primary --json"
        )
    if project_link_exists and not hosted_auth.get("connected"):
        warnings.append("hosted auth is not connected, so runner sync cannot reach the hosted app.")
        next_actions.append("orp auth login")
    if sync_ready:
        notes.append("runner is ready to sync linked project/session inventory to the hosted app.")
    if work_ready:
        notes.append("runner has at least one routeable linked session for hosted prompt delivery.")
    elif sync_ready:
        warnings.append("runner can sync this repo, but there is no routeable linked session yet.")
        next_actions.append("orp link session set-primary <orp_session_id> --json")
    if active_job:
        notes.append("runner is tracking an active hosted lease for this repo.")
        if lease_health.get("stale"):
            warnings.append(
                f"local runner lease appears stale ({int(lease_health.get('age_seconds', 0) or 0)}s since heartbeat)."
            )
            if str(active_job.get("job_id", "")).strip():
                cancel_command = f"orp runner cancel {str(active_job.get('job_id', '')).strip()}"
                if str(active_job.get("lease_id", "")).strip():
                    cancel_command += f" --lease-id {str(active_job.get('lease_id', '')).strip()}"
                cancel_command += " --json"
                next_actions.append(cancel_command)
    if last_job and str(last_job.get("status", "")).strip() == "failed":
        warnings.append("last hosted runner job failed; review the last job summary and error in runner status JSON.")

    return {
        "ok": True,
        "machine": machine,
        "machine_path": str(machine_path),
        "repo_has_git": repo_has_git,
        "repo_runner": repo_runner,
        "repo_runner_path": _path_for_state(repo_runner_path, repo_root) if repo_runner_path is not None else "",
        "repo_runtime": repo_runtime,
        "repo_runtime_path": _path_for_state(repo_runtime_path, repo_root) if repo_runtime_path is not None else "",
        "active_lease": lease_health,
        "project_link_exists": project_link_exists,
        "session_counts": session_counts,
        "sync_ready": sync_ready,
        "work_ready": work_ready,
        "hosted_auth": hosted_auth,
        "link_status": link_status,
        "warnings": _unique_strings(warnings + list(link_status.get("warnings", []))),
        "notes": _unique_strings(notes + list(link_status.get("notes", []))),
        "next_actions": _unique_strings(next_actions + list(link_status.get("next_actions", []))),
    }


def _perform_runner_heartbeat(
    repo_root: Path,
    args: argparse.Namespace,
    session: dict[str, Any],
    machine: dict[str, Any],
    *,
    heartbeat_at_utc: str = "",
    job_id: str = "",
    lease_id: str = "",
) -> dict[str, Any]:
    timestamp_utc = _normalize_timestamp_utc(heartbeat_at_utc, fallback=_now_utc())
    runtime = _read_runner_runtime(repo_root) if _git_repo_present(repo_root) else _default_runner_runtime_payload()
    active_job = runtime.get("active_job", {}) if isinstance(runtime.get("active_job"), dict) else {}
    resolved_job_id = str(job_id).strip() or str(active_job.get("job_id", "")).strip()
    resolved_lease_id = str(lease_id).strip() or str(active_job.get("lease_id", "")).strip()
    body: dict[str, Any] = {
        "machineId": str(machine.get("machine_id", "")).strip(),
        "machineName": str(machine.get("machine_name", "")).strip(),
    }
    if resolved_job_id:
        body["jobId"] = resolved_job_id
    if resolved_lease_id:
        body["leaseId"] = resolved_lease_id
    response = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path="/api/cli/runner/heartbeat",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    machine_update: dict[str, Any] = {
        "runner_enabled": bool(machine.get("runner_enabled", False)),
        "last_heartbeat_at_utc": timestamp_utc,
    }
    linked_email = str(session.get("email", "")).strip() or str(machine.get("linked_email", "")).strip()
    if linked_email:
        machine_update["linked_email"] = linked_email
    machine_path = _save_runner_machine(machine_update)
    repo_runner_path = ""
    repo_runtime_path = ""
    if _git_repo_present(repo_root):
        repo_runner_path = _path_for_state(_write_runner_repo_state(repo_root, {**machine, **machine_update}), repo_root)
        _, runtime_path = _record_runner_heartbeat(
            repo_root,
            heartbeat_at_utc=timestamp_utc,
            job_id=resolved_job_id,
            lease_id=resolved_lease_id,
        )
        if runtime_path is not None:
            repo_runtime_path = _path_for_state(runtime_path, repo_root)
    return {
        "machine": _load_runner_machine(),
        "machine_path": str(machine_path),
        "repo_runner_path": repo_runner_path,
        "repo_runtime_path": repo_runtime_path,
        "heartbeat_at_utc": timestamp_utc,
        "job_id": resolved_job_id,
        "lease_id": resolved_lease_id,
        "response": response if isinstance(response, dict) else {},
    }


def _runner_job_path_value(raw: Any, repo_root: Path) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    return _normalize_local_path(text, repo_root, fallback="")


def _runner_job_target_summary(job: dict[str, Any], repo_root: Path) -> dict[str, str]:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    project = job.get("project") if isinstance(job.get("project"), dict) else {}
    session = job.get("session") if isinstance(job.get("session"), dict) else {}
    checkpoint_id = (
        str(job.get("checkpointId", job.get("checkpoint_id", ""))).strip()
        or str(payload.get("checkpointId", payload.get("checkpoint_id", ""))).strip()
    )
    idea_id = (
        str(job.get("ideaId", job.get("idea_id", ""))).strip()
        or str(payload.get("ideaId", payload.get("idea_id", ""))).strip()
        or str(project.get("ideaId", project.get("idea_id", ""))).strip()
        or str(session.get("ideaId", session.get("idea_id", ""))).strip()
    )
    world_id = (
        str(payload.get("worldId", payload.get("world_id", ""))).strip()
        or str(project.get("worldId", project.get("world_id", ""))).strip()
        or str(session.get("worldId", session.get("world_id", ""))).strip()
    )
    project_root = (
        _runner_job_path_value(payload.get("projectRoot", payload.get("project_root", "")), repo_root)
        or _runner_job_path_value(project.get("projectRoot", project.get("project_root", "")), repo_root)
        or _runner_job_path_value(session.get("projectRoot", session.get("project_root", "")), repo_root)
    )
    explicit_orp_session_id = (
        str(payload.get("orpSessionId", payload.get("orp_session_id", ""))).strip()
        or str(session.get("orpSessionId", session.get("orp_session_id", ""))).strip()
    )
    explicit_codex_session_id = (
        str(payload.get("codexSessionId", payload.get("codex_session_id", ""))).strip()
        or str(session.get("codexSessionId", session.get("codex_session_id", ""))).strip()
    )
    prompt = (
        str(payload.get("prompt", "")).strip()
        or str(job.get("prompt", "")).strip()
    )
    return {
        "job_id": str(job.get("id", "")).strip(),
        "kind": str(job.get("kind", "")).strip(),
        "checkpoint_id": checkpoint_id,
        "idea_id": idea_id,
        "world_id": world_id,
        "project_root": project_root,
        "orp_session_id": explicit_orp_session_id,
        "codex_session_id": explicit_codex_session_id,
        "prompt": prompt,
    }


def _runner_supported_job_kinds() -> set[str]:
    return {
        "session.prompt",
        "idea.checkpoint",
    }


def _runner_job_lease_summary(poll_payload: Any, job: dict[str, Any]) -> dict[str, str]:
    poll = poll_payload if isinstance(poll_payload, dict) else {}
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    lease = poll.get("lease") if isinstance(poll.get("lease"), dict) else {}
    lease_id = (
        str(poll.get("leaseId", poll.get("lease_id", ""))).strip()
        or str(job.get("leaseId", job.get("lease_id", ""))).strip()
        or str(payload.get("leaseId", payload.get("lease_id", ""))).strip()
        or str(lease.get("id", lease.get("leaseId", lease.get("lease_id", "")))).strip()
    )
    lease_expires_at_utc = _normalize_timestamp_utc(
        poll.get("leaseExpiresAt", poll.get("lease_expires_at"))
        or job.get("leaseExpiresAt", job.get("lease_expires_at"))
        or payload.get("leaseExpiresAt", payload.get("lease_expires_at"))
        or lease.get("expiresAt", lease.get("lease_expires_at")),
        fallback="",
    )
    return {
        "lease_id": lease_id,
        "lease_expires_at_utc": lease_expires_at_utc,
    }


def _runner_runtime_job_snapshot(
    job: dict[str, Any],
    repo_root: Path,
    *,
    lease_id: str = "",
    lease_expires_at_utc: str = "",
    selected_session: dict[str, Any] | None = None,
    status: str = "",
    claimed_at_utc: str = "",
    started_at_utc: str = "",
    last_heartbeat_at_utc: str = "",
    finished_at_utc: str = "",
    summary: str = "",
    error: str = "",
) -> dict[str, Any]:
    target = _runner_job_target_summary(job, repo_root)
    session = selected_session if isinstance(selected_session, dict) else {}
    snapshot: dict[str, Any] = {
        "job_id": target["job_id"],
        "job_kind": target["kind"],
        "lease_id": str(lease_id).strip(),
        "checkpoint_id": target["checkpoint_id"],
        "idea_id": target["idea_id"],
        "world_id": target["world_id"],
        "project_root": target["project_root"] or str(repo_root),
        "repo_root": str(repo_root),
        "orp_session_id": str(session.get("orp_session_id", target.get("orp_session_id", ""))).strip(),
        "codex_session_id": str(session.get("codex_session_id", target.get("codex_session_id", ""))).strip(),
        "status": str(status).strip().lower(),
        "summary": str(summary).strip(),
        "error": str(error).strip(),
        "claimed_at_utc": _normalize_timestamp_utc(claimed_at_utc, fallback=""),
        "started_at_utc": _normalize_timestamp_utc(started_at_utc, fallback=""),
        "last_heartbeat_at_utc": _normalize_timestamp_utc(last_heartbeat_at_utc, fallback=""),
        "lease_expires_at_utc": _normalize_timestamp_utc(lease_expires_at_utc, fallback=""),
        "finished_at_utc": _normalize_timestamp_utc(finished_at_utc, fallback=""),
    }
    return _normalize_runner_runtime_job(snapshot)


def _record_runner_claim(
    repo_root: Path,
    job: dict[str, Any],
    *,
    lease_id: str = "",
    lease_expires_at_utc: str = "",
    claimed_at_utc: str = "",
) -> tuple[dict[str, Any], Path]:
    timestamp_utc = _normalize_timestamp_utc(claimed_at_utc, fallback=_now_utc())
    active_job = _runner_runtime_job_snapshot(
        job,
        repo_root,
        lease_id=lease_id,
        lease_expires_at_utc=lease_expires_at_utc,
        status="claimed",
        claimed_at_utc=timestamp_utc,
        last_heartbeat_at_utc=timestamp_utc,
    )
    return _update_runner_runtime(
        repo_root,
        status="claimed",
        active_job=active_job,
        event=_runner_runtime_event(
            status="claimed",
            job_id=active_job.get("job_id", ""),
            lease_id=active_job.get("lease_id", ""),
            timestamp_utc=timestamp_utc,
            message="Claimed hosted runner job.",
        ),
    )


def _record_runner_start(
    repo_root: Path,
    job: dict[str, Any],
    *,
    lease_id: str = "",
    lease_expires_at_utc: str = "",
    selected_session: dict[str, Any] | None = None,
    started_at_utc: str = "",
) -> tuple[dict[str, Any], Path]:
    timestamp_utc = _normalize_timestamp_utc(started_at_utc, fallback=_now_utc())
    current = _read_runner_runtime(repo_root)
    claimed_at_utc = str(current.get("active_job", {}).get("claimed_at_utc", "")).strip()
    active_job = _runner_runtime_job_snapshot(
        job,
        repo_root,
        lease_id=lease_id or str(current.get("active_job", {}).get("lease_id", "")).strip(),
        lease_expires_at_utc=lease_expires_at_utc or str(current.get("active_job", {}).get("lease_expires_at_utc", "")).strip(),
        selected_session=selected_session,
        status="running",
        claimed_at_utc=claimed_at_utc,
        started_at_utc=timestamp_utc,
        last_heartbeat_at_utc=timestamp_utc,
    )
    return _update_runner_runtime(
        repo_root,
        status="running",
        active_job=active_job,
        event=_runner_runtime_event(
            status="running",
            job_id=active_job.get("job_id", ""),
            lease_id=active_job.get("lease_id", ""),
            timestamp_utc=timestamp_utc,
            message="Started hosted runner job.",
        ),
    )


def _record_runner_heartbeat(
    repo_root: Path,
    *,
    heartbeat_at_utc: str = "",
    job_id: str = "",
    lease_id: str = "",
) -> tuple[dict[str, Any], Path] | tuple[dict[str, Any], None]:
    current = _read_runner_runtime(repo_root)
    active_job = current.get("active_job", {}) if isinstance(current.get("active_job"), dict) else {}
    if not active_job:
        return current, None
    current_job_id = str(active_job.get("job_id", "")).strip()
    current_lease_id = str(active_job.get("lease_id", "")).strip()
    if str(job_id).strip() and current_job_id and str(job_id).strip() != current_job_id:
        return current, None
    if str(lease_id).strip() and current_lease_id and str(lease_id).strip() != current_lease_id:
        return current, None
    timestamp_utc = _normalize_timestamp_utc(heartbeat_at_utc, fallback=_now_utc())
    updated_job = _normalize_runner_runtime_job(
        {
            **active_job,
            "last_heartbeat_at_utc": timestamp_utc,
        }
    )
    return _update_runner_runtime(
        repo_root,
        status="running",
        active_job=updated_job,
        event=_runner_runtime_event(
            status="heartbeat",
            job_id=updated_job.get("job_id", ""),
            lease_id=updated_job.get("lease_id", ""),
            timestamp_utc=timestamp_utc,
            message="Sent hosted runner heartbeat.",
        ),
    )


def _record_runner_finish(
    repo_root: Path,
    job: dict[str, Any],
    *,
    final_status: str,
    lease_id: str = "",
    lease_expires_at_utc: str = "",
    selected_session: dict[str, Any] | None = None,
    summary: str = "",
    error: str = "",
    finished_at_utc: str = "",
) -> tuple[dict[str, Any], Path]:
    timestamp_utc = _normalize_timestamp_utc(finished_at_utc, fallback=_now_utc())
    current = _read_runner_runtime(repo_root)
    active_job = current.get("active_job", {}) if isinstance(current.get("active_job"), dict) else {}
    claimed_at_utc = str(active_job.get("claimed_at_utc", "")).strip()
    started_at_utc = str(active_job.get("started_at_utc", "")).strip()
    last_heartbeat_at_utc = str(active_job.get("last_heartbeat_at_utc", "")).strip()
    last_job = _runner_runtime_job_snapshot(
        job,
        repo_root,
        lease_id=lease_id or str(active_job.get("lease_id", "")).strip(),
        lease_expires_at_utc=lease_expires_at_utc or str(active_job.get("lease_expires_at_utc", "")).strip(),
        selected_session=selected_session,
        status=final_status,
        claimed_at_utc=claimed_at_utc,
        started_at_utc=started_at_utc,
        last_heartbeat_at_utc=last_heartbeat_at_utc,
        finished_at_utc=timestamp_utc,
        summary=summary,
        error=error,
    )
    return _update_runner_runtime(
        repo_root,
        status="idle",
        clear_active=True,
        last_job=last_job,
        event=_runner_runtime_event(
            status=final_status,
            job_id=last_job.get("job_id", ""),
            lease_id=last_job.get("lease_id", ""),
            timestamp_utc=timestamp_utc,
            message=str(summary).strip() or str(error).strip() or f"Runner job {final_status}.",
        ),
    )


def _resolve_runner_control_target(
    repo_root: Path,
    *,
    job_id: str = "",
    lease_id: str = "",
    prefer_last_job: bool = False,
) -> dict[str, Any]:
    runtime = _read_runner_runtime(repo_root)
    active_job = runtime.get("active_job", {}) if isinstance(runtime.get("active_job"), dict) else {}
    last_job = runtime.get("last_job", {}) if isinstance(runtime.get("last_job"), dict) else {}
    selected = active_job if active_job else {}
    source = "active_runtime"
    if not selected and prefer_last_job and last_job:
        selected = last_job
        source = "last_job"
    resolved_job_id = str(job_id).strip() or str(selected.get("job_id", "")).strip()
    resolved_lease_id = str(lease_id).strip() or str(selected.get("lease_id", "")).strip()
    return {
        "job_id": resolved_job_id,
        "lease_id": resolved_lease_id,
        "job": selected,
        "source": source if selected else ("explicit" if resolved_job_id or resolved_lease_id else ""),
        "runtime": runtime,
    }


def _resolve_runner_control_target_for_roots(
    repo_roots: Sequence[Path],
    *,
    job_id: str = "",
    lease_id: str = "",
    prefer_last_job: bool = False,
) -> tuple[Path, dict[str, Any]]:
    explicit_job_id = str(job_id).strip()
    explicit_lease_id = str(lease_id).strip()
    active_candidates: list[tuple[Path, dict[str, Any]]] = []
    last_candidates: list[tuple[Path, dict[str, Any]]] = []
    roots = list(repo_roots) or [Path(".").resolve()]
    for repo_root in roots:
        target = _resolve_runner_control_target(
            repo_root,
            job_id=explicit_job_id,
            lease_id=explicit_lease_id,
            prefer_last_job=prefer_last_job,
        )
        if explicit_job_id and target.get("job_id") == explicit_job_id:
            return repo_root, target
        if explicit_lease_id and target.get("lease_id") == explicit_lease_id and target.get("job_id"):
            return repo_root, target
        if target.get("source") == "active_runtime" and target.get("job_id"):
            active_candidates.append((repo_root, target))
        elif prefer_last_job and target.get("source") == "last_job" and target.get("job_id"):
            last_candidates.append((repo_root, target))
    if active_candidates:
        return active_candidates[0]
    if last_candidates:
        return last_candidates[0]
    if explicit_job_id or explicit_lease_id:
        return roots[0], {
            "job_id": explicit_job_id,
            "lease_id": explicit_lease_id,
            "job": {},
            "source": "explicit",
            "runtime": _read_runner_runtime(roots[0]),
        }
    return roots[0], _resolve_runner_control_target(roots[0], prefer_last_job=prefer_last_job)


def _runner_active_lease_health(
    runtime: dict[str, Any],
    machine: dict[str, Any],
) -> dict[str, Any]:
    active_job = runtime.get("active_job", {}) if isinstance(runtime.get("active_job"), dict) else {}
    if not active_job:
        return {"has_active_job": False, "stale": False, "age_seconds": 0}
    heartbeat_at = (
        str(active_job.get("last_heartbeat_at_utc", "")).strip()
        or str(machine.get("last_heartbeat_at_utc", "")).strip()
        or str(active_job.get("started_at_utc", "")).strip()
        or str(active_job.get("claimed_at_utc", "")).strip()
    )
    parsed = _parse_iso8601_utc(heartbeat_at)
    if parsed is None:
        return {"has_active_job": True, "stale": False, "age_seconds": 0}
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    else:
        parsed = parsed.astimezone(dt.timezone.utc)
    age_seconds = max(0, int((dt.datetime.now(dt.timezone.utc) - parsed).total_seconds()))
    return {
        "has_active_job": True,
        "stale": age_seconds >= RUNNER_LEASE_STALE_SECONDS,
        "age_seconds": age_seconds,
    }


def _runner_job_matches_current_repo(job: dict[str, Any], repo_root: Path, link_status: dict[str, Any]) -> tuple[bool, str]:
    project_link = link_status.get("project_link", {}) if isinstance(link_status.get("project_link"), dict) else {}
    if not project_link:
        return False, "current repo is not linked to a hosted idea/world."
    target = _runner_job_target_summary(job, repo_root)
    project_idea_id = str(project_link.get("idea_id", "")).strip()
    project_world_id = str(project_link.get("world_id", "")).strip()
    project_root = str(project_link.get("project_root", str(repo_root))).strip() or str(repo_root)

    checks: list[tuple[str, bool]] = []
    if target["idea_id"] and project_idea_id:
        checks.append(("idea_id", target["idea_id"] == project_idea_id))
    if target["world_id"] and project_world_id:
        checks.append(("world_id", target["world_id"] == project_world_id))
    if target["project_root"]:
        checks.append(("project_root", target["project_root"] == project_root))
    if not checks:
        return True, ""
    if any(match for _, match in checks):
        return True, ""
    detail = ", ".join([f"{name} mismatch" for name, _ in checks]) or "job target mismatch"
    return False, f"claimed runner job does not target the current repo ({detail})."


def _runner_repo_contexts_for_roots(
    repo_roots: Sequence[Path],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    for repo_root in repo_roots:
        if not _git_repo_present(repo_root):
            continue
        link_status = _link_status_payload(repo_root, args, refresh_remote_world=False)
        contexts.append(
            {
                "repo_root": repo_root,
                "link_status": link_status,
                "project_link": link_status.get("project_link", {}) if isinstance(link_status.get("project_link"), dict) else {},
            }
        )
    return contexts


def _select_runner_repo_context_for_job(
    job: dict[str, Any],
    repo_contexts: Sequence[dict[str, Any]],
    *,
    default_repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    linked_contexts = [
        context
        for context in repo_contexts
        if isinstance(context.get("project_link"), dict) and context.get("project_link")
    ]
    if not linked_contexts:
        return {}, {
            "source": "none",
            "error": "no linked repo is available on this machine for runner work.",
        }

    default_context = next(
        (context for context in linked_contexts if context.get("repo_root") == default_repo_root),
        linked_contexts[0],
    )
    best_context: dict[str, Any] = {}
    best_details: dict[str, Any] = {}
    best_score = -1
    mismatch_notes: list[str] = []

    for context in linked_contexts:
        repo_root = context["repo_root"]
        link_status = context["link_status"]
        project_link = context["project_link"]
        target = _runner_job_target_summary(job, repo_root)
        sessions = [
            row
            for row in link_status.get("sessions", [])
            if isinstance(row, dict)
        ]
        checks: list[tuple[str, bool]] = []
        score = 0

        target_orp_session_id = target["orp_session_id"]
        if target_orp_session_id:
            session_match = any(
                str(row.get("orp_session_id", "")).strip() == target_orp_session_id
                for row in sessions
            )
            checks.append(("orp_session_id", session_match))
            if session_match:
                score += 8

        target_codex_session_id = target["codex_session_id"]
        if target_codex_session_id:
            codex_match = any(
                str(row.get("codex_session_id", "")).strip() == target_codex_session_id
                for row in sessions
            )
            checks.append(("codex_session_id", codex_match))
            if codex_match:
                score += 6

        project_root = str(project_link.get("project_root", str(repo_root))).strip() or str(repo_root)
        if target["project_root"]:
            project_root_match = target["project_root"] == project_root
            checks.append(("project_root", project_root_match))
            if project_root_match:
                score += 4

        project_world_id = str(project_link.get("world_id", "")).strip()
        if target["world_id"] and project_world_id:
            world_match = target["world_id"] == project_world_id
            checks.append(("world_id", world_match))
            if world_match:
                score += 2

        project_idea_id = str(project_link.get("idea_id", "")).strip()
        if target["idea_id"] and project_idea_id:
            idea_match = target["idea_id"] == project_idea_id
            checks.append(("idea_id", idea_match))
            if idea_match:
                score += 1

        if not checks:
            continue

        if any(match for _, match in checks):
            if score > best_score:
                best_context = context
                best_score = score
                best_details = {
                    "source": "job_target_match",
                    "score": score,
                    "matched_fields": [name for name, matched in checks if matched],
                    "target": target,
                }
            continue

        mismatch_fields = ", ".join(name for name, _ in checks) or "target"
        mismatch_notes.append(f"{repo_root}: {mismatch_fields} mismatch")

    if best_context:
        return best_context, best_details

    target = _runner_job_target_summary(job, default_repo_root)
    has_explicit_target = any(
        bool(target[key])
        for key in ("idea_id", "world_id", "project_root", "orp_session_id", "codex_session_id")
    )
    if has_explicit_target:
        detail = "; ".join(mismatch_notes) if mismatch_notes else "no linked repo matched the job target"
        return {}, {
            "source": "none",
            "target": target,
            "error": f"claimed runner job does not target any linked repo on this machine ({detail}).",
        }

    return default_context, {
        "source": "default_repo_root" if default_context.get("repo_root") == default_repo_root else "first_linked_repo",
        "score": 0,
        "matched_fields": [],
        "target": target,
    }


def _select_runner_session_for_job(job: dict[str, Any], repo_root: Path, link_status: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    sessions = [
        row
        for row in link_status.get("sessions", [])
        if isinstance(row, dict)
    ]
    target = _runner_job_target_summary(job, repo_root)
    target_session_id = target["orp_session_id"]
    explicit_fallback_reason = ""
    if target_session_id:
        selected = next((row for row in sessions if str(row.get("orp_session_id", "")).strip() == target_session_id), {})
        if not selected:
            explicit_fallback_reason = "missing_target_session"
        elif selected.get("archived"):
            explicit_fallback_reason = "archived_target_session"
        else:
            codex_session_id = str(selected.get("codex_session_id", "")).strip() or target["codex_session_id"]
            if not codex_session_id:
                explicit_fallback_reason = "target_session_missing_codex_session_id"
            else:
                selected = dict(selected)
                selected["codex_session_id"] = codex_session_id
                return selected, {
                    "source": "explicit_orp_session_id",
                    "targeted": True,
                }

    primary = next(
        (
            row
            for row in sessions
            if not row.get("archived")
            and bool(row.get("primary"))
            and str(row.get("state", "active")).strip() == "active"
            and str(row.get("codex_session_id", "")).strip()
        ),
        {},
    )
    if primary:
        selection = {
            "source": "primary_session",
            "targeted": False,
        }
        if explicit_fallback_reason:
            selection = {
                "source": "primary_session_fallback",
                "targeted": True,
                "fallback_reason": explicit_fallback_reason,
                "requested_orp_session_id": target_session_id,
            }
        return primary, selection

    first_routeable = next(
        (
            row
            for row in sessions
            if not row.get("archived")
            and str(row.get("state", "active")).strip() == "active"
            and str(row.get("codex_session_id", "")).strip()
        ),
        {},
    )
    if first_routeable:
        selection = {
            "source": "first_routeable_session",
            "targeted": False,
        }
        if explicit_fallback_reason:
            selection = {
                "source": "first_routeable_session_fallback",
                "targeted": True,
                "fallback_reason": explicit_fallback_reason,
                "requested_orp_session_id": target_session_id,
            }
        return first_routeable, selection
    if explicit_fallback_reason and target_session_id:
        raise RuntimeError(
            f"runner job targeted ORP session `{target_session_id}`, but it is unavailable ({explicit_fallback_reason}) and no fallback active linked session with a Codex session id is available for this repo."
        )
    raise RuntimeError("no active linked session with a Codex session id is available for this repo.")


def _runner_job_log_lines(run_result: dict[str, Any]) -> list[dict[str, str]]:
    lines: list[dict[str, str]] = []
    stdout = str(run_result.get("stdout", ""))
    stderr = str(run_result.get("stderr", ""))
    for line in stdout.splitlines():
        text = line.rstrip()
        if text:
            lines.append({"level": "info", "line": text})
    for line in stderr.splitlines():
        text = line.rstrip()
        if text:
            lines.append({"level": "error", "line": text})
    return lines


def _runner_post_job_update(
    *,
    args: argparse.Namespace,
    session: dict[str, Any],
    path: str,
    method: str = "POST",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=path,
        method=method,
        token=str(session.get("token", "")).strip(),
        body=body,
    )


def _touch_link_session_last_active(repo_root: Path, orp_session_id: str, *, timestamp_utc: str = "") -> dict[str, Any]:
    session = _read_link_session(repo_root, orp_session_id)
    if not session:
        return {}
    payload = {k: v for k, v in session.items() if k != "path"}
    payload["last_active_at_utc"] = _normalize_timestamp_utc(timestamp_utc, fallback=_now_utc())
    _write_link_session(repo_root, payload)
    return _read_link_session(repo_root, orp_session_id)


def _run_runner_codex_job(
    *,
    job: dict[str, Any],
    repo_root: Path,
    selected_session: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    target = _runner_job_target_summary(job, repo_root)
    project_root = str(selected_session.get("project_root", "")).strip() or str(repo_root)
    codex_session_id = str(selected_session.get("codex_session_id", "")).strip()
    prompt = target["prompt"]
    if not codex_session_id:
        raise RuntimeError("selected linked session is missing a Codex session id.")
    if not prompt:
        raise RuntimeError("runner job is missing a prompt.")

    output_path = Path(tempfile.gettempdir()) / f"orp-runner-response-{target['job_id'] or 'job'}.txt"
    codex_bin = _resolve_codex_bin(args)
    cmd = [
        codex_bin,
        "exec",
        "resume",
        "--skip-git-repo-check",
        "--output-last-message",
        str(output_path),
        codex_session_id,
        "-",
    ]
    env = dict(os.environ)
    profile = str(getattr(args, "codex_config_profile", "")).strip()
    if profile:
        env["CODEX_PROFILE"] = profile

    proc = subprocess.run(
        cmd,
        cwd=project_root,
        input=prompt,
        capture_output=True,
        text=True,
        env=env,
    )

    body = ""
    if output_path.exists():
        try:
            body = output_path.read_text(encoding="utf-8")
        finally:
            try:
                output_path.unlink()
            except Exception:
                pass
    if not body:
        body = proc.stdout or proc.stderr or ""
    summary = _summarize_checkpoint_response(body)
    return {
        "ok": proc.returncode == 0,
        "exitCode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "body": body,
        "summary": summary,
        "command": " ".join(cmd),
    }


def _perform_runner_sync(
    repo_root: Path,
    args: argparse.Namespace,
    session: dict[str, Any],
    machine: dict[str, Any],
    link_status: dict[str, Any],
    *,
    synced_at_utc: str = "",
) -> dict[str, Any]:
    sync_payload = _runner_sync_payload_for_repo(repo_root, machine, link_status)
    if synced_at_utc:
        sync_payload["syncedAt"] = synced_at_utc
    response = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path="/api/cli/runner/sync",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body=sync_payload,
    )
    synced_at = str(sync_payload.get("syncedAt", "")).strip() or _now_utc()
    machine_update: dict[str, Any] = {
        "runner_enabled": True,
        "linked_email": str(session.get("email", "")).strip(),
        "last_sync_at_utc": synced_at,
    }
    machine_path = _save_runner_machine(machine_update)
    repo_runner_path = _write_runner_repo_state(repo_root, {**machine, **machine_update})
    return {
        "machine": _load_runner_machine(),
        "machine_path": str(machine_path),
        "repo_runner_path": _path_for_state(repo_runner_path, repo_root),
        "sync_payload": sync_payload,
        "response": response if isinstance(response, dict) else {},
        "synced_at_utc": synced_at,
    }


def _perform_runner_sync_for_roots(
    primary_repo_root: Path,
    repo_roots: Sequence[Path],
    args: argparse.Namespace,
    session: dict[str, Any],
    machine: dict[str, Any],
) -> dict[str, Any]:
    sync_payload, sync_summary = _runner_sync_payload_for_roots(
        repo_roots,
        machine,
        args,
        linked_email=str(session.get("email", "")).strip(),
    )
    if not sync_payload["linkedProjects"]:
        raise RuntimeError("No linked project is available to sync.")
    response = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path="/api/cli/runner/sync",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body=sync_payload,
    )
    synced_at = str(sync_payload.get("syncedAt", "")).strip() or _now_utc()
    machine_update: dict[str, Any] = {
        "runner_enabled": True,
        "linked_email": str(session.get("email", "")).strip(),
        "last_sync_at_utc": synced_at,
    }
    machine_path = _save_runner_machine(machine_update)
    repo_runner_path = ""
    if _git_repo_present(primary_repo_root):
        repo_runner_path = _path_for_state(
            _write_runner_repo_state(primary_repo_root, {**machine, **machine_update}),
            primary_repo_root,
        )
    return {
        "machine": _load_runner_machine(),
        "machine_path": str(machine_path),
        "repo_runner_path": repo_runner_path,
        "sync_payload": sync_payload,
        "response": response if isinstance(response, dict) else {},
        "synced_at_utc": synced_at,
        "linked_projects": len(sync_payload["linkedProjects"]),
        "sessions": len(sync_payload["sessions"]),
        "routeable_sessions": int(sync_summary.get("routeable_sessions", 0) or 0),
        "included_project_roots": list(sync_summary.get("included_project_roots", [])),
        "skipped_project_roots": list(sync_summary.get("skipped_project_roots", [])),
    }


def _run_runner_work_once(args: argparse.Namespace) -> dict[str, Any]:
    requested_repo_root = Path(args.repo_root).resolve()
    candidate_roots = _normalize_runner_sync_roots(
        requested_repo_root,
        getattr(args, "linked_project_roots", None),
    )
    repo_root = next((root for root in candidate_roots if _git_repo_present(root)), requested_repo_root)
    if not _git_repo_present(repo_root):
        raise RuntimeError("git repository not detected for any requested runner root. Run `orp init` or `git init` first.")
    machine = _load_runner_machine()
    if not machine.get("runner_enabled"):
        raise RuntimeError("Runner is disabled. Run `orp runner enable --json` first.")
    session = _require_hosted_session(args)
    repo_contexts = _runner_repo_contexts_for_roots(candidate_roots, args)
    if not any(context.get("project_link") for context in repo_contexts):
        raise RuntimeError("No linked repo is available for runner work. Run `orp link project bind --idea-id <idea-id> --json` first.")

    heartbeat = _perform_runner_heartbeat(repo_root, args, session, machine)
    heartbeat_error = ""
    machine = heartbeat.get("machine") if isinstance(heartbeat.get("machine"), dict) else _load_runner_machine()
    machine_id = str(machine.get("machine_id", "")).strip()
    if not machine_id:
        raise RuntimeError("Runner machine id is missing.")
    poll_payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/runner/jobs/poll?machineId={urlparse.quote(machine_id)}",
        token=str(session.get("token", "")).strip(),
    )
    job = poll_payload.get("job") if isinstance(poll_payload, dict) and isinstance(poll_payload.get("job"), dict) else poll_payload
    if not isinstance(job, dict) or not job or not str(job.get("id", "")).strip():
        return {
            "ok": True,
            "claimed": False,
            "job": None,
            "heartbeat": heartbeat,
            "candidate_project_roots": [str(root) for root in candidate_roots],
        }
    lease = _runner_job_lease_summary(poll_payload, job)
    lease_id = str(lease.get("lease_id", "")).strip()
    lease_expires_at_utc = str(lease.get("lease_expires_at_utc", "")).strip()

    selected_context, repo_selection = _select_runner_repo_context_for_job(
        job,
        repo_contexts,
        default_repo_root=requested_repo_root,
    )
    selected_repo_root = selected_context.get("repo_root") if isinstance(selected_context, dict) else None
    selected_session: dict[str, Any] = {}
    selection: dict[str, Any] = {}
    match_ok = bool(selected_context)
    match_error = str(repo_selection.get("error", "")).strip()
    if match_ok and isinstance(selected_repo_root, Path):
        selected_session, selection = _select_runner_session_for_job(
            job,
            selected_repo_root,
            selected_context["link_status"],
        )
        selection = {
            **selection,
            "repo_selection_source": str(repo_selection.get("source", "")).strip(),
            "selected_repo_root": str(selected_repo_root),
            "matched_fields": list(repo_selection.get("matched_fields", [])),
        }

    if bool(getattr(args, "dry_run", False)):
        return {
            "ok": match_ok,
            "claimed": True,
            "dry_run": True,
            "job": job,
            "selected_repo_root": str(selected_repo_root) if isinstance(selected_repo_root, Path) else "",
            "selected_session": selected_session,
            "selection": selection,
            "repo_selection": repo_selection,
            "error": match_error,
            "heartbeat": heartbeat,
            "candidate_project_roots": [str(root) for root in candidate_roots],
        }

    job_id = str(job.get("id", "")).strip()
    claim_root = selected_repo_root if isinstance(selected_repo_root, Path) else repo_root
    runtime_claim, runtime_path = _record_runner_claim(
        claim_root,
        job,
        lease_id=lease_id,
        lease_expires_at_utc=lease_expires_at_utc,
    )
    start_response = _runner_post_job_update(
        args=args,
        session=session,
        path=f"/api/cli/runner/jobs/{urlparse.quote(job_id)}/start",
        body={
            "machineId": machine_id,
            "leaseId": lease_id or None,
        },
    )

    if not match_ok:
        complete_response = _runner_post_job_update(
            args=args,
            session=session,
            path=f"/api/cli/runner/jobs/{urlparse.quote(job_id)}/complete",
            body={
                "machineId": machine_id,
                "leaseId": lease_id or None,
                "success": False,
                "summary": None,
                "content": None,
                "error": match_error,
            },
        )
        runtime_last, runtime_last_path = _record_runner_finish(
            repo_root,
            job,
            final_status="failed",
            lease_id=lease_id,
            lease_expires_at_utc=lease_expires_at_utc,
            error=match_error,
        )
        return {
            "ok": False,
            "claimed": True,
            "job": job,
            "lease": lease,
            "selected_repo_root": "",
            "selected_session": {},
            "selection": {},
            "repo_selection": repo_selection,
            "start_response": start_response,
            "complete_response": complete_response,
            "error": match_error,
            "heartbeat": heartbeat,
            "runtime": runtime_last,
            "runtime_path": _path_for_state(runtime_last_path, repo_root),
            "candidate_project_roots": [str(root) for root in candidate_roots],
        }

    assert isinstance(selected_repo_root, Path)
    runtime_start, runtime_start_path = _record_runner_start(
        selected_repo_root,
        job,
        lease_id=lease_id,
        lease_expires_at_utc=lease_expires_at_utc,
        selected_session=selected_session,
    )
    target = _runner_job_target_summary(job, selected_repo_root)
    meta = {
        "orpSessionId": str(selected_session.get("orp_session_id", "")).strip(),
        "codexSessionId": str(selected_session.get("codex_session_id", "")).strip(),
        "leaseId": lease_id or None,
    }
    job_kind = str(job.get("kind", "")).strip()
    message_text = (
        f"Sending checkpoint review prompt to {selected_session.get('label', 'linked session')}."
        if job_kind == "idea.checkpoint"
        else f"Sending prompt to {selected_session.get('label', 'linked session')}."
    )
    message_response = _runner_post_job_update(
        args=args,
        session=session,
        path=f"/api/cli/runner/jobs/{urlparse.quote(job_id)}/messages",
        body={
            "machineId": machine_id,
            "leaseId": lease_id or None,
            "sender": "system",
            "content": message_text,
            "meta": meta,
        },
    )

    if job_kind not in _runner_supported_job_kinds():
        error_text = f"unsupported runner job kind: {job_kind or '(missing)'}"
        complete_response = _runner_post_job_update(
            args=args,
            session=session,
            path=f"/api/cli/runner/jobs/{urlparse.quote(job_id)}/complete",
            body={
                "machineId": machine_id,
                "leaseId": lease_id or None,
                "success": False,
                "summary": None,
                "content": None,
                "error": error_text,
            },
        )
        runtime_last, runtime_last_path = _record_runner_finish(
            selected_repo_root,
            job,
            final_status="failed",
            lease_id=lease_id,
            lease_expires_at_utc=lease_expires_at_utc,
            selected_session=selected_session,
            error=error_text,
        )
        return {
            "ok": False,
            "claimed": True,
            "job": job,
            "lease": lease,
            "selected_repo_root": str(selected_repo_root),
            "selected_session": selected_session,
            "selection": selection,
            "repo_selection": repo_selection,
            "start_response": start_response,
            "message_response": message_response,
            "complete_response": complete_response,
            "error": error_text,
            "heartbeat": heartbeat,
            "runtime": runtime_last,
            "runtime_path": _path_for_state(runtime_last_path, selected_repo_root),
            "candidate_project_roots": [str(root) for root in candidate_roots],
        }

    heartbeat_interval = max(1, int(getattr(args, "heartbeat_interval", 20)))
    heartbeat_stop = threading.Event()
    heartbeat_errors: list[str] = []

    def heartbeat_loop() -> None:
        while not heartbeat_stop.wait(heartbeat_interval):
            try:
                _perform_runner_heartbeat(
                    selected_repo_root,
                    args,
                    session,
                    _load_runner_machine(),
                    job_id=job_id,
                    lease_id=lease_id,
                )
            except Exception as exc:
                heartbeat_errors.append(str(exc))

    heartbeat_thread = threading.Thread(target=heartbeat_loop, name="orp-runner-heartbeat", daemon=True)
    heartbeat_thread.start()
    sync_result: dict[str, Any] = {}
    sync_error = ""
    try:
        run_result = _run_runner_codex_job(
            job=job,
            repo_root=selected_repo_root,
            selected_session=selected_session,
            args=args,
        )
    except Exception as exc:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=1.0)
        if heartbeat_errors and not heartbeat_error:
            heartbeat_error = heartbeat_errors[-1]
        error_text = str(exc)
        complete_response = _runner_post_job_update(
            args=args,
            session=session,
            path=f"/api/cli/runner/jobs/{urlparse.quote(job_id)}/complete",
            body={
                "machineId": machine_id,
                "leaseId": lease_id or None,
                "success": False,
                "summary": None,
                "content": None,
                "error": error_text,
            },
        )
        runtime_last, runtime_last_path = _record_runner_finish(
            selected_repo_root,
            job,
            final_status="failed",
            lease_id=lease_id,
            lease_expires_at_utc=lease_expires_at_utc,
            selected_session=selected_session,
            error=error_text,
        )
        return {
            "ok": False,
            "claimed": True,
            "job": job,
            "lease": lease,
            "selected_repo_root": str(selected_repo_root),
            "selected_session": selected_session,
            "selection": selection,
            "repo_selection": repo_selection,
            "start_response": start_response,
            "message_response": message_response,
            "complete_response": complete_response,
            "error": error_text,
            "heartbeat": heartbeat,
            "heartbeat_error": heartbeat_error,
            "runtime": runtime_last,
            "runtime_path": _path_for_state(runtime_last_path, selected_repo_root),
            "candidate_project_roots": [str(root) for root in candidate_roots],
        }
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=1.0)

    if heartbeat_errors and not heartbeat_error:
        heartbeat_error = heartbeat_errors[-1]

    log_lines = _runner_job_log_lines(run_result)
    logs_response: dict[str, Any] = {}
    if log_lines:
        logs_response = _runner_post_job_update(
            args=args,
            session=session,
            path=f"/api/cli/runner/jobs/{urlparse.quote(job_id)}/logs",
            body={
                "machineId": machine_id,
                "leaseId": lease_id or None,
                "lines": log_lines,
            },
        )

    if run_result.get("ok"):
        touched_session = _touch_link_session_last_active(
            selected_repo_root,
            str(selected_session.get("orp_session_id", "")).strip(),
        )
        try:
            sync_result = _perform_runner_sync_for_roots(
                repo_root,
                candidate_roots,
                args,
                session,
                machine,
            )
        except Exception as exc:
            sync_error = str(exc)
        complete_response = _runner_post_job_update(
            args=args,
            session=session,
            path=f"/api/cli/runner/jobs/{urlparse.quote(job_id)}/complete",
            body={
                "machineId": machine_id,
                "leaseId": lease_id or None,
                "success": True,
                "summary": (
                    str(run_result.get("summary", "")).strip()
                    or (
                        f"Checkpoint review sent to {selected_session.get('label', 'linked session')}."
                        if job_kind == "idea.checkpoint"
                        else f"Prompt sent to {selected_session.get('label', 'linked session')}."
                    )
                ),
                "content": str(run_result.get("body", "")),
                "error": None,
            },
        )
        success_summary = (
            str(run_result.get("summary", "")).strip()
            or (
                f"Checkpoint review sent to {selected_session.get('label', 'linked session')}."
                if job_kind == "idea.checkpoint"
                else f"Prompt sent to {selected_session.get('label', 'linked session')}."
            )
        )
        runtime_last, runtime_last_path = _record_runner_finish(
            selected_repo_root,
            job,
            final_status="completed",
            lease_id=lease_id,
            lease_expires_at_utc=lease_expires_at_utc,
            selected_session=touched_session or selected_session,
            summary=success_summary,
        )
        return {
            "ok": True,
            "claimed": True,
            "job": job,
            "lease": lease,
            "selected_repo_root": str(selected_repo_root),
            "selected_session": touched_session or selected_session,
            "selection": selection,
            "repo_selection": repo_selection,
            "start_response": start_response,
            "message_response": message_response,
            "logs_response": logs_response,
            "complete_response": complete_response,
            "worker": run_result,
            "sync_result": sync_result,
            "sync_error": sync_error,
            "heartbeat": heartbeat,
            "heartbeat_error": heartbeat_error,
            "runtime": runtime_last,
            "runtime_path": _path_for_state(runtime_last_path, selected_repo_root),
            "candidate_project_roots": [str(root) for root in candidate_roots],
        }

    error_text = (
        next((line.strip() for line in str(run_result.get("stderr", "")).splitlines() if line.strip()), "")
        or "Codex returned a non-zero exit code."
    )
    complete_response = _runner_post_job_update(
        args=args,
        session=session,
        path=f"/api/cli/runner/jobs/{urlparse.quote(job_id)}/complete",
        body={
            "machineId": machine_id,
            "leaseId": lease_id or None,
            "success": False,
            "summary": str(run_result.get("summary", "")).strip() or None,
            "content": None,
            "error": error_text,
        },
    )
    runtime_last, runtime_last_path = _record_runner_finish(
        selected_repo_root,
        job,
        final_status="failed",
        lease_id=lease_id,
        lease_expires_at_utc=lease_expires_at_utc,
        selected_session=selected_session,
        summary=str(run_result.get("summary", "")).strip(),
        error=error_text,
    )
    return {
        "ok": False,
        "claimed": True,
        "job": job,
        "lease": lease,
        "selected_repo_root": str(selected_repo_root),
        "selected_session": selected_session,
        "selection": selection,
        "repo_selection": repo_selection,
        "start_response": start_response,
        "message_response": message_response,
        "logs_response": logs_response,
        "complete_response": complete_response,
        "worker": run_result,
        "error": error_text,
        "heartbeat": heartbeat,
        "heartbeat_error": heartbeat_error,
        "runtime": runtime_last,
        "runtime_path": _path_for_state(runtime_last_path, selected_repo_root),
        "candidate_project_roots": [str(root) for root in candidate_roots],
    }


def _append_bounded_event_list(payload: dict[str, Any], key: str, event: dict[str, Any], *, limit: int = 25) -> None:
    rows = payload.get(key)
    if not isinstance(rows, list):
        rows = []
    rows = [row for row in rows if isinstance(row, dict)]
    rows.append(event)
    payload[key] = rows[-limit:]


def _git_latest_checkpoint_commit(repo_root: Path) -> dict[str, Any]:
    proc = _git_run(
        repo_root,
        [
            "log",
            "-1",
            "--pretty=format:%H%x1f%h%x1f%s%x1f%cI",
            "--grep",
            "^checkpoint:",
        ],
    )
    if proc.returncode != 0:
        return {}
    parts = proc.stdout.strip().split("\x1f") if proc.stdout.strip() else []
    if len(parts) != 4:
        return {}
    return {
        "commit_full": parts[0],
        "commit": parts[1],
        "commit_message": parts[2],
        "committed_at_utc": parts[3],
    }


def _latest_run_payload(repo_root: Path, *, run_id_arg: str = "", run_json_arg: str = "") -> dict[str, Any]:
    try:
        run_id, run_json_path = _resolve_run_json_path(
            repo_root=repo_root,
            run_id_arg=run_id_arg,
            run_json_arg=run_json_arg,
        )
    except RuntimeError:
        return {}

    run = _read_json_if_exists(run_json_path)
    summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
    repo = run.get("repo") if isinstance(run.get("repo"), dict) else {}
    git = repo.get("git") if isinstance(repo.get("git"), dict) else {}
    return {
        "run_id": run_id,
        "run_json": _path_for_state(run_json_path, repo_root),
        "profile": str(run.get("profile", "")).strip(),
        "overall": str(summary.get("overall_result", "")).strip(),
        "gates_passed": int(summary.get("gates_passed", 0) or 0),
        "gates_failed": int(summary.get("gates_failed", 0) or 0),
        "gates_total": int(summary.get("gates_total", 0) or 0),
        "started_at_utc": str(run.get("started_at_utc", "")).strip(),
        "ended_at_utc": str(run.get("ended_at_utc", "")).strip(),
        "git_branch": str(git.get("branch", "")).strip(),
        "git_commit": str(git.get("commit", "")).strip(),
    }


def _github_repo_from_remote_url(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""

    patterns = [
        r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            return f"{match.group('owner')}/{match.group('repo')}"
    return ""


def _normalize_github_repo(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""

    parsed = _github_repo_from_remote_url(text)
    if parsed:
        return parsed

    if text.endswith(".git"):
        text = text[:-4]
    text = text.strip("/")
    pieces = [piece for piece in text.split("/") if piece]
    if len(pieces) != 2:
        raise RuntimeError(f"expected GitHub repo as owner/repo, got: {raw}")
    return f"{pieces[0]}/{pieces[1]}"


def _synthesized_github_remote_url(github_repo: str) -> str:
    return f"https://github.com/{github_repo}.git"


def _git_init_repo(repo_root: Path, default_branch: str) -> dict[str, Any]:
    init_proc = _git_run(repo_root, ["init", "-b", default_branch])
    if init_proc.returncode == 0:
        return {
            "initialized": True,
            "method": "git init -b",
        }

    fallback_proc = _git_run(repo_root, ["init"])
    if fallback_proc.returncode != 0:
        detail = fallback_proc.stderr.strip() or fallback_proc.stdout.strip() or "git init failed"
        raise RuntimeError(f"failed to initialize git repo: {detail}")

    head_ref = f"refs/heads/{default_branch}"
    head_proc = _git_run(repo_root, ["symbolic-ref", "HEAD", head_ref])
    if head_proc.returncode == 0:
        return {
            "initialized": True,
            "method": "git init + symbolic-ref",
        }

    checkout_proc = _git_run(repo_root, ["checkout", "-b", default_branch])
    if checkout_proc.returncode == 0:
        return {
            "initialized": True,
            "method": "git init + checkout -b",
        }

    detail = checkout_proc.stderr.strip() or head_proc.stderr.strip() or "unable to select default branch"
    raise RuntimeError(f"failed to set default branch to {default_branch}: {detail}")


def _git_governance_snapshot(
    repo_root: Path,
    *,
    default_branch: str,
    allow_protected_branch_work: bool,
) -> dict[str, Any]:
    present = _git_repo_present(repo_root)
    branch = _git_current_branch(repo_root) if present else ""
    commit = _git_stdout(repo_root, ["rev-parse", "--short", "HEAD"]) if present else ""
    origin_url = _git_stdout(repo_root, ["remote", "get-url", "origin"]) if present else ""
    has_commits = _git_has_commits(repo_root) if present else False
    status_lines = _git_status_lines(repo_root) if present else []
    protected_branches = [default_branch]
    protected_branch = bool(branch) and branch in protected_branches
    work_branch_required = protected_branch and not allow_protected_branch_work
    working_branch_safe = bool(branch) and (allow_protected_branch_work or not protected_branch)
    return {
        "present": present,
        "branch": branch,
        "commit": commit,
        "has_commits": has_commits,
        "dirty": len(status_lines) > 0,
        "dirty_paths": status_lines,
        "default_branch": default_branch,
        "protected_branches": protected_branches,
        "protected_branch": protected_branch,
        "allow_protected_branch_work": allow_protected_branch_work,
        "work_branch_required": work_branch_required,
        "working_branch_safe": working_branch_safe,
        "detected_remote_url": origin_url,
        "detected_github_repo": _github_repo_from_remote_url(origin_url),
    }


def _effective_remote_context(
    *,
    detected_remote_url: str,
    detected_github_repo: str,
    remote_url_arg: str,
    github_repo_arg: str,
) -> dict[str, Any]:
    explicit_remote_url_input = str(remote_url_arg or "").strip()
    explicit_github_repo_input = _normalize_github_repo(github_repo_arg)
    explicit_remote_url = explicit_remote_url_input
    explicit_github_repo = explicit_github_repo_input
    github_from_remote = _github_repo_from_remote_url(explicit_remote_url)

    if explicit_github_repo and github_from_remote and explicit_github_repo != github_from_remote:
        raise RuntimeError(
            "explicit GitHub repo and --remote-url disagree; pass matching values or only one of them."
        )

    if explicit_github_repo and not explicit_remote_url:
        explicit_remote_url = _synthesized_github_remote_url(explicit_github_repo)
    if github_from_remote and not explicit_github_repo:
        explicit_github_repo = github_from_remote

    effective_remote_url = explicit_remote_url or str(detected_remote_url or "").strip()
    effective_github_repo = explicit_github_repo or str(detected_github_repo or "").strip()

    source = "none"
    if explicit_remote_url_input and explicit_github_repo_input:
        source = "explicit_remote_url+github_repo"
    elif explicit_github_repo_input:
        source = "explicit_github_repo"
    elif explicit_remote_url_input:
        source = "explicit_remote_url"
    elif detected_remote_url:
        source = "detected_origin"

    mode = "local_only"
    if effective_remote_url and effective_github_repo:
        mode = "github"
    elif effective_remote_url:
        mode = "remote"

    return {
        "source": source,
        "mode": mode,
        "detected_remote_url": str(detected_remote_url or "").strip(),
        "detected_github_repo": str(detected_github_repo or "").strip(),
        "effective_remote_url": effective_remote_url,
        "effective_github_repo": effective_github_repo,
    }


def _init_kernel_task_template(repo_name: str) -> str:
    safe_name = str(repo_name or "").strip() or "my-project"
    return (
        'schema_version: "1.0.0"\n'
        "artifact_class: task\n"
        f"object: bootstrap ORP governance for {safe_name}\n"
        "goal: establish a local-first ORP workflow with a promotable starter task artifact\n"
        "boundary:\n"
        "  - repository bootstrap and governance setup\n"
        "  - initial ORP validation and readiness loop\n"
        "constraints:\n"
        "  - keep evidence in canonical artifact paths instead of ORP process metadata\n"
        "  - preserve a clean handoff and checkpoint discipline from day one\n"
        "success_criteria:\n"
        "  - default ORP gate profile passes\n"
        "  - repo is ready for a first meaningful work branch and checkpoint sequence\n"
        "canonical_target:\n"
        "  - orp/HANDOFF.md\n"
        "  - orp/checkpoints/CHECKPOINT_LOG.md\n"
        "artifact_refs:\n"
        "  - orp.yml\n"
        "  - orp/HANDOFF.md\n"
        "  - orp/checkpoints/CHECKPOINT_LOG.md\n"
    )


def _init_config_starter(repo_name: str = "my-project") -> str:
    safe_name = str(repo_name or "").strip() or "my-project"
    return (
        'version: "1"\n'
        "project:\n"
        f"  name: {safe_name}\n"
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
        "  - id: starter_kernel\n"
        "    description: Validate the starter ORP reasoning-kernel task artifact\n"
        "    phase: structure_kernel\n"
        "    command: echo ORP_KERNEL_STARTER\n"
        "    pass:\n"
        "      exit_codes: [0]\n"
        "      stdout_must_contain:\n"
        "        - ORP_KERNEL_STARTER\n"
        "    kernel:\n"
        "      mode: hard\n"
        "      artifacts:\n"
        "        - path: analysis/orp.kernel.task.yml\n"
        "          artifact_class: task\n"
        "    evidence:\n"
        "      status: process_only\n"
        "      note: Starter kernel artifact records task structure, not evidence.\n"
        "      paths:\n"
        "        - analysis/orp.kernel.task.yml\n"
        "    on_fail: stop\n"
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
        "      - starter_kernel\n"
        "      - smoke\n"
    )


def _init_handoff_template(repo_root: Path, *, default_branch: str, initialized_at_utc: str) -> str:
    return (
        f"# ORP Repo Handoff\n\n"
        f"- Repo: `{repo_root.name}`\n"
        f"- ORP-governed since: `{initialized_at_utc}`\n"
        f"- Protected branch expectation: `{default_branch}`\n\n"
        "## Current Objective\n\n"
        "- Describe the current implementation goal.\n"
        "- Link the active branch and the next meaningful checkpoint.\n\n"
        "## Validation State\n\n"
        "- Record what was validated, what is still failing, and what blocks readiness.\n\n"
        "## Agent Rules\n\n"
        f"- Do not do meaningful implementation work directly on `{default_branch}` unless explicitly allowed.\n"
        "- Create a work branch before substantial edits.\n"
        "- Create a checkpoint commit after each meaningful completed unit of work.\n"
        "- Do not mark work ready when validation is failing.\n"
        "- Update this handoff before leaving the repo.\n"
    )


def _init_checkpoint_log_template() -> str:
    return (
        "# ORP Checkpoint Log\n\n"
        "Record meaningful checkpoint commits and why they were created.\n\n"
        "| UTC | Branch | Commit | Note |\n"
        "|---|---|---|---|\n"
    )


def _agent_policy_payload(
    *,
    default_branch: str,
    allow_protected_branch_work: bool,
    remote_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "mode": "repo_governance",
        "local_first": True,
        "remote_optional": True,
        "branch_policy": {
            "default_branch": default_branch,
            "protected_branches": [default_branch],
            "allow_direct_work_on_protected_branches": allow_protected_branch_work,
            "require_work_branch_for_meaningful_edits": not allow_protected_branch_work,
        },
        "checkpoint_policy": {
            "required": True,
            "cadence": "after_each_meaningful_completed_unit",
            "commit_message_prefix": "checkpoint:",
            "log_path": "orp/checkpoints/CHECKPOINT_LOG.md",
        },
        "merge_policy": {
            "allow_automatic_merge_to_protected_branches": False,
            "require_validation_before_ready": True,
        },
        "continuity_policy": {
            "handoff_path": "orp/HANDOFF.md",
            "update_handoff_during_transitions": True,
            "prefer_explicit_cleanup_flows": True,
            "prefer_destructive_deletion": False,
        },
        "remote_policy": {
            "mode": remote_context["mode"],
            "effective_remote_url": remote_context["effective_remote_url"],
            "effective_github_repo": remote_context["effective_github_repo"],
            "source": remote_context["source"],
        },
        "rules": [
            {
                "id": "no_direct_protected_branch_work",
                "enabled": True,
                "enforcement": "governance_runtime",
            },
            {
                "id": "checkpoint_after_meaningful_unit",
                "enabled": True,
                "enforcement": "governance_runtime",
            },
            {
                "id": "validation_before_ready",
                "enabled": True,
                "enforcement": "governance_runtime",
            },
            {
                "id": "no_automatic_merge_to_protected",
                "enabled": True,
                "enforcement": "governance_runtime",
            },
        ],
    }


def _governance_runtime_payload(
    *,
    repo_root: Path,
    config_path: Path,
    initialized_at_utc: str,
    git_snapshot: dict[str, Any],
    remote_context: dict[str, Any],
    warnings: list[str],
    next_actions: list[str],
    initialized_git: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "governance_mode": "repo_governance",
        "initialized_at_utc": initialized_at_utc,
        "tool": {
            "name": "orp",
            "package": ORP_PACKAGE_NAME,
            "version": ORP_TOOL_VERSION,
        },
        "repo": {
            "root_path": str(repo_root),
            "orp_governed": True,
        },
        "runtime": {
            "config_path": _path_for_state(config_path, repo_root),
            "state_json": "orp/state.json",
            "manifest_path": "orp/governance.json",
            "agent_policy_path": "orp/agent-policy.json",
            "handoff_path": "orp/HANDOFF.md",
            "checkpoint_log_path": "orp/checkpoints/CHECKPOINT_LOG.md",
            "artifact_root": "orp/artifacts",
            "packet_root": "orp/packets",
            "discovery_root": "orp/discovery/github",
        },
        "git": {
            **git_snapshot,
            "initialized_by_orp": initialized_git,
        },
        "remote": remote_context,
        "status": {
            "warnings": warnings,
            "next_actions": next_actions,
            "ready_for_agent_work": bool(git_snapshot["working_branch_safe"]) and not bool(git_snapshot["dirty"]),
        },
    }


def _resolve_repo_path(repo_root: Path, raw: str, fallback_relative: str) -> Path:
    text = str(raw or "").strip()
    path = Path(text) if text else repo_root / fallback_relative
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _checkpoint_commit_message(note: str) -> str:
    clean = re.sub(r"\s+", " ", str(note or "").strip())
    if not clean:
        raise RuntimeError("checkpoint note is required.")
    return f"checkpoint: {clean}"


def _backup_note(note: str) -> str:
    clean = re.sub(r"\s+", " ", str(note or "").strip())
    if clean:
        return clean
    return "agent backup snapshot"


def _backup_stamp(timestamp_utc: str) -> str:
    parsed = _parse_iso8601_utc(timestamp_utc)
    if parsed is None:
        return re.sub(r"[^0-9]+", "", str(timestamp_utc or "")) or "backup"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    else:
        parsed = parsed.astimezone(dt.timezone.utc)
    return parsed.strftime("%Y%m%d-%H%M%S")


def _ref_slug(text: str, *, fallback: str = "backup") -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", str(text or "").strip().lower()).strip(".-_")
    return clean or fallback


def _markdown_table_escape(text: str) -> str:
    return str(text or "").replace("|", "\\|").strip()


def _append_checkpoint_log_row(
    path: Path,
    *,
    timestamp_utc: str,
    branch: str,
    note: str,
) -> None:
    if not path.exists():
        _write_text(path, _init_checkpoint_log_template())
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    row = (
        f"| {_markdown_table_escape(timestamp_utc)} | {_markdown_table_escape(branch or '(detached)')} | "
        f"HEAD | {_markdown_table_escape(note)} |\n"
    )
    path.write_text(text + row, encoding="utf-8")


def _create_checkpoint_commit(
    repo_root: Path,
    status_payload: dict[str, Any],
    *,
    branch: str,
    note: str,
    timestamp_utc: str,
) -> dict[str, Any]:
    commit_message = _checkpoint_commit_message(note)

    _git_require_success(
        repo_root,
        ["var", "GIT_AUTHOR_IDENT"],
        context="git author identity is not configured",
    )

    checkpoint_log_path = repo_root / str(status_payload.get("checkpoint_log_path", "orp/checkpoints/CHECKPOINT_LOG.md"))
    checkpoint_log_path = checkpoint_log_path.resolve()
    _append_checkpoint_log_row(
        checkpoint_log_path,
        timestamp_utc=timestamp_utc,
        branch=branch,
        note=note,
    )

    _git_require_success(repo_root, ["add", "-A"], context="failed to stage checkpoint changes")
    _git_require_success(
        repo_root,
        ["commit", "-m", commit_message],
        context="failed to create checkpoint commit",
    )

    commit_full = _git_stdout(repo_root, ["rev-parse", "HEAD"])
    commit_short = _git_stdout(repo_root, ["rev-parse", "--short", "HEAD"])
    return {
        "timestamp_utc": timestamp_utc,
        "branch": branch,
        "note": note,
        "commit": commit_short,
        "commit_full": commit_full,
        "commit_message": commit_message,
        "checkpoint_log_path": _path_for_state(checkpoint_log_path, repo_root),
    }


def _generate_backup_work_branch(repo_root: Path, current_branch: str, *, timestamp_utc: str) -> str:
    stamp = _backup_stamp(timestamp_utc)
    base = _ref_slug(current_branch or "detached", fallback="head")
    candidate = f"work/backup-{base}-{stamp}"
    if not _git_branch_exists(repo_root, candidate):
        return candidate
    suffix = 2
    while True:
        variant = f"{candidate}-{suffix}"
        if not _git_branch_exists(repo_root, variant):
            return variant
        suffix += 1


def _backup_remote_ref_name(branch: str, *, timestamp_utc: str, prefix: str = "orp/backup") -> str:
    clean_prefix = str(prefix or "orp/backup").strip().strip("/")
    if not clean_prefix:
        clean_prefix = "orp/backup"
    stamp = _backup_stamp(timestamp_utc)
    branch_slug = _ref_slug(branch or "detached", fallback="head")
    return f"{clean_prefix}/{branch_slug}/{stamp}"


def _governance_status_payload(repo_root: Path, config_arg: str) -> dict[str, Any]:
    state_path = repo_root / "orp" / "state.json"
    state = _read_json_if_exists(state_path)
    governance_state = state.get("governance") if isinstance(state.get("governance"), dict) else {}
    default_branch = str(governance_state.get("default_branch", "main")).strip() or "main"
    allow_protected_branch_work = bool(governance_state.get("allow_protected_branch_work", False))

    config_path = _resolve_repo_path(
        repo_root,
        str(governance_state.get("config_path", config_arg)),
        config_arg,
    )
    manifest_path = _resolve_repo_path(
        repo_root,
        str(governance_state.get("manifest_path", "orp/governance.json")),
        "orp/governance.json",
    )
    agent_policy_path = _resolve_repo_path(
        repo_root,
        str(governance_state.get("agent_policy_path", "orp/agent-policy.json")),
        "orp/agent-policy.json",
    )
    handoff_path = _resolve_repo_path(
        repo_root,
        str(governance_state.get("handoff_path", "orp/HANDOFF.md")),
        "orp/HANDOFF.md",
    )
    checkpoint_log_path = _resolve_repo_path(
        repo_root,
        str(governance_state.get("checkpoint_log_path", "orp/checkpoints/CHECKPOINT_LOG.md")),
        "orp/checkpoints/CHECKPOINT_LOG.md",
    )

    manifest = _read_json_if_exists(manifest_path)
    orp_governed = bool(governance_state.get("orp_governed")) or bool(manifest.get("repo", {}).get("orp_governed"))
    git_snapshot = _git_governance_snapshot(
        repo_root,
        default_branch=default_branch,
        allow_protected_branch_work=allow_protected_branch_work,
    )
    remote_context = _effective_remote_context(
        detected_remote_url=str(git_snapshot.get("detected_remote_url", "")),
        detected_github_repo=str(git_snapshot.get("detected_github_repo", "")),
        remote_url_arg=str(governance_state.get("effective_remote_url", "")),
        github_repo_arg=str(governance_state.get("effective_github_repo", "")),
    )
    git_runtime = _read_git_runtime(repo_root)
    last_checkpoint = (
        git_runtime.get("last_checkpoint")
        if isinstance(git_runtime.get("last_checkpoint"), dict)
        else {}
    )
    last_backup = (
        git_runtime.get("last_backup")
        if isinstance(git_runtime.get("last_backup"), dict)
        else {}
    )
    if not last_checkpoint:
        last_checkpoint = _git_latest_checkpoint_commit(repo_root)
    last_branch_action = (
        git_runtime.get("last_branch_action")
        if isinstance(git_runtime.get("last_branch_action"), dict)
        else {}
    )
    last_ready = (
        git_runtime.get("last_ready")
        if isinstance(git_runtime.get("last_ready"), dict)
        else {}
    )
    latest_run = _latest_run_payload(repo_root)

    upstream_branch = _git_upstream_branch(repo_root) if git_snapshot["present"] else ""
    upstream_remote = ""
    upstream_branch_name = ""
    if upstream_branch:
        upstream_remote, _, upstream_branch_name = upstream_branch.partition("/")
    remote_name = upstream_remote or ("origin" if str(remote_context.get("effective_remote_url", "")).strip() else "")
    remote_default_branch = _git_remote_default_branch(repo_root, remote_name) if git_snapshot["present"] else ""
    ahead_count = None
    behind_count = None
    if upstream_branch:
        ahead_behind = _git_ahead_behind(repo_root, "HEAD", upstream_branch)
        if ahead_behind is not None:
            ahead_count, behind_count = ahead_behind
    remote_default_ahead = None
    remote_default_behind = None
    if remote_name and remote_default_branch:
        remote_default_ref = f"{remote_name}/{remote_default_branch}"
        ahead_behind_default = _git_ahead_behind(repo_root, "HEAD", remote_default_ref)
        if ahead_behind_default is not None:
            remote_default_ahead, remote_default_behind = ahead_behind_default

    warnings: list[str] = []
    notes: list[str] = []
    next_actions: list[str] = []

    if not git_snapshot["present"]:
        warnings.append("git repository not detected at repo root.")
        if not orp_governed:
            next_actions.append("orp init")
    if not orp_governed:
        warnings.append("repo is not ORP-governed yet.")
        next_actions.append("orp init")
    else:
        if git_snapshot["protected_branch"] and not allow_protected_branch_work:
            warnings.append(
                f"current branch `{git_snapshot['branch']}` is protected; switch to a work branch before meaningful edits."
            )
            next_actions.append("orp branch start <topic>")
        if git_snapshot["dirty"]:
            warnings.append("working tree is dirty; create a checkpoint commit before handoff or readiness.")
            next_actions.append('orp checkpoint create -m "describe completed unit"')
            if remote_context["mode"] != "local_only":
                notes.append("current local work can be captured to a dedicated remote backup ref with `orp backup`.")
                next_actions.append('orp backup -m "backup current work" --json')
        if not handoff_path.exists():
            warnings.append("handoff file is missing from ORP governance runtime.")
        if not checkpoint_log_path.exists():
            warnings.append("checkpoint log is missing from ORP governance runtime.")
        if not agent_policy_path.exists():
            warnings.append("agent policy file is missing from ORP governance runtime.")

    if remote_context["mode"] == "local_only":
        notes.append("local-first mode active; no remote is required.")
    elif remote_context["mode"] == "github":
        notes.append(f"GitHub remote awareness active for `{remote_context['effective_github_repo']}`.")
    elif remote_context["mode"] == "remote":
        notes.append("non-GitHub remote awareness active.")

    if remote_context["mode"] != "local_only":
        if upstream_branch:
            if behind_count is not None and behind_count > 0:
                warnings.append(
                    f"current branch is behind upstream `{upstream_branch}` by {behind_count} commit(s)."
                )
            if ahead_count is not None and ahead_count > 0:
                notes.append(
                    f"current branch is ahead of upstream `{upstream_branch}` by {ahead_count} commit(s)."
                )
        elif git_snapshot["working_branch_safe"]:
            notes.append("current work branch has no upstream tracking branch yet.")
            if git_snapshot["branch"]:
                next_actions.append(f"git push -u origin {git_snapshot['branch']}")

        if remote_default_branch:
            notes.append(f"remote default branch is `{remote_default_branch}`.")
        elif remote_name:
            notes.append(f"remote `{remote_name}` is configured but its default branch is not known locally.")

    ready_for_agent_work = (
        bool(orp_governed)
        and bool(git_snapshot["present"])
        and bool(git_snapshot["working_branch_safe"])
        and not bool(git_snapshot["dirty"])
        and handoff_path.exists()
        and checkpoint_log_path.exists()
        and agent_policy_path.exists()
    )

    local_ready = ready_for_agent_work
    if not latest_run:
        local_ready = False
    if latest_run and latest_run.get("overall") != "PASS":
        local_ready = False
    checkpoint_at = _parse_iso8601_utc(last_checkpoint.get("timestamp_utc") or last_checkpoint.get("committed_at_utc"))
    validation_at = _parse_iso8601_utc(latest_run.get("ended_at_utc"))
    checkpoint_after_validation = bool(checkpoint_at and validation_at and checkpoint_at >= validation_at)
    if latest_run and validation_at and not checkpoint_after_validation:
        local_ready = False
    if latest_run and latest_run.get("overall") == "PASS" and not checkpoint_after_validation:
        warnings.append("latest passing validation run is newer than the latest checkpoint commit.")
        next_actions.append('orp checkpoint create -m "checkpoint validation-ready state"')
    if not latest_run:
        warnings.append("no validation run found. Run `orp gate run --profile <profile>` before readiness.")
    elif latest_run.get("overall") != "PASS":
        warnings.append(
            f"latest validation run `{latest_run.get('run_id', '')}` did not pass."
        )

    remote_ready = local_ready
    if remote_context["mode"] != "local_only":
        if behind_count is not None and behind_count > 0:
            remote_ready = False
        if git_snapshot["working_branch_safe"] and not upstream_branch:
            remote_ready = False

    readiness_scope = "local_only" if remote_context["mode"] == "local_only" else "remote_optional"
    if last_ready:
        last_ready_commit = str(last_ready.get("commit_full", "")).strip() or str(last_ready.get("commit", "")).strip()
        current_commit = str(git_snapshot.get("commit", "")).strip()
        if last_ready_commit and current_commit and last_ready_commit != current_commit:
            notes.append("latest recorded readiness applies to an older commit than the current HEAD.")

    return {
        "repo_root": str(repo_root),
        "orp_governed": bool(orp_governed),
        "mode": str(governance_state.get("mode", "repo_governance")) if orp_governed else "uninitialized",
        "config_path": _path_for_state(config_path, repo_root),
        "config_exists": config_path.exists(),
        "state_path": _path_for_state(state_path, repo_root),
        "state_exists": state_path.exists(),
        "manifest_path": _path_for_state(manifest_path, repo_root),
        "manifest_exists": manifest_path.exists(),
        "agent_policy_path": _path_for_state(agent_policy_path, repo_root),
        "agent_policy_exists": agent_policy_path.exists(),
        "handoff_path": _path_for_state(handoff_path, repo_root),
        "handoff_exists": handoff_path.exists(),
        "checkpoint_log_path": _path_for_state(checkpoint_log_path, repo_root),
        "checkpoint_log_exists": checkpoint_log_path.exists(),
        "git_runtime_path": _path_for_state(_git_runtime_path(repo_root) or Path(".git/orp/runtime.json"), repo_root),
        "git": {
            **git_snapshot,
            "effective_remote_mode": remote_context["mode"],
            "effective_remote_url": remote_context["effective_remote_url"],
            "effective_github_repo": remote_context["effective_github_repo"],
            "remote_name": remote_name,
            "upstream_branch": upstream_branch,
            "upstream_remote": upstream_remote,
            "upstream_branch_name": upstream_branch_name,
            "remote_default_branch": remote_default_branch,
            "ahead_count": ahead_count,
            "behind_count": behind_count,
            "remote_default_ahead_count": remote_default_ahead,
            "remote_default_behind_count": remote_default_behind,
        },
        "runtime": {
            "last_branch_action": last_branch_action,
            "last_checkpoint": last_checkpoint,
            "last_backup": last_backup,
            "last_ready": last_ready,
            "latest_run": latest_run,
        },
        "validation": {
            "available": bool(latest_run),
            "run": latest_run,
            "checkpoint_after_validation": checkpoint_after_validation if latest_run else False,
        },
        "readiness": {
            "scope": readiness_scope,
            "local_ready": local_ready,
            "remote_ready": remote_ready,
            "last_ready": last_ready,
        },
        "warnings": warnings,
        "notes": notes,
        "next_actions": _unique_strings(next_actions),
        "ready_for_agent_work": ready_for_agent_work,
    }


def _replace_vars(s: str, values: dict[str, str]) -> str:
    out = s
    for key, val in values.items():
        out = out.replace("{" + key + "}", val)
    return out


def _sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    return "sha256:" + h.hexdigest()


def _unique_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _slug_token(text: str, *, fallback: str = "item") -> str:
    token = re.sub(r"[^a-z0-9]+", "-", str(text or "").strip().lower()).strip("-")
    return token or fallback


def _resolve_config_paths(raw_paths: Any, repo_root: Path, vars_map: dict[str, str]) -> list[str]:
    out: list[str] = []
    if not isinstance(raw_paths, list):
        return out
    for raw in raw_paths:
        if not isinstance(raw, str):
            continue
        replaced = _replace_vars(raw, vars_map)
        path = Path(replaced)
        full = path if path.is_absolute() else repo_root / path
        out.append(_path_for_state(full, repo_root))
    return _unique_strings(out)


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
    live = {}
    if isinstance(board, dict):
        candidate_live = board.get("live_snapshot", board.get("live", {}))
        if isinstance(candidate_live, dict):
            live = candidate_live
    route_rows = []
    if isinstance(live, dict):
        # Some boards store this as "routes", others as "route_status".
        route_rows = live.get("route_status", live.get("routes", []))
    if not route_rows and isinstance(board, dict):
        direct_rows = board.get("route_status", [])
        if isinstance(direct_rows, list):
            route_rows = direct_rows
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
                    r"^(?:atom|ready)=(?P<atom>\S+).*ticket=(?P<ticket>\S+)\s+gate=(?P<gate>\S+).*deps=(?P<deps>\S+)",
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
        "starter_scaffold": bool(board.get("starter_scaffold", False)),
        "starter_note": str(board.get("starter_note", "")),
    }


def _collect_claim_context(
    config: dict[str, Any],
    run: dict[str, Any],
    evidence_paths: list[str],
) -> dict[str, Any]:
    project = config.get("project")
    project_name = ""
    if isinstance(project, dict):
        project_name = str(project.get("name", "")).strip()
    profile = str(run.get("profile", "")).strip() or "default"
    claim_id = f"{project_name}:{profile}" if project_name else profile

    canonical_artifacts: list[str] = []
    results = run.get("results", [])
    if isinstance(results, list):
        for row in results:
            if not isinstance(row, dict):
                continue
            raw_paths = row.get("evidence_paths", [])
            if isinstance(raw_paths, list):
                for raw in raw_paths:
                    if isinstance(raw, str):
                        canonical_artifacts.append(raw)
    canonical_artifacts.extend(evidence_paths)
    return {
        "claim_id": claim_id,
        "canonical_artifacts": _unique_strings(canonical_artifacts),
    }


def _config_epistemic_status(
    config: dict[str, Any], repo_root: Path, vars_map: dict[str, str]
) -> dict[str, Any]:
    raw = config.get("epistemic_status")
    if not isinstance(raw, dict):
        return {
            "overall": "",
            "starter_scaffold": False,
            "strongest_evidence_paths": [],
            "notes": [],
        }
    notes = [str(x) for x in raw.get("notes", []) if isinstance(x, str)]
    return {
        "overall": str(raw.get("overall", "")).strip(),
        "starter_scaffold": bool(raw.get("starter_scaffold", False)),
        "include_last_erdos_sync": bool(raw.get("include_last_erdos_sync", False)),
        "strongest_evidence_paths": _resolve_config_paths(
            raw.get("strongest_evidence_paths", []), repo_root, vars_map
        ),
        "notes": notes,
    }


def _last_erdos_sync_evidence_paths(state: dict[str, Any], repo_root: Path) -> list[str]:
    raw = state.get("last_erdos_sync")
    if not isinstance(raw, dict):
        return []

    paths: list[str] = []
    for key in ["out_all", "out_open", "out_closed", "out_active", "out_open_list"]:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value.strip())
            full = path if path.is_absolute() else repo_root / path
            paths.append(_path_for_state(full, repo_root))

    selected = raw.get("selected", [])
    if isinstance(selected, list):
        for row in selected:
            if not isinstance(row, dict):
                continue
            out_value = row.get("out")
            if isinstance(out_value, str) and out_value.strip():
                path = Path(out_value.strip())
                full = path if path.is_absolute() else repo_root / path
                paths.append(_path_for_state(full, repo_root))
    return _unique_strings(paths)


def _derive_epistemic_status(
    config: dict[str, Any],
    run_results: list[dict[str, Any]],
    state: dict[str, Any],
    repo_root: Path,
    vars_map: dict[str, str],
) -> dict[str, Any]:
    declared = _config_epistemic_status(config, repo_root, vars_map)
    stub_gates: list[str] = []
    starter_gates: list[str] = []
    evidence_gates: list[str] = []
    process_only_gates: list[str] = []
    notes = list(declared.get("notes", []))
    strongest_paths = list(declared.get("strongest_evidence_paths", []))

    for row in run_results:
        if not isinstance(row, dict):
            continue
        gate_id = str(row.get("gate_id", "")).strip()
        evidence_status = str(row.get("evidence_status", "")).strip()
        if evidence_status == "starter_stub":
            stub_gates.append(gate_id)
        elif evidence_status == "starter_scaffold":
            starter_gates.append(gate_id)
        elif evidence_status == "evidence":
            evidence_gates.append(gate_id)
            strongest_paths.extend(
                [str(x) for x in row.get("evidence_paths", []) if isinstance(x, str)]
            )
        else:
            process_only_gates.append(gate_id)

        note = str(row.get("evidence_note", "")).strip()
        if note:
            notes.append(note)

    if bool(declared.get("include_last_erdos_sync", False)):
        strongest_paths.extend(_last_erdos_sync_evidence_paths(state, repo_root))
    strongest_paths = _unique_strings(strongest_paths)
    notes = _unique_strings(notes)

    declared_overall = str(declared.get("overall", "")).strip()
    if declared_overall:
        overall = declared_overall
    elif stub_gates or starter_gates:
        overall = "starter_scaffold"
    elif strongest_paths:
        overall = "evidence_backed"
    else:
        overall = "process_only"

    starter_scaffold = bool(declared.get("starter_scaffold", False) or stub_gates or starter_gates)
    return {
        "overall": overall,
        "starter_scaffold": starter_scaffold,
        "stub_gates": _unique_strings(stub_gates),
        "starter_scaffold_gates": _unique_strings(starter_gates),
        "evidence_gates": _unique_strings(evidence_gates),
        "process_only_gates": _unique_strings(process_only_gates),
        "strongest_evidence_paths": strongest_paths,
        "notes": notes,
    }


def _discover_packs() -> tuple[Path, list[dict[str, str]]]:
    packs_root = _orp_repo_root() / "packs"
    packs: list[dict[str, str]] = []
    if not packs_root.exists():
        return packs_root, packs

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
        description = str(meta.get("description", "")).strip() if isinstance(meta, dict) else ""
        packs.append(
            {
                "id": pack_id,
                "version": version,
                "name": name,
                "description": description,
                "path": str(child),
            }
        )
    return packs_root, packs


def _about_payload() -> dict[str, Any]:
    _, packs = _discover_packs()
    return {
        "tool": {
            "name": "orp",
            "package": ORP_PACKAGE_NAME,
            "version": ORP_TOOL_VERSION,
            "description": "Open Research Protocol CLI for agent-friendly research workflows.",
            "agent_friendly": True,
        },
        "discovery": {
            "llms_txt": "llms.txt",
            "readme": "README.md",
            "start_here": "docs/START_HERE.md",
            "protocol": "PROTOCOL.md",
            "install": "INSTALL.md",
            "agent_integration": "AGENT_INTEGRATION.md",
            "agent_loop": "docs/AGENT_LOOP.md",
            "discover": "docs/DISCOVER.md",
            "exchange": "docs/EXCHANGE.md",
            "profile_packs": "docs/PROFILE_PACKS.md",
        },
        "artifacts": {
            "state_json": "orp/state.json",
            "run_json": "orp/artifacts/<run_id>/RUN.json",
            "run_summary_md": "orp/artifacts/<run_id>/RUN_SUMMARY.md",
            "packet_json": "orp/packets/<packet_id>.json",
            "packet_md": "orp/packets/<packet_id>.md",
            "discovery_scan_json": "orp/discovery/github/<scan_id>/SCAN.json",
            "discovery_scan_md": "orp/discovery/github/<scan_id>/SCAN_SUMMARY.md",
            "exchange_json": "orp/exchange/<exchange_id>/EXCHANGE.json",
            "exchange_summary_md": "orp/exchange/<exchange_id>/EXCHANGE_SUMMARY.md",
            "exchange_transfer_map_md": "orp/exchange/<exchange_id>/TRANSFER_MAP.md",
        },
        "schemas": {
            "config": "spec/v1/orp.config.schema.json",
            "packet": "spec/v1/packet.schema.json",
            "kernel": "spec/v1/kernel.schema.json",
            "kernel_proposal": "spec/v1/kernel-proposal.schema.json",
            "kernel_extension": "spec/v1/kernel-extension.schema.json",
            "youtube_source": "spec/v1/youtube-source.schema.json",
            "exchange_report": "spec/v1/exchange-report.schema.json",
            "profile_pack": "spec/v1/profile-pack.schema.json",
            "link_project": "spec/v1/link-project.schema.json",
            "link_session": "spec/v1/link-session.schema.json",
            "runner_machine": "spec/v1/runner-machine.schema.json",
            "runner_runtime": "spec/v1/runner-runtime.schema.json",
        },
        "abilities": [
            {
                "id": "kernel",
                "description": "Reasoning-kernel artifact scaffolding, validation, observation, proposal, and migration for promotable repository truth.",
                "entrypoints": [
                    ["kernel", "validate"],
                    ["kernel", "scaffold"],
                    ["kernel", "stats"],
                    ["kernel", "propose"],
                    ["kernel", "migrate"],
                ],
            },
            {
                "id": "youtube",
                "description": "Public YouTube metadata and transcript ingestion for agent-readable external source context.",
                "entrypoints": [
                    ["youtube", "inspect"],
                ],
            },
            {
                "id": "workspace",
                "description": "Hosted workspace auth, first-class workspace records, ideas, features, worlds, checkpoints, and worker operations.",
                "entrypoints": [
                    ["auth", "login"],
                    ["whoami"],
                    ["workspaces", "list"],
                    ["workspaces", "show"],
                    ["workspaces", "tabs"],
                    ["ideas", "list"],
                    ["world", "bind"],
                    ["checkpoint", "queue"],
                    ["agent", "work"],
                ],
            },
            {
                "id": "secrets",
                "description": "Hosted secret store for global API key inventory, provider metadata, and project-scoped resolution.",
                "entrypoints": [
                    ["secrets", "list"],
                    ["secrets", "show"],
                    ["secrets", "add"],
                    ["secrets", "bind"],
                    ["secrets", "resolve"],
                ],
            },
            {
                "id": "linking",
                "description": "Canonical CLI-owned repo/project/session linking for hosted routing and Rust-app interoperability.",
                "entrypoints": [
                    ["link", "project", "bind"],
                    ["link", "project", "show"],
                    ["link", "session", "register"],
                    ["link", "session", "list"],
                    ["link", "status"],
                    ["link", "doctor"],
                ],
            },
            {
                "id": "runner",
                "description": "Machine runner identity, enable/disable state, and hosted sync for linked repos and sessions.",
                "entrypoints": [
                    ["runner", "status"],
                    ["runner", "enable"],
                    ["runner", "disable"],
                    ["runner", "heartbeat"],
                    ["runner", "sync"],
                    ["runner", "work"],
                ],
            },
            {
                "id": "maintenance",
                "description": "Machine-local ORP update checks and daily maintenance scheduling.",
                "entrypoints": [
                    ["update"],
                    ["maintenance", "check"],
                    ["maintenance", "status"],
                    ["maintenance", "enable"],
                    ["maintenance", "disable"],
                ],
            },
            {
                "id": "schedule",
                "description": "Local scheduled Codex jobs with one-shot runs and macOS launchd enable/disable control.",
                "entrypoints": [
                    ["schedule", "add", "codex"],
                    ["schedule", "list"],
                    ["schedule", "show"],
                    ["schedule", "run"],
                    ["schedule", "enable"],
                    ["schedule", "disable"],
                ],
            },
            {
                "id": "discover",
                "description": "Profile-based GitHub discovery for repos, issues, and people signals.",
                "entrypoints": [
                    ["discover", "profile", "init"],
                    ["discover", "github", "scan"],
                ],
            },
            {
                "id": "exchange",
                "description": "Structured local-first synthesis of another repository or project directory into exchange artifacts and transfer maps.",
                "entrypoints": [
                    ["exchange", "repo", "synthesize"],
                ],
            },
            {
                "id": "collaborate",
                "description": "Built-in repository collaboration setup and workflow execution.",
                "entrypoints": [
                    ["collaborate", "init"],
                    ["collaborate", "workflows"],
                    ["collaborate", "gates"],
                    ["collaborate", "run"],
                ],
            },
            {
                "id": "frontier",
                "description": "Version-stack, milestone, phase, and live-frontier control for long-running agent-first research programs.",
                "entrypoints": [
                    ["frontier", "init"],
                    ["frontier", "state"],
                    ["frontier", "roadmap"],
                    ["frontier", "checklist"],
                    ["frontier", "stack"],
                    ["frontier", "add-version"],
                    ["frontier", "add-milestone"],
                    ["frontier", "add-phase"],
                    ["frontier", "set-live"],
                    ["frontier", "render"],
                    ["frontier", "doctor"],
                ],
            },
            {
                "id": "governance",
                "description": "Local-first repo governance, branch safety, checkpoint commits, backup refs, and runtime status.",
                "entrypoints": [
                    ["init"],
                    ["status"],
                    ["branch", "start"],
                    ["checkpoint", "create"],
                    ["backup"],
                    ["ready"],
                    ["doctor"],
                    ["cleanup"],
                ],
            },
            {
                "id": "erdos",
                "description": "Domain-specific Erdos sync and open-problem workflow support.",
                "entrypoints": [
                    ["erdos", "sync"],
                ],
            },
            {
                "id": "packs",
                "description": "Advanced/internal pack discovery and install surface.",
                "entrypoints": [
                    ["pack", "list"],
                    ["pack", "install"],
                    ["pack", "fetch"],
                ],
            },
        ],
        "commands": [
            {"name": "home", "path": ["home"], "json_output": True},
            {"name": "about", "path": ["about"], "json_output": True},
            {"name": "update", "path": ["update"], "json_output": True},
            {"name": "maintenance_check", "path": ["maintenance", "check"], "json_output": True},
            {"name": "maintenance_status", "path": ["maintenance", "status"], "json_output": True},
            {"name": "maintenance_enable", "path": ["maintenance", "enable"], "json_output": True},
            {"name": "maintenance_disable", "path": ["maintenance", "disable"], "json_output": True},
            {"name": "schedule_add_codex", "path": ["schedule", "add", "codex"], "json_output": True},
            {"name": "schedule_list", "path": ["schedule", "list"], "json_output": True},
            {"name": "schedule_show", "path": ["schedule", "show"], "json_output": True},
            {"name": "schedule_run", "path": ["schedule", "run"], "json_output": True},
            {"name": "schedule_enable", "path": ["schedule", "enable"], "json_output": True},
            {"name": "schedule_disable", "path": ["schedule", "disable"], "json_output": True},
            {"name": "kernel_validate", "path": ["kernel", "validate"], "json_output": True},
            {"name": "kernel_scaffold", "path": ["kernel", "scaffold"], "json_output": True},
            {"name": "kernel_stats", "path": ["kernel", "stats"], "json_output": True},
            {"name": "kernel_propose", "path": ["kernel", "propose"], "json_output": True},
            {"name": "kernel_migrate", "path": ["kernel", "migrate"], "json_output": True},
            {"name": "youtube_inspect", "path": ["youtube", "inspect"], "json_output": True},
            {"name": "auth_login", "path": ["auth", "login"], "json_output": True},
            {"name": "auth_verify", "path": ["auth", "verify"], "json_output": True},
            {"name": "auth_logout", "path": ["auth", "logout"], "json_output": True},
            {"name": "whoami", "path": ["whoami"], "json_output": True},
            {"name": "mode_list", "path": ["mode", "list"], "json_output": True},
            {"name": "mode_show", "path": ["mode", "show"], "json_output": True},
            {"name": "mode_nudge", "path": ["mode", "nudge"], "json_output": True},
            {"name": "secrets_list", "path": ["secrets", "list"], "json_output": True},
            {"name": "secrets_show", "path": ["secrets", "show"], "json_output": True},
            {"name": "secrets_add", "path": ["secrets", "add"], "json_output": True},
            {"name": "secrets_ensure", "path": ["secrets", "ensure"], "json_output": True},
            {"name": "secrets_keychain_list", "path": ["secrets", "keychain-list"], "json_output": True},
            {"name": "secrets_keychain_show", "path": ["secrets", "keychain-show"], "json_output": True},
            {"name": "secrets_sync_keychain", "path": ["secrets", "sync-keychain"], "json_output": True},
            {"name": "secrets_update", "path": ["secrets", "update"], "json_output": True},
            {"name": "secrets_archive", "path": ["secrets", "archive"], "json_output": True},
            {"name": "secrets_bind", "path": ["secrets", "bind"], "json_output": True},
            {"name": "secrets_unbind", "path": ["secrets", "unbind"], "json_output": True},
            {"name": "secrets_resolve", "path": ["secrets", "resolve"], "json_output": True},
            {"name": "workspaces_list", "path": ["workspaces", "list"], "json_output": True},
            {"name": "workspaces_show", "path": ["workspaces", "show"], "json_output": True},
            {"name": "workspaces_tabs", "path": ["workspaces", "tabs"], "json_output": True},
            {"name": "workspaces_timeline", "path": ["workspaces", "timeline"], "json_output": True},
            {"name": "workspaces_add", "path": ["workspaces", "add"], "json_output": True},
            {"name": "workspaces_update", "path": ["workspaces", "update"], "json_output": True},
            {"name": "workspaces_push_state", "path": ["workspaces", "push-state"], "json_output": True},
            {"name": "workspaces_add_event", "path": ["workspaces", "add-event"], "json_output": True},
            {"name": "ideas_list", "path": ["ideas", "list"], "json_output": True},
            {"name": "idea_show", "path": ["idea", "show"], "json_output": True},
            {"name": "idea_add", "path": ["idea", "add"], "json_output": True},
            {"name": "idea_update", "path": ["idea", "update"], "json_output": True},
            {"name": "idea_remove", "path": ["idea", "remove"], "json_output": True},
            {"name": "idea_restore", "path": ["idea", "restore"], "json_output": True},
            {"name": "feature_list", "path": ["feature", "list"], "json_output": True},
            {"name": "feature_show", "path": ["feature", "show"], "json_output": True},
            {"name": "feature_add", "path": ["feature", "add"], "json_output": True},
            {"name": "feature_update", "path": ["feature", "update"], "json_output": True},
            {"name": "feature_remove", "path": ["feature", "remove"], "json_output": True},
            {"name": "world_show", "path": ["world", "show"], "json_output": True},
            {"name": "world_bind", "path": ["world", "bind"], "json_output": True},
            {"name": "link_project_bind", "path": ["link", "project", "bind"], "json_output": True},
            {"name": "link_project_show", "path": ["link", "project", "show"], "json_output": True},
            {"name": "link_project_status", "path": ["link", "project", "status"], "json_output": True},
            {"name": "link_project_unbind", "path": ["link", "project", "unbind"], "json_output": True},
            {"name": "link_session_register", "path": ["link", "session", "register"], "json_output": True},
            {"name": "link_session_list", "path": ["link", "session", "list"], "json_output": True},
            {"name": "link_session_show", "path": ["link", "session", "show"], "json_output": True},
            {"name": "link_session_set_primary", "path": ["link", "session", "set-primary"], "json_output": True},
            {"name": "link_session_archive", "path": ["link", "session", "archive"], "json_output": True},
            {"name": "link_session_unarchive", "path": ["link", "session", "unarchive"], "json_output": True},
            {"name": "link_session_remove", "path": ["link", "session", "remove"], "json_output": True},
            {"name": "link_session_import_rust", "path": ["link", "session", "import-rust"], "json_output": True},
            {"name": "link_status", "path": ["link", "status"], "json_output": True},
            {"name": "link_doctor", "path": ["link", "doctor"], "json_output": True},
            {"name": "runner_status", "path": ["runner", "status"], "json_output": True},
            {"name": "runner_enable", "path": ["runner", "enable"], "json_output": True},
            {"name": "runner_disable", "path": ["runner", "disable"], "json_output": True},
            {"name": "runner_heartbeat", "path": ["runner", "heartbeat"], "json_output": True},
            {"name": "runner_sync", "path": ["runner", "sync"], "json_output": True},
            {"name": "runner_work", "path": ["runner", "work"], "json_output": True},
            {"name": "runner_cancel", "path": ["runner", "cancel"], "json_output": True},
            {"name": "runner_retry", "path": ["runner", "retry"], "json_output": True},
            {"name": "checkpoint_queue", "path": ["checkpoint", "queue"], "json_output": True},
            {"name": "agent_work", "path": ["agent", "work"], "json_output": True},
            {"name": "discover_profile_init", "path": ["discover", "profile", "init"], "json_output": True},
            {"name": "discover_github_scan", "path": ["discover", "github", "scan"], "json_output": True},
            {"name": "exchange_repo_synthesize", "path": ["exchange", "repo", "synthesize"], "json_output": True},
            {"name": "collaborate_init", "path": ["collaborate", "init"], "json_output": True},
            {"name": "collaborate_workflows", "path": ["collaborate", "workflows"], "json_output": True},
            {"name": "collaborate_gates", "path": ["collaborate", "gates"], "json_output": True},
            {"name": "collaborate_run", "path": ["collaborate", "run"], "json_output": True},
            {"name": "init", "path": ["init"], "json_output": True},
            {"name": "status", "path": ["status"], "json_output": True},
            {"name": "frontier_init", "path": ["frontier", "init"], "json_output": True},
            {"name": "frontier_state", "path": ["frontier", "state"], "json_output": True},
            {"name": "frontier_roadmap", "path": ["frontier", "roadmap"], "json_output": True},
            {"name": "frontier_checklist", "path": ["frontier", "checklist"], "json_output": True},
            {"name": "frontier_stack", "path": ["frontier", "stack"], "json_output": True},
            {"name": "frontier_add_version", "path": ["frontier", "add-version"], "json_output": True},
            {"name": "frontier_add_milestone", "path": ["frontier", "add-milestone"], "json_output": True},
            {"name": "frontier_add_phase", "path": ["frontier", "add-phase"], "json_output": True},
            {"name": "frontier_set_live", "path": ["frontier", "set-live"], "json_output": True},
            {"name": "frontier_render", "path": ["frontier", "render"], "json_output": True},
            {"name": "frontier_doctor", "path": ["frontier", "doctor"], "json_output": True},
            {"name": "branch_start", "path": ["branch", "start"], "json_output": True},
            {"name": "checkpoint_create", "path": ["checkpoint", "create"], "json_output": True},
            {"name": "backup", "path": ["backup"], "json_output": True},
            {"name": "ready", "path": ["ready"], "json_output": True},
            {"name": "doctor", "path": ["doctor"], "json_output": True},
            {"name": "cleanup", "path": ["cleanup"], "json_output": True},
            {"name": "gate_run", "path": ["gate", "run"], "json_output": True},
            {"name": "packet_emit", "path": ["packet", "emit"], "json_output": True},
            {"name": "erdos_sync", "path": ["erdos", "sync"], "json_output": True},
            {"name": "pack_list", "path": ["pack", "list"], "json_output": True},
            {"name": "pack_install", "path": ["pack", "install"], "json_output": True},
            {"name": "pack_fetch", "path": ["pack", "fetch"], "json_output": True},
            {"name": "report_summary", "path": ["report", "summary"], "json_output": True},
        ],
        "notes": [
            "ORP files are process-only and are not evidence.",
            "Canonical evidence lives in repo artifact paths outside ORP docs.",
            "Default CLI output is human-readable; listed commands with json_output=true also support --json.",
            "Reasoning-kernel artifacts shape promotable repository truth for tasks, decisions, hypotheses, experiments, checkpoints, policies, and results.",
            "Kernel evolution in ORP should stay explicit: observe real usage, propose changes, and migrate artifacts through versioned CLI surfaces rather than silent agent mutation.",
            "YouTube inspection is a built-in ORP ability exposed through `orp youtube inspect`, returning public metadata plus full transcript text and segments whenever public caption tracks are available.",
            "Discovery profiles in ORP are portable search-intent files managed directly by ORP.",
            "Knowledge exchange is a built-in ORP ability exposed through `orp exchange repo synthesize`, producing structured exchange artifacts and transfer maps for local or remote source repositories.",
            "Collaboration is a built-in ORP ability exposed through `orp collaborate ...`.",
            "Frontier control is a built-in ORP ability exposed through `orp frontier ...`, separating the exact live point, the exact active milestone, the near structured checklist, and the farther major-version stack.",
            "Agent modes are lightweight optional overlays for taste, perspective shifts, and fresh movement; `orp mode nudge sleek-minimal-progressive --json` gives agents a deterministic reminder they can call on when they want a deeper, wider, top-down, or rotated lens without changing ORP's core artifact boundaries.",
            "Project/session linking is a built-in ORP ability exposed through `orp link ...` and stored machine-locally under `.git/orp/link/`.",
            "Secrets are easiest to understand as saved keys and tokens: humans usually run `orp secrets add ...` and paste the value at the prompt, agents usually pipe the value with `--value-stdin`, and local macOS Keychain caching plus hosted sync are optional layers on top.",
            "Machine runner identity, heartbeat, hosted sync, prompt-job execution, and lease control are built into ORP through `orp runner status`, `orp runner enable`, `orp runner disable`, `orp runner heartbeat`, `orp runner sync`, `orp runner work`, `orp runner cancel`, and `orp runner retry`.",
            "Repo governance is built into ORP through `orp init`, `orp status`, `orp branch start`, `orp checkpoint create`, `orp backup`, `orp ready`, `orp doctor`, and `orp cleanup`.",
            "Hosted workspace operations are built directly into ORP under `orp workspaces ...`, plus the linked auth/ideas/feature/world/checkpoint/agent surfaces.",
        ],
        "packs": packs,
    }


def _collaboration_workflow_map() -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in COLLABORATION_WORKFLOWS}


def _collaboration_workflow_payload(repo_root: Path) -> dict[str, Any]:
    workflows: list[dict[str, Any]] = []
    for row in COLLABORATION_WORKFLOWS:
        config_name = str(row.get("config", "")).strip()
        config_path = (repo_root / config_name).resolve()
        workflows.append(
            {
                "id": row["id"],
                "profile": row["profile"],
                "config": config_name,
                "config_exists": config_path.exists(),
                "description": row["description"],
                "gate_ids": list(row["gate_ids"]),
            }
        )
    return {
        "workspace_ready": (repo_root / "orp.issue-smashers.yml").exists(),
        "recommended_init_command": "orp collaborate init",
        "workflows": workflows,
    }


def _git_home_context(repo_root: Path) -> dict[str, Any]:
    context = {
        "present": False,
        "branch": "",
        "commit": "",
    }
    try:
        inside = subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        context["present"] = inside == "true"
    except Exception:
        return context

    if not context["present"]:
        return context

    try:
        context["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass
    try:
        context["commit"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        pass
    return context


def _home_payload(repo_root: Path, config_arg: str) -> dict[str, Any]:
    about = _about_payload()
    collaboration = _collaboration_workflow_payload(repo_root)
    maintenance = _maintenance_agent_status()
    schedules = _list_schedule_jobs_payload()
    config_path = Path(config_arg)
    if not config_path.is_absolute():
        config_path = repo_root / config_path
    config_path = config_path.resolve()

    state_path = repo_root / "orp" / "state.json"
    state_exists = state_path.exists()
    state: dict[str, Any] = {}
    if state_exists:
        try:
            state = _read_json(state_path)
        except Exception:
            state = {}

    git_context = _git_home_context(repo_root)
    last_run_id = str(state.get("last_run_id", "")).strip() if isinstance(state, dict) else ""
    last_packet_id = str(state.get("last_packet_id", "")).strip() if isinstance(state, dict) else ""
    runtime_initialized = state_exists or (repo_root / "orp").exists()

    daily_loop = [
        {
            "label": "Inspect the saved workspace ledger inventory",
            "command": "orp workspace list",
        },
        {
            "label": "Inspect saved paths and exact recovery commands for the main workspace",
            "command": "orp workspace tabs main",
        },
        {
            "label": "Save a new API key or token interactively when you need one",
            "command": 'orp secrets add --alias <alias> --label "<label>" --provider <provider>',
        },
        {
            "label": "Create a local checkpoint commit",
            "command": 'orp checkpoint create -m "capture loop state" --json',
        },
        {
            "label": "Inspect the exact live frontier point",
            "command": "orp frontier state --json",
        },
        {
            "label": "Inspect local scheduled Codex jobs",
            "command": "orp schedule list --json",
        },
        {
            "label": "Get an optional creativity/perspective nudge",
            "command": "orp mode nudge sleek-minimal-progressive --json",
        },
    ]

    quick_actions = [
        {
            "label": "Inspect the saved workspace ledger inventory",
            "command": "orp workspace list",
        },
        {
            "label": "Inspect the saved tabs in the main workspace ledger",
            "command": "orp workspace tabs main",
        },
        {
            "label": "Add a saved path/session directly to the main workspace ledger",
            "command": 'orp workspace add-tab main --path /absolute/path/to/project --resume-command "codex resume <id>"',
        },
        {
            "label": "Remove a saved path/session directly from the main workspace ledger",
            "command": "orp workspace remove-tab main --path /absolute/path/to/project",
        },
        {
            "label": "Initialize a frontier version stack for this repo",
            "command": "orp frontier init --program-id <program-id> --json",
        },
        {
            "label": "Connect ORP to the hosted workspace",
            "command": "orp auth login",
        },
        {
            "label": "Inspect the current hosted workspace identity",
            "command": "orp whoami --json",
        },
        {
            "label": "Get an optional creative perspective nudge for agent work",
            "command": "orp mode nudge sleek-minimal-progressive --json",
        },
        {
            "label": "List first-class hosted workspaces",
            "command": "orp workspaces list --json",
        },
        {
            "label": "Inspect saved keys and tokens already known to ORP",
            "command": "orp secrets list --json",
        },
        {
            "label": "Reuse a saved key or prompt for it and save it for this project",
            "command": "orp secrets ensure --alias <alias> --provider <provider> --current-project --json",
        },
        {
            "label": "List locally cached Keychain-backed secrets on this Mac",
            "command": "orp secrets keychain-list --json",
        },
        {
            "label": "Sync one hosted secret into the local macOS Keychain",
            "command": "orp secrets sync-keychain <alias-or-id> --json",
        },
        {
            "label": "Resolve one provider secret for the current project with local-first lookup",
            "command": "orp secrets resolve --provider openai --reveal --local-first --json",
        },
        {
            "label": "Inspect a YouTube video and ingest full public transcript context",
            "command": "orp youtube inspect https://www.youtube.com/watch?v=<video_id> --json",
        },
        {
            "label": "List hosted ideas in the current workspace",
            "command": "orp ideas list --json",
        },
        {
            "label": "Inspect local project/session link state",
            "command": "orp link status --json",
        },
        {
            "label": "Inspect machine runner state",
            "command": "orp runner status --json",
        },
        {
            "label": "Scaffold a discovery profile for GitHub scanning",
            "command": "orp discover profile init --json",
        },
        {
            "label": "Deeply synthesize another repo or local project into exchange artifacts",
            "command": "orp exchange repo synthesize /path/to/source --json",
        },
        {
            "label": "Inspect local repo governance status",
            "command": "orp status --json",
        },
        {
            "label": "Initialize collaboration scaffolding here",
            "command": "orp collaborate init",
        },
        {
            "label": "Inspect collaboration workflows",
            "command": "orp collaborate workflows --json",
        },
        {
            "label": "Inspect the full collaboration gate chain",
            "command": "orp collaborate gates --workflow full_flow --json",
        },
        {
            "label": "Run the full collaboration workflow",
            "command": "orp collaborate run --workflow full_flow --json",
        },
        {
            "label": "Inspect machine-readable capability surface",
            "command": "orp about --json",
        },
        {
            "label": "Inspect ORP maintenance and cached update state",
            "command": "orp maintenance status --json",
        },
        {
            "label": "Run an ORP maintenance check now",
            "command": "orp maintenance check --json",
        },
    ]
    if schedules.get("jobs"):
        quick_actions.append(
            {
                "label": "List local scheduled Codex jobs",
                "command": "orp schedule list --json",
            }
        )
    else:
        quick_actions.append(
            {
                "label": "Create one scheduled Codex job",
                "command": 'orp schedule add codex --name <name> --prompt "Summarize this repo" --json',
            }
        )
    if not runtime_initialized:
        quick_actions.insert(
            0,
            {
                "label": "Initialize ORP repo governance here",
                "command": "orp init",
            },
        )
        quick_actions.insert(
            1,
            {
                "label": "Add a new provider key interactively",
                "command": 'orp secrets add --alias <alias> --label "<label>" --provider <provider>',
            },
        )
    else:
        quick_actions.insert(
            0,
            {
                "label": "Inspect repo governance safety and branch state",
                "command": "orp status --json",
            },
        )
        quick_actions.insert(
            1,
            {
                "label": "Start a safe work branch",
                "command": "orp branch start work/<topic> --json",
            },
        )
        quick_actions.insert(
            2,
            {
                "label": "Create a structured checkpoint commit",
                "command": 'orp checkpoint create -m "describe completed unit" --json',
            },
        )
        quick_actions.insert(
            3,
            {
                "label": "Validate the starter kernel artifact",
                "command": "orp kernel validate analysis/orp.kernel.task.yml --json",
            },
        )
        quick_actions.insert(
            4,
            {
                "label": "Checkpoint and back up current work to a dedicated remote ref",
                "command": 'orp backup -m "backup current work" --json',
            },
        )
        quick_actions.insert(
            5,
            {
                "label": "Inspect kernel validation pressure across recorded runs",
                "command": "orp kernel stats --json",
            },
        )
        quick_actions.insert(
            6,
            {
                "label": "Inspect the exact live frontier point",
                "command": "orp frontier state --json",
            },
        )
        quick_actions.insert(
            7,
            {
                "label": "Inspect the active milestone roadmap",
                "command": "orp frontier roadmap --json",
            },
        )
        quick_actions.insert(
            8,
            {
                "label": "Mark the repo locally ready after validation",
                "command": "orp ready --json",
            },
        )
        quick_actions.insert(
            9,
            {
                "label": "Inspect local project/session link state",
                "command": "orp link status --json",
            },
        )
        quick_actions.insert(
            9,
            {
                "label": "Add a new provider key interactively",
                "command": 'orp secrets add --alias <alias> --label "<label>" --provider <provider>',
            },
        )
        quick_actions.insert(
            10,
            {
                "label": "Inspect machine runner state",
                "command": "orp runner status --json",
            },
        )
        quick_actions.insert(
            11,
            {
                "label": "Inspect and repair governance health",
                "command": "orp doctor --json",
            },
        )
        quick_actions.insert(
            12,
            {
                "label": "Inspect safe cleanup candidates",
                "command": "orp cleanup --json",
            },
        )
    if config_path.exists():
        quick_actions.append(
            {
                "label": "Run the default profile",
                "command": "orp gate run --profile default --json",
            }
        )
    if last_run_id:
        quick_actions.append(
            {
                "label": "Summarize the last run",
                "command": "orp report summary --json",
            }
        )
    if bool(maintenance.get("cached_update_available")):
        quick_actions.insert(
            0,
            {
                "label": "Update ORP to the latest published release",
                "command": "orp update --yes",
            },
        )
    elif bool(maintenance.get("check_due")):
        quick_actions.insert(
            0,
            {
                "label": "Refresh ORP maintenance and update state",
                "command": "orp maintenance check --json",
            },
        )
    if _maintenance_platform_supported() and not bool(maintenance.get("enabled")):
        quick_actions.append(
            {
                "label": "Enable daily ORP maintenance on this Mac",
                "command": "orp maintenance enable --json",
            }
        )

    return {
        "tool": about["tool"],
        "repo": {
            "root_path": str(repo_root),
            "config_path": _path_for_state(config_path, repo_root),
            "config_exists": config_path.exists(),
            "git": git_context,
        },
        "runtime": {
            "initialized": runtime_initialized,
            "state_path": _path_for_state(state_path, repo_root),
            "state_exists": state_exists,
            "last_run_id": last_run_id,
            "last_packet_id": last_packet_id,
        },
        "maintenance": maintenance,
        "schedule": schedules,
        "daily_loop": daily_loop,
        "abilities": [
            {
                "id": "workspace",
                "description": "Saved workspace ledgers, copyable recovery commands, and direct add/remove flows for paths and Codex or Claude resume commands.",
                "entrypoints": [
                    "orp workspace list",
                    "orp workspace tabs main",
                    'orp workspace add-tab main --path /absolute/path/to/project --resume-command "codex resume <id>"',
                    "orp workspace remove-tab main --path /absolute/path/to/project",
                    "orp workspace sync main",
                ],
            },
            {
                "id": "hosted",
                "description": "Hosted identity, ideas, first-class workspace records, runner lanes, and control-plane status.",
                "entrypoints": [
                    "orp auth login",
                    "orp whoami --json",
                    "orp ideas list --json",
                    "orp workspaces list --json",
                    "orp runner status --json",
                    "orp agent work --once --json",
                ],
            },
            {
                "id": "modes",
                "description": "Lightweight optional cognitive overlays for taste, creativity, perspective shifts, and exploratory momentum.",
                "entrypoints": [
                    "orp mode list --json",
                    "orp mode show sleek-minimal-progressive --json",
                    "orp mode nudge sleek-minimal-progressive --json",
                ],
            },
            {
                "id": "secrets",
                "description": "Saved API keys and tokens, with an interactive human flow, a stdin agent flow, optional local macOS Keychain caching, and optional hosted sync.",
                "entrypoints": [
                    "orp secrets list --json",
                    "orp secrets show <alias-or-id> --json",
                    'orp secrets add --alias <alias> --label "<label>" --provider <provider>',
                    "orp secrets ensure --alias <alias> --provider <provider> --current-project --json",
                    "orp secrets keychain-list --json",
                    "orp secrets keychain-show <alias-or-id> --json",
                    "orp secrets sync-keychain <alias-or-id> --json",
                    "orp secrets bind <alias-or-id> --idea-id <idea-id> --json",
                    "orp secrets resolve --provider <provider> --reveal --local-first --json",
                ],
            },
            {
                "id": "linking",
                "description": "Canonical CLI-owned repo/project/session linking for hosted routing and Rust-app interoperability.",
                "entrypoints": [
                    "orp link project bind --idea-id <idea-id> --json",
                    "orp link session register --orp-session-id <id> --label <label> --codex-session-id <session-id> --primary --json",
                    "orp link session import-rust --json",
                    "orp link status --json",
                    "orp link doctor --json",
                ],
            },
            {
                "id": "runner",
                "description": "Machine runner identity, local enable/disable state, and hosted sync for linked repos and sessions.",
                "entrypoints": [
                    "orp runner status --json",
                    "orp runner enable --json",
                    "orp runner disable --json",
                    "orp runner heartbeat --json",
                    "orp runner sync --json",
                    "orp runner work --once --json",
                ],
            },
            {
                "id": "maintenance",
                "description": "Machine-local ORP update checks and daily launchd scheduling on macOS.",
                "entrypoints": [
                    "orp update --json",
                    "orp maintenance check --json",
                    "orp maintenance status --json",
                    "orp maintenance enable --json",
                    "orp maintenance disable --json",
                ],
            },
            {
                "id": "schedule",
                "description": "Local scheduled Codex jobs with one-shot runs and macOS launchd enable/disable control.",
                "entrypoints": [
                    "orp schedule add codex --name <name> --prompt <prompt> --json",
                    "orp schedule list --json",
                    "orp schedule show <name-or-id> --json",
                    "orp schedule run <name-or-id> --json",
                    "orp schedule enable <name-or-id> --json",
                    "orp schedule disable <name-or-id> --json",
                ],
            },
            {
                "id": "discover",
                "description": "Profile-based GitHub discovery for repos, issues, and people signals.",
                "entrypoints": [
                    "orp discover profile init --json",
                    f"orp discover github scan --profile {DEFAULT_DISCOVER_PROFILE} --json",
                ],
            },
            {
                "id": "exchange",
                "description": "Structured local-first synthesis of another repo or project directory into exchange artifacts and transfer maps.",
                "entrypoints": [
                    "orp exchange repo synthesize /path/to/source --json",
                ],
            },
            {
                "id": "collaborate",
                "description": "Built-in repository collaboration setup and workflow execution.",
                "entrypoints": [
                    "orp collaborate init",
                    "orp collaborate workflows --json",
                    "orp collaborate run --workflow full_flow --json",
                ],
            },
            {
                "id": "frontier",
                "description": "Version-stack, milestone, phase, and exact live-frontier control for long-running agent-first research programs.",
                "entrypoints": [
                    "orp frontier init --program-id <program-id> --json",
                    "orp frontier state --json",
                    "orp frontier roadmap --json",
                    "orp frontier checklist --json",
                    "orp frontier stack --json",
                ],
            },
            {
                "id": "governance",
                "description": "Local-first repo governance, branch safety, checkpoint commits, backup refs, and runtime status.",
                "entrypoints": [
                    "orp init",
                    "orp status --json",
                    "orp branch start work/<topic> --json",
                    'orp checkpoint create -m "describe completed unit" --json',
                    'orp backup -m "backup current work" --json',
                    "orp ready --json",
                    "orp doctor --json",
                    "orp cleanup --json",
                ],
            },
            {
                "id": "erdos",
                "description": "Domain-specific Erdos sync and problem workflow support.",
                "entrypoints": [
                    "orp erdos sync --json",
                ],
            },
        ],
        "collaboration": collaboration,
        "packs": about["packs"],
        "discovery": about["discovery"],
        "quick_actions": quick_actions,
        "notes": about["notes"],
    }


def _truncate(text: str, *, limit: int = 76) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _render_home_screen(payload: dict[str, Any]) -> str:
    tool = payload.get("tool", {})
    repo = payload.get("repo", {})
    runtime = payload.get("runtime", {})
    maintenance = payload.get("maintenance", {})
    daily_loop = payload.get("daily_loop", [])
    abilities = payload.get("abilities", [])
    collaboration = payload.get("collaboration", {})
    packs = payload.get("packs", [])
    discovery = payload.get("discovery", {})
    quick_actions = payload.get("quick_actions", [])

    lines: list[str] = []
    lines.append(f"ORP {tool.get('version', 'unknown')}")
    lines.append("Agent-first CLI for workspace ledgers, secrets, scheduling, governed execution, and research workflows.")
    lines.append("")
    lines.append("Repo")
    lines.append(f"  root: {repo.get('root_path', '')}")
    lines.append(
        f"  config: {repo.get('config_path', '')} ({'present' if repo.get('config_exists') else 'missing'})"
    )

    git_ctx = repo.get("git", {})
    if isinstance(git_ctx, dict) and git_ctx.get("present"):
        branch = str(git_ctx.get("branch", "")).strip() or "(no branch)"
        commit = str(git_ctx.get("commit", "")).strip() or "(no commits yet)"
        lines.append(f"  git: yes, branch={branch}, commit={commit}")
    else:
        lines.append("  git: no")

    lines.append("")
    lines.append("Runtime")
    lines.append(
        f"  initialized: {'yes' if runtime.get('initialized') else 'no'}"
    )
    lines.append(
        f"  state: {runtime.get('state_path', '')} ({'present' if runtime.get('state_exists') else 'missing'})"
    )
    last_run_id = str(runtime.get("last_run_id", "")).strip()
    last_packet_id = str(runtime.get("last_packet_id", "")).strip()
    lines.append(f"  last_run_id: {last_run_id or '(none)'}")
    lines.append(f"  last_packet_id: {last_packet_id or '(none)'}")

    lines.append("")
    lines.append("Maintenance")
    lines.append(f"  enabled: {'yes' if maintenance.get('enabled') else 'no'}")
    lines.append(f"  last_checked_at: {maintenance.get('last_checked_at', '') or 'never'}")
    lines.append(f"  check_due: {'yes' if maintenance.get('check_due') else 'no'}")
    if maintenance.get("cached_update_available"):
        latest = str(maintenance.get("cached_latest_version", "")).strip() or "unknown"
        lines.append(f"  cached_update_available: yes ({latest})")
    else:
        lines.append("  cached_update_available: no")
    schedule = maintenance.get("schedule", {})
    if isinstance(schedule, dict) and schedule.get("hour") is not None and schedule.get("minute") is not None:
        lines.append(f"  schedule: daily at {int(schedule['hour']):02d}:{int(schedule['minute']):02d}")
    if isinstance(maintenance, dict) and isinstance(maintenance.get("state_path"), str):
        lines.append(f"  state: {maintenance.get('state_path', '')}")

    lines.append("")
    lines.append("Daily Loop")
    if isinstance(daily_loop, list):
        for row in daily_loop:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label", "")).strip()
            command = str(row.get("command", "")).strip()
            if not label or not command:
                continue
            lines.append(f"  - {label}")
            lines.append(f"    {command}")

    lines.append("")
    lines.append("Command Families")
    if isinstance(abilities, list) and abilities:
        ability_map = {
            str(row.get("id", "")).strip(): row
            for row in abilities
            if isinstance(row, dict) and str(row.get("id", "")).strip()
        }
        visible_ability_ids = [
            "workspace",
            "secrets",
            "governance",
            "frontier",
            "schedule",
            "modes",
            "hosted",
            "discover",
        ]
        shown = 0
        for ability_id in visible_ability_ids:
            row = ability_map.get(ability_id)
            if not isinstance(row, dict):
                continue
            desc = _truncate(str(row.get("description", "")).strip())
            lines.append(f"  - {ability_id}")
            if desc:
                lines.append(f"    {desc}")
            shown += 1
        remaining = max(len(ability_map) - shown, 0)
        if remaining:
            lines.append(f"  - ... and {remaining} more in `orp about --json`")

    lines.append("")
    lines.append("Collaboration")
    lines.append(
        f"  workspace_ready: {'yes' if collaboration.get('workspace_ready') else 'no'}"
    )
    lines.append(
        f"  fastest_setup: {collaboration.get('recommended_init_command', 'orp collaborate init')}"
    )
    workflows = collaboration.get("workflows", [])
    if isinstance(workflows, list):
        for row in workflows[:2]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"  - {row.get('id', '')}: {_truncate(str(row.get('description', '')).strip(), limit=64)}"
            )
        if len(workflows) > 2:
            lines.append("  - ... run `orp collaborate workflows --json` for the full list")

    lines.append("")
    lines.append("Discovery")
    for key in ["readme", "start_here", "protocol", "agent_integration", "agent_loop", "discover", "profile_packs"]:
        value = discovery.get(key)
        if isinstance(value, str) and value:
            lines.append(f"  {key}: {value}")

    lines.append("")
    lines.append("Quick Actions")
    if isinstance(quick_actions, list):
        for row in quick_actions[:10]:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label", "")).strip()
            command = str(row.get("command", "")).strip()
            if not label or not command:
                continue
            lines.append(f"  - {label}")
            lines.append(f"    {command}")
        remaining = max(len(quick_actions) - 10, 0)
        if remaining:
            lines.append(f"  - ... and {remaining} more in `orp home --json`")

    lines.append("")
    lines.append("Tip")
    lines.append("  Run `orp home --json` or `orp about --json` for machine-readable output.")
    lines.append("")
    return "\n".join(lines)


def _perform_github_discovery_scan(
    *,
    repo_root: Path,
    profile_path: Path,
    scan_id: str,
    repos_fixture_path: Path | None,
    issues_fixture_path: Path | None,
) -> dict[str, Any]:
    _ensure_dirs(repo_root)
    raw_profile = _read_json(profile_path)
    profile = _normalize_discover_profile(raw_profile)
    owner = profile["github"]["owner"]
    owner_login = owner["login"]
    if not owner_login or owner_login == "YOUR_GITHUB_OWNER":
        raise RuntimeError("discovery profile must set discover.github.owner.login")

    token_context = _github_token_context()
    headers = _github_headers(token_context["token"])
    owner_type = owner["type"]
    if owner_type == "auto":
        owner_type = _github_detect_owner_type(owner_login, headers)

    repos_fixture = _load_fixture_json(repos_fixture_path) if repos_fixture_path else None
    issues_fixture = _load_fixture_json(issues_fixture_path) if issues_fixture_path else None
    repo_limit = int(profile["github"]["ranking"]["repo_sample_size"])
    if repos_fixture is not None:
        if not isinstance(repos_fixture, list):
            raise RuntimeError("repos fixture must be a JSON array")
        repos_raw = [row for row in repos_fixture if isinstance(row, dict)]
    else:
        repos_raw = _github_list_repos(
            owner_login=owner_login,
            owner_type=owner_type,
            limit=repo_limit,
            headers=headers,
        )

    ranked_repos: list[dict[str, Any]] = []
    for repo in repos_raw:
        if bool(repo.get("archived")):
            continue
        score, reasons = _score_repo(repo, profile)
        if score < 0:
            continue
        row = {
            "name": str(repo.get("name", "")).strip(),
            "full_name": str(repo.get("full_name", "")).strip(),
            "url": str(repo.get("html_url", "")).strip(),
            "description": str(repo.get("description", "") or "").strip(),
            "language": str(repo.get("language", "") or "").strip(),
            "topics": [str(item).strip() for item in repo.get("topics", []) if isinstance(item, str)],
            "score": score,
            "reasons": reasons,
            "updated_at": str(repo.get("updated_at", "") or "").strip(),
            "open_issues_count": int(repo.get("open_issues_count") or 0),
        }
        ranked_repos.append(row)

    ranked_repos = sorted(
        ranked_repos,
        key=lambda row: (
            -int(row["score"]),
            _recency_sort_key(str(row["updated_at"])),
            str(row["full_name"]),
        ),
        reverse=False,
    )
    top_repos = ranked_repos[: int(profile["github"]["ranking"]["max_repos"])]

    issue_rows: list[dict[str, Any]] = []
    people_map: dict[str, dict[str, Any]] = {}
    issues_per_repo = int(profile["github"]["ranking"]["issues_per_repo"])
    for repo_row in top_repos:
        repo_full_name = str(repo_row["full_name"])
        repo_name = str(repo_row["name"])
        if not repo_full_name or not repo_name:
            continue
        if isinstance(issues_fixture, dict):
            issues_raw = issues_fixture.get(repo_full_name, [])
            if not isinstance(issues_raw, list):
                issues_raw = []
        else:
            issues_raw = _github_list_issues(
                owner_login=owner_login,
                repo_name=repo_name,
                states=profile["github"]["filters"]["issue_states"],
                per_repo_limit=issues_per_repo,
                headers=headers,
            )
        for issue in issues_raw:
            if not isinstance(issue, dict):
                continue
            score, reasons = _score_issue(issue, repo_row, profile)
            if score < 0:
                continue
            labels = [str(row.get("name", "")).strip() for row in issue.get("labels", []) if isinstance(row, dict)]
            assignees = [str(row.get("login", "")).strip() for row in issue.get("assignees", []) if isinstance(row, dict)]
            author = str((issue.get("user") or {}).get("login", "")).strip() if isinstance(issue.get("user"), dict) else ""
            people = _unique_strings([author, *assignees])
            issue_row = {
                "repo": repo_full_name,
                "number": int(issue.get("number") or 0),
                "title": str(issue.get("title", "") or "").strip(),
                "url": str(issue.get("html_url", "")).strip(),
                "state": str(issue.get("state", "") or "").strip(),
                "labels": labels,
                "assignees": assignees,
                "author": author,
                "people": people,
                "updated_at": str(issue.get("updated_at", "") or "").strip(),
                "score": score,
                "reasons": reasons,
            }
            issue_rows.append(issue_row)
            for login in people:
                if not login:
                    continue
                person = people_map.setdefault(
                    login,
                    {
                        "login": login,
                        "score": 0,
                        "matched_issue_count": 0,
                        "repos": set(),
                    },
                )
                person["score"] += score
                person["matched_issue_count"] += 1
                person["repos"].add(repo_full_name)

    issue_rows = sorted(
        issue_rows,
        key=lambda row: (
            -int(row["score"]),
            _recency_sort_key(str(row["updated_at"])),
            str(row["repo"]),
            int(row["number"]),
        ),
        reverse=False,
    )
    top_issues = issue_rows[: int(profile["github"]["ranking"]["max_issues"])]

    people_rows: list[dict[str, Any]] = []
    for person in people_map.values():
        people_rows.append(
            {
                "login": str(person["login"]),
                "score": int(person["score"]),
                "matched_issue_count": int(person["matched_issue_count"]),
                "repos": sorted(str(repo) for repo in person["repos"]),
            }
        )
    people_rows = sorted(
        people_rows,
        key=lambda row: (-int(row["score"]), -int(row["matched_issue_count"]), str(row["login"])),
        reverse=False,
    )[: int(profile["github"]["ranking"]["max_people"])]

    out_root = repo_root / DEFAULT_DISCOVER_SCAN_ROOT / scan_id
    scan_json = out_root / "SCAN.json"
    summary_md = out_root / "SCAN_SUMMARY.md"
    payload = {
        "scan_id": scan_id,
        "generated_at_utc": _now_utc(),
        "profile": {
            "path": _path_for_state(profile_path, repo_root),
            "profile_id": profile["profile_id"],
        },
        "owner": {
            "login": owner_login,
            "type": owner_type,
        },
        "auth": {
            "source": token_context["source"],
            "authenticated": bool(token_context["token"]),
        },
        "counts": {
            "repos_fetched": len(repos_raw),
            "repos_considered": len(top_repos),
            "issues_considered": len(top_issues),
            "people_considered": len(people_rows),
        },
        "repos": top_repos,
        "issues": top_issues,
        "people": people_rows,
        "notes": [
            "Discovery scan output is process-only recommendation data.",
            "Use the top repo/issue matches to choose where collaboration should start.",
            "ORP owns the portable discovery profile and artifact format.",
        ],
        "artifacts": {
            "scan_json": _path_for_state(scan_json, repo_root),
            "summary_md": _path_for_state(summary_md, repo_root),
        },
    }
    _write_json(scan_json, payload)
    _write_text(summary_md, _render_discover_scan_summary(payload))

    state_path = repo_root / "orp" / "state.json"
    state = _read_json(state_path) if state_path.exists() else {}
    if not isinstance(state, dict):
        state = {}
    state.setdefault("runs", {})
    state.setdefault("discovery_scans", {})
    state["last_discover_scan_id"] = scan_id
    state["discovery_scans"][scan_id] = {
        "scan_json": payload["artifacts"]["scan_json"],
        "summary_md": payload["artifacts"]["summary_md"],
        "profile_path": payload["profile"]["path"],
        "owner": owner_login,
    }
    _write_json(state_path, state)
    return payload


def cmd_init(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    repo_root.mkdir(parents=True, exist_ok=True)
    repo_name = repo_root.name or "my-project"

    default_branch = str(getattr(args, "default_branch", "main") or "main").strip() or "main"
    allow_protected_branch_work = bool(getattr(args, "allow_protected_branch_work", False))
    git_was_present = _git_repo_present(repo_root)
    git_init_result = {"initialized": False, "method": ""}
    if not git_was_present:
        git_init_result = _git_init_repo(repo_root, default_branch)

    _ensure_dirs(repo_root)
    config_path = repo_root / args.config
    config_action = "kept"
    if not config_path.exists():
        config_path.write_text(_init_config_starter(repo_name), encoding="utf-8")
        config_action = "created"
    kernel_starter_path = repo_root / "analysis" / "orp.kernel.task.yml"

    initialized_at_utc = _now_utc()
    git_snapshot = _git_governance_snapshot(
        repo_root,
        default_branch=default_branch,
        allow_protected_branch_work=allow_protected_branch_work,
    )
    remote_context = _effective_remote_context(
        detected_remote_url=str(git_snapshot["detected_remote_url"]),
        detected_github_repo=str(git_snapshot["detected_github_repo"]),
        remote_url_arg=str(getattr(args, "remote_url", "")),
        github_repo_arg=str(getattr(args, "github_repo", "")),
    )

    warnings: list[str] = []
    notes: list[str] = []
    next_actions: list[str] = []

    if git_snapshot["protected_branch"] and not allow_protected_branch_work:
        warnings.append(
            f"current branch `{git_snapshot['branch']}` is protected; create or switch to a work branch before meaningful edits."
        )
        next_actions.append("git checkout -b orp/bootstrap")
    elif not git_snapshot["branch"]:
        warnings.append("git HEAD is detached or has no symbolic branch; switch to a named work branch before agent work.")

    if git_snapshot["dirty"]:
        warnings.append("working tree is dirty; create an explicit checkpoint commit before agent work.")
        next_actions.append(
            'git add orp.yml orp analysis/orp.kernel.task.yml && git commit -m "checkpoint: bootstrap ORP governance"'
        )

    if not git_snapshot["has_commits"]:
        notes.append("repo has no commits yet; treat the first commit as the initial ORP checkpoint.")

    if remote_context["mode"] == "local_only":
        notes.append("no git remote detected; ORP is operating in local-first mode.")
        if not getattr(args, "github_repo", "") and not getattr(args, "remote_url", ""):
            next_actions.append("optional: rerun with --github-repo owner/repo or --remote-url <url> when a remote exists")
    elif remote_context["mode"] == "github":
        notes.append(
            f"GitHub remote context recorded for `{remote_context['effective_github_repo']}`."
        )
    else:
        notes.append("non-GitHub remote context recorded for this repo.")

    files: dict[str, dict[str, str]] = {
        "config": {
            "path": str(config_path),
            "action": config_action,
        }
    }
    handoff_path = repo_root / "orp" / "HANDOFF.md"
    checkpoint_log_path = repo_root / "orp" / "checkpoints" / "CHECKPOINT_LOG.md"
    governance_path = repo_root / "orp" / "governance.json"
    agent_policy_path = repo_root / "orp" / "agent-policy.json"

    files["handoff"] = {
        "path": _path_for_state(handoff_path, repo_root),
        "action": _write_text_if_missing(
            handoff_path,
            _init_handoff_template(
                repo_root,
                default_branch=default_branch,
                initialized_at_utc=initialized_at_utc,
            ),
        ),
    }
    files["checkpoint_log"] = {
        "path": _path_for_state(checkpoint_log_path, repo_root),
        "action": _write_text_if_missing(checkpoint_log_path, _init_checkpoint_log_template()),
    }
    files["starter_kernel"] = {
        "path": _path_for_state(kernel_starter_path, repo_root),
        "action": _write_text_if_missing(kernel_starter_path, _init_kernel_task_template(repo_name)),
    }

    agent_policy_exists = agent_policy_path.exists()
    agent_policy = _agent_policy_payload(
        default_branch=default_branch,
        allow_protected_branch_work=allow_protected_branch_work,
        remote_context=remote_context,
    )
    _write_json(agent_policy_path, agent_policy)
    files["agent_policy"] = {
        "path": _path_for_state(agent_policy_path, repo_root),
        "action": "updated" if agent_policy_exists else "created",
    }

    governance_exists = governance_path.exists()
    governance_payload = _governance_runtime_payload(
        repo_root=repo_root,
        config_path=config_path,
        initialized_at_utc=initialized_at_utc,
        git_snapshot=git_snapshot,
        remote_context=remote_context,
        warnings=warnings,
        next_actions=next_actions,
        initialized_git=bool(git_init_result["initialized"]),
    )
    _write_json(governance_path, governance_payload)
    files["governance_manifest"] = {
        "path": _path_for_state(governance_path, repo_root),
        "action": "updated" if governance_exists else "created",
    }

    state_path = repo_root / "orp" / "state.json"
    state = _read_json(state_path) if state_path.exists() else _default_state_payload()
    if not isinstance(state, dict):
        state = _default_state_payload()
    state.setdefault("governance", {})
    governance_state = state["governance"]
    if not isinstance(governance_state, dict):
        governance_state = {}
        state["governance"] = governance_state
    governance_state.update(
        {
            "orp_governed": True,
            "mode": "repo_governance",
            "initialized_at_utc": initialized_at_utc,
            "config_path": _path_for_state(config_path, repo_root),
            "manifest_path": _path_for_state(governance_path, repo_root),
            "agent_policy_path": _path_for_state(agent_policy_path, repo_root),
            "handoff_path": _path_for_state(handoff_path, repo_root),
            "checkpoint_log_path": _path_for_state(checkpoint_log_path, repo_root),
            "default_branch": default_branch,
            "protected_branches": [default_branch],
            "allow_protected_branch_work": allow_protected_branch_work,
            "git_initialized_by_orp": bool(git_init_result["initialized"]),
            "git_init_method": str(git_init_result["method"]),
            "remote_mode": remote_context["mode"],
            "effective_remote_url": remote_context["effective_remote_url"],
            "effective_github_repo": remote_context["effective_github_repo"],
            "remote_source": remote_context["source"],
        }
    )
    _write_json(state_path, state)

    git_runtime = _read_git_runtime(repo_root)
    git_runtime["initialized_at_utc"] = git_runtime.get("initialized_at_utc") or initialized_at_utc
    git_runtime["last_init"] = {
        "timestamp_utc": initialized_at_utc,
        "default_branch": default_branch,
        "allow_protected_branch_work": allow_protected_branch_work,
        "git_initialized_by_orp": bool(git_init_result["initialized"]),
        "git_init_method": str(git_init_result["method"]),
        "remote_mode": remote_context["mode"],
        "effective_remote_url": remote_context["effective_remote_url"],
        "effective_github_repo": remote_context["effective_github_repo"],
    }
    _write_git_runtime(repo_root, git_runtime)

    result = {
        "ok": True,
        "config_action": config_action,
        "config_path": str(config_path),
        "runtime_root": str(repo_root / "orp"),
        "files": files,
        "git": {
            **git_snapshot,
            "initialized_by_orp": bool(git_init_result["initialized"]),
            "git_init_method": str(git_init_result["method"]),
            "effective_remote_mode": remote_context["mode"],
            "effective_remote_url": remote_context["effective_remote_url"],
            "effective_github_repo": remote_context["effective_github_repo"],
        },
        "warnings": warnings,
        "notes": notes,
        "next_actions": next_actions,
    }
    if args.json_output:
        _print_json(result)
    else:
        if config_action == "created":
            print(f"created {config_path}")
        else:
            print(f"kept existing {config_path}")
        print(f"initialized ORP governance runtime under {repo_root / 'orp'}")
        if git_init_result["initialized"]:
            print(f"initialized git repository with default branch {default_branch}")
        print(
            "git_state="
            + ",".join(
                [
                    f"branch={git_snapshot['branch'] or '(none)'}",
                    f"dirty={'true' if git_snapshot['dirty'] else 'false'}",
                    f"protected={'true' if git_snapshot['protected_branch'] else 'false'}",
                    f"remote_mode={remote_context['mode']}",
                ]
            )
        )
        for note in notes:
            print(f"note={note}")
        for warning in warnings:
            print(f"warning={warning}")
        for action in next_actions:
            print(f"next={action}")
    return 0


def _render_governance_status_text(payload: dict[str, Any]) -> str:
    git = payload.get("git", {}) if isinstance(payload.get("git"), dict) else {}
    runtime = payload.get("runtime", {}) if isinstance(payload.get("runtime"), dict) else {}
    validation = payload.get("validation", {}) if isinstance(payload.get("validation"), dict) else {}
    readiness = payload.get("readiness", {}) if isinstance(payload.get("readiness"), dict) else {}
    last_branch_action = (
        runtime.get("last_branch_action")
        if isinstance(runtime.get("last_branch_action"), dict)
        else {}
    )
    last_checkpoint = (
        runtime.get("last_checkpoint")
        if isinstance(runtime.get("last_checkpoint"), dict)
        else {}
    )
    last_backup = (
        runtime.get("last_backup")
        if isinstance(runtime.get("last_backup"), dict)
        else {}
    )

    lines = [
        "ORP Governance Status",
        f"repo_root={payload.get('repo_root', '')}",
        f"orp_governed={'true' if payload.get('orp_governed') else 'false'}",
        f"mode={payload.get('mode', '')}",
        f"ready_for_agent_work={'true' if payload.get('ready_for_agent_work') else 'false'}",
        f"git.present={'true' if git.get('present') else 'false'}",
        f"git.branch={git.get('branch', '') or '(none)'}",
        f"git.commit={git.get('commit', '') or '(none)'}",
        f"git.dirty={'true' if git.get('dirty') else 'false'}",
        f"git.protected_branch={'true' if git.get('protected_branch') else 'false'}",
        f"git.work_branch_required={'true' if git.get('work_branch_required') else 'false'}",
        f"remote.mode={git.get('effective_remote_mode', '')}",
        f"remote.url={git.get('effective_remote_url', '') or '(none)'}",
        f"remote.github_repo={git.get('effective_github_repo', '') or '(none)'}",
        f"remote.upstream={git.get('upstream_branch', '') or '(none)'}",
        f"remote.default_branch={git.get('remote_default_branch', '') or '(none)'}",
        f"remote.ahead={git.get('ahead_count', '') if git.get('ahead_count') is not None else '(unknown)'}",
        f"remote.behind={git.get('behind_count', '') if git.get('behind_count') is not None else '(unknown)'}",
        f"paths.config={payload.get('config_path', '')}",
        f"paths.handoff={payload.get('handoff_path', '')}",
        f"paths.checkpoint_log={payload.get('checkpoint_log_path', '')}",
        f"paths.git_runtime={payload.get('git_runtime_path', '')}",
        f"readiness.local_ready={'true' if readiness.get('local_ready') else 'false'}",
        f"readiness.remote_ready={'true' if readiness.get('remote_ready') else 'false'}",
    ]
    if last_branch_action:
        lines.append(
            "last_branch_action="
            + ",".join(
                [
                    f"action={last_branch_action.get('action', '')}",
                    f"from={last_branch_action.get('from_branch', '') or '(none)'}",
                    f"to={last_branch_action.get('to_branch', '') or '(none)'}",
                    f"at={last_branch_action.get('timestamp_utc', '')}",
                ]
            )
        )
    if last_checkpoint:
        lines.append(
            "last_checkpoint="
            + ",".join(
                [
                    f"commit={last_checkpoint.get('commit', '') or '(none)'}",
                    f"branch={last_checkpoint.get('branch', '') or '(none)'}",
                    f"note={last_checkpoint.get('note', last_checkpoint.get('commit_message', ''))}",
                    f"at={last_checkpoint.get('timestamp_utc', last_checkpoint.get('committed_at_utc', ''))}",
                ]
            )
        )
    if last_backup:
        lines.append(
            "last_backup="
            + ",".join(
                [
                    f"commit={last_backup.get('commit', '') or '(none)'}",
                    f"branch={last_backup.get('branch', '') or '(none)'}",
                    f"remote={last_backup.get('remote_name', '') or '(none)'}",
                    f"ref={last_backup.get('backup_ref', '') or '(none)'}",
                    f"scope={last_backup.get('backup_scope', '') or '(none)'}",
                    f"at={last_backup.get('timestamp_utc', '')}",
                ]
            )
        )
    latest_run = validation.get("run") if isinstance(validation.get("run"), dict) else {}
    if latest_run:
        lines.append(
            "latest_run="
            + ",".join(
                [
                    f"run_id={latest_run.get('run_id', '')}",
                    f"profile={latest_run.get('profile', '')}",
                    f"overall={latest_run.get('overall', '')}",
                    f"ended_at={latest_run.get('ended_at_utc', '')}",
                ]
            )
        )
        lines.append(
            f"validation.checkpoint_after_validation={'true' if validation.get('checkpoint_after_validation') else 'false'}"
        )
    for note in payload.get("notes", []):
        lines.append(f"note={note}")
    for warning in payload.get("warnings", []):
        lines.append(f"warning={warning}")
    for action in payload.get("next_actions", []):
        lines.append(f"next={action}")
    return "\n".join(lines)


def cmd_status(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload = _governance_status_payload(repo_root, args.config)
    if args.json_output:
        _print_json(payload)
    else:
        print(_render_governance_status_text(payload))
    return 0


def cmd_branch_start(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    status_payload = _governance_status_payload(repo_root, args.config)
    if not status_payload.get("orp_governed"):
        raise RuntimeError("repo is not ORP-governed yet. Run `orp init` first.")

    git = status_payload.get("git", {}) if isinstance(status_payload.get("git"), dict) else {}
    if not git.get("present"):
        raise RuntimeError("git repository not detected. Run `orp init` first.")

    target_branch = str(getattr(args, "name", "")).strip()
    if not target_branch:
        raise RuntimeError("branch name is required.")

    validate_proc = _git_run(repo_root, ["check-ref-format", "--branch", target_branch])
    if validate_proc.returncode != 0:
        raise RuntimeError(f"invalid branch name `{target_branch}`: {_git_error_detail(validate_proc)}")

    protected_branches = [
        str(item).strip()
        for item in git.get("protected_branches", [])
        if isinstance(item, str) and str(item).strip()
    ]
    if target_branch in protected_branches and not bool(git.get("allow_protected_branch_work")):
        raise RuntimeError(
            f"target branch `{target_branch}` is protected. Choose a non-protected work branch name."
        )

    current_branch = str(git.get("branch", "")).strip()
    dirty_before = bool(git.get("dirty"))
    if dirty_before and not bool(getattr(args, "allow_dirty", False)):
        raise RuntimeError(
            "working tree is dirty. Commit or stash changes first, or rerun with `--allow-dirty`."
        )

    if current_branch == target_branch:
        action = "already_current"
        base_ref = current_branch or "HEAD"
    else:
        branch_exists = _git_branch_exists(repo_root, target_branch)
        base_ref = str(getattr(args, "from_ref", "")).strip() or current_branch or "HEAD"
        if branch_exists:
            _git_require_success(
                repo_root,
                ["checkout", target_branch],
                context=f"failed to switch to existing branch `{target_branch}`",
            )
            action = "switched_existing"
        else:
            create_args = ["checkout", "-b", target_branch]
            if git.get("has_commits"):
                create_args.append(base_ref)
            _git_require_success(
                repo_root,
                create_args,
                context=f"failed to create branch `{target_branch}`",
            )
            action = "created"

    now = _now_utc()
    event = {
        "timestamp_utc": now,
        "action": action,
        "from_branch": current_branch,
        "to_branch": target_branch,
        "from_ref": base_ref,
        "dirty_before": dirty_before,
    }
    git_runtime = _read_git_runtime(repo_root)
    git_runtime["last_branch_action"] = event
    _append_bounded_event_list(git_runtime, "branch_transitions", event)
    _write_git_runtime(repo_root, git_runtime)

    refreshed = _governance_status_payload(repo_root, args.config)
    result = {
        "ok": True,
        "action": action,
        "branch": target_branch,
        "previous_branch": current_branch,
        "from_ref": base_ref,
        "dirty_before": dirty_before,
        "git_runtime_path": refreshed.get("git_runtime_path", ""),
        "ready_for_agent_work": refreshed.get("ready_for_agent_work", False),
        "warnings": refreshed.get("warnings", []),
        "next_actions": refreshed.get("next_actions", []),
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"action={action}")
        print(f"branch={target_branch}")
        print(f"previous_branch={current_branch or '(none)'}")
        print(f"from_ref={base_ref}")
        print(f"git_runtime={refreshed.get('git_runtime_path', '')}")
        for warning in result["warnings"]:
            print(f"warning={warning}")
        for action_line in result["next_actions"]:
            print(f"next={action_line}")
    return 0


def cmd_checkpoint_create(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    status_payload = _governance_status_payload(repo_root, args.config)
    if not status_payload.get("orp_governed"):
        raise RuntimeError("repo is not ORP-governed yet. Run `orp init` first.")

    git = status_payload.get("git", {}) if isinstance(status_payload.get("git"), dict) else {}
    if not git.get("present"):
        raise RuntimeError("git repository not detected. Run `orp init` first.")

    branch = str(git.get("branch", "")).strip()
    if not branch:
        raise RuntimeError("git HEAD is detached. Switch to a named work branch before checkpointing.")

    protected_branch = bool(git.get("protected_branch"))
    protected_allowed = bool(git.get("allow_protected_branch_work")) or bool(
        getattr(args, "allow_protected_branch", False)
    )
    if protected_branch and not protected_allowed:
        raise RuntimeError(
            f"current branch `{branch}` is protected. Create a work branch first or rerun with `--allow-protected-branch`."
        )

    note = re.sub(r"\s+", " ", str(getattr(args, "message", "")).strip())
    timestamp_utc = _now_utc()
    event = _create_checkpoint_commit(
        repo_root,
        status_payload,
        branch=branch,
        note=note,
        timestamp_utc=timestamp_utc,
    )
    git_runtime = _read_git_runtime(repo_root)
    git_runtime["last_checkpoint"] = event
    _append_bounded_event_list(git_runtime, "checkpoint_history", event)
    _write_git_runtime(repo_root, git_runtime)

    refreshed = _governance_status_payload(repo_root, args.config)
    result = {
        "ok": True,
        "branch": branch,
        "commit": event["commit"],
        "commit_full": event["commit_full"],
        "commit_message": event["commit_message"],
        "note": note,
        "checkpoint_log_path": event["checkpoint_log_path"],
        "git_runtime_path": refreshed.get("git_runtime_path", ""),
        "ready_for_agent_work": refreshed.get("ready_for_agent_work", False),
        "warnings": refreshed.get("warnings", []),
        "next_actions": refreshed.get("next_actions", []),
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"commit={commit_short}")
        print(f"branch={branch}")
        print(f"message={commit_message}")
        print(f"checkpoint_log={result['checkpoint_log_path']}")
        print(f"git_runtime={result['git_runtime_path']}")
        for warning in result["warnings"]:
            print(f"warning={warning}")
        for action_line in result["next_actions"]:
            print(f"next={action_line}")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    status_payload = _governance_status_payload(repo_root, args.config)
    if not status_payload.get("orp_governed"):
        raise RuntimeError("repo is not ORP-governed yet. Run `orp init` first.")

    git = status_payload.get("git", {}) if isinstance(status_payload.get("git"), dict) else {}
    if not git.get("present"):
        raise RuntimeError("git repository not detected. Run `orp init` first.")

    timestamp_utc = _now_utc()
    branch_before = str(git.get("branch", "")).strip()
    active_branch = branch_before
    dirty_before = bool(git.get("dirty"))
    auto_branch_event: dict[str, Any] = {}

    if dirty_before and (not active_branch or (bool(git.get("protected_branch")) and not bool(getattr(args, "allow_protected_branch", False)))):
        backup_branch = _generate_backup_work_branch(repo_root, active_branch, timestamp_utc=timestamp_utc)
        _git_require_success(
            repo_root,
            ["checkout", "-b", backup_branch],
            context=f"failed to create backup work branch `{backup_branch}`",
        )
        active_branch = backup_branch
        auto_branch_event = {
            "timestamp_utc": timestamp_utc,
            "action": "created_for_backup",
            "from_branch": branch_before,
            "to_branch": active_branch,
            "from_ref": branch_before or "HEAD",
            "dirty_before": dirty_before,
        }

    checkpoint_event: dict[str, Any] = {}
    if dirty_before:
        if not active_branch:
            raise RuntimeError("unable to determine a branch for backup checkpointing.")
        checkpoint_event = _create_checkpoint_commit(
            repo_root,
            status_payload,
            branch=active_branch,
            note=_backup_note(getattr(args, "message", "")),
            timestamp_utc=timestamp_utc,
        )

    commit_full = (
        str(checkpoint_event.get("commit_full", "")).strip()
        if checkpoint_event
        else _git_stdout(repo_root, ["rev-parse", "HEAD"])
    )
    commit_short = (
        str(checkpoint_event.get("commit", "")).strip()
        if checkpoint_event
        else _git_stdout(repo_root, ["rev-parse", "--short", "HEAD"])
    )
    if not commit_full:
        raise RuntimeError("no commit is available to back up yet. Create a checkpoint commit first.")

    remote_name = str(getattr(args, "remote", "")).strip()
    if not remote_name:
        remote_name = str(git.get("upstream_remote", "")).strip()
    if not remote_name and str(git.get("effective_remote_url", "")).strip():
        remote_name = "origin"

    remote_url = _git_stdout(repo_root, ["remote", "get-url", remote_name]) if remote_name else ""
    backup_ref = _backup_remote_ref_name(
        active_branch or branch_before or "detached",
        timestamp_utc=timestamp_utc,
        prefix=str(getattr(args, "prefix", "orp/backup")),
    )
    push_target = f"refs/heads/{backup_ref}"
    pushed_remote = False
    backup_scope = "local_only"
    if remote_name:
        _git_require_success(
            repo_root,
            ["push", remote_name, f"HEAD:{push_target}"],
            context=f"failed to push backup ref `{backup_ref}` to remote `{remote_name}`",
        )
        pushed_remote = True
        backup_scope = "remote"

    backup_event = {
        "timestamp_utc": timestamp_utc,
        "branch_before": branch_before,
        "branch": active_branch or branch_before,
        "dirty_before": dirty_before,
        "checkpoint_created": bool(checkpoint_event),
        "note": checkpoint_event.get("note", ""),
        "commit": commit_short,
        "commit_full": commit_full,
        "remote_name": remote_name,
        "remote_url": remote_url,
        "backup_ref": backup_ref,
        "push_target": push_target if pushed_remote else "",
        "pushed_remote": pushed_remote,
        "backup_scope": backup_scope,
        "auto_branch_created": bool(auto_branch_event),
        "auto_branch_name": active_branch if auto_branch_event else "",
    }

    git_runtime = _read_git_runtime(repo_root)
    if auto_branch_event:
        git_runtime["last_branch_action"] = auto_branch_event
        _append_bounded_event_list(git_runtime, "branch_transitions", auto_branch_event)
    if checkpoint_event:
        git_runtime["last_checkpoint"] = checkpoint_event
        _append_bounded_event_list(git_runtime, "checkpoint_history", checkpoint_event)
    git_runtime["last_backup"] = backup_event
    _append_bounded_event_list(git_runtime, "backup_history", backup_event)
    _write_git_runtime(repo_root, git_runtime)

    refreshed = _governance_status_payload(repo_root, args.config)
    next_actions = list(refreshed.get("next_actions", []))
    notes = []
    if not pushed_remote:
        notes.append("no remote was configured; backup was recorded locally only.")
        next_actions.append("git remote add origin <url>")
    result = {
        "ok": True,
        "backup_scope": backup_scope,
        "branch_before": branch_before,
        "branch": active_branch or branch_before,
        "dirty_before": dirty_before,
        "checkpoint_created": bool(checkpoint_event),
        "checkpoint_note": checkpoint_event.get("note", ""),
        "commit": commit_short,
        "commit_full": commit_full,
        "remote_name": remote_name,
        "remote_url": remote_url,
        "backup_ref": backup_ref,
        "push_target": push_target if pushed_remote else "",
        "pushed_remote": pushed_remote,
        "auto_branch_created": bool(auto_branch_event),
        "auto_branch_name": active_branch if auto_branch_event else "",
        "git_runtime_path": refreshed.get("git_runtime_path", ""),
        "ready_for_agent_work": refreshed.get("ready_for_agent_work", False),
        "warnings": refreshed.get("warnings", []),
        "notes": _unique_strings(list(refreshed.get("notes", [])) + notes),
        "next_actions": _unique_strings(next_actions),
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"backup_scope={backup_scope}")
        print(f"branch={result['branch'] or '(detached)'}")
        print(f"commit={commit_short}")
        print(f"remote={remote_name or '(none)'}")
        print(f"backup_ref={backup_ref}")
        print(f"pushed_remote={'true' if pushed_remote else 'false'}")
        if result["auto_branch_created"]:
            print(f"auto_branch={result['auto_branch_name']}")
        if result["checkpoint_created"]:
            print(f"checkpoint_note={result['checkpoint_note']}")
        print(f"git_runtime={result['git_runtime_path']}")
        for note in result["notes"]:
            print(f"note={note}")
        for warning in result["warnings"]:
            print(f"warning={warning}")
        for action_line in result["next_actions"]:
            print(f"next={action_line}")
    return 0


def _doctor_issue(
    *,
    severity: str,
    code: str,
    message: str,
    fixable: bool = False,
    path: str = "",
) -> dict[str, Any]:
    issue = {
        "severity": severity,
        "code": code,
        "message": message,
        "fixable": fixable,
    }
    if path:
        issue["path"] = path
    return issue


def _cleanup_candidates(repo_root: Path, status_payload: dict[str, Any]) -> list[dict[str, Any]]:
    git = status_payload.get("git", {}) if isinstance(status_payload.get("git"), dict) else {}
    default_branch = str(git.get("default_branch", "main")).strip() or "main"
    current_branch = str(git.get("branch", "")).strip()
    protected_branches = {
        str(item).strip()
        for item in git.get("protected_branches", [])
        if isinstance(item, str) and str(item).strip()
    }

    merged: set[str] = set()
    merged_proc = _git_run(repo_root, ["branch", "--format=%(refname:short)", "--merged", default_branch])
    if merged_proc.returncode == 0:
        merged = {line.strip() for line in merged_proc.stdout.splitlines() if line.strip()}

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in _git_branch_inventory(repo_root):
        branch_name = str(row.get("name", "")).strip()
        if not branch_name or branch_name == current_branch or branch_name in protected_branches:
            continue
        reasons: list[str] = []
        safe_delete = False
        if branch_name in merged:
            reasons.append("merged_into_default_branch")
            safe_delete = True
        track = str(row.get("track", "")).strip()
        if "[gone]" in track:
            reasons.append("upstream_gone")
        if not reasons or branch_name in seen:
            continue
        seen.add(branch_name)
        candidates.append(
            {
                "branch": branch_name,
                "commit": str(row.get("commit", "")).strip(),
                "upstream": str(row.get("upstream", "")).strip(),
                "committed_at_utc": str(row.get("committed_at_utc", "")).strip(),
                "subject": str(row.get("subject", "")).strip(),
                "reasons": reasons,
                "safe_delete": safe_delete,
                "delete_command": f"git branch -d {branch_name}" if safe_delete else "",
            }
        )
    return sorted(candidates, key=lambda row: (0 if row["safe_delete"] else 1, row["branch"]))


def _apply_doctor_fixes(repo_root: Path, config_arg: str, status_payload: dict[str, Any]) -> list[str]:
    state_path = repo_root / "orp" / "state.json"
    state = _read_json_if_exists(state_path)
    governance_state = state.get("governance") if isinstance(state.get("governance"), dict) else {}
    repo_name = repo_root.name or "my-project"

    default_branch = str(governance_state.get("default_branch", "main")).strip() or "main"
    allow_protected_branch_work = bool(governance_state.get("allow_protected_branch_work", False))
    initialized_at_utc = str(governance_state.get("initialized_at_utc", "")).strip() or _now_utc()
    config_path = repo_root / str(governance_state.get("config_path", config_arg) or config_arg)
    if not config_path.is_absolute():
        config_path = (repo_root / config_path).resolve()
    else:
        config_path = config_path.resolve()

    if not config_path.exists():
        config_path.write_text(_init_config_starter(repo_name), encoding="utf-8")

    git_snapshot = _git_governance_snapshot(
        repo_root,
        default_branch=default_branch,
        allow_protected_branch_work=allow_protected_branch_work,
    )
    remote_context = _effective_remote_context(
        detected_remote_url=str(git_snapshot.get("detected_remote_url", "")),
        detected_github_repo=str(git_snapshot.get("detected_github_repo", "")),
        remote_url_arg=str(governance_state.get("effective_remote_url", "")),
        github_repo_arg=str(governance_state.get("effective_github_repo", "")),
    )

    handoff_path = repo_root / "orp" / "HANDOFF.md"
    checkpoint_log_path = repo_root / "orp" / "checkpoints" / "CHECKPOINT_LOG.md"
    kernel_starter_path = repo_root / "analysis" / "orp.kernel.task.yml"
    governance_path = repo_root / "orp" / "governance.json"
    agent_policy_path = repo_root / "orp" / "agent-policy.json"

    fixes_applied: list[str] = []
    if _write_text_if_missing(
        handoff_path,
        _init_handoff_template(
            repo_root,
            default_branch=default_branch,
            initialized_at_utc=initialized_at_utc,
        ),
    ) == "created":
        fixes_applied.append("created_handoff")
    if _write_text_if_missing(checkpoint_log_path, _init_checkpoint_log_template()) == "created":
        fixes_applied.append("created_checkpoint_log")
    if _write_text_if_missing(kernel_starter_path, _init_kernel_task_template(repo_name)) == "created":
        fixes_applied.append("created_starter_kernel")

    _write_json(
        agent_policy_path,
        _agent_policy_payload(
            default_branch=default_branch,
            allow_protected_branch_work=allow_protected_branch_work,
            remote_context=remote_context,
        ),
    )
    fixes_applied.append("synced_agent_policy")

    refreshed_status = _governance_status_payload(repo_root, config_arg)
    _write_json(
        governance_path,
        _governance_runtime_payload(
            repo_root=repo_root,
            config_path=config_path,
            initialized_at_utc=initialized_at_utc,
            git_snapshot=git_snapshot,
            remote_context=remote_context,
            warnings=list(refreshed_status.get("warnings", [])),
            next_actions=list(refreshed_status.get("next_actions", [])),
            initialized_git=bool(governance_state.get("git_initialized_by_orp", False)),
        ),
    )
    fixes_applied.append("synced_governance_manifest")

    state.setdefault("governance", {})
    if not isinstance(state["governance"], dict):
        state["governance"] = {}
    state["governance"].update(
        {
            "orp_governed": True,
            "mode": "repo_governance",
            "initialized_at_utc": initialized_at_utc,
            "config_path": _path_for_state(config_path, repo_root),
            "manifest_path": _path_for_state(governance_path, repo_root),
            "agent_policy_path": _path_for_state(agent_policy_path, repo_root),
            "handoff_path": _path_for_state(handoff_path, repo_root),
            "checkpoint_log_path": _path_for_state(checkpoint_log_path, repo_root),
            "default_branch": default_branch,
            "protected_branches": [default_branch],
            "allow_protected_branch_work": allow_protected_branch_work,
            "git_initialized_by_orp": bool(governance_state.get("git_initialized_by_orp", False)),
            "git_init_method": str(governance_state.get("git_init_method", "")).strip(),
            "remote_mode": remote_context["mode"],
            "effective_remote_url": remote_context["effective_remote_url"],
            "effective_github_repo": remote_context["effective_github_repo"],
            "remote_source": remote_context["source"],
        }
    )
    _write_json(state_path, state)
    fixes_applied.append("synced_state_governance")

    git_runtime = _read_git_runtime(repo_root)
    if not str(git_runtime.get("initialized_at_utc", "")).strip():
        git_runtime["initialized_at_utc"] = initialized_at_utc
        fixes_applied.append("initialized_git_runtime")
    _write_git_runtime(repo_root, git_runtime)
    return fixes_applied


def cmd_ready(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    status_payload = _governance_status_payload(repo_root, args.config)
    if not status_payload.get("orp_governed"):
        raise RuntimeError("repo is not ORP-governed yet. Run `orp init` first.")

    git = status_payload.get("git", {}) if isinstance(status_payload.get("git"), dict) else {}
    readiness = status_payload.get("readiness", {}) if isinstance(status_payload.get("readiness"), dict) else {}
    validation = status_payload.get("validation", {}) if isinstance(status_payload.get("validation"), dict) else {}
    run = validation.get("run") if isinstance(validation.get("run"), dict) else {}
    if getattr(args, "run_id", "") or getattr(args, "run_json", ""):
        run = _latest_run_payload(
            repo_root,
            run_id_arg=str(getattr(args, "run_id", "")),
            run_json_arg=str(getattr(args, "run_json", "")),
        )
        checkpoint = (
            (status_payload.get("runtime", {}) if isinstance(status_payload.get("runtime"), dict) else {})
            .get("last_checkpoint", {})
        )
        checkpoint_at = _parse_iso8601_utc(checkpoint.get("timestamp_utc") or checkpoint.get("committed_at_utc"))
        validation_at = _parse_iso8601_utc(run.get("ended_at_utc"))
        validation = {
            "available": bool(run),
            "run": run,
            "checkpoint_after_validation": bool(checkpoint_at and validation_at and checkpoint_at >= validation_at),
        }
        readiness = {
            **readiness,
            "local_ready": bool(status_payload.get("ready_for_agent_work")) and bool(run) and run.get("overall") == "PASS" and bool(validation["checkpoint_after_validation"]),
            "remote_ready": bool(readiness.get("remote_ready")) and bool(run) and run.get("overall") == "PASS" and bool(validation["checkpoint_after_validation"]),
        }

    if not git.get("present"):
        raise RuntimeError("git repository not detected. Run `orp init` first.")
    if not status_payload.get("handoff_exists"):
        raise RuntimeError("handoff file is missing. Run `orp doctor --fix` first.")
    if not status_payload.get("checkpoint_log_exists"):
        raise RuntimeError("checkpoint log is missing. Run `orp doctor --fix` first.")
    if not status_payload.get("agent_policy_exists"):
        raise RuntimeError("agent policy is missing. Run `orp doctor --fix` first.")
    if git.get("dirty"):
        raise RuntimeError("working tree is dirty. Create a checkpoint commit before marking ready.")
    if git.get("protected_branch") and not git.get("allow_protected_branch_work"):
        raise RuntimeError(
            f"current branch `{git.get('branch', '')}` is protected. Use a work branch before marking ready."
        )
    if not validation.get("available"):
        raise RuntimeError("no validation run found. Run `orp gate run --profile <profile>` first.")
    if run.get("overall") != "PASS":
        raise RuntimeError(f"latest validation run `{run.get('run_id', '')}` did not pass.")
    if not validation.get("checkpoint_after_validation"):
        raise RuntimeError(
            "latest passing validation run is newer than the latest checkpoint commit. Create a new checkpoint first."
        )
    if not readiness.get("local_ready"):
        raise RuntimeError("repo is not locally ready yet. Run `orp status` to inspect blockers.")
    if bool(getattr(args, "require_remote_ready", False)) and not readiness.get("remote_ready"):
        raise RuntimeError("repo is locally ready but not remote-ready yet. Resolve remote tracking blockers first.")

    timestamp_utc = _now_utc()
    event = {
        "timestamp_utc": timestamp_utc,
        "branch": str(git.get("branch", "")).strip(),
        "commit": str(git.get("commit", "")).strip(),
        "run_id": str(run.get("run_id", "")).strip(),
        "run_json": str(run.get("run_json", "")).strip(),
        "profile": str(run.get("profile", "")).strip(),
        "validation_overall": str(run.get("overall", "")).strip(),
        "checkpoint_commit": str(
            (status_payload.get("runtime", {}) if isinstance(status_payload.get("runtime"), dict) else {})
            .get("last_checkpoint", {})
            .get("commit", "")
        ).strip(),
        "local_ready": True,
        "remote_ready": bool(readiness.get("remote_ready")),
        "scope": (
            "local_only"
            if str(git.get("effective_remote_mode", "")).strip() == "local_only"
            else ("remote" if bool(readiness.get("remote_ready")) else "local")
        ),
    }
    git_runtime = _read_git_runtime(repo_root)
    git_runtime["last_ready"] = event
    _append_bounded_event_list(git_runtime, "ready_history", event)
    _write_git_runtime(repo_root, git_runtime)

    refreshed = _governance_status_payload(repo_root, args.config)
    result = {
        "ok": True,
        "branch": event["branch"],
        "commit": event["commit"],
        "run_id": event["run_id"],
        "profile": event["profile"],
        "local_ready": True,
        "remote_ready": bool(refreshed.get("readiness", {}).get("remote_ready")),
        "scope": event["scope"],
        "git_runtime_path": refreshed.get("git_runtime_path", ""),
        "warnings": refreshed.get("warnings", []),
        "next_actions": refreshed.get("next_actions", []),
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"branch={result['branch']}")
        print(f"commit={result['commit']}")
        print(f"run_id={result['run_id']}")
        print(f"profile={result['profile']}")
        print(f"local_ready={'true' if result['local_ready'] else 'false'}")
        print(f"remote_ready={'true' if result['remote_ready'] else 'false'}")
        print(f"scope={result['scope']}")
        for warning in result["warnings"]:
            print(f"warning={warning}")
        for action_line in result["next_actions"]:
            print(f"next={action_line}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    status_payload = _governance_status_payload(repo_root, args.config)
    issues: list[dict[str, Any]] = []

    if not status_payload.get("orp_governed"):
        issues.append(
            _doctor_issue(
                severity="error",
                code="not_orp_governed",
                message="repo is not ORP-governed yet.",
                fixable=False,
            )
        )
    else:
        if not status_payload.get("config_exists"):
            issues.append(
                _doctor_issue(
                    severity="error",
                    code="missing_config",
                    message="ORP config file is missing.",
                    fixable=True,
                    path=str(status_payload.get("config_path", "")),
                )
            )
        if not status_payload.get("manifest_exists"):
            issues.append(
                _doctor_issue(
                    severity="error",
                    code="missing_governance_manifest",
                    message="ORP governance manifest is missing.",
                    fixable=True,
                    path=str(status_payload.get("manifest_path", "")),
                )
            )
        if not status_payload.get("agent_policy_exists"):
            issues.append(
                _doctor_issue(
                    severity="error",
                    code="missing_agent_policy",
                    message="ORP agent policy file is missing.",
                    fixable=True,
                    path=str(status_payload.get("agent_policy_path", "")),
                )
            )
        if not status_payload.get("handoff_exists"):
            issues.append(
                _doctor_issue(
                    severity="error",
                    code="missing_handoff",
                    message="ORP handoff file is missing.",
                    fixable=True,
                    path=str(status_payload.get("handoff_path", "")),
                )
            )
        if not status_payload.get("checkpoint_log_exists"):
            issues.append(
                _doctor_issue(
                    severity="error",
                    code="missing_checkpoint_log",
                    message="ORP checkpoint log is missing.",
                    fixable=True,
                    path=str(status_payload.get("checkpoint_log_path", "")),
                )
            )

    git = status_payload.get("git", {}) if isinstance(status_payload.get("git"), dict) else {}
    if status_payload.get("orp_governed") and not git.get("present"):
        issues.append(
            _doctor_issue(
                severity="error",
                code="missing_git_repo",
                message="git repository is not available at repo root.",
                fixable=False,
            )
        )
    git_runtime_path = _git_runtime_path(repo_root)
    if status_payload.get("orp_governed") and git_runtime_path is not None and not git_runtime_path.exists():
        issues.append(
            _doctor_issue(
                severity="warning",
                code="missing_git_runtime",
                message="git-local ORP runtime file is missing.",
                fixable=True,
                path=_path_for_state(git_runtime_path, repo_root),
            )
        )

    author_proc = _git_run(repo_root, ["var", "GIT_AUTHOR_IDENT"]) if git.get("present") else None
    if git.get("present") and author_proc is not None and author_proc.returncode != 0:
        issues.append(
            _doctor_issue(
                severity="warning",
                code="git_author_identity_missing",
                message="git author identity is not configured.",
                fixable=False,
            )
        )

    if git.get("effective_remote_mode") != "local_only":
        detected_remote_url = str(git.get("detected_remote_url", "")).strip()
        effective_remote_url = str(git.get("effective_remote_url", "")).strip()
        if detected_remote_url and effective_remote_url and detected_remote_url != effective_remote_url:
            issues.append(
                _doctor_issue(
                    severity="warning",
                    code="remote_metadata_mismatch",
                    message="recorded remote URL does not match detected origin URL.",
                    fixable=True,
                )
            )
        if git.get("behind_count") is not None and int(git.get("behind_count") or 0) > 0:
            issues.append(
                _doctor_issue(
                    severity="warning",
                    code="branch_behind_upstream",
                    message=f"current branch is behind upstream by {int(git.get('behind_count') or 0)} commit(s).",
                    fixable=False,
                )
            )

    validation = status_payload.get("validation", {}) if isinstance(status_payload.get("validation"), dict) else {}
    run = validation.get("run") if isinstance(validation.get("run"), dict) else {}
    if not validation.get("available"):
        issues.append(
            _doctor_issue(
                severity="warning",
                code="missing_validation_run",
                message="no validation run is available for readiness.",
                fixable=False,
            )
        )
    elif run.get("overall") != "PASS":
        issues.append(
            _doctor_issue(
                severity="warning",
                code="latest_validation_failed",
                message=f"latest validation run `{run.get('run_id', '')}` did not pass.",
                fixable=False,
            )
        )
    elif not validation.get("checkpoint_after_validation"):
        issues.append(
            _doctor_issue(
                severity="warning",
                code="checkpoint_outdated_after_validation",
                message="latest passing validation run is newer than the latest checkpoint commit.",
                fixable=False,
            )
        )

    fixes_applied: list[str] = []
    if getattr(args, "fix", False) and status_payload.get("orp_governed"):
        fixes_applied = _apply_doctor_fixes(repo_root, args.config, status_payload)
        status_payload = _governance_status_payload(repo_root, args.config)
        issues = [
            issue
            for issue in issues
            if not (issue.get("fixable") and issue.get("severity") in {"error", "warning"})
        ]
        if not status_payload.get("config_exists"):
            issues.append(
                _doctor_issue(severity="error", code="missing_config", message="ORP config file is missing.", fixable=True)
            )

    timestamp_utc = _now_utc()
    git_runtime = _read_git_runtime(repo_root)
    doctor_event = {
        "timestamp_utc": timestamp_utc,
        "errors": sum(1 for issue in issues if issue.get("severity") == "error"),
        "warnings": sum(1 for issue in issues if issue.get("severity") == "warning"),
        "fix": bool(getattr(args, "fix", False)),
        "fixes_applied": fixes_applied,
    }
    git_runtime["last_doctor"] = doctor_event
    _append_bounded_event_list(git_runtime, "doctor_history", doctor_event)
    _write_git_runtime(repo_root, git_runtime)

    errors = doctor_event["errors"]
    warnings_count = doctor_event["warnings"]
    ok = errors == 0 and (warnings_count == 0 or not bool(getattr(args, "strict", False)))
    result = {
        "ok": ok,
        "errors": errors,
        "warnings": warnings_count,
        "fix": bool(getattr(args, "fix", False)),
        "fixes_applied": fixes_applied,
        "issues": issues,
        "ready_for_agent_work": status_payload.get("ready_for_agent_work", False),
        "readiness": status_payload.get("readiness", {}),
        "git_runtime_path": status_payload.get("git_runtime_path", ""),
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"ok={'true' if ok else 'false'}")
        print(f"errors={errors}")
        print(f"warnings={warnings_count}")
        for fix_name in fixes_applied:
            print(f"fix={fix_name}")
        for issue in issues:
            print(
                "issue="
                + ",".join(
                    [
                        f"severity={issue.get('severity', '')}",
                        f"code={issue.get('code', '')}",
                        f"message={issue.get('message', '')}",
                    ]
                )
            )
    return 0 if ok else 1


def cmd_cleanup(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    status_payload = _governance_status_payload(repo_root, args.config)
    git = status_payload.get("git", {}) if isinstance(status_payload.get("git"), dict) else {}
    if not git.get("present"):
        raise RuntimeError("git repository not detected. Run `orp init` first.")

    candidates = _cleanup_candidates(repo_root, status_payload)
    deleted_branches: list[str] = []
    if getattr(args, "apply", False) and getattr(args, "delete_merged", False):
        for row in candidates:
            if not row.get("safe_delete"):
                continue
            branch_name = str(row.get("branch", "")).strip()
            if not branch_name:
                continue
            _git_require_success(
                repo_root,
                ["branch", "-d", branch_name],
                context=f"failed to delete merged branch `{branch_name}`",
            )
            deleted_branches.append(branch_name)
        candidates = _cleanup_candidates(repo_root, status_payload)

    event = {
        "timestamp_utc": _now_utc(),
        "apply": bool(getattr(args, "apply", False)),
        "delete_merged": bool(getattr(args, "delete_merged", False)),
        "deleted_branches": deleted_branches,
        "suggestion_count": len(candidates),
    }
    git_runtime = _read_git_runtime(repo_root)
    git_runtime["last_cleanup"] = event
    _append_bounded_event_list(git_runtime, "cleanup_history", event)
    _write_git_runtime(repo_root, git_runtime)

    result = {
        "ok": True,
        "deleted_branches": deleted_branches,
        "candidates": candidates,
        "git_runtime_path": status_payload.get("git_runtime_path", ""),
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"deleted_branches={','.join(deleted_branches) if deleted_branches else '(none)'}")
        for row in candidates:
            print(
                "candidate="
                + ",".join(
                    [
                        f"branch={row.get('branch', '')}",
                        f"reasons={'+'.join(row.get('reasons', []))}",
                        f"safe_delete={'true' if row.get('safe_delete') else 'false'}",
                    ]
                )
            )
    return 0


def cmd_frontier_init(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    _ensure_dirs(repo_root)
    paths = _frontier_paths(repo_root)
    if paths["stack_json"].exists() and not args.force:
        raise RuntimeError(
            f"frontier already exists at {_path_for_state(paths['stack_json'], repo_root)}. Use --force to overwrite."
        )

    program_id = str(args.program_id or "").strip() or (repo_root.name or "research-program")
    label = str(args.label or "").strip() or _frontier_default_label(repo_root, program_id)
    stack = _default_frontier_stack_payload(program_id, label)
    state = _default_frontier_state_payload()
    written = _frontier_write_materialized_views(repo_root, stack, state)
    result = {
        "ok": True,
        "program_id": program_id,
        "label": label,
        "paths": written,
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"program_id={program_id}")
        print(f"label={label}")
        for key, value in written.items():
            print(f"{key}={value}")
    return 0


def cmd_frontier_state(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    stack = _frontier_load_stack(repo_root)
    state = _frontier_load_state(repo_root)
    payload = {
        **state,
        "program_id": str(stack.get("program_id", "")).strip(),
        "label": str(stack.get("label", "")).strip(),
        "paths": {
            "state_json": _path_for_state(_frontier_paths(repo_root)["state_json"], repo_root),
            "state_md": _path_for_state(_frontier_paths(repo_root)["state_md"], repo_root),
        },
    }
    if args.json_output:
        _print_json(payload)
    else:
        print(f"program_id={payload['program_id']}")
        print(f"active_version={payload.get('active_version', '')}")
        print(f"active_milestone={payload.get('active_milestone', '')}")
        print(f"active_phase={payload.get('active_phase', '')}")
        print(f"band={payload.get('band', '')}")
        print(f"next_action={payload.get('next_action', '')}")
        blockers = _coerce_string_list(payload.get("blocked_by"))
        print("blocked_by=" + (",".join(blockers) if blockers else "(none)"))
    return 0


def cmd_frontier_stack(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    stack = _frontier_load_stack(repo_root)
    payload = {
        **stack,
        "paths": {
            "stack_json": _path_for_state(_frontier_paths(repo_root)["stack_json"], repo_root),
            "stack_md": _path_for_state(_frontier_paths(repo_root)["stack_md"], repo_root),
        },
    }
    if args.json_output:
        _print_json(payload)
    else:
        print(f"program_id={payload.get('program_id', '')}")
        print(f"label={payload.get('label', '')}")
        print(f"versions={len(payload.get('versions', [])) if isinstance(payload.get('versions'), list) else 0}")
    return 0


def cmd_frontier_roadmap(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload = _read_json_if_exists(_frontier_paths(repo_root)["roadmap_json"])
    if not payload:
        stack = _frontier_load_stack(repo_root)
        state = _frontier_load_state(repo_root)
        payload = _frontier_build_roadmap_payload(stack, state)
    if args.json_output:
        _print_json(payload)
    else:
        print(f"active_version={payload.get('active_version', '')}")
        print(f"active_milestone={payload.get('active_milestone', '')}")
        print(f"phases={len(payload.get('phases', [])) if isinstance(payload.get('phases'), list) else 0}")
    return 0


def cmd_frontier_checklist(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload = _read_json_if_exists(_frontier_paths(repo_root)["checklist_json"])
    if not payload:
        stack = _frontier_load_stack(repo_root)
        state = _frontier_load_state(repo_root)
        payload = _frontier_build_checklist_payload(stack, state)
    if args.json_output:
        _print_json(payload)
    else:
        print(f"active_version={payload.get('active_version', '')}")
        print(f"active_milestone={payload.get('active_milestone', '')}")
        print(f"exact={len(payload.get('exact', [])) if isinstance(payload.get('exact'), list) else 0}")
        print(f"structured={len(payload.get('structured', [])) if isinstance(payload.get('structured'), list) else 0}")
        print(f"horizon={len(payload.get('horizon', [])) if isinstance(payload.get('horizon'), list) else 0}")
    return 0


def cmd_frontier_add_version(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    stack = _frontier_load_stack(repo_root)
    state = _frontier_load_state(repo_root)
    version_id = str(args.id).strip()
    if _frontier_find_version(stack, version_id) is not None:
        raise RuntimeError(f"frontier version `{version_id}` already exists.")
    version = {
        "id": version_id,
        "label": str(args.label).strip(),
        "intent": str(args.intent or "").strip(),
        "status": str(args.status or "planned").strip() or "planned",
        "milestones": [],
    }
    versions = stack.get("versions")
    if not isinstance(versions, list):
        versions = []
        stack["versions"] = versions
    versions.append(version)
    written = _frontier_write_materialized_views(repo_root, stack, state)
    result = {"ok": True, "version": version, "paths": written}
    if args.json_output:
        _print_json(result)
    else:
        print(f"version_id={version_id}")
        print(f"label={version['label']}")
    return 0


def cmd_frontier_add_milestone(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    stack = _frontier_load_stack(repo_root)
    state = _frontier_load_state(repo_root)
    version_id = str(args.version).strip()
    version = _frontier_find_version(stack, version_id)
    if version is None:
        raise RuntimeError(f"frontier version `{version_id}` was not found.")
    milestone_id = str(args.id).strip()
    _, existing = _frontier_find_milestone(stack, milestone_id)
    if existing is not None:
        raise RuntimeError(f"frontier milestone `{milestone_id}` already exists.")
    band = str(args.band or "structured").strip()
    if band not in FRONTIER_BANDS:
        raise RuntimeError(f"frontier band must be one of: {', '.join(FRONTIER_BANDS)}")
    milestone = {
        "id": milestone_id,
        "parent_version": version_id,
        "label": str(args.label).strip(),
        "band": band,
        "status": str(args.status or "planned").strip() or "planned",
        "depends_on": _coerce_string_list(getattr(args, "depends_on", [])),
        "success_criteria": _coerce_string_list(getattr(args, "success_criterion", [])),
        "phases": [],
    }
    milestones = version.get("milestones")
    if not isinstance(milestones, list):
        milestones = []
        version["milestones"] = milestones
    milestones.append(milestone)
    written = _frontier_write_materialized_views(repo_root, stack, state)
    result = {"ok": True, "milestone": milestone, "paths": written}
    if args.json_output:
        _print_json(result)
    else:
        print(f"milestone_id={milestone_id}")
        print(f"version_id={version_id}")
    return 0


def cmd_frontier_add_phase(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    stack = _frontier_load_stack(repo_root)
    state = _frontier_load_state(repo_root)
    milestone_id = str(args.milestone).strip()
    _, milestone = _frontier_find_milestone(stack, milestone_id)
    if milestone is None:
        raise RuntimeError(f"frontier milestone `{milestone_id}` was not found.")
    phase_id = str(args.id).strip()
    if _frontier_find_phase(milestone, phase_id) is not None:
        raise RuntimeError(f"frontier phase `{phase_id}` already exists in milestone `{milestone_id}`.")
    compute_hooks: list[dict[str, Any]] = []
    compute_point_id = str(getattr(args, "compute_point_id", "") or "").strip()
    if compute_point_id:
        compute_hooks.append(
            {
                "compute_point_id": compute_point_id,
                "allowed_rungs": _coerce_string_list(getattr(args, "allowed_rung", [])),
                "paid_requires_user_approval": bool(getattr(args, "paid_requires_user_approval", False)),
            }
        )
    phase = {
        "id": phase_id,
        "label": str(args.label).strip(),
        "status": str(args.status or "planned").strip() or "planned",
        "goal": str(args.goal or "").strip(),
        "depends_on": _coerce_string_list(getattr(args, "depends_on", [])),
        "requirements": _coerce_string_list(getattr(args, "requirement", [])),
        "success_criteria": _coerce_string_list(getattr(args, "success_criterion", [])),
        "plans": _coerce_string_list(getattr(args, "plan", [])),
        "compute_hooks": compute_hooks,
    }
    phases = milestone.get("phases")
    if not isinstance(phases, list):
        phases = []
        milestone["phases"] = phases
    phases.append(phase)
    written = _frontier_write_materialized_views(repo_root, stack, state)
    result = {"ok": True, "phase": phase, "paths": written}
    if args.json_output:
        _print_json(result)
    else:
        print(f"phase_id={phase_id}")
        print(f"milestone_id={milestone_id}")
    return 0


def cmd_frontier_set_live(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    stack = _frontier_load_stack(repo_root)
    state = _frontier_load_state(repo_root)
    version_id = str(args.version).strip()
    milestone_id = str(args.milestone).strip()
    phase_id = str(args.phase or "").strip()

    version = _frontier_find_version(stack, version_id)
    if version is None:
        raise RuntimeError(f"frontier version `{version_id}` was not found.")
    _, milestone = _frontier_find_milestone(stack, milestone_id)
    if milestone is None:
        raise RuntimeError(f"frontier milestone `{milestone_id}` was not found.")
    if str(milestone.get("parent_version", "")).strip() and str(milestone.get("parent_version", "")).strip() != version_id:
        raise RuntimeError(f"frontier milestone `{milestone_id}` does not belong to version `{version_id}`.")
    if phase_id and _frontier_find_phase(milestone, phase_id) is None:
        raise RuntimeError(f"frontier phase `{phase_id}` was not found in milestone `{milestone_id}`.")

    versions = stack.get("versions")
    if isinstance(versions, list):
        for version_row in versions:
            if not isinstance(version_row, dict):
                continue
            version_row["status"] = "active" if str(version_row.get("id", "")).strip() == version_id else (
                str(version_row.get("status", "")).strip() or "planned"
            )
            milestones = version_row.get("milestones")
            if not isinstance(milestones, list):
                continue
            for milestone_row in milestones:
                if not isinstance(milestone_row, dict):
                    continue
                if str(milestone_row.get("id", "")).strip() == milestone_id:
                    milestone_row["status"] = "active"
                elif str(milestone_row.get("status", "")).strip() == "active":
                    milestone_row["status"] = "planned"
                phases = milestone_row.get("phases")
                if not isinstance(phases, list):
                    continue
                for phase_row in phases:
                    if not isinstance(phase_row, dict):
                        continue
                    if phase_id and str(milestone_row.get("id", "")).strip() == milestone_id:
                        if str(phase_row.get("id", "")).strip() == phase_id:
                            phase_row["status"] = "active"
                        elif str(phase_row.get("status", "")).strip() == "active":
                            phase_row["status"] = "planned"

    band = str(args.band or milestone.get("band", "") or "").strip()
    if band and band not in FRONTIER_BANDS:
        raise RuntimeError(f"frontier band must be one of: {', '.join(FRONTIER_BANDS)}")
    state["active_version"] = version_id
    state["active_milestone"] = milestone_id
    state["active_phase"] = phase_id
    state["band"] = band
    next_action = str(args.next_action or "").strip()
    if not next_action:
        next_action = f"execute phase {phase_id}" if phase_id else f"execute milestone {milestone_id}"
    state["next_action"] = next_action
    state["blocked_by"] = _coerce_string_list(getattr(args, "blocked_by", []))

    written = _frontier_write_materialized_views(repo_root, stack, state)
    result = {"ok": True, "state": state, "paths": written}
    if args.json_output:
        _print_json(result)
    else:
        print(f"active_version={state['active_version']}")
        print(f"active_milestone={state['active_milestone']}")
        print(f"active_phase={state['active_phase']}")
        print(f"next_action={state['next_action']}")
    return 0


def cmd_frontier_render(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    stack = _frontier_load_stack(repo_root)
    state = _frontier_load_state(repo_root)
    written = _frontier_write_materialized_views(repo_root, stack, state)
    result = {"ok": True, "paths": written}
    if args.json_output:
        _print_json(result)
    else:
        for key, value in written.items():
            print(f"{key}={value}")
    return 0


def cmd_frontier_doctor(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload = _frontier_doctor_payload(repo_root)
    fixes_applied: list[str] = []
    if args.fix and payload["ok"]:
        stack = _frontier_load_stack(repo_root)
        state = _frontier_load_state(repo_root)
        _frontier_write_materialized_views(repo_root, stack, state)
        fixes_applied.append("rendered_frontier_views")
    payload["fix"] = bool(args.fix)
    payload["fixes_applied"] = fixes_applied
    if args.json_output:
        _print_json(payload)
    else:
        print(f"ok={'true' if payload['ok'] else 'false'}")
        for issue in payload.get("issues", []):
            print(f"issue={issue.get('severity','')}:{issue.get('code','')}:{issue.get('message','')}")
        for fix_name in fixes_applied:
            print(f"fix={fix_name}")
    return 0 if payload["ok"] else 1


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


def _kernel_schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "spec" / "v1" / "kernel.schema.json"


def _kernel_proposal_schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "spec" / "v1" / "kernel-proposal.schema.json"


def _kernel_extension_schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "spec" / "v1" / "kernel-extension.schema.json"


def _load_kernel_schema() -> dict[str, Any]:
    path = _kernel_schema_path()
    if not path.exists():
        raise RuntimeError(f"kernel schema is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("kernel schema root must be an object")
    return payload


def _kernel_schema_metadata() -> tuple[dict[str, list[str]], dict[str, dict[str, Any]], set[str], list[str]]:
    schema = _load_kernel_schema()
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise RuntimeError("kernel schema is missing object properties")
    ordered_fields = [str(field).strip() for field in properties.keys() if str(field).strip()]

    field_kinds: dict[str, dict[str, Any]] = {}
    for field, raw in properties.items():
        if not isinstance(raw, dict):
            continue
        if "const" in raw:
            field_kinds[field] = {"kind": "const", "value": raw.get("const")}
            continue
        if "enum" in raw and isinstance(raw.get("enum"), list):
            field_kinds[field] = {"kind": "enum", "value": list(raw.get("enum", []))}
            continue
        ref = raw.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            field_kinds[field] = {"kind": ref.split("/")[-1]}

    requirements: dict[str, list[str]] = {}
    raw_all_of = schema.get("allOf")
    if isinstance(raw_all_of, list):
        for clause in raw_all_of:
            if not isinstance(clause, dict):
                continue
            raw_if = clause.get("if")
            raw_then = clause.get("then")
            if not isinstance(raw_if, dict) or not isinstance(raw_then, dict):
                continue
            const = (
                raw_if.get("properties", {})
                .get("artifact_class", {})
                .get("const")
            )
            required_fields = raw_then.get("required")
            if isinstance(const, str) and isinstance(required_fields, list):
                requirements[const] = [
                    str(field).strip()
                    for field in required_fields
                    if isinstance(field, str) and str(field).strip()
                ]
    return requirements, field_kinds, set(field_kinds.keys()), ordered_fields


(
    KERNEL_ARTIFACT_CLASS_REQUIREMENTS,
    KERNEL_FIELD_KINDS,
    KERNEL_ALLOWED_FIELDS,
    KERNEL_FIELD_ORDER,
) = _kernel_schema_metadata()


def _kernel_ordered_fields_for_class(artifact_class: str, present_fields: Sequence[str] | None = None) -> list[str]:
    ordered: list[str] = ["schema_version", "artifact_class"]
    required_fields = KERNEL_ARTIFACT_CLASS_REQUIREMENTS.get(str(artifact_class).strip(), [])
    for field in required_fields:
        if field not in ordered:
            ordered.append(field)
    for field in KERNEL_FIELD_ORDER:
        if field not in ordered:
            ordered.append(field)
    if present_fields is None:
        return ordered
    present_set = {str(field).strip() for field in present_fields if str(field).strip()}
    return [field for field in ordered if field in present_set]


def _kernel_text_valid(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _kernel_text_list_valid(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(_kernel_text_valid(item) for item in value)


def _kernel_field_present(field: str, value: Any) -> bool:
    kind = str(KERNEL_FIELD_KINDS.get(field, {}).get("kind", ""))
    if kind == "non_empty_text":
        return _kernel_text_valid(value)
    if kind == "text_list":
        return _kernel_text_list_valid(value)
    if kind == "text_or_text_list":
        return _kernel_text_valid(value) or _kernel_text_list_valid(value)
    if kind == "const":
        return value is not None
    if kind == "enum":
        return value is not None
    return value is not None


def _kernel_field_shape_issues(field: str, value: Any) -> list[str]:
    meta = KERNEL_FIELD_KINDS.get(field, {})
    kind = str(meta.get("kind", ""))
    if kind == "const":
        expected = meta.get("value")
        return [] if value == expected else [f"must equal `{expected}`."]
    if kind == "enum":
        allowed = [str(x) for x in meta.get("value", [])]
        return [] if value in allowed else [f"must be one of: {', '.join(allowed)}."]
    if kind == "non_empty_text":
        return [] if _kernel_text_valid(value) else ["must be a non-empty string."]
    if kind == "text_list":
        return [] if _kernel_text_list_valid(value) else ["must be a non-empty list of non-empty strings."]
    if kind == "text_or_text_list":
        return [] if (_kernel_text_valid(value) or _kernel_text_list_valid(value)) else [
            "must be a non-empty string or a non-empty list of non-empty strings."
        ]
    return []


def _validate_kernel_payload(
    payload: dict[str, Any],
    *,
    expected_class: str = "",
    extra_required_fields: Sequence[str] = (),
) -> dict[str, Any]:
    artifact_issues: list[str] = []
    missing_fields: list[str] = []

    for field in sorted(str(key) for key in payload.keys() if str(key) not in KERNEL_ALLOWED_FIELDS):
        artifact_issues.append(f"unexpected field: `{field}`.")

    schema_version = payload.get("schema_version")
    artifact_issues.extend(
        [f"field `schema_version` {issue}" for issue in _kernel_field_shape_issues("schema_version", schema_version)]
    )

    actual_class = str(payload.get("artifact_class", "")).strip()
    artifact_issues.extend(
        [f"field `artifact_class` {issue}" for issue in _kernel_field_shape_issues("artifact_class", payload.get("artifact_class"))]
    )
    if actual_class not in KERNEL_ARTIFACT_CLASS_REQUIREMENTS:
        artifact_issues.append(f"unsupported artifact_class: {actual_class or '(missing)'}.")

    if expected_class and actual_class and expected_class != actual_class:
        artifact_issues.append(
            f"artifact_class mismatch: expected `{expected_class}`, found `{actual_class}`."
        )

    field_class = actual_class or expected_class
    required_fields = list(KERNEL_ARTIFACT_CLASS_REQUIREMENTS.get(field_class, []))
    for field in _unique_strings([str(x).strip() for x in extra_required_fields if str(x).strip()]):
        if field not in required_fields:
            required_fields.append(field)
    for field, value in payload.items():
        if not isinstance(field, str) or field not in KERNEL_ALLOWED_FIELDS:
            continue
        for issue in _kernel_field_shape_issues(field, value):
            artifact_issues.append(f"field `{field}` {issue}")
    for field in required_fields:
        if not _kernel_field_present(field, payload.get(field)):
            missing_fields.append(field)
    if missing_fields:
        artifact_issues.append("missing required fields: " + ", ".join(missing_fields))

    return {
        "artifact_class": actual_class,
        "expected_artifact_class": expected_class,
        "valid": not artifact_issues,
        "missing_fields": missing_fields,
        "issues": artifact_issues,
    }


def _kernel_canonical_payload(
    payload: dict[str, Any],
    *,
    drop_unknown_fields: bool,
) -> tuple[dict[str, Any], list[str]]:
    unknown_fields = sorted(str(key) for key in payload.keys() if str(key) not in KERNEL_ALLOWED_FIELDS)
    if unknown_fields and not drop_unknown_fields:
        raise RuntimeError(
            "kernel artifact has unknown fields: " + ", ".join(unknown_fields) + ". Re-run with --drop-unknown-fields to discard them."
        )

    artifact_class = str(payload.get("artifact_class", "")).strip()
    if artifact_class not in KERNEL_ARTIFACT_CLASS_REQUIREMENTS:
        raise RuntimeError(f"unsupported artifact_class: {artifact_class or '(missing)'}")

    known_payload = {
        str(key): value
        for key, value in payload.items()
        if str(key) in KERNEL_ALLOWED_FIELDS
    }
    known_payload["schema_version"] = KERNEL_SCHEMA_VERSION
    known_payload["artifact_class"] = artifact_class

    ordered_fields = _kernel_ordered_fields_for_class(artifact_class, present_fields=list(known_payload.keys()))
    canonical: dict[str, Any] = {}
    for field in ordered_fields:
        if field in known_payload:
            canonical[field] = known_payload[field]
    return canonical, unknown_fields


def _kernel_proposal_template(
    *,
    proposal_kind: str,
    title: str,
    target_artifact_classes: Sequence[str],
    target_fields: Sequence[str],
) -> dict[str, Any]:
    clean_classes = _unique_strings([str(x).strip() for x in target_artifact_classes if str(x).strip()])
    clean_fields = _unique_strings([str(x).strip() for x in target_fields if str(x).strip()])
    return {
        "schema_version": KERNEL_SCHEMA_VERSION,
        "proposal_kind": proposal_kind,
        "title": title,
        "status": "draft",
        "summary": "describe the kernel evolution being proposed",
        "target_scope": {
            "artifact_classes": clean_classes,
            "fields": clean_fields,
        },
        "proposed_change": [
            "describe the exact structural change",
        ],
        "rationale": [
            "describe why the current kernel is insufficient",
        ],
        "evidence_refs": [
            "docs/ORP_REASONING_KERNEL_EVIDENCE_MATRIX.md",
        ],
        "compatibility_notes": [
            "describe backward-compatibility expectations",
        ],
        "migration_plan": [
            "describe how existing artifacts will be preserved or migrated",
        ],
        "evaluation_plan": [
            "describe what new evidence should justify promotion into the core kernel",
        ],
    }


def _kernel_observation_stats_from_run(run: dict[str, Any]) -> dict[str, Any]:
    results = run.get("results", [])
    if not isinstance(results, list):
        results = []
    kernel_rows = [
        row.get("kernel_validation")
        for row in results
        if isinstance(row, dict) and isinstance(row.get("kernel_validation"), dict)
    ]
    return {
        "run_id": str(run.get("run_id", "")).strip(),
        "kernel_validations": kernel_rows,
    }


def _kernel_validation_mode(gate: dict[str, Any]) -> str:
    kernel_cfg = gate.get("kernel") if isinstance(gate.get("kernel"), dict) else {}
    default_mode = "hard" if str(gate.get("phase", "")).strip() == "structure_kernel" else "soft"
    mode = str(kernel_cfg.get("mode", default_mode)).strip().lower()
    if mode in {"soft", "hard"}:
        return mode
    return default_mode


def _kernel_artifact_specs(
    gate: dict[str, Any],
    repo_root: Path,
    vars_map: dict[str, str],
) -> list[dict[str, Any]]:
    kernel_cfg = gate.get("kernel") if isinstance(gate.get("kernel"), dict) else {}
    raw_artifacts = kernel_cfg.get("artifacts")
    if not isinstance(raw_artifacts, list):
        return []

    specs: list[dict[str, Any]] = []
    for raw in raw_artifacts:
        if not isinstance(raw, dict):
            continue
        path_raw = str(raw.get("path", "")).strip()
        if not path_raw:
            continue
        replaced = _replace_vars(path_raw, vars_map)
        path = Path(replaced)
        if not path.is_absolute():
            path = repo_root / path
        specs.append(
            {
                "path": path.resolve(),
                "expected_artifact_class": str(raw.get("artifact_class", "")).strip(),
                "required": bool(raw.get("required", True)),
                "extra_required_fields": _unique_strings(
                    [str(x).strip() for x in raw.get("extra_required_fields", []) if isinstance(x, str)]
                ),
            }
        )
    return specs


def _validate_kernel_gate(
    gate: dict[str, Any],
    repo_root: Path,
    vars_map: dict[str, str],
) -> dict[str, Any] | None:
    if str(gate.get("phase", "")).strip() != "structure_kernel":
        return None
    if not isinstance(gate.get("kernel"), dict):
        return None

    mode = _kernel_validation_mode(gate)
    specs = _kernel_artifact_specs(gate, repo_root, vars_map)
    issues: list[str] = []
    artifact_results: list[dict[str, Any]] = []

    if not specs:
        issues.append("structure_kernel gate requires kernel.artifacts.")

    for spec in specs:
        path = spec["path"]
        expected_class = str(spec.get("expected_artifact_class", "")).strip()
        required = bool(spec.get("required", True))
        extra_required_fields = [
            str(x).strip()
            for x in spec.get("extra_required_fields", [])
            if isinstance(x, str) and str(x).strip()
        ]

        artifact_issues: list[str] = []
        missing_fields: list[str] = []
        exists = path.exists()
        optional_skipped = False
        payload: dict[str, Any] = {}

        if not exists:
            if required:
                artifact_issues.append("kernel artifact file is missing.")
            else:
                optional_skipped = True
        else:
            try:
                loaded_payload = _load_config(path)
                if isinstance(loaded_payload, dict):
                    payload = loaded_payload
                else:
                    artifact_issues.append("kernel artifact root must be an object.")
            except Exception as exc:
                artifact_issues.append(f"failed to parse kernel artifact: {exc}")

        actual_class = ""
        if payload:
            validation = _validate_kernel_payload(
                payload,
                expected_class=expected_class,
                extra_required_fields=extra_required_fields,
            )
            actual_class = str(validation.get("artifact_class", "")).strip()
            missing_fields = list(validation.get("missing_fields", []))
            artifact_issues.extend([str(issue) for issue in validation.get("issues", []) if isinstance(issue, str)])

        valid = optional_skipped or (exists and not artifact_issues)
        path_state = _path_for_state(path, repo_root)
        artifact_results.append(
            {
                "path": path_state,
                "exists": exists,
                "required": required,
                "optional_skipped": optional_skipped,
                "artifact_class": actual_class,
                "expected_artifact_class": expected_class,
                "valid": valid,
                "missing_fields": missing_fields,
                "issues": artifact_issues,
            }
        )
        issues.extend([f"{path_state}: {issue}" for issue in artifact_issues])

    valid = bool(specs) and all(bool(row.get("valid")) for row in artifact_results)
    return {
        "mode": mode,
        "valid": valid,
        "artifacts_total": len(artifact_results),
        "artifacts_valid": sum(1 for row in artifact_results if row.get("valid")),
        "issues": issues,
        "artifacts": artifact_results,
    }


def _kernel_template_payload(artifact_class: str, name_hint: str = "") -> dict[str, Any]:
    hint = str(name_hint or "").strip() or "this artifact"
    templates: dict[str, dict[str, Any]] = {
        "task": {
            "object": f"describe the task object for {hint}",
            "goal": "describe the intended outcome",
            "boundary": ["define what is in scope", "define what is out of scope"],
            "constraints": ["list the main constraints"],
            "success_criteria": ["describe how success will be recognized"],
        },
        "decision": {
            "question": f"describe the decision question for {hint}",
            "chosen_path": "describe the selected path",
            "rejected_alternatives": ["list key rejected alternatives"],
            "rationale": "describe why this path was chosen",
            "consequences": ["list immediate consequences and tradeoffs"],
        },
        "hypothesis": {
            "claim": f"state the hypothesis for {hint}",
            "boundary": "describe the domain or conditions where the claim is meant to hold",
            "assumptions": ["list assumptions the claim depends on"],
            "test_path": "describe how the hypothesis will be tested",
            "falsifiers": ["list what would falsify the hypothesis"],
        },
        "experiment": {
            "objective": f"describe the experiment objective for {hint}",
            "method": "describe the method or procedure",
            "inputs": ["list the required inputs"],
            "outputs": ["list the expected outputs"],
            "evidence_expectations": ["list the evidence this experiment should produce"],
            "interpretation_limits": ["list limits on interpretation"],
        },
        "checkpoint": {
            "completed_unit": f"describe the completed unit for {hint}",
            "current_state": "describe the current state of work",
            "risks": ["list immediate risks or unresolved concerns"],
            "next_handoff_target": "describe what the next operator or agent should pick up",
            "artifact_refs": ["list the key artifact paths tied to this checkpoint"],
        },
        "policy": {
            "scope": f"describe the policy scope for {hint}",
            "rule": "state the rule",
            "rationale": "describe why the rule exists",
            "invariants": ["list the invariants the rule protects"],
            "enforcement_surface": "describe where ORP should enforce or check this policy",
        },
        "result": {
            "claim": f"state the resulting claim for {hint}",
            "evidence_paths": ["list canonical evidence paths"],
            "status": "describe the result status",
            "interpretation_limits": ["list the limits on what this result means"],
            "next_follow_up": "describe the next follow-up action",
        },
    }
    if artifact_class not in templates:
        raise RuntimeError(f"unsupported kernel artifact class: {artifact_class}")
    return {
        "schema_version": "1.0.0",
        "artifact_class": artifact_class,
        **templates[artifact_class],
    }


def _write_structured_payload(path: Path, payload: dict[str, Any], *, format_hint: str = "") -> str:
    fmt = str(format_hint or "").strip().lower()
    if not fmt:
        if path.suffix.lower() == ".json":
            fmt = "json"
        elif path.suffix.lower() in {".yaml", ".yml"}:
            fmt = "yaml"
        else:
            fmt = "yaml"

    if fmt == "json":
        _write_json(path, payload)
        return "json"

    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise RuntimeError("YAML output requires PyYAML. Use --format json or install PyYAML.") from exc
    _write_text(path, yaml.safe_dump(payload, sort_keys=False, allow_unicode=False))
    return "yaml"


def cmd_kernel_validate(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    artifact_path = _resolve_cli_path(args.artifact, repo_root)
    fake_gate = {
        "phase": "structure_kernel",
        "kernel": {
            "mode": "hard",
            "artifacts": [
                {
                    "path": str(artifact_path),
                    "artifact_class": str(getattr(args, "artifact_class", "") or "").strip(),
                    "extra_required_fields": list(getattr(args, "required_field", []) or []),
                }
            ],
        },
    }
    validation = _validate_kernel_gate(fake_gate, repo_root, {})
    if validation is None:
        raise RuntimeError("failed to construct kernel validation request")

    artifact_result = validation.get("artifacts", [None])[0] if isinstance(validation.get("artifacts"), list) else None
    result = {
        "ok": bool(validation.get("valid")),
        "artifact": _path_for_state(artifact_path, repo_root),
        "expected_artifact_class": str(getattr(args, "artifact_class", "") or "").strip(),
        "validation": validation,
        "artifact_result": artifact_result,
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"artifact={result['artifact']}")
        print(f"valid={'true' if result['ok'] else 'false'}")
        if artifact_result:
            print(f"artifact_class={artifact_result.get('artifact_class', '')}")
            missing = artifact_result.get("missing_fields", [])
            print("missing_fields=" + (",".join(missing) if missing else "(none)"))
        for issue in validation.get("issues", []):
            print(f"issue={issue}")
    return 0 if result["ok"] else 1


def cmd_kernel_scaffold(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    out_path = _resolve_cli_path(args.out, repo_root)
    if out_path.exists() and not args.force:
        raise RuntimeError(
            f"kernel artifact already exists: {_path_for_state(out_path, repo_root)}. Use --force to overwrite."
        )
    payload = _kernel_template_payload(args.artifact_class, args.name or repo_root.name)
    emitted_format = _write_structured_payload(out_path, payload, format_hint=args.format)
    result = {
        "ok": True,
        "artifact_class": args.artifact_class,
        "path": _path_for_state(out_path, repo_root),
        "format": emitted_format,
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"path={result['path']}")
        print(f"artifact_class={result['artifact_class']}")
        print(f"format={result['format']}")
    return 0


def _resolve_kernel_run_json_paths(
    *,
    repo_root: Path,
    run_ids: Sequence[str],
    run_jsons: Sequence[str],
) -> list[Path]:
    resolved: list[Path] = []
    if run_jsons:
        for raw in run_jsons:
            if not str(raw).strip():
                continue
            _, path = _resolve_run_json_path(repo_root=repo_root, run_id_arg="", run_json_arg=str(raw))
            resolved.append(path)
        return resolved
    if run_ids:
        for raw in run_ids:
            if not str(raw).strip():
                continue
            _, path = _resolve_run_json_path(repo_root=repo_root, run_id_arg=str(raw), run_json_arg="")
            resolved.append(path)
        return resolved

    seen: set[Path] = set()
    state_path = repo_root / "orp" / "state.json"
    if state_path.exists():
        try:
            state = _read_json(state_path)
        except Exception:
            state = {}
        runs = state.get("runs")
        if isinstance(runs, dict):
            for value in runs.values():
                if not isinstance(value, str) or not value.strip():
                    continue
                candidate = (repo_root / value).resolve()
                if candidate.exists() and candidate not in seen:
                    seen.add(candidate)
                    resolved.append(candidate)
    artifacts_root = repo_root / "orp" / "artifacts"
    if artifacts_root.exists():
        for candidate in sorted(artifacts_root.glob("*/RUN.json")):
            candidate = candidate.resolve()
            if candidate not in seen:
                seen.add(candidate)
                resolved.append(candidate)
    return resolved


def _kernel_stats_payload(
    repo_root: Path,
    run_json_paths: Sequence[Path],
) -> dict[str, Any]:
    runs_scanned = 0
    runs_with_kernel_validation = 0
    gate_rows_total = 0
    artifacts_total = 0
    artifacts_valid = 0
    artifacts_invalid = 0
    mode_counts: dict[str, int] = {}
    artifact_class_counts: dict[str, int] = {}
    missing_field_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    path_counts: dict[str, int] = {}
    per_run: list[dict[str, Any]] = []

    for run_json in run_json_paths:
        run = _read_json(run_json)
        stats = _kernel_observation_stats_from_run(run)
        kernel_rows = stats["kernel_validations"]
        runs_scanned += 1
        if kernel_rows:
            runs_with_kernel_validation += 1
        per_run.append(
            {
                "run_id": stats["run_id"] or run_json.parent.name,
                "run_json": _path_for_state(run_json, repo_root),
                "kernel_validations": len(kernel_rows),
            }
        )
        for row in kernel_rows:
            if not isinstance(row, dict):
                continue
            gate_rows_total += 1
            mode = str(row.get("mode", "")).strip() or "unknown"
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
            for artifact in row.get("artifacts", []) if isinstance(row.get("artifacts"), list) else []:
                if not isinstance(artifact, dict):
                    continue
                artifacts_total += 1
                if artifact.get("valid"):
                    artifacts_valid += 1
                else:
                    artifacts_invalid += 1
                artifact_class = str(
                    artifact.get("artifact_class") or artifact.get("expected_artifact_class") or "unknown"
                ).strip() or "unknown"
                artifact_class_counts[artifact_class] = artifact_class_counts.get(artifact_class, 0) + 1
                artifact_path = str(artifact.get("path", "")).strip()
                if artifact_path:
                    path_counts[artifact_path] = path_counts.get(artifact_path, 0) + 1
                for field in artifact.get("missing_fields", []) if isinstance(artifact.get("missing_fields"), list) else []:
                    key = str(field).strip()
                    if key:
                        missing_field_counts[key] = missing_field_counts.get(key, 0) + 1
                for issue in artifact.get("issues", []) if isinstance(artifact.get("issues"), list) else []:
                    key = str(issue).strip()
                    if key:
                        issue_counts[key] = issue_counts.get(key, 0) + 1

    top_missing_fields = [
        {"field": key, "count": count}
        for key, count in sorted(missing_field_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]
    top_issue_signals = [
        {"issue": key, "count": count}
        for key, count in sorted(issue_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]
    top_paths = [
        {"path": key, "count": count}
        for key, count in sorted(path_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]
    observations: list[str] = []
    if runs_scanned == 0:
        observations.append("No RUN.json artifacts were found. Run `orp gate run` with a structure_kernel gate to collect kernel observations.")
    elif runs_with_kernel_validation == 0:
        observations.append("RUN.json artifacts exist, but none recorded kernel_validation. Add a structure_kernel gate with a kernel.artifacts block.")
    else:
        if top_missing_fields:
            focus = ", ".join(f"{row['field']} ({row['count']})" for row in top_missing_fields[:5])
            observations.append(f"Most repeated missing fields: {focus}.")
        if artifacts_invalid == 0:
            observations.append("All observed kernel artifacts validated successfully across scanned runs.")
        else:
            observations.append(
                f"{artifacts_invalid} of {artifacts_total} observed kernel artifacts failed validation."
            )
    return {
        "ok": True,
        "repo_root": str(repo_root),
        "runs_scanned": runs_scanned,
        "runs_with_kernel_validation": runs_with_kernel_validation,
        "kernel_validation_rows": gate_rows_total,
        "artifacts_total": artifacts_total,
        "artifacts_valid": artifacts_valid,
        "artifacts_invalid": artifacts_invalid,
        "artifact_validation_rate": round((artifacts_valid / artifacts_total), 3) if artifacts_total else None,
        "mode_counts": mode_counts,
        "artifact_class_counts": artifact_class_counts,
        "top_missing_fields": top_missing_fields,
        "top_issue_signals": top_issue_signals,
        "top_paths": top_paths,
        "observations": observations,
        "runs": per_run,
    }


def cmd_kernel_stats(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    run_json_paths = _resolve_kernel_run_json_paths(
        repo_root=repo_root,
        run_ids=list(getattr(args, "run_id", []) or []),
        run_jsons=list(getattr(args, "run_json", []) or []),
    )
    payload = _kernel_stats_payload(repo_root, run_json_paths)
    if args.json_output:
        _print_json(payload)
    else:
        print(f"runs_scanned={payload['runs_scanned']}")
        print(f"runs_with_kernel_validation={payload['runs_with_kernel_validation']}")
        print(f"artifacts_total={payload['artifacts_total']}")
        print(f"artifacts_valid={payload['artifacts_valid']}")
        print(f"artifacts_invalid={payload['artifacts_invalid']}")
        for row in payload.get("top_missing_fields", []):
            print(f"missing_field={row['field']} count={row['count']}")
        for note in payload.get("observations", []):
            print(f"note={note}")
    return 0


def cmd_kernel_propose(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    title = str(args.title or "").strip()
    if not title:
        raise RuntimeError("proposal title is required.")
    slug = _slug_token(getattr(args, "slug", "") or title, fallback="kernel-proposal")
    out_raw = str(getattr(args, "out", "") or "").strip()
    if out_raw:
        out_path = _resolve_cli_path(out_raw, repo_root)
    else:
        out_path = repo_root / "analysis" / "kernel-proposals" / f"{slug}.yml"
    if out_path.exists() and not args.force:
        raise RuntimeError(
            f"kernel proposal already exists: {_path_for_state(out_path, repo_root)}. Use --force to overwrite."
        )
    payload = _kernel_proposal_template(
        proposal_kind=str(args.kind).strip(),
        title=title,
        target_artifact_classes=list(getattr(args, "artifact_class", []) or []),
        target_fields=list(getattr(args, "field", []) or []),
    )
    emitted_format = _write_structured_payload(out_path, payload, format_hint=args.format)
    result = {
        "ok": True,
        "path": _path_for_state(out_path, repo_root),
        "format": emitted_format,
        "proposal_kind": payload["proposal_kind"],
        "title": payload["title"],
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"path={result['path']}")
        print(f"proposal_kind={result['proposal_kind']}")
        print(f"title={result['title']}")
        print(f"format={result['format']}")
    return 0


def cmd_kernel_migrate(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    artifact_path = _resolve_cli_path(args.artifact, repo_root)
    if not artifact_path.exists():
        raise RuntimeError(f"kernel artifact not found: {_path_for_state(artifact_path, repo_root)}")
    loaded_payload = _load_config(artifact_path)
    if not isinstance(loaded_payload, dict):
        raise RuntimeError("kernel artifact root must be an object.")
    out_raw = str(getattr(args, "out", "") or "").strip()
    out_path = _resolve_cli_path(out_raw, repo_root) if out_raw else artifact_path
    if out_path.exists() and out_path != artifact_path and not args.force:
        raise RuntimeError(
            f"output path already exists: {_path_for_state(out_path, repo_root)}. Use --force to overwrite."
        )

    original_schema_version = str(loaded_payload.get("schema_version", "") or "").strip()
    canonical_payload, dropped_unknown_fields = _kernel_canonical_payload(
        loaded_payload,
        drop_unknown_fields=bool(getattr(args, "drop_unknown_fields", False)),
    )
    emitted_format = _write_structured_payload(out_path, canonical_payload, format_hint=args.format)
    validation = _validate_kernel_payload(canonical_payload, expected_class=str(canonical_payload.get("artifact_class", "")).strip())
    result = {
        "ok": True,
        "artifact": _path_for_state(artifact_path, repo_root),
        "path": _path_for_state(out_path, repo_root),
        "format": emitted_format,
        "schema_version_before": original_schema_version or "(missing)",
        "schema_version_after": str(canonical_payload.get("schema_version", "")),
        "schema_version_updated": (original_schema_version or "") != str(canonical_payload.get("schema_version", "")),
        "artifact_class": str(canonical_payload.get("artifact_class", "")),
        "dropped_unknown_fields": dropped_unknown_fields,
        "validation": validation,
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"path={result['path']}")
        print(f"artifact_class={result['artifact_class']}")
        print(f"schema_version_before={result['schema_version_before']}")
        print(f"schema_version_after={result['schema_version_after']}")
        if dropped_unknown_fields:
            print("dropped_unknown_fields=" + ",".join(dropped_unknown_fields))
        print(f"valid={'true' if validation.get('valid') else 'false'}")
        for issue in validation.get("issues", []):
            print(f"issue={issue}")
    return 0


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
        evidence_cfg = gate.get("evidence", {}) if isinstance(gate.get("evidence"), dict) else {}
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

        kernel_validation = _validate_kernel_gate(gate, repo_root, vars_map)
        kernel_ok = True
        if kernel_validation is not None and kernel_validation.get("mode") == "hard":
            kernel_ok = bool(kernel_validation.get("valid"))

        passed = (
            ok_exit
            and ok_out
            and ok_err
            and (len(file_issues) == 0)
            and (exec_status == "ok")
            and kernel_ok
        )
        status = "pass" if passed else "fail"
        issues = []
        if not ok_exit:
            issues.append(f"exit code {rc} not in {exit_codes}")
        issues.extend(out_issues)
        issues.extend(err_issues)
        issues.extend(file_issues)
        if exec_status != "ok":
            issues.append(exec_status)
        if kernel_validation is not None and not kernel_validation.get("valid"):
            issues.extend(
                [
                    f"kernel validation: {issue}"
                    for issue in kernel_validation.get("issues", [])
                    if isinstance(issue, str)
                ]
            )

        evidence_paths = _resolve_config_paths(
            evidence_cfg.get("paths", []) if isinstance(evidence_cfg, dict) else [],
            repo_root,
            vars_map,
        )
        evidence_status = (
            str(evidence_cfg.get("status", "")).strip()
            if isinstance(evidence_cfg, dict)
            else ""
        ) or "process_only"
        evidence_note = (
            str(evidence_cfg.get("note", "")).strip()
            if isinstance(evidence_cfg, dict)
            else ""
        )

        result_row = {
            "gate_id": gate_id,
            "phase": gate.get("phase", "custom"),
            "command": cmd,
            "status": status,
            "exit_code": rc,
            "duration_ms": dur_ms,
            "stdout_path": str(stdout_path.relative_to(repo_root)),
            "stderr_path": str(stderr_path.relative_to(repo_root)),
            "rule_issues": issues,
            "evidence_paths": evidence_paths,
            "evidence_status": evidence_status,
            "evidence_note": evidence_note,
        }
        if kernel_validation is not None:
            result_row["kernel_validation"] = kernel_validation

        run_results.append(result_row)

        if not passed:
            on_fail = str(gate.get("on_fail", "stop"))
            if on_fail in {"stop", "mark_blocked"}:
                stop_now = True

    ended = _now_utc()
    gates_passed = sum(1 for g in run_results if g["status"] == "pass")
    gates_failed = sum(1 for g in run_results if g["status"] == "fail")
    gates_total = len(run_results)
    overall = "PASS" if gates_failed == 0 else "FAIL"
    git_snapshot = _git_governance_snapshot(
        repo_root,
        default_branch="main",
        allow_protected_branch_work=True,
    )

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
        "repo": {
            "git": {
                "present": git_snapshot["present"],
                "branch": git_snapshot["branch"],
                "commit": git_snapshot["commit"],
                "dirty_before_run": git_snapshot["dirty"],
            }
        },
    }

    state_path = repo_root / "orp" / "state.json"
    state = _read_json(state_path)
    run_record["epistemic_status"] = _derive_epistemic_status(
        config=config,
        run_results=run_results,
        state=state,
        repo_root=repo_root,
        vars_map=vars_map,
    )

    run_json_path = run_artifacts / "RUN.json"
    _write_json(run_json_path, run_record)

    runs = state.setdefault("runs", {})
    if isinstance(runs, dict):
        runs[run_id] = str(run_json_path.relative_to(repo_root))
    state["last_run_id"] = run_id
    _write_json(state_path, state)

    result = {
        "run_id": run_id,
        "overall": overall,
        "gates_passed": gates_passed,
        "gates_failed": gates_failed,
        "gates_total": gates_total,
        "run_record": str(run_json_path.relative_to(repo_root)),
    }
    if args.json_output:
        _print_json(result)
    else:
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
    git_present = False
    try:
        inside = subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(repo_root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        git_present = inside == "true"
    except Exception:
        git_present = False
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
    epistemic_status = run.get("epistemic_status")
    if not isinstance(epistemic_status, dict):
        epistemic_status = _derive_epistemic_status(
            config=effective_config,
            run_results=run.get("results", []) if isinstance(run.get("results"), list) else [],
            state=state,
            repo_root=repo_root,
            vars_map={"run_id": run_id},
        )
    strongest_evidence_paths = [
        str(x) for x in epistemic_status.get("strongest_evidence_paths", []) if isinstance(x, str)
    ]
    claim_context = _collect_claim_context(effective_config, run, strongest_evidence_paths)

    packet = {
        "schema_version": "1.0.0",
        "packet_id": packet_id,
        "kind": kind,
        "created_at_utc": now,
        "protocol_boundary": {
            "process_only": True,
            "evidence_paths": strongest_evidence_paths,
            "note": "Packet is process metadata. Evidence remains in canonical artifact paths.",
        },
        "repo": {
            "root_path": str(repo_root),
            "git": {
                "present": git_present,
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
        "evidence_status": epistemic_status,
        "artifacts": {
            "packet_json_path": f"orp/packets/{packet_id}.json",
            "packet_md_path": f"orp/packets/{packet_id}.md",
            "artifact_root": f"orp/artifacts/{run_id}",
            "extra_paths": [],
        },
    }
    if kind in {"pr", "claim", "verification"}:
        packet["claim_context"] = claim_context
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

    result = {
        "packet_id": packet_id,
        "packet_json": str(packet_json_path.relative_to(repo_root)),
        "packet_md": str(packet_md_path.relative_to(repo_root)),
        "packet_kind": kind,
        "run_id": run_id,
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"packet_id={packet_id}")
        print(f"packet_json={packet_json_path.relative_to(repo_root)}")
        print(f"packet_md={packet_md_path.relative_to(repo_root)}")
    return 0


def cmd_pack_list(args: argparse.Namespace) -> int:
    packs_root, packs = _discover_packs()
    if args.json_output:
        _print_json(
            {
                "packs_root": str(packs_root),
                "packs_count": len(packs),
                "packs": packs,
            }
        )
        return 0

    if not packs:
        print(f"packs_root={packs_root}")
        print("packs.count=0")
        return 0

    for pack in packs:
        pack_id = pack.get("id", "")
        version = pack.get("version", "unknown")
        name = pack.get("name", "")
        path = pack.get("path", "")
        print(f"pack.id={pack_id}")
        print(f"pack.version={version}")
        print(f"pack.path={path}")
        if name:
            print(f"pack.name={name}")
        print("---")

    print(f"packs_root={packs_root}")
    print(f"packs.count={len(packs)}")
    return 0


def cmd_discover_profile_init(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    out_path = _resolve_cli_path(args.out or DEFAULT_DISCOVER_PROFILE, repo_root)
    payload = _discover_profile_template(
        profile_id=args.profile_id,
        owner=args.owner or "",
        owner_type=args.owner_type,
        keywords=_coerce_string_list(args.keyword),
        topics=_coerce_string_list(args.topic),
        languages=_coerce_string_list(args.language),
        areas=_coerce_string_list(args.area),
        people=_coerce_string_list(args.person),
    )
    _write_json(out_path, payload)

    result = {
        "ok": True,
        "profile_path": _path_for_state(out_path, repo_root),
        "profile_id": payload["profile_id"],
        "owner_login": payload["discover"]["github"]["owner"]["login"],
        "owner_type": payload["discover"]["github"]["owner"]["type"],
        "notes": payload["notes"],
    }
    if args.json_output:
        _print_json(result)
        return 0

    print(f"profile_path={result['profile_path']}")
    print(f"profile_id={result['profile_id']}")
    print(f"owner_login={result['owner_login']}")
    print(f"owner_type={result['owner_type']}")
    print(f"next=orp discover github scan --profile {result['profile_path']}")
    return 0


def cmd_discover_github_scan(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    profile_path = _resolve_cli_path(args.profile or DEFAULT_DISCOVER_PROFILE, repo_root)
    if not profile_path.exists():
        raise RuntimeError(
            f"missing discovery profile: {_path_for_state(profile_path, repo_root)}. "
            "Run `orp discover profile init` first."
        )

    repos_fixture = _resolve_cli_path(args.repos_fixture, repo_root) if args.repos_fixture else None
    issues_fixture = _resolve_cli_path(args.issues_fixture, repo_root) if args.issues_fixture else None
    scan_id = args.scan_id or _scan_id()
    payload = _perform_github_discovery_scan(
        repo_root=repo_root,
        profile_path=profile_path,
        scan_id=scan_id,
        repos_fixture_path=repos_fixture,
        issues_fixture_path=issues_fixture,
    )
    if args.json_output:
        _print_json(payload)
        return 0

    print(f"scan_id={payload['scan_id']}")
    print(f"profile={payload['profile']['path']}")
    print(f"owner={payload['owner']['login']}")
    print(f"owner_type={payload['owner']['type']}")
    print(f"scan_json={payload['artifacts']['scan_json']}")
    print(f"summary_md={payload['artifacts']['summary_md']}")
    if payload["repos"]:
        top_repo = payload["repos"][0]["full_name"]
        print(f"top_repo={top_repo}")
        print(f"next=orp collaborate init --github-repo {top_repo}")
    if payload["issues"]:
        top_issue = payload["issues"][0]
        print(f"top_issue={top_issue['repo']}#{top_issue['number']}")
    return 0


def cmd_exchange_repo_synthesize(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    exchange_id = str(getattr(args, "exchange_id", "") or "").strip() or _exchange_id()
    source = _exchange_source_payload(repo_root, args)
    source_root = Path(str(source.get("local_path", "")).strip()).resolve()
    inventory = _exchange_inventory(source_root)
    relation = _exchange_relation(repo_root, source_root, inventory)
    suggested_focus = _exchange_suggested_focus(inventory, relation)
    paths = _exchange_paths(repo_root, exchange_id)

    payload = {
        "schema_version": EXCHANGE_REPORT_SCHEMA_VERSION,
        "kind": "exchange_report",
        "exchange_id": exchange_id,
        "generated_at_utc": _now_utc(),
        "current_project_root": str(repo_root),
        "source": source,
        "inventory": inventory,
        "relation": relation,
        "suggested_focus": suggested_focus,
        "artifacts": {
            "exchange_json": _path_for_state(paths["exchange_json"], repo_root),
            "summary_md": _path_for_state(paths["summary_md"], repo_root),
            "transfer_map_md": _path_for_state(paths["transfer_map_md"], repo_root),
        },
        "notes": [
            "Knowledge exchange is deeper than discovery scan output.",
            "Exchange artifacts are structured synthesis aids, not evidence by themselves.",
            "Local non-git directories can be bootstrapped into git when `--allow-git-init` is explicitly provided.",
        ],
    }
    _write_json(paths["exchange_json"], payload)
    _write_text(paths["summary_md"], _exchange_summary_markdown(payload))
    _write_text(paths["transfer_map_md"], _exchange_transfer_map_markdown(payload))

    result = {
        "ok": True,
        "exchange_id": exchange_id,
        "source": source,
        "inventory": inventory,
        "relation": relation,
        "suggested_focus": suggested_focus,
        "artifacts": payload["artifacts"],
        "schema_path": "spec/v1/exchange-report.schema.json",
    }
    if args.json_output:
        _print_json(result)
        return 0

    print(f"exchange_id={exchange_id}")
    print(f"source.mode={source.get('mode', '')}")
    print(f"source.local_path={source.get('local_path', '')}")
    print(f"source.git_present={str(bool(source.get('git_present'))).lower()}")
    print(f"source.git_initialized_by_orp={str(bool(source.get('git_initialized_by_orp'))).lower()}")
    print(f"artifacts.exchange_json={payload['artifacts']['exchange_json']}")
    print(f"artifacts.summary_md={payload['artifacts']['summary_md']}")
    print(f"artifacts.transfer_map_md={payload['artifacts']['transfer_map_md']}")
    return 0


def cmd_about(args: argparse.Namespace) -> int:
    payload = _about_payload()
    if args.json_output:
        _print_json(payload)
        return 0

    print(f"tool.name={payload['tool']['name']}")
    print(f"tool.package={payload['tool']['package']}")
    print(f"tool.version={payload['tool']['version']}")
    print(f"tool.agent_friendly={str(payload['tool']['agent_friendly']).lower()}")
    print(f"discovery.llms_txt={payload['discovery']['llms_txt']}")
    print(f"discovery.agent_integration={payload['discovery']['agent_integration']}")
    print(f"discovery.protocol={payload['discovery']['protocol']}")
    print(f"artifact.run_json={payload['artifacts']['run_json']}")
    print(f"artifact.packet_json={payload['artifacts']['packet_json']}")
    print(f"schema.config={payload['schemas']['config']}")
    print(f"schema.packet={payload['schemas']['packet']}")
    print(f"schema.kernel={payload['schemas']['kernel']}")
    print(f"schema.profile_pack={payload['schemas']['profile_pack']}")
    print(f"packs.count={len(payload['packs'])}")
    for pack in payload["packs"]:
        if not isinstance(pack, dict):
            continue
        print(f"pack.id={pack.get('id', '')}")
        print(f"pack.version={pack.get('version', '')}")
    return 0


def cmd_home(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload = _home_payload(repo_root, args.config)
    if args.json_output:
        _print_json(payload)
        return 0

    print(_render_home_screen(payload))
    return 0


def cmd_mode_list(args: argparse.Namespace) -> int:
    payload = {
        "ok": True,
        "schema_version": AGENT_MODE_REGISTRY_VERSION,
        "items": [_agent_mode_public_payload(mode) for mode in AGENT_MODES],
    }
    if args.json_output:
        _print_json(payload)
        return 0

    _print_pairs([("modes.count", len(payload["items"]))])
    for row in payload["items"]:
        print("---")
        _print_pairs(
            [
                ("mode.id", row["id"]),
                ("mode.label", row["label"]),
                ("mode.summary", row["summary"]),
                ("mode.activation_phrase", row["activation_phrase"]),
            ]
        )
    return 0


def cmd_mode_show(args: argparse.Namespace) -> int:
    mode = _agent_mode(getattr(args, "mode_ref", ""))
    payload = {
        "ok": True,
        "mode": _agent_mode_public_payload(mode),
    }
    if args.json_output:
        _print_json(payload)
        return 0

    mode_payload = payload["mode"]
    _print_pairs(
        [
            ("mode.id", mode_payload["id"]),
            ("mode.label", mode_payload["label"]),
            ("mode.summary", mode_payload["summary"]),
            ("mode.operator_reminder", mode_payload["operator_reminder"]),
            ("mode.activation_phrase", mode_payload["activation_phrase"]),
            ("mode.invocation_style", mode_payload["invocation_style"]),
            ("mode.nudge_card_count", mode_payload["nudge_card_count"]),
        ]
    )
    for key in ("when_to_use", "perspective_shifts", "principles", "ritual", "questions", "anti_patterns"):
        rows = mode_payload.get(key, [])
        if isinstance(rows, list) and rows:
            print(f"{key}:")
            for row in rows:
                print(f"- {row}")
    return 0


def cmd_mode_nudge(args: argparse.Namespace) -> int:
    mode = _agent_mode(getattr(args, "mode_ref", ""))
    payload = {
        "ok": True,
        **_agent_mode_nudge(mode, seed=str(getattr(args, "seed", "") or "").strip()),
    }
    if args.json_output:
        _print_json(payload)
        return 0

    _print_pairs(
        [
            ("mode.id", payload["mode"]["id"]),
            ("mode.label", payload["mode"]["label"]),
            ("mode.activation_phrase", payload["mode"]["activation_phrase"]),
            ("nudge.seed", payload["seed"]),
            ("nudge.card_index", payload["card_index"]),
            ("nudge.title", payload["card"]["title"]),
            ("nudge.prompt", payload["card"]["prompt"]),
            ("nudge.twist", payload["card"]["twist"]),
            ("nudge.release", payload["card"]["release"]),
        ]
    )
    print("nudge.micro_loop:")
    for row in payload["micro_loop"]:
        print(f"- {row}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    payload = _update_payload()
    if getattr(args, "yes", False):
        payload["apply"] = _apply_update(payload)

    if args.json_output:
        _print_json(payload)
        if getattr(args, "yes", False) and not bool((payload.get("apply") or {}).get("ok")):
            return 1
        return 0

    print(_render_update_report(payload))

    apply_payload = payload.get("apply")
    if isinstance(apply_payload, dict) and not bool(apply_payload.get("ok")):
        return 1
    return 0


def cmd_maintenance_check(args: argparse.Namespace) -> int:
    payload = _maintenance_check_payload(source="manual")
    if args.json_output:
        _print_json(payload)
        return 0 if payload.get("ok") else 1

    print(_render_maintenance_check_report(payload))
    return 0 if payload.get("ok") else 1


def cmd_maintenance_status(args: argparse.Namespace) -> int:
    payload = _maintenance_agent_status()
    if args.json_output:
        _print_json(payload)
        return 0

    print(_render_maintenance_status_report(payload))
    return 0


def cmd_maintenance_enable(args: argparse.Namespace) -> int:
    hour = int(getattr(args, "hour", 9))
    minute = int(getattr(args, "minute", 0))
    if hour < 0 or hour > 23:
        raise RuntimeError("--hour must be between 0 and 23.")
    if minute < 0 or minute > 59:
        raise RuntimeError("--minute must be between 0 and 59.")
    payload = _enable_maintenance_agent(hour=hour, minute=minute)
    if args.json_output:
        _print_json(payload)
        return 0 if payload.get("ok") else 1

    print(_render_maintenance_enable_report(payload))
    return 0 if payload.get("ok") else 1


def cmd_maintenance_disable(args: argparse.Namespace) -> int:
    payload = _disable_maintenance_agent()
    if args.json_output:
        _print_json(payload)
        return 0 if payload.get("ok") else 1

    print(_render_maintenance_disable_report(payload))
    return 0 if payload.get("ok") else 1


def cmd_schedule_add_codex(args: argparse.Namespace) -> int:
    payload = _create_schedule_codex_job(args)
    if args.json_output:
        _print_json(payload)
        return 0

    print(_render_schedule_add_report(payload))
    return 0


def cmd_schedule_list(args: argparse.Namespace) -> int:
    payload = _list_schedule_jobs_payload()
    if args.json_output:
        _print_json(payload)
        return 0

    print(_render_schedule_list_report(payload))
    return 0


def cmd_schedule_show(args: argparse.Namespace) -> int:
    payload = _show_schedule_job_payload(args.target)
    if args.json_output:
        _print_json(payload)
        return 0

    print(_render_schedule_show_report(payload))
    return 0


def cmd_schedule_run(args: argparse.Namespace) -> int:
    registry = _load_schedule_registry()
    _, job = _find_schedule_job_index(registry, args.target)
    payload = _run_schedule_job_once(job)
    if args.json_output:
        _print_json(payload)
        return 0 if payload.get("ok") else 1

    print(_render_schedule_run_report(payload))
    return 0 if payload.get("ok") else 1


def cmd_schedule_enable(args: argparse.Namespace) -> int:
    hour = getattr(args, "hour", None)
    minute = getattr(args, "minute", None)
    if hour is not None:
        hour = int(hour)
    if minute is not None:
        minute = int(minute)

    registry = _load_schedule_registry()
    _, job = _find_schedule_job_index(registry, args.target)
    payload = _enable_schedule_job(job, hour=hour, minute=minute)
    if args.json_output:
        _print_json(payload)
        return 0 if payload.get("ok") else 1

    print(_render_schedule_enable_report(payload))
    return 0 if payload.get("ok") else 1


def cmd_schedule_disable(args: argparse.Namespace) -> int:
    registry = _load_schedule_registry()
    _, job = _find_schedule_job_index(registry, args.target)
    payload = _disable_schedule_job(job)
    if args.json_output:
        _print_json(payload)
        return 0 if payload.get("ok") else 1

    print(_render_schedule_disable_report(payload))
    return 0 if payload.get("ok") else 1


def cmd_collaborate_workflows(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    payload = _collaboration_workflow_payload(repo_root)
    if args.json_output:
        _print_json(payload)
        return 0

    print(f"workspace_ready={'yes' if payload['workspace_ready'] else 'no'}")
    print(f"recommended_init_command={payload['recommended_init_command']}")
    for row in payload["workflows"]:
        print("---")
        print(f"workflow.id={row['id']}")
        print(f"workflow.profile={row['profile']}")
        print(f"workflow.config={row['config']}")
        print(f"workflow.config_exists={str(bool(row['config_exists'])).lower()}")
        print(f"workflow.description={row['description']}")
        print(f"workflow.gates={','.join(row['gate_ids'])}")
    return 0


def cmd_collaborate_gates(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    wf = _collaboration_workflow_map().get(args.workflow)
    if wf is None:
        raise RuntimeError(f"unknown collaboration workflow: {args.workflow}")

    config_name = str(wf["config"])
    config_path = (repo_root / config_name).resolve()
    payload = {
        "workflow": str(wf["id"]),
        "profile": str(wf["profile"]),
        "config": config_name,
        "config_exists": config_path.exists(),
        "description": str(wf["description"]),
        "gate_ids": list(wf["gate_ids"]),
        "recommended_run_command": f"orp collaborate run --workflow {wf['id']}",
    }
    if args.json_output:
        _print_json(payload)
        return 0

    print(f"workflow.id={payload['workflow']}")
    print(f"profile={payload['profile']}")
    print(f"config={payload['config']}")
    print(f"config_exists={str(bool(payload['config_exists'])).lower()}")
    print(f"description={payload['description']}")
    print(f"recommended_run_command={payload['recommended_run_command']}")
    print("gates=" + ",".join(payload["gate_ids"]))
    return 0


def cmd_collaborate_init(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    target_repo_root = Path(args.target_repo_root)
    if not target_repo_root.is_absolute():
        target_repo_root = (repo_root / target_repo_root).resolve()

    script_path = Path(__file__).resolve().parent.parent / "scripts" / "orp-pack-install.py"
    if not script_path.exists():
        raise RuntimeError(f"missing collaboration installer script: {script_path}")

    forwarded: list[str] = [
        "--pack-id",
        "issue-smashers",
        "--target-repo-root",
        str(target_repo_root),
    ]
    if args.workspace_root:
        forwarded.extend(["--var", f"ISSUE_SMASHERS_ROOT={args.workspace_root}"])
        forwarded.extend(["--var", f"ISSUE_SMASHERS_REPOS_DIR={args.workspace_root}/repos"])
        forwarded.extend(["--var", f"ISSUE_SMASHERS_WORKTREES_DIR={args.workspace_root}/worktrees"])
        forwarded.extend(["--var", f"ISSUE_SMASHERS_SCRATCH_DIR={args.workspace_root}/scratch"])
        forwarded.extend(["--var", f"ISSUE_SMASHERS_ARCHIVE_DIR={args.workspace_root}/archive"])
        forwarded.extend(
            ["--var", f"WATCHLIST_FILE={args.workspace_root}/analysis/ISSUE_SMASHERS_WATCHLIST.json"]
        )
        forwarded.extend(
            ["--var", f"STATUS_FILE={args.workspace_root}/analysis/ISSUE_SMASHERS_STATUS.md"]
        )
        forwarded.extend(["--var", f"WORKSPACE_RULES_FILE={args.workspace_root}/WORKSPACE_RULES.md"])
        forwarded.extend(["--var", f"DEFAULT_PR_BODY_FILE={args.workspace_root}/analysis/PR_DRAFT_BODY.md"])
    if args.github_repo:
        forwarded.extend(["--var", f"TARGET_GITHUB_REPO={args.github_repo}"])
    if args.github_author:
        forwarded.extend(["--var", f"TARGET_GITHUB_AUTHOR={args.github_author}"])
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

    proc = subprocess.run(
        [sys.executable, str(script_path), *forwarded],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    parsed = _parse_pack_install_output(proc.stdout)
    if proc.returncode == 0:
        _ensure_dirs(target_repo_root)

    payload = {
        "ok": proc.returncode == 0,
        "returncode": int(proc.returncode),
        "target_repo_root": str(target_repo_root),
        "workspace_root": args.workspace_root or "issue-smashers",
        "config": "orp.issue-smashers.yml",
        "feedback_config": "orp.issue-smashers-feedback-hardening.yml",
        "report": parsed.get("report", "orp.issue-smashers.pack-install-report.md"),
        "rendered": parsed.get("rendered", {}),
        "bootstrap": parsed.get("bootstrap", {}),
        "implementation": {
            "internal_pack_id": "issue-smashers",
        },
    }
    if proc.stderr.strip():
        payload["stderr"] = proc.stderr.strip()

    if args.json_output:
        _print_json(payload)
    else:
        if proc.returncode == 0:
            print(f"target_repo_root={target_repo_root}")
            print(f"workspace_root={payload['workspace_root']}")
            print(f"config={payload['config']}")
            print(f"feedback_config={payload['feedback_config']}")
            print(f"report={payload['report']}")
            print("next=orp collaborate workflows")
            print("next=orp collaborate run --workflow full_flow")
        else:
            _emit_subprocess_result(proc)
    return int(proc.returncode)


def cmd_collaborate_run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    wf = _collaboration_workflow_map().get(args.workflow)
    if wf is None:
        raise RuntimeError(f"unknown collaboration workflow: {args.workflow}")

    config_name = str(wf["config"])
    config_path = (repo_root / config_name).resolve()
    if not config_path.exists():
        raise RuntimeError(
            f"missing collaboration config: {config_name}. Run `orp collaborate init` first."
        )

    gate_args = argparse.Namespace(
        repo_root=str(repo_root),
        config=config_name,
        profile=str(wf["profile"]),
        run_id=args.run_id,
        json_output=bool(args.json_output),
    )
    return cmd_gate_run(gate_args)


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
    proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
    if args.json_output:
        result = _parse_pack_install_output(proc.stdout)
        result["ok"] = proc.returncode == 0
        result["returncode"] = int(proc.returncode)
        if proc.stderr.strip():
            result["stderr"] = proc.stderr.strip()
        _print_json(result)
    else:
        _emit_subprocess_result(proc)
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


def _coerce_scalar(value: str) -> Any:
    text = value.strip()
    if text == "":
        return ""
    lower = text.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except Exception:
            return text
    return text


def _insert_dotted_value(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = [part for part in dotted_key.split(".") if part]
    if not parts:
        return

    cur: dict[str, Any] = target
    for part in parts[:-1]:
        existing = cur.get(part)
        if not isinstance(existing, dict):
            existing = {}
            cur[part] = existing
        cur = existing

    leaf = parts[-1]
    existing = cur.get(leaf)
    if existing is None:
        cur[leaf] = value
        return
    if isinstance(existing, list):
        existing.append(value)
        return
    cur[leaf] = [existing, value]


def _parse_kv_tree(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        _insert_dotted_value(out, key.strip(), _coerce_scalar(value))
    return out


def _split_csv_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value]
    if not isinstance(value, str):
        return []
    text = value.strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _parse_pack_install_output(text: str) -> dict[str, Any]:
    payload = _parse_kv_tree(text)
    payload["included_components"] = _split_csv_value(payload.get("included_components", ""))
    return payload


def _parse_erdos_sync_output(text: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    selected_rows: list[dict[str, Any]] = []
    current_selected: dict[str, Any] | None = None

    for raw in (text or "").splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        coerced = _coerce_scalar(value)

        if key == "selected.count":
            payload["selected_count"] = coerced
            continue
        if key == "selected.missing":
            payload["selected_missing"] = _split_csv_value(coerced)
            continue
        if key.startswith("selected."):
            field = key.split(".", 1)[1]
            if field == "problem_id":
                if current_selected:
                    selected_rows.append(current_selected)
                current_selected = {}
            if current_selected is None:
                current_selected = {}
            current_selected[field] = coerced
            continue

        _insert_dotted_value(payload, key, coerced)

    if current_selected:
        selected_rows.append(current_selected)
    if selected_rows:
        payload["selected"] = selected_rows
    return payload


def _emit_subprocess_result(proc: subprocess.CompletedProcess[str]) -> None:
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")


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
    fetch_payload = _parse_kv_tree(proc.stdout)
    if proc.returncode != 0:
        if args.json_output:
            result: dict[str, Any] = {
                "ok": False,
                "returncode": int(proc.returncode),
                "fetch": fetch_payload,
            }
            if proc.stderr.strip():
                result["stderr"] = proc.stderr.strip()
            _print_json(result)
        else:
            _emit_subprocess_result(proc)
        return int(proc.returncode)

    if not args.install_target:
        if args.json_output:
            result = {
                "ok": True,
                "returncode": 0,
                "fetch": fetch_payload,
            }
            _print_json(result)
        else:
            _emit_subprocess_result(proc)
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

    proc_install = subprocess.run(install_cmd, cwd=str(repo_root), capture_output=True, text=True)
    if args.json_output:
        result = {
            "ok": proc_install.returncode == 0,
            "returncode": int(proc_install.returncode),
            "fetch": fetch_payload,
            "install": _parse_pack_install_output(proc_install.stdout),
        }
        if proc.stderr.strip():
            result["fetch_stderr"] = proc.stderr.strip()
        if proc_install.stderr.strip():
            result["install_stderr"] = proc_install.stderr.strip()
        _print_json(result)
    else:
        _emit_subprocess_result(proc)
        _emit_subprocess_result(proc_install)
    return int(proc_install.returncode)


def cmd_erdos_sync(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    _ensure_dirs(repo_root)
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
    proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
    result = _parse_erdos_sync_output(proc.stdout)
    if proc.returncode == 0:
        state_path = repo_root / "orp" / "state.json"
        state = _read_json(state_path)
        result["synced_at_utc"] = _now_utc()
        state["last_erdos_sync"] = result
        _write_json(state_path, state)

    if args.json_output:
        result["ok"] = proc.returncode == 0
        result["returncode"] = int(proc.returncode)
        if proc.stderr.strip():
            result["stderr"] = proc.stderr.strip()
        _print_json(result)
    else:
        _emit_subprocess_result(proc)
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

    epistemic = run.get("epistemic_status", {})
    if isinstance(epistemic, dict) and epistemic:
        lines.append("")
        lines.append("## Epistemic Status")
        lines.append("")
        lines.append(f"- overall: `{str(epistemic.get('overall', '')).strip()}`")
        lines.append(f"- starter_scaffold: `{str(bool(epistemic.get('starter_scaffold', False))).lower()}`")

        stub_gates = [str(x) for x in epistemic.get("stub_gates", []) if isinstance(x, str)]
        starter_gates = [
            str(x) for x in epistemic.get("starter_scaffold_gates", []) if isinstance(x, str)
        ]
        evidence_gates = [str(x) for x in epistemic.get("evidence_gates", []) if isinstance(x, str)]
        strongest_paths = [
            str(x) for x in epistemic.get("strongest_evidence_paths", []) if isinstance(x, str)
        ]
        notes = [str(x) for x in epistemic.get("notes", []) if isinstance(x, str)]

        lines.append(
            f"- stub_gates: `{', '.join(stub_gates) if stub_gates else '(none)'}`"
        )
        lines.append(
            f"- starter_scaffold_gates: `{', '.join(starter_gates) if starter_gates else '(none)'}`"
        )
        lines.append(
            f"- evidence_gates: `{', '.join(evidence_gates) if evidence_gates else '(none)'}`"
        )
        if strongest_paths:
            lines.append("- strongest_evidence_paths:")
            for path in strongest_paths:
                lines.append(f"  - `{path}`")
        if notes:
            lines.append("- notes:")
            for note in notes:
                lines.append(f"  - {note}")

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

    result = {
        "run_id": run_id,
        "run_json": _path_for_state(run_json_path, repo_root),
        "summary_md": _path_for_state(out_path, repo_root),
    }
    if args.print_stdout:
        result["summary_markdown"] = summary_md

    if args.json_output:
        _print_json(result)
    else:
        print(f"run_id={run_id}")
        print(f"run_json={_path_for_state(run_json_path, repo_root)}")
        print(f"summary_md={_path_for_state(out_path, repo_root)}")
        if args.print_stdout:
            print("---")
            print(summary_md)
    return 0


def cmd_auth_login(args: argparse.Namespace) -> int:
    session = _load_hosted_session()
    base_url = _resolve_hosted_base_url(args, session)

    email = str(getattr(args, "email", "")).strip() or str(session.get("email", "")).strip()
    if not email:
        email = _prompt_value("Email")
    if not email:
        raise RuntimeError("Email is required.")

    password_from_stdin = bool(getattr(args, "password_stdin", False))
    password = str(getattr(args, "password", "")).strip()
    if password_from_stdin and password:
        raise RuntimeError("Use either --password or --password-stdin, not both.")
    if password_from_stdin:
        password = _read_value_from_stdin()
    if not password:
        password = _prompt_value("Password", secret=True)
    if not password:
        raise RuntimeError("Password is required.")

    payload = _request_hosted_json(
        base_url=base_url,
        path="/api/auth/device-login",
        method="POST",
        body={
            "email": email,
            "password": password,
        },
    )
    pending = payload.get("pendingVerification")
    expires_at = str(payload.get("expiresAt", "")).strip()
    token = str(payload.get("token", "")).strip()
    user = payload.get("user") if isinstance(payload.get("user"), dict) else None
    if user is None and any(key in payload for key in ("userId", "email", "name")):
        user = {
            "id": str(payload.get("userId", "")).strip(),
            "email": str(payload.get("email", email)).strip() or email,
            "name": str(payload.get("name", "")).strip(),
        }

    if isinstance(pending, dict) or expires_at:
        pending_payload = pending if isinstance(pending, dict) else {"expiresAt": expires_at}
        updated = {
            **session,
            "base_url": base_url,
            "email": email,
            "token": "",
            "user": None,
            "pending_verification": pending_payload,
        }
        _save_hosted_session(updated)

        result = {
            "base_url": base_url,
            "email": _mask_email(email),
            "expires_at": str(pending_payload.get("expiresAt", "")).strip(),
            "pending_verification": True,
        }
    elif token and user is not None:
        updated = {
            **session,
            "base_url": base_url,
            "email": email,
            "token": token,
            "user": user,
            "pending_verification": None,
        }
        _save_hosted_session(updated)

        result = {
            "base_url": base_url,
            "email": str(user.get("email", email)).strip() or email,
            "user_id": str(user.get("id", "")).strip(),
            "connected": True,
        }
    else:
        raise RuntimeError(
            "Hosted ORP login did not return pending verification details or a usable session."
        )

    if args.json_output:
        _print_json(result)
    else:
        if result.get("pending_verification") is True:
            _print_pairs(
                [
                    ("base_url", result["base_url"]),
                    ("email", result["email"]),
                    ("expires_at", result["expires_at"]),
                    ("pending_verification", "true"),
                ]
            )
        else:
            _print_pairs(
                [
                    ("base_url", result["base_url"]),
                    ("email", result["email"]),
                    ("user_id", result["user_id"]),
                    ("connected", "true"),
                ]
            )
    return 0


def cmd_auth_verify(args: argparse.Namespace) -> int:
    session = _load_hosted_session()
    base_url = _resolve_hosted_base_url(args, session)

    email = str(getattr(args, "email", "")).strip() or str(session.get("email", "")).strip()
    if not email:
        email = _prompt_value("Email")
    if not email:
        raise RuntimeError("Email is required.")

    code_from_stdin = bool(getattr(args, "code_stdin", False))
    code = str(getattr(args, "code", "")).strip()
    if code_from_stdin and code:
        raise RuntimeError("Use either --code or --code-stdin, not both.")
    if code_from_stdin:
        code = _read_value_from_stdin()
    if not code:
        code = _prompt_value("Verification code")
    if not code:
        raise RuntimeError("Verification code is required.")

    payload = _request_hosted_json(
        base_url=base_url,
        path="/api/auth/device-verify",
        method="POST",
        body={
            "email": email,
            "code": code,
        },
    )
    token = str(payload.get("token", "")).strip()
    user = payload.get("user") if isinstance(payload.get("user"), dict) else None
    if user is None and any(key in payload for key in ("userId", "email", "name")):
        user = {
            "id": str(payload.get("userId", "")).strip(),
            "email": str(payload.get("email", email)).strip() or email,
            "name": str(payload.get("name", "")).strip(),
        }
    if not token or user is None:
        raise RuntimeError("Hosted ORP verify did not return a usable session.")

    updated = {
        **session,
        "base_url": base_url,
        "email": email,
        "token": token,
        "user": user,
        "pending_verification": None,
    }
    _save_hosted_session(updated)

    result = {
        "base_url": base_url,
        "email": str(user.get("email", email)).strip() or email,
        "user_id": str(user.get("id", "")).strip(),
        "connected": True,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("base_url", result["base_url"]),
                ("email", result["email"]),
                ("user_id", result["user_id"]),
                ("connected", "true"),
            ]
        )
    return 0


def cmd_auth_logout(args: argparse.Namespace) -> int:
    session = _load_hosted_session()
    updated = {
        "base_url": _normalize_base_url(session.get("base_url", "")),
        "email": str(session.get("email", "")).strip(),
        "token": "",
        "user": None,
        "pending_verification": None,
    }
    _save_hosted_session(updated)
    result = {
        "base_url": updated["base_url"],
        "connected": False,
        "ok": True,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("base_url", result["base_url"]),
                ("connected", "false"),
                ("ok", "true"),
            ]
        )
    return 0


def _load_current_project_scope(repo_root: Path, *, required: bool) -> dict[str, str]:
    project_link = _read_link_project(repo_root)
    if not project_link:
        if required:
            raise RuntimeError(
                "No local linked project found. Run `orp link project bind --idea-id <idea-id>` first or pass --world-id/--idea-id explicitly."
            )
        return {}

    world_id = str(project_link.get("world_id", "")).strip()
    idea_id = str(project_link.get("idea_id", "")).strip()
    if not world_id and not idea_id:
        if required:
            raise RuntimeError(
                "The current linked project is missing world and idea identifiers. Rebind the project or pass --world-id/--idea-id explicitly."
            )
        return {}

    return {
        "world_id": world_id,
        "idea_id": idea_id,
        "idea_title": str(project_link.get("idea_title", "")).strip(),
        "world_name": str(project_link.get("world_name", "")).strip(),
    }


def _resolve_secret_scope_from_args(
    args: argparse.Namespace,
    *,
    require_scope: bool = False,
    fallback_to_current_project: bool = False,
) -> tuple[str, str]:
    repo_root = Path(str(getattr(args, "repo_root", ".") or ".")).resolve()
    world_id = str(getattr(args, "world_id", "") or "").strip()
    idea_id = str(getattr(args, "idea_id", "") or "").strip()
    current_project = bool(getattr(args, "current_project", False))

    if not world_id and not idea_id and (current_project or fallback_to_current_project):
        scope = _load_current_project_scope(repo_root, required=current_project)
        if scope:
            world_id = str(scope.get("world_id", "")).strip()
            idea_id = str(scope.get("idea_id", "")).strip()

    if require_scope and not world_id and not idea_id:
        raise RuntimeError("Provide --world-id, --idea-id, or --current-project.")

    return world_id, idea_id


def _resolve_secret_value_arg(args: argparse.Namespace, *, required: bool) -> tuple[bool, str]:
    value_from_stdin = bool(getattr(args, "value_stdin", False))
    raw_value = getattr(args, "value", None)
    if value_from_stdin and raw_value is not None:
        raise RuntimeError("Use either --value or --value-stdin, not both.")

    provided = raw_value is not None or value_from_stdin
    value = str(raw_value).strip() if raw_value is not None else ""
    if value_from_stdin:
        value = _read_value_from_stdin()

    if required and not value:
        value = _prompt_value("Secret value", secret=True)
        provided = provided or bool(value)

    if required and not value:
        raise RuntimeError("Secret value is required.")

    return provided, value


def _build_secret_binding_payload_from_args(
    args: argparse.Namespace,
    *,
    fallback_to_current_project: bool = False,
) -> dict[str, Any] | None:
    world_id, idea_id = _resolve_secret_scope_from_args(
        args,
        require_scope=False,
        fallback_to_current_project=fallback_to_current_project,
    )
    purpose = str(getattr(args, "purpose", "") or "").strip()
    primary = bool(getattr(args, "primary", False))

    if not world_id and not idea_id:
        if purpose or primary or bool(getattr(args, "current_project", False)):
            raise RuntimeError("Provide --world-id, --idea-id, or --current-project to attach binding metadata.")
        return None

    binding: dict[str, Any] = {}
    if world_id:
        binding["worldId"] = world_id
    if idea_id:
        binding["ideaId"] = idea_id
    if purpose:
        binding["purpose"] = purpose
    if primary:
        binding["isPrimary"] = True
    return binding


def _request_secret_payload(
    args: argparse.Namespace,
    *,
    path: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session = _require_hosted_session(args)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=path,
        method=method,
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Hosted ORP returned an invalid secret payload.")
    return payload


def _resolve_secret_from_hosted(
    args: argparse.Namespace,
    *,
    secret_ref: str = "",
    provider: str = "",
    reveal: bool = False,
) -> dict[str, Any]:
    world_id, idea_id = _resolve_secret_scope_from_args(
        args,
        require_scope=not bool(secret_ref),
        fallback_to_current_project=not bool(secret_ref),
    )

    body: dict[str, Any] = {
        "reveal": reveal,
    }
    if secret_ref:
        body["id" if _looks_like_uuid(secret_ref) else "alias"] = secret_ref
    elif provider:
        body["provider"] = provider
    else:
        raise RuntimeError("Provide a secret reference or --provider to resolve a secret.")
    if world_id:
        body["worldId"] = world_id
    if idea_id:
        body["ideaId"] = idea_id

    payload = _request_secret_payload(
        args,
        path="/api/cli/secrets/resolve",
        method="POST",
        body=body,
    )
    secret = payload.get("secret") if isinstance(payload.get("secret"), dict) else {}
    binding = payload.get("binding") if isinstance(payload.get("binding"), dict) else None
    return {
        "ok": bool(payload.get("ok", True)),
        "secret": secret,
        "binding": binding,
        "value": payload.get("value"),
        "matched_by": str(payload.get("matchedBy", "")).strip(),
        "source": "hosted",
    }


def _resolve_secret_from_keychain(
    args: argparse.Namespace,
    *,
    secret_ref: str = "",
    provider: str = "",
    reveal: bool = False,
) -> dict[str, Any] | None:
    world_id, idea_id = _resolve_secret_scope_from_args(
        args,
        require_scope=False,
        fallback_to_current_project=not bool(secret_ref),
    )
    entry = _select_keychain_entry(
        secret_ref=secret_ref,
        provider=provider,
        world_id=world_id,
        idea_id=idea_id,
    )
    if entry is None:
        return None
    bindings = entry.get("bindings") if isinstance(entry.get("bindings"), list) else []
    binding = next(
        (
            row
            for row in bindings
            if isinstance(row, dict) and _binding_matches_secret_scope(row, world_id, idea_id)
        ),
        None,
    )
    secret = _secret_payload_from_keychain_entry(entry)
    matched_by = "keychain+alias" if secret_ref else "keychain+provider"
    if (world_id or idea_id) and binding is not None:
        matched_by += "+project"
    result = {
        "ok": True,
        "secret": secret,
        "binding": _binding_payload_from_keychain_summary(binding) if isinstance(binding, dict) else None,
        "value": _read_keychain_secret_value(entry) if reveal else None,
        "matched_by": matched_by,
        "source": "keychain",
    }
    return result


def _secret_bindings(secret: dict[str, Any]) -> list[dict[str, Any]]:
    rows = secret.get("bindings")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _print_secret_binding_rows(bindings: list[dict[str, Any]]) -> None:
    for row in bindings:
        print("---")
        _print_pairs(
            [
                ("binding.id", str(row.get("id", "")).strip()),
                ("binding.world_id", str(row.get("worldId", "")).strip()),
                ("binding.world_name", str(row.get("worldName", "")).strip()),
                ("binding.idea_id", str(row.get("ideaId", "")).strip()),
                ("binding.idea_title", str(row.get("ideaTitle", "")).strip()),
                ("binding.project_root", str(row.get("projectRoot", "")).strip()),
                ("binding.purpose", str(row.get("purpose", "")).strip()),
                ("binding.primary", str(bool(row.get("isPrimary", False))).lower()),
            ]
        )


def _print_secret_human(
    secret: dict[str, Any],
    *,
    include_bindings: bool = False,
    binding: dict[str, Any] | None = None,
    value: str | None = None,
    matched_by: str = "",
    source: str = "",
) -> None:
    bindings = _secret_bindings(secret)
    _print_pairs(
        [
            ("secret.id", str(secret.get("id", "")).strip()),
            ("secret.alias", str(secret.get("alias", "")).strip()),
            ("secret.label", str(secret.get("label", "")).strip()),
            ("secret.provider", str(secret.get("provider", "")).strip()),
            ("secret.kind", str(secret.get("kind", "")).strip()),
            ("secret.env_var_name", str(secret.get("envVarName", "")).strip()),
            ("secret.preview", str(secret.get("valuePreview", "")).strip()),
            ("secret.version", str(secret.get("valueVersion", "")).strip()),
            ("secret.status", str(secret.get("status", "")).strip()),
            ("secret.binding_count", len(bindings)),
            ("secret.last_used_at", str(secret.get("lastUsedAt", "")).strip()),
            ("secret.rotated_at", str(secret.get("rotatedAt", "")).strip()),
            ("secret.updated_at", str(secret.get("updatedAt", "")).strip()),
        ]
    )
    if matched_by:
        print(f"secret.matched_by={matched_by}")
    if source:
        print(f"secret.source={source}")
    if binding:
        _print_pairs(
            [
                ("binding.id", str(binding.get("id", "")).strip()),
                ("binding.world_id", str(binding.get("worldId", "")).strip()),
                ("binding.idea_id", str(binding.get("ideaId", "")).strip()),
                ("binding.purpose", str(binding.get("purpose", "")).strip()),
                ("binding.primary", str(bool(binding.get("isPrimary", False))).lower()),
            ]
        )
    if value is not None:
        print(f"secret.value={value}")
    if include_bindings and bindings:
        _print_secret_binding_rows(bindings)


def _keychain_service_for_secret(secret: dict[str, Any]) -> str:
    provider = str(secret.get("provider", "")).strip() or "unknown"
    return f"orp.secret.{provider}"


def _keychain_account_for_secret(secret: dict[str, Any]) -> str:
    alias = str(secret.get("alias", "")).strip()
    if alias:
        return alias
    return str(secret.get("id", "")).strip()


def _keychain_label_for_secret(secret: dict[str, Any]) -> str:
    label = str(secret.get("label", "")).strip()
    if label:
        return label
    alias = str(secret.get("alias", "")).strip()
    if alias:
        return alias
    return str(secret.get("id", "")).strip() or "ORP Secret"


def _keychain_comment_for_secret(secret: dict[str, Any]) -> str:
    payload = {
        "secret_id": str(secret.get("id", "")).strip(),
        "alias": str(secret.get("alias", "")).strip(),
        "provider": str(secret.get("provider", "")).strip(),
        "env_var_name": str(secret.get("envVarName", "")).strip(),
    }
    return json.dumps(payload, sort_keys=True)


def _normalize_secret_binding_summary(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "binding_id": str(binding.get("id", "")).strip(),
        "world_id": str(binding.get("worldId", "")).strip(),
        "idea_id": str(binding.get("ideaId", "")).strip(),
        "purpose": str(binding.get("purpose", "")).strip(),
        "primary": bool(binding.get("isPrimary", False)),
    }


def _binding_payload_from_keychain_summary(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(binding.get("binding_id", "")).strip(),
        "worldId": str(binding.get("world_id", "")).strip(),
        "ideaId": str(binding.get("idea_id", "")).strip(),
        "purpose": str(binding.get("purpose", "")).strip(),
        "isPrimary": bool(binding.get("primary", False)),
    }


def _merge_secret_binding_summaries(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in [*existing, *incoming]:
        if not isinstance(row, dict):
            continue
        normalized = _normalize_secret_binding_summary(row)
        key = (
            normalized["binding_id"],
            normalized["world_id"],
            normalized["idea_id"],
            normalized["purpose"],
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


def _build_keychain_registry_entry(
    secret: dict[str, Any],
    *,
    binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bindings = [_normalize_secret_binding_summary(row) for row in _secret_bindings(secret)]
    if binding:
        bindings = _merge_secret_binding_summaries(bindings, [binding])
    return {
        "secret_id": str(secret.get("id", "")).strip(),
        "alias": str(secret.get("alias", "")).strip(),
        "label": str(secret.get("label", "")).strip(),
        "provider": str(secret.get("provider", "")).strip(),
        "kind": str(secret.get("kind", "")).strip(),
        "env_var_name": str(secret.get("envVarName", "")).strip(),
        "status": str(secret.get("status", "")).strip(),
        "value_version": str(secret.get("valueVersion", "")).strip(),
        "value_preview": str(secret.get("valuePreview", "")).strip(),
        "keychain_service": _keychain_service_for_secret(secret),
        "keychain_account": _keychain_account_for_secret(secret),
        "keychain_label": _keychain_label_for_secret(secret),
        "bindings": bindings,
        "last_synced_at_utc": _now_utc(),
    }


def _secret_payload_from_keychain_entry(entry: dict[str, Any]) -> dict[str, Any]:
    bindings = entry.get("bindings") if isinstance(entry.get("bindings"), list) else []
    return {
        "id": str(entry.get("secret_id", "")).strip(),
        "alias": str(entry.get("alias", "")).strip(),
        "label": str(entry.get("label", "")).strip(),
        "provider": str(entry.get("provider", "")).strip(),
        "kind": str(entry.get("kind", "")).strip(),
        "envVarName": str(entry.get("env_var_name", "")).strip(),
        "status": str(entry.get("status", "")).strip(),
        "valueVersion": str(entry.get("value_version", "")).strip(),
        "valuePreview": str(entry.get("value_preview", "")).strip(),
        "bindings": [
            _binding_payload_from_keychain_summary(row)
            for row in bindings
            if isinstance(row, dict)
        ],
    }


def _upsert_keychain_secret_registry_entry(entry: dict[str, Any]) -> dict[str, Any]:
    registry = _load_keychain_secret_registry()
    items = registry.get("items") if isinstance(registry.get("items"), list) else []
    secret_id = str(entry.get("secret_id", "")).strip()
    service = str(entry.get("keychain_service", "")).strip()
    account = str(entry.get("keychain_account", "")).strip()
    next_items: list[dict[str, Any]] = []
    existing_entry: dict[str, Any] | None = None
    for row in items:
        if not isinstance(row, dict):
            continue
        row_secret_id = str(row.get("secret_id", "")).strip()
        row_service = str(row.get("keychain_service", "")).strip()
        row_account = str(row.get("keychain_account", "")).strip()
        if (secret_id and row_secret_id == secret_id) or (service and account and row_service == service and row_account == account):
            existing_entry = row
            continue
        next_items.append(row)
    merged = {
        **(existing_entry or {}),
        **entry,
    }
    merged["bindings"] = _merge_secret_binding_summaries(
        existing_entry.get("bindings", []) if isinstance(existing_entry, dict) else [],
        entry.get("bindings", []) if isinstance(entry.get("bindings"), list) else [],
    )
    next_items.append(merged)
    registry["items"] = sorted(
        next_items,
        key=lambda row: (
            str(row.get("provider", "")).strip(),
            str(row.get("alias", "")).strip() or str(row.get("secret_id", "")).strip(),
        ),
    )
    _save_keychain_secret_registry(registry)
    return merged


def _list_keychain_registry_entries(
    *,
    secret_ref: str = "",
    provider: str = "",
    world_id: str = "",
    idea_id: str = "",
) -> list[dict[str, Any]]:
    registry = _load_keychain_secret_registry()
    items = registry.get("items") if isinstance(registry.get("items"), list) else []
    filtered: list[dict[str, Any]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        alias = str(row.get("alias", "")).strip()
        secret_id = str(row.get("secret_id", "")).strip()
        row_provider = str(row.get("provider", "")).strip()
        if secret_ref and secret_ref not in {alias, secret_id}:
            continue
        if provider and row_provider != provider:
            continue
        if world_id or idea_id:
            bindings = row.get("bindings") if isinstance(row.get("bindings"), list) else []
            if not any(
                isinstance(binding, dict) and _binding_matches_secret_scope(binding, world_id, idea_id)
                for binding in bindings
            ):
                continue
        filtered.append(row)
    return sorted(
        filtered,
        key=lambda row: (
            str(row.get("provider", "")).strip(),
            str(row.get("alias", "")).strip() or str(row.get("secret_id", "")).strip(),
        ),
    )


def _binding_matches_secret_scope(binding: dict[str, Any], world_id: str, idea_id: str) -> bool:
    binding_world_id = str(binding.get("world_id", "")).strip()
    binding_idea_id = str(binding.get("idea_id", "")).strip()
    if world_id and binding_world_id != world_id:
        return False
    if idea_id and binding_idea_id != idea_id:
        return False
    return True


def _select_keychain_entry(
    *,
    secret_ref: str,
    provider: str,
    world_id: str,
    idea_id: str,
) -> dict[str, Any] | None:
    registry = _load_keychain_secret_registry()
    items = registry.get("items") if isinstance(registry.get("items"), list) else []
    if secret_ref:
        for row in items:
            if not isinstance(row, dict):
                continue
            alias = str(row.get("alias", "")).strip()
            secret_id = str(row.get("secret_id", "")).strip()
            if secret_ref == alias or secret_ref == secret_id:
                return row
        return None

    candidates = [
        row
        for row in items
        if isinstance(row, dict) and str(row.get("provider", "")).strip() == provider
    ]
    if world_id or idea_id:
        scoped: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for row in candidates:
            bindings = row.get("bindings") if isinstance(row.get("bindings"), list) else []
            for binding in bindings:
                if isinstance(binding, dict) and _binding_matches_secret_scope(binding, world_id, idea_id):
                    scoped.append((row, binding))
                    break
        if len(scoped) == 1:
            return scoped[0][0]
        primary_scoped = [row for row, binding in scoped if bool(binding.get("primary", False))]
        if len(primary_scoped) == 1:
            return primary_scoped[0]
        if len(scoped) > 1:
            raise RuntimeError("Multiple local Keychain secrets match this provider and project scope.")
        return None

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise RuntimeError("Multiple local Keychain secrets match this provider. Narrow the request with an alias or project scope.")
    return None


def _read_keychain_secret_value(entry: dict[str, Any]) -> str:
    service = str(entry.get("keychain_service", "")).strip()
    account = str(entry.get("keychain_account", "")).strip()
    if not service or not account:
        raise RuntimeError("Local Keychain secret entry is missing its service/account coordinates.")
    proc = _run_keychain_command(
        ["find-generic-password", "-s", service, "-a", account, "-w"],
    )
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "macOS Keychain lookup failed."
        raise RuntimeError(message)
    return proc.stdout.rstrip("\n")


def _store_keychain_secret_value(secret: dict[str, Any], value: str) -> dict[str, str]:
    service = _keychain_service_for_secret(secret)
    account = _keychain_account_for_secret(secret)
    label = _keychain_label_for_secret(secret)
    comment = _keychain_comment_for_secret(secret)
    proc = _run_keychain_command(
        [
            "add-generic-password",
            "-a",
            account,
            "-s",
            service,
            "-D",
            "ORP Secret",
            "-j",
            comment,
            "-l",
            label,
            "-U",
            "-w",
            value,
        ]
    )
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "macOS Keychain write failed."
        raise RuntimeError(message)
    return {
        "keychain_service": service,
        "keychain_account": account,
        "keychain_label": label,
    }


def _sync_secret_to_keychain(
    secret: dict[str, Any],
    *,
    value: str,
    binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    keychain_coordinates = _store_keychain_secret_value(secret, value)
    entry = _build_keychain_registry_entry(secret, binding=binding)
    entry.update(keychain_coordinates)
    return _upsert_keychain_secret_registry_entry(entry)


def _try_get_secret_by_ref(args: argparse.Namespace, secret_ref: str) -> dict[str, Any] | None:
    ref = str(secret_ref or "").strip()
    if not ref:
        return None
    try:
        payload = _request_secret_payload(
            args,
            path=f"/api/cli/secrets/{urlparse.quote(ref)}",
        )
    except HostedApiError as exc:
        if "status=404" in str(exc):
            return None
        raise
    secret = payload.get("secret") if isinstance(payload.get("secret"), dict) else payload
    if not isinstance(secret, dict):
        raise RuntimeError("Hosted ORP returned an invalid secret record.")
    return secret


def _find_secret_binding(secret: dict[str, Any], desired_binding: dict[str, Any] | None) -> dict[str, Any] | None:
    if not desired_binding:
        return None
    desired_world_id = str(desired_binding.get("worldId", "")).strip()
    desired_idea_id = str(desired_binding.get("ideaId", "")).strip()
    for row in _secret_bindings(secret):
        world_id = str(row.get("worldId", "")).strip()
        idea_id = str(row.get("ideaId", "")).strip()
        if desired_world_id and world_id != desired_world_id:
            continue
        if desired_idea_id and idea_id != desired_idea_id:
            continue
        return row
    return None


def _validate_existing_secret_for_ensure(secret: dict[str, Any], args: argparse.Namespace) -> None:
    desired_provider = str(getattr(args, "provider", "") or "").strip()
    actual_provider = str(secret.get("provider", "")).strip()
    if desired_provider and actual_provider and desired_provider != actual_provider:
        raise RuntimeError(
            f"Secret alias already exists with provider '{actual_provider}', not '{desired_provider}'."
        )


def _create_secret_binding_for_ensure(
    args: argparse.Namespace,
    secret: dict[str, Any],
    desired_binding: dict[str, Any],
) -> dict[str, Any]:
    alias = str(secret.get("alias", "")).strip()
    if not alias:
        raise RuntimeError("Existing secret is missing an alias and cannot be bound safely.")
    body = dict(desired_binding)
    body["secretAlias"] = alias
    payload = _request_secret_payload(
        args,
        path="/api/cli/secrets/bindings",
        method="POST",
        body=body,
    )
    binding = payload.get("binding") if isinstance(payload.get("binding"), dict) else payload
    if not isinstance(binding, dict):
        raise RuntimeError("Hosted ORP returned an invalid binding record.")
    return binding


def _resolve_secret_for_ensure(
    args: argparse.Namespace,
    secret: dict[str, Any],
    desired_binding: dict[str, Any] | None,
) -> dict[str, Any]:
    alias = str(secret.get("alias", "")).strip()
    secret_id = str(secret.get("id", "")).strip()
    body: dict[str, Any] = {
        "reveal": True,
    }
    if alias:
        body["alias"] = alias
    elif secret_id:
        body["id"] = secret_id
    else:
        raise RuntimeError("Secret is missing both alias and id and cannot be resolved.")
    if desired_binding:
        world_id = str(desired_binding.get("worldId", "")).strip()
        idea_id = str(desired_binding.get("ideaId", "")).strip()
        if world_id:
            body["worldId"] = world_id
        if idea_id:
            body["ideaId"] = idea_id
    payload = _request_secret_payload(
        args,
        path="/api/cli/secrets/resolve",
        method="POST",
        body=body,
    )
    resolved_secret = payload.get("secret") if isinstance(payload.get("secret"), dict) else secret
    binding = payload.get("binding") if isinstance(payload.get("binding"), dict) else None
    return {
        "secret": resolved_secret if isinstance(resolved_secret, dict) else secret,
        "binding": binding,
        "value": payload.get("value"),
        "matched_by": str(payload.get("matchedBy", "")).strip(),
    }


def cmd_whoami(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    base_url = _resolve_hosted_base_url(args, session)
    payload = _request_hosted_json(
        base_url=base_url,
        path="/api/cli/me",
        token=str(session.get("token", "")).strip(),
    )
    user = payload.get("user") if isinstance(payload.get("user"), dict) else payload
    if not isinstance(user, dict):
        raise RuntimeError("Hosted ORP did not return a user payload.")

    result = {
        "base_url": base_url,
        "user_id": str(user.get("id", "")).strip(),
        "email": str(user.get("email", "")).strip(),
        "name": str(user.get("name", "")).strip(),
        "connected": True,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("base_url", result["base_url"]),
                ("user_id", result["user_id"]),
                ("email", result["email"]),
                ("name", result["name"]),
                ("connected", "true"),
            ]
        )
    return 0


def cmd_ideas_list(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    params: list[str] = []
    if int(args.limit) > 0:
        params.append(f"limit={int(args.limit)}")
    cursor = str(getattr(args, "cursor", "")).strip()
    if cursor:
        params.append(f"cursor={urlparse.quote(cursor)}")
    sort_value = str(getattr(args, "sort", "")).strip()
    if sort_value:
        params.append(f"sort={urlparse.quote(sort_value)}")
    if bool(getattr(args, "deleted", False)):
        params.append("deleted=1")
    query = f"?{'&'.join(params)}" if params else ""

    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas{query}",
        token=str(session.get("token", "")).strip(),
    )
    ideas = payload.get("ideas") if isinstance(payload.get("ideas"), list) else None
    if ideas is None and isinstance(payload.get("items"), list):
        ideas = payload.get("items")
    cursor_value = payload.get("cursor")
    next_cursor = str(cursor_value).strip() if cursor_value is not None else ""
    if not next_cursor:
        next_cursor_value = payload.get("nextCursor")
        next_cursor = str(next_cursor_value).strip() if next_cursor_value is not None else ""
    has_more = payload.get("hasMore")
    if isinstance(has_more, bool):
        has_more_value = has_more
    else:
        has_more_value = bool(next_cursor)
    result = {
        "ideas": ideas or [],
        "cursor": next_cursor,
        "has_more": has_more_value,
        "sort": str(payload.get("sort", "")).strip() or sort_value or "updated_desc",
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("ideas.count", len(result["ideas"])),
                ("cursor", result["cursor"]),
                ("has_more", str(result["has_more"]).lower()),
                ("sort", result["sort"]),
            ]
        )
        for row in result["ideas"]:
            if not isinstance(row, dict):
                continue
            print("---")
            _print_pairs(
                [
                    ("idea.id", str(row.get("id", "")).strip()),
                    ("idea.title", str(row.get("title", "")).strip()),
                    ("idea.visibility", str(row.get("visibility", "")).strip()),
                    ("idea.updated_at", str(row.get("updatedAt", "")).strip()),
                ]
            )
    return 0


def _workspace_value(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record:
            return record.get(key)
    return None


def _workspace_text(record: dict[str, Any], *keys: str) -> str:
    value = _workspace_value(record, *keys)
    if value is None:
        return ""
    return str(value).strip()


def _workspace_object(record: dict[str, Any], *keys: str) -> dict[str, Any]:
    value = _workspace_value(record, *keys)
    return value if isinstance(value, dict) else {}


def _workspace_list(record: dict[str, Any], *keys: str) -> list[Any]:
    value = _workspace_value(record, *keys)
    return value if isinstance(value, list) else []


def _workspace_tab_rows(workspace: dict[str, Any]) -> list[dict[str, Any]]:
    state = _workspace_object(workspace, "state")
    tabs = _workspace_list(state, "tabs")
    if tabs:
        return [row for row in tabs if isinstance(row, dict)]
    return [row for row in _workspace_list(workspace, "tabs") if isinstance(row, dict)]


def _workspace_capture_context(workspace: dict[str, Any]) -> dict[str, Any]:
    state = _workspace_object(workspace, "state")
    return _workspace_object(state, "capture_context", "captureContext")


def _normalize_remote_workspace_payload(payload: dict[str, Any]) -> dict[str, Any]:
    workspace = payload.get("workspace") if isinstance(payload.get("workspace"), dict) else payload
    if not isinstance(workspace, dict):
        raise RuntimeError("Hosted ORP returned an invalid workspace payload.")

    normalized = dict(workspace)
    state = _workspace_object(normalized, "state")
    tabs = _workspace_tab_rows(normalized)
    if tabs:
        state = dict(state)
        state["tabs"] = tabs
        normalized["state"] = state

    return {
        "ok": bool(payload.get("ok", True)),
        "workspace": normalized,
    }


def _workspace_manifest_from_notes(notes: Any) -> dict[str, Any] | None:
    text = str(notes or "")
    if not text.strip():
        return None
    match = re.search(r"```orp-workspace\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if not match:
        return None
    raw = str(match.group(1) or "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _workspace_path_basename(project_root: Any) -> str:
    text = str(project_root or "").strip().rstrip("/")
    if not text:
        return ""
    return Path(text).name or text.split("/")[-1]


def _workspace_bridge_tab_title(
    raw_title: Any,
    project_root: Any,
    *,
    index: int,
    seen_titles: dict[str, int],
) -> str:
    base = str(raw_title or "").strip() or _workspace_path_basename(project_root) or f"tab-{index + 1}"
    count = seen_titles.get(base, 0) + 1
    seen_titles[base] = count
    if count == 1:
        return base
    return f"{base} ({count})"


def _workspace_bridge_tabs_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    tabs = manifest.get("tabs")
    if not isinstance(tabs, list):
        return []
    seen_titles: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(tabs):
        if not isinstance(raw, dict):
            continue
        project_root = str(
            raw.get("path")
            or raw.get("project_root")
            or raw.get("projectRoot")
            or ""
        ).strip()
        if not project_root:
            continue
        title = _workspace_bridge_tab_title(
            raw.get("title") or raw.get("repo_label") or raw.get("repoLabel"),
            project_root,
            index=index,
            seen_titles=seen_titles,
        )
        resume_command = str(raw.get("resumeCommand") or raw.get("resume_command") or "").strip()
        resume_tool = str(raw.get("resumeTool") or raw.get("resume_tool") or "").strip().lower()
        resume_session_id = str(raw.get("resumeSessionId") or raw.get("resume_session_id") or raw.get("sessionId") or "").strip()
        codex_session_id = str(raw.get("codexSessionId") or raw.get("codex_session_id") or "").strip()
        claude_session_id = str(raw.get("claudeSessionId") or raw.get("claude_session_id") or "").strip()
        if not resume_command:
            if resume_tool and resume_session_id:
                resume_command = f"{resume_tool} resume {resume_session_id}"
            elif codex_session_id:
                resume_command = f"codex resume {codex_session_id}"
                resume_tool = "codex"
                resume_session_id = codex_session_id
            elif claude_session_id:
                resume_command = f"claude resume {claude_session_id}"
                resume_tool = "claude"
                resume_session_id = claude_session_id
        rows.append(
            {
                "tab_id": f"tab_{index + 1}",
                "order_index": index,
                "title": title,
                "repo_label": title,
                "project_root": project_root,
                "resume_command": resume_command,
                "resume_tool": resume_tool,
                "resume_session_id": resume_session_id,
                "codex_session_id": codex_session_id or (resume_session_id if resume_tool == "codex" else ""),
                "tmux_session_name": str(raw.get("tmuxSessionName") or raw.get("tmux_session_name") or "").strip(),
                "status": "active",
            }
        )
    return rows


def _workspace_bridge_tabs_from_notes(notes: Any) -> list[dict[str, Any]]:
    text = re.sub(r"```orp-workspace\s*[\s\S]*?```", "", str(notes or ""), flags=re.IGNORECASE)
    seen_titles: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or not stripped.startswith("/"):
            continue
        match = re.match(
            r"^(?P<path>/.*?)(?::\s*(?P<resume>(?P<tool>codex|claude)\s+resume\b.*))?\s*$",
            stripped,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        project_root = str(match.group("path") or "").strip()
        if not project_root:
            continue
        resume_command = str(match.group("resume") or "").strip()
        resume_tool = str(match.group("tool") or "").strip().lower()
        session_match = re.match(r"^(?:codex|claude)\s+resume\s+([^\s]+)", resume_command, flags=re.IGNORECASE)
        resume_session_id = str(session_match.group(1) if session_match else "").strip()
        title = _workspace_bridge_tab_title(
            "",
            project_root,
            index=len(rows),
            seen_titles=seen_titles,
        )
        rows.append(
            {
                "tab_id": f"tab_{len(rows) + 1}",
                "order_index": len(rows),
                "title": title,
                "repo_label": title,
                "project_root": project_root,
                "resume_command": resume_command,
                "resume_tool": resume_tool,
                "resume_session_id": resume_session_id,
                "codex_session_id": resume_session_id if resume_tool == "codex" else "",
                "tmux_session_name": "",
                "status": "active",
            }
        )
    return rows


def _workspace_bridge_from_idea(idea: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(idea, dict):
        return None
    manifest = _workspace_manifest_from_notes(idea.get("notes"))
    tabs = _workspace_bridge_tabs_from_manifest(manifest) if manifest else _workspace_bridge_tabs_from_notes(idea.get("notes"))
    if not tabs:
        return None

    idea_id = str(idea.get("id", "")).strip()
    idea_title = str(idea.get("title", "")).strip()
    workspace_id = str((manifest or {}).get("workspaceId", "")).strip() or (f"idea-{idea_id}" if idea_id else "")
    title = str((manifest or {}).get("title", "")).strip() or idea_title or workspace_id
    description = str(idea.get("description", "")).strip()
    updated_at = str(idea.get("updatedAt", "")).strip()
    visibility = str(idea.get("visibility", "")).strip()
    tab_count = len(tabs)

    return {
        "workspace_id": workspace_id,
        "id": workspace_id,
        "title": title,
        "description": description,
        "visibility": visibility,
        "updatedAt": updated_at,
        "updated_at_utc": updated_at,
        "source_kind": "idea_bridge",
        "bridge_kind": "idea_notes",
        "linkedIdea": {
            "ideaId": idea_id,
            "relationship": "primary",
            "ideaTitle": idea_title,
        },
        "linked_idea": {
            "idea_id": idea_id,
            "relationship": "primary",
            "idea_title": idea_title,
        },
        "metrics": {
            "tabCount": tab_count,
            "tab_count": tab_count,
        },
        "state": {
            "state_version": 0,
            "tabCount": tab_count,
            "tab_count": tab_count,
            "summary": "",
            "current_focus": "",
            "trajectory": "",
            "tabs": tabs,
            "source_kind": "idea_bridge",
        },
        "manifest": manifest or None,
    }


def _list_workspace_bridge_page(
    args: argparse.Namespace,
    *,
    limit: int,
    cursor: str,
) -> dict[str, Any]:
    session = _require_hosted_session(args)
    params: list[str] = []
    if int(limit) > 0:
        params.append(f"limit={int(limit)}")
    if cursor:
        params.append(f"cursor={urlparse.quote(cursor)}")
    query = f"?{'&'.join(params)}" if params else ""
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas{query}",
        token=str(session.get("token", "")).strip(),
    )
    ideas = payload.get("ideas") if isinstance(payload.get("ideas"), list) else None
    if ideas is None and isinstance(payload.get("items"), list):
        ideas = payload.get("items")
    cursor_value = payload.get("cursor")
    next_cursor = str(cursor_value).strip() if cursor_value is not None else ""
    if not next_cursor:
        next_cursor_value = payload.get("nextCursor")
        next_cursor = str(next_cursor_value).strip() if next_cursor_value is not None else ""
    has_more = payload.get("hasMore")
    if isinstance(has_more, bool):
        has_more_value = has_more
    else:
        has_more_value = bool(next_cursor)
    workspaces = [
        row
        for row in (_workspace_bridge_from_idea(idea) for idea in (ideas or []))
        if isinstance(row, dict)
    ]
    return {
        "workspaces": workspaces,
        "cursor": next_cursor,
        "has_more": has_more_value,
        "source": "idea_bridge",
    }


def _list_remote_workspaces_page(
    args: argparse.Namespace,
    *,
    limit: int,
    cursor: str,
) -> dict[str, Any]:
    session = _require_hosted_session(args)
    params: list[str] = []
    if int(limit) > 0:
        params.append(f"limit={int(limit)}")
    if cursor:
        params.append(f"cursor={urlparse.quote(cursor)}")
    query = f"?{'&'.join(params)}" if params else ""

    try:
        payload = _request_hosted_json(
            base_url=_resolve_hosted_base_url(args, session),
            path=f"/api/cli/workspaces{query}",
            token=str(session.get("token", "")).strip(),
        )
    except HostedApiError as exc:
        if "status=404" not in str(exc):
            raise
        return _list_workspace_bridge_page(args, limit=limit, cursor=cursor)

    workspaces = payload.get("workspaces") if isinstance(payload.get("workspaces"), list) else None
    if workspaces is None and isinstance(payload.get("items"), list):
        workspaces = payload.get("items")
    cursor_value = payload.get("cursor")
    next_cursor = str(cursor_value).strip() if cursor_value is not None else ""
    if not next_cursor:
        next_cursor_value = payload.get("nextCursor")
        next_cursor = str(next_cursor_value).strip() if next_cursor_value is not None else ""
    has_more = payload.get("hasMore")
    if isinstance(has_more, bool):
        has_more_value = has_more
    else:
        has_more_value = bool(next_cursor)

    return {
        "workspaces": [row for row in (workspaces or []) if isinstance(row, dict)],
        "cursor": next_cursor,
        "has_more": has_more_value,
        "source": "hosted",
    }


def _workspace_selector_values(workspace: dict[str, Any]) -> list[str]:
    linked_idea = _workspace_object(workspace, "linked_idea", "linkedIdea")
    values = [
        _workspace_text(workspace, "workspace_id", "id"),
        _workspace_text(workspace, "title"),
        _workspace_text(linked_idea, "idea_id", "ideaId"),
        _workspace_text(linked_idea, "idea_title", "ideaTitle"),
    ]
    return [value for value in values if value]


def _workspace_selector_score(selector: str, workspace: dict[str, Any]) -> int:
    selector_text = str(selector or "").strip()
    if not selector_text:
        return 0
    selector_lower = selector_text.lower()
    selector_slug = _slugify_value(selector_text)
    best = 0
    for candidate in _workspace_selector_values(workspace):
        candidate_text = str(candidate or "").strip()
        if not candidate_text:
            continue
        candidate_lower = candidate_text.lower()
        candidate_slug = _slugify_value(candidate_text)
        if selector_text == candidate_text:
            best = max(best, 40)
        elif selector_lower == candidate_lower:
            best = max(best, 35)
        elif selector_slug == candidate_slug:
            best = max(best, 20)
    if best > 0 and _workspace_text(workspace, "source_kind") != "idea_bridge":
        best += 5
    return best


def _resolve_workspace_selector(workspace_ref: str, workspaces: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    selector = str(workspace_ref or "").strip()
    if not selector:
        return None
    ranked: list[tuple[int, dict[str, Any]]] = []
    for workspace in workspaces:
        if not isinstance(workspace, dict):
            continue
        score = _workspace_selector_score(selector, workspace)
        if score > 0:
            ranked.append((score, workspace))
    if not ranked:
        return None
    ranked.sort(key=lambda row: row[0], reverse=True)
    best_score = ranked[0][0]
    best = [workspace for score, workspace in ranked if score == best_score]
    if len(best) > 1:
        matches = "; ".join(
            f"{_workspace_text(row, 'title') or _workspace_text(row, 'workspace_id', 'id')} [{_workspace_text(row, 'workspace_id', 'id')}]"
            for row in best
        )
        raise RuntimeError(f"Workspace selector `{selector}` is ambiguous. Matches: {matches}")
    return best[0]


def _list_all_remote_workspaces(args: argparse.Namespace, *, limit: int = 200) -> dict[str, Any]:
    cursor = ""
    items: list[dict[str, Any]] = []
    source = ""
    for _ in range(20):
        page = _list_remote_workspaces_page(args, limit=limit, cursor=cursor)
        items.extend([row for row in page.get("workspaces", []) if isinstance(row, dict)])
        source = source or str(page.get("source", "")).strip()
        cursor = str(page.get("cursor", "")).strip()
        if not page.get("has_more") or not cursor:
            break
    return {
        "workspaces": items,
        "source": source or "hosted",
    }


def _get_remote_workspace_by_id(args: argparse.Namespace, workspace_id: str) -> dict[str, Any]:
    session = _require_hosted_session(args)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/workspaces/{urlparse.quote(workspace_id)}",
        token=str(session.get("token", "")).strip(),
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Hosted ORP returned an invalid workspace payload.")
    return _normalize_remote_workspace_payload(payload)["workspace"]


def _get_remote_workspace(args: argparse.Namespace, workspace_ref: str) -> dict[str, Any]:
    selector = str(workspace_ref or "").strip()
    if not selector:
        raise RuntimeError("Workspace name or id is required.")
    candidates = _list_all_remote_workspaces(args)
    resolved = _resolve_workspace_selector(selector, candidates.get("workspaces", []))
    if resolved is None:
        try:
            return _get_remote_workspace_by_id(args, selector)
        except HostedApiError as exc:
            if "status=404" not in str(exc):
                raise
        raise RuntimeError(f"Workspace not found: {selector}")
    if _workspace_text(resolved, "source_kind") == "idea_bridge":
        return resolved
    workspace_id = _workspace_text(resolved, "workspace_id", "id") or selector
    return _get_remote_workspace_by_id(args, workspace_id)


def _build_remote_workspace_body(
    args: argparse.Namespace,
    current_workspace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    title = getattr(args, "title", None)
    description = getattr(args, "description", None)
    visibility = getattr(args, "visibility", None)
    idea_id = getattr(args, "idea_id", None)

    if title is not None:
        text = str(title).strip()
        if text:
            body["title"] = _normalize_workspace_title_input(text)
    if description is not None:
        text = str(description).strip()
        body["description"] = text or None
    if visibility is not None:
        text = str(visibility).strip()
        if text:
            body["visibility"] = text
    if idea_id is not None:
        text = str(idea_id).strip()
        if text:
            body["linkedIdea"] = {
                "ideaId": text,
                "relationship": "primary",
            }
    return body


def _load_hosted_workspace_json_file(path_arg: str, *, label: str) -> tuple[Path, dict[str, Any]]:
    path = Path(str(path_arg)).expanduser().resolve()
    if not path.exists():
        raise RuntimeError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse {label} JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} JSON at {path} must be an object.")
    return path, payload


def cmd_workspaces_list(args: argparse.Namespace) -> int:
    result = _list_remote_workspaces_page(
        args,
        limit=int(args.limit),
        cursor=str(getattr(args, "cursor", "")).strip(),
    )
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("workspaces.count", len(result["workspaces"])),
                ("cursor", result["cursor"]),
                ("has_more", str(result["has_more"]).lower()),
                ("source", str(result.get("source", "")).strip() or "hosted"),
            ]
        )
        for row in result["workspaces"]:
            linked_idea = _workspace_object(row, "linked_idea", "linkedIdea")
            metrics = _workspace_object(row, "metrics")
            print("---")
            _print_pairs(
                [
                    ("workspace.id", _workspace_text(row, "workspace_id", "id")),
                    ("workspace.title", _workspace_text(row, "title")),
                    ("workspace.visibility", _workspace_text(row, "visibility")),
                    ("workspace.idea_id", _workspace_text(linked_idea, "idea_id", "ideaId")),
                    ("workspace.source", _workspace_text(row, "source_kind") or str(result.get("source", "")).strip() or "hosted"),
                    ("workspace.tab_count", _workspace_text(metrics, "tab_count", "tabCount")),
                    ("workspace.updated_at", _workspace_text(row, "updated_at_utc", "updatedAt")),
                ]
            )
    return 0


def cmd_workspaces_show(args: argparse.Namespace) -> int:
    workspace = _get_remote_workspace(args, args.workspace_id)
    result = {
        "ok": True,
        "workspace": workspace,
    }
    if args.json_output:
        _print_json(result)
    else:
        linked_idea = _workspace_object(workspace, "linked_idea", "linkedIdea")
        state = _workspace_object(workspace, "state")
        _print_pairs(
            [
                ("workspace.id", _workspace_text(workspace, "workspace_id", "id")),
                ("workspace.title", _workspace_text(workspace, "title")),
                ("workspace.visibility", _workspace_text(workspace, "visibility")),
                ("workspace.idea_id", _workspace_text(linked_idea, "idea_id", "ideaId")),
                ("workspace.source", _workspace_text(workspace, "source_kind") or "hosted"),
                ("state.tab_count", _workspace_text(state, "tab_count", "tabCount")),
                ("state.current_focus", _workspace_text(state, "current_focus", "currentFocus")),
                ("state.trajectory", _workspace_text(state, "trajectory")),
                ("workspace.updated_at", _workspace_text(workspace, "updated_at_utc", "updatedAt")),
            ]
        )
    return 0


def cmd_workspaces_tabs(args: argparse.Namespace) -> int:
    workspace = _get_remote_workspace(args, args.workspace_id)
    if _workspace_text(workspace, "source_kind") == "idea_bridge":
        tabs = _workspace_tab_rows(workspace)
        title = _workspace_text(workspace, "title")
    else:
        session = _require_hosted_session(args)
        workspace_id = _workspace_text(workspace, "workspace_id", "id") or args.workspace_id
        payload = _request_hosted_json(
            base_url=_resolve_hosted_base_url(args, session),
            path=f"/api/cli/workspaces/{urlparse.quote(workspace_id)}/tabs",
            token=str(session.get("token", "")).strip(),
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Hosted ORP returned an invalid workspace tabs payload.")

        payload_workspace = payload.get("workspace") if isinstance(payload.get("workspace"), dict) else None
        tabs = payload.get("tabs") if isinstance(payload.get("tabs"), list) else None
        if tabs is None and isinstance(payload.get("items"), list):
            tabs = payload.get("items")
        if tabs is None:
            if payload_workspace is not None:
                tabs = _workspace_tab_rows(payload_workspace)
            else:
                payload_workspace = _normalize_remote_workspace_payload(payload)["workspace"]
                tabs = _workspace_tab_rows(payload_workspace)

        title = _workspace_text(payload, "title")
        if not title and payload_workspace is not None:
            title = _workspace_text(payload_workspace, "title")
    result = {
        "workspace_id": _workspace_text(workspace, "workspace_id", "id") or args.workspace_id,
        "title": title,
        "tabs": [row for row in (tabs or []) if isinstance(row, dict)],
        "source": _workspace_text(workspace, "source_kind") or "hosted",
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("workspace.id", result["workspace_id"]),
                ("workspace.title", result["title"]),
                ("workspace.source", result["source"]),
                ("tabs.count", len(tabs)),
            ]
        )
        for index, row in enumerate(tabs, start=1):
            print("---")
            _print_pairs(
                [
                    ("tab.index", index),
                    ("tab.title", _workspace_text(row, "title", "repo_label", "repoLabel")),
                    ("tab.project_root", _workspace_text(row, "project_root", "projectRoot")),
                    ("tab.resume_command", _workspace_text(row, "resume_command", "resumeCommand")),
                    ("tab.resume_tool", _workspace_text(row, "resume_tool", "resumeTool")),
                    ("tab.resume_session_id", _workspace_text(row, "resume_session_id", "resumeSessionId")),
                    ("tab.codex_session_id", _workspace_text(row, "codex_session_id", "codexSessionId")),
                    ("tab.tmux_session_name", _workspace_text(row, "tmux_session_name", "tmuxSessionName")),
                    ("tab.current_task", _workspace_text(row, "current_task", "currentTask")),
                ]
            )
    return 0


def cmd_workspaces_timeline(args: argparse.Namespace) -> int:
    workspace = _get_remote_workspace(args, args.workspace_id)
    if _workspace_text(workspace, "source_kind") == "idea_bridge":
        events: list[dict[str, Any]] = []
    else:
        session = _require_hosted_session(args)
        params: list[str] = []
        if int(args.limit) > 0:
            params.append(f"limit={int(args.limit)}")
        query = f"?{'&'.join(params)}" if params else ""

        workspace_id = _workspace_text(workspace, "workspace_id", "id") or args.workspace_id
        payload = _request_hosted_json(
            base_url=_resolve_hosted_base_url(args, session),
            path=f"/api/cli/workspaces/{urlparse.quote(workspace_id)}/timeline{query}",
            token=str(session.get("token", "")).strip(),
        )
        events = payload.get("events") if isinstance(payload.get("events"), list) else None
        if events is None and isinstance(payload.get("items"), list):
            events = payload.get("items")
    result = {
        "workspace_id": _workspace_text(workspace, "workspace_id", "id") or args.workspace_id,
        "events": [row for row in (events or []) if isinstance(row, dict)],
        "source": _workspace_text(workspace, "source_kind") or "hosted",
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("workspace.id", result["workspace_id"]),
                ("workspace.source", result["source"]),
                ("events.count", len(result["events"])),
            ]
        )
        for row in result["events"]:
            print("---")
            _print_pairs(
                [
                    ("event.id", _workspace_text(row, "event_id", "id")),
                    ("event.type", _workspace_text(row, "event_type", "type")),
                    ("event.summary", _workspace_text(row, "summary")),
                    ("event.created_at", _workspace_text(row, "created_at_utc", "createdAt")),
                ]
            )
    return 0


def cmd_workspaces_add(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    body = _build_remote_workspace_body(args, None)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path="/api/cli/workspaces",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    result = _normalize_remote_workspace_payload(payload)
    if args.json_output:
        _print_json(result)
    else:
        workspace = result["workspace"]
        _print_pairs(
            [
                ("workspace.id", _workspace_text(workspace, "workspace_id", "id")),
                ("workspace.title", _workspace_text(workspace, "title")),
                ("workspace.visibility", _workspace_text(workspace, "visibility")),
            ]
        )
    return 0


def cmd_workspaces_update(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    current = _get_remote_workspace(args, args.workspace_id)
    body = _build_remote_workspace_body(args, current)
    updated_at = _workspace_text(current, "updated_at_utc", "updatedAt")
    if updated_at:
        body["updatedAt"] = updated_at
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/workspaces/{urlparse.quote(args.workspace_id)}",
        method="PATCH",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    result = _normalize_remote_workspace_payload(payload)
    if args.json_output:
        _print_json(result)
    else:
        workspace = result["workspace"]
        _print_pairs(
            [
                ("workspace.id", _workspace_text(workspace, "workspace_id", "id")),
                ("workspace.title", _workspace_text(workspace, "title")),
                ("workspace.updated_at", _workspace_text(workspace, "updated_at_utc", "updatedAt")),
            ]
        )
    return 0


def cmd_workspaces_push_state(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    state_path, body = _load_hosted_workspace_json_file(args.state_file, label="workspace state")
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/workspaces/{urlparse.quote(args.workspace_id)}/state",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    if args.json_output:
        _print_json(payload)
    else:
        _print_pairs(
            [
                ("workspace.id", args.workspace_id),
                ("state.file", str(state_path)),
                ("ok", str(bool(payload.get("ok", True))).lower()),
            ]
        )
    return 0


def cmd_workspaces_add_event(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    event_path, body = _load_hosted_workspace_json_file(args.event_file, label="workspace event")
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/workspaces/{urlparse.quote(args.workspace_id)}/events",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    if args.json_output:
        _print_json(payload)
    else:
        _print_pairs(
            [
                ("workspace.id", args.workspace_id),
                ("event.file", str(event_path)),
                ("ok", str(bool(payload.get("ok", True))).lower()),
            ]
        )
    return 0


def _normalize_remote_idea_payload(payload: dict[str, Any]) -> dict[str, Any]:
    idea = payload.get("idea") if isinstance(payload.get("idea"), dict) else payload
    if not isinstance(idea, dict):
        raise RuntimeError("Hosted ORP returned an invalid idea payload.")
    features = payload.get("features") if isinstance(payload.get("features"), list) else idea.get("features")
    normalized_features = features if isinstance(features, list) else []
    normalized_idea = dict(idea)
    normalized_idea["features"] = normalized_features
    return {
        "ok": bool(payload.get("ok", True)),
        "idea": normalized_idea,
        "features": normalized_features,
    }


def _get_remote_idea(args: argparse.Namespace, idea_id: str) -> dict[str, Any]:
    session = _require_hosted_session(args)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas/{urlparse.quote(idea_id)}",
        token=str(session.get("token", "")).strip(),
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Hosted ORP returned an invalid idea payload.")
    return _normalize_remote_idea_payload(payload)["idea"]


def _require_current_repo_project_root(raw: Any, repo_root: Path, *, context: str) -> str:
    project_root = _normalize_local_path(raw, repo_root, fallback=str(repo_root))
    if project_root != str(repo_root):
        raise RuntimeError(f"{context} only supports the current --repo-root. Re-run with the matching repo root.")
    return project_root


def _print_link_status_human(payload: dict[str, Any]) -> None:
    session_counts = payload.get("session_counts", {}) if isinstance(payload.get("session_counts"), dict) else {}
    primary_session = payload.get("primary_session", {}) if isinstance(payload.get("primary_session"), dict) else {}
    project_link = payload.get("project_link", {}) if isinstance(payload.get("project_link"), dict) else {}
    hosted_auth = payload.get("hosted_auth", {}) if isinstance(payload.get("hosted_auth"), dict) else {}
    hosted_world = payload.get("hosted_world", {}) if isinstance(payload.get("hosted_world"), dict) else {}

    print(f"project_linked={'true' if payload.get('project_link_exists') else 'false'}")
    print(f"routing_ready={'true' if payload.get('routing_ready') else 'false'}")
    print(f"project.idea_id={project_link.get('idea_id', '')}")
    print(f"project.world_id={project_link.get('world_id', '')}")
    print(f"project.link_path={payload.get('project_link_path', '')}")
    print(f"sessions.total={session_counts.get('total', 0)}")
    print(f"sessions.active={session_counts.get('active', 0)}")
    print(f"sessions.archived={session_counts.get('archived', 0)}")
    print(f"sessions.routeable={session_counts.get('routeable', 0)}")
    print(f"primary.orp_session_id={primary_session.get('orp_session_id', '')}")
    print(f"primary.codex_session_id={primary_session.get('codex_session_id', '')}")
    print(f"hosted.connected={'true' if hosted_auth.get('connected') else 'false'}")
    print(f"hosted.email={hosted_auth.get('email', '')}")
    print(f"hosted.world_id={hosted_world.get('id', '')}")
    for note in payload.get("notes", []):
        print(f"note={note}")
    for warning in payload.get("warnings", []):
        print(f"warning={warning}")
    for action_line in payload.get("next_actions", []):
        print(f"next={action_line}")


def _print_runner_status_human(payload: dict[str, Any]) -> None:
    machine = payload.get("machine", {}) if isinstance(payload.get("machine"), dict) else {}
    session_counts = payload.get("session_counts", {}) if isinstance(payload.get("session_counts"), dict) else {}
    repo_runtime = payload.get("repo_runtime", {}) if isinstance(payload.get("repo_runtime"), dict) else {}
    active_job = repo_runtime.get("active_job", {}) if isinstance(repo_runtime.get("active_job"), dict) else {}
    last_job = repo_runtime.get("last_job", {}) if isinstance(repo_runtime.get("last_job"), dict) else {}
    print(f"runner.enabled={'true' if machine.get('runner_enabled') else 'false'}")
    print(f"runner.sync_ready={'true' if payload.get('sync_ready') else 'false'}")
    print(f"runner.work_ready={'true' if payload.get('work_ready') else 'false'}")
    print(f"machine.id={machine.get('machine_id', '')}")
    print(f"machine.name={machine.get('machine_name', '')}")
    print(f"machine.platform={machine.get('platform', '')}")
    print(f"machine.last_heartbeat_at_utc={machine.get('last_heartbeat_at_utc', '')}")
    print(f"machine.last_sync_at_utc={machine.get('last_sync_at_utc', '')}")
    print(f"machine.path={payload.get('machine_path', '')}")
    print(f"repo.runner_path={payload.get('repo_runner_path', '')}")
    print(f"repo.runtime_path={payload.get('repo_runtime_path', '')}")
    print(f"runtime.status={repo_runtime.get('status', '')}")
    print(f"runtime.active_job_id={active_job.get('job_id', '')}")
    print(f"runtime.active_lease_id={active_job.get('lease_id', '')}")
    print(f"runtime.last_job_status={last_job.get('status', '')}")
    print(f"project_linked={'true' if payload.get('project_link_exists') else 'false'}")
    print(f"sessions.total={session_counts.get('total', 0)}")
    print(f"sessions.routeable={session_counts.get('routeable', 0)}")
    for note in payload.get("notes", []):
        print(f"note={note}")
    for warning in payload.get("warnings", []):
        print(f"warning={warning}")
    for action_line in payload.get("next_actions", []):
        print(f"next={action_line}")


def cmd_idea_show(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas/{urlparse.quote(args.idea_id)}",
        token=str(session.get("token", "")).strip(),
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Hosted ORP returned an invalid idea payload.")
    result = _normalize_remote_idea_payload(payload)
    idea = result["idea"]
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("idea.id", str(idea.get("id", "")).strip()),
                ("idea.title", str(idea.get("title", "")).strip()),
                ("idea.visibility", str(idea.get("visibility", "")).strip()),
                ("idea.github_url", str(idea.get("githubUrl", "")).strip()),
                ("idea.updated_at", str(idea.get("updatedAt", "")).strip()),
            ]
        )
    return 0


def cmd_idea_add(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    body = _build_remote_idea_body(args, require_notes=True)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path="/api/cli/ideas",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    if args.json_output:
        _print_json(payload)
    else:
        _print_pairs(
            [
                ("idea.id", str(payload.get("id", "")).strip()),
                ("idea.title", str(payload.get("title", "")).strip()),
                ("idea.visibility", str(payload.get("visibility", "")).strip()),
            ]
        )
    return 0


def cmd_idea_update(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    current = _get_remote_idea(args, args.idea_id)
    body = _build_remote_idea_body(args, current_idea=current, require_notes=False)
    updated_at = str(current.get("updatedAt", "")).strip()
    if updated_at:
        body["updatedAt"] = updated_at
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas/{urlparse.quote(args.idea_id)}",
        method="PATCH",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    if args.json_output:
        _print_json(payload)
    else:
        _print_pairs(
            [
                ("idea.id", str(payload.get("id", "")).strip()),
                ("idea.title", str(payload.get("title", "")).strip()),
                ("idea.visibility", str(payload.get("visibility", "")).strip()),
                ("idea.updated_at", str(payload.get("updatedAt", "")).strip()),
            ]
        )
    return 0


def cmd_idea_remove(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    suffix = "?purge=1" if bool(getattr(args, "purge", False)) else ""
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas/{urlparse.quote(args.idea_id)}{suffix}",
        method="DELETE",
        token=str(session.get("token", "")).strip(),
    )
    if args.json_output:
        _print_json(payload)
    else:
        _print_pairs(
            [
                ("idea.id", str(payload.get("removedIdeaId", "")).strip()),
                ("mode", str(payload.get("mode", "")).strip()),
                ("ok", str(bool(payload.get("ok", False))).lower()),
            ]
        )
    return 0


def cmd_idea_restore(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas/{urlparse.quote(args.idea_id)}/restore",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body={},
    )
    if args.json_output:
        _print_json(payload)
    else:
        _print_pairs(
            [
                ("idea.id", str(payload.get("id", "")).strip()),
                ("idea.title", str(payload.get("title", "")).strip()),
                ("idea.visibility", str(payload.get("visibility", "")).strip()),
                ("ok", str(bool(payload.get("ok", True))).lower()),
            ]
        )
    return 0


def cmd_feature_list(args: argparse.Namespace) -> int:
    idea = _get_remote_idea(args, args.idea_id)
    features = idea.get("features") if isinstance(idea.get("features"), list) else []
    result = {
        "idea_id": str(idea.get("id", "")).strip(),
        "idea_title": str(idea.get("title", "")).strip(),
        "features": features,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("idea.id", result["idea_id"]),
                ("idea.title", result["idea_title"]),
                ("features.count", len(features)),
            ]
        )
        for row in features:
            if not isinstance(row, dict):
                continue
            print("---")
            _print_pairs(
                [
                    ("feature.id", str(row.get("id", "")).strip()),
                    ("feature.title", str(row.get("title", "")).strip()),
                    ("feature.updated_at", str(row.get("updatedAt", "")).strip()),
                ]
            )
    return 0


def _find_feature_by_id(idea_payload: dict[str, Any], feature_id: str) -> dict[str, Any]:
    features = idea_payload.get("features")
    if not isinstance(features, list):
        raise RuntimeError("Idea does not contain feature data.")
    for row in features:
        if isinstance(row, dict) and str(row.get("id", "")).strip() == feature_id:
            return row
    raise RuntimeError(f"Feature not found on idea: {feature_id}")


def cmd_feature_show(args: argparse.Namespace) -> int:
    idea = _get_remote_idea(args, args.idea_id)
    feature = _find_feature_by_id(idea, args.feature_id)
    result = {
        "idea_id": str(idea.get("id", "")).strip(),
        "feature": feature,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("feature.id", str(feature.get("id", "")).strip()),
                ("feature.title", str(feature.get("title", "")).strip()),
                ("feature.updated_at", str(feature.get("updatedAt", "")).strip()),
            ]
        )
    return 0


def cmd_feature_add(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    body = _build_remote_feature_body(args, args.idea_id, None)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas/{urlparse.quote(args.idea_id)}/features",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    if args.json_output:
        _print_json(payload)
    else:
        _print_pairs(
            [
                ("feature.id", str(payload.get("id", "")).strip()),
                ("feature.title", str(payload.get("title", "")).strip()),
                ("idea.id", str(payload.get("ideaId", args.idea_id)).strip()),
            ]
        )
    return 0


def cmd_feature_update(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    idea = _get_remote_idea(args, args.idea_id)
    current = _find_feature_by_id(idea, args.feature_id)
    body = _build_remote_feature_body(args, args.idea_id, current)
    updated_at = str(current.get("updatedAt", "")).strip()
    if updated_at:
        body["updatedAt"] = updated_at
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/features/{urlparse.quote(args.feature_id)}",
        method="PATCH",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    if args.json_output:
        _print_json(payload)
    else:
        _print_pairs(
            [
                ("feature.id", str(payload.get("id", "")).strip()),
                ("feature.title", str(payload.get("title", "")).strip()),
                ("feature.updated_at", str(payload.get("updatedAt", "")).strip()),
            ]
        )
    return 0


def cmd_feature_remove(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/features/{urlparse.quote(args.feature_id)}",
        method="DELETE",
        token=str(session.get("token", "")).strip(),
    )
    if args.json_output:
        _print_json(payload)
    else:
        _print_pairs(
            [
                ("feature.id", str(payload.get("removedFeatureId", "")).strip()),
                ("idea.id", str(payload.get("ideaId", "")).strip()),
                ("ok", str(bool(payload.get("ok", False))).lower()),
            ]
        )
    return 0


def cmd_world_show(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas/{urlparse.quote(args.idea_id)}/world",
        token=str(session.get("token", "")).strip(),
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Hosted ORP returned an invalid world payload.")
    result = _normalize_remote_world_payload(payload)
    world = result["world"]
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("world.id", str(world.get("id", "")).strip()),
                ("world.name", str(world.get("name", "")).strip()),
                ("world.project_root", str(world.get("projectRoot", "")).strip()),
                ("world.github_url", str(world.get("githubUrl", "")).strip()),
                ("world.codex_session_id", str(world.get("codexSessionId", "")).strip()),
                ("world.status", str(world.get("status", "")).strip()),
            ]
        )
    return 0


def cmd_world_bind(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    body = _build_remote_world_body(args)
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas/{urlparse.quote(args.idea_id)}/world",
        method="PUT",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Hosted ORP returned an invalid world payload.")
    result = _normalize_remote_world_payload(payload)
    world = result["world"]
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("world.id", str(world.get("id", "")).strip()),
                ("world.name", str(world.get("name", "")).strip()),
                ("world.project_root", str(world.get("projectRoot", "")).strip()),
                ("world.codex_session_id", str(world.get("codexSessionId", "")).strip()),
                ("world.status", str(world.get("status", "")).strip()),
            ]
        )
    return 0


def cmd_secrets_list(args: argparse.Namespace) -> int:
    params: list[str] = []
    provider = str(getattr(args, "provider", "") or "").strip()
    if provider:
        params.append(f"provider={urlparse.quote(provider)}")
    world_id, idea_id = _resolve_secret_scope_from_args(args, require_scope=False)
    if world_id:
        params.append(f"worldId={urlparse.quote(world_id)}")
    if idea_id:
        params.append(f"ideaId={urlparse.quote(idea_id)}")
    if bool(getattr(args, "archived", False)):
        params.append("archived=1")
    query = f"?{'&'.join(params)}" if params else ""

    payload = _request_secret_payload(args, path=f"/api/cli/secrets{query}")
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    result = {
        "ok": bool(payload.get("ok", True)),
        "items": [row for row in items if isinstance(row, dict)],
        "provider": provider,
        "world_id": world_id,
        "idea_id": idea_id,
        "archived": bool(getattr(args, "archived", False)),
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("secrets.count", len(result["items"])),
                ("filter.provider", provider),
                ("filter.world_id", world_id),
                ("filter.idea_id", idea_id),
                ("filter.archived", str(result["archived"]).lower()),
            ]
        )
        for secret in result["items"]:
            print("---")
            _print_secret_human(secret, include_bindings=False)
    return 0


def cmd_secrets_show(args: argparse.Namespace) -> int:
    secret_ref = str(getattr(args, "secret_ref", "") or "").strip()
    if not secret_ref:
        raise RuntimeError("Secret reference is required.")
    payload = _request_secret_payload(
        args,
        path=f"/api/cli/secrets/{urlparse.quote(secret_ref)}",
    )
    secret = payload.get("secret") if isinstance(payload.get("secret"), dict) else payload
    if not isinstance(secret, dict):
        raise RuntimeError("Hosted ORP returned an invalid secret record.")
    result = {
        "ok": bool(payload.get("ok", True)),
        "secret": secret,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_secret_human(secret, include_bindings=True)
    return 0


def cmd_secrets_add(args: argparse.Namespace) -> int:
    _, value = _resolve_secret_value_arg(args, required=True)
    body: dict[str, Any] = {
        "alias": str(getattr(args, "alias", "")).strip(),
        "label": str(getattr(args, "label", "")).strip(),
        "provider": str(getattr(args, "provider", "")).strip(),
        "kind": str(getattr(args, "kind", "api_key")).strip() or "api_key",
        "value": value,
    }
    env_var_name = getattr(args, "env_var_name", None)
    if env_var_name is not None:
        text = str(env_var_name).strip()
        body["envVarName"] = text or None
    notes = getattr(args, "notes", None)
    if notes is not None:
        text = str(notes).strip()
        body["notes"] = text or None
    binding = _build_secret_binding_payload_from_args(args)
    body["bindings"] = [binding] if binding else []

    payload = _request_secret_payload(
        args,
        path="/api/cli/secrets",
        method="POST",
        body=body,
    )
    secret = payload.get("secret") if isinstance(payload.get("secret"), dict) else payload
    if not isinstance(secret, dict):
        raise RuntimeError("Hosted ORP returned an invalid secret record.")
    result = {
        "ok": bool(payload.get("ok", True)),
        "secret": secret,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_secret_human(secret, include_bindings=True)
    return 0


def cmd_secrets_ensure(args: argparse.Namespace) -> int:
    alias = str(getattr(args, "alias", "") or "").strip()
    if not alias:
        raise RuntimeError("Secret alias is required.")

    desired_binding = _build_secret_binding_payload_from_args(
        args,
        fallback_to_current_project=True,
    )
    secret = _try_get_secret_by_ref(args, alias)
    created = False
    binding_created = False
    binding_reused = False
    binding = None

    if secret is None:
        _, value = _resolve_secret_value_arg(args, required=True)
        label = str(getattr(args, "label", "") or "").strip() or alias
        body: dict[str, Any] = {
            "alias": alias,
            "label": label,
            "provider": str(getattr(args, "provider", "")).strip(),
            "kind": str(getattr(args, "kind", "api_key")).strip() or "api_key",
            "value": value,
        }
        env_var_name = getattr(args, "env_var_name", None)
        if env_var_name is not None:
            text = str(env_var_name).strip()
            body["envVarName"] = text or None
        notes = getattr(args, "notes", None)
        if notes is not None:
            text = str(notes).strip()
            body["notes"] = text or None
        body["bindings"] = [desired_binding] if desired_binding else []

        payload = _request_secret_payload(
            args,
            path="/api/cli/secrets",
            method="POST",
            body=body,
        )
        created_secret = payload.get("secret") if isinstance(payload.get("secret"), dict) else payload
        if not isinstance(created_secret, dict):
            raise RuntimeError("Hosted ORP returned an invalid secret record.")
        secret = created_secret
        created = True
        if desired_binding:
            binding = _find_secret_binding(secret, desired_binding)
            binding_created = binding is not None
    else:
        _validate_existing_secret_for_ensure(secret, args)
        if desired_binding:
            binding = _find_secret_binding(secret, desired_binding)
            if binding is not None:
                binding_reused = True
            else:
                binding = _create_secret_binding_for_ensure(args, secret, desired_binding)
                binding_created = True
                secret = dict(secret)
                secret["bindings"] = [*_secret_bindings(secret), binding]

    resolved: dict[str, Any] | None = None
    if bool(getattr(args, "reveal", False)):
        resolved = _resolve_secret_for_ensure(args, secret, desired_binding)
        secret = resolved["secret"]
        if binding is None and isinstance(resolved.get("binding"), dict):
            binding = resolved["binding"]

    result = {
        "ok": True,
        "created": created,
        "binding_created": binding_created,
        "binding_reused": binding_reused,
        "secret": secret,
        "binding": binding,
    }
    if resolved is not None:
        result["value"] = resolved.get("value")
        result["matched_by"] = resolved.get("matched_by", "")

    if args.json_output:
        _print_json(result)
    else:
        _print_secret_human(
            secret,
            include_bindings=True,
            binding=binding if isinstance(binding, dict) else None,
            value=result.get("value") if bool(getattr(args, "reveal", False)) else None,
            matched_by=str(result.get("matched_by", "") or ""),
        )
        print(f"secret.created={str(created).lower()}")
        print(f"binding.created={str(binding_created).lower()}")
        print(f"binding.reused={str(binding_reused).lower()}")
    return 0


def cmd_secrets_update(args: argparse.Namespace) -> int:
    secret_ref = str(getattr(args, "secret_ref", "") or "").strip()
    if not secret_ref:
        raise RuntimeError("Secret reference is required.")

    body: dict[str, Any] = {}
    for attr_name, body_key in (
        ("alias", "alias"),
        ("label", "label"),
        ("provider", "provider"),
        ("kind", "kind"),
        ("env_var_name", "envVarName"),
        ("notes", "notes"),
        ("status", "status"),
    ):
        value = getattr(args, attr_name, None)
        if value is not None:
            text = str(value).strip()
            if body_key in {"envVarName", "notes"}:
                body[body_key] = text or None
            else:
                body[body_key] = text

    value_provided, value = _resolve_secret_value_arg(args, required=False)
    if value_provided:
        body["value"] = value

    if not body:
        raise RuntimeError("Provide at least one field to update.")

    payload = _request_secret_payload(
        args,
        path=f"/api/cli/secrets/{urlparse.quote(secret_ref)}",
        method="PATCH",
        body=body,
    )
    secret = payload.get("secret") if isinstance(payload.get("secret"), dict) else payload
    if not isinstance(secret, dict):
        raise RuntimeError("Hosted ORP returned an invalid secret record.")
    result = {
        "ok": bool(payload.get("ok", True)),
        "secret": secret,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_secret_human(secret, include_bindings=True)
    return 0


def cmd_secrets_archive(args: argparse.Namespace) -> int:
    secret_ref = str(getattr(args, "secret_ref", "") or "").strip()
    if not secret_ref:
        raise RuntimeError("Secret reference is required.")
    payload = _request_secret_payload(
        args,
        path=f"/api/cli/secrets/{urlparse.quote(secret_ref)}",
        method="DELETE",
    )
    secret = payload.get("secret") if isinstance(payload.get("secret"), dict) else payload
    if not isinstance(secret, dict):
        raise RuntimeError("Hosted ORP returned an invalid secret record.")
    result = {
        "ok": bool(payload.get("ok", True)),
        "secret": secret,
        "removed_secret_id": str(payload.get("removedSecretId", secret.get("id", ""))).strip(),
        "archived": bool(payload.get("archived", True)),
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_secret_human(secret, include_bindings=True)
        print(f"removed_secret_id={result['removed_secret_id']}")
        print(f"archived={str(result['archived']).lower()}")
    return 0


def cmd_secrets_bind(args: argparse.Namespace) -> int:
    secret_ref = str(getattr(args, "secret_ref", "") or "").strip()
    if not secret_ref:
        raise RuntimeError("Secret reference is required.")
    world_id, idea_id = _resolve_secret_scope_from_args(
        args,
        require_scope=True,
        fallback_to_current_project=True,
    )
    body: dict[str, Any] = {
        "secretId" if _looks_like_uuid(secret_ref) else "secretAlias": secret_ref,
    }
    if world_id:
        body["worldId"] = world_id
    if idea_id:
        body["ideaId"] = idea_id
    purpose = str(getattr(args, "purpose", "") or "").strip()
    if purpose:
        body["purpose"] = purpose
    if bool(getattr(args, "primary", False)):
        body["isPrimary"] = True

    payload = _request_secret_payload(
        args,
        path="/api/cli/secrets/bindings",
        method="POST",
        body=body,
    )
    binding = payload.get("binding") if isinstance(payload.get("binding"), dict) else payload
    if not isinstance(binding, dict):
        raise RuntimeError("Hosted ORP returned an invalid binding record.")
    result = {
        "ok": bool(payload.get("ok", True)),
        "binding": binding,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("binding.id", str(binding.get("id", "")).strip()),
                ("binding.world_id", str(binding.get("worldId", "")).strip()),
                ("binding.idea_id", str(binding.get("ideaId", "")).strip()),
                ("binding.secret_id", str(binding.get("secretId", "")).strip()),
                ("binding.primary", str(bool(binding.get("isPrimary", False))).lower()),
            ]
        )
    return 0


def cmd_secrets_unbind(args: argparse.Namespace) -> int:
    binding_id = str(getattr(args, "binding_id", "") or "").strip()
    if not binding_id:
        raise RuntimeError("Binding id is required.")
    payload = _request_secret_payload(
        args,
        path=f"/api/cli/secrets/bindings/{urlparse.quote(binding_id)}",
        method="DELETE",
    )
    binding = payload.get("binding") if isinstance(payload.get("binding"), dict) else {}
    result = {
        "ok": bool(payload.get("ok", True)),
        "removed_binding_id": str(payload.get("removedBindingId", binding_id)).strip(),
        "binding": binding,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("removed_binding_id", result["removed_binding_id"]),
                ("binding.secret_id", str(binding.get("secretId", "")).strip()),
                ("binding.world_id", str(binding.get("worldId", "")).strip()),
            ]
        )
    return 0


def cmd_secrets_resolve(args: argparse.Namespace) -> int:
    secret_ref = str(getattr(args, "secret_ref", "") or "").strip()
    provider = str(getattr(args, "provider", "") or "").strip()
    reveal = bool(getattr(args, "reveal", False))
    local_first = bool(getattr(args, "local_first", False))
    local_only = bool(getattr(args, "local_only", False))
    sync_keychain = bool(getattr(args, "sync_keychain", False))
    if local_first and local_only:
        raise RuntimeError("Use either --local-first or --local-only, not both.")

    result: dict[str, Any] | None = None
    if local_first or local_only:
        result = _resolve_secret_from_keychain(
            args,
            secret_ref=secret_ref,
            provider=provider,
            reveal=reveal,
        )
        if result is None and local_only:
            raise RuntimeError("No matching local Keychain secret was found.")

    if result is None:
        result = _resolve_secret_from_hosted(
            args,
            secret_ref=secret_ref,
            provider=provider,
            reveal=reveal,
        )
        if sync_keychain:
            if not reveal:
                raise RuntimeError("--sync-keychain requires --reveal so ORP can securely cache the resolved value locally.")
            _sync_secret_to_keychain(
                result["secret"],
                value=str(result.get("value") or ""),
                binding=result.get("binding") if isinstance(result.get("binding"), dict) else None,
            )
    if args.json_output:
        _print_json(result)
    else:
        _print_secret_human(
            result["secret"],
            include_bindings=False,
            binding=result.get("binding") if isinstance(result.get("binding"), dict) else None,
            value=result["value"] if reveal else None,
            matched_by=result["matched_by"],
            source=str(result.get("source", "")).strip(),
        )
    return 0


def cmd_secrets_keychain_list(args: argparse.Namespace) -> int:
    provider = str(getattr(args, "provider", "") or "").strip()
    world_id, idea_id = _resolve_secret_scope_from_args(
        args,
        require_scope=False,
        fallback_to_current_project=bool(getattr(args, "current_project", False)),
    )
    items = _list_keychain_registry_entries(
        provider=provider,
        world_id=world_id,
        idea_id=idea_id,
    )
    result = {
        "ok": True,
        "items": items,
        "provider": provider,
        "world_id": world_id,
        "idea_id": idea_id,
        "registry_path": str(_keychain_secret_registry_path()),
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("local_secrets.count", len(items)),
                ("filter.provider", provider),
                ("filter.world_id", world_id),
                ("filter.idea_id", idea_id),
                ("registry.path", result["registry_path"]),
            ]
        )
        for row in items:
            print("---")
            _print_pairs(
                [
                    ("secret.id", str(row.get("secret_id", "")).strip()),
                    ("secret.alias", str(row.get("alias", "")).strip()),
                    ("secret.label", str(row.get("label", "")).strip()),
                    ("secret.provider", str(row.get("provider", "")).strip()),
                    ("secret.kind", str(row.get("kind", "")).strip()),
                    ("secret.env_var_name", str(row.get("env_var_name", "")).strip()),
                    ("secret.status", str(row.get("status", "")).strip()),
                    ("secret.binding_count", len(row.get("bindings", [])) if isinstance(row.get("bindings"), list) else 0),
                    ("keychain.service", str(row.get("keychain_service", "")).strip()),
                    ("keychain.account", str(row.get("keychain_account", "")).strip()),
                    ("last_synced_at", str(row.get("last_synced_at_utc", "")).strip()),
                ]
            )
    return 0


def cmd_secrets_keychain_show(args: argparse.Namespace) -> int:
    secret_ref = str(getattr(args, "secret_ref", "") or "").strip()
    if not secret_ref:
        raise RuntimeError("Secret reference is required.")
    items = _list_keychain_registry_entries(secret_ref=secret_ref)
    if not items:
        raise RuntimeError("No matching local Keychain secret was found.")
    entry = items[0]
    secret = _secret_payload_from_keychain_entry(entry)
    result = {
        "ok": True,
        "secret": secret,
        "registry_path": str(_keychain_secret_registry_path()),
        "keychain_service": str(entry.get("keychain_service", "")).strip(),
        "keychain_account": str(entry.get("keychain_account", "")).strip(),
        "last_synced_at_utc": str(entry.get("last_synced_at_utc", "")).strip(),
        "source": "keychain",
    }
    if bool(getattr(args, "reveal", False)):
        result["value"] = _read_keychain_secret_value(entry)
    if args.json_output:
        _print_json(result)
    else:
        _print_secret_human(
            secret,
            include_bindings=True,
            value=str(result.get("value")) if "value" in result else None,
            source="keychain",
        )
        _print_pairs(
            [
                ("keychain.service", result["keychain_service"]),
                ("keychain.account", result["keychain_account"]),
                ("registry.path", result["registry_path"]),
                ("last_synced_at", result["last_synced_at_utc"]),
            ]
        )
    return 0


def cmd_secrets_sync_keychain(args: argparse.Namespace) -> int:
    _ensure_keychain_supported()
    secret_ref = str(getattr(args, "secret_ref", "") or "").strip()
    provider = str(getattr(args, "provider", "") or "").strip()
    sync_all = bool(getattr(args, "all", False))

    synced_items: list[dict[str, Any]] = []

    if sync_all:
        params: list[str] = []
        if provider:
            params.append(f"provider={urlparse.quote(provider)}")
        world_id, idea_id = _resolve_secret_scope_from_args(args, require_scope=False, fallback_to_current_project=False)
        if world_id:
            params.append(f"worldId={urlparse.quote(world_id)}")
        if idea_id:
            params.append(f"ideaId={urlparse.quote(idea_id)}")
        query = f"?{'&'.join(params)}" if params else ""
        payload = _request_secret_payload(args, path=f"/api/cli/secrets{query}")
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        for row in items:
            if not isinstance(row, dict):
                continue
            ref = str(row.get("alias", "")).strip() or str(row.get("id", "")).strip()
            if not ref:
                continue
            resolved = _resolve_secret_from_hosted(
                args,
                secret_ref=ref,
                reveal=True,
            )
            entry = _sync_secret_to_keychain(
                resolved["secret"],
                value=str(resolved.get("value") or ""),
                binding=resolved.get("binding") if isinstance(resolved.get("binding"), dict) else None,
            )
            synced_items.append(entry)
    else:
        if not secret_ref and not provider:
            raise RuntimeError("Provide a secret reference, --provider, or use --all.")
        resolved = _resolve_secret_from_hosted(
            args,
            secret_ref=secret_ref,
            provider=provider,
            reveal=True,
        )
        entry = _sync_secret_to_keychain(
            resolved["secret"],
            value=str(resolved.get("value") or ""),
            binding=resolved.get("binding") if isinstance(resolved.get("binding"), dict) else None,
        )
        synced_items.append(entry)

    result = {
        "ok": True,
        "count": len(synced_items),
        "items": synced_items,
        "registry_path": str(_keychain_secret_registry_path()),
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("synced.count", result["count"]),
                ("registry.path", result["registry_path"]),
            ]
        )
        for row in synced_items:
            print("---")
            _print_pairs(
                [
                    ("secret.id", str(row.get("secret_id", "")).strip()),
                    ("secret.alias", str(row.get("alias", "")).strip()),
                    ("secret.provider", str(row.get("provider", "")).strip()),
                    ("keychain.service", str(row.get("keychain_service", "")).strip()),
                    ("keychain.account", str(row.get("keychain_account", "")).strip()),
                    ("synced_at", str(row.get("last_synced_at_utc", "")).strip()),
                ]
            )
    return 0


def cmd_link_project_bind(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    _require_link_root(repo_root)
    session = _require_hosted_session(args)
    existing_link = _read_link_project(repo_root)
    primary_session = next((row for row in _list_link_sessions(repo_root) if row.get("primary")), {})
    project_root = _require_current_repo_project_root(
        getattr(args, "project_root", ""),
        repo_root,
        context="orp link project bind",
    )
    detected_remote_url = _git_stdout(repo_root, ["remote", "get-url", "origin"]) if _git_repo_present(repo_root) else ""
    github_url = (
        str(getattr(args, "github_url", "") or "").strip()
        or str(existing_link.get("github_url", "")).strip()
        or detected_remote_url
    )
    codex_session_id = (
        str(getattr(args, "codex_session_id", "") or "").strip()
        or str(primary_session.get("codex_session_id", "")).strip()
    )
    world_name = str(getattr(args, "name", "") or "").strip() or str(existing_link.get("world_name", "")).strip() or repo_root.name
    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas/{urlparse.quote(str(args.idea_id).strip())}/world",
        method="PUT",
        token=str(session.get("token", "")).strip(),
        body={
            "name": world_name,
            "projectRoot": project_root,
            "githubUrl": github_url or None,
            "codexSessionId": codex_session_id or None,
        },
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Hosted ORP returned an invalid world payload.")
    world = _normalize_remote_world_payload(payload)["world"]
    project_link = {
        "idea_id": str(args.idea_id).strip(),
        "idea_title": str(getattr(args, "idea_title", "") or "").strip()
        or str(existing_link.get("idea_title", "")).strip(),
        "world_id": str(world.get("id", "")).strip(),
        "world_name": str(world.get("name", "")).strip() or world_name,
        "project_root": project_root,
        "github_url": str(world.get("githubUrl", "")).strip() or github_url,
        "linked_at_utc": _now_utc(),
        "linked_email": str(session.get("email", "")).strip(),
        "source": "cli",
    }
    notes = str(getattr(args, "notes", "") or "").strip()
    if notes:
        project_link["notes"] = notes
    path = _write_link_project(repo_root, project_link)
    result = {
        "ok": True,
        "project_link": _read_link_project(repo_root),
        "project_link_path": _path_for_state(path, repo_root),
        "world": world,
        "session_counts": _link_session_counts(_list_link_sessions(repo_root)),
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("idea.id", result["project_link"].get("idea_id", "")),
                ("world.id", str(world.get("id", "")).strip()),
                ("world.name", str(world.get("name", "")).strip()),
                ("project.link_path", result["project_link_path"]),
                ("sessions.total", result["session_counts"]["total"]),
            ]
        )
    return 0


def cmd_link_project_show(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    project_link = _read_link_project(repo_root)
    if not project_link:
        raise RuntimeError("No local project link found. Run `orp link project bind --idea-id <idea-id> --json` first.")
    path = _link_project_path(repo_root)
    result = {
        "ok": True,
        "project_link": project_link,
        "project_link_path": _path_for_state(path, repo_root) if path is not None else "",
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("idea.id", project_link.get("idea_id", "")),
                ("idea.title", project_link.get("idea_title", "")),
                ("world.id", project_link.get("world_id", "")),
                ("world.name", project_link.get("world_name", "")),
                ("project.root", project_link.get("project_root", "")),
                ("project.link_path", result["project_link_path"]),
            ]
        )
    return 0


def cmd_link_project_status(args: argparse.Namespace) -> int:
    return cmd_link_status(args)


def cmd_link_project_unbind(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    project_link = _read_link_project(repo_root)
    path = _delete_link_project(repo_root)
    sessions = _list_link_sessions(repo_root)
    warnings: list[str] = []
    next_actions: list[str] = []
    if sessions:
        warnings.append("local session links remain after unbinding the project link.")
        next_actions.append("orp link session list --json")
    result = {
        "ok": True,
        "removed": path is not None,
        "removed_project_link": project_link,
        "project_link_path": _path_for_state(path, repo_root) if path is not None else "",
        "session_counts": _link_session_counts(sessions),
        "warnings": warnings,
        "next_actions": next_actions,
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"removed={'true' if result['removed'] else 'false'}")
        print(f"project.link_path={result['project_link_path']}")
        for warning in warnings:
            print(f"warning={warning}")
        for action_line in next_actions:
            print(f"next={action_line}")
    return 0


def cmd_link_session_register(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    _require_link_root(repo_root)
    existing = _read_link_session(repo_root, str(args.orp_session_id).strip())
    project_root = _require_current_repo_project_root(
        getattr(args, "project_root", ""),
        repo_root,
        context="orp link session register",
    )
    if (getattr(args, "window_id", None) is None) != (getattr(args, "tab_number", None) is None):
        raise RuntimeError("Provide both --window-id and --tab-number together.")

    payload: dict[str, Any] = {k: v for k, v in existing.items() if k != "path"}
    payload["orp_session_id"] = str(args.orp_session_id).strip()
    payload["label"] = str(args.label).strip()
    payload["project_root"] = project_root
    payload["state"] = str(getattr(args, "state", "") or payload.get("state", "active")).strip() or "active"
    payload["created_at_utc"] = _normalize_timestamp_utc(
        getattr(args, "created_at", None),
        fallback=str(payload.get("created_at_utc", "")) or _now_utc(),
    )
    payload["last_active_at_utc"] = _normalize_timestamp_utc(
        getattr(args, "last_active_at", None),
        fallback=str(payload.get("last_active_at_utc", "")) or payload["created_at_utc"],
    )
    archived_arg = getattr(args, "archived", None)
    payload["archived"] = bool(archived_arg) if archived_arg is not None else bool(payload.get("archived", False))
    primary_arg = getattr(args, "primary", None)
    payload["primary"] = (bool(primary_arg) if primary_arg is not None else bool(payload.get("primary", False))) and not payload["archived"]
    payload["source"] = "cli"

    codex_session_id = getattr(args, "codex_session_id", None)
    if codex_session_id is not None:
        text = str(codex_session_id).strip()
        if text:
            payload["codex_session_id"] = text
        else:
            payload.pop("codex_session_id", None)
    role = getattr(args, "role", None)
    if role is not None:
        text = str(role).strip().lower()
        if text:
            payload["role"] = text
        else:
            payload.pop("role", None)
    notes = getattr(args, "notes", None)
    if notes is not None:
        text = str(notes).strip()
        if text:
            payload["notes"] = text
        else:
            payload.pop("notes", None)
    if getattr(args, "window_id", None) is not None and getattr(args, "tab_number", None) is not None:
        payload["terminal_target"] = {
            "window_id": int(args.window_id),
            "tab_number": int(args.tab_number),
        }

    path = _write_link_session(repo_root, payload)
    if payload.get("primary"):
        _set_primary_link_session(repo_root, payload["orp_session_id"])
    primary_session = _rebalance_primary_link_session(repo_root)
    session = _read_link_session(repo_root, payload["orp_session_id"])
    result = {
        "ok": True,
        "created": not bool(existing),
        "session": session,
        "primary_session": primary_session,
        "session_path": _path_for_state(path, repo_root),
        "session_counts": _link_session_counts(_list_link_sessions(repo_root)),
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("session.id", session.get("orp_session_id", "")),
                ("session.label", session.get("label", "")),
                ("session.codex_session_id", session.get("codex_session_id", "")),
                ("session.primary", str(bool(session.get("primary"))).lower()),
                ("session.path", result["session_path"]),
            ]
        )
    return 0


def cmd_link_session_list(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    sessions = _list_link_sessions(repo_root)
    result = {
        "ok": True,
        "sessions": sessions,
        "session_counts": _link_session_counts(sessions),
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"sessions.total={result['session_counts']['total']}")
        for row in sessions:
            print("---")
            _print_pairs(
                [
                    ("session.id", row.get("orp_session_id", "")),
                    ("session.label", row.get("label", "")),
                    ("session.primary", str(bool(row.get("primary"))).lower()),
                    ("session.archived", str(bool(row.get("archived"))).lower()),
                    ("session.codex_session_id", row.get("codex_session_id", "")),
                    ("session.path", row.get("path", "")),
                ]
            )
    return 0


def cmd_link_session_show(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    session = _read_link_session(repo_root, str(args.orp_session_id).strip())
    if not session:
        raise RuntimeError(f"Linked session not found: {args.orp_session_id}")
    result = {
        "ok": True,
        "session": session,
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("session.id", session.get("orp_session_id", "")),
                ("session.label", session.get("label", "")),
                ("session.state", session.get("state", "")),
                ("session.primary", str(bool(session.get("primary"))).lower()),
                ("session.archived", str(bool(session.get("archived"))).lower()),
                ("session.codex_session_id", session.get("codex_session_id", "")),
                ("session.path", session.get("path", "")),
            ]
        )
    return 0


def cmd_link_session_set_primary(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    session = _read_link_session(repo_root, str(args.orp_session_id).strip())
    if not session:
        raise RuntimeError(f"Linked session not found: {args.orp_session_id}")
    if session.get("archived"):
        raise RuntimeError("Archived sessions cannot be marked primary. Unarchive the session first.")
    _set_primary_link_session(repo_root, str(args.orp_session_id).strip())
    primary_session = _rebalance_primary_link_session(repo_root)
    result = {
        "ok": True,
        "primary_session": primary_session,
        "session_counts": _link_session_counts(_list_link_sessions(repo_root)),
    }
    if args.json_output:
        _print_json(result)
    else:
        _print_pairs(
            [
                ("primary.orp_session_id", primary_session.get("orp_session_id", "")),
                ("primary.codex_session_id", primary_session.get("codex_session_id", "")),
            ]
        )
    return 0


def cmd_link_session_archive(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    session = _read_link_session(repo_root, str(args.orp_session_id).strip())
    if not session:
        raise RuntimeError(f"Linked session not found: {args.orp_session_id}")
    payload = {k: v for k, v in session.items() if k != "path"}
    payload["archived"] = True
    payload["primary"] = False
    _write_link_session(repo_root, payload)
    primary_session = _rebalance_primary_link_session(repo_root)
    result = {
        "ok": True,
        "session": _read_link_session(repo_root, str(args.orp_session_id).strip()),
        "primary_session": primary_session,
        "session_counts": _link_session_counts(_list_link_sessions(repo_root)),
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"archived=true")
        print(f"session.id={result['session'].get('orp_session_id', '')}")
    return 0


def cmd_link_session_unarchive(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    session = _read_link_session(repo_root, str(args.orp_session_id).strip())
    if not session:
        raise RuntimeError(f"Linked session not found: {args.orp_session_id}")
    payload = {k: v for k, v in session.items() if k != "path"}
    payload["archived"] = False
    _write_link_session(repo_root, payload)
    primary_session = _rebalance_primary_link_session(repo_root)
    result = {
        "ok": True,
        "session": _read_link_session(repo_root, str(args.orp_session_id).strip()),
        "primary_session": primary_session,
        "session_counts": _link_session_counts(_list_link_sessions(repo_root)),
    }
    if args.json_output:
        _print_json(result)
    else:
        print("archived=false")
        print(f"session.id={result['session'].get('orp_session_id', '')}")
    return 0


def cmd_link_session_remove(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    session = _read_link_session(repo_root, str(args.orp_session_id).strip())
    if not session:
        raise RuntimeError(f"Linked session not found: {args.orp_session_id}")
    path = _delete_link_session(repo_root, str(args.orp_session_id).strip())
    primary_session = _rebalance_primary_link_session(repo_root)
    result = {
        "ok": True,
        "removed": path is not None,
        "removed_session": session,
        "session_path": _path_for_state(path, repo_root) if path is not None else "",
        "primary_session": primary_session,
        "session_counts": _link_session_counts(_list_link_sessions(repo_root)),
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"removed={'true' if result['removed'] else 'false'}")
        print(f"session.id={session.get('orp_session_id', '')}")
        print(f"session.path={result['session_path']}")
    return 0


def cmd_link_session_import_rust(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    _require_link_root(repo_root)
    rust_project_path = repo_root / ".orp" / "project.json"
    rust_sessions_dir = repo_root / ".orp" / "sessions"
    project_metadata = _read_json_if_exists(rust_project_path)
    if not project_metadata and not rust_sessions_dir.exists():
        raise RuntimeError("No Rust ORP metadata found under .orp/.")

    imported_project: dict[str, Any] = {}
    project_link_path = ""
    hosted_link = project_metadata.get("hosted_link") if isinstance(project_metadata.get("hosted_link"), dict) else {}
    if hosted_link:
        idea_id = str(hosted_link.get("idea_id", hosted_link.get("ideaId", ""))).strip()
        if idea_id:
            imported_project = {
                "idea_id": idea_id,
                "idea_title": str(hosted_link.get("idea_title", hosted_link.get("ideaTitle", ""))).strip(),
                "world_id": str(hosted_link.get("world_id", hosted_link.get("worldId", ""))).strip(),
                "world_name": str(hosted_link.get("world_name", hosted_link.get("worldName", ""))).strip(),
                "project_root": _normalize_local_path(
                    project_metadata.get("project_path", project_metadata.get("projectPath", str(repo_root))),
                    repo_root,
                    fallback=str(repo_root),
                ),
                "github_url": str(project_metadata.get("github_remote", project_metadata.get("githubRemote", ""))).strip(),
                "linked_at_utc": _normalize_timestamp_utc(
                    hosted_link.get("linked_at", hosted_link.get("linkedAt")),
                    fallback=_now_utc(),
                ),
                "linked_email": str(hosted_link.get("linked_email", hosted_link.get("linkedEmail", ""))).strip(),
                "source": "import-rust",
                "notes": "Imported from Rust ORP project metadata.",
            }
            project_link_path = _path_for_state(_write_link_project(repo_root, imported_project), repo_root)
            imported_project = _read_link_project(repo_root)

    archived_session_ids = {
        str(item).strip()
        for item in project_metadata.get("archived_session_ids", [])
        if isinstance(item, str) and str(item).strip()
    }
    archived_codex_session_ids = {
        str(item).strip()
        for item in project_metadata.get("archived_codex_session_ids", [])
        if isinstance(item, str) and str(item).strip()
    }
    ignored_codex_session_ids = [
        str(item).strip()
        for item in project_metadata.get("ignored_codex_session_ids", [])
        if isinstance(item, str) and str(item).strip()
    ]
    session_order = [
        str(item).strip()
        for item in project_metadata.get("session_order", [])
        if isinstance(item, str) and str(item).strip()
    ]

    imported_sessions: list[dict[str, Any]] = []
    skipped_paths: list[str] = []
    rust_session_payloads: list[dict[str, Any]] = []
    if rust_sessions_dir.exists():
        for path in sorted(rust_sessions_dir.glob("*.json")):
            raw = _read_json_if_exists(path)
            if not raw:
                skipped_paths.append(_path_for_state(path, repo_root))
                continue
            session_id = str(raw.get("session_id", raw.get("sessionId", ""))).strip()
            label = str(raw.get("label", "")).strip()
            if not session_id or not label:
                skipped_paths.append(_path_for_state(path, repo_root))
                continue
            codex_session_id = str(raw.get("codex_session_id", raw.get("codexSessionId", ""))).strip()
            archived = session_id in archived_session_ids or (codex_session_id and codex_session_id in archived_codex_session_ids)
            rust_session_payloads.append(
                {
                    "orp_session_id": session_id,
                    "label": label,
                    "state": str(raw.get("state", "active")).strip().lower() or "active",
                    "project_root": _normalize_local_path(
                        raw.get("project_path", raw.get("projectPath", str(repo_root))),
                        repo_root,
                        fallback=str(repo_root),
                    ),
                    "codex_session_id": codex_session_id,
                    "terminal_target": raw.get("terminal_target", raw.get("terminalTarget")),
                    "created_at_utc": _normalize_timestamp_utc(
                        raw.get("created_at", raw.get("createdAt")),
                        fallback=_now_utc(),
                    ),
                    "last_active_at_utc": _normalize_timestamp_utc(
                        raw.get("last_active_at", raw.get("lastActiveAt")),
                        fallback=_normalize_timestamp_utc(raw.get("created_at", raw.get("createdAt")), fallback=_now_utc()),
                    ),
                    "archived": archived,
                    "primary": False,
                    "source": "import-rust",
                    "notes": "Imported from Rust ORP session metadata.",
                }
            )

    primary_session_id = ""
    session_lookup = {row["orp_session_id"]: row for row in rust_session_payloads}
    for session_id in session_order:
        row = session_lookup.get(session_id)
        if row and not row.get("archived"):
            primary_session_id = session_id
            break
    if not primary_session_id:
        sorted_candidates = sorted(rust_session_payloads, key=_link_session_sort_key)
        for row in sorted_candidates:
            if not row.get("archived"):
                primary_session_id = row["orp_session_id"]
                break

    for row in rust_session_payloads:
        row["primary"] = row["orp_session_id"] == primary_session_id and not row.get("archived")
        _write_link_session(repo_root, row)
        imported_sessions.append(_read_link_session(repo_root, row["orp_session_id"]))

    primary_session = _rebalance_primary_link_session(repo_root)
    result = {
        "ok": True,
        "imported_project": bool(imported_project),
        "project_link": imported_project,
        "project_link_path": project_link_path,
        "imported_sessions": imported_sessions,
        "imported_session_count": len(imported_sessions),
        "primary_session": primary_session,
        "session_counts": _link_session_counts(_list_link_sessions(repo_root)),
        "rust_project_path": _path_for_state(rust_project_path, repo_root),
        "rust_sessions_dir": _path_for_state(rust_sessions_dir, repo_root),
        "ignored_codex_session_ids": ignored_codex_session_ids,
        "skipped_paths": skipped_paths,
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"imported_project={'true' if result['imported_project'] else 'false'}")
        print(f"imported_sessions={result['imported_session_count']}")
        print(f"primary.orp_session_id={primary_session.get('orp_session_id', '')}")
        for path in skipped_paths:
            print(f"warning=skipped invalid Rust session metadata at {path}")
    return 0


def cmd_link_import_rust(args: argparse.Namespace) -> int:
    if not bool(getattr(args, "all", False)):
        raise RuntimeError("`orp link import-rust` requires `--all` to confirm importing project and session metadata.")
    return cmd_link_session_import_rust(args)


def cmd_link_status(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    result = _link_status_payload(repo_root, args)
    if args.json_output:
        _print_json(result)
    else:
        _print_link_status_human(result)
    return 0


def cmd_link_doctor(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    status_payload = _link_status_payload(repo_root, args)
    issues: list[dict[str, Any]] = []

    if not _git_repo_present(repo_root):
        issues.append(
            _doctor_issue(
                severity="error",
                code="missing_git_repo",
                message="git repository not detected at repo root.",
                fixable=False,
            )
        )

    project_link_path = _link_project_path(repo_root)
    project_link = status_payload.get("project_link", {}) if isinstance(status_payload.get("project_link"), dict) else {}
    if project_link_path is not None and project_link_path.exists() and not project_link:
        issues.append(
            _doctor_issue(
                severity="error",
                code="invalid_project_link_record",
                message="local project link file exists but could not be parsed as a valid linked project.",
                fixable=False,
                path=_path_for_state(project_link_path, repo_root),
            )
        )
    if project_link:
        if str(project_link.get("project_root", "")).strip() != str(repo_root):
            issues.append(
                _doctor_issue(
                    severity="warning",
                    code="project_root_mismatch",
                    message="linked project root does not match the current repo root.",
                    fixable=False,
                    path=_path_for_state(project_link_path, repo_root) if project_link_path is not None else "",
                )
            )
        if not status_payload.get("hosted_auth", {}).get("connected"):
            issues.append(
                _doctor_issue(
                    severity="warning",
                    code="missing_hosted_auth",
                    message="hosted auth is missing for the linked project.",
                    fixable=False,
                )
            )

    sessions = status_payload.get("sessions", []) if isinstance(status_payload.get("sessions"), list) else []
    if project_link and not sessions:
        issues.append(
            _doctor_issue(
                severity="warning",
                code="linked_project_without_sessions",
                message="project link exists but no linked sessions are registered.",
                fixable=False,
            )
        )
    if sessions and not project_link:
        issues.append(
            _doctor_issue(
                severity="warning",
                code="sessions_without_project_link",
                message="linked sessions exist but the repo is not linked to a hosted idea/world.",
                fixable=False,
            )
        )

    primary_sessions = [row for row in sessions if row.get("primary")]
    if len(primary_sessions) > 1:
        issues.append(
            _doctor_issue(
                severity="error",
                code="multiple_primary_sessions",
                message="multiple linked sessions are marked primary.",
                fixable=False,
            )
        )
    elif sessions and not primary_sessions:
        issues.append(
            _doctor_issue(
                severity="warning",
                code="missing_primary_session",
                message="no linked session is marked primary.",
                fixable=False,
            )
        )

    sessions_dir = _link_sessions_dir(repo_root)
    if sessions_dir is not None and sessions_dir.exists():
        for path in sorted(sessions_dir.glob("*.json")):
            raw = _read_json_if_exists(path)
            if not raw:
                issues.append(
                    _doctor_issue(
                        severity="error",
                        code="invalid_session_link_record",
                        message="linked session file exists but could not be parsed.",
                        fixable=False,
                        path=_path_for_state(path, repo_root),
                    )
                )
                continue
            try:
                session = _normalize_link_session_payload(
                    raw,
                    repo_root,
                    default_source=str(raw.get("source", "cli")).strip() or "cli",
                )
            except RuntimeError as exc:
                issues.append(
                    _doctor_issue(
                        severity="error",
                        code="invalid_session_link_record",
                        message=str(exc),
                        fixable=False,
                        path=_path_for_state(path, repo_root),
                    )
                )
                continue
            if str(session.get("project_root", "")).strip() != str(repo_root):
                issues.append(
                    _doctor_issue(
                        severity="warning",
                        code="session_project_root_mismatch",
                        message=f"linked session `{session['orp_session_id']}` points at a different project root.",
                        fixable=False,
                        path=_path_for_state(path, repo_root),
                    )
                )
            if not session.get("archived") and str(session.get("state", "active")).strip() == "active" and not str(session.get("codex_session_id", "")).strip():
                issues.append(
                    _doctor_issue(
                        severity="warning",
                        code="missing_codex_session_id",
                        message=f"active linked session `{session['orp_session_id']}` is missing a Codex session id.",
                        fixable=False,
                        path=_path_for_state(path, repo_root),
                    )
                )

    hosted_world = status_payload.get("hosted_world", {}) if isinstance(status_payload.get("hosted_world"), dict) else {}
    if status_payload.get("hosted_world_error"):
        issues.append(
            _doctor_issue(
                severity="warning",
                code="hosted_world_unavailable",
                message=str(status_payload.get("hosted_world_error", "")).strip(),
                fixable=False,
            )
        )
    if project_link and hosted_world:
        remote_root = _normalize_local_path(hosted_world.get("projectRoot", ""), repo_root)
        if remote_root and remote_root != str(project_link.get("project_root", "")).strip():
            issues.append(
                _doctor_issue(
                    severity="warning",
                    code="hosted_world_project_root_mismatch",
                    message="hosted world project root does not match the local linked project root.",
                    fixable=False,
                )
            )
        remote_world_id = str(hosted_world.get("id", "")).strip()
        local_world_id = str(project_link.get("world_id", "")).strip()
        if remote_world_id and local_world_id and remote_world_id != local_world_id:
            issues.append(
                _doctor_issue(
                    severity="warning",
                    code="hosted_world_id_mismatch",
                    message="hosted world id does not match the locally recorded world id.",
                    fixable=False,
                )
            )

    errors = sum(1 for issue in issues if issue.get("severity") == "error")
    warnings_count = sum(1 for issue in issues if issue.get("severity") == "warning")
    ok = errors == 0 and (warnings_count == 0 or not bool(getattr(args, "strict", False)))
    result = {
        "ok": ok,
        "errors": errors,
        "warnings": warnings_count,
        "issues": issues,
        "status": status_payload,
    }
    if args.json_output:
        _print_json(result)
    else:
        print(f"ok={'true' if ok else 'false'}")
        print(f"errors={errors}")
        print(f"warnings={warnings_count}")
        for issue in issues:
            print(
                "issue="
                + ",".join(
                    [
                        f"severity={issue.get('severity', '')}",
                        f"code={issue.get('code', '')}",
                        f"message={issue.get('message', '')}",
                    ]
                )
            )
    return 0 if ok else 1


def cmd_runner_status(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    result = _runner_status_payload(repo_root, args)
    if args.json_output:
        _print_json(result)
    else:
        _print_runner_status_human(result)
    return 0


def cmd_runner_enable(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    hosted_session = _load_hosted_session()
    machine_update: dict[str, Any] = {
        "runner_enabled": True,
    }
    linked_email = str(hosted_session.get("email", "")).strip()
    if linked_email:
        machine_update["linked_email"] = linked_email
    machine_path = _save_runner_machine(machine_update)
    machine = _load_runner_machine()
    repo_runner_path = ""
    if _git_repo_present(repo_root):
        repo_runner_path = _path_for_state(_write_runner_repo_state(repo_root, machine), repo_root)
    result = {
        "ok": True,
        "machine": machine,
        "machine_path": str(machine_path),
        "repo_runner_path": repo_runner_path,
        "repo_has_git": _git_repo_present(repo_root),
    }
    if args.json_output:
        _print_json(result)
    else:
        print("runner.enabled=true")
        print(f"machine.id={machine.get('machine_id', '')}")
        print(f"machine.path={result['machine_path']}")
        print(f"repo.runner_path={repo_runner_path}")
    return 0


def cmd_runner_disable(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    machine_path = _save_runner_machine({"runner_enabled": False})
    machine = _load_runner_machine()
    repo_runner_path = ""
    if _git_repo_present(repo_root):
        repo_runner_path = _path_for_state(_write_runner_repo_state(repo_root, machine), repo_root)
    result = {
        "ok": True,
        "machine": machine,
        "machine_path": str(machine_path),
        "repo_runner_path": repo_runner_path,
        "repo_has_git": _git_repo_present(repo_root),
    }
    if args.json_output:
        _print_json(result)
    else:
        print("runner.enabled=false")
        print(f"machine.id={machine.get('machine_id', '')}")
        print(f"machine.path={result['machine_path']}")
        print(f"repo.runner_path={repo_runner_path}")
    return 0


def cmd_runner_heartbeat(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    machine = _load_runner_machine()
    if not machine.get("runner_enabled"):
        raise RuntimeError("Runner is disabled. Run `orp runner enable --json` first.")
    session = _require_hosted_session(args)
    result = {
        "ok": True,
        **_perform_runner_heartbeat(repo_root, args, session, machine),
    }
    if args.json_output:
        _print_json(result)
    else:
        print("ok=true")
        print(f"heartbeat_at_utc={result['heartbeat_at_utc']}")
        print(f"machine.id={result['machine'].get('machine_id', '')}")
        print(f"machine.path={result['machine_path']}")
        print(f"repo.runner_path={result['repo_runner_path']}")
    return 0


def cmd_runner_sync(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    machine = _load_runner_machine()
    if not machine.get("runner_enabled"):
        raise RuntimeError("Runner is disabled. Run `orp runner enable --json` first.")
    session = _require_hosted_session(args)
    candidate_roots = _normalize_runner_sync_roots(
        repo_root,
        getattr(args, "linked_project_roots", None),
    )
    if not any(_git_repo_present(root) for root in candidate_roots):
        raise RuntimeError("git repository not detected for any requested sync root. Run `orp init` or `git init` first.")
    sync_result = _perform_runner_sync_for_roots(
        repo_root,
        candidate_roots,
        args,
        session,
        machine,
    )
    result = {
        "ok": True,
        **sync_result,
    }
    if args.json_output:
        _print_json(result)
    else:
        print("ok=true")
        print(f"linked_projects={result['linked_projects']}")
        print(f"sessions={result['sessions']}")
        print(f"routeable_sessions={result['routeable_sessions']}")
        print(f"included_project_roots={len(result['included_project_roots'])}")
        print(f"skipped_project_roots={len(result['skipped_project_roots'])}")
        print(f"machine.path={result['machine_path']}")
        print(f"repo.runner_path={result['repo_runner_path']}")
    return 0


def cmd_runner_work(args: argparse.Namespace) -> int:
    poll_interval = max(1, int(getattr(args, "poll_interval", 30)))
    if bool(getattr(args, "once", False)):
        result = _run_runner_work_once(args)
        if args.json_output:
            _print_json(result)
        else:
            if not result.get("claimed"):
                print("job.claimed=false")
                print("job.status=idle")
            else:
                print("job.claimed=true")
                print(f"job.id={str(result.get('job', {}).get('id', '')).strip()}")
                print(f"job.kind={str(result.get('job', {}).get('kind', '')).strip()}")
                if result.get("dry_run"):
                    print("job.mode=dry-run")
                else:
                    session = result.get("selected_session", {}) if isinstance(result.get("selected_session"), dict) else {}
                    selected_repo_root = str(result.get("selected_repo_root", "")).strip()
                    lease = result.get("lease", {}) if isinstance(result.get("lease"), dict) else {}
                    if selected_repo_root:
                        print(f"repo.root={selected_repo_root}")
                    print(f"lease.id={str(lease.get('lease_id', '')).strip()}")
                    print(f"session.id={str(session.get('orp_session_id', '')).strip()}")
                    print(f"session.codex_session_id={str(session.get('codex_session_id', '')).strip()}")
                    print(f"response.ok={str(bool(result.get('ok', False))).lower()}")
                    if result.get("runtime_path"):
                        print(f"runtime.path={str(result.get('runtime_path', '')).strip()}")
                    if result.get("error"):
                        print(f"error={str(result.get('error', '')).strip()}")
                    if result.get("heartbeat_error"):
                        print(f"heartbeat_error={str(result.get('heartbeat_error', '')).strip()}")
        return 0 if result.get("ok", True) else 1

    while True:
        result = _run_runner_work_once(args)
        if args.json_output:
            _print_json(result)
        else:
            if not result.get("claimed"):
                print("job.claimed=false")
                print("job.status=idle")
            else:
                print("job.claimed=true")
                print(f"job.id={str(result.get('job', {}).get('id', '')).strip()}")
                print(f"job.kind={str(result.get('job', {}).get('kind', '')).strip()}")
                if result.get("dry_run"):
                    print("job.mode=dry-run")
                else:
                    session = result.get("selected_session", {}) if isinstance(result.get("selected_session"), dict) else {}
                    selected_repo_root = str(result.get("selected_repo_root", "")).strip()
                    lease = result.get("lease", {}) if isinstance(result.get("lease"), dict) else {}
                    if selected_repo_root:
                        print(f"repo.root={selected_repo_root}")
                    print(f"lease.id={str(lease.get('lease_id', '')).strip()}")
                    print(f"session.id={str(session.get('orp_session_id', '')).strip()}")
                    print(f"session.codex_session_id={str(session.get('codex_session_id', '')).strip()}")
                    print(f"response.ok={str(bool(result.get('ok', False))).lower()}")
                    if result.get("runtime_path"):
                        print(f"runtime.path={str(result.get('runtime_path', '')).strip()}")
                    if result.get("error"):
                        print(f"error={str(result.get('error', '')).strip()}")
                    if result.get("heartbeat_error"):
                        print(f"heartbeat_error={str(result.get('heartbeat_error', '')).strip()}")
        sys.stdout.flush()
        if not result.get("ok", True):
            return 1
        if result.get("claimed"):
            continue
        _wait_for_next_runner_cycle(args, poll_interval)


def _runner_control_job_payload(target: dict[str, Any], job_id: str) -> dict[str, Any]:
    job = target.get("job", {}) if isinstance(target.get("job"), dict) else {}
    payload: dict[str, Any] = {
        "id": str(job.get("job_id", job.get("id", job_id))).strip() or job_id,
    }
    job_kind = str(job.get("job_kind", job.get("kind", ""))).strip()
    if job_kind:
        payload["kind"] = job_kind
    idea_id = str(job.get("idea_id", "")).strip()
    if idea_id:
        payload["ideaId"] = idea_id
    world_id = str(job.get("world_id", "")).strip()
    if world_id:
        payload["worldId"] = world_id
    project_root = str(job.get("project_root", "")).strip()
    if project_root:
        payload["payload"] = {"projectRoot": project_root}
    return payload


def cmd_runner_cancel(args: argparse.Namespace) -> int:
    requested_repo_root = Path(args.repo_root).resolve()
    candidate_roots = _normalize_runner_sync_roots(
        requested_repo_root,
        getattr(args, "linked_project_roots", None),
    )
    repo_root, target = _resolve_runner_control_target_for_roots(
        candidate_roots,
        job_id=str(getattr(args, "job_id", "") or "").strip(),
        lease_id=str(getattr(args, "lease_id", "") or "").strip(),
        prefer_last_job=False,
    )
    job_id = str(target.get("job_id", "")).strip()
    lease_id = str(target.get("lease_id", "")).strip()
    if not job_id:
        raise RuntimeError("No active runner job is recorded locally. Provide a job id explicitly or run `orp runner status --json` first.")
    session = _require_hosted_session(args)
    machine = _load_runner_machine()
    reason = str(getattr(args, "reason", "") or "").strip()
    response = _runner_post_job_update(
        args=args,
        session=session,
        path=f"/api/cli/runner/jobs/{urlparse.quote(job_id)}/cancel",
        body={
            "machineId": str(machine.get("machine_id", "")).strip(),
            "leaseId": lease_id or None,
            "reason": reason or None,
        },
    )
    runtime, runtime_path = _record_runner_finish(
        repo_root,
        _runner_control_job_payload(target, job_id),
        final_status="cancelled",
        lease_id=lease_id,
        summary="Hosted runner job cancelled.",
        error=reason,
    )
    result = {
        "ok": True,
        "job_id": job_id,
        "lease_id": lease_id,
        "repo_root": str(repo_root),
        "target_source": str(target.get("source", "")).strip(),
        "response": response if isinstance(response, dict) else {},
        "runtime": runtime,
        "runtime_path": _path_for_state(runtime_path, repo_root),
    }
    if args.json_output:
        _print_json(result)
    else:
        print("ok=true")
        print(f"job.id={job_id}")
        print(f"lease.id={lease_id}")
        print(f"repo.root={result['repo_root']}")
        print(f"runtime.path={result['runtime_path']}")
    return 0


def cmd_runner_retry(args: argparse.Namespace) -> int:
    requested_repo_root = Path(args.repo_root).resolve()
    candidate_roots = _normalize_runner_sync_roots(
        requested_repo_root,
        getattr(args, "linked_project_roots", None),
    )
    repo_root, target = _resolve_runner_control_target_for_roots(
        candidate_roots,
        job_id=str(getattr(args, "job_id", "") or "").strip(),
        lease_id=str(getattr(args, "lease_id", "") or "").strip(),
        prefer_last_job=True,
    )
    job_id = str(target.get("job_id", "")).strip()
    lease_id = str(target.get("lease_id", "")).strip()
    if not job_id:
        raise RuntimeError("No runner job is recorded locally for retry. Provide a job id explicitly or run `orp runner status --json` first.")
    session = _require_hosted_session(args)
    machine = _load_runner_machine()
    reason = str(getattr(args, "reason", "") or "").strip()
    response = _runner_post_job_update(
        args=args,
        session=session,
        path=f"/api/cli/runner/jobs/{urlparse.quote(job_id)}/retry",
        body={
            "machineId": str(machine.get("machine_id", "")).strip(),
            "leaseId": lease_id or None,
            "reason": reason or None,
        },
    )
    runtime, runtime_path = _record_runner_finish(
        repo_root,
        _runner_control_job_payload(target, job_id),
        final_status="retried",
        lease_id=lease_id,
        summary="Hosted runner job requeued for retry.",
        error=reason,
    )
    result = {
        "ok": True,
        "job_id": job_id,
        "lease_id": lease_id,
        "repo_root": str(repo_root),
        "target_source": str(target.get("source", "")).strip(),
        "response": response if isinstance(response, dict) else {},
        "runtime": runtime,
        "runtime_path": _path_for_state(runtime_path, repo_root),
    }
    if args.json_output:
        _print_json(result)
    else:
        print("ok=true")
        print(f"job.id={job_id}")
        print(f"lease.id={lease_id}")
        print(f"repo.root={result['repo_root']}")
        print(f"runtime.path={result['runtime_path']}")
    return 0


def cmd_checkpoint_queue(args: argparse.Namespace) -> int:
    session = _require_hosted_session(args)
    body: dict[str, Any] = {
        "triggerType": str(getattr(args, "trigger_type", "agent-feedback")).strip() or "agent-feedback",
        "contextSelection": _build_checkpoint_context_selection(args),
    }
    world_id = str(getattr(args, "world_id", "")).strip()
    if world_id:
        body["worldId"] = world_id
    focus_feature = str(getattr(args, "focus_feature", "")).strip()
    if focus_feature:
        body["featureId"] = focus_feature
    focus_detail = str(getattr(args, "focus_detail_section", "")).strip()
    if focus_detail:
        body["detailSectionId"] = focus_detail

    payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/ideas/{urlparse.quote(args.idea_id)}/checkpoints",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body=body,
    )
    if args.json_output:
        _print_json(payload)
    else:
        _print_pairs(
            [
                ("checkpoint.id", str(payload.get("id", "")).strip()),
                ("checkpoint.status", str(payload.get("status", "")).strip()),
                ("checkpoint.world_id", str(payload.get("worldId", "")).strip()),
                ("checkpoint.idea_id", str(payload.get("ideaId", "")).strip()),
            ]
        )
    return 0


def _run_worker_once(args: argparse.Namespace) -> dict[str, Any]:
    session = _require_hosted_session(args)
    agent = str(getattr(args, "agent", "")).strip()
    query = f"?agent={urlparse.quote(agent)}" if agent else ""
    job_payload = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/agent/jobs/poll{query}",
        token=str(session.get("token", "")).strip(),
    )
    job = job_payload.get("job") if isinstance(job_payload.get("job"), dict) else job_payload
    if not isinstance(job, dict) or not job:
        return {
            "ok": True,
            "claimed": False,
            "job": None,
        }

    if bool(getattr(args, "dry_run", False)):
        return {
            "ok": True,
            "claimed": True,
            "dry_run": True,
            "job": job,
        }

    run_result = _run_checkpoint_codex_job(job, args)
    checkpoint = job.get("checkpoint") if isinstance(job.get("checkpoint"), dict) else {}
    checkpoint_id = str(checkpoint.get("id", "")).strip()
    if not checkpoint_id:
        raise RuntimeError("Claimed checkpoint job is missing checkpoint id.")

    response_payload = {
        "summary": str(run_result.get("summary", "")).strip(),
        "body": str(run_result.get("body", "")),
        "structuredOutput": run_result.get("structured", {}),
        "worker": {
            "command": str(run_result.get("command", "")),
            "exitCode": int(run_result.get("exitCode", 0)),
            "stdout": str(run_result.get("stdout", "")),
            "stderr": str(run_result.get("stderr", "")),
            "ok": bool(run_result.get("ok", False)),
        },
    }
    response = _request_hosted_json(
        base_url=_resolve_hosted_base_url(args, session),
        path=f"/api/cli/checkpoints/{urlparse.quote(checkpoint_id)}/respond",
        method="POST",
        token=str(session.get("token", "")).strip(),
        body=response_payload,
    )
    return {
        "ok": bool(run_result.get("ok", False)),
        "claimed": True,
        "job": job,
        "response": response,
        "worker": run_result,
    }


def _agent_work_runner_args(args: argparse.Namespace) -> argparse.Namespace:
    repo_root = str(getattr(args, "repo_root", "")).strip() or str(Path.cwd())
    return argparse.Namespace(
        repo_root=repo_root,
        config=getattr(args, "config", "orp.yml"),
        base_url=getattr(args, "base_url", ""),
        json_output=bool(getattr(args, "json_output", False)),
        once=True,
        dry_run=bool(getattr(args, "dry_run", False)),
        poll_interval=int(getattr(args, "poll_interval", 30)),
        codex_bin=str(getattr(args, "codex_bin", "")).strip(),
        codex_config_profile=str(getattr(args, "codex_config_profile", "")).strip(),
        linked_project_roots=None,
        heartbeat_interval=20,
    )


def _agent_work_should_use_legacy_fallback(args: argparse.Namespace, error: Exception) -> bool:
    if str(getattr(args, "agent", "")).strip():
        return True
    message = str(error).strip().lower()
    fallback_markers = (
        "git repository not detected",
        "runner is disabled",
        "no linked repo is available for runner work",
        "no linked repo is available on this machine for runner work",
        "no active linked session with a codex session id is available for this repo",
        "selected linked session is missing a codex session id",
    )
    return any(marker in message for marker in fallback_markers)


def _extract_agent_checkpoint_id(result: dict[str, Any]) -> str:
    job = result.get("job", {}) if isinstance(result.get("job"), dict) else {}
    if isinstance(job.get("checkpoint"), dict):
        return str(job["checkpoint"].get("id", "")).strip()
    payload = job.get("payload", {}) if isinstance(job.get("payload"), dict) else {}
    return (
        str(job.get("checkpointId", job.get("checkpoint_id", ""))).strip()
        or str(payload.get("checkpointId", payload.get("checkpoint_id", ""))).strip()
    )


def _print_agent_work_result(result: dict[str, Any]) -> None:
    if not result.get("claimed"):
        print("job.claimed=false")
        print("job.status=idle")
        return

    job = result.get("job", {}) if isinstance(result.get("job"), dict) else {}
    checkpoint_id = _extract_agent_checkpoint_id(result)
    job_kind = str(job.get("kind", "")).strip() or str(job.get("intent", "")).strip()
    compatibility = result.get("compatibility", {}) if isinstance(result.get("compatibility"), dict) else {}

    print("job.claimed=true")
    if job_kind:
        print(f"job.kind={job_kind}")
    if checkpoint_id:
        print(f"checkpoint.id={checkpoint_id}")
    if result.get("dry_run"):
        print("job.mode=dry-run")
        return

    mode = str(compatibility.get("mode", "")).strip()
    if mode:
        print(f"job.mode={mode}")

    response = result.get("response", {}) if isinstance(result.get("response"), dict) else {}
    if response:
        print(f"response.id={str(response.get('id', '')).strip()}")
        print(f"response.ok={str(bool(result.get('ok', False))).lower()}")
        return

    print(f"job.ok={str(bool(result.get('ok', False))).lower()}")


def _run_agent_work_compat_once(args: argparse.Namespace) -> dict[str, Any]:
    if str(getattr(args, "agent", "")).strip():
        result = _run_worker_once(args)
        result["compatibility"] = {
            "mode": "legacy-agent-filter",
            "legacy_fallback": True,
        }
        return result

    runner_args = _agent_work_runner_args(args)
    try:
        result = _run_runner_work_once(runner_args)
        result["compatibility"] = {
            "mode": "runner-primary",
            "legacy_fallback": False,
        }
        return result
    except RuntimeError as exc:
        if not _agent_work_should_use_legacy_fallback(args, exc):
            raise
        result = _run_worker_once(args)
        result["compatibility"] = {
            "mode": "legacy-checkpoint-fallback",
            "legacy_fallback": True,
            "reason": str(exc),
        }
        return result


def cmd_agent_work(args: argparse.Namespace) -> int:
    poll_interval = max(1, int(getattr(args, "poll_interval", 30)))
    if bool(getattr(args, "once", False)):
        result = _run_agent_work_compat_once(args)
        if args.json_output:
            _print_json(result)
        else:
            _print_agent_work_result(result)
        return 0 if result.get("ok", True) else 1

    while True:
        result = _run_agent_work_compat_once(args)
        if args.json_output:
            _print_json(result)
        else:
            _print_agent_work_result(result)
        sys.stdout.flush()
        if not result.get("ok", True):
            return 1
        if result.get("claimed"):
            continue
        compatibility = result.get("compatibility", {}) if isinstance(result.get("compatibility"), dict) else {}
        if (
            str(compatibility.get("mode", "")).strip() == "runner-primary"
            and not bool(compatibility.get("legacy_fallback"))
        ):
            _wait_for_next_runner_cycle(args, poll_interval)
            continue
        time.sleep(poll_interval)


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

    claim = packet.get("claim_context")
    if isinstance(claim, dict):
        lines.append("")
        lines.append("## Claim Context")
        lines.append("")
        lines.append(f"- Claim id: `{claim.get('claim_id', '')}`")
        artifacts = [str(x) for x in claim.get("canonical_artifacts", []) if isinstance(x, str)]
        if artifacts:
            lines.append("- Canonical artifacts:")
            for path in artifacts:
                lines.append(f"  - `{path}`")

    atomic = packet.get("atomic_context")
    if isinstance(atomic, dict):
        lines.append("")
        lines.append("## Atomic Context")
        lines.append("")
        lines.append(f"- Board: `{atomic.get('board_id', '')}`")
        lines.append(f"- Problem: `{atomic.get('problem_id', '')}`")
        lines.append(f"- Snapshot: `{atomic.get('board_snapshot_path', '')}`")
        if atomic.get("starter_scaffold"):
            lines.append(f"- Starter scaffold: `true`")
        starter_note = str(atomic.get("starter_note", "")).strip()
        if starter_note:
            lines.append(f"- Starter note: `{starter_note}`")

    evidence_status = packet.get("evidence_status")
    if isinstance(evidence_status, dict):
        lines.append("")
        lines.append("## Evidence Status")
        lines.append("")
        lines.append(f"- Overall: `{evidence_status.get('overall', '')}`")
        lines.append(
            f"- Starter scaffold: `{str(bool(evidence_status.get('starter_scaffold', False))).lower()}`"
        )
        strongest_paths = [
            str(x)
            for x in evidence_status.get("strongest_evidence_paths", [])
            if isinstance(x, str)
        ]
        if strongest_paths:
            lines.append("- Strongest evidence paths:")
            for path in strongest_paths:
                lines.append(f"  - `{path}`")
        stub_gates = [str(x) for x in evidence_status.get("stub_gates", []) if isinstance(x, str)]
        if stub_gates:
            lines.append(f"- Stub gates: `{', '.join(stub_gates)}`")

    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append("- This packet is process metadata only.")
    lines.append("- Evidence remains in canonical artifact paths.")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ORP CLI")
    p.add_argument("--repo-root", default=".", help="Repository root (default: .)")
    p.add_argument("--config", default="orp.yml", help="Config path relative to repo root (default: orp.yml)")
    sub = p.add_subparsers(dest="cmd", required=False)

    def add_json_flag(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--json",
            dest="json_output",
            action="store_true",
            help="Print machine-readable JSON",
        )

    def add_base_url_flag(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--base-url",
            default="",
            help=f"Hosted ORP base URL (default: {DEFAULT_HOSTED_BASE_URL} or saved session)",
        )

    def add_secret_scope_flags(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--world-id", default="", help="Hosted world id")
        parser.add_argument("--idea-id", default="", help="Hosted idea id")
        parser.add_argument(
            "--current-project",
            action="store_true",
            help="Use the linked project/world from --repo-root when world/idea ids are omitted",
        )

    def add_feature_body_args(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--notes", default=None, help="Feature notes/body")
        parser.add_argument("--detail", default=None, help="Primary detail section body")
        parser.add_argument("--detail-label", default=None, help="Primary detail section label")
        parser.add_argument(
            "--details-file",
            default="",
            help="Path to feature detail sections JSON payload",
        )
        parser.add_argument(
            "--details-json",
            default="",
            help="Inline JSON payload for feature detail sections",
        )
        parser.add_argument(
            "--clear-details",
            action="store_true",
            help="Clear all structured detail sections",
        )
        parser.add_argument("--starred", action="store_true", help="Mark feature as starred")
        parser.add_argument(
            "--super-starred",
            action="store_true",
            help="Mark feature as super starred",
        )
        parser.add_argument(
            "--visibility",
            default=None,
            help="Feature visibility override when supported by the hosted workspace",
        )

    s_home = sub.add_parser(
        "home",
        help="Show ORP home screen with packs, repo status, and quick-start commands",
    )
    add_json_flag(s_home)
    s_home.set_defaults(func=cmd_home, json_output=False)

    s_about = sub.add_parser(
        "about",
        help="Describe ORP discovery surfaces and machine-friendly interfaces",
    )
    add_json_flag(s_about)
    s_about.set_defaults(func=cmd_about, json_output=False)

    s_mode = sub.add_parser(
        "mode",
        help="Agent-first creative and cognitive overlay modes",
    )
    mode_sub = s_mode.add_subparsers(dest="mode_cmd", required=True)

    s_mode_list = mode_sub.add_parser("list", help="List built-in agent modes")
    add_json_flag(s_mode_list)
    s_mode_list.set_defaults(func=cmd_mode_list, json_output=False)

    s_mode_show = mode_sub.add_parser("show", help="Show one built-in agent mode")
    s_mode_show.add_argument("mode_ref", help="Mode id or alias")
    add_json_flag(s_mode_show)
    s_mode_show.set_defaults(func=cmd_mode_show, json_output=False)

    s_mode_nudge = mode_sub.add_parser(
        "nudge",
        help="Return a deterministic creativity nudge card for one agent mode",
    )
    s_mode_nudge.add_argument("mode_ref", help="Mode id or alias")
    s_mode_nudge.add_argument(
        "--seed",
        default="",
        help="Optional deterministic seed; defaults to today's local date",
    )
    add_json_flag(s_mode_nudge)
    s_mode_nudge.set_defaults(func=cmd_mode_nudge, json_output=False)

    s_update = sub.add_parser(
        "update",
        help="Check npm for a newer ORP release and print the recommended upgrade command",
    )
    s_update.add_argument(
        "--yes",
        action="store_true",
        help="Apply the recommended update step when ORP can do so safely",
    )
    add_json_flag(s_update)
    s_update.set_defaults(func=cmd_update, json_output=False)

    s_maintenance = sub.add_parser(
        "maintenance",
        help="Machine-local ORP maintenance checks and daily macOS launchd scheduling",
    )
    maintenance_sub = s_maintenance.add_subparsers(dest="maintenance_cmd", required=True)

    s_maintenance_check = maintenance_sub.add_parser("check", help="Run a maintenance check and cache the result locally")
    add_json_flag(s_maintenance_check)
    s_maintenance_check.set_defaults(func=cmd_maintenance_check, json_output=False)

    s_maintenance_status = maintenance_sub.add_parser("status", help="Show cached maintenance state and launchd status")
    add_json_flag(s_maintenance_status)
    s_maintenance_status.set_defaults(func=cmd_maintenance_status, json_output=False)

    s_maintenance_enable = maintenance_sub.add_parser(
        "enable",
        help="Install and start a daily macOS launchd job for ORP maintenance",
    )
    s_maintenance_enable.add_argument("--hour", type=int, default=9, help="Hour of day in local time (default: 9)")
    s_maintenance_enable.add_argument("--minute", type=int, default=0, help="Minute of hour (default: 0)")
    add_json_flag(s_maintenance_enable)
    s_maintenance_enable.set_defaults(func=cmd_maintenance_enable, json_output=False)

    s_maintenance_disable = maintenance_sub.add_parser(
        "disable",
        help="Disable the daily macOS launchd job for ORP maintenance",
    )
    add_json_flag(s_maintenance_disable)
    s_maintenance_disable.set_defaults(func=cmd_maintenance_disable, json_output=False)

    s_schedule = sub.add_parser(
        "schedule",
        help="Local scheduled Codex jobs with one-shot run and macOS launchd enable/disable",
    )
    schedule_sub = s_schedule.add_subparsers(dest="schedule_cmd", required=True)

    s_schedule_add = schedule_sub.add_parser("add", help="Create one local scheduled job")
    schedule_add_sub = s_schedule_add.add_subparsers(dest="schedule_add_cmd", required=True)

    s_schedule_add_codex = schedule_add_sub.add_parser(
        "codex",
        help="Create a scheduled Codex job bound to one repo root and prompt",
    )
    s_schedule_add_codex.add_argument("--name", required=True, help="Human-readable job name")
    s_schedule_add_codex.add_argument(
        "--repo-root",
        default="",
        help="Repo or working directory for the Codex job (default: current directory)",
    )
    s_schedule_add_codex.add_argument("--prompt", default="", help="Inline prompt for the scheduled Codex job")
    s_schedule_add_codex.add_argument(
        "--prompt-file",
        default="",
        help="Path to a prompt file read at run time instead of storing an inline prompt",
    )
    s_schedule_add_codex.add_argument(
        "--sandbox",
        choices=["read-only", "workspace-write"],
        default="read-only",
        help="Sandbox mode for codex exec (default: read-only)",
    )
    s_schedule_add_codex.add_argument("--hour", type=int, default=9, help="Hour of day in local time (default: 9)")
    s_schedule_add_codex.add_argument("--minute", type=int, default=0, help="Minute of hour (default: 0)")
    s_schedule_add_codex.add_argument("--codex-bin", default="", help="Codex executable path")
    s_schedule_add_codex.add_argument(
        "--codex-config-profile",
        default="",
        help="Optional Codex config profile passed via CODEX_PROFILE",
    )
    s_schedule_add_codex.add_argument(
        "--codex-session-id",
        default="",
        help="Optional Codex session id to resume instead of starting a fresh non-interactive run",
    )
    add_json_flag(s_schedule_add_codex)
    s_schedule_add_codex.set_defaults(func=cmd_schedule_add_codex, json_output=False)

    s_schedule_list = schedule_sub.add_parser("list", help="List local scheduled jobs")
    add_json_flag(s_schedule_list)
    s_schedule_list.set_defaults(func=cmd_schedule_list, json_output=False)

    s_schedule_show = schedule_sub.add_parser("show", help="Show one scheduled job with prompt, repo, and session details")
    s_schedule_show.add_argument("target", help="Scheduled job name or id")
    add_json_flag(s_schedule_show)
    s_schedule_show.set_defaults(func=cmd_schedule_show, json_output=False)

    s_schedule_run = schedule_sub.add_parser("run", help="Run one scheduled job immediately")
    s_schedule_run.add_argument("target", help="Scheduled job name or id")
    add_json_flag(s_schedule_run)
    s_schedule_run.set_defaults(func=cmd_schedule_run, json_output=False)

    s_schedule_enable = schedule_sub.add_parser("enable", help="Enable recurring execution for one scheduled job")
    s_schedule_enable.add_argument("target", help="Scheduled job name or id")
    s_schedule_enable.add_argument("--hour", type=int, default=None, help="Optional hour override in local time")
    s_schedule_enable.add_argument("--minute", type=int, default=None, help="Optional minute override in local time")
    add_json_flag(s_schedule_enable)
    s_schedule_enable.set_defaults(func=cmd_schedule_enable, json_output=False)

    s_schedule_disable = schedule_sub.add_parser("disable", help="Disable recurring execution for one scheduled job")
    s_schedule_disable.add_argument("target", help="Scheduled job name or id")
    add_json_flag(s_schedule_disable)
    s_schedule_disable.set_defaults(func=cmd_schedule_disable, json_output=False)

    s_auth = sub.add_parser("auth", help="Hosted workspace authentication operations")
    auth_sub = s_auth.add_subparsers(dest="auth_cmd", required=True)

    s_auth_login = auth_sub.add_parser("login", help="Start hosted workspace login flow")
    s_auth_login.add_argument("--email", default="", help="Hosted account email")
    s_auth_login.add_argument("--password", default="", help="Hosted account password")
    s_auth_login.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the hosted account password from stdin",
    )
    add_base_url_flag(s_auth_login)
    add_json_flag(s_auth_login)
    s_auth_login.set_defaults(func=cmd_auth_login, json_output=False)

    s_auth_verify = auth_sub.add_parser("verify", help="Complete hosted workspace verification")
    s_auth_verify.add_argument("--email", default="", help="Hosted account email")
    s_auth_verify.add_argument("--code", default="", help="Verification code")
    s_auth_verify.add_argument(
        "--code-stdin",
        action="store_true",
        help="Read the verification code from stdin",
    )
    add_base_url_flag(s_auth_verify)
    add_json_flag(s_auth_verify)
    s_auth_verify.set_defaults(func=cmd_auth_verify, json_output=False)

    s_auth_logout = auth_sub.add_parser("logout", help="Clear the hosted workspace session")
    add_json_flag(s_auth_logout)
    s_auth_logout.set_defaults(func=cmd_auth_logout, json_output=False)

    s_whoami = sub.add_parser("whoami", help="Show the current hosted workspace identity")
    add_base_url_flag(s_whoami)
    add_json_flag(s_whoami)
    s_whoami.set_defaults(func=cmd_whoami, json_output=False)

    s_ideas = sub.add_parser("ideas", help="Hosted workspace idea listing operations")
    ideas_sub = s_ideas.add_subparsers(dest="ideas_cmd", required=True)
    s_ideas_list = ideas_sub.add_parser("list", help="List ideas from the hosted workspace")
    s_ideas_list.add_argument("--limit", type=int, default=25, help="Page size (default: 25)")
    s_ideas_list.add_argument("--cursor", default="", help="Pagination cursor")
    s_ideas_list.add_argument(
        "--sort",
        default="updated_desc",
        help="Sort order (default: updated_desc)",
    )
    s_ideas_list.add_argument(
        "--deleted",
        action="store_true",
        help="List deleted ideas instead of active ones",
    )
    add_base_url_flag(s_ideas_list)
    add_json_flag(s_ideas_list)
    s_ideas_list.set_defaults(func=cmd_ideas_list, json_output=False)

    s_workspaces = sub.add_parser("workspaces", help="Hosted workspace record operations")
    workspaces_sub = s_workspaces.add_subparsers(dest="workspaces_cmd", required=True)

    s_workspaces_list = workspaces_sub.add_parser("list", help="List hosted workspaces")
    s_workspaces_list.add_argument("--limit", type=int, default=25, help="Page size (default: 25)")
    s_workspaces_list.add_argument("--cursor", default="", help="Pagination cursor")
    add_base_url_flag(s_workspaces_list)
    add_json_flag(s_workspaces_list)
    s_workspaces_list.set_defaults(func=cmd_workspaces_list, json_output=False)

    s_workspaces_show = workspaces_sub.add_parser("show", help="Show one hosted workspace by name or id")
    s_workspaces_show.add_argument("workspace_id", help="Hosted workspace name or id")
    add_base_url_flag(s_workspaces_show)
    add_json_flag(s_workspaces_show)
    s_workspaces_show.set_defaults(func=cmd_workspaces_show, json_output=False)

    s_workspaces_tabs = workspaces_sub.add_parser("tabs", help="Show saved tabs for one hosted workspace by name or id")
    s_workspaces_tabs.add_argument("workspace_id", help="Hosted workspace name or id")
    add_base_url_flag(s_workspaces_tabs)
    add_json_flag(s_workspaces_tabs)
    s_workspaces_tabs.set_defaults(func=cmd_workspaces_tabs, json_output=False)

    s_workspaces_timeline = workspaces_sub.add_parser("timeline", help="Show timeline events for one hosted workspace by name or id")
    s_workspaces_timeline.add_argument("workspace_id", help="Hosted workspace name or id")
    s_workspaces_timeline.add_argument("--limit", type=int, default=25, help="Page size (default: 25)")
    add_base_url_flag(s_workspaces_timeline)
    add_json_flag(s_workspaces_timeline)
    s_workspaces_timeline.set_defaults(func=cmd_workspaces_timeline, json_output=False)

    s_workspaces_add = workspaces_sub.add_parser("add", help="Create a hosted workspace")
    s_workspaces_add.add_argument("--title", required=True, help="Workspace title in lowercase-dash format")
    s_workspaces_add.add_argument("--description", default=None, help="Workspace description")
    s_workspaces_add.add_argument("--visibility", default=None, help="Workspace visibility")
    s_workspaces_add.add_argument("--idea-id", default=None, help="Optional linked hosted idea id")
    add_base_url_flag(s_workspaces_add)
    add_json_flag(s_workspaces_add)
    s_workspaces_add.set_defaults(func=cmd_workspaces_add, json_output=False)

    s_workspaces_update = workspaces_sub.add_parser("update", help="Update a hosted workspace")
    s_workspaces_update.add_argument("workspace_id", help="Hosted workspace id")
    s_workspaces_update.add_argument("--title", default=None, help="Workspace title in lowercase-dash format")
    s_workspaces_update.add_argument("--description", default=None, help="Workspace description")
    s_workspaces_update.add_argument("--visibility", default=None, help="Workspace visibility")
    s_workspaces_update.add_argument("--idea-id", default=None, help="Optional linked hosted idea id")
    add_base_url_flag(s_workspaces_update)
    add_json_flag(s_workspaces_update)
    s_workspaces_update.set_defaults(func=cmd_workspaces_update, json_output=False)

    s_workspaces_push_state = workspaces_sub.add_parser(
        "push-state", help="Push one current-state JSON payload into a hosted workspace"
    )
    s_workspaces_push_state.add_argument("workspace_id", help="Hosted workspace id")
    s_workspaces_push_state.add_argument("--state-file", required=True, help="Path to a hosted workspace state JSON file")
    add_base_url_flag(s_workspaces_push_state)
    add_json_flag(s_workspaces_push_state)
    s_workspaces_push_state.set_defaults(func=cmd_workspaces_push_state, json_output=False)

    s_workspaces_add_event = workspaces_sub.add_parser(
        "add-event", help="Append one timeline event JSON payload to a hosted workspace"
    )
    s_workspaces_add_event.add_argument("workspace_id", help="Hosted workspace id")
    s_workspaces_add_event.add_argument("--event-file", required=True, help="Path to a hosted workspace event JSON file")
    add_base_url_flag(s_workspaces_add_event)
    add_json_flag(s_workspaces_add_event)
    s_workspaces_add_event.set_defaults(func=cmd_workspaces_add_event, json_output=False)

    s_idea = sub.add_parser("idea", help="Hosted workspace idea CRUD operations")
    idea_sub = s_idea.add_subparsers(dest="idea_cmd", required=True)

    s_idea_show = idea_sub.add_parser("show", help="Show one hosted idea")
    s_idea_show.add_argument("idea_id", help="Hosted idea id")
    add_base_url_flag(s_idea_show)
    add_json_flag(s_idea_show)
    s_idea_show.set_defaults(func=cmd_idea_show, json_output=False)

    s_idea_add = idea_sub.add_parser("add", help="Create a hosted idea")
    s_idea_add.add_argument("--title", required=True, help="Idea title")
    s_idea_add.add_argument("--notes", default=None, help="Idea core plan/notes")
    s_idea_add.add_argument("--summary", default=None, help="Alias for notes")
    s_idea_add.add_argument("--github-url", default=None, help="Idea-level web or GitHub URL")
    s_idea_add.add_argument("--link-label", default=None, help="Optional label for the idea link")
    s_idea_add.add_argument("--visibility", default=None, help="Idea visibility")
    add_base_url_flag(s_idea_add)
    add_json_flag(s_idea_add)
    s_idea_add.set_defaults(func=cmd_idea_add, json_output=False)

    s_idea_update = idea_sub.add_parser("update", help="Update a hosted idea")
    s_idea_update.add_argument("idea_id", help="Hosted idea id")
    s_idea_update.add_argument("--title", default=None, help="Idea title")
    s_idea_update.add_argument("--notes", default=None, help="Idea core plan/notes")
    s_idea_update.add_argument("--summary", default=None, help="Alias for notes")
    s_idea_update.add_argument("--github-url", default=None, help="Idea-level web or GitHub URL")
    s_idea_update.add_argument("--link-label", default=None, help="Optional label for the idea link")
    s_idea_update.add_argument("--visibility", default=None, help="Idea visibility")
    add_base_url_flag(s_idea_update)
    add_json_flag(s_idea_update)
    s_idea_update.set_defaults(func=cmd_idea_update, json_output=False)

    s_idea_remove = idea_sub.add_parser("remove", help="Remove a hosted idea")
    s_idea_remove.add_argument("idea_id", help="Hosted idea id")
    s_idea_remove.add_argument(
        "--purge",
        action="store_true",
        help="Permanently purge instead of soft-delete",
    )
    add_base_url_flag(s_idea_remove)
    add_json_flag(s_idea_remove)
    s_idea_remove.set_defaults(func=cmd_idea_remove, json_output=False)

    s_idea_restore = idea_sub.add_parser("restore", help="Restore a soft-deleted hosted idea")
    s_idea_restore.add_argument("idea_id", help="Hosted idea id")
    add_base_url_flag(s_idea_restore)
    add_json_flag(s_idea_restore)
    s_idea_restore.set_defaults(func=cmd_idea_restore, json_output=False)

    s_feature = sub.add_parser("feature", help="Hosted workspace feature CRUD operations")
    feature_sub = s_feature.add_subparsers(dest="feature_cmd", required=True)

    s_feature_list = feature_sub.add_parser("list", help="List features on a hosted idea")
    s_feature_list.add_argument("idea_id", help="Hosted idea id")
    add_base_url_flag(s_feature_list)
    add_json_flag(s_feature_list)
    s_feature_list.set_defaults(func=cmd_feature_list, json_output=False)

    s_feature_show = feature_sub.add_parser("show", help="Show one hosted feature")
    s_feature_show.add_argument("feature_id", help="Hosted feature id")
    s_feature_show.add_argument("--idea-id", required=True, help="Parent hosted idea id")
    add_base_url_flag(s_feature_show)
    add_json_flag(s_feature_show)
    s_feature_show.set_defaults(func=cmd_feature_show, json_output=False)

    s_feature_add = feature_sub.add_parser("add", help="Create a hosted feature")
    s_feature_add.add_argument("--idea-id", required=True, help="Parent hosted idea id")
    s_feature_add.add_argument("--title", required=True, help="Feature title")
    add_feature_body_args(s_feature_add)
    add_base_url_flag(s_feature_add)
    add_json_flag(s_feature_add)
    s_feature_add.set_defaults(func=cmd_feature_add, json_output=False)

    s_feature_update = feature_sub.add_parser("update", help="Update a hosted feature")
    s_feature_update.add_argument("feature_id", help="Hosted feature id")
    s_feature_update.add_argument("--idea-id", required=True, help="Parent hosted idea id")
    s_feature_update.add_argument("--title", default=None, help="Feature title")
    add_feature_body_args(s_feature_update)
    add_base_url_flag(s_feature_update)
    add_json_flag(s_feature_update)
    s_feature_update.set_defaults(func=cmd_feature_update, json_output=False)

    s_feature_remove = feature_sub.add_parser("remove", help="Remove a hosted feature")
    s_feature_remove.add_argument("feature_id", help="Hosted feature id")
    add_base_url_flag(s_feature_remove)
    add_json_flag(s_feature_remove)
    s_feature_remove.set_defaults(func=cmd_feature_remove, json_output=False)

    s_world = sub.add_parser("world", help="Hosted workspace world binding operations")
    world_sub = s_world.add_subparsers(dest="world_cmd", required=True)

    s_world_show = world_sub.add_parser("show", help="Show the world bound to a hosted idea")
    s_world_show.add_argument("idea_id", help="Hosted idea id")
    add_base_url_flag(s_world_show)
    add_json_flag(s_world_show)
    s_world_show.set_defaults(func=cmd_world_show, json_output=False)

    s_world_bind = world_sub.add_parser("bind", help="Create or update a hosted idea world binding")
    s_world_bind.add_argument("idea_id", help="Hosted idea id")
    s_world_bind.add_argument("--name", default=None, help="World name")
    s_world_bind.add_argument("--project-root", default=None, help="Absolute project root path")
    s_world_bind.add_argument("--github-url", default=None, help="World GitHub URL")
    s_world_bind.add_argument("--codex-session-id", default=None, help="Primary Codex session id")
    add_base_url_flag(s_world_bind)
    add_json_flag(s_world_bind)
    s_world_bind.set_defaults(func=cmd_world_bind, json_output=False)

    s_youtube = sub.add_parser("youtube", help="Public YouTube metadata and transcript inspection")
    youtube_sub = s_youtube.add_subparsers(dest="youtube_cmd", required=True)

    s_youtube_inspect = youtube_sub.add_parser(
        "inspect",
        help="Inspect a YouTube video and fetch public metadata plus full transcript text and segments when caption tracks are available",
    )
    s_youtube_inspect.add_argument("url", help="YouTube watch/share URL or 11-character video id")
    s_youtube_inspect.add_argument(
        "--lang",
        default="",
        help="Preferred caption language code, for example en or es",
    )
    s_youtube_inspect.add_argument(
        "--save",
        action="store_true",
        help="Save the inspected source artifact under orp/external/youtube/<video_id>.json",
    )
    s_youtube_inspect.add_argument(
        "--out",
        default="",
        help="Optional output path for the source artifact (.json, .yml, or .yaml)",
    )
    s_youtube_inspect.add_argument(
        "--format",
        default="",
        choices=["", "json", "yaml"],
        help="Optional explicit output format when saving",
    )
    s_youtube_inspect.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing saved artifact",
    )
    add_json_flag(s_youtube_inspect)
    s_youtube_inspect.set_defaults(func=cmd_youtube_inspect, json_output=False)

    s_secrets = sub.add_parser(
        "secrets",
        help="Save and reuse API keys and tokens locally, with optional hosted sync",
        description=(
            "ORP secrets are easiest to understand as saved keys and tokens.\n\n"
            "Human flow:\n"
            "  1. Run `orp secrets add ...`\n"
            "  2. Paste the value when ORP prompts `Secret value:`\n"
            "  3. Later run `orp secrets list` or `orp secrets resolve ...`\n\n"
            "Agent flow:\n"
            "  - Pipe the value with `--value-stdin` instead of typing it interactively.\n\n"
            "Local macOS Keychain caching and hosted sync are optional layers on top."
        ),
        epilog=(
            "Examples:\n"
            "  orp secrets add --alias openai-primary --label \"OpenAI Primary\" --provider openai\n"
            "  printf '%s' 'sk-...' | orp secrets add --alias openai-primary --label \"OpenAI Primary\" --provider openai --value-stdin\n"
            "  orp secrets list\n"
            "  orp secrets resolve openai-primary --reveal"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    secrets_sub = s_secrets.add_subparsers(dest="secrets_cmd", required=True)

    s_secrets_list = secrets_sub.add_parser("list", help="List saved secrets known to ORP")
    s_secrets_list.add_argument("--provider", default="", help="Optional provider filter")
    add_secret_scope_flags(s_secrets_list)
    s_secrets_list.add_argument(
        "--archived",
        action="store_true",
        help="Include archived secrets",
    )
    add_base_url_flag(s_secrets_list)
    add_json_flag(s_secrets_list)
    s_secrets_list.set_defaults(func=cmd_secrets_list, json_output=False)

    s_secrets_show = secrets_sub.add_parser("show", help="Show one saved secret by alias or id")
    s_secrets_show.add_argument("secret_ref", help="Secret alias or id")
    add_base_url_flag(s_secrets_show)
    add_json_flag(s_secrets_show)
    s_secrets_show.set_defaults(func=cmd_secrets_show, json_output=False)

    s_secrets_add = secrets_sub.add_parser(
        "add",
        help="Save a new secret; ORP prompts for the value unless you pass --value-stdin",
    )
    s_secrets_add.add_argument("--alias", required=True, help="Stable secret alias")
    s_secrets_add.add_argument("--label", required=True, help="Human label for the secret")
    s_secrets_add.add_argument("--provider", required=True, help="Provider slug, for example openai")
    s_secrets_add.add_argument(
        "--kind",
        choices=["api_key", "access_token", "password", "other"],
        default="api_key",
        help="Secret kind (default: api_key)",
    )
    s_secrets_add.add_argument("--env-var-name", default=None, help="Optional env var name, for example OPENAI_API_KEY")
    s_secrets_add.add_argument("--value", default=None, help="Secret value")
    s_secrets_add.add_argument(
        "--value-stdin",
        action="store_true",
        help="Read the secret value from stdin",
    )
    s_secrets_add.add_argument("--notes", default=None, help="Optional notes")
    add_secret_scope_flags(s_secrets_add)
    s_secrets_add.add_argument("--purpose", default="", help="Optional project usage note when binding")
    s_secrets_add.add_argument(
        "--primary",
        action="store_true",
        help="Mark the binding as primary for the project when binding during create",
    )
    add_base_url_flag(s_secrets_add)
    add_json_flag(s_secrets_add)
    s_secrets_add.set_defaults(func=cmd_secrets_add, json_output=False)

    s_secrets_ensure = secrets_sub.add_parser(
        "ensure",
        help="Reuse a saved secret or prompt for it and save it when missing",
    )
    s_secrets_ensure.add_argument("--alias", required=True, help="Stable secret alias")
    s_secrets_ensure.add_argument("--label", default="", help="Human label for create-if-missing flows")
    s_secrets_ensure.add_argument("--provider", required=True, help="Provider slug, for example openai")
    s_secrets_ensure.add_argument(
        "--kind",
        choices=["api_key", "access_token", "password", "other"],
        default="api_key",
        help="Secret kind when create-if-missing is needed (default: api_key)",
    )
    s_secrets_ensure.add_argument(
        "--env-var-name",
        default=None,
        help="Optional env var name to store on create, for example OPENAI_API_KEY",
    )
    s_secrets_ensure.add_argument("--value", default=None, help="Secret value when create-if-missing is needed")
    s_secrets_ensure.add_argument(
        "--value-stdin",
        action="store_true",
        help="Read the secret value from stdin when create-if-missing is needed",
    )
    s_secrets_ensure.add_argument("--notes", default=None, help="Optional notes for create-if-missing flows")
    add_secret_scope_flags(s_secrets_ensure)
    s_secrets_ensure.add_argument("--purpose", default="", help="Optional project usage note when binding")
    s_secrets_ensure.add_argument(
        "--primary",
        action="store_true",
        help="Mark the binding as primary for the target project",
    )
    s_secrets_ensure.add_argument(
        "--reveal",
        action="store_true",
        help="Resolve and return the plaintext value after ensuring the secret",
    )
    add_base_url_flag(s_secrets_ensure)
    add_json_flag(s_secrets_ensure)
    s_secrets_ensure.set_defaults(func=cmd_secrets_ensure, json_output=False)

    s_secrets_keychain_list = secrets_sub.add_parser(
        "keychain-list",
        help="List local macOS Keychain copies known to ORP on this machine",
    )
    s_secrets_keychain_list.add_argument("--provider", default="", help="Optional provider filter")
    add_secret_scope_flags(s_secrets_keychain_list)
    add_json_flag(s_secrets_keychain_list)
    s_secrets_keychain_list.set_defaults(func=cmd_secrets_keychain_list, json_output=False)

    s_secrets_keychain_show = secrets_sub.add_parser(
        "keychain-show",
        help="Show one local macOS Keychain copy by alias or id",
    )
    s_secrets_keychain_show.add_argument("secret_ref", help="Secret alias or id")
    s_secrets_keychain_show.add_argument(
        "--reveal",
        action="store_true",
        help="Return the plaintext value from the local macOS Keychain",
    )
    add_json_flag(s_secrets_keychain_show)
    s_secrets_keychain_show.set_defaults(func=cmd_secrets_keychain_show, json_output=False)

    s_secrets_sync_keychain = secrets_sub.add_parser(
        "sync-keychain",
        help="Copy one saved secret into the local macOS Keychain",
    )
    s_secrets_sync_keychain.add_argument("secret_ref", nargs="?", default="", help="Optional secret alias or id")
    s_secrets_sync_keychain.add_argument("--provider", default="", help="Provider slug for project-scoped sync")
    add_secret_scope_flags(s_secrets_sync_keychain)
    s_secrets_sync_keychain.add_argument(
        "--all",
        action="store_true",
        help="Sync every matching hosted secret into the local Keychain",
    )
    add_base_url_flag(s_secrets_sync_keychain)
    add_json_flag(s_secrets_sync_keychain)
    s_secrets_sync_keychain.set_defaults(func=cmd_secrets_sync_keychain, json_output=False)

    s_secrets_update = secrets_sub.add_parser("update", help="Update one saved secret")
    s_secrets_update.add_argument("secret_ref", help="Secret alias or id")
    s_secrets_update.add_argument("--alias", default=None, help="New alias")
    s_secrets_update.add_argument("--label", default=None, help="New label")
    s_secrets_update.add_argument("--provider", default=None, help="Provider slug")
    s_secrets_update.add_argument(
        "--kind",
        choices=["api_key", "access_token", "password", "other"],
        default=None,
        help="Secret kind",
    )
    s_secrets_update.add_argument("--env-var-name", default=None, help="Updated env var name")
    s_secrets_update.add_argument("--value", default=None, help="New secret value")
    s_secrets_update.add_argument(
        "--value-stdin",
        action="store_true",
        help="Read the new secret value from stdin",
    )
    s_secrets_update.add_argument("--notes", default=None, help="Updated notes")
    s_secrets_update.add_argument(
        "--status",
        choices=["active", "archived", "revoked"],
        default=None,
        help="Update the secret status",
    )
    add_base_url_flag(s_secrets_update)
    add_json_flag(s_secrets_update)
    s_secrets_update.set_defaults(func=cmd_secrets_update, json_output=False)

    s_secrets_archive = secrets_sub.add_parser("archive", help="Archive one saved secret")
    s_secrets_archive.add_argument("secret_ref", help="Secret alias or id")
    add_base_url_flag(s_secrets_archive)
    add_json_flag(s_secrets_archive)
    s_secrets_archive.set_defaults(func=cmd_secrets_archive, json_output=False)

    s_secrets_bind = secrets_sub.add_parser("bind", help="Bind one saved secret to a hosted project/world")
    s_secrets_bind.add_argument("secret_ref", help="Secret alias or id")
    add_secret_scope_flags(s_secrets_bind)
    s_secrets_bind.add_argument("--purpose", default="", help="Optional project usage note")
    s_secrets_bind.add_argument(
        "--primary",
        action="store_true",
        help="Mark the binding as primary for the target project",
    )
    add_base_url_flag(s_secrets_bind)
    add_json_flag(s_secrets_bind)
    s_secrets_bind.set_defaults(func=cmd_secrets_bind, json_output=False)

    s_secrets_unbind = secrets_sub.add_parser("unbind", help="Remove one hosted secret binding")
    s_secrets_unbind.add_argument("binding_id", help="Hosted binding id")
    add_base_url_flag(s_secrets_unbind)
    add_json_flag(s_secrets_unbind)
    s_secrets_unbind.set_defaults(func=cmd_secrets_unbind, json_output=False)

    s_secrets_resolve = secrets_sub.add_parser(
        "resolve",
        help="Resolve one saved secret by alias/id or by provider plus project scope",
    )
    s_secrets_resolve.add_argument("secret_ref", nargs="?", default="", help="Optional secret alias or id")
    s_secrets_resolve.add_argument("--provider", default="", help="Provider slug for project-scoped resolution")
    add_secret_scope_flags(s_secrets_resolve)
    s_secrets_resolve.add_argument(
        "--reveal",
        action="store_true",
        help="Return the plaintext value in the command output",
    )
    s_secrets_resolve.add_argument(
        "--local-first",
        action="store_true",
        help="Prefer the local macOS Keychain cache before falling back to the hosted secret store",
    )
    s_secrets_resolve.add_argument(
        "--local-only",
        action="store_true",
        help="Resolve only from the local macOS Keychain cache",
    )
    s_secrets_resolve.add_argument(
        "--sync-keychain",
        action="store_true",
        help="After a hosted resolve, store the plaintext value in the local macOS Keychain",
    )
    add_base_url_flag(s_secrets_resolve)
    add_json_flag(s_secrets_resolve)
    s_secrets_resolve.set_defaults(func=cmd_secrets_resolve, json_output=False)

    s_link = sub.add_parser(
        "link",
        help="Machine-local project and session linking for hosted ORP routing",
    )
    link_sub = s_link.add_subparsers(dest="link_cmd", required=True)

    s_link_project = link_sub.add_parser("project", help="Project-level link operations")
    link_project_sub = s_link_project.add_subparsers(dest="link_project_cmd", required=True)

    s_link_project_bind = link_project_sub.add_parser(
        "bind",
        help="Bind the current repo to a hosted idea/world and save local link metadata",
    )
    s_link_project_bind.add_argument("--idea-id", required=True, help="Hosted idea id")
    s_link_project_bind.add_argument("--idea-title", default="", help="Optional hosted idea title")
    s_link_project_bind.add_argument("--name", default="", help="Optional world name override")
    s_link_project_bind.add_argument(
        "--project-root",
        default="",
        help="Project root override; must match the current --repo-root",
    )
    s_link_project_bind.add_argument("--github-url", default="", help="Optional GitHub/web URL override")
    s_link_project_bind.add_argument("--codex-session-id", default="", help="Primary Codex session id override")
    s_link_project_bind.add_argument("--notes", default="", help="Optional local notes stored with the link")
    add_base_url_flag(s_link_project_bind)
    add_json_flag(s_link_project_bind)
    s_link_project_bind.set_defaults(func=cmd_link_project_bind, json_output=False)

    s_link_project_show = link_project_sub.add_parser(
        "show",
        help="Show the locally stored linked-project record",
    )
    add_json_flag(s_link_project_show)
    s_link_project_show.set_defaults(func=cmd_link_project_show, json_output=False)

    s_link_project_status = link_project_sub.add_parser(
        "status",
        help="Show linked-project status with local sessions and hosted refresh info",
    )
    add_base_url_flag(s_link_project_status)
    add_json_flag(s_link_project_status)
    s_link_project_status.set_defaults(func=cmd_link_project_status, json_output=False)

    s_link_project_unbind = link_project_sub.add_parser(
        "unbind",
        help="Remove the local linked-project record without deleting hosted state",
    )
    add_json_flag(s_link_project_unbind)
    s_link_project_unbind.set_defaults(func=cmd_link_project_unbind, json_output=False)

    s_link_session = link_sub.add_parser("session", help="Machine-local linked session operations")
    link_session_sub = s_link_session.add_subparsers(dest="link_session_cmd", required=True)

    s_link_session_register = link_session_sub.add_parser(
        "register",
        help="Register or update a linked ORP session for this repo",
    )
    s_link_session_register.add_argument("--orp-session-id", required=True, help="ORP session id")
    s_link_session_register.add_argument("--label", required=True, help="Human label for the session")
    s_link_session_register.add_argument("--codex-session-id", default=None, help="Linked Codex session id")
    s_link_session_register.add_argument(
        "--project-root",
        default="",
        help="Project root override; must match the current --repo-root",
    )
    s_link_session_register.add_argument(
        "--state",
        choices=["active", "closed"],
        default="active",
        help="Linked session state (default: active)",
    )
    s_link_session_register.add_argument(
        "--role",
        choices=["primary", "secondary", "review", "exploration", "other"],
        default=None,
        help="Optional local role hint",
    )
    s_link_session_register.add_argument("--created-at", default=None, help="Optional creation timestamp override")
    s_link_session_register.add_argument(
        "--last-active-at",
        default=None,
        help="Optional last-active timestamp override",
    )
    s_link_session_register.add_argument("--window-id", type=int, default=None, help="Optional terminal window id")
    s_link_session_register.add_argument("--tab-number", type=int, default=None, help="Optional terminal tab number")
    s_link_session_register.add_argument(
        "--archived",
        action="store_true",
        default=None,
        help="Register the session as archived",
    )
    s_link_session_register.add_argument(
        "--primary",
        action="store_true",
        default=None,
        help="Mark this session as the primary linked session",
    )
    s_link_session_register.add_argument("--notes", default=None, help="Optional local notes stored with the session")
    add_json_flag(s_link_session_register)
    s_link_session_register.set_defaults(func=cmd_link_session_register, json_output=False)

    s_link_session_list = link_session_sub.add_parser("list", help="List linked sessions for this repo")
    add_json_flag(s_link_session_list)
    s_link_session_list.set_defaults(func=cmd_link_session_list, json_output=False)

    s_link_session_show = link_session_sub.add_parser("show", help="Show one linked session")
    s_link_session_show.add_argument("orp_session_id", help="Linked ORP session id")
    add_json_flag(s_link_session_show)
    s_link_session_show.set_defaults(func=cmd_link_session_show, json_output=False)

    s_link_session_set_primary = link_session_sub.add_parser(
        "set-primary",
        help="Set the primary linked session for this repo",
    )
    s_link_session_set_primary.add_argument("orp_session_id", help="Linked ORP session id")
    add_json_flag(s_link_session_set_primary)
    s_link_session_set_primary.set_defaults(func=cmd_link_session_set_primary, json_output=False)

    s_link_session_archive = link_session_sub.add_parser("archive", help="Archive one linked session")
    s_link_session_archive.add_argument("orp_session_id", help="Linked ORP session id")
    add_json_flag(s_link_session_archive)
    s_link_session_archive.set_defaults(func=cmd_link_session_archive, json_output=False)

    s_link_session_unarchive = link_session_sub.add_parser("unarchive", help="Unarchive one linked session")
    s_link_session_unarchive.add_argument("orp_session_id", help="Linked ORP session id")
    add_json_flag(s_link_session_unarchive)
    s_link_session_unarchive.set_defaults(func=cmd_link_session_unarchive, json_output=False)

    s_link_session_remove = link_session_sub.add_parser("remove", help="Remove one linked session")
    s_link_session_remove.add_argument("orp_session_id", help="Linked ORP session id")
    add_json_flag(s_link_session_remove)
    s_link_session_remove.set_defaults(func=cmd_link_session_remove, json_output=False)

    s_link_session_import_rust = link_session_sub.add_parser(
        "import-rust",
        help="Import Rust desktop app .orp metadata into CLI link storage",
    )
    add_json_flag(s_link_session_import_rust)
    s_link_session_import_rust.set_defaults(func=cmd_link_session_import_rust, json_output=False)

    s_link_import_rust = link_sub.add_parser(
        "import-rust",
        help="Import Rust desktop app project and session metadata into CLI link storage",
    )
    s_link_import_rust.add_argument(
        "--all",
        action="store_true",
        help="Import both .orp/project.json and .orp/sessions/*.json into CLI link storage",
    )
    add_json_flag(s_link_import_rust)
    s_link_import_rust.set_defaults(func=cmd_link_import_rust, json_output=False)

    s_link_status = link_sub.add_parser("status", help="Show linked project/session status for this repo")
    add_base_url_flag(s_link_status)
    add_json_flag(s_link_status)
    s_link_status.set_defaults(func=cmd_link_status, json_output=False)

    s_link_doctor = link_sub.add_parser("doctor", help="Validate local project/session link health")
    s_link_doctor.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when warnings are present",
    )
    add_base_url_flag(s_link_doctor)
    add_json_flag(s_link_doctor)
    s_link_doctor.set_defaults(func=cmd_link_doctor, json_output=False)

    s_runner = sub.add_parser("runner", help="Machine runner identity and hosted sync operations")
    runner_sub = s_runner.add_subparsers(dest="runner_cmd", required=True)

    s_runner_status = runner_sub.add_parser("status", help="Show machine runner state for this repo")
    add_base_url_flag(s_runner_status)
    add_json_flag(s_runner_status)
    s_runner_status.set_defaults(func=cmd_runner_status, json_output=False)

    s_runner_enable = runner_sub.add_parser("enable", help="Enable the machine runner locally")
    add_json_flag(s_runner_enable)
    s_runner_enable.set_defaults(func=cmd_runner_enable, json_output=False)

    s_runner_disable = runner_sub.add_parser("disable", help="Disable the machine runner locally")
    add_json_flag(s_runner_disable)
    s_runner_disable.set_defaults(func=cmd_runner_disable, json_output=False)

    s_runner_heartbeat = runner_sub.add_parser(
        "heartbeat",
        help="Send one hosted runner heartbeat and persist the local heartbeat timestamp",
    )
    add_base_url_flag(s_runner_heartbeat)
    add_json_flag(s_runner_heartbeat)
    s_runner_heartbeat.set_defaults(func=cmd_runner_heartbeat, json_output=False)

    s_runner_sync = runner_sub.add_parser(
        "sync",
        help="Sync the current repo's linked project/session inventory to the hosted app",
    )
    s_runner_sync.add_argument(
        "--linked-project-root",
        dest="linked_project_roots",
        action="append",
        default=[],
        help="Additional linked project root to include in this machine sync; repeat for multiple repos",
    )
    add_base_url_flag(s_runner_sync)
    add_json_flag(s_runner_sync)
    s_runner_sync.set_defaults(func=cmd_runner_sync, json_output=False)

    s_runner_work = runner_sub.add_parser(
        "work",
        help="Poll and process hosted runner jobs for the current linked repo",
    )
    s_runner_work.add_argument("--codex-bin", default="", help="Codex executable path")
    s_runner_work.add_argument(
        "--codex-config-profile",
        default="",
        help="Optional Codex config profile passed via CODEX_PROFILE",
    )
    s_runner_work.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Poll interval in seconds for continuous mode (default: 30)",
    )
    s_runner_work.add_argument(
        "--transport",
        choices=["auto", "poll", "sse"],
        default="auto",
        help="Wait strategy between idle runner cycles (default: auto)",
    )
    s_runner_work.add_argument(
        "--heartbeat-interval",
        type=int,
        default=20,
        help="Heartbeat interval in seconds while waiting or executing (default: 20)",
    )
    s_runner_work.add_argument(
        "--dry-run",
        action="store_true",
        help="Claim jobs but do not start or execute them",
    )
    s_runner_work.add_argument(
        "--linked-project-root",
        dest="linked_project_roots",
        action="append",
        default=[],
        help="Additional linked project root to include in this machine worker; repeat for multiple repos",
    )
    s_runner_work.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll/claim cycle and exit",
    )
    s_runner_work.add_argument(
        "--continuous",
        action="store_true",
        help="Explicitly keep polling until interrupted (default behavior when --once is omitted)",
    )
    add_base_url_flag(s_runner_work)
    add_json_flag(s_runner_work)
    s_runner_work.set_defaults(func=cmd_runner_work, json_output=False)

    s_runner_cancel = runner_sub.add_parser(
        "cancel",
        help="Cancel the active hosted runner job for this repo or one explicit job id",
    )
    s_runner_cancel.add_argument("job_id", nargs="?", default="", help="Optional hosted runner job id")
    s_runner_cancel.add_argument("--lease-id", default="", help="Optional hosted lease id override")
    s_runner_cancel.add_argument("--reason", default="", help="Optional cancellation reason")
    s_runner_cancel.add_argument(
        "--linked-project-root",
        dest="linked_project_roots",
        action="append",
        default=[],
        help="Additional linked project root to search for an active runner lease; repeat for multiple repos",
    )
    add_base_url_flag(s_runner_cancel)
    add_json_flag(s_runner_cancel)
    s_runner_cancel.set_defaults(func=cmd_runner_cancel, json_output=False)

    s_runner_retry = runner_sub.add_parser(
        "retry",
        help="Retry the most recent hosted runner job for this repo or one explicit job id",
    )
    s_runner_retry.add_argument("job_id", nargs="?", default="", help="Optional hosted runner job id")
    s_runner_retry.add_argument("--lease-id", default="", help="Optional hosted lease id override")
    s_runner_retry.add_argument("--reason", default="", help="Optional retry reason")
    s_runner_retry.add_argument(
        "--linked-project-root",
        dest="linked_project_roots",
        action="append",
        default=[],
        help="Additional linked project root to search for a retry target; repeat for multiple repos",
    )
    add_base_url_flag(s_runner_retry)
    add_json_flag(s_runner_retry)
    s_runner_retry.set_defaults(func=cmd_runner_retry, json_output=False)

    s_checkpoint = sub.add_parser("checkpoint", help="Checkpoint operations")
    checkpoint_sub = s_checkpoint.add_subparsers(dest="checkpoint_cmd", required=True)

    s_checkpoint_create = checkpoint_sub.add_parser(
        "create",
        help="Stage changes and create a local governance checkpoint commit",
    )
    s_checkpoint_create.add_argument(
        "-m",
        "--message",
        required=True,
        help="Checkpoint note used in the commit message and ORP checkpoint log",
    )
    s_checkpoint_create.add_argument(
        "--allow-protected-branch",
        action="store_true",
        help="Explicitly allow checkpointing while on a protected branch",
    )
    add_json_flag(s_checkpoint_create)
    s_checkpoint_create.set_defaults(func=cmd_checkpoint_create, json_output=False)

    s_checkpoint_queue = checkpoint_sub.add_parser("queue", help="Queue a hosted checkpoint review")
    s_checkpoint_queue.add_argument("--idea-id", required=True, help="Hosted idea id")
    s_checkpoint_queue.add_argument("--world-id", default="", help="Explicit world id override")
    s_checkpoint_queue.add_argument(
        "--trigger-type",
        default="agent-feedback",
        help="Checkpoint trigger type (default: agent-feedback)",
    )
    s_checkpoint_queue.add_argument("--feature-id", default="", dest="focus_feature", help="Focus one feature id")
    s_checkpoint_queue.add_argument(
        "--detail-section-id",
        default="",
        dest="focus_detail_section",
        help="Focus one detail section id",
    )
    s_checkpoint_queue.add_argument("--user-note", default="", help="Instructional note sent to the worker")
    s_checkpoint_queue.add_argument(
        "--skip-idea-title",
        action="store_true",
        help="Exclude idea title from checkpoint context",
    )
    s_checkpoint_queue.add_argument(
        "--skip-core-plan",
        action="store_true",
        help="Exclude core plan from checkpoint context",
    )
    s_checkpoint_queue.add_argument(
        "--skip-github",
        action="store_true",
        help="Exclude GitHub/web link from checkpoint context",
    )
    s_checkpoint_queue.add_argument(
        "--skip-repo-binding",
        action="store_true",
        help="Exclude world/repo binding from checkpoint context",
    )
    s_checkpoint_queue.add_argument(
        "--include-previous-response-summaries",
        action="store_true",
        help="Include recent response summaries in checkpoint context",
    )
    add_base_url_flag(s_checkpoint_queue)
    add_json_flag(s_checkpoint_queue)
    s_checkpoint_queue.set_defaults(func=cmd_checkpoint_queue, json_output=False)

    s_agent = sub.add_parser("agent", help="Compatibility worker commands with runner-first fallback behavior")
    agent_sub = s_agent.add_subparsers(dest="agent_cmd", required=True)

    s_agent_work = agent_sub.add_parser(
        "work",
        help="Compatibility alias for runner work with legacy checkpoint fallback",
    )
    s_agent_work.add_argument("--agent", default="", help="Optional agent/world selector")
    s_agent_work.add_argument("--codex-bin", default="", help="Codex executable path")
    s_agent_work.add_argument(
        "--codex-config-profile",
        default="",
        help="Optional Codex config profile passed via CODEX_CONFIG_PROFILE",
    )
    s_agent_work.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Poll interval in seconds for continuous mode (default: 30)",
    )
    s_agent_work.add_argument(
        "--transport",
        choices=["auto", "poll", "sse"],
        default="auto",
        help="Wait strategy between idle runner-primary cycles (default: auto)",
    )
    s_agent_work.add_argument(
        "--dry-run",
        action="store_true",
        help="Claim jobs but do not execute Codex or post responses",
    )
    s_agent_work.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll/claim cycle and exit",
    )
    add_base_url_flag(s_agent_work)
    add_json_flag(s_agent_work)
    s_agent_work.set_defaults(func=cmd_agent_work, json_output=False)

    s_discover = sub.add_parser(
        "discover",
        help="Profile-based GitHub discovery and recommendation operations",
    )
    discover_sub = s_discover.add_subparsers(dest="discover_cmd", required=True)

    s_discover_profile = discover_sub.add_parser(
        "profile",
        help="Discovery profile scaffold operations",
    )
    discover_profile_sub = s_discover_profile.add_subparsers(dest="discover_profile_cmd", required=True)
    s_discover_profile_init = discover_profile_sub.add_parser(
        "init",
        help="Scaffold a GitHub discovery profile",
    )
    s_discover_profile_init.add_argument(
        "--out",
        default=DEFAULT_DISCOVER_PROFILE,
        help=f"Output profile path (default: {DEFAULT_DISCOVER_PROFILE})",
    )
    s_discover_profile_init.add_argument(
        "--profile-id",
        default="default",
        help="Profile id (default: default)",
    )
    s_discover_profile_init.add_argument(
        "--owner",
        default="",
        help="GitHub owner login to scan, for example SproutSeeds",
    )
    s_discover_profile_init.add_argument(
        "--owner-type",
        choices=["auto", "user", "org"],
        default="auto",
        help="GitHub owner type (default: auto)",
    )
    s_discover_profile_init.add_argument(
        "--keyword",
        action="append",
        default=[],
        help="Interest keyword (repeatable)",
    )
    s_discover_profile_init.add_argument(
        "--topic",
        action="append",
        default=[],
        help="Preferred repo topic (repeatable)",
    )
    s_discover_profile_init.add_argument(
        "--language",
        action="append",
        default=[],
        help="Preferred language (repeatable)",
    )
    s_discover_profile_init.add_argument(
        "--area",
        action="append",
        default=[],
        help="Preferred issue/repo area keyword, for example docs or compiler (repeatable)",
    )
    s_discover_profile_init.add_argument(
        "--person",
        action="append",
        default=[],
        help="Preferred person/login signal (repeatable)",
    )
    s_discover_profile_init.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_discover_profile_init.set_defaults(func=cmd_discover_profile_init, json_output=False)

    s_discover_github = discover_sub.add_parser(
        "github",
        help="GitHub-owner discovery operations",
    )
    discover_github_sub = s_discover_github.add_subparsers(dest="discover_github_cmd", required=True)
    s_discover_github_scan = discover_github_sub.add_parser(
        "scan",
        help="Scan a GitHub owner space and rank repo/issue/person matches",
    )
    s_discover_github_scan.add_argument(
        "--profile",
        default=DEFAULT_DISCOVER_PROFILE,
        help=f"Discovery profile path (default: {DEFAULT_DISCOVER_PROFILE})",
    )
    s_discover_github_scan.add_argument(
        "--scan-id",
        default="",
        help="Optional scan id override",
    )
    s_discover_github_scan.add_argument(
        "--repos-fixture",
        default="",
        help="Advanced/testing: read repos from fixture JSON instead of GitHub API",
    )
    s_discover_github_scan.add_argument(
        "--issues-fixture",
        default="",
        help="Advanced/testing: read issues map fixture JSON instead of GitHub API",
    )
    s_discover_github_scan.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_discover_github_scan.set_defaults(func=cmd_discover_github_scan, json_output=False)

    s_exchange = sub.add_parser(
        "exchange",
        help="Local-first repository and project synthesis for reusable knowledge transfer",
    )
    exchange_sub = s_exchange.add_subparsers(dest="exchange_cmd", required=True)

    s_exchange_repo = exchange_sub.add_parser(
        "repo",
        help="Repository and local project exchange operations",
    )
    exchange_repo_sub = s_exchange_repo.add_subparsers(dest="exchange_repo_cmd", required=True)
    s_exchange_repo_synthesize = exchange_repo_sub.add_parser(
        "synthesize",
        help="Synthesize another repository or project directory into structured ORP exchange artifacts",
    )
    s_exchange_repo_synthesize.add_argument(
        "source",
        help="Source directory, git URL, or owner/repo reference to synthesize",
    )
    s_exchange_repo_synthesize.add_argument(
        "--exchange-id",
        default="",
        help="Optional exchange id override",
    )
    s_exchange_repo_synthesize.add_argument(
        "--allow-git-init",
        action="store_true",
        help="If the source is a local non-git directory, initialize git there before synthesis",
    )
    add_json_flag(s_exchange_repo_synthesize)
    s_exchange_repo_synthesize.set_defaults(func=cmd_exchange_repo_synthesize, json_output=False)

    s_collab = sub.add_parser(
        "collaborate",
        help="Built-in repository collaboration setup and workflow operations",
    )
    collab_sub = s_collab.add_subparsers(dest="collaborate_cmd", required=True)

    s_collab_init = collab_sub.add_parser(
        "init",
        help="Scaffold collaboration workspace and configs in the target repository",
    )
    s_collab_init.add_argument(
        "--target-repo-root",
        default=".",
        help="Repository root to scaffold (default: current --repo-root)",
    )
    s_collab_init.add_argument(
        "--workspace-root",
        default="issue-smashers",
        help="Workspace root relative to target repo (default: issue-smashers)",
    )
    s_collab_init.add_argument(
        "--github-repo",
        default="",
        help="Optional GitHub repo slug, for example owner/repo",
    )
    s_collab_init.add_argument(
        "--github-author",
        default="",
        help="Optional GitHub login used for coordination-aware gates",
    )
    s_collab_init.add_argument(
        "--var",
        action="append",
        default=[],
        help="Advanced internal template override KEY=VALUE (repeatable)",
    )
    s_collab_init.add_argument(
        "--report",
        default="",
        help="Optional install report output path",
    )
    s_collab_init.add_argument(
        "--strict-deps",
        action="store_true",
        help="Exit non-zero if dependency audit finds missing paths",
    )
    s_collab_init.add_argument(
        "--no-bootstrap",
        dest="bootstrap",
        action="store_false",
        help="Disable starter collaboration workspace scaffold",
    )
    s_collab_init.add_argument(
        "--overwrite-bootstrap",
        action="store_true",
        help="Allow overwriting existing scaffolded collaboration files",
    )
    s_collab_init.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_collab_init.set_defaults(func=cmd_collaborate_init, json_output=False, bootstrap=True)

    s_collab_workflows = collab_sub.add_parser(
        "workflows",
        help="List built-in collaboration workflows and their backing configs",
    )
    s_collab_workflows.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_collab_workflows.set_defaults(func=cmd_collaborate_workflows, json_output=False)

    s_collab_gates = collab_sub.add_parser(
        "gates",
        help="Show the gate chain for a collaboration workflow",
    )
    s_collab_gates.add_argument(
        "--workflow",
        default="full_flow",
        help="Workflow id (default: full_flow)",
    )
    s_collab_gates.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_collab_gates.set_defaults(func=cmd_collaborate_gates, json_output=False)

    s_collab_run = collab_sub.add_parser(
        "run",
        help="Run a built-in collaboration workflow",
    )
    s_collab_run.add_argument(
        "--workflow",
        default="full_flow",
        help="Workflow id (default: full_flow)",
    )
    s_collab_run.add_argument(
        "--run-id",
        default="",
        help="Optional run id override",
    )
    s_collab_run.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_collab_run.set_defaults(func=cmd_collaborate_run, json_output=False)

    s_init = sub.add_parser("init", help="Make this repo ORP-governed with local-first git safety")
    s_init.add_argument(
        "--default-branch",
        default="main",
        help="Protected/default branch expectation (default: main)",
    )
    s_init.add_argument(
        "--github-repo",
        default="",
        help="Optional GitHub repo context as owner/repo",
    )
    s_init.add_argument(
        "--remote-url",
        default="",
        help="Optional remote URL to record in ORP governance metadata",
    )
    s_init.add_argument(
        "--allow-protected-branch-work",
        action="store_true",
        help="Allow ORP governance to treat protected-branch work as explicitly permitted",
    )
    s_init.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_init.set_defaults(func=cmd_init, json_output=False)

    s_status = sub.add_parser("status", help="Show ORP repo governance safety and runtime status")
    add_json_flag(s_status)
    s_status.set_defaults(func=cmd_status, json_output=False)

    s_branch = sub.add_parser("branch", help="ORP repo governance branch operations")
    branch_sub = s_branch.add_subparsers(dest="branch_cmd", required=True)
    s_branch_start = branch_sub.add_parser(
        "start",
        help="Create or switch to a safe work branch for meaningful edits",
    )
    s_branch_start.add_argument("name", help="Work branch name")
    s_branch_start.add_argument(
        "--from",
        dest="from_ref",
        default="",
        help="Base ref for new branch creation (default: current branch or HEAD)",
    )
    s_branch_start.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow branch creation/switching when the working tree is dirty",
    )
    add_json_flag(s_branch_start)
    s_branch_start.set_defaults(func=cmd_branch_start, json_output=False)

    s_backup = sub.add_parser(
        "backup",
        help="Create a safe checkpointed backup and push it to a dedicated remote ref when possible",
    )
    s_backup.add_argument(
        "-m",
        "--message",
        default="",
        help="Optional checkpoint note when dirty local changes need to be captured before backup",
    )
    s_backup.add_argument(
        "--remote",
        default="",
        help="Optional remote name override (default: upstream remote or origin when configured)",
    )
    s_backup.add_argument(
        "--prefix",
        default="orp/backup",
        help="Remote branch prefix for pushed backup refs (default: orp/backup)",
    )
    s_backup.add_argument(
        "--allow-protected-branch",
        action="store_true",
        help="Allow checkpointing directly on a protected branch instead of auto-creating a backup work branch",
    )
    add_json_flag(s_backup)
    s_backup.set_defaults(func=cmd_backup, json_output=False)

    s_ready = sub.add_parser("ready", help="Mark the repo locally ready after validation and checkpointing")
    s_ready.add_argument("--run-id", default="", help="Optional validation run id override")
    s_ready.add_argument("--run-json", default="", help="Optional validation RUN.json path override")
    s_ready.add_argument(
        "--require-remote-ready",
        action="store_true",
        help="Fail unless remote-aware readiness conditions are also satisfied",
    )
    add_json_flag(s_ready)
    s_ready.set_defaults(func=cmd_ready, json_output=False)

    s_doctor = sub.add_parser("doctor", help="Inspect and optionally repair ORP governance health")
    s_doctor.add_argument(
        "--fix",
        action="store_true",
        help="Repair missing governance runtime files when safe to do so",
    )
    s_doctor.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when warnings are present",
    )
    add_json_flag(s_doctor)
    s_doctor.set_defaults(func=cmd_doctor, json_output=False)

    s_cleanup = sub.add_parser("cleanup", help="Inspect or apply safe stale-branch cleanup operations")
    s_cleanup.add_argument(
        "--apply",
        action="store_true",
        help="Apply the requested cleanup operations instead of only reporting them",
    )
    s_cleanup.add_argument(
        "--delete-merged",
        action="store_true",
        help="Delete local branches that are already merged into the protected default branch",
    )
    add_json_flag(s_cleanup)
    s_cleanup.set_defaults(func=cmd_cleanup, json_output=False)

    s_frontier = sub.add_parser(
        "frontier",
        help="Version-stack, milestone, and phase frontier operations for agent-first research programs",
    )
    frontier_sub = s_frontier.add_subparsers(dest="frontier_cmd", required=True)

    s_frontier_init = frontier_sub.add_parser(
        "init",
        help="Initialize the ORP frontier control surface under orp/frontier/",
    )
    s_frontier_init.add_argument("--program-id", default="", help="Frontier program id")
    s_frontier_init.add_argument("--label", default="", help="Human label for the frontier program")
    s_frontier_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing frontier control surface",
    )
    add_json_flag(s_frontier_init)
    s_frontier_init.set_defaults(func=cmd_frontier_init, json_output=False)

    s_frontier_state = frontier_sub.add_parser(
        "state",
        help="Show the exact live frontier point",
    )
    add_json_flag(s_frontier_state)
    s_frontier_state.set_defaults(func=cmd_frontier_state, json_output=False)

    s_frontier_roadmap = frontier_sub.add_parser(
        "roadmap",
        help="Show the exact active milestone roadmap",
    )
    add_json_flag(s_frontier_roadmap)
    s_frontier_roadmap.set_defaults(func=cmd_frontier_roadmap, json_output=False)

    s_frontier_checklist = frontier_sub.add_parser(
        "checklist",
        help="Show the near-term exact/structured/horizon checklist",
    )
    add_json_flag(s_frontier_checklist)
    s_frontier_checklist.set_defaults(func=cmd_frontier_checklist, json_output=False)

    s_frontier_stack = frontier_sub.add_parser(
        "stack",
        help="Show the larger major-version stack",
    )
    add_json_flag(s_frontier_stack)
    s_frontier_stack.set_defaults(func=cmd_frontier_stack, json_output=False)

    s_frontier_add_version = frontier_sub.add_parser(
        "add-version",
        help="Add one major version to the frontier stack",
    )
    s_frontier_add_version.add_argument("--id", required=True, help="Version id, for example v11")
    s_frontier_add_version.add_argument("--label", required=True, help="Version label")
    s_frontier_add_version.add_argument("--intent", default="", help="Optional version intent")
    s_frontier_add_version.add_argument(
        "--status",
        default="planned",
        choices=["planned", "active", "horizon", "complete"],
        help="Version status (default: planned)",
    )
    add_json_flag(s_frontier_add_version)
    s_frontier_add_version.set_defaults(func=cmd_frontier_add_version, json_output=False)

    s_frontier_add_milestone = frontier_sub.add_parser(
        "add-milestone",
        help="Add one milestone under a major version",
    )
    s_frontier_add_milestone.add_argument("--version", required=True, help="Parent version id")
    s_frontier_add_milestone.add_argument("--id", required=True, help="Milestone id, for example v10.4")
    s_frontier_add_milestone.add_argument("--label", required=True, help="Milestone label")
    s_frontier_add_milestone.add_argument(
        "--band",
        default="structured",
        choices=list(FRONTIER_BANDS),
        help="Planning band (default: structured)",
    )
    s_frontier_add_milestone.add_argument(
        "--status",
        default="planned",
        choices=["planned", "active", "horizon", "complete"],
        help="Milestone status (default: planned)",
    )
    s_frontier_add_milestone.add_argument(
        "--depends-on",
        action="append",
        default=[],
        help="Dependency milestone or phase id (repeatable)",
    )
    s_frontier_add_milestone.add_argument(
        "--success-criterion",
        action="append",
        default=[],
        help="Milestone success criterion (repeatable)",
    )
    add_json_flag(s_frontier_add_milestone)
    s_frontier_add_milestone.set_defaults(func=cmd_frontier_add_milestone, json_output=False)

    s_frontier_add_phase = frontier_sub.add_parser(
        "add-phase",
        help="Add one phase under a milestone",
    )
    s_frontier_add_phase.add_argument("--milestone", required=True, help="Parent milestone id")
    s_frontier_add_phase.add_argument("--id", required=True, help="Phase id")
    s_frontier_add_phase.add_argument("--label", required=True, help="Phase label")
    s_frontier_add_phase.add_argument(
        "--status",
        default="planned",
        choices=["planned", "active", "complete"],
        help="Phase status (default: planned)",
    )
    s_frontier_add_phase.add_argument("--goal", default="", help="Optional phase goal")
    s_frontier_add_phase.add_argument(
        "--depends-on",
        action="append",
        default=[],
        help="Dependency phase or milestone id (repeatable)",
    )
    s_frontier_add_phase.add_argument(
        "--requirement",
        action="append",
        default=[],
        help="Requirement identifier or note (repeatable)",
    )
    s_frontier_add_phase.add_argument(
        "--success-criterion",
        action="append",
        default=[],
        help="Phase success criterion (repeatable)",
    )
    s_frontier_add_phase.add_argument(
        "--plan",
        action="append",
        default=[],
        help="Plan id or plan note (repeatable)",
    )
    s_frontier_add_phase.add_argument(
        "--compute-point-id",
        default="",
        help="Optional linked compute point id",
    )
    s_frontier_add_phase.add_argument(
        "--allowed-rung",
        action="append",
        default=[],
        help="Allowed compute rung for the compute hook (repeatable)",
    )
    s_frontier_add_phase.add_argument(
        "--paid-requires-user-approval",
        action="store_true",
        help="Mark the attached compute hook as requiring explicit user approval for paid compute",
    )
    add_json_flag(s_frontier_add_phase)
    s_frontier_add_phase.set_defaults(func=cmd_frontier_add_phase, json_output=False)

    s_frontier_set_live = frontier_sub.add_parser(
        "set-live",
        help="Update the exact live frontier pointer",
    )
    s_frontier_set_live.add_argument("--version", required=True, help="Active version id")
    s_frontier_set_live.add_argument("--milestone", required=True, help="Active milestone id")
    s_frontier_set_live.add_argument("--phase", default="", help="Active phase id")
    s_frontier_set_live.add_argument(
        "--band",
        default="",
        choices=["", *FRONTIER_BANDS],
        help="Optional explicit band override",
    )
    s_frontier_set_live.add_argument("--next-action", default="", help="Optional live next action override")
    s_frontier_set_live.add_argument(
        "--blocked-by",
        action="append",
        default=[],
        help="Current blocker id or note (repeatable)",
    )
    add_json_flag(s_frontier_set_live)
    s_frontier_set_live.set_defaults(func=cmd_frontier_set_live, json_output=False)

    s_frontier_render = frontier_sub.add_parser(
        "render",
        help="Refresh the materialized frontier JSON and markdown views",
    )
    add_json_flag(s_frontier_render)
    s_frontier_render.set_defaults(func=cmd_frontier_render, json_output=False)

    s_frontier_doctor = frontier_sub.add_parser(
        "doctor",
        help="Validate frontier consistency and optionally re-render views",
    )
    s_frontier_doctor.add_argument(
        "--fix",
        action="store_true",
        help="Re-render materialized frontier views when the frontier is otherwise consistent",
    )
    add_json_flag(s_frontier_doctor)
    s_frontier_doctor.set_defaults(func=cmd_frontier_doctor, json_output=False)

    s_kernel = sub.add_parser("kernel", help="Reasoning-kernel artifact operations")
    kernel_sub = s_kernel.add_subparsers(dest="kernel_cmd", required=True)

    s_kernel_validate = kernel_sub.add_parser(
        "validate",
        help="Validate one kernel artifact against typed ORP structure rules",
    )
    s_kernel_validate.add_argument("artifact", help="Kernel artifact path (.yml, .yaml, or .json)")
    s_kernel_validate.add_argument(
        "--artifact-class",
        default="",
        help="Optional expected artifact class override",
    )
    s_kernel_validate.add_argument(
        "--required-field",
        action="append",
        default=[],
        help="Extra required field to enforce during validation (repeatable)",
    )
    add_json_flag(s_kernel_validate)
    s_kernel_validate.set_defaults(func=cmd_kernel_validate, json_output=False)

    s_kernel_scaffold = kernel_sub.add_parser(
        "scaffold",
        help="Write a starter kernel artifact template for a typed ORP artifact class",
    )
    s_kernel_scaffold.add_argument(
        "--artifact-class",
        required=True,
        choices=sorted(KERNEL_ARTIFACT_CLASS_REQUIREMENTS.keys()),
        help="Typed kernel artifact class to scaffold",
    )
    s_kernel_scaffold.add_argument(
        "--out",
        required=True,
        help="Output artifact path (.yml/.yaml or .json)",
    )
    s_kernel_scaffold.add_argument(
        "--name",
        default="",
        help="Optional name hint used in scaffold placeholders",
    )
    s_kernel_scaffold.add_argument(
        "--format",
        default="",
        choices=["", "yaml", "json"],
        help="Optional explicit output format (default: infer from file extension)",
    )
    s_kernel_scaffold.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing artifact at --out",
    )
    add_json_flag(s_kernel_scaffold)
    s_kernel_scaffold.set_defaults(func=cmd_kernel_scaffold, json_output=False)

    s_kernel_stats = kernel_sub.add_parser(
        "stats",
        help="Summarize observed kernel validation pressure from RUN.json artifacts",
    )
    s_kernel_stats.add_argument(
        "--run-id",
        action="append",
        default=[],
        help="Specific run id to include (repeatable). Defaults to all discovered runs.",
    )
    s_kernel_stats.add_argument(
        "--run-json",
        action="append",
        default=[],
        help="Explicit RUN.json path to include (repeatable). Defaults to all discovered runs.",
    )
    add_json_flag(s_kernel_stats)
    s_kernel_stats.set_defaults(func=cmd_kernel_stats, json_output=False)

    s_kernel_propose = kernel_sub.add_parser(
        "propose",
        help="Scaffold a governed kernel-evolution proposal artifact",
    )
    s_kernel_propose.add_argument(
        "--kind",
        required=True,
        choices=["add_field", "new_class", "requirement_change", "deprecate_field"],
        help="Type of kernel evolution proposal",
    )
    s_kernel_propose.add_argument(
        "--title",
        required=True,
        help="Proposal title",
    )
    s_kernel_propose.add_argument(
        "--artifact-class",
        action="append",
        default=[],
        choices=sorted(KERNEL_ARTIFACT_CLASS_REQUIREMENTS.keys()),
        help="Affected kernel artifact class (repeatable)",
    )
    s_kernel_propose.add_argument(
        "--field",
        action="append",
        default=[],
        help="Affected kernel field name (repeatable)",
    )
    s_kernel_propose.add_argument(
        "--slug",
        default="",
        help="Optional output slug override",
    )
    s_kernel_propose.add_argument(
        "--out",
        default="",
        help="Optional output path (default: analysis/kernel-proposals/<slug>.yml)",
    )
    s_kernel_propose.add_argument(
        "--format",
        default="",
        choices=["", "yaml", "json"],
        help="Optional explicit output format",
    )
    s_kernel_propose.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing proposal at the output path",
    )
    add_json_flag(s_kernel_propose)
    s_kernel_propose.set_defaults(func=cmd_kernel_propose, json_output=False)

    s_kernel_migrate = kernel_sub.add_parser(
        "migrate",
        help="Rewrite a kernel artifact into the current canonical field order and schema version",
    )
    s_kernel_migrate.add_argument("artifact", help="Kernel artifact path (.yml, .yaml, or .json)")
    s_kernel_migrate.add_argument(
        "--out",
        default="",
        help="Optional output path (default: rewrite in place)",
    )
    s_kernel_migrate.add_argument(
        "--format",
        default="",
        choices=["", "yaml", "json"],
        help="Optional explicit output format",
    )
    s_kernel_migrate.add_argument(
        "--drop-unknown-fields",
        action="store_true",
        help="Drop unknown fields instead of failing migration",
    )
    s_kernel_migrate.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing --out path",
    )
    add_json_flag(s_kernel_migrate)
    s_kernel_migrate.set_defaults(func=cmd_kernel_migrate, json_output=False)

    s_gate = sub.add_parser("gate", help="Gate operations")
    gate_sub = s_gate.add_subparsers(dest="gate_cmd", required=True)
    s_run = gate_sub.add_parser("run", help="Run configured gates for a profile")
    s_run.add_argument("--profile", required=True, help="Profile name from config")
    s_run.add_argument("--run-id", default="", help="Optional run id override")
    s_run.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_run.set_defaults(func=cmd_gate_run, json_output=False)

    s_packet = sub.add_parser("packet", help="Packet operations")
    packet_sub = s_packet.add_subparsers(dest="packet_cmd", required=True)
    s_emit = packet_sub.add_parser("emit", help="Emit packet from latest or specified run")
    s_emit.add_argument("--profile", required=True, help="Profile name from config")
    s_emit.add_argument("--run-id", default="", help="Run id (defaults to last run)")
    s_emit.add_argument("--kind", default="", help="Packet kind override")
    s_emit.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_emit.set_defaults(func=cmd_packet_emit, json_output=False)

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
    s_erdos_sync.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_erdos_sync.set_defaults(func=cmd_erdos_sync, json_output=False)

    s_pack = sub.add_parser("pack", help="Advanced/internal profile pack operations")
    pack_sub = s_pack.add_subparsers(dest="pack_cmd", required=True)

    s_pack_list = pack_sub.add_parser("list", help="List available local ORP packs")
    s_pack_list.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_pack_list.set_defaults(func=cmd_pack_list, json_output=False)

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
        default=[],
        help=(
            "Component to install (repeatable). "
            "Valid values depend on the selected pack. "
            "Default when omitted: the pack's default install set."
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
        help="Install report output path (default depends on selected pack)",
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
    s_pack_install.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_pack_install.set_defaults(func=cmd_pack_install, json_output=False)

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
        default=[],
        help="Install component to include (repeatable, install mode only; valid values depend on the pack)",
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
    s_pack_fetch.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_pack_fetch.set_defaults(func=cmd_pack_fetch, json_output=False)

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
    s_report_summary.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_report_summary.set_defaults(func=cmd_report_summary, json_output=False)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "cmd", None):
        return cmd_home(
            argparse.Namespace(
                repo_root=args.repo_root,
                config=args.config,
                json_output=False,
            )
        )
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
