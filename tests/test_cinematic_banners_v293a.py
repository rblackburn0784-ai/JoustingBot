"""v2.9.3a cinematic timing, strict title visibility and NPC flags."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from services import live_banner_art, live_sprite_renderer, sprite_staging
from services.training import OPPONENTS
from services.banner_art import BANNER_FILES


def fighter(user_id):
    return SimpleNamespace(user_id=user_id, knight_name=f"Rider {user_id}")


class CinemaTimingTests(unittest.TestCase):
    def test_pass_runs_seven_seconds_with_five_original_phases(self):
        moments = live_sprite_renderer.timeline()
        self.assertEqual(len(moments), 26)
        self.assertEqual(sum(item.duration_ms for item in moments), 6950)
        self.assertGreater(sum(item.duration_ms for item in moments), 4300 + 2000)
        self.assertEqual(moments[-1].duration_ms, 1200)
        stages = tuple(dict.fromkeys(m.phase for m in moments))
        self.assertEqual(stages, live_sprite_renderer.PHASES)
        self.assertEqual(len(set(live_sprite_renderer.PHASES)), 5)
        self.assertEqual(live_sprite_renderer.timeline("slip")[-1].phase, "OUTCOME")

    def test_refusal_still_stops_before_collision(self):
        moments = live_sprite_renderer.timeline("refusal")
        collide = next(m for m in moments if m.phase == "COLLISION")
        self.assertLess(collide.position, 1.0)


class BannerSelectionTests(unittest.TestCase):
    def test_all_twelve_npcs_have_distinct_personality_title_mappings(self):
        self.assertEqual(len(OPPONENTS), 12)
        self.assertEqual(set(live_banner_art.NPC_BANNERS),
                         {npc.key for npc in OPPONENTS})
        self.assertEqual(len(set(live_banner_art.NPC_BANNERS.values())), 12)
        self.assertTrue(set(live_banner_art.NPC_BANNERS.values()).issubset(BANNER_FILES))
        for npc in OPPONENTS:
            with self.subTest(npc=npc.name):
                self.assertEqual(live_banner_art.entrant_banner_key(fighter(npc.player_id), 7),
                                 live_banner_art.NPC_BANNERS[npc.key])

    def test_equipped_real_title_only_and_guild_scoped(self):
        with patch.object(live_banner_art, "equipped_title_key", return_value=None) as title:
            self.assertIsNone(live_banner_art.entrant_banner_key(fighter(42), 123))
            title.assert_called_once_with(123, 42)
        with patch.object(live_banner_art, "equipped_title_key", return_value="mud_king") as title:
            self.assertEqual(live_banner_art.entrant_banner_key(fighter(42), 123), "mud_king")
            self.assertIsNone(live_banner_art.entrant_banner_key(fighter(42), None))
            self.assertIsNone(live_banner_art.entrant_banner_key(fighter(-99999), 123))
            self.assertEqual(title.call_count, 1)

    def test_unknown_ids_never_get_fabricated_player_or_npc_flags(self):
        self.assertIsNone(live_banner_art.entrant_banner_key(fighter(0), 4))
        self.assertIsNone(live_banner_art.entrant_banner_key(fighter(-29000), 4))
        self.assertIsNone(live_banner_art.entrant_banner_key(SimpleNamespace(), 4))


class CompositingTests(unittest.TestCase):
    def test_neither_player_banner_means_draw_nothing(self):
        canvas = Image.new("RGBA", (960, 540), (20, 35, 50, 255))
        original = canvas.tobytes()
        lay = sprite_staging.SceneLayout()
        live_banner_art.draw_side_banners(
            canvas, left_key=None, right_key=None,
            left_rect=lay.left_banner_rect, right_rect=lay.right_banner_rect)
        self.assertEqual(canvas.tobytes(), original)

    def test_player_pngs_draw_only_on_correct_sides(self):
        with tempfile.TemporaryDirectory() as temp:
            png = Path(temp) / "flag.png"
            Image.new("RGBA", (90, 185), (240, 55, 75, 255)).save(png)
            canvas = Image.new("RGBA", (960, 540), (10, 20, 30, 255))
            lay = sprite_staging.SceneLayout()
            with patch.object(live_banner_art, "banner_path", return_value=png):
                live_banner_art.draw_side_banners(
                    canvas, left_key="mud_king", right_key="frozen_terror",
                    left_rect=lay.left_banner_rect, right_rect=lay.right_banner_rect)
            self.assertEqual(canvas.getpixel((64, 190))[:3], (240, 55, 75))
            self.assertEqual(canvas.getpixel((895, 190))[:3], (240, 55, 75))
            self.assertEqual(canvas.getpixel((470, 190))[:3], (10, 20, 30))

    def test_missing_player_png_stays_hidden_but_training_npc_has_heraldry(self):
        canvas = Image.new("RGBA", (960, 540), (10, 20, 30, 255))
        lay = sprite_staging.SceneLayout()
        with patch.object(live_banner_art, "banner_path", return_value=None):
            live_banner_art.draw_side_banners(
                canvas, left_key="mud_king", right_key="steady_in_the_saddle",
                right_npc=True, left_rect=lay.left_banner_rect,
                right_rect=lay.right_banner_rect)
        self.assertEqual(canvas.getpixel((60, 180))[:3], (10, 20, 30))
        self.assertNotEqual(canvas.getpixel((895, 180))[:3], (10, 20, 30))

    def test_crowd_mask_trimmed_to_stands_and_local_optional(self):
        lay = sprite_staging.SceneLayout()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.mkdir(exist_ok=True)
            # Explicit mask removes left half of left box, leaving all other
            # grandstands intact.
            mask = Image.new("L", (250, 62), 255)
            for x in range(125):
                for y in range(62):
                    mask.putpixel((x, y), 0)
            mask.save(root / "left.png")
            canvas = Image.new("RGBA", (960, 540), (10, 20, 30, 255))
            crowd = Image.new("RGBA", (940, 98), (220, 80, 115, 255))
            sprite_staging.fill_crowd_stands(
                canvas, crowd, lay.crowd_stands, mask_root=root)
            self.assertEqual(canvas.getpixel((50, 145))[:3], (10, 20, 30))
            self.assertEqual(canvas.getpixel((250, 145))[:3], (220, 80, 115))
            self.assertEqual(canvas.getpixel((460, 145))[:3], (220, 80, 115))
            self.assertEqual(canvas.getpixel((639, 145))[:3], (10, 20, 30))

    def test_validates_new_banner_rectangles(self):
        lay = sprite_staging.SceneLayout()
        self.assertGreater(lay.barrier_top + lay.barrier_height, 330)
        self.assertLess(lay.barrier_top + lay.barrier_height, lay.horse_top + 285)
        with self.assertRaises(ValueError):
            sprite_staging.SceneLayout(left_banner_rect=(0, 1, 80, 120))


if __name__ == "__main__":
    unittest.main()
