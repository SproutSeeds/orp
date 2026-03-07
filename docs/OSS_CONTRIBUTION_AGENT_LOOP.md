# OSS Contribution Agent Loop

Use this loop when the task is external OSS contribution workflow rather than a research claim.

## 1. Orient

- Read `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md`.
- Read `PROTOCOL.md`.
- Keep the ORP boundary in force: governance artifacts are process-only, not evidence.

## 2. Choose The Adapter

- If the target is mathlib, inspect:
  - `packs/external-pr-governance/adapters/mathlib/README.md`
- If the target is formal-conjectures, inspect:
  - `packs/external-pr-governance/adapters/formal-conjectures/README.md`

If the target repo is new, model its adapter on those two.

## 3. Render Or Draft A Governance Config

- Start from:
  - `packs/external-pr-governance/pack.yml`
- Render or adapt:
  - `packs/external-pr-governance/profiles/oss-pr-governance.yml.tmpl`
  - `packs/external-pr-governance/profiles/oss-feedback-hardening.yml.tmpl`

Fastest path:

```bash
orp pack install --pack-id external-pr-governance
```

That gives you install-and-adapt configs with explicit placeholder commands. Replace those adapter hooks before running meaningful governance passes.

If a host repo already has a stronger adapter, prefer that adapter over the generic template.

## 4. Run The Lifecycle In Order

1. `external_watch_select`
2. `external_pre_open`
3. `external_local_readiness`
4. `external_draft_transition`
5. `external_draft_lifecycle`
6. `external_feedback_hardening` when maintainer feedback reveals a missed check

Do not skip directly from local work to ready-for-review.

## 5. Preserve Etiquette

- Coordinate before competing with active contributors.
- Keep PR text portable and concise.
- Open or update as draft first.
- Only mark ready when local checks, freeze/readiness checks, and draft CI are all green.
- Resolve review threads only after the corresponding fix is pushed and rechecked.

## 6. Checkpoint

Before handoff, compaction, `git commit`, or `git push`:

```sh
scripts/orp-checkpoint.sh --sync --agent-file /path/to/agent/instructions.md "oss contribution governance checkpoint"
```

## 7. Respect The Boundary

- Governance profiles and packets describe workflow quality.
- The underlying repo artifacts remain the evidence source.
- If a guard fails, downgrade workflow confidence immediately and preserve the failure state.
