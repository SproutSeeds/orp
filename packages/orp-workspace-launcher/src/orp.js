import fs from "node:fs/promises";
import syncFs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

import { extractStructuredWorkspaceFromNotes, parseWorkspaceSource } from "./core-plan.js";
import { listTrackedWorkspaces, loadWorkspaceSlots, normalizeWorkspaceSlotName } from "./registry.js";

const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));

function runCommand(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env || process.env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      resolve({ code: code == null ? 1 : code, stdout, stderr });
    });
  });
}

function resolveOrpInvocation(options = {}) {
  if (options.orpCommand) {
    return {
      command: options.orpCommand,
      prefixArgs: [],
    };
  }

  const bundledBin = path.resolve(MODULE_DIR, "../../../bin/orp.js");
  if (syncFs.existsSync(bundledBin)) {
    return {
      command: process.execPath,
      prefixArgs: [bundledBin],
    };
  }

  return {
    command: "orp",
    prefixArgs: [],
  };
}

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

function getObjectValue(record, ...keys) {
  for (const key of keys) {
    const value = record?.[key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return value;
    }
  }
  return null;
}

function getArrayValue(record, ...keys) {
  for (const key of keys) {
    const value = record?.[key];
    if (Array.isArray(value)) {
      return value;
    }
  }
  return [];
}

function getTextValue(record, ...keys) {
  for (const key of keys) {
    const normalized = normalizeOptionalString(record?.[key]);
    if (normalized) {
      return normalized;
    }
  }
  return null;
}

function parseOrpJsonResult(result, fallbackError) {
  if (result.code !== 0) {
    throw new Error(result.stderr.trim() || result.stdout.trim() || fallbackError);
  }

  try {
    return JSON.parse(result.stdout);
  } catch (error) {
    throw new Error(`Failed to parse ORP JSON output: ${error instanceof Error ? error.message : String(error)}`);
  }
}

export async function fetchIdeaPayload(ideaId, options = {}) {
  const invocation = resolveOrpInvocation(options);
  const args = [...invocation.prefixArgs, "idea", "show", "--json"];
  if (options.baseUrl) {
    args.push("--base-url", options.baseUrl);
  }
  args.push(ideaId);

  const result = await runCommand(invocation.command, args, options);
  const payload = parseOrpJsonResult(result, "Failed to fetch ORP idea.");

  if (!payload || payload.ok !== true || !payload.idea) {
    throw new Error("ORP returned an unexpected idea payload.");
  }

  return payload;
}

export async function fetchIdeasPayload(options = {}) {
  const invocation = resolveOrpInvocation(options);
  const items = [];
  let cursor = "";

  for (;;) {
    const args = [...invocation.prefixArgs, "ideas", "list", "--limit", "200", "--json"];
    if (options.baseUrl) {
      args.push("--base-url", options.baseUrl);
    }
    if (cursor) {
      args.push("--cursor", cursor);
    }

    const result = await runCommand(invocation.command, args, options);
    const payload = parseOrpJsonResult(result, "Failed to fetch ORP ideas.");
    const pageItems = Array.isArray(payload?.ideas) ? payload.ideas : [];
    items.push(...pageItems.filter((row) => row && typeof row === "object" && !Array.isArray(row)));
    cursor = normalizeOptionalString(payload?.cursor);
    if (!payload?.has_more || !cursor) {
      break;
    }
  }

  return {
    ok: true,
    ideas: items,
  };
}

export async function fetchHostedWorkspacesPayload(options = {}) {
  const invocation = resolveOrpInvocation(options);
  const items = [];
  let cursor = "";
  let source = "";

  for (;;) {
    const args = [...invocation.prefixArgs, "workspaces", "list", "--limit", "200", "--json"];
    if (options.baseUrl) {
      args.push("--base-url", options.baseUrl);
    }
    if (cursor) {
      args.push("--cursor", cursor);
    }

    const result = await runCommand(invocation.command, args, options);
    const payload = parseOrpJsonResult(result, "Failed to fetch ORP workspaces.");
    const pageItems = Array.isArray(payload?.workspaces) ? payload.workspaces : [];
    items.push(...pageItems.filter((row) => row && typeof row === "object" && !Array.isArray(row)));
    source = normalizeOptionalString(payload?.source) || source;
    cursor = normalizeOptionalString(payload?.cursor);
    if (!payload?.has_more || !cursor) {
      break;
    }
  }

  return {
    ok: true,
    source: source || "hosted",
    workspaces: items,
  };
}

