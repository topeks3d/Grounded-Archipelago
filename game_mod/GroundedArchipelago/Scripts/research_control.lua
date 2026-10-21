-- research_control.lua
--
-- Research no longer unlocks recipes (gear only comes from AP items):
--   * FBaseItemData ResearchUnlockRecipes / NewResearchUnlockRecipes are
--     emptied; UnlockRecipes (first pickup) only loses AP-managed rows -- the
--     rest of such a list is unlocked by this mod on first pickup instead.
--   * Brainpower levels (UGlobalItemData.ResearchLevels) lose their
--     UnlockRecipes and BonusScienceAtLevel; SciencePerResearch is zeroed.
--     Brainpower (UPartyComponent.ResearchPoints) is set to the max level.
--   * BURG.L tech tree entries that would sell an AP-managed recipe are
--     emptied.
--   * The recipe categories in config.lua are unlocked up front.
--
-- Data-table edits are per game process (reapplied each launch). Recipes a
-- save already knows stay known -- use a fresh save for a new seed.
--
-- The stripping only happens in the Archipelago world. Every list and value
-- it changes is remembered first, and put back when any other world loads,
-- so other saves research the vanilla way.

local M = {}

local objects = require("ap_objects")

local item_grants = require("item_grants")

local function log(fmt, ...)
    print(string.format("[GroundedArchipelago] " .. fmt .. "\n", ...))
end

local function unwrap(value)
    local ok, unwrapped = pcall(function() return value:get() end)
    if ok and unwrapped ~= nil then
        return unwrapped
    end
    return value
end

local function to_text(value)
    if value == nil then
        return nil
    end
    if type(value) == "string" then
        return value
    end
    local ok, text = pcall(function() return value:ToString() end)
    if ok and type(text) == "string" then
        return text
    end
    local get_ok, inner = pcall(function() return value:get() end)
    if get_ok and inner ~= nil then
        if type(inner) == "string" then
            return inner
        end
        local inner_ok, inner_text = pcall(function() return inner:ToString() end)
        if inner_ok and type(inner_text) == "string" then
            return inner_text
        end
    end
    local plain_ok, plain = pcall(tostring, value)
    return plain_ok and plain or nil
end

local function handle_row_name(handle)
    local ok, name = pcall(function() return unwrap(handle).RowName end)
    if not ok then
        return nil
    end
    return to_text(name)
end

