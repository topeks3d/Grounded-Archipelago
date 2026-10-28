-- main.lua
--
-- UE4SS entry point: wires the modules together. IPC is in ap_ipc.lua,
-- check detection in location_hooks.lua, received items in item_grants.lua.

-- Make sure sibling scripts are on package.path (most UE4SS builds already
-- do this; `debug` may be missing in some sandboxes, hence pcall).
local ok, this_dir = pcall(function()
    local source = debug.getinfo(1, "S").source
    return (source:match("^@(.*)$") or ""):match("^(.*)[/\\][^/\\]+$")
end)
if ok and this_dir then
    package.path = this_dir .. "/?.lua;" .. package.path
end

local config = require("config")
local ipc_module = require("ap_ipc")
local location_hooks = require("location_hooks")
local item_grants = require("item_grants")
local research_control = require("research_control")
local recipe_shuffle = require("recipe_shuffle")
local drop_shuffle = require("drop_shuffle")
local test_mode = require("test_mode")
local landmarks = require("landmarks")
local world_gate = require("world_gate")
local notifications = require("notifications")
local deathlink = require("deathlink")
local player_upgrades = require("player_upgrades")
local safety_net = require("safety_net")
local gear_perks = require("gear_perks")
local compass = require("compass")
local data_dump = require("data_dump")
local region_locks = require("region_locks")
local shop = require("shop")
local mutations = require("mutations")
local ending_gate = require("ending_gate")
local reminders = require("reminders")
local ap_loop = require("ap_loop")
local diagnose = require("diagnose")

local MOD_NAME = "GroundedArchipelago"

local function log(msg)
    print(string.format("[%s] %s\n", MOD_NAME, msg))
end

local ipc_dir = config.get_ipc_dir()
if not ipc_dir then
    log("FATAL: no IPC directory available, mod is disabled. Set config.ipc_dir_override in Scripts/config.lua.")
    return
end

log("Using IPC directory: " .. ipc_dir)
local ipc = ipc_module.new(ipc_dir)

-- Test mode (config.test_mode): log every detected check to
-- <ipc dir>/test_checks.log and optionally hold them back from the room.
test_mode.set_log_dir(ipc_dir)
if test_mode.enabled(config) then
    ipc.test_mode = { log_check = test_mode.log_check, send_checks = config.test_mode.send_checks == true }
end

-- If config.quest_manager_asset_path is unset, find it and print it.
local diag_ok, diag_err = pcall(diagnose.find_quest_manager_path, config)
if not diag_ok then
    log("diagnose.find_quest_manager_path failed, continuing anyway: " .. tostring(diag_err))
end

-- Hooks and pollers, wired once at startup. pcall: a failure there must
-- never stop the item sync loop below from registering.
local hooks_ok, hooks_err = pcall(location_hooks.register_all, ipc, config)
if not hooks_ok then
    log("location_hooks.register_all failed, continuing anyway so item sync still works: " .. tostring(hooks_err))
end

-- The sync loop: the only caller of item_grants.apply, so retrying an item
-- whose grant returned false lives in one place.
local was_in_world = false
-- Whether the mod's game-data edits (research, gold cards, recipe and drop
-- shuffles) are wanted: true in the Archipelago world, false in any other
-- loaded world (everything put back to vanilla), nil on the main menu
-- before any world (left as it is until one loads).
local ap_active = nil

-- Stutter hunting: any step (or a whole tick) taking SLOW_MS or more is
-- logged, at most every SLOW_LOG_SECONDS per step. os.clock is wall time
-- on Windows builds.
local SLOW_MS = 20
local SLOW_LOG_SECONDS = 30
local slow_logged = {}

local function note_time(name, started)
    local ms = (os.clock() - started) * 1000
    if ms >= SLOW_MS then
        local now = os.time()
        if not slow_logged[name] or os.difftime(now, slow_logged[name]) >= SLOW_LOG_SECONDS then
            slow_logged[name] = now
            log(string.format("SLOW: %s took %.0f ms", name, ms))
        end
    end
end

-- pcall(fn, ...), timed under `name`.
local function timed(name, fn, ...)
    local started = os.clock()
    local results = table.pack(pcall(fn, ...))
    note_time(name, started)
    return table.unpack(results, 1, results.n)
end

