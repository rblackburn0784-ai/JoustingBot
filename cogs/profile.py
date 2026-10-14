from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cogs.knight import get_knight, load_knights
from cogs.horse import Horse, load_horses
from services.records import knight_record, horse_record, latest_matches
from services.competition import equipped_title

def knight_stats_embed(member: discord.abc.User) -> discord.Embed:
    knight = get_knight(load_knights(), member.id)
    stats = knight_record(member.id)
    e = discord.Embed(title=f"⚔️ {knight.name if knight else member.display_name} — Career")
    guild = getattr(member, "guild", None)
    current_title = equipped_title(guild.id, member.id) if guild else None
    e.description = f"Rider: {member.mention}" + (f"\n🏅 **{current_title}**" if current_title else "")
    e.add_field(name="Record", value=f"🏆 {stats['wins']} W  ·  {stats['losses']} L  ·  {stats['draws']} D\nJousts: **{stats['jousts_completed']}**", inline=False)
    e.add_field(name="Highlights", value=f"Unhorsings caused: **{stats['unhorsings_caused']}**\nTimes unhorsed: **{stats['times_unhorsed']}**\nLance breaks: **{stats['lance_breaks']}**", inline=False)
    return e

def horse_stats_embed(horse: Horse) -> discord.Embed:
    stats = horse_record(horse.horse_id)
    e = discord.Embed(title=f"🐎 {horse.name} — Career", description=f"{horse.breed} · `{horse.horse_id}`")
    e.add_field(name="Career", value=f"Jousts: **{stats['jousts_run']}**\nWins with rider: **{stats['wins_with_rider']}**\nRefusals: **{stats['refusals']}**\nSlips: **{stats['slips']}**", inline=False)
    return e

def history_lines(user_id: int) -> str:
    rows = []
    for m in latest_matches(user_id):
        mine, other = ("a", "b") if m["a"]["user_id"] == user_id else ("b", "a")
        a, b = m[mine], m[other]
        verdict = "Draw" if a["score"] == b["score"] else ("Win" if a["score"] > b["score"] else "Loss")
        rows.append(f"**{verdict}** · {a['knight']} {a['score']}–{b['score']} {b['knight']}\n🏟️ {m['arena_name']} · <t:{int(__import__('datetime').datetime.fromisoformat(m['timestamp']).timestamp())}:d>")
    return "\n".join(rows) if rows else "No completed jousts yet."

class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View a rider's career and last five jousts.")
    async def profile(self, interaction: discord.Interaction, player: discord.Member | None = None):
        member = player or interaction.user
        embed = knight_stats_embed(member)
        knight = get_knight(load_knights(), member.id)
        if knight and knight.bound_horse_id:
            raw = load_horses().get("horses", {}).get(knight.bound_horse_id)
            if raw:
                horse = Horse.from_dict(raw)
                h = horse_record(horse.horse_id)
                embed.add_field(name="🐎 Current Mount", value=f"**{horse.name}** · {h['jousts_run']} jousts · {h['wins_with_rider']} wins", inline=False)
        embed.add_field(name="📜 Last Five Matches", value=history_lines(member.id), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
