# ORP Agent Loop

Use this loop when an AI agent is the primary operator of an ORP-enabled repo.

## 1. Discover

- Read `llms.txt`.
- Run `orp about --json`.
- If packs matter, run `orp pack list --json`.
- Read `PROTOCOL.md` before making claims.
- If the task is external OSS contribution workflow or PR governance, read
  `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md` before selecting work.
- For the more detailed external-contribution operator rhythm, then read
  `docs/OSS_CONTRIBUTION_AGENT_LOOP.md`.

## 2. Select Work

- Identify the target profile and canonical artifact paths.
- If a pack-backed workflow needs setup, run:
  - `orp pack install --pack-id <pack-id> --json`
  - or `orp pack fetch --source <git-url> --pack-id <pack-id> --install-target . --json`
- If the workflow depends on public Erdos data, sync it first:
  - `orp erdos sync --problem-id <id> --out-problem-dir <dir> --json`

## 3. Run

- Execute the target workflow:
  - `orp gate run --profile <profile> --json`
- Treat the resulting `run_id` as the handle for follow-on steps.

## 4. Emit Process Metadata

- Write the packet:
  - `orp packet emit --profile <profile> --run-id <run_id> --json`
- Packets are process metadata only. They are not evidence.

## 5. Render Human Review Output

- Write the one-page digest:
  - `orp report summary --run-id <run_id> --json`
- Share the generated `RUN_SUMMARY.md` with humans when a fast review artifact is useful.
- Read `RUN.json.epistemic_status` and packet `evidence_status` before making any claim about what counts as evidence versus starter scaffolding.

## 6. Checkpoint

- Before handoff, compaction, or any meaningful git transition, write a checkpoint:
  - `orp checkpoint create -m "checkpoint note" --json`
- If the current state should exist off-machine before you stop, hand off, or compact:
  - `orp backup -m "backup current work" --json`

## 7. Respect the Boundary

- ORP docs, packets, and summaries are process artifacts.
- Evidence must remain in canonical artifact paths such as code, data, proofs, logs, and papers.
- If verification fails, downgrade the claim immediately and preserve the failed path.

## Minimal Public Example

```sh
orp about --json
orp pack install --pack-id erdos-open-problems --include catalog --json
orp --config orp.erdos-catalog-sync.yml gate run --profile erdos_catalog_sync_active --json
orp --config orp.erdos-catalog-sync.yml packet emit --profile erdos_catalog_sync_active --json
orp --config orp.erdos-catalog-sync.yml report summary --json
```
