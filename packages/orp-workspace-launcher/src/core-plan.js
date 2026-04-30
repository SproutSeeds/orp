import path from "node:path";

export const WORKSPACE_SCHEMA_VERSION = "1";

const SUPPORTED_RESUME_TOOLS = new Set(["codex", "claude"]);
const CODEX_RESUME_PATTERN = /^\s*codex\s+resume\s+([^\s]+)(?:\s+.*)?$/i;
const CLAUDE_LEGACY_RESUME_PATTERN = /^\s*claude\s+resume\s+([^\s]+)(?:\s+.*)?$/i;
const CLAUDE_FLAG_RESUME_PATTERN = /^\s*claude\s+(?:--resume|-r)(?:=|\s+)([^\s]+)(?:\s+.*)?$/i;
const STRUCTURED_WORKSPACE_PATTERN = /```orp-workspace\s*([\s\S]*?)```/i;

function partitionOnColon(value) {
  const index = value.indexOf(":");
  if (index === -1) {
    return [value, ""];
  }
  return [value.slice(0, index), value.slice(index + 1)];
}

function shellQuote(value) {
  const text = String(value);
  if (text.length === 0) {
    return "''";
  }
  return `'${text.replace(/'/g, `'\"'\"'`)}'`;
}

function normalizeDisplayPath(value) {
  const trimmed = String(value).trim();
  if (trimmed === "/") {
    return trimmed;
  }
  return trimmed.replace(/\/+$/, "");
}

function hashText(value) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash.toString(36);
}

function slugify(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized || "workspace";
}

function validateAbsolutePath(value, label) {
  if (typeof value !== "string" || !value.trim().startsWith("/")) {
    throw new Error(`${label} must be an absolute path`);
  }
  return value.trim();
}

function normalizeOptionalString(value) {
  if (value == null) {
    return null;
  }
  const trimmed = String(value).trim();
  return trimmed.length > 0 ? trimmed : null;
}

function normalizeOptionalCommand(value) {
  return normalizeOptionalString(value);
}

function normalizeOptionalUrl(value, label) {
  const normalized = normalizeOptionalString(value);
  if (!normalized) {
    return null;
  }
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(normalized) || /^[^@\s]+@[^:\s]+:[^\s]+$/i.test(normalized)) {
    return normalized;
  }
  throw new Error(`${label} must look like a git remote URL`);
}

function normalizeMachineMetadata(rawMachine) {
  if (rawMachine == null) {
    return null;
  }
  if (!rawMachine || typeof rawMachine !== "object" || Array.isArray(rawMachine)) {
    throw new Error("workspace manifest machine metadata must be an object");
  }

  const machine = Object.fromEntries(
    Object.entries({
      machineId: normalizeOptionalString(rawMachine.machineId),
      machineLabel: normalizeOptionalString(rawMachine.machineLabel),
      platform: normalizeOptionalString(rawMachine.platform),
      host: normalizeOptionalString(rawMachine.host),
    }).filter(([, value]) => value != null),
  );

  return Object.keys(machine).length > 0 ? machine : null;
}

function normalizeResumeTool(value) {
  const trimmed = normalizeOptionalString(value)?.toLowerCase() || null;
  return trimmed && SUPPORTED_RESUME_TOOLS.has(trimmed) ? trimmed : null;
}

export function buildCanonicalResumeCommand(tool, sessionId) {
  const resumeTool = normalizeResumeTool(tool);
  const resumeSessionId = normalizeOptionalString(sessionId);
  if (!resumeTool || !resumeSessionId) {
    return null;
  }
  if (resumeTool === "claude") {
    return `claude --resume ${resumeSessionId}`;
  }
  return `${resumeTool} resume ${resumeSessionId}`;
}

export function parseResumeCommandText(value) {
  const trimmed = normalizeOptionalString(value);
  if (!trimmed) {
    return {
      resumeCommand: null,
      resumeTool: null,
      resumeSessionId: null,
    };
  }

  const codexMatch = trimmed.match(CODEX_RESUME_PATTERN);
  if (codexMatch) {
    return {
      resumeCommand: trimmed,
      resumeTool: "codex",
      resumeSessionId: normalizeOptionalString(codexMatch[1]),
    };
  }

  const claudeFlagMatch = trimmed.match(CLAUDE_FLAG_RESUME_PATTERN);
  if (claudeFlagMatch) {
    return {
      resumeCommand: trimmed,
      resumeTool: "claude",
      resumeSessionId: normalizeOptionalString(claudeFlagMatch[1]),
    };
  }

  const claudeLegacyMatch = trimmed.match(CLAUDE_LEGACY_RESUME_PATTERN);
  if (!claudeLegacyMatch) {
    return {
      resumeCommand: null,
      resumeTool: null,
      resumeSessionId: null,
    };
  }

  return {
    resumeCommand: trimmed,
    resumeTool: "claude",
    resumeSessionId: normalizeOptionalString(claudeLegacyMatch[1]),
  };
}

