#!/usr/bin/env python3
"""Exercise an exact tarball and real previous npm releases in disposable prefixes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("tarball", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
tarball = args.tarball.resolve()
records = []

def run(argv, env, cwd, *, parse=True, product=False):
    child_env = dict(env)
    if product:
        child_env.update(ORP_TEST_GUARD="1", ORP_TEST_ROOT=env["HOME"], PYTHONPATH=str(ROOT / "tests/guard"))
    proc = subprocess.run([str(item) for item in argv], env=child_env, cwd=cwd, capture_output=True, text=True, timeout=120)
    if proc.returncode:
        raise RuntimeError(f"Command failed: {argv[0:4]}\n{proc.stderr}\n{proc.stdout}")
    return json.loads(proc.stdout) if parse else proc.stdout

def environment(root):
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "COMSPEC", "PATHEXT") if key in os.environ}
    for name, relative in {"HOME":"home", "XDG_CONFIG_HOME":"config", "XDG_DATA_HOME":"data", "XDG_STATE_HOME":"state", "XDG_CACHE_HOME":"cache", "TMPDIR":"tmp", "TMP":"tmp", "TEMP":"tmp"}.items():
        directory = root / relative
        directory.mkdir(exist_ok=True)
        env[name] = str(directory)
    for name, relative in {"NPM_CONFIG_USERCONFIG":"npmrc", "NPM_CONFIG_GLOBALCONFIG":"npm-globalrc", "GIT_CONFIG_GLOBAL":"gitconfig"}.items():
        (root / relative).touch()
        env[name] = str(root / relative)
    env.update(ORP_PYTHON=sys.executable, PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1", NPM_CONFIG_CACHE=str(root / "npm-cache"), NPM_CONFIG_UPDATE_NOTIFIER="false")
    return env

def install(spec, prefix, env, cwd):
    # The explicit prefix is always beneath this harness's TemporaryDirectory.
    run(["npm", "install", "--global", "--prefix", prefix, "--no-audit", "--no-fund", spec], env, cwd, parse=False)
    package = prefix / "lib/node_modules/open-research-protocol"
    if not package.is_dir(): raise RuntimeError("Expected isolated POSIX npm prefix is missing")
    return ["node", package / "bin/orp.js"]

try:
    with tempfile.TemporaryDirectory(prefix="orp-installed-") as temporary:
        base = Path(temporary)
        for lane in ("fresh", "stable-upgrade", "rc1-repair"):
            root = base / lane
            root.mkdir()
            env = environment(root)
            project = root / "project"
            project.mkdir()
            prefix = root / "prefix"
            old_manifest = None
            if lane != "fresh":
                version = "0.4.38" if lane == "stable-upgrade" else "0.5.0-rc.1"
                old = install(f"open-research-protocol@{version}", prefix, env, root)
                old_env = {**env, "ORP_STORAGE_LAYOUT": "legacy-v0"}
                run([*old, "workspace", "create", "upgrade-example", "--json"], old_env, project, product=True)
                created = run([*old, "workspace", "add-tab", "upgrade-example", "--path", project, "--title", "Original", "--json"], old_env, project, product=True)
                old_manifest = Path(created["manifestPath"])
                if lane == "rc1-repair":
                    plan = run([*old, "storage", "migrate", "--json"], env, project, product=True)
                    run([*old, "storage", "migrate", "--apply", "--confirm", plan["plan_id"], "--json"], env, project, product=True)
                    # Reproduce rc.1 editing the stale legacy reference after migration.
                    run([*old, "workspace", "add-tab", "upgrade-example", "--path", root / "second", "--title", "Later legacy edit", "--json"], env, project, product=True)
                frozen = old_manifest.read_bytes()
            command = install(str(tarball), prefix, env, root)
            package = prefix / "lib/node_modules/open-research-protocol"
            expected_version = json.loads((ROOT / "package.json").read_text())["version"]
            assert json.loads((package / "package.json").read_text())["version"] == expected_version
            about = run([*command, "about", "--json"], env, project, product=True)
            if lane == "fresh":
                adoption = root / "adoption"
                run(["sh", package / "scripts/orp-init.sh", adoption], env, root, parse=False)
                assert (adoption / "PROTOCOL.md").is_file()
                assert (adoption / "cone/CONTEXT_LOG.md").read_text().startswith("# Context Log\n")
                run([*command, "init", "--json"], env, project, product=True)
                run([*command, "config", "validate", "--json"], env, project, product=True)
                run([*command, "agents", "audit", "--json"], env, project, product=True)
                run([*command, "checkpoint", "inspect", "--json"], env, project, product=True)
                run([*command, "workspace", "create", "release-example", "--json"], env, project, product=True)
                run([*command, "workspace", "add-tab", "release-example", "--here", "--json"], env, project, product=True)
                prompt = "Keep these exact words.\nSecond line — unchanged."
                context = run([*command, "codex", "context", "--allow-once", "--prompt", prompt], env, project, product=True)
                assert context["prompt"] == prompt
                assert context["context"]["governed"] is True
                run([*command, "agents", "codex", "sync", "--codex-home", root / "codex", "--json"], env, project, product=True)
            else:
                flags = ["--prefer-legacy"] if lane == "rc1-repair" else []
                plan = run([*command, "storage", "migrate", *flags, "--json"], env, project, product=True)
                assert plan["can_apply"], plan
                run([*command, "storage", "migrate", *flags, "--apply", "--confirm", plan["plan_id"], "--json"], env, project, product=True)
                updated = run([*command, "workspace", "add-tab", "upgrade-example", "--path", root / "third", "--title", "After upgrade", "--json"], env, project, product=True)
                target = Path(updated["manifestPath"])
                assert target.is_relative_to(Path(env["XDG_DATA_HOME"]))
                assert target != old_manifest and old_manifest.read_bytes() == frozen
                content = target.read_text()
                assert "Original" in content and "After upgrade" in content
                if lane == "rc1-repair": assert "Later legacy edit" in content
                repeated = run([*command, "storage", "migrate", "--json"], env, project, product=True)
                assert not repeated["operations"], repeated
            run([*command, "storage", "report", "--json"], env, project, product=True)
            records.append({"lane":lane,"status":"PASS"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.JSONEncoder(indent=2).encode({"status":"PASS", "tarball_sha512":hashlib.sha512(tarball.read_bytes()).hexdigest(), "lanes":records}) + "\n")
    print(args.output.read_text())
except Exception:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.JSONEncoder(indent=2).encode({"status":"FAIL", "completed_lanes":records}) + "\n")
    raise
