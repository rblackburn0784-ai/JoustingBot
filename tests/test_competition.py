"""Regression tests for v0.7 competition rules; no Discord token required."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from services import competition as c


def match(mid, guild=12, arena="royal_lists", score_a=3, score_b=0,
          a_id=1, b_id=2, a_horse="h1", b_horse="h2", passes=None):
    return {
        "id": mid, "guild_id": guild, "arena_key": arena, "mode": "challenge",
        "a": {"user_id": a_id, "knight": "Arthur", "horse": "Thunder",
              "horse_id": a_horse, "score": score_a},
        "b": {"user_id": b_id, "knight": "Basil", "horse": "Biscuit",
              "horse_id": b_horse, "score": score_b},
        "passes": passes or [],
    }


class CompetitionTests(unittest.TestCase):
    def test_instant_matches_do_not_rank(self):
        instant = match("instant")
        instant["mode"] = "instant"
        self.assertEqual(c.ranked(12, "wins", {"matches": [instant]}), [])
        self.assertEqual(c.title_progress(12, 1, {"matches": [instant]})["crowd_favourite"]["progress"], 0)

    def test_server_isolation_and_duplicate_match_ids(self):
        fixture = {"matches": [
            match("first"),
            match("first"),  # retry with the same ID must not double count
            match("second", guild=99),
            match("legacy", guild=None),
        ]}
        self.assertEqual(c.aggregate(12, fixture)[0][1]["wins"], 1)
        self.assertEqual(c.aggregate(99, fixture)[0][1]["wins"], 1)
        self.assertEqual(len(c.guild_matches(12, fixture)), 1)

    def test_minimum_five_jousts_for_win_rate(self):
        history = {"matches": [match(f"m{i}") for i in range(4)]}
        self.assertEqual(c.ranked(12, "winrate", history), [])
        history["matches"].append(match("m4"))
        rows = c.ranked(12, "winrate", history)
        self.assertEqual(rows[0]["id"], 1)
        self.assertEqual(rows[0]["value"], 100.0)

    def test_horse_clean_rate_and_incidents(self):
        refusal = {"category": "horse_refusal", "result": "Thunder: horse refusal",
                   "points_a": 0, "points_b": 1, "notes": []}
        slip = {"category": "horse_slip", "result": "Thunder: horse slip",
                "points_a": 0, "points_b": 1, "notes": []}
        data = {"matches": [
            match("clean1"), match("clean2"), match("refusal", passes=[refusal]),
            match("slip", passes=[slip]), match("clean3")
        ]}
        knights, horses = c.aggregate(12, data)
        self.assertEqual(horses["h1"]["clean_jousts"], 3)
        self.assertEqual(horses["h1"]["refusals"], 1)
        self.assertEqual(horses["h1"]["slips"], 1)
        self.assertEqual(knights[1]["refusals"], 1)
        board = c.ranked(12, "reliable_horse", data)
        thunder = next(row for row in board if row["id"] == "h1")
        self.assertEqual(thunder["value"], 60.0)

    def test_titles_progress_and_equipping(self):
        passes = [
            {"category": "lance_break", "result": "Arthur: lance break",
             "points_a": 1, "points_b": 0, "notes": []},
            {"category": "unhorsing", "result": "Basil: unhorsing",
             "points_a": 0, "points_b": 3, "notes": []},
        ]
        data = {"matches": [
            match(f"m{i}", arena="muddy_field", passes=passes) for i in range(10)
        ]}
        progress = c.title_progress(12, 1, data)
        self.assertTrue(progress["shield_splitter"]["earned"])
        self.assertTrue(progress["mud_king"]["earned"])
        self.assertTrue(progress["the_unhorsed"]["earned"])
        self.assertTrue(progress["crowd_favourite"]["earned"])
        self.assertFalse(progress["frozen_terror"]["earned"])
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(c, "TITLES_PATH", os.path.join(directory, "titles.json")):
                c.set_title(12, 1, "mud_king", data)
                self.assertEqual(c.equipped_title(12, 1, data), "Mud King")
                self.assertIsNone(c.equipped_title(99, 1, data))
                with self.assertRaises(ValueError):
                    c.set_title(12, 1, "frozen_terror", data)
                c.set_title(12, 1, None, data)
                self.assertIsNone(c.equipped_title(12, 1, data))

    def test_arena_specialist_and_chaotic_horse(self):
        refusal = {"category": "horse_refusal", "result": "Thunder: horse refusal",
                   "points_a": 0, "points_b": 1, "notes": []}
        data = {"matches": [
            match("m1", arena="frozen_ground", passes=[refusal]),
            match("m2", arena="frozen_ground", passes=[refusal]),
            match("m3", arena="frozen_ground", passes=[refusal]),
        ]}
        self.assertEqual(c.ranked(12, "arena", data)[0]["id"], 1)
        self.assertEqual(c.ranked(12, "chaotic_horse", data)[0]["id"], "h1")
        self.assertEqual(c.ranked(12, "reliable_horse", data), [])


if __name__ == "__main__":
    unittest.main()
