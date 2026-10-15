"""v0.8.5: single-elimination 4/8 player tournaments, persisted per guild.

Exactly one open tournament per guild. Match IDs/seeds are stable so a
restarted 'next match' cannot grant duplicate competitive results.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from services.storage import load_json, save_json
from services.arenas import ARENAS

PATH = "storage/tournaments.json"
ALLOWED_SIZES = (4, 8)
HISTORY_LIMIT = 20


class TournamentError(ValueError):
    pass


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_db() -> dict:
    db = load_json(PATH, {"guilds": {}})
    if not isinstance(db, dict) or not isinstance(db.get("guilds"), dict):
        return {"guilds": {}}
    return db


def _bucket(db: dict, guild_id: int) -> dict:
    return db.setdefault("guilds", {}).setdefault(str(guild_id), {
        "active": None, "history": [],
    })


def current(guild_id: int) -> dict | None:
    return load_db().get("guilds", {}).get(str(guild_id), {}).get("active")


def recent(guild_id: int, limit: int = 5) -> list[dict]:
    return list(reversed(load_db().get("guilds", {}).get(str(guild_id), {}).get("history", [])[-limit:]))


def create(guild_id: int, owner_id: int, name: str, size: int) -> dict:
    name = " ".join(name.split())
    if size not in ALLOWED_SIZES:
        raise TournamentError("Tournament size must be 4 or 8.")
    if not 3 <= len(name) <= 50 or "\n" in name:
        raise TournamentError("Tournament name must be 3–50 characters.")
    db = load_db()
    bucket = _bucket(db, guild_id)
    if bucket.get("active") is not None:
        raise TournamentError("Finish the current tournament before creating another.")
    item = {
        "id": uuid.uuid4().hex[:12],
        "name": name, "size": size, "guild_id": guild_id,
        "created_by": owner_id, "created_at": timestamp(),
        "status": "registration", "entrants": [],
        "seed": random.SystemRandom().randrange(1, 2**31),
        "rounds": [], "champion": None,
    }
    bucket["active"] = item
    save_json(PATH, db)
    return item


def join(guild_id: int, user_id: int) -> dict:
    db = load_db()
    item = _bucket(db, guild_id).get("active")
    if not item or item["status"] != "registration":
        raise TournamentError("There is no open tournament registration.")
    if user_id in item["entrants"]:
        raise TournamentError("You are already registered.")
    if len(item["entrants"]) >= item["size"]:
        raise TournamentError("The tournament is full.")
    item["entrants"].append(user_id)
    save_json(PATH, db)
    return item


def _match(tournament_id: str, round_index: int, match_index: int, a=None, b=None, seed=0, arena_key="royal_lists") -> dict:
    return {
        "id": f"t-{tournament_id}-r{round_index + 1}-m{match_index + 1}",
        "a": a, "b": b, "status": "pending",
        "seed": seed, "arena_key": arena_key, "winner": None, "record_id": None,
        "tiebreak": None,
    }


def start(guild_id: int) -> dict:
    db = load_db()
    item = _bucket(db, guild_id).get("active")
    if not item or item["status"] != "registration":
        raise TournamentError("No tournament is awaiting its start.")
    if len(item["entrants"]) != item["size"]:
        raise TournamentError(f"Registration must be full ({len(item['entrants'])}/{item['size']}).")
    rng = random.Random(item["seed"])
    players = list(item["entrants"])
    rng.shuffle(players)
    rounds = []
    count = len(players)
    ridx = 0
    while count >= 2:
        match_count = count // 2
        matches = [
            _match(item["id"], ridx, i,
                   players[i * 2] if ridx == 0 else None,
                   players[i * 2 + 1] if ridx == 0 else None,
                   rng.randrange(1, 2**31), rng.choice(tuple(ARENAS)))
            for i in range(match_count)
        ]
        rounds.append(matches)
        count //= 2
        ridx += 1
    item["rounds"] = rounds
    item["status"] = "running"
    item["started_at"] = timestamp()
    save_json(PATH, db)
    return item


def pending(item: dict) -> dict | None:
    for ridx, rnd in enumerate(item.get("rounds", [])):
        for midx, match in enumerate(rnd):
            if match["status"] != "complete":
                if match["a"] is not None and match["b"] is not None:
                    return {"round": ridx, "index": midx, "match": match}
                return None
    return None


def reserve_next(guild_id: int) -> dict:
    db = load_db()
    item = _bucket(db, guild_id).get("active")
    if not item or item["status"] != "running":
        raise TournamentError("No tournament is running.")
    selection = pending(item)
    if selection is None:
        raise TournamentError("No ready pairing; the tournament may already be complete.")
    match = selection["match"]
    if match["status"] == "pending":
        match["status"] = "running"
        match["reserved_at"] = timestamp()
        save_json(PATH, db)
    # A 'running' pairing can be resumed with the same seed and record ID.
    return {"tournament": item, **selection}


def complete_match(guild_id: int, tournament_id: str, match_id: str,
                   winner: int, record_id: str, *, tiebreak: str | None = None) -> dict:
    db = load_db()
    bucket = _bucket(db, guild_id)
    item = bucket.get("active")
    if not item or item["id"] != tournament_id or item["status"] != "running":
        raise TournamentError("The tournament is no longer running.")
    selection = pending(item)
    if not selection or selection["match"]["id"] != match_id:
        raise TournamentError("That is not the current pairing.")
    match = selection["match"]
    if match["status"] != "running":
        raise TournamentError("Pairing must be reserved before recording a result.")
    if winner not in (match["a"], match["b"]):
        raise TournamentError("Winner must be one of this match's registered entrants.")
    match["winner"] = winner
    match["record_id"] = record_id
    match["tiebreak"] = tiebreak
    match["status"] = "complete"
    match["completed_at"] = timestamp()
    ridx, midx = selection["round"], selection["index"]
    if ridx == len(item["rounds"]) - 1:
        item["champion"] = winner
        item["status"] = "completed"
        item["completed_at"] = timestamp()
        bucket.setdefault("history", []).append(item)
        bucket["history"] = bucket["history"][-HISTORY_LIMIT:]
        bucket["active"] = None
    else:
        downstream = item["rounds"][ridx + 1][midx // 2]
        slot = "a" if midx % 2 == 0 else "b"
        if downstream[slot] is not None:
            raise TournamentError("Next bracket slot is already occupied.")
        downstream[slot] = winner
    save_json(PATH, db)
    return item


def tie_winner(a: int, b: int, seed: int) -> int:
    """Published, stable marshal's tiebreak if the five-pass joust ends level."""
    return (a, b)[random.Random(seed ^ 0x5F3759DF).randrange(2)]
