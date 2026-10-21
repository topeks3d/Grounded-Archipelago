-- deathlink.lua
--
-- Outgoing: polls the local pawn's HealthComponent:IsDead() every tick; a
-- false -> true edge bumps ipc.death_seq for the client. (Don't hook
-- BP_SurvivalPlayerCharacter_C:HandleDeath -- the game froze on death.)
--
-- Incoming: the client bumps death_link_seq; the mod shows the cause and
-- kills the player with the TryKill cheat command. That death isn't sent
-- back out.

local M = {}

local item_grants = require("item_grants")
local notifications = require("notifications")

local SUPPRESS_SECONDS = 15

local function log(fmt, ...)
    print(string.format("[GroundedArchipelago] " .. fmt .. "\n", ...))
end

local suppress_until = 0   -- os.time() before which local deaths aren't reported
local seen_seq = nil       -- last to_game death_link_seq acted on (nil = not read yet)
local was_dead = nil       -- local pawn's IsDead() last tick (nil = unknown)

-- true/false for the local player's pawn, nil if it can't be read right
-- now (no pawn while respawning/loading, etc.).
local function local_player_is_dead()
    local controller = item_grants.get_local_player_controller()
    if not controller then
        return nil
    end
    local ok, dead = pcall(function()
        local pawn = controller.Pawn
        if not pawn or not pawn:IsValid() then
            return nil
        end
        local health = pawn.HealthComponent
        if not health or not health:IsValid() then
            return nil
        end
        return health:IsDead()
    end)
    if ok and type(dead) == "boolean" then
        return dead
    end
    return nil
end

local function poll_local_death(ipc, in_world)
    if not in_world then
        was_dead = nil
        return
    end
    local dead = local_player_is_dead()
    if dead == nil then
        return -- keep the last known state across a missing pawn
    end
    local previous = was_dead
    was_dead = dead
    if not dead or previous ~= false then
        return -- only a real alive -> dead edge counts (not loading in dead)
    end
    if os.time() < suppress_until then
        log("DeathLink: local death caused by a received DeathLink -- not sending it back out")
        return
    end
    if not ipc.reporting_enabled then
        return
    end
    log("DeathLink: local death (#%d)", ipc.death_seq + 1)
    ipc:report_death()
end

-- For main.lua: received items wait while the player is dead.
function M.is_local_player_dead()
    return local_player_is_dead() == true
end

-- Kept so location_hooks.register_all's call stays valid; nothing to hook.
function M.register(_ipc, _register_hook_with_retry, _config)
end

-- Called every poll tick with ipc:poll()'s status.
function M.tick(ipc, status, in_world)
    poll_local_death(ipc, in_world)

    local seq = status.death_link_seq or 0
    if seen_seq == nil or seq < seen_seq or not status.death_link or not in_world then
        -- First read, a client restart, DeathLink off, or not in the world:
        -- nothing to act on (deaths that happen while you aren't playing
        -- are dropped, like in other games).
        seen_seq = seq
        return
    end
    if seq == seen_seq then
        return
    end
    seen_seq = seq
    notifications.show(status.death_link_message ~= "" and status.death_link_message or "DeathLink!")
    suppress_until = os.time() + SUPPRESS_SECONDS
    local ok, err = item_grants.execute_console_command("TryKill")
    if not ok then
        log("DeathLink: TryKill failed: %s", tostring(err))
    else
        log("DeathLink: received -- issued TryKill")
    end
end

return M