export function resolveResumeMetadata(raw = {}) {
  const parsedCommand = parseResumeCommandText(raw.resumeCommand ?? raw.remainder);
  const explicitTool = normalizeResumeTool(raw.resumeTool);
  const explicitResumeSessionId = normalizeOptionalString(raw.resumeSessionId ?? raw.sessionId);
  const legacyCodexSessionId = normalizeOptionalString(raw.codexSessionId);
  const legacyClaudeSessionId = normalizeOptionalString(raw.claudeSessionId);

  const resumeTool =
    parsedCommand.resumeTool ||
    explicitTool ||
    (explicitResumeSessionId ? "codex" : null) ||
    (legacyCodexSessionId ? "codex" : null) ||
    (legacyClaudeSessionId ? "claude" : null);

  const resumeSessionId =
    parsedCommand.resumeSessionId ||
    explicitResumeSessionId ||
    (resumeTool === "codex" ? legacyCodexSessionId : null) ||
    (resumeTool === "claude" ? legacyClaudeSessionId : null) ||
    legacyCodexSessionId ||
    legacyClaudeSessionId ||
    null;

  const resumeCommand =
    parsedCommand.resumeCommand ||
    buildCanonicalResumeCommand(resumeTool, resumeSessionId);

  return {
    resumeCommand,
    resumeTool,
    resumeSessionId,
  };
}

export function getResumeCommand(entry) {
  return resolveResumeMetadata(entry).resumeCommand;
}

function normalizeOptionalPositiveInteger(value, label) {
  if (value == null || value === "") {
    return null;
  }
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw new Error(`${label} must be a positive integer`);
  }
  return parsed;
}

function normalizeOptionalNonNegativeInteger(value, label) {
  if (value == null || value === "") {
    return null;
  }
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${label} must be a non-negative integer`);
  }
  return parsed;
}

function normalizeOptionalPositiveNumber(value, label) {
  if (value == null || value === "") {
    return null;
  }
  const parsed = Number(String(value));
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${label} must be a positive number`);
  }
  return parsed;
}

function normalizeCaptureMetadata(rawCapture) {
  if (rawCapture == null) {
    return null;
  }
  if (!rawCapture || typeof rawCapture !== "object" || Array.isArray(rawCapture)) {
    throw new Error("workspace manifest capture metadata must be an object");
  }

  const capture = Object.fromEntries(
    Object.entries({
      sourceApp: normalizeOptionalString(rawCapture.sourceApp),
      mode: normalizeOptionalString(rawCapture.mode),
      host: normalizeOptionalString(rawCapture.host),
      windowId: normalizeOptionalPositiveInteger(rawCapture.windowId, "workspace manifest capture.windowId"),
      windowIndex: normalizeOptionalPositiveInteger(rawCapture.windowIndex, "workspace manifest capture.windowIndex"),
      tabCount: normalizeOptionalNonNegativeInteger(rawCapture.tabCount, "workspace manifest capture.tabCount"),
      capturedAt: normalizeOptionalString(rawCapture.capturedAt),
      trackingStartedAt: normalizeOptionalString(rawCapture.trackingStartedAt),
      pollSeconds: normalizeOptionalPositiveNumber(rawCapture.pollSeconds, "workspace manifest capture.pollSeconds"),
    }).filter(([, value]) => value != null),
  );

  return Object.keys(capture).length > 0 ? capture : null;
}

