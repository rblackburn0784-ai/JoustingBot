"""v0.8.1a risk, treatment-tier, relief and compatibility tests."""
from __future__ import annotations
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from services import injuries as inj
from services import progression as prog


def match(mid: str, arena="royal_lists", category="unhorsing", now=None):
    now = now or datetime.now(timezone.utc)
    return {
        "id": mid, "timestamp": now.isoformat(), "guild_id": 33, "mode": "challenge",
        "arena_key": arena,
        "a": {"user_id": 7, "knight": "Sir A", "score": 3, "horse_id": "ha",
              "horse": "Sable", "horse_breed": "Destrier",
              "horse_stats": {"courage": 9, "obedience": 8},
              "gear": {"lance": "lance_heavy", "armour": "armour_full", "barding": "barding_steel"}},
        "b": {"user_id": 8, "knight": "Sir B", "score": 0, "horse_id": "hb",
              "horse": "Comet", "horse_breed": "Courser",
              "horse_stats": {"courage": 3, "obedience": 3},
              "gear": {"lance": "lance_ash", "armour": "armour_light", "barding": "barding_runner"}},
        "passes": [{"category": category, "points_a": 3, "points_b": 0,
                    "result": "Sir A struck hard", "notes": []}],
    }


class InjuryRiskTests(unittest.TestCase):
    def test_arena_armour_barding_lance_and_breed_alter_risk(self):
        m = match("risk")
        old = inj.risk_profile(m, "b", "a", "unhorsing")
        self.assertLess(old["chance"], 42)
        m["arena_key"] = "frozen_ground"
        self.assertGreater(inj.risk_profile(m, "b", "a", "unhorsing")["chance"], old["chance"])
        m["arena_key"] = "royal_lists"
        m["b"]["gear"]["armour"] = "armour_full"
        self.assertLess(inj.risk_profile(m, "b", "a", "unhorsing")["chance"], old["chance"])
        m["b"]["gear"]["armour"] = "armour_light"
        m["b"]["gear"]["barding"] = "barding_steel"
        self.assertLess(inj.risk_profile(m, "b", "a", "unhorsing")["chance"], old["chance"])
        m["b"]["gear"]["barding"] = "barding_runner"
        m["a"]["gear"]["lance"] = "lance_tournament"
        self.assertLess(inj.risk_profile(m, "b", "a", "unhorsing")["chance"], old["chance"])
        m["a"]["gear"]["lance"] = "lance_heavy"
        m["b"]["horse_breed"] = "Palfrey"
        self.assertLess(inj.risk_profile(m, "b", "a", "unhorsing")["chance"], old["chance"])
        m["b"]["horse_breed"] = "Courser"
        m["b"]["horse_stats"] = {"courage": 9, "obedience": 9}
        self.assertLess(inj.risk_profile(m, "b", "a", "unhorsing")["chance"], old["chance"])

    def test_risk_is_bounded_and_rider_injured_modifier(self):
        m = match("bounds", arena="frozen_ground")
        base = inj.risk_profile(m, "b", "a", "unhorsing")
        m["b"]["already_injured"] = True
        danger = inj.risk_profile(m, "b", "a", "unhorsing")
        self.assertGreaterEqual(danger["chance"], base["chance"])
        self.assertGreaterEqual(danger["chance"], inj.MIN_RISK)
        self.assertLessEqual(danger["chance"], inj.MAX_RISK)

    def test_weighted_injury_categories_by_arena(self):
        def counts(arena):
            selections = []
            for r in range(100):
                with patch.object(inj, "roll", return_value=r):
                    selections.append(inj._choose_kind("m", "b", arena))
            return selections
        self.assertGreater(counts("frozen_ground").count("twisted_knee"),
                           counts("royal_lists").count("twisted_knee"))
        self.assertGreater(counts("wind_swept").count("jarred_wrist"),
                           counts("muddy_field").count("jarred_wrist"))

    def test_match_snapshot_has_explainable_risk_and_timing(self):
        m = match("snapshot", arena="frozen_ground")
        with patch.object(inj, "roll", return_value=0):
            first = inj.make_events(m)
            self.assertEqual(first, inj.make_events(m))
        self.assertEqual(len(first), 1)
        self.assertIn("risk_modifiers", first[0])
        self.assertIn("severity", first[0])
        self.assertGreaterEqual(first[0]["risk"], 2)
        self.assertLessEqual(first[0]["risk"], 42)
        self.assertIn(first[0]["key"], inj.KINDS)


