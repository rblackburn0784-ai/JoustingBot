"""Deterministic knight injuries (v0.8.1), natural recovery, paid treatment."""
from __future__ import annotations
import hashlib
from datetime import datetime, timedelta, timezone
from services.records import load_history

KINDS = {
    "bruised_ribs": ("Bruised Ribs", "endurance", 24),
    "wrenched_shoulder": ("Wrenched Shoulder", "strength", 36),
    "jarred_wrist": ("Jarred Wrist", "control", 48),
}
RISKS = {"unhorsing": 28, "saddle_stagger": 12, "heavy_shield_hit": 6}
PENALTY_CAP = 2
HEAL_HOURS = 24
HEAL_COST = 30

def utc(value):
    date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)

def roll(mid, side, salt):
    return int.from_bytes(hashlib.sha256(f"{mid}:{side}:{salt}".encode()).digest()[:8], "big") % 100

def make_events(match: dict) -> list[dict]:
    """One roll per rider, based on their worst scoring hit taken in the match."""
    if match.get("mode") != "challenge" or match.get("guild_id") is None:
        return []
    try:
        start = utc(match["timestamp"])
    except (ValueError, TypeError, KeyError):
        return []
    events = []
    for side, other in (("a", "b"), ("b", "a")):
        strongest = None
        for item in match.get("passes", []):
            category = item.get("category")
            if category not in RISKS:
                continue
            try:
                struck = int(item.get("points_" + other, 0)) > 0
            except (TypeError, ValueError):
                continue
            if struck and (strongest is None or RISKS[category] > RISKS[strongest]):
                strongest = category
        if not strongest or roll(match["id"], side, "risk") >= RISKS[strongest]:
            continue
        key = list(KINDS)[roll(match["id"], side, "kind") % len(KINDS)]
        name, stat, hours = KINDS[key]
        events.append({
            "id": f"{match['id']}:{side}", "user_id": match[side]["user_id"],
            "key": key, "name": name, "stat": stat, "source": strongest,
            "started_at": start.isoformat(),
            "expires_at": (start + timedelta(hours=hours)).isoformat(),
        })
    return events

def healing_spent(guild_id: int, user_id: int, data: dict | None = None) -> int:
    if data is None:
        from services.progression import _db
        data = _db()
    player = data.get("guilds", {}).get(str(guild_id), {}).get(str(user_id), {})
    return sum(int(entry.get("gold", 0)) for entry in player.get("healing", {}).values()
               if isinstance(entry, dict))

def injuries(guild_id: int | None, user_id: int, history=None, data=None, now=None) -> list[dict]:
    """Only match snapshots made since v0.8.1 can cause injuries."""
    if guild_id is None:
        return []
    if history is None:
        history = load_history()
    if data is None:
        from services.progression import _db
        data = _db()
    now = now or datetime.now(timezone.utc)
    paid = data.get("guilds", {}).get(str(guild_id), {}).get(str(user_id), {}).get("healing", {})
    result, seen = [], set()
    for match in history.get("matches", []):
        if match.get("guild_id") != guild_id or match.get("mode") != "challenge":
            continue
        for event in match.get("injuries", []):
            try:
                if event["user_id"] != user_id or event["id"] in seen:
                    continue
                seen.add(event["id"])
                hours = max(0, int(paid.get(event["id"], {}).get("hours", 0)))
                expiration = utc(event["expires_at"]) - timedelta(hours=hours)
                remaining = max(0, (expiration - now).total_seconds())
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            result.append({**event, "remaining_seconds": remaining,
                           "recovered_at": expiration.isoformat(), "active": remaining > 0})
    return sorted(result, key=lambda e: (e["remaining_seconds"], e["id"]), reverse=True)

def active(guild_id: int | None, user_id: int, history=None, data=None, now=None) -> list[dict]:
    return [e for e in injuries(guild_id, user_id, history, data, now) if e["active"]]

def apply_penalty(stats: dict[str, int], guild_id: int | None, user_id: int,
                  history=None, data=None, now=None) -> dict[str, int]:
    final, affected = dict(stats), set()
    for injury in active(guild_id, user_id, history, data, now):
        stat = injury["stat"]
        if len(affected) >= PENALTY_CAP:
            break
        if stat not in final or stat in affected:
            continue
        final[stat] = max(1, int(final[stat]) - 1)
        affected.add(stat)
    return final

def heal(guild_id: int | None, user_id: int, injury_id: str, now=None) -> tuple[int, dict]:
    """One treatment pays 30 gold and advances recovery by 24 real hours."""
    if guild_id is None:
        raise ValueError("Heal your injuries in a Discord server.")
    from services.progression import _db, _ensure_player, PATH, wallet
    from services.storage import save_json
    data, history = _db(), load_history()
    now = now or datetime.now(timezone.utc)
    injury = next((x for x in active(guild_id, user_id, history, data, now)
                   if x["id"] == injury_id), None)
    if injury is None:
        raise ValueError("That injury is already healed or doesn't belong to you.")
    if wallet(guild_id, user_id, history, data) < HEAL_COST:
        raise ValueError(f"Healing requires {HEAL_COST} gold.")
    payments = _ensure_player(data, guild_id, user_id).setdefault("healing", {})
    entry = payments.setdefault(injury_id, {"hours": 0, "gold": 0})
    entry["hours"] += HEAL_HOURS
    entry["gold"] += HEAL_COST
    entry["last_treated_at"] = now.isoformat()
    save_json(PATH, data)
    return wallet(guild_id, user_id, history, data), injury

def duration(seconds: float) -> str:
    if seconds <= 0:
        return "Recovered"
    whole_hours = int((seconds + 3599) // 3600)
    if whole_hours >= 24:
        d, h = divmod(whole_hours, 24)
        return f"{d}d {h}h" if h else f"{d}d"
    return f"{whole_hours}h"
