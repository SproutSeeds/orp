import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  addTabToManifest,
  normalizeWorkspaceManifest,
  parseWorkspaceCreateArgs,
  parseWorkspaceAddTabArgs,
  parseWorkspaceRemoveTabArgs,
  removeTabsFromManifest,
  runWorkspaceCreate,
  runWorkspaceAddTab,
  runWorkspaceRemoveTab,
} from "../src/index.js";

async function makeTempDir() {
  return fs.mkdtemp(path.join(os.tmpdir(), "orp-workspace-ledger-"));
}

async function captureStdout(fn) {
  const chunks = [];
  const originalWrite = process.stdout.write;
  process.stdout.write = (chunk, encoding, callback) => {
    chunks.push(typeof chunk === "string" ? chunk : chunk.toString(encoding || "utf8"));
    if (typeof callback === "function") {
      callback();
    }
    return true;
  };

  try {
    const code = await fn();
    return {
      code,
      stdout: chunks.join(""),
    };
  } finally {
    process.stdout.write = originalWrite;
  }
}

async function withTempConfigHome(fn) {
  const tempDir = await makeTempDir();
  const original = process.env.XDG_CONFIG_HOME;
  process.env.XDG_CONFIG_HOME = tempDir;
  try {
    return await fn(tempDir);
  } finally {
    if (original == null) {
      delete process.env.XDG_CONFIG_HOME;
    } else {
      process.env.XDG_CONFIG_HOME = original;
    }
  }
}

async function makeFakeIdeaBridgeOrpCommand(tempDir, options = {}) {
  const scriptPath = path.join(tempDir, "fake-orp.cjs");
  const logPath = path.join(tempDir, "orp-calls.jsonl");
  const failCreate = options.failCreate === true;
  const script = `#!/usr/bin/env node
const fs = require("node:fs");

const args = process.argv.slice(2);
const logPath = process.env.FAKE_ORP_LOG;
if (logPath) {
  fs.appendFileSync(logPath, JSON.stringify({ args }) + "\\n", "utf8");
}

const ideaId = "idea-main-123";
const bridgeWorkspaceId = "captured-iterm-window-20260401t032225z";
const hostedWorkspaceId = "ws-main-cody-1";
const failCreate = ${JSON.stringify(failCreate)};
const baseTabs = [
  { tab_id: "tab-orp", title: "orp", project_root: "/Volumes/Code_2TB/code/orp" },
  { tab_id: "tab-frg", title: "frg-site", project_root: "/Volumes/Code_2TB/code/frg-site" },
];

function write(payload) {
  process.stdout.write(JSON.stringify(payload) + "\\n");
}

function linkedIdea() {
  return {
    idea_id: ideaId,
    idea_title: "Terminal paths and codex sessions 03-26-2026",
    relationship: "primary",
  };
}

function state(tabs) {
  return {
    captured_at_utc: "2026-04-15T12:00:00.000Z",
    updated_at_utc: "2026-04-15T12:00:00.000Z",
    tab_count: tabs.length,
    capture_context: {
      source_app: "test",
      mode: "snapshot",
      machine_id: "test-mac:darwin",
      machine_label: "Test Mac",
      platform: "darwin",
    },
    tabs,
  };
}

function bridgeWorkspace() {
  return {
    workspace_id: bridgeWorkspaceId,
    title: "Main Cody 1",
    source_kind: "idea_bridge",
    linked_idea: linkedIdea(),
    state: state(baseTabs),
  };
}

function hostedWorkspace(tabs = []) {
  return {
    workspace_id: hostedWorkspaceId,
    title: "main-cody-1",
    source_kind: "hosted",
    linked_idea: linkedIdea(),
    state: state(tabs),
  };
}

if (args[0] === "workspaces" && args[1] === "list") {
  write({ ok: true, source: "hosted", workspaces: [bridgeWorkspace()], has_more: false, cursor: "" });
} else if (args[0] === "workspaces" && args[1] === "show") {
  if (args[2] === bridgeWorkspaceId) {
    write({ ok: true, workspace: bridgeWorkspace() });
  } else if (args[2] === hostedWorkspaceId) {
    write({ ok: true, workspace: hostedWorkspace(baseTabs) });
  } else {
    process.stderr.write("unknown workspace: " + args[2] + "\\n");
    process.exit(1);
  }
} else if (args[0] === "workspaces" && args[1] === "add") {
  if (failCreate) {
    process.stderr.write("Hosted ORP returned an HTML error page instead of JSON (status=404 path=/api/cli/workspaces)\\n");
    process.exit(1);
  }
  const title = args[args.indexOf("--title") + 1];
  const linked = args[args.indexOf("--idea-id") + 1];
  if (title !== "main-cody-1" || linked !== ideaId) {
    process.stderr.write("unexpected add args: " + JSON.stringify(args) + "\\n");
    process.exit(1);
  }
  write({ ok: true, workspace: hostedWorkspace([]) });
} else if (args[0] === "workspaces" && args[1] === "push-state") {
  const stateFile = args[args.indexOf("--state-file") + 1];
  const pushedState = JSON.parse(fs.readFileSync(stateFile, "utf8"));
  write({ ok: true, workspace: hostedWorkspace(pushedState.tabs || []) });
} else if (args[0] === "ideas" && args[1] === "list") {
  write({ ok: true, ideas: [], has_more: false, cursor: "" });
} else if (args[0] === "idea" && args[1] === "update") {
  process.stderr.write("idea update should not be called\\n");
  process.exit(2);
} else {
  process.stderr.write("unexpected args: " + JSON.stringify(args) + "\\n");
  process.exit(1);
}
`;

  await fs.writeFile(scriptPath, script, "utf8");
  await fs.chmod(scriptPath, 0o755);
  await fs.writeFile(logPath, "", "utf8");
  return { scriptPath, logPath };
}

