from __future__ import annotations

import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

INTENTS = discord.Intents.default()


class JoustBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS)

    async def setup_hook(self):
        await self.load_extension("cogs.knight")
        await self.load_extension("cogs.horse")
        await self.load_extension("cogs.equipment")
        await self.load_extension("cogs.arena")
        await self.load_extension("cogs.joust")

        await self.tree.sync()
        print("Slash commands synced.")


async def main():
    if not TOKEN:
        raise RuntimeError("Missing DISCORD_BOT_TOKEN in .env")

    bot = JoustBot()
    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())