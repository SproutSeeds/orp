#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
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
const before = JSON.parse(run("npm", ["view", pkg.name, "dist-tags", "--json"]));
const spec = `${pkg.name}@${pkg.version}`;
const lookup = spawnSync("npm", ["view", spec, "dist.integrity", "--json"], { encoding: "utf8" });
if (lookup.status !== 0) {
  let error; try { error = JSON.parse(lookup.stdout); } catch {}
  if (error?.error?.code !== "E404") throw new Error("Registry lookup failed; publication stopped");
  run("npm", ["publish", tarball, "--ignore-scripts", "--access", "public", "--provenance", "--tag", channel]);
}
const integrity = JSON.parse(run("npm", ["view", spec, "dist.integrity", "--json"]));
if (integrity !== manifest.integrity) throw new Error("Registry bytes differ from the tested candidate");
const after = JSON.parse(run("npm", ["view", pkg.name, "dist-tags", "--json"]));
if (after[channel] !== pkg.version) throw new Error("Registry channel does not match the candidate");
if (channel === "next" && after.latest !== before.latest) throw new Error("Stable latest unexpectedly changed");
console.log(JSON.stringify({ status:"PASS", package:spec, integrity, channel, distTags:after }, null, 2));
