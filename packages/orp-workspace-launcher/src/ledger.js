import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import {
  buildCanonicalResumeCommand,
  deriveBaseTitle,
  normalizeWorkspaceManifest,
  parseWorkspaceSource,
  resolveResumeMetadata,
} from "./core-plan.js";
import { buildHostedWorkspaceState } from "./hosted-state.js";
import {
  buildWorkspaceManifestFromHostedWorkspacePayload,
  fetchIdeaPayload,
  fetchHostedWorkspacePayload,
  loadWorkspaceSource,
  pushHostedWorkspaceState,
  resolveWorkspaceWatchTargets,
  updateIdeaPayload,
} from "./orp.js";
import {
  cacheManagedWorkspaceManifest,
  loadWorkspaceRegistry,
  loadWorkspaceSlots,
  registerWorkspaceManifest,
  setWorkspaceSlot,
} from "./registry.js";
import { buildWorkspaceSyncPreview, resolveWorkspaceSyncTargetIdeaId, validateWorkspaceTitle } from "./sync.js";

function normalizeOptionalString(value) {
  if (value == null) {
    return null;
  }
  const trimmed = String(value).trim();
  return trimmed.length > 0 ? trimmed : null;
}

function validateAbsolutePath(value, label) {
  const normalized = normalizeOptionalString(value);
  if (!normalized || !normalized.startsWith("/")) {
    throw new Error(`${label} must be an absolute path`);
  }
  return normalized;
}

function serializeManifest(manifest) {
  return `${JSON.stringify(materializeWorkspaceManifest(manifest), null, 2)}\n`;
}

function materializeWorkspaceTab(tab) {
  const resume = resolveResumeMetadata(tab);
  return Object.fromEntries(
    Object.entries({
      title: normalizeOptionalString(tab.title) || undefined,
      path: tab.path,
      resumeCommand: resume.resumeCommand || undefined,
      resumeTool: resume.resumeTool || undefined,
      resumeSessionId: resume.resumeSessionId || undefined,
      codexSessionId: resume.resumeTool === "codex" ? resume.resumeSessionId || undefined : undefined,
      claudeSessionId: resume.resumeTool === "claude" ? resume.resumeSessionId || undefined : undefined,
    }).filter(([, value]) => value !== undefined),
  );
}

function materializeWorkspaceManifest(manifest) {
  const normalized = normalizeWorkspaceManifest(manifest);
  return Object.fromEntries(
    Object.entries({
      version: normalized.version,
      workspaceId: normalized.workspaceId || undefined,
      title: normalized.title || undefined,
      capture: normalized.capture || undefined,
      tabs: normalized.tabs.map((tab) => materializeWorkspaceTab(tab)),
    }).filter(([, value]) => value !== undefined),
  );
}

function normalizeEditableManifest(source, parsed) {
  const baseManifest = parsed.manifest
    ? {
        version: parsed.manifest.version,
        workspaceId: parsed.manifest.workspaceId,
        title: parsed.manifest.title,
        capture: parsed.manifest.capture,
        tabs: parsed.manifest.tabs.map((entry) => {
          const resume = resolveResumeMetadata(entry);
          return Object.fromEntries(
            Object.entries({
              title: normalizeOptionalString(entry.title) || undefined,
              path: entry.path,
              resumeCommand: resume.resumeCommand || undefined,
              resumeTool: resume.resumeTool || undefined,
              resumeSessionId: resume.resumeSessionId || undefined,
              codexSessionId: resume.resumeTool === "codex" ? resume.resumeSessionId || undefined : undefined,
              claudeSessionId: resume.resumeTool === "claude" ? resume.resumeSessionId || undefined : undefined,
            }).filter(([, value]) => value !== undefined),
          );
        }),
      }
    : {
        version: "1",
        workspaceId: source.workspaceManifest?.workspaceId || source.title || "workspace",
        title: source.workspaceManifest?.title || source.title || null,
        capture: source.workspaceManifest?.capture || null,
        tabs: parsed.entries.map((entry) => {
          const resume = resolveResumeMetadata(entry);
          return Object.fromEntries(
            Object.entries({
              title: normalizeOptionalString(entry.title) || deriveBaseTitle(entry),
              path: entry.path,
              resumeCommand: resume.resumeCommand || undefined,
              resumeTool: resume.resumeTool || undefined,
              resumeSessionId: resume.resumeSessionId || undefined,
              codexSessionId: resume.resumeTool === "codex" ? resume.resumeSessionId || undefined : undefined,
              claudeSessionId: resume.resumeTool === "claude" ? resume.resumeSessionId || undefined : undefined,
            }).filter(([, value]) => value !== undefined),
          );
        }),
      };

  return normalizeWorkspaceManifest(baseManifest);
}

