import test from "node:test";
import assert from "node:assert/strict";

import { runOrpWorkspaceCommand } from "../src/index.js";

async function captureStdout(fn) {
  const chunks = [];
  const originalWrite = process.stdout.write;
  process.stdout.write = (chunk, encoding, callback) => {
    chunks.push(typeof chunk === "string" ? chunk : chunk.toString(encoding || "utf8"));
    if (typeof callback === "function") {
      callback();
    }
    return true;
  };

  try {
    const code = await fn();
    return {
      code,
      stdout: chunks.join(""),
    };
  } finally {
    process.stdout.write = originalWrite;
  }
}

test("runOrpWorkspaceCommand shows the ledger-first help surface", async () => {
  const { code, stdout } = await captureStdout(() => runOrpWorkspaceCommand(["-h"]));

  assert.equal(code, 0);
  assert.match(stdout, /orp workspace ledger <name-or-id>/);
  assert.match(stdout, /orp workspace ledger add <name-or-id>/);
  assert.match(stdout, /orp workspace ledger remove <name-or-id>/);
  assert.match(stdout, /orp workspace tabs <name-or-id>/);
});

test("runOrpWorkspaceCommand routes ledger help to the tabs help surface", async () => {
  const { code, stdout } = await captureStdout(() => runOrpWorkspaceCommand(["ledger", "-h"]));

  assert.equal(code, 0);
  assert.match(stdout, /ORP workspace tabs/);
  assert.match(stdout, /copyable and includes the saved `cd \.\.\. && resume \.\.\.` recovery command/);
});
