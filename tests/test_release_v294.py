"""v2.9.4 targeted security, persistence and graphics regression checks."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image

from cogs.joust import JoustCog
from cogs.tournament import advancing_rider
from services import asset_health, combat, final_scorecard


class CompetitiveIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def test_competitive_challenge_rejects_client_selected_seed(self):
        # No preliminary read/lock/simulation should occur after a ranked seed.
        cog = JoustCog(SimpleNamespace())
        interaction = SimpleNamespace(
            response=SimpleNamespace(send_message=AsyncMock()),
            user=SimpleNamespace(id=11),
        )
        opponent = SimpleNamespace(id=22)
        with patch.object(cog, "prepare_duel") as prepare:
            await JoustCog.challenge.callback(
                cog, interaction, opponent, seed=12345
            )
        prepare.assert_not_called()
        interaction.response.send_message.assert_awaited_once()
        self.assertIn("cannot specify a seed",
                      interaction.response.send_message.await_args.args[0])

    async def test_rejects_stale_foreign_horse_binding(self):
        cog = JoustCog(SimpleNamespace())
        rider_a = SimpleNamespace(id=11)
        rider_b = SimpleNamespace(id=22, bot=False)
        knight_a = SimpleNamespace(bound_horse_id="red-horse")
        knight_b = SimpleNamespace(bound_horse_id="blue-horse")
        with patch("cogs.joust.load_knights", return_value={}), \
             patch("cogs.joust.load_horses", return_value={
                 "horses": {"red-horse": {"owner_id": 999}, "blue-horse": {"owner_id": 22}}
             }), \
             patch("cogs.joust.get_knight", side_effect=[knight_a, knight_b]), \
             patch("cogs.joust.Horse.from_dict", side_effect=[
                 SimpleNamespace(owner_id=999),
                 SimpleNamespace(owner_id=22),
             ]):
            error, prepared = cog.prepare_duel(
                challenger=rider_a, opponent=rider_b, arena_key="royal_lists"
            )
        self.assertIsNone(prepared)
        self.assertIn("belongs to a different rider", error)


class DeterministicSeedTests(unittest.TestCase):
    def test_unseeded_match_uses_system_rng_and_seeded_replay_is_unchanged(self):
        knight_stats = dict(strength=6, control=6, endurance=6,
                            agility=5, resolve=5, tactics=5)
        horse_stats = dict(speed=6, stamina=6, power=5,
                           obedience=6, courage=6)
        a = combat.Fighter(11, "Red", "Red Mount", knight_stats, horse_stats,
                           "lance_ash", "armour_mail", "barding_none")
        b = combat.Fighter(22, "Blue", "Blue Mount", knight_stats, horse_stats,
                           "lance_ash", "armour_mail", "barding_none")
        with patch("services.combat.secrets.randbelow", return_value=1234) as secure:
            automatic = combat.run_single_match(a, b, "royal_lists")
        secure.assert_called_once_with(2_147_483_647)
        self.assertEqual(automatic.seed, 1235)
        with patch("services.combat.secrets.randbelow") as secure:
            replay = combat.run_single_match(a, b, "royal_lists", seed=1235)
        secure.assert_not_called()
        self.assertEqual(automatic, replay)

    def test_tournament_recovery_winner_does_not_need_member_objects(self):
        self.assertEqual(advancing_rider(4, 2, 11, 22, 99), (11, None))
        self.assertEqual(advancing_rider(2, 4, 11, 22, 99), (22, None))
        winner, label = advancing_rider(2, 2, 11, 22, 99)
        self.assertIn(winner, (11, 22))
        self.assertEqual(label, "seeded marshal decision")
        self.assertEqual(advancing_rider(2, 2, 11, 22, 99), (winner, label))

    def test_tournament_final_scorecard_follows_intro_identity(self):
        self.assertEqual(final_scorecard._format(SimpleNamespace(
            mode="challenge", intro_event_type="TOURNAMENT MATCH")), "TOURNAMENT")
        self.assertEqual(final_scorecard._format(SimpleNamespace(
            mode="challenge", intro_event_type="TOURNAMENT FINAL")), "GRAND FINAL")
        self.assertEqual(final_scorecard._format(SimpleNamespace(
            mode="challenge")), "RANKED JOUST")


class AssetAuditTests(unittest.TestCase):
    def test_missing_assets_are_warnings_not_crashes(self):
        with tempfile.TemporaryDirectory() as folder:
            report = asset_health.audit_assets(Path(folder))
        self.assertGreater(report["expected"], 100)
        self.assertEqual(report["present"], 0)
        self.assertEqual(report["missing"], report["expected"])
        self.assertFalse(report["ready_for_full_graphics"])
        self.assertFalse(report["errors"])
        self.assertTrue(report["warnings"])

    def test_corrupt_and_opaque_sprite_files_are_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "assets/jousting/props/barrier.png"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"fake png")
            knight = root / ("assets/jousting/knights/blue_knight/idle/"
                             "blue_knight_idle_left_01.png")
            knight.parent.mkdir(parents=True)
            Image.new("RGB", (400, 640), (100, 50, 60)).save(knight)
            report = asset_health.audit_assets(root)
        self.assertEqual(len(report["errors"]), 2)
        self.assertTrue(any("barrier.png" in e for e in report["errors"]))
        self.assertTrue(any("alpha" in e for e in report["errors"]))

class BroadcastVersionTests(unittest.TestCase):
    def test_live_intro_and_passes_show_release_version(self):
        from services.live_broadcast import _intro_embed, _screen_embed
        p = SimpleNamespace(arena_key="royal_lists", mode="training")
        result = SimpleNamespace(fighter_a="Red", fighter_b="Blue",
                                 passes=[object()])
        clip = SimpleNamespace(pass_no=1, path=Path("pass_1.gif"))
        intro = _intro_embed(result, p)
        live_pass = _screen_embed(result, clip, arena_key=p.arena_key)
        self.assertIn("v2.9.6a", intro.footer.text)
        self.assertIn("v2.9.6a", live_pass.footer.text)
