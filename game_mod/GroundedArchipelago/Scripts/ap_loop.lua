-- ap_loop.lua
--
-- "Run forever" on whichever UE4SS primitive exists: LoopAsync (older) or
-- LoopInGameThreadWithDelay (newer). Calling a missing one unprotected
-- would stop every periodic part of the mod.

local M = {}

-- Returns true on success, false (and logs a message) if no usable
-- loop-scheduling primitive is available at all.
function M.start_loop(interval_ms, callback)
    if type(LoopInGameThreadWithDelay) == "function" then
        local ok, err = pcall(function()
            LoopInGameThreadWithDelay(interval_ms, function()
                callback()
            end)
        end)
        if ok then
            return true
        end
        print(string.format(
            "[GroundedArchipelago] LoopInGameThreadWithDelay exists but failed (%s), trying LoopAsync\n",
            tostring(err)
        ))
    end

    if type(LoopAsync) == "function" then
        local ok, err = pcall(function()
            LoopAsync(interval_ms, function()
                callback()
                return false -- LoopAsync's convention: false = keep looping
            end)
        end)
        if ok then
            return true
        end
        print(string.format("[GroundedArchipelago] LoopAsync exists but failed (%s)\n", tostring(err)))
    end

    print(
        "[GroundedArchipelago] ERROR: no working loop-scheduling function found " ..
        "(tried LoopInGameThreadWithDelay and LoopAsync). Periodic item sync and " ..
        "poll-based location checks will not run. This likely means your UE4SS version uses a " ..
        "different API than either of these -- please report this so it can be added.\n"
    )
    return false
end

return M
