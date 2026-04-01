import path from "node:path";
import process from "node:process";

import { fetchHostedWorkspacesPayload } from "./orp.js";
import {
  isManagedWorkspaceManifestPath,
  listTrackedWorkspaces,
  loadWorkspaceSlots,
  normalizeWorkspaceSlotName,
} from "./registry.js";

function normalizeOptionalString(value) {
  if (value == null) {
    return null;
  }
  const trimmed = String(value).trim();
  return trimmed.length > 0 ? trimmed : null;
}

function slugify(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized || null;
}

function countHostedResumeSessions(workspace) {
  const tabs = Array.isArray(workspace?.state?.tabs)
    ? workspace.state.tabs
    : Array.isArray(workspace?.tabs)
      ? workspace.tabs
      : Array.isArray(workspace?.manifest?.tabs)
        ? workspace.manifest.tabs
        : [];
  return tabs.reduce((count, tab) => {
    const sessionId = normalizeOptionalString(
      tab?.resume_session_id ??
        tab?.resumeSessionId ??
        tab?.codex_session_id ??
        tab?.codexSessionId ??
        tab?.sessionId,
    );
    return sessionId ? count + 1 : count;
  }, 0);
}

function buildHostedWorkspaceSummary(workspace) {
  const linkedIdea = workspace?.linked_idea || workspace?.linkedIdea || {};
  const metrics = workspace?.metrics || {};
  return {
    workspaceId: normalizeOptionalString(workspace?.workspace_id ?? workspace?.id),
    title: normalizeOptionalString(workspace?.title),
    visibility: normalizeOptionalString(workspace?.visibility),
    ideaId: normalizeOptionalString(linkedIdea.idea_id ?? linkedIdea.ideaId),
    tabCount:
      Number.isInteger(metrics.tab_count) ? metrics.tab_count : Number.isInteger(metrics.tabCount) ? metrics.tabCount : 0,
    codexSessionCount: countHostedResumeSessions(workspace),
    updatedAt: normalizeOptionalString(workspace?.updated_at_utc ?? workspace?.updatedAt),
    source: normalizeOptionalString(workspace?.source_kind) || "hosted",
  };
}

function buildLocalWorkspaceSummary(workspace) {
  return {
    workspaceId: normalizeOptionalString(workspace?.workspaceId),
    title: normalizeOptionalString(workspace?.title),
    status: normalizeOptionalString(workspace?.status) || "ok",
    manifestPath: normalizeOptionalString(workspace?.manifestPath),
    tabCount: Number.isInteger(workspace?.tabCount) ? workspace.tabCount : 0,
    codexSessionCount: Number.isInteger(workspace?.codexSessionCount) ? workspace.codexSessionCount : 0,
    resumeSessions: Array.isArray(workspace?.resumeSessions) ? workspace.resumeSessions : [],
    updatedAt: normalizeOptionalString(workspace?.updatedAt),
    managedCache: isManagedWorkspaceManifestPath(workspace?.manifestPath),
    host: normalizeOptionalString(workspace?.host),
    captureMode: normalizeOptionalString(workspace?.captureMode),
    error: normalizeOptionalString(workspace?.error),
  };
}

function mergeKeyForWorkspace(summary) {
  const workspaceId = normalizeOptionalString(summary?.workspaceId);
  if (workspaceId) {
    return `id:${workspaceId}`;
  }
  const titleSlug = slugify(summary?.title);
  if (titleSlug) {
    return `title:${titleSlug}`;
  }
  const manifestPath = normalizeOptionalString(summary?.manifestPath);
  if (manifestPath) {
    return `path:${path.resolve(manifestPath)}`;
  }
  return `unknown:${Math.random().toString(36).slice(2, 10)}`;
}

function timestampsSortValue(record) {
  return Date.parse(record?.updatedAt || "") || 0;
}

function preferNewerSummary(current, candidate) {
  if (!current) {
    return candidate;
  }
  return timestampsSortValue(candidate) > timestampsSortValue(current) ? candidate : current;
}

