"""
Itemsanity: first pickup of each item ("Item: <ItemName>"), reported by
location_hooks.lua's HandleOnItemAdded hook under the game's display name.

Location IDs follow list order -- only ever append. After changing a list,
regenerate grounded_data.py / ap_data.lua (connector/tools). Which of these
are in a seed, their requirements and regions come from location_review.txt.
"""
from __future__ import annotations

from typing import Dict, List

# --- Material Resources (crafted, not looted from a specific creature) ---
_MATERIAL_COMMON = [
    "Ash Cement", "Bug Rubber", "Charcoal Ash", "Crude Rope",
    "Mushroom Slurry", "Plant Slurry", "Repair Glue", "Spoiled Meat Slurry",
]
_MATERIAL_UNCOMMON = [
    "Berry Leather", "Brittle Plating", "Brittle Whetstone", "Lint Rope", "Mighty Glob", "Mighty Jewel",
    "Mint Glob", "Mint Jewel", "Mushroom Brick", "Pupa Leather",
    "Salt Glob", "Salty Jewel", "Silk Rope", "Sour Glob", "Sour Jewel",
    "Spicy Glob", "Spicy Jewel", "Sturdy Plating", "Sturdy Whetstone",
    "Supreme Plating", "Supreme Whetstone",
]

# --- Environmental Resources (gathered from plants/nodes/the ground) ---
_ENVIRONMENTAL_COMMON = [
    "Acorn Bits", "Acorn Shell", "Acorn Top", "Algae", "Apple Bits",
    "Berry Chunk", "Billy Hog Bite", "Clay", "Clover Leaf",
    "Cookie Sandwich Bits", "Donut Chunk", "Dry Grass Chunk",
    "Eelgrass Strand", "Flower Petal", "Grass Plank", "Grass Seeds",
    "Grumble's Granola Bar", "Lilypad Wax", "Muscle Sprout", "Mushroom",
    "Mushroom Chunk", "Nectar", "Pebblet", "Plant Fiber", "Pollen",
    "Pond Moss", "Pupa Hide", "Rotten Food", "Salt Shard", "Sap",
    "Slime Mold Stalk", "Spoiled Meat", "Sprig", "Thistle Needle",
    "Toadstool Chunk", "Weed Stem",
]
_ENVIRONMENTAL_UNCOMMON = [
    "Brittle Marble Shard", "Brittle Quartzite Shard", "Lint",
    "Mint Chunk", "Pinecone Piece", "Rust", "Spiky Bur",
    "Sturdy Marble Shard", "Sturdy Quartzite Shard", "Sunken Bone",
    "Supreme Marble Shard", "Supreme Quartzite Shard", "Toenail",
    "Wasp Paper", "Wooden Splinter",
]
_ENVIRONMENTAL_RARE = [
    "Crow Feather Piece", "EverChar Coal Chunk", "Gunpowder Clump",
    "Gum Nugget", "Koi Fish Scale", "Sour Lump", "Spicy Shard",
]

# --- Creature Resources from ordinary (non-boss, non-queen) creatures ---
_CREATURE_COMMON = [
    "Acid Gland", "Antlion Part", "Aphid Honeydew", "Bee Fuzz",
    "Black Ant Head", "Black Ant Mandibles", "Black Ant Part",
    "Black Ox Part", "Bombardier Part", "Diving Bell Spider Chunk",
    "Dust Mite Fuzz", "Fire Ant Head", "Fire Ant Mandibles",
    "Fire Ant Part", "Fungal Growth", "Glow Goo", "Gnat Fuzz",
    "Grub Hide", "Grub Sludge", "Iridescent Scale", "Ladybug Part",
    "Ladybird Shell", "Larva Spike", "Mite Fuzz", "Mosquito Beak",
    "Mosquito Blood Sack", "Raw Aphid Meat", "Raw Gnat Meat",
    "Raw Grub Meat", "Raw Tadpole Meat", "Raw Weevil Meat",
    "Red Ant Part", "Roly Poly Part", "Spider Chunk", "Stinkbug Part",
    "Tiger Mosquito Beak", "Termite Part", "Tough Gunk",
    "Water Boatman Fin", "Water Flea Meat", "Web Fiber", "Weevil Nose",
]
_CREATURE_UNCOMMON = [
    "Antlion Pincer", "Bee Stinger", "Boiling Gland", "Black Ant Egg",
    "Black Ox Horn", "Fire Ant Egg", "Green Shield Bug Parts",
    "Ladybug Head", "Moth Fuzz", "Moth Scale",
    "Red Ant Egg", "Red Ant Head", "Red Ant Mandibles", "Roly Poly Shell",
    "Spider Fang", "Spider Venom", "Stinkbug Gas Sack",
    "Termite Chompers", "Tick Fang", "Wasp Leg", "Wasp Shell",
    "Twinkling Shell",
]

