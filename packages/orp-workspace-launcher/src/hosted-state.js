import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";

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
        sessions: [],
      });
    }
    const project = groups.get(projectRoot);
    project.remote_url = project.remote_url || normalizeOptionalString(tab.remote_url);
    project.remote_branch = project.remote_branch || normalizeOptionalString(tab.remote_branch);
    project.bootstrap_command = project.bootstrap_command || normalizeOptionalString(tab.bootstrap_command);
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
        session_count: project.sessions.length,
        sessions: project.sessions,
      }).filter(([, value]) => value !== undefined && value !== null),
    ),
  );
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

  const tabs = manifest.tabs.map((tab, index) => {
    const previous = matchPreviousHostedTab(tab, previousTabs);
    const title = normalizeOptionalString(tab.title) || previous?.title || null;
    const projectRoot = normalizeOptionalString(tab.path);
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
        linked_idea_id: previous?.linkedIdeaId || undefined,
        linked_feature_id: previous?.linkedFeatureId || undefined,
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
