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

WIDTH = 1400
HEIGHT = 900
SIDE_MARGIN = 64
SHELL_TOP = 188
BOTTOM_MARGIN = 128
WINDOW_PADDING = 28

OUTER_BG = "#050C13"
WINDOW_BG = "#081929"
WINDOW_EDGE = "#173B5A"
TITLEBAR_BG = "#10283D"
TERMINAL_BG = "#071525"
INK = "#EAF7F3"
MUTED = "#9AB2C8"
DIM = "#63798F"
ACCENT = "#70F0DF"
SKY = "#8AB8FF"
SOFT = "#F3D9B7"
CORAL = "#FF9B88"
LIME = "#BDF59E"
GOLD = "#F6D06F"
MASCOT_DARK = "#14324A"
MASCOT_BODY = "#DDFCF4"
MASCOT_WING = "#62DDCC"

FONT_MONO = "/System/Library/Fonts/Menlo.ttc"
FONT_SANS_BOLD = "/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf"


def load_font(path: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


MONO_18 = load_font(FONT_MONO, 18)
MONO_20 = load_font(FONT_MONO, 20)
MONO_24 = load_font(FONT_MONO, 24)
MONO_32 = load_font(FONT_MONO, 32)
SANS_22 = load_font(FONT_SANS_BOLD, 22)
SANS_26 = load_font(FONT_SANS_BOLD, 26)
SANS_34 = load_font(FONT_SANS_BOLD, 34)
SANS_52 = load_font(FONT_SANS_BOLD, 52)
SANS_66 = load_font(FONT_SANS_BOLD, 66)

CONTENT_X = SIDE_MARGIN + WINDOW_PADDING + 46
CONTENT_Y = SHELL_TOP + 132
CONTENT_WIDTH = 760
LINE_HEIGHT = 34
TYPING_MS = 48
COMMAND_SETTLE_MS = 320
OUTPUT_STEP_MS = 180
SCENE_HOLD_MS = 8500

SCENES = [
    {
        "id": "home",
        "label": "field guide",
        "headline": "context before claims",
        "sermon": [
            "Read the room first.",
            "Then route the agent.",
            "Receipts beat vibes.",
        ],
        "command": "orp home",
        "output_font": "small",
        "line_height": 30,
        "output": [
            ("ORP 0.4.28", ACCENT),
            ("Agent-first CLI for workspace ledgers, agendas, secrets, and research workflows.", INK),
            ("Daily Loop", SKY),
            ("  orp workspace tabs main", ACCENT),
            ("  orp project refresh --json", INK),
            ("  orp agenda focus", SOFT),
            ("  orp mode breakdown granular-breakdown", SKY),
        ],
    },
    {
        "id": "workspace",
        "label": "workspace",
        "headline": "save every live thread",
        "sermon": [
            "A tab is a thread.",
            "A thread needs a path.",
            "A crash should not win.",
        ],
        "command": "orp workspace tabs main",
        "output": [
            ("saved tabs: 24", ACCENT),
            ("projects: grouped by repo", SKY),
            ("orp", INK),
            ("  path: ~/code/orp", INK),
            ("  resume: cd '~/code/orp' && codex resume 019d32d3-d8b2-7fa2-aaec-c74b5134afd6", SOFT),
            ("claude and codex recovery commands stay side-by-side", ACCENT),
        ],
    },
    {
        "id": "secrets",
        "label": "secrets",
        "headline": "save keys without spilling them",
        "sermon": [
            "Name the credential.",
            "Hide the value.",
            "Reuse it safely.",
        ],
        "command": "orp secrets add --alias openai-primary --provider openai",
        "output": [
            ("Secret value:", ACCENT),
            ("  sk-...", INK),
            ("secret.alias=openai-primary", SKY),
            ("secret.provider=openai", ACCENT),
            ("username: optional", INK),
            ("value: stored locally, not printed", SKY),
            ("next: orp secrets keychain-spend-policy openai-primary --daily-spend-cap-usd 5", SOFT),
        ],
    },
    {
        "id": "research",
        "label": "research",
        "headline": "ask in lanes, spend with consent",
        "sermon": [
            "Dry-run the plan.",
            "Use OpenAI when it helps.",
            "Spend only on purpose.",
        ],
        "command": 'orp research ask "Should we expand this project?" --json',
        "output": [
            ("status: planned", ACCENT),
            ("lanes: plan -> reason -> web -> deep research", SKY),
            ("openai: ready when --execute is explicit", INK),
            ("spend_preflight: checked before provider calls", SOFT),
            ("answer path: orp/research/<run_id>/ANSWER.json", ACCENT),
        ],
    },
    {
        "id": "governance",
        "label": "governance",
        "headline": "checkpoint the work, not the vibes",
        "sermon": [
            "Progress gets named.",
            "Repos stay recoverable.",
            "Evidence stays separate.",
        ],
        "command": 'orp checkpoint create -m "capture loop state"',
        "output": [
            ("checkpoint: capture loop state", ACCENT),
            ("branch: work/release-hardening", INK),
            ("backup: ready", SKY),
            ("doctor: clean enough to keep moving", ACCENT),
            ("boundary: ORP is process; proof lives in canonical artifacts", SOFT),
        ],
    },
    {
        "id": "breakdown",
        "label": "breakdown",
        "headline": "make hard work legible",
        "sermon": [
            "Broad first.",
            "Then lanes.",
            "Then atoms.",
        ],
        "command": "orp mode breakdown granular-breakdown",
        "output": [
            ("sequence:", ACCENT),
            ("  L0 whole frame", INK),
            ("  L1 boundary", SKY),
            ("  L2 major lanes", INK),
            ("  L4 atomic obligations", SOFT),
            ("  L7 durable checklist", ACCENT),
            ("use when the project feels bigger than your hands", SKY),
        ],
    },
    {
        "id": "share",
        "label": "publish",
        "headline": "share the protocol forward",
        "sermon": [
            "Open research is a relay.",
            "Make the next handoff kinder.",
            "Leave a map.",
        ],
        "command": "orp report summary --json",
        "output": [
            ("packet: ready", ACCENT),
            ("report: current state summarized", INK),
            ("handoff: agent-readable", SKY),
            ("install: npm install -g open-research-protocol", SOFT),
            ("message: keep research open, recoverable, and kind", ACCENT),
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
    for y in range(0, HEIGHT, 6):
        blend = y / max(1, HEIGHT)
        red = int(5 + blend * 4)
        green = int(12 + blend * 10)
        blue = int(19 + blend * 20)
        draw.rectangle((0, y, WIDTH, y + 6), fill=(red, green, blue))
    orbit_colors = [ACCENT, SKY, SOFT, ACCENT, SKY]
    orbit_points = [
        (84, 76),
        (WIDTH - 92, 78),
        (118, HEIGHT - 120),
        (268, HEIGHT - 188),
    ]
    for idx, (x, y) in enumerate(orbit_points):
        r = 8 if idx % 2 == 0 else 6
        color = orbit_colors[idx % len(orbit_colors)]
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def draw_terminal_shell(draw: ImageDraw.ImageDraw) -> tuple[int, int, int, int]:
    left = SIDE_MARGIN
    top = SHELL_TOP
    right = 966
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
    draw.text((label_x, 24), label, font=MONO_20, fill=DIM)
    headline = scene["headline"]
    headline_box = draw.textbbox((0, 0), headline, font=SANS_66)
    headline_x = (WIDTH - (headline_box[2] - headline_box[0])) // 2
    draw.text((headline_x, 58), headline, font=SANS_66, fill=ACCENT)


def draw_speech_bubble(draw: ImageDraw.ImageDraw, scene: dict) -> None:
    left, top, right, bottom = 996, 202, 1332, 398
    draw.rounded_rectangle((left, top, right, bottom), radius=28, fill="#0E2335", outline="#1E4969", width=2)
    draw.polygon([(1060, bottom - 2), (1096, bottom - 2), (1076, bottom + 34)], fill="#0E2335", outline="#1E4969")
    draw.text((left + 28, top + 22), "protocol note", font=MONO_20, fill=SKY)
    y = top + 62
    for line in scene.get("sermon", []):
        for wrapped in wrap_line(str(line), SANS_26, right - left - 54):
            draw.text((left + 28, y), wrapped, font=SANS_26, fill=INK)
            y += 32


def draw_mascot_mouth(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    scene: dict,
    pulse: int,
    scale: float = 1.0,
) -> None:
    expression = {
        "home": "smile",
        "workspace": "focused",
        "secrets": "wink",
        "research": "curious",
        "governance": "proud",
        "breakdown": "ooh",
        "share": "beam",
        "hero": "beam",
    }.get(str(scene.get("id", "")), "smile")
    def p(dx: float, dy: float) -> tuple[int, int]:
        return (round(cx + dx * scale), round(cy + dy * scale))

    def box(x1: float, y1: float, x2: float, y2: float) -> tuple[int, int, int, int]:
        return (*p(x1, y1), *p(x2, y2))

    width_3 = max(2, round(3 * scale))
    width_4 = max(2, round(4 * scale))
    width_5 = max(2, round(5 * scale))
    wobble = int(math.sin(pulse / 2.0) * 2 * scale)
    if expression == "focused":
        draw.arc(box(-20, 14, 20, 42), start=205, end=335, fill=MASCOT_DARK, width=width_4)
        draw.line((*p(-12, 32 + wobble), *p(12, 32 - wobble)), fill=MASCOT_DARK, width=width_3)
    elif expression == "wink":
        draw.arc(box(-22, 8, 22, 38), start=18, end=162, fill=CORAL, width=width_5)
        draw.ellipse(box(18, 18, 26, 26), fill=GOLD)
    elif expression == "curious":
        draw.ellipse(box(-12, 16, 12, 40), fill=MASCOT_DARK)
        draw.ellipse(box(-5, 22, 5, 34), fill=CORAL)
    elif expression == "proud":
        draw.arc(box(-26, 4, 26, 42), start=22, end=158, fill=MASCOT_DARK, width=width_5)
        draw.ellipse(box(-16, 30, -8, 38), fill=ACCENT)
        draw.ellipse(box(8, 30, 16, 38), fill=ACCENT)
    elif expression == "ooh":
        draw.ellipse(box(-15, 14, 15, 46), fill=MASCOT_DARK)
        draw.ellipse(box(-6, 23, 6, 37), fill="#FBE7C8")
    elif expression == "beam":
        draw.rounded_rectangle(box(-26, 16, 26, 42), radius=round(12 * scale), fill=MASCOT_DARK)
        for tooth_x in (-13, 0, 13):
            draw.line((*p(tooth_x, 17), *p(tooth_x, 40)), fill="#DDFCF4", width=max(1, round(2 * scale)))
        draw.arc(box(-28, 6, 28, 48), start=20, end=160, fill=CORAL, width=width_3)
    else:
        draw.arc(box(-24, 10, 24, 42), start=20, end=160, fill=MASCOT_DARK, width=width_5)
        draw.ellipse(box(-9, 30, 9, 38), fill=CORAL)


def draw_mascot(
    draw: ImageDraw.ImageDraw,
    scene: dict,
    pulse: int = 0,
    *,
    center: tuple[int, int] = (1136, 610),
    scale: float = 1.0,
) -> None:
    base_cx, base_cy = center
    cx = base_cx
    cy = base_cy + int(math.sin(pulse / 3.0) * 4 * scale)

    def p(dx: float, dy: float) -> tuple[int, int]:
        return (round(cx + dx * scale), round(cy + dy * scale))

    def box(x1: float, y1: float, x2: float, y2: float) -> tuple[int, int, int, int]:
        return (*p(x1, y1), *p(x2, y2))

    outline_width = max(2, round(3 * scale))
    eye_width = max(2, round(3 * scale))
    draw.ellipse(box(-82, 84, 82, 110), fill="#03101A")
    draw.polygon(
        [
            p(-78, -52),
            p(-50, -122),
            p(-16, -54),
            p(16, -54),
            p(50, -122),
            p(78, -52),
            p(66, 58),
            p(34, 88),
            p(-34, 88),
            p(-66, 58),
        ],
        fill=MASCOT_BODY,
        outline="#122B42",
    )
    draw.polygon([p(-48, -84), p(-28, -52), p(-62, -52)], fill="#CFFFF8")
    draw.polygon([p(48, -84), p(28, -52), p(62, -52)], fill="#CFFFF8")
    draw.pieslice(box(-86, -30, -38, 56), start=92, end=270, fill=MASCOT_WING, outline="#122B42", width=outline_width)
    draw.pieslice(box(38, -30, 86, 56), start=270, end=88, fill=MASCOT_WING, outline="#122B42", width=outline_width)
    draw.ellipse(box(-52, -40, -10, 4), fill=TERMINAL_BG, outline="#122B42", width=eye_width)
    draw.ellipse(box(10, -40, 52, 4), fill=TERMINAL_BG, outline="#122B42", width=eye_width)
    blink = pulse % 17 == 0
    if blink:
        draw.line((*p(-43, -18), *p(-19, -18)), fill=ACCENT, width=max(2, round(4 * scale)))
        draw.line((*p(19, -18), *p(43, -18)), fill=ACCENT, width=max(2, round(4 * scale)))
    else:
        draw.ellipse(box(-39, -30, -23, -14), fill=ACCENT)
        draw.ellipse(box(23, -30, 39, -14), fill=ACCENT)
    draw.polygon([p(-10, -2), p(10, -2), p(0, 15)], fill=GOLD)
    draw_mascot_mouth(draw, cx, cy, scene, pulse, scale=scale)
    draw.ellipse(box(-18, 66, -6, 78), fill=ACCENT)
    draw.ellipse(box(6, 66, 18, 78), fill=SKY)


def render_scene(scene: dict, typed_chars: Optional[int] = None, shown_lines: int = 0, cursor: bool = False) -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), OUTER_BG)
    draw = ImageDraw.Draw(image)
    draw_background(draw)
    draw_scene_header(draw, scene)
    draw_terminal_shell(draw)
    pulse = int((typed_chars or 0) + shown_lines * 3)
    draw_speech_bubble(draw, scene)
    draw_mascot(draw, scene, pulse=pulse)

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
    footer_y = HEIGHT - 84
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
    draw.text((gutter, 20), "ORP mascot walkthrough storyboard", font=SANS_34, fill=INK)
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
    for old_scene in ASSETS.glob("terminal-scene-*.png"):
        old_scene.unlink()
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
