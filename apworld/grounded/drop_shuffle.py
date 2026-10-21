"""
Creature drop shuffle: a seeded permutation of creature materials ("whatever
dropped Spider Fang now drops Moth Scale"), the same for every creature.

Materials only swap within a group with identical requirement tokens
(location_review.txt "needs:"), so logic, itemsanity and recipe_shuffle's
pools stay correct without knowing the mapping. Gold cards are a separate
mechanism (Bestiary RareDropChance) and never change.

slot_data["creature_drop_shuffle"]: vanilla Table_AllItems row -> new row;
drop_shuffle.lua rewrites a dying creature's LootComponent through it.
"""
from __future__ import annotations

from random import Random
from typing import Dict, Tuple

from .review_data import ITEM_NEEDS

# display name -> Table_AllItems row. Anything not listed stays vanilla.
DROP_ROWS: Dict[str, str] = {
    "Acid Gland": "AcidGland", "Bee Fuzz": "BeeFuzz", "Bee Stinger": "BeeStinger",
    "Gnat Fuzz": "FuzzGnat", "Grub Hide": "GrubHide", "Grub Sludge": "GrubGoop",
    "Larva Spike": "LarvaSpike", "Mite Fuzz": "FuzzMite",
    "Raw Aphid Meat": "AphidMeat", "Raw Gnat Meat": "GnatMeat", "Raw Grub Meat": "GrubMeat",
    "Raw Tadpole Meat": "TadpoleMeat", "Raw Weevil Meat": "WeevilMeat",
    "Water Flea Meat": "WaterFleaChunk", "Weevil Nose": "WeevilNose",
    "Red Ant Part": "AntPart", "Red Ant Head": "AntHead", "Red Ant Mandibles": "AntMandibles",
    "Stinkbug Gas Sack": "StinkBugGasSack",
    "Black Ant Head": "AntHeadBlack", "Black Ant Mandibles": "AntMandiblesBlack",
    "Black Ant Part": "AntPartBlack", "Bombardier Part": "BombardierPart",
    "Boiling Gland": "BombardierExpGland", "Diving Bell Spider Chunk": "DivingBellSpiderChunk",
    "Ladybug Head": "LadybugHead", "Mosquito Beak": "MosquitoBeak",
    "Mosquito Blood Sack": "MosquitoBloodSack", "Spider Chunk": "SpiderChunk",
    "Spider Fang": "SpiderFang", "Spider Venom": "SpiderVenom",
    "Water Boatman Fin": "WaterBoatmanFin", "Moth Fuzz": "MothFuzz", "Moth Scale": "MothScale",
    "Antlion Part": "AntlionPart", "Antlion Pincer": "AntlionPincer",
    "Black Ox Part": "BlackOxPart", "Black Ox Horn": "BlackOxHorn",
    "Roly Poly Part": "RolyPolyPart", "Roly Poly Shell": "RolyPolyShell",
    "Termite Part": "TermitePart", "Termite Chompers": "TermiteChompers",
    "Tiger Mosquito Beak": "MosquitoBeakTiger", "Tick Fang": "MiteTickFang",
    "Fire Ant Head": "AntHeadFire", "Fire Ant Mandibles": "AntMandiblesFire",
    "Fire Ant Part": "AntPartFire", "Wasp Leg": "WaspLeg", "Ladybird Shell": "Ladybirdshell",
    "Dust Mite Fuzz": "FuzzMiteDust", "Green Shield Bug Parts": "StinkbugPartGreenShield",
}


def _group_by_requirement() -> Tuple[Dict[str, str], ...]:
    groups: Dict[Tuple[str, ...], Dict[str, str]] = {}
    for name in sorted(DROP_ROWS):
        key = tuple(sorted(ITEM_NEEDS[name]))
        groups.setdefault(key, {})[name] = DROP_ROWS[name]
    return tuple(groups[key] for key in sorted(groups))


# Swaps only happen inside a group: drops with exactly the same "needs:"
# tokens in location_review.txt (so a group of one never changes).
DROP_GROUPS: Tuple[Dict[str, str], ...] = _group_by_requirement()

DISPLAY_NAME_BY_ROW: Dict[str, str] = {row: name for group in DROP_GROUPS for name, row in group.items()}


def generate(random: Random) -> Dict[str, str]:
    """vanilla item row -> replacement item row, a permutation within each
    group. Rows that happen to map to themselves are left out."""
    result: Dict[str, str] = {}
    for group in DROP_GROUPS:
        rows = sorted(group.values())
        shuffled = rows[:]
        random.shuffle(shuffled)
        result.update({old: new for old, new in zip(rows, shuffled) if old != new})
    return result
