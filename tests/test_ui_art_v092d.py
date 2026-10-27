"""v0.9.2d visual menu tests: real PNG routing, fallback and no fake purchases."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
from PIL import Image

from cogs import menu
from services import ui_art


class ArtworkRouting(unittest.TestCase):
    def test_five_breeds_resolve_to_matching_horse_image(self):
        expected = {
            "courser": "bay", "destrier": "black", "rouncey": "chestnut",
            "palfrey": "grey", "charger": "white",
        }
        for breed, coat in expected.items():
            with self.subTest(breed=breed):
                self.assertEqual(ui_art.selected_coat(breed), coat)
                self.assertEqual(ui_art.screen_path("horse", coat).name,
                                 f"horse_{coat}.png")

    def test_missing_image_does_not_block_discord_controls(self):
        with tempfile.TemporaryDirectory() as root, patch.object(ui_art, "ROOT", Path(root)):
            self.assertIsNone(ui_art.render("shop"))
            self.assertIsNone(ui_art.render("knight"))
            self.assertIsNone(ui_art.render("horse", coat="bay"))

    def test_all_seven_user_png_backgrounds_are_usable(self):
        with tempfile.TemporaryDirectory() as root, patch.object(ui_art, "ROOT", Path(root)):
            root = Path(root)
            files = ["shop.png", "knight.png"] + [
                f"horse_{coat}.png" for coat in sorted(ui_art.COATS)
            ]
            for i, filename in enumerate(files):
                colour = (i * 20, 40, 60)
                Image.new("RGB", (1648, 928), colour).save(root / filename)
            for filename in files:
                screen = "horse" if filename.startswith("horse_") else filename[:-4]
                coat = filename[6:-4] if screen == "horse" else "chestnut"
                pixels = ui_art.render(
                    screen, coat=coat, equipped={"lance": "Ash Lance", "barding": "Leather"},
                    focus="barding",
                )
                self.assertIsInstance(pixels, bytes)
                with Image.open(io.BytesIO(pixels)) as im:
                    self.assertEqual(im.size, (1280, 720))
                    self.assertEqual(im.format, "JPEG")

    def test_live_override_mapping_applied(self):
        with tempfile.TemporaryDirectory() as root:
            mapping = Path(root) / "visual_mapping.json"
            mapping.write_text('{"breed_to_coat":{"courser":"white"},'
                               '"player_coats":{"101":"Bay"}}', encoding="utf-8")
            with patch.object(ui_art, "MAPPING", mapping):
                self.assertEqual(ui_art.selected_coat("courser"), "white")
                self.assertEqual(ui_art.selected_coat("courser", 101), "bay")
                self.assertEqual(ui_art.selected_coat("unknown"), "chestnut")

    def test_explicit_horse_coat_wins_and_survives_serializer(self):
        from cogs.horse import Horse
        horse = Horse(
            horse_id="h-101-test", owner_id=101, name="Starlight",
            breed="courser",
            stats={"speed": 5, "stamina": 5, "power": 5,
                   "obedience": 5, "courage": 4},
            visual_coat="white",
        )
        raw = horse.to_dict()
        restored = Horse.from_dict(raw)
        self.assertEqual(restored.visual_coat, "white")
        self.assertEqual(ui_art.horse_coat(restored.to_dict(), 101), "white")
        self.assertEqual(restored.breed, "courser")

    def test_screen_file_paths_are_whitelisted(self):
        self.assertIsNone(ui_art.screen_path("../secrets"))
        self.assertEqual(ui_art.screen_path("horse", "../../foo").name,
                         "horse_chestnut.png")


class MenuFlows(unittest.IsolatedAsyncioTestCase):
    async def test_shop_menu_visible_to_all_players_without_admin_access(self):
        view = menu.MainMenuView(22, allow_admin=False)
        labels = [getattr(c, "label", None) for c in view.children]
        self.assertIn("Shop", labels)
        self.assertIn("Equipment", labels)
        self.assertNotIn("Admin", labels)
        admin = menu.MainMenuView(22, allow_admin=True)
        self.assertIn("Admin", [getattr(c, "label", None) for c in admin.children])

    async def test_navigate_reuses_private_message_and_keeps_image_in_sync(self):
        intr = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock(), edit_message=AsyncMock()),
            edit_original_response=AsyncMock(),
        )
        screen = menu.ShopHome(22, 1)
        with patch.object(ui_art, "render", return_value=b"fake jpeg"), \
             patch("services.progression.wallet", return_value=80):
            await menu.navigate(intr, screen)
        intr.response.defer.assert_awaited_once()
        intr.response.edit_message.assert_not_awaited()
        kw = intr.edit_original_response.await_args.kwargs
        self.assertEqual(kw["embed"].image.url, "attachment://joust_ui.jpg")
        self.assertEqual(len(kw["attachments"]), 1)
        self.assertIs(kw["view"], screen)

    async def test_navigate_without_image_falls_back_to_fully_usable_embed(self):
        intr = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock(), edit_message=AsyncMock()),
            edit_original_response=AsyncMock(),
        )
        screen = menu.ShopHome(22, 1)
        with patch.object(ui_art, "render", return_value=None), \
             patch("services.progression.wallet", return_value=80):
            await menu.navigate(intr, screen)
        kwargs = intr.edit_original_response.await_args.kwargs
        self.assertEqual(kwargs["attachments"], [])
        self.assertIn("Shop", kwargs["embed"].title)
        self.assertTrue(screen.children)

    async def test_shop_purchase_uses_existing_buy_and_never_auto_equips(self):
        intr = SimpleNamespace(
            user=SimpleNamespace(id=22),
            guild_id=1,
            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
            edit_original_response=AsyncMock(),
        )
        page = menu.ShopPicker(22, "lance", 1, "lance_oakbreaker")
        with patch("services.progression.buy", return_value=19) as buying, \
             patch("services.progression.set_loadout") as equipping, \
             patch.object(ui_art, "render", return_value=None), \
             patch("services.progression.wallet", return_value=19), \
             patch("services.progression.unlock_info",
                   return_value={"owned":True,"eligible":True,"cost":110,
                                 "requirement":"wins","progress":5,"required":5}):
            await page.purchase(intr)
        buying.assert_called_once_with(1, 22, "lance_oakbreaker")
        equipping.assert_not_called()
        # The first acknowledgement happens before any balance/journal IO.
        self.assertGreaterEqual(intr.response.defer.await_count, 1)
        self.assertIn("Purchased", intr.edit_original_response.await_args.kwargs["content"])

    async def test_horse_picker_changes_breed_with_selected_horse(self):
        h1 = {"horse_id":"h1", "owner_id":22, "name":"Pearl", "breed":"charger",
              "stats":{}, "equipped_barding_key":"barding_none"}
        h2 = {"horse_id":"h2", "owner_id":22, "name":"Shadow", "breed":"destrier",
              "stats":{}, "equipped_barding_key":"barding_none"}
        with patch.object(menu, "load_horses",
                          return_value={"horses":{"h1":h1,"h2":h2}}), \
             patch.object(menu, "load_knights", return_value={"knights":{}}):
            stable = menu.StableView(22, guild_id=1)
            stable.selected_id = "h2"
            self.assertEqual(stable.art_kwargs()["coat"], "black")
            stable.selected_id = "h1"
            self.assertEqual(stable.art_kwargs()["coat"], "white")


if __name__ == "__main__":
    unittest.main()
