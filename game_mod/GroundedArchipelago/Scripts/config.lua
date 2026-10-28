-- config.lua
--
-- Everything here is safe to hand-edit. If you see a "Could not
-- auto-detect mod directory" warning in the UE4SS log, set
-- `ipc_dir_override` below -- see "IPC directory resolution".

local config = {}

config.poll_interval_ms = 1000 -- how often to check for new items / run poll-based location triggers

-- ---------------------------------------------------------------------
-- Test mode (for trying out changes without generating a new room)
-- ---------------------------------------------------------------------
-- enabled = true:
--   * Every check the mod detects is written to ipc/test_checks.log
--     (including repeats -- at most once per 10 seconds each -- and checks
--     done outside the "archipelago" world).
--   * send_checks = false (default): detected checks are ONLY logged --
--     never sent or marked checked, so you can trigger them again.
--   * overrides: replace the room's option values (nil = the room's value).
--     Shuffles are built locally from `seed`.
--
-- Turn this back off (enabled = false) before playing a real seed.
config.test_mode = {
    enabled = false,
    send_checks = false,
    seed = 1,
    overrides = {
        creature_drop_shuffle = nil, -- true / false
        recipe_shuffle = nil,        -- true / false
        recipe_cost_multiplier = nil, -- 50-300 (percent)
        progressive_molar_upgrades = nil, -- true / false (tiers follow received copies)
        gear_perks = nil,            -- 0 off, 1 weapons, 2 weapons and armor
        region_locks = nil,          -- true / false (passes follow received items)
        shop_checks = nil,           -- true / false
        gold_card_drop_chance = nil, -- 0-50 (50 = 100%)
        gold_card_goal_amount = nil, -- 1-65
        goal = nil,                  -- 0 embiggening, 1 boss_only, 2 infected_broodmother,
                                     -- 3 both, 4 gold_cards, 5 itemsanity, 6 story_boss_only, 7 short
        excluded_bosses = nil,       -- e.g. {"Wasp Queen", "Black Widow"}
        death_link = nil,            -- true / false
    },
}

-- ---------------------------------------------------------------------
-- Which world Archipelago runs in (see world_gate.lua)
-- ---------------------------------------------------------------------
-- Received items are only applied, and checks only sent, while you're
-- in a loaded world with this name (case-insensitive) -- never on the
-- main menu, and never in your other saves. Set to nil to allow any
-- world (e.g. if you join someone else's game and the name doesn't come
-- through).
config.required_world_name = "archipelago"
-- After the world is loaded and your character has spawned, wait this
-- long before granting items, so nothing lands mid-loading-screen.
config.world_settle_ms = 3000

