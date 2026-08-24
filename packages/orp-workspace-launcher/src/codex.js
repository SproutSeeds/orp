import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";

import { buildLaunchPlan, getResumeCommand, parseWorkspaceSource } from "./core-plan.js";
import { applyWorkspaceAddTabOptions } from "./ledger.js";
import { loadWorkspaceSource } from "./orp.js";
import { loadLocalConfig } from "./storage.js";

const DEFAULT_WORKSPACE = "main";
const DEFAULT_SCAN_DAYS = 30;
const SESSION_READ_BYTES = 64 * 1024;
const SESSION_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

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

function pathContains(parent, child) {
  const normalizedParent = normalizePath(parent);
  const normalizedChild = normalizePath(child);
  if (!normalizedParent || !normalizedChild) {
    return false;
  }
  return normalizedChild === normalizedParent || normalizedChild.startsWith(`${normalizedParent}${path.sep}`);
}

function resolveCodexHome(options = {}) {
  return (
    normalizeOptionalString(options.codexHome) ||
    normalizeOptionalString(process.env.CODEX_HOME) ||
    path.join(os.homedir(), ".codex")
  );
}

function defaultForbiddenRoots() {
  return new Set(
    [
      path.parse(process.cwd()).root,
      os.homedir(),
      "/Volumes/Code_2TB/code",
      normalizeOptionalString(process.env.ORP_CODE_ROOT),
    ]
      .map((entry) => (entry ? path.resolve(entry) : null))
      .filter(Boolean),
  );
}

function isArtifactOutputRepo(repoRoot) {
  const base = path.basename(String(repoRoot || ""));
  return /(^|-)artifacts?$/i.test(base) || /-artifacts?-/i.test(base);
}

export function isDelegatedCodexSession(session) {
  const originator = normalizeOptionalString(session?.originator)?.toLowerCase();
  if (originator === "clawdad" || originator?.includes("delegate")) {
    return true;
  }
  const source = session?.source;
  if (!source || typeof source !== "object" || Array.isArray(source)) {
    return false;
  }
  if (source.subagent || source.delegate || source.delegated) {
    return true;
  }
  const sourceText = JSON.stringify(source).toLowerCase();
  return sourceText.includes("subagent") || sourceText.includes("delegate");
}

export function isCodexExecSession(session) {
  const originator = normalizeOptionalString(session?.originator)?.toLowerCase();
  if (originator === "codex_exec" || originator === "codex-exec") {
    return true;
  }
  const source = session?.source;
  if (typeof source === "string") {
    return source.trim().toLowerCase() === "exec";
  }
  if (!source || typeof source !== "object" || Array.isArray(source)) {
    return false;
  }
  const sourceKind = normalizeOptionalString(source.kind ?? source.type ?? source.source)?.toLowerCase();
  return sourceKind === "exec";
}

export function parseCodexSessionMetaLine(line, filePath, stat = {}) {
  let row;
  try {
    row = JSON.parse(line);
  } catch {
    return null;
  }
  if (!row || row.type !== "session_meta" || !row.payload || typeof row.payload !== "object") {
    return null;
  }

  const payload = row.payload;
  const sessionId = normalizeOptionalString(payload.id);
  const cwd = normalizeOptionalString(payload.cwd);
  if (!sessionId || !SESSION_ID_PATTERN.test(sessionId) || !cwd) {
    return null;
  }

  const timestamp = normalizeOptionalString(payload.timestamp) || normalizeOptionalString(row.timestamp);
  const timestampMs = timestamp ? Date.parse(timestamp) : 0;
  const source =
    typeof payload.source === "string"
      ? normalizeOptionalString(payload.source)
      : payload.source && typeof payload.source === "object" && !Array.isArray(payload.source)
        ? payload.source
        : null;
  return {
    sessionId,
    cwd: path.resolve(cwd),
    timestamp,
    timestampMs: Number.isFinite(timestampMs) ? timestampMs : 0,
    updatedMs: typeof stat.mtimeMs === "number" ? stat.mtimeMs : 0,
    filePath,
    originator: normalizeOptionalString(payload.originator),
    cliVersion: normalizeOptionalString(payload.cli_version ?? payload.cliVersion),
    source,
  };
}

