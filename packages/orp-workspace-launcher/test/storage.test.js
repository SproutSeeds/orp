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
} from "../src/index.js";


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
