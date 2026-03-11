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
or profile governance exists later, ORP should still own the portable profile
format and the resulting scan artifacts.

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

## Ownership

ORP owns:

- the portable discovery profile format
- GitHub scanning
- ranked discovery artifacts

Other tools may read or trigger ORP discovery, but ORP does not depend on a
wrapper to manage active context or profile selection.
