"""
Builds the GitHub release package:

    dist/GroundedArchipelago-<world_version>.zip
        grounded.apworld            -> Archipelago's custom_worlds folder
        GroundedArchipelago/        -> Grounded's ue4ss/Mods folder
        grounded_poptracker.zip     -> PopTracker's packs folder (optional)
        README.md, SETUP.md         -> overview / install guide
        LICENSE, NOTICE.md          -> if present in the project root

Only what players need: no tests, caches, IPC files, location_review.txt or
tools. The world version comes from apworld/grounded/archipelago.json --
bump it there before building a new release.

The wand.com map image and pin positions are left out by default (wand.com's
terms don't allow redistributing them; the Tracker's Map tab then says so).
--include-wand-map puts them back, for a build you only use yourself.

    python connector/tools/build_release.py [--include-wand-map]
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apworld_zip import WAND_DATA, world_version, write_apworld  # noqa: E402

PROJECT = Path(__file__).resolve().parents[2]
MOD_SRC = PROJECT / "game_mod" / "GroundedArchipelago"
TRACKER_SRC = PROJECT / "tracker" / "grounded_poptracker"
DIST = PROJECT / "dist"


def zip_folder(src: Path, dest: Path, arc_root: str) -> None:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(src.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                zf.write(path, Path(arc_root) / path.relative_to(src))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-wand-map", action="store_true",
                        help="keep the wand.com map/pins in the apworld (personal builds only)")
    args = parser.parse_args()

    version = world_version()
    name = f"GroundedArchipelago-{version}"
    stage = DIST / name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    skipped = write_apworld(stage / "grounded.apworld", exclude=() if args.include_wand_map else WAND_DATA)

    mod_dst = stage / "GroundedArchipelago"
    (mod_dst / "Scripts").mkdir(parents=True)
    for lua in sorted((MOD_SRC / "Scripts").glob("*.lua")):
        shutil.copy2(lua, mod_dst / "Scripts" / lua.name)
    shutil.copy2(MOD_SRC / "enabled.txt", mod_dst / "enabled.txt")

    if TRACKER_SRC.exists():
        zip_folder(TRACKER_SRC, stage / "grounded_poptracker.zip", "grounded_poptracker")

    shutil.copy2(PROJECT / "README.md", stage / "README.md")
    shutil.copy2(PROJECT / "apworld" / "grounded" / "docs" / "setup_en.md", stage / "SETUP.md")
    for extra in ("LICENSE", "LICENSE.md", "NOTICE.md"):
        if (PROJECT / extra).exists():
            shutil.copy2(PROJECT / extra, stage / extra)

    archive = DIST / f"{name}.zip"
    zip_folder(stage, archive, name)
    size_kb = archive.stat().st_size // 1024
    print(f"Built {archive} ({size_kb} KB)")
    print("  " + ", ".join(sorted(p.name for p in stage.iterdir())))
    if skipped:
        print(f"  left out of the apworld (wand.com data): {', '.join(skipped)}")


if __name__ == "__main__":
    main()
