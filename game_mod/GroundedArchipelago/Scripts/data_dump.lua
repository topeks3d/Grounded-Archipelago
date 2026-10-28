-- data_dump.lua
--
-- One-time log dumps of game data the apworld is built from (like the
-- ITEM_ROW / RECIPE_ROW dumps in location_hooks.lua), plus a live line
-- whenever the player's zone changes:
--   ZONE_ROW:       GlobalTableData.ZonesTable (region locks)
--   TECH_TREE:      GlobalTableData.TechTreesTable, one line per tree
--   TECH_NODE:      every node of every tree's TechTreeRecipesTable (shop)
--   TECH_CHIP:      items whose TechTreeUnlocks open a tree (BURG.L chips)
--   ZONE: now in    the local player's zone (ZoneManagerComponent)

local M = {}

local objects = require("ap_objects")

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
    return tostring(value)
end

local function handle_rows(array)
    local rows = {}
    pcall(function()
        for i = 1, #array do
            local row = to_text(unwrap(array[i]).RowName)
            if row and row ~= "None" then
                rows[#rows + 1] = row
            end
        end
    end)
    return rows
end

local function for_each_row(data_table, fn)
    local ok, names = pcall(function() return data_table:GetRowNames() end)
    if not ok or not names then
        return false
    end
    for i = 1, #names do
        local name = to_text(names[i])
        local row_ok, row = pcall(function() return unwrap(data_table:FindRow(names[i])) end)
        if row_ok and row then
            pcall(fn, name, row)
        end
    end
    return true
end

local function get_table(field)
    local ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if not ok or not global_data then
        return nil
    end
    local table_ok, data_table = pcall(function() return global_data[field] end)
    return table_ok and data_table and unwrap(data_table) or nil
end

local zones_done, trees_done, chips_done = false, false, false

local function dump_zones()
    local zones = get_table("ZonesTable")
    if not zones then
        return false
    end
    log("=== ZONE TABLE DUMP ===")
    for_each_row(zones, function(name, row)
        log("ZONE_ROW: %s | priority=%s | interior=%s", name, tostring(row.Priority), tostring(row.bUseInteriorTrigger))
    end)
    log("=== END ZONE TABLE DUMP ===")
    return true
end

local function dump_tech_trees()
    local trees = get_table("TechTreesTable")
    if not trees then
        return false
    end
    log("=== TECH TREE DUMP ===")
    for_each_row(trees, function(tree_name, tree)
        local nodes = unwrap(tree.TechTreeRecipesTable)
        local path_ok, path = pcall(function() return nodes:GetFullName() end)
        log("TECH_TREE: %s | science_on_unlock=%s | table=%s", tree_name, tostring(tree.ScienceRewardOnUnlock),
            path_ok and tostring(path) or "?")
        for_each_row(nodes, function(node_name, node)
            log("TECH_NODE: %s | %s | type=%s | cost=%s | needs_unlocks=%s | ngplus=%s | timed=%s | unlocks=%s",
                tree_name, node_name, tostring(node.UnlockType), tostring(node.Cost),
                tostring(node.RequiredTechTreeUnlocks), tostring(node.RequiredNewGamePlusTier),
                tostring(node.bIsTimedExclusive), table.concat(handle_rows(node.UnlockData), ","))
        end)
    end)
    log("=== END TECH TREE DUMP ===")
    return true
end

local function dump_chips()
    local items = get_table("AllItemsTable")
    if not items then
        return false
    end
    for_each_row(items, function(item_name, row)
        local trees = handle_rows(row.TechTreeUnlocks)
        if #trees > 0 then
            log("TECH_CHIP: %s -> %s", item_name, table.concat(trees, ","))
        end
    end)
    return true
end

local last_zone = nil

local function log_zone_change()
    local ok, zone = pcall(function()
        local game_state = objects.find_first("SurvivalGameState")
        local manager = unwrap(game_state.ZoneManagerComponent)
        return to_text(unwrap(manager:GetLocalZoneRowHandle()).RowName)
    end)
    if ok and zone and zone ~= last_zone then
        last_zone = zone
        log("ZONE: now in %s", zone)
    end
end

-- Every poll tick from main.lua.
function M.tick(in_world)
    if not zones_done then
        zones_done = dump_zones()
    end
    if not trees_done then
        trees_done = dump_tech_trees()
    end
    if not chips_done then
        chips_done = dump_chips()
    end
    if in_world then
        log_zone_change()
    end
end

M.unwrap = unwrap
M.to_text = to_text

return M
