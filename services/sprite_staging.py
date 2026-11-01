"""v2.9.3: non-gameplay calibration for side-on joust broadcast sprites.

All positions are in 960x540 scene pixels. Local artists can override only
the documented numbers by editing assets/jousting/scene_layout.json.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops

LOG = logging.getLogger(__name__)
CANVAS = (960, 540)
DEFAULT_STANDS = (
    (35, 132, 250, 62),    # left viewing box, inside original railings
    (356, 132, 248, 62),   # middle box
    (675, 132, 250, 62),   # right box
)


@dataclass(frozen=True)
class SceneLayout:
    horse_top: int = 159                 # was 195; hooves now meet the arena surface
    knight_scale: float = 0.90           # was 1.00
    rider_foot_clearance: int = 69      # rider feet relative to full horse canvas bottom
    barrier_left: int = 43
    barrier_top: int = 301              # rail now lives in the middle depth plane
    barrier_width: int = 845
    barrier_height: int = 92
    lance_raised_degrees: float = 46.0
    lance_lowered_degrees: float = 0.0
    lance_hand_offset_x: int = 20        # local x offset from rider/horse centre
    lance_hand_fraction_y: float = 0.48 # fraction down knight PNG, near the grip
    shield_forward_offset_x: int = 8    # off-hand shield near rider's chest
    shield_offhand_lift: int = 35       # reduced lift; shield sits just below helmet
    collision_closure_px: int = 18     # each horse travels slightly further at contact
    crowd_stands: tuple[tuple[int, int, int, int], ...] = DEFAULT_STANDS
    left_banner_rect: tuple[int, int, int, int] = (30, 144, 69, 133)
    right_banner_rect: tuple[int, int, int, int] = (862, 144, 69, 133)

    def __post_init__(self):
        if not (105 <= self.horse_top <= 245):
            raise ValueError("horse_top outside safe stage range")
        if not (.70 <= self.knight_scale <= 1.10):
            raise ValueError("knight_scale outside safe sprite range")
        if not (30 <= self.rider_foot_clearance <= 115):
            raise ValueError("rider_foot_clearance outside safe range")
        if not (260 <= self.barrier_top <= 440):
            raise ValueError("barrier_top outside safe stage range")
        if not (20 <= self.lance_raised_degrees <= 75):
            raise ValueError("lance_raised_degrees outside safe range")
        if not (-25 <= self.lance_lowered_degrees <= 25):
            raise ValueError("lance_lowered_degrees outside safe range")
        if not (0 <= self.lance_hand_offset_x <= 80):
            raise ValueError("lance_hand_offset_x outside safe range")
        if not (.25 <= self.lance_hand_fraction_y <= .80):
            raise ValueError("lance_hand_fraction_y outside safe range")
        if not (0 <= self.shield_forward_offset_x <= 50):
            raise ValueError("shield_forward_offset_x outside safe range")
        if not (10 <= self.shield_offhand_lift <= 85):
            raise ValueError("shield_offhand_lift outside safe range")
        if not (0 <= self.collision_closure_px <= 45):
            raise ValueError("collision_closure_px outside safe stage range")
        if not (0 <= self.barrier_left < CANVAS[0] and
                400 <= self.barrier_width <= CANVAS[0] and
                30 <= self.barrier_height <= 180):
            raise ValueError("barrier dimensions outside safe range")
        if len(self.crowd_stands) != 3:
            raise ValueError("There must be exactly three crowd stands")
        for x, y, width, height in self.crowd_stands:
            if x < 0 or y < 0 or width < 30 or height < 20 or x + width > CANVAS[0] or y + height > CANVAS[1]:
                raise ValueError("Crowd stand out of image bounds")
        for x, y, width, height in (self.left_banner_rect, self.right_banner_rect):
            if x < 0 or y < 78 or width < 30 or height < 40 or x + width > CANVAS[0] or y + height > 460:
                raise ValueError("Side banner anchor out of image bounds")


@lru_cache(maxsize=16)
def _from_json(path: str, mtime_ns: int) -> SceneLayout:
    del mtime_ns
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("layout root must be an object")
        allowed = set(SceneLayout.__dataclass_fields__)
        overrides = {k: v for k, v in data.items() if k in allowed}
        for key in ("crowd_stands", "left_banner_rect", "right_banner_rect"):
            if key in overrides:
                if key == "crowd_stands":
                    overrides[key] = tuple(tuple(rect) for rect in overrides[key])
                else:
                    overrides[key] = tuple(overrides[key])
        # Require numerical values, not arbitrary strings/paths from config.
        for key, value in overrides.items():
            if key == "crowd_stands":
                if not all(len(rect) == 4 and all(type(n) is int for n in rect)
                           for rect in value):
                    raise ValueError("crowd_stands entries must be four integers")
            elif key in ("left_banner_rect", "right_banner_rect"):
                if len(value) != 4 or not all(type(n) is int for n in value):
                    raise ValueError(f"{key} must be four integers")
            elif type(value) not in (int, float):
                raise ValueError(f"{key} must be numeric")
        return SceneLayout(**overrides)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        LOG.warning("Invalid scene_layout.json (%s); using safe v2.9.3 defaults", exc)
        return SceneLayout()


def load_layout(asset_root: Path) -> SceneLayout:
    path = Path(asset_root) / "scene_layout.json"
    if not path.is_file():
        return SceneLayout()
    try:
        return _from_json(str(path), path.stat().st_mtime_ns)
    except OSError:
        return SceneLayout()


def fill_crowd_stands(canvas: Image.Image, crowd: Image.Image,
                      stands: tuple[tuple[int, int, int, int], ...],
                      mask_root: Path | None = None) -> None:
    """Fit three independent crowd sections into the three raised pavilions.

    Regions are hard-clipped to their boxes; optional local PNG alpha masks
    remove spectators at arches, pillars and grandstand borders.
    """
    image = crowd.convert("RGBA")
    width, height = image.size
    for index, (x, y, target_width, target_height) in enumerate(stands):
        left = round(index * width / 3)
        right = round((index + 1) * width / 3)
        portion = image.crop((left, 0, right, height)).resize(
            (target_width, target_height), Image.Resampling.LANCZOS)
        if mask_root is not None:
            filename = ("left", "centre", "right")[index] + ".png"
            mask_file = Path(mask_root) / filename
            if mask_file.is_file():
                try:
                    with Image.open(mask_file) as mask:
                        # Alpha channel takes priority for transparent PNGs.
                        active = (mask.getchannel("A") if "A" in mask.getbands()
                                  else mask.convert("L"))
                        active = active.resize(
                            (target_width, target_height), Image.Resampling.LANCZOS)
                        portion.putalpha(ImageChops.multiply(
                            portion.getchannel("A"), active))
                except (OSError, ValueError):
                    LOG.warning("Ignoring invalid crowd stand mask: %s", mask_file)
        canvas.alpha_composite(portion, (x, y))


def shield_position(*, rider_centre_x: int, lance_grip_y: int,
                    face_right: bool, shield_size: tuple[int, int],
                    layout: SceneLayout) -> tuple[int, int]:
    """Place the shield just outside the knight's off-hand, not on the mount.

    Offsets are mirrored for red/right-facing and blue/left-facing riders.
    This uses the REAL shield dimensions so custom local variants still align.
    """
    width, _height = shield_size
    forward = layout.shield_forward_offset_x
    left = (rider_centre_x + forward if face_right
            else rider_centre_x - forward - width)
    return round(left), round(lance_grip_y - layout.shield_offhand_lift)


def rider_centres(position: float, kind: str, layout: SceneLayout) -> tuple[int, int]:
    """Move the riders nearer at a genuine hit, without premature collisions.

    At PREP/GALLOP the trajectory is unchanged. From the final ready sequence
    onward it eases in up to collision_closure_px *per rider*.
    Misses/refusals/slips never receive this extra contact motion.
    """
    pos = max(0.0, min(1.0, float(position)))
    red = round(95 + 260 * pos)
    blue = round(865 - 260 * pos)
    if kind in ("miss", "refusal", "slip"):
        return red, blue
    fraction = max(0.0, min(1.0, (pos - .60) / .40))
    extra = round(layout.collision_closure_px * fraction)
    return red + extra, blue - extra


def lance_tip(*, hand: tuple[int, int], face_right: bool,
              length: int = 196) -> tuple[int, int]:
    """Projected forward tip of a horizontal lance at the collision stage.

    Matches the pivot percentages in attach_lance; used by alignment tests.
    """
    reach = round(length * .81)
    return (hand[0] + (reach if face_right else -reach), hand[1])


def attach_lance(canvas: Image.Image, lance: Image.Image, *,
                 hand: tuple[int, int], face_right: bool,
                 raised: bool, layout: SceneLayout) -> None:
    """Rotate a lance *around its grip* while keeping the grip in the hand.

    A transparent fixed-size rotation canvas avoids PIL expand=True changing
    the displayed grip point. Works for original sprite or fallback art.
    """
    source = lance.convert("RGBA")
    half = max(140, max(source.size) + 8)
    size = half * 2
    centre = size // 2
    # After atlas flip, hilt is at left end for red and right end for blue.
    grip_x = round(source.width * (.19 if face_right else .81))
    grip_y = round(source.height * .50)
    buffer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    buffer.alpha_composite(source, (centre - grip_x, centre - grip_y))
    angle = (layout.lance_raised_degrees if raised else layout.lance_lowered_degrees)
    angle = angle if face_right else -angle
    rotated = buffer.rotate(angle, resample=Image.Resampling.BICUBIC)
    bounds = rotated.getbbox()
    if bounds is None:
        return
    sprite = rotated.crop(bounds)
    x = round(hand[0] - centre + bounds[0])
    y = round(hand[1] - centre + bounds[1])
    canvas.alpha_composite(sprite, (x, y))