async function readFirstSessionMetaLine(filePath) {
  let handle;
  try {
    handle = await fs.open(filePath, "r");
    const buffer = Buffer.alloc(SESSION_READ_BYTES);
    const { bytesRead } = await handle.read(buffer, 0, buffer.length, 0);
    if (bytesRead <= 0) {
      return "";
    }
    const chunk = buffer.subarray(0, bytesRead).toString("utf8");
    for (const line of chunk.split("\n")) {
      if (!line.trim()) {
        continue;
      }
      let row;
      try {
        row = JSON.parse(line);
      } catch {
        continue;
      }
      if (row?.type === "session_meta") {
        return line;
      }
    }
    return "";
  } catch {
    return "";
  } finally {
    if (handle) {
      await handle.close().catch(() => {});
    }
  }
}

async function walkSessionFiles(rootDir, options = {}, files = []) {
  let entries;
  try {
    entries = await fs.readdir(rootDir, { withFileTypes: true });
  } catch {
    return files;
  }

  for (const entry of entries) {
    const entryPath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      await walkSessionFiles(entryPath, options, files);
      continue;
    }
    if (!entry.isFile() || !entry.name.endsWith(".jsonl") || !entry.name.startsWith("rollout-")) {
      continue;
    }
    files.push(entryPath);
  }
  return files;
}

export async function scanCodexSessions(options = {}) {
  const codexHome = resolveCodexHome(options);
  const sessionsDir = path.join(codexHome, "sessions");
  const sinceMs = typeof options.sinceMs === "number" ? options.sinceMs : 0;
  const includeDelegated = Boolean(options.includeDelegated || options.includeSubagents);
  const includeExec = Boolean(options.includeExec || options.includeCodexExec);
  const files = await walkSessionFiles(sessionsDir, options);
  const sessions = [];

  for (const filePath of files) {
    let stat;
    try {
      stat = await fs.stat(filePath);
    } catch {
      continue;
    }
    if (sinceMs && stat.mtimeMs < sinceMs) {
      continue;
    }
    const metaLine = await readFirstSessionMetaLine(filePath);
    if (!metaLine) {
      continue;
    }
    const session = parseCodexSessionMetaLine(metaLine, filePath, stat);
    if (!session) {
      continue;
    }
    if (!includeExec && isCodexExecSession(session)) {
      continue;
    }
    if (!includeDelegated && isDelegatedCodexSession(session)) {
      continue;
    }
    sessions.push(session);
  }

  return sessions.sort((left, right) => latestSessionMs(right) - latestSessionMs(left));
}

function latestSessionMs(session) {
  return Math.max(Number(session?.updatedMs || 0), Number(session?.timestampMs || 0));
}

export function resolveRepoRoot(startPath = process.cwd(), options = {}) {
  const cwd = path.resolve(startPath);
  const git = spawnSync("git", ["-C", cwd, "rev-parse", "--show-toplevel"], {
    encoding: "utf8",
  });
  const repoRoot = git.status === 0 && git.stdout.trim() ? path.resolve(git.stdout.trim()) : cwd;
  const forbiddenRoots = options.forbiddenRoots instanceof Set ? options.forbiddenRoots : defaultForbiddenRoots();
  const isForbidden = forbiddenRoots.has(repoRoot);
  const isArtifact = !options.includeArtifactRepos && isArtifactOutputRepo(repoRoot);

  return {
    inputPath: cwd,
    repoRoot,
    ok: !isForbidden && !isArtifact,
    reason: isForbidden ? "broad_root" : isArtifact ? "artifact_output_repo" : null,
  };
}

function latestSessionForPath(sessions, targetPath) {
  const target = path.resolve(targetPath);
  return (
    sessions
      .filter((session) => pathContains(target, session.cwd))
      .sort((left, right) => latestSessionMs(right) - latestSessionMs(left))[0] || null
  );
}

