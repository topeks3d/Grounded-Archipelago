-- gear_perks.lua
--
-- GearPerks (slot_data "gear_perks": 0 off, 1 weapons, 2 weapons and
-- armor): gear in the player's inventory and equipment slots gets random
-- perks the way New Game+ infused gear does.
--
-- The game already has everything for this:
--   * FBaseItemData.EquippableData.RandomEffectType (Tier1/2/3/Other, or
--     None for gear that can't have perks),
--   * UGlobalItemData.GeneratedItemEffects: type -> {EffectCount,
--     PossibleEffects} -- the NG+ perk pools,
--   * UItem.RandomEffects: the perks one item has (saved with it).
-- Gear whose RandomEffectType is None uses the pool of its tier. Items that
-- already have perks (real NG+ gear, or done before) are left alone. Every
-- pick is seeded by the room and the item row, so every Insect Axe in a seed
-- rolls the same perks (like RecipeShuffle, part of the seed). Gear that's
-- already equipped when it gets its perks may need re-equipping first.

local M = {}

local item_grants = require("item_grants")

local SCAN_SECONDS = 2
local EQUIPMENT_SLOTS = {"MainHand", "OffHand", "Head", "Chest", "Arms", "Legs"}

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
    return nil
end

local function is_valid(obj)
    local ok, valid = pcall(function() return obj:IsValid() end)
    return ok and valid == true
end

-- ---------------------------------------------------------------------
-- Deterministic picks
-- ---------------------------------------------------------------------
local function hash(text)
    local h = 5381
    for i = 1, #text do
        h = (h * 33 + text:byte(i)) % 2147483647
    end
    return h
end

-- Park-Miller, as test_mode.lua: returns rand(n) -> 1..n.
local function make_rng(seed)
    local state = seed % 2147483647
    if state <= 0 then
        state = state + 2147483646
    end
    return function(n)
        state = (state * 16807) % 2147483647
        return (state % n) + 1
    end
end

-- `count` distinct entries of `pool`, the same every time for one seed key.
function M.pick(pool, count, seed_key)
    local rand = make_rng(hash(seed_key))
    local copy = {}
    for i, v in ipairs(pool) do
        copy[i] = v
    end
    local picked = {}
    for _ = 1, math.min(count, #copy) do
        local i = rand(#copy)
        picked[#picked + 1] = table.remove(copy, i)
    end
    return picked
end

-- ---------------------------------------------------------------------
-- Game data
-- ---------------------------------------------------------------------
-- RandomEffectType -> {count =, effects = {{dt =, row =}, ...}}
local pools = nil

local function load_pools()
    if pools then
        return pools
    end
    local ok, assets = pcall(FindAllOf, "GlobalItemData")
    if not ok or not assets then
        return nil
    end
    for _, asset in ipairs(assets) do
        local found = {}
        local any = false
        pcall(function()
            asset.GeneratedItemEffects:ForEach(function(key, value)
                local effect_type = unwrap(key)
                local data = unwrap(value)
                local entry = {count = data.EffectCount, effects = {}}
                local list = data.PossibleEffects
                for i = 1, #list do
                    local handle = unwrap(list[i])
                    local row = to_text(handle.RowName)
                    if row and row ~= "None" then
                        entry.effects[#entry.effects + 1] = {dt = handle.DataTable, row = row}
                    end
                end
                found[effect_type] = entry
                any = true
            end)
        end)
        if any then
            pools = found
            for effect_type, entry in pairs(found) do
                log("GEAR_PERKS: perk pool %s: %d effects, %d per item", tostring(effect_type), #entry.effects,
                    entry.count or 0)
            end
            return pools
        end
    end
    return nil
end

local function get_items_table()
    local ok, global_data = pcall(require("ap_objects").find_first, "GlobalTableData")
    if not ok or not global_data then
        return nil
    end
    local table_ok, items = pcall(function() return global_data.AllItemsTable end)
    return table_ok and items and unwrap(items) or nil
end

-- ---------------------------------------------------------------------
-- Items
-- ---------------------------------------------------------------------
local no_perks = {}  -- item row -> true for gear that never gets perks here

local function player_items()
    local controller = item_grants.get_local_player_controller()
    if not controller then
        return {}
    end
    local items = {}
    pcall(function()
        local pawn = unwrap(controller.Pawn)
        local list = unwrap(pawn.InventoryComponent).Items
        for i = 1, #list do
            items[#items + 1] = unwrap(list[i])
        end
        local equipment = unwrap(pawn.EquipmentComponent)
        for _, slot in ipairs(EQUIPMENT_SLOTS) do
            local item = equipment[slot]
            if item then
                items[#items + 1] = unwrap(item)
            end
        end
    end)
    return items
end

-- Weapons (main/off hand) or, in mode 2, armor too; nil = not gear.
local WEAPON_SLOTS = {[1] = true, [2] = true}
local ARMOR_SLOTS = {[3] = true, [4] = true, [5] = true, [6] = true}

-- The perk pool for an item row: its own RandomEffectType, or -- for gear
-- the game never rolls perks for (None) -- the pool of its tier.
local function pool_for(item_row, item)
    local effect_type = tonumber(item_row.EquippableData.RandomEffectType) or 0
    if effect_type ~= 0 and pools[effect_type] and #pools[effect_type].effects > 0 then
        return pools[effect_type], "type " .. effect_type
    end
    local tier_ok, tier = pcall(function() return item:GetTier() end)
    tier = tier_ok and tonumber(tier) or tonumber(item_row.Tier) or 1
    tier = math.max(1, math.min(3, tier))
    if pools[tier] and #pools[tier].effects > 0 then
        return pools[tier], "tier " .. tier
    end
    return nil, "no pool"
end

local logged = {} -- item row -> true once its outcome is logged

local function log_once(row, fmt, ...)
    if not logged[row] then
        logged[row] = true
        log(fmt, ...)
    end
end

-- Gives one item its perks, if it should have some and doesn't yet.
local function handle_item(item, mode, room_key, items_table)
    local row = to_text(unwrap(item.ItemDataRowHandle).RowName)
    if not row or row == "None" or no_perks[row] then
        return
    end
    local slot_ok, slot = pcall(function() return tonumber(item:GetEquipmentSlot()) end)
    if not slot_ok or not slot then
        return
    end
    local is_weapon = WEAPON_SLOTS[slot] == true
    if not is_weapon and not (mode == 2 and ARMOR_SLOTS[slot]) then
        no_perks[row] = true -- not gear (or armor in weapons-only mode)
        return
    end
    local seed_key = room_key .. "|" .. row


    local count_ok, existing = pcall(function() return #item.RandomEffects end)
    if not count_ok or existing > 0 then
        return
    end
    local row_ok, item_row = pcall(function() return unwrap(items_table:FindRow(row)) end)
    if not row_ok or not item_row then
        log_once(row, "GEAR_PERKS: %s: item row not readable", row)
        return
    end
    local pool_ok, pool, source = pcall(pool_for, item_row, item)
    if not pool_ok or not pool then
        no_perks[row] = true
        log_once(row, "GEAR_PERKS: %s gets no perks (%s)", row, tostring(pool_ok and source or pool))
        return
    end
    local picked = M.pick(pool.effects, math.max(1, pool.count or 1), seed_key)
    local names = {}
    local ok, err = pcall(function()
        local effects = item.RandomEffects
        for i, effect in ipairs(picked) do
            effects[i] = {DataTable = effect.dt, RowName = FName(effect.row)}
            names[#names + 1] = effect.row
        end
    end)
    local stuck_ok, stuck = pcall(function() return #item.RandomEffects end)
    if not ok or not stuck_ok or stuck == 0 then
        no_perks[row] = true -- don't retry a write that fails every time
        log("GEAR_PERKS: couldn't give %s its perks: %s", row, ok and "the list stayed empty" or tostring(err))
        return
    end
    log("GEAR_PERKS: %s (%s) -> %s", row, source, table.concat(names, ", "))
end

local last_scan = 0

-- Every poll tick from main.lua while in the Archipelago world.
function M.tick(mode, room_key, in_world)
    mode = tonumber(mode) or 0
    if mode == 0 or not in_world or not room_key then
        return
    end
    local now = os.time()
    if os.difftime(now, last_scan) < SCAN_SECONDS then
        return
    end
    last_scan = now
    if not load_pools() then
        return
    end
    local items_table = get_items_table()
    if not items_table then
        return
    end
    for _, item in ipairs(player_items()) do
        if is_valid(item) then
            handle_item(item, mode, room_key, items_table)
        end
    end
end

return M
