-- shop.lua
--
-- ShopChecks (apworld shop.py): buying a BURG.L science shop node sends its
-- check, noticed by reading UPartyComponent.TechUnlockDatas (node row name
-- -> science spent on it). Data only: a crash on the first in-world tick
-- pointed at calling IsTechTreeRecipeUnlocked with a hand-built handle.
-- BURG.L chips open pages as usual. The node still gives what it always
-- did, except recipes that are Archipelago items: research_control.lua
-- empties those nodes. The shop's tables aren't touched here -- emptying
-- the perk / sign set nodes looked to crash the game as a world loaded.

local M = {}

local objects = require("ap_objects")

local SHOP_NODES = require("ap_data").SHOP_NODES or {}

local function unwrap(value)
    local ok, unwrapped = pcall(function() return value:get() end)
    if ok and unwrapped ~= nil then
        return unwrapped
    end
    return value
end

local function get_party()
    local ok, party = pcall(function() return unwrap(objects.find_first("SurvivalGameState").PartyComponent) end)
    return ok and party or nil
end

local function to_text(value)
    local ok, text = pcall(function() return value:ToString() end)
    return ok and type(text) == "string" and text or nil
end

-- Node row name -> its index in TechUnlockDatas. Reading every entry's name
-- took ~35 ms (a hitch every poll), so the full scan runs only when the
-- party or the list's length changes; polls then read a few points.
local index = {}
local indexed_party, indexed_length = nil, -1

local function list_length(list)
    local ok, n = pcall(function() return #list end)
    return ok and n or nil
end

local function row_name(list, i)
    local ok, name = pcall(function() return to_text(unwrap(unwrap(list[i]).TechTreeNodeRowName).Name) end)
    return ok and name or nil
end

local function points_at(list, i)
    local ok, points = pcall(function() return tonumber(unwrap(list[i]).PointsAllocated) end)
    return ok and points or nil
end

local function refresh_index(party, list)
    local length = list_length(list)
    if not length then
        return false
    end
    if party == indexed_party and length == indexed_length then
        return true
    end
    index = {}
    for i = 1, length do
        local name = row_name(list, i)
        if name then
            local best = index[name]
            -- A node listed twice: keep the entry with the most spent.
            if not best or (points_at(list, i) or 0) > (points_at(list, best) or 0) then
                index[name] = i
            end
        end
    end
    indexed_party, indexed_length = party, length
    return true
end

-- Whether a shop node counts as bought: paid in full (every node is listed
-- from the start, with 0 spent).
function M.is_bought(points, cost)
    return points ~= nil and cost ~= nil and cost > 0 and points >= cost
end

local BATCH = 10  -- nodes read per tick (all 60 within a few seconds)
local cursor = 0
local seen_points = {} -- node row -> points last seen (changes are logged)

local function log(fmt, ...)
    print(string.format("[GroundedArchipelago] " .. fmt .. "\n", ...))
end

local function poll_some(ipc, party)
    local ok_list, list = pcall(function() return party.TechUnlockDatas end)
    if not ok_list or not list or not refresh_index(party, list) then
        return
    end
    local count = #SHOP_NODES
    local read = 0
    for _ = 1, count do
        if read >= BATCH then
            break
        end
        cursor = cursor % count + 1
        local entry = SHOP_NODES[cursor]
        local node, location, cost = entry[2], entry[3], entry[4] or 0
        local i = index[node]
        if i and not ipc.checked_locations[location] then
            read = read + 1
            local points = points_at(list, i)
            if points and seen_points[node] ~= nil and seen_points[node] ~= points then
                log("SHOP: node %s now has %s science spent", node, tostring(points))
            end
            seen_points[node] = points
            if M.is_bought(points, cost) then
                if row_name(list, i) == node then
                    ipc:report_location(location)
                else
                    indexed_length = -1 -- the list moved under us: rescan next tick
                    return
                end
            end
        end
    end
end

-- Every poll tick from main.lua, in the loaded Archipelago world.
function M.tick(ipc, status, in_world)
    if not in_world or not status.shop_checks or #SHOP_NODES == 0 then
        return
    end
    local party = get_party()
    if party then
        poll_some(ipc, party)
    end
end

return M