function buildWorkspaceTitleFromIdea(idea, manifest) {
  return normalizeOptionalString(manifest?.title) || normalizeOptionalString(idea?.title) || null;
}

function buildWorkspaceIdFromIdea(idea, manifest) {
  return normalizeOptionalString(manifest?.workspaceId) || normalizeOptionalString(idea?.id) || null;
}

function selectorForms(value) {
  const exact = normalizeOptionalString(value);
  const lower = exact ? exact.toLowerCase() : null;
  const slug = exact ? slugify(exact) : null;
  return { exact, lower, slug };
}

function matchQuality(selector, candidate) {
  const selectorFormsValue = selectorForms(selector);
  const candidates = [candidate].flat().filter(Boolean);
  let best = 0;
  for (const value of candidates) {
    const candidateForms = selectorForms(value);
    if (!candidateForms.exact) {
      continue;
    }
    if (selectorFormsValue.exact === candidateForms.exact) {
      best = Math.max(best, 40);
    } else if (selectorFormsValue.lower && selectorFormsValue.lower === candidateForms.lower) {
      best = Math.max(best, 35);
    } else if (selectorFormsValue.slug && selectorFormsValue.slug === candidateForms.slug) {
      best = Math.max(best, 20);
    }
  }
  return best;
}

function extractIdeaWorkspaceCandidate(idea) {
  if (!idea || typeof idea !== "object" || Array.isArray(idea)) {
    return null;
  }
  const notes = typeof idea.notes === "string" ? idea.notes : "";
  let parsed;
  try {
    parsed = parseWorkspaceSource({
      sourceType: "hosted-idea",
      sourceLabel: normalizeOptionalString(idea.title) || normalizeOptionalString(idea.id) || "Hosted idea",
      title: normalizeOptionalString(idea.title) || normalizeOptionalString(idea.id) || "Hosted idea",
      notes,
      idea,
    });
  } catch {
    return null;
  }

  if (!Array.isArray(parsed.entries) || parsed.entries.length === 0) {
    return null;
  }

  let manifest = null;
  try {
    manifest = extractStructuredWorkspaceFromNotes(notes);
  } catch {
    manifest = null;
  }

  const title = buildWorkspaceTitleFromIdea(idea, manifest);
  const workspaceId = buildWorkspaceIdFromIdea(idea, manifest);
  return {
    kind: "hosted-idea",
    idea,
    manifest,
    title,
    workspaceId,
    selectorValues: [
      normalizeOptionalString(idea.id),
      normalizeOptionalString(idea.title),
      workspaceId,
      title,
    ].filter(Boolean),
    tabCount: parsed.entries.length,
    parseMode: parsed.parseMode,
  };
}

function extractLocalWorkspaceCandidate(workspace) {
  if (!workspace || typeof workspace !== "object" || Array.isArray(workspace)) {
    return null;
  }
  if (workspace.status && workspace.status !== "ok") {
    return null;
  }
  return {
    kind: "workspace-file",
    manifestPath: normalizeOptionalString(workspace.manifestPath),
    workspaceId: normalizeOptionalString(workspace.workspaceId),
    title: normalizeOptionalString(workspace.title),
    selectorValues: [
      normalizeOptionalString(workspace.workspaceId),
      normalizeOptionalString(workspace.title),
      normalizeOptionalString(workspace.manifestPath ? path.basename(workspace.manifestPath, path.extname(workspace.manifestPath)) : ""),
    ].filter(Boolean),
    updatedAt: normalizeOptionalString(workspace.updatedAt),
  };
}

function extractHostedWorkspaceCandidate(workspace) {
  if (!workspace || typeof workspace !== "object" || Array.isArray(workspace)) {
    return null;
  }
  const workspaceId = normalizeOptionalString(workspace.workspace_id ?? workspace.id);
  if (!workspaceId) {
    return null;
  }
  const linkedIdea = getObjectValue(workspace, "linked_idea", "linkedIdea");
  return {
    kind: "hosted-workspace",
    workspaceId,
    title: normalizeOptionalString(workspace.title) || workspaceId,
    hostedWorkspaceId: workspaceId,
    selectorValues: [
      workspaceId,
      normalizeOptionalString(workspace.title),
      getTextValue(linkedIdea, "idea_id", "ideaId"),
      getTextValue(linkedIdea, "idea_title", "ideaTitle"),
    ].filter(Boolean),
    updatedAt: normalizeOptionalString(workspace.updated_at_utc ?? workspace.updatedAt),
    sourceKind: normalizeOptionalString(workspace.source_kind ?? workspace.sourceKind) || "hosted",
  };
}