# --- Other (prepared food) ---
_OTHER = [
    "Aphid Jerky", "Aphid Roast", "Cooked Tadpole Meat", "Dew Drop",
    "Gnat Jerky", "Gnat Roast", "Grub Jerky", "Grub Roast", "Juice Drop",
    "Soda Drop", "Tadpole Jerky", "Water Flea Jerky", "Water Flea Roast",
    "Weevil Jerky", "Weevil Roast",
]

# Not checks: boss / queen drops, seasonal and New Game+ items.
EXCLUDED_BOSS_OR_QUEEN_LOCKED = [
    # Broodmother (regular)
    "Broodmother Chunk", "Broodmother Fang", "Broodmother Venom",
    "Broodmother Infused Ooze",
    # Infected Broodmother
    "Infected Chunk", "Infected Fang", "Infected Venom",
    "Infected Broodmother Infused Ooze",
    # Wasp Queen (the boss)
    "Wasp Queen Chunk", "Wasp Queen Head", "Wasp Queen Infused Ooze",
    "Wasp Queen Wing",
    # Mantis (the boss)
    "Mantis Claw", "Mantis Chunk", "Mantis Head", "Mantis Infused Ooze",
    # Black Widow (the boss)
    "Black Widow Fang",
    # Ant/Termite queens and kings
    "Black Ant Queen Chunk", "Black Ant Queen Head",
    "Black Ant Queen Pheromone",
    "Fire Ant Queen Chunk", "Fire Ant Queen Head",
    "Fire Ant Queen Pheromone",
    "Red Ant Queen Chunk", "Red Ant Queen Head", "Red Ant Queen Pheromone",
    "Termite King Carapace",
    # "Super" variants (elite spawns)
    "Super Stink Sack", "Super Spider Venom",
]
EXCLUDED_SEASONAL_OR_NEW_GAME_PLUS = [
    "Candy Cornlet",  # Halloween-only
    "Chocolate", "Rainbow Chocolate Chunk", "Smoochies Chunk",  # Easter-only
    "Burnt Toast", "Crispy Toast", "Perfect Toast",  # New Game+ / REMIX.R only
    # New Game+ only -- AP hands out jelly/ooze as bundles (items.py)
    "DeDuper Jelly", "Fusion Crystal", "Infused Ooze",
]

# Items from the ending area (SPAC.R / JavaMatic) -- kept out of itemsanity.
EXCLUDED_ENDING_AREA: List[str] = [
]

ITEMSANITY_ITEM_NAMES: List[str] = [
    *_MATERIAL_COMMON,
    *_MATERIAL_UNCOMMON,
    *_ENVIRONMENTAL_COMMON,
    *_ENVIRONMENTAL_UNCOMMON,
    *_ENVIRONMENTAL_RARE,
    *_CREATURE_COMMON,
    *_CREATURE_UNCOMMON,
    *_OTHER,
]

# Keep in sync with location_hooks.lua's ITEM_LOCATION_PREFIX.
ITEM_LOCATION_PREFIX = "Item: "

BASE_ID = 9411000 + 2000

itemsanity_location_names: List[str] = [
    ITEM_LOCATION_PREFIX + name for name in ITEMSANITY_ITEM_NAMES
]

itemsanity_location_name_to_id: Dict[str, int] = {
    name: BASE_ID + offset for offset, name in enumerate(itemsanity_location_names)
}
