"""Grand Tournament Circuit v2.9.7: seasons, Houses and Chronicle.

Private OwnedView navigation, guild-scoped honorary titles and server-side
roster protection. No new virtual currency or combat buffs.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

from cogs.menu import OwnedView, embed, navigate
from cogs.knight import get_knight, load_knights
from services import circuit as engine
from services.arenas import ARENAS

# One lock per guild for slash, modal and component House writes.
HOUSE_LOCKS = defaultdict(asyncio.Lock)


def rider(uid: int) -> str:
    return f"<@{uid}>" if isinstance(uid, int) and uid > 0 else "Unknown knight"


def standings_embed(gid: int, number: int | None = None) -> discord.Embed:
    report = engine.seasonal_standings(gid, number)
    window = report["season"]
    lines = [f"**{i}.** {rider(p['user_id'])} — **{p['points']} points** · "
             f"{p['wins']} wins · {p['championships']} crowns"
             for i, p in enumerate(report["standings"][:12], 1)]
    return embed(
        "🏆 " + window["name"],
        f"**UTC dates:** {window['start'][:10]} – {window['end'][:10]}\n"
        f"**Verified tournament jousts:** {report['verified_matches']}\n\n"
        + ("\n".join(lines) if lines else "No qualifying jousts yet.")
        + "\n\nHonours are honorary: 2 points per completed tournament bout, "
          "+5 for advancing, +10 per verified crown and +3 knockout finalist. "
          "No additional gold, XP or stat bonuses."
    )


def arenas_embed(gid: int, number: int | None = None) -> discord.Embed:
    report = engine.arena_champions(gid, number)
    lines = []
    for key, arena in ARENAS.items():
        top = report["arenas"][key]
        champions = ", ".join(f"{rider(p['id'])} ({p['wins']} wins)" for p in top)
        lines.append(f"**{arena.name}:** {champions or 'Awaiting a qualifier'}")
    return embed(
        "🏟️ The Six Arena Championships",
        "\n".join(lines) +
        "\n\nThree verified tournament wins in the same arena, during one season, "
        "are needed to qualify. All awards remain cosmetic."
    )


def houses_embed(gid: int, number: int | None = None) -> discord.Embed:
    board = engine.house_standings(gid, number)
    lines = [
        f"**{i}. {discord.utils.escape_markdown(h['name'])}** — "
        f"{h['points']} pts · {h['wins']} wins · "
        f"{h['rivalry_wins']} rivalry wins"
        for i, h in enumerate(board[:12], 1)
    ]
    return embed("🏰 Knight House Standings",
                 ("\n".join(lines) if lines else "No Houses founded yet.")
                 + "\n\nHouse points are earned only from verified tournament bouts. "
                   "The House at the time of the match keeps its historical points.")


def herald_embed(gid: int) -> discord.Embed:
    stories = engine.chronicle(gid)
    lines = [
        f"**{x['day']} · {discord.utils.escape_markdown(x['title'])}**\n{x['body']}"
        for x in stories
    ]
    return embed("📰 The Herald's Chronicle",
                 ("\n\n".join(lines) if lines
                  else "No completed tournament reports yet.")[:3900])


def hall_embed(gid: int) -> discord.Embed:
    entries = engine.champions_hall(gid, limit=15)
    lines = [
        f"🏅 **{e['date']}** · {rider(e['champion'])} — "
        f"{discord.utils.escape_markdown(e['name'])} "
        f"({e['format'].replace('_', ' ')}, {e['size']} riders)"
        for e in entries
    ]
    return embed("🏆 Hall of Champions",
                 ("\n".join(lines) if lines
                  else "No verified crowns recorded yet.")[:3900]
                 + "\n\nThe Hall is computed from the permanent verified tournament archive.")




def house_mission_embed(gid: int, uid: int) -> discord.Embed:
    hid = engine.house_for(gid, uid)
    if not hid:
        return embed("🏰 Daily House Rivalries",
                     "Join a House first. Missions track genuine tournament results only.")
    board = engine.house_missions(gid, hid)
    names = {
        "rival_bouts": "Complete a bout against a rival House",
        "team_turnout": "Three distinct Housemates compete today",
        "rival_victories": "Win two inter-House jousts today",
    }
    lines = [
        f"{'✅' if board[key]['complete'] else '⏳'} **{label}**"
        f" — {board[key]['progress']}/{board[key]['goal']}"
        for key, label in names.items()
    ]
    return embed("🏰 Daily House Rivalry Missions",
                 f"**UTC date:** {board['date']}\n\n"
                 + "\n".join(lines)
                 + "\n\nProgress is automatic from verified tournament records. "
                   "Missions are honorary and cannot be repeatedly claimed.")


class CircuitHub(OwnedView):
    def __init__(self, uid: int, gid: int | None):
        super().__init__(uid)
        self.gid = gid
        for i, (label, tab, emoji) in enumerate((
            ("Season Standings", "season", "🏆"),
            ("Arena Championships", "arenas", "🏟️"),
            ("House Rankings", "houses", "🏰"),
            ("Herald's Chronicle", "herald", "📰"),
            ("Hall of Champions", "hall", "🎖️"),
        )):
            self.button(label, lambda it, tab=tab: navigate(
                it, CircuitPage(it.user.id, it.guild_id, tab)),
                row=i // 3, emoji=emoji)
        self.button("Join a House", lambda it: navigate(
            it, HousePage(it.user.id, it.guild_id)), row=2, emoji="🛡️")
        self.button("Tournament Hub", self.tournaments, row=2, emoji="⚔️")
        self.home()

    async def tournaments(self, interaction):
        from cogs.tournament import TournamentHub
        from cogs.menu import is_admin
        await navigate(interaction, TournamentHub(
            interaction.user.id, interaction.guild_id, is_admin(interaction)))

    def make_embed(self):
        if not self.gid:
            return embed("🏰 Grand Tournament Circuit", "Open this inside a server.")
        win = engine.season_window()
        leaders = engine.seasonal_standings(self.gid)["standings"]
        leader = (f"{rider(leaders[0]['user_id'])} · {leaders[0]['points']} points"
                  if leaders else "No contender yet")
        return embed(
            "🏰 The Grand Tournament Circuit",
            f"**{win['name']}**\n"
            f"**UTC:** {win['start'][:10]} – {win['end'][:10]}\n"
            f"**Season leader:** {leader}\n\n"
            "Ranked and round-robin tournaments, six arena honours, "
            "Knight Houses, historic champions and automatic Herald dispatches. "
            "All Circuit awards are honorary."
        )


class CircuitPage(OwnedView):
    def __init__(self, uid: int, gid: int | None, tab: str = "season",
                 season: int | None = None):
        super().__init__(uid)
        self.gid, self.tab, self.season = gid, tab, season
        for label, key, emoji in (
            ("Season", "season", "🏆"), ("Arenas", "arenas", "🏟️"),
            ("Houses", "houses", "🏰"), ("Herald", "herald", "📰"),
            ("Champions", "hall", "🎖️"),
        ):
            self.button(label, lambda it, key=key: navigate(
                it, CircuitPage(it.user.id, it.guild_id, key, self.season)),
                emoji=emoji, row=0)
        number = self.season or engine.season_number() or 1
        self.button("Previous Season", lambda it: navigate(
            it, CircuitPage(it.user.id, it.guild_id, self.tab, number - 1)),
            row=1, disabled=number <= 1)
        self.button("Current Season", lambda it: navigate(
            it, CircuitPage(it.user.id, it.guild_id, self.tab)), row=1)
        self.button("Grand Circuit", lambda it: navigate(
            it, CircuitHub(it.user.id, it.guild_id)), row=2)
        self.home()

    def make_embed(self):
        if not self.gid:
            return embed("🏰 Grand Circuit", "Server-only Circuit.")
        if self.tab == "arenas":
            return arenas_embed(self.gid, self.season)
        if self.tab == "houses":
            return houses_embed(self.gid, self.season)
        if self.tab == "herald":
            return herald_embed(self.gid)
        if self.tab == "hall":
            return hall_embed(self.gid)
        return standings_embed(self.gid, self.season)


class HouseCreateModal(discord.ui.Modal, title="Found a Knight House"):
    name = discord.ui.TextInput(label="New House name", min_length=3,
                                max_length=32, placeholder="House of the Silver Lance")

    async def on_submit(self, interaction):
        try:
            if not interaction.guild_id:
                raise engine.CircuitError("Create a House in your Discord server.")
            if not get_knight(load_knights(), interaction.user.id):
                raise engine.CircuitError("Create a knight before founding a House.")
            async with HOUSE_LOCKS[interaction.guild_id]:
                house = engine.create_house(interaction.guild_id, interaction.user.id,
                                            str(self.name))
        except engine.CircuitError as ex:
            return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        view = HousePage(interaction.user.id, interaction.guild_id)
        await navigate(interaction, view,
                       f"✅ Founded {discord.utils.escape_markdown(house['name'])}.")


class HouseSelect(discord.ui.Select):
    def __init__(self, page: "HousePage", entries: dict):
        self.page = page
        super().__init__(
            row=0, placeholder="Select the Knight House to join",
            options=[
                discord.SelectOption(label=item["name"][:100], value=hid,
                                     description=f"{len(item['members'])} knights")
                for hid, item in list(entries.items())[:12]
            ])

    async def callback(self, interaction):
        if not get_knight(load_knights(), interaction.user.id):
            return await interaction.response.send_message(
                "❌ Create a knight before joining a House.", ephemeral=True)
        try:
            async with HOUSE_LOCKS[interaction.guild_id]:
                result = engine.join_house(interaction.guild_id, interaction.user.id,
                                           self.values[0])
        except engine.CircuitError as ex:
            return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await navigate(interaction, HousePage(interaction.user.id, interaction.guild_id),
                       f"✅ Joined {discord.utils.escape_markdown(result['name'])}.")


class HousePage(OwnedView):
    def __init__(self, uid: int, gid: int | None):
        super().__init__(uid)
        self.gid = gid
        houses = engine.guild_houses(gid) if gid else {}
        belonging = engine.house_for(gid, uid) if gid else None
        if not belonging and houses:
            self.add_item(HouseSelect(self, houses))
        self.button("Found House", self.found, row=1, disabled=bool(belonging))
        self.button("Leave House", self.leave, row=1, disabled=not belonging)
        self.button("Standings", lambda it: navigate(
            it, CircuitPage(it.user.id, it.guild_id, "houses")), row=2)
        self.button("Daily Missions", self.missions, row=2, emoji="⚔️")
        self.button("Grand Circuit", lambda it: navigate(
            it, CircuitHub(it.user.id, it.guild_id)), row=2)
        self.home()

    def make_embed(self):
        if not self.gid:
            return embed("🏰 Knight Houses", "Create or join a House in a server.")
        houses = engine.guild_houses(self.gid)
        mine = engine.house_for(self.gid, self.owner_id)
        name = houses.get(mine, {}).get("name", "Not joined")
        lines = [
            f"**{discord.utils.escape_markdown(h['name'])}** — "
            f"{len(h['members'])} knights · Captain {rider(h['captain'])} "
            f"· ID `{hid}`"
            for hid, h in list(houses.items())[:12]
        ]
        return embed(
            "🏰 Knight Houses",
            f"**Your House:** {discord.utils.escape_markdown(name)}\n\n"
            + ("\n".join(lines) if lines else "No Houses founded here yet.")
            + "\n\n**Transfers:** a 24-hour cooldown applies when leaving "
              "for a different House. Rejoining your previous House is "
              "allowed immediately. Use the dropdown or `/house join`."
        )

    async def missions(self, interaction):
        await navigate(interaction, HouseMissionsPage(interaction.user.id, interaction.guild_id))

    async def found(self, interaction):
        await interaction.response.send_modal(HouseCreateModal())

    async def leave(self, interaction):
        try:
            async with HOUSE_LOCKS[interaction.guild_id]:
                engine.leave_house(interaction.guild_id, interaction.user.id)
        except engine.CircuitError as ex:
            return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await navigate(interaction, HousePage(interaction.user.id, interaction.guild_id),
                       "✅ Left your House. Historic honours remain unchanged.")


class HouseMissionsPage(OwnedView):
    def __init__(self, uid: int, gid: int | None):
        super().__init__(uid)
        self.gid = gid
        self.button("Knight Houses", lambda it: navigate(
            it, HousePage(it.user.id, it.guild_id)), row=0)
        self.button("Refresh", lambda it: navigate(
            it, HouseMissionsPage(it.user.id, it.guild_id)), row=0)
        self.home()

    def make_embed(self):
        if not self.gid:
            return embed("🏰 House Missions", "Server-only House challenges.")
        return house_mission_embed(self.gid, self.owner_id)


class CircuitCog(commands.Cog):
    circuit_group = app_commands.Group(name="circuit", description="The Grand Tournament Circuit")
    house_group = app_commands.Group(name="house", description="Your Knight House")
    herald_group = app_commands.Group(name="herald", description="The Herald's Chronicle")
    hall_group = app_commands.Group(name="hall", description="Hall of Champions")

    def __init__(self, bot):
        self.bot = bot

    @circuit_group.command(name="menu", description="Open the Circuit menu.")
    @app_commands.guild_only()
    async def circuit_menu(self, interaction: discord.Interaction):
        view = CircuitHub(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(embed=view.make_embed(), view=view,
                                                ephemeral=True)

    @circuit_group.command(name="standings", description="Season standings.")
    @app_commands.guild_only()
    async def standings(self, interaction: discord.Interaction, season: int | None = None):
        try:
            card = standings_embed(interaction.guild_id, season)
        except engine.CircuitError as ex:
            return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await interaction.response.send_message(embed=card, ephemeral=True)

    @circuit_group.command(name="arenas", description="Seasonal arena champions.")
    @app_commands.guild_only()
    async def arenas(self, interaction: discord.Interaction, season: int | None = None):
        try:
            card = arenas_embed(interaction.guild_id, season)
        except engine.CircuitError as ex:
            return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await interaction.response.send_message(embed=card, ephemeral=True)

    @circuit_group.command(name="houses", description="Honorary House standings.")
    @app_commands.guild_only()
    async def houses(self, interaction: discord.Interaction, season: int | None = None):
        try:
            card = houses_embed(interaction.guild_id, season)
        except engine.CircuitError as ex:
            return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await interaction.response.send_message(embed=card, ephemeral=True)

    @house_group.command(name="menu", description="Browse and join Knight Houses.")
    @app_commands.guild_only()
    async def house_menu(self, interaction: discord.Interaction):
        page = HousePage(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(embed=page.make_embed(), view=page,
                                                ephemeral=True)

    @house_group.command(name="found", description="Found a new House.")
    @app_commands.guild_only()
    async def found(self, interaction: discord.Interaction, name: str):
        if not get_knight(load_knights(), interaction.user.id):
            return await interaction.response.send_message(
                "❌ Create a knight first.", ephemeral=True)
        try:
            async with HOUSE_LOCKS[interaction.guild_id]:
                house = engine.create_house(interaction.guild_id, interaction.user.id, name)
        except engine.CircuitError as ex:
            return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await interaction.response.send_message(
            f"✅ Founded {discord.utils.escape_markdown(house['name'])}. "
            f"House ID: {house['id']}.", ephemeral=True)

    @house_group.command(name="join", description="Join a House by ID.")
    @app_commands.guild_only()
    async def join(self, interaction: discord.Interaction, house_id: str):
        if not get_knight(load_knights(), interaction.user.id):
            return await interaction.response.send_message(
                "❌ Create a knight first.", ephemeral=True)
        try:
            async with HOUSE_LOCKS[interaction.guild_id]:
                house = engine.join_house(interaction.guild_id, interaction.user.id, house_id)
        except engine.CircuitError as ex:
            return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await interaction.response.send_message(
            f"✅ Joined {discord.utils.escape_markdown(house['name'])}.", ephemeral=True)

    @house_group.command(name="leave", description="Leave your current House.")
    @app_commands.guild_only()
    async def leave(self, interaction: discord.Interaction):
        try:
            async with HOUSE_LOCKS[interaction.guild_id]:
                engine.leave_house(interaction.guild_id, interaction.user.id)
        except engine.CircuitError as ex:
            return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await interaction.response.send_message("✅ Left your House.", ephemeral=True)

    @house_group.command(name="captain", description="Pass leadership to a current House member.")
    @app_commands.guild_only()
    async def captain(self, interaction: discord.Interaction, member: discord.Member):
        try:
            if member.bot:
                raise engine.CircuitError("Bots cannot become House captains.")
            async with HOUSE_LOCKS[interaction.guild_id]:
                house = engine.transfer_captain(interaction.guild_id,
                                                 interaction.user.id, member.id)
        except engine.CircuitError as ex:
            return await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
        await interaction.response.send_message(
            f"✅ {rider(member.id)} now leads "
            f"{discord.utils.escape_markdown(house['name'])}.", ephemeral=True)

    @house_group.command(name="missions", description="View daily honorary House rivalry missions.")
    @app_commands.guild_only()
    async def missions(self, interaction: discord.Interaction):
        page = HouseMissionsPage(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(
            embed=page.make_embed(), view=page, ephemeral=True)

    @house_group.command(name="roster", description="List House names and IDs.")
    @app_commands.guild_only()
    async def roster(self, interaction: discord.Interaction):
        houses = engine.guild_houses(interaction.guild_id)
        lines = [
            f"**{discord.utils.escape_markdown(h['name'])}** (ID: {hid})\n"
            f"{len(h['members'])} members · Captain {rider(h['captain'])}"
            for hid, h in houses.items()
        ]
        await interaction.response.send_message(
            embed=embed("🏰 Knight House Roster",
                        "\n\n".join(lines)[:3900] if lines else "No Houses founded."),
            ephemeral=True)

    @herald_group.command(name="read", description="Read automatic tournament news.")
    @app_commands.guild_only()
    async def read(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=herald_embed(interaction.guild_id),
                                                ephemeral=True)

    @hall_group.command(name="champions", description="Review lifetime tournament champions.")
    @app_commands.guild_only()
    async def champions(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=hall_embed(interaction.guild_id),
                                                ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CircuitCog(bot))
