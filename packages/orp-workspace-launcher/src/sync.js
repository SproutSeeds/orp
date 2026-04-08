import process from "node:process";
import { createInterface } from "node:readline/promises";

import {
  deriveBaseTitle,
  deriveWorkspaceId,
  getResumeCommand,
  parseWorkspaceSource,
  resolveResumeMetadata,
  WORKSPACE_SCHEMA_VERSION,
} from "./core-plan.js";
import { fetchIdeaPayload, loadWorkspaceSource, updateIdeaPayload } from "./orp.js";
import { cacheManagedWorkspaceManifest } from "./registry.js";

const STRUCTURED_WORKSPACE_BLOCK_PATTERN = /```orp-workspace\s*[\s\S]*?```/i;
const WORKSPACE_TITLE_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function printSyncHelp() {
  console.log(`ORP workspace sync

Usage:
  orp workspace sync <name-or-id> [--workspace-file <path> | --notes-file <path>] [--title <slug>] [--dry-run] [--json]

Options:
  --workspace-file <path> Read a structured workspace manifest JSON file
  --notes-file <path>     Read a local notes file and normalize launchable paths into a manifest
  --title <slug>          Required when the source workspace does not already have a saved title
  --dry-run               Print the sync preview without updating the hosted idea
  --json                  Print the sync preview as JSON
  --base-url <url>        Override the ORP hosted base URL
  --orp-command <cmd>     Override the ORP CLI executable used for hosted fetches/updates
  -h, --help              Show this help text

Examples:
  orp workspace sync main
  orp workspace sync main --workspace-file ./workspace.json --title main-cody-1
  orp workspace sync main --notes-file ./workspace-notes.txt --title main-cody-1 --dry-run
`);
}

function normalizeOptionalString(value) {
  if (value == null) {
    return null;
  }
  const trimmed = String(value).trim();
  return trimmed.length > 0 ? trimmed : null;
}

function parseWorkspaceSyncArgs(argv = []) {
  const options = {
    dryRun: false,
    json: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "-h" || arg === "--help") {
      options.help = true;
      continue;
    }
    if (arg === "--dry-run") {
      options.dryRun = true;
      continue;
    }
    if (arg === "--json") {
      options.json = true;
      continue;
    }
    if (arg.startsWith("--")) {
      const next = argv[index + 1];
      if (next == null || next.startsWith("--")) {
        throw new Error(`missing value for ${arg}`);
      }
      if (arg === "--workspace-file") {
        options.workspaceFile = next;
      } else if (arg === "--notes-file") {
        options.notesFile = next;
      } else if (arg === "--title") {
        options.title = next;
      } else if (arg === "--base-url") {
        options.baseUrl = next;
      } else if (arg === "--orp-command") {
        options.orpCommand = next;
      } else {
        throw new Error(`unknown option: ${arg}`);
      }
      index += 1;
      continue;
    }

    if (options.ideaId) {
      throw new Error(`unexpected argument: ${arg}`);
    }
    options.ideaId = arg;
  }

  return options;
}

function getLinkedIdeaIdFromWorkspaceRecord(workspace) {
  if (!workspace || typeof workspace !== "object" || Array.isArray(workspace)) {
    return null;
  }
  const linkedIdea =
    workspace.linked_idea && typeof workspace.linked_idea === "object" && !Array.isArray(workspace.linked_idea)
      ? workspace.linked_idea
      : workspace.linkedIdea && typeof workspace.linkedIdea === "object" && !Array.isArray(workspace.linkedIdea)
        ? workspace.linkedIdea
        : null;
  return normalizeOptionalString(linkedIdea?.idea_id ?? linkedIdea?.ideaId);
}

export function resolveWorkspaceSyncTargetIdeaId(source) {
  if (!source || typeof source !== "object" || Array.isArray(source)) {
    return null;
  }
  if (source.sourceType === "hosted-idea") {
    return normalizeOptionalString(source.idea?.id);
  }
  if (source.sourceType === "hosted-workspace") {
    return getLinkedIdeaIdFromWorkspaceRecord(source.hostedWorkspace);
  }
  return null;
}

async function resolveWorkspaceSyncTargetSource(source, options) {
  if (!options.workspaceFile && !options.notesFile && (source.sourceType === "hosted-idea" || source.sourceType === "hosted-workspace")) {
    return source;
  }
  return loadWorkspaceSource({
    ideaId: options.ideaId,
    baseUrl: options.baseUrl,
    orpCommand: options.orpCommand,
  });
}

export function validateWorkspaceTitle(value, label = "--title") {
  const normalized = normalizeOptionalString(value);
  if (!normalized) {
    throw new Error(`${label} is required and must use lowercase letters, numbers, and dashes only.`);
  }
  if (!WORKSPACE_TITLE_PATTERN.test(normalized)) {
    throw new Error(`${label} must use lowercase letters, numbers, and single dashes only, like main-cody-1.`);
  }
  return normalized;
}

