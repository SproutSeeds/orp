import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import {
  atomicWriteOrpFile,
  getOrpStorageDir,
  getStorageLayout,
  loadLocalConfig,
  registerWorkspaceManifest,
  cacheManagedWorkspaceManifest,
} from "../src/index.js";
import { applyWorkspaceAddTabOptions } from "../src/ledger.js";


async function makeTempDir() {
  return fs.mkdtemp(path.join(os.tmpdir(), "orp-storage-"));
}

function xdgEnv(root) {
  return {
    HOME: path.join(root, "home"),
    XDG_CONFIG_HOME: path.join(root, "config"),
    XDG_DATA_HOME: path.join(root, "data"),
    XDG_STATE_HOME: path.join(root, "state"),
    XDG_CACHE_HOME: path.join(root, "cache"),
  };
}

test("fresh local storage uses separated XDG roots", async () => {
  const root = await makeTempDir();
  const env = xdgEnv(root);

  assert.equal(getStorageLayout(env), "xdg-v1");
  assert.equal(getOrpStorageDir("config", env), path.join(root, "config", "orp"));
  assert.equal(getOrpStorageDir("data", env), path.join(root, "data", "orp"));
  assert.equal(getOrpStorageDir("state", env), path.join(root, "state", "orp"));
  assert.equal(getOrpStorageDir("cache", env), path.join(root, "cache", "orp"));
});

test("a config-only XDG override retains the legacy automation layout", async () => {
  const root = await makeTempDir();
  const env = {
    HOME: path.join(root, "home"),
    XDG_CONFIG_HOME: path.join(root, "config"),
  };

  assert.equal(getStorageLayout(env), "legacy-v0");
  assert.equal(getOrpStorageDir("data", env), path.join(root, "config", "orp"));
});

test("atomic ORP writes use private files and directories", async () => {
  const root = await makeTempDir();
  const env = xdgEnv(root);
  const filePath = path.join(getOrpStorageDir("data", env), "nested", "state.json");

  await atomicWriteOrpFile(filePath, '{"ok":true}\n', { env });

  assert.equal(await fs.readFile(filePath, "utf8"), '{"ok":true}\n');
  assert.equal((await fs.stat(filePath)).mode & 0o777, 0o600);
  assert.equal((await fs.stat(path.dirname(filePath))).mode & 0o777, 0o700);
  const siblings = await fs.readdir(path.dirname(filePath));
  assert.deepEqual(siblings, ["state.json"]);
});

test("workspace registry follows xdg-v1 and is private", async () => {
  const root = await makeTempDir();
  const env = xdgEnv(root);
  const manifestPath = path.join(root, "project", "workspace.json");
  const manifest = {
    version: "1",
    workspaceId: "main",
    title: "Main",
    tabs: [],
  };

  const result = await registerWorkspaceManifest(manifestPath, manifest, { env });

  assert.equal(result.registryPath, path.join(root, "data", "orp", "workspace-registry.json"));
  assert.equal((await fs.stat(result.registryPath)).mode & 0o777, 0o600);
  assert.equal((await fs.stat(path.dirname(result.registryPath))).mode & 0o777, 0o700);
});

test("local config rejects unknown keys and unsupported sync fields", async () => {
  const root = await makeTempDir();
  const env = xdgEnv(root);
  const configPath = path.join(root, "config", "orp", "config.json");
  await fs.mkdir(path.dirname(configPath), { recursive: true });
  await fs.writeFile(configPath, JSON.stringify({
    ...defaultConfig(),
    surprise: true,
  }));
  assert.throws(() => loadLocalConfig(env), /unknown root key/);

  await fs.writeFile(configPath, JSON.stringify({
    ...defaultConfig(),
    sync: { enabled: true, allowlist: ["tabs.source_file"] },
  }));
  assert.throws(() => loadLocalConfig(env), /invalid sync.allowlist/);
});

function defaultConfig() {
  return {
    schema: "orp.local_config/1",
    schema_version: "1.0.0",
    storage: { layout: "xdg-v1", retention: { cache_days: 30, backup_days: 90, backup_keep: 5 } },
    codex: { context_enabled: false, max_bytes: 2048, hosted_sync: false },
    sync: { enabled: false, allowlist: [] },
  };
}

test("managed add-tab preserves the original manifest after a partial temporary write", async (t) => {
  const root = await makeTempDir();
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const env = xdgEnv(root);
  const saved = await cacheManagedWorkspaceManifest({ version: "1", workspaceId: "failure", title: "failure", tabs: [{ path: path.join(root, "project"), title: "first" }] }, { env });
  const before = await fs.readFile(saved.manifestPath);
  const originalOpen = fs.open;
  fs.open = async (file, ...args) => {
    const handle = await originalOpen(file, ...args);
    if (path.basename(String(file)).startsWith(`.${path.basename(saved.manifestPath)}.`)) {
      const originalWrite = handle.writeFile.bind(handle);
      handle.writeFile = async (content) => {
        await originalWrite(String(content).slice(0, 1));
        throw Object.assign(new Error("injected disk-full failure"), { code: "ENOSPC" });
      };
    }
    return handle;
  };
  try {
    await assert.rejects(applyWorkspaceAddTabOptions({ workspaceFile: saved.manifestPath, path: path.join(root, "second"), title: "second", env }), /disk-full/);
  } finally {
    fs.open = originalOpen;
  }
  assert.deepEqual(await fs.readFile(saved.manifestPath), before);
  assert.equal((await fs.readdir(path.dirname(saved.manifestPath))).some((name) => name.endsWith(".tmp")), false);
  await assert.rejects(fs.stat(path.join(root, "config/orp/.storage-write.lock")), { code: "ENOENT" });
});

test("first Node data write pins XDG and later native config does not change layout", async (t) => {
  const root = await makeTempDir();
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const env = xdgEnv(root);
  await atomicWriteOrpFile(path.join(getOrpStorageDir("data", env), "agenda.json"), "{}", { env });
  await atomicWriteOrpFile(path.join(getOrpStorageDir("config", env), "agents.json"), "{}", { env });
  assert.equal(getStorageLayout(env), "xdg-v1");
  assert.equal(loadLocalConfig(env).storage.layout, "xdg-v1");
});

test("a stale legacy manifest reference cannot write after XDG is selected", async (t) => {
  const root = await makeTempDir();
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const env = xdgEnv(root);
  await atomicWriteOrpFile(path.join(getOrpStorageDir("config", env), "config.json"), JSON.stringify(defaultConfig()), { env });
  await assert.rejects(atomicWriteOrpFile(path.join(root, "config/orp/workspaces/main.json"), "{}", { env }), /legacy reference/);
});

test("external workspace files retain their existing permissions during atomic edits", async (t) => {
  const root = await makeTempDir();
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const file = path.join(root, "user-workspace.json");
  await fs.writeFile(file, "before", { mode: 0o600 });
  await atomicWriteOrpFile(file, "after", { env: xdgEnv(root) });
  assert.equal(await fs.readFile(file, "utf8"), "after");
  assert.equal((await fs.stat(file)).mode & 0o777, 0o600);
});
