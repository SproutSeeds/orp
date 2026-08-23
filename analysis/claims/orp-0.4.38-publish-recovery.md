# Claim

## Claim ID

`CLAIM-20260823-ORP-0438-PUBLISH-RECOVERY`

## Claim Class

Verified

## Statement

ORP 0.4.38 preserves the verified 0.4.37 local reliability behavior and adds a
deterministic npm package boundary: test-generated Python bytecode and macOS
metadata are excluded even when they exist inside allowlisted package
directories, the default hygiene policy remains included, and the publication
workflow independently audits those conditions before publishing.

## Scope and Assumptions

- Applies to the source candidate in this branch and the tarball identified in
  the verification record below.
- Covers package contents, tests, and workflow validation.
- Registry availability is included after successful workflow publication and
  fresh installation of `open-research-protocol@0.4.38` from npm.

## Canonical Artifacts

- `package.json`
- `.npmignore`
- `.github/workflows/npm-publish.yml`
- `tests/test_npm_publish_guard.py`
- `CHANGELOG.md`
- `results/verification/orp-0.4.38-publish-recovery.md`

## Verification Hook

- Run `env -u PYTHONPYCACHEPREFIX npm test`; expect 240 tests and `OK`.
- Create bytecode in `cli/__pycache__` and `scripts/__pycache__`, then run
  `npm pack --dry-run --json --ignore-scripts`; expect 204 files, no `.pyc` or
  `__pycache__` paths, and `orp/hygiene-policy.json` present.
- Run `npm pack`; expect npm SHA-1
  `4e9a536ae1a6266abc8504dcd558a30cd0b052ad` before evidence-only commits.
- Run `git diff --check` and parse `.github/workflows/npm-publish.yml` with
  PyYAML; expect success.

## Status

Verified

## Next Hook

Use the verified 0.4.38 release as the stable base for ORP 0.5 local storage,
configuration, Codex integration, browser authentication, and hosted workspace
work.