function normalizeStructuredTab(rawTab, index) {
  if (!rawTab || typeof rawTab !== "object" || Array.isArray(rawTab)) {
    throw new Error(`workspace tab ${index + 1} must be an object`);
  }

  const pathValue = validateAbsolutePath(rawTab.path, `workspace tab ${index + 1} path`);
  const title = normalizeOptionalString(rawTab.title);
  const resume = resolveResumeMetadata(rawTab);
  const tmuxSessionName = normalizeOptionalString(rawTab.tmuxSessionName);
  const plan = rawTab.plan && typeof rawTab.plan === "object" && !Array.isArray(rawTab.plan) ? rawTab.plan : null;
  const tasks = Array.isArray(rawTab.tasks) ? rawTab.tasks : [];

  return {
    lineNumber: index + 1,
    rawLine: JSON.stringify(rawTab),
    path: pathValue,
    remainder: resume.resumeCommand || "",
    sessionId: resume.resumeSessionId,
    resumeCommand: resume.resumeCommand,
    resumeTool: resume.resumeTool,
    title,
    tmuxSessionName,
    remoteUrl: normalizeOptionalUrl(rawTab.remoteUrl, `workspace tab ${index + 1} remoteUrl`),
    remoteBranch: normalizeOptionalString(rawTab.remoteBranch),
    bootstrapCommand: normalizeOptionalCommand(rawTab.bootstrapCommand),
    linkedIdeaId: normalizeOptionalString(rawTab.linkedIdeaId ?? rawTab.linked_idea_id),
    linkedFeatureId: normalizeOptionalString(rawTab.linkedFeatureId ?? rawTab.linked_feature_id),
    plan,
    tasks,
  };
}

function normalizeStructuredProject(rawProject, projectIndex) {
  if (!rawProject || typeof rawProject !== "object" || Array.isArray(rawProject)) {
    throw new Error(`workspace project ${projectIndex + 1} must be an object`);
  }

  const projectPath = validateAbsolutePath(rawProject.path, `workspace project ${projectIndex + 1} path`);
  const sessions = Array.isArray(rawProject.sessions) && rawProject.sessions.length > 0 ? rawProject.sessions : [{}];

  return sessions.map((rawSession, sessionIndex) => {
    if (!rawSession || typeof rawSession !== "object" || Array.isArray(rawSession)) {
      throw new Error(`workspace project ${projectIndex + 1} session ${sessionIndex + 1} must be an object`);
    }
    return normalizeStructuredTab(
      {
        title: rawSession.title ?? rawProject.title,
        path: projectPath,
        remoteUrl: rawSession.remoteUrl ?? rawProject.remoteUrl,
        remoteBranch: rawSession.remoteBranch ?? rawProject.remoteBranch,
        bootstrapCommand: rawSession.bootstrapCommand ?? rawProject.bootstrapCommand,
        resumeCommand: rawSession.resumeCommand,
        resumeTool: rawSession.resumeTool,
        resumeSessionId: rawSession.resumeSessionId ?? rawSession.sessionId,
        codexSessionId: rawSession.codexSessionId,
        claudeSessionId: rawSession.claudeSessionId,
        tmuxSessionName: rawSession.tmuxSessionName,
        linkedIdeaId: rawSession.linkedIdeaId ?? rawSession.linked_idea_id ?? rawProject.linkedIdeaId ?? rawProject.linked_idea_id,
        linkedFeatureId:
          rawSession.linkedFeatureId ??
          rawSession.linked_feature_id ??
          rawProject.linkedFeatureId ??
          rawProject.linked_feature_id,
        plan: rawSession.plan ?? rawProject.plan,
        tasks: rawSession.tasks ?? rawProject.tasks,
      },
      sessionIndex,
    );
  });
}

export function normalizeWorkspaceManifest(rawManifest) {
  if (!rawManifest || typeof rawManifest !== "object" || Array.isArray(rawManifest)) {
    throw new Error("workspace manifest must be a JSON object");
  }

  const version = String(rawManifest.version ?? WORKSPACE_SCHEMA_VERSION);
  if (version !== WORKSPACE_SCHEMA_VERSION) {
    throw new Error(`unsupported workspace manifest version: ${version}`);
  }

  const hasProjects = Array.isArray(rawManifest.projects);
  const hasTabs = Array.isArray(rawManifest.tabs);
  if (!hasProjects && !hasTabs) {
    throw new Error("workspace manifest must include a tabs array or projects array");
  }

  const tabs = hasProjects
    ? rawManifest.projects.flatMap((project, index) => normalizeStructuredProject(project, index))
    : rawManifest.tabs.map((tab, index) => normalizeStructuredTab(tab, index));
  return {
    version,
    workspaceId: normalizeOptionalString(rawManifest.workspaceId),
    title: normalizeOptionalString(rawManifest.title),
    tmuxPrefix: normalizeOptionalString(rawManifest.tmuxPrefix),
    machine: normalizeMachineMetadata(rawManifest.machine),
    capture: normalizeCaptureMetadata(rawManifest.capture),
    tabs,
  };
}