function candidateMergeKey(candidate) {
  const workspaceId = normalizeOptionalString(candidate?.workspaceId);
  if (workspaceId) {
    return `id:${workspaceId}`;
  }
  const titleSlug = slugify(candidate?.title);
  if (titleSlug) {
    return `title:${titleSlug}`;
  }
  const manifestPath = normalizeOptionalString(candidate?.manifestPath);
  if (manifestPath) {
    return `path:${path.resolve(manifestPath)}`;
  }
  const ideaId = normalizeOptionalString(candidate?.idea?.id);
  if (ideaId) {
    return `idea:${ideaId}`;
  }
  return null;
}

function looksLikeGeneratedCaptureName(value) {
  const normalized = normalizeOptionalString(value);
  if (!normalized) {
    return false;
  }
  return /^captured-iterm-window-/i.test(normalized);
}

export function chooseImplicitMainCandidate(candidates = []) {
  const rows = Array.isArray(candidates) ? candidates.filter(Boolean) : [];
  if (rows.length === 1) {
    return rows[0];
  }

  const hostedBacked = rows.filter((candidate) => candidate.kind === "hosted-workspace" || candidate.kind === "hosted-idea");
  if (hostedBacked.length === 1) {
    return hostedBacked[0];
  }

  const nonGenerated = rows.filter((candidate) => {
    if (candidate.kind !== "workspace-file") {
      return true;
    }
    return !looksLikeGeneratedCaptureName(candidate.workspaceId) && !looksLikeGeneratedCaptureName(candidate.title);
  });
  if (nonGenerated.length === 1) {
    return nonGenerated[0];
  }

  return null;
}

function collectUniqueWorkspaceCandidates(collections = {}) {
  const localCandidates = Array.isArray(collections.localWorkspaces)
    ? collections.localWorkspaces.map((row) => extractLocalWorkspaceCandidate(row)).filter(Boolean)
    : [];
  const hostedCandidates = Array.isArray(collections.hostedWorkspaces)
    ? collections.hostedWorkspaces.map((row) => extractHostedWorkspaceCandidate(row)).filter(Boolean)
    : [];
  const ideaCandidates = Array.isArray(collections.ideas)
    ? collections.ideas.map((row) => extractIdeaWorkspaceCandidate(row)).filter(Boolean)
    : [];

  const merged = new Map();
  for (const candidate of [...hostedCandidates, ...ideaCandidates, ...localCandidates]) {
    const key = candidateMergeKey(candidate);
    if (!key) {
      continue;
    }
    const current = merged.get(key);
    if (
      !current ||
      (current.kind === "workspace-file" && candidate.kind !== "workspace-file") ||
      (current.kind === "hosted-idea" && candidate.kind === "hosted-workspace")
    ) {
      merged.set(key, candidate);
    }
  }
  return [...merged.values()];
}

async function collectWorkspaceSelectorCollections(options = {}) {
  const [ideasPayload, hostedWorkspacesPayload, localRegistry] = await Promise.all([
    fetchIdeasPayload(options).catch(() => ({ ideas: [] })),
    fetchHostedWorkspacesPayload(options).catch(() => ({ workspaces: [] })),
    listTrackedWorkspaces(options).catch(() => ({ workspaces: [] })),
  ]);
  return {
    ideas: ideasPayload.ideas,
    hostedWorkspaces: hostedWorkspacesPayload.workspaces,
    localWorkspaces: localRegistry.workspaces,
  };
}

function buildWorkspaceSourceOptionsFromCandidate(candidate) {
  if (!candidate || typeof candidate !== "object") {
    return null;
  }
  if (candidate.kind === "workspace-file" && candidate.manifestPath) {
    return {
      workspaceFile: candidate.manifestPath,
    };
  }
  if (candidate.kind === "hosted-idea" && candidate.idea?.id) {
    return {
      ideaId: candidate.idea.id,
    };
  }
  if (candidate.kind === "hosted-workspace" && candidate.workspaceId) {
    return {
      hostedWorkspaceId: candidate.workspaceId,
    };
  }
  return null;
}

