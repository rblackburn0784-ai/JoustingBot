from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.horse import Horse, load_horses
from cogs.knight import get_knight, load_knights
from services.arenas import ARENAS, get_arena
from services.combat import Fighter, MatchResult, PassLog, run_single_match
from services.tactics import TacticPlan, STYLES, TARGETS, MOVES, label as tactic_label
from services.equipment import get_item
from services.records import record_match
from services.progression import loadout, equipped_standard
from services.injuries import (
    apply_penalty, active as active_injuries, duration as injury_duration,
    support_for_next_bout, risk_profile,
)


VERSION_LABEL = "JoustingBot v0.9.2 — Cinematic Matchday Broadcast"
CHALLENGE_TIMEOUT_SECONDS = 240


# Add real hosted GIF/image URLs here later if you want animated match presentation.
# Leaving these blank is safe; the bot will simply omit images.
GIF_PLACEHOLDERS = {
    "intro": "",
    "lance_break": "",
    "heavy_shield_hit": "",
    "saddle_stagger": "",
    "unhorsing": "",
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
    "clean_miss": [
        "The horses thunder past, but both lance tips cut empty air.",
        "A wild pass. Plenty of speed, no clean contact, and the crowd lets them hear it.",
    ],
    "shield_scrape": [
        "The lance skims across the shield, close enough to sting but not enough to score.",
        "A scrape of wood and paint marks the shield, but the marshals wave away the point.",
    ],
    "lance_break": [
        "The lance splinters across the shield in a shower of timber.",
        "A sharp crack echoes down the lists as the lance breaks cleanly on impact.",
    ],
    "heavy_shield_hit": [
        "A heavy strike lands square and rattles armour from helm to boot.",
        "The blow crashes into the shield with enough force to turn the rider in the saddle.",
    ],
    "saddle_stagger": [
        "The rider nearly goes. One boot kicks loose before they drag themselves back into the seat.",
        "The saddle rocks, the crowd rises, but the rider somehow clings on.",
    ],
    "unhorsing": [
        "The impact lands like a thunderclap — saddle, pride and balance all vanish at once.",
        "A brutal hit crashes home and the rider is torn from the saddle before the crowd can breathe.",
    ],
    "horse_refusal": [
        "The horse checks hard at the line, refusing the thunder of the charge.",
        "The mount will not commit. The opposing rider claims the advantage without a clean strike.",
    ],
    "horse_slip": [
        "Hooves skid out from under the charge and the pass collapses before the lance can tell its story.",
        "The mount loses the ground, and with it goes the chance of a clean strike.",
    ],
    "double_clash": [
        "Both knights meet with equal force, armour ringing but neither yielding.",
        "A perfect collision of stubbornness. Neither rider gains the advantage.",
    ],
}


@dataclass
class PreparedDuel:
    challenger: discord.Member | discord.User
    opponent: discord.Member
    arena_key: str
    knight_a: object
    knight_b: object
    horse_a: Horse
    horse_b: Horse
    fighter_a: Fighter
    fighter_b: Fighter
    seed: Optional[int] = None
    debug_requested: bool = False
    guild_id: Optional[int] = None
    mode: str = "instant"
    support_token_a: Optional[str] = None
    support_token_b: Optional[str] = None
    had_injury_a: bool = False
    had_injury_b: bool = False
    tactics_a: TacticPlan = field(default_factory=TacticPlan)
    tactics_b: TacticPlan = field(default_factory=TacticPlan)
    tactics_ready: set[int] = field(default_factory=set)


def equipment_name(key: Optional[str]) -> str:
    item = get_item(key)
    return item.name if item else str(key or "None")


def stats_line(stats: dict[str, int]) -> str:
    return " · ".join(f"{key[:3].title()} {value}" for key, value in stats.items())


def total_stats(stats: dict[str, int]) -> int:
    return sum(int(v) for v in stats.values())


def pick_flavour(pass_log: PassLog) -> str:
    lines = RESULT_FLAVOUR.get(pass_log.category)
    if lines:
        return lines[(pass_log.pass_no - 1) % len(lines)]
    return "The pass is judged, the points are marked, and the riders wheel back for another run."


