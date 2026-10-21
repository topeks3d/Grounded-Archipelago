"""
Bundled online data for the client's Tracker (see
connector/tools/fetch_online_data.py, which writes data/):

  data/map.png               the yard (wand.com map tiles)
  data/landmark_pins.json    where each landmark sits on it
  data/recipes.json          vanilla recipes (Grounded wiki)
  data/icons/*.png           item icons (Grounded wiki)
  data/sources.json          where each item comes from (Grounded wiki)

Read with pkgutil so it works from inside the .apworld zip. check_info()
is plain Python (no Kivy) so it can be tested.
"""
from __future__ import annotations

import json
import pkgutil
import re
from functools import lru_cache
from typing import Dict, List, NamedTuple, Optional, Tuple

from .craftsanity import CRAFT_LOCATION_PREFIX, CRAFTSANITY_LOCATION_TO_GATE_ITEM
from .gear import GEAR_BY_NAME
from .itemsanity import ITEM_LOCATION_PREFIX
from .landmarks import LANDMARK_PREFIX


def _data(path: str) -> Optional[bytes]:
    try:
        return pkgutil.get_data(__package__, "data/" + path)
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=1)
def landmark_pins() -> Dict[str, dict]:
    raw = _data("landmark_pins.json")
    return json.loads(raw) if raw else {}


@lru_cache(maxsize=1)
def _recipes() -> dict:
    raw = _data("recipes.json")
    return json.loads(raw) if raw else {"names": {}, "recipes": {}}


@lru_cache(maxsize=1)
def _sources() -> Dict[str, str]:
    raw = _data("sources.json")
    return json.loads(raw) if raw else {}


def map_png() -> Optional[bytes]:
    return _data("map.png")


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")


def wiki_name(name: str) -> str:
    """Our item / craft name -> the wiki's (armor pieces have their own)."""
    return _recipes()["names"].get(name, name)


@lru_cache(maxsize=512)
def icon_png(name: str) -> Optional[bytes]:
    """Icon for one of our names or a wiki name, if the wiki had one."""
    return _data(f"icons/{_safe(wiki_name(name))}.png") or _data(f"icons/{_safe(name)}.png")


def vanilla_recipes(name: str) -> List[dict]:
    return _recipes()["recipes"].get(wiki_name(name), [])


def logo_png() -> Optional[bytes]:
    return _data("ap_logo.png")


def location_item(mod_name: str) -> Optional[str]:
    """The item behind an item / craft check ("Item: Sprig" -> "Sprig")."""
    for prefix in (ITEM_LOCATION_PREFIX, CRAFT_LOCATION_PREFIX):
        if mod_name.startswith(prefix):
            return mod_name[len(prefix):]
    return None


def item_row(name: str) -> Optional[str]:
    """Table_AllItems row for one of our item / craft names, where known
    (the in-game banner shows that item's icon)."""
    from .craftsanity import CRAFTSANITY_ROW_TO_DISPLAY_NAME
    from .drop_shuffle import DROP_ROWS
    from .recipe_shuffle import MATERIAL_BY_ROW

    for row, display in CRAFTSANITY_ROW_TO_DISPLAY_NAME.items():
        if display == name:
            return row
    if name in DROP_ROWS:
        return DROP_ROWS[name]
    for row, material in MATERIAL_BY_ROW.items():
        if material.name == name:
            return row
    return None


def own_item_icon(item_name: str, copy: int = 1) -> Optional[bytes]:
    """Icon for one of Grounded's AP items (gear recipe, progressive gear,
    resource bundle), if the wiki had one."""
    from .gear import PROGRESSIVE_LINES

    line = PROGRESSIVE_LINES.get(item_name)
    if line:
        item_name = line[max(0, min(copy, len(line)) - 1)]
    if item_name.endswith(" Bundle"):
        item_name = item_name[:-len(" Bundle")]
    return icon_png(item_name)


# ---------------------------------------------------------------------------
# Check info
# ---------------------------------------------------------------------------
_TOKEN_TEXT = {
    "c1": "Tier 1 weapon", "c2": "Tier 2 weapon + full Tier 2 armor", "c3": "Tier 3 weapon + full Tier 3 armor",
    "gas": "Gas Mask", "dive": "Diving Gear", "canister": "Haze canister plugged (Gas Mask + Tier 2)",
    "undershed": "Reach the Undershed (Zip Line Rig, Gas Mask, Diving Gear, Tier 3)",
    "smoothie": "Smoothie Station", "cookery": "Cookery", "oven": "Oven", "jelly": "All DeDuper Jelly Bundles",
    "shovel": "Acorn Shovel or better",
}
_TOOL_TEXT = {
    "axe": ("Pebblet Axe", "Insect Axe", "Termite Axe"),
    "hammer": ("Pebblet Hammer", "Insect Hammer", "Black Ox Hammer"),
    "shovel": ("Acorn Shovel", "Black Ant Shovel"),
    "dagger": ("Bone Dagger", "Spider Fang Dagger", "Widow Dagger"),
}


def token_text(token: str) -> str:
    if token.startswith("kill:"):
        return "Beat " + token[5:]
    match = re.match(r"^(axe|hammer|shovel|dagger)([123])$", token)
    if match:
        tool, tier = match.group(1), int(match.group(2))
        text = _TOOL_TEXT[tool][tier - 1] + " or better"
        return text + (" (+ Diving Gear)" if tool == "dagger" else "")
    return _TOKEN_TEXT.get(token, token)


class Requirement(NamedTuple):
    text: str
    met: bool


