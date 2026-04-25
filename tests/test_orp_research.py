from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def load_cli_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("orp_cli_research_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), "--repo-root", str(root), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


class OrpResearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_xdg = os.environ.get("XDG_CONFIG_HOME")
        self._xdg_config_home = tempfile.TemporaryDirectory()
        os.environ["XDG_CONFIG_HOME"] = self._xdg_config_home.name
        self.addCleanup(self._restore_xdg_config_home)

    def _restore_xdg_config_home(self) -> None:
        self._xdg_config_home.cleanup()
        if self._old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self._old_xdg

    def test_research_profile_show_exposes_staged_template(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = run_cli(
                root,
                "research",
                "profile",
                "show",
                "deep-think-web-think-deep",
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            profile = payload["profile"]
            self.assertEqual(profile["profile_id"], "deep-think-web-think-deep")
            self.assertTrue(profile["execution_policy"]["sequential"])
            self.assertEqual(
                [row["lane_id"] for row in profile["lanes"]],
                [
                    "deep_research_opening",
                    "think_after_deep",
                    "think_web_crosscheck",
                    "think_synthesis",
                    "deep_research_final",
                ],
            )
            fields = {row["key"]: row for row in profile["prompt_form"]["fields"]}
            self.assertTrue(fields["goal"]["required"])
            self.assertIn("deliverable_format", fields)

    def test_research_ask_dry_run_persists_plan_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = run_cli(
                root,
                "research",
                "ask",
                "Where should the OpenAI research loop live?",
                "--run-id",
                "research-dry",
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["run_id"], "research-dry")
            self.assertEqual(payload["status"], "planned")
            self.assertFalse(payload["execute"])
            self.assertEqual(payload["profile_id"], "openai-council")
            self.assertEqual({row["status"] for row in payload["lane_statuses"]}, {"planned"})
            self.assertIn("planning_only", payload["synthesis"]["confidence"])

            answer_path = root / payload["artifacts"]["answer_json"]
            summary_path = root / payload["artifacts"]["summary_md"]
            lanes_root = root / payload["artifacts"]["lanes_root"]
            self.assertTrue(answer_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue((lanes_root / "openai_reasoning_high.json").exists())
            self.assertEqual(
                [row["call_moment"] for row in payload["lane_statuses"]],
                ["thinking_reasoning_high", "web_synthesis", "pro_deep_research"],
            )
            self.assertEqual({row["api_called"] for row in payload["lane_statuses"]}, {False})

            answer = json.loads(answer_path.read_text(encoding="utf-8"))
            self.assertEqual(answer["kind"], "research_run")
            self.assertEqual(answer["breakdown"]["question"], "Where should the OpenAI research loop live?")
            self.assertEqual(
                [row["moment_id"] for row in answer["call_moments"]],
                ["plan", "thinking_reasoning_high", "web_synthesis", "pro_deep_research"],
            )
            reasoning_lane = json.loads((lanes_root / "openai_reasoning_high.json").read_text(encoding="utf-8"))
            self.assertEqual(reasoning_lane["call_moment"], "thinking_reasoning_high")
            self.assertFalse(reasoning_lane["api_call"]["called"])
            self.assertEqual(reasoning_lane["api_call"]["secret_alias"], "openai-primary")
            self.assertFalse(reasoning_lane["api_call"]["secret_value_persisted"])
            self.assertEqual(answer["synthesis"]["completed_lane_count"], 0)
            self.assertIn("No live research lane has completed", answer["synthesis"]["answer"])

            state = json.loads((root / "orp" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["last_research_run_id"], "research-dry")
            self.assertIn("research-dry", state["research_runs"])

            status_proc = run_cli(root, "research", "status", "latest", "--json")
            self.assertEqual(status_proc.returncode, 0, msg=status_proc.stderr + "\n" + status_proc.stdout)
            status_payload = json.loads(status_proc.stdout)
            self.assertEqual(status_payload["run_id"], "research-dry")
            self.assertEqual(status_payload["status"], "planned")

    def test_staged_profile_dry_run_persists_sequence_fields_and_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proc = run_cli(
                root,
                "research",
                "ask",
                "How should Acme use ORP research for product strategy?",
                "--profile",
                "deep-think-web-think-deep",
                "--field",
                "goal=Choose whether to make the staged loop the default research template.",
                "--field",
                "audience=Platform team",
                "--field",
                "deliverable_format=Decision memo",
                "--run-id",
                "staged-dry",
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "planned")
            self.assertEqual(payload["profile_id"], "deep-think-web-think-deep")
            self.assertEqual(
                [row["lane_id"] for row in payload["lane_statuses"]],
                [
                    "deep_research_opening",
                    "think_after_deep",
                    "think_web_crosscheck",
                    "think_synthesis",
                    "deep_research_final",
                ],
            )
            self.assertEqual(
                [row["call_moment"] for row in payload["lane_statuses"]],
                [
                    "opening_deep_research",
                    "think_after_deep",
                    "think_web_crosscheck",
                    "think_synthesis",
                    "final_deep_research",
                ],
            )

            answer_path = root / payload["artifacts"]["answer_json"]
            lanes_root = root / payload["artifacts"]["lanes_root"]
            answer = json.loads(answer_path.read_text(encoding="utf-8"))
            self.assertEqual(answer["profile"]["lane_count"], 5)
            self.assertEqual(answer["breakdown"]["template_fields"]["goal"], "Choose whether to make the staged loop the default research template.")
            self.assertEqual(answer["breakdown"]["template_fields"]["audience"], "Platform team")
            self.assertEqual(answer["breakdown"]["lanes"][2]["lane"], "think_web_crosscheck")

            request = json.loads((root / payload["artifacts"]["request_json"]).read_text(encoding="utf-8"))
            self.assertEqual(request["timeout_sec"], 900)
            self.assertEqual(request["template_fields"]["deliverable_format"], "Decision memo")

            opening = json.loads((lanes_root / "deep_research_opening.json").read_text(encoding="utf-8"))
            self.assertIn("Choose whether to make the staged loop", opening["prompt"])
            self.assertEqual(opening["api_call"]["secret_alias"], "openai-primary")
            self.assertFalse(opening["api_call"]["called"])

            think = json.loads((lanes_root / "think_after_deep.json").read_text(encoding="utf-8"))
            self.assertIn("Previous Lane Outputs:", think["prompt"])
            self.assertIn("No completed text captured", think["prompt"])
            self.assertEqual(think["api_call"]["call_moment"], "think_after_deep")

            final = json.loads((lanes_root / "deep_research_final.json").read_text(encoding="utf-8"))
            self.assertIn("Previous Lane Outputs:", final["prompt"])
            self.assertEqual(final["api_call"]["call_moment"], "final_deep_research")
            self.assertEqual(final["api_call"]["secret_alias"], "openai-primary")

    def test_staged_profile_later_prompt_includes_previous_fixture_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture_dir = root / "fixtures"
            fixture_dir.mkdir()
            opening_fixture = fixture_dir / "opening.txt"
            opening_fixture.write_text(
                "Opening research says the target market is regulated and source quality is uneven.",
                encoding="utf-8",
            )
            proc = run_cli(
                root,
                "research",
                "ask",
                "Should this company use the staged research pattern?",
                "--profile",
                "deep-think-web-think-deep",
                "--field",
                "goal=Decide whether staged research is worth adopting.",
                "--lane-fixture",
                f"deep_research_opening={opening_fixture}",
                "--run-id",
                "staged-fixture",
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "partial")
            lanes_root = root / payload["artifacts"]["lanes_root"]
            think = json.loads((lanes_root / "think_after_deep.json").read_text(encoding="utf-8"))
            self.assertIn("Opening research says the target market is regulated", think["prompt"])
            self.assertEqual(think["status"], "planned")

    def test_staged_live_lane_skips_when_previous_output_is_incomplete(self) -> None:
        module = load_cli_module()
        profile = module._research_profile_for_id("deep-think-web-think-deep")
        lane = profile["lanes"][1]
        breakdown = module._research_breakdown(
            "Should the staged research pattern run?",
            profile,
            {"goal": "Avoid wasting provider calls after an incomplete prerequisite."},
        )
        with tempfile.TemporaryDirectory() as td:
            result = module._research_run_lane(
                lane,
                question="Should the staged research pattern run?",
                breakdown=breakdown,
                repo_root=Path(td),
                execute=True,
                fixtures={},
                chimera_bin="chimera",
                timeout_sec=1,
                previous_lanes=[
                    {
                        "lane_id": "deep_research_opening",
                        "label": "Opening Deep Research",
                        "status": "failed",
                        "text": "",
                    }
                ],
            )
        self.assertEqual(result["status"], "skipped")
        self.assertFalse(result["api_call"]["called"])
        self.assertIn("previous lane output was not complete", result["notes"][0])
        self.assertIn("Previous Lane Outputs:", result["prompt"])

    def test_research_ask_with_lane_fixtures_synthesizes_completed_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture_dir = root / "fixtures"
            fixture_dir.mkdir()
            reasoning_fixture = fixture_dir / "reasoning.json"
            reasoning_fixture.write_text(
                json.dumps(
                    {
                        "text": "OpenAI frontier lane says ORP should own durability and tool-call surfaces.",
                        "citations": [
                            {
                                "type": "url_citation",
                                "title": "ORP docs",
                                "url": "https://example.com/orp",
                            }
                        ],
                        "confidence": "high",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            web_fixture = fixture_dir / "web.txt"
            web_fixture.write_text(
                "OpenAI web lane says ORP should call OpenAI provider APIs directly.",
                encoding="utf-8",
            )

            proc = run_cli(
                root,
                "research",
                "ask",
                "Where should this system live?",
                "--run-id",
                "research-fixture",
                "--lane-fixture",
                f"openai_reasoning_high={reasoning_fixture}",
                "--lane-fixture",
                f"openai_web_synthesis={web_fixture}",
                "--json",
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr + "\n" + proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "partial")
            self.assertEqual(payload["synthesis"]["completed_lane_count"], 2)
            self.assertEqual(payload["synthesis"]["confidence"], "multi_lane")
            self.assertIn("ORP should own durability", payload["synthesis"]["answer"])
            self.assertIn("ORP should call OpenAI provider APIs directly", payload["synthesis"]["answer"])
            self.assertEqual(payload["synthesis"]["citations"][0]["url"], "https://example.com/orp")

            show_proc = run_cli(root, "research", "show", "research-fixture", "--json")
            self.assertEqual(show_proc.returncode, 0, msg=show_proc.stderr + "\n" + show_proc.stdout)
            show_payload = json.loads(show_proc.stdout)
            self.assertEqual(show_payload["run_id"], "research-fixture")
            lane_statuses = {row["lane_id"]: row["status"] for row in show_payload["lanes"]}
            self.assertEqual(lane_statuses["openai_reasoning_high"], "complete")
            self.assertEqual(lane_statuses["openai_web_synthesis"], "complete")
            self.assertEqual(lane_statuses["openai_deep_research"], "planned")

    def test_openai_adapter_uses_responses_model_reasoning_and_web_search(self) -> None:
        module = load_cli_module()
        captured: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "id": "resp_test",
                        "status": "completed",
                        "model": "gpt-5.5",
                        "output": [
                            {"type": "web_search_call", "status": "completed"},
                            {
                                "type": "message",
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": "OpenAI Responses answer.",
                                        "annotations": [
                                            {
                                                "type": "url_citation",
                                                "title": "Source",
                                                "url": "https://example.com",
                                                "start_index": 0,
                                                "end_index": 6,
                                            }
                                        ],
                                    }
                                ],
                            },
                        ],
                        "usage": {"input_tokens": 11, "output_tokens": 7},
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        lane = {
            "lane_id": "openai_web_synthesis",
            "call_moment": "web_synthesis",
            "label": "OpenAI web synthesis",
            "provider": "openai",
            "model": "gpt-5.5",
            "adapter": "openai_responses",
            "env_var": "OPENAI_API_KEY",
            "reasoning_effort": "medium",
            "text_verbosity": "high",
            "web_search": True,
            "web_search_tool": "web_search",
            "search_context_size": "high",
            "external_web_access": False,
            "max_tool_calls": 3,
            "max_output_tokens": 777,
        }
        with mock.patch.dict(module.os.environ, {"OPENAI_API_KEY": "sk-openai-test"}):
            with mock.patch.object(module.urlrequest, "urlopen", side_effect=fake_urlopen):
                result = module._research_run_openai_lane(
                    lane,
                    "Prompt body",
                    timeout_sec=13,
                    started_at_utc="2026-04-17T00:00:00Z",
                )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["adapter"], "openai_responses")
        self.assertEqual(result["call_moment"], "web_synthesis")
        self.assertTrue(result["api_call"]["called"])
        self.assertEqual(result["api_call"]["call_moment"], "web_synthesis")
        self.assertEqual(result["api_call"]["secret_source"], "env:OPENAI_API_KEY")
        self.assertIn("tools", result["api_call"]["request_body_keys"])
        self.assertEqual(result["api_call"]["tools"], ["web_search"])
        self.assertFalse(result["api_call"]["secret_value_persisted"])
        self.assertEqual(result["text"], "OpenAI Responses answer.")
        self.assertEqual(result["tool_call_count"], 1)
        self.assertEqual(result["citations"][0]["url"], "https://example.com")
        self.assertEqual(captured["url"], "https://api.openai.com/v1/responses")
        body = captured["body"]
        self.assertEqual(body["model"], "gpt-5.5")
        self.assertEqual(body["input"], "Prompt body")
        self.assertEqual(body["reasoning"], {"effort": "medium"})
        self.assertEqual(body["text"], {"verbosity": "high"})
        self.assertEqual(body["max_tool_calls"], 3)
        self.assertEqual(body["max_output_tokens"], 777)
        self.assertEqual(
            body["tools"],
            [
                {
                    "type": "web_search",
                    "search_context_size": "high",
                    "external_web_access": False,
                }
            ],
        )
        headers = {str(k).lower(): v for k, v in captured["headers"].items()}
        self.assertEqual(headers["authorization"], "Bearer sk-openai-test")

    def test_research_secret_value_resolves_keychain_alias(self) -> None:
        module = load_cli_module()
        entry = {
            "keychain_service": "orp.secret.openai",
            "keychain_account": "openai-primary",
        }
        lane = {
            "provider": "openai",
            "env_var": "OPENAI_API_KEY",
            "secret_alias": "openai-primary",
        }

        with mock.patch.dict(module.os.environ, {"OPENAI_API_KEY": ""}):
            with mock.patch.object(module, "_select_keychain_entry", return_value=entry) as select_entry:
                with mock.patch.object(module, "_read_keychain_secret_value", return_value="sk-local-test"):
                    value, source, issue = module._research_secret_value_for_lane(lane)

        self.assertEqual(value, "sk-local-test")
        self.assertEqual(source, "keychain")
        self.assertEqual(issue, "")
        select_entry.assert_called_once_with(
            secret_ref="openai-primary",
            provider="openai",
            world_id="",
            idea_id="",
        )

    def test_openai_adapter_reserves_keychain_daily_spend_before_call(self) -> None:
        module = load_cli_module()

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "id": "resp_spend_test",
                        "status": "completed",
                        "model": "gpt-5.5",
                        "output": [
                            {
                                "type": "message",
                                "content": [{"type": "output_text", "text": "Spend-governed answer."}],
                            }
                        ],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    }
                ).encode("utf-8")

        lane = {
            "lane_id": "openai_reasoning_high",
            "call_moment": "thinking_reasoning_high",
            "label": "OpenAI reasoning high",
            "provider": "openai",
            "model": "gpt-5.5",
            "adapter": "openai_responses",
            "env_var": "OPENAI_API_KEY",
            "secret_alias": "openai-primary",
            "spend_reserve_usd": 1.25,
        }
        entry = {
            "alias": "openai-primary",
            "provider": "openai",
            "spend_policy": {
                "daily_cap_usd": 5.0,
                "dashboard_limit": {"status": "confirmed", "provider": "openai"},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            ledger_path = Path(td) / "spend-ledger.json"
            with mock.patch.object(module, "_research_spend_ledger_path", return_value=ledger_path):
                with mock.patch.object(module, "_research_secret_value_for_lane", return_value=("sk-openai-test", "keychain", "")):
                    with mock.patch.object(module, "_select_keychain_entry", return_value=entry):
                        with mock.patch.object(module.urlrequest, "urlopen", return_value=FakeResponse()):
                            result = module._research_run_openai_lane(
                                lane,
                                "Prompt body",
                                timeout_sec=13,
                                started_at_utc="2026-04-17T00:00:00Z",
                            )

            self.assertEqual(result["status"], "complete")
            self.assertTrue(result["api_call"]["called"])
            spend = result["api_call"]["spend_preflight"]
            self.assertTrue(spend["allowed"])
            self.assertEqual(spend["daily_cap_usd"], 5.0)
            self.assertEqual(spend["reserve_usd"], 1.25)
            self.assertEqual(spend["dashboard_limit"]["status"], "confirmed")
            self.assertTrue(spend["reservation_id"].startswith("spend-"))
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual([row["event"] for row in ledger["records"]], ["reserved", "usage"])
            self.assertEqual(ledger["records"][0]["amount_usd"], 1.25)
            self.assertEqual(ledger["records"][1]["amount_usd"], 0.0)
            self.assertEqual(ledger["records"][1]["usage"]["output_tokens"], 5)

    def test_openai_adapter_skips_when_daily_spend_cap_would_be_exceeded(self) -> None:
        module = load_cli_module()
        lane = {
            "lane_id": "openai_deep_research",
            "call_moment": "pro_deep_research",
            "label": "OpenAI deep research",
            "provider": "openai",
            "model": "gpt-5.5",
            "adapter": "openai_responses",
            "env_var": "OPENAI_API_KEY",
            "secret_alias": "openai-primary",
            "spend_reserve_usd": 1.25,
        }
        entry = {
            "alias": "openai-primary",
            "provider": "openai",
            "spend_policy": {
                "daily_cap_usd": 1.0,
                "dashboard_limit": {"status": "confirmed", "provider": "openai"},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            ledger_path = Path(td) / "spend-ledger.json"
            with mock.patch.object(module, "_research_spend_ledger_path", return_value=ledger_path):
                with mock.patch.object(module, "_research_secret_value_for_lane", return_value=("sk-openai-test", "keychain", "")):
                    with mock.patch.object(module, "_select_keychain_entry", return_value=entry):
                        with mock.patch.object(module.urlrequest, "urlopen") as urlopen:
                            result = module._research_run_openai_lane(
                                lane,
                                "Prompt body",
                                timeout_sec=13,
                                started_at_utc="2026-04-17T00:00:00Z",
                            )

            self.assertEqual(result["status"], "skipped")
            self.assertFalse(result["api_call"]["called"])
            self.assertFalse(result["api_call"]["spend_preflight"]["allowed"])
            self.assertEqual(result["api_call"]["spend_preflight"]["reason"], "daily spend cap would be exceeded")
            self.assertFalse(ledger_path.exists())
            urlopen.assert_not_called()

    def test_openai_adapter_records_incomplete_details(self) -> None:
        module = load_cli_module()

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "id": "resp_incomplete_test",
                        "status": "incomplete",
                        "model": "gpt-5.5",
                        "incomplete_details": {"reason": "max_output_tokens"},
                        "output": [{"type": "reasoning", "summary": []}],
                        "usage": {
                            "input_tokens": 10,
                            "output_tokens": 20,
                            "output_tokens_details": {"reasoning_tokens": 20},
                        },
                    }
                ).encode("utf-8")

        def fake_urlopen(_request, timeout=0):
            return FakeResponse()

        lane = {
            "lane_id": "openai_reasoning_high",
            "call_moment": "thinking_reasoning_high",
            "label": "OpenAI reasoning high",
            "provider": "openai",
            "model": "gpt-5.5",
            "adapter": "openai_responses",
            "env_var": "OPENAI_API_KEY",
            "reasoning_effort": "high",
            "max_output_tokens": 20,
        }
        with mock.patch.dict(module.os.environ, {"OPENAI_API_KEY": "sk-openai-test"}):
            with mock.patch.object(module.urlrequest, "urlopen", side_effect=fake_urlopen):
                result = module._research_run_openai_lane(
                    lane,
                    "Prompt body",
                    timeout_sec=13,
                    started_at_utc="2026-04-17T00:00:00Z",
                )

        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["provider_status"], "incomplete")
        self.assertEqual(result["incomplete_details"], {"reason": "max_output_tokens"})
        self.assertEqual(result["provider_error"], None)
        self.assertEqual(result["output_types"], ["reasoning"])
        self.assertEqual(result["usage"]["output_tokens_details"]["reasoning_tokens"], 20)

    def test_openai_deep_research_lane_uses_background_and_reasoning_summary(self) -> None:
        module = load_cli_module()
        captured: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "id": "resp_deep_test",
                        "status": "in_progress",
                        "model": "gpt-5.5",
                        "output": [],
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        lane = {
            "lane_id": "openai_deep_research",
            "call_moment": "pro_deep_research",
            "label": "OpenAI Pro / Deep Research",
            "provider": "openai",
            "model": "gpt-5.5",
            "adapter": "openai_responses",
            "env_var": "OPENAI_API_KEY",
            "reasoning_effort": "xhigh",
            "reasoning_summary": "auto",
            "web_search": True,
            "web_search_tool": "web_search",
            "background": True,
            "max_tool_calls": 40,
        }
        with mock.patch.dict(module.os.environ, {"OPENAI_API_KEY": "sk-openai-test"}):
            with mock.patch.object(module.urlrequest, "urlopen", side_effect=fake_urlopen):
                result = module._research_run_openai_lane(
                    lane,
                    "Prompt body",
                    timeout_sec=13,
                    started_at_utc="2026-04-17T00:00:00Z",
                )

        body = captured["body"]
        self.assertEqual(body["model"], "gpt-5.5")
        self.assertTrue(body["background"])
        self.assertEqual(body["reasoning"], {"effort": "xhigh", "summary": "auto"})
        self.assertEqual(body["tools"], [{"type": "web_search", "search_context_size": "medium"}])
        self.assertEqual(body["max_tool_calls"], 40)
        self.assertEqual(result["status"], "in_progress")
        self.assertEqual(result["provider_response_id"], "resp_deep_test")
        self.assertEqual(result["call_moment"], "pro_deep_research")
        self.assertTrue(result["api_call"]["called"])
        self.assertEqual(result["api_call"]["tools"], ["web_search"])
        self.assertEqual(result["output_types"], [])

    def test_direct_anthropic_adapter_uses_messages_api(self) -> None:
        module = load_cli_module()
        captured: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "id": "msg_test",
                        "model": "claude-opus-4-7",
                        "content": [{"type": "text", "text": "Anthropic direct answer."}],
                        "stop_reason": "end_turn",
                        "usage": {"input_tokens": 11, "output_tokens": 7},
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        lane = {
            "lane_id": "anthropic_opus",
            "label": "Anthropic Opus critique",
            "provider": "anthropic",
            "model": "claude-opus-4-7",
            "adapter": "anthropic_messages",
            "env_var": "ANTHROPIC_API_KEY",
            "max_tokens": 1234,
        }
        with mock.patch.dict(module.os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            with mock.patch.object(module.urlrequest, "urlopen", side_effect=fake_urlopen):
                result = module._research_run_anthropic_lane(
                    lane,
                    "Prompt body",
                    timeout_sec=9,
                    started_at_utc="2026-04-17T00:00:00Z",
                )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["adapter"], "anthropic_messages")
        self.assertEqual(result["text"], "Anthropic direct answer.")
        self.assertEqual(captured["url"], "https://api.anthropic.com/v1/messages")
        self.assertEqual(captured["body"]["model"], "claude-opus-4-7")
        self.assertEqual(captured["body"]["max_tokens"], 1234)
        self.assertEqual(captured["body"]["messages"][0]["content"], "Prompt body")
        headers = {str(k).lower(): v for k, v in captured["headers"].items()}
        self.assertEqual(headers["x-api-key"], "sk-ant-test")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")

    def test_direct_xai_adapter_uses_chat_completions_api(self) -> None:
        module = load_cli_module()
        captured: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "id": "xai_test",
                        "model": "grok-4.20-reasoning",
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "xAI direct answer.",
                                }
                            }
                        ],
                        "usage": {"prompt_tokens": 11, "completion_tokens": 7},
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        lane = {
            "lane_id": "xai_grok",
            "label": "xAI Grok 4.20 pass",
            "provider": "xai",
            "model": "grok-4.20-reasoning",
            "adapter": "xai_chat_completions",
            "env_var": "XAI_API_KEY",
            "max_tokens": 2345,
        }
        with mock.patch.dict(module.os.environ, {"XAI_API_KEY": "xai-test"}):
            with mock.patch.object(module.urlrequest, "urlopen", side_effect=fake_urlopen):
                result = module._research_run_xai_lane(
                    lane,
                    "Prompt body",
                    timeout_sec=11,
                    started_at_utc="2026-04-17T00:00:00Z",
                )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["adapter"], "xai_chat_completions")
        self.assertEqual(result["text"], "xAI direct answer.")
        self.assertEqual(captured["url"], "https://api.x.ai/v1/chat/completions")
        self.assertEqual(captured["body"]["model"], "grok-4.20-reasoning")
        self.assertEqual(captured["body"]["max_tokens"], 2345)
        self.assertEqual(captured["body"]["messages"][-1]["content"], "Prompt body")
        headers = {str(k).lower(): v for k, v in captured["headers"].items()}
        self.assertEqual(headers["authorization"], "Bearer xai-test")


if __name__ == "__main__":
    unittest.main()
