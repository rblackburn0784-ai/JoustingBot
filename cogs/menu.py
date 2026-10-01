from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


def main_menu_embed() -> discord.Embed:
    e = discord.Embed(
        title="🏰 Jousting Bot Main Menu",
        description=(
            "Create a knight, raise a horse, equip both, choose an arena, and run single joust matches.\n\n"
            "**Recommended flow**\n"
            "1. `/knight create`\n"
            "2. `/horse create`\n"
            "3. `/horse bind`\n"
            "4. `/equip list`\n"
            "5. `/arena list`\n"
            "6. `/joust duel`"
        ),
    )
    e.add_field(
        name="Core Systems",
        value="⚔️ Knights\n🐴 Horses\n🛡️ Equipment\n🏟️ Arenas\n🎯 Single Duels",
        inline=False,
    )
    e.set_footer(text="Use the buttons below for command help.")
    return e


def getting_started_embed() -> discord.Embed:
    e = discord.Embed(
        title="📜 Getting Started",
        description=(
            "Start by creating your knight and horse. Both use private dropdown builders, so you do not need to type stat numbers manually."
        ),
    )
    e.add_field(
        name="First-time setup",
        value=(
            "`/knight create name: Sir Example`\n"
            "`/horse create name: Thunder breed: Destrier`\n"
            "`/horse list`\n"
            "`/horse bind horse_id: <id from list>`"
        ),
        inline=False,
    )
    e.add_field(
        name="Then equip and fight",
        value=(
            "`/equip list`\n"
            "`/equip lance item_key: lance_heavy`\n"
            "`/equip armour item_key: armour_full`\n"
            "`/equip barding item_key: barding_steel`\n"
            "`/joust duel opponent: @Opponent arena_key: royal_lists`"
        ),
        inline=False,
    )
    return e


def knight_help_embed() -> discord.Embed:
    e = discord.Embed(
        title="⚔️ Knight Commands",
        description="Knights are the rider/player character.",
    )
    e.add_field(
        name="Commands",
        value=(
            "`/knight create name:<name>` — open the knight stat builder\n"
            "`/knight view` — view your knight\n"
            "`/knight delete` — delete your knight"
        ),
        inline=False,
    )
    e.add_field(
        name="Stats",
        value="Strength, Control, Endurance, Agility, Resolve, Tactics. Spend exactly **20** points.",
        inline=False,
    )
    return e


def horse_help_embed() -> discord.Embed:
    e = discord.Embed(
        title="🐴 Horse Commands",
        description="Horses are created separately and must be bound to your knight before jousting.",
    )
    e.add_field(
        name="Commands",
        value=(
            "`/horse create name:<name> breed:<breed>` — open the horse stat builder\n"
            "`/horse list` — list your horses and IDs\n"
            "`/horse view horse_id:<id>` — view a horse\n"
            "`/horse bind horse_id:<id>` — bind a horse to your knight\n"
            "`/horse delete horse_id:<id>` — delete a horse"
        ),
        inline=False,
    )
    e.add_field(
        name="Stats",
        value="Speed, Stamina, Power, Obedience, Courage. Spend exactly **24** points.",
        inline=False,
    )
    return e


def equipment_help_embed() -> discord.Embed:
    e = discord.Embed(
        title="🛡️ Equipment Commands",
        description="Equipment has positive and negative traits. There is no gold/shop system yet; you can freely equip listed items.",
    )
    e.add_field(
        name="Commands",
        value=(
            "`/equip list` — list everything\n"
            "`/equip list slot:lance` — list lances\n"
            "`/equip list slot:armour` — list armour\n"
            "`/equip list slot:barding` — list horse barding\n"
            "`/equip lance item_key:<key>` — equip a lance\n"
            "`/equip armour item_key:<key>` — equip armour\n"
            "`/equip barding item_key:<key>` — equip barding on your bound horse"
        ),
        inline=False,
    )
    return e


def arena_help_embed() -> discord.Embed:
    e = discord.Embed(
        title="🏟️ Arena Commands",
        description="Arenas modify alignment, charge, slip risk, panic risk, and impact.",
    )
    e.add_field(
        name="Commands",
        value=(
            "`/arena list` — list arenas\n"
            "`/arena view arena_key:<key>` — view arena modifiers"
        ),
        inline=False,
    )
    e.add_field(
        name="Current arenas",
        value="`royal_lists`, `muddy_field`, `frozen_ground`, `wind_swept`, `festival_arena`, `war_torn`",
        inline=False,
    )
    return e


def duel_help_embed() -> discord.Embed:
    e = discord.Embed(
        title="🎯 Joust Duel",
        description="Single-match jousting. Both players need a knight and a bound horse.",
    )
    e.add_field(
        name="Command",
        value="`/joust duel opponent:@Opponent arena_key:royal_lists`",
        inline=False,
    )
    e.add_field(
        name="Scoring",
        value=(
            "Lance break = 1 point\n"
            "Solid hit = 2 points\n"
            "Unhorsed = 3 points\n"
            "First to 3 points or highest score after 5 passes wins."
        ),
        inline=False,
    )
    return e


class MainMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Getting Started", emoji="📜", style=discord.ButtonStyle.primary, row=0)
    async def getting_started(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=getting_started_embed(), view=self)

    @discord.ui.button(label="Knight", emoji="⚔️", style=discord.ButtonStyle.secondary, row=0)
    async def knight(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=knight_help_embed(), view=self)

    @discord.ui.button(label="Horse", emoji="🐴", style=discord.ButtonStyle.secondary, row=0)
    async def horse(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=horse_help_embed(), view=self)

    @discord.ui.button(label="Equipment", emoji="🛡️", style=discord.ButtonStyle.secondary, row=1)
    async def equipment(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=equipment_help_embed(), view=self)

    @discord.ui.button(label="Arenas", emoji="🏟️", style=discord.ButtonStyle.secondary, row=1)
    async def arenas(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=arena_help_embed(), view=self)

    @discord.ui.button(label="Duel", emoji="🎯", style=discord.ButtonStyle.secondary, row=1)
    async def duel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=duel_help_embed(), view=self)

    @discord.ui.button(label="Home", emoji="🏰", style=discord.ButtonStyle.success, row=2)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=main_menu_embed(), view=self)


class MenuCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="menu", description="Open the Jousting Bot main menu.")
    async def menu(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=main_menu_embed(),
            view=MainMenuView(),
            ephemeral=True,
        )

    @app_commands.command(name="help_joust", description="Open the Jousting Bot help menu.")
    async def help_joust(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=main_menu_embed(),
            view=MainMenuView(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(MenuCog(bot))
