# ORP v1 Lifecycle Mapping

This mapping keeps current ORP semantics intact while adding atomic discovery states.

## Claim-Level Mapping (current templates -> workflow state)

| Current field | Value | ORP `workflow_state` |
|---|---|---|
| `Claim Status` | `Draft` | `draft` |
| `Claim Status` | `In review` | `ready` |
| `Claim Status` | `Verified` | `reviewed` |
| `Claim Status` | `Blocked` | `blocked` |
| `Claim Status` | `Retracted` | `retracted` |

Notes:
- `Claim Level` (`Exact/Verified/Heuristic/Conjecture`) remains epistemic and separate from workflow state.
- `accepted` is optional and should be set only by an explicit acceptance action (maintainer/reviewer decision), not inferred automatically.

## Atomic Board Mapping (sunflower-style atoms -> workflow state)

| Board atom status | ORP `workflow_state` |
|---|---|
| `todo` | `draft` |
| `in_progress` | `ready` |
| `blocked` | `blocked` |
| `done` | `reviewed` |

Notes:
- Promote to `accepted` at higher scopes only when closure criteria are met and explicitly recorded:
  - all atoms in a gate are `done` -> gate can be marked accepted,
  - all gates in a ticket are complete -> ticket can be marked accepted,
  - route closure can be marked accepted once strict/loose checks pass.

## Why this split matters

- `workflow_state` tracks execution/lifecycle.
- `claim_level` tracks epistemic strength.
- `atom_status` tracks discovery execution at atomic granularity.

This prevents drift between documentation claims, verification records, and board progress signals.
