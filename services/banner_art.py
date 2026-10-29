"""v2.9.2f — title banner sprites, selection previews and distant arena standards.

One authoritative equipped title is already persisted per guild/user in
services.competition; artwork is a cosmetic view of that stored title.
No new mutable title/banner save is required.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

BASE = Path(__file__).resolve().parents[1]
BANNER_ROOT = BASE / "assets" / "title_banners"
BANNER_FILES = {
    "the_unhorsed": "01_the_unhorsed.png",
    "shield_splitter": "02_shield_splitter.png",
    "mud_king": "03_mud_king.png",
    "frozen_terror": "04_frozen_terror.png",
    "crowd_favourite": "05_crowd_favourite.png",
    "the_reluctant_rider": "06_the_reluctant_rider.png",
    "first_lance": "07_first_lance.png",
    "iron_will": "08_iron_will.png",
    "grand_champion": "09_grand_champion.png",
    "veteran_of_the_lists": "10_veteran_of_the_lists.png",
    "saddlebreaker": "11_saddlebreaker.png",
    "timberstorm": "12_timberstorm.png",
    "royal_standard": "13_royal_standard.png",
    "gale_rider": "14_gale_rider.png",
    "festival_hero": "15_festival_hero.png",
    "battle_hardened": "16_battle_hardened.png",
    "honour_bound": "17_honour_bound.png",
    "steady_in_the_saddle": "18_steady_in_the_saddle.png",
    "lists_initiate": "19_lists_initiate.png",
    "bracket_breaker": "20_bracket_breaker.png",
    "the_finalist": "21_the_finalist.png",
    "silver_lance": "22_silver_lance.png",
    "cup_bearer": "23_cup_bearer.png",
    "king_of_the_lists": "24_king_of_the_lists.png",
    "elite_eight": "25_elite_eight.png",
    "grand_melee_champion": "26_grand_melee_champion.png",
    "marshal_favourite": "27_marshals_favourite.png",
    "tourney_veteran": "28_tourney_veteran.png",
    "lance_of_the_lists": "29_lance_of_the_lists.png",
    "arena_conqueror": "30_arena_conqueror.png",
}

# 1280x720 arena-preview coordinates: small, raised and in the far stands.
# Separate anchors allow different backgrounds to be calibrated independently.
ARENA_ANCHORS = {
    "royal_lists": (595, 100, 82, 168),
    "muddy_field": (595, 105, 78, 160),
    "frozen_ground": (595, 100, 78, 160),
    "wind_swept": (595, 102, 78, 158),
    "festival_arena": (600, 95, 85, 175),
    "war_torn": (596, 105, 76, 153),
}


def banner_path(key: str | None) -> Path | None:
    """Only keys in the explicit whitelist can resolve to an image."""
    filename = BANNER_FILES.get(key) if isinstance(key, str) else None
    if not filename:
        return None
    candidates = (BANNER_ROOT / filename, BASE / "title_banners" / filename)
    return next((p for p in candidates if p.is_file()), None)


def _font(size: int) -> ImageFont.ImageFont:
    for font_name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _default_banner() -> Image.Image:
    """An unearned-free neutral royal blue standard (never a title reward)."""
    canvas = Image.new("RGBA", (220, 450), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.line((16, 15, 204, 15), fill=(226, 190, 115, 255), width=9)
    draw.ellipse((8, 5, 25, 24), fill=(230, 188, 99, 255))
    draw.ellipse((195, 5, 212, 24), fill=(230, 188, 99, 255))
    cloth = [(33, 22), (187, 22), (187, 404), (110, 355), (33, 404)]
    draw.polygon(cloth, fill=(20, 45, 87, 245))
    draw.line(cloth + [cloth[0]], fill=(223, 174, 84, 255), width=7, joint="curve")
    draw.polygon([(110, 145), (145, 190), (110, 235), (75, 190)],
                 fill=(213, 173, 102, 255))
    draw.polygon([(110, 162), (130, 190), (110, 218), (90, 190)],
                 fill=(20, 45, 87, 255))
    return canvas


def _banner_image(key: str | None) -> Image.Image:
    path = banner_path(key)
    if path:
        try:
            with Image.open(path) as original:
                original.load()
                return original.convert("RGBA")
        except (OSError, ValueError, SyntaxError):
            pass
    return _default_banner()


def _stamp(canvas: Image.Image, banner_key: str | None,
           rect: tuple[int, int, int, int]) -> None:
    """Composite proportionally, respecting each transparent PNG's own alpha."""
    x, y, width, height = rect
    if min(width, height) <= 0:
        return
    banner = _banner_image(banner_key)
    banner.thumbnail((width, height), Image.Resampling.LANCZOS)
    px = x + (width - banner.width) // 2
    py = y + (height - banner.height) // 2
    canvas.alpha_composite(banner, (px, py))


def _text(draw: ImageDraw.ImageDraw, pos: tuple[int, int],
          value: str, size: int = 24, color=(245, 229, 184)) -> None:
    draw.text(pos, value, font=_font(size), fill=color)


def collection_image(*, banner_key: str | None,
                     preview_key: str | None = None,
                     preview_locked: bool = False) -> Image.Image:
    """Large equipped standard and optional candidate preview in a 16:9 menu."""
    width, height = 1280, 720
    canvas = Image.new("RGBA", (width, height), (15, 25, 47, 255))
    draw = ImageDraw.Draw(canvas)
    for y in range(height):
        mix = y / height
        draw.line((0, y, width, y),
                  fill=(int(17 + 13 * mix), int(31 + 8 * mix),
                        int(56 - 8 * mix), 255))
    draw.rounded_rectangle((32, 26, 1248, 693), radius=20,
                           outline=(181, 137, 74), width=4)
    draw.line((66, 107, 1213, 107), fill=(164, 130, 73), width=2)
    _text(draw, (75, 47), "THE ROYAL STANDARD GALLERY", 38)
    _text(draw, (180, 126), "EQUIPPED BANNER", 27)
    _text(draw, (794, 126), "SELECTED TITLE", 27)
    draw.rounded_rectangle((89, 171, 600, 643), radius=13,
                           fill=(12, 21, 40), outline=(112, 87, 49), width=3)
    draw.rounded_rectangle((669, 171, 1190, 643), radius=13,
                           fill=(12, 21, 40), outline=(112, 87, 49), width=3)
    _stamp(canvas, banner_key, (185, 184, 295, 398))
    if not banner_key:
        _text(draw, (211, 600), "No title equipped - plain standard", 19)
    else:
        _text(draw, (210, 600), "Your equipped title standard", 19)
    if preview_locked:
        _stamp(canvas, None, (817, 216, 221, 342))
        draw.rounded_rectangle((823, 456, 1029, 513), radius=9,
                               fill=(12, 20, 35), outline=(222, 175, 89), width=2)
        _text(draw, (867, 469), "LOCKED", 24)
    else:
        _stamp(canvas, preview_key, (781, 184, 295, 398))
    _text(draw, (755, 600), "Browse titles below, then Equip Selected", 18)
    return canvas.convert("RGB")


def arena_image(background: Image.Image, *, arena: str,
                banner_key: str | None) -> Image.Image:
    """Place the selected standard at the far end of a menu arena preview."""
    picture = background.convert("RGBA")
    rect = ARENA_ANCHORS.get(arena)
    if rect:
        _stamp(picture, banner_key, rect)
    return picture.convert("RGB")