-- Reads a TArray<FDataTableRowHandle> into a plain list of row names.
local function read_handle_array(array)
    local names = {}
    local len_ok, len = pcall(function() return #array end)
    if not len_ok or type(len) ~= "number" then
        return names
    end
    for i = 1, len do
        local elem_ok, elem = pcall(function() return array[i] end)
        if elem_ok and elem then
            local name = handle_row_name(elem)
            if name and name ~= "None" then
                table.insert(names, name)
            end
        end
    end
    return names
end

local function empty_array(array)
    return pcall(function() array:Empty() end)
end

-- ---------------------------------------------------------------------
-- Vanilla values, for putting everything back outside the AP world
-- ---------------------------------------------------------------------
-- key -> {fetch = fn() -> TArray, entries = {{dt=, row=}, ...}} for emptied
-- handle arrays; key -> {fetch = fn() -> object, field =, value =} for
-- zeroed numbers. Arrays are re-found through `fetch` on restore rather
-- than kept as userdata across ticks. The first recording of a key wins
-- (that's the vanilla one).
local saved_arrays = {}
local saved_values = {}

local function read_handle_entries(array)
    local entries = {}
    local len_ok, len = pcall(function() return #array end)
    if not len_ok or type(len) ~= "number" then
        return nil
    end
    for i = 1, len do
        local ok, entry = pcall(function()
            local handle = unwrap(array[i])
            return {dt = handle.DataTable, row = to_text(handle.RowName)}
        end)
        if not ok or not entry.row then
            return nil
        end
        entries[#entries + 1] = entry
    end
    return entries
end

-- Empties `array` after remembering its contents under `key`.
local function strip_array(key, array, fetch)
    if not saved_arrays[key] then
        local entries = read_handle_entries(array)
        if not entries then
            return false
        end
        saved_arrays[key] = {fetch = fetch, entries = entries}
    end
    return empty_array(array)
end

local function zero_value(key, object, field, fetch)
    if not saved_values[key] then
        local ok, value = pcall(function() return object[field] end)
        if not ok or type(value) ~= "number" then
            return false
        end
        saved_values[key] = {fetch = fetch, field = field, value = value}
    end
    return pcall(function() object[field] = 0 end)
end

-- Refills an emptied array (UE4SS grows a TArray when writing one past
-- its end). Read back, since a silent no-op would look like success.
local function refill_array(array, entries)
    if not empty_array(array) then
        return false, "couldn't empty it first"
    end
    for i, entry in ipairs(entries) do
        local ok, err = pcall(function()
            array[i] = {DataTable = entry.dt, RowName = FName(entry.row)}
        end)
        if not ok then
            return false, string.format("adding %s: %s", entry.row, tostring(err))
        end
    end
    local len_ok, len = pcall(function() return #array end)
    if not len_ok or len ~= #entries then
        return false, string.format("%s of %d entries after refilling", tostring(len), #entries)
    end
    return true
end

local function get_global_table_data()
    local ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if ok and global_data then
        return global_data
    end
    return nil
end

local function get_table(global_data, field)
    local ok, data_table = pcall(function() return global_data[field] end)
    if not ok or not data_table then
        return nil
    end
    return unwrap(data_table)
end

local function for_each_row(data_table, fn)
    local names_ok, row_names = pcall(function() return data_table:GetRowNames() end)
    if not names_ok or not row_names then
        return false
    end
    for i = 1, #row_names do
        local row_name = row_names[i]
        local row_ok, row = pcall(function() return data_table:FindRow(row_name) end)
        if row_ok and row then
            local fn_ok, fn_err = pcall(fn, tostring(row_name), unwrap(row))
            if not fn_ok then
                log("research_control: error on row '%s': %s", tostring(row_name), tostring(fn_err))
            end
        end
    end
    return true
end

-- ---------------------------------------------------------------------
-- 1. Strip unlock sources (once per game process)
-- ---------------------------------------------------------------------
M.deferred_pickup_unlocks = {} -- item row name -> {recipe rows}, see on_item_picked_up
local stripped = false

local function strip_item_unlocks(global_data, managed)
    local items_table = get_table(global_data, "AllItemsTable")
    if not items_table then
        return false
    end
    local research_cleared, pickup_cleared = 0, 0
    local ok = for_each_row(items_table, function(row_name, row)
        local function fetch(field)
            return function()
                local data_table = get_table(get_global_table_data(), "AllItemsTable")
                return unwrap(data_table:FindRow(row_name))[field]
            end
        end
        for _, field in ipairs({"ResearchUnlockRecipes", "NewResearchUnlockRecipes"}) do
            local arr_ok, arr = pcall(function() return row[field] end)
            if arr_ok and arr and #read_handle_array(arr) > 0 then
                if strip_array("item|" .. row_name .. "|" .. field, arr, fetch(field)) then
                    research_cleared = research_cleared + 1
                end
            end
        end

        local arr_ok, pickup = pcall(function() return row.UnlockRecipes end)
        if arr_ok and pickup then
            local rows = read_handle_array(pickup)
            local has_managed, keep = false, {}
            for _, recipe in ipairs(rows) do
                if managed[recipe] then
                    has_managed = true
                else
                    table.insert(keep, recipe)
                end
            end
            if has_managed and strip_array("item|" .. row_name .. "|UnlockRecipes", pickup, fetch("UnlockRecipes")) then
                pickup_cleared = pickup_cleared + 1
                if #keep > 0 then
                    M.deferred_pickup_unlocks[row_name] = keep
                end
                log("research_control: removed AP-managed gear from '%s' pickup unlocks (kept for pickup: %s)",
                    row_name, #keep > 0 and table.concat(keep, ", ") or "nothing")
            end
        end
    end)
    log("research_control: cleared research unlocks on %d item fields, gear pickup unlocks on %d items",
        research_cleared, pickup_cleared)
    return ok
end

local function strip_brainpower_unlocks()
    local ok, assets = pcall(FindAllOf, "GlobalItemData")
    if not ok or not assets then
        return false
    end
    local stripped_any = false
    for _, asset in ipairs(assets) do
        local levels_ok, levels = pcall(function() return asset.ResearchLevels end)
        local name_ok, asset_name = pcall(function() return asset:GetFullName() end)
        if levels_ok and levels and name_ok then
            local len_ok, len = pcall(function() return #levels end)
            if len_ok and type(len) == "number" and len > 0 then
                local function find_asset()
                    for _, candidate in ipairs(FindAllOf("GlobalItemData") or {}) do
                        if candidate:GetFullName() == asset_name then
                            return candidate
                        end
                    end
                    error("GlobalItemData " .. asset_name .. " is gone")
                end
                for i = 1, len do
                    local function find_level()
                        return unwrap(find_asset().ResearchLevels[i])
                    end
                    pcall(function()
                        local level = unwrap(levels[i])
                        local key = "brainpower|" .. asset_name .. "|" .. i
                        strip_array(key .. "|UnlockRecipes", level.UnlockRecipes,
                            function() return find_level().UnlockRecipes end)
                        zero_value(key .. "|BonusScienceAtLevel", level, "BonusScienceAtLevel", find_level)
                    end)
                end
                zero_value("brainpower|" .. asset_name .. "|SciencePerResearch", asset, "SciencePerResearch", find_asset)
                stripped_any = true
                log("research_control: disabled recipe unlocks + bonus science on %d brainpower levels", len)
            end
        end
    end
    return stripped_any
end

local function strip_tech_tree_unlocks(global_data, managed)
    local trees = get_table(global_data, "TechTreesTable")
    if not trees then
        return
    end
    for_each_row(trees, function(tree_name, tree)
        local recipes_ok, recipes_table = pcall(function() return tree.TechTreeRecipesTable end)
        if not recipes_ok or not recipes_table then
            return
        end
        for_each_row(unwrap(recipes_table), function(node_name, node)
            local data_ok, unlock_data = pcall(function() return node.UnlockData end)
            if not data_ok or not unlock_data then
                return
            end
            for _, recipe in ipairs(read_handle_array(unlock_data)) do
                if managed[recipe] then
                    strip_array("tech|" .. tree_name .. "|" .. node_name, unlock_data, function()
                        local tree_row = unwrap(get_table(get_global_table_data(), "TechTreesTable"):FindRow(tree_name))
                        return unwrap(unwrap(tree_row.TechTreeRecipesTable):FindRow(node_name)).UnlockData
                    end)
                    log("research_control: BURG.L tech tree '%s' node '%s' sold AP-managed '%s' -- emptied",
                        tree_name, node_name, recipe)
                    return
                end
            end
        end)
    end)
end

-- Each step latches on its own (retrying a walk over every item row each
-- tick was a hitch).
local items_stripped, brainpower_stripped = false, false
local BRAINPOWER_RETRY_SECONDS = 5
local last_brainpower_attempt = nil

local function strip_unlock_sources_once()
    if stripped then
        return true
    end
    local global_data = get_global_table_data()
    if not global_data then
        return false
    end
    local managed = item_grants.get_managed_recipe_rows()
    if not items_stripped then
        if not strip_item_unlocks(global_data, managed) then
            return false
        end
        items_stripped = true
        strip_tech_tree_unlocks(global_data, managed)
    end
    if not brainpower_stripped then
        -- FindAllOf is a full object scan; don't repeat it every tick.
        local now = os.time()
        if last_brainpower_attempt and os.difftime(now, last_brainpower_attempt) < BRAINPOWER_RETRY_SECONDS then
            return false
        end
        last_brainpower_attempt = now
        if not strip_brainpower_unlocks() then
            return false -- GlobalItemData not loaded yet; retry later
        end
        brainpower_stripped = true
    end
    stripped = true
    return true
end

-- ---------------------------------------------------------------------
-- 2. Category unlocks (once per session, once a player exists)
-- ---------------------------------------------------------------------
local function normalize(text)
    return (tostring(text or ""):lower():gsub("[^%w]", ""))
end

local function matches_any(category, patterns)
    local norm = normalize(category)
    for _, pattern in ipairs(patterns or {}) do
        if norm:find(normalize(pattern), 1, true) then
            return true
        end
    end
    return false
end

-- Returns {category_tag -> {row names}} for one recipe table.
local function recipes_by_category(data_table)
    local by_category = {}
    for_each_row(data_table, function(row_name, row)
        local tag_ok, tag_name = pcall(function() return row.CategoryTag.TagName end)
        local category = (tag_ok and to_text(tag_name)) or "<unreadable>"
        by_category[category] = by_category[category] or {}
        table.insert(by_category[category], row_name)
    end)
    return by_category
end

local dumped_categories = false
local categories_unlocked = false

local function unlock_categories(config)
    if categories_unlocked then
        return true
    end
    local global_data = get_global_table_data()
    if not global_data then
        return false
    end
    local managed = item_grants.get_managed_recipe_rows()
    for row in pairs(item_grants.get_managed_building_rows()) do
        managed[row] = true
    end
    local to_unlock = {}   -- crafting rows (UnlockRecipe cheat)
    local to_build = {}    -- building rows (the cheat ignores these)
    local sources = {
        {"CraftingRecipeTable", config.unlock_crafting_categories, to_unlock},
        {"BuildingRecipeTable", config.unlock_building_categories, to_build},
    }
    for _, source in ipairs(sources) do
        local data_table = get_table(global_data, source[1])
        if not data_table then
            return false
        end
        local by_category = recipes_by_category(data_table)
        for category, rows in pairs(by_category) do
            local selected = matches_any(category, source[2])
            if not dumped_categories then
                -- One line per category so the patterns in config.lua can
                -- be checked/tuned against the real tag names.
                log("RECIPE_CATEGORY: %s | %s | %d rows | %s | e.g. %s",
                    source[1], category, #rows, selected and "UNLOCKED" or "locked",
                    -- Building categories are small: list every row.
                    table.concat(rows, ", ", 1, source[1] == "BuildingRecipeTable" and #rows or math.min(#rows, 6)))
            end
            if selected then
                for _, row in ipairs(rows) do
                    if not managed[row] then
                        table.insert(source[3], row)
                    end
                end
            end
        end
    end
    dumped_categories = true

    for _, row in ipairs(to_unlock) do
        local ok, err = item_grants.execute_console_command("UnlockRecipe " .. row)
        if not ok then
            log("research_control: UnlockRecipe %s failed (%s) -- will retry all category unlocks", row, tostring(err))
            return false
        end
    end
    for _, row in ipairs(to_build) do
        local ok, err = item_grants.unlock_building_recipe(row)
        if not ok then
            log("research_control: building recipe %s failed (%s) -- will retry all category unlocks", row, tostring(err))
            return false
        end
    end
    log("research_control: unlocked %d crafting + %d building recipes from the configured categories",
        #to_unlock, #to_build)
    categories_unlocked = true
    return true
end

-- ---------------------------------------------------------------------
-- 3. Max brainpower (once per session, once the save is loaded)
-- ---------------------------------------------------------------------
local brainpower_done = false

local function max_brainpower()
    if brainpower_done then
        return true
    end
    local gs_ok, game_state = pcall(objects.find_first, "SurvivalGameState")
    if not gs_ok or not game_state then
        return false
    end
    local pc_ok, party = pcall(function() return game_state.PartyComponent end)
    if not pc_ok or not party then
        return false
    end
    party = unwrap(party)
    local max_ok, max_level = pcall(function() return party:GetMaxResearchLevel() end)
    if not max_ok or type(max_level) ~= "number" then
        return false
    end
    local req_ok, required = pcall(function() return party:GetPointsRequiredForResearchLevel(max_level) end)
    local cur_ok, current = pcall(function() return party.ResearchPoints end)
    if not req_ok or type(required) ~= "number" or not cur_ok or type(current) ~= "number" then
        return false
    end
    if current < required then
        local write_ok, write_err = pcall(function() party.ResearchPoints = required end)
        if not write_ok then
            log("research_control: couldn't set brainpower: %s", tostring(write_err))
            return false
        end
        -- Refreshes level/UI state; level-up unlocks were stripped above.
        pcall(function() party:UpdateResearchPointData(current) end)
        log("research_control: brainpower set to max (level %d, %d -> %d points)", max_level, current, required)
    end
    brainpower_done = true
    return true
end

-- ---------------------------------------------------------------------
-- 4. Putting vanilla research back (any other world)
-- ---------------------------------------------------------------------
local restore_failed = false

-- Returns true once everything stripped is back. On failure the rest
-- stays stripped until the game restarts (logged and shown once).
local function restore_unlock_sources()
    if restore_failed or (not items_stripped and not brainpower_stripped) then
        return true
    end
    local restored, problems = 0, {}
    for key, saved in pairs(saved_arrays) do
        local fetch_ok, array = pcall(saved.fetch)
        local ok, err = false, array
        if fetch_ok and array then
            ok, err = refill_array(array, saved.entries)
        end
        if ok then
            restored = restored + 1
        else
            problems[#problems + 1] = key .. ": " .. tostring(err)
        end
    end
    for key, saved in pairs(saved_values) do
        local ok, err = pcall(function() saved.fetch()[saved.field] = saved.value end)
        if not ok then
            problems[#problems + 1] = key .. ": " .. tostring(err)
        end
    end
    stripped, items_stripped, brainpower_stripped = false, false, false
    last_brainpower_attempt = nil
    M.deferred_pickup_unlocks = {}
    if #problems > 0 then
        restore_failed = true
        log("research_control: couldn't put vanilla research back (%d problems, e.g. %s) -- restart Grounded " ..
            "before playing other worlds", #problems, problems[1])
        pcall(function()
            require("notifications").show_local(
                "Archipelago: restart Grounded to get normal research back in this world")
        end)
        return false
    end
    log("research_control: vanilla research restored (%d lists) for a non-Archipelago world", restored)
    return true
end

-- Every tick from main.lua; each step is a no-op once done.
--   active: true in a world named for Archipelago (strip research), false
--           in any other loaded world (put vanilla back), nil on the main
--           menu (leave as is until a world loads).
--   in_world: the Archipelago world is fully loaded (per-save steps).
function M.tick(config, in_world, active)
    if config.disable_research == false then
        return
    end
    if active == false then
        restore_unlock_sources()
        return
    end
    if active == nil then
        return
    end
    restore_failed = false -- back in the AP world: a later restore may try again
    if not strip_unlock_sources_once() then
        return -- nothing else is safe until unlock sources are stripped
    end
    if not in_world then
        return
    end
    if max_brainpower() then
        unlock_categories(config)
    end
end

-- Leaving a world: per-save steps run again for the next one.
function M.on_world_left()
    brainpower_done = false
    categories_unlocked = false
end

-- Called from the item-pickup hook with the picked-up item's ROW name:
-- unlocks any non-gear recipes that were removed from its pickup list.
function M.on_item_picked_up(item_row)
    local rows = M.deferred_pickup_unlocks[item_row]
    if not rows then
        return
    end
    for _, row in ipairs(rows) do
        if not item_grants.execute_console_command("UnlockRecipe " .. row) then
            return -- try again on the next pickup
        end
    end
    M.deferred_pickup_unlocks[item_row] = nil
end

return M
