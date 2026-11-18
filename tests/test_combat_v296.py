"""v2.9.6 — tactical counters, adaptive NPCs, training safety and analysis."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import patch
import discord

from services import tactics, training, drills, combat_analysis, evolution
from services.combat import Fighter, run_single_match
from cogs.tactic_ui import AdvancedEditor, TacticEditor
from tools.simulate_balance_v296 import sweep, PLANS

NOW = datetime(2026, 11, 18, 14, 0, tzinfo=timezone.utc)


def profile():
    return {
        "knights": {
            "5": {"user_id": 5, "name": "Sir Test",
                  "bound_horse_id": "h5",
                  "stats": {"strength": 4, "control": 4, "endurance": 3,
                            "agility": 3, "resolve": 3, "tactics": 3}}
        }
    }


def horse():
    return {
        "horses": {"h5": {
            "horse_id": "h5", "owner_id": 5, "name": "Comet",
            "breed": "courser",
            "stats": {"speed": 5, "stamina": 5, "power": 5,
                      "obedience": 5, "courage": 4}
        }}
    }


class TacticalCounterTests(TestCase):
    def test_defaults_and_invalid_choices(self):
        default = tactics.TacticPlan()
        self.assertEqual(default.shield_guard, "square")
        self.assertEqual(default.charge_intensity, "balanced")
        self.assertEqual(default.lance_control, "balanced")
        self.assertFalse(tactics.advanced_active(default))
        for field, value in (
            ("shield_guard", "invincible"),
            ("charge_intensity", "impossible"),
            ("lance_control", "laser"),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                tactics.TacticPlan(**{**default.as_dict(), field: value})

    def test_advanced_tradeoffs_and_counterplay(self):
        base = tactics.effects(tactics.TacticPlan(), pass_no=1, fatigue=0,
                               horse_stats={"stamina": 5, "courage": 5, "obedience": 5})
        careful = tactics.effects(tactics.TacticPlan(
            charge_intensity="measured", lance_control="precise"),
            pass_no=1, fatigue=0,
            horse_stats={"stamina": 5, "courage": 5, "obedience": 5})
        heavy = tactics.effects(tactics.TacticPlan(
            charge_intensity="full", lance_control="forceful"),
            pass_no=1, fatigue=0,
            horse_stats={"stamina": 5, "courage": 5, "obedience": 5})
        self.assertGreater(careful.alignment, base.alignment)
        self.assertLess(careful.charge, base.charge)
        self.assertGreater(heavy.charge, base.charge)
        self.assertLess(heavy.alignment, base.alignment)
        self.assertGreater(heavy.fatigue_gain, base.fatigue_gain)
        a = tactics.TacticPlan(target="rider")
        b = tactics.TacticPlan(shield_guard="high")
        self.assertLess(tactics.counterplay(a, b)[1], 0)
        self.assertGreater(tactics.counterplay(a, b)[2], 0)
        self.assertGreater(tactics.counterplay(a, b)[2],
                           tactics.counterplay(a, b, defender_wear=2)[2])

    def test_replay_determinism_in_all_arenas_with_advanced(self):
        stats = {"strength": 6, "control": 6, "endurance": 6,
                 "agility": 5, "resolve": 5, "tactics": 5}
        mount = {"speed": 6, "stamina": 5, "power": 5,
                 "obedience": 6, "courage": 5}
        a = Fighter(5, "Red", "Fire", stats, mount,
                    "lance_ash", "armour_mail", "barding_none")
        b = Fighter(6, "Blue", "Ice", stats, mount,
                    "lance_ash", "armour_mail", "barding_none")
        pa = tactics.TacticPlan("aggressive", "rider", "reckless_charge",
                                "high", "full", "forceful")
        pb = tactics.TacticPlan("cautious", "lance", "shield_brace",
                                "low", "measured", "precise")
        from services.arenas import ARENAS
        for arena in ARENAS:
            first = run_single_match(a, b, arena, seed=4794,
                                     tactics_a=pa, tactics_b=pb)
            second = run_single_match(a, b, arena, seed=4794,
                                      tactics_a=pa, tactics_b=pb)
            self.assertEqual(asdict(first), asdict(second))
            self.assertTrue(any("guard" in " ".join(p.notes).lower()
                                for p in first.passes))

    def test_small_balance_smoke_no_complete_winlock(self):
        stats = sweep(seeds=10)
        self.assertEqual(len(stats), len(PLANS) - 1)
        for name, row in stats.items():
            self.assertEqual(row["matches"], 120)
            self.assertGreater(row["win_share"], 0.02, name)
            self.assertLess(row["win_share"], 0.98, name)


class AdaptiveNPCTests(TestCase):
    def test_twelve_distinct_personalities_and_adaptation_requires_history(self):
        self.assertEqual(len(training.NPC_ADVANCED), 12)
        from services.training import opponent
        npc = opponent("maud")
        self.assertEqual(npc.tactics.charge_intensity, "full")
        self.assertEqual(training.adaptive_tactics(
            npc, 88, 5, history={"matches": []}), npc.tactics)
        journal = {"matches": [
            {"id": f"m{i}", "mode": "training", "guild_id": 88,
             "a": {"user_id": 5, "tactics": {"target": "lance"}},
             "b": {"user_id": npc.player_id}}
            for i in range(2)
        ] + [
            {"id": "foreign", "mode": "training", "guild_id": 99,
             "a": {"user_id": 5, "tactics": {"target": "rider"}},
             "b": {"user_id": npc.player_id}}
        ]}
        self.assertEqual(training.adaptive_tactics(
            npc, 88, 5, history=journal).shield_guard, "low")
        self.assertEqual(training.adaptive_tactics(
            npc, 99, 5, history=journal), npc.tactics)


class DrillTests(TestCase):
    def test_four_drills_are_owned_guild_scoped_and_daily_limited(self):
        data = {"guilds": {}}
        with patch("cogs.knight.load_knights", return_value=profile()), \
             patch("cogs.horse.load_horses", return_value=horse()), \
             patch.object(drills, "_db", return_value=data), \
             patch.object(evolution, "_db", return_value=data), \
             patch.object(drills, "save_json") as save:
            for key in drills.DRILLS:
                result = drills.run_drill(88, 5, key, now=NOW, roll=20)
                self.assertTrue(result["success"])
                self.assertEqual(result["mastery_awarded"], 1)
                with self.assertRaisesRegex(ValueError, "completed this drill"):
                    drills.run_drill(88, 5, key, now=NOW, roll=20)
            self.assertEqual(save.call_count, 4)
            self.assertEqual(drills.drill_status(88, 5, now=NOW, data=data)["mastery"], 4)
            self.assertEqual(drills.drill_status(89, 5, now=NOW, data=data)["mastery"], 0)
            self.assertEqual(drills.drill_status(88, 5, now=NOW+timedelta(days=1),
                                                data=data)["completed"], 0)
            self.assertEqual(drills.run_drill(
                88, 5, "accuracy", now=NOW+timedelta(days=1), roll=1)["mastery_awarded"], 0)
            with self.assertRaises(ValueError):
                drills.run_drill(88, 6, "accuracy", now=NOW, roll=20)


class AnalysisTests(TestCase):
    def test_private_lookup_and_read_only_pass_summary(self):
        record = {
            "id": "real-1", "guild_id": 88, "mode": "challenge",
            "arena_key": "royal_lists", "arena_name": "Royal Lists",
            "seed": 112, "a": {"user_id": 5, "knight": "Sir Test",
                              "score": 2, "gear": {"lance": "lance_ash"},
                              "tactics": {"style": "balanced"}},
            "b": {"user_id": 6, "knight": "Sir Blue", "score": 1},
            "passes": [{
                "pass_no": 1, "category": "heavy_shield_hit",
                "points_a": 2, "points_b": 0, "margin": 9,
                "tactics_a": {"fatigue": 1, "alignment": 0, "charge": 2},
                "tactics_b": {"fatigue": 1},
                "notes": ["The shield is struck hard"],
            }],
        }
        h = {"matches": [record]}
        self.assertIsNone(combat_analysis.owned_match(99, 5, history=h))
        self.assertIsNone(combat_analysis.owned_match(88, 7, history=h))
        self.assertIsNone(combat_analysis.owned_match(88, 5,
                          match_id="unknown", history=h))
        got = combat_analysis.owned_match(88, 5, history=h)
        self.assertEqual(got["id"], "real-1")
        text = combat_analysis.breakdown(got, 5)
        self.assertIn("Victory", text["summary"])
        self.assertIn("Heavy shield impact", text["passes"][0])
        self.assertEqual(text["count"], 1)


class AdvancedPanelTests(TestCase):
    def test_both_private_screens_respect_five_discord_rows(self):
        challenge = SimpleNamespace(completed=False)
        a = TacticEditor(challenge, 5)
        b = AdvancedEditor(challenge, 5, tactics.TacticPlan(shield_guard="high"))
        for page in (a, b):
            self.assertEqual(len([x for x in page.children
                                  if isinstance(x, discord.ui.Select)]), 3)
            rows = {}
            for item in page.children:
                rows.setdefault(item.row, []).append(item)
                self.assertIn(item.row, range(5))
            for row, children in rows.items():
                if any(isinstance(x, discord.ui.Select) for x in children):
                    self.assertEqual(len(children), 1)
                else:
                    self.assertLessEqual(len(children), 5)
        self.assertTrue(any(getattr(x, "label", None) == "Advanced Setup"
                            for x in a.children))
        self.assertTrue(any(getattr(x, "label", None) == "Back to Tactics"
                            for x in b.children))



class DefensiveRebalanceTests(TestCase):
    def test_measured_low_guard_and_controlled_counterstrike(self):
        p = tactics.TacticPlan(
            style="cautious", target="lance", manoeuvre="shield_brace",
            shield_guard="low", charge_intensity="measured",
            lance_control="precise",
        )
        mount = {"stamina": 5, "obedience": 5, "courage": 5}
        actual = tactics.effects(p, pass_no=1, fatigue=0, horse_stats=mount)
        self.assertEqual(actual.charge, -3)
        high_same = tactics.TacticPlan(
            style="cautious", target="lance", manoeuvre="shield_brace",
            shield_guard="high", charge_intensity="measured",
            lance_control="precise",
        )
        high_effect = tactics.effects(high_same, pass_no=1, fatigue=0, horse_stats=mount)
        self.assertEqual(high_effect.charge, actual.charge - 2)
        self.assertGreater(actual.alignment, 0)
        self.assertGreaterEqual(actual.resistance, 3)
        # The bonus must never be granted to all-out aggression.
        wild = tactics.TacticPlan(style="aggressive", target="rider",
                                  manoeuvre="reckless_charge",
                                  shield_guard="high",
                                  charge_intensity="full", lance_control="forceful")
        self.assertNotEqual(actual.charge, tactics.effects(
            wild, pass_no=1, fatigue=0, horse_stats=mount).charge)
        high = tactics.TacticPlan(shield_guard="high")
        self.assertEqual(tactics.counterplay(wild, high)[1], -3)
        self.assertEqual(tactics.counterplay(wild, high, defender_wear=2)[2], 0)

    def test_no_legacy_change_when_advanced_controls_are_neutral(self):
        legacy = tactics.TacticPlan(style="cautious", target="lance",
                                     manoeuvre="shield_brace")
        new = tactics.TacticPlan(style="cautious", target="lance",
                                  manoeuvre="shield_brace",
                                  shield_guard="square",
                                  charge_intensity="balanced",
                                  lance_control="balanced")
        a = tactics.effects(legacy, pass_no=1, fatigue=0,
                            horse_stats={"stamina": 5, "obedience": 5, "courage": 5})
        b = tactics.effects(new, pass_no=1, fatigue=0,
                            horse_stats={"stamina": 5, "obedience": 5, "courage": 5})
        self.assertEqual(a, b)
        self.assertFalse(tactics.advanced_active(legacy))