async function loadWorkspaceTabs(options = {}) {
  const source = await loadWorkspaceSource({
    ideaId: options.workspace || DEFAULT_WORKSPACE,
    workspaceFile: options.workspaceFile,
    hostedWorkspaceId: options.hostedWorkspaceId,
    baseUrl: options.baseUrl,
    orpCommand: options.orpCommand,
  });
  const parsed = parseWorkspaceSource(source);
  const tabs = buildLaunchPlan(parsed.entries, {
    tmux: false,
    resume: true,
  });
  return {
    source,
    parsed,
    tabs,
  };
}

function codexTabsForPath(tabs, repoRoot) {
  const target = path.resolve(repoRoot);
  return tabs.filter((tab) => path.resolve(tab.path) === target && tab.resumeTool === "codex");
}

function anyTabsForPath(tabs, repoRoot) {
  const target = path.resolve(repoRoot);
  return tabs.filter((tab) => path.resolve(tab.path) === target);
}

function tabSummary(tab) {
  if (!tab) {
    return null;
  }
  return {
    title: tab.title || null,
    path: tab.path,
    resumeCommand: getResumeCommand(tab),
    resumeTool: tab.resumeTool || null,
    resumeSessionId: tab.sessionId || null,
    codexSessionId: tab.resumeTool === "codex" ? tab.sessionId || null : null,
  };
}

function sessionSummary(session) {
  if (!session) {
    return null;
  }
  return {
    sessionId: session.sessionId,
    cwd: session.cwd,
    timestamp: session.timestamp || null,
    updatedAt: session.updatedMs ? new Date(session.updatedMs).toISOString() : null,
    originator: session.originator || null,
    cliVersion: session.cliVersion || null,
    source: session.source || null,
    filePath: session.filePath || null,
  };
}

function sinceMsFromOptions(options = {}) {
  if (typeof options.sinceMs === "number") {
    return options.sinceMs;
  }
  const sinceDays = Number.isFinite(options.sinceDays) ? options.sinceDays : DEFAULT_SCAN_DAYS;
  return sinceDays > 0 ? Date.now() - sinceDays * 24 * 60 * 60 * 1000 : 0;
}

export async function buildCodexStatusReport(options = {}) {
  const repo = resolveRepoRoot(options.path || process.cwd(), options);
  const workspace = options.workspace || DEFAULT_WORKSPACE;
  const [workspaceData, sessions] = await Promise.all([
    loadWorkspaceTabs(options),
    scanCodexSessions({
      ...options,
      sinceMs: sinceMsFromOptions(options),
    }),
  ]);
  const trackedCodexTabs = repo.ok ? codexTabsForPath(workspaceData.tabs, repo.repoRoot) : [];
  const trackedTabs = repo.ok ? anyTabsForPath(workspaceData.tabs, repo.repoRoot) : [];
  const latestSession = repo.ok ? latestSessionForPath(sessions, repo.repoRoot) : null;
  const primaryTab = trackedCodexTabs.length === 1 ? trackedCodexTabs[0] : trackedCodexTabs[0] || null;
  const trackedSessionId = primaryTab?.sessionId || null;

  let status = "unknown";
  if (!repo.ok) {
    status = repo.reason || "invalid_repo";
  } else if (trackedCodexTabs.length > 1) {
    status = "ambiguous";
  } else if (trackedTabs.length === 0) {
    status = "untracked";
  } else if (!latestSession) {
    status = "no_local_codex_session";
  } else if (trackedSessionId === latestSession.sessionId) {
    status = "current";
  } else {
    status = "stale";
  }

  return {
    workspace,
    sourceLabel: workspaceData.source.sourceLabel,
    repoRoot: repo.repoRoot,
    repoOk: repo.ok,
    repoReason: repo.reason,
    status,
    stale: status === "stale",
    trackedTab: tabSummary(primaryTab),
    trackedTabs: trackedCodexTabs.map((tab) => tabSummary(tab)),
    latestCodexSession: sessionSummary(latestSession),
    updateCommand:
      repo.ok && latestSession
        ? `orp workspace add-tab ${workspace} --path '${repo.repoRoot}' --resume-tool codex --resume-session-id ${latestSession.sessionId}`
        : null,
  };
}

