import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { createHash } from "node:crypto";

import { normalizeWorkspaceManifest } from "./core-plan.js";

const WORKSPACE_REGISTRY_VERSION = "1";
const WORKSPACE_SLOTS_VERSION = "1";
const WORKSPACE_SLOT_NAMES = new Set(["main", "offhand"]);

function normalizeOptionalString(value) {
  if (value == null) {
    return null;
  }
  const trimmed = String(value).trim();
  return trimmed.length > 0 ? trimmed : null;
}

function slugify(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized || "workspace";
}

export function normalizeWorkspaceSlotName(value) {
  const normalized = normalizeOptionalString(value)?.toLowerCase() || null;
  return normalized && WORKSPACE_SLOT_NAMES.has(normalized) ? normalized : null;
}

function shortHash(value) {
  return createHash("sha1").update(String(value || "")).digest("hex").slice(0, 8);
}

function countTabsWithValue(tabs, key) {
  return tabs.reduce((count, tab) => (normalizeOptionalString(tab[key]) ? count + 1 : count), 0);
}

function buildResumeSessionRows(tabs) {
  return tabs
    .map((tab) => {
      const resumeCommand = normalizeOptionalString(tab.resumeCommand);
      const resumeTool = normalizeOptionalString(tab.resumeTool);
      const resumeSessionId = normalizeOptionalString(tab.resumeSessionId ?? tab.sessionId);
      if (!resumeCommand && !resumeSessionId) {
        return null;
      }
      return Object.fromEntries(
        Object.entries({
          title: normalizeOptionalString(tab.title) ?? undefined,
          path: normalizeOptionalString(tab.path) ?? undefined,
          resumeCommand: resumeCommand ?? undefined,
          resumeTool: resumeTool ?? undefined,
          resumeSessionId: resumeSessionId ?? undefined,
          codexSessionId: resumeTool === "codex" ? resumeSessionId ?? undefined : undefined,
        }).filter(([, value]) => value !== undefined),
      );
    })
    .filter(Boolean);
}

function normalizeRegistryEntry(rawEntry) {
  if (!rawEntry || typeof rawEntry !== "object" || Array.isArray(rawEntry)) {
    return null;
  }

  const manifestPath = normalizeOptionalString(rawEntry.manifestPath);
  if (!manifestPath) {
    return null;
  }

  return Object.fromEntries(
    Object.entries({
      manifestPath,
      workspaceId: normalizeOptionalString(rawEntry.workspaceId) ?? undefined,
      title: normalizeOptionalString(rawEntry.title) ?? undefined,
      host: normalizeOptionalString(rawEntry.host) ?? undefined,
      captureMode: normalizeOptionalString(rawEntry.captureMode) ?? undefined,
      capturedAt: normalizeOptionalString(rawEntry.capturedAt) ?? undefined,
      trackingStartedAt: normalizeOptionalString(rawEntry.trackingStartedAt) ?? undefined,
      windowId: Number.isInteger(rawEntry.windowId) && rawEntry.windowId > 0 ? rawEntry.windowId : undefined,
      windowIndex: Number.isInteger(rawEntry.windowIndex) && rawEntry.windowIndex > 0 ? rawEntry.windowIndex : undefined,
      tabCount: Number.isInteger(rawEntry.tabCount) && rawEntry.tabCount >= 0 ? rawEntry.tabCount : undefined,
      codexSessionCount:
        Number.isInteger(rawEntry.codexSessionCount) && rawEntry.codexSessionCount >= 0
          ? rawEntry.codexSessionCount
          : undefined,
      tmuxSessionCount:
        Number.isInteger(rawEntry.tmuxSessionCount) && rawEntry.tmuxSessionCount >= 0
          ? rawEntry.tmuxSessionCount
          : undefined,
      resumeSessions: Array.isArray(rawEntry.resumeSessions)
        ? rawEntry.resumeSessions
            .map((session) => {
              if (!session || typeof session !== "object" || Array.isArray(session)) {
                return null;
              }
              const resumeCommand = normalizeOptionalString(session.resumeCommand);
              const resumeSessionId = normalizeOptionalString(session.resumeSessionId);
              if (!resumeCommand && !resumeSessionId) {
                return null;
              }
              return Object.fromEntries(
                Object.entries({
                  title: normalizeOptionalString(session.title) ?? undefined,
                  path: normalizeOptionalString(session.path) ?? undefined,
                  resumeCommand: resumeCommand ?? undefined,
                  resumeTool: normalizeOptionalString(session.resumeTool) ?? undefined,
                  resumeSessionId: resumeSessionId ?? undefined,
                  codexSessionId: normalizeOptionalString(session.codexSessionId) ?? undefined,
                }).filter(([, value]) => value !== undefined),
              );
            })
            .filter(Boolean)
        : Array.isArray(rawEntry.codexSessions)
          ? rawEntry.codexSessions
            .map((session) => {
              if (!session || typeof session !== "object" || Array.isArray(session)) {
                return null;
              }
              const codexSessionId = normalizeOptionalString(session.codexSessionId);
              if (!codexSessionId) {
                return null;
              }
              return Object.fromEntries(
                Object.entries({
                  title: normalizeOptionalString(session.title) ?? undefined,
                  path: normalizeOptionalString(session.path) ?? undefined,
                  resumeCommand: codexSessionId ? `codex resume ${codexSessionId}` : undefined,
                  resumeTool: codexSessionId ? "codex" : undefined,
                  resumeSessionId: codexSessionId,
                  codexSessionId,
                }).filter(([, value]) => value !== undefined),
              );
            })
            .filter(Boolean)
        : undefined,
      codexSessions: undefined,
      registeredAt: normalizeOptionalString(rawEntry.registeredAt) ?? undefined,
      updatedAt: normalizeOptionalString(rawEntry.updatedAt) ?? undefined,
    }).filter(([, value]) => value !== undefined),
  );
}

