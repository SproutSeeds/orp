#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import {
  buildComputePointDecisionPacket,
  buildOrpComputeGateResult,
  buildOrpComputePacket,
  defineComputePacket,
  defineDecision,
  defineImpactRead,
  definePolicy,
  defineProjectComputeMap,
  defineResultBundle,
  defineRung,
  evaluateDispatch,
  runLocalShellPacket,
} from "breakthroughs";

function printHelp() {
  console.log(`ORP compute

Usage:
  orp compute decide --input <path> [--packet-out <path>] [--json]
  orp compute decide --project-map <path> --point-id <id> [--rung-id <id>] [--success-bar <path>] [--packet-out <path>] [--json]
  orp compute run-local --input <path> --task <path> [--receipt-out <path>] [--packet-out <path>] [--json]
  orp compute run-local --project-map <path> --point-id <id> --task <path> [--rung-id <id>] [--success-bar <path>] [--receipt-out <path>] [--packet-out <path>] [--json]

Input JSON shape:
  {
    "decision": { ... },
    "rung": { ... },
    "policy": { ... },
    "packet": { ... },
    "repo": {
      "rootPath": "/abs/path",
      "git": { "branch": "main", "commit": "abc123" }
    },
    "orp": {
      "boardId": "targeted_compute",
      "problemId": "adult-vs-developmental-rgc",
      "artifactRoot": "orp/artifacts"
    }
  }

Project-map mode:
  {
    "projectId": "longevity-controller",
    "repoRoots": ["/abs/path"],
    "rungs": [...],
    "defaultPolicy": {...},
    "computePoints": [...]
  }

Project-map mode options:
- --project-map <path> points to a repo compute catalog
- --point-id <id> selects the compute point
- --rung-id <id> optionally overrides the point default rung
- --success-bar <path> optionally points to a JSON object merged into the packet success bar
- repo/orp context is derived from the project map unless overridden with --repo-root, --board-id, --problem-id, or --artifact-root

Task JSON shape for run-local:
  {
    "command": "node",
    "args": ["-e", "console.log('hello')"],
    "cwd": "/abs/path",
    "timeoutMs": 30000,
    "env": {}
  }

Policy semantics:
- local admitted rungs can resolve to run_local
- paid admitted rungs resolve to request_paid_approval unless the rung is explicitly approved in policy.paid.approvedRungs
`);
}

function parseArgs(argv) {
  const options = {
    json: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];

    if (arg === "--json") {
      options.json = true;
      continue;
    }
    if (arg === "-h" || arg === "--help") {
      options.help = true;
      continue;
    }
    if (arg.startsWith("--")) {
      const key = arg.slice(2).replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
      const value = argv[i + 1];
      if (value == null || value.startsWith("--")) {
        throw new Error(`missing value for ${arg}`);
      }
      options[key] = value;
      i += 1;
      continue;
    }

    if (!options.command) {
      options.command = arg;
    } else {
      throw new Error(`unexpected argument: ${arg}`);
    }
  }

  return options;
}

async function readJson(filePath) {
  const raw = await fs.readFile(filePath, "utf8");
  return JSON.parse(raw);
}

async function writeJson(filePath, payload) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

function buildContext(raw) {
  if (!raw || typeof raw !== "object") {
    throw new Error("input must be a JSON object");
  }

  return {
    raw,
    decision: defineDecision(raw.decision),
    rung: defineRung(raw.rung),
    policy: definePolicy(raw.policy),
    packet: defineComputePacket(raw.packet),
  };
}

