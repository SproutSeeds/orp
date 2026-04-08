# Start Here

Use this guide when you are new to ORP and want the shortest correct path from "fresh repo" to "agent and repo are operating in lockstep."

The design goal is simple:

- local-first by default
- hosted sync is optional
- the workspace ledger remembers where ongoing work lives
- `AGENTS.md` and `CLAUDE.md` keep umbrella and child guidance aligned
- the agenda keeps two ranked lists for what matters now and what to expand next
- the connections registry remembers which services, accounts, and secret aliases power your tooling
- opportunity boards remember contests, programs, grants, and similar openings
- repo governance keeps work intentional
- the agent uses ORP as its operating lens, not as an afterthought

## Core Rule

Do not let ORP process scaffolding masquerade as evidence or repository truth.

ORP is there to:

- keep the workspace ledger honest
- keep connection identities and auth references organized
- keep repo governance explicit
- keep secrets and continuity usable
- help the agent stay aligned

But canonical evidence still lives in the repo's real artifacts: code, data, proofs, papers, logs, and outputs.

## Start In 60 Seconds

Install:

```bash
npm i -g open-research-protocol
```

If you already know you want the standard local-first ORP loop in a repo, the fastest path is:

```bash
orp home
orp agents root set /absolute/path/to/projects
orp init
orp agents audit
orp workspace create main-cody-1
orp workspace tabs main
orp agenda refresh --json
orp agenda focus
orp connections providers
orp connections add github-main --provider github --label "GitHub Main" --auth-secret-alias github-main
orp connections add huggingface-main --provider huggingface --label "Hugging Face" --secret-binding primary=hf-main --secret-binding publish=hf-publish
orp connections add my-science-portal --provider custom --label "My Science Portal" --url https://example.org --secret-binding primary=my-science-token
orp opportunities create main-opportunities --label "Main Opportunities"
orp opportunities list
orp secrets ensure --alias openai-primary --provider openai --current-project --json
orp status --json
orp checkpoint create -m "capture loop state" --json
```

That gets you:

- the discovery screen
- an optional umbrella projects root for parent/child agent guidance
- repo governance initialized
- repo-level AGENTS.md and CLAUDE.md scaffolded or refreshed
- a local workspace ledger
- the main recovery surface
- a local operating agenda
- a saved connection record for a real integration
- a separate opportunities board for contests/programs/grants
- secrets setup
- a clean repo-governance read
- a first intentional checkpoint

## Beginner Flow

This is the zero-assumption path for a new user.

### 1. Install the CLI once

```bash
npm i -g open-research-protocol
```

This gives you a global `orp` command.

### 2. Start with the home screen

```bash
orp home
```

Use `orp home` when you want the main operator screen:

- what ORP is
- what the current daily loop is
- what command families exist
- what discovery docs to read next

### 3. Initialize the repo

From the repo root:

```bash
orp init
```

`orp init` makes the repo ORP-governed. It creates the starter config/runtime scaffolding, seeds the handoff and checkpoint log, and records the repo's governance state.

More concretely, `orp init` does these jobs:

- creates a git repo if one does not already exist
- creates `orp.yml` if it is missing
- creates the ORP runtime directories under `orp/`
- seeds:
  - `orp/HANDOFF.md`
  - `orp/checkpoints/CHECKPOINT_LOG.md`
  - `analysis/orp.kernel.task.yml`
- scaffolds or updates:
  - `AGENTS.md`
  - `CLAUDE.md`
- writes governance metadata like:
  - `orp/governance.json`
  - `orp/agent-policy.json`
  - `orp/state.json`

So `orp init` is not "start doing the work." It is "make this repo legible and governable for humans and agents."

The important subtlety is that ORP does not own those agent files outright:

- if `AGENTS.md` or `CLAUDE.md` already exists, ORP preserves the human-written content and only refreshes its own marked blocks
- if the file is missing, ORP scaffolds it with a sensible starter structure
- the ORP-managed blocks can point a child repo back to a higher-level umbrella projects root when you configure one

