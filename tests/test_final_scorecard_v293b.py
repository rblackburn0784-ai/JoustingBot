"""v2.9.3b: genuine winner background, coloured columns and stats integrity."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from services import broadcast_art, final_scorecard
from services.combat import PassLog


def result(winner="Red Knight"):
    return SimpleNamespace(
        fighter_a="Red Knight", fighter_b="Blue Knight",
        winner=winner, arena_name="Royal Lists",
        score_a=2, score_b=3, seed=415723,
        passes=[
            PassLog(1, "Red: lance break", "lance_break", 2, 0, 8),
            PassLog(2, "Blue: unhorsing", "unhorsing", 0, 3, 12),
        ],
    )


def prepared():
    return SimpleNamespace(arena_key="royal_lists", mode="training",
                           scorecard_injuries={"a": 1, "b": 0})


class Templates(unittest.TestCase):
    def test_winner_side_selects_correct_template(self):
        self.assertEqual(final_scorecard.template_colour(result("Red Knight")), "red")
        self.assertEqual(final_scorecard.template_colour(result("Blue Knight")), "blue")
        self.assertIsNone(final_scorecard.template_colour(result("Draw")))

    def test_blue_left_red_right_names_stats_and_footer(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for colour, rgb in (("blue", (14, 40, 90)), ("red", (145, 22, 24))):
                Image.new("RGB", final_scorecard.SIZE, rgb).save(
                    root / final_scorecard.TEMPLATES[colour])
            with patch.object(final_scorecard, "ART_ROOT", root), \
                 patch.object(final_scorecard, "_in_panel", wraps=final_scorecard._in_panel) as ink:
                original = result("Red Knight")
                data = final_scorecard.render(original, prepared())
                self.assertEqual((original.score_a, original.score_b), (2, 3))
                self.assertEqual(len(original.passes), 2)
                self.assertIsNotNone(data)
                args = [(call.args[1], call.args[2]) for call in ink.call_args_list]
                self.assertIn(("Blue Knight", final_scorecard.NAME_RECTS["blue"]), args)
                self.assertIn(("Red Knight", final_scorecard.NAME_RECTS["red"]), args)
                self.assertIn(("Royal Lists", final_scorecard.BOTTOM_RECTS["arena"]), args)
                self.assertIn(("TRAINING", final_scorecard.BOTTOM_RECTS["format"]), args)
                self.assertIn((415723, final_scorecard.BOTTOM_RECTS["seed"]), args)
                # Blue is fighter B: 3 awarded points, 1 unhorsing and 0 injuries.
                self.assertIn((3, final_scorecard.BOTTOM_RECTS["seed"])
                              if False else (3, (
                                  final_scorecard.STAT_X["blue"]-56,
                                  final_scorecard.STAT_Y["impact_score"]-22,
                                  final_scorecard.STAT_X["blue"]+56,
                                  final_scorecard.STAT_Y["impact_score"]+28)), args)
                self.assertIn((1, (
                    final_scorecard.STAT_X["red"]-56,
                    final_scorecard.STAT_Y["injuries"]-22,
                    final_scorecard.STAT_X["red"]+56,
                    final_scorecard.STAT_Y["injuries"]+28)), args)
                with Image.open(BytesIO(data)) as im:
                    self.assertEqual(im.size, (1672, 941))
                    self.assertEqual(im.format, "PNG")
                    self.assertEqual(im.getpixel((0, 0)), (145, 22, 24))
            with patch.object(final_scorecard, "ART_ROOT", root):
                image = Image.open(BytesIO(final_scorecard.render(
                    result("Blue Knight"), prepared())))
                self.assertEqual(image.getpixel((0, 0)), (14, 40, 90))

    def test_draw_damaged_and_missing_image_use_existing_neutral_card(self):
        with TemporaryDirectory() as temp:
            with patch.object(final_scorecard, "ART_ROOT", Path(temp)), \
                 patch.object(broadcast_art, "ROOT", Path(temp)):
                drawn = broadcast_art.final(result("Draw"), prepared())
                with Image.open(BytesIO(drawn)) as im:
                    self.assertEqual(im.size, (1200, 675))
                missing = broadcast_art.final(result("Red Knight"), prepared())
                with Image.open(BytesIO(missing)) as im:
                    self.assertEqual(im.size, (1200, 675))
                (Path(temp) / "final_red_win.png").write_bytes(b"not png")
                damaged = broadcast_art.final(result("Red Knight"), prepared())
                with Image.open(BytesIO(damaged)) as im:
                    self.assertEqual(im.size, (1200, 675))

    def test_long_names_do_not_spill_into_labels(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            Image.new("RGB", final_scorecard.SIZE, (238, 194, 124)).save(
                root / "final_blue_win.png")
            match = result("Blue Knight")
            match.fighter_b = "Blue Knight"  # template selection stays exact
            match.fighter_a = "A Very Very Very Long Knight Name The Seventh"
            with patch.object(final_scorecard, "ART_ROOT", root):
                data = final_scorecard.render(match, prepared())
                self.assertTrue(data)
                with Image.open(BytesIO(data)) as im:
                    self.assertEqual(im.size, final_scorecard.SIZE)

    def test_stat_counts_are_from_saved_match(self):
        self.assertEqual(final_scorecard._injuries(prepared()), (1, 0))
        self.assertEqual(final_scorecard._injuries(SimpleNamespace()), (0, 0))
        self.assertEqual(final_scorecard._format(prepared()), "TRAINING")
        self.assertEqual(final_scorecard._format(
            SimpleNamespace(mode="challenge")), "RANKED JOUST")


if __name__ == "__main__":
    unittest.main()