function buildWorkspaceSourceOptionsFromSlot(slot) {
  if (!slot || typeof slot !== "object") {
    return null;
  }
  if (slot.kind === "workspace-file" && slot.manifestPath) {
    return {
      workspaceFile: slot.manifestPath,
    };
  }
  if (slot.kind === "hosted-workspace") {
    const hostedWorkspaceId = normalizeOptionalString(slot.hostedWorkspaceId) || normalizeOptionalString(slot.workspaceId);
    if (hostedWorkspaceId) {
      return {
        hostedWorkspaceId,
      };
    }
  }
  if (slot.kind === "hosted-idea") {
    const ideaId = normalizeOptionalString(slot.ideaId) || normalizeOptionalString(slot.workspaceId) || normalizeOptionalString(slot.selector);
    if (ideaId) {
      return {
        ideaId,
      };
    }
  }
  return null;
}

export function buildWorkspaceSlotAssignment(candidate) {
  if (!candidate || typeof candidate !== "object") {
    throw new Error("workspace candidate is required");
  }
  if (candidate.kind === "workspace-file") {
    return {
      kind: "workspace-file",
      selector: normalizeOptionalString(candidate.title) || normalizeOptionalString(candidate.workspaceId) || candidate.manifestPath,
      workspaceId: normalizeOptionalString(candidate.workspaceId) || undefined,
      title: normalizeOptionalString(candidate.title) || undefined,
      manifestPath: normalizeOptionalString(candidate.manifestPath) || undefined,
    };
  }
  if (candidate.kind === "hosted-idea") {
    return {
      kind: "hosted-idea",
      selector:
        normalizeOptionalString(candidate.title) ||
        normalizeOptionalString(candidate.workspaceId) ||
        normalizeOptionalString(candidate.idea?.id) ||
        undefined,
      workspaceId: normalizeOptionalString(candidate.workspaceId) || undefined,
      title: normalizeOptionalString(candidate.title) || undefined,
      ideaId: normalizeOptionalString(candidate.idea?.id) || undefined,
    };
  }
  if (candidate.kind === "hosted-workspace") {
    return {
      kind: "hosted-workspace",
      selector:
        normalizeOptionalString(candidate.title) ||
        normalizeOptionalString(candidate.workspaceId) ||
        undefined,
      workspaceId: normalizeOptionalString(candidate.workspaceId) || undefined,
      title: normalizeOptionalString(candidate.title) || undefined,
      hostedWorkspaceId: normalizeOptionalString(candidate.workspaceId) || undefined,
    };
  }
  throw new Error(`unsupported workspace candidate kind: ${candidate.kind || "unknown"}`);
}

async function resolveWorkspaceSlotTarget(selector, options = {}) {
  const slotName = normalizeWorkspaceSlotName(selector);
  if (!slotName) {
    return null;
  }

  const { slots } = await loadWorkspaceSlots(options).catch(() => ({ slots: {} }));
  const explicitSlot = slots[slotName] || null;
  if (explicitSlot) {
    const target = buildWorkspaceSourceOptionsFromSlot(explicitSlot);
    if (!target) {
      throw new Error(`Workspace slot '${slotName}' is set but no longer points to a valid workspace target.`);
    }
    return {
      slotName,
      mode: "explicit",
      target,
      slot: explicitSlot,
    };
  }

  if (slotName === "main") {
    const collections = await collectWorkspaceSelectorCollections(options);
    const candidates = collectUniqueWorkspaceCandidates(collections);
    const implicitCandidate = chooseImplicitMainCandidate(candidates);
    if (implicitCandidate) {
      const target = buildWorkspaceSourceOptionsFromCandidate(implicitCandidate);
      if (target) {
        return {
          slotName,
          mode: "implicit",
          target,
          candidate: implicitCandidate,
        };
      }
    }
  }

  return {
    slotName,
    mode: "unset",
    target: null,
    slot: explicitSlot,
  };
}

