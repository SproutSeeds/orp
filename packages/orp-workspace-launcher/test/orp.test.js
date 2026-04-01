import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  chooseImplicitMainCandidate,
  loadWorkspaceSource,
  resolveWorkspaceSelectorFromCollections,
  resolveWorkspaceWatchTargets,
} from "../src/orp.js";
import { setWorkspaceSlot } from "../src/registry.js";

async function makeTempDir() {
  return fs.mkdtemp(path.join(os.tmpdir(), "orp-workspace-selector-"));
}

test("resolveWorkspaceSelectorFromCollections matches hosted ideas by saved workspace id and title slug", () => {
  const ideas = [
    {
      id: "ef86bd4c-35b0-454c-ac90-9136a006b0af",
      title: "Terminal paths and codex sessions 03-26-2026",
      notes: `
\`\`\`orp-workspace
{
  "version": "1",
  "workspaceId": "workspace-main-1",
  "title": "Main Cody 1",
  "tabs": [
    { "title": "orp", "path": "/Volumes/Code_2TB/code/orp" }
  ]
}
\`\`\`
`,
    },
  ];

  const byWorkspaceId = resolveWorkspaceSelectorFromCollections("workspace-main-1", { ideas });
  assert.equal(byWorkspaceId?.kind, "hosted-idea");
  assert.equal(byWorkspaceId?.idea?.id, "ef86bd4c-35b0-454c-ac90-9136a006b0af");

  const byTitleSlug = resolveWorkspaceSelectorFromCollections("main-cody-1", { ideas });
  assert.equal(byTitleSlug?.title, "Main Cody 1");
});

test("resolveWorkspaceSelectorFromCollections can match local tracked workspaces by title", () => {
  const resolved = resolveWorkspaceSelectorFromCollections("ORP Main", {
    localWorkspaces: [
      {
        manifestPath: "/tmp/orp-main.json",
        workspaceId: "orp-main",
        title: "ORP Main",
        status: "ok",
      },
    ],
  });

  assert.equal(resolved?.kind, "workspace-file");
  assert.equal(resolved?.manifestPath, "/tmp/orp-main.json");
});

test("resolveWorkspaceSelectorFromCollections prefers hosted saved workspaces over local duplicates", () => {
  const ideas = [
    {
      id: "idea-main",
      title: "ORP Main",
      notes: `
\`\`\`orp-workspace
{
  "version": "1",
  "workspaceId": "orp-main",
  "title": "ORP Main",
  "tabs": [
    { "path": "/Volumes/Code_2TB/code/orp" }
  ]
}
\`\`\`
`,
    },
  ];
  const localWorkspaces = [
    {
      manifestPath: "/tmp/orp-main.json",
      workspaceId: "orp-main",
      title: "ORP Main",
      status: "ok",
    },
  ];

  const resolved = resolveWorkspaceSelectorFromCollections("orp-main", {
    ideas,
    localWorkspaces,
  });

  assert.equal(resolved?.kind, "hosted-idea");
  assert.equal(resolved?.idea?.id, "idea-main");
});

test("resolveWorkspaceSelectorFromCollections raises on ambiguous hosted titles", () => {
  const ideas = [
    {
      id: "idea-1",
      title: "Main Cody 1",
      notes: `
/Volumes/Code_2TB/code/orp
`,
    },
    {
      id: "idea-2",
      title: "Main Cody 1",
      notes: `
/Volumes/Code_2TB/code/orp-web-app
`,
    },
  ];

  assert.throws(
    () => resolveWorkspaceSelectorFromCollections("Main Cody 1", { ideas }),
    /ambiguous/i,
  );
});

test("loadWorkspaceSource resolves the main slot to an explicit local manifest", async () => {
  const tempDir = await makeTempDir();
  const env = {
    ...process.env,
    XDG_CONFIG_HOME: path.join(tempDir, "config"),
  };
  const manifestPath = path.join(tempDir, "main-cody-1.json");
  await fs.writeFile(
    manifestPath,
    `${JSON.stringify(
      {
        version: "1",
        workspaceId: "main-cody-1",
        title: "main-cody-1",
        tabs: [{ path: "/Volumes/Code_2TB/code/orp" }],
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
  await setWorkspaceSlot(
    "main",
    {
      kind: "workspace-file",
      workspaceId: "main-cody-1",
      title: "main-cody-1",
      manifestPath,
    },
    { env },
  );

  const source = await loadWorkspaceSource({
    ideaId: "main",
    env,
  });

  assert.equal(source.sourceType, "workspace-file");
  assert.equal(source.sourcePath, path.resolve(manifestPath));
  assert.equal(source.workspaceManifest?.workspaceId, "main-cody-1");
});

test("chooseImplicitMainCandidate prefers the single hosted-backed workspace over generated local captures", () => {
  const candidate = chooseImplicitMainCandidate([
    {
      kind: "hosted-idea",
      workspaceId: "idea-ef86bd4c-35b0-454c-ac90-9136a006b0af",
      title: "Terminal paths and codex sessions 03-26-2026",
    },
    {
      kind: "workspace-file",
      workspaceId: "captured-iterm-window-20260401t032225z",
      title: "captured-iterm-window-20260401t032225z",
      manifestPath: "/tmp/captured-1.json",
    },
    {
      kind: "workspace-file",
      workspaceId: "captured-iterm-window-20260401t032215z",
      title: "captured-iterm-window-20260401t032215z",
      manifestPath: "/tmp/captured-2.json",
    },
  ]);

  assert.equal(candidate?.kind, "hosted-idea");
  assert.equal(candidate?.workspaceId, "idea-ef86bd4c-35b0-454c-ac90-9136a006b0af");
});

test("resolveWorkspaceWatchTargets syncs idea-bridge hosted workspaces through the linked idea", () => {
  const targets = resolveWorkspaceWatchTargets(
    {
      sourceType: "hosted-workspace",
      hostedWorkspace: {
        workspace_id: "idea-ef86bd4c-35b0-454c-ac90-9136a006b0af",
        source_kind: "idea_bridge",
        linkedIdea: {
          ideaId: "ef86bd4c-35b0-454c-ac90-9136a006b0af",
        },
      },
    },
    {},
  );

  assert.equal(targets.hostedWorkspaceId, null);
  assert.equal(targets.syncIdeaSelector, "ef86bd4c-35b0-454c-ac90-9136a006b0af");
});

test("resolveWorkspaceWatchTargets preserves true hosted workspace ids", () => {
  const targets = resolveWorkspaceWatchTargets(
    {
      sourceType: "hosted-workspace",
      hostedWorkspace: {
        workspace_id: "ws_orp_main",
        source_kind: "hosted",
      },
    },
    {},
  );

  assert.equal(targets.hostedWorkspaceId, "ws_orp_main");
  assert.equal(targets.syncIdeaSelector, null);
});
