"""v0.8 progression and loadout regression tests; no network or bot token."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from services import progression as p
from services.equipment import ITEMS


def fight(index: int, *, guild: int = 7, arena: str = "royal_lists",
          score_a: int = 3, score_b: int = 0, barding: str = "barding_none",
          category: str = "lance_break") -> dict:
    return {
        "id": f"m{index}", "guild_id": guild, "mode": "challenge", "arena_key": arena,
        "a": {"user_id": 101, "knight": "Arthur", "horse_id": "h101",
              "horse": "Thunder", "score": score_a,
              "gear": {"lance": "lance_ash", "armour": "armour_mail", "barding": barding}},
        "b": {"user_id": 102, "knight": "Basil", "horse_id": "h102", "horse": "Biscuit",
              "score": score_b, "gear": {"barding": "barding_none"}},
        "passes": [{"category": category, "result": f"Arthur: {category}",
                    "points_a": 1, "points_b": 0, "notes": []}],
    }


class ProgressionTests(unittest.TestCase):
    def test_new_gear_all_have_tradeoffs(self):
        self.assertEqual(len(p.UNLOCKS), 6)
        self.assertEqual(len(ITEMS), 18)
        for key in p.UNLOCKS:
            item = ITEMS[key]
            negative = [
                item.alignment_mod < 0, item.charge_mod < 0, item.impact_mult < 1,
                item.slip_mod > 0, item.panic_mod < 0, item.unhorse_resist < 0,
            ] + [v < 0 for v in item.knight_stat_mods.values()] + [
                v < 0 for v in item.horse_stat_mods.values()
            ]
            self.assertTrue(any(negative), f"{key} has no disadvantage")

    def test_accepted_matches_only_and_no_barding_snapshot(self):
        history = {"matches": [
            fight(0), fight(1, guild=99), fight(2, barding="barding_runner"),
            dict(fight(3), mode="instant")
        ]}
        self.assertEqual(p.earned_gold(7, 101, history), 40)
        values = p.progress(7, 101, history)
        self.assertEqual(values["wins"], 2)
        self.assertEqual(values["no_barding_wins"], 1)
        self.assertEqual(p.earned_gold(99, 101, history), 20)

    def test_frozen_survival_and_preexisting_without_snapshots(self):
        a = fight(0, arena="frozen_ground")
        b = fight(1, arena="frozen_ground")
        c = fight(2, arena="frozen_ground")
        b["passes"][0]["category"] = "unhorsing"
        b["passes"][0]["points_a"] = 0
        b["passes"][0]["points_b"] = 3
        b["a"]["score"], b["b"]["score"] = 0, 3
        del c["a"]["gear"]
        values = p.progress(7, 101, {"matches": [a,b,c]})
        self.assertEqual(values["frozen_survivals"], 2)
        self.assertEqual(values["no_barding_wins"], 1)

    def test_purchase_wallet_duplicate_and_per_guild_loadouts(self):
        matches = {"matches": [fight(i) for i in range(12)]}
        with tempfile.TemporaryDirectory() as td:
            with patch.object(p, "PATH", os.path.join(td, "progression.json")):
                with patch.object(p, "load_history", return_value=matches):
                    self.assertEqual(p.earned_gold(7, 101), 240)
                    self.assertTrue(p.unlocked(7, 101, "lance_ash"))
                    self.assertFalse(p.unlocked(7, 101, "lance_oakbreaker"))
                    with self.assertRaises(ValueError):
                        p.set_loadout(7, 101, "lance", "lance_oakbreaker")
                    self.assertEqual(p.buy(7, 101, "lance_oakbreaker"), 130)
                    with self.assertRaises(ValueError):
                        p.buy(7, 101, "lance_oakbreaker")
                    p.set_loadout(7, 101, "lance", "lance_oakbreaker")
                    self.assertEqual(p.loadout(7, 101, "lance", "lance_ash"), "lance_oakbreaker")
                    self.assertEqual(p.loadout(8, 101, "lance", "lance_ash"), "lance_ash")
                    self.assertEqual(p.wallet(7, 101), 130)
                    self.assertFalse(p.unlocked(8, 101, "lance_oakbreaker"))

    def test_barding_is_individual_to_each_horse(self):
        matches = {"matches": [fight(i, arena="frozen_ground") for i in range(8)]}
        with tempfile.TemporaryDirectory() as td:
            with patch.object(p, "PATH", os.path.join(td, "progression.json")):
                with patch.object(p, "load_history", return_value=matches):
                    self.assertGreaterEqual(p.progress(7, 101)["frozen_survivals"], 3)
                    p.buy(7, 101, "barding_marsh")
                    with self.assertRaises(ValueError):
                        p.set_loadout(7, 101, "barding", "barding_marsh")
                    p.set_loadout(7, 101, "barding", "barding_marsh", horse_id="h101")
                    self.assertEqual(p.loadout(7, 101, "barding", "barding_none", "h101"), "barding_marsh")
                    self.assertEqual(p.loadout(7, 101, "barding", "barding_none", "h103"), "barding_none")
                    self.assertEqual(p.loadout(8, 101, "barding", "barding_none", "h101"), "barding_none")

    def test_unmet_unlock_and_insufficient_funds(self):
        history = {"matches": [fight(i) for i in range(5)]}
        with tempfile.TemporaryDirectory() as td:
            with patch.object(p, "PATH", os.path.join(td, "progression.json")):
                with patch.object(p, "load_history", return_value=history):
                    # 5 victories = 100 gold, but the lance costs 110.
                    with self.assertRaisesRegex(ValueError, "110 gold"):
                        p.buy(7, 101, "lance_oakbreaker")
                    with self.assertRaisesRegex(ValueError, "Requirement not met"):
                        p.buy(7, 101, "lance_windrunner")
                    self.assertEqual(p.wallet(7, 101), 100)

    def test_cosmetic_standards(self):
        history = {"matches": [fight(i) for i in range(5)]}
        with tempfile.TemporaryDirectory() as td:
            with patch.object(p, "PATH", os.path.join(td, "progression.json")):
                with patch.object(p, "load_history", return_value=history):
                    p.set_standard(7, 101, "royal")
                    self.assertEqual(p.equipped_standard(7, 101), "Royal Standard")
                    self.assertEqual(p.equipped_standard(8, 101), "")
                    with self.assertRaises(ValueError):
                        p.set_standard(7, 101, "frost")
                    p.set_standard(7, 101, "none")
                    self.assertEqual(p.equipped_standard(7, 101), "")

    def test_prestige_rank_progression(self):
        matches = {"matches": [fight(i) for i in range(5)]}
        self.assertEqual(p.prestige(7, 101, matches), (15, "Lancer"))
        self.assertEqual(p.reputation(7, 101, matches), 10)
        self.assertEqual(p.prestige(9, 101, matches), (0, "Squire"))


if __name__ == "__main__":
    unittest.main()
