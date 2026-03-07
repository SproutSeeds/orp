# Erdos Open Problems Pack

Domain pack for sunflower/Erdos workflows.

This pack is designed to preserve ORP core generality:

- `catalog` works in any repo.
- `live_compare`, `problem857`, and `governance` are optional adapters that depend on sunflower-coda style scripts/boards.

## Included templates

- `sunflower_live_compare_suite`
  - Side-by-side gate compare profiles for Problems 857/20/367.
- `sunflower_problem857_discovery`
  - Discovery-first atomic gating profile for Problem 857.
- `sunflower_mathlib_pr_governance`
  - Local-first PR governance profiles aligned to mathlib submission workflow:
    - pre-open policy/viability/naturality checks
    - draft-readiness local gate/tighten/freeze/PR-body hygiene
    - end-to-end full flow
- `erdos_problems_catalog_sync`
  - Sync profile that ingests all Erdos problems from `erdosproblems.com` and publishes:
    - `erdos_problems.all.json`
    - `erdos_problems.open.json`
    - `erdos_problems.closed.json`
    - `erdos_problems.active.json` (open by default)

## Required variable

- `TARGET_REPO_ROOT`
  - Absolute path to the target repo where scripts/boards live.

## Recommended install flow (CLI)

List packs:

```bash
./scripts/orp pack list
```

If ORP is installed globally via npm, use `orp pack list`.

Install all pack components into a target repo and write dependency audit:

```bash
orp pack install \
  --pack-id erdos-open-problems
```

If developing ORP locally, the equivalent command is `./scripts/orp pack install ...`.

Fetch this pack from a remote pack repo via CLI:

```bash
orp pack fetch \
  --source https://github.com/example/orp-packs.git \
  --pack-id erdos-open-problems \
  --install-target .
```

Install public-only component:

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --include catalog
```

Clean-room public catalog cycle:

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --include catalog

orp --config orp.erdos-catalog-sync.yml \
  gate run --profile erdos_catalog_sync_active

orp report summary
```

This is the simplest pack-backed research cycle validated from the published npm package in a fresh directory.

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

In this public lane, `spec_faithfulness` is no longer a stub. It validates that the synced `erdos_problem.857.json` payload, the installed scope YAML, and the starter board all target the same problem.

Empty repo to real updated Problem 857 workspace:

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --include problem857 \
  --var PROBLEM857_SOURCE_MODE=public_repo \
  --var PROBLEM857_PUBLIC_REPO_URL=https://github.com/SproutSeeds/sunflower-lean

orp erdos sync \
  --problem-id 857 \
  --out-problem-dir analysis/erdos_problems/selected

orp --config orp.erdos-problem857.yml \
  gate run --profile sunflower_problem857_discovery

orp report summary
```

This mode syncs the real public `sunflower-lean` repo into `sunflower_lean/` instead of writing starter-only 857 scaffolding. ORP then generates the 857 bridge files it owns (`analysis/`, `docs/`, `scripts/`, and `orchestrator/`) so the public consistency check and frontier loop do not depend on private repo structure.

Enforce strict adapter readiness:

```bash
orp pack install \
  --pack-id erdos-open-problems \
  --target-repo-root /path/to/sunflower-coda/repo \
  --include live_compare \
  --include problem857 \
  --include governance \
  --no-bootstrap \
  --strict-deps
```

Dependency matrix:

- `docs/SUNFLOWER_ADAPTER_DEPENDENCIES.md`

Optional:

- `ORP_TIMEOUT_SEC` (default `1200`)
- `PROBLEM857_LEAN_BUILD_COMMAND` (default `lake build SunflowerLean.Balance`)
- `PROBLEM857_SOURCE_MODE` (default `starter`; use `public_repo` to sync the public `sunflower-lean` repo plus ORP bridge files)
- `PROBLEM857_PUBLIC_REPO_URL` (default `https://github.com/SproutSeeds/sunflower-lean`)
- `PROBLEM857_PUBLIC_REPO_REF` (default `main`)
- `MATHLIB_REPO_ROOT` (default `$HOME/Documents/code/mathlib4`)
- `MATHLIB_GITHUB_REPO` (default `leanprover-community/mathlib4`)
- `MATHLIB_GITHUB_AUTHOR` (default `SproutSeeds`)
- `DEFAULT_PR_BODY_FILE` (default `analysis/MATHLIB_DRAFT_PR_BODY.md`)
- `READY_TO_DRAFT_NOTE` (default `micro-pass complete: naming/docstring-tone/readability`)
- `UPSTREAM_SUBMISSION_MODE` (default `hold`)
- `MAX_PRS_PER_SESSION` (default `2`)
- `REQUIRE_EXPLICIT_APPROVAL` (default `True`)
- `ORP_NATURALITY_MODULE` (required for governance profiles; no default)
- `ORP_REPO_ROOT` (default `.`)
- `ERDOS_SOURCE_URL` (default `https://erdosproblems.com/range/1-end`)
- `ERDOS_DATA_SUBDIR` (default `analysis/erdos_problems`)
- `ERDOS_OPEN_LIST_FILE` (default `analysis/erdos_problems/erdos_open_problems.md`)
- `ERDOS_TIMEOUT_SEC` (default `90`)
- `ERDOS_ACTIVE_STATUS` (default `open`)

