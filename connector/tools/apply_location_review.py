"""
Applies location_review.txt (project root) to the apworld.

The review file is the rule for the checks the mod has. For every check
line in its non-CANDIDATE sections:

    [x] Item: Salty Jewel => Item: Salt Jewel   # needs: c2, hammer3, oven
     |   |                    |                       |
     |   name the mod reports |                       requirement tokens
     |                        name shown in Archipelago (optional)
     ticked = the check exists ([ ] = left out of generated seeds)

and the "### <group>" heading it sits under (Itemsanity / Craftsanity /
Landmarks). Headings used outside Craftsanity are regions (biomes);
headings only used in Craftsanity (Weapons, Armor, ...) are craft groups.
"needs:" notes are read on Item and Landmark lines.

Writes:
  apworld/grounded/review_data.py     -- disabled checks, groups, item and
                                         landmark needs
  apworld/grounded/location_renames.py -- the "=>" renames

Unticking a check never changes any location ID (IDs come from the
location lists, which keep every name). Afterwards regenerate
grounded_data.py / ap_data.lua and the tracker pack, then deploy:

    python connector/tools/apply_location_review.py
"""
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
REVIEW = PROJECT / "location_review.txt"
APWORLD = PROJECT / "apworld" / "grounded"
RENAMES = APWORLD / "location_renames.py"
DATA = APWORLD / "review_data.py"

CHECK = re.compile(r"^\[(?P<box>[ xX])\]\s*(?P<name>.+?)\s*(?:=>\s*(?P<new>[^#]+?))?\s*(?:#(?P<note>.*))?$")
TOKEN = re.compile(r"^(c[1-3]|axe[1-3]|hammer[1-3]|shovel[12]?|dagger[1-3]|gas|dive|canister|undershed"
                   r"|smoothie|cookery|oven|jelly|kill:[A-Za-z ]+)$")


def parse_needs(note: str, where: str):
    """Requirement tokens from a line's "#" note, or None if it has none."""
    note = (note or "").strip()
    match = re.search(r"needs:\s*([^;]*)", note)
    if not match:
        return () if note.lower().startswith("free") else None
    tokens = []
    for raw in match.group(1).split(","):
        token = re.sub(r"\(.*?\)", "", raw).strip()
        if not token or token.lower() == "free":
            continue
        if not TOKEN.match(token):
            raise SystemExit(f"{where}: unknown needs token '{token}'")
        tokens.append(token)
    return tuple(tokens)


def read_review(text: str):
    renames, disabled, biomes, item_needs, biome_order = {}, [], {}, {}, []
    landmark_needs, regions = {}, set()
    section, candidate, biome = "", False, None
    for number, line in enumerate(text.splitlines(), 1):
        line = line.rstrip()
        if line.startswith("## "):
            section, candidate, biome = line[3:], "(CANDIDATE)" in line, None
            continue
        if line.startswith("### "):
            biome = line[4:].strip()
            if biome not in biome_order:
                biome_order.append(biome)
            if not section.startswith("Craftsanity"):
                regions.add(biome)
            continue
        if candidate or not line.startswith("["):
            continue
        match = CHECK.match(line)
        if not match:
            raise SystemExit(f"line {number}: can't read '{line}'")
        name, new = match["name"], (match["new"] or "").strip()
        where = f"line {number} ({name})"
        if new and new != name:
            if name in renames:
                raise SystemExit(f"{where}: renamed twice")
            renames[name] = new
        if match["box"] == " ":
            disabled.append(name)
        if biome:
            biomes[name] = biome
        if name.startswith("Item: "):
            needs = parse_needs(match["note"], where)
            item_needs[name[len("Item: "):]] = needs or ()
        if name.startswith("Landmark: "):
            landmark_needs[name] = parse_needs(match["note"], where) or ()
    taken = list(renames.values())
    for new in set(taken):
        if taken.count(new) > 1:
            raise SystemExit(f"two checks are renamed to '{new}'")
    region_order = [b for b in biome_order if b in regions]
    craft_groups = [b for b in biome_order if b not in regions]
    return renames, disabled, biomes, item_needs, landmark_needs, region_order, craft_groups


def write_renames(renames: dict) -> None:
    source = RENAMES.read_text(encoding="utf-8")
    body = "".join(f"    {old!r}: {new!r},\n" for old, new in renames.items())
    updated, count = re.subn(r"(LOCATION_RENAMES: Dict\[str, str\] = \{\n)(.*?)(^\})",
                             lambda m: m[1] + body + m[3], source, flags=re.S | re.M)
    if count != 1:
        raise SystemExit(f"couldn't find the LOCATION_RENAMES table in {RENAMES}")
    RENAMES.write_text(updated, encoding="utf-8", newline="\n")


def write_data(disabled, biomes, item_needs, landmark_needs, region_order, craft_groups) -> None:
    out = ['"""',
           "GENERATED from location_review.txt by connector/tools/apply_location_review.py",
           "-- edit the review file and rerun the tool instead of editing this.",
           '"""',
           "from typing import Dict, FrozenSet, List, Tuple",
           "",
           "# Checks unticked in the review file: never created in a seed (their IDs",
           "# stay reserved).",
           "DISABLED_LOCATIONS: FrozenSet[str] = frozenset({"]
    out += [f"    {name!r}," for name in disabled]
    out += ["})", "", "# Region (biome) headings, in file order.", "REGIONS: List[str] = ["]
    out += [f"    {b!r}," for b in region_order]
    out += ["]", "", "# Headings only used in Craftsanity (Weapons, Armor, ...).", "CRAFT_GROUPS: List[str] = ["]
    out += [f"    {b!r}," for b in craft_groups]
    out += ["]", "", "BIOMES: List[str] = REGIONS + CRAFT_GROUPS", "",
            "# mod location name -> region or craft group (Item / Craft / Landmark checks).",
            "LOCATION_BIOMES: Dict[str, str] = {"]
    out += [f"    {name!r}: {biome!r}," for name, biome in biomes.items()]
    out += ["}", "", "# Itemsanity: item name -> requirement tokens (see rules.py).",
            "ITEM_NEEDS: Dict[str, Tuple[str, ...]] = {"]
    out += [f"    {name!r}: {tokens!r}," for name, tokens in item_needs.items()]
    out += ["}", "", "# Landmarks: mod location name -> requirement tokens.",
            "LANDMARK_NEEDS: Dict[str, Tuple[str, ...]] = {"]
    out += [f"    {name!r}: {tokens!r}," for name, tokens in landmark_needs.items()]
    out += ["}", ""]
    DATA.write_text("\n".join(out), encoding="utf-8", newline="\n")


def main() -> None:
    renames, disabled, biomes, item_needs, landmark_needs, region_order, craft_groups =         read_review(REVIEW.read_text(encoding="utf-8"))
    write_renames(renames)
    write_data(disabled, biomes, item_needs, landmark_needs, region_order, craft_groups)
    print(f"{len(renames)} rename(s), {len(disabled)} unticked check(s), "
          f"{len(biomes)} check(s) in {len(region_order)} region(s) + {len(craft_groups)} craft group(s), "
          f"{len(item_needs)} item and {len(landmark_needs)} landmark requirement(s)")
    print(f"Wrote {RENAMES} and {DATA}")


if __name__ == "__main__":
    main()
