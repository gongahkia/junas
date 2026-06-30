#!/usr/bin/env python3
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = ROOT / "test" / "fixtures" / "outlook_smart_alert_messages.json"
OUT_DIR = ROOT / "docs" / "assets" / "outlook"
IMAGE_SIZE = (1200, 760)


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


FONTS = {
    "title": _font(30, bold=True),
    "heading": _font(22, bold=True),
    "body": _font(20),
    "small": _font(15),
    "mono": _font(16),
}


def _draw_wrapped(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], width: int, font: Any, fill: str) -> int:
    x, y = xy
    chars = max(32, width // 10)
    for line in textwrap.wrap(text, width=chars):
        draw.text((x, y), line, font=font, fill=fill)
        y += 28
    return y


def _rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str | None = None) -> None:
    draw.rounded_rectangle(box, radius=18, fill=fill, outline=outline, width=2 if outline else 1)


def _base_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", IMAGE_SIZE, "#f3f6fb")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 76, IMAGE_SIZE[1]), fill="#0f6cbd")
    for index, label in enumerate(("Mail", "Calendar", "People", "Files")):
        y = 34 + index * 64
        draw.rounded_rectangle((16, y, 60, y + 44), radius=10, fill="#185abd" if index == 0 else "#2b7cd3")
        draw.text((24, y + 12), label[0], font=FONTS["body"], fill="#ffffff")
    draw.rectangle((76, 0, IMAGE_SIZE[0], 64), fill="#ffffff")
    draw.text((104, 19), "Outlook", font=FONTS["heading"], fill="#1f2937")
    draw.text((1030, 22), "New message", font=FONTS["small"], fill="#4b5563")
    _rounded(draw, (122, 104, 1080, 682), "#ffffff", "#d9e2ec")
    draw.text((154, 136), "To: outside.counsel@example.com", font=FONTS["small"], fill="#4b5563")
    draw.line((154, 164, 1048, 164), fill="#e5e7eb", width=1)
    draw.text((154, 188), "Subject: Project Raven update", font=FONTS["small"], fill="#4b5563")
    draw.line((154, 216, 1048, 216), fill="#e5e7eb", width=1)
    body = (
        "Synthetic email body used for Smart Alerts rendering. "
        "No real mailbox, tenant, or recipient data is captured."
    )
    _draw_wrapped(draw, body, (154, 250), 760, FONTS["body"], "#374151")
    return image, draw


def _fixture_summary(name: str, data: dict[str, Any]) -> list[str]:
    lines = [f"state: {name}", f"mode: {data['mode']}", f"allowEvent: {str(data['allowEvent']).lower()}"]
    if data.get("sendModeOverride"):
        lines.append(f"sendModeOverride: {data['sendModeOverride']}")
    return lines


def render_state(name: str, data: dict[str, Any]) -> None:
    image, draw = _base_canvas()
    color = {
        "allow": "#10893e",
        "warn": "#f59e0b",
        "block": "#dc2626",
        "approval_required": "#7c3aed",
    }[name]
    title = {
        "allow": "Send allowed",
        "warn": "Junas review warning",
        "block": "Junas policy block",
        "approval_required": "Reviewer approval required",
    }[name]
    message = data.get("errorMessage") or "No Smart Alert dialog is shown for allowEvent=true."
    _rounded(draw, (284, 188, 916, 530), "#ffffff", "#cbd5e1")
    draw.rounded_rectangle((318, 226, 370, 278), radius=14, fill=color)
    draw.text((392, 226), title, font=FONTS["title"], fill="#111827")
    y = _draw_wrapped(draw, message, (392, 276), 450, FONTS["body"], "#111827")
    y += 18
    for line in _fixture_summary(name, data):
        draw.text((392, y), line, font=FONTS["mono"], fill="#4b5563")
        y += 24
    draw.text(
        (318, 492),
        "Rendered from test/fixtures/outlook_smart_alert_messages.json",
        font=FONTS["small"],
        fill="#6b7280",
    )
    if name == "allow":
        draw.rounded_rectangle((748, 584, 1028, 628), radius=8, fill="#0f6cbd")
        draw.text((833, 595), "Send", font=FONTS["body"], fill="#ffffff")
    else:
        draw.rounded_rectangle((688, 438, 820, 482), radius=8, fill="#ffffff", outline="#cbd5e1", width=1)
        draw.text((718, 449), "Cancel", font=FONTS["body"], fill="#374151")
        draw.rounded_rectangle((836, 438, 1030, 482), radius=8, fill="#0f6cbd")
        button = "Send anyway" if name == "warn" else "Open Junas Review"
        draw.text((858, 449), button, font=FONTS["body"], fill="#ffffff")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(OUT_DIR / f"outlook-smart-alert-{name}.png")


def main() -> int:
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for name in ("allow", "warn", "block", "approval_required"):
        render_state(name, fixtures[name])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
