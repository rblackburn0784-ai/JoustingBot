from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from services.arenas import get_arena
from services.equipment import (
    apply_horse_equipment,
    apply_knight_equipment,
    total_alignment_mod,
    total_charge_mod,
    total_impact_mult,
    total_panic_mod,
    total_slip_mod,
    total_unhorse_resist,
)


@dataclass
class Fighter:
    user_id: int
    knight_name: str
    horse_name: str

    knight_stats: Dict[str, int]
    horse_stats: Dict[str, int]

    lance_key: str
    armour_key: str
    barding_key: str


@dataclass
class PassLog:
    pass_no: int
    result: str
    points_a: int
    points_b: int
    margin: int
    notes: List[str] = field(default_factory=list)


@dataclass
class MatchResult:
    fighter_a: str
    fighter_b: str
    arena_name: str
    score_a: int
    score_b: int
    winner: str
    passes: List[PassLog]

ALIGNMENT_TARGET = 18
MISS_TARGET = 10


def d20() -> int:
    return random.randint(1, 20)


def behaviour_check(
    *,
    horse_stats: Dict[str, int],
    barding_key: str,
    arena_slip_mod: int = 0,
    arena_panic_mod: int = 0,
) -> Optional[str]:
    courage = int(horse_stats.get("courage", 0))
    obedience = int(horse_stats.get("obedience", 0))
    stamina = int(horse_stats.get("stamina", 0))

    panic_mod = total_panic_mod(barding_key) - arena_panic_mod
    slip_mod = total_slip_mod(barding_key) + arena_slip_mod

    refuse_roll = d20() + courage + obedience + panic_mod
    if refuse_roll < 10:
        return "refused"

    slip_roll = d20() + obedience + stamina - slip_mod
    if slip_roll < 9:
        return "slipped"

    bolt_roll = d20() + courage + panic_mod
    if bolt_roll < 8:
        return "bolted"

    return None


def calculate_alignment(fighter: Fighter, extra_penalty: int = 0) -> int:
    knight_stats = apply_knight_equipment(
        fighter.knight_stats,
        fighter.lance_key,
        fighter.armour_key,
    )

    horse_stats = apply_horse_equipment(
        fighter.horse_stats,
        fighter.barding_key,
    )

    base = int(knight_stats.get("control", 0)) + int(horse_stats.get("obedience", 0))
    equip_mod = total_alignment_mod(fighter.lance_key, fighter.armour_key)

    return d20() + base + equip_mod + extra_penalty


def calculate_charge(fighter: Fighter, extra_penalty: int = 0) -> int:
    knight_stats = apply_knight_equipment(
        fighter.knight_stats,
        fighter.lance_key,
        fighter.armour_key,
    )

    horse_stats = apply_horse_equipment(
        fighter.horse_stats,
        fighter.barding_key,
    )

    base = (
        int(knight_stats.get("strength", 0))
        + int(horse_stats.get("speed", 0))
        + int(horse_stats.get("power", 0))
    )

    equip_mod = total_charge_mod(
        fighter.lance_key,
        fighter.armour_key,
        fighter.barding_key,
    )

    raw = d20() + base + equip_mod + extra_penalty
    impact = total_impact_mult(fighter.lance_key, fighter.armour_key)

    return int(round(raw * impact))


def score_margin(margin: int) -> tuple[int, str]:
    if margin >= 8:
        return 3, "unhorsed"
    if margin >= 4:
        return 2, "solid hit"
    if margin >= 1:
        return 1, "lance break"

    return 0, "glancing clash"


