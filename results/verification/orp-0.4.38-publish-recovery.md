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
- Pull request 7 checks: GitGuardian PASS and Kernel Evidence PASS.
- Merged release commit:
  `fce795d3930cc3a96398db545dbd2e75e04cebbd`.
- GitHub Actions publication run `32670049296`: PASS, including 240 tests,
  package-manifest audit, and npm publish.
- npm registry: `latest` is `0.4.38`, 204 files, npm SHA-1
  `7ebe47ff7fb4cb3d3443551a805b7276b74b1fbc`, registry tarball SHA-256
  `c76f665c81e5106e7a7f6ad54453b8734bf6beff4a1dfc850af9b28e78f655e1`.
- Extracted registry and local package directories compare byte-for-byte with
  no differences. The compressed tarball hashes differ because the local and
  CI npm toolchains emitted different gzip bytes around identical contents.
- Fresh registry prefix install: version `0.4.38`, two packages installed, no
  `.pyc` or `.DS_Store` files present.
- Fresh repository initialization: `ok: true`; configuration, agent guides,
  hygiene policy, project context, and governance files created.
- Fresh repository hygiene: five generated bootstrap paths classified, zero
  unclassified paths, `safe_to_expand: true`.
- Installed large-output check: 123,831 stdout bytes, valid JSON, 98 tabs, zero
  stderr bytes.
- Installed hosted check: stable `orp.hosted_error/1` response with status 500,
  retryable true, and path `/api/cli/me`.
- GitHub release: `https://github.com/SproutSeeds/orp/releases/tag/v0.4.38`.

## Result

**PASS**

## Notes

The first npm publication attempt remains a separate failed path. The corrected
release is publicly available and its fresh registry install is verified.

## Default action if FAIL/INCONCLUSIVE

- FAIL -> downgrade the claim and link the failure evidence.
- INCONCLUSIVE -> mark the missing release proof and do not publish.

## Next Hook

Start ORP 0.5 from merged commit
`fce795d3930cc3a96398db545dbd2e75e04cebbd`, retaining 0.4.38 as the rollback
and compatibility baseline.
