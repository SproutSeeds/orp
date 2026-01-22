#!/usr/bin/env sh
set -eu

# orp-agent-integrate.sh — append the ORP agent instructions snippet into a target Markdown file.
#
# Usage:
#   ./scripts/orp-agent-integrate.sh /path/to/your/agent/instructions.md

if [ "${1:-}" = "" ]; then
  echo "usage: $0 /path/to/agent/instructions.md"
  exit 2
fi

TARGET="$1"
MARKER_BEGIN="<!-- ORP:BEGIN -->"
MARKER_END="<!-- ORP:END -->"

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

if ! grep -q "$MARKER_BEGIN" "$SNIPPET_FILE" || ! grep -q "$MARKER_END" "$SNIPPET_FILE"; then
  echo "error: ORP snippet markers not found in $SNIPPET_FILE"
  exit 4
fi

if [ -f "$TARGET" ] && grep -q "$MARKER_BEGIN" "$TARGET"; then
  echo "ORP snippet already present in: $TARGET"
  exit 0
fi

mkdir -p "$(dirname "$TARGET")"

if [ -f "$TARGET" ] && [ -s "$TARGET" ]; then
  printf '\n' >> "$TARGET"
fi

awk '
  $0=="<!-- ORP:BEGIN -->" {p=1}
  p {print}
  $0=="<!-- ORP:END -->" {exit}
' "$SNIPPET_FILE" >> "$TARGET"

echo "ORP snippet appended to: $TARGET"
echo "Next: ensure your agent uses that file as its primary instructions."

