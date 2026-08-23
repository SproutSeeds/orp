# Verification Record

## Verified Claim ID

`CLAIM-20260823-ORP-0437-LOCAL-RELIABILITY`

## Verifier

Codex

## Date

2026-08-23

## Environment

- OS / hardware: macOS 26.3 build 25D125
- Language/runtime versions: Node.js 24.10.0, npm 11.6.0, Python 3.14.6
- Git: 2.50.1 (Apple Git-155)
- Candidate commit: `ea7f41471cee6527267742ab422828548a5a76ce`
- Package dependency install: 2 packages audited, 0 vulnerabilities

## Inputs (canonical paths)

- `bin/orp.js`
- `cli/orp.py`
- `orp/hygiene-policy.json`
- `tests/test_npm_bin_wrapper.py`
- `tests/test_orp_file_permissions.py`
- `tests/test_orp_hosted_cli.py`
- `package.json`
- `CHANGELOG.md`
- `/tmp/orp-v0437-artifacts.6qofTv/open-research-protocol-0.4.37.tgz`

## Commands Run (copy/paste)

- `npm install --no-package-lock`
- `npm test`
- `python3 -m py_compile cli/orp.py`
- `node --check bin/orp.js`
- `git diff --check`
- `npm pack --dry-run --json --cache /tmp/orp-npm-cache-v0437`
- `npm pack --pack-destination /tmp/orp-v0437-artifacts.6qofTv --cache /tmp/orp-npm-cache-v0437`
- `npm install -g --prefix /tmp/orp-v0437-prefix.MWDIaN /tmp/orp-v0437-artifacts.6qofTv/open-research-protocol-0.4.37.tgz`
- `env XDG_CONFIG_HOME=/tmp/orp-v0437-config.rpAsZi /tmp/orp-v0437-prefix.MWDIaN/bin/orp init --json`
- Installed-package large workspace JSON parse check using `orp workspace tabs main --json`
- `/tmp/orp-v0437-prefix.MWDIaN/bin/orp whoami --json`
- `npm publish --dry-run --access public`
- `orp hygiene --json`

## Outputs

- Logs:
  - Dependency-complete suite: `Ran 239 tests in 106.623s`, `OK`, zero skips.
  - Focused hosted suite: 23 tests, `OK`.
  - Wrapper suite: 6 tests, `OK`.
  - Private permission suite: 1 test, `OK`.
  - Package dry-run: version `0.4.37`, 204 files, hygiene policy included.
  - Fresh-prefix install: package version `0.4.37`; help and `about --json` succeeded.
  - Fresh repository initialization returned `ok: true` and created the hygiene policy.
  - Installed large-output check returned 123,831 bytes, 98 tabs, and `complete: true`.
  - Live hosted failure returned schema `orp.hosted_error/1`, status 500, a sanitized code, and `retryable: true` without a traceback.
  - `npm publish --dry-run --access public` completed and selected tag `latest`.
  - Candidate worktree hygiene was clean before the release branch push.
- Artifacts produced:
  - `/tmp/orp-v0437-artifacts.6qofTv/open-research-protocol-0.4.37.tgz`
- Checksums/hashes:
  - SHA-256: `915b66b298adaec71ad172afb469d52d3e640e8e8f5c794ac6d6425d0879b648`
  - npm SHA-1: `0437356d506cea9627d1eef2be345f86ce19cd67`

## Result

**PASS**

## Notes

The local npm session returned `E401` for `npm whoami`, so the verified manual
dry run does not establish local publish authorization. Normal publication is
the repository's tag-triggered GitHub Actions workflow; its configured npm
credential must be proven by the actual tagged release. Production
`orp.earth` availability is outside this local reliability claim.

## Default action if FAIL/INCONCLUSIVE

- FAIL → downgrade claim label and link this record.
- INCONCLUSIVE → downgrade by default OR explicitly mark “blocked by X” with a follow-up issue.

## Next Hook

Merge this exact candidate, push tag `v0.4.37`, verify the npm workflow, install
`open-research-protocol@0.4.37` from the registry, and repeat the installed
version, large-output, fresh-init, permissions, and hosted-error smoke checks.
