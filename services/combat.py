from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from services.arenas import get_arena
from services.balance import (
    ALIGNMENT_TARGET,
    BOLT_ALIGNMENT_PENALTY,
    BOLT_TARGET,
    HEAVY_SHIELD_HIT_MARGIN,
    LANCE_BREAK_MARGIN,
    MISS_TARGET,
    PASSES_PER_MATCH,
    POOR_LINE_CHARGE_PENALTY,
    REFUSAL_POINT_AWARD,
    REFUSAL_TARGET,
    SADDLE_STAGGER_MARGIN,
    SHIELD_SCRAPE_MARGIN,
    SLIP_ALIGNMENT_PENALTY,
    SLIP_POINT_AWARD,
    SLIP_TARGET,
    UNHORSING_MARGIN,
    WINNING_SCORE,
)
from services.tactics import TacticPlan, effects, advance_fatigue, target_result
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
    category: str
    points_a: int
    points_b: int
    margin: int
    notes: List[str] = field(default_factory=list)
    arena_line: str = ""
    gear_line: str = ""
    debug_rolls: List[str] = field(default_factory=list)
    tactics_a: dict = field(default_factory=dict)
    tactics_b: dict = field(default_factory=dict)


@dataclass
class MatchResult:
    fighter_a: str
    fighter_b: str
    arena_name: str
    score_a: int
    score_b: int
    winner: str
    passes: List[PassLog]
    seed: int
    tactics_a: TacticPlan = field(default_factory=TacticPlan)
    tactics_b: TacticPlan = field(default_factory=TacticPlan)


def d20(rng: random.Random) -> int:
    return rng.randint(1, 20)


def arena_pass_line(arena_key: str, pass_no: int) -> str:
    lines = {
        "royal_lists": [
            "The royal lists give both riders a clean, honest run.",
            "The crowd leans in as the lances lower on the straight rail.",
        ],
        "muddy_field": [
            "Mud drags at every hoofbeat and threatens to steal momentum.",
            "The ground spits wet earth as the horses fight for purchase.",
        ],
        "frozen_ground": [
            "Hooves hammer the frozen ground with dangerous speed.",
            "The icy track promises a brutal impact or a sudden fall.",
        ],
        "wind_swept": [
            "Wind claws at the lance tips and tests every correction.",
            "A hard gust crosses the lists just as the riders commit.",
        ],
        "festival_arena": [
            "The festival crowd roars loud enough to unsettle even trained mounts.",
            "Banners snap and drums beat as the riders thunder forward.",
        ],
        "war_torn": [
            "Broken earth and old scars make the charge ugly and unforgiving.",
            "The battlefield lists turn every stride into a gamble.",
        ],
    }
    options = lines.get(arena_key, ["The arena shapes the charge as the riders close the distance."])
    return options[(pass_no - 1) % len(options)]


def gear_pass_line(fighter: Fighter, category: str) -> str:
    lance = fighter.lance_key
    armour = fighter.armour_key
    barding = fighter.barding_key

    if category in {"unhorsing", "saddle_stagger", "heavy_shield_hit"}:
        if lance == "lance_heavy":
            return f"{fighter.knight_name}'s heavy lance turns the pass into a violent collision."
        if lance == "lance_tournament":
            return f"{fighter.knight_name}'s tournament lance finds a cleaner line than its light frame suggests."
        if lance == "lance_long":
            return f"{fighter.knight_name} uses the long reach to touch first and disrupt the opposing seat."

    if category in {"clean_miss", "shield_scrape"}:
        if armour == "armour_reinforced_helm":
            return f"The reinforced helm protects {fighter.knight_name}, but the narrow sightline makes the aim suffer."
        if armour == "armour_full":
            return f"Full plate keeps {fighter.knight_name} steady, though the weight slows the correction."

    if category in {"horse_refusal", "horse_slip"}:
        if barding == "barding_steel":
            return f"Steel barding protects {fighter.horse_name}, but the extra weight punishes the footing."
        if barding == "barding_spiked":
            return f"The spiked barding looks fearsome, but {fighter.horse_name} fights the awkward balance."
        if barding == "barding_leather":
            return f"Leather barding helps settle {fighter.horse_name}, though the pressure still tells."

    return "Gear, nerve and footing all play their part in the pass."


