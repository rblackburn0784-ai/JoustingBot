"""v2.9.3a cosmetic side banners for live jousts.

Player flags are displayed ONLY when an earned title is actually equipped.
Training-yard opponents have individually assigned, personality-themed heraldry.
Never modifies titles, unlocks, combat, rewards or player records.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw

from services.banner_art import banner_path
from services.competition import equipped_title_key
from services.training import OPPONENTS

LOG = logging.getLogger(__name__)

# Explicit NPC assignments: use the existing personalities, not unsupported
# generic "aggressive/cautious" guesses or earned player achievements.
NPC_BANNERS: dict[str, str] = {
    "osric": "steady_in_the_saddle",       # careful patient counter-rider
    "beren": "veteran_of_the_lists",       # gruff old fundamentals coach
    "elis": "gale_rider",                  # quick, showy and hard to catch
    "maud": "shield_splitter",             # devastating direct charger
    "tamsin": "honour_bound",              # resolute defensive seat
    "roland": "battle_hardened",           # aggressive veteran
    "ysabel": "silver_lance",              # precise long-lance rider
    "godric": "iron_will",                 # armoured endurance specialist
    "rowena": "bracket_breaker",           # clever relentless tactician
    "aldric": "saddlebreaker",             # impact and unhorsing specialist
    "seraphine": "royal_standard",         # disciplined royal champion
    "black_knight": "arena_conqueror",     # final legendary challenge
}
NPC_BY_ID = {npc.player_id: npc.key for npc in OPPONENTS}


def entrant_banner_key(fighter, guild_id: int | None) -> str | None:
    """Return a render-only banner; never grants title ownership.

    Negative player ids must match an actual training opponent in the roster.
    Unknown NPCs and users without an equipped earned title remain bannerless.
    """
    try:
        user_id = int(getattr(fighter, "user_id"))
    except (ValueError, TypeError, AttributeError):
        return None
    npc_key = NPC_BY_ID.get(user_id)
    if npc_key:
        return NPC_BANNERS.get(npc_key)
    if user_id <= 0 or guild_id is None:
        return None
    try:
        return equipped_title_key(guild_id, user_id)
    except (ValueError, TypeError, OSError, KeyError):
        LOG.warning("Cannot resolve cosmetic banner for player %s", user_id)
        return None


def _npc_placeholder(key: str) -> Image.Image:
    """A distinct neutral heraldic flag when optional NPC art isn't installed.

    This fallback is never displayed for an unadorned real player.
    """
    palette = {
        "steady_in_the_saddle": (44, 91, 130), "veteran_of_the_lists": (108, 73, 42),
        "gale_rider": (64, 133, 128), "shield_splitter": (134, 45, 39),
        "honour_bound": (65, 83, 128), "battle_hardened": (139, 67, 35),
        "silver_lance": (82, 106, 135), "iron_will": (77, 80, 96),
        "bracket_breaker": (102, 64, 130), "saddlebreaker": (130, 46, 62),
        "royal_standard": (34, 61, 119), "arena_conqueror": (45, 40, 69),
    }
    colour = palette.get(key, (50, 68, 100))
    image = Image.new("RGBA", (110, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    points = [(10, 5), (100, 5), (100, 217), (55, 188), (10, 217)]
    draw.polygon(points, fill=(*colour, 250))
    draw.line(points + [points[0]], fill=(220, 183, 101, 255), width=5)
    draw.polygon([(55, 62), (77, 108), (55, 155), (33, 108)],
                 fill=(226, 194, 125, 255))
    return image


def _load_banner(key: str, is_npc: bool) -> Image.Image | None:
    path = banner_path(key)
    if path is not None:
        try:
            with Image.open(path) as source:
                source.load()
                return source.convert("RGBA")
        except (ValueError, OSError):
            LOG.warning("Unable to load title flag %s", path)
    return _npc_placeholder(key) if is_npc else None


def draw_side_banners(canvas: Image.Image, *, left_key: str | None,
                      right_key: str | None,
                      left_npc: bool = False, right_npc: bool = False,
                      left_rect: tuple[int, int, int, int],
                      right_rect: tuple[int, int, int, int]) -> None:
    """Composite optional flags at the arena edges, not into the joust lane."""
    for key, is_npc, rect in (
        (left_key, left_npc, left_rect),
        (right_key, right_npc, right_rect),
    ):
        if key is None:
            continue
        art = _load_banner(key, is_npc)
        if art is None:
            continue
        x, y, width, height = rect
        art.thumbnail((width, height), Image.Resampling.LANCZOS)
        px = x + (width - art.width) // 2
        py = y + (height - art.height) // 2
        canvas.alpha_composite(art, (px, py))