function sampleManifest() {
  return normalizeWorkspaceManifest({
    version: "1",
    workspaceId: "main-cody-1",
    title: "main-cody-1",
    tabs: [
      {
        title: "orp",
        path: "/Volumes/Code_2TB/code/orp",
      },
      {
        title: "frg-site",
        path: "/Volumes/Code_2TB/code/frg-site",
        resumeCommand: "codex resume 019d348d-5031-78e1-9840-a66deaac33ae",
        resumeTool: "codex",
        resumeSessionId: "019d348d-5031-78e1-9840-a66deaac33ae",
      },
    ],
  });
}

test("parseWorkspaceAddTabArgs accepts explicit resume metadata", () => {
  const parsed = parseWorkspaceAddTabArgs([
    "main",
    "--path",
    "/Volumes/Code_2TB/code/new-project",
    "--remote-url",
    "git@github.com:org/new-project.git",
    "--bootstrap-command",
    "npm install",
    "--resume-tool",
    "claude",
    "--resume-session-id",
    "claude-456",
    "--json",
  ]);

  assert.equal(parsed.ideaId, "main");
  assert.equal(parsed.path, "/Volumes/Code_2TB/code/new-project");
  assert.equal(parsed.remoteUrl, "git@github.com:org/new-project.git");
  assert.equal(parsed.bootstrapCommand, "npm install");
  assert.equal(parsed.resumeTool, "claude");
  assert.equal(parsed.resumeSessionId, "claude-456");
  assert.equal(parsed.json, true);
});

test("parseWorkspaceAddTabArgs resolves --here and --current-codex", () => {
  const originalThreadId = process.env.CODEX_THREAD_ID;
  const originalCwd = process.cwd();
  process.env.CODEX_THREAD_ID = "019d4f24-c8ba-78b2-a726-48b1ce9f0fe9";
  process.chdir("/Volumes/Code_2TB/code/orp");
  try {
    const parsed = parseWorkspaceAddTabArgs([
      "main",
      "--here",
      "--current-codex",
    ]);

    assert.equal(parsed.ideaId, "main");
    assert.equal(parsed.path, "/Volumes/Code_2TB/code/orp");
    assert.equal(parsed.resumeTool, "codex");
    assert.equal(parsed.resumeSessionId, "019d4f24-c8ba-78b2-a726-48b1ce9f0fe9");
  } finally {
    process.chdir(originalCwd);
    if (originalThreadId == null) {
      delete process.env.CODEX_THREAD_ID;
    } else {
      process.env.CODEX_THREAD_ID = originalThreadId;
    }
  }
});

