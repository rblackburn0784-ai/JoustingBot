"""Admin-only maintenance panels and version command (v0.9.0)."""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

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
        self.button("Reset User", self.reset_user, row=3, style=discord.ButtonStyle.danger)
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

    async def reset_user(self, interaction):
        await navigate(interaction, ResetUserPage(interaction.user.id, interaction.guild_id))

    async def back(self, interaction):
        await navigate(interaction, AdminPage(interaction.user.id))



class ResetConfirmation(discord.ui.Modal, title="Confirm Server User Reset"):
    confirmation = discord.ui.TextInput(
        label="Type RESET followed by the target ID",
        placeholder="RESET 123456789012345678", max_length=40,
    )

    def __init__(self, guild_id, user_id, actor_id, scope):
        super().__init__()
        self.guild_id, self.user_id, self.actor_id, self.scope = guild_id, user_id, actor_id, scope

    async def on_submit(self, interaction):
        if interaction.user.id != self.actor_id or interaction.guild_id != self.guild_id or not is_admin(interaction):
            return await interaction.response.send_message("Access denied.", ephemeral=True)
        if str(self.confirmation).strip() != f"RESET {self.user_id}":
            return await interaction.response.send_message("Confirmation mismatch. Nothing changed.", ephemeral=True)
        cog = interaction.client.get_cog("MaintenanceCog")
        if cog is None:
            return await interaction.response.send_message("Maintenance unavailable.", ephemeral=True)
        async with cog.lock:
            if not idle(interaction.client):
                return await interaction.response.send_message("Matches are active. Reset blocked.", ephemeral=True)
            try:
                report = store.reset_user(self.guild_id, self.user_id, self.scope, self.actor_id)
            except (store.MaintenanceError, ValueError, OSError) as exc:
                LOG.exception("Reset refused for player %s", self.user_id)
                return await interaction.response.send_message(
                    f"Reset refused: {str(exc)[:320]}", ephemeral=True)
        view = MaintenancePage(interaction.user.id)
        await interaction.response.send_message(
            content=f"Reset completed for <@{self.user_id}> ({self.scope}). "
                    f"Verified safety backup: {report['backup']}. Match records and spending preserved.",
            embed=view.make_embed(), view=view, ephemeral=True)


class ConfirmUserResetPage(OwnedView):
    def __init__(self, actor_id, guild_id, user_id, scope):
        super().__init__(actor_id, admin=True)
        self.guild_id, self.user_id, self.scope = guild_id, user_id, scope
        self.button("Confirm Reset", self.confirm, row=0, style=discord.ButtonStyle.danger)
        self.button("Cancel", lambda it: navigate(it, MaintenancePage(it.user.id)), row=0)
        self.home()

    def make_embed(self):
        plan = store.reset_user_plan(self.guild_id, self.user_id, self.scope)
        actions = "\n".join("- " + item for item in plan["changes"]) or "No settings currently selected."
        return embed("Review Server User Reset",
                     f"Target: <@{self.user_id}>\nServer: {self.guild_id}\nScope: {self.scope}\n\n"
                     f"Changes:\n{actions}\n\nPreserved: {', '.join(plan['preserved'])}.\n\n"
                     "A verified backup is created first. Press Confirm Reset, then type "
                     "RESET followed by the target numeric ID.")

    async def confirm(self, interaction):
        if not is_admin(interaction) or interaction.guild_id != self.guild_id:
            return await interaction.response.send_message("Access denied.", ephemeral=True)
        await interaction.response.send_modal(
            ResetConfirmation(self.guild_id, self.user_id, interaction.user.id, self.scope))


class ResetMemberSelect(discord.ui.UserSelect):
    def __init__(self, page):
        self.page = page
        super().__init__(placeholder="Choose member", row=0)

    async def callback(self, interaction):
        self.page.target_id = self.values[0].id
        await interaction.response.edit_message(embed=self.page.make_embed(), view=self.page)


class ResetScopeSelect(discord.ui.Select):
    def __init__(self, page):
        self.page = page
        super().__init__(row=1, placeholder="Reset scope", options=[
            discord.SelectOption(label="Settings", value="settings", default=True,
                                 description="Remove equipped selections but keep purchases"),
            discord.SelectOption(label="Inventory", value="inventory",
                                 description="Also retire gear purchases, with no refund"),
        ])

    async def callback(self, interaction):
        self.page.scope = self.values[0]
        await interaction.response.edit_message(embed=self.page.make_embed(), view=self.page)


