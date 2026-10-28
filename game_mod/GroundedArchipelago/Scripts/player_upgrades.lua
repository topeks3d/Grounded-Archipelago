-- player_upgrades.lua
--
-- ProgressiveMolarUpgrades (apworld player_upgrades.py). Follows how many
-- copies of each item the room has sent (to_game.json's full received
-- list), so a restart or a fresh save simply catches up:
--
--   * Molar upgrades: a PlayerUpgradesTable row (Health, Stamina, Thirst,
--     Healing, Perks) is raised one tier at a time until the player's tier
--     (PlayerUpgradeComponent.PlayerUpgrades) matches the copies received
--     -- UPlayerUpgradeComponent:ServerUnlockUpgradeTier with bIgnoreCost,
--     falling back to the "UnlockPlayerUpgrade <row>" cheat. Each row's
--     BaseCost is raised out of reach so molars can't buy tiers on top; the
--     vanilla costs come back in any other world.

local M = {}

local objects = require("ap_objects")
local item_grants = require("item_grants")
local ap_data = require("ap_data")

local MOLAR_UPGRADES = ap_data.MOLAR_UPGRADES or {}
local BLOCKED_COST = 9999
-- Vanilla BaseCosts, for when the table is already blocked (the mod was
-- reloaded mid-session): Perks starts at 3 molars, the rest at 1.
local DEFAULT_COSTS = {Perks = 3}
-- A tier that hasn't gone up this long after asking is logged, then asked
-- for again at this interval.
local STUCK_SECONDS = 10

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

-- ---------------------------------------------------------------------
-- Molar upgrade costs (PlayerUpgradesTable, process-wide)
-- ---------------------------------------------------------------------
local vanilla_costs = nil -- row -> BaseCost, while blocked

local function get_upgrades_table()
    local ok, global_data = pcall(objects.find_first, "GlobalTableData")
    if not ok or not global_data then
        return nil
    end
    local table_ok, upgrades = pcall(function() return global_data.PlayerUpgradesTable end)
    if not table_ok or not upgrades then
        return nil
    end
    return unwrap(upgrades)
end

local function set_costs(blocked)
    if blocked == (vanilla_costs ~= nil) then
        return
    end
    local upgrades = get_upgrades_table()
    if not upgrades then
        return
    end
    if blocked then
        local saved = {}
        for _, row in pairs(MOLAR_UPGRADES) do
            local ok, err = pcall(function()
                local data = unwrap(upgrades:FindRow(row))
                local cost = data.BaseCost
                saved[row] = cost < BLOCKED_COST and cost or (DEFAULT_COSTS[row] or 1)
                data.BaseCost = BLOCKED_COST
            end)
            if not ok then
                log("PLAYER_UPGRADES: couldn't block molar cost of '%s': %s", row, tostring(err))
            end
        end
        vanilla_costs = saved
        log("PLAYER_UPGRADES: molar upgrades can no longer be bought (they come from Archipelago items)")
    else
        for row, cost in pairs(vanilla_costs) do
            pcall(function() unwrap(upgrades:FindRow(row)).BaseCost = cost end)
        end
        vanilla_costs = nil
        log("PLAYER_UPGRADES: vanilla molar upgrade costs restored")
    end
end

-- ---------------------------------------------------------------------
-- Molar upgrade tiers
-- ---------------------------------------------------------------------
local function get_upgrade_component()
    local controller = item_grants.get_local_player_controller()
    if not controller then
        return nil
    end
    local ok, component = pcall(function() return unwrap(controller.PlayerState).PlayerUpgradeComponent end)
    if not ok or not component then
        return nil
    end
    return unwrap(component)
end

-- row -> tier, or nil if the component can't be read.
local function read_tiers(component)
    local ok, tiers = pcall(function()
        local list = component.PlayerUpgrades
        local found = {}
        for i = 1, #list do
            local entry = unwrap(list[i])
            local name = to_text(entry.UpgradeName.Name)
            if name then
                found[name] = entry.Tier
            end
        end
        return found
    end)
    return ok and tiers or nil
end

-- Raises `row` one tier above `before`.
local function unlock_tier(component, row, before)
    local upgrades = get_upgrades_table()
    if not upgrades then
        return
    end
    local ok = pcall(function()
        component:ServerUnlockUpgradeTier({DataTable = upgrades, RowName = FName(row)}, true)
    end)
    local tiers = ok and read_tiers(component)
    if tiers and (tiers[row] or 0) > before then
        return
    end
    -- The cheat may check the cost: let it see the vanilla one for this call.
    local blocked = vanilla_costs ~= nil and vanilla_costs[row] ~= nil
    if blocked then
        pcall(function() unwrap(upgrades:FindRow(row)).BaseCost = vanilla_costs[row] end)
    end
    item_grants.execute_console_command("UnlockPlayerUpgrade " .. row)
    if blocked then
        pcall(function() unwrap(upgrades:FindRow(row)).BaseCost = BLOCKED_COST end)
    end
end

local asked = {} -- row -> {tier = tier when asked, time = os.time()}

local function sync_tiers(counts)
    local component = get_upgrade_component()
    if not component then
        return
    end
    local tiers = read_tiers(component)
    if not tiers then
        return
    end
    for item_name, row in pairs(MOLAR_UPGRADES) do
        local target = counts[item_name] or 0
        local tier = tiers[row] or 0
        local last = asked[row]
        if tier >= target then
            asked[row] = nil
        elseif not last or last.tier ~= tier or os.difftime(os.time(), last.time) >= STUCK_SECONDS then
            if last and last.tier == tier then
                log("PLAYER_UPGRADES: %s is still tier %d after asking for %d -- asking again", row, tier, target)
            end
            -- One tier per row per tick.
            unlock_tier(component, row, tier)
            local now_tier = (read_tiers(component) or {})[row] or 0
            log("PLAYER_UPGRADES: %s tier %d -> %d (target %d)", row, tier, now_tier, target)
            -- Not up yet: wait for it (or STUCK_SECONDS) instead of asking twice.
            asked[row] = now_tier <= tier and {tier = tier, time = os.time()} or nil
        end
    end
end

-- ---------------------------------------------------------------------
-- Every poll tick from main.lua.
--   ap_active: true in the Archipelago world (even while loading), false
--              in another world, nil on the main menu.
--   in_world:  the Archipelago world is fully loaded.
-- ---------------------------------------------------------------------
function M.tick(status, ipc_dir, in_world, ap_active)
    if ap_active ~= nil then
        set_costs(ap_active and status.progressive_molar_upgrades == true)
    end
    if not in_world then
        return
    end
    local counts = status.item_counts or {}
    if status.progressive_molar_upgrades then
        sync_tiers(counts)
    end
end

-- Names of the AP items this module applies (item_grants.lua treats them as
-- applied on arrival).
function M.item_names()
    local names = {}
    for name in pairs(MOLAR_UPGRADES) do
        names[#names + 1] = name
    end
    return names
end

return M
