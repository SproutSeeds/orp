import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { buildHostedWorkspaceState, normalizeHostedRemoteUrl } from "../src/index.js";

async function makeFrontierProject() {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "orp-hosted-state-frontier-"));
  const frontierRoot = path.join(root, "orp", "frontier");
  const linkRoot = path.join(root, ".git", "orp", "link");
  await fs.mkdir(frontierRoot, { recursive: true });
  await fs.mkdir(linkRoot, { recursive: true });
  await fs.writeFile(
    path.join(frontierRoot, "TAS.md"),
    [
      "# ORP TAS: Evidence-Backed Conditional Strategy Controls",
      "",
      "## Active Task Order",
      "",
      "1. Define a small replay metadata taxonomy for semantic regimes.",
      "2. Add a metadata-quality gate.",
    ].join("\n"),
    "utf8",
  );
  await fs.writeFile(
    path.join(frontierRoot, "state.json"),
    JSON.stringify(
      {
        active_version: "v0",
        active_milestone: "v0.2",
        active_phase: "regime-metadata-quality",
        next_action: "Implement replay metadata taxonomy and metadata-quality gates.",
      },
      null,
      2,
    ),
    "utf8",
  );
  await fs.writeFile(
    path.join(frontierRoot, "version-stack.json"),
    JSON.stringify(
      {
        versions: [
          {
            id: "v0",
            label: "Dry-run Topstep 50K lab",
            milestones: [
              {
                id: "v0.2",
                label: "Evidence-backed conditional strategy controls",
                phases: [
                  {
                    id: "signal-quality-and-control-provenance",
                    label: "Signal quality and control provenance",
                    status: "completed",
                  },
                  {
                    id: "regime-metadata-quality",
                    label: "Regime metadata quality",
                    status: "active",
                  },
                  {
                    id: "first-regime-sample-capture",
                    label: "First regime sample capture",
                    status: "planned",
                  },
                ],
              },
            ],
          },
        ],
      },
      null,
      2,
    ),
    "utf8",
  );
  await fs.writeFile(
    path.join(linkRoot, "project.json"),
    JSON.stringify(
      {
        idea_id: "idea-123",
        idea_title: "Canonical futures idea",
        active_feature_id: "feature-regime-metadata-quality",
        frontier_feature_ids: {
          "regime-metadata-quality": "feature-regime-metadata-quality",
        },
        project_root: root,
      },
      null,
      2,
    ),
    "utf8",
  );
  return root;
}

test("buildHostedWorkspaceState defaults to a versioned metadata-only payload", async () => {
  const projectRoot = await makeFrontierProject();
  const state = buildHostedWorkspaceState({
    version: "1",
    workspaceId: "main-cody-1",
    title: "main-cody-1",
    tabs: [
      {
        title: "futures-prop-trading-lab",
        path: projectRoot,
        resumeTool: "codex",
        resumeSessionId: "019d4f24-c8ba-78b2-a726-48b1ce9f0fe9",
      },
    ],
  });

  assert.equal(state.tabs.length, 1);
  assert.equal(state.contract_version, "2.0.0");
  assert.deepEqual(state.sync_policy.allowlist, []);
  assert.deepEqual(Object.keys(state.tabs[0]).sort(), ["order_index", "status", "tab_id"]);
  const serialized = JSON.stringify(state);
  assert.ok(!serialized.includes(projectRoot));
  assert.ok(!serialized.includes("019d4f24-c8ba-78b2-a726-48b1ce9f0fe9"));
  assert.ok(!serialized.includes("Evidence-Backed Conditional Strategy Controls"));
  assert.ok(!serialized.includes("idea-123"));
  assert.ok(!serialized.includes("project_root"));
  assert.ok(!serialized.includes("resume_session_id"));
});

