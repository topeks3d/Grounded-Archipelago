"""
Craftsanity: first craft of each recipe ("Craft: <name>"), matched by the
crafted item's Table_AllItems row (location_hooks.lua keeps a copy of
CRAFTSANITY_ROW_TO_DISPLAY_NAME -- keep them in sync).

Location IDs follow the order of CRAFTSANITY_ROW_TO_DISPLAY_NAME: gear added
later (_LATE_GEAR_ROWS, side armor) and Fin Flops go at the end so earlier
IDs never shift -- only ever append.
"""
from __future__ import annotations

from typing import Dict, List

from .gear import GEAR


_LATE_GEAR_ROWS = ("DaggerSpiderWidow", "BoneDivingKnife") + tuple(g.item_row for g in GEAR if g.side)
CRAFTSANITY_ROW_TO_DISPLAY_NAME: Dict[str, str] = {
    g.item_row: g.name for g in GEAR if g.item_row not in _LATE_GEAR_ROWS
}
CRAFTSANITY_ROW_TO_DISPLAY_NAME.update({
    # Consumables (36) -- gated on the "Consumables" grouped item.
    "Canteen": "Canteen",
    "Canteen+": "Upgraded Canteen",
    "CanteenCharcoal": "Charcoal Canteen",
    "GranolaAcorn": "Acorn Granola",
    "Bandage": "Bandage",
    "MealTier1BoatmanSoap": "Boatman Fin Soup",
    "SmoothieFiber": "Fiber Smoothie",
    "SmoothieGastroGoo": "Gastro Goo Smoothie",
    "SmoothieFuzzOnTheRocks": "Fuzz On The Rocks Smoothie",
    "SmoothieAphid": "Aphid Smoothie",
    "SmoothieBerry": "Berry Smoothie",
    "SmoothieWaterBreathing": "Water Breathing Smoothie",
    "SmoothieSwimSpeed": "Swim Speed Smoothie",
    "SmoothieAttack": "Attack Smoothie",
    "SmoothieAnt": "Ant Smoothie",
    "SmoothieHumanFood": "Human Food Smoothie",
    "SmoothieWasp": "Wasp Smoothie",
    "SmoothieBoss": "Boss Smoothie",
    "BombHeal": "Healing Bomb",
    "MealTier1Spaghetflea": "Spaghetflea",
    "MealTier2SpiderSlider": "Spider Slider",
    "MealTier1Larvagna": "Larvagna",
    "MealTier1Miteloaf": "Miteloaf",
    "MealTier2MacNBees": "Mac N Bees",
    "MealTier1Gnatchos": "Gnatchos",
    "MealTier2Funguspacho": "Funguspacho",
    "MealTier2Omelant": "Omelant",
    "MealTier3Quesadillantlion": "Quesadillantlion",
    "MealTier3BlackOxBurger": "Black Ox Burger",
    "MealTier3TermiteDelight": "Termite Delight",
    "MealTier3TadpolePudding": "Tadpole Pudding",
    "MealTier3Wasperole": "Wasperole",
    "MealTier3Empanadust": "Empanadust",

    # Utilities (15) -- gated on the "Utilities" grouped item.
    "Torch": "Torch",
    "Torch+": "Upgraded Torch",
    "Flare": "Flare",
    "SmokeScreen": "Smoke Screen",
    "Binoculars": "Binoculars",
    "LeafBlower": "Leaf Blower",
    "RepairHammer": "Repair Hammer",
    "RepairArmor1": "Armor Repair Kit",
    "RepairArmor2": "Advanced Armor Repair Kit",
    "DecoyBait": "Decoy Bait",
    "DivingLantern": "Diving Lantern",
    "DivingLantern+": "Upgraded Diving Lantern",
    "LanternFirefly": "Firefly Lantern",
})
CRAFTSANITY_ROW_TO_DISPLAY_NAME.update({g.item_row: g.name for g in GEAR if g.item_row in _LATE_GEAR_ROWS})

# Fin Flops: the Flippers recipe comes with the "Diving Gear" item.
CRAFTSANITY_ROW_TO_DISPLAY_NAME["Flippers"] = "Fin Flops"

# row -> the AP item that unlocks the recipe (gear gates on itself).
CRAFTSANITY_ROW_TO_GATE_ITEM: Dict[str, str] = {g.item_row: g.name for g in GEAR}
CONSUMABLES_ROWS = (
    "Canteen", "Canteen+", "CanteenCharcoal", "GranolaAcorn", "Bandage",
    "MealTier1BoatmanSoap", "SmoothieFiber", "SmoothieGastroGoo",
    "SmoothieFuzzOnTheRocks", "SmoothieAphid", "SmoothieBerry", "SmoothieWaterBreathing",
    "SmoothieSwimSpeed", "SmoothieAttack", "SmoothieAnt", "SmoothieHumanFood",
    "SmoothieWasp", "SmoothieBoss", "BombHeal",
    "MealTier1Spaghetflea", "MealTier2SpiderSlider", "MealTier1Larvagna", "MealTier1Miteloaf",
    "MealTier2MacNBees", "MealTier1Gnatchos", "MealTier2Funguspacho", "MealTier2Omelant", "MealTier3Quesadillantlion",
    "MealTier3BlackOxBurger", "MealTier3TermiteDelight", "MealTier3TadpolePudding", "MealTier3Wasperole", "MealTier3Empanadust",
)
_UTILITIES_ROWS = (
    "Torch", "Torch+", "Flare", "SmokeScreen", "Binoculars", "LeafBlower",
    "RepairHammer", "RepairArmor1", "RepairArmor2", "DecoyBait",
    "DivingLantern", "DivingLantern+", "LanternFirefly",
)
for _row in CONSUMABLES_ROWS:
    CRAFTSANITY_ROW_TO_GATE_ITEM[_row] = "Consumables"
for _row in _UTILITIES_ROWS:
    CRAFTSANITY_ROW_TO_GATE_ITEM[_row] = "Utilities"
CRAFTSANITY_ROW_TO_GATE_ITEM["Flippers"] = "Diving Gear"

# Keep in sync with location_hooks.lua's CRAFT_LOCATION_PREFIX.
CRAFT_LOCATION_PREFIX = "Craft: "

craftsanity_location_names: List[str] = [
    CRAFT_LOCATION_PREFIX + name for name in CRAFTSANITY_ROW_TO_DISPLAY_NAME.values()
]


CRAFTSANITY_LOCATION_TO_GATE_ITEM: Dict[str, str] = {
    CRAFT_LOCATION_PREFIX + CRAFTSANITY_ROW_TO_DISPLAY_NAME[row]: gate_item
    for row, gate_item in CRAFTSANITY_ROW_TO_GATE_ITEM.items()
}


BASE_ID = 9411000 + 6000

craftsanity_location_name_to_id: Dict[str, int] = {
    name: BASE_ID + offset for offset, name in enumerate(craftsanity_location_names)
}
