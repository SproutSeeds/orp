#!/usr/bin/env node

const path = require("path");
const { pathToFileURL } = require("url");
const { spawnSync } = require("child_process");

const cliPath = path.resolve(__dirname, "..", "cli", "orp.py");
const computeCliUrl = pathToFileURL(path.resolve(__dirname, "orp-compute.mjs")).href;
const argv = process.argv.slice(2);

const candidates = [];
if (process.env.ORP_PYTHON && process.env.ORP_PYTHON.trim() !== "") {
  candidates.push(process.env.ORP_PYTHON.trim());
}
if (process.platform === "win32") {
  candidates.push("py");
}
candidates.push("python3", "python");

function isTopLevelHelp(args) {
  return args.length === 0 || args.includes("-h") || args.includes("--help");
}

async function runCompute(args) {
  const mod = await import(computeCliUrl);
  const code = await mod.runComputeCli(args);
  process.exit(code == null ? 0 : code);
}

async function main() {
  if (argv[0] === "compute") {
    await runCompute(argv.slice(1));
    return;
  }

  const captureOutput = isTopLevelHelp(argv);
  let lastErr = null;

  for (const py of candidates) {
    const args = py === "py" ? ["-3", cliPath, ...argv] : [cliPath, ...argv];
    const result = spawnSync(
      py,
      args,
      captureOutput
        ? { encoding: "utf8" }
        : { stdio: "inherit" },
    );

    if (!result.error) {
      if (captureOutput) {
        if (result.stdout) {
          process.stdout.write(result.stdout);
        }
        if (result.stderr) {
          process.stderr.write(result.stderr);
        }
        if (result.status === 0) {
          process.stdout.write("\nAdditional wrapper surface:\n  orp compute -h\n");
        }
      }
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
}

main().catch((error) => {
  console.error(String(error && error.stack ? error.stack : error));
  process.exit(1);
});