class TreatmentTests(unittest.TestCase):
    def prepare(self, now=None, wound_hours=46):
        now = now or datetime.now(timezone.utc)
        history = {"matches": [match(f"win{i}", now=now) for i in range(8)]}
        injury_match = history["matches"][0]
        injury_match["injuries"] = [{
            "id": "win0:b", "user_id": 8, "name": "Jarred Wrist",
            "key": "jarred_wrist", "stat": "control",
            "started_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=wound_hours)).isoformat()
        }]
        return now, history

    def test_three_tiers_have_expected_risk_reward_values(self):
        self.assertEqual(set(inj.TREATMENTS), {"faith_healer", "shady_doctor", "private_doctor"})
        costs = [inj.TREATMENTS[k]["cost"] for k in inj.TREATMENTS]
        speed = [inj.TREATMENTS[k]["hours"] for k in inj.TREATMENTS]
        fail = [inj.TREATMENTS[k]["failure"] for k in inj.TREATMENTS]
        help_chance = [inj.TREATMENTS[k]["support"] for k in inj.TREATMENTS]
        self.assertEqual(costs, sorted(costs))
        self.assertEqual(speed, sorted(speed))
        self.assertEqual(fail, sorted(fail, reverse=True))
        self.assertEqual(help_chance, sorted(help_chance))

    def test_failed_treatment_spends_gold_without_healing(self):
        now, history = self.prepare()
        with tempfile.TemporaryDirectory() as td, \
             patch.object(prog, "PATH", str(Path(td) / "progression.json")), \
             patch.object(inj, "load_history", return_value=history), \
             patch.object(prog, "load_history", return_value=history), \
             patch.object(inj, "_treatment_roll", return_value=0):
            before = prog.wallet(33, 8)
            after, outcome = inj.heal(33, 8, "win0:b", now=now, provider="faith_healer")
            self.assertFalse(outcome["success"])
            self.assertEqual(outcome["hours_reduced"], 0)
            self.assertEqual(after, before - 12)
            self.assertAlmostEqual(inj.active(33, 8, now=now)[0]["remaining_seconds"],
                                   46*3600, delta=1)

    def test_expensive_treatment_never_heals_instantly(self):
        now, history = self.prepare(wound_hours=26)
        with tempfile.TemporaryDirectory() as td, \
             patch.object(prog, "PATH", str(Path(td) / "progression.json")), \
             patch.object(inj, "load_history", return_value=history), \
             patch.object(prog, "load_history", return_value=history), \
             patch.object(inj, "_treatment_roll", return_value=99):
            _, report = inj.heal(33, 8, "win0:b", now=now, provider="private_doctor")
            self.assertTrue(report["success"])
            self.assertAlmostEqual(report["hours_reduced"], 23, delta=1/60)
            remaining = inj.active(33, 8, now=now)
            self.assertEqual(len(remaining), 1)
            self.assertAlmostEqual(remaining[0]["remaining_seconds"], 3*3600, delta=1)

    def test_support_can_reduce_one_penalty_for_exactly_one_completed_bout(self):
        now, history = self.prepare()
        with tempfile.TemporaryDirectory() as td, \
             patch.object(prog, "PATH", str(Path(td) / "progression.json")), \
             patch.object(inj, "load_history", return_value=history), \
             patch.object(prog, "load_history", return_value=history), \
             patch.object(inj, "_treatment_roll", side_effect=lambda token, salt:
                          99 if salt == "success" else 0):
            _, report = inj.heal(33, 8, "win0:b", now=now, provider="faith_healer")
            self.assertTrue(report["support_ready"])
            support = inj.support_for_next_bout(33, 8, history=history, now=now)
            self.assertIsNotNone(support)
            base = {"control": 6, "strength": 6}
            regular = inj.apply_penalty(base, 33, 8, history=history, now=now)
            helped = inj.apply_penalty(base, 33, 8, history=history, now=now, relief=True)
            self.assertEqual(regular["control"], 5)
            self.assertEqual(helped, base)
            history["matches"].append({
                **match("used", now=now),
                "b": {**match("used", now=now)["b"], "support_token": support["id"]}
            })
            self.assertIsNone(inj.support_for_next_bout(33, 8, history=history, now=now))
            self.assertIsNone(inj.support_for_next_bout(34, 8, history=history, now=now))

    def test_injury_ward_has_provider_dropdown_home_and_treatment_button(self):
        from cogs.menu import InjuryPage
        import discord
        wound = {
            "id": "m:b", "name": "Bruised Ribs", "stat": "endurance",
            "remaining_seconds": 32 * 3600, "severity": "moderate",
        }
        with patch.object(inj, "active", return_value=[wound]):
            page = InjuryPage(8, 33)
        selects = [c for c in page.children if isinstance(c, discord.ui.Select)]
        labels = [c.label for c in page.children if isinstance(c, discord.ui.Button)]
        self.assertEqual(len(selects), 2)
        self.assertEqual(len(selects[1].options), 3)
        self.assertIn("Treat Selected", labels)
        self.assertIn("Main Menu", labels)
        self.assertEqual({x.row for x in selects}, {0, 1})

    def test_multiple_treatments_do_not_stack_support_across_jousts(self):
        now, history = self.prepare(wound_hours=72)
        with tempfile.TemporaryDirectory() as td, \
             patch.object(prog, "PATH", str(Path(td) / "progression.json")), \
             patch.object(inj, "load_history", return_value=history), \
             patch.object(prog, "load_history", return_value=history), \
             patch.object(inj, "_treatment_roll", side_effect=lambda token, salt:
                          99 if salt == "success" else 0):
            first_balance, first = inj.heal(
                33, 8, "win0:b", now=now, provider="faith_healer"
            )
            second_balance, second = inj.heal(
                33, 8, "win0:b", now=now, provider="faith_healer"
            )
            self.assertTrue(first["support_ready"])
            self.assertTrue(second["support_ready"])
            self.assertEqual(first_balance - second_balance, 12)
            self.assertIsNotNone(inj.support_for_next_bout(33, 8, history=history, now=now))
            # Declined challenges, or other guilds' matches, do not consume aid.
            history["matches"].append({
                **match("declined", now=now + timedelta(minutes=1)),
                "mode": "declined"
            })
            self.assertIsNotNone(inj.support_for_next_bout(
                33, 8, history=history, now=now + timedelta(minutes=2)))
            # Once a new accepted joust has completed, *all* earlier treatment
            # boosts expire, including older tokens that were not selected.
            history["matches"].append(match("next_joust", now=now + timedelta(minutes=3)))
            self.assertIsNone(inj.support_for_next_bout(
                33, 8, history=history, now=now + timedelta(minutes=4)))

    def test_support_expires_after_one_day_without_a_match(self):
        now, history = self.prepare()
        with tempfile.TemporaryDirectory() as td, \
             patch.object(prog, "PATH", str(Path(td) / "progression.json")), \
             patch.object(inj, "load_history", return_value=history), \
             patch.object(prog, "load_history", return_value=history), \
             patch.object(inj, "_treatment_roll", side_effect=lambda token, salt:
                          99 if salt == "success" else 0):
            inj.heal(33, 8, "win0:b", now=now, provider="faith_healer")
            self.assertIsNone(inj.support_for_next_bout(
                33, 8, history=history, now=now+timedelta(hours=25)))


if __name__ == "__main__":
    unittest.main()