export function resolveWorkspaceSelectorFromCollections(selector, collections = {}) {
  const normalizedSelector = normalizeOptionalString(selector);
  if (!normalizedSelector) {
    return null;
  }

  const localCandidates = Array.isArray(collections.localWorkspaces)
    ? collections.localWorkspaces.map((row) => extractLocalWorkspaceCandidate(row)).filter(Boolean)
    : [];
  const hostedCandidates = Array.isArray(collections.hostedWorkspaces)
    ? collections.hostedWorkspaces.map((row) => extractHostedWorkspaceCandidate(row)).filter(Boolean)
    : [];
  const ideaCandidates = Array.isArray(collections.ideas)
    ? collections.ideas.map((row) => extractIdeaWorkspaceCandidate(row)).filter(Boolean)
    : [];

  const ranked = [];
  for (const candidate of [...hostedCandidates, ...ideaCandidates, ...localCandidates]) {
    let score = matchQuality(normalizedSelector, candidate.selectorValues);
    if (candidate.kind === "hosted-workspace") {
      score += 10;
    } else if (candidate.kind === "hosted-idea") {
      score += 5;
    }
    if (score > 0) {
      ranked.push({ candidate, score });
    }
  }

  if (ranked.length === 0) {
    return null;
  }

  ranked.sort((left, right) => right.score - left.score);
  const bestScore = ranked[0].score;
  const best = ranked.filter((row) => row.score === bestScore);
  if (best.length > 1) {
    const choices = best
      .map(({ candidate }) => {
        if (candidate.kind === "hosted-idea") {
          return `${candidate.title || candidate.workspaceId || candidate.idea.id} [idea ${candidate.idea.id}]`;
        }
        if (candidate.kind === "hosted-workspace") {
          return `${candidate.title || candidate.workspaceId} [workspace ${candidate.workspaceId}]`;
        }
        return `${candidate.title || candidate.workspaceId || candidate.manifestPath} [${candidate.manifestPath}]`;
      })
      .join("; ");
    throw new Error(`Workspace selector '${normalizedSelector}' is ambiguous. Matches: ${choices}`);
  }
  return best[0].candidate;
}

export function buildWorkspaceManifestFromHostedWorkspacePayload(payload) {
  const workspace =
    payload && typeof payload === "object" && !Array.isArray(payload) && payload.workspace && typeof payload.workspace === "object"
      ? payload.workspace
      : payload;
  if (!workspace || typeof workspace !== "object" || Array.isArray(workspace)) {
    throw new Error("Hosted ORP returned an unexpected workspace payload.");
  }

  const state = getObjectValue(workspace, "state") || {};
  const captureContext = getObjectValue(state, "capture_context", "captureContext");
  const tabs = getArrayValue(state, "tabs").filter((row) => row && typeof row === "object" && !Array.isArray(row));

  const manifest = {
    version: "1",
    workspaceId: getTextValue(workspace, "workspace_id", "id"),
    title: getTextValue(workspace, "title"),
    capture: captureContext
      ? Object.fromEntries(
          Object.entries({
            sourceApp: getTextValue(captureContext, "source_app", "sourceApp"),
            mode: getTextValue(captureContext, "mode"),
            host: getTextValue(captureContext, "host"),
            windowId:
              Number.isInteger(captureContext.window_id) && captureContext.window_id > 0
                ? captureContext.window_id
                : Number.isInteger(captureContext.windowId) && captureContext.windowId > 0
                  ? captureContext.windowId
                  : undefined,
            windowIndex:
              Number.isInteger(captureContext.window_index) && captureContext.window_index > 0
                ? captureContext.window_index
                : Number.isInteger(captureContext.windowIndex) && captureContext.windowIndex > 0
                  ? captureContext.windowIndex
                  : undefined,
            pollSeconds:
              typeof captureContext.poll_seconds === "number" && captureContext.poll_seconds > 0
                ? captureContext.poll_seconds
                : typeof captureContext.pollSeconds === "number" && captureContext.pollSeconds > 0
                  ? captureContext.pollSeconds
                  : undefined,
            capturedAt: getTextValue(state, "captured_at_utc", "capturedAtUtc"),
            trackingStartedAt: getTextValue(captureContext, "tracking_started_at_utc", "trackingStartedAtUtc"),
            tabCount:
              Number.isInteger(state.tab_count) && state.tab_count >= 0
                ? state.tab_count
                : Number.isInteger(state.tabCount) && state.tabCount >= 0
                  ? state.tabCount
                  : tabs.length,
          }).filter(([, value]) => value !== undefined && value !== null),
        )
      : undefined,
    tabs: tabs.map((tab) =>
      Object.fromEntries(
        Object.entries({
          title:
            getTextValue(tab, "title") ||
            getTextValue(tab, "repo_label", "repoLabel") ||
            path.basename(String(getTextValue(tab, "project_root", "projectRoot") || "").replace(/\/+$/, "")) ||
            undefined,
          path: getTextValue(tab, "project_root", "projectRoot"),
          resumeCommand: getTextValue(tab, "resume_command", "resumeCommand"),
          resumeTool: getTextValue(tab, "resume_tool", "resumeTool"),
          resumeSessionId: getTextValue(tab, "resume_session_id", "resumeSessionId"),
          codexSessionId: getTextValue(tab, "codex_session_id", "codexSessionId"),
          tmuxSessionName: getTextValue(tab, "tmux_session_name", "tmuxSessionName"),
        }).filter(([, value]) => value !== undefined && value !== null),
      ),
    ),
  };

  if (!manifest.workspaceId || manifest.tabs.length === 0) {
    throw new Error("Hosted ORP workspace payload is missing a workspace id or saved tabs.");
  }

  return manifest;
}

