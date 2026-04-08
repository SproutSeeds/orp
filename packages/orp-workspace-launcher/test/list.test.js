import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  applyWorkspaceSlotsToInventory,
  buildWorkspaceInventory,
  cacheManagedWorkspaceManifest,
  getManagedWorkspaceDir,
  listTrackedWorkspaces,
  loadWorkspaceSlots,
  parseWorkspaceListArgs,
  registerWorkspaceManifest,
  setWorkspaceSlot,
  summarizeTrackedWorkspaces,
  summarizeWorkspaceInventory,
} from "../src/index.js";

async function makeTempDir() {
  return fs.mkdtemp(path.join(os.tmpdir(), "orp-workspace-list-"));
}

test("parseWorkspaceListArgs accepts --json", () => {
  const parsed = parseWorkspaceListArgs(["--json"]);
  assert.equal(parsed.json, true);
  assert.throws(() => parseWorkspaceListArgs(["--wat"]), /unexpected argument/);
});

test("registerWorkspaceManifest and listTrackedWorkspaces expose tracked saved resume commands", async () => {
  const tempDir = await makeTempDir();
  const env = {
    ...process.env,
    XDG_CONFIG_HOME: path.join(tempDir, "config"),
  };
  const manifestPath = path.join(tempDir, "workspace.json");
  const manifest = {
    version: "1",
    workspaceId: "orp-main",
    title: "ORP Main",
    machine: {
      machineId: "mac-studio:darwin",
      machineLabel: "Mac Studio",
      platform: "darwin",
    },
    capture: {
      sourceApp: "iTerm",
      mode: "watch",
      host: "local-macbook",
      windowId: 7,
      windowIndex: 1,
      tabCount: 2,
      capturedAt: "2026-03-28T12:00:00.000Z",
      trackingStartedAt: "2026-03-28T11:55:00.000Z",
      pollSeconds: 2,
    },
    tabs: [
      {
        path: "/Volumes/Code_2TB/code/orp",
      },
      {
        title: "web",
        path: "/Volumes/Code_2TB/code/orp-web-app",
        resumeCommand: "claude resume claude-999",
        resumeTool: "claude",
        resumeSessionId: "claude-999",
      },
    ],
  };

  await fs.writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  const registration = await registerWorkspaceManifest(manifestPath, manifest, { env });
  const result = await listTrackedWorkspaces({ env });

  assert.match(registration.registryPath, /workspace-registry\.json$/);
  assert.equal(result.workspaces.length, 1);
  assert.deepEqual(result.workspaces[0], {
    manifestPath: path.resolve(manifestPath),
    workspaceId: "orp-main",
    title: "ORP Main",
    machineId: "mac-studio:darwin",
    machineLabel: "Mac Studio",
    platform: "darwin",
    host: "local-macbook",
    captureMode: "watch",
    capturedAt: "2026-03-28T12:00:00.000Z",
    trackingStartedAt: "2026-03-28T11:55:00.000Z",
    windowId: 7,
    windowIndex: 1,
    tabCount: 2,
    codexSessionCount: 1,
    tmuxSessionCount: 0,
    resumeSessions: [
      {
        title: "web",
        path: "/Volumes/Code_2TB/code/orp-web-app",
        resumeCommand: "claude resume claude-999",
        resumeTool: "claude",
        resumeSessionId: "claude-999",
      },
    ],
    registeredAt: registration.entry.registeredAt,
    updatedAt: registration.entry.updatedAt,
    status: "ok",
  });

  const summary = summarizeTrackedWorkspaces(result);
  assert.match(summary, /Local tracked workspaces: 1/);
  assert.match(summary, /ORP Main \[orp-main\]/);
  assert.match(summary, /Machine: Mac Studio \(darwin\)/);
  assert.match(summary, /Saved resume sessions: 1/);
  assert.match(summary, /web: claude resume claude-999/);
});

test("listTrackedWorkspaces retains missing manifests in the registry output", async () => {
  const tempDir = await makeTempDir();
  const env = {
    ...process.env,
    XDG_CONFIG_HOME: path.join(tempDir, "config"),
  };
  const manifestPath = path.join(tempDir, "workspace.json");
  const manifest = {
    version: "1",
    workspaceId: "orp-main",
    tabs: [{ path: "/Volumes/Code_2TB/code/orp" }],
  };

  await fs.writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  await registerWorkspaceManifest(manifestPath, manifest, { env });
  await fs.unlink(manifestPath);

  const result = await listTrackedWorkspaces({ env });
  assert.equal(result.workspaces[0]?.status, "missing");
  assert.equal(result.workspaces[0]?.error, "manifest file not found");
});

test("summarizeTrackedWorkspaces explains how to start when nothing is registered", () => {
  const summary = summarizeTrackedWorkspaces({
    registryPath: "/tmp/workspace-registry.json",
    workspaces: [],
  });

  assert.match(summary, /No local tracked workspaces yet/);
  assert.match(summary, /orp workspace create main-cody-1/);
  assert.match(summary, /orp workspace list/);
});

