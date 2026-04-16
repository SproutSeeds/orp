import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";

import {
  buildDirectCommand,
  buildWorkspaceProjectGroups,
  deriveBaseTitle,
  normalizeWorkspaceManifest,
  parseWorkspaceSource,
  resolveResumeMetadata,
} from "./core-plan.js";
import { buildHostedWorkspaceState } from "./hosted-state.js";
import {
  buildWorkspaceManifestFromHostedWorkspacePayload,
  createHostedWorkspaceForIdea,
  fetchHostedWorkspacePayload,
  findHostedWorkspaceByLinkedIdea,
  loadWorkspaceSource,
  pushHostedWorkspaceState,
  resolveWorkspaceWatchTargets,
} from "./orp.js";
import {
  cacheManagedWorkspaceManifest,
  loadWorkspaceRegistry,
  loadWorkspaceSlots,
  registerWorkspaceManifest,
  setWorkspaceSlot,
} from "./registry.js";
import { validateWorkspaceTitle } from "./sync.js";

function normalizeOptionalString(value) {
  if (value == null) {
    return null;
  }
  const trimmed = String(value).trim();
  return trimmed.length > 0 ? trimmed : null;
}

function buildCurrentMachineMetadata(options = {}) {
  const machineId = normalizeOptionalString(options.machineId) || `${os.hostname().trim() || "machine"}:${process.platform}`;
  return {
    machineId,
    machineLabel: normalizeOptionalString(options.machineLabel) || os.hostname().trim() || "This Machine",
    platform: normalizeOptionalString(options.platform) || process.platform,
    host: os.hostname().trim() || undefined,
  };
}

function validateAbsolutePath(value, label) {
  const normalized = normalizeOptionalString(value);
  if (!normalized || !normalized.startsWith("/")) {
    throw new Error(`${label} must be an absolute path`);
  }
  return normalized;
}

function resolveCurrentCodexResume() {
  const sessionId = normalizeOptionalString(process.env.CODEX_THREAD_ID);
  if (!sessionId) {
    throw new Error("`--current-codex` requires `CODEX_THREAD_ID` in the current environment.");
  }
  return {
    resumeTool: "codex",
    resumeSessionId: sessionId,
  };
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
      remoteUrl: normalizeOptionalString(tab.remoteUrl) || undefined,
      remoteBranch: normalizeOptionalString(tab.remoteBranch) || undefined,
      bootstrapCommand: normalizeOptionalString(tab.bootstrapCommand) || undefined,
      resumeCommand: resume.resumeCommand || undefined,
      resumeTool: resume.resumeTool || undefined,
      resumeSessionId: resume.resumeSessionId || undefined,
      codexSessionId: resume.resumeTool === "codex" ? resume.resumeSessionId || undefined : undefined,
      claudeSessionId: resume.resumeTool === "claude" ? resume.resumeSessionId || undefined : undefined,
    }).filter(([, value]) => value !== undefined),
  );
}

function buildWorkspaceResultTab(tab) {
  if (!tab) {
    return null;
  }
  const materialized = materializeWorkspaceTab(tab);
  return {
    ...materialized,
    restartCommand: buildDirectCommand(
      {
        path: materialized.path,
        resumeCommand: materialized.resumeCommand || null,
        resumeTool: materialized.resumeTool || null,
        sessionId: materialized.resumeSessionId || null,
        resumeSessionId: materialized.resumeSessionId || null,
      },
      { resume: true },
    ),
  };
}

function materializeWorkspaceManifest(manifest) {
  const normalized = normalizeWorkspaceManifest(manifest);
  const tabs = normalized.tabs.map((tab) => materializeWorkspaceTab(tab));
  return Object.fromEntries(
    Object.entries({
      version: normalized.version,
      workspaceId: normalized.workspaceId || undefined,
      title: normalized.title || undefined,
      machine: normalized.machine || undefined,
      capture: normalized.capture || undefined,
      projects: buildWorkspaceProjectGroups(normalized.tabs),
      tabs,
    }).filter(([, value]) => value !== undefined),
  );
}

function getObjectValue(record, ...keys) {
  for (const key of keys) {
    const value = record?.[key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return value;
    }
  }
  return null;
}

function getHostedWorkspaceId(workspace) {
  return normalizeOptionalString(workspace?.workspace_id ?? workspace?.workspaceId ?? workspace?.id);
}

