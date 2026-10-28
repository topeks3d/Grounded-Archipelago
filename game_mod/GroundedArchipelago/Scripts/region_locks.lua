-- region_locks.lua
--
-- RegionLocks (apworld region_locks.py): every region but the Grasslands
-- needs its "Region Pass: <Region>" item. The player's region comes from
-- the game's own zone volumes (ZoneManagerComponent.PlayerOverlapVolumes:
-- every AGameZoneVolume the player is inside; ZONE_REGIONS below says which
-- region each ZonesTable row is). All of them, not just the one the game
-- names (GetLocalZoneRowHandle): Shed_Grasslands has the same priority as
-- the yard-wide Grasslands volume, so the game reports "Grasslands" there.
-- The highest ZONE_PRIORITY among the player's zones wins.
--
-- Entering a locked region shows a warning; still there GRACE_SECONDS later,
-- the player is put back where they last stood in an open region. Zones
-- missing from ZONE_REGIONS never count as locked (and never become the
-- spot to return to).

local M = {}

local objects = require("ap_objects")
local item_grants = require("item_grants")
local notifications = require("notifications")
local ap_data = require("ap_data")

local REGION_PASSES = ap_data.REGION_PASSES or {}
local START_REGION = ap_data.START_REGION or "Grasslands"
local GRACE_SECONDS = 5