test("parseWorkspaceCreateArgs validates slug titles and optional seed metadata", () => {
  const parsed = parseWorkspaceCreateArgs([
    "main-cody-1",
    "--slot",
    "main",
    "--machine-label",
    "Mac Studio",
    "--path",
    "/Volumes/Code_2TB/code/orp",
    "--remote-url",
    "git@github.com:SproutSeeds/orp.git",
    "--resume-tool",
    "claude",
    "--resume-session-id",
    "claude-456",
    "--json",
  ]);

  assert.equal(parsed.title, "main-cody-1");
  assert.equal(parsed.slotName, "main");
  assert.equal(parsed.machineLabel, "Mac Studio");
  assert.equal(parsed.path, "/Volumes/Code_2TB/code/orp");
  assert.equal(parsed.remoteUrl, "git@github.com:SproutSeeds/orp.git");
  assert.equal(parsed.resumeTool, "claude");
  assert.equal(parsed.resumeSessionId, "claude-456");
  assert.equal(parsed.json, true);
  assert.throws(() => parseWorkspaceCreateArgs(["Main Cody"]), /workspace title/);
});

test("parseWorkspaceRemoveTabArgs requires a matching selector", () => {
  assert.throws(
    () => parseWorkspaceRemoveTabArgs(["main"]),
    /Provide at least one selector/,
  );
});

test("addTabToManifest canonicalizes Claude resume commands from tool plus session id", () => {
  const result = addTabToManifest(sampleManifest(), {
    path: "/Volumes/Code_2TB/code/anthropic-lab",
    title: "anthropic-lab",
    remoteUrl: "git@github.com:anthropic/anthropic-lab.git",
    bootstrapCommand: "uv sync",
    resumeTool: "claude",
    resumeSessionId: "claude-456",
  });

  assert.equal(result.added, true);
  assert.equal(result.manifest.tabs.length, 3);
  assert.equal(result.manifest.tabs[2]?.path, "/Volumes/Code_2TB/code/anthropic-lab");
  assert.equal(result.manifest.tabs[2]?.title, "anthropic-lab");
  assert.equal(result.manifest.tabs[2]?.remoteUrl, "git@github.com:anthropic/anthropic-lab.git");
  assert.equal(result.manifest.tabs[2]?.bootstrapCommand, "uv sync");
  assert.equal(result.manifest.tabs[2]?.resumeCommand, "claude --resume claude-456");
  assert.equal(result.manifest.tabs[2]?.resumeTool, "claude");
  assert.equal(result.manifest.tabs[2]?.sessionId, "claude-456");
});

test("addTabToManifest updates an existing matching tab instead of appending a duplicate", () => {
  const result = addTabToManifest(sampleManifest(), {
    path: "/Volumes/Code_2TB/code/orp",
    title: "orp",
    resumeTool: "codex",
    resumeSessionId: "019d4f24-c8ba-78b2-a726-48b1ce9f0fe9",
  });

  assert.equal(result.added, false);
  assert.equal(result.updated, true);
  assert.equal(result.mutation, "updated");
  assert.equal(result.manifest.tabs.length, 2);
  assert.equal(result.manifest.tabs[0]?.resumeCommand, "codex resume 019d4f24-c8ba-78b2-a726-48b1ce9f0fe9");
});

test("addTabToManifest preserves existing resume metadata when no new resume is provided", () => {
  const result = addTabToManifest(sampleManifest(), {
    path: "/Volumes/Code_2TB/code/frg-site",
    title: "frg-site",
  });

  assert.equal(result.added, false);
  assert.equal(result.updated, false);
  assert.equal(result.unchanged, true);
  assert.equal(result.mutation, "unchanged");
  assert.equal(result.manifest.tabs.length, 2);
  assert.equal(result.manifest.tabs[1]?.resumeCommand, "codex resume 019d348d-5031-78e1-9840-a66deaac33ae");
});

