# Grounded Archipelago

An [Archipelago](https://archipelago.gg) multiworld randomizer for
[Grounded](https://grounded.obsidian.net/). Your gear recipes, crafting
stations and traversal gear are shuffled into the multiworld; picking things
up, crafting, beating bosses, finding landmarks and more become checks that
send items to you and the other players.

Unofficial fan project -- not affiliated with or endorsed by Obsidian
Entertainment, Xbox Game Studios, Microsoft or the Archipelago project.

## Features

- **Checks:** first pickup of ~160 resources, first craft of ~130 weapons,
  tools, armor, meals and utilities, boss kills, Milk Molar milestones,
  over 100 landmarks, and optionally mutations and gold Creature Cards.
- **Items:** every Tier 1-3 weapon, tool and armor recipe (or progressive
  gear lines), the Smoothie Station, Cookery and Oven, Gas Mask, Diving Gear
  and Zip Line Rig, plus resource bundles as filler. Research no longer unlocks
  gear -- only the multiworld does.
- **Logic** follows the game: tiers of weapons and armor, harvesting tools,
  and the story areas (Haze, Pond, Upper Yard, Undershed).
- **Goals:** the real ending, a boss sweep (all bosses, story bosses, or a
  short run), the Infected Broodmother, gold cards, or itemsanity.
- **Options:** Recipe Shuffle (new ingredients for Tier 2-3 gear), Creature
  Drop Shuffle, Progressive Gear, DeathLink, and more.
- **Grounded Client** with a built-in **Tracker**: checks by region, what's in
  logic, recipes (including shuffled ones), where to find each item, and a
  landmark map -- plus notification cards drawn over the game for items you
  send and receive.
- A **PopTracker** pack, and Universal Tracker support.

## Setup guide

### What you need

- Grounded on PC ([Steam](https://store.steampowered.com/app/962130/Grounded/))
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or later
- [UE4SS for Grounded](https://www.nexusmods.com/grounded/mods/198) (0R4X's
  Grounded-ready UE4SS package -- this mod was built and tested on it)
- The latest `GroundedArchipelago-<version>.zip` from this repository's
  [Releases](https://github.com/topeks3d/Grounded-Archipelago/releases). It
  contains `grounded.apworld`, the `GroundedArchipelago` mod folder,
  `grounded_poptracker.zip` (optional) and a copy of this guide (`SETUP.md`).

### 1. Install the Archipelago world

Double-click `grounded.apworld` (Archipelago installs it), or copy it into
Archipelago's `custom_worlds` folder (`C:\ProgramData\Archipelago\custom_worlds`
for the Windows installer). Restart the Archipelago Launcher afterwards.

### 2. Install the game mod

1. Install UE4SS for Grounded: extract it into
   `Grounded\Maine\Binaries\Win64`, so `dwmapi.dll` and the `ue4ss` folder sit
   next to `Maine-Win64-Shipping.exe`. (In Steam: right-click Grounded >
   Manage > Browse local files to find the `Grounded` folder.)
2. Copy the `GroundedArchipelago` folder into `ue4ss\Mods`, so you end up with
   `...\Win64\ue4ss\Mods\GroundedArchipelago\Scripts\main.lua`.
3. Open `ue4ss\Mods\mods.txt` and make sure it has these lines:

   ```
   CheatManagerEnablerMod : 1
   ConsoleEnablerMod : 0
   GroundedArchipelago : 1
   BPModLoaderMod : 0
   ```

   Received items are granted through the game's own cheat commands, which
   need **CheatManagerEnablerMod**. Leave **ConsoleEnablerMod** and
   **BPModLoaderMod** off: they can crash Grounded on startup, and this mod
   doesn't need them.
4. Start Grounded once. `ue4ss\UE4SS.log` should now have lines starting with
   `[GroundedArchipelago]`, including the IPC folder the mod uses.

### 3. Generate and host a game

Make a YAML for Grounded (Archipelago Launcher > **Generate Template
Options**, then edit `Grounded.yaml`), put it in Archipelago's `Players`
folder with everyone else's, and generate and host the multiworld the usual
Archipelago way.

### 4. Play

1. Open the Archipelago Launcher and start **Grounded Client**. It finds the
   mod's IPC folder by itself for a normal Steam install.
2. Type your server address in the client and connect with your slot name.
3. In Grounded, create a new world named **archipelago** (any capitalization)
   and load it. Archipelago only runs in that world:
   - received items arrive once you've spawned there;
   - checks only count there -- every other save plays like the normal game,
     and an on-screen reminder says so every 5 minutes;
   - while you're in it, a reminder also appears every 5 minutes if the
     client isn't connected.
4. Run Grounded in **Windowed** or **Borderless** display mode to see the
   notification cards the client draws over the game.

Use a fresh **archipelago** world for each new multiworld: recipes a save has
already learned stay learned.

## The Grounded Client

- **Tracker tab:** every check in your seed, by region, plus Weapons, Armor,
  Meals and Utility crafts, bosses, molars and more. Green ("Ready") checks are
  in logic, red ("Locked") ones aren't yet. Click a check for its icon, what it
  needs, its recipe (your seed's shuffled one with Recipe Shuffle) and where to
  find it (the creatures that drop it this seed with Creature Drop Shuffle).
- **Map** (in the Tracker): every landmark, visited or not. The map image isn't
  included in releases (see Credits & references); landmarks are still
  tracked in the region tabs.
- **Notification cards:** received and sent items, hints and DeathLinks pop up
  over the game with the item, the player and the location.
- **Commands:** `/overlay` (cards on/off -- off uses the game's own
  notification feed), `/ipc_status` (where the client and mod exchange files),
  `/override_save_binding` (see Troubleshooting), plus Archipelago's usual ones.

## Other trackers

- **PopTracker:** put `grounded_poptracker.zip` in PopTracker's `packs`
  folder, open the pack, click the AP button and connect with your slot name.
- **Universal Tracker** works with this world directly.

## How it works

Two parts, talking through a folder of small JSON files (the mod's `ipc`
folder):

- `game_mod/GroundedArchipelago` -- a UE4SS Lua mod inside the game: detects
  checks, grants received items, and applies the research changes, gold card
  drop chance and recipe/drop shuffles (only in the **archipelago** world).
- `apworld/grounded` -- the Archipelago world (generation and logic) and the
  Grounded Client (server connection, Tracker, notification cards).

The world's tests are in `apworld/grounded/test`: copy `apworld/grounded` into
an Archipelago source checkout's `worlds/` folder and run
`python -m pytest worlds/grounded/test`.

## Credits & references

**Game**
- *Grounded* is developed by Obsidian Entertainment and published by Xbox Game
  Studios. Grounded © Microsoft Corporation. Grounded Archipelago was created
  under Microsoft's
  ["Game Content Usage Rules"](https://www.xbox.com/en-US/developers/rules)
  using assets from Grounded, and it is not endorsed by or affiliated with
  Microsoft.

**Frameworks this project builds on**
- [Archipelago](https://archipelago.gg)
  ([source](https://github.com/ArchipelagoMW/Archipelago)): the multiworld
  randomizer. The apworld, the Grounded Client (built on Archipelago's
  `CommonClient` and Kivy UI) and the tests use its APIs. Its logo is used on
  the notification cards.
- [RE-UE4SS](https://github.com/UE4SS-RE/RE-UE4SS): the Unreal Engine
  scripting system the in-game mod runs on, including its built-in
  CheatManagerEnablerMod.
- [UE4SS for Grounded](https://www.nexusmods.com/grounded/mods/198) by 0R4X
  (Nexus Mods): the Grounded-ready UE4SS package (UE4SS 3.0.1 with
  Grounded-specific fixes) this mod was developed and tested on.
- [Kivy](https://kivy.org) and [KivyMD](https://github.com/kivymd/KivyMD),
  which come with Archipelago: the client's UI. Icons use the
  [Material Design Icons](https://pictogrammers.com/library/mdi/) font bundled
  with KivyMD.
- [PopTracker](https://github.com/black-sliver/PopTracker): the pack in
  `tracker/grounded_poptracker` follows its pack format.
- [Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases):
  works with this world directly.

**Data in `apworld/grounded/data/`** (from `connector/tools/fetch_online_data.py`)
- **Recipes and item sources:** the [Grounded Wiki](https://grounded.wiki.gg)
  on wiki.gg (its `Template:Recipe` page and item infoboxes), used under
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The
  adapted files `recipes.json` and `sources.json` are shared under the same
  licence.
- **Item icons:** Grounded's own item art, as hosted on the Grounded Wiki --
  used under Microsoft's Game Content Usage Rules (see above).
- **Yard map and landmark pin positions:** from the
  [Grounded map on wand.com](https://wand.com/maps/grounded/yard) (WeMod).
  wand.com's terms don't allow redistributing its content, so **release
  builds don't include them**; `fetch_online_data.py --map` makes a copy for
  your own use.

**Design**
- The notification cards drawn over the game follow the look of the Bloons TD 6
  Archipelago mod's notifications
  ([Matt's BTD6 mod](https://github.com/Matt41321/BloonsArchipelago)).

**Research**
- Item, creature, boss and location details were cross-checked against the
  [Grounded Wiki (wiki.gg)](https://grounded.wiki.gg) and the
  [Grounded Wiki on Fandom](https://grounded.fandom.com), and against the
  game's own data read in-game through UE4SS (object, header and data-table
  dumps).

**Build tools (not shipped)**
- [Pillow](https://python-pillow.org) builds the map image, icons and
  PopTracker images.
- [lupa](https://github.com/scoder/lupa) loads the Lua scripts in testing.

## AI Disclosure

**This project was created almost entirely with AI.**

- **Tools:** [Claude Code](https://claude.com/claude-code) (Anthropic), using
  Claude models.
- **Purpose:** writing the project's code -- the Archipelago world
  (generation, logic, options), the Grounded Client (connection, Tracker,
  notification cards), the UE4SS Lua mod and the build/data tools -- plus
  the documentation, working out how the game works from UE4SS dumps and
  logs, and collecting game data from public sources (see Credits &
  references).
- **How extensively:** nearly all code and documentation was written by
  Claude Code. The human side was directing it: deciding the features and
  design, choosing which checks exist and what they require (hand-edited in
  `location_review.txt`), and supplying the game dumps and logs it worked
  from. No AI-generated images or art are used.
- **Human review:** every feature was tried in-game during development, and
  the project was then tested by 2 people. Review was through playtesting
  rather than a line-by-line code review.

If any developer would like to fork or remake the mod based on this project,
you are free to do so.

## License

The code is released under the [MIT License](LICENSE), © 2026 topeks3d.
This covers the project's own code only. The bundled wiki data
(`recipes.json`, `sources.json`) stays under CC BY-SA 4.0, and Grounded's item
art stays Microsoft's (see Credits & references above).

## Troubleshooting

Most problems show up in `Grounded\Maine\Binaries\Win64\ue4ss\UE4SS.log` --
search it for `[GroundedArchipelago]`.

- **No `[GroundedArchipelago]` lines in the log at all:** the mod isn't
  loading. Check the folder is `ue4ss\Mods\GroundedArchipelago\Scripts\main.lua`
  (not one folder deeper) and that `mods.txt` has `GroundedArchipelago : 1`.
- **"Archipelago is off: this world isn't named 'archipelago'":** you're in a
  different save. Create or load a world named **archipelago**. If you joined
  someone else's game and the name doesn't come through, set
  `config.required_world_name = nil` in the mod's `Scripts\config.lua`.
- **"Not connected to the multiworld":** start the Grounded Client and connect.
  If it's open and connected but the message keeps coming, check `/ipc_status`
  in the client points at the same folder as the "Using IPC directory" line in
  the UE4SS log.
- **The client can't find the game:** for a non-standard install, start the
  client with `--ipc-dir "<the IPC folder from the UE4SS log>"` (in the
  Launcher, or `ArchipelagoLauncher.exe "Grounded Client" -- --ipc-dir "..."`).
- **Items never arrive:** make sure `CheatManagerEnablerMod : 1` is in
  `mods.txt`, and that you're in the **archipelago** world with your character
  spawned (items wait while you're dead or on a loading screen).
- **Checks aren't sent:** the client binds each multiworld to the first save it
  sees, so progress from another save can't leak in. If you really changed
  saves, or the server's address changed, type `/override_save_binding` in the
  client while the right save is loaded.
- **No notification cards over the game:** switch Grounded to Windowed or
  Borderless, and check `/overlay` hasn't turned them off.
- **"Restart Grounded to get normal research back in this world":** the mod
  couldn't undo its research changes after you left the archipelago world.
  Restart the game before playing your other saves.
- **Grounded crashes on startup:** set `ConsoleEnablerMod` and `BPModLoaderMod`
  to `: 0` in `mods.txt`.
- **Still stuck:** open an issue on this repository with your `UE4SS.log` and
  the Grounded Client's log (`Archipelago\logs\GroundedClient_*.txt`).
