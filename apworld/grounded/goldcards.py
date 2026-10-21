"""
Gold Creature Card checks: each card is a Table_AllItems row named
Bestiary<Creature>Gold; location_hooks.lua's pickup hook reports
"Gold Card: <row>". The gold_cards goal counts locked "Gold Card Progress"
items (Gold Card Goal Amount of them).
"""
from __future__ import annotations

from typing import List, Tuple

GOLD_CARD_ROW_NAMES: List[str] = [
    "BestiaryAntBlackSoldierGold",
    "BestiaryAntBlackWorkerGold",
    "BestiaryAntFireSoldierGold",
    "BestiaryAntFireWorkerGold",
    "BestiaryAntInfectedSoldierGold",
    "BestiaryAntInfectedWorkerGold",
    "BestiaryAntRedSoldierGold",
    "BestiaryAntRedWorkerGold",
    "BestiaryAntlionGold",
    "BestiaryAphidGold",
    "BestiaryArcRBossGold",
    "BestiaryArcRGold",
    "BestiaryBeeGold",
    "BestiaryBlackOxGold",
    "BestiaryBombardierGold",
    "BestiaryBossIBMGold",
    "BestiaryFireflyGold",
    "BestiaryGnatGold",
    "BestiaryGnatInfectedGold",
    "BestiaryGnatMeatyGold",
    "BestiaryGrubGold",
    "BestiaryLadybugGold",
    "BestiaryLadybugInfectedGold",
    "BestiaryLadybugUpperyardGold",
    "BestiaryLarvaCharcoalGold",
    "BestiaryLarvaGold",
    "BestiaryLarvaInfectedGold",
    "BestiaryMantGold",
    "BestiaryMantisGold",
    "BestiaryMiteDustGold",
    "BestiaryMiteGold",
    "BestiaryMiteInfectedGold",
    "BestiaryMiteTickGold",
    "BestiaryMosquitoGold",
    "BestiaryMosquitoTigerGold",
    "BestiaryMothGold",
    "BestiaryRolyPolyGold",
    "BestiaryRolyPolySicklyGold",
    "BestiaryScarabGold",
    "BestiarySchmectorGold",
    "BestiarySpiderBlackWidowGold",
    "BestiarySpiderBossBroodmotherGold",
    "BestiarySpiderDivingBellGold",
    "BestiarySpiderOrbGold",
    "BestiarySpiderOrbJrGold",
    "BestiarySpiderWolfGold",
    "BestiarySpiderWolfInfectedGold",
    "BestiarySpiderlingGold",
    "BestiarySpiderlingWidowGold",
    "BestiaryStinkbugGold",
    "BestiaryStinkbugGreenShieldGold",
    "BestiaryTadpoleGold",
    "BestiaryTazTGold",
    "BestiaryTazTRuzTGold",
    "BestiaryTermiteKingGold",
    "BestiaryTermiteSoldierGold",
    "BestiaryTermiteWorkerGold",
    "BestiaryWaspDroneGold",
    "BestiaryWaspGold",
    "BestiaryWaspQueenGold",
    "BestiaryWaterBoatmanGold",
    "BestiaryWaterFleaGold",
    "BestiaryWaterFleaSpinyGold",
    "BestiaryWeevilGold",
    "BestiaryWeevilInfectedGold",
]

# Keep in sync with location_hooks.lua's GOLD_CARD_LOCATION_PREFIX.
GOLD_CARD_LOCATION_PREFIX = "Gold Card: "
GOLD_CARD_PROGRESS_ITEM = "Gold Card Progress"

gold_card_location_names: List[str] = [
    GOLD_CARD_LOCATION_PREFIX + name for name in GOLD_CARD_ROW_NAMES
]

gold_card_event_locations: List[Tuple[str, str, str]] = [
    (name, "Grasslands", GOLD_CARD_PROGRESS_ITEM) for name in gold_card_location_names
]

BASE_ID = 9411000 + 4000

gold_card_location_name_to_id = {
    name: BASE_ID + offset for offset, name in enumerate(gold_card_location_names)
}