function normalizeRegistry(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return {
      version: WORKSPACE_REGISTRY_VERSION,
      workspaces: [],
    };
  }

  const version = normalizeOptionalString(payload.version) || WORKSPACE_REGISTRY_VERSION;
  if (version !== WORKSPACE_REGISTRY_VERSION) {
    throw new Error(`unsupported workspace registry version: ${version}`);
  }

  return {
    version,
    workspaces: Array.isArray(payload.workspaces)
      ? payload.workspaces.map((entry) => normalizeRegistryEntry(entry)).filter(Boolean)
      : [],
  };
}

function normalizeWorkspaceSlotEntry(rawEntry) {
  if (!rawEntry || typeof rawEntry !== "object" || Array.isArray(rawEntry)) {
    return null;
  }

  const slot = normalizeWorkspaceSlotName(rawEntry.slot);
  const kind = normalizeOptionalString(rawEntry.kind);
  if (!slot || !kind) {
    return null;
  }

  return Object.fromEntries(
    Object.entries({
      slot,
      kind,
      selector: normalizeOptionalString(rawEntry.selector) ?? undefined,
      workspaceId: normalizeOptionalString(rawEntry.workspaceId) ?? undefined,
      title: normalizeOptionalString(rawEntry.title) ?? undefined,
      ideaId: normalizeOptionalString(rawEntry.ideaId) ?? undefined,
      hostedWorkspaceId: normalizeOptionalString(rawEntry.hostedWorkspaceId) ?? undefined,
      manifestPath: normalizeOptionalString(rawEntry.manifestPath) ?? undefined,
      assignedAt: normalizeOptionalString(rawEntry.assignedAt) ?? undefined,
      updatedAt: normalizeOptionalString(rawEntry.updatedAt) ?? undefined,
    }).filter(([, value]) => value !== undefined),
  );
}

