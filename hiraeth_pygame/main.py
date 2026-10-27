if __package__:
    from .shared import (
        CONFIG,
        DOWNTIME_ACTIVITIES,
        DOWNTIME_LABELS,
        HEIGHT,
        MAX_PARTY,
        RULES,
        SEX_OPTIONS,
        STATS,
        WIDTH,
        WINDOW_SIZE,
        character_point_limit,
        pygame,
        random,
        read_characters,
    )
    from .combat import CombatMixin
    from .creator import CreatorMixin
    from .inventory import InventoryMixin
    from .journey import JourneyMixin
    from .persistence import PersistenceMixin
    from .rendering import RenderingMixin
else:
    from shared import (
        CONFIG,
        DOWNTIME_ACTIVITIES,
        DOWNTIME_LABELS,
        HEIGHT,
        MAX_PARTY,
        RULES,
        SEX_OPTIONS,
        STATS,
        WIDTH,
        WINDOW_SIZE,
        character_point_limit,
        pygame,
        random,
        read_characters,
    )
    from combat import CombatMixin
    from creator import CreatorMixin
    from inventory import InventoryMixin
    from journey import JourneyMixin
    from persistence import PersistenceMixin
    from rendering import RenderingMixin


class Hiraeth(
    CombatMixin, CreatorMixin, InventoryMixin, JourneyMixin,
    PersistenceMixin, RenderingMixin,
):
    def __init__(self):
        self.config = CONFIG
        self.journey = self.config['journey']
        self.combat = self.config['combat']
        self.texts = self.config['text']
        self.rules = RULES
        pygame.init()
        pygame.display.set_caption(self.texts['game_title'])
        self.display = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        self.screen = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('georgia', 20)
        self.body = pygame.font.SysFont('segoeui', 15)
        self.small = pygame.font.SysFont('segoeui', 11, bold=True)
        self.tiny = pygame.font.SysFont('segoeui', 9, bold=True)
        self.characters, self.archive_message = read_characters()
        self.races, self.trait_catalog = self.read_creator_options()
        self.selected = []
        self.character_offset = 0
        self.dropdown = None
        self.dropdown_offset = 0
        self.view = 'selection'
        self.overview = None
        self.inventory_category = 'weapons'
        self.inventory_owner = None
        self.inventory_selected = None
        self.inventory_owned_index = None
        self.inventory_scroll = 0
        self.inventory_owned_scroll = 0
        self.pending_spell = None
        self.creator = None
        self.game = None
        self.continuation = None
        self.quit_prompt = False
        self.message = ''
        self.buttons = []
        self.attack_animations = []
        self.animation_next_at = 0
        self.log_scroll = 0
        self.inventory_recipient = 0
        self.load_save()

    def handle_action(self, action):
        if isinstance(action, tuple) and action[0] == 'focus' and self.creator is not None:
            self.creator['focus'] = action[1]
            return
        if isinstance(action, tuple) and action[0] == 'select_dropdown':
            _, kind, value = action
            if kind == 'race':
                self.creator['race'] = value
                allowed = {trait['Name'] for trait in self.creator_trait_options()}
                self.creator['traits'] = {
                    name: cost for name, cost in self.creator['traits'].items()
                    if name in allowed
                }
                if self.creator.get('trait_pick') not in allowed:
                    self.creator['trait_pick'] = None
            else:
                self.creator[kind] = value
            self.dropdown = None
            return
        if isinstance(action, tuple) and action[0] == 'select_trait':
            self.creator['trait_pick'] = action[1]
            picked = next((trait for trait in self.creator_trait_options() if trait['Name'] == action[1]), None)
            self.creator['trait_rank'] = (
                int(self.creator['traits'].get(action[1], self.creator_trait_cost(picked)))
                if picked else 1
            )
            self.dropdown = None
            return
        if action in ('dropdown_race', 'dropdown_sex', 'dropdown_trait'):
            kind = action.removeprefix('dropdown_')
            self.dropdown = None if self.dropdown == kind else kind
            self.dropdown_offset = 0
            return
        if action == 'add_trait':
            name = self.creator.get('trait_pick')
            trait = next((item for item in self.creator_trait_options() if item['Name'] == name), None)
            if trait:
                new_cost = self.creator_trait_cost(trait, self.creator.get('trait_rank'))
                old_cost = int(self.creator['traits'].get(name, 0))
                limit = character_point_limit(self.creator['level'], self.creator['race'])
                if self.creator_points() - old_cost + new_cost <= limit:
                    self.creator['traits'][name] = new_cost
                else:
                    self.message = 'Not enough character points; lower an attribute or add a drawback first.'
            return
        if action == 'remove_trait':
            name = self.creator.get('trait_pick')
            self.creator['traits'].pop(name, None)
            return
        if isinstance(action, tuple) and action[0] == 'creator_stat':
            key, change = action[1], action[2]
            next_value = max(6, min(20, int(self.creator['stats'][key]) + change))
            if change < 0 or self.creator_points() + next_value - int(self.creator['stats'][key]) <= character_point_limit(self.creator['level'], self.creator['race']):
                self.creator['stats'][key] = str(next_value)
            else:
                self.message = 'That increase exceeds the character point limit.'
            return
        if isinstance(action, tuple) and action[0] == 'creator_trait_rank':
            name = self.creator.get('trait_pick')
            trait = next((item for item in self.creator_trait_options() if item['Name'] == name), None)
            if trait and trait.get('Variable'):
                minimum = int(trait.get('MinCost', trait.get('Cost', 1)))
                maximum = int(trait.get('MaxCost', trait.get('Cost', minimum)))
                old_rank = int(self.creator.get('trait_rank', minimum))
                new_rank = max(minimum, min(maximum, old_rank + action[1]))
                old_cost = int(self.creator['traits'].get(name, 0))
                if name not in self.creator['traits'] or self.creator_points() - old_cost + new_rank <= character_point_limit(self.creator['level'], self.creator['race']):
                    self.creator['trait_rank'] = new_rank
                    if name in self.creator['traits']:
                        self.creator['traits'][name] = new_rank
                else:
                    self.message = 'That trait rank exceeds the character point limit.'
            return
        if isinstance(action, tuple) and action[0] == 'creator_level':
            try:
                level = int(self.creator['level'])
            except ValueError:
                level = 1
            next_level = max(1, min(100, level + action[1]))
            if self.creator_points() <= character_point_limit(next_level, self.creator['race']):
                self.creator['level'] = str(next_level)
            else:
                self.message = 'Remove some allocated points before lowering this character level.'
            return
        if action == 'creator_sex':
            current = self.creator['sex']
            self.creator['sex'] = SEX_OPTIONS[(SEX_OPTIONS.index(current) + 1) % len(SEX_OPTIONS)]
            return
        if action == 'resume' and self.game is None and self.continuation:
            self.game = self.continuation
            for member in self.game.get('party', []):
                self.normalize_member(member)
            self.game.setdefault('party_inventory', [])
            self.continuation = None
            self.view = 'game'
            self.message = ''
            return
        if self.game is None:
            if action == 'create_screen':
                self.creator = {
                    'name': '', 'race': 'Human', 'level': '1',
                    'sex': SEX_OPTIONS[0],
                    'stats': {key: '10' for key in STATS},
                    'traits': {}, 'trait_pick': None, 'notes': '', 'focus': 'name',
                }
                self.dropdown = None
                self.message = ''
                self.view = 'creator'
            elif action == 'creator_cancel':
                self.creator = None
                self.dropdown = None
                self.view = 'selection'
                self.message = ''
            elif action == 'create_save':
                self.save_new_character()
            elif isinstance(action, tuple) and action[0] == 'toggle_member':
                index = action[1]
                if index in self.selected:
                    self.selected.remove(index)
                elif len(self.selected) < MAX_PARTY:
                    self.selected.append(index)
            elif action == 'earlier':
                self.character_offset = max(0, self.character_offset - 1)
            elif action == 'later':
                self.character_offset = min(max(0, len(self.characters) - 4), self.character_offset + 1)
            elif action == 'start':
                self.begin_journey()
            elif action == 'start_sandbox':
                self.begin_sandbox()
            return

        game = self.game
        if isinstance(action, tuple) and action[0] == 'log_scroll':
            self.log_scroll = max(
                0,
                min(
                    max(0, len(self.journal_lines()) - 5),
                    self.log_scroll + action[1],
                ),
            )
        elif isinstance(action, tuple) and action[0] == 'party_rank':
            index = action[1]
            if not 0 <= index < len(game['party']) or game['party'][index]['health'] <= 0:
                return
            member = game['party'][index]
            if game['mode'] == 'combat':
                battle = game.get('battle') or {}
                if (
                    battle.get('phase') == 'planning'
                    and battle.get('planning_actor') == index
                    and str(index) not in battle.get('plans', {})
                    and not battle.get('targeting')
                ):
                    self.plan_move(index, 'switch_rank')
            elif game['mode'] not in ('won', 'lost'):
                member['rank'] = 'back' if member.get('rank', 'front') == 'front' else 'front'
                self.message = f"{member['Name']} moves to the {member['rank']} row."
                self.save()
        elif isinstance(action, tuple) and action[0] == 'cycle_downtime':
            index = action[1]
            if not 0 <= index < len(game['party']) or game['party'][index]['health'] <= 0:
                return
            member = game['party'][index]
            current = member.get('downtime_activity', 'health')
            next_index = (DOWNTIME_ACTIVITIES.index(current) + 1) % len(DOWNTIME_ACTIVITIES)
            member['downtime_activity'] = DOWNTIME_ACTIVITIES[next_index]
            self.message = f"{member['Name']} will {DOWNTIME_LABELS[member['downtime_activity']].lower()} during downtime."
            self.save()
        elif action == 'forage' and game['mode'] == 'journey' and game['supply'] == 0:
            self.forage_supplies()
        elif isinstance(action, tuple) and action[0] == 'town_repair':
            self.repair_armor_in_town(action[1])
        elif action == 'inventory':
            self.view = 'inventory'
            self.overview = None
            self.inventory_owned_index = None
            self.inventory_selected = None
            self.message = ''
        elif action == 'inventory_back':
            self.view = 'game'
            self.message = ''
        elif isinstance(action, tuple) and action[0] == 'inventory_category':
            self.inventory_category = action[1]
            self.inventory_scroll = 0
            self.inventory_owned_scroll = 0
            self.inventory_owned_index = None
            self.inventory_selected = None
        elif isinstance(action, tuple) and action[0] == 'inventory_owner':
            self.inventory_owner = action[1]
            self.inventory_owned_scroll = 0
            self.inventory_owned_index = None
        elif isinstance(action, tuple) and action[0] == 'inventory_select':
            self.inventory_selected = action[1]
            self.inventory_owned_index = None
        elif isinstance(action, tuple) and action[0] == 'inventory_owned':
            self.inventory_owned_index = action[1]
            self.inventory_selected = None
        elif isinstance(action, tuple) and action[0] == 'inventory_recipient':
            choices = self.transfer_choices()
            if choices:
                self.inventory_recipient = (
                    self.inventory_recipient + action[1]
                ) % len(choices)
        elif action == 'inventory_buy':
            self.buy_inventory_item()
        elif action == 'inventory_learn':
            self.learn_inventory_spell()
        elif action == 'inventory_cast':
            if self.inventory_owner is not None and self.inventory_selected:
                self.pending_spell = {
                    'spell_id': self.inventory_selected,
                    'actor': self.inventory_owner,
                }
                self.view = 'spell_target'
        elif action == 'inventory_transfer':
            self.transfer_inventory_item()
        elif action == 'inventory_equip':
            self.equip_inventory_item()
        elif action == 'inventory_unequip':
            self.unequip_inventory_item()
        elif action == 'spell_target_back':
            self.view = 'inventory'
            self.pending_spell = None
        elif isinstance(action, tuple) and action[0] == 'cast_outside_target':
            if self.pending_spell:
                succeeded = self.cast_spell(
                    self.pending_spell['spell_id'],
                    self.pending_spell['actor'],
                    action[1],
                    in_combat=False,
                )
                if succeeded:
                    self.view = 'inventory'
                    self.pending_spell = None
        elif action == 'quit_prompt':
            self.quit_prompt = True
            self.message = ''
        elif action == 'cancel_quit':
            self.quit_prompt = False
            self.message = ''
        elif action == 'modal_dismiss':
            return
        elif action == 'save_to_menu':
            if self.save():
                self.continuation = game
                self.game = None
                self.overview = None
                self.quit_prompt = False
                self.view = 'selection'
        elif action == 'delete_to_menu':
            if self.delete_save():
                self.game = None
                self.continuation = None
                self.overview = None
                self.quit_prompt = False
                self.view = 'selection'
        elif isinstance(action, tuple) and action[0] == 'sandbox_move' and game['mode'] == 'sandbox':
            self.move_sandbox(action[1])
        elif isinstance(action, tuple) and action[0] == 'overview':
            self.overview = action[1]
        elif action == 'overview_back':
            self.overview = None
        elif action == 'new':
            if self.delete_save():
                self.game = None
                self.continuation = None
                self.overview = None
                self.quit_prompt = False
                self.view = 'selection'
        elif action == 'town_inventory' and game['mode'] == 'town':
            self.view = 'inventory'
            self.overview = None
            self.inventory_category = 'weapons'
            self.inventory_scroll = 0
            self.inventory_owned_index = None
            self.inventory_selected = None
            self.message = ''
        elif action == 'settlement_supply' and game['mode'] in ('town', 'waystation'):
            location = game.get('location', {})
            is_town = location.get('type') == 'town'
            if is_town and game['reputation'] <= -3:
                self.message = 'The town refuses to resupply the party at its current reputation.'
                return
            if game['wealth'] < 1:
                self.message = 'Need 1 Wealth for a supply exchange.'
                return
            amount = max(
                1,
                self.journey['supply_per_wealth_base'] + game['reputation'],
            )
            game['wealth'] -= 1
            game['supply'] += amount
            game['day'] += 1
            self.message = f"Exchanged 1 Wealth for {amount} Supply."
            game['log'].insert(0, self.message)
            self.save()
        elif action == 'town_rest' and game['mode'] == 'town':
            upkeep = self.journey['town_upkeep_wealth_per_turn']
            if game['wealth'] < upkeep:
                self.message = f'Need {upkeep} Wealth to cover town upkeep for a rest.'
                return
            game['wealth'] -= upkeep
            game['day'] += 1
            activities = self.perform_downtime()
            self.message = f"Rested in town and paid {upkeep} Wealth upkeep."
            if activities:
                self.log_activities(self.message, activities)
            else:
                game['log'].insert(0, self.message)
            self.save()
        elif action == 'depart' and game['mode'] in ('town', 'waystation'):
            current_type = game['location']['type']
            destination = self.generate_destination(current_type)
            game['travel_destination'] = {
                'type': destination['type'],
                'name': destination['name'],
                'level': destination['level'],
            }
            game['travel_remaining'] = destination['distance']
            game['mode'] = 'journey'
            self.message = ''
            game['log'].insert(
                0,
                f"The party leaves {game['location']['name']} for {destination['name']} "
                f"({destination['distance']} travel days).",
            )
            self.save()
        elif action == 'travel' and game['mode'] == 'journey' and game.get('travel_remaining'):
            supplied = game['supply'] >= max(1, self.journey['supply_per_travel'])
            if game['supply'] >= self.journey['supply_per_travel']:
                game['supply'] -= self.journey['supply_per_travel']
            elif game['supply'] > 0:
                game['supply'] = 0
            game['day'] += 1
            game['step'] += 1
            game['travel_remaining'] -= 1
            if not supplied:
                self.apply_supply_shortage()
            if game['mode'] == 'lost':
                pass
            else:
                combat_roll = random.random() * 100
                combat_chance = self.journey['combat_chance'] * 100
                combat_encounter = combat_roll < combat_chance
                game['log'].insert(
                    0,
                    f"Encounter check: {combat_roll:.1f}% vs {combat_chance:g}% "
                    f"({'combat' if combat_encounter else 'no combat'}).",
                )
                if combat_encounter:
                    self.start_battle()
                else:
                    event_roll = random.random() * 100
                    event_chance = self.journey['event_chance'] * 100
                    event_encounter = event_roll < event_chance
                    game['log'].insert(
                        0,
                        f"Event check: {event_roll:.1f}% vs {event_chance:g}% "
                        f"({'event' if event_encounter else 'no event'}).",
                    )
                    if event_encounter:
                        events = self.config['events']
                        game['mode'] = 'event'
                        game['event'] = dict(random.choices(
                            events,
                            weights=[event['rarity'] for event in events],
                            k=1,
                        )[0])
                        game['log'].insert(0, self.texts['dilemma_log'].format(title=game['event']['title']))
                    else:
                        self.continue_after_travel_turn()
            self.save()
        elif isinstance(action, tuple) and action[0] == 'camp_recovery' and game['mode'] == 'journey':
            game['camp_recovery'] = action[1]
            self.save()
        elif action == 'rest' and game['mode'] == 'journey' and game['supply'] >= self.journey['supply_per_camp']:
            game['supply'] -= self.journey['supply_per_camp']
            game['day'] += 1
            activities = self.perform_downtime()
            self.log_activities(
                f"The party camps, spends {self.journey['supply_per_camp']} Supply.",
                activities or ['No one needs recovery'],
            )
            self.save()
        elif isinstance(action, tuple) and action[0] == 'event_choice' and game['mode'] == 'event':
            choice = game['event']['choices'][action[1]]
            game['supply'] = max(0, game['supply'] + choice['supply'])
            game['wealth'] = max(0, game['wealth'] + choice['wealth'])
            game['reputation'] += choice['reputation']
            game['event'] = None
            game['log'].insert(0, self.texts['event_result_log'].format(
                result=choice['result'], reputation=choice['reputation'],
            ))
            self.continue_after_travel_turn()
            self.save()
        elif isinstance(action, tuple) and action[0] == 'plan_member' and game['mode'] == 'combat':
            battle = game['battle']
            if battle.get('phase') == 'planning':
                battle['plans'].pop(str(action[1]), None)
                battle['planning_actor'] = action[1]
                battle['targeting'] = None
        elif action == 'combat_choose_attack' and game['mode'] == 'combat':
            battle = game['battle']
            actor_index = battle.get('planning_actor')
            if actor_index is not None:
                battle['targeting'] = {
                    'kind': 'attack', 'target_type': 'foe', 'actor': actor_index,
                }
        elif action == 'combat_choose_guard' and game['mode'] == 'combat':
            battle = game['battle']
            self.plan_move(battle.get('planning_actor'), 'guard')
        elif isinstance(action, tuple) and action[0] == 'combat_choose_spell' and game['mode'] == 'combat':
            battle = game['battle']
            actor_index = battle.get('planning_actor')
            spell = self.item_by_id('spells', action[1])
            if actor_index is not None and spell:
                actor = game['party'][actor_index]
                if action[1] in actor.get('known_spells', []) and actor.get('magica_now', 0) >= spell['cost']:
                    battle['targeting'] = {
                        'kind': 'spell',
                        'spell_id': action[1],
                        'target_type': spell['target'],
                        'actor': actor_index,
                    }
        elif isinstance(action, tuple) and action[0] == 'combat_target_foe' and game['mode'] == 'combat':
            targeting = game['battle'].get('targeting')
            if targeting and targeting.get('target_type') == 'foe':
                if targeting['kind'] == 'attack':
                    self.plan_move(targeting['actor'], 'attack', target_index=action[1])
                else:
                    self.plan_move(
                        targeting['actor'], 'spell', target_index=action[1],
                        spell_id=targeting['spell_id'],
                    )
        elif isinstance(action, tuple) and action[0] == 'combat_target_party' and game['mode'] == 'combat':
            targeting = game['battle'].get('targeting')
            if targeting and targeting.get('target_type') == 'ally':
                self.plan_move(
                    targeting['actor'], 'spell', target_index=action[1],
                    spell_id=targeting['spell_id'],
                )
        elif action == 'combat_cancel_target' and game['mode'] == 'combat':
            game['battle']['targeting'] = None
        elif action == 'combat_resolve' and game['mode'] == 'combat':
            self.resolve_party_moves()
        elif action == 'guard' and game['mode'] == 'combat':
            self.plan_move(game['battle'].get('planning_actor'), 'guard')
            self.save()
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.display = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.MOUSEWHEEL and self.game is None and self.view == 'creator' and self.dropdown == 'trait':
                    self.dropdown_offset = min(max(0, self.dropdown_offset - event.y), max(0, len(self.trait_catalog) - 7))
                elif event.type == pygame.MOUSEWHEEL and self.game is not None and self.view == 'game' and self.mouse_position()[1] >= 598:
                    self.log_scroll = min(
                        max(0, self.log_scroll + event.y),
                        max(0, len(self.journal_lines()) - 5),
                    )
                elif event.type == pygame.MOUSEWHEEL and self.game is not None and self.game['mode'] == 'combat' and self.view == 'game':
                    enemies = self.game['battle'].get('enemies', [])
                    self.game['battle']['target_scroll'] = min(
                        max(0, self.game['battle'].get('target_scroll', 0) - event.y),
                        max(0, len(enemies) - 6),
                    )
                elif event.type == pygame.MOUSEWHEEL and self.game is not None and self.view == 'inventory':
                    if self.mouse_position()[0] >= 444:
                        if self.inventory_category == 'spells' and self.inventory_owner is not None:
                            owned_count = len(self.game['party'][self.inventory_owner].get('known_spells', []))
                            self.inventory_owned_scroll = min(max(0, self.inventory_owned_scroll - event.y), max(0, owned_count - 5))
                        else:
                            owned_count = len(self.current_inventory())
                            self.inventory_owned_scroll = min(max(0, self.inventory_owned_scroll - event.y), max(0, owned_count - 5))
                    else:
                        count = len(self.rules[self.inventory_category])
                        self.inventory_scroll = min(max(0, self.inventory_scroll - event.y), max(0, count - 7))
                elif event.type == pygame.MOUSEWHEEL and self.game is None and len(self.characters) > 4:
                    self.character_offset = min(max(0, self.character_offset - event.y), len(self.characters) - 4)
                elif event.type == pygame.TEXTINPUT and self.game is None and self.view == 'creator':
                    self.edit_creator_text(event.text)
                elif event.type == pygame.KEYDOWN and self.game is None and self.view == 'creator':
                    focus = self.creator['focus']
                    if event.key == pygame.K_BACKSPACE and focus:
                        self.creator[focus] = self.creator[focus][:-1]
                    elif event.key == pygame.K_RETURN and focus == 'notes':
                        self.edit_creator_text('\n')
                elif event.type == pygame.KEYDOWN and self.game is not None and self.game['mode'] == 'sandbox' and self.view != 'inventory' and self.overview is None:
                    directions = {
                        pygame.K_UP: 'up',
                        pygame.K_DOWN: 'down',
                        pygame.K_LEFT: 'left',
                        pygame.K_RIGHT: 'right',
                    }
                    direction = directions.get(event.key)
                    if direction:
                        self.move_sandbox(direction)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_position = self.mouse_position(event.pos)
                    for rect, action in reversed(self.buttons):
                        if rect.collidepoint(mouse_position):
                            self.handle_action(action)
                            break
            if self.game is None and self.view == 'creator':
                self.draw_creator()
            elif self.game is None:
                self.draw_selection()
            else:
                self.draw_game()
            self.present()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()


if __name__ == '__main__':
    Hiraeth().run()
