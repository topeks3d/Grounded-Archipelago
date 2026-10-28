-- compass.lua
--
-- Feeds the client's nearest-unchecked compass (apworld compass.py), only
-- while the client has it on (to_game.json "compass"):
--   * ipc/compass.json: the player's position and facing (yaw), each tick.
--   * ipc/landmark_positions.json: where each landmark (POI_* asset) is,
--     from the UPointOfInterestComponents currently loaded -- the yard
--     streams in and out, so this grows as you explore and is kept between
--     sessions (positions never change).

local M = {}

local item_grants = require("item_grants")
local json = require("ap_json")

local SCAN_SECONDS = 15

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

local function write_atomic(path, contents)
    local tmp = path .. ".tmp"
    local f = io.open(tmp, "w")
    if not f then
        return
    end
    f:write(contents)
    f:close()
    if not os.rename(tmp, path) then
        os.remove(path)
        os.rename(tmp, path)
    end
end

local function vector(v)
    v = unwrap(v)
    return {x = v.X, y = v.Y, z = v.Z}
end

-- ---------------------------------------------------------------------
-- Landmark positions
-- ---------------------------------------------------------------------
local positions = nil
local positions_path = nil
local last_scan = 0

local function load_positions(dir)
    if positions then
        return
    end
    positions_path = dir .. "/landmark_positions.json"
    local f = io.open(positions_path, "r")
    local data = nil
    if f then
        data = json.decode(f:read("*a") or "")
        f:close()
    end
    positions = type(data) == "table" and data or {}
end

local function asset_name(asset)
    local ok, name = pcall(function() return asset:GetFName():ToString() end)
    return ok and type(name) == "string" and name ~= "" and name or nil
end

local function is_valid(obj)
    local ok, valid = pcall(function() return obj ~= nil and obj:IsValid() end)
    return ok and valid == true
end

-- The actor a landmark component sits on, only if it's a live actor placed
-- in a loaded level. FindAllOf also returns class defaults, Blueprint
-- templates and components of yard sections that have streamed out; calling
-- into those crashes the game (a native fault pcall can't catch).
local function live_owner(component)
    if not is_valid(component) then
        return nil
    end
    local name_ok, name = pcall(function() return component:GetFullName() end)
    if not name_ok or type(name) ~= "string" or not name:find(":PersistentLevel.", 1, true) then
        return nil
    end
    local owner_ok, owner = pcall(function() return component:GetOuter() end)
    if not owner_ok or not is_valid(owner) then
        return nil
    end
    return owner
end

local function scan_landmarks()
    local ok, components = pcall(FindAllOf, "PointOfInterestComponent")
    if not ok or not components then
        return
    end
    local added = 0
    for _, component in ipairs(components) do
        pcall(function()
            local owner = live_owner(component)
            if not owner then
                return
            end
            local data = unwrap(component.PointOfInterestData)
            local name = is_valid(data) and asset_name(data) or nil
            if name and not positions[name] then
                positions[name] = vector(owner:K2_GetActorLocation())
                added = added + 1
            end
        end)
    end
    if added > 0 then
        write_atomic(positions_path, json.encode(positions))
        log("COMPASS: %d new landmark position(s) seen", added)
    end
end

-- ---------------------------------------------------------------------
-- Every poll tick from main.lua.
-- ---------------------------------------------------------------------
function M.tick(status, ipc_dir, in_world)
    if not status.compass or not in_world then
        return
    end
    load_positions(ipc_dir)
    local now = os.time()
    if os.difftime(now, last_scan) >= SCAN_SECONDS then
        last_scan = now
        scan_landmarks()
    end
    local controller = item_grants.get_local_player_controller()
    if not controller then
        return
    end
    local pawn_ok, pawn = pcall(function() return unwrap(controller.Pawn) end)
    if not pawn_ok or not is_valid(pawn) then
        return -- dead / respawning
    end
    local ok, pose = pcall(function()
        local pos = vector(pawn:K2_GetActorLocation())
        local yaw_ok, yaw = pcall(function() return unwrap(controller:GetControlRotation()).Yaw end)
        pos.yaw = yaw_ok and yaw or 0
        pos.time = now
        return pos
    end)
    if ok and pose then
        write_atomic(ipc_dir .. "/compass.json", json.encode(pose))
    end
end

return M
