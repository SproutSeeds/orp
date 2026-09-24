#!/usr/bin/env node
const fs = require("node:fs");
const report = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const entry = report[0];
const paths = (entry?.files || []).map((item) => item.path);
const forbidden = /(^|\/)(?:__pycache__|\.venv|node_modules|\.git|\.codex|\.clawdad)(\/|$)|\.py[cod]$|(^|\/)\.DS_Store$|^(?:docs\/audits|cone|analysis|results|tests)\/|\/test\/|^scripts\/test-|(^|\/)\.env(?:\.|$)|(^|\/)\.npmrc$|\.(?:pem|key|p12)$/;
const blocked = paths.filter((file) => forbidden.test(file));
if (blocked.length) throw new Error(`Forbidden package paths: ${blocked.join(", ")}`);
for (const required of ["bin/orp.js", "cli/orp.py", "packages/orp-workspace-launcher/src/storage.js", "spec/v2/hosted-workspace-state.schema.json", "orp/hygiene-policy.json", "PROTOCOL.md", "docs/START_HERE.md"]) {
  if (!paths.includes(required)) throw new Error(`Missing package file: ${required}`);
}
if (!entry.integrity?.startsWith("sha512-")) throw new Error("Package integrity is missing");
if (process.argv[3]) {
  const actual = require("node:crypto").createHash("sha512").update(fs.readFileSync(process.argv[3])).digest("base64");
  if (`sha512-${actual}` !== entry.integrity) throw new Error("Tarball bytes differ from the tested package manifest");
}
console.log(`PASS package manifest: ${paths.length} files, ${entry.integrity}`);
