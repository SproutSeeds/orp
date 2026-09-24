#!/usr/bin/env node
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const root = path.resolve(__dirname, "..");
const python = process.env.ORP_PYTHON || "python3";
const env = { ...process.env, ORP_PYTHON: python, PYTHONDONTWRITEBYTECODE: "1" };
function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, env, stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
run(python, ["-c", "import sys, yaml, jsonschema; assert sys.version_info >= (3, 11), 'Python 3.11+ required'"]);
if (!fs.existsSync(path.join(root, "node_modules/breakthroughs/package.json"))) throw new Error("Run npm ci before testing");
run(python, ["scripts/test-python.py"]);
const tests = fs.readdirSync(path.join(root, "packages")).flatMap((name) => {
  const directory = path.join(root, "packages", name, "test");
  return fs.existsSync(directory) ? fs.readdirSync(directory).filter((file) => file.endsWith(".test.js")).map((file) => path.join(directory, file)) : [];
});
if (!tests.length) throw new Error("Node tests are missing");
run(process.execPath, ["--require", "./tests/guard/node.cjs", "--test", ...tests.sort()]);
run(python, ["scripts/orp-kernel-ci-check.py"]);
