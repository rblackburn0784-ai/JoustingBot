"""v2.9.7 Grand Circuit: integrity, league formats, Houses and archive tests."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import discord

from services import circuit, tournaments, records, tournament_awards
from services.storage import save_json
from cogs.tournament import TournamentHub, TournamentPanel
from cogs.circuit import CircuitHub, CircuitPage, HousePage


UTC = timezone.utc
NOW = datetime(2026, 11, 18, 16, 30, tzinfo=UTC)


class CircuitFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        folder = Path(self.temp.name)
        self.patches = [
            patch.object(tournaments, "PATH", str(folder / "tournaments.json")),
            patch.object(records, "HISTORY_PATH", str(folder / "matches.json")),
            patch.object(circuit, "PATH", str(folder / "houses.json")),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def finish(self, *, format="single_elimination", size=4,
               guild=77, name="King's Day") -> tuple[dict, list[dict]]:
        event = tournaments.create(guild, 99, name, size, format=format)
        for uid in range(101, 101 + size):
            tournaments.join(guild, uid)
        tournament = tournaments.start(guild)
        entries = []
        history = records.load_history()
        for _ in range(sum(len(r) for r in tournament["rounds"])):
            pairing = tournaments.reserve_next(guild)["match"]
            a, b = pairing["a"], pairing["b"]
            row = {
                "id": pairing["id"], "timestamp": NOW.isoformat(),
                "guild_id": guild, "mode": "challenge",
                "tournament_id": event["id"], "arena_key": pairing["arena_key"],
                "seed": pairing["seed"],
                "a": {"user_id": a, "score": 3, "knight": f"Knight {a}",
                      "house_id": circuit.house_for(guild, a)},
                "b": {"user_id": b, "score": 0, "knight": f"Knight {b}",
                      "house_id": circuit.house_for(guild, b)},
                "passes": [],
            }
            history["matches"].append(row)
            save_json(records.HISTORY_PATH, history)
            tournaments.complete_match(guild, event["id"], pairing["id"], a,
                                       pairing["id"])
            entries.append(row)
        return tournaments.recent(guild, 1)[0], entries


class TournamentExpansionTests(CircuitFixture):
    def test_original_knockout_still_has_three_matches_and_stable_seed(self):
        event, entries = self.finish()
        self.assertEqual(event["format"], "single_elimination")
        self.assertEqual(len(entries), 3)
        self.assertEqual(len(event["rounds"]), 2)
        self.assertEqual(event["status"], "completed")
        self.assertEqual(len({e["id"] for e in entries}), 3)
        self.assertTrue(event["champion"] in event["entrants"])

    def test_four_rider_round_robin_finishes_six_fixtures(self):
        event, entries = self.finish(format="round_robin")
        self.assertEqual(len(entries), 6)
        self.assertEqual(len(event["rounds"]), 6)
        self.assertEqual(event["champion"], event["standings"][0]["user_id"])
        self.assertEqual(sum(row["wins"] for row in event["standings"]), 6)
        self.assertEqual(len({tuple(sorted((r["a"]["user_id"], r["b"]["user_id"])))
                              for r in entries}), 6)
        winner = event["champion"]
        self.assertEqual(tournament_awards.tournament_stats(77, winner)["championships"], 1)
        # A league's final scheduled fixture is NOT a knockout "final".
        self.assertEqual(sum(tournament_awards.tournament_stats(77, uid)["finals"]
                             for uid in event["entrants"]), 0)

    def test_eight_rider_round_robin_has_28_recoverable_matches(self):
        event, rows = self.finish(format="round_robin", size=8)
        self.assertEqual(len(rows), 28)
        self.assertEqual(event["status"], "completed")
        self.assertEqual(event["standings"][0]["wins"], max(
            r["wins"] for r in event["standings"]))

    def test_ranked_seeding_uses_verified_guild_history(self):
        historical = []
        for number, uid in enumerate((101, 101, 101, 102, 102, 103), 1):
            historical.append({
                "id": f"history-{number}", "guild_id": 77, "mode": "challenge",
                "a": {"user_id": uid, "score": 3},
                "b": {"user_id": 999, "score": 0},
                "passes": [],
            })
        save_json(records.HISTORY_PATH, {"matches": historical})
        event = tournaments.create(77, 5, "Ranked Lists", 4, seeding="ranked")
        for uid in (104, 103, 102, 101):
            tournaments.join(77, uid)
        started = tournaments.start(77)
        self.assertEqual(started["seeding_order"], [101, 102, 103, 104])
        self.assertEqual([(r["a"], r["b"]) for r in started["rounds"][0]],
                         [(101, 104), (102, 103)])
        self.assertEqual(event["seed"], started["seed"])

    def test_checkin_schedule_and_withdrawal_are_enforced(self):
        future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        item = tournaments.create(77, 5, "Scheduled Lists", 4,
                                  scheduled_at=future, require_checkin=True)
        for uid in (101, 102, 103, 104):
            tournaments.join(77, uid)
        with self.assertRaisesRegex(tournaments.TournamentError, "check in"):
            tournaments.start(77)
        tournaments.check_in(77, 101)
        with self.assertRaisesRegex(tournaments.TournamentError, "already checked"):
            tournaments.check_in(77, 101)
        for uid in (102, 103, 104):
            tournaments.check_in(77, uid)
        with self.assertRaisesRegex(tournaments.TournamentError, "scheduled"):
            tournaments.start(77)
        tournaments.leave(77, 104)
        self.assertNotIn(104, tournaments.current(77)["checked_in"])
        tournaments.join(77, 104)
        tournaments.check_in(77, 104)
        db = tournaments.load_db()
        db["guilds"]["77"]["active"]["scheduled_at"] = (
            datetime.now(UTC) - timedelta(seconds=2)).isoformat()
        save_json(tournaments.PATH, db)
        ready = tournaments.start(77)
        self.assertEqual(ready["status"], "running")
        with self.assertRaisesRegex(tournaments.TournamentError, "only during"):
            tournaments.leave(77, 101)

    def test_invalid_formats_and_naive_schedule_fail_before_save(self):
        with self.assertRaises(tournaments.TournamentError):
            tournaments.create(77, 5, "Invalid Format", 4, format="anything")
        with self.assertRaises(tournaments.TournamentError):
            tournaments.create(77, 5, "Naive Date", 4, scheduled_at="2026-12-01T20:00")
        with self.assertRaises(tournaments.TournamentError):
            tournaments.create(77, 5, "Invalid Seeding", 4,
                               format="round_robin", seeding="ranked")
        self.assertIsNone(tournaments.current(77))


class SeasonAndArchiveTests(CircuitFixture):
    def test_season_calendar_rolls_without_scheduled_tasks(self):
        self.assertIsNone(circuit.season_number(NOW - timedelta(days=1)))
        self.assertEqual(circuit.season_number(NOW), 1)
        self.assertEqual(circuit.season_number(
            circuit.SEASON_START + timedelta(days=42)), 2)
        self.assertEqual(circuit.season_window(1)["end"],
                         circuit.season_window(2)["start"])
        with self.assertRaises(circuit.CircuitError):
            circuit.season_window(0)

    def test_verification_prevents_duplicate_phantom_points_and_crowns(self):
        event, entries = self.finish()
        champion = event["champion"]
        data = circuit.seasonal_standings(77, season=1)
        row = next(row for row in data["standings"] if row["user_id"] == champion)
        self.assertEqual(row["championships"], 1)
        self.assertEqual(row["points"], 10 + row["played"]*2 + row["wins"]*5)
        self.assertEqual(data["verified_matches"], 3)
        journal = records.load_history()
        journal["matches"].append(dict(entries[0]))  # duplicate match ID
        journal["matches"].append({
            "id": "forgery", "timestamp": NOW.isoformat(), "guild_id": 77,
            "mode": "challenge", "tournament_id": event["id"],
            "a": {"user_id": 999, "score": 99}, "b": {"user_id": 998, "score": 0},
            "passes": [],
        })
        save_json(records.HISTORY_PATH, journal)
        self.assertEqual(circuit.seasonal_standings(77, 1), data)
        self.assertEqual(len(circuit.champions_hall(77)), 1)
        self.assertEqual(len(circuit.chronicle(77)), 1)
        self.assertEqual(circuit.seasonal_standings(78, 1)["verified_matches"], 0)

    def test_incomplete_or_forged_bracket_is_not_archived(self):
        event, rows = self.finish()
        journal = records.load_history()
        journal["matches"][-1]["tournament_id"] = "wrong"
        save_json(records.HISTORY_PATH, journal)
        self.assertFalse(circuit.champions_hall(77))
        standings = circuit.seasonal_standings(77, 1)
        self.assertTrue(all(r["championships"] == 0 for r in standings["standings"]))

    def test_arena_qualification_needs_three_verified_wins(self):
        for i in range(3):
            self.finish(name=f"Arena Cup {i}")
        # Force observed arena into a common arena for a deterministic fixture.
        data = tournaments.load_db()
        history = records.load_history()
        for event in data["guilds"]["77"]["history"]:
            for rnd in event["rounds"]:
                for row in rnd:
                    row["arena_key"] = "royal_lists"
        for match in history["matches"]:
            match["arena_key"] = "royal_lists"
        save_json(tournaments.PATH, data)
        save_json(records.HISTORY_PATH, history)
        boards = circuit.arena_champions(77, 1)["arenas"]["royal_lists"]
        self.assertTrue(all(r["wins"] >= 3 for r in boards))
        self.assertEqual(circuit.arena_champions(78, 1)["arenas"]["royal_lists"], [])


class HouseIntegrityTests(CircuitFixture):
    def test_house_ownership_transfer_and_guild_isolation(self):
        first = circuit.create_house(77, 101, "Silver Lances")
        second = circuit.create_house(77, 103, "Black Falcons")
        self.assertNotEqual(first["id"], second["id"])
        circuit.join_house(77, 102, first["id"])
        self.assertEqual(circuit.house_for(77, 102), first["id"])
        self.assertIsNone(circuit.house_for(78, 102))
        with self.assertRaises(circuit.CircuitError):
            circuit.create_house(77, 101, "Another House")
        with self.assertRaises(circuit.CircuitError):
            circuit.leave_house(77, 101)
        with self.assertRaises(circuit.CircuitError):
            circuit.transfer_captain(77, 102, 101)
        circuit.transfer_captain(77, 101, 102)
        circuit.leave_house(77, 101)
        self.assertIsNone(circuit.house_for(77, 101))
        self.assertEqual(circuit.guild_houses(77)[first["id"]]["captain"], 102)
        self.assertEqual(circuit.guild_houses(77)[second["id"]]["captain"], 103)

    def test_roster_is_snapshot_derived_and_factions_do_not_rewrite_history(self):
        red = circuit.create_house(77, 101, "Scarlet Keep")
        blue = circuit.create_house(77, 102, "Blue Banner")
        circuit.join_house(77, 103, red["id"])
        circuit.join_house(77, 104, blue["id"])
        self.finish(name="Rivals Cup")
        before = circuit.house_standings(77, 1)
        self.assertGreater(sum(x["points"] for x in before), 0)
        circuit.leave_house(77, 103, now=NOW)
        circuit.join_house(77, 103, blue["id"], now=NOW + timedelta(hours=25))
        self.assertEqual(before, circuit.house_standings(77, 1))
        self.assertEqual(circuit.house_standings(78, 1), [])

    def test_match_recorder_snapshots_own_houses_safely(self):
        red = circuit.create_house(77, 101, "Red House")
        blue = circuit.create_house(77, 102, "Blue House")
        fa = SimpleNamespace(user_id=101, lance_key="lance_ash", armour_key="armour_mail",
                             barding_key="barding_none")
        fb = SimpleNamespace(user_id=102, lance_key="lance_ash", armour_key="armour_mail",
                             barding_key="barding_none")
        obj = SimpleNamespace(
            guild_id=77, arena_key="royal_lists", mode="challenge",
            fighter_a=fa, fighter_b=fb,
            knight_a=SimpleNamespace(name="Sir Red"), knight_b=SimpleNamespace(name="Sir Blue"),
            horse_a=SimpleNamespace(horse_id="a", name="Mount A", stats={}, breed="courser"),
            horse_b=SimpleNamespace(horse_id="b", name="Mount B", stats={}, breed="courser"),
        )
        outcome = SimpleNamespace(seed=4242, arena_name="Royal Lists",
                                  passes=[], score_a=2, score_b=0)
        with patch("services.injuries.make_events", return_value=[]):
            records.record_match(obj, outcome)
        entry = records.load_history()["matches"][0]
        self.assertEqual(entry["a"]["house_id"], red["id"])
        self.assertEqual(entry["b"]["house_id"], blue["id"])


class CircuitUIContractTests(CircuitFixture):
    def test_all_pages_keep_single_message_private_navigation(self):
        pages = (
            CircuitHub(101, None), CircuitPage(101, None),
            HousePage(101, None), TournamentHub(101, None),
        )
        for page in pages:
            self.assertTrue(any(getattr(c, "label", "") == "Main Menu"
                                for c in page.children))
            self.assertLessEqual(len(page.children), 25)
            self.assertLessEqual(len(page.make_embed().description or ""), 4096)
            for row in range(5):
                children = [c for c in page.children if c.row == row]
                self.assertLessEqual(len(children), 5)
                if any(isinstance(c, discord.ui.Select) for c in children):
                    self.assertEqual(len(children), 1)
        public = TournamentPanel()
        self.assertTrue(any(c.label == "Check In" for c in public.children))
        self.assertTrue(any(c.label == "Leave Tournament" for c in public.children))
        self.assertTrue(all(c.custom_id for c in public.children))





class QualificationAndMissionTests(CircuitFixture):
    def test_circuit_final_is_qualified_ranked_and_honorary(self):
        with patch("services.circuit.seasonal_standings", return_value={
            "standings": [
                {"user_id": uid, "points": score}
                for uid, score in ((105, 20), (103, 18), (101, 16), (104, 14),
                                   (102, 2), (106, 0))
            ]
        }):
            event = tournaments.create(77, 9, "Season Final", 4,
                                       seeding="ranked", championship=True)
        self.assertTrue(event["championship"])
        self.assertEqual(event["qualified_entrants"], [105, 103, 101, 104])
        self.assertEqual(event["season"], 1)
        with self.assertRaisesRegex(tournaments.TournamentError, "qualified"):
            tournaments.join(77, 102)
        for uid in (104, 101, 105, 103):
            tournaments.join(77, uid)
        result = tournaments.start(77)
        self.assertEqual(result["seeding_order"], [105, 103, 101, 104])
        self.assertEqual([(m["a"], m["b"]) for m in result["rounds"][0]],
                         [(105, 104), (103, 101)])

    def test_no_circuit_final_without_previous_verified_qualification(self):
        with self.assertRaisesRegex(tournaments.TournamentError, "contenders"):
            tournaments.create(77, 9, "Too Early", 4,
                               seeding="ranked", championship=True)
        self.assertIsNone(tournaments.current(77))

    def test_house_rivalry_missions_are_journal_derived(self):
        first = circuit.create_house(77, 101, "House North")
        second = circuit.create_house(77, 103, "House South")
        circuit.join_house(77, 102, first["id"])
        circuit.join_house(77, 104, second["id"])
        self.finish(name="Rival League", format="round_robin")
        a = circuit.house_missions(77, first["id"], now=NOW)
        b = circuit.house_missions(77, second["id"], now=NOW)
        self.assertTrue(a["rival_bouts"]["complete"])
        self.assertTrue(b["rival_bouts"]["complete"])
        self.assertEqual(a, circuit.house_missions(77, first["id"], now=NOW))
        self.assertEqual(circuit.house_missions(77, first["id"],
                         now=NOW + timedelta(days=1))["rival_bouts"]["progress"], 0)
        self.assertEqual(circuit.house_missions(78, first["id"],
                         now=NOW)["rival_bouts"]["progress"], 0)


if __name__ == "__main__":
    unittest.main()
