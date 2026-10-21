from dataclasses import dataclass

from Options import Choice, DeathLink, DefaultOnToggle, OptionSet, PerGameCommonOptions, Range, StartInventoryPool, Toggle

from .killsanity import KILLSANITY_BOSS_NAMES


class Goal(Choice):
    """What you need to do to complete your Grounded world.

    embiggening: Beat Director Schmector (or the Mant, if he's excluded),
    then finish the game's ending ("Go Big Or Never Go Home").

    boss_only: Kill every major boss -- Assistant Manager, Hedge
    Broodmother, Mant, Mantis, Director Schmector, Wasp Queen, Black Widow
    -- except any listed in Excluded Bosses.

    infected_broodmother: Kill the Infected Broodmother.

    infected_broodmother_and_embiggening: Both of the above.

    gold_cards: Collect Gold Card Goal Amount of the 65 gold Creature
    Cards. See Gold Card Drop Chance if you don't want to rely on their
    very low vanilla drop odds.

    itemsanity: Pick up every tracked item at least once.

    story_boss_only: Kill just Assistant Manager, Mant, and Director
    Schmector -- the subset of boss_only tied to the main story line.

    short: Kill just Assistant Manager and Mant -- a smaller subset of
    story_boss_only, for a quick playthrough.
    """
    display_name = "Goal"
    option_embiggening = 0
    option_boss_only = 1
    option_infected_broodmother = 2
    option_infected_broodmother_and_embiggening = 3
    option_gold_cards = 4
    option_itemsanity = 5
    option_story_boss_only = 6
    option_short = 7
    default = 0


class ExcludedBosses(OptionSet):
    """Bosses you don't want to be required to fight (boss_only goal; for
    embiggening, excluding Director Schmector makes the Mant the final boss).
    Valid names: Assistant Manager, Hedge Broodmother, Mant, Mantis,
    Director Schmector, Wasp Queen, Black Widow."""
    display_name = "Excluded Bosses"
    valid_keys = frozenset(KILLSANITY_BOSS_NAMES)
    default = frozenset()


class IncludeBossChecks(DefaultOnToggle):
    """Include "Defeat <boss>" locations as checks.

    Turn this off if you'd rather not be required to fight things like the
    Broodmother or Black Widow to find items."""
    display_name = "Include Boss Checks"


class GoldCardDropChance(Range):
    """Drop chance for every creature's gold Creature Card, on a 0-50 scale
    where 50 means 100%. The default 5 is a 10% chance; vanilla is about 1%
    for most creatures. 0 leaves the game's own odds alone."""
    display_name = "Gold Card Drop Chance"
    range_start = 0
    range_end = 50
    default = 5


class GoldCardGoalAmount(Range):
    """Gold cards goal: how many of the 65 gold Creature Cards you need."""
    display_name = "Gold Card Goal Amount"
    range_start = 1
    range_end = 65
    default = 65


class RecipeShuffle(Toggle):
    """Shuffle the ingredients of every Tier 2 and Tier 3 weapon, tool and
    armor recipe, so gear no longer costs what it does in vanilla (Tier 1
    recipes are left alone -- they're the starting point for everything
    else).

    New ingredients always come from creatures one tier below the gear
    (Tier 2 gear from Tier 1 creatures and starting-area resources, Tier 3
    gear from Tier 1-2 creatures), so logic never expects a recipe you
    can't gather for yet. Click a craft check in the client's Tracker tab
    to see the new costs; the in-game crafting menu shows them too."""
    display_name = "Recipe Shuffle"


class CreatureDropShuffle(Toggle):
    """Shuffle what creatures drop when killed: every creature part (and
    raw meat) is swapped for another one, consistently -- e.g. everything
    that dropped Spider Fang might now drop Moth Scale instead.

    Parts are only swapped with others from the same tier/area (Tier 1
    with Tier 1, Upper Yard Tier 3 with Upper Yard Tier 3, ...), so logic
    never expects a material earlier than you can really get it. Gold
    Creature Cards are NOT shuffled -- each creature still drops its own.
    Click an item check in the client's Tracker tab to see who drops it now."""
    display_name = "Creature Drop Shuffle"


class ProgressiveGear(Toggle):
    """Replace the individual recipes of the main gear lines with
    progressive items: Progressive Axe, Hammer, Shovel, Spear and Bow, and
    Progressive Head/Chest/Leg Armor (Clover -> Acorn -> Grub -> Bee ->
    Ladybug -> Red Ant -> Black Ant -> Spider -> Roly Poly -> Antlion ->
    Black Ox -> Mantis). Each copy unlocks the next recipe in its line.
    Other weapons stay individual items."""
    display_name = "Progressive Gear"


class MutationChecks(Toggle):
    """Add checks for unlocking 1, 3, 5, 8, 12, 16, 20 and 25 mutations."""
    display_name = "Mutation Checks"


class LandmarkChecks(DefaultOnToggle):
    """Add a check for discovering each of the yard's landmarks (field
    stations, labs, juice boxes, ...). The client's Tracker > Map tab shows
    where they are."""
    display_name = "Landmark Checks"


@dataclass
class GroundedOptions(PerGameCommonOptions):
    goal: Goal
    excluded_bosses: ExcludedBosses
    include_boss_checks: IncludeBossChecks
    gold_card_drop_chance: GoldCardDropChance
    gold_card_goal_amount: GoldCardGoalAmount
    recipe_shuffle: RecipeShuffle
    creature_drop_shuffle: CreatureDropShuffle
    progressive_gear: ProgressiveGear
    mutation_checks: MutationChecks
    landmark_checks: LandmarkChecks
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool
