import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import fs from "node:fs";

import { resolveResumeMetadata } from "./core-plan.js";

function normalizeOptionalString(value) {
  if (value == null) {
    return null;
  }
  const trimmed = String(value).trim();
  return trimmed.length > 0 ? trimmed : null;
}

function hashText(value) {
  return crypto.createHash("sha256").update(String(value || ""), "utf8").digest("hex");
}

function getHostedObjectValue(record, ...keys) {
  for (const key of keys) {
    const value = record?.[key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return value;
    }
  }
  return null;
}

function getHostedIntegerValue(record, ...keys) {
  for (const key of keys) {
    const value = record?.[key];
    if (Number.isInteger(value)) {
      return value;
    }
  }
  return null;
}

function normalizePreviousHostedTabs(workspace) {
  const state = getHostedObjectValue(workspace, "state") || {};
  const tabs = Array.isArray(state.tabs) ? state.tabs : Array.isArray(workspace?.tabs) ? workspace.tabs : [];

  return tabs.map((tab) => {
    const resume = resolveResumeMetadata({
      resumeCommand: tab.resume_command ?? tab.resumeCommand,
      resumeTool: tab.resume_tool ?? tab.resumeTool,
      resumeSessionId:
        tab.resume_session_id ??
        tab.resumeSessionId ??
        tab.codex_session_id ??
        tab.codexSessionId ??
        tab.claude_session_id ??
        tab.claudeSessionId,
      codexSessionId: tab.codex_session_id ?? tab.codexSessionId,
      claudeSessionId: tab.claude_session_id ?? tab.claudeSessionId,
    });

    return {
      tabId: normalizeOptionalString(tab.tab_id ?? tab.tabId),
      title: normalizeOptionalString(tab.title),
      path: normalizeOptionalString(tab.project_root ?? tab.projectRoot),
      remoteUrl: normalizeOptionalString(tab.remote_url ?? tab.remoteUrl),
      remoteBranch: normalizeOptionalString(tab.remote_branch ?? tab.remoteBranch),
      bootstrapCommand: normalizeOptionalString(tab.bootstrap_command ?? tab.bootstrapCommand),
      repoLabel: normalizeOptionalString(tab.repo_label ?? tab.repoLabel),
      terminalTitle: normalizeOptionalString(tab.terminal_title ?? tab.terminalTitle),
      resumeCommand: resume.resumeCommand,
      resumeTool: resume.resumeTool,
      resumeSessionId: resume.resumeSessionId,
      currentTask: normalizeOptionalString(tab.current_task ?? tab.currentTask),
      focusSummary: normalizeOptionalString(tab.focus_summary ?? tab.focusSummary),
      trajectorySummary: normalizeOptionalString(tab.trajectory_summary ?? tab.trajectorySummary),
      lastActivityAt: normalizeOptionalString(tab.last_activity_at_utc ?? tab.lastActivityAtUtc),
      linkedIdeaId: normalizeOptionalString(tab.linked_idea_id ?? tab.linkedIdeaId),
      linkedFeatureId: normalizeOptionalString(tab.linked_feature_id ?? tab.linkedFeatureId),
      plan: tab.plan && typeof tab.plan === "object" && !Array.isArray(tab.plan) ? tab.plan : null,
      tasks: Array.isArray(tab.tasks) ? tab.tasks : [],
      used: false,
    };
  });
}

function matchPreviousHostedTab(tab, previousTabs) {
  const normalizedTitle = normalizeOptionalString(tab.title);

  let match =
    previousTabs.find(
      (candidate) => !candidate.used && candidate.path === tab.path && candidate.title === normalizedTitle,
    ) || null;

  if (!match) {
    match = previousTabs.find((candidate) => !candidate.used && candidate.path === tab.path) || null;
  }

  if (match) {
    match.used = true;
  }

  return match;
}

function buildHostedProjectGroups(tabs) {
  const groups = new Map();
  for (const tab of tabs) {
    const projectRoot = normalizeOptionalString(tab.project_root);
    if (!projectRoot) {
      continue;
    }
    if (!groups.has(projectRoot)) {
      groups.set(projectRoot, {
        title: normalizeOptionalString(tab.repo_label) || path.basename(String(projectRoot).replace(/\/+$/, "")) || projectRoot,
        project_root: projectRoot,
        remote_url: normalizeOptionalString(tab.remote_url),
        remote_branch: normalizeOptionalString(tab.remote_branch),
        bootstrap_command: normalizeOptionalString(tab.bootstrap_command),
        linked_idea_id: normalizeOptionalString(tab.linked_idea_id),
        linked_feature_id: normalizeOptionalString(tab.linked_feature_id),
        plan: tab.plan && typeof tab.plan === "object" && !Array.isArray(tab.plan) ? tab.plan : undefined,
        tasks: Array.isArray(tab.tasks) ? tab.tasks : undefined,
        sessions: [],
      });
    }
    const project = groups.get(projectRoot);
    project.remote_url = project.remote_url || normalizeOptionalString(tab.remote_url);
    project.remote_branch = project.remote_branch || normalizeOptionalString(tab.remote_branch);
    project.bootstrap_command = project.bootstrap_command || normalizeOptionalString(tab.bootstrap_command);
    project.linked_idea_id = project.linked_idea_id || normalizeOptionalString(tab.linked_idea_id);
    project.linked_feature_id = project.linked_feature_id || normalizeOptionalString(tab.linked_feature_id);
    project.plan = project.plan || (tab.plan && typeof tab.plan === "object" && !Array.isArray(tab.plan) ? tab.plan : undefined);
    if ((!Array.isArray(project.tasks) || project.tasks.length === 0) && Array.isArray(tab.tasks) && tab.tasks.length > 0) {
      project.tasks = tab.tasks;
    }
    project.sessions.push(
      Object.fromEntries(
        Object.entries({
          tab_id: normalizeOptionalString(tab.tab_id),
          title: normalizeOptionalString(tab.title),
          resume_command: normalizeOptionalString(tab.resume_command),
          resume_tool: normalizeOptionalString(tab.resume_tool),
          resume_session_id: normalizeOptionalString(tab.resume_session_id),
          codex_session_id: normalizeOptionalString(tab.codex_session_id),
          claude_session_id: normalizeOptionalString(tab.claude_session_id),
          status: normalizeOptionalString(tab.status),
          current_task: normalizeOptionalString(tab.current_task),
        }).filter(([, value]) => value !== undefined && value !== null),
      ),
    );
  }

  return [...groups.values()].map((project) =>
    Object.fromEntries(
      Object.entries({
        title: project.title,
        project_root: project.project_root,
        remote_url: project.remote_url || undefined,
        remote_branch: project.remote_branch || undefined,
        bootstrap_command: project.bootstrap_command || undefined,
        linked_idea_id: project.linked_idea_id || undefined,
        linked_feature_id: project.linked_feature_id || undefined,
        plan: project.plan || undefined,
        tasks: Array.isArray(project.tasks) && project.tasks.length > 0 ? project.tasks : undefined,
        session_count: project.sessions.length,
        sessions: project.sessions,
      }).filter(([, value]) => value !== undefined && value !== null),
    ),
  );
}

function readJsonIfExists(filePath) {
  try {
    if (!fs.existsSync(filePath)) {
      return null;
    }
    const parsed = JSON.parse(fs.readFileSync(filePath, "utf8"));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function readTextIfExists(filePath) {
  try {
    if (!fs.existsSync(filePath)) {
      return null;
    }
    const text = fs.readFileSync(filePath, "utf8").trim();
    return text.length > 0 ? text : null;
  } catch {
    return null;
  }
}

function resolveGitDir(projectRoot) {
  const dotGit = path.join(projectRoot, ".git");
  try {
    const stat = fs.statSync(dotGit);
    if (stat.isDirectory()) {
      return dotGit;
    }
    if (stat.isFile()) {
      const text = fs.readFileSync(dotGit, "utf8").trim();
      const match = text.match(/^gitdir:\s*(.+)$/i);
      if (match) {
        const gitDir = match[1].trim();
        return path.isAbsolute(gitDir) ? gitDir : path.resolve(projectRoot, gitDir);
      }
    }
  } catch {
    return null;
  }
  return null;
}

function readProjectLink(projectRoot, cache) {
  const normalizedRoot = normalizeOptionalString(projectRoot);
  if (!normalizedRoot) {
    return null;
  }
  const cacheKey = `link:${normalizedRoot}`;
  if (cache.has(cacheKey)) {
    return cache.get(cacheKey);
  }

  const gitDir = resolveGitDir(normalizedRoot);
  const linkPath = gitDir ? path.join(gitDir, "orp", "link", "project.json") : null;
  const link = linkPath ? readJsonIfExists(linkPath) : null;
  const ideaId = normalizeOptionalString(link?.idea_id ?? link?.ideaId);
  if (!ideaId) {
    cache.set(cacheKey, null);
    return null;
  }
  const frontierFeatureIds =
    link?.frontier_feature_ids && typeof link.frontier_feature_ids === "object" && !Array.isArray(link.frontier_feature_ids)
      ? link.frontier_feature_ids
      : link?.frontierFeatureIds && typeof link.frontierFeatureIds === "object" && !Array.isArray(link.frontierFeatureIds)
        ? link.frontierFeatureIds
        : {};
  const normalizedLink = {
    ideaId,
    ideaTitle: normalizeOptionalString(link?.idea_title ?? link?.ideaTitle),
    activeFeatureId: normalizeOptionalString(
      link?.active_feature_id ?? link?.activeFeatureId ?? link?.linked_feature_id ?? link?.linkedFeatureId,
    ),
    frontierFeatureIds,
  };
  cache.set(cacheKey, normalizedLink);
  return normalizedLink;
}

function findFrontierVersion(stack, versionId) {
  const versions = Array.isArray(stack?.versions) ? stack.versions : [];
  return versions.find((version) => normalizeOptionalString(version?.id) === versionId) || null;
}

function findFrontierMilestone(stack, milestoneId) {
  const versions = Array.isArray(stack?.versions) ? stack.versions : [];
  for (const version of versions) {
    const milestones = Array.isArray(version?.milestones) ? version.milestones : [];
    const milestone = milestones.find((row) => normalizeOptionalString(row?.id) === milestoneId);
    if (milestone) {
      return { version, milestone };
    }
  }
  return { version: null, milestone: null };
}

function findFrontierPhase(milestone, phaseId) {
  const phases = Array.isArray(milestone?.phases) ? milestone.phases : [];
  return phases.find((phase) => normalizeOptionalString(phase?.id) === phaseId) || null;
}

function taskStatusFromFrontierStatus(value) {
  const text = normalizeOptionalString(value)?.toLowerCase().replace(/[-\s]+/g, "_") || "";
  if (["complete", "completed", "done", "terminal"].includes(text)) {
    return "done";
  }
  if (["active", "in_progress", "running"].includes(text)) {
    return "in_progress";
  }
  if (["blocked", "stuck"].includes(text)) {
    return "blocked";
  }
  if (["skipped", "canceled", "cancelled"].includes(text)) {
    return "skipped";
  }
  return "todo";
}

function titleFromTas(tasText) {
  if (!tasText) {
    return null;
  }
  const line = tasText
    .split(/\r?\n/)
    .map((row) => row.trim())
    .find((row) => row.startsWith("# "));
  return line ? line.replace(/^#\s+/, "").trim() || null : null;
}

function buildFrontierPlan({ projectRoot, tasText, state, stack }) {
  const activeVersionId = normalizeOptionalString(state?.active_version ?? stack?.current_frontier?.active_version);
  const activeMilestoneId = normalizeOptionalString(state?.active_milestone ?? stack?.current_frontier?.active_milestone);
  const activePhaseId = normalizeOptionalString(state?.active_phase ?? stack?.current_frontier?.active_phase);
  const nextAction = normalizeOptionalString(state?.next_action ?? stack?.current_frontier?.next_action);
  const version = activeVersionId ? findFrontierVersion(stack, activeVersionId) : null;
  const { milestone } = activeMilestoneId ? findFrontierMilestone(stack, activeMilestoneId) : { milestone: null };
  const phase = activePhaseId ? findFrontierPhase(milestone, activePhaseId) : null;
  const tasTitle = titleFromTas(tasText);
  const summary =
    tasTitle ||
    normalizeOptionalString(milestone?.label) ||
    normalizeOptionalString(phase?.label) ||
    normalizeOptionalString(version?.label) ||
    nextAction;

  const bodyParts = [
    nextAction ? `Current next action: ${nextAction}` : "",
    activeVersionId || activeMilestoneId || activePhaseId
      ? `Active frontier: ${[activeVersionId, activeMilestoneId, activePhaseId].filter(Boolean).join(" / ")}`
      : "",
    tasText || "",
  ].filter(Boolean);

  if (!summary && bodyParts.length === 0) {
    return null;
  }

  return {
    summary: summary || null,
    body: bodyParts.join("\n\n"),
    source: tasText ? "orp/frontier/TAS.md" : "orp/frontier/state.json",
  };
}

function buildFrontierTasks({ state, stack }) {
  const activeMilestoneId = normalizeOptionalString(state?.active_milestone ?? stack?.current_frontier?.active_milestone);
  const activePhaseId = normalizeOptionalString(state?.active_phase ?? stack?.current_frontier?.active_phase);
  const { milestone } = activeMilestoneId ? findFrontierMilestone(stack, activeMilestoneId) : { milestone: null };
  const phases = Array.isArray(milestone?.phases) ? milestone.phases : [];

  return phases
    .map((phase, index) => {
      const id = normalizeOptionalString(phase?.id) || `frontier-task-${index + 1}`;
      const status = id === activePhaseId ? "in_progress" : taskStatusFromFrontierStatus(phase?.status);
      return {
        id,
        title:
          normalizeOptionalString(phase?.label) ||
          normalizeOptionalString(phase?.goal) ||
          id,
        status,
        completed: status === "done",
      };
    })
    .filter((task) => task.title);
}

function readProjectFrontierContext(projectRoot, cache) {
  const normalizedRoot = normalizeOptionalString(projectRoot);
  if (!normalizedRoot) {
    return null;
  }
  if (cache.has(normalizedRoot)) {
    return cache.get(normalizedRoot);
  }

  const frontierRoot = path.join(normalizedRoot, "orp", "frontier");
  const state = readJsonIfExists(path.join(frontierRoot, "state.json"));
  const stack = readJsonIfExists(path.join(frontierRoot, "version-stack.json"));
  const tasText = readTextIfExists(path.join(frontierRoot, "TAS.md"));
  const projectLink = readProjectLink(normalizedRoot, cache);
  if (!state && !stack && !tasText && !projectLink) {
    cache.set(normalizedRoot, null);
    return null;
  }

  const context = {
    plan: buildFrontierPlan({ projectRoot: normalizedRoot, tasText, state, stack }),
    tasks: stack ? buildFrontierTasks({ state, stack }) : [],
    link: projectLink,
  };
  cache.set(normalizedRoot, context);
  return context;
}

export function enrichWorkspaceTabsWithProjectContext(tabs = []) {
  const projectContextCache = new Map();
  return tabs.map((tab) => {
    const projectRoot = normalizeOptionalString(tab?.path ?? tab?.project_root ?? tab?.projectRoot);
    const projectContext = readProjectFrontierContext(projectRoot, projectContextCache);
    if (!projectContext) {
      return tab;
    }
    const plan =
      tab?.plan && typeof tab.plan === "object" && !Array.isArray(tab.plan)
        ? tab.plan
        : projectContext.plan || undefined;
    const tasks =
      Array.isArray(tab?.tasks) && tab.tasks.length > 0
        ? tab.tasks
        : Array.isArray(projectContext.tasks) && projectContext.tasks.length > 0
          ? projectContext.tasks
          : undefined;

    return Object.fromEntries(
      Object.entries({
        ...tab,
        linkedIdeaId: tab?.linkedIdeaId ?? tab?.linked_idea_id ?? projectContext.link?.ideaId,
        linkedFeatureId: tab?.linkedFeatureId ?? tab?.linked_feature_id ?? projectContext.link?.activeFeatureId,
        plan,
        tasks,
      }).filter(([, value]) => value !== undefined && value !== null),
    );
  });
}

export function enrichWorkspaceManifestWithProjectContext(manifest) {
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    return manifest;
  }
  return {
    ...manifest,
    tabs: enrichWorkspaceTabsWithProjectContext(Array.isArray(manifest.tabs) ? manifest.tabs : []),
  };
}

export function buildHostedWorkspaceState(manifest, options = {}) {
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    throw new Error("workspace manifest is required to build a hosted workspace state payload");
  }
  if (!Array.isArray(manifest.tabs) || manifest.tabs.length === 0) {
    throw new Error("workspace manifest must include at least one saved tab");
  }

  const previousWorkspace =
    options.previousWorkspace && typeof options.previousWorkspace === "object" && !Array.isArray(options.previousWorkspace)
      ? options.previousWorkspace
      : null;
  const previousState = getHostedObjectValue(previousWorkspace, "state") || {};
  const capturedAt = normalizeOptionalString(options.capturedAt) || new Date().toISOString();
  const updatedAt = normalizeOptionalString(options.updatedAt) || capturedAt;
  const previousTabs = normalizePreviousHostedTabs(previousWorkspace);
  const projectContextCache = new Map();

  const tabs = manifest.tabs.map((tab, index) => {
    const previous = matchPreviousHostedTab(tab, previousTabs);
    const title = normalizeOptionalString(tab.title) || previous?.title || null;
    const projectRoot = normalizeOptionalString(tab.path);
    const projectContext = readProjectFrontierContext(projectRoot, projectContextCache);
    const repoLabel = previous?.repoLabel || path.basename(String(projectRoot).replace(/\/+$/, "")) || projectRoot;
    const terminalTitle = previous?.terminalTitle || title || repoLabel;
    const resume = resolveResumeMetadata({
      resumeCommand: tab.resumeCommand,
      resumeTool: tab.resumeTool,
      resumeSessionId: tab.resumeSessionId ?? tab.sessionId,
      codexSessionId: tab.codexSessionId,
      claudeSessionId: tab.claudeSessionId,
    });
    const previousResume = resolveResumeMetadata(previous || {});
    const resumeCommand = resume.resumeCommand || previousResume.resumeCommand || undefined;
    const resumeTool = resume.resumeTool || previousResume.resumeTool || undefined;
    const resumeSessionId = resume.resumeSessionId || previousResume.resumeSessionId || undefined;
    const codexSessionId =
      (resumeTool === "codex" ? resumeSessionId : null) ||
      (previousResume.resumeTool === "codex" ? previousResume.resumeSessionId : null) ||
      undefined;
    const claudeSessionId =
      (resumeTool === "claude" ? resumeSessionId : null) ||
      (previousResume.resumeTool === "claude" ? previousResume.resumeSessionId : null) ||
      undefined;
    const tabIdSeed = JSON.stringify({
      workspaceId: manifest.workspaceId || previousWorkspace?.workspace_id || previousWorkspace?.id || "workspace",
      projectRoot,
      title,
      orderIndex: index,
    });

    return Object.fromEntries(
      Object.entries({
        tab_id: previous?.tabId || `tab-${hashText(tabIdSeed).slice(0, 16)}`,
        order_index: index,
        title: title || undefined,
        project_root: projectRoot,
        remote_url: normalizeOptionalString(tab.remoteUrl) || previous?.remoteUrl || undefined,
        remote_branch: normalizeOptionalString(tab.remoteBranch) || previous?.remoteBranch || undefined,
        bootstrap_command: normalizeOptionalString(tab.bootstrapCommand) || previous?.bootstrapCommand || undefined,
        repo_label: repoLabel || undefined,
        resume_command: resumeCommand,
        resume_tool: resumeTool,
        resume_session_id: resumeSessionId,
        codex_session_id: codexSessionId,
        claude_session_id: claudeSessionId,
        terminal_title: terminalTitle || undefined,
        status: "active",
        current_task: previous?.currentTask || undefined,
        focus_summary: previous?.focusSummary || undefined,
        trajectory_summary: previous?.trajectorySummary || undefined,
        last_activity_at_utc: previous?.lastActivityAt || undefined,
        linked_feature_id:
          normalizeOptionalString(tab.linkedFeatureId ?? tab.linked_feature_id) ||
          projectContext?.link?.activeFeatureId ||
          previous?.linkedFeatureId ||
          undefined,
        linked_idea_id:
          normalizeOptionalString(tab.linkedIdeaId ?? tab.linked_idea_id) ||
          projectContext?.link?.ideaId ||
          previous?.linkedIdeaId ||
          undefined,
        plan: projectContext?.plan || previous?.plan || undefined,
        tasks:
          Array.isArray(projectContext?.tasks) && projectContext.tasks.length > 0
            ? projectContext.tasks
            : Array.isArray(previous?.tasks) && previous.tasks.length > 0
              ? previous.tasks
              : undefined,
      }).filter(([, value]) => value !== undefined && value !== null),
    );
  });
  const projects = buildHostedProjectGroups(tabs);

  const captureContext = Object.fromEntries(
    Object.entries({
      source_app: "terminal-ledger",
      mode: "manual",
      host: os.hostname(),
      machine_id: normalizeOptionalString(manifest.machine?.machineId) || undefined,
      machine_label: normalizeOptionalString(manifest.machine?.machineLabel) || undefined,
      platform: normalizeOptionalString(manifest.machine?.platform) || process.platform,
      terminal_frontend: "terminal",
      durable_backend: options.durableBackend || "manual-ledger",
    }).filter(([, value]) => value !== undefined && value !== null),
  );

  const stateVersion = Math.max(1, (getHostedIntegerValue(previousState, "state_version", "stateVersion") || 0) + 1);
  const snapshotSeed = JSON.stringify({
    workspaceId: manifest.workspaceId || previousWorkspace?.workspace_id || previousWorkspace?.id || "workspace",
    capturedAt,
    tabs: tabs.map((tab) => ({
      order_index: tab.order_index,
      project_root: tab.project_root,
      title: tab.title || null,
      codex_session_id: tab.codex_session_id || null,
      claude_session_id: tab.claude_session_id || null,
    })),
  });

  return Object.fromEntries(
    Object.entries({
      state_version: stateVersion,
      snapshot_id: `snapshot-${hashText(snapshotSeed).slice(0, 16)}`,
      summary: normalizeOptionalString(previousState.summary),
      current_focus: normalizeOptionalString(previousState.current_focus ?? previousState.currentFocus),
      trajectory: normalizeOptionalString(previousState.trajectory),
      opened_at_utc: normalizeOptionalString(previousState.opened_at_utc ?? previousState.openedAtUtc),
      captured_at_utc: capturedAt,
      updated_at_utc: updatedAt,
      tab_count: tabs.length,
      project_count: projects.length,
      capture_context: Object.keys(captureContext).length > 0 ? captureContext : undefined,
      projects,
      tabs,
    }).filter(([, value]) => value !== undefined && value !== null),
  );
}
