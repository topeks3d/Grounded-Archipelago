"""
Access rules. Every location's requirement is a list of tokens (see
_TOKEN_RULES):

  c1 / c2 / c3        combat tier: c1 = a Tier 1 melee weapon; cN = c(N-1)
                      plus a Tier N melee weapon AND Tier N armor covering
                      head, chest and legs (any mix of sets).
  axe1..3 / hammer1..3 / shovel1..2 / dagger1..3
                      craftable harvesting tool of at least that tier
                      (Pebblet -> Insect -> Termite Axe / Black Ox Hammer;
                      Acorn -> Black Ant Shovel; Bone -> Spider Fang ->
                      Widow Dagger). "shovel" = shovel1. Dagger resources
                      are all underwater, so daggerN includes Diving Gear.
  gas / dive          Gas Mask (Haze) / Diving Gear (deep pond).
  canister            the Haze canister plugged (Gas Mask + Tier 2 for the
                      Haze's creatures). Gates Spiky Bur, some infected
                      bugs and the Infected Broodmother's arena. (Meeting
                      Wendell also unlocks Spiky Bur; not modelled -- the
                      canister is the conservative route.)
  undershed           Undershed (the last story area): Zip Line Rig, Gas
                      Mask, Diving Gear and Tier 3.
  smoothie / cookery / oven
                      Smoothie Station / Cookery (meals) / Oven (globs,
                      jewels, boss keys) building unlocks. (The Roasting
                      Spit is unlocked from the start.)
  jelly               every DeDuper Jelly Bundle (NG+ weapon recipes).
  kill:<boss>         whatever that boss kill requires (see BOSS_REQUIREMENTS).

Item and landmark requirements come from location_review.txt (via
review_data.py). Everything is deliberately conservative: when unsure, gate
a step later rather than earlier.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, Iterable, Tuple

from worlds.generic.Rules import add_rule

from .craftsanity import (CRAFT_LOCATION_PREFIX, CRAFTSANITY_LOCATION_TO_GATE_ITEM,
                          CRAFTSANITY_ROW_TO_DISPLAY_NAME, CONSUMABLES_ROWS)
from .mutations import MUTATION_REQUIREMENTS
from .gear import GEAR, GEAR_BY_NAME, gear_names
from .goldcards import GOLD_CARD_LOCATION_PREFIX
from .items import JELLY_BUNDLE, JELLY_BUNDLE_COUNT
from .itemsanity import ITEM_LOCATION_PREFIX
from .killsanity import KILL_LOCATION_PREFIX
from .location_renames import ap_name
from .review_data import ITEM_NEEDS, LANDMARK_NEEDS
from .molars import MOLAR_LOCATION_PREFIX

if TYPE_CHECKING:
    from BaseClasses import CollectionState

    from . import GroundedWorld

Rule = Callable[["CollectionState", int], bool]


# ---------------------------------------------------------------------------
# Gear-derived building blocks
#
# Combat tiers chain strictly: Tier N gear only counts once you can already
# fight Tier N-1 creatures, because that's where its materials come from.
# (Otherwise holding e.g. only Black Ox armor recipes would claim Tier 2
# fights are possible, though Black Ox parts need a Tier 2 fight first.)
# Mantis armor is left out of armor coverage entirely: it's made from the
# Mantis boss, which already needs Tier 3.
# ---------------------------------------------------------------------------
_EXCLUDED_FROM_COVERAGE = {"Mantis Head Armor", "Mantis Chest Armor", "Mantis Leg Armor"} | {g.name for g in GEAR if g.side}

# NG+ weapons only count once their DeDuper Jelly is in hand (even with
# RecipeShuffle).
_MELEE = {
    t: tuple(n for n in gear_names(kind="melee", tier=t) if not GEAR_BY_NAME[n].ng_plus)
    for t in (1, 2, 3)
}
# Gear whose materials need a fight of its own tier can't help reach that
# tier (the Widow Dagger needs the Black Widow, a Tier 3 fight).
_MELEE = {t: tuple(n for n in names if (GEAR_BY_NAME[n].material_fight or 0) < t) for t, names in _MELEE.items()}
_NG_PLUS_MELEE = tuple(g.name for g in GEAR if g.ng_plus and g.kind == "melee")
_ARMOR = {
    (t, s): tuple(n for n in gear_names(kind="armor", slot=s, tier=t) if n not in _EXCLUDED_FROM_COVERAGE)
    for t in (1, 2, 3) for s in ("head", "chest", "legs")
}
_TOOL_KINDS = ("axe", "hammer", "shovel", "dagger")
# (tool, tier, combat tier its materials need) -> gear names
_TOOLS: Dict[Tuple[str, int, int], Tuple[str, ...]] = {}
for _g in GEAR:
    if _g.tool:
        _key = (_g.tool, _g.tier, _g.material_fight if _g.material_fight is not None else _g.tier - 1)
        _TOOLS[_key] = _TOOLS.get(_key, ()) + (_g.name,)


def has_all_jelly(state: "CollectionState", player: int) -> bool:
    return state.has(JELLY_BUNDLE, player, JELLY_BUNDLE_COUNT)


def has_melee(state: "CollectionState", player: int, tier: int) -> bool:
    if state.has_any(_MELEE[tier], player):
        return True
    return tier == 3 and state.has_any(_NG_PLUS_MELEE, player) and has_all_jelly(state, player)


def has_armor_tier(state: "CollectionState", player: int, tier: int) -> bool:
    return all(state.has_any(_ARMOR[(tier, slot)], player) for slot in ("head", "chest", "legs"))


def can_fight(state: "CollectionState", player: int, tier: int) -> bool:
    if tier <= 0:
        return True
    if tier == 1:
        return has_melee(state, player, 1)
    return (
        can_fight(state, player, tier - 1)
        and has_melee(state, player, tier)
        and has_armor_tier(state, player, tier)
    )


def has_tool(state: "CollectionState", player: int, tool: str, min_tier: int) -> bool:
    """A harvesting tool of at least min_tier that the player can actually
    craft (Tier N tools need Tier N-1 fights for their materials)."""
    return any(
        state.has_any(names, player) and can_fight(state, player, fight)
        for (kind, t, fight), names in _TOOLS.items()
        if kind == tool and t >= min_tier
    )


# Kept for anything still importing the old names.
def can_fight_tier2_creatures(state: "CollectionState", player: int) -> bool:
    return can_fight(state, player, 2)


def can_fight_tier3_creatures(state: "CollectionState", player: int) -> bool:
    return can_fight(state, player, 3)


def has_gas_mask(state: "CollectionState", player: int) -> bool:
    return state.has("Gas Mask", player)


def has_diving_gear(state: "CollectionState", player: int) -> bool:
    return state.has("Diving Gear", player)


def can_reach_upper_yard(state: "CollectionState", player: int) -> bool:
    return state.has_all(("Zip Line Rig", "Gas Mask", "Diving Gear"), player) and can_fight(state, player, 2)


def can_reach_undershed(state: "CollectionState", player: int) -> bool:
    return can_reach_upper_yard(state, player) and can_fight(state, player, 3)


def ending_boss(excluded_bosses) -> str:
    """The boss that must be beaten before the ending counts (the mod also
    blocks the ending in-game until then): Director Schmector, or the Mant
    if Schmector is in ExcludedBosses. Keep in sync with ending_gate.lua."""
    return "Mant" if "Director Schmector" in excluded_bosses else "Director Schmector"


_TOKEN_RULES: Dict[str, Rule] = {
    "c1": lambda s, p: can_fight(s, p, 1),
    "c2": lambda s, p: can_fight(s, p, 2),
    "c3": lambda s, p: can_fight(s, p, 3),
    "gas": has_gas_mask,
    "dive": has_diving_gear,
    "canister": lambda s, p: has_gas_mask(s, p) and can_fight(s, p, 2),
    "undershed": can_reach_undershed,
    "smoothie": lambda s, p: s.has("Smoothie Station", p),
    "cookery": lambda s, p: s.has("Cookery", p),
    "oven": lambda s, p: s.has("Oven", p),
    "shovel": lambda s, p: has_tool(s, p, "shovel", 1),  # same as shovel1
    "jelly": has_all_jelly,
}
for _tier in (1, 2, 3):
    _TOKEN_RULES[f"axe{_tier}"] = (lambda t: lambda s, p: has_tool(s, p, "axe", t))(_tier)
    _TOKEN_RULES[f"hammer{_tier}"] = (lambda t: lambda s, p: has_tool(s, p, "hammer", t))(_tier)
    # Daggers: Bone (Tier 1), Spider Fang (Tier 2), Widow (Tier 3). Everything
    # they harvest is underwater, so they also need the Diving Gear.
    _TOKEN_RULES[f"dagger{_tier}"] = (lambda t: lambda s, p: has_diving_gear(s, p) and has_tool(s, p, "dagger", t))(_tier)
for _tier in (1, 2):  # no Tier 3 shovel exists
    _TOKEN_RULES[f"shovel{_tier}"] = (lambda t: lambda s, p: has_tool(s, p, "shovel", t))(_tier)


# ---------------------------------------------------------------------------
# Bosses
# ---------------------------------------------------------------------------
# Story order: the Undershed (Mant, Director Schmector) comes last.
# "oven": these four are summoned with a key crafted in the Oven
# (BossKeyBM / BossKeyIBM / BossKeyMantis / BossKeyWaspQueen, all
# CraftingBuilding.Forge in the RECIPE_ROW dump).
BOSS_REQUIREMENTS: Dict[str, Tuple[str, ...]] = {
    "Hedge Broodmother": ("c3", "oven"),
    "Black Widow": ("c3",),
    "Mantis": ("c3", "oven"),
    "Wasp Queen": ("c3", "oven"),
    "Assistant Manager": ("c3",),
    "Mant": ("undershed", "c3"),
    "Director Schmector": ("undershed", "c3"),
    "Infected Broodmother": ("gas", "canister", "c3", "oven"),
}


def _build_rule(tokens: Iterable[str]) -> Rule:
    rules = []
    for token in tokens:
        if token.startswith("kill:"):
            rules.append(_build_rule(BOSS_REQUIREMENTS[token[5:]]))
        else:
            rules.append(_TOKEN_RULES[token])
    rules = tuple(rules)
    if not rules:
        return lambda state, player: True
    return lambda state, player: all(rule(state, player) for rule in rules)


# ---------------------------------------------------------------------------
# Itemsanity: item display name -> requirement tokens, straight from the
# "needs:" notes in location_review.txt (see review_data.py).
# ---------------------------------------------------------------------------
ITEM_REQUIREMENTS: Dict[str, Tuple[str, ...]] = dict(ITEM_NEEDS)


# ---------------------------------------------------------------------------
# Craftsanity: on top of the recipe item itself, the materials. Tier N gear
# is built from Tier N creatures, which you fight with Tier N-1 gear.
# ---------------------------------------------------------------------------
_CRAFT_TIER_BASE = {1: (), 2: ("c1",), 3: ("c2",)}

CRAFT_EXTRA_REQUIREMENTS: Dict[str, Tuple[str, ...]] = {
    # Gear needing a specific resource beyond its tier baseline
    "Widow Dagger": ("kill:Black Widow",),
    "Bone Dagger": ("dive",),  # an underwater tool (materials unconfirmed)
    "Acorn Head Armor": ("hammer1",), "Acorn Chest Armor": ("hammer1",), "Acorn Leg Armor": ("hammer1",),
    "Grub Head Armor": ("c1",), "Grub Chest Armor": ("c1",), "Grub Leg Armor": ("c1",),
    "Ladybug Head Armor": ("c2",), "Ladybug Chest Armor": ("c2",), "Ladybug Leg Armor": ("c2",),
    "Bee Head Armor": ("c1",), "Bee Chest Armor": ("c1",), "Bee Leg Armor": ("c1",),
    "Ant Queen Scepter": ("c2",),
    "Salt Arrow": ("c2",), "Mint Arrow": ("c2", "hammer2"), "Spicy Arrow": ("c2",),
    # Gunpowder Clump (axe3) / EverChar Coal Chunk (hammer3)
    "Roman Candle": ("axe3",), "Everchar Torch": ("hammer3",), "Bone Trident": ("dive",),
    "Mantis Head Armor": ("kill:Mantis",), "Mantis Chest Armor": ("kill:Mantis",),
    "Mantis Leg Armor": ("kill:Mantis",),
    # Sour weapons need Sour Globs (c3, hammer3, oven)
    "Sour Mallet": ("c3", "hammer3", "oven"), "Sour Katana": ("c3", "hammer3", "oven"),
    "Sour Staff": ("c3", "hammer3", "oven"), "Sour Battle Axe": ("c3", "hammer3", "oven"),
    "Sour Greatsword": ("c3", "hammer3", "oven"), "Sour Warhammer": ("c3", "hammer3", "oven"),
    "Mint Mallet": ("hammer2",), "Mint Katana": ("hammer2",), "Mint Staff": ("hammer2",),
    "Mint Battle Axe": ("hammer2",), "Mint Greatsword": ("hammer2",), "Mint Great Axe": ("hammer2",),
    # Side armor (gear.py's Gear.side) -- from the materials' itemsanity needs
    "Koi Head Armor": ("dive", "shovel1"), "Koi Chest Armor": ("dive", "shovel1"),
    "Koi Leg Armor": ("dive", "shovel1"),
    "Fire Ant Head Armor": ("c3",), "Fire Ant Chest Armor": ("c3",), "Fire Ant Leg Armor": ("c3",),
    "Moth Head Armor": ("c3",), "Moth Chest Armor": ("c3",), "Moth Leg Armor": ("c3",),
    "Wasp Head Armor": ("c3",), "Wasp Chest Armor": ("c3",), "Wasp Leg Armor": ("c3",),
    "Termite Armor": ("c3",), "Eyepatch": ("c2",), "Mite Hat": ("c1",), "Firefly Head Lamp": ("c2",),
    "Lucky Hat": ("axe1",), "Marksman's Cap": ("axe2",), "Wizard Hat": ("axe2",),
    "Aphid Slippers": ("c1",), "Fin Flops": ("dive", "dagger1"),
    # Consumables / utilities
    "Fiber Smoothie": ("smoothie",), "Gastro Goo Smoothie": ("smoothie", "c1"),
    "Fuzz On The Rocks Smoothie": ("smoothie", "c1"), "Aphid Smoothie": ("smoothie", "c1"),
    "Berry Smoothie": ("smoothie",), "Water Breathing Smoothie": ("smoothie", "c1"),
    "Swim Speed Smoothie": ("smoothie", "c2"), "Attack Smoothie": ("smoothie", "c1"),
    "Ant Smoothie": ("smoothie", "c1"), "Human Food Smoothie": ("smoothie", "axe1"),
    "Wasp Smoothie": ("smoothie", "c3"), "Boss Smoothie": ("smoothie", "c3", "kill:Hedge Broodmother"),
    "Canteen": ("c1",), "Upgraded Canteen": ("c2",), "Charcoal Canteen": ("hammer2",),
    "Acorn Granola": ("hammer1",), "Bandage": (), "Boatman Fin Soup": ("c2",),
    "Healing Bomb": ("c2",),
    "Spaghetflea": ("c1",), "Larvagna": ("c1",), "Miteloaf": ("c1",), "Gnatchos": ("c1",),
    "Spider Slider": ("c2",), "Mac N Bees": ("c1",), "Funguspacho": ("c2", "gas"), "Omelant": ("c2",),
    "Quesadillantlion": ("c3",), "Black Ox Burger": ("c3",), "Termite Delight": ("c3",),
    "Tadpole Pudding": ("c2",), "Wasperole": ("c3",), "Empanadust": ("c3",),
    "Torch": (), "Upgraded Torch": ("c1",), "Flare": ("c1",), "Smoke Screen": ("c2",),
    "Binoculars": ("c1",), "Leaf Blower": ("c2",), "Repair Hammer": ("c1",),
    "Armor Repair Kit": ("c1",), "Advanced Armor Repair Kit": ("c2",), "Decoy Bait": ("c1",),
    "Diving Lantern": ("dive",), "Upgraded Diving Lantern": ("dive", "c2"),
    "Firefly Lantern": ("c1",),
}


# Meals (every MealTier* recipe) are made in the Cookery.
for _row in CONSUMABLES_ROWS:
    if _row.startswith("MealTier"):
        _meal = CRAFTSANITY_ROW_TO_DISPLAY_NAME[_row]
        CRAFT_EXTRA_REQUIREMENTS[_meal] = CRAFT_EXTRA_REQUIREMENTS.get(_meal, ()) + ("cookery",)

# NG+ weapons also need their DeDuper Jelly.
for _gear in GEAR:
    if _gear.ng_plus:
        CRAFT_EXTRA_REQUIREMENTS[_gear.name] = CRAFT_EXTRA_REQUIREMENTS.get(_gear.name, ()) + ("jelly",)


def _craft_requirement(display_name: str, shuffled_recipes=frozenset()) -> Tuple[str, ...]:
    gear = GEAR_BY_NAME.get(display_name)
    base = _CRAFT_TIER_BASE[gear.tier] if gear else ()
    if gear and gear.recipe_row in shuffled_recipes:
        # Ingredients were replaced by recipe_shuffle.py, which only draws
        # from materials within the tier baseline -- the vanilla extras
        # below no longer apply.
        return base
    return base + CRAFT_EXTRA_REQUIREMENTS.get(display_name, ())


# ---------------------------------------------------------------------------
# Gold cards: tier of the creature that drops them.
# ---------------------------------------------------------------------------
GOLD_CARD_REQUIREMENTS: Dict[str, Tuple[str, ...]] = {
    "BestiaryAntRedWorkerGold": ("c1",), "BestiaryAphidGold": ("c1",), "BestiaryGnatGold": ("c1",),
    "BestiaryGrubGold": ("c1",), "BestiaryLarvaGold": ("c1",), "BestiaryMiteGold": ("c1",),
    "BestiaryWeevilGold": ("c1",), "BestiaryWaterFleaGold": ("c1",), "BestiaryTadpoleGold": ("c1",),
    "BestiaryFireflyGold": ("c2",), "BestiaryStinkbugGold": ("c2",), "BestiaryBeeGold": ("c2",),
    "BestiaryAntRedSoldierGold": ("c2",), "BestiaryAntBlackWorkerGold": ("c2",),
    "BestiaryAntBlackSoldierGold": ("c2",), "BestiaryLadybugGold": ("c2",),
    "BestiaryMosquitoGold": ("c2",), "BestiaryBombardierGold": ("c1",),
    "BestiarySpiderOrbGold": ("c2",), "BestiarySpiderOrbJrGold": ("c2",),
    "BestiarySpiderWolfGold": ("c2",), "BestiarySpiderlingGold": ("c2",),
    "BestiarySpiderDivingBellGold": ("c2", "dive"), "BestiaryWaterBoatmanGold": ("c2",),
    "BestiaryWaterFleaSpinyGold": ("c2", "dive"), "BestiaryRolyPolyGold": ("c3",),
    "BestiaryMothGold": ("c3",), "BestiaryArcRGold": ("c2", "gas"), "BestiaryTazTGold": ("c2", "dive"),
    "BestiaryLarvaInfectedGold": ("canister",), "BestiaryWeevilInfectedGold": ("canister",),
    "BestiaryGnatInfectedGold": ("canister",), "BestiaryMiteInfectedGold": ("canister",),
    "BestiaryAntInfectedWorkerGold": ("canister",), "BestiaryAntInfectedSoldierGold": ("canister",),
    "BestiaryLadybugInfectedGold": ("canister",), "BestiaryRolyPolySicklyGold": ("c3", "gas"),
    "BestiaryMiteDustGold": ("c3",), "BestiaryStinkbugGreenShieldGold": ("c3",),
    "BestiaryGnatMeatyGold": ("c2",),
    "BestiaryAntlionGold": ("c3",), "BestiaryBlackOxGold": ("c3",), "BestiaryMosquitoTigerGold": ("c3",),
    "BestiaryMiteTickGold": ("c3",), "BestiaryScarabGold": ("c3",),
    "BestiaryTermiteSoldierGold": ("c3",), "BestiaryTermiteWorkerGold": ("c3",),
    "BestiaryTermiteKingGold": ("c3",), "BestiarySpiderBlackWidowGold": ("kill:Black Widow",),
    "BestiarySpiderlingWidowGold": ("c3",), "BestiarySpiderWolfInfectedGold": ("c3", "canister"),
    "BestiaryAntFireSoldierGold": ("c3",), "BestiaryAntFireWorkerGold": ("c3",),
    "BestiaryLadybugUpperyardGold": ("c3",), "BestiaryLarvaCharcoalGold": ("c3",),
    "BestiaryWaspDroneGold": ("c3",), "BestiaryWaspGold": ("c3",),
    "BestiaryArcRBossGold": ("kill:Assistant Manager",), "BestiaryTazTRuzTGold": ("c3", "dive"),
    "BestiaryMantisGold": ("kill:Mantis",), "BestiaryWaspQueenGold": ("kill:Wasp Queen",),
    "BestiaryMantGold": ("kill:Mant",), "BestiarySchmectorGold": ("kill:Director Schmector",),
    "BestiarySpiderBossBroodmotherGold": ("kill:Hedge Broodmother",),
    "BestiaryBossIBMGold": ("kill:Infected Broodmother",),
}


# ---------------------------------------------------------------------------
# Molar milestones: more molars need more of the yard.
# ---------------------------------------------------------------------------
def _molar_requirement(threshold: int) -> Tuple[str, ...]:
    if threshold <= 10:
        return ("c1",)
    if threshold <= 25:
        return ("c2",)
    if threshold <= 40:
        return ("c2", "gas", "dive")
    if threshold <= 55:
        return ("c3",)
    return ("c3", "undershed")


def location_rules(excluded_bosses=(), shuffled_recipes=frozenset()) -> Dict[str, Rule]:
    """Every location's full rule, keyed by the mod's location name. Used by
    set_rules and by the client's Tracker tab (which calls each rule with a
    stand-in state built from the items received)."""
    from .molars import MOLAR_MILESTONES

    parts: Dict[str, list] = {}

    def gate(loc_name: str, tokens: Iterable[str]) -> None:
        tokens = tuple(tokens)
        if tokens:
            parts.setdefault(loc_name, []).append(_build_rule(tokens))

    # Bosses
    for boss, tokens in BOSS_REQUIREMENTS.items():
        gate(KILL_LOCATION_PREFIX + boss, tokens)
    gate("Defeat the Infected Broodmother", BOSS_REQUIREMENTS["Infected Broodmother"])

    # The real ending: the whole story, then beating the final boss (see
    # ending_boss) -- the mod won't let the ending count before that kill.
    gate("Go Big Or Never Go Home (Ending)", ("undershed", "c3", "kill:" + ending_boss(excluded_bosses)))

    # Itemsanity
    for item_name, tokens in ITEM_REQUIREMENTS.items():
        gate(ITEM_LOCATION_PREFIX + item_name, tokens)

    # Craftsanity: the recipe itself (gate item), then the materials.
    for loc_name, gate_item in CRAFTSANITY_LOCATION_TO_GATE_ITEM.items():
        parts.setdefault(loc_name, []).append(
            lambda state, player, gate_item=gate_item: state.has(gate_item, player))
        gate(loc_name, _craft_requirement(loc_name[len(CRAFT_LOCATION_PREFIX):], shuffled_recipes))

    # Mutation milestones
    for loc_name, tokens in MUTATION_REQUIREMENTS.items():
        gate(loc_name, tokens)

    # Landmarks ("needs:" in location_review.txt)
    for loc_name, tokens in LANDMARK_NEEDS.items():
        gate(loc_name, tokens)

    # Gold cards
    for row_name, tokens in GOLD_CARD_REQUIREMENTS.items():
        gate(GOLD_CARD_LOCATION_PREFIX + row_name, tokens)

    # Molars
    for threshold in MOLAR_MILESTONES:
        gate(MOLAR_LOCATION_PREFIX + str(threshold), _molar_requirement(threshold))

    def combine(rules):
        rules = tuple(rules)
        return lambda state, player: all(rule(state, player) for rule in rules)

    return {name: combine(rules) for name, rules in parts.items()}


def set_rules(world: "GroundedWorld") -> None:
    player = world.player
    all_rules = location_rules(world.options.excluded_bosses.value, frozenset(world.recipe_ingredients))
    for loc_name, rule in all_rules.items():
        if _has_location(world, loc_name):
            add_rule(world.multiworld.get_location(ap_name(loc_name), player),
                     lambda state, rule=rule: rule(state, player))


def _has_location(world: "GroundedWorld", loc_name: str) -> bool:
    try:
        world.multiworld.get_location(ap_name(loc_name), world.player)
        return True
    except KeyError:
        return False
