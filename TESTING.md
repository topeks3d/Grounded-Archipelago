# In-game testing checklist

Everything below is built from the game's header/data dumps and passes the
automated tests (apworld tests plus a stubbed-UE4SS simulation of the Lua
mod), but **none of it has run in the real game yet**. Each item says what
to do, what you should see, and which log lines prove it worked.

All log lines start with `[GroundedArchipelago]` and are in
`Grounded/Maine/Binaries/Win64/ue4ss/UE4SS.log`. When something fails, the
most useful thing to send back is that log.

## Setup

1. Copy `game_mod/GroundedArchipelago` into `ue4ss/Mods/` (replace the old
   folder -- several new files were added).
2. Install the updated `apworld/grounded` and generate a test seed. A good
   test YAML turns everything on:

   ```yaml
   name: Tester
   game: Grounded
   Grounded:
     goal: embiggening
     recipe_shuffle: true
     creature_drop_shuffle: true
     progressive_gear: true
     mutation_checks: true
     death_link: true
   ```

   For DeathLink and the "Sent ..." / hint messages you need a second slot
   in the room (any game, or a second Grounded slot) that you can
   `!admin`-send items from or die in.
3. Start the Grounded Client and connect.
4. In Grounded, create a **new** world named `archipelago`.

Tip: the `CheatManagerEnablerMod` is already required, so the game's own
console commands (`GiveItem`, `AddScience`, ...) are available to speed up
getting to later tests.

---

## 0. Test mode (try options without a new room)

In `Scripts/config.lua` (the installed copy), set `config.test_mode.enabled
= true` and fill in any `overrides` (e.g. `creature_drop_shuffle = true`).
Restart the game. Then:

| Step | Expect |
|---|---|
| Load any world | `TEST MODE ON: overrides ...` in the UE4SS log; shuffles log `TEST MODE: built local ...`. |
| Do anything that's a check (pick up Sap, craft, kill a boss, ...) | A line in `ipc/test_checks.log` -- `detected (test mode: NOT sent)`, or `already checked in this room` for ones sent before. |
| `send_checks = true` | Checks are sent normally too, and logged as `NEW: sent`. |

Checks renamed in `location_renames.py` show both names in the log, e.g.
`Kill: Mantis (AP: Kill: Praying Mantis)`.

Change `seed` for a different local shuffle. Set `enabled = false` again
before playing a real seed.

## 0b. Landmarks (Landmark Checks option)

Generate with `landmark_checks: true` to get them as real checks; with it
off they still show on the client's Tracker > Map tab.

| Step | Expect |
|---|---|
| Load a world with landmarks already discovered | `Landmarks discovered in this world: N`, then one `LANDMARK: POI_... \| name=... \| category=... \| reward=...` line each. Those already-found ones are sent as checks once connected. |
| Discover a new landmark | Within a second: a new `LANDMARK:` line, `REPORTED ... Landmark: POI_...`, the check arrives on the server under its readable name (e.g. "Landmark: Ashtray"), and it turns green on the Tracker's Map tab. |
| Compare the logged `name=` with the readable name in `location_review.txt` | If they differ, fix the `=>` name (and move the line if its biome is wrong). |

Watch for: `Couldn't read PlayerState.DiscoveredPointsOfInterest` (then
the fallback is hooking `UPartyComponent:DiscoverPointOfInterestData`), or
`name=?` (display names unreadable -- names would come from the asset).

## 1. World gate (the main-menu fix)

| Step | Expect |
|---|---|
| Connect the client while on the main menu, with items waiting | Log: `Not in a world (main menu / loading) -- holding received items...`. **No** `Issued:` lines. |
| Load a world with a different name | Log: `World '<name>' is loaded, but Archipelago only runs in a world named 'archipelago'...`. Still no `Issued:` lines; pickups log `Ignored check ...`. |
| Load the `archipelago` world | `World 'archipelago' loading -- waiting for the player to spawn.`, then ~3 s after spawning `In Archipelago world 'archipelago'...` followed by `Issued:` lines. The items are actually in your game. |
| Quit to menu, reload the world | Brainpower/category unlocks run again; nothing is granted twice. |

