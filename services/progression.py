"""v0.8 progression. All currency is earned from accepted guild challenges.

Gold/prestige derive from immutable completed-match records; only purchases, loadouts
and cosmetic standard selections are persisted. Starter equipment is always free.
"""
from __future__ import annotations

from datetime import datetime, timezone

from services.competition import aggregate, guild_matches
from services.equipment import ITEMS
from services.records import load_history
from services.storage import load_json, save_json

PATH = "storage/progression.json"
STARTER = {"lance": "lance_ash", "armour": "armour_mail", "barding": "barding_none"}
GOLD_PER_JOUST = 12
GOLD_WIN_BONUS = 8
GOLD_DRAW_BONUS = 4

# The first condition is required before the player can spend gold to obtain the item.
# Each item is deliberately a sidegrade; no item is simply superior in all conditions.
UNLOCKS = {
    "lance_oakbreaker": ("Oakbreaker Lance", "wins", 5, 110),
    "lance_windrunner": ("Windrunner Lance", "wind_wins", 3, 100),
    "armour_riveted": ("Riveted Mail", "jousts", 8, 105),
    "armour_duelist": ("Duelist's Harness", "unhorsings", 3, 110),
    "barding_runner": ("Runner's Barding", "no_barding_wins", 1, 95),
    "barding_marsh": ("Marsh Warden Barding", "frozen_survivals", 3, 95),
}

STANDARDS = {
    "none": ("No Standard", "jousts", 0),
    "royal": ("Royal Standard", "wins", 5),
    "frost": ("Frost Pennant", "frozen_survivals", 3),
    "mud": ("Mud Banner", "mud_wins", 3),
}

TIERS = ((100, "Legend of the Lists"), (60, "Grand Champion"),
         (30, "Knight Errant"), (10, "Lancer"), (0, "Squire"))


def _db() -> dict:
    data = load_json(PATH, {"guilds": {}})
    return data if isinstance(data, dict) and isinstance(data.get("guilds"), dict) else {"guilds": {}}


def _player(data: dict, guild_id: int, user_id: int) -> dict:
    return data.get("guilds", {}).get(str(guild_id), {}).get(str(user_id), {})


def _ensure_player(data: dict, guild_id: int, user_id: int) -> dict:
    return data.setdefault("guilds", {}).setdefault(str(guild_id), {}).setdefault(
        str(user_id), {"purchases": {}, "loadout": {}, "standard": "none"}
    )


def _matches(guild_id: int, user_id: int, history: dict) -> list[tuple[dict, str, str]]:
    result = []
    for match in guild_matches(guild_id, history):
        a, b = match["a"], match["b"]
        if a.get("user_id") == user_id:
            result.append((match, "a", "b"))
        elif b.get("user_id") == user_id:
            result.append((match, "b", "a"))
    return result


def earned_gold(guild_id: int, user_id: int, history: dict | None = None) -> int:
    matches = _matches(guild_id, user_id, history if history is not None else load_history())
    total = 0
    for m, own, other in matches:
        total += GOLD_PER_JOUST
        if m[own]["score"] > m[other]["score"]:
            total += GOLD_WIN_BONUS
        elif m[own]["score"] == m[other]["score"]:
            total += GOLD_DRAW_BONUS
    return total


def progress(guild_id: int, user_id: int, history: dict | None = None) -> dict[str, int]:
    data = history if history is not None else load_history()
    knights, _ = aggregate(guild_id, data)
    player = knights.get(user_id, {})
    values = {
        "wins": int(player.get("wins", 0)),
        "jousts": int(player.get("jousts", 0)),
        "unhorsings": int(player.get("unhorsings", 0)),
        "wind_wins": int(player.get("wind_wins", 0)),
        "mud_wins": int(player.get("mud_wins", 0)),
        "no_barding_wins": 0,
        "frozen_survivals": 0,
    }
    for m, own, other in _matches(guild_id, user_id, data):
        if (m[own]["score"] > m[other]["score"]
                and m[own].get("gear", {}).get("barding") == STARTER["barding"]):
            values["no_barding_wins"] += 1

        if m.get("arena_key") == "frozen_ground":
            unhorsed = any(
                p.get("category") == "unhorsing" and int(p.get("points_" + other, 0)) > 0
                for p in m.get("passes", [])
            )
            if not unhorsed:
                values["frozen_survivals"] += 1
    return values


def prestige(guild_id: int, user_id: int, history: dict | None = None) -> tuple[int, str]:
    values = progress(guild_id, user_id, history)
    points = values["jousts"] + 2 * values["wins"]
    return points, next(name for threshold, name in TIERS if points >= threshold)


def purchased(guild_id: int, user_id: int, data: dict | None = None) -> dict:
    return dict(_player(data if data is not None else _db(), guild_id, user_id).get("purchases", {}))