test("addTabToManifest asks for a title when multiple saved tabs share a path", () => {
  const manifest = normalizeWorkspaceManifest({
    version: "1",
    workspaceId: "main-cody-1",
    title: "main-cody-1",
    tabs: [
      {
        title: "longevity-research",
        path: "/Volumes/Code_2TB/code/longevity-research",
      },
      {
        title: "longevity-research (2)",
        path: "/Volumes/Code_2TB/code/longevity-research",
      },
    ],
  });

  assert.throws(
    () =>
      addTabToManifest(manifest, {
        path: "/Volumes/Code_2TB/code/longevity-research",
        resumeTool: "codex",
        resumeSessionId: "019d4f24-c8ba-78b2-a726-48b1ce9f0fe9",
      }),
    /Multiple saved tabs already use this path/,
  );
});

test("normalizeWorkspaceManifest expands grouped project sessions", () => {
  const manifest = normalizeWorkspaceManifest({
    version: "1",
    workspaceId: "main-cody-1",
    title: "main-cody-1",
    projects: [
      {
        title: "orp",
        path: "/Volumes/Code_2TB/code/orp",
        remoteUrl: "git@github.com:SproutSeeds/orp.git",
        sessions: [
          {
            title: "orp release",
            resumeTool: "codex",
            resumeSessionId: "019d32d3-d8b2-7fa2-aaec-c74b5134afd6",
          },
          {
            title: "orp docs",
            resumeCommand: "claude --resume 469d99b2-2997-42bf-a8f5-3812c808ef29",
          },
        ],
      },
    ],
  });

  assert.equal(manifest.tabs.length, 2);
  assert.equal(manifest.tabs[0]?.path, "/Volumes/Code_2TB/code/orp");
  assert.equal(manifest.tabs[0]?.title, "orp release");
  assert.equal(manifest.tabs[0]?.resumeTool, "codex");
  assert.equal(manifest.tabs[1]?.title, "orp docs");
  assert.equal(manifest.tabs[1]?.resumeTool, "claude");
  assert.equal(manifest.tabs[1]?.sessionId, "469d99b2-2997-42bf-a8f5-3812c808ef29");
});

test("removeTabsFromManifest can target a saved tab by path and resume session id", () => {
  const result = removeTabsFromManifest(sampleManifest(), {
    path: "/Volumes/Code_2TB/code/frg-site",
    resumeSessionId: "019d348d-5031-78e1-9840-a66deaac33ae",
  });

  assert.equal(result.manifest.tabs.length, 1);
  assert.equal(result.removedTabs.length, 1);
  assert.equal(result.removedTabs[0]?.path, "/Volumes/Code_2TB/code/frg-site");
});

test("runWorkspaceAddTab updates a local workspace manifest file", async () => {
  await withTempConfigHome(async () => {
    const tempDir = await makeTempDir();
    const manifestPath = path.join(tempDir, "workspace.json");
    await fs.writeFile(manifestPath, `${JSON.stringify(sampleManifest(), null, 2)}\n`, "utf8");

    const { code, stdout } = await captureStdout(() =>
      runWorkspaceAddTab([
        "--workspace-file",
        manifestPath,
        "--path",
        "/Volumes/Code_2TB/code/anthropic-lab",
        "--remote-url",
        "git@github.com:anthropic/anthropic-lab.git",
        "--bootstrap-command",
        "uv sync",
        "--resume-tool",
        "claude",
        "--resume-session-id",
        "claude-456",
        "--json",
      ]),
    );
    const payload = JSON.parse(stdout);
    const saved = JSON.parse(await fs.readFile(manifestPath, "utf8"));

    assert.equal(code, 0);
    assert.equal(payload.action, "add-tab");
    assert.equal(payload.tabCount, 3);
    assert.equal(payload.tab.remoteUrl, "git@github.com:anthropic/anthropic-lab.git");
    assert.equal(payload.tab.bootstrapCommand, "uv sync");
    assert.equal(payload.tab.resumeCommand, "claude --resume claude-456");
    assert.equal(saved.tabs.length, 3);
    assert.equal(saved.tabs[2]?.remoteUrl, "git@github.com:anthropic/anthropic-lab.git");
    assert.equal(saved.tabs[2]?.resumeCommand, "claude --resume claude-456");
  });
});

