# Architecture

Grounded is closed-source and its scripting layer (UE4SS Lua) most likely
can't open real network sockets on its own. So instead of one client, this
mod is two cooperating pieces:

```
 Archipelago server  <--WebSocket-->  apworld/grounded/client.py  <--local files-->  game_mod (UE4SS Lua, runs inside Grounded.exe)
```

1. **`apworld/grounded/client.py`** -- a normal Python program, built on
   Archipelago's own `CommonClient`. It does everything network-related:
   logging into the room, receiving items, sending `LocationChecks`,
   DeathLink, etc. It has no idea how Grounded's internals work. It lives
   inside the apworld package (rather than as a standalone script) and is
   registered as an Archipelago Launcher Component in `__init__.py`, so it
   runs via `ArchipelagoLauncher.exe "Grounded Client"` (or
   `python Launcher.py "Grounded Client"` from source) using whatever
   Archipelago environment is already loaded. `connector/grounded_connector.py`
   is a thin standalone wrapper around the same code for people running a
   source checkout who'd rather not go through the Launcher -- see
   `connector/README.md` for why the Launcher route is the one that also
   works against the compiled Windows installer.
2. **`game_mod/GroundedArchipelago`** -- a UE4SS Lua mod that runs inside the
   game process. It has no idea what a WebSocket is. All it knows how to do
   is (a) notice when the player does something that matches a location on
   the AP location list, and (b) apply an item's effect when told to.
3. The two talk over a **local IPC folder** of small JSON files that the
   connector and the Lua mod both read/write on disk. This only needs Lua's
   stock `io`/`os` libraries -- no native extensions, no sockets, nothing
   that has to be verified against a specific UE4SS build.

This mirrors how several existing Archipelago integrations handle
similarly "hard to hook directly" games (an external process owns the
network connection, an in-process script owns game state).

## IPC folder

Default: `<Grounded install>/Maps/../Binaries/Win64/ue4ss/Mods/GroundedArchipelago/ipc/`
(the mod computes this relative to its own script path at load time; see
`ap_ipc.lua`). The connector is told the same path via `--ipc-dir` (or a
config file) and must point at the identical folder.

Both sides poll roughly once a second. That's plenty fast for a survival
game -- nothing here is frame-critical.

### `to_game.json` (connector writes, mod reads)

```json
{
  "connected": true,
  "slot": "YourSlotName",
  "room_key": "<seed>:<slot>",
  "goal": 0,
  "received_items": [
    { "index": 0, "name": "Gas Mask", "copy": 1, "sender": "" },
    { "index": 1, "name": "Progressive Axe", "copy": 2, "sender": "Bob" }
  ],
  "server_checked_locations": ["Item: Sap"],
  "recipe_shuffle": { "AxeTier2": [["AntPart", 3], ["Sap", 4]] },
  "notifications": [{ "id": 1790000001, "text": "Sent Insect Axe to Bob" }],
  "death_link": true,
  "death_link_seq": 0,
  "death_link_message": ""
}
```

* `received_items` is the **full history**, in server order, not a delta.
  The mod keeps a small persisted counter (`ipc/applied_state.json`, written
  by the mod itself) of how many it has already applied, and only acts on
  entries past that point. Replaying the whole list each time means a game
  or connector restart can't cause a missed item -- worst case an item gets
  re-applied, which every item effect in `item_grants.lua` is written to
  tolerate (granting a blueprint you already have is a no-op, not an error).
  `copy` is which copy of that item this is (progressive gear); `sender` is
  who found it ("" = yourself), for the on-screen message. Items are only
  applied inside the Archipelago world (see `world_gate.lua`).
* `recipe_shuffle` is slot_data's RecipeShuffle table (see
  `recipe_shuffle.lua`); empty = vanilla recipes.
* `notifications` is the client's last 30 on-screen messages (sent items,
  hints). The mod shows ids above the last one it showed (persisted).
* `death_link_seq` increments every time someone else's DeathLink death
  should be applied to this player. The mod only acts on increases it sees
  while in the Archipelago world (see `deathlink.lua`).

### `from_game.json` (mod writes, connector reads)

```json
{
  "checked_locations": ["Item: Sap", "BURG.L Chip: Oak Tree"],
  "goal_complete": false,
  "room_key": "<seed>:<slot>",
  "world_name": "archipelago",
  "world_code": "30EC",
  "recipe_slots": { "AxeTier2": 3 },
  "death_seq": 0
}
```

* `checked_locations` is also the full history of everything checked so far
  this session (location **names**, not ids -- the connector resolves names
  to ids using the data package it gets from the server after connecting, so
  the Lua side never needs to know about numeric ids or this world's
  `item_base_id`/offset scheme at all).
* `death_seq` increments on each local death, for DeathLink (not for the
  death a received DeathLink causes). In memory only -- the client treats a
  lower value as a game restart.
* `recipe_slots` is how many ingredients each shuffled recipe really has,
  so the client's Tracker shows exactly the slots the game uses.
* `goal_complete` is set true once the mod detects the configured goal
  (ending cutscene for "embiggening", or all tracked bosses dead for
  "boss_sweep").

### Writes are atomic

Both sides write to `<file>.tmp` then `os.rename()` over the real filename.
Lua's stock `os.rename` is enough for this -- no extra library needed. This
avoids the connector or the mod ever reading a half-written file.

## What's real vs. a placeholder right now

* The IPC layer, the connector, and the apworld are fully implemented and
  (for the apworld) tested against a real Archipelago install.
* The **hook points** in `game_mod/GroundedArchipelago/Scripts/location_hooks.lua`
  (which UFunction fires when a BURG.L chip is picked up, a quest completes,
  a boss dies, etc.) are written as a clear, data-driven registration
  pattern with one worked example, but the exact class/function names are
  marked `-- TODO: verify` -- they need to be confirmed against a live
  UE4SS object dump of the actual game, which requires owning/running the
  game on Windows with UE4SS installed. I don't have that environment
  available to me, so I could not verify them myself.
* Likewise `item_grants.lua`'s actual "give this item to the player" calls
  are stubbed with the pattern to follow, not real UFunction calls.

See the top of each Lua file for exactly what to fill in.
