# Erdos Catalog Data Snapshots

This directory stores canonical snapshots produced by:

`scripts/orp-erdos-problems-sync.py`

Files:

- `erdos_problems.all.json`
  - Full catalog snapshot from `https://erdosproblems.com/range/1-end`.
- `erdos_problems.open.json`
  - Problems with `status_bucket=open`.
- `erdos_problems.closed.json`
  - Problems with `status_bucket=closed`.
- `erdos_problems.active.json`
  - Active subset selected by `--active-status` (default `open`).
- `erdos_open_problems.md`
  - Direct-link list of open problems for quick browsing and daily refresh workflows.

Each file includes:

- source URL and source hash
- solve-count metadata reported by the site
- summary counts
- sorted problem records with status/statement/tags/formalization metadata

Refresh command:

```bash
./scripts/orp erdos sync
```

Set active subset to all:

```bash
./scripts/orp erdos sync --active-status all
```

Lookup one or more specific problems and print links:

```bash
./scripts/orp erdos sync --problem-id 857 --problem-id 20
```
