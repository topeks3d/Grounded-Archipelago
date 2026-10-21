-- world_gate.lua
--
-- "Is the player in the Archipelago world?" (On the main menu, grants
-- "succeed" against nothing and would be marked applied; in any other
-- world the whole mod stays out of the way.) All of:
--   * ASurvivalGameState has a PlaythroughName (empty on the main menu),
--   * it matches config.required_world_name (case-insensitive, trimmed;
--     nil/"" accepts any world),
--   * the local PlayerController has a SurvivalPlayerCharacter pawn,
--   * all of that has held for config.world_settle_ms.

local M = {}

local objects = require("ap_objects")

local item_grants = require("item_grants")

local function log(fmt, ...)
    print(string.format("[GroundedArchipelago] " .. fmt .. "\n", ...))
end

local function is_valid(obj)
    if not obj then
        return false
    end
    local ok, valid = pcall(function() return obj:IsValid() end)
    return ok and valid == true
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

local function normalize(name)
    return (tostring(name or ""):lower():gsub("^%s+", ""):gsub("%s+$", ""))
end

-- Returns the loaded world's name, or nil if no world is loaded.
function M.read_world_name()
    local gs_ok, game_state = pcall(objects.find_first, "SurvivalGameState")
    if not gs_ok or not is_valid(game_state) then
        return nil
    end
    local name_ok, name = pcall(function() return game_state.PlaythroughName end)
    if not name_ok then
        return nil
    end
    local text = to_text(name)
    if not text or text == "" then
        return nil
    end
    return text
end

local function player_character_spawned()
    local controller = item_grants.get_local_player_controller()
    if not controller then
        return false
    end
    local pawn_ok, pawn = pcall(function() return controller.Pawn end)
    if not pawn_ok or not is_valid(pawn) then
        return false
    end
    local class_ok, class_name = pcall(function() return pawn:GetClass():GetFullName() end)
    return class_ok and type(class_name) == "string" and class_name:find("SurvivalPlayerCharacter", 1, true) ~= nil
end

local last_state = nil      -- last logged state key, so each state is only logged once
local in_world_since = nil  -- os.time() when every check first passed

local function set_state(key, fmt, ...)
    if last_state ~= key then
        last_state = key
        log(fmt, ...)
    end
end

M.player_character_spawned = player_character_spawned

-- Returns in_world (bool), world_name (string or nil), ap_world (bool: a
-- world is loaded and its name is the Archipelago one -- true as soon as
-- it starts loading, unlike in_world). Cheap enough to call every poll tick.
function M.check(config)
    local world_name = M.read_world_name()
    if not world_name then
        in_world_since = nil
        set_state("menu", "Not in a world (main menu / loading) -- holding received items until one is loaded.")
        return false, nil, false
    end

    local required = config.required_world_name
    if required and required ~= "" and normalize(world_name) ~= normalize(required) then
        in_world_since = nil
        set_state("wrong:" .. world_name,
            "World '%s' is loaded, but Archipelago only runs in a world named '%s' -- the mod is off here " ..
            "(vanilla game, received items held, checks ignored). Create/rename a world to '%s' (or change " ..
            "required_world_name in Scripts/config.lua).", world_name, required, required)
        return false, world_name, false
    end

    if not player_character_spawned() then
        in_world_since = nil
        set_state("nopawn:" .. world_name, "World '%s' loading -- waiting for the player to spawn.", world_name)
        return false, world_name, true
    end

    local now = os.time()
    in_world_since = in_world_since or now
    if os.difftime(now, in_world_since) * 1000 < (config.world_settle_ms or 0) then
        return false, world_name, true
    end

    set_state("in:" .. world_name, "In Archipelago world '%s' -- applying received items and sending checks.", world_name)
    return true, world_name, true
end

return M
