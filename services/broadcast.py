"""JoustingBot v0.9.2: pure, deterministic matchday broadcast plan.

Presentation NEVER rolls RNG, re-simulates combat, pays rewards or writes history.
All scenes derive from the single authoritative MatchResult.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.balance import PASSES_PER_MATCH

STAGES = ("approach", "charge", "impact", "aftermath")
PHASE_ICONS = {"approach": "🏇", "charge": "💨", "impact": "💥", "aftermath": "🏁"}
PHASE_COLORS = {
    "approach": 0x416174, "charge": 0xB47A32,
    "impact": 0xA43E3B, "aftermath": 0x46775E,
}
IMPACT_LINES = {
    "clean_miss": "Both lances sweep through empty air. The crowd groans.",
    "shield_scrape": "A lance skims the shield. The marshals dismiss the glancing blow.",
    "lance_break": "Timber cracks across the lists. Splinters scatter in the dust.",
    "heavy_shield_hit": "A tremendous shield strike echoes through the stands.",
    "saddle_stagger": "A knight nearly loses the saddle as armour and leather shudder.",
    "unhorsing": "An armoured rider is torn from the saddle. The stands erupt!",
    "horse_refusal": "The mount refuses the line. The marshal awards the pass.",
    "horse_slip": "Hooves slide on the treacherous ground. The charge falls apart.",
    "double_clash": "Both riders collide with matching force. Neither claims the edge.",
}


@dataclass(frozen=True)
class BroadcastFrame:
    pass_no: int
    phase: str
    title: str
    commentary: str
    score_a: int
    score_b: int
    progress: int
    total: int
    category: str = ""

    @property
    def key(self) -> str:
        return f"{self.pass_no}:{self.phase}"


def _knight_tactics(pass_log: Any, side: str) -> dict:
    data = getattr(pass_log, "tactics_" + side, None)
    return data if isinstance(data, dict) else {}


def make_frames(result: Any, *, arena_key: str) -> list[BroadcastFrame]:
    """Create four truthful stages per unique pass, without revealing future outcomes.

    APPROACH/CHARGE must never mention result, points or the winning rider.
    IMPACT can announce the outcome, AFTERMATH can show the updated score.
    """
    passes = getattr(result, "passes", []) or []
    unique = set()
    frames: list[BroadcastFrame] = []
    a_score = b_score = 0
    # Never reveal a shortened match before its outcome.
    total = PASSES_PER_MATCH
    for p in passes:
        no = int(p.pass_no)
        if no in unique:
            raise ValueError("Duplicate pass in combat result: cannot broadcast safely.")
        unique.add(no)
        ta, tb = _knight_tactics(p, "a"), _knight_tactics(p, "b")
        a_style = str(ta.get("style", "balanced")).title()
        b_style = str(tb.get("style", "balanced")).title()
        a_target = str(ta.get("target", "shield")).title()
        b_target = str(tb.get("target", "shield")).title()
        a_move, b_move = ta.get("move", "none"), tb.get("move", "none")
        a_fatigue, b_fatigue = int(ta.get("fatigue", 0)), int(tb.get("fatigue", 0))
        setting = {
            "royal_lists": "Banners rise above the pristine tournament rail.",
            "muddy_field": "Wet clods fly beneath the pounding hooves.",
            "frozen_ground": "Iron shoes ring against frozen earth.",
            "wind_swept": "A crosswind snaps at the lowered lances.",
            "festival_arena": "The festival drums shake the wooden stands.",
            "war_torn": "Dust swirls over the battered battlefield.",
        }.get(arena_key, "The crowd rises as the knights prepare.")
        approach = (
            f"{setting} {result.fighter_a} takes a {a_style.lower()} pace; "
            f"{result.fighter_b} a {b_style.lower()} line. "
            f"The marshals prepare pass {no}."
        )
        charge = (
            f"{result.fighter_a} lowers the lance towards the {a_target.lower()}; "
            f"{result.fighter_b} sights the {b_target.lower()}. "
            f"Fatigue: {a_fatigue} / {b_fatigue}."
        )
        moves = []
        if a_move not in (None, "none"):
            moves.append(f"{result.fighter_a}: {str(a_move).replace('_', ' ').title()}")
        if b_move not in (None, "none"):
            moves.append(f"{result.fighter_b}: {str(b_move).replace('_', ' ').title()}")
        if moves:
            charge += " Tactical manoeuvres: " + "; ".join(moves) + "."
        impact = str(getattr(p, "result", "") or "Impact at the rail.") + ". " + IMPACT_LINES.get(
            p.category, "The marshals judge a hard-fought pass."
        )
        gear = str(getattr(p, "gear_line", "") or "")
        if gear and gear != "Gear, nerve and footing all play their part in the pass.":
            impact += " " + gear
        a_score += int(p.points_a)
        b_score += int(p.points_b)
        commentary = (
            f"Marshal's ruling: {int(p.points_a):+d} to {result.fighter_a}, "
            f"{int(p.points_b):+d} to {result.fighter_b}. "
            f"The running score is {a_score}–{b_score}. "
            f"{str(getattr(p, 'arena_line', '') or '')}"
        )
        stages = (
            ("approach", approach), ("charge", charge),
            ("impact", impact), ("aftermath", commentary),
        )
        for phase, line in stages:
            frames.append(BroadcastFrame(
                pass_no=no, phase=phase,
                title=f"{PHASE_ICONS[phase]} Pass {no} — {phase.title()}",
                commentary=line[:1000], score_a=a_score if phase == "aftermath" else a_score - int(p.points_a),
                score_b=b_score if phase == "aftermath" else b_score - int(p.points_b),
                progress=no, total=total,
                category=p.category if phase in ("impact", "aftermath") else "",
            ))
    if (a_score, b_score) != (result.score_a, result.score_b):
        raise ValueError("Broadcast score does not match the saved combat result.")
    return frames


def statistics(result: Any) -> dict[str, dict[str, int]]:
    """Readable match statistics without changing gameplay or persistence."""
    stats = {
        "a": {"lance_breaks": 0, "unhorsings": 0, "heavy_hits": 0, "penalties": 0, "points": int(result.score_a)},
        "b": {"lance_breaks": 0, "unhorsings": 0, "heavy_hits": 0, "penalties": 0, "points": int(result.score_b)},
    }
    for p in result.passes:
        for side, other in (("a", "b"), ("b", "a")):
            awarded = int(getattr(p, "points_" + side, 0)) > 0
            if not awarded:
                continue
            if p.category == "lance_break":
                stats[side]["lance_breaks"] += 1
            elif p.category == "unhorsing":
                stats[side]["unhorsings"] += 1
            elif p.category in {"heavy_shield_hit", "saddle_stagger"}:
                stats[side]["heavy_hits"] += 1
            elif p.category in {"horse_refusal", "horse_slip"}:
                stats[other]["penalties"] += 1
    return stats



def entrance_commentary(prepared: Any) -> str:
    """Pre-match narrative with no simulated result or hidden mechanics."""
    return (
        f"🎺 **West gate:** {prepared.knight_a.name} rides in on {prepared.horse_a.name}. "
        f"The first banners rise in salute.\n"
        f"🎺 **East gate:** {prepared.knight_b.name} follows on {prepared.horse_b.name}, "
        f"turning towards the opposite rail.\n"
        "The marshals signal the lists are ready. No champion has yet been decided."
    )
