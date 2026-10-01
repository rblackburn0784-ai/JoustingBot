from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.knight import load_knights, save_knights
from services.storage import load_json, save_json


HORSES_DB_PATH = "storage/horses.json"

HORSE_STATS = ("speed", "stamina", "power", "obedience", "courage")
HORSE_STAT_POOL = 24
HORSE_STAT_MIN = 1
HORSE_STAT_MAX = 10

NAME_RE = re.compile(r"^[A-Za-z0-9 _\-'.]{2,24}$")
BREED_RE = re.compile(r"^[A-Za-z0-9 _\-'.]{2,28}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_horses() -> Dict[str, Any]:
    return load_json(HORSES_DB_PATH, {"horses": {}})


def save_horses(db: Dict[str, Any]) -> None:
    save_json(HORSES_DB_PATH, db)


@dataclass
class Horse:
    horse_id: str
    owner_id: int
    name: str
    breed: str
    stats: Dict[str, int]

    equipped_barding_key: str = "barding_none"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Horse":
        return Horse(
            horse_id=str(data["horse_id"]),
            owner_id=int(data["owner_id"]),
            name=str(data["name"]),
            breed=str(data["breed"]),
            stats=dict(data["stats"]),
            equipped_barding_key=data.get("equipped_barding_key", "barding_none"),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
        )


def make_horse_id(owner_id: int, name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "-", name.lower()).strip("-")
    stamp = int(datetime.now(timezone.utc).timestamp())
    return f"h-{owner_id}-{safe}-{stamp}"


def validate_text(value: str, regex: re.Pattern, field_name: str) -> str:
    value = value.strip()

    if not regex.match(value):
        raise ValueError(f"{field_name} has invalid characters or length.")

    return value


def validate_horse_stats(stats: Dict[str, int]) -> None:
    missing = [s for s in HORSE_STATS if s not in stats]
    if missing:
        raise ValueError(f"Missing horse stats: {', '.join(missing)}")

    for stat, value in stats.items():
        if stat not in HORSE_STATS:
            raise ValueError(f"Unknown horse stat: {stat}")

        if value < HORSE_STAT_MIN or value > HORSE_STAT_MAX:
            raise ValueError(
                f"{stat.title()} must be between {HORSE_STAT_MIN} and {HORSE_STAT_MAX}."
            )

    total = sum(stats.values())
    if total != HORSE_STAT_POOL:
        raise ValueError(f"Horse stats must total {HORSE_STAT_POOL}. You provided {total}.")


def horse_embed(horse: Horse, user: discord.abc.User) -> discord.Embed:
    e = discord.Embed(
        title=f"{horse.name} ({horse.breed})",
        description=f"Horse profile for {user.mention}",
    )

    stats = "\n".join(
        f"**{stat.title()}**: {horse.stats.get(stat, 0)}"
        for stat in HORSE_STATS
    )

    e.add_field(name="Stats", value=stats, inline=False)
    e.add_field(name="Barding", value=f"`{horse.equipped_barding_key}`", inline=True)
    e.add_field(name="Horse ID", value=f"`{horse.horse_id}`", inline=False)

    return e


class HorseStatSelect(discord.ui.Select):
    def __init__(self, builder: "HorseStatBuilderView"):
        self.builder = builder

        options = [
            discord.SelectOption(
                label=stat.title(),
                value=stat,
                description=f"Current value: {builder.stats[stat]}",
                default=(stat == builder.selected_stat),
            )
            for stat in HORSE_STATS
        ]

        super().__init__(
            placeholder="Choose a horse stat to edit",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder.user_id:
            return await interaction.response.send_message(
                "❌ This horse builder is not yours.",
                ephemeral=True,
            )

        self.builder.selected_stat = str(self.values[0])
        await self.builder.refresh(interaction)


class HorseValueSelect(discord.ui.Select):
    def __init__(self, builder: "HorseStatBuilderView"):
        self.builder = builder
        stat = builder.selected_stat
        current_value = builder.stats[stat]

        max_allowed = min(HORSE_STAT_MAX, current_value + builder.remaining_points())

        options = [
            discord.SelectOption(
                label=str(value),
                value=str(value),
                description=f"Set {stat.title()} to {value}",
                default=(value == current_value),
            )
            for value in range(HORSE_STAT_MIN, max_allowed + 1)
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
                "❌ This horse builder is not yours.",
                ephemeral=True,
            )

        stat = self.builder.selected_stat
        old_value = self.builder.stats[stat]
        new_value = int(self.values[0])
        new_total = self.builder.total_points() - old_value + new_value

        if new_total > HORSE_STAT_POOL:
            return await interaction.response.send_message(
                f"❌ That would exceed the {HORSE_STAT_POOL}-point limit.",
                ephemeral=True,
            )

        self.builder.stats[stat] = new_value
        await self.builder.refresh(interaction)


class CreateHorseButton(discord.ui.Button):
    def __init__(self, builder: "HorseStatBuilderView"):
        self.builder = builder

        super().__init__(
            label="Create Horse",
            style=discord.ButtonStyle.success,
            disabled=(builder.total_points() != HORSE_STAT_POOL),
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder.user_id:
            return await interaction.response.send_message(
                "❌ This horse builder is not yours.",
                ephemeral=True,
            )

        if self.builder.total_points() != HORSE_STAT_POOL:
            return await interaction.response.send_message(
                f"❌ You must spend exactly **{HORSE_STAT_POOL}** points.",
                ephemeral=True,
            )

        horses_db = load_horses()

        horse = Horse(
            horse_id=make_horse_id(interaction.user.id, self.builder.name),
            owner_id=interaction.user.id,
            name=self.builder.name,
            breed=self.builder.breed,
            stats=dict(self.builder.stats),
        )

        horses_db.setdefault("horses", {})
        horses_db["horses"][horse.horse_id] = horse.to_dict()
        save_horses(horses_db)

        await interaction.response.edit_message(
            content="✅ Horse created.",
            embed=horse_embed(horse, interaction.user),
            view=None,
        )


class ResetHorseStatsButton(discord.ui.Button):
    def __init__(self, builder: "HorseStatBuilderView"):
        self.builder = builder

        super().__init__(
            label="Reset Stats",
            style=discord.ButtonStyle.secondary,
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.builder.user_id:
            return await interaction.response.send_message(
                "❌ This horse builder is not yours.",
                ephemeral=True,
            )

        self.builder.stats = {stat: HORSE_STAT_MIN for stat in HORSE_STATS}
        self.builder.selected_stat = HORSE_STATS[0]
        await self.builder.refresh(interaction)


class HorseStatBuilderView(discord.ui.View):
    def __init__(self, user_id: int, name: str, breed: str):
        super().__init__(timeout=300)

        self.user_id = user_id
        self.name = name
        self.breed = breed
        self.stats: Dict[str, int] = {stat: HORSE_STAT_MIN for stat in HORSE_STATS}
        self.selected_stat = HORSE_STATS[0]

        self.rebuild_items()

    def rebuild_items(self) -> None:
        self.clear_items()
        self.add_item(HorseStatSelect(self))
        self.add_item(HorseValueSelect(self))
        self.add_item(CreateHorseButton(self))
        self.add_item(ResetHorseStatsButton(self))

    def total_points(self) -> int:
        return sum(self.stats.values())

    def remaining_points(self) -> int:
        return HORSE_STAT_POOL - self.total_points()

    def make_embed(self) -> discord.Embed:
        total = self.total_points()
        remaining = self.remaining_points()

        e = discord.Embed(
            title=f"Create Horse — {self.name}",
            description=(
                f"Breed: **{self.breed}**\n\n"
                "Use the first dropdown to choose a stat, then the second dropdown to set its value.\n\n"
                f"**Points Used:** {total}/{HORSE_STAT_POOL}\n"
                f"**Points Remaining:** {remaining}\n"
                f"**Editing:** {self.selected_stat.title()}"
            ),
        )

        stat_lines = []
        for stat in HORSE_STATS:
            marker = "⬅️" if stat == self.selected_stat else ""
            stat_lines.append(f"**{stat.title()}**: {self.stats[stat]} {marker}")

        e.add_field(name="Stats", value="\n".join(stat_lines), inline=False)

        if total == HORSE_STAT_POOL:
            e.set_footer(text="Ready. Press Create Horse.")
        else:
            e.set_footer(text="Spend exactly 24 points to enable Create Horse.")

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


class HorseCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    horse_group = app_commands.Group(
        name="horse",
        description="Horse creation and management",
    )

    @horse_group.command(name="create", description="Create a horse using dropdown stat selection.")
    async def create(
        self,
        interaction: discord.Interaction,
        name: str,
        breed: str,
    ):
        try:
            name = validate_text(name, NAME_RE, "Name")
            breed = validate_text(breed, BREED_RE, "Breed")
        except ValueError as e:
            return await interaction.response.send_message(f"❌ {e}", ephemeral=True)

        view = HorseStatBuilderView(
            user_id=interaction.user.id,
            name=name,
            breed=breed,
        )

        await interaction.response.send_message(
            embed=view.make_embed(),
            view=view,
            ephemeral=True,
        )

    @horse_group.command(name="list", description="List your horses.")
    async def list_horses(self, interaction: discord.Interaction):
        horses_db = load_horses()
        owned: List[Horse] = []

        for raw in horses_db.get("horses", {}).values():
            horse = Horse.from_dict(raw)
            if horse.owner_id == interaction.user.id:
                owned.append(horse)

        if not owned:
            return await interaction.response.send_message(
                "You have no horses yet. Use `/horse create`.",
                ephemeral=True,
            )

        lines = [
            f"• **{h.name}** ({h.breed}) — `{h.horse_id}` — Barding: `{h.equipped_barding_key}`"
            for h in owned
        ]

        e = discord.Embed(
            title=f"{interaction.user.display_name}'s Stable",
            description="\n".join(lines),
        )

        await interaction.response.send_message(embed=e, ephemeral=True)

    @horse_group.command(name="view", description="View a horse by ID.")
    async def view(self, interaction: discord.Interaction, horse_id: str):
        horses_db = load_horses()
        raw = horses_db.get("horses", {}).get(horse_id)

        if not raw:
            return await interaction.response.send_message(
                "❌ Horse not found.",
                ephemeral=True,
            )

        horse = Horse.from_dict(raw)

        if horse.owner_id != interaction.user.id:
            return await interaction.response.send_message(
                "❌ That horse is not yours.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            embed=horse_embed(horse, interaction.user),
            ephemeral=True,
        )

    @horse_group.command(name="bind", description="Bind one of your horses to your knight.")
    async def bind(self, interaction: discord.Interaction, horse_id: str):
        await interaction.response.defer(ephemeral=True)

        knights_db = load_knights()
        knight_raw = knights_db.get("knights", {}).get(str(interaction.user.id))

        if not knight_raw:
            return await interaction.followup.send(
                "❌ You need a knight first. Use `/knight create`.",
                ephemeral=True,
            )

        horses_db = load_horses()
        raw = horses_db.get("horses", {}).get(horse_id)

        if not raw:
            return await interaction.followup.send(
                "❌ Horse not found.",
                ephemeral=True,
            )

        horse = Horse.from_dict(raw)

        if horse.owner_id != interaction.user.id:
            return await interaction.followup.send(
                "❌ That horse is not yours.",
                ephemeral=True,
            )

        knight_raw["bound_horse_id"] = horse_id
        knights_db["knights"][str(interaction.user.id)] = knight_raw
        save_knights(knights_db)

        await interaction.followup.send(
            f"✅ Bound **{horse.name}** to your knight.",
            ephemeral=True,
        )

    @horse_group.command(name="delete", description="Delete one of your horses.")
    async def delete(self, interaction: discord.Interaction, horse_id: str):
        await interaction.response.defer(ephemeral=True)

        horses_db = load_horses()
        raw = horses_db.get("horses", {}).get(horse_id)

        if not raw:
            return await interaction.followup.send(
                "❌ Horse not found.",
                ephemeral=True,
            )

        horse = Horse.from_dict(raw)

        if horse.owner_id != interaction.user.id:
            return await interaction.followup.send(
                "❌ That horse is not yours.",
                ephemeral=True,
            )

        del horses_db["horses"][horse_id]
        save_horses(horses_db)

        knights_db = load_knights()
        knight_raw = knights_db.get("knights", {}).get(str(interaction.user.id))

        if knight_raw and knight_raw.get("bound_horse_id") == horse_id:
            knight_raw["bound_horse_id"] = None
            knights_db["knights"][str(interaction.user.id)] = knight_raw
            save_knights(knights_db)

        await interaction.followup.send("🗑️ Horse deleted.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HorseCog(bot))
