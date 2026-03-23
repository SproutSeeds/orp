# ORP Reasoning Kernel Evaluation Plan

This document turns the remaining kernel evidence gaps into concrete next
experiments.

The goal is to upgrade the kernel from:

- technically valid and operationally useful

to:

- comparatively validated against real alternatives and real project outcomes

Supporting references:

- [docs/ORP_REASONING_KERNEL_EVIDENCE_MATRIX.md](/Volumes/Code_2TB/code/orp/docs/ORP_REASONING_KERNEL_EVIDENCE_MATRIX.md)
- [docs/ORP_REASONING_KERNEL_TECHNICAL_VALIDATION.md](/Volumes/Code_2TB/code/orp/docs/ORP_REASONING_KERNEL_TECHNICAL_VALIDATION.md)

## Evaluation Principles

Every kernel evaluation should be:

- comparative, not just descriptive
- cross-domain where possible
- judged by downstream usefulness, not only schema validity
- reproducible and artifact-backed

The main alternatives to compare against are:

1. Free-form artifact writing
2. Generic checklist artifact writing
3. ORP typed kernel artifact writing

## Experiment 1: Artifact Clarity And Completeness

### Question

Does the ORP kernel produce more complete and legible promotable artifacts than
free-form writing or a generic checklist?

### Setup

- Select 20 prompts spread across:
  - software
  - research
  - product/design
  - operations
  - writing/knowledge work
- For each prompt, produce three artifact versions:
  - free-form
  - generic checklist
  - ORP kernel

### Scoring

Blind-review each artifact against:

- artifact type clarity
- boundary clarity
- constraint clarity
- evaluation clarity
- handoff readiness
- ambiguity remaining

### Primary metric

- mean reviewer score by condition

### Success criterion

- kernel condition beats free-form and generic checklist on at least four of
  six scoring dimensions

## Experiment 2: Handoff Pickup Study

### Question

Does the ORP kernel improve pickup quality for another human or agent?

### Setup

- Use matched artifacts from Experiment 1
- Give a second operator one artifact at a time and ask them to:
  - explain the task
  - state the constraints
  - identify success criteria
  - identify next action

### Scoring

- time to correct interpretation
- interpretation accuracy
- number of clarifying questions required

### Primary metric

- successful pickup rate without clarification

### Success criterion

- kernel artifacts reduce clarifying questions and increase correct pickup rate

## Experiment 3: Downstream Execution Quality

### Question

Does kernel-structured promotion improve downstream execution or review
success?

### Setup

- Choose a fixed set of implementation or research tasks
- Feed matched task artifacts to agents or operators
- Compare execution using:
  - free-form task definition
  - generic checklist task definition
  - kernel task artifact

### Scoring

- completion rate
- rework rate
- reviewer acceptance
- alignment with stated constraints
- mismatch between claimed and delivered outcome

### Primary metric

- accepted completion rate with minimal rework

### Success criterion

- kernel condition improves acceptance or reduces rework materially

## Experiment 4: Cross-Domain Corpus Fit

### Question

Do the current kernel artifact classes fit real project work across domains?

### Setup

- Collect 50 to 100 real artifacts across:
  - software
  - research
  - design/product
  - ops/reliability
  - writing/editorial
- Map each artifact into the current kernel classes

### Scoring

- clean fit
- awkward fit
- no fit
- missing field pressure
- repeated need for new field or class

### Primary metric

- percent of artifacts that map cleanly without schema strain

### Success criterion

- at least 80 percent clean fit across the corpus

## Experiment 5: Operational Warning Value

### Question

Do soft-mode kernel warnings predict later rework or low-quality promotion?

### Setup

- instrument real ORP repos using soft-mode kernel gates
- log:
  - warning presence
  - later edits to the same artifact
  - eventual hard-mode pass/fail
  - downstream rework indicators

### Primary metric

- correlation between early warnings and later rework

### Success criterion

- warnings show predictive value strong enough to justify continued soft-mode
  emphasis

## Suggested Order

The best order is:

1. Artifact clarity and completeness
2. Handoff pickup
3. Cross-domain corpus fit
4. Downstream execution quality
5. Operational warning value

That sequence gives the fastest evidence on whether the kernel is genuinely
useful before investing in longer operational studies.

## Minimal Evidence Package To Upgrade v0.1 Claims

If we want to move from “strong implementation” to “serious comparative
validation,” the smallest next package is:

1. a 20-prompt comparative artifact study
2. a pickup study on those same artifacts
3. a cross-domain corpus fit table

That would be enough to substantially strengthen the kernel’s public claims.

## Bottom Line

The kernel is already technically real and operationally validated.

What remains is comparative evidence:

- better than free-form?
- better than a generic checklist?
- good across real domains?
- useful in real handoffs?

This plan defines how to answer those questions cleanly.
