from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cogs.horse import Horse, load_horses, save_horses
from cogs.knight import load_knights, save_knights
from services.equipment import ITEMS, get_item, items_by_slot


class EquipmentCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    equip_group = app_commands.Group(
        name="equip",
        description="Equip lances, armour, and horse barding",
    )

    @equip_group.command(name="list", description="List equipment.")
    async def list_items(self, interaction: discord.Interaction, slot: str = ""):
        slot = slot.strip().lower()

        if slot in ("lance", "armour", "barding"):
            items = items_by_slot(slot)  # type: ignore[arg-type]
        else:
            items = ITEMS

        lines = []
        for key, item in items.items():
            lines.append(
                f"• `{key}` — **{item.name}** ({item.slot})\n"
                f"  _{item.description}_"
            )

        e = discord.Embed(
            title="Equipment",
            description="\n".join(lines)[:4096],
        )

        await interaction.response.send_message(embed=e, ephemeral=True)

    @equip_group.command(name="lance", description="Equip a lance.")
    async def equip_lance(self, interaction: discord.Interaction, item_key: str):
        await interaction.response.defer(ephemeral=True)

        item = get_item(item_key)
        if not item or item.slot != "lance":
            return await interaction.followup.send(
                "❌ Unknown lance. Use `/equip list lance`.",
                ephemeral=True,
            )

        db = load_knights()
        knight = db.get("knights", {}).get(str(interaction.user.id))

        if not knight:
            return await interaction.followup.send(
                "❌ You need a knight first.",
                ephemeral=True,
            )

        knight["equipped_lance_key"] = item.key
        db["knights"][str(interaction.user.id)] = knight
        save_knights(db)

        await interaction.followup.send(
            f"✅ Equipped lance: **{item.name}**",
            ephemeral=True,
        )

    @equip_group.command(name="armour", description="Equip armour.")
    async def equip_armour(self, interaction: discord.Interaction, item_key: str):
        await interaction.response.defer(ephemeral=True)

        item = get_item(item_key)
        if not item or item.slot != "armour":
            return await interaction.followup.send(
                "❌ Unknown armour. Use `/equip list armour`.",
                ephemeral=True,
            )

        db = load_knights()
        knight = db.get("knights", {}).get(str(interaction.user.id))

        if not knight:
            return await interaction.followup.send(
                "❌ You need a knight first.",
                ephemeral=True,
            )

        knight["equipped_armour_key"] = item.key
        db["knights"][str(interaction.user.id)] = knight
        save_knights(db)

        await interaction.followup.send(
            f"✅ Equipped armour: **{item.name}**",
            ephemeral=True,
        )

    @equip_group.command(name="barding", description="Equip barding on your bound horse.")
    async def equip_barding(self, interaction: discord.Interaction, item_key: str):
        await interaction.response.defer(ephemeral=True)

        item = get_item(item_key)
        if not item or item.slot != "barding":
            return await interaction.followup.send(
                "❌ Unknown barding. Use `/equip list barding`.",
                ephemeral=True,
            )

        knights_db = load_knights()
        knight = knights_db.get("knights", {}).get(str(interaction.user.id))

        if not knight:
            return await interaction.followup.send(
                "❌ You need a knight first.",
                ephemeral=True,
            )

        horse_id = knight.get("bound_horse_id")
        if not horse_id:
            return await interaction.followup.send(
                "❌ You need a bound horse first. Use `/horse bind`.",
                ephemeral=True,
            )

        horses_db = load_horses()
        raw = horses_db.get("horses", {}).get(horse_id)

        if not raw:
            return await interaction.followup.send(
                "❌ Could not find your bound horse.",
                ephemeral=True,
            )

        horse = Horse.from_dict(raw)

        if horse.owner_id != interaction.user.id:
            return await interaction.followup.send(
                "❌ That horse is not yours.",
                ephemeral=True,
            )

        raw["equipped_barding_key"] = item.key
        horses_db["horses"][horse_id] = raw
        save_horses(horses_db)

        await interaction.followup.send(
            f"✅ Equipped **{item.name}** on **{horse.name}**.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EquipmentCog(bot))