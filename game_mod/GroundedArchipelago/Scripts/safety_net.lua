-- safety_net.lua
--
-- /resync in the client bumps to_game.json's resync_seq: every received
-- item that's safe to apply twice (recipe and station unlocks -- see
-- item_grants.is_reapply_safe) is applied again, in case the save lost
-- some (e.g. a crash before the game saved).

local M = {}

local item_grants = require("item_grants")
local notifications = require("notifications")

local function log(fmt, ...)
    print(string.format("[GroundedArchipelago] " .. fmt .. "\n", ...))
end

-- ---------------------------------------------------------------------
-- /resync
-- ---------------------------------------------------------------------
local seen_seq = nil -- last resync_seq acted on (nil = not read yet)

local function reapply_all(received)
    local applied, skipped = 0, 0
    local copies = {}
    for _, entry in ipairs(received) do
        copies[entry.name] = (copies[entry.name] or 0) + 1
    end
    -- Progressive items: only the highest copy matters.
    for name, count in pairs(copies) do
        if item_grants.is_reapply_safe(name) then
            if item_grants.apply(name, count) then
                applied = applied + 1
            end
        else
            skipped = skipped + 1
        end
    end
    log("RESYNC: re-applied %d unlock item(s); %d kind(s) of bundle/one-off item not repeated", applied, skipped)
    notifications.show_local(string.format("Archipelago: re-applied %d unlocks from the multiworld", applied))
end

-- ---------------------------------------------------------------------
-- Every poll tick from main.lua.
-- ---------------------------------------------------------------------
function M.tick(status, in_world)
    if not in_world then
        return
    end
    local seq = status.resync_seq or 0
    if seen_seq == nil or seq < seen_seq then
        seen_seq = seq -- first read, or the client restarted
    elseif seq > seen_seq then
        seen_seq = seq
        reapply_all(status.received_items or {})
    end
end

return M
