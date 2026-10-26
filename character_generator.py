import pandas as pd
import random
from pathlib import Path

TRAITS_FILE = Path(__file__).with_name('traits.csv')

def create_character(level: int, race: str = 'Human', start_with_martial_training: bool = False, start_with_sorcery: bool = False, teenager: bool = False):
    
    def roll_stat():
        total = (
            random.randint(1, 6)
            + random.randint(1, 6)
            + random.randint(1, 6)
        )

        return max(total, 6)

    # =========================
    # LOAD TRAITS
    # =========================

    trait_data = pd.read_csv(TRAITS_FILE)

    general_traits = trait_data[
        (trait_data['Type'] == 'General')
        & (trait_data['PlayerOnly'] != 1)
    ].reset_index(drop=True)

    drawbacks = trait_data[
        (trait_data['Type'] == 'Drawback')
        & (trait_data['PlayerOnly'] != 1)
    ].reset_index(drop=True)

    martial_traits = trait_data[
        (trait_data['Type'] == 'Martial')
        & (trait_data['PlayerOnly'] != 1)
    ].reset_index(drop=True)

    sorcery_traits = trait_data[
        (trait_data['Type'] == 'Sorcery')
        & (trait_data['PlayerOnly'] != 1)
    ].reset_index(drop=True)

    race = race.title()

    racial_traits = pd.DataFrame()

    if race != 'Human':

        racial_traits = trait_data[
            (trait_data['Type'] == race)
            & (trait_data['PlayerOnly'] != 1)
        ].reset_index(drop=True)

    # =========================
    # BASE STATS
    # =========================

    point_limit = 60 + (2 * level) + (2 if race == 'Human' else 0)
    starting_trait_cost = (
        (5 if start_with_martial_training else 0)
        + (5 if start_with_sorcery else 0)
    )
    while True:
        strength = roll_stat()
        agility = roll_stat()
        constitution = roll_stat()
        charisma = roll_stat()
        wisdom = roll_stat()
        willpower = roll_stat()

        total_spread = (
            strength
            + agility
            + constitution
            + charisma
            + wisdom
            + willpower
        )
        if total_spread + starting_trait_cost <= point_limit:
            break

    target = point_limit - total_spread

    # =========================
    # STATE TRACKING
    # =========================

    allocated_points = 0

    drawback_counter = 0
    racial_trait_counter = 0

    exclusions = []

    selected_traits = {}

    has_martial_training = start_with_martial_training
    has_sorcery = start_with_sorcery

    # =========================
    # STARTING OPTIONS
    # =========================

    # Exclude Teenager unless explicitly enabled
    if not teenager:
        exclusions.append('Teenager')

    # Automatically grant gateway traits
    if start_with_martial_training:

        selected_traits['Martial Training'] = 5

        exclusions.append('Martial Training')

    if start_with_sorcery:

        selected_traits['Sorcery'] = 5

        exclusions.append('Sorcery')

    if teenager:

        teenager_row = drawbacks[
            drawbacks['Name'] == 'Teenager'
        ]

        if not teenager_row.empty:

            teenager_cost = teenager_row.iloc[0]['Cost']

            selected_traits['Teenager'] = teenager_cost

            exclusions.append('Teenager')

            allocated_points += teenager_cost

            drawback_counter += 1

    allocated_points = sum(selected_traits.values())

    # =========================
    # BUILD CHARACTER
    # =========================

    max_iterations = 1000
    iteration = 0

    while allocated_points < target and iteration < max_iterations:

        iteration += 1

        cap = target - allocated_points

        valid_actions = []

        # =========================
        # GENERAL / SPECIAL TRAITS
        # =========================

        available_traits = general_traits.copy()

        if has_martial_training:

            available_traits = pd.concat(
                [available_traits, martial_traits],
                ignore_index=True
            )

        if has_sorcery:

            available_traits = pd.concat(
                [available_traits, sorcery_traits],
                ignore_index=True
            )

        available_traits = available_traits[
            ~available_traits['Name'].isin(exclusions)
        ]

        available_traits = available_traits[
            available_traits['Min Cost'] <= cap
        ].reset_index(drop=True)

        if not available_traits.empty:
            valid_actions.append('trait')

        # =========================
        # STAT UPS
        # =========================

        available_stats_to_increase = []

        if strength < 20:
            available_stats_to_increase.append('strength')

        if agility < 20:
            available_stats_to_increase.append('agility')

        if constitution < 20:
            available_stats_to_increase.append('constitution')

        if charisma < 20:
            available_stats_to_increase.append('charisma')

        if wisdom < 20:
            available_stats_to_increase.append('wisdom')

        if willpower < 20:
            available_stats_to_increase.append('willpower')

        if available_stats_to_increase and cap >= 1:
            valid_actions.append('statup')

        # =========================
        # DRAWBACKS
        # =========================

        available_drawbacks = drawbacks[
            ~drawbacks['Name'].isin(exclusions)
        ].reset_index(drop=True)

        if (
            drawback_counter < 5
            and not available_drawbacks.empty
        ):
            valid_actions.append('drawback')

        # =========================
        # RACIAL TRAITS
        # =========================

        available_racial_traits = pd.DataFrame()

        if race != 'Human':

            available_racial_traits = racial_traits[
                ~racial_traits['Name'].isin(exclusions)
            ]

            available_racial_traits = available_racial_traits[
                available_racial_traits['Min Cost'] <= cap
            ].reset_index(drop=True)

            if (
                racial_trait_counter < 2
                and not available_racial_traits.empty
            ):
                valid_actions.append('racial_trait')

        # =========================
        # FAILSAFE
        # =========================

        if not valid_actions:
            break

        action = random.choice(valid_actions)

        # =========================
        # TRAIT
        # =========================

        if action == 'trait':

            chosen_trait = available_traits.sample(1).iloc[0]

            cost = chosen_trait['Cost']

            if chosen_trait['Var']:

                min_cost = min(
                    chosen_trait['Cost'],
                    chosen_trait['Min Cost']
                )

                max_cost = min(
                    max(
                        chosen_trait['Cost'],
                        chosen_trait['Min Cost']
                    ),
                    cap
                )

                cost = random.randint(min_cost, max_cost)

            trait_name = chosen_trait['Name']
            exclusion = chosen_trait['Exclusions']

            allocated_points += cost

            # Upgradeable gateway traits
            if trait_name in selected_traits:

                if cost > selected_traits[trait_name]:
                    selected_traits[trait_name] = cost

            else:
                selected_traits[trait_name] = cost

            # Unlock advanced trees
            if trait_name == 'Martial Training' and cost == 5:
                has_martial_training = True

            if trait_name == 'Sorcery' and cost == 5:
                has_sorcery = True

            # Gateway traits remain upgradeable
            if trait_name not in [
                'Martial Training',
                'Sorcery'
            ]:
                exclusions.append(trait_name)

            if pd.notna(exclusion):
                exclusions.append(exclusion)

        # =========================
        # STAT UP
        # =========================

        elif action == 'statup':

            chosen_stat = random.choice(
                available_stats_to_increase
            )

            if chosen_stat == 'strength':
                strength += 1

            elif chosen_stat == 'agility':
                agility += 1

            elif chosen_stat == 'constitution':
                constitution += 1

            elif chosen_stat == 'charisma':
                charisma += 1

            elif chosen_stat == 'wisdom':
                wisdom += 1

            elif chosen_stat == 'willpower':
                willpower += 1

            allocated_points += 1

        # =========================
        # DRAWBACK
        # =========================

        elif action == 'drawback':

            chosen_drawback = (
                available_drawbacks.sample(1).iloc[0]
            )

            cost = chosen_drawback['Cost']

            if chosen_drawback['Var']:

                min_cost = min(
                    chosen_drawback['Cost'],
                    chosen_drawback['Min Cost']
                )

                max_cost = max(
                    chosen_drawback['Cost'],
                    chosen_drawback['Min Cost']
                )

                cost = random.randint(
                    min_cost,
                    max_cost
                )

            drawback_name = chosen_drawback['Name']
            exclusion = chosen_drawback['Exclusions']

            allocated_points += cost

            selected_traits[drawback_name] = cost

            exclusions.append(drawback_name)

            if pd.notna(exclusion):
                exclusions.append(exclusion)

            drawback_counter += 1

        # =========================
        # RACIAL TRAIT
        # =========================

        elif action == 'racial_trait':

            chosen_racial_trait = (
                available_racial_traits.sample(1).iloc[0]
            )

            cost = chosen_racial_trait['Cost']

            if chosen_racial_trait['Var']:

                min_cost = min(
                    chosen_racial_trait['Cost'],
                    chosen_racial_trait['Min Cost']
                )

                max_cost = min(
                    max(
                        chosen_racial_trait['Cost'],
                        chosen_racial_trait['Min Cost']
                    ),
                    cap
                )

                cost = random.randint(
                    min_cost,
                    max_cost
                )

            racial_trait_name = (
                chosen_racial_trait['Name']
            )

            exclusion = (
                chosen_racial_trait['Exclusions']
            )

            allocated_points += cost

            selected_traits[
                racial_trait_name
            ] = cost

            exclusions.append(racial_trait_name)

            if pd.notna(exclusion):
                exclusions.append(exclusion)

            racial_trait_counter += 1

    # =========================
    # DERIVED STATS
    # =========================

    health = (
        constitution
        + max(strength, willpower)
    )

    stamina = (
        max(constitution, strength, agility)
        + sorted(
            [constitution, strength, agility]
        )[1]
    )

    magica = (
        willpower
        + max(charisma, wisdom)
    )

    # =========================
    # OUTPUT
    # =========================

    character_value = (
        strength + agility + constitution + charisma + wisdom + willpower
        + sum(selected_traits.values())
    )

    return {

        'Race': race,
        'Level': level,

        'Stats': {
            'STR': strength,
            'AGI': agility,
            'CON': constitution,
            'CHA': charisma,
            'WIS': wisdom,
            'WIL': willpower
        },

        'Derived': {
            'Health': health,
            'Stamina': stamina,
            'Magica': magica
        },

        'Traits': selected_traits,

        'Meta': {
            'Target': point_limit - 60,
            'Allocated Points': character_value - 60,
            'Spread Offset': 0,
            'Starting Spread': 60,
            'Has Martial Training': has_martial_training,
            'Has Sorcery': has_sorcery,
            'Teenager': teenager,
            'Character Value': character_value,
            'Character Value Limit': point_limit,
        }
    }