If you keep many repos under one shared parent directory, set that umbrella root once:

```bash
orp agents root set /absolute/path/to/projects
```

Then initialize or resync a child repo with the parent explicitly linked:

```bash
orp init --projects-root /absolute/path/to/projects
orp agents audit
```

If you want to refresh the files later without rerunning the full repo bootstrap:

```bash
orp agents sync
```

After that, check the repo state:

```bash
orp status --json
```

### 4. Create the workspace ledger

This is the local-first memory layer for ongoing work.

```bash
orp workspace create mac-main --machine-label "Mac Studio"
orp workspace list
orp workspace tabs main
```

You do not need a hosted account for this. The workspace ledger works locally out of the box.

The important idea is:

- the workspace ledger is not a GUI tab manager
- it is the saved memory of where work lives
- it stores machine-specific paths plus exact resumable command lines
- it can also store portable remote repo URLs and bootstrap commands for another machine
- it is the crash-recovery layer for you and the agent

This is separate from the agent-instruction hierarchy:

- `workspace` remembers concrete working continuity like paths and resume commands
- `agents` keeps the higher-level parent/child guidance files aligned

### 5. Save ongoing tabs and sessions

If you want ORP to remember an ongoing repo path plus a resumable session, add it explicitly:

```bash
orp workspace add-tab main --path /absolute/path/to/project --remote-url git@github.com:org/project.git --bootstrap-command "npm install" --resume-command "codex resume <session-id>"
```

For Claude:

```bash
orp workspace add-tab main --path /absolute/path/to/project --resume-tool claude --resume-session-id <session-id>
```

To inspect what is saved:

```bash
orp workspace tabs main
```

The `resume:` line is the exact copyable recovery command:

```text
resume: cd '/absolute/path/to/project' && codex resume <session-id>
```

or:

```text
resume: cd '/absolute/path/to/project' && claude --resume <session-id>
```

If you also save a remote repo and bootstrap command, `orp workspace tabs main` will show extra lines like:

```text
remote: git@github.com:org/project.git [branch main]
clone: git clone 'git@github.com:org/project.git' 'project'
bootstrap: npm install
setup: git clone 'git@github.com:org/project.git' 'project' && cd 'project' && npm install
```

That is the portable part a second machine can use. The local `path` and the local `resume:` line still belong to the machine that saved the session.

To remove something from the saved ledger:

```bash
orp workspace remove-tab main --path /absolute/path/to/project
```

So the `workspace` lane is really:

- `create` a ledger
- `add-tab` to remember a path/session and, optionally, the remote/bootstrap details needed on another rig
- `remove-tab` to prune old work
- `tabs` to inspect exact saved recovery commands
- `list` to see all saved workspaces

### 6. Create one agenda lane

This is the separate memory lane for ranked action pressure and ranked suggestions. It is intentionally distinct from `workspace`, `connections`, and `opportunities`.

Run one refresh:

```bash
orp agenda refresh --json
```

Check whether recurring refreshes are enabled:

```bash
orp agenda refresh-status --json
```

If you want ORP to refresh the agenda on a schedule, you must opt in explicitly. Nothing starts making recurring Codex calls until you enable it yourself. The starter preset is morning, afternoon, and evening:

```bash
orp agenda enable-refreshes --json
```

If you want your own times instead, override them directly:

```bash
orp agenda enable-refreshes --morning 08:30 --afternoon 13:00 --evening 18:30 --json
```

Disable the recurring refreshes any time:

```bash
orp agenda disable-refreshes --json
```

Inspect the saved outputs:

```bash
orp agenda actions
orp agenda suggestions
orp agenda focus
```

If you want ORP to optimize around one explicit north star instead of inferring it from current context:

```bash
orp agenda set-north-star "Advance the ocular controller and ORP ecosystems"
```

The practical model is:

- `agenda refresh` is a real Codex reasoning pass
- it reads current main-workspace context, GitHub pressure, opportunities, and connections
- it writes two saved ranked lists locally:
  - `actions`
  - `suggestions`
