"""
Builds the PopTracker pack in ../../tracker/grounded_poptracker/ from the
apworld's own tables (items, locations, rules), so the tracker's logic and
ids can't drift from the world's.

    python tools/generate_poptracker_pack.py /path/to/Archipelago

Needs a real Archipelago checkout on the path (the apworld imports
BaseClasses) and Pillow (for the item icons and the overview map).
Re-run after changing items, locations or rules.

Logic notes:
  * Rules are the same tokens rules.py uses (c1/c2/c3, gas, dive, canister, upper,
    undershed, spit, smoothie, cookery, oven, shovel, jelly, axeN, hammerN, shovelN, daggerN), evaluated by
    scripts/logic.lua against the tracked items. Boss requirements are
    expanded here, so the Lua side only knows base tokens.
  * Craft checks use the vanilla material requirements even in
    RecipeShuffle seeds, which makes a few Tier 2/3 crafts show up later
    than they really are -- never earlier. (Universal Tracker, which runs
    the apworld's own logic, is exact.)
  * Options that add/remove checks (mutations, gold cards,
    the ending, boss checks) come from slot_data via hidden setting items.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

PACK_VERSION = "0.1.0"

# Overview map: area -> (x, y, w, h, colour)
MAP_W, MAP_H = 1200, 800
AREAS = {
    "Start":     (20, 20, 370, 240, (120, 180, 90)),
    "Tier 1":    (410, 20, 370, 240, (150, 190, 80)),
    "Tier 2":    (800, 20, 380, 240, (200, 170, 70)),
    "Haze":      (20, 280, 370, 240, (150, 140, 120)),
    "Pond":      (410, 280, 370, 240, (80, 150, 200)),
    "Tier 3":    (800, 280, 380, 240, (200, 120, 70)),
    "Upper Yard": (20, 540, 570, 240, (110, 160, 110)),
    "Undershed": (610, 540, 570, 240, (110, 100, 130)),
}
CATEGORIES = [
    ("Item: ", "Items"), ("Craft: ", "Crafting"), ("Kill: ", "Bosses"), ("Defeat ", "Bosses"),
    ("Gold Card: ", "Gold Cards"), ("Molars: ", "Molars"), ("Mutations: ", "Mutations"),
    ("Go Big", "Ending"), ("Landmark: ", "Landmarks"),
]
# location category -> hidden setting item that must be on for it to show
CATEGORY_SETTING = {
    "Gold Cards": "setting_gold_cards", "Mutations": "setting_mutations", "Ending": "setting_ending",
    "Landmarks": "setting_landmarks",
}
SETTINGS = ["setting_gold_cards", "setting_mutations", "setting_ending", "setting_landmarks",
            "setting_boss_checks"]


def code_of(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def area_of(tokens) -> str:
    tokens = set(tokens)
    if "undershed" in tokens:
        return "Undershed"
    if "upper" in tokens:
        return "Upper Yard"
    if "dive" in tokens:
        return "Pond"
    if "gas" in tokens:
        return "Haze"
    if "c3" in tokens or "axe3" in tokens or "hammer3" in tokens:
        return "Tier 3"
    if "c2" in tokens or "axe2" in tokens or "hammer2" in tokens:
        return "Tier 2"
    if tokens - {"has"} and any(not t.startswith("has:") for t in tokens):
        return "Tier 1"
    return "Start"


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: generate_poptracker_pack.py <path to Archipelago checkout>")
        raise SystemExit(1)
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(Path(sys.argv[1]).resolve()))
    sys.path.insert(0, str(project_root / "apworld"))

    from grounded import rules
    from grounded.craftsanity import CRAFT_LOCATION_PREFIX, CRAFTSANITY_LOCATION_TO_GATE_ITEM
    from grounded.mutations import MUTATION_REQUIREMENTS
    from grounded.gear import GEAR, PROGRESSIVE_LINES
    from grounded.goldcards import GOLD_CARD_LOCATION_PREFIX
    from grounded.itemsanity import ITEM_LOCATION_PREFIX
    from grounded.items import item_name_to_id, item_table, ItemType, JELLY_BUNDLE, JELLY_BUNDLE_COUNT
    from grounded.killsanity import KILL_LOCATION_PREFIX
    from grounded.locations import location_name_to_id, mod_location_name_to_id
    from grounded.location_renames import ap_name, mod_name
    from grounded.molars import MOLAR_LOCATION_PREFIX, MOLAR_MILESTONES
    from grounded.review_data import DISABLED_LOCATIONS

    def expand(tokens):
        out = []
        for token in tokens:
            if token.startswith("kill:"):
                out.extend(expand(rules.BOSS_REQUIREMENTS[token[5:]]))
            else:
                out.append(token)
        return out

    # location name -> requirement tokens (mirrors rules.set_rules). Built
    # with the mod's names, then switched to Archipelago's (location_renames.py).
    requirements = {name: [] for name in mod_location_name_to_id}
    for boss, tokens in rules.BOSS_REQUIREMENTS.items():
        requirements[KILL_LOCATION_PREFIX + boss] = expand(tokens)
    requirements["Defeat the Infected Broodmother"] = expand(rules.BOSS_REQUIREMENTS["Infected Broodmother"])
    # Director Schmector and the Mant (his stand-in when excluded) have the
    # same requirements, so the tracker doesn't need to know which applies.
    requirements["Go Big Or Never Go Home (Ending)"] = expand(
        ("undershed", "c3", "kill:" + rules.ending_boss(set())))
    for item_name, tokens in rules.ITEM_REQUIREMENTS.items():
        requirements[ITEM_LOCATION_PREFIX + item_name] = expand(tokens)
    for loc_name, gate_item in CRAFTSANITY_LOCATION_TO_GATE_ITEM.items():
        display = loc_name[len(CRAFT_LOCATION_PREFIX):]
        gate = "gear:" + code_of(gate_item) if gate_item in {g.name for g in GEAR} else "has:" + code_of(gate_item)
        requirements[loc_name] = [gate] + expand(rules._craft_requirement(display))
    for row, tokens in rules.GOLD_CARD_REQUIREMENTS.items():
        requirements[GOLD_CARD_LOCATION_PREFIX + row] = expand(tokens)
    for threshold in MOLAR_MILESTONES:
        requirements[MOLAR_LOCATION_PREFIX + str(threshold)] = list(rules._molar_requirement(threshold))
    for loc_name, tokens in MUTATION_REQUIREMENTS.items():
        requirements[loc_name] = expand(tokens)
    from grounded.review_data import LANDMARK_NEEDS
    for loc_name, tokens in LANDMARK_NEEDS.items():
        requirements[loc_name] = expand(tokens)
    requirements = {ap_name(name): tokens for name, tokens in requirements.items()}

    out = project_root / "tracker" / "grounded_poptracker"
    if out.exists():
        shutil.rmtree(out)
    for sub in ("items", "layouts", "locations", "maps", "scripts/autotracking", "images/items", "images/maps"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ items
    # Filler isn't tracked, except the jelly bundles logic counts (rules.py's "jelly").
    trackable = [n for n, d in item_table.items()
                 if (d.type != ItemType.filler or n == JELLY_BUNDLE) and not n.endswith("Progress")]
    icon_colours = {
        "gear": (90, 160, 220), "story": (230, 190, 60), "progressive": (200, 110, 200),
        "t1": (120, 190, 90), "t2": (220, 170, 60), "t3": (220, 100, 70), "other": (150, 150, 150),
    }
    gear_tier = {g.name: g.tier for g in GEAR}

    def colour_for(name):
        if name in PROGRESSIVE_LINES:
            return icon_colours["progressive"]
        if name in gear_tier:
            return icon_colours[f"t{gear_tier[name]}"]
        return icon_colours.get(item_table[name].type.name, icon_colours["other"])

    items_json = []
    for name in trackable:
        code = code_of(name)
        draw_icon(out / "images" / "items" / f"{code}.png", name, colour_for(name))
        if name in PROGRESSIVE_LINES or name == JELLY_BUNDLE:
            max_quantity = JELLY_BUNDLE_COUNT if name == JELLY_BUNDLE else len(PROGRESSIVE_LINES[name])
            items_json.append({"name": name, "type": "consumable", "img": f"images/items/{code}.png",
                               "codes": code, "max_quantity": max_quantity})
        else:
            items_json.append({"name": name, "type": "toggle", "img": f"images/items/{code}.png", "codes": code})
    for setting in SETTINGS:
        draw_icon(out / "images" / "items" / f"{setting}.png", setting[8:].replace("_", " "), (70, 70, 70))
        items_json.append({"name": setting, "type": "toggle", "img": f"images/items/{setting}.png", "codes": setting})
    write_json(out / "items" / "items.json", items_json)

    # --------------------------------------------------------------- locations
    pins = {}  # (area, category) -> [location names]
    for name in location_name_to_id:
        if mod_name(name) in DISABLED_LOCATIONS:
            continue  # unticked in location_review.txt
        category = next((c for prefix, c in CATEGORIES if mod_name(name).startswith(prefix)), "Other")
        pins.setdefault((area_of(requirements[name]), category), []).append(name)

    draw_map(out / "images" / "maps" / "yard.png")
    locations_json, location_paths = [], {}
    per_area = {}
    for (area, category), names in sorted(pins.items()):
        index = per_area.get(area, 0)
        per_area[area] = index + 1
        x0, y0, w, _h, _c = AREAS[area]
        pin_x = x0 + 40 + (index % 5) * ((w - 60) // 5)
        pin_y = y0 + 70 + (index // 5) * 70
        pin_name = f"{area} - {category}"
        sections = []
        for loc in sorted(names):
            rule = "$req" + "".join("|" + t for t in requirements[loc]) if requirements[loc] else "$req"
            section = {"name": loc, "item_count": 1, "access_rules": [rule]}
            setting = CATEGORY_SETTING.get(category)
            if mod_name(loc).startswith("Defeat "):
                setting = "setting_boss_checks"
            if setting:
                section["visibility_rules"] = [setting]
            sections.append(section)
            location_paths[location_name_to_id[loc]] = f"@{pin_name}/{loc}"
        locations_json.append({"name": pin_name, "sections": sections,
                               "map_locations": [{"map": "yard", "x": pin_x, "y": pin_y}]})
    write_json(out / "locations" / "locations.json", locations_json)
    write_json(out / "maps" / "maps.json", [{"name": "yard", "location_size": 28, "location_border_thickness": 4,
                                             "img": "images/maps/yard.png"}])

    # ---------------------------------------------------------------- layouts
    def grid(names, per_row=8):
        return [[code_of(n) for n in names[i:i + per_row]] for i in range(0, len(names), per_row)]

    groups = [
        ("Traversal & Stations", ["Gas Mask", "Diving Gear", "Zip Line Rig", "Smoothie Station", "Cookery", "Oven",
                                  "Consumables", "Utilities"]),
        ("Progressive Gear", list(PROGRESSIVE_LINES)),
        ("Tier 1 Gear", [g.name for g in GEAR if g.tier == 1]),
        ("Tier 2 Gear", [g.name for g in GEAR if g.tier == 2]),
        ("Tier 3 Gear", [g.name for g in GEAR if g.tier == 3]),
        ("New Game+ Materials", [JELLY_BUNDLE]),
    ]
    item_panel = {"type": "array", "orientation": "vertical", "margin": "5", "content": [
        {"type": "group", "header": title, "content": {
            "type": "itemgrid", "item_margin": "2", "item_size": 32, "rows": grid(names)}}
        for title, names in groups
    ]}
    write_json(out / "layouts" / "tracker.json", {
        "tracker_default": {"type": "container", "background": "#202020", "content": {
            "type": "dock", "dropshadow": True, "content": [
                {"type": "dock", "dock": "left", "v_alignment": "stretch", "content": [item_panel]},
                {"type": "map", "maps": ["yard"]},
            ]}},
        "tracker_broadcast": {"type": "array", "content": [item_panel]},
    })

    # ---------------------------------------------------------------- scripts
    melee = {t: [code_of(g.name) for g in GEAR if g.kind == "melee" and g.tier == t and not g.ng_plus
                 and (g.material_fight or 0) < t]
             for t in (1, 2, 3)}
    ng_plus_melee = [code_of(g.name) for g in GEAR if g.kind == "melee" and g.ng_plus]
    armor = {(t, s): [code_of(g.name) for g in GEAR if g.kind == "armor" and g.tier == t and g.slot == s
                      and g.name not in rules._EXCLUDED_FROM_COVERAGE]
             for t in (1, 2, 3) for s in ("head", "chest", "legs")}
    # (tool, tier) -> [[code, combat tier its materials need], ...]
    tools = {(tool, t): [[code_of(g.name), g.material_fight if g.material_fight is not None else t - 1]
                         for g in GEAR if g.tool == tool and g.tier == t]
             for tool in rules._TOOL_KINDS for t in (1, 2, 3)}
    prog_of = {code_of(g): (code_of(p), i + 1) for p, line in PROGRESSIVE_LINES.items() for i, g in enumerate(line)}

    def lua_list(values):
        return "{" + ", ".join(f'"{v}"' for v in values) + "}"

    data_lines = ["-- AUTO-GENERATED by connector/tools/generate_poptracker_pack.py", "LOGIC = {}", "LOGIC.MELEE = {"]
    data_lines += [f"    [{t}] = {lua_list(v)}," for t, v in melee.items()] + ["}"]
    data_lines += [f"LOGIC.NG_PLUS_MELEE = {lua_list(ng_plus_melee)}",
                   f'LOGIC.JELLY = {{"{code_of(JELLY_BUNDLE)}", {JELLY_BUNDLE_COUNT}}}', "LOGIC.ARMOR = {"]
    data_lines += [f'    ["{t}_{s}"] = {lua_list(v)},' for (t, s), v in armor.items()] + ["}", "LOGIC.TOOLS = {"]
    data_lines += [f'    ["{tool}_{t}"] = {{' + ", ".join(f'{{"{c}", {f}}}' for c, f in v) + "},"
                   for (tool, t), v in tools.items()] + ["}", "LOGIC.PROG_OF = {"]
    data_lines += [f'    ["{g}"] = {{"{p}", {i}}},' for g, (p, i) in prog_of.items()] + ["}", ""]
    (out / "scripts" / "logic_data.lua").write_text("\n".join(data_lines), encoding="utf-8")

    mapping = ["-- AUTO-GENERATED by connector/tools/generate_poptracker_pack.py", "ITEM_MAPPING = {"]
    mapping += [f'    [{item_name_to_id[n]}] = "{code_of(n)}",' for n in trackable] + ["}", "LOCATION_MAPPING = {"]
    mapping += [f"    [{loc_id}] = {json.dumps(path)}," for loc_id, path in sorted(location_paths.items())]
    mapping += ["}", ""]
    (out / "scripts" / "autotracking" / "mappings.lua").write_text("\n".join(mapping), encoding="utf-8")

    for name, text in STATIC_FILES.items():
        (out / name).write_text(text.replace("%VERSION%", PACK_VERSION), encoding="utf-8")
    print(f"Wrote {out} ({len(items_json)} items, {len(locations_json)} pins, {len(location_paths)} checks)")


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _font(size):
    from PIL import ImageFont
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_icon(path: Path, name: str, colour) -> None:
    from PIL import Image, ImageDraw
    words = [w for w in re.split(r"[\s.\-]+", name.replace("Progressive", "Prog")) if w]
    label = "".join(w[0] for w in words[:3]).upper()
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((2, 2, 61, 61), radius=12, fill=colour, outline=(20, 20, 20), width=3)
    font = _font(26 if len(label) <= 2 else 20)
    box = draw.textbbox((0, 0), label, font=font)
    draw.text(((64 - (box[2] - box[0])) / 2 - box[0], (64 - (box[3] - box[1])) / 2 - box[1]), label,
              font=font, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    img.save(path)


def draw_map(path: Path) -> None:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (MAP_W, MAP_H), (40, 55, 40))
    draw = ImageDraw.Draw(img)
    font = _font(28)
    for area, (x, y, w, h, colour) in AREAS.items():
        draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=colour, outline=(15, 15, 15), width=4)
        draw.text((x + 16, y + 12), area, font=font, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
    img.save(path)


STATIC_FILES = {
    "manifest.json": json.dumps({
        "name": "Grounded Archipelago",
        "game_name": "Grounded",
        "package_uid": "grounded_archipelago",
        "package_version": "%VERSION%",
        "platform": "pc",
        "author": "Grounded Archipelago contributors",
        "variants": {"standard": {"display_name": "Map Tracker"}},
    }, indent=2),
    "scripts/init.lua": """-- Grounded Archipelago PopTracker pack (generated -- see
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
""",
    "scripts/logic.lua": """-- Mirrors apworld/grounded/rules.py's tokens. Every location's
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
""",
    "scripts/autotracking.lua": """ScriptHost:LoadScript("scripts/autotracking/mappings.lua")

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
""",
    "README.md": """# Grounded Archipelago -- PopTracker pack

Generated by `connector/tools/generate_poptracker_pack.py` -- regenerate
instead of editing by hand.

Install: zip this folder (or copy it) into PopTracker's `packs` folder,
open it in PopTracker, then click the AP button and connect with your slot
name. Items and checked locations track automatically, and checks for
options your seed doesn't use are hidden.

The map is an overview, not the real yard: each pin is a group of checks
(e.g. "Tier 2 - Crafting"), placed in the area/tier logic expects. Hover a
pin for its checks.
""",
}


if __name__ == "__main__":
    main()
