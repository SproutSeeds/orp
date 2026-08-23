# Failed Path Record

> Note: This record documents a failure of an approach, not a person.

## Topic

Manual local npm publication authentication for ORP 0.4.37

## Summary

The current shell's npm session cannot authenticate to the registry. This
rules out an immediate manual local publish unless an existing approved
credential can be restored from ORP or Keychain.

## What was attempted

- `npm whoami`

## Why it failed

npm returned `E401 Unauthorized` for the registry `/-/whoami` endpoint.

## Evidence (canonical artifacts)

- `results/verification/orp-0.4.37-release.md`
- Repository release workflow: `.github/workflows/npm-publish.yml`

## What this rules out

Publishing manually from the current unauthenticated npm CLI session.

## What might still work (next hook)

Use the normal tag-triggered GitHub Actions publication path and verify its
configured `NPM_TOKEN`; otherwise restore an existing npm credential from ORP
or macOS Keychain without exposing the token in logs or repository files.