class Recipe(NamedTuple):
    station: str
    materials: List[Tuple[str, object]]   # (name, count)
    shuffled: bool


class CheckInfo(NamedTuple):
    title: str                 # as Archipelago shows it
    item: str                  # the item it's about (icon / recipe lookups)
    kind: str                  # "Item", "Craft", "Landmark", ...
    requirements: List[Requirement]
    recipes: List[Recipe]
    note: str
    sources: List[str] = []    # where to find it (items)
    sources_shuffled: bool = False


def item_sources(item: str, slot_data: Optional[dict] = None) -> Tuple[List[str], bool]:
    """Where `item` comes from: the wiki's source, or -- with Creature Drop
    Shuffle -- the creatures that now drop it (whoever used to drop the
    material it was swapped in for). Returns (lines, shuffled)."""
    from .drop_shuffle import DISPLAY_NAME_BY_ROW, DROP_ROWS

    sources = _sources()
    mapping = (slot_data or {}).get("creature_drop_shuffle") or {}
    row = DROP_ROWS.get(item)
    if mapping and row and row in mapping.values():
        lines = []
        for vanilla_row, new_row in sorted(mapping.items()):
            if new_row != row:
                continue
            replaced = DISPLAY_NAME_BY_ROW.get(vanilla_row, vanilla_row)
            who = sources.get(wiki_name(replaced), "whatever drops it")
            lines.append(f"{who} (in place of their {replaced})")
        return lines, True
    vanilla = sources.get(wiki_name(item))
    return ([vanilla] if vanilla else []), False


def _tokens_for(mod_name: str, shuffled: frozenset) -> Tuple[str, ...]:
    from . import rules
    from .review_data import LANDMARK_NEEDS

    if mod_name.startswith(ITEM_LOCATION_PREFIX):
        return tuple(rules.ITEM_REQUIREMENTS.get(mod_name[len(ITEM_LOCATION_PREFIX):], ()))
    if mod_name.startswith(CRAFT_LOCATION_PREFIX):
        return tuple(rules._craft_requirement(mod_name[len(CRAFT_LOCATION_PREFIX):], shuffled))
    if mod_name.startswith(LANDMARK_PREFIX):
        return tuple(LANDMARK_NEEDS.get(mod_name, ()))
    return ()


def _shuffled_recipe(gear_name: str, shuffle: dict, slots: dict) -> Optional[Recipe]:
    from .recipe_shuffle import MATERIAL_BY_ROW

    gear = GEAR_BY_NAME.get(gear_name)
    entries = shuffle.get(gear.recipe_row) if gear else None
    if not entries:
        return None
    count = slots.get(gear.recipe_row)
    if not isinstance(count, int) or count <= 0:
        # The game keeps the vanilla number of ingredient slots.
        vanilla = vanilla_recipes(gear_name)
        count = len(vanilla[0]["materials"]) if vanilla else len(entries)
    materials = []
    for row, amount in entries[:count]:
        material = MATERIAL_BY_ROW.get(row)
        materials.append((material.name if material else row, amount))
    station = vanilla_recipes(gear_name)[0]["station"] if vanilla_recipes(gear_name) else ""
    return Recipe(station, materials, True)


def check_info(mod_name: str, ap_name: str, state, slot_data: Optional[dict] = None,
               recipe_slots: Optional[dict] = None) -> CheckInfo:
    """Everything the info popup shows for one check. `state` is anything
    with has / has_any / has_all / count (tracker_tab._ItemState)."""
    from . import rules

    slot_data = slot_data or {}
    shuffle = slot_data.get("recipe_shuffle") or {}
    tokens = _tokens_for(mod_name, frozenset(shuffle))
    requirements = [Requirement(token_text(t), bool(rules._build_rule((t,))(state, 1))) for t in tokens]

    kind, item, note = "Other", ap_name, ""
    recipes: List[Recipe] = []
    if mod_name.startswith(ITEM_LOCATION_PREFIX):
        kind, item = "Item", mod_name[len(ITEM_LOCATION_PREFIX):]
        recipes = [Recipe(r["station"], [tuple(m) for m in r["materials"]], False) for r in vanilla_recipes(item)]
        note = "Pick it up (or craft it) once to send the check."
        sources, sources_shuffled = item_sources(item, slot_data)
    elif mod_name.startswith(CRAFT_LOCATION_PREFIX):
        kind, item = "Craft", mod_name[len(CRAFT_LOCATION_PREFIX):]
        gate = CRAFTSANITY_LOCATION_TO_GATE_ITEM.get(mod_name)
        if gate:
            requirements.insert(0, Requirement(f"Recipe: {gate}", bool(state.has(gate, 1))))
        shuffled = _shuffled_recipe(item, shuffle, recipe_slots or {})
        if shuffled:
            recipes = [shuffled]
            note = "Shuffled recipe for this seed (Recipe Shuffle)."
        else:
            recipes = [Recipe(r["station"], [tuple(m) for m in r["materials"]], False) for r in vanilla_recipes(item)]
            note = "Craft it once to send the check."
    elif mod_name.startswith(LANDMARK_PREFIX):
        kind = "Landmark"
        pin = landmark_pins().get(mod_name[len(LANDMARK_PREFIX):])
        note = ("Map position is approximate." if pin and pin.get("approx")
                else "" if pin else "Not on the map yet.")
    title = ap_name
    if kind != "Item":
        sources, sources_shuffled = [], False
    return CheckInfo(title, item, kind, requirements, recipes, note, sources, sources_shuffled)
