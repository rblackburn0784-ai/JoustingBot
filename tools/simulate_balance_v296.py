"""v2.9.6 — deterministic equal-stat, cross-arena tactical balance sweep.

Run: python tools/simulate_balance_v296.py [--seeds 200] [--json]
Outputs fair seat-swapped win shares vs the neutral baseline. This is a
diagnostic, not a promise of perfectly even outcomes in unequal-stat matches.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.arenas import ARENAS
from services.combat import Fighter, run_single_match
from services.tactics import TacticPlan

KNIGHT = dict(strength=5, control=5, endurance=5, agility=4, resolve=4, tactics=4)
HORSE = dict(speed=5, stamina=5, power=5, obedience=5, courage=4)
PLANS = {
    "neutral": TacticPlan(),
    "measured_precision": TacticPlan(charge_intensity="measured", lance_control="precise"),
    "full_force": TacticPlan(charge_intensity="full", lance_control="forceful"),
    "high_guard": TacticPlan(shield_guard="high"),
    "low_guard": TacticPlan(shield_guard="low"),
    "cautious_counter": TacticPlan(
        style="cautious", target="lance", manoeuvre="shield_brace",
        shield_guard="low", charge_intensity="measured", lance_control="precise"),
    "aggressive_striker": TacticPlan(
        style="aggressive", target="rider", manoeuvre="reckless_charge",
        shield_guard="high", charge_intensity="full", lance_control="forceful"),
    "cautious_high_guard": TacticPlan(
        style="cautious", target="shield", manoeuvre="shield_brace",
        shield_guard="high", charge_intensity="measured", lance_control="precise"),
}


def fighter(uid: int) -> Fighter:
    return Fighter(uid, "Red" if uid == 1 else "Blue",
                   "Comet", dict(KNIGHT), dict(HORSE),
                   "lance_ash", "armour_mail", "barding_none")


def sweep(seeds: int = 200) -> dict:
    if not 1 <= seeds <= 5000:
        raise ValueError("Choose between 1 and 5000 seeds per arena.")
    neutral = PLANS["neutral"]
    rows = {}
    for name, tactic in PLANS.items():
        if name == "neutral":
            continue
        total_points, bouts, wins, draws = 0.0, 0, 0, 0
        arenas = {}
        for key in ARENAS:
            score, played = 0.0, 0
            for seed in range(1, seeds + 1):
                for swap in (False, True):
                    left_plan, right_plan = (
                        (tactic, neutral) if not swap else (neutral, tactic)
                    )
                    result = run_single_match(
                        fighter(1), fighter(2), key,
                        seed=seed, tactics_a=left_plan, tactics_b=right_plan)
                    own, opponent = (
                        (result.score_a, result.score_b) if not swap
                        else (result.score_b, result.score_a)
                    )
                    delta = 1.0 if own > opponent else 0.5 if own == opponent else 0.0
                    score += delta
                    total_points += delta
                    bouts += 1
                    played += 1
                    wins += int(own > opponent)
                    draws += int(own == opponent)
            arenas[key] = round(score / played, 4)
        rows[name] = {
            "win_share": round(total_points / bouts, 4),
            "wins": wins, "draws": draws, "matches": bouts,
            "arenas": arenas,
        }
    return rows





def head_to_head(first: str, second: str, seeds: int = 100) -> dict:
    """Equal-stat, mirrored-seat trial of an explicit pair of strategies."""
    if first not in PLANS or second not in PLANS or not 1 <= seeds <= 5000:
        raise ValueError("Choose valid plans and 1–5000 seeds.")
    results = {}
    total = 0.0
    for key in ARENAS:
        points = 0.0
        for seed in range(1, seeds + 1):
            for swapped in (False, True):
                left, right = ((PLANS[first], PLANS[second]) if not swapped
                               else (PLANS[second], PLANS[first]))
                result = run_single_match(fighter(1), fighter(2), key,
                                          seed=seed, tactics_a=left, tactics_b=right)
                own, theirs = ((result.score_a, result.score_b) if not swapped
                               else (result.score_b, result.score_a))
                points += 1.0 if own > theirs else 0.5 if own == theirs else 0.0
        results[key] = round(points / (seeds * 2), 4)
        total += points
    return {"first": first, "second": second,
            "win_share": round(total / (len(ARENAS) * seeds * 2), 4),
            "arenas": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=200)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--defence-check", action="store_true",
                        help="Require defensive builds to remain viable.")
    options = parser.parse_args()
    result = sweep(options.seeds)
    matchups = (
        ([head_to_head("cautious_counter", other, options.seeds)
           for other in ("aggressive_striker", "full_force", "neutral")]
         + [head_to_head("cautious_high_guard", "aggressive_striker", options.seeds)])
        if options.defence_check else []
    )
    if options.json:
        print(json.dumps({"vs_neutral": result, "head_to_head": matchups}, indent=2))
    else:
        print(f"v2.9.6 combat balance · {options.seeds} seeded pairs per arena")
        for name, value in result.items():
            print(f"{name:22} {value['win_share']:.1%} seat-adjusted win share "
                  f"({value['matches']} matches)")
            for arena, ratio in value["arenas"].items():
                print(f"  {arena:22} {ratio:.1%}")
        for row in matchups:
            print(f"{row['first']} vs {row['second']:19} {row['win_share']:.1%} "
                  "seat-adjusted win share")
    if options.defence_check:
        # These are viability floors, not a claim of perfect balance.
        defensive = result["cautious_counter"]["win_share"]
        if not 0.38 <= defensive <= 0.65:
            print(f"FAIL: cautious defence remains outside viability band: "
                  f"{defensive:.1%}", file=sys.stderr)
            return 2
        if result["measured_precision"]["win_share"] < 0.38:
            print("FAIL: measured precision is underpowered.", file=sys.stderr)
            return 2
        if result["aggressive_striker"]["win_share"] > 0.68:
            print("FAIL: aggressive striker dominates neutral.", file=sys.stderr)
            return 2
        cautious_high = result["cautious_high_guard"]["win_share"]
        if not 0.38 <= cautious_high <= 0.62:
            print(f"FAIL: cautious high-guard dominance/weakness: {cautious_high:.1%}",
                  file=sys.stderr)
            return 2
        high_vs_aggressive = next(
            m["win_share"] for m in matchups
            if m["first"] == "cautious_high_guard" and m["second"] == "aggressive_striker"
        )
        if not 0.40 <= high_vs_aggressive <= 0.68:
            print(f"FAIL: high-guard anti-aggression counter is outside its "
                  f"target band: {high_vs_aggressive:.1%}", file=sys.stderr)
            return 2
    # Wide safety tripwire: identity/seat-neutral tactics should not become
    # completely unstoppable. The full sweep still needs human review.
    if any(not 0.10 <= row["win_share"] <= 0.90 for row in result.values()):
        print("WARNING: Possible dominant or ineffective tactic detected.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