export function summarizeCodexStatus(report) {
  const lines = [
    `Workspace: ${report.workspace}`,
    `Repo: ${report.repoRoot}`,
    `Status: ${report.status}`,
  ];
  if (report.trackedTab) {
    lines.push(`Tracked: ${report.trackedTab.resumeCommand || "path-only"}`);
  }
  if (report.latestCodexSession) {
    lines.push(`Latest local Codex: codex resume ${report.latestCodexSession.sessionId}`);
    lines.push(`Latest cwd: ${report.latestCodexSession.cwd}`);
  }
  if (report.updateCommand && report.stale) {
    lines.push(`Refresh: ${report.updateCommand}`);
  }
  return lines.join("\n");
}

function buildWorkspaceOptions(options = {}) {
  return Object.fromEntries(
    Object.entries({
      ideaId: options.workspace || DEFAULT_WORKSPACE,
      workspaceFile: options.workspaceFile,
      hostedWorkspaceId: options.hostedWorkspaceId,
      baseUrl: options.baseUrl,
      orpCommand: options.orpCommand,
    }).filter(([, value]) => value != null),
  );
}

function plannedMutationForTrackedPath(tabs, repoRoot, latestSession) {
  const trackedTabs = anyTabsForPath(tabs, repoRoot);
  if (trackedTabs.length === 0) {
    return null;
  }
  const codexTabs = codexTabsForPath(tabs, repoRoot);
  if (codexTabs.length > 1) {
    return {
      action: "skip",
      reason: "ambiguous_codex_tabs",
      repoRoot,
      latestCodexSession: sessionSummary(latestSession),
      trackedTabs: codexTabs.map((tab) => tabSummary(tab)),
    };
  }
  const current = codexTabs[0] || null;
  if (!latestSession) {
    return {
      action: "skip",
      reason: "no_local_codex_session",
      repoRoot,
      trackedTab: tabSummary(current || trackedTabs[0]),
    };
  }
  if (current?.sessionId === latestSession.sessionId) {
    return {
      action: "unchanged",
      repoRoot,
      trackedTab: tabSummary(current),
      latestCodexSession: sessionSummary(latestSession),
    };
  }
  return {
    action: current ? "update" : "attach",
    repoRoot,
    title: current?.title || trackedTabs[0]?.title || undefined,
    trackedTab: tabSummary(current || trackedTabs[0]),
    latestCodexSession: sessionSummary(latestSession),
  };
}

export async function buildCodexReconcilePlan(options = {}) {
  const workspace = options.workspace || DEFAULT_WORKSPACE;
  const [workspaceData, sessions] = await Promise.all([
    loadWorkspaceTabs(options),
    scanCodexSessions({
      ...options,
      sinceMs: sinceMsFromOptions(options),
    }),
  ]);
  const trackedPaths = [...new Set(workspaceData.tabs.map((tab) => path.resolve(tab.path)))];
  const actions = [];

  for (const repoRoot of trackedPaths) {
    if (!resolveRepoRoot(repoRoot, options).ok) {
      actions.push({ action: "skip", reason: "refused_repo_root", repoRoot });
      continue;
    }
    actions.push(plannedMutationForTrackedPath(workspaceData.tabs, repoRoot, latestSessionForPath(sessions, repoRoot)));
  }

  const trackedPathSet = new Set(trackedPaths);
  const missingByRepo = new Map();
  if (options.addMissing) {
    for (const session of sessions) {
      const repo = resolveRepoRoot(session.cwd, options);
      if (!repo.ok || trackedPathSet.has(repo.repoRoot)) {
        continue;
      }
      const current = missingByRepo.get(repo.repoRoot);
      if (!current || latestSessionMs(session) > latestSessionMs(current)) {
        missingByRepo.set(repo.repoRoot, session);
      }
    }
    for (const [repoRoot, session] of missingByRepo.entries()) {
      actions.push({
        action: "add",
        repoRoot,
        title: path.basename(repoRoot),
        latestCodexSession: sessionSummary(session),
      });
    }
  }

  return {
    workspace,
    sourceLabel: workspaceData.source.sourceLabel,
    dryRun: Boolean(options.dryRun),
    addMissing: Boolean(options.addMissing),
    actionCount: actions.filter((action) => ["update", "attach", "add"].includes(action?.action)).length,
    actions: actions.filter(Boolean),
  };
}