export async function fetchHostedWorkspacePayload(workspaceId, options = {}) {
  const invocation = resolveOrpInvocation(options);
  const args = [...invocation.prefixArgs, "workspaces", "show", workspaceId, "--json"];
  if (options.baseUrl) {
    args.push("--base-url", options.baseUrl);
  }

  const result = await runCommand(invocation.command, args, options);
  const payload = parseOrpJsonResult(result, "Failed to fetch ORP hosted workspace.");
  if (!payload || payload.ok !== true || !payload.workspace) {
    throw new Error("ORP returned an unexpected hosted workspace payload.");
  }
  return payload;
}

export async function updateIdeaPayload(ideaId, fields, options = {}) {
  const invocation = resolveOrpInvocation(options);
  const args = [...invocation.prefixArgs, "idea", "update"];
  if (options.baseUrl) {
    args.push("--base-url", options.baseUrl);
  }
  args.push(ideaId);

  if (fields.title != null) {
    args.push("--title", String(fields.title));
  }
  if (fields.notes != null) {
    args.push("--notes", String(fields.notes));
  }

  args.push("--json");

  const result = await runCommand(invocation.command, args, options);
  const payload = parseOrpJsonResult(result, "Failed to update ORP idea.");

  if (!payload || payload.ok !== true || !payload.idea?.id) {
    throw new Error("ORP returned an unexpected update payload.");
  }

  return payload.idea;
}

export async function pushHostedWorkspaceState(workspaceId, state, options = {}) {
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "orp-hosted-workspace-state-"));
  const statePath = path.join(tempDir, "state.json");
  try {
    await fs.writeFile(statePath, `${JSON.stringify(state, null, 2)}\n`, "utf8");
    const invocation = resolveOrpInvocation(options);
    const args = [...invocation.prefixArgs, "workspaces", "push-state", workspaceId, "--state-file", statePath, "--json"];
    if (options.baseUrl) {
      args.push("--base-url", options.baseUrl);
    }
    const result = await runCommand(invocation.command, args, options);
    return parseOrpJsonResult(result, "Failed to push hosted workspace state.");
  } finally {
    await fs.rm(tempDir, { recursive: true, force: true });
  }
}

export function resolveWorkspaceWatchTargets(source, options = {}) {
  if (!source || typeof source !== "object") {
    return {
      hostedWorkspaceId: null,
      syncIdeaSelector: null,
    };
  }

  if (source.sourceType === "hosted-idea") {
    return {
      hostedWorkspaceId: null,
      syncIdeaSelector: source.idea?.id || options.ideaId || null,
    };
  }

  if (source.sourceType === "hosted-workspace") {
    const hostedWorkspace = source.hostedWorkspace || {};
    const sourceKind = normalizeOptionalString(hostedWorkspace.source_kind ?? hostedWorkspace.sourceKind) || "hosted";
    const linkedIdea = getObjectValue(hostedWorkspace, "linked_idea", "linkedIdea");
    const linkedIdeaId = getTextValue(linkedIdea, "idea_id", "ideaId");
    if (sourceKind === "idea_bridge" && linkedIdeaId) {
      return {
        hostedWorkspaceId: null,
        syncIdeaSelector: linkedIdeaId,
      };
    }
    return {
      hostedWorkspaceId:
        normalizeOptionalString(hostedWorkspace.workspace_id ?? hostedWorkspace.id) ||
        normalizeOptionalString(options.hostedWorkspaceId),
      syncIdeaSelector: null,
    };
  }

  return {
    hostedWorkspaceId: null,
    syncIdeaSelector: null,
  };
}

