"""v2.9.7 Grand Tournament Circuit: honorary Houses, seasons and verified honours.

All standings are derived from completed, guild-scoped tournament brackets
joined to the immutable match journal. No repeatable rewards or paid bonuses.
Historic House affiliation is snapshotted on match recording; transfers do not
rewrite a former House's results.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid

from services.arenas import ARENAS
from services.records import load_history
from services.storage import load_json, save_json
from services.tournaments import load_db as tournament_db

PATH = "storage/houses.json"
SEASON_START = datetime(2026, 11, 18, tzinfo=timezone.utc)
SEASON_DAYS = 42
MAX_HOUSES = 12
MAX_MEMBERS = 50
MAX_FEED = 12
HOUSE_TRANSFER_HOURS = 24


class CircuitError(ValueError):
    pass


def utc(value: datetime | str | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as ex:
            raise CircuitError("Invalid saved UTC timestamp.") from ex
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CircuitError("A timezone-aware date is required.")
    return value.astimezone(timezone.utc)


def season_number(when: datetime | str | None = None) -> int | None:
    point = utc(when)
    if point < SEASON_START:
        return None
    return int((point - SEASON_START).days // SEASON_DAYS) + 1


def season_window(number: int | None = None, now: datetime | None = None) -> dict:
    if number is None:
        number = season_number(now)
    if not isinstance(number, int) or not 1 <= number <= 500:
        raise CircuitError("Unknown Grand Circuit season.")
    start = SEASON_START + timedelta(days=(number - 1) * SEASON_DAYS)
    end = start + timedelta(days=SEASON_DAYS)
    return {"number": number, "name": f"Season {number}: The King's Circuit",
            "start": start.isoformat(), "end": end.isoformat(),
            "active": start <= utc(now) < end}


def load_houses() -> dict:
    data = load_json(PATH, {"guilds": {}})
    if not isinstance(data, dict) or not isinstance(data.get("guilds"), dict):
        raise CircuitError("House data is damaged. Contact an admin; no records were changed.")
    return data


def _bucket(data: dict, guild_id: int) -> dict:
    if not isinstance(guild_id, int) or guild_id <= 0:
        raise CircuitError("This action must be used in a server.")
    bucket = data.setdefault("guilds", {}).setdefault(
        str(guild_id), {"houses": {}, "members": {}})
    if not isinstance(bucket, dict):
        raise CircuitError("Invalid stored House roster.")
    bucket.setdefault("houses", {})
    bucket.setdefault("members", {})
    bucket.setdefault("departures", {})
    if (not isinstance(bucket["houses"], dict)
            or not isinstance(bucket["members"], dict)
            or not isinstance(bucket["departures"], dict)):
        raise CircuitError("Invalid stored House roster.")
    # Fail closed on broken rosters instead of allowing writes that amplify
    # corruption. Applies to old v2.9.7 saves with no departures key.
    for hid, house in bucket["houses"].items():
        if (not isinstance(house, dict) or house.get("id") != hid
                or not isinstance(house.get("members"), list)
                or not isinstance(house.get("captain"), int)
                or house["captain"] not in house["members"]
                or any(type(uid) is not int or uid <= 0 for uid in house["members"])
                or len(house["members"]) != len(set(house["members"]))
                or not isinstance(house.get("name"), str)):
            raise CircuitError("House roster is damaged; contact a server admin.")
        if any(bucket["members"].get(str(uid)) != hid for uid in house["members"]):
            raise CircuitError("House membership index does not match the roster.")
    for uid, hid in bucket["members"].items():
        if (not str(uid).isdigit() or hid not in bucket["houses"]
                or int(uid) not in bucket["houses"][hid]["members"]):
            raise CircuitError("House membership index is damaged.")
    return bucket


def _rider_id(user_id: int) -> None:
    if type(user_id) is not int or user_id <= 0:
        raise CircuitError("Invalid knight ID.")


def _transfer_check(bucket: dict, user_id: int,
                    destination: str | None,
                    now: datetime | None = None) -> None:
    departure = bucket["departures"].get(str(user_id))
    if departure is None:
        return
    if not isinstance(departure, dict) or not isinstance(departure.get("house"), str):
        raise CircuitError("House transfer record is damaged; contact an admin.")
    if destination is not None and destination == departure["house"]:
        return  # returning to the same original House is harmless
    if not isinstance(departure.get("at"), str):
        raise CircuitError("House transfer timestamp is invalid; contact an admin.")
    elapsed = (utc(now) - utc(departure["at"])).total_seconds()
    if elapsed < 0:
        raise CircuitError("House transfer timestamp is in the future; contact an admin.")
    if elapsed < HOUSE_TRANSFER_HOURS * 3600:
        remaining = max(1, int((HOUSE_TRANSFER_HOURS * 3600 - elapsed + 3599) // 3600))
        raise CircuitError(
            f"House transfers have a {HOUSE_TRANSFER_HOURS}-hour cooldown "
            f"({remaining} hour(s) remaining). Returning to your previous House is allowed.")


def house_for(guild_id: int | None, user_id: int) -> str | None:
    if not guild_id or user_id <= 0:
        return None
    bucket = _bucket(load_houses(), guild_id)
    hid = bucket["members"].get(str(user_id))
    house = bucket["houses"].get(hid)
    if not isinstance(house, dict) or user_id not in house.get("members", []):
        return None
    return hid


def create_house(guild_id: int, user_id: int, name: str) -> dict:
    _rider_id(user_id)
    name = " ".join(str(name or "").split())
    if not 3 <= len(name) <= 32 or any(ch in name for ch in "<>@#\n\r"):
        raise CircuitError("House name must contain 3–32 characters and no mentions.")
    data = load_houses()
    group = _bucket(data, guild_id)
    if str(user_id) in group["members"]:
        raise CircuitError("Leave your current House before founding another.")
    _transfer_check(group, user_id, None)
    if len(group["houses"]) >= MAX_HOUSES:
        raise CircuitError("This server already has the maximum 12 Houses.")
    if any(h.get("name", "").casefold() == name.casefold()
           for h in group["houses"].values()):
        raise CircuitError("A House already bears that name.")
    hid = uuid.uuid4().hex[:10]
    house = {"id": hid, "name": name, "captain": user_id,
             "members": [user_id], "created_at": utc().isoformat()}
    group["houses"][hid] = house
    group["members"][str(user_id)] = hid
    save_json(PATH, data)
    return house


def join_house(guild_id: int, user_id: int, house_id: str, *,
               now: datetime | None = None) -> dict:
    _rider_id(user_id)
    data = load_houses()
    group = _bucket(data, guild_id)
    if str(user_id) in group["members"]:
        raise CircuitError("You are already in a House. Leave it first.")
    house = group["houses"].get(house_id)
    if not isinstance(house, dict):
        raise CircuitError("That House does not exist in this server.")
    _transfer_check(group, user_id, house_id, now)
    if len(house.get("members", [])) >= MAX_MEMBERS:
        raise CircuitError("That House's roster is full.")
    house["members"].append(user_id)
    group["members"][str(user_id)] = house_id
    save_json(PATH, data)
    return house


def leave_house(guild_id: int, user_id: int, *,
                now: datetime | None = None) -> None:
    _rider_id(user_id)
    data = load_houses()
    group = _bucket(data, guild_id)
    hid = group["members"].get(str(user_id))
    house = group["houses"].get(hid)
    if not isinstance(house, dict):
        raise CircuitError("You have not joined a House.")
    if house["captain"] == user_id and len(house["members"]) > 1:
        raise CircuitError("Transfer the captaincy before leaving your House.")
    house["members"].remove(user_id)
    del group["members"][str(user_id)]
    group["departures"][str(user_id)] = {"house": hid, "at": utc(now).isoformat()}
    if not house["members"]:
        del group["houses"][hid]
    save_json(PATH, data)


def transfer_captain(guild_id: int, captain_id: int, to_user: int) -> dict:
    _rider_id(captain_id)
    _rider_id(to_user)
    data = load_houses()
    group = _bucket(data, guild_id)
    hid = group["members"].get(str(captain_id))
    house = group["houses"].get(hid)
    if not house or house["captain"] != captain_id:
        raise CircuitError("Only a House captain can transfer captaincy.")
    if to_user == captain_id or to_user not in house["members"]:
        raise CircuitError("Choose another current member of your House.")
    house["captain"] = to_user
    save_json(PATH, data)
    return house


def guild_houses(guild_id: int, data: dict | None = None) -> dict:
    return _bucket(data if data is not None else load_houses(), guild_id)["houses"]


def verified_results(guild_id: int, tournaments: dict | None = None,
                     history: dict | None = None) -> list[dict]:
    """One verified journal row per completed bracket match; no free wins from
    forged names, ordinary challenges, pending brackets or duplicate records.
    """
    tdb = tournaments if tournaments is not None else tournament_db()
    journal = history if history is not None else load_history()
    group = tdb.get("guilds", {}).get(str(guild_id), {})
    events = list(group.get("history", []))
    active = group.get("active")
    if isinstance(active, dict) and active.get("status") == "running":
        events.append(active)
    matches = {}
    for row in journal.get("matches", []):
        if isinstance(row, dict) and row.get("guild_id") == guild_id and row.get("mode") == "challenge":
            mid = row.get("id")
            if mid and mid not in matches:
                matches[mid] = row
    found, used = [], set()
    for event in events:
        if not isinstance(event, dict) or event.get("guild_id") != guild_id \
                or event.get("status") not in ("running", "completed"):
            continue
        for rnd in event.get("rounds", []):
            for pairing in rnd:
                if not isinstance(pairing, dict) or pairing.get("status") != "complete":
                    continue
                record_id = pairing.get("record_id")
                if not record_id or record_id in used:
                    continue
                row = matches.get(record_id)
                if not row or row.get("tournament_id") != event.get("id") \
                        or row.get("id") != pairing.get("id"):
                    continue
                a, b = row.get("a") or {}, row.get("b") or {}
                if (a.get("user_id"), b.get("user_id")) != (
                        pairing.get("a"), pairing.get("b")):
                    continue
                if pairing.get("winner") not in (a.get("user_id"), b.get("user_id")):
                    continue
                # When the journal contains optional provenance details, they
                # must match the stored bracket. Older records lacking a seed
                # still remain readable and cannot be backfilled arbitrarily.
                if ("seed" in row and row["seed"] != pairing.get("seed")):
                    continue
                if ("arena_key" in row and row["arena_key"] != pairing.get("arena_key")):
                    continue
                try:
                    when = utc(row["timestamp"])
                except (KeyError, CircuitError):
                    continue
                used.add(record_id)
                found.append({"event": event, "pairing": pairing,
                              "journal": row, "when": when})
    return found


def seasonal_standings(guild_id: int, season: int | None = None, *,
                       tournaments: dict | None = None,
                       history: dict | None = None) -> dict:
    window = season_window(season)
    start, end = utc(window["start"]), utc(window["end"])
    played = verified_results(guild_id, tournaments, history)
    rows: dict[int, dict] = {}
    # Count all verified matches for an event, even across season boundaries.
    all_verified_events: dict[str, int] = defaultdict(int)
    for verified in played:
        all_verified_events[verified["event"]["id"]] += 1

    def profile(uid, knight):
        if uid not in rows:
            rows[uid] = {"user_id": uid, "name": knight or f"Knight {uid}",
                         "points": 0, "played": 0, "wins": 0,
                         "championships": 0, "finals": 0}
        return rows[uid]

    for pair in played:
        if not start <= pair["when"] < end:
            continue
        match = pair["journal"]
        winner = pair["pairing"]["winner"]
        for side in ("a", "b"):
            member = match[side]
            uid = member["user_id"]
            if not isinstance(uid, int) or uid <= 0:
                continue
            item = profile(uid, member.get("knight"))
            item["played"] += 1
            item["points"] += 2  # participation, but only verified played rounds
            if winner == uid:
                item["wins"] += 1
                item["points"] += 5

    # A completed crown is genuine only with all match records verified.
    tdb = tournaments if tournaments is not None else tournament_db()
    events = tdb.get("guilds", {}).get(str(guild_id), {}).get("history", [])
    for event in events:
        if not isinstance(event, dict) or event.get("status") != "completed":
            continue
        eid = event.get("id")
        expected = sum(len(rnd) for rnd in event.get("rounds", []))
        if not eid or expected == 0 or all_verified_events[eid] != expected:
            continue
        try:
            completed = utc(event["completed_at"])
        except (KeyError, CircuitError):
            continue
        if not start <= completed < end:
            continue
        champ = event.get("champion")
        if champ in rows:
            rows[champ]["championships"] += 1
            rows[champ]["points"] += 10
        # No fictional runner-up: round-robin crowns have no final opponent.
        if event.get("format", "single_elimination") == "single_elimination":
            final = event["rounds"][-1][0]
            runner = final["b"] if final["a"] == champ else final["a"]
            if runner in rows:
                rows[runner]["finals"] += 1
                rows[runner]["points"] += 3

    standings = sorted(rows.values(),
                       key=lambda r: (-r["points"], -r["wins"],
                                      -r["championships"], r["user_id"]))
    return {"season": window, "standings": standings, "verified_matches": sum(
        1 for row in played if start <= row["when"] < end
    )}


def arena_champions(guild_id: int, season: int | None = None, *,
                    tournaments: dict | None = None,
                    history: dict | None = None) -> dict:
    window = season_window(season)
    start, end = utc(window["start"]), utc(window["end"])
    buckets: dict[str, dict[int, dict]] = {key: {} for key in ARENAS}
    for pair in verified_results(guild_id, tournaments, history):
        if not start <= pair["when"] < end:
            continue
        key = pair["journal"].get("arena_key")
        if key not in buckets:
            continue
        match = pair["journal"]
        for side in ("a", "b"):
            uid = match[side].get("user_id")
            if not isinstance(uid, int) or uid <= 0:
                continue
            row = buckets[key].setdefault(uid, {"id": uid, "played": 0, "wins": 0})
            row["played"] += 1
            row["wins"] += int(pair["pairing"]["winner"] == uid)
    result = {}
    for key in ARENAS:
        qualified = [entry for entry in buckets[key].values() if entry["wins"] >= 3]
        qualified.sort(key=lambda v: (-v["wins"], -v["wins"] / v["played"], v["id"]))
        result[key] = qualified[:3]
    return {"season": window, "arenas": result}


def house_standings(guild_id: int, season: int | None = None, *,
                    tournaments: dict | None = None,
                    history: dict | None = None,
                    houses: dict | None = None) -> list[dict]:
    window = season_window(season)
    start, end = utc(window["start"]), utc(window["end"])
    named = guild_houses(guild_id, houses)
    tally = defaultdict(lambda: {"points": 0, "matches": 0, "wins": 0,
                                 "rivalry_wins": 0})
    for pair in verified_results(guild_id, tournaments, history):
        if not start <= pair["when"] < end:
            continue
        row = pair["journal"]
        a, b = row.get("a") or {}, row.get("b") or {}
        house_a, house_b = a.get("house_id"), b.get("house_id")
        if house_a and house_a == house_b:
            # Intra-house jousts don't count towards collective scores.
            continue
        for side, hid, rival in (("a", house_a, house_b), ("b", house_b, house_a)):
            if not hid:
                continue
            entry = tally[hid]
            entry["matches"] += 1
            entry["points"] += 1
            if pair["pairing"]["winner"] == row[side]["user_id"]:
                entry["wins"] += 1
                entry["points"] += 3
                if rival:
                    entry["rivalry_wins"] += 1
                    entry["points"] += 1
    result = [{"id": hid, "name": named.get(hid, {}).get("name", "Former House"),
               **counts} for hid, counts in tally.items()]
    for hid, house in named.items():
        if hid not in tally:
            result.append({"id": hid, "name": house.get("name", "House"),
                           "points": 0, "matches": 0, "wins": 0, "rivalry_wins": 0})
    result.sort(key=lambda r: (-r["points"], -r["wins"], r["name"].casefold(), r["id"]))
    return result


def champions_hall(guild_id: int, *, tournaments: dict | None = None,
                   history: dict | None = None, limit: int = 15) -> list[dict]:
    tdb = tournaments if tournaments is not None else tournament_db()
    by_event = defaultdict(int)
    for pair in verified_results(guild_id, tdb, history):
        by_event[pair["event"]["id"]] += 1
    rows = []
    for event in tdb.get("guilds", {}).get(str(guild_id), {}).get("history", []):
        if not isinstance(event, dict) or event.get("status") != "completed":
            continue
        expected = sum(len(rnd) for rnd in event.get("rounds", []))
        if not expected or by_event[event.get("id")] != expected:
            continue
        when = event.get("completed_at", "")
        try:
            season = season_number(when)
        except CircuitError:
            continue
        rows.append({"event_id": event["id"], "name": event["name"],
                     "champion": event["champion"], "season": season,
                     "date": when[:10], "format": event.get("format", "single_elimination"),
                     "size": event["size"]})
    rows.sort(key=lambda x: (x["date"], x["event_id"]), reverse=True)
    return rows[:max(0, min(50, limit))]


def chronicle(guild_id: int, *, tournaments: dict | None = None,
              history: dict | None = None, limit: int = 8) -> list[dict]:
    """Human-readable headlines grounded in completed verified events."""
    events = champions_hall(guild_id, tournaments=tournaments, history=history, limit=50)
    headlines = []
    for event in events:
        lines = ("From the Grand Melee" if event["size"] == 8
                 else "From the Lists")
        headlines.append({
            "day": event["date"],
            "title": f"🏆 {event['name']} crowns a champion",
            "body": f"<@{event['champion']}> has claimed the {lines.lower()} crown. "
                    f"{event['size']} riders took part; format: "
                    f"{event['format'].replace('_', ' ')}.",
        })
    # Verified upset notices only when ranked seeding was in effect.
    for item in verified_results(guild_id, tournaments, history):
        event = item["event"]
        ranking = event.get("seeding_order") or []
        if not ranking:
            continue
        pair = item["pairing"]
        winner, a, b = pair.get("winner"), pair.get("a"), pair.get("b")
        loser = b if winner == a else a
        if winner in ranking and loser in ranking and ranking.index(winner) > ranking.index(loser):
            headlines.append({
                "day": item["when"].date().isoformat(),
                "title": "⚔️ A lower seed topples a favourite",
                "body": f"<@{winner}> defeats higher-seeded <@{loser}> in "
                        f"{event.get('name', 'the tournament')[:50]}.",
            })
    headlines.sort(key=lambda item: item["day"], reverse=True)
    return headlines[:max(0, min(MAX_FEED, limit))]



def house_missions(guild_id: int, house_id: str, *,
                   now: datetime | None = None,
                   tournaments: dict | None = None,
                   history: dict | None = None) -> dict:
    """Daily cooperative goals from unique verified matches; no repeatable claims."""
    today = utc(now).date()
    bouts, members, wins = 0, set(), 0
    for item in verified_results(guild_id, tournaments, history):
        if item["when"].date() != today:
            continue
        match = item["journal"]
        a, b = match.get("a") or {}, match.get("b") or {}
        if a.get("house_id") == b.get("house_id"):
            continue
        for side in ("a", "b"):
            user = match[side]
            if user.get("house_id") != house_id:
                continue
            bouts += 1
            members.add(user.get("user_id"))
            wins += int(item["pairing"]["winner"] == user.get("user_id"))
    return {
        "date": today.isoformat(), "house_id": house_id,
        "rival_bouts": {"progress": min(bouts, 1), "goal": 1,
                        "complete": bouts >= 1},
        "team_turnout": {"progress": min(len(members), 3), "goal": 3,
                         "complete": len(members) >= 3},
        "rival_victories": {"progress": min(wins, 2), "goal": 2,
                            "complete": wins >= 2},
    }
