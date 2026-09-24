"""Deny unintended network, credential, model, and installer effects in tests."""
from contextlib import contextmanager
import ctypes
import os
from pathlib import Path
import shutil
import socket
import subprocess
from unittest import mock


@contextmanager
def guarded():
    original_connect = socket.socket.connect
    original_cdll = ctypes.CDLL
    original_popen = subprocess.Popen

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            if address[0] not in ("127.0.0.1", "::1", "localhost"):
                raise RuntimeError(f"Test guard: external network must be mocked ({address[0]}).")
        return original_connect(sock, address)

    def cdll(name, *args, **kwargs):
        if "Security.framework" in str(name):
            raise RuntimeError("Test guard: native Keychain access must be mocked.")
        return original_cdll(name, *args, **kwargs)

    def popen(command, *args, **kwargs):
        if isinstance(command, (str, bytes)) or kwargs.get("shell"):
            raise RuntimeError("Test guard: use explicit argv and mock shell execution.")
        argv = [os.fspath(item) for item in command]
        name = Path(argv[0]).name
        child_env = kwargs.get("env") or os.environ
        executable = shutil.which(argv[0], path=child_env.get("PATH")) or argv[0]
        fixture_root = os.environ.get("ORP_TEST_ROOT", "")
        fake_tool = bool(fixture_root) and Path(executable).resolve().is_relative_to(Path(fixture_root))
        if not fake_tool:
            if name in {"npm", "npx", "pnpm", "yarn", "pip", "pip3", "security", "launchctl", "gh", "clawdad", "codex"}:
                dry_pack = name == "npm" and argv[1:2] == ["pack"] and "--dry-run" in argv and "--ignore-scripts" in argv
                if not dry_pack and argv[1:] not in (["--version"], ["-v"]):
                    raise RuntimeError(f"Test guard: external {name} operation must be mocked.")
            if name == "git":
                remote_args = any(value.startswith(("https://", "http://", "ssh://", "git@")) for value in argv[1:])
                local_configuration = "remote" in argv and any(value in argv for value in ("add", "set-url"))
                if (remote_args and not local_configuration) or "pull" in argv:
                    raise RuntimeError("Test guard: remote Git operation must be mocked.")
                if "push" in argv or "fetch" in argv:
                    probe = original_popen([argv[0], "config", "--get", "remote.origin.url"], cwd=kwargs.get("cwd"), env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    url, _ = probe.communicate()
                    if probe.returncode != 0 or not url.strip().startswith(("/", "file://")):
                        raise RuntimeError("Test guard: remote Git write/read must be mocked.")
        return original_popen(command, *args, **kwargs)

    with mock.patch.object(socket.socket, "connect", connect), mock.patch.object(ctypes, "CDLL", cdll), mock.patch.object(subprocess, "Popen", popen):
        yield