def pass_icon(pass_log: PassLog) -> str:
    icons = {
        "clean_miss": "💨",
        "shield_scrape": "🛡️",
        "lance_break": "🪵",
        "heavy_shield_hit": "💢",
        "saddle_stagger": "😬",
        "unhorsing": "💥",
        "horse_refusal": "🐎",
        "horse_slip": "🧊",
        "double_clash": "⚔️",
    }
    return icons.get(pass_log.category, "🏇")


def gif_for_result(result: MatchResult) -> str:
    if result.winner == "Draw":
        return GIF_PLACEHOLDERS.get("draw", "")

    priority = ["unhorsing", "saddle_stagger", "heavy_shield_hit", "lance_break", "clean_miss"]
    for category in priority:
        if any(p.category == category for p in result.passes):
            if category == "clean_miss":
                return GIF_PLACEHOLDERS.get("miss", "")
            return GIF_PLACEHOLDERS.get(category, "")

    return GIF_PLACEHOLDERS.get("victory", "")


def make_intro_embed(prepared: PreparedDuel) -> discord.Embed:
    arena = get_arena(prepared.arena_key)
    flavour = ARENA_FLAVOUR.get(prepared.arena_key, arena.description)

    e = discord.Embed(
        title="🏰 The Lists Are Open",
        description=(
            f"{prepared.challenger.mention} faces {prepared.opponent.mention} before the crowd.\n\n"
            f"🏟️ **{arena.name}**\n"
            f"_{flavour}_"
        ),
    )

    e.add_field(
        name=f"🛡️ {prepared.knight_a.name}",
        value=(
            f"Horse: **{prepared.horse_a.name}** ({prepared.horse_a.breed})\n"
            f"Lance: **{equipment_name(prepared.knight_a.equipped_lance_key)}**\n"
            f"Armour: **{equipment_name(prepared.knight_a.equipped_armour_key)}**\n"
            f"Barding: **{equipment_name(prepared.horse_a.equipped_barding_key)}**"
        ),
        inline=True,
    )

    e.add_field(
        name=f"🛡️ {prepared.knight_b.name}",
        value=(
            f"Horse: **{prepared.horse_b.name}** ({prepared.horse_b.breed})\n"
            f"Lance: **{equipment_name(prepared.knight_b.equipped_lance_key)}**\n"
            f"Armour: **{equipment_name(prepared.knight_b.equipped_armour_key)}**\n"
            f"Barding: **{equipment_name(prepared.horse_b.equipped_barding_key)}**"
        ),
        inline=True,
    )

    e.add_field(
        name="🧠 Revealed Tactics",
        value=f"**{prepared.knight_a.name}:** {tactic_label(prepared.tactics_a)}\n"
              f"**{prepared.knight_b.name}:** {tactic_label(prepared.tactics_b)}",
        inline=False,
    )

    if prepared.guild_id is not None:
        standard_a = equipped_standard(prepared.guild_id, prepared.challenger.id)
        standard_b = equipped_standard(prepared.guild_id, prepared.opponent.id)
        if standard_a or standard_b:
            e.add_field(
                name="🚩 Standards",
                value=f"{prepared.knight_a.name}: **{standard_a or 'None'}**\n"
                      f"{prepared.knight_b.name}: **{standard_b or 'None'}**",
                inline=False,
            )

    if prepared.guild_id is not None:
        for user_id, name in ((prepared.challenger.id, prepared.knight_a.name),
                              (prepared.opponent.id, prepared.knight_b.name)):
            injury_list = active_injuries(prepared.guild_id, user_id)
            if injury_list:
                e.add_field(
                    name=f"🩹 {name} — recovering",
                    value="\n".join(
                        f"{inj['name']} ({injury_duration(inj['remaining_seconds'])})"
                        for inj in injury_list[:3]
                    )[:1024],
                    inline=False,
                )

    seed_text = f"Seed `{prepared.seed}`" if prepared.seed is not None else "Seed will be generated at match start."
    e.add_field(
        name="🎺 Marshal's Call",
        value=f"Visors down. Lances couched. At the signal, ride hard and hold the line.\n{seed_text}",
        inline=False,
    )

    intro_gif = GIF_PLACEHOLDERS.get("intro", "")
    if intro_gif:
        e.set_image(url=intro_gif)

    e.set_footer(text=VERSION_LABEL)
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
            f"{result.fighter_b}: **{result.score_b}**\n"
            f"🎲 Seed: `{result.seed}`"
        ),
    )

    pass_lines = []
    for p in result.passes:
        point_text = f"+{p.points_a}/+{p.points_b}"
        line = (
            f"{pass_icon(p)} **Pass {p.pass_no}** — {p.result}\n"
            f"_{p.arena_line}_\n"
            f"_{pick_flavour(p)}_\n"
            f"_{p.gear_line}_\n"
            f"Score: `{point_text}` · Margin: `{p.margin}`"
        )

        if p.notes:
            line += "\n" + " ".join(f"• _{note}_" for note in p.notes)

        pass_lines.append(line)

    # One embed field per pass avoids Discord silently truncating later tactical
    # decisions after the first 1024 characters of a combined chronicle.
    for pass_no, line in enumerate(pass_lines, 1):
        e.add_field(
            name=f"📜 Pass {pass_no} — Chronicle",
            value=line[:1024] or "No pass details.",
            inline=False,
        )

    e.add_field(
        name="🧠 Tactical Plans",
        value=f"**{result.fighter_a}:** {tactic_label(getattr(result, 'tactics_a', TacticPlan()))}\n"
              f"**{result.fighter_b}:** {tactic_label(getattr(result, 'tactics_b', TacticPlan()))}",
        inline=False,
    )

    if result.score_a == result.score_b:
        summary = "The match ends level, with neither rider able to force a decisive advantage."
    else:
        loser = result.fighter_b if result.winner == result.fighter_a else result.fighter_a
        summary = f"{result.winner} edges out {loser}, turning pressure into points when it mattered."

    e.add_field(name="🧾 Match Summary", value=summary, inline=False)
    e.set_footer(text=VERSION_LABEL)

    result_gif = gif_for_result(result)
    if result_gif:
        e.set_image(url=result_gif)

    return e


