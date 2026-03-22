#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_HOSTED=0
RUN_WORKER=0
RUN_TESTS=1
KEEP_TEMP=0
CODEX_SESSION_ID="${CODEX_THREAD_ID:-}"
IDEA_ID=""
TMP_ROOT=""
ORP_BIN=""

usage() {
  cat <<'EOF'
Usage: scripts/orp-release-smoke.sh [options]

Local release smoke:
  - runs unit tests
  - verifies npm pack / publish dry runs
  - installs the packed tarball into a clean temp prefix
  - exercises init/status/branch/checkpoint/gate/ready on a fresh repo

Optional hosted smoke:
  --hosted            run hosted whoami/ideas/add/show/world/checkpoint smoke
  --worker            after --hosted, run `orp agent work --once`
  --codex-session-id  Codex session id used for hosted world binding

Other options:
  --skip-tests        skip the unit test pass
  --keep-temp         keep temp install/repo directories for inspection
  -h, --help          show this help
EOF
}

note() {
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

json_field() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

path = sys.argv[1]
field = sys.argv[2]
value = json.loads(open(path, encoding="utf-8").read())
for part in field.split("."):
    if isinstance(value, dict):
        value = value.get(part)
    elif isinstance(value, list) and part.isdigit():
        idx = int(part)
        value = value[idx] if 0 <= idx < len(value) else None
    else:
        value = None
        break
if value is None:
    print("")
elif isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
PY
}

cleanup() {
  local exit_code=$?
  if [[ -n "${IDEA_ID}" && -n "${ORP_BIN}" ]]; then
    note "Cleaning up hosted smoke idea ${IDEA_ID}"
    "${ORP_BIN}" idea remove "${IDEA_ID}" --purge --json >/dev/null 2>&1 || true
  fi
  if [[ "${KEEP_TEMP}" != "1" && -n "${TMP_ROOT}" && -d "${TMP_ROOT}" ]]; then
    rm -rf "${TMP_ROOT}" >/dev/null 2>&1 || true
  fi
  exit "${exit_code}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hosted)
      RUN_HOSTED=1
      shift
      ;;
    --worker)
      RUN_HOSTED=1
      RUN_WORKER=1
      shift
      ;;
    --skip-tests)
      RUN_TESTS=0
      shift
      ;;
    --keep-temp)
      KEEP_TEMP=1
      shift
      ;;
    --codex-session-id)
      CODEX_SESSION_ID="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

trap cleanup EXIT

command -v python3 >/dev/null
command -v npm >/dev/null
command -v node >/dev/null
command -v git >/dev/null

TMP_ROOT="$(mktemp -d /tmp/orp-release-smoke.XXXXXX)"
PACK_DIR="${TMP_ROOT}/pack"
PREFIX_DIR="${TMP_ROOT}/prefix"
REPO_DIR="${TMP_ROOT}/repo"
mkdir -p "${PACK_DIR}" "${PREFIX_DIR}" "${REPO_DIR}"

if [[ "${RUN_TESTS}" == "1" ]]; then
  note "Running unit tests"
  (
    cd "${ROOT_DIR}"
    env PYTHONPYCACHEPREFIX=/tmp/orp-pyc python3 -m unittest discover -s tests -v
  )
fi

note "Checking published npm version"
(
  cd "${ROOT_DIR}"
  npm view open-research-protocol version dist-tags --json
)

note "Verifying npm pack and publish dry runs"
(
  cd "${ROOT_DIR}"
  npm pack --dry-run --cache /tmp/orp-npm-cache
  npm publish --dry-run
)

note "Packing local release candidate"
(
  cd "${PACK_DIR}"
  npm pack "${ROOT_DIR}" --json > pack.json
)
TARBALL="${PACK_DIR}/$(json_field "${PACK_DIR}/pack.json" "0.filename")"

note "Installing tarball into temp prefix"
npm install -g --prefix "${PREFIX_DIR}" "${TARBALL}" >/dev/null
ORP_BIN="${PREFIX_DIR}/bin/orp"

note "Checking installed binary"
"${ORP_BIN}" -h >/dev/null

note "Running fresh-repo governance smoke"
(
  cd "${REPO_DIR}"
  "${ORP_BIN}" init --json >/dev/null
  git config user.name "ORP Release Smoke"
  git config user.email "orp-release@example.com"
  "${ORP_BIN}" status --json >/dev/null
  "${ORP_BIN}" branch start work/bootstrap --allow-dirty --json >/dev/null
  "${ORP_BIN}" checkpoint create -m "bootstrap governance" --json >/dev/null
  "${ORP_BIN}" backup -m "backup bootstrap governance" --json >/dev/null
  "${ORP_BIN}" gate run --profile default --json >/dev/null
  "${ORP_BIN}" checkpoint create -m "capture passing validation" --json >/dev/null
  "${ORP_BIN}" ready --json >/dev/null
  "${ORP_BIN}" packet emit --profile default --json >/dev/null
  "${ORP_BIN}" report summary --json >/dev/null
)

if [[ "${RUN_HOSTED}" == "1" ]]; then
  note "Running hosted workspace smoke"
  "${ORP_BIN}" whoami --json >/dev/null
  "${ORP_BIN}" ideas list --limit 5 --json >/dev/null

  local_idea_json="${TMP_ROOT}/idea-add.json"
  "${ORP_BIN}" idea add \
    --title "ORP release smoke $(date '+%Y-%m-%d %H:%M:%S')" \
    --notes "Temporary hosted smoke test for ORP CLI release readiness. Safe to purge." \
    --json > "${local_idea_json}"
  IDEA_ID="$(json_field "${local_idea_json}" "idea.id")"
  if [[ -z "${IDEA_ID}" ]]; then
    printf 'Hosted smoke failed: could not create idea.\n' >&2
    exit 1
  fi

  "${ORP_BIN}" idea show "${IDEA_ID}" --json >/dev/null

  if [[ -z "${CODEX_SESSION_ID}" ]]; then
    printf 'Hosted smoke requires --codex-session-id or CODEX_THREAD_ID for world binding.\n' >&2
    exit 1
  fi

  "${ORP_BIN}" world bind "${IDEA_ID}" \
    --name "ORP release smoke" \
    --project-root "${ROOT_DIR}" \
    --github-url "https://github.com/SproutSeeds/orp" \
    --codex-session-id "${CODEX_SESSION_ID}" \
    --json >/dev/null

  world_ok=0
  for _ in 1 2 3 4 5; do
    local_world_json="${TMP_ROOT}/world-show.json"
    "${ORP_BIN}" world show "${IDEA_ID}" --json > "${local_world_json}"
    if [[ "$(json_field "${local_world_json}" "world.id")" != "" ]]; then
      world_ok=1
      break
    fi
    sleep 1
  done
  if [[ "${world_ok}" != "1" ]]; then
    printf 'Hosted smoke failed: world show did not return a bound world.\n' >&2
    exit 1
  fi

  "${ORP_BIN}" checkpoint queue --idea-id "${IDEA_ID}" --json >/dev/null

  if [[ "${RUN_WORKER}" == "1" ]]; then
    note "Running hosted worker smoke"
    "${ORP_BIN}" agent work --once --json >/dev/null
  fi
fi

note "Release smoke passed"
if [[ "${KEEP_TEMP}" == "1" ]]; then
  note "Temp files kept at ${TMP_ROOT}"
fi
