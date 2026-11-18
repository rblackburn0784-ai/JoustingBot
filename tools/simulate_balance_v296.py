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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=200)
    parser.add_argument("--json", action="store_true")
    options = parser.parse_args()
    result = sweep(options.seeds)
    if options.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"v2.9.6 combat balance · {options.seeds} seeded pairs per arena")
        for name, value in result.items():
            print(f"{name:22} {value['win_share']:.1%} seat-adjusted win share "
                  f"({value['matches']} matches)")
            for arena, ratio in value["arenas"].items():
                print(f"  {arena:22} {ratio:.1%}")
    # Wide safety tripwire: identity/seat-neutral tactics should not become
    # completely unstoppable. The full sweep still needs human review.
    if any(not 0.10 <= row["win_share"] <= 0.90 for row in result.values()):
        print("WARNING: Possible dominant or ineffective tactic detected.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