def make_debug_embed(result: MatchResult) -> discord.Embed:
    e = discord.Embed(
        title="🧪 Hidden Debug Roll Breakdown",
        description=f"Seed: `{result.seed}`\nThis is intended for admin/debug tuning only.",
    )

    for p in result.passes:
        debug_text = "\n".join(p.debug_rolls) or "No debug rolls captured."
        e.add_field(
            name=f"Pass {p.pass_no} — {p.category}",
            value=debug_text[:1024],
            inline=False,
        )

    e.set_footer(text=VERSION_LABEL)
    return e


def preview_risk(prepared: PreparedDuel) -> str:
    """Approximate unhorsing injury risk before acceptance; no new RNG rolls."""
    record = {
        "arena_key": prepared.arena_key,
        "a": {
            "gear": {
                "lance": prepared.fighter_a.lance_key,
                "armour": prepared.fighter_a.armour_key,
                "barding": prepared.fighter_a.barding_key,
            },
            "horse_breed": prepared.horse_a.breed,
            "horse_stats": prepared.horse_a.stats,
            "already_injured": bool(active_injuries(prepared.guild_id, prepared.challenger.id)),
        },
        "b": {
            "gear": {
                "lance": prepared.fighter_b.lance_key,
                "armour": prepared.fighter_b.armour_key,
                "barding": prepared.fighter_b.barding_key,
            },
            "horse_breed": prepared.horse_b.breed,
            "horse_stats": prepared.horse_b.stats,
            "already_injured": bool(active_injuries(prepared.guild_id, prepared.opponent.id)),
        },
    }
    odds_a = risk_profile(record, "a", "b", "unhorsing")["chance"]
    odds_b = risk_profile(record, "b", "a", "unhorsing")["chance"]
    return (
        f"**{prepared.knight_a.name}:** {odds_a}% if unhorsed\n"
        f"**{prepared.knight_b.name}:** {odds_b}% if unhorsed\n"
        "Illustrative risk *if an unhorsing happens*; other impacts use lower base odds."
    )


