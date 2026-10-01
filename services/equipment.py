from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Optional


Slot = Literal["lance", "armour", "barding"]


@dataclass(frozen=True)
class EquipmentItem:
    key: str
    name: str
    slot: Slot
    description: str

    knight_stat_mods: Dict[str, int] = field(default_factory=dict)
    horse_stat_mods: Dict[str, int] = field(default_factory=dict)

    alignment_mod: int = 0
    charge_mod: int = 0
    impact_mult: float = 1.0

    # In combat.py, higher panic_mod helps the horse resist refusal/bolting.
    # Arena panic is applied separately as a penalty.
    slip_mod: int = 0
    panic_mod: int = 0
    unhorse_resist: int = 0


ITEMS: Dict[str, EquipmentItem] = {}


def add_item(item: EquipmentItem) -> None:
    if item.key in ITEMS:
        raise ValueError(f"Duplicate equipment key: {item.key}")

    ITEMS[item.key] = item


# -------------------------
# Lances
# -------------------------

add_item(
    EquipmentItem(
        key="lance_ash",
        name="Ash Lance",
        slot="lance",
        description="Balanced and reliable. No major bonuses or penalties.",
    )
)

add_item(
    EquipmentItem(
        key="lance_heavy",
        name="Heavy War Lance",
        slot="lance",
        description="Hits harder, but is harder to aim.",
        alignment_mod=-2,
        charge_mod=1,
        impact_mult=1.12,
        knight_stat_mods={"control": -1},
    )
)

add_item(
    EquipmentItem(
        key="lance_tournament",
        name="Tournament Lance",
        slot="lance",
        description="Accurate and clean, but less forceful on impact.",
        alignment_mod=3,
        impact_mult=0.92,
    )
)

add_item(
    EquipmentItem(
        key="lance_long",
        name="Long Reach Lance",
        slot="lance",
        description="Better line control at range, but awkward in the final impact.",
        alignment_mod=2,
        charge_mod=-1,
        impact_mult=0.98,
        knight_stat_mods={"control": 1, "strength": -1},
    )
)


# -------------------------
# Armour
# -------------------------

add_item(
    EquipmentItem(
        key="armour_mail",
        name="Tournament Mail",
        slot="armour",
        description="Balanced armour used in most formal jousts.",
    )
)

add_item(
    EquipmentItem(
        key="armour_light",
        name="Light Plate",
        slot="armour",
        description="Agile and responsive, but less stable under heavy impact.",
        knight_stat_mods={"agility": 2, "endurance": -1},
        alignment_mod=1,
        unhorse_resist=-1,
    )
)

add_item(
    EquipmentItem(
        key="armour_full",
        name="Full Plate",
        slot="armour",
        description="Excellent stability, but slower and harder to control.",
        knight_stat_mods={"endurance": 2, "agility": -1, "control": -1},
        alignment_mod=-1,
        unhorse_resist=2,
    )
)

add_item(
    EquipmentItem(
        key="armour_reinforced_helm",
        name="Reinforced Helm",
        slot="armour",
        description="Improves nerve and safety, but narrows vision.",
        knight_stat_mods={"resolve": 2, "control": -1},
        alignment_mod=-1,
        unhorse_resist=1,
    )
)


# -------------------------
# Horse barding
# -------------------------

add_item(
    EquipmentItem(
        key="barding_none",
        name="No Barding",
        slot="barding",
        description="No protection. Maximum freedom of movement.",
    )
)

add_item(
    EquipmentItem(
        key="barding_leather",
        name="Leather Barding",
        slot="barding",
        description="Light protection. Keeps the horse calmer with little speed cost.",
        horse_stat_mods={"courage": 1},
        panic_mod=1,
    )
)

add_item(
    EquipmentItem(
        key="barding_steel",
        name="Steel Barding",
        slot="barding",
        description="Heavy protection and confidence, but slows the horse.",
        horse_stat_mods={"courage": 2, "speed": -1},
        panic_mod=2,
        slip_mod=1,
        charge_mod=-1,
    )
)

add_item(
    EquipmentItem(
        key="barding_spiked",
        name="Spiked Barding",
        slot="barding",
        description="Intimidating and bold, but more awkward under pressure.",
        horse_stat_mods={"courage": 1, "obedience": -1},
        panic_mod=1,
        slip_mod=1,
        charge_mod=1,
    )
)


def get_item(key: Optional[str]) -> Optional[EquipmentItem]:
    if not key:
        return None

    return ITEMS.get(key)


def items_by_slot(slot: Slot) -> Dict[str, EquipmentItem]:
    return {k: v for k, v in ITEMS.items() if v.slot == slot}


def apply_knight_equipment(
    base_stats: Dict[str, int],
    lance_key: Optional[str],
    armour_key: Optional[str],
) -> Dict[str, int]:
    stats = dict(base_stats)

    for key in (lance_key, armour_key):
        item = get_item(key)
        if not item:
            continue

        for stat, mod in item.knight_stat_mods.items():
            stats[stat] = max(0, stats.get(stat, 0) + mod)

    return stats


def apply_horse_equipment(
    base_stats: Dict[str, int],
    barding_key: Optional[str],
) -> Dict[str, int]:
    stats = dict(base_stats)

    item = get_item(barding_key)
    if item:
        for stat, mod in item.horse_stat_mods.items():
            stats[stat] = max(0, stats.get(stat, 0) + mod)

    return stats


def total_alignment_mod(
    lance_key: Optional[str],
    armour_key: Optional[str],
) -> int:
    total = 0

    for key in (lance_key, armour_key):
        item = get_item(key)
        if item:
            total += item.alignment_mod

    return total


def total_charge_mod(
    lance_key: Optional[str],
    armour_key: Optional[str],
    barding_key: Optional[str],
) -> int:
    total = 0

    for key in (lance_key, armour_key, barding_key):
        item = get_item(key)
        if item:
            total += item.charge_mod

    return total


def total_impact_mult(
    lance_key: Optional[str],
    armour_key: Optional[str],
) -> float:
    mult = 1.0

    for key in (lance_key, armour_key):
        item = get_item(key)
        if item:
            mult *= item.impact_mult

    return mult


def total_slip_mod(barding_key: Optional[str]) -> int:
    item = get_item(barding_key)
    return item.slip_mod if item else 0


def total_panic_mod(barding_key: Optional[str]) -> int:
    item = get_item(barding_key)
    return item.panic_mod if item else 0


def total_unhorse_resist(armour_key: Optional[str]) -> int:
    item = get_item(armour_key)
    return item.unhorse_resist if item else 0