export function extractStructuredWorkspaceFromNotes(notes) {
  const match = String(notes || "").match(STRUCTURED_WORKSPACE_PATTERN);
  if (!match) {
    return null;
  }

  let parsed;
  try {
    parsed = JSON.parse(match[1]);
  } catch (error) {
    throw new Error(
      `failed to parse \`\`\`orp-workspace\`\`\` JSON: ${error instanceof Error ? error.message : String(error)}`,
    );
  }

  return normalizeWorkspaceManifest(parsed);
}

export function deriveBaseTitle(entry) {
  if (entry.title && String(entry.title).trim().length > 0) {
    return String(entry.title).trim();
  }
  const normalized = normalizeDisplayPath(entry.path);
  return path.basename(normalized) || normalized;
}

export function buildWorkspaceProjectGroups(entries = []) {
  const groups = new Map();

  for (const entry of entries) {
    const projectPath = validateAbsolutePath(entry.path, "workspace project path");
    if (!groups.has(projectPath)) {
      groups.set(projectPath, {
        title: deriveBaseTitle(entry),
        path: projectPath,
        remoteUrl: normalizeOptionalUrl(entry.remoteUrl, "workspace project remoteUrl"),
        remoteBranch: normalizeOptionalString(entry.remoteBranch),
        bootstrapCommand: normalizeOptionalCommand(entry.bootstrapCommand),
        linkedIdeaId: normalizeOptionalString(entry.linkedIdeaId),
        linkedFeatureId: normalizeOptionalString(entry.linkedFeatureId),
        plan: entry.plan && typeof entry.plan === "object" && !Array.isArray(entry.plan) ? entry.plan : null,
        tasks: Array.isArray(entry.tasks) && entry.tasks.length > 0 ? entry.tasks : [],
        sessions: [],
      });
    }

    const project = groups.get(projectPath);
    project.remoteUrl = project.remoteUrl || normalizeOptionalUrl(entry.remoteUrl, "workspace project remoteUrl");
    project.remoteBranch = project.remoteBranch || normalizeOptionalString(entry.remoteBranch);
    project.bootstrapCommand = project.bootstrapCommand || normalizeOptionalCommand(entry.bootstrapCommand);
    project.linkedIdeaId = project.linkedIdeaId || normalizeOptionalString(entry.linkedIdeaId);
    project.linkedFeatureId = project.linkedFeatureId || normalizeOptionalString(entry.linkedFeatureId);
    project.plan =
      project.plan ||
      (entry.plan && typeof entry.plan === "object" && !Array.isArray(entry.plan) ? entry.plan : null);
    if ((!Array.isArray(project.tasks) || project.tasks.length === 0) && Array.isArray(entry.tasks) && entry.tasks.length > 0) {
      project.tasks = entry.tasks;
    }

    const resume = resolveResumeMetadata(entry);
    project.sessions.push(
      Object.fromEntries(
        Object.entries({
          title: normalizeOptionalString(entry.title) || deriveBaseTitle(entry),
          resumeCommand: resume.resumeCommand || undefined,
          resumeTool: resume.resumeTool || undefined,
          resumeSessionId: resume.resumeSessionId || undefined,
          codexSessionId: resume.resumeTool === "codex" ? resume.resumeSessionId || undefined : undefined,
          claudeSessionId: resume.resumeTool === "claude" ? resume.resumeSessionId || undefined : undefined,
        }).filter(([, value]) => value !== undefined),
      ),
    );
  }

  return [...groups.values()].map((project) =>
    Object.fromEntries(
      Object.entries({
        title: project.title,
        path: project.path,
        remoteUrl: project.remoteUrl || undefined,
        remoteBranch: project.remoteBranch || undefined,
        bootstrapCommand: project.bootstrapCommand || undefined,
        linkedIdeaId: project.linkedIdeaId || undefined,
        linkedFeatureId: project.linkedFeatureId || undefined,
        plan: project.plan || undefined,
        tasks: Array.isArray(project.tasks) && project.tasks.length > 0 ? project.tasks : undefined,
        sessionCount: project.sessions.length,
        sessions: project.sessions,
      }).filter(([, value]) => value !== undefined),
    ),
  );
}

