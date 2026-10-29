"""Arena and Injury Ward scene regression checks for v0.9.2d."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image

from cogs import menu
from services import ui_art
from services.arenas import ARENAS


class SceneAssets(unittest.TestCase):
    def test_scene_paths_are_whitelisted(self):
        self.assertIsNone(ui_art.screen_path("arena", arena="../../.env"))
        self.assertIsNone(ui_art.screen_path("arena", arena="not_an_arena"))
        self.assertIsNone(ui_art.screen_path("../injury_ward"))
        self.assertEqual(ui_art.screen_path("injury").name, "injury_ward.png")
        for arena in ARENAS:
            with self.subTest(arena=arena):
                self.assertEqual(ui_art.screen_path("arena", arena=arena).name,
                                 f"{arena}.png")

    def test_scene_render_and_missing_image_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "ui"
            root.mkdir()
            with patch.object(ui_art, "ROOT", root), patch.object(ui_art, "BASE", Path(tmp)):
                self.assertIsNone(ui_art.render("arena", arena="frozen_ground"))
                self.assertIsNone(ui_art.render("injury"))
                arena_dir = root / "arenas"
                arena_dir.mkdir()
                for name in ("royal_lists", "frozen_ground"):
                    Image.new("RGB", (960, 540), (70, 50, 20)).save(
                        arena_dir / f"{name}.png")
                Image.new("RGB", (960, 540), (30, 40, 60)).save(root / "injury_ward.png")
                for screen, name in (("arena", "royal_lists"), ("arena", "frozen_ground"),
                                     ("injury", None)):
                    with self.subTest(screen=screen, name=name):
                        pixels = ui_art.render(screen, arena=name or "royal_lists")
                        self.assertIsInstance(pixels, bytes)
                        with Image.open(io.BytesIO(pixels)) as image:
                            self.assertEqual(image.size, (1280, 720))
                            self.assertEqual(image.format, "JPEG")

    def test_historical_arena_directory_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = base / "assets" / "jousting" / "arenas"
            folder.mkdir(parents=True)
            filename = folder / "wind_swept.png"
            Image.new("RGB", (960, 540), (20, 40, 60)).save(filename)
            with patch.object(ui_art, "ROOT", base / "assets" / "ui"), patch.object(ui_art, "BASE", base):
                self.assertEqual(ui_art.screen_path("arena", arena="wind_swept"), filename)


class SceneMenus(unittest.IsolatedAsyncioTestCase):
    async def test_arena_selected_by_dropdown_rebuilds_defaults_and_image(self):
        page = menu.ArenaPage(22, "frozen_ground")
        self.assertEqual(page.art_kwargs(), {"screen": "arena", "arena": "frozen_ground"})
        dropdown = next(x for x in page.children if isinstance(x, menu.ArenaSelect))
        dropdown._values = ["muddy_field"]
        intr = SimpleNamespace(user=SimpleNamespace(id=22))
        with patch.object(menu, "navigate", new_callable=AsyncMock) as nav:
            await dropdown.callback(intr)
        new_page = nav.await_args.args[1]
        self.assertEqual(new_page.art_kwargs(), {"screen": "arena", "arena": "muddy_field"})
        self.assertEqual(new_page.make_embed().title, "🏟️ Muddy Field")
        opts = next(x for x in new_page.children if isinstance(x, menu.ArenaSelect)).options
        self.assertTrue(next(o for o in opts if o.value == "muddy_field").default)

    async def test_injury_menu_displays_ward_when_fully_recovered(self):
        with patch("services.injuries.active", return_value=[]):
            page = menu.InjuryPage(22, 1)
        self.assertEqual(page.art_kwargs(), {"screen": "injury"})
        self.assertTrue(any(getattr(item, "label", "") == "Refresh" for item in page.children))

    async def test_ward_treatment_selection_refreshes_image(self):
        with patch("services.injuries.active", return_value=[
            {"id": "one", "name": "Arm", "stat": "strength", "remaining_seconds": 20}
        ]):
            page = menu.InjuryPage(22, 1)
        item = next(c for c in page.children if isinstance(c, menu.TreatmentSelect))
        item._values = ["shady_doctor"]
        intr = SimpleNamespace(user=SimpleNamespace(id=22), guild_id=1)
        with patch.object(menu, "navigate", new_callable=AsyncMock) as nav:
            await item.callback(intr)
        self.assertEqual(nav.await_args.args[1].art_kwargs(), {"screen": "injury"})


if __name__ == "__main__":
    unittest.main()