local function tick()
    local status = ipc:poll()
    -- Test mode: config.test_mode.overrides replace the room's options.
    local override_ok, override_err = timed("test_mode.apply_overrides", test_mode.apply_overrides, status, config)
    if not override_ok then
        log("test_mode.apply_overrides failed, continuing anyway: " .. tostring(override_err))
    end

    -- Only inside the Archipelago world: on the main menu grants "succeed"
    -- against nothing.
    local gate_ok, in_world, world_name, ap_world = timed("world_gate.check", world_gate.check, config)
    if not gate_ok then
        log("world_gate.check failed, treating as not in world: " .. tostring(in_world))
        in_world, world_name, ap_world = false, nil, false
    end
    if world_name then
        ap_active = ap_world == true
    end
    if was_in_world and not in_world then
        research_control.on_world_left()
    end
    was_in_world = in_world
    ipc.reporting_enabled = in_world
    ipc.gold_card_drop_chance = status.gold_card_drop_chance or 0
    ipc.goal = status.goal or 0
    ipc.gold_card_goal_amount = status.gold_card_goal_amount or 65
    ipc.excluded_bosses = status.excluded_bosses or {}
    ipc.progressive_molar_upgrades = status.progressive_molar_upgrades == true

    -- Which save is loaded, refreshed every tick for the client's save binding.
    local identity_ok, identity_err = timed("location_hooks.refresh_world_identity", location_hooks.refresh_world_identity, ipc)
    if not identity_ok then
        log("location_hooks.refresh_world_identity failed, continuing anyway: " .. tostring(identity_err))
    end

    -- One-time data-table dumps (items, recipes, bestiary); no-op once done.
    local dump_ok, dump_err = pcall(location_hooks.dump_static_data_once)
    if not dump_ok then
        log("location_hooks.dump_static_data_once failed, continuing anyway: " .. tostring(dump_err))
    end

    -- Zone / tech tree dumps and zone-change log lines (data_dump.lua).
    timed("data_dump.tick", data_dump.tick, in_world)

    ipc:_flush_from_game()

    -- ShopChecks: purchases become checks (shop.lua).
    local shop_ok, shop_err = timed("shop.tick", shop.tick, ipc, status, in_world)
    if not shop_ok then
        log("shop.tick failed, continuing anyway: " .. tostring(shop_err))
    end

    -- Research/brainpower control and up-front category unlocks.
    local research_ok, research_err = timed("research_control.tick", research_control.tick, config, in_world, ap_active)
    if not research_ok then
        log("research_control.tick failed, continuing anyway: " .. tostring(research_err))
    end

    -- Gold card drop chance: patched straight into the bestiary table
    -- (see location_hooks.apply_gold_card_drop_chance); 0 = vanilla.
    if ap_active ~= nil then
        local gold_ok, gold_err = pcall(
            location_hooks.apply_gold_card_drop_chance,
            ap_active and (config.gold_card_drop_chance_override or ipc.gold_card_drop_chance) or 0
        )
        if not gold_ok then
            log("location_hooks.apply_gold_card_drop_chance failed, continuing anyway: " .. tostring(gold_err))
        end

        -- RecipeShuffle / RecipeCostMultiplier: rewrite ingredients in the
        -- recipe table as soon as the world starts loading; {} / 100 = vanilla.
        local shuffle_ok, shuffle_err = timed("recipe_shuffle.tick", recipe_shuffle.tick, ipc, ap_active and status.recipe_shuffle or {},
            ap_active and status.recipe_cost_multiplier or 100)
        if not shuffle_ok then
            log("recipe_shuffle.tick failed, continuing anyway: " .. tostring(shuffle_err))
        end
    end

    -- ProgressiveMolarUpgrades (player_upgrades.lua).
    local upgrades_ok, upgrades_err = timed("player_upgrades.tick", player_upgrades.tick, status, ipc_dir, in_world, ap_active)
    if not upgrades_ok then
        log("player_upgrades.tick failed, continuing anyway: " .. tostring(upgrades_err))
    end

    -- CreatureDropShuffle: applied per kill by the creature-death hook
    -- (see drop_shuffle.lua); this just keeps its mapping current.
    drop_shuffle.set_mapping(ap_active and status.creature_drop_shuffle or {})

    -- Landmark discovery (see landmarks.lua). Runs in any world:
    -- report_location itself decides whether anything is sent.
    local landmark_ok, landmark_err = timed("landmarks.tick", landmarks.tick, ipc)
    if not landmark_ok then
        log("landmarks.tick failed, continuing anyway: " .. tostring(landmark_err))
    end

    timed("notifications.tick", notifications.tick)

    -- "This world isn't the Archipelago one" / "not connected" reminders.
    local reminder_ok, reminder_err = pcall(function()
        local spawned = world_name ~= nil and world_gate.player_character_spawned()
        reminders.tick(config, world_name, ap_world, in_world, status.client_connected == true, spawned)
    end)
    if not reminder_ok then
        log("reminders.tick failed, continuing anyway: " .. tostring(reminder_err))
    end

    local death_ok, death_err = timed("deathlink.tick", deathlink.tick, ipc, status, in_world)
    if not death_ok then
        log("deathlink.tick failed, continuing anyway: " .. tostring(death_err))
    end

    -- /resync (safety_net.lua).
    local safety_ok, safety_err = timed("safety_net.tick", safety_net.tick, status, in_world)
    if not safety_ok then
        log("safety_net.tick failed, continuing anyway: " .. tostring(safety_err))
    end

    if not in_world then
        return -- received items wait until the player is in the Archipelago world
    end

    local ending_ok, ending_err = timed("ending_gate.tick", ending_gate.tick, ipc)
    if not ending_ok then
        log("ending_gate.tick failed, continuing anyway: " .. tostring(ending_err))
    end

    -- RegionLocks: keep the player out of regions without a pass.
    local regions_ok, regions_err = timed("region_locks.tick", region_locks.tick, status, in_world)
    if not regions_ok then
        log("region_locks.tick failed, continuing anyway: " .. tostring(regions_err))
    end

    -- The client's compass, while it's on (compass.lua).
    local compass_ok, compass_err = timed("compass.tick", compass.tick, status, ipc_dir, in_world)
    if not compass_ok then
        log("compass.tick failed, continuing anyway: " .. tostring(compass_err))
    end

    -- GearPerks: NG+-style perks on the player's gear (gear_perks.lua).
    local perks_ok, perks_err = timed("gear_perks.tick", gear_perks.tick, status.gear_perks, ipc.room_key, in_world)
    if not perks_ok then
        log("gear_perks.tick failed, continuing anyway: " .. tostring(perks_err))
    end

    local mutation_ok, mutation_err = timed("mutations.tick_mutations", mutations.tick_mutations, ipc)
    if not mutation_ok then
        log("mutations.tick_mutations failed, continuing anyway: " .. tostring(mutation_err))
    end

    -- Nothing is granted into a dead character (death screen / respawn).
    local dead_ok, dead = pcall(deathlink.is_local_player_dead)
    if dead_ok and dead then
        return
    end

    local received = {}
    for _, entry in ipairs(status.new_items) do
        local applied = item_grants.apply(entry.name, entry.copy)
        if applied then
            ipc:mark_item_applied(entry.index)
            received[#received + 1] = entry
        else
            log(string.format("Deferring item '%s' (index %d), will retry", entry.name, entry.index))
            break -- keep items in order: don't skip ahead to a later index
        end
    end

    -- On-screen messages: what just arrived, then the client's feed (sent
    -- items, hints). A big batch (e.g. first time loading in) is summarized.
    notifications.set_overlay(status.overlay_notifications)
    pcall(function()
        if #received > 4 then
            notifications.show(string.format("Received %d items from the multiworld", #received))
        else
            for _, entry in ipairs(received) do
                local sender = entry.sender or ""
                local location = type(entry.location) == "string" and entry.location or ""
                local detail = location ~= "" and ((sender ~= "" and "Found at their " or "Location: ") .. location) or ""
                notifications.show(sender ~= "" and string.format("Received %s from %s", entry.name, sender)
                    or string.format("Found your %s", entry.name), detail, item_grants.icon_row(entry.name, entry.copy))
            end
        end
        notifications.show_pending(ipc, status.notifications)
    end)
end

local sync_loop_ok = ap_loop.start_loop(config.poll_interval_ms, function()
    local started = os.clock()
    local ok, err = pcall(tick)
    note_time("whole tick", started)
    if not ok then
        log("tick failed: " .. tostring(err))
    end
end)

if not sync_loop_ok then
    log("FATAL: could not start the item-sync loop (see error above) -- received items will never be applied.")
end

log("Loaded. Waiting for the connector (connector/grounded_connector.py) to write to " .. ipc_dir .. "/to_game.json")