function getHostedWorkspaceTitle(workspace) {
  return normalizeOptionalString(workspace?.title) || getHostedWorkspaceId(workspace);
}

function buildHostedWorkspaceSlotAssignment(workspace) {
  const workspaceId = getHostedWorkspaceId(workspace);
  if (!workspaceId) {
    return null;
  }
  const title = getHostedWorkspaceTitle(workspace);
  return {
    kind: "hosted-workspace",
    selector: title || workspaceId,
    workspaceId,
    title: title || undefined,
    hostedWorkspaceId: workspaceId,
  };
}

function buildWorkspaceFileSlotAssignment(manifest, manifestPath) {
  const workspaceId = normalizeOptionalString(manifest?.workspaceId);
  const title = normalizeOptionalString(manifest?.title) || workspaceId || undefined;
  return {
    kind: "workspace-file",
    selector: title || workspaceId || manifestPath,
    workspaceId: workspaceId || undefined,
    title,
    manifestPath,
  };
}

async function assignMatchingWorkspaceSlots(source, manifest, assignment, options = {}) {
  if (!assignment) {
    return {};
  }

  const slotNames = new Set();
  if (source.resolvedSlotName) {
    slotNames.add(source.resolvedSlotName);
  }

  const sourceWorkspaceIds = new Set(
    [
      manifest?.workspaceId,
      source.workspaceManifest?.workspaceId,
      getHostedWorkspaceId(source.hostedWorkspace),
      source.hostedWorkspaceId,
    ]
      .map((value) => normalizeOptionalString(value))
      .filter(Boolean),
  );
  const sourcePaths = new Set(
    [source.sourcePath, assignment.manifestPath]
      .map((value) => normalizeOptionalString(value))
      .filter(Boolean)
      .map((value) => path.resolve(value)),
  );

  const slotsResult = await loadWorkspaceSlots(options).catch(() => ({ slots: {} }));
  for (const [slotName, slot] of Object.entries(slotsResult.slots || {})) {
    if (!slot || typeof slot !== "object" || Array.isArray(slot)) {
      continue;
    }
    const slotIds = [
      slot.workspaceId,
      slot.hostedWorkspaceId,
      slot.selector,
    ]
      .map((value) => normalizeOptionalString(value))
      .filter(Boolean);
    const slotPath = normalizeOptionalString(slot.manifestPath);
    if (slotIds.some((value) => sourceWorkspaceIds.has(value)) || (slotPath && sourcePaths.has(path.resolve(slotPath)))) {
      slotNames.add(slotName);
    }
  }

  const assignedSlots = {};
  for (const slotName of slotNames) {
    assignedSlots[slotName] = (await setWorkspaceSlot(slotName, assignment, options)).slot;
  }
  return assignedSlots;
}