async function applyReconcileAction(action, options = {}) {
  if (!["update", "attach", "add"].includes(action.action)) {
    return { ...action, applied: false };
  }
  const latest = action.latestCodexSession;
  const result = await applyWorkspaceAddTabOptions({
    ...buildWorkspaceOptions(options),
    path: action.repoRoot,
    title: action.action === "add" ? action.title : undefined,
    resumeTool: "codex",
    resumeSessionId: latest.sessionId,
    append: Boolean(options.append),
  });
  return {
    ...action,
    applied: true,
    mutation: result.mutation,
    tab: result.tab,
  };
}

export async function applyCodexReconcilePlan(plan, options = {}) {
  const appliedActions = [];
  for (const action of plan.actions) {
    if (options.dryRun || !["update", "attach", "add"].includes(action.action)) {
      appliedActions.push({ ...action, applied: false });
      continue;
    }
    appliedActions.push(await applyReconcileAction(action, options));
  }
  return {
    ...plan,
    dryRun: Boolean(options.dryRun),
    actions: appliedActions,
  };
}

export function summarizeCodexReconcile(report) {
  const lines = [
    `Workspace: ${report.workspace}`,
    `Source: ${report.sourceLabel}`,
    `Mode: ${report.dryRun ? "dry-run" : "apply"}`,
    `Actionable: ${report.actionCount}`,
    "",
  ];
  for (const action of report.actions) {
    const prefix = action.applied ? "applied" : action.action;
    lines.push(`${prefix}: ${action.repoRoot}${action.reason ? ` (${action.reason})` : ""}`);
    if (action.latestCodexSession) {
      lines.push(`  latest: codex resume ${action.latestCodexSession.sessionId}`);
    }
  }
  return lines.join("\n").trimEnd();
}

function runReadOnlyGit(repoRoot, args) {
  const result = spawnSync("git", ["-C", repoRoot, ...args], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  });
  return result.status === 0 ? result.stdout.replace(/\r?\n$/, "") : null;
}

async function digestLocalContractFile(repoRoot, relativePath) {
  const filePath = path.join(repoRoot, relativePath);
  try {
    const stat = await fs.stat(filePath);
    if (!stat.isFile()) {
      return null;
    }
    const bytes = await fs.readFile(filePath);
    return {
      kind: "file_digest",
      path: relativePath,
      sha256: createHash("sha256").update(bytes).digest("hex"),
      bytes: bytes.length,
    };
  } catch (error) {
    if (error?.code === "ENOENT") {
      return null;
    }
    throw error;
  }
}

