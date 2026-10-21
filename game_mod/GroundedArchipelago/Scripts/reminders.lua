-- reminders.lua
--
-- Repeating HUD reminders (notifications.show_local, every REPEAT_SECONDS
-- while the situation lasts; the first one shortly after spawning in):
--   * a world is loaded that isn't the Archipelago one -- the mod is off
--     there, which is easy to miss;
--   * the Archipelago world is loaded but the Grounded Client isn't
--     connected to the multiworld (skipped in test mode, which is offline
--     on purpose).

local M = {}

local notifications = require("notifications")

local REPEAT_SECONDS = 300
local SPAWN_GRACE_SECONDS = 5 -- let the HUD come up after spawning

local current = nil   -- reminder kind being repeated, or nil
local next_due = 0    -- os.time() the next one may show
local spawned_since = nil

local function text_for(kind, config)
    if kind == "wrong_world" then
        local required = config.required_world_name or "archipelago"
        return string.format(
            "Archipelago is off: this world isn't named '%s'. Create or rename a world to '%s' to play your seed.",
            required, required)
    end
    return "Archipelago: not connected to the multiworld -- open the Grounded Client and connect."
end

-- Every poll tick. world_name/ap_world/in_world: from world_gate.check;
-- connected: the client is running and connected (ipc:poll's status).
function M.tick(config, world_name, ap_world, in_world, connected, player_spawned)
    local kind = nil
    if world_name and not ap_world then
        kind = "wrong_world"
    elseif in_world and not connected and not (config.test_mode and config.test_mode.enabled) then
        kind = "disconnected"
    end

    local now = os.time()
    if kind and player_spawned then
        spawned_since = spawned_since or now
    else
        spawned_since = nil
    end
    if kind ~= current then
        current = kind
        next_due = 0
    end
    if not kind or not spawned_since or now - spawned_since < SPAWN_GRACE_SECONDS or now < next_due then
        return
    end
    -- Not shown (no HUD yet): try again next tick.
    if notifications.show_local(text_for(kind, config)) then
        next_due = now + REPEAT_SECONDS
    end
end

return M
