# Formal Conjectures Adapter Notes

Use this adapter when the issue-smashers lane targets
`google-deepmind/formal-conjectures` or a similar formalization-heavy external
repo.

This adapter is intentionally lighter than the mathlib reference today. It
should grow into:

- issue watch and candidate selection
- viability rules around collaborator activity and active PR overlap
- local test/build gates for the target repo
- clean PR-body and disclosure conventions
- feedback hardening when maintainers reveal a missed check

Until the adapter is fully specified, treat the rendered Issue Smashers config as
install-and-adapt and replace placeholder commands with repo-specific commands.
