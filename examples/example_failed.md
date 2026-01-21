# Example Failed Path Record

## Topic
Attempted proof strategy based on assumption A

## Summary
The approach fails because assumption A does not hold in general (counterexample found).

## What was attempted
Tried to derive property P from assumption A using lemma L and case split.

## Why it failed
Counterexample: artifact `analysis/counterexamples/case_001.json` violates lemma precondition.

## Evidence
- `analysis/counterexamples/case_001.json`
- `analysis/notes/attempt_20260120.md`

## What this rules out
Any proof relying on assumption A as a global invariant.

## What might still work (next hook)
Restrict to a narrower class where assumption A holds, or replace A with weaker condition A'.

