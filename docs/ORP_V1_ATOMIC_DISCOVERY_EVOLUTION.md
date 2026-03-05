# ORP v1 Evolution: Atomic Discovery + Team Collaboration

This document extends ORP from a docs-first protocol into a local-first runtime model that still preserves ORP core boundaries.

## Why this evolution

ORP cannot be only a GitHub/PR collaboration wrapper. In sunflower-coda style workflows, truth advances through:

- atomic board states (`tickets -> gates -> atoms`),
- scope-lock and spec-faithfulness checks,
- deterministic theorem-cycle gates,
- route-progress verification (strict and loose).

So ORP v1 must model discovery loops and collaboration loops as first-class peers.

## Core model

1. ORP Spec (stable core)
- Protocol rules, claim levels, downgrade rules.
- Versioned schemas for packets/config.
- Lifecycle mapping for claim and atomic states.

2. ORP Runtime (optional executor)
- Runs configured gates.
- Captures stdout/stderr/timings/evidence pointers.
- Emits packet JSON + packet markdown + artifact logs.

3. ORP Profiles (optional apps)
- `discovery` profile for atomic problem-scope loops.
- `collaboration` profile for PR prep and handoff.
- `review` profile for triage and verification.

## Proposed repo tree

```text
orp/
  PROTOCOL.md
  templates/
  spec/
    v1/
      packet.schema.json
      orp.config.schema.json
      LIFECYCLE_MAPPING.md
  examples/
    orp.sunflower-coda.atomic.yml
    packet.problem_scope.example.json
  docs/
    ORP_V1_ATOMIC_DISCOVERY_EVOLUTION.md
  scripts/
    orp-init.sh
    orp-checkpoint.sh
    orp-agent-integrate.sh
  cli/                         # planned runtime package
    src/
      commands/
        init.ts
        gate-run.ts
        packet-emit.ts
      profiles/
        discovery.ts
        collaboration.ts
        review.ts
      packet/
        writer-json.ts
        writer-markdown.ts
      gates/
        runner.ts
        evaluator.ts
```

## Lifecycle compatibility contract

Claim workflow stays compatible with existing templates:

- `Draft -> draft`
- `In review -> ready`
- `Verified -> reviewed`
- `Blocked -> blocked`
- `Retracted -> retracted`

Atomic discovery workflow adds board-native mappings:

- `todo -> draft`
- `in_progress -> ready`
- `blocked -> blocked`
- `done -> reviewed`

`accepted` remains explicit; do not auto-promote without recorded acceptance criteria.

## Packet kinds and minimum outputs

ORP v1 packet kinds:

- `pr`
- `claim`
- `verification`
- `problem_scope`
- `atom_pass`

Minimum outputs per run:

- `orp/packets/<id>.json`
- `orp/packets/<id>.md`
- `orp/artifacts/<run_id>/...`

For discovery packets, include board context:

- `board_id`, `problem_id`, `ticket_id`, `gate_id`, `atom_id`
- atom dependencies and ready-queue size
- route status snapshot
- board JSON snapshot path

## Sunflower-coda profile mapping

The example profile (`examples/orp.sunflower-coda.atomic.yml`) treats existing board operations as canonical gates:

- board refresh gate (`problem857_ops_board.py refresh`)
- ready-queue gate (`problem857_ops_board.py ready`)
- spec-faithfulness gate (`orchestrator/spec_check.py`)
- Lean build gate (`lake build SunflowerLean.Balance`)
- frontier/route gate (`scripts/frontier_status.py --problem 857`)

This means ORP wraps your proven local gates instead of replacing them.

## Migration path for this repo

1. Keep `PROTOCOL.md` and templates as the constitution.
2. Keep current shell scripts as stable compatibility layer.
3. Add runtime CLI as optional (not mandatory for adoption).
4. Ship discovery profile first for atomic board users.
5. Keep reviewer/collaborator profiles optional modules.

This keeps ORP core stable while letting high-rigor workflows (like sunflower-coda) adopt runtime enforcement immediately.

## Pack Distribution Model

To keep ORP core repo-agnostic and still support specialized domains:

- publish domain workflows as profile packs under `packs/` (or external repos),
- define pack metadata in `pack.yml` (schema: `spec/v1/profile-pack.schema.json`),
- ship templates with placeholders (for example `{{TARGET_REPO_ROOT}}`),
- render to concrete config via `scripts/orp-pack-render.py`.

This makes profiles portable and installable without hardcoding one team's repo paths into ORP core.

Collaboration governance example is now captured as a separate pack template:

- `packs/erdos-open-problems/profiles/sunflower-mathlib-pr-governance.yml.tmpl`

It models pre-open viability/policy checks and draft-readiness gates as optional collaboration profiles, parallel to discovery profiles.

## Minimal CLI Now Available

A minimal runtime skeleton now exists at:

- `cli/orp.py`
- `scripts/orp` (launcher)

Supported commands:

```bash
./scripts/orp init
./scripts/orp gate run --profile default
./scripts/orp packet emit --profile default
./scripts/orp report summary --run-id <run_id>
./scripts/orp erdos sync
```

For sunflower-style discovery profiles:

```bash
./scripts/orp --repo-root /path/to/repo --config examples/orp.sunflower-coda.atomic.yml \
  gate run --profile sunflower_problem857_discovery

./scripts/orp --repo-root /path/to/repo --config examples/orp.sunflower-coda.atomic.yml \
  packet emit --profile sunflower_problem857_discovery --kind problem_scope
```

Current scope of this runtime:

- sequential gate execution with pass/fail rule checks,
- captured stdout/stderr logs in `orp/artifacts/<run_id>/`,
- one-page run summaries (`orp/artifacts/<run_id>/RUN_SUMMARY.md`) via `orp report summary`,
- run state in `orp/state.json`,
- packet JSON + markdown emission to `orp/packets/`.