-- The ending only counts after beating Director Schmector (or the Mant if
-- he's in your ExcludedBosses) -- see ending_gate.lua. If that boss's kill
-- is ever NOT detected (the UE4SS log never shows "REPORTED ... Kill:
-- Director Schmector"), set this to false so you can still finish.
config.gate_ending_on_final_boss = true
config.hook_retry_interval_ms = 3000 -- how often to retry registering a hook whose target class isn't loaded yet

-- ---------------------------------------------------------------------
-- Gold Card drop chance override (optional, local-only)
-- ---------------------------------------------------------------------
-- Overrides the room's GoldCardDropChance without regenerating (it only
-- affects an in-game roll, never logic). Same 0-50 scale (50 = 100%).
-- nil = use the room's value.
config.gold_card_drop_chance_override = nil -- e.g. 25 for a 50% chance

-- ---------------------------------------------------------------------
-- Research / brainpower (see research_control.lua)
-- ---------------------------------------------------------------------
-- true (default): analyzing resources and brainpower level-ups unlock no
-- recipes, brainpower is set to max, and AP-managed gear recipes are
-- only obtainable through AP items. Set false to leave research vanilla.
config.disable_research = true

-- ---------------------------------------------------------------------
-- On-screen messages
-- ---------------------------------------------------------------------
-- Where received / sent items, hints and DeathLinks are shown:
--   "overlay" (default): the Grounded Client draws notification cards over
--             the game (needs Windowed or Borderless display mode); the HUD
--             stays quiet. If the client's overlay is off, feed lines instead.
--   "banner": the game's big key-item banner, location on a second line.
--   "feed":   only the small notification feed lines.
config.notification_style = "overlay"
-- How long each "banner" stays up, in seconds.
config.banner_seconds = 3

-- To make up for research unlocks being gone, every recipe whose category
-- tag matches one of these patterns is unlocked up front. Matching is a
-- case-insensitive substring check with punctuation ignored, against the
-- recipe's CategoryTag. The first session prints one "RECIPE_CATEGORY:"
-- line per real category (with UNLOCKED/locked) -- if something you
-- expected is locked (or vice versa), adjust these to match those names.
-- AP-managed gear recipes are never unlocked by this, whatever matches.
config.unlock_crafting_categories = {"material"} -- Material Resources
-- Building tags: Recipe.Building.Structure.* / StructureComplex.*, .Utility.*,
-- .Decoration.*, .BugTrophy.*. The Smoothie Station, Cookery and Oven stay AP
-- items; the Roasting Spit and Drying Rack are unlocked here ("utility").
config.unlock_building_categories = {"structure", "utility", "decoration", "bugtrophy"}

-- ---------------------------------------------------------------------
-- Known asset paths for hooks (see location_hooks.lua)
-- ---------------------------------------------------------------------
-- BP_QuestManagerComponent's full asset path (needed for item pickup, gold
-- card and craft checks). If a game update moves it, set this to nil: the
-- mod then finds the new path and prints it on load (diagnose.lua).
config.quest_manager_asset_path = "/Game/Blueprints/Quests/BP_QuestManagerComponent.BP_QuestManagerComponent_C"

-- ---------------------------------------------------------------------
-- IPC directory resolution
-- ---------------------------------------------------------------------
-- The folder the mod and the Grounded Client exchange files in. It's
-- auto-detected; if the UE4SS log warns that it couldn't be, set an
-- absolute path here (forward slashes are fine) and pass the same path to
-- the client's --ipc-dir:
--
--   config.ipc_dir_override = "C:/Games/Grounded/Binaries/Win64/ue4ss/Mods/GroundedArchipelago/ipc"

config.ipc_dir_override = nil

-- Strategy 1: this file's own path via Lua's debug library (not available
-- on every UE4SS build).
local function try_debug_getinfo()
    local ok, info = pcall(function()
        return debug.getinfo(1, "S")
    end)
    if not ok or not info or not info.source then
        return nil
    end
    local path = info.source:match("^@(.*)$")
    if not path then
        return nil
    end
    -- this file lives at <mod_dir>/Scripts/config.lua
    local scripts_dir = path:match("^(.*)[/\\][^/\\]+$")
    if not scripts_dir then
        return nil
    end
    return scripts_dir:match("^(.*)[/\\][^/\\]+$")
end

-- Strategy 2: the working directory is normally Binaries/Win64; confirm by
-- finding this file at ue4ss/Mods/GroundedArchipelago/Scripts/config.lua.
local function try_relative_cwd()
    local candidate_mod_dir = "ue4ss/Mods/GroundedArchipelago"
    local probe = io.open(candidate_mod_dir .. "/Scripts/config.lua", "r")
    if not probe then
        return nil
    end
    probe:close()
    return candidate_mod_dir
end

function config.get_ipc_dir()
    if config.ipc_dir_override then
        return config.ipc_dir_override
    end

    local mod_dir = try_debug_getinfo()
    if not mod_dir then
        mod_dir = try_relative_cwd()
    end

    if not mod_dir then
        print(
            "[GroundedArchipelago] Could not auto-detect mod directory (tried debug.getinfo and a " ..
            "relative-cwd guess, neither worked). Set config.ipc_dir_override in Scripts/config.lua to " ..
            "an absolute path -- see the comment above it for the exact format.\n"
        )
        return nil
    end

    return mod_dir .. "/ipc"
end

return config
