"""v0.9.0a safe server resets and admin command UI regression tests."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import discord
from discord.ext import commands

from services import maintenance as m, progression as p
from services.storage import save_json, load_json
from cogs import maintenance as ui


class AdminResetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.storage = root / "storage"
        self.backups = root / "backups"
        self.storage.mkdir()
        self.patches = [
            patch.object(m, "DATA_DIR", self.storage),
            patch.object(m, "BACKUP_DIR", self.backups),
            patch.object(p, "PATH", str(self.storage / "progression.json")),
        ]
        for item in self.patches:
            item.start()
        matches = []
        for number in range(6):
            matches.append({
                "id": f"match-{number}", "guild_id": 100, "mode": "challenge",
                "a": {"user_id": 7, "score": 3}, "b": {"user_id": 8, "score": 0},
                "passes": [], "arena_key": "royal_lists",
            })
        self.history = {"matches": matches}
        save_json(str(self.storage / "matches.json"), matches and self.history)
        save_json(str(self.storage / "knights.json"), {"knights": {"7": {"name": "Knight"}}})
        save_json(str(self.storage / "horses.json"), {"horses": {"horse-a": {"owner_id": 7}}})
        save_json(str(self.storage / "titles.json"), {
            "guilds": {"100": {"7": "first_lance"}, "200": {"7": "shield_splitter"}}
        })
        save_json(str(self.storage / "tournaments.json"), {"guilds": {"100": {"history": []}}})
        self.progression = {
            "guilds": {
                "100": {"7": {
                    "purchases": {"lance_oakbreaker": {"cost": 40}},
                    "loadout": {"lance": "lance_oakbreaker"},
                    "horse_barding": {"horse-a": "barding_leather"},
                    "standard": "royal",
                    "healing": {"match-0:b": {"gold": 27, "hours": 12}},
                }},
                "200": {"7": {"purchases": {"lance_oakbreaker": {"cost": 90}},
                              "loadout": {"lance": "lance_oakbreaker"},
                              "standard": "frost"}},
            }
        }
        save_json(p.PATH, self.progression)
        self.wallet_patch = patch.object(p, "load_history", return_value=self.history)
        self.wallet_patch.start()

    def tearDown(self):
        self.wallet_patch.stop()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def json(self, filename):
        return load_json(str(self.storage / filename), {})

    def test_settings_reset_keeps_purchases_healing_and_gold(self):
        before = p.wallet(100, 7)
        self.assertEqual(before, 53)
        preview = m.reset_user_plan(100, 7)
        self.assertIn("Earned gold history", preview["preserved"])
        result = m.reset_user(100, 7, "settings", 50)
        self.assertEqual(result["scope"], "settings")
        self.assertIn(result["backup"], m.backup_names())
        self.assertEqual(self.json("admin_audit.json")["events"][0]["action"], "reset_user")
        record = self.json("progression.json")["guilds"]["100"]["7"]
        self.assertNotIn("loadout", record)
        self.assertNotIn("horse_barding", record)
        self.assertEqual(record["standard"], "none")
        self.assertIn("lance_oakbreaker", record["purchases"])
        self.assertEqual(record["healing"]["match-0:b"]["gold"], 27)
        self.assertEqual(p.wallet(100, 7), before)
        self.assertNotIn("7", self.json("titles.json")["guilds"]["100"])
        self.assertIn("7", self.json("titles.json")["guilds"]["200"])
        self.assertEqual(self.json("knights.json")["knights"]["7"]["name"], "Knight")
        self.assertEqual(len(self.json("matches.json")["matches"]), 6)

    def test_inventory_reset_does_not_refund_gold(self):
        balance = p.wallet(100, 7)
        first = m.reset_user(100, 7, "inventory", 50)
        record = self.json("progression.json")["guilds"]["100"]["7"]
        self.assertEqual(record["retired_spend"], 40)
        self.assertEqual(record["purchases"], {})
        self.assertEqual(p.wallet(100, 7), balance)
        # A repeated administrative action must be financially idempotent.
        again = m.reset_user(100, 7, "inventory", 50)
        self.assertEqual(self.json("progression.json")["guilds"]["100"]["7"]["retired_spend"], 40)
        self.assertEqual(p.wallet(100, 7), balance)
        self.assertNotEqual(first["backup"], again["backup"])
        self.assertEqual(len(self.json("admin_audit.json")["events"]), 2)

    def test_invalid_reset_cannot_mutate_or_backup(self):
        before = self.json("progression.json")
        for scope in ("all", "", "global"):
            with self.assertRaises(m.MaintenanceError):
                m.reset_user(100, 7, scope, 50)
        self.assertEqual(before, self.json("progression.json"))
        self.assertEqual(m.backup_names(), [])

    def test_malformed_user_data_fails_closed_without_mutation(self):
        data = self.json("progression.json")
        data["guilds"]["100"] = ["not a guild object"]
        save_json(p.PATH, data)
        with self.assertRaises(m.MaintenanceError):
            m.reset_user(100, 7, "settings", 50)
        self.assertEqual(m.backup_names(), [])
        self.assertEqual(self.json("progression.json")["guilds"]["100"], ["not a guild object"])

    def test_backup_carries_new_admin_audit_log(self):
        m.reset_user(100, 7, "settings", 50)
        name = m.create_backup()
        verified = m.verify_backup(name)
        self.assertIn("admin_audit.json", verified)
        self.assertIn("matches.json", verified)
        self.assertIn("progression.json", verified)


class AdminUIFixtures(unittest.IsolatedAsyncioTestCase):
    async def test_admin_subcommands_registered(self):
        async with commands.Bot(command_prefix="!", intents=discord.Intents.default()) as bot:
            await bot.load_extension("cogs.menu")
            await bot.load_extension("cogs.maintenance")
            group = bot.tree.get_command("admin")
            self.assertIsInstance(group, discord.app_commands.Group)
            self.assertTrue({"panel", "backup", "repair", "health", "reset_user"} <=
                            {x.name for x in group.commands})
            self.assertIsNotNone(bot.tree.get_command("version"))
            self.assertIsNotNone(bot.tree.get_command("maintenance"))

    async def test_reset_views_include_home_and_admin_recheck(self):
        page = ui.ResetUserPage(77, 100)
        review = ui.ConfirmUserResetPage(77, 100, 88, "inventory")
        for screen in (page, review):
            self.assertIn("Main Menu", [getattr(x, "label", None) for x in screen.children])
            denied = SimpleNamespace(
                user=SimpleNamespace(id=77, guild_permissions=SimpleNamespace(manage_guild=False)),
                guild_id=100, response=SimpleNamespace(send_message=AsyncMock()),
            )
            self.assertFalse(await screen.interaction_check(denied))
            denied.response.send_message.assert_awaited_once()

    async def test_modal_wrong_confirmation_does_nothing(self):
        modal = ui.ResetConfirmation(100, 88, 77, "inventory")
        modal.confirmation._value = "RESET 99"
        intr = SimpleNamespace(
            user=SimpleNamespace(id=77, guild_permissions=SimpleNamespace(manage_guild=True)),
            guild_id=100, response=SimpleNamespace(send_message=AsyncMock()),
        )
        with patch.object(ui.store, "reset_user") as action:
            await modal.on_submit(intr)
            action.assert_not_called()
        intr.response.send_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
