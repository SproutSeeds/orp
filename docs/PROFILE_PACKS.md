# ORP Profile Packs (v1 Draft)

Profile packs let ORP stay general while domain experts publish reusable workflows for specific problem sets.

## Core principle

- ORP core: generic runtime/spec/lifecycle.
- Profile packs: optional domain bundles (gates, profiles, adapters, docs).

This keeps one stable ORP runtime while enabling many ecosystems.

## Pack layout

```text
packs/<pack-id>/
  pack.yml
  README.md
  profiles/
    *.yml.tmpl
  adapters/           # optional
  docs/               # optional
```

## `pack.yml` metadata

Canonical fields:

- `schema_version`: `1.0.0`
- `pack_id`: stable id
- `name`, `version`, `description`
- `orp_version_min`: optional compatibility floor
- `variables`: render-time variables (for example `TARGET_REPO_ROOT`)
- `templates`: available config templates

Schema:

- `spec/v1/profile-pack.schema.json`

## Template variables

Templates use `{{VAR_NAME}}` placeholders.

Example:

```yaml
working_dir: {{TARGET_REPO_ROOT}}
```

Render-time values are supplied via `--var KEY=VALUE`.

## Install flow (fresh ORP -> pack adoption)

Recommended via ORP CLI:

```bash
orp pack list

orp pack install \
  --pack-id erdos-open-problems
```

If developing ORP locally, the equivalent command is `./scripts/orp`.

External pack source via CLI-only flow:

```bash
orp pack fetch \
  --source https://github.com/example/orp-packs.git \
  --pack-id erdos-open-problems \
  --install-target /path/to/repo
```

This installs rendered config files and writes a dependency audit report:

- `./orp.erdos-catalog-sync.yml`
- `./orp.erdos-live-compare.yml`
- `./orp.erdos-problem857.yml`
- `./orp.erdos.pack-install-report.md`

Issue Smashers workspace install:

```bash
orp pack install \
  --pack-id issue-smashers
```

This writes:

- `./orp.issue-smashers.yml`
- `./orp.issue-smashers-feedback-hardening.yml`
- `./orp.issue-smashers.pack-install-report.md`
- `./issue-smashers/README.md`
- `./issue-smashers/WORKSPACE_RULES.md`
- `./issue-smashers/setup-issue-smashers.sh`
- `./issue-smashers/analysis/ISSUE_SMASHERS_WATCHLIST.json`
- `./issue-smashers/analysis/ISSUE_SMASHERS_STATUS.md`
- `./issue-smashers/analysis/PR_DRAFT_BODY.md`

Use this pack when you want the generic external contribution lifecycle plus a
standard workspace convention for multi-repo issue work. It does not clone repos
automatically and it keeps command hooks install-and-adapt by default.

Default install behavior is starter-friendly:

- includes `catalog`, `live_compare`, and `problem857`,
- scaffolds starter 857/20/367 board scripts + board JSON seeds for install-and-go,
- keeps `governance` optional.

Public-only setup (no private adapters yet):

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --include catalog
```

Clean-room public pack cycle:

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --include catalog

orp --config orp.erdos-catalog-sync.yml \
  gate run --profile erdos_catalog_sync_active

orp report summary
```

This path has been validated against the published npm package in a fresh directory and is the recommended first pack workflow.

Clean-room public Problem 857 cycle:

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --include problem857

orp erdos sync \
  --problem-id 857 \
  --out-problem-dir analysis/erdos_problems/selected

orp --config orp.erdos-problem857.yml \
  gate run --profile sunflower_problem857_discovery

orp report summary
```

This lane remains starter-heavy overall, but `spec_faithfulness` now performs a real public consistency check against the synced Problem 857 payload.

If you want a fresh repo to pull the real public `sunflower-lean` repo instead of starter-only 857 scaffolding, install with:

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --include problem857 \
  --var PROBLEM857_SOURCE_MODE=public_repo \
  --var PROBLEM857_PUBLIC_REPO_URL=https://github.com/SproutSeeds/sunflower-lean
```

This syncs the public Lean repo into `sunflower_lean/` and generates the ORP-owned 857 bridge files that the discovery workflow needs.

Strict mode for private adapter readiness:

```bash
./scripts/orp pack install \
  --pack-id erdos-open-problems \
  --target-repo-root /path/to/sunflower-coda/repo \
  --include live_compare \
  --include problem857 \
  --include governance \
  --no-bootstrap \
  --strict-deps
```

Manual render path (advanced):

```bash
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --list
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --template sunflower_live_compare_suite \
  --var TARGET_REPO_ROOT=/path/to/repo --out /path/to/repo/orp.erdos-live-compare.yml
```

Then run ORP with the rendered config:

```bash
orp --repo-root /path/to/scratch-repo --config /path/to/repo/orp.erdos-live-compare.yml \
  gate run --profile sunflower_live_compare_857

orp --repo-root /path/to/scratch-repo report summary --run-id <run_id>

export ORP_ISSUE_NUMBER=34959
export ORP_BRANCH_NAME=cody/issue-34959-cancellation-bounds
export ORP_NATURALITY_MODULE=Mathlib/Combinatorics/SetFamily/Shade
export ORP_PR_BODY_FILE=/path/to/repo/analysis/MATHLIB_DRAFT_PR_BODY.md

orp --repo-root /path/to/scratch-repo --config /path/to/repo/orp.erdos-mathlib-pr-governance.yml \
  gate run --profile sunflower_mathlib_full_flow

orp --repo-root /path/to/scratch-repo --config /path/to/repo/orp.erdos-catalog-sync.yml \
  gate run --profile erdos_catalog_sync_active

orp erdos sync --problem-id 857 --problem-id 20
```

## Publishing model

- Packs can live in this repo (`packs/`) or external repos.
- Users can copy/install packs without changing ORP core.
- Version packs independently (for example `0.1.0`, `0.2.0`).

## Quality guidance

- Keep templates repo-agnostic (no personal absolute paths).
- Keep required variables minimal.
- Document assumptions in pack README.
- Prefer profile variants over hardcoded behavior in ORP core.
