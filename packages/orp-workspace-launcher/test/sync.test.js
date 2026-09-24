import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { buildHostedWorkspaceState, workspacePayloadSha256, verifyHostedWorkspaceReadback } from "../src/hosted-state.js";
import { runWorkspaceSync } from "../src/sync.js";

const manifest = { version: "1", workspaceId: "release", title: "release", tabs: [{ title: "Example", path: "/synthetic/project" }] };
const destination = { base_url: "https://example.com", user_id: "user-fixture", workspace_id: "release", idea_id: "idea-fixture", title: "release" };

test("published v2 golden projections and semantic hashes remain consistent", async () => {
  const fixtures = JSON.parse(await fs.readFile(new URL("../../../tests/fixtures/hosted-workspace-v2.json", import.meta.url)));
  for (const item of fixtures.valid) {
    const actual = buildHostedWorkspaceState(item.manifest, item.options);
    assert.deepEqual(actual, item.state, item.name);
    assert.equal(workspacePayloadSha256(actual), item.payload_sha256, item.name);
  }
});

test("approval is stable over time and binds all content, order, version, policy and destination", () => {
  const options = { destination, syncAllowlist: ["workspace.summary", "workspace.current_focus", "workspace.trajectory", "tabs.activity", "tabs.title"], summary: "Ready", currentFocus: "Verify", trajectory: "Release" };
  const first = buildHostedWorkspaceState(manifest, { ...options, capturedAt: "2026-01-01T00:00:00Z" });
  const later = buildHostedWorkspaceState(manifest, { ...options, capturedAt: "2026-09-23T00:00:00Z" });
  assert.equal(first.snapshot_id, later.snapshot_id);
  assert.equal(workspacePayloadSha256(first), workspacePayloadSha256(later));
  assert.equal(first.tabs[0].last_synced_at_utc, undefined);
  for (const changed of [{ summary: "Changed" }, { currentFocus: "Changed" }, { trajectory: "Changed" },
    { destination: { ...destination, user_id: "other" } }, { destination: { ...destination, base_url: "https://other.example.com" } },
    { destination: { ...destination, idea_id: "other" } }, { syncAllowlist: [] },
    { previousWorkspace: { state: { state_version: 1 } } }]) {
    assert.notEqual(first.snapshot_id, buildHostedWorkspaceState(manifest, { ...options, ...changed }).snapshot_id);
  }
  const activity = structuredClone(manifest);
  activity.tabs[0].lastActivityAt = "2026-09-23T00:00:00Z";
  assert.notEqual(first.snapshot_id, buildHostedWorkspaceState(activity, options).snapshot_id);
  const retry = buildHostedWorkspaceState(manifest, { ...options, confirm: first.snapshot_id, previousWorkspace: { state: first } });
  assert.equal(retry.snapshot_id, first.snapshot_id);
  assert.equal(retry.state_version, 1);
  const reordered = { ...manifest, tabs: [manifest.tabs[0], { title: "Second", path: "/synthetic/second" }] };
  assert.notEqual(buildHostedWorkspaceState(reordered, options).snapshot_id,
    buildHostedWorkspaceState({ ...reordered, tabs: [...reordered.tabs].reverse() }, options).snapshot_id);
});

test("readback rejects legacy coercion, missing content and wrong destination", () => {
  const state = buildHostedWorkspaceState(manifest, { destination });
  const workspace = { schema_version: "2.0.0", source_kind: "hosted_v2", workspace_id: "release", linked_idea: { idea_id: "idea-fixture" },
    current_state_version: 1, state, payload_sha256: workspacePayloadSha256(state) };
  assert.equal(verifyHostedWorkspaceReadback(workspace, state, destination), workspace);
  for (const changes of [{ schema_version: "1.0.0" }, { state: { ...state, tabs: [] } }, { workspace_id: "other" }, { payload_sha256: "wrong" }]) {
    assert.throws(() => verifyHostedWorkspaceReadback({ ...workspace, ...changes }, state, destination), /readback differs/);
  }
});

async function output(action) {
  const original = process.stdout.write;
  let text = "";
  process.stdout.write = (chunk) => { text += chunk; return true; };
  try { await action(); return text; } finally { process.stdout.write = original; }
}

