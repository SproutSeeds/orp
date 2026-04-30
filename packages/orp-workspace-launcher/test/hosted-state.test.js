import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { buildHostedWorkspaceState } from "../src/index.js";

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

test("buildHostedWorkspaceState compiles local ORP frontier plan and tasks", async () => {
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
  assert.equal(state.tabs[0].plan.summary, "ORP TAS: Evidence-Backed Conditional Strategy Controls");
  assert.equal(state.tabs[0].plan.source, "orp/frontier/TAS.md");
  assert.equal(state.tabs[0].linked_idea_id, "idea-123");
  assert.equal(state.tabs[0].linked_feature_id, "feature-regime-metadata-quality");
  assert.match(state.tabs[0].plan.body, /Current next action: Implement replay metadata taxonomy/);
  assert.deepEqual(
    state.tabs[0].tasks.map((task) => [task.id, task.status]),
    [
      ["signal-quality-and-control-provenance", "done"],
      ["regime-metadata-quality", "in_progress"],
      ["first-regime-sample-capture", "todo"],
    ],
  );
  assert.equal(state.projects[0].plan.summary, "ORP TAS: Evidence-Backed Conditional Strategy Controls");
  assert.equal(state.projects[0].tasks.length, 3);
  assert.equal(state.projects[0].linked_idea_id, "idea-123");
  assert.equal(state.projects[0].linked_feature_id, "feature-regime-metadata-quality");
});
