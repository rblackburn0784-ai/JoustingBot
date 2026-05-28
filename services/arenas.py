from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Arena:
    key: str
    name: str
    description: str

    alignment_mod: int = 0
    charge_mod: int = 0

    slip_mod: int = 0
    panic_mod: int = 0

    impact_mult: float = 1.0


ARENAS: Dict[str, Arena] = {
    "royal_lists": Arena(
        key="royal_lists",
        name="Royal Lists",
        description="A proper tournament field. Balanced, clean footing, no tricks.",
    ),

    "muddy_field": Arena(
        key="muddy_field",
        name="Muddy Field",
        description="Thick mud slows the charge and makes the line harder to hold.",
        alignment_mod=-1,
        charge_mod=-2,
        slip_mod=3,
        impact_mult=0.95,
    ),

    "frozen_ground": Arena(
        key="frozen_ground",
        name="Frozen Ground",
        description="Fast, dangerous ground. Charges hit harder, but horses risk slipping.",
        charge_mod=1,
        slip_mod=4,
        impact_mult=1.12,
    ),

    "wind_swept": Arena(
        key="wind_swept",
        name="Wind-Swept Field",
        description="Strong gusts push lances off-line. Control matters more than brute force.",
        alignment_mod=-3,
        panic_mod=1,
    ),

    "festival_arena": Arena(
        key="festival_arena",
        name="Festival Arena",
        description="Crowds, banners, noise and pressure. Great atmosphere, but distracting.",
        alignment_mod=-1,
        panic_mod=2,
        impact_mult=1.03,
    ),

    "war_torn": Arena(
        key="war_torn",
        name="War-Torn Battlefield",
        description="Broken ground, debris and chaos. Powerful hits, but unstable footing.",
        alignment_mod=-2,
        charge_mod=1,
        slip_mod=2,
        panic_mod=3,
        impact_mult=1.08,
    ),
}


def get_arena(arena_key: str) -> Arena:
    if arena_key not in ARENAS:
        raise KeyError(arena_key)

    return ARENAS[arena_key]