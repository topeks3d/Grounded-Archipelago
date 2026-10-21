-- recipe_shuffle.lua
--
-- Applies the RecipeShuffle option: rewrites the ingredients of Tier 2/3
-- gear recipes in GlobalTableData.CraftingRecipeTable, using the seeded
-- list the apworld generated (slot_data "recipe_shuffle", forwarded by the
-- client in to_game.json -- see apworld/grounded/recipe_shuffle.py).
--
-- Mapping format: recipe row -> { {item_row, count}, ... }. The vanilla
-- recipe keeps its number of ingredient slots; slot i gets entry i.
--
-- Struct layout (confirmed in the C++ header dump, Maine.hpp):
--   FBaseRecipeData.Requirements : TArray<FRecipeRequirements>
--   FRecipeRequirements { FDataTableRowHandle Item; int32 ItemCount; }
-- Every ingredient handle already points at the all-items table, so only
-- RowName/ItemCount change -- the DataTable pointer is left alone.
--
-- Like research_control.lua, edits live in memory for this game process
-- only and are reapplied every launch. The vanilla values are remembered
-- the first time a recipe is touched, so switching to a room with a
-- different (or no) shuffle restores/replaces them correctly without a
-- restart.

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

local function get_recipe_table()
    local ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if not ok or not global_data then
        return nil
    end
    local table_ok, recipe_table = pcall(function() return global_data.CraftingRecipeTable end)
    if not table_ok or not recipe_table then
        return nil
    end
    return unwrap(recipe_table)
end

-- recipe row -> { {row=, count=}, ... } as they were before we touched them
local originals = {}
local applied_signature = nil
local failed_warned = {}

-- Stable string for a mapping, so an unchanged mapping is a cheap no-op.
local function signature(mapping)
    local keys = {}
    for recipe in pairs(mapping) do
        keys[#keys + 1] = recipe
    end
    table.sort(keys)
    local parts = {}
    for _, recipe in ipairs(keys) do
        local entries = {}
        for _, entry in ipairs(mapping[recipe]) do
            entries[#entries + 1] = tostring(entry[1]) .. "*" .. tostring(entry[2])
        end
        parts[#parts + 1] = recipe .. "=" .. table.concat(entries, ",")
    end
    return table.concat(parts, ";")
end

local function read_requirements(requirements)
    local list = {}
    local len_ok, len = pcall(function() return #requirements end)
    if not len_ok or type(len) ~= "number" then
        return nil
    end
    for i = 1, len do
        local ok, entry = pcall(function()
            local req = unwrap(requirements[i])
            return { row = to_text(req.Item.RowName), count = req.ItemCount }
        end)
        if not ok then
            return nil
        end
        list[#list + 1] = entry
    end
    return list
end

local function write_requirement(requirements, i, row, count)
    local ok, err = pcall(function()
        local req = unwrap(requirements[i])
        req.Item.RowName = FName(row)
        req.ItemCount = count
    end)
    if not ok then
        return false, tostring(err)
    end
    -- Read back: a silent no-op write would otherwise look like success.
    local check_ok, now_row = pcall(function() return to_text(unwrap(requirements[i]).Item.RowName) end)
    if not check_ok or now_row ~= row then
        return false, "read back '" .. tostring(now_row) .. "'"
    end
    return true
end

-- Rewrites one recipe to `entries` ({ {row, count}, ... }), or back to
-- vanilla when entries is nil. Returns the number of ingredient slots, or
-- nil on failure.
local function apply_recipe(recipe_table, recipe_row, entries)
    local row_ok, recipe = pcall(function() return recipe_table:FindRow(recipe_row) end)
    if not row_ok or not recipe then
        return nil, "no such recipe row"
    end
    recipe = unwrap(recipe)
    local req_ok, requirements = pcall(function() return recipe.Requirements end)
    if not req_ok or not requirements then
        return nil, "couldn't read Requirements"
    end

    if not originals[recipe_row] then
        if not entries then
            return 0 -- never touched, nothing to restore
        end
        local vanilla = read_requirements(requirements)
        if not vanilla then
            return nil, "couldn't read vanilla requirements"
        end
        originals[recipe_row] = vanilla
    end

    local vanilla = originals[recipe_row]
    local described = {}
    for i, original in ipairs(vanilla) do
        local row, count = original.row, original.count
        if entries and entries[i] then
            row, count = entries[i][1], entries[i][2]
        end
        local ok, err = write_requirement(requirements, i, row, count)
        if not ok then
            return nil, string.format("slot %d -> %s: %s", i, row, err)
        end
        described[#described + 1] = string.format("%dx %s", count, row)
    end
    log("RECIPE_SHUFFLE: %s %s %s", recipe_row, entries and "->" or "restored to", table.concat(described, ", "))
    return #vanilla
end

-- Called every poll tick with the mapping from to_game.json (may be nil or
-- empty). `ipc` gets ipc.recipe_slots = {recipe_row -> slot count} so the
-- client's Tracker can show exactly what the game uses.
function M.tick(ipc, mapping)
    mapping = mapping or {}
    local sig = signature(mapping)
    if sig == applied_signature then
        return
    end
    if sig == "" and next(originals) == nil then
        applied_signature = sig -- shuffle off and nothing was ever changed
        return
    end

    local recipe_table = get_recipe_table()
    if not recipe_table then
        return -- GlobalTableData not loaded yet, retry next tick
    end

    local slots, changed, failed = {}, 0, 0
    -- Restore anything we changed that the new mapping doesn't cover.
    for recipe_row in pairs(originals) do
        if not mapping[recipe_row] then
            apply_recipe(recipe_table, recipe_row, nil)
        end
    end
    for recipe_row, entries in pairs(mapping) do
        local count, err = apply_recipe(recipe_table, recipe_row, entries)
        if count then
            slots[recipe_row] = count
            changed = changed + 1
        else
            failed = failed + 1
            if not failed_warned[recipe_row] then
                failed_warned[recipe_row] = true
                log("RECIPE_SHUFFLE: couldn't rewrite '%s': %s", recipe_row, tostring(err))
            end
        end
    end

    if changed == 0 and failed > 0 then
        return -- table probably not populated yet; retry the whole thing next tick
    end
    ipc.recipe_slots = slots
    ipc:_flush_from_game()
    -- Individual failures are logged once and not retried every tick:
    -- once other rows worked, they're data problems (a renamed row), not
    -- timing ones.
    applied_signature = sig
    log("RECIPE_SHUFFLE: rewrote %d recipe(s)%s", changed, failed > 0 and string.format(", %d failed", failed) or "")
end

return M
