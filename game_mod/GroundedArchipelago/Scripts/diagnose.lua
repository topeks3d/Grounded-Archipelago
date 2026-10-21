-- diagnose.lua
--
-- Finds BP_QuestManagerComponent's asset path (for config.lua's
-- quest_manager_asset_path) from a live instance: FindFirstOf(short class
-- name), then GetClass():GetFullName(). It's a component, so actor dumps
-- don't list it.

local M = {}

local objects = require("ap_objects")
local ap_loop = require("ap_loop")

function M.find_quest_manager_path(config)
    if config.quest_manager_asset_path then
        return -- already configured, nothing to find
    end

    local found = false

    local function try_once()
        if found then
            return
        end
        local ok, instance = pcall(objects.find_first, "BP_QuestManagerComponent_C")
        if not ok or not instance then
            return
        end
        local valid_ok, is_valid = pcall(function() return instance:IsValid() end)
        if valid_ok and not is_valid then
            return
        end

        local path_ok, full_name = pcall(function() return instance:GetClass():GetFullName() end)
        if path_ok and full_name then
            found = true
            -- full_name looks like "Class /Game/Path/To/X.X_C" -- strip the
            -- leading type-name word so what's printed is paste-ready.
            local asset_path = full_name:match("^%S+%s+(.+)$") or full_name
            print(string.format(
                "[GroundedArchipelago] ==========================================\n" ..
                "[GroundedArchipelago] Found BP_QuestManagerComponent_C!\n" ..
                "[GroundedArchipelago] Set this in config.lua:\n" ..
                "[GroundedArchipelago]   config.quest_manager_asset_path = \"%s\"\n" ..
                "[GroundedArchipelago] ==========================================\n",
                asset_path
            ))
        end
    end

    try_once()
    if not found then
        print("[GroundedArchipelago] BP_QuestManagerComponent_C not loaded yet, will keep checking...\n")
        ap_loop.start_loop(config.hook_retry_interval_ms or 3000, function()
            try_once()
        end)
    end
end

return M
