from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile
import hashlib
from contextlib import redirect_stdout
from unittest import mock

from orp_test_support import IsolatedTestCase

ROOT = Path(__file__).resolve().parents[1]


class StorageRegressionTests(IsolatedTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = {key: value for key, value in os.environ.items() if key != "ORP_STORAGE_LAYOUT"}
        self.env.update({f"XDG_{key}_HOME": str(self.root / key.lower()) for key in ("CONFIG", "DATA", "STATE", "CACHE")})
        self.environment = mock.patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        spec = importlib.util.spec_from_file_location("orp_storage_regressions", ROOT / "cli/orp.py")
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.legacy = self.root / "config/orp"
        self.data = self.root / "data/orp"

    def fixture(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.JSONEncoder(indent=2).encode(value) + "\n")
        return path

    def node(self, body, **overrides):
        module = (ROOT / "packages/orp-workspace-launcher/src/index.js").as_uri()
        script = f"import * as orp from {json.JSONEncoder().encode(module)};\n" + body
        result = subprocess.run([shutil.which("node"), "--input-type=module", "-e", script], env={**self.env, **overrides}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_first_data_and_agents_writes_pin_the_same_layout_in_both_runtimes(self):
        agenda = self.cli._orp_storage_file("data", "agenda.json")
        self.cli._write_json(agenda, {"items": ["retained"]})
        self.cli._write_json(self.legacy / "agents.json", {"version": "1"})
        self.assertEqual(self.cli._orp_storage_layout(), "xdg-v1")
        self.assertEqual(self.node("console.log(orp.getStorageLayout());").strip(), "xdg-v1")
        self.assertEqual(json.loads(agenda.read_text())["items"], ["retained"])

    def test_legacy_compaction_preserves_active_unknown_and_archive_files(self):
        self.fixture(self.legacy / "config.json", self.cli._local_config_template(layout="legacy-v0"))
        retained = ["agenda.json", "workspaces/main.json", "secrets-keychain.json", "custom-record.json", "archives/retained.tar.gz", "custom-record.json.bak-old", "custom-record.json.bak-new"]
        for name in retained:
            self.fixture(self.legacy / name, {"keep": name})
        cache = self.fixture(self.legacy / "cache/responses/old.json", {"cached": True})
        for file in self.legacy.rglob("*"):
            if file.is_file():
                os.utime(file, (1_600_000_000, 1_600_000_000))
        before = {name: (self.legacy / name).read_bytes() for name in ["config.json", *retained]}
        plan = self.cli._build_storage_compaction_plan()
        self.assertEqual([row["path"] for row in plan["operations"]], [str(cache)])
        result = self.cli._apply_storage_compaction(plan, plan["plan_id"])
        self.assertEqual(result["removed_count"], 1)
        self.cli._verify_compaction_archive(Path(result["archive_path"]), plan)
        self.assertEqual({name: (self.legacy / name).read_bytes() for name in before}, before)
        restore = self.cli._build_storage_restore_plan(Path(result["archive_path"]), "legacy-v0")
        self.fixture(cache, {"newer": True})
        conflict = self.cli._build_storage_restore_plan(Path(result["archive_path"]), "legacy-v0")
        self.assertFalse(conflict["can_apply"])
        with self.assertRaisesRegex(RuntimeError, "conflicts"):
            self.cli._apply_storage_restore(restore, restore["plan_id"])
        self.assertTrue(json.loads(cache.read_text())["newer"])
        cache.unlink()
        restored = self.cli._apply_storage_restore(restore, restore["plan_id"])
        self.assertEqual(restored["restored_count"], 1)
        self.assertTrue(json.loads(cache.read_text())["cached"])

    def test_overlapping_xdg_roots_refuse_migration_and_compaction(self):
        self.fixture(self.legacy / "config.json", self.cli._local_config_template())
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.root / "data")}):
            compact = self.cli._build_storage_compaction_plan()
            migrate = self.cli._build_storage_migration_plan()
            self.assertFalse(compact["can_apply"])
            self.assertFalse(migrate["can_apply"])
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                self.cli._apply_storage_compaction(compact, compact["plan_id"])

    def test_migration_rebases_slots_and_registry_and_future_edits_leave_legacy_frozen(self):
        first = str(self.root / "first")
        second = str(self.root / "second")
        output = self.node(f"const saved = await orp.cacheManagedWorkspaceManifest({{version:'1',workspaceId:'main',title:'main',tabs:[{{path:{json.JSONEncoder().encode(first)},title:'first'}}]}}); await orp.setWorkspaceSlot('main', {{kind:'workspace-file',manifestPath:saved.manifestPath,selector:saved.manifestPath}}); console.log(saved.manifestPath);", ORP_STORAGE_LAYOUT="legacy-v0")
        legacy_manifest = Path(output.strip())
        original = legacy_manifest.read_bytes()
        plan = self.cli._build_storage_migration_plan()
        self.assertTrue(any(row["rewrites"] for row in plan["operations"]))
        result = self.cli._apply_storage_migration(plan, plan["plan_id"])
        self.assertEqual(result["active_layout"], "xdg-v1")
        self.node(f"await orp.runWorkspaceAddTab(['main','--path',{json.JSONEncoder().encode(second)},'--title','second','--json']);")
        self.assertEqual(legacy_manifest.read_bytes(), original)
        moved = self.data / "workspaces" / legacy_manifest.name
        self.assertNotEqual(moved.read_bytes(), original)
        registry = json.loads((self.data / "workspace-registry.json").read_text())
        self.assertEqual(Path(registry["workspaces"][0]["manifestPath"]), moved)
        repeat = self.cli._build_storage_migration_plan()
        self.assertEqual(repeat["operations"], [])

    def test_migration_target_created_during_copy_is_never_clobbered(self):
        self.fixture(self.legacy / "agenda.json", {"source": True})
        plan = self.cli._build_storage_migration_plan()
        original_copy = self.cli._copy_file_atomic

        def race(source, target, **options):
            if target == self.data / "agenda.json":
                self.fixture(target, {"concurrent": True})
            return original_copy(source, target, **options)

        with mock.patch.object(self.cli, "_copy_file_atomic", side_effect=race):
            with self.assertRaises(FileExistsError):
                self.cli._apply_storage_migration(plan, plan["plan_id"])
        self.assertTrue(json.loads((self.data / "agenda.json").read_text())["concurrent"])
        self.assertEqual(self.cli._orp_storage_layout(), "legacy-v0")
        self.assertFalse((self.legacy / ".storage-write.lock").exists())

    def test_rc1_reference_repair_requires_reviewed_conflict_choice_and_keeps_backup(self):
        old = self.fixture(self.legacy / "workspaces/main.json", {"version": "1", "tabs": [{"title": "new legacy edit"}]})
        target = self.fixture(self.data / "workspaces/main.json", {"version": "1", "tabs": []})
        original_target = target.read_bytes()
        external = str(self.root / "external/user-workspace.json")
        self.fixture(self.data / "workspace-registry.json", {"version": "1", "workspaces": [{"manifestPath": str(old)}, {"manifestPath": external}]})
        self.fixture(self.legacy / "config.json", self.cli._local_config_template())
        self.assertFalse(self.cli._build_storage_migration_plan()["can_apply"])
        plan = self.cli._build_storage_migration_plan(prefer_legacy=True)
        self.assertTrue(plan["can_apply"])
        result = self.cli._apply_storage_migration(plan, plan["plan_id"])
        self.assertEqual(target.read_bytes(), old.read_bytes())
        backups = Path(result["journal_path"]).parent / "backups"
        self.assertIn(original_target, [p.read_bytes() for p in backups.iterdir()])
        rows = json.loads((self.data / "workspace-registry.json").read_text())["workspaces"]
        self.assertEqual(rows[0]["manifestPath"], str(target))
        self.assertEqual(rows[1]["manifestPath"], external)

    def test_interrupted_migration_reuses_verified_copy(self):
        first = self.fixture(self.legacy / "agenda.json", {"first": True})
        self.fixture(self.legacy / "connections.json", {"second": True})
        plan = self.cli._build_storage_migration_plan()
        original_copy = self.cli._copy_file_atomic

        def interrupt(source, target, **options):
            if target.name == "connections.json":
                raise OSError("injected interruption")
            return original_copy(source, target, **options)

        with mock.patch.object(self.cli, "_copy_file_atomic", side_effect=interrupt):
            with self.assertRaisesRegex(OSError, "interruption"):
                self.cli._apply_storage_migration(plan, plan["plan_id"])
        self.assertEqual(self.cli._orp_storage_layout(), "legacy-v0")
        self.assertEqual((self.data / "agenda.json").read_bytes(), first.read_bytes())
        retry = self.cli._build_storage_migration_plan()
        self.assertEqual(retry["already_copied_count"], 1)
        self.cli._apply_storage_migration(retry, retry["plan_id"])
        self.assertEqual(self.cli._orp_storage_layout(), "xdg-v1")

    def test_lock_recovery_refuses_a_live_owner_and_accepts_exact_dead_owner_plan(self):
        with self.cli._storage_write_lock():
            plan = self.cli._storage_unlock_plan()
            self.assertFalse(plan["can_apply"])
        lock = self.legacy / ".storage-write.lock"
        self.fixture(lock / "owner.json", {"pid": 99999999, "host": self.cli.platform.node()})
        with mock.patch.object(self.cli.os, "kill", side_effect=ProcessLookupError):
            plan = self.cli._storage_unlock_plan()
            with redirect_stdout(io.StringIO()):
                self.cli.cmd_storage_unlock(argparse.Namespace(apply=True, confirm=plan["plan_id"], json_output=True))
        self.assertFalse(lock.exists())

    def test_mixed_unselected_roots_require_explicit_reconciliation(self):
        self.fixture(self.legacy / "agenda.json", {"legacy": True})
        self.fixture(self.data / "agenda.json", {"xdg": True})
        with self.assertRaisesRegex(RuntimeError, "Both legacy and XDG"):
            self.cli._orp_storage_layout()
        plan = self.cli._build_storage_migration_plan()
        self.assertFalse(plan["can_apply"])
        self.assertTrue(self.cli._build_storage_migration_plan(prefer_legacy=True)["can_apply"])

    def test_source_changed_after_copy_prevents_layout_switch(self):
        source = self.fixture(self.legacy / "agenda.json", {"before": True})
        plan = self.cli._build_storage_migration_plan()
        original_copy = self.cli._copy_file_atomic

        def race(old, target, **options):
            original_copy(old, target, **options)
            self.fixture(source, {"after": True})

        with mock.patch.object(self.cli, "_copy_file_atomic", side_effect=race):
            with self.assertRaisesRegex(RuntimeError, "before selector"):
                self.cli._apply_storage_migration(plan, plan["plan_id"])
        self.assertEqual(self.cli._orp_storage_layout(), "legacy-v0")
        self.assertTrue(json.loads(source.read_text())["after"])

    def test_symlinked_target_directory_is_refused(self):
        self.fixture(self.legacy / "workspaces/main.json", {"tabs": []})
        outside = self.root / "outside"
        outside.mkdir()
        self.data.mkdir(parents=True)
        (self.data / "workspaces").symlink_to(outside, target_is_directory=True)
        plan = self.cli._build_storage_migration_plan()
        self.assertFalse(plan["can_apply"])
        self.assertTrue(any("symlink" in error for error in plan["errors"]))
        self.assertEqual(list(outside.iterdir()), [])

    def test_restore_rejects_archive_path_traversal_without_writing(self):
        archive_path = self.root / "untrusted.tar.gz"
        content = b"untrusted"
        row = {"category": "data", "relative_path": "../escape", "archive_member": "files/payload", "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        manifest = json.JSONEncoder().encode({"files": [row]}).encode()
        with tarfile.open(archive_path, "w:gz") as archive:
            for name, payload in [("MANIFEST.json", manifest), ("files/payload", content)]:
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            self.cli._build_storage_restore_plan(archive_path, "xdg-v1")
        self.assertFalse((self.root / "data/escape").exists())
