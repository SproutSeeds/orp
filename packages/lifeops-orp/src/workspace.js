import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

function withJsonFlag(args = []) {
  return args.includes("--json") ? args : [...args, "--json"];
}

function normalizeCommandError(error) {
  if (error instanceof Error) {
    return error;
  }
  return new Error(String(error));
}

export async function runOrpJson({
  repoRoot,
  args = [],
  orpCommand = "orp",
} = {}) {
  if (!repoRoot) {
    throw new Error("runOrpJson requires a repoRoot.");
  }

  const result = await execFileAsync(orpCommand, withJsonFlag(args), {
    cwd: repoRoot,
    env: process.env,
    maxBuffer: 8 * 1024 * 1024,
  });

  const stdout = String(result.stdout ?? "").trim();
  if (!stdout) {
    throw new Error(`ORP command returned no JSON output: ${args.join(" ")}`);
  }

  try {
    return JSON.parse(stdout);
  } catch (error) {
    throw new Error(
      `Failed to parse ORP JSON output for "${args.join(" ")}": ${
        normalizeCommandError(error).message
      }`,
    );
  }
}

async function tryCommand(commandRunner, input) {
  try {
    return await commandRunner(input);
  } catch {
    return null;
  }
}

export async function collectOrpWorkspace({
  repoRoot,
  orpCommand = "orp",
  includeAbout = true,
  commandRunner,
} = {}) {
  if (!repoRoot) {
    throw new Error("collectOrpWorkspace requires a repoRoot.");
  }

  const runner =
    commandRunner ??
    ((input) =>
      runOrpJson({
        repoRoot: input.repoRoot,
        args: input.args,
        orpCommand,
      }));

  const status = await runner({
    repoRoot,
    args: ["status"],
  });

  const frontierState = await tryCommand(runner, {
    repoRoot,
    args: ["frontier", "state"],
  });
  const frontierRoadmap = await tryCommand(runner, {
    repoRoot,
    args: ["frontier", "roadmap"],
  });
  const frontierChecklist = await tryCommand(runner, {
    repoRoot,
    args: ["frontier", "checklist"],
  });
  const about = includeAbout
    ? await tryCommand(runner, {
        repoRoot,
        args: ["about"],
      })
    : null;

  return {
    repoRoot,
    status,
    frontierState,
    frontierRoadmap,
    frontierChecklist,
    about,
    collectedAt: new Date().toISOString(),
  };
}