test("separate preview/apply attempts create once, retry safely, reject changes, and require v2 readiness", async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "sync-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const workspaceFile = path.join(root, "workspace with spaces.json");
  const script = path.join(root, "fake-orp.mjs");
  const stateFile = path.join(root, "server.json");
  const callsFile = path.join(root, "calls.ndjson");
  const modeFile = path.join(root, "mode.txt");
  await fs.writeFile(workspaceFile, JSON.stringify(manifest));
  await fs.writeFile(script, `#!${process.execPath}
import fs from 'node:fs';
import { workspacePayloadSha256 } from ${JSON.stringify(new URL("../src/hosted-state.js", import.meta.url).href)};
const args = process.argv.slice(2), key = args.slice(0,2).join(' ');
const file = ${JSON.stringify(stateFile)}, callsFile = ${JSON.stringify(callsFile)}, modeFile = ${JSON.stringify(modeFile)};
fs.appendFileSync(callsFile, JSON.stringify(key) + '\\n');
let workspace = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file)) : null;
const idea = { id: 'idea-fixture', title: 'Example idea', notes: '' };
const send = (value) => console.log(JSON.stringify(value));
if (key === 'workspaces capabilities') send({ ok: true, contract_version: fs.existsSync(modeFile) ? '1.0.0' : '2.0.0', ...${JSON.stringify({base_url: destination.base_url, user_id: destination.user_id})} });
else if (key === 'ideas list') send({ ok: true, ideas: [idea] });
else if (key === 'idea show') send({ ok: true, idea });
else if (key === 'workspaces list') send({ ok: true, workspaces: workspace ? [workspace] : [] });
else if (key === 'workspaces show') send({ ok: true, workspace });
else if (key === 'workspaces add') {
 workspace = { schema_version: '2.0.0', source_kind: 'hosted_v2', workspace_id: 'release', title: 'release', linked_idea: {idea_id: 'idea-fixture'}, current_state_version: 0, state: null };
 fs.writeFileSync(file, JSON.stringify(workspace)); send({ ok: true, workspace });
} else if (key === 'workspaces push-state') {
 const state = JSON.parse(fs.readFileSync(args[args.indexOf('--state-file')+1]));
 workspace = { ...workspace, state, current_state_version: state.state_version, payload_sha256: workspacePayloadSha256(state) };
 fs.writeFileSync(file, JSON.stringify(workspace)); send({ ok: true, workspace });
} else { console.error('Unexpected fake command: '+key); process.exit(1); }
`, { mode: 0o700 });
  const args = ["idea-fixture", "--workspace-file", workspaceFile, "--title", "release", "--allow", "tabs.title", "--allow", "tabs.activity", "--orp-command", script];
  const preview = JSON.parse(await output(() => runWorkspaceSync([...args, "--json"])));
  const confirmation = preview.hostedSync.state.snapshot_id;
  const human = await output(() => runWorkspaceSync(args));
  assert.ok(human.includes(`'${workspaceFile}'`));
  assert.match(human, /--allow tabs.activity/);
  assert.match(human, /"destination"/);
  assert.equal((await fs.readFile(callsFile, "utf8")).includes("push-state"), false);
  const applyArgs = [...args, "--apply", "--confirm", confirmation, "--json"];
  const applied = JSON.parse(await output(() => runWorkspaceSync(applyArgs)));
  assert.equal(applied.snapshotId, confirmation);
  const retried = JSON.parse(await output(() => runWorkspaceSync(applyArgs)));
  assert.equal(retried.snapshotId, confirmation);
  assert.equal((await fs.readFile(callsFile, "utf8")).trim().split("\n").map(JSON.parse).filter((call) => call === "workspaces add").length, 1);
  await fs.writeFile(workspaceFile, JSON.stringify({ ...manifest, tabs: [{ ...manifest.tabs[0], title: "Changed" }] }));
  await assert.rejects(() => output(() => runWorkspaceSync(applyArgs)), /confirmation must exactly match/);
  const before = (await fs.readFile(callsFile, "utf8")).trim().split("\n").map(JSON.parse).filter((call) => call === "workspaces push-state").length;
  await fs.writeFile(modeFile, "legacy");
  await assert.rejects(() => output(() => runWorkspaceSync(applyArgs)), /ready contract 2.0.0/);
  assert.equal((await fs.readFile(callsFile, "utf8")).trim().split("\n").map(JSON.parse).filter((call) => call === "workspaces push-state").length, before);
});
