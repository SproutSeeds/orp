# Agent Runtime Borrowing Notes

ORP should watch fast-moving personal-agent runtimes such as Hermes Agent and
OpenClaw as design references, not as replacements for the ORP state model.
Their strongest lesson is that users want one reachable assistant surface across
CLI, mobile, messaging, schedulers, and remote machines. ORP's role is to make
that assistant surface durable, governable, and recoverable.

The architectural boundary is:

```text
Clawdad = entry point and operator surface
ORP = durable workspace state, routing ledger, agenda, governance, packets, and checkpoints
Agent runtimes = execution backends, gateways, sandboxes, schedulers, or transports
Project artifacts = evidence
```

Hermes/OpenClaw-style systems can inspire ORP features, but they should not
become parallel ledgers. ORP remains the canonical place for workspace tabs,
linked sessions, runner state, operating agendas, opportunities, connections,
repo governance, checkpoints, and research packets.

## Ideas Worth Borrowing

- Gateway ergonomics: simplify setup for phone, chat, and always-on entrypoints
  while preserving ORP's local-first and hosted-linked records.
- Skills and capability packs: expose small, auditable ORP command groups that
  agents can load for specific jobs instead of handing them the whole machine.
- Background process signals: let long-running builds, scans, and research jobs
  notify the current agent/session when they finish or hit watched output.
- Model and provider routing: study runtime-level provider switching while
  keeping ORP's routing records independent of any one model vendor.
- Subagent isolation: borrow fresh-context worker patterns, but record only the
  resulting task state, evidence paths, and handoff summaries in ORP.
- Local dashboards: use dashboards as visibility layers over ORP state, not as
  a second source of workspace truth.
- Backup/import flows: make ORP's machine state, linked sessions, and local
  workspace ledgers easier to inspect, export, and restore.
- Security hardening: preserve strict boundaries for remote control, including
  allowlists, sandboxed command execution, explicit secret scoping, and clear
  approval points.

## Design Guardrails

- ORP files are process-only and remain separate from evidence.
- Messaging platforms must not own the durable agenda or project ledger.
- Agent memories may summarize preferences or conversation context, but ORP owns
  project routing, governance, and operational state.
- Any borrowed gateway or scheduler behavior should write back to ORP through
  explicit commands, not mutate hidden state.
- A new surface is acceptable only if an operator can still recover the work
  from ORP without knowing which agent runtime handled it.

## First Useful Adapter

A good borrowing experiment is an ORP skill or bridge for an external agent
runtime with read-first commands:

- `orp home --json`
- `orp agenda focus`
- `orp workspace tabs main`
- `orp runner status --json`
- `orp link status --json`
- `orp youtube inspect <url> --json`

The next layer can add carefully scoped writes such as registering a session,
emitting a checkpoint, or dispatching through Clawdad, but only after the read
surface proves useful and safe.
