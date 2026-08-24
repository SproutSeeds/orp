import fs from "node:fs/promises";
import fsSync from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { randomBytes } from "node:crypto";


export const STORAGE_LAYOUT_LEGACY = "legacy-v0";
export const STORAGE_LAYOUT_XDG = "xdg-v1";
const STORAGE_LAYOUTS = new Set([STORAGE_LAYOUT_LEGACY, STORAGE_LAYOUT_XDG]);
const HOSTED_SYNC_FIELDS = new Set([
  "workspace.summary",
  "workspace.current_focus",
  "workspace.trajectory",
  "tabs.title",
  "tabs.remote_url",
  "tabs.remote_branch",
  "tabs.linked_idea_id",
  "tabs.linked_feature_id",
  "tabs.activity",
  "tabs.plan_summary",
  "tabs.tasks",
]);

function optional(value) {
  const normalized = value == null ? "" : String(value).trim();
  return normalized || null;
}

function resolveHome(env = process.env) {
  return optional(env?.HOME) ? path.resolve(env.HOME) : os.homedir();
}

export function getConfigHome(env = process.env) {
  return optional(env?.XDG_CONFIG_HOME)
    ? path.resolve(env.XDG_CONFIG_HOME)
    : path.join(resolveHome(env), ".config");
}

export function getDataHome(env = process.env) {
  return optional(env?.XDG_DATA_HOME)
    ? path.resolve(env.XDG_DATA_HOME)
    : path.join(resolveHome(env), ".local", "share");
}

export function getStateHome(env = process.env) {
  return optional(env?.XDG_STATE_HOME)
    ? path.resolve(env.XDG_STATE_HOME)
    : path.join(resolveHome(env), ".local", "state");
}

export function getCacheHome(env = process.env) {
  return optional(env?.XDG_CACHE_HOME)
    ? path.resolve(env.XDG_CACHE_HOME)
    : path.join(resolveHome(env), ".cache");
}

export function getLocalConfigPath(env = process.env) {
  return path.join(getConfigHome(env), "orp", "config.json");
}

export function defaultLocalConfig(layout = STORAGE_LAYOUT_XDG) {
  return {
    schema: "orp.local_config/1",
    schema_version: "1.0.0",
    storage: {
      layout,
      retention: {
        cache_days: 30,
        backup_days: 90,
        backup_keep: 5,
      },
    },
    codex: {
      context_enabled: false,
      max_bytes: 2048,
      hosted_sync: false,
    },
    sync: {
      enabled: false,
      allowlist: [],
    },
  };
}

export function loadLocalConfig(env = process.env) {
  const configPath = getLocalConfigPath(env);
  let raw = null;
  try {
    raw = JSON.parse(fsSync.readFileSync(configPath, "utf8"));
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw error;
    }
  }
  const config = raw || defaultLocalConfig(detectDefaultStorageLayout(env));
  validateLocalConfig(config, configPath);
  return config;
}

function exactKeys(value, expected, label, configPath) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`invalid ${label} in ${configPath}`);
  }
  const unknown = Object.keys(value).filter((key) => !expected.includes(key));
  if (unknown.length > 0) {
    throw new Error(`unknown ${label} key in ${configPath}: ${unknown.sort().join(", ")}`);
  }
}

export function validateLocalConfig(config, configPath = "ORP local config") {
  exactKeys(config, ["schema", "schema_version", "storage", "codex", "sync"], "root", configPath);
  if (config.schema !== "orp.local_config/1" || config.schema_version !== "1.0.0") {
    throw new Error(`invalid ORP local config schema in ${configPath}`);
  }
  exactKeys(config.storage, ["layout", "retention"], "storage", configPath);
  if (!STORAGE_LAYOUTS.has(config.storage.layout)) {
    throw new Error(`invalid storage.layout in ${configPath}`);
  }
  exactKeys(config.storage.retention, ["cache_days", "backup_days", "backup_keep"], "storage.retention", configPath);
  for (const [key, minimum] of [["cache_days", 0], ["backup_days", 0], ["backup_keep", 1]]) {
    const value = config.storage.retention[key];
    if (!Number.isInteger(value) || value < minimum) {
      throw new Error(`invalid storage.retention.${key} in ${configPath}`);
    }
  }
  exactKeys(config.codex, ["context_enabled", "max_bytes", "hosted_sync"], "codex", configPath);
  if (typeof config.codex?.context_enabled !== "boolean") {
    throw new Error(`invalid codex.context_enabled in ${configPath}`);
  }
  if (!Number.isInteger(config.codex?.max_bytes) || config.codex.max_bytes < 256 || config.codex.max_bytes > 2048) {
    throw new Error(`invalid codex.max_bytes in ${configPath}`);
  }
  if (config.codex?.hosted_sync !== false) {
    throw new Error("codex.hosted_sync must remain false");
  }
  exactKeys(config.sync, ["enabled", "allowlist"], "sync", configPath);
  if (typeof config.sync.enabled !== "boolean") {
    throw new Error(`invalid sync.enabled in ${configPath}`);
  }
  if (!Array.isArray(config.sync.allowlist) || config.sync.allowlist.some((field) => typeof field !== "string")) {
    throw new Error(`invalid sync.allowlist in ${configPath}`);
  }
  const unique = new Set(config.sync.allowlist);
  if (unique.size !== config.sync.allowlist.length || [...unique].some((field) => !HOSTED_SYNC_FIELDS.has(field))) {
    throw new Error(`invalid sync.allowlist in ${configPath}`);
  }
  return config;
}

