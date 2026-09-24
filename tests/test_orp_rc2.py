import argparse
import ctypes
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import tomllib
from unittest import mock

from orp_test_support import IsolatedTestCase

ROOT = Path(__file__).resolve().parents[1]

def cli():
    spec = importlib.util.spec_from_file_location("orp_rc2_test", ROOT / "cli/orp.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Rc2Regressions(IsolatedTestCase):
    def test_semver_order_and_exact_install(self):
        module = cli()
        ordered = ["0.4.38", "0.5.0-alpha", "0.5.0-alpha.1", "0.5.0-alpha.beta", "0.5.0-beta", "0.5.0-beta.2", "0.5.0-beta.11", "0.5.0-rc.2", "0.5.0-rc.10", "0.5.0"]
        for left, right in zip(ordered, ordered[1:]):
            self.assertEqual(module._compare_versions(left, right), -1)
        self.assertEqual(module._compare_versions("0.5.0+build.7", "0.5.0+build.8"), 0)
        for invalid in ("latest", "0.5", "01.5.0", "0.5.0-rc.01", "0.5.0; echo unsafe"):
            with self.assertRaises(ValueError): module._version_key(invalid)
        with mock.patch.object(module.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            module._apply_update({"status": "update_available", "install_kind": "npm-global", "tool": {"latest_version": "0.5.0-rc.2"}})
            self.assertEqual(run.call_args.args[0], ["npm", "install", "-g", "open-research-protocol@0.5.0-rc.2"])

    def test_update_channel_and_archive_are_explicit(self):
        module = cli()
        with mock.patch.object(module, "ORP_TOOL_VERSION", "0.5.0-rc.2"), mock.patch.object(module, "_fetch_latest_npm_version", return_value=("0.5.0", "")) as fetch:
            result = module._update_payload()
            self.assertEqual(result["channel"], "next")
            self.assertEqual(result["status"], "update_available")
            fetch.assert_called_once_with(channel="next")
        with mock.patch.object(module, "_tool_package_root", return_value=Path(tempfile.gettempdir()) / "unpacked"):
            self.assertEqual(module._update_install_kind(), "unknown")

    def test_unsupported_login_has_no_external_effect(self):
        module = cli()
        with mock.patch.object(module, "_keychain_supported", return_value=False), mock.patch.object(module, "_request_hosted_json") as request:
            with self.assertRaisesRegex(RuntimeError, "requires macOS Keychain"):
                module.cmd_auth_login(argparse.Namespace())
            request.assert_not_called()

    def test_effect_guards_block_real_installers_network_and_keychain(self):
        with self.assertRaisesRegex(RuntimeError, "external npm"):
            subprocess.run(["npm", "install", "-g", "open-research-protocol"])
        with socket.socket() as sock, self.assertRaisesRegex(RuntimeError, "external network"):
            sock.connect(("203.0.113.1", 443))
        with self.assertRaisesRegex(RuntimeError, "Keychain"):
            ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")

    def test_codex_toml_comments_false_and_backups(self):
        module = cli()
        for header in ("[features] # keep this comment", '["features"]', "[ 'features' ]"):
            original = f'model = "example"\n{header}\n# keep flag note\ncodex_hooks = false # user choice\njs_repl = true\n[other] # another table\nvalue = 7\n'
            result, action = module._codex_config_enable_hooks_text(original)
            parsed = tomllib.loads(result)
            self.assertEqual(parsed["features"], {"hooks": False, "js_repl": True})
            self.assertEqual(parsed["other"]["value"], 7)
            self.assertIn("# user choice", result)
            self.assertEqual(action, "migrated")
            self.assertEqual(module._codex_config_enable_hooks_text(result), (result, "kept_disabled"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.toml"
            config.write_text(original)
            result = module._codex_sync_payload(root)
            self.assertTrue(result["ok"])
            self.assertFalse(result["audit"]["checks"]["config"]["hooks_enabled"])
            backup = list(root.glob("config.toml.orp-backup-*"))
            self.assertEqual(len(backup), 1)
            self.assertEqual(backup[0].read_text(), original)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("/usr/bin/python3", module._codex_desired_session_hook(root)["hooks"][0]["command"])
            self.assertNotIn("/Volumes/Code_2TB", module._codex_session_start_hook_script())

    def test_invalid_codex_config_is_unchanged(self):
        module = cli()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.toml"
            original = "[features]\nhooks = false\n[features]\nhooks = true\n"
            config.write_text(original)
            with self.assertRaises(tomllib.TOMLDecodeError): module._codex_sync_payload(root)
            self.assertEqual(config.read_text(), original)
            self.assertFalse((root / "AGENTS.md").exists())

    def test_invalid_codex_hooks_preflight_preserves_all_files(self):
        module = cli()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "hooks.json").write_text("{broken")
            (root / "config.toml").write_text("[features]\ncodex_hooks = false\n")
            before = {file.name: file.read_bytes() for file in root.iterdir()}
            result = module._codex_sync_payload(root)
            self.assertFalse(result["ok"])
            self.assertEqual({file.name: file.read_bytes() for file in root.iterdir()}, before)
