import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  applyCodexReconcilePlan,
  buildCodexReconcilePlan,
  buildCodexStatusReport,
  parseCodexSessionMetaLine,
  runOrpCodexCommand,
  scanCodexSessions,
} from "../src/index.js";

async function makeTempDir() {
  return fs.mkdtemp(path.join(os.tmpdir(), "orp-codex-"));
}

async function writeSession(codexHome, sessionId, cwd, timestamp, extraPayload = {}) {
  const day = timestamp.slice(0, 10).split("-");
  const sessionsDir = path.join(codexHome, "sessions", day[0], day[1], day[2]);
  await fs.mkdir(sessionsDir, { recursive: true });
  const filePath = path.join(sessionsDir, `rollout-${timestamp.replaceAll(":", "-")}-${sessionId}.jsonl`);
  const row = {
    timestamp,
    type: "session_meta",
    payload: {
      id: sessionId,
      timestamp,
      cwd,
      originator: "codex-tui",
      cli_version: "0.125.0",
      ...extraPayload,
    },
  };
  await fs.writeFile(filePath, `${JSON.stringify(row)}\n`, "utf8");
  const mtime = new Date(timestamp);
  await fs.utimes(filePath, mtime, mtime);
  return filePath;
}

async function writeSessionWithPrefix(codexHome, sessionId, cwd, timestamp) {
  const filePath = await writeSession(codexHome, sessionId, cwd, timestamp);
  const original = await fs.readFile(filePath, "utf8");
  await fs.writeFile(filePath, `${JSON.stringify({ type: "response_item", payload: {} })}\n${original}`, "utf8");
  const mtime = new Date(timestamp);
  await fs.utimes(filePath, mtime, mtime);
  return filePath;
}

