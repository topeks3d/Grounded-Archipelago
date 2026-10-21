# Development notes

The project's original README: status updates and investigation notes from
building the mod (UE4SS dumps, hook experiments), kept for reference. Some of
it is out of date -- see README.md and TESTING.md for the current state.

## Status

**Working and tested:**
- The Archipelago world (`apworld/grounded`) generates valid seeds and
  passes Archipelago's own generic world test suite (50 tests / 872
  subtests, run against a real Archipelago checkout).
- The game-side IPC layer (`game_mod/GroundedArchipelago/Scripts/ap_ipc.lua`
  + `ap_json.lua`) has its own test suite covering the JSON round trip and a
  simulated mid-session restart, run under a real Lua 5.4 interpreter.
- The full network path has been run end-to-end against a real, locally
  hosted Archipelago server, through **both** supported invocation
  paths -- the standalone `connector/grounded_connector.py` script and
  `Launcher.py "Grounded Client"` (the same mechanism
  `ArchipelagoLauncher.exe "Grounded Client"` uses against a compiled
  install): connecting, receiving `slot_data` and previously-earned items,
  sending a location check, receiving the resulting item back, and
  reporting goal completion all round-tripped successfully.
- The client is registered as an Archipelago Launcher Component
  (`apworld/grounded/client.py` + the registration in `__init__.py`), which
  is what makes it work against the compiled Windows installer at all --
  that install layout doesn't expose `CommonClient.py` as loose, importable
  source the way a source checkout does, so a plain standalone script can't
  reach it. This was a real bug in an earlier version of this project,
  found by an actual user hitting it -- see `connector/README.md`'s "Two
  ways to install Archipelago" for the full story.

**Update from a real UE4SS level actor dump (a CSV of placed actors, not a
function/property dump):** confirmed real class paths for the player
character (`BP_SurvivalPlayerCharacter_Female02_C`, under
`/Game/Blueprints/Player/` -- the old `BP_PlayerCharacter_C` guess didn't
exist anywhere in the game), several boss managers, and a
`BP_LabPOITrigger_C` under an actual `Quests` folder. Also found: this
mod's original bug (`from_game.json` never being created) was independent
of any of that -- `ap_ipc.lua` only flushed that file on the *first*
successful location/death/goal report, and with every hook still a
placeholder, that first report never happened. Fixed by flushing once,
unconditionally, at mod load.

**Update from a full UE4SS C++ header dump (the real SDK-generation
feature -- one `.hpp` per class with actual function signatures, not just
placement):** this is what an actor dump can't give you, and it resolved
several of the above from "real class, guessed function" to fully
confirmed:
- Player death: `HandleDeath()` -- a real, zero-argument function on the
  *base* `BP_SurvivalPlayerCharacter_C` (`":OnDeath"` never existed). All
  four character skins (Female, Female02, Male02, Gellarde) turned out to
  be completely empty subclasses, so hooking the base class covers every
  skin with one hook, and `item_grants.lua`'s player-lookup list now has
  all four confirmed real class names instead of one plus a guess.
- Infected Broodmother: superseded by a better find (see the next update
  below) -- `BP_BossManager_IBM_C:OnDeactivated` is still real, but no
  longer what's wired in for her.
- The Black Anthill boss (`BP_BAH_BossStateManager_C`) has a real
  `ConditionalToggle_BossDead` component field of type
  `UConditionalToggleComponent`, which has a real `IsEnabled()` getter --
  turned the dead-end "Defeat the Broodmother" poll placeholder into an
  actual implementation. The semantic assumption (toggle enabled == boss
  dead) is inferred from the field's name, not independently proven.
- Wasp Queen's own manager class does *not* override `OnDeactivated` --
  it shares the base class implementation, so there's no Wasp-Queen-
  specific function to point a hook at without also disambiguating by
  instance class at runtime. Deliberately left unwired rather than risk
  misattributing another boss's kill to her.
- `BQOption`/`BQ_Kill*` quests all inherit a real
  `HandleActorKilledWithAttack(AActor*, FDamageInfo&)` function and a
  `CreatureTag` field from the native `UBurgleQuest2Kill`. Not wired in
  yet -- documented in `location_hooks.lua` as an alternative to the
  ULootComponent approach below, in case that one doesn't pan out.
- `BP_LabPOITrigger_C` has a real `OnTrigger(AActor*, AActor*)` function
  -- an ordinary trigger-box overlap event. Needs object unwrapping,
  same as above.
- "Story: Meet BURG.L" and the ending sequence are still exactly as
  unresolved as before -- neither dump had anything to say about them.

