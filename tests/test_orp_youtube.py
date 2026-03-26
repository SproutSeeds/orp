from __future__ import annotations

import argparse
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI = REPO_ROOT / "cli" / "orp.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("orp_cli_youtube_test", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OrpYoutubeTests(unittest.TestCase):
    def test_video_id_from_supported_inputs(self) -> None:
        module = load_cli_module()
        expected = "dQw4w9WgXcQ"
        inputs = [
            expected,
            f"https://youtu.be/{expected}",
            f"https://www.youtube.com/watch?v={expected}&t=43s",
            f"https://www.youtube.com/shorts/{expected}",
            f"https://www.youtube.com/embed/{expected}",
            f"https://music.youtube.com/watch?v={expected}",
        ]
        for raw in inputs:
            with self.subTest(raw=raw):
                self.assertEqual(module._youtube_video_id_from_url(raw), expected)

    def test_pick_caption_track_prefers_requested_language_and_manual_track(self) -> None:
        module = load_cli_module()
        tracks = [
            {"languageCode": "en", "kind": "asr", "baseUrl": "https://example.invalid/asr"},
            {"languageCode": "es", "baseUrl": "https://example.invalid/es"},
            {"languageCode": "en", "baseUrl": "https://example.invalid/manual"},
        ]
        chosen = module._pick_youtube_caption_track(tracks, preferred_lang="en")
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["baseUrl"], "https://example.invalid/manual")

    def test_parse_json3_transcript_merges_segments(self) -> None:
        module = load_cli_module()
        transcript_text, segments = module._parse_youtube_transcript_json3(
            {
                "events": [
                    {
                        "tStartMs": "0",
                        "dDurationMs": "1000",
                        "segs": [{"utf8": "Hello "}, {"utf8": "world"}],
                    },
                    {
                        "tStartMs": "1000",
                        "dDurationMs": "2000",
                        "segs": [{"utf8": "Second line"}],
                    },
                ]
            }
        )
        self.assertEqual(transcript_text, "Hello world\nSecond line")
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["start_ms"], 0)
        self.assertEqual(segments[1]["duration_ms"], 2000)

    def test_parse_xml_transcript_supports_srv3_paragraphs(self) -> None:
        module = load_cli_module()
        transcript_text, segments = module._parse_youtube_transcript_xml(
            """<?xml version="1.0" encoding="utf-8" ?>
            <timedtext format="3">
              <body>
                <p t="1200" d="2160">All right</p>
                <p t="5318" d="2656"><s>the cool thing</s><s> about these guys</s></p>
              </body>
            </timedtext>"""
        )
        self.assertEqual(transcript_text, "All right\nthe cool thing about these guys")
        self.assertEqual(
            segments,
            [
                {"start_ms": 1200, "duration_ms": 2160, "text": "All right"},
                {"start_ms": 5318, "duration_ms": 2656, "text": "the cool thing about these guys"},
            ],
        )

    def test_youtube_inspect_payload_assembles_metadata_and_transcript(self) -> None:
        module = load_cli_module()

        module._youtube_fetch_oembed = lambda canonical_url: {
            "title": "Fallback title",
            "author_name": "Fallback author",
            "author_url": "https://youtube.com/@fallback",
            "thumbnail_url": "https://img.youtube.com/example.jpg",
        }
        module._youtube_fetch_watch_state = lambda video_id: {
            "video_details": {
                "title": "Primary title",
                "author": "Primary author",
                "lengthSeconds": "42",
                "shortDescription": "A compact description.",
                "channelId": "channel_123",
            },
            "microformat": {"publishDate": "2026-03-25"},
            "playability_status": {"status": "OK"},
            "caption_tracks": [
                {
                    "languageCode": "en",
                    "name": {"simpleText": "English"},
                    "baseUrl": "https://example.invalid/en",
                    "_orp_source": "watch_page",
                }
            ],
        }
        module._youtube_fetch_android_player_state = lambda video_id: {
            "video_details": {},
            "microformat": {},
            "playability_status": {},
            "caption_tracks": [],
        }
        module._youtube_fetch_transcript_from_track = lambda track: (
            "Hello world",
            [{"start_ms": 0, "duration_ms": 1000, "text": "Hello world"}],
            "watch_page_json3",
        )

        payload = module._youtube_inspect_payload("https://youtu.be/dQw4w9WgXcQ", preferred_lang="en")
        self.assertEqual(payload["schema_version"], "1.0.0")
        self.assertEqual(payload["kind"], "youtube_source")
        self.assertEqual(payload["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(payload["title"], "Primary title")
        self.assertEqual(payload["author_name"], "Primary author")
        self.assertEqual(payload["duration_seconds"], 42)
        self.assertEqual(payload["transcript_track_count"], 1)
        self.assertEqual(
            payload["available_transcript_tracks"],
            [{"language_code": "en", "name": "English", "kind": "manual", "source": "watch_page"}],
        )
        self.assertTrue(payload["transcript_available"])
        self.assertEqual(payload["transcript_language"], "en")
        self.assertEqual(payload["transcript_track_source"], "watch_page")
        self.assertEqual(payload["transcript_fetch_mode"], "watch_page_json3")
        self.assertEqual(payload["transcript_text"], "Hello world")
        self.assertEqual(payload["transcript_sources_tried"], ["watch_page:en:English"])
        self.assertIn("Transcript:\nHello world", payload["text_bundle"])

    def test_youtube_inspect_payload_falls_back_to_android_player_tracks(self) -> None:
        module = load_cli_module()

        module._youtube_fetch_oembed = lambda canonical_url: {}
        module._youtube_fetch_watch_state = lambda video_id: {
            "video_details": {
                "title": "Watch title",
                "author": "Watch author",
                "lengthSeconds": "42",
                "shortDescription": "Watch description.",
                "channelId": "channel_watch",
            },
            "microformat": {"publishDate": "2026-03-25"},
            "playability_status": {"status": "OK"},
            "caption_tracks": [
                {
                    "languageCode": "en",
                    "name": {"simpleText": "English"},
                    "baseUrl": "https://example.invalid/watch-en",
                    "_orp_source": "watch_page",
                }
            ],
        }
        module._youtube_fetch_android_player_state = lambda video_id: {
            "video_details": {},
            "microformat": {},
            "playability_status": {},
            "caption_tracks": [
                {
                    "languageCode": "en",
                    "name": {"simpleText": "English"},
                    "baseUrl": "https://example.invalid/android-en",
                    "_orp_source": "android_player",
                }
            ],
        }

        def fake_fetch(track):
            if track.get("_orp_source") == "watch_page":
                return ("", [], "unavailable")
            return (
                "Full transcript",
                [{"start_ms": 0, "duration_ms": 2000, "text": "Full transcript"}],
                "android_player_xml",
            )

        module._youtube_fetch_transcript_from_track = fake_fetch
        payload = module._youtube_inspect_payload("https://youtu.be/dQw4w9WgXcQ", preferred_lang="en")
        self.assertTrue(payload["transcript_available"])
        self.assertEqual(payload["transcript_track_source"], "android_player")
        self.assertEqual(payload["transcript_fetch_mode"], "android_player_xml")
        self.assertEqual(
            payload["transcript_sources_tried"],
            ["android_player:en:English"],
        )

    def test_cmd_youtube_inspect_json_save_writes_default_artifact(self) -> None:
        module = load_cli_module()
        fake_payload = {
            "schema_version": "1.0.0",
            "kind": "youtube_source",
            "retrieved_at_utc": "2026-03-25T12:00:00Z",
            "source_url": "https://youtu.be/dQw4w9WgXcQ",
            "canonical_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "video_id": "dQw4w9WgXcQ",
            "title": "Video title",
            "author_name": "Author",
            "author_url": "",
            "thumbnail_url": "",
            "channel_id": "",
            "description": "Description",
            "duration_seconds": 42,
            "published_at": "2026-03-25",
            "playability_status": "OK",
            "transcript_track_count": 1,
            "available_transcript_tracks": [
                {"language_code": "en", "name": "English", "kind": "manual", "source": "android_player"}
            ],
            "transcript_available": True,
            "transcript_language": "en",
            "transcript_track_name": "English",
            "transcript_track_source": "android_player",
            "transcript_kind": "manual",
            "transcript_fetch_mode": "android_player_xml",
            "transcript_text": "Hello world",
            "transcript_segments": [{"start_ms": 0, "duration_ms": 1000, "text": "Hello world"}],
            "transcript_sources_tried": ["android_player:en:English"],
            "warnings": [],
            "text_bundle": "Title: Video title\n\nTranscript:\nHello world",
        }
        module._youtube_inspect_payload = lambda raw_url, preferred_lang="": fake_payload

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = module.cmd_youtube_inspect(
                    argparse.Namespace(
                        repo_root=str(root),
                        url="https://youtu.be/dQw4w9WgXcQ",
                        lang="",
                        save=True,
                        out="",
                        format="",
                        force=False,
                        json_output=True,
                    )
                )
            self.assertEqual(result, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["saved"])
            self.assertEqual(payload["path"], "orp/external/youtube/dQw4w9WgXcQ.json")
            saved = root / payload["path"]
            self.assertTrue(saved.exists())
            saved_payload = json.loads(saved.read_text(encoding="utf-8"))
            self.assertEqual(saved_payload["video_id"], "dQw4w9WgXcQ")
            self.assertEqual(saved_payload["transcript_text"], "Hello world")

    def test_youtube_source_schema_exists(self) -> None:
        module = load_cli_module()
        schema_path = module._youtube_source_schema_path()
        self.assertTrue(schema_path.exists())
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["title"], "ORP YouTube Source Artifact")


if __name__ == "__main__":
    unittest.main()