function normalizeWorkspaceSlots(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return {
      version: WORKSPACE_SLOTS_VERSION,
      slots: {},
    };
  }

  const version = normalizeOptionalString(payload.version) || WORKSPACE_SLOTS_VERSION;
  if (version !== WORKSPACE_SLOTS_VERSION) {
    throw new Error(`unsupported workspace slots version: ${version}`);
  }

  const rawSlots =
    payload.slots && typeof payload.slots === "object" && !Array.isArray(payload.slots) ? payload.slots : {};
  const slots = {};
  for (const [slotName, rawEntry] of Object.entries(rawSlots)) {
    const normalizedSlotName = normalizeWorkspaceSlotName(slotName);
    const entry = normalizeWorkspaceSlotEntry({
      slot: slotName,
      ...(rawEntry && typeof rawEntry === "object" && !Array.isArray(rawEntry) ? rawEntry : {}),
    });
    if (normalizedSlotName && entry) {
      slots[normalizedSlotName] = entry;
    }
  }

  return {
    version,
    slots,
  };
}

function registrySortValue(entry) {
  return Date.parse(entry.updatedAt || entry.capturedAt || entry.registeredAt || "") || 0;
}

function sortRegistryEntries(entries) {
  return [...entries].sort((left, right) => {
    const dateDelta = registrySortValue(right) - registrySortValue(left);
    if (dateDelta !== 0) {
      return dateDelta;
    }
    return String(left.manifestPath).localeCompare(String(right.manifestPath));
  });
}

export function getConfigHome(env = process.env) {
  const xdgConfigHome = normalizeOptionalString(env?.XDG_CONFIG_HOME);
  if (xdgConfigHome) {
    return path.resolve(xdgConfigHome);
  }
  return path.join(os.homedir(), ".config");
}

export function getOrpUserDir(env = process.env) {
  return path.join(getConfigHome(env), "orp");
}

export function getWorkspaceRegistryPath(options = {}) {
  if (options.registryPath) {
    return path.resolve(options.registryPath);
  }
  return path.join(getOrpUserDir(options.env), "workspace-registry.json");
}

export function getWorkspaceSlotsPath(options = {}) {
  if (options.slotsPath) {
    return path.resolve(options.slotsPath);
  }
  return path.join(getOrpUserDir(options.env), "workspace-slots.json");
}

export function getWorkspaceStylesPath(options = {}) {
  if (options.stylesPath) {
    return path.resolve(options.stylesPath);
  }
  return path.join(getOrpUserDir(options.env), "workspace-styles.json");
}

export function getWorkspaceStyleBindingsPath(options = {}) {
  if (options.styleBindingsPath) {
    return path.resolve(options.styleBindingsPath);
  }
  return path.join(getOrpUserDir(options.env), "workspace-style-bindings.json");
}

export function getManagedWorkspaceDir(options = {}) {
  return path.join(getOrpUserDir(options.env), "workspaces");
}

export function isManagedWorkspaceManifestPath(manifestPath, options = {}) {
  const candidate = normalizeOptionalString(manifestPath);
  if (!candidate) {
    return false;
  }
  const managedDir = path.resolve(getManagedWorkspaceDir(options));
  const resolvedPath = path.resolve(candidate);
  return resolvedPath === managedDir || resolvedPath.startsWith(`${managedDir}${path.sep}`);
}

export function getManagedWorkspaceManifestPath(manifest, options = {}) {
  const workspaceId = normalizeOptionalString(manifest?.workspaceId);
  const title = normalizeOptionalString(manifest?.title);
  const token = workspaceId || title || "workspace";
  const fileName = `${slugify(token)}-${shortHash(token)}.json`;
  return path.join(getManagedWorkspaceDir(options), fileName);
}

