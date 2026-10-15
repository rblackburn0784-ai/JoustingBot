"""v0.8.5a: tournament-specific titles, medals, badges and UI safety tests."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import discord

from cogs.competition import title_autocomplete
from cogs.menu import TitlePage
from cogs.tournament import TournamentCabinet, TournamentHub, TournamentPanel
from services import records as rec
from services import tournaments as tour
from services import competition as comp
from services.tournament_awards import (
    TOURNAMENT_TITLES, TOURNAMENT_ACHIEVEMENTS,
    tournament_stats, achievement_progress,
)
from services.storage import save_json


class AwardsFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            patch.object(tour, "PATH", str(root / "tournaments.json")),
            patch.object(rec, "HISTORY_PATH", str(root / "matches.json")),
            patch.object(comp, "TITLES_PATH", str(root / "titles.json")),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp.cleanup()

    def complete(self, gid=80, size=4):
        event = tour.create(gid, 99, "King's Cup", size)
        for uid in range(101, 101 + size):
            tour.join(gid, uid)
        event = tour.start(gid)
        journal = rec.load_history()
        runner_up = None
        while tour.current(gid):
            pairing = tour.reserve_next(gid)["match"]
            a, b = pairing["a"], pairing["b"]
            # Deliberately ensure final is won by side A; the remaining matches
            # use a stable winning side and genuine scored points.
            result = {
                "id": pairing["id"], "mode": "challenge",
                "guild_id": gid, "tournament_id": event["id"],
                "arena_key": pairing["arena_key"],
                "a": {"user_id": a, "score": 3, "knight": "Arthur"},
                "b": {"user_id": b, "score": 0, "knight": "Basil"},
                "passes": [
                    {"category": "unhorsing", "points_a": 3, "points_b": 0},
                    {"category": "lance_break", "points_a": 1, "points_b": 0},
                ],
            }
            journal["matches"].append(result)
            save_json(rec.HISTORY_PATH, journal)
            runner_up = b
            tour.complete_match(gid, event["id"], pairing["id"], a, pairing["id"])
        event = tour.recent(gid, 1)[0]
        return event, event["champion"], runner_up

    def test_title_and_achievement_catalogue(self):
        self.assertEqual(len(TOURNAMENT_TITLES), 12)
        self.assertEqual(len(TOURNAMENT_ACHIEVEMENTS), 8)
        self.assertEqual(len(comp.TITLE_RULES), 30)
        self.assertEqual(len(set(comp.TITLE_RULES)), 30)

    def test_verified_champion_and_runner_up_awards(self):
        event, champion, silver = self.complete()
        top = tournament_stats(80, champion)
        bottom = tournament_stats(80, silver)
        self.assertEqual(top["championships"], 1)
        self.assertEqual(top["finals"], 1)
        self.assertEqual(top["advances"], 2)
        self.assertEqual(top["unhorsings"], 2)
        self.assertEqual(top["lance_breaks"], 2)
        self.assertEqual(bottom["runners_up"], 1)
        self.assertEqual(bottom["finals"], 1)

        badges = achievement_progress(80, champion)
        self.assertTrue(badges["victory_banner"]["earned"])
        self.assertTrue(badges["championship_bout"]["earned"])
        titles = comp.title_progress(80, champion)
        self.assertTrue(titles["cup_bearer"]["earned"])
        self.assertTrue(titles["lists_initiate"]["earned"])
        self.assertFalse(titles["king_of_the_lists"]["earned"])
        self.assertTrue(comp.title_progress(80, silver)["silver_lance"]["earned"])

    def test_tournament_title_can_equip_and_save(self):
        _, champion, _ = self.complete()
        comp.set_title(80, champion, "cup_bearer")
        self.assertEqual(comp.equipped_title(80, champion), "Cup Bearer")
        with self.assertRaisesRegex(ValueError, "haven't earned"):
            comp.set_title(80, champion, "king_of_the_lists")
        self.assertIsNone(comp.equipped_title(81, champion))

    def test_normal_joust_and_other_server_cannot_unlock_tournament_awards(self):
        event, champion, silver = self.complete(80)
        journal = rec.load_history()
        journal["matches"].append({
            "id": "ordinary", "mode": "challenge", "guild_id": 80,
            "a": {"user_id": champion, "score": 3},
            "b": {"user_id": silver, "score": 0},
            "passes": [{"category": "unhorsing", "points_a": 3, "points_b": 0}],
        })
        save_json(rec.HISTORY_PATH, journal)
        self.assertEqual(tournament_stats(80, champion)["championships"], 1)
        self.assertEqual(tournament_stats(80, champion)["unhorsings"], 2)
        self.assertEqual(tournament_stats(81, champion)["entries"], 0)
        self.assertFalse(achievement_progress(81, champion)["victory_banner"]["earned"])

    def test_unplayed_registration_grants_nothing(self):
        tour.create(80, 99, "Winter Lists", 8)
        tour.join(80, 101)
        self.assertEqual(tournament_stats(80, 101)["entries"], 0)
        self.assertFalse(comp.title_progress(80, 101)["lists_initiate"]["earned"])
        self.assertFalse(achievement_progress(80, 101)["first_registration"]["earned"])

    def test_history_keeps_more_than_twenty_events(self):
        for index in range(21):
            event = tour.create(80, 99, f"Cup {index}", 4)
            for uid in range(101, 105):
                tour.join(80, uid)
            event = tour.start(80)
            for _ in range(3):
                match = tour.reserve_next(80)["match"]
                journal = rec.load_history()
                journal["matches"].append({
                    "id": match["id"], "guild_id": 80,
                    "mode": "challenge", "tournament_id": event["id"],
                    "a": {"user_id": match["a"], "score": 3},
                    "b": {"user_id": match["b"], "score": 0},
                    "passes": [],
                })
                save_json(rec.HISTORY_PATH, journal)
                tour.complete_match(80, event["id"], match["id"], match["a"], match["id"])
        self.assertEqual(len(tour.load_db()["guilds"]["80"]["history"]), 21)
        self.assertEqual(tournament_stats(80, 101)["entries"], 21)

    def test_bad_history_result_cannot_create_championship(self):
        event, champion, silver = self.complete()
        journal = rec.load_history()
        for row in journal["matches"]:
            row["tournament_id"] = "wrong-event"
        save_json(rec.HISTORY_PATH, journal)
        self.assertEqual(tournament_stats(80, champion)["championships"], 0)
        self.assertEqual(tournament_stats(80, champion)["advances"], 0)

    def test_ui_pagination_and_tournament_cabinet_controls(self):
        page = TitlePage(101, 80, page=4)
        selects = [c for c in page.children if isinstance(c, discord.ui.Select)]
        self.assertEqual(len(selects), 1)
        self.assertEqual(len(selects[0].options), 6)
        self.assertIn("Main Menu", [c.label for c in page.children])
        cabinet = TournamentCabinet(101, 80)
        self.assertIn("Tournament Menu", [c.label for c in cabinet.children])
        self.assertIn("Main Menu", [c.label for c in cabinet.children])
        self.assertIn("Trophy Cabinet", [c.label for c in TournamentPanel().children])
        self.assertIn("Trophy Cabinet", [c.label for c in TournamentHub(101, 80).children])
        self.assertGreater(len(cabinet.make_embed().fields), 0)

    def test_autocomplete_respects_discord_limit_and_finds_tournament_titles(self):
        async def check():
            matches = await title_autocomplete(None, "")
            self.assertLessEqual(len(matches), 25)
            matches = await title_autocomplete(None, "King of")
            self.assertTrue(any(c.value == "king_of_the_lists" for c in matches))
        asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
