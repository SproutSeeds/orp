# Installing ORP into a repo

ORP supports both:

- docs-first template adoption (`PROTOCOL.md`, templates), and
- optional runtime CLI usage (`orp`) for gates/packets/packs.

The default runtime story is now:

- `orp config ...`, `orp storage ...`, `orp workspace ...`, and
  `orp checkpoint ...` for the local-first operating layer
- `orp secrets ...` for machine-local macOS Keychain credentials
- `orp codex context ...` for an optional read-only, prompt-preserving context packet
- `orp auth ...` and `orp workspaces ...` for optional hosted metadata
- `orp discover ...` for profile-based GitHub scanning and opportunity selection
- `orp collaborate ...` for repository collaboration
- `orp erdos ...` for Erdos-specific workflows
- `orp pack ...` only when you need advanced/internal template install behavior

Optional global CLI install:

```sh
npm i -g open-research-protocol
orp
orp -h
orp about --json
```

CLI prerequisites:

- Python 3 on `PATH`
- `PyYAML` (`python3 -m pip install pyyaml`)

Agent-friendly discovery surfaces:

- bare `orp` for the CLI home screen with packs, repo status, and quick actions
- `orp home --json` for machine-readable landing context
- `orp config show --json` for the validated local configuration
- `orp storage report --json` for ORP-owned storage only
- `orp workspace create main` for a local recovery ledger
- `orp codex context --allow-once --prompt "my exact prompt"` for bounded,
  offline repository context
- `orp auth login` for hosted workspace login
- `orp whoami --json` for the current hosted identity
- `orp workspaces list --json` for hosted metadata listing
- `orp workspace sync <selector> --allow <field> --json` for a reviewed,
  dry-run hosted projection
- `orp discover profile init --json` for a portable discovery profile scaffold
- `orp discover github scan --profile orp.profile.default.json --json` for ranked GitHub repo/issue/person recommendations
- `orp collaborate init` for immediate collaboration scaffolding
- `orp collaborate workflows --json` for built-in collaboration workflow discovery
- `orp collaborate gates --workflow full_flow --json` for the exact gate chain
- `llms.txt` for quick repo/package discovery
- `orp about --json` for machine-readable capabilities, schemas, artifacts, and bundled packs
- `docs/DISCOVER.md` for the discovery profile model and scan artifacts
- `docs/AGENT_LOOP.md` for the intended agent operating rhythm
- `orp pack list --json` for machine-readable bundled pack inventory

Fastest collaboration setup in a fresh repo:

```sh
orp collaborate init
orp collaborate workflows --json
orp collaborate run --workflow full_flow --json
```

This uses ORP's built-in collaboration ability. You do not need to think in
terms of separate governance packs for the default collaboration path.

Fastest local workspace loop from the published ORP binary:

```sh
orp init
orp config validate --json
orp storage report --json
orp workspace create main
orp workspace add-tab main --here --title "current project"
orp checkpoint inspect --json
orp codex context --allow-once --prompt "my exact prompt"
```

This loop is offline and needs no account. For optional hosted visibility, run
`orp auth login`, preview
`orp workspace sync <selector> --allow tabs.title --json`, and apply only with
the exact reviewed `snapshot_id`.

To choose where collaboration should start, scaffold a profile first:

```sh
orp discover profile init --owner SproutSeeds --owner-type org
orp discover github scan --profile orp.profile.default.json --json
```

## Option 0 — Smoke-test ORP in a fresh directory

This is the fastest way to verify the published CLI before integrating ORP into a real repo.

```sh
mkdir test-orp && cd test-orp
npm i -g open-research-protocol
orp init
orp config validate --json
orp storage report --json
orp workspace create main
orp workspace add-tab main --here --title "smoke test"
orp codex context --allow-once --prompt "verify fresh-user onboarding"
orp gate run --profile default
orp packet emit --profile default
orp report summary
find orp -maxdepth 3 -type f | sort
```

Expected outcomes:

- `orp.yml` is created in the working directory
- local configuration validates and the storage report stays within ORP-owned roots
- the Codex context result preserves the supplied prompt and stays at or below 2,048 bytes
- `orp/artifacts/<run_id>/RUN.json` is written after `gate run`
- `orp/packets/*.json` and `orp/packets/*.md` are written after `packet emit`
- `orp/artifacts/<run_id>/RUN_SUMMARY.md` is written after `report summary`

Then validate a real public pack flow:

```sh
orp pack list
orp pack install --pack-id erdos-open-problems --include catalog
orp --config orp.erdos-catalog-sync.yml gate run --profile erdos_catalog_sync_active
orp report summary
```

This exercises the published pack install path plus a real pack-backed gate run.

## Option A — Add ORP to an existing repo

1) Copy the folder into your repo (recommended: `orp/`):

```sh
mkdir -p /path/to/your/repo/orp
cp -R /path/to/orp/* /path/to/your/repo/orp/
```

2) Link it from your repo `README.md` (example):

```md
## Protocol
This project follows ORP: `orp/PROTOCOL.md`.
```

3) Edit `orp/PROTOCOL.md` and fill in the **Canonical Paths** section for your repo. This is required for correctness.

4) Start using templates for all claims/verifications:
- `orp/templates/CLAIM.md`
- `orp/templates/VERIFICATION_RECORD.md`
- `orp/templates/FAILED_TOPIC.md`

5) Optional (agent users): integrate ORP into your agent’s primary instruction file:
- Read `orp/AGENT_INTEGRATION.md`
- Or run: `orp/scripts/orp-agent-integrate.sh --sync /path/to/your/agent/instructions.md`
   - Optional checkpoint tool (writes a process-only handoff/compaction log): `orp/scripts/orp-checkpoint.sh --sync --agent-file /path/to/your/agent/instructions.md "checkpoint note"`

## Option B — Start a new project from ORP

1) Create a new project directory and copy ORP in:

```sh
mkdir -p /path/to/new-project
cp -R /path/to/orp/* /path/to/new-project/
```

2) Rename/edit `README.md` and `PROTOCOL.md` for your project.

3) Define canonical paths (paper/code/data/etc) in `PROTOCOL.md`.

4) Optional (agent users): integrate ORP into your agent’s primary instruction file:
- Read `AGENT_INTEGRATION.md`
- Or run: `scripts/orp-agent-integrate.sh --sync /path/to/your/agent/instructions.md`
   - Optional checkpoint tool (writes a process-only handoff/compaction log): `scripts/orp-checkpoint.sh --sync --agent-file /path/to/your/agent/instructions.md "checkpoint note"`

## Optional helper script

If you want a guided copy:

```sh
./scripts/orp-init.sh /path/to/your/repo/orp
```

If you are evaluating ORP for the first time, prefer Option 0 before copying files into a larger repo.

## Important note: “activation”

ORP becomes real only when your team adopts the procedure:

- claims must be labeled,
- Exact/Verified claims must have verification hooks,
- disagreements are resolved by verification or downgrade,
- and failures are recorded as first-class artifacts.

There is no automated enforcement unless you add it (CI hooks, PR checks, etc.).
