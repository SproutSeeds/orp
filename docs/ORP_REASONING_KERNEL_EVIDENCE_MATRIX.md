# ORP Reasoning Kernel Evidence Matrix

This document separates what the ORP Reasoning Kernel currently proves from
what it only suggests.

Its purpose is to prevent the kernel from being over-claimed. The kernel is
stronger when we can say, precisely:

- what is already validated
- what is only partially supported
- what is still unproven
- what experiment would close the gap

Supporting references:

- [docs/ORP_REASONING_KERNEL_V0_1.md](./ORP_REASONING_KERNEL_V0_1.md)
- [docs/ORP_REASONING_KERNEL_TECHNICAL_VALIDATION.md](./ORP_REASONING_KERNEL_TECHNICAL_VALIDATION.md)
- [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json)
- [docs/ORP_REASONING_KERNEL_AGENT_PILOT.md](./ORP_REASONING_KERNEL_AGENT_PILOT.md)
- [docs/ORP_REASONING_KERNEL_AGENT_REPLICATION.md](./ORP_REASONING_KERNEL_AGENT_REPLICATION.md)
- [docs/ORP_REASONING_KERNEL_CONTINUATION_PILOT.md](./ORP_REASONING_KERNEL_CONTINUATION_PILOT.md)
- [docs/ORP_REASONING_KERNEL_CANONICAL_CONTINUATION_PILOT.md](./ORP_REASONING_KERNEL_CANONICAL_CONTINUATION_PILOT.md)

## Evidence Grades

- `A`
  Directly supported by shipped implementation, tests, and repeatable benchmark
  evidence in this repo.
- `B`
  Strongly supported by implementation behavior and design logic, but still
  missing comparative or external validation.
- `C`
  Plausible and well-motivated, but not yet measured directly.
- `D`
  Strategic aspiration only. No meaningful validation yet.

## What Is Sealed For v0.1

These claims are strong enough to treat as validated implementation truths for
the current kernel release.

