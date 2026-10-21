"""
Kill checks for the seven major bosses. Reported by location_hooks.lua's
creature-death hook. "Mant" and "Mantis" are different creatures.
"""
from __future__ import annotations

from typing import Dict, List

KILLSANITY_BOSS_NAMES: List[str] = [
    "Assistant Manager",
    "Hedge Broodmother",
    "Mant",
    "Mantis",
    "Director Schmector",
    "Wasp Queen",
    "Black Widow",
]

# Keep in sync with location_hooks.lua's KILL_LOCATION_PREFIX.
KILL_LOCATION_PREFIX = "Kill: "

killsanity_location_names: List[str] = [
    KILL_LOCATION_PREFIX + name for name in KILLSANITY_BOSS_NAMES
]

BASE_ID = 9411000 + 5000

killsanity_location_name_to_id: Dict[str, int] = {
    name: BASE_ID + offset for offset, name in enumerate(killsanity_location_names)
}
