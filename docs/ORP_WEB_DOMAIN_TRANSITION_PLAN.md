# ORP Web Domain Transition Plan

Use this when moving the hosted ORP web app from `codacli.com` to the new ORP-aligned domains.

## Target shape

- Primary branded domain: `orp.earth`
- Full-name support domain: `openresearchprotocol.com`
- Legacy redirect domain: `codacli.com`

## Current safe state

- CLI/package is already public as:
  - `open-research-protocol`
  - `orp`
- Hosted app still defaults to `https://codacli.com` in the CLI until the web cutover is verified.
- Keep this default in place until auth, runner, and redirects are all ready.

## Rollout order

### 1. Domain attachment

- Add `orp.earth` and `www.orp.earth` to the Vercel project.
- Add `openresearchprotocol.com` and `www.openresearchprotocol.com` to the same project.
- Keep `codacli.com` attached during the transition.
- Point Namecheap DNS at the Vercel records exactly as issued.

### 2. Canonical browser host

- Make `orp.earth` the canonical browser/app host.
- Update:
  - app metadata
  - canonical URLs
  - OG/Twitter metadata
  - sitemap / robots
- Treat `openresearchprotocol.com` as a support/canonical-name domain, not necessarily the primary user-facing host.

### 3. Auth and email

- Update auth base URLs and callback URLs for `orp.earth`.
- Update magic-link / verification email links to `orp.earth`.
- Confirm cookies and session behavior work cleanly on the new canonical host.
- Avoid running two browser-session domains in parallel longer than necessary.

### 4. Runner / websocket / terminal paths

- Inventory every host reference used by:
  - runner
  - websocket
  - TTY / terminal pairing
  - agent worker loops
- Move those to ORP-aligned hosts only after staging verification.
- If needed, use dedicated subdomains rather than mixing them into the app host.

### 5. Redirects

- Redirect browser traffic from `codacli.com` to `orp.earth`.
- Keep legacy API/worker compatibility only where needed during transition.
- Redirect `openresearchprotocol.com` to `orp.earth` unless there is a deliberate reason to keep it browsable.

### 6. CLI cutover

- After the hosted app is stable on `orp.earth`, update the CLI default hosted base URL.
- Keep `ORP_BASE_URL` / `CODA_BASE_URL` overrides working during the transition.
- Verify:
  - `orp auth login`
  - `orp whoami --json`
  - `orp ideas list --json`
  - `orp world bind ...`
  - `orp checkpoint queue ...`
  - `orp agent work --once --json`

## Verification checklist

- `orp.earth` serves the app correctly.
- Email verification links open on `orp.earth`.
- Existing users can log in without session confusion.
- Runner/worker flows still connect and post responses.
- `codacli.com` redirects cleanly.
- `openresearchprotocol.com` resolves as intended.

## Rollback

- If auth or runner behavior breaks, revert the canonical host before changing the CLI default.
- Keep `codacli.com` attached until the new host has passed real-user verification.