| Claim | Grade | Current Evidence | Why It Matters |
| --- | --- | --- | --- |
| ORP has a real typed kernel artifact surface. | A | [spec/v1/kernel.schema.json](../spec/v1/kernel.schema.json), [cli/orp.py](../cli/orp.py) | The kernel is not just prose. It is an enforceable CLI surface. |
| `orp init` seeds a valid starter kernel artifact and validates it in the default flow. | A | [tests/test_orp_init.py](../tests/test_orp_init.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | New repos get the kernel by default instead of needing manual adoption. |
| All seven v0.1 artifact classes can scaffold and validate successfully. | A | [tests/test_orp_kernel.py](../tests/test_orp_kernel.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | The kernel is broad enough for multiple project artifact types. |
| Hard mode blocks invalid promotable artifacts. | A | [tests/test_orp_kernel.py](../tests/test_orp_kernel.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | ORP can enforce structural promotion standards rather than only advising. |
| Soft mode records invalidity without blocking work. | A | [tests/test_orp_kernel.py](../tests/test_orp_kernel.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | ORP can stay fluid at intake while still surfacing missing structure. |
| Existing `structure_kernel` gates remain compatible when no explicit kernel config is present. | A | [tests/test_orp_kernel.py](../tests/test_orp_kernel.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | The kernel does not silently break earlier ORP configurations. |
| One-shot local kernel CLI operations are within human-scale latency on the reference machine. | A | [scripts/orp-kernel-benchmark.py](../scripts/orp-kernel-benchmark.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | The kernel is operationally lightweight enough to use during normal work. |
| A small cross-domain reference corpus fits the current class set cleanly. | A | [examples/kernel/corpus](../examples/kernel/corpus), [tests/test_orp_kernel_corpus.py](../tests/test_orp_kernel_corpus.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | The kernel now has explicit cross-domain fit evidence, not only rationale. |
| Each artifact class rejects a candidate when a required field is removed. | A | [tests/test_orp_kernel_corpus.py](../tests/test_orp_kernel_corpus.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | Class-specific enforcement is directly proven instead of inferred from a subset of cases. |
| The CLI validator stays aligned with the published kernel schema. | A | [tests/test_orp_kernel_corpus.py](../tests/test_orp_kernel_corpus.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | The kernel no longer relies on an undocumented validator rule set drifting away from the schema. |
| Equivalent YAML and JSON artifacts validate to the same semantic result. | A | [tests/test_orp_kernel_corpus.py](../tests/test_orp_kernel_corpus.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | The protocol is representation-stable rather than format-sensitive. |
| The validator rejects adversarial near-miss artifacts. | A | [tests/test_orp_kernel_corpus.py](../tests/test_orp_kernel_corpus.py), [docs/benchmarks/orp_reasoning_kernel_v0_1_validation.json](./benchmarks/orp_reasoning_kernel_v0_1_validation.json) | The kernel is stronger against malformed or gameable inputs than before. |
| On a matched internal comparison corpus, kernel artifacts outperform both free-form and generic checklist artifacts on structural scoring. | A | [docs/ORP_REASONING_KERNEL_COMPARISON_PILOT.md](./ORP_REASONING_KERNEL_COMPARISON_PILOT.md), [docs/benchmarks/orp_reasoning_kernel_comparison_v0_1.json](./benchmarks/orp_reasoning_kernel_comparison_v0_1.json), [scripts/orp-kernel-comparison.py](../scripts/orp-kernel-comparison.py) | ORP now has direct comparative evidence for structural artifact quality on a matched internal corpus, not only rationale. |
| On a matched internal pickup proxy, kernel artifacts preserve more explicit handoff-critical information than both free-form and generic checklist artifacts. | A | [docs/ORP_REASONING_KERNEL_PICKUP_PILOT.md](./ORP_REASONING_KERNEL_PICKUP_PILOT.md), [docs/benchmarks/orp_reasoning_kernel_pickup_v0_1.json](./benchmarks/orp_reasoning_kernel_pickup_v0_1.json), [scripts/orp-kernel-pickup.py](../scripts/orp-kernel-pickup.py) | ORP now has a second comparative signal showing that kernel structure turns into more explicit pickup value, not just fuller-looking artifacts. |
| On a matched live Codex recoverability simulation, kernel artifacts preserve full required-field recoverability, outperform free-form artifacts on all matched cases, and outperform generic checklist artifacts on average without per-case losses. | A | [docs/ORP_REASONING_KERNEL_AGENT_PILOT.md](./ORP_REASONING_KERNEL_AGENT_PILOT.md), [docs/benchmarks/orp_reasoning_kernel_agent_pilot_v0_1.json](./benchmarks/orp_reasoning_kernel_agent_pilot_v0_1.json), [scripts/orp-kernel-agent-pilot.py](../scripts/orp-kernel-agent-pilot.py) | ORP now has direct in-environment agent evidence that the kernel’s structural advantage survives contact with a real fresh downstream Codex session. |
| On a `10`-repeat full-corpus live Codex replication pilot, the kernel’s recoverability advantage stays stable across fresh-session reruns, with zero invention, no run-level losses, and perfect per-field stability on required kernel fields. | A | [docs/ORP_REASONING_KERNEL_AGENT_REPLICATION.md](./ORP_REASONING_KERNEL_AGENT_REPLICATION.md), [docs/benchmarks/orp_reasoning_kernel_agent_replication_v0_2.json](./benchmarks/orp_reasoning_kernel_agent_replication_v0_2.json), [scripts/orp-kernel-agent-replication.py](../scripts/orp-kernel-agent-replication.py) | ORP now has stronger repeatability evidence that the live agent result is not just a single-run artifact and that the structural advantage survives at field level, not only in aggregate means. |
| On a matched full-corpus live continuation pilot, kernel artifacts support the strongest continuation score, never underperform the generic checklist baseline, and keep invention at zero. | A | [docs/ORP_REASONING_KERNEL_CONTINUATION_PILOT.md](./ORP_REASONING_KERNEL_CONTINUATION_PILOT.md), [docs/benchmarks/orp_reasoning_kernel_continuation_v0_1.json](./benchmarks/orp_reasoning_kernel_continuation_v0_1.json), [scripts/orp-kernel-continuation-pilot.py](../scripts/orp-kernel-continuation-pilot.py) | ORP now has direct agent-first evidence that kernel artifacts are not only recoverable, but also a safe and effective base for downstream continuation. |
| On a harder matched full-corpus canonical continuation pilot, kernel artifacts beat free-form on every case, beat checklist on average, and keep the lowest invention rate while revealing checklist as a real competitive baseline on some cases. | A | [docs/ORP_REASONING_KERNEL_CANONICAL_CONTINUATION_PILOT.md](./ORP_REASONING_KERNEL_CANONICAL_CONTINUATION_PILOT.md), [docs/benchmarks/orp_reasoning_kernel_canonical_continuation_v0_1.json](./benchmarks/orp_reasoning_kernel_canonical_continuation_v0_1.json), [scripts/orp-kernel-canonical-continuation.py](../scripts/orp-kernel-canonical-continuation.py) | ORP now has a stricter downstream-agent benchmark where the task is not merely “continue safely,” but “produce the next canonical artifact” without inventing unsupported structure. |

## What Is Strong But Not Fully Sealed

These claims are directionally convincing, but still need comparative or
broader validation before they should be presented as fully proven.

| Claim | Grade | Current Evidence | Missing Evidence | Best Next Experiment |
| --- | --- | --- | --- | --- |
| The seven chosen artifact classes are a good universal first set. | B | Cross-domain rationale, passing roundtrip coverage, a small five-domain reference corpus, and full required-field enforcement across all classes | Larger real-world corpus coverage across multiple project types | Cross-domain corpus fit study at real-project scale |
| The kernel reduces accidental chat-to-truth drift. | B | ORP’s promotion model and hard/soft gate behavior | Before/after repo evidence showing fewer ambiguous promotable artifacts | Comparative artifact hygiene study |
| The kernel is better than a generic checklist. | B | Typed classes give stronger semantic requirements than one generic field list, the internal comparison pilot shows a structural scoring advantage, the live Codex pilot shows a higher mean recoverability score with no per-case losses, and the harder canonical continuation pilot still favors the kernel on aggregate while showing checklist is genuinely competitive | Blinded human review and downstream task outcomes | Structured baseline comparison |
| The kernel is better than free-form artifact writing alone. | B | Implementation logic is strong, promotion semantics exist, the internal comparison and pickup pilots favor the kernel, and the live Codex pilot shows a `7/7` case advantage on recoverability | Outcome comparison on real artifacts and reviewers | Free-form vs kernel artifact review study |
| The kernel can scale across agents and handoffs. | B | Machine-checkable artifacts, visible run traces, a matched internal pickup proxy, a live Codex recoverability pilot showing stronger downstream field recovery, and first replication/continuation smokes that preserve the same general pattern | Multi-operator pickup data across models and humans | Handoff pickup experiment |

## What Is Still Unproven

These are important claims, but they should not be stated as established fact
yet.

| Claim | Grade | Why It Is Not Yet Proven | What Would Prove It |
| --- | --- | --- | --- |
| Kernel use improves downstream project outcomes. | D | No controlled comparison yet between kernel and non-kernel workflows | Comparative study over real tasks with outcome scoring |
| Kernel-aware agents produce better work than agents without kernel structure. | D | No A/B benchmark on identical prompts and acceptance criteria | Agent benchmark across matched tasks |
| Kernel warnings correlate with later rework or quality failures. | D | No operational data collection yet | Longitudinal study on soft-mode warnings vs later edits |
| The current class set is close to optimal. | D | No competing class-model comparison or pruning study | Corpus analysis plus ablation tests |
| The kernel is equally suitable across software, research, ops, and writing domains. | C | Small cross-domain corpus fit is good, but no broad real-project or reviewer evidence yet | Cross-domain corpus and reviewer study |

## Research Questions That Matter Most

If we want to move from “technically valid” to “research-grade validated,” the
highest-value questions are:

1. Does the kernel reduce ambiguity relative to free-form project artifacts?
2. Does the kernel improve handoff pickup quality for humans and agents?
3. Does the kernel improve downstream implementation or review success?
4. Is the typed class model actually better than a simpler generic checklist?
5. Where does the current class set fail across real project domains?

## Recommended Public Wording Right Now

These are safe claims now:

- ORP ships a typed reasoning-kernel artifact layer.
- ORP can scaffold, validate, and gate promotable kernel artifacts.
- ORP supports hard and soft promotion semantics for kernel validation.
- ORP includes repeatable benchmark evidence for the current implementation.

These should still be framed as goals or hypotheses:

- the kernel improves project outcomes
- the kernel is superior to other artifact-structuring approaches
- the current class set is the right final ontology

## Bottom Line

The kernel is sealed for `v0.1` as an implementation and protocol surface.

Its internal validity is now much stronger than a simple happy-path release:

- schema and validator rules align directly
- every required field is exercised through ablation
- equivalent YAML and JSON artifacts behave the same
- adversarial near-miss artifacts are rejected
- a small cross-domain corpus fits the current class set
- a live fresh-agent Codex pilot shows the kernel’s recoverability advantage survives beyond deterministic local scoring
- a `10`-repeat full-corpus replication pilot and two levels of continuation pilot suggest that advantage is reasonably stable and carries into downstream agent continuation behavior

It is not yet sealed as a universally outcome-superior project methodology.

That is a good place to be if we stay explicit about the difference.