function inferSyncStatus(entry) {
  if (entry.hosted && entry.local) {
    if (entry.local.status !== "ok") {
      return entry.local.status;
    }
    const matches =
      normalizeOptionalString(entry.hosted.workspaceId) === normalizeOptionalString(entry.local.workspaceId) &&
      normalizeOptionalString(entry.hosted.title) === normalizeOptionalString(entry.local.title) &&
      Number(entry.hosted.tabCount || 0) === Number(entry.local.tabCount || 0) &&
      Number(entry.hosted.codexSessionCount || 0) === Number(entry.local.codexSessionCount || 0);
    if (matches) {
      return "synced";
    }
    return entry.local.managedCache ? "needs-sync" : "linked";
  }
  if (entry.hosted) {
    return "hosted-only";
  }
  if (entry.local?.managedCache) {
    return "local-cache-only";
  }
  return "local-only";
}

function workspaceMatchesSlot(workspace, slot) {
  if (!workspace || !slot) {
    return false;
  }

  const slotKind = normalizeOptionalString(slot.kind);
  if (slotKind === "workspace-file") {
    return (
      normalizeOptionalString(workspace.local?.manifestPath) === normalizeOptionalString(slot.manifestPath) ||
      normalizeOptionalString(workspace.workspaceId) === normalizeOptionalString(slot.workspaceId)
    );
  }

  if (slotKind === "hosted-idea") {
    return (
      normalizeOptionalString(workspace.hosted?.ideaId) === normalizeOptionalString(slot.ideaId) ||
      normalizeOptionalString(workspace.workspaceId) === normalizeOptionalString(slot.workspaceId)
    );
  }

  if (slotKind === "hosted-workspace") {
    const slotWorkspaceId = normalizeOptionalString(slot.hostedWorkspaceId) || normalizeOptionalString(slot.workspaceId);
    return normalizeOptionalString(workspace.workspaceId) === slotWorkspaceId;
  }

  return false;
}

export function applyWorkspaceSlotsToInventory(result, slots = {}) {
  const normalizedSlots = {};
  for (const [slotName, slot] of Object.entries(slots || {})) {
    const normalizedSlotName = normalizeWorkspaceSlotName(slotName);
    if (normalizedSlotName && slot && typeof slot === "object" && !Array.isArray(slot)) {
      normalizedSlots[normalizedSlotName] = slot;
    }
  }

  const workspaces = Array.isArray(result?.workspaces) ? result.workspaces : [];
  const annotatedWorkspaces = workspaces.map((workspace) => {
    const slotNames = Object.entries(normalizedSlots)
      .filter(([, slot]) => workspaceMatchesSlot(workspace, slot))
      .map(([slotName]) => slotName)
      .sort();
    return {
      ...workspace,
      slots: slotNames,
    };
  });

  const hasExplicitMain = annotatedWorkspaces.some((workspace) => workspace.slots.includes("main"));
  if (!hasExplicitMain && annotatedWorkspaces.length === 1) {
    annotatedWorkspaces[0] = {
      ...annotatedWorkspaces[0],
      slots: [...annotatedWorkspaces[0].slots, "main"],
      implicitMain: true,
    };
  }

  return {
    ...result,
    slots: normalizedSlots,
    workspaces: annotatedWorkspaces,
  };
}

export function buildWorkspaceInventory({ localResult, hostedResult, hostedError = null }) {
  const merged = new Map();
  const localWorkspaces = Array.isArray(localResult?.workspaces) ? localResult.workspaces : [];
  const hostedWorkspaces = Array.isArray(hostedResult?.workspaces) ? hostedResult.workspaces : [];

  for (const workspace of hostedWorkspaces) {
    const hosted = buildHostedWorkspaceSummary(workspace);
    const key = mergeKeyForWorkspace(hosted);
    const current = merged.get(key) || {};
    merged.set(key, {
      ...current,
      workspaceId: hosted.workspaceId || current.workspaceId || null,
      title: hosted.title || current.title || hosted.workspaceId || null,
      hosted: preferNewerSummary(current.hosted, hosted),
      sources: {
        hosted: true,
        local: Boolean(current.local),
      },
    });
  }

  for (const workspace of localWorkspaces) {
    const local = buildLocalWorkspaceSummary(workspace);
    const key = mergeKeyForWorkspace(local);
    const current = merged.get(key) || {};
    const preferredLocal = preferNewerSummary(current.local, local);
    merged.set(key, {
      ...current,
      workspaceId: preferredLocal.workspaceId || current.workspaceId || null,
      title:
        preferredLocal.title ||
        current.title ||
        preferredLocal.workspaceId ||
        path.basename(preferredLocal.manifestPath || ""),
      local: preferredLocal,
      sources: {
        hosted: Boolean(current.hosted),
        local: true,
      },
    });
  }

  const workspaces = [...merged.values()]
    .map((entry) => ({
      workspaceId: entry.workspaceId,
      title: entry.title,
      availability:
        entry.hosted && entry.local ? "hosted+local" : entry.hosted ? "hosted" : "local",
      syncStatus: inferSyncStatus(entry),
      sources: entry.sources,
      hosted: entry.hosted || null,
      local: entry.local || null,
    }))
    .sort((left, right) => {
      const dateDelta = timestampsSortValue(right.hosted || right.local) - timestampsSortValue(left.hosted || left.local);
      if (dateDelta !== 0) {
        return dateDelta;
      }
      return String(left.title || left.workspaceId || "").localeCompare(String(right.title || right.workspaceId || ""));
    });

  return {
    registryPath: localResult?.registryPath || null,
    hostedSource: normalizeOptionalString(hostedResult?.source) || null,
    hostedError: normalizeOptionalString(hostedError),
    workspaces,
  };
}

