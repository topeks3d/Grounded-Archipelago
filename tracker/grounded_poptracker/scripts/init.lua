-- Grounded Archipelago PopTracker pack (generated -- see
-- connector/tools/generate_poptracker_pack.py)
Tracker:AddItems("items/items.json")
ScriptHost:LoadScript("scripts/logic_data.lua")
ScriptHost:LoadScript("scripts/logic.lua")
Tracker:AddMaps("maps/maps.json")
Tracker:AddLocations("locations/locations.json")
Tracker:AddLayouts("layouts/tracker.json")
if PopVersion and PopVersion >= "0.18.0" then
    ScriptHost:LoadScript("scripts/autotracking.lua")
end
