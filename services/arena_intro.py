"""v2.9.3e: arena-specific pre-joust art, with no combat or storage writes.

Six illustrated templates live in assets/ui/intro_screens/. Red is left
(fighter_a), blue is right (fighter_b), regardless of who wins.
"""
from __future__ import annotations

from io import BytesIO
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from services.arenas import ARENAS
from services.live_banner_art import draw_side_banners, entrant_banner_key, NPC_BY_ID

LOG = logging.getLogger(__name__)
ART_ROOT = Path(__file__).resolve().parents[1] / "assets" / "ui" / "intro_screens"
SIZE = (1672, 941)
ARENA_FILES = {key: f"{key}_intro.png" for key in ARENAS}
INK = (64, 37, 19)
RED_NAME = (151, 716, 573, 812)
BLUE_NAME = (1093, 716, 1515, 812)
EVENT_RECT = (545, 114, 1127, 196)
ARENA_RECT = (609, 191, 1063, 239)
RED_BANNER = (145, 76, 182, 231)
BLUE_BANNER = (1345, 76, 182, 231)
CREST_RECT = (806, 237, 870, 304)
CREST_KEYS = {"friendly", "challenge", "training", "tournament", "tournament_final"}
EVENT_LABELS = {
    "instant": "FRIENDLY JOUST",
    "challenge": "CHALLENGE JOUST",
    "training": "TRAINING JOUST",
    "tournament": "TOURNAMENT MATCH",
}


def event_type(prepared) -> str:
    override = getattr(prepared, "intro_event_type", None)
    if isinstance(override, str) and override.strip():
        return " ".join(override.split())[:80].upper()
    return EVENT_LABELS.get(str(getattr(prepared, "mode", "instant")).lower(), "JOUST")


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSerif-Bold.ttf", "Georgia Bold.ttf",
                 "DejaVuSans-Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text(draw: ImageDraw.ImageDraw, label: object,
          box: tuple[int, int, int, int], *, size: int, minimum: int = 15) -> None:
    x0, y0, x1, y1 = box
    value = " ".join(str(label or "").split())
    if not value:
        return
    while True:
        font = _font(size)
        bbox = draw.textbbox((0, 0), value, font=font)
        if bbox[2] - bbox[0] <= x1 - x0 - 12 or size <= minimum:
            break
        size -= 2
    while len(value) > 1 and draw.textbbox((0, 0), value, font=font)[2] > x1-x0-12:
        value = value[:-2].rstrip() + "…"
    bbox = draw.textbbox((0, 0), value, font=font)
    x = x0 + (x1-x0-(bbox[2]-bbox[0]))/2 - bbox[0]
    y = y0 + (y1-y0-(bbox[3]-bbox[1]))/2 - bbox[1]
    draw.text((round(x), round(y)), value, fill=INK, font=font,
              stroke_width=1, stroke_fill=(239, 214, 158))


def _name(prepared, side: str) -> str:
    knight = getattr(prepared, "knight_a" if side == "red" else "knight_b", None)
    fighter = getattr(prepared, "fighter_a" if side == "red" else "fighter_b", None)
    return str(getattr(knight, "name", None) or getattr(fighter, "knight_name", None)
               or ("Red Knight" if side == "red" else "Blue Knight"))


def _crest(image: Image.Image, prepared) -> None:
    key = getattr(prepared, "intro_crest_key", None)
    if key not in CREST_KEYS:
        return  # Preserve the gold lion painted into the supplied template.
    path = ART_ROOT / "crests" / (key + ".png")
    if not path.is_file():
        return
    try:
        with Image.open(path) as source:
            crest = source.convert("RGBA")
            crest.thumbnail((CREST_RECT[2]-CREST_RECT[0],
                             CREST_RECT[3]-CREST_RECT[1]), Image.Resampling.LANCZOS)
            x = (CREST_RECT[0]+CREST_RECT[2]-crest.width)//2
            y = (CREST_RECT[1]+CREST_RECT[3]-crest.height)//2
            image.alpha_composite(crest, (x, y))
    except (OSError, ValueError):
        LOG.warning("Cannot load intro event crest: %s", path)


def render(prepared, *, banner_a: str | None = None, banner_b: str | None = None,
           npc_a: bool = False, npc_b: bool = False) -> bytes | None:
    """Overlay event, arena, names and optionally equipped earned standards.

    No artwork? Return None so the broadcaster uses its previous first-pass
    path. Player standards are resolved from the existing equipped title only.
    """
    key = str(getattr(prepared, "arena_key", ""))
    filename = ARENA_FILES.get(key)
    if filename is None:
        return None
    try:
        with Image.open(ART_ROOT / filename) as source:
            image = ImageOps.fit(source.convert("RGBA"), SIZE, Image.Resampling.LANCZOS)
    except (OSError, ValueError):
        return None
    fa, fb = getattr(prepared, "fighter_a", None), getattr(prepared, "fighter_b", None)
    guild_id = getattr(prepared, "guild_id", None)
    if banner_a is None and fa is not None:
        banner_a = entrant_banner_key(fa, guild_id)
    if banner_b is None and fb is not None:
        banner_b = entrant_banner_key(fb, guild_id)
    npc_a = npc_a or getattr(fa, "user_id", None) in NPC_BY_ID
    npc_b = npc_b or getattr(fb, "user_id", None) in NPC_BY_ID
    draw_side_banners(image, left_key=banner_a, right_key=banner_b,
                      left_npc=npc_a, right_npc=npc_b,
                      left_rect=RED_BANNER, right_rect=BLUE_BANNER)
    _crest(image, prepared)
    draw = ImageDraw.Draw(image)
    _text(draw, event_type(prepared), EVENT_RECT, size=48, minimum=26)
    _text(draw, ARENAS[key].name.upper(), ARENA_RECT, size=24, minimum=18)
    _text(draw, _name(prepared, "red"), RED_NAME, size=46, minimum=20)
    _text(draw, _name(prepared, "blue"), BLUE_NAME, size=46, minimum=20)
    stream = BytesIO()
    image.convert("RGB").save(stream, format="PNG", optimize=True)
    return stream.getvalue()
