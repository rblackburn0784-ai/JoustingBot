"""Equipment commands backed by v0.8 guild-scoped player inventories."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cogs.horse import load_horses
from cogs.knight import load_knights
from services.equipment import ITEMS, get_item, items_by_slot
from services.progression import buy, loadout, set_loadout, unlock_info, wallet


async def send_with_home(interaction: discord.Interaction, message: str) -> None:
    from cogs.menu import HomeOnlyView
    await interaction.response.send_message(
        message, ephemeral=True, view=HomeOnlyView(interaction.user.id)
    )


class EquipmentCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    equip_group = app_commands.Group(
        name="equip", description="Manage your server's lances, armour and barding"
    )

    @equip_group.command(name="list", description="Browse gear and its unlock requirements.")
    async def list_items(self, interaction: discord.Interaction, slot: str = ""):
        slot = slot.strip().lower()
        if slot and slot not in {"lance", "armour", "barding"}:
            return await send_with_home(interaction, "❌ Slot must be lance, armour or barding.")
        from cogs.menu import HomeOnlyView
        e = discord.Embed(title="🛡️ Equipment Catalog",
                          description="Original equipment is free. Extra gear needs achievements and gold.")
        for current_slot in ([slot] if slot else ["lance", "armour", "barding"]):
            lines = []
            for key, item in items_by_slot(current_slot).items():
                state = unlock_info(interaction.guild_id, interaction.user.id, key)
                if state["owned"]:
                    status = "✅ Owned"
                else:
                    status = (f"🔒 {state['cost']} gold · "
                              f"{state['requirement']} {state['progress']}/{state['required']}")
                lines.append(f"**{item.name}** (`{key}`)\n{item.description}\n{status}")
            e.add_field(name=current_slot.title(), value="\n\n".join(lines)[:1024], inline=False)
        await interaction.response.send_message(
            embed=e, ephemeral=True, view=HomeOnlyView(interaction.user.id)
        )

    async def _equip(self, interaction: discord.Interaction, item_key: str, slot: str):
        item = get_item(item_key)
        if not item or item.slot != slot:
            return await send_with_home(interaction, "❌ Unknown equipment key for this slot.")
        if interaction.guild_id is None:
            return await send_with_home(interaction, "❌ Equip gear within a Discord server.")
        knight = load_knights().get("knights", {}).get(str(interaction.user.id))
        if not knight:
            return await send_with_home(interaction, "❌ Create a knight first.")
        horse_id = None
        if slot == "barding":
            horse_id = knight.get("bound_horse_id")
            horse = load_horses().get("horses", {}).get(knight.get("bound_horse_id"))
            if not horse or int(horse.get("owner_id", -1)) != interaction.user.id:
                return await send_with_home(interaction, "❌ Bind a horse you own first.")
        try:
            set_loadout(interaction.guild_id, interaction.user.id, slot, item_key, horse_id=horse_id)
        except ValueError as exc:
            return await send_with_home(interaction, f"🔒 {exc}")
        return await send_with_home(interaction, f"✅ Equipped **{item.name}** in this server.")

    @equip_group.command(name="lance", description="Equip an owned lance.")
    async def lance(self, interaction: discord.Interaction, item_key: str):
        await self._equip(interaction, item_key, "lance")

    @equip_group.command(name="armour", description="Equip owned armour.")
    async def armour(self, interaction: discord.Interaction, item_key: str):
        await self._equip(interaction, item_key, "armour")

    @equip_group.command(name="barding", description="Equip owned barding on your bound mount.")
    async def barding(self, interaction: discord.Interaction, item_key: str):
        await self._equip(interaction, item_key, "barding")

    @equip_group.command(name="unlock", description="Spend earned gold to unlock a sidegrade.")
    async def unlock(self, interaction: discord.Interaction, item_key: str):
        try:
            balance = buy(interaction.guild_id, interaction.user.id, item_key)
        except ValueError as exc:
            return await send_with_home(interaction, f"❌ {exc}")
        item = ITEMS[item_key]
        await send_with_home(
            interaction,
            f"🔓 **{item.name} unlocked!** Gold remaining: **{balance}**. "
            f"Equip it from /menu → Equipment or /equip {item.slot}."
        )

    @equip_group.command(name="wallet", description="View your guild equipment gold balance.")
    async def wallet_command(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            return await send_with_home(interaction, "❌ Open your wallet in a server.")
        balance = wallet(interaction.guild_id, interaction.user.id)
        await send_with_home(interaction, f"🪙 Your equipment gold: **{balance}**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(EquipmentCog(bot))
