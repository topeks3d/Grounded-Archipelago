"""
Downloads the online data the Grounded Client's Tracker uses and turns it
into files under apworld/grounded/data/:

  map.png              the yard, stitched from wand.com's (WeMod) interactive
                       map tiles
  landmark_pins.json   POI asset -> {"title", "u", "v", "approx"}: where each
                       landmark sits on map.png (u, v in 0..1), using
                       wand.com's pins (LANDMARK_PINS below matches them up)
  recipes.json         vanilla recipes from the Grounded wiki (wiki.gg,
                       Template:Recipe): item -> [{"station", "materials"}]
  icons/<name>.png     64px item icons from the wiki, for every item, craft
                       and ingredient the tracker can show
  sources.json         item -> where it comes from (the wiki infobox's
                       "source" field, e.g. Raw Aphid Meat -> Aphid)

    python connector/tools/fetch_online_data.py [--map] [--wiki]

(both by default). Needs Pillow. Re-run after changing LANDMARK_PINS or
WIKI_NAMES; downloads are cached in connector/tools/.cache.

Sources and licences: the map image and pin positions come from
https://wand.com/maps/grounded/yard (WeMod); recipes and icons from
https://grounded.wiki.gg (text CC BY-SA; icons are game assets). Fine for
personal use -- ask before publishing them with the apworld.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
APWORLD = PROJECT / "apworld" / "grounded"
OUT = APWORLD / "data"
CACHE = Path(__file__).resolve().parent / ".cache"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

WAND_PAGE = "https://wand.com/maps/grounded/yard"
MAP_ZOOM = 4          # 16 x 16 tiles of 256 px -> a 4096 px map
WIKI_API = "https://grounded.wiki.gg/api.php"

# ---------------------------------------------------------------------------
# POI asset -> the wand.com pin it is. A pin is a title, or (title, lng)
# when the title appears more than once, or (lng, lat) for a spot with no
# usable title (Mix.R stations, the pond's Pagoda). approx=True when the
# match is a best guess (shown as such in the client). Assets missing here
# have no pin. "name" overrides the title as the landmark's name.
# ---------------------------------------------------------------------------
LANDMARK_PINS = {
    "POI_4Leaf_Clover": {"pin": "4 Leaf Clover"},
    "POI_AntHill_Jungle": {"pin": "Jungle Anthill"},
    "POI_AntHill_Lawnmower": {"pin": "Lawnmower Anthill"},
    "POI_Ant_Hill_Abandoned": {"pin": "Old Anthill"},
    "POI_Ashtray": {"pin": "Dirty Ashtray"},
    "POI_BAH_Lab": {"pin": "Black Anthill Laboratory"},
    "POI_BAH_SandboxEntrance": {"pin": ("Black Anthill Descent", -99.03), "name": "Black Anthill Descent (Sandbox)"},
    "POI_BAH_TrashEntrance": {"pin": ("Black Anthill Descent", -106.01), "name": "Black Anthill Descent (Trash Heap)"},
    "POI_Bat": {"pin": "Bomber Baseball Bat"},
    "POI_Battletoad": {"pin": "Rash", "name": "Rash (Battletoad)"},
    "POI_Bike_Thor": {"pin": "Samsquatch Dirt Bike"},
    "POI_BottomPondBackEntry": {"pin": "Depths Mouth", "approx": True},
    "POI_BottomPondLabEntrance": {"pin": "Pond Hatch", "approx": True},
    "POI_BottomPondTrex": {"pin": "Sunken T-Rex"},
    "POI_BrawnyBoxEntrance": {"pin": "Brawny Boy Bin Entrance"},
    "POI_Can_CalvoRootBeer": {"pin": "Calvo Can"},
    "POI_Can_Chop": {"pin": "Chop Can", "category": "Landmarks"},
    "POI_Can_CrushedLaBise": {"pin": "Crushed La Bise Can"},
    "POI_Can_FizzamBlueberry": {"pin": ("Fizzam Can", 137.16), "name": "Fizzam Blueberry Can", "approx": True},
    "POI_Can_FizzamChuberry": {"pin": ("Fizzam Can", 28.31), "name": "Fizzam Chuberry Can", "approx": True},
    "POI_Can_Jabby": {"pin": "Jabby Cola"},
    "POI_Can_Welp": {"pin": "Welp Flavordrink"},
    "POI_Cap_Gun": {"pin": "Buster Cap Gun"},
    "POI_Castle_Moldorc_Vista": {"pin": "Castle Moldorc Playset"},
    "POI_CharcoalHotSpring": {"pin": "Charcoal Hot Spring"},
    "POI_CootieCatcher": {"pin": "Cootie Catcher"},
    "POI_CrackedDirt_Glove": {"pin": "Abandoned Gardening Glove"},
    "POI_Defense_Point_Haze": {"pin": (-36.68, -65.32), "name": "Mix.R: Haze"},
    "POI_Defense_Point_Hedge": {"pin": (142.15, -59.84), "name": "Mix.R: Hedge"},
    "POI_Defense_Point_RedAnthill": {"pin": (-40.72, -5.51), "name": "Mix.R: Red Anthill"},
    "POI_Defense_Point_Sandbox": {"pin": (-139.32, -63.91), "name": "Mix.R: Sandbox"},
    "POI_Defense_Point_Super_Jungle": {"pin": (44.37, 71.35), "name": "Super Mix.R: Tire"},
    "POI_Defense_Point_Super_Lawnmower": {"pin": (69.98, 81.49), "name": "Super Mix.R: Lawnmower"},
    "POI_Defense_Point_Super_MiniHegde": {"pin": (145.02, 61.76), "name": "Super Mix.R: Fence"},
    "POI_Defense_Point_WesternStep": {"pin": (-145.92, 38.80), "name": "Mix.R: Grill"},
    "POI_ExposedPipe_Haze": {"pin": ("Exposed White Pipe", -82.47), "name": "Exposed White Pipe (Haze)"},
    "POI_ExposedPipe_WeedArea": {"pin": ("Exposed White Pipe", -116.97), "name": "Exposed White Pipe (Weeds)"},
    "POI_Field_Station_BrickWall": {"pin": "Moldorc", "name": "Field Station: Moldorc", "approx": True},
    "POI_Field_Station_Cave": {"pin": "Larva Cave", "name": "Field Station: Larva Cave"},
    "POI_Field_Station_EastSteps": {"pin": "Stinkbug", "name": "Field Station: Stinkbug", "approx": True},
    "POI_Field_Station_Grasslands_Chop_Can": {"pin": ("Chop Can", 43.84), "name": "Field Station: Chop Can"},
    "POI_Field_Station_Grasslands_Intro": {"pin": ("Mysterious Machine", -6.80), "name": "Field Station: Mysterious Machine"},
    "POI_Field_Station_Grasslands_Porch_Branch": {"pin": "Oak Branch", "name": "Field Station: Oak Branch", "approx": True},
    "POI_Field_Station_Grasslands_Rooty_Flood": {"pin": "North Grasslands", "name": "Field Station: North Grasslands", "approx": True},
    "POI_Field_Station_Haze": {"pin": "Haze Field", "name": "Field Station: Haze"},
    "POI_Field_Station_Hedge": {"pin": ("Hedge", 69.07), "name": "Field Station: Hedge"},
    "POI_Field_Station_JavaMatic": {"pin": "Shed Deck", "name": "Field Station: Shed Deck", "approx": True},
    "POI_Field_Station_Jungle": {"pin": "Tire Field", "name": "Field Station: Tire Field", "approx": True},
    "POI_Field_Station_Junkyard": {"pin": ("Wheelbarrow", 145.50), "name": "Field Station: Wheelbarrow", "approx": True},
    "POI_Field_Station_Oak": {"pin": "Flower Bed", "name": "Field Station: Flower Bed", "approx": True},
    "POI_Field_Station_PicnicTable": {"pin": "Picnic Table", "name": "Field Station: Picnic Table"},
    "POI_Field_Station_Sandbox": {"pin": ("Sandbox", -100.04), "name": "Field Station: Sandbox"},
    "POI_Field_Station_StorageBox": {"pin": "Brawny Boy", "name": "Field Station: Brawny Boy", "approx": True},
    "POI_Field_Station_Stump": {"pin": ("Stump", 124.45), "name": "Field Station: Stump"},
    "POI_Field_Station_Termite_Wood_Pile": {"pin": "Wood Pile", "name": "Field Station: Wood Pile"},
    "POI_Field_Station_Trash": {"pin": "Trash Heap", "name": "Field Station: Trash Heap"},
    "POI_Field_Station_Undershed": {"pin": ("Undershed", -48.92), "name": "Field Station: Undershed"},
    "POI_Field_Station_UpperPond": {"pin": "Pond", "name": "Field Station: Koi Pond", "approx": True},
    "POI_FlyingDisc": {"pin": "Flingman Flying Disc"},
    "POI_Frankenline": {"pin": "Frankenline"},
    "POI_GardenGnome": {"pin": "Garden Gnome"},
    "POI_Haze_Lab": {"pin": "Haze Laboratory"},
    "POI_Hedge_Ascent": {"pin": "Hedge Ascent"},
    "POI_Hedge_Lab": {"pin": "Hedge Laboratory"},
    "POI_Hedge_Lab_Destroyed_Entrance": {"pin": "Hedge Lab Entrance"},
    "POI_JavaMatic": {"pin": "JavaMatic"},
    "POI_JavamaticOutPost": {"pin": "JavaMatic Storage"},
    "POI_Juicebox_Apricop": {"pin": "Punch-O", "name": "Apricop Punch-O"},
    "POI_Juicebox_ArmedRaspberry": {"pin": "Armed Raspberry Punch-O"},
    "POI_Juicebox_LemonCrime": {"pin": "Lemon Crime Punch-O"},
    "POI_Juicebox_PeachFuzz": {"pin": "Peach Fuzz Punch-O"},
    "POI_Juicebox_Tropicop": {"pin": "Tropicop Punch-O"},
    "POI_Lawnmower": {"pin": ("Lawnmower", 69.38)},
    "POI_MarshBaseball": {"pin": ("Baseball", -10.91)},
    "POI_MilkMolarBottle": {"pin": ("Milk Molar Bottle", -125.94)},
    "POI_Mint_Container": {"pin": "Candy Dispenser", "approx": True},
    "POI_MysteriousLab": {"pin": "Mysterious Lab"},
    "POI_NewGamePlusMachine": {"pin": ("Mysterious Machine", 8.98)},
    "POI_Oak_Lab": {"pin": "Oak Laboratory"},
    "POI_PicnicTable_Cooler": {"pin": "Cooler Box"},
    "POI_PicnicTable_Shovel": {"pin": "Leaning Shovel"},
    "POI_Picnic_Dungeon": {"pin": "Minotaur Maze's End"},
    "POI_PondLabDome": {"pin": "Pond Dome"},
    "POI_PondLabExit": {"pin": "Pond Laboratory", "name": "Pond Lab Exit", "approx": True},
    "POI_PondPagoda": {"pin": (93.62, 37.01), "name": "Pagoda"},
    "POI_PondPlantPot": {"pin": "Sunken Pot"},
    "POI_RottedStump": {"pin": ("Stump", 118.07), "name": "Rotted Stump"},
    "POI_SCAB_ShedPorch": {"pin": "Full-Sized SCA.B"},
    "POI_Sandbox_LabOutpost": {"pin": "Sandbox Outpost Laboratory"},
    "POI_ShristyToyCar": {"pin": "Christy Doll Car"},
    "POI_StumpLab": {"pin": "Stump Laboratory Outpost"},
    "POI_TazTLarge": {"pin": "Large Disassembled TAYZ.T"},
    "POI_Trash_CRT": {"pin": "Trashed AARTZ 3000"},
    "POI_Undershed_Entrance": {"pin": "Undershed Entrance"},
    "POI_Undershed_Lab": {"pin": "Undershed Laboratory"},
    "POI_Undershed_Sinkhole": {"pin": "Undershed Sinkhole"},
    "POI_Upperyard_Ascent": {"pin": "Upper Yard Ascent"},
    "POI_WaspNest": {"pin": "Wasp Nest"},
    "POI_WeddingRing": {"pin": "Wedding Ring"},
    "POI_Wheelbarrow": {"pin": ("Wheelbarrow", 129.76)},
    "POI_WoodPileEntrance": {"pin": "Wood Pile Entrance"},
    "POI_WormHoleContainer": {"pin": "Rocket Shaped Candy Container", "approx": True},
    "POI_YogiSwoleHead": {"pin": "Yogi Swole Head"},
    "POI_YokedGirthHead": {"pin": "Yoked Girth Head"},
    "POI_YokedGirthPackaging": {"pin": "Yoked Girth Blister Pack"},
}
PIN_SUBCATEGORIES = ("Landmarks", "Field Stations", "Laboratory", "Mix.R", "Area of Interests")

# Our check / item name -> the wiki's name, where they differ (armor pieces
# have their own names in the game; a few utilities and smoothies too).
WIKI_NAMES = {
    "Clover Head Armor": "Clover Hood", "Clover Chest Armor": "Clover Poncho", "Clover Leg Armor": "Clover Shin Guards",
    "Acorn Head Armor": "Acorn Face Mask", "Acorn Chest Armor": "Acorn Chestplate", "Acorn Leg Armor": "Acorn Leg Plates",
    "Grub Head Armor": "Grub Goggles", "Grub Chest Armor": "Grub Vest", "Grub Leg Armor": "Grub Leggings",
    "Ladybug Head Armor": "Ladybug Faceplate", "Ladybug Chest Armor": "Ladybug Chestplate",
    "Ladybug Leg Armor": "Ladybug Shin Guards",
    "Bee Head Armor": "Bee Face Mask", "Bee Chest Armor": "Bee Shoulder Pads", "Bee Leg Armor": "Bee Shin Guards",
    "Red Ant Head Armor": "Red Ant Helmet", "Red Ant Chest Armor": "Red Ant Arm Guards",
    "Red Ant Leg Armor": "Red Ant Knee Guards",
    "Black Ant Head Armor": "Black Ant Helmet", "Black Ant Chest Armor": "Black Ant Chestplate",
    "Black Ant Leg Armor": "Black Ant Legplates",
    "Spider Head Armor": "Spider Hood", "Spider Chest Armor": "Spider Shoulder Guard",
    "Spider Leg Armor": "Spider Knee Pads",
    "Roly Poly Head Armor": "Roly Poly Helmet", "Roly Poly Chest Armor": "Roly Poly Breastplate",
    "Roly Poly Leg Armor": "Roly Poly Legplates",
    "Antlion Head Armor": "Antlion Wide Brim", "Antlion Chest Armor": "Antlion Poncho",
    "Antlion Leg Armor": "Antlion Spurs",
    "Black Ox Head Armor": "Black Ox Helm", "Black Ox Chest Armor": "Black Ox Harness",
    "Black Ox Leg Armor": "Black Ox Legwraps",
    "Mantis Head Armor": "Assassin's Mask", "Mantis Chest Armor": "Assassin's Chestplate",
    "Mantis Leg Armor": "Assassin's Greaves",
    "Koi Head Armor": "Koi Scale Helmet", "Koi Chest Armor": "Koi Scale Chestplate", "Koi Leg Armor": "Koi Scale Greaves",
    "Fire Ant Head Armor": "Fire Ant Helmet", "Fire Ant Chest Armor": "Fire Ant Chestplate",
    "Fire Ant Leg Armor": "Fire Ant Legplates",
    "Moth Head Armor": "Moth Wrap", "Moth Chest Armor": "Moth Robe", "Moth Leg Armor": "Moth Leggings",
    "Wasp Head Armor": "Wasp Morion", "Wasp Chest Armor": "Wasp Breastplate", "Wasp Leg Armor": "Wasp Greaves",
    "Fiber Smoothie": "Green Machine", "Berry Smoothie": "Hedge Lord", "Aphid Smoothie": "Boost Juice",
    "Water Breathing Smoothie": "Liquid Gills", "Swim Speed Smoothie": "Fluid Flippers",
    "Attack Smoothie": "Liquid Rage", "Ant Smoothie": "Worker's Comp", "Fuzz On The Rocks Smoothie": "Fuzz on the Rocks",
    "Gastro Goo Smoothie": "Gastro Goo", "Human Food Smoothie": "Human Food", "Wasp Smoothie": "Waspidote",
    "Bandage": "Fiber Bandage", "Armor Repair Kit": "Armor Glue", "Advanced Armor Repair Kit": "Super Armor Glue",
    "Everchar Torch": "EverChar Torch", "Healing Bomb": "Healbasa", "Smoke Screen": "Shinobi Sneeze",
    "Repair Hammer": "Repair Tool", "Salt Pickaxe": "Salt Chipper", "Tadpole Pudding": "Tadpoloca Pudding",
}


def fetch(url: str, cache_name: str | None = None, binary: bool = False, retries: int = 3):
    path = CACHE / cache_name if cache_name else None
    if path and path.exists():
        data = path.read_bytes()
        return data if binary else data.decode("utf-8")
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            break
        except Exception:  # noqa: BLE001 -- network hiccups: retry, then give up loudly
            if attempt == retries - 1:
                raise
            time.sleep(2)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data if binary else data.decode("utf-8")


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------
def wand_data() -> dict:
    html = fetch(WAND_PAGE, "wand.html")
    pattern = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
    text = "".join(json.loads('"' + chunk + '"') for chunk in pattern.findall(html))
    decoder = json.JSONDecoder()
    metadata = decoder.raw_decode(text, text.find('{"minZoom"'))[0]
    features, pos = [], 0
    while True:
        i = text.find('{"type":"Feature","geometry"', pos)
        if i < 0:
            break
        feature, pos = decoder.raw_decode(text, i)
        features.append(feature)
    if not features:
        raise SystemExit("no pins found on the wand.com page -- its format changed?")
    return {"metadata": metadata, "features": features}


def mercator(lng: float, lat: float):
    """lng/lat -> (u, v) in 0..1 over the whole tile pyramid."""
    u = (lng + 180) / 360
    v = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2
    return u, v


def build_map(data: dict) -> None:
    from PIL import Image

    base = data["metadata"]["baseTilePath"]
    count = 2 ** MAP_ZOOM
    image = None
    for row in range(count):
        for col in range(count):
            # wand.com's tile URLs are {z}/{row}/{col}
            tile = fetch(f"{base}/{MAP_ZOOM}/{row}/{col}.webp", f"tiles/{MAP_ZOOM}_{row}_{col}.webp", binary=True)
            img = Image.open(io.BytesIO(tile)).convert("RGB")
            if image is None:
                size = img.size[0]
                image = Image.new("RGB", (size * count, size * count))
            image.paste(img, (col * size, row * size))
        print(f"  map row {row + 1}/{count}")
    image = image.quantize(colors=32)
    OUT.mkdir(parents=True, exist_ok=True)
    image.save(OUT / "map.png", optimize=True)
    print(f"Wrote {OUT / 'map.png'} ({image.size[0]} px, {(OUT / 'map.png').stat().st_size // 1024} KB)")


def build_pins(data: dict) -> None:
    subs = {s["externalId"]: s["title"] for s in data["metadata"]["subcategories"]}
    pins = []
    for feature in data["features"]:
        category = subs.get(feature["properties"].get("subcategoryExternalId"))
        if category in PIN_SUBCATEGORIES:
            lng, lat = feature["geometry"]["coordinates"]
            pins.append((category, (feature["properties"].get("title") or "").strip(), lng, lat))

    def find(spec, wanted_category=None):
        if isinstance(spec, tuple) and isinstance(spec[0], (int, float)):
            matches = [p for p in pins if abs(p[2] - spec[0]) < 0.05 and abs(p[3] - spec[1]) < 0.05]
        elif isinstance(spec, tuple):
            matches = [p for p in pins if p[1] == spec[0] and abs(p[2] - spec[1]) < 0.05]
        else:
            matches = [p for p in pins if p[1] == spec and p[0] != "Area of Interests"]
            if wanted_category:
                matches = [p for p in matches if p[0] == wanted_category]
        if len(matches) != 1:
            raise SystemExit(f"pin {spec!r}: {len(matches)} matches")
        return matches[0]

    out = {}
    for asset, entry in LANDMARK_PINS.items():
        _cat, title, lng, lat = find(entry["pin"], entry.get("category"))
        u, v = mercator(lng, lat)
        out[asset] = {"title": entry.get("name", title), "u": round(u, 5), "v": round(v, 5),
                      "approx": bool(entry.get("approx"))}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "landmark_pins.json").write_text(json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")
    print(f"Wrote {OUT / 'landmark_pins.json'} ({len(out)} pins, "
          f"{sum(1 for e in out.values() if e['approx'])} approximate)")


# ---------------------------------------------------------------------------
# Wiki: recipes and icons
# ---------------------------------------------------------------------------
def parse_recipes(wikitext: str) -> dict:
    recipes: dict = {}
    for match in re.finditer(r"\{\{Recipe:(Item|Smoothie)\|([^{}]*)\}\}", wikitext):
        kind, body = match.groups()
        fields = {}
        for part in body.split("|"):
            if "=" in part:
                key, value = part.split("=", 1)
                fields[key.strip()] = re.sub(r"\[\[|\]\]", "", value).strip()
        if kind == "Smoothie":
            name = fields.get("Smoothie")
            materials = [[fields[k], 1] for k in ("Ingredient1", "Ingredient2", "Ingredient3") if fields.get(k)]
            station = "Smoothie Station"
        else:
            name = fields.get("Item")
            materials = []
            for n in range(1, 8):
                material = fields.get(f"Material{n}")
                if material:
                    qty = fields.get(f"Material{n}Quantity", "1")
                    materials.append([material, int(qty) if qty.isdigit() else qty])
            station = fields.get("Station", "")
        if name and materials:
            recipes.setdefault(name, []).append({"station": station, "materials": materials})
    return recipes


def needed_names() -> dict:
    """Every item / craft / ingredient name the tracker can show -> the
    name it has in Archipelago (the "=>" rename, which is usually the
    in-game name the wiki uses too)."""
    ns: dict = {}
    exec((APWORLD / "grounded_data.py").read_text(encoding="utf-8"), ns)
    names = {}
    for loc, loc_id in ns["MOD_LOCATION_NAME_TO_ID"].items():
        for prefix in ("Item: ", "Craft: "):
            if loc.startswith(prefix):
                shown = ns["LOCATION_ID_TO_NAME"].get(loc_id, loc)
                names[loc[len(prefix):]] = shown.split(": ", 1)[1]
    rs = (APWORLD / "recipe_shuffle.py").read_text(encoding="utf-8")
    for name in re.findall(r'Material\("([^"]+)"', rs):
        names.setdefault(name, name)
    return names


def build_wiki() -> None:
    raw = fetch(f"{WIKI_API}?action=parse&page=Template:Recipe&prop=wikitext&format=json", "recipe_template.json")
    recipes = parse_recipes(json.loads(raw)["parse"]["wikitext"]["*"])
    ours = needed_names()
    wiki_name = {}
    for name, shown in ours.items():
        candidates = [WIKI_NAMES.get(name), shown, name]
        wiki_name[name] = next((c for c in candidates if c and c in recipes), WIKI_NAMES.get(name, shown))
    # Ingredients of the recipes we show need icons too.
    icon_names = set(wiki_name.values())
    for name in list(icon_names):
        for recipe in recipes.get(name, []):
            icon_names |= {m for m, _ in recipe["materials"]}
    kept = {name: recipes[name] for name in sorted(set(wiki_name.values())) if name in recipes}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "recipes.json").write_text(json.dumps({"names": wiki_name, "recipes": kept}, indent=1, sort_keys=True),
                                      encoding="utf-8")
    print(f"Wrote {OUT / 'recipes.json'} ({len(kept)} recipes; "
          f"{len([n for n in ours if wiki_name[n] not in recipes])} of our names have none, e.g. raw materials)")

    from PIL import Image

    icons = OUT / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    titles = sorted(icon_names)
    missing = []
    for start in range(0, len(titles), 40):
        batch = titles[start:start + 40]
        query = urllib.parse.urlencode({
            "action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 64,
            "titles": "|".join(f"File:{t}.png" for t in batch)})
        info = json.loads(fetch(f"{WIKI_API}?{query}"))
        pages = info["query"]["pages"]
        back = {n["to"]: n["from"] for n in info["query"].get("normalized", [])}
        for page in pages.values():
            title = back.get(page["title"], page["title"])[len("File:"):-len(".png")]
            image_info = page.get("imageinfo")
            if not image_info:
                missing.append(title)
                continue
            url = image_info[0].get("thumburl") or image_info[0]["url"]
            data = fetch(url, f"icons/{safe(title)}.img", binary=True)
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            img.thumbnail((64, 64))
            img.save(icons / f"{safe(title)}.png", optimize=True)
    print(f"Wrote {len(titles) - len(missing)} icons to {icons}; no wiki image for: {', '.join(sorted(missing)) or '-'}")
    build_sources(wiki_name[n] for n in ours)


def _clean(text: str) -> str:
    """Wiki markup -> plain text: [[a|b]] -> b, {{Icon|X|...}} -> X, lists joined."""
    text = re.sub(r"<br\s*/?>", ", ", text)
    text = re.sub(r"\{\{Icon\|([^|}]+)[^}]*\}\}", r"\1", text)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>|'{2,3}", "", text)
    parts = [part.strip(" *#:-") for part in re.split(r"\n|,", text)]
    return ", ".join(part for part in parts if part)


def build_sources(names) -> None:
    """The wiki infobox "source" field of every item page we can show
    (the Grounded 1 tab -- pages also have a Grounded 2 one)."""
    titles = sorted(set(names))
    sources = {}
    for start in range(0, len(titles), 40):
        batch = titles[start:start + 40]
        query = urllib.parse.urlencode({
            "action": "query", "format": "json", "prop": "revisions", "rvprop": "content", "rvslots": "main",
            "redirects": 1, "titles": "|".join(batch)})
        info = json.loads(fetch(f"{WIKI_API}?{query}", f"sources/{start}.json"))
        back = {r["to"]: r["from"] for r in info["query"].get("redirects", [])}
        back.update({n["to"]: n["from"] for n in info["query"].get("normalized", [])})
        for page in info["query"]["pages"].values():
            revisions = page.get("revisions")
            if not revisions:
                continue
            text = revisions[0]["slots"]["main"]["*"]
            text = text.split("Grounded 2", 1)[0] if "{{ImgTabber" in text else text
            match = re.search(r"\|\s*source\s*=(.*?)(?=\n\s*\||\n\}\})", text, re.S)
            if match and _clean(match.group(1)).lower() not in ("", "none"):
                title = page["title"]
                sources[back.get(title, title)] = _clean(match.group(1))
    (OUT / "sources.json").write_text(json.dumps(sources, indent=1, sort_keys=True), encoding="utf-8")
    print(f"Wrote {OUT / 'sources.json'} ({len(sources)} of {len(titles)} items have a source)")


def safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", action="store_true")
    parser.add_argument("--wiki", action="store_true")
    args = parser.parse_args()
    both = not (args.map or args.wiki)
    if args.map or both:
        data = wand_data()
        build_pins(data)
        build_map(data)
    if args.wiki or both:
        build_wiki()


if __name__ == "__main__":
    main()
