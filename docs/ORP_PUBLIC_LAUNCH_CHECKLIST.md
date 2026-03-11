# ORP Public Launch Checklist

Use this checklist when releasing ORP as the unified public CLI and product surface.

## 1. CLI readiness

- Run:
  - `python3 -m unittest discover -s tests -v`
  - `npm pack --dry-run --cache /tmp/orp-npm-cache`
- Smoke-test in a fresh directory:
  - `npm i -g open-research-protocol`
  - `orp about --json`
  - `orp auth login`
  - `orp whoami --json`
  - `orp ideas list --json`

## 2. Hosted workspace readiness

- Confirm the hosted workspace base URL is reachable.
- Confirm login / verify / whoami still work from the published `orp` binary.
- Confirm at least one real hosted idea can be:
  - listed
  - shown
  - world-bound
  - checkpoint-queued

## 3. Worker loop readiness

- Confirm one bound world can complete:
  - `orp checkpoint queue --idea-id <idea-id> --json`
  - `orp agent work --once --json`
- Confirm the checkpoint response lands back in the hosted workspace.

## 4. Package release

- Bump `package.json` version.
- Commit and push `main`.
- Tag and push:
  - `git tag vX.Y.Z`
  - `git push origin vX.Y.Z`
- Publish if needed:
  - `npm publish --access public`

## 5. Transition messaging

- Treat ORP as the primary CLI surface.
- Point old `coda-cli` users toward:
  - `npm i -g open-research-protocol`
  - `orp`
- If the legacy `coda-cli` package is still live, deprecate it with a migration note once ORP release is confirmed stable.

## 6. Post-release checks

- `npm view open-research-protocol version`
- `npm i -g open-research-protocol`
- `orp -h`
- `orp about --json`

## 7. Web app rollout coordination

- Keep the web app and CLI rollout loosely coupled.
- Launch the ORP CLI first if the web app/domain transition is still in progress.
- Do not change domain, auth, runner, and package names all in one step unless all staging checks are green.