If the world is never recognised: check the `World '...'` line for the
name the game reports. Joining someone else's game as a client may not
report a name -- set `config.required_world_name = nil` in
`Scripts/config.lua` for that case, and please note whether it was needed.

## 2. Recipe Shuffle

| Step | Expect |
|---|---|
| Load in with `recipe_shuffle: true` | One `RECIPE_SHUFFLE: <row> -> ...` line per Tier 2/3 gear recipe, then `RECIPE_SHUFFLE: rewrote N recipe(s)` with no `failed`. |
| Receive e.g. Insect Axe (or a 2nd Progressive Axe) and open the crafting menu | The recipe shows the **new** ingredients from the log (not vanilla). |
| Craft it with the new ingredients | The new ingredients are consumed; crafting with the vanilla ones is impossible. |
| Client Tracker: click the craft check (e.g. Insect Axe) | The popup's "Recipe (shuffled)" lists the same ingredients as the crafting menu, same count of slots. |
| Tier 1 recipes (e.g. Pebblet Axe) | Unchanged vanilla costs. |

Watch for: the menu showing vanilla costs while the log says rewritten
(the UI may cache recipes -- try reopening the menu / reloading), or
`couldn't rewrite '<row>'` lines.

## 2b. Creature Drop Shuffle

| Step | Expect |
|---|---|
| Client Tracker: click an item check that's a creature part (e.g. Red Ant Part) | "Where to find it" names the creatures that drop it this seed. |
| Kill a creature whose drops are listed (e.g. a Red Worker Ant) | After `Creature death seen: ...`, a `DROP_SHUFFLE: AntPart->..., ...` line. |
| Harvest the corpse | You get the **new** materials the Tracker lists, not the vanilla ones. |
| Kill creatures with `gold_card_drop_chance: 50` | Each still drops **its own** gold card (e.g. Red Worker Ant -> Red Worker Ant card). |

Watch for: `didn't stick (read back ...)` or `drop_shuffle.apply failed`
lines, or corpses still giving vanilla parts while the log says rewritten
(that would mean the loot is rolled before OnDeath).

## 3. On-screen messages

| Step | Expect |
|---|---|
| Receive an item from another slot | On screen: `Received <item> from <player>`. Log: `NOTIFY: ...`. |
| Receive your own item (found in your world) | `Found your <item>`. |
| Find another slot's item in your world | `Sent <item> to <player>`. |
| From another slot, `!hint` one of your items | `Hint: Your <item> is at <location> (<player>'s world)`. |
| Connect with 5+ items waiting | One summary line (`Received N items from the multiworld`) instead of a flood. |

If only the `NOTIFY:` log lines appear and nothing shows on screen, look for
`Couldn't show on-screen messages (GameUI:PostGenericMessage failed...)`.

## 3b. Notification cards (overlay)

Set Grounded to **Windowed** or **Borderless** -- the cards are drawn by the
Grounded Client on top of the game, and can't show over exclusive Fullscreen.

