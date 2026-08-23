# Verification Record

## Verified Claim ID

`CLAIM-20260823-ORP-0438-PUBLISH-RECOVERY`

## Verifier

Codex

## Date

2026-08-23

## Environment

- OS: macOS 26.3 build 25D125
- Node.js 24.10.0, npm 11.6.0, Python 3.14.6
- Base commit: `2c205758ee16bcd2ecdf0aea353a21bd8db781ce`
- Failure reproduction: Python bytecode written inside `cli/` and `scripts/`

## Inputs (canonical paths)

- `package.json`
- `.npmignore`
- `.github/workflows/npm-publish.yml`
- `tests/test_npm_publish_guard.py`
- `CHANGELOG.md`
- `/tmp/orp-v0438-final.wAA8ac/open-research-protocol-0.4.38.tgz`

## Commands Run (copy/paste)

- `env -u PYTHONPYCACHEPREFIX npm test`
- `python3 -m unittest tests.test_npm_publish_guard -v`
- `npm pack --dry-run --json --ignore-scripts`
- `npm pack --pack-destination /tmp/orp-v0438-final.wAA8ac --cache /tmp/orp-npm-cache-v0438`
- `python3 -c 'import pathlib,yaml; yaml.safe_load(pathlib.Path(".github/workflows/npm-publish.yml").read_text())'`
- `git diff --check`
- Keychain-backed authenticated request to npm `/-/whoami` without printing or
  persisting the credential

## Outputs

- Full suite under the CI bytecode condition: `Ran 240 tests in 107.425s`,
  `OK`.
- Focused publication suite: 4 tests, `OK`.
- Simulated dirty package manifest: version `0.4.38`, 204 files, zero blocked
  cache paths, default hygiene policy present.
- Actual tarball: 951.0 kB packed, 6.0 MB unpacked, 204 files.
- Workflow YAML parse: PASS.
- Git diff whitespace check: PASS.
- New Keychain credential authentication: HTTP 200 as npm owner
  `sproutseeds`; the credential value was neither printed nor persisted.
- npm SHA-1: `4e9a536ae1a6266abc8504dcd558a30cd0b052ad`.
- SHA-256:
  `a287c8a8fb60a20f260af2f0d308f86912f8627176d148bbd5c3c4a953b9918c`.

## Result

**PASS**

## Notes

The first npm publication attempt is a separate failed path. This record proves
the corrected source/package candidate and credential identity; public registry
availability requires the actual `v0.4.38` workflow and a fresh registry install.

## Default action if FAIL/INCONCLUSIVE

- FAIL -> downgrade the claim and link the failure evidence.
- INCONCLUSIVE -> mark the missing release proof and do not publish.

## Next Hook

Commit, push, pass pull-request checks, merge, rotate `NPM_TOKEN` through stdin,
tag `v0.4.38`, and verify the published registry artifact from a fresh prefix.
