"""v0.9.2a integration checks that run on clean GitHub without binary artwork."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image
from services import sprite_engine as engine
from services.sprite_broadcast_adapter import send_sprite_broadcast


def fighter(uid, name, breed):
    return SimpleNamespace(user_id=uid, knight_name=name, horse_name=name+" Horse",
                           horse_breed=breed)


def match(passes=1):
    history = [
        SimpleNamespace(pass_no=i, points_a=1, points_b=0, category="lance_break",
                        result="Red: lance break", notes=[], margin=2)
        for i in range(1, passes+1)
    ]
    return SimpleNamespace(
        fighter_a="Red", fighter_b="Blue", arena_name="Royal Lists",
        score_a=passes, score_b=0, winner="Red", seed=42, passes=history,
    )


class SpriteEngineTests(unittest.TestCase):
    def test_fighter_breed_positional_compatibility_and_seeded_combat(self):
        """Previous asset audits pass breed as ninth positional field."""
        from services.combat import Fighter, run_single_match

        args_a = (11, "Arthur", "Sable", 
                  {"strength": 6, "control": 6, "endurance": 6,
                   "agility": 5, "resolve": 5, "tactics": 5},
                  {"speed": 6, "stamina": 6, "power": 5,
                   "obedience": 6, "courage": 6},
                  "lance_ash", "armour_mail", "barding_none")
        args_b = (12, "Basil", "Misty",
                  {"strength": 6, "control": 6, "endurance": 6,
                   "agility": 5, "resolve": 5, "tactics": 5},
                  {"speed": 6, "stamina": 6, "power": 5,
                   "obedience": 6, "courage": 6},
                  "lance_ash", "armour_mail", "barding_none")
        legacy_a = Fighter(*args_a)
        legacy_b = Fighter(*args_b)
        sprite_a = Fighter(*args_a, "destrier")
        sprite_b = Fighter(*args_b, "courser")
        self.assertEqual(legacy_a.horse_breed, "rouncey")
        self.assertEqual(sprite_a.horse_breed, "destrier")
        self.assertEqual(engine.AssetCatalog().horse_coat(sprite_a), "Black")
        first = run_single_match(legacy_a, legacy_b, "royal_lists", seed=2345)
        second = run_single_match(sprite_a, sprite_b, "royal_lists", seed=2345)
        self.assertEqual(first, second)  # breed is purely visual metadata

    def test_strict_numbering_excludes_previews_and_strips(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            for file in ("gallop_02.png", "gallop_01.png", "gallop.png",
                         "gallop_strip.png", "gallop_preview.png"):
                (folder/file).touch()
            self.assertEqual(
                [p.name for p in engine.AssetCatalog._numbered(folder, "gallop")],
                ["gallop_01.png", "gallop_02.png"],
            )

    def test_horse_coat_mapping_and_knight_orientations(self):
        with tempfile.TemporaryDirectory() as root:
            atlas = engine.AssetCatalog(Path(root))
            self.assertEqual(atlas.horse_coat(fighter(1, "A", "destrier")), "Black")
            self.assertEqual(atlas.horse_coat(fighter(2, "B", "courser")), "Bay")
            self.assertEqual(atlas.knight("red", "gallop", True)[0].size, (170, 272))
            self.assertEqual(atlas.knight("blue", "gallop", False)[0].size, (170, 272))
            self.assertEqual(atlas.horse("Chestnut", "gallop")[0].size, (285, 285))
            self.assertIn("knight", " ".join(atlas.missing))

    def test_pass_category_mapping_both_hit_and_unhorsing(self):
        a, b = fighter(1, "Red", "rouncey"), fighter(2, "Blue", "courser")
        p = SimpleNamespace(category="unhorsing", result="Impact!", notes=[],
                            points_a=3, points_b=0)
        self.assertEqual(engine._event(p, a, b)[1], {"b"})
        p.category = "horse_refusal"
        p.points_a = 0
        p.points_b = 1
        self.assertEqual(engine._event(p, a, b)[1], {"a"})

    def test_render_is_pure_and_has_score_integrity_guard(self):
        with tempfile.TemporaryDirectory() as name:
            atlas = engine.AssetCatalog(Path(name))
            a, b = fighter(1, "Red", "rouncey"), fighter(2, "Blue", "destrier")
            result = match()
            output_dir = Path(name)/"renders"
            with patch.object(engine, "RENDER_DIR", output_dir):
                bundle = engine.render_match_media(result, a, b, "royal_lists",
                                                   out_stem="test", catalog=atlas)
                self.assertTrue(bundle.gif_path.is_file())
                self.assertTrue(bundle.summary_path.is_file())
                with Image.open(bundle.gif_path) as animated:
                    self.assertGreaterEqual(animated.n_frames, 10)
                self.assertEqual(result.score_a, 1)
                result.score_a = 99
                with self.assertRaisesRegex(ValueError, "totals"):
                    engine.render_match_media(result, a, b, "royal_lists",
                                              out_stem="bad", catalog=atlas)

    def test_duplicate_pass_fails_before_output(self):
        a, b = fighter(1, "Red", "rouncey"), fighter(2, "Blue", "destrier")
        m = match()
        m.passes.append(m.passes[0])
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "Duplicate pass"):
                engine.render_match_media(m, a, b, "royal_lists",
                                          catalog=engine.AssetCatalog(Path(root)))


class SpriteAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_without_art_the_previous_broadcast_is_used(self):
        with tempfile.TemporaryDirectory() as name:
            prepared = SimpleNamespace(arena_key="royal_lists")
            sender = SimpleNamespace(send=AsyncMock())
            # The live broadcaster imports ASSET_ROOT into its own module.
            # Patch the *lookup site*, not the sprite_engine definition, so
            # this test also passes on machines with the full PNG pack installed.
            with patch("services.live_broadcast.ASSET_ROOT", Path(name)):
                self.assertFalse(await send_sprite_broadcast(sender, match(), prepared))
            sender.send.assert_not_awaited()

    async def test_disabled_sprite_replay_does_not_send(self):
        sender = SimpleNamespace(send=AsyncMock())
        with patch.dict("os.environ", {"JOUST_SPRITE_ENABLED": "false"}):
            self.assertFalse(await send_sprite_broadcast(sender, match(),
                                                          SimpleNamespace(arena_key="royal_lists")))
        sender.send.assert_not_awaited()

    async def test_adapter_delegates_to_single_live_message_without_combat(self):
        sender = SimpleNamespace(send=AsyncMock())
        prepared = SimpleNamespace(arena_key="royal_lists")
        with patch("services.live_broadcast.play_live_match", new_callable=AsyncMock,
                   return_value=True) as live:
            sent = await send_sprite_broadcast(sender, match(), prepared)
        self.assertTrue(sent)
        live.assert_awaited_once()
        sender.send.assert_not_awaited()



if __name__ == "__main__":
    unittest.main()
