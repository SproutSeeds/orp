# ORP Knowledge Exchange

`orp exchange repo synthesize` is ORP's deeper repository-synthesis surface.

It is different from `orp discover`:

- `discover` is breadth-first scanning and ranking
- `exchange` is depth-first synthesis and transfer mapping

The goal is to turn another codebase or project directory into structured
knowledge you can reuse inside the current repo.

## Why this exists

Agents and humans often do not just need to *find* promising repositories.
They need to understand:

- what a source repo is really doing
- how it is organized
- what patterns are reusable
- what its workflows imply
- and how it can help the current project

That calls for a more harnessed, repo-native artifact flow than a default scan.

## Command

```bash
orp exchange repo synthesize /path/to/source --json
```

If the source is a plain local directory and you want ORP to bootstrap git
tracking there first:

```bash
orp exchange repo synthesize /path/to/source --allow-git-init --json
```

Remote git references are also accepted:

```bash
orp exchange repo synthesize owner/repo --json
orp exchange repo synthesize https://github.com/owner/repo.git --json
```

## Source modes

ORP currently supports:

- `local_git`
- `local_directory`
- `remote_git`

For local non-git directories, ORP will only mutate the source when
`--allow-git-init` is explicitly provided.

## Artifacts

Each exchange run writes:

- `orp/exchange/<exchange_id>/EXCHANGE.json`
- `orp/exchange/<exchange_id>/EXCHANGE_SUMMARY.md`
- `orp/exchange/<exchange_id>/TRANSFER_MAP.md`

These artifacts are synthesis aids, not evidence by themselves.

## What the exchange focuses on

The first slice is intentionally structured around:

- source identity and mode
- inventory of docs, tests, manifests, and languages
- relationship to the current project
- shared languages / manifests / top-level structure
- suggested focus areas for deeper human or agent analysis
- transfer mapping and project momentum

The aim is to answer:

- what does this repo know?
- how is it organized?
- what can transfer?
- how does it help us right now?

not just:

- what tasks should we do next?

## Important boundary

Knowledge exchange artifacts are process artifacts.

They help ORP structure understanding and transfer, but they do not replace
canonical evidence in the source or host repository.