- recurring agenda refreshes are disabled by default until the user enables them
- the built-in default schedule is morning, afternoon, and evening, but user-chosen times win
- `focus` is the fastest operator and agent recall surface

### 7. Create one connections registry

This is the separate memory lane for service accounts, data sources, deploy targets, databases, archives, and public research destinations. It is intentionally distinct from both `workspace` and `secrets`.

Inspect the built-in provider templates first if they help:

```bash
orp connections providers
```

Add one saved connection that references a saved ORP secret alias:

```bash
orp connections add github-main --provider github --label "GitHub Main" --account cody --organization sproutseeds --auth-secret-alias github-main
```

If the same service needs multiple tokens, keep them together under named secret bindings:

```bash
orp connections add huggingface-main --provider huggingface --label "Hugging Face" --account cody --secret-binding primary=hf-main --secret-binding publish=hf-publish --secret-binding inference=hf-inference
```

If ORP has never seen the service before, use `custom` and keep going:

```bash
orp connections add my-science-portal --provider custom --label "My Science Portal" --url https://example.org --secret-binding primary=my-science-token
```

Inspect or update it later:

```bash
orp connections show github-main
orp connections list
orp connections update github-main --status paused
```

Mirror the same registry to hosted ORP when you want the same setup on another machine:

```bash
orp auth login
orp connections sync --json
orp connections pull --json
```

The important idea is:

- `secrets` stores the actual sensitive value
- `connections` stores the provider/account/capability record and which secret alias or named secret bindings power it
- `workspace` stores where current work lives
- built-in providers are optional; `custom` is the straight path for anything new or specialized

### 8. Create one opportunities board

This is the separate memory lane for contests, programs, grants, fellowships, and similar openings. It is intentionally distinct from `workspace`.

Create one board:

```bash
orp opportunities create main-opportunities --label "Main Opportunities"
```

Add one tracked item:

```bash
orp opportunities add main-opportunities --title "vision-prize" --kind contest --section ocular-longevity --priority high --url https://example.com/vision-prize
```

Inspect the board:

```bash
orp opportunities show main-opportunities
orp opportunities focus main-opportunities --limit 5
orp opportunities list
```

Update or remove one item:

```bash
orp opportunities update main-opportunities vision-prize --status submitted
orp opportunities remove main-opportunities vision-prize
```

If you authenticate later and want the same board on another machine, mirror it:

```bash
orp auth login
orp opportunities sync main-opportunities --json
orp opportunities pull main-opportunities --json
```

The important idea is:

- `workspace` remembers where active sessions live
- `opportunities` remembers what external openings matter
- agents can read and update both, but they should stay separate
- local-first is the default; hosted sync is optional

### 9. Set up secrets

Today, secrets are the one part of ORP that still starts from the hosted ORP account layer. So before you save or resolve secrets, log in:

```bash
orp auth login
```

After that, think about secrets in two separate user flows:

- human operator flow
- agent/script flow

#### Human operator flow

If you are at the terminal and want to save a new key manually, use:

```bash
orp secrets add --alias openai-primary --label "OpenAI Primary" --provider openai
```

ORP then prompts:

```text
Secret value:
```

That is where you paste the real key.

After that, you can inspect and reuse it:

```bash
orp secrets list
orp secrets show openai-primary
orp secrets resolve openai-primary --reveal
```

That is the clearest beginner flow:

1. log in
2. add the key
3. paste the value when prompted
4. list or show it later
5. resolve it when you need to use it

#### Agent or script flow

If an agent or script needs to save a key non-interactively, use stdin:

```bash
printf '%s' 'sk-...' | orp secrets add --alias openai-primary --label "OpenAI Primary" --provider openai --value-stdin
```

This is the safe automation path because the secret value is not typed into the command line flags directly.

#### Convenience flow: `ensure`

If the repo or agent needs an API key and you want ORP to handle both "already exists" and "missing" cases, use:

```bash
orp secrets ensure --alias openai-primary --provider openai --current-project
```

In plain English, that means:

