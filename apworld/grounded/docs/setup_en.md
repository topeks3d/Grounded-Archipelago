# Grounded Randomizer Setup Guide

## Required software

- [Grounded](https://store.steampowered.com/app/962130/Grounded/) -- only the
  Steam version is supported
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or later
- [CluelessOtter's UE4SS for Grounded](https://www.nexusmods.com/grounded/mods/201)
- This project's release zip: `grounded.apworld`, the `GroundedArchipelago`
  mod folder and (optionally) `grounded_poptracker.zip`

## 1. Install the Archipelago world

Double-click `grounded.apworld` (Archipelago installs it), or copy it into
Archipelago's `custom_worlds` folder (`C:\ProgramData\Archipelago\custom_worlds`
for the Windows installer). Restart the Archipelago Launcher afterwards.

## 2. Install the game mod

1. Install UE4SS by following
   [CluelessOtter's guide](https://www.nexusmods.com/grounded/mods/201) --
   please read their guide carefully.
2. Copy the `GroundedArchipelago` folder into `ue4ss\Mods`, so you have
   `...\Win64\ue4ss\Mods\GroundedArchipelago\Scripts\main.lua`.
3. In `ue4ss\Mods\mods.txt`, add the line `GroundedArchipelago : 1` and make
   sure `CheatManagerEnablerMod : 1` is there -- received items are granted
   through the game's own cheat commands, which need it.
4. Start Grounded once. The UE4SS log (`ue4ss\UE4SS.log`) should show lines
   starting with `[GroundedArchipelago]`, including the IPC folder it uses.

## 3. Generate and host a game

Make a YAML for Grounded (Archipelago Launcher > **Generate Template
Options**, or the options page), then generate and host the multiworld the
usual Archipelago way.

## 4. Play

1. Open the Archipelago Launcher and start **Grounded Client**. It finds the
   mod's IPC folder by itself for a normal Steam install; if it can't, start
   it with `--ipc-dir "<the IPC folder from the UE4SS log>"`.
2. Type your server address in the client and connect with your slot name.
3. In Grounded, create a new world named **archipelago** (any capitalization)
   and load it. Archipelago only runs in that world: received items wait until
   you've spawned there, checks from other saves are ignored, and your other
   worlds play like the normal game (an on-screen reminder says so every 5
   minutes). While you're in it, a reminder also appears every 5 minutes if
   the client isn't connected. (The name can be changed with
   `required_world_name` in the mod's `Scripts\config.lua`.)
4. Run Grounded in **Windowed** or **Borderless** display mode to see the
   notification cards the client draws over the game.

## The Grounded Client

- **Tracker tab:** every check in your seed, by region, plus Weapons, Armor,
  Meals and Utility crafts, bosses, molars and more. Green ("Ready") checks are
  in logic, red ("Locked") ones aren't yet. Click a check for its icon, what it
  needs, its recipe (your seed's shuffled one with Recipe Shuffle) and where to
  find it (the creatures that drop it this seed with Creature Drop Shuffle).
- **Map** (in the Tracker): every landmark, visited or not. Mouse wheel zooms,
  drag pans, click a pin for its name. The map image isn't in the release
  package (see the README); landmarks are still tracked in the region tabs.
- **Notification cards:** received and sent items, hints and DeathLinks pop up
  over the game with the item, the player and the location. `/overlay` turns
  them off (the game's own notification feed is used instead).
- Commands: `/overlay`, `/ipc_status` (where the client and mod exchange
  files), `/override_save_binding` (see below), plus Archipelago's usual ones.

## Other trackers

- **PopTracker:** put `grounded_poptracker.zip` in PopTracker's `packs`
  folder, open the pack, click the AP button and connect with your slot name.
- **Universal Tracker** works with this world directly.

## Troubleshooting

- **Nothing happens in-game:** check `UE4SS.log` for `[GroundedArchipelago]`
  lines. "Not in a world" / "World '...' is loaded, but ..." mean you're not in
  the **archipelago** world yet.
- **Checks aren't sent:** the client binds a multiworld to the first save it
  sees (to stop checks coming from a different save). If you really changed
  saves, or the server's address changed, type `/override_save_binding`.
- **No notification cards:** switch Grounded to Windowed or Borderless, and
  check `/overlay` hasn't turned them off.
- **Items never arrive:** make sure `CheatManagerEnablerMod : 1` is in
  `mods.txt` (step 2.3).
- **Grounded crashes on startup:** set `ConsoleEnablerMod` and `BPModLoaderMod`
  to `: 0` in `mods.txt`.