export function summarizeManifestForRegistry(manifestPath, manifest) {
  const normalizedPath = path.resolve(manifestPath);
  const resumeSessions = buildResumeSessionRows(manifest.tabs || []);

  return Object.fromEntries(
    Object.entries({
      manifestPath: normalizedPath,
      workspaceId: normalizeOptionalString(manifest.workspaceId) ?? undefined,
      title: normalizeOptionalString(manifest.title) ?? undefined,
      host: normalizeOptionalString(manifest.capture?.host) ?? undefined,
      captureMode: normalizeOptionalString(manifest.capture?.mode) ?? undefined,
      capturedAt: normalizeOptionalString(manifest.capture?.capturedAt) ?? undefined,
      trackingStartedAt: normalizeOptionalString(manifest.capture?.trackingStartedAt) ?? undefined,
      windowId: manifest.capture?.windowId ?? undefined,
      windowIndex: manifest.capture?.windowIndex ?? undefined,
      tabCount: Array.isArray(manifest.tabs) ? manifest.tabs.length : 0,
      codexSessionCount: resumeSessions.length,
      tmuxSessionCount: countTabsWithValue(manifest.tabs || [], "tmuxSessionName"),
      resumeSessions,
    }).filter(([, value]) => value !== undefined),
  );
}

function serializeManagedWorkspaceManifest(manifest) {
  const normalized = normalizeWorkspaceManifest(manifest);
  const tabs = Array.isArray(normalized.tabs)
    ? normalized.tabs.map((tab) => {
        const resumeCommand = normalizeOptionalString(tab.resumeCommand);
        const resumeTool = normalizeOptionalString(tab.resumeTool);
        const resumeSessionId = normalizeOptionalString(tab.resumeSessionId ?? tab.sessionId);
        return Object.fromEntries(
          Object.entries({
            title: normalizeOptionalString(tab.title) ?? undefined,
            path: normalizeOptionalString(tab.path) ?? undefined,
            resumeCommand: resumeCommand ?? undefined,
            resumeTool: resumeTool ?? undefined,
            resumeSessionId: resumeSessionId ?? undefined,
            codexSessionId: resumeTool === "codex" ? resumeSessionId ?? undefined : undefined,
            claudeSessionId: resumeTool === "claude" ? resumeSessionId ?? undefined : undefined,
          }).filter(([, value]) => value !== undefined),
        );
      })
    : [];

  return `${JSON.stringify(
    Object.fromEntries(
      Object.entries({
        version: normalized.version,
        workspaceId: normalizeOptionalString(normalized.workspaceId) ?? undefined,
        title: normalizeOptionalString(normalized.title) ?? undefined,
        capture: normalized.capture || undefined,
        tabs,
      }).filter(([, value]) => value !== undefined),
    ),
    null,
    2,
  )}\n`;
}

export async function loadWorkspaceRegistry(options = {}) {
  const registryPath = getWorkspaceRegistryPath(options);
  try {
    const raw = await fs.readFile(registryPath, "utf8");
    return {
      registryPath,
      registry: normalizeRegistry(JSON.parse(raw)),
    };
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return {
        registryPath,
        registry: {
          version: WORKSPACE_REGISTRY_VERSION,
          workspaces: [],
        },
      };
    }
    throw error;
  }
}

async function saveWorkspaceRegistry(registryPath, registry) {
  await fs.mkdir(path.dirname(registryPath), { recursive: true });
  await fs.writeFile(`${registryPath}`, `${JSON.stringify(registry, null, 2)}\n`, "utf8");
}