async function promptForWorkspaceTitle() {
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    throw new Error("Workspace title is required. Provide --title <slug> with lowercase letters, numbers, and dashes only.");
  }
  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  try {
    const answer = await rl.question("Workspace title (lowercase-dash format, example: main-cody-1): ");
    return validateWorkspaceTitle(answer, "workspace title");
  } finally {
    rl.close();
  }
}

function normalizeNotesBody(value) {
  return String(value || "")
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function combineNoteSections(sections) {
  return sections
    .map((section) => normalizeNotesBody(section))
    .filter((section) => section.length > 0)
    .join("\n\n");
}

export function extractWorkspaceNarrativeNotes(notes, options = {}) {
  const withoutStructuredBlock = String(notes || "").replace(STRUCTURED_WORKSPACE_BLOCK_PATTERN, "");
  const lines = withoutStructuredBlock.split(/\r?\n/);
  const filteredLines = options.stripLegacyWorkspaceLines
    ? lines.filter((line) => !line.trim().startsWith("/"))
    : lines;
  return normalizeNotesBody(filteredLines.join("\n"));
}

function serializeWorkspaceManifest(manifest) {
  const tabs = manifest.tabs.map((entry) =>
    Object.fromEntries(
      Object.entries({
        title: normalizeOptionalString(entry.title) ?? undefined,
        path: String(entry.path).trim(),
        remoteUrl: normalizeOptionalString(entry.remoteUrl) ?? undefined,
        remoteBranch: normalizeOptionalString(entry.remoteBranch) ?? undefined,
        bootstrapCommand: normalizeOptionalString(entry.bootstrapCommand) ?? undefined,
        resumeCommand: normalizeOptionalString(entry.resumeCommand) ?? undefined,
        resumeTool: normalizeOptionalString(entry.resumeTool) ?? undefined,
        resumeSessionId: normalizeOptionalString(entry.resumeSessionId ?? entry.sessionId) ?? undefined,
        codexSessionId:
          normalizeOptionalString(entry.resumeTool) === "codex"
            ? normalizeOptionalString(entry.codexSessionId ?? entry.resumeSessionId ?? entry.sessionId) ?? undefined
            : undefined,
        claudeSessionId:
          normalizeOptionalString(entry.resumeTool) === "claude"
            ? normalizeOptionalString(entry.claudeSessionId ?? entry.resumeSessionId ?? entry.sessionId) ?? undefined
            : undefined,
      }).filter(([, value]) => value !== undefined),
    ),
  );

  const normalized = Object.fromEntries(
    Object.entries({
      version: WORKSPACE_SCHEMA_VERSION,
      workspaceId: normalizeOptionalString(manifest.workspaceId) ?? undefined,
      title: normalizeOptionalString(manifest.title) ?? undefined,
      machine: manifest.machine ?? undefined,
      tabs,
    }).filter(([, value]) => value !== undefined),
  );

  return JSON.stringify(normalized, null, 2);
}

function composeWorkspaceNotes({ narrativeNotes, manifest }) {
  return combineNoteSections([
    narrativeNotes,
    `\`\`\`orp-workspace\n${serializeWorkspaceManifest(manifest)}\n\`\`\``,
  ]);
}

export function buildWorkspaceSyncPreview({ source, parsed, targetIdea, workspaceTitle = null }) {
  const manifest = parsed.manifest
    ? {
        version: parsed.manifest.version || WORKSPACE_SCHEMA_VERSION,
        workspaceId: parsed.manifest.workspaceId || workspaceTitle || deriveWorkspaceId(source, parsed),
        title: workspaceTitle || parsed.manifest.title || null,
        machine: parsed.manifest.machine || null,
        tabs: parsed.manifest.tabs.map((entry) => ({
          title: entry.title || deriveBaseTitle(entry),
          path: entry.path,
          remoteUrl: entry.remoteUrl || null,
          remoteBranch: entry.remoteBranch || null,
          bootstrapCommand: entry.bootstrapCommand || null,
          resumeCommand: entry.resumeCommand || null,
          resumeTool: entry.resumeTool || null,
          resumeSessionId: entry.sessionId || null,
          codexSessionId: entry.resumeTool === "codex" ? entry.sessionId || null : null,
          claudeSessionId: entry.resumeTool === "claude" ? entry.sessionId || null : null,
        })),
      }
    : {
        version: WORKSPACE_SCHEMA_VERSION,
        workspaceId: workspaceTitle || deriveWorkspaceId(source, parsed),
        title: workspaceTitle || null,
        machine: null,
        tabs: parsed.entries.map((entry) => ({
          title: deriveBaseTitle(entry),
          path: entry.path,
          remoteUrl: entry.remoteUrl || null,
          remoteBranch: entry.remoteBranch || null,
          bootstrapCommand: entry.bootstrapCommand || null,
          resumeCommand: getResumeCommand(entry),
          resumeTool: resolveResumeMetadata(entry).resumeTool,
          resumeSessionId: resolveResumeMetadata(entry).resumeSessionId,
          codexSessionId:
            resolveResumeMetadata(entry).resumeTool === "codex" ? resolveResumeMetadata(entry).resumeSessionId : null,
          claudeSessionId:
            resolveResumeMetadata(entry).resumeTool === "claude" ? resolveResumeMetadata(entry).resumeSessionId : null,
        })),
      };

  const narrativeSourceNotes =
    source.sourceType === "workspace-file" ? targetIdea.notes || "" : source.notes || targetIdea.notes || "";
  const narrativeNotes = extractWorkspaceNarrativeNotes(narrativeSourceNotes, {
    stripLegacyWorkspaceLines: source.sourceType === "workspace-file",
  });
  const nextNotes = composeWorkspaceNotes({
    narrativeNotes,
    manifest,
  });

  return {
    targetIdeaId: targetIdea.id,
    targetIdeaTitle: targetIdea.title,
    sourceType: source.sourceType,
    sourceLabel: source.sourceLabel,
    parseMode: parsed.parseMode,
    workspaceId: manifest.workspaceId,
    manifest,
    nextNotes,
    nextNotesLength: nextNotes.length,
    tabs: manifest.tabs,
    skipped: parsed.skipped,
  };
}

function summarizeSyncPreview(preview) {
  const lines = [
    `Workspace sync preview`,
    `  target: ${preview.targetIdeaTitle} (${preview.targetIdeaId})`,
    `  source: ${preview.sourceType} (${preview.sourceLabel})`,
    `  parse mode: ${preview.parseMode}`,
    `  workspace id: ${preview.workspaceId}`,
    `  tabs: ${preview.tabs.length}`,
    `  stored notes: ${preview.nextNotesLength} chars`,
  ];

  if (preview.skipped.length > 0) {
    lines.push(`  skipped non-path lines: ${preview.skipped.length}`);
  }
  return lines.join("\n");
}

export async function runWorkspaceSync(argv = process.argv.slice(2)) {
  const options = parseWorkspaceSyncArgs(argv);
  if (options.help) {
    printSyncHelp();
    return 0;
  }
  if (!options.ideaId) {
    throw new Error("Provide the hosted workspace selector that should receive the synced workspace.");
  }

  const source = await loadWorkspaceSource(options);
  const parsed = parseWorkspaceSource(source);
  if (parsed.entries.length === 0) {
    throw new Error("No launchable workspace lines were found in the provided source.");
  }
  const resolvedWorkspaceTitle = options.title
    ? validateWorkspaceTitle(options.title)
    : normalizeOptionalString(parsed.manifest?.title) || (await promptForWorkspaceTitle());
  const targetSource = await resolveWorkspaceSyncTargetSource(source, options);
  const targetIdeaId = resolveWorkspaceSyncTargetIdeaId(targetSource);
  if (!targetIdeaId) {
    throw new Error(
      `Workspace sync target '${options.ideaId}' does not resolve to a hosted idea-backed workspace. Use a synced hosted selector like main, an idea id, or a workspace linked to a hosted idea.`,
    );
  }

  const targetPayload =
    targetSource.sourceType === "hosted-idea" && targetSource.idea?.id === targetIdeaId
      ? targetSource.payload
      : await fetchIdeaPayload(targetIdeaId, options);

  if (!targetPayload?.idea) {
    throw new Error("Unable to resolve the hosted ORP idea for workspace sync.");
  }

  const preview = buildWorkspaceSyncPreview({
    source,
    parsed,
    targetIdea: targetPayload.idea,
    workspaceTitle: resolvedWorkspaceTitle,
  });

  if (options.json) {
    process.stdout.write(`${JSON.stringify(preview, null, 2)}\n`);
    return 0;
  }

  if (options.dryRun) {
    process.stdout.write(`${summarizeSyncPreview(preview)}\n`);
    return 0;
  }

  const updated = await updateIdeaPayload(targetIdeaId, { notes: preview.nextNotes }, options);
  const managedCache = await cacheManagedWorkspaceManifest(preview.manifest);
  process.stdout.write(
    `Synced workspace '${preview.workspaceId}' to idea '${updated.title || preview.targetIdeaTitle}'.\n`,
  );
  process.stdout.write(`Tabs: ${preview.tabs.length}. Stored notes: ${preview.nextNotesLength} chars.\n`);
  process.stdout.write(`Updated local workspace cache at ${managedCache.manifestPath}.\n`);
  return 0;
}
