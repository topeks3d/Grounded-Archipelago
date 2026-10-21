from __future__ import annotations

from typing import Any, Dict, List

from BaseClasses import CollectionState, Item, ItemClassification as IC, Location, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.LauncherComponents import Component, Type, components
from worlds.LauncherComponents import launch as launch_component

from . import regions as regions_module
from . import rules as rules_module
from .items import (
    BASE_ID as ITEM_BASE_ID,
    FILLER_WEIGHTS,
    filler_item_names,
    item_name_groups,
    item_name_to_id,
    item_table,
)
from .location_renames import ap_name
from .review_data import DISABLED_LOCATIONS
from .locations import itemsanity_location_names, killsanity_location_names, location_name_groups, location_name_to_id
from .consumables import EARLY_CONSUMABLES
from .craftsanity import craftsanity_location_names
from .gear import GEAR, PROGRESSIVE_GEAR, PROGRESSIVE_LINES
from .goldcards import GOLD_CARD_PROGRESS_ITEM, gold_card_location_names
from .options import GroundedOptions
from . import drop_shuffle, recipe_shuffle


def _launch_client(*args: str) -> None:
    # Lazy import: generation shouldn't load CommonClient.
    from .client import launch
    launch_component(launch, name="GroundedClient", args=args)


components.append(Component(
    "Grounded Client",
    func=_launch_client,
    component_type=Type.CLIENT,
    game_name="Grounded",
))


class GroundedWeb(WebWorld):
    tutorials = [
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up the Grounded randomizer connected to an Archipelago Multiworld.",
            "English",
            "setup_en.md",
            "setup/en",
            ["your-name-here"],
        )
    ]
    theme = "grassFlowers"


class GroundedItem(Item):
    game: str = "Grounded"


class GroundedLocation(Location):
    game: str = "Grounded"


