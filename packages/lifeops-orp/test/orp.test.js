import test from "node:test";
import assert from "node:assert/strict";

import {
  buildOrpProjectSharePacket,
  collectOrpWorkspace,
  createOrpConnector,
  createOrpProjectShareInput,
  mapOrpWorkspaceToItems,
} from "../src/index.js";

function createWorkspace() {
  return {
    repoRoot: "/tmp/demo-repo",
    collectedAt: "2026-03-26T00:00:00.000Z",
    status: {
      next_actions: [
        "orp checkpoint create -m \"capture passing validation\" --json",
        "orp ready --json",
      ],
      readiness: {
        scope: "local_only",
        local_ready: true,
        remote_ready: false,
      },
      runtime: {
        latest_run: {
          overall: "PASS",
        },
        last_ready: {
          run_id: "run-123",
        },
      },
      validation: {
        checkpoint_after_validation: true,
      },
    },
    frontierState: {
      program_id: "lifeops",
      label: "Life Ops",
      active_version: "v1",
      active_milestone: "v1.2",
      active_phase: "395",
      next_action: "execute phase 395",
    },
    frontierRoadmap: {
      active_milestone: "v1.2",
    },
    frontierChecklist: {
      exact: [
        {
          version_id: "v1",
          milestone_id: "v1.2",
          phase_id: "395",
          label: "Execute phase 395",
        },
      ],
    },
    about: {
      tool: {
        name: "orp",
      },
    },
  };
}

test("collectOrpWorkspace gathers core ORP json surfaces", async () => {
  const calls = [];
  const workspace = await collectOrpWorkspace({
    repoRoot: "/tmp/demo-repo",
    commandRunner: async ({ args }) => {
      calls.push(args.join(" "));
      const [first, second] = args;
      if (first === "status") {
        return createWorkspace().status;
      }
      if (first === "frontier" && second === "state") {
        return createWorkspace().frontierState;
      }
      if (first === "frontier" && second === "roadmap") {
        return createWorkspace().frontierRoadmap;
      }
      if (first === "frontier" && second === "checklist") {
        return createWorkspace().frontierChecklist;
      }
      if (first === "about") {
        return createWorkspace().about;
      }
      throw new Error(`unexpected args: ${args.join(" ")}`);
    },
  });

  assert.equal(calls[0], "status");
  assert.equal(workspace.frontierState.active_milestone, "v1.2");
  assert.equal(workspace.about.tool.name, "orp");
});

test("mapOrpWorkspaceToItems creates readiness, frontier, and checklist items", () => {
  const items = mapOrpWorkspaceToItems({
    workspace: createWorkspace(),
    projectName: "Life Ops Research",
    organization: "ORP",
  });

  assert.ok(items.some((item) => item.title === "Life Ops Research is ready to share"));
  assert.ok(items.some((item) => item.title.includes("ORP frontier: execute phase 395")));
  assert.ok(items.some((item) => item.title.includes("ORP checklist: Execute phase 395")));
});

test("createOrpProjectShareInput derives share context from ORP workspace", () => {
  const shareInput = createOrpProjectShareInput({
    workspace: createWorkspace(),
    projectName: "Life Ops Research",
    repoUrl: "https://github.com/example/repo",
  });

  assert.equal(shareInput.name, "Life Ops Research");
  assert.match(shareInput.whyNow, /ready/i);
  assert.ok(shareInput.highlights.some((line) => line.includes("execute phase 395")));
  assert.ok(shareInput.proofPoints.some((line) => line.includes("PASS")));
});

test("buildOrpProjectSharePacket delegates to injected Life Ops share builder", async () => {
  let captured = null;
  const result = await buildOrpProjectSharePacket({
    repoRoot: "/tmp/demo-repo",
    projectName: "Life Ops Research",
    recipients: [{ email: "alicia@example.com" }],
    buildProjectSharePacket(input) {
      captured = input;
      return { ok: true, input };
    },
    orpCommand: "orp",
    includeAbout: false,
    commandRunner: async ({ args }) => {
      const [first, second] = args;
      if (first === "status") {
        return createWorkspace().status;
      }
      if (first === "frontier" && second === "state") {
        return createWorkspace().frontierState;
      }
      if (first === "frontier" && second === "roadmap") {
        return createWorkspace().frontierRoadmap;
      }
      if (first === "frontier" && second === "checklist") {
        return createWorkspace().frontierChecklist;
      }
      throw new Error(`unexpected args: ${args.join(" ")}`);
    },
    extraHighlights: ["Agent-first workflow"],
    extraCodebases: ["@lifeops/core"],
  });

  assert.equal(result.ok, true);
  assert.equal(captured.project.name, "Life Ops Research");
  assert.ok(captured.project.codebases.includes("@lifeops/core"));
});

test("createOrpConnector exposes a Life Ops-compatible pull contract", async () => {
  const connector = createOrpConnector({
    repoRoot: "/tmp/demo-repo",
    projectName: "Life Ops Research",
    includeAbout: false,
    commandRunner: async ({ args }) => {
      const [first, second] = args;
      if (first === "status") {
        return createWorkspace().status;
      }
      if (first === "frontier" && second === "state") {
        return createWorkspace().frontierState;
      }
      if (first === "frontier" && second === "roadmap") {
        return createWorkspace().frontierRoadmap;
      }
      if (first === "frontier" && second === "checklist") {
        return createWorkspace().frontierChecklist;
      }
      throw new Error(`unexpected args: ${args.join(" ")}`);
    },
  });

  const payload = await connector.pull();
  assert.ok(Array.isArray(payload.items));
  assert.ok(payload.items.length >= 3);
  assert.equal(payload.meta.workspace.repoRoot, "/tmp/demo-repo");
});
