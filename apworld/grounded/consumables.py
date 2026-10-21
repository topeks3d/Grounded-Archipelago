"""
Every consumable recipe that's its own AP item (food, drink, healing).
items.py, craftsanity.py and rules.py build on CONSUMABLES; the mod gets
the recipe rows through the generated ap_data.lua.

- item_row: Table_AllItems row (craft detection, icons).
- recipe_rows: CraftingRecipeTable rows the item unlocks (UnlockRecipe). The
  first is the recipe itself; the rest are variants with no check of their
  own (BandageEfficient, SmoothieHealing, SausageBombHealing).

Item offsets 220-252 (items.py BASE_ID); only ever append.
"""
from __future__ import annotations

from typing import Dict, List, NamedTuple, Tuple


class Consumable(NamedTuple):
    name: str               # AP item name == craftsanity display name
    code_offset: int
    item_row: str
    recipe_rows: Tuple[str, ...]


CONSUMABLES: List[Consumable] = [
    Consumable("Canteen",                    220, "Canteen",                   ("Canteen",)),
    Consumable("Upgraded Canteen",           221, "Canteen+",                  ("Canteen+",)),
    Consumable("Charcoal Canteen",           222, "CanteenCharcoal",           ("CanteenCharcoal",)),
    Consumable("Acorn Granola",              223, "GranolaAcorn",              ("AcornGranola",)),
    Consumable("Bandage",                    224, "Bandage",                   ("Bandage", "BandageEfficient")),
    Consumable("Boatman Fin Soup",           225, "MealTier1BoatmanSoap",      ("BoatmanFinSoup",)),
    Consumable("Fiber Smoothie",             226, "SmoothieFiber",             ("SmoothieFiber", "SmoothieHealing")),
    Consumable("Gastro Goo Smoothie",        227, "SmoothieGastroGoo",         ("SmoothieGastroGoo",)),
    Consumable("Fuzz On The Rocks Smoothie", 228, "SmoothieFuzzOnTheRocks",    ("SmoothieFuzzOnTheRocks",)),
    Consumable("Aphid Smoothie",             229, "SmoothieAphid",             ("SmoothieAphid",)),
    Consumable("Berry Smoothie",             230, "SmoothieBerry",             ("SmoothieBerry",)),
    Consumable("Water Breathing Smoothie",   231, "SmoothieWaterBreathing",    ("SmoothieWaterBreathing",)),
    Consumable("Swim Speed Smoothie",        232, "SmoothieSwimSpeed",         ("SmoothieSwimSpeed",)),
    Consumable("Attack Smoothie",            233, "SmoothieAttack",            ("SmoothieAttack",)),
    Consumable("Ant Smoothie",               234, "SmoothieAnt",               ("SmoothieAnt",)),
    Consumable("Human Food Smoothie",        235, "SmoothieHumanFood",         ("SmoothieHumanFood",)),
    Consumable("Wasp Smoothie",              236, "SmoothieWasp",              ("SmoothieWasp",)),
    Consumable("Boss Smoothie",              237, "SmoothieBoss",              ("SmoothieBoss",)),
    Consumable("Healing Bomb",               238, "BombHeal",                  ("BombHealing", "SausageBombHealing")),
    Consumable("Spaghetflea",                239, "MealTier1Spaghetflea",      ("Spaghetflea",)),
    Consumable("Spider Slider",              240, "MealTier2SpiderSlider",     ("SpiderSlider",)),
    Consumable("Larvagna",                   241, "MealTier1Larvagna",         ("Larvagna",)),
    Consumable("Miteloaf",                   242, "MealTier1Miteloaf",         ("Miteloaf",)),
    Consumable("Mac N Bees",                 243, "MealTier2MacNBees",         ("MacNBees",)),
    Consumable("Gnatchos",                   244, "MealTier1Gnatchos",         ("Gnatchos",)),
    Consumable("Funguspacho",                245, "MealTier2Funguspacho",      ("Funguspacho",)),
    Consumable("Omelant",                    246, "MealTier2Omelant",          ("Omelant",)),
    Consumable("Quesadillantlion",           247, "MealTier3Quesadillantlion", ("Quesadillantlion",)),
    Consumable("Black Ox Burger",            248, "MealTier3BlackOxBurger",    ("BlackOxBurger",)),
    Consumable("Termite Delight",            249, "MealTier3TermiteDelight",   ("TermiteDelight",)),
    Consumable("Tadpole Pudding",            250, "MealTier3TadpolePudding",   ("TadpolePudding",)),
    Consumable("Wasperole",                  251, "MealTier3Wasperole",        ("Wasperole",)),
    Consumable("Empanadust",                 252, "MealTier3Empanadust",       ("Empanadust",)),
]

CONSUMABLE_BY_NAME: Dict[str, Consumable] = {c.name: c for c in CONSUMABLES}

# Forced early (with the Tier 1 gear): healing from the very start.
EARLY_CONSUMABLES = ("Bandage",)
