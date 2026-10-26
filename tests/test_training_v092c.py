"""v0.9.2c Training Yard balance, injury, privacy and permissions tests."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cogs import joust as ui
from cogs import tournament as tourn_ui
from cogs.menu import MainMenuView, TrainingPage
from services import training, injuries, competition, progression, records
from services.combat import Fighter
from services.storage import load_json


def record(key, user_id=101, guild=88, days=0, *, mode="training"):
    date = datetime(2026, 10, 26, 12, tzinfo=timezone.utc) + timedelta(days=days)
    return {
        "id": key, "mode": mode, "guild_id": guild,
        "timestamp": date.isoformat(), "arena_key": "royal_lists",
        "a": {"user_id": user_id, "score": 2},
        "b": {"user_id": -20001 if mode == "training" else 102, "score": 1},
        "passes": [],
        "injuries": [],
    }


class TrainingBalanceTests(unittest.TestCase):
    def test_twelve_distinct_tiered_opponents_and_original_coaches(self):
        roster = training.OPPONENTS
        self.assertEqual(len(roster), 12)
        self.assertEqual([npc.level for npc in roster], list(range(1, 13)))
        self.assertEqual(len({npc.key for npc in roster}), 12)
        self.assertTrue({"osric", "beren", "elis", "maud"} <= {npc.key for npc in roster})
        for npc in roster:
            self.assertEqual(training.opponent(npc.key.upper()), npc)
            f = npc.fighter()
            self.assertIsInstance(f, Fighter)
            self.assertEqual(f.horse_breed, npc.breed)
            self.assertEqual(f.user_id, npc.player_id)
            self.assertTrue(all(1 <= value <= 8 for value in f.knight_stats.values()))
            self.assertTrue(all(1 <= value <= 10 for value in f.horse_stats.values()))
            self.assertNotEqual(f.user_id, 0)

    def test_bounded_small_xp_and_no_gold_or_ranked_credit(self):
        # More than ten sessions on one UTC day awards precisely 30 XP.
        entries = [record(f"train-{i}") for i in range(15)]
        entries.append(record("competitive", mode="challenge"))
        data = {"matches": entries}
        xp = training.earned_training(88, 101, data,
                                     now=datetime(2026, 10, 26, tzinfo=timezone.utc))
        self.assertEqual(xp["sessions"], 15)
        self.assertEqual(xp["xp"], 30)
        self.assertEqual(xp["level"], 2)
        self.assertEqual(xp["today_xp"], 30)
        self.assertEqual(len([v for v in xp["awards"].values() if v]), 10)
        # Only one challenge is eligible for paid rewards/rank/leaderboards.
        self.assertEqual(len(competition.guild_matches(88, data)), 1)
        self.assertEqual(progression.earned_gold(88, 101, data),
                         progression.GOLD_PER_JOUST + progression.GOLD_WIN_BONUS)

    def test_distinct_guilds_players_and_calendar_days(self):
        data = {"matches": [
            *[record(f"t-{i}") for i in range(11)],
            record("next-day", days=1),
            record("wrong-user", user_id=333),
            record("wrong-guild", guild=77),
            record("duplicate", days=1),
            record("duplicate", days=1),
        ]}
        score = training.earned_training(
            88, 101, data, now=datetime(2026, 10, 27, tzinfo=timezone.utc))
        self.assertEqual(score["sessions"], 13)
        self.assertEqual(score["xp"], 36)
        self.assertEqual(score["today_xp"], 6)

    def test_training_match_injures_player_only_and_heals_using_existing_system(self):
        entry = record("training-injury")
        entry.update({
            "mode": "training",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "a": {
                "user_id": 101, "score": 0, "horse_breed": "rouncey",
                "horse_stats": {"courage": 3, "obedience": 4}, "gear": {},
            },
            "b": {
                "user_id": -20001, "score": 3, "horse_breed": "destrier",
                "horse_stats": {"courage": 6, "obedience": 6}, "gear": {},
            },
            "passes": [{"pass_no": 1, "category": "unhorsing",
                        "points_a": 0, "points_b": 3,
                        "tactics_a": {}, "tactics_b": {}}],
        })
        with patch.object(injuries, "roll", return_value=0):
            events = injuries.make_events(entry)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["user_id"], 101)
        entry["injuries"] = events
        history = {"matches": [entry]}
        self.assertTrue(injuries.active(88, 101, history=history, data={"guilds": {}}))
        self.assertEqual(injuries.active(88, -20001, history=history, data={"guilds": {}}), [])

    def test_instant_duels_have_no_training_xp(self):
        h = {"matches": [record("instant", mode="instant")]}
        self.assertEqual(training.earned_training(88, 101, h)["xp"], 0)

    def test_roster_and_menu_show_training_to_every_player(self):
        view = MainMenuView(101, allow_admin=False)
        self.assertIn("Training Yard", [getattr(x, "label", None) for x in view.children])
        with patch.object(training, "load_history", return_value={"matches": []}):
            page = TrainingPage(101, 88)
            self.assertIn("0 gold", page.make_embed().description.lower())


class TrainingCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_training_prepared_with_player_horse_and_npc_without_mutation(self):
        npc = training.opponent("maud")
        knight = SimpleNamespace(
            name="Sir Test", stats={"strength": 4, "control": 4, "endurance": 3,
                                    "agility": 3, "resolve": 3, "tactics": 3},
            bound_horse_id="h-one", equipped_lance_key="lance_ash",
            equipped_armour_key="armour_mail",
        )
        raw_horse = {
            "horse_id": "h-one", "owner_id": 101, "name": "Comet",
            "breed": "courser", "stats": {
                "speed": 5, "stamina": 5, "power": 5, "obedience": 5, "courage": 4,
            }, "equipped_barding_key": "barding_none",
        }
        cog = ui.JoustCog(SimpleNamespace())
        with patch.object(ui, "get_knight", return_value=knight), \
             patch.object(ui, "load_knights", return_value={"knights": {"101": {}}}), \
             patch.object(ui, "load_horses", return_value={"horses": {"h-one": raw_horse}}), \
             patch.object(ui, "loadout", side_effect=lambda _g, _u, _slot, default, *args: default), \
             patch.object(ui, "apply_penalty", side_effect=lambda stats, *a, **k: dict(stats)):
            error, prepared = cog.prepare_training(
                SimpleNamespace(id=101, mention="<@101>"), 88, npc)
        self.assertIsNone(error)
        self.assertEqual(prepared.mode, "training")
        self.assertEqual(prepared.fighter_b.knight_name, "Dame Maud Ironhand")
        self.assertEqual(prepared.fighter_a.user_id, 101)
        self.assertEqual(prepared.fighter_b.user_id, npc.player_id)
        self.assertEqual(prepared.tactics_b, npc.tactics)

    async def test_failed_training_prerequisites_do_not_simulate_or_record(self):
        npc = training.opponent("osric")
        cog = ui.JoustCog(SimpleNamespace())
        with patch.object(ui, "get_knight", return_value=None), \
             patch.object(ui, "load_knights", return_value={"knights": {}}), \
             patch.object(ui, "load_horses", return_value={"horses": {}}):
            reason, prepared = cog.prepare_training(SimpleNamespace(id=101), 88, npc)
        self.assertIn("Create a knight", reason)
        self.assertIsNone(prepared)


class TournamentCreationPermissions(unittest.IsolatedAsyncioTestCase):
    async def test_creation_cannot_be_executed_by_ordinary_member(self):
        user = SimpleNamespace(id=101, guild_permissions=SimpleNamespace(manage_guild=False))
        intr = SimpleNamespace(
            user=user, guild_id=88,
            response=SimpleNamespace(send_message=AsyncMock()),
        )
        cog = tourn_ui.TournamentCog(SimpleNamespace())
        with patch.object(tourn_ui.engine, "create") as mutate:
            await cog.do_create(intr, "King's Cup", 4)
        mutate.assert_not_called()
        self.assertIn("Only server admins",
                      intr.response.send_message.await_args.args[0])

    async def test_admin_can_create_but_nonadmin_can_still_join(self):
        user = SimpleNamespace(id=101, guild_permissions=SimpleNamespace(manage_guild=True))
        intr = SimpleNamespace(
            user=user, guild_id=88, channel=None,
            response=SimpleNamespace(send_message=AsyncMock()),
        )
        cog = tourn_ui.TournamentCog(SimpleNamespace())
        with patch.object(tourn_ui.engine, "create", return_value={} ) as mutate:
            await cog.do_create(intr, "King's Cup", 4)
        mutate.assert_called_once_with(88, 101, "King's Cup", 4)
        # The public registration command has no admin-only permission decorator.
        join = next(c for c in cog.group.commands if c.name == "join")
        self.assertIsNotNone(join)
        players_view = tourn_ui.TournamentHub(101, 88, admin=False)
        self.assertNotIn("Create", [getattr(c, "label", None) for c in players_view.children])


if __name__ == "__main__":
    unittest.main()
