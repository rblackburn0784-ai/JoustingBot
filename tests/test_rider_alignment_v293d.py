"""v2.9.3d: real stage geometry for off-hand shields and lance contact.

Synthetic sprite tests need no art pack, network, Discord or player records.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services import sprite_engine, sprite_staging


class ContactGeometryTests(unittest.TestCase):
    def test_shields_move_up_and_inwards_on_both_riders(self):
        layout = sprite_staging.SceneLayout()
        self.assertEqual(layout.shield_forward_offset_x, 8)
        self.assertEqual(layout.shield_offhand_lift, 35)
        self.assertEqual(
            sprite_staging.shield_position(
                rider_centre_x=373, lance_grip_y=260,
                face_right=True, shield_size=(50, 70), layout=layout),
            (381, 225))
        self.assertEqual(
            sprite_staging.shield_position(
                rider_centre_x=587, lance_grip_y=260,
                face_right=False, shield_size=(50, 70), layout=layout),
            (529, 225))

    def test_collision_lance_tips_land_inside_opponents_shields(self):
        layout = sprite_staging.SceneLayout()
        red_x, blue_x = sprite_staging.rider_centres(1.0, "heavy_hit", layout)
        self.assertEqual((red_x, blue_x), (373, 587))
        # Corresponds to default 285x285 horse and 90%-scale 170x272 knight.
        knight_height = round(272 * layout.knight_scale)
        knight_y = (layout.horse_top + 285
                    - layout.rider_foot_clearance - knight_height)
        grip_y = round(knight_y + knight_height * layout.lance_hand_fraction_y)
        red_shield = sprite_staging.shield_position(
            rider_centre_x=red_x, lance_grip_y=grip_y,
            face_right=True, shield_size=(50, 70), layout=layout)
        blue_shield = sprite_staging.shield_position(
            rider_centre_x=blue_x, lance_grip_y=grip_y,
            face_right=False, shield_size=(50, 70), layout=layout)
        red_tip = sprite_staging.lance_tip(
            hand=(red_x+layout.lance_hand_offset_x, grip_y),
            face_right=True)
        blue_tip = sprite_staging.lance_tip(
            hand=(blue_x-layout.lance_hand_offset_x, grip_y),
            face_right=False)
        self.assertLessEqual(blue_shield[0], red_tip[0])
        self.assertGreaterEqual(blue_shield[0]+50, red_tip[0])
        self.assertLessEqual(red_shield[0], blue_tip[0])
        self.assertGreaterEqual(red_shield[0]+50, blue_tip[0])
        for _x, y in (red_tip, blue_tip):
            self.assertGreaterEqual(y, red_shield[1])
            self.assertLessEqual(y, red_shield[1] + 70)

    def test_early_frames_keep_distance_and_misses_do_not_touch(self):
        layout = sprite_staging.SceneLayout()
        for pos in (.11, .40, .60):
            with self.subTest(pos=pos):
                self.assertEqual(
                    sprite_staging.rider_centres(pos, "heavy_hit", layout),
                    (round(95+260*pos), round(865-260*pos)))
        for kind in ("miss", "refusal", "slip"):
            self.assertEqual(
                sprite_staging.rider_centres(1.0, kind, layout),
                (355, 605))
        near = sprite_staging.rider_centres(.83, "heavy_hit", layout)
        self.assertGreater(near[0], round(95+260*.83))
        self.assertLess(near[1], round(865-260*.83))

    def test_artist_layout_values_are_validated_and_fall_back_safely(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "scene_layout.json"
            config.write_text(json.dumps({
                "shield_forward_offset_x": 14,
                "shield_offhand_lift": 57,
                "collision_closure_px": 25,
            }), encoding="utf-8")
            layout = sprite_staging.load_layout(root)
            self.assertEqual(layout.shield_forward_offset_x, 14)
            self.assertEqual(layout.shield_offhand_lift, 57)
            self.assertEqual(layout.collision_closure_px, 25)
            config.write_text(json.dumps({"collision_closure_px": 9999}),
                              encoding="utf-8")
            self.assertEqual(sprite_staging.load_layout(root),
                             sprite_staging.SceneLayout())

    def test_red_and_blue_shields_render_on_top_of_the_riders(self):
        class FakeAtlas:
            root = Path("/tmp/joust_fake_no_art")

            def horse(self, coat, state, face_right=True):
                return (Image.new("RGBA", (285, 285), (35, 35, 35, 255)),)

            def knight(self, colour, state, face_right=True, *, scale=1.0):
                return (Image.new("RGBA",
                                  (round(170*scale), round(272*scale)),
                                  (120, 32, 32, 255)),)

            def prop(self, name, dims=(80, 90), flip=False):
                c = (0, 230, 0, 255) if name == "shield" else (250, 220, 30, 255)
                return Image.new("RGBA", dims, c)

        atlas = FakeAtlas()
        layout = sprite_staging.SceneLayout()
        for face_right, x in ((True, 373), (False, 587)):
            with self.subTest(face_right=face_right):
                canvas = Image.new("RGBA", (960, 540), (0, 0, 0, 255))
                sprite_engine._rider(
                    canvas, atlas, "Bay", face_right, "lower_lance", "gallop",
                    x, 0, True, False, False, layout)
                knight_y = (layout.horse_top + 285 - layout.rider_foot_clearance
                            - round(272*layout.knight_scale))
                grip_y = round(knight_y + round(272*layout.knight_scale)
                               * layout.lance_hand_fraction_y)
                left, top = sprite_staging.shield_position(
                    rider_centre_x=x, lance_grip_y=grip_y,
                    face_right=face_right, shield_size=(50, 70),
                    layout=layout)
                self.assertEqual(canvas.getpixel((left+25, top+25))[:3],
                                 (0, 230, 0))


if __name__ == "__main__":
    unittest.main()
