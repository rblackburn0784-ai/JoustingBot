"""v2.9.6 — specialist, non-competitive training drills.

Four drills, each usable once per UTC day per guild/player. A successful
attempt adds one cosmetic Mastery point; never gold, competitive XP, stat
increases, equipment or injuries. No user-controlled RNG seed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import secrets

from services.evolution import bound_horse, utc_day, _state
from services.progression import _db, _ensure_player, PATH
from services.storage import save_json

DRILLS = {
    "accuracy": ("Lance Accuracy", "control", "obedience", 19,
                 "Guide the lance tip cleanly through a narrow target."),
    "seat": ("Saddle Stability", "endurance", "stamina", 20,
             "Remain steady through a hard practice tilt."),
    "defence": ("Shield Defence", "resolve", "courage", 19,
                "Cover the mark while holding a sound shield position."),
    "horsemanship": ("Horse Handling", "tactics", "obedience", 19,
                     "Keep the horse responsive through a tight course."),
}
MAX_DAILY_ATTEMPTS = len(DRILLS)
RECORD_LIMIT = 40


def _knight_and_horse(user_id: int) -> tuple[dict, dict]:
    from cogs.knight import load_knights
    knight = load_knights().get("knights", {}).get(str(user_id))
    if not isinstance(knight, dict) or int(knight.get("user_id", 0)) != user_id:
        raise ValueError("Create your knight before entering the drill yard.")
    horse = bound_horse(user_id)
    return knight, horse


def drill_status(guild_id: int, user_id: int, *,
                 now: datetime | None = None, data: dict | None = None) -> dict:
    state = _state(guild_id, user_id, data)
    records = state.get("drill_records", [])
    if not isinstance(records, list):
        records = []
    today = utc_day(now)
    attempts = {
        r.get("drill") for r in records
        if isinstance(r, dict) and r.get("day") == today
        and r.get("drill") in DRILLS
    }
    recent = [r for r in records if isinstance(r, dict)][-5:]
    return {
        "today": today, "completed": len(attempts),
        "available": tuple(key for key in DRILLS if key not in attempts),
        "mastery": max(0, int(state.get("drill_mastery", 0))),
        "recent": recent,
    }


def run_drill(guild_id: int, user_id: int, key: str, *,
              now: datetime | None = None, roll: int | None = None) -> dict:
    if key not in DRILLS:
        raise ValueError("Unknown specialist drill.")
    _state(guild_id, user_id)  # require a guild before touching any global data
    knight, horse = _knight_and_horse(user_id)
    data = _db()
    status = drill_status(guild_id, user_id, now=now, data=data)
    if key not in status["available"]:
        raise ValueError("You've completed this drill today. Try again after UTC midnight.")
    if status["completed"] >= MAX_DAILY_ATTEMPTS:
        raise ValueError("You've reached today's training-drill limit.")
    label, knight_stat, horse_stat, target, description = DRILLS[key]
    value = secrets.randbelow(20) + 1 if roll is None else roll
    if type(value) is not int or not 1 <= value <= 20:
        raise ValueError("Invalid internal drill roll.")
    bonus = int(knight["stats"].get(knight_stat, 0)) + int(horse["stats"].get(horse_stat, 0))
    total = value + bonus
    success = total >= target
    point = now or datetime.now(timezone.utc)
    if point.tzinfo is None:
        raise ValueError("Time must have a timezone.")
    attempt = {
        "day": status["today"], "at": point.astimezone(timezone.utc).isoformat(),
        "drill": key, "roll": value, "bonus": bonus,
        "score": total, "target": target, "success": success,
        "mastery_awarded": int(success),
    }
    state = _ensure_player(data, guild_id, user_id)
    state.setdefault("drill_records", []).append(attempt)
    state["drill_records"] = state["drill_records"][-RECORD_LIMIT:]
    state["drill_mastery"] = max(0, int(state.get("drill_mastery", 0))) + int(success)
    save_json(PATH, data)
    return {**attempt, "name": label, "description": description,
            "mastery": state["drill_mastery"],
            "remaining_today": MAX_DAILY_ATTEMPTS - status["completed"] - 1}
