-- item_grants.lua
--
-- Applies items that arrived from Archipelago. Every grant must be safe to
-- run more than once for the same item (restart recovery re-applies).

local M = {}

local objects = require("ap_objects")

-- The local PlayerController: IsLocalController() only. (UEHelpers'
-- IsPlayerController() matches remote players' controllers too, so in
-- multiplayer grants could target the wrong player.)
-- Cached (ap_objects.lua): a FindAllOf every call caused hitches.
local function get_local_player_controller()
    local controller = objects.find_matching("local PlayerController", "PlayerController", function(c)
        return c:IsLocalController() == true
    end)
    if not controller then
        return nil, "no valid local PlayerController found"
    end
    return controller
end

-- ---------------------------------------------------------------------
-- Grants go through the game's own console commands (USurvivalCheatManager:
-- GiveItem, UnlockRecipe, AddScience, ...) via
-- KismetSystemLibrary:ExecuteConsoleCommand. There's no return value, so
-- "issued" is the best we can report.
-- ---------------------------------------------------------------------

local function execute_console_command(command)
    local player_controller, pc_err = get_local_player_controller()
    if not player_controller then
        return false, "get_local_player_controller() failed: " .. tostring(pc_err)
    end
    local ksl_ok, ksl = pcall(StaticFindObject, "/Script/Engine.Default__KismetSystemLibrary")
    if not ksl_ok or not ksl then
        return false, "couldn't find KismetSystemLibrary CDO: " .. tostring(ksl)
    end
    local pawn_ok, pawn = pcall(function() return player_controller.player end)
    local call_ok, call_err = pcall(function()
        ksl:ExecuteConsoleCommand((pawn_ok and pawn) or player_controller, command, player_controller)
    end)
    if not call_ok then
        return false, tostring(call_err)
    end
    return true
end

-- GiveItem <row> <count>. False only if it couldn't be issued (no player
-- controller yet) -- safe to retry.
local function grant_item_by_row_name(row_name, count)
    count = count or 1
    local ok, err = execute_console_command(string.format("GiveItem %s %d", row_name, count))
    if not ok then
        print(string.format(
            "[GroundedArchipelago] GiveItem %s %d failed to issue: %s -- will retry.\n",
            row_name, count, tostring(err)
        ))
        return false
    end
    print(string.format("[GroundedArchipelago] Issued: GiveItem %s %d\n", row_name, count))
    return true
end

