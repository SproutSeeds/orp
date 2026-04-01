import process from "node:process";

import {
  buildWorkspaceTabsReport,
  parseWorkspaceTabsArgs,
  summarizeWorkspaceTabs,
} from "./tabs.js";
import { loadWorkspaceSource } from "./orp.js";
import { parseWorkspaceSource } from "./core-plan.js";

export function parseWorkspaceCommandsArgs(argv = []) {
  return parseWorkspaceTabsArgs(argv);
}

export function buildWorkspaceCommandsReport(source, parsed, options = {}) {
  const report = buildWorkspaceTabsReport(source, parsed, options);
  return {
    ...report,
    commandCount: report.tabCount,
  };
}

export function summarizeWorkspaceCommands(report) {
  return summarizeWorkspaceTabs({
    ...report,
    tabCount: report.commandCount ?? report.tabCount,
  });
}

function printWorkspaceCommandsHelp() {
  console.log(`ORP workspace commands

Usage:
  orp workspace commands <name-or-id> [--json]
  orp workspace commands --hosted-workspace-id <workspace-id> [--json]
  orp workspace commands --notes-file <path> [--json]
  orp workspace commands --workspace-file <path> [--json]

Options:
  --json                  Print saved recovery commands as JSON
  --hosted-workspace-id <id> Read a first-class hosted workspace instead of an idea
  --notes-file <path>     Read a local notes file instead of ORP
  --workspace-file <path> Read a structured workspace manifest JSON file
  --base-url <url>        Override the ORP hosted base URL
  --orp-command <cmd>     Override the ORP CLI executable used for hosted fetches
  -h, --help              Show this help text

Notes:
  - This is now a compatibility alias for \`orp workspace tabs ...\`.
  - Use \`orp workspace tabs ...\` as the main read command for saved paths plus copyable resume lines.
  - The selector can be \`main\`, \`offhand\`, a hosted idea id, a hosted workspace id, a local workspace id, or a saved workspace title/slug.
`);
}

export async function runWorkspaceCommands(argv = process.argv.slice(2)) {
  const options = parseWorkspaceCommandsArgs(argv);
  if (options.help) {
    printWorkspaceCommandsHelp();
    return 0;
  }

  const source = await loadWorkspaceSource(options);
  const parsed = parseWorkspaceSource(source);
  const report = buildWorkspaceCommandsReport(source, parsed, options);

  if (report.commandCount === 0) {
    throw new Error("No saved workspace commands were found in the provided workspace source.");
  }

  if (options.json) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    return 0;
  }

  process.stdout.write(`${summarizeWorkspaceCommands(report)}\n`);
  return 0;
}
