from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_local_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpLocalContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = {
            "HOME": str(self.root / "home"),
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_STATE_HOME": str(self.root / "state"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
        }
        self.env_patch = mock.patch.dict(os.environ, self.env, clear=True)
        self.env_patch.start()
        self.module = load_cli_module()

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.temp.cleanup()

    def test_fresh_install_defaults_to_xdg_v1_without_writing(self) -> None:
        payload = self.module._storage_report_payload()

        self.assertEqual(payload["layout"], "xdg-v1")
        roots = {row["category"]: row["path"] for row in payload["roots"]}
        self.assertEqual(roots["config"], str(self.root / "config" / "orp"))
        self.assertEqual(roots["data"], str(self.root / "data" / "orp"))
        self.assertEqual(roots["state"], str(self.root / "state" / "orp"))
        self.assertEqual(roots["cache"], str(self.root / "cache" / "orp"))
        self.assertFalse((self.root / "config" / "orp" / "config.json").exists())
        self.assertFalse(payload["codex_storage_scanned"])
        self.assertFalse(payload["repository_storage_scanned"])

    def test_config_set_writes_private_atomic_config(self) -> None:
        with redirect_stdout(io.StringIO()):
            result = self.module.cmd_config_set(
                argparse.Namespace(key="codex.context_enabled", value="true", json_output=True)
            )

        self.assertEqual(result, 0)
        path = self.root / "config" / "orp" / "config.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(payload["codex"]["context_enabled"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_config_layout_cannot_bypass_migration(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "storage migrate"):
            self.module.cmd_config_set(
                argparse.Namespace(key="storage.layout", value="legacy-v0", json_output=True)
            )

    def test_config_rejects_unknown_partial_and_codex_hosted_sync_keys(self) -> None:
        path = self.root / "config" / "orp" / "config.json"
        path.parent.mkdir(parents=True)

        path.write_text(json.dumps({"schema": "orp.local_config/1", "surprise": True}), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unknown root key"):
            self.module._load_local_config()

        payload = self.module._local_config_template()
        payload["codex"]["hosted_sync"] = True
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "must remain false"):
            self.module._load_local_config()

        payload = self.module._local_config_template()
        payload["sync"]["allowlist"] = ["tabs.source_file"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unsupported fields"):
            self.module._load_local_config()

    def test_config_only_xdg_override_preserves_legacy_automation_contract(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "HOME": str(self.root / "second-home"),
                "XDG_CONFIG_HOME": str(self.root / "second-config"),
            },
            clear=True,
        ):
            module = load_cli_module()
            self.assertEqual(module._orp_storage_layout(), "legacy-v0")
            self.assertEqual(
                module._keychain_secret_registry_path(),
                self.root / "second-config" / "orp" / "secrets-keychain.json",
            )

    def test_migration_is_deterministic_verified_and_source_preserving(self) -> None:
        legacy = self.root / "config" / "orp"
        legacy.mkdir(parents=True)
        (legacy / "agenda.json").write_text('{"items":[]}\n', encoding="utf-8")
        workspace = legacy / "workspaces" / "main.json"
        workspace.parent.mkdir()
        workspace.write_text('{"version":"1","tabs":[]}\n', encoding="utf-8")
        (legacy / "human-note.txt").write_text("keep me\n", encoding="utf-8")

        first = self.module._build_storage_migration_plan()
        second = self.module._build_storage_migration_plan()

        self.assertEqual(first["plan_id"], second["plan_id"])
        self.assertTrue(first["can_apply"])
        self.assertEqual(first["copy_count"], 2)
        self.assertEqual(first["unclassified"], ["human-note.txt"])

        applied = self.module._apply_storage_migration(first, first["plan_id"])
        self.assertTrue(applied["applied"])
        self.assertEqual(applied["active_layout"], "xdg-v1")
        migrated_agenda = self.root / "data" / "orp" / "agenda.json"
        migrated_workspace = self.root / "data" / "orp" / "workspaces" / "main.json"
        self.assertEqual(migrated_agenda.read_bytes(), (legacy / "agenda.json").read_bytes())
        self.assertEqual(migrated_workspace.read_bytes(), workspace.read_bytes())
        self.assertTrue((legacy / "agenda.json").exists())
        self.assertTrue((legacy / "human-note.txt").exists())
        self.assertEqual(migrated_agenda.stat().st_mode & 0o777, 0o600)

    def test_migration_refuses_changed_target(self) -> None:
        legacy = self.root / "config" / "orp"
        legacy.mkdir(parents=True)
        (legacy / "agenda.json").write_text('{"source":true}\n', encoding="utf-8")
        target = self.root / "data" / "orp" / "agenda.json"
        target.parent.mkdir(parents=True)
        target.write_text('{"target":true}\n', encoding="utf-8")

        plan = self.module._build_storage_migration_plan()
        self.assertFalse(plan["can_apply"])
        self.assertEqual(len(plan["conflicts"]), 1)
        with self.assertRaisesRegex(RuntimeError, "target conflicts"):
            self.module._apply_storage_migration(plan, plan["plan_id"])

    def test_compaction_requires_exact_plan_and_archives_before_removal(self) -> None:
        config = self.module._local_config_template(layout="xdg-v1")
        config["storage"]["retention"] = {
            "cache_days": 30,
            "backup_days": 90,
            "backup_keep": 1,
        }
        self.module._write_json(self.module._local_config_path(), config)

        data_root = self.root / "data" / "orp"
        data_root.mkdir(parents=True)
        newest = data_root / "agenda.json.bak-new"
        expired = data_root / "agenda.json.bak-old"
        newest.write_text("new\n", encoding="utf-8")
        expired.write_text("old\n", encoding="utf-8")
        cache_file = self.root / "cache" / "orp" / "responses" / "old.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_text("{}\n", encoding="utf-8")
        codex_file = self.root / "home" / ".codex" / "sessions" / "rollout-private.jsonl"
        codex_file.parent.mkdir(parents=True)
        codex_file.write_text("private transcript\n", encoding="utf-8")

        old = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).timestamp()
        recent = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc).timestamp()
        os.utime(expired, (old, old))
        os.utime(cache_file, (old, old))
        os.utime(newest, (recent, recent))
        now = dt.datetime(2026, 8, 23, tzinfo=dt.timezone.utc)

        first = self.module._build_storage_compaction_plan(now)
        second = self.module._build_storage_compaction_plan(now)
        self.assertEqual(first["plan_id"], second["plan_id"])
        self.assertEqual(first["operation_count"], 2)
        self.assertFalse(first["codex_storage_scanned"])
        self.assertNotIn(str(codex_file), json.dumps(first))
        with self.assertRaisesRegex(RuntimeError, "exactly match"):
            self.module._apply_storage_compaction(first, "wrong-plan")

        applied = self.module._apply_storage_compaction(first, first["plan_id"])
        self.assertTrue(applied["archive_created"])
        self.assertFalse(expired.exists())
        self.assertFalse(cache_file.exists())
        self.assertTrue(newest.exists())
        self.assertTrue(codex_file.exists())
        archive = Path(applied["archive_path"])
        self.assertTrue(archive.exists())
        self.module._verify_compaction_archive(archive, first)


if __name__ == "__main__":
    unittest.main()
