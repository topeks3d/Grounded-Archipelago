-- mutations.lua
--
-- MutationChecks: counts UPerkComponent.Perks entries (local player state)
-- with Tier >= 0 -- every mutation has an entry, locked ones at Tier -1.
-- Milestones come from the generated ap_data.lua.

local M = {}

local ap_data = require("ap_data")
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

local last_logged_mutations = nil
local logged_tiers = false

-- Locked mutations are listed too (Tier -1) -- only count Tier >= 0.
local function read_mutation_count()
    local controller = item_grants.get_local_player_controller()
    if not controller then
        return nil
    end
    local ok, count, tiers = pcall(function()
        local player_state = unwrap(controller.PlayerState)
        local perks = unwrap(player_state.PerkComponent).Perks
        local unlocked, histogram = 0, {}
        for i = 1, #perks do
            local tier = unwrap(perks[i]).Tier
            if type(tier) ~= "number" then
                error("FPerkStatus.Tier unreadable")
            end
            histogram[tier] = (histogram[tier] or 0) + 1
            if tier >= 0 then
                unlocked = unlocked + 1
            end
        end
        return unlocked, histogram
    end)
    if not ok or type(count) ~= "number" then
        return nil
    end
    if not logged_tiers then
        logged_tiers = true
        local parts = {}
        for tier, n in pairs(tiers) do
            parts[#parts + 1] = string.format("tier %d x%d", tier, n)
        end
        table.sort(parts)
        log("Mutation tiers: %s", #parts > 0 and table.concat(parts, ", ") or "none")
    end
    return count
end

function M.tick_mutations(ipc)
    local count = read_mutation_count()
    if not count then
        return
    end
    if count ~= last_logged_mutations then
        last_logged_mutations = count
        log("Mutations unlocked: %d", count)
    end
    for _, milestone in ipairs(ap_data.MUTATION_MILESTONES) do
        if count >= milestone then
            ipc:report_location(ap_data.MUTATION_PREFIX .. tostring(milestone))
        end
    end
end

return M
