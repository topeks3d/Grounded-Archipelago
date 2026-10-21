-- ending_gate.lua
--
-- The ending only counts once the final boss is beaten: Director
-- Schmector, or the Mant if he's in ExcludedBosses (keep in sync with
-- rules.py's ending_boss). Two layers:
--   1. Block: the endgame shrink pad buttons
--      (BP_Button_Switch_ShrinkpadEndGame_Activate_C / _Target_C) report
--      Disabled (EInteractionState 1) from IsInteractionEnabled until the
--      kill is recorded -- only while the game itself has made them
--      interactable (ConditionalToggle_IsInteractable). The early story's
--      separate Shrinkpad_Activate/_Target pair is never touched. If the
--      toggle can't be read the button is left alone.
--   2. Backstop: if the game is won anyway, the ending check is held
--      (persisted) until the kill is recorded.

local M = {}
M.enabled = true

local notifications = require("notifications")

local ENDING_LOCATION = "Go Big Or Never Go Home (Ending)"
local BUTTON_PATHS = {
    "/Game/Blueprints/Environment/BP_Button_Switch_ShrinkpadEndGame_Activate.BP_Button_Switch_ShrinkpadEndGame_Activate_C:IsInteractionEnabled",
    "/Game/Blueprints/Environment/BP_Button_Switch_ShrinkpadEndGame_Target.BP_Button_Switch_ShrinkpadEndGame_Target_C:IsInteractionEnabled",
}
local INTERACTION_DISABLED = 1
local NOTICE_INTERVAL = 15 -- seconds between "beat the boss first" messages

local function log(fmt, ...)
    print(string.format("[GroundedArchipelago] " .. fmt .. "\n", ...))
end

function M.required_boss(ipc)
    for _, boss in ipairs(ipc.excluded_bosses or {}) do
        if boss == "Director Schmector" then
            return "Mant"
        end
    end
    return "Director Schmector"
end

function M.boss_defeated(ipc)
    return ipc.checked_locations["Kill: " .. M.required_boss(ipc)] == true
end

local last_notice = 0

local function notice(ipc)
    if os.difftime(os.time(), last_notice) >= NOTICE_INTERVAL then
        last_notice = os.time()
        notifications.show_local(string.format("Archipelago: defeat %s before going home", M.required_boss(ipc)))
    end
end

-- True only when the game has made this endgame button usable (the
-- ending is actually available). Anything unreadable counts as false.
local function game_made_interactable(Context)
    local ok, enabled = pcall(function()
        local button = Context
        local get_ok, unwrapped = pcall(function() return Context:get() end)
        if get_ok and unwrapped ~= nil then
            button = unwrapped
        end
        local toggle = button.ConditionalToggle_IsInteractable
        local toggle_ok, inner = pcall(function() return toggle:get() end)
        if toggle_ok and inner ~= nil then
            toggle = inner
        end
        return toggle:IsEnabled()
    end)
    return ok and enabled == true
end

local warned_unreadable = false

function M.register(ipc, register_hook_with_retry, config)
    M.enabled = config.gate_ending_on_final_boss ~= false
    if not M.enabled then
        log("Ending gate disabled in config.lua -- the ending counts without beating the final boss")
        return
    end
    for _, path in ipairs(BUTTON_PATHS) do
        register_hook_with_retry("ending gate (endgame shrink pad button)", path, function(Context)
            if not ipc.reporting_enabled or M.boss_defeated(ipc) then
                return nil -- leave the game's own answer alone
            end
            if not game_made_interactable(Context) then
                if not warned_unreadable then
                    warned_unreadable = true
                    log("Ending gate: endgame button not interactable yet (or unreadable) -- leaving it alone")
                end
                return nil
            end
            notice(ipc)
            return INTERACTION_DISABLED
        end, config.hook_retry_interval_ms)
    end
end

function M.on_game_won(ipc)
    if not M.enabled or M.boss_defeated(ipc) then
        ipc:report_location(ENDING_LOCATION)
        return
    end
    log("Ending reached before %s was recorded as defeated -- holding the ending check until then",
        M.required_boss(ipc))
    ipc:set_ending_pending(true)
    notice(ipc)
end

-- Called every poll tick: sends a held ending once the kill is recorded
-- (from this session's hooks or merged in from the server).
function M.tick(ipc)
    if ipc.ending_pending and M.boss_defeated(ipc) and ipc:report_location(ENDING_LOCATION) then
        ipc:set_ending_pending(false)
    end
end

return M
