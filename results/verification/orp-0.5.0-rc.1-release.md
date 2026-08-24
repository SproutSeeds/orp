# Verification Record

## Verified Claim ID

`CLAIM-20260823-ORP-050-RC1`

## Verifier

Codex

## Date

2026-08-23

## Environment

- macOS 26.3 build 25D125
- Node.js 24.10.0, npm 11.6.0, Python 3.14.6
- ORP base commit: `6222b37fdf78c1d43098d172cac9e988fabd18ef`
- Web base commit: `2d56731b48f9bbaf9ada5ba20462dba3d320def0`
- Disposable PostgreSQL at `127.0.0.1:55437`

## Inputs (canonical paths)

- `package.json`
- `package-lock.json`
- `cli/orp.py`
- `packages/orp-workspace-launcher/`
- `spec/v1/`
- `.github/workflows/npm-publish.yml`
- `scripts/npm-release-tag.js`
- `/tmp/orp-rc1-release.28CQHK/open-research-protocol-0.5.0-rc.1.tgz`
- orp-web-app source and migration `0046_orp_v2_local_first.sql`

## Commands Run (copy/paste)

- `python3 -m unittest discover -s tests -v`
- `node --test packages/orp-workspace-launcher/test/*.test.js`
- `npm pack --pack-destination /tmp/orp-rc1-release.28CQHK --ignore-scripts --json`
- `npm install --prefix /tmp/orp-rc1-release.28CQHK/prefix /tmp/orp-rc1-release.28CQHK/open-research-protocol-0.5.0-rc.1.tgz`
- Fresh-XDG `orp about --json`, `orp config validate --json`,
  `orp storage report --json`, `orp workspace list --json`, `orp init --json`,
  workspace create/add/list/tabs, `orp checkpoint inspect --json`, and
  `orp codex context --allow-once ... --json`
- `node scripts/npm-release-tag.js 0.5.0-rc.1`
- `node scripts/npm-release-tag.js 0.5.0`
- orp-web-app `./node_modules/.bin/vitest run`
- orp-web-app `ORP_TEST_DATABASE_URL=postgresql://codymitchell@127.0.0.1:55437/postgres ./node_modules/.bin/vitest run tests/integration/orp-v2-db.test.ts`
- orp-web-app `./node_modules/.bin/tsc --noEmit`
- orp-web-app production `./node_modules/.bin/next build` with disposable local
  database and test-only authentication configuration
- `git diff --check` and `orp hygiene --json` in both worktrees

## Outputs

- ORP Python: 256/256 PASS in 111.551 seconds.
- Workspace launcher: 79/79 PASS.
- Web: 58 files PASS plus one skipped integration file; 186 tests PASS and four
  intentionally skipped without the database environment.
- Web database integration: 4/4 PASS against disposable PostgreSQL.
- TypeScript: PASS with zero diagnostics.
- Next.js production build: PASS; 80 static pages generated and `/device`,
  `/healthz`, `/readyz`, device APIs, and workspace-v2 APIs compiled.
- Candidate: 973,594 packed bytes, 6,126,101 unpacked bytes, 212 files.
- npm SHA-1: `c97842c5f6dd1efbdfb5bbcf1cdf9212b6032cc5`.
- SHA-256:
  `06fd3980f77af3dd9d4b3b84fe8d42e5854f11ceac3e4cc923125b7308b6bbd7`.
- Package scan: zero `.pyc`, `__pycache__`, `.DS_Store`, tarball, private-key,
  or token-shaped credential files/values.
- Fresh install: two packages installed; `orp about --json` reported
  `0.5.0-rc.1` and 182 command records.
- Fresh config: valid absent config with effective layout `xdg-v1`.
- Fresh storage: zero bytes before first write, with
  `codex_storage_scanned: false` and `repository_storage_scanned: false`.
- Fresh workspace listing: local-only with `hostedRequested: false` and no
  hosted error. Explicit `--hosted` without credentials returned a contained
  login-required error while retaining local inventory.
- Local workspace directory mode: 700. Registry, slot, and workspace files:
  600.
- Fresh Codex packet: exact prompt retained, 564 bytes, all read-only/offline
  boundaries true, and no absolute paths or resume IDs emitted.
- npm tag selection: prerelease -> `next`; stable -> `latest`.
- Keychain recovery: a disposable 166-byte UTF-8 value round-tripped exactly
  through the native Security.framework path and was deleted. The affected
  pre-existing item was restored from its separately validated companion and
  exact equality was confirmed in memory. No secret value was printed or
  written to disk. Tests stub all real Keychain operations.

## Result

**PASS** for the local release candidate. Registry, staging, and production
evidence will be appended after their respective hooks.

## Notes

No production database, production deployment, paid Neon resource, global
Codex configuration, real local compaction, legacy-token policy, or legal text
was changed during this verification.

Rollback is explicit:

- npm RC: keep `latest` on 0.4.38; if the RC fails, remove or repoint only the
  `next` dist-tag and preserve the immutable published version for diagnosis.
- Staging: stop routing testers to the failed preview and retain its deployment
  ID/log record.
- Production application: restore the recorded prior Vercel deployment while
  leaving additive migration 0046 in place.
- Backfill: use the exact rollback plan and batch ID; only empty rows created by
  that batch may be removed, while legacy ideas remain untouched.

## Default action if FAIL/INCONCLUSIVE

- FAIL -> downgrade this claim, do not tag or publish, and add a failed-path
  record.
- INCONCLUSIVE -> identify the missing hook and keep npm/production unchanged.

## Next Hook

Checkpoint the exact source, push both release branches, publish npm `next`,
and verify an isolated staging deployment.
