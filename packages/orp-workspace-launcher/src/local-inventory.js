import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";

import { scanCodexSessions } from "./codex.js";
import { deriveBaseTitle, normalizeWorkspaceManifest, resolveResumeMetadata } from "./core-plan.js";

const DEFAULT_CODEX_SCAN_DAYS = 14;
const DEFAULT_ORP_STATE_SCAN_DEPTH = 4;
const SKIP_SCAN_DIRS = new Set([
  ".cache",
  ".git",
  ".next",
  ".turbo",
  ".venv",
  "__pycache__",
  "build",
  "coverage",
  "dist",
  "node_modules",
  "target",
  "tmp",
  "venv",
]);

function normalizeOptionalString(value) {
  if (value == null) {
    return null;
  }
  const trimmed = String(value).trim();
  return trimmed.length > 0 ? trimmed : null;
}

function normalizePath(value) {
  const normalized = normalizeOptionalString(value);
  return normalized ? path.resolve(normalized) : null;
}

function uniqueStrings(values = []) {
  return [...new Set(values.map((value) => normalizeOptionalString(value)).filter(Boolean))];
}

function isObject(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

function isWithinRoot(root, candidate) {
  const rootPath = normalizePath(root);
  const candidatePath = normalizePath(candidate);
  if (!rootPath || !candidatePath) {
    return false;
  }
  return candidatePath === rootPath || candidatePath.startsWith(`${rootPath}${path.sep}`);
}

function pathDepth(candidate) {
  return normalizePath(candidate)?.split(path.sep).filter(Boolean).length || 0;
}

function commonAncestor(paths = []) {
  const normalized = paths.map((candidate) => normalizePath(candidate)).filter(Boolean);
  if (normalized.length === 0) {
    return null;
  }
  const split = normalized.map((candidate) => candidate.split(path.sep).filter(Boolean));
  const parts = [];
  for (let index = 0; ; index += 1) {
    const value = split[0]?.[index];
    if (!value || split.some((row) => row[index] !== value)) {
      break;
    }
    parts.push(value);
  }
  return parts.length > 0 ? `${path.sep}${parts.join(path.sep)}` : path.parse(normalized[0]).root;
}

function splitRootList(value) {
  if (Array.isArray(value)) {
    return uniqueStrings(value);
  }
  const normalized = normalizeOptionalString(value);
  return normalized ? uniqueStrings(normalized.split(path.delimiter)) : [];
}

export function inferLocalProjectRoots(manifest, options = {}) {
  const explicitRoots = [
    ...splitRootList(options.localProjectRoots),
    ...splitRootList(options.localProjectRoot),
    ...splitRootList(options.env?.ORP_WORKSPACE_LOCAL_PROJECT_ROOTS ?? process.env.ORP_WORKSPACE_LOCAL_PROJECT_ROOTS),
  ].map((candidate) => path.resolve(candidate));
  if (explicitRoots.length > 0) {
    return uniqueStrings(explicitRoots);
  }

  const tabPaths = Array.isArray(manifest?.tabs)
    ? manifest.tabs.map((tab) => normalizePath(tab?.path)).filter(Boolean)
    : [];
  if (tabPaths.length === 0) {
    return [];
  }

  const candidate = commonAncestor(tabPaths.map((entry) => path.dirname(entry)));
  if (candidate && pathDepth(candidate) >= 3) {
    return [candidate];
  }

  return uniqueStrings(tabPaths.map((entry) => path.dirname(entry)));
}

function newestIso(...values) {
  let newest = 0;
  for (const value of values) {
    const normalized = normalizeOptionalString(value);
    const ms = normalized ? Date.parse(normalized) : 0;
    if (Number.isFinite(ms) && ms > newest) {
      newest = ms;
    }
  }
  return newest > 0 ? new Date(newest).toISOString() : null;
}

function isoFromMs(value) {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? new Date(value).toISOString() : null;
}

function titleFromPath(projectPath) {
  const normalized = normalizePath(projectPath);
  return normalized ? path.basename(normalized) || normalized : null;
}

function tabKey(tab) {
  const normalizedPath = normalizePath(tab?.path);
  const resume = resolveResumeMetadata(tab || {});
  if (normalizedPath && resume.resumeTool && resume.resumeSessionId) {
    return `${normalizedPath}|${resume.resumeTool}|${resume.resumeSessionId}`;
  }
  return `${normalizedPath}|path-only|${normalizeOptionalString(tab?.title) || ""}`;
}

function stripUndefined(record) {
  return Object.fromEntries(Object.entries(record).filter(([, value]) => value !== undefined && value !== null));
}

function buildResumeFields({ resumeTool, resumeSessionId, resumeCommand }) {
  const tool = normalizeOptionalString(resumeTool);
  const sessionId = normalizeOptionalString(resumeSessionId);
  const command = normalizeOptionalString(resumeCommand) || (tool && sessionId ? `${tool} resume ${sessionId}` : null);
  return {
    resumeCommand: command,
    resumeTool: tool,
    resumeSessionId: sessionId,
    codexSessionId: tool === "codex" ? sessionId : null,
    claudeSessionId: tool === "claude" ? sessionId : null,
  };
}

async function readJson(filePath) {
  try {
    const raw = await fs.readFile(filePath, "utf8");
    const parsed = JSON.parse(raw);
    return isObject(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

async function statIso(filePath) {
  try {
    const stat = await fs.stat(filePath);
    return isoFromMs(stat.mtimeMs);
  } catch {
    return null;
  }
}

async function walkOrpStateFiles(root, options = {}, depth = 0, output = []) {
  const maxDepth = Number.isFinite(options.orpStateScanDepth)
    ? options.orpStateScanDepth
    : DEFAULT_ORP_STATE_SCAN_DEPTH;
  if (depth > maxDepth) {
    return output;
  }

  const statePath = path.join(root, "orp", "state.json");
  try {
    const stat = await fs.stat(statePath);
    if (stat.isFile()) {
      output.push(statePath);
    }
  } catch {
    // No ORP state in this directory.
  }

  if (depth >= maxDepth) {
    return output;
  }

  let entries;
  try {
    entries = await fs.readdir(root, { withFileTypes: true });
  } catch {
    return output;
  }

  for (const entry of entries) {
    if (!entry.isDirectory() || SKIP_SCAN_DIRS.has(entry.name) || entry.name.startsWith("._")) {
      continue;
    }
    if (entry.name === "orp") {
      continue;
    }
    await walkOrpStateFiles(path.join(root, entry.name), options, depth + 1, output);
  }
  return output;
}

function tabsFromOrpStartupState(state, statePath, options = {}) {
  const startup = isObject(state?.startup) ? state.startup : {};
  const workspace = isObject(startup.workspace) ? startup.workspace : {};
  const requestedWorkspace = normalizeOptionalString(workspace.workspace);
  const selector = normalizeOptionalString(options.workspaceSelector ?? options.ideaId ?? options.workspace);
  if (selector && requestedWorkspace && requestedWorkspace !== selector) {
    return [];
  }

  const rows = [];
  const resultManifest = isObject(workspace.result?.manifest) ? workspace.result.manifest : null;
  const targetWorkspaceId = normalizeOptionalString(options.workspaceId);
  if (resultManifest) {
    try {
      const manifest = normalizeWorkspaceManifest(resultManifest);
      if (!targetWorkspaceId || !manifest.workspaceId || manifest.workspaceId === targetWorkspaceId) {
        rows.push(
          ...manifest.tabs.map((tab) =>
            stripUndefined({
              ...tab,
              title: normalizeOptionalString(tab.title) || titleFromPath(tab.path),
              lastActivityAt: normalizeOptionalString(tab.lastActivityAt) || normalizeOptionalString(startup.updated_at_utc) || undefined,
              syncSource: "orp-project-startup",
              inventorySourcePath: statePath,
            }),
          ),
        );
      }
    } catch {
      // Ignore malformed historical startup manifests and keep scanning.
    }
  }

  const resultTab = isObject(workspace.result?.tab) ? workspace.result.tab : null;
  const projectPath = normalizePath(resultTab?.path ?? workspace.path);
  if (!projectPath) {
    return rows;
  }

  const resume = buildResumeFields({
    resumeCommand: resultTab?.resumeCommand,
    resumeTool: resultTab?.resumeTool ?? (workspace.codex_session_id ? "codex" : null),
    resumeSessionId: resultTab?.resumeSessionId ?? resultTab?.codexSessionId ?? workspace.codex_session_id,
  });

  rows.push(
    stripUndefined({
      title: normalizeOptionalString(resultTab?.title) || titleFromPath(projectPath),
      path: projectPath,
      remoteUrl: normalizeOptionalString(resultTab?.remoteUrl ?? workspace.remote_url),
      remoteBranch: normalizeOptionalString(resultTab?.remoteBranch ?? workspace.remote_branch),
      bootstrapCommand: normalizeOptionalString(resultTab?.bootstrapCommand),
      ...resume,
      linkedIdeaId: normalizeOptionalString(resultTab?.linkedIdeaId ?? resultTab?.linked_idea_id),
      linkedFeatureId: normalizeOptionalString(resultTab?.linkedFeatureId ?? resultTab?.linked_feature_id),
      plan: isObject(resultTab?.plan) ? resultTab.plan : undefined,
      tasks: Array.isArray(resultTab?.tasks) && resultTab.tasks.length > 0 ? resultTab.tasks : undefined,
      lastActivityAt: normalizeOptionalString(startup.updated_at_utc) || undefined,
      syncSource: "orp-project-startup",
      inventorySourcePath: statePath,
    }),
  );
  return rows;
}

async function collectOrpStartupRows(roots, options = {}) {
  const rows = [];
  for (const root of roots) {
    const stateFiles = await walkOrpStateFiles(root, options);
    for (const statePath of stateFiles) {
      const state = await readJson(statePath);
      if (!state) {
        continue;
      }
      const tabs = tabsFromOrpStartupState(state, statePath, options);
      if (tabs.length === 0) {
        continue;
      }
      const fallbackActivityAt = await statIso(statePath);
      rows.push(
        ...tabs.map((tab) => ({
          ...tab,
          lastActivityAt: tab.lastActivityAt || fallbackActivityAt || undefined,
        })),
      );
    }
  }
  return rows;
}

function resolveClawdadStatePath(options = {}) {
  if (options.clawdadStatePath) {
    return path.resolve(options.clawdadStatePath);
  }
  const env = options.env || process.env;
  const clawdadHome = normalizeOptionalString(options.clawdadHome) || normalizeOptionalString(env.CLAWDAD_HOME);
  return path.join(clawdadHome ? path.resolve(clawdadHome) : path.join(os.homedir(), ".clawdad"), "state.json");
}

function isQuarantinedSession(project, sessionId, session) {
  if (session?.quarantined === true || normalizeOptionalString(session?.quarantined) === "true") {
    return true;
  }
  const quarantined = project?.quarantined_sessions;
  if (Array.isArray(quarantined)) {
    return quarantined.includes(sessionId);
  }
  return Boolean(isObject(quarantined) && quarantined[sessionId]);
}

function latestClawdadSessionIso(project, session) {
  return newestIso(
    session?.last_response,
    session?.last_response_at,
    session?.last_dispatch,
    session?.last_dispatch_at,
    session?.updated_at,
    session?.created_at,
    session?.tracked_at,
    project?.last_response,
    project?.last_dispatch,
    project?.registered_at,
  );
}

function collectClawdadProjectRows(projectPath, project) {
  const sessions = isObject(project?.sessions) ? project.sessions : {};
  const codexSessions = Object.entries(sessions)
    .filter(([sessionId, session]) => {
      if (!isObject(session) || isQuarantinedSession(project, sessionId, session)) {
        return false;
      }
      const provider =
        normalizeOptionalString(session.provider_override)?.toLowerCase() ||
        normalizeOptionalString(session.provider)?.toLowerCase();
      return provider === "codex";
    })
    .sort(([leftId, leftSession], [rightId, rightSession]) => {
      const activeSessionId = normalizeOptionalString(project?.active_session_id);
      if (leftId === activeSessionId && rightId !== activeSessionId) {
        return -1;
      }
      if (rightId === activeSessionId && leftId !== activeSessionId) {
        return 1;
      }
      const rightMs = Date.parse(latestClawdadSessionIso(project, rightSession) || "") || 0;
      const leftMs = Date.parse(latestClawdadSessionIso(project, leftSession) || "") || 0;
      return rightMs - leftMs;
    });

  if (codexSessions.length > 0) {
    const [sessionId, session] = codexSessions[0];
    return [
      stripUndefined({
        title: normalizeOptionalString(session.slug) || titleFromPath(projectPath),
        path: projectPath,
        ...buildResumeFields({
          resumeTool: "codex",
          resumeSessionId: sessionId,
        }),
        lastActivityAt: latestClawdadSessionIso(project, session) || undefined,
        syncSource: "clawdad",
      }),
    ];
  }

  return [
    stripUndefined({
      title: titleFromPath(projectPath),
      path: projectPath,
      lastActivityAt: newestIso(project?.last_response, project?.last_dispatch, project?.registered_at) || undefined,
      syncSource: "clawdad",
    }),
  ];
}

async function collectClawdadRows(roots, options = {}) {
  const clawdadStatePath = resolveClawdadStatePath(options);
  const state = await readJson(clawdadStatePath);
  if (!state || !isObject(state.projects)) {
    return [];
  }
  const knownProjectPaths = options.knownProjectPaths instanceof Set ? options.knownProjectPaths : null;
  const includeClawdadOnlyProjects = Boolean(options.includeClawdadOnlyProjects);
  const rows = [];
  for (const [projectPathValue, project] of Object.entries(state.projects)) {
    const projectPath = normalizePath(projectPathValue);
    if (!projectPath || !roots.some((root) => isWithinRoot(root, projectPath))) {
      continue;
    }
    if (!includeClawdadOnlyProjects && knownProjectPaths && !knownProjectPaths.has(projectPath)) {
      continue;
    }
    rows.push(...collectClawdadProjectRows(projectPath, project));
  }
  return rows;
}

function latestSessionMs(session) {
  return Math.max(Number(session?.updatedMs || 0), Number(session?.timestampMs || 0));
}

function collectKnownProjectPaths(manifest, rows = []) {
  return new Set(
    [
      ...(Array.isArray(manifest?.tabs) ? manifest.tabs.map((tab) => normalizePath(tab?.path)) : []),
      ...rows.map((row) => normalizePath(row.path)),
    ].filter(Boolean),
  );
}

function latestCodexSessionRows(sessions, knownPaths, options = {}) {
  const rowsByPath = new Map();
  const includeCodexOnlyProjects = Boolean(options.includeCodexOnlyProjects);
  for (const session of sessions) {
    const cwd = normalizePath(session.cwd);
    if (!cwd) {
      continue;
    }
    const matchedPath =
      [...knownPaths].find((projectPath) => isWithinRoot(projectPath, cwd)) ||
      (includeCodexOnlyProjects ? cwd : null);
    if (!matchedPath) {
      continue;
    }
    const current = rowsByPath.get(matchedPath);
    if (!current || latestSessionMs(session) > latestSessionMs(current)) {
      rowsByPath.set(matchedPath, session);
    }
  }

  return [...rowsByPath.entries()].map(([projectPath, session]) =>
    stripUndefined({
      title: titleFromPath(projectPath),
      path: projectPath,
      ...buildResumeFields({
        resumeTool: "codex",
        resumeSessionId: session.sessionId,
      }),
      lastActivityAt: newestIso(session.timestamp, isoFromMs(session.updatedMs)) || undefined,
      syncSource: "codex-session-meta",
    }),
  );
}

async function collectCodexRows(manifest, existingRows, roots, options = {}) {
  const sinceDays = Number.isFinite(options.codexScanDays) ? options.codexScanDays : DEFAULT_CODEX_SCAN_DAYS;
  const sinceMs = Number.isFinite(options.codexSinceMs)
    ? options.codexSinceMs
    : sinceDays > 0
      ? Date.now() - sinceDays * 24 * 60 * 60 * 1000
      : 0;
  let sessions = [];
  try {
    sessions = await scanCodexSessions({
      ...options,
      sinceMs,
    });
  } catch {
    return [];
  }
  const rootSessions = sessions.filter((session) => roots.some((root) => isWithinRoot(root, session.cwd)));
  return latestCodexSessionRows(rootSessions, collectKnownProjectPaths(manifest, existingRows), options);
}

function tabSortMs(tab) {
  const value = normalizeOptionalString(tab?.lastActivityAt ?? tab?.last_activity_at_utc);
  const ms = value ? Date.parse(value) : 0;
  return Number.isFinite(ms) ? ms : 0;
}

function mergeTabFields(existing, candidate) {
  const merged = {
    ...existing,
    ...candidate,
    title: normalizeOptionalString(candidate.title) || normalizeOptionalString(existing?.title) || deriveBaseTitle(candidate),
    remoteUrl: normalizeOptionalString(candidate.remoteUrl) || normalizeOptionalString(existing?.remoteUrl) || undefined,
    remoteBranch: normalizeOptionalString(candidate.remoteBranch) || normalizeOptionalString(existing?.remoteBranch) || undefined,
    bootstrapCommand:
      normalizeOptionalString(candidate.bootstrapCommand) || normalizeOptionalString(existing?.bootstrapCommand) || undefined,
    linkedIdeaId:
      normalizeOptionalString(candidate.linkedIdeaId ?? candidate.linked_idea_id) ||
      normalizeOptionalString(existing?.linkedIdeaId ?? existing?.linked_idea_id) ||
      undefined,
    linkedFeatureId:
      normalizeOptionalString(candidate.linkedFeatureId ?? candidate.linked_feature_id) ||
      normalizeOptionalString(existing?.linkedFeatureId ?? existing?.linked_feature_id) ||
      undefined,
    plan:
      candidate.plan && isObject(candidate.plan)
        ? candidate.plan
        : existing?.plan && isObject(existing.plan)
          ? existing.plan
          : undefined,
    tasks:
      Array.isArray(candidate.tasks) && candidate.tasks.length > 0
        ? candidate.tasks
        : Array.isArray(existing?.tasks) && existing.tasks.length > 0
          ? existing.tasks
          : undefined,
    lastActivityAt:
      newestIso(candidate.lastActivityAt, candidate.last_activity_at_utc, existing?.lastActivityAt, existing?.last_activity_at_utc) ||
      undefined,
    syncSource: normalizeOptionalString(candidate.syncSource) || normalizeOptionalString(existing?.syncSource) || undefined,
  };
  const resume = resolveResumeMetadata(merged);
  return stripUndefined({
    ...merged,
    resumeCommand: resume.resumeCommand || undefined,
    resumeTool: resume.resumeTool || undefined,
    resumeSessionId: resume.resumeSessionId || undefined,
    codexSessionId: resume.resumeTool === "codex" ? resume.resumeSessionId || undefined : undefined,
    claudeSessionId: resume.resumeTool === "claude" ? resume.resumeSessionId || undefined : undefined,
  });
}

function dedupeRowsByKey(rows) {
  const byKey = new Map();
  for (const row of rows) {
    const key = tabKey(row);
    const current = byKey.get(key);
    if (!current || tabSortMs(row) >= tabSortMs(current)) {
      byKey.set(key, row);
    }
  }
  return [...byKey.values()];
}

function sourceRank(row) {
  const source = normalizeOptionalString(row?.syncSource);
  if (source === "codex-session-meta") {
    return 40;
  }
  if (source === "orp-project-startup") {
    return 30;
  }
  if (source === "clawdad") {
    return 35;
  }
  return 10;
}

function selectCanonicalInventoryRows(rows) {
  const rowsByPath = new Map();
  for (const row of dedupeRowsByKey(rows)) {
    const projectPath = normalizePath(row.path);
    if (!projectPath) {
      continue;
    }
    if (!rowsByPath.has(projectPath)) {
      rowsByPath.set(projectPath, []);
    }
    rowsByPath.get(projectPath).push(row);
  }

  const selected = [];
  for (const rowsForPath of rowsByPath.values()) {
    const sorted = [...rowsForPath].sort((left, right) => {
      const rankDelta = sourceRank(right) - sourceRank(left);
      if (rankDelta !== 0) {
        return rankDelta;
      }
      return tabSortMs(right) - tabSortMs(left);
    });
    selected.push(sorted[0]);
  }

  return selected.sort((left, right) => tabSortMs(right) - tabSortMs(left));
}

function mergeInventoryRowsIntoManifest(manifest, inventoryRows, options = {}) {
  const existingTabs = Array.isArray(manifest?.tabs) ? manifest.tabs : [];
  const inventoryByPath = new Map();
  for (const row of selectCanonicalInventoryRows(inventoryRows)) {
    const projectPath = normalizePath(row.path);
    if (!projectPath) {
      continue;
    }
    if (!inventoryByPath.has(projectPath)) {
      inventoryByPath.set(projectPath, []);
    }
    inventoryByPath.get(projectPath).push(row);
  }

  const usedInventoryPaths = new Set();
  const seenExistingPaths = new Set();
  const nextTabs = [];
  for (const tab of existingTabs) {
    const projectPath = normalizePath(tab.path);
    if (projectPath && seenExistingPaths.has(projectPath)) {
      if (!inventoryByPath.has(projectPath)) {
        nextTabs.push(tab);
      }
      continue;
    }
    if (projectPath) {
      seenExistingPaths.add(projectPath);
    }
    const candidates = projectPath ? inventoryByPath.get(projectPath) || [] : [];
    if (candidates.length === 0) {
      nextTabs.push(tab);
      continue;
    }
    usedInventoryPaths.add(projectPath);
    for (const candidate of candidates) {
      const matchingExisting =
        existingTabs.find((existing) => tabKey(existing) === tabKey(candidate)) ||
        existingTabs.find((existing) => normalizePath(existing.path) === projectPath) ||
        tab;
      nextTabs.push(mergeTabFields(matchingExisting, candidate));
    }
  }

  const newRows = [];
  for (const [projectPath, rows] of inventoryByPath.entries()) {
    if (usedInventoryPaths.has(projectPath)) {
      continue;
    }
    newRows.push(...rows.map((row) => mergeTabFields({}, row)));
  }
  newRows.sort((left, right) => tabSortMs(right) - tabSortMs(left));
  nextTabs.push(...newRows);

  const tabLimit = Number.isInteger(options.maxInventoryTabs) && options.maxInventoryTabs > 0 ? options.maxInventoryTabs : null;
  return {
    ...manifest,
    tabs: tabLimit ? nextTabs.slice(0, tabLimit) : nextTabs,
  };
}

export async function buildLocalProjectInventory(manifest, options = {}) {
  const roots = inferLocalProjectRoots(manifest, options);
  const inventoryOptions = {
    ...options,
    workspaceId: normalizeOptionalString(options.workspaceId) || normalizeOptionalString(manifest?.workspaceId),
  };
  const orpRows = await collectOrpStartupRows(roots, inventoryOptions);
  const knownProjectPaths = collectKnownProjectPaths(manifest, orpRows);
  const clawdadRows = await collectClawdadRows(roots, {
    ...inventoryOptions,
    knownProjectPaths,
  });
  const codexRows = await collectCodexRows(manifest, [...orpRows, ...clawdadRows], roots, options);
  const rows = selectCanonicalInventoryRows([...orpRows, ...clawdadRows, ...codexRows]);
  return {
    contract: {
      source_of_truth: "orp-workspace-ledger",
      reconciliation_sources: ["orp-project-startup", "clawdad", "codex-session-meta"],
      codex_sessions_scope: options.includeCodexOnlyProjects ? "known-and-codex-only-projects" : "known-projects-only",
    },
    roots,
    rowCount: rows.length,
    projectCount: new Set(rows.map((row) => normalizePath(row.path)).filter(Boolean)).size,
    rows,
  };
}

export async function mergeLocalProjectInventoryIntoManifest(manifest, options = {}) {
  const inventory = await buildLocalProjectInventory(manifest, options);
  return {
    manifest: mergeInventoryRowsIntoManifest(manifest, inventory.rows, options),
    inventory,
  };
}
