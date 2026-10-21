"""
Item definitions for the Grounded world.

Item IDs are BASE_ID + code_offset. Retired offsets, never reuse: 2, 4, 5,
10-20, 30.
"""
from __future__ import annotations

from enum import IntEnum
from typing import Dict, NamedTuple, Set

from BaseClasses import ItemClassification as IC

from .gear import GEAR, PROGRESSIVE_LINES

BASE_ID = 9411000


class ItemType(IntEnum):
    gear = 1
    blueprint = 2
    story = 3
    filler = 4


class ItemData(NamedTuple):
    code_offset: int
    classification: IC
    type: ItemType
    count: int = 1  # copies in a default pool


# Granted by item_grants.lua: Gas Mask -> GasMask recipe, Diving Gear ->
# DivingMask/Rebreather/Flippers recipes, Zip Line Rig -> KeyZiplineAscender.
gear_items: Dict[str, ItemData] = {
    "Gas Mask":               ItemData(0, IC.progression, ItemType.gear),
    "Diving Gear":            ItemData(1, IC.progression, ItemType.gear),
    "Zip Line Rig":           ItemData(3, IC.progression, ItemType.gear),
}

# Station / recipe-group unlocks (item_grants.lua). Research unlocks are
# disabled in-game, so these are the only way to get them.
blueprint_items: Dict[str, ItemData] = {
    "Smoothie Station":      ItemData(21, IC.progression, ItemType.blueprint),
    # Cookery = BuildingRecipeTable row "CookingStation" (every MealTier* meal).
    "Cookery":               ItemData(26, IC.progression, ItemType.blueprint),
    # Oven = row "Smelter" (globs, jewels, Ash Cement, Mushroom Brick, boss keys).
    "Oven":                  ItemData(27, IC.progression, ItemType.blueprint),
    "Consumables":           ItemData(24, IC.progression, ItemType.blueprint),
    "Utilities":             ItemData(25, IC.progression, ItemType.blueprint),
}

# One item per gear recipe (gear.py).
gear_recipe_items: Dict[str, ItemData] = {
    g.name: ItemData(g.code_offset, IC.progression, ItemType.blueprint) for g in GEAR
}

# ProgressiveGear: count=0 here; create_items adds them (and drops the
# recipes they replace) when the option is on.
progressive_items: Dict[str, ItemData] = {
    name: ItemData(190 + i, IC.progression, ItemType.blueprint, count=0)
    for i, name in enumerate(PROGRESSIVE_LINES)
}

story_items: Dict[str, ItemData] = {}

# Filler (item_grants.lua grants them). Raw Science goes through AddScience,
# not GiveItem: its row behaves like a currency pickup.
filler_items: Dict[str, ItemData] = {
    "Raw Science Bundle": ItemData(40, IC.filler, ItemType.filler, count=0),
    "Full Restore":       ItemData(41, IC.filler, ItemType.filler, count=0),
    "Bandage Bundle":     ItemData(48, IC.filler, ItemType.filler, count=0),
}

# DeDuper Jelly only exists in New Game+; the 13 NG+ weapon recipes need 2
# each. Logic requires all bundles before any jelly recipe counts (13 x 2 =
# 26, plus spares). Keep JELLY_PER_BUNDLE in sync with item_grants.lua.
JELLY_BUNDLE = "DeDuper Jelly Bundle"
JELLY_PER_BUNDLE = 8
JELLY_BUNDLE_COUNT = 4
filler_items[JELLY_BUNDLE] = ItemData(49, IC.progression, ItemType.filler, count=JELLY_BUNDLE_COUNT)

# Infused Ooze (NG+ only) -- not in logic, fixed count. Keep OOZE_PER_BUNDLE
# in sync with item_grants.lua.
OOZE_BUNDLE = "Infused Ooze Bundle"
OOZE_PER_BUNDLE = 10
OOZE_BUNDLE_COUNT = 2
filler_items[OOZE_BUNDLE] = ItemData(54, IC.filler, ItemType.filler, count=OOZE_BUNDLE_COUNT)

# Relative odds for get_filler_item_name.
FILLER_WEIGHTS: Dict[str, int] = {
    "Raw Science Bundle": 6,
    "Full Restore": 3,
    "Bandage Bundle": 2,
}

# Locked goal-progress items (never in the random pool). They need real IDs
# so the server grants them when their ID-bearing location is checked; goals
# count them with state.has(..., n), since those locations are ungated.
special_items: Dict[str, ItemData] = {
    "Gold Card Progress": ItemData(50, IC.progression_skip_balancing, ItemType.story, count=0),
    "Boss Kill Progress": ItemData(51, IC.progression_skip_balancing, ItemType.story, count=0),
    "Victory Progress": ItemData(52, IC.progression_skip_balancing, ItemType.story, count=0),
    "Itemsanity Progress": ItemData(53, IC.progression_skip_balancing, ItemType.story, count=0),
}

item_table: Dict[str, ItemData] = {
    **gear_items,
    **blueprint_items,
    **gear_recipe_items,
    **progressive_items,
    **story_items,
    **filler_items,
    **special_items,
}

item_name_to_id: Dict[str, int] = {
    name: BASE_ID + data.code_offset for name, data in item_table.items()
}

item_name_groups: Dict[str, Set[str]] = {
    "Gear": set(gear_items.keys()),
    "Blueprints": set(blueprint_items.keys()) | set(gear_recipe_items.keys()),
    "Tier 1 Gear": {g.name for g in GEAR if g.tier == 1},
    "Tier 2 Gear": {g.name for g in GEAR if g.tier == 2},
    "Tier 3 Gear": {g.name for g in GEAR if g.tier == 3},
    "Armor": {g.name for g in GEAR if g.kind == "armor"},
    "Filler": set(filler_items.keys()),
    "Progressive Gear": set(progressive_items.keys()),
}

# Random filler only -- the jelly bundles are a fixed, logic-relevant count.
filler_item_names = [name for name in filler_items if name in FILLER_WEIGHTS]