**Update from the same C++ header dump, a second pass specifically on
kill detection:** `ULootComponent` -- a native component attached to
essentially every lootable creature in the game -- has its own
`OnDeath(const FDamageInfo&)` function. Unlike `OnDeactivated`/
`BossActivateDelegate` earlier, `OnDeath` is never a shared/reused
delegate-handler name in the dump -- it's its own distinct function on
ten different classes, the same per-class-own-function shape that made
the confirmed-working player `HandleDeath` hook work. `location_hooks.lua`
now hooks this once, universally, instead of one guess per boss:
- Infected Broodmother is identified via a plain, directly-readable
  `Context.bIsInfectedBroodmother` bool on the same component -- no class
  lookup needed, the strongest-grounded boss-kill signal in this file.
- Every other creature: the code also attempts `Context:GetOuter()` (the
  owning creature Actor) then `:GetClass():GetFullName()` on that, the
  same technique `diagnose.lua` already uses elsewhere -- but `GetOuter()`
  hasn't been used anywhere else in this codebase, and no creature *pawn*
  class name has been confirmed for any other boss (the actor dump only
  ever caught boss *manager* classes, which are a different actor from
  the creature itself). `CREATURE_CLASS_TO_LOCATION` in
  `location_hooks.lua` is deliberately empty until one is.
- This is also the first attempt anywhere in this project at a native
  (`/Script/...`) hook path rather than a Blueprint (`/Game/...`) one --
  every hook that has actually registered in a real game so far has been
  a Blueprint path, so whether a native path registers at all in this
  build is itself untested, on top of whether `OnDeath` fires the way its
  name suggests.

**Update from a real playtest with the native hook registered:** confirmed
the native `/Script/...` hook path *does* register (it registered
immediately at mod load, before the save even finished loading -- native
classes are resident from engine start, unlike Blueprint classes, which
only register once their asset loads). But the same session showed two
real bugs, not fixed by getting that far:
- "Defeat the Broodmother" and "Defeat the Infected Broodmother" were
  both reported instantly, with neither boss actually killed that
  session. Root cause almost certainly isn't a live false-positive in
  either hook -- `ap_ipc.lua`'s `_load_state()` silently loaded
  `checked_locations` from a previous session's `applied_state.json`
  with zero logging, and the unconditional startup flush (see the very
  first Status update above) re-reports anything already marked checked
  the instant the mod loads, indistinguishable from a fresh in-session
  check. Both `_load_state()` and `report_location()` now log loudly
  (loaded-from-disk vs. reported-fresh-this-session), so this is fully
  diagnosable the next time it happens instead of a guess.
