# Examples (non-exhaustive)

These files are intentionally **minimal** and **illustrative**.

- Treat `templates/` as the canonical spec for fields/structure.
- Treat `PROTOCOL.md` as the canonical spec for workflow rules.
- Do not treat examples as checklists or requirements.

Additional v1 runtime draft examples:

- `orp.reasoning-kernel.starter.yml` — minimal kernel-aware profile showing a real `structure_kernel` gate.
- `kernel/trace-widget.task.kernel.yml` — example typed kernel artifact for a promotable task.
- `kernel/corpus/` — small cross-domain reference corpus used by the kernel validation benchmarks.
- `kernel/comparison/` — matched prompt corpus used by the kernel comparison pilot harness.
- `orp.sunflower-coda.atomic.yml` — discovery-first profile for atomic board workflows.
- `orp.sunflower-coda.live-compare.yml` — side-by-side gate-compare profiles for sunflower Problems 857/20/367.
- `orp.sunflower-coda.pr-governance.yml` — local-first PR governance profile set (pre-open, draft-readiness, full flow).
- `orp.external-pr-governance.yml` — generic external OSS contribution governance example.
- `orp.erdos-problems.catalog.yml` — Erdos catalog sync profile (all/open/closed + open-default active set).
- `packet.problem_scope.example.json` — example `problem_scope` packet with board/ticket/gate/atom context.
- `reports/` — example one-page run summaries for sunflower live-compare profiles.

Pack install flow can generate these config files automatically:

- `orp pack install --pack-id erdos-open-problems`