-- ZonesTable row -> region (location_review.txt's region headings), from
-- the "ZONE_ROW:" / "ZONE: now in" lines data_dump.lua logs. Zones left out
-- (caves whose region isn't certain) never count as locked.
M.ZONE_REGIONS = {
    Grasslands = "Grasslands",
    Drygrass = "Grasslands",
    Marsh = "Grasslands",
    FlowerBed = "Grasslands",
    OakTree = "Grasslands",
    OakTree_Interior = "Grasslands",
    Lab = "Grasslands",
    Cave_Anthill = "Grasslands",
    UpperGrasslands = "Upper Grasslands",
    PicnicTable = "Upper Grasslands",
    UpperYard_StorageBox = "Upper Grasslands",
    WaspNest = "Upper Grasslands",
    Haze = "Haze",
    Shed_Grasslands = "Shed Surroundings",
    Hedge = "Hedge",
    Lab_Hedge = "Hedge",
    Cave_SpiderBoss = "Hedge",
    Pond = "Pond",
    Pond_Upper = "Pond",
    Pond_Lower = "Pond",
    Sandbox = "Sandbox",
    Garbage = "Sandbox",
    Cave_BlackAnthill = "Sandbox",
    Wood_Pile_Ext = "Woodpile",
    Wood_Pile_Int = "Woodpile",
    MoldorcCastle = "Moldorc Highlands",
    OminentCave = "Moldorc Highlands",
    OminentLab = "Moldorc Highlands",
    BBQ = "BBQ",
    Undershed = "Undershed",
    UndershedLab = "Undershed",
}

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

-- ZonesTable priorities (the "ZONE_ROW:" dump), except Shed_Grasslands:
-- raised above the outdoor zones around it so it isn't lost under them.
M.ZONE_PRIORITY = {
    Grasslands = 1, Drygrass = 2, Hedge = 3, Marsh = 4, Haze = 5, Sandbox = 6, FlowerBed = 7, OakTree = 8,
    OakTree_Interior = 9, Pond = 10, Pond_Upper = 11, Pond_Lower = 12, Cave_Anthill = 13, Lab = 14, Lab_Hedge = 15,
    Cave_Spider = 16, Cave_BlackAnthill = 17, PicnicTable = 18, Garbage = 19, BBQ = 2, Shed_Grasslands = 3.5,
    Wood_Pile_Ext = 3, Wood_Pile_Int = 4, UpperGrasslands = 3, Undershed = 11, UndershedLab = 12, OminentCave = 13,
    OminentLab = 14, Cave_Generic = 13, Cave_FireAnthill = 18, MoldorcCastle = 11, UpperYard_StorageBox = 12,
    WaspNest = 16, Cave_SpiderBoss = 16, RemixerLab = 16,
}

local function zone_manager()
    local ok, manager = pcall(function()
        return unwrap(objects.find_first("SurvivalGameState").ZoneManagerComponent)
    end)
    return ok and manager or nil
end

-- Every zone row the local player's volumes say they're in, or nil.
local function overlapped_zones(manager, controller)
    local ok, zones = pcall(function()
        local mine = unwrap(controller.PlayerState):GetFullName()
        local entries = manager.PlayerOverlapVolumes
        for i = 1, #entries do
            local entry = unwrap(entries[i])
            if unwrap(entry.PlayerState):GetFullName() == mine then
                local found = {}
                local volumes = entry.Volumes
                for j = 1, #volumes do
                    local volume = unwrap(volumes[j])
                    local row = unwrap(volume.ZoneData).RowName:ToString()
                    if row and row ~= "None" then
                        found[#found + 1] = row
                    end
                end
                return found
            end
        end
        return nil
    end)
    return ok and zones or nil
end

-- The player's zone row and region: the highest-priority zone they're in
-- (ZONE_PRIORITY), or the game's own pick if the volumes can't be read. An
-- unmapped zone on top (an uncertain cave) means no region: never locked.
function M.region_for_zones(zones, fallback_zone)
    local pick, best = nil, nil
    for _, zone in ipairs(zones or {}) do
        local priority = M.ZONE_PRIORITY[zone] or 0
        if not best or priority > best then
            pick, best = zone, priority
        end
    end
    pick = pick or fallback_zone
    return pick, pick and M.ZONE_REGIONS[pick]
end

local last_zones_text = nil

local function current_region()
    local manager = zone_manager()
    local controller = item_grants.get_local_player_controller()
    if not manager or not controller then
        return nil, nil
    end
    local zones = overlapped_zones(manager, controller)
    local fallback_ok, fallback = pcall(function()
        return unwrap(manager:GetLocalZoneRowHandle()).RowName:ToString()
    end)
    local zone, region = M.region_for_zones(zones, fallback_ok and fallback or nil)
    local zones_text = table.concat(zones or {}, "+") .. " -> " .. tostring(region)
    if zones_text ~= last_zones_text then
        last_zones_text = zones_text
        log("REGION_LOCKS: zones %s", zones_text)
    end
    return zone, region
end

local function get_pawn()
    local controller = item_grants.get_local_player_controller()
    if not controller then
        return nil
    end
    local ok, pawn = pcall(function() return unwrap(controller.Pawn) end)
    return ok and pawn or nil
end

-- Regions whose pass has arrived (status.item_counts), plus the start.
function M.open_regions(item_counts)
    local open = {[START_REGION] = true}
    for item_name, region in pairs(REGION_PASSES) do
        if (item_counts[item_name] or 0) > 0 then
            open[region] = true
        end
    end
    return open
end

local safe_spot = nil      -- {location =, rotation =} last seen in an open region
local entered_at = nil     -- os.time() the player entered the locked region
local locked_region = nil

local function send_back(pawn)
    if not safe_spot then
        return false
    end
    local ok, err = pcall(function() pawn:K2_TeleportTo(safe_spot.location, safe_spot.rotation) end)
    if not ok then
        log("REGION_LOCKS: couldn't move the player back: %s", tostring(err))
    end
    return ok
end

-- Every poll tick from main.lua.
function M.tick(status, in_world)
    if not status.region_locks or not in_world then
        entered_at, locked_region = nil, nil
        return
    end
    local zone, region = current_region()
    local pawn = get_pawn()
    if not region or not pawn then
        return
    end
    local open = M.open_regions(status.item_counts or {})
    if open[region] then
        entered_at, locked_region = nil, nil
        pcall(function()
            local location = unwrap(pawn:K2_GetActorLocation())
            local rotation = unwrap(pawn:K2_GetActorRotation())
            safe_spot = {location = {X = location.X, Y = location.Y, Z = location.Z},
                         rotation = {Pitch = rotation.Pitch, Yaw = rotation.Yaw, Roll = rotation.Roll}}
        end)
        return
    end
    local now = os.time()
    if locked_region ~= region then
        locked_region, entered_at = region, now
        log("REGION_LOCKS: entered locked region %s (zone %s)", region, zone)
        notifications.show_local(string.format(
            "%s is locked -- you need the Region Pass: %s. Turn back within %d seconds.", region, region, GRACE_SECONDS))
        return
    end
    if os.difftime(now, entered_at) >= GRACE_SECONDS then
        if send_back(pawn) then
            log("REGION_LOCKS: sent the player back out of %s", region)
            notifications.show_local(string.format("%s is locked -- sent back.", region))
        end
        entered_at = now -- try again after another grace period if still inside
    end
end

return M
