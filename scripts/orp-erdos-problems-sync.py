#!/usr/bin/env python3
"""Sync Erdos problems catalog data from erdosproblems.com.

Outputs four JSON files:
- all problems
- open problems
- closed problems
- active problems (default active set is open)

This keeps ORP core general while letting pack profiles use a canonical
problem catalog snapshot for gating and planning.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib import request


DEFAULT_SOURCE_URL = "https://erdosproblems.com/range/1-end"
DEFAULT_USER_AGENT = "ORP-ErdosSync/1.0 (+https://github.com/teorth/erdosproblems)"

SOLVE_COUNT_RE = re.compile(
    r"([0-9]+)\s+solved\s+out\s+of\s+([0-9]+)\s+shown", re.IGNORECASE
)


def _now_utc() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_tags(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", text)
    return _collapse_ws(html.unescape(without_tags))


def _fetch_html(url: str, timeout_sec: int, user_agent: str) -> str:
    req = request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with request.urlopen(req, timeout=timeout_sec) as resp:  # nosec B310
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def _extract_solve_count(page_html: str) -> dict[str, Any]:
    m = SOLVE_COUNT_RE.search(page_html)
    if not m:
        return {
            "raw": "",
            "solved": None,
            "shown": None,
        }
    return {
        "raw": m.group(0),
        "solved": int(m.group(1)),
        "shown": int(m.group(2)),
    }


def _extract_first(pattern: str, text: str, flags: int = 0) -> str:
    m = re.search(pattern, text, flags)
    if not m:
        return ""
    return m.group(1)


def _parse_problem_block(block_html: str) -> dict[str, Any] | None:
    status_dom = _extract_first(
        r'<div\s+class="problem-text"\s+id="(open|solved)"', block_html
    )
    if not status_dom:
        return None

    problem_id_text = _extract_first(r'<div id="problem_id">\s*<a href="/([0-9]+)">', block_html)
    if not problem_id_text:
        return None
    problem_id = int(problem_id_text)

    status_label = _strip_tags(
        _extract_first(
            r'<span class="tooltip">\s*([^<]+?)\s*<span class="tooltiptext">',
            block_html,
            flags=re.DOTALL,
        )
    )
    status_detail = _strip_tags(
        _extract_first(
            r'<span class="tooltiptext">\s*(.*?)\s*</span>',
            block_html,
            flags=re.DOTALL,
        )
    )

    prize_block = _extract_first(r"<div id=\"prize\">(.*?)</div>", block_html, flags=re.DOTALL)
    prize_amount = _strip_tags(_extract_first(r"-\s*([^<]+)$", prize_block, flags=re.MULTILINE))
    if not prize_amount:
        prize_amount = _strip_tags(_extract_first(r"(\$[0-9][0-9,]*)", prize_block))

    statement = _strip_tags(_extract_first(r'<div id="content">(.*?)</div>', block_html, flags=re.DOTALL))

    tags_block = _extract_first(r'<div id="tags">(.*?)</div>', block_html, flags=re.DOTALL)
    tags = [_strip_tags(x) for x in re.findall(r"<a [^>]*>(.*?)</a>", tags_block, flags=re.DOTALL)]
    tags = [t for t in tags if t]

    last_edited = _strip_tags(
        _extract_first(r"This page was last edited\s+([^<]+)\.", block_html)
    )
    latex_path = _extract_first(r'<a href="(/latex/[0-9]+)">View the LaTeX source</a>', block_html)

    external_block = _extract_first(r'<div class="external">(.*?)</div>', block_html, flags=re.DOTALL)
    external_text = _strip_tags(external_block)

    formalized_yes_url = _extract_first(
        r'Formalised statement\?\s*<a href="([^"]*ErdosProblems/[^"]+\.lean)"',
        external_block,
        flags=re.DOTALL,
    )
    if formalized_yes_url:
        formalized: bool | None = True
        formalized_url = formalized_yes_url
    elif re.search(r"Formalised statement\?\s*No\b", external_text):
        formalized = False
        formalized_url = ""
    else:
        formalized = None
        formalized_url = ""

    oeis_urls = sorted(
        set(re.findall(r'https?://oeis\.org/[A-Za-z0-9]+', external_block))
    )

    comments_match = re.search(
        r'href="/forum/discuss/([0-9]+)">\s*([0-9]+)\s+comments?',
        block_html,
        flags=re.DOTALL,
    )
    if comments_match:
        comments_problem_id = int(comments_match.group(1))
        comments_count = int(comments_match.group(2))
    else:
        comments_problem_id = problem_id
        comments_count = None

    if status_dom == "open":
        status_bucket = "open"
    elif status_dom == "solved":
        status_bucket = "closed"
    else:
        status_bucket = "unknown"

    return {
        "problem_id": problem_id,
        "problem_url": f"/{problem_id}",
        "status_bucket": status_bucket,
        "status_dom_id": status_dom,
        "status_label": status_label,
        "status_detail": status_detail,
        "prize_amount": prize_amount,
        "statement": statement,
        "tags": tags,
        "last_edited": last_edited,
        "latex_path": latex_path,
        "formalized": formalized,
        "formalized_url": formalized_url,
        "oeis_urls": oeis_urls,
        "comments_problem_id": comments_problem_id,
        "comments_count": comments_count,
    }


def _parse_problems(page_html: str) -> list[dict[str, Any]]:
    chunks = page_html.split('<div class="problem-box">')
    if len(chunks) <= 1:
        return []

    out: dict[int, dict[str, Any]] = {}
    for chunk in chunks[1:]:
        record = _parse_problem_block(chunk)
        if not record:
            continue
        out[int(record["problem_id"])] = record
    return [out[k] for k in sorted(out)]


def _summary(problems: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(problems)
    open_count = sum(1 for p in problems if p.get("status_bucket") == "open")
    closed_count = sum(1 for p in problems if p.get("status_bucket") == "closed")
    unknown_count = total - open_count - closed_count
    status_label_counts: dict[str, int] = {}
    for p in problems:
        label = str(p.get("status_label", "")).strip()
        if not label:
            label = "UNKNOWN"
        status_label_counts[label] = status_label_counts.get(label, 0) + 1
    return {
        "total": total,
        "open": open_count,
        "closed": closed_count,
        "unknown": unknown_count,
        "status_label_counts": dict(sorted(status_label_counts.items())),
    }


def _build_payload(
    *,
    subset: str,
    active_status: str,
    source_url: str,
    source_hash: str,
    solve_count: dict[str, Any],
    synced_at_utc: str,
    problems: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "subset": subset,
        "active_status": active_status,
        "generated_at_utc": synced_at_utc,
        "source": {
            "site": "erdosproblems.com",
            "url": source_url,
            "source_sha256": source_hash,
            "solve_count": solve_count,
        },
        "summary": _summary(problems),
        "problem_ids": [int(p["problem_id"]) for p in problems],
        "problems": problems,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _statement_preview(text: str, max_chars: int) -> str:
    t = _collapse_ws(text)
    if len(t) <= max_chars:
        return t
    if max_chars <= 3:
        return t[:max_chars]
    return t[: max_chars - 3].rstrip() + "..."


def _problem_public_url(problem_id: int) -> str:
    return f"https://erdosproblems.com/{problem_id}"


def _write_open_list_markdown(
    *,
    path: Path,
    open_problems: list[dict[str, Any]],
    source_url: str,
    synced_at_utc: str,
    max_statement_chars: int,
) -> None:
    lines: list[str] = []
    lines.append("# Erdos Open Problems (Active Snapshot)")
    lines.append("")
    lines.append(f"- generated_at_utc: `{synced_at_utc}`")
    lines.append(f"- source_url: `{source_url}`")
    lines.append(f"- total_open: `{len(open_problems)}`")
    lines.append("")
    for p in open_problems:
        pid = int(p["problem_id"])
        link = _problem_public_url(pid)
        label = str(p.get("status_label", "OPEN")).strip() or "OPEN"
        prize = str(p.get("prize_amount", "")).strip()
        tags = [str(t).strip() for t in p.get("tags", []) if str(t).strip()]
        tags_text = ", ".join(tags)
        statement = _statement_preview(str(p.get("statement", "")), max_statement_chars)
        last_edited = str(p.get("last_edited", "")).strip()
        suffix_parts = [label]
        if prize:
            suffix_parts.append(prize)
        if tags_text:
            suffix_parts.append(tags_text)
        suffix = " | ".join(suffix_parts)
        line = f"- [#{pid}]({link})"
        if suffix:
            line += f" — {suffix}"
        if last_edited:
            line += f" — edited: {last_edited}"
        if statement:
            line += f" — {statement}"
        lines.append(line)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_selected_problem_payload(
    *,
    out_path: Path,
    synced_at_utc: str,
    source_url: str,
    source_hash: str,
    solve_count: dict[str, Any],
    problem: dict[str, Any],
) -> None:
    payload = {
        "schema_version": "1.0.0",
        "selected_at_utc": synced_at_utc,
        "source": {
            "site": "erdosproblems.com",
            "url": source_url,
            "source_sha256": source_hash,
            "solve_count": solve_count,
        },
        "problem": problem,
    }
    _write_json(out_path, payload)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sync Erdos problems catalog from erdosproblems.com")
    p.add_argument("--source-url", default=DEFAULT_SOURCE_URL, help="Source URL (default: range/1-end).")
    p.add_argument("--input-html", default="", help="Optional local HTML file (skip network fetch).")
    p.add_argument("--write-html-snapshot", default="", help="Optional path to write fetched HTML snapshot.")
    p.add_argument("--timeout-sec", type=int, default=90, help="HTTP timeout in seconds (default: 90).")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="HTTP user-agent header.")
    p.add_argument(
        "--active-status",
        choices=["open", "closed", "all"],
        default="open",
        help="Default active set to publish (default: open).",
    )
    p.add_argument(
        "--allow-count-mismatch",
        action="store_true",
        help="Allow parsed problem count mismatch vs solve_count banner.",
    )
    p.add_argument(
        "--out-all",
        default="packs/erdos-open-problems/data/erdos_problems.all.json",
        help="Output file for all problems dataset.",
    )
    p.add_argument(
        "--out-open",
        default="packs/erdos-open-problems/data/erdos_problems.open.json",
        help="Output file for open problems dataset.",
    )
    p.add_argument(
        "--out-closed",
        default="packs/erdos-open-problems/data/erdos_problems.closed.json",
        help="Output file for closed problems dataset.",
    )
    p.add_argument(
        "--out-active",
        default="packs/erdos-open-problems/data/erdos_problems.active.json",
        help="Output file for active-status dataset.",
    )
    p.add_argument(
        "--out-open-list",
        default="packs/erdos-open-problems/data/erdos_open_problems.md",
        help=(
            "Markdown output listing every open problem with direct links "
            "(default: packs/erdos-open-problems/data/erdos_open_problems.md)."
        ),
    )
    p.add_argument(
        "--open-list-max-statement-chars",
        type=int,
        default=140,
        help="Statement preview character cap for --out-open-list (default: 140).",
    )
    p.add_argument(
        "--problem-id",
        action="append",
        type=int,
        default=[],
        help="Problem id to print direct link/status metadata for (repeatable).",
    )
    p.add_argument(
        "--out-problem-dir",
        default="",
        help="Optional output directory for --problem-id JSON payloads (files: erdos_problem.<id>.json).",
    )
    return p


def main() -> int:
    args = _build_parser().parse_args()
    synced_at_utc = _now_utc()

    if args.input_html.strip():
        input_path = Path(args.input_html).resolve()
        if not input_path.exists():
            print(f"error: input HTML file not found: {input_path}", file=sys.stderr)
            return 2
        page_html = input_path.read_text(encoding="utf-8")
        source_url = f"file://{input_path}"
    else:
        source_url = args.source_url
        page_html = _fetch_html(source_url, args.timeout_sec, args.user_agent)
        if args.write_html_snapshot.strip():
            snap_path = Path(args.write_html_snapshot).resolve()
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            snap_path.write_text(page_html, encoding="utf-8")

    source_hash = _sha256_text(page_html)
    solve_count = _extract_solve_count(page_html)
    all_problems = _parse_problems(page_html)
    open_problems = [p for p in all_problems if p.get("status_bucket") == "open"]
    closed_problems = [p for p in all_problems if p.get("status_bucket") == "closed"]

    if args.active_status == "open":
        active_problems = open_problems
    elif args.active_status == "closed":
        active_problems = closed_problems
    else:
        active_problems = all_problems

    reported_total = solve_count.get("shown")
    reported_solved = solve_count.get("solved")
    parsed_total = len(all_problems)
    mismatch = isinstance(reported_total, int) and reported_total != parsed_total

    if mismatch and not args.allow_count_mismatch:
        print("error: parsed problem count does not match solve_count banner.", file=sys.stderr)
        print(f"reported_total={reported_total}", file=sys.stderr)
        print(f"parsed_total={parsed_total}", file=sys.stderr)
        print("hint: rerun with --allow-count-mismatch if site markup changed.", file=sys.stderr)
        return 3

    out_all = Path(args.out_all).resolve()
    out_open = Path(args.out_open).resolve()
    out_closed = Path(args.out_closed).resolve()
    out_active = Path(args.out_active).resolve()

    payload_all = _build_payload(
        subset="all",
        active_status=args.active_status,
        source_url=source_url,
        source_hash=source_hash,
        solve_count=solve_count,
        synced_at_utc=synced_at_utc,
        problems=all_problems,
    )
    payload_open = _build_payload(
        subset="open",
        active_status=args.active_status,
        source_url=source_url,
        source_hash=source_hash,
        solve_count=solve_count,
        synced_at_utc=synced_at_utc,
        problems=open_problems,
    )
    payload_closed = _build_payload(
        subset="closed",
        active_status=args.active_status,
        source_url=source_url,
        source_hash=source_hash,
        solve_count=solve_count,
        synced_at_utc=synced_at_utc,
        problems=closed_problems,
    )
    payload_active = _build_payload(
        subset="active",
        active_status=args.active_status,
        source_url=source_url,
        source_hash=source_hash,
        solve_count=solve_count,
        synced_at_utc=synced_at_utc,
        problems=active_problems,
    )

    _write_json(out_all, payload_all)
    _write_json(out_open, payload_open)
    _write_json(out_closed, payload_closed)
    _write_json(out_active, payload_active)

    out_open_list = None
    if args.out_open_list.strip():
        out_open_list = Path(args.out_open_list).resolve()
        _write_open_list_markdown(
            path=out_open_list,
            open_problems=open_problems,
            source_url=source_url,
            synced_at_utc=synced_at_utc,
            max_statement_chars=max(20, int(args.open_list_max_statement_chars)),
        )

    selected_problem_ids = sorted(set(int(x) for x in (args.problem_id or [])))
    selected_missing: list[int] = []
    if selected_problem_ids:
        by_id = {int(p["problem_id"]): p for p in all_problems}
        out_problem_dir: Path | None = None
        if args.out_problem_dir.strip():
            out_problem_dir = Path(args.out_problem_dir).resolve()
            out_problem_dir.mkdir(parents=True, exist_ok=True)

        for pid in selected_problem_ids:
            rec = by_id.get(pid)
            if rec is None:
                selected_missing.append(pid)
                continue
            link = _problem_public_url(pid)
            print(f"selected.problem_id={pid}")
            print(f"selected.url={link}")
            print(f"selected.status_bucket={rec.get('status_bucket', '')}")
            print(f"selected.status_label={rec.get('status_label', '')}")
            print(f"selected.prize_amount={rec.get('prize_amount', '')}")
            print(f"selected.last_edited={rec.get('last_edited', '')}")
            print(
                "selected.statement_preview="
                + _statement_preview(str(rec.get("statement", "")), 200)
            )
            if out_problem_dir is not None:
                out_path = out_problem_dir / f"erdos_problem.{pid}.json"
                _write_selected_problem_payload(
                    out_path=out_path,
                    synced_at_utc=synced_at_utc,
                    source_url=source_url,
                    source_hash=source_hash,
                    solve_count=solve_count,
                    problem=rec,
                )
                print(f"selected.out={out_path}")

    summary_all = payload_all["summary"]
    summary_active = payload_active["summary"]

    print(f"source_url={source_url}")
    print(f"source_sha256={source_hash}")
    print(f"reported_total={reported_total}")
    print(f"reported_solved={reported_solved}")
    print(f"parsed_total={summary_all['total']}")
    print(f"summary.open={summary_all['open']}")
    print(f"summary.closed={summary_all['closed']}")
    print(f"summary.unknown={summary_all['unknown']}")
    print(f"active_status={args.active_status}")
    print(f"summary.active={summary_active['total']}")
    print(f"out_all={out_all}")
    print(f"out_open={out_open}")
    print(f"out_closed={out_closed}")
    print(f"out_active={out_active}")
    if out_open_list is not None:
        print(f"out_open_list={out_open_list}")
    if selected_problem_ids:
        print(f"selected.count={len(selected_problem_ids)}")
    if selected_missing:
        missing_csv = ",".join(str(x) for x in selected_missing)
        print(f"selected.missing={missing_csv}")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
