"""
Deploys this project to the local game + Archipelago install:

  1. game_mod/GroundedArchipelago/Scripts -> the Steam Grounded UE4SS mod
     folder (ipc/ is never touched).
  2. apworld/grounded -> a fresh grounded.apworld in Archipelago's
     custom_worlds (tests and __pycache__ left out).

Both are backed up first (to --backup-dir, default: a timestamped folder
in the system temp dir).

config.lua is only copied when the installed one has no test_mode section
yet (i.e. predates it) or with --config, so your local test-mode settings
survive redeploys.

    python connector/tools/deploy.py [--mod-only | --apworld-only] [--config]
"""
import argparse
import os
import shutil
import tempfile
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apworld_zip import world_version, write_apworld  # noqa: E402

PROJECT = Path(__file__).resolve().parents[2]
MOD_SRC = PROJECT / "game_mod" / "GroundedArchipelago"
MOD_DST = Path(r"C:\SteamLibrary\steamapps\common\Grounded\Maine\Binaries\Win64\ue4ss\Mods\GroundedArchipelago")
APWORLD_DST = Path(r"C:\ProgramData\Archipelago\custom_worlds\grounded.apworld")


def deploy_mod(backup: Path, force_config: bool) -> None:
    if MOD_DST.exists():
        shutil.copytree(MOD_DST, backup / "GroundedArchipelago", ignore=shutil.ignore_patterns("ipc"))
    dst_scripts = MOD_DST / "Scripts"
    dst_scripts.mkdir(parents=True, exist_ok=True)
    installed_config = dst_scripts / "config.lua"
    keep_config = (not force_config and installed_config.exists()
                   and "config.test_mode" in installed_config.read_text(encoding="utf-8"))
    copied = 0
    for src in (MOD_SRC / "Scripts").glob("*.lua"):
        if src.name == "config.lua" and keep_config:
            continue
        shutil.copy2(src, dst_scripts / src.name)
        copied += 1
    for extra in ("enabled.txt",):
        if (MOD_SRC / extra).exists():
            shutil.copy2(MOD_SRC / extra, MOD_DST / extra)
    print(f"Mod: copied {copied} script(s) to {dst_scripts}"
          + (" (kept your installed config.lua -- pass --config to replace it)" if keep_config else ""))


def deploy_apworld(backup: Path) -> None:
    if APWORLD_DST.exists():
        shutil.copy2(APWORLD_DST, backup / APWORLD_DST.name)
    tmp = APWORLD_DST.with_suffix(".apworld.tmp")
    write_apworld(tmp)  # local deploys keep the wand.com map (personal use)
    os.replace(tmp, APWORLD_DST)
    print(f"Apworld: wrote {APWORLD_DST} (world version {world_version()})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mod-only", action="store_true")
    parser.add_argument("--apworld-only", action="store_true")
    parser.add_argument("--config", action="store_true", help="also overwrite the installed config.lua")
    parser.add_argument("--backup-dir", type=Path,
                        default=Path(tempfile.gettempdir()) / f"grounded_deploy_backup_{time.strftime('%Y%m%d_%H%M%S')}")
    args = parser.parse_args()
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"Backups: {args.backup_dir}")
    if not args.apworld_only:
        deploy_mod(args.backup_dir, args.config)
    if not args.mod_only:
        deploy_apworld(args.backup_dir)


if __name__ == "__main__":
    main()