export function deriveTmuxSessionName(entry, options = {}) {
  if (entry.tmuxSessionName && String(entry.tmuxSessionName).trim().length > 0) {
    return String(entry.tmuxSessionName).trim();
  }

  const prefix = (options.tmuxPrefix || "orp").trim() || "orp";
  const base = deriveBaseTitle(entry)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "workspace";
  const entropy = hashText(`${entry.path}:${getResumeCommand(entry) || entry.sessionId || ""}:${entry.lineNumber || 0}`).slice(
    0,
    6,
  );
  return `${prefix}-${base}-${entropy}`.slice(0, 64);
}

export function deriveWorkspaceId(source, parsed) {
  if (parsed.manifest?.workspaceId) {
    return parsed.manifest.workspaceId;
  }

  if (source.sourceType === "hosted-idea" && source.idea?.id) {
    return `idea-${source.idea.id}`;
  }

  if (source.sourceType === "workspace-file" && source.sourcePath) {
    return `file-${slugify(path.basename(source.sourcePath, path.extname(source.sourcePath)))}-${hashText(source.sourcePath).slice(0, 6)}`;
  }

  if (source.sourcePath) {
    return `file-${hashText(source.sourcePath).slice(0, 8)}`;
  }

  return `workspace-${hashText(`${source.sourceType}:${source.sourceLabel}`).slice(0, 8)}`;
}

export function parseCorePlanNotes(notes) {
  const entries = [];
  const skipped = [];

  for (const [index, rawLine] of String(notes || "").split(/\r?\n/).entries()) {
    const lineNumber = index + 1;
    const line = rawLine.trim();
    if (!line) {
      continue;
    }
    if (!line.startsWith("/")) {
      skipped.push({ lineNumber, rawLine });
      continue;
    }

    const [rawPath, rawRemainder] = partitionOnColon(line);
    const workspacePath = rawPath.trim();
    const remainder = rawRemainder.trim();
    const resume = resolveResumeMetadata({ resumeCommand: remainder });

    entries.push({
      lineNumber,
      rawLine,
      path: workspacePath,
      remainder,
      sessionId: resume.resumeSessionId,
      resumeCommand: resume.resumeCommand,
      resumeTool: resume.resumeTool,
      title: null,
      tmuxSessionName: null,
    });
  }

  return { entries, skipped, manifest: null, parseMode: "notes" };
}

export function parseWorkspaceSource(source) {
  if (source.workspaceManifest) {
    const manifest = normalizeWorkspaceManifest(source.workspaceManifest);
    return {
      entries: manifest.tabs,
      skipped: [],
      manifest,
      parseMode: "manifest",
    };
  }

  const structuredManifest = extractStructuredWorkspaceFromNotes(source.notes || "");
  if (structuredManifest) {
    return {
      entries: structuredManifest.tabs,
      skipped: [],
      manifest: structuredManifest,
      parseMode: "manifest",
    };
  }

  return parseCorePlanNotes(source.notes || "");
}

export function buildDirectCommand(entry, options = {}) {
  const commands = [`cd ${shellQuote(entry.path)}`];
  const resumeCommand = options.resume !== false ? getResumeCommand(entry) : null;
  if (resumeCommand) {
    commands.push(resumeCommand);
  }
  return commands.join(" && ");
}

export function buildCloneCommand(entry, options = {}) {
  const remoteUrl = normalizeOptionalUrl(entry?.remoteUrl, "workspace tab remoteUrl");
  if (!remoteUrl) {
    return null;
  }
  const repoDir = options.repoDir || path.basename(normalizeDisplayPath(entry.path));
  const branch = normalizeOptionalString(entry?.remoteBranch);
  const parts = ["git", "clone"];
  if (branch) {
    parts.push("--branch", shellQuote(branch));
  }
  parts.push(shellQuote(remoteUrl));
  if (repoDir) {
    parts.push(shellQuote(repoDir));
  }
  return parts.join(" ");
}

export function buildSetupCommand(entry, options = {}) {
  const cloneCommand = buildCloneCommand(entry, options);
  const bootstrapCommand = normalizeOptionalCommand(entry?.bootstrapCommand);
  if (!cloneCommand && !bootstrapCommand) {
    return null;
  }
  if (cloneCommand && bootstrapCommand) {
    const repoDir = options.repoDir || path.basename(normalizeDisplayPath(entry.path));
    return `${cloneCommand} && cd ${shellQuote(repoDir)} && ${bootstrapCommand}`;
  }
  return cloneCommand || bootstrapCommand;
}

