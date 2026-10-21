import unittest
from worlds.grounded.location_renames import ap_name
from worlds.grounded.gear import GEAR
from test.bases import WorldTestBase


class TestGroundedLogic(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only"}

    def _reachable(self, name):
        # Tests use the mod's names; renames (location_renames.py) mustn't break them.
        return self.can_reach_location(ap_name(name))

    def test_start_state(self):
        # Reported as wrongly in logic from the start:
        for name in ("Kill: Black Widow", "Kill: Hedge Broodmother", "Item: Mighty Glob",
                     "Kill: Mant", "Kill: Wasp Queen", "Item: Spider Fang", "Item: Grass Plank",
                     "Craft: Red Ant Head Armor", "Molars: 1"):
            self.assertFalse(self._reachable(name), name)
        # Genuinely free at the start:
        for name in ("Item: Plant Fiber", "Item: Sprig", "Item: Pebblet"):
            self.assertTrue(self._reachable(name), name)
        for name in ("Item: Berry Chunk", "Item: Clover Leaf", "Item: Rotten Food"):
            self.assertFalse(self._reachable(name), name)

    def test_shovel_tiers(self):
        from worlds.grounded.rules import _TOKEN_RULES
        state = self.multiworld.state
        self.collect_by_name(["Acorn Shovel"])
        self.assertTrue(_TOKEN_RULES["shovel1"](state, self.player))
        self.assertTrue(_TOKEN_RULES["shovel"](state, self.player))
        self.assertFalse(_TOKEN_RULES["shovel2"](state, self.player))
        # Tier 2 tools need Tier 1 fights for their materials.
        self.collect_by_name(["Black Ant Shovel"])
        self.assertFalse(_TOKEN_RULES["shovel2"](state, self.player))
        self.collect_by_name(["Pebblet Spear"])
        self.assertTrue(_TOKEN_RULES["shovel2"](state, self.player))

    def test_meals_need_cookery(self):
        self.assertIn("Cookery", {i.name for i in self.multiworld.itempool})
        self.collect_by_name(["Pebblet Spear", "Spaghetflea"])
        self.assertFalse(self.can_reach_location(ap_name("Craft: Spaghetflea")))
        self.collect_by_name(["Cookery"])
        self.assertTrue(self.can_reach_location(ap_name("Craft: Spaghetflea")))

    def test_globs_need_oven(self):
        from worlds.grounded.rules import _TOKEN_RULES
        self.assertIn("Oven", {i.name for i in self.multiworld.itempool})
        # Everything Mighty Glob needs except the Oven: c2 + hammer2.
        self.collect_by_name(["Pebblet Spear", "Insect Hammer", "Red Ant Head Armor", "Red Ant Chest Armor",
                              "Red Ant Leg Armor", "Stinger Spear"])
        state = self.multiworld.state
        self.assertTrue(_TOKEN_RULES["c2"](state, self.player) and _TOKEN_RULES["hammer2"](state, self.player))
        self.assertFalse(self.can_reach_location(ap_name("Item: Mighty Glob")))
        self.collect_by_name(["Oven"])
        self.assertTrue(self.can_reach_location(ap_name("Item: Mighty Glob")))

    def test_key_bosses_need_oven(self):
        keyed = [ap_name(n) for n in ("Kill: Hedge Broodmother", "Kill: Mantis", "Kill: Wasp Queen",
                                      "Defeat the Infected Broodmother")]
        self.collect_all_but(["Oven"])
        for loc in keyed:
            self.assertFalse(self.can_reach_location(loc), loc)
        self.assertTrue(self.can_reach_location(ap_name("Kill: Black Widow")))
        self.assertTrue(self.can_reach_location(ap_name("Kill: Director Schmector")))
        self.collect_by_name(["Oven"])
        for loc in keyed:
            self.assertTrue(self.can_reach_location(loc), loc)

    def test_spiky_bur_needs_haze_canister(self):
        # needs: axe3, canister (location_review.txt)
        self.collect_by_name(["Pebblet Spear", "Stinger Spear", "Red Ant Head Armor", "Red Ant Chest Armor",
                              "Red Ant Leg Armor", "Gas Mask"])
        self.assertFalse(self._reachable("Item: Spiky Bur"))
        self.collect_by_name(["Termite Axe"])
        self.assertTrue(self._reachable("Item: Spiky Bur"))
        self.multiworld.state.remove(self.get_item_by_name("Gas Mask"))
        self.assertFalse(self._reachable("Item: Spiky Bur"))

    def test_review_file_applied(self):
        from worlds.grounded.review_data import DISABLED_LOCATIONS, LOCATION_BIOMES
        from worlds.grounded.locations import mod_location_name_to_id
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertTrue(DISABLED_LOCATIONS)
        for name in DISABLED_LOCATIONS:
            self.assertIn(name, mod_location_name_to_id, name)  # ID kept
            self.assertNotIn(ap_name(name), names, name)
        # Every item / craft check has a biome.
        for name in mod_location_name_to_id:
            if name.startswith(("Item: ", "Craft: ")):
                self.assertIn(name, LOCATION_BIOMES, name)
        # No Roasting Spit needed (the mod unlocks it at the start).
        self.assertTrue(self._reachable("Item: Aphid Roast"))

    def test_location_rules_with_plain_state(self):
        # The client's Tracker tab evaluates location_rules with a stand-in state.
        from worlds.grounded.rules import location_rules

        class Plain:
            def __init__(self, items):
                self.items = items

            def has(self, name, player, count=1):
                return self.items.get(name, 0) >= count

            def has_any(self, names, player):
                return any(self.items.get(n, 0) for n in names)

            def has_all(self, names, player):
                return all(self.items.get(n, 0) for n in names)

        rules = location_rules()
        self.assertFalse(rules["Item: Grass Plank"](Plain({}), 1))
        self.assertTrue(rules["Item: Grass Plank"](Plain({"Pebblet Axe": 1}), 1))
        self.assertFalse(rules["Craft: Pebblet Axe"](Plain({}), 1))

    def test_dagger_tiers(self):
        from worlds.grounded.rules import _TOKEN_RULES
        state = self.multiworld.state
        dagger = {t: (lambda t=t: _TOKEN_RULES[f"dagger{t}"](state, self.player)) for t in (1, 2, 3)}
        self.assertIn("Widow Dagger", {i.name for i in self.multiworld.itempool})
        self.assertIn("Bone Dagger", {i.name for i in self.multiworld.itempool})
        # Bone Dagger (Tier 1), and dagger resources are all underwater.
        self.collect_by_name(["Bone Dagger"])
        self.assertFalse(dagger[1]())
        self.collect_by_name(["Diving Gear"])
        self.assertTrue(dagger[1]())
        self.assertFalse(dagger[2]())
        self.assertFalse(_TOKEN_RULES["c1"](state, self.player))  # not a combat weapon
        # Spider Fang Dagger (Tier 2): its materials need a Tier 1 fight.
        self.collect_by_name(["Spider Fang Dagger"])
        self.assertFalse(dagger[2]())
        self.collect_by_name(["Pebblet Spear"])
        self.assertTrue(dagger[2]())
        self.assertFalse(dagger[3]())
        # Widow Dagger (Tier 3): made from the Black Widow, a Tier 3 fight.
        self.collect_by_name(["Widow Dagger", "Stinger Spear", "Red Ant Head Armor", "Red Ant Chest Armor",
                              "Red Ant Leg Armor"])
        self.assertFalse(dagger[3]())
        self.assertFalse(_TOKEN_RULES["c3"](state, self.player))  # the Widow Dagger alone isn't a Tier 3 weapon
        self.collect_by_name(["Black Ox Head Armor", "Black Ox Chest Armor", "Black Ox Leg Armor"])
        self.assertFalse(_TOKEN_RULES["c3"](state, self.player))
        self.collect_by_name(["Termite Axe"])
        self.assertTrue(dagger[3]())

    def test_tracker_tab_groups(self):
        from worlds.grounded.tracker_tab import CHECKED, IN_LOGIC, OUT_OF_LOGIC, build_groups
        from worlds.grounded.grounded_data import ITEM_NAME_TO_ID
        from worlds.grounded.locations import mod_location_name_to_id
        ids = {name: code for name, code in mod_location_name_to_id.items()}
        seed = [ids["Item: Plant Fiber"], ids["Item: Grass Plank"], ids["Item: Algae"],
                ids["Kill: Mant"], ids["Craft: Pebblet Axe"]]
        groups = dict(build_groups(seed, [ids["Item: Algae"]], [ITEM_NAME_TO_ID["Progressive Axe"]],
                                   {"recipe_shuffle": {}}))
        status = {c.name: c.status for checks in groups.values() for c in checks}
        self.assertEqual(status[ap_name("Item: Plant Fiber")], IN_LOGIC)
        self.assertEqual(status[ap_name("Item: Grass Plank")], IN_LOGIC)  # Progressive Axe -> Pebblet Axe
        self.assertEqual(status[ap_name("Item: Algae")], CHECKED)
        self.assertEqual(status[ap_name("Kill: Mant")], OUT_OF_LOGIC)
        self.assertEqual(status[ap_name("Craft: Pebblet Axe")], IN_LOGIC)
        self.assertIn(ap_name("Item: Algae"), [c.name for c in groups["Pond"]])
        self.assertIn(ap_name("Kill: Mant"), [c.name for c in groups["Bosses"]])

    def test_location_renames_round_trip(self):
        from worlds.grounded.location_renames import mod_name
        from worlds.grounded.locations import location_name_to_id, mod_location_name_to_id
        from worlds.grounded.grounded_data import LOCATION_NAME_TO_ID, MOD_LOCATION_NAME_TO_ID
        for name, code in mod_location_name_to_id.items():
            self.assertEqual(location_name_to_id[ap_name(name)], code)
            self.assertEqual(mod_name(ap_name(name)), name)
        # The client's generated copy must match (regenerate grounded_data.py).
        self.assertEqual(LOCATION_NAME_TO_ID, location_name_to_id)
        self.assertEqual(MOD_LOCATION_NAME_TO_ID, mod_location_name_to_id)

    def test_tier1(self):
        self.collect_by_name(["Pebblet Axe"])
        self.assertTrue(self._reachable("Item: Grass Plank"))
        self.assertTrue(self._reachable("Item: Weed Stem"))
        self.assertTrue(self._reachable("Item: Clover Leaf"))
        self.assertFalse(self._reachable("Item: Berry Chunk"))  # axe2
        self.assertTrue(self._reachable("Molars: 1"))
        self.assertTrue(self._reachable("Craft: Pebblet Axe"))
        self.assertFalse(self._reachable("Item: Spider Fang"))

    def test_tier2_needs_armor_coverage(self):
        self.collect_by_name(["Pebblet Spear", "Stinger Spear", "Red Ant Head Armor", "Red Ant Chest Armor"])
        self.assertFalse(self._reachable("Item: Spider Fang"))
        self.collect_by_name(["Spider Leg Armor"])
        self.assertTrue(self._reachable("Item: Spider Fang"))
        self.assertFalse(self._reachable("Kill: Black Widow"))

    def test_tier3_recipes_alone_dont_skip_tier2(self):
        self.collect_by_name(["Pebblet Spear", "Termite Axe", "Black Ox Head Armor",
                              "Black Ox Chest Armor", "Black Ox Leg Armor"])
        self.assertFalse(self._reachable("Kill: Black Widow"))
        self.assertFalse(self._reachable("Item: Spider Fang"))

    def test_story_gates(self):
        self.collect_by_name(["Pebblet Spear", "Stinger Spear", "Red Ant Head Armor", "Red Ant Chest Armor",
                              "Red Ant Leg Armor", "Termite Axe", "Black Ox Head Armor",
                              "Black Ox Chest Armor", "Black Ox Leg Armor", "Oven"])
        self.assertTrue(self._reachable("Kill: Black Widow"))
        self.assertTrue(self._reachable("Kill: Hedge Broodmother"))
        self.assertTrue(self._reachable("Kill: Wasp Queen"))  # no Upper Yard gate any more
        self.assertFalse(self._reachable("Kill: Mant"))
        self.collect_by_name(["Gas Mask", "Diving Gear"])
        self.assertFalse(self._reachable("Kill: Mant"))
        self.collect_by_name(["Zip Line Rig"])
        self.assertTrue(self._reachable("Kill: Mant"))

    def test_ng_plus_weapons_need_jelly(self):
        tier2 = ["Pebblet Spear", "Stinger Spear", "Red Ant Head Armor", "Red Ant Chest Armor",
                 "Red Ant Leg Armor"]
        self.collect_by_name(tier2 + ["Spicy Warhammer", "Black Ox Head Armor",
                                      "Black Ox Chest Armor", "Black Ox Leg Armor"])
        # An NG+ weapon can't be crafted (so can't count for Tier 3) without the jelly.
        self.assertFalse(self._reachable("Kill: Black Widow"))
        self.assertFalse(self._reachable("Craft: Spicy Warhammer"))
        bundles = self.get_items_by_name("DeDuper Jelly Bundle")
        self.collect(bundles[0])
        self.assertFalse(self._reachable("Craft: Spicy Warhammer"))
        self.collect(bundles[1:])
        self.assertTrue(self._reachable("Craft: Spicy Warhammer"))
        self.assertTrue(self._reachable("Kill: Black Widow"))

    def test_jelly_and_ooze_bundles_in_pool(self):
        from worlds.grounded.items import JELLY_BUNDLE, JELLY_BUNDLE_COUNT, OOZE_BUNDLE, OOZE_BUNDLE_COUNT
        pool = [item.name for item in self.multiworld.itempool if item.player == self.player]
        self.assertEqual(pool.count(JELLY_BUNDLE), JELLY_BUNDLE_COUNT)
        self.assertEqual(pool.count(OOZE_BUNDLE), OOZE_BUNDLE_COUNT)

    def test_ng_plus_itemsanity_removed(self):
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        for name in ("Item: DeDuper Jelly", "Item: Fusion Crystal", "Item: Infused Ooze"):
            self.assertNotIn(name, names)

    def test_every_gear_item_exists_once(self):
        pool = [item.name for item in self.multiworld.itempool if item.player == self.player]
        for gear in GEAR:
            self.assertEqual(pool.count(gear.name), 1, gear.name)

    def test_consumables_unlock_one_by_one(self):
        from worlds.grounded.consumables import CONSUMABLES
        from worlds.grounded.craftsanity import CRAFTSANITY_ROW_TO_DISPLAY_NAME
        from worlds.grounded.items import item_table
        self.assertNotIn("Consumables", item_table)
        pool = [item.name for item in self.multiworld.itempool if item.player == self.player]
        for consumable in CONSUMABLES:
            self.assertEqual(pool.count(consumable.name), 1, consumable.name)
            self.assertEqual(CRAFTSANITY_ROW_TO_DISPLAY_NAME[consumable.item_row], consumable.name)
        # Each recipe opens only its own craft check.
        self.assertFalse(self._reachable("Craft: Bandage"))
        self.collect_by_name(["Bandage"])
        self.assertTrue(self._reachable("Craft: Bandage"))
        self.assertFalse(self._reachable("Craft: Torch"))
        self.collect_by_name(["Pebblet Spear"])
        self.assertFalse(self._reachable("Craft: Canteen"))
        self.collect_by_name(["Canteen"])
        self.assertTrue(self._reachable("Craft: Canteen"))

    def test_bandage_is_early(self):
        early = self.multiworld.early_items[self.player]
        for name in ("Bandage", "Pebblet Axe", "Pebblet Hammer"):
            self.assertEqual(early.get(name), 1, name)


class TestGroundedRecipeShuffle(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only", "recipe_shuffle": True}

    def test_only_tier2_and_3_shuffled(self):
        shuffled = self.world.recipe_ingredients
        for gear in GEAR:
            self.assertEqual(gear.recipe_row in shuffled, gear.tier in (2, 3), gear.name)

    def test_ingredients_are_logic_safe(self):
        from worlds.grounded.recipe_shuffle import MATERIAL_BY_ROW, MAX_INGREDIENTS, TIER2_MATERIALS
        from worlds.grounded.rules import ITEM_REQUIREMENTS
        tier2_rows = {m.row for m in TIER2_MATERIALS}
        allowed = {2: {(), ("c1",)}, 3: {(), ("c1",), ("c2",)}}
        tier_of = {g.recipe_row: g.tier for g in GEAR}
        for recipe_row, entries in self.world.recipe_ingredients.items():
            self.assertEqual(len(entries), MAX_INGREDIENTS, recipe_row)
            rows = [row for row, _ in entries]
            self.assertEqual(len(set(rows)), len(rows), recipe_row)
            for row, count in entries:
                material = MATERIAL_BY_ROW[row]
                self.assertIn(ITEM_REQUIREMENTS.get(material.name, ()), allowed[tier_of[recipe_row]], material.name)
                self.assertGreaterEqual(count, 1)
                if tier_of[recipe_row] == 2:
                    self.assertNotIn(row, tier2_rows, recipe_row)

    def test_slot_data(self):
        self.assertEqual(self.world.fill_slot_data()["recipe_shuffle"], self.world.recipe_ingredients)

    def test_shuffled_craft_drops_vanilla_extras(self):
        # Vanilla Bone Trident needs the pond (Diving Gear); shuffled, it doesn't.
        self.collect_by_name(["Pebblet Spear", "Bone Trident"])
        self.assertTrue(self.can_reach_location(ap_name("Craft: Bone Trident")))


class TestGroundedNoRecipeShuffle(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only"}

    def test_off_by_default(self):
        self.assertEqual(self.world.recipe_ingredients, {})
        self.assertEqual(self.world.fill_slot_data()["recipe_shuffle"], {})


class TestGroundedCreatureDropShuffle(WorldTestBase):
    game = "Grounded"
    options = {"goal": "gold_cards", "creature_drop_shuffle": True}

    def test_groups_share_requirements(self):
        from worlds.grounded.drop_shuffle import DROP_GROUPS
        from worlds.grounded.rules import ITEM_REQUIREMENTS
        for group in DROP_GROUPS:
            reqs = {tuple(sorted(ITEM_REQUIREMENTS[name])) for name in group}
            self.assertEqual(len(reqs), 1, sorted(group))

    def test_mapping_is_a_permutation_within_groups(self):
        from worlds.grounded.drop_shuffle import DROP_GROUPS
        mapping = self.world.drop_mapping
        self.assertTrue(mapping)
        self.assertEqual(sorted(mapping), sorted(mapping.values()))
        group_of = {row: i for i, group in enumerate(DROP_GROUPS) for row in group.values()}
        for old, new in mapping.items():
            self.assertEqual(group_of[old], group_of[new], old)

    def test_gold_cards_untouched(self):
        from worlds.grounded.goldcards import GOLD_CARD_ROW_NAMES
        rows = set(self.world.drop_mapping) | set(self.world.drop_mapping.values())
        self.assertFalse(rows & set(GOLD_CARD_ROW_NAMES))
        self.assertFalse(any(row.startswith("Bestiary") for row in rows))

    def test_slot_data(self):
        self.assertEqual(self.world.fill_slot_data()["creature_drop_shuffle"], self.world.drop_mapping)

    def test_universal_tracker_regen_matches(self):
        slot_data = {"goal": 4, "creature_drop_shuffle": {"AntPart": "BeeFuzz", "BeeFuzz": "AntPart"}}
        self.multiworld.re_gen_passthrough = {"Grounded": slot_data}
        self.world.generate_early()
        self.assertEqual(self.world.drop_mapping, {"AntPart": "BeeFuzz", "BeeFuzz": "AntPart"})
        self.assertTrue(self.world.options.creature_drop_shuffle)


class TestGroundedNoCreatureDropShuffle(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only"}

    def test_off_by_default(self):
        self.assertEqual(self.world.drop_mapping, {})
        self.assertEqual(self.world.fill_slot_data()["creature_drop_shuffle"], {})


class TestGroundedProgressiveGear(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only", "progressive_gear": True}

    def test_pool_uses_progressive_items(self):
        from worlds.grounded.gear import PROGRESSIVE_GEAR, PROGRESSIVE_LINES
        pool = [item.name for item in self.multiworld.itempool if item.player == self.player]
        for name, line in PROGRESSIVE_LINES.items():
            self.assertEqual(pool.count(name), len(line), name)
        for gear_name in PROGRESSIVE_GEAR:
            self.assertNotIn(gear_name, pool)

    def test_copies_credit_gear_in_order(self):
        self.collect(self.get_items_by_name("Progressive Spear")[:1])
        self.assertTrue(self.multiworld.state.has("Pebblet Spear", self.player))
        self.assertFalse(self.multiworld.state.has("Stinger Spear", self.player))
        self.assertTrue(self.can_reach_location(ap_name("Craft: Pebblet Spear")))
        # 6 head armor copies reach Red Ant (the first Tier 2 head piece)
        self.collect(self.get_items_by_name("Progressive Head Armor")[:6])
        self.assertTrue(self.multiworld.state.has("Red Ant Head Armor", self.player))
        self.assertFalse(self.multiworld.state.has("Black Ant Head Armor", self.player))

    def test_remove_uncredits(self):
        items = self.get_items_by_name("Progressive Axe")[:2]
        self.collect(items)
        self.assertTrue(self.multiworld.state.has("Insect Axe", self.player))
        self.remove(items[1:])
        self.assertFalse(self.multiworld.state.has("Insect Axe", self.player))
        self.assertTrue(self.multiworld.state.has("Pebblet Axe", self.player))


class TestGroundedMutations(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only", "mutation_checks": True, "death_link": True}

    def test_locations_present_and_gated(self):
        from worlds.grounded.mutations import mutation_location_names
        for name in mutation_location_names:
            self.multiworld.get_location(ap_name(name), self.player)
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(any(n.startswith(("Note: ", "BURG.L Chip: ")) for n in names))
        self.assertFalse(self.can_reach_location(ap_name("Mutations: 25")))

    def test_slot_data(self):
        data = self.world.fill_slot_data()
        self.assertTrue(data["mutation_checks"] and data["death_link"])
        self.assertNotIn("exploration_checks", data)


class TestGroundedLandmarks(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only", "landmark_checks": True}

    def test_locations_present_and_gated(self):
        from worlds.grounded.landmarks import landmark_location_names
        from worlds.grounded.review_data import DISABLED_LOCATIONS
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        expected = {ap_name(n) for n in landmark_location_names if n not in DISABLED_LOCATIONS}
        self.assertTrue(expected and expected <= names)
        self.assertTrue(self.can_reach_location(ap_name("Landmark: POI_Ashtray")))
        self.assertFalse(self.can_reach_location(ap_name("Landmark: POI_Haze_Lab")))  # needs: gas
        self.collect_by_name(["Gas Mask"])
        self.assertTrue(self.can_reach_location(ap_name("Landmark: POI_Haze_Lab")))
        self.assertTrue(self.world.fill_slot_data()["landmark_checks"])

    def test_landmark_map(self):
        from worlds.grounded.tracker_tab import IN_LOGIC, OUT_OF_LOGIC, VISITED, landmark_map
        regions = dict(landmark_map(["Landmark: POI_Ashtray"], [], {}))
        status = {mark.name: mark.status for marks in regions.values() for mark in marks}
        self.assertEqual(status[ap_name("Landmark: POI_Ashtray")[len("Landmark: "):]], VISITED)
        self.assertEqual(status[ap_name("Landmark: POI_Haze_Lab")[len("Landmark: "):]], OUT_OF_LOGIC)
        self.assertEqual(status[ap_name("Landmark: POI_Cap_Gun")[len("Landmark: "):]], IN_LOGIC)


class TestOnlineData(unittest.TestCase):
    """The bundled map / wiki data (connector/tools/fetch_online_data.py)
    and the info popup built from it."""

    def test_pins_cover_landmarks(self):
        from worlds.grounded.landmarks import LANDMARK_ASSETS
        from worlds.grounded.online_data import landmark_pins, map_png
        pins = landmark_pins()
        if not pins or not map_png():
            self.skipTest("wand.com map data not present (not in the repo -- see fetch_online_data.py --map)")
        self.assertGreater(len(pins), 100)
        self.assertTrue(set(pins) <= set(LANDMARK_ASSETS))
        for pin in pins.values():
            self.assertTrue(0 < pin["u"] < 1 and 0 < pin["v"] < 1)
        self.assertTrue(map_png()[1:4] == b"PNG")

    def test_vanilla_and_shuffled_recipes(self):
        from worlds.grounded.online_data import check_info, icon_png
        from worlds.grounded.tracker_tab import state_for
        from worlds.grounded.grounded_data import ITEM_NAME_TO_ID
        state = state_for([ITEM_NAME_TO_ID["Pebblet Spear"]])
        info = check_info("Craft: Black Ant Sword", "Craft: Black Ant Sword", state, {})
        self.assertEqual(info.recipes[0].materials[0], ("Black Ant Mandibles", 2))
        self.assertFalse(info.recipes[0].shuffled)
        self.assertEqual(info.requirements[0], ("Recipe: Black Ant Sword", False))
        shuffle = {"SwordAntBlack": [["AcidGland", 3], ["FuzzMite", 5], ["AntMandibles", 3], ["Sap", 2], ["StoneShale", 1]]}
        info = check_info("Craft: Black Ant Sword", "Craft: Black Ant Sword", state, {"recipe_shuffle": shuffle})
        self.assertTrue(info.recipes[0].shuffled)
        self.assertEqual(len(info.recipes[0].materials), 3)  # vanilla slot count
        self.assertEqual(info.recipes[0].materials[0], ("Acid Gland", 3))
        # Armor pieces use their in-game names on the wiki.
        info = check_info("Craft: Clover Head Armor", "Craft: Clover Head Armor", state, {})
        self.assertIn(("Clover Leaf", 4), info.recipes[0].materials)
        self.assertIsNotNone(icon_png("Clover Head Armor"))
        self.assertIsNotNone(icon_png("Grass Plank"))

    def test_item_sources(self):
        from worlds.grounded.online_data import item_sources
        self.assertEqual(item_sources("Raw Aphid Meat", {}), (["Aphid"], False))
        # Creature Drop Shuffle: whatever dropped Raw Weevil Meat now drops
        # Raw Aphid Meat (and the other way round).
        shuffle = {"creature_drop_shuffle": {"WeevilMeat": "AphidMeat", "AphidMeat": "WeevilMeat"}}
        lines, shuffled = item_sources("Raw Aphid Meat", shuffle)
        self.assertTrue(shuffled)
        self.assertEqual(lines, ["Weevil (in place of their Raw Weevil Meat)"])


class TestClientNotifications(unittest.TestCase):
    """Server messages -> overlay cards and in-game notifications."""

    def test_cards(self):
        import asyncio

        async def run():
            import json
            import tempfile
            from pathlib import Path
            from NetUtils import NetworkItem, NetworkSlot, SlotType
            from worlds.grounded.client import _build_context_class
            from worlds.grounded.grounded_data import ITEM_NAME_TO_ID, MOD_LOCATION_NAME_TO_ID

            ctx = _build_context_class()(None, None, Path(tempfile.mkdtemp()))
            cards = []
            ctx.overlay.post = cards.append
            ctx.slot = 1
            ctx.player_names = {1: "Me", 2: "Bob"}
            ctx.slot_info = {1: NetworkSlot("Me", "Grounded", SlotType.player), 2: NetworkSlot("Bob", "Celeste", SlotType.player)}
            axe = ITEM_NAME_TO_ID["Insect Axe"]
            sprig = MOD_LOCATION_NAME_TO_ID["Item: Sprig"]
            # Received from Bob (progression)
            ctx._notify_from_print_json({"type": "ItemSend", "receiving": 1, "item": NetworkItem(axe, 77, 2, 0b001)})
            # Sent to Bob from our Sprig check
            ctx._notify_from_print_json({"type": "ItemSend", "receiving": 2, "item": NetworkItem(12345, sprig, 1, 0)})
            self.assertEqual(cards[0].kind, "progression")
            self.assertEqual(cards[0].title, "Insect Axe")
            self.assertTrue(cards[0].subtitle.startswith("from Bob (Celeste)"))
            self.assertIsNotNone(cards[0].icon_png)
            self.assertEqual(cards[1].kind, "filler")
            self.assertTrue(cards[1].subtitle.startswith("to Bob (Celeste)"))
            self.assertIsNotNone(cards[1].icon_png)  # the Sprig check's own icon
            sent = ctx.notifications[-1]
            self.assertTrue(sent["text"].startswith("Sent ") and sent["detail"].startswith("Location: "))
            self.assertEqual(sent["icon_row"], "Twig")
            self.assertTrue(json.loads(ctx.to_game_path.read_text())["overlay_notifications"])

        asyncio.run(run())


class TestGroundedDefaults(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only"}

    def test_optional_locations_absent(self):
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(any(n.startswith(("BURG.L Chip: ", "Note: ", "Mutations: ")) for n in names))
        # Landmark Checks is on by default.
        self.assertTrue(any(n.startswith("Landmark: ") for n in names))
        self.assertTrue(self.world.fill_slot_data()["landmark_checks"])

    def test_roasting_spit_not_an_item(self):
        from worlds.grounded.items import item_table
        self.assertNotIn("Roasting Spit", item_table)

    def test_removed_items_gone(self):
        from worlds.grounded.items import item_table
        for name in ("Multi-Story Bases", "Fortified Bases", "SCA.B Scanner Upgrade", "Torch Upgrade",
                     "Tier 4 Weapons", "Tier 4 Armor", "Spicy Resistance Charm", "Cold Resistance Charm"):
            self.assertNotIn(name, item_table)

    def test_filler_variety(self):
        from worlds.grounded.items import filler_item_names
        names = {self.world.get_filler_item_name() for _ in range(300)}
        self.assertEqual(names, set(filler_item_names))

    def test_universal_tracker_regen_matches(self):
        from worlds.grounded import GroundedWorld
        slot_data = {"goal": 1, "excluded_bosses": ["Wasp Queen"], "include_boss_checks": False,
                     "gold_card_goal_amount": 10, "progressive_gear": True,
                     "mutation_checks": False, "recipe_shuffle": {"AxeTier2": [["AntPart", 2]]}}
        self.assertIs(GroundedWorld.interpret_slot_data(slot_data), slot_data)
        self.multiworld.re_gen_passthrough = {"Grounded": slot_data}
        self.world.generate_early()
        self.assertEqual(self.world.recipe_ingredients, {"AxeTier2": [["AntPart", 2]]})
        self.assertTrue(self.world.options.progressive_gear)
        self.assertEqual(self.world.options.excluded_bosses.value, {"Wasp Queen"})


class TestGroundedEverythingOn(WorldTestBase):
    game = "Grounded"
    options = {"goal": "embiggening", "recipe_shuffle": True, "creature_drop_shuffle": True, "progressive_gear": True,
               "mutation_checks": True, "death_link": True}


class TestGroundedEnding(WorldTestBase):
    game = "Grounded"
    options = {"goal": "embiggening"}

    def test_ending_needs_final_boss_not_an_item(self):
        from worlds.grounded.items import item_table
        from worlds.grounded.rules import ending_boss
        self.assertNotIn("SPAC.R Embiggening Cell", item_table)
        self.assertEqual(ending_boss(set()), "Director Schmector")
        self.assertEqual(ending_boss({"Director Schmector"}), "Mant")
        self.assertFalse(self.can_reach_location(ap_name("Go Big Or Never Go Home (Ending)")))
        self.collect_by_name(["Pebblet Spear", "Stinger Spear", "Red Ant Head Armor", "Red Ant Chest Armor",
                              "Red Ant Leg Armor", "Termite Axe", "Black Ox Head Armor", "Black Ox Chest Armor",
                              "Black Ox Leg Armor", "Gas Mask", "Diving Gear", "Zip Line Rig"])
        self.assertTrue(self.can_reach_location(ap_name("Kill: Director Schmector")))
        self.assertTrue(self.can_reach_location(ap_name("Go Big Or Never Go Home (Ending)")))
