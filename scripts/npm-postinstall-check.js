#!/usr/bin/env node

const { spawnSync } = require("child_process");

function firstAvailable(candidates) {
  for (const cmd of candidates) {
    const probe = spawnSync(cmd, [...(cmd === "py" ? ["-3"] : []), "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"], { encoding: "utf8" });
    if (!probe.error && probe.status === 0) {
      return cmd;
    }
  }
  return null;
}

const pythonCandidates = [process.env.ORP_PYTHON, ...(process.platform === "win32" ? ["py", "python3", "python"] : ["python3", "python"])].filter(Boolean);
const py = firstAvailable(pythonCandidates);

if (!py) {
  console.warn("[orp] Python 3.11 or newer is required. Install it on PATH or set ORP_PYTHON.");
  process.exit(0);
}

const yamlCheckArgs = py === "py" ? ["-3", "-c", "import yaml"] : ["-c", "import yaml"];
const yamlCheck = spawnSync(py, yamlCheckArgs, { encoding: "utf8" });

if (yamlCheck.error || yamlCheck.status !== 0) {
  console.warn("[orp] warning: PyYAML not detected in your Python environment.");
  console.warn(`[orp] install PyYAML in the Python environment selected by ORP_PYTHON or ${py}. See INSTALL.md for a virtual environment setup.`);
}
