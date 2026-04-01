import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  buildWorkspaceCommandsReport,
  parseWorkspaceCommandsArgs,
  parseWorkspaceSource,
  runWorkspaceCommands,
} from "../src/index.js";

async function makeTempDir() {
  return fs.mkdtemp(path.join(os.tmpdir(), "orp-workspace-commands-"));
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

test("parseWorkspaceCommandsArgs accepts JSON and workspace selectors", () => {
  const parsed = parseWorkspaceCommandsArgs([
    "--workspace-file",
    "/tmp/workspace.json",
    "--json",
  ]);

  assert.equal(parsed.workspaceFile, "/tmp/workspace.json");
  assert.equal(parsed.json, true);
  assert.throws(() => parseWorkspaceCommandsArgs(["idea-123", "idea-456"]), /unexpected argument/);
  assert.throws(() => parseWorkspaceCommandsArgs(["--wat"]), /missing value|unknown option/);
});

test("buildWorkspaceCommandsReport exposes direct restart commands and exact saved resume commands", () => {
  const parsed = parseWorkspaceSource({
    sourceType: "hosted-idea",
    sourceLabel: "Workspace idea",
    title: "Workspace idea",
    notes: `
/Volumes/Code_2TB/code/collaboration: codex resume abc-123
/Volumes/Code_2TB/code/anthropic-lab: claude resume claude-456
/Volumes/Code_2TB/code/collaboration
`,
  });

  const report = buildWorkspaceCommandsReport(
    {
      sourceType: "hosted-idea",
      sourceLabel: "Workspace idea",
      title: "Workspace idea",
    },
    parsed,
  );

  assert.equal(report.commandCount, 3);
  assert.equal(report.tabs[0]?.resumeCommand, "codex resume abc-123");
  assert.equal(report.tabs[0]?.restartCommand, "cd '/Volumes/Code_2TB/code/collaboration' && codex resume abc-123");
  assert.equal(report.tabs[1]?.resumeCommand, "claude resume claude-456");
  assert.equal(
    report.tabs[1]?.restartCommand,
    "cd '/Volumes/Code_2TB/code/anthropic-lab' && claude resume claude-456",
  );
  assert.equal(report.tabs[2]?.restartCommand, "cd '/Volumes/Code_2TB/code/collaboration'");
});

test("runWorkspaceCommands prints JSON with copyable commands", async () => {
  const tempDir = await makeTempDir();
  const manifestPath = path.join(tempDir, "workspace.json");
  await fs.writeFile(
    manifestPath,
    `${JSON.stringify(
      {
        version: "1",
        workspaceId: "orp-main",
        title: "ORP Main",
        tabs: [
          {
            title: "orp",
            path: "/Volumes/Code_2TB/code/orp",
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

  const { code, stdout } = await captureStdout(() =>
    runWorkspaceCommands(["--workspace-file", manifestPath, "--json"]),
  );
  const parsed = JSON.parse(stdout);

  assert.equal(code, 0);
  assert.equal(parsed.workspaceId, "orp-main");
  assert.equal(parsed.commandCount, 2);
  assert.equal(parsed.tabs[0]?.resumeCommand, "claude resume claude-999");
  assert.equal(parsed.tabs[0]?.claudeSessionId, "claude-999");
  assert.equal(parsed.tabs[0]?.restartCommand, "cd '/Volumes/Code_2TB/code/orp' && claude resume claude-999");
  assert.equal(parsed.tabs[1]?.restartCommand, "cd '/Volumes/Code_2TB/code/orp-web-app'");
});

test("buildWorkspaceCommandsReport canonicalizes Claude restart commands from tool and session metadata", () => {
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
          resumeTool: "claude",
          resumeSessionId: "claude-456",
        },
      ],
      notes: "",
    },
    notes: "",
  });

  const report = buildWorkspaceCommandsReport(
    {
      sourceType: "workspace-file",
      sourceLabel: "/tmp/workspace.json",
      title: "workspace",
    },
    parsed,
  );

  assert.equal(report.tabs[0]?.resumeCommand, "claude --resume claude-456");
  assert.equal(
    report.tabs[0]?.restartCommand,
    "cd '/Volumes/Code_2TB/code/anthropic-lab' && claude --resume claude-456",
  );
});
