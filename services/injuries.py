"""v0.8.1a: deterministic injury risk, contextual wounds and tiered treatment.

All outcomes are recorded once. Historical 0.8.1 wound snapshots remain valid.
Roll outcomes are game balance values, not real-world medical probabilities.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from services.records import load_history

# Tuple shape stays backward compatible with v0.8.1 (name, penalised stat, base hours).
KINDS = {
    "bruised_ribs": ("Bruised Ribs", "endurance", 24),
    "wrenched_shoulder": ("Wrenched Shoulder", "strength", 36),
    "jarred_wrist": ("Jarred Wrist", "control", 48),
    "twisted_knee": ("Twisted Knee", "agility", 32),
    "strained_back": ("Strained Back", "endurance", 40),
}
RISKS = {"unhorsing": 28, "saddle_stagger": 12, "heavy_shield_hit": 6, "horse_slip": 10}
PENALTY_CAP = 2
HEAL_HOURS = 24   # Legacy names retained for callers; tiered treatment supersedes these.
HEAL_COST = 30
MIN_RECOVERY_HOURS = 3
SUPPORT_WINDOW_HOURS = 24
TREATMENTS = {
    "faith_healer": {
        "name": "Faith Healer", "cost": 12, "hours": 8, "failure": 16, "support": 12,
        "description": "Cheap and uncertain. Modest help with recovery.",
    },
    "shady_doctor": {
        "name": "Shady Doctor", "cost": 27, "hours": 18, "failure": 9, "support": 18,
        "description": "A practical but unreliable physician with quick hands.",
    },
    "private_doctor": {
        "name": "Private Doctor", "cost": 55, "hours": 30, "failure": 3, "support": 24,
        "description": "Expensive, reliable care with the best recovery reduction.",
    },
}
ARENA_RISK = {
    "royal_lists": -3, "muddy_field": 5, "frozen_ground": 7,
    "wind_swept": 2, "festival_arena": -1, "war_torn": 6,
}
# These alter the *location* of the injury, not merely its frequency.
ARENA_KIND_WEIGHTS = {
    "royal_lists": {"bruised_ribs": 3, "jarred_wrist": 2},
    "muddy_field": {"twisted_knee": 6, "strained_back": 3},
    "frozen_ground": {"twisted_knee": 5, "jarred_wrist": 4},
    "wind_swept": {"jarred_wrist": 5, "wrenched_shoulder": 3},
    "festival_arena": {"bruised_ribs": 5, "strained_back": 3},
    "war_torn": {"wrenched_shoulder": 5, "bruised_ribs": 4},
}
ARMOUR_RISK = {
    "armour_mail": -1, "armour_light": 3, "armour_full": -5,
    "armour_reinforced_helm": -4, "armour_riveted": -2, "armour_duelist": 5,
}
BARDING_RISK = {
    "barding_none": 1, "barding_leather": -1, "barding_steel": -2,
    "barding_spiked": 2, "barding_runner": 3, "barding_marsh": -2,
}
LANCE_RISK = {
    "lance_heavy": 4, "lance_oakbreaker": 3,
    "lance_tournament": -2, "lance_windrunner": -1,
}
BREED_RISK = {
    "destrier": -2, "courser": 1, "charger": 2,
    "palfrey": -2, "cob": -1, "warhorse": -1,
}
MIN_RISK, MAX_RISK = 2, 42
# Severity influences *duration*, not the total combat penalty.
SEVERITIES = {"light": 0.80, "moderate": 1.0, "serious": 1.35}


def utc(value):
    date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)


def roll(mid, side, salt):
    return int.from_bytes(hashlib.sha256(f"{mid}:{side}:{salt}".encode()).digest()[:8], "big") % 100


def _breed_modifier(breed: str) -> int:
    text = str(breed or "").lower().replace("-", " ")
    return next((mod for label, mod in BREED_RISK.items() if label in text), 0)


def risk_profile(match: dict, side: str, other: str, category: str, event: dict | None = None) -> dict:
    """Percentage points attributable to arena, armour, lance, horse gear and breed."""
    defender = match.get(side, {})
    attacker = match.get(other, {})
    own_gear = defender.get("gear") or {}
    foe_gear = attacker.get("gear") or {}
    area = str(match.get("arena_key", "royal_lists"))
    horse_stats = defender.get("horse_stats") or {}
    courage = int(horse_stats.get("courage", 5))
    obedience = int(horse_stats.get("obedience", 5))
    horse_handling = (-1 if courage >= 8 else (1 if courage <= 3 else 0))
    horse_handling += (-1 if obedience >= 8 else (1 if obedience <= 3 else 0))
    mods = {
        "arena": ARENA_RISK.get(area, 0),
        "armour": ARMOUR_RISK.get(own_gear.get("armour"), 0),
        "barding": BARDING_RISK.get(own_gear.get("barding"), 0),
        "attacker_lance": LANCE_RISK.get(foe_gear.get("lance"), 0),
        "horse_breed": _breed_modifier(defender.get("horse_breed", "")),
        "horse_handling": horse_handling,
    }
    # Riding while hurt adds a little danger without multiplying injury penalties.
    if defender.get("already_injured"):
        mods["riding_hurt"] = 3
    if category == "horse_slip":
        # Slippery ground primarily causes lower-body rather than shield injuries.
        mods["terrain_slip"] = max(0, ARENA_RISK.get(area, 0)) // 2
    # Tactical intent affects the *rider accepting the risk*, rather than
    # allowing one player to injure the other simply by picking Aggressive.
    # Rider-targeted hits do add a modest extra risk to the defender.
    if event:
        own_tactics = event.get("tactics_" + side, {})
        attack_tactics = event.get("tactics_" + other, {})
        styles = {"cautious": -4, "balanced": 0, "aggressive": 5}
        mods["riding_style"] = styles.get(own_tactics.get("style"), 0)
        mods["fatigue"] = min(3, max(0, int(own_tactics.get("fatigue", 0)) // 3))
        mods["reckless_self"] = 4 if own_tactics.get("move") == "reckless_charge" else 0
        mods["rider_target"] = 3 if attack_tactics.get("target") == "rider" else 0
        mods["reckless_move"] = 3 if attack_tactics.get("move") == "reckless_charge" else 0
    base = RISKS[category]
    chance = max(MIN_RISK, min(MAX_RISK, base + sum(mods.values())))
    return {"category": category, "base": base, "modifiers": mods, "chance": chance}


def _choose_kind(match_id: str, side: str, arena: str, category: str = "",
                 defender: dict | None = None, attacker: dict | None = None) -> str:
    weights = {key: 2 for key in KINDS}
    for key, bonus in ARENA_KIND_WEIGHTS.get(arena, {}).items():
        weights[key] += bonus
    if category == "horse_slip":
        weights["twisted_knee"] += 7
        weights["strained_back"] += 3
    defender = defender or {}
    attacker = attacker or {}
    armour = (defender.get("gear") or {}).get("armour")
    barding = (defender.get("gear") or {}).get("barding")
    lance = (attacker.get("gear") or {}).get("lance")
    breed = str(defender.get("horse_breed", "")).lower()
    if armour in {"armour_light", "armour_duelist"}:
        weights["bruised_ribs"] += 3
    if armour == "armour_full":
        weights["strained_back"] += 2
    if barding == "barding_steel":
        weights["strained_back"] += 2
    if lance in {"lance_heavy", "lance_oakbreaker"}:
        weights["bruised_ribs"] += 2
    if "courser" in breed or "charger" in breed:
        weights["twisted_knee"] += 2
    total = sum(weights.values())
    target = roll(match_id, side, "kind") * total // 100
    for kind, weight in weights.items():
        if target < weight:
            return kind
        target -= weight
    return next(iter(KINDS))


def make_events(match: dict) -> list[dict]:
    """At most one injury per rider, deterministic from one saved match ID.

    The highest-risk impact *received* in a match is used; a refusal/miss cannot
    hurt the opponent. Results are saved to the match journal rather than rerolled.
    """
    if match.get("mode") not in ("challenge", "training") or match.get("guild_id") is None:
        return []
    try:
        started = utc(match["timestamp"])
        mid = str(match["id"])
    except (ValueError, KeyError, TypeError):
        return []
    events = []
    # NPC opponents never receive persisted injuries. Training exposes the
    # human rider to the same deterministic risk from genuine impacts.
    participants = (("a", "b"),) if match.get("mode") == "training" else (
        ("a", "b"), ("b", "a"))
    for side, other in participants:
        strongest = None
        for event in match.get("passes", []):
            category = event.get("category")
            if category not in RISKS:
                continue
            try:
                struck = int(event.get("points_" + other, 0)) > 0
            except (ValueError, TypeError):
                continue
            if not struck:
                continue
            profile = risk_profile(match, side, other, category, event=event)
            if strongest is None or profile["chance"] > strongest["chance"]:
                strongest = profile
        if not strongest or roll(mid, side, "risk") >= strongest["chance"]:
            continue
        kind = _choose_kind(mid, side, match.get("arena_key", "royal_lists"), strongest["category"],
                            defender=match.get(side), attacker=match.get(other))
        name, stat, hours = KINDS[kind]
        severity_roll = roll(mid, side, "severity")
        severity = "light" if severity_roll < 50 else ("moderate" if severity_roll < 90 else "serious")
        real_hours = max(12, round(hours * SEVERITIES[severity]))
        events.append({
            "id": f"{mid}:{side}", "user_id": match[side]["user_id"],
            "key": kind, "name": name, "stat": stat, "source": strongest["category"],
            "severity": severity, "base_risk": strongest["base"],
            "risk": strongest["chance"], "risk_modifiers": strongest["modifiers"],
            "started_at": started.isoformat(),
            "expires_at": (started + timedelta(hours=real_hours)).isoformat(),
        })
    return events


def healing_spent(guild_id: int, user_id: int, data: dict | None = None) -> int:
    if data is None:
        from services.progression import _db
        data = _db()
    player = data.get("guilds", {}).get(str(guild_id), {}).get(str(user_id), {})
    return sum(int(record.get("gold", 0)) for record in player.get("healing", {}).values()
               if isinstance(record, dict))


def injuries(guild_id: int | None, user_id: int, history=None, data=None, now=None) -> list[dict]:
    """Read injury snapshots from v0.8.1 onward; preserve legacy healing records."""
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
        if match.get("guild_id") != guild_id or match.get("mode") not in ("challenge", "training"):
            continue
        for event in match.get("injuries", []):
            try:
                if event["user_id"] != user_id or event["id"] in seen:
                    continue
                seen.add(event["id"])
                hours = max(0.0, float(paid.get(event["id"], {}).get("hours", 0)))
                expiry = utc(event["expires_at"]) - timedelta(hours=hours)
                remaining = max(0, (expiry - now).total_seconds())
            except (KeyError, ValueError, TypeError, OverflowError):
                continue
            result.append({**event, "remaining_seconds": remaining,
                           "recovered_at": expiry.isoformat(), "active": remaining > 0})
    return sorted(result, key=lambda e: (e["remaining_seconds"], e["id"]), reverse=True)


def active(guild_id: int | None, user_id: int, history=None, data=None, now=None) -> list[dict]:
    return [record for record in injuries(guild_id, user_id, history, data, now) if record["active"]]


def support_for_next_bout(guild_id: int | None, user_id: int, history=None, data=None, now=None) -> dict | None:
    """One use only, during the next eligible accepted bout within 24 hours.

    Any completed accepted joust after treatment consumes the opportunity.
    Declines, timeouts and admin instant test duels do not consume it.
    """
    if guild_id is None:
        return None
    if history is None:
        history = load_history()
    if data is None:
        from services.progression import _db
        data = _db()
    now = now or datetime.now(timezone.utc)
    if not active(guild_id, user_id, history, data, now):
        return None
    player = data.get("guilds", {}).get(str(guild_id), {}).get(str(user_id), {})
    # Any completed competitive match after treatment consumes that support opportunity.
    # Several treatments before the same match do not create several future boosts.
    completed = []
    used = set()
    for match in history.get("matches", []):
        if not isinstance(match, dict) or match.get("guild_id") != guild_id or match.get("mode") != "challenge":
            continue
        sides = [match.get(side, {}) for side in ("a", "b")]
        if not any(isinstance(side, dict) and side.get("user_id") == user_id for side in sides):
            continue
        try:
            completed_at = utc(match["timestamp"])
        except (KeyError, TypeError, ValueError):
            completed_at = None
        if completed_at is not None and completed_at <= now:
            completed.append(completed_at)
        used.update(side.get("support_token") for side in sides if isinstance(side, dict)
                    and side.get("user_id") == user_id and side.get("support_token"))
    recovering_ids = {w["id"] for w in active(guild_id, user_id, history, data, now)}
    choices = []
    for injury_id, entry in player.get("healing", {}).items():
        for payment in entry.get("treatments", []):
            try:
                if not payment.get("support_ready"):
                    continue
                token = payment["id"]
                time = utc(payment["at"])
                if token in used or time > now or now - time > timedelta(hours=SUPPORT_WINDOW_HOURS):
                    continue
                if injury_id not in recovering_ids:
                    continue
                if any(time < completed_at <= now for completed_at in completed):
                    continue
                choices.append(payment)
            except (KeyError, TypeError, ValueError):
                continue
    if not choices:
        return None
    return max(choices, key=lambda p: p["at"])


def apply_penalty(stats: dict[str, int], guild_id: int | None, user_id: int,
                  history=None, data=None, now=None, *, relief: bool = False) -> dict[str, int]:
    final, affected = dict(stats), set()
    for wound in active(guild_id, user_id, history, data, now):
        stat = wound["stat"]
        if len(affected) >= PENALTY_CAP:
            break
        if stat not in final or stat in affected:
            continue
        final[stat] = max(1, int(final[stat]) - 1)
        affected.add(stat)
    if relief and affected:
        # Reduce exactly one injury penalty, never buff the original allocation.
        first = next(stat for stat in stats if stat in affected)
        final[first] = int(stats[first])
    return final


def _treatment_roll(token: str, salt: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{token}:{salt}".encode()).digest()[:8], "big") % 100


def heal(guild_id: int | None, user_id: int, injury_id: str, now=None,
         provider: str = "shady_doctor") -> tuple[int, dict]:
    """Treatment is not instant. A failed attempt consumes gold, not time."""
    if guild_id is None:
        raise ValueError("Treat injuries inside a Discord server.")
    tier = TREATMENTS.get(provider)
    if tier is None:
        raise ValueError("Unknown treatment provider.")
    from services.progression import _db, _ensure_player, PATH, wallet
    from services.storage import save_json
    data, history = _db(), load_history()
    now = now or datetime.now(timezone.utc)
    wound = next((w for w in active(guild_id, user_id, history, data, now)
                  if w["id"] == injury_id), None)
    if wound is None:
        raise ValueError("That injury is healed or does not belong to you.")
    minimum = MIN_RECOVERY_HOURS * 3600
    if wound["remaining_seconds"] <= minimum:
        raise ValueError("Recovery is nearly complete. Allow it to finish naturally.")
    if wallet(guild_id, user_id, history, data) < tier["cost"]:
        raise ValueError(f"{tier['name']} costs {tier['cost']} gold.")
    token = uuid.uuid4().hex
    success = _treatment_roll(token, "success") >= tier["failure"]
    support = success and _treatment_roll(token, "relief") < tier["support"]
    hours_cut = min(tier["hours"], (wound["remaining_seconds"] - minimum) / 3600) if success else 0
    hours_cut = max(0, hours_cut)
    entry = _ensure_player(data, guild_id, user_id).setdefault("healing", {}).setdefault(
        injury_id, {"hours": 0, "gold": 0, "treatments": []}
    )
    entry["hours"] = float(entry.get("hours", 0)) + hours_cut
    entry["gold"] = int(entry.get("gold", 0)) + tier["cost"]
    entry["last_treated_at"] = now.isoformat()
    entry.setdefault("treatments", []).append({
        "id": token, "at": now.isoformat(), "provider": provider,
        "gold": tier["cost"], "success": success, "hours": round(hours_cut, 4),
        "support_ready": support,
    })
    save_json(PATH, data)
    return wallet(guild_id, user_id, history, data), {
        **wound, "provider": tier["name"], "success": success,
        "hours_reduced": hours_cut, "support_ready": support,
        "cost": tier["cost"],
    }


def duration(seconds: float) -> str:
    if seconds <= 0:
        return "Recovered"
    minutes = int((seconds + 59) // 60)
    if minutes >= 1440:
        d, rest = divmod(minutes, 1440)
        return f"{d}d {rest // 60}h" if rest else f"{d}d"
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m" if h else f"{m}m"