async function writeWorkspaceManifest(filePath, tabs) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(
    filePath,
    `${JSON.stringify(
      {
        version: "1",
        workspaceId: "orp-main",
        title: "ORP Main",
        tabs,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
}

test("parseCodexSessionMetaLine reads stable session metadata", () => {
  const row = JSON.stringify({
    timestamp: "2026-04-25T12:00:00Z",
    type: "session_meta",
    payload: {
      id: "019dc2cb-d435-7072-bbfd-4ae4280474dd",
      timestamp: "2026-04-25T12:00:00Z",
      cwd: "/tmp/example",
      originator: "codex-tui",
      cli_version: "0.125.0",
    },
  });

  const parsed = parseCodexSessionMetaLine(row, "/tmp/session.jsonl", { mtimeMs: 123 });
  assert.equal(parsed.sessionId, "019dc2cb-d435-7072-bbfd-4ae4280474dd");
  assert.equal(parsed.cwd, "/tmp/example");
  assert.equal(parsed.cliVersion, "0.125.0");
  assert.equal(parsed.updatedMs, 123);
  assert.equal(parseCodexSessionMetaLine("not json", "/tmp/session.jsonl"), null);
});

test("scanCodexSessions ignores delegated sessions by default", async () => {
  const tempDir = await makeTempDir();
  const codexHome = path.join(tempDir, "codex-home");
  await writeSession(
    codexHome,
    "019dc2cb-d435-7072-bbfd-4ae4280474aa",
    path.join(tempDir, "repo"),
    "2026-04-25T12:00:00Z",
  );
  await writeSession(
    codexHome,
    "019dc2cb-d435-7072-bbfd-4ae4280474bb",
    path.join(tempDir, "repo"),
    "2026-04-25T12:01:00Z",
    { source: { subagent: { other: "guardian" } } },
  );
  await writeSession(
    codexHome,
    "019dc2cb-d435-7072-bbfd-4ae4280474cc",
    path.join(tempDir, "repo"),
    "2026-04-25T12:02:00Z",
    { originator: "clawdad" },
  );

  const defaultSessions = await scanCodexSessions({ codexHome, sinceMs: 0 });
  assert.deepEqual(
    defaultSessions.map((session) => session.sessionId),
    ["019dc2cb-d435-7072-bbfd-4ae4280474aa"],
  );

  const allSessions = await scanCodexSessions({ codexHome, sinceMs: 0, includeSubagents: true });
  assert.deepEqual(
    allSessions.map((session) => session.sessionId),
    [
      "019dc2cb-d435-7072-bbfd-4ae4280474cc",
      "019dc2cb-d435-7072-bbfd-4ae4280474bb",
      "019dc2cb-d435-7072-bbfd-4ae4280474aa",
    ],
  );
});

test("scanCodexSessions ignores exec sessions by default", async () => {
  const tempDir = await makeTempDir();
  const codexHome = path.join(tempDir, "codex-home");
  const repoRoot = path.join(tempDir, "repo");
  await writeSession(
    codexHome,
    "019dc2cb-d435-7072-bbfd-4ae4280474d1",
    repoRoot,
    "2026-04-25T12:00:00Z",
  );
  await writeSession(
    codexHome,
    "019dc2cb-d435-7072-bbfd-4ae4280474d2",
    repoRoot,
    "2026-04-25T12:01:00Z",
    { originator: "codex_exec", source: "exec" },
  );

  const defaultSessions = await scanCodexSessions({ codexHome, sinceMs: 0 });
  assert.deepEqual(
    defaultSessions.map((session) => session.sessionId),
    ["019dc2cb-d435-7072-bbfd-4ae4280474d1"],
  );

  const withExecSessions = await scanCodexSessions({ codexHome, sinceMs: 0, includeExec: true });
  assert.deepEqual(
    withExecSessions.map((session) => session.sessionId),
    ["019dc2cb-d435-7072-bbfd-4ae4280474d2", "019dc2cb-d435-7072-bbfd-4ae4280474d1"],
  );
  assert.equal(withExecSessions[0].source, "exec");
});

test("scanCodexSessions finds session metadata near the start of a rollout file", async () => {
  const tempDir = await makeTempDir();
  const codexHome = path.join(tempDir, "codex-home");
  const repoRoot = path.join(tempDir, "repo");
  await writeSessionWithPrefix(
    codexHome,
    "019dc2cb-d435-7072-bbfd-4ae4280474dd",
    repoRoot,
    "2026-04-25T12:00:00Z",
  );

  const sessions = await scanCodexSessions({ codexHome, sinceMs: 0 });
  assert.equal(sessions.length, 1);
  assert.equal(sessions[0].sessionId, "019dc2cb-d435-7072-bbfd-4ae4280474dd");
});

test("buildCodexStatusReport marks a tracked repo stale when local Codex metadata is newer", async () => {
  const tempDir = await makeTempDir();
  const repoRoot = path.join(tempDir, "repo");
  const codexHome = path.join(tempDir, "codex-home");
  const workspaceFile = path.join(tempDir, "workspace.json");
  await fs.mkdir(repoRoot, { recursive: true });
  await writeWorkspaceManifest(workspaceFile, [
    {
      title: "repo",
      path: repoRoot,
      resumeTool: "codex",
      resumeSessionId: "019dc2cb-d435-7072-bbfd-4ae428047401",
    },
  ]);
  await writeSession(codexHome, "019dc2cb-d435-7072-bbfd-4ae428047402", repoRoot, "2026-04-25T12:00:00Z");

  const report = await buildCodexStatusReport({
    workspaceFile,
    codexHome,
    path: repoRoot,
    sinceDays: 0,
  });

  assert.equal(report.status, "stale");
  assert.equal(report.trackedTab.codexSessionId, "019dc2cb-d435-7072-bbfd-4ae428047401");
  assert.equal(report.latestCodexSession.sessionId, "019dc2cb-d435-7072-bbfd-4ae428047402");
});

test("Codex reconcile updates tracked workspace tabs without appending by default", async () => {
  const tempDir = await makeTempDir();
  const repoRoot = path.join(tempDir, "repo");
  const codexHome = path.join(tempDir, "codex-home");
  const workspaceFile = path.join(tempDir, "workspace.json");
  await fs.mkdir(repoRoot, { recursive: true });
  await writeWorkspaceManifest(workspaceFile, [
    {
      title: "repo",
      path: repoRoot,
      resumeTool: "codex",
      resumeSessionId: "019dc2cb-d435-7072-bbfd-4ae428047411",
    },
  ]);
  await writeSession(codexHome, "019dc2cb-d435-7072-bbfd-4ae428047412", repoRoot, "2026-04-25T12:00:00Z");

  const plan = await buildCodexReconcilePlan({
    workspaceFile,
    codexHome,
    sinceDays: 0,
  });
  assert.equal(plan.actionCount, 1);
  assert.equal(plan.actions[0].action, "update");

  const applied = await applyCodexReconcilePlan(plan, {
    workspaceFile,
    codexHome,
  });
  assert.equal(applied.actions[0].applied, true);

  const manifest = JSON.parse(await fs.readFile(workspaceFile, "utf8"));
  assert.equal(manifest.tabs.length, 1);
  assert.equal(manifest.tabs[0].resumeSessionId, "019dc2cb-d435-7072-bbfd-4ae428047412");
  assert.equal(manifest.tabs[0].codexSessionId, "019dc2cb-d435-7072-bbfd-4ae428047412");
});

test("bare orp codex routes to start", async () => {
  const tempDir = await makeTempDir();
  const codexHome = path.join(tempDir, "codex-home");
  const fakeCodex = path.join(tempDir, "fake-codex");
  await fs.writeFile(fakeCodex, "#!/bin/sh\nexit 0\n", "utf8");
  await fs.chmod(fakeCodex, 0o755);

  const originalWrite = process.stderr.write;
  let stderr = "";
  process.stderr.write = (chunk) => {
    stderr += String(chunk);
    return true;
  };
  try {
    const code = await runOrpCodexCommand([
      "--path",
      tempDir,
      "--codex-home",
      codexHome,
      "--codex-bin",
      fakeCodex,
      "--watch-timeout-ms",
      "1",
      "--search",
    ]);
    assert.equal(code, 0);
    assert.match(stderr, /Fallback: orp workspace add-tab main --here --current-codex/);
  } finally {
    process.stderr.write = originalWrite;
  }
});

test("bare orp codex saves the new session when Codex writes metadata", async () => {
  const tempDir = await makeTempDir();
  const repoRoot = path.join(tempDir, "repo");
  const codexHome = path.join(tempDir, "codex-home");
  const workspaceFile = path.join(tempDir, "workspace.json");
  const fakeCodex = path.join(tempDir, "fake-codex.js");
  const sessionId = "019dc2cb-d435-7072-bbfd-4ae4280474ee";
  await fs.mkdir(repoRoot, { recursive: true });
  await writeWorkspaceManifest(workspaceFile, []);
  await fs.writeFile(
    fakeCodex,
    `#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");
if (!process.argv.includes("--search")) process.exit(7);
const codexHome = ${JSON.stringify(codexHome)};
const repoRoot = ${JSON.stringify(repoRoot)};
const sessionId = ${JSON.stringify(sessionId)};
const timestamp = new Date().toISOString();
const dir = path.join(codexHome, "sessions", "2026", "04", "25");
fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(
  path.join(dir, "rollout-2026-04-25T12-00-00Z-" + sessionId + ".jsonl"),
  JSON.stringify({
    timestamp,
    type: "session_meta",
    payload: { id: sessionId, timestamp, cwd: repoRoot, originator: "codex-tui" },
  }) + "\\n",
);
`,
    "utf8",
  );
  await fs.chmod(fakeCodex, 0o755);

  const originalWrite = process.stderr.write;
  let stderr = "";
  process.stderr.write = (chunk) => {
    stderr += String(chunk);
    return true;
  };
  try {
    const code = await runOrpCodexCommand([
      "--path",
      repoRoot,
      "--workspace-file",
      workspaceFile,
      "--codex-home",
      codexHome,
      "--codex-bin",
      fakeCodex,
      "--watch-timeout-ms",
      "2000",
      "--search",
    ]);
    assert.equal(code, 0);
    assert.match(stderr, new RegExp(`ORP saved Codex session for .*: codex resume ${sessionId}`));
  } finally {
    process.stderr.write = originalWrite;
  }

  const manifest = JSON.parse(await fs.readFile(workspaceFile, "utf8"));
  assert.equal(manifest.tabs.length, 1);
  assert.equal(manifest.tabs[0].path, repoRoot);
  assert.equal(manifest.tabs[0].resumeTool, "codex");
  assert.equal(manifest.tabs[0].resumeSessionId, sessionId);
});
