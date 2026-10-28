"""
The client's nearest-unchecked compass: a line over the game naming the
closest landmark check you haven't done yet, how far it is and which way,
within a radius you choose (Tracker tab, or /compass and /compass_radius).

The mod writes the player's position and facing to ipc/compass.json while
the compass is on, and every landmark position it has seen loaded to
ipc/landmark_positions.json (compass.lua). Game units are centimetres.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, Optional, Tuple

DEFAULT_RADIUS_M = 100
MIN_RADIUS_M, MAX_RADIUS_M = 20, 400
# Height difference worth mentioning, in metres.
_LEVEL_M = 8

_ARROWS = ("ahead", "ahead-right", "right", "behind-right", "behind", "behind-left", "left", "ahead-left")


def direction(player: Dict[str, float], target: Dict[str, float]) -> str:
    """Where `target` is relative to the way the player faces. Unreal's yaw
    turns from +X toward +Y, so a positive angle is to the right."""
    bearing = math.degrees(math.atan2(target["y"] - player["y"], target["x"] - player["x"]))
    relative = (bearing - player.get("yaw", 0.0) + 180.0) % 360.0 - 180.0
    return _ARROWS[int(((relative + 22.5) % 360.0) // 45.0)]


def nearest(player: Dict[str, float], targets: Iterable[Tuple[str, Dict[str, float]]],
            radius_m: float) -> Optional[Tuple[str, float, Dict[str, float]]]:
    """(name, metres, position) of the closest target within radius_m."""
    best = None
    for name, pos in targets:
        metres = math.dist((player["x"], player["y"], player["z"]), (pos["x"], pos["y"], pos["z"])) / 100.0
        if metres <= radius_m and (best is None or metres < best[1]):
            best = (name, metres, pos)
    return best


def describe(player: Optional[Dict[str, float]], positions: Dict[str, Dict[str, float]],
             wanted: Dict[str, str], radius_m: float) -> Optional[str]:
    """The compass line, or None when nothing unchecked is in range.
    `positions`: landmark asset name -> position; `wanted`: landmark asset
    name -> display name, for the landmark checks still to do."""
    if not player or not all(k in player for k in ("x", "y", "z")):
        return None
    targets = [(name, pos) for name, pos in positions.items()
               if name in wanted and all(k in pos for k in ("x", "y", "z"))]
    found = nearest(player, targets, radius_m)
    if not found:
        return None
    name, metres, pos = found
    height = (pos["z"] - player["z"]) / 100.0
    level = " above" if height > _LEVEL_M else " below" if height < -_LEVEL_M else ""
    return f"{wanted[name]}  ·  {metres:.0f} m {direction(player, pos)}{level}"