test("runWorkspaceAddTab promotes idea-bridge workspaces to hosted workspace state", async () => {
  await withTempConfigHome(async (configHome) => {
    const tempDir = await makeTempDir();
    const { scriptPath, logPath } = await makeFakeIdeaBridgeOrpCommand(tempDir);
    const originalLogPath = process.env.FAKE_ORP_LOG;
    process.env.FAKE_ORP_LOG = logPath;

    try {
      const { code, stdout } = await captureStdout(() =>
        runWorkspaceAddTab([
          "main",
          "--path",
          "/Volumes/Code_2TB/code/anthropic-lab",
          "--title",
          "anthropic-lab",
          "--remote-url",
          "git@github.com:anthropic/anthropic-lab.git",
          "--resume-tool",
          "codex",
          "--resume-session-id",
          "019d4f24-c8ba-78b2-a726-48b1ce9f0fe9",
          "--orp-command",
          scriptPath,
          "--json",
        ]),
      );
      const payload = JSON.parse(stdout);
      const calls = (await fs.readFile(logPath, "utf8"))
        .trim()
        .split("\n")
        .filter(Boolean)
        .map((line) => JSON.parse(line).args);
      const slots = JSON.parse(await fs.readFile(path.join(configHome, "orp", "workspace-slots.json"), "utf8"));

      assert.equal(code, 0);
      assert.equal(payload.persistedTo, "hosted-workspace");
      assert.equal(payload.promotedFromIdeaId, "idea-main-123");
      assert.equal(payload.createdHostedWorkspace, true);
      assert.equal(payload.workspaceSourceId, "ws-main-cody-1");
      assert.equal(payload.tabCount, 3);
      assert.equal(payload.tab.restartCommand, "cd '/Volumes/Code_2TB/code/anthropic-lab' && codex resume 019d4f24-c8ba-78b2-a726-48b1ce9f0fe9");
      assert.equal(payload.manifest.tabs[2]?.path, "/Volumes/Code_2TB/code/anthropic-lab");
      assert.ok(calls.some((args) => args[0] === "workspaces" && args[1] === "add"));
      assert.ok(calls.some((args) => args[0] === "workspaces" && args[1] === "push-state"));
      assert.equal(calls.some((args) => args[0] === "idea" && args[1] === "update"), false);
      assert.equal(slots.slots.main.kind, "hosted-workspace");
      assert.equal(slots.slots.main.hostedWorkspaceId, "ws-main-cody-1");
    } finally {
      if (originalLogPath == null) {
        delete process.env.FAKE_ORP_LOG;
      } else {
        process.env.FAKE_ORP_LOG = originalLogPath;
      }
    }
  });
});