export function buildTmuxPresentationCommands(entry, options = {}) {
  const sessionName = options.sessionName || deriveTmuxSessionName(entry, options);
  const quotedSession = shellQuote(sessionName);
  const targetWindow = `${quotedSession}:0`;
  const title = options.displayTitle || entry.displayTitle || deriveBaseTitle(entry);

  return [
    `tmux set-option -t ${quotedSession} set-titles on`,
    `tmux set-option -t ${quotedSession} set-titles-string ${shellQuote(title)}`,
    `tmux set-window-option -t ${targetWindow} automatic-rename off`,
    `tmux set-window-option -t ${targetWindow} allow-rename off`,
    `tmux rename-window -t ${targetWindow} ${shellQuote(title)}`,
  ];
}

export function buildTmuxCommand(entry, options = {}) {
  const sessionName = options.sessionName || deriveTmuxSessionName(entry, options);
  const sessionNameQuoted = shellQuote(sessionName);
  const loginShell = options.loginShell || process.env.SHELL || "/bin/zsh";
  const bootstrapCommand = `cd ${shellQuote(entry.path)} && exec ${shellQuote(loginShell)} -l`;
  const presentationCommands = buildTmuxPresentationCommands(entry, { ...options, sessionName });
  const createParts = [
    `tmux new-session -d -s ${sessionNameQuoted} ${shellQuote(bootstrapCommand)}`,
    ...presentationCommands,
  ];

  const resumeCommand = options.resume !== false ? getResumeCommand(entry) : null;
  if (resumeCommand) {
    createParts.push(
      `tmux send-keys -t ${sessionNameQuoted} ${shellQuote(resumeCommand)} C-m`,
    );
  }

  return [
    `if tmux has-session -t ${sessionNameQuoted} 2>/dev/null; then`,
    `${presentationCommands.join(" && ")} && tmux attach-session -t ${sessionNameQuoted};`,
    "else",
    `${createParts.join(" && ")} && tmux attach-session -t ${sessionNameQuoted};`,
    "fi",
  ].join(" ");
}

export function buildLaunchPlan(entries, options = {}) {
  const titleCounts = new Map();

  return entries.map((entry) => {
    const baseTitle = deriveBaseTitle(entry);
    const occurrence = (titleCounts.get(baseTitle) || 0) + 1;
    titleCounts.set(baseTitle, occurrence);

    const title = occurrence === 1 ? baseTitle : `${baseTitle} (${occurrence})`;
    const sessionName = options.tmux ? deriveTmuxSessionName(entry, options) : null;
    // iTerm already appends "(tmux)" when a tab is backed by a tmux session,
    // so the title we push into tmux should stay clean.
    const displayTitle = title;
    const command = options.tmux
      ? buildTmuxCommand(entry, { ...options, sessionName, displayTitle })
      : buildDirectCommand(entry, options);

    return {
      ...entry,
      title,
      displayTitle,
      sessionName,
      command,
      mode: options.tmux ? "tmux" : "direct",
    };
  });
}

export function summarizeLaunchPlan(plan) {
  const terminalLabel = plan.terminalApp === "terminal" ? "Terminal.app" : "iTerm";
  const lines = [
    `Source: ${plan.sourceLabel}`,
    `Workspace ID: ${plan.workspaceId}`,
    `Tabs: ${plan.tabs.length}`,
    `Mode: ${plan.tmux ? `${terminalLabel} + tmux` : `${terminalLabel} direct`}`,
    `Parse mode: ${plan.parseMode}`,
    "",
  ];

  for (const [index, tab] of plan.tabs.entries()) {
    lines.push(`${String(index + 1).padStart(2, "0")}. ${tab.title}`);
    lines.push(`    path: ${tab.path}`);
    if (tab.resumeCommand) {
      lines.push(`    resume: ${tab.resumeCommand}`);
    }
    if (tab.sessionName) {
      lines.push(`    tmux: ${tab.sessionName}`);
    }
    lines.push(`    command: ${tab.command}`);
  }

  if (plan.skipped.length > 0) {
    lines.push("");
    lines.push("Skipped lines:");
    for (const skipped of plan.skipped) {
      lines.push(`  line ${skipped.lineNumber}: ${skipped.rawLine}`);
    }
  }

  return lines.join("\n");
}
