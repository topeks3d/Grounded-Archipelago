-- Mirrors apworld/grounded/rules.py's tokens. Every location's
-- access rule is "$req|token|token|...".

local function count(code)
    return Tracker:ProviderCountForCode(code)
end

-- A gear recipe, whether it came as its own item or as the Nth copy of
-- a progressive item.
function has_gear(code)
    if count(code) > 0 then
        return true
    end
    local prog = LOGIC.PROG_OF[code]
    return prog ~= nil and count(prog[1]) >= prog[2]
end

local function any_gear(codes)
    for _, code in ipairs(codes) do
        if has_gear(code) then
            return true
        end
    end
    return false
end

local function has_armor_tier(tier)
    return any_gear(LOGIC.ARMOR[tier .. "_head"]) and any_gear(LOGIC.ARMOR[tier .. "_chest"])
        and any_gear(LOGIC.ARMOR[tier .. "_legs"])
end

local function has_all_jelly()
    return count(LOGIC.JELLY[1]) >= LOGIC.JELLY[2]
end

-- NG+ weapons only count once their DeDuper Jelly is in hand (rules.py).
local function has_melee(tier)
    if any_gear(LOGIC.MELEE[tier]) then
        return true
    end
    return tier == 3 and any_gear(LOGIC.NG_PLUS_MELEE) and has_all_jelly()
end

function can_fight(tier)
    if tier <= 0 then
        return true
    end
    if tier == 1 then
        return has_melee(1)
    end
    return can_fight(tier - 1) and has_melee(tier) and has_armor_tier(tier)
end

local function has_tool(tool, min_tier)
    -- LOGIC.TOOLS entries: {code, combat tier its materials need}
    for t = min_tier, 3 do
        for _, entry in ipairs(LOGIC.TOOLS[tool .. "_" .. t] or {}) do
            if has_gear(entry[1]) and can_fight(entry[2]) then
                return true
            end
        end
    end
    return false
end

local function upper()
    return count("gas_mask") > 0 and count("diving_gear") > 0 and count("zip_line_rig") > 0 and can_fight(2)
end

local TOKENS = {
    c1 = function() return can_fight(1) end,
    c2 = function() return can_fight(2) end,
    c3 = function() return can_fight(3) end,
    gas = function() return count("gas_mask") > 0 end,
    dive = function() return count("diving_gear") > 0 end,
    canister = function() return count("gas_mask") > 0 and can_fight(2) end,
    upper = upper,
    undershed = function() return upper() and can_fight(3) end,
    spit = function() return count("roasting_spit") > 0 end,
    smoothie = function() return count("smoothie_station") > 0 end,
    cookery = function() return count("cookery") > 0 end,
    oven = function() return count("oven") > 0 end,
    shovel = function() return has_tool("shovel", 1) end,
    jelly = has_all_jelly,
}
for t = 1, 3 do
    TOKENS["axe" .. t] = function() return has_tool("axe", t) end
    TOKENS["hammer" .. t] = function() return has_tool("hammer", t) end
    -- dagger resources are all underwater (rules.py)
    TOKENS["dagger" .. t] = function() return count("diving_gear") > 0 and has_tool("dagger", t) end
end
for t = 1, 2 do
    TOKENS["shovel" .. t] = function() return has_tool("shovel", t) end
end

function req(...)
    for _, token in ipairs({...}) do
        local ok
        if token:sub(1, 4) == "has:" then
            ok = count(token:sub(5)) > 0
        elseif token:sub(1, 5) == "gear:" then
            ok = has_gear(token:sub(6))
        else
            ok = TOKENS[token] and TOKENS[token]() or false
        end
        if not ok then
            return false
        end
    end
    return true
end