async function saveWorkspaceSlots(slotsPath, payload) {
  await fs.mkdir(path.dirname(slotsPath), { recursive: true });
  await fs.writeFile(`${slotsPath}`, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

export async function loadWorkspaceSlots(options = {}) {
  const slotsPath = getWorkspaceSlotsPath(options);
  try {
    const raw = await fs.readFile(slotsPath, "utf8");
    return {
      slotsPath,
      slots: normalizeWorkspaceSlots(JSON.parse(raw)).slots,
    };
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return {
        slotsPath,
        slots: {},
      };
    }
    throw error;
  }
}

export async function setWorkspaceSlot(slotName, assignment, options = {}) {
  const normalizedSlot = normalizeWorkspaceSlotName(slotName);
  if (!normalizedSlot) {
    throw new Error(`unsupported workspace slot: ${slotName}`);
  }

  const entry = normalizeWorkspaceSlotEntry({
    slot: normalizedSlot,
    ...(assignment && typeof assignment === "object" && !Array.isArray(assignment) ? assignment : {}),
  });
  if (!entry) {
    throw new Error(`invalid workspace slot assignment for ${normalizedSlot}`);
  }

  const { slotsPath, slots } = await loadWorkspaceSlots(options);
  const now = new Date().toISOString();
  const existing = slots[normalizedSlot];
  const nextSlots = {
    ...slots,
    [normalizedSlot]: {
      ...entry,
      slot: normalizedSlot,
      assignedAt: existing?.assignedAt || now,
      updatedAt: now,
    },
  };

  await saveWorkspaceSlots(slotsPath, {
    version: WORKSPACE_SLOTS_VERSION,
    slots: nextSlots,
  });

  return {
    slotsPath,
    slot: nextSlots[normalizedSlot],
  };
}

export async function clearWorkspaceSlot(slotName, options = {}) {
  const normalizedSlot = normalizeWorkspaceSlotName(slotName);
  if (!normalizedSlot) {
    throw new Error(`unsupported workspace slot: ${slotName}`);
  }

  const { slotsPath, slots } = await loadWorkspaceSlots(options);
  if (!slots[normalizedSlot]) {
    return {
      slotsPath,
      cleared: false,
    };
  }

  const nextSlots = { ...slots };
  delete nextSlots[normalizedSlot];
  await saveWorkspaceSlots(slotsPath, {
    version: WORKSPACE_SLOTS_VERSION,
    slots: nextSlots,
  });
  return {
    slotsPath,
    cleared: true,
  };
}

export async function registerWorkspaceManifest(manifestPath, manifest, options = {}) {
  const resolvedManifest = normalizeWorkspaceManifest(manifest);
  const { registryPath, registry } = await loadWorkspaceRegistry(options);
  const now = new Date().toISOString();
  const normalizedManifestPath = path.resolve(manifestPath);
  const existingEntry = registry.workspaces.find((entry) => entry.manifestPath === normalizedManifestPath) || null;
  const nextEntry = {
    ...summarizeManifestForRegistry(normalizedManifestPath, resolvedManifest),
    registeredAt: existingEntry?.registeredAt || now,
    updatedAt: now,
  };
  const nextRegistry = {
    version: registry.version,
    workspaces: sortRegistryEntries([
      ...registry.workspaces.filter((entry) => entry.manifestPath !== normalizedManifestPath),
      nextEntry,
    ]),
  };

  await saveWorkspaceRegistry(registryPath, nextRegistry);

  return {
    registryPath,
    entry: nextEntry,
  };
}

export async function cacheManagedWorkspaceManifest(manifest, options = {}) {
  const resolvedManifest = normalizeWorkspaceManifest(manifest);
  const manifestPath = getManagedWorkspaceManifestPath(resolvedManifest, options);
  await fs.mkdir(path.dirname(manifestPath), { recursive: true });
  await fs.writeFile(`${manifestPath}`, serializeManagedWorkspaceManifest(resolvedManifest), "utf8");
  const registration = await registerWorkspaceManifest(manifestPath, resolvedManifest, options);
  return {
    manifestPath,
    manifest: resolvedManifest,
    registryPath: registration.registryPath,
    entry: registration.entry,
  };
}

export async function listTrackedWorkspaces(options = {}) {
  const { registryPath, registry } = await loadWorkspaceRegistry(options);
  const workspaces = [];

  for (const entry of registry.workspaces) {
    try {
      const rawManifest = await fs.readFile(entry.manifestPath, "utf8");
      const manifest = normalizeWorkspaceManifest(JSON.parse(rawManifest));
      workspaces.push({
        ...entry,
        ...summarizeManifestForRegistry(entry.manifestPath, manifest),
        registeredAt: entry.registeredAt,
        updatedAt: entry.updatedAt,
        status: "ok",
      });
    } catch (error) {
      if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
        workspaces.push({
          ...entry,
          status: "missing",
          error: "manifest file not found",
        });
        continue;
      }

      workspaces.push({
        ...entry,
        status: "invalid",
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  return {
    registryPath,
    workspaces: sortRegistryEntries(workspaces),
  };
}
