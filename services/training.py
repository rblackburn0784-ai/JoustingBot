"""v0.9.2c — the Training Yard: named, tiered NPCs and modest, journal-backed XP.

Training bouts are *real* seeded combat, but NEVER competitive challenges:
there is no gold, leaderboard credit, title farming or tournament entry.
XP is cosmetic yard mastery, derived from one immutable match history (no
separate award writes or duplicate rewards on retries).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from services.combat import Fighter
from services.records import load_history
from services.tactics import TacticPlan

TRAIN_XP_PER_BOUT = 3
TRAIN_DAILY_XP_CAP = 30
TRAIN_XP_PER_LEVEL = 30
TRAIN_COOLDOWN_SECONDS = 120
NPC_ID_BASE = -20000


@dataclass(frozen=True)
class YardOpponent:
    key: str
    name: str
    level: int
    title: str
    personality: str
    knight_stats: tuple[int, int, int, int, int, int]
    horse_name: str
    horse_stats: tuple[int, int, int, int, int]
    breed: str = "rouncey"
    lance: str = "lance_ash"
    armour: str = "armour_mail"
    barding: str = "barding_none"
    style: str = "balanced"
    target: str = "shield"

    @property
    def player_id(self) -> int:
        return NPC_ID_BASE - self.level

    @property
    def knight_map(self) -> dict[str, int]:
        return dict(zip(("strength", "control", "endurance", "agility", "resolve", "tactics"),
                        self.knight_stats))

    @property
    def horse_map(self) -> dict[str, int]:
        return dict(zip(("speed", "stamina", "power", "obedience", "courage"),
                        self.horse_stats))

    def fighter(self) -> Fighter:
        return Fighter(
            self.player_id, self.name, self.horse_name, self.knight_map, self.horse_map,
            self.lance, self.armour, self.barding, self.breed,
        )

    @property
    def tactics(self) -> TacticPlan:
        return TacticPlan(style=self.style, target=self.target)


# Four original training characters retained, expanded to 12 different levels.
# Stat values increase with tier, but strong opponents are not a reliable XP farm:
# all completed sessions award only 3 yard XP, irrespective of winning.
OPPONENTS: tuple[YardOpponent, ...] = (
    YardOpponent("osric", "Osric the Careful", 1, "Patient counter-rider",
                 "Waits for mistakes and treats every pass like a lesson.",
                 (2, 4, 2, 2, 3, 4), "Mossbell", (2, 4, 2, 4, 2),
                 lance="lance_tournament", style="cautious", target="lance"),
    YardOpponent("beren", "Beren of the Old Yard", 2, "Gruff fundamentals coach",
                 "Calls every mistake by name and makes you ride it again.",
                 (3, 3, 4, 2, 3, 2), "Candlewick", (3, 4, 3, 3, 1),
                 breed="rouncey"),
    YardOpponent("elis", "Elis Quickspur", 3, "Fast, nervy show-off",
                 "Loves speed, hates waiting, and challenges your control.",
                 (2, 3, 2, 5, 2, 3), "Silver Skirl", (5, 2, 2, 2, 3),
                 breed="palfrey", armour="armour_light"),
    YardOpponent("maud", "Dame Maud Ironhand", 4, "Direct power charger",
                 "Believes a clean hard hit solves most problems.",
                 (5, 2, 4, 1, 4, 1), "Hammerwake", (2, 3, 5, 1, 3),
                 breed="destrier", lance="lance_heavy", armour="armour_full",
                 style="aggressive", target="rider"),
    YardOpponent("tamsin", "Tamsin the Steady", 5, "Defensive seat specialist",
                 "Tests your saddle position, patience and nerve.",
                 (3, 5, 5, 3, 4, 3), "Surestep", (4, 5, 3, 6, 5),
                 breed="courser", style="cautious", target="shield"),
    YardOpponent("roland", "Roland Redspur", 6, "Aggressive veteran",
                 "Drives into contact and forces you to choose your line.",
                 (6, 4, 5, 3, 4, 3), "Ember", (5, 5, 6, 4, 5),
                 breed="charger", lance="lance_heavy", style="aggressive", target="rider"),
    YardOpponent("ysabel", "Lady Ysabel Windward", 7, "Precise long-lance rider",
                 "Finds your weakest angle and rarely gives it back.",
                 (4, 7, 5, 5, 5, 6), "Boreal", (7, 5, 4, 6, 6),
                 breed="palfrey", lance="lance_long", target="lance"),
    YardOpponent("godric", "Godric Stonewall", 8, "Armoured endurance wall",
                 "Wins by weathering impacts and outlasting overconfident riders.",
                 (7, 5, 7, 2, 7, 5), "Ironhoof", (4, 8, 7, 6, 8),
                 breed="destrier", armour="armour_full", barding="barding_steel",
                 style="cautious"),
    YardOpponent("rowena", "Rowena Blackthorn", 9, "Relentless tactician",
                 "Keeps changing her line until your discipline breaks.",
                 (6, 8, 6, 7, 6, 8), "Nightfall", (8, 7, 6, 7, 7),
                 breed="courser", lance="lance_tournament", target="lance"),
    YardOpponent("aldric", "Sir Aldric Breakspear", 10, "Fierce impact master",
                 "One poor defence can send you flying from the saddle.",
                 (8, 7, 8, 4, 8, 7), "Tempest", (7, 8, 9, 6, 8),
                 breed="charger", lance="lance_heavy", armour="armour_full",
                 style="aggressive", target="rider"),
    YardOpponent("seraphine", "Dame Seraphine Vale", 11, "Royal champion",
                 "Combines speed, restraint and ruthless accuracy.",
                 (8, 8, 8, 8, 8, 8), "Dawnstar", (9, 9, 8, 9, 9),
                 breed="palfrey", lance="lance_tournament", target="lance"),
    YardOpponent("black_knight", "The Black Knight", 12, "Legend of the old lists",
                 "A dangerous examination for even the best-trained rider.",
                 (8, 8, 8, 8, 8, 8), "Dreadmarch", (9, 10, 10, 9, 10),
                 breed="destrier", lance="lance_heavy", armour="armour_full",
                 barding="barding_steel", style="aggressive", target="rider"),
)

BY_KEY = {npc.key: npc for npc in OPPONENTS}


def opponent(key: str) -> YardOpponent | None:
    return BY_KEY.get((key or "").strip().lower())


def _datetime(value: Any) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None
        return stamp.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def earned_training(guild_id: int, user_id: int, history: dict | None = None,
                    now: datetime | None = None) -> dict:
    """Session and XP totals from completed training records, per guild.

    A match ID can award once, and at most 10 bouts/day earn XP.
    Training rank/XP are yard recognition only: never gold, power or prestige.
    """
    journal = history if history is not None else load_history()
    sessions = []
    seen = set()
    for match in journal.get("matches", []):
        if not isinstance(match, dict) or match.get("mode") != "training" \
                or match.get("guild_id") != guild_id \
                or (match.get("a") or {}).get("user_id") != user_id:
            continue
        key = str(match.get("id") or "")
        stamp = _datetime(match.get("timestamp"))
        if not key or key in seen or stamp is None:
            continue
        seen.add(key)
        sessions.append((stamp, key))
    sessions.sort()
    daily = {}
    total_xp = 0
    rewarded = {}
    for date, key in sessions:
        day = date.date().isoformat()
        count = daily.get(day, 0)
        gain = TRAIN_XP_PER_BOUT if count * TRAIN_XP_PER_BOUT < TRAIN_DAILY_XP_CAP else 0
        daily[day] = count + 1
        rewarded[key] = gain
        total_xp += gain
    today = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()
    return {
        "sessions": len(sessions), "xp": total_xp,
        "level": 1 + total_xp // TRAIN_XP_PER_LEVEL,
        "towards_next": total_xp % TRAIN_XP_PER_LEVEL,
        "today_xp": min(TRAIN_DAILY_XP_CAP, daily.get(today, 0) * TRAIN_XP_PER_BOUT),
        "awards": rewarded,
    }
