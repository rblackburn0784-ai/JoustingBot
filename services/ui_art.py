"""v0.9.2d — optional, lossless-source visual backgrounds for interactive Discord menus.

The supplied Shop/Knight/Horse PNGs are user-owned local assets. This renderer
never fabricates equipment overlays or changes stats, ownership, purchases, or
saved characters. When art has not been installed, menus remain fully usable.
"""
from __future__ import annotations

import io
import json
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE / "assets" / "ui"
MAPPING = BASE / "assets" / "jousting" / "visual_mapping.json"
SIZE = (1280, 720)
SCREENS = {
    "shop": "shop.png",
    "knight": "knight.png",
    "horse": "horse_{coat}.png",
}
COATS = {"bay", "black", "chestnut", "grey", "white"}
HORSE_SLOTS = (
    ("Bridle", None),
    ("Saddle", None),
    ("Saddle Blanket", None),
    ("Chest Barding", "barding"),
    ("Horseshoes", None),
    ("Face Armor", None),
    ("Leg Armor", None),
    ("Tail Gear", None),
)
KNIGHT_SLOTS = (
    ("Helmet", None),
    ("Armour", "armour"),
    ("Gauntlets", None),
    ("Boots", None),
    ("Lance", "lance"),
    ("Shield", None),
    ("Cloak", None),
    ("Accessory", None),
)


def selected_coat(breed: str | None, owner_id: int | None = None) -> str:
    """Use the same coat map as live sprite broadcasts and the stable."""
    defaults = {
        "courser": "bay", "destrier": "black", "rouncey": "chestnut",
        "palfrey": "grey", "charger": "white", "gray": "grey",
    }
    try:
        content = json.loads(MAPPING.read_text(encoding="utf-8"))
        defaults.update({str(k).lower(): str(v).lower()
                         for k, v in content.get("breed_to_coat", {}).items()
                         if str(v).lower() in COATS})
        if owner_id is not None:
            override = content.get("player_coats", {}).get(str(owner_id))
            if str(override).lower() in COATS:
                return str(override).lower()
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    raw = str(breed or "chestnut").strip().lower()
    coat = defaults.get(raw, raw)
    return coat if coat in COATS else "chestnut"


def screen_path(screen: str, coat: str = "chestnut") -> Path | None:
    if screen not in SCREENS:
        return None
    if screen == "horse":
        coat = str(coat).lower()
        if coat not in COATS:
            coat = selected_coat(coat)
        filename = SCREENS[screen].format(coat=coat)
    else:
        filename = SCREENS[screen]
    return ROOT / filename


@lru_cache(maxsize=16)
def _background(path: str, mtime_ns: int) -> Image.Image:
    with Image.open(path) as src:
        src = src.convert("RGB")
        return src.resize(SIZE, Image.Resampling.LANCZOS)


def _font(size: int):
    for font in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit(draw, text: str, font, max_width: int) -> str:
    text = str(text)
    while text and draw.textbbox((0, 0), text, font=font)[2] > max_width:
        text = text[:-2].rstrip() + "…" if len(text) > 2 else ""
    return text


def _slots(canvas: Image.Image, screen: str, equipped: dict | None, focus: str | None):
    """Fill the artwork's existing EMPTY BLACK slot windows; no new gear art yet."""
    draw = ImageDraw.Draw(canvas)
    labels = HORSE_SLOTS if screen == "horse" else KNIGHT_SLOTS
    equipment = equipped or {}
    scale = SIZE[0] / 1648.0
    for n, (title, slot) in enumerate(labels):
        column = 0 if n < 4 else 1
        row = n % 4
        # Black slots on provided 1648x928 layouts (not the labelled icon plaques).
        x0 = round((302 if column == 0 else 1205) * scale)
        x1 = round((442 if column == 0 else 1344) * scale)
        y0 = round((142 + 188 * row) * scale)
        y1 = round((265 + 188 * row) * scale)
        if slot is None:
            # Do not suggest non-existent equipment can be purchased yet.
            caption = "COMING SOON"
            line = "Art expansion"
        else:
            caption = "SELECTED" if focus == slot else "EQUIPPED"
            line = str(equipment.get(slot) or "Starter gear")
        rect = (x0, y0, x1, y1)
        if focus == slot:
            draw.rounded_rectangle(rect, radius=5, outline=(226, 185, 90), width=2)
        bg = (x0+3, y1-45, x1-3, y1-6)
        draw.rounded_rectangle(bg, radius=5, fill=(8, 13, 22))
        small = _font(12)
        major = _font(13)
        draw.text((x0+7, y1-40), _fit(draw, caption, small, x1-x0-13),
                  font=small, fill=(212, 180, 117))
        draw.text((x0+7, y1-23), _fit(draw, line, major, x1-x0-13),
                  font=major, fill=(247, 239, 220))


def render(screen: str, *, coat: str = "chestnut",
           equipped: dict | None = None, focus: str | None = None) -> bytes | None:
    """Return JPEG bytes to attach to the SAME private menu message.

    Do not construct mock-ups from the joust battle sprites when the user-provided
    PNGs are absent. The embed/controls work without art.
    """
    path = screen_path(screen, coat)
    if path is None or not path.is_file():
        return None
    try:
        picture = _background(str(path), path.stat().st_mtime_ns).copy()
        if screen in ("horse", "knight"):
            _slots(picture, screen, equipped, focus)
        stream = io.BytesIO()
        picture.save(stream, format="JPEG", quality=88, optimize=True)
        return stream.getvalue()
    except (OSError, ValueError):
        return None


def installed_screens() -> list[str]:
    return [p.name for p in ROOT.glob("*.png") if p.is_file()]
