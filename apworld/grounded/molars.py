"""
Milk Molar milestones: total molars collected, read by the mod as
UPlayerUpgradeComponent GetTotalSpentPoints() + GetRemainingUpgradePoints()
(only ever goes up). Not GameState's GetTotalMilkMolarCount() -- that's a
world-wide constant and fired every milestone on a fresh save.
"""
from __future__ import annotations

from typing import Dict, List

# Keep in sync with location_hooks.lua's MOLAR_MILESTONES / MOLAR_LOCATION_PREFIX.
MOLAR_MILESTONES: List[int] = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75]
MOLAR_LOCATION_PREFIX = "Molars: "

molar_location_names: List[str] = [
    MOLAR_LOCATION_PREFIX + str(threshold) for threshold in MOLAR_MILESTONES
]

BASE_ID = 9411000 + 7000

molar_location_name_to_id: Dict[str, int] = {
    name: BASE_ID + offset for offset, name in enumerate(molar_location_names)
}