def outcome_from_margin(margin: int) -> tuple[int, str, str]:
    if margin >= UNHORSING_MARGIN:
        return 3, "unhorsing", "unhorsing"
    if margin >= SADDLE_STAGGER_MARGIN:
        return 2, "saddle_stagger", "saddle stagger"
    if margin >= HEAVY_SHIELD_HIT_MARGIN:
        return 2, "heavy_shield_hit", "heavy shield hit"
    if margin >= LANCE_BREAK_MARGIN:
        return 1, "lance_break", "lance break"
    if margin >= SHIELD_SCRAPE_MARGIN:
        return 0, "shield_scrape", "shield scrape"

    return 0, "double_clash", "glancing clash"


def behaviour_check(
    *,
    rng: random.Random,
    horse_stats: Dict[str, int],
    barding_key: str,
    arena_slip_mod: int = 0,
    arena_panic_mod: int = 0,
    handling: int = 0,
) -> tuple[Optional[str], List[str]]:
    courage = int(horse_stats.get("courage", 0))
    obedience = int(horse_stats.get("obedience", 0))
    stamina = int(horse_stats.get("stamina", 0))

    panic_mod = total_panic_mod(barding_key) - arena_panic_mod
    slip_mod = total_slip_mod(barding_key) + arena_slip_mod

    debug: List[str] = []

    refuse_d20 = d20(rng)
    refuse_total = refuse_d20 + courage + obedience + panic_mod + handling
    debug.append(
        f"refusal: d20 {refuse_d20} + courage {courage} + obedience {obedience} + panic_mod {panic_mod} = {refuse_total} vs {REFUSAL_TARGET}"
    )
    if refuse_total < REFUSAL_TARGET:
        return "refused", debug

    slip_d20 = d20(rng)
    slip_total = slip_d20 + obedience + stamina - slip_mod + handling
    debug.append(
        f"slip: d20 {slip_d20} + obedience {obedience} + stamina {stamina} - slip_mod {slip_mod} = {slip_total} vs {SLIP_TARGET}"
    )
    if slip_total < SLIP_TARGET:
        return "slipped", debug

    bolt_d20 = d20(rng)
    bolt_total = bolt_d20 + courage + panic_mod + handling
    debug.append(f"bolt: d20 {bolt_d20} + courage {courage} + panic_mod {panic_mod} = {bolt_total} vs {BOLT_TARGET}")
    if bolt_total < BOLT_TARGET:
        return "bolted", debug

    return None, debug


def calculate_alignment(fighter: Fighter, *, rng: random.Random, extra_penalty: int = 0) -> tuple[int, str]:
    knight_stats = apply_knight_equipment(
        fighter.knight_stats,
        fighter.lance_key,
        fighter.armour_key,
    )

    horse_stats = apply_horse_equipment(
        fighter.horse_stats,
        fighter.barding_key,
    )

    control = int(knight_stats.get("control", 0))
    obedience = int(horse_stats.get("obedience", 0))
    equip_mod = total_alignment_mod(fighter.lance_key, fighter.armour_key)
    roll = d20(rng)
    total = roll + control + obedience + equip_mod + extra_penalty
    debug = (
        f"alignment {fighter.knight_name}: d20 {roll} + control {control} + obedience {obedience} "
        f"+ equip {equip_mod} + penalty {extra_penalty} = {total}"
    )
    return total, debug


def calculate_charge(fighter: Fighter, *, rng: random.Random, extra_penalty: int = 0) -> tuple[int, str]:
    knight_stats = apply_knight_equipment(
        fighter.knight_stats,
        fighter.lance_key,
        fighter.armour_key,
    )

    horse_stats = apply_horse_equipment(
        fighter.horse_stats,
        fighter.barding_key,
    )

    strength = int(knight_stats.get("strength", 0))
    speed = int(horse_stats.get("speed", 0))
    power = int(horse_stats.get("power", 0))
    equip_mod = total_charge_mod(
        fighter.lance_key,
        fighter.armour_key,
        fighter.barding_key,
    )
    impact = total_impact_mult(fighter.lance_key, fighter.armour_key)
    roll = d20(rng)
    raw = roll + strength + speed + power + equip_mod + extra_penalty
    total = int(round(raw * impact))
    debug = (
        f"charge {fighter.knight_name}: (d20 {roll} + strength {strength} + speed {speed} + power {power} "
        f"+ equip {equip_mod} + penalty {extra_penalty}) x impact {impact:.2f} = {total}"
    )
    return total, debug


