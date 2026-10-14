"""Guild-scoped leaderboards, earned titles and selected-title storage (v0.7)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from services.records import load_history
from services.storage import load_json, save_json

TITLES_PATH = "storage/titles.json"
MIN_WIN_RATE_JOUSTS = 5
MIN_HORSE_JOUSTS = 5
MIN_CHAOTIC_JOUSTS = 3
MIN_ARENA_JOUSTS = 3
TOP_COUNT = 10

# Stable keys are used in storage; display names are never used as IDs.
TITLE_RULES = {
    "the_unhorsed": ("The Unhorsed", "Be unhorsed 5 times.", "unhorsed", 5),
    "shield_splitter": ("Shield Splitter", "Break 5 lances.", "lance_breaks", 5),
    "mud_king": ("Mud King", "Win 3 jousts on Muddy Field.", "mud_wins", 3),
    "frozen_terror": ("Frozen Terror", "Win 3 jousts on Frozen Ground.", "frozen_wins", 3),
    "crowd_favourite": ("Crowd Favourite", "Complete 10 jousts.", "jousts", 10),
    "the_reluctant_rider": ("The Reluctant Rider", "Experience 3 horse refusals.", "refusals", 3),
}

CATEGORIES = {
    "wins": "Most Wins",
    "winrate": "Best Win Rate (5+ jousts)",
    "unhorsings": "Most Unhorsings",
    "lancebreaks": "Most Lance Breaks",
    "jousts": "Most Jousts",
    "reliable_horse": "Most Reliable Horse (5+ jousts)",
    "chaotic_horse": "Most Chaotic Horse (3+ jousts)",
    "arena": "Arena Specialists (3+ jousts per arena)",
}


def guild_matches(guild_id: int, history: dict | None = None) -> list[dict]:
    """Legacy v0.6 matches without guild_id are intentionally excluded."""
    matches = (history if history is not None else load_history()).get("matches", [])
    seen: set[str] = set()
    selected: list[dict] = []
    for m in matches:
        if not isinstance(m, dict) or m.get("guild_id") != guild_id:
            continue
        match_id = str(m.get("id", ""))
        if match_id and match_id in seen:
            continue
        if match_id:
            seen.add(match_id)
        if isinstance(m.get("a"), dict) and isinstance(m.get("b"), dict):
            selected.append(m)
    return selected


def _knight() -> dict:
    return dict(name="", wins=0, losses=0, draws=0, jousts=0, unhorsings=0,
                unhorsed=0, lance_breaks=0, refusals=0, mud_wins=0, frozen_wins=0,
                arenas=defaultdict(lambda: {"wins": 0, "jousts": 0}))


def _horse() -> dict:
    return dict(name="", owner_id=0, jousts=0, wins=0, refusals=0,
                slips=0, clean_jousts=0)


def aggregate(guild_id: int, history: dict | None = None) -> tuple[dict[int, dict], dict[str, dict]]:
    """Calculate stats once, using recorded pass categories and participants."""
    knights: dict[int, dict] = defaultdict(_knight)
    horses: dict[str, dict] = defaultdict(_horse)

    for match in guild_matches(guild_id, history):
        riders = {side: match[side] for side in ("a", "b")}
        try:
            a_score, b_score = int(riders["a"]["score"]), int(riders["b"]["score"])
            ids = {side: int(riders[side]["user_id"]) for side in ("a", "b")}
        except (ValueError, TypeError, KeyError):
            continue

        horse_ids: dict[str, str] = {}
        incidents = {"a": False, "b": False}
        for side in ("a", "b"):
            entry = riders[side]
            user = knights[ids[side]]
            user["name"] = str(entry.get("knight", "Knight"))[:80]
            user["jousts"] += 1
            won = (a_score > b_score) if side == "a" else (b_score > a_score)
            if a_score == b_score:
                user["draws"] += 1
            elif won:
                user["wins"] += 1
            else:
                user["losses"] += 1

            arena = str(match.get("arena_key", "unknown"))
            user["arenas"][arena]["jousts"] += 1
            if won:
                user["arenas"][arena]["wins"] += 1
                if arena == "muddy_field":
                    user["mud_wins"] += 1
                if arena == "frozen_ground":
                    user["frozen_wins"] += 1

            hid = str(entry.get("horse_id") or "")
            horse_ids[side] = hid
            if hid:
                horse = horses[hid]
                horse["name"] = str(entry.get("horse", "Horse"))[:80]
                horse["owner_id"] = ids[side]
                horse["jousts"] += 1
                if won:
                    horse["wins"] += 1

        for p in match.get("passes", []):
            if not isinstance(p, dict):
                continue
            category = str(p.get("category", ""))
            result = str(p.get("result", ""))
            notes = p.get("notes", [])
            if not isinstance(notes, list):
                notes = []
            for side in ("a", "b"):
                opponent = "b" if side == "a" else "a"
                try:
                    my_pts = int(p.get("points_" + side, 0))
                    opp_pts = int(p.get("points_" + opponent, 0))
                except (ValueError, TypeError):
                    my_pts = opp_pts = 0
                player = knights[ids[side]]
                if category == "unhorsing":
                    if my_pts > 0:
                        player["unhorsings"] += 1
                    if opp_pts > 0:
                        player["unhorsed"] += 1
                if category == "lance_break" and my_pts > 0:
                    player["lance_breaks"] += 1

                hid = horse_ids[side]
                if not hid:
                    continue
                horse = horses[hid]
                name = str(riders[side].get("horse", ""))
                # Older logs include the affected horse in result/notes.
                refused = category == "horse_refusal" and (
                    result.startswith(name + ":") or result == "Both horses refused"
                )
                slipped = (
                    (category == "horse_slip" and result.startswith(name + ":"))
                    or any(str(note).startswith(name + " slips ") for note in notes)
                )
                if refused:
                    horse["refusals"] += 1
                    player["refusals"] += 1
                    incidents[side] = True
                if slipped:
                    horse["slips"] += 1
                    incidents[side] = True

        for side in ("a", "b"):
            hid = horse_ids[side]
            if hid and not incidents[side]:
                horses[hid]["clean_jousts"] += 1

    return dict(knights), dict(horses)


def ranked(guild_id: int, category: str, history: dict | None = None) -> list[dict]:
    if category not in CATEGORIES:
        raise ValueError("Unknown leaderboard category")
    knights, horses = aggregate(guild_id, history)
    rows: list[dict] = []
    if category in {"wins", "winrate", "unhorsings", "lancebreaks", "jousts"}:
        field = {"wins": "wins", "unhorsings": "unhorsings", "lancebreaks": "lance_breaks",
                 "jousts": "jousts"}.get(category)
        for uid, s in knights.items():
            if category == "winrate":
                if s["jousts"] < MIN_WIN_RATE_JOUSTS:
                    continue
                value = 100 * s["wins"] / s["jousts"]
                detail = f"{value:.1f}% ({s['wins']}W/{s['jousts']}J)"
            else:
                value = s[field]
                detail = str(value)
            rows.append({"id": uid, "name": s["name"], "value": value, "detail": detail})
    elif category in {"reliable_horse", "chaotic_horse"}:
        for horse_id, s in horses.items():
            minimum = MIN_HORSE_JOUSTS if category == "reliable_horse" else MIN_CHAOTIC_JOUSTS
            if s["jousts"] < minimum:
                continue
            if category == "reliable_horse":
                value = 100 * s["clean_jousts"] / s["jousts"]
                detail = f"{value:.1f}% clean ({s['clean_jousts']}/{s['jousts']})"
            else:
                value = (s["refusals"] + s["slips"]) / s["jousts"]
                detail = f"{value:.2f} incidents/joust ({s['refusals']} refusals, {s['slips']} slips)"
            rows.append({"id": horse_id, "name": s["name"],
                         "owner_id": s["owner_id"], "value": value, "detail": detail})
    else:
        for uid, s in knights.items():
            options = [(arena, d) for arena, d in s["arenas"].items()
                       if d["jousts"] >= MIN_ARENA_JOUSTS]
            if not options:
                continue
            arena, d = max(options, key=lambda x: (x[1]["wins"], x[1]["wins"] / x[1]["jousts"]))
            rate = 100 * d["wins"] / d["jousts"]
            rows.append({"id": uid, "name": s["name"], "value": d["wins"],
                         "detail": f"{arena.replace('_', ' ').title()}: {d['wins']}W/{d['jousts']}J ({rate:.0f}%)"})
    rows.sort(key=lambda r: (-r["value"], str(r.get("name", "")).casefold(), str(r["id"])))
    return rows[:TOP_COUNT]


def title_progress(guild_id: int, user_id: int, history: dict | None = None) -> dict[str, dict]:
    knights, _ = aggregate(guild_id, history)
    s = knights.get(user_id, _knight())
    fields = {
        "unhorsed": s["unhorsed"], "lance_breaks": s["lance_breaks"],
        "mud_wins": s["mud_wins"], "frozen_wins": s["frozen_wins"],
        "jousts": s["jousts"], "refusals": s["refusals"],
    }
    return {key: {"name": name, "description": desc, "progress": fields[field],
                  "required": target, "earned": fields[field] >= target}
            for key, (name, desc, field, target) in TITLE_RULES.items()}


def equipped_title(guild_id: int, user_id: int, history: dict | None = None) -> str | None:
    data = load_json(TITLES_PATH, {"guilds": {}})
    key = str(data.get("guilds", {}).get(str(guild_id), {}).get(str(user_id), ""))
    if key and title_progress(guild_id, user_id, history).get(key, {}).get("earned"):
        return TITLE_RULES[key][0]
    return None


def set_title(guild_id: int, user_id: int, key: str | None, history: dict | None = None) -> None:
    if key is not None and not title_progress(guild_id, user_id, history).get(key, {}).get("earned"):
        raise ValueError("You haven't earned that title yet.")
    data = load_json(TITLES_PATH, {"guilds": {}})
    if not isinstance(data, dict):
        data = {"guilds": {}}
    players = data.setdefault("guilds", {}).setdefault(str(guild_id), {})
    if key is None:
        players.pop(str(user_id), None)
    else:
        players[str(user_id)] = key
    save_json(TITLES_PATH, data)
