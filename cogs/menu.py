"""JoustingBot v0.7.1 — fully actionable, owner-locked Discord UI hub."""
from __future__ import annotations

import random
import shutil
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from cogs.knight import (
    KnightStatBuilderView, get_knight, load_knights, save_knights,
    knight_embed, validate_name,
)
from cogs.horse import (
    Horse, HorseStatBuilderView, load_horses, save_horses, horse_embed,
    NAME_RE, BREED_RE, validate_text,
)
from cogs.profile import knight_stats_embed, horse_stats_embed, history_lines
from services.arenas import ARENAS
from services.competition import (
    CATEGORIES, TITLE_RULES, equipped_title, ranked, set_title, title_progress,
)
from services.equipment import items_by_slot, get_item
from services.records import load_history

VERSION = "v0.9.0"
STYLE = discord.ButtonStyle


def is_admin(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(interaction.guild_id and perms and perms.manage_guild)


def embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=title, description=description, colour=discord.Colour.dark_gold())
    e.set_footer(text=f"JoustingBot {VERSION} · Use Main Menu to return")
    return e


class Action(discord.ui.Button):
    def __init__(self, label: str, callback, *, row: int = 0,
                 style: discord.ButtonStyle = STYLE.secondary, emoji: str | None = None,
                 disabled: bool = False):
        self.action = callback
        super().__init__(label=label, row=row, style=style, emoji=emoji, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        await self.action(interaction)


class OwnedView(discord.ui.View):
    def __init__(self, user_id: int, *, admin: bool = False):
        super().__init__(timeout=300)
        self.owner_id = user_id
        self.admin_only = admin

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Open your own /menu.", ephemeral=True)
            return False
        if self.admin_only and not is_admin(interaction):
            await interaction.response.send_message("⛔ Admin access requires Manage Server permission.", ephemeral=True)
            return False
        return True

    def button(self, label: str, callback, *, row: int = 0, style=STYLE.secondary,
               emoji: str | None = None, disabled: bool = False):
        self.add_item(Action(label, callback, row=row, style=style, emoji=emoji, disabled=disabled))

    def home(self):
        self.button("Main Menu", lambda it: navigate(it, MainMenuView(it.user.id, is_admin(it))),
                    row=4, style=STYLE.success, emoji="🏰")

    async def on_timeout(self):
        for component in self.children:
            component.disabled = True


async def navigate(interaction: discord.Interaction, view: "OwnedView", message: str | None = None):
    await interaction.response.edit_message(content=message, embed=view.make_embed(), view=view)


class HomeOnlyView(OwnedView):
    """Single-button navigation for modal-generated creation screens."""
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.home()

    def make_embed(self):
        return embed("🏰 Main Menu", "Press Main Menu to return to the hub.")


class PublicHomeView(discord.ui.View):
    """A public button that privately opens the caller's own menu."""
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Main Menu", emoji="🏰", style=discord.ButtonStyle.success)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MainMenuView(interaction.user.id, is_admin(interaction))
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)



