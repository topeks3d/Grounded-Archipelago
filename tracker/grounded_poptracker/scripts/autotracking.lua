ScriptHost:LoadScript("scripts/autotracking/mappings.lua")

local SETTINGS_FROM_SLOT_DATA = {
    setting_mutations = function(sd) return sd.mutation_checks end,
    setting_landmarks = function(sd) return sd.landmark_checks end,
    setting_gold_cards = function(sd) return sd.goal == 4 end,
    setting_ending = function(sd) return sd.goal == 0 or sd.goal == 3 end,
    setting_boss_checks = function(sd) return sd.include_boss_checks ~= false end,
}

local function set_item(code, active, quantity)
    local obj = Tracker:FindObjectForCode(code)
    if not obj then
        return
    end
    if obj.Type == "consumable" then
        obj.AcquiredCount = quantity or 0
    else
        obj.Active = active
    end
end

function onClear(slot_data)
    for _, code in pairs(ITEM_MAPPING) do
        set_item(code, false, 0)
    end
    for _, path in pairs(LOCATION_MAPPING) do
        local obj = Tracker:FindObjectForCode(path)
        if obj then
            obj.AvailableChestCount = obj.ChestCount
        end
    end
    for code, fn in pairs(SETTINGS_FROM_SLOT_DATA) do
        set_item(code, slot_data ~= nil and fn(slot_data) and true or false)
    end
end

function onItem(index, item_id, item_name, player_number)
    local code = ITEM_MAPPING[item_id]
    if not code then
        return
    end
    local obj = Tracker:FindObjectForCode(code)
    if not obj then
        return
    end
    if obj.Type == "consumable" then
        obj.AcquiredCount = obj.AcquiredCount + 1
    else
        obj.Active = true
    end
end

function onLocation(location_id, location_name)
    local path = LOCATION_MAPPING[location_id]
    local obj = path and Tracker:FindObjectForCode(path)
    if obj then
        obj.AvailableChestCount = obj.AvailableChestCount - 1
    end
end

Archipelago:AddClearHandler("clear handler", onClear)
Archipelago:AddItemHandler("item handler", onItem)
Archipelago:AddLocationHandler("location handler", onLocation)
