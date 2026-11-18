"""v2.9.5 — evolution regressions: compatibility, economy, daily and UI."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import patch

import discord

from services import evolution, progression, equipment
from services.combat import Fighter, run_single_match
from cogs import evolution as screens


NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def horses():
    return {"horses": {
        "h5": {"horse_id": "h5", "owner_id": 5, "name": "Comet", "breed": "courser",
               "stats": {"speed": 5, "stamina": 5, "power": 5,
                         "obedience": 5, "courage": 4}},
        "other": {"horse_id": "other", "owner_id": 6, "name": "Thunder",
                  "breed": "destrier", "stats": {}},
    }}


def match(mid, mode="training", when=NOW, guild=88, arena="royal_lists"):
    return {
        "id": mid, "mode": mode, "guild_id": guild, "arena_key": arena,
        "timestamp": when.isoformat(),
        "a": {"user_id": 5, "horse_id": "h5", "score": 2},
        "b": {"user_id": -20001 if mode == "training" else 6,
              "horse_id": "other", "score": 0},
    }


class DailyRenownTests(TestCase):
    def test_objectives_are_journal_derived_and_only_pay_cosmetic_renown_once(self):
        data = {"guilds": {}}
        today = evolution.utc_day(NOW)
        arena = evolution.daily_goals(
            88, 5, now=NOW, history={"matches": []}, data=data)["arena_key"]
        journal = {"matches": [
            match("t1"), match("c1", mode="challenge", arena=arena),
            match("c1", mode="challenge", arena=arena),
            match("foreign", mode="training", guild=999),
            match("old", when=NOW - timedelta(days=1)),
        ]}
        with patch.object(evolution, "_db", return_value=data), \
             patch.object(evolution, "load_history", return_value=journal), \
             patch.object(evolution, "save_json") as save:
            result = evolution.daily_goals(88, 5, now=NOW)
            self.assertEqual(set(result["goals"]), {"training", "challenge", "arena"})
            self.assertTrue(all(g["earned"] for g in result["goals"].values()))
            for key in ("training", "challenge", "arena"):
                evolution.claim_goal(88, 5, key, now=NOW)
                with self.assertRaises(ValueError):
                    evolution.claim_goal(88, 5, key, now=NOW)
            self.assertEqual(evolution.daily_goals(88, 5, now=NOW)["renown"], 16)
            self.assertEqual(save.call_count, 3)
            self.assertFalse(any(g["claimed"] for g in evolution.daily_goals(
                88, 5, now=NOW + timedelta(days=1))["goals"].values()))
        self.assertEqual(progression.GOLD_PER_JOUST, 12)


class BondAndCareTests(TestCase):
    def test_care_one_per_utc_day_per_owned_horse_and_bonus_caps_at_one(self):
        db = {"guilds": {}}
        journal = {"matches": [match(f"m{x}") for x in range(20)] + [match("m0")]}
        with patch("cogs.horse.load_horses", return_value=horses()), \
             patch.object(evolution, "_db", return_value=db), \
             patch.object(evolution, "load_history", return_value=journal), \
             patch.object(evolution, "save_json"):
            before = evolution.bond(88, 5, "h5", now=NOW)
            self.assertEqual(before["score"], 40)
            self.assertEqual(before["obedience_bonus"], 1)
            groomed = evolution.groom(88, 5, "h5", now=NOW)
            self.assertEqual(groomed["score"], 43)
            with self.assertRaisesRegex(ValueError, "already groomed"):
                evolution.groom(88, 5, "h5", now=NOW)
            self.assertEqual(evolution.groom(
                88, 5, "h5", now=NOW + timedelta(days=1))["score"], 46)
            with self.assertRaisesRegex(ValueError, "belongs to you"):
                evolution.groom(88, 5, "other", now=NOW)
            self.assertEqual(evolution.bond(88, 5, "h5", now=NOW)["obedience_bonus"], 1)

    def test_bonding_is_scoped_to_guild_and_has_no_gold_or_xp(self):
        with patch("cogs.horse.load_horses", return_value=horses()):
            a = evolution.bond(88, 5, "h5", history={"matches": [match("t")]}, data={"guilds": {}})
            b = evolution.bond(89, 5, "h5", history={"matches": [match("t")]}, data={"guilds": {}})
        self.assertEqual(a["score"], 2)
        self.assertEqual(b["score"], 0)
        stats = {"speed": 5, "stamina": 5, "power": 5, "obedience": 10, "courage": 5}
        self.assertEqual(equipment.apply_horse_equipment(
            stats, "barding_none", bond_bonus=1)["obedience"], 10)


class PresetSecurityTests(TestCase):
    def test_preset_saves_current_gear_and_refuses_other_mount(self):
        db = {"guilds": {}}
        knight = {"knights": {"5": {
            "bound_horse_id": "h5", "equipped_lance_key": "lance_ash",
            "equipped_armour_key": "armour_mail",
        }}}
        with patch("cogs.horse.load_horses", return_value=horses()), \
             patch("cogs.knight.load_knights", return_value=knight), \
             patch.object(evolution, "_db", return_value=db), \
             patch.object(progression, "_db", return_value=db), \
             patch.object(evolution, "save_json"), \
             patch.object(evolution, "unlocked", return_value=True):
            evolution.set_preferred_tactics(88, 5, style="cautious",
                                             target="lance", manoeuvre="shield_brace")
            saved = evolution.save_preset(88, 5, "defence")
            self.assertEqual(len(saved["gear"]), 8)
            self.assertEqual(saved["tactics"]["style"], "cautious")
            self.assertEqual(saved["horse_id"], "h5")
            evolution.apply_preset(88, 5, "defence")
            profile = db["guilds"]["88"]["5"]
            self.assertEqual(profile["loadout"]["shield"], "shield_kite")
            self.assertEqual(profile["horse_gear"]["h5"]["saddle"], "saddle_standard")
            knight["knights"]["5"]["bound_horse_id"] = "other"
            with self.assertRaisesRegex(ValueError, "belongs to you"):
                evolution.apply_preset(88, 5, "defence")
            knight["knights"]["5"]["bound_horse_id"] = "h5"
            evolution.delete_preset(88, 5, "defence")
            self.assertFalse(evolution.preset_names(88, 5)["defence"])

    def test_rejects_locked_or_tampered_presets_without_partial_equipping(self):
        db = {"guilds": {"88": {"5": {"presets": {"speed": {
            "horse_id": "h5", "gear": {
                **{k: v for k, v in progression.STARTER.items()},
                "helm": "helm_watchful",
            },
            "tactics": {"style": "balanced", "target": "shield", "manoeuvre": "none"}
        }}}}}}
        with patch("cogs.horse.load_horses", return_value=horses()), \
             patch("cogs.knight.load_knights", return_value={
                 "knights": {"5": {"bound_horse_id": "h5"}}
             }), \
             patch.object(evolution, "_db", return_value=db):
            with self.assertRaisesRegex(ValueError, "unavailable helm"):
                evolution.apply_preset(88, 5, "speed")
            self.assertNotIn("loadout", db["guilds"]["88"]["5"])


class GearBalanceTests(TestCase):
    def test_new_starter_slots_are_neutral_and_old_fighter_constructor_works(self):
        self.assertEqual(len(progression.STARTER), 8)
        knight = {"strength": 5, "control": 5, "endurance": 5,
                  "agility": 4, "resolve": 4, "tactics": 4}
        horse = {"speed": 5, "stamina": 5, "power": 5,
                 "obedience": 5, "courage": 5}
        older = Fighter(5, "Red", "Comet", knight, horse,
                        "lance_ash", "armour_mail", "barding_none", "rouncey")
        current = Fighter(5, "Red", "Comet", knight, horse,
                          "lance_ash", "armour_mail", "barding_none", "rouncey",
                          helm_key="helm_plain", shield_key="shield_kite",
                          saddle_key="saddle_standard", bridle_key="bridle_simple",
                          shoes_key="shoes_iron", bond_bonus=0)
        enemy = Fighter(6, "Blue", "Misty", knight, horse,
                        "lance_ash", "armour_mail", "barding_none")
        self.assertEqual(
            run_single_match(older, enemy, "royal_lists", seed=12345),
            run_single_match(current, enemy, "royal_lists", seed=12345),
        )
        self.assertEqual(equipment.total_unhorse_resist(
            "armour_mail", "shield_round"), 1)
        self.assertEqual(equipment.total_slip_mod(
            "barding_none", "shoes_grip"), -2)


class MenuSmokeTests(TestCase):
    def test_headquarters_and_evolution_panels_follow_private_menu_contract(self):
        pages = (
            screens.HeadquartersPage(5, None), screens.DailyPage(5, None),
            screens.StableCarePage(5, None), screens.PresetPage(5, None),
            screens.TacticsPreferencePage(5, None),
        )
        for view in pages:
            self.assertLessEqual(len(view.children), 25)
            self.assertTrue(any(getattr(c, "label", "") == "Main Menu"
                                for c in view.children))
            for row in range(5):
                contents = [c for c in view.children if c.row == row]
                if any(isinstance(c, discord.ui.Select) for c in contents):
                    self.assertEqual(len(contents), 1)
                else:
                    self.assertLessEqual(len(contents), 5)
            self.assertLessEqual(len(view.make_embed().description or ""), 4096)


class RespecSafetyTests(TestCase):
    def test_respec_cooldown_validation_and_metadata_survive_recreation(self):
        from datetime import timedelta
        stats = {"strength": 4, "control": 4, "endurance": 3,
                 "agility": 3, "resolve": 3, "tactics": 3}
        changed = {"strength": 5, "control": 3, "endurance": 3,
                   "agility": 3, "resolve": 3, "tactics": 3}
        db = {"knights": {"5": {
            "user_id": 5, "stats": stats.copy(), "name": "Sir Test",
            "bound_horse_id": "h5", "equipped_lance_key": "lance_ash"
        }}}
        with patch("cogs.knight.load_knights", return_value=db), \
             patch("cogs.knight.save_knights") as save, \
             patch("services.tournaments.load_db", return_value={"guilds": {}}):
            with self.assertRaisesRegex(ValueError, "active challenge"):
                evolution.respec_knight(5, changed, now=NOW, active_match=True)
            with self.assertRaisesRegex(ValueError, "total 20"):
                evolution.respec_knight(5, {**changed, "strength": 6}, now=NOW)
            with self.assertRaisesRegex(ValueError, "No changes"):
                evolution.respec_knight(5, stats.copy(), now=NOW)
            result = evolution.respec_knight(5, changed, now=NOW)
            self.assertEqual(result["stats"], changed)
            self.assertEqual(result["bound_horse_id"], "h5")
            self.assertEqual(save.call_count, 1)
            self.assertEqual(evolution.respec_remaining(5, now=NOW), 14*24*3600)
            # Recreating a knight must never clear the persisted cooldown.
            db["knights"]["5"] = {"user_id": 5, "stats": stats.copy(), "name": "New Knight"}
            with self.assertRaisesRegex(ValueError, "cooldown"):
                evolution.respec_knight(5, changed, now=NOW + timedelta(days=2))
            evolution.respec_knight(5, changed, now=NOW + timedelta(days=14, seconds=1))
            self.assertEqual(save.call_count, 2)

    def test_tournament_registration_blocks_global_stat_reallocation(self):
        stats = {"strength": 5, "control": 3, "endurance": 3,
                 "agility": 3, "resolve": 3, "tactics": 3}
        data = {"knights": {"5": {"user_id": 5, "name": "Sir Test",
                                 "stats": {"strength": 4, "control": 4,
                                           "endurance": 3, "agility": 3,
                                           "resolve": 3, "tactics": 3}}}}
        events = {"guilds": {"99": {"active": {
            "status": "registration", "entrants": [5]
        }}}}
        with patch("cogs.knight.load_knights", return_value=data), \
             patch("cogs.knight.save_knights") as save, \
             patch("services.tournaments.load_db", return_value=events):
            with self.assertRaisesRegex(ValueError, "tournament"):
                evolution.respec_knight(5, stats, now=NOW)
            save.assert_not_called()
