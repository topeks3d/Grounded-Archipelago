"""
ShopChecks: buying a BURG.L science shop node sends its check (shop.lua);
the node still gives its usual reward unless that's an AP-managed recipe
(research_control.lua empties those). The BURG.L chips open shop pages as
usual. So a page's checks are in
logic once its chip can be reached (TREE_REQUIREMENTS) and the science paid.

The node list (shop_data.py) is generated from the game's own tech tree
table by connector/tools/import_game_dump.py, from the "TECH_NODE:" lines
data_dump.lua writes to the UE4SS log.

Location IDs: BASE_ID + 3500 + ShopNode.offset (offsets are fixed per
node in shop_data.py -- only ever append).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .shop_data import SHOP_NODES, ShopNode

SHOP_LOCATION_PREFIX = "BURG.L Shop: "
SHOP_ID_OFFSET = 3500

# Science cost -> combat tier whose areas pay for it (Raw Science is found
# all over the yard, more of it further out).
_COST_TIERS: Tuple[Tuple[int, Tuple[str, ...]], ...] = (
    (1500, ()),
    (4000, ("c1",)),
    (8000, ("c2",)),
)


# Where each page's BURG.L chip is found (the lab or outpost it's in, from
# location_review.txt's landmarks). Mint's chip location isn't pinned down,
# so it waits for every region.
TREE_REQUIREMENTS: Dict[str, Tuple[str, ...]] = {
    "OakLabTechTree": (),
    "AntHillTechTree": (),
    "HedgeLabTechTree": ("c2", "region:Hedge"),
    "WeedLabTechTree": ("gas", "region:Haze"),
    "MintTechTree": ("c2", "region:*"),
    "PondTechTree": ("dive", "region:Pond"),
    "PondOutpostTechTree": ("region:Pond",),
    "AntHillBlackTechTree": ("c1", "region:Sandbox"),
    "PicnicTechTree": ("c2", "region:Upper Grasslands"),
    "WoodPileTechTree": ("c3", "region:Woodpile"),
    "StumpTechTree": ("c2", "region:Upper Grasslands"),
    "StorageBoxTechTree": ("c3", "region:Upper Grasslands"),
}


def shop_location_name(node: ShopNode) -> str:
    """The name the mod reports (and Archipelago shows)."""
    return f"{SHOP_LOCATION_PREFIX}{node.name}"


shop_location_names: List[str] = [shop_location_name(node) for node in SHOP_NODES]

SHOP_NODE_BY_LOCATION: Dict[str, ShopNode] = {shop_location_name(node): node for node in SHOP_NODES}


def shop_requirement(node: ShopNode) -> Tuple[str, ...]:
    """The chip's tokens plus the science's; unknown pages wait for everything."""
    chip = TREE_REQUIREMENTS.get(node.tree, ("c3", "region:*"))
    science = next((tokens for limit, tokens in _COST_TIERS if node.cost <= limit), ("c3",))
    return tuple(dict.fromkeys(chip + science))