test("runWorkspaceAddTab falls back to local ledger when hosted workspace creation is unavailable", async () => {
  await withTempConfigHome(async (configHome) => {
    const tempDir = await makeTempDir();
    const { scriptPath, logPath } = await makeFakeIdeaBridgeOrpCommand(tempDir, { failCreate: true });
    const originalLogPath = process.env.FAKE_ORP_LOG;
    process.env.FAKE_ORP_LOG = logPath;

    try {
      const { code, stdout } = await captureStdout(() =>
        runWorkspaceAddTab([
          "main",
          "--path",
          "/Volumes/Code_2TB/code/anthropic-lab",
          "--title",
          "anthropic-lab",
          "--remote-url",
          "git@github.com:anthropic/anthropic-lab.git",
          "--resume-tool",
          "codex",
          "--resume-session-id",
          "019d4f24-c8ba-78b2-a726-48b1ce9f0fe9",
          "--orp-command",
          scriptPath,
          "--json",
        ]),
      );
      const payload = JSON.parse(stdout);
      const calls = (await fs.readFile(logPath, "utf8"))
        .trim()
        .split("\n")
        .filter(Boolean)
        .map((line) => JSON.parse(line).args);
      const saved = JSON.parse(await fs.readFile(payload.manifestPath, "utf8"));
      const slots = JSON.parse(await fs.readFile(path.join(configHome, "orp", "workspace-slots.json"), "utf8"));

      assert.equal(code, 0);
      assert.equal(payload.persistedTo, "workspace-file");
      assert.equal(payload.promotedFromIdeaId, "idea-main-123");
      assert.match(payload.hostedMigrationSkippedReason, /status=404/);
      assert.equal(payload.tabCount, 3);
      assert.equal(saved.tabs[2]?.path, "/Volumes/Code_2TB/code/anthropic-lab");
      assert.ok(calls.some((args) => args[0] === "workspaces" && args[1] === "add"));
      assert.equal(calls.some((args) => args[0] === "idea" && args[1] === "update"), false);
      assert.equal(slots.slots.main.kind, "workspace-file");
      assert.equal(slots.slots.main.manifestPath, payload.manifestPath);
    } finally {
      if (originalLogPath == null) {
        delete process.env.FAKE_ORP_LOG;
      } else {
        process.env.FAKE_ORP_LOG = originalLogPath;
      }
    }
  });
});

test("runWorkspaceAddTab upserts an existing tab and returns the rendered recovery command", async () => {
  await withTempConfigHome(async () => {
    const tempDir = await makeTempDir();
    const manifestPath = path.join(tempDir, "workspace.json");
    await fs.writeFile(manifestPath, `${JSON.stringify(sampleManifest(), null, 2)}\n`, "utf8");

    const { code, stdout } = await captureStdout(() =>
      runWorkspaceAddTab([
        "--workspace-file",
        manifestPath,
        "--path",
        "/Volumes/Code_2TB/code/orp",
        "--resume-tool",
        "codex",
        "--resume-session-id",
        "019d4f24-c8ba-78b2-a726-48b1ce9f0fe9",
        "--json",
      ]),
    );
    const payload = JSON.parse(stdout);
    const saved = JSON.parse(await fs.readFile(manifestPath, "utf8"));

    assert.equal(code, 0);
    assert.equal(payload.action, "add-tab");
    assert.equal(payload.mutation, "updated");
    assert.equal(payload.tabCount, 2);
    assert.equal(payload.tab.resumeCommand, "codex resume 019d4f24-c8ba-78b2-a726-48b1ce9f0fe9");
    assert.equal(
      payload.tab.restartCommand,
      "cd '/Volumes/Code_2TB/code/orp' && codex resume 019d4f24-c8ba-78b2-a726-48b1ce9f0fe9",
    );
    assert.equal(saved.tabs.length, 2);
    assert.equal(saved.tabs[0]?.resumeCommand, "codex resume 019d4f24-c8ba-78b2-a726-48b1ce9f0fe9");
  });
});

test("runWorkspaceAddTab stores same-project sessions under a grouped project object", async () => {
  await withTempConfigHome(async () => {
    const tempDir = await makeTempDir();
    const manifestPath = path.join(tempDir, "workspace.json");
    await fs.writeFile(manifestPath, `${JSON.stringify(sampleManifest(), null, 2)}\n`, "utf8");

    const { code, stdout } = await captureStdout(() =>
      runWorkspaceAddTab([
        "--workspace-file",
        manifestPath,
        "--path",
        "/Volumes/Code_2TB/code/orp",
        "--title",
        "orp second session",
        "--resume-tool",
        "codex",
        "--resume-session-id",
        "019d32d3-d8b2-7fa2-aaec-c74b5134afd6",
        "--append",
        "--json",
      ]),
    );
    const payload = JSON.parse(stdout);
    const saved = JSON.parse(await fs.readFile(manifestPath, "utf8"));

    assert.equal(code, 0);
    assert.equal(payload.action, "add-tab");
    assert.equal(payload.mutation, "added");
    assert.equal(payload.tabCount, 3);
    const orpProject = saved.projects.find((project) => project.path === "/Volumes/Code_2TB/code/orp");
    assert.ok(orpProject);
    assert.equal(orpProject.sessionCount, 2);
    assert.equal(orpProject.sessions[1]?.title, "orp second session");
    assert.equal(orpProject.sessions[1]?.resumeCommand, "codex resume 019d32d3-d8b2-7fa2-aaec-c74b5134afd6");
    assert.equal(saved.tabs.length, 3);
  });
});