## Render examples (manual / advanced)

List templates:

```bash
python3 scripts/orp-pack-render.py --pack packs/erdos-open-problems --list
```

Render live compare config:

```bash
python3 scripts/orp-pack-render.py \
  --pack packs/erdos-open-problems \
  --template sunflower_live_compare_suite \
  --var TARGET_REPO_ROOT=/path/to/sunflower-coda/repo \
  --out /path/to/sunflower-coda/repo/orp.erdos-live-compare.yml
```

Render 857 discovery config:

```bash
python3 scripts/orp-pack-render.py \
  --pack packs/erdos-open-problems \
  --template sunflower_problem857_discovery \
  --var TARGET_REPO_ROOT=/path/to/sunflower-coda/repo \
  --out /path/to/sunflower-coda/repo/orp.erdos-problem857.yml
```

Render mathlib PR governance config:

```bash
python3 scripts/orp-pack-render.py \
  --pack packs/erdos-open-problems \
  --template sunflower_mathlib_pr_governance \
  --var TARGET_REPO_ROOT=/path/to/sunflower-coda/repo \
  --out /path/to/sunflower-coda/repo/orp.erdos-mathlib-pr-governance.yml
```

Render Erdos catalog sync config:

```bash
python3 scripts/orp-pack-render.py \
  --pack packs/erdos-open-problems \
  --template erdos_problems_catalog_sync \
  --var TARGET_REPO_ROOT=/path/to/sunflower-coda/repo \
  --var ORP_REPO_ROOT=/path/to/orp \
  --out /path/to/sunflower-coda/repo/orp.erdos-catalog-sync.yml
```

## Run with ORP

```bash
orp --repo-root /path/to/scratch-repo --config /path/to/sunflower-coda/repo/orp.erdos-live-compare.yml \
  gate run --profile sunflower_live_compare_857

orp --repo-root /path/to/scratch-repo report summary --run-id <run_id>
```

PR-governance run examples:

```bash
export ORP_ISSUE_NUMBER=34959
export ORP_BRANCH_NAME=cody/issue-34959-cancellation-bounds
export ORP_NATURALITY_MODULE=Mathlib/Combinatorics/SetFamily/Shade
export ORP_PR_BODY_FILE=/path/to/sunflower-coda/repo/analysis/MATHLIB_DRAFT_PR_BODY.md

orp --repo-root /path/to/scratch-repo --config /path/to/sunflower-coda/repo/orp.erdos-mathlib-pr-governance.yml \
  gate run --profile sunflower_mathlib_pre_open

orp --repo-root /path/to/scratch-repo --config /path/to/sunflower-coda/repo/orp.erdos-mathlib-pr-governance.yml \
  gate run --profile sunflower_mathlib_draft_readiness
```

Catalog sync run (open-default active set):

```bash
orp --repo-root /path/to/scratch-repo --config /path/to/sunflower-coda/repo/orp.erdos-catalog-sync.yml \
  gate run --profile erdos_catalog_sync_active
```

Look up specific problem links/status:

```bash
orp erdos sync \
  --problem-id 857 \
  --problem-id 20 \
  --out-problem-dir /path/to/sunflower-coda/repo/analysis/erdos_problems/selected
```

Use closed or all as active set:

```bash
python3 scripts/orp-pack-render.py \
  --pack packs/erdos-open-problems \
  --template erdos_problems_catalog_sync \
  --var TARGET_REPO_ROOT=/path/to/sunflower-coda/repo \
  --var ORP_REPO_ROOT=/path/to/orp \
  --var ERDOS_ACTIVE_STATUS=all \
  --out /path/to/sunflower-coda/repo/orp.erdos-catalog-sync.all.yml
```

## Included snapshots

This pack includes a baseline snapshot in `data/` generated by:

```bash
./scripts/orp erdos sync
```

See `data/README.md` for file semantics.

## Daily refresh (optional)

Run daily via cron:

```bash
0 6 * * * cd /path/to/orp && ./scripts/orp erdos sync
```

This refreshes all/open/closed/active JSON snapshots and `erdos_open_problems.md`.

Optional GitHub Actions schedule:

- `.github/workflows/erdos-catalog-refresh.yml`
