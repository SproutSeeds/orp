# Generic GitHub Adapter Notes

Use this adapter when you want the Issue Smashers workspace shape before a
repo-specific adapter exists.

The minimum viable setup is:

- choose a target repo and issue lane
- record it in the watchlist and status board
- replace each placeholder command with a real repo-specific command or a test
  stub
- keep the PR body under the workspace analysis directory

This adapter is intentionally simple. It keeps the pack useful for new repos
without pretending generic GitHub etiquette is the same as a mature
repo-specific workflow.
