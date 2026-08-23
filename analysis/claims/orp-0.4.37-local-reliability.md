# ORP 0.4.37 local reliability

## Title

ORP 0.4.37 preserves complete agent-facing output and private local state

## Claim ID

`CLAIM-20260823-ORP-0437-LOCAL-RELIABILITY`

## Claim Level

**Verified**

## Statement

For the `0.4.37` release candidate, the npm wrapper drains JSON output larger
than 64 KiB before process exit, ORP user configuration JSON is replaced
atomically with `0700` directory and `0600` file permissions, and hosted
failures requested as JSON use a stable sanitized and retry-aware envelope.
These statements apply to the exact source and package artifacts identified
below and do not assert availability of the hosted `orp.earth` service.

## Scope / Assumptions

- Node.js 18 or newer and Python 3 are available as required by the package.
- Permission assertions use a POSIX filesystem.
- Hosted error tests use deterministic fixtures rather than production calls.
- Production npm availability is a separate post-publication verification.

## Instrument (optional)

- Instrument(s) used: None
- Instrument parameters explored (if any): None

## Canonical Artifacts (source of truth)

- `bin/orp.js`
- `cli/orp.py`
- `orp/hygiene-policy.json`
- `tests/test_npm_bin_wrapper.py`
- `tests/test_orp_file_permissions.py`
- `tests/test_orp_hosted_cli.py`
- `package.json`
- `CHANGELOG.md`
- `results/verification/orp-0.4.37-release.md`

## Verification Hook

- Command(s) to run:
  - `npm test`
  - `git diff --check`
  - `npm pack --dry-run --cache /tmp/orp-npm-cache`
  - `npm publish --dry-run`
  - Fresh-prefix install and CLI smoke commands from `docs/NPM_RELEASE_CHECKLIST.md`
- Expected outputs:
  - Full unit suite reports `OK`.
  - Large-output JSON parses and contains its final workspace tab.
  - Private-state test observes `0700` directories and a `0600` file.
  - Hosted `503` fixture produces schema `orp.hosted_error/1` with `retryable: true`.
  - Package dry runs contain the required CLI, hygiene policy, templates, and documentation.
- Determinism notes:
  - Tests use temporary directories and local fixtures.
  - Network-dependent hosted checks are excluded from the local reliability claim.

## Status

Verified

## Next Hook

The `v0.4.37` tag passed code and package validation but failed before npm
publication. Preserve that failed tag and publish the corrected package as
`open-research-protocol@0.4.38`; see
`analysis/FAILED_npm-publish-v0.4.37-20260823.md`.
