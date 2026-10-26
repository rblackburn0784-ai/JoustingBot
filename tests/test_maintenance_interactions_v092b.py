"""Regression: storage-backed Discord admin interactions acknowledge before IO.

These checks use mocked interactions and a fake storage layer; no Discord
token, server, user records, or real backup files are touched.
"""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from cogs import maintenance as ui


def interaction():
    response = SimpleNamespace(
        defer=AsyncMock(),
        send_message=AsyncMock(),
        edit_message=AsyncMock(),
    )
    return SimpleNamespace(
        user=SimpleNamespace(
            id=99,
            guild_permissions=SimpleNamespace(manage_guild=True),
        ),
        guild_id=123,
        response=response,
        edit_original_response=AsyncMock(),
        followup=SimpleNamespace(send=AsyncMock()),
        client=SimpleNamespace(get_cog=lambda name: None),
    )


class AcknowledgementTests(unittest.IsolatedAsyncioTestCase):
    async def test_slash_repair_defers_before_preview_without_applying(self):
        intr = interaction()
        cog = ui.MaintenanceCog(SimpleNamespace())
        called = []

        def preview(*, apply=False):
            self.assertEqual(intr.response.defer.await_count, 1)
            self.assertFalse(apply)
            called.append("preview")
            return {"changes": ["Create missing matches.json."],
                    "applied": False, "backup": None}

        with patch.object(ui.store, "repair", side_effect=preview):
            await ui.MaintenanceCog.admin_repair.callback(cog, intr)
        intr.response.defer.assert_awaited_once_with(thinking=True, ephemeral=True)
        intr.edit_original_response.assert_awaited_once()
        intr.response.send_message.assert_not_awaited()
        self.assertEqual(called, ["preview"])
        kwargs = intr.edit_original_response.await_args.kwargs
        self.assertIn("Create missing matches.json.", kwargs["embed"].description)
        self.assertIsInstance(kwargs["view"], ui.ConfirmPage)

    async def test_slash_repair_rejected_plan_is_private_and_does_not_apply(self):
        intr = interaction()
        cog = ui.MaintenanceCog(SimpleNamespace())
        with patch.object(ui.store, "repair", side_effect=ui.store.MaintenanceError(
                "damaged records")):
            await ui.MaintenanceCog.admin_repair.callback(cog, intr)
        intr.response.defer.assert_awaited_once()
        self.assertIn("Repair blocked", intr.edit_original_response.await_args.kwargs["content"])
        intr.response.send_message.assert_not_awaited()

    async def test_confirm_button_defers_before_work_and_calls_apply_true(self):
        intr = interaction()
        cog = ui.MaintenanceCog(SimpleNamespace())
        intr.client.get_cog = lambda name: cog if name == "MaintenanceCog" else None
        def apply(*, apply=False):
            self.assertEqual(intr.response.defer.await_count, 1)
            self.assertTrue(apply)
            return {"changes": ["Create missing matches.json."],
                    "applied": True, "backup": "bkp-test"}

        view = ui.ConfirmPage(99, "repair", steps=["Create missing matches.json."])
        with patch.object(ui, "idle", return_value=True), \
             patch.object(ui.store, "repair", side_effect=apply), \
             patch.object(ui.store, "backup_names", return_value=[]):
            await view.execute(intr)
        intr.response.defer.assert_awaited_once()
        intr.edit_original_response.assert_awaited_once()
        self.assertIn("Safety backup: bkp-test",
                      intr.edit_original_response.await_args.kwargs["content"])

    async def test_review_repairs_button_acknowledges_first(self):
        intr = interaction()
        view = ui.MaintenancePage(99)
        def preview(*, apply=False):
            self.assertEqual(intr.response.defer.await_count, 1)
            self.assertFalse(apply)
            return {"changes": ["Create missing titles.json."]}
        with patch.object(ui.store, "repair", side_effect=preview):
            await view.repair(intr)
        intr.response.defer.assert_awaited_once()
        intr.edit_original_response.assert_awaited_once()

    async def test_slash_backup_defers_before_file_copy(self):
        intr = interaction()
        cog = ui.MaintenanceCog(SimpleNamespace())
        def backup():
            self.assertEqual(intr.response.defer.await_count, 1)
            return "bkp-test"
        with patch.object(ui, "idle", return_value=True), \
             patch.object(ui.store, "create_backup", side_effect=backup), \
             patch.object(ui.store, "backup_names", return_value=[]):
            await ui.MaintenanceCog.admin_backup.callback(cog, intr)
        intr.response.defer.assert_awaited_once_with(thinking=True, ephemeral=True)
        self.assertIn("bkp-test", intr.edit_original_response.await_args.kwargs["content"])

    async def test_slash_health_defers_before_storage_inspection(self):
        intr = interaction()
        cog = ui.MaintenanceCog(SimpleNamespace())
        def health():
            self.assertEqual(intr.response.defer.await_count, 1)
            return discord.Embed(title="Health OK")
        with patch.object(ui, "health_embed", side_effect=health), \
             patch.object(ui.store, "backup_names", return_value=[]):
            await ui.MaintenanceCog.admin_health.callback(cog, intr)
        intr.response.defer.assert_awaited_once_with(thinking=True, ephemeral=True)
        self.assertEqual(intr.edit_original_response.await_args.kwargs["embed"].title,
                         "Health OK")


if __name__ == "__main__":
    unittest.main()
