"""Admin-only maintenance panels and version command (v0.9.0)."""
from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs.menu import OwnedView, MainMenuView, AdminPage, embed, navigate, is_admin
from services import maintenance as store

LOG = logging.getLogger(__name__)


def idle(bot) -> bool:
    joust = bot.get_cog("JoustCog")
    if joust and getattr(joust, "active_challenge_players", set()):
        return False
    tournaments = bot.get_cog("TournamentCog")
    if tournaments and any(lock.locked() for lock in getattr(tournaments, "locks", {}).values()):
        return False
    return True


def health_embed() -> discord.Embed:
    data = store.inspect()
    rows = [f"{'✅' if status == 'OK' else '⚪' if status == 'MISSING' else '❌'} "
            f"{name}: {status}" for name, status in data["files"]]
    rows.extend("❌ " + issue for issue in data["errors"][:6])
    rows.extend("⚠️ " + issue for issue in data["warnings"][:6])
    return embed("🩺 Storage Health", "\n".join(rows)[:3900])


class BackupSelect(discord.ui.Select):
    def __init__(self, page):
        self.page = page
        super().__init__(
            placeholder="Select backup to restore", row=0,
            options=[discord.SelectOption(label=name, value=name, default=name == page.selected)
                     for name in store.backup_names(20)],
        )

    async def callback(self, interaction):
        self.page.selected = self.values[0]
        await interaction.response.edit_message(embed=self.page.make_embed(), view=self.page)


class ConfirmPage(OwnedView):
    def __init__(self, uid, action: str, backup: str | None = None):
        super().__init__(uid, admin=True)
        self.action = action
        self.backup = backup
        self.button("Confirm " + action.title(), self.execute, row=0,
                    style=discord.ButtonStyle.danger)
        self.button("Cancel", self.cancel, row=0)
        self.home()

    def make_embed(self):
        if self.action == "restore":
            detail = ("Overwrite current storage files with the verified snapshot "
                      + str(self.backup) + "? A pre-restore backup is created first. "
                      "This is a potentially destructive operation.")
        else:
            steps = store.repair()["changes"]
            detail = "Apply conservative JSON repairs: " + "; ".join(steps)
        return embed("⚠️ Confirm " + self.action.title(), detail)

    async def cancel(self, interaction):
        await navigate(interaction, MaintenancePage(interaction.user.id))

    async def execute(self, interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("⛔ Admin only.", ephemeral=True)
        cog = interaction.client.get_cog("MaintenanceCog")
        if cog is None:
            return await interaction.response.send_message("Maintenance unavailable.", ephemeral=True)
        async with cog.lock:
            if not idle(interaction.client):
                return await interaction.response.send_message(
                    "❌ An active challenge or tournament match is running.", ephemeral=True)
            try:
                if self.action == "restore":
                    safety = store.restore_backup(self.backup or "")
                    message = f"✅ Snapshot restored. Pre-restore safety backup: {safety}"
                else:
                    info = store.repair(apply=True)
                    message = ("✅ Repaired: " + "; ".join(info["changes"])
                               + f" · Safety backup: {info['backup']}" if info["applied"]
                               else "✅ No repairs needed.")
            except (store.MaintenanceError, ValueError, OSError) as error:
                LOG.exception("Maintenance %s failed", self.action)
                return await interaction.response.send_message(
                    f"❌ Maintenance blocked: {str(error)[:400]}", ephemeral=True)
        await navigate(interaction, MaintenancePage(interaction.user.id), message)


class MaintenancePage(OwnedView):
    def __init__(self, uid, selected=None):
        super().__init__(uid, admin=True)
        recent = store.backup_names(20)
        self.selected = selected if selected in recent else recent[0] if recent else None
        if recent:
            self.add_item(BackupSelect(self))
        self.button("Validate", self.validate, row=1, emoji="🩺")
        self.button("Create Backup", self.backup, row=1, emoji="💾")
        self.button("Review Repairs", self.repair, row=1, emoji="🛠️")
        self.button("Restore Selected", self.restore, row=2, emoji="♻️",
                    disabled=self.selected is None, style=discord.ButtonStyle.danger)
        self.button("Admin Dashboard", self.back, row=2)
        self.home()

    def make_embed(self):
        recent = store.backup_names(5)
        return embed(
            "🛠️ Admin Maintenance",
            "Requires Manage Server permission. All restores are SHA256 verified and "
            "require confirmation.\n\n"
            f"**Selected backup:** {self.selected or 'None'}\n"
            + ("\n".join(recent) if recent else "No backups yet.")
            + "\n\nSnapshots are stored locally. Keep separate off-host backups.",
        )

    async def validate(self, interaction):
        await interaction.response.edit_message(embed=health_embed(), view=self)

    async def backup(self, interaction):
        cog = interaction.client.get_cog("MaintenanceCog")
        async with cog.lock:
            if not idle(interaction.client):
                return await interaction.response.send_message("❌ Wait for matches to finish.", ephemeral=True)
            try:
                name = store.create_backup()
            except (store.MaintenanceError, OSError) as error:
                return await interaction.response.send_message(
                    f"❌ Backup rejected: {error}", ephemeral=True)
        await navigate(interaction, MaintenancePage(interaction.user.id, name),
                       f"✅ Verified snapshot saved: {name}")

    async def repair(self, interaction):
        try:
            steps = store.repair()["changes"]
        except store.MaintenanceError as error:
            return await interaction.response.send_message(f"❌ Repair refused: {error}", ephemeral=True)
        if not steps:
            return await interaction.response.send_message("✅ No repairs needed.", ephemeral=True)
        await navigate(interaction, ConfirmPage(interaction.user.id, "repair"))

    async def restore(self, interaction):
        if not self.selected:
            return await interaction.response.send_message("❌ No snapshot selected.", ephemeral=True)
        try:
            store.verify_backup(self.selected)
        except store.MaintenanceError as error:
            return await interaction.response.send_message(f"❌ Backup failed verification: {error}", ephemeral=True)
        await navigate(interaction, ConfirmPage(interaction.user.id, "restore", self.selected))

    async def back(self, interaction):
        await navigate(interaction, AdminPage(interaction.user.id))


class MaintenanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lock = asyncio.Lock()

    @app_commands.command(name="version", description="Show bot release and stability features.")
    async def version(self, interaction: discord.Interaction):
        view = MainMenuView(interaction.user.id, is_admin(interaction))
        await interaction.response.send_message(
            embed=embed("⚙️ JoustingBot v0.9.0",
                        "Stability & Admin Tools\n"
                        "✅ Atomic JSON saves · verified local backups · safe repairs\n"
                        "✅ Challenge cooldowns and locks · error cleanup\n"
                        "✅ Admin-only restore with confirmation\n\n"
                        "Use /maintenance as an admin to manage backups."),
            view=view, ephemeral=True,
        )

    @app_commands.command(name="maintenance", description="Admin: validate, back up, repair or restore data.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def maintenance(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("⛔ Manage Server required.", ephemeral=True)
        view = MaintenancePage(interaction.user.id)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(MaintenanceCog(bot))
