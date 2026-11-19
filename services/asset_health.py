"""v2.9.4 on-disk art audit. Never mutates images, saves or player records.

A missing optional asset is reported as a warning, not a gameplay failure.
A present corrupt/nontransparent sprite is an error for a full-art deployment.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from services.arenas import ARENAS
from services.banner_art import BANNER_FILES

BASE = Path(__file__).resolve().parents[1]
HORSE_COATS = ("Bay", "Black", "Chestnut", "Grey", "White")
HORSE_STATES = ("Idle", "Gallop", "Rear", "Refusal", "Slip")
KNIGHT_STATES = ("idle", "gallop", "impact", "lower_lance", "unhorsed")
CROWD = ("idle_1", "idle_2", "cheer", "boo", "applause")
EFFECTS = ("dust_1", "dust_2", "splinter", "impact_flash", "stars")
UI = ("shop", "knight", "injury_ward", "tournament",
      "tournament_history", "trophy_cabinet") + tuple(
          "horse_" + coat.lower() for coat in HORSE_COATS
      )


def _specs() -> list[tuple[str, tuple[str, ...], bool, str]]:
    """Group, possible paths, needs transparency, preferred proportions."""
    specs = []
    def add(group, paths, alpha=False, ratio=""):
        specs.append((group, tuple(paths), alpha, ratio))

    for key in ARENAS:
        add("Live arena scenes", [f"assets/jousting/arenas/{key}.png"], ratio="landscape")
        add("Arena introductions", [f"assets/ui/intro_screens/{key}_intro.png"],
            ratio="landscape")
    for item in UI:
        add("Menu artwork", [f"assets/ui/{item}.png"], ratio="landscape")
    for side in ("red", "blue"):
        for direction in ("left", "right"):
            for state in KNIGHT_STATES:
                count = 4 if state == "idle" else 1
                for frame in range(1, count + 1):
                    name = f"{side}_knight_{state}_{direction}_{frame:02d}.png"
                    add("Knight animation", [
                        f"assets/jousting/knights/{side}_knight/{state}/{name}"
                    ], alpha=True)
    for coat in HORSE_COATS:
        for state in HORSE_STATES:
            add("Horse animation", [
                f"assets/jousting/horses/{coat}/{state}/{state.lower()}_01.png"
            ], alpha=True)
    for name in ("lance", "broken_lance", "shield", "barrier"):
        add("Arena props", [f"assets/jousting/props/{name}.png"], alpha=True)
    for name in CROWD:
        add("Crowd animation", [f"assets/jousting/crowd/{name}.png"], alpha=True)
    for name in EFFECTS:
        add("Impact effects", [
            f"assets/jousting/effects/animation_frames/{name}/{name}_01.png",
            f"assets/jousting/effects/{name}.png",
        ], alpha=True)
    for filename in BANNER_FILES.values():
        add("Earned title standards", [
            f"assets/title_banners/{filename}", f"title_banners/{filename}"
        ], alpha=True)
    for colour in ("blue", "red"):
        add("Final scorecards", [
            f"assets/broadcast/final_{colour}_win.png"
        ], ratio="landscape")
    return specs


def audit_assets(root: Path | None = None) -> dict:
    """Inspect installed PNGs, preferred source paths and transparency.

    Missing packs cannot be checked for actual visual alignment or art style.
    """
    root = Path(root) if root is not None else BASE
    errors: list[str] = []
    missing_samples: dict[str, list[str]] = defaultdict(list)
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"present": 0, "expected": 0})
    present, missing = 0, 0
    idle_sizes: dict[tuple[str, str], set[tuple[int, int]]] = defaultdict(set)
    specs = _specs()
    for group, locations, alpha, ratio in specs:
        stats[group]["expected"] += 1
        options = [root / loc for loc in locations]
        found = next((p for p in options if p.is_file() or p.is_symlink()), None)
        if found is None:
            missing += 1
            if len(missing_samples[group]) < 3:
                missing_samples[group].append(locations[0])
            continue
        present += 1
        stats[group]["present"] += 1
        rel = str(found.relative_to(root))
        if found.is_symlink():
            errors.append(rel + ": symlink assets are not accepted")
            continue
        try:
            if found.stat().st_size > 50_000_000:
                raise ValueError("image exceeds 50 MB")
            # Pillow requires verify() immediately after Image.open().
            # Metadata extraction/getchannel can consume the file pointer;
            # verifying afterwards raises RuntimeError on valid PNG files.
            with Image.open(found) as verification:
                verification.verify()
            with Image.open(found) as img:
                if img.format != "PNG":
                    raise ValueError("not PNG data")
                width, height = img.size
                if width <= 0 or height <= 0 or width > 8192 or height > 8192:
                    raise ValueError("unsafe dimensions")
                if ratio == "landscape" and not (1.6 <= width / height <= 1.9):
                    raise ValueError(f"unexpected aspect ratio {width}x{height}")
                if alpha:
                    if "A" not in img.getbands():
                        raise ValueError("sprite has no alpha channel")
                    extrema = img.getchannel("A").getextrema()
                    if extrema is None or extrema[0] == 255:
                        raise ValueError("sprite has no transparent pixels")
                if group == "Knight animation" and "/idle/" in rel:
                    components = found.stem.split("_")
                    # Name is red_knight_idle_left_01 etc.
                    pair = (components[0], components[-2])
                    idle_sizes[pair].add(img.size)
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
                RuntimeError, Image.DecompressionBombError) as exc:
            errors.append(f"{rel}: {exc}")
    for (colour, direction), sizes in idle_sizes.items():
        if len(sizes) > 1:
            errors.append(f"Knight {colour}/{direction} idle PNGs have inconsistent sizes: {sorted(sizes)}")

    # Do not silently mix legacy 05+ frames from another visual style.
    for colour in ("red", "blue"):
        folder = root / "assets" / "jousting" / "knights" / f"{colour}_knight" / "idle"
        for direction in ("left", "right"):
            extras = sorted(folder.glob(f"{colour}_knight_idle_{direction}_[0-9][0-9].png"))
            extras = [p for p in extras if int(p.stem[-2:]) > 4]
            if extras:
                errors.append(f"{colour}/{direction} idle has extra 05+ frames that could mix art styles")
    warnings = [
        f"{group}: {stat['present']}/{stat['expected']} found; missing examples: "
        + ", ".join(missing_samples[group])
        for group, stat in stats.items()
        if stat["present"] != stat["expected"]
    ]
    return {
        "expected": len(specs), "present": present, "missing": missing,
        "errors": errors, "warnings": warnings,
        "groups": {key: dict(val) for key, val in stats.items()},
        "ready_for_full_graphics": missing == 0 and not errors,
    }
