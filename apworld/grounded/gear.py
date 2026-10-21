"""
Every gear recipe that's its own AP item (weapons, tools, armor). items.py,
craftsanity.py and rules.py all build on GEAR; item_grants.lua
(GEAR_ITEM_TO_RECIPE_ROW) and location_hooks.lua keep hand-synced copies.

- recipe_row: CraftingRecipeTable row (item_grants.lua's UnlockRecipe).
- item_row: Table_AllItems row (craft detection). Usually the same as
  recipe_row, but not always (e.g. ClubAnt vs AntClub).
"""
from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional


class Gear(NamedTuple):
    name: str               # AP item name == craftsanity display name
    code_offset: int        # item id offset (see items.py BASE_ID)
    recipe_row: str
    item_row: str
    tier: int
    kind: str               # "melee", "ranged", "tool", "ammo", "shield", "armor", "other"
    tool: Optional[str] = None   # "axe" / "hammer" / "shovel" / "dagger" for harvesting tools
    slot: Optional[str] = None   # "head" / "chest" / "legs" for armor
    # New Game+ recipe: needs DeDuper Jelly, which AP hands out as bundles.
    ng_plus: bool = False
    # Combat tier its materials need when above tier - 1 (Widow Dagger: boss parts).
    material_fight: Optional[int] = None
    # Extra armor: own item and craft check only -- not counted for combat
    # tiers, not forced early, not in progressive lines.
    side: bool = False


