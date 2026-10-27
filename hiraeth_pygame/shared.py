import json
import os
import random
from pathlib import Path
import uuid

import pygame

if __package__:
    from .config import CONFIG, SEX_OPTIONS
    from .rules import RULES
else:
    from config import CONFIG, SEX_OPTIONS
    from rules import RULES


ROOT = Path(__file__).resolve().parent
CHARACTERS_FILE = ROOT.parent / 'characters.json'
SAVE_FILE = ROOT / 'hiraeth.json'
TRAITS_FILE = ROOT.parent / 'traits.json'
WIDTH, HEIGHT = 1000, 720
WINDOW_SIZE = (1280, 900)
MAX_PARTY = 4
DOWNTIME_ACTIVITIES = ('health', 'magica', 'stamina', 'repair')
DOWNTIME_LABELS = {
    'health': 'Health',
    'magica': 'Magica',
    'stamina': 'Stamina',
    'repair': 'Repair AP',
}

INK = (31, 43, 40)
MUTED = (99, 113, 105)
PAPER = (235, 233, 220)
PANEL = (221, 222, 211)
WHITE = (249, 247, 237)
GREEN = (46, 90, 84)
DARK_GREEN = (20, 39, 37)
GOLD = (229, 189, 104)
CORAL = (189, 97, 71)
LINE = (194, 201, 190)

STATS = {
    'STR': 'Strength',
    'AGI': 'Agility',
    'CON': 'Constitution',
    'CHA': 'Charisma',
    'WIS': 'Wisdom',
    'WIL': 'Willpower',
}

def read_characters():
    if not CHARACTERS_FILE.exists():
        return [], 'No character archive found. Create characters in the workshop first.'
    try:
        with CHARACTERS_FILE.open(encoding='utf-8') as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        return [], f'Could not read the character archive: {error}'
    if not isinstance(data, list):
        return [], 'The character archive must contain a list.'
    usable = []
    seen = set()
    for character in data:
        if not isinstance(character, dict) or not character.get('Name'):
            continue
        if not isinstance(character.get('Stats'), dict) or not isinstance(character.get('Derived'), dict):
            continue
        identity = character.get('Id') or character['Name']
        if identity in seen:
            continue
        seen.add(identity)
        usable.append(character)
    if not usable:
        return [], 'No usable characters found. Create a character in the workshop first.'
    return usable, ''


def modifier(character, stat):
    try:
        value = int(character.get('Stats', {}).get(stat, 10))
    except (TypeError, ValueError):
        value = 10
    return (value - 10) // 2


def character_point_limit(level, race):
    return 60 + (2 * int(level)) + (2 if race == 'Human' else 0)


def spell_capacity(character):
    traits = character.get('Traits', {})
    try:
        sorcery_rank = int(traits.get('Sorcery', 0) or 0)
    except (TypeError, ValueError):
        sorcery_rank = 0
    has_sorcery = bool(character.get('Meta', {}).get('Has Sorcery')) if isinstance(character.get('Meta'), dict) else False
    if character.get('Race') == 'Shei':
        return max(0, modifier(character, 'WIL')) + 1
    if sorcery_rank < 5 and not has_sorcery:
        return 0
    return max(0, modifier(character, 'WIL'))


def new_battle(config):
    templates = config['monsters']
    count_range = config['journey']['monsters_per_battle']
    count = random.randint(count_range['min'], count_range['max'])
    enemies = []
    for template in random.sample(templates, count):
        enemy = dict(template)
        enemy['health_now'] = enemy['health']
        enemy['stamina_now'] = max(1, enemy['damage'] * 2)
        enemy['magica_now'] = max(1, enemy['damage'] * 2)
        enemies.append(enemy)
    return {
        'enemies': enemies,
        'phase': 'planning',
        'round': 1,
        'plans': {},
        'turn': 0,
        'guarding': [],
    }


