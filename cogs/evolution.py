"""v2.9.5 — user-owned, private headquarters, daily renown and stable controls."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from cogs.knight import get_knight, load_knights
from cogs.horse import load_horses
from cogs.menu import OwnedView, MainMenuView, navigate, embed, is_admin
from services.competition import equipped_title, title_progress
from services.evolution import (
    PRESETS, DAILY_QUEST_TYPES, bound_horse, bond, groom, daily_goals,
    claim_goal, preset_names, save_preset, apply_preset, delete_preset,
    preferred_tactics, set_preferred_tactics,
)
from services.injuries import active as active_injuries
from services.progression import loadout, wallet, STARTER
from services.tactics import (
    STYLES, TARGETS, MOVES, GUARDS, CHARGE_INTENSITIES, LANCE_CONTROLS,
    TacticPlan,
)


def my_horses(uid: int) -> list[dict]:
    horses = load_horses().get("horses", {})
    return sorted(
        (value for value in horses.values()
         if isinstance(value, dict) and int(value.get("owner_id", 0)) == uid),
        key=lambda h: (h.get("name", "").casefold(), h.get("horse_id", "")),
    )


class HeadquartersPage(OwnedView):
    def __init__(self, user_id: int, guild_id: int | None):
        super().__init__(user_id)
        self.guild_id = guild_id
        self.button("Daily Objectives", lambda it: navigate(
            it, DailyPage(it.user.id, it.guild_id)), emoji="📜")
        self.button("Stable & Bond", lambda it: navigate(
            it, StableCarePage(it.user.id, it.guild_id)), emoji="🐎")
        self.button("Presets", lambda it: navigate(
            it, PresetPage(it.user.id, it.guild_id)), emoji="🛡️")
        self.button("Preferred Tactics", lambda it: navigate(
            it, TacticsPreferencePage(it.user.id, it.guild_id)), row=1, emoji="🧠")
        self.button("Equipment", lambda it: self._equipment(it), row=1)
        self.home()

    async def _equipment(self, interaction):
        from cogs.menu import EquipmentPage
        await navigate(interaction, EquipmentPage(interaction.user.id, interaction.guild_id))

    def make_embed(self):
        if not self.guild_id:
            return embed("🏰 Knight Headquarters", "Open your headquarters inside a Discord server.")
        knight = get_knight(load_knights(), self.owner_id)
        heading = f"⚔️ **{knight.name}**" if knight else "⚔️ **No knight yet**"
        note = "Create your knight and bind a horse from /menu." if not knight else ""
        horse = None
        if knight and knight.bound_horse_id:
            horse = load_horses().get("horses", {}).get(knight.bound_horse_id)
            if not isinstance(horse, dict) or int(horse.get("owner_id", 0)) != self.owner_id:
                horse = None
        if horse:
            state = bond(self.guild_id, self.owner_id, horse["horse_id"])
            mount = (f"🐎 **{discord.utils.escape_markdown(horse['name'])}** ({horse['breed']}) · "
                     f"{state['rank']} {state['score']}/100"
                     + (" · +1 obedience" if state["obedience_bonus"] else ""))
        else:
            mount = "🐎 **No bound horse**"
        goals = daily_goals(self.guild_id, self.owner_id)
        complete = sum(g["claimed"] for g in goals["goals"].values())
        injuries = active_injuries(self.guild_id, self.owner_id)
        progress = title_progress(self.guild_id, self.owner_id)
        title = equipped_title(self.guild_id, self.owner_id) or "No title equipped"
        gear = ""
        if knight:
            gear = ("🛡️ **Gear:** " + " · ".join(
                loadout(self.guild_id, self.owner_id, slot, STARTER[slot])
                for slot in ("lance", "armour", "helm", "shield")
            ))
        return embed(
            "🏰 Your Knight Headquarters",
            f"{heading}\n{note}\n{mount}\n{gear}\n\n"
            f"🪙 **Gold:** {wallet(self.guild_id, self.owner_id)}"
            f" · ✨ **Renown:** {goals['renown']}\n"
            f"🏅 **Title:** {title} · **Earned:** {sum(x['earned'] for x in progress.values())}/{len(progress)}\n"
            f"🩹 **Active injuries:** {len(injuries)}\n"
            f"📜 **Today's claimed objectives:** {complete}/3\n\n"
            "Presets remember equipment and preferred tactics. "
            "Tactics remain private and must still be locked for each challenge."
        )


class DailyPage(OwnedView):
    def __init__(self, user_id: int, guild_id: int | None):
        super().__init__(user_id)
        self.guild_id = guild_id
        available = daily_goals(guild_id, user_id)["goals"] if guild_id else {}
        for key in DAILY_QUEST_TYPES:
            task = available.get(key, {})
            self.button(
                f"Claim {key.title()}", lambda it, k=key: self.claim(it, k),
                disabled=not task.get("earned") or task.get("claimed", False),
                emoji="🎁",
            )
        self.button("Headquarters", lambda it: navigate(
            it, HeadquartersPage(it.user.id, it.guild_id)), row=1)
        self.home()

    def make_embed(self):
        if not self.guild_id:
            return embed("📜 Daily Objectives", "Daily goals are server-specific.")
        details = daily_goals(self.guild_id, self.owner_id)
        lines = []
        for key, goal in details["goals"].items():
            mark = "✅ Claimed" if goal["claimed"] else "🎁 Ready" if goal["earned"] else "⏳"
            lines.append(f"{mark} **{goal['name']}** — {goal['progress']}/{goal['required']}"
                         f" · +{goal['renown']} renown")
        return embed("📜 Daily Knight Objectives",
                     f"**UTC date:** {details['date']}\n"
                     f"**Lifetime cosmetic renown:** {details['renown']}\n\n"
                     + "\n".join(lines) + "\n\n"
                     "Renown is honorary only: no gold, stat upgrades or prize advantage.")

    async def claim(self, interaction, key):
        if not self.guild_id:
            return await interaction.response.send_message("Use a server.", ephemeral=True)
        try:
            result = claim_goal(self.guild_id, interaction.user.id, key)
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        await navigate(interaction, DailyPage(interaction.user.id, self.guild_id),
                       f"✅ Objective claimed. Total renown: {result['renown']}.")


class StableSelect(discord.ui.Select):
    def __init__(self, parent: "StableCarePage", choices: list[dict]):
        self.page = parent
        super().__init__(row=0, placeholder="Choose your horse", options=[
            discord.SelectOption(label=h.get("name", "Horse")[:100],
                                 value=h["horse_id"], default=h["horse_id"] == parent.horse_id)
            for h in choices[:25]
        ])

    async def callback(self, interaction):
        await navigate(interaction, StableCarePage(interaction.user.id,
                       interaction.guild_id, self.values[0]))


class StableCarePage(OwnedView):
    def __init__(self, user_id: int, guild_id: int | None, horse_id: str | None = None):
        super().__init__(user_id)
        self.guild_id = guild_id
        horses = my_horses(user_id)
        self.horse_id = horse_id if any(h["horse_id"] == horse_id for h in horses) \
            else horses[0]["horse_id"] if horses else None
        if horses:
            self.add_item(StableSelect(self, horses))
        self.button("Groom Horse", self.groom, row=1, disabled=not horses, emoji="🧽")
        self.button("Headquarters", lambda it: navigate(
            it, HeadquartersPage(it.user.id, it.guild_id)), row=1)
        self.home()

    def make_embed(self):
        if not self.guild_id:
            return embed("🐎 Your Stable", "Open your stable inside a server.")
        horse = next((h for h in my_horses(self.owner_id)
                      if h["horse_id"] == self.horse_id), None)
        if not horse:
            return embed("🐎 Your Stable", "Create a horse and bind it to your knight.")
        state = bond(self.guild_id, self.owner_id, horse["horse_id"])
        return embed("🐎 Stable — Trust & Care",
                     f"**{discord.utils.escape_markdown(horse['name'])}** · {horse['breed']}\n"
                     f"**Bond:** {state['score']}/100 — {state['rank']}\n"
                     f"**Completed jousts together:** {state['matches']}\n"
                     f"**Care points:** {state['care_points']}\n"
                     f"**Grooming today:** {'Available' if state['can_groom'] else 'Completed'}\n\n"
                     "Groom once per horse per UTC day for +3 bond. "
                     "Each recorded training or accepted joust grants +2 bond, "
                     "capped at 100. At 40 bond, the horse gains a maximum +1 obedience; "
                     "no stacking beyond that bonus.")

    async def groom(self, interaction):
        if not self.guild_id or not self.horse_id:
            return await interaction.response.send_message("Choose your horse in a server.", ephemeral=True)
        try:
            result = groom(self.guild_id, interaction.user.id, self.horse_id)
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        await navigate(interaction, StableCarePage(interaction.user.id, self.guild_id, self.horse_id),
                       f"✅ Horse groomed. Bond: {result['score']}/100.")


class PresetSelect(discord.ui.Select):
    def __init__(self, page: "PresetPage"):
        self.page = page
        super().__init__(row=0, placeholder="Select preset", options=[
            discord.SelectOption(label=label, value=key,
                                 default=page.selected == key)
            for key, label in PRESETS.items()
        ])

    async def callback(self, interaction):
        await navigate(interaction, PresetPage(interaction.user.id,
                       interaction.guild_id, self.values[0]))


class PresetPage(OwnedView):
    def __init__(self, user_id: int, guild_id: int | None, selected: str = "balanced"):
        super().__init__(user_id)
        self.guild_id = guild_id
        self.selected = selected if selected in PRESETS else "balanced"
        self.add_item(PresetSelect(self))
        self.button("Save Current", self.save, row=1, emoji="💾")
        self.button("Equip Preset", self.apply, row=1, style=discord.ButtonStyle.primary)
        self.button("Delete Preset", self.delete, row=1, style=discord.ButtonStyle.danger)
        self.button("Tactics", lambda it: navigate(
            it, TacticsPreferencePage(it.user.id, it.guild_id)), row=2)
        self.button("Headquarters", lambda it: navigate(
            it, HeadquartersPage(it.user.id, it.guild_id)), row=2)
        self.home()

    def make_embed(self):
        if not self.guild_id:
            return embed("🛡️ Loadout Presets", "Save your gear in a server.")
        slots = preset_names(self.guild_id, self.owner_id)
        current = slots.get(self.selected)
        rows = [f"{'✅' if value else '⚪'} **{PRESETS[key]}**" for key, value in slots.items()]
        detail = "Empty — equip gear, then save." if not current else (
            "Horse: `" + current["horse_id"] + "`\n" +
            "\n".join(f"**{slot.title()}:** {key}"
                      for slot, key in current["gear"].items()) +
            "\n**Tactics:** " + str(current.get("tactics", {}))
        )
        return embed("🛡️ Knight & Horse Loadout Presets",
                     "\n".join(rows) + f"\n\n**Selected: {PRESETS[self.selected]}**\n" + detail
                     + "\n\nPresets save your current bound horse's equipment and your "
                       "preferred private tactics. They cannot equip locked items or "
                       "another player's mount.")

    async def _perform(self, interaction, fn, success):
        if not self.guild_id:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        try:
            fn(self.guild_id, interaction.user.id, self.selected)
        except (ValueError, KeyError) as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        await navigate(interaction, PresetPage(interaction.user.id, self.guild_id, self.selected), success)

    async def save(self, interaction):
        await self._perform(interaction, save_preset, "✅ Current gear and tactics saved.")

    async def apply(self, interaction):
        await self._perform(interaction, apply_preset, "✅ Preset equipped. Tactics still require private locking.")

    async def delete(self, interaction):
        await self._perform(interaction, delete_preset, "✅ Preset removed; equipped gear unchanged.")


class PreferenceSelect(discord.ui.Select):
    def __init__(self, page: "TacticsPreferencePage", field: str, options: dict, row: int):
        self.page = page
        self.field = field
        super().__init__(row=row, placeholder=field.title(), options=[
            discord.SelectOption(label=meta[0][:100], value=key,
                                 default=getattr(page.plan, field) == key)
            for key, meta in options.items()
        ])

    async def callback(self, interaction):
        kwargs = self.page.plan.as_dict()
        kwargs[self.field] = self.values[0]
        await navigate(interaction, TacticsPreferencePage(
            interaction.user.id, interaction.guild_id, **kwargs))


class TacticsPreferencePage(OwnedView):
    def __init__(self, user_id: int, guild_id: int | None,
                 style: str | None = None, target: str | None = None,
                 manoeuvre: str | None = None, shield_guard: str | None = None,
                 charge_intensity: str | None = None,
                 lance_control: str | None = None):
        super().__init__(user_id)
        self.guild_id = guild_id
        plan = preferred_tactics(guild_id, user_id) if guild_id else TacticPlan()
        self.plan = TacticPlan(
            style=style or plan.style, target=target or plan.target,
            manoeuvre=manoeuvre or plan.manoeuvre,
            shield_guard=shield_guard or plan.shield_guard,
            charge_intensity=charge_intensity or plan.charge_intensity,
            lance_control=lance_control or plan.lance_control,
        )
        self.add_item(PreferenceSelect(self, "style", STYLES, 0))
        self.add_item(PreferenceSelect(self, "target", TARGETS, 1))
        self.add_item(PreferenceSelect(self, "manoeuvre", MOVES, 2))
        self.button("Advanced Defaults", self.advanced, row=3, emoji="🛡️")
        self.button("Save Preference", self.save, row=3, style=discord.ButtonStyle.primary)
        self.button("Headquarters", lambda it: navigate(
            it, HeadquartersPage(it.user.id, it.guild_id)), row=3)
        self.home()

    def make_embed(self):
        return embed("🧠 Preferred Tactical Plan",
                     f"**Style:** {self.plan.style}\n**Target:** {self.plan.target}\n"
                     f"**Manoeuvre:** {self.plan.manoeuvre}\n"
                     f"**Shield guard:** {self.plan.shield_guard}\n"
                     f"**Charge:** {self.plan.charge_intensity}\n"
                     f"**Lance grip:** {self.plan.lance_control}\n\n"
                     "Your plan is stored privately and prefilled when you first "
                     "open the tactics editor for a new challenge. It is not "
                     "automatically locked or revealed to your opponent.")

    async def advanced(self, interaction):
        await navigate(interaction, AdvancedPreferencePage(
            interaction.user.id, interaction.guild_id, self.plan))

    async def save(self, interaction):
        if not self.guild_id:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        try:
            set_preferred_tactics(self.guild_id, interaction.user.id, **self.plan.as_dict())
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        await navigate(interaction, TacticsPreferencePage(interaction.user.id, self.guild_id),
                       "✅ Preferred tactics saved privately.")





class AdvancedPreferenceSelect(discord.ui.Select):
    def __init__(self, page: "AdvancedPreferencePage", field: str,
                 choices: dict, row: int):
        self.page = page
        self.field = field
        super().__init__(row=row, placeholder=field.replace("_", " ").title(),
                         options=[
                             discord.SelectOption(
                                 label=value[0][:100], value=key,
                                 description=value[1][:100],
                                 default=getattr(page.plan, field) == key,
                             )
                             for key, value in choices.items()
                         ])

    async def callback(self, interaction: discord.Interaction):
        data = self.page.plan.as_dict()
        data[self.field] = self.values[0]
        await navigate(interaction, AdvancedPreferencePage(
            interaction.user.id, interaction.guild_id, TacticPlan(**data)))


class AdvancedPreferencePage(OwnedView):
    def __init__(self, user_id: int, guild_id: int | None, plan: TacticPlan):
        super().__init__(user_id)
        self.guild_id = guild_id
        self.plan = plan
        for row, (field, options) in enumerate((
            ("shield_guard", GUARDS),
            ("charge_intensity", CHARGE_INTENSITIES),
            ("lance_control", LANCE_CONTROLS),
        )):
            self.add_item(AdvancedPreferenceSelect(self, field, options, row))
        self.button("Back to Tactics", lambda it: navigate(
            it, TacticsPreferencePage(it.user.id, it.guild_id, **self.plan.as_dict())),
            row=3, style=discord.ButtonStyle.primary)
        self.home()

    def make_embed(self):
        return embed(
            "🛡️ Advanced Tactical Defaults",
            f"**Shield:** {GUARDS[self.plan.shield_guard][0]}\n"
            f"**Charge:** {CHARGE_INTENSITIES[self.plan.charge_intensity][0]}\n"
            f"**Lance:** {LANCE_CONTROLS[self.plan.lance_control][0]}\n\n"
            "Select your options, then return to Tactics and press **Save Preference**. "
            "These are just defaults; both players still lock tactics privately.",
        )


class EvolutionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    stable_group = app_commands.Group(name="stable", description="Horse bonds and daily care")
    presets_group = app_commands.Group(name="presets", description="Manage knight and horse loadout presets")

    @app_commands.command(name="headquarters", description="View your knight's personal headquarters.")
    async def headquarters(self, interaction: discord.Interaction):
        page = HeadquartersPage(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(embed=page.make_embed(), view=page, ephemeral=True)

    @app_commands.command(name="daily", description="View and claim daily honorary objectives.")
    async def daily(self, interaction: discord.Interaction):
        page = DailyPage(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(embed=page.make_embed(), view=page, ephemeral=True)

    @stable_group.command(name="bond", description="Check bond with your bound or chosen horse.")
    async def stable_bond(self, interaction: discord.Interaction, horse_id: str = ""):
        if not interaction.guild_id:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        try:
            hid = horse_id or bound_horse(interaction.user.id)["horse_id"]
            result = bond(interaction.guild_id, interaction.user.id, hid)
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        page = StableCarePage(interaction.user.id, interaction.guild_id, hid)
        await interaction.response.send_message(embed=page.make_embed(), view=page, ephemeral=True)

    @stable_group.command(name="groom", description="Groom one owned horse once per UTC day.")
    async def stable_groom(self, interaction: discord.Interaction, horse_id: str = ""):
        if not interaction.guild_id:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        try:
            hid = horse_id or bound_horse(interaction.user.id)["horse_id"]
            result = groom(interaction.guild_id, interaction.user.id, hid)
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        await interaction.response.send_message(
            f"🐎 Horse groomed! Bond {result['score']}/100 — {result['rank']}.", ephemeral=True)

    @presets_group.command(name="save", description="Save your current owned equipment as a preset.")
    async def preset_save(self, interaction: discord.Interaction,
                          name: str = "balanced"):
        try:
            save_preset(interaction.guild_id, interaction.user.id, name)
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        await interaction.response.send_message(f"💾 Saved **{PRESETS[name]}** preset.", ephemeral=True)

    @presets_group.command(name="equip", description="Apply an owned equipment preset.")
    async def preset_equip(self, interaction: discord.Interaction, name: str = "balanced"):
        try:
            apply_preset(interaction.guild_id, interaction.user.id, name)
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        await interaction.response.send_message(
            f"🛡️ Equipped **{PRESETS[name]}**. You still must lock tactics before a challenge.",
            ephemeral=True)

    @presets_group.command(name="view", description="Browse your saved loadout presets.")
    async def preset_view(self, interaction: discord.Interaction):
        page = PresetPage(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(embed=page.make_embed(), view=page, ephemeral=True)

    @presets_group.command(name="tactics", description="Save preferred tactical choices.")
    async def preset_tactics(self, interaction: discord.Interaction, style: str = "balanced",
                             target: str = "shield", manoeuvre: str = "none",
                             shield_guard: str = "", charge_intensity: str = "",
                             lance_control: str = ""):
        if not interaction.guild_id:
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        try:
            plan = set_preferred_tactics(
                interaction.guild_id, interaction.user.id,
                style=style, target=target, manoeuvre=manoeuvre,
                shield_guard=shield_guard or None,
                charge_intensity=charge_intensity or None,
                lance_control=lance_control or None)
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        await interaction.response.send_message(
            f"🧠 Preferred tactics saved: {plan.style} / {plan.target} / {plan.manoeuvre}. "
            "Still requires your private Lock Tactics confirmation.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EvolutionCog(bot))
