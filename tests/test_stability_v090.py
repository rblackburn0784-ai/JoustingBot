"""v0.9.0 challenge concurrency, cooldown and admin UI smoke tests."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
from discord import app_commands

from cogs.joust import JoustCog
from cogs.maintenance import MaintenancePage, ConfirmPage, MaintenanceCog, idle
from cogs.menu import AdminPage, MainMenuView
from services import maintenance as m
from main import JoustBot


class LockTests(unittest.TestCase):
    def setUp(self):
        self.cog = JoustCog(SimpleNamespace())

    def test_atomic_reservation_prevents_duplicate_active_duels(self):
        self.assertTrue(self.cog.try_lock_challenge(1, 2))
        self.assertFalse(self.cog.try_lock_challenge(1, 3))
        self.assertFalse(self.cog.try_lock_challenge(2, 4))
        self.assertFalse(self.cog.try_lock_challenge(3, 3))
        self.assertTrue(self.cog.is_player_busy(1))
        self.cog.release_challenge(1, 2)
        self.assertFalse(self.cog.is_player_busy(1))
        self.assertTrue(self.cog.try_lock_challenge(1, 3))

    def test_cooldown_applies_per_sender_and_guild(self):
        with patch("cogs.joust.time.monotonic", return_value=100.0):
            self.cog.mark_challenge_posted(10, 1)
            self.assertEqual(self.cog.cooldown_remaining(10, 1), 30)
            self.assertEqual(self.cog.cooldown_remaining(10, 2), 0)
            self.assertEqual(self.cog.cooldown_remaining(11, 1), 0)
        with patch("cogs.joust.time.monotonic", return_value=115.0):
            self.assertEqual(self.cog.cooldown_remaining(10, 1), 15)
        with patch("cogs.joust.time.monotonic", return_value=131.0):
            self.assertEqual(self.cog.cooldown_remaining(10, 1), 0)

    def test_maintenance_idle_checks_joust_and_tournament_lock(self):
        tournament_lock = asyncio.Lock()
        tour = SimpleNamespace(locks={1: tournament_lock})
        bot = SimpleNamespace(get_cog=lambda name: self.cog if name == "JoustCog" else tour)
        self.assertTrue(idle(bot))
        self.cog.try_lock_challenge(1, 2)
        self.assertFalse(idle(bot))
        self.cog.release_challenge(1, 2)


class UIPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.patches = [
            patch.object(m, "DATA_DIR", Path(self.root.name) / "storage"),
            patch.object(m, "BACKUP_DIR", Path(self.root.name) / "backups"),
        ]
        for p in self.patches:
            p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.root.cleanup()

    async def test_maintenance_is_admin_only(self):
        view = MaintenancePage(123)
        permitted = SimpleNamespace(id=123, guild_permissions=SimpleNamespace(manage_guild=True))
        forbidden = SimpleNamespace(id=123, guild_permissions=SimpleNamespace(manage_guild=False))
        foreign = SimpleNamespace(id=44, guild_permissions=SimpleNamespace(manage_guild=True))
        def interaction(user):
            return SimpleNamespace(user=user, guild_id=100,
                                   response=SimpleNamespace(send_message=AsyncMock()))
        self.assertTrue(await view.interaction_check(interaction(permitted)))
        self.assertFalse(await view.interaction_check(interaction(forbidden)))
        self.assertFalse(await view.interaction_check(interaction(foreign)))
        self.assertIn("Main Menu", [getattr(c, "label", "") for c in view.children])

    async def test_restore_confirmation_is_explicit(self):
        view = ConfirmPage(1, "restore", "bkp-20261015T120000Z-1234abcd")
        labels = [getattr(x, "label", "") for x in view.children]
        self.assertIn("Confirm Restore", labels)
        self.assertIn("Cancel", labels)
        self.assertIn("Main Menu", labels)

    async def test_main_menu_has_admin_tools_and_version(self):
        admin = AdminPage(12)
        self.assertIn("Maintenance Tools", [x.label for x in admin.children])
        self.assertNotIn("Admin", [x.label for x in MainMenuView(12, False).children])
        self.assertIn("Admin", [x.label for x in MainMenuView(12, True).children])
        self.assertTrue(hasattr(MaintenanceCog.version, "name"))

    async def test_error_handler_sends_generic_private_failure(self):
        bot = JoustBot()
        user = SimpleNamespace(id=9)
        response = SimpleNamespace(is_done=lambda: False, send_message=AsyncMock())
        interaction = SimpleNamespace(
            guild_id=10, user=user, response=response,
            command=SimpleNamespace(qualified_name="testing"),
            followup=SimpleNamespace(send=AsyncMock()),
        )
        await bot.on_app_command_error(interaction, app_commands.CheckFailure("No access"))
        response.send_message.assert_awaited_once()
        self.assertIn("not permitted", response.send_message.call_args.args[0])
        self.assertTrue(response.send_message.call_args.kwargs["ephemeral"])
        await bot.close()


if __name__ == "__main__":
    unittest.main()
