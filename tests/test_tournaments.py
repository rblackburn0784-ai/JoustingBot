"""v0.8.5: tournament bracket, registration, persistence, UI and journal tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import discord

from services import tournaments as t
from services import records as records


class BracketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(t, "PATH", str(Path(self.temp.name) / "tournaments.json"))
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temp.cleanup()

    def register(self, guild=100, size=4):
        item = t.create(guild, 1, "The King's Cup", size)
        for uid in range(10, 10 + size):
            t.join(guild, uid)
        return item

    def test_four_player_registration_and_bracket(self):
        item = self.register(size=4)
        self.assertEqual(item["size"], 4)
        self.assertEqual(len(item["entrants"]), 4)
        with self.assertRaisesRegex(t.TournamentError, "full"):
            t.join(100, 99)
        with self.assertRaisesRegex(t.TournamentError, "Finish"):
            t.create(100, 1, "Second Tournament", 4)
        started = t.start(100)
        self.assertEqual([len(x) for x in started["rounds"]], [2, 1])
        self.assertEqual({i for rnd in started["rounds"] for m in rnd
                          for i in (m["arena_key"],)}.issubset(set(__import__("services.arenas", fromlist=["ARENAS"]).ARENAS)), True)
        count = 0
        while t.current(100):
            choice = t.reserve_next(100)
            match = choice["match"]
            self.assertNotEqual(match["a"], match["b"])
            self.assertTrue(match["seed"] > 0)
            # Reserve twice still points to same saved match, not a second event.
            self.assertEqual(t.reserve_next(100)["match"]["id"], match["id"])
            t.complete_match(100, started["id"], match["id"], match["a"], match["id"])
            count += 1
        self.assertEqual(count, 3)
        hist = t.recent(100)
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["status"], "completed")
        self.assertIn(hist[0]["champion"], started["entrants"])
        self.assertIsNone(t.current(100))
        # Can run a new event after archiving the previous one.
        self.assertEqual(t.create(100, 1, "Second Tournament", 8)["size"], 8)

    def test_eight_player_seven_matches(self):
        self.register(size=8)
        item = t.start(100)
        self.assertEqual([len(x) for x in item["rounds"]], [4, 2, 1])
        completed = 0
        while t.current(100):
            nxt = t.reserve_next(100)["match"]
            t.complete_match(100, item["id"], nxt["id"], nxt["b"], nxt["id"])
            completed += 1
        self.assertEqual(completed, 7)
        self.assertIn(t.recent(100)[0]["champion"], item["entrants"])

    def test_no_early_start_and_no_duplicate_registration(self):
        t.create(100, 3, "Winter Cup", 8)
        t.join(100, 10)
        with self.assertRaisesRegex(t.TournamentError, "already registered"):
            t.join(100, 10)
        with self.assertRaisesRegex(t.TournamentError, "full"):
            t.start(100)
        with self.assertRaisesRegex(t.TournamentError, "No tournament"):
            t.reserve_next(100)

    def test_guild_isolation_and_recovery_from_reserved_match(self):
        self.register(100, size=4)
        self.register(200, size=8)
        t.start(100)
        a = t.reserve_next(100)["match"]
        other = t.current(200)
        self.assertEqual(other["status"], "registration")
        # Simulate process restart: read the same state from disk.
        recovered = t.reserve_next(100)["match"]
        self.assertEqual(a["id"], recovered["id"])
        self.assertEqual(a["seed"], recovered["seed"])
        self.assertEqual(a["arena_key"], recovered["arena_key"])
        t.complete_match(100, t.current(100)["id"], a["id"], a["a"], a["id"])
        self.assertEqual(t.current(200)["status"], "registration")

    def test_match_must_be_reserved_and_winner_must_participate(self):
        self.register()
        item = t.start(100)
        match = t.pending(item)["match"]
        with self.assertRaisesRegex(t.TournamentError, "reserved"):
            t.complete_match(100, item["id"], match["id"], match["a"], match["id"])
        t.reserve_next(100)
        with self.assertRaisesRegex(t.TournamentError, "registered entrants"):
            t.complete_match(100, item["id"], match["id"], 999, match["id"])
        with self.assertRaisesRegex(t.TournamentError, "not the current"):
            t.complete_match(100, item["id"], "unknown", match["a"], "unknown")

    def test_tiebreak_is_stable(self):
        for seed in (1, 4, 9001):
            winner = t.tie_winner(10, 11, seed)
            self.assertIn(winner, (10, 11))
            self.assertEqual(t.tie_winner(10, 11, seed), winner)


class JournalTests(unittest.TestCase):
    def test_tournament_match_id_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(records, "HISTORY_PATH", str(Path(td) / "matches.json")):
                a = SimpleNamespace(user_id=12, knight_name="Knight A", horse_name="Mount A",
                                    lance_key="lance_ash", armour_key="armour_mail",
                                    barding_key="barding_none")
                b = SimpleNamespace(user_id=13, knight_name="Knight B", horse_name="Mount B",
                                    lance_key="lance_ash", armour_key="armour_mail",
                                    barding_key="barding_none")
                obj = SimpleNamespace(
                    guild_id=100, arena_key="royal_lists", mode="challenge",
                    fighter_a=a, fighter_b=b,
                    knight_a=SimpleNamespace(name="Knight A"),
                    knight_b=SimpleNamespace(name="Knight B"),
                    horse_a=SimpleNamespace(name="Mount A", horse_id="ha", breed="Destrier", stats={}),
                    horse_b=SimpleNamespace(name="Mount B", horse_id="hb", breed="Destrier", stats={}),
                    had_injury_a=False, had_injury_b=False,
                    support_token_a=None, support_token_b=None,
                )
                result = SimpleNamespace(seed=123, arena_name="Royal Lists",
                                         score_a=3, score_b=0, passes=[])
                key = "t-cup-r1-m1"
                self.assertEqual(records.record_match(
                    obj, result, match_id=key, tournament_id="cup"), key)
                self.assertEqual(records.record_match(
                    obj, result, match_id=key, tournament_id="cup"), key)
                self.assertEqual(len(records.load_history()["matches"]), 1)
                self.assertEqual(records.load_history()["matches"][0]["mode"], "challenge")
                self.assertEqual(records.load_history()["matches"][0]["tournament_id"], "cup")
                with self.assertRaisesRegex(ValueError, "identity conflict"):
                    records.record_match(obj, result, match_id=key, tournament_id="other")


class ButtonTests(unittest.TestCase):
    def test_public_panel_buttons_are_persistent_and_home_is_present(self):
        from cogs.tournament import TournamentPanel, TournamentHub
        view = TournamentPanel()
        self.assertIsNone(view.timeout)
        for child in view.children:
            self.assertTrue(child.custom_id)
        labels = {child.label for child in view.children}
        self.assertTrue({"Join Tournament", "Start Tournament", "Start Next Match",
                         "History", "Refresh", "Main Menu"} <= labels)
        hub = TournamentHub(55, None, False)
        self.assertIn("Main Menu", {v.label for v in hub.children})
        self.assertNotIn("Create", {v.label for v in hub.children})
        admin = TournamentHub(55, None, True)
        self.assertIn("Create", {v.label for v in admin.children})


if __name__ == "__main__":
    unittest.main()
