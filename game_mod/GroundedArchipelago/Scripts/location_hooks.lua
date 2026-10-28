-- location_hooks.lua
--
-- Turns in-game events into ipc:report_location(...) calls.
--
-- UE4SS notes for this build:
-- 1. RegisterHook callbacks are PRE-hooks for /Script/ (native) paths and
--    POST-hooks for /Game/ (Blueprint) paths. Params arrive as
--    `Context, <the UFunction's params>`; only strings, bools and
--    FOutputDevice are plain Lua values -- everything else needs :get().
-- 2. A hooked UFunction must already be loaded, so registration is retried
--    on a timer (register_hook_with_retry).

local M = {}

local objects = require("ap_objects")
local ap_loop = require("ap_loop")
local item_grants = require("item_grants")
local research_control = require("research_control")
local deathlink = require("deathlink")
local ending_gate = require("ending_gate")
local drop_shuffle = require("drop_shuffle")

-- A bool property can come back as a UObject reference (truthy in Lua);
-- only an actual Lua boolean counts, otherwise nil (unknown).
local function read_bool_property(obj, field_name)
    local ok, raw = pcall(function() return obj[field_name] end)
    if not ok then
        return nil, raw
    end
    if type(raw) == "boolean" then
        return raw
    end
    local get_ok, unwrapped = pcall(function() return raw:get() end)
    if get_ok and type(unwrapped) == "boolean" then
        return unwrapped
    end
    return nil, string.format(
        "field read didn't error, but wasn't a real boolean either (got %s, tostring: %s)",
        type(raw), tostring(raw)
    )
end

-- Hook params (Context included) arrive wrapped: :get() once, then do all
-- property/method access on the result. Falls back to the value itself.
local function unwrap_param(value)
    local ok, unwrapped = pcall(function() return value:get() end)
    if ok and unwrapped ~= nil then
        return unwrapped
    end
    return value
end

-- RowName (an FName) of an FDataTableRowHandle-shaped struct -- unwrap the
-- handle itself first.
local function get_row_name(RowHandle)
    local name_ok, name_value = pcall(function() return RowHandle.RowName end)
    if not name_ok then
        return nil, name_value
    end
    if type(name_value) == "string" then
        return name_value
    end
    local tostr_ok, tostr_val = pcall(function() return name_value:ToString() end)
    if tostr_ok and type(tostr_val) == "string" then
        return tostr_val
    end
    local get_ok, unwrapped = pcall(function() return name_value:get() end)
    if get_ok and unwrapped ~= nil then
        if type(unwrapped) == "string" then
            return unwrapped
        end
        local inner_ok, inner_val = pcall(function() return unwrapped:ToString() end)
        if inner_ok and type(inner_val) == "string" then
            return inner_val
        end
    end
    local plain_ok, plain_val = pcall(tostring, name_value)
    if plain_ok then
        return plain_val
    end
    return nil, "couldn't read RowName in any form"
end

-- Tries once now, then on a timer until the class is loaded and the hook
-- registers.
local function register_hook_with_retry(description, path, callback, retry_interval_ms)
    local registered = false

    local function try_once()
        local ok, err = pcall(RegisterHook, path, callback)
        if ok then
            registered = true
            print(string.format("[GroundedArchipelago] Hook registered: %s (%s)\n", description, path))
        end
        return ok, err
    end

    local ok, err = try_once()
    if ok then
        return
    end

    print(string.format(
        "[GroundedArchipelago] Hook '%s' not ready yet (%s) -- will retry every %dms\n",
        description, tostring(err), retry_interval_ms
    ))
    ap_loop.start_loop(retry_interval_ms, function()
        if not registered then
            try_once()
        end
    end)
end

-- ---------------------------------------------------------------------
-- Item pickups, via BP_QuestManagerComponent_C:HandleOnItemAdded
--
-- ItemName is a proxy: tostring() gives "RemoteUnrealParam: 0x..." and
-- :get() an FString needing :ToString(). Neither errors, so get_item_name()
-- checks the result doesn't look like a proxy printout.
-- ---------------------------------------------------------------------

local warned_about_item_name_unwrap = false

-- "<TypeName>: <hex address>" -- an un-decoded UE4SS proxy.
local function looks_like_unresolved_proxy(s)
    return type(s) == "string" and s:match("^%a[%a_]*: %x+$") ~= nil
end

-- `value` as a real Lua string (string, :ToString(), tostring()), or nil.
local function try_extract_string(value)
    if type(value) == "string" and not looks_like_unresolved_proxy(value) then
        return value
    end
    local tostr_ok, tostr_val = pcall(function() return value:ToString() end)
    if tostr_ok and type(tostr_val) == "string" and not looks_like_unresolved_proxy(tostr_val) then
        return tostr_val
    end
    local plain_ok, plain_val = pcall(tostring, value)
    if plain_ok and type(plain_val) == "string" and not looks_like_unresolved_proxy(plain_val) then
        return plain_val
    end
    return nil
end

local function get_item_name(ItemName)
    -- Attempt 1: maybe ItemName itself is already usable directly.
    local direct = try_extract_string(ItemName)
    if direct then
        return direct
    end

    -- What :get() returns may still need :ToString().
    local get_ok, unwrapped = pcall(function() return ItemName:get() end)
    if get_ok and unwrapped ~= nil then
        local extracted = try_extract_string(unwrapped)
        if extracted then
            return extracted
        end
    end

    if not warned_about_item_name_unwrap then
        warned_about_item_name_unwrap = true
        print(
            "[GroundedArchipelago] WARNING: couldn't turn ItemName into real text -- tried it " ..
            "directly, :ToString(), :get(), and :get():ToString(), and every attempt either errored " ..
            "or still looked like an unresolved proxy printout (e.g. 'FString: 0000...') rather than " ..
            "actual text. Falling back to raw tostring(), which will look the same. This needs a " ..
            "different UE4SS accessor for reading an FString hook parameter on your build -- check " ..
            "UE4SS's Lua docs/examples and report back what works.\n"
        )
    end

    local ok, name = pcall(tostring, ItemName)
    if not ok then
        return nil
    end
    return name
end

-- One-time dump of every Table_AllItems row (for checking item names), and
-- hands the table to item_grants.lua.
local dumped_item_table = false