export function summarizeWorkspaceInventory(result) {
  const workspaces = Array.isArray(result?.workspaces) ? result.workspaces : [];
  const hostedCount = workspaces.filter((workspace) => workspace.sources?.hosted).length;
  const localCount = workspaces.filter((workspace) => workspace.sources?.local).length;
  const syncedCount = workspaces.filter((workspace) => workspace.syncStatus === "synced").length;
  const slotNames = Object.keys(result?.slots || {}).filter(Boolean).sort();

  const lines = [
    `Workspace inventory: ${workspaces.length}`,
    `Hosted available: ${hostedCount}`,
    `Local available: ${localCount}`,
  ];
  if (result?.registryPath) {
    lines.push(`Local registry: ${result.registryPath}`);
  }
  if (result?.hostedSource) {
    lines.push(`Hosted source: ${result.hostedSource}`);
  }
  lines.push(`Synced pairs: ${syncedCount}`);
  if (slotNames.length > 0) {
    lines.push(`Named slots: ${slotNames.join(", ")}`);
  }

  if (result?.hostedError) {
    lines.push("");
    lines.push(`Hosted unavailable: ${result.hostedError}`);
  }

  if (workspaces.length === 0) {
    lines.push("");
    lines.push("No workspaces yet.");
    lines.push("Start one locally without an account or sync a hosted workspace later.");
    lines.push("  orp workspace create main-cody-1");
    return lines.join("\n");
  }

  workspaces.forEach((workspace, index) => {
    lines.push("");
    lines.push(`[${index + 1}] ${formatWorkspaceHeading(workspace)}`);
    if (workspace.slots?.length) {
      lines.push(
        `Slots: ${workspace.slots.join(", ")}${workspace.implicitMain ? " (main inferred because this is the only workspace)" : ""}`,
      );
    }
    lines.push(`Availability: ${workspace.availability}`);
    lines.push(`Sync: ${workspace.syncStatus}`);
    if (workspace.hosted) {
      lines.push(
        `Hosted: ORP${workspace.hosted.ideaId ? ` (idea ${workspace.hosted.ideaId})` : ""}, tabs ${workspace.hosted.tabCount || 0}, updated ${workspace.hosted.updatedAt || "unknown"}`,
      );
    }
    if (workspace.local) {
      lines.push(
        `Local: ${workspace.local.manifestPath}${workspace.local.managedCache ? " [managed cache]" : ""}`,
      );
      lines.push(`Local status: ${workspace.local.status}, tabs ${workspace.local.tabCount || 0}`);
    }
  });

  return lines.join("\n");
}

export function parseWorkspaceListArgs(argv = []) {
  const options = {
    json: false,
  };

  for (const arg of argv) {
    if (arg === "-h" || arg === "--help") {
      options.help = true;
      continue;
    }
    if (arg === "--json") {
      options.json = true;
      continue;
    }
    throw new Error(`unexpected argument: ${arg}`);
  }

  return options;
}

function formatWorkspaceHeading(workspace) {
  const title = normalizeOptionalString(workspace.title);
  const workspaceId = normalizeOptionalString(workspace.workspaceId);
  if (title && workspaceId && title !== workspaceId) {
    return `${title} [${workspaceId}]`;
  }
  if (title) {
    return title;
  }
  if (workspaceId) {
    return workspaceId;
  }
  return path.basename(workspace.manifestPath);
}

