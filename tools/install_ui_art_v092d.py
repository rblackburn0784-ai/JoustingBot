"""Install the user's seven full-screen PNGs into v0.9.2d Discord UI.

Keep original files; copy validated PNGs only. Never overwrite saved
characters, gear, sprites, .env, or existing data files.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "ui"
NAMES = (
    "shop", "knight",
    "horse_white", "horse_bay", "horse_black", "horse_grey", "horse_chestnut",
)


def main() -> int:
    cli = argparse.ArgumentParser(description="Install seven Knight/Horse/Shop PNG screens")
    cli.add_argument("--source", type=Path, required=True, help="Folder containing the seven renamed PNGs")
    cli.add_argument("--check", action="store_true", help="Validate but do not copy")
    opts = cli.parse_args()

    source = opts.source.resolve()
    if not source.is_dir():
        cli.error("The --source folder does not exist.")
    listing = {p.name.lower(): p for p in source.iterdir() if p.is_file()}
    missing = [name for name in NAMES if name + ".png" not in listing]
    if missing:
        cli.error(
            "Missing source images: " + ", ".join(name + ".png" for name in missing)
            + "\nDownload the seven pictures and rename them as documented in assets/ui/README.md."
        )
    images = {}
    for name in NAMES:
        file = listing[name + ".png"]
        with Image.open(file) as image:
            image.verify()
        with Image.open(file) as image:
            if image.format != "PNG":
                cli.error(f"{file.name} is not a PNG.")
            width, height = image.size
            if width < 960 or height < 540 or abs((width/height) - 16/9) > .1:
                cli.error(f"{file.name} must be a landscape, approximately 16:9, >=960x540 image.")
        images[name] = file

    if opts.check:
        print("OK — all seven screens are valid. No files were changed.")
        return 0
    DEST.mkdir(parents=True, exist_ok=True)
    for name, path in images.items():
        dest = DEST / (name + ".png")
        if path.resolve() != dest.resolve():
            shutil.copy2(path, dest)
        print(f"Installed: {dest.relative_to(ROOT)}")
    print("Done. Restart your Discord bot and open /menu → Shop, Knight or Horse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
