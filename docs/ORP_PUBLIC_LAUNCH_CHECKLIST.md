# ORP Public Launch Checklist

Use this checklist when releasing ORP as the unified public CLI and product surface.

## 1. CLI readiness

- Run:
  - `bash scripts/orp-release-smoke.sh`
  - `python3 -m unittest discover -s tests -v`
  - `git status --short`
  - `git rev-list --left-right --count origin/main...HEAD`
  - `npm view open-research-protocol version dist-tags --json`
  - `npm pack --dry-run --cache /tmp/orp-npm-cache`
  - `npm publish --dry-run`
- Smoke-test in a fresh directory:
  - `bash scripts/orp-release-smoke.sh --hosted --codex-session-id <session-id>`
  - `npm i -g open-research-protocol`
  - `orp -h`
  - `orp workspace -h`
  - `orp init`
  - `orp status --json`
  - `orp branch start work/bootstrap --allow-dirty --json`
  - `orp checkpoint create -m "bootstrap governance" --json`
  - `orp backup -m "backup bootstrap governance" --json`
  - `orp gate run --profile default --json`
  - `orp checkpoint create -m "capture passing validation" --json`
  - `orp ready --json`
  - `orp about --json`
  - `orp auth login`
  - `orp whoami --json`
  - `orp ideas list --json`
  - `orp workspace tabs main`

## 2. Hosted workspace readiness

- Confirm the hosted workspace base URL is reachable.
- Confirm login / verify / whoami still work from the published `orp` binary.
- Confirm at least one real hosted idea can be:
  - listed
  - shown
  - world-bound
  - checkpoint-queued

## 3. Worker loop readiness

- Status:
  Verified internally on March 16, 2026 against `https://orp.earth` with machine-scoped session routing and the polling-based runner lease flow, from both the direct CLI path and the Rust-side smoke harness.
- Confirm one bound world can complete:
  - `orp checkpoint queue --idea-id <idea-id> --json`
  - `orp runner work --once --json`
  - `orp agent work --once --json` remains available as the compatibility path
- Confirm the checkpoint response lands back in the hosted workspace.
- Confirm the hosted operator console reflects the same lifecycle at `/dashboard/admin/runners`.
- Use [RUNNER_INTERNAL_OPERATIONS.md](/Users/codymitchell/Documents/code/orp/docs/RUNNER_INTERNAL_OPERATIONS.md) for the internal rollout and recovery flow.

## 4. Package release

- Refresh launch assets:
  - `npm run render:terminal-demo`
- Bump `package.json` version.
- Commit and push `main`.
- Expect `npm publish` to fail if the worktree is dirty or the release commit is not already on GitHub.
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
- Legacy `@sproutseeds/coda-cli` package is deprecated with a migration note to `open-research-protocol`.

## 6. Post-release checks

- `npm view open-research-protocol version`
- `npm i -g open-research-protocol`
- `orp -h`
- confirm README renders the terminal demo GIF on GitHub and npm
- `orp init`
- `orp status --json`
- `orp about --json`

## 7. Web app rollout coordination

- Keep the web app and CLI rollout loosely coupled.
- Launch the ORP CLI first if the web app/domain transition is still in progress.
- Do not change domain, auth, runner, and package names all in one step unless all staging checks are green.
- Follow [ORP_WEB_DOMAIN_TRANSITION_PLAN.md](/Users/codymitchell/Documents/code/orp/docs/ORP_WEB_DOMAIN_TRANSITION_PLAN.md) for the hosted cutover sequence.