export async function loadWorkspaceSource(options = {}) {
  if (options.workspaceFile) {
    const workspacePath = path.resolve(options.workspaceFile);
    const raw = await fs.readFile(workspacePath, "utf8");
    let workspaceManifest;
    try {
      workspaceManifest = JSON.parse(raw);
    } catch (error) {
      throw new Error(
        `Failed to parse workspace JSON at ${workspacePath}: ${error instanceof Error ? error.message : String(error)}`,
      );
    }

    return {
      sourceType: "workspace-file",
      sourceLabel: workspacePath,
      sourcePath: workspacePath,
      title: path.basename(workspacePath),
      workspaceManifest,
      notes: "",
    };
  }

  if (options.notesFile) {
    const notesPath = path.resolve(options.notesFile);
    const notes = await fs.readFile(notesPath, "utf8");
    return {
      sourceType: "file",
      sourceLabel: notesPath,
      sourcePath: notesPath,
      title: path.basename(notesPath),
      notes,
    };
  }

  if (options.hostedWorkspaceId) {
    const payload = await fetchHostedWorkspacePayload(options.hostedWorkspaceId, options);
    return {
      sourceType: "hosted-workspace",
      sourceLabel: payload.workspace.title || options.hostedWorkspaceId,
      title: payload.workspace.title || options.hostedWorkspaceId,
      workspaceManifest: buildWorkspaceManifestFromHostedWorkspacePayload(payload),
      notes: "",
      hostedWorkspace: payload.workspace,
      payload,
    };
  }

  if (!options.ideaId) {
    throw new Error(
      "Provide a workspace name or id, use --hosted-workspace-id <id>, --workspace-file <path>, or --notes-file <path>.",
    );
  }

  const selector = options.ideaId;
  const slotTarget = await resolveWorkspaceSlotTarget(selector, options);
  if (slotTarget?.target) {
    return loadWorkspaceSource({
      ...options,
      ideaId: slotTarget.target.ideaId,
      workspaceFile: slotTarget.target.workspaceFile,
      hostedWorkspaceId: slotTarget.target.hostedWorkspaceId,
    });
  }
  if (slotTarget?.slotName && slotTarget.mode === "unset") {
    throw new Error(
      slotTarget.slotName === "main"
        ? "Workspace slot 'main' is not set. If this Mac only has one workspace it becomes main automatically; otherwise run `orp workspace slot set main <name-or-id>`."
        : "Workspace slot 'offhand' is not set. Run `orp workspace slot set offhand <name-or-id>`.",
    );
  }

  const collections = await collectWorkspaceSelectorCollections(options);
  const resolved = resolveWorkspaceSelectorFromCollections(selector, collections);

  if (resolved?.kind === "hosted-workspace" && resolved.workspaceId) {
    const payload = await fetchHostedWorkspacePayload(resolved.workspaceId, options);
    return {
      sourceType: "hosted-workspace",
      sourceLabel: payload.workspace.title || resolved.workspaceId,
      title: payload.workspace.title || resolved.workspaceId,
      workspaceManifest: buildWorkspaceManifestFromHostedWorkspacePayload(payload),
      notes: "",
      hostedWorkspace: payload.workspace,
      payload,
    };
  }

  if (resolved?.kind === "workspace-file" && resolved.manifestPath) {
    const workspacePath = path.resolve(resolved.manifestPath);
    const raw = await fs.readFile(workspacePath, "utf8");
    const workspaceManifest = JSON.parse(raw);
    return {
      sourceType: "workspace-file",
      sourceLabel: resolved.title || workspacePath,
      sourcePath: workspacePath,
      title: resolved.title || path.basename(workspacePath),
      workspaceManifest,
      notes: "",
    };
  }

  if (resolved?.kind === "hosted-idea") {
    return {
      sourceType: "hosted-idea",
      sourceLabel: resolved.title || resolved.idea.id,
      title: resolved.title || resolved.idea.id,
      notes: resolved.idea.notes || "",
      idea: resolved.idea,
      payload: { ok: true, idea: resolved.idea },
    };
  }

  const payload = await fetchIdeaPayload(selector, options);
  return {
    sourceType: "hosted-idea",
    sourceLabel: payload.idea.title || selector,
    title: payload.idea.title || selector,
    notes: payload.idea.notes || "",
    idea: payload.idea,
    payload,
  };
}