function summarizeResumeSessions(workspace) {
  const sessions = Array.isArray(workspace.resumeSessions)
    ? workspace.resumeSessions
    : Array.isArray(workspace.codexSessions)
      ? workspace.codexSessions
      : [];
  const lines = [`Saved resume sessions: ${workspace.codexSessionCount || 0}`];
  for (const session of sessions.slice(0, 5)) {
    const label = normalizeOptionalString(session.title) || path.basename(session.path || "") || "(untitled tab)";
    lines.push(`  ${label}: ${normalizeOptionalString(session.resumeCommand) || normalizeOptionalString(session.codexSessionId) || "(unknown)"}`);
  }
  if (sessions.length > 5) {
    lines.push(`  ... ${sessions.length - 5} more`);
  }
  return lines;
}

export function summarizeTrackedWorkspaces(result) {
  if (!result.workspaces || result.workspaces.length === 0) {
    return [
      "No local tracked workspaces yet.",
      `Registry: ${result.registryPath}`,
      "",
      "Create one with:",
      "  orp workspace create main-cody-1",
      "",
      "For the combined hosted + local inventory, use:",
      "  orp workspace list",
    ].join("\n");
  }

  const lines = [`Local tracked workspaces: ${result.workspaces.length}`, `Registry: ${result.registryPath}`];

  result.workspaces.forEach((workspace, index) => {
    lines.push("");
    lines.push(`[${index + 1}] ${formatWorkspaceHeading(workspace)}`);
    lines.push(`Status: ${workspace.status}`);
    lines.push(`File: ${workspace.manifestPath}`);
    lines.push(`Saved tabs: ${workspace.tabCount || 0}`);

    if (workspace.captureMode) {
      lines.push(`Capture mode: ${workspace.captureMode}`);
    }
    if (workspace.host) {
      lines.push(`Host: ${workspace.host}`);
    }
    if (workspace.capturedAt) {
      lines.push(`Captured at: ${workspace.capturedAt}`);
    }
    if (workspace.trackingStartedAt) {
      lines.push(`Tracking since: ${workspace.trackingStartedAt}`);
    }
    if (workspace.windowIndex != null || workspace.windowId != null) {
      lines.push(
        `Window: #${workspace.windowIndex != null ? workspace.windowIndex : "?"}${workspace.windowId != null ? ` (id ${workspace.windowId})` : ""}`,
      );
    }
    if (workspace.updatedAt) {
      lines.push(`Registry updated: ${workspace.updatedAt}`);
    }

    lines.push(...summarizeResumeSessions(workspace));

    if (workspace.error) {
      lines.push(`Error: ${workspace.error}`);
    }
  });

  return lines.join("\n");
}

function printWorkspaceListHelp() {
  console.log(`ORP workspace list

Usage:
  orp workspace list [--json]

Options:
  --json       Print tracked workspace metadata as JSON
  -h, --help   Show this help text

Notes:
  - This shows one merged inventory of hosted ORP workspaces and local manifests on this Mac.
  - Hosted workspaces are labeled separately from local manifests.
  - Syncing or editing a hosted workspace stores a managed local cache so it can show up on both sides.
  - Slot labels show which workspace is currently assigned as \`main\` or \`offhand\`.
`);
}

export async function runWorkspaceList(argv = process.argv.slice(2)) {
  const options = parseWorkspaceListArgs(argv);
  if (options.help) {
    printWorkspaceListHelp();
    return 0;
  }

  const localResult = await listTrackedWorkspaces();
  let hostedResult = { source: null, workspaces: [] };
  let hostedError = null;
  try {
    hostedResult = await fetchHostedWorkspacesPayload();
  } catch (error) {
    hostedError = error instanceof Error ? error.message : String(error);
  }

  let result = buildWorkspaceInventory({
    localResult,
    hostedResult,
    hostedError,
  });
  try {
    const slotsResult = await loadWorkspaceSlots();
    result = applyWorkspaceSlotsToInventory(result, slotsResult.slots);
  } catch {
    result = applyWorkspaceSlotsToInventory(result, {});
  }

  if (options.json) {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return 0;
  }

  process.stdout.write(`${summarizeWorkspaceInventory(result)}\n`);
  return 0;
}
