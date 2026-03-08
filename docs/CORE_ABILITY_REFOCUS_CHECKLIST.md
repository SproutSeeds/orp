# ORP Core Ability Refocus Checklist

This checklist tracks the shift from a pack-first public story to an
ability-first ORP CLI.

## Product Shape

- [x] Discovery is presented as a built-in ORP ability.
- [x] Bare `orp` opens a home screen instead of only failing on missing
  subcommands.
- [x] Collaboration is presented as a built-in ORP ability.
- [x] `erdos` remains a domain-specific ORP ability.
- [x] Packs remain available for advanced/internal use.
- [ ] The released npm package includes the new collaboration-first surface.

## Default User Story

- [x] `orp discover profile init` scaffolds a portable discovery profile.
- [x] `orp discover github scan` ranks repo, issue, and people opportunities
  inside a GitHub owner space.
- [x] `orp collaborate init` is the fastest collaboration setup path.
- [x] `orp collaborate workflows` exposes built-in collaboration workflows.
- [x] `orp collaborate gates --workflow <id>` shows the gate chain before a run.
- [x] `orp collaborate run --workflow <id>` runs the built-in collaboration
  workflow.
- [x] README points users at `orp collaborate ...` first.
- [x] INSTALL points users at `orp collaborate ...` first.
- [ ] Add a collaboration-specific summary/example doc if real users still need
  more onboarding.

## Advanced / Internal Story

- [x] `pack` is still available.
- [x] Home screen labels packs as advanced bundles.
- [x] Pack docs remain available for ORP maintainers and advanced users.
- [ ] Decide later whether `external-pr-governance` and `issue-smashers` stay
  as visible internal names or become more hidden implementation details.

## Machine-Readable Discovery

- [x] `orp home --json` exists.
- [x] `orp about --json` exists.
- [x] `orp about --json` exposes commands.
- [x] `orp about --json` exposes abilities.
- [x] `orp discover ... --json` exists.
- [x] `orp collaborate workflows --json` exists.
- [x] `orp collaborate gates --json` exists.
- [ ] Add a machine-readable examples surface if agents still need more direct
  task discovery.

## Domain Shape

- [x] Collaboration is part of ORP core UX.
- [x] Erdos stays separate.
- [ ] Decide whether `erdos` should gain a matching `workflows` / `run`
  surface for symmetry with `collaborate`.

## Release Checklist

- [ ] Commit the collaboration-first refocus.
- [ ] Release the next npm version.
- [ ] Validate the collaboration-first story from a clean published install.
