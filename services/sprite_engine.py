"""v0.9.2a — layered sprite animation for an already-completed joust.

The combat engine and database are never invoked here. Replace PNGs under
assets/jousting without changing code. Missing assets use fallback sprites.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from services.arenas import ARENAS

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
ASSET_ROOT = ROOT / "assets" / "jousting"
RENDER_DIR = ROOT / "storage" / "renders"
SIZE = (960, 540)
BREED_COAT = {
    "courser": "Bay", "destrier": "Black", "rouncey": "Chestnut",
    "palfrey": "Grey", "charger": "White", "bay": "Bay",
    "black": "Black", "chestnut": "Chestnut", "grey": "Grey",
    "gray": "Grey", "white": "White",
}
COATS = ("Bay", "Black", "Chestnut", "Grey", "White")
HORSE_STATES = ("idle", "gallop", "rear", "refusal", "slip")
KNIGHT_STATES = ("idle", "gallop", "impact", "lower_lance", "unhorsed")


@dataclass(frozen=True)
class RenderBundle:
    gif_path: Path | None = None
    summary_path: Path | None = None
    gif_parts: tuple[Path, ...] = ()
    error: str | None = None


def _font(size):
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _fit_text(draw, text, width, size):
    text = str(text).replace("\n", " ")
    f = _font(size)
    while text and draw.textbbox((0, 0), text, font=f)[2] > width:
        text = text[:-2] + "…" if len(text) > 2 else ""
    return text


def _place(canvas, sprite, x, y):
    canvas.alpha_composite(sprite, (int(x), int(y)))


class AssetCatalog:
    """Load numbered PNGs, not preview sheets or duplicate stills."""

    def __init__(self, root: Path = ASSET_ROOT):
        self.root = Path(root)
        self._cache = {}
        self.missing = set()
        self.use_counts = {group: 0 for group in
                           ("arena", "horse", "knight", "crowd", "prop", "effect")}
        self.breed_coat = dict(BREED_COAT)
        self.player_coat = {}
        path = self.root / "visual_mapping.json"
        if path.is_file():
            try:
                mapping = json.loads(path.read_text(encoding="utf-8"))
                for breed, coat in mapping.get("breed_to_coat", {}).items():
                    if str(coat).title() in COATS:
                        self.breed_coat[str(breed).lower()] = str(coat).title()
                for player_id, coat in mapping.get("player_coats", {}).items():
                    if str(coat).title() in COATS:
                        self.player_coat[str(player_id)] = str(coat).title()
            except (ValueError, OSError, AttributeError):
                LOG.warning("Invalid visual mapping file; falling back to default colours")

    @staticmethod
    def _numbered(folder, stem, direction=""):
        if not folder.is_dir():
            return []
        suffix = "_" + direction if direction else ""
        pattern = re.compile(rf"{re.escape(stem + suffix)}_(\d{{2,3}})\.png$", re.I)
        found = []
        for path in folder.iterdir():
            match = pattern.fullmatch(path.name)
            if match and path.is_file():
                found.append((int(match.group(1)), path))
        return [path for _, path in sorted(found)]

    def _load(self, group, key, files, dims, mirror=False, trim=False):
        token = (group, tuple(key), dims, mirror, trim)
        if token not in self._cache:
            out = []
            for path in files:
                try:
                    with Image.open(path) as im:
                        image = im.convert("RGBA")
                        if trim and image.getbbox():
                            image = image.crop(image.getbbox())
                        image = image.resize(dims, Image.Resampling.LANCZOS)
                        if mirror:
                            image = ImageOps.mirror(image)
                        out.append(image)
                except (OSError, ValueError):
                    LOG.warning("Cannot read sprite: %s", path)
            if not out:
                self.missing.add(str((group, key)))
                image = Image.new("RGBA", dims, (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                draw.rounded_rectangle(
                    (2, 2, dims[0]-3, dims[1]-3), radius=12,
                    fill=(94, 55, 75, 140), outline="white", width=2,
                )
                draw.text((8, dims[1]//2), str(key[0])[:12], font=_font(13), fill="white")
                out = [image]
            else:
                self.use_counts[group] += len(out)
            self._cache[token] = tuple(out)
        return self._cache[token]

    def horse_coat(self, fighter):
        uid = str(getattr(fighter, "user_id", ""))
        key = str(getattr(fighter, "sprite_coat", "") or
                  getattr(fighter, "horse_breed", "rouncey")).lower()
        return self.player_coat.get(uid, self.breed_coat.get(key, "Chestnut"))

    def horse(self, coat, state, face_right=True):
        coat = self.breed_coat.get(str(coat).lower(), "Chestnut")
        state = state if state in HORSE_STATES else "idle"
        files = self._numbered(self.root / "horses" / coat / state.title(), state)
        if not files and state != "idle":
            return self.horse(coat, "idle", face_right)
        return self._load("horse", (coat, state), files, (285, 285), not face_right)

    def knight(self, colour, state, face_right=True):
        colour = "red" if str(colour).lower() == "red" else "blue"
        state = state if state in KNIGHT_STATES else "idle"
        side = "right" if face_right else "left"
        files = self._numbered(
            self.root / "knights" / (colour + "_knight") / state,
            f"{colour}_knight_{state}", side,
        )
        if not files and state != "idle":
            return self.knight(colour, "idle", face_right)
        # Knight art has TWO separately authored directions; never mirror it.
        return self._load("knight", (colour, state, side), files, (170, 272))

    def arena(self, key):
        path = self.root / "arenas" / (key + ".png")
        if path.is_file():
            try:
                with Image.open(path) as im:
                    self.use_counts["arena"] += 1
                    return ImageOps.fit(im.convert("RGBA"), SIZE, Image.Resampling.LANCZOS)
            except OSError:
                pass
        self.missing.add(f"arena:{key}")
        background = Image.new("RGBA", SIZE, (75, 96, 85, 255))
        ImageDraw.Draw(background).rectangle((0, 270, 960, 540), fill=(125, 99, 67))
        return background

    def crowd(self, mood):
        if mood not in {"idle_1", "idle_2", "boo", "cheer", "applause"}:
            mood = "idle_1"
        return self._load(
            "crowd", (mood,), [self.root / "crowd" / (mood + ".png")],
            (940, 98),
        )[0]

    def prop(self, name, dims=(80, 90), flip=False):
        return self._load(
            "prop", (name,), [self.root / "props" / (name + ".png")],
            dims, mirror=flip, trim=True,
        )[0]

    def effect(self, name, dims=(105, 105)):
        folder = self.root / "effects" / "animation_frames" / name
        files = self._numbered(folder, name)
        if not files:
            files = [self.root / "effects" / (name + ".png")]
        return self._load("effect", (name,), files, dims)


def _event(log, fa, fb):
    category = str(getattr(log, "category", "")).lower()
    result = str(getattr(log, "result", "")).lower()
    notes = " ".join(str(n).lower() for n in getattr(log, "notes", ()))
    side = "a" if int(log.points_a) > int(log.points_b) else (
        "b" if int(log.points_b) > int(log.points_a) else "none"
    )
    other = "b" if side == "a" else "a"
    if category in ("horse_refusal", "horse_slip") or "refus" in result:
        kind = "slip" if category == "horse_slip" else "refusal"
        return kind, ({other} if side != "none" else {"a", "b"}), side
    if category == "unhorsing" or "unhors" in result:
        return "unhorsed", ({other} if side != "none" else set()), side
    if category == "lance_break" or "lance break" in result:
        return "lance_break", set(), side
    if category in ("heavy_shield_hit", "saddle_stagger") or "solid hit" in result:
        return "heavy_hit", set(), side
    if "slip" in notes:
        affected = set()
        if fa.horse_name.lower() in notes: affected.add("a")
        if fb.horse_name.lower() in notes: affected.add("b")
        return "slip", affected, side
    if "miss" in result or category in ("clean_miss", "shield_scrape"):
        return "miss", set(), side
    return "clash", set(), side


def _hud(canvas, a, b, scores, number, phase, message=""):
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((12, 10, 948, 76), radius=13,
                        fill=(10, 18, 31, 220), outline=(227, 186, 107), width=2)
    d.text((28, 27), _fit_text(d, a, 260, 24), font=_font(24), fill=(253, 218, 218))
    name = _fit_text(d, b, 250, 24)
    n_width = d.textbbox((0, 0), name, font=_font(24))[2]
    d.text((930-n_width, 27), name, font=_font(24), fill=(208, 226, 255))
    d.text((414, 24), f"{scores[0]} : {scores[1]}", font=_font(32), fill="white")
    d.rounded_rectangle((310, 83, 650, 124), radius=10, fill=(12, 19, 27, 200))
    d.text((327, 92), f"PASS {number}  •  {phase}", font=_font(22), fill=(248, 210, 148))
    if message:
        d.rounded_rectangle((28, 473, 932, 530), radius=12, fill=(8, 14, 22, 218))
        d.text((42, 492), _fit_text(d, message, 860, 23),
               font=_font(23), fill="white")


def _rider(canvas, atlas, coat, face_right, state, mount_state, x, step,
           lowered, fallen, broken):
    horse = atlas.horse(coat, mount_state, face_right)
    rider = atlas.knight("red" if face_right else "blue", state, face_right)
    hy = 195
    _place(canvas, horse[step % len(horse)], x - 142, hy)
    knight = rider[step % len(rider)]
    if fallen:
        # Progress a falling rider towards the ground over successive frames.
        progress = min(1.0, max(0.0, step / 4))
        angle = 20 + round(60 * progress)
        knight = knight.rotate(-angle if face_right else angle, expand=True,
                               resample=Image.Resampling.BICUBIC)
        _place(canvas, knight, x-82 + (round(74 * progress) if face_right else -round(74 * progress)),
               hy-40 + round(130 * progress))
    else:
        _place(canvas, knight, x-85, hy-55)
        shield_name = "shield_red" if face_right else "shield_blue"
        variant = atlas.root / "props" / "variants" / (shield_name + ".png")
        if variant.is_file():
            shield = atlas._load("prop", (shield_name,), [variant],
                                 (50, 70), trim=True)[0]
        else:
            shield = atlas.prop("shield", (50, 70))
        _place(canvas, shield, x+(47 if face_right else -92), hy+60)
        lance = atlas.prop("broken_lance" if broken else "lance",
                           (196, 33), flip=not face_right)
        if not lowered:
            lance = lance.rotate(-51 if face_right else 51, expand=True)
        _place(canvas, lance, x+(38 if face_right else -229),
               hy+91 if lowered else hy-42)


def _scene(background, atlas, fa, fb, coat_a, coat_b, log, phase, step, pos,
           scores, kind, affected, winner, commentary=None):
    picture = background.copy()
    mood = ("idle_1" if phase in ("PREP", "APPROACH", "CHARGE", "GALLOP", "LANCE READY") else
            "applause" if kind == "unhorsed" else
            "boo" if kind in ("refusal", "slip") else
            "cheer" if kind in ("heavy_hit", "lance_break") else "idle_2")
    _place(picture, atlas.crowd(mood), 10, 139)
    xa, xb = round(95 + 260 * pos), round(865 - 260 * pos)
    mount_a = "idle" if phase == "PREP" else "gallop"
    mount_b = "idle" if phase == "PREP" else "gallop"
    if phase in ("IMPACT", "AFTERMATH", "COLLISION", "OUTCOME") and kind in ("refusal", "slip"):
        if "a" in affected: mount_a = kind
        if "b" in affected: mount_b = kind
    elif phase in ("AFTERMATH", "OUTCOME") and kind == "unhorsed":
        if "a" in affected: mount_a = "rear"
        if "b" in affected: mount_b = "rear"
    rider_a = ("idle" if phase == "PREP" else
               "gallop" if phase in ("APPROACH", "GALLOP") else
               "lower_lance" if phase in ("CHARGE", "LANCE READY") else "impact")
    rider_b = rider_a
    if phase in ("AFTERMATH", "OUTCOME") and kind == "unhorsed":
        if "a" in affected: rider_a = "unhorsed"
        if "b" in affected: rider_b = "unhorsed"
    _rider(picture, atlas, coat_a, True, rider_a, mount_a, xa, step,
           phase not in ("PREP", "APPROACH", "GALLOP"), rider_a == "unhorsed",
           phase in ("AFTERMATH", "OUTCOME") and kind == "lance_break" and winner == "a")
    _rider(picture, atlas, coat_b, False, rider_b, mount_b, xb, step,
           phase not in ("PREP", "APPROACH", "GALLOP"), rider_b == "unhorsed",
           phase in ("AFTERMATH", "OUTCOME") and kind == "lance_break" and winner == "b")
    if phase in ("APPROACH", "CHARGE", "GALLOP", "LANCE READY"):
        dust = atlas.effect("dust_1", (105, 72))
        _place(picture, dust[step % len(dust)], xa-70, 393)
        _place(picture, dust[(step+2) % len(dust)], xb+10, 393)
    elif phase in ("IMPACT", "COLLISION") and kind in ("heavy_hit", "lance_break", "unhorsed"):
        effects = ["impact_flash"]
        if kind in ("lance_break", "unhorsed"): effects.append("splinter")
        if kind == "unhorsed": effects.append("stars")
        for i, effect in enumerate(effects):
            sprites = atlas.effect(effect)
            _place(picture, sprites[step % len(sprites)], 435+22*i, 225+12*i)
    _place(picture, atlas.prop("barrier", (875, 115)), 43, 408)
    detail = (str(log.result) if phase in ("IMPACT", "AFTERMATH", "COLLISION", "OUTCOME")
              else "") if commentary is None else commentary
    _hud(picture, fa.knight_name, fb.knight_name, scores, log.pass_no, phase, detail)
    return picture


def render_match_media(result, fighter_a, fighter_b, arena_key,
                       out_stem=None, *, catalog=None, coat_a=None, coat_b=None,
                       max_kib=7500):
    """Generate a chronological sprite replay from logged passes, without combat calls."""
    atlas = catalog or AssetCatalog()
    background = atlas.arena(arena_key)
    if coat_a:
        coat_a = atlas.player_coat.get(str(getattr(fighter_a, "user_id", "")),
                  atlas.breed_coat.get(str(coat_a).lower(), "Chestnut"))
    else:
        coat_a = atlas.horse_coat(fighter_a)
    if coat_b:
        coat_b = atlas.player_coat.get(str(getattr(fighter_b, "user_id", "")),
                  atlas.breed_coat.get(str(coat_b).lower(), "Chestnut"))
    else:
        coat_b = atlas.horse_coat(fighter_b)
    frames, durations, seen = [], [], set()
    start = type("Intro", (), {"pass_no": 1, "result": ""})()
    frames.append(_scene(background, atlas, fighter_a, fighter_b, coat_a, coat_b,
                         start, "APPROACH", 0, .15, (0, 0), "clash", set(), "none"))
    durations.append(700)
    scores = (0, 0)
    per_pass = 13
    for log in result.passes:
        if log.pass_no in seen:
            raise ValueError(f"Duplicate pass {log.pass_no} in saved combat result")
        seen.add(log.pass_no)
        kind, affected, winner = _event(log, fighter_a, fighter_b)
        old = scores
        scores = (scores[0] + int(log.points_a), scores[1] + int(log.points_b))
        for phase, positions in (
            ("APPROACH", (.14, .29, .43, .58)),
            ("CHARGE", (.69, .82, .94, 1.0)),
            ("IMPACT", (1.0, 1.0)),
            ("AFTERMATH", (1.0, 1.0, .92)),
        ):
            for step, pos in enumerate(positions):
                visible = scores if phase in ("IMPACT", "AFTERMATH") else old
                frames.append(_scene(background, atlas, fighter_a, fighter_b,
                                     coat_a, coat_b, log, phase, step, pos,
                                     visible, kind, affected, winner))
                durations.append(220 if phase == "IMPACT" else 150 if phase == "AFTERMATH" else 120)
    if scores != (result.score_a, result.score_b):
        raise ValueError("Pass totals do not match authoritative result")
    final = background.copy()
    _place(final, atlas.crowd("applause"), 10, 139)
    d = ImageDraw.Draw(final)
    d.rounded_rectangle((65, 103, 894, 448), radius=26,
                        fill=(12, 21, 34, 228), outline=(217, 177, 100), width=3)
    d.text((90, 130), "THE GRAND LISTS  •  FINAL", font=_font(33), fill=(243, 213, 141))
    d.text((90, 205), _fit_text(d, fighter_a.knight_name, 330, 27),
           font=_font(27), fill="white")
    d.text((555, 205), _fit_text(d, fighter_b.knight_name, 305, 27),
           font=_font(27), fill="white")
    d.text((365, 245), f"{scores[0]}  —  {scores[1]}", font=_font(45),
           fill=(243, 213, 141))
    d.text((95, 350), _fit_text(d, "Winner: " + str(result.winner), 735, 30),
           font=_font(30), fill="white")
    d.text((95, 402), f"{ARENAS[arena_key].name if arena_key in ARENAS else arena_key}",
           font=_font(21), fill=(220, 220, 212))
    frames.append(final)
    durations.append(1200)

    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", str(out_stem or "joust"))[:60]
    root = RENDER_DIR / (stem + "_" + uuid.uuid4().hex[:9])
    png, gif = root.with_suffix(".png"), root.with_suffix(".gif")
    final.convert("RGB").save(png, optimize=True)
    max_bytes = max(1, int(max_kib)) * 1024

    if len(seen) <= 2:
        quantised = [f.convert("RGB").quantize(colors=96, method=Image.Quantize.MEDIANCUT)
                     for f in frames]
        quantised[0].save(gif, save_all=True, append_images=quantised[1:],
                          duration=durations, loop=0, optimize=True, disposal=2)
        if gif.stat().st_size <= max_bytes:
            return RenderBundle(gif_path=gif, summary_path=png)
        gif.unlink(missing_ok=True)

    clips = []
    for i in range(len(result.passes)):
        start = 0 if i == 0 else 1 + i * per_pass
        end = 1 + (i+1) * per_pass
        part_frames = frames[start:end]
        part_times = durations[start:end]
        part = root.with_name(root.name + f"_pass_{i+1:02}.gif")
        for width, colours in ((720, 64), (560, 48), (440, 40)):
            target = (width, width*9//16)
            quantised = [image.convert("RGB").resize(target, Image.Resampling.LANCZOS)
                         .quantize(colors=colours, method=Image.Quantize.MEDIANCUT)
                         for image in part_frames]
            quantised[0].save(part, save_all=True, append_images=quantised[1:],
                              duration=part_times, loop=0, optimize=True, disposal=2)
            if part.stat().st_size <= max_bytes:
                break
        if part.stat().st_size > max_bytes:
            part.unlink(missing_ok=True)
            for old in clips:
                old.unlink(missing_ok=True)
            return RenderBundle(summary_path=png,
                                error="Animated pass is too large for Discord")
        clips.append(part)
    return RenderBundle(summary_path=png, gif_parts=tuple(clips))


def maybe_render_match_media(*args, **kwargs):
    try:
        return render_match_media(*args, **kwargs)
    except Exception as exc:
        LOG.exception("Sprite renderer failed")
        return RenderBundle(error=str(exc))
