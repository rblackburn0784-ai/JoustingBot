from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

from services.storage import load_json, save_json


DB_PATH = "storage/knights.json"

STATS = ("strength", "control", "endurance", "agility", "resolve", "tactics")
STAT_POOL = 20
STAT_MIN = 1
STAT_MAX = 8

NAME_RE = re.compile(r"^[A-Za-z0-9 _\-'.]{2,24}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_knights() -> Dict[str, Any]:
    return load_json(DB_PATH, {"knights": {}})


def save_knights(db: Dict[str, Any]) -> None:
    save_json(DB_PATH, db)


@dataclass
class Knight:
    user_id: int
    name: str
    stats: Dict[str, int]

    equipped_lance_key: str = "lance_ash"
    equipped_armour_key: str = "armour_mail"
    bound_horse_id: Optional[str] = None

    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Knight":
        return Knight(
            user_id=int(data["user_id"]),
            name=str(data["name"]),
            stats=dict(data["stats"]),
            equipped_lance_key=data.get("equipped_lance_key", "lance_ash"),
            equipped_armour_key=data.get("equipped_armour_key", "armour_mail"),
            bound_horse_id=data.get("bound_horse_id"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


def get_knight(db: Dict[str, Any], user_id: int) -> Optional[Knight]:
    raw = db.get("knights", {}).get(str(user_id))
    return Knight.from_dict(raw) if raw else None


def set_knight(db: Dict[str, Any], knight: Knight) -> None:
    db.setdefault("knights", {})
    knight.updated_at = utc_now()
    db["knights"][str(knight.user_id)] = knight.to_dict()


def validate_name(name: str) -> str:
    name = name.strip()

    if not NAME_RE.match(name):
        raise ValueError("Name must be 2-24 characters using letters, numbers, spaces, _ - ' .")

    return name


def validate_stats(stats: Dict[str, int]) -> None:
    missing = [s for s in STATS if s not in stats]
    if missing:
        raise ValueError(f"Missing stats: {', '.join(missing)}")

    for stat, value in stats.items():
        if stat not in STATS:
            raise ValueError(f"Unknown stat: {stat}")

        if value < STAT_MIN or value > STAT_MAX:
            raise ValueError(f"{stat.title()} must be between {STAT_MIN} and {STAT_MAX}.")

    total = sum(stats.values())
    if total != STAT_POOL:
        raise ValueError(f"Knight stats must total {STAT_POOL}. You provided {total}.")


def knight_embed(knight: Knight, user: discord.abc.User) -> discord.Embed:
    e = discord.Embed(
        title=knight.name,
        description=f"Knight profile for {user.mention}",
    )

    stats = "\n".join(
        f"**{stat.title()}**: {knight.stats.get(stat, 0)}"
        for stat in STATS
    )

    e.add_field(name="Stats", value=stats, inline=False)
    e.add_field(name="Lance", value=f"`{knight.equipped_lance_key}`", inline=True)
    e.add_field(name="Armour", value=f"`{knight.equipped_armour_key}`", inline=True)
    e.add_field(name="Bound Horse", value=knight.bound_horse_id or "None", inline=False)

    return e


class StatSelect(discord.ui.Select):
    def __init__(self, builder: "KnightStatBuilderView"):
        self.builder = builder

        options = [
            discord.SelectOption(
                label=stat.title(),
                value=stat,
                description=f"Current value: {builder.stats[stat]}",
                default=(stat == builder.selected_stat),
            )
            for stat in STATS
        ]

        super().__init__(
            placeholder="Choose a stat to edit",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder.user_id:
            return await interaction.response.send_message(
                "❌ This stat builder is not yours.",
                ephemeral=True,
            )

        self.builder.selected_stat = str(self.values[0])
        await self.builder.refresh(interaction)


class ValueSelect(discord.ui.Select):
    def __init__(self, builder: "KnightStatBuilderView"):
        self.builder = builder
        stat = builder.selected_stat
        current_value = builder.stats[stat]

        # Dynamic cap: the player can only pick values that keep the total at or below 20.
        max_allowed = min(STAT_MAX, current_value + builder.remaining_points())

        options = [
            discord.SelectOption(
                label=str(value),
                value=str(value),
                description=f"Set {stat.title()} to {value}",
                default=(value == current_value),
            )
            for value in range(STAT_MIN, max_allowed + 1)
        ]

        super().__init__(
            placeholder=f"Set {stat.title()} value",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder.user_id:
            return await interaction.response.send_message(
                "❌ This stat builder is not yours.",
                ephemeral=True,
            )

        stat = self.builder.selected_stat
        old_value = self.builder.stats[stat]
        new_value = int(self.values[0])
        new_total = self.builder.total_points() - old_value + new_value

        if new_total > STAT_POOL:
            return await interaction.response.send_message(
                f"❌ That would exceed the {STAT_POOL}-point limit.",
                ephemeral=True,
            )

        self.builder.stats[stat] = new_value
        await self.builder.refresh(interaction)


class CreateKnightButton(discord.ui.Button):
    def __init__(self, builder: "KnightStatBuilderView"):
        self.builder = builder

        super().__init__(
            label="Create Knight",
            style=discord.ButtonStyle.success,
            disabled=(builder.total_points() != STAT_POOL),
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder.user_id:
            return await interaction.response.send_message(
                "❌ This stat builder is not yours.",
                ephemeral=True,
            )

        if self.builder.total_points() != STAT_POOL:
            return await interaction.response.send_message(
                f"❌ You must spend exactly **{STAT_POOL}** points.",
                ephemeral=True,
            )

        db = load_knights()

        if get_knight(db, interaction.user.id):
            return await interaction.response.send_message(
                "❌ You already have a knight. Use `/knight view`.",
                ephemeral=True,
            )

        knight = Knight(
            user_id=interaction.user.id,
            name=self.builder.name,
            stats=dict(self.builder.stats),
        )

        set_knight(db, knight)
        save_knights(db)

        await interaction.response.edit_message(
            content="✅ Knight created.",
            embed=knight_embed(knight, interaction.user),
            view=None,
        )


class ResetStatsButton(discord.ui.Button):
    def __init__(self, builder: "KnightStatBuilderView"):
        self.builder = builder

        super().__init__(
            label="Reset Stats",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder.user_id:
            return await interaction.response.send_message(
                "❌ This stat builder is not yours.",
                ephemeral=True,
            )

        self.builder.stats = {stat: STAT_MIN for stat in STATS}
        self.builder.selected_stat = STATS[0]
        await self.builder.refresh(interaction)


class KnightStatBuilderView(discord.ui.View):
    def __init__(self, user_id: int, name: str):
        super().__init__(timeout=300)

        self.user_id = user_id
        self.name = name
        self.stats: Dict[str, int] = {stat: STAT_MIN for stat in STATS}
        self.selected_stat = STATS[0]

        self.rebuild_items()

    def rebuild_items(self) -> None:
        self.clear_items()
        self.add_item(StatSelect(self))
        self.add_item(ValueSelect(self))
        self.add_item(CreateKnightButton(self))
        self.add_item(ResetStatsButton(self))

    def total_points(self) -> int:
        return sum(self.stats.values())

    def remaining_points(self) -> int:
        return STAT_POOL - self.total_points()

    def make_embed(self) -> discord.Embed:
        total = self.total_points()
        remaining = self.remaining_points()

        e = discord.Embed(
            title=f"Create Knight — {self.name}",
            description=(
                "Use the first dropdown to choose a stat, then the second dropdown to set its value.\n\n"
                f"**Points Used:** {total}/{STAT_POOL}\n"
                f"**Points Remaining:** {remaining}\n"
                f"**Editing:** {self.selected_stat.title()}"
            ),
        )

        stat_lines = []
        for stat in STATS:
            marker = "⬅️" if stat == self.selected_stat else ""
            stat_lines.append(f"**{stat.title()}**: {self.stats[stat]} {marker}")

        e.add_field(name="Stats", value="\n".join(stat_lines), inline=False)

        if total == STAT_POOL:
            e.set_footer(text="Ready. Press Create Knight.")
        else:
            e.set_footer(text="Spend exactly 20 points to enable Create Knight.")

        return e

    async def refresh(self, interaction: discord.Interaction) -> None:
        self.rebuild_items()
        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self,
        )

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True


class KnightCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    knight_group = app_commands.Group(
        name="knight",
        description="Knight creation and management",
    )

    @knight_group.command(name="create", description="Create your knight using dropdown stat selection.")
    async def create(self, interaction: discord.Interaction, name: str):
        try:
            name = validate_name(name)
        except ValueError as e:
            return await interaction.response.send_message(
                f"❌ {e}",
                ephemeral=True,
            )

        db = load_knights()

        if get_knight(db, interaction.user.id):
            return await interaction.response.send_message(
                "❌ You already have a knight. Use `/knight view`.",
                ephemeral=True,
            )

        view = KnightStatBuilderView(
            user_id=interaction.user.id,
            name=name,
        )

        await interaction.response.send_message(
            embed=view.make_embed(),
            view=view,
            ephemeral=True,
        )

    @knight_group.command(name="view", description="View your knight.")
    async def view(self, interaction: discord.Interaction):
        db = load_knights()
        knight = get_knight(db, interaction.user.id)

        if not knight:
            return await interaction.response.send_message(
                "❌ You do not have a knight yet. Use `/knight create`.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            embed=knight_embed(knight, interaction.user),
            ephemeral=True,
        )

    @knight_group.command(name="delete", description="Delete your knight.")
    async def delete(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        db = load_knights()
        user_key = str(interaction.user.id)

        if user_key not in db.get("knights", {}):
            return await interaction.followup.send(
                "❌ You do not have a knight to delete.",
                ephemeral=True,
            )

        del db["knights"][user_key]
        save_knights(db)

        await interaction.followup.send("🗑️ Knight deleted.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(KnightCog(bot))
