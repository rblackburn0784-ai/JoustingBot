"""v0.9.1 tactical jousting. Pure immutable plans, seed-independent deterministic effects.

All adjustments are *small integer offsets*. RNG remains exclusively in combat.py.
The same plan + fighter stats + arena + seed always reproduce the same joust.
"""
from __future__ import annotations
from dataclasses import dataclass

STYLES = {
    "cautious": ("Cautious", 2, -1, 0, -4, "Safer line and mount handling; weaker impacts."),
    "balanced": ("Balanced", 0, 0, 1, 0, "No modifier; moderate fatigue."),
    "aggressive": ("Aggressive", -3, 2, 3, 5, "Harder charge, but fatigue, control and injury risks rise."),
}
TARGETS = {
    "shield": ("Shield", 0, 0, 0, "Balanced, conventional target."),
    "lance": ("Lance", 2, -1, -1, "Cleaner line, less force; broken-lance scoring."),
    "rider": ("Rider", -2, 1, 3, "Higher-impact target, poorer alignment and extra injury risk."),
}
MOVES = {
    "none": ("No Manoeuvre", 0, 0, 0, 0, 0, "No special move."),
    "precision_strike": ("Precision Strike", 3, -1, 0, 0, 2, "Steady the lance; sacrifices impact."),
    "reckless_charge": ("Reckless Charge", -3, 2, 0, 4, 2, "Extra impact, difficult control and serious risk."),
    "shield_brace": ("Shield Brace", 1, -1, 3, -2, 2, "Improves seat and defence; sacrifices momentum."),
    "feigned_miss": ("Feigned Miss", 2, -1, 0, -1, 2, "Disrupts an aggressive opponent by -2 alignment while active; light impact."),
    "last_stand": ("Last Stand", 2, 2, 0, 3, 3, "A comeback attempt from pass three, with extra fatigue."),
}
MAX_FATIGUE = 8
COOLDOWN_PASSES = 2
MAX_TACTICAL_RISK_MOD = 12

# v2.9.6: neutral defaults retain earlier seed/replay and scoring behaviour.
# (display name, description, alignment, charge, defence, handling, fatigue, injury risk)
GUARDS = {
    "square": ("Square Guard", "Balanced shield coverage; no modifier.", 0, 0, 0, 0, 0, 0),
    "high": ("High Guard", "Covers the rider against high strikes; gives up low coverage.", -1, 0, 1, 0, 0, 0),
    "low": ("Low Guard", "Protects the lance line; exposes the upper seat.", 1, 0, 0, 0, 0, 0),
}
CHARGE_INTENSITIES = {
    "balanced": ("Balanced Charge", "Even momentum and control.", 0, 0, 0, 0, 0, 0),
    "measured": ("Measured Charge", "Cleaner line, moderately less impact.", 2, -1, 0, 1, 0, -1),
    "full": ("Full Charge", "Greater impact with mounting fatigue and handling risk.", -2, 2, 0, -1, 1, 2),
}
LANCE_CONTROLS = {
    "balanced": ("Balanced Lance", "Familiar balance of precision and force.", 0, 0, 0, 0, 0, 0),
    "precise": ("Precision Grip", "Steadier tip but weaker impact.", 2, -1, 0, 0, 0, 0),
    "forceful": ("Driving Grip", "More power, harder to place the tip.", -2, 2, 0, 0, 0, 1),
}


def advanced_active(*plans: "TacticPlan") -> bool:
    """Keep legacy matches numerically unchanged with default advanced choices."""
    return any((p.shield_guard, p.charge_intensity, p.lance_control)
               != ("square", "balanced", "balanced") for p in plans)


def counterplay(attacker: "TacticPlan", defender: "TacticPlan",
                defender_wear: int = 0) -> tuple[int, int, int, str]:
    """Return alignment, charge and defender-resistance adjustments.

    High guard answers a rider-target charge; low guard answers lance hunting.
    Wear weakens a previously battered shield, without altering its inventory.
    """
    if attacker.target == "rider" and defender.shield_guard == "high":
        resist = max(0, 2 - min(2, max(0, defender_wear)))
        # A high guard is especially effective against an all-out high strike,
        # but loses effectiveness as the shield absorbs hits.
        penalty = -3 if attacker.charge_intensity == "full" else -2
        return (0, penalty, resist, "High shield guard smothers the rider-target charge.")
    if attacker.target == "lance" and defender.shield_guard == "low":
        resist = max(0, 1 - min(1, max(0, defender_wear)))
        return (-2, 0, resist, "Low shield guard frustrates the lance attack.")
    if attacker.target == "rider" and defender.shield_guard == "low":
        return (1, 1, -1, "The low shield guard exposes the high strike.")
    return 0, 0, 0, ""



@dataclass(frozen=True)
class TacticPlan:
    style: str = "balanced"
    target: str = "shield"
    manoeuvre: str = "none"
    shield_guard: str = "square"
    charge_intensity: str = "balanced"
    lance_control: str = "balanced"

    def __post_init__(self):
        if (self.style not in STYLES or self.target not in TARGETS
                or self.manoeuvre not in MOVES or self.shield_guard not in GUARDS
                or self.charge_intensity not in CHARGE_INTENSITIES
                or self.lance_control not in LANCE_CONTROLS):
            raise ValueError("Invalid jousting tactic.")

    def as_dict(self) -> dict[str, str]:
        return {
            "style": self.style, "target": self.target, "manoeuvre": self.manoeuvre,
            "shield_guard": self.shield_guard,
            "charge_intensity": self.charge_intensity,
            "lance_control": self.lance_control,
        }


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
    for choices, key in ((GUARDS, plan.shield_guard),
                         (CHARGE_INTENSITIES, plan.charge_intensity),
                         (LANCE_CONTROLS, plan.lance_control)):
        _, _, add_align, add_charge, add_resist, add_handle, add_fatigue, add_risk = choices[key]
        align += add_align
        charge += add_charge
        mr += add_resist
        handling += add_handle
        gain += add_fatigue
        risk += add_risk
    # v2.9.6a: guarded, measured precision should convert a sound defensive
    # line into an occasional effective counterstrike. The narrow +2 only
    # offsets part of the stacked cautious/lance/brace/precision penalties;
    # it cannot be stacked with Full Charge or an aggressive riding style.
    if (plan.style == "cautious" and plan.shield_guard in {"high", "low"}
            and plan.charge_intensity == "measured"
            and plan.lance_control == "precise"):
        charge += 2
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
    base = (f"{STYLES[plan.style][0]} · {TARGETS[plan.target][0]} · "
            f"{MOVES[plan.manoeuvre][0]}")
    if not advanced_active(plan):
        return base
    return (base + f" · {GUARDS[plan.shield_guard][0]} / "
            f"{CHARGE_INTENSITIES[plan.charge_intensity][0]} / "
            f"{LANCE_CONTROLS[plan.lance_control][0]}")


def target_result(category: str, points: int, target: str) -> tuple[str, int]:
    """Targeting a lance favours a single-point break over heavy shield scores."""
    if target == "lance" and category in {"heavy_shield_hit", "saddle_stagger"}:
        return "lance_break", 1
    return category, points
