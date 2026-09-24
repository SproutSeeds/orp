# npm release procedure

The release unit is one tested tarball tied to a tagged commit on `origin/main`.
Prereleases publish to `next`; stable versions publish to `latest`.

## Prepare and verify

1. Preserve and classify existing work with `git status --short` and
   `orp hygiene --json`. Work on one scoped release branch.
2. Update `package.json`, `package-lock.json`, changelog, migration guidance,
   and release notes together. Check current registry versions and tags.
3. Create a Python 3.11+ environment and install `requirements-test.txt`.
   Run `npm ci --ignore-scripts` and `ORP_PYTHON=/path/to/python npm test`.
   The required Python suite rejects skipped checks. Node tests use a separate
   isolated environment; real installers, remote writes, and Keychain calls
   are blocked in ordinary unit tests.
4. Pack to a temporary directory with `npm pack --ignore-scripts --json`.
   Run `node scripts/verify-package.js <manifest.json> <tarball.tgz>`, then
   `python scripts/test-installed.py <tarball.tgz> --output <installed.json>`.
   This installs lifecycle scripts into temporary prefixes and exercises a
   fresh setup, stable 0.4.38 upgrade, and the rc.1 migration repair.
5. Run `git diff --check`, check the scoped staged files, and record verification
   under `results/verification/<version>/`. Preserve raw local evidence there;
   publish only the sanitized record and summary.
6. Open a release PR. The reusable `.github/workflows/validate.yml` gate covers
   Linux with Node 18/22/24, macOS with Node 24, and Python 3.11/3.14.
   All jobs must pass, including the installed artifact checks.

## Publish

1. Merge the reviewed PR after required checks pass. Fetch `origin/main` and
   verify the exact release commit and version again.
2. Tag that commit `v<package-version>` and push the tag. This triggers
   `.github/workflows/npm-publish.yml`.
3. The publish workflow runs the reusable validation gate, downloads its tested
   tarball, checks a clean tree, main ancestry, matching version tag and lockfile,
   then publishes those exact bytes with provenance. Publication is serialized.
4. The workflow verifies registry SHA-512, the selected dist-tag, and that a
   prerelease did not move stable `latest`. An existing version is accepted only
   if its integrity and channel match the candidate.
5. Download the registry tarball, check its integrity, run an isolated install,
   and create the matching GitHub prerelease/release with the reviewed notes.

Manual workflow dispatch is a recovery path on main. It requires the existing
matching tag and exact `release_version`. Avoid direct `npm publish` from an
unreviewed checkout; use the same tested artifact and checks during recovery.

## Hosted and stable acceptance

Hosted readiness, device authorization, scope enforcement, token rotation and
revocation, workspace readback, and migration recovery have their own checks.
A disposable database and synthetic credentials establish automated behavior.
Production migration/deployment, legacy credential retirement, and stable
promotion require their concrete deployment and acceptance decisions.

Use the native macOS Keychain round-trip check separately from mocked tests.
Record fresh interactive Codex hook delivery separately from TOML/configuration
checks. Keep stable `latest=0.4.38` through the 0.5.0-rc.2 candidate period.