GEAR: List[Gear] = [
    # --- Tier 1 ---
    Gear("Pebblet Axe",        100, "Axe",        "Axe",        1, "melee", tool="axe"),
    Gear("Pebblet Hammer",     101, "Hammer",     "Hammer",     1, "melee", tool="hammer"),
    Gear("Pebblet Spear",      102, "Spear",      "Spear",      1, "melee"),
    Gear("Acorn Shovel",       103, "Shovel",     "Shovel",     1, "tool", tool="shovel"),
    Gear("Sprig Bow",          104, "Bow",        "Bow",        1, "ranged"),
    Gear("Spiky Sprig",        105, "SpikySprig", "SpikySprig", 1, "melee"),
    Gear("Clover Head Armor",  106, "HeadClover",  "HeadClover",  1, "armor", slot="head"),
    Gear("Clover Chest Armor", 107, "ChestClover", "ChestClover", 1, "armor", slot="chest"),
    Gear("Clover Leg Armor",   108, "LegsClover",  "LegsClover",  1, "armor", slot="legs"),
    Gear("Acorn Head Armor",   109, "HeadAcorn",   "HeadAcorn",   1, "armor", slot="head"),
    Gear("Acorn Chest Armor",  110, "ChestAcorn",  "ChestAcorn",  1, "armor", slot="chest"),
    Gear("Acorn Leg Armor",    111, "LegsAcorn",   "LegsAcorn",   1, "armor", slot="legs"),
    Gear("Grub Head Armor",    112, "HeadGrub",    "HeadGrub",    1, "armor", slot="head"),
    Gear("Grub Chest Armor",   113, "ChestGrub",   "ChestGrub",   1, "armor", slot="chest"),
    Gear("Grub Leg Armor",     114, "LegsGrub",    "LegsGrub",    1, "armor", slot="legs"),
    Gear("Ladybug Head Armor", 115, "HeadLadybug", "HeadLadybug", 1, "armor", slot="head"),
    Gear("Ladybug Chest Armor", 116, "ChestLadybug", "ChestLadybug", 1, "armor", slot="chest"),
    Gear("Ladybug Leg Armor",  117, "LegsLadybug", "LegsLadybug", 1, "armor", slot="legs"),
    Gear("Bee Head Armor",     118, "HeadBee",     "HeadBee",     1, "armor", slot="head"),
    Gear("Bee Chest Armor",    119, "ChestBee",    "ChestBee",    1, "armor", slot="chest"),
    Gear("Bee Leg Armor",      120, "LegsBee",     "LegsBee",     1, "armor", slot="legs"),

    # --- Tier 2 weapons ---
    Gear("Stinger Spear",      60, "SpearTier2",     "SpearTier2",      2, "melee"),
    Gear("Red Ant Club",       61, "ClubAnt",        "AntClub",         2, "melee"),
    Gear("Spider Fang Dagger", 62, "DaggerSpider",   "DaggerSpider",    2, "melee", tool="dagger"),
    Gear("Mosquito Needle",    63, "RapierMosquito", "RapierMosquito",  2, "melee"),
    Gear("Black Ant Sword",    64, "SwordAntBlack",  "SwordAntBlack",   2, "melee"),
    Gear("Ant Queen Scepter",  65, "ScepterAntQueen", "AntQueenScepter", 2, "melee"),
    Gear("Insect Hammer",      66, "HammerTier2",    "HammerTier2",     2, "melee", tool="hammer"),
    Gear("Insect Axe",         67, "AxeTier2",       "AxeTier2",        2, "melee", tool="axe"),
    Gear("Black Ant Shovel",   68, "ShovelAntBlack", "ShovelAntBlack",  2, "tool", tool="shovel"),
    Gear("Insect Bow",         69, "BowTier2",       "BowTier2",        2, "ranged"),
    Gear("Crow Crossbow",      70, "CrossbowCrow",   "CrossbowCrow",    2, "ranged"),
    Gear("Salt Arrow",         71, "ArrowSalt",      "ArrowSalt",       2, "ammo"),
    Gear("Mint Arrow",         72, "ArrowMint",      "ArrowMint",       2, "ammo"),
    Gear("Spicy Arrow",        73, "ArrowSpicy",     "ArrowSpicy",      2, "ammo"),
    Gear("Roman Candle",       74, "RomanCandle",    "RomanCandle",     2, "other"),
    Gear("Everchar Torch",     75, "TorchCharcoal",  "TorchCharcoal",   2, "other"),
    Gear("Black Ant Shield",   76, "ShieldAntBlack", "ShieldAntBlack",  2, "shield"),
    Gear("Bone Trident",       77, "TridentBone",    "TridentBone",     2, "melee"),
    Gear("Feather Arrow",      78, "ArrowCrow",      "ArrowCrow",       2, "ammo"),

    # --- Tier 2 armor ---
    Gear("Red Ant Head Armor",    160, "HeadAnt",       "HeadAnt",       2, "armor", slot="head"),
    Gear("Red Ant Chest Armor",   161, "ChestAnt",      "ChestAnt",      2, "armor", slot="chest"),
    Gear("Red Ant Leg Armor",     162, "LegsAnt",       "LegsAnt",       2, "armor", slot="legs"),
    Gear("Black Ant Head Armor",  163, "HeadAntBlack",  "HeadAntBlack",  2, "armor", slot="head"),
    Gear("Black Ant Chest Armor", 164, "ChestAntBlack", "ChestAntBlack", 2, "armor", slot="chest"),
    Gear("Black Ant Leg Armor",   165, "LegsAntBlack",  "LegsAntBlack",  2, "armor", slot="legs"),
    Gear("Spider Head Armor",     166, "HeadSpider",    "HeadSpider",    2, "armor", slot="head"),
    Gear("Spider Chest Armor",    167, "ChestSpider",   "ChestSpider",   2, "armor", slot="chest"),
    Gear("Spider Leg Armor",      168, "LegsSpider",    "LegsSpider",    2, "armor", slot="legs"),

    # --- Tier 3 weapons ---
    Gear("Termite Axe",           130, "AxeTier3",            "AxeTier3",            3, "melee", tool="axe"),
    Gear("Black Ox Hammer",       131, "HammerTier3",         "HammerTier3",         3, "melee", tool="hammer"),
    Gear("Rusty Spear",           132, "SpearTier3",          "SpearTier3",          3, "melee"),
    Gear("Ladybird Shield",       133, "ShieldLadybird",      "ShieldLadybird",      3, "shield"),
    Gear("Black Ox Crossbow",     134, "CrossBowBlackOx",     "CrossBowBlackOx",     3, "ranged"),
    Gear("Tiger Mosquito Rapier", 135, "RapierMosquitoTiger", "RapierMosquitoTiger", 3, "melee"),
    Gear("Mint Mallet",           136, "MintMallet",          "MintMallet",          3, "melee"),
    Gear("Spicy Mallet",          137, "SpicyMallet",         "SpicyMallet",         3, "melee", ng_plus=True),
    Gear("Sour Mallet",           138, "SourMallet",          "SourMallet",          3, "melee", ng_plus=True),
    Gear("Salt Morning Star",     139, "MorningStarSalt",     "MorningStarSalt",     3, "melee"),
    Gear("Salt Pickaxe",          140, "PickaxeSalt",         "PickAxeSalty",        3, "melee", ng_plus=True),
    Gear("Mint Katana",           141, "KatanaMint",          "KatanaMint",          3, "melee", ng_plus=True),
    Gear("Spicy Katana",          142, "KatanaSpicy",         "KatanaSpicy",         3, "melee"),
    Gear("Sour Katana",           143, "KatanaSour",          "KatanaSour",          3, "melee", ng_plus=True),
    Gear("Mint Staff",            144, "StaffMint",           "StaffMint",           3, "melee"),
    Gear("Spicy Staff",           145, "StaffSpicy",          "StaffSpicy",          3, "melee"),
    Gear("Sour Staff",            146, "StaffSour",           "StaffSour",           3, "melee"),
    Gear("Mint Battle Axe",       147, "BattleAxeMint",       "BattleAxeMint",       3, "melee", ng_plus=True),
    Gear("Sour Battle Axe",       148, "BattleAxeSour",       "BattleAxeSour",       3, "melee"),
    Gear("Spicy Battle Axe",      149, "BattleAxeSpicy",      "BattleAxeSpicy",      3, "melee", ng_plus=True),
    Gear("Mint Greatsword",       150, "GreatswordMint",      "GreatswordMint",      3, "melee", ng_plus=True),
    Gear("Sour Greatsword",       151, "GreatswordSour",      "GreatswordSour",      3, "melee", ng_plus=True),
    Gear("Spicy Great Axe",       152, "GreatAxeSpicy",       "GreatAxeSpicy",       3, "melee", ng_plus=True),
    Gear("Mint Great Axe",        153, "GreatAxeMint",        "GreatAxeMint",        3, "melee", ng_plus=True),
    Gear("Spicy Warhammer",       154, "WarhammerSpicy",      "WarhammerSpicy",      3, "melee", ng_plus=True),
    Gear("Sour Warhammer",        155, "WarhammerSour",       "WarhammerSour",       3, "melee", ng_plus=True),
    # The only Tier 3 dagger (harvests Tier 3 dagger resources).
    Gear("Widow Dagger",          182, "DaggerSpiderWidow",   "DaggerSpiderWidow",   3, "melee", tool="dagger",
         material_fight=3),
    # Tier 1 dagger (an underwater tool; never counted as a combat weapon).
    Gear("Bone Dagger",           183, "BoneDivingKnife",     "BoneDivingKnife",     1, "tool", tool="dagger"),

    # --- Tier 3 armor ---
    Gear("Mantis Head Armor",     170, "HeadMantis",    "HeadMantis",    3, "armor", slot="head"),
    Gear("Mantis Chest Armor",    171, "ChestMantis",   "ChestMantis",   3, "armor", slot="chest"),
    Gear("Mantis Leg Armor",      172, "LegMantis",     "LegsMantis",    3, "armor", slot="legs"),
    Gear("Roly Poly Head Armor",  173, "HeadRolyPoly",  "HeadRolyPoly",  3, "armor", slot="head"),
    Gear("Roly Poly Chest Armor", 174, "ChestRolyPoly", "ChestRolyPoly", 3, "armor", slot="chest"),
    Gear("Roly Poly Leg Armor",   175, "LegsRolyPoly",  "LegsRolyPoly",  3, "armor", slot="legs"),
    Gear("Black Ox Head Armor",   176, "HeadBlackOx",   "HeadBlackOx",   3, "armor", slot="head"),
    Gear("Black Ox Chest Armor",  177, "ChestBlackOx",  "ChestBlackOx",  3, "armor", slot="chest"),
    Gear("Black Ox Leg Armor",    178, "LegsBlackOx",   "LegsBlackOx",   3, "armor", slot="legs"),
    Gear("Antlion Head Armor",    179, "HeadAntlion",   "HeadAntlion",   3, "armor", slot="head"),
    Gear("Antlion Chest Armor",   180, "ChestAntlion",  "ChestAntlion",  3, "armor", slot="chest"),
    Gear("Antlion Leg Armor",     181, "LegsAntlion",   "LegsAntlion",   3, "armor", slot="legs"),

    # --- Side armor (Gear.side); item rows assumed equal to recipe rows ---
    Gear("Koi Head Armor",        200, "KoiFishScaleHelmet",     "KoiFishScaleHelmet",     3, "armor", slot="head", side=True),
    Gear("Koi Chest Armor",       201, "KoiFishScaleChestPlate", "KoiFishScaleChestPlate", 3, "armor", slot="chest", side=True),
    Gear("Koi Leg Armor",         202, "KoiFishScaleLegPlates",  "KoiFishScaleLegPlates",  3, "armor", slot="legs", side=True),
    Gear("Fire Ant Head Armor",   203, "HeadAntFire",  "HeadAntFire",  3, "armor", slot="head", side=True),
    Gear("Fire Ant Chest Armor",  204, "ChestAntFire", "ChestAntFire", 3, "armor", slot="chest", side=True),
    Gear("Fire Ant Leg Armor",    205, "LegsAntFire",  "LegsAntFire",  3, "armor", slot="legs", side=True),
    Gear("Moth Head Armor",       206, "HeadMoth",     "HeadMoth",     3, "armor", slot="head", side=True),
    Gear("Moth Chest Armor",      207, "ChestMoth",    "ChestMoth",    3, "armor", slot="chest", side=True),
    Gear("Moth Leg Armor",        208, "LegsMoth",     "LegsMoth",     3, "armor", slot="legs", side=True),
    Gear("Wasp Head Armor",       209, "HeadWasp",     "HeadWasp",     3, "armor", slot="head", side=True),
    Gear("Wasp Chest Armor",      210, "ChestWasp",    "ChestWasp",    3, "armor", slot="chest", side=True),
    Gear("Wasp Leg Armor",        211, "LegsWasp",     "LegsWasp",     3, "armor", slot="legs", side=True),
    Gear("Eyepatch",              212, "HeadEyepatch",   "HeadEyepatch",   2, "armor", slot="head", side=True),
    Gear("Mite Hat",              213, "HeadMite",       "HeadMite",       1, "armor", slot="head", side=True),
    Gear("Firefly Head Lamp",     214, "HeadFirefly",    "HeadFirefly",    2, "armor", slot="head", side=True),
    Gear("Lucky Hat",             215, "HeadLuckyHat",   "HeadLuckyHat",   1, "armor", slot="head", side=True),
    Gear("Marksman's Cap",        216, "HeadCrowArcher", "HeadCrowArcher", 2, "armor", slot="head", side=True),
    Gear("Wizard Hat",            217, "HeadCrowWizard", "HeadCrowWizard", 2, "armor", slot="head", side=True),
    Gear("Termite Armor",         218, "ChestTermite",   "ChestTermite",   3, "armor", slot="chest", side=True),
    Gear("Aphid Slippers",        219, "LegsAphid",      "LegsAphid",      1, "armor", slot="legs", side=True),
]

