# External PR Governance Pack

Generic ORP pack for local-first external OSS contribution workflows.

This pack is intentionally adapter-oriented:

- ORP core stays generic.
- Repo-specific commands and etiquette live in adapters or rendered config variables.

## Purpose

Standardize the lifecycle for external contributions:

1. watch and select,
2. viability and coordination,
3. local verification,
4. ready-to-draft freeze,
5. draft PR lifecycle,
6. ready-for-review promotion,
7. maintainer-feedback hardening.

## Included templates

- `oss_pr_governance`
  - generic watch/select, pre-open, local-readiness, draft-transition, and draft-lifecycle profiles
- `oss_feedback_hardening`
  - generic feedback-to-guard hardening profile

## Included adapters

- `adapters/mathlib/`
  - reference adapter for the highest-rigor current implementation
- `adapters/formal-conjectures/`
  - first non-mathlib adapter target

## Design rule

Use this pack for the generic contract.

If a stronger repo-specific adapter already exists, treat that adapter as the source of truth for:

- exact commands,
- exact pass tokens,
- exact PR-body conventions,
- exact branch/worktree conventions,
- exact maintainer etiquette overlays.

## Install Through ORP

Install the generic governance configs into a target repo:

```bash
orp pack install --pack-id external-pr-governance
```

That renders:

- `orp.external-pr-governance.yml`
- `orp.external-pr-feedback-hardening.yml`
- `orp.external-pr.pack-install-report.md`

The rendered configs are intentionally install-and-adapt, not install-and-go:

- repo metadata defaults to placeholders
- command hooks default to explicit failing placeholders
- bootstrap creates `analysis/PR_DRAFT_BODY.md` so the PR-body lane has a canonical starting point

Replace the placeholder commands with adapter-specific commands before running meaningful governance profiles.

## Render examples

List templates:

```bash
python3 scripts/orp-pack-render.py --pack packs/external-pr-governance --list
```

Render generic governance config:

```bash
python3 scripts/orp-pack-render.py \
  --pack packs/external-pr-governance \
  --template oss_pr_governance \
  --var TARGET_REPO_ROOT=/path/to/working/repo \
  --var TARGET_GITHUB_REPO=owner/repo \
  --var TARGET_GITHUB_AUTHOR=YourLogin \
  --var WATCH_SELECT_COMMAND="printf 'selection=PASS\n'" \
  --var VIABILITY_COMMAND="printf 'decision=PASS\n'" \
  --var OVERLAP_COMMAND="printf 'overlap=PASS\n'" \
  --var LOCAL_GATE_COMMAND="printf 'gate=PASS\n'" \
  --var READY_TO_DRAFT_COMMAND="printf 'ready_to_draft=PASS\n'" \
  --var PR_BODY_PREFLIGHT_COMMAND="printf 'gate=PASS\n'" \
  --var DRAFT_PR_TRANSITION_COMMAND="printf 'draft_pr=PASS\n'" \
  --var DRAFT_CI_COMMAND="printf 'draft_ci=PASS\n'" \
  --var READY_FOR_REVIEW_COMMAND="printf 'ready_for_review=PASS\n'" \
  --out /path/to/working/repo/orp.external-pr-governance.yml
```

Render feedback-hardening config:

```bash
python3 scripts/orp-pack-render.py \
  --pack packs/external-pr-governance \
  --template oss_feedback_hardening \
  --var TARGET_REPO_ROOT=/path/to/working/repo \
  --var FEEDBACK_RECORD_COMMAND="printf 'feedback_recorded=PASS\n'" \
  --var GUARD_VALIDATION_COMMAND="printf 'guard_validation=PASS\n'" \
  --var DOC_SYNC_COMMAND="printf 'docs_sync=PASS\n'" \
  --out /path/to/working/repo/orp.external-pr-feedback-hardening.yml
```

## Recommended companion docs

- `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md`
- `docs/OSS_CONTRIBUTION_AGENT_LOOP.md`
- `docs/SUNFLOWER_CODA_PR_GOVERNANCE_MAPPING.md`
