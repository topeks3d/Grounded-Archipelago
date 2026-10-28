"""
RegionLocks: every region except the Grasslands needs its "Region Pass".
Without it the mod sends you back out (region_locks.lua); logic only puts
a check in reach once the passes for everything it needs are in hand:

  * Item and Landmark checks: the region they're filed under in
    location_review.txt.
  * Crafting (Craft checks, and gear counting toward the combat tiers):
    the regions its ingredients come from -- each material's own Item
    check region. With RecipeShuffle, the shuffled ingredients.
  * Boss kills: the boss's arena (BOSS_REGIONS).
  * Gold cards beyond Tier 1 creatures and the higher molar counts: they
    can be anywhere, so every pass (molars: the lower yard first).

Regions behind others (VIA) also need those passes, since the way in runs
through them.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, FrozenSet, Iterable, Mapping, Optional, Sequence, Tuple

from .review_data import LOCATION_BIOMES, REGIONS

PASS_PREFIX = "Region Pass: "
START_REGION = "Grasslands"
LOCKED_REGIONS: Tuple[str, ...] = tuple(r for r in REGIONS if r != START_REGION)

# Reaching these means crossing the first (Upper Yard layout on the map).
VIA: Dict[str, Tuple[str, ...]] = {
    "Shed Surroundings": ("Upper Grasslands",),
    "Woodpile": ("Upper Grasslands",),
    "Undershed": ("Shed Surroundings", "Upper Grasslands"),
}

# Boss arenas (grounded.wiki.gg + the landmarks in location_review.txt).
BOSS_REGIONS: Dict[str, Tuple[str, ...]] = {
    "Hedge Broodmother": ("Hedge",),
    "Black Widow": ("Upper Grasslands",),     # Brawny Boy Bin
    "Mantis": ("Shed Surroundings",),
    "Wasp Queen": ("Upper Grasslands",),      # Brawny Boy Bin
    "Assistant Manager": ("Sandbox",),        # Black Anthill Lab
    "Mant": ("Undershed",),
    "Director Schmector": ("Undershed", "Moldorc Highlands"),  # Mysterious Lab
    "Infected Broodmother": ("Haze",),
}

# Molar milestones above these need the lower yard / every region.
MOLARS_LOWER_YARD = 10
MOLARS_EVERYWHERE = 40
LOWER_YARD: Tuple[str, ...] = ("Hedge", "Pond", "Haze", "Sandbox")


def pass_item(region: str) -> str:
    return PASS_PREFIX + region


PASS_ITEMS: Tuple[str, ...] = tuple(pass_item(r) for r in LOCKED_REGIONS)


def with_via(regions: Iterable[str]) -> FrozenSet[str]:
    """`regions` plus whatever lies on the way, minus the free start."""
    out = set()
    for region in regions:
        out.add(region)
        out.update(VIA.get(region, ()))
    out.discard(START_REGION)
    return frozenset(out)


def item_region(item_name: str) -> Optional[str]:
    """The region an item is filed under (its Item check), if any."""
    region = LOCATION_BIOMES.get("Item: " + item_name)
    return region if region in REGIONS else None


@lru_cache(maxsize=None)
def _our_name(wiki_material: str) -> str:
    from .online_data import _recipes
    names = {wiki: ours for ours, wiki in _recipes()["names"].items()}
    return names.get(wiki_material, wiki_material)


@lru_cache(maxsize=None)
def vanilla_craft_regions(name: str) -> FrozenSet[str]:
    """Regions the ingredients of `name` (gear or consumable) come from."""
    from .online_data import vanilla_recipes
    recipes = vanilla_recipes(name)
    if not recipes:
        return frozenset()
    regions = (item_region(_our_name(material)) for material, _count in recipes[0]["materials"])
    return with_via(r for r in regions if r)


def shuffled_craft_regions(entries: Sequence[Sequence]) -> FrozenSet[str]:
    """Regions of RecipeShuffle ingredients ([[item_row, count], ...])."""
    from .recipe_shuffle import MATERIAL_BY_ROW
    regions = []
    for row, _count in entries:
        material = MATERIAL_BY_ROW.get(row)
        region = item_region(material.name) if material else None
        if region:
            regions.append(region)
    return with_via(regions)


def craft_regions(recipe_shuffle: Mapping[str, Sequence]) -> Dict[str, FrozenSet[str]]:
    """Every craftable gear / consumable name -> the regions it needs."""
    from .consumables import CONSUMABLES
    from .gear import GEAR
    out: Dict[str, FrozenSet[str]] = {}
    for gear in GEAR:
        entries = recipe_shuffle.get(gear.recipe_row)
        out[gear.name] = shuffled_craft_regions(entries) if entries else vanilla_craft_regions(gear.name)
    for consumable in CONSUMABLES:
        out[consumable.name] = vanilla_craft_regions(consumable.name)
    return out


def molar_regions(threshold: int) -> FrozenSet[str]:
    if threshold > MOLARS_EVERYWHERE:
        return frozenset(LOCKED_REGIONS)
    if threshold > MOLARS_LOWER_YARD:
        return with_via(LOWER_YARD)
    return frozenset()