async def open_maintenance(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("⛔ Manage Server required.", ephemeral=True)
    from cogs.maintenance import MaintenancePage
    await navigate(interaction, MaintenancePage(interaction.user.id))


async def open_tournaments(interaction: discord.Interaction):
    from cogs.tournament import TournamentHub
    await navigate(interaction, TournamentHub(
        interaction.user.id, interaction.guild_id, is_admin(interaction)))


class VersionPage(OwnedView):
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.home()

    def make_embed(self):
        return embed(
            "⚙️ JoustingBot v0.9.0",
            "**Stability & Admin Tools**\n"
            "Reliable atomic saves, checksum-verified local backups, safe repair previews, "
            "confirmed restores, challenge locks and cooldowns, and clearer errors.\n\n"
            "The admin Maintenance Tools panel is visible only to Manage Server users."
        )


class MainMenuView(OwnedView):
    def __init__(self, user_id: int, allow_admin: bool = False):
        super().__init__(user_id)
        pages = [
            ("Getting Started", "📜", lambda it: navigate(it, StartView(it.user.id))),
            ("Knight", "⚔️", lambda it: navigate(it, KnightPage(it.user.id))),
            ("Horse", "🐎", lambda it: navigate(it, HorsePage(it.user.id))),
            ("Equipment", "🛡️", lambda it: navigate(it, EquipmentPage(it.user.id, it.guild_id))),
            ("Arenas", "🏟️", lambda it: navigate(it, ArenaPage(it.user.id))),
            ("Challenge", "🎯", lambda it: navigate(it, DuelPage(it.user.id))),
            ("Profile", "📜", lambda it: navigate(it, ProfilePage(it.user.id))),
            ("Leaderboards", "🏆", lambda it: navigate(it, LeaderboardPage(it.user.id, it.guild_id))),
            ("Titles", "🏅", lambda it: navigate(it, TitlePage(it.user.id, it.guild_id))),
            ("Progression", "🪙", lambda it: navigate(it, ProgressionPage(it.user.id, it.guild_id))),
            ("Injuries", "🩹", lambda it: navigate(it, InjuryPage(it.user.id, it.guild_id))),
            ("Tournaments", "🏆", open_tournaments),
            ("Version", "ℹ️", lambda it: navigate(it, VersionPage(it.user.id))),
        ]
        for i, (label, icon, action) in enumerate(pages):
            self.button(label, action, row=i // 5, emoji=icon)
        if allow_admin:
            self.button("Admin", lambda it: navigate(it, AdminPage(it.user.id)),
                        row=2, style=STYLE.danger, emoji="⚙️")
        self.home()

    def make_embed(self):
        return embed("🏰 The Grand Lists — Main Menu",
                     "Welcome, rider. Build your knight and mount, choose your equipment, "
                     "challenge another player, and earn your way up the lists.\n\n"
                     "**Every section below opens usable controls.**\n"
                     "⚔️ Knight · 🐎 Horse · 🛡️ Equipment · 🏟️ Arenas\n"
                     "🎯 Challenge · 📜 Profile · 🏆 Leaderboards · 🏅 Titles\n"
                     "🪙 Progression & Gold · 🩹 Injuries & Recovery\n\n"
                     "Only authorised members see the ⚙️ Admin controls.")


class StartView(OwnedView):
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.button("Create Knight", lambda it: navigate(it, KnightPage(it.user.id)), emoji="⚔️")
        self.button("Build Horse", lambda it: navigate(it, HorsePage(it.user.id)), emoji="🐎")
        self.button("Choose Equipment", lambda it: navigate(it, EquipmentPage(it.user.id, it.guild_id)), row=1, emoji="🛡️")
        self.button("Challenge", lambda it: navigate(it, DuelPage(it.user.id)), row=1, emoji="🎯")
        self.button("Earn Gold", lambda it: navigate(it, ProgressionPage(it.user.id, it.guild_id)), row=2, emoji="🪙")
        self.button("Recover", lambda it: navigate(it, InjuryPage(it.user.id, it.guild_id)), row=2, emoji="🩹")
        self.home()

    def make_embed(self):
        return embed("📜 Getting Started", "1. Create a **knight** (20 total stat points).\n"
                     "2. Create a **horse** (24 points), then bind it.\n"
                     "3. Equip a lance, armour and barding.\n"
                     "4. Choose an arena and issue a challenge.\n"
                     "5. Win jousts to appear on leaderboards and unlock titles.\n\n"
                     "Private builders, selections and confirmations are available through the buttons below.")


class KnightModal(discord.ui.Modal, title="Create Your Knight"):
    name = discord.ui.TextInput(label="Knight name", placeholder="Sir Raymond", min_length=2, max_length=24)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            name = validate_name(str(self.name))
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        if get_knight(load_knights(), interaction.user.id):
            return await interaction.response.send_message("❌ You already have a knight.", ephemeral=True)
        view = KnightStatBuilderView(interaction.user.id, name)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)


class ConfirmKnightDelete(OwnedView):
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.button("Confirm Delete", self.confirm, style=STYLE.danger, emoji="🗑️", row=0)
        self.button("Cancel", lambda it: navigate(it, KnightPage(it.user.id)), row=0)
        self.home()

    def make_embed(self):
        return embed("⚠️ Delete Your Knight?", "This removes the active knight but **does not erase historical match results**.")

    async def confirm(self, interaction):
        db = load_knights()
        existed = db.get("knights", {}).pop(str(interaction.user.id), None)
        if existed:
            save_knights(db)
        await navigate(interaction, KnightPage(interaction.user.id), "✅ Knight deleted." if existed else "No knight found.")


class KnightPage(OwnedView):
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.button("Create", self.create, emoji="➕")
        self.button("View Knight", self.view, emoji="🛡️")
        self.button("Career Stats", self.stats, emoji="📊")
        self.button("Delete", lambda it: navigate(it, ConfirmKnightDelete(it.user.id)), style=STYLE.danger)
        self.home()

    def make_embed(self):
        knight = get_knight(load_knights(), self.owner_id)
        return embed("⚔️ Knight Hall", f"Current knight: **{knight.name}**" if knight else
                     "No knight created yet. Press **Create** to begin.")

    async def create(self, interaction):
        await interaction.response.send_modal(KnightModal())

    async def view(self, interaction):
        knight = get_knight(load_knights(), interaction.user.id)
        if knight:
            from services.progression import loadout
            knight.equipped_lance_key = loadout(interaction.guild_id, interaction.user.id,
                                                  "lance", knight.equipped_lance_key)
            knight.equipped_armour_key = loadout(interaction.guild_id, interaction.user.id,
                                                   "armour", knight.equipped_armour_key)
        await interaction.response.edit_message(
            embed=knight_embed(knight, interaction.user) if knight else self.make_embed(), view=self)

    async def stats(self, interaction):
        await interaction.response.edit_message(embed=knight_stats_embed(interaction.user), view=self)


class HorseModal(discord.ui.Modal, title="Create Your Horse"):
    name = discord.ui.TextInput(label="Horse name", placeholder="Thunder", min_length=2, max_length=24)
    breed = discord.ui.TextInput(label="Breed", placeholder="Destrier", min_length=2, max_length=28)

    async def on_submit(self, interaction):
        try:
            name = validate_text(str(self.name), NAME_RE, "Name")
            breed = validate_text(str(self.breed), BREED_RE, "Breed")
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        view = HorseStatBuilderView(interaction.user.id, name, breed)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)


class HorsePage(OwnedView):
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.button("Create Horse", lambda it: it.response.send_modal(HorseModal()), emoji="➕")
        self.button("Manage Stable", lambda it: navigate(it, StableView(it.user.id, guild_id=it.guild_id)), emoji="📋")
        self.home()

    def make_embed(self):
        all_horses = load_horses().get("horses", {}).values()
        owned = [x for x in all_horses if x.get("owner_id") == self.owner_id]
        return embed("🐎 Your Stables", f"**{len(owned)}** horse(s) in your stable.\n"
                     "Create a horse or open **Manage Stable** to view, bind, inspect stats or delete it.")


