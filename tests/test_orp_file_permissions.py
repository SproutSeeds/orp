from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock


CLI = Path(__file__).resolve().parents[1] / "cli" / "orp.py"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_file_permissions_test", CLI)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load ORP CLI module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORP = _load_cli_module()


class OrpFilePermissionTests(unittest.TestCase):
    def test_user_config_json_is_atomic_and_private_independent_of_umask(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config_home = Path(td) / "config"
            target = config_home / "orp" / "nested" / "session.json"
            original_umask = os.umask(0)
            try:
                with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config_home)}):
                    ORP._write_json(target, {"token": "first"})
                    os.chmod(target, 0o666)
                    ORP._write_json(target, {"token": "replacement"})
            finally:
                os.umask(original_umask)

            self.assertEqual(stat.S_IMODE((config_home / "orp").stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(target.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"token": "replacement"})
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
