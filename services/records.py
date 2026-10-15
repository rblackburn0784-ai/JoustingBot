from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from services.storage import load_json, save_json

HISTORY_PATH = "storage/matches.json"
LIMIT = 5

def load_history() -> dict:
    data = load_json(HISTORY_PATH, {"matches": []})
    if not isinstance(data, dict) or not isinstance(data.get("matches"), list):
        return {"matches": []}
    return data

def record_match(prepared: Any, result: Any, *, match_id: str | None = None,
                 tournament_id: str | None = None) -> str:
    """Append completed matches only; decline/timeout never calls this function."""
    data = load_history()
    match_id = match_id or str(uuid.uuid4())
    if tournament_id:
        existing = next((m for m in data["matches"] if m.get("id") == match_id), None)
        if existing is not None:
            if (existing.get("tournament_id") != tournament_id
                    or existing.get("guild_id") != prepared.guild_id):
                raise ValueError("Tournament match record identity conflict.")
            return match_id
    passes = []
    for p in result.passes:
        passes.append({
            "pass_no": p.pass_no, "category": p.category, "result": p.result,
            "points_a": p.points_a, "points_b": p.points_b,
            "notes": list(p.notes),
        })
    entry = {
        "id": match_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "guild_id": getattr(prepared, "guild_id", None),
        "mode": getattr(prepared, "mode", "instant"),
        "arena_key": prepared.arena_key, "arena_name": result.arena_name,
        "seed": result.seed,
        "tournament_id": tournament_id,
        "a": {"user_id": prepared.fighter_a.user_id, "knight": prepared.knight_a.name,
              "horse_id": prepared.horse_a.horse_id, "horse": prepared.horse_a.name,
              "horse_breed": getattr(prepared.horse_a, "breed", ""),
              "horse_stats": dict(getattr(prepared.horse_a, "stats", {})),
              "already_injured": bool(getattr(prepared, "had_injury_a", False)),
              "support_token": getattr(prepared, "support_token_a", None),
              "gear": {"lance": prepared.fighter_a.lance_key, "armour": prepared.fighter_a.armour_key,
                       "barding": prepared.fighter_a.barding_key},
              "score": result.score_a},
        "b": {"user_id": prepared.fighter_b.user_id, "knight": prepared.knight_b.name,
              "horse_id": prepared.horse_b.horse_id, "horse": prepared.horse_b.name,
              "horse_breed": getattr(prepared.horse_b, "breed", ""),
              "horse_stats": dict(getattr(prepared.horse_b, "stats", {})),
              "already_injured": bool(getattr(prepared, "had_injury_b", False)),
              "support_token": getattr(prepared, "support_token_b", None),
              "gear": {"lance": prepared.fighter_b.lance_key, "armour": prepared.fighter_b.armour_key,
                       "barding": prepared.fighter_b.barding_key},
              "score": result.score_b},
        "passes": passes,
    }
    from services.injuries import make_events
    entry["injuries"] = make_events(entry)
    data["matches"].append(entry)
    save_json(HISTORY_PATH, data)
    return match_id

def participant_matches(user_id: int) -> list[dict]:
    matches = load_history()["matches"]
    return [m for m in matches if any(m.get(side, {}).get("user_id") == user_id for side in ("a", "b"))]

def latest_matches(user_id: int, count: int = LIMIT) -> list[dict]:
    return participant_matches(user_id)[-count:][::-1]

def knight_record(user_id: int) -> dict[str, int]:
    stats = {k: 0 for k in ("wins", "losses", "draws", "jousts_completed",
                             "unhorsings_caused", "times_unhorsed", "lance_breaks")}
    for m in participant_matches(user_id):
        mine = "a" if m["a"]["user_id"] == user_id else "b"
        other = "b" if mine == "a" else "a"
        stats["jousts_completed"] += 1
        if m[mine]["score"] == m[other]["score"]:
            stats["draws"] += 1
        elif m[mine]["score"] > m[other]["score"]:
            stats["wins"] += 1
        else:
            stats["losses"] += 1
        for p in m["passes"]:
            cat = p["category"]
            my_pts = p.get("points_" + mine, 0)
            their_pts = p.get("points_" + other, 0)
            if cat == "unhorsing":
                if my_pts > 0: stats["unhorsings_caused"] += 1
                if their_pts > 0: stats["times_unhorsed"] += 1
            elif cat == "lance_break" and my_pts > 0:
                stats["lance_breaks"] += 1
    return stats

def horse_record(horse_id: str) -> dict[str, int]:
    stats = {k: 0 for k in ("jousts_run", "refusals", "slips", "wins_with_rider")}
    for m in load_history()["matches"]:
        if m.get("a", {}).get("horse_id") == horse_id: mine, other = "a", "b"
        elif m.get("b", {}).get("horse_id") == horse_id: mine, other = "b", "a"
        else: continue
        stats["jousts_run"] += 1
        if m[mine]["score"] > m[other]["score"]:
            stats["wins_with_rider"] += 1
        name = m[mine]["horse"]
        for p in m["passes"]:
            if p["category"] == "horse_refusal" and (
                p["result"].startswith(name + ":") or
                p["result"] == "Both horses refused"
            ):
                stats["refusals"] += 1
            if p["category"] == "horse_slip" and p["result"].startswith(name + ":"):
                stats["slips"] += 1
            if any(note.startswith(name + " slips ") for note in p.get("notes", [])):
                stats["slips"] += 1
    return stats
