from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def _run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--repo-root",
            str(root),
            *args,
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


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
    proc = _run_git(root, "config", "user.name", "ORP Test")
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + "\n" + proc.stdout)
    proc = _run_git(root, "config", "user.email", "orp-test@example.com")
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + "\n" + proc.stdout)


def _git_init_bare(root: Path) -> None:
    proc = _run_git(root, "init", "--bare")
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


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class OrpInitTests(unittest.TestCase):
    def test_init_json_bootstraps_git_and_governance_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = _run_cli(root, "init", "--json")
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["config_action"], "created")
            self.assertTrue(payload["git"]["present"])
            self.assertTrue(payload["git"]["initialized_by_orp"])
            self.assertEqual(payload["git"]["git_init_method"], "git init -b")
            self.assertEqual(payload["git"]["branch"], "main")
            self.assertEqual(payload["git"]["default_branch"], "main")
            self.assertTrue(payload["git"]["protected_branch"])
            self.assertTrue(payload["git"]["work_branch_required"])
            self.assertTrue(payload["git"]["dirty"])
            self.assertEqual(payload["git"]["effective_remote_mode"], "local_only")
            self.assertEqual(payload["files"]["governance_manifest"]["path"], "orp/governance.json")
            self.assertEqual(payload["files"]["agent_policy"]["path"], "orp/agent-policy.json")
            self.assertEqual(payload["files"]["handoff"]["path"], "orp/HANDOFF.md")
            self.assertEqual(payload["files"]["checkpoint_log"]["path"], "orp/checkpoints/CHECKPOINT_LOG.md")
            self.assertEqual(payload["files"]["starter_kernel"]["path"], "analysis/orp.kernel.task.yml")
            self.assertIn("agents", payload)
            self.assertEqual(payload["agents"]["role"], "project")
            self.assertTrue(any("protected" in row for row in payload["warnings"]))
            self.assertTrue(any("dirty" in row for row in payload["warnings"]))

            self.assertTrue((root / "orp.yml").exists())
            self.assertTrue((root / "orp" / "governance.json").exists())
            self.assertTrue((root / "orp" / "agent-policy.json").exists())
            self.assertTrue((root / "orp" / "HANDOFF.md").exists())
            self.assertTrue((root / "orp" / "checkpoints" / "CHECKPOINT_LOG.md").exists())
            self.assertTrue((root / "analysis" / "orp.kernel.task.yml").exists())
            self.assertTrue((root / "AGENTS.md").exists())
            self.assertTrue((root / "CLAUDE.md").exists())
            self.assertIn("<!-- ORP:AGENT_GUIDE:BEGIN -->", (root / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertIn("<!-- ORP:BEGIN -->", (root / "AGENTS.md").read_text(encoding="utf-8"))

            state = json.loads((root / "orp" / "state.json").read_text(encoding="utf-8"))
            self.assertTrue(state["governance"]["orp_governed"])
            self.assertEqual(state["governance"]["mode"], "repo_governance")
            self.assertEqual(state["governance"]["default_branch"], "main")
            self.assertEqual(state["governance"]["manifest_path"], "orp/governance.json")

            branch = _run_git(root, "symbolic-ref", "--short", "HEAD")
            self.assertEqual(branch.returncode, 0, msg=branch.stderr + "\n" + branch.stdout)
            self.assertEqual(branch.stdout.strip(), "main")

    def test_init_json_detects_existing_origin_on_feature_branch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init_main(root)
            proc = _run_git(root, "checkout", "-b", "feature/safe")
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            proc = _run_git(root, "remote", "add", "origin", "https://github.com/example/demo.git")
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            init_proc = _run_cli(root, "init", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            payload = json.loads(init_proc.stdout)
            self.assertFalse(payload["git"]["initialized_by_orp"])
            self.assertEqual(payload["git"]["branch"], "feature/safe")
            self.assertFalse(payload["git"]["protected_branch"])
            self.assertFalse(payload["git"]["work_branch_required"])
            self.assertTrue(payload["git"]["working_branch_safe"])
            self.assertEqual(payload["git"]["detected_remote_url"], "https://github.com/example/demo.git")
            self.assertEqual(payload["git"]["effective_remote_mode"], "github")
            self.assertEqual(payload["git"]["effective_remote_url"], "https://github.com/example/demo.git")
            self.assertEqual(payload["git"]["effective_github_repo"], "example/demo")
            self.assertTrue(any("GitHub remote context recorded" in row for row in payload["notes"]))

    def test_init_json_keeps_handoff_on_rerun_and_accepts_explicit_github_repo(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = _run_cli(root, "init", "--github-repo", "owner/repo", "--json")
            self.assertEqual(first.returncode, 0, msg=first.stderr + "\n" + first.stdout)

            handoff_path = root / "orp" / "HANDOFF.md"
            handoff_path.write_text("# custom handoff\n", encoding="utf-8")

            second = _run_cli(root, "init", "--github-repo", "owner/repo", "--json")
            self.assertEqual(second.returncode, 0, msg=second.stderr + "\n" + second.stdout)

            payload = json.loads(second.stdout)
            self.assertEqual(payload["files"]["handoff"]["action"], "kept")
            self.assertEqual(handoff_path.read_text(encoding="utf-8"), "# custom handoff\n")
            self.assertEqual(payload["git"]["effective_remote_mode"], "github")
            self.assertEqual(payload["git"]["effective_github_repo"], "owner/repo")
            self.assertEqual(payload["git"]["effective_remote_url"], "https://github.com/owner/repo.git")
            self.assertEqual(payload["files"]["governance_manifest"]["action"], "updated")
            self.assertEqual(payload["files"]["agent_policy"]["action"], "updated")

    def test_status_json_reports_governance_paths_and_branch_safety(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_proc = _run_cli(root, "init", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            status_proc = _run_cli(root, "status", "--json")
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)

            payload = json.loads(status_proc.stdout)
            self.assertTrue(payload["orp_governed"])
            self.assertEqual(payload["mode"], "repo_governance")
            self.assertEqual(payload["config_path"], "orp.yml")
            self.assertEqual(payload["handoff_path"], "orp/HANDOFF.md")
            self.assertEqual(payload["checkpoint_log_path"], "orp/checkpoints/CHECKPOINT_LOG.md")
            self.assertTrue(payload["agent_policy_exists"])
            self.assertTrue(payload["manifest_exists"])
            self.assertTrue(payload["git"]["present"])
            self.assertEqual(payload["git"]["branch"], "main")
            self.assertTrue(payload["git"]["protected_branch"])
            self.assertTrue(payload["git"]["work_branch_required"])
            self.assertTrue(payload["git"]["dirty"])
            self.assertEqual(payload["git"]["effective_remote_mode"], "local_only")
            self.assertTrue(payload["git_runtime_path"].endswith(".git/orp/runtime.json"))
            self.assertIn("orp branch start <topic>", payload["next_actions"])
            self.assertIn('orp checkpoint create -m "describe completed unit"', payload["next_actions"])

    def test_branch_start_requires_clean_tree_by_default_then_records_transition(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_proc = _run_cli(root, "init", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            blocked = _run_cli(root, "branch", "start", "feature/safe-branch", "--json")
            self.assertEqual(blocked.returncode, 2, msg=blocked.stderr + "\n" + blocked.stdout)
            self.assertIn("working tree is dirty", blocked.stderr)

            _git_commit_all(root, "bootstrap governance runtime")

            branch_proc = _run_cli(root, "branch", "start", "feature/safe-branch", "--json")
            self.assertEqual(branch_proc.returncode, 0, msg=branch_proc.stderr + "\n" + branch_proc.stdout)

            payload = json.loads(branch_proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["action"], "created")
            self.assertEqual(payload["branch"], "feature/safe-branch")
            self.assertEqual(payload["previous_branch"], "main")
            self.assertFalse(payload["dirty_before"])
            self.assertTrue(payload["ready_for_agent_work"])

            branch = _run_git(root, "symbolic-ref", "--short", "HEAD")
            self.assertEqual(branch.returncode, 0, msg=branch.stderr + "\n" + branch.stdout)
            self.assertEqual(branch.stdout.strip(), "feature/safe-branch")

            status_proc = _run_cli(root, "status", "--json")
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            status_payload = json.loads(status_proc.stdout)
            self.assertEqual(status_payload["runtime"]["last_branch_action"]["action"], "created")
            self.assertEqual(status_payload["runtime"]["last_branch_action"]["to_branch"], "feature/safe-branch")

    def test_backup_auto_branches_dirty_main_and_pushes_remote_backup_ref(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            remote = root / "remote.git"
            remote.mkdir(parents=True, exist_ok=True)
            _git_init_bare(remote)

            init_proc = _run_cli(root, "init", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)
            _git_config_identity(root)

            remote_add = _run_git(root, "remote", "add", "origin", str(remote))
            self.assertEqual(remote_add.returncode, 0, msg=remote_add.stderr + "\n" + remote_add.stdout)

            status_proc = _run_cli(root, "status", "--json")
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            status_payload = json.loads(status_proc.stdout)
            self.assertIn('orp backup -m "backup current work" --json', status_payload["next_actions"])

            backup_proc = _run_cli(root, "backup", "-m", "backup initial governance", "--json")
            self.assertEqual(backup_proc.returncode, 0, msg=backup_proc.stderr + "\n" + backup_proc.stdout)

            payload = json.loads(backup_proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["backup_scope"], "remote")
            self.assertTrue(payload["dirty_before"])
            self.assertTrue(payload["checkpoint_created"])
            self.assertTrue(payload["pushed_remote"])
            self.assertTrue(payload["auto_branch_created"])
            self.assertTrue(payload["branch"].startswith("work/backup-main-"))
            self.assertTrue(payload["backup_ref"].startswith("orp/backup/"))

            branch = _run_git(root, "symbolic-ref", "--short", "HEAD")
            self.assertEqual(branch.returncode, 0, msg=branch.stderr + "\n" + branch.stdout)
            self.assertEqual(branch.stdout.strip(), payload["branch"])

            remote_refs = _run_git(remote, "for-each-ref", "refs/heads", "--format=%(refname:short)")
            self.assertEqual(remote_refs.returncode, 0, msg=remote_refs.stderr + "\n" + remote_refs.stdout)
            self.assertIn(payload["backup_ref"], {line.strip() for line in remote_refs.stdout.splitlines() if line.strip()})

            refreshed_status = _run_cli(root, "status", "--json")
            self.assertEqual(refreshed_status.returncode, 0, msg=refreshed_status.stderr + "\n" + refreshed_status.stdout)
            refreshed_payload = json.loads(refreshed_status.stdout)
            self.assertEqual(refreshed_payload["runtime"]["last_backup"]["backup_ref"], payload["backup_ref"])
            self.assertEqual(refreshed_payload["runtime"]["last_backup"]["backup_scope"], "remote")

    def test_backup_local_only_creates_checkpoint_without_push(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_proc = _run_cli(root, "init", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)
            _git_config_identity(root)

            backup_proc = _run_cli(root, "backup", "-m", "local backup only", "--json")
            self.assertEqual(backup_proc.returncode, 0, msg=backup_proc.stderr + "\n" + backup_proc.stdout)

            payload = json.loads(backup_proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["backup_scope"], "local_only")
            self.assertTrue(payload["dirty_before"])
            self.assertTrue(payload["checkpoint_created"])
            self.assertFalse(payload["pushed_remote"])
            self.assertTrue(payload["auto_branch_created"])
            self.assertIn("git remote add origin <url>", payload["next_actions"])

    def test_checkpoint_create_commits_log_and_updates_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_proc = _run_cli(root, "init", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            _git_config_identity(root)
            branch_proc = _run_cli(root, "branch", "start", "feature/checkpoint", "--allow-dirty", "--json")
            self.assertEqual(branch_proc.returncode, 0, msg=branch_proc.stderr + "\n" + branch_proc.stdout)

            checkpoint_proc = _run_cli(
                root,
                "checkpoint",
                "create",
                "-m",
                "bootstrap governance checkpoint",
                "--json",
            )
            self.assertEqual(
                checkpoint_proc.returncode,
                0,
                msg=checkpoint_proc.stderr + "\n" + checkpoint_proc.stdout,
            )

            payload = json.loads(checkpoint_proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["branch"], "feature/checkpoint")
            self.assertEqual(payload["commit_message"], "checkpoint: bootstrap governance checkpoint")
            self.assertEqual(payload["checkpoint_log_path"], "orp/checkpoints/CHECKPOINT_LOG.md")
            self.assertTrue(payload["ready_for_agent_work"])

            head = _run_git(root, "log", "-1", "--pretty=%s")
            self.assertEqual(head.returncode, 0, msg=head.stderr + "\n" + head.stdout)
            self.assertEqual(head.stdout.strip(), "checkpoint: bootstrap governance checkpoint")

            status_proc = _run_cli(root, "status", "--json")
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            status_payload = json.loads(status_proc.stdout)
            self.assertEqual(status_payload["runtime"]["last_checkpoint"]["commit"], payload["commit"])
            self.assertEqual(
                status_payload["runtime"]["last_checkpoint"]["commit_message"],
                "checkpoint: bootstrap governance checkpoint",
            )
            self.assertTrue(status_payload["ready_for_agent_work"])

            checkpoint_log = (root / "orp" / "checkpoints" / "CHECKPOINT_LOG.md").read_text(encoding="utf-8")
            self.assertIn("bootstrap governance checkpoint", checkpoint_log)
            self.assertIn("feature/checkpoint", checkpoint_log)

    def test_ready_uses_latest_passing_validation_and_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_proc = _run_cli(root, "init", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            _git_config_identity(root)
            branch_proc = _run_cli(root, "branch", "start", "feature/ready", "--allow-dirty", "--json")
            self.assertEqual(branch_proc.returncode, 0, msg=branch_proc.stderr + "\n" + branch_proc.stdout)

            bootstrap_checkpoint = _run_cli(
                root,
                "checkpoint",
                "create",
                "-m",
                "bootstrap ready branch",
                "--json",
            )
            self.assertEqual(
                bootstrap_checkpoint.returncode,
                0,
                msg=bootstrap_checkpoint.stderr + "\n" + bootstrap_checkpoint.stdout,
            )

            run_proc = _run_cli(root, "gate", "run", "--profile", "default", "--json")
            self.assertEqual(run_proc.returncode, 0, msg=run_proc.stderr + "\n" + run_proc.stdout)
            run_payload = json.loads(run_proc.stdout)
            self.assertEqual(run_payload["overall"], "PASS")
            run_record = json.loads((root / run_payload["run_record"]).read_text(encoding="utf-8"))
            kernel_result = next(
                row for row in run_record["results"] if row.get("phase") == "structure_kernel"
            )
            self.assertTrue(kernel_result["kernel_validation"]["valid"])
            self.assertEqual(kernel_result["kernel_validation"]["mode"], "hard")

            ready_checkpoint = _run_cli(
                root,
                "checkpoint",
                "create",
                "-m",
                "capture passing validation",
                "--json",
            )
            self.assertEqual(
                ready_checkpoint.returncode,
                0,
                msg=ready_checkpoint.stderr + "\n" + ready_checkpoint.stdout,
            )

            ready_proc = _run_cli(root, "ready", "--json")
            self.assertEqual(ready_proc.returncode, 0, msg=ready_proc.stderr + "\n" + ready_proc.stdout)

            payload = json.loads(ready_proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["run_id"], run_payload["run_id"])
            self.assertTrue(payload["local_ready"])
            self.assertTrue(payload["remote_ready"])
            self.assertEqual(payload["scope"], "local_only")

            status_proc = _run_cli(root, "status", "--json")
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            status_payload = json.loads(status_proc.stdout)
            self.assertTrue(status_payload["readiness"]["local_ready"])
            self.assertTrue(status_payload["readiness"]["remote_ready"])
            self.assertEqual(status_payload["runtime"]["last_ready"]["run_id"], run_payload["run_id"])
            self.assertEqual(status_payload["runtime"]["latest_run"]["overall"], "PASS")
            self.assertTrue(status_payload["validation"]["checkpoint_after_validation"])

    def test_doctor_fix_recreates_missing_governance_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_proc = _run_cli(root, "init", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            (root / "orp" / "HANDOFF.md").unlink()
            (root / "orp" / "agent-policy.json").unlink()
            (root / "analysis" / "orp.kernel.task.yml").unlink()

            doctor_proc = _run_cli(root, "doctor", "--json")
            self.assertEqual(doctor_proc.returncode, 1, msg=doctor_proc.stderr + "\n" + doctor_proc.stdout)
            doctor_payload = json.loads(doctor_proc.stdout)
            codes = {issue["code"] for issue in doctor_payload["issues"]}
            self.assertIn("missing_handoff", codes)
            self.assertIn("missing_agent_policy", codes)

            fix_proc = _run_cli(root, "doctor", "--fix", "--json")
            self.assertEqual(fix_proc.returncode, 0, msg=fix_proc.stderr + "\n" + fix_proc.stdout)
            fix_payload = json.loads(fix_proc.stdout)
            self.assertTrue(fix_payload["ok"])
            self.assertIn("created_handoff", fix_payload["fixes_applied"])
            self.assertIn("synced_agent_policy", fix_payload["fixes_applied"])
            self.assertIn("created_starter_kernel", fix_payload["fixes_applied"])
            self.assertTrue((root / "orp" / "HANDOFF.md").exists())
            self.assertTrue((root / "orp" / "agent-policy.json").exists())
            self.assertTrue((root / "analysis" / "orp.kernel.task.yml").exists())

    def test_cleanup_suggests_and_deletes_merged_work_branch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_proc = _run_cli(root, "init", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            _git_commit_all(root, "bootstrap governance runtime")
            branch_proc = _run_cli(root, "branch", "start", "feature/cleanup", "--json")
            self.assertEqual(branch_proc.returncode, 0, msg=branch_proc.stderr + "\n" + branch_proc.stdout)

            _write_file(root / "feature.txt", "cleanup candidate\n")
            _git_commit_all(root, "feature cleanup work")

            checkout_main = _run_git(root, "checkout", "main")
            self.assertEqual(checkout_main.returncode, 0, msg=checkout_main.stderr + "\n" + checkout_main.stdout)
            merge_proc = _run_git(root, "merge", "--ff-only", "feature/cleanup")
            self.assertEqual(merge_proc.returncode, 0, msg=merge_proc.stderr + "\n" + merge_proc.stdout)

            cleanup_proc = _run_cli(root, "cleanup", "--json")
            self.assertEqual(cleanup_proc.returncode, 0, msg=cleanup_proc.stderr + "\n" + cleanup_proc.stdout)
            cleanup_payload = json.loads(cleanup_proc.stdout)
            branch_rows = {row["branch"]: row for row in cleanup_payload["candidates"]}
            self.assertIn("feature/cleanup", branch_rows)
            self.assertTrue(branch_rows["feature/cleanup"]["safe_delete"])
            self.assertIn("merged_into_default_branch", branch_rows["feature/cleanup"]["reasons"])

            apply_proc = _run_cli(root, "cleanup", "--apply", "--delete-merged", "--json")
            self.assertEqual(apply_proc.returncode, 0, msg=apply_proc.stderr + "\n" + apply_proc.stdout)
            apply_payload = json.loads(apply_proc.stdout)
            self.assertIn("feature/cleanup", apply_payload["deleted_branches"])

            branch_check = _run_git(root, "branch", "--list", "feature/cleanup")
            self.assertEqual(branch_check.returncode, 0, msg=branch_check.stderr + "\n" + branch_check.stdout)
            self.assertEqual(branch_check.stdout.strip(), "")

    def test_status_json_reports_remote_tracking_counts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            remote_root = Path(td) / "remote.git"
            remote_proc = subprocess.run(
                ["git", "init", "--bare", str(remote_root)],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(remote_proc.returncode, 0, msg=remote_proc.stderr + "\n" + remote_proc.stdout)

            _git_init_main(root)
            _git_config_identity(root)
            _write_file(root / "seed.txt", "seed\n")
            _git_commit_all(root, "seed")
            add_remote = _run_git(root, "remote", "add", "origin", str(remote_root))
            self.assertEqual(add_remote.returncode, 0, msg=add_remote.stderr + "\n" + add_remote.stdout)
            push_main = _run_git(root, "push", "-u", "origin", "main")
            self.assertEqual(push_main.returncode, 0, msg=push_main.stderr + "\n" + push_main.stdout)
            set_remote_head = subprocess.run(
                ["git", "symbolic-ref", "HEAD", "refs/heads/main"],
                capture_output=True,
                text=True,
                cwd=str(remote_root),
            )
            self.assertEqual(
                set_remote_head.returncode,
                0,
                msg=set_remote_head.stderr + "\n" + set_remote_head.stdout,
            )
            set_head = _run_git(root, "remote", "set-head", "origin", "-a")
            self.assertEqual(set_head.returncode, 0, msg=set_head.stderr + "\n" + set_head.stdout)

            checkout_feature = _run_git(root, "checkout", "-b", "feature/remote")
            self.assertEqual(checkout_feature.returncode, 0, msg=checkout_feature.stderr + "\n" + checkout_feature.stdout)
            _write_file(root / "remote.txt", "one\n")
            _git_commit_all(root, "remote one")
            push_feature = _run_git(root, "push", "-u", "origin", "feature/remote")
            self.assertEqual(push_feature.returncode, 0, msg=push_feature.stderr + "\n" + push_feature.stdout)
            _write_file(root / "remote.txt", "two\n")
            _git_commit_all(root, "remote two")

            init_proc = _run_cli(root, "init", "--json")
            self.assertEqual(init_proc.returncode, 0, msg=init_proc.stderr + "\n" + init_proc.stdout)

            status_proc = _run_cli(root, "status", "--json")
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            payload = json.loads(status_proc.stdout)
            self.assertEqual(payload["git"]["effective_remote_mode"], "remote")
            self.assertEqual(payload["git"]["upstream_branch"], "origin/feature/remote")
            self.assertEqual(payload["git"]["remote_default_branch"], "main")
            self.assertEqual(payload["git"]["ahead_count"], 1)
            self.assertEqual(payload["git"]["behind_count"], 0)
            self.assertIn("non-GitHub remote awareness active", "\n".join(payload["notes"]))


if __name__ == "__main__":
    unittest.main()
