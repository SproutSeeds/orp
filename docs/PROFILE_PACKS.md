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

## Rendering

Use:

```bash
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --list

python3 scripts/orp-pack-render.py \
  --pack packs/erdos-open-problems \
  --template sunflower_live_compare_suite \
  --var TARGET_REPO_ROOT=/path/to/repo \
  --out /path/to/repo/orp.erdos-live-compare.yml

python3 scripts/orp-pack-render.py \
  --pack packs/erdos-open-problems \
  --template sunflower_mathlib_pr_governance \
  --var TARGET_REPO_ROOT=/path/to/repo \
  --out /path/to/repo/orp.erdos-mathlib-pr-governance.yml

python3 scripts/orp-pack-render.py \
  --pack packs/erdos-open-problems \
  --template erdos_problems_catalog_sync \
  --var TARGET_REPO_ROOT=/path/to/repo \
  --var ORP_REPO_ROOT=/path/to/orp \
  --out /path/to/repo/orp.erdos-catalog-sync.yml
```

Then run ORP with the rendered config:

```bash
./scripts/orp --repo-root /tmp/orp-compare --config /path/to/repo/orp.erdos-live-compare.yml \
  gate run --profile sunflower_live_compare_857

export ORP_ISSUE_NUMBER=34959
export ORP_BRANCH_NAME=cody/issue-34959-cancellation-bounds
export ORP_PR_BODY_FILE=/path/to/repo/analysis/MATHLIB_DRAFT_PR_BODY.md

./scripts/orp --repo-root /tmp/orp-compare --config /path/to/repo/orp.erdos-mathlib-pr-governance.yml \
  gate run --profile sunflower_mathlib_full_flow

./scripts/orp --repo-root /tmp/orp-compare --config /path/to/repo/orp.erdos-catalog-sync.yml \
  gate run --profile erdos_catalog_sync_active

./scripts/orp erdos sync --problem-id 857 --problem-id 20
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
