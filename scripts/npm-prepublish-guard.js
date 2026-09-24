#!/usr/bin/env node

const { spawnSync } = require("child_process");
const fs = require("node:fs");

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
    "working tree is not clean. Classify and commit the release scope before publishing so npm and GitHub stay aligned.",
    preview,
  );
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

const main = git(["merge-base", "--is-ancestor", "HEAD", "refs/remotes/origin/main"]);
if (main.status !== 0) fail("release HEAD must be contained in origin/main.");
const pkg = JSON.parse(fs.readFileSync("package.json", "utf8"));
const lock = JSON.parse(fs.readFileSync("package-lock.json", "utf8"));
if (pkg.name !== "open-research-protocol" || lock.name !== pkg.name
    || lock.version !== pkg.version || lock.packages?.[""]?.version !== pkg.version
    || JSON.stringify(pkg.dependencies) !== JSON.stringify(lock.packages?.[""]?.dependencies)) {
  fail("package and lockfile identity, version or dependencies differ.");
}
const head = git(["rev-parse", "HEAD"]);
const tag = git(["rev-parse", `refs/tags/v${pkg.version}^{commit}`]);
if (tag.status !== 0 || tag.stdout.trim() !== head.stdout.trim()) fail("the version tag must point to release HEAD.");
if (process.env.GITHUB_ACTIONS === "true" && process.env.GITHUB_REPOSITORY !== "SproutSeeds/orp") {
  fail("publishing is restricted to the canonical SproutSeeds/orp repository.");
}
