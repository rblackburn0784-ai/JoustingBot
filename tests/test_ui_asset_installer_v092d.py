"""Verify supplied v0.9.2d PNG packs can be installed without renaming art."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

from tools import install_ui_art_v092d as installer


def sample_png() -> bytes:
    payload = io.BytesIO()
    Image.new("RGB", (960, 540), (20, 50, 80)).save(payload, format="PNG")
    return payload.getvalue()


class InstallerTests(unittest.TestCase):
    def test_original_nested_setup_zip_and_check_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "setup.zip"
            with ZipFile(archive, "w") as writer:
                for key, names in installer.ALIASES.items():
                    writer.writestr(f"screens/{names[-1]}", sample_png())
            images = installer.source_images(archive)
            self.assertEqual(set(images), set(installer.ALIASES))
            with patch.object(installer, "DEST", root / "not_written"):
                self.assertEqual(installer.main(["--source", str(archive), "--check"]), 0)
            self.assertFalse((root / "not_written").exists())

    def test_release_zip_layout_and_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "release.zip"
            with ZipFile(archive, "w") as writer:
                for names in installer.ALIASES.values():
                    writer.writestr(f"Jousting Bot/assets/ui/{names[-1]}", sample_png())
            target = root / "assets" / "ui"
            with patch.object(installer, "DEST", target), patch.object(installer, "ROOT", root):
                self.assertEqual(installer.main(["--source", str(archive)]), 0)
            self.assertEqual({p.name for p in target.glob("*.png")},
                             {name + ".png" for name in installer.ALIASES})

    def test_rejects_missing_and_invalid_art(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for key, names in installer.ALIASES.items():
                (root / names[-1]).write_bytes(b"not a png" if key == "shop" else sample_png())
            with self.assertRaisesRegex(ValueError, "invalid PNG"):
                installer.source_images(root)
            (root / "equipment_setup.png").unlink()
            with self.assertRaisesRegex(ValueError, "Missing shop"):
                installer.source_images(root)


if __name__ == "__main__":
    unittest.main()
