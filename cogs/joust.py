from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.horse import Horse, load_horses
from cogs.knight import get_knight, load_knights
from services.arenas import ARENAS, get_arena
from services.combat import Fighter, PassLog, MatchResult, run_single_match
from services.equipment import get_item


# Add real hosted GIF/image URLs here later if you want animated match presentation.
# Leaving these blank is safe; the bot will simply omit images.
GIF_PLACEHOLDERS = {
    "intro": "",
    "lance_break": "",
    "solid_hit": "",
    "unhorsed": "",
    "miss": "",
    "draw": "",
    "victory": "",
}


ARENA_FLAVOUR = {
    "royal_lists": "The banners are straight, the ground is clean, and every noble eye is fixed on the rail.",
    "muddy_field": "Mud grips the hooves and spits beneath every stride. Control will matter more than pride here.",
    "frozen_ground": "The lists are glassy and cruel. One clean charge could be glorious — or disastrous.",
    "wind_swept": "Crosswinds tear at cloaks and lance tips. A steady hand may decide the day.",
    "festival_arena": "The crowd is loud, the drums are louder, and the horses can feel every cheer.",
    "war_torn": "Broken earth, battered shields and old scars turn this field into a brutal proving ground.",
}


RESULT_FLAVOUR = {
    "unhorsed": [
        "The impact lands like a thunderclap — saddle, pride and balance all vanish at once.",
        "A brutal hit crashes home and the rider is torn from the saddle before the crowd can breathe.",
        "The lance finds its mark with savage force. One knight stays mounted. The other does not.",
    ],
    "solid hit": [
        "A heavy strike lands square and rattles armour from helm to boot.",
        "The hit connects cleanly, drawing a roar from the rail and a grim nod from the marshals.",
        "Wood cracks, armour rings, and the rider absorbs a punishing blow.",
    ],
    "lance break": [
        "The lance splinters across the shield in a shower of timber.",
        "A sharp crack echoes down the lists as the lance breaks cleanly on impact.",
        "The strike is not decisive, but the broken lance earns the crowd's approval.",
    ],
    "glancing clash": [
        "The lances scrape past with a glancing clash and neither rider gives ground.",
        "A near thing — close enough to sting, not enough to score.",
        "Both riders survive the exchange with little more than scraped paint and bruised pride.",
    ],
    "Horse refused": [
        "A horse checks hard at the line, refusing the thunder of the charge.",
        "The mount will not commit. The opposing rider claims the advantage without a clean strike.",
    ],
    "Both horses refused": [
        "Both horses decide the wisest knight is the one who stays exactly where they are.",
        "The lists fall into awkward silence as neither mount accepts the charge.",
    ],
    "Double miss": [
        "Both lances cut empty air. The crowd groans as the riders thunder past untouched.",
        "A wild exchange — all speed, no steel, no score.",
    ],
    "Even clash": [
        "Both knights meet with equal force, armour ringing but neither yielding.",
        "A perfect collision of stubbornness. Neither rider gains the advantage.",
    ],
}


def equipment_name(key: Optional[str]) -> str:
    item = get_item(key)
    return item.name if item else str(key or "None")


def pick_flavour(pass_log: PassLog) -> str:
    result = pass_log.result

    for key, lines in RESULT_FLAVOUR.items():
        if key in result:
            return lines[(pass_log.pass_no - 1) % len(lines)]

    return "The pass is judged, the points are marked, and the riders wheel back for another run."


def pass_icon(pass_log: PassLog) -> str:
    result = pass_log.result.lower()

    if "unhorsed" in result:
        return "💥"
    if "solid hit" in result:
        return "🛡️"
    if "lance break" in result:
        return "🪵"
    if "miss" in result:
        return "💨"
    if "refused" in result:
        return "🐎"
    if "even" in result or "glancing" in result:
        return "⚔️"

    return "🏇"


def gif_for_result(result: MatchResult) -> str:
    if result.winner == "Draw":
        return GIF_PLACEHOLDERS.get("draw", "")

    for p in result.passes:
        if "unhorsed" in p.result.lower():
            return GIF_PLACEHOLDERS.get("unhorsed", "")
        if "solid hit" in p.result.lower():
            return GIF_PLACEHOLDERS.get("solid_hit", "")
        if "lance break" in p.result.lower():
            return GIF_PLACEHOLDERS.get("lance_break", "")

    return GIF_PLACEHOLDERS.get("victory", "")


