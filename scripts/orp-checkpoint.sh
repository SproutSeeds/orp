#!/usr/bin/env sh
set -eu

# orp-checkpoint.sh — lightweight ORP checkpoint for agentic workflows (process-only).
#
# Typical usage (agent knows its instruction file path):
#   ./scripts/orp-checkpoint.sh --agent-file /path/to/agent/instructions.md "pre-push checkpoint"
#
# Modes:
#   --status  : print last checkpoint + current git status summary (no write)
#   --check   : run checks only (no write)
#   --sync    : sync ORP snippet into agent files before checking (requires --agent-file)
#
# Exit codes:
#   0 = OK
#   1 = ORP snippet missing/out of date in one or more agent files (or check failed)
#   2 = usage error
#   4 = internal/config error

usage() {
  cat <<EOF
usage:
  $0 [--status|--check] [--sync] [--agent-file PATH ...] [--log-file PATH] [NOTE]

examples:
  $0 --status
  $0 --agent-file CLAUDE.md "compaction checkpoint"
  $0 --sync --agent-file CLAUDE.md --agent-file AGENTS.md "pre-push checkpoint"
  $0 --check --agent-file CLAUDE.md
EOF
}

MODE="write"
DO_SYNC="0"
LOG_FILE=""
NOTE=""
AGENT_FILES=""

while [ $# -gt 0 ]; do
  case "$1" in
    --status) MODE="status"; shift ;;
    --check) MODE="check"; shift ;;
    --sync) DO_SYNC="1"; shift ;;
    --agent-file)
      shift
      if [ "${1:-}" = "" ]; then usage; exit 2; fi
      AGENT_FILES="${AGENT_FILES}${AGENT_FILES:+
}$1"
      shift
      ;;
    --log-file)
      shift
      if [ "${1:-}" = "" ]; then usage; exit 2; fi
      LOG_FILE="$1"
      shift
      ;;
    --help|-h) usage; exit 0 ;;
    --) shift; break ;;
    -*) usage; exit 2 ;;
    *) NOTE="${NOTE}${NOTE:+ }$1"; shift ;;
  esac
done

SCRIPT_PATH="$0"
case "$SCRIPT_PATH" in
  */*) : ;;
  *) SCRIPT_PATH="$(command -v "$SCRIPT_PATH" 2>/dev/null || printf '%s' "$SCRIPT_PATH")" ;;
esac

ORP_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
cd "$ORP_ROOT"

if [ "$LOG_FILE" = "" ]; then
  LOG_FILE="$ORP_ROOT/cone/CONTEXT_LOG.md"
fi

timestamp_utc="$(date -u "+%Y-%m-%dT%H:%M:%SZ")"

git_inside="0"
git_root=""
git_branch=""
git_head=""
staged_count="0"
unstaged_count="0"
untracked_count="0"

if git_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  git_inside="1"
  git_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  git_head="$(git rev-parse --short HEAD 2>/dev/null || true)"
  status="$(git status --porcelain=v1 2>/dev/null || true)"
  if [ "$status" != "" ]; then
    staged_count="$(printf '%s\n' "$status" | awk 'substr($0,1,2)!="??" && substr($0,1,1)!=" " {c++} END{print c+0}')"
    unstaged_count="$(printf '%s\n' "$status" | awk 'substr($0,1,2)!="??" && substr($0,2,1)!=" " {c++} END{print c+0}')"
    untracked_count="$(printf '%s\n' "$status" | awk 'substr($0,1,2)=="??" {c++} END{print c+0}')"
  fi
fi

last_checkpoint="(none)"
if [ -f "$LOG_FILE" ]; then
  last_line="$(awk '/^## Checkpoint — /{x=$0} END{print x}' "$LOG_FILE")"
  if [ "${last_line:-}" != "" ]; then
    last_checkpoint="${last_line#\#\# Checkpoint — }"
  fi
fi

echo "ORP root: $ORP_ROOT"
echo "Checkpoint log: $LOG_FILE"
echo "Last checkpoint: $last_checkpoint"
if [ "$git_inside" = "1" ]; then
  echo "Git: branch=$git_branch head=$git_head staged=$staged_count unstaged=$unstaged_count untracked=$untracked_count"
else
  echo "Git: (not a git repo)"
fi

orp_check_status="skipped"
orp_check_exit="0"
agent_checked=""

if [ "$AGENT_FILES" != "" ]; then
  orp_check_status="PASS"
  agent_checked="$(printf '%s' "$AGENT_FILES" | tr '\n' ' ')"
  while IFS= read -r f; do
    [ "$f" = "" ] && continue
    if [ "$DO_SYNC" = "1" ]; then
      "$ORP_ROOT/scripts/orp-agent-integrate.sh" --sync "$f" >/dev/null
    fi
    if "$ORP_ROOT/scripts/orp-agent-integrate.sh" --check "$f" >/dev/null; then
      :
    else
      orp_check_status="FAIL"
      orp_check_exit="1"
    fi
  done <<EOF
$AGENT_FILES
EOF
fi

echo "ORP snippet sync: $orp_check_status"

if [ "$MODE" = "status" ]; then
  exit 0
fi

if [ "$MODE" = "check" ]; then
  exit "$orp_check_exit"
fi

mkdir -p "$(dirname "$LOG_FILE")"
if [ ! -f "$LOG_FILE" ]; then
  cat >"$LOG_FILE" <<'EOF'
# Context Log (process-only; not evidence)

> This file is **not evidence**. It is a running, lightweight trace of “what’s going on” to support handoff, compaction, and
> coordination.
EOF
  printf '\n' >> "$LOG_FILE"
fi

{
  echo
  echo "## Checkpoint — $timestamp_utc"
  echo "- Note: ${NOTE:-}"
  echo "- Repo state:"
  if [ "$git_inside" = "1" ]; then
    echo "  - Branch: $git_branch"
    echo "  - Head: $git_head"
    echo "  - Git status: staged=$staged_count, unstaged=$unstaged_count, untracked=$untracked_count"
  else
    echo "  - Branch:"
    echo "  - Head:"
    echo "  - Git status: staged=?, unstaged=?, untracked=?"
  fi
  echo "- ORP snippet sync:"
  echo "  - Agent instruction files checked: ${agent_checked:-}"
  echo "  - Result: $orp_check_status"
  echo "- Canonical artifacts touched (paths only):"
  echo "- Next hook:"
} >> "$LOG_FILE"

echo "Wrote checkpoint entry."

exit "$orp_check_exit"