class GroundedWorld(World):
    """
    You've been shrunk to the size of an ant and dropped in a suburban
    backyard. Gather resources, craft tools and armor, befriend BURG.L,
    uncover the labs hidden around the yard, and figure out how to get big
    again -- all while avoiding being eaten by spiders.
    """

    game = "Grounded"
    web = GroundedWeb()

    options_dataclass = GroundedOptions
    options: GroundedOptions

    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id
    item_name_groups = item_name_groups
    location_name_groups = location_name_groups

    location_type = GroundedLocation

    required_client_version = (0, 5, 1)

    # recipe row -> [[item_row, count], ...]; empty unless RecipeShuffle is on.
    recipe_ingredients: Dict[str, List[List]]

    # vanilla item row -> replacement row; empty unless CreatureDropShuffle is on.
    drop_mapping: Dict[str, str]

    # Universal Tracker: it can rebuild this world from slot_data alone.
    ut_can_gen_without_yaml = True

    def generate_early(self) -> None:
        # Universal Tracker regenerates the world with the room's slot_data
        # passed through -- use it instead of the (absent) YAML so its logic
        # matches the real seed, including the exact recipe shuffle.
        passthrough = getattr(self.multiworld, "re_gen_passthrough", {}).get(self.game)
        if passthrough:
            self._apply_slot_data(passthrough)
            self.recipe_ingredients = dict(passthrough.get("recipe_shuffle") or {})
            self.drop_mapping = dict(passthrough.get("creature_drop_shuffle") or {})
        else:
            self.recipe_ingredients = (
                recipe_shuffle.generate(self.random) if self.options.recipe_shuffle.value else {}
            )
            self.drop_mapping = (
                drop_shuffle.generate(self.random) if self.options.creature_drop_shuffle.value else {}
            )

        # Tier 1 recipes go early: nearly every check needs a Tier 1 weapon or
        # tool, and research no longer hands them out. With ProgressiveGear,
        # that's one copy per Tier 1 piece in each line.
        early = self.multiworld.early_items[self.player]
        for gear in GEAR:
            if gear.tier != 1 or gear.side:
                continue
            if self.options.progressive_gear and gear.name in PROGRESSIVE_GEAR:
                prog = PROGRESSIVE_GEAR[gear.name]
                early[prog] = early.get(prog, 0) + 1
            else:
                early[gear.name] = 1
        # Bandages too: healing from the start, alongside the Pebblet tools.
        for name in EARLY_CONSUMABLES:
            early[name] = 1

    def _apply_slot_data(self, slot_data: Dict[str, Any]) -> None:
        options = self.options
        options.goal.value = slot_data.get("goal", options.goal.value)
        options.excluded_bosses.value = set(slot_data.get("excluded_bosses", []))
        options.include_boss_checks.value = int(slot_data.get("include_boss_checks", True))
        options.gold_card_goal_amount.value = slot_data.get("gold_card_goal_amount", options.gold_card_goal_amount.value)
        options.recipe_shuffle.value = int(bool(slot_data.get("recipe_shuffle")))
        options.creature_drop_shuffle.value = int(bool(slot_data.get("creature_drop_shuffle")))
        options.progressive_gear.value = int(slot_data.get("progressive_gear", False))
        options.mutation_checks.value = int(slot_data.get("mutation_checks", False))
        options.landmark_checks.value = int(slot_data.get("landmark_checks", False))

    @staticmethod
    def interpret_slot_data(slot_data: Dict[str, Any]) -> Dict[str, Any]:
        return slot_data

    def create_regions(self) -> None:
        regions_module.create_regions(self)

    def create_items(self) -> None:
        location_count = len(self.multiworld.get_unfilled_locations(self.player))

        progressive = bool(self.options.progressive_gear)
        required: List[GroundedItem] = []
        for name, data in item_table.items():
            if progressive and name in PROGRESSIVE_GEAR:
                continue  # replaced by its progressive item below
            for _ in range(data.count):
                required.append(self.create_item(name))
        if progressive:
            for name, line in PROGRESSIVE_LINES.items():
                required.extend(self.create_item(name) for _ in line)

        if len(required) > location_count:
            # Fewer locations than fixed items: keep progression, drop the rest.
            required.sort(key=lambda item: 0 if item.classification == IC.progression else 1)
            required = required[:location_count]

        pool = required
        while len(pool) < location_count:
            pool.append(self.create_item(self.get_filler_item_name()))

        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        rules_module.set_rules(self)

        if not itemsanity_location_names:
            raise Exception(
                "itemsanity.py's ITEMSANITY_ITEM_NAMES list is empty, so Itemsanity (which is always "
                "on) would add no locations at all. This shouldn't happen with the file as shipped -- "
                "if you emptied that list yourself, put at least one item name back."
            )

        if not killsanity_location_names:
            raise Exception(
                "killsanity.py's KILLSANITY_BOSS_NAMES list is empty, so Killsanity (which is always "
                "on) would add no locations at all. This shouldn't happen with the file as shipped -- "
                "if you emptied that list yourself, put at least one boss name back."
            )

        if not craftsanity_location_names:
            raise Exception(
                "craftsanity.py's CRAFTSANITY_ROW_TO_DISPLAY_NAME dict is empty, so Craftsanity "
                "(which is always on) would add no locations at all. This shouldn't happen with the "
                "file as shipped -- if you emptied that dict yourself, put at least one item back."
            )

        if self.options.goal.value == self.options.goal.option_gold_cards:
            self.multiworld.completion_condition[self.player] = lambda state: state.has(
                GOLD_CARD_PROGRESS_ITEM, self.player, self.options.gold_card_goal_amount.value
            )
        elif self.options.goal.value == self.options.goal.option_embiggening:
            self.multiworld.completion_condition[self.player] = lambda state: state.has(
                "Victory Progress", self.player, 1
            )
        elif self.options.goal.value == self.options.goal.option_infected_broodmother:
            self.multiworld.completion_condition[self.player] = lambda state: state.has(
                "Boss Kill Progress", self.player, 1
            )
        elif self.options.goal.value == self.options.goal.option_infected_broodmother_and_embiggening:
            self.multiworld.completion_condition[self.player] = lambda state: (
                state.has("Boss Kill Progress", self.player, 1)
                and state.has("Victory Progress", self.player, 1)
            )
        elif self.options.goal.value == self.options.goal.option_itemsanity:
            self.multiworld.completion_condition[self.player] = lambda state: all(
                state.can_reach_location(ap_name(name), self.player)
                for name in itemsanity_location_names if name not in DISABLED_LOCATIONS
            )
        elif self.options.goal.value == self.options.goal.option_story_boss_only:
            self.multiworld.completion_condition[self.player] = lambda state: state.has(
                "Boss Kill Progress", self.player, 3
            )
        elif self.options.goal.value == self.options.goal.option_short:
            self.multiworld.completion_condition[self.player] = lambda state: state.has(
                "Boss Kill Progress", self.player, 2
            )
        else:
            # boss_only: every boss except ExcludedBosses (locked progress
            # items, see regions.py).
            required_boss_count = len(killsanity_location_names) - len(self.options.excluded_bosses.value)
            self.multiworld.completion_condition[self.player] = lambda state: state.has(
                "Boss Kill Progress", self.player, required_boss_count
            )

    def create_item(self, name: str) -> GroundedItem:
        data = item_table[name]
        return GroundedItem(name, data.classification, item_name_to_id[name], self.player)

    def get_filler_item_name(self) -> str:
        return self.random.choices(filler_item_names, weights=[FILLER_WEIGHTS[n] for n in filler_item_names])[0]

    # ProgressiveGear: the Nth copy of a progressive item also credits the
    # Nth gear piece of its line, so every rule written against individual
    # gear names (rules.py) keeps working unchanged.
    def collect(self, state: CollectionState, item: Item) -> bool:
        changed = super().collect(state, item)
        line = PROGRESSIVE_LINES.get(item.name)
        if changed and line:
            copies = state.prog_items[self.player][item.name]
            if copies <= len(line):
                state.prog_items[self.player][line[copies - 1]] += 1
        return changed

    def remove(self, state: CollectionState, item: Item) -> bool:
        line = PROGRESSIVE_LINES.get(item.name)
        copies = state.prog_items[self.player][item.name] if line else 0
        changed = super().remove(state, item)
        if changed and line and 1 <= copies <= len(line):
            gear_name = line[copies - 1]
            state.prog_items[self.player][gear_name] -= 1
            if state.prog_items[self.player][gear_name] < 1:
                del state.prog_items[self.player][gear_name]
        return changed

    def fill_slot_data(self) -> Dict[str, Any]:
        return {
            "goal": self.options.goal.value,
            "excluded_bosses": sorted(self.options.excluded_bosses.value),
            "include_boss_checks": bool(self.options.include_boss_checks.value),
            "gold_card_drop_chance": self.options.gold_card_drop_chance.value,
            "gold_card_goal_amount": self.options.gold_card_goal_amount.value,
            # Always off (Tier 1 recipes are AP items); kept for older mods.
            "start_with_tier1_recipes": False,
            "item_base_id": ITEM_BASE_ID,
            # See recipe_shuffle.py / recipe_shuffle.lua. Empty = vanilla.
            "recipe_shuffle": self.recipe_ingredients,
            # See drop_shuffle.py / drop_shuffle.lua. Empty = vanilla drops.
            "creature_drop_shuffle": self.drop_mapping,
            "progressive_gear": bool(self.options.progressive_gear.value),
            "mutation_checks": bool(self.options.mutation_checks.value),
            "landmark_checks": bool(self.options.landmark_checks.value),
            "death_link": bool(self.options.death_link.value),
        }
