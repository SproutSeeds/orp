# ORP Agent Loop

Use this loop when an AI agent is the primary operator of an ORP-enabled repo.

For the longer-horizon model where ORP scans a project's specs, roadmaps, and
codebase, compiles what is autonomous, and runs until a true human gate, also
read:

- `docs/ORP_AUTONOMY_PROJECT_COMPILATION_MODEL.md`

## 1. Discover

- Read `llms.txt`.
- Run `orp about --json`.
- If the task benefits from fresh concepting, tasteful interface work, or
  exploratory reframing, run:
  - `orp mode nudge sleek-minimal-progressive --json`
  - Treat it as an optional lens for deeper, wider, top-down, or rotated perspective shifts.
- If the task feels confusing, too large to hold at once, or likely to benefit
  from more intentional granularity, run:
  - `orp mode breakdown granular-breakdown --json`
  - Optionally follow with `orp mode nudge granular-breakdown --json` if you only need a short reminder card.
  - Treat it as a broad-to-atomic ladder: whole frame, boundary, major lanes, subclaims, atomic obligations, dependency order, durable checklist, and next verification.
- If packs matter, run `orp pack list --json`.
- Read `PROTOCOL.md` before making claims.
- If the repo uses parent/child agent guidance, run `orp agents audit --json` so you know `AGENTS.md` and `CLAUDE.md` are aligned before taking a long-running path.
- If the task is external OSS contribution workflow or PR governance, read
  `docs/EXTERNAL_CONTRIBUTION_GOVERNANCE.md` before selecting work.
- For the more detailed external-contribution operator rhythm, then read
  `docs/OSS_CONTRIBUTION_AGENT_LOOP.md`.

## 2. Select Work

- Identify the target profile and canonical artifact paths.
- If the task depends on the current highest-leverage action slice, refresh ORP's agenda first:
  - `orp agenda refresh --json`
  - `orp agenda refresh-status --json`
  - `orp agenda enable-refreshes --json`
  - `orp agenda enable-refreshes --morning 08:30 --afternoon 13:00 --evening 18:30 --json`
  - `orp agenda disable-refreshes --json`
  - `orp agenda actions --json`
  - `orp agenda suggestions --json`
  - `orp agenda focus --json`
  - `orp agenda set-north-star "Advance the ocular controller and ORP ecosystems" --json`
- If the task depends on umbrella guidance or project-specific agent instructions, inspect or refresh the managed files first:
  - `orp agents root show --json`
  - `orp agents sync --json`
  - `orp agents audit --json`
- If the task depends on an external service, deployment target, dataset platform, or publishing destination, inspect the saved connections first:
  - `orp connections providers --json`
  - `orp connections list --json`
  - `orp connections show <connection> --json`
  - `orp connections add <connection-id> --provider github --auth-secret-alias <alias> --secret-binding releases=<alias> --json`
  - `orp connections add <connection-id> --provider custom --label "Custom Service" --url https://example.org --secret-binding primary=<alias> --json`
  - `orp connections update <connection> --status paused --json`
  - `orp connections sync --json`
  - `orp connections pull --json`
- If the task is shaped by contests, programs, grants, or similar openings, inspect the saved board first:
  - `orp opportunities list --json`
  - `orp opportunities show <board> --json`
  - `orp opportunities focus <board> --limit 5 --json`
  - `orp opportunities add <board> --title "<title>" --kind contest --section <section> --priority high --json`
  - `orp opportunities update <board> <item-id> --status submitted --json`
  - `orp opportunities sync <board> --json`
  - `orp opportunities pull <board> --json`
- If the task needs an API key or token that is not already available, save it first:
  - human interactive path:
    - `orp secrets add --alias <alias> --label "<label>" --provider <provider>`
    - `orp secrets add --alias <alias> --label "<label>" --provider <provider> --kind password --username <login>`
  - agent/script path:
    - `printf '%s' '<secret>' | orp secrets add --alias <alias> --label "<label>" --provider <provider> --value-stdin`
  - convenience path:
    - `orp secrets ensure --alias <alias> --provider <provider> --current-project --json`
- If a pack-backed workflow needs setup, run:
  - `orp pack install --pack-id <pack-id> --json`
  - or `orp pack fetch --source <git-url> --pack-id <pack-id> --install-target . --json`
- If the workflow depends on public Erdos data, sync it first:
  - `orp erdos sync --problem-id <id> --out-problem-dir <dir> --json`
- If the task begins from a public YouTube link, normalize it first:
  - `orp youtube inspect <youtube-url> --json`
  - or `orp youtube inspect <youtube-url> --save --json` when the source artifact should stay with the repo
- If the task depends on understanding another local repo or project directory deeply, synthesize it first:
  - `orp exchange repo synthesize /path/to/source --json`

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

- Before promoting a task/decision/hypothesis/experiment artifact into repo truth, validate its kernel shape:
  - `orp kernel validate <artifact-path> --json`
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
