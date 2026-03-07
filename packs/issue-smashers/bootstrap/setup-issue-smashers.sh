#!/usr/bin/env bash
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

mkdir -p \
  "$ROOT/analysis" \
  "$ROOT/repos" \
  "$ROOT/worktrees" \
  "$ROOT/scratch" \
  "$ROOT/archive"

printf 'workspace_root=%s\n' "$ROOT"
printf 'ensured=analysis\n'
printf 'ensured=repos\n'
printf 'ensured=worktrees\n'
printf 'ensured=scratch\n'
printf 'ensured=archive\n'