export async function buildCodexContextPacket(options = {}) {
  const env = options.env || process.env;
  const config = loadLocalConfig(env);
  if (!config.codex.context_enabled && !options.allowOnce) {
    throw new Error(
      "ORP Codex context is disabled. Use --allow-once or enable it with `orp config set codex.context_enabled true`.",
    );
  }
  if (config.codex.hosted_sync !== false) {
    throw new Error("ORP Codex context cannot run while codex.hosted_sync is enabled");
  }

  const prompt = options.prompt == null ? "" : String(options.prompt);
  const repo = resolveRepoRoot(options.path || process.cwd(), options);
  if (!repo.ok) {
    throw new Error(`Refusing Codex context for ${path.basename(repo.repoRoot)}: ${repo.reason}`);
  }

  const branch = runReadOnlyGit(repo.repoRoot, ["symbolic-ref", "--quiet", "--short", "HEAD"]);
  const head = runReadOnlyGit(repo.repoRoot, ["rev-parse", "--short=12", "HEAD"]);
  const porcelain = runReadOnlyGit(repo.repoRoot, ["status", "--porcelain=v1", "--untracked-files=normal"]);
  const contractFiles = [];
  for (const relativePath of ["AGENTS.md", "PROTOCOL.md", "orp.yml"]) {
    const digest = await digestLocalContractFile(repo.repoRoot, relativePath);
    if (digest) {
      contractFiles.push(digest);
    }
  }

  const packet = {
    schema: "orp.codex_context/1",
    schema_version: "1.0.0",
    prompt,
    context: {
      project: path.basename(repo.repoRoot),
      repository: {
        branch: branch || "detached-or-unknown",
        head: head || "unknown",
        worktree: porcelain == null ? "unknown" : porcelain.length === 0 ? "clean" : "dirty",
      },
      governed: contractFiles.some((row) => row.path === "PROTOCOL.md"),
    },
    provenance: [
      {
        kind: "git_read_only",
        fields: ["branch", "head", "worktree"],
      },
      ...contractFiles,
    ],
    boundaries: {
      read_only: true,
      offline: true,
      prompt_transform: "none",
      codex_storage_access: false,
      transcript_access: false,
      memory_access: false,
      goal_access: false,
      hosted_sync: false,
      absolute_paths_emitted: false,
      resume_ids_emitted: false,
    },
  };

  const maxBytes = Math.min(2048, config.codex.max_bytes);
  let serialized = JSON.stringify(packet);
  while (Buffer.byteLength(`${serialized}\n`, "utf8") > maxBytes && packet.provenance.length > 1) {
    packet.provenance.pop();
    packet.context.provenance_reduced_to_fit = true;
    serialized = JSON.stringify(packet);
  }
  const byteLength = Buffer.byteLength(`${serialized}\n`, "utf8");
  if (byteLength > maxBytes) {
    throw new Error(
      `Prompt-preserving context would be ${byteLength} bytes, above the configured ${maxBytes}-byte limit. Shorten the prompt or raise codex.max_bytes up to 2048.`,
    );
  }
  return {
    packet,
    serialized,
    byteLength,
    maxBytes,
  };
}

async function readPromptStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}

function parseCommonOptions(argv = [], defaults = {}, parseOptions = {}) {
  const options = {
    workspace: DEFAULT_WORKSPACE,
    json: false,
    sinceDays: DEFAULT_SCAN_DAYS,
    ...defaults,
  };
  const rest = [];
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
    if (arg === "--dry-run") {
      options.dryRun = true;
      continue;
    }
    if (arg === "--add-missing") {
      options.addMissing = true;
      continue;
    }
    if (arg === "--append") {
      options.append = true;
      continue;
    }
    if (arg === "--allow-once") {
      options.allowOnce = true;
      continue;
    }
    if (arg === "--prompt-stdin") {
      options.promptStdin = true;
      continue;
    }
    if (arg === "--legacy-session-access") {
      options.legacySessionAccess = true;
      continue;
    }
    if (arg === "--include-subagents" || arg === "--include-delegated") {
      options.includeSubagents = true;
      options.includeDelegated = true;
      continue;
    }
    if (arg === "--include-exec") {
      options.includeExec = true;
      continue;
    }
    if (arg === "--include-artifacts") {
      options.includeArtifactRepos = true;
      continue;
    }
    if (arg === "--") {
      rest.push(...argv.slice(index + 1));
      break;
    }
    if (arg.startsWith("--")) {
      const next = argv[index + 1];
      if (arg === "--workspace") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.workspace = next;
      } else if (arg === "--workspace-file") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.workspaceFile = next;
      } else if (arg === "--hosted-workspace-id") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.hostedWorkspaceId = next;
      } else if (arg === "--base-url") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.baseUrl = next;
      } else if (arg === "--orp-command") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.orpCommand = next;
      } else if (arg === "--codex-home") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.codexHome = next;
      } else if (arg === "--path") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.path = next;
      } else if (arg === "--since-days") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.sinceDays = Number(next);
      } else if (arg === "--title") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.title = next;
      } else if (arg === "--codex-bin") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.codexBin = next;
      } else if (arg === "--watch-timeout-ms") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.watchTimeoutMs = Number(next);
      } else if (arg === "--prompt") {
        if (next == null || next.startsWith("--")) {
          throw new Error(`missing value for ${arg}`);
        }
        options.prompt = next;
      } else {
        if (parseOptions.passUnknownOptions) {
          rest.push(...argv.slice(index));
          break;
        }
        throw new Error(`unknown option: ${arg}`);
      }
      index += 1;
      continue;
    }
    rest.push(arg);
  }
  return { options, rest };
}