async function loadContext(options) {
  if (options.input && options.projectMap) {
    throw new Error("use either --input or --project-map, not both");
  }

  if (options.projectMap) {
    if (!options.pointId) {
      throw new Error("project-map mode requires --point-id <id>");
    }

    const projectMap = defineProjectComputeMap(await readJson(options.projectMap));
    const successBar = options.successBar
      ? await readJson(options.successBar)
      : undefined;
    const template = buildComputePointDecisionPacket({
      projectComputeMap: projectMap,
      pointId: options.pointId,
      rungId: options.rungId,
      successBar,
    });

    return {
      raw: {
        projectMap,
        repo: {
          rootPath: options.repoRoot || projectMap.repoRoots[0] || process.cwd(),
        },
        orp: {
          boardId: options.boardId || "targeted_compute",
          problemId: options.problemId || template.computePoint.id,
          artifactRoot:
            options.artifactRoot ||
            `orp/artifacts/compute/${template.computePoint.id}`,
        },
      },
      projectMap,
      computePoint: template.computePoint,
      decision: template.decision,
      rung: template.rung,
      policy: template.policy,
      packet: template.packet,
    };
  }

  if (!options.input) {
    throw new Error("compute command requires --input <path> or --project-map <path>");
  }

  return buildContext(await readJson(options.input));
}

function commandLabel(subcommand, options) {
  const parts = ["orp", "compute", subcommand];
  if (options.input) {
    parts.push("--input", options.input);
  }
  if (options.projectMap) {
    parts.push("--project-map", options.projectMap);
  }
  if (options.pointId) {
    parts.push("--point-id", options.pointId);
  }
  if (options.rungId) {
    parts.push("--rung-id", options.rungId);
  }
  if (options.task) {
    parts.push("--task", options.task);
  }
  return parts.join(" ");
}

function gateStatusForDispatch(action) {
  if (action === "hold_packet") {
    return "fail";
  }
  if (action === "request_paid_approval") {
    return "hold";
  }
  return "pass";
}

function summarizeDispatch(dispatchResult) {
  if (dispatchResult.action === "request_paid_approval") {
    return `compute packet requires explicit paid approval for rung ${dispatchResult.rungId}`;
  }
  if (dispatchResult.action === "hold_packet") {
    return `compute packet is being held because ${dispatchResult.reason}`;
  }
  return `compute packet admitted with action ${dispatchResult.action}`;
}

async function runDecide(options) {
  const context = await loadContext(options);
  const dispatchResult = evaluateDispatch(context);
  const gateResult = buildOrpComputeGateResult({
    gateId: context.packet.rungId,
    command: commandLabel("decide", options),
    status: gateStatusForDispatch(dispatchResult.action),
    evidenceNote: summarizeDispatch(dispatchResult),
  });

  const payload = {
    ok: dispatchResult.action !== "hold_packet",
    command: "compute decide",
    dispatch_result: dispatchResult,
    gate_result: gateResult,
  };

  if (options.packetOut) {
    const orpPacket = buildOrpComputePacket({
      repoRoot: context.raw.repo?.rootPath || process.cwd(),
      repoGit: context.raw.repo?.git,
      decision: context.decision,
      packet: context.packet,
      dispatchResult,
      gateResults: [gateResult],
      artifactRoot: context.raw.orp?.artifactRoot,
      boardId: context.raw.orp?.boardId,
      problemId: context.raw.orp?.problemId,
      stateNote: summarizeDispatch(dispatchResult),
    });
    await writeJson(options.packetOut, orpPacket);
    payload.orp_packet_path = path.resolve(options.packetOut);
  }

  if (options.json) {
    console.log(JSON.stringify(payload, null, 2));
  } else {
    console.log(`${dispatchResult.action}: ${summarizeDispatch(dispatchResult)}`);
  }

  return dispatchResult.action === "hold_packet" ? 1 : 0;
}

