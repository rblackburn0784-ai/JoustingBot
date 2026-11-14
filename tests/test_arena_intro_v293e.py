"""v2.9.3e: arena artwork overlays and one-message introduction regression."""
from __future__ import annotations

from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
from PIL import Image

from services import arena_intro, live_broadcast as live, live_sprite_renderer as renderer


def prepared():
    return SimpleNamespace(
        arena_key="royal_lists", mode="challenge", guild_id=None,
        knight_a=SimpleNamespace(name="Scarlet Knight"),
        knight_b=SimpleNamespace(name="Azure Knight"),
        fighter_a=SimpleNamespace(user_id=1, knight_name="Scarlet Knight"),
        fighter_b=SimpleNamespace(user_id=2, knight_name="Azure Knight"),
        horse_a=SimpleNamespace(breed="rouncey"),
        horse_b=SimpleNamespace(breed="palfrey"),
    )


def result():
    log = SimpleNamespace(
        pass_no=1, category="lance_break", result="Lance break",
        points_a=1, points_b=0, margin=2, notes=[], tactics_a={}, tactics_b={},
    )
    return SimpleNamespace(
        fighter_a="Scarlet Knight", fighter_b="Azure Knight",
        winner="Scarlet Knight", arena_name="Royal Lists", arena_key="royal_lists",
        score_a=1, score_b=0, seed=123, passes=[log],
    )


class IntroArtTests(unittest.TestCase):
    def test_arena_files_cover_all_six_known_arenas(self):
        self.assertEqual(len(arena_intro.ARENA_FILES), 6)
        self.assertEqual(arena_intro.ARENA_FILES["war_torn"], "war_torn_intro.png")

    def test_missing_or_broken_art_is_safe(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(arena_intro, "ART_ROOT", Path(folder)):
            self.assertIsNone(arena_intro.render(prepared()))
            (Path(folder) / "royal_lists_intro.png").write_text("not an image")
            self.assertIsNone(arena_intro.render(prepared()))

    def test_draws_names_event_arena_without_changing_other_parts(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(arena_intro, "ART_ROOT", Path(folder)):
            Image.new("RGB", arena_intro.SIZE, (235, 216, 173)).save(Path(folder) / "royal_lists_intro.png")
            with patch.object(arena_intro, "draw_side_banners") as banners:
                rendered = arena_intro.render(prepared())
            self.assertIsNotNone(rendered)
            with Image.open(BytesIO(rendered)) as picture:
                self.assertEqual(picture.size, arena_intro.SIZE)
                self.assertEqual(picture.getpixel((20, 400)), (235, 216, 173))
                self.assertNotEqual(
                    picture.crop(arena_intro.EVENT_RECT).getextrema(),
                    ((235, 235), (216, 216), (173, 173)),
                )
            self.assertEqual(banners.call_args.kwargs["left_rect"], arena_intro.RED_BANNER)
            self.assertEqual(banners.call_args.kwargs["right_rect"], arena_intro.BLUE_BANNER)

    def test_lower_plaque_names_are_centre_aligned(self):
        # Verify the painted glyph bounds, including proportional glyph widths.
        from PIL import ImageDraw
        for rect, name in (
            (arena_intro.RED_NAME, "TheDude"),
            (arena_intro.BLUE_NAME, "Osric the Careful"),
        ):
            background = (250, 238, 212)
            image = Image.new("RGB", (1672, 941), background)
            arena_intro._text(ImageDraw.Draw(image), name, rect, size=46, minimum=20)
            bounds = Image.eval(image.convert("L"), lambda x: 255 if x < 226 else 0).getbbox()
            self.assertIsNotNone(bounds)
            actual_cx = (bounds[0] + bounds[2]) / 2
            expected_cx = (rect[0] + rect[2]) / 2
            self.assertLessEqual(abs(actual_cx - expected_cx), 3)

    def test_arena_label_is_higher_than_original_layout(self):
        self.assertLess(
            (arena_intro.ARENA_RECT[1] + arena_intro.ARENA_RECT[3]) / 2, 215
        )

    def test_tournament_final_label_has_no_gameplay_side_effect(self):
        p = prepared()
        p.intro_event_type = "Tournament Final"
        self.assertEqual(arena_intro.event_type(p), "TOURNAMENT FINAL")
        self.assertEqual(p.mode, "challenge")


class IntroDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_intro_then_first_pass_then_final_on_same_message(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "arenas").mkdir()
            (root / "arenas" / "royal_lists.png").touch()
            clip_path = root / "pass_1.gif"
            clip_path.write_bytes(b"GIF89a")
            clip = renderer.PassClip(clip_path, 1200, 1, (0, 0), (1, 0), renderer.PHASES)
            edits, sends, sleeps = [], [], []
            message = SimpleNamespace()
            async def edit(**kwargs):
                edits.append(kwargs)
                return message
            async def send(**kwargs):
                sends.append(kwargs)
                return message
            async def sleep(duration):
                sleeps.append(duration)
            message.edit = edit
            with patch.object(live, "ASSET_ROOT", root), \
                 patch.object(live, "render_live_pass", return_value=clip), \
                 patch.object(live, "_intro_image", new_callable=AsyncMock, return_value=b"png"), \
                 patch.object(live, "_final_image", new_callable=AsyncMock, return_value=None), \
                 patch.dict("os.environ", {"JOUST_LIVE_INTRO_SECONDS": "1.3"}):
                success = await live.play_live_match(SimpleNamespace(send=send), result(),
                                                     prepared(), sleep=sleep, pause=0)
            self.assertTrue(success)
            self.assertEqual(len(sends), 1)
            self.assertEqual(len(edits), 2)
            self.assertEqual(sends[0]["embed"].image.url, "attachment://joust_live_intro.png")
            self.assertIn("pass_1.gif", edits[0]["embed"].image.url)
            self.assertEqual(edits[-1]["embed"].title, "🏆 The Grand Lists — Final Result")
            self.assertAlmostEqual(sleeps[0], 1.3)
            self.assertGreater(sleeps[1], 1.0)

    async def test_missing_intro_retains_original_first_pass_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "arenas").mkdir()
            (root / "arenas" / "royal_lists.png").touch()
            path = root / "pass_1.gif"
            path.write_bytes(b"GIF89a")
            clip = renderer.PassClip(path, 1100, 1, (0, 0), (1, 0), renderer.PHASES)
            message = SimpleNamespace(edit=AsyncMock())
            sender = SimpleNamespace(send=AsyncMock(return_value=message))
            with patch.object(live, "ASSET_ROOT", root), \
                 patch.object(live, "render_live_pass", return_value=clip), \
                 patch.object(live, "_intro_image", new_callable=AsyncMock, return_value=None), \
                 patch.object(live, "_final_image", new_callable=AsyncMock, return_value=None):
                success = await live.play_live_match(sender, result(), prepared(), sleep=AsyncMock())
            self.assertTrue(success)
            self.assertIn("pass_1.gif", sender.send.await_args.kwargs["embed"].image.url)
            self.assertEqual(message.edit.await_count, 1)
