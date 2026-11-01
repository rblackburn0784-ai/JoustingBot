"""v2.9.3b — final match score over the two user-supplied victory cards.

Blue is at left and red at right in BOTH templates. In match results,
fighter_a is the red knight and fighter_b is the blue knight. This module
never simulates, mutates, or writes game state.
"""
from __future__ import annotations

from io import BytesIO
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from services.broadcast import statistics

LOG = logging.getLogger(__name__)
ART_ROOT = Path(__file__).resolve().parents[1] / "assets" / "broadcast"
TEMPLATES = {
    "blue": "final_blue_win.png",
    "red": "final_red_win.png",
}
# Native original scorecards are 1672 x 941. Keep the design, no cropping.
SIZE = (1672, 941)
INK = (49, 26, 11)

# Panels arranged as (left blue competitor, right red competitor).
NAME_RECTS = {
    "blue": (273, 470, 496, 538),
    "red": (1163, 470, 1383, 538),
}
# Column value centres are in the empty cells on either side of the labels.
STAT_X = {"blue": 614, "red": 1052}
STAT_Y = {
    "passes": 425,
    "lance_breaks": 484,
    "unhorsings": 543,
    "injuries": 602,
    "impact_score": 658,
}
BOTTOM_RECTS = {
    "arena": (315, 783, 603, 840),
    "format": (702, 783, 990, 840),
    "seed": (1107, 783, 1390, 840),
}


def template_colour(result) -> str | None:
    """Only select victory artwork for the actual recorded winner."""
    if result.winner == result.fighter_a:
        return "red"
    if result.winner == result.fighter_b:
        return "blue"
    return None  # draws and malformed results use legacy neutral card


def _font(size: int) -> ImageFont.ImageFont:
    for name in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "DejaVuSerif-Bold.ttf",
        "Georgia Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "arialbd.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _in_panel(draw: ImageDraw.ImageDraw, value: object,
              rect: tuple[int, int, int, int], *,
              size: int = 36, min_size: int = 14) -> None:
    """Centre and shrink text so even long names never hit the shield edges."""
    x0, y0, x1, y1 = rect
    text = str(value).replace("\\n", " ").strip() or "—"
    f = _font(size)
    while size > min_size and draw.textbbox((0, 0), text, font=f)[2] > x1-x0-8:
        size -= 2
        f = _font(size)
    while len(text) > 1 and draw.textbbox((0, 0), text, font=f)[2] > x1-x0-8:
        text = text[:-2].rstrip() + "…"
    bbox = draw.textbbox((0, 0), text, font=f)
    width, height = bbox[2]-bbox[0], bbox[3]-bbox[1]
    x = x0 + (x1-x0-width)/2 - bbox[0]
    y = y0 + (y1-y0-height)/2 - bbox[1]
    draw.text((round(x), round(y)), text, font=f, fill=INK)


def _value(draw: ImageDraw.ImageDraw, number: object, side: str, row: str) -> None:
    x, y = STAT_X[side], STAT_Y[row]
    _in_panel(draw, number, (x-56, y-22, x+56, y+28), size=33, min_size=20)


def _injuries(prepared) -> tuple[int, int]:
    """Count only injuries created by THIS bout, not old active injuries.

    send_match records them before initiating either live or fallback broadcast.
    Unavailable legacy scorecards default to zero without reading the DB again.
    """
    counts = getattr(prepared, "scorecard_injuries", None)
    if not isinstance(counts, dict):
        return (0, 0)
    return (max(0, int(counts.get("a", 0))),
            max(0, int(counts.get("b", 0))))


def _format(prepared) -> str:
    return {
        "challenge": "RANKED JOUST",
        "training": "TRAINING",
        "instant": "FRIENDLY",
        "tournament": "TOURNAMENT",
    }.get(str(getattr(prepared, "mode", "")).lower(), "JOUST")


def render(result, prepared) -> bytes | None:
    """Render a victory template, or return None for draw / missing asset.

    Left is BLUE=fighter_b and right is RED=fighter_a, irrespective of winner.
    The 'IMPACT SCORE' artwork row displays final awarded match points;
    raw impact force is not a tracked per-player total in MatchResult.
    """
    colour = template_colour(result)
    if colour is None:
        return None
    path = ART_ROOT / TEMPLATES[colour]
    try:
        with Image.open(path) as source:
            source.load()
            image = source.convert("RGB")
        if image.size != SIZE:
            # Accept artist revisions only if same native design proportions.
            if abs(image.width/image.height - SIZE[0]/SIZE[1]) > .025:
                LOG.warning("Scorecard template is not 16:9: %s", path)
                return None
            image = image.resize(SIZE, Image.Resampling.LANCZOS)
    except (OSError, ValueError) as exc:
        LOG.info("No usable %s scorecard at %s (%s)", colour, path, exc)
        return None

    draw = ImageDraw.Draw(image)
    stats = statistics(result)
    injured_a, injured_b = _injuries(prepared)
    # The blue knight is fighter B, on the LEFT of these supplied PNGs.
    sides = (
        ("blue", result.fighter_b, "b", injured_b),
        ("red", result.fighter_a, "a", injured_a),
    )
    for side, name, stat_key, injury_count in sides:
        _in_panel(draw, name, NAME_RECTS[side], size=34, min_size=16)
        values = {
            "passes": len(result.passes),
            "lance_breaks": stats[stat_key]["lance_breaks"],
            "unhorsings": stats[stat_key]["unhorsings"],
            "injuries": injury_count,
            "impact_score": stats[stat_key]["points"],
        }
        for row, value in values.items():
            _value(draw, value, side, row)

    arena = getattr(prepared, "arena_key", None) or getattr(result, "arena_name", "royal_lists")
    arena = str(arena).replace("_", " ").title()
    _in_panel(draw, arena, BOTTOM_RECTS["arena"], size=31, min_size=17)
    _in_panel(draw, _format(prepared), BOTTOM_RECTS["format"], size=31, min_size=16)
    _in_panel(draw, result.seed, BOTTOM_RECTS["seed"], size=32, min_size=16)
    out = BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()
