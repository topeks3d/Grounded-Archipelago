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

## Requirements

- Grounded on PC (Steam)
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or later
- [UE4SS for Grounded](https://www.nexusmods.com/grounded/mods/198) (0R4X's
  UE4SS package for Grounded)

## Installing

Download the latest `GroundedArchipelago-<version>.zip` from Releases and
follow **SETUP.md** inside it (also at
[apworld/grounded/docs/setup_en.md](apworld/grounded/docs/setup_en.md)). In
short:

1. Install `grounded.apworld` into Archipelago (double-click it, or put it in
   `custom_worlds`).
2. Install UE4SS for Grounded and copy the `GroundedArchipelago` folder into
   `ue4ss\Mods`; in `mods.txt` enable GroundedArchipelago and
   CheatManagerEnablerMod, and leave ConsoleEnablerMod off.
3. Generate and host a game with a Grounded YAML.
4. Start **Grounded Client** from the Archipelago Launcher, connect, then load
   a Grounded world named **archipelago**.

## How it works

Two parts, talking through a folder of small JSON files:

- `game_mod/GroundedArchipelago` -- a UE4SS Lua mod inside the game: detects
  checks, grants received items, applies the recipe and drop shuffles.
- `apworld/grounded` -- the Archipelago world (generation and logic) and the
  Grounded Client (server connection, Tracker, notification cards).

See [ARCHITECTURE.md](ARCHITECTURE.md) for the details, [TESTING.md](TESTING.md)
for the in-game test checklist and [DEV_NOTES.md](DEV_NOTES.md) for the
history of how the game hooks were found.

## Building from source

- `python connector/tools/deploy.py` -- install the mod and apworld into your
  local Grounded and Archipelago.
- `python connector/tools/build_release.py` -- build
  `dist/GroundedArchipelago-<version>.zip` (the version comes from
  `apworld/grounded/archipelago.json`).
- `python connector/tools/apply_location_review.py` -- apply
  `location_review.txt` (which checks exist, their requirements, names and
  regions).
- `python connector/tools/fetch_online_data.py` -- refresh the bundled wiki
  data (and, for your own use, the wand.com map). Needs Pillow.
- Tests: copy `apworld/grounded` into an Archipelago checkout's `worlds/` and
  run `python -m pytest worlds/grounded/test`.

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
