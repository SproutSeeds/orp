#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import {
  buildOrpComputeGateResult,
  buildOrpComputePacket,
  defineComputePacket,
  defineDecision,
  defineImpactRead,
  definePolicy,
  defineResultBundle,
  defineRung,
  evaluateDispatch,
  runLocalShellPacket,
} from "breakthroughs";

function printHelp() {
  console.log(`ORP compute

Usage:
  orp compute decide --input <path> [--packet-out <path>] [--json]
  orp compute run-local --input <path> --task <path> [--receipt-out <path>] [--packet-out <path>] [--json]

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

function commandLabel(subcommand, options) {
  const parts = ["orp", "compute", subcommand];
  if (options.input) {
    parts.push("--input", options.input);
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
  if (!options.input) {
    throw new Error("compute decide requires --input <path>");
  }

  const context = buildContext(await readJson(options.input));
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
  if (!options.input) {
    throw new Error("compute run-local requires --input <path>");
  }
  if (!options.task) {
    throw new Error("compute run-local requires --task <path>");
  }

  const context = buildContext(await readJson(options.input));
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
