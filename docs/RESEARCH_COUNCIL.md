# ORP Research Council

ORP research council runs turn one question into a durable, tool-callable research artifact. The default profile is OpenAI-only right now, so one saved ORP key can power the full loop:

```bash
orp research ask "Where should this system live?" --json
```

By default this is a dry run. ORP writes the decomposition, profile, lane plan, lane JSON files, synthesized planning answer, and summary under:

```text
orp/research/<run_id>/
```

Live provider calls require an explicit flag:

```bash
orp research ask "Where should this system live?" --execute --json
```

## Lanes

The built-in `openai-council` profile defines three OpenAI API lanes:

- `openai_reasoning_high`: `gpt-5.4` with `reasoning.effort=high` for the deliberate thinking pass.
- `openai_web_synthesis`: `gpt-5.4` with high reasoning plus Responses API web search for current public evidence and citations.
- `openai_deep_research`: `o3-deep-research-2025-06-26` with background execution and web search preview for Pro/Deep Research style investigation.

This follows OpenAI's current model guidance: `gpt-5.4` is the default for general-purpose, coding, reasoning, and agentic workflows; web search is enabled through the Responses API `tools` array when current information is needed; and Deep Research is available through the Responses endpoint with `o3-deep-research-2025-06-26`.

## Staged Deep Research Template

ORP also includes a built-in `deep-think-web-think-deep` profile for a strict sequence:

```text
Deep Research -> think -> think/web search -> think -> Deep Research
```

Inspect the template before using it:

```bash
orp research profile show deep-think-web-think-deep --json
```

Run a dry plan with form-like fields filled by a human or an agent:

```bash
orp research ask "Should this product use a staged research loop?" \
  --profile deep-think-web-think-deep \
  --field goal="Decide whether to adopt the staged loop" \
  --field audience="Platform team" \
  --field decision_to_support="Choose the default research workflow" \
  --field project_context="ORP owns durable artifacts and secret resolution" \
  --field constraints="Use one OpenAI API key first" \
  --field deliverable_format="Decision memo with risks and next steps" \
  --json
```

The prompt form is intentionally general. It gives an agent a reusable customization surface, similar to filling out a product intake form for a company:

- `goal`
- `audience`
- `decision_to_support`
- `project_context`
- `constraints`
- `known_inputs`
- `source_preferences`
- `recency_requirements`
- `excluded_assumptions`
- `success_criteria`
- `deliverable_format`

Dry runs persist the generated prompt for every lane under `orp/research/<run_id>/lanes/`. Later lanes include earlier lane outputs when those outputs exist, whether they came from live calls or `--lane-fixture` files. This makes the sequence inspectable before spending live provider calls. In live mode, later staged lanes skip their provider call if an earlier required lane did not complete with text.

The staged profile keeps Deep Research foreground by default so the next lane can receive actual output. Deep Research can take a long time; pass a larger `--timeout-sec` for live runs or provide a custom profile file that sets `background=true` if you want asynchronous Deep Research behavior.

## API Call Moments

ORP records when API keys are intended to be used:

- `plan`: local decomposition only. No API key is resolved.
- `thinking_reasoning_high`: resolve `openai-primary` immediately before the `openai_reasoning_high` lane.
- `web_synthesis`: resolve `openai-primary` immediately before the `openai_web_synthesis` lane.
- `pro_deep_research`: resolve `openai-primary` immediately before the `openai_deep_research` lane.

Dry runs write every lane with `api_call.called=false`. Live runs require `--execute`; even then, secret values are read only at the lane call moment and are not written to artifacts.

Secret values are read from environment variables first. If an env var is missing and a matching ORP Keychain secret is available, ORP can use it at execution time. Secret values are not persisted in artifacts.

The default live profile expects this ORP secret alias or env var:

- `openai-primary` / `OPENAI_API_KEY`

Store a local machine copy without the hosted secret API like this:

```bash
printf '%s' '<openai-key>' | orp secrets keychain-add \
  --alias openai-primary \
  --label "OpenAI Primary" \
  --provider openai \
  --value-stdin \
  --json
```

## Fixtures

Provider outputs can be attached without spending live calls:

```bash
orp research ask "Where should this live?" \
  --lane-fixture openai_reasoning_high=reports/reasoning.json \
  --lane-fixture openai_web_synthesis=reports/web.txt \
  --json
```

Fixtures are useful when an OpenAI run happened outside ORP, when you are comparing model settings manually, or when tests need deterministic lane outputs.

## OpenAI API Notes

ORP uses the Responses API for these lanes. Useful knobs in profile JSON:

- `model`: for example `gpt-5.4` or `o3-deep-research-2025-06-26`.
- `call_moment`: the named research-loop moment when this lane may resolve a key.
- `reasoning_effort`: `none`, `low`, `medium`, `high`, or `xhigh` for supported models.
- `reasoning_summary`: `auto` or `detailed` for Deep Research reasoning summaries.
- `text_verbosity`: `low`, `medium`, or `high`.
- `web_search`: `true` to add the Responses API web-search tool.
- `search_context_size`: `low`, `medium`, or `high` for web search.
- `background`: `true` for long-running Deep Research calls.
- `max_output_tokens`: hard cap for a lane response.

The default profile deliberately avoids Anthropic, xAI, and local-model lanes so a single OpenAI key is enough.

## Project Context Timing

`orp init` creates `orp/project.json`, a process-only project context lens for the current directory. It records the authority surfaces ORP can see, the directory signals it should route on, and the default research timing policy:

- decompose locally first
- use high-reasoning API calls when a decision gate or ambiguous next action needs outside reasoning
- use web synthesis when current public facts, docs, papers, project status, or citations matter
- use Deep Research only after reasoning/web lanes expose a research-heavy gap, disagreement, source-quality issue, or literature-scale synthesis need

Run `orp project refresh --json` after adding or changing roadmap, spec, agent-guidance, docs, manifest, or command-surface files. Refreshing project context does not call a provider; live provider calls remain explicit through `orp research ask --execute`.

## Follow-Up Commands

```bash
orp project show --json
orp project refresh --json
orp research status latest --json
orp research show latest --json
```

## Codex MCP Tool

ORP also ships a tiny stdio MCP wrapper for the research commands:

```toml
[mcp_servers.orp-research]
command = "/path/to/orp/scripts/orp-mcp"
```

It exposes:

- `orp_research_ask`
- `orp_research_profile_list`
- `orp_research_profile_show`
- `orp_research_status`
- `orp_research_show`

Research council files are ORP process artifacts. They record decomposition, provider lane outputs, and synthesis. Canonical evidence still belongs in source repositories, linked reports, cited URLs, datasets, papers, or other primary artifacts.
