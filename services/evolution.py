"""v2.9.5 — non-pay-to-win daily goals, horse care and loadout presets.

All persistence uses the existing guild-scoped progression.json. Renown is
cosmetic, never converted to spendable gold. No additional gameplay journal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.arenas import ARENAS
from services.records import load_history
from services.progression import (
    STARTER, _db, _ensure_player, _player, loadout, unlocked, PATH,
)
from services.storage import save_json
from services.tactics import MOVES, STYLES, TARGETS, TacticPlan

HORSE_GEAR_SLOTS = ("barding", "saddle", "bridle", "shoes")
GEAR_SLOTS = ("lance", "armour", "helm", "shield", *HORSE_GEAR_SLOTS)
PRESETS = {"balanced": "Balanced", "defence": "Defensive", "speed": "Speed"}
GOAL_RENOWN = {"training": 3, "challenge": 5, "arena": 8}
DAILY_QUEST_TYPES = ("training", "challenge", "arena")


def utc_day(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError("Time must be timezone-aware.")
    return stamp.astimezone(timezone.utc).date().isoformat()


def _state(guild_id: int, user_id: int, data: dict | None = None) -> dict:
    if not guild_id or guild_id <= 0 or user_id <= 0:
        raise ValueError("Use this feature in a Discord server.")
    return _player(data if data is not None else _db(), guild_id, user_id)


def owned_horse(user_id: int, horse_id: str) -> dict:
    from cogs.horse import load_horses
    record = load_horses().get("horses", {}).get(horse_id)
    if not isinstance(record, dict) or int(record.get("owner_id", 0)) != user_id:
        raise ValueError("Choose a horse that belongs to you.")
    return record


def bound_horse(user_id: int) -> dict:
    from cogs.knight import load_knights
    knight = load_knights().get("knights", {}).get(str(user_id))
    if not isinstance(knight, dict) or not knight.get("bound_horse_id"):
        raise ValueError("Create a knight and bind one of your horses first.")
    return owned_horse(user_id, knight["bound_horse_id"])


def bond(guild_id: int, user_id: int, horse_id: str, *,
         history: dict | None = None, data: dict | None = None,
         now: datetime | None = None,
         verified_owner: bool = False) -> dict:
    if not verified_owner:
        owned_horse(user_id, horse_id)  # fail closed on abandoned/foreign mounts
    profile = _state(guild_id, user_id, data)
    grooming = (profile.get("horse_care", {}) or {}).get(horse_id, {}) or {}
    care = min(100, max(0, int(grooming.get("care_points", 0))))
    matches, seen = 0, set()
    journal = history if history is not None else load_history()
    for match in journal.get("matches", []):
        if not isinstance(match, dict) or match.get("guild_id") != guild_id \
                or match.get("mode") not in ("training", "challenge"):
            continue
        mid = str(match.get("id") or "")
        if not mid or mid in seen:
            continue
        for side in ("a", "b"):
            participant = match.get(side) or {}
            if (isinstance(participant, dict)
                    and participant.get("user_id") == user_id
                    and participant.get("horse_id") == horse_id):
                seen.add(mid)
                matches += 1
                break
    score = min(100, care + matches * 2)
    rank = ("Legendary Companion" if score >= 80 else "Trusted Partner"
            if score >= 40 else "Familiar" if score >= 15 else "New Bond")
    return {
        "score": score, "rank": rank, "matches": matches, "care_points": care,
        "obedience_bonus": 1 if score >= 40 else 0,
        "can_groom": grooming.get("last_day") != utc_day(now),
    }


def groom(guild_id: int, user_id: int, horse_id: str,
          *, now: datetime | None = None) -> dict:
    _state(guild_id, user_id)
    owned_horse(user_id, horse_id)
    day = utc_day(now)
    data = _db()
    state = _ensure_player(data, guild_id, user_id)
    entry = state.setdefault("horse_care", {}).setdefault(
        horse_id, {"care_points": 0, "last_day": None})
    if entry.get("last_day") == day:
        raise ValueError("You have already groomed this horse today (UTC).")
    entry["care_points"] = min(100, max(0, int(entry.get("care_points", 0))) + 3)
    entry["last_day"] = day
    save_json(PATH, data)
    return bond(guild_id, user_id, horse_id, data=data, now=now)


def _today_matches(guild_id: int, user_id: int, day: str, history: dict) -> list[dict]:
    selected, seen = [], set()
    for match in history.get("matches", []):
        if not isinstance(match, dict) or match.get("guild_id") != guild_id:
            continue
        if match.get("mode") not in ("training", "challenge"):
            continue
        mid = str(match.get("id") or "")
        if not mid or mid in seen:
            continue
        try:
            instant = datetime.fromisoformat(str(match["timestamp"]).replace("Z", "+00:00"))
            if utc_day(instant) != day:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        if any(isinstance(match.get(side), dict)
               and match[side].get("user_id") == user_id for side in ("a", "b")):
            seen.add(mid)
            selected.append(match)
    return selected


def daily_goals(guild_id: int, user_id: int, *, now: datetime | None = None,
                history: dict | None = None, data: dict | None = None) -> dict:
    day = utc_day(now)
    journal = history if history is not None else load_history()
    profile = _state(guild_id, user_id, data)
    matches = _today_matches(guild_id, user_id, day, journal)
    arena = list(ARENAS)[(datetime.fromisoformat(day).date().toordinal() + guild_id) % len(ARENAS)]
    trained = sum(m.get("mode") == "training" for m in matches)
    challenges = sum(m.get("mode") == "challenge" for m in matches)
    featured = sum(m.get("arena_key") == arena for m in matches)
    claims = profile.get("daily_claims", {})
    claimed = set(claims.get(day, [])) if isinstance(claims, dict) else set()
    goals = {
        "training": ("Complete one Training Yard joust", trained, 1),
        "challenge": ("Complete one accepted player challenge", challenges, 1),
        "arena": (f"Joust on {ARENAS[arena].name}", featured, 1),
    }
    return {
        "date": day, "arena_key": arena,
        "renown": max(0, int(profile.get("renown", 0))),
        "goals": {
            key: {"name": label, "progress": min(value, target),
                  "required": target, "earned": value >= target,
                  "claimed": key in claimed, "renown": GOAL_RENOWN[key]}
            for key, (label, value, target) in goals.items()
        },
    }


def claim_goal(guild_id: int, user_id: int, key: str,
               *, now: datetime | None = None) -> dict:
    if key not in DAILY_QUEST_TYPES:
        raise ValueError("Unknown daily objective.")
    data = _db()
    progress = daily_goals(guild_id, user_id, now=now, data=data)
    goal = progress["goals"][key]
    if goal["claimed"]:
        raise ValueError("You already collected this objective today.")
    if not goal["earned"]:
        raise ValueError("Complete the objective before claiming its renown.")
    state = _ensure_player(data, guild_id, user_id)
    claims = state.setdefault("daily_claims", {})
    claims.setdefault(progress["date"], []).append(key)
    # Keep a compact claim journal; historic cosmetic renown is retained.
    for old in list(claims):
        if old < progress["date"] and len(claims) > 20:
            claims.pop(old, None)
    state["renown"] = max(0, int(state.get("renown", 0))) + GOAL_RENOWN[key]
    save_json(PATH, data)
    return daily_goals(guild_id, user_id, now=now, data=data)


def preferred_tactics(guild_id: int, user_id: int,
                      *, data: dict | None = None) -> TacticPlan:
    raw = _state(guild_id, user_id, data).get("preferred_tactics", {})
    if not isinstance(raw, dict):
        return TacticPlan()
    try:
        return TacticPlan(**{field: raw.get(field, default)
                             for field, default in TacticPlan().as_dict().items()})
    except ValueError:
        return TacticPlan()


def set_preferred_tactics(guild_id: int, user_id: int, *,
                          style: str, target: str, manoeuvre: str) -> TacticPlan:
    _state(guild_id, user_id)
    plan = TacticPlan(style=style, target=target, manoeuvre=manoeuvre)
    data = _db()
    _ensure_player(data, guild_id, user_id)["preferred_tactics"] = plan.as_dict()
    save_json(PATH, data)
    return plan


def preset_names(guild_id: int, user_id: int) -> dict:
    existing = _state(guild_id, user_id).get("presets", {})
    return {key: existing.get(key) for key in PRESETS} if isinstance(existing, dict) else {}


def save_preset(guild_id: int, user_id: int, name: str) -> dict:
    _state(guild_id, user_id)
    if name not in PRESETS:
        raise ValueError("Select Balanced, Defence or Speed.")
    horse = bound_horse(user_id)
    hid = horse["horse_id"]
    from cogs.knight import load_knights
    knight = load_knights()["knights"][str(user_id)]
    data = _db()
    defaults = {
        "lance": knight.get("equipped_lance_key", STARTER["lance"]),
        "armour": knight.get("equipped_armour_key", STARTER["armour"]),
        "barding": horse.get("equipped_barding_key", STARTER["barding"]),
    }
    gear = {
        slot: loadout(
            guild_id, user_id, slot, defaults.get(slot, STARTER[slot]),
            horse_id=hid if slot in HORSE_GEAR_SLOTS else None
        )
        for slot in GEAR_SLOTS
    }
    record = {"horse_id": hid, "gear": gear,
              "tactics": preferred_tactics(guild_id, user_id, data=data).as_dict()}
    _ensure_player(data, guild_id, user_id).setdefault("presets", {})[name] = record
    save_json(PATH, data)
    return record


def apply_preset(guild_id: int, user_id: int, name: str) -> dict:
    _state(guild_id, user_id)
    if name not in PRESETS:
        raise ValueError("Unknown equipment preset.")
    horse = bound_horse(user_id)
    data = _db()
    player = _state(guild_id, user_id, data)
    entry = player.get("presets", {}).get(name)
    if not isinstance(entry, dict):
        raise ValueError("Save that preset before equipping it.")
    if entry.get("horse_id") != horse["horse_id"]:
        raise ValueError("That preset belongs to a different horse. Bind its mount or resave it.")
    gear = entry.get("gear", {})
    from services.equipment import ITEMS
    if not isinstance(gear, dict) or set(gear) != set(GEAR_SLOTS):
        raise ValueError("Preset is incomplete; save it again.")
    for slot, key in gear.items():
        item = ITEMS.get(key)
        if not item or item.slot != slot or not unlocked(guild_id, user_id, key, data):
            raise ValueError(f"Preset contains unavailable {slot}; nothing equipped.")
    try:
        plan = TacticPlan(**entry["tactics"])
    except (TypeError, KeyError, ValueError):
        raise ValueError("Preset tactics are invalid; nothing equipped.") from None
    target = _ensure_player(data, guild_id, user_id)
    for slot, key in gear.items():
        if slot in HORSE_GEAR_SLOTS:
            target.setdefault("horse_gear", {}).setdefault(horse["horse_id"], {})[slot] = key
            if slot == "barding":
                target.setdefault("horse_barding", {})[horse["horse_id"]] = key
        else:
            target.setdefault("loadout", {})[slot] = key
    target["preferred_tactics"] = plan.as_dict()
    save_json(PATH, data)
    return entry


def delete_preset(guild_id: int, user_id: int, name: str) -> None:
    _state(guild_id, user_id)
    if name not in PRESETS:
        raise ValueError("Unknown equipment preset.")
    data = _db()
    profile = _ensure_player(data, guild_id, user_id)
    if name not in profile.get("presets", {}):
        raise ValueError("No saved preset in that slot.")
    del profile["presets"][name]
    save_json(PATH, data)


# Knight statistics are global across guilds, so the respec cooldown is stored
# in knights.json rather than a guild's progression.json. Deleting a knight
# cannot erase this historical cooldown record.
RESPEC_COOLDOWN_DAYS = 14


def respec_remaining(user_id: int, *, now: datetime | None = None) -> int:
    """Whole seconds before another respec; malformed cooldown fails closed."""
    from cogs.knight import load_knights
    from datetime import timedelta
    if user_id <= 0:
        raise ValueError("Invalid knight owner.")
    data = load_knights()
    stamped = data.get("respec_history", {}).get(str(user_id))
    if not stamped:
        return 0
    try:
        at = datetime.fromisoformat(str(stamped).replace("Z", "+00:00"))
        if at.tzinfo is None:
            raise ValueError("Naive timestamp")
        point = now or datetime.now(timezone.utc)
        if point.tzinfo is None:
            raise ValueError("Naive current time")
        remaining = ((at.astimezone(timezone.utc) +
                      timedelta(days=RESPEC_COOLDOWN_DAYS)) -
                     point.astimezone(timezone.utc)).total_seconds()
        return max(0, int(remaining + 0.999))
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Respec cooldown data is invalid; ask an admin to review it.") from None


def respec_knight(user_id: int, stats: dict[str, int], *,
                  now: datetime | None = None, active_match: bool = False) -> dict:
    """Respend exactly 20 existing points, never changing equipment or history.

    The caller checks live challenge locks. Tournament registrations are checked
    independently here, including other guilds the owner participates in.
    """
    from cogs.knight import load_knights, save_knights, validate_stats
    from services.tournaments import load_db
    if user_id <= 0:
        raise ValueError("Invalid knight owner.")
    if active_match:
        raise ValueError("Finish or decline your active challenge before changing stats.")
    tournament_data = load_db()
    for guild in tournament_data.get("guilds", {}).values():
        if not isinstance(guild, dict):
            continue
        tournament = guild.get("active") or {}
        if (isinstance(tournament, dict)
                and tournament.get("status") in ("registration", "running")
                and user_id in tournament.get("entrants", [])):
            raise ValueError("Leave or complete your registered tournament before changing stats.")
    if not isinstance(stats, dict):
        raise ValueError("Invalid stat allocation.")
    # Ensure boolean values cannot masquerade as valid integers.
    if any(type(x) is not int for x in stats.values()):
        raise ValueError("Stats must be whole numbers.")
    validate_stats(stats)
    knight_data = load_knights()
    existing = knight_data.get("knights", {}).get(str(user_id))
    if not isinstance(existing, dict) or int(existing.get("user_id", -1)) != user_id:
        raise ValueError("Create your own knight before reallocating stats.")
    if dict(existing.get("stats", {})) == stats:
        raise ValueError("No changes to the current stat allocation.")
    cooldown = respec_remaining(user_id, now=now)
    if cooldown:
        remaining_days = (cooldown + 86_399) // 86_400
        raise ValueError(f"Respec cooldown: {remaining_days} day(s) remain.")
    point = now or datetime.now(timezone.utc)
    if point.tzinfo is None:
        raise ValueError("Time must include a timezone.")
    existing["stats"] = dict(stats)
    existing["updated_at"] = point.astimezone(timezone.utc).isoformat()
    knight_data.setdefault("respec_history", {})[str(user_id)] = existing["updated_at"]
    # One atomic file update. Bound horse, gear, name and career remain intact.
    save_knights(knight_data)
    return dict(existing)