class ResetUserPage(OwnedView):
    def __init__(self, actor_id, guild_id):
        super().__init__(actor_id, admin=True)
        self.guild_id, self.target_id, self.scope = guild_id, None, "settings"
        self.add_item(ResetMemberSelect(self))
        self.add_item(ResetScopeSelect(self))
        self.button("Review Reset", self.review, row=2, style=discord.ButtonStyle.danger)
        self.button("Back", lambda it: navigate(it, MaintenancePage(it.user.id)), row=3)
        self.home()

    def make_embed(self):
        mention = f"<@{self.target_id}>" if self.target_id else "None"
        return embed("Server User Reset",
                     f"Member: {mention}\nScope: {self.scope}\n\n"
                     "Settings clears selected loadout, standard and title.\n"
                     "Inventory also removes unlocked-item ownership without refund.\n"
                     "Historical matches, gold already spent, injuries, tournaments, "
                     "shared characters and other servers are preserved.")

    async def review(self, interaction):
        if not is_admin(interaction) or interaction.guild_id != self.guild_id:
            return await interaction.response.send_message("Access denied.", ephemeral=True)
        if not self.target_id or interaction.guild is None:
            return await interaction.response.send_message("Select a member first.", ephemeral=True)
        if interaction.guild.get_member(self.target_id) is None:
            try:
                await interaction.guild.fetch_member(self.target_id)
            except discord.HTTPException:
                return await interaction.response.send_message("Target is not a member.", ephemeral=True)
        try:
            view = ConfirmUserResetPage(interaction.user.id, self.guild_id, self.target_id, self.scope)
            summary = view.make_embed()
        except store.MaintenanceError as exc:
            return await interaction.response.send_message(f"Reset blocked: {exc}", ephemeral=True)
        await interaction.response.edit_message(embed=summary, view=view)


class MaintenanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lock = asyncio.Lock()

    admin_group = app_commands.Group(name="admin", description="Server administration and repair")

    @admin_group.command(name="panel", description="Open the restricted administrator dashboard.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def admin_panel(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("Manage Server required.", ephemeral=True)
        view = AdminPage(interaction.user.id)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    @admin_group.command(name="health", description="Inspect persistent JSON health.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def admin_health(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("Manage Server required.", ephemeral=True)
        view = MaintenancePage(interaction.user.id)
        await interaction.response.send_message(embed=health_embed(), view=view, ephemeral=True)

    @admin_group.command(name="backup", description="Create a verified local JSON backup.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def admin_backup(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("Manage Server required.", ephemeral=True)
        async with self.lock:
            if not idle(interaction.client):
                return await interaction.response.send_message("Matches are active. Backup blocked.", ephemeral=True)
            try:
                name = store.create_backup()
            except (store.MaintenanceError, OSError) as exc:
                LOG.exception("Admin backup failed")
                return await interaction.response.send_message(
                    f"Backup blocked: {str(exc)[:300]}", ephemeral=True)
        view = MaintenancePage(interaction.user.id, name)
        await interaction.response.send_message(
            content=f"Verified local backup created: {name}.",
            embed=view.make_embed(), view=view, ephemeral=True)

    @admin_group.command(name="repair", description="Preview safe repairs requiring confirmation.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def admin_repair(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("Manage Server required.", ephemeral=True)
        try:
            plan = store.repair()
        except store.MaintenanceError as exc:
            return await interaction.response.send_message(
                f"Repair blocked: {str(exc)[:300]}", ephemeral=True)
        if not plan["changes"]:
            view = MaintenancePage(interaction.user.id)
            return await interaction.response.send_message(
                content="No safe repairs required.", embed=view.make_embed(), view=view, ephemeral=True)
        view = ConfirmPage(interaction.user.id, "repair")
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    @admin_group.command(name="reset_user", description="Safely reset server settings or gear inventory.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    @app_commands.describe(member="The server member to reset", scope="Settings, or purchased inventory without refund")
    async def admin_reset_user(self, interaction: discord.Interaction, member: discord.Member,
                               scope: Literal["settings", "inventory"] = "settings"):
        if not is_admin(interaction) or interaction.guild_id != member.guild.id:
            return await interaction.response.send_message("Manage Server required.", ephemeral=True)
        try:
            view = ConfirmUserResetPage(interaction.user.id, interaction.guild_id, member.id, scope)
            preview = view.make_embed()
        except store.MaintenanceError as exc:
            return await interaction.response.send_message(f"Reset blocked: {exc}", ephemeral=True)
        await interaction.response.send_message(embed=preview, view=view, ephemeral=True)

    @app_commands.command(name="version", description="Show bot release and stability features.")
    async def version(self, interaction: discord.Interaction):
        view = MainMenuView(interaction.user.id, is_admin(interaction))
        await interaction.response.send_message(
            embed=embed("⚙️ JoustingBot v0.9.1",
                        "Combat Tactics & Decisions\n"
                        "✅ Atomic JSON saves · verified local backups · safe repairs\n"
                        "✅ Private tactics for each rider: style, target, manoeuvre\n"
                        "✅ Fatigue, temperament and injury trade-offs · seeded replay\n"
                        "✅ Challenge cooldowns and locks · error cleanup\n"
                        "✅ Admin-only restore with confirmation\n\n"
                        "Use /admin health, /admin backup, /admin repair and /admin reset_user."),
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
