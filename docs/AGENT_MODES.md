# ORP Agent Modes

ORP agent modes are lightweight cognitive overlays.

They do not change ORP's evidence boundary, artifact model, or canonical
workflow surfaces. They exist to help an agent adjust taste and exploratory
behavior intentionally.

They are optional.

Think of them as paint colors or lenses an agent or user can pick up when the
work needs a different feel or perspective. They should not feel forced,
contrived, or permanently switched on.

## Built-In Modes

### `sleek-minimal-progressive`

Purpose:

- keep outputs clean without becoming generic
- create fresh movement when a project feels flat or trapped
- help the operator dive deeper, step back top-down, zoom wider, or rotate the angle
- preserve one surprising move long enough to evaluate it
- bias toward momentum and graceful next steps

Recommended commands:

```bash
orp mode list --json
orp mode show sleek-minimal-progressive --json
orp mode nudge sleek-minimal-progressive --json
```

Operational idea:

- `list` tells the agent what modes exist
- `show` returns the full reminder, ritual, questions, and anti-patterns
- `nudge` returns one deterministic creativity card that can be used as a
  short-lived prompt overlay for the next drafting or design pass

The `nudge` surface is intentionally small. It should create motion and taste,
not replace the main task or force novelty for its own sake.

Use this mode when:

- the work feels stuck in one framing
- a solution is serviceable but not alive
- you need a deliberate perspective shift
- you want to invite a bit more play without losing structure

### `ruthless-simplification`

Use this when the work is swollen, muddy, or overloaded. It is the "cut to the
live core" mode.

- collapse branches
- remove ornamental complexity
- find the shortest honest shape
- recover momentum through clarity

### `systems-constellation`

Use this when the local move is probably part of a larger field of constraints,
dependencies, and downstream effects.

- step back top-down
- inspect upstream and downstream impacts
- think in loops and time horizons
- choose the system move, not just the local patch

### `bold-concept-generation`

Use this when the work needs bigger options before it needs tighter polish.

- generate stronger conceptual directions
- import principles from other domains
- keep one unreasonable idea alive long enough to inspect it
- prune only after a genuinely bold pass exists

### `granular-breakdown`

Use this when the work needs more intentional granularity so the user, agent,
or future collaborator can actually understand and continue it.

- name the whole problem plainly
- split the work into current state, desired state, and missing bridge
- order steps by dependency, risk, and comprehension
- choose one small verification that proves movement
- compress the result back into a clear summary after the breakdown

Recommended commands:

```bash
orp mode show granular-breakdown --json
orp mode breakdown granular-breakdown --json
orp mode nudge granular-breakdown --json
```

Use `breakdown` when the task needs a real ladder from broad framing to atomic
subtasks or sub-lemmas. Use `nudge` when the agent only needs a compact reminder
card for the next pass.

Use this regularly as part of the research/development loop when:

- the user asks what a feature, command, or error means
- the plan is correct but too large to hold at once
- a repo handoff needs to be understandable to the next agent
- a high-level goal needs to become a safe sequence of small moves

The full breakdown ladder is:

- whole frame
- boundary
- major lanes
- subclaims
- atomic obligations
- dependency ladder
- active target
- durable checklist
- next verification

If the breakdown becomes operationally important, promote it into a durable
checklist artifact with stable IDs, dependencies, statuses, source artifacts,
falsifier boundaries, and the first active target.
