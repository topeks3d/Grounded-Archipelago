"""
Progressive player upgrades -- AP items that do what Milk Molars normally do:

  ProgressiveMolarUpgrades: one item per tier of BURG.L's Milk Molar
  upgrades (PlayerUpgradesTable rows Health, Stamina, Thirst, Healing,
  Perks). The mod grants the tiers with the game's UnlockPlayerUpgrade
  command and makes the molar upgrades unaffordable, so molars no longer
  buy anything (molar checks still count them).

Keep in sync with player_upgrades.lua (via ap_data.lua).
"""
from __future__ import annotations

from typing import Dict, Tuple

# AP item -> (PlayerUpgradesTable row, tiers). Tier counts from the game's
# upgrade screen (Health 6, Perks = Max Active Mutations 3, the rest 5).
MOLAR_UPGRADES: Dict[str, Tuple[str, int]] = {
    "Progressive Max Health": ("Health", 6),
    "Progressive Max Stamina": ("Stamina", 5),
    "Progressive Hunger and Thirst": ("Thirst", 5),
    "Progressive Healing": ("Healing", 5),
    "Progressive Mutation Slot": ("Perks", 3),
}

# Logic with ProgressiveMolarUpgrades on: combat tier -> Max Health copies.
# Without molars, a Tier 2/3 fight on base health is a lot to ask.
HEALTH_FOR_COMBAT_TIER: Dict[int, int] = {2: 1, 3: 3}
