# Claim

## Title

ORP 0.5.0-rc.1 local-first release candidate

## Claim ID

`CLAIM-20260823-ORP-050-RC1`

## Claim Level

**Verified**

## Statement

The ORP 0.5.0-rc.1 candidate makes local configuration, ORP-owned storage,
workspace recovery, checkpoints, and generic credentials local-first while
keeping its Codex context adapter opt-in, read-only, offline, prompt-preserving,
and bounded to 2,048 bytes. Its hosted contract accepts only an explicit,
sanitized metadata projection backed by scoped browser device authorization and
dedicated versioned workspace records. This claim covers the exact local npm
candidate and the locally verified web application source; staging and
production are separate verification hooks.

## Scope / Assumptions

- npm candidate:
  `/tmp/orp-rc1-release.28CQHK/open-research-protocol-0.5.0-rc.1.tgz`
- ORP base commit: `6222b37fdf78c1d43098d172cac9e988fabd18ef`
- Web base commit: `2d56731b48f9bbaf9ada5ba20462dba3d320def0`
- The production database, production deployment, legacy-token policy, global
  Codex configuration, local compaction apply, and legal-policy publication
  remain outside this claim.

## Canonical Artifacts (source of truth)

- `cli/orp.py`
- `packages/orp-workspace-launcher/src/storage.js`
- `packages/orp-workspace-launcher/src/codex.js`
- `packages/orp-workspace-launcher/src/hosted-state.js`
- `spec/v1/local-config.schema.json`
- `spec/v1/storage-report.schema.json`
- `spec/v1/codex-context.schema.json`
- `spec/v1/hosted-workspace-state-v2.schema.json`
- `analysis/FAILED_keychain-security-cli-truncation-20260823.md`
- `results/verification/orp-0.5.0-rc.1-release.md`
- orp-web-app `drizzle/migrations/0046_orp_v2_local_first.sql`
- orp-web-app `lib/auth/device-authorization.ts`
- orp-web-app `lib/auth/device-tokens.ts`
- orp-web-app `lib/workspaces/hosted-state-v2.ts`
- orp-web-app `docs/orp-0.5-operations.md`

## Verification Hook

- Run `python3 -m unittest discover -s tests -v`; expect 256 tests and `OK`.
- Run `node --test packages/orp-workspace-launcher/test/*.test.js`; expect 79
  passing tests.
- In orp-web-app, run `./node_modules/.bin/vitest run`; expect 186 passing tests
  and four intentional database-test skips.
- In orp-web-app, run the v2 integration test with a disposable Postgres
  database; expect four passing tests.
- In orp-web-app, run `./node_modules/.bin/tsc --noEmit` and the production
  `next build`; expect zero type errors and all 80 pages generated.
- Pack and install the npm tarball into fresh XDG roots; expect version
  `0.5.0-rc.1`, offline `workspace list`, zero repository/Codex storage scans,
  private local writes, and a prompt-preserving Codex packet below 2,048 bytes.
- Run `node scripts/npm-release-tag.js 0.5.0-rc.1`; expect `next`. Run it with
  `0.5.0`; expect `latest`.

Determinism notes: package contents are controlled by `package.json` and
`.npmignore`; migration/compaction/backfill plans hash their reviewed inputs;
the package checksum below identifies the exact compressed candidate.

## Status

Verified

## Next Hook

Publish the immutable RC to npm `next`, deploy the exact web commit to an
isolated preview, and record registry plus staging results before requesting
the production gate.
