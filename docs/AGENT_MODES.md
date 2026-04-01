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
