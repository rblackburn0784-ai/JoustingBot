from __future__ import annotations

import asyncio
import logging
import os
import uuid

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
INTENTS = discord.Intents.default()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOG = logging.getLogger("joustingbot")


class JoustBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS)

    async def setup_hook(self):
        for module in (
            "cogs.menu", "cogs.knight", "cogs.horse", "cogs.equipment",
            "cogs.arena", "cogs.joust", "cogs.profile", "cogs.competition",
            "cogs.tournament", "cogs.maintenance",
        ):
            await self.load_extension(module)
        await self.tree.sync()
        LOG.info("Slash commands synced.")

    async def on_app_command_error(self, interaction: discord.Interaction,
                                   error: app_commands.AppCommandError) -> None:
        """Always acknowledge failed interactions without leaking stack traces."""
        original = getattr(error, "original", error)
        if isinstance(error, app_commands.MissingPermissions):
            message = "⛔ You do not have permission to use this command."
        elif isinstance(error, app_commands.CommandOnCooldown):
            message = f"⌛ Please retry in {error.retry_after:.0f} seconds."
        elif isinstance(error, app_commands.CheckFailure):
            message = "⛔ This command is not permitted here."
        elif isinstance(error, (app_commands.CommandNotFound,)):
            message = "❌ This command is no longer available. Try /menu."
        else:
            incident = uuid.uuid4().hex[:8]
            LOG.error(
                "Command error reference %s, command=%s, guild=%s, user=%s",
                incident, getattr(interaction.command, "qualified_name", "unknown"),
                interaction.guild_id, interaction.user.id,
                exc_info=(type(original), original, original.__traceback__),
            )
            message = f"⚠️ That action failed. Reference: {incident}. An admin can check the bot logs."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            LOG.warning("Could not notify user of command failure.")


async def main():
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_BOT_TOKEN in .env")
    async with JoustBot() as bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