class HorsePicker(discord.ui.Select):
    def __init__(self, parent: "StableView", choices):
        self.screen = parent
        options = [discord.SelectOption(
            label=Horse.from_dict(raw).name[:100], value=Horse.from_dict(raw).horse_id,
            description=Horse.from_dict(raw).breed[:100],
            default=parent.selected_id == Horse.from_dict(raw).horse_id,
        ) for raw in choices]
        super().__init__(placeholder="Select a horse", options=options, row=0)

    async def callback(self, interaction):
        self.screen.selected_id = self.values[0]
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class StableView(OwnedView):
    PAGE_SIZE = 20

    def __init__(self, user_id: int, page: int = 0, guild_id: int | None = None):
        super().__init__(user_id)
        self.guild_id = guild_id
        self.page = page
        self.raws = [r for r in load_horses().get("horses", {}).values() if r.get("owner_id") == user_id]
        self.raws.sort(key=lambda x: (x.get("name", "").lower(), x.get("horse_id", "")))
        self.page = min(self.page, max(0, (len(self.raws) - 1) // self.PAGE_SIZE))
        choices = self.raws[self.page * self.PAGE_SIZE:(self.page + 1) * self.PAGE_SIZE]
        self.selected_id = choices[0].get("horse_id") if choices else None
        if choices:
            self.add_item(HorsePicker(self, choices))
        self.button("View", self.show, row=1, disabled=not choices)
        self.button("Stats", self.stats, row=1, disabled=not choices)
        self.button("Bind", self.bind, row=1, style=STYLE.primary, disabled=not choices)
        self.button("Delete", self.delete, row=1, style=STYLE.danger, disabled=not choices)
        self.button("◀", lambda it: navigate(it, StableView(it.user.id, self.page - 1, it.guild_id)),
                    row=2, disabled=self.page == 0)
        self.button("▶", lambda it: navigate(it, StableView(it.user.id, self.page + 1, it.guild_id)),
                    row=2, disabled=(self.page + 1) * self.PAGE_SIZE >= len(self.raws))
        self.button("Back", lambda it: navigate(it, HorsePage(it.user.id)), row=2)
        self.home()

    def horse(self):
        raw = load_horses().get("horses", {}).get(self.selected_id)
        if raw and raw.get("owner_id") == self.owner_id:
            return Horse.from_dict(raw)
        return None

    def make_embed(self):
        h = self.horse()
        if h:
            from services.progression import loadout
            current_barding = loadout(self.guild_id, self.owner_id, "barding", h.equipped_barding_key, h.horse_id)
            detail = f"**{h.name}** ({h.breed})\nBarding: {current_barding}\nID: `{h.horse_id}`"
        else:
            detail = "No horse on this page."
        return embed("🐎 Stable Management", f"{detail}\n\nPage {self.page + 1} of "
                     f"{max(1, (len(self.raws) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)}")

    async def show(self, interaction):
        h = self.horse()
        if h:
            from services.progression import loadout
            h.equipped_barding_key = loadout(interaction.guild_id, interaction.user.id,
                                                "barding", h.equipped_barding_key, h.horse_id)
        await interaction.response.edit_message(embed=horse_embed(h, interaction.user) if h else self.make_embed(), view=self)

    async def stats(self, interaction):
        h = self.horse()
        await interaction.response.edit_message(embed=horse_stats_embed(h) if h else self.make_embed(), view=self)

    async def bind(self, interaction):
        h = self.horse()
        if not h:
            return await interaction.response.send_message("❌ Horse not found.", ephemeral=True)
        db = load_knights()
        knight = db.get("knights", {}).get(str(interaction.user.id))
        if not knight:
            return await interaction.response.send_message("❌ Create your knight first.", ephemeral=True)
        knight["bound_horse_id"] = h.horse_id
        save_knights(db)
        await navigate(interaction, StableView(interaction.user.id, self.page, interaction.guild_id), f"✅ {h.name} is now your mount.")

    async def delete(self, interaction):
        h = self.horse()
        if h:
            await navigate(interaction, ConfirmHorseDelete(interaction.user.id, h.horse_id))
        else:
            await interaction.response.send_message("❌ Horse not found.", ephemeral=True)


class ConfirmHorseDelete(OwnedView):
    def __init__(self, user_id: int, horse_id: str):
        super().__init__(user_id)
        self.horse_id = horse_id
        self.button("Confirm Delete", self.confirm, style=STYLE.danger)
        self.button("Cancel", lambda it: navigate(it, StableView(it.user.id, guild_id=it.guild_id)))
        self.home()

    def make_embed(self):
        return embed("⚠️ Delete Horse?", "Deleting a horse will also unbind it from your knight.")

    async def confirm(self, interaction):
        db = load_horses()
        raw = db.get("horses", {}).get(self.horse_id)
        if not raw or raw.get("owner_id") != interaction.user.id:
            return await interaction.response.send_message("❌ That horse is not yours.", ephemeral=True)
        del db["horses"][self.horse_id]
        save_horses(db)
        knights = load_knights()
        knight = knights.get("knights", {}).get(str(interaction.user.id))
        if knight and knight.get("bound_horse_id") == self.horse_id:
            knight["bound_horse_id"] = None
            save_knights(knights)
        await navigate(interaction, StableView(interaction.user.id, guild_id=interaction.guild_id), "🗑️ Horse deleted.")



class InjurySelect(discord.ui.Select):
    def __init__(self, screen: "InjuryPage"):
        self.screen = screen
        super().__init__(
            placeholder="Select an active injury", row=0,
            options=[
                discord.SelectOption(
                    label=f"{w['name']} ({w['stat']})"[:100],
                    value=w["id"],
                    description=f"{screen.duration(w['remaining_seconds'])} to natural recovery"[:100],
                    default=w["id"] == screen.selected,
                ) for w in screen.current[:25]
            ],
        )

    async def callback(self, interaction):
        self.screen.selected = self.values[0]
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class TreatmentSelect(discord.ui.Select):
    def __init__(self, screen: "InjuryPage"):
        from services.injuries import TREATMENTS
        self.screen = screen
        super().__init__(
            placeholder="Choose a treatment provider", row=1,
            options=[
                discord.SelectOption(
                    label=t["name"], value=key,
                    description=f"{t['cost']} gold · up to {t['hours']}h recovery · {t['failure']}% fail",
                    default=key == screen.provider,
                ) for key, t in TREATMENTS.items()
            ],
        )

    async def callback(self, interaction):
        self.screen.provider = self.values[0]
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class InjuryPage(OwnedView):
    """Private injury ward with tiered healing and owned Main Menu navigation."""
    def __init__(self, user_id: int, guild_id: int | None,
                 selected: str | None = None, provider: str = "shady_doctor"):
        super().__init__(user_id)
        from services.injuries import active, duration, TREATMENTS
        self.guild_id = guild_id
        self.duration = duration
        self.provider = provider if provider in TREATMENTS else "shady_doctor"
        self.current = active(guild_id, user_id) if guild_id is not None else []
        self.selected = selected if selected in {i["id"] for i in self.current} else (
            self.current[0]["id"] if self.current else None
        )
        if self.current:
            self.add_item(InjurySelect(self))
            self.add_item(TreatmentSelect(self))
        self.button("Treat Selected", self.treat, row=2, style=STYLE.primary,
                    emoji="🩹", disabled=self.selected is None)
        self.button("Refresh", self.refresh, row=2)
        self.button("Career Profile", lambda it: navigate(it, ProfilePage(it.user.id)), row=3)
        self.home()

    def make_embed(self):
        from services.injuries import TREATMENTS, PENALTY_CAP, MIN_RECOVERY_HOURS, support_for_next_bout
        from services.progression import wallet
        if self.guild_id is None:
            return embed("🩹 Injury Ward", "Open the injury ward in a Discord server.")
        gold = wallet(self.guild_id, self.owner_id)
        title = "🩹 Injury Ward — Recovery"
        if not self.current:
            return embed(title, f"✅ Fully recovered.\n🪙 **Gold:** {gold}\n"
                         "Serious jousting impacts can cause temporary injuries. No treatment is needed now.")
        tier = TREATMENTS[self.provider]
        lines = []
        for wound in self.current[:12]:
            marker = "➡️" if wound["id"] == self.selected else "•"
            sev = wound.get("severity", "moderate").title()
            chance = wound.get("risk")
            info = f" · {chance}% risk at injury" if chance is not None else ""
            lines.append(
                f"{marker} **{wound['name']}** ({sev}) — −1 {wound['stat'].title()} · "
                f"{self.duration(wound['remaining_seconds'])} remaining{info}"
            )
        next_help = support_for_next_bout(self.guild_id, self.owner_id)
        e = embed(title,
            f"🪙 **Gold:** {gold} · **Effective debuff cap:** −{PENALTY_CAP} total stat points\n"
            f"**Selected treatment:** {tier['name']} · {tier['cost']} gold\n"
            f"Up to **{tier['hours']}h** recovery reduction · {tier['failure']}% failure\n"
            f"On successful treatment: **{tier['support']}%** chance of one-bout pain relief.\n"
            f"Treatment cannot cut natural recovery below **{MIN_RECOVERY_HOURS}h**.\n"
            f"**Relief ready for next injured bout:** {'✅ Yes' if next_help else 'No'}\n\n"
            + "\n".join(lines))
        return e

    async def treat(self, interaction):
        if not self.selected:
            return await interaction.response.send_message("✅ No injury needs treatment.", ephemeral=True)
        from services.injuries import heal
        try:
            balance, result = heal(
                interaction.guild_id, interaction.user.id, self.selected, provider=self.provider
            )
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        if result["success"]:
            outcome = (f"✅ **{result['provider']}** helped {result['name']}: "
                       f"recovery shortened by {result['hours_reduced']:.1f} hours.")
            if result["support_ready"]:
                outcome += " 🛡️ Temporary aid available for the next injured bout."
        else:
            outcome = f"⚠️ **{result['provider']}** treatment failed. No recovery time was removed."
        await navigate(
            interaction,
            InjuryPage(interaction.user.id, interaction.guild_id, self.selected, self.provider),
            f"{outcome} You have **{balance} gold** left."
        )

    async def refresh(self, interaction):
        await navigate(interaction, InjuryPage(
            interaction.user.id, interaction.guild_id, self.selected, self.provider
        ))


class EquipmentPage(OwnedView):
    def __init__(self, user_id: int, guild_id: int | None = None):
        super().__init__(user_id)
        self.guild_id = guild_id
        for slot, name in (("lance", "Lances"), ("armour", "Armour"), ("barding", "Horse Barding")):
            self.button(name, lambda it, s=slot: navigate(
                it, EquipmentPicker(it.user.id, s, it.guild_id)), row=0)
        self.button("Progression & Gold", lambda it: navigate(it, ProgressionPage(it.user.id, it.guild_id)),
                    row=1, emoji="🪙")
        self.button("Standards", lambda it: navigate(it, StandardPage(it.user.id, it.guild_id)),
                    row=1, emoji="🚩")
        self.home()

    def make_embed(self):
        from services.progression import loadout, wallet
        knight = get_knight(load_knights(), self.owner_id)
        if knight:
            description = (
                f"**Lance:** {loadout(self.guild_id, self.owner_id, 'lance', knight.equipped_lance_key)}\n"
                f"**Armour:** {loadout(self.guild_id, self.owner_id, 'armour', knight.equipped_armour_key)}\n"
                f"**Bound Horse:** {knight.bound_horse_id or 'None'}"
            )
            raw = load_horses().get("horses", {}).get(knight.bound_horse_id)
            if raw and raw.get("owner_id") == self.owner_id:
                description += (
                    f"\n**Barding:** {loadout(self.guild_id, self.owner_id, 'barding', raw.get('equipped_barding_key'), knight.bound_horse_id)}"
                )
        else:
            description = "Create a knight before equipping."
        money = wallet(self.guild_id, self.owner_id) if self.guild_id else 0
        return embed("🛡️ Armory — Equipment", description + f"\n\n🪙 **{money} gold**"
                     "\nAll twelve starter items are free. Unlock sidegrades by playing accepted jousts.")


class GearSelect(discord.ui.Select):
    def __init__(self, screen: "EquipmentPicker"):
        self.screen = screen
        choices = items_by_slot(screen.slot)
        super().__init__(placeholder="Choose equipment", row=0, options=[
            discord.SelectOption(label=item.name[:100], value=key,
                description=item.description[:100], default=key == screen.selected)
            for key, item in choices.items()
        ])

    async def callback(self, interaction):
        self.screen.selected = self.values[0]
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class EquipmentPicker(OwnedView):
    def __init__(self, user_id: int, slot: str, guild_id: int | None = None, selected: str | None = None):
        super().__init__(user_id)
        self.slot = slot
        self.guild_id = guild_id
        self.selected = selected or next(iter(items_by_slot(slot)))
        self.add_item(GearSelect(self))
        self.button("Equip Selected", self.equip, row=1, style=STYLE.primary)
        self.button("Unlock Selected", self.unlock, row=1, emoji="🔓")
        self.button("Back", lambda it: navigate(it, EquipmentPage(it.user.id, it.guild_id)), row=2)
        self.home()

    def make_embed(self):
        from services.progression import unlock_info, wallet, loadout
        gear = get_item(self.selected)
        state = unlock_info(self.guild_id, self.owner_id, self.selected)
        mods = [f"{attr}: {getattr(gear, attr):+}" for attr in
                ("alignment_mod", "charge_mod", "slip_mod", "panic_mod", "unhorse_resist")
                if getattr(gear, attr) != 0]
        if gear.impact_mult != 1:
            mods.append(f"Impact x{gear.impact_mult:.2f}")
        for field in ("knight_stat_mods", "horse_stat_mods"):
            mods.extend(f"{key}: {value:+}" for key, value in getattr(gear, field).items())
        if state["owned"]:
            access = "✅ Owned · Ready to equip"
        else:
            access = (f"🔒 Requirement: {state['requirement']} "
                      f"{state['progress']}/{state['required']}\n🪙 Cost: **{state['cost']} gold**")
        money = wallet(self.guild_id, self.owner_id) if self.guild_id else 0
        return embed(f"🛡️ {gear.name}", f"{gear.description}\n\n"
                     f"**Trade-offs:** {' · '.join(mods) or 'Balanced'}\n"
                     f"**Status:** {access}\n**Wallet:** {money} gold")

    async def equip(self, interaction):
        from services.progression import set_loadout
        gear = get_item(self.selected)
        if gear is None or gear.slot != self.slot:
            return await interaction.response.send_message("❌ Invalid gear.", ephemeral=True)
        knight = load_knights().get("knights", {}).get(str(interaction.user.id))
        if knight is None:
            return await interaction.response.send_message("❌ Create a knight first.", ephemeral=True)
        if self.slot == "barding":
            horse = load_horses().get("horses", {}).get(knight.get("bound_horse_id"))
            if horse is None or horse.get("owner_id") != interaction.user.id:
                return await interaction.response.send_message("❌ Bind a horse you own first.", ephemeral=True)
        try:
            set_loadout(interaction.guild_id, interaction.user.id, self.slot, self.selected,
                        horse_id=knight.get("bound_horse_id") if self.slot == "barding" else None)
        except ValueError as exc:
            return await interaction.response.send_message(f"🔒 {exc}", ephemeral=True)
        await navigate(interaction, EquipmentPicker(interaction.user.id, self.slot,
                       interaction.guild_id, self.selected), f"✅ Equipped {gear.name}.")

    async def unlock(self, interaction):
        from services.progression import buy
        try:
            balance = buy(interaction.guild_id, interaction.user.id, self.selected)
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        item = get_item(self.selected)
        await navigate(interaction, EquipmentPicker(interaction.user.id, self.slot,
                       interaction.guild_id, self.selected),
                       f"🔓 Unlocked **{item.name}**! {balance} gold remaining.")


class ProgressionPage(OwnedView):
    def __init__(self, user_id: int, guild_id: int | None = None):
        super().__init__(user_id)
        self.guild_id = guild_id
        self.button("Open Armory", lambda it: navigate(it, EquipmentPage(it.user.id, it.guild_id)),
                    row=0, style=STYLE.primary, emoji="🛡️")
        self.button("View Standards", lambda it: navigate(it, StandardPage(it.user.id, it.guild_id)),
                    row=0, emoji="🚩")
        self.button("Injury Ward", lambda it: navigate(it, InjuryPage(it.user.id, it.guild_id)),
                    row=1, emoji="🩹")
        self.home()

    def make_embed(self):
        from services.progression import UNLOCKS, earned_gold, prestige, reputation, wallet, purchased, progress
        if self.guild_id is None:
            return embed("🪙 Career Progression", "Progression is tracked per Discord server. Open /menu in a server.")
        scores = progress(self.guild_id, self.owner_id)
        points, tier = prestige(self.guild_id, self.owner_id)
        rep = reputation(self.guild_id, self.owner_id)
        owned = purchased(self.guild_id, self.owner_id)
        remaining = wallet(self.guild_id, self.owner_id)
        total = earned_gold(self.guild_id, self.owner_id)
        e = embed("🪙 Progression & Unlocks",
                  f"**Rank:** {tier} · **Prestige:** {points} · **Reputation:** {rep}\n"
                  f"**Gold:** {remaining} available · {total} lifetime earned\n"
                  f"**Career:** {scores['jousts']} accepted jousts · {scores['wins']} victories\n\n"
                  "Play accepted challenges to earn gold and prestige. "
                  "Starter gear remains free; unlockables offer trade-offs, not raw power.")
        lines = []
        for key, (name, condition, required, cost) in UNLOCKS.items():
            progress_now = scores[condition]
            icon = "✅" if key in owned else ("🟡" if progress_now >= required else "🔒")
            lines.append(f"{icon} **{name}** — {cost} gold · {condition.replace('_', ' ')} "
                         f"{progress_now}/{required}")
        e.add_field(name="Sidegrade Unlocks", value="\n".join(lines), inline=False)
        return e


class StandardSelect(discord.ui.Select):
    def __init__(self, screen: "StandardPage"):
        from services.progression import STANDARDS
        self.screen = screen
        super().__init__(placeholder="Choose cosmetic standard", row=0, options=[
            discord.SelectOption(label=value[0], value=key, default=key == screen.selected)
            for key, value in STANDARDS.items()
        ])

    async def callback(self, interaction):
        self.screen.selected = self.values[0]
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class StandardPage(OwnedView):
    def __init__(self, user_id: int, guild_id: int | None = None, selected: str = "none"):
        super().__init__(user_id)
        self.guild_id = guild_id
        self.selected = selected
        self.add_item(StandardSelect(self))
        self.button("Equip Standard", self.equip, row=1, style=STYLE.primary)
        self.button("Progression", lambda it: navigate(it, ProgressionPage(it.user.id, it.guild_id)), row=1)
        self.home()

    def make_embed(self):
        from services.progression import STANDARDS, equipped_standard, standard_info
        if self.guild_id is None:
            return embed("🚩 Cosmetic Standards", "Open this section inside a Discord server.")
        lines = []
        for key in STANDARDS:
            status = standard_info(self.guild_id, self.owner_id, key)
            icon = "✅" if status["earned"] else "🔒"
            lines.append(f"{icon} **{status['name']}** — {status['progress']}/{status['required']} "
                         f"{STANDARDS[key][1].replace('_', ' ')}")
        return embed("🚩 Cosmetic Standards",
                     f"**Equipped:** {equipped_standard(self.guild_id, self.owner_id) or 'None'}\n"
                     f"**Selected:** {STANDARDS[self.selected][0]}\n\n"
                     + "\n".join(lines)
                     + "\n\nStandards are purely visual and give no combat advantage.")

    async def equip(self, interaction):
        from services.progression import STANDARDS, set_standard
        try:
            set_standard(interaction.guild_id, interaction.user.id, self.selected)
        except ValueError as exc:
            return await interaction.response.send_message(f"🔒 {exc}", ephemeral=True)
        await navigate(interaction, StandardPage(interaction.user.id, interaction.guild_id,
                       self.selected), f"✅ Equipped {STANDARDS[self.selected][0]}.")


class ArenaSelect(discord.ui.Select):
    def __init__(self, parent: "ArenaPage"):
        self.screen = parent
        super().__init__(placeholder="Choose arena", row=0, options=[
            discord.SelectOption(label=arena.name[:100], value=key, default=key == parent.selected)
            for key, arena in ARENAS.items()
        ])

    async def callback(self, interaction):
        self.screen.selected = self.values[0]
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class ArenaPage(OwnedView):
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.selected = "royal_lists"
        self.add_item(ArenaSelect(self))
        self.button("Random Arena", self.random, row=1)
        self.button("Challenge Here", lambda it: navigate(it, DuelPage(it.user.id, arena_key=self.selected)),
                    row=1, style=STYLE.primary)
        self.home()

    def make_embed(self):
        a = ARENAS[self.selected]
        return embed(f"🏟️ {a.name}", f"{a.description}\n\n"
                     f"Alignment {a.alignment_mod:+} · Charge {a.charge_mod:+}\n"
                     f"Slip {a.slip_mod:+} · Panic {a.panic_mod:+} · Impact x{a.impact_mult:.2f}")

    async def random(self, interaction):
        self.selected = random.choice(list(ARENAS))
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


class ArenaForDuel(discord.ui.Select):
    def __init__(self, parent: "DuelPage"):
        self.screen = parent
        super().__init__(placeholder="Choose arena", row=1, options=[
            discord.SelectOption(label=v.name, value=k, default=k == parent.arena_key)
            for k, v in ARENAS.items()
        ])

    async def callback(self, interaction):
        self.screen.arena_key = self.values[0]
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class OpponentSelect(discord.ui.UserSelect):
    def __init__(self, parent: "DuelPage"):
        self.screen = parent
        super().__init__(placeholder="Select a Discord player to challenge", row=0)

    async def callback(self, interaction):
        self.screen.opponent_id = self.values[0].id
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class DuelPage(OwnedView):
    def __init__(self, user_id: int, arena_key: str = "royal_lists", *, instant: bool = False):
        super().__init__(user_id, admin=instant)
        self.arena_key = arena_key
        self.opponent_id = None
        self.instant = instant
        self.add_item(OpponentSelect(self))
        self.add_item(ArenaForDuel(self))
        self.button("Run Test Duel" if instant else "Issue Challenge", self.start,
                    row=2, style=STYLE.primary)
        self.button("Random Arena", self.random, row=2)
        self.home()

    def make_embed(self):
        mode = "**ADMIN-ONLY instant test**" if self.instant else "Opponent must accept before the joust runs."
        opponent = f"<@{self.opponent_id}>" if self.opponent_id else "Not yet selected"
        return embed("🎯 " + ("Test Duel" if self.instant else "Joust Challenge"),
                     f"**Opponent:** {opponent}\n**Arena:** {ARENAS[self.arena_key].name}\n\n"
                     f"{mode}\n\nSelect a player and arena, then press the action button.")

    async def random(self, interaction):
        self.arena_key = random.choice(list(ARENAS))
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    async def start(self, interaction):
        from cogs.joust import ChallengeView, make_challenge_embed
        if self.instant and not is_admin(interaction):
            return await interaction.response.send_message("⛔ Admin only.", ephemeral=True)
        if not interaction.guild or not interaction.channel or not self.opponent_id:
            return await interaction.response.send_message("❌ Select an opponent in a server channel.", ephemeral=True)
        opponent = interaction.guild.get_member(self.opponent_id)
        if not opponent:
            try:
                opponent = await interaction.guild.fetch_member(self.opponent_id)
            except discord.HTTPException:
                return await interaction.response.send_message("❌ Player not found in this server.", ephemeral=True)
        cog = interaction.client.get_cog("JoustCog")
        if not cog:
            return await interaction.response.send_message("❌ Joust system unavailable.", ephemeral=True)
        if cog.is_player_busy(interaction.user.id) or cog.is_player_busy(opponent.id):
            return await interaction.response.send_message("❌ One rider already has an active challenge.", ephemeral=True)
        error, prepared = cog.prepare_duel(
            challenger=interaction.user, opponent=opponent, arena_key=self.arena_key,
            guild_id=interaction.guild_id,
        )
        if error or prepared is None:
            return await interaction.response.send_message(error or "❌ Could not prepare duel.", ephemeral=True)
        if not self.instant:
            remaining = cog.cooldown_remaining(interaction.guild_id, interaction.user.id)
            if remaining:
                return await interaction.response.send_message(
                    f"⌛ Wait {remaining}s before sending another challenge.", ephemeral=True)
        if not cog.try_lock_challenge(interaction.user.id, opponent.id):
            return await interaction.response.send_message("❌ A rider is already busy.", ephemeral=True)
        try:
            await interaction.response.defer(ephemeral=True)
            if self.instant:
                await cog.send_match(interaction.channel, prepared)
                return await interaction.followup.send(
                    "✅ Test duel posted. Competitive records are unaffected.", ephemeral=True)
            prepared.mode = "challenge"
            challenge_view = ChallengeView(cog, prepared)
            try:
                challenge_view.message = await interaction.channel.send(
                    embed=make_challenge_embed(prepared), view=challenge_view)
            except Exception:
                challenge_view.stop()
                raise
            cog.mark_challenge_posted(interaction.guild_id, interaction.user.id)
            await interaction.followup.send("✅ Public challenge posted.", ephemeral=True)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Duel menu action failed")
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Failed to post the match. Ask an admin to check the logs.", ephemeral=True)
            else:
                await interaction.response.send_message(
                    "❌ Failed to post the match.", ephemeral=True)
        finally:
            # Accepted challenges retain their lock until declined, expired or completed.
            if self.instant or 'challenge_view' not in locals() or challenge_view.message is None:
                cog.release_challenge(interaction.user.id, opponent.id)


class OtherPlayerSelect(discord.ui.UserSelect):
    def __init__(self, parent: "ProfilePage"):
        self.screen = parent
        super().__init__(placeholder="Choose a rider to view", row=0)

    async def callback(self, interaction):
        self.screen.target = self.values[0]
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class ProfilePage(OwnedView):
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.target = None
        self.add_item(OtherPlayerSelect(self))
        self.button("My Profile", self.mine, row=1)
        self.button("Career Stats", self.stats, row=1)
        self.button("Match History", self.history, row=1)
        self.button("Injury Ward", lambda it: navigate(it, InjuryPage(it.user.id, it.guild_id)), row=2, emoji="🩹")
        self.home()

    def make_embed(self):
        # Other riders are selected by Discord's user selector; they need not be online.
        if self.target is None:
            return embed("📜 Rider Profiles",
                         "Press **My Profile**, or select another Discord user above.\n"
                         "Career summaries show historical results and equipped titles.")
        e = knight_stats_embed(self.target)
        e.add_field(name="📜 Last Five Matches", value=history_lines(self.target.id)[:1024], inline=False)
        return e

    async def mine(self, interaction):
        self.target = interaction.user
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    async def stats(self, interaction):
        user = self.target or interaction.user
        await interaction.response.edit_message(embed=knight_stats_embed(user), view=self)

    async def history(self, interaction):
        user = self.target or interaction.user
        await interaction.response.edit_message(embed=embed("📜 Last Five Jousts", history_lines(user.id)[:4000]), view=self)


class RankingSelect(discord.ui.Select):
    def __init__(self, parent: "LeaderboardPage"):
        self.screen = parent
        super().__init__(placeholder="Select leaderboard", row=0, options=[
            discord.SelectOption(label=name[:100], value=key, default=key == parent.category)
            for key, name in CATEGORIES.items()
        ])

    async def callback(self, interaction):
        self.screen.category = self.values[0]
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class LeaderboardPage(OwnedView):
    def __init__(self, user_id: int, guild_id: int | None, category: str = "wins"):
        super().__init__(user_id)
        self.guild_id = guild_id
        self.category = category
        self.add_item(RankingSelect(self))
        self.button("Refresh Board", lambda it: navigate(it, LeaderboardPage(it.user.id, it.guild_id, self.category)),
                    row=1, style=STYLE.primary)
        self.home()

    def make_embed(self):
        if self.guild_id is None:
            return embed("🏆 Server Leaderboards", "Use this section inside a Discord server.")
        entries = ranked(self.guild_id, self.category)
        e = embed(f"🏆 {CATEGORIES[self.category]}", "Accepted challenges only · Top 10")
        if not entries:
            e.add_field(name="No qualifying results yet", value="Complete accepted challenges to build your rankings.", inline=False)
        else:
            lines = []
            for i, row in enumerate(entries):
                if "owner_id" in row:
                    label = f"**{discord.utils.escape_markdown(row['name'])}** (<@{row['owner_id']}>)"
                else:
                    label = f"**{discord.utils.escape_markdown(row['name'])}** (<@{row['id']}>)"
                    title = equipped_title(self.guild_id, row["id"])
                    if title:
                        label += f" · *{title}*"
                lines.append(f"**{i + 1}.** {label} — {row['detail']}")
            e.add_field(name="Standings", value="\n".join(lines)[:1024], inline=False)
        return e


class TitleSelect(discord.ui.Select):
    def __init__(self, parent: "TitlePage"):
        self.screen = parent
        items = list(TITLE_RULES.items())
        visible = items[parent.page * parent.PER_PAGE:(parent.page + 1) * parent.PER_PAGE]
        options = [
            discord.SelectOption(label=label, value=key, default=key == parent.selected)
            for key, (label, _d, _f, _n) in visible
        ]
        super().__init__(placeholder="Choose title to equip (must be earned)", options=options, row=0)

    async def callback(self, interaction):
        self.screen.selected = self.values[0]
        await interaction.response.edit_message(embed=self.screen.make_embed(), view=self.screen)


class TitlePage(OwnedView):
    PER_PAGE = 6

    def __init__(self, user_id: int, guild_id: int | None, page: int = 0, selected: str | None = None):
        super().__init__(user_id)
        self.guild_id = guild_id
        self.page = max(0, min(page, (len(TITLE_RULES) - 1) // self.PER_PAGE))
        visible_keys = list(TITLE_RULES)[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]
        self.selected = selected if selected in visible_keys else visible_keys[0]
        self.add_item(TitleSelect(self))
        self.button("Equip Selected", self.equip, row=1, style=STYLE.primary)
        self.button("Unequip", self.unequip, row=1)
        self.button("◀ Previous", self.previous, row=2, disabled=page == 0)
        self.button("Next ▶", self.next, row=2, disabled=(page + 1) * self.PER_PAGE >= len(TITLE_RULES))
        self.home()

    def make_embed(self):
        if self.guild_id is None:
            return embed("🏅 Titles", "Titles are earned separately in each Discord server.")
        status = title_progress(self.guild_id, self.owner_id)
        equipped = equipped_title(self.guild_id, self.owner_id)
        entries = list(status.items())
        chunks = entries[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]
        lines = [f"{'✅' if val['earned'] else '🔒'} **{val['name']}** — {val['progress']}/{val['required']}\n"
                 f"    {val['description']}" for _, val in chunks]
        e = embed("🏅 Your Title Collection",
                  f"**Equipped:** {equipped or 'None'}\n**Earned:** {sum(p['earned'] for p in status.values())}/{len(status)}\n\n"
                  + "\n".join(lines))
        e.add_field(name="Browsing", value=f"Page {self.page + 1} of {(len(entries) + self.PER_PAGE - 1) // self.PER_PAGE}\n"
                    f"Selected: **{status[self.selected]['name']}**", inline=False)
        return e

    async def previous(self, interaction):
        await navigate(interaction, TitlePage(interaction.user.id, interaction.guild_id, self.page - 1))

    async def next(self, interaction):
        await navigate(interaction, TitlePage(interaction.user.id, interaction.guild_id, self.page + 1))

    async def equip(self, interaction):
        if self.guild_id is None:
            return await interaction.response.send_message("❌ Use this in a server.", ephemeral=True)
        try:
            set_title(self.guild_id, interaction.user.id, self.selected)
        except ValueError as exc:
            return await interaction.response.send_message(f"🔒 {exc}", ephemeral=True)
        await interaction.response.edit_message(content="✅ Title equipped.", embed=self.make_embed(), view=self)

    async def unequip(self, interaction):
        if self.guild_id is None:
            return await interaction.response.send_message("❌ Use this in a server.", ephemeral=True)
        set_title(self.guild_id, interaction.user.id, None)
        await interaction.response.edit_message(content="✅ Title unequipped.", embed=self.make_embed(), view=self)


class AdminPage(OwnedView):
    def __init__(self, user_id: int):
        super().__init__(user_id, admin=True)
        self.button("System Health", self.health, row=0, emoji="💚")
        self.button("Server Summary", self.summary, row=0, emoji="📊")
        self.button("Maintenance Tools", open_maintenance, row=1, style=STYLE.primary, emoji="🛠️")
        self.button("Instant Test Duel", lambda it: navigate(it, DuelPage(it.user.id, instant=True)), row=1)
        self.button("Tournament Director", open_tournaments, row=2, emoji="🏆")
        self.home()

    def make_embed(self):
        return embed("⚙️ Admin Control Room",
                     "**Restricted: Manage Server permission required.**\n"
                     "Validate, back up, repair or restore local data with confirmation. "
                     "Run unranked test matches and manage tournaments.")

    async def health(self, interaction):
        from cogs.maintenance import health_embed
        await interaction.response.edit_message(embed=health_embed(), view=self)

    async def summary(self, interaction):
        from services.competition import aggregate
        from services.records import load_history
        total = load_history().get("matches", [])
        guild = interaction.guild_id
        relevant = [m for m in total if m.get("guild_id") == guild]
        knights, horses = aggregate(guild)
        await interaction.response.edit_message(embed=embed(
            "⚙️ Server Summary",
            f"**Recorded matches:** {len(relevant)}\n**Competitive riders:** {len(knights)}\n"
            f"**Horses used:** {len(horses)}\n\n"
            "Instant test duels appear in records but are excluded from competitive totals."
        ), view=self)

    async def backup(self, interaction):
        await open_maintenance(interaction)



class MenuCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="menu", description="Open the interactive JoustingBot game hub.")
    async def menu(self, interaction: discord.Interaction):
        view = MainMenuView(interaction.user.id, is_admin(interaction))
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    @app_commands.command(name="help_joust", description="Open JoustingBot controls and help.")
    async def help_joust(self, interaction: discord.Interaction):
        view = MainMenuView(interaction.user.id, is_admin(interaction))
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    @app_commands.command(name="injuries", description="Inspect your injuries and purchase faster healing.")
    async def injuries(self, interaction: discord.Interaction):
        view = InjuryPage(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    @app_commands.command(name="heal", description="Spend gold on tiered non-instant recovery treatment.")
    @app_commands.choices(provider=[
        app_commands.Choice(name="Faith Healer (12 gold)", value="faith_healer"),
        app_commands.Choice(name="Shady Doctor (27 gold)", value="shady_doctor"),
        app_commands.Choice(name="Private Doctor (55 gold)", value="private_doctor"),
    ])
    async def heal(self, interaction: discord.Interaction, injury_id: str,
                   provider: str = "shady_doctor"):
        from services.injuries import heal
        try:
            balance, result = heal(
                interaction.guild_id, interaction.user.id, injury_id, provider=provider
            )
        except ValueError as exc:
            return await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        view = InjuryPage(interaction.user.id, interaction.guild_id, provider=provider)
        summary = (
            f"✅ {result['provider']} reduced {result['name']} recovery "
            f"by {result['hours_reduced']:.1f}h."
            if result["success"]
            else f"⚠️ {result['provider']} treatment failed."
        )
        if result["support_ready"]:
            summary += " Temporary next-bout pain relief is available!"
        await interaction.response.send_message(
            content=f"{summary} Gold remaining: **{balance}**.",
            embed=view.make_embed(), view=view, ephemeral=True
        )

    @app_commands.command(name="progress", description="Check your gold, prestige and equipment unlocks.")
    async def progress(self, interaction: discord.Interaction):
        view = ProgressionPage(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    @app_commands.command(name="armory", description="Browse, unlock and equip gear with buttons.")
    async def armory(self, interaction: discord.Interaction):
        view = EquipmentPage(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)

    @app_commands.command(name="standards", description="Browse and equip cosmetic standards.")
    async def standards(self, interaction: discord.Interaction):
        view = StandardPage(interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)



async def setup(bot: commands.Bot):
    await bot.add_cog(MenuCog(bot))
