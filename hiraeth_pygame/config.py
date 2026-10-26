import json
import math
from string import Formatter
from pathlib import Path


CONFIG_FILE = Path(__file__).with_name('game_config.json')
SEX_OPTIONS = ('Male', 'Female', 'Agender', 'Gender fluid')


class ConfigurationError(ValueError):
    pass


def _object(value, label):
    if not isinstance(value, dict):
        raise ConfigurationError(f'{label} must be an object.')
    return value


def _integer(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f'{label} must be a whole number.')
    if minimum is not None and value < minimum:
        raise ConfigurationError(f'{label} must be at least {minimum}.')
    return value


def _number(value, label, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f'{label} must be a number.')
    if not math.isfinite(value):
        raise ConfigurationError(f'{label} must be finite.')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        bounds = f'between {minimum} and {maximum}'
        raise ConfigurationError(f'{label} must be {bounds}.')
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f'{label} must be a non-empty string.')
    return value


def load_config(path=CONFIG_FILE):
    try:
        with Path(path).open(encoding='utf-8') as file:
            config = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError(f'Could not load {path}: {error}') from error

    config = _object(config, 'Configuration')
    journey = _object(config.get('journey'), 'journey')
    combat = _object(config.get('combat'), 'combat')
    sandbox = _object(config.get('sandbox'), 'sandbox')
    monsters = config.get('monsters')
    events = config.get('events')
    texts = _object(config.get('text'), 'text')

    _integer(journey.get('stages'), 'journey.stages', 1)
    for key in (
        'starting_supply', 'starting_wealth', 'supply_per_travel',
        'town_upkeep_wealth_per_turn', 'supply_per_wealth_base',
        'supply_per_camp', 'camp_heal_per_member', 'victory_wealth',
    ):
        _integer(journey.get(key), f'journey.{key}', 0)
    _integer(journey.get('starting_reputation'), 'journey.starting_reputation')
    _integer(journey.get('victory_reputation'), 'journey.victory_reputation')
    _number(journey.get('combat_chance'), 'journey.combat_chance', 0, 1)
    _number(journey.get('event_chance'), 'journey.event_chance', 0, 1)

    town_level = _object(journey.get('town_level'), 'journey.town_level')
    level_min = _integer(town_level.get('min'), 'journey.town_level.min', 1)
    _integer(town_level.get('max'), 'journey.town_level.max', level_min)
    distances = _object(journey.get('distance'), 'journey.distance')
    for key in ('town_to_waystation', 'waystation_to_town'):
        distance = _object(distances.get(key), f'journey.distance.{key}')
        minimum = _integer(distance.get('min'), f'journey.distance.{key}.min', 1)
        _integer(distance.get('max'), f'journey.distance.{key}.max', minimum)
    for key in ('town_names', 'waystation_names'):
        names = journey.get(key)
        if not isinstance(names, list) or not names:
            raise ConfigurationError(f'journey.{key} must be a non-empty list.')
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ConfigurationError(f'journey.{key} must contain non-empty names.')

    enemy_count = _object(journey.get('monsters_per_battle'), 'journey.monsters_per_battle')
    minimum = _integer(enemy_count.get('min'), 'journey.monsters_per_battle.min', 1)
    maximum = _integer(enemy_count.get('max'), 'journey.monsters_per_battle.max', minimum)

    _integer(combat.get('attack_base_damage'), 'combat.attack_base_damage', 0)
    damage_min = _integer(combat.get('attack_damage_min'), 'combat.attack_damage_min', 1)
    damage_max = _integer(combat.get('attack_damage_max'), 'combat.attack_damage_max', damage_min)
    for key in ('constitution_reduction_divisor', 'guard_reduction_divisor', 'minimum_damage'):
        _integer(combat.get(key), f'combat.{key}', 1)

    map_rows = sandbox.get('map')
    if not isinstance(map_rows, list) or not map_rows:
        raise ConfigurationError('sandbox.map must contain at least one row.')
    if any(not isinstance(row, str) or not row for row in map_rows):
        raise ConfigurationError('sandbox.map rows must be non-empty strings.')
    map_width = len(map_rows[0])
    if any(len(row) != map_width for row in map_rows):
        raise ConfigurationError('sandbox.map rows must all have the same width.')
    if map_width > 35 or len(map_rows) > 12:
        raise ConfigurationError('sandbox.map must be no wider than 35 tiles or taller than 12 tiles.')
    blocked_symbols = sandbox.get('blocked_symbols')
    if not isinstance(blocked_symbols, list) or any(not isinstance(symbol, str) or len(symbol) != 1 for symbol in blocked_symbols):
        raise ConfigurationError('sandbox.blocked_symbols must be a list of single-character symbols.')
    start = _object(sandbox.get('start'), 'sandbox.start')
    start_x = _integer(start.get('x'), 'sandbox.start.x', 0)
    start_y = _integer(start.get('y'), 'sandbox.start.y', 0)
    if start_y >= len(map_rows) or start_x >= map_width:
        raise ConfigurationError('sandbox.start must be within the configured map.')
    if map_rows[start_y][start_x] in blocked_symbols:
        raise ConfigurationError('sandbox.start cannot be on a blocked map tile.')
    legend = sandbox.get('legend')
    if not isinstance(legend, list) or not legend or any(not isinstance(item, str) or not item for item in legend):
        raise ConfigurationError('sandbox.legend must be a list of non-empty strings.')
    sandbox_text = _object(sandbox.get('text'), 'sandbox.text')
    for key in ('title', 'description', 'coordinates', 'move_log', 'blocked_log'):
        _text(sandbox_text.get(key), f'sandbox.text.{key}')
    directions = _object(sandbox_text.get('directions'), 'sandbox.text.directions')
    for key in ('up', 'down', 'left', 'right'):
        _text(directions.get(key), f'sandbox.text.directions.{key}')

    if not isinstance(monsters, list) or not monsters:
        raise ConfigurationError('monsters must be a non-empty list.')
    if maximum > len(monsters):
        raise ConfigurationError('journey.monsters_per_battle.max cannot exceed the number of monsters.')
    monster_names = set()
    for index, raw_monster in enumerate(monsters):
        monster = _object(raw_monster, f'monsters[{index}]')
        name = _text(monster.get('name'), f'monsters[{index}].name')
        if name in monster_names:
            raise ConfigurationError(f'Monster names must be unique: {name}.')
        monster_names.add(name)
        _text(monster.get('description'), f'monsters[{index}].description')
        for key in ('health', 'attack', 'defense'):
            _integer(monster.get(key), f'monsters[{index}].{key}', 1)

    if not isinstance(events, list) or not events:
        raise ConfigurationError('events must be a non-empty list.')
    for index, raw_event in enumerate(events):
        event = _object(raw_event, f'events[{index}]')
        _text(event.get('title'), f'events[{index}].title')
        _text(event.get('description'), f'events[{index}].description')
        _integer(event.get('rarity'), f'events[{index}].rarity', 1)
        choices = event.get('choices')
        if not isinstance(choices, list) or not 1 <= len(choices) <= 4:
            raise ConfigurationError(f'events[{index}].choices must contain between one and four choices.')
        for choice_index, raw_choice in enumerate(choices):
            choice = _object(raw_choice, f'events[{index}].choices[{choice_index}]')
            _text(choice.get('label'), f'events[{index}].choices[{choice_index}].label')
            _text(choice.get('result'), f'events[{index}].choices[{choice_index}].result')
            for key in ('supply', 'wealth', 'reputation'):
                _integer(choice.get(key), f'events[{index}].choices[{choice_index}].{key}')

    for key in (
        'game_title', 'selection_kicker', 'selection_subtitle',
        'selection_intro_title', 'selection_intro', 'starting_resources',
        'combat_intro', 'journey_intro', 'travel_button', 'camp_button',
        'supply_shortage', 'guard_button', 'guard_subtitle', 'bestiary_heading', 'journal_heading',
        'win_title', 'win_summary', 'loss_title', 'loss_summary',
        'battle_start_log', 'dilemma_log', 'party_falls_log', 'victory_log',
        'camp_log', 'guard_log', 'enemy_hit_log', 'player_hit_log',
        'player_miss_log', 'event_result_log', 'journey_start_log',
    ):
        _text(texts.get(key), f'text.{key}')

    journey_titles = _object(texts.get('journey_titles'), 'text.journey_titles')
    for key in ('combat', 'event', 'journey', 'won', 'lost'):
        _text(journey_titles.get(key), f'text.journey_titles.{key}')
    template_fields = {
        'starting_resources': {'supply', 'wealth', 'reputation'},
        'dilemma_log': {'title'},
        'victory_log': {'wealth', 'reputation'},
        'camp_log': {'supply', 'health'},
        'guard_log': {'name'},
        'enemy_hit_log': {'monster', 'character', 'damage'},
        'player_hit_log': {'character', 'monster', 'damage'},
        'player_miss_log': {'character', 'monster'},
        'event_result_log': {'result', 'reputation'},
        'journey_start_log': {'party', 'supply'},
    }
    for key, required_fields in template_fields.items():
        try:
            fields = {
                field_name
                for _, field_name, _, _ in Formatter().parse(texts[key])
                if field_name is not None
            }
        except ValueError as error:
            raise ConfigurationError(f'text.{key} has invalid formatting: {error}') from error
        if fields != required_fields:
            raise ConfigurationError(
                f'text.{key} must use exactly these placeholders: {", ".join(sorted(required_fields))}.'
            )
    for key, required_fields in (
        ('coordinates', {'x', 'y'}),
        ('move_log', {'direction', 'x', 'y'}),
        ('blocked_log', {'direction'}),
    ):
        try:
            fields = {
                field_name
                for _, field_name, _, _ in Formatter().parse(sandbox_text[key])
                if field_name is not None
            }
        except ValueError as error:
            raise ConfigurationError(f'sandbox.text.{key} has invalid formatting: {error}') from error
        if fields != required_fields:
            raise ConfigurationError(
                f'sandbox.text.{key} must use exactly these placeholders: {", ".join(sorted(required_fields))}.'
            )
    return config


CONFIG = load_config()
