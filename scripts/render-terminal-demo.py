#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
GIF_PATH = ASSETS / "terminal-demo.gif"
POSTER_PATH = ASSETS / "terminal-demo-poster.png"
STORYBOARD_PATH = ASSETS / "terminal-demo-storyboard.png"

WIDTH = 1360
HEIGHT = 840
SIDE_MARGIN = 72
SHELL_TOP = 132
BOTTOM_MARGIN = 72
WINDOW_PADDING = 28

OUTER_BG = "#07131F"
WINDOW_BG = "#0A1728"
WINDOW_EDGE = "#16314D"
TITLEBAR_BG = "#10243A"
TERMINAL_BG = "#0C1B2E"
INK = "#E7F4F1"
MUTED = "#8FA7BF"
DIM = "#6C819A"
ACCENT = "#6EE7D8"
SKY = "#8DBEFF"
SOFT = "#F1D6B8"
CORAL = "#FF9A86"
LIME = "#BDEB9B"
GOLD = "#F6D98D"

FONT_MONO = "/System/Library/Fonts/Menlo.ttc"
FONT_SANS_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def load_font(path: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


MONO_18 = load_font(FONT_MONO, 18)
MONO_20 = load_font(FONT_MONO, 20)
MONO_24 = load_font(FONT_MONO, 24)
MONO_28 = load_font(FONT_MONO, 28)
MONO_32 = load_font(FONT_MONO, 32)
SANS_22 = load_font(FONT_SANS_BOLD, 22)
SANS_26 = load_font(FONT_SANS_BOLD, 26)
SANS_34 = load_font(FONT_SANS_BOLD, 34)
SANS_52 = load_font(FONT_SANS_BOLD, 52)

CONTENT_X = SIDE_MARGIN + WINDOW_PADDING + 46
CONTENT_Y = SHELL_TOP + 138
CONTENT_WIDTH = (WIDTH - SIDE_MARGIN - WINDOW_PADDING) - CONTENT_X - 20
LINE_HEIGHT = 34
TYPING_MS = 75
COMMAND_SETTLE_MS = 320
OUTPUT_STEP_MS = 240
SCENE_HOLD_MS = 33000

SCENES = [
    {
        "id": "home",
        "label": "home",
        "headline": "discover the surface",
        "command": "orp home",
        "output_font": "small",
        "line_height": 30,
        "output": [
            ("ORP 0.4.13", ACCENT),
            ("Agent-first CLI for workspace ledgers, secrets, scheduling, and research workflows.", INK),
            ("Repo", SKY),
            ("  root: /Volumes/Code_2TB/code/orp", INK),
            ("  config: orp.yml (missing)", ACCENT),
            ("  git: yes, branch=main, commit=4cde66c", SOFT),
            ("Daily Loop", SKY),
            ("  orp workspace tabs main", ACCENT),
            ('  orp secrets add --alias <alias> --label "<label>" --provider <provider>', INK),
            ('  orp checkpoint create -m "capture loop state"', SOFT),
        ],
    },
    {
        "id": "hosted",
        "label": "hosted",
        "headline": "see the control plane",
        "command": "orp workspaces list",
        "output": [
            ("workspaces.count=2", ACCENT),
            ("cursor=", INK),
            ("has_more=false", SKY),
            ("source=idea_bridge", ACCENT),
            ("---", DIM),
            ("workspace.id=main-cody-1", INK),
            ("workspace.title=main-cody-1", SKY),
            ("workspace.tab_count=18", SOFT),
        ],
    },
    {
        "id": "secrets",
        "label": "secrets",
        "headline": "save the key once, reuse it later",
        "command": 'orp secrets add --alias openai-primary --label "OpenAI Primary" --provider openai',
        "output": [
            ("Secret value:", ACCENT),
            ("  sk-...", INK),
            ("secret.alias=openai-primary", SKY),
            ("secret.provider=openai", ACCENT),
            ("secret.kind=api_key", INK),
            ("secret.status=active", SKY),
            ("next: orp secrets resolve openai-primary --reveal", SOFT),
        ],
    },
    {
        "id": "workspace",
        "label": "workspace",
        "headline": "keep the workspace ledger",
        "command": "orp workspace tabs main",
        "output": [
            ("saved tabs: 11", ACCENT),
            ("ledger: hosted canonical + local cache", INK),
            ("recovery: copy the exact cd && resume command you need", SKY),
            ("tools: codex resume and claude --resume are both tracked", ACCENT),
            ("tail tabs: orp · orp-web-app · RigidityCore · frg-site", SOFT),
        ],
    },
    {
        "id": "schedule",
        "label": "schedule",
        "headline": "automate the next loop",
        "command": 'orp schedule add codex --name morning-summary --prompt "Summarize this repo"',
        "output": [
            ("ORP Scheduled Job Created", ACCENT),
            ("Name: morning-summary", INK),
            ("Kind: codex", SKY),
            ("Schedule: daily at 09:00", ACCENT),
            ("Prompt source: inline", INK),
            ("Codex session id: none", SKY),
            ("Next steps:", ACCENT),
            ("  orp schedule run morning-summary", SOFT),
        ],
    },
    {
        "id": "governance",
        "label": "governance",
        "headline": "checkpoint the repo safely",
        "command": 'orp checkpoint create -m "capture loop state"',
        "output": [
            ("commit=7f3c2a1", ACCENT),
            ("branch=work/release-hardening", INK),
            ("message=checkpoint: capture loop state", SKY),
            ("checkpoint_log=orp/checkpoints/CHECKPOINT_LOG.md", ACCENT),
            ("git_runtime=orp/git/runtime.json", SOFT),
        ],
    },
    {
        "id": "planning",
        "label": "planning",
        "headline": "track the live point",
        "command": "orp frontier state",
        "output": [
            ("program_id=sunflower-coda", ACCENT),
            ("active_version=v10", INK),
            ("active_milestone=v10.3", SKY),
            ("active_phase=395", ACCENT),
            ("band=verification", INK),
            ("next_action=Execute Phase 395", SKY),
            ("blocked_by=(none)", SOFT),
        ],
    },
    {
        "id": "synthesis",
        "label": "synthesis",
        "headline": "scan, synthesize, collaborate",
        "command": "orp exchange repo synthesize /path/to/source",
        "output": [
            ("exchange_id=exc_20260331_001", ACCENT),
            ("source.mode=local_path", INK),
            ("source.local_path=/path/to/source", SKY),
            ("source.git_present=true", ACCENT),
            ("artifacts.exchange_json=orp/exchange/exc_20260331_001/EXCHANGE.json", INK),
            ("artifacts.summary_md=orp/exchange/exc_20260331_001/SUMMARY.md", SKY),
            ("artifacts.transfer_map_md=orp/exchange/exc_20260331_001/TRANSFER_MAP.md", SOFT),
        ],
    },
    {
        "id": "mode",
        "label": "mode",
        "headline": "change the lens",
        "command": "orp mode nudge sleek-minimal-progressive",
        "output": [
            ("mode.id=sleek-minimal-progressive", ACCENT),
            ("mode.label=Sleek Minimal Progressive", INK),
            ("nudge.title=Subtractive Spark", SKY),
            ("nudge.prompt=remove one thing before adding one surprising move", ACCENT),
            ("nudge.twist=keep the architecture cleaner than the idea feels", INK),
            ("nudge.release=drop the first obvious framing", SOFT),
            ("nudge.micro_loop:", ACCENT),
            ("- zoom out, rotate, re-enter deliberately", SKY),
        ],
    },
]


def wrap_line(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        trial_box = font.getbbox(trial)
        trial_width = trial_box[2] - trial_box[0]
        if trial_width <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def wrap_command(command: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = command.split(" ")
    lines: list[str] = []
    current = "$"
    for word in words:
        trial = f"{current} {word}".strip()
        trial_box = font.getbbox(trial)
        trial_width = trial_box[2] - trial_box[0]
        if trial_width <= max_width or current == "$":
            current = trial
        else:
            lines.append(current)
            current = f"  {word}"
    if current:
        lines.append(current)
    return lines


def draw_background(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=OUTER_BG)
    orbit_colors = [ACCENT, SKY, SOFT, ACCENT, SKY]
    orbit_points = [
        (84, 70),
        (WIDTH - 88, 66),
        (106, HEIGHT - 118),
        (232, HEIGHT - 176),
        (WIDTH - 210, HEIGHT - 162),
        (WIDTH - 116, HEIGHT - 110),
    ]
    for idx, (x, y) in enumerate(orbit_points):
        r = 8 if idx % 2 == 0 else 6
        color = orbit_colors[idx % len(orbit_colors)]
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
    draw.line((106, HEIGHT - 118, 232, HEIGHT - 176), fill="#17324D", width=2)
    draw.line((WIDTH - 210, HEIGHT - 162, WIDTH - 116, HEIGHT - 110), fill="#17324D", width=2)


def draw_terminal_shell(draw: ImageDraw.ImageDraw) -> tuple[int, int, int, int]:
    left = SIDE_MARGIN
    top = SHELL_TOP
    right = WIDTH - SIDE_MARGIN
    bottom = HEIGHT - BOTTOM_MARGIN
    draw.rounded_rectangle((left, top, right, bottom), radius=36, fill=WINDOW_BG, outline=WINDOW_EDGE, width=2)
    draw.rounded_rectangle(
        (left + WINDOW_PADDING, top + WINDOW_PADDING, right - WINDOW_PADDING, bottom - WINDOW_PADDING),
        radius=24,
        fill=TERMINAL_BG,
        outline="#1A3A5A",
        width=2,
    )
    title_bottom = top + WINDOW_PADDING + 62
    draw.rounded_rectangle(
        (left + WINDOW_PADDING, top + WINDOW_PADDING, right - WINDOW_PADDING, title_bottom),
        radius=24,
        fill=TITLEBAR_BG,
    )
    draw.rectangle((left + WINDOW_PADDING, title_bottom - 24, right - WINDOW_PADDING, title_bottom), fill=TITLEBAR_BG)
    for idx, color in enumerate((CORAL, GOLD, LIME)):
        x = left + WINDOW_PADDING + 22 + (idx * 28)
        y = top + WINDOW_PADDING + 20
        draw.ellipse((x, y, x + 14, y + 14), fill=color)
    draw.text((left + WINDOW_PADDING + 112, top + WINDOW_PADDING + 12), "open-research-protocol demo", font=SANS_22, fill=INK)
    right_label = "agent-first research loop"
    right_box = draw.textbbox((0, 0), right_label, font=MONO_18)
    right_x = right - WINDOW_PADDING - 22 - (right_box[2] - right_box[0])
    draw.text((right_x, top + WINDOW_PADDING + 18), right_label, font=MONO_18, fill=DIM)
    return (left, top, right, bottom)


def draw_scene_header(draw: ImageDraw.ImageDraw, scene: dict) -> None:
    label = scene["label"].upper()
    label_box = draw.textbbox((0, 0), label, font=MONO_20)
    label_x = (WIDTH - (label_box[2] - label_box[0])) // 2
    draw.text((label_x, 18), label, font=MONO_20, fill=DIM)
    headline = scene["headline"]
    headline_box = draw.textbbox((0, 0), headline, font=SANS_52)
    headline_x = (WIDTH - (headline_box[2] - headline_box[0])) // 2
    draw.text((headline_x, 42), headline, font=SANS_52, fill=ACCENT)


def render_scene(scene: dict, typed_chars: Optional[int] = None, shown_lines: int = 0, cursor: bool = False) -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), OUTER_BG)
    draw = ImageDraw.Draw(image)
    draw_background(draw)
    draw_scene_header(draw, scene)
    draw_terminal_shell(draw)

    command = scene["command"] if typed_chars is None else scene["command"][:typed_chars]
    command_lines = wrap_command(command, MONO_32, CONTENT_WIDTH)
    if cursor and command_lines:
        command_lines[-1] = f"{command_lines[-1]}_"
    command_y = CONTENT_Y + 14
    for line in command_lines:
        draw.text((CONTENT_X, command_y), line, font=MONO_32, fill=ACCENT)
        command_y += 40

    output_font = MONO_24 if scene.get("output_font") != "small" else MONO_20
    line_height = int(scene.get("line_height", LINE_HEIGHT))
    content_max_y = HEIGHT - BOTTOM_MARGIN - WINDOW_PADDING - 20
    y = command_y + 38
    for text, color in scene["output"][:shown_lines]:
        if y > content_max_y:
            break
        for line in wrap_line(text, output_font, CONTENT_WIDTH):
            if y > content_max_y:
                break
            draw.text((CONTENT_X, y), line, font=output_font, fill=color)
            y += line_height

    footer = "npm install -g open-research-protocol"
    footer_box = draw.textbbox((0, 0), footer, font=MONO_24)
    footer_width = (footer_box[2] - footer_box[0]) + 46
    footer_x = (WIDTH - footer_width) // 2
    footer_y = HEIGHT - 118
    draw.rounded_rectangle((footer_x, footer_y, footer_x + footer_width, footer_y + 54), radius=15, fill=ACCENT)
    draw.text((footer_x + 23, footer_y + 14), footer, font=MONO_24, fill=WINDOW_BG)
    return image


def build_storyboard(final_frames: list[Image.Image]) -> Image.Image:
    thumb_width = 560
    thumb_height = int(thumb_width * HEIGHT / WIDTH)
    cols = 3 if len(final_frames) > 6 else 2
    rows = max(1, math.ceil(len(final_frames) / cols))
    gutter = 24
    board_width = thumb_width * cols + gutter * (cols + 1)
    board_height = thumb_height * rows + gutter * (rows + 1) + 72
    storyboard = Image.new("RGBA", (board_width, board_height), OUTER_BG)
    draw = ImageDraw.Draw(storyboard)
    draw.text((gutter, 20), "ORP terminal walkthrough storyboard", font=SANS_34, fill=INK)
    for idx, frame in enumerate(final_frames):
        thumb = frame.copy()
        thumb.thumbnail((thumb_width, thumb_height))
        row = idx // cols
        col = idx % cols
        x = gutter + col * (thumb_width + gutter)
        y = 72 + gutter + row * (thumb_height + gutter)
        storyboard.alpha_composite(thumb, (x, y))
    return storyboard


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    frames: list[Image.Image] = []
    durations: list[int] = []
    final_scene_frames: list[Image.Image] = []

    for index, scene in enumerate(SCENES, start=1):
        command = scene["command"]
        step = 2 if len(command) < 28 else 4
        for typed in range(1, len(command) + 1, step):
            frames.append(render_scene(scene, typed_chars=typed, shown_lines=0, cursor=True))
            durations.append(TYPING_MS)
        frames.append(render_scene(scene, typed_chars=len(command), shown_lines=0, cursor=False))
        durations.append(COMMAND_SETTLE_MS)
        for shown_lines in range(1, len(scene["output"]) + 1):
            frame = render_scene(scene, typed_chars=len(command), shown_lines=shown_lines, cursor=False)
            frames.append(frame)
            durations.append(OUTPUT_STEP_MS if shown_lines < len(scene["output"]) else SCENE_HOLD_MS)
            if shown_lines == len(scene["output"]):
                final_scene_frames.append(frame.copy())
                scene_path = ASSETS / f"terminal-scene-{index:02d}-{scene['id']}.png"
                frame.save(scene_path)

    poster = final_scene_frames[2] if len(final_scene_frames) >= 3 else final_scene_frames[0]
    poster.save(POSTER_PATH)
    storyboard = build_storyboard(final_scene_frames)
    storyboard.save(STORYBOARD_PATH)
    frames[0].save(
        GIF_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"WROTE {GIF_PATH}")
    print(f"WROTE {POSTER_PATH}")
    print(f"WROTE {STORYBOARD_PATH}")
    for index, scene in enumerate(SCENES, start=1):
        scene_name = f"terminal-scene-{index:02d}-{scene['id']}.png"
        print(f"WROTE {ASSETS / scene_name}")


if __name__ == "__main__":
    main()
