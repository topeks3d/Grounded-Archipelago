-- ap_ipc.lua
--
-- File-based IPC with the Grounded Client (to_game.json / from_game.json /
-- applied_state.json; see ARCHITECTURE.md). Stock `io`/`os` only.

local json = require("ap_json")

-- The client rewrites client_heartbeat.json every few seconds while it runs.
local HEARTBEAT_STALE_SECONDS = 20

local function ensure_dir(path)
    local probe = path .. "/._ap_probe"
    local f = io.open(probe, "w")
    if f then
        f:close()
        os.remove(probe)
        return true
    end
    local sep = package.config:sub(1, 1)
    if sep == "\\" then
        os.execute('mkdir "' .. path:gsub("/", "\\") .. '" >nul 2>nul')
    else
        os.execute('mkdir -p "' .. path .. '"')
    end
    f = io.open(probe, "w")
    if f then
        f:close()
        os.remove(probe)
        return true
    end
    return false
end

local ipc = {}
ipc.__index = ipc

function ipc.new(dir)
    local self = setmetatable({}, ipc)
    self.dir = dir
    if not ensure_dir(dir) then
        print(string.format("[GroundedArchipelago] WARNING: could not create/access IPC directory '%s'\n", dir))
    end
    self.to_game_path = dir .. "/to_game.json"
    self.from_game_path = dir .. "/from_game.json"
    self.state_path = dir .. "/applied_state.json"

    -- What we've already told the connector about / already applied from it.
    self.checked_locations = {}   -- set: name -> true
    self.applied_item_index = -1  -- last index from to_game.received_items we've handled
    self.applied_tier1_unlock = false -- see main.lua's poll loop / item_grants.unlock_tier1_recipes
    self.goal_complete = false
    -- The game was won before the final boss's kill was recorded -- see
    -- ending_gate.lua. Persisted, reset with the room.
    self.ending_pending = false
    -- AP room ("<seed>:<slot>") the state above belongs to -- see _sync_room.
    self.room_key = nil
    -- Refreshed every tick from to_game.json; read at kill time by hooks.
    self.gold_card_drop_chance = 0
    self.goal = 0
    self.gold_card_goal_amount = 65
    -- Optional callback(self) after each NEW location (goal checks).
    self.on_location_reported = nil
    -- Save binding (set by location_hooks.lua's refresh_world_identity);
    -- nil until read (e.g. on the main menu).
    self.world_name = nil
    self.world_code = nil
    -- False outside the Archipelago world (world_gate.lua): nothing is sent.
    self.reporting_enabled = false
    -- recipe row -> ingredient slot count, set by recipe_shuffle.lua.
    self.recipe_slots = {}
    -- Highest client notification id already shown (persisted, so a game
    -- restart doesn't replay them). See notifications.lua.
    self.last_notification_id = 0
    -- Local deaths reported to the client for DeathLink (in memory only --
    -- the client treats a lower value as a restart). See deathlink.lua.
    self.death_seq = 0
    local data_ok, ap_data = pcall(require, "ap_data")
    self.mod_version = data_ok and ap_data.VERSION or nil

    self:_load_state()

    -- Write from_game.json right away, so it exists (and the folder is known
    -- to be writable) before anything is reported.
    local flushed_ok = self:_flush_from_game()
    if flushed_ok then
        print(string.format(
            "[GroundedArchipelago] from_game.json created/refreshed at %s\n", self.from_game_path
        ))
    else
        print(string.format(
            "[GroundedArchipelago] WARNING: could not write from_game.json to '%s' -- check the folder is " ..
            "writable and that no antivirus/OneDrive lock has it open.\n", self.from_game_path
        ))
    end

    return self
end

-- ---------------------------------------------------------------------
-- Low-level atomic file helpers
-- ---------------------------------------------------------------------

local function read_file(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local contents = f:read("*a")
    f:close()
    return contents
end

local function write_file_atomic(path, contents)
    local tmp_path = path .. ".tmp"
    local f, err = io.open(tmp_path, "w")
    if not f then
        return false, err
    end
    f:write(contents)
    f:close()

    local ok, rename_err = os.rename(tmp_path, path)
    if ok then
        return true
    end

    -- On Windows os.rename fails if the target exists: remove and retry.
    -- Briefly no file at `path` -- readers tolerate that.
    os.remove(path)
    local ok2, rename_err2 = os.rename(tmp_path, path)
    if not ok2 then
        return false, rename_err2 or rename_err
    end
    return true
end

-- ---------------------------------------------------------------------
-- Local persisted state (survives a game/mod restart mid-session)
-- ---------------------------------------------------------------------

function ipc:_load_state()
    local raw = read_file(self.state_path)
    if not raw then return end
    local data = json.decode(raw)
    if not data then return end
    self.applied_item_index = data.applied_item_index or -1
    self.applied_tier1_unlock = data.applied_tier1_unlock or false
    self.goal_complete = data.goal_complete or false
    self.ending_pending = data.ending_pending or false
    self.room_key = data.room_key
    self.last_notification_id = data.last_notification_id or 0
    for _, name in ipairs(data.checked_locations or {}) do
        self.checked_locations[name] = true
    end

    -- Logged loudly: these are re-sent on load. If one wasn't really
    -- checked, remove it from applied_state.json (or delete the file).
    local loaded_count = 0
    for _ in pairs(self.checked_locations) do
        loaded_count = loaded_count + 1
    end
    if loaded_count > 0 then
        local names = {}
        for name in pairs(self.checked_locations) do
            names[#names + 1] = name
        end
        print(string.format(
            "[GroundedArchipelago] Loaded %d previously-checked location(s) from %s: %s\n",
            loaded_count, self.state_path, table.concat(names, ", ")
        ))
    end
end

function ipc:_save_state()
    local checked_list = {}
    for name in pairs(self.checked_locations) do
        checked_list[#checked_list + 1] = name
    end
    local ok, err = write_file_atomic(self.state_path, json.encode({
        applied_item_index = self.applied_item_index,
        applied_tier1_unlock = self.applied_tier1_unlock,
        goal_complete = self.goal_complete,
        ending_pending = self.ending_pending,
        room_key = self.room_key,
        last_notification_id = self.last_notification_id,
        checked_locations = checked_list,
    }))
    if not ok then
        print(string.format(
            "[GroundedArchipelago] WARNING: failed to write applied_state.json: %s\n", tostring(err)
        ))
    end
    return ok
end

-- ---------------------------------------------------------------------
-- Reading from the connector
-- ---------------------------------------------------------------------

-- New {index, name, ...} items not applied yet. Doesn't change state: call
-- ipc:mark_item_applied() after handling each, so a crash loses nothing.
function ipc:poll()
    local raw = read_file(self.to_game_path)
    if not raw then
        return { new_items = {}, connected = false, slot = nil }
    end
    local data = json.decode(raw)
    if not data then
        return { new_items = {}, connected = false, slot = nil }
    end

    self:_sync_room(data)

    local new_items = {}
    local item_counts = {} -- name -> copies received so far (applied or not)
    for _, entry in ipairs(data.received_items or {}) do
        if entry.index > self.applied_item_index then
            new_items[#new_items + 1] = entry
        end
        item_counts[entry.name] = (item_counts[entry.name] or 0) + 1
    end
    table.sort(new_items, function(a, b) return a.index < b.index end)

    -- to_game.json is only rewritten on events, so its "connected" goes
    -- stale when the client closes; the client's heartbeat says whether it
    -- is actually running (and connected) right now.
    local heartbeat = json.decode(read_file(self.dir .. "/client_heartbeat.json") or "") or {}
    local alive = type(heartbeat.time) == "number" and math.abs(os.time() - heartbeat.time) < HEARTBEAT_STALE_SECONDS

    return {
        new_items = new_items,
        item_counts = item_counts,
        received_items = data.received_items or {},
        resync_seq = data.resync_seq or 0,
        connected = data.connected or false,
        client_connected = alive and heartbeat.connected == true,
        slot = data.slot,
        goal = data.goal,
        gold_card_drop_chance = data.gold_card_drop_chance or 0,
        gold_card_goal_amount = data.gold_card_goal_amount or 65,
        start_with_tier1_recipes = data.start_with_tier1_recipes,
        excluded_bosses = data.excluded_bosses or {},
        recipe_shuffle = data.recipe_shuffle or {},
        recipe_cost_multiplier = data.recipe_cost_multiplier or 100,
        progressive_molar_upgrades = data.progressive_molar_upgrades == true,
        gear_perks = data.gear_perks or 0,
        compass = data.compass == true,
        region_locks = data.region_locks == true,
        shop_checks = data.shop_checks == true,
        creature_drop_shuffle = data.creature_drop_shuffle or {},
        notifications = data.notifications or {},
        death_link = data.death_link or false,
        death_link_seq = data.death_link_seq or 0,
        death_link_message = data.death_link_message or "",
        -- The client draws its own notification cards over the game
        -- (overlay.py); the mod then keeps AP messages out of the HUD.
        overlay_notifications = data.overlay_notifications == true,
    }
end

-- Scopes local state to the connected room: a different room (or a saved
-- state without one) resets checks and the applied-item index. Then every
-- location the server already has is merged in -- the server is the source
-- of truth.
function ipc:_sync_room(data)
    local room = data.room_key
    if not room then
        return -- connector hasn't connected yet / old connector
    end
    local changed = false
    if self.room_key ~= room then
        print(string.format(
            "[GroundedArchipelago] AP room changed (%s -> %s): resetting saved checks and applied items\n",
            tostring(self.room_key), room
        ))
        self.checked_locations = {}
        self.goal_complete = false
        self.ending_pending = false
        self.applied_item_index = -1
        self.room_key = room
        changed = true
    end
    for _, name in ipairs(data.server_checked_locations or {}) do
        if not self.checked_locations[name] then
            self.checked_locations[name] = true
            changed = true
        end
    end
    if changed then
        self:_save_state()
        self:_flush_from_game()
    end
end

function ipc:mark_item_applied(index)
    if index > self.applied_item_index then
        self.applied_item_index = index
        self:_save_state()
    end
end

function ipc:set_ending_pending(pending)
    self.ending_pending = pending
    self:_save_state()
end

function ipc:mark_notification_shown(id)
    if id > self.last_notification_id then
        self.last_notification_id = id
        self:_save_state()
    end
end

function ipc:report_death()
    self.death_seq = self.death_seq + 1
    self:_flush_from_game()
end

function ipc:mark_tier1_unlock_applied()
    self.applied_tier1_unlock = true
    self:_save_state()
end

-- ---------------------------------------------------------------------
-- Writing to the connector
-- ---------------------------------------------------------------------

-- Idempotent. True if the location is (now) checked, false if ignored
-- because we're not in the Archipelago world -- latching callers retry.
function ipc:report_location(name)
    -- Test mode (see test_mode.lua / config.lua): every detection is
    -- logged to test_checks.log, and with send_checks off nothing is sent
    -- or marked checked, so the same check can be triggered again later.
    local test = self.test_mode
    if self.checked_locations[name] then
        if test then
            test.log_check(name, "detected (already checked in this room)")
        end
        return true
    end
    if test and not test.send_checks then
        test.log_check(name, "detected (test mode: NOT sent)")
        return true
    end
    if not self.reporting_enabled then
        if test then
            test.log_check(name, "detected outside the Archipelago world: NOT sent")
        end
        self._ignored_logged = self._ignored_logged or {}
        if not self._ignored_logged[name] then
            self._ignored_logged[name] = true
            print(string.format("[GroundedArchipelago] Ignored check '%s' -- not in the Archipelago world\n", name))
        end
        return false
    end
    self.checked_locations[name] = true
    print(string.format("[GroundedArchipelago] REPORTED (new this session): %s\n", name))
    if test then
        test.log_check(name, "NEW: sent")
    end
    self:_flush_from_game()
    self:_save_state()
    if self.on_location_reported then
        local ok, err = pcall(self.on_location_reported, self)
        if not ok then
            print(string.format("[GroundedArchipelago] on_location_reported callback errored: %s\n", tostring(err)))
        end
    end
    return true
end

function ipc:report_goal_complete()
    if self.goal_complete then return end
    self.goal_complete = true
    self:_flush_from_game()
    self:_save_state()
end

function ipc:_flush_from_game()
    local checked_list = {}
    for name in pairs(self.checked_locations) do
        checked_list[#checked_list + 1] = name
    end
    table.sort(checked_list) -- stable output, so unchanged state compares equal below
    local contents = json.encode({
        checked_locations = checked_list,
        goal_complete = self.goal_complete,
        -- The client only sends these if this matches its own room, so a
        -- stale file from another room can never leak checks into it.
        room_key = self.room_key,
        -- Save binding (see client.py), set by location_hooks.lua.
        world_name = self.world_name,
        world_code = self.world_code,
        recipe_slots = self.recipe_slots,
        death_seq = self.death_seq,
        -- The client warns if this isn't its apworld's version.
        mod_version = self.mod_version,
    })
    -- main.lua calls this every poll tick; only touch the disk when
    -- something actually changed (a write+rename every second on the game
    -- thread is a hitch, especially with antivirus/OneDrive watching).
    if contents == self._last_from_game then
        return true
    end
    local ok, err = write_file_atomic(self.from_game_path, contents)
    if ok then
        self._last_from_game = contents
    end
    if not ok then
        print(string.format(
            "[GroundedArchipelago] WARNING: failed to write from_game.json: %s\n", tostring(err)
        ))
    end
    return ok
end

return ipc
