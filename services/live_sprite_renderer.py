"""v0.9.2b — build ONE self-contained animated sprite clip per jousting pass.

No combat, database, Discord or rewards calls belong here. All data is read
from the authoritative pass journal. Each clip has five consecutive moments:
PREP -> GALLOP -> LANCE READY -> COLLISION -> OUTCOME.
The GIF plays only once and holds on its outcome until the next pass arrives.
"""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from services.sprite_engine import (
    AssetCatalog, RENDER_DIR, SIZE, _event, _scene,
)


@dataclass(frozen=True)
class Moment:
    phase: str
    step: int
    position: float
    duration_ms: int


@dataclass(frozen=True)
class PassClip:
    path: Path
    duration_ms: int
    pass_no: int
    score_before: tuple[int, int]
    score_after: tuple[int, int]
    stages: tuple[str, ...]
    is_animated: bool = True


# Distinct moments; multiple images within movement phases animate gallop
# cycles and lance-lowering. Outcome is held longer for the spectators.
PHASES = ("PREP", "GALLOP", "LANCE READY", "COLLISION", "OUTCOME")


def validate_result(result):
    """Validate *all* saved passes before allowing any live replay to start."""
    seen, score_a, score_b = set(), 0, 0
    passes = getattr(result, "passes", ()) or ()
    if not passes:
        raise ValueError("Cannot stream a match without recorded passes")
    for log in passes:
        number = int(log.pass_no)
        if number in seen or number <= 0:
            raise ValueError("Duplicate/invalid pass in saved result")
        seen.add(number)
        points_a, points_b = int(log.points_a), int(log.points_b)
        if points_a < 0 or points_b < 0:
            raise ValueError("Negative pass score")
        score_a += points_a
        score_b += points_b
    if (score_a, score_b) != (int(result.score_a), int(result.score_b)):
        raise ValueError("Pass totals do not match the recorded result")
    return True


def timeline(kind="clash"):
    """A fixed-time choreography; the combat result never changes the RNG."""
    slow = kind in ("refusal", "slip")
    meet = .67 if slow else 1.0
    path = [
        Moment("PREP", i, .11, 280 if i == 0 else 150)
        for i in range(4)
    ]
    path += [
        Moment("GALLOP", i, .12 + i * .067, 115)
        for i in range(7)
    ]
    path += [
        Moment("LANCE READY", i, .60 + (meet-.60) * i / 6, 130)
        for i in range(7)
    ]
    path += [
        Moment("COLLISION", i, meet, 180 if i != 2 else 260)
        for i in range(3)
    ]
    path += [
        Moment("OUTCOME", i, max(.55, meet-.04*i), 160 if i != 4 else 650)
        for i in range(5)
    ]
    return tuple(path)


def moment_commentary(moment, log, fa, fb, score_before, score_after, *,
                      show_ticker=True, event_kind="clash"):
    if not show_ticker:
        return ""
    if moment.phase == "PREP":
        return "Marshals signal the riders to prepare."
    if moment.phase == "GALLOP":
        return f"{fa.knight_name} and {fb.knight_name} surge towards the centre."
    if moment.phase == "LANCE READY":
        a = getattr(log, "tactics_a", {}) or {}
        b = getattr(log, "tactics_b", {}) or {}
        a_target = str(a.get("target", "shield")).replace("_", " ").title()
        b_target = str(b.get("target", "shield")).replace("_", " ").title()
        return f"Lances lower — {fa.knight_name}: {a_target}; {fb.knight_name}: {b_target}."
    if moment.phase == "COLLISION":
        if event_kind == "refusal":
            return "A mount refuses the charge! The marshals intervene."
        if event_kind == "slip":
            return "A horse loses its footing in the charge!"
        if event_kind == "miss":
            return "The lances whistle through empty air!"
        return "The riders meet at the rail!"
    return (f"{log.result}  •  +{int(log.points_a)}/+{int(log.points_b)} points"
            f"  •  Score {score_after[0]}–{score_after[1]}")


def _coat(atlas, fighter, horse=None):
    uid = str(getattr(fighter, "user_id", ""))
    breed = str(getattr(horse, "sprite_coat", None) or
                getattr(horse, "breed", None) or
                getattr(fighter, "horse_breed", "rouncey")).lower()
    return atlas.player_coat.get(uid, atlas.breed_coat.get(breed, "Chestnut"))


def _save_gif(images, moments, destination, max_kib):
    if len(images) != len(moments) or not images:
        raise ValueError("GIF frames and timings are inconsistent")
    max_bytes = max(1, int(max_kib)) * 1024
    durations = [item.duration_ms for item in moments]
    for width, palette in ((960, 96), (720, 80), (560, 64), (440, 48)):
        target = (width, round(width * SIZE[1] / SIZE[0]))
        quantised = [
            frame.convert("RGB").resize(target, Image.Resampling.LANCZOS)
                 .quantize(colors=palette, method=Image.Quantize.MEDIANCUT)
            for frame in images
        ]
        # Do not specify GIF loop=0 (that repeats forever). Discord must
        # finish on the outcome frame until the next pass takes its place.
        quantised[0].save(
            destination, save_all=True, append_images=quantised[1:],
            duration=durations, optimize=True, disposal=2,
        )
        if destination.stat().st_size <= max_bytes:
            return
    destination.unlink(missing_ok=True)
    raise ValueError("Pass animation exceeds configured upload size")


def render_live_pass(result, fighter_a, fighter_b, arena_key, log,
                     score_before, score_after, *, atlas=None, horse_a=None,
                     horse_b=None, max_kib=7500, show_ticker=True,
                     reduced_motion=False, out_stem=None):
    """Generate one pass file, never the entire match in a single recap dump."""
    atlas = atlas or AssetCatalog()
    coat_a = _coat(atlas, fighter_a, horse_a)
    coat_b = _coat(atlas, fighter_b, horse_b)
    background = atlas.arena(arena_key)
    kind, affected, winner = _event(log, fighter_a, fighter_b)
    script = timeline(kind)
    frames = []
    for item in script if not reduced_motion else script[-1:]:
        pre_outcome = item.phase != "OUTCOME"
        visible_score = score_before if pre_outcome else score_after
        ticker = moment_commentary(
            item, log, fighter_a, fighter_b, score_before, score_after,
            show_ticker=show_ticker, event_kind=kind,
        )
        frames.append(_scene(
            background, atlas, fighter_a, fighter_b, coat_a, coat_b,
            log, item.phase, item.step, item.position, visible_score,
            kind, affected, winner, commentary=ticker,
        ))
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", str(out_stem or "joust"))[:42]
    key = uuid.uuid4().hex[:10]
    if reduced_motion:
        path = RENDER_DIR / f"{stem}_pass_{int(log.pass_no):02d}_{key}.png"
        frames[0].convert("RGB").save(path, optimize=True)
        duration = 1400
    else:
        path = RENDER_DIR / f"{stem}_pass_{int(log.pass_no):02d}_{key}.gif"
        _save_gif(frames, script, path, max_kib)
        duration = sum(item.duration_ms for item in script)
    return PassClip(path, duration, int(log.pass_no), tuple(score_before),
                    tuple(score_after), PHASES, not reduced_motion)