GEAR_BY_NAME: Dict[str, Gear] = {g.name: g for g in GEAR}


def gear_names(tier: Optional[int] = None, kind: Optional[str] = None,
               tool: Optional[str] = None, slot: Optional[str] = None,
               min_tier: Optional[int] = None) -> List[str]:
    return [
        g.name for g in GEAR
        if (tier is None or g.tier == tier)
        and (min_tier is None or g.tier >= min_tier)
        and (kind is None or g.kind == kind)
        and (tool is None or g.tool == tool)
        and (slot is None or g.slot == slot)
    ]


# ProgressiveGear: the Nth copy unlocks the Nth recipe of its line. Logic
# still uses the gear names -- GroundedWorld.collect/remove credit them.
# The mod gets these lines through the generated ap_data.lua.
def _armor_line(slot: str) -> List[str]:
    sets = ["Clover", "Acorn", "Grub", "Bee", "Ladybug", "Red Ant", "Black Ant", "Spider",
            "Roly Poly", "Antlion", "Black Ox", "Mantis"]
    piece = {"head": "Head", "chest": "Chest", "legs": "Leg"}[slot]
    return [f"{s} {piece} Armor" for s in sets]


PROGRESSIVE_LINES: Dict[str, List[str]] = {
    "Progressive Axe": ["Pebblet Axe", "Insect Axe", "Termite Axe"],
    "Progressive Hammer": ["Pebblet Hammer", "Insect Hammer", "Black Ox Hammer"],
    "Progressive Shovel": ["Acorn Shovel", "Black Ant Shovel"],
    "Progressive Spear": ["Pebblet Spear", "Stinger Spear", "Rusty Spear"],
    "Progressive Bow": ["Sprig Bow", "Insect Bow", "Crow Crossbow", "Black Ox Crossbow"],
    "Progressive Head Armor": _armor_line("head"),
    "Progressive Chest Armor": _armor_line("chest"),
    "Progressive Leg Armor": _armor_line("legs"),
}

# gear name -> progressive item that replaces it
PROGRESSIVE_GEAR: Dict[str, str] = {
    gear: prog for prog, line in PROGRESSIVE_LINES.items() for gear in line
}
