"""Tournament Lite v0.8.5a: lifetime title and achievement progress.

Awards are computed from completed, guild-scoped brackets and verified match
journal entries. No player-editable counters or repeatable claims are stored.
"""
from __future__ import annotations

from services.records import load_history
from services.tournaments import load_db

# Title entries follow the existing competition TITLE_RULES tuple format:
# (display name, unlock description, progress stat, threshold)
TOURNAMENT_TITLES = {
    "lists_initiate": ("Lists Initiate", "Enter your first started tournament.", "tourney_entries", 1),
    "bracket_breaker": ("Bracket Breaker", "Advance through 3 tournament matches.", "tourney_advances", 3),
    "the_finalist": ("The Finalist", "Reach a completed tournament final.", "tourney_finals", 1),
    "silver_lance": ("Silver Lance", "Finish a tournament as runner-up.", "tourney_runners_up", 1),
    "cup_bearer": ("Cup Bearer", "Win your first tournament championship.", "tourney_championships", 1),
    "king_of_the_lists": ("King of the Lists", "Win 3 tournaments.", "tourney_championships", 3),
    "elite_eight": ("Elite Eight", "Compete in a started 8-rider tournament.", "tourney_eight_entries", 1),
    "grand_melee_champion": ("Grand Melee Champion", "Win an 8-rider tournament.", "tourney_eight_crowns", 1),
    "marshal_favourite": ("Marshal's Favourite", "Advance by a marshal's tiebreak.", "tourney_marshal_advances", 1),
    "tourney_veteran": ("Tourney Veteran", "Enter 5 started tournaments.", "tourney_entries", 5),
    "lance_of_the_lists": ("Lance of the Lists", "Unhorse opponents 3 times in tournament matches.", "tourney_unhorsings", 3),
    "arena_conqueror": ("Arena Conqueror", "Win tournament jousts at 3 different arenas.", "tourney_unique_arenas", 3),
}

# Achievements add permanent recognition but cannot be equipped as titles.
TOURNAMENT_ACHIEVEMENTS = {
    "first_registration": ("First Entry", "Enter a started tournament.", "entries", 1),
    "first_advance": ("Opening Victory", "Advance from your first tournament pairing.", "advances", 1),
    "championship_bout": ("Centre of the Lists", "Compete in a completed final.", "finals", 1),
    "victory_banner": ("Raise the Banner", "Win a tournament.", "championships", 1),
    "silver_medal": ("A Noble Defeat", "Finish runner-up.", "runners_up", 1),
    "eight_person_bracket": ("Grand Melee", "Compete in an 8-rider event.", "eight_entries", 1),
    "against_the_odds": ("Still Standing", "Win a tournament match while injured.", "injured_wins", 1),
    "century_of_splinters": ("Tournament Splinters", "Break 5 lances in tournament matches.", "lance_breaks", 5),
}


def _empty() -> dict[str, int]:
    return {
        "entries": 0, "eight_entries": 0, "matches": 0, "advances": 0,
        "finals": 0, "runners_up": 0, "championships": 0,
        "four_crowns": 0, "eight_crowns": 0, "marshal_advances": 0,
        "unhorsings": 0, "lance_breaks": 0, "injured_wins": 0,
        "unique_arenas": 0,
    }


