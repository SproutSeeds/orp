#!/usr/bin/env sh
set -eu

# orp-agent-integrate.sh — install/check/sync the ORP agent instructions snippet in a target Markdown file.
#
# Usage:
#   ./scripts/orp-agent-integrate.sh [--check|--sync] /path/to/your/agent/instructions.md

usage() {
  cat <<EOF
usage:
  $0 /path/to/agent/instructions.md
  $0 --check /path/to/agent/instructions.md
  $0 --sync  /path/to/agent/instructions.md

default behavior:
  Append the ORP snippet if missing (never overwrites).

--check:
  Exit 0 if the ORP snippet exists and matches the canonical snippet in AGENT_INTEGRATION.md.
  Exit 1 if missing or out of date.

--sync:
  Ensure the target contains the canonical ORP snippet (append if missing; replace if present but out of date).
EOF
}

MODE="append"
while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE="check"; shift ;;
    --sync) MODE="sync"; shift ;;
    --help|-h) usage; exit 0 ;;
    --) shift; break ;;
    -*) usage; exit 2 ;;
    *) break ;;
  esac
done

if [ "${1:-}" = "" ]; then
  usage
  exit 2
fi

TARGET="$1"
MARKER_BEGIN="<!-- ORP:BEGIN -->"
MARKER_END="<!-- ORP:END -->"

SNIPPET_TMP=""
TARGET_SNIPPET_TMP=""
OUT_TMP=""
cleanup() {
  if [ -n "${SNIPPET_TMP:-}" ] && [ -f "$SNIPPET_TMP" ]; then
    rm -f "$SNIPPET_TMP"
  fi
  if [ -n "${TARGET_SNIPPET_TMP:-}" ] && [ -f "$TARGET_SNIPPET_TMP" ]; then
    rm -f "$TARGET_SNIPPET_TMP"
  fi
  if [ -n "${OUT_TMP:-}" ] && [ -f "$OUT_TMP" ]; then
    rm -f "$OUT_TMP"
  fi
  :
}
trap cleanup EXIT

SCRIPT_PATH="$0"
case "$SCRIPT_PATH" in
  */*) : ;;
  *) SCRIPT_PATH="$(command -v "$SCRIPT_PATH" 2>/dev/null || printf '%s' "$SCRIPT_PATH")" ;;
esac

ROOT_DIR="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
SNIPPET_FILE="$ROOT_DIR/AGENT_INTEGRATION.md"

if [ ! -f "$SNIPPET_FILE" ]; then
  echo "error: missing $SNIPPET_FILE"
  exit 4
fi

SNIPPET_TMP="$(mktemp)"
awk '
  $0=="<!-- ORP:BEGIN -->" {p=1}
  p {print}
  $0=="<!-- ORP:END -->" {exit}
' "$SNIPPET_FILE" > "$SNIPPET_TMP"

if ! grep -q "$MARKER_BEGIN" "$SNIPPET_TMP" || ! grep -q "$MARKER_END" "$SNIPPET_TMP"; then
  echo "error: ORP snippet markers not found in $SNIPPET_FILE"
  exit 4
fi

cksum2() {
  cksum "$1" | awk '{print $1 " " $2}'
}

canonical_sig="$(cksum2 "$SNIPPET_TMP")"

has_begin="0"
has_end="0"
if [ -f "$TARGET" ]; then
  if grep -q "$MARKER_BEGIN" "$TARGET"; then has_begin="1"; fi
  if grep -q "$MARKER_END" "$TARGET"; then has_end="1"; fi
fi

if [ "$has_begin" = "1" ] && [ "$has_end" = "0" ]; then
  echo "error: $TARGET contains $MARKER_BEGIN but not $MARKER_END"
  exit 4
fi
if [ "$has_begin" = "0" ] && [ "$has_end" = "1" ]; then
  echo "error: $TARGET contains $MARKER_END but not $MARKER_BEGIN"
  exit 4
fi

target_sig=""
if [ "$has_begin" = "1" ]; then
  TARGET_SNIPPET_TMP="$(mktemp)"
  awk '
    $0=="<!-- ORP:BEGIN -->" {p=1}
    p {print}
    $0=="<!-- ORP:END -->" {exit}
  ' "$TARGET" > "$TARGET_SNIPPET_TMP"
  target_sig="$(cksum2 "$TARGET_SNIPPET_TMP")"
fi

if [ "$MODE" = "check" ]; then
  if [ "$has_begin" = "0" ]; then
    echo "ORP snippet missing in: $TARGET"
    echo "Fix: $0 --sync $TARGET"
    exit 1
  fi
  if [ "$target_sig" = "$canonical_sig" ]; then
    echo "OK: ORP snippet is up to date in: $TARGET"
    exit 0
  fi
  echo "OUT OF DATE: ORP snippet differs from $SNIPPET_FILE"
  echo "Fix: $0 --sync $TARGET"
  exit 1
fi

if [ "$MODE" = "append" ] && [ "$has_begin" = "1" ]; then
  echo "ORP snippet already present in: $TARGET (not modifying)"
  echo "Tip: $0 --check $TARGET  (detect drift)"
  echo "Tip: $0 --sync  $TARGET  (update in place)"
  exit 0
fi

mkdir -p "$(dirname "$TARGET")"

if [ "$MODE" = "append" ]; then
  if [ -f "$TARGET" ] && [ -s "$TARGET" ]; then
    printf '\n' >> "$TARGET"
  fi
  cat "$SNIPPET_TMP" >> "$TARGET"
  echo "ORP snippet appended to: $TARGET"
  echo "Next: ensure your agent uses that file as its primary instructions."
  exit 0
fi

if [ "$MODE" = "sync" ]; then
  if [ "$has_begin" = "0" ]; then
    if [ -f "$TARGET" ] && [ -s "$TARGET" ]; then
      printf '\n' >> "$TARGET"
    fi
    cat "$SNIPPET_TMP" >> "$TARGET"
    echo "ORP snippet appended to: $TARGET"
    echo "Next: ensure your agent uses that file as its primary instructions."
    exit 0
  fi

  OUT_TMP="$(mktemp)"
  awk -v begin="$MARKER_BEGIN" -v end="$MARKER_END" -v snippet="$SNIPPET_TMP" '
    BEGIN {in_old=0}
    {
      if ($0==begin) {
        in_old=1
        while ((getline line < snippet) > 0) print line
        close(snippet)
        next
      }
      if (in_old) {
        if ($0==end) in_old=0
        next
      }
      print
    }
  ' "$TARGET" > "$OUT_TMP"

  mv "$OUT_TMP" "$TARGET"
  OUT_TMP=""

  echo "ORP snippet synced in: $TARGET"
  echo "Next: ensure your agent uses that file as its primary instructions."
  exit 0
fi

echo "error: unknown mode"
exit 4