function parseLedgerSelectorArgs(argv = [], { commandName, requirePath = false, requireSelector = true } = {}) {
  const options = {
    json: false,
    all: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    if (arg === "-h" || arg === "--help") {
      options.help = true;
      continue;
    }
    if (arg === "--json") {
      options.json = true;
      continue;
    }
    if (arg === "--all") {
      options.all = true;
      continue;
    }
    if (arg.startsWith("--")) {
      const next = argv[index + 1];
      if (next == null || next.startsWith("--")) {
        throw new Error(`missing value for ${arg}`);
      }

      if (arg === "--workspace-file") {
        options.workspaceFile = next;
      } else if (arg === "--hosted-workspace-id") {
        options.hostedWorkspaceId = next;
      } else if (arg === "--base-url") {
        options.baseUrl = next;
      } else if (arg === "--orp-command") {
        options.orpCommand = next;
      } else if (arg === "--path") {
        options.path = next;
      } else if (arg === "--title") {
        options.title = next;
      } else if (arg === "--resume-command") {
        options.resumeCommand = next;
      } else if (arg === "--resume-tool") {
        options.resumeTool = next;
      } else if (arg === "--resume-session-id") {
        options.resumeSessionId = next;
      } else if (arg === "--index") {
        options.index = next;
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

  if (options.help) {
    return options;
  }

  if (requireSelector && !options.ideaId && !options.workspaceFile && !options.hostedWorkspaceId) {
    throw new Error(`Provide a workspace selector for \`${commandName}\`.`);
  }
  if (requirePath && !options.path) {
    throw new Error(`--path is required for \`${commandName}\`.`);
  }
  if (options.path) {
    options.path = validateAbsolutePath(options.path, "--path");
  }
  if (options.index != null) {
    const parsed = Number.parseInt(String(options.index), 10);
    if (!Number.isInteger(parsed) || parsed < 1) {
      throw new Error("--index must be a positive integer");
    }
    options.index = parsed;
  }

  return options;
}

export function parseWorkspaceAddTabArgs(argv = []) {
  return parseLedgerSelectorArgs(argv, {
    commandName: "orp workspace add-tab",
    requirePath: true,
    requireSelector: true,
  });
}

export function parseWorkspaceCreateArgs(argv = []) {
  const options = {
    json: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    if (arg === "-h" || arg === "--help") {
      options.help = true;
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
      } else if (arg === "--slot") {
        options.slotName = next;
      } else if (arg === "--path") {
        options.path = next;
      } else if (arg === "--resume-command") {
        options.resumeCommand = next;
      } else if (arg === "--resume-tool") {
        options.resumeTool = next;
      } else if (arg === "--resume-session-id") {
        options.resumeSessionId = next;
      } else {
        throw new Error(`unknown option: ${arg}`);
      }
      index += 1;
      continue;
    }

    if (options.title) {
      throw new Error(`unexpected argument: ${arg}`);
    }
    options.title = arg;
  }

  if (options.help) {
    return options;
  }

  options.title = validateWorkspaceTitle(options.title, "workspace title");
  if (options.path) {
    options.path = validateAbsolutePath(options.path, "--path");
  }
  if (options.slotName) {
    const slot = String(options.slotName || "").trim().toLowerCase();
    if (slot !== "main" && slot !== "offhand") {
      throw new Error("--slot must be one of: main, offhand");
    }
    options.slotName = slot;
  }

  return options;
}

export function parseWorkspaceRemoveTabArgs(argv = []) {
  const options = parseLedgerSelectorArgs(argv, {
    commandName: "orp workspace remove-tab",
    requirePath: false,
    requireSelector: true,
  });
  if (options.help) {
    return options;
  }
  if (
    options.index == null &&
    !options.path &&
    !options.title &&
    !options.resumeCommand &&
    !options.resumeSessionId
  ) {
    throw new Error("Provide at least one selector like --index, --path, --title, --resume-command, or --resume-session-id.");
  }
  return options;
}

export function addTabToManifest(manifest, options = {}) {
  const nextManifest = normalizeWorkspaceManifest({
    ...manifest,
    tabs: manifest.tabs.map((tab) => ({ ...tab })),
  });
  const resume = resolveResumeMetadata({
    resumeCommand: options.resumeCommand,
    resumeTool: options.resumeTool,
    resumeSessionId: options.resumeSessionId,
  });
  const nextTab = Object.fromEntries(
    Object.entries({
      title: normalizeOptionalString(options.title) || undefined,
      path: validateAbsolutePath(options.path, "--path"),
      resumeCommand: resume.resumeCommand || undefined,
      resumeTool: resume.resumeTool || undefined,
      resumeSessionId: resume.resumeSessionId || undefined,
      codexSessionId: resume.resumeTool === "codex" ? resume.resumeSessionId || undefined : undefined,
      claudeSessionId: resume.resumeTool === "claude" ? resume.resumeSessionId || undefined : undefined,
    }).filter(([, value]) => value !== undefined),
  );

  const duplicate = nextManifest.tabs.find((tab) => {
    const existingResume = resolveResumeMetadata(tab);
    return (
      tab.path === nextTab.path &&
      normalizeOptionalString(tab.title) === normalizeOptionalString(nextTab.title) &&
      existingResume.resumeCommand === (nextTab.resumeCommand || null)
    );
  });

  if (duplicate) {
    return {
      manifest: nextManifest,
      added: false,
      tab: duplicate,
    };
  }

  nextManifest.tabs.push(nextTab);
  return {
    manifest: normalizeWorkspaceManifest(nextManifest),
    added: true,
    tab: nextTab,
  };
}

function tabMatchesRemoval(tab, filters = {}, index) {
  const resume = resolveResumeMetadata(tab);
  if (filters.index != null && filters.index !== index + 1) {
    return false;
  }
  if (filters.path && tab.path !== filters.path) {
    return false;
  }
  if (filters.title && normalizeOptionalString(tab.title) !== normalizeOptionalString(filters.title)) {
    return false;
  }
  if (filters.resumeCommand && resume.resumeCommand !== normalizeOptionalString(filters.resumeCommand)) {
    return false;
  }
  if (filters.resumeSessionId && resume.resumeSessionId !== normalizeOptionalString(filters.resumeSessionId)) {
    return false;
  }
  if (filters.resumeTool && resume.resumeTool !== normalizeOptionalString(filters.resumeTool)?.toLowerCase()) {
    return false;
  }
  return true;
}

export function removeTabsFromManifest(manifest, filters = {}) {
  const nextManifest = normalizeWorkspaceManifest({
    ...manifest,
    tabs: manifest.tabs.map((tab) => ({ ...tab })),
  });
  const matchedIndexes = nextManifest.tabs
    .map((tab, index) => (tabMatchesRemoval(tab, filters, index) ? index : -1))
    .filter((index) => index >= 0);

  if (matchedIndexes.length === 0) {
    throw new Error("No saved tab matched the provided selectors.");
  }
  if (!filters.all && matchedIndexes.length > 1) {
    throw new Error("Multiple saved tabs matched the provided selectors. Narrow it down or pass --all.");
  }

  const removalSet = new Set(filters.all ? matchedIndexes : [matchedIndexes[0]]);
  const removedTabs = nextManifest.tabs.filter((_, index) => removalSet.has(index));
  nextManifest.tabs = nextManifest.tabs.filter((_, index) => !removalSet.has(index));

  if (nextManifest.tabs.length === 0) {
    throw new Error("Refusing to remove every saved tab from the workspace.");
  }

  return {
    manifest: normalizeWorkspaceManifest(nextManifest),
    removedTabs,
  };
}

async function persistWorkspaceManifest(source, manifest, options = {}) {
  const watchTargets = resolveWorkspaceWatchTargets(source, options);

  if (source.sourceType === "workspace-file" && source.sourcePath) {
    await fs.writeFile(source.sourcePath, serializeManifest(manifest), "utf8");
    const registration = await registerWorkspaceManifest(source.sourcePath, manifest, options);
    return {
      persistedTo: "workspace-file",
      manifestPath: source.sourcePath,
      registryPath: registration.registryPath,
      manifest,
    };
  }

  if (watchTargets.syncIdeaSelector) {
    const targetSource = await loadWorkspaceSource({
      ...options,
      ideaId: watchTargets.syncIdeaSelector,
    });
    const targetIdeaId = resolveWorkspaceSyncTargetIdeaId(targetSource);
    if (!targetIdeaId) {
      throw new Error(`Workspace source does not resolve to a syncable hosted idea: ${watchTargets.syncIdeaSelector}`);
    }
    const targetPayload =
      targetSource.sourceType === "hosted-idea" && targetSource.idea?.id === targetIdeaId
        ? targetSource.payload
        : await fetchIdeaPayload(targetIdeaId, options);
    const liveSource = {
      sourceType: "workspace-file",
      sourceLabel: `edited-workspace:${watchTargets.syncIdeaSelector}`,
      title: manifest.title || manifest.workspaceId || source.title || watchTargets.syncIdeaSelector,
      workspaceManifest: manifest,
      notes: "",
    };
    const parsed = parseWorkspaceSource(liveSource);
    const preview = buildWorkspaceSyncPreview({
      source: liveSource,
      parsed,
      targetIdea: targetPayload.idea,
      workspaceTitle: manifest.title || manifest.workspaceId || undefined,
    });
    const updatedIdea = await updateIdeaPayload(targetIdeaId, { notes: preview.nextNotes }, options);
    const managedCache = await cacheManagedWorkspaceManifest(preview.manifest, options);
    return {
      persistedTo: "hosted-idea",
      ideaId: targetIdeaId,
      updatedIdea,
      managedCache,
      manifest: preview.manifest,
    };
  }

  if (watchTargets.hostedWorkspaceId) {
    const previousWorkspace =
      source.hostedWorkspace ||
      (await fetchHostedWorkspacePayload(watchTargets.hostedWorkspaceId, options)).workspace;
    const state = buildHostedWorkspaceState(manifest, {
      previousWorkspace,
      capturedAt: manifest.capture?.capturedAt,
      updatedAt: new Date().toISOString(),
    });
    const pushResult = await pushHostedWorkspaceState(watchTargets.hostedWorkspaceId, state, options);
    const cachedManifest = buildWorkspaceManifestFromHostedWorkspacePayload(pushResult);
    const managedCache = await cacheManagedWorkspaceManifest(cachedManifest, options);
    return {
      persistedTo: "hosted-workspace",
      workspaceId: watchTargets.hostedWorkspaceId,
      pushResult,
      managedCache,
      manifest: cachedManifest,
    };
  }

  throw new Error("This workspace source cannot be edited in place yet. Use a saved workspace selector or --workspace-file.");
}

function printWorkspaceAddTabHelp() {
  console.log(`ORP workspace add-tab

Usage:
  orp workspace add-tab <name-or-id> --path <absolute-path> [--title <title>] [--resume-command <text> | --resume-tool <codex|claude> --resume-session-id <id>] [--json]
  orp workspace add-tab --hosted-workspace-id <workspace-id> --path <absolute-path> [--json]
  orp workspace add-tab --workspace-file <path> --path <absolute-path> [--json]

Options:
  --path <absolute-path> Add this local project path to the saved workspace
  --title <title>        Optional saved tab title
  --resume-command <text> Exact saved resume command, like \`codex resume ...\` or \`claude --resume ...\`
  --resume-tool <tool>   Build the resume command from \`codex\` or \`claude\`
  --resume-session-id <id> Resume session id to save with the tab
  --hosted-workspace-id <id> Edit a first-class hosted workspace directly
  --workspace-file <path> Edit a local structured workspace manifest
  --json                 Print the updated workspace edit result as JSON
  -h, --help             Show this help text

Examples:
  orp workspace add-tab main --path /Volumes/Code_2TB/code/new-project
  orp workspace add-tab main --path /Volumes/Code_2TB/code/new-project --resume-command "codex resume 019d..."
  orp workspace add-tab main --path /Volumes/Code_2TB/code/new-project --resume-tool claude --resume-session-id claude-456
`);
}

function printWorkspaceCreateHelp() {
  console.log(`ORP workspace create

Usage:
  orp workspace create <title-slug> [--workspace-file <path>] [--slot <main|offhand>] [--path <absolute-path>] [--resume-command <text> | --resume-tool <codex|claude> --resume-session-id <id>] [--json]

Options:
  <title-slug>           Required local workspace title using lowercase letters, numbers, and dashes only
  --workspace-file <path> Create the workspace manifest at an explicit local path instead of the managed ORP workspace directory
  --slot <main|offhand>  Optionally assign the created workspace to a named slot
  --path <absolute-path> Optionally seed the workspace with one saved path immediately
  --resume-command <text> Exact saved resume command, like \`codex resume ...\` or \`claude --resume ...\`
  --resume-tool <tool>   Build the resume command from \`codex\` or \`claude\`
  --resume-session-id <id> Resume session id to save with the first tab
  --json                 Print the created workspace result as JSON
  -h, --help             Show this help text

Examples:
  orp workspace create main-cody-1
  orp workspace create main-cody-1 --slot main
  orp workspace create research-lab --path /Volumes/Code_2TB/code/research-lab
  orp workspace create research-lab --path /Volumes/Code_2TB/code/research-lab --resume-tool claude --resume-session-id 469d99b2-2997-42bf-a8f5-3812c808ef29
`);
}

function printWorkspaceRemoveTabHelp() {
  console.log(`ORP workspace remove-tab

Usage:
  orp workspace remove-tab <name-or-id> (--index <n> | --path <absolute-path> | --title <title> | --resume-session-id <id> | --resume-command <text>) [--all] [--json]
  orp workspace remove-tab --hosted-workspace-id <workspace-id> ... [--json]
  orp workspace remove-tab --workspace-file <path> ... [--json]

Options:
  --index <n>            Remove the saved tab at 1-based index \`n\`
  --path <absolute-path> Match saved tabs by absolute path
  --title <title>        Match saved tabs by title
  --resume-command <text> Match saved tabs by exact resume command
  --resume-session-id <id> Match saved tabs by resume session id
  --resume-tool <tool>   Narrow removal to \`codex\` or \`claude\`
  --all                  Remove every matching tab instead of requiring one exact match
  --hosted-workspace-id <id> Edit a first-class hosted workspace directly
  --workspace-file <path> Edit a local structured workspace manifest
  --json                 Print the updated workspace edit result as JSON
  -h, --help             Show this help text

Examples:
  orp workspace remove-tab main --index 11
  orp workspace remove-tab main --path /Volumes/Code_2TB/code/frg-site --resume-session-id 019d348d-5031-78e1-9840-a66deaac33ae
  orp workspace remove-tab main --title frg-site
`);
}

function summarizeWorkspaceLedgerMutation(result) {
  const lines = [
    `Workspace: ${result.workspaceTitle || result.workspaceId || "workspace"}`,
    `Action: ${result.action}`,
    `Saved tabs: ${result.tabCount}`,
  ];

  if (result.action === "add-tab") {
    lines.push(`Added: ${result.tab?.title || path.basename(result.tab?.path || "") || result.tab?.path}`);
    lines.push(`Path: ${result.tab?.path}`);
    if (result.tab?.resumeCommand) {
      lines.push(`Resume: ${result.tab.resumeCommand}`);
    }
  } else if (result.action === "remove-tab") {
    lines.push(`Removed: ${result.removedTabs.length}`);
    for (const tab of result.removedTabs) {
      lines.push(`  - ${tab.title || path.basename(tab.path)} (${tab.path})`);
    }
  }

  if (result.persistedTo === "hosted-idea") {
    lines.push(`Canonical source: ORP idea ${result.ideaId}`);
  } else if (result.persistedTo === "hosted-workspace") {
    lines.push(`Canonical source: hosted workspace ${result.workspaceId}`);
  } else if (result.persistedTo === "workspace-file") {
    lines.push(`Saved file: ${result.manifestPath}`);
  }

  if (result.managedCachePath) {
    lines.push(`Local cache: ${result.managedCachePath}`);
  }

  return lines.join("\n");
}

async function runWorkspaceLedgerMutation(options, mutate, action) {
  const source = await loadWorkspaceSource(options);
  const parsed = parseWorkspaceSource(source);
  const manifest = normalizeEditableManifest(source, parsed);
  const mutated = mutate(manifest, options);
  const persisted = await persistWorkspaceManifest(source, mutated.manifest, options);
  const finalManifest = materializeWorkspaceManifest(persisted.manifest || mutated.manifest);

  const result = {
    action,
    workspaceId: finalManifest.workspaceId,
    workspaceTitle: finalManifest.title || source.title || null,
    tabCount: finalManifest.tabs.length,
    tab: mutated.tab ? materializeWorkspaceTab(mutated.tab) : null,
    removedTabs: (mutated.removedTabs || []).map((tab) => materializeWorkspaceTab(tab)),
    persistedTo: persisted.persistedTo,
    ideaId: persisted.ideaId || null,
    workspaceSourceId: persisted.workspaceId || null,
    manifestPath: persisted.manifestPath || null,
    managedCachePath: persisted.managedCache?.manifestPath || null,
    manifest: finalManifest,
  };

  if (options.json) {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return 0;
  }

  process.stdout.write(`${summarizeWorkspaceLedgerMutation(result)}\n`);
  return 0;
}

export async function runWorkspaceAddTab(argv = process.argv.slice(2)) {
  const options = parseWorkspaceAddTabArgs(argv);
  if (options.help) {
    printWorkspaceAddTabHelp();
    return 0;
  }
  return runWorkspaceLedgerMutation(options, addTabToManifest, "add-tab");
}

export async function runWorkspaceRemoveTab(argv = process.argv.slice(2)) {
  const options = parseWorkspaceRemoveTabArgs(argv);
  if (options.help) {
    printWorkspaceRemoveTabHelp();
    return 0;
  }
  return runWorkspaceLedgerMutation(options, removeTabsFromManifest, "remove-tab");
}

export async function runWorkspaceCreate(argv = process.argv.slice(2)) {
  const options = parseWorkspaceCreateArgs(argv);
  if (options.help) {
    printWorkspaceCreateHelp();
    return 0;
  }

  const tabs = [];
  if (options.path) {
    const resume = resolveResumeMetadata({
      resumeCommand: options.resumeCommand,
      resumeTool: options.resumeTool,
      resumeSessionId: options.resumeSessionId,
    });
    tabs.push(
      Object.fromEntries(
        Object.entries({
          title: deriveBaseTitle({ path: options.path }),
          path: options.path,
          resumeCommand: resume.resumeCommand || undefined,
          resumeTool: resume.resumeTool || undefined,
          resumeSessionId: resume.resumeSessionId || undefined,
          codexSessionId: resume.resumeTool === "codex" ? resume.resumeSessionId || undefined : undefined,
          claudeSessionId: resume.resumeTool === "claude" ? resume.resumeSessionId || undefined : undefined,
        }).filter(([, value]) => value !== undefined),
      ),
    );
  }

  const manifest = normalizeWorkspaceManifest({
    version: "1",
    workspaceId: options.title,
    title: options.title,
    tabs,
  });

  let manifestPath = null;
  let registryPath = null;
  let managedCachePath = null;
  if (options.workspaceFile) {
    manifestPath = path.resolve(options.workspaceFile);
    await fs.mkdir(path.dirname(manifestPath), { recursive: true });
    await fs.writeFile(manifestPath, serializeManifest(manifest), "utf8");
    const registration = await registerWorkspaceManifest(manifestPath, manifest, options);
    registryPath = registration.registryPath;
  } else {
    const cached = await cacheManagedWorkspaceManifest(manifest, options);
    manifestPath = cached.manifestPath;
    registryPath = cached.registryPath;
    managedCachePath = cached.manifestPath;
  }

  let assignedSlot = null;
  const assignment = {
    kind: "workspace-file",
    selector: manifest.title,
    workspaceId: manifest.workspaceId,
    title: manifest.title,
    manifestPath,
  };
  if (options.slotName) {
    assignedSlot = (await setWorkspaceSlot(options.slotName, assignment, options)).slot;
  } else {
    const [registryResult, slotsResult] = await Promise.all([
      loadWorkspaceRegistry(options),
      loadWorkspaceSlots(options),
    ]);
    if (!slotsResult.slots?.main && Array.isArray(registryResult.registry?.workspaces) && registryResult.registry.workspaces.length === 1) {
      assignedSlot = (await setWorkspaceSlot("main", assignment, options)).slot;
    }
  }

  const result = {
    ok: true,
    action: "create",
    workspaceId: manifest.workspaceId,
    workspaceTitle: manifest.title,
    tabCount: manifest.tabs.length,
    manifestPath,
    registryPath,
    managedCachePath,
    slot: assignedSlot,
    manifest: materializeWorkspaceManifest(manifest),
  };

  if (options.json) {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return 0;
  }

  const lines = [
    `Workspace: ${result.workspaceTitle}`,
    "Action: create",
    `Saved tabs: ${result.tabCount}`,
    `Saved file: ${result.manifestPath}`,
  ];
  if (result.slot?.slot) {
    lines.push(`Slot: ${result.slot.slot}`);
  }
  process.stdout.write(`${lines.join("\n")}\n`);
  return 0;
}
