"""Install seven optional v0.9.2d UI backgrounds from a folder or ZIP.

Accepts both the release ZIP's original filenames and the names used by the
GitHub renderer. Only the seven validated PNGs are written; data and secrets
are not touched. ZIP entries are read in memory, never extracted to disk.
"""
from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "ui"
ALIASES = {
    "shop": ("shop.png", "equipment_setup.png"),
    "knight": ("knight.png", "knight_setup.png"),
    "horse_white": ("horse_white.png",),
    "horse_bay": ("horse_bay.png",),
    "horse_black": ("horse_black.png",),
    "horse_grey": ("horse_grey.png",),
    "horse_chestnut": ("horse_chestnut.png",),
}


def source_images(source: Path) -> dict[str, bytes]:
    """Resolve each expected image from any supported folder/ZIP layout."""
    if source.is_dir():
        sources = sorted((p for p in source.rglob("*") if p.is_file()), key=str)
        entries = [(p.name.lower(), p.read_bytes, str(p)) for p in sources
                   if p.suffix.lower() == ".png"]
    elif source.is_file() and source.suffix.lower() == ".zip":
        try:
            with ZipFile(source) as archive:
                # Read only whitelisted image names; do not extract arbitrary paths.
                entries = [(Path(name).name.lower(), archive.read(name), name)
                           for name in archive.namelist()
                           if not name.endswith("/") and
                           Path(name).name.lower() in {alias for group in ALIASES.values() for alias in group}]
        except (BadZipFile, OSError, RuntimeError) as exc:
            raise ValueError(f"Cannot read ZIP: {exc}") from exc
    else:
        raise ValueError("--source must point to a directory or a .zip archive")

    selected: dict[str, bytes] = {}
    for name, aliases in ALIASES.items():
        for alias in aliases:  # Prefer canonical name if both names are present.
            matches = [(value, label) for filename, value, label in entries if filename == alias]
            if matches:
                if len(matches) != 1:
                    raise ValueError(f"Ambiguous source: found multiple copies of {alias}")
                value, label = matches[0]
                data = value() if callable(value) else value
                _validate_png(label, data)
                selected[name] = data
                break
        else:
            raise ValueError(f"Missing {name}: expected {' or '.join(aliases)}")
    return selected


def _validate_png(label: str, data: bytes) -> None:
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG":
                raise ValueError(f"{label} is not a PNG")
            width, height = image.size
            if width < 960 or height < 540 or abs(width / height - 16 / 9) > 0.1:
                raise ValueError(f"{label} must be landscape, approximately 16:9, at least 960x540")
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"{label} is an invalid PNG: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description="Install seven Knight/Horse/Shop PNG screens")
    cli.add_argument("--source", type=Path, required=True,
                     help="Art folder or Jousting_Bot_Setup_PNG_Pack_v2.zip / release ZIP")
    cli.add_argument("--check", action="store_true", help="Validate without installing")
    opts = cli.parse_args(argv)
    try:
        images = source_images(opts.source.expanduser().resolve())
    except ValueError as exc:
        cli.error(str(exc))
    if opts.check:
        print("OK — all seven screens are valid. No files were changed.")
        return 0
    DEST.mkdir(parents=True, exist_ok=True)
    for name, content in images.items():
        destination = DEST / f"{name}.png"
        if not destination.is_file() or destination.read_bytes() != content:
            destination.write_bytes(content)
        print(f"Installed: {destination.relative_to(ROOT)}")
    print("Done. Restart your Discord bot and open /menu → Shop, Knight or Horse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
