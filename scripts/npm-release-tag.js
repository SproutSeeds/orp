#!/usr/bin/env node

const version = String(process.argv[2] || "").trim();
const semver = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;
const match = semver.exec(version);

if (!match) {
  console.error("error: expected a valid semantic version");
  process.exit(1);
}

process.stdout.write(match[4] ? "next\n" : "latest\n");
