import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { mergeLocalProjectInventoryIntoManifest } from "../src/index.js";

async function makeTempDir() {
  return fs.mkdtemp(path.join(os.tmpdir(), "orp-local-inventory-"));
}

async function writeJson(filePath, payload) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

test("mergeLocalProjectInventoryIntoManifest reconciles ORP startup, Clawdad, and known Codex sessions", async () => {
  const root = await makeTempDir();
  const codexHome = path.join(root, "codex-home");
  const clawdadStatePath = path.join(root, "clawdad", "state.json");
  const existingPath = path.join(root, "existing");
  const tailnetPath = path.join(root, "tailnet-app");
  const financialPath = path.join(root, "financial-stack");

  await fs.mkdir(existingPath, { recursive: true });
  await writeJson(path.join(tailnetPath, "orp", "state.json"), {
    startup: {
      updated_at_utc: "2026-04-30T02:59:15Z",
      workspace: {
        requested: true,
        workspace: "main",
        path: tailnetPath,
        result: {
          manifest: {
            version: "1",
            workspaceId: "main",
            title: "main",
            tabs: [
              {
                title: "financial-stack",
                path: financialPath,
                resumeTool: "codex",
                resumeSessionId: "019dc348-ce52-7f52-8ac8-0200a9bf946a",
              },
            ],
          },
          tab: {
            title: "Tailnet App",
            path: tailnetPath,
            bootstrapCommand: "npm test",
            resumeTool: "codex",
            resumeSessionId: "019dcd50-111d-7451-bd01-dbc21336c679",
          },
        },
      },
    },
  });
  await writeJson(clawdadStatePath, {
    projects: {
      [financialPath]: {
        status: "completed",
        last_dispatch: "2026-04-25T20:47:50Z",
        last_response: "2026-04-25T20:49:37Z",
        registered_at: "2026-04-25T20:11:21.625Z",
        sessions: {
          "019dc348-ce52-7f52-8ac8-0200a9bf946a": {
            slug: "financial-stack",
            provider: "codex",
            quarantined: "true",
          },
          "019dc644-d31d-78e1-a3ed-8575aead1c96": {
            slug: "financial-stack",
            provider: "codex",
            tracked_at: "2026-04-25T20:11:21.625Z",
          },
        },
        quarantined_sessions: {
          "019dc348-ce52-7f52-8ac8-0200a9bf946a": true,
        },
      },
    },
  });
  const codexSessionPath = path.join(codexHome, "sessions", "2026", "04", "30", "rollout-existing.jsonl");
  await fs.mkdir(path.dirname(codexSessionPath), { recursive: true });
  await fs.writeFile(codexSessionPath, `${JSON.stringify({
    timestamp: "2026-04-30T12:00:00.000Z",
    type: "session_meta",
    payload: {
      id: "019df000-1111-7222-8333-444455556666",
      cwd: existingPath,
      timestamp: "2026-04-30T12:00:00.000Z",
    },
  })}\n`, "utf8");

  const merged = await mergeLocalProjectInventoryIntoManifest(
    {
      version: "1",
      workspaceId: "main",
      title: "main",
      tabs: [
        {
          title: "existing",
          path: existingPath,
          resumeTool: "codex",
          resumeSessionId: "019d0000-1111-7222-8333-444455556666",
        },
      ],
    },
    {
      localProjectRoots: [root],
      clawdadStatePath,
      codexHome,
      workspaceSelector: "main",
      codexScanDays: 30,
    },
  );

  const byPath = new Map(merged.manifest.tabs.map((tab) => [tab.path, tab]));
  assert.equal(byPath.get(existingPath)?.resumeSessionId, "019df000-1111-7222-8333-444455556666");
  assert.equal(byPath.get(tailnetPath)?.bootstrapCommand, "npm test");
  assert.equal(byPath.get(tailnetPath)?.resumeSessionId, "019dcd50-111d-7451-bd01-dbc21336c679");
  assert.equal(byPath.get(financialPath)?.resumeSessionId, "019dc644-d31d-78e1-a3ed-8575aead1c96");
  assert.equal([...byPath.values()].some((tab) => tab.resumeSessionId === "019dc348-ce52-7f52-8ac8-0200a9bf946a"), false);
  assert.equal(merged.inventory.projectCount, 3);
});
