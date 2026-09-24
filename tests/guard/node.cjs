// Preload before node:test imports product code. Each test worker owns its home,
// XDG roots, fake tool directory, and descendants' Python safety environment.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const cp = require("node:child_process");
const net = require("node:net");
const { syncBuiltinESMExports } = require("node:module");

const root = fs.mkdtempSync(path.join(os.tmpdir(), "orp-node-test-"));
const previous = { ...process.env };
for (const key of Object.keys(process.env)) delete process.env[key];
Object.assign(process.env, {
  PATH: previous.PATH || "", HOME: path.join(root, "home"),
  XDG_CONFIG_HOME: path.join(root, "config"), XDG_DATA_HOME: path.join(root, "data"),
  XDG_STATE_HOME: path.join(root, "state"), XDG_CACHE_HOME: path.join(root, "cache"),
  TMPDIR: path.join(root, "tmp"), TMP: path.join(root, "tmp"), TEMP: path.join(root, "tmp"),
  ORP_STORAGE_LAYOUT: "legacy-v0", ORP_TEST_GUARD: "1", ORP_TEST_ROOT: root,
  PYTHONPATH: __dirname, PYTHONDONTWRITEBYTECODE: "1",
  GIT_CONFIG_NOSYSTEM: "1", GIT_CONFIG_GLOBAL: path.join(root, "gitconfig"),
  NPM_CONFIG_GLOBALCONFIG: path.join(root, "npm-globalrc"),
  NPM_CONFIG_USERCONFIG: path.join(root, "npmrc"), NPM_CONFIG_CACHE: path.join(root, "npm-cache"),
});
for (const key of ["SYSTEMROOT", "COMSPEC", "PATHEXT", "NODE_TEST_CONTEXT", "ORP_PYTHON"]) {
  if (previous[key]) process.env[key] = previous[key];
}
for (const directory of [process.env.HOME, process.env.TMPDIR]) fs.mkdirSync(directory, { recursive: true });
fs.writeFileSync(process.env.NPM_CONFIG_USERCONFIG, "");
fs.writeFileSync(process.env.NPM_CONFIG_GLOBALCONFIG, "");
fs.writeFileSync(process.env.GIT_CONFIG_GLOBAL, "");
process.on("exit", () => fs.rmSync(root, { recursive: true, force: true }));

const forbidden = new Set(["orp", "npm", "npx", "pnpm", "yarn", "pip", "pip3", "security", "launchctl", "gh", "clawdad", "codex"]);
for (const method of ["spawn", "spawnSync", "execFile", "execFileSync"]) {
  const original = cp[method];
  cp[method] = function (file, args, ...rest) {
    const fake = path.isAbsolute(file) && path.resolve(file).startsWith(`${root}${path.sep}`);
    if (!fake && forbidden.has(path.basename(file))) {
      throw new Error(`Test guard: external ${path.basename(file)} command must be mocked.`);
    }
    if (path.basename(file) === "git" && Array.isArray(args) && args.some((arg) => /^(https?:|ssh:|git@)/.test(arg)) && !args.includes("remote")) {
      throw new Error("Test guard: remote Git operation must be mocked.");
    }
    return original.call(this, file, args, ...rest);
  };
}
for (const method of ["exec", "execSync"]) {
  cp[method] = () => { throw new Error("Test guard: shell execution must be mocked."); };
}
const connect = net.Socket.prototype.connect;
net.Socket.prototype.connect = function (...args) {
  const first = args[0];
  const options = typeof first === "object" && !Array.isArray(first) ? first : Array.isArray(first) ? first[0] : null;
  const host = options?.host || (typeof args[1] === "string" ? args[1] : null);
  if (host && !["localhost", "127.0.0.1", "::1"].includes(host)) throw new Error("Test guard: external network must be mocked.");
  return connect.apply(this, args);
};
const fetch = globalThis.fetch;
globalThis.fetch = (input, ...args) => {
  const url = new URL(typeof input === "string" || input instanceof URL ? input : input.url);
  if (!["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) throw new Error("Test guard: external fetch must be mocked.");
  return fetch(input, ...args);
};
syncBuiltinESMExports();