-- Raw Science goes through AddScience (its item row behaves like a
-- currency, so GiveItem doesn't work for it).
local function give_science(amount)
    local ok, err = execute_console_command(string.format("AddScience %d", amount))
    if not ok then
        print(string.format(
            "[GroundedArchipelago] AddScience %d failed to issue: %s -- will retry.\n", amount, tostring(err)
        ))
        return false
    end
    print(string.format("[GroundedArchipelago] Issued: AddScience %d\n", amount))
    return true
end

-- ---------------------------------------------------------------------
-- Unused fallback: the old CreateItem + AddItem path (kept in case GiveItem
-- fails for some item category).
-- ---------------------------------------------------------------------

M.cached_item_data_table = nil

function M.note_item_data_table(data_table)
    if not M.cached_item_data_table then
        M.cached_item_data_table = data_table
        local path_ok, path = pcall(function() return data_table:GetFullName() end)
        print(string.format(
            "[GroundedArchipelago] Captured item DataTable from a live pickup: %s\n",
            path_ok and tostring(path) or ("couldn't read its path: " .. tostring(path))
        ))
    end
end

local warned_about_no_data_table = false
local warned_which_data_table_source = false

local function get_item_data_table()
    local global_ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if global_ok and global_data then
        local table_ok, all_items = pcall(function() return global_data.AllItemsTable end)
        if table_ok and all_items then
            local get_ok, unwrapped = pcall(function() return all_items:get() end)
            local result = (get_ok and unwrapped) or all_items
            if not warned_which_data_table_source then
                warned_which_data_table_source = true
                local path_ok, path = pcall(function() return result:GetFullName() end)
                print(string.format(
                    "[GroundedArchipelago] Using GlobalTableData.AllItemsTable for item grants: %s\n",
                    path_ok and tostring(path) or ("(GetFullName failed: " .. tostring(path) .. ")")
                ))
            end
            return result
        end
    end
    if M.cached_item_data_table then
        if not warned_which_data_table_source then
            warned_which_data_table_source = true
            local path_ok, path = pcall(function() return M.cached_item_data_table:GetFullName() end)
            print(string.format(
                "[GroundedArchipelago] GlobalTableData not usable -- falling back to the " ..
                "pickup-captured DataTable for item grants: %s\n",
                path_ok and tostring(path) or ("(GetFullName failed: " .. tostring(path) .. ")")
            ))
        end
        return M.cached_item_data_table
    end
    if not warned_about_no_data_table then
        warned_about_no_data_table = true
        print(
            "[GroundedArchipelago] Can't grant items yet -- neither " ..
            "FindFirstOf('GlobalTableData').AllItemsTable nor a pickup-captured DataTable is " ..
            "available. Will keep retrying quietly (this warning won't repeat). Try picking up any " ..
            "item, or check whether 'GlobalTableData' is the right class name for your UE4SS build.\n"
        )
    end
    return nil
end

-- USurvivalGameplayStatics is a function library: use its Default__ object
-- via StaticFindObject (FindFirstOf doesn't give a callable reference).
local function get_survival_gameplay_statics()
    local ok, instance = pcall(StaticFindObject, "/Script/Maine.Default__SurvivalGameplayStatics")
    if ok and instance then
        return instance
    end
    return nil
end

local function make_row_handle(data_table, row_name)
    return { DataTable = data_table, RowName = row_name }
end

local function grant_item_by_row_name_via_create_item(player, row_name, count)
    count = count or 1
    local data_table = get_item_data_table()
    if not data_table then
        return false
    end

    local statics = get_survival_gameplay_statics()
    if not statics then
        print("[GroundedArchipelago] Couldn't find USurvivalGameplayStatics -- will retry.\n")
        return false
    end

    local inv_ok, inv = pcall(function() return player.InventoryComponent end)
    if not inv_ok or not inv then
        print("[GroundedArchipelago] Local player has no readable InventoryComponent -- will retry.\n")
        return false
    end

    local granted = 0
    for i = 1, count do
        local row_handle = make_row_handle(data_table, row_name)
        local create_ok, item = pcall(function() return statics:CreateItem(player, row_handle) end)
        if not create_ok or not item then
            print(string.format(
                "[GroundedArchipelago] CreateItem('%s') failed (%d/%d): %s\n",
                row_name, i, count, tostring(item)
            ))
            break
        end
        local add_ok, add_err = pcall(function() inv:AddItem(item, true) end)
        if not add_ok then
            print(string.format(
                "[GroundedArchipelago] InventoryComponent:AddItem for '%s' failed (%d/%d): %s\n",
                row_name, i, count, tostring(add_err)
            ))
            break
        end
        granted = granted + 1
    end

    if granted == 0 then
        print(string.format("[GroundedArchipelago] Granted 0/%d of '%s' -- will retry.\n", count, row_name))
        return false
    end
    if granted < count then
        print(string.format(
            "[GroundedArchipelago] Granted %d/%d of '%s' (stopping short rather than risk " ..
            "double-granting the ones that landed -- see the comment above this function).\n",
            granted, count, row_name
        ))
    end
    return true
end

-- Filler bundles: AP item -> {Table_AllItems row, amount}. Keep in sync with
-- items.py's filler_items.
local RESOURCE_BUNDLES = {
    ["Plant Fiber Bundle"] = {"FiberRaw", 15},
    ["Sprig Bundle"]       = {"Twig", 10},
    ["Pebblet Bundle"]     = {"StoneShale", 10},
    ["Sap Bundle"]         = {"Sap", 8},
    ["Grass Plank Bundle"] = {"GrassPlank", 5},
    ["Crude Rope Bundle"]  = {"FiberWoven", 4},
    ["Bandage Bundle"]     = {"Bandage", 3},
    -- NG+ materials (items.py's JELLY_PER_BUNDLE / OOZE_PER_BUNDLE). DeDuper
    -- Jelly's row is "ScienceDust"; Infused Ooze is "UpgradeCrystalCreature".
    ["DeDuper Jelly Bundle"] = {"ScienceDust", 8},
    ["Infused Ooze Bundle"]  = {"UpgradeCrystalCreature", 10},
}

local function simple_command(command)
    local ok, err = execute_console_command(command)
    if not ok then
        print(string.format("[GroundedArchipelago] %s failed to issue: %s -- will retry.\n", command, tostring(err)))
        return false
    end
    print(string.format("[GroundedArchipelago] Issued: %s\n", command))
    return true
end

-- Grouped recipe items -> their CraftingRecipeTable rows (UnlockRecipe).
local TIER_NAME_TO_RECIPE_ROWS = {
    -- Consumables: food, drink and healing.
    ["Consumables"] = {
        "Canteen", "Canteen+", "CanteenCharcoal", "AcornGranola",
        "Bandage", "BandageEfficient", "BoatmanFinSoup",
        "SmoothieFiber", "SmoothieGastroGoo", "SmoothieFuzzOnTheRocks", "SmoothieAphid",
        "SmoothieBerry", "SmoothieWaterBreathing", "SmoothieSwimSpeed", "SmoothieAttack",
        "SmoothieAnt", "SmoothieHumanFood", "SmoothieWasp", "SmoothieBoss", "SmoothieHealing",
        "BombHealing", "SausageBombHealing",
        "Spaghetflea", "SpiderSlider", "Larvagna", "Miteloaf", "MacNBees", "Gnatchos",
        "Funguspacho", "Omelant", "Quesadillantlion", "BlackOxBurger", "TermiteDelight",
        "TadpolePudding", "Wasperole", "Empanadust",
    },
    -- Utilities: light sources, repair tools and the like. (No harpoon items
    -- -- not implemented in the game. No TorchCharcoal -- that's the
    -- Everchar Torch's own item.)
    ["Utilities"] = {
        "Torch", "Torch+", "TorchMold",
        "Flare", "SmokeScreen", "Binoculars", "LeafBlower",
        "RepairHammer", "RepairArmor1", "RepairArmor2",
        "GunWater", "DecoyBait",
        "DivingLantern", "DivingLantern+", "LanternFirefly",
    },
}

local function unlock_blueprint_tier(tier_name)
    local recipe_rows = TIER_NAME_TO_RECIPE_ROWS[tier_name]
    if not recipe_rows or #recipe_rows == 0 then
        print(string.format(
            "[GroundedArchipelago] TODO: unlock blueprint tier '%s' -- no recipe row-name mapping " ..
            "yet (UnlockRecipe <name> is a real console command, see the file header; this tier " ..
            "just isn't mapped to any real recipe row names yet).\n",
            tier_name
        ))
        return true
    end

    local all_issued = true
    for _, recipe_row in ipairs(recipe_rows) do
        local ok, err = execute_console_command("UnlockRecipe " .. recipe_row)
        if not ok then
            print(string.format(
                "[GroundedArchipelago] UnlockRecipe %s failed to issue: %s -- will retry the whole " ..
                "tier next tick (UnlockRecipe is idempotent, so re-issuing already-succeeded ones is " ..
                "harmless).\n",
                recipe_row, tostring(err)
            ))
            all_issued = false
            break
        end
        print(string.format("[GroundedArchipelago] Issued: UnlockRecipe %s\n", recipe_row))
    end
    return all_issued
end

-- Gear recipe items: AP item name -> CraftingRecipeTable row (not always
-- the item row, e.g. Red Ant Club = recipe "ClubAnt", item "AntClub").
-- Keep in sync with apworld/grounded/gear.py.
local GEAR_ITEM_TO_RECIPE_ROW = {
    -- Tier 1
    ["Pebblet Axe"] = "Axe",
    ["Pebblet Hammer"] = "Hammer",
    ["Pebblet Spear"] = "Spear",
    ["Acorn Shovel"] = "Shovel",
    ["Sprig Bow"] = "Bow",
    ["Spiky Sprig"] = "SpikySprig",
    ["Clover Head Armor"] = "HeadClover",
    ["Clover Chest Armor"] = "ChestClover",
    ["Clover Leg Armor"] = "LegsClover",
    ["Acorn Head Armor"] = "HeadAcorn",
    ["Acorn Chest Armor"] = "ChestAcorn",
    ["Acorn Leg Armor"] = "LegsAcorn",
    ["Grub Head Armor"] = "HeadGrub",
    ["Grub Chest Armor"] = "ChestGrub",
    ["Grub Leg Armor"] = "LegsGrub",
    ["Ladybug Head Armor"] = "HeadLadybug",
    ["Ladybug Chest Armor"] = "ChestLadybug",
    ["Ladybug Leg Armor"] = "LegsLadybug",
    ["Bee Head Armor"] = "HeadBee",
    ["Bee Chest Armor"] = "ChestBee",
    ["Bee Leg Armor"] = "LegsBee",
    -- Tier 2
    ["Stinger Spear"] = "SpearTier2",
    ["Red Ant Club"] = "ClubAnt",
    ["Spider Fang Dagger"] = "DaggerSpider",
    ["Mosquito Needle"] = "RapierMosquito",
    ["Black Ant Sword"] = "SwordAntBlack",
    ["Ant Queen Scepter"] = "ScepterAntQueen",
    ["Insect Hammer"] = "HammerTier2",
    ["Insect Axe"] = "AxeTier2",
    ["Black Ant Shovel"] = "ShovelAntBlack",
    ["Insect Bow"] = "BowTier2",
    ["Crow Crossbow"] = "CrossbowCrow",
    ["Salt Arrow"] = "ArrowSalt",
    ["Mint Arrow"] = "ArrowMint",
    ["Spicy Arrow"] = "ArrowSpicy",
    ["Roman Candle"] = "RomanCandle",
    ["Everchar Torch"] = "TorchCharcoal",
    ["Black Ant Shield"] = "ShieldAntBlack",
    ["Bone Trident"] = "TridentBone",
    ["Feather Arrow"] = "ArrowCrow",
    ["Red Ant Head Armor"] = "HeadAnt",
    ["Red Ant Chest Armor"] = "ChestAnt",
    ["Red Ant Leg Armor"] = "LegsAnt",
    ["Black Ant Head Armor"] = "HeadAntBlack",
    ["Black Ant Chest Armor"] = "ChestAntBlack",
    ["Black Ant Leg Armor"] = "LegsAntBlack",
    ["Spider Head Armor"] = "HeadSpider",
    ["Spider Chest Armor"] = "ChestSpider",
    ["Spider Leg Armor"] = "LegsSpider",
    -- Tier 3
    ["Termite Axe"] = "AxeTier3",
    ["Black Ox Hammer"] = "HammerTier3",
    ["Rusty Spear"] = "SpearTier3",
    ["Ladybird Shield"] = "ShieldLadybird",
    ["Black Ox Crossbow"] = "CrossBowBlackOx",
    ["Tiger Mosquito Rapier"] = "RapierMosquitoTiger",
    ["Mint Mallet"] = "MintMallet",
    ["Spicy Mallet"] = "SpicyMallet",
    ["Sour Mallet"] = "SourMallet",
    ["Salt Morning Star"] = "MorningStarSalt",
    ["Salt Pickaxe"] = "PickaxeSalt",
    ["Mint Katana"] = "KatanaMint",
    ["Spicy Katana"] = "KatanaSpicy",
    ["Sour Katana"] = "KatanaSour",
    ["Mint Staff"] = "StaffMint",
    ["Spicy Staff"] = "StaffSpicy",
    ["Sour Staff"] = "StaffSour",
    ["Mint Battle Axe"] = "BattleAxeMint",
    ["Sour Battle Axe"] = "BattleAxeSour",
    ["Spicy Battle Axe"] = "BattleAxeSpicy",
    ["Mint Greatsword"] = "GreatswordMint",
    ["Sour Greatsword"] = "GreatswordSour",
    ["Spicy Great Axe"] = "GreatAxeSpicy",
    ["Mint Great Axe"] = "GreatAxeMint",
    ["Spicy Warhammer"] = "WarhammerSpicy",
    ["Sour Warhammer"] = "WarhammerSour",
    ["Widow Dagger"] = "DaggerSpiderWidow",
    ["Bone Dagger"] = "BoneDivingKnife",
    ["Mantis Head Armor"] = "HeadMantis",
    ["Mantis Chest Armor"] = "ChestMantis",
    ["Mantis Leg Armor"] = "LegMantis",
    ["Roly Poly Head Armor"] = "HeadRolyPoly",
    ["Roly Poly Chest Armor"] = "ChestRolyPoly",
    ["Roly Poly Leg Armor"] = "LegsRolyPoly",
    ["Black Ox Head Armor"] = "HeadBlackOx",
    ["Black Ox Chest Armor"] = "ChestBlackOx",
    ["Black Ox Leg Armor"] = "LegsBlackOx",
    ["Antlion Head Armor"] = "HeadAntlion",
    ["Antlion Chest Armor"] = "ChestAntlion",
    ["Antlion Leg Armor"] = "LegsAntlion",
    -- Side armor (gear.py's Gear.side)
    ["Koi Head Armor"] = "KoiFishScaleHelmet",
    ["Koi Chest Armor"] = "KoiFishScaleChestPlate",
    ["Koi Leg Armor"] = "KoiFishScaleLegPlates",
    ["Fire Ant Head Armor"] = "HeadAntFire",
    ["Fire Ant Chest Armor"] = "ChestAntFire",
    ["Fire Ant Leg Armor"] = "LegsAntFire",
    ["Moth Head Armor"] = "HeadMoth",
    ["Moth Chest Armor"] = "ChestMoth",
    ["Moth Leg Armor"] = "LegsMoth",
    ["Wasp Head Armor"] = "HeadWasp",
    ["Wasp Chest Armor"] = "ChestWasp",
    ["Wasp Leg Armor"] = "LegsWasp",
    ["Eyepatch"] = "HeadEyepatch",
    ["Mite Hat"] = "HeadMite",
    ["Firefly Head Lamp"] = "HeadFirefly",
    ["Lucky Hat"] = "HeadLuckyHat",
    ["Marksman's Cap"] = "HeadCrowArcher",
    ["Wizard Hat"] = "HeadCrowWizard",
    ["Termite Armor"] = "ChestTermite",
    ["Aphid Slippers"] = "LegsAphid",
}

local function unlock_single_recipe(item_name)
    local recipe_row = GEAR_ITEM_TO_RECIPE_ROW[item_name]
    if not recipe_row then
        print(string.format(
            "[GroundedArchipelago] TODO: unlock recipe for '%s' -- no row-name mapping.\n", item_name
        ))
        return true
    end
    local ok, err = execute_console_command("UnlockRecipe " .. recipe_row)
    if not ok then
        print(string.format(
            "[GroundedArchipelago] UnlockRecipe %s failed to issue: %s -- will retry.\n",
            recipe_row, tostring(err)
        ))
        return false
    end
    print(string.format("[GroundedArchipelago] Issued: UnlockRecipe %s\n", recipe_row))
    return true
end

-- Unlocks a fixed list of recipe rows (idempotent, retried as a whole).
local function unlock_recipe_rows(rows)
    for _, row in ipairs(rows) do
        local ok, err = execute_console_command("UnlockRecipe " .. row)
        if not ok then
            print(string.format(
                "[GroundedArchipelago] UnlockRecipe %s failed to issue: %s -- will retry.\n", row, tostring(err)
            ))
            return false
        end
        print(string.format("[GroundedArchipelago] Issued: UnlockRecipe %s\n", row))
    end
    return true
end

-- Gear items -> the recipes they unlock (research unlocks are disabled).
local GEAR_ITEM_TO_RECIPE_ROWS = {
    ["Gas Mask"] = {"GasMask"},
    ["Diving Gear"] = {"DivingMask", "Rebreather", "Flippers"},
}

-- Building recipes: UPartyComponent:AddKnownBuildingRecipeByName (UnlockRecipe
-- only handles crafting recipes). False only when the game isn't ready.
local function unlock_building_recipe(row)
    local controller = get_local_player_controller()
    if not controller then
        return false, "no local PlayerController"
    end
    local gs_ok, game_state = pcall(objects.find_first, "SurvivalGameState")
    if not gs_ok or not game_state then
        return false, "no SurvivalGameState"
    end
    local ok, result = pcall(function()
        local party = game_state.PartyComponent
        local get_ok, unwrapped = pcall(function() return party:get() end)
        party = (get_ok and unwrapped) or party
        return party:AddKnownBuildingRecipeByName(FName(row), controller.PlayerState, false)
    end)
    if not ok then
        return false, tostring(result)
    end
    return true
end

local function unlock_building_rows(rows)
    for _, row in ipairs(rows) do
        local ok, err = unlock_building_recipe(row)
        if not ok then
            print(string.format(
                "[GroundedArchipelago] Building recipe %s failed to unlock: %s -- will retry.\n", row, tostring(err)
            ))
            return false
        end
        print(string.format("[GroundedArchipelago] Unlocked building recipe: %s\n", row))
    end
    return true
end

-- Station items -> BuildingRecipeTable rows: Smoothie Station "MashBowl",
-- Cookery "CookingStation", Oven "Smelter" (globs, jewels, boss keys). The
-- Roasting Spit ("Campfire") and Drying Rack are unlocked at the start by
-- research_control.lua; ROASTING_SPIT_ROWS only serves older rooms that can
-- still send a "Roasting Spit" item.
local STATION_ITEM_TO_BUILDING_ROWS = {
    ["Smoothie Station"] = {"MashBowl"},
    ["Cookery"] = {"CookingStation"},
    ["Oven"] = {"Smelter"},
}

local ROASTING_SPIT_ROWS = {"Campfire", "DryingRack"}

local function unlock_station(item_name)
    return unlock_building_rows(STATION_ITEM_TO_BUILDING_ROWS[item_name])
end

local function give_key_item(row_name)
    return grant_item_by_row_name(row_name, 1)
end


-- AP item name -> grant function (names must match items.py's item_table).
-- Each closure must `return` the inner result: false means "retry later",
-- and dropping it makes the sync loop think the item applied.
local grant_table = {
    ["Gas Mask"]               = function() return unlock_recipe_rows(GEAR_ITEM_TO_RECIPE_ROWS["Gas Mask"]) end,
    ["Diving Gear"]            = function() return unlock_recipe_rows(GEAR_ITEM_TO_RECIPE_ROWS["Diving Gear"]) end,
    ["Zip Line Rig"]           = function() return give_key_item("KeyZiplineAscender") end,

    ["Roasting Spit"]         = function() return unlock_building_rows(ROASTING_SPIT_ROWS) end,
    ["Smoothie Station"]      = function() return unlock_station("Smoothie Station") end,
    ["Cookery"]               = function() return unlock_station("Cookery") end,
    ["Oven"]                  = function() return unlock_station("Oven") end,
    ["Consumables"]           = function() return unlock_blueprint_tier("Consumables") end,
    ["Utilities"]             = function() return unlock_blueprint_tier("Utilities") end,


    -- 2500 (was 500): science is the main currency early on, and with a
    -- lot more filler in the pool each bundle needs to be worth grabbing.
    ["Raw Science Bundle"]   = function() return give_science(2500) end,
    ["Full Restore"]         = function() return simple_command("FullRestore") end,
}

for item_name, bundle in pairs(RESOURCE_BUNDLES) do
    grant_table[item_name] = function() return grant_item_by_row_name(bundle[1], bundle[2]) end
end

-- Every individual gear recipe item (see GEAR_ITEM_TO_RECIPE_ROW).
for item_name, _ in pairs(GEAR_ITEM_TO_RECIPE_ROW) do
    grant_table[item_name] = function() return unlock_single_recipe(item_name) end
end

-- ProgressiveGear: the Nth copy unlocks the first N recipes of its line
-- (UnlockRecipe is idempotent; lines come from ap_data.lua).
local PROGRESSIVE_LINES = require("ap_data").PROGRESSIVE_LINES

local function unlock_progressive(item_name, copy)
    local line = PROGRESSIVE_LINES[item_name]
    local rows = {}
    for i = 1, math.min(copy or 1, #line) do
        rows[#rows + 1] = line[i]
    end
    return unlock_recipe_rows(rows)
end

-- True if applied (ipc advances past it), false to retry next poll (e.g.
-- still on the main menu). `copy`: which copy of the item (progressive).
function M.apply(item_name, copy)
    if PROGRESSIVE_LINES[item_name] then
        local ok, result = pcall(unlock_progressive, item_name, copy)
        if not ok then
            print(string.format("[GroundedArchipelago] Error applying item '%s': %s\n", item_name, tostring(result)))
            return false
        end
        return result ~= false
    end
    local fn = grant_table[item_name]
    if not fn then
        print(string.format("[GroundedArchipelago] Received unknown item '%s', ignoring\n", item_name))
        return true -- don't get stuck retrying something we'll never recognize
    end
    local ok, result = pcall(fn)
    if not ok then
        print(string.format("[GroundedArchipelago] Error applying item '%s': %s\n", item_name, tostring(result)))
        return false
    end
    if result == false then
        return false -- explicit "try again later" signal
    end
    return true
end

-- UnlockRecipe for one recipe row, outside the AP item table.
function M.unlock_recipe_row(recipe_row)
    local ok, err = execute_console_command("UnlockRecipe " .. recipe_row)
    if not ok then
        print(string.format(
            "[GroundedArchipelago] UnlockRecipe %s (via item-use) failed to issue: %s\n",
            recipe_row, tostring(err)
        ))
        return false
    end
    print(string.format("[GroundedArchipelago] Issued (via item-use): UnlockRecipe %s\n", recipe_row))
    return true
end

-- ---------------------------------------------------------------------
-- Every recipe row an AP item can unlock. research_control.lua strips them
-- from every other unlock source (pickups, BURG.L tech trees).
-- ---------------------------------------------------------------------
function M.get_managed_recipe_rows()
    local rows = {}
    for _, row in pairs(GEAR_ITEM_TO_RECIPE_ROW) do
        rows[row] = true
    end
    for _, list in pairs(GEAR_ITEM_TO_RECIPE_ROWS) do
        for _, row in ipairs(list) do
            rows[row] = true
        end
    end
    for _, list in pairs(TIER_NAME_TO_RECIPE_ROWS) do
        for _, row in ipairs(list) do
            rows[row] = true
        end
    end
    for _, list in pairs(PROGRESSIVE_LINES) do
        for _, row in ipairs(list) do
            rows[row] = true
        end
    end
    return rows
end

-- Station building rows (AP items) -- research_control.lua must never
-- unlock these through its category unlocks.
function M.get_managed_building_rows()
    local rows = {}
    for _, list in pairs(STATION_ITEM_TO_BUILDING_ROWS) do
        for _, row in ipairs(list) do
            rows[row] = true
        end
    end
    return rows
end

-- Item row whose icon the in-game popup can show for a received AP item
-- (gear recipes, progressive gear, resource bundles), or nil. Recipe rows
-- double as item rows for nearly all gear.
function M.icon_row(item_name, copy)
    local line = PROGRESSIVE_LINES[item_name]
    if line then
        return line[math.max(1, math.min(copy or 1, #line))]
    end
    if GEAR_ITEM_TO_RECIPE_ROW[item_name] then
        return GEAR_ITEM_TO_RECIPE_ROW[item_name]
    end
    local bundle = RESOURCE_BUNDLES[item_name]
    return bundle and bundle[1] or nil
end

M.get_item_data_table = get_item_data_table
M.unlock_building_recipe = unlock_building_recipe
M.execute_console_command = execute_console_command
M.get_local_player_controller = get_local_player_controller


return M
