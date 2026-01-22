# Choosing (or Ignoring) Instruments

> *Instruments are available, not required.*

This document explains **when to use an instrument**, **when not to**, and shows a small example of both paths. The goal is clarity without pressure.

---

## The Short Rule

You do **not** need an instrument to use ORP.

ORP functions fully with:
- clear claims
- explicit verification hooks
- honest downgrade or failure recording

Instruments are optional tools for **upstream framing**, nothing more.

---

## When an Instrument Helps

Consider using an instrument if:

- the problem feels large, vague, or multidimensional
- you are unsure what to measure first
- competing intuitions are pulling in different directions
- you want to generate *predictions* before making claims

An instrument helps you choose *where to stand* before you speak.

---

## When to Ignore Instruments

It is often better to skip instruments when:

- the claim is narrow and well-defined
- the verification method is obvious
- you are extending known work incrementally
- speed matters more than framing

Skipping instruments is not a shortcut.
It is a valid choice.

---

## How to Choose an Instrument (If You Do)

Ask one simple question:

> *What kind of uncertainty am I facing?*

Then choose accordingly:

- **Orbit Lens** → uncertainty about *stability, balance, or persistence*
- **Compression Lens** → uncertainty about *what really matters*
- **Adversarial Lens** → uncertainty about *hidden failure modes*

You may use more than one — or none.

---

## Tiny Example A: Using an Instrument

**Context:** Studying a large combinatorial family suspected to be extremal.

Before making a claim, you apply the **Orbit Lens**:
- forces: structure vs entropy
- distance knob: density of the family
- invariant: collision count under projection

**Result:**
You predict that beyond a certain density, collisions must explode.

**Then:**
You write a claim in ORP:
> *Claim:* Any family exceeding density X contains a forbidden configuration.
>
> *Instrument used:* Orbit Lens (density regime)
>
> *Verification:* SAT search + counting argument

Verification proceeds normally.
The instrument does not affect acceptance.

---

## Tiny Example B: Ignoring Instruments

**Context:** Checking whether a specific bound holds for n ≤ 10.

You already know:
- what to compute
- how to verify it

You write a claim directly:
> *Claim:* Bound Y holds for all n ≤ 10.
>
> *Verification:* Exhaustive computation

No instrument is referenced.
This is fully valid ORP usage.

---

## Important Boundary

Instruments:
- influence *what questions are asked*
- never influence *whether a claim is accepted*

Verification is blind to framing.

---

## Final Reassurance

If you:
- never use an instrument, ORP still works
- use one instrument, ORP still works
- invent a new instrument, ORP still works

Instruments are an invitation, not an obligation.

*Use them when they help. Ignore them when they don’t.*

