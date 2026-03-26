# ORP YouTube Inspect

`orp youtube inspect` is ORP's first-class public-source ingestion surface for
YouTube videos.

It gives agents and users a stable way to turn a YouTube link into:

- normalized video metadata,
- full public transcript text and segment timing when caption tracks are available,
- segment-level timing rows,
- and one agent-friendly `text_bundle` field that can be handed directly into
  summarization, extraction, comparison, or kernel-shaped artifact creation.

## Why this exists

Agents often receive a raw YouTube URL and are asked:

- what is this video about?
- summarize it,
- extract claims,
- capture action items,
- compare it against repo work,
- or turn it into a canonical ORP artifact.

Without a built-in surface, each agent has to improvise scraping, transcript
discovery, and output shape. ORP now treats this as a real protocol ability.

## Command

```bash
orp youtube inspect https://www.youtube.com/watch?v=<video_id> --json
```

Optional persistence:

```bash
orp youtube inspect https://www.youtube.com/watch?v=<video_id> --save --json
orp youtube inspect https://www.youtube.com/watch?v=<video_id> --out analysis/source.youtube.json --json
```

## Output shape

The canonical artifact schema is:

- `spec/v1/youtube-source.schema.json`

The command returns:

- source identity:
  - `source_url`
  - `canonical_url`
  - `video_id`
- metadata:
  - `title`
  - `author_name`
  - `author_url`
  - `thumbnail_url`
  - `channel_id`
  - `description`
  - `duration_seconds`
  - `published_at`
  - `playability_status`
- transcript fields:
  - `transcript_track_count`
  - `available_transcript_tracks`
  - `transcript_available`
  - `transcript_language`
  - `transcript_track_name`
  - `transcript_track_source`
  - `transcript_kind`
  - `transcript_fetch_mode`
  - `transcript_text`
  - `transcript_segments`
  - `transcript_sources_tried`
- agent-ready bundle:
  - `text_bundle`
- capture notes:
  - `warnings`

## Save behavior

`--save` writes the artifact to:

```text
orp/external/youtube/<video_id>.json
```

This keeps YouTube ingestion consistent with ORP's larger local-first artifact
discipline while staying outside the evidence boundary by default.

## Important boundary

`orp youtube inspect` returns public source context. It does **not** make the
result canonical evidence by itself.

When public caption tracks exist, ORP now attempts full transcript ingestion
across multiple retrieval strategies and records which track/source succeeded.
If a video has no accessible caption tracks, ORP reports that honestly instead
of silently fabricating a transcript.

If a video matters for repo truth, the agent should still:

1. inspect the video,
2. summarize or structure the relevant claims,
3. promote that into a typed ORP artifact when appropriate,
4. and cite the saved source artifact path alongside any downstream result.
