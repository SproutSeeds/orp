import process from "node:process";

import {
  buildCloneCommand,
  buildDirectCommand,
  buildLaunchPlan,
  buildSetupCommand,
  deriveWorkspaceId,
  getResumeCommand,
  parseWorkspaceSource,
} from "./core-plan.js";
import { loadWorkspaceSource } from "./orp.js";

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

  return {
    sourceType: source.sourceType,
    sourceLabel: source.sourceLabel,
    title: parsed.manifest?.title || source.title,
    workspaceId: deriveWorkspaceId(source, parsed),
    machine: parsed.manifest?.machine || null,
    parseMode: parsed.parseMode,
    tabCount: launchTabs.length,
    skippedCount: parsed.skipped.length,
    tabs: launchTabs.map((tab, index) => ({
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
  - This shows the saved tab order plus any stored local path, remote repo, bootstrap command, and \`codex resume ...\` / \`claude --resume ...\` metadata.
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
