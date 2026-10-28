"""
Region graph: a hub (Grasslands) with every other region one hop away.
Region connections are ungated except the Haze (Gas Mask); everything else
is gated per location in rules.py.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Region

from . import rules
from .itemsanity import itemsanity_location_names
from .killsanity import KILLSANITY_BOSS_NAMES, KILL_LOCATION_PREFIX
from .goldcards import GOLD_CARD_LOCATION_PREFIX, GOLD_CARD_PROGRESS_ITEM, gold_card_location_names
from .locations import event_locations, locations_by_region
from .location_renames import ap_name
from .mutations import MUTATION_PREFIX
from .landmarks import LANDMARK_PREFIX
from .shop import SHOP_LOCATION_PREFIX
from .review_data import DISABLED_LOCATIONS

if TYPE_CHECKING:
    from . import GroundedWorld


def create_regions(world: "GroundedWorld") -> None:
    player = world.player
    multiworld = world.multiworld
    options = world.options

    region_names = list(locations_by_region.keys())
    regions = {name: Region(name, player, multiworld) for name in ["Menu", *region_names]}

    for name, region in regions.items():
        if name == "Menu":
            continue
        location_type = world.location_type
        for loc_name, _offset in locations_by_region[name]:
            if _skip_location(loc_name, options):
                continue
            region.add_locations({ap_name(loc_name): world.location_name_to_id[ap_name(loc_name)]}, location_type)

    regions["Menu"].connect(regions["Grasslands"])
    regions["Grasslands"].connect(regions["Haze"], rule=lambda state: rules.has_gas_mask(state, player))

    if "Itemsanity" in regions:
        regions["Grasslands"].connect(regions["Itemsanity"])

    if "Killsanity" in regions:
        regions["Grasslands"].connect(regions["Killsanity"])

    if "Craftsanity" in regions:
        regions["Grasslands"].connect(regions["Craftsanity"])

    if "Gold Cards" in regions:
        regions["Grasslands"].connect(regions["Gold Cards"])

    if "Molars" in regions:
        regions["Grasslands"].connect(regions["Molars"])

    regions["Grasslands"].connect(regions["Mutations"])
    regions["Grasslands"].connect(regions["Landmarks"])
    regions["Grasslands"].connect(regions["BURG.L Shop"])

    for region in regions.values():
        multiworld.regions.append(region)

    for loc_name, region_name, item_name in event_locations:
        regions[region_name].add_event(loc_name, item_name)

    # Goals: locked progress items on the required locations. Those
    # locations are ungated, so reachability can't tell "done" from "not yet"
    # -- the goal counts the progress items instead (state.has(..., n)).
    if options.goal.value == options.goal.option_gold_cards:
        for loc_name in gold_card_location_names:
            location = multiworld.get_location(ap_name(loc_name), player)
            location.place_locked_item(world.create_item(GOLD_CARD_PROGRESS_ITEM))

    if options.goal.value == options.goal.option_boss_only:
        excluded = set(options.excluded_bosses.value)
        for boss_name in KILLSANITY_BOSS_NAMES:
            if boss_name in excluded:
                continue
            location = multiworld.get_location(ap_name(KILL_LOCATION_PREFIX + boss_name), player)
            location.place_locked_item(world.create_item("Boss Kill Progress"))

    if options.goal.value == options.goal.option_story_boss_only:
        for boss_name in ("Assistant Manager", "Mant", "Director Schmector"):
            location = multiworld.get_location(ap_name(KILL_LOCATION_PREFIX + boss_name), player)
            location.place_locked_item(world.create_item("Boss Kill Progress"))

    if options.goal.value == options.goal.option_short:
        for boss_name in ("Assistant Manager", "Mant"):
            location = multiworld.get_location(ap_name(KILL_LOCATION_PREFIX + boss_name), player)
            location.place_locked_item(world.create_item("Boss Kill Progress"))

    if options.goal.value in (
        options.goal.option_infected_broodmother,
        options.goal.option_infected_broodmother_and_embiggening,
    ):
        location = multiworld.get_location(ap_name("Defeat the Infected Broodmother"), player)
        location.place_locked_item(world.create_item("Boss Kill Progress"))

    if options.goal.value in (
        options.goal.option_embiggening,
        options.goal.option_infected_broodmother_and_embiggening,
    ):
        location = multiworld.get_location(ap_name("Go Big Or Never Go Home (Ending)"), player)
        location.place_locked_item(world.create_item("Victory Progress"))
    # Itemsanity goal: no locked items (that left no free location to start
    # with); see __init__.py's completion condition and the client's
    # _itemsanity_goal_met.


def _skip_location(loc_name: str, options) -> bool:
    # Unticked in location_review.txt.
    if loc_name in DISABLED_LOCATIONS:
        return True
    is_boss_check = loc_name.startswith("Defeat ")
    is_gold_card_check = loc_name.startswith(GOLD_CARD_LOCATION_PREFIX)
    if is_boss_check and not options.include_boss_checks:
        return True
    if is_gold_card_check and options.goal.value != options.goal.option_gold_cards:
        return True
    if loc_name == "Go Big Or Never Go Home (Ending)" and options.goal.value not in (
        options.goal.option_embiggening, options.goal.option_infected_broodmother_and_embiggening,
    ):
        return True
    if loc_name.startswith(MUTATION_PREFIX) and not options.mutation_checks:
        return True
    if loc_name.startswith(LANDMARK_PREFIX) and not options.landmark_checks:
        return True
    if loc_name.startswith(SHOP_LOCATION_PREFIX) and not options.shop_checks:
        return True
    return False
