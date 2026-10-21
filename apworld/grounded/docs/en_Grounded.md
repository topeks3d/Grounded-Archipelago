# Grounded

## Where is the settings page?

Check out the [player options page](../player-options) for a full list of
options you can set, with explanations of what each one does.

## What does randomization do to this game?

Picking up resources, crafting recipes for the first time, boss kills and
Milk Molar milestones become Archipelago locations. Instead of always unlocking the same
research/blueprint tier, gear, and story progress, what you get from those
moments is decided by the multiworld: it might be a tool you need, something
for another player's game, or a handful of a resource to tide you over.

## What is the goal of Grounded when randomized?

Depending on the "Goal" option:

- **Embiggening (default):** beat Director Schmector (or the Mant, if Director
  Schmector is in Excluded Bosses), then finish the ending sequence ("Go Big
  Or Never Go Home"). The mod keeps the ending's shrink pad disabled until
  that boss is beaten.
- **Boss Only:** kill every major boss -- Assistant Manager, Hedge
  Broodmother, Mant, Mantis, Director Schmector, Wasp Queen and Black Widow --
  except any in Excluded Bosses.
- **Story Boss Only:** Assistant Manager, Mant and Director Schmector.
- **Short:** Assistant Manager and Mant.
- **Infected Broodmother**, or **Infected Broodmother and Embiggening**.
- **Gold Cards:** collect a number of gold Creature Cards (Gold Card Goal
  Amount; Gold Card Drop Chance makes them drop more often).
- **Itemsanity:** pick up every tracked item at least once.

## What items and locations get shuffled?

- **Locations:** picking up each tracked resource ("Item: ..."), crafting each
  tracked recipe for the first time ("Craft: ..."), killing the named bosses
  ("Kill: ..."), Milk Molar milestones (regular and gold/Mega molars both
  count), and gold Creature Cards when that goal is chosen.
- **Optional locations:** with **Mutation Checks**, unlocking 1, 3, 5, 8, 12,
  16, 20 and 25 mutations (off by default); with **Landmark Checks**,
  discovering each of the yard's landmarks (field stations, labs, juice
  boxes, ...) -- on by default.
- **Items:** every Tier 1-3 weapon, tool and armor recipe as its own item
  (or, with **Progressive Gear**, Progressive Axe/Hammer/Shovel/Spear/Bow and
  Progressive Head/Chest/Leg Armor), Consumables/Utilities recipe groups, the
  Smoothie Station, Cookery and Oven, traversal gear (Gas Mask, Diving Gear,
  Zip Line Rig).
- **Filler:** Raw Science (2500 per bundle), Full Restore (health, food, water
  and stamina to full) and Bandage Bundles. Also 4 DeDuper Jelly Bundles
  (needed in logic for the New Game+ weapons) and 2 Infused Ooze Bundles.

## What changes in-game?

- Analyzing resources and brainpower level-ups no longer unlock recipes
  (brainpower is set to its max level); gear recipes only come from
  Archipelago items.
- To make up for it, all Material Resources, Base Building, Advanced Building
  and Storage & Utilities recipes are unlocked from the start.
- **Recipe Shuffle** (option, off by default): every Tier 2 and Tier 3
  weapon, tool and armor recipe gets new, seeded ingredients. Tier 1 recipes
  keep their vanilla costs. New ingredients always come from one tier below
  the gear, so logic stays correct. Click a craft check in the Grounded
  Client's Tracker tab to see the new costs.
- Archipelago only runs in a world named **archipelago** (case doesn't
  matter). Received items wait until you've loaded that world and your
  character has spawned, and checks from any other save are ignored. You can
  change the name in the mod's `Scripts/config.lua` (`required_world_name`).
- Items you receive and send, hints about your items, and DeathLinks pop up
  on screen (and in the UE4SS log).
- **DeathLink** (option): when you die, everyone linked dies; when they die,
  so do you. Deaths only count inside the Archipelago world.
- Logic expects Tier N creatures to be fought with a Tier N melee weapon and
  full Tier N armor coverage (head, chest, legs), and the story areas in
  order: Haze (Gas Mask), Pond (Diving Gear), Upper Yard (Zip Line Rig),
  then the Undershed.

## Which items can be in another player's world?

Any item on this world's list can be sent to or received from another
player's game, same as usual for Archipelago.

## I don't have Grounded modding set up. What do I need?

See the [setup guide](../../setup/en) -- you'll need
[UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) installed for Grounded, this
world's mod in your UE4SS Mods folder, and the Grounded Client (from the
Archipelago Launcher) running alongside the game.
