"""v0.8.1 injury recovery, deterministic events, balance, and gold spend tests."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from services import injuries as inj
from services import progression as pr
from services import records as rec


def fixture(mid="m1", *, guild=7, mode="challenge", started=None,
            category="unhorsing", points_a=3, points_b=0):
    timestamp = (started or datetime.now(timezone.utc)).isoformat()
    return {
        "id": mid, "timestamp": timestamp, "guild_id": guild,
        "mode": mode, "arena_key": "royal_lists",
        "a": {"user_id": 101, "score": 3, "horse_id": "ha", "horse": "Swift", "knight": "Arthur"},
        "b": {"user_id": 102, "score": 0, "horse_id": "hb", "horse": "Swift", "knight": "Basil"},
        "passes": [{"category": category, "points_a": points_a, "points_b": points_b,
                    "result": category, "notes": []}],
    }


class InjuryTests(unittest.TestCase):
    def test_injuries_are_deterministic_and_one_per_victim(self):
        m = fixture()
        with patch.object(inj, "roll", side_effect=lambda mid, side, salt: 0):
            first = inj.make_events(m)
            self.assertEqual(first, inj.make_events(m))
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["user_id"], 102)
        self.assertEqual(first[0]["stat"], "endurance")
        self.assertEqual((inj.utc(first[0]["expires_at"]) -
                          inj.utc(first[0]["started_at"])).total_seconds(), 19*3600)

    def test_no_injury_for_instant_test_or_uncharged_pass(self):
        m = fixture(mode="instant")
        with patch.object(inj, "roll", return_value=0):
            self.assertEqual(inj.make_events(m), [])
            m["mode"] = "challenge"
            m["passes"][0]["category"] = "clean_miss"
            self.assertEqual(inj.make_events(m), [])
            m["guild_id"] = None
            self.assertEqual(inj.make_events(m), [])

    def test_legacy_records_are_not_backfilled(self):
        history = {"matches": [fixture()]}
        self.assertEqual(inj.active(7, 102, history, {"guilds": {}}), [])

    def test_max_debuff_two_points_and_no_stacking_same_stat(self):
        now = datetime.now(timezone.utc)
        many = []
        kinds = ["bruised_ribs", "wrenched_shoulder", "jarred_wrist", "bruised_ribs"]
        for i, kind in enumerate(kinds):
            m = fixture(str(i), started=now)
            label, stat, hours = inj.KINDS[kind]
            m["injuries"] = [{
                "id": f"{i}:b", "user_id": 102, "key": kind, "name": label,
                "stat": stat, "started_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=hours)).isoformat(),
            }]
            many.append(m)
        history = {"matches": many}
        original = {"strength": 6, "control": 6, "endurance": 6, "agility": 6}
        affected = inj.apply_penalty(original, 7, 102, history, {"guilds": {}}, now)
        self.assertEqual(sum(original.values()) - sum(affected.values()), 2)
        self.assertTrue(all(0 <= original[k] - v <= 1 for k, v in affected.items()))
        self.assertEqual(original["agility"], affected["agility"])
        self.assertEqual(original["strength"], 6)

    def test_natural_recovery_passes_even_when_bot_not_running(self):
        start = datetime.now(timezone.utc) - timedelta(hours=25)
        m = fixture(started=start)
        with patch.object(inj, "roll", return_value=0):
            m["injuries"] = inj.make_events(m)
        history = {"matches": [m]}
        self.assertEqual(inj.active(7, 102, history, {"guilds": {}}), [])

    def test_healing_spends_gold_without_instant_recovery(self):
        start = datetime.now(timezone.utc)
        event_match = fixture("injured", started=start)
        with patch.object(inj, "roll", return_value=0):
            event_match["injuries"] = inj.make_events(event_match)
        history = {"matches": [event_match, fixture("second", started=start)]}
        injury_id = event_match["injuries"][0]["id"]
        with tempfile.TemporaryDirectory() as td:
            with patch.object(pr, "PATH", str(Path(td) / "progression.json")), \
                 patch.object(inj, "load_history", return_value=history), \
                 patch.object(pr, "load_history", return_value=history), \
                 patch.object(inj, "_treatment_roll", return_value=99):
                self.assertEqual(pr.wallet(7, 102), 24)
                with self.assertRaisesRegex(ValueError, "27 gold"):
                    inj.heal(7, 102, injury_id, now=start)
                history["matches"].append(fixture("third", started=start))
                self.assertEqual(pr.wallet(7, 102), 36)
                gold, response = inj.heal(7, 102, injury_id, now=start)
                self.assertTrue(response["success"])
                self.assertEqual(gold, 9)
                self.assertEqual(pr.wallet(7, 102), 9)
                wounded = inj.active(7, 102, history, now=start)
                self.assertEqual(len(wounded), 1)
                self.assertAlmostEqual(wounded[0]["remaining_seconds"], 3 * 3600, delta=1)
                with self.assertRaisesRegex(ValueError, "nearly complete"):
                    inj.heal(7, 102, injury_id, now=start)
                self.assertEqual(pr.wallet(7, 101), 60)

    def test_record_match_saves_exactly_one_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(rec, "HISTORY_PATH", str(Path(td) / "matches.json")), \
                 patch.object(inj, "roll", return_value=0):
                fighter_a = SimpleNamespace(user_id=101, lance_key="lance_ash",
                                            armour_key="armour_mail", barding_key="barding_none")
                fighter_b = SimpleNamespace(user_id=102, lance_key="lance_ash",
                                            armour_key="armour_mail", barding_key="barding_none")
                prepared = SimpleNamespace(
                    guild_id=7, mode="challenge", arena_key="royal_lists",
                    fighter_a=fighter_a, fighter_b=fighter_b,
                    knight_a=SimpleNamespace(name="Arthur"),
                    knight_b=SimpleNamespace(name="Basil"),
                    horse_a=SimpleNamespace(name="Swift", horse_id="ha"),
                    horse_b=SimpleNamespace(name="Swift", horse_id="hb"))
                result = SimpleNamespace(
                    arena_name="Royal Lists", seed=42, score_a=3, score_b=0,
                    passes=[SimpleNamespace(pass_no=1, category="unhorsing",
                          points_a=3, points_b=0, result="Arthur: unhorsing", notes=[])])
                match_id = rec.record_match(prepared, result)
                saved = rec.load_history()["matches"]
                self.assertEqual(len(saved), 1)
                self.assertEqual(saved[0]["id"], match_id)
                self.assertEqual(saved[0]["injuries"][0]["user_id"], 102)
                self.assertEqual(len(saved[0]["injuries"]), 1)


if __name__ == "__main__":
    unittest.main()