def make_intro_embed(
    *,
    challenger: discord.Member | discord.User,
    opponent: discord.Member,
    knight_a,
    knight_b,
    horse_a: Horse,
    horse_b: Horse,
    arena_key: str,
) -> discord.Embed:
    arena = get_arena(arena_key)
    flavour = ARENA_FLAVOUR.get(arena_key, arena.description)

    e = discord.Embed(
        title="🏰 The Lists Are Open",
        description=(
            f"{challenger.mention} challenges {opponent.mention} before the crowd.\n\n"
            f"🏟️ **{arena.name}**\n"
            f"_{flavour}_"
        ),
    )

    e.add_field(
        name=f"🛡️ {knight_a.name}",
        value=(
            f"Horse: **{horse_a.name}** ({horse_a.breed})\n"
            f"Lance: **{equipment_name(knight_a.equipped_lance_key)}**\n"
            f"Armour: **{equipment_name(knight_a.equipped_armour_key)}**\n"
            f"Barding: **{equipment_name(horse_a.equipped_barding_key)}**"
        ),
        inline=True,
    )

    e.add_field(
        name=f"🛡️ {knight_b.name}",
        value=(
            f"Horse: **{horse_b.name}** ({horse_b.breed})\n"
            f"Lance: **{equipment_name(knight_b.equipped_lance_key)}**\n"
            f"Armour: **{equipment_name(knight_b.equipped_armour_key)}**\n"
            f"Barding: **{equipment_name(horse_b.equipped_barding_key)}**"
        ),
        inline=True,
    )

    e.add_field(
        name="🎺 Marshal's Call",
        value="Visors down. Lances couched. At the signal, ride hard and hold the line.",
        inline=False,
    )

    intro_gif = GIF_PLACEHOLDERS.get("intro", "")
    if intro_gif:
        e.set_image(url=intro_gif)

    return e


def make_result_embed(result: MatchResult, arena_key: str) -> discord.Embed:
    arena = get_arena(arena_key)

    if result.winner == "Draw":
        title = "⚖️ Joust Result — Honour Even"
        outcome = "No rider claims the field. The marshals call it a draw."
    else:
        title = "🏆 Joust Result — Victor Declared"
        outcome = f"**{result.winner}** claims the lists."

    e = discord.Embed(
        title=title,
        description=(
            f"🏟️ **{arena.name}**\n"
            f"{outcome}\n\n"
            f"**Final Score**\n"
            f"{result.fighter_a}: **{result.score_a}**\n"
            f"{result.fighter_b}: **{result.score_b}**"
        ),
    )

    pass_lines = []
    for p in result.passes:
        point_text = f"+{p.points_a}/+{p.points_b}"
        line = (
            f"{pass_icon(p)} **Pass {p.pass_no}** — {p.result}\n"
            f"_{pick_flavour(p)}_\n"
            f"Score: `{point_text}` · Margin: `{p.margin}`"
        )

        if p.notes:
            line += "\n" + " ".join(f"• _{note}_" for note in p.notes)

        pass_lines.append(line)

    e.add_field(
        name="📜 Pass-by-Pass Chronicle",
        value="\n\n".join(pass_lines)[:1024],
        inline=False,
    )

    if result.score_a == result.score_b:
        summary = "The match ends level, with neither rider able to force a decisive advantage."
    else:
        loser = result.fighter_b if result.winner == result.fighter_a else result.fighter_a
        summary = f"{result.winner} edges out {loser}, turning pressure into points when it mattered."

    e.add_field(
        name="🧾 Match Summary",
        value=summary,
        inline=False,
    )

    e.set_footer(text="JoustingBot v0.3 — Match Presentation Update")

    result_gif = gif_for_result(result)
    if result_gif:
        e.set_image(url=result_gif)

    return e


class JoustCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    joust_group = app_commands.Group(
        name="joust",
        description="Single joust matches",
    )

    @joust_group.command(name="duel", description="Run a cinematic single joust match against another player.")
    async def duel(self, interaction: discord.Interaction, opponent: discord.Member, arena_key: str = "royal_lists"):
        await interaction.response.defer(ephemeral=False)

        if opponent.id == interaction.user.id:
            return await interaction.followup.send("❌ You cannot joust yourself.")

        if opponent.bot:
            return await interaction.followup.send("❌ You cannot joust a bot.")

        arena_key = arena_key.strip().lower()

        if arena_key not in ARENAS:
            return await interaction.followup.send(
                "❌ Unknown arena. Use `/arena list`.",
            )

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

        intro_embed = make_intro_embed(
            challenger=interaction.user,
            opponent=opponent,
            knight_a=knight_a,
            knight_b=knight_b,
            horse_a=horse_a,
            horse_b=horse_b,
            arena_key=arena_key,
        )

        await interaction.followup.send(embed=intro_embed)

        result = run_single_match(fighter_a, fighter_b, arena_key)
        result_embed = make_result_embed(result, arena_key)

        await interaction.followup.send(embed=result_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(JoustCog(bot))