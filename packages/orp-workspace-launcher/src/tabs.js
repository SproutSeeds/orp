import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";

import {
  buildCloneCommand,
  buildDirectCommand,
  buildLaunchPlan,
  buildSetupCommand,
  buildWorkspaceProjectGroups,
  deriveWorkspaceId,
  getResumeCommand,
  parseWorkspaceSource,
} from "./core-plan.js";
import { loadWorkspaceSource } from "./orp.js";

const SESSION_ID_PATTERN = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

function normalizeOptionalString(value) {
  if (value == null) {
    return null;
  }
  const trimmed = String(value).trim();
  return trimmed.length > 0 ? trimmed : null;
}

function resolveCodexHome(options = {}) {
  return (
    normalizeOptionalString(options.codexHome) ||
    normalizeOptionalString(process.env.CODEX_HOME) ||
    path.join(os.homedir(), ".codex")
  );
}

function collectCodexSessionIds(tabs = []) {
  return new Set(
    tabs
      .filter((tab) => tab.resumeTool === "codex")
      .map((tab) => normalizeOptionalString(tab.sessionId))
      .map((sessionId) => sessionId?.toLowerCase())
      .filter(Boolean),
  );
}

function sessionIdsInFilename(filename, wantedSessionIds) {
  const matches = new Set();
  for (const match of filename.matchAll(SESSION_ID_PATTERN)) {
    const sessionId = match[0].toLowerCase();
    if (wantedSessionIds.has(sessionId)) {
      matches.add(sessionId);
    }
  }

  if (matches.size > 0) {
    return matches;
  }

  for (const sessionId of wantedSessionIds) {
    if (filename.includes(sessionId)) {
      matches.add(sessionId);
    }
  }
  return matches;
}

function rememberActivity(activityBySessionId, sessionId, filePath, stat) {
  const current = activityBySessionId.get(sessionId);
  if (!current || stat.mtimeMs > current.mtimeMs) {
    activityBySessionId.set(sessionId, {
      mtimeMs: stat.mtimeMs,
      filePath,
    });
  }
}

function scanActivityDirectory(rootDir, wantedSessionIds, activityBySessionId) {
  let entries;
  try {
    entries = fs.readdirSync(rootDir, { withFileTypes: true });
  } catch {
    return;
  }

  for (const entry of entries) {
    const entryPath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      scanActivityDirectory(entryPath, wantedSessionIds, activityBySessionId);
      continue;
    }
    if (!entry.isFile()) {
      continue;
    }

    const matchingSessionIds = sessionIdsInFilename(entry.name, wantedSessionIds);
    if (matchingSessionIds.size === 0) {
      continue;
    }

    let stat;
    try {
      stat = fs.statSync(entryPath);
    } catch {
      continue;
    }
    for (const sessionId of matchingSessionIds) {
      rememberActivity(activityBySessionId, sessionId, entryPath, stat);
    }
  }
}

function buildCodexActivityIndex(tabs = [], options = {}) {
  const wantedSessionIds = collectCodexSessionIds(tabs);
  if (wantedSessionIds.size === 0) {
    return new Map();
  }

  const activityBySessionId = new Map();
  const codexHome = resolveCodexHome(options);
  scanActivityDirectory(path.join(codexHome, "sessions"), wantedSessionIds, activityBySessionId);
  scanActivityDirectory(path.join(codexHome, "shell_snapshots"), wantedSessionIds, activityBySessionId);
  return activityBySessionId;
}

function buildRankedTabs(tabs = [], options = {}) {
  const activityBySessionId = buildCodexActivityIndex(tabs, options);
  return tabs.map((tab, originalIndex) => {
    const sessionActivity =
      tab.resumeTool === "codex" && tab.sessionId ? activityBySessionId.get(String(tab.sessionId).toLowerCase()) : null;
    return {
      tab,
      originalIndex,
      activityMs: sessionActivity?.mtimeMs || 0,
    };
  });
}

