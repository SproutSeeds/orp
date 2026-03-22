from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD = REPO_ROOT / "scripts" / "npm-prepublish-guard.js"


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=str(root),
    )


def _git_init_main(root: Path) -> None:
    proc = _run_git(root, "init", "-b", "main")
    if proc.returncode == 0:
        return
    proc = _run_git(root, "init")
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + "\n" + proc.stdout)
    proc = _run_git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + "\n" + proc.stdout)


def _git_config_identity(root: Path) -> None:
    for key, value in [("user.name", "ORP Test"), ("user.email", "orp-test@example.com")]:
        proc = _run_git(root, "config", key, value)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr + "\n" + proc.stdout)


def _git_commit_all(root: Path, message: str) -> None:
    _git_config_identity(root)
    proc = _run_git(root, "add", "-A")
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + "\n" + proc.stdout)
    proc = _run_git(root, "commit", "-m", message)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + "\n" + proc.stdout)


def _git_init_bare(root: Path) -> None:
    proc = subprocess.run(
        ["git", "init", "--bare"],
        capture_output=True,
        text=True,
        cwd=str(root),
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + "\n" + proc.stdout)


class NpmPublishGuardTests(unittest.TestCase):
    def test_guard_blocks_dirty_worktree(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node not found on PATH")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init_main(root)
            (root / "README.md").write_text("clean\n", encoding="utf-8")
            _git_commit_all(root, "initial")
            (root / "README.md").write_text("dirty\n", encoding="utf-8")

            proc = subprocess.run(
                ["node", str(GUARD)],
                capture_output=True,
                text=True,
                cwd=str(root),
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("working tree is not clean", proc.stderr)

    def test_guard_blocks_unpushed_clean_head(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node not found on PATH")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init_main(root)
            (root / "README.md").write_text("clean\n", encoding="utf-8")
            _git_commit_all(root, "initial")

            proc = subprocess.run(
                ["node", str(GUARD)],
                capture_output=True,
                text=True,
                cwd=str(root),
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("not present on any remote branch", proc.stderr)

    def test_guard_allows_clean_pushed_head(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node not found on PATH")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "repo"
            remote = Path(td) / "remote.git"
            root.mkdir(parents=True, exist_ok=True)
            remote.mkdir(parents=True, exist_ok=True)
            _git_init_main(root)
            _git_init_bare(remote)
            (root / "README.md").write_text("clean\n", encoding="utf-8")
            _git_commit_all(root, "initial")

            add_remote = _run_git(root, "remote", "add", "origin", str(remote))
            self.assertEqual(add_remote.returncode, 0, msg=add_remote.stderr + "\n" + add_remote.stdout)
            push = _run_git(root, "push", "-u", "origin", "main")
            self.assertEqual(push.returncode, 0, msg=push.stderr + "\n" + push.stdout)

            proc = subprocess.run(
                ["node", str(GUARD)],
                capture_output=True,
                text=True,
                cwd=str(root),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)


if __name__ == "__main__":
    unittest.main()
