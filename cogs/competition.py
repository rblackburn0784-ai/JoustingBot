"""Public guild leaderboards and personal title management (v0.7)."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.competition import (
    CATEGORIES, TITLE_RULES, equipped_title, ranked, set_title, title_progress,
)


async def require_guild(interaction: discord.Interaction) -> int | None:
    if interaction.guild_id is None:
        await interaction.response.send_message(
            "❌ Leaderboards and titles are available inside a server only.", ephemeral=True
        )
        return None
    return interaction.guild_id


class CompetitionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    leaderboard_group = app_commands.Group(
        name="leaderboard", description="Jousting rankings for this Discord server"
    )
    title_group = app_commands.Group(
        name="title", description="Equip or remove a title you've earned"
    )

    async def show_board(self, interaction: discord.Interaction, key: str) -> None:
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        rows = ranked(guild_id, key)
        e = discord.Embed(
            title=f"🏆 {CATEGORIES[key]}",
            description=f"**{interaction.guild.name}** · Top 10\nRankings use completed jousts recorded in this server.",
            colour=discord.Colour.gold(),
        )
        if not rows:
            e.add_field(
                name="No qualifying contenders yet",
                value="Finish some accepted jousts to appear here. Minimum match counts apply to win rate and horse/arena rankings.",
                inline=False,
            )
        else:
            lines = []
            for pos, row in enumerate(rows, 1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"{pos}.")
                if "owner_id" in row:
                    display = f"**{discord.utils.escape_markdown(row['name'])}** (owner <@{row['owner_id']}>)"
                else:
                    title = equipped_title(guild_id, row["id"])
                    suffix = f" · *{title}*" if title else ""
                    display = f"**{discord.utils.escape_markdown(row['name'])}** (<@{row['id']}>)" + suffix
                lines.append(f"{medal} {display}\n      {row['detail']}")
            e.add_field(name="Standings", value="\n".join(lines)[:1024], inline=False)
        if key == "winrate":
            e.set_footer(text="Win rate = wins ÷ completed jousts; 5+ jousts required.")
        elif key == "reliable_horse":
            e.set_footer(text="Clean = a joust without refusal/slip; 5+ jousts required.")
        elif key == "chaotic_horse":
            e.set_footer(text="Incidents per joust = (refusals + slips) ÷ jousts; 3+ required.")
        elif key == "arena":
            e.set_footer(text="Each rider's strongest arena; minimum 3 appearances in that arena.")
        else:
            e.set_footer(text="JoustingBot v0.7 — Leaderboards & Titles")
        await interaction.response.send_message(embed=e)

    @leaderboard_group.command(name="wins", description="Rank knights by number of wins.")
    async def wins(self, interaction: discord.Interaction):
        await self.show_board(interaction, "wins")

    @leaderboard_group.command(name="winrate", description="Best win rates, minimum five jousts.")
    async def winrate(self, interaction: discord.Interaction):
        await self.show_board(interaction, "winrate")

    @leaderboard_group.command(name="unhorsings", description="Rank knights by unhorsings caused.")
    async def unhorsings(self, interaction: discord.Interaction):
        await self.show_board(interaction, "unhorsings")

    @leaderboard_group.command(name="lancebreaks", description="Rank knights by lance breaks.")
    async def lancebreaks(self, interaction: discord.Interaction):
        await self.show_board(interaction, "lancebreaks")

    @leaderboard_group.command(name="jousts", description="Most completed jousts.")
    async def jousts(self, interaction: discord.Interaction):
        await self.show_board(interaction, "jousts")

    @leaderboard_group.command(name="reliable_horse", description="Horses with the highest clean-joust rates.")
    async def reliable_horse(self, interaction: discord.Interaction):
        await self.show_board(interaction, "reliable_horse")

    @leaderboard_group.command(name="chaotic_horse", description="Horses with the most incidents per joust.")
    async def chaotic_horse(self, interaction: discord.Interaction):
        await self.show_board(interaction, "chaotic_horse")

    @leaderboard_group.command(name="arena", description="Knights with the most wins at their best arena.")
    async def arena(self, interaction: discord.Interaction):
        await self.show_board(interaction, "arena")

    @app_commands.command(name="titles", description="See your earned and locked titles.")
    async def titles(self, interaction: discord.Interaction):
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        progress = title_progress(guild_id, interaction.user.id)
        wearing = equipped_title(guild_id, interaction.user.id)
        e = discord.Embed(
            title="🏅 Your Titles",
            description=f"{interaction.user.mention} · Equipped: **{wearing or 'None'}**",
            colour=discord.Colour.gold(),
        )
        lines = []
        for key, info in progress.items():
            icon = "✅" if info["earned"] else "🔒"
            lines.append(
                f"{icon} **{info['name']}** — {info['progress']}/{info['required']}\n"
                f"      {info['description']}"
            )
        e.add_field(name="Progress", value="\n".join(lines)[:1024], inline=False)
        e.set_footer(text="Earn titles with completed server jousts, then use /title equip.")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @title_group.command(name="equip", description="Display one of your earned titles.")
    @app_commands.choices(title=[
        app_commands.Choice(name=display, value=key)
        for key, (display, _description, _field, _threshold) in TITLE_RULES.items()
    ])
    async def equip(self, interaction: discord.Interaction, title: str):
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        if title not in TITLE_RULES:
            return await interaction.response.send_message("❌ Unknown title.", ephemeral=True)
        try:
            set_title(guild_id, interaction.user.id, title)
        except ValueError as exc:
            return await interaction.response.send_message(f"🔒 {exc}", ephemeral=True)
        await interaction.response.send_message(
            f"🏅 Equipped **{TITLE_RULES[title][0]}**! This now appears alongside your name on this server's leaderboards and profile.",
            ephemeral=True,
        )

    @title_group.command(name="unequip", description="Remove your displayed title.")
    async def unequip(self, interaction: discord.Interaction):
        guild_id = await require_guild(interaction)
        if guild_id is None:
            return
        set_title(guild_id, interaction.user.id, None)
        await interaction.response.send_message("✅ Title unequipped.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CompetitionCog(bot))
