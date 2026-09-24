#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { waitForPublishedCandidate } = require("./npm-registry-readback");
const directory = path.resolve(process.argv[2]);
const manifestPath = path.join(directory, "manifest.json");
const manifest = JSON.parse(fs.readFileSync(manifestPath))[0];
const pkg = require("../package.json");
const tarball = path.join(directory, manifest.filename);
const installed = JSON.parse(fs.readFileSync(path.join(directory, "installed.json")));
if (manifest.name !== pkg.name || manifest.version !== pkg.version || installed.status !== "PASS"
    || installed.tarball_sha512 !== require("node:crypto").createHash("sha512").update(fs.readFileSync(tarball)).digest("hex")) {
  throw new Error("Candidate identity or installed verification differs");
}
function run(command, args) {
  const result = spawnSync(command, args, { encoding: "utf8" });
  if (result.error || result.status !== 0) throw new Error(result.stderr || result.error?.message || "Command failed");
  return result.stdout.trim();
}
run(process.execPath, [path.join(__dirname, "verify-package.js"), manifestPath, tarball]);
const channel = run(process.execPath, [path.join(__dirname, "npm-release-tag.js"), pkg.version]);
const before = JSON.parse(run("npm", ["view", pkg.name, "dist-tags", "--json", "--prefer-online"]));
const spec = `${pkg.name}@${pkg.version}`;
function readIntegrity() {
  const lookup = spawnSync("npm", ["view", spec, "dist.integrity", "--json", "--prefer-online"], { encoding: "utf8" });
  if (lookup.status !== 0) {
    let error; try { error = JSON.parse(lookup.stdout); } catch {}
    if (error?.error?.code !== "E404") throw new Error("Registry lookup failed; publication stopped");
    return null;
  }
  return JSON.parse(lookup.stdout);
}
async function publish() {
  if (readIntegrity() === null) {
    run("npm", ["publish", tarball, "--ignore-scripts", "--access", "public", "--provenance", "--tag", channel]);
    console.log("Publication accepted; waiting for registry visibility and release channel.");
  }
  const result = await waitForPublishedCandidate({
    integrity: manifest.integrity, version: pkg.version, channel, previousLatest: before.latest,
    read() {
      const integrity = readIntegrity();
      if (integrity === null) return null;
      const tags = JSON.parse(run("npm", ["view", pkg.name, "dist-tags", "--json", "--prefer-online"]));
      return { integrity, tags };
    },
  });
  console.log(JSON.stringify({ status:"PASS", package:spec, integrity:result.integrity, channel, distTags:result.tags }, null, 2));
}
publish().catch((error) => { console.error(error.message); process.exitCode = 1; });
