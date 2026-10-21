"""
grounded_connector.py

Standalone convenience entry point for running the Grounded client from a
terminal without going through Archipelago's own Launcher. This is mainly
useful for a source-checkout/dev workflow (e.g. on Linux, or if you'd
rather not use the Launcher GUI at all).

**If you installed Archipelago via the Windows installer (e.g. it lives at
C:\\ProgramData\\Archipelago), use the Launcher instead -- see the top-level
README and connector/README.md for why.** The short version: this script
needs CommonClient.py importable as loose source on disk, which a source
checkout has and the compiled installer generally doesn't (its Python
modules are bundled inside lib\\library.zip). The Launcher route
(`ArchipelagoLauncher.exe "Grounded Client" --ipc-dir ... --connect ... `
`--name ... --nogui`) runs inside that already-configured environment
directly and doesn't have this problem.

Usage (source checkout only):
    python grounded_connector.py --archipelago-dir /path/to/Archipelago \\
        --ipc-dir "/path/to/Grounded/.../ue4ss/Mods/GroundedArchipelago/ipc" \\
        --connect archipelago.gg:38281 --name YourSlotName --nogui
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_APWORLD_DIR = _PROJECT_ROOT / "apworld"


def _early_arg(flag: str) -> str | None:
    for i, arg in enumerate(sys.argv):
        if arg == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if arg.startswith(flag + "="):
            return arg.split("=", 1)[1]
    return None


def _bootstrap_archipelago_path() -> None:
    root_candidates = []
    explicit = _early_arg("--archipelago-dir")
    if explicit:
        root_candidates.append(Path(explicit).resolve())
    env_dir = os.environ.get("ARCHIPELAGO_DIR")
    if env_dir:
        root_candidates.append(Path(env_dir).resolve())
    root_candidates.append(Path(__file__).resolve().parent)
    root_candidates.append(Path(__file__).resolve().parent.parent)

    subdir_candidates = ["", "lib", "_internal", "_internal/lib"]

    checked = []
    for root in root_candidates:
        for sub in subdir_candidates:
            candidate = (root / sub) if sub else root
            checked.append(candidate)
            if (candidate / "CommonClient.py").exists():
                sys.path.insert(0, str(candidate))
                return

    print(
        "Could not find CommonClient.py under any of:\n  "
        + "\n  ".join(str(c) for c in checked)
        + "\n\nThis script only works against a source checkout of Archipelago "
        "(https://github.com/ArchipelagoMW/Archipelago), where CommonClient.py "
        "sits as loose source. If you installed Archipelago via the Windows "
        "installer instead, use the Launcher route described at the top of "
        "this file / in connector/README.md -- it doesn't have this problem.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _strip_own_arg(flag: str) -> None:
    """Remove --archipelago-dir <value> from sys.argv before handing the
    rest to client.launch(), since CommonClient's own arg parser doesn't
    know about it."""
    i = 0
    while i < len(sys.argv):
        if sys.argv[i] == flag:
            del sys.argv[i:i + 2]
        elif sys.argv[i].startswith(flag + "="):
            del sys.argv[i]
        else:
            i += 1


if __name__ == "__main__":
    _bootstrap_archipelago_path()
    _strip_own_arg("--archipelago-dir")

    if str(_APWORLD_DIR) not in sys.path:
        sys.path.insert(0, str(_APWORLD_DIR))

    from grounded.client import launch

    launch(*sys.argv[1:])
