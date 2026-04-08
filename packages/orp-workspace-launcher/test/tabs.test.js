import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { buildWorkspaceTabsReport, parseWorkspaceSource, parseWorkspaceTabsArgs, runWorkspaceTabs } from "../src/index.js";

async function makeTempDir() {
  return fs.mkdtemp(path.join(os.tmpdir(), "orp-workspace-tabs-"));
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

test("parseWorkspaceTabsArgs accepts JSON and workspace selectors", () => {
  const parsed = parseWorkspaceTabsArgs([
    "--workspace-file",
    "/tmp/workspace.json",
    "--json",
  ]);

  assert.equal(parsed.workspaceFile, "/tmp/workspace.json");
  assert.equal(parsed.json, true);
  assert.throws(() => parseWorkspaceTabsArgs(["idea-123", "idea-456"]), /unexpected argument/);
  assert.throws(() => parseWorkspaceTabsArgs(["--wat"]), /missing value|unknown option/);
});

test("buildWorkspaceTabsReport keeps duplicate titles unique and exposes generic resume metadata", () => {
  const parsed = parseWorkspaceSource({
    sourceType: "hosted-idea",
    sourceLabel: "Workspace idea",
    title: "Workspace idea",
    workspaceManifest: {
      version: "1",
      workspaceId: "workspace-idea",
      machine: {
        machineId: "mac-studio:darwin",
        machineLabel: "Mac Studio",
        platform: "darwin",
      },
      tabs: [
        {
          path: "/Volumes/Code_2TB/code/collaboration",
          title: "collaboration",
          remoteUrl: "git@github.com:org/collaboration.git",
          bootstrapCommand: "npm install",
          resumeCommand: "codex resume abc-123",
        },
        {
          path: "/Volumes/Code_2TB/code/anthropic-lab",
          title: "anthropic-lab",
          remoteUrl: "git@github.com:anthropic/anthropic-lab.git",
          remoteBranch: "main",
          resumeCommand: "claude resume claude-456",
        },
        {
          path: "/Volumes/Code_2TB/code/collaboration",
        },
      ],
    },
    notes: "",
  });

  const report = buildWorkspaceTabsReport(
    {
      sourceType: "hosted-idea",
      sourceLabel: "Workspace idea",
      title: "Workspace idea",
    },
    parsed,
  );

  assert.equal(report.workspaceId, "workspace-idea");
  assert.equal(report.machine?.machineLabel, "Mac Studio");
  assert.equal(report.tabCount, 3);
  assert.equal(report.tabs[0]?.title, "collaboration");
  assert.equal(report.tabs[0]?.remoteUrl, "git@github.com:org/collaboration.git");
  assert.equal(report.tabs[0]?.bootstrapCommand, "npm install");
  assert.equal(report.tabs[0]?.cloneCommand, "git clone 'git@github.com:org/collaboration.git' 'collaboration'");
  assert.equal(
    report.tabs[0]?.setupCommand,
    "git clone 'git@github.com:org/collaboration.git' 'collaboration' && cd 'collaboration' && npm install",
  );
  assert.equal(report.tabs[0]?.resumeCommand, "codex resume abc-123");
  assert.equal(
    report.tabs[0]?.restartCommand,
    "cd '/Volumes/Code_2TB/code/collaboration' && codex resume abc-123",
  );
  assert.equal(report.tabs[0]?.codexSessionId, "abc-123");
  assert.equal(report.tabs[1]?.title, "anthropic-lab");
  assert.equal(report.tabs[1]?.resumeCommand, "claude resume claude-456");
  assert.equal(report.tabs[1]?.remoteBranch, "main");
  assert.equal(
    report.tabs[1]?.restartCommand,
    "cd '/Volumes/Code_2TB/code/anthropic-lab' && claude resume claude-456",
  );
  assert.equal(report.tabs[1]?.claudeSessionId, "claude-456");
  assert.equal(report.tabs[2]?.title, "collaboration (2)");
  assert.equal(report.tabs[2]?.codexSessionId, null);
});

test("runWorkspaceTabs prints JSON without launch commands", async () => {
  const tempDir = await makeTempDir();
  const manifestPath = path.join(tempDir, "workspace.json");
  await fs.writeFile(
    manifestPath,
    `${JSON.stringify(
      {
        version: "1",
        workspaceId: "orp-main",
        title: "ORP Main",
        machine: {
          machineId: "mac-studio:darwin",
          machineLabel: "Mac Studio",
          platform: "darwin",
        },
        tabs: [
          {
            title: "orp",
            path: "/Volumes/Code_2TB/code/orp",
            remoteUrl: "git@github.com:SproutSeeds/orp.git",
            bootstrapCommand: "npm install",
            resumeCommand: "claude resume claude-999",
            resumeTool: "claude",
            resumeSessionId: "claude-999",
          },
          {
            title: "web",
            path: "/Volumes/Code_2TB/code/orp-web-app",
          },
        ],
      },
      null,
      2,
    )}\n`,
    "utf8",
  );

  const { code, stdout } = await captureStdout(() => runWorkspaceTabs(["--workspace-file", manifestPath, "--json"]));
  const parsed = JSON.parse(stdout);

  assert.equal(code, 0);
  assert.equal(parsed.workspaceId, "orp-main");
  assert.equal(parsed.machine.machineLabel, "Mac Studio");
  assert.equal(parsed.tabCount, 2);
  assert.equal(parsed.tabs[0]?.title, "orp");
  assert.equal(parsed.tabs[0]?.remoteUrl, "git@github.com:SproutSeeds/orp.git");
  assert.equal(parsed.tabs[0]?.bootstrapCommand, "npm install");
  assert.equal(parsed.tabs[0]?.resumeCommand, "claude resume claude-999");
  assert.equal(parsed.tabs[0]?.restartCommand, "cd '/Volumes/Code_2TB/code/orp' && claude resume claude-999");
  assert.equal(parsed.tabs[0]?.claudeSessionId, "claude-999");
  assert.equal(parsed.tabs[1]?.title, "web");
  assert.ok(!stdout.includes('"command"'));
});

test("buildWorkspaceTabsReport canonicalizes Claude resume commands from tool and session metadata", () => {
  const parsed = parseWorkspaceSource({
    sourceType: "workspace-file",
    sourceLabel: "/tmp/workspace.json",
    title: "workspace",
    workspaceManifest: {
      version: "1",
      workspaceId: "orp-main",
      tabs: [
        {
          title: "anthropic-lab",
          path: "/Volumes/Code_2TB/code/anthropic-lab",
          remoteUrl: "git@github.com:anthropic/anthropic-lab.git",
          resumeTool: "claude",
          resumeSessionId: "claude-456",
        },
      ],
    },
    notes: "",
  });

  const report = buildWorkspaceTabsReport(
    {
      sourceType: "workspace-file",
      sourceLabel: "/tmp/workspace.json",
      title: "workspace",
    },
    parsed,
  );

  assert.equal(report.tabs[0]?.resumeCommand, "claude --resume claude-456");
  assert.equal(report.tabs[0]?.cloneCommand, "git clone 'git@github.com:anthropic/anthropic-lab.git' 'anthropic-lab'");
  assert.equal(
    report.tabs[0]?.restartCommand,
    "cd '/Volumes/Code_2TB/code/anthropic-lab' && claude --resume claude-456",
  );
  assert.equal(report.tabs[0]?.claudeSessionId, "claude-456");
});
