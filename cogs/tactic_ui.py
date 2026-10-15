"""Private two-rider tactical choices for an outstanding accepted challenge."""
from __future__ import annotations

import discord

from services.tactics import MOVES, STYLES, TARGETS, TacticPlan, label


class PlanSelect(discord.ui.Select):
    def __init__(self, screen: "TacticEditor", key: str, choices: dict, row: int):
        self.screen = screen
        self.key = key
        names = {"style": "Choose riding style", "target": "Choose lance target",
                 "manoeuvre": "Optional special manoeuvre"}
        super().__init__(placeholder=names[key], row=row, options=[
            discord.SelectOption(
                label=entry[0][:100], value=code,
                description=entry[-1][:100],
                default=getattr(screen.plan, key) == code,
            ) for code, entry in choices.items()
        ])

    async def callback(self, interaction: discord.Interaction):
        data = self.screen.plan.as_dict()
        data[self.key] = self.values[0]
        updated = TacticEditor(self.screen.challenge, self.screen.player_id, TacticPlan(**data))
        await interaction.response.edit_message(embed=updated.make_embed(), view=updated)


class TacticEditor(discord.ui.View):
    """Ephemeral plan editor. Never show a rider's choices in a public embed."""
    def __init__(self, challenge, player_id: int, plan: TacticPlan | None = None):
        super().__init__(timeout=180)
        self.challenge = challenge
        self.player_id = player_id
        self.plan = plan or TacticPlan()
        self.add_item(PlanSelect(self, "style", STYLES, 0))
        self.add_item(PlanSelect(self, "target", TARGETS, 1))
        self.add_item(PlanSelect(self, "manoeuvre", MOVES, 2))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.player_id or self.challenge.completed:
            await interaction.response.send_message(
                "❌ Only an active participant can use this tactical panel.", ephemeral=True)
            return False
        return True

    def make_embed(self) -> discord.Embed:
        box = discord.Embed(
            title="🧠 Private Tactics — Prepare Your Charge",
            description="Choose a style, target and optional manoeuvre, then **Lock Tactics**. "
                        "The other rider sees only that you are ready, not what you chose.",
            colour=discord.Colour.blue(),
        )
        box.add_field(name="Selected", value=label(self.plan), inline=False)
        box.add_field(name="Style", value=STYLES[self.plan.style][-1], inline=False)
        box.add_field(name="Target", value=TARGETS[self.plan.target][-1], inline=False)
        box.add_field(
            name="Manoeuvre",
            value=MOVES[self.plan.manoeuvre][-1] +
                  "\nTwo full passes of cooldown after use. Last Stand activates on "
                  "pass three only when trailing or sufficiently fatigued.",
            inline=False,
        )
        return box

    @discord.ui.button(label="Main Menu", emoji="🏰",
                       style=discord.ButtonStyle.secondary, row=4)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import MainMenuView, is_admin
        view = MainMenuView(interaction.user.id, is_admin(interaction))
        await interaction.response.edit_message(embed=view.make_embed(), view=view)

    @discord.ui.button(label="Lock Tactics", emoji="🔒",
                       style=discord.ButtonStyle.success, row=3)
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.challenge.completed:
            return await interaction.response.send_message("❌ Challenge closed.", ephemeral=True)
        prepared = self.challenge.prepared
        if self.player_id == prepared.challenger.id:
            prepared.tactics_a = self.plan
        elif self.player_id == prepared.opponent.id:
            prepared.tactics_b = self.plan
        else:
            return await interaction.response.send_message("❌ Not a joust participant.", ephemeral=True)
        prepared.tactics_ready.add(self.player_id)
        from cogs.menu import HomeOnlyView
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🔒 Your Tactics Are Locked",
                description="Your selections are private. The challenged player can accept "
                            "once both riders are ready. You can reopen the tactical editor "
                            "and change your plan until acceptance.",
            ),
            view=HomeOnlyView(interaction.user.id),
        )
        if self.challenge.message is not None and not self.challenge.completed:
            from cogs.joust import make_challenge_embed
            try:
                await self.challenge.message.edit(
                    embed=make_challenge_embed(prepared), view=self.challenge)
            except discord.HTTPException:
                pass