function normalizeEditableManifest(source, parsed) {
  const baseManifest = parsed.manifest
    ? {
        version: parsed.manifest.version,
        workspaceId: parsed.manifest.workspaceId,
        title: parsed.manifest.title,
        machine: parsed.manifest.machine,
        capture: parsed.manifest.capture,
        tabs: parsed.manifest.tabs.map((entry) => {
          const resume = resolveResumeMetadata(entry);
          return Object.fromEntries(
            Object.entries({
              title: normalizeOptionalString(entry.title) || undefined,
              path: entry.path,
              remoteUrl: normalizeOptionalString(entry.remoteUrl) || undefined,
              remoteBranch: normalizeOptionalString(entry.remoteBranch) || undefined,
              bootstrapCommand: normalizeOptionalString(entry.bootstrapCommand) || undefined,
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
        machine: source.workspaceManifest?.machine || null,
        capture: source.workspaceManifest?.capture || null,
        tabs: parsed.entries.map((entry) => {
          const resume = resolveResumeMetadata(entry);
          return Object.fromEntries(
            Object.entries({
              title: normalizeOptionalString(entry.title) || deriveBaseTitle(entry),
              path: entry.path,
              remoteUrl: normalizeOptionalString(entry.remoteUrl) || undefined,
              remoteBranch: normalizeOptionalString(entry.remoteBranch) || undefined,
              bootstrapCommand: normalizeOptionalString(entry.bootstrapCommand) || undefined,
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

async function findOrCreateHostedWorkspaceForIdea(ideaId, source, manifest, options = {}) {
  const existingWorkspace = await findHostedWorkspaceByLinkedIdea(ideaId, options);
  if (existingWorkspace) {
    return {
      workspace: existingWorkspace,
      created: false,
    };
  }

  const linkedIdea =
    source.sourceType === "hosted-idea"
      ? source.idea
      : getObjectValue(source.hostedWorkspace, "linked_idea", "linkedIdea");
  const title =
    manifest.title ||
    manifest.workspaceId ||
    source.title ||
    normalizeOptionalString(linkedIdea?.idea_title ?? linkedIdea?.ideaTitle) ||
    normalizeOptionalString(linkedIdea?.title) ||
    ideaId;
  const created = await createHostedWorkspaceForIdea({ title, ideaId }, options);
  return {
    workspace: created.workspace,
    created: true,
    createdPayload: created,
  };
}

async function persistIdeaBackedWorkspaceToLocalCache(ideaId, source, manifest, reason, options = {}) {
  const managedCache = await cacheManagedWorkspaceManifest(manifest, options);
  const assignment = buildWorkspaceFileSlotAssignment(manifest, managedCache.manifestPath);
  const assignedSlots = await assignMatchingWorkspaceSlots(source, manifest, assignment, options);
  return {
    persistedTo: "workspace-file",
    ideaId,
    promotedFromIdeaId: ideaId,
    hostedMigrationSkippedReason: reason instanceof Error ? reason.message : String(reason || "Hosted workspace API unavailable."),
    manifestPath: managedCache.manifestPath,
    registryPath: managedCache.registryPath,
    assignedSlots,
    managedCache,
    manifest,
  };
}

function parseLedgerSelectorArgs(
  argv = [],
  { commandName, requirePath = false, requireSelector = true, allowAppend = false, allowHere = false, allowCurrentCodex = false } = {},
) {
  const options = {
    json: false,
    all: false,
    append: false,
    here: false,
    currentCodex: false,
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
    if (allowAppend && arg === "--append") {
      options.append = true;
      continue;
    }
    if (allowHere && arg === "--here") {
      options.here = true;
      continue;
    }
    if (allowCurrentCodex && arg === "--current-codex") {
      options.currentCodex = true;
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
      } else if (arg === "--remote-url") {
        options.remoteUrl = next;
      } else if (arg === "--remote-branch") {
        options.remoteBranch = next;
      } else if (arg === "--bootstrap-command") {
        options.bootstrapCommand = next;
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
  if (options.here && options.path) {
    throw new Error("Use either `--path` or `--here`, not both.");
  }
  if (requirePath && !options.path && !options.here) {
    throw new Error(`\`--path\` or \`--here\` is required for \`${commandName}\`.`);
  }
  if (options.here) {
    options.path = path.resolve(process.cwd());
  }
  if (options.path) {
    options.path = validateAbsolutePath(options.path, "--path");
  }
  if (options.currentCodex) {
    if (options.resumeCommand || options.resumeTool || options.resumeSessionId) {
      throw new Error("`--current-codex` cannot be combined with explicit resume metadata.");
    }
    Object.assign(options, resolveCurrentCodexResume());
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
    allowAppend: true,
    allowHere: true,
    allowCurrentCodex: true,
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
      } else if (arg === "--remote-url") {
        options.remoteUrl = next;
      } else if (arg === "--remote-branch") {
        options.remoteBranch = next;
      } else if (arg === "--bootstrap-command") {
        options.bootstrapCommand = next;
      } else if (arg === "--machine-id") {
        options.machineId = next;
      } else if (arg === "--machine-label") {
        options.machineLabel = next;
      } else if (arg === "--platform") {
        options.platform = next;
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
  const normalizedPath = validateAbsolutePath(options.path, "--path");
  const normalizedTitle = normalizeOptionalString(options.title);
  const explicitResumeRequested = Boolean(
    normalizeOptionalString(options.resumeCommand) ||
      normalizeOptionalString(options.resumeTool) ||
      normalizeOptionalString(options.resumeSessionId),
  );
  const requestedResume = explicitResumeRequested
    ? resolveResumeMetadata({
        resumeCommand: options.resumeCommand,
        resumeTool: options.resumeTool,
        resumeSessionId: options.resumeSessionId,
      })
    : null;

  const buildTab = (existingTab = null) => {
    const existingResume = resolveResumeMetadata(existingTab || {});
    const chosenResume = requestedResume || existingResume;
    return Object.fromEntries(
      Object.entries({
        title: normalizedTitle || normalizeOptionalString(existingTab?.title) || undefined,
        path: normalizedPath,
        remoteUrl: normalizeOptionalString(options.remoteUrl) || normalizeOptionalString(existingTab?.remoteUrl) || undefined,
        remoteBranch:
          normalizeOptionalString(options.remoteBranch) || normalizeOptionalString(existingTab?.remoteBranch) || undefined,
        bootstrapCommand:
          normalizeOptionalString(options.bootstrapCommand) ||
          normalizeOptionalString(existingTab?.bootstrapCommand) ||
          undefined,
        resumeCommand: chosenResume.resumeCommand || undefined,
        resumeTool: chosenResume.resumeTool || undefined,
        resumeSessionId: chosenResume.resumeSessionId || undefined,
        codexSessionId: chosenResume.resumeTool === "codex" ? chosenResume.resumeSessionId || undefined : undefined,
        claudeSessionId: chosenResume.resumeTool === "claude" ? chosenResume.resumeSessionId || undefined : undefined,
      }).filter(([, value]) => value !== undefined),
    );
  };

  const nextTab = buildTab();
  if (options.append) {
    nextManifest.tabs.push(nextTab);
    return {
      manifest: normalizeWorkspaceManifest(nextManifest),
      added: true,
      updated: false,
      unchanged: false,
      mutation: "added",
      tab: nextTab,
    };
  }

  const pathMatchIndexes = nextManifest.tabs
    .map((tab, index) => (tab.path === normalizedPath ? index : -1))
    .filter((index) => index >= 0);
  let matchedIndexes = [];

  if (normalizedTitle) {
    matchedIndexes = pathMatchIndexes.filter(
      (index) => normalizeOptionalString(nextManifest.tabs[index]?.title) === normalizedTitle,
    );
    if (matchedIndexes.length === 0 && pathMatchIndexes.length === 1) {
      matchedIndexes = pathMatchIndexes;
    }
  } else if (pathMatchIndexes.length > 0) {
    const uniqueTitles = new Set(
      pathMatchIndexes.map((index) => normalizeOptionalString(nextManifest.tabs[index]?.title) || ""),
    );
    if (pathMatchIndexes.length === 1 || uniqueTitles.size <= 1) {
      matchedIndexes = pathMatchIndexes;
    } else {
      throw new Error(
        "Multiple saved tabs already use this path. Re-run with `--title` to target one tab or `--append` to add another.",
      );
    }
  }

  if (matchedIndexes.length === 0) {
    nextManifest.tabs.push(nextTab);
    return {
      manifest: normalizeWorkspaceManifest(nextManifest),
      added: true,
      updated: false,
      unchanged: false,
      mutation: "added",
      tab: nextTab,
    };
  }

  const [primaryIndex, ...duplicateIndexes] = matchedIndexes;
  const currentTab = nextManifest.tabs[primaryIndex];
  const updatedTab = buildTab(currentTab);
  const currentMaterialized = JSON.stringify(materializeWorkspaceTab(currentTab));
  const updatedMaterialized = JSON.stringify(materializeWorkspaceTab(updatedTab));
  nextManifest.tabs[primaryIndex] = updatedTab;

  if (duplicateIndexes.length > 0) {
    const removalSet = new Set(duplicateIndexes);
    nextManifest.tabs = nextManifest.tabs.filter((_, index) => !removalSet.has(index));
  }

  const changed = currentMaterialized !== updatedMaterialized || duplicateIndexes.length > 0;
  return {
    manifest: normalizeWorkspaceManifest(nextManifest),
    added: false,
    updated: changed,
    unchanged: !changed,
    mutation: changed ? "updated" : "unchanged",
    tab: updatedTab,
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
    const ideaId = watchTargets.syncIdeaSelector;
    let promoted;
    try {
      promoted = await findOrCreateHostedWorkspaceForIdea(ideaId, source, manifest, options);
    } catch (error) {
      return persistIdeaBackedWorkspaceToLocalCache(ideaId, source, manifest, error, options);
    }
    const workspaceId = getHostedWorkspaceId(promoted.workspace);
    if (!workspaceId) {
      throw new Error(`Hosted workspace for idea ${ideaId} did not include a workspace id.`);
    }

    const previousWorkspace = promoted.created
      ? promoted.workspace
      : (await fetchHostedWorkspacePayload(workspaceId, options)).workspace;
    const state = buildHostedWorkspaceState(manifest, {
      previousWorkspace,
      capturedAt: manifest.capture?.capturedAt,
      updatedAt: new Date().toISOString(),
    });
    const pushResult = await pushHostedWorkspaceState(workspaceId, state, options);
    const cachedManifest = buildWorkspaceManifestFromHostedWorkspacePayload(pushResult);
    const managedCache = await cacheManagedWorkspaceManifest(cachedManifest, options);
    const workspaceForSlot = pushResult.workspace || promoted.workspace;
    const assignedSlots = await assignMatchingWorkspaceSlots(
      source,
      cachedManifest,
      buildHostedWorkspaceSlotAssignment(workspaceForSlot),
      options,
    );
    return {
      persistedTo: "hosted-workspace",
      ideaId,
      promotedFromIdeaId: ideaId,
      createdHostedWorkspace: promoted.created,
      workspaceId,
      pushResult,
      assignedSlots,
      managedCache,
      manifest: cachedManifest,
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
  orp workspace add-tab <name-or-id> (--path <absolute-path> | --here) [--title <title>] [--remote-url <git-url>] [--remote-branch <branch>] [--bootstrap-command <text>] [--resume-command <text> | --resume-tool <codex|claude> --resume-session-id <id> | --current-codex] [--append] [--json]
  orp workspace add-tab --hosted-workspace-id <workspace-id> (--path <absolute-path> | --here) [--json]
  orp workspace add-tab --workspace-file <path> (--path <absolute-path> | --here) [--json]

Options:
  --path <absolute-path> Add this local project path to the saved workspace
  --here                 Use the current working directory as the saved path
  --title <title>        Optional saved tab title
  --remote-url <git-url> Optional git remote URL for cross-machine setup
  --remote-branch <branch> Optional default branch to clone on another machine
  --bootstrap-command <text> Optional setup command like \`npm install\` or \`uv sync\`
  --resume-command <text> Exact saved resume command, like \`codex resume ...\` or \`claude --resume ...\`
  --resume-tool <tool>   Build the resume command from \`codex\` or \`claude\`
  --resume-session-id <id> Resume session id to save with the tab
  --current-codex        Save the current \`CODEX_THREAD_ID\` as a Codex resume target
  --append               Add another saved session for the same project path instead of updating the existing one
  --hosted-workspace-id <id> Edit a first-class hosted workspace directly
  --workspace-file <path> Edit a local structured workspace manifest
  --json                 Print the updated workspace edit result as JSON
  -h, --help             Show this help text

Examples:
  orp workspace add-tab main --path /absolute/path/to/new-project
  orp workspace add-tab main --here --current-codex
  orp workspace add-tab main --path /absolute/path/to/new-project --resume-command "codex resume 019d..."
  orp workspace add-tab main --path /absolute/path/to/new-project --resume-tool claude --resume-session-id claude-456
  orp workspace add-tab main --path /absolute/path/to/new-project --title "second active thread" --resume-tool codex --resume-session-id 019d... --append
  orp workspace add-tab main --path /absolute/path/to/new-project --remote-url git@github.com:org/new-project.git --bootstrap-command "npm install"
`);
}

function printWorkspaceCreateHelp() {
  console.log(`ORP workspace create

Usage:
  orp workspace create <title-slug> [--workspace-file <path>] [--slot <main|offhand>] [--machine-id <id>] [--machine-label <label>] [--platform <platform>] [--path <absolute-path>] [--remote-url <git-url>] [--remote-branch <branch>] [--bootstrap-command <text>] [--resume-command <text> | --resume-tool <codex|claude> --resume-session-id <id>] [--json]

Options:
  <title-slug>           Required local workspace title using lowercase letters, numbers, and dashes only
  --workspace-file <path> Create the workspace manifest at an explicit local path instead of the managed ORP workspace directory
  --slot <main|offhand>  Optionally assign the created workspace to a named slot
  --machine-id <id>      Optional stable machine id for this workspace ledger (defaults to this machine)
  --machine-label <label> Optional human label for the current machine
  --platform <platform>  Optional platform label like darwin, linux, or win32
  --path <absolute-path> Optionally seed the workspace with one saved path immediately
  --remote-url <git-url> Optional git remote URL for the first saved tab
  --remote-branch <branch> Optional default branch to clone on another machine
  --bootstrap-command <text> Optional setup command like \`npm install\` or \`uv sync\`
  --resume-command <text> Exact saved resume command, like \`codex resume ...\` or \`claude --resume ...\`
  --resume-tool <tool>   Build the resume command from \`codex\` or \`claude\`
  --resume-session-id <id> Resume session id to save with the first tab
  --json                 Print the created workspace result as JSON
  -h, --help             Show this help text

Examples:
  orp workspace create main-cody-1
  orp workspace create main-cody-1 --slot main
  orp workspace create research-lab --path /absolute/path/to/research-lab
  orp workspace create research-lab --path /absolute/path/to/research-lab --resume-tool claude --resume-session-id 469d99b2-2997-42bf-a8f5-3812c808ef29
  orp workspace create mac-main --machine-label "Mac Studio" --path /absolute/path/to/research-lab --remote-url git@github.com:org/research-lab.git --bootstrap-command "npm install"
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
  orp workspace remove-tab main --path /absolute/path/to/frg-site --resume-session-id 019d348d-5031-78e1-9840-a66deaac33ae
  orp workspace remove-tab main --title frg-site
`);
}

function summarizeWorkspaceLedgerMutation(result) {
  const lines = [
    `Workspace: ${result.workspaceTitle || result.workspaceId || "workspace"}`,
    `Action: ${result.action}`,
    ...(result.action === "add-tab" && result.mutation ? [`Result: ${result.mutation}`] : []),
    `Saved tabs: ${result.tabCount}`,
  ];

  if (result.action === "add-tab") {
    lines.push(`Tab: ${result.tab?.title || path.basename(result.tab?.path || "") || result.tab?.path}`);
    lines.push(`Path: ${result.tab?.path}`);
    if (result.tab?.remoteUrl) {
      lines.push(`Remote: ${result.tab.remoteUrl}`);
    }
    if (result.tab?.bootstrapCommand) {
      lines.push(`Bootstrap: ${result.tab.bootstrapCommand}`);
    }
    if (result.tab?.resumeCommand && result.tab?.restartCommand) {
      lines.push(`Resume: ${result.tab.restartCommand}`);
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
    if (result.promotedFromIdeaId) {
      lines.push(`Linked idea: ${result.promotedFromIdeaId}`);
    }
  } else if (result.persistedTo === "workspace-file") {
    lines.push(`Saved file: ${result.manifestPath}`);
    if (result.hostedMigrationSkippedReason) {
      lines.push(`Hosted migration skipped: ${result.hostedMigrationSkippedReason}`);
    }
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
    mutation: mutated.mutation || null,
    tabCount: finalManifest.tabs.length,
    tab: buildWorkspaceResultTab(mutated.tab),
    removedTabs: (mutated.removedTabs || []).map((tab) => buildWorkspaceResultTab(tab)),
    persistedTo: persisted.persistedTo,
    ideaId: persisted.ideaId || null,
    promotedFromIdeaId: persisted.promotedFromIdeaId || null,
    createdHostedWorkspace: persisted.createdHostedWorkspace || false,
    hostedMigrationSkippedReason: persisted.hostedMigrationSkippedReason || null,
    workspaceSourceId: persisted.workspaceId || null,
    manifestPath: persisted.manifestPath || null,
    managedCachePath: persisted.managedCache?.manifestPath || null,
    assignedSlot: persisted.assignedSlot || Object.values(persisted.assignedSlots || {})[0] || null,
    assignedSlots: persisted.assignedSlots || null,
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
          remoteUrl: normalizeOptionalString(options.remoteUrl) || undefined,
          remoteBranch: normalizeOptionalString(options.remoteBranch) || undefined,
          bootstrapCommand: normalizeOptionalString(options.bootstrapCommand) || undefined,
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
    machine: buildCurrentMachineMetadata(options),
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
  if (result.manifest?.machine?.machineLabel) {
    lines.push(`Machine: ${result.manifest.machine.machineLabel}${result.manifest.machine.platform ? ` (${result.manifest.machine.platform})` : ""}`);
  }
  if (result.slot?.slot) {
    lines.push(`Slot: ${result.slot.slot}`);
  }
  process.stdout.write(`${lines.join("\n")}\n`);
  return 0;
}
