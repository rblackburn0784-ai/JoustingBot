from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.arenas import ARENAS, get_arena


class ArenaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    arena_group = app_commands.Group(
        name="arena",
        description="View jousting arenas",
    )

    @arena_group.command(name="list", description="List available arenas.")
    async def list_arenas(self, interaction: discord.Interaction):
        lines = []

        for arena in ARENAS.values():
            lines.append(
                f"• `{arena.key}` — **{arena.name}**\n"
                f"  _{arena.description}_"
            )

        e = discord.Embed(
            title="Available Arenas",
            description="\n".join(lines),
        )

        await interaction.response.send_message(embed=e, ephemeral=True)

    @arena_group.command(name="view", description="View an arena by key.")
    async def view_arena(self, interaction: discord.Interaction, arena_key: str):
        try:
            arena = get_arena(arena_key)
        except KeyError:
            return await interaction.response.send_message(
                "❌ Unknown arena. Use `/arena list`.",
                ephemeral=True,
            )

        e = discord.Embed(
            title=arena.name,
            description=arena.description,
        )

        e.add_field(name="Alignment Mod", value=f"{arena.alignment_mod:+d}", inline=True)
        e.add_field(name="Charge Mod", value=f"{arena.charge_mod:+d}", inline=True)
        e.add_field(name="Slip Mod", value=f"{arena.slip_mod:+d}", inline=True)
        e.add_field(name="Panic Mod", value=f"{arena.panic_mod:+d}", inline=True)
        e.add_field(name="Impact Multiplier", value=f"x{arena.impact_mult:.2f}", inline=True)

        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ArenaCog(bot))