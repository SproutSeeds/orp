# npm Release Checklist (`@sproutseeds/orp-cli`)

Use this checklist to publish professional, versioned ORP CLI releases.

## One-time setup

1. Confirm npm package ownership for `@sproutseeds/orp-cli`.
2. Add repository secret `NPM_TOKEN` in GitHub Actions:
   - token should have permission to publish this package.
3. Confirm package metadata in `package.json`:
   - `name`, `version`, `repository`, `bin`.

## Per-release flow

1. Ensure `main` is green and local tests pass:
   - `python3 -m unittest discover -s tests -v`
   - `npm pack --dry-run --cache /tmp/orp-npm-cache`
2. Bump version in `package.json` (for example `0.1.1`).
3. Commit and push the version bump to `main`.
4. Create and push a matching tag:
   - `git tag v0.1.1`
   - `git push origin v0.1.1`
5. Watch workflow:
   - `.github/workflows/npm-publish.yml`
   - tag push is the normal publish trigger
6. Verify npm install:
   - `npm i -g @sproutseeds/orp-cli`
   - `orp -h`

## Important guardrail

Tag version must match `package.json` exactly.

- Example:
  - tag: `v0.1.1`
  - package version: `0.1.1`

The publish workflow hard-fails if these differ.

Manual workflow dispatch is available as a recovery path, but it still requires the same exact version string.

## Manual publish fallback

If automation is temporarily unavailable:

1. Checkout intended commit locally.
2. Run release validations above.
3. Publish:
   - `npm publish --access public`
4. Create and push the matching tag:
   - `git tag v0.1.1`
   - `git push origin v0.1.1`
5. Add release notes.

The tag-triggered workflow will still validate the version and will skip `npm publish` if that exact npm version already exists.