- Item granting was stuck retrying forever ("no live item DataTable
  reference captured this session") because the design required a real
  pickup to happen first to capture a DataTable reference, and the
  playtest never picked anything up. Fixed by finding
  `UGlobalTableData::AllItemsTable` in the header dump -- a persistent
  config object (not something that needs a pickup to exist) that very
  likely holds the same master item table pickups already reference.
  `item_grants.lua` now tries this first, falls back to a pickup-captured
  table, and only warns (once) if neither is available.
- The creature-death hook now also logs on *every* death, matched or
  not -- printing the resolved creature class name -- so confirming the
  hook works at all no longer requires killing (or re-killing) a specific
  boss; any regular creature kill shows up in the log immediately.

**Not yet possible to verify from here:**
- Whether `OnDeath`/`ConditionalToggle_BossDead` actually mean what
  their names suggest, in practice, at the moment of a real kill -- a
  header dump proves a function or property *exists*, not what triggers
  it or what it's used for. Needs an actual in-game kill to confirm
  (native hook *registration* is now confirmed working, per the update
  just above -- what's still open is only the semantic trigger).
- The real UFunction behind "Story: Meet BURG.L" and the ending. Quest-
  completion logic appears to live on components this project hasn't
  been able to fully trace from either dump.
- Wolf Spider, Black Widow, Orb Weaver, and Ricky have no confirmed boss-
  manager class yet -- not because they don't exist, but because neither
  dump was taken while standing in their arenas. Re-dump while standing
  in each zone to fill these in the same way the others were found.
- Whether `RegisterHook` is currently reliable in Grounded at all -- there's
  a standing UE4SS issue about this (RE-UE4SS#626, filed Aug 2024); check
  its current status before betting the whole design on hooks working. The
  Lua mod supports a polling-based fallback for exactly this reason.
- The specific in-game content (which BURG.L chip is which, boss names,
  item names) is drawn from public wiki research, not a live data dump. Core
  facts are well corroborated; anything from post-launch DLC is flagged
  `TODO: verify` and should be checked against the current game version.

See `ARCHITECTURE.md` for the full design and exactly what's real vs. a
placeholder, file by file.

## Layout

```
apworld/grounded/       -- the Archipelago world (Python) -- generation, logic, options, and client.py (the network client, registered as a Launcher Component)
game_mod/GroundedArchipelago/ -- the UE4SS Lua mod that runs inside Grounded.exe
connector/               -- thin standalone wrapper for running the client from a source checkout without the Launcher, plus the generator tools (grounded_data.py + the mod's ap_data.lua, and the PopTracker pack)
tracker/grounded_poptracker/ -- generated PopTracker pack (connector/tools/generate_poptracker_pack.py)
ARCHITECTURE.md          -- why this is two processes, and the IPC contract between them
```

## Quick start

See `apworld/grounded/docs/setup_en.md` for the full install/run guide. In
short:

1. Install `apworld/grounded` into your Archipelago setup -- as a
   `grounded.apworld` in `custom_worlds\` if you use the compiled Windows
   installer, or copied into `worlds/` if you run from a source checkout.
2. Generate/host a seed the normal Archipelago way.
3. Drop `game_mod/GroundedArchipelago` into UE4SS's `Mods/` folder for your
   Grounded install, and enable it. Also enable UE4SS's own built-in
   `ConsoleEnablerMod` and `CheatManagerEnablerMod` in `Mods/mods.txt` (or
   `mods.json`) if they aren't already -- item granting (`GiveItem`) and
   recipe unlocking (`UnlockRecipe`) both work by invoking Grounded's own
   developer console commands, which need these enabled to exist at all.
4. Run the "Grounded Client" -- from the Archipelago Launcher GUI directly
   (it now auto-detects a standard Steam install; see `connector/README.md`
   if that fails and you need to pass `--ipc-dir` manually) -- and just
   type your server address into the client window that opens, the same
   as any other Archipelago client.

## Where to pick this up next

**Start with [TESTING.md](TESTING.md)** -- the checklist of everything that
still needs confirming in the real game, with the log lines to look for.

Roughly in order of what unblocks the most:

1. **Do an actual in-game smoke test of what's now wired in**: run the
   connector, actually die once (confirms `HandleDeath`), and kill any
   creature with a loot component (confirms `ULootComponent:OnDeath`
   fires and that a native `/Script/...` hook path can register at all),
   ideally the Infected Broodmother specifically (also confirms
   `bIsInfectedBroodmother`) and the Black Anthill boss if reachable
   (confirms `ConditionalToggle_BossDead`). This is now the highest-value
   next step -- everything below it is either already-confirmed-by-dump
   or a bigger lift.
2. **Get a creature *pawn* class name for at least one more boss** (Wasp
   Queen, Mantis, Black Widow, Wolf Spider, Orb Weaver, or the regular
   Broodmother) by dumping actors while actually fighting one, then add
   it to `location_hooks.lua`'s `CREATURE_CLASS_TO_LOCATION` -- this
   immediately extends the same `ULootComponent:OnDeath` hook to cover
   that boss too, no new hook needed.
3. **Wire in `UBurgleQuest2Kill::HandleActorKilledWithAttack`** -- see the
   Status section above. This is the best-supported path to one hook that
   covers every boss (including Wolf Spider, Black Widow, Orb Weaver,
   Mantis, which have no dedicated manager class at all), but needs the
   object/struct-unwrapping `location_hooks.lua` has held off on so far.
   Confirming the hooks in step 1 work at all is worth doing first, since
   this is a bigger lift built on the same RegisterHook mechanism.
4. Re-dump (either kind) while standing in the Wolf Spider, Black Widow,
   Orb Weaver, and Ricky arenas specifically -- neither existing dump was
   taken there, so those bosses have no confirmed manager class yet.
5. "Story: Meet BURG.L" and the ending sequence remain fully unresolved --
   neither dump surfaced anything for either. May need a targeted dump
   taken at the exact moment of that cutscene/quest completion, or
   tracing the quest system's `UBaseQuest`/`NotifyQuestComplete` path by
   hand.
6. Check whether RE-UE4SS#626 is resolved on the UE4SS version you're
   targeting; if `RegisterHook` still doesn't fire reliably in Grounded,
   lean on the polling style instead (already the pattern for the Black
   Anthill boss).
7. Expand/verify the location and item lists in `apworld/grounded/items.py`
   and `locations.py` against the real game -- the current set is an
   intentionally modest v0.1 draft, not a claim of full coverage.
