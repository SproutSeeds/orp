#!/usr/bin/env node

const { spawnSync } = require("child_process");

function git(args) {
  return spawnSync("git", args, { encoding: "utf8" });
}

function fail(message, details = "") {
  console.error(`[orp] prepublish blocked: ${message}`);
  if (details.trim()) {
    console.error(details.trim());
  }
  process.exit(1);
}

const inside = git(["rev-parse", "--is-inside-work-tree"]);
if (inside.error || inside.status !== 0 || inside.stdout.trim() !== "true") {
  fail("npm publish must run from inside a git worktree.");
}

const status = git(["status", "--short"]);
if (status.error || status.status !== 0) {
  fail("unable to inspect git working tree state.", status.stderr || status.stdout);
}

if (status.stdout.trim()) {
  const preview = status.stdout
    .trim()
    .split("\n")
    .slice(0, 10)
    .join("\n");
  fail(
    "working tree is not clean. Commit, stash, or remove local-only files before publishing so npm and GitHub stay aligned.",
    preview,
  );
}

if (process.env.GITHUB_ACTIONS === "true") {
  process.exit(0);
}

const remoteContains = git(["branch", "-r", "--contains", "HEAD"]);
if (remoteContains.error || remoteContains.status !== 0) {
  fail("unable to confirm that HEAD exists on a remote branch.", remoteContains.stderr || remoteContains.stdout);
}

const remoteBranches = remoteContains.stdout
  .split("\n")
  .map((line) => line.trim())
  .filter(Boolean);

if (remoteBranches.length === 0) {
  fail("current HEAD is not present on any remote branch. Push the release commit to GitHub before publishing.");
}
