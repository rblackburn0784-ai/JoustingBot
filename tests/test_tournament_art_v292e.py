"""v2.9.2e: Tournament Hall, History and Trophy Cabinet artwork/interaction tests."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
from PIL import Image

from cogs import tournament
from services import ui_art


class TournamentArtwork(unittest.TestCase):
    def test_names_and_missing_art_are_safe(self):
        expected = {
            "tournament": "tournament.png",
            "tournament_history": "tournament_history.png",
            "trophy_cabinet": "trophy_cabinet.png",
        }
        with tempfile.TemporaryDirectory() as tmp, patch.object(ui_art, "ROOT", Path(tmp)):
            for screen, filename in expected.items():
                with self.subTest(screen=screen):
                    self.assertEqual(ui_art.screen_path(screen).name, filename)
                    self.assertIsNone(ui_art.render(screen))
            self.assertIsNone(ui_art.screen_path("../../.env"))

    def test_images_attach_in_existing_renderer(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(ui_art, "ROOT", Path(tmp)):
            for name in ("tournament", "tournament_history", "trophy_cabinet"):
                Image.new("RGB", (1672, 941), (15, 35, 66)).save(Path(tmp) / f"{name}.png")
                art = ui_art.render(name)
                self.assertIsInstance(art, bytes)
                with Image.open(io.BytesIO(art)) as rendered:
                    self.assertEqual(rendered.size, (1280, 720))
                    self.assertEqual(rendered.format, "JPEG")


class TournamentScreens(unittest.IsolatedAsyncioTestCase):
    async def test_hub_and_history_have_distinct_art_and_return_controls(self):
        with patch.object(tournament.engine, "current", return_value=None), \
             patch.object(tournament.engine, "recent", return_value=[]):
            hub = tournament.TournamentHub(42, 123, admin=True)
            history = tournament.TournamentHistory(42, 123)
            self.assertEqual(hub.art_kwargs(), {"screen": "tournament"})
            self.assertEqual(history.art_kwargs(), {"screen": "tournament_history"})
            self.assertIn("Tournament", hub.make_embed().title)
            self.assertIn("History", history.make_embed().title)
            labels = [getattr(child, "label", "") for child in history.children]
            self.assertIn("Refresh History", labels)
            self.assertIn("Tournament Menu", labels)
            intr = SimpleNamespace(user=SimpleNamespace(id=42), guild_id=123)
            with patch.object(tournament, "navigate", new_callable=AsyncMock) as nav:
                await hub.history(intr)
            self.assertIsInstance(nav.await_args.args[1], tournament.TournamentHistory)

    async def test_cabinet_tabs_keep_art_and_original_features(self):
        for tab in ("achievements", "titles", "records"):
            cabinet = tournament.TournamentCabinet(42, 123, tab=tab)
            self.assertEqual(cabinet.art_kwargs(), {"screen": "trophy_cabinet"})
            labels = [getattr(child, "label", "") for child in cabinet.children]
            for name in ("Achievements", "Tournament Titles", "Career Medals", "Equip Title"):
                self.assertIn(name, labels)

    async def test_public_button_opens_private_illustrated_history(self):
        intr = SimpleNamespace(user=SimpleNamespace(id=42), guild_id=123)
        panel = tournament.TournamentPanel()
        with patch.object(tournament, "send_private_screen", new_callable=AsyncMock) as send:
            await panel.history.callback(intr)
        self.assertIsInstance(send.await_args.args[1], tournament.TournamentHistory)

    async def test_private_entry_acknowledges_before_art_generation(self):
        intr = SimpleNamespace(
            user=SimpleNamespace(id=42),
            guild_id=123,
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )
        view = tournament.TournamentHistory(42, 123)
        with patch.object(ui_art, "render", return_value=b"jpeg data"), \
             patch.object(tournament, "history_embed", return_value=discord.Embed(title="History")):
            await tournament.send_private_screen(intr, view)
        intr.response.defer.assert_awaited_once_with(thinking=True, ephemeral=True)
        sent = intr.followup.send.await_args.kwargs
        self.assertTrue(sent["ephemeral"])
        self.assertEqual(sent["embed"].image.url, "attachment://joust_ui.jpg")
        self.assertEqual(sent["file"].filename, "joust_ui.jpg")

    async def test_missing_image_has_working_private_controls(self):
        intr = SimpleNamespace(
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )
        view = tournament.TournamentHistory(42, None)
        with patch.object(ui_art, "render", return_value=None):
            await tournament.send_private_screen(intr, view)
        sent = intr.followup.send.await_args.kwargs
        self.assertNotIn("file", sent)
        self.assertIs(sent["view"], view)
        self.assertTrue(view.children)


if __name__ == "__main__":
    unittest.main()