test("runWorkspaceRemoveTab updates a local workspace manifest file", async () => {
  await withTempConfigHome(async () => {
    const tempDir = await makeTempDir();
    const manifestPath = path.join(tempDir, "workspace.json");
    await fs.writeFile(manifestPath, `${JSON.stringify(sampleManifest(), null, 2)}\n`, "utf8");

    const { code, stdout } = await captureStdout(() =>
      runWorkspaceRemoveTab([
        "--workspace-file",
        manifestPath,
        "--path",
        "/Volumes/Code_2TB/code/frg-site",
        "--resume-session-id",
        "019d348d-5031-78e1-9840-a66deaac33ae",
        "--json",
      ]),
    );
    const payload = JSON.parse(stdout);
    const saved = JSON.parse(await fs.readFile(manifestPath, "utf8"));

    assert.equal(code, 0);
    assert.equal(payload.action, "remove-tab");
    assert.equal(payload.tabCount, 1);
    assert.equal(payload.removedTabs.length, 1);
    assert.equal(saved.tabs.length, 1);
    assert.equal(saved.tabs[0]?.path, "/Volumes/Code_2TB/code/orp");
  });
});

test("runWorkspaceCreate creates a local managed workspace and auto-assigns main when it is the first one", async () => {
  await withTempConfigHome(async (configHome) => {
    const { code, stdout } = await captureStdout(() =>
      runWorkspaceCreate([
        "main-cody-1",
        "--machine-label",
        "Mac Studio",
        "--path",
        "/Volumes/Code_2TB/code/orp",
        "--remote-url",
        "git@github.com:SproutSeeds/orp.git",
        "--bootstrap-command",
        "npm install",
        "--resume-tool",
        "claude",
        "--resume-session-id",
        "claude-456",
        "--json",
      ]),
    );
    const payload = JSON.parse(stdout);
    const saved = JSON.parse(await fs.readFile(payload.manifestPath, "utf8"));
    const slots = JSON.parse(await fs.readFile(path.join(configHome, "orp", "workspace-slots.json"), "utf8"));

    assert.equal(code, 0);
    assert.equal(payload.action, "create");
    assert.equal(payload.workspaceTitle, "main-cody-1");
    assert.equal(payload.tabCount, 1);
    assert.equal(saved.title, "main-cody-1");
    assert.equal(saved.machine.machineLabel, "Mac Studio");
    assert.equal(saved.tabs[0]?.remoteUrl, "git@github.com:SproutSeeds/orp.git");
    assert.equal(saved.tabs[0]?.bootstrapCommand, "npm install");
    assert.equal(saved.tabs[0]?.resumeCommand, "claude --resume claude-456");
    assert.equal(slots.slots.main.title, "main-cody-1");
  });
});

test("runWorkspaceCreate allows an empty local ledger before any tabs are added", async () => {
  await withTempConfigHome(async () => {
    const { code, stdout } = await captureStdout(() =>
      runWorkspaceCreate([
        "empty-ledger",
        "--json",
      ]),
    );
    const payload = JSON.parse(stdout);
    const saved = JSON.parse(await fs.readFile(payload.manifestPath, "utf8"));

    assert.equal(code, 0);
    assert.equal(payload.workspaceTitle, "empty-ledger");
    assert.equal(payload.tabCount, 0);
    assert.deepEqual(saved.tabs, []);
  });
});
