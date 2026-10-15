"""Generated 1200x675 introduction and final scoreboard PNGs.

No external art is required. Optional arena backgrounds can be placed in
assets/broadcast/intro.png, assets/broadcast/final.png, or
assets/broadcast/arena_<arena_key>.png. All paths stay within the bot folder.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from services.broadcast import statistics

W, H = 1200, 675
GOLD = (232, 194, 111)
WHITE = (239, 238, 224)
SUBTLE = (179, 184, 185)
ROOT = Path(__file__).resolve().parent.parent / "assets" / "broadcast"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(size: int, bold: bool = False):
    path = FONT_BOLD if bold else FONT_REGULAR
    for candidate in (path, "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def fit_text(draw, value: object, width: int, size=44, min_size=16, bold=False):
    value = str(value).replace("\n", " ").strip()
    while size > min_size:
        f = font(size, bold)
        if draw.textbbox((0, 0), value, font=f)[2] <= width:
            return value, f
        size -= 2
    f = font(min_size, bold)
    while value and draw.textbbox((0, 0), value + "…", font=f)[2] > width:
        value = value[:-1]
    return value + ("…" if value else ""), f


def background(scene: str, arena_key: str):
    allowed = (
        ROOT / f"arena_{arena_key}.png",
        ROOT / f"{scene}.png",
    )
    for candidate in allowed:
        if candidate.is_file():
            try:
                im = Image.open(candidate).convert("RGB")
                base = ImageOps.fit(im, (W, H), method=Image.Resampling.LANCZOS)
                base = base.convert("RGBA")
                base.alpha_composite(Image.new("RGBA", (W, H), (8, 15, 23, 180)))
                return base.convert("RGB")
            except (OSError, ValueError):
                continue
    base = Image.new("RGB", (W, H))
    pixels = base.load()
    for y in range(H):
        factor = y / H
        r = int(13 + factor * 20)
        g = int(28 + factor * 14)
        b = int(38 + factor * 14)
        for x in range(W):
            pixels[x, y] = (r, g, b)
    return base


def text_center(draw, y: int, message: str, size: int, color=WHITE, bold=False):
    text, chosen_font = fit_text(draw, message, W - 140, size, 18, bold)
    width = draw.textbbox((0, 0), text, font=chosen_font)[2]
    draw.text(((W - width) // 2, y), text, font=chosen_font, fill=color)


def crest(draw, center_x: int, top: int, color: tuple):
    x, y = center_x, top
    draw.polygon([
        (x-45, y), (x+45, y), (x+42, y+72),
        (x, y+108), (x-42, y+72),
    ], fill=color, outline=GOLD, width=4)
    draw.line([(x-22, y+40), (x+22, y+60)], fill=WHITE, width=7)
    draw.line([(x+24, y+35), (x-19, y+68)], fill=WHITE, width=7)


def backdrop(draw, kind: str):
    draw.rectangle((25, 20, W-25, H-20), outline=GOLD, width=3)
    draw.line((65, 112, W-65, 112), fill=GOLD, width=2)
    draw.line((65, H-74, W-65, H-74), fill=GOLD, width=2)
    text_center(draw, 44, kind, 42, GOLD, True)


def _save(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def _name(draw, value: str, x: int, y: int, width: int):
    text, chosen = fit_text(draw, value, width, 43, 20, True)
    draw.text((x, y), text, font=chosen, fill=WHITE)


def intro(prepared) -> bytes:
    arena_key = getattr(prepared, "arena_key", "royal_lists")
    image = background("intro", arena_key)
    draw = ImageDraw.Draw(image)
    backdrop(draw, "THE GRAND LISTS · MATCHDAY")
    arena = arena_key.replace("_", " ").upper()
    text_center(draw, 127, arena, 24, SUBTLE, True)
    crest(draw, 290, 215, (91, 37, 48))
    crest(draw, 910, 215, (33, 69, 109))
    _name(draw, prepared.knight_a.name, 95, 356, 430)
    _name(draw, prepared.knight_b.name, 720, 356, 430)
    draw.text((552, 285), "VS", font=font(67, True), fill=GOLD)
    _, f = fit_text(draw, prepared.horse_a.name, 400, 23)
    draw.text((95, 416), "Mount: " + prepared.horse_a.name[:38], font=f, fill=SUBTLE)
    _, f = fit_text(draw, prepared.horse_b.name, 400, 23)
    draw.text((720, 416), "Mount: " + prepared.horse_b.name[:38], font=f, fill=SUBTLE)
    for x, plan in ((95, prepared.tactics_a), (720, prepared.tactics_b)):
        desc = f"{plan.style.title()} / {plan.target.title()}"
        value, f = fit_text(draw, desc, 430, 23)
        draw.text((x, 470), value, font=f, fill=GOLD)
    text_center(draw, 554, "LANCES DOWN · THE MARSHALS ARE READY", 24, WHITE, True)
    return _save(image)


def final(result, prepared) -> bytes:
    arena_key = getattr(prepared, "arena_key", "royal_lists")
    image = background("final", arena_key)
    draw = ImageDraw.Draw(image)
    backdrop(draw, "THE GRAND LISTS · FINAL SCORE")
    winner = "HONOURS EVEN" if result.winner == "Draw" else f"VICTOR: {result.winner}"
    text_center(draw, 136, winner, 38, GOLD, True)
    draw.rounded_rectangle((75, 220, 543, 505), radius=16, fill=(34, 49, 67), outline=GOLD, width=2)
    draw.rounded_rectangle((657, 220, 1125, 505), radius=16, fill=(34, 49, 67), outline=GOLD, width=2)
    _name(draw, result.fighter_a, 101, 251, 410)
    _name(draw, result.fighter_b, 680, 251, 420)
    draw.text((227, 319), str(result.score_a), font=font(105, True), fill=WHITE)
    draw.text((805, 319), str(result.score_b), font=font(105, True), fill=WHITE)
    draw.text((579, 345), "–", font=font(47, True), fill=GOLD)
    stats = statistics(result)
    labels = (("Lance Breaks", "lance_breaks"), ("Unhorsings", "unhorsings"), ("Heavy Hits", "heavy_hits"))
    for x, side in ((99, "a"), (678, "b")):
        line = "  ·  ".join(f"{name}: {stats[side][key]}" for name, key in labels)
        message, f = fit_text(draw, line, 427, 17, 12)
        draw.text((x, 469), message, font=f, fill=SUBTLE)
    text_center(draw, 537, f"{arena_key.replace('_', ' ').title()}  ·  Seed {result.seed}", 23, SUBTLE)
    return _save(image)
