"""v2.9.2f: title/banner mapping, safe persistence and illustrated menu regression."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image

from cogs import menu
from services import banner_art, competition, ui_art
from services.arenas import ARENAS


class BannerMappingTests(unittest.TestCase):
    def test_all_thirty_titles_have_exactly_one_safe_banner_image(self):
        self.assertEqual(len(banner_art.BANNER_FILES), 30)
        self.assertEqual(set(banner_art.BANNER_FILES), set(competition.TITLE_RULES))
        self.assertEqual(len(set(banner_art.BANNER_FILES.values())), 30)
        self.assertEqual(banner_art.BANNER_FILES["marshal_favourite"],
                         "27_marshals_favourite.png")

    def test_path_validation_and_original_zip_layout_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            filename = banner_art.BANNER_FILES["mud_king"]
            art = root / "title_banners"
            art.mkdir()
            expected = art / filename
            Image.new("RGBA", (254, 539), (220, 40, 50, 190)).save(expected)
            with patch.object(banner_art, "BASE", root), \
                 patch.object(banner_art, "BANNER_ROOT", root / "assets" / "title_banners"):
                self.assertEqual(banner_art.banner_path("mud_king"), expected)
                self.assertIsNone(banner_art.banner_path("../../.env"))
                self.assertIsNone(banner_art.banner_path("not_a_title"))

    def test_default_and_selected_title_gallery_render_without_any_png(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(banner_art, "BASE", Path(tmp)), \
             patch.object(banner_art, "BANNER_ROOT", Path(tmp)):
            default = ui_art.render("title_collection", banner_key=None,
                                    preview_key=None, preview_locked=True)
            self.assertIsInstance(default, bytes)
            with Image.open(io.BytesIO(default)) as image:
                self.assertEqual(image.size, (1280, 720))
                self.assertEqual(image.format, "JPEG")

    def test_chosen_banner_changes_far_arena_not_its_gameplay_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            banner_file = root / "03_mud_king.png"
            Image.new("RGBA", (140, 320), (244, 42, 41, 255)).save(banner_file)
            background = Image.new("RGB", (1280, 720), (40, 90, 110))
            with patch.object(banner_art, "BANNER_ROOT", root):
                original = background.copy()
                chosen = banner_art.arena_image(background, arena="royal_lists",
                                                banner_key="mud_king")
                empty = banner_art.arena_image(background, arena="royal_lists",
                                               banner_key=None)
            self.assertEqual(original.getpixel((640, 180)), (40, 90, 110))
            self.assertNotEqual(chosen.getpixel((635, 180)),
                                empty.getpixel((635, 180)))
            self.assertEqual(chosen.getpixel((90, 620)), (40, 90, 110))
            self.assertEqual(set(ARENAS), set(banner_art.ARENA_ANCHORS))


class BannerPersistenceTests(unittest.TestCase):
    def test_equipped_key_reuses_existing_guild_scoped_title_save(self):
        db = {"guilds": {"44": {"22": "mud_king"}, "55": {"22": "first_lance"}}}
        earned = {
            "mud_king": {"earned": True}, "first_lance": {"earned": True}
        }
        with patch.object(competition, "load_json", return_value=db), \
             patch.object(competition, "title_progress", return_value=earned):
            self.assertEqual(competition.equipped_title_key(44, 22), "mud_king")
            self.assertEqual(competition.equipped_title_key(55, 22), "first_lance")
            self.assertEqual(competition.equipped_title_key(44, 33), None)

    def test_unlock_rules_remain_mandatory_and_save_unchanged(self):
        stored = {"guilds": {"44": {}}}
        progress = {"mud_king": {"earned": True}, "frozen_terror": {"earned": False}}
        with patch.object(competition, "load_json", return_value=stored), \
             patch.object(competition, "save_json") as save, \
             patch.object(competition, "title_progress", return_value=progress):
            competition.set_title(44, 22, "mud_king")
            self.assertEqual(stored["guilds"]["44"]["22"], "mud_king")
            self.assertEqual(competition.equipped_title_key(44, 22), "mud_king")
            with self.assertRaises(ValueError):
                competition.set_title(44, 22, "frozen_terror")
            self.assertEqual(stored["guilds"]["44"]["22"], "mud_king")
            competition.set_title(44, 22, None)
            self.assertIsNone(competition.equipped_title_key(44, 22))
            self.assertEqual(save.call_count, 2)


class BannerMenuTests(unittest.IsolatedAsyncioTestCase):
    async def test_title_collection_preview_locked_and_equipped(self):
        progress = {key: {"earned": key == "mud_king"} for key in competition.TITLE_RULES}
        with patch.object(menu, "title_progress", return_value=progress), \
             patch.object(menu, "equipped_title_key", return_value="mud_king"):
            screen = menu.TitlePage(22, 44, selected="frozen_terror")
            props = screen.art_kwargs()
            self.assertEqual(props["banner_key"], "mud_king")
            self.assertIsNone(props["preview_key"])
            self.assertTrue(props["preview_locked"])
            screen.selected = "mud_king"
            props = screen.art_kwargs()
            self.assertFalse(props["preview_locked"])
            self.assertEqual(props["preview_key"], "mud_king")

    async def test_arena_and_duel_use_player_banner_in_same_guild(self):
        with patch.object(menu, "equipped_title_key", return_value="mud_king") as key:
            arena = menu.ArenaPage(22, selected="frozen_ground", guild_id=44)
            self.assertEqual(arena.art_kwargs()["banner_key"], "mud_king")
            self.assertEqual(arena.art_kwargs()["arena"], "frozen_ground")
            duel = menu.DuelPage(22, arena_key="muddy_field", guild_id=44)
            self.assertEqual(duel.art_kwargs()["banner_key"], "mud_king")
            key.assert_called_with(44, 22)
        no_guild = menu.ArenaPage(22)
        self.assertIsNone(no_guild.art_kwargs()["banner_key"])

    async def test_title_equip_refreshes_image_and_uses_existing_set_title(self):
        page = menu.TitlePage(22, 44, selected="mud_king")
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=22),
            guild_id=44,
            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )
        with patch.object(menu, "set_title") as saved, \
             patch.object(menu, "navigate", new_callable=AsyncMock) as nav:
            await page.equip(interaction)
        interaction.response.defer.assert_awaited_once()
        saved.assert_called_once_with(44, 22, "mud_king")
        self.assertEqual(nav.await_args.args[1].selected, "mud_king")
        self.assertIn("matching banner", nav.await_args.args[2])

    async def test_unequip_restores_default_and_refreshes(self):
        page = menu.TitlePage(22, 44)
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=22),
            guild_id=44,
            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        )
        with patch.object(menu, "set_title") as saved, \
             patch.object(menu, "navigate", new_callable=AsyncMock) as nav:
            await page.unequip(interaction)
        saved.assert_called_once_with(44, 22, None)
        self.assertIn("Default banner", nav.await_args.args[2])


if __name__ == "__main__":
    unittest.main()