async function runLocal(options) {
  if (!options.task) {
    throw new Error("compute run-local requires --task <path>");
  }

  const context = await loadContext(options);
  const task = await readJson(options.task);
  const dispatchResult = evaluateDispatch(context);

  if (dispatchResult.action !== "run_local") {
    const message = `compute packet is not locally runnable; dispatch action is ${dispatchResult.action}`;
    if (options.json) {
      console.log(JSON.stringify({ ok: false, error: message, dispatch_result: dispatchResult }, null, 2));
    } else {
      console.error(message);
    }
    return 1;
  }

  const executionReceipt = await runLocalShellPacket({
    decision: context.decision,
    rung: context.rung,
    packet: context.packet,
    dispatchResult,
    task,
  });

  const gateResult = buildOrpComputeGateResult({
    gateId: context.packet.rungId,
    command: `${executionReceipt.command} ${executionReceipt.args.join(" ")}`.trim(),
    status: executionReceipt.status === "pass" ? "pass" : "fail",
    exitCode: executionReceipt.exitCode == null ? 1 : executionReceipt.exitCode,
    durationMs: executionReceipt.durationMs,
    evidenceNote: `local shell execution completed with status ${executionReceipt.status}`,
  });

  const resultBundle = defineResultBundle({
    id: `${context.packet.id}-result`,
    packetId: context.packet.id,
    outputs: context.packet.requiredOutputs,
    status: executionReceipt.status,
    metrics: {
      exitCode: executionReceipt.exitCode,
      durationMs: executionReceipt.durationMs,
      timedOut: executionReceipt.timedOut,
    },
  });

  const impactRead = defineImpactRead({
    id: `${context.packet.id}-impact`,
    bundleId: resultBundle.id,
    nextAction: executionReceipt.status === "pass" ? "review_result_bundle" : "reroute_or_debug",
    summary:
      executionReceipt.status === "pass"
        ? `local compute packet ${context.packet.id} completed successfully`
        : `local compute packet ${context.packet.id} failed and needs follow-up`,
  });

  const payload = {
    ok: executionReceipt.status === "pass",
    command: "compute run-local",
    dispatch_result: dispatchResult,
    execution_receipt: executionReceipt,
    gate_result: gateResult,
    result_bundle: resultBundle,
    impact_read: impactRead,
  };

  if (options.receiptOut) {
    await writeJson(options.receiptOut, executionReceipt);
    payload.execution_receipt_path = path.resolve(options.receiptOut);
  }

  if (options.packetOut) {
    const orpPacket = buildOrpComputePacket({
      repoRoot: context.raw.repo?.rootPath || process.cwd(),
      repoGit: context.raw.repo?.git,
      decision: context.decision,
      packet: context.packet,
      dispatchResult,
      resultBundle,
      impactRead,
      gateResults: [gateResult],
      artifactRoot: context.raw.orp?.artifactRoot,
      boardId: context.raw.orp?.boardId,
      problemId: context.raw.orp?.problemId,
      extraPaths: options.receiptOut ? [path.resolve(options.receiptOut)] : [],
      stateNote: impactRead.summary,
    });
    await writeJson(options.packetOut, orpPacket);
    payload.orp_packet_path = path.resolve(options.packetOut);
  }

  if (options.json) {
    console.log(JSON.stringify(payload, null, 2));
  } else {
    console.log(`${executionReceipt.status}: ${impactRead.summary}`);
  }

  if (executionReceipt.exitCode == null) {
    return 1;
  }
  return executionReceipt.exitCode;
}

export async function runComputeCli(argv = process.argv.slice(2)) {
  let options;
  try {
    options = parseArgs(argv);
  } catch (error) {
    console.error(String(error.message || error));
    printHelp();
    return 1;
  }

  if (options.help || !options.command) {
    printHelp();
    return 0;
  }

  try {
    if (options.command === "decide") {
      return await runDecide(options);
    }
    if (options.command === "run-local") {
      return await runLocal(options);
    }
    throw new Error(`unknown compute command: ${options.command}`);
  } catch (error) {
    if (options.json) {
      console.log(JSON.stringify({ ok: false, error: String(error.message || error) }, null, 2));
    } else {
      console.error(String(error.message || error));
    }
    return 1;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const code = await runComputeCli(process.argv.slice(2));
  process.exit(code == null ? 0 : code);
}
