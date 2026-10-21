"""
Mutation milestones (MutationChecks option): how many mutations the player
has unlocked (UPerkComponent.Perks, Tier >= 0 -- see mutations.lua, which
gets MUTATION_MILESTONES through the generated ap_data.lua).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

MUTATION_PREFIX = "Mutations: "
MUTATION_MILESTONES: List[int] = [1, 3, 5, 8, 12, 16, 20, 25]


def mutation_tokens(threshold: int) -> Tuple[str, ...]:
    if threshold <= 3:
        return ("c1",)
    if threshold <= 8:
        return ("c2",)
    if threshold <= 12:
        return ("c2", "gas", "dive")
    if threshold <= 16:
        return ("c3",)
    return ("c3", "undershed")


mutation_location_names: List[str] = [MUTATION_PREFIX + str(t) for t in MUTATION_MILESTONES]
MUTATION_REQUIREMENTS: Dict[str, Tuple[str, ...]] = {
    MUTATION_PREFIX + str(t): mutation_tokens(t) for t in MUTATION_MILESTONES
}
