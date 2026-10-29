"""v2.9.3 render regression suite; uses synthetic art, no player data or Discord."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from services import sprite_engine as engine
from services import sprite_staging as stage


def opaque(color, dims):
    return Image.new("RGBA", dims, color)


class FakeAtlas:
    def __init__(self, root):
        self.root = Path(root)
        self.scene_layout = stage.SceneLayout()

    def horse(self, coat, state, face_right=True):
        return (opaque((222, 32, 26, 255) if face_right else
                       (28, 72, 218, 255), (285, 285)),)

    def knight(self, colour, state, face_right=True, *, scale=1.0):
        dims = (round(170 * scale), round(272 * scale))
        return (opaque((235, 80, 67, 255) if colour == "red" else
                       (72, 110, 235, 255), dims),)

    def prop(self, name, dims=(80, 90), flip=False):
        color = ((30, 230, 60, 255) if name == "barrier"
                 else (235, 200, 60, 255))
        return opaque(color, dims)

    def crowd(self, mood):
        return opaque((220, 30, 200, 255), (940, 98))

    def effect(self, name, dims=(105, 105)):
        return (opaque((0, 0, 0, 0), dims),)


def scene(root, phase="PREP"):
    log = SimpleNamespace(pass_no=1, result="Training", points_a=0, points_b=0)
    fa = SimpleNamespace(knight_name="Red Rider")
    fb = SimpleNamespace(knight_name="Blue Rider")
    return engine._scene(
        opaque((40, 60, 80, 255), engine.SIZE), FakeAtlas(root),
        fa, fb, "Bay", "Black", log, phase, 0, .11,
        (0, 0), "clash", set(), "none", commentary="",
    )


class LayoutTests(unittest.TestCase):
    def test_valid_config_matches_default_and_is_artist_editable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scene_layout.json"
            path.write_text(json.dumps({
                "horse_top": 152, "knight_scale": .87, "barrier_top": 341,
                "crowd_stands": [[10, 140, 260, 75], [340, 140, 280, 75],
                                 [690, 140, 260, 75]],
            }))
            custom = stage.load_layout(Path(tmp))
            self.assertEqual(custom.horse_top, 152)
            self.assertAlmostEqual(custom.knight_scale, .87)
            self.assertEqual(custom.barrier_top, 341)
            self.assertEqual(len(custom.crowd_stands), 3)
            path.write_text('{"horse_top":-200, "crowd_stands":[]}')
            self.assertEqual(stage.load_layout(Path(tmp)), stage.SceneLayout())

    def test_default_stage_raises_mounts_scales_knights_and_barrier(self):
        layout = stage.SceneLayout()
        self.assertLess(layout.horse_top, 195)
        self.assertLess(layout.knight_scale, 1.0)
        self.assertLess(layout.barrier_top, 408)
        self.assertEqual(len(layout.crowd_stands), 3)

    def test_atlas_knights_scale_without_affecting_horses(self):
        with tempfile.TemporaryDirectory() as tmp:
            atlas = engine.AssetCatalog(Path(tmp))
            scaled = atlas.knight("red", "idle", scale=.9)[0]
            regular = atlas.knight("red", "idle")[0]
            horse = atlas.horse("Bay", "idle")[0]
            self.assertEqual(scaled.size, (153, 245))
            self.assertEqual(regular.size, (170, 272))
            self.assertEqual(horse.size, (285, 285))


class LayerTests(unittest.TestCase):
    def test_barrier_sits_above_ground_between_blue_and_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            canvas = scene(tmp)
        layout = stage.SceneLayout()
        # Central barrier visible; far/blue is obscured by the rail.
        self.assertEqual(canvas.getpixel((460, layout.barrier_top + 42))[:3],
                         (30, 230, 60))
        self.assertEqual(canvas.getpixel((820, layout.barrier_top + 42))[:3],
                         (30, 230, 60))
        # Near/red horse covers the barrier because it is in front.
        self.assertEqual(canvas.getpixel((140, layout.barrier_top + 42))[:3],
                         (222, 32, 26))
        # The previous pass/phase black plaque must not be drawn.
        self.assertEqual(canvas.getpixel((470, 100))[:3], (40, 60, 80))
        # But the scoreboard still exists.
        self.assertNotEqual(canvas.getpixel((440, 28))[:3], (40, 60, 80))

    def test_crowd_is_present_in_three_pavilions_not_across_walkways(self):
        with tempfile.TemporaryDirectory() as tmp:
            canvas = scene(tmp)
        for x in (100, 460, 750):
            self.assertEqual(canvas.getpixel((x, 155))[:3], (220, 30, 200))
        for x in (321, 640):
            self.assertEqual(canvas.getpixel((x, 155))[:3], (40, 60, 80))

    def test_lances_start_raised_from_the_hand_both_directions(self):
        layout = stage.SceneLayout()
        lance = opaque((230, 220, 20, 255), (196, 10))
        for direction, hand in ((True, (250, 350)), (False, (700, 350))):
            with self.subTest(face_right=direction):
                raised = opaque((0, 0, 0, 0), engine.SIZE)
                level = raised.copy()
                stage.attach_lance(raised, lance, hand=hand, face_right=direction,
                                   raised=True, layout=layout)
                stage.attach_lance(level, lance, hand=hand, face_right=direction,
                                   raised=False, layout=layout)
                rb = raised.getbbox()
                lb = level.getbbox()
                self.assertIsNotNone(rb)
                self.assertLess(rb[1], hand[1] - 60)
                self.assertGreater(lb[1], hand[1] - 15)
                self.assertLessEqual(rb[0], hand[0])
                self.assertGreaterEqual(rb[2], hand[0])
                self.assertEqual(raised.getpixel(hand)[:3], (230, 220, 20))


if __name__ == "__main__":
    unittest.main()
