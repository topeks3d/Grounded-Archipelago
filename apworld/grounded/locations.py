"""
Location definitions: region -> [(mod location name, offset)].

IDs are BASE_ID + offset and come from list order within each range -- only
append to the source lists. Offset ranges: 1000 itemsanity, 1500 killsanity,
1800 craftsanity, 2000 gold cards, 2200 molars, 2800 mutations, 3000
landmarks, 3500 BURG.L shop (shop_data.py's offsets). 2400+ is retired (old
exploration checks) -- don't reuse.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .itemsanity import ITEMSANITY_ITEM_NAMES, ITEM_LOCATION_PREFIX
from .killsanity import killsanity_location_names
from .craftsanity import craftsanity_location_names
from .goldcards import gold_card_location_names
from .molars import molar_location_names
from .mutations import mutation_location_names
from .landmarks import landmark_location_names
from .shop import SHOP_ID_OFFSET, SHOP_NODES, shop_location_name
from .location_renames import ap_name

BASE_ID = 9411000 + 1000  # clear of the item id range

locations_by_region: Dict[str, List[Tuple[str, int]]] = {
    "Grasslands": [
        # Reported when ASurvivalGameState:OnGameWon fires (embiggening goals only).
        ("Go Big Or Never Go Home (Ending)", 6),
    ],
    "Haze": [
        ("Defeat the Infected Broodmother", 51),
    ],
}

itemsanity_location_names: List[str] = [
    ITEM_LOCATION_PREFIX + name for name in ITEMSANITY_ITEM_NAMES
]
if itemsanity_location_names:
    locations_by_region["Itemsanity"] = [
        (name, 1000 + i) for i, name in enumerate(itemsanity_location_names)
    ]

if killsanity_location_names:
    locations_by_region["Killsanity"] = [
        (name, 1500 + i) for i, name in enumerate(killsanity_location_names)
    ]

if craftsanity_location_names:
    locations_by_region["Craftsanity"] = [
        (name, 1800 + i) for i, name in enumerate(craftsanity_location_names)
    ]

# Always defined; regions._skip_location drops them unless the goal is gold_cards.
locations_by_region["Gold Cards"] = [
    (name, 2000 + i) for i, name in enumerate(gold_card_location_names)
]

locations_by_region["Molars"] = [
    (name, 2200 + i) for i, name in enumerate(molar_location_names)
]

locations_by_region["Mutations"] = [
    (name, 2800 + i) for i, name in enumerate(mutation_location_names)
]

locations_by_region["Landmarks"] = [
    (name, 3000 + i) for i, name in enumerate(landmark_location_names)
]

locations_by_region["BURG.L Shop"] = [
    (shop_location_name(node), SHOP_ID_OFFSET + node.offset) for node in SHOP_NODES
]

# (name, region_name, item_name) -- id-less locations with a locked item.
event_locations: List[Tuple[str, str, str]] = [
]

# Everything in the apworld uses the names the mod reports; Archipelago sees
# the display names from location_renames.py.
mod_location_name_to_id: Dict[str, int] = {
    name: BASE_ID + offset
    for locations in locations_by_region.values()
    for name, offset in locations
}

location_name_to_id: Dict[str, int] = {
    ap_name(name): code for name, code in mod_location_name_to_id.items()
}
assert len(location_name_to_id) == len(mod_location_name_to_id),     "a renamed location collides with another location's name (location_renames.py)"

location_name_groups: Dict[str, set] = {
    region: {ap_name(name) for name, _ in locations}
    for region, locations in locations_by_region.items()
}
