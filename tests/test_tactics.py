"""v0.9.1 tactical decisions, deterministic simulation and Discord privacy tests."""
from __future__ import annotations

import unittest
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord

from services.combat import Fighter, run_single_match
from services.tactics import (
    STYLES, TARGETS, MOVES, MAX_FATIGUE, TacticPlan,
    effects, advance_fatigue, target_result,
)
from services.injuries import risk_profile
from cogs.tactic_ui import TacticEditor


def fighter(user_id=1, *, courage=5, obedience=5, stamina=5):
    return Fighter(
        user_id=user_id, knight_name=f"Knight {user_id}", horse_name=f"Horse {user_id}",
        knight_stats={"strength": 6, "control": 6, "endurance": 6, "agility": 6,
                      "resolve": 6, "tactics": 6},
        horse_stats={"speed": 6, "power": 6, "stamina": stamina,
                     "obedience": obedience, "courage": courage},
        lance_key="lance_ash", armour_key="armour_mail", barding_key="barding_none",
    )


class TacticRules(unittest.TestCase):
    def test_defaults_validation_and_fatigue_cap(self):
        self.assertEqual(TacticPlan().as_dict(),
                         {"style": "balanced", "target": "shield", "manoeuvre": "none"})
        for field, bad in (("style", "invincible"), ("target", "neck"), ("manoeuvre", "cheat")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                TacticPlan(**{**TacticPlan().as_dict(), field: bad})
        self.assertEqual(len(STYLES), 3)
        self.assertEqual(len(TARGETS), 3)
        for style in STYLES:
            self.assertIn(style, STYLES)
        fatigue = 0
        plan = TacticPlan("aggressive", "rider", "reckless_charge")
        for n in range(1, 8):
            e = effects(plan, pass_no=n, fatigue=fatigue, horse_stats=fighter().horse_stats)
            fatigue = advance_fatigue(fatigue, e)
        self.assertEqual(fatigue, MAX_FATIGUE)

    def test_manoeuvre_is_activated_then_cools_down(self):
        plan = TacticPlan("balanced", "shield", "precision_strike")
        moves = [effects(plan, pass_no=n, fatigue=0, horse_stats=fighter().horse_stats).move
                 for n in range(1, 6)]
        self.assertEqual(moves, ["precision_strike", "none", "none", "precision_strike", "none"])
        comeback = TacticPlan("balanced", "rider", "last_stand")
        self.assertEqual(effects(comeback, pass_no=1, fatigue=0,
                                 horse_stats=fighter().horse_stats).move, "none")
        self.assertEqual(effects(comeback, pass_no=3, fatigue=0,
                                 horse_stats=fighter().horse_stats,
                                 score_for=0, score_against=2).move, "last_stand")
        self.assertEqual(effects(comeback, pass_no=3, fatigue=0,
                                 horse_stats=fighter().horse_stats,
                                 score_for=2, score_against=0).move, "none")

    def test_aggressive_is_a_gamble_and_cautious_has_tradeoff(self):
        horse = fighter().horse_stats
        cautious = effects(TacticPlan("cautious"), pass_no=1, fatigue=0, horse_stats=horse)
        balanced = effects(TacticPlan(), pass_no=1, fatigue=0, horse_stats=horse)
        wild = effects(TacticPlan("aggressive"), pass_no=1, fatigue=0, horse_stats=horse)
        self.assertGreater(cautious.alignment, balanced.alignment)
        self.assertLess(cautious.charge, balanced.charge)
        self.assertGreater(wild.charge, balanced.charge)
        self.assertLess(wild.alignment, balanced.alignment)
        self.assertGreater(wild.fatigue_gain, balanced.fatigue_gain)
        self.assertGreater(wild.injury_risk, balanced.injury_risk)
        nervous = effects(TacticPlan("aggressive"), pass_no=1, fatigue=0,
                          horse_stats=fighter(courage=2, obedience=2).horse_stats)
        self.assertLess(nervous.handling, wild.handling)
        tired = effects(TacticPlan("aggressive"), pass_no=4, fatigue=6, horse_stats=horse)
        fresh = effects(TacticPlan("aggressive"), pass_no=1, fatigue=0, horse_stats=horse)
        self.assertLess(tired.alignment, fresh.alignment)
        self.assertLess(tired.charge, fresh.charge)

    def test_lance_target_converts_heavy_scoring_into_break(self):
        self.assertEqual(target_result("saddle_stagger", 2, "lance"), ("lance_break", 1))
        self.assertEqual(target_result("unhorsing", 3, "lance"), ("unhorsing", 3))
        self.assertEqual(target_result("heavy_shield_hit", 2, "shield"),
                         ("heavy_shield_hit", 2))

    def test_unchanged_seed_is_reproducible_with_tactics(self):
        a, b = fighter(1), fighter(2)
        pa = TacticPlan("aggressive", "rider", "reckless_charge")
        pb = TacticPlan("cautious", "lance", "shield_brace")
        first = run_single_match(a, b, "frozen_ground", seed=98421, tactics_a=pa, tactics_b=pb)
        again = run_single_match(a, b, "frozen_ground", seed=98421, tactics_a=pa, tactics_b=pb)
        self.assertEqual(asdict(first), asdict(again))
        self.assertEqual(first.tactics_a, pa)
        self.assertEqual(first.tactics_b, pb)
        self.assertTrue(first.passes)
        self.assertTrue(all(pass_.tactics_a and pass_.tactics_b for pass_ in first.passes))
        self.assertTrue(any("Aggressive" in note for item in first.passes for note in item.notes))
        normal = run_single_match(a, b, "frozen_ground", seed=98421)
        self.assertNotEqual(asdict(normal), asdict(first))

    def test_feigned_miss_counters_aggressive_opponents(self):
        from unittest.mock import patch
        left = TacticPlan("balanced", "shield", "feigned_miss")
        angry = TacticPlan("aggressive", "rider", "none")
        calm = TacticPlan("balanced", "rider", "none")
        with patch("services.combat.behaviour_check", return_value=(None, [])):
            vs_aggressive = run_single_match(
                fighter(1), fighter(2), "royal_lists", seed=1192, tactics_a=left, tactics_b=angry
            )
            vs_calm = run_single_match(
                fighter(1), fighter(2), "royal_lists", seed=1192, tactics_a=left, tactics_b=calm
            )
        self.assertTrue(any("feint draws" in note for p in vs_aggressive.passes for note in p.notes))
        self.assertFalse(any("feint draws" in note for p in vs_calm.passes for note in p.notes))

    def test_tactical_risk_changes_with_style_and_rider_target(self):
        base = {
            "arena_key": "royal_lists",
            "a": {"gear": {"armour": "armour_mail", "barding": "barding_none"},
                  "horse_breed": "destrier", "horse_stats": {"courage": 6, "obedience": 6}},
            "b": {"gear": {"lance": "lance_ash"}, "horse_stats": {"courage": 6, "obedience": 6}},
        }
        baseline = risk_profile(base, "a", "b", "unhorsing")["chance"]
        event = {"tactics_a": {"style": "aggressive", "fatigue": 6},
                 "tactics_b": {"target": "rider", "move": "reckless_charge"}}
        risky = risk_profile(base, "a", "b", "unhorsing", event=event)["chance"]
        self.assertGreater(risky, baseline)
        event["tactics_a"]["style"] = "cautious"
        event["tactics_a"]["fatigue"] = 0
        event["tactics_b"] = {"target": "shield", "move": "none"}
        safer = risk_profile(base, "a", "b", "unhorsing", event=event)["chance"]
        self.assertLess(safer, baseline)

    def test_no_extreme_strategy_dominates_equal_stats(self):
        """A coarse seeded 500-match sweep; caution and aggression remain competitive."""
        plans = [
            TacticPlan("cautious", "shield", "precision_strike"),
            TacticPlan("balanced", "lance", "shield_brace"),
            TacticPlan("aggressive", "rider", "reckless_charge"),
        ]
        for left in plans:
            for right in plans:
                if left == right:
                    continue
                wins, draws = 0, 0
                # Swap seat order to avoid RNG seat bias.
                for seed in range(100, 350):
                    for swap in (False, True):
                        if not swap:
                            result = run_single_match(fighter(1), fighter(2), "royal_lists",
                                                      seed=seed, tactics_a=left, tactics_b=right)
                            lhs, rhs = result.score_a, result.score_b
                        else:
                            result = run_single_match(fighter(2), fighter(1), "royal_lists",
                                                      seed=seed, tactics_a=right, tactics_b=left)
                            lhs, rhs = result.score_b, result.score_a
                        wins += lhs > rhs
                        draws += lhs == rhs
                share = (wins + draws * 0.5) / 500
                self.assertGreater(share, 0.12, (left, right, share))
                self.assertLess(share, 0.88, (left, right, share))


class PrivateTacticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_challenge_needs_two_locked_tactics(self):
        from cogs.joust import ChallengeView
        from unittest.mock import Mock
        prepared = SimpleNamespace(
            challenger=SimpleNamespace(id=11),
            opponent=SimpleNamespace(id=22),
            tactics_a=TacticPlan(), tactics_b=TacticPlan(),
            tactics_ready={11},
        )
        view = ChallengeView(Mock(), prepared)
        response = SimpleNamespace(send_message=AsyncMock())
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=22),
            response=response,
        )
        await view.accept.callback(interaction)
        self.assertFalse(view.completed)
        response.send_message.assert_awaited_once()
        self.assertTrue(response.send_message.await_args.kwargs["ephemeral"])

    async def test_tactical_button_is_private_for_both_players(self):
        from cogs.joust import ChallengeView
        from unittest.mock import Mock
        prepared = SimpleNamespace(
            challenger=SimpleNamespace(id=11),
            opponent=SimpleNamespace(id=22),
            tactics_a=TacticPlan(), tactics_b=TacticPlan(), tactics_ready=set(),
        )
        view = ChallengeView(Mock(), prepared)
        for pid in (11, 22):
            response = SimpleNamespace(send_message=AsyncMock())
            interaction = SimpleNamespace(user=SimpleNamespace(id=pid), response=response)
            await view.choose_tactics.callback(interaction)
            self.assertTrue(response.send_message.await_args.kwargs["ephemeral"])
            self.assertIsInstance(response.send_message.await_args.kwargs["view"], TacticEditor)

    async def test_private_editor_rows_and_owner_protection(self):
        prepared = SimpleNamespace(
            challenger=SimpleNamespace(id=11), opponent=SimpleNamespace(id=22),
            tactics_a=TacticPlan(), tactics_b=TacticPlan(), tactics_ready=set(),
        )
        challenge = SimpleNamespace(completed=False, prepared=prepared, message=None)
        screen = TacticEditor(challenge, 11)
        choices = [x for x in screen.children if isinstance(x, discord.ui.Select)]
        self.assertEqual({x.row for x in choices}, {0, 1, 2})
        self.assertIn("Lock Tactics", [getattr(x, "label", None) for x in screen.children])
        denied = SimpleNamespace(user=SimpleNamespace(id=22),
                                 response=SimpleNamespace(send_message=AsyncMock()))
        self.assertFalse(await screen.interaction_check(denied))
        denied.response.send_message.assert_awaited_once()
        screen.plan = TacticPlan("aggressive", "rider", "reckless_charge")
        intr = SimpleNamespace(user=SimpleNamespace(id=11),
                               response=SimpleNamespace(edit_message=AsyncMock()))
        await screen.lock.callback(intr)
        self.assertEqual(prepared.tactics_a, screen.plan)
        self.assertEqual(prepared.tactics_ready, {11})
        intr.response.edit_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
