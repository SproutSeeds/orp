import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  buildLaunchPlan,
  buildWorkspaceSyncPreview,
  deriveBaseTitle,
  extractStructuredWorkspaceFromNotes,
  normalizeWorkspaceManifest,
  parseCorePlanNotes,
  parseWorkspaceSource,
  resolveWorkspaceSyncTargetIdeaId,
} from "../src/index.js";
import { extractWorkspaceNarrativeNotes } from "../src/sync.js";

test("parseCorePlanNotes extracts paths and generic resume commands", () => {
  const notes = `
/Volumes/Code_2TB/code/orp-web-app: codex resume 019ce2ee-6083-7d02-9d3a-d27a761132a8
/Volumes/Code_2TB/code/anthropic-lab: claude resume claude-456

/Volumes/Code_2TB/code/care-evidence-support
not a path
`;

  const parsed = parseCorePlanNotes(notes);
  assert.equal(parsed.entries.length, 3);
  assert.deepEqual(
    parsed.entries.map((entry) => ({
      path: entry.path,
      resumeCommand: entry.resumeCommand,
      resumeTool: entry.resumeTool,
      sessionId: entry.sessionId,
    })),
    [
      {
        path: "/Volumes/Code_2TB/code/orp-web-app",
        resumeCommand: "codex resume 019ce2ee-6083-7d02-9d3a-d27a761132a8",
        resumeTool: "codex",
        sessionId: "019ce2ee-6083-7d02-9d3a-d27a761132a8",
      },
      {
        path: "/Volumes/Code_2TB/code/anthropic-lab",
        resumeCommand: "claude resume claude-456",
        resumeTool: "claude",
        sessionId: "claude-456",
      },
      {
        path: "/Volumes/Code_2TB/code/care-evidence-support",
        resumeCommand: null,
        resumeTool: null,
        sessionId: null,
      },
    ],
  );
  assert.equal(parsed.skipped.length, 1);
});

test("parseCorePlanNotes accepts real Claude resume flag syntax", () => {
  const parsed = parseCorePlanNotes(`
/Volumes/Code_2TB/code/anthropic-lab: claude --resume claude-456
`);

  assert.equal(parsed.entries.length, 1);
  assert.equal(parsed.entries[0]?.resumeCommand, "claude --resume claude-456");
  assert.equal(parsed.entries[0]?.resumeTool, "claude");
  assert.equal(parsed.entries[0]?.sessionId, "claude-456");
});

test("buildLaunchPlan keeps duplicate titles unique and preserves exact resume commands", () => {
  const parsed = parseCorePlanNotes(`
/Volumes/Code_2TB/code/collaboration: codex resume abc-123
/Volumes/Code_2TB/code/anthropic-lab: claude resume claude-456
/Volumes/Code_2TB/code/collaboration
`);

  const plan = buildLaunchPlan(parsed.entries, {
    tmux: false,
  });

  assert.equal(plan[0].title, "collaboration");
  assert.equal(plan[1].title, "anthropic-lab");
  assert.equal(plan[2].title, "collaboration (2)");
  assert.equal(plan[0].resumeCommand, "codex resume abc-123");
  assert.equal(plan[1].resumeCommand, "claude resume claude-456");
});

test("structured workspace blocks are extracted from notes", () => {
  const notes = `
Some overview text.

\`\`\`orp-workspace
{
  "version": "1",
  "workspaceId": "workspace-idea",
  "tabs": [
    { "title": "orp", "path": "/Volumes/Code_2TB/code/orp" },
    { "title": "web", "path": "/Volumes/Code_2TB/code/orp-web-app", "resumeCommand": "claude resume claude-456", "resumeTool": "claude", "resumeSessionId": "claude-456" }
  ]
}
\`\`\`
`;
  const manifest = extractStructuredWorkspaceFromNotes(notes);
  const parsed = parseWorkspaceSource({
    sourceType: "hosted-idea",
    sourceLabel: "Workspace idea",
    notes,
  });

  assert.equal(manifest.workspaceId, "workspace-idea");
  assert.equal(parsed.parseMode, "manifest");
  assert.equal(parsed.entries.length, 2);
  assert.equal(parsed.entries[1]?.sessionId, "claude-456");
  assert.equal(parsed.entries[1]?.resumeCommand, "claude resume claude-456");
});

test("normalizeWorkspaceManifest keeps ledger fields and strips nothing important", () => {
  const manifest = normalizeWorkspaceManifest({
    version: "1",
    workspaceId: "terminal-paths",
    title: "Terminal Paths",
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
      },
      {
        title: "lab",
        path: "/Volumes/Code_2TB/code/anthropic-lab",
        remoteUrl: "git@github.com:anthropic/lab.git",
        remoteBranch: "main",
        resumeTool: "claude",
        resumeSessionId: "claude-456",
      },
    ],
  });

  assert.equal(manifest.workspaceId, "terminal-paths");
  assert.equal(manifest.title, "Terminal Paths");
  assert.equal(manifest.machine?.machineLabel, "Mac Studio");
  assert.equal(manifest.tabs[0]?.title, "orp");
  assert.equal(manifest.tabs[0]?.remoteUrl, "git@github.com:SproutSeeds/orp.git");
  assert.equal(manifest.tabs[0]?.bootstrapCommand, "npm install");
  assert.equal(manifest.tabs[1]?.resumeTool, "claude");
  assert.equal(manifest.tabs[1]?.remoteBranch, "main");
});

