"""v0.9.1 tactical jousting. Pure immutable plans, seed-independent deterministic effects.

All adjustments are *small integer offsets*. RNG remains exclusively in combat.py.
The same plan + fighter stats + arena + seed always reproduce the same joust.
"""
from __future__ import annotations
from dataclasses import dataclass

STYLES = {
    "cautious": ("Cautious", 2, -3, 0, -4, "Safer line and mount handling; weaker impacts."),
    "balanced": ("Balanced", 0, 0, 1, 0, "No modifier; moderate fatigue."),
    "aggressive": ("Aggressive", -2, 3, 2, 5, "Harder charge, but fatigue, control and injury risks rise."),
}
TARGETS = {
    "shield": ("Shield", 0, 0, 0, "Balanced, conventional target."),
    "lance": ("Lance", 2, -2, -1, "Cleaner line, less force; broken-lance scoring."),
    "rider": ("Rider", -2, 2, 3, "Higher-impact target, poorer alignment and extra injury risk."),
}
MOVES = {
    "none": ("No Manoeuvre", 0, 0, 0, 0, 0, "No special move."),
    "precision_strike": ("Precision Strike", 3, -2, 0, 0, 2, "Steady the lance; sacrifices impact."),
    "reckless_charge": ("Reckless Charge", -3, 4, 0, 4, 2, "Extra impact, difficult control and serious risk."),
    "shield_brace": ("Shield Brace", 1, -2, 3, -2, 2, "Improves seat and defence; sacrifices momentum."),
    "feigned_miss": ("Feigned Miss", 2, -2, 0, -1, 2, "A deceptive late correction; controlled but light."),
    "last_stand": ("Last Stand", 2, 2, 0, 3, 3, "A comeback attempt from pass three, with extra fatigue."),
}
MAX_FATIGUE = 8
COOLDOWN_PASSES = 2
MAX_TACTICAL_RISK_MOD = 12


@dataclass(frozen=True)
class TacticPlan:
    style: str = "balanced"
    target: str = "shield"
    manoeuvre: str = "none"

    def __post_init__(self):
        if self.style not in STYLES or self.target not in TARGETS or self.manoeuvre not in MOVES:
            raise ValueError("Invalid jousting tactic.")

    def as_dict(self) -> dict[str, str]:
        return {"style": self.style, "target": self.target, "manoeuvre": self.manoeuvre}


@dataclass(frozen=True)
class PassTactics:
    alignment: int = 0
    charge: int = 0
    resistance: int = 0
    handling: int = 0
    injury_risk: int = 0
    fatigue_gain: int = 0
    move: str = "none"
    fatigue: int = 0


def fatigue_penalty(fatigue: int, horse_stats: dict[str, int], style: str) -> int:
    """High stamina mitigates, but cannot eliminate, accumulating fatigue."""
    stamina = int(horse_stats.get("stamina", 5))
    relief = 1 if stamina >= 8 else 0
    return max(0, (fatigue // 2) - relief)


def effects(plan: TacticPlan, *, pass_no: int, fatigue: int, horse_stats: dict[str, int],
            score_for: int = 0, score_against: int = 0) -> PassTactics:
    name, align, charge, gain, risk, _ = STYLES[plan.style]
    _, target_align, target_charge, target_risk, _ = TARGETS[plan.target]
    align += target_align
    charge += target_charge
    risk += target_risk

    # Riding recklessly with a nervous mount is a real gamble.
    courage = int(horse_stats.get("courage", 5))
    obedience = int(horse_stats.get("obedience", 5))
    handling = (1 if plan.style == "cautious" else
                -1 if plan.style == "aggressive" and min(courage, obedience) <= 6 else 0)
    if plan.style == "aggressive" and courage <= 3:
        handling -= 1

    move = "none"
    # Cooldown: after use, skip two full passes before using the move again.
    # Last Stand is only available from pass 3 and only when losing/fatigued.
    eligible = ((pass_no - 1) % (COOLDOWN_PASSES + 1) == 0)
    if plan.manoeuvre == "last_stand":
        eligible = pass_no == 3 and (score_for < score_against or fatigue >= 3)
    if plan.manoeuvre != "none" and eligible:
        move = plan.manoeuvre
        _, ma, mc, mr, mi, _cooldown, _description = MOVES[move]
        align += ma
        charge += mc
        risk += mi
        gain += 1 if move in {"reckless_charge", "last_stand"} else 0
    else:
        mr = 0
    spent = fatigue_penalty(fatigue, horse_stats, plan.style)
    return PassTactics(
        alignment=align - spent,
        charge=charge - spent,
        resistance=mr,
        handling=handling - min(2, fatigue // 4),
        injury_risk=max(-8, min(MAX_TACTICAL_RISK_MOD, risk)),
        fatigue_gain=gain,
        move=move,
        fatigue=fatigue,
    )


def advance_fatigue(fatigue: int, tactic: PassTactics) -> int:
    return min(MAX_FATIGUE, fatigue + tactic.fatigue_gain)


def label(plan: TacticPlan) -> str:
    return (f"{STYLES[plan.style][0]} · {TARGETS[plan.target][0]} · "
            f"{MOVES[plan.manoeuvre][0]}")


def target_result(category: str, points: int, target: str) -> tuple[str, int]:
    """Targeting a lance favours a single-point break over heavy shield scores."""
    if target == "lance" and category in {"heavy_shield_hit", "saddle_stagger"}:
        return "lance_break", 1
    return category, points
