from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cogs.horse import Horse, load_horses
from cogs.knight import get_knight, load_knights
from services.combat import Fighter, run_single_match
from services.arenas import ARENAS

class JoustCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    joust_group = app_commands.Group(
        name="joust",
        description="Single joust matches",
    )

    @joust_group.command(name="duel", description="Run a single joust match against another player.")
    async def duel(self, interaction: discord.Interaction, opponent: discord.Member, arena_key: str = "royal_lists"):
        await interaction.response.defer(ephemeral=False)

        if opponent.id == interaction.user.id:
            return await interaction.followup.send("❌ You cannot joust yourself.")

        if opponent.bot:
            return await interaction.followup.send("❌ You cannot joust a bot.")

        knights_db = load_knights()
        horses_db = load_horses()

        knight_a = get_knight(knights_db, interaction.user.id)
        knight_b = get_knight(knights_db, opponent.id)

        if not knight_a or not knight_b:
            return await interaction.followup.send(
                "❌ Both players need a knight. Use `/knight create`."
            )

        if not knight_a.bound_horse_id or not knight_b.bound_horse_id:
            return await interaction.followup.send(
                "❌ Both players need a bound horse. Use `/horse bind`."
            )

        horse_a_raw = horses_db.get("horses", {}).get(knight_a.bound_horse_id)
        horse_b_raw = horses_db.get("horses", {}).get(knight_b.bound_horse_id)

        if not horse_a_raw or not horse_b_raw:
            return await interaction.followup.send(
                "❌ Could not load one of the bound horses."
            )
        if arena_key not in ARENAS:
            return await interaction.followup.send(
                "❌ Unknown arena. Use `/arena list`.",
            )

        horse_a = Horse.from_dict(horse_a_raw)
        horse_b = Horse.from_dict(horse_b_raw)

        fighter_a = Fighter(
            user_id=interaction.user.id,
            knight_name=knight_a.name,
            horse_name=horse_a.name,
            knight_stats=knight_a.stats,
            horse_stats=horse_a.stats,
            lance_key=knight_a.equipped_lance_key,
            armour_key=knight_a.equipped_armour_key,
            barding_key=horse_a.equipped_barding_key,
        )

        fighter_b = Fighter(
            user_id=opponent.id,
            knight_name=knight_b.name,
            horse_name=horse_b.name,
            knight_stats=knight_b.stats,
            horse_stats=horse_b.stats,
            lance_key=knight_b.equipped_lance_key,
            armour_key=knight_b.equipped_armour_key,
            barding_key=horse_b.equipped_barding_key,
        )

        result = run_single_match(fighter_a, fighter_b, arena_key)

        e = discord.Embed(
            title="⚔️ Joust Duel",
            description=(
                f"{interaction.user.mention} vs {opponent.mention}\n"
                f"🏟️ Arena: **{result.arena_name}**"
            ),
        )

        e.add_field(
            name="Final Score",
            value=(
                f"**{result.fighter_a}**: {result.score_a}\n"
                f"**{result.fighter_b}**: {result.score_b}"
            ),
            inline=False,
        )

        e.add_field(
            name="Winner",
            value=f"**{result.winner}**",
            inline=False,
        )

        pass_lines = []
        for p in result.passes:
            line = (
                f"**Pass {p.pass_no}:** {p.result} "
                f"`+{p.points_a}/+{p.points_b}` | margin `{p.margin}`"
            )

            if p.notes:
                line += "\n" + " ".join(f"_{note}_" for note in p.notes)

            pass_lines.append(line)

        e.add_field(
            name="Passes",
            value="\n\n".join(pass_lines)[:1024],
            inline=False,
        )

        e.add_field(
            name=f"{knight_a.name}'s Gear",
            value=(
                f"Lance: `{knight_a.equipped_lance_key}`\n"
                f"Armour: `{knight_a.equipped_armour_key}`\n"
                f"Horse Barding: `{horse_a.equipped_barding_key}`"
            ),
            inline=True,
        )

        e.add_field(
            name=f"{knight_b.name}'s Gear",
            value=(
                f"Lance: `{knight_b.equipped_lance_key}`\n"
                f"Armour: `{knight_b.equipped_armour_key}`\n"
                f"Horse Barding: `{horse_b.equipped_barding_key}`"
            ),
            inline=True,
        )

        await interaction.followup.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(JoustCog(bot))