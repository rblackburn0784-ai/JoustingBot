"""v0.8.5: single-elimination 4/8 player tournaments, persisted per guild.

Exactly one open tournament per guild. Match IDs/seeds are stable so a
restarted 'next match' cannot grant duplicate competitive results.
"""
from __future__ import annotations

import random
import uuid
from itertools import combinations
from datetime import datetime, timezone, timedelta

from services.storage import load_json, save_json
from services.arenas import ARENAS

PATH = "storage/tournaments.json"
ALLOWED_SIZES = (4, 8)
ALLOWED_FORMATS = ("single_elimination", "round_robin")
ALLOWED_SEEDING = ("random", "ranked")
HISTORY_LIMIT = 20  # recent() display cap; full completed history remains stored


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


def create(guild_id: int, owner_id: int, name: str, size: int, *,
           format: str = "single_elimination",
           scheduled_at: str = "", require_checkin: bool = False,
           seeding: str = "random", championship: bool = False) -> dict:
    name = " ".join(name.split())
    if size not in ALLOWED_SIZES:
        raise TournamentError("Tournament size must be 4 or 8.")
    if not 3 <= len(name) <= 50 or "\n" in name:
        raise TournamentError("Tournament name must be 3–50 characters.")
    if format not in ALLOWED_FORMATS:
        raise TournamentError("Tournament format must be single_elimination or round_robin.")
    if seeding not in ALLOWED_SEEDING:
        raise TournamentError("Seeding must be random or ranked.")
    if format == "round_robin" and seeding != "random":
        raise TournamentError("Ranked seeding applies only to elimination brackets.")
    qualifiers, circuit_season = None, None
    if championship:
        if format != "single_elimination" or seeding != "ranked":
            raise TournamentError("Circuit finals require ranked single-elimination brackets.")
        from services.circuit import seasonal_standings, season_number
        standings = seasonal_standings(guild_id)["standings"]
        qualifiers = [r["user_id"] for r in standings if r["points"] >= 7][:size]
        if len(qualifiers) != size:
            raise TournamentError(
                f"Need {size} seasonal contenders with 7+ Circuit points to create a final.")
        circuit_season = season_number()
    schedule = None
    if scheduled_at:
        try:
            schedule = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError as ex:
            raise TournamentError("Use an ISO 8601 scheduled time with timezone.") from ex
        now = datetime.now(timezone.utc)
        if schedule.tzinfo is None or not now < schedule.astimezone(timezone.utc) <= now + timedelta(days=60):
            raise TournamentError("Scheduled start must be within the next 60 days (with timezone).")
        schedule = schedule.astimezone(timezone.utc).isoformat()
    db = load_db()
    bucket = _bucket(db, guild_id)
    if bucket.get("active") is not None:
        raise TournamentError("Finish the current tournament before creating another.")
    item = {
        "id": uuid.uuid4().hex[:12],
        "name": name, "size": size, "guild_id": guild_id,
        "created_by": owner_id, "created_at": timestamp(),
        "status": "registration", "entrants": [],
        "format": format, "seeding": seeding,
        "championship": bool(championship), "season": circuit_season,
        "qualified_entrants": qualifiers,
        "scheduled_at": schedule, "require_checkin": bool(require_checkin),
        "checked_in": [],
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
    qualified = item.get("qualified_entrants")
    if qualified is not None and user_id not in qualified:
        raise TournamentError("Only season-qualified riders may enter this Circuit Final.")
    if len(item["entrants"]) >= item["size"]:
        raise TournamentError("The tournament is full.")
    item["entrants"].append(user_id)
    save_json(PATH, db)
    return item


def check_in(guild_id: int, user_id: int) -> dict:
    db = load_db()
    item = _bucket(db, guild_id).get("active")
    if not item or item.get("status") != "registration":
        raise TournamentError("There is no registration awaiting check-in.")
    if user_id not in item.get("entrants", []):
        raise TournamentError("Join the tournament before checking in.")
    verified = item.setdefault("checked_in", [])
    if user_id in verified:
        raise TournamentError("You are already checked in.")
    verified.append(user_id)
    save_json(PATH, db)
    return item


def leave(guild_id: int, user_id: int) -> dict:
    db = load_db()
    item = _bucket(db, guild_id).get("active")
    if not item or item.get("status") != "registration":
        raise TournamentError("You can leave only during open registration.")
    if user_id not in item.get("entrants", []):
        raise TournamentError("You are not registered.")
    item["entrants"].remove(user_id)
    if user_id in item.get("checked_in", []):
        item["checked_in"].remove(user_id)
    save_json(PATH, db)
    return item


def _ranked_entrants(guild_id: int, entrants: list[int]) -> list[int]:
    """Rank by genuine guild challenge wins, then ID; no user-selected seed."""
    from services.records import load_history
    scores = {uid: 0 for uid in entrants}
    seen = set()
    for record in load_history().get("matches", []):
        if not isinstance(record, dict) or record.get("guild_id") != guild_id or record.get("mode") != "challenge":
            continue
        mid = record.get("id")
        if not mid or mid in seen:
            continue
        seen.add(mid)
        a, b = record.get("a") or {}, record.get("b") or {}
        if a.get("score", 0) > b.get("score", 0) and a.get("user_id") in scores:
            scores[a["user_id"]] += 1
        elif b.get("score", 0) > a.get("score", 0) and b.get("user_id") in scores:
            scores[b["user_id"]] += 1
    return sorted(entrants, key=lambda uid: (-scores[uid], uid))


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
    if item.get("require_checkin") and set(item.get("checked_in", [])) != set(item["entrants"]):
        raise TournamentError("All registered riders must check in before starting.")
    if item.get("scheduled_at"):
        when = datetime.fromisoformat(item["scheduled_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < when:
            raise TournamentError("The scheduled start time has not arrived.")
    rng = random.Random(item["seed"])
    players = list(item["entrants"])
    if item.get("format") == "round_robin":
        rng.shuffle(players)
        rounds = [[_match(item["id"], ridx, 0, a, b,
                          rng.randrange(1, 2**31), rng.choice(tuple(ARENAS)))]
                  for ridx, (a, b) in enumerate(combinations(players, 2))]
    else:
        if item.get("seeding") == "ranked":
            ranking = (list(item["qualified_entrants"]) if item.get("championship")
                       else _ranked_entrants(guild_id, players))
            order = ((0, 3, 1, 2) if len(players) == 4
                     else (0, 7, 3, 4, 1, 6, 2, 5))
            players = [ranking[i] for i in order]
            item["seeding_order"] = list(ranking)
        else:
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
    if item.get("format") == "round_robin":
        if all(m["status"] == "complete" for rnd in item["rounds"] for m in rnd):
            scores = {uid: 0 for uid in item["entrants"]}
            for rnd in item["rounds"]:
                for completed in rnd:
                    scores[completed["winner"]] += 3
            # Deterministic tiebreak by original registered ID (published).
            ordered = sorted(item["entrants"], key=lambda uid: (-scores[uid], uid))
            item["standings"] = [{"user_id": uid, "points": scores[uid],
                                  "wins": scores[uid] // 3}
                                 for uid in ordered]
            item["champion"] = ordered[0]
            item["status"] = "completed"
            item["completed_at"] = timestamp()
            bucket.setdefault("history", []).append(item)
            bucket["active"] = None
    elif ridx == len(item["rounds"]) - 1:
        item["champion"] = winner
        item["status"] = "completed"
        item["completed_at"] = timestamp()
        bucket.setdefault("history", []).append(item)
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
