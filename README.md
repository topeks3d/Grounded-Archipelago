# Grounded Archipelago

An [Archipelago](https://archipelago.gg) multiworld randomizer for
[Grounded](https://grounded.obsidian.net/). Your gear recipes, crafting
stations and traversal gear are shuffled into the multiworld; picking things
up, crafting, beating bosses, finding landmarks and more become checks that
send items to you and the other players.

Unofficial fan project -- not affiliated with or endorsed by Obsidian
Entertainment, Xbox Game Studios, Microsoft or the Archipelago project.

## Features

- **Grounded Client** with a built-in **Tracker**: checks by region, what's in
  logic, recipes (including shuffled ones), where to find each item, and a
  landmark map -- plus notification cards drawn over the game for items you
  send and receive.
- A **PopTracker** pack, and Universal Tracker support.

## Setup guide

### Requirements

- Grounded **ONLY STEAM VERSION IS SUPPORTED** ([Steam page](https://store.steampowered.com/app/962130/Grounded/))
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or later
- [CluelessOtter's UE4SS for Grounded](https://www.nexusmods.com/grounded/mods/201)
- WinRAR to extract files
- The latest `GroundedArchipelagozip` from
  [Releases](https://github.com/topeks3d/Grounded-Archipelago/releases). It
  contains the apworld, the mod files and an optional poptracker.

### 1. Install the Archipelago world

Double click the apworld or drag it into your archipelago custom worlds folder.

### 2. Setting up the mod

1. Install UE4SS according to [CluelessOtter's guide](https://www.nexusmods.com/grounded/mods/201).
   - **`PLEASE MAKE SURE YOU READ THEIR GUIDE FOR INSTALLING UE4SS `**

3. Copy the `GroundedArchipelago` folder into the mods folder inside ue4ss.
4. Open `ue4ss\Mods\mods.txt` and make sure that these mods are enabled (you will need to add the GroundedArchipelago line):

   ```
   CheatManagerEnablerMod : 1
   GroundedArchipelago : 1
   ```

5. Start Grounded once. `ue4ss\UE4SS.log` should now have lines starting with
   `[GroundedArchipelago]`, including the IPC folder the mod uses.

### 3. Generate and host a game

If youre hosting, generate and host your multiworld the usual way following [these instructions](https://archipelago.gg/tutorial/Archipelago/setup_en#generating-a-game).

### 4. Play

1. Open the Archipelago Launcher and open the **Grounded Client**.

2. Type your server address in the client and connect with your slot name.

3. In Grounded, create a new world named **archipelago** (any capitalization)
   and load it. The mod will only run in worlds with that name.
   - You will be told if you are in an accepted world but aren't connected to a multiworld, and you will also be told if you aren't in a world with an accepted name.

Please remember to only play on fresh saves if you are starting a new multiworld.

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

## Other trackers

**You do not need to use these since the client already has a tracker tab, however you may prefer these so the alternatives have been implemented.**

- **PopTracker:** put `grounded_poptracker.zip` in PopTracker's `packs`
  folder, open the pack, click the AP button and connect with your slot name.
- **Universal Tracker** works with this world directly.


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
- [UE4SS for Grounded](https://www.nexusmods.com/grounded/mods/201) by CluelessOtter
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
  Claude Code. All I did was decide what features should be in the mod and how they work. No AI-generated images or art are used.
- **Human review:** every feature was tried in-game during development, and
  the project was then tested by friends while playing in our own asyncs. 

If any developer would like to fork or remake the mod based on this project due to disagreements about AI usage,
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

- **"Archipelago is off: this world isn't named 'archipelago'":** Create or load a world named **archipelago**. If you joined
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
  client while the right save is loaded. If that doesn't work, look at the 2nd problem. 

- **No notification cards over the game:** switch Grounded to Windowed or
  Borderless, and check `/overlay` hasn't turned them off.

- **"Restart Grounded to get normal research back in this world":** the mod
  couldn't undo its research changes after you left the archipelago world.
  Restart the game before playing your other saves.

- **Grounded crashes on startup:** set `ConsoleEnablerMod` and `BPModLoaderMod`
  to `: 0` in `mods.txt`.

- **Still stuck:** open an issue on this repository with your `UE4SS.log` and
  the Grounded Client's log (`Archipelago\logs\GroundedClient_*.txt`).
