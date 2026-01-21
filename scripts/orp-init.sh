#!/usr/bin/env sh
set -eu

# orp-init.sh — copy ORP into a target directory (no git, no dependencies).
#
# Usage:
#   ./scripts/orp-init.sh /path/to/your/repo/orp
#
# This script copies:
#   README.md, INSTALL.md, PROTOCOL.md, templates/, examples/
#
# It does NOT:
#   - initialize git
#   - modify your repo README
#   - enforce the protocol

SCRIPT_PATH="$0"
case "$SCRIPT_PATH" in
  */*) : ;;
  *) SCRIPT_PATH="$(command -v "$SCRIPT_PATH" 2>/dev/null || printf '%s' "$SCRIPT_PATH")" ;;
esac

ROOT_DIR="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
cd "$ROOT_DIR"

if [ "${1:-}" = "" ]; then
  echo "usage: $0 /path/to/target/orp"
  exit 2
fi

TARGET="$1"

if [ -e "$TARGET/PROTOCOL.md" ]; then
  echo "Warning: ORP files already exist at $TARGET. Aborting."
  exit 3
fi

mkdir -p "$TARGET"
mkdir -p "$TARGET/templates" "$TARGET/examples"

cp -f "./README.md" "./INSTALL.md" "./PROTOCOL.md" "$TARGET/"
cp -f "./templates/"*.md "$TARGET/templates/"
cp -f "./examples/"*.md "$TARGET/examples/"

echo "ORP copied to: $TARGET"
echo "IMPORTANT: Edit $TARGET/PROTOCOL.md and define Canonical Paths."