test("buildHostedWorkspaceState includes only explicitly allowlisted fields", () => {
  const state = buildHostedWorkspaceState(
    {
      version: "1",
      workspaceId: "main-cody-1",
      title: "main-cody-1",
      tabs: [
        {
          title: "tailnet-app",
          path: "/Volumes/Code_2TB/code/tailnet-app",
          resumeTool: "codex",
          resumeSessionId: "019dcd50-111d-7451-bd01-dbc21336c679",
          linkedIdeaId: "idea-tailnet",
          linkedFeatureId: "feature-tailnet",
          plan: {
            summary: "Ship Tailnet App workspace sync",
            body: "Keep the hosted workspace aligned with local project inventory.",
          },
          tasks: [
            {
              id: "sync-contract",
              title: "Define sync contract",
              status: "in_progress",
            },
          ],
          lastActivityAt: "2026-04-30T02:59:15.000Z",
          lastSyncedAt: "2026-04-30T12:00:00.000Z",
          syncSource: "orp-project-startup",
        },
      ],
    },
    {
      updatedAt: "2026-04-30T12:30:00.000Z",
      syncAllowlist: [
        "tabs.title",
        "tabs.linked_idea_id",
        "tabs.linked_feature_id",
        "tabs.activity",
        "tabs.plan_summary",
        "tabs.tasks",
      ],
      localInventory: {
        contract: {
          source_of_truth: "orp-workspace-ledger",
        },
      },
    },
  );

  assert.equal(state.tabs[0].title, "tailnet-app");
  assert.equal(state.tabs[0].plan_summary, "Ship Tailnet App workspace sync");
  assert.equal(state.tabs[0].tasks[0].id, "sync-contract");
  assert.equal(state.tabs[0].linked_idea_id, "idea-tailnet");
  assert.equal(state.tabs[0].linked_feature_id, "feature-tailnet");
  assert.equal(state.tabs[0].last_activity_at_utc, "2026-04-30T02:59:15.000Z");
  assert.equal(state.tabs[0].last_synced_at_utc, "2026-04-30T12:00:00.000Z");
  const serialized = JSON.stringify(state);
  assert.ok(!serialized.includes("/Volumes/Code_2TB/code/tailnet-app"));
  assert.ok(!serialized.includes("019dcd50-111d-7451-bd01-dbc21336c679"));
  assert.ok(!serialized.includes("Keep the hosted workspace aligned"));
  assert.ok(!serialized.includes("orp-project-startup"));
  assert.ok(!serialized.includes("source_of_truth"));
});

test("hosted remote URLs reject embedded credentials and request metadata", () => {
  assert.equal(normalizeHostedRemoteUrl("https://github.com/SproutSeeds/orp.git"), "https://github.com/SproutSeeds/orp.git");
  assert.equal(normalizeHostedRemoteUrl("git@github.com:SproutSeeds/orp.git"), "git@github.com:SproutSeeds/orp.git");
  assert.throws(
    () => normalizeHostedRemoteUrl("https://token@github.com/SproutSeeds/orp.git?access_token=secret"),
    /must not contain credentials/,
  );
});

test("hosted projection rejects sensitive content embedded in allowlisted text", () => {
  const manifest = {
    version: "1",
    workspaceId: "main",
    tabs: [{ title: "safe", path: "/tmp/safe" }],
  };
  const sensitive = [
    "Review /Volumes/Code_2TB/code/orp before release",
    "access_token=super-secret-value",
    "User: keep this private\nAssistant: understood",
    "Run codex resume 019dcd50-111d-7451-bd01-dbc21336c679",
    "hostname=codys-macbook.local",
  ];
  for (const summary of sensitive) {
    assert.throws(
      () => buildHostedWorkspaceState(manifest, { syncAllowlist: ["workspace.summary"], summary }),
      /hosted workspace metadata contains/,
    );
  }
});

test("hosted projection accepts ordinary summaries about security concepts", () => {
  const state = buildHostedWorkspaceState(
    { version: "1", workspaceId: "main", tabs: [{ title: "safe", path: "/tmp/safe" }] },
    {
      syncAllowlist: ["workspace.summary"],
      summary: "Rotate access tokens and document transcript protections.",
    },
  );
  assert.equal(state.summary, "Rotate access tokens and document transcript protections.");
});