function printCodexHelp() {
  console.log(`ORP Codex adapter

Usage:
  orp codex context --allow-once [--prompt <exact-prompt> | --prompt-stdin]
  orp codex status --legacy-session-access [--workspace main] [--json]
  orp codex reconcile --legacy-session-access [--workspace main] [--dry-run] [--json]
  orp codex start --legacy-session-access [--workspace main] [-- <codex args...>]

Commands:
  context    Emit an opt-in, read-only, offline context packet of at most 2 KiB
  status     Legacy metadata-only session comparison; requires explicit access
  reconcile  Legacy workspace session update; requires explicit access
  start      Legacy Codex launcher/session recorder; requires explicit access

Notes:
  - Context never reads Codex sessions, transcripts, memory, goals, or permissions.
  - Context preserves the supplied prompt byte-for-byte and never syncs it.
  - The 0.5 context adapter is read-only and never reads Codex-owned storage.
  - Legacy session commands require --legacy-session-access on every invocation.
  - Codex exec sessions are ignored by legacy scanning by default.
  - Delegated/subagent sessions are ignored by default.
  - Broad roots and artifact-output repos are refused unless explicitly overridden.
  - Use -- before Codex args that conflict with ORP wrapper options.
  - Manual fallback inside Codex remains: orp workspace add-tab main --here --current-codex
`);
}

function printContextHelp() {
  console.log(`ORP Codex context

Usage:
  orp codex context --allow-once [--path <repo-or-subdir>] [--prompt <exact-prompt> | --prompt-stdin]

The packet is read-only, offline, transcript-free, prompt-preserving, and bounded
by codex.max_bytes (hard maximum: 2048 bytes). --allow-once opts in without
changing local configuration.
`);
}

function printStatusHelp() {
  console.log(`ORP Codex status

Usage:
  orp codex status --legacy-session-access [--workspace main] [--path <repo-or-subdir>] [--codex-home <path>] [--include-exec] [--json]
`);
}

function printReconcileHelp() {
  console.log(`ORP Codex reconcile

Usage:
  orp codex reconcile --legacy-session-access [--workspace main] [--dry-run] [--add-missing] [--since-days <n>] [--include-exec] [--json]
`);
}

function printStartHelp() {
  console.log(`ORP Codex start

Usage:
  orp codex start --legacy-session-access [--workspace main] [--append] [--title <title>] [--codex-bin <bin>] [--watch-timeout-ms <ms>] [-- <codex args...>]
`);
}

async function runCodexStatus(argv) {
  const { options } = parseCommonOptions(argv);
  if (options.help) {
    printStatusHelp();
    return 0;
  }
  if (!options.legacySessionAccess) {
    throw new Error("Legacy Codex session status requires --legacy-session-access");
  }
  const report = await buildCodexStatusReport(options);
  process.stdout.write(options.json ? `${JSON.stringify(report, null, 2)}\n` : `${summarizeCodexStatus(report)}\n`);
  return 0;
}

async function runCodexReconcile(argv) {
  const { options } = parseCommonOptions(argv);
  if (options.help) {
    printReconcileHelp();
    return 0;
  }
  if (!options.legacySessionAccess) {
    throw new Error("Legacy Codex session reconciliation requires --legacy-session-access");
  }
  const plan = await buildCodexReconcilePlan(options);
  const report = await applyCodexReconcilePlan(plan, options);
  process.stdout.write(options.json ? `${JSON.stringify(report, null, 2)}\n` : `${summarizeCodexReconcile(report)}\n`);
  return 0;
}

async function runCodexContext(argv) {
  const { options, rest } = parseCommonOptions(argv);
  if (options.help) {
    printContextHelp();
    return 0;
  }
  if (rest.length > 0) {
    throw new Error(`unexpected context argument: ${rest[0]}`);
  }
  if (options.prompt != null && options.promptStdin) {
    throw new Error("Use either --prompt or --prompt-stdin, not both");
  }
  if (options.promptStdin) {
    options.prompt = await readPromptStdin();
  }
  const result = await buildCodexContextPacket(options);
  process.stdout.write(`${result.serialized}\n`);
  return 0;
}