```text
Make sure this project has an OpenAI key available to it.
```

The important thing to understand is:

- this command does not contain the key itself
- it is a lookup-or-create command
- the actual key is either already saved, or ORP will ask you for it

`ensure` is the beginner-friendly path because it handles both cases:

- if the secret already exists in ORP, reuse it
- if it does not exist yet, create it
- if `--current-project` is present, bind it to the repo you are in now

If the secret does not exist yet, ORP will ask you for the secret value securely unless you provide it explicitly with `--value` or `--value-stdin`.

That means the common beginner flow is simply:

1. run:
   ```bash
   orp secrets ensure --alias openai-primary --provider openai --current-project
   ```
2. if ORP already knows the key, it reuses it
3. if ORP does not know the key yet, it prompts:
   ```text
   Secret value:
   ```
4. paste the real key there

So the easiest path for a new user is still:

```bash
orp secrets ensure --alias openai-primary --provider openai --current-project
```

If ORP already knows that key, it reuses it.
If ORP does not know that key yet, it prompts for the value and then saves it.

If you want to be explicit and add a brand-new key first, you can also do it in two steps:

```bash
orp secrets add --alias openai-primary --provider openai --current-project
orp secrets ensure --alias openai-primary --provider openai --current-project
```

The mental model is:

- `add` = I know this is a brand-new secret
- `ensure` = use the existing one, or create it if missing
- `list` = show me what is saved
- `show` = show me one saved secret record
- `resolve` = give me the actual value so I can use it now
- `sync-keychain` = keep a secure local Mac copy too

You can ignore `--env-var-name` at first.
It is only optional metadata like `OPENAI_API_KEY`.
It is not the secret value itself.

For example:

```bash
orp secrets resolve --provider openai --current-project --reveal
```

If you want a local secure copy on macOS too:

```bash
orp secrets sync-keychain openai-primary --json
```

The right mental model is:

- hosted ORP secret inventory can be the canonical source of truth
- local Keychain can be the secure local cache
- `ensure` means "reuse it if it exists, create it if it doesn't, and bind it if needed"
- if the key is missing and you did not pass a value, ORP prompts you for it
- `add` is the clearest first command for a brand-new human user

### 10. Start working safely

ORP's default repo-governance loop is:

```bash
orp branch start work/<topic> --json
orp checkpoint create -m "describe completed unit" --json
orp backup -m "backup current work" --json
orp ready --json
```

The most important habit is simple:

- do meaningful work on a work branch
- checkpoint intentionally
- keep the repo status honest

That is the boundary between "we are just editing files" and "we are working in a governed research or engineering loop."

This is the checkpoint governance loop:

1. `orp status --json`
   Inspect whether the repo is safe for work right now.
   This tells you things like:
   - whether the repo is ORP-governed
   - whether git is present
   - whether the worktree is dirty
   - whether you are on a protected branch
   - whether validation and readiness are in a good state

2. `orp branch start work/<topic> --json`
   Create or switch to a safe work branch.
   ORP wants meaningful edits to happen on a non-protected work branch unless you have explicitly allowed protected-branch work.

3. `orp checkpoint create -m "describe completed unit" --json`
   Create an intentional checkpoint commit.
   This is the core save-state action.
   It does not mean "ship the work." It means:
   - record a meaningful completed unit
   - make the state recoverable
   - update the checkpoint log and local governance runtime

4. `orp backup -m "backup current work" --json`
   Create a safer backup snapshot, and push it to a dedicated remote ref when possible.
   If the repo is dirty in a risky context, ORP can create a backup work branch first.
   So `backup` is the "make sure this state exists off-machine too" step.

5. `orp ready --json`
   Mark the repo locally ready only when the real conditions are met.
   `ready` is stricter than "I feel done."
   It checks things like:
   - handoff/checkpoint files exist
   - working tree is clean
   - branch policy is respected
   - the latest validation run passed
   - there is a checkpoint after that passing validation