def wallet(guild_id: int, user_id: int, history: dict | None = None, data: dict | None = None) -> int:
    owned = purchased(guild_id, user_id, data)
    spent = sum(int(x.get("cost", 0)) for x in owned.values() if isinstance(x, dict))
    return max(0, earned_gold(guild_id, user_id, history) - spent)


def unlocked(guild_id: int | None, user_id: int, key: str, data: dict | None = None) -> bool:
    if key not in ITEMS:
        return False
    if key not in UNLOCKS:
        return True
    if guild_id is None:
        return False
    return key in purchased(guild_id, user_id, data)


def unlock_info(guild_id: int | None, user_id: int, key: str,
                history: dict | None = None, data: dict | None = None) -> dict:
    item = ITEMS.get(key)
    if item is None:
        raise ValueError("Unknown equipment item.")
    if key not in UNLOCKS:
        return {"owned": True, "eligible": True, "cost": 0, "progress": 0,
                "required": 0, "requirement": "Starter equipment"}
    label, field, requirement, cost = UNLOCKS[key]
    owned = unlocked(guild_id, user_id, key, data)
    current = progress(guild_id, user_id, history)[field] if guild_id is not None else 0
    return {"owned": owned, "eligible": current >= requirement, "cost": cost,
            "progress": current, "required": requirement, "requirement": field.replace("_", " ")}


def buy(guild_id: int | None, user_id: int, key: str) -> int:
    """Spend a recorded gold amount, never allowing duplicate purchases."""
    if guild_id is None:
        raise ValueError("Unlocks require a Discord server.")
    if key not in UNLOCKS:
        raise ValueError("This item is already available to everyone.")
    history = load_history()
    data = _db()
    if unlocked(guild_id, user_id, key, data):
        raise ValueError("You already own this item.")
    state = unlock_info(guild_id, user_id, key, history, data)
    if not state["eligible"]:
        raise ValueError(
            f"Requirement not met: {state['requirement']} {state['progress']}/{state['required']}."
        )
    if wallet(guild_id, user_id, history, data) < state["cost"]:
        raise ValueError(f"You need {state['cost']} gold to unlock this item.")
    owned = _ensure_player(data, guild_id, user_id).setdefault("purchases", {})
    owned[key] = {"cost": state["cost"], "at": datetime.now(timezone.utc).isoformat()}
    save_json(PATH, data)
    return wallet(guild_id, user_id, history, data)


def set_loadout(guild_id: int | None, user_id: int, slot: str, key: str, horse_id: str | None = None) -> None:
    item = ITEMS.get(key)
    if item is None or item.slot != slot:
        raise ValueError("This equipment does not belong in that slot.")
    if guild_id is None:
        raise ValueError("Equip items within your Discord server.")
    data = _db()
    if not unlocked(guild_id, user_id, key, data):
        raise ValueError("That gear is locked. Unlock it in the Armory first.")
    player = _ensure_player(data, guild_id, user_id)
    if slot == "barding":
        if not horse_id:
            raise ValueError("Select your bound horse before equipping barding.")
        player.setdefault("horse_barding", {})[horse_id] = key
    else:
        player.setdefault("loadout", {})[slot] = key
    save_json(PATH, data)


def loadout(guild_id: int | None, user_id: int, slot: str, old_key: str | None = None, horse_id: str | None = None) -> str:
    data = _db()
    if guild_id is not None:
        player = _player(data, guild_id, user_id)
        selected = player.get("loadout", {}).get(slot)
        if slot == "barding" and horse_id:
            selected = player.get("horse_barding", {}).get(horse_id, selected)
        if selected and unlocked(guild_id, user_id, selected, data):
            return selected
    if old_key and old_key in ITEMS and ITEMS[old_key].slot == slot and unlocked(guild_id, user_id, old_key, data):
        return old_key
    return STARTER[slot]


def standard_info(guild_id: int | None, user_id: int, key: str,
                  history: dict | None = None) -> dict:
    if key not in STANDARDS:
        raise ValueError("Unknown standard.")
    name, field, required = STANDARDS[key]
    values = progress(guild_id, user_id, history) if guild_id is not None else {}
    amount = values.get(field, 0)
    return {"name": name, "required": required, "progress": amount,
            "earned": amount >= required and guild_id is not None}


def set_standard(guild_id: int | None, user_id: int, key: str) -> None:
    if guild_id is None:
        raise ValueError("Standards can only be equipped in a Discord server.")
    if not standard_info(guild_id, user_id, key)["earned"]:
        raise ValueError("You have not earned this standard.")
    data = _db()
    _ensure_player(data, guild_id, user_id)["standard"] = key
    save_json(PATH, data)


def equipped_standard(guild_id: int | None, user_id: int) -> str:
    if guild_id is None:
        return ""
    key = _player(_db(), guild_id, user_id).get("standard", "none")
    if key not in STANDARDS or not standard_info(guild_id, user_id, key)["earned"]:
        return ""
    return STANDARDS[key][0] if key != "none" else ""
