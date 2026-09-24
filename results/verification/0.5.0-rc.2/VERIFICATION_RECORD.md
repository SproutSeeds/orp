# Verification Record — ORP 0.5.0-rc.2

## Verified claim

`analysis/claims/orp-0.5.0-rc.2.md` — **Verified** for the local regression and installed-package checks recorded here.

## Verifier and date

ORP release verification, September 23, 2026 (local; September 24 UTC).

## Environment

macOS arm64; Node 24.10.0; Python 3.14.7; npm 11.6.0. Python dependencies are pinned in `requirements-test.txt`; npm dependencies use `package-lock.json`.

## Canonical inputs

`cli/`, `packages/`, `tests/`, `spec/v2/`, `scripts/`, `.github/workflows/`, `package.json` and `package-lock.json`. Base commit and selected source hashes are in `summary.json`.

## Verification hooks

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
npm ci --ignore-scripts --no-audit --no-fund
ORP_PYTHON="$PWD/.venv/bin/python" npm test
npm pack --ignore-scripts --json --pack-destination /tmp > /tmp/orp-manifest.json
node scripts/verify-package.js /tmp/orp-manifest.json /tmp/open-research-protocol-0.5.0-rc.2.tgz
.venv/bin/python scripts/test-installed.py /tmp/open-research-protocol-0.5.0-rc.2.tgz --output /tmp/orp-installed.json
npm audit --omit=dev
.venv/bin/python cli/orp.py hygiene --json
git diff --check
```

Expected: 277 Python tests and 92 Node tests pass with zero skips, followed by the kernel artifact checks. All three installed lanes must report PASS: fresh, stable 0.4.38 upgrade, and rc.1 migration repair. The package verifier must accept the actual tarball; production dependency audit must report zero vulnerabilities.

## Result

**PASS**, scoped to the commands and environment above. `summary.json` records the installed tarball SHA-512, package file count, source hashes and counts. `native-keychain.json` records a separate native synthetic credential write/read/delete/absence check; no real credentials were used for that check.

The suite exercises compaction preservation, verified archive restoration, migration interruption and target races, stale-reference repair, partial-write preservation, semantic approval/readback, shared v2 fixtures, SemVer/channel handling, Codex TOML preservation, and refusal of unsupported auth before network effects.

## Determinism and evidence

Regression fixtures run with disposable HOME/XDG/temp roots and guarded external effects. Installed upgrade checks retrieve the named historical npm versions into disposable prefixes. Timestamps, temporary paths, registry availability and native Keychain availability vary. Workflow validation repacks and rechecks its exact candidate; registry verification uses that workflow candidate's integrity, which may differ from this local archive because of npm/runtime packaging details.

Raw local attempts and logs remain under this canonical directory and are ignored by Git and excluded from npm. Sanitized durable results are committed here. Failed attempts and corrections are recorded in `analysis/FAILED_rc2-verification-setup.md`.

## Limits and next hook

GitHub runs the same gate on Linux Node 18/22/24 and macOS Node 24, with Python 3.11/3.14. Those results and the publication receipt must pass before release completion. Native Keychain proof covers macOS only; Windows is unverified. Hosted contract tests do not establish production availability. Fresh interactive Codex delivery, a named hosted production deployment, and real-use acceptance remain stable-promotion gates.
