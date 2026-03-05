#!/usr/bin/env node

const { spawnSync } = require("child_process");

function firstAvailable(candidates) {
  for (const cmd of candidates) {
    const probe = spawnSync(cmd, ["--version"], { encoding: "utf8" });
    if (!probe.error && probe.status === 0) {
      return cmd;
    }
  }
  return null;
}

const pythonCandidates = process.platform === "win32" ? ["py", "python", "python3"] : ["python3", "python"];
const py = firstAvailable(pythonCandidates);

if (!py) {
  console.warn("[orp] warning: Python 3 not found on PATH.");
  console.warn("[orp] install Python 3 to use the `orp` CLI binary.");
  process.exit(0);
}

const yamlCheckArgs = py === "py" ? ["-3", "-c", "import yaml"] : ["-c", "import yaml"];
const yamlCheck = spawnSync(py, yamlCheckArgs, { encoding: "utf8" });

if (yamlCheck.error || yamlCheck.status !== 0) {
  console.warn("[orp] warning: PyYAML not detected in your Python environment.");
  console.warn("[orp] run: python3 -m pip install pyyaml");
}