local function dump_full_item_table_once()
    if dumped_item_table then
        return
    end

    -- GlobalTableData is reachable as soon as a save is loaded.
    local global_ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if not global_ok or not global_data then
        return -- retry next call -- don't mark done until GlobalTableData is actually found
    end
    dumped_item_table = true

    local dt_ok, data_table = pcall(function() return global_data.AllItemsTable end)
    if not dt_ok or not data_table then
        print(string.format(
            "[GroundedArchipelago] Couldn't read GlobalTableData.AllItemsTable to dump the full " ..
            "item table (%s).\n",
            tostring(data_table)
        ))
        return
    end
    data_table = unwrap_param(data_table)

    -- item_grants.lua needs the same table for GiveItem row handles.
    local note_ok, note_err = pcall(item_grants.note_item_data_table, data_table)
    if not note_ok then
        print(string.format(
            "[GroundedArchipelago] item_grants.note_item_data_table failed: %s\n", tostring(note_err)
        ))
    end

    local names_ok, row_names = pcall(function() return data_table:GetRowNames() end)
    if not names_ok then
        print(string.format(
            "[GroundedArchipelago] DataTable:GetRowNames() errored: %s -- either your UE4SS build " ..
            "doesn't have UDataTable Lua support (added in UE4SS #997; check your version), or the " ..
            "AllItemsTable reference itself isn't usable.\n",
            tostring(row_names)
        ))
        return
    end

    local count_ok, count = pcall(function() return #row_names end)
    print(string.format(
        "[GroundedArchipelago] === FULL ITEM TABLE DUMP: %s rows ===\n",
        count_ok and tostring(count) or "?"
    ))
    if count_ok then
        for i = 1, count do
            local row_ok, row_name = pcall(function() return row_names[i] end)
            -- FBaseItemData.Tier: for weapons/tools, the harvest tier
            -- (e.g. which dagger cuts which resources).
            local tier = "?"
            if row_ok then
                pcall(function()
                    tier = tostring(unwrap_param(data_table:FindRow(row_name)).Tier)
                end)
            end
            print(string.format(
                "[GroundedArchipelago] ITEM_ROW: %s | tier=%s\n",
                row_ok and tostring(row_name) or "<unreadable>", tier
            ))
        end
    end
    print("[GroundedArchipelago] === END FULL ITEM TABLE DUMP ===\n")
end

-- ---------------------------------------------------------------------
-- One-time dump of GlobalTableData.BestiaryTable: every creature's pawn
-- class (FBestiaryData.Creature, a TSoftClassPtr).
-- ---------------------------------------------------------------------
local dumped_bestiary_creatures = false

-- TSoftClassPtr -> "<package path>.<class>": GetObjectID() then
-- GetAssetPathName() + GetSubPathString() (per UE4SS's LuaTSoftObjectPtr.cpp).
-- The other attempts are fallbacks for other UE4SS builds.
local function read_soft_class_path(soft_class_ptr, log_which_attempt)
    local confirmed_ok, confirmed_result = pcall(function()
        local object_id = soft_class_ptr:GetObjectID()
        local asset_path_name = object_id:GetAssetPathName()
        local sub_path_string = object_id:GetSubPathString()
        local asset_path_ok, asset_path_str = pcall(function() return asset_path_name:ToString() end)
        local sub_path_ok, sub_path_str = pcall(function() return sub_path_string:ToString() end)
        asset_path_str = (asset_path_ok and type(asset_path_str) == "string") and asset_path_str or tostring(asset_path_name)
        sub_path_str = (sub_path_ok and type(sub_path_str) == "string") and sub_path_str or tostring(sub_path_string)
        return asset_path_str .. "." .. sub_path_str
    end)
    if confirmed_ok and type(confirmed_result) == "string" and confirmed_result ~= "." then
        if log_which_attempt then
            print("[GroundedArchipelago] Bestiary Creature path read via: GetObjectID/GetAssetPathName+GetSubPathString\n")
        end
        return confirmed_result
    end

    local attempts = {
        {"ToString", function() return soft_class_ptr:ToString() end},
        {"GetAssetPathString", function() return soft_class_ptr:GetAssetPathString() end},
        {"ToSoftObjectPath():ToString()", function() return soft_class_ptr:ToSoftObjectPath():ToString() end},
    }
    for _, attempt in ipairs(attempts) do
        local name, fn = attempt[1], attempt[2]
        local ok, result = pcall(fn)
        if ok and type(result) == "string" and result ~= "" then
            if log_which_attempt then
                print(string.format("[GroundedArchipelago] Bestiary Creature path read via: %s\n", name))
            end
            return result
        end
    end
    local ok, plain = pcall(tostring, soft_class_ptr)
    return ok and plain or "<unreadable>"
end

local function dump_bestiary_creature_classes_once()
    if dumped_bestiary_creatures then
        return
    end
    local global_ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if not global_ok or not global_data then
        return -- retry next call
    end
    dumped_bestiary_creatures = true

    local bt_ok, bestiary_table = pcall(function() return global_data.BestiaryTable end)
    if not bt_ok or not bestiary_table then
        print(string.format(
            "[GroundedArchipelago] Couldn't read GlobalTableData.BestiaryTable to dump creature " ..
            "classes (%s).\n",
            tostring(bestiary_table)
        ))
        return
    end
    bestiary_table = unwrap_param(bestiary_table)

    local names_ok, row_names = pcall(function() return bestiary_table:GetRowNames() end)
    if not names_ok then
        print(string.format(
            "[GroundedArchipelago] BestiaryTable:GetRowNames() errored: %s\n", tostring(row_names)
        ))
        return
    end

    local count_ok, count = pcall(function() return #row_names end)
    print(string.format(
        "[GroundedArchipelago] === BESTIARY CREATURE CLASS DUMP: %s rows ===\n",
        count_ok and tostring(count) or "?"
    ))
    if count_ok then
        for i = 1, count do
            local row_name_ok, row_name = pcall(function() return row_names[i] end)
            if row_name_ok then
                local row_ok, row = pcall(function() return bestiary_table:FindRow(row_name) end)
                if row_ok and row then
                    row = unwrap_param(row)
                    local creature_ok, creature_ptr = pcall(function() return row.Creature end)
                    if creature_ok and creature_ptr then
                        local path = read_soft_class_path(creature_ptr, i == 1)
                        print(string.format(
                            "[GroundedArchipelago] BESTIARY_CREATURE: %s -> %s\n",
                            tostring(row_name), path
                        ))
                    else
                        print(string.format(
                            "[GroundedArchipelago] BESTIARY_CREATURE: %s -> <couldn't read Creature field: %s>\n",
                            tostring(row_name), tostring(creature_ptr)
                        ))
                    end
                else
                    print(string.format(
                        "[GroundedArchipelago] BESTIARY_CREATURE: %s -> <FindRow failed: %s>\n",
                        tostring(row_name), tostring(row)
                    ))
                end
            end
        end
    end
    print("[GroundedArchipelago] === END BESTIARY CREATURE CLASS DUMP ===\n")
end

-- One-time dump of CraftingRecipeTable (recipe rows for UnlockRecipe,
-- which aren't always the item rows).
-- ---------------------------------------------------------------------
local dumped_crafting_recipe_table = false

local function dump_crafting_recipe_table_once()
    if dumped_crafting_recipe_table then
        return
    end

    local global_ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if not global_ok or not global_data then
        return -- retry next call -- don't mark done until GlobalTableData is actually found
    end
    dumped_crafting_recipe_table = true

    local table_ok, recipe_table = pcall(function() return global_data.CraftingRecipeTable end)
    if not table_ok or not recipe_table then
        print(string.format(
            "[GroundedArchipelago] Couldn't read GlobalTableData.CraftingRecipeTable (%s).\n",
            tostring(recipe_table)
        ))
        return
    end
    recipe_table = unwrap_param(recipe_table)

    local names_ok, row_names = pcall(function() return recipe_table:GetRowNames() end)
    if not names_ok then
        print(string.format(
            "[GroundedArchipelago] CraftingRecipeTable:GetRowNames() errored: %s\n", tostring(row_names)
        ))
        return
    end

    local count_ok, count = pcall(function() return #row_names end)
    print(string.format(
        "[GroundedArchipelago] === FULL CRAFTING RECIPE TABLE DUMP: %s rows ===\n",
        count_ok and tostring(count) or "?"
    ))
    if count_ok then
        for i = 1, count do
            local row_ok, row_name = pcall(function() return row_names[i] end)
            -- FRecipeData.CraftingBuildingTag: which building crafts it
            -- (e.g. the Oven for jewels); empty for the player's own menu.
            local tag = "?"
            if row_ok then
                pcall(function()
                    local row = unwrap_param(recipe_table:FindRow(row_name))
                    tag = row.CraftingBuildingTag.TagName:ToString()
                end)
            end
            print(string.format(
                "[GroundedArchipelago] RECIPE_ROW: %s | building=%s\n",
                row_ok and tostring(row_name) or "<unreadable>", tag
            ))
        end
    end
    print("[GroundedArchipelago] === END FULL CRAFTING RECIPE TABLE DUMP ===\n")
end

-- Runs the static-data dumps from main.lua's poll loop, each retrying until
-- GlobalTableData is found.
local dumped_player_upgrades_table = false

local function dump_player_upgrades_table_once()
    if dumped_player_upgrades_table then
        return
    end

    local global_ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if not global_ok or not global_data then
        return -- retry next call -- don't mark done until GlobalTableData is actually found
    end
    dumped_player_upgrades_table = true

    local table_ok, upgrades_table = pcall(function() return global_data.PlayerUpgradesTable end)
    if not table_ok or not upgrades_table then
        print(string.format(
            "[GroundedArchipelago] Couldn't read GlobalTableData.PlayerUpgradesTable (%s).\n",
            tostring(upgrades_table)
        ))
        return
    end
    upgrades_table = unwrap_param(upgrades_table)

    local names_ok, row_names = pcall(function() return upgrades_table:GetRowNames() end)
    if not names_ok then
        print(string.format(
            "[GroundedArchipelago] PlayerUpgradesTable:GetRowNames() errored: %s\n", tostring(row_names)
        ))
        return
    end

    local count_ok, count = pcall(function() return #row_names end)
    print(string.format(
        "[GroundedArchipelago] === FULL PLAYER UPGRADES (MUTATIONS) TABLE DUMP: %s rows ===\n",
        count_ok and tostring(count) or "?"
    ))
    if count_ok then
        for i = 1, count do
            local row_ok, row_name = pcall(function() return row_names[i] end)
            print(string.format(
                "[GroundedArchipelago] PLAYER_UPGRADE_ROW: %s\n",
                row_ok and tostring(row_name) or "<unreadable>"
            ))
        end
    end
    print("[GroundedArchipelago] === END FULL PLAYER UPGRADES TABLE DUMP ===\n")
end

-- ---------------------------------------------------------------------
-- Story / super chip events (LOG ONLY -- "STORY:" lines, no checks yet).
-- UQuestManagerComponent:MulticastCompleteQuest / MulticastCompleteObjective,
-- UPartyComponent:ServerSetLastSuperChipReturned and
-- MulticastNotifyKeyItemCollected, plus a one-time quest table dump.
-- ---------------------------------------------------------------------
local dumped_quest_table = false

local function dump_quest_table_once()
    if dumped_quest_table then
        return
    end
    local global_ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if not global_ok or not global_data then
        return
    end
    dumped_quest_table = true
    local table_ok, quests = pcall(function() return global_data.QuestsTable end)
    if not table_ok or not quests then
        print("[GroundedArchipelago] Couldn't read GlobalTableData.QuestsTable\n")
        return
    end
    quests = unwrap_param(quests)
    local names_ok, row_names = pcall(function() return quests:GetRowNames() end)
    if not names_ok or not row_names then
        return
    end
    print(string.format("[GroundedArchipelago] === QUEST TABLE DUMP: %d rows ===\n", #row_names))
    for i = 1, #row_names do
        local row_name = row_names[i]
        pcall(function()
            local row = unwrap_param(quests:FindRow(row_name))
            local crit_ok, crit = pcall(function() return row.IsCritPathQuest end)
            local display = try_extract_string(row.DisplayName) or "?"
            local needs = {}
            pcall(function()
                local objectives = row.Objectives
                for j = 1, #objectives do
                    local obj = unwrap_param(objectives[j])
                    local item_ok, item = pcall(get_row_name, unwrap_param(obj.RecipeOrItem))
                    if item_ok and item and item ~= "None" then
                        table.insert(needs, item)
                    end
                end
            end)
            print(string.format(
                "[GroundedArchipelago] QUEST_ROW: %s | crit=%s | name=%s | objective items: %s\n",
                tostring(row_name), crit_ok and tostring(crit) or "?", display,
                #needs > 0 and table.concat(needs, ", ") or "-"
            ))
        end)
    end
    print("[GroundedArchipelago] === END QUEST TABLE DUMP ===\n")
end

local function register_story_discovery_hooks(config)
    local function row_of(handle)
        local ok, name = pcall(get_row_name, unwrap_param(handle))
        return ok and tostring(name) or "?"
    end
    local function int_of(value)
        local ok, v = pcall(function() return value:get() end)
        return ok and v or value
    end
    register_hook_with_retry("story: quest complete (log only)",
        "/Script/Maine.QuestManagerComponent:MulticastCompleteQuest",
        function(_Context, QuestRowHandle, _PlayerState)
            print(string.format("[GroundedArchipelago] STORY: quest complete '%s'\n", row_of(QuestRowHandle)))
        end, config.hook_retry_interval_ms)
    register_hook_with_retry("story: objective complete (log only)",
        "/Script/Maine.QuestManagerComponent:MulticastCompleteObjective",
        function(_Context, QuestRowHandle, QuestIndex, _PlayerState)
            print(string.format("[GroundedArchipelago] STORY: objective %s of quest '%s' complete\n",
                tostring(int_of(QuestIndex)), row_of(QuestRowHandle)))
        end, config.hook_retry_interval_ms)
    register_hook_with_retry("story: key item collected (log only)",
        "/Script/Maine.PartyComponent:MulticastNotifyKeyItemCollected",
        function(_Context, ItemRowHandle, _PlayerState, _Recipes)
            print(string.format("[GroundedArchipelago] STORY: key item collected '%s'\n", row_of(ItemRowHandle)))
        end, config.hook_retry_interval_ms)
    register_hook_with_retry("story: super chip returned (log only)",
        "/Script/Maine.PartyComponent:ServerSetLastSuperChipReturned",
        function(_Context, Item)
            print(string.format("[GroundedArchipelago] STORY: super chip returned '%s'\n", row_of(Item)))
        end, config.hook_retry_interval_ms)
end

local function dump_static_data_once()
    dump_quest_table_once()
    dump_full_item_table_once()
    dump_crafting_recipe_table_once()
    dump_bestiary_creature_classes_once()
    dump_player_upgrades_table_once()
end

-- ItemName -> extra AP location name (besides the "Item: " one).
local item_pickup_to_location = {
    -- fill in with real names as they're discovered, e.g. ["Chip_OakLab"] = "some location name"
}

-- Every pickup is reported as "Item: <ItemName>"; names the seed doesn't
-- have are ignored by the client. Keep in sync with itemsanity.py.
local ITEM_LOCATION_PREFIX = "Item: "

-- Keep in sync with goldcards.py. Gold cards are item rows containing
-- "Gold" (Bestiary<Creature>Gold), matched by row name.
local GOLD_CARD_LOCATION_PREFIX = "Gold Card: "

-- Keep in sync with killsanity.py's KILL_LOCATION_PREFIX.
local KILL_LOCATION_PREFIX = "Kill: "

-- Keep in sync with craftsanity.py's CRAFT_LOCATION_PREFIX and
-- CRAFTSANITY_ROW_TO_DISPLAY_NAME (matched by item row name).
local CRAFT_LOCATION_PREFIX = "Craft: "
local CRAFTSANITY_ROW_TO_DISPLAY_NAME = {
    Axe = "Pebblet Axe",
    Hammer = "Pebblet Hammer",
    Spear = "Pebblet Spear",
    Shovel = "Acorn Shovel",
    Bow = "Sprig Bow",
    SpikySprig = "Spiky Sprig",
    HeadClover = "Clover Head Armor",
    ChestClover = "Clover Chest Armor",
    LegsClover = "Clover Leg Armor",
    HeadAcorn = "Acorn Head Armor",
    ChestAcorn = "Acorn Chest Armor",
    LegsAcorn = "Acorn Leg Armor",
    HeadGrub = "Grub Head Armor",
    ChestGrub = "Grub Chest Armor",
    LegsGrub = "Grub Leg Armor",
    HeadLadybug = "Ladybug Head Armor",
    ChestLadybug = "Ladybug Chest Armor",
    LegsLadybug = "Ladybug Leg Armor",
    HeadBee = "Bee Head Armor",
    ChestBee = "Bee Chest Armor",
    LegsBee = "Bee Leg Armor",
    SpearTier2 = "Stinger Spear",
    AntClub = "Red Ant Club",
    DaggerSpider = "Spider Fang Dagger",
    RapierMosquito = "Mosquito Needle",
    SwordAntBlack = "Black Ant Sword",
    AntQueenScepter = "Ant Queen Scepter",
    HammerTier2 = "Insect Hammer",
    AxeTier2 = "Insect Axe",
    ShovelAntBlack = "Black Ant Shovel",
    BowTier2 = "Insect Bow",
    CrossbowCrow = "Crow Crossbow",
    ArrowSalt = "Salt Arrow",
    ArrowMint = "Mint Arrow",
    ArrowSpicy = "Spicy Arrow",
    RomanCandle = "Roman Candle",
    TorchCharcoal = "Everchar Torch",
    ShieldAntBlack = "Black Ant Shield",
    TridentBone = "Bone Trident",
    ArrowCrow = "Feather Arrow",
    HeadAnt = "Red Ant Head Armor",
    ChestAnt = "Red Ant Chest Armor",
    LegsAnt = "Red Ant Leg Armor",
    HeadAntBlack = "Black Ant Head Armor",
    ChestAntBlack = "Black Ant Chest Armor",
    LegsAntBlack = "Black Ant Leg Armor",
    HeadSpider = "Spider Head Armor",
    ChestSpider = "Spider Chest Armor",
    LegsSpider = "Spider Leg Armor",
    AxeTier3 = "Termite Axe",
    HammerTier3 = "Black Ox Hammer",
    SpearTier3 = "Rusty Spear",
    ShieldLadybird = "Ladybird Shield",
    CrossBowBlackOx = "Black Ox Crossbow",
    RapierMosquitoTiger = "Tiger Mosquito Rapier",
    MintMallet = "Mint Mallet",
    SpicyMallet = "Spicy Mallet",
    SourMallet = "Sour Mallet",
    MorningStarSalt = "Salt Morning Star",
    PickAxeSalty = "Salt Pickaxe",
    KatanaMint = "Mint Katana",
    KatanaSpicy = "Spicy Katana",
    KatanaSour = "Sour Katana",
    StaffMint = "Mint Staff",
    StaffSpicy = "Spicy Staff",
    StaffSour = "Sour Staff",
    BattleAxeMint = "Mint Battle Axe",
    BattleAxeSour = "Sour Battle Axe",
    BattleAxeSpicy = "Spicy Battle Axe",
    GreatswordMint = "Mint Greatsword",
    GreatswordSour = "Sour Greatsword",
    GreatAxeSpicy = "Spicy Great Axe",
    GreatAxeMint = "Mint Great Axe",
    WarhammerSpicy = "Spicy Warhammer",
    WarhammerSour = "Sour Warhammer",
    DaggerSpiderWidow = "Widow Dagger",
    BoneDivingKnife = "Bone Dagger",
    HeadMantis = "Mantis Head Armor",
    ChestMantis = "Mantis Chest Armor",
    LegsMantis = "Mantis Leg Armor",
    HeadRolyPoly = "Roly Poly Head Armor",
    ChestRolyPoly = "Roly Poly Chest Armor",
    LegsRolyPoly = "Roly Poly Leg Armor",
    HeadBlackOx = "Black Ox Head Armor",
    ChestBlackOx = "Black Ox Chest Armor",
    LegsBlackOx = "Black Ox Leg Armor",
    HeadAntlion = "Antlion Head Armor",
    ChestAntlion = "Antlion Chest Armor",
    LegsAntlion = "Antlion Leg Armor",
    Canteen = "Canteen",
    ["Canteen+"] = "Upgraded Canteen",
    CanteenCharcoal = "Charcoal Canteen",
    GranolaAcorn = "Acorn Granola",
    Bandage = "Bandage",
    MealTier1BoatmanSoap = "Boatman Fin Soup",
    SmoothieFiber = "Fiber Smoothie",
    SmoothieGastroGoo = "Gastro Goo Smoothie",
    SmoothieFuzzOnTheRocks = "Fuzz On The Rocks Smoothie",
    SmoothieAphid = "Aphid Smoothie",
    SmoothieBerry = "Berry Smoothie",
    SmoothieWaterBreathing = "Water Breathing Smoothie",
    SmoothieSwimSpeed = "Swim Speed Smoothie",
    SmoothieAttack = "Attack Smoothie",
    SmoothieAnt = "Ant Smoothie",
    SmoothieHumanFood = "Human Food Smoothie",
    SmoothieWasp = "Wasp Smoothie",
    SmoothieBoss = "Boss Smoothie",
    BombHeal = "Healing Bomb",
    MealTier1Spaghetflea = "Spaghetflea",
    MealTier2SpiderSlider = "Spider Slider",
    MealTier1Larvagna = "Larvagna",
    MealTier1Miteloaf = "Miteloaf",
    MealTier2MacNBees = "Mac N Bees",
    MealTier1Gnatchos = "Gnatchos",
    MealTier2Funguspacho = "Funguspacho",
    MealTier2Omelant = "Omelant",
    MealTier3Quesadillantlion = "Quesadillantlion",
    MealTier3BlackOxBurger = "Black Ox Burger",
    MealTier3TermiteDelight = "Termite Delight",
    MealTier3TadpolePudding = "Tadpole Pudding",
    MealTier3Wasperole = "Wasperole",
    MealTier3Empanadust = "Empanadust",
    Torch = "Torch",
    ["Torch+"] = "Upgraded Torch",
    Flare = "Flare",
    SmokeScreen = "Smoke Screen",
    Binoculars = "Binoculars",
    LeafBlower = "Leaf Blower",
    RepairHammer = "Repair Hammer",
    RepairArmor1 = "Armor Repair Kit",
    RepairArmor2 = "Advanced Armor Repair Kit",
    DecoyBait = "Decoy Bait",
    DivingLantern = "Diving Lantern",
    ["DivingLantern+"] = "Upgraded Diving Lantern",
    LanternFirefly = "Firefly Lantern",
    KoiFishScaleHelmet = "Koi Head Armor",
    KoiFishScaleChestPlate = "Koi Chest Armor",
    KoiFishScaleLegPlates = "Koi Leg Armor",
    HeadAntFire = "Fire Ant Head Armor",
    ChestAntFire = "Fire Ant Chest Armor",
    LegsAntFire = "Fire Ant Leg Armor",
    HeadMoth = "Moth Head Armor",
    ChestMoth = "Moth Chest Armor",
    LegsMoth = "Moth Leg Armor",
    HeadWasp = "Wasp Head Armor",
    ChestWasp = "Wasp Chest Armor",
    LegsWasp = "Wasp Leg Armor",
    HeadEyepatch = "Eyepatch",
    HeadMite = "Mite Hat",
    HeadFirefly = "Firefly Head Lamp",
    HeadLuckyHat = "Lucky Hat",
    HeadCrowArcher = "Marksman's Cap",
    HeadCrowWizard = "Wizard Hat",
    ChestTermite = "Termite Armor",
    LegsAphid = "Aphid Slippers",
    Flippers = "Fin Flops",
}

-- Used when config.quest_manager_asset_path is nil (without it, no pickup,
-- craft or gold card check is detected).
local DEFAULT_QUEST_MANAGER_ASSET_PATH =
    "/Game/Blueprints/Quests/BP_QuestManagerComponent.BP_QuestManagerComponent_C"

local function register_item_pickup_hook(ipc, config)
    local asset_path = config.quest_manager_asset_path or DEFAULT_QUEST_MANAGER_ASSET_PATH
    local path = asset_path .. ":HandleOnItemAdded"
    register_hook_with_retry("item pickup (HandleOnItemAdded)", path, function(
        _Context, _InventoryComponentOwner, ItemHandle, _IsNewItem, _Count, _TotalCount, ItemName
    )
        -- Items received from the multiworld (GiveItem) land here too and
        -- count as found, same as picking them up off the ground.
        local row_ok, row_name = pcall(get_row_name, unwrap_param(ItemHandle))
        if row_ok and row_name then
            -- Non-gear recipes this item used to unlock on pickup, if
            -- research_control had to clear its list (see there).
            pcall(research_control.on_item_picked_up, tostring(row_name))
        end
        if row_ok and row_name and tostring(row_name):find("Gold", 1, true) then
            ipc:report_location(GOLD_CARD_LOCATION_PREFIX .. tostring(row_name))
        end
        if row_ok and row_name and CRAFTSANITY_ROW_TO_DISPLAY_NAME[tostring(row_name)] then
            ipc:report_location(CRAFT_LOCATION_PREFIX .. CRAFTSANITY_ROW_TO_DISPLAY_NAME[tostring(row_name)])
        end

        local name = get_item_name(ItemName)
        if not name then
            print(string.format(
                "[GroundedArchipelago] HandleOnItemAdded fired but ItemName couldn't be read " ..
                "(row name was '%s') -- per a real bug report that some items (e.g. Grass Plank, " ..
                "Weed Stem) never count towards Itemsanity even though they're tracked: this is the " ..
                "exact failure that would cause that, since Itemsanity only reports below, after this " ..
                "point, and this bails out before ever reaching it. Printing the row name here (which " ..
                "doesn't depend on ItemName at all) so a future log can show exactly which real items " ..
                "hit this failure.\n",
                row_ok and tostring(row_name) or "?"
            ))
            return
        end
        print(string.format(
            "[GroundedArchipelago] Item pickup seen: '%s' (row %s)\n", name, row_ok and tostring(row_name) or "?"
        ))

        local location = item_pickup_to_location[name]
        if location then
            ipc:report_location(location)
        end

        ipc:report_location(ITEM_LOCATION_PREFIX .. name)
    end, config.hook_retry_interval_ms)
end

-- ---------------------------------------------------------------------
-- Drink-in-place items (Dew Drop, Juice Drop, Soda Drop)
--
-- Drinking never puts them in the inventory, so HandleOnItemAdded misses
-- them. Three hooks feed report_consumed_row (report_location dedupes):
--   1. ASurvivalCharacter:MulticastPlayConsumedEffect -- player only.
--   2. ASurvivalGameState:MulticastPlayItemConsumeAudioAtLocation.
--   3. ASpawnedItemDroplet:AdjustServings -- the droplet's own row.
-- ---------------------------------------------------------------------

-- Keys are Table_AllItems row names; values must exactly match
-- itemsanity.py's ITEMSANITY_ITEM_NAMES entries.
local CONSUMED_ROW_TO_ITEM_NAME = {
    DewDrop = "Dew Drop",
    JuiceDrop = "Juice Drop",
    SodaDrop = "Soda Drop",
}

-- Fallback for hook 3 if PlacedItemData can't be read: droplet class
-- name fragment -> row name. Checked in order (subclasses first).
local DROPLET_CLASS_TO_ROW = {
    {"BP_World_Droplet_LemonJuice", "JuiceDrop"},
    {"BP_World_Droplet_Soda", "SodaDrop"},
    {"BP_World_Droplet_Water", "DewDrop"},
}

local logged_consumed_rows = {}

local function report_consumed_row(ipc, row_name, source)
    if not row_name then
        return
    end
    row_name = tostring(row_name)
    if not logged_consumed_rows[row_name] then
        logged_consumed_rows[row_name] = true
        print(string.format("[GroundedArchipelago] Item consumed in place: '%s' (via %s)\n", row_name, source))
    end
    local item_name = CONSUMED_ROW_TO_ITEM_NAME[row_name]
    if item_name then
        ipc:report_location(ITEM_LOCATION_PREFIX .. item_name)
    end
end

local function read_param_row_name(handle_param)
    local ok, row_name = pcall(get_row_name, unwrap_param(handle_param))
    if ok and row_name and row_name ~= "None" then
        return row_name
    end
    return nil
end

local function register_consume_hooks(ipc, config)
    register_hook_with_retry(
        "item consumed (ASurvivalCharacter:MulticastPlayConsumedEffect)",
        "/Script/Maine.SurvivalCharacter:MulticastPlayConsumedEffect",
        function(Context, ItemType, _AtLocation)
            local character = unwrap_param(Context)
            local class_ok, class_name = pcall(function() return character:GetClass():GetFullName() end)
            if not class_ok or not tostring(class_name):find("PlayerCharacter", 1, true) then
                return -- a creature eating something, not the player
            end
            report_consumed_row(ipc, read_param_row_name(ItemType), "MulticastPlayConsumedEffect")
        end,
        config.hook_retry_interval_ms
    )

    register_hook_with_retry(
        "item consumed (ASurvivalGameState:MulticastPlayItemConsumeAudioAtLocation)",
        "/Script/Maine.SurvivalGameState:MulticastPlayItemConsumeAudioAtLocation",
        function(_Context, ItemRowHandle, _Location)
            report_consumed_row(ipc, read_param_row_name(ItemRowHandle), "MulticastPlayItemConsumeAudioAtLocation")
        end,
        config.hook_retry_interval_ms
    )

    register_hook_with_retry(
        "droplet serving taken (ASpawnedItemDroplet:AdjustServings)",
        "/Script/Maine.SpawnedItemDroplet:AdjustServings",
        function(Context, Delta)
            local delta_ok, delta = pcall(function() return Delta:get() end)
            if not delta_ok or type(delta) ~= "number" then
                delta = Delta
            end
            if type(delta) ~= "number" or delta >= 0 then
                return -- only servings being taken out count
            end
            local droplet = unwrap_param(Context)

            local row_name = nil
            local data_ok, placed_item_data = pcall(function() return droplet.PlacedItemData end)
            if data_ok and placed_item_data then
                row_name = read_param_row_name(placed_item_data)
            end
            if not row_name then
                local class_ok, class_name = pcall(function() return droplet:GetClass():GetFullName() end)
                if class_ok and class_name then
                    for _, entry in ipairs(DROPLET_CLASS_TO_ROW) do
                        if tostring(class_name):find(entry[1], 1, true) then
                            row_name = entry[2]
                            break
                        end
                    end
                end
            end
            report_consumed_row(ipc, row_name, "AdjustServings")
        end,
        config.hook_retry_interval_ms
    )
end

-- ---------------------------------------------------------------------
-- Carried (hauled) items: Grass Plank ("GrassPlank"), Weed Stem ("Log")
--
-- Hauling goes through UHaulingComponent, not the inventory. Three paths
-- (report_location dedupes): ClientOnItemAdded, AddItem (both player only
-- -- ants haul too), and polling the player's HauledItems each tick.
-- ---------------------------------------------------------------------

-- Table_AllItems row -> itemsanity.py name. Unknown hauled rows are
-- logged once so this can grow.
local HAULED_ROW_TO_ITEM_NAME = {
    GrassPlank = "Grass Plank",
    Log = "Weed Stem",
}

local logged_hauled_rows = {}

local function report_hauled_row(ipc, row_name, source)
    if not row_name or row_name == "None" then
        return
    end
    row_name = tostring(row_name)
    if not logged_hauled_rows[row_name] then
        logged_hauled_rows[row_name] = true
        print(string.format("[GroundedArchipelago] Item hauled: '%s' (via %s)\n", row_name, source))
    end
    local item_name = HAULED_ROW_TO_ITEM_NAME[row_name]
    if item_name then
        ipc:report_location(ITEM_LOCATION_PREFIX .. item_name)
    end
end

local function item_row_name(item)
    local ok, handle = pcall(function() return unwrap_param(item).ItemDataRowHandle end)
    if not ok or not handle then
        return nil
    end
    local name_ok, row_name = pcall(get_row_name, unwrap_param(handle))
    return name_ok and row_name or nil
end

local function hauler_is_player(hauling_component)
    local ok, class_name = pcall(function()
        return unwrap_param(hauling_component):GetOuter():GetClass():GetFullName()
    end)
    return ok and tostring(class_name):find("PlayerCharacter", 1, true) ~= nil
end

local function register_hauling_hooks(ipc, config)
    register_hook_with_retry(
        "item hauled (UHaulingComponent:ClientOnItemAdded)",
        "/Script/Maine.HaulingComponent:ClientOnItemAdded",
        function(Context, ItemRowHandle)
            if hauler_is_player(Context) then
                local ok, row_name = pcall(get_row_name, unwrap_param(ItemRowHandle))
                report_hauled_row(ipc, ok and row_name or nil, "ClientOnItemAdded")
            end
        end,
        config.hook_retry_interval_ms
    )

    register_hook_with_retry(
        "item hauled (UHaulingComponent:AddItem)",
        "/Script/Maine.HaulingComponent:AddItem",
        function(Context, Item, _IsNewItem)
            if hauler_is_player(Context) then
                report_hauled_row(ipc, item_row_name(Item), "AddItem")
            end
        end,
        config.hook_retry_interval_ms
    )

    ap_loop.start_loop(config.poll_interval_ms, function()
        -- The local controller's pawn, not FindAllOf("SurvivalPlayerCharacter"):
        -- a full object scan every second caused a visible hitch.
        local controller = item_grants.get_local_player_controller()
        if not controller then
            return
        end
        pcall(function()
            local player = controller.Pawn
            if not objects.is_valid(player) then
                return
            end
            local hauled = unwrap_param(player.HaulingComponent).HauledItems
            for i = 1, #hauled do
                report_hauled_row(ipc, item_row_name(hauled[i]), "HauledItems poll")
            end
        end)
    end)
end

-- ---------------------------------------------------------------------
-- Creature deaths, via ULootComponent:OnDeath (native, every lootable
-- creature). Context.bIsInfectedBroodmother identifies her directly;
-- otherwise the owner's class (GetOuter():GetClass():GetFullName()) is
-- matched against CREATURE_CLASS_TO_LOCATION.
-- ---------------------------------------------------------------------

-- Creature class fragment -> kill location (must match killsanity.py).
-- "Creature death seen: <class>" in the log gives the class to use.
local CREATURE_CLASS_TO_LOCATION = {
    -- From the BestiaryTable dump (BESTIARY_CREATURE lines: each bestiary
    -- entry's creature Blueprint class), all confirmed by a real kill:
    ["BP_Spider_Boss_Hedge_C"] = "Kill: Hedge Broodmother",  -- BestiarySpiderBossBroodmother
    ["BP_Mant_C"] = "Kill: Mant",                             -- BestiaryMant
    ["BP_Mantis_C"] = "Kill: Mantis",                         -- BestiaryMantis
    ["BP_Ominent_Robot_C"] = "Kill: Director Schmector",      -- BestiarySchmector
    ["BP_Wicklow_C"] = "Kill: Wasp Queen",                    -- BestiaryWaspQueen
    ["BP_Spider_BlackWidow_C"] = "Kill: Black Widow",
    -- Not its adds (BP_ArcR_BossAdd_C, BP_TazT_BossAdd_C).
    ["BP_ArcR_MKII_C"] = "Kill: Assistant Manager",          -- BestiaryArcRBoss
}

local warned_about_infected_bool = false

-- ---------------------------------------------------------------------
-- Gold card drop chance
--
-- Gold cards come from FBestiaryData.RareDropChance, not the creature's
-- LootComponent. Every bestiary row is patched once from the main loop (no
-- per-kill native calls -- those crashed on non-creatures), in the same
-- scale the vanilla values use (> 1.0 means percent). 0 restores vanilla.
-- ---------------------------------------------------------------------
local gold_card_vanilla = nil  -- row name -> vanilla RareDropChance
local gold_card_applied = nil  -- option value currently applied

function M.apply_gold_card_drop_chance(option_value)
    option_value = tonumber(option_value) or 0
    if option_value == gold_card_applied then
        return
    end
    local global_ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if not global_ok or not global_data then
        return
    end
    local table_ok, bestiary_table = pcall(function() return global_data.BestiaryTable end)
    if not table_ok or not bestiary_table then
        return
    end
    bestiary_table = unwrap_param(bestiary_table)
    local names_ok, row_names = pcall(function() return bestiary_table:GetRowNames() end)
    if not names_ok or not row_names then
        return
    end

    local rows = {}
    for i = 1, #row_names do
        local name = row_names[i]
        local row_ok, row = pcall(function() return bestiary_table:FindRow(name) end)
        if row_ok and row then
            rows[tostring(name)] = unwrap_param(row)
        end
    end

    if not gold_card_vanilla then
        gold_card_vanilla = {}
        local min_v, max_v, samples = math.huge, -math.huge, {}
        for name, row in pairs(rows) do
            local v_ok, v = pcall(function() return row.RareDropChance end)
            if v_ok and type(v) == "number" then
                gold_card_vanilla[name] = v
                min_v, max_v = math.min(min_v, v), math.max(max_v, v)
                if #samples < 8 then
                    table.insert(samples, string.format("%s=%s", name, tostring(v)))
                end
            end
        end
        print(string.format(
            "[GroundedArchipelago] Gold card: vanilla RareDropChance range %s..%s (e.g. %s)\n",
            tostring(min_v), tostring(max_v), table.concat(samples, ", ")
        ))
    end

    local percent_scale = false
    for _, v in pairs(gold_card_vanilla) do
        if v > 1.0 then
            percent_scale = true
            break
        end
    end
    local fraction = math.min(option_value / 50.0, 1.0)
    local written, failed = 0, 0
    for name, row in pairs(rows) do
        local target
        if option_value <= 0 then
            target = gold_card_vanilla[name]
        else
            target = percent_scale and (fraction * 100.0) or fraction
        end
        if target ~= nil then
            local write_ok = pcall(function() row.RareDropChance = target end)
            if write_ok then written = written + 1 else failed = failed + 1 end
        end
    end
    print(string.format(
        "[GroundedArchipelago] Gold card: option %d -> %s on %d bestiary rows (%s scale%s)\n",
        option_value,
        option_value <= 0 and "vanilla values" or string.format("%.0f%% chance", fraction * 100),
        written, percent_scale and "percent" or "0-1",
        failed > 0 and string.format(", %d writes FAILED", failed) or ""
    ))
    gold_card_applied = option_value
end

local function register_creature_death_hook(ipc, config)
    register_hook_with_retry(
        "creature death (ULootComponent:OnDeath)",
        "/Script/Maine.LootComponent:OnDeath",
        function(Context, _DamageInfo)
            Context = unwrap_param(Context)

            -- Before GetOuter(), which can fail.
            local is_infected, infected_err = read_bool_property(Context, "bIsInfectedBroodmother")
            if is_infected == nil and infected_err and not warned_about_infected_bool then
                warned_about_infected_bool = true
                print(string.format(
                    "[GroundedArchipelago] bIsInfectedBroodmother didn't read as a real boolean: %s -- " ..
                    "treating every death as NOT the Infected Broodmother until this is fixed, rather " ..
                    "than risk misreporting every kill as her the way an earlier build did.\n",
                    tostring(infected_err)
                ))
            end
            if is_infected == true then
                print("[GroundedArchipelago] Creature death seen: Infected Broodmother (bIsInfectedBroodmother)\n")
                ipc:report_location("Defeat the Infected Broodmother")
                return
            end

            local outer_ok, outer = pcall(function() return Context:GetOuter() end)
            if not outer_ok or not outer then
                print(string.format(
                    "[GroundedArchipelago] Creature death seen, but GetOuter() failed: %s\n",
                    tostring(outer)
                ))
                return
            end

            local class_ok, class_name = pcall(function() return outer:GetClass():GetFullName() end)
            if not class_ok or not class_name then
                print(string.format(
                    "[GroundedArchipelago] Creature death seen (GetOuter ok), but GetClass/GetFullName " ..
                    "failed: %s\n", tostring(class_name)
                ))
                return
            end

            -- Foliage and sticky-web harvest nodes share ULootComponent with
            -- creatures; native creature calls on them crash the game (not
            -- catchable by pcall), so they're skipped. BP_Spider_Web_C is the
            -- Orb Weaver itself -- don't block it.
            if tostring(class_name):find("FoliageActors", 1, true)
                or tostring(class_name):find("BP_Spiderweb_Sticky", 1, true) then
                return
            end


            print(string.format("[GroundedArchipelago] Creature death seen: %s\n", tostring(class_name)))

            -- CreatureDropShuffle: rewrite the corpse's loot rows before it
            -- spawns (pre-hook). Gold cards are a separate roll.
            local drops_ok, drops_err = pcall(drop_shuffle.apply, Context)
            if not drops_ok then
                print(string.format("[GroundedArchipelago] drop_shuffle.apply failed: %s\n", tostring(drops_err)))
            end

            -- Only the bosses in CREATURE_CLASS_TO_LOCATION count.
            for class_name_fragment, location in pairs(CREATURE_CLASS_TO_LOCATION) do
                if tostring(class_name):find(class_name_fragment, 1, true) then
                    ipc:report_location(location)
                    return
                end
            end
        end,
        config.hook_retry_interval_ms
    )
end





-- ---------------------------------------------------------------------
-- Embiggening goal: the real ending ("Go Big Or Never Go Home")
--
-- UAchievementsComponent:OnGameWon() (on ASurvivalPlayerState) fires when
-- the ending completes. ASurvivalGameState's OnGameWon is a delegate, not a
-- hookable UFunction.
-- ---------------------------------------------------------------------
local function register_game_won_hook(ipc, config)
    register_hook_with_retry(
        "game won (UAchievementsComponent:OnGameWon)",
        "/Script/Maine.AchievementsComponent:OnGameWon",
        function(_Context)
            print("[GroundedArchipelago] OnGameWon fired\n")
            ending_gate.on_game_won(ipc)
        end,
        config.hook_retry_interval_ms
    )
end

-- Polling triggers: check(state) gets a table that persists between polls
-- and returns true once the condition holds; reported once.
local poll_triggers = {
    -- Add one entry per remaining location in ../../apworld/grounded/locations.py
    -- that doesn't have a working hook yet.
}

-- ---------------------------------------------------------------------
-- Molars: UPlayerUpgradeComponent GetTotalSpentPoints() +
-- GetRemainingUpgradePoints() (only goes up). GameState's
-- GetTotalMilkMolarCount() is a world-wide constant -- don't use it.
-- ---------------------------------------------------------------------
local MOLAR_MILESTONES = {1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75}
local MOLAR_LOCATION_PREFIX = "Molars: "

-- Mega (gold) Milk Molars are a separate "party" currency on
-- ASurvivalGameState.PartyComponent: max(GetTotalPartyUpgradePoints(),
-- GetRemainingPartyUpgradePoints()).
local function read_party_molar_count()
    local gs_ok, game_state = pcall(objects.find_first, "SurvivalGameState")
    if not gs_ok or not game_state then
        return nil
    end
    local pc_ok, party_component = pcall(function() return game_state.PartyComponent end)
    if not pc_ok or not party_component then
        return nil
    end
    party_component = unwrap_param(party_component)
    local total_ok, total = pcall(function() return party_component:GetTotalPartyUpgradePoints() end)
    local remaining_ok, remaining = pcall(function() return party_component:GetRemainingPartyUpgradePoints() end)
    total = (total_ok and type(total) == "number") and total or nil
    remaining = (remaining_ok and type(remaining) == "number") and remaining or nil
    if total and remaining then
        return math.max(total, remaining)
    end
    return total or remaining
end

-- With ProgressiveMolarUpgrades, tiers come from AP items rather than
-- molars, so "spent + remaining" could count them as molars. Use the
-- party's own tally of personal molars collected instead (or, failing
-- that, only the unspent ones -- an undercount never sends a check early).
local function read_collected_personal_molars()
    local gs_ok, game_state = pcall(objects.find_first, "SurvivalGameState")
    if not gs_ok or not game_state then
        return nil
    end
    local ok, total = pcall(function()
        return unwrap_param(game_state.PartyComponent):GetTotalPersonalUpgradePoints()
    end)
    return (ok and type(total) == "number") and total or nil
end

local function read_personal_molar_count(ipc)
    if ipc and ipc.progressive_molar_upgrades then
        local collected = read_collected_personal_molars()
        if collected then
            return collected
        end
    end
    local player_state_ok, player_state = pcall(objects.find_first, "SurvivalPlayerState")
    if not player_state_ok or not player_state then
        return nil
    end
    local upgrade_component_ok, upgrade_component = pcall(function()
        return player_state.PlayerUpgradeComponent
    end)
    if not upgrade_component_ok or not upgrade_component then
        return nil
    end
    upgrade_component = unwrap_param(upgrade_component)
    local spent_ok, spent = pcall(function() return upgrade_component:GetTotalSpentPoints() end)
    local remaining_ok, remaining = pcall(function()
        return upgrade_component:GetRemainingUpgradePoints()
    end)
    if spent_ok and remaining_ok and type(spent) == "number" and type(remaining) == "number" then
        if ipc and ipc.progressive_molar_upgrades then
            return remaining
        end
        return spent + remaining
    end
    return nil
end

local function register_molar_polling(ipc, interval_ms)
    local last_logged_personal, last_logged_party = nil, nil

    ap_loop.start_loop(interval_ms, function()
        local personal = read_personal_molar_count(ipc)
        if not personal then
            return -- no player yet (main menu / loading)
        end
        local party = read_party_molar_count() or 0

        -- Logged only when a count changes, so a real log can confirm
        -- both counters track actual pickups.
        if personal ~= last_logged_personal or party ~= last_logged_party then
            last_logged_personal, last_logged_party = personal, party
            print(string.format(
                "[GroundedArchipelago] Molar count: %d regular + %d gold/mega = %d\n",
                personal, party, personal + party
            ))
        end

        -- Every reached milestone, every tick (report_location dedupes), so a
        -- reset state (_sync_room) re-sends them.
        local molar_count = personal + party
        for _, milestone in ipairs(MOLAR_MILESTONES) do
            if molar_count >= milestone then
                ipc:report_location(MOLAR_LOCATION_PREFIX .. tostring(milestone))
            end
        end
    end)
end

local function register_poll_triggers(ipc, interval_ms)
    local poll_state = {}
    ap_loop.start_loop(interval_ms, function()
        for _, trigger in ipairs(poll_triggers) do
            if not poll_state[trigger.location] then
                local ok, is_done = pcall(trigger.check, poll_state)
                if ok and is_done then
                    -- Only latch once the report actually went through
                    -- (it's ignored outside the Archipelago world).
                    poll_state[trigger.location] = ipc:report_location(trigger.location) or nil
                elseif not ok then
                    print(string.format(
                        "[GroundedArchipelago] Poll trigger for '%s' errored: %s\n",
                        trigger.location, tostring(is_done)
                    ))
                end
            end
        end
    end)
end

-- ---------------------------------------------------------------------
-- Goal completion, checked after every new location (ipc.on_location_reported).
-- Keep the "goal == N" numbers in sync with options.py's Goal.
-- ---------------------------------------------------------------------

-- Must match killsanity.py's KILLSANITY_BOSS_NAMES minus "Red Soldier
-- Ant" (test-only) -- there's no way to import that Python list from here.
local ALL_BOSS_LOCATIONS = {
    "Kill: Assistant Manager",
    "Kill: Hedge Broodmother",
    "Kill: Mant",
    "Kill: Mantis",
    "Kill: Director Schmector",
    "Kill: Wasp Queen",
    "Kill: Black Widow",
}

local STORY_BOSS_LOCATIONS = {
    "Kill: Assistant Manager",
    "Kill: Mant",
    "Kill: Director Schmector",
}

-- Keep in sync with goldcards.py's list length.
local GOLD_CARD_TOTAL_COUNT = 65
local ITEMSANITY_TOTAL_COUNT = 169

local function check_goal_completion(ipc)
    if ipc.goal_complete then
        return
    end
    local goal = ipc.goal or 0

    if goal == 0 then -- option_embiggening
        if ipc.checked_locations["Go Big Or Never Go Home (Ending)"] then
            ipc:report_goal_complete()
        end

    elseif goal == 1 then -- option_boss_only
        local excluded = {}
        for _, name in ipairs(ipc.excluded_bosses or {}) do
            excluded[name] = true
        end
        for _, location in ipairs(ALL_BOSS_LOCATIONS) do
            local boss_name = location:gsub("^Kill: ", "")
            if not excluded[boss_name] and not ipc.checked_locations[location] then
                return
            end
        end
        ipc:report_goal_complete()

    elseif goal == 2 then -- option_infected_broodmother
        if ipc.checked_locations["Defeat the Infected Broodmother"] then
            ipc:report_goal_complete()
        end

    elseif goal == 3 then -- option_infected_broodmother_and_embiggening
        if ipc.checked_locations["Defeat the Infected Broodmother"]
            and ipc.checked_locations["Go Big Or Never Go Home (Ending)"] then
            ipc:report_goal_complete()
        end

    elseif goal == 4 then -- option_gold_cards
        local count = 0
        for name in pairs(ipc.checked_locations) do
            if tostring(name):find("^Gold Card: ") then
                count = count + 1
            end
        end
        -- GoldCardGoalAmount (slot_data gold_card_goal_amount), a count.
        local required = math.min(ipc.gold_card_goal_amount or GOLD_CARD_TOTAL_COUNT, GOLD_CARD_TOTAL_COUNT)
        if count >= required then
            ipc:report_goal_complete()
        end

    elseif goal == 5 then -- option_itemsanity
        -- Decided by the client (_itemsanity_goal_met): "Item: " reports
        -- include non-itemsanity pickups.

    elseif goal == 6 then -- option_story_boss_only
        for _, location in ipairs(STORY_BOSS_LOCATIONS) do
            if not ipc.checked_locations[location] then
                return
            end
        end
        ipc:report_goal_complete()
    end
end

-- ---------------------------------------------------------------------
-- Save binding: the save's "World Name - Code" as the save browser shows
-- it (e.g. "NEW GAME - 30EC"). The active save's USaveGameHeaderData is
-- found by comparing PlaythroughGuid (struct ==, not :ToString()) against
-- SaveLoadManager.SaveGameHeaderDatas; the code is its SaveFolderName.
-- ---------------------------------------------------------------------
local warned_about_world_identity = {} -- keyed by step name, so each distinct failure point only warns once

local function warn_once(step, fmt, ...)
    if warned_about_world_identity[step] then
        return
    end
    warned_about_world_identity[step] = true
    print(string.format("[GroundedArchipelago] World identity (%s): " .. fmt .. "\n", step, ...))
end

function M.refresh_world_identity(ipc)
    local gs_ok, game_state = pcall(objects.find_first, "SurvivalGameState")
    if not gs_ok or not game_state then
        return -- no warning here -- entirely normal while still on the main menu
    end

    local guid_ok, current_guid = pcall(function() return game_state.PlaythroughGuid end)
    if not guid_ok or not current_guid then
        warn_once("current-guid", "couldn't read ASurvivalGameState.PlaythroughGuid: %s", tostring(current_guid))
        return
    end
    current_guid = unwrap_param(current_guid)

    local instance_ok, game_instance = pcall(objects.find_first, "SurvivalGameInstance")
    if not instance_ok or not game_instance then
        warn_once("game-instance", "couldn't find SurvivalGameInstance: %s", tostring(game_instance))
        return
    end

    local slm_ok, save_load_manager = pcall(function() return game_instance.SaveLoadManager end)
    if not slm_ok or not save_load_manager then
        warn_once("save-load-manager", "couldn't read SaveLoadManager off the game instance: %s", tostring(save_load_manager))
        return
    end
    save_load_manager = unwrap_param(save_load_manager)

    local headers_ok, headers = pcall(function() return save_load_manager.SaveGameHeaderDatas end)
    if not headers_ok or not headers then
        warn_once("headers-array", "couldn't read SaveGameHeaderDatas: %s", tostring(headers))
        return
    end
    headers = unwrap_param(headers)

    local count_ok, count = pcall(function() return #headers end)
    if not count_ok then
        warn_once("headers-length", "couldn't get a length for SaveGameHeaderDatas: %s", tostring(count))
        return
    end

    for i = 1, count do
        local entry_ok, entry = pcall(function() return headers[i] end)
        if entry_ok and entry then
            entry = unwrap_param(entry)
            local entry_guid_ok, entry_guid = pcall(function() return entry.PlaythroughGuid end)
            if entry_guid_ok and entry_guid then
                entry_guid = unwrap_param(entry_guid)
                local eq_ok, is_equal = pcall(function() return entry_guid == current_guid end)
                if eq_ok and is_equal then
                    local name_ok, save_name = pcall(function() return entry.SaveName end)
                    local folder_ok, folder_name = pcall(function() return entry.SaveFolderName end)
                    if name_ok and save_name then
                        local n_ok, n_str = pcall(function() return save_name:ToString() end)
                        ipc.world_name = (n_ok and type(n_str) == "string") and n_str or tostring(save_name)
                    end
                    if folder_ok and folder_name then
                        local f_ok, f_str = pcall(function() return folder_name:ToString() end)
                        ipc.world_code = (f_ok and type(f_str) == "string") and f_str or tostring(folder_name)
                    end
                    if not warned_about_world_identity["found"] then
                        warned_about_world_identity["found"] = true
                        print(string.format(
                            "[GroundedArchipelago] World identity found: name='%s' code='%s'\n",
                            tostring(ipc.world_name), tostring(ipc.world_code)
                        ))
                    end
                    return
                end
            end
        end
    end

    warn_once("no-match", "checked %d known save header(s), none matched the current save's GUID", count)
end

function M.register_all(ipc, config)
    ipc.on_location_reported = check_goal_completion
    register_item_pickup_hook(ipc, config)
    register_consume_hooks(ipc, config)
    register_hauling_hooks(ipc, config)
    register_story_discovery_hooks(config)
    register_creature_death_hook(ipc, config)
    register_game_won_hook(ipc, config)
    register_molar_polling(ipc, config.poll_interval_ms)
    register_poll_triggers(ipc, config.poll_interval_ms)
    deathlink.register(ipc, register_hook_with_retry, config)
    ending_gate.register(ipc, register_hook_with_retry, config)
end

-- Driven from main.lua's poll loop.
M.dump_static_data_once = dump_static_data_once

return M
