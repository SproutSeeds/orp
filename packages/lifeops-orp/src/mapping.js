import { collectOrpWorkspace } from "./workspace.js";

function slugify(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function pushItem(items, item) {
  if (!item) {
    return;
  }
  items.push(item);
}

function projectLabel(workspace, projectName) {
  return (
    projectName ||
    workspace.frontierState?.label ||
    workspace.frontierState?.program_id ||
    workspace.status?.repo_root?.split("/").filter(Boolean).pop() ||
    "ORP Project"
  );
}

function readinessItem(workspace, name, organization) {
  const readiness = workspace.status?.readiness ?? {};
  if (!readiness.local_ready && !readiness.remote_ready) {
    return null;
  }
  const scope = readiness.scope || "local_only";
  return {
    id: `orp-ready:${slugify(name)}`,
    kind: "alert",
    title: `${name} is ready to share`,
    summary: `ORP readiness is marked true (${scope}).`,
    priority: "high",
    organization,
    tags: ["orp", "readiness", "share"],
    source: {
      connector: "orp",
      id: "ready",
    },
    metadata: {
      readiness,
      latestRun: workspace.status?.runtime?.last_ready ?? {},
    },
  };
}

function frontierItem(workspace, name, organization) {
  const frontier = workspace.frontierState ?? {};
  if (!frontier.active_milestone && !frontier.next_action) {
    return null;
  }
  const milestone = frontier.active_milestone || frontier.active_version || "frontier";
  const title = frontier.next_action
    ? `ORP frontier: ${frontier.next_action}`
    : `Advance frontier milestone ${milestone}`;

  return {
    id: `orp-frontier:${slugify(name)}:${slugify(milestone) || "state"}`,
    kind: "task",
    title,
    summary: [
      frontier.active_version ? `version ${frontier.active_version}` : "",
      frontier.active_milestone ? `milestone ${frontier.active_milestone}` : "",
      frontier.active_phase ? `phase ${frontier.active_phase}` : "",
    ]
      .filter(Boolean)
      .join(" / "),
    priority: "high",
    organization,
    tags: ["orp", "frontier"],
    source: {
      connector: "orp",
      id: "frontier-state",
    },
    metadata: {
      frontier,
    },
  };
}

function nextActionItems(workspace, name, organization) {
  const actions = Array.isArray(workspace.status?.next_actions) ? workspace.status.next_actions : [];
  return actions.slice(0, 5).map((action, index) => ({
    id: `orp-next:${slugify(name)}:${index + 1}`,
    kind: "task",
    title: `ORP next action: ${action}`,
    summary: `Suggested by ORP status for ${name}.`,
    priority: index === 0 ? "high" : "normal",
    organization,
    tags: ["orp", "next-action"],
    source: {
      connector: "orp",
      id: `next-action-${index + 1}`,
    },
    metadata: {
      action,
    },
  }));
}

function checklistItems(workspace, name, organization) {
  const exact = Array.isArray(workspace.frontierChecklist?.exact)
    ? workspace.frontierChecklist.exact
    : [];
  return exact.slice(0, 10).map((row, index) => {
    const milestone = row.milestone_id || row.milestone || `item-${index + 1}`;
    const label = row.label || row.phase_label || row.next_action || milestone;
    return {
      id: `orp-checklist:${slugify(name)}:${slugify(milestone)}`,
      kind: "task",
      title: `ORP checklist: ${label}`,
      summary: [
        row.version_id ? `version ${row.version_id}` : "",
        row.milestone_id ? `milestone ${row.milestone_id}` : "",
        row.phase_id ? `phase ${row.phase_id}` : "",
      ]
        .filter(Boolean)
        .join(" / "),
      priority: "normal",
      organization,
      tags: ["orp", "checklist"],
      source: {
        connector: "orp",
        id: `checklist-${index + 1}`,
      },
      metadata: {
        checklistRow: row,
      },
    };
  });
}

function validationAlert(workspace, name, organization) {
  const latestRun = workspace.status?.runtime?.latest_run ?? {};
  const overall = latestRun.overall || "";
  if (!overall || overall === "PASS") {
    return null;
  }
  return {
    id: `orp-validation:${slugify(name)}`,
    kind: "alert",
    title: `${name} has a non-passing ORP validation state`,
    summary: `Latest ORP run overall status: ${overall}.`,
    priority: "urgent",
    organization,
    tags: ["orp", "validation"],
    source: {
      connector: "orp",
      id: "validation",
    },
    metadata: {
      latestRun,
    },
  };
}

export function mapOrpWorkspaceToItems({
  workspace,
  projectName,
  organization = "ORP",
} = {}) {
  if (!workspace || typeof workspace !== "object") {
    throw new Error("mapOrpWorkspaceToItems requires a workspace object.");
  }

  const name = projectLabel(workspace, projectName);
  const items = [];

  pushItem(items, readinessItem(workspace, name, organization));
  pushItem(items, frontierItem(workspace, name, organization));
  pushItem(items, validationAlert(workspace, name, organization));

  items.push(...nextActionItems(workspace, name, organization));
  items.push(...checklistItems(workspace, name, organization));

  return items;
}

export function createOrpProjectShareInput({
  workspace,
  projectName,
  summary = "",
  repoUrl = "",
  liveUrl = "",
  extraHighlights = [],
  extraProofPoints = [],
  extraCodebases = [],
} = {}) {
  if (!workspace || typeof workspace !== "object") {
    throw new Error("createOrpProjectShareInput requires a workspace object.");
  }

  const name = projectLabel(workspace, projectName);
  const readiness = workspace.status?.readiness ?? {};
  const frontier = workspace.frontierState ?? {};
  const latestRun = workspace.status?.runtime?.latest_run ?? {};

  const whyNow = readiness.local_ready || readiness.remote_ready
    ? "ORP marks this repo as ready, so this is a strong moment to share it with selected collaborators."
    : "The ORP frontier is active and concrete next actions are already defined, so this is a good moment to share progress in a structured way.";

  const highlights = [
    frontier.next_action ? `Current frontier next action: ${frontier.next_action}` : "",
    frontier.active_milestone ? `Active frontier milestone: ${frontier.active_milestone}` : "",
    Array.isArray(workspace.status?.next_actions) && workspace.status.next_actions[0]
      ? `Immediate ORP next action: ${workspace.status.next_actions[0]}`
      : "",
    ...extraHighlights,
  ].filter(Boolean);

  const proofPoints = [
    latestRun.overall ? `Latest ORP validation run: ${latestRun.overall}` : "",
    readiness.local_ready ? "Local ORP readiness is marked true." : "",
    readiness.remote_ready ? "Remote ORP readiness is marked true." : "",
    workspace.status?.validation?.checkpoint_after_validation
      ? "Checkpoint captured after validation."
      : "",
    ...extraProofPoints,
  ].filter(Boolean);

  const links = [
    repoUrl ? { label: "Repository", url: repoUrl } : null,
    liveUrl ? { label: "Live URL", url: liveUrl } : null,
  ].filter(Boolean);

  const codebases = [
    "open-research-protocol",
    ...extraCodebases,
  ].filter(Boolean);

  return {
    name,
    summary: summary || `An ORP-governed project with machine-readable frontier, readiness, and workflow state.`,
    whyNow,
    highlights,
    proofPoints,
    links,
    codebases,
  };
}

export async function buildOrpProjectSharePacket({
  repoRoot,
  buildProjectSharePacket,
  recipients,
  orpCommand = "orp",
  includeAbout = true,
  commandRunner,
  ...shareOptions
} = {}) {
  if (typeof buildProjectSharePacket !== "function") {
    throw new Error("buildOrpProjectSharePacket requires a buildProjectSharePacket function.");
  }

  const workspace = await collectOrpWorkspace({
    repoRoot,
    orpCommand,
    includeAbout,
    commandRunner,
  });

  return buildProjectSharePacket({
    project: createOrpProjectShareInput({
      workspace,
      ...shareOptions,
    }),
    recipients,
    senderName: shareOptions.senderName,
    baseTime: shareOptions.baseTime,
  });
}

export function createOrpConnector({
  repoRoot,
  orpCommand = "orp",
  name = "orp",
  projectName,
  organization = "ORP",
  includeAbout = false,
  commandRunner,
} = {}) {
  return {
    name,
    async pull() {
      const workspace = await collectOrpWorkspace({
        repoRoot,
        orpCommand,
        includeAbout,
        commandRunner,
      });
      return {
        items: mapOrpWorkspaceToItems({
          workspace,
          projectName,
          organization,
        }),
        meta: {
          workspace,
        },
      };
    },
  };
}