def make_pass(
    *,
    pass_no: int,
    result: str,
    category: str,
    points_a: int,
    points_b: int,
    margin: int,
    notes: Optional[List[str]] = None,
    arena_key: str,
    gear_fighter: Optional[Fighter] = None,
    debug_rolls: Optional[List[str]] = None,
) -> PassLog:
    return PassLog(
        pass_no=pass_no,
        result=result,
        category=category,
        points_a=points_a,
        points_b=points_b,
        margin=margin,
        notes=notes or [],
        arena_line=arena_pass_line(arena_key, pass_no),
        gear_line=gear_pass_line(gear_fighter, category) if gear_fighter else "Gear, nerve and footing all play their part in the pass.",
        debug_rolls=debug_rolls or [],
    )


def run_single_match(fighter_a: Fighter, fighter_b: Fighter, arena_key: str, seed: Optional[int] = None,
                     tactics_a: TacticPlan | None = None, tactics_b: TacticPlan | None = None) -> MatchResult:
    arena = get_arena(arena_key)
    seed_value = int(seed if seed is not None else random.randint(1, 2_147_483_647))
    rng = random.Random(seed_value)

    score_a = 0
    score_b = 0
    passes: List[PassLog] = []
    tactics_a = tactics_a or TacticPlan()
    tactics_b = tactics_b or TacticPlan()
    fatigue_a = fatigue_b = 0
    tactical_snapshots = {}

    for pass_no in range(1, PASSES_PER_MATCH + 1):
        a_fx = effects(tactics_a, pass_no=pass_no, fatigue=fatigue_a,
                       horse_stats=fighter_a.horse_stats, score_for=score_a, score_against=score_b)
        b_fx = effects(tactics_b, pass_no=pass_no, fatigue=fatigue_b,
                       horse_stats=fighter_b.horse_stats, score_for=score_b, score_against=score_a)
        tactical_snapshots[pass_no] = (a_fx, b_fx)
        fatigue_a = advance_fatigue(fatigue_a, a_fx)
        fatigue_b = advance_fatigue(fatigue_b, b_fx)
        notes: List[str] = []
        debug_rolls: List[str] = [f"seed: {seed_value}"]

        horse_a_effective = apply_horse_equipment(
            fighter_a.horse_stats,
            fighter_a.barding_key,
        )
        horse_b_effective = apply_horse_equipment(
            fighter_b.horse_stats,
            fighter_b.barding_key,
        )

        behaviour_a, behaviour_debug_a = behaviour_check(
            rng=rng,
            horse_stats=horse_a_effective,
            barding_key=fighter_a.barding_key,
            arena_slip_mod=arena.slip_mod,
            arena_panic_mod=arena.panic_mod,
            handling=a_fx.handling,
        )
        behaviour_b, behaviour_debug_b = behaviour_check(
            rng=rng,
            horse_stats=horse_b_effective,
            barding_key=fighter_b.barding_key,
            arena_slip_mod=arena.slip_mod,
            arena_panic_mod=arena.panic_mod,
            handling=b_fx.handling,
        )
        debug_rolls.extend([f"{fighter_a.horse_name} {line}" for line in behaviour_debug_a])
        debug_rolls.extend([f"{fighter_b.horse_name} {line}" for line in behaviour_debug_b])

        if behaviour_a == "refused" and behaviour_b != "refused":
            score_b += REFUSAL_POINT_AWARD
            passes.append(
                make_pass(
                    pass_no=pass_no,
                    result=f"{fighter_a.horse_name}: horse refusal",
                    category="horse_refusal",
                    points_a=0,
                    points_b=REFUSAL_POINT_AWARD,
                    margin=0,
                    notes=[f"{fighter_a.horse_name} refuses the charge and {fighter_b.knight_name} is awarded the pass."],
                    arena_key=arena_key,
                    gear_fighter=fighter_a,
                    debug_rolls=debug_rolls,
                )
            )
            continue

        if behaviour_b == "refused" and behaviour_a != "refused":
            score_a += REFUSAL_POINT_AWARD
            passes.append(
                make_pass(
                    pass_no=pass_no,
                    result=f"{fighter_b.horse_name}: horse refusal",
                    category="horse_refusal",
                    points_a=REFUSAL_POINT_AWARD,
                    points_b=0,
                    margin=0,
                    notes=[f"{fighter_b.horse_name} refuses the charge and {fighter_a.knight_name} is awarded the pass."],
                    arena_key=arena_key,
                    gear_fighter=fighter_b,
                    debug_rolls=debug_rolls,
                )
            )
            continue

        if behaviour_a == "refused" and behaviour_b == "refused":
            passes.append(
                make_pass(
                    pass_no=pass_no,
                    result="Both horses refused",
                    category="horse_refusal",
                    points_a=0,
                    points_b=0,
                    margin=0,
                    notes=[f"{fighter_a.horse_name} and {fighter_b.horse_name} both refuse the charge."],
                    arena_key=arena_key,
                    debug_rolls=debug_rolls,
                )
            )
            continue

        if behaviour_a == "slipped" and behaviour_b != "slipped":
            score_b += SLIP_POINT_AWARD
            passes.append(
                make_pass(
                    pass_no=pass_no,
                    result=f"{fighter_a.horse_name}: horse slip",
                    category="horse_slip",
                    points_a=0,
                    points_b=SLIP_POINT_AWARD,
                    margin=0,
                    notes=[f"{fighter_a.horse_name} loses footing before the strike can properly form."],
                    arena_key=arena_key,
                    gear_fighter=fighter_a,
                    debug_rolls=debug_rolls,
                )
            )
            continue

        if behaviour_b == "slipped" and behaviour_a != "slipped":
            score_a += SLIP_POINT_AWARD
            passes.append(
                make_pass(
                    pass_no=pass_no,
                    result=f"{fighter_b.horse_name}: horse slip",
                    category="horse_slip",
                    points_a=SLIP_POINT_AWARD,
                    points_b=0,
                    margin=0,
                    notes=[f"{fighter_b.horse_name} loses footing before the strike can properly form."],
                    arena_key=arena_key,
                    gear_fighter=fighter_b,
                    debug_rolls=debug_rolls,
                )
            )
            continue

        penalty_a = arena.alignment_mod + a_fx.alignment
        penalty_b = arena.alignment_mod + b_fx.alignment
        # The Feigned Miss counters an overcommitted aggressive rider.
        # Precision Strike remains better against other riding styles.
        if a_fx.move == "feigned_miss" and tactics_b.style == "aggressive":
            penalty_b -= 2
            notes.append(f"{fighter_a.knight_name}'s feint draws {fighter_b.knight_name} off-line.")
        if b_fx.move == "feigned_miss" and tactics_a.style == "aggressive":
            penalty_a -= 2
            notes.append(f"{fighter_b.knight_name}'s feint draws {fighter_a.knight_name} off-line.")

        if behaviour_a == "slipped":
            penalty_a += SLIP_ALIGNMENT_PENALTY
            notes.append(f"{fighter_a.horse_name} slips and loses momentum.")
        if behaviour_b == "slipped":
            penalty_b += SLIP_ALIGNMENT_PENALTY
            notes.append(f"{fighter_b.horse_name} slips and loses momentum.")
        if behaviour_a == "bolted":
            penalty_a += BOLT_ALIGNMENT_PENALTY
            notes.append(f"{fighter_a.horse_name} bolts under pressure.")
        if behaviour_b == "bolted":
            penalty_b += BOLT_ALIGNMENT_PENALTY
            notes.append(f"{fighter_b.horse_name} bolts under pressure.")

        align_a, align_debug_a = calculate_alignment(fighter_a, rng=rng, extra_penalty=penalty_a)
        align_b, align_debug_b = calculate_alignment(fighter_b, rng=rng, extra_penalty=penalty_b)
        debug_rolls.extend([align_debug_a, align_debug_b])

        if align_a < MISS_TARGET and align_b < MISS_TARGET:
            passes.append(
                make_pass(
                    pass_no=pass_no,
                    result="Clean miss from both riders",
                    category="clean_miss",
                    points_a=0,
                    points_b=0,
                    margin=0,
                    notes=notes + ["Both riders miss their lines and thunder past without a scoring strike."],
                    arena_key=arena_key,
                    debug_rolls=debug_rolls,
                )
            )
            continue

        charge_penalty_a = arena.charge_mod + a_fx.charge
        charge_penalty_b = arena.charge_mod + b_fx.charge
        if behaviour_a == "bolted":
            charge_penalty_a += BOLT_ALIGNMENT_PENALTY
        elif behaviour_a == "slipped":
            charge_penalty_a += SLIP_ALIGNMENT_PENALTY
        if behaviour_b == "bolted":
            charge_penalty_b += BOLT_ALIGNMENT_PENALTY
        elif behaviour_b == "slipped":
            charge_penalty_b += SLIP_ALIGNMENT_PENALTY

        if align_a < ALIGNMENT_TARGET:
            charge_penalty_a += POOR_LINE_CHARGE_PENALTY
            notes.append(f"{fighter_a.knight_name} has a poor line into contact.")
        if align_b < ALIGNMENT_TARGET:
            charge_penalty_b += POOR_LINE_CHARGE_PENALTY
            notes.append(f"{fighter_b.knight_name} has a poor line into contact.")

        charge_a, charge_debug_a = calculate_charge(fighter_a, rng=rng, extra_penalty=charge_penalty_a)
        charge_b, charge_debug_b = calculate_charge(fighter_b, rng=rng, extra_penalty=charge_penalty_b)
        charge_a = int(round(charge_a * arena.impact_mult))
        charge_b = int(round(charge_b * arena.impact_mult))
        debug_rolls.extend(
            [
                charge_debug_a + f"; arena impact x{arena.impact_mult:.2f} => {charge_a}",
                charge_debug_b + f"; arena impact x{arena.impact_mult:.2f} => {charge_b}",
            ]
        )

        resist_a = total_unhorse_resist(fighter_a.armour_key) + a_fx.resistance
        resist_b = total_unhorse_resist(fighter_b.armour_key) + b_fx.resistance
        margin = charge_a - charge_b
        debug_rolls.append(f"raw margin: {charge_a} - {charge_b} = {margin}; resist A {resist_a}; resist B {resist_b}")

        if margin > 0:
            adjusted_margin = max(0, margin - resist_b)
            points, category, label = outcome_from_margin(adjusted_margin)
            category, points = target_result(category, points, tactics_a.target)
            label = category.replace('_', ' ')
            score_a += points
            passes.append(
                make_pass(
                    pass_no=pass_no,
                    result=f"{fighter_a.knight_name}: {label}",
                    category=category,
                    points_a=points,
                    points_b=0,
                    margin=adjusted_margin,
                    notes=notes,
                    arena_key=arena_key,
                    gear_fighter=fighter_a,
                    debug_rolls=debug_rolls + [f"adjusted margin after defender resist: {adjusted_margin}"],
                )
            )
        elif margin < 0:
            adjusted_margin = max(0, abs(margin) - resist_a)
            points, category, label = outcome_from_margin(adjusted_margin)
            category, points = target_result(category, points, tactics_b.target)
            label = category.replace('_', ' ')
            score_b += points
            passes.append(
                make_pass(
                    pass_no=pass_no,
                    result=f"{fighter_b.knight_name}: {label}",
                    category=category,
                    points_a=0,
                    points_b=points,
                    margin=adjusted_margin,
                    notes=notes,
                    arena_key=arena_key,
                    gear_fighter=fighter_b,
                    debug_rolls=debug_rolls + [f"adjusted margin after defender resist: {adjusted_margin}"],
                )
            )
        else:
            passes.append(
                make_pass(
                    pass_no=pass_no,
                    result="Double clash",
                    category="double_clash",
                    points_a=0,
                    points_b=0,
                    margin=0,
                    notes=notes + ["Both riders meet with equal force and neither gains the scoring edge."],
                    arena_key=arena_key,
                    debug_rolls=debug_rolls,
                )
            )

        if score_a >= WINNING_SCORE or score_b >= WINNING_SCORE:
            break

    for log in passes:
        aa, bb = tactical_snapshots[log.pass_no]
        log.tactics_a = {**aa.__dict__, **tactics_a.as_dict()}
        log.tactics_b = {**bb.__dict__, **tactics_b.as_dict()}
        for knight, plan, detail in ((fighter_a.knight_name, tactics_a, aa),
                                     (fighter_b.knight_name, tactics_b, bb)):
            log.notes.append(
                f"{knight}: {plan.style.title()} / {plan.target.title()} "
                f"(fatigue {detail.fatigue})"
                + (f" · {detail.move.replace('_',' ').title()}" if detail.move != "none" else "")
            )
            log.debug_rolls.append(
                f"{knight} tactical align {detail.alignment} charge {detail.charge} "
                f"resist {detail.resistance} handling {detail.handling} risk {detail.injury_risk:+}pp"
            )

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
        seed=seed_value,
        tactics_a=tactics_a,
        tactics_b=tactics_b,
    )
