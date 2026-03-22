# npm Release Checklist (`open-research-protocol`)

Use this checklist to publish professional, versioned ORP CLI releases.

## One-time setup

1. Confirm npm package ownership for `open-research-protocol`.
2. Add repository secret `NPM_TOKEN` in GitHub Actions:
   - token should have permission to publish this package.
3. Confirm package metadata in `package.json`:
   - `name`, `version`, `repository`, `bin`.

## Per-release flow

1. Ensure `main` is green and local tests pass:
   - shortcut: `bash scripts/orp-release-smoke.sh`
   - `python3 -m unittest discover -s tests -v`
   - `git status --short`
   - `git rev-list --left-right --count origin/main...HEAD`
   - `npm view open-research-protocol version dist-tags --json`
   - `npm pack --dry-run --cache /tmp/orp-npm-cache`
   - `npm publish --dry-run`
2. Run the fresh-install governance smoke test from a clean temp prefix and clean repo:
   - scripted path:
     - `bash scripts/orp-release-smoke.sh`
     - `bash scripts/orp-release-smoke.sh --hosted --codex-session-id <session-id>`
     - `bash scripts/orp-release-smoke.sh --hosted --worker --codex-session-id <session-id>`
   - `npm pack`
   - `npm install -g --prefix /tmp/orp-global ./open-research-protocol-X.Y.Z.tgz`
   - `env PATH=/tmp/orp-global/bin:$PATH orp -h`
   - `mkdir /tmp/orp-fresh && cd /tmp/orp-fresh`
   - `env PATH=/tmp/orp-global/bin:$PATH orp init --json`
   - `git config user.name "ORP Release Smoke"`
   - `git config user.email "orp-release@example.com"`
   - `env PATH=/tmp/orp-global/bin:$PATH orp branch start work/bootstrap --allow-dirty --json`
   - `env PATH=/tmp/orp-global/bin:$PATH orp checkpoint create -m "bootstrap governance" --json`
   - `env PATH=/tmp/orp-global/bin:$PATH orp backup -m "backup bootstrap governance" --json`
   - `env PATH=/tmp/orp-global/bin:$PATH orp gate run --profile default --json`
   - `env PATH=/tmp/orp-global/bin:$PATH orp checkpoint create -m "capture passing validation" --json`
   - `env PATH=/tmp/orp-global/bin:$PATH orp ready --json`
   - optional follow-through:
     - `env PATH=/tmp/orp-global/bin:$PATH orp packet emit --profile default --json`
     - `env PATH=/tmp/orp-global/bin:$PATH orp report summary --json`
3. Confirm the version you intend to publish is not already live.
   - local `package.json` version must be newer than the currently published `latest`
   - `npm publish` is guarded and will fail if the worktree is dirty or the current commit is not already on a remote branch
4. Bump version in `package.json` (for example `0.4.4` -> `0.4.5`).
5. Commit and push the version bump to `main`.
6. Create and push a matching tag:
   - `git tag v0.4.5`
   - `git push origin v0.4.5`
7. Watch workflow:
   - `.github/workflows/npm-publish.yml`
   - tag push is the normal publish trigger
8. Verify npm install after publish:
   - `npm i -g open-research-protocol`
   - `orp -h`
   - `orp init`
   - `orp status --json`
   - `orp about --json`

## Important guardrail

Tag version must match `package.json` exactly.

- Example:
  - tag: `v0.4.0`
  - package version: `0.4.0`

The publish workflow hard-fails if these differ.

Manual workflow dispatch is available as a recovery path, but it still requires the same exact version string.

## Manual publish fallback

If automation is temporarily unavailable:

1. Checkout intended commit locally.
2. Run release validations above, including `npm publish --dry-run`.
3. Publish:
   - `npm publish --access public`
4. Create and push the matching tag:
   - `git tag vX.Y.Z`
   - `git push origin vX.Y.Z`
5. Add release notes.

The tag-triggered workflow will still validate the version and will skip `npm publish` if that exact npm version already exists.
