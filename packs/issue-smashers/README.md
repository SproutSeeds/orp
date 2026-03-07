# Issue Smashers Pack

Opinionated ORP pack for running disciplined external contribution work from a
shared `issue-smashers/` workspace.

This pack is meant to sit one layer above the generic
`external-pr-governance` pack:

- `external-pr-governance` keeps the portable lifecycle contract
- `issue-smashers` adds a workspace convention, operator-facing docs, and a
  reusable scaffold for multi-repo issue work

## What this pack installs

`orp pack install --pack-id issue-smashers` renders:

- `orp.issue-smashers.yml`
- `orp.issue-smashers-feedback-hardening.yml`
- `orp.issue-smashers.pack-install-report.md`

and bootstraps a workspace skeleton under:

- `issue-smashers/README.md`
- `issue-smashers/WORKSPACE_RULES.md`
- `issue-smashers/setup-issue-smashers.sh`
- `issue-smashers/analysis/PR_DRAFT_BODY.md`
- `issue-smashers/analysis/ISSUE_SMASHERS_WATCHLIST.json`
- `issue-smashers/analysis/ISSUE_SMASHERS_STATUS.md`
- `issue-smashers/repos/`
- `issue-smashers/worktrees/`
- `issue-smashers/scratch/`
- `issue-smashers/archive/`

The pack is intentionally install-and-adapt:

- workspace structure is real
- profile templates are real
- command hooks still require adapter-specific commands before governance runs
  become meaningful

## Workspace model

The `issue-smashers/` directory is a plain workspace, not a replacement for
ORP core and not a monorepo that should own cloned target repos in Git
history.

Recommended usage:

- keep ORP installed globally or available as a separate source repo
- install this pack into a parent directory
- let `issue-smashers/repos/` hold base clones
- let `issue-smashers/worktrees/` hold one active lane per issue
- treat `scratch/` as disposable and `archive/` as optional

## Install through ORP

```bash
orp pack install --pack-id issue-smashers
```

That gives you the rendered configs plus the workspace scaffold.

For a clean test flow, replace the placeholder commands with simple pass
commands and run:

```bash
orp --config orp.issue-smashers.yml \
  gate run --profile issue_smashers_full_flow

orp --config orp.issue-smashers.yml \
  packet emit --profile issue_smashers_full_flow

orp --config orp.issue-smashers-feedback-hardening.yml \
  gate run --profile issue_smashers_feedback_hardening
```

## Included adapters

- `adapters/mathlib/`
  - maps the pack to the highest-rigor current workflow
- `adapters/formal-conjectures/`
  - sketches the next non-mathlib target
- `adapters/generic-github/`
  - keeps the workspace useful even before repo-specific adapters exist

## Design rule

Use this pack when you want the operator ergonomics and directory shape of
Issue Smashers.

Use `external-pr-governance` when you only want the generic lifecycle without a
workspace convention.
