"""
Builds grounded.apworld from apworld/grounded -- shared by deploy.py and
build_release.py.

The zip gets the full manifest Archipelago's own build writes (see its
setup.py): apworld/grounded/archipelago.json (game, authors, world_version,
minimum_ap_version) plus the container fields "version" and
"compatible_version". Without a manifest, Archipelago 0.6.x logs "Invalid
or missing manifest" and 0.7.0 won't load the apworld at all.
"""
import json
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
APWORLD_SRC = PROJECT / "apworld" / "grounded"
MANIFEST = APWORLD_SRC / "archipelago.json"
CONTAINER_VERSION = 7  # worlds/Files.py's APWorldContainer, Archipelago 0.6.x

# Bundled data that comes from wand.com (WeMod), whose terms don't allow
# redistributing it -- left out of release builds unless asked for.
WAND_DATA = ("data/map.png", "data/landmark_pins.json")


def manifest() -> dict:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    data.update({"version": CONTAINER_VERSION, "compatible_version": CONTAINER_VERSION})
    return data


def world_version() -> str:
    return manifest().get("world_version", "0.0.0")


def write_apworld(dest: Path, exclude=()) -> list:
    """Writes the apworld to `dest`. `exclude`: paths relative to
    apworld/grounded (e.g. WAND_DATA). Returns the excluded paths found."""
    skipped = []
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(APWORLD_SRC.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(APWORLD_SRC)
            if "__pycache__" in rel.parts or rel.parts[0] == "test" or rel.name == "archipelago.json":
                continue
            if rel.as_posix() in exclude:
                skipped.append(rel.as_posix())
                continue
            zf.write(path, Path("grounded") / rel)
        zf.writestr("grounded/archipelago.json", json.dumps(manifest(), indent=1))
    return skipped
