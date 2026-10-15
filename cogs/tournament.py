"""Tournament Lite: volunteer registration, admin-driven single elimination."""
from __future__ import annotations

import asyncio
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

from cogs.knight import get_knight, load_knights
from cogs.horse import load_horses
from cogs.menu import MainMenuView, is_admin, OwnedView, navigate
from services import tournaments as engine
from services.records import load_history


def at(uid):
    return "<@" + str(uid) + ">" if uid is not None else "TBD"


def status_embed(gid):
    t = engine.current(gid)
    e = discord.Embed(title="🏆 Tournament Lite", colour=discord.Colour.gold())
    if not t:
        last = engine.recent(gid, 1)
        e.description = ("No active tournament. Admins can create one."
                         if not last else
                         "No active tournament. Last champion: " + at(last[0]["champion"]))
        return e
    e.title = "🏆 " + discord.utils.escape_markdown(t["name"])
    e.description = (
        f"Format: **{t['size']} players** · {t['status'].title()}\n"
        f"Registered: **{len(t['entrants'])}/{t['size']}**\n"
        "Joining consents to admin-run competitive matches. Gear, injuries and rewards apply."
    )
    if t["status"] == "registration":
        e.add_field(name="Entrants", value="\n".join(
            f"{i + 1}. {at(uid)}" for i, uid in enumerate(t["entrants"])
        ) or "Awaiting registrations.", inline=False)
        e.add_field(name="Next", value="Players Join, then admin Starts when full.", inline=False)
    else:
        rounds = t.get("rounds", [])
        for idx, rnd in enumerate(rounds):
            label = "Final" if idx == len(rounds)-1 else ("Semifinals" if idx == len(rounds)-2 else "Quarterfinals")
            lines = []
            for i, m in enumerate(rnd):
                sym = "✅" if m["status"] == "complete" else ("⏳" if m["status"] == "running" else "◯")
                win = " → " + at(m["winner"]) if m["winner"] else ""
                lines.append(f"{sym} {i+1}. {at(m['a'])} vs {at(m['b'])}{win}")
            e.add_field(name=label, value="\n".join(lines), inline=False)
        nxt = engine.pending(t)
        if nxt:
            m = nxt["match"]
            e.add_field(name="Next Pairing",
                        value=f"{at(m['a'])} vs {at(m['b'])} · {m['arena_key'].replace('_',' ').title()}",
                        inline=False)
    return e


def history_embed(gid):
    e = discord.Embed(title="📜 Tournament History", colour=discord.Colour.gold())
    items = engine.recent(gid, 10)
    if not items:
        e.description = "No completed tournaments yet."
    for t in items:
        e.add_field(name=discord.utils.escape_markdown(t["name"]),
                    value=f"Champion: {at(t['champion'])} · {t['size']} entrants · "
                          + t.get("completed_at", "")[:10], inline=False)
    return e


def valid_rider(member):
    if member.bot:
        return "Bots cannot enter."
    k = get_knight(load_knights(), member.id)
    if not k or not k.bound_horse_id:
        return "Create a knight and bind a horse before entering."
    h = load_horses().get("horses", {}).get(k.bound_horse_id)
    if not h or int(h.get("owner_id", -1)) != member.id:
        return "Your bound horse must belong to you."
    return None


async def member_in(guild, uid):
    user = guild.get_member(uid)
    if user:
        return user
    try:
        return await guild.fetch_member(uid)
    except discord.HTTPException:
        return None


class HomeView(OwnedView):
    def __init__(self, uid):
        super().__init__(uid)
        self.home()
    def make_embed(self):
        return discord.Embed(title="Return to the Main Menu")


