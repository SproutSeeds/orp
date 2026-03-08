# Coda to ORP Contract

This document defines the boundary between:

- `codacli.com` / `coda-cli`
- `ORP`

The goal is to let both systems work together without turning ORP into an app
backend or turning Coda into a second protocol runtime.

## Repository Split

Recommended shape:

- `orp` repo
  - protocol/runtime
  - discovery execution
  - collaboration execution
  - packets, run records, summaries
  - portable local-first CLI
- `coda-cli` repo
  - operator-facing wrapper
  - active profile selection
  - auth/session handling
  - Coda export retrieval
  - convenience commands layered over ORP
- `codacli.com`
  - authenticated web product
  - user database
  - idea cards
  - feature scaffolds
  - notes/detail sections
  - export surface for agents and `coda-cli`

## Ownership Boundary

Coda owns:

- user identity
- database records
- idea cards
- categories
- feature scaffolds
- note/detail sections
- active context selection
- export APIs / export files

ORP owns:

- portable discovery profile format
- GitHub discovery scans
- collaboration workflows
- gate execution
- packets
- run summaries
- process artifacts

In short:

- Coda answers: "What does this user care about right now?"
- ORP answers: "How do we discover, structure, and execute the work?"

## MVP Rule

The MVP should be read-only from Coda into ORP.

That means:

- Coda exports context
- ORP consumes derived context
- ORP produces scan/run artifacts
- Coda may read those artifacts later
- ORP does not write back into Coda yet

This keeps the first integration simple and auditable.

## Canonical Coda Export

Coda should expose a canonical export that reflects the app's richer data
model.

Example shape:

```json
{
  "schema_version": "1.0.0",
  "user": {
    "id": "user_123",
    "handle": "cody"
  },
  "active_context": {
    "idea_id": "idea_problem857",
    "title": "Sunflower formalization work",
    "categories": ["math", "lean", "formalization"]
  },
  "ideas": [
    {
      "id": "idea_problem857",
      "title": "Sunflower formalization work",
      "summary": "Look for repos and issues aligned with Problem 857 work.",
      "tags": ["sunflower", "lean", "proof"],
      "feature_scaffold": {
        "areas": ["balance", "container", "docs"],
        "notes": ["Prefer public repos first."]
      }
    }
  ]
}
```

ORP should not depend directly on the full Coda export schema.

## Derived ORP Inputs

`coda-cli` should derive smaller ORP-native inputs from the richer Coda export.

The first derived input is an ORP discovery profile.

Example:

```json
{
  "schema_version": "1.0.0",
  "profile_id": "idea_problem857",
  "notes": [
    "Derived from Coda active context."
  ],
  "discover": {
    "github": {
      "owner": {
        "login": "SproutSeeds",
        "type": "org"
      },
      "signals": {
        "keywords": ["sunflower", "formalization", "proof"],
        "repo_topics": ["lean", "math"],
        "languages": ["Lean"],
        "areas": ["balance", "container", "docs"],
        "people": []
      },
      "filters": {
        "include_repos": [],
        "exclude_repos": [],
        "issue_states": ["open"],
        "labels_any": [],
        "exclude_labels": [],
        "updated_within_days": 180
      },
      "ranking": {
        "repo_sample_size": 30,
        "max_repos": 12,
        "max_issues": 24,
        "max_people": 12,
        "issues_per_repo": 30
      }
    }
  }
}
```

Other future derived inputs may include:

- collaboration bootstrap hints
- target repo selection
- issue lane selection
- preferred adapters

## ORP Outputs Coda May Read

For the first integration, Coda should treat ORP outputs as read-only runtime
artifacts.

Useful outputs:

- `orp/discovery/github/<scan_id>/SCAN.json`
- `orp/discovery/github/<scan_id>/SCAN_SUMMARY.md`
- `orp/artifacts/<run_id>/RUN.json`
- `orp/artifacts/<run_id>/RUN_SUMMARY.md`
- `orp/packets/<packet_id>.json`

These let Coda display:

- recommended repos/issues/people
- latest collaboration run results
- packetized process context

## CLI Relationship

`coda-cli` should be a thin wrapper over ORP, not a second workflow engine.

Good examples:

- `coda profile export`
- `coda profile use <idea-id>`
- `coda discover`
- `coda collaborate init`

Under the hood, those should call ORP's JSON surfaces such as:

- `orp discover profile init --json`
- `orp discover github scan --json`
- `orp collaborate init --json`
- `orp collaborate run --json`

## Non-Goals For ORP

ORP should not own:

- authenticated user databases
- profile sharing semantics
- team/private visibility policy
- app-level note editing
- direct mutation of Coda records

Those belong in Coda.

## Practical Rule

When in doubt:

- if it is portable execution or protocol data, keep it in ORP
- if it is user/app context or authenticated product state, keep it in Coda
