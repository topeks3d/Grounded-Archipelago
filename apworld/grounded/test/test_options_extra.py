from worlds.grounded.location_renames import ap_name
from worlds.grounded.player_upgrades import MOLAR_UPGRADES
from test.bases import WorldTestBase


def _pool_count(test, name):
    return sum(1 for item in test.multiworld.itempool if item.player == test.player and item.name == name)


class TestRecipeCostMultiplier(WorldTestBase):
    game = "Grounded"
    options = {"recipe_cost_multiplier": 150}

    def test_slot_data(self):
        self.assertEqual(self.world.fill_slot_data()["recipe_cost_multiplier"], 150)

    def test_tracker_scales_costs(self):
        from worlds.grounded.online_data import Recipe, _scale_recipe
        recipe = Recipe("Workbench", [("Sap", 3), ("Pebblet", 1)], False)
        self.assertEqual(_scale_recipe(recipe, 150).materials, [("Sap", 5), ("Pebblet", 2)])
        self.assertEqual(_scale_recipe(recipe, 50).materials, [("Sap", 2), ("Pebblet", 1)])


class TestProgressiveMolarUpgrades(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only", "progressive_molar_upgrades": True}

    def test_pool(self):
        for name, (_row, tiers) in MOLAR_UPGRADES.items():
            self.assertEqual(_pool_count(self, name), tiers, name)

    def test_tier2_fights_need_health(self):
        tier2 = ["Pebblet Spear", "Stinger Spear", "Red Ant Head Armor", "Red Ant Chest Armor",
                 "Red Ant Leg Armor"]
        self.collect_by_name(tier2)
        from worlds.grounded.rules import can_fight
        self.assertFalse(can_fight(self.multiworld.state, self.player, 2))
        self.collect_by_name(["Progressive Max Health"])
        self.assertTrue(can_fight(self.multiworld.state, self.player, 2))

    def test_slot_data(self):
        self.assertTrue(self.world.fill_slot_data()["progressive_molar_upgrades"])


class TestWithoutMolarUpgrades(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only"}

    def test_tier2_fights_without_health(self):
        self.collect_by_name(["Pebblet Spear", "Stinger Spear", "Red Ant Head Armor", "Red Ant Chest Armor",
                              "Red Ant Leg Armor"])
        from worlds.grounded.rules import can_fight
        self.assertTrue(can_fight(self.multiworld.state, self.player, 2))
        for name in MOLAR_UPGRADES:
            self.assertEqual(_pool_count(self, name), 0, name)


class TestStarterKit(WorldTestBase):
    game = "Grounded"
    options = {"starter_kit": True}

    def test_precollected_not_in_pool(self):
        start = [item.name for item in self.multiworld.precollected_items[self.player]]
        for name in ("Pebblet Axe", "Pebblet Hammer", "Pebblet Spear", "Canteen", "Bandage"):
            self.assertIn(name, start)
            self.assertEqual(_pool_count(self, name), 0, name)
        self.assertNotIn("Pebblet Axe", self.multiworld.early_items[self.player])


class TestStarterKitProgressive(WorldTestBase):
    game = "Grounded"
    options = {"starter_kit": True, "progressive_gear": True}

    def test_first_progressive_copies(self):
        start = [item.name for item in self.multiworld.precollected_items[self.player]]
        for name in ("Progressive Axe", "Progressive Hammer", "Progressive Spear"):
            self.assertEqual(start.count(name), 1, name)
        # The rest of each line is still in the pool.
        self.assertEqual(_pool_count(self, "Progressive Axe"), 2)
        self.assertNotIn("Progressive Axe", self.multiworld.early_items[self.player])
        self.assertEqual(self.multiworld.early_items[self.player].get("Progressive Shovel"), 1)


class TestGearPerks(WorldTestBase):
    game = "Grounded"
    options = {"gear_perks": "weapons_and_armor"}

    def test_slot_data(self):
        self.assertEqual(self.world.fill_slot_data()["gear_perks"], 2)


class TestRegionLocks(WorldTestBase):
    game = "Grounded"
    options = {"goal": "boss_only", "region_locks": True, "landmark_checks": True}

    def test_passes_in_pool(self):
        from worlds.grounded.region_locks import PASS_ITEMS
        for name in PASS_ITEMS:
            self.assertEqual(_pool_count(self, name), 1, name)
        self.assertNotIn("Region Pass: Grasslands", PASS_ITEMS)

    def test_regional_checks_need_their_pass(self):
        # An Item check filed under the Hedge, and a Grasslands one.
        from worlds.grounded.review_data import LOCATION_BIOMES
        hedge = next(n for n, b in LOCATION_BIOMES.items() if b == "Hedge" and n.startswith("Landmark: "))
        self.assertFalse(self._reach(hedge))
        self.collect_by_name(["Region Pass: Hedge"])
        self.assertTrue(self._reach(hedge) or not self._has(hedge))

    def test_gear_needs_ingredient_regions(self):
        from worlds.grounded.rules import usable
        state = self.multiworld.state
        self.collect_by_name(["Antlion Head Armor"])
        self.assertFalse(usable(state, self.player, "Antlion Head Armor"))
        self.collect_by_name(["Region Pass: Sandbox"])
        self.assertTrue(usable(state, self.player, "Antlion Head Armor"))

    def test_boss_needs_arena(self):
        from worlds.grounded.rules import location_rules
        rule = location_rules()["Kill: Hedge Broodmother"]
        state = self.multiworld.get_all_state(False)
        self.assertTrue(rule(state, self.player))
        state.remove(self.world.create_item("Region Pass: Hedge"))
        self.assertFalse(rule(state, self.player))

    def _has(self, name):
        from worlds.grounded.location_renames import ap_name
        try:
            self.multiworld.get_location(ap_name(name), self.player)
            return True
        except KeyError:
            return False

    def _reach(self, name):
        from worlds.grounded.location_renames import ap_name
        return self._has(name) and self.can_reach_location(ap_name(name))


class TestEverythingOn(WorldTestBase):
    """Every new option together, on top of the shuffles."""
    game = "Grounded"
    options = {"goal": "embiggening", "region_locks": True, "progressive_molar_upgrades": True,
               "starter_kit": True, "progressive_gear": True,
               "recipe_shuffle": True, "creature_drop_shuffle": True, "gear_perks": "weapons",
               "recipe_cost_multiplier": 300, "landmark_checks": True, "mutation_checks": True,
               "shop_checks": True}


class TestShopChecks(WorldTestBase):
    game = "Grounded"
    options = {"shop_checks": True}

    def test_shop_locations(self):
        from worlds.grounded.shop import SHOP_NODES, shop_location_name
        from worlds.grounded.location_renames import ap_name
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        for node in SHOP_NODES:
            self.assertIn(ap_name(shop_location_name(node)), names)
        self.assertTrue(self.world.fill_slot_data()["shop_checks"])


class TestShopChecksChipRegions(WorldTestBase):
    game = "Grounded"
    options = {"shop_checks": True, "region_locks": True}

    def test_page_waits_for_its_chip_region(self):
        from worlds.grounded.rules import location_rules
        from worlds.grounded.shop import SHOP_NODES, TREE_REQUIREMENTS, shop_location_name
        self.assertEqual({n.tree for n in SHOP_NODES} - set(TREE_REQUIREMENTS), set(), "every page has a chip rule")
        rules = location_rules()
        state = self.multiworld.get_all_state(False)
        pond = next(n for n in SHOP_NODES if n.tree == "PondOutpostTechTree")
        oak = next(n for n in SHOP_NODES if n.tree == "OakLabTechTree" and n.cost <= 1500)
        self.assertTrue(rules[shop_location_name(pond)](state, self.player))
        state.remove(self.world.create_item("Region Pass: Pond"))
        self.assertFalse(rules[shop_location_name(pond)](state, self.player))
        self.assertTrue(rules.get(shop_location_name(oak), lambda s, p: True)(state, self.player))


class TestRegionLockPopup(WorldTestBase):
    game = "Grounded"
    options = {"region_locks": True}

    def test_popup_lists_real_passes(self):
        from worlds.grounded.online_data import check_info
        from worlds.grounded.tracker_tab import _rules_for, state_for
        slot_data = {"region_locks": True}
        _rules_for(slot_data)
        info = check_info("Craft: Antlion Head Armor", "Craft: Antlion Head Armor", state_for(()), slot_data)
        passes = [r.text for r in info.requirements if r.text.startswith("Region Pass: ")]
        self.assertEqual(passes, ["Region Pass: Sandbox"])
