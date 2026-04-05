from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "orp-pack-install.py"
CLI = REPO_ROOT / "cli" / "orp.py"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))


def _run_cli(target: Path, config_name: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--repo-root",
            str(target),
            "--config",
            config_name,
            *args,
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _write_selected_problem_payload(target: Path, *, problem_id: int = 857, status_bucket: str = "open") -> Path:
    out_path = target / "analysis" / "erdos_problems" / "selected" / f"erdos_problem.{problem_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "selected_at_utc": "2026-03-07T09:15:00Z",
        "source": {
            "site": "erdosproblems.com",
            "url": f"https://erdosproblems.com/{problem_id}",
            "source_sha256": "abc123",
            "solve_count": {
                "raw": "0 solved out of 1 shown",
                "solved": 0,
                "shown": 1,
            },
        },
        "problem": {
            "problem_id": problem_id,
            "problem_url": f"/{problem_id}",
            "status_bucket": status_bucket,
            "status_dom_id": "open" if status_bucket == "open" else "solved",
            "status_label": status_bucket.upper(),
            "status_detail": "starter test payload",
            "prize_amount": "",
            "statement": "Show that every large enough family contains a sunflower.",
            "tags": ["Combinatorics"],
            "last_edited": "March 7, 2026",
            "latex_path": f"/latex/{problem_id}",
            "formalized": False,
            "formalized_url": "",
            "oeis_urls": [],
            "comments_problem_id": problem_id,
            "comments_count": 0,
        },
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out_path


def _git(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(["git", *cmd], cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr + "\n" + proc.stdout)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_fake_problem857_public_repo(root: Path) -> None:
    _write(root / "README.md", "# sunflower-lean test repo\n")
    _write(root / "AI_DISCLOSURE.md", "AI-assisted drafting; verified claims require local checks.\n")
    _write(root / "lean-toolchain", "leanprover/lean4:stable\n")
    _write(root / "lake-manifest.json", "{\n  \"version\": 7\n}\n")
    _write(root / "lakefile.toml", 'name = "SunflowerLean"\n')
    _write(root / "SunflowerLean.lean", "import SunflowerLean.Balance\n")
    _write(root / "lean-examples" / "Basic.lean", "def demo : Nat := 1\n")
    _write(root / "SunflowerLean" / "Balance.lean", "theorem placeholder : True := by trivial\n")
    _write(root / "SunflowerLean" / "BalanceCore.lean", "def balanceCore : Nat := 0\n")
    _write(root / "SunflowerLean" / "BalanceCasesA.lean", "def balanceCaseA : Nat := 0\n")
    _write(root / "SunflowerLean" / "BalanceCasesB.lean", "def balanceCaseB : Nat := 0\n")
    _write(root / "SunflowerLean" / "BalanceCandidatesA.lean", "def balanceCandidateA : Nat := 0\n")
    _write(root / "SunflowerLean" / "BalanceCandidatesB.lean", "def balanceCandidateB : Nat := 0\n")
    _write(root / "SunflowerLean" / "Container.lean", "def containerLemma : Nat := 0\n")
    _write(root / "SunflowerLean" / "LocalTuran.lean", "def localTuran : Nat := 0\n")
    _write(root / "SunflowerLean" / "Obstruction.lean", "def obstruction : Nat := 0\n")
    _write(root / "SunflowerLean" / "SATBridge.lean", "def satBridge : Nat := 0\n")
    _write(root / "SunflowerLean" / "UnionBounds.lean", "def unionBounds : Nat := 0\n")

    _git(["init", "-b", "main"], cwd=root)
    _git(["config", "user.name", "ORP Test"], cwd=root)
    _git(["config", "user.email", "orp@example.com"], cwd=root)
    _git(["add", "-A"], cwd=root)
    _git(["commit", "-m", "seed public problem857 repo"], cwd=root)


def _make_generic_local_pack(root: Path) -> Path:
    pack_root = root / "generic-local-pack"
    _write(
        pack_root / "pack.yml",
        """schema_version: "1.0.0"
pack_id: generic-local-pack
name: Generic Local Pack
version: "0.1.0"
description: >
  Small local pack used to verify that install metadata can live in pack.yml
  outside the ORP source tree.

variables:
  TARGET_REPO_ROOT:
    description: Absolute path to the working repo.
    required: true

templates:
  generic_local_profile:
    path: profiles/generic-local.yml.tmpl
    description: Minimal generic local verification profile.
    output_hint: orp.generic-local.yml
    default_profiles:
      - generic_local_flow

install:
  default_includes:
    - generic_profile
  report_name: orp.generic-local.pack-install-report.md
  components:
    generic_profile:
      template_id: generic_local_profile
      required_paths:
        - analysis/GENERIC_READY.md
""",
    )
    _write(
        pack_root / "profiles" / "generic-local.yml.tmpl",
        """version: "1"

project:
  name: generic-local-pack
  repo_root: .

runtime:
  shell: /bin/bash
  default_timeout_sec: 1200
  artifacts_root: orp/artifacts

packet:
  default_kind: verification
  output_dir: orp/packets
  write_markdown: true
  deterministic_mode: true

lifecycle:
  claim_status_map:
    Draft: draft
    Verified: reviewed
  atom_status_map:
    todo: draft
    done: reviewed

gates:
  - id: generic_gate
    description: Minimal generic verification gate.
    phase: verification
    command: >
      printf 'generic_gate=PASS\\n'
    working_dir: {{TARGET_REPO_ROOT}}
    pass:
      exit_codes: [0]
      stdout_must_contain:
        - generic_gate=PASS
    evidence:
      include_stdout: true
      include_stderr: true
    on_fail: stop

profiles:
  generic_local_flow:
    description: Minimal local flow for generic repo-owned pack validation.
    mode: collaboration
    packet_kind: verification
    gate_ids:
      - generic_gate
""",
    )
    return pack_root


class OrpPackInstallTests(unittest.TestCase):
    def test_pack_install_supports_repo_owned_pack_metadata_from_pack_yml(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack_root = _make_generic_local_pack(root)
            target = root / "target"
            _write(target / "analysis" / "GENERIC_READY.md", "# ready\n")

            install = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(REPO_ROOT),
                    "pack",
                    "install",
                    "--pack-path",
                    str(pack_root),
                    "--target-repo-root",
                    str(target),
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(install.returncode, 0, msg=install.stderr + "\n" + install.stdout)
            payload = json.loads(install.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["included_components"], ["generic_profile"])
            self.assertEqual(
                Path(payload["report"]).resolve(),
                (target / "orp.generic-local.pack-install-report.md").resolve(),
            )

            cfg = target / "orp.generic-local.yml"
            report = target / "orp.generic-local.pack-install-report.md"
            self.assertTrue(cfg.exists(), msg=f"missing rendered config: {cfg}")
            self.assertTrue(report.exists(), msg=f"missing report: {report}")
            self.assertIn("`generic_profile`", report.read_text(encoding="utf-8"))

            run = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(target),
                    "--config",
                    str(cfg),
                    "gate",
                    "run",
                    "--profile",
                    "generic_local_flow",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr + "\n" + run.stdout)
            self.assertIn("overall=PASS", run.stdout)

    def test_catalog_install_renders_config_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            proc = _run(
                [
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "catalog",
                ]
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            cfg = target / "orp.erdos-catalog-sync.yml"
            report = target / "orp.erdos.pack-install-report.md"
            self.assertTrue(cfg.exists(), msg=f"missing rendered config: {cfg}")
            self.assertTrue(report.exists(), msg=f"missing report: {report}")
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("`catalog`", report_text)
            self.assertIn("## Dependency Audit", report_text)
            self.assertIn("deps.missing_total=0", proc.stdout)

    def test_live_compare_strict_deps_fails_when_bootstrap_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            proc = _run(
                [
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "live_compare",
                    "--strict-deps",
                    "--no-bootstrap",
                ]
            )
            self.assertEqual(proc.returncode, 3, msg=proc.stderr)
            report = target / "orp.erdos.pack-install-report.md"
            self.assertTrue(report.exists(), msg=f"missing report: {report}")
            text = report.read_text(encoding="utf-8")
            self.assertIn("analysis/problem857_counting_gateboard.json", text)
            self.assertIn("scripts/problem857_ops_board.py", text)

    def test_live_compare_bootstrap_is_install_and_go(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            install = _run(
                [
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "live_compare",
                ]
            )
            self.assertEqual(install.returncode, 0, msg=install.stderr)
            self.assertIn("deps.missing_total=0", install.stdout)

            cfg = target / "orp.erdos-live-compare.yml"
            self.assertTrue(cfg.exists(), msg=f"missing rendered config: {cfg}")

            run = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(target),
                    "--config",
                    str(cfg),
                    "gate",
                    "run",
                    "--profile",
                    "sunflower_live_compare_857",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr + "\n" + run.stdout)
            self.assertIn("overall=PASS", run.stdout)

            m = re.search(r"run_id=([A-Za-z0-9\\-]+)", run.stdout)
            self.assertIsNotNone(m, msg=f"missing run_id in stdout: {run.stdout}")
            run_id = str(m.group(1))
            run_json = target / "orp" / "artifacts" / run_id / "RUN.json"
            self.assertTrue(run_json.exists(), msg=f"missing run json: {run_json}")

    def test_problem857_bootstrap_is_install_and_go_after_public_sync(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            install = _run(
                [
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "problem857",
                ]
            )
            self.assertEqual(install.returncode, 0, msg=install.stderr)
            self.assertIn("deps.missing_total=0", install.stdout)

            cfg = target / "orp.erdos-problem857.yml"
            self.assertTrue(cfg.exists(), msg=f"missing rendered config: {cfg}")
            cfg_text = cfg.read_text(encoding="utf-8")
            self.assertIn("epistemic_status:", cfg_text)
            self.assertIn("overall: starter_public_scaffold", cfg_text)
            self.assertIn("selected_problem_json:", cfg_text)
            self.assertIn("status: evidence", cfg_text)

            _write_selected_problem_payload(target)

            run = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(target),
                    "--config",
                    str(cfg),
                    "gate",
                    "run",
                    "--profile",
                    "sunflower_problem857_discovery",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr + "\n" + run.stdout)
            self.assertIn("overall=PASS", run.stdout)

            m = re.search(r"run_id=([A-Za-z0-9\\-]+)", run.stdout)
            self.assertIsNotNone(m, msg=f"missing run_id in stdout: {run.stdout}")
            run_id = str(m.group(1))
            run_json = target / "orp" / "artifacts" / run_id / "RUN.json"
            self.assertTrue(run_json.exists(), msg=f"missing run json: {run_json}")
            run_payload = json.loads(run_json.read_text(encoding="utf-8"))
            results = {
                str(row["gate_id"]): row
                for row in run_payload.get("results", [])
                if isinstance(row, dict) and "gate_id" in row
            }
            self.assertEqual(results["spec_faithfulness"]["evidence_status"], "evidence")
            self.assertEqual(
                results["spec_faithfulness"]["evidence_paths"],
                ["analysis/erdos_problems/selected/erdos_problem.857.json"],
            )
            self.assertEqual(run_payload["epistemic_status"]["stub_gates"], ["lean_build_balance"])
            self.assertIn("spec_faithfulness", run_payload["epistemic_status"]["evidence_gates"])

            spec_json = target / "orchestrator" / "logs" / run_id / "SPEC_CHECK.json"
            self.assertTrue(spec_json.exists(), msg=f"missing spec check json: {spec_json}")
            spec_payload = json.loads(spec_json.read_text(encoding="utf-8"))
            self.assertEqual(spec_payload["status"], "PASS")
            self.assertEqual(spec_payload["problem_id"], 857)
            self.assertEqual(spec_payload["summary"]["failed"], 0)
            check_ids = {row["id"] for row in spec_payload["checks"] if isinstance(row, dict)}
            self.assertIn("selected_problem_id_matches", check_ids)
            self.assertIn("scope_status_matches_public_status", check_ids)

            report = target / "orp.erdos.pack-install-report.md"
            self.assertTrue(report.exists(), msg=f"missing report: {report}")
            report_text = report.read_text(encoding="utf-8")
            self.assertIn(
                "`orp erdos sync --problem-id 857 --out-problem-dir analysis/erdos_problems/selected`",
                report_text,
            )
            self.assertIn("`orp --config <rendered-config> gate run --profile <profile>`", report_text)
            self.assertIn("`./scripts/orp --config <rendered-config> gate run --profile <profile>`", report_text)

    def test_problem857_spec_check_fails_without_selected_problem(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            install = _run(
                [
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "problem857",
                ]
            )
            self.assertEqual(install.returncode, 0, msg=install.stderr)

            spec = subprocess.run(
                [
                    sys.executable,
                    str(target / "orchestrator" / "problem857_public_spec_check.py"),
                    "--run-id",
                    "run-missing-public-problem",
                ],
                capture_output=True,
                text=True,
                cwd=str(target),
            )
            self.assertEqual(spec.returncode, 1, msg=spec.stderr + "\n" + spec.stdout)
            self.assertIn("spec_check=FAIL", spec.stdout)

            spec_json = target / "orchestrator" / "logs" / "run-missing-public-problem" / "SPEC_CHECK.json"
            self.assertTrue(spec_json.exists(), msg=f"missing spec check json: {spec_json}")
            payload = json.loads(spec_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "FAIL")
            self.assertGreater(payload["summary"]["failed"], 0)

    def test_problem857_public_repo_bootstrap_syncs_public_lean_repo_and_generates_bridge_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "public-problem857"
            target = Path(td) / "target"
            source.mkdir(parents=True, exist_ok=True)
            _make_fake_problem857_public_repo(source)

            install = _run(
                [
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "problem857",
                    "--var",
                    "PROBLEM857_SOURCE_MODE=public_repo",
                    "--var",
                    f"PROBLEM857_PUBLIC_REPO_URL={source}",
                    "--var",
                    "PROBLEM857_PUBLIC_REPO_REF=main",
                    "--var",
                    "PROBLEM857_LEAN_BUILD_COMMAND=python3 -c \"print('lean_build=PASS')\"",
                ]
            )
            self.assertEqual(install.returncode, 0, msg=install.stderr + "\n" + install.stdout)
            self.assertIn("problem857.source_mode=public_repo", install.stdout)
            self.assertIn("deps.missing_total=0", install.stdout)

            cfg = target / "orp.erdos-problem857.yml"
            self.assertTrue(cfg.exists(), msg=f"missing rendered config: {cfg}")
            cfg_text = cfg.read_text(encoding="utf-8")
            self.assertIn("synced public sunflower-lean repo plus ORP-generated bridge files", cfg_text)
            self.assertIn("status: evidence", cfg_text)
            self.assertIn("python3 orchestrator/problem857_public_spec_check.py", cfg_text)

            self.assertTrue((target / "scripts" / "problem857_ops_board.py").exists())
            self.assertTrue((target / "scripts" / "frontier_status.py").exists())
            self.assertTrue((target / "orchestrator" / "reduction_graph.yaml").exists())
            self.assertTrue((target / "orchestrator" / "v2" / "scopes" / "problem_857.yaml").exists())
            self.assertTrue((target / "sunflower_lean" / "lakefile.toml").exists())
            self.assertTrue((target / "sunflower_lean" / "SunflowerLean" / "Balance.lean").exists())
            self.assertTrue((target / "orchestrator" / "problem857_public_spec_check.py").exists())
            self.assertFalse((target / "scripts" / "orp-lean-build-stub.py").exists())

            _write_selected_problem_payload(target)

            run = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(target),
                    "--config",
                    str(cfg),
                    "gate",
                    "run",
                    "--profile",
                    "sunflower_problem857_discovery",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(run.returncode, 0, msg=run.stderr + "\n" + run.stdout)
            self.assertIn("overall=PASS", run.stdout)

            m = re.search(r"run_id=([A-Za-z0-9\\-]+)", run.stdout)
            self.assertIsNotNone(m, msg=f"missing run_id in stdout: {run.stdout}")
            run_id = str(m.group(1))
            run_json = target / "orp" / "artifacts" / run_id / "RUN.json"
            run_payload = json.loads(run_json.read_text(encoding="utf-8"))
            self.assertEqual(run_payload["epistemic_status"]["overall"], "evidence_backed")
            self.assertFalse(run_payload["epistemic_status"]["starter_scaffold"])
            self.assertIn("spec_faithfulness", run_payload["epistemic_status"]["evidence_gates"])
            self.assertIn("lean_build_balance", run_payload["epistemic_status"]["evidence_gates"])
            self.assertEqual(run_payload["epistemic_status"]["stub_gates"], [])
            self.assertEqual(run_payload["epistemic_status"]["starter_scaffold_gates"], [])

            packet = _run_cli(
                target,
                "orp.erdos-problem857.yml",
                ["packet", "emit", "--profile", "sunflower_problem857_discovery", "--run-id", run_id],
            )
            self.assertEqual(packet.returncode, 0, msg=packet.stderr + "\n" + packet.stdout)
            packet_json = target / "orp" / "packets" / f"pkt-problem_scope-{run_id}.json"
            packet_payload = json.loads(packet_json.read_text(encoding="utf-8"))
            self.assertFalse(packet_payload["atomic_context"]["starter_scaffold"])
            self.assertEqual(
                packet_payload["atomic_context"]["route_status"]["balance_core"],
                {
                    "done": 4,
                    "total": 4,
                    "strict_done": 4,
                    "strict_total": 4,
                },
            )
            self.assertEqual(packet_payload["atomic_context"]["atom_id"], "A_public_balance_build")
            self.assertEqual(packet_payload["evidence_status"]["overall"], "evidence_backed")

    def test_external_governance_install_renders_install_and_adapt_configs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            proc = _run(
                [
                    "--pack-id",
                    "external-pr-governance",
                    "--target-repo-root",
                    str(target),
                ]
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            self.assertIn("deps.missing_total=0", proc.stdout)

            governance_cfg = target / "orp.external-pr-governance.yml"
            feedback_cfg = target / "orp.external-pr-feedback-hardening.yml"
            report = target / "orp.external-pr.pack-install-report.md"
            pr_body = target / "analysis" / "PR_DRAFT_BODY.md"

            self.assertTrue(governance_cfg.exists(), msg=f"missing rendered config: {governance_cfg}")
            self.assertTrue(feedback_cfg.exists(), msg=f"missing rendered config: {feedback_cfg}")
            self.assertTrue(report.exists(), msg=f"missing report: {report}")
            self.assertTrue(pr_body.exists(), msg=f"missing starter pr body: {pr_body}")

            governance_text = governance_cfg.read_text(encoding="utf-8")
            self.assertIn("external_watch_select:", governance_text)
            self.assertIn("draft_pr_transition", governance_text)
            self.assertIn("configure WATCH_SELECT_COMMAND", governance_text)

            feedback_text = feedback_cfg.read_text(encoding="utf-8")
            self.assertIn("default_kind: verification", feedback_text)
            self.assertIn("packet_kind: verification", feedback_text)

            report_text = report.read_text(encoding="utf-8")
            self.assertIn("Replace the placeholder commands", report_text)
            self.assertIn("external_watch_select", report_text)
            self.assertIn("external_feedback_hardening", report_text)

    def test_external_governance_full_flow_and_feedback_profiles_run_with_adapter_vars(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            install = _run(
                [
                    "--pack-id",
                    "external-pr-governance",
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "governance",
                    "--include",
                    "feedback_hardening",
                    "--var",
                    "TARGET_GITHUB_REPO=owner/repo",
                    "--var",
                    "TARGET_GITHUB_AUTHOR=tester",
                    "--var",
                    "WATCH_SELECT_COMMAND=printf 'selection=PASS\\n'",
                    "--var",
                    "VIABILITY_COMMAND=printf 'decision=PASS\\n'",
                    "--var",
                    "OVERLAP_COMMAND=printf 'overlap=PASS\\n'",
                    "--var",
                    "LOCAL_GATE_COMMAND=printf 'gate=PASS\\n'",
                    "--var",
                    "READY_TO_DRAFT_COMMAND=printf 'ready_to_draft=PASS\\n'",
                    "--var",
                    "PR_BODY_PREFLIGHT_COMMAND=printf 'gate=PASS\\n'",
                    "--var",
                    "DRAFT_PR_TRANSITION_COMMAND=printf 'draft_pr=PASS\\n'",
                    "--var",
                    "DRAFT_CI_COMMAND=printf 'draft_ci=PASS\\n'",
                    "--var",
                    "READY_FOR_REVIEW_COMMAND=printf 'ready_for_review=PASS\\n'",
                    "--var",
                    "FEEDBACK_RECORD_COMMAND=printf 'feedback_recorded=PASS\\n'",
                    "--var",
                    "GUARD_VALIDATION_COMMAND=printf 'guard_validation=PASS\\n'",
                    "--var",
                    "DOC_SYNC_COMMAND=printf 'docs_sync=PASS\\n'",
                ]
            )
            self.assertEqual(install.returncode, 0, msg=install.stderr + "\n" + install.stdout)

            run_governance = _run_cli(
                target,
                "orp.external-pr-governance.yml",
                ["gate", "run", "--profile", "external_full_flow"],
            )
            self.assertEqual(
                run_governance.returncode,
                0,
                msg=run_governance.stderr + "\n" + run_governance.stdout,
            )
            self.assertIn("overall=PASS", run_governance.stdout)
            m_governance = re.search(r"run_id=([A-Za-z0-9\\-]+)", run_governance.stdout)
            self.assertIsNotNone(m_governance, msg=run_governance.stdout)
            governance_run_id = str(m_governance.group(1))

            state_path = target / "orp" / "state.json"
            state_payload = json.loads(state_path.read_text(encoding="utf-8"))
            state_payload["last_erdos_sync"] = {
                "out_all": str(target / "analysis" / "erdos_problems" / "erdos_problems.all.json"),
                "selected": [
                    {
                        "problem_id": 857,
                        "out": str(
                            target
                            / "analysis"
                            / "erdos_problems"
                            / "selected"
                            / "erdos_problem.857.json"
                        ),
                    }
                ],
            }
            state_path.write_text(json.dumps(state_payload, indent=2) + "\n", encoding="utf-8")

            emit_governance = _run_cli(
                target,
                "orp.external-pr-governance.yml",
                ["packet", "emit", "--profile", "external_full_flow", "--run-id", governance_run_id],
            )
            self.assertEqual(
                emit_governance.returncode,
                0,
                msg=emit_governance.stderr + "\n" + emit_governance.stdout,
            )
            governance_packet = json.loads(
                (target / "orp" / "packets" / f"pkt-pr-{governance_run_id}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(governance_packet["kind"], "pr")
            self.assertEqual(
                governance_packet["claim_context"]["claim_id"],
                "external-pr-governance:external_full_flow",
            )
            self.assertEqual(
                governance_packet["claim_context"]["canonical_artifacts"],
                ["analysis/PR_DRAFT_BODY.md"],
            )

            run_feedback = _run_cli(
                target,
                "orp.external-pr-feedback-hardening.yml",
                ["gate", "run", "--profile", "external_feedback_hardening"],
            )
            self.assertEqual(
                run_feedback.returncode,
                0,
                msg=run_feedback.stderr + "\n" + run_feedback.stdout,
            )
            self.assertIn("overall=PASS", run_feedback.stdout)
            m_feedback = re.search(r"run_id=([A-Za-z0-9\\-]+)", run_feedback.stdout)
            self.assertIsNotNone(m_feedback, msg=run_feedback.stdout)
            feedback_run_id = str(m_feedback.group(1))

            emit_feedback = _run_cli(
                target,
                "orp.external-pr-feedback-hardening.yml",
                ["packet", "emit", "--profile", "external_feedback_hardening", "--run-id", feedback_run_id],
            )
            self.assertEqual(
                emit_feedback.returncode,
                0,
                msg=emit_feedback.stderr + "\n" + emit_feedback.stdout,
            )
            feedback_packet = json.loads(
                (target / "orp" / "packets" / f"pkt-verification-{feedback_run_id}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(feedback_packet["kind"], "verification")
            self.assertEqual(
                feedback_packet["claim_context"]["claim_id"],
                "external-pr-feedback-hardening:external_feedback_hardening",
            )

    def test_issue_smashers_install_renders_workspace_and_feedback_configs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            proc = _run(
                [
                    "--pack-id",
                    "issue-smashers",
                    "--target-repo-root",
                    str(target),
                ]
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            self.assertIn("deps.missing_total=0", proc.stdout)

            workspace_cfg = target / "orp.issue-smashers.yml"
            feedback_cfg = target / "orp.issue-smashers-feedback-hardening.yml"
            report = target / "orp.issue-smashers.pack-install-report.md"
            workspace_root = target / "issue-smashers"
            rules = workspace_root / "WORKSPACE_RULES.md"
            setup = workspace_root / "setup-issue-smashers.sh"
            watchlist = workspace_root / "analysis" / "ISSUE_SMASHERS_WATCHLIST.json"
            status = workspace_root / "analysis" / "ISSUE_SMASHERS_STATUS.md"
            pr_body = workspace_root / "analysis" / "PR_DRAFT_BODY.md"

            self.assertTrue(workspace_cfg.exists(), msg=f"missing rendered config: {workspace_cfg}")
            self.assertTrue(feedback_cfg.exists(), msg=f"missing rendered config: {feedback_cfg}")
            self.assertTrue(report.exists(), msg=f"missing report: {report}")
            self.assertTrue((workspace_root / "README.md").exists(), msg="missing workspace README")
            self.assertTrue(rules.exists(), msg="missing workspace rules")
            self.assertTrue(setup.exists(), msg="missing setup script")
            self.assertTrue(watchlist.exists(), msg="missing watchlist")
            self.assertTrue(status.exists(), msg="missing status board")
            self.assertTrue(pr_body.exists(), msg="missing starter pr body")
            self.assertTrue((workspace_root / "repos" / ".gitkeep").exists(), msg="missing repos placeholder")
            self.assertTrue(
                (workspace_root / "worktrees" / ".gitkeep").exists(),
                msg="missing worktrees placeholder",
            )

            workspace_text = workspace_cfg.read_text(encoding="utf-8")
            self.assertIn("issue_smashers_full_flow:", workspace_text)
            self.assertIn("configure WATCH_SELECT_COMMAND", workspace_text)
            self.assertIn("issue-smashers/analysis/PR_DRAFT_BODY.md", workspace_text)

            feedback_text = feedback_cfg.read_text(encoding="utf-8")
            self.assertIn("default_kind: verification", feedback_text)
            self.assertIn("issue_smashers_feedback_hardening", feedback_text)

            report_text = report.read_text(encoding="utf-8")
            self.assertIn("plain workspace scaffold", report_text)
            self.assertIn("issue_smashers_full_flow", report_text)

    def test_issue_smashers_full_flow_and_feedback_profiles_run_with_adapter_vars(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            install = _run(
                [
                    "--pack-id",
                    "issue-smashers",
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "workspace",
                    "--include",
                    "feedback_hardening",
                    "--var",
                    "TARGET_GITHUB_REPO=owner/repo",
                    "--var",
                    "TARGET_GITHUB_AUTHOR=tester",
                    "--var",
                    "WATCH_SELECT_COMMAND=printf 'selection=PASS\\n'",
                    "--var",
                    "VIABILITY_COMMAND=printf 'decision=PASS\\n'",
                    "--var",
                    "OVERLAP_COMMAND=printf 'overlap=PASS\\n'",
                    "--var",
                    "LOCAL_GATE_COMMAND=printf 'gate=PASS\\n'",
                    "--var",
                    "READY_TO_DRAFT_COMMAND=printf 'ready_to_draft=PASS\\n'",
                    "--var",
                    "PR_BODY_PREFLIGHT_COMMAND=printf 'gate=PASS\\n'",
                    "--var",
                    "DRAFT_PR_TRANSITION_COMMAND=printf 'draft_pr=PASS\\n'",
                    "--var",
                    "DRAFT_CI_COMMAND=printf 'draft_ci=PASS\\n'",
                    "--var",
                    "READY_FOR_REVIEW_COMMAND=printf 'ready_for_review=PASS\\n'",
                    "--var",
                    "FEEDBACK_RECORD_COMMAND=printf 'feedback_recorded=PASS\\n'",
                    "--var",
                    "GUARD_VALIDATION_COMMAND=printf 'guard_validation=PASS\\n'",
                    "--var",
                    "DOC_SYNC_COMMAND=printf 'docs_sync=PASS\\n'",
                ]
            )
            self.assertEqual(install.returncode, 0, msg=install.stderr + "\n" + install.stdout)

            run_workspace = _run_cli(
                target,
                "orp.issue-smashers.yml",
                ["gate", "run", "--profile", "issue_smashers_full_flow"],
            )
            self.assertEqual(run_workspace.returncode, 0, msg=run_workspace.stderr + "\n" + run_workspace.stdout)
            self.assertIn("overall=PASS", run_workspace.stdout)
            m_workspace = re.search(r"run_id=([A-Za-z0-9\\-]+)", run_workspace.stdout)
            self.assertIsNotNone(m_workspace, msg=run_workspace.stdout)
            workspace_run_id = str(m_workspace.group(1))

            emit_workspace = _run_cli(
                target,
                "orp.issue-smashers.yml",
                ["packet", "emit", "--profile", "issue_smashers_full_flow", "--run-id", workspace_run_id],
            )
            self.assertEqual(
                emit_workspace.returncode,
                0,
                msg=emit_workspace.stderr + "\n" + emit_workspace.stdout,
            )
            workspace_packet = json.loads(
                (target / "orp" / "packets" / f"pkt-pr-{workspace_run_id}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(workspace_packet["kind"], "pr")
            self.assertEqual(
                workspace_packet["claim_context"]["claim_id"],
                "issue-smashers:issue_smashers_full_flow",
            )
            workspace_artifacts = set(workspace_packet["claim_context"]["canonical_artifacts"])
            self.assertIn("issue-smashers/analysis/PR_DRAFT_BODY.md", workspace_artifacts)
            self.assertIn("issue-smashers/analysis/ISSUE_SMASHERS_STATUS.md", workspace_artifacts)
            self.assertIn("issue-smashers/analysis/ISSUE_SMASHERS_WATCHLIST.json", workspace_artifacts)

            run_feedback = _run_cli(
                target,
                "orp.issue-smashers-feedback-hardening.yml",
                ["gate", "run", "--profile", "issue_smashers_feedback_hardening"],
            )
            self.assertEqual(run_feedback.returncode, 0, msg=run_feedback.stderr + "\n" + run_feedback.stdout)
            self.assertIn("overall=PASS", run_feedback.stdout)
            m_feedback = re.search(r"run_id=([A-Za-z0-9\\-]+)", run_feedback.stdout)
            self.assertIsNotNone(m_feedback, msg=run_feedback.stdout)
            feedback_run_id = str(m_feedback.group(1))

            emit_feedback = _run_cli(
                target,
                "orp.issue-smashers-feedback-hardening.yml",
                ["packet", "emit", "--profile", "issue_smashers_feedback_hardening", "--run-id", feedback_run_id],
            )
            self.assertEqual(
                emit_feedback.returncode,
                0,
                msg=emit_feedback.stderr + "\n" + emit_feedback.stdout,
            )
            feedback_packet = json.loads(
                (target / "orp" / "packets" / f"pkt-verification-{feedback_run_id}.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(feedback_packet["kind"], "verification")
            self.assertEqual(
                feedback_packet["claim_context"]["claim_id"],
                "issue-smashers-feedback-hardening:issue_smashers_feedback_hardening",
            )
            feedback_artifacts = set(feedback_packet["claim_context"]["canonical_artifacts"])
            self.assertIn("issue-smashers/WORKSPACE_RULES.md", feedback_artifacts)
            self.assertIn("issue-smashers/analysis/ISSUE_SMASHERS_STATUS.md", feedback_artifacts)

    def test_cli_pack_install_json_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--repo-root",
                    str(REPO_ROOT),
                    "pack",
                    "install",
                    "--target-repo-root",
                    str(target),
                    "--include",
                    "catalog",
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)

            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["returncode"], 0)
            self.assertEqual(payload["pack_id"], "erdos-open-problems")
            self.assertEqual(payload["included_components"], ["catalog"])
            self.assertEqual(payload["deps"]["missing_total"], 0)
            self.assertIn("catalog", payload["rendered"])


if __name__ == "__main__":
    unittest.main()
