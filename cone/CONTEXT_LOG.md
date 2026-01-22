# Context Log (process-only; not evidence)

> This file is **not evidence**. It is a running, lightweight trace of “what’s going on” to support handoff, compaction, and
> coordination.
>
> Keep entries neutral: hypotheses, decisions, links, next hooks. Avoid “proving” anything here.

---

## How to use

- Add an entry at major transitions:
  - after context compaction/summarization
  - before `git commit` / `git push` (optional but recommended for agentic workflows)
  - before publishing a **Verified/Exact** claim
  - at handoff (“here’s the state; here’s next”)
- Prefer links to canonical artifacts (code/data/logs) rather than reproducing content here.

---

## Entry template

### Checkpoint — YYYY-MM-DDTHH:MM:SSZ
- Note:
- Repo state:
  - Branch:
  - Head:
  - Git status: staged=?, unstaged=?, untracked=?
- ORP snippet sync:
  - Agent instruction files checked:
  - Result: PASS / FAIL / (skipped)
- Canonical artifacts touched (paths only):
- Next hook:
