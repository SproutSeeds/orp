# Installing ORP into a repo

ORP is a **template pack**. There is no runtime and nothing to “install” in the dependency sense.

## Option A — Add ORP to an existing repo

1) Copy the folder into your repo (recommended: `orp/`):

```sh
mkdir -p /path/to/your/repo/orp
cp -R /Users/codymitchell/Documents/code/orp/* /path/to/your/repo/orp/
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

## Option B — Start a new project from ORP

1) Create a new project directory and copy ORP in:

```sh
mkdir -p /path/to/new-project
cp -R /Users/codymitchell/Documents/code/orp/* /path/to/new-project/
```

2) Rename/edit `README.md` and `PROTOCOL.md` for your project.

3) Define canonical paths (paper/code/data/etc) in `PROTOCOL.md`.

4) Optional (agent users): integrate ORP into your agent’s primary instruction file:
- Read `AGENT_INTEGRATION.md`
- Or run: `scripts/orp-agent-integrate.sh --sync /path/to/your/agent/instructions.md`

## Optional helper script

If you want a guided copy:

```sh
./scripts/orp-init.sh /path/to/your/repo/orp
```

## Important note: “activation”

ORP becomes real only when your team adopts the procedure:

- claims must be labeled,
- Exact/Verified claims must have verification hooks,
- disagreements are resolved by verification or downgrade,
- and failures are recorded as first-class artifacts.

There is no automated enforcement unless you add it (CI hooks, PR checks, etc.).