test("cacheManagedWorkspaceManifest writes a managed local cache and registers it", async () => {
  const tempDir = await makeTempDir();
  const env = {
    ...process.env,
    XDG_CONFIG_HOME: path.join(tempDir, "config"),
  };

  const result = await cacheManagedWorkspaceManifest(
    {
      version: "1",
      workspaceId: "idea-123",
      title: "Main Cody 1",
      tabs: [{ title: "orp", path: "/Volumes/Code_2TB/code/orp" }],
    },
    { env },
  );

  assert.match(result.manifestPath, /workspaces\/idea-123-[a-f0-9]{8}\.json$/);
  assert.equal(path.dirname(result.manifestPath), getManagedWorkspaceDir({ env }));

  const listed = await listTrackedWorkspaces({ env });
  assert.equal(listed.workspaces.length, 1);
  assert.equal(listed.workspaces[0]?.workspaceId, "idea-123");
  assert.equal(listed.workspaces[0]?.title, "Main Cody 1");
});

test("buildWorkspaceInventory merges hosted and local workspace state", () => {
  const result = buildWorkspaceInventory({
    localResult: {
      registryPath: "/tmp/workspace-registry.json",
      workspaces: [
        {
          manifestPath: "/Users/example/.config/orp/workspaces/idea-123-deadbeef.json",
          workspaceId: "idea-123",
          title: "Main Cody 1",
          machineId: "mac-studio:darwin",
          machineLabel: "Mac Studio",
          platform: "darwin",
          tabCount: 2,
          codexSessionCount: 1,
          updatedAt: "2026-03-30T12:00:00.000Z",
          status: "ok",
        },
        {
          manifestPath: "/tmp/local-only.json",
          workspaceId: "local-only",
          title: "Local Only",
          tabCount: 1,
          codexSessionCount: 0,
          updatedAt: "2026-03-29T12:00:00.000Z",
          status: "ok",
        },
      ],
    },
    hostedResult: {
      source: "idea_bridge",
      workspaces: [
        {
          workspace_id: "idea-123",
          title: "Main Cody 1",
          updatedAt: "2026-03-30T12:05:00.000Z",
          linkedIdea: { ideaId: "ef86" },
          metrics: { tabCount: 2 },
          state: {
            capture_context: {
              machine_id: "mac-studio:darwin",
              machine_label: "Mac Studio",
              platform: "darwin",
            },
            tabs: [
              { project_root: "/Volumes/Code_2TB/code/orp", codex_session_id: "abc-123" },
              { project_root: "/Volumes/Code_2TB/code/orp-web-app" },
            ],
          },
          source_kind: "idea_bridge",
        },
      ],
    },
  });

  assert.equal(result.workspaces.length, 2);
  assert.equal(result.workspaces[0]?.workspaceId, "idea-123");
  assert.equal(result.workspaces[0]?.machineLabel, "Mac Studio");
  assert.equal(result.workspaces[0]?.availability, "hosted+local");
  assert.equal(result.workspaces[0]?.syncStatus, "synced");
  assert.equal(result.workspaces[1]?.workspaceId, "local-only");
  assert.equal(result.workspaces[1]?.availability, "local");

  const summary = summarizeWorkspaceInventory(result);
  assert.match(summary, /Workspace inventory: 2/);
  assert.match(summary, /Hosted available: 1/);
  assert.match(summary, /Local available: 2/);
  assert.match(summary, /Machine: Mac Studio \(darwin\)/);
  assert.match(summary, /Sync: synced/);
});

test("applyWorkspaceSlotsToInventory annotates explicit and implicit slots", async () => {
  const tempDir = await makeTempDir();
  const env = {
    ...process.env,
    XDG_CONFIG_HOME: path.join(tempDir, "config"),
  };

  await setWorkspaceSlot(
    "offhand",
    {
      kind: "workspace-file",
      workspaceId: "research-lab",
      title: "research-lab",
      manifestPath: "/tmp/research-lab.json",
    },
    { env },
  );
  const { slots } = await loadWorkspaceSlots({ env });

  const explicitResult = applyWorkspaceSlotsToInventory(
    buildWorkspaceInventory({
      localResult: {
        registryPath: "/tmp/workspace-registry.json",
        workspaces: [
          {
            manifestPath: "/tmp/research-lab.json",
            workspaceId: "research-lab",
            title: "research-lab",
            tabCount: 1,
            codexSessionCount: 0,
            updatedAt: "2026-03-30T12:00:00.000Z",
            status: "ok",
          },
        ],
      },
      hostedResult: {
        source: "idea_bridge",
        workspaces: [],
      },
    }),
    slots,
  );

  assert.deepEqual(explicitResult.workspaces[0]?.slots, ["offhand", "main"]);
  assert.equal(explicitResult.workspaces[0]?.implicitMain, true);

  const implicitResult = applyWorkspaceSlotsToInventory(
    buildWorkspaceInventory({
      localResult: {
        registryPath: "/tmp/workspace-registry.json",
        workspaces: [
          {
            manifestPath: "/tmp/main-cody-1.json",
            workspaceId: "main-cody-1",
            title: "main-cody-1",
            tabCount: 2,
            codexSessionCount: 1,
            updatedAt: "2026-03-30T12:00:00.000Z",
            status: "ok",
          },
        ],
      },
      hostedResult: {
        source: "idea_bridge",
        workspaces: [],
      },
    }),
    {},
  );

  assert.deepEqual(implicitResult.workspaces[0]?.slots, ["main"]);
  assert.equal(implicitResult.workspaces[0]?.implicitMain, true);
  assert.match(summarizeWorkspaceInventory(implicitResult), /Slots: main \(main inferred because this is the only workspace\)/);
});
