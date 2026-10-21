"""
Recipe shuffle: new, seeded ingredients for every Tier 2 and 3 gear recipe
(Tier 1 stays vanilla).

Logic safety: Tier N gear counts once the player can fight Tier N-1
creatures, so Tier 2 recipes only draw materials needing nothing or "c1",
and Tier 3 ones materials needing at most "c2" (their location_review.txt
needs). A shuffled recipe is never harder than its tier baseline.

slot_data["recipe_shuffle"]: recipe row -> MAX_INGREDIENTS [item_row, count]
pairs. recipe_shuffle.lua keeps each recipe's vanilla slot count and fills
the slots from the front of the list.
"""
from __future__ import annotations

from random import Random
from typing import Dict, List, NamedTuple, Tuple

from .gear import GEAR


class Material(NamedTuple):
    name: str       # display name (== its ITEM_REQUIREMENTS / itemsanity name)
    row: str        # Table_AllItems row
    low: int        # count range per recipe slot
    high: int


# No requirement at all (ungated in rules.py).
FREE_MATERIALS: Tuple[Material, ...] = (
    Material("Plant Fiber", "FiberRaw", 3, 8),
    Material("Sprig", "Twig", 3, 8),
    Material("Pebblet", "StoneShale", 3, 8),
    Material("Sap", "Sap", 2, 6),
    Material("Crude Rope", "FiberWoven", 2, 4),
    Material("Flower Petal", "FlowerPetal", 2, 5),
    Material("Gnat Fuzz", "FuzzGnat", 2, 5),
    Material("Weevil Nose", "WeevilNose", 1, 3),
    Material("Slime Mold Stalk", "SlimeMold", 1, 3),
)

# ("c1",) in rules.py's ITEM_REQUIREMENTS. Materials whose review-file needs
# include a tool, the Gas Mask or Diving Gear (Grub Hide/Sludge: shovel1,
# Pupa Hide/Leather: axe3, Crow Feather Piece: axe2, Stinkbug Gas Sack: gas)
# can't be in any pool.
TIER1_MATERIALS: Tuple[Material, ...] = (
    Material("Red Ant Part", "AntPart", 2, 5),
    Material("Red Ant Head", "AntHead", 1, 2),
    Material("Red Ant Mandibles", "AntMandibles", 1, 3),
    Material("Acid Gland", "AcidGland", 1, 3),
    Material("Mite Fuzz", "FuzzMite", 2, 5),
    Material("Larva Spike", "LarvaSpike", 1, 3),
    Material("Bombardier Part", "BombardierPart", 1, 4),
)

# ("c2",) in rules.py's ITEM_REQUIREMENTS. (Left out for needing more than
# c2: Spiky Bur, Lint, Wooden Splinter, Rust, Toenail, Pinecone Piece, Salt
# Shard, Moth Fuzz/Scale, Water Boatman Fin.)
TIER2_MATERIALS: Tuple[Material, ...] = (
    Material("Black Ant Part", "AntPartBlack", 2, 5),
    Material("Black Ant Head", "AntHeadBlack", 1, 2),
    Material("Black Ant Mandibles", "AntMandiblesBlack", 1, 3),
    Material("Boiling Gland", "BombardierExpGland", 1, 2),
    Material("Ladybug Head", "LadybugHead", 1, 2),
    Material("Spider Chunk", "SpiderChunk", 1, 4),
    Material("Spider Fang", "SpiderFang", 1, 3),
    Material("Spider Venom", "SpiderVenom", 1, 2),
    Material("Mosquito Beak", "MosquitoBeak", 1, 3),
    Material("Mosquito Blood Sack", "MosquitoBloodSack", 1, 3),
    Material("Bee Stinger", "BeeStinger", 1, 2),
    Material("Bee Fuzz", "BeeFuzz", 2, 5),
)

MAX_INGREDIENTS = 5

MATERIAL_BY_ROW: Dict[str, Material] = {
    m.row: m for m in FREE_MATERIALS + TIER1_MATERIALS + TIER2_MATERIALS
}

# gear tier -> (the "signature" pool slot 1 is drawn from, pool for the rest)
_TIER_POOLS: Dict[int, Tuple[Tuple[Material, ...], Tuple[Material, ...]]] = {
    2: (TIER1_MATERIALS, FREE_MATERIALS + TIER1_MATERIALS),
    3: (TIER2_MATERIALS, TIER1_MATERIALS + TIER2_MATERIALS),
}

# Ammo is crafted in batches from a handful of materials -- keep it cheap.
_CHEAP_KINDS = {"ammo"}


def shuffled_gear():
    """Every gear piece whose ingredients get shuffled (Tier 2 and 3)."""
    return [g for g in GEAR if g.tier in _TIER_POOLS]


def generate(random: Random) -> Dict[str, List[List]]:
    """recipe row -> [[item_row, count], ...] (MAX_INGREDIENTS long, no
    repeated materials within one recipe)."""
    result: Dict[str, List[List]] = {}
    for gear in shuffled_gear():
        signature_pool, rest_pool = _TIER_POOLS[gear.tier]
        first = random.choice(signature_pool)
        rest = random.sample([m for m in rest_pool if m is not first], MAX_INGREDIENTS - 1)
        entries = []
        for material in [first] + rest:
            high = material.low if gear.kind in _CHEAP_KINDS else material.high
            entries.append([material.row, random.randint(material.low, high)])
        result[gear.recipe_row] = entries
    return result