def make_challenge_embed(prepared: PreparedDuel) -> discord.Embed:
    arena = get_arena(prepared.arena_key)
    flavour = ARENA_FLAVOUR.get(prepared.arena_key, arena.description)

    e = discord.Embed(
        title="⚔️ Joust Challenge Issued",
        description=(
            f"{prepared.challenger.mention} has challenged {prepared.opponent.mention} to the lists.\n\n"
            f"🏟️ **Arena:** {arena.name}\n"
            f"_{flavour}_\n\n"
            f"{prepared.opponent.mention}, do you accept?"
        ),
    )

    e.add_field(
        name=f"Challenger — {prepared.knight_a.name}",
        value=(
            f"Horse: **{prepared.horse_a.name}** ({prepared.horse_a.breed})\n"
            f"Knight total: **{total_stats(prepared.knight_a.stats)}** · Horse total: **{total_stats(prepared.horse_a.stats)}**\n"
            f"Knight: `{stats_line(prepared.knight_a.stats)}`\n"
            f"Horse: `{stats_line(prepared.horse_a.stats)}`\n"
            f"Gear: {equipment_name(prepared.knight_a.equipped_lance_key)}, {equipment_name(prepared.knight_a.equipped_armour_key)}, {equipment_name(prepared.horse_a.equipped_barding_key)}"
        ),
        inline=False,
    )
    e.add_field(
        name=f"Opponent — {prepared.knight_b.name}",
        value=(
            f"Horse: **{prepared.horse_b.name}** ({prepared.horse_b.breed})\n"
            f"Knight total: **{total_stats(prepared.knight_b.stats)}** · Horse total: **{total_stats(prepared.horse_b.stats)}**\n"
            f"Knight: `{stats_line(prepared.knight_b.stats)}`\n"
            f"Horse: `{stats_line(prepared.horse_b.stats)}`\n"
            f"Gear: {equipment_name(prepared.knight_b.equipped_lance_key)}, {equipment_name(prepared.knight_b.equipped_armour_key)}, {equipment_name(prepared.horse_b.equipped_barding_key)}"
        ),
        inline=False,
    )
    e.add_field(
        name="Arena Modifiers",
        value=(
            f"Alignment `{arena.alignment_mod:+d}` · Charge `{arena.charge_mod:+d}` · "
            f"Slip `{arena.slip_mod:+d}` · Panic `{arena.panic_mod:+d}` · Impact `x{arena.impact_mult:.2f}`"
        ),
        inline=False,
    )
    e.add_field(name="🩹 Injury Risk Preview", value=preview_risk(prepared), inline=False)
    ra = prepared.challenger.id in prepared.tactics_ready
    rb = prepared.opponent.id in prepared.tactics_ready
    e.add_field(name="🧠 Private Tactics", value=(
        f"{prepared.knight_a.name}: {'✅ Locked' if ra else '⌛ Choose Tactics'}\n"
        f"{prepared.knight_b.name}: {'✅ Locked' if rb else '⌛ Choose Tactics'}\n"
        "**Both riders must lock their private tactics before the opponent can accept.**"
    ), inline=False)
    seed_text = f"Seed `{prepared.seed}`" if prepared.seed is not None else "Random seed will be generated when accepted."
    e.add_field(
        name="Challenge Rules",
        value=f"Expires in {CHALLENGE_TIMEOUT_SECONDS} seconds. {seed_text}",
        inline=False,
    )

    e.set_footer(text=VERSION_LABEL)
    return e


def make_challenge_closed_embed(prepared: PreparedDuel, title: str, description: str) -> discord.Embed:
    arena = get_arena(prepared.arena_key)
    e = discord.Embed(title=title, description=description)
    e.add_field(name="Arena", value=arena.name, inline=True)
    e.add_field(name="Challenger", value=prepared.knight_a.name, inline=True)
    e.add_field(name="Opponent", value=prepared.knight_b.name, inline=True)
    e.set_footer(text=VERSION_LABEL)
    return e


class ChallengeHomeView(discord.ui.View):
    """A public return-to-menu button; each click opens a private hub."""
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Main Menu", emoji="🏰", style=discord.ButtonStyle.success, row=1)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import MainMenuView, is_admin
        view = MainMenuView(interaction.user.id, is_admin(interaction))
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)


