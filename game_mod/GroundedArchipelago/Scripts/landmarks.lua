-- landmarks.lua
--
-- Landmark checks: polls ASurvivalPlayerState.DiscoveredPointsOfInterest
-- (UPointOfInterestDataAsset*, saved with the world, so earlier discoveries
-- come back on load) and reports "Landmark: <asset name>", e.g.
-- "Landmark: POI_Ashtray". Reported in every Archipelago world; the client
-- only sends them when the seed has LandmarkChecks on. DisplayName reads
-- back as "?", so readable names come from location_review.txt.

local M = {}

local item_grants = require("item_grants")

M.LANDMARK_PREFIX = "Landmark: "

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

local reported = {}   -- asset name -> true once report_location accepted it
local described = {}  -- asset name -> true once its details were logged
local warned = false
local last_count = nil

local function asset_name(asset)
    local ok, name = pcall(function() return asset:GetFName():ToString() end)
    if ok and type(name) == "string" and name ~= "" then
        return name
    end
    local full_ok, full = pcall(function() return asset:GetFullName() end)
    if full_ok and type(full) == "string" then
        return full:match("([^%./]+)$")
    end
    return nil
end

-- One line per landmark, the first time it's seen: what the apworld will
-- need to name and gate it.
local function describe(name, asset)
    if described[name] then
        return
    end
    described[name] = true
    local display = nil
    pcall(function() display = to_text(asset.DisplayName) end)
    local category = nil
    pcall(function() category = to_text(asset.CategoryTag.TagName) end)
    local reward = nil
    pcall(function() reward = to_text(asset.ItemReward.RowName) end)
    log("LANDMARK: %s | name=%s | category=%s | reward=%s",
        name, tostring(display or "?"), tostring(category or "?"), tostring(reward or "?"))
end

local function read_discovered()
    local controller = item_grants.get_local_player_controller()
    if not controller then
        return nil
    end
    local ok, result = pcall(function()
        local player_state = unwrap(controller.PlayerState)
        local list = player_state.DiscoveredPointsOfInterest
        local found = {}
        for i = 1, #list do
            local asset = unwrap(list[i])
            local name = asset and asset_name(asset)
            if name then
                found[#found + 1] = {name = name, asset = asset}
            end
        end
        return found
    end)
    if not ok then
        if not warned then
            warned = true
            log("Couldn't read PlayerState.DiscoveredPointsOfInterest: %s", tostring(result))
        end
        return nil
    end
    return result
end

function M.tick(ipc)
    local discovered = read_discovered()
    if not discovered then
        return
    end
    if #discovered ~= last_count then
        last_count = #discovered
        log("Landmarks discovered in this world: %d", #discovered)
    end
    for _, entry in ipairs(discovered) do
        describe(entry.name, entry.asset)
        if not reported[entry.name] and ipc:report_location(M.LANDMARK_PREFIX .. entry.name) then
            reported[entry.name] = true
        end
    end
end

return M