function legacyHasMaterial(env = process.env) {
  const root = path.join(getConfigHome(env), "orp");
  try {
    return fsSync.readdirSync(root).some((name) => name !== "config.json");
  } catch {
    return false;
  }
}

function detectDefaultStorageLayout(env = process.env) {
  const configOnly = Boolean(optional(env?.XDG_CONFIG_HOME)) && ![
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "XDG_CACHE_HOME",
  ].some((name) => Boolean(optional(env?.[name])));
  return legacyHasMaterial(env) || configOnly ? STORAGE_LAYOUT_LEGACY : STORAGE_LAYOUT_XDG;
}

export function getStorageLayout(env = process.env) {
  const override = optional(env?.ORP_STORAGE_LAYOUT);
  if (override) {
    if (!STORAGE_LAYOUTS.has(override)) {
      throw new Error("ORP_STORAGE_LAYOUT must be legacy-v0 or xdg-v1");
    }
    return override;
  }

  const configPath = getLocalConfigPath(env);
  try {
    const payload = JSON.parse(fsSync.readFileSync(configPath, "utf8"));
    validateLocalConfig(payload, configPath);
    return payload.storage.layout;
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw error;
    }
  }

  return detectDefaultStorageLayout(env);
}

export function getOrpStorageDir(category, env = process.env, options = {}) {
  const layout = options.layout || getStorageLayout(env);
  if (!STORAGE_LAYOUTS.has(layout)) {
    throw new Error(`unsupported ORP storage layout: ${layout}`);
  }
  if (layout === STORAGE_LAYOUT_LEGACY) {
    return path.join(getConfigHome(env), "orp");
  }
  const homes = {
    config: getConfigHome(env),
    data: getDataHome(env),
    state: getStateHome(env),
    cache: getCacheHome(env),
  };
  if (!(category in homes)) {
    throw new Error(`unknown ORP storage category: ${category}`);
  }
  return path.join(homes[category], "orp");
}

export function getOrpStorageRoots(env = process.env) {
  return Object.fromEntries(
    ["config", "data", "state", "cache"].map((category) => [category, getOrpStorageDir(category, env)]),
  );
}

function containingOrpRoot(filePath, env = process.env) {
  const resolved = path.resolve(filePath);
  const roots = new Set([
    path.join(getConfigHome(env), "orp"),
    path.join(getDataHome(env), "orp"),
    path.join(getStateHome(env), "orp"),
    path.join(getCacheHome(env), "orp"),
  ]);
  for (const root of roots) {
    const resolvedRoot = path.resolve(root);
    if (resolved === resolvedRoot || resolved.startsWith(`${resolvedRoot}${path.sep}`)) {
      return resolvedRoot;
    }
  }
  return null;
}

async function makePrivateParents(directory, root) {
  await fs.mkdir(directory, { recursive: true, mode: 0o700 });
  let current = path.resolve(directory);
  while (true) {
    await fs.chmod(current, 0o700);
    if (current === root) {
      break;
    }
    current = path.dirname(current);
  }
}

export async function atomicWriteOrpFile(filePath, content, options = {}) {
  const env = options.env || process.env;
  const target = path.resolve(filePath);
  const root = containingOrpRoot(target, env);
  const directory = path.dirname(target);
  if (root) {
    await makePrivateParents(directory, root);
  } else {
    await fs.mkdir(directory, { recursive: true });
  }

  const temporary = path.join(
    directory,
    `.${path.basename(target)}.${process.pid}.${randomBytes(6).toString("hex")}.tmp`,
  );
  const mode = root ? 0o600 : 0o644;
  let handle;
  try {
    handle = await fs.open(temporary, "wx", mode);
    await handle.writeFile(content, options.encoding || "utf8");
    await handle.sync();
    await handle.close();
    handle = null;
    await fs.rename(temporary, target);
    await fs.chmod(target, mode);
  } finally {
    if (handle) {
      await handle.close().catch(() => {});
    }
    await fs.unlink(temporary).catch((error) => {
      if (error?.code !== "ENOENT") {
        throw error;
      }
    });
  }
}
