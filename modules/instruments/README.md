# ORP Instruments Framework

> *Truth does not emerge from a single lens. It emerges from well-governed interaction between lenses.*

This document defines **what an Instrument is**, **how Instruments integrate with ORP**, and **how anyone can create one**. Orbit is the first instrument — not the only one.

---

## 1) What We Are Building (Plainly)

ORP is a protocol for **truth under pressure**.

It governs:
- how claims are stated,
- how verification is attached,
- how failures are recorded,
- how disagreement resolves via evidence, not argument.

**Instruments live upstream of this.**

An Instrument is a *framing tool* that helps generate better questions, sharper claims, and testable predictions *before* ORP governance begins.

ORP does **not** judge instruments.
ORP only governs what happens *after* an instrument is used.

---

## 2) Definition: ORP Instrument

An **ORP Instrument** is a modular, process-only artifact that:

- operates **pre-claim**
- introduces a **reference frame** for inquiry
- identifies **forces, parameters, and invariants**
- produces **testable observations or predictions**
- never contains evidence or conclusions

An instrument may influence *what claims are made*, but never *how they are verified*.

---

## 3) Non-Negotiable Constraints (Why This Works)

Every ORP Instrument must satisfy:

1. **Process-only**  
   No data, no results, no conclusions.

2. **Non-authoritative**  
   Instruments do not override claims or verification.

3. **Composable**  
   Multiple instruments may be applied to the same inquiry.

4. **Discardable**  
   Instruments may be abandoned without loss of truth.

5. **Prediction-generating**  
   Must lead to statements that can be verified or falsified downstream.

These constraints prevent ideology, lock-in, or protocol drift.

---

## 4) The Instrument Contract (Template Spec)

Every instrument should answer the following:

### A) Purpose
What kind of systems or questions does this instrument help with?

### B) Forces
What competing pressures does this instrument highlight?

### C) Distance / Control Parameters
What knobs can be tuned?

### D) Stability Invariants
What quantities indicate persistence or health?

### E) Failure Signals
What patterns indicate collapse or invalid framing?

### F) Reframing Moves
How does this instrument change perspective?

### G) Observation Test
What would count as a *new observation* using this instrument?

---

## 5) Orbit Lens (Instrument #1)

**Focus:** balance, gradients, persistence, stability under motion.

- Forces: structure vs entropy
- Distance: density, degree, step size, conditioning depth
- Invariants: bounded collisions, energy, entropy under constraint
- Failure: collapse into rigidity or noise

Orbit establishes the pattern. It is not canonical.

---

## 6) Future Instruments (Examples, Not Prescriptions)

- **Compression Lens** – invariants under minimal description
- **Adversarial Lens** – worst-case stress and counterexamples
- **Evolution Lens** – mutation, selection, path dependence
- **Energy Lens** – cost, dissipation, potential functions
- **Temporal Lens** – time, accumulation, irreversible steps

Each instrument must obey the same contract.

---

## 7) Integration with ORP Workflow

Instruments are optional inputs to claims.

**CLAIM.md hook (optional):**

> **Instrument(s) used:**  
> (e.g. Orbit Lens, Compression Lens, Adversarial Lens)
>
> **Instrument parameters explored (if any):**  
> (brief — distance knob, regime, or slice examined)

Claims may reference one or more instruments, but verification ignores the instrument and tests the claim directly.

Failed claims remain valuable regardless of instrument choice.

---

## 8) Where Instruments Live

Recommended structure:

- `modules/instruments/ORBIT/`
- `modules/instruments/<NAME>/`

Each instrument contains:
- `README.md` (definition + philosophy)
- `TEMPLATE.md` (fillable version)

ORP core remains unchanged.

---

## 9) Why This Matters

Disagreements move upstream.

Instead of arguing outcomes, researchers compare:
- frames
- invariants
- predictions

Truth advances by **instrument performance**, not persuasion.

---

## Closing

ORP governs truth.
Instruments explore reality.

No single lens owns understanding.
But every lens must answer to verification.

*Orbit is the first instrument.
It will not be the last.*