test("extractWorkspaceNarrativeNotes removes structured workspace blocks and legacy path lines", () => {
  const notes = `
Workspace summary.

/Volumes/Code_2TB/code/orp

\`\`\`orp-workspace
{
  "version": "1",
  "workspaceId": "workspace-demo",
  "tabs": [
    { "path": "/Volumes/Code_2TB/code/orp" }
  ]
}
\`\`\`
`;

  assert.equal(
    extractWorkspaceNarrativeNotes(notes, { stripLegacyWorkspaceLines: true }),
    "Workspace summary.",
  );
});

test("buildWorkspaceSyncPreview converts path notes into a structured workspace block", () => {
  const source = {
    sourceType: "hosted-idea",
    sourceLabel: "Workspace idea",
    title: "Workspace idea",
    notes: `
Workspace summary.

/Volumes/Code_2TB/code/orp: codex resume abc-123
/Volumes/Code_2TB/code/orp-web-app
`,
    idea: { id: "idea-123" },
  };
  const parsed = parseWorkspaceSource(source);
  const preview = buildWorkspaceSyncPreview({
    source,
    parsed,
    targetIdea: {
      id: "idea-123",
      title: "Workspace idea",
      notes: source.notes,
    },
  });

  assert.equal(preview.workspaceId, "idea-idea-123");
  assert.equal(preview.tabs.length, 2);
  assert.equal(preview.tabs[0]?.resumeCommand, "codex resume abc-123");
  assert.equal(preview.tabs[1]?.title, deriveBaseTitle(preview.tabs[1]));
  assert.match(preview.nextNotes, /```orp-workspace/);
  assert.match(preview.nextNotes, /"workspaceId": "idea-idea-123"/);
  assert.match(preview.nextNotes, /Workspace summary\./);
  assert.match(preview.nextNotes, /\/Volumes\/Code_2TB\/code\/orp: codex resume abc-123/);
  assert.match(preview.nextNotes, /\/Volumes\/Code_2TB\/code\/orp-web-app/);
});

test("buildWorkspaceSyncPreview strips stale legacy path lines when syncing from a workspace file", () => {
  const source = {
    sourceType: "workspace-file",
    sourceLabel: "/tmp/workspace.json",
    sourcePath: "/tmp/workspace.json",
    title: "Workspace idea",
    notes: "",
    workspaceManifest: {
      version: "1",
      workspaceId: "workspace-file-demo",
      tabs: [{ title: "orp", path: "/Volumes/Code_2TB/code/orp" }],
    },
  };
  const parsed = parseWorkspaceSource(source);
  const preview = buildWorkspaceSyncPreview({
    source,
    parsed,
    targetIdea: {
      id: "idea-123",
      title: "Workspace idea",
      notes: `
Workspace summary.

/Volumes/Code_2TB/code/orp: codex resume stale-session
`,
    },
  });

  assert.match(preview.nextNotes, /Workspace summary\./);
  assert.match(preview.nextNotes, /```orp-workspace/);
  assert.doesNotMatch(preview.nextNotes, /stale-session/);
  assert.doesNotMatch(preview.nextNotes, /\/Volumes\/Code_2TB\/code\/orp: codex resume/);
});

test("buildWorkspaceSyncPreview enriches workspace-file tabs with linked ORP project context", async () => {
  const projectRoot = await fs.mkdtemp(path.join(os.tmpdir(), "orp-workspace-sync-frontier-"));
  await fs.mkdir(path.join(projectRoot, ".git", "orp", "link"), { recursive: true });
  await fs.writeFile(
    path.join(projectRoot, ".git", "orp", "link", "project.json"),
    JSON.stringify(
      {
        idea_id: "idea-linked",
        active_feature_id: "feature-active",
        project_root: projectRoot,
      },
      null,
      2,
    ),
    "utf8",
  );
  const source = {
    sourceType: "workspace-file",
    sourceLabel: "/tmp/workspace.json",
    sourcePath: "/tmp/workspace.json",
    title: "Workspace idea",
    notes: "",
    workspaceManifest: {
      version: "1",
      workspaceId: "workspace-file-demo",
      tabs: [{ title: "Linked project", path: projectRoot }],
    },
  };
  const parsed = parseWorkspaceSource(source);
  const preview = buildWorkspaceSyncPreview({
    source,
    parsed,
    targetIdea: {
      id: "idea-123",
      title: "Workspace idea",
      notes: "",
    },
  });

  assert.equal(preview.tabs[0]?.linkedIdeaId, "idea-linked");
  assert.equal(preview.tabs[0]?.linkedFeatureId, "feature-active");
  assert.match(preview.nextNotes, /"linkedIdeaId": "idea-linked"/);
  assert.match(preview.nextNotes, /"linkedFeatureId": "feature-active"/);
});

test("resolveWorkspaceSyncTargetIdeaId supports hosted idea and hosted workspace sources", () => {
  assert.equal(
    resolveWorkspaceSyncTargetIdeaId({
      sourceType: "hosted-idea",
      idea: { id: "idea-123" },
    }),
    "idea-123",
  );

  assert.equal(
    resolveWorkspaceSyncTargetIdeaId({
      sourceType: "hosted-workspace",
      hostedWorkspace: {
        linkedIdea: {
          ideaId: "idea-456",
        },
      },
    }),
    "idea-456",
  );
});