class TournamentPanel(discord.ui.View):
    """Registered persistent public buttons; permissions checked by the cog."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Join Tournament", emoji="🛡️", style=discord.ButtonStyle.success,
                       custom_id="tournament:join", row=0)
    async def join(self, interaction, button):
        await interaction.client.get_cog("TournamentCog").do_join(interaction)

    @discord.ui.button(label="Start Tournament", emoji="🏆", style=discord.ButtonStyle.primary,
                       custom_id="tournament:start", row=0)
    async def start(self, interaction, button):
        await interaction.client.get_cog("TournamentCog").do_start(interaction)

    @discord.ui.button(label="Start Next Match", emoji="⚔️", style=discord.ButtonStyle.primary,
                       custom_id="tournament:next", row=0)
    async def next(self, interaction, button):
        await interaction.client.get_cog("TournamentCog").do_next(interaction)

    @discord.ui.button(label="History", emoji="📜", style=discord.ButtonStyle.secondary,
                       custom_id="tournament:history", row=0)
    async def history(self, interaction, button):
        if interaction.guild_id is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        await interaction.response.send_message(embed=history_embed(interaction.guild_id),
                                                view=HomeView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label="Refresh", emoji="🔄", style=discord.ButtonStyle.secondary,
                       custom_id="tournament:refresh", row=1)
    async def refresh(self, interaction, button):
        if interaction.guild_id is None:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        await interaction.response.edit_message(embed=status_embed(interaction.guild_id), view=self)

    @discord.ui.button(label="Main Menu", emoji="🏰", style=discord.ButtonStyle.secondary,
                       custom_id="tournament:home", row=1)
    async def home(self, interaction, button):
        v = MainMenuView(interaction.user.id, is_admin(interaction))
        await interaction.response.send_message(embed=v.make_embed(), view=v, ephemeral=True)


class NewTournament(discord.ui.Modal, title="Create Tournament"):
    name = discord.ui.TextInput(label="Event name", min_length=3, max_length=50)
    size = discord.ui.TextInput(label="Players (4 or 8)", min_length=1, max_length=1,
                                placeholder="4")

    async def on_submit(self, interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("⛔ Admin only.", ephemeral=True)
        sz = int(str(self.size)) if str(self.size) in ("4", "8") else 0
        await interaction.client.get_cog("TournamentCog").do_create(interaction, str(self.name), sz)


class TournamentHub(OwnedView):
    def __init__(self, uid, gid, admin=False):
        super().__init__(uid)
        self.gid = gid
        self.button("Refresh", self.refresh, row=0, emoji="🔄")
        self.button("Join", self.join, row=0, emoji="🛡️")
        self.button("History", self.history, row=0, emoji="📜")
        if admin:
            self.button("Create", self.create, row=1, style=discord.ButtonStyle.primary)
            self.button("Start", self.start, row=1)
            self.button("Start Next Match", self.next, row=1)
        self.home()

    def make_embed(self):
        return status_embed(self.gid) if self.gid else discord.Embed(
            title="Tournaments", description="Use the tournament menu in your server."
        )

    async def refresh(self, it):
        await navigate(it, TournamentHub(it.user.id, it.guild_id, is_admin(it)))
    async def join(self, it):
        await it.client.get_cog("TournamentCog").do_join(it)
    async def history(self, it):
        await it.response.edit_message(embed=history_embed(it.guild_id), view=self)
    async def create(self, it):
        if not is_admin(it):
            return await it.response.send_message("Admin only.", ephemeral=True)
        await it.response.send_modal(NewTournament())
    async def start(self, it):
        await it.client.get_cog("TournamentCog").do_start(it)
    async def next(self, it):
        await it.client.get_cog("TournamentCog").do_next(it)


class TournamentCog(commands.Cog):
    group = app_commands.Group(name="tournament", description="Four- and eight-player jousting tournaments")

    def __init__(self, bot):
        self.bot = bot
        self.locks = defaultdict(asyncio.Lock)

    async def cog_load(self):
        self.bot.add_view(TournamentPanel())

    async def do_create(self, interaction, name, size):
        if not is_admin(interaction):
            return await interaction.response.send_message("⛔ Manage Server permission required.", ephemeral=True)
        async with self.locks[interaction.guild_id]:
            try:
                engine.create(interaction.guild_id, interaction.user.id, name, size)
            except engine.TournamentError as ex:
                return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await interaction.response.send_message("✅ Registration opened.", ephemeral=True)
        if interaction.channel:
            await interaction.channel.send(embed=status_embed(interaction.guild_id), view=TournamentPanel())

    async def do_join(self, interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Join in a server.", ephemeral=True)
        reason = valid_rider(interaction.user)
        if reason:
            return await interaction.response.send_message(f"❌ {reason}", ephemeral=True)
        async with self.locks[interaction.guild_id]:
            try:
                item = engine.join(interaction.guild_id, interaction.user.id)
            except engine.TournamentError as ex:
                return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await interaction.response.send_message(
            f"✅ Registered for {discord.utils.escape_markdown(item['name'])} "
            f"({len(item['entrants'])}/{item['size']}).", ephemeral=True)
        if interaction.message and interaction.message.embeds:
            try:
                await interaction.message.edit(embed=status_embed(interaction.guild_id),
                                               view=TournamentPanel())
            except discord.HTTPException:
                pass

    async def do_start(self, interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("⛔ Manage Server permission required.", ephemeral=True)
        current = engine.current(interaction.guild_id)
        if not current or current["status"] != "registration":
            return await interaction.response.send_message("❌ No tournament awaiting start.", ephemeral=True)
        if len(current["entrants"]) != current["size"]:
            return await interaction.response.send_message(
                f"❌ Need {current['size']} riders; only {len(current['entrants'])} registered.", ephemeral=True)
        for uid in current["entrants"]:
            rider = await member_in(interaction.guild, uid)
            if rider is None or valid_rider(rider):
                return await interaction.response.send_message(
                    f"❌ Rider {at(uid)} is no longer ready or available.", ephemeral=True)
        async with self.locks[interaction.guild_id]:
            try:
                engine.start(interaction.guild_id)
            except engine.TournamentError as ex:
                return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await interaction.response.send_message("✅ Bracket generated. Press Start Next Match.",
                                                ephemeral=True)
        if interaction.channel:
            await interaction.channel.send(embed=status_embed(interaction.guild_id), view=TournamentPanel())

    async def do_next(self, interaction):
        if not is_admin(interaction):
            return await interaction.response.send_message("⛔ Manage Server permission required.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        async with self.locks[interaction.guild_id]:
            state = engine.current(interaction.guild_id)
            if not state or state["status"] != "running":
                return await interaction.followup.send("❌ No running tournament.", ephemeral=True)
            choice = engine.pending(state)
            if choice is None:
                return await interaction.followup.send("❌ No pairing ready.", ephemeral=True)
            match = choice["match"]
            journal = next((m for m in reversed(load_history()["matches"])
                            if m.get("id") == match["id"]), None)
            a = await member_in(interaction.guild, match["a"])
            b = await member_in(interaction.guild, match["b"])
            if journal is None and (not a or not b):
                return await interaction.followup.send("❌ A rider has left this server.", ephemeral=True)
            joust = self.bot.get_cog("JoustCog")
            if journal is None and joust is None:
                return await interaction.followup.send("❌ Joust engine unavailable.", ephemeral=True)
            if journal is None:
                if joust.is_player_busy(a.id) or joust.is_player_busy(b.id):
                    return await interaction.followup.send("❌ A rider is already challenging.", ephemeral=True)
                error, prepared = joust.prepare_duel(
                    challenger=a, opponent=b, arena_key=match["arena_key"],
                    seed=match["seed"], guild_id=interaction.guild_id)
                if error or prepared is None:
                    return await interaction.followup.send(error or "Riders not ready.", ephemeral=True)
                prepared.mode = "challenge"
                engine.reserve_next(interaction.guild_id)
                joust.lock_challenge(a.id, b.id)
                try:
                    result = await joust.send_match(
                        interaction.channel, prepared,
                        record_id=match["id"], tournament_id=state["id"])
                    score_a, score_b = result.score_a, result.score_b
                except Exception:
                    return await interaction.followup.send(
                        "⚠️ Match interrupted. Press Next to recover its saved result or retry.",
                        ephemeral=True)
                finally:
                    joust.release_challenge(a.id, b.id)
            else:
                if journal.get("tournament_id") != state["id"]:
                    return await interaction.followup.send("❌ Match journal ID conflict.", ephemeral=True)
                engine.reserve_next(interaction.guild_id)
                score_a, score_b = journal["a"]["score"], journal["b"]["score"]
            if score_a > score_b:
                winner, tiebreak = a.id, None
            elif score_b > score_a:
                winner, tiebreak = b.id, None
            else:
                winner = engine.tie_winner(a.id, b.id, match["seed"])
                tiebreak = "seeded marshal decision"
            try:
                done = engine.complete_match(interaction.guild_id, state["id"],
                                              match["id"], winner, match["id"],
                                              tiebreak=tiebreak)
            except engine.TournamentError as ex:
                return await interaction.followup.send(f"⚠️ Result saved, bracket update failed: {ex}",
                                                        ephemeral=True)
            label = "🏆 GRAND CHAMPION" if done["status"] == "completed" else "⚔️ Round Complete"
            notice = discord.Embed(
                title=label,
                description=f"{at(match['a'])} {score_a} — {score_b} {at(match['b'])}\n"
                            f"Advances: {at(winner)}"
                            + (f"\nTie resolved by {tiebreak}." if tiebreak else "")
                            + ("\nThe champion has been crowned!" if done["status"] == "completed" else ""),
                colour=discord.Colour.gold())
            if interaction.channel:
                await interaction.channel.send(embed=notice)
                await interaction.channel.send(embed=status_embed(interaction.guild_id),
                                               view=TournamentPanel())
            await interaction.followup.send(f"✅ {at(winner)} advances.", ephemeral=True)

    @group.command(name="create", description="Admin: create a 4- or 8-rider event.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(size=[app_commands.Choice(name="4 riders", value=4),
                                app_commands.Choice(name="8 riders", value=8)])
    async def create(self, interaction: discord.Interaction, name: str, size: int = 4):
        await self.do_create(interaction, name, size)

    @group.command(name="join", description="Register for the open tournament.")
    @app_commands.guild_only()
    async def join(self, interaction: discord.Interaction):
        await self.do_join(interaction)

    @group.command(name="start", description="Admin: generate the full bracket.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def start(self, interaction: discord.Interaction):
        await self.do_start(interaction)

    @group.command(name="status", description="View tournament registration and bracket.")
    @app_commands.guild_only()
    async def status(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=status_embed(interaction.guild_id),
                                                view=TournamentPanel())

    @group.command(name="next", description="Admin: simulate the next bracket pairing.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    async def next(self, interaction: discord.Interaction):
        await self.do_next(interaction)

    @group.command(name="history", description="Show recent tournament champions.")
    @app_commands.guild_only()
    async def history(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=history_embed(interaction.guild_id),
                                                view=HomeView(interaction.user.id), ephemeral=True)


async def setup(bot):
    await bot.add_cog(TournamentCog(bot))
