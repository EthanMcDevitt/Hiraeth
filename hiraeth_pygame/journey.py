if __package__:
    from .shared import (
        DOWNTIME_ACTIVITIES,
        modifier,
        new_battle,
        random,
        spell_capacity,
    )
else:
    from shared import (
        DOWNTIME_ACTIVITIES,
        modifier,
        new_battle,
        random,
        spell_capacity,
    )


class JourneyMixin:

    def generate_destination(self, current_type):
        next_type = 'waystation' if current_type == 'town' else 'town'
        range_key = 'town_to_waystation' if next_type == 'waystation' else 'waystation_to_town'
        distance_range = self.journey['distance'][range_key]
        if next_type == 'town':
            town_level = self.journey['town_level']
            level = random.randint(town_level['min'], town_level['max'])
            name = random.choice(self.journey['town_names'])
        else:
            level = None
            name = random.choice(self.journey['waystation_names'])
        return {
            'type': next_type,
            'name': name,
            'level': level,
            'distance': random.randint(distance_range['min'], distance_range['max']),
        }

    def continue_after_travel_turn(self):
        game = self.game
        if game['step'] >= self.journey['stages']:
            game['mode'] = 'won'
            return
        if game.get('travel_remaining', 1) <= 0:
            game['location'] = game.pop('travel_destination', None) or {
                'type': 'waystation', 'name': 'A roadside shelter',
            }
            game['mode'] = game['location']['type']
            game['travel_remaining'] = None
            game['log'].insert(0, f"The party reaches {game['location']['name']}.")
        else:
            game['mode'] = 'journey'

    def begin_journey(self):
        if not self.selected:
            return
        party = []
        for index in self.selected:
            character = self.characters[index]
            try:
                maximum = max(1, int(character['Derived']['Health']))
            except (KeyError, TypeError, ValueError):
                self.message = f"{character.get('Name', 'Traveler')} has no valid Health value."
                return
            member = self.prepare_member(character, maximum)
            party.append(member)
        self.game = {
            'party': party,
            'party_inventory': [],
            'day': 1,
            'step': 0,
            'supply': self.journey['starting_supply'],
            'wealth': self.journey['starting_wealth'],
            'reputation': self.journey['starting_reputation'],
            'camp_recovery': 'health',
            'mode': 'town',
            'location': {
                'type': 'town',
                'name': random.choice(self.journey['town_names']),
                'level': random.randint(
                    self.journey['town_level']['min'],
                    self.journey['town_level']['max'],
                ),
            },
            'travel_remaining': None,
            'travel_destination': None,
            'battle': None,
            'event': None,
            'log': [self.texts['journey_start_log'].format(
                party=', '.join(person['Name'] for person in party),
                supply=self.journey['starting_supply'],
            )],
        }
        self.message = ''
        self.save()

    def begin_sandbox(self):
        if not self.selected:
            return
        party = []
        for index in self.selected:
            character = self.characters[index]
            try:
                maximum = max(1, int(character['Derived']['Health']))
            except (KeyError, TypeError, ValueError):
                self.message = f"{character.get('Name', 'Traveler')} has no valid Health value."
                return
            member = self.prepare_member(character, maximum)
            party.append(member)
        start = self.config['sandbox']['start']
        self.game = {
            'party': party,
            'party_inventory': [],
            'day': 1,
            'step': 0,
            'position': {'x': start['x'], 'y': start['y']},
            'supply': self.journey['starting_supply'],
            'wealth': self.journey['starting_wealth'],
            'reputation': self.journey['starting_reputation'],
            'camp_recovery': 'health',
            'mode': 'sandbox',
            'battle': None,
            'event': None,
            'log': [],
        }
        self.message = ''
        self.save()

    def prepare_member(self, character, maximum):
        member = dict(character)
        member['max_health'] = maximum
        member['health'] = maximum
        for label, key in (('Stamina', 'stamina'), ('Magica', 'magica')):
            try:
                value = max(0, int(member.get('Derived', {}).get(label, 0)))
            except (TypeError, ValueError):
                value = 0
            member[f'max_{key}'] = value
            member[f'{key}_now'] = value
        self.normalize_member(member)
        return member

    @staticmethod
    def normalize_member(member):
        member.setdefault('inventory', [])
        member.setdefault('known_spells', [])
        member.setdefault('rank', 'front')
        if member['rank'] not in ('front', 'back'):
            member['rank'] = 'front'
        member.setdefault('downtime_activity', 'health')
        if member['downtime_activity'] not in DOWNTIME_ACTIVITIES:
            member['downtime_activity'] = 'health'
        member.setdefault('equipment', {'weapon': None, 'armor': None, 'helmet': None, 'shield': None})
        equipment = member['equipment']
        for slot in ('weapon', 'armor', 'helmet', 'shield'):
            equipment.setdefault(slot, None)
        member.setdefault('max_stamina', max(0, int(member.get('Derived', {}).get('Stamina', 0) or 0)))
        member.setdefault('stamina_now', member['max_stamina'])
        member.setdefault('max_magica', max(0, int(member.get('Derived', {}).get('Magica', 0) or 0)))
        member.setdefault('magica_now', member['max_magica'])
        member.setdefault('armor_ap_max', 0)
        member.setdefault('armor_ap_now', member['armor_ap_max'])
        member.setdefault('armor_ap_total', member['armor_ap_max'])
        member.setdefault('armor_ap_broken', 0)
        capacity = spell_capacity(member)
        member['max_spells'] = capacity
        member.setdefault('Derived', {})['Max Spells'] = member['max_spells']
        member['known_spells'] = member['known_spells'][:member['max_spells']]

    def move_sandbox(self, direction):
        sandbox = self.config['sandbox']
        deltas = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
        dx, dy = deltas[direction]
        position = self.game['position']
        target_x, target_y = position['x'] + dx, position['y'] + dy
        rows = sandbox['map']
        direction_name = sandbox['text']['directions'][direction]
        if not (0 <= target_y < len(rows) and 0 <= target_x < len(rows[target_y])):
            self.message = sandbox['text']['blocked_log'].format(direction=direction_name)
            return
        if rows[target_y][target_x] in sandbox['blocked_symbols']:
            self.message = sandbox['text']['blocked_log'].format(direction=direction_name)
            return
        position['x'], position['y'] = target_x, target_y
        self.game['day'] += 1
        self.message = sandbox['text']['move_log'].format(
            direction=direction_name, x=target_x, y=target_y,
        )
        self.save()

    def start_battle(self):
        battle = new_battle(self.config)
        ambush_roll = random.random() * 100
        ambush_chance = self.journey['ambush_chance'] * 100
        battle['ambush'] = ambush_roll < ambush_chance
        self.game['battle'] = battle
        self.game['mode'] = 'combat'
        self.game['log'].insert(
            0,
            f"Ambush check: {ambush_roll:.1f}% vs {ambush_chance:g}% "
            f"({'ambush' if battle['ambush'] else 'no ambush'}).",
        )
        self.log_scroll = 0
        if battle['ambush']:
            self.game['log'].insert(0, 'The creatures strike before the party can act.')
            self.enemy_turn()
        else:
            battle['phase'] = 'planning'
            battle['planning_actor'] = next(
                (index for index, member in enumerate(self.game['party']) if member['health'] > 0),
                None,
            )
            self.game['log'].insert(0, 'The party spots the creatures in time and acts first.')

    def can_take_downtime(self, member):
        if member['health'] <= 0:
            return False
        activity = member.get('downtime_activity', 'health')
        if activity == 'health':
            return member['health'] < member['max_health']
        if activity == 'magica':
            return member['magica_now'] < member['max_magica']
        if activity == 'stamina':
            return member['stamina_now'] < member['max_stamina']
        return activity == 'repair' and member.get('armor_ap_now', 0) < member.get('armor_ap_max', 0)

    def perform_downtime(self):
        results = []
        for member in self.game['party']:
            if not self.can_take_downtime(member):
                continue
            activity = member.get('downtime_activity', 'health')
            if activity == 'health':
                faces, total = self.roll_dice_details('1d6')
                amount = min(total, member['max_health'] - member['health'])
                member['health'] += amount
                results.append(
                    f"{member['Name']} rolls {self.format_dice('1d6', faces)}; "
                    f"recovers {amount} Health"
                )
            elif activity == 'magica':
                faces, total = self.roll_dice_details('2d4')
                amount = min(total, member['max_magica'] - member['magica_now'])
                member['magica_now'] += amount
                results.append(
                    f"{member['Name']} rolls {self.format_dice('2d4', faces)}; "
                    f"recovers {amount} Magica"
                )
            elif activity == 'stamina':
                faces, total = self.roll_dice_details('2d6')
                amount = min(total, member['max_stamina'] - member['stamina_now'])
                member['stamina_now'] += amount
                results.append(
                    f"{member['Name']} rolls {self.format_dice('2d6', faces)}; "
                    f"recovers {amount} Stamina"
                )
            else:
                repaired, failed, checks = self.repair_armor(member)
                results.extend(f"{member['Name']} armor: {check}" for check in checks)
                results.append(
                    f"{member['Name']} armor repair: {repaired} AP restored"
                    + (f", {failed} permanently broken" if failed else '')
                )
        return results

    def log_activities(self, summary, activities):
        self.game['log'].insert(0, summary)
        for activity in reversed(activities):
            self.game['log'].insert(0, activity + '.')

    def repair_armor(self, member):
        armor = self.item_by_id('armor', member.get('equipment', {}).get('armor'))
        if not armor:
            armor = next(
                (
                    item for slot in ('helmet', 'shield')
                    if (item := self.item_by_id('armor', member.get('equipment', {}).get(slot)))
                ),
                None,
            )
        base_ap = armor.get('ap', 0) if armor else 0
        traits = armor.get('traits', '').lower() if armor else ''
        inventory = set(member.get('inventory', [])) | set(self.game.get('party_inventory', []))
        die = 6
        if 'light' in traits and 'sewing_kit' in inventory:
            die = 8
        elif ('medium' in traits or 'heavy' in traits) and 'smith_tools' in inventory:
            die = 8
        bonus = (1 if 'simple construction' in traits else 0)
        bonus += 5 if self.trait_rank(member, 'Master Crafter') > 0 else 0
        damaged = max(0, member['armor_ap_max'] - member['armor_ap_now'])
        repaired = failed = 0
        checks = []
        for _ in range(damaged):
            face = random.randint(1, die)
            total = face + bonus
            success = total > base_ap
            checks.append(
                f"d{die} {face}"
                + (f" + {bonus} = {total}" if bonus else '')
                + f": {total} > AP {base_ap} ({'success' if success else 'failure'})"
            )
            if success:
                member['armor_ap_now'] += 1
                repaired += 1
            else:
                member['armor_ap_broken'] = member.get('armor_ap_broken', 0) + 1
                member['armor_ap_max'] -= 1
                failed += 1
        return repaired, failed, checks

    def apply_supply_shortage(self):
        losses = []
        for member in self.alive_party():
            deduction = self.journey['starvation_per_day']
            starting_stamina = max(0, member.get('stamina_now', 0))
            stamina_loss = min(starting_stamina, deduction)
            health_loss = deduction - stamina_loss
            member['stamina_now'] = starting_stamina - stamina_loss
            member['health'] = max(0, member['health'] - health_loss)
            if stamina_loss:
                losses.append(f"{member['Name']} loses {stamina_loss} Stamina")
            if health_loss:
                losses.append(f"{member['Name']} loses {health_loss} Health")
        if losses:
            self.game['log'].insert(0, 'Without supplies: ' + '; '.join(losses) + '.')
        if not self.alive_party():
            self.game['mode'] = 'lost'
            self.game['battle'] = None
            self.game['log'].insert(0, 'The party falls after running out of supplies.')

    def town_repair_limit(self, member):
        equipment = member.get('equipment', {})
        equipped_armor = [
            armor
            for slot in ('armor', 'helmet', 'shield')
            if (armor := self.item_by_id('armor', equipment.get(slot)))
        ]
        if not equipped_armor:
            return None
        return max(armor['ap'] for armor in equipped_armor)

    def repair_armor_in_town(self, member_index):
        if self.game.get('mode') != 'town' or not 0 <= member_index < len(self.game['party']):
            return
        member = self.game['party'][member_index]
        town_level = self.game.get('location', {}).get('level', 1)
        armor_limit = self.town_repair_limit(member)
        damaged = max(0, member.get('armor_ap_total', member['armor_ap_max']) - member['armor_ap_now'])
        if armor_limit is None or armor_limit > town_level or damaged == 0:
            self.message = 'This town cannot repair that character’s armor.'
            return
        if self.game['wealth'] < 1:
            self.message = 'Need 1 Wealth to repair armor in town.'
            return
        repaired = min(damaged, town_level)
        broken_repaired = min(repaired, member.get('armor_ap_broken', 0))
        member['armor_ap_broken'] = member.get('armor_ap_broken', 0) - broken_repaired
        member['armor_ap_max'] = min(
            member.get('armor_ap_total', member['armor_ap_max']),
            member['armor_ap_max'] + broken_repaired,
        )
        member['armor_ap_now'] = min(
            member['armor_ap_max'],
            member['armor_ap_now'] + repaired,
        )
        self.game['wealth'] -= 1
        self.message = f"Spent 1 Wealth to repair {repaired} AP for {member['Name']}."
        self.game['log'].insert(0, self.message)
        self.save()

    def forage_supplies(self):
        supplies = 0
        checks = []
        for member in self.alive_party():
            if self.trait_rank(member, 'Survivalist') > 0:
                supplies += 1
                checks.append(f"{member['Name']} succeeds automatically (Survivalist)")
                continue
            rolls = [random.randint(1, 20)]
            has_fishing_kit = 'fishing_kit' in member.get('inventory', [])
            if has_fishing_kit:
                rolls.append(random.randint(1, 20))
            selected = max(rolls)
            wisdom = modifier(member, 'WIS')
            total = selected + wisdom
            success = total >= 11
            check = (
                f"{member['Name']} foraging: d20 {rolls}"
                + (' (advantage)' if has_fishing_kit else '')
                + f" + WIS {wisdom} = {total} vs DC 11 ({'success' if success else 'failure'})"
            )
            checks.append(check)
            if success:
                supplies += 1
        self.game['day'] += 1
        self.game['supply'] += supplies
        self.game['log'].insert(
            0, f"Foraging yielded {supplies} Supply."
        )
        for check in reversed(checks):
            self.game['log'].insert(0, check + '.')
        if not supplies:
            self.apply_supply_shortage()
        self.save()
