import process from "node:process";

import { buildWorkspaceInventory, applyWorkspaceSlotsToInventory } from "./list.js";
import { buildWorkspaceSlotAssignment, fetchHostedWorkspacesPayload, fetchIdeasPayload, resolveWorkspaceSelectorFromCollections } from "./orp.js";
import { clearWorkspaceSlot, listTrackedWorkspaces, loadWorkspaceSlots, normalizeWorkspaceSlotName, setWorkspaceSlot } from "./registry.js";

function normalizeOptionalString(value) {
  if (value == null) {
    return null;
  }
  const trimmed = String(value).trim();
  return trimmed.length > 0 ? trimmed : null;
}

function printWorkspaceSlotHelp() {
  console.log(`ORP workspace slot

Usage:
  orp workspace slot list [--json]
  orp workspace slot set <main|offhand> <name-or-id> [--json]
  orp workspace slot clear <main|offhand> [--json]

Examples:
  orp workspace slot list
  orp workspace slot set main main-cody-1
  orp workspace slot set offhand research-lab
  orp workspace slot clear offhand
`);
}

function parseWorkspaceSlotArgs(argv = []) {
  const options = {
    json: false,
  };

  const positionals = [];
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
    positionals.push(arg);
  }

  options.subcommand = positionals[0] || null;
  options.slotName = positionals[1] || null;
  options.selector = positionals[2] || null;
  if (positionals.length > 3) {
    throw new Error(`unexpected argument: ${positionals[3]}`);
  }
  return options;
}

function summarizeSlotInventory(payload) {
  const lines = ["Workspace slots"];
  for (const slotName of ["main", "offhand"]) {
    const slot = payload?.slots?.[slotName] || null;
    if (!slot) {
      lines.push(`${slotName}: unset`);
      continue;
    }
    const label = normalizeOptionalString(slot.title) || normalizeOptionalString(slot.workspaceId) || normalizeOptionalString(slot.selector) || "unknown";
    const extra =
      normalizeOptionalString(slot.kind) === "workspace-file"
        ? slot.manifestPath
        : normalizeOptionalString(slot.ideaId) || normalizeOptionalString(slot.hostedWorkspaceId) || normalizeOptionalString(slot.workspaceId);
    lines.push(`${slotName}: ${label}${extra ? ` [${extra}]` : ""}`);
  }
  return lines.join("\n");
}

async function buildSlotInventory(options = {}) {
  const [localResult, slotsResult] = await Promise.all([listTrackedWorkspaces(options), loadWorkspaceSlots(options)]);
  let hostedResult = { source: null, workspaces: [] };
  try {
    hostedResult = await fetchHostedWorkspacesPayload(options);
  } catch {
    hostedResult = { source: null, workspaces: [] };
  }
  return applyWorkspaceSlotsToInventory(
    buildWorkspaceInventory({
      localResult,
      hostedResult,
      hostedError: null,
    }),
    slotsResult.slots,
  );
}

async function resolveWorkspaceSelection(selector, options = {}) {
  const [ideasPayload, hostedResult, localRegistry] = await Promise.all([
    fetchIdeasPayload(options).catch(() => ({ ideas: [] })),
    fetchHostedWorkspacesPayload(options).catch(() => ({ workspaces: [] })),
    listTrackedWorkspaces(options).catch(() => ({ workspaces: [] })),
  ]);
  return resolveWorkspaceSelectorFromCollections(selector, {
    ideas: ideasPayload.ideas,
    hostedWorkspaces: hostedResult.workspaces,
    localWorkspaces: localRegistry.workspaces,
  });
}

export async function runWorkspaceSlot(argv = process.argv.slice(2)) {
  const options = parseWorkspaceSlotArgs(argv);
  if (options.help || !options.subcommand) {
    printWorkspaceSlotHelp();
    return 0;
  }

  if (options.subcommand === "list") {
    const inventory = await buildSlotInventory(options);
    const payload = {
      ok: true,
      slots: inventory.slots || {},
      workspaces: inventory.workspaces.filter((workspace) => Array.isArray(workspace.slots) && workspace.slots.length > 0),
    };
    if (options.json) {
      process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
      return 0;
    }
    process.stdout.write(`${summarizeSlotInventory(payload)}\n`);
    return 0;
  }

  const slotName = normalizeWorkspaceSlotName(options.slotName);
  if (!slotName) {
    throw new Error("Provide a supported slot name: main or offhand.");
  }

  if (options.subcommand === "clear") {
    const result = await clearWorkspaceSlot(slotName, options);
    const payload = {
      ok: true,
      slotName,
      cleared: result.cleared,
      slotsPath: result.slotsPath,
    };
    if (options.json) {
      process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
      return 0;
    }
    process.stdout.write(
      `${result.cleared ? "Cleared" : "Left unchanged"} workspace slot '${slotName}'.\n`,
    );
    return 0;
  }

  if (options.subcommand === "set") {
    const selector = normalizeOptionalString(options.selector);
    if (!selector) {
      throw new Error(`Provide a workspace name or id to assign to '${slotName}'.`);
    }
    if (normalizeWorkspaceSlotName(selector)) {
      throw new Error(`Use a real workspace title or id when assigning '${slotName}', not another slot name.`);
    }

    const candidate = await resolveWorkspaceSelection(selector, options);
    if (!candidate) {
      throw new Error(`Workspace not found: ${selector}`);
    }
    const assignment = buildWorkspaceSlotAssignment(candidate);
    const result = await setWorkspaceSlot(slotName, assignment, options);
    const payload = {
      ok: true,
      slotName,
      slot: result.slot,
      slotsPath: result.slotsPath,
    };
    if (options.json) {
      process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
      return 0;
    }
    const label =
      normalizeOptionalString(result.slot.title) ||
      normalizeOptionalString(result.slot.workspaceId) ||
      normalizeOptionalString(result.slot.selector) ||
      "workspace";
    process.stdout.write(`Assigned workspace slot '${slotName}' to '${label}'.\n`);
    return 0;
  }

  throw new Error(`unknown workspace slot subcommand: ${options.subcommand}`);
}