function orderTabsByRecentActivity(tabs = [], options = {}) {
  const rankedTabs = buildRankedTabs(tabs, options);
  const projects = new Map();

  for (const ranked of rankedTabs) {
    const projectPath = ranked.tab.path;
    if (!projects.has(projectPath)) {
      projects.set(projectPath, {
        projectPath,
        firstIndex: ranked.originalIndex,
        activityMs: ranked.activityMs,
        tabs: [],
      });
    }

    const project = projects.get(projectPath);
    project.firstIndex = Math.min(project.firstIndex, ranked.originalIndex);
    project.activityMs = Math.max(project.activityMs, ranked.activityMs);
    project.tabs.push(ranked);
  }

  return [...projects.values()]
    .sort(
      (left, right) =>
        right.activityMs - left.activityMs ||
        left.firstIndex - right.firstIndex,
    )
    .flatMap((project) =>
      project.tabs
        .sort((left, right) => right.activityMs - left.activityMs || left.originalIndex - right.originalIndex)
        .map((ranked) => ranked.tab),
    );
}

export function parseWorkspaceTabsArgs(argv = []) {
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
      if (arg === "--notes-file") {
        options.notesFile = next;
      } else if (arg === "--hosted-workspace-id") {
        options.hostedWorkspaceId = next;
      } else if (arg === "--workspace-file") {
        options.workspaceFile = next;
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

export function buildWorkspaceTabsReport(source, parsed, options = {}) {
  const launchTabs = buildLaunchPlan(parsed.entries, {
    tmux: false,
    resume: true,
  });
  const orderedLaunchTabs = orderTabsByRecentActivity(launchTabs, options);
  const projectGroups = buildWorkspaceProjectGroups(orderedLaunchTabs);

  return {
    sourceType: source.sourceType,
    sourceLabel: source.sourceLabel,
    title: parsed.manifest?.title || source.title,
    workspaceId: deriveWorkspaceId(source, parsed),
    machine: parsed.manifest?.machine || null,
    parseMode: parsed.parseMode,
    tabCount: orderedLaunchTabs.length,
    projectCount: projectGroups.length,
    skippedCount: parsed.skipped.length,
    projects: projectGroups.map((project) => ({
      ...project,
      sessions: project.sessions.map((session) => ({
        ...session,
        restartCommand: buildDirectCommand(
          {
            path: project.path,
            resumeCommand: session.resumeCommand || null,
            resumeTool: session.resumeTool || null,
            resumeSessionId: session.resumeSessionId || null,
            sessionId: session.resumeSessionId || null,
          },
          { resume: true },
        ),
      })),
    })),
    tabs: orderedLaunchTabs.map((tab, index) => ({
      index: index + 1,
      title: tab.title,
      path: tab.path,
      remoteUrl: tab.remoteUrl || null,
      remoteBranch: tab.remoteBranch || null,
      bootstrapCommand: tab.bootstrapCommand || null,
      resumeCommand: getResumeCommand(tab),
      restartCommand: buildDirectCommand(
        {
          path: tab.path,
          remoteUrl: tab.remoteUrl || null,
          remoteBranch: tab.remoteBranch || null,
          bootstrapCommand: tab.bootstrapCommand || null,
          resumeCommand: tab.resumeCommand || null,
          resumeTool: tab.resumeTool || null,
          resumeSessionId: tab.sessionId || null,
          sessionId: tab.sessionId || null,
        },
        { resume: true },
      ),
      cloneCommand: buildCloneCommand(tab),
      setupCommand: buildSetupCommand(tab),
      resumeTool: tab.resumeTool || null,
      resumeSessionId: tab.sessionId || null,
      codexSessionId: tab.resumeTool === "codex" ? tab.sessionId || null : null,
      claudeSessionId: tab.resumeTool === "claude" ? tab.sessionId || null : null,
    })),
    skipped: parsed.skipped,
  };
}

export function summarizeWorkspaceTabs(report) {
  const lines = [
    `Source: ${report.sourceLabel}`,
    `Workspace ID: ${report.workspaceId}`,
    ...(report.machine?.machineLabel
      ? [
          `Machine: ${report.machine.machineLabel}${
            report.machine.platform ? ` (${report.machine.platform})` : ""
          }${report.machine.machineId ? ` [${report.machine.machineId}]` : ""}`,
        ]
      : []),
    `Saved projects: ${report.projectCount}`,
    `Saved tabs: ${report.tabCount}`,
    `Parse mode: ${report.parseMode}`,
    "",
  ];

  for (const tab of report.tabs) {
    lines.push(`${String(tab.index).padStart(2, "0")}. ${tab.title}`);
    lines.push(`    path: ${tab.path}`);
    if (tab.remoteUrl) {
      lines.push(`    remote: ${tab.remoteUrl}${tab.remoteBranch ? ` [branch ${tab.remoteBranch}]` : ""}`);
    }
    if (tab.cloneCommand) {
      lines.push(`    clone: ${tab.cloneCommand}`);
    }
    if (tab.bootstrapCommand) {
      lines.push(`    bootstrap: ${tab.bootstrapCommand}`);
    }
    if (tab.setupCommand) {
      lines.push(`    setup: ${tab.setupCommand}`);
    }
    if (tab.resumeCommand) {
      lines.push(`    resume: ${tab.restartCommand}`);
    }
  }

  if (report.skipped.length > 0) {
    lines.push("");
    lines.push("Skipped lines:");
    for (const skipped of report.skipped) {
      lines.push(`  line ${skipped.lineNumber}: ${skipped.rawLine}`);
    }
  }

  return lines.join("\n");
}

function printWorkspaceTabsHelp() {
  console.log(`ORP workspace tabs

Usage:
  orp workspace tabs <name-or-id> [--json]
  orp workspace tabs --hosted-workspace-id <workspace-id> [--json]
  orp workspace tabs --notes-file <path> [--json]
  orp workspace tabs --workspace-file <path> [--json]

Options:
  --json                  Print saved tab metadata as JSON
  --hosted-workspace-id <id> Read a first-class hosted workspace instead of an idea
  --notes-file <path>     Read a local notes file instead of ORP
  --workspace-file <path> Read a structured workspace manifest JSON file
  --base-url <url>        Override the ORP hosted base URL
  --orp-command <cmd>     Override the ORP CLI executable used for hosted fetches
  -h, --help              Show this help text

Notes:
  - This shows activity-ranked saved tabs plus any stored local path, remote repo, bootstrap command, and \`codex resume ...\` / \`claude --resume ...\` metadata.
  - Codex-backed tabs are ranked by the latest matching local session or shell snapshot activity; ties keep the saved ledger order.
  - JSON output includes grouped \`projects[].sessions[]\` so duplicate project paths can be reviewed and sunset together.
  - The human-readable \`resume:\` line is already copyable and includes the saved \`cd ... && resume ...\` recovery command.
  - When a tab also has \`remote:\` or \`setup:\` lines, those are the portable cross-machine clues for cloning and preparing the repo on another rig.
  - The selector can be \`main\`, \`offhand\`, a hosted idea id, a hosted workspace id, a local workspace id, or a saved workspace title/slug.
`);
}

export async function runWorkspaceTabs(argv = process.argv.slice(2)) {
  const options = parseWorkspaceTabsArgs(argv);
  if (options.help) {
    printWorkspaceTabsHelp();
    return 0;
  }

  const source = await loadWorkspaceSource(options);
  const parsed = parseWorkspaceSource(source);
  const report = buildWorkspaceTabsReport(source, parsed, options);

  if (report.tabCount === 0) {
    throw new Error("No saved tabs were found in the provided workspace source.");
  }

  if (options.json) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    return 0;
  }

  process.stdout.write(`${summarizeWorkspaceTabs(report)}\n`);
  return 0;
}