def tournament_stats(
    guild_id: int, user_id: int, tournament_data: dict | None = None,
    match_history: dict | None = None,
) -> dict[str, int]:
    """Compute awards from complete bracket results, never unplayed registrations."""
    db = tournament_data if tournament_data is not None else load_db()
    journal = match_history if match_history is not None else load_history()
    group = db.get("guilds", {}).get(str(guild_id), {})
    events = list(group.get("history", []))
    live = group.get("active")
    if live and live.get("status") == "running":
        events.append(live)

    records = {}
    for entry in journal.get("matches", []):
        if not isinstance(entry, dict) or entry.get("guild_id") != guild_id:
            continue
        mid = entry.get("id")
        if mid and mid not in records and entry.get("mode") == "challenge":
            records[mid] = entry

    result = _empty()
    arenas = set()
    visited_events = set()
    for event in events:
        if not isinstance(event, dict) or event.get("guild_id") != guild_id:
            continue
        eid = event.get("id")
        if not eid or eid in visited_events or event.get("status") not in ("running", "completed"):
            continue
        visited_events.add(eid)
        entrants = event.get("entrants", [])
        if user_id not in entrants:
            continue
        result["entries"] += 1
        size = event.get("size")
        if size == 8:
            result["eight_entries"] += 1

        rounds = event.get("rounds", [])
        for ridx, rnd in enumerate(rounds):
            if not isinstance(rnd, list):
                continue
            for pairing in rnd:
                if not isinstance(pairing, dict) or pairing.get("status") != "complete":
                    continue
                a, b = pairing.get("a"), pairing.get("b")
                if user_id not in (a, b):
                    continue
                record_id = pairing.get("record_id")
                entry = records.get(record_id)
                # Verified bracket journal ownership, tournament identity and pairing.
                if (not entry or entry.get("tournament_id") != eid
                        or {entry.get("a", {}).get("user_id"), entry.get("b", {}).get("user_id")} != {a, b}):
                    continue
                result["matches"] += 1
                if ridx == len(rounds) - 1:
                    result["finals"] += 1
                    if event.get("status") == "completed":
                        if event.get("champion") == user_id:
                            result["championships"] += 1
                            if size == 4:
                                result["four_crowns"] += 1
                            elif size == 8:
                                result["eight_crowns"] += 1
                        else:
                            result["runners_up"] += 1
                if pairing.get("winner") != user_id:
                    continue
                result["advances"] += 1
                if pairing.get("tiebreak"):
                    result["marshal_advances"] += 1
                arena = entry.get("arena_key")
                if arena:
                    arenas.add(arena)
                own = entry["a"] if entry["a"]["user_id"] == user_id else entry["b"]
                other = entry["b"] if own is entry["a"] else entry["a"]
                if own.get("already_injured"):
                    result["injured_wins"] += 1
                # Only genuine awarded points count; deterministic tiebreaks do
                # not change the actual match's score or earned joust stats.
                my_side = "a" if own is entry["a"] else "b"
                for p in entry.get("passes", []):
                    if not isinstance(p, dict):
                        continue
                    try:
                        points = int(p.get("points_" + my_side, 0))
                    except (ValueError, TypeError):
                        continue
                    if points > 0 and p.get("category") == "unhorsing":
                        result["unhorsings"] += 1
                    elif points > 0 and p.get("category") == "lance_break":
                        result["lance_breaks"] += 1

        # Count lance breaks/unhorsings in lost tournament bouts too; each is
        # a completed verified match, and no feats come from ordinary duels.
        for rnd in rounds:
            for pairing in rnd:
                if not isinstance(pairing, dict) or pairing.get("status") != "complete":
                    continue
                if pairing.get("winner") == user_id or user_id not in (pairing.get("a"), pairing.get("b")):
                    continue
                entry = records.get(pairing.get("record_id"))
                if (not entry or entry.get("tournament_id") != eid
                        or {entry.get("a", {}).get("user_id"), entry.get("b", {}).get("user_id")}
                        != {pairing.get("a"), pairing.get("b")}):
                    continue
                my_side = "a" if entry["a"]["user_id"] == user_id else "b"
                for p in entry.get("passes", []):
                    if not isinstance(p, dict):
                        continue
                    try:
                        pts = int(p.get("points_" + my_side, 0))
                    except (ValueError, TypeError):
                        continue
                    if pts > 0 and p.get("category") == "unhorsing":
                        result["unhorsings"] += 1
                    elif pts > 0 and p.get("category") == "lance_break":
                        result["lance_breaks"] += 1
    result["unique_arenas"] = len(arenas)
    return result


def achievement_progress(guild_id: int, user_id: int, tournament_data: dict | None = None,
                         match_history: dict | None = None) -> dict[str, dict]:
    stats = tournament_stats(guild_id, user_id, tournament_data, match_history)
    return {
        key: {"name": name, "description": detail, "progress": stats[field],
              "required": goal, "earned": stats[field] >= goal}
        for key, (name, detail, field, goal) in TOURNAMENT_ACHIEVEMENTS.items()
    }