def run_single_match(fighter_a: Fighter, fighter_b: Fighter, arena_key: str) -> MatchResult:
    arena = get_arena(arena_key)
    score_a = 0
    score_b = 0
    passes: List[PassLog] = []

    for pass_no in range(1, 6):
        notes: List[str] = []

        horse_a_effective = apply_horse_equipment(
            fighter_a.horse_stats,
            fighter_a.barding_key,
        )
        horse_b_effective = apply_horse_equipment(
            fighter_b.horse_stats,
            fighter_b.barding_key,
        )

        behaviour_a = behaviour_check(
            horse_stats=horse_a_effective,
            barding_key=fighter_a.barding_key,
            arena_slip_mod=arena.slip_mod,
            arena_panic_mod=arena.panic_mod,
        )
        behaviour_b = behaviour_check(
            horse_stats=horse_b_effective,
            barding_key=fighter_b.barding_key,
            arena_slip_mod=arena.slip_mod,
            arena_panic_mod=arena.panic_mod,
        )

        penalty_a = 0
        penalty_b = 0

        if behaviour_a == "refused" and behaviour_b != "refused":
            score_b += 1
            passes.append(
                PassLog(
                    pass_no=pass_no,
                    result="Horse refused",
                    points_a=0,
                    points_b=1,
                    margin=0,
                    notes=[f"{fighter_a.horse_name} refused the charge."],
                )
            )
            continue

        if behaviour_b == "refused" and behaviour_a != "refused":
            score_a += 1
            passes.append(
                PassLog(
                    pass_no=pass_no,
                    result="Horse refused",
                    points_a=1,
                    points_b=0,
                    margin=0,
                    notes=[f"{fighter_b.horse_name} refused the charge."],
                )
            )
            continue

        if behaviour_a == "refused" and behaviour_b == "refused":
            passes.append(
                PassLog(
                    pass_no=pass_no,
                    result="Both horses refused",
                    points_a=0,
                    points_b=0,
                    margin=0,
                    notes=[
                        f"{fighter_a.horse_name} and {fighter_b.horse_name} both refused."
                    ],
                )
            )
            continue

        if behaviour_a == "slipped":
            penalty_a -= 4
            notes.append(f"{fighter_a.horse_name} slipped and lost momentum.")

        if behaviour_b == "slipped":
            penalty_b -= 4
            notes.append(f"{fighter_b.horse_name} slipped and lost momentum.")

        penalty_a += arena.alignment_mod
        penalty_b += arena.alignment_mod

        if behaviour_a == "bolted":
            penalty_a -= 5
            notes.append(f"{fighter_a.horse_name} bolted under pressure.")

        if behaviour_b == "bolted":
            penalty_b -= 5
            notes.append(f"{fighter_b.horse_name} bolted under pressure.")

        align_a = calculate_alignment(fighter_a, extra_penalty=penalty_a)
        align_b = calculate_alignment(fighter_b, extra_penalty=penalty_b)

        if align_a < MISS_TARGET and align_b < MISS_TARGET:
            passes.append(
                PassLog(
                    pass_no=pass_no,
                    result="Double miss",
                    points_a=0,
                    points_b=0,
                    margin=0,
                    notes=notes + ["Both riders missed their line."],
                )
            )
            continue

        if align_a < ALIGNMENT_TARGET:
            penalty_a -= 3
            notes.append(f"{fighter_a.knight_name} had a poor line.")

        if align_b < ALIGNMENT_TARGET:
            penalty_b -= 3
            notes.append(f"{fighter_b.knight_name} had a poor line.")

        charge_a = int(
            round(calculate_charge(fighter_a, extra_penalty=penalty_a + arena.charge_mod) * arena.impact_mult))
        charge_b = int(
            round(calculate_charge(fighter_b, extra_penalty=penalty_b + arena.charge_mod) * arena.impact_mult))

        resist_a = total_unhorse_resist(fighter_a.armour_key)
        resist_b = total_unhorse_resist(fighter_b.armour_key)

        margin = charge_a - charge_b

        if margin > 0:
            adjusted_margin = max(0, margin - resist_b)
            points, result = score_margin(adjusted_margin)
            score_a += points

            passes.append(
                PassLog(
                    pass_no=pass_no,
                    result=f"{fighter_a.knight_name}: {result}",
                    points_a=points,
                    points_b=0,
                    margin=adjusted_margin,
                    notes=notes,
                )
            )

        elif margin < 0:
            adjusted_margin = max(0, abs(margin) - resist_a)
            points, result = score_margin(adjusted_margin)
            score_b += points

            passes.append(
                PassLog(
                    pass_no=pass_no,
                    result=f"{fighter_b.knight_name}: {result}",
                    points_a=0,
                    points_b=points,
                    margin=adjusted_margin,
                    notes=notes,
                )
            )

        else:
            passes.append(
                PassLog(
                    pass_no=pass_no,
                    result="Even clash",
                    points_a=0,
                    points_b=0,
                    margin=0,
                    notes=notes + ["Both riders met with equal force."],
                )
            )

        if score_a >= 3 or score_b >= 3:
            break

    if score_a > score_b:
        winner = fighter_a.knight_name
    elif score_b > score_a:
        winner = fighter_b.knight_name
    else:
        winner = "Draw"

    return MatchResult(
        fighter_a=fighter_a.knight_name,
        fighter_b=fighter_b.knight_name,
        arena_name=arena.name,
        score_a=score_a,
        score_b=score_b,
        winner=winner,
        passes=passes,
    )