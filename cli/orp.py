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
- built-in abilities over mode switches
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
from urllib import parse as urlparse
from urllib import request as urlrequest


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


def _tool_package_name() -> str:
    package_json = Path(__file__).resolve().parent.parent / "package.json"
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


def _ensure_dirs(repo_root: Path) -> None:
    (repo_root / "orp" / "packets").mkdir(parents=True, exist_ok=True)
    (repo_root / "orp" / "artifacts").mkdir(parents=True, exist_ok=True)
    (repo_root / "orp" / "discovery" / "github").mkdir(parents=True, exist_ok=True)
    state_path = repo_root / "orp" / "state.json"
    if not state_path.exists():
        _write_json(
            state_path,
            {
                "last_run_id": "",
                "last_packet_id": "",
                "runs": {},
                "last_erdos_sync": {},
                "last_discover_scan_id": "",
                "discovery_scans": {},
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
            "protocol": "PROTOCOL.md",
            "install": "INSTALL.md",
            "agent_integration": "AGENT_INTEGRATION.md",
            "agent_loop": "docs/AGENT_LOOP.md",
            "discover": "docs/DISCOVER.md",
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
        },
        "schemas": {
            "config": "spec/v1/orp.config.schema.json",
            "packet": "spec/v1/packet.schema.json",
            "profile_pack": "spec/v1/profile-pack.schema.json",
        },
        "abilities": [
            {
                "id": "discover",
                "description": "Profile-based GitHub discovery for repos, issues, and people signals.",
                "entrypoints": [
                    ["discover", "profile", "init"],
                    ["discover", "github", "scan"],
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
            {"name": "discover_profile_init", "path": ["discover", "profile", "init"], "json_output": True},
            {"name": "discover_github_scan", "path": ["discover", "github", "scan"], "json_output": True},
            {"name": "collaborate_init", "path": ["collaborate", "init"], "json_output": True},
            {"name": "collaborate_workflows", "path": ["collaborate", "workflows"], "json_output": True},
            {"name": "collaborate_gates", "path": ["collaborate", "gates"], "json_output": True},
            {"name": "collaborate_run", "path": ["collaborate", "run"], "json_output": True},
            {"name": "init", "path": ["init"], "json_output": True},
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
            "Discovery profiles in ORP are portable search-intent files managed directly by ORP.",
            "Collaboration is a built-in ORP ability exposed through `orp collaborate ...`.",
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

    quick_actions = [
        {
            "label": "Scaffold a discovery profile for GitHub scanning",
            "command": "orp discover profile init --json",
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
    ]
    if not runtime_initialized:
        quick_actions.insert(
            0,
            {
                "label": "Initialize base ORP runtime only",
                "command": "orp init",
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
        "abilities": [
            {
                "id": "discover",
                "description": "Profile-based GitHub discovery for repos, issues, and people signals.",
                "entrypoints": [
                    "orp discover profile init --json",
                    f"orp discover github scan --profile {DEFAULT_DISCOVER_PROFILE} --json",
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
    abilities = payload.get("abilities", [])
    collaboration = payload.get("collaboration", {})
    packs = payload.get("packs", [])
    discovery = payload.get("discovery", {})
    quick_actions = payload.get("quick_actions", [])

    lines: list[str] = []
    lines.append(f"ORP {tool.get('version', 'unknown')}")
    lines.append("Open Research Protocol CLI")
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
    lines.append("Abilities")
    if isinstance(abilities, list) and abilities:
        for row in abilities:
            if not isinstance(row, dict):
                continue
            ability_id = str(row.get("id", "")).strip()
            desc = _truncate(str(row.get("description", "")).strip())
            lines.append(f"  - {ability_id}")
            if desc:
                lines.append(f"    {desc}")
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
        for row in workflows[:3]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"  - {row.get('id', '')}: {_truncate(str(row.get('description', '')).strip(), limit=64)}"
            )
        if len(workflows) > 3:
            lines.append("  - ... run `orp collaborate workflows --json` for the full list")

    lines.append("")
    lines.append("Advanced Bundles")
    if isinstance(packs, list) and packs:
        for pack in packs:
            if not isinstance(pack, dict):
                continue
            pack_id = str(pack.get("id", "")).strip()
            version = str(pack.get("version", "")).strip()
            desc = _truncate(str(pack.get("description", "")).strip())
            title = f"  - {pack_id}"
            if version:
                title += f" ({version})"
            lines.append(title)
            if desc:
                lines.append(f"    {desc}")
    else:
        lines.append("  (no local internal bundles discovered)")

    lines.append("")
    lines.append("Discovery")
    for key in ["readme", "protocol", "agent_integration", "agent_loop", "discover", "profile_packs"]:
        value = discovery.get(key)
        if isinstance(value, str) and value:
            lines.append(f"  {key}: {value}")

    lines.append("")
    lines.append("Quick Actions")
    if isinstance(quick_actions, list):
        for row in quick_actions:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label", "")).strip()
            command = str(row.get("command", "")).strip()
            if not label or not command:
                continue
            lines.append(f"  - {label}")
            lines.append(f"    {command}")

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
    _ensure_dirs(repo_root)

    config_path = repo_root / args.config
    config_action = "kept"
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
        config_action = "created"

    result = {
        "config_action": config_action,
        "config_path": str(config_path),
        "runtime_root": str(repo_root / "orp"),
    }
    if args.json_output:
        _print_json(result)
    else:
        if config_action == "created":
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
                "evidence_paths": evidence_paths,
                "evidence_status": evidence_status,
                "evidence_note": evidence_note,
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

    s_home = sub.add_parser(
        "home",
        help="Show ORP home screen with packs, repo status, and quick-start commands",
    )
    s_home.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_home.set_defaults(func=cmd_home, json_output=False)

    s_about = sub.add_parser(
        "about",
        help="Describe ORP discovery surfaces and machine-friendly interfaces",
    )
    s_about.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_about.set_defaults(func=cmd_about, json_output=False)

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

    s_init = sub.add_parser("init", help="Initialize runtime folders and starter config")
    s_init.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print machine-readable JSON",
    )
    s_init.set_defaults(func=cmd_init, json_output=False)

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
