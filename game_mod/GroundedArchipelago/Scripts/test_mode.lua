-- test_mode.lua
--
-- Local testing without a new room (config.lua's "Test mode"):
--   * apply_overrides: replaces the room's options with config.test_mode's;
--     shuffle options get a local seeded shuffle from ap_data.lua's pools.
--   * log_check: every detected check goes to <ipc dir>/test_checks.log.

local M = {}

local ap_data = require("ap_data")

local log_path = nil
local last_logged = {}  -- name -> os.time() of the last line, to skip per-tick repeats

local function log(fmt, ...)
    print(string.format("[GroundedArchipelago] " .. fmt .. "\n", ...))
end

function M.enabled(config)
    return config.test_mode ~= nil and config.test_mode.enabled == true
end

-- ---------------------------------------------------------------------
-- Seeded local shuffles (same rules as drop_shuffle.py / recipe_shuffle.py)
-- ---------------------------------------------------------------------

-- Park-Miller: deterministic per seed, and doesn't disturb math.random.
local function make_rng(seed)
    local state = math.floor(tonumber(seed) or 1) % 2147483647
    if state <= 0 then
        state = state + 2147483646
    end
    return function(n) -- 1..n
        state = (state * 16807) % 2147483647
        return (state % n) + 1
    end
end

local function shuffled_copy(list, rand)
    local copy = {}
    for i, v in ipairs(list) do
        copy[i] = v
    end
    for i = #copy, 2, -1 do
        local j = rand(i)
        copy[i], copy[j] = copy[j], copy[i]
    end
    return copy
end

local function build_drop_mapping(seed)
    local rand = make_rng(seed)
    local mapping = {}
    for _, group in ipairs(ap_data.DROP_GROUPS) do
        local shuffled = shuffled_copy(group, rand)
        for i, row in ipairs(group) do
            if shuffled[i] ~= row then
                mapping[row] = shuffled[i]
            end
        end
    end
    return mapping
end

local function build_recipe_mapping(seed)
    local rand = make_rng(seed + 7919)
    local mapping = {}
    for _, gear in ipairs(ap_data.RECIPE_SHUFFLED_GEAR) do
        local recipe_row, tier, cheap = gear[1], gear[2], gear[3]
        local pools = ap_data.RECIPE_TIER_POOLS[tier]
        local first = pools.signature[rand(#pools.signature)]
        local candidates = {}
        for _, material in ipairs(pools.rest) do
            if material[1] ~= first[1] then
                candidates[#candidates + 1] = material
            end
        end
        candidates = shuffled_copy(candidates, rand)
        local entries = {}
        local picks = {first}
        for i = 1, ap_data.RECIPE_MAX_INGREDIENTS - 1 do
            picks[#picks + 1] = candidates[i]
        end
        for _, material in ipairs(picks) do
            local low, high = material[2], cheap and material[2] or material[3]
            entries[#entries + 1] = {material[1], low + rand(high - low + 1) - 1}
        end
        mapping[recipe_row] = entries
    end
    return mapping
end

local cache = {}
local function cached(kind, seed, builder)
    local key = kind .. ":" .. tostring(seed)
    if not cache[key] then
        cache[key] = builder(seed)
        local n = 0
        for _ in pairs(cache[key]) do
            n = n + 1
        end
        log("TEST MODE: built local %s (seed %s, %d entries)", kind, tostring(seed), n)
    end
    return cache[key]
end

-- ---------------------------------------------------------------------
-- Overrides
-- ---------------------------------------------------------------------

local PLAIN_OVERRIDES = {
    "goal", "excluded_bosses", "gold_card_drop_chance", "gold_card_goal_amount", "death_link",
}
local announced = false

function M.apply_overrides(status, config)
    if not M.enabled(config) then
        return
    end
    local overrides = config.test_mode.overrides or {}
    local seed = config.test_mode.seed or 1
    for _, key in ipairs(PLAIN_OVERRIDES) do
        if overrides[key] ~= nil then
            status[key] = overrides[key]
        end
    end
    if overrides.creature_drop_shuffle ~= nil then
        status.creature_drop_shuffle = overrides.creature_drop_shuffle
            and cached("drop shuffle", seed, build_drop_mapping) or {}
    end
    if overrides.recipe_shuffle ~= nil then
        status.recipe_shuffle = overrides.recipe_shuffle
            and cached("recipe shuffle", seed, build_recipe_mapping) or {}
    end
    if not announced then
        announced = true
        local parts = {}
        for key, value in pairs(overrides) do
            parts[#parts + 1] = key .. "=" .. tostring(value)
        end
        table.sort(parts)
        log("TEST MODE ON: overrides %s; checks %s; detections logged to test_checks.log",
            #parts > 0 and table.concat(parts, ", ") or "(none)",
            config.test_mode.send_checks and "ARE sent" or "are NOT sent")
    end
end

-- ---------------------------------------------------------------------
-- Check log
-- ---------------------------------------------------------------------

function M.set_log_dir(dir)
    log_path = dir and (dir .. "/test_checks.log") or nil
end

-- status: short reason, e.g. "NEW - sent", "already checked", "not sent (test mode)".
function M.log_check(name, status)
    if not log_path then
        return
    end
    local now = os.time()
    local key = name .. "|" .. status
    if last_logged[key] and now - last_logged[key] < 10 then
        return -- polled checks re-fire every tick; one line per 10s is plenty
    end
    last_logged[key] = now
    local f = io.open(log_path, "a")
    if not f then
        return
    end
    -- Renamed in Archipelago (location_renames.py)? Show that name too.
    local shown = name
    if ap_data.LOCATION_RENAMES and ap_data.LOCATION_RENAMES[name] then
        shown = name .. " (AP: " .. ap_data.LOCATION_RENAMES[name] .. ")"
    end
    f:write(string.format("%s  %-45s  %s\n", os.date("%Y-%m-%d %H:%M:%S"), shown, status))
    f:close()
end

return M
