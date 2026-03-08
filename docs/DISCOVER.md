# ORP Discover

`orp discover` is ORP's built-in discovery ability for finding promising work
inside a GitHub owner space.

The first concrete surface is a GitHub profile scanner:

- scaffold a discovery profile
- define keywords, languages, topics, areas, and people signals
- scan a GitHub user or organization
- rank repositories, issues, and active people
- hand off the strongest match into `orp collaborate`

Today ORP scans public GitHub owner space by default. If richer access policy
or profile governance exists later, that belongs in Coda rather than in ORP.

## Commands

Scaffold a profile:

```bash
orp discover profile init --owner SproutSeeds --owner-type org --json
```

Run a scan:

```bash
orp discover github scan --profile orp.profile.default.json --json
```

## Profile Model

Discovery profiles are portable JSON files owned by ORP.

Current profile fields let you shape:

- GitHub owner scope
- keywords
- repo topics
- languages
- area terms
- people signals
- repo and issue filters
- ranking limits

## Artifacts

GitHub scans write:

- `orp/discovery/github/<scan_id>/SCAN.json`
- `orp/discovery/github/<scan_id>/SCAN_SUMMARY.md`

These are process-only recommendation artifacts, not evidence.

## Coda Relationship

ORP should own the portable discovery profile format and the scanning
artifacts.

If `coda-cli` exists later, the clean role for Coda is:

- manage active profiles
- switch between operator contexts
- wrap ORP commands for a smoother operator UX

That keeps ORP as the protocol/runtime while letting Coda become a higher-level
profile manager if it earns its place.