class ChallengeView(discord.ui.View):
    def __init__(self, cog: "JoustCog", prepared: PreparedDuel):
        super().__init__(timeout=CHALLENGE_TIMEOUT_SECONDS)
        self.cog = cog
        self.prepared = prepared
        self.message: Optional[discord.Message] = None
        self.completed = False

    async def on_timeout(self) -> None:
        if self.completed:
            return

        self.completed = True
        self.cog.release_challenge(self.prepared.challenger.id, self.prepared.opponent.id)

        for item in self.children:
            item.disabled = True

        if self.message:
            embed = make_challenge_closed_embed(
                self.prepared,
                "⌛ Joust Challenge Expired",
                f"{self.prepared.opponent.mention} did not answer the challenge in time.",
            )
            try:
                await self.message.edit(embed=embed, view=ChallengeHomeView())
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Main Menu", emoji="🏰", style=discord.ButtonStyle.secondary, row=1)
    async def home_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import MainMenuView, is_admin
        view = MainMenuView(interaction.user.id, is_admin(interaction))
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    @discord.ui.button(label="Choose Tactics", emoji="🧠", style=discord.ButtonStyle.primary)
    async def choose_tactics(self, interaction: discord.Interaction, button: discord.ui.Button):
        prepared = self.prepared
        if self.completed or interaction.user.id not in (prepared.challenger.id, prepared.opponent.id):
            return await interaction.response.send_message(
                "❌ Only active challenge participants can select tactics.", ephemeral=True)
        from cogs.tactic_ui import TacticEditor
        current = prepared.tactics_a if interaction.user.id == prepared.challenger.id else prepared.tactics_b
        panel = TacticEditor(self, interaction.user.id, current)
        await interaction.response.send_message(embed=panel.make_embed(), view=panel, ephemeral=True)

    @discord.ui.button(label="Accept Challenge", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.prepared.opponent.id:
            return await interaction.response.send_message("❌ Only the challenged player can accept this joust.", ephemeral=True)

        if self.completed:
            return await interaction.response.send_message("❌ This challenge is already closed.", ephemeral=True)
        if self.prepared.tactics_ready != {self.prepared.challenger.id, self.prepared.opponent.id}:
            return await interaction.response.send_message(
                "🧠 Both riders must choose and **Lock Tactics** before accepting.",
                ephemeral=True)
        self.completed = True

        for item in self.children:
            item.disabled = True

        accepted_embed = make_challenge_closed_embed(
            self.prepared,
            "✅ Challenge Accepted",
            f"{self.prepared.opponent.mention} accepts {self.prepared.challenger.mention}'s challenge. The riders take the field.",
        )

        try:
            await interaction.response.edit_message(embed=accepted_embed, view=ChallengeHomeView())
            result = await self.cog.send_match(interaction.followup, self.prepared)
            if self.prepared.debug_requested:
                await interaction.followup.send(embed=make_debug_embed(result), ephemeral=True)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Accepted challenge interaction failed")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "⚠️ The challenge could not finish; please ask an admin to check the bot logs.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        "⚠️ The challenge could not finish.", ephemeral=True,
                    )
            except discord.HTTPException:
                pass
        finally:
            self.cog.release_challenge(self.prepared.challenger.id, self.prepared.opponent.id)
            self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in {self.prepared.challenger.id, self.prepared.opponent.id}:
            return await interaction.response.send_message("❌ This challenge is not yours to decline.", ephemeral=True)

        if self.completed:
            return await interaction.response.send_message("❌ This challenge is already closed.", ephemeral=True)
        self.completed = True
        self.cog.release_challenge(self.prepared.challenger.id, self.prepared.opponent.id)

        for item in self.children:
            item.disabled = True

        declined_by = "challenger" if interaction.user.id == self.prepared.challenger.id else "opponent"
        embed = make_challenge_closed_embed(self.prepared, "❌ Challenge Declined", f"The joust was declined by the {declined_by}.")

        await interaction.response.edit_message(embed=embed, view=ChallengeHomeView())
        self.stop()

    @discord.ui.button(label="Random Arena", style=discord.ButtonStyle.secondary)
    async def random_arena(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in {self.prepared.challenger.id, self.prepared.opponent.id}:
            return await interaction.response.send_message("❌ Only the two riders can randomise this arena.", ephemeral=True)

        if self.completed:
            return await interaction.response.send_message("❌ This challenge is already closed.", ephemeral=True)

        keys = list(ARENAS.keys())
        if len(keys) > 1 and self.prepared.arena_key in keys:
            keys.remove(self.prepared.arena_key)

        if self.prepared.tactics_ready:
            return await interaction.response.send_message(
                "❌ Arena is locked once either rider has selected their tactics.", ephemeral=True)
        self.prepared.arena_key = random.choice(keys)
        await interaction.response.edit_message(embed=make_challenge_embed(self.prepared), view=self)


class JoustCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_challenge_players: set[int] = set()
        self.last_challenge_at: dict[tuple[int, int], float] = {}
        self.challenge_cooldown_seconds = 30

    joust_group = app_commands.Group(name="joust", description="Single joust matches")

    def is_player_busy(self, user_id: int) -> bool:
        return user_id in self.active_challenge_players

    def try_lock_challenge(self, challenger_id: int, opponent_id: int) -> bool:
        """Synchronous check-and-reserve, without coroutine switching."""
        if (challenger_id == opponent_id or challenger_id in self.active_challenge_players
                or opponent_id in self.active_challenge_players):
            return False
        self.active_challenge_players.update((challenger_id, opponent_id))
        return True

    def cooldown_remaining(self, guild_id: int | None, challenger_id: int) -> int:
        key = (guild_id or 0, challenger_id)
        elapsed = time.monotonic() - self.last_challenge_at.get(key, -1e12)
        return max(0, int(self.challenge_cooldown_seconds - elapsed + 0.999))

    def mark_challenge_posted(self, guild_id: int | None, challenger_id: int) -> None:
        self.last_challenge_at[(guild_id or 0, challenger_id)] = time.monotonic()

    def lock_challenge(self, challenger_id: int, opponent_id: int) -> None:
        if not self.try_lock_challenge(challenger_id, opponent_id):
            raise ValueError("One rider is already busy.")

    def release_challenge(self, challenger_id: int, opponent_id: int) -> None:
        self.active_challenge_players.discard(challenger_id)
        self.active_challenge_players.discard(opponent_id)

    @staticmethod
    def can_debug(interaction: discord.Interaction, requested: bool) -> bool:
        perms = getattr(interaction.user, "guild_permissions", None)
        return bool(requested and perms and perms.manage_guild)

    def prepare_duel(
        self,
        *,
        challenger: discord.Member | discord.User,
        opponent: discord.Member,
        arena_key: str,
        seed: Optional[int] = None,
        debug_requested: bool = False,
        guild_id: Optional[int] = None,
    ) -> tuple[Optional[str], Optional[PreparedDuel]]:
        if opponent.id == challenger.id:
            return "❌ You cannot joust yourself.", None

        if opponent.bot:
            return "❌ You cannot joust a bot.", None

        arena_key = arena_key.strip().lower()

        if arena_key == "random":
            arena_key = random.choice(list(ARENAS.keys()))

        if arena_key not in ARENAS:
            return "❌ Unknown arena. Use `/arena list`, or use `random`.", None

        knights_db = load_knights()
        horses_db = load_horses()

        knight_a = get_knight(knights_db, challenger.id)
        knight_b = get_knight(knights_db, opponent.id)

        if not knight_a or not knight_b:
            return "❌ Both players need a knight. Use `/knight create`.", None

        if not knight_a.bound_horse_id or not knight_b.bound_horse_id:
            return "❌ Both players need a bound horse. Use `/horse bind`.", None

        horse_a_raw = horses_db.get("horses", {}).get(knight_a.bound_horse_id)
        horse_b_raw = horses_db.get("horses", {}).get(knight_b.bound_horse_id)

        if not horse_a_raw or not horse_b_raw:
            return "❌ Could not load one of the bound horses.", None

        horse_a = Horse.from_dict(horse_a_raw)
        horse_b = Horse.from_dict(horse_b_raw)

        # v0.8: resolve per-server unlocked loadouts before simulation and presentation.
        # Legacy starter equipment remains usable without migration.
        for knight, horse, user_id in (
            (knight_a, horse_a, challenger.id),
            (knight_b, horse_b, opponent.id),
        ):
            knight.equipped_lance_key = loadout(guild_id, user_id, "lance", knight.equipped_lance_key)
            knight.equipped_armour_key = loadout(guild_id, user_id, "armour", knight.equipped_armour_key)
            horse.equipped_barding_key = loadout(guild_id, user_id, "barding", horse.equipped_barding_key, horse.horse_id)

        effective_a = apply_penalty(knight_a.stats, guild_id, challenger.id)
        effective_b = apply_penalty(knight_b.stats, guild_id, opponent.id)

        fighter_a = Fighter(
            user_id=challenger.id,
            knight_name=knight_a.name,
            horse_name=horse_a.name,
            knight_stats=effective_a,
            horse_stats=horse_a.stats,
            lance_key=knight_a.equipped_lance_key,
            armour_key=knight_a.equipped_armour_key,
            barding_key=horse_a.equipped_barding_key,
        )

        fighter_b = Fighter(
            user_id=opponent.id,
            knight_name=knight_b.name,
            horse_name=horse_b.name,
            knight_stats=effective_b,
            horse_stats=horse_b.stats,
            lance_key=knight_b.equipped_lance_key,
            armour_key=knight_b.equipped_armour_key,
            barding_key=horse_b.equipped_barding_key,
        )

        return None, PreparedDuel(
            challenger=challenger,
            opponent=opponent,
            arena_key=arena_key,
            knight_a=knight_a,
            knight_b=knight_b,
            horse_a=horse_a,
            horse_b=horse_b,
            fighter_a=fighter_a,
            fighter_b=fighter_b,
            seed=seed,
            debug_requested=debug_requested,
            guild_id=guild_id,
        )

    async def send_match(self, sender, prepared: PreparedDuel, *,
                         record_id: str | None = None,
                         tournament_id: str | None = None) -> MatchResult:
        # Re-check at acceptance, not at challenge creation; time-based healing
        # and last-minute treatment might have changed the knight's condition.
        if prepared.guild_id is not None:
            for side, user_id, fighter, knight in (
                ("a", prepared.challenger.id, prepared.fighter_a, prepared.knight_a),
                ("b", prepared.opponent.id, prepared.fighter_b, prepared.knight_b),
            ):
                injured = bool(active_injuries(prepared.guild_id, user_id))
                assistance = (support_for_next_bout(prepared.guild_id, user_id)
                              if prepared.mode == "challenge" else None)
                setattr(prepared, "had_injury_" + side, injured)
                setattr(prepared, "support_token_" + side,
                        assistance["id"] if assistance is not None else None)
                fighter.knight_stats = apply_penalty(
                    knight.stats, prepared.guild_id, user_id,
                    relief=bool(assistance),
                )
        # Render the pre-match state before the journal is updated, so a fresh
        # injury sustained in this bout isn't mistakenly shown at the entrance.
        intro_embed = make_intro_embed(prepared)

        # Authoritative combat and history happen EXACTLY ONCE. Presentation
        # is a replay of this result: Discord edits never trigger combat again.
        result = run_single_match(prepared.fighter_a, prepared.fighter_b, prepared.arena_key,
                                  seed=prepared.seed, tactics_a=prepared.tactics_a,
                                  tactics_b=prepared.tactics_b)
        result_embed = make_result_embed(result, prepared.arena_key)
        match_id = record_match(prepared, result, match_id=record_id, tournament_id=tournament_id)
        if prepared.guild_id is not None and prepared.mode == "challenge":
            from services.records import load_history
            entry = next(
                (m for m in reversed(load_history()["matches"]) if m.get("id") == match_id), {}
            )
            events = entry.get("injuries", [])
            if events:
                descriptions = []
                for event in events:
                    rider = prepared.knight_a.name if event["user_id"] == prepared.challenger.id else prepared.knight_b.name
                    mods = event.get("risk_modifiers") or {}
                    details = " ".join(
                        f"{label.replace('_', ' ')} {value:+}%"
                        for label, value in mods.items() if value
                    )
                    descriptions.append(
                        f"**{rider}**: {event['name']} ({event.get('severity', 'moderate')}) "
                        f"· −1 {event['stat']} · {event.get('risk', '?')}% injury risk"
                        + (f"\n_{details}_" if details else "")
                    )
                result_embed.add_field(name="🩹 Injuries Sustained", value="\n".join(descriptions)[:1024], inline=False)
        result_embed.add_field(name="📜 Match ID", value=f"`{match_id}`", inline=False)
        helped = []
        if prepared.support_token_a:
            helped.append(prepared.knight_a.name)
        if prepared.support_token_b:
            helped.append(prepared.knight_b.name)
        if helped:
            result_embed.add_field(
                name="🩹 Physician's Aid",
                value=", ".join(helped) + " received one-bout pain relief (one injury penalty eased).",
                inline=False,
            )
        # Broadcast is non-authoritative: a Discord/media failure cannot
        # duplicate the match or erase its completed, saved result.
        import logging
        from cogs import broadcast
        display = logging.getLogger(__name__)
        if broadcast.enabled():
            try:
                await broadcast.send_intro(sender, prepared, intro_embed)
                await broadcast.play_passes(
                    sender, result, arena_key=prepared.arena_key,
                    home_view=ChallengeHomeView(),
                )
            except Exception:
                display.exception("Cinematic stages failed for recorded match %s", match_id)
        else:
            try:
                await sender.send(embed=intro_embed)
            except Exception:
                display.exception("Broadcast-off introduction failed for match %s", match_id)

        await broadcast.send_final(
            sender, result_embed, result, prepared, home_view=ChallengeHomeView()
        )
        return result

    @joust_group.command(name="duel", description="Run a cinematic single joust match immediately.")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def duel(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member,
        arena_key: str = "royal_lists",
        seed: Optional[int] = None,
        debug: bool = False,
    ):
        permissions = getattr(interaction.user, "guild_permissions", None)
        if not (permissions and permissions.manage_guild):
            return await interaction.response.send_message(
                "⛔ Instant duels are admin test tools. Use /joust challenge instead.", ephemeral=True)
        await interaction.response.defer(ephemeral=False)

        debug_allowed = self.can_debug(interaction, debug)
        error, prepared = self.prepare_duel(
            challenger=interaction.user,
            opponent=opponent,
            arena_key=arena_key,
            seed=seed,
            debug_requested=debug_allowed,
            guild_id=interaction.guild_id,
        )

        if error or not prepared:
            return await interaction.followup.send(error or "❌ Could not prepare joust.")

        if not self.try_lock_challenge(interaction.user.id, opponent.id):
            return await interaction.followup.send("❌ One rider is already busy.", ephemeral=True)
        try:
            result = await self.send_match(interaction.followup, prepared)
        finally:
            self.release_challenge(interaction.user.id, opponent.id)

        if debug_allowed:
            await interaction.followup.send(embed=make_debug_embed(result), ephemeral=True)
        elif debug:
            await interaction.followup.send("❌ Debug output requires Manage Server permission.", ephemeral=True)

    @joust_group.command(name="challenge", description="Challenge another player to a joust with accept/decline buttons.")
    async def challenge(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member,
        arena_key: str = "royal_lists",
        seed: Optional[int] = None,
        debug: bool = False,
    ):
        if self.is_player_busy(interaction.user.id):
            return await interaction.response.send_message("❌ You already have an active joust challenge.", ephemeral=True)

        if self.is_player_busy(opponent.id):
            return await interaction.response.send_message("❌ That player already has an active joust challenge.", ephemeral=True)

        debug_allowed = self.can_debug(interaction, debug)
        error, prepared = self.prepare_duel(
            challenger=interaction.user,
            opponent=opponent,
            arena_key=arena_key,
            seed=seed,
            debug_requested=debug_allowed,
            guild_id=interaction.guild_id,
        )

        if error or not prepared:
            return await interaction.response.send_message(error or "❌ Could not prepare challenge.", ephemeral=True)

        remaining = self.cooldown_remaining(interaction.guild_id, interaction.user.id)
        if remaining:
            return await interaction.response.send_message(
                f"⌛ Please wait {remaining}s before issuing another challenge.", ephemeral=True)
        prepared.mode = "challenge"
        if not self.try_lock_challenge(interaction.user.id, opponent.id):
            return await interaction.response.send_message("❌ A rider is already busy.", ephemeral=True)
        view = ChallengeView(self, prepared)
        try:
            await interaction.response.send_message(embed=make_challenge_embed(prepared), view=view)
            view.message = await interaction.original_response()
        except Exception:
            self.release_challenge(interaction.user.id, opponent.id)
            view.stop()
            raise
        self.mark_challenge_posted(interaction.guild_id, interaction.user.id)

        if debug and not debug_allowed:
            await interaction.followup.send("❌ Debug output requires Manage Server permission.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(JoustCog(bot))