6. `orp doctor --json`
   Inspect governance health and optionally repair missing ORP files with `--fix`.
   Use this when the repo feels out of sync with ORP.

7. `orp cleanup --json`
   Inspect stale branch cleanup candidates.
   This is the "help me prune old branch debris safely" step, not a destructive reset tool.

So the checkpoint governance loop is really:

- inspect the repo
- move onto a safe work branch
- checkpoint meaningful progress
- back it up when needed
- mark readiness honestly
- doctor and cleanup when the repo drifts

That is the part of ORP that keeps the human, the agent, and the repo in check together.

### 11. Keep the program context visible

If the work belongs to a longer-running research or product trajectory:

```bash
orp frontier state --json
orp frontier roadmap --json
```

This is the "where are we in the program?" layer.

The distinction is:

- `workspace` answers: where is the work physically happening?
- `frontier` answers: where are we logically in the larger program?

### 12. Use optional perspective support

When the work feels too linear, too trapped, or too narrow:

```bash
orp mode nudge sleek-minimal-progressive --json
```

This is optional. It does not override the protocol. It just gives the agent or operator a lightweight perspective shift.

It is there to help with:

- getting unstuck
- zooming in or out
- rotating the angle of attack
- keeping the work fresh without making the workflow sloppy

### 13. Optional hosted sync

Hosted ORP is not required for the local workspace ledger or repo-governance loop.

If you want hosted identity, ideas, workspace sync, or runners later:

```bash
orp auth login
orp whoami --json
orp workspaces list --json
orp workspace sync main
```

So the rule is:

- local-first works immediately
- hosted adds sync and control-plane features later

## Daily Loop

Once a repo is ORP-governed and the workspace ledger already exists, this is the main operating loop:

```bash
orp workspace tabs main
orp status --json
orp secrets ensure --alias <alias> --provider <provider> --current-project --json
orp frontier state --json
```

Then do the next meaningful unit of work.

After a real step, checkpoint it:

```bash
orp checkpoint create -m "describe completed unit" --json
```

If the current state should exist off-machine too:

```bash
orp backup -m "backup current work" --json
```

When the work is truly in a ready state:

```bash
orp ready --json
```

The guiding rule is simple:

- recover the saved workspace
- inspect repo safety
- resolve the right secret
- inspect the current frontier
- do the next honest move
- checkpoint at honest boundaries

## Minimum Working Loop

If you only want the irreducible ORP loop, it is this:

1. recover the workspace ledger
   ```bash
   orp workspace tabs main
   ```
2. inspect repo safety
   ```bash
   orp status --json
   ```
3. resolve the right secret
   ```bash
   orp secrets ensure --alias <alias> --provider <provider> --current-project --json
   ```
4. inspect the current frontier
   ```bash
   orp frontier state --json
   ```
5. do the next honest move
6. checkpoint it
   ```bash
   orp checkpoint create -m "describe completed unit" --json
   ```

That is the shortest version of the protocol:

- recover continuity
- inspect safety
- resolve access
- inspect context
- do the work
- checkpoint it honestly

## Agent Contract

If you want the agent to stay aligned with ORP, the default check sequence should be:

```bash
orp workspace tabs main
orp status --json
orp secrets ensure --alias <alias> --provider <provider> --current-project --json
orp frontier state --json
```

And before handoff or a meaningful completed unit:

```bash
orp checkpoint create -m "checkpoint note" --json
```

That is the practical ORP loop:

1. recover the workspace ledger
2. inspect repo safety
3. resolve the right key
4. inspect the current frontier
5. do the work
6. checkpoint it honestly

The key point is that ORP should become the lens:

- not "something we remember to use sometimes"
- but the operating frame the agent checks before and after meaningful work

## If You Only Remember 8 Commands

```bash
orp home
orp init
orp workspace create main-cody-1
orp workspace tabs main
orp workspace add-tab main --path /absolute/path/to/project --resume-command "codex resume <id>"
orp secrets ensure --alias openai-primary --provider openai --current-project --json
orp status --json
orp checkpoint create -m "capture loop state" --json
```
