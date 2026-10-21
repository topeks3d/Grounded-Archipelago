-- drop_shuffle.lua
--
-- CreatureDropShuffle: rewrites a dying creature's ULootComponent.Items
-- (FLootData.ItemData.RowName) through slot_data "creature_drop_shuffle"
-- (vanilla row -> new row; see apworld/grounded/drop_shuffle.py). Only the
-- RowName changes. Called from location_hooks.lua's OnDeath pre-hook,
-- before any loot spawns. "Bestiary*" (gold card) rows are never touched.

local M = {}

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

local mapping = {}
-- A permutation must not be applied twice to one component: keyed by its
-- full name (unique among live objects).
local done = {}

-- Called every poll tick with the mapping from to_game.json (may be nil).
function M.set_mapping(new_mapping)
    mapping = new_mapping or {}
end

function M.apply(loot_component)
    if next(mapping) == nil then
        return
    end
    local name_ok, full_name = pcall(function() return loot_component:GetFullName() end)
    local key = name_ok and full_name or nil
    if key and done[key] then
        return
    end

    local items_ok, items = pcall(function() return loot_component.Items end)
    if not items_ok or not items then
        return
    end
    local len_ok, len = pcall(function() return #items end)
    if not len_ok or type(len) ~= "number" then
        return
    end

    local changed = {}
    for i = 1, len do
        pcall(function()
            local entry = unwrap(items[i])
            local row = to_text(entry.ItemData.RowName)
            local new_row = row and mapping[row]
            if new_row and not row:find("^Bestiary") and not new_row:find("^Bestiary") then
                entry.ItemData.RowName = FName(new_row)
                local now_row = to_text(unwrap(items[i]).ItemData.RowName)
                if now_row == new_row then
                    changed[#changed + 1] = row .. "->" .. new_row
                else
                    log("DROP_SHUFFLE: write %s->%s didn't stick (read back '%s')", row, new_row, tostring(now_row))
                end
            end
        end)
    end
    if key then
        done[key] = true
    end
    if #changed > 0 then
        log("DROP_SHUFFLE: %s", table.concat(changed, ", "))
    end
end

return M