async function waitForMatchingSession(repoRoot, options = {}) {
  const startedAtMs = options.startedAtMs || Date.now();
  const timeoutMs = Number.isFinite(options.watchTimeoutMs) ? options.watchTimeoutMs : 30000;
  const deadline = Date.now() + timeoutMs;
  let latest = null;
  while (Date.now() <= deadline) {
    const sessions = await scanCodexSessions({
      ...options,
      sinceMs: startedAtMs - 1000,
    });
    latest = latestSessionForPath(sessions, repoRoot);
    if (latest && latestSessionMs(latest) >= startedAtMs - 1000) {
      return latest;
    }
    const remainingMs = deadline - Date.now();
    if (remainingMs <= 0) {
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, Math.min(500, remainingMs)));
  }
  return latest;
}

async function runCodexStart(argv) {
  const { options, rest: codexArgs } = parseCommonOptions(argv, {
    watchTimeoutMs: 30000,
  }, { passUnknownOptions: true });
  if (options.help) {
    printStartHelp();
    return 0;
  }
  if (!options.legacySessionAccess) {
    throw new Error("Legacy Codex launching and session recording requires --legacy-session-access");
  }
  const repo = resolveRepoRoot(options.path || process.cwd(), options);
  if (!repo.ok) {
    throw new Error(`Refusing to start Codex for ${repo.repoRoot}: ${repo.reason}`);
  }

  const startedAtMs = Date.now();
  const codexBin = normalizeOptionalString(options.codexBin) || "codex";
  const args = ["-C", repo.repoRoot, ...codexArgs];
  const watcher = waitForMatchingSession(repo.repoRoot, {
    ...options,
    startedAtMs,
  })
    .then(async (session) => {
      if (!session) {
        return null;
      }
      const result = await applyWorkspaceAddTabOptions({
        ...buildWorkspaceOptions(options),
        path: repo.repoRoot,
        title: options.append ? options.title : undefined,
        resumeTool: "codex",
        resumeSessionId: session.sessionId,
        append: Boolean(options.append),
      });
      return { session, result };
    })
    .catch((error) => ({ error }));

  const child = spawn(codexBin, args, {
    cwd: repo.repoRoot,
    stdio: "inherit",
    env: process.env,
  });

  const childExit = await new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("close", (code) => resolve(code == null ? 1 : code));
  });
  const watched = await watcher;
  if (!watched || watched.error) {
    process.stderr.write(
      `ORP could not automatically save the Codex session. Fallback: orp workspace add-tab ${options.workspace || DEFAULT_WORKSPACE} --here --current-codex\n`,
    );
    if (watched?.error) {
      process.stderr.write(`${watched.error instanceof Error ? watched.error.message : String(watched.error)}\n`);
    }
  } else if (options.json) {
    process.stdout.write(`${JSON.stringify({ repoRoot: repo.repoRoot, session: sessionSummary(watched.session), mutation: watched.result.mutation }, null, 2)}\n`);
  } else {
    process.stderr.write(
      `ORP saved Codex session for ${repo.repoRoot}: codex resume ${watched.session.sessionId}\n`,
    );
  }
  return childExit;
}

export async function runOrpCodexCommand(argv = []) {
  const [subcommand, ...rest] = argv;
  if (subcommand === "-h" || subcommand === "--help" || subcommand === "help") {
    printCodexHelp();
    return 0;
  }
  if (!subcommand) {
    printCodexHelp();
    return 0;
  }
  if (subcommand === "status") {
    return runCodexStatus(rest);
  }
  if (subcommand === "context") {
    return runCodexContext(rest);
  }
  if (subcommand === "reconcile") {
    return runCodexReconcile(rest);
  }
  if (subcommand === "start") {
    return runCodexStart(rest);
  }
  throw new Error(`unknown codex subcommand: ${subcommand}`);
}
