"""Per-test user state and external-effect guards for unittest discovery."""
from contextlib import ExitStack
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from guard.orp_test_safety import guarded


class IsolatedTestCase(unittest.TestCase):
    # Historical fixtures exercise the legacy layout explicitly. Tests of fresh
    # layout selection clear the environment and provide all four XDG homes.
    storage_layout = "legacy-v0"

    def run(self, result=None):
        with tempfile.TemporaryDirectory(prefix="orp-test-") as directory, ExitStack() as stack:
            root = Path(directory)
            temporary = root / "tmp"
            temporary.mkdir()
            env = {
                "PATH": os.environ.get("PATH", os.defpath),
                "HOME": str(root / "home"),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"),
                "XDG_STATE_HOME": str(root / "state"),
                "XDG_CACHE_HOME": str(root / "cache"),
                "TMPDIR": str(temporary),
                "TMP": str(temporary),
                "TEMP": str(temporary),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": str(root / "gitconfig"),
                "NPM_CONFIG_USERCONFIG": str(root / "npmrc"),
                "NPM_CONFIG_GLOBALCONFIG": str(root / "npm-globalrc"),
                "NPM_CONFIG_CACHE": str(root / "npm-cache"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "ORP_PYTHON": sys.executable,
                "PYTHONPATH": str(Path(__file__).parent / "guard"),
                "ORP_TEST_GUARD": "1",
                "ORP_TEST_ROOT": str(root),
                "LANG": "C.UTF-8",
            }
            if self.storage_layout:
                env["ORP_STORAGE_LAYOUT"] = self.storage_layout
            if os.name == "nt":
                for key in ("SYSTEMROOT", "COMSPEC", "PATHEXT"):
                    if key in os.environ:
                        env[key] = os.environ[key]
            (root / "home").mkdir()
            (root / "npmrc").touch()
            (root / "npm-globalrc").touch()
            (root / "gitconfig").touch()
            stack.enter_context(mock.patch.dict(os.environ, env, clear=True))
            stack.enter_context(mock.patch.object(tempfile, "tempdir", str(temporary)))
            stack.enter_context(guarded())
            return super().run(result)