| Step | Expect |
|---|---|
| Connect the client | A green "You have connected." card at the left of the game window. |
| Receive an item | A card: coloured bar + "[Progression] Insect Axe" (Useful / Filler / Trap by the item's class), the item's icon, and "from Bob (Celeste)  ·  <their location>" (or "from your world  ·  <your check>"). The HUD itself shows nothing for it. |
| Send a check for someone else | "[Filler] Moon Boots", "to Bob (Celeste)  ·  <your check>", with the checked item's icon. |
| Several at once | Up to five stacked; each slides in, stays ~5 s, fades, and the rest move up. |
| Clicking / playing while a card is up | The game keeps focus and input -- cards are click-through. |
| `/overlay` in the client | Turns the cards off (remembered); messages then go to the game's notification feed instead. |

The game's own key-item banner is still there, off: `config.notification_style
= "banner"` in config.lua turns it back on (3 s each, `config.banner_seconds`,
with the checked item's icon). `"feed"` uses only the small feed lines.

## 4. Received items: progressive gear and filler

| Step | Expect |
|---|---|
| 1st / 2nd / 3rd Progressive Axe | Pebblet Axe, then Insect Axe, then Termite Axe recipes unlock (`Issued: UnlockRecipe Axe`, `...AxeTier2`, ...). |
| Progressive Head Armor copies | Clover -> Acorn -> Grub -> Bee -> Ladybug -> Red Ant -> Black Ant -> Spider -> Roly Poly -> Antlion -> Black Ox -> Mantis. |
| Full Restore | Health, food, water, stamina refill (`Issued: FullRestore`). |
| Resource bundles (Plant Fiber, Sprig, Pebblet, Sap, Grass Plank, Crude Rope, Bandage) | Items appear in the inventory (`Issued: GiveItem <row> <n>`). |
| After a Bandage / Grass Plank bundle | **No** `REPORTED ... Item: Grass Plank` / `Craft: Bandage` from the bundle itself. |

Removed items (Multi-Story Bases, Fortified Bases, SCA.B Scanner Upgrade,
Torch Upgrade, Tier 4 Weapons/Armor, both Resistance Charms, SPAC.R
Embiggening Cell) should never appear in a new seed.

## 5. DeathLink

| Step | Expect |
|---|---|
| Load in | `Hook registered: player death (HandleDeath)`. |
| Die | `DeathLink: local death (#1)`; the client logs `DeathLink: Sending death to your friends...`; the other slot dies. |
| Other slot dies | On screen `DeathLink: <cause>`, log `DeathLink: received -- issued TryKill`, and you actually die. |
| The death that DeathLink caused | `DeathLink: local death caused by a received DeathLink -- not sending it back out` (no ping-pong). |
| Co-op: another player on your world dies | Nothing is sent (only your own character counts). |

If you don't die: `TryKill` may need a target or behave differently --
note what the log says after `issued TryKill`.

## 6. Boss kill detection

Six bosses got real class names from the bestiary dump (previously
undetected). Kill each and check for `Creature death seen: <class>` followed
by `REPORTED ... Kill: <boss>`:

| Boss | Expected class in the log |
|---|---|
| Assistant Manager | `BP_ArcR_MKII_C` (confirmed by a real kill, 2026-10-03) |
| Hedge Broodmother | `BP_Spider_Boss_Hedge_C` |
| Mant | `BP_Mant_C` |
| Mantis | `BP_Mantis_C` |
| Director Schmector | `BP_Ominent_Robot_C` |
| Wasp Queen | `BP_Wicklow_C` |

If a kill logs a different class (or no `Creature death seen` at all),
send that line -- the fix is one line in `location_hooks.lua`'s
`CREATURE_CLASS_TO_LOCATION`. **Director Schmector matters most**: the
ending depends on it (next section).

## 7. Ending gate (replaces the SPAC.R Embiggening Cell item)

The ending now requires beating Director Schmector (or the Mant, if
Schmector is in `excluded_bosses`).

**Test this first, on a brand-new world:** the opening quest (Mysterious
Machine -> Reset Pylons -> Return To Platform, before the oak tree
explosion frees BURG.L) uses the SPAC.R shrink pad buttons. There are two
overlapping button pairs there: the regular `BP_Button_Switch_Shrinkpad_*`
pair, which the gate never touches, and the `...ShrinkpadEndGame_*` pair,
which it only blocks once the game itself has made those interactable.

| Step | Expect |
|---|---|
| New world: go through the opening quest and press the shrink pad buttons | Buttons work exactly as in vanilla, the quest continues to the oak tree explosion and BURG.L. At most one log line `Ending gate: endgame button not interactable yet (or unreadable) -- leaving it alone`; **no** "defeat Director Schmector" message. |
| Load in | `Hook registered: ending gate (endgame shrink pad button)` (twice, may only appear once you're near the SPAC.R). |
| Try to use the ending's shrink pad button **before** beating the boss | The button can't be used; on screen `Archipelago: defeat Director Schmector before going home`. |
| Beat Director Schmector | `REPORTED ... Kill: Director Schmector`; the button works again. |
| Finish the game | `OnGameWon fired`, `REPORTED ... Go Big Or Never Go Home (Ending)`, goal complete in the client. |
| (If the button was **not** blocked) finish before the boss | `Ending reached before Director Schmector was recorded as defeated -- holding the ending check`; the ending is sent automatically as soon as the kill is recorded. |

Two things this test settles:
- whether overriding the button's `IsInteractionEnabled` return value from
  a UE4SS hook actually disables it (if not, the backstop above still
  keeps the goal honest);
- whether the game even lets you reach the ending before Schmector.

**If the opening-quest buttons don't work** (or you see the "defeat
Director Schmector" message during the opening), set
`config.gate_ending_on_final_boss = false` and send the log -- that turns
the button block off entirely.

**If the Schmector kill is never detected** you'd be locked out: set
`config.gate_ending_on_final_boss = false` in `Scripts/config.lua` to finish
anyway, and report it.

## 8. Mutation checks

| Step | Expect |
|---|---|
| Load in | `Mutation tiers: ...` once, then `Mutations unlocked: N` matching the mutations screen (a fresh world is 0). |
| Unlock a mutation | The count goes up; at 1, 3, 5, 8, ... `REPORTED ... Mutations: <n>`. |

If the count is wrong (e.g. counts locked mutations or tiers), note the
in-game number vs the logged one.

## 9. Trackers

| Step | Expect |
|---|---|
| PopTracker: load `tracker/grounded_poptracker`, connect via the AP button | Items light up as received; progressive items count up; checked locations clear; mutation/gold-card pins hidden when the seed doesn't use them. |
| Universal Tracker: connect to the room | Logic matches the seed, no YAML needed. |
| Grounded Client: open the **Tracker** tab after connecting | A sidebar of tabs: Overview (a card per tab with progress), Map, one tab per region (items, crafts and landmarks found there), the crafting groups (Utility / Weapons / Armor / Meals), then Bosses / Gold Cards / Molars / Mutations. Green = in logic, red = not yet, grey struck through = checked. Receiving an item or sending a check updates it within a second. "Hide checked" and "In logic only" filter a tab. Unticked checks from `location_review.txt` don't appear. |
| Tracker > **Map** | The real yard map with a pin per landmark: green = visited, white = reachable, red = not yet, a ring instead of a dot = position is a best guess. Mouse wheel zooms, dragging pans, "Reset view" fits it again. Clicking a pin shows the landmark's name, biome and needs. Discovering one in-game turns it green within a second, even if Landmark Checks is off in the seed. Note any pin that's in the wrong place. |
| Tracker: click a check tile (it lights up under the mouse) | A popup with the item's icon, what the check needs (green tick = have it, red cross = not yet) and its recipe with ingredient icons. With Recipe Shuffle on, a gear craft shows this seed's shuffled recipe; compare it with the in-game crafting menu. Items also show **Where to find it**: with Creature Drop Shuffle on, the creatures that drop it this seed ("Weevil (in place of their Raw Weevil Meat)") -- kill one and check. |
| Load the Archipelago world for the first time | The Roasting Spit and Drying Rack are already in the build menu (no AP item needed). |

## 10. Still unconfirmed from before

Carried over from the README's status section:
- `ULootComponent:OnDeath` + `bIsInfectedBroodmother` for "Defeat the
  Infected Broodmother".
- Molar counting after spending molars (`Molar count:` lines should never
  go down).
- Dagger harvest tiers: the `ITEM_ROW: BoneDivingKnife | tier=...`,
  `DaggerSpider` and `DaggerSpiderWidow` lines (logic assumes 1, 2 and 3).
  Receiving **Bone Dagger** / **Widow Dagger** should unlock its recipe
  (`Issued: UnlockRecipe BoneDivingKnife` / `DaggerSpiderWidow`).
- Research/brainpower changes: analyzing gives nothing, brainpower maxed,
  Materials/Base Building/Storage recipes unlocked up front
  (`RECIPE_CATEGORY:` lines show what matched).
