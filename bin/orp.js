#!/usr/bin/env node

const path = require("path");
const { spawnSync } = require("child_process");

const cliPath = path.resolve(__dirname, "..", "cli", "orp.py");
const argv = process.argv.slice(2);

const candidates = [];
if (process.env.ORP_PYTHON && process.env.ORP_PYTHON.trim() !== "") {
  candidates.push(process.env.ORP_PYTHON.trim());
}
if (process.platform === "win32") {
  candidates.push("py");
}
candidates.push("python3", "python");

let lastErr = null;

for (const py of candidates) {
  const args = py === "py" ? ["-3", cliPath, ...argv] : [cliPath, ...argv];
  const result = spawnSync(py, args, { stdio: "inherit" });
  if (!result.error) {
    process.exit(result.status == null ? 1 : result.status);
  }
  if (result.error && result.error.code === "ENOENT") {
    continue;
  }
  lastErr = result.error;
}

console.error("ORP CLI requires Python 3 on PATH.");
console.error("Tried: " + candidates.join(", "));
if (lastErr) {
  console.error(String(lastErr));
}
process.exit(1);

