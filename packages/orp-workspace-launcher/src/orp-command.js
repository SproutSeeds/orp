import { runWorkspaceAddTab, runWorkspaceCreate, runWorkspaceRemoveTab } from "./ledger.js";
import { runWorkspaceList } from "./list.js";
import { runWorkspaceSlot } from "./slot.js";
import { runWorkspaceSync } from "./sync.js";
import { runWorkspaceTabs } from "./tabs.js";

function printWorkspaceHelp() {
  console.log(`ORP workspace

Usage:
  orp workspace create <title-slug> [--workspace-file <path>] [--slot <main|offhand>] [--machine-id <id>] [--machine-label <label>] [--platform <platform>] [--path <absolute-path>] [--remote-url <git-url>] [--remote-branch <branch>] [--bootstrap-command <text>] [--resume-command <text> | --resume-tool <codex|claude> --resume-session-id <id>] [--json]
  orp workspace list [--json]
  orp workspace tabs <name-or-id> [--json]
  orp workspace tabs --hosted-workspace-id <workspace-id> [--json]
  orp workspace tabs --notes-file <path> [--json]
  orp workspace tabs --workspace-file <path> [--json]
  orp workspace add-tab <name-or-id> (--path <absolute-path> | --here) [--title <title>] [--remote-url <git-url>] [--remote-branch <branch>] [--bootstrap-command <text>] [--resume-command <text> | --resume-tool <codex|claude> --resume-session-id <id> | --current-codex] [--append] [--json]
  orp workspace remove-tab <name-or-id> (--index <n> | --path <absolute-path> | --title <title> | --resume-session-id <id> | --resume-command <text>) [--all] [--json]
  orp workspace slot <list|set|clear> ...
  orp workspace sync <name-or-id> [--workspace-file <path> | --notes-file <path>] [--dry-run] [--json]
  orp workspace ledger <name-or-id> [--json]
  orp workspace ledger add <name-or-id> (--path <absolute-path> | --here) [--title <title>] [--remote-url <git-url>] [--remote-branch <branch>] [--bootstrap-command <text>] [--resume-command <text> | --resume-tool <codex|claude> --resume-session-id <id> | --current-codex] [--append] [--json]
  orp workspace ledger remove <name-or-id> (--index <n> | --path <absolute-path> | --title <title> | --resume-session-id <id> | --resume-command <text>) [--all] [--json]
  orp workspace -h

Commands:
  create  Create a local workspace ledger so ORP works without a hosted account
  list    List one merged inventory of hosted ORP workspaces and local manifests
  tabs    List the saved tabs inside a workspace with copyable resume/recovery lines
  add-tab Add a saved tab/path/session to the workspace ledger directly
  remove-tab Remove one or more saved tabs from the workspace ledger directly
  slot    Assign and inspect named workspace slots like main and offhand
  sync    Post a CLI-authored workspace manifest back to the hosted ORP idea
  ledger  Compatibility alias for the same tabs/add/remove ledger flow

Notes:
  - Local-only usage works: create a workspace with \`orp workspace create <title-slug>\`, then use \`orp workspace tabs ...\`, \`orp workspace add-tab ...\`, and \`orp workspace remove-tab ...\` without authenticating.
  - Use \`orp workspace list\` for the combined hosted + local workspace inventory.
  - Use \`orp workspace tabs <workspace>\` when you want saved paths plus copyable \`cd ... && codex resume ...\` / \`claude --resume ...\` recovery lines, along with optional remote repo and bootstrap metadata for another machine.
  - Use \`orp workspace create ... --machine-label ...\` when you want the workspace ledger to stay clearly tied to one rig.
  - Use \`orp workspace add-tab ... --remote-url ... --bootstrap-command ...\` when you want ORP to remember how to recreate the repo on another machine.
  - Use \`orp workspace add-tab ...\` and \`orp workspace remove-tab ...\` when you want to edit the saved workspace ledger explicitly from Terminal.app or any other shell.
  - If you prefer the older ledger-prefixed wording, \`orp workspace ledger\`, \`orp workspace ledger add\`, and \`orp workspace ledger remove\` stay available as aliases.
  - \`main\` and \`offhand\` are reserved slot selectors; use \`orp workspace slot set ...\` to assign them.
  - Syncing or editing a hosted workspace writes a managed local cache on this Mac.
  - \`<name-or-id>\` can be a saved workspace title, workspace id, idea id, or local tracked workspace title/id.

Examples:
  orp workspace create main-cody-1
  orp workspace create main-cody-1 --slot main
  orp workspace create mac-main --machine-label "Mac Studio" --path /absolute/path/to/orp --remote-url git@github.com:SproutSeeds/orp.git --bootstrap-command "npm install"
  orp workspace list
  orp workspace tabs main-cody-1
  orp workspace add-tab main --here --current-codex
  orp workspace add-tab main --path /absolute/path/to/new-project --resume-command "codex resume 019d..."
  orp workspace add-tab main --path /absolute/path/to/new-project --remote-url git@github.com:org/new-project.git --bootstrap-command "npm install"
  orp workspace remove-tab main --path /absolute/path/to/frg-site --resume-session-id 019d348d-5031-78e1-9840-a66deaac33ae
  orp workspace slot set main main-cody-1
  orp workspace slot set offhand research-lab
  orp workspace slot list
  orp workspace ledger main
  orp workspace ledger add main --path /absolute/path/to/new-project --resume-command "codex resume 019d..."
  orp workspace ledger remove main --title frg-site
  orp workspace tabs --hosted-workspace-id ws_orp_main
  orp workspace sync main --workspace-file ./workspace.json
`);
}

export async function runOrpWorkspaceCommand(argv = []) {
  const [subcommand, ...rest] = argv;

  if (!subcommand || subcommand === "-h" || subcommand === "--help" || subcommand === "help") {
    printWorkspaceHelp();
    return 0;
  }

  if (subcommand === "ledger") {
    const [ledgerSubcommand, ...ledgerRest] = rest;
    if (!ledgerSubcommand || ledgerSubcommand === "show") {
      return runWorkspaceTabs(ledgerRest);
    }
    if (ledgerSubcommand === "-h" || ledgerSubcommand === "--help") {
      return runWorkspaceTabs(["-h"]);
    }
    if (ledgerSubcommand === "add") {
      return runWorkspaceAddTab(ledgerRest);
    }
    if (ledgerSubcommand === "remove") {
      return runWorkspaceRemoveTab(ledgerRest);
    }
    if (ledgerSubcommand === "commands") {
      return runWorkspaceTabs(ledgerRest);
    }
    return runWorkspaceTabs(rest);
  }

  if (subcommand === "create") {
    return runWorkspaceCreate(rest);
  }

  if (subcommand === "tabs") {
    return runWorkspaceTabs(rest);
  }

  if (subcommand === "commands") {
    return runWorkspaceTabs(rest);
  }

  if (subcommand === "add-tab") {
    return runWorkspaceAddTab(rest);
  }

  if (subcommand === "remove-tab") {
    return runWorkspaceRemoveTab(rest);
  }

  if (subcommand === "list") {
    return runWorkspaceList(rest);
  }

  if (subcommand === "slot") {
    return runWorkspaceSlot(rest);
  }

  if (subcommand === "sync") {
    return runWorkspaceSync(rest);
  }

  throw new Error(`unknown workspace subcommand: ${subcommand}`);
}
