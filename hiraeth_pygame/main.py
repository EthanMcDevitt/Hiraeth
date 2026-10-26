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
MAX_PARTY = 4

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
        enemy['stamina_now'] = max(1, enemy['attack'] * 2)
        enemy['magica_now'] = max(1, enemy['attack'] * 2)
        enemies.append(enemy)
    return {
        'enemies': enemies,
        'phase': 'planning',
        'round': 1,
        'plans': {},
        'turn': 0,
        'guarding': [],
    }


class Hiraeth:
    def __init__(self):
        self.config = CONFIG
        self.journey = self.config['journey']
        self.combat = self.config['combat']
        self.texts = self.config['text']
        self.rules = RULES
        pygame.init()
        pygame.display.set_caption(self.texts['game_title'])
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
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
        self.inventory_recipient = 0
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
        self.load_save()

    @staticmethod
    def read_creator_options():
        core_types = {'General', 'Drawback', 'Martial', 'Sorcery', 'Magic'}
        try:
            with TRAITS_FILE.open(encoding='utf-8-sig') as file:
                catalog = json.load(file)
            if not isinstance(catalog, list):
                raise ValueError('Trait catalog must contain a list.')
            traits = [
                trait for trait in catalog
                if isinstance(trait, dict) and trait.get('Name') and not trait.get('PlayerOnly')
            ]
            races = ['Human'] + sorted({
                trait['Type'] for trait in traits
                if trait.get('Type') not in core_types
            })
            return races, sorted(traits, key=lambda trait: (trait.get('Type', ''), trait['Name']))
        except (OSError, json.JSONDecodeError, ValueError):
            return ['Human'], []

    def load_save(self):
        if not SAVE_FILE.exists():
            return
        try:
            with SAVE_FILE.open(encoding='utf-8') as file:
                saved = json.load(file)
            if not isinstance(saved.get('party'), list) or not 1 <= len(saved['party']) <= MAX_PARTY:
                raise ValueError('saved party must contain one to four characters')
            for member in saved['party']:
                if not isinstance(member.get('Stats'), dict):
                    raise ValueError('saved character is missing attributes')
                self.normalize_member(member)
            saved.setdefault('location', {'type': 'town', 'name': 'Briar Glen', 'level': 2})
            saved.setdefault('travel_remaining', None)
            saved.setdefault('travel_destination', None)
            saved.setdefault('next_stop_type', 'waystation')
            if saved.get('mode') == 'journey' and saved['location'].get('type') in ('town', 'waystation'):
                saved['location'] = {'type': 'wilderness', 'name': 'The old road'}
                saved['travel_remaining'] = 1
                saved['travel_destination'] = None
            if saved.get('mode') == 'combat' and isinstance(saved.get('battle'), dict):
                battle = saved['battle']
                battle.setdefault('phase', 'planning')
                battle.setdefault('plans', {})
                battle.setdefault('targeting', None)
                battle.setdefault('planning_actor', battle.get('turn', 0))
            if min(saved['supply'], saved['wealth']) < 0:
                raise ValueError('saved resources cannot be negative')
            saved.setdefault('party_inventory', [])
            saved.setdefault('camp_recovery', 'health')
            self.continuation = saved
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            self.message = f'Saved journey could not be restored: {error}'

    def save(self):
        if self.game is None:
            return True
        try:
            with SAVE_FILE.open('w', encoding='utf-8') as file:
                json.dump(self.game, file, indent=2, ensure_ascii=False)
            self.message = ''
            return True
        except OSError as error:
            self.message = f'Could not save the journey: {error}'
            return False

    def delete_save(self):
        try:
            if SAVE_FILE.exists():
                SAVE_FILE.unlink()
            self.message = ''
            return True
        except OSError as error:
            self.message = f'Could not delete the saved journey: {error}'
            return False

    def text(self, value, x, y, color=INK, font=None):
        rendered = (font or self.body).render(str(value), True, color)
        self.screen.blit(rendered, (x, y))
        return rendered.get_height()

    def wrapped(self, value, rect, color=MUTED, font=None, line_gap=5):
        font = font or self.body
        lines = []
        line = ''
        for word in str(value).split():
            candidate = f'{line} {word}'.strip()
            if line and font.size(candidate)[0] > rect.width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        y = rect.y
        for line in lines:
            if y + font.get_linesize() > rect.bottom:
                break
            self.text(line, rect.x, y, color, font)
            y += font.get_linesize() + line_gap
        return y

    def box(self, rect, color=WHITE, border=LINE, radius=4):
        pygame.draw.rect(self.screen, color, rect, border_radius=radius)
        if border:
            pygame.draw.rect(self.screen, border, rect, width=1, border_radius=radius)

    def button(self, rect, label, action, primary=False, enabled=True, subtitle=None):
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        color = GREEN if primary else (229, 235, 227)
        border = GREEN if primary else (190, 201, 190)
        if not enabled:
            color = (204, 207, 197)
            border = color
        elif hovered:
            color = DARK_GREEN if primary else (211, 224, 211)
        pygame.draw.rect(self.screen, color, rect, border_radius=3)
        pygame.draw.rect(self.screen, border, rect, width=1, border_radius=3)
        label_color = WHITE if primary and enabled else (INK if enabled else MUTED)
        font = self.small if subtitle else self.body
        rendered = font.render(label, True, label_color)
        label_y = 4 if subtitle else (rect.height - rendered.get_height()) // 2
        self.screen.blit(rendered, (rect.x + 12, rect.y + label_y))
        if subtitle:
            self.text(subtitle, rect.x + 12, rect.y + 21, GOLD if primary else MUTED, self.tiny)
        if enabled:
            self.buttons.append((rect, action))

    def frame(self, kicker, subtitle=''):
        self.screen.fill((17, 27, 27))
        pygame.draw.rect(self.screen, (20, 32, 31), (0, 0, WIDTH, 60))
        self.text(f"✦  {self.texts['game_title'].upper()}", 32, 21, GOLD, self.small)
        self.text('ESC  QUIT', WIDTH - 98, 23, (196, 203, 190), self.tiny)
        pygame.draw.rect(self.screen, PAPER, (25, 75, WIDTH - 50, HEIGHT - 100), border_radius=3)
        pygame.draw.rect(self.screen, (110, 116, 99), (25, 75, WIDTH - 50, HEIGHT - 100), width=1, border_radius=3)
        self.buttons = []
        self.text(kicker.upper(), 58, 101, CORAL, self.tiny)
        if subtitle:
            self.text(subtitle, 58, 122, MUTED, self.tiny)
        if self.game is not None:
            if self.view != 'inventory':
                self.button(pygame.Rect(660, 14, 112, 32), 'Inventory', 'inventory')
            self.button(pygame.Rect(790, 14, 112, 32), 'Quit to menu', 'quit_prompt')

    def draw_quit_prompt(self):
        if not self.quit_prompt:
            return
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((17, 27, 27, 190))
        self.screen.blit(overlay, (0, 0))
        self.buttons.append((pygame.Rect(0, 0, WIDTH, HEIGHT), 'modal_dismiss'))
        rect = pygame.Rect(275, 250, 450, 210)
        self.box(rect, PAPER, GOLD, radius=6)
        self.text('Leave this session?', rect.x + 24, rect.y + 23, INK, self.font)
        self.wrapped(
            'Save it to continue later, or delete the saved session and return to the menu.',
            pygame.Rect(rect.x + 24, rect.y + 62, 402, 45), MUTED, self.small, 2,
        )
        self.button(pygame.Rect(rect.x + 24, rect.y + 125, 190, 42), 'Save and return', 'save_to_menu', primary=True)
        self.button(pygame.Rect(rect.x + 224, rect.y + 125, 200, 42), 'Delete and return', 'delete_to_menu')
        self.button(pygame.Rect(rect.x + 24, rect.y + 174, 130, 28), 'Keep playing', 'cancel_quit')
        if self.message:
            self.text(self.message, rect.x + 165, rect.y + 180, CORAL, self.tiny)

    def draw_selection(self):
        self.frame(self.texts['selection_kicker'], self.texts['selection_subtitle'])
        self.text(self.texts['selection_intro_title'], 58, 158, INK, pygame.font.SysFont('georgia', 48))
        self.wrapped(
            self.texts['selection_intro'],
            pygame.Rect(60, 220, 840, 42), MUTED, self.body,
        )
        if not self.characters:
            self.box(pygame.Rect(58, 300, 840, 112), (242, 238, 223), (213, 197, 165))
            self.wrapped(self.archive_message, pygame.Rect(78, 320, 790, 50), CORAL)
            self.text('Create your first character here, or use the Character Workshop.', 78, 365, MUTED, self.small)
            self.button(pygame.Rect(636, 551, 272, 52), 'Create a character', 'create_screen', primary=True)
            if self.continuation:
                self.button(pygame.Rect(636, 612, 272, 40), 'Resume saved session', 'resume')
            self.text(self.texts['starting_resources'].format(
                supply=self.journey['starting_supply'],
                wealth=self.journey['starting_wealth'],
                reputation=self.journey['starting_reputation'],
            ), 636, 617, MUTED, self.small)
            if self.message:
                self.wrapped(self.message, pygame.Rect(58, 655, 850, 20), CORAL, self.tiny, 1)
            return

        self.text('AVAILABLE CHARACTERS', 60, 280, MUTED, self.tiny)
        visible = self.characters[self.character_offset:self.character_offset + 4]
        for index, character in enumerate(visible):
            real_index = self.character_offset + index
            y = 303 + index * 67
            rect = pygame.Rect(58, y, 548, 59)
            is_selected = real_index in self.selected
            self.box(rect, (246, 244, 232) if is_selected else (226, 227, 215), GOLD if is_selected else LINE)
            self.buttons.append((rect, ('toggle_member', real_index)))
            marker = 'IN PARTY' if is_selected else 'ADD TO PARTY'
            self.text(character['Name'], rect.x + 13, rect.y + 8, INK, self.font)
            self.text(f"{character.get('Race', 'Unknown')}  ·  LV {character.get('Level', 1)}  ·  {marker}", rect.x + 14, rect.y + 36, GREEN if is_selected else MUTED, self.tiny)
        if len(self.characters) > 4:
            self.button(pygame.Rect(58, 581, 110, 34), 'Earlier', 'earlier', enabled=self.character_offset > 0)
            self.button(pygame.Rect(178, 581, 110, 34), 'Later', 'later', enabled=self.character_offset + 4 < len(self.characters))
        self.box(pygame.Rect(636, 303, 272, 225), WHITE)
        self.text(f'PARTY  {len(self.selected)} / {MAX_PARTY}', 654, 320, GREEN, self.small)
        for slot, index in enumerate(self.selected):
            character = self.characters[index]
            health = character.get('Derived', {}).get('Health', '?')
            self.text(f"{slot + 1}. {character['Name']}  ·  HP {health}", 654, 350 + slot * 35, INK, self.body)
        if not self.selected:
            self.wrapped('Choose at least one character to begin.', pygame.Rect(654, 359, 230, 45), MUTED, self.small)
        self.button(pygame.Rect(636, 551, 272, 44), 'Begin the journey', 'start', primary=True, enabled=bool(self.selected))
        self.button(pygame.Rect(636, 603, 272, 38), 'Sandbox adventure', 'start_sandbox', enabled=bool(self.selected))
        self.button(pygame.Rect(636, 649, 272, 34), 'Create a character', 'create_screen')
        if self.continuation:
            self.button(pygame.Rect(330, 581, 250, 36), 'Resume saved session', 'resume')
        self.wrapped(self.texts['starting_resources'].format(
            supply=self.journey['starting_supply'],
            wealth=self.journey['starting_wealth'],
            reputation=self.journey['starting_reputation'],
        ), pygame.Rect(58, 646, 500, 26), MUTED, self.tiny, 1)
        if self.message:
            self.wrapped(self.message, pygame.Rect(58, 655, 850, 20), CORAL, self.tiny, 1)

    def draw_creator(self):
        self.frame('Create a traveler', 'DESIGN A CHARACTER FOR YOUR ROSTER')
        creator = self.creator
        self.text('A new face on the road', 58, 155, INK, pygame.font.SysFont('georgia', 32))
        self.text('Name', 58, 204, MUTED, self.tiny)
        self.draw_input('name', pygame.Rect(58, 221, 850, 40), creator['name'])
        self.text('Race', 58, 276, MUTED, self.tiny)
        self.button(pygame.Rect(58, 293, 410, 40), creator['race'] + '  ▾', 'dropdown_race')
        self.text('Level', 500, 276, MUTED, self.tiny)
        self.button(pygame.Rect(500, 293, 44, 40), '−', ('creator_level', -1))
        self.box(pygame.Rect(550, 293, 82, 40), WHITE, LINE)
        self.text(creator['level'], 581, 303, INK, self.body)
        self.button(pygame.Rect(638, 293, 44, 40), '+', ('creator_level', 1))
        self.text('Sex', 700, 276, MUTED, self.tiny)
        self.button(pygame.Rect(700, 293, 208, 40), creator['sex'] + '  ▾', 'dropdown_sex')
        self.text(
            f"Max spells: {self.creator_spell_capacity()}  ·  requires Shei ancestry or Sorcery rank 5",
            58, 334, GREEN, self.tiny,
        )

        point_limit = character_point_limit(creator['level'], creator['race'])
        allocated = sum(map(int, creator['stats'].values())) + sum(map(int, creator['traits'].values()))
        self.text(f'Attributes  ·  {allocated} / {point_limit} points (includes traits)  ·  6–20', 58, 353, MUTED, self.tiny)
        for index, key in enumerate(STATS):
            column, row = divmod(index, 3)
            x = 58 + column * 434
            y = 372 + row * 48
            rect = pygame.Rect(x, y, 410, 42)
            self.box(rect, PANEL)
            self.text(f'{key}  ·  {STATS[key]}', x + 12, y + 12, INK, self.small)
            self.button(pygame.Rect(x + 300, y + 4, 38, 34), '−', ('creator_stat', key, -1))
            self.text(creator['stats'][key], x + 351, y + 12, GREEN, self.body)
            self.button(pygame.Rect(x + 365, y + 4, 38, 34), '+', ('creator_stat', key, 1))

        self.text('Traits', 58, 518, MUTED, self.tiny)
        picked = creator.get('trait_pick')
        picked_name = picked or 'Choose a trait'
        self.button(pygame.Rect(58, 535, 430, 38), picked_name + '  ▾', 'dropdown_trait')
        picked_trait = next((trait for trait in self.trait_catalog if trait['Name'] == picked), None)
        rank = creator.get('trait_rank', 1)
        if picked_trait and picked_trait.get('Variable'):
            self.button(pygame.Rect(496, 535, 34, 38), '−', ('creator_trait_rank', -1))
            self.text(f'R{rank}', 540, 548, GREEN, self.tiny)
            self.button(pygame.Rect(570, 535, 34, 38), '+', ('creator_trait_rank', 1))
        else:
            self.text(f'Cost {picked_trait.get("Cost", 0) if picked_trait else "—"}', 510, 548, GREEN, self.tiny)
        trait_cost = self.creator_trait_cost(picked_trait, rank) if picked_trait else 0
        allocated = self.creator_points()
        limit = character_point_limit(creator['level'], creator['race'])
        current_cost = int(creator['traits'].get(picked, 0)) if picked else 0
        self.button(
            pygame.Rect(620, 535, 135, 38), 'Add trait', 'add_trait',
            enabled=bool(picked_trait and allocated - current_cost + trait_cost <= limit),
        )
        self.button(
            pygame.Rect(768, 535, 140, 38),
            'Remove selected',
            'remove_trait',
            enabled=bool(picked and picked in creator['traits']),
        )
        selected_traits = list(creator['traits'])
        selected_text = 'Selected: ' + (
            ' · '.join(selected_traits[:5]) if selected_traits else 'none'
        )
        if len(selected_traits) > 5:
            selected_text += f"  ·  +{len(selected_traits) - 5} more"
        self.wrapped(selected_text, pygame.Rect(58, 578, 840, 30), GREEN, self.tiny, 1)
        self.text('Other notes', 58, 612, MUTED, self.tiny)
        self.draw_input('notes', pygame.Rect(58, 629, 850, 31), creator['notes'])
        self.button(pygame.Rect(58, 664, 220, 34), 'Save character', 'create_save', primary=True)
        self.button(pygame.Rect(292, 664, 170, 34), 'Back to roster', 'creator_cancel')
        if self.message:
            self.text(self.message, 480, 676, CORAL, self.tiny)
        self.draw_creator_dropdown()

    def draw_creator_dropdown(self):
        if not self.dropdown:
            return
        creator = self.creator
        kind = self.dropdown
        if kind == 'race':
            options = self.races
            rect = pygame.Rect(58, 333, 410, min(7, len(options)) * 30 + 2)
            visible_start = 0
        elif kind == 'sex':
            options = list(SEX_OPTIONS)
            rect = pygame.Rect(700, 333, 208, len(options) * 30 + 2)
            visible_start = 0
        else:
            options = self.creator_trait_options()
            rect = pygame.Rect(58, 575, 430, min(7, len(options)) * 30 + 2)
            visible_start = self.dropdown_offset
        self.box(rect, WHITE, GREEN, radius=3)
        visible = options[visible_start:visible_start + 7]
        if kind == 'trait' and not visible:
            self.text('No traits are available in the catalog.', rect.x + 10, rect.y + 8, MUTED, self.tiny)
        for index, option in enumerate(visible):
            row = pygame.Rect(rect.x + 1, rect.y + 1 + index * 30, rect.width - 2, 30)
            if kind == 'trait':
                label = f"{option['Name']}  ·  {option.get('Type', 'Trait')}"
                action = ('select_trait', option['Name'])
            else:
                label = option
                action = ('select_dropdown', kind, option)
            self.text(label, row.x + 9, row.y + 8, INK, self.tiny)
            self.buttons.append((row, action))
        if kind == 'trait' and len(options) > 7:
            self.text(f'{visible_start + 1}–{min(visible_start + 7, len(options))} of {len(options)}  ·  scroll', rect.x + 390, rect.bottom + 5, MUTED, self.tiny)

    def creator_trait_options(self):
        shared_types = {'General', 'Drawback', 'Martial', 'Sorcery', 'Magic'}
        race = self.creator['race']
        return [
            trait for trait in self.trait_catalog
            if trait.get('Type') in shared_types or trait.get('Type') == race
        ]

    def creator_trait_cost(self, trait, rank=None):
        if trait.get('Variable'):
            minimum = int(trait.get('MinCost', trait.get('Cost', 1)))
            maximum = int(trait.get('MaxCost', trait.get('Cost', minimum)))
            return max(minimum, min(maximum, int(rank if rank is not None else minimum)))
        return int(trait.get('Cost', 0))

    def creator_spell_capacity(self):
        preview = {
            'Race': self.creator['race'],
            'Stats': {key: int(value) for key, value in self.creator['stats'].items()},
            'Traits': self.creator['traits'],
        }
        return spell_capacity(preview)

    def creator_points(self):
        return sum(map(int, self.creator['stats'].values())) + sum(
            map(int, self.creator['traits'].values())
        )

    def draw_input(self, key, rect, value, multiline=False):
        active = self.creator['focus'] == key
        self.box(rect, WHITE, GOLD if active else LINE)
        self.buttons.append((rect, ('focus', key)))
        value = str(value)
        if multiline:
            lines = value.splitlines() or ['']
            for row, line in enumerate(lines[-2:]):
                self.text(line, rect.x + 10, rect.y + 6 + row * 18, INK, self.small)
        else:
            self.text(value, rect.x + 10, rect.y + 11, INK, self.body)

    def draw_member_overview(self):
        member = self.game['party'][self.overview]
        self.frame('Party member overview', 'CHARACTER DETAILS')
        self.text(member['Name'], 58, 158, INK, pygame.font.SysFont('georgia', 38))
        self.text(
            f"{member.get('Race', 'Traveler')}  ·  LEVEL {member.get('Level', 1)}  ·  {member.get('Sex', 'Sex unspecified')}",
            60, 208, GREEN, self.small,
        )
        self.text(f"Health  {max(0, member['health'])} / {member['max_health']}", 60, 240, CORAL, self.body)
        self.text(
            f"Stamina  {member.get('stamina_now', 0)}/{member.get('max_stamina', 0)}"
            f"  ·  Magica  {member.get('magica_now', 0)}/{member.get('max_magica', 0)}",
            60, 263, GREEN, self.small,
        )

        self.text('ATTRIBUTES', 58, 286, MUTED, self.tiny)
        stats = member.get('Stats', {})
        for index, (key, label) in enumerate(STATS.items()):
            column, row = divmod(index, 2)
            x = 58 + column * 300
            y = 310 + row * 48
            self.box(pygame.Rect(x, y, 270, 42), PANEL)
            value = stats.get(key, '—')
            self.text(f'{label}  ({key})', x + 12, y + 12, INK, self.small)
            self.text(value, x + 224, y + 9, GREEN, self.body)

        derived = member.get('Derived', {})
        self.text('STATS', 58, 418, MUTED, self.tiny)
        derived_labels = ('Health', 'Stamina', 'Magica', 'Max Spells')
        for index, key in enumerate(derived_labels):
            value = member.get('max_spells', 0) if key == 'Max Spells' else derived.get(key, '—')
            self.text(f'{key}: {value}', 58 + index * 150, 440, DARK_GREEN, self.body)

        known_spells = [
            spell for spell in (
                self.item_by_id('spells', spell_id)
                for spell_id in member.get('known_spells', [])
            )
            if spell
        ]
        self.text('KNOWN SPELLS', 58, 470, MUTED, self.tiny)
        spell_names = '  ·  '.join(spell['name'] for spell in known_spells) or 'None learned'
        self.box(pygame.Rect(58, 486, 840, 48), WHITE, LINE)
        self.wrapped(spell_names, pygame.Rect(70, 498, 816, 30), INK, self.small, 1)

        traits = member.get('Traits', {})
        self.text('TRAITS', 58, 543, MUTED, self.tiny)
        trait_lines = [f'{name} (rank {rank})' for name, rank in traits.items()]
        trait_lines.extend(
            f"FREE {member.get('Race', 'ancestry')} ANCESTRY: {feature}"
            for feature in member.get('Ancestry Features', [])
        )
        self.wrapped(
            '  ·  '.join(trait_lines) if trait_lines else 'No recorded traits.',
            pygame.Rect(58, 559, 840, 37), INK, self.tiny, 1,
        )
        self.text('OTHER NOTES', 58, 603, MUTED, self.tiny)
        notes = member.get('Notes') or 'No additional notes.'
        self.wrapped(notes, pygame.Rect(58, 619, 840, 40), INK, self.small, 2)
        inventory = member.get('inventory', [])
        self.button(pygame.Rect(58, 667, 180, 32), 'Back to the road', 'overview_back', primary=True)
        self.button(pygame.Rect(252, 667, 180, 32), f'Inventory ({len(inventory)} items)', 'inventory')

    def item_by_id(self, category, item_id):
        return next((item for item in self.rules[category] if item['id'] == item_id), None)

    def item_name(self, category, item_id):
        item = self.item_by_id(category, item_id) if item_id else None
        return item['name'] if item else None

    def current_inventory(self):
        if self.inventory_owner is None:
            return self.game.setdefault('party_inventory', [])
        return self.game['party'][self.inventory_owner].setdefault('inventory', [])

    def draw_inventory(self):
        self.frame('Inventory & rules', 'EQUIPMENT, ARMOR, WEAPONS, AND KNOWN SPELLS')
        self.text(f"Wealth available: {self.game['wealth']}", 58, 151, GREEN, self.body)
        if self.game.get('mode') == 'town':
            self.text('Town stock; purchase access depends on settlement level and Reputation.', 58, 176, MUTED, self.tiny)
        else:
            self.text('Browse and manage gear; equipment purchases are only available in towns.', 58, 176, MUTED, self.tiny)

        categories = (('weapons', 'Weapons'), ('armor', 'Armor'), ('gear', 'Gear'), ('spells', 'Spells'))
        for index, (key, label) in enumerate(categories):
            rect = pygame.Rect(58 + index * 96, 200, 88, 34)
            self.button(rect, label, ('inventory_category', key), primary=self.inventory_category == key)

        self.box(pygame.Rect(58, 244, 365, 356), WHITE)
        self.text('AVAILABLE', 72, 257, MUTED, self.tiny)
        items = self.rules[self.inventory_category]
        visible = items[self.inventory_scroll:self.inventory_scroll + 7]
        if not visible:
            self.text('No entries in this section.', 74, 286, MUTED, self.small)
        for row_index, item in enumerate(visible):
            rect = pygame.Rect(68, 279 + row_index * 43, 344, 37)
            selected = item['id'] == self.inventory_selected
            self.box(rect, (246, 244, 232) if selected else PANEL, GOLD if selected else LINE)
            self.text(item['name'], rect.x + 9, rect.y + 5, INK, self.small)
            cost_label = f"Cast {item['cost']} Magica" if self.inventory_category == 'spells' else f"Wealth {item.get('cost', 0)}"
            self.text(cost_label, rect.x + 9, rect.y + 22, MUTED, self.tiny)
            self.buttons.append((rect, ('inventory_select', item['id'])))
        self.text(f'{self.inventory_scroll + 1}–{min(len(items), self.inventory_scroll + 7)} of {len(items)}  ·  scroll to browse',
                  72, 586, MUTED, self.tiny)

        self.box(pygame.Rect(444, 200, 464, 420), WHITE)
        self.text('CARRYING', 462, 216, MUTED, self.tiny)
        owners = [(None, 'Party')]
        owners.extend((index, member['Name'][:11]) for index, member in enumerate(self.game['party']))
        for index, (owner, label) in enumerate(owners):
            x = 462 + index * 87
            self.button(
                pygame.Rect(x, 236, 80, 31), label,
                ('inventory_owner', owner), primary=self.inventory_owner == owner,
            )

        if self.inventory_owner is None:
            owner_name = 'Party inventory'
            owned = self.game.setdefault('party_inventory', [])
            self.text(owner_name, 462, 281, GREEN, self.small)
            self.text(f'{len(owned)} shared items', 462, 300, MUTED, self.tiny)
            if self.game['party']:
                self.button(
                    pygame.Rect(462, 316, 230, 27),
                    f"Give items to {self.game['party'][self.inventory_recipient]['Name']}  ›",
                    ('inventory_recipient', 1),
                )
        else:
            member = self.game['party'][self.inventory_owner]
            owner_name = member['Name']
            owned = member.setdefault('inventory', [])
            capacity = max(1, int(member.get('Stats', {}).get('STR', 10)))
            slots = self.inventory_slots(owned)
            self.text(f'{owner_name}  ·  {slots}/{capacity} slots', 462, 281, GREEN, self.small)
            equip = member.setdefault('equipment', {'weapon': None, 'armor': None, 'helmet': None, 'shield': None})
            self.text(
                'Equipped: ' + (self.item_name('weapons', equip.get('weapon')) or 'Unarmed')
                + '  /  ' + ' / '.join(
                    self.item_name('armor', equip.get(key)) or '—'
                    for key in ('armor', 'helmet', 'shield')
                ),
                462, 300, MUTED, self.tiny,
            )

        if self.inventory_category == 'spells' and self.inventory_owner is not None:
            member = self.game['party'][self.inventory_owner]
            known = member.setdefault('known_spells', [])
            shown_owned = [self.item_by_id('spells', spell_id) for spell_id in known]
            self.text('KNOWN SPELLS', 462, 343, MUTED, self.tiny)
            known = [spell for spell in shown_owned if spell]
            visible_known = known[self.inventory_owned_scroll:self.inventory_owned_scroll + 5]
            for row_index, spell in enumerate(visible_known):
                self.text(f"{spell['name']}  ·  {spell['school']}  ·  {spell['cost']} Magica",
                          462, 366 + row_index * 26, INK, self.tiny)
            if len(known) > 5:
                self.text(f'{self.inventory_owned_scroll + 1}–{min(len(known), self.inventory_owned_scroll + 5)} of {len(known)}',
                          780, 343, MUTED, self.tiny)
            self.text(f"Spell capacity: {len(known)}/{member.get('max_spells', 0)}", 462, 486, GREEN, self.tiny)
        else:
            self.text('ITEMS IN THIS INVENTORY', 462, 343, MUTED, self.tiny)
            visible_owned = owned[self.inventory_owned_scroll:self.inventory_owned_scroll + 6]
            for row_index, item_id in enumerate(visible_owned):
                item = self.find_item(item_id)
                label = item['name'] if item else item_id
                if self.inventory_owner is not None:
                    equip = self.game['party'][self.inventory_owner].get('equipment', {})
                    equipped = item_id in equip.values()
                    label += '  · equipped' if equipped else ''
                rect = pygame.Rect(458, 362 + row_index * 29, 435, 25)
                self.box(rect, (246, 244, 232) if self.inventory_owned_index == row_index + self.inventory_owned_scroll else PANEL, LINE)
                self.text(label, rect.x + 8, rect.y + 5, INK, self.tiny)
                self.buttons.append((rect, ('inventory_owned', row_index + self.inventory_owned_scroll)))
            if len(owned) > 6:
                self.text(f'{self.inventory_owned_scroll + 1}–{min(len(owned), self.inventory_owned_scroll + 6)} of {len(owned)}',
                          462, 541, MUTED, self.tiny)

        selected = next((item for item in items if item['id'] == self.inventory_selected), None)
        if selected:
            detail_y = 512
            self.text(selected['name'], 462, detail_y, INK, self.body)
            if self.inventory_category == 'weapons':
                detail = f"{selected['range']} range  ·  {selected['damage']} {selected['damage_type']}  ·  {selected['traits']}"
            elif self.inventory_category == 'armor':
                detail = f"{selected['kind'].title()}  ·  {selected['ap']} AP  ·  {selected['slots']} slots  ·  {selected['traits']}"
            elif self.inventory_category == 'spells':
                detail = f"{selected['school']}  ·  {selected['cost']} Magica  ·  {selected['effect']}"
            else:
                detail = f"{selected['slots']} slots  ·  {selected['traits']}"
            self.wrapped(detail, pygame.Rect(462, detail_y + 23, 425, 43), MUTED, self.tiny, 1)

        if self.inventory_category == 'spells':
            member = self.game['party'][self.inventory_owner] if self.inventory_owner is not None else None
            can_learn = bool(
                member and selected
                and member.get('max_spells', 0) > len(member.get('known_spells', []))
                and selected['id'] not in member.get('known_spells', [])
            )
            self.button(pygame.Rect(462, 584, 200, 32), 'Learn spell', 'inventory_learn', primary=True, enabled=can_learn)
            can_cast = (
                self.game['mode'] not in ('combat', 'won', 'lost')
                and self.inventory_owner is not None
                and bool(selected)
                and selected['target'] == 'ally'
                and selected['id'] in self.game['party'][self.inventory_owner].get('known_spells', [])
            )
            self.button(pygame.Rect(674, 584, 210, 32), 'Cast on a character', 'inventory_cast', enabled=can_cast)
        else:
            location = self.game.get('location', {})
            is_town = location.get('type') == 'town'
            can_trade = is_town and location.get('level', 1) + self.game.get('reputation', 0) > 0
            buy_cost = selected.get('cost', 0) if selected else 0
            self.button(
                pygame.Rect(462, 584, 165, 32),
                'Buy item' if is_town else 'Town purchase only',
                'inventory_buy', primary=True,
                enabled=bool(selected and can_trade and self.game['wealth'] >= buy_cost),
            )
            can_move = self.inventory_owned_index is not None and self.inventory_owned_index < len(self.current_inventory())
            if self.inventory_owner is None:
                self.button(pygame.Rect(636, 584, 154, 32), 'Give to member', 'inventory_transfer', enabled=can_move and bool(self.game['party']))
            else:
                item_id = self.current_inventory()[self.inventory_owned_index] if can_move else None
                usable = bool(item_id and (self.item_by_id('weapons', item_id) or self.item_by_id('armor', item_id)))
                equipment = self.game['party'][self.inventory_owner].get('equipment', {})
                equipped = bool(item_id and item_id in equipment.values())
                self.button(
                    pygame.Rect(636, 584, 116, 32), 'Unequip' if equipped else 'Equip',
                    'inventory_unequip' if equipped else 'inventory_equip',
                    enabled=usable or equipped,
                )
                self.button(
                    pygame.Rect(758, 584, 136, 32), 'Store with party',
                    'inventory_transfer', enabled=can_move and not equipped,
                )
        self.button(
            pygame.Rect(58, 646, 190, 40),
            'Back to settlement' if self.game.get('mode') in ('town', 'waystation') else 'Back to the road',
            'inventory_back', primary=True,
        )
        if self.message:
            self.wrapped(self.message, pygame.Rect(270, 650, 630, 32), CORAL, self.tiny, 1)

    def find_item(self, item_id):
        for category in ('weapons', 'armor', 'gear', 'spells'):
            item = self.item_by_id(category, item_id)
            if item:
                return item
        return None

    def inventory_slots(self, item_ids):
        return sum((self.find_item(item_id) or {}).get('slots', 1) for item_id in item_ids)

    def is_encumbered(self, member):
        strength = max(1, int(member.get('Stats', {}).get('STR', 10)))
        return self.inventory_slots(member.get('inventory', [])) > strength

    def draw_resources(self):
        game = self.game
        journey_value = (
            f"{game['position']['x']}, {game['position']['y']}"
            if game['mode'] == 'sandbox'
            else f"{game['step']} / {self.journey['stages']}"
        )
        values = [
            ('SUPPLY', game['supply'], 'provisions'),
            ('WEALTH', game['wealth'], 'party funds'),
            ('REPUTATION', f"{game['reputation']:+d}", 'karma'),
            ('LOCATION' if game['mode'] == 'sandbox' else 'JOURNEY', journey_value, 'map coordinates' if game['mode'] == 'sandbox' else 'stages'),
        ]
        for index, (label, value, detail) in enumerate(values):
            x = 292 + index * 155
            rect = pygame.Rect(x, 147, 143, 66)
            self.box(rect, PANEL)
            pygame.draw.rect(self.screen, CORAL if label == 'REPUTATION' and game['reputation'] < 0 else GREEN, (rect.x, rect.y, rect.width, 2))
            self.text(label, rect.x + 10, rect.y + 9, MUTED, self.tiny)
            self.text(value, rect.x + 10, rect.y + 24, DARK_GREEN, pygame.font.SysFont('georgia', 21))
            self.text(detail, rect.x + 10, rect.y + 49, MUTED, self.tiny)

    def draw_party(self):
        self.text('THE PARTY', 58, 147, MUTED, self.tiny)
        battle = self.game.get('battle') if self.game['mode'] == 'combat' else None
        targeting = battle.get('targeting') if battle else None
        for index, member in enumerate(self.game['party']):
            rect = pygame.Rect(58, 169 + index * 90, 215, 78)
            living = member['health'] > 0
            active = bool(battle and battle.get('planning_actor') == index and living)
            self.box(rect, (246, 244, 232) if active else (226, 227, 215), GOLD if active else LINE)
            self.text(member['Name'], rect.x + 12, rect.y + 9, INK if living else MUTED, self.body)
            self.text(f"{member.get('Race', 'Traveler')}  ·  HP {max(0, member['health'])}/{member['max_health']}", rect.x + 12, rect.y + 32, GREEN if living else CORAL, self.tiny)
            stats = member.get('Stats', {})
            self.text('STR ' + str(stats.get('STR', 10)) + '   AGI ' + str(stats.get('AGI', 10)), rect.x + 12, rect.y + 52, MUTED, self.tiny)
            if targeting and targeting.get('target_type') == 'ally' and living:
                self.buttons.append((rect, ('combat_target_party', index)))
            elif battle:
                plan = battle.get('plans', {}).get(str(index))
                status = 'Choose move' if plan is None else self.plan_description(plan, battle)
                self.text(status, rect.x + 115, rect.y + 54, GOLD if plan else MUTED, self.tiny)
                if living and battle.get('phase') == 'planning':
                    self.buttons.append((rect, ('plan_member', index)))
            else:
                self.buttons.append((rect, ('overview', index)))

    def plan_description(self, plan, battle):
        if plan['kind'] == 'guard':
            return 'Guard locked'
        if plan['kind'] == 'attack':
            target = battle['enemies'][plan['target']]['name']
            return f'Attack: {target[:12]}'
        spell = self.item_by_id('spells', plan.get('spell_id'))
        if spell and spell['target'] == 'ally':
            target_name = self.game['party'][plan['target']]['Name']
        elif spell:
            target_name = battle['enemies'][plan['target']]['name']
        else:
            target_name = '?'
        return f"{(spell['name'] if spell else 'Spell')[:8]}: {target_name[:8]}"

    def draw_game(self):
        game = self.game
        if self.view == 'inventory':
            self.draw_inventory()
            self.draw_quit_prompt()
            return
        if self.view == 'spell_target':
            self.draw_spell_target()
            self.draw_quit_prompt()
            return
        if self.overview is not None:
            self.draw_member_overview()
            self.draw_quit_prompt()
            return
        if game['mode'] == 'sandbox':
            self.draw_sandbox()
            return
        location = game.get('location', {})
        title = location.get('name') if game['mode'] in ('town', 'waystation') else None
        title = title or self.texts['journey_titles'].get(game['mode'], self.texts['game_title'])
        place = location.get('name', 'the road')
        self.frame(
            f"DAY {game['day']}  /  STAGE {min(game['step'] + 1, self.journey['stages'])}",
            f"{place.upper()}  ·  TRAVELING AS {', '.join(member['Name'] for member in game['party'])}",
        )
        self.draw_party()
        self.draw_resources()
        self.text(title, 292, 231, INK, pygame.font.SysFont('georgia', 32))
        if game['mode'] == 'combat':
            self.draw_combat()
        elif game['mode'] == 'event':
            self.draw_event()
        elif game['mode'] == 'journey':
            self.draw_journey_actions()
        elif game['mode'] in ('town', 'waystation'):
            self.draw_settlement_actions()
        elif game['mode'] in ('won', 'lost'):
            self.draw_ending()
        if game['mode'] != 'event':
            self.draw_journal()
        if self.message:
            self.text(self.message, 292, 676, CORAL, self.tiny)
        self.draw_quit_prompt()

    def draw_spell_target(self):
        spell = self.item_by_id('spells', self.pending_spell['spell_id'])
        actor = self.game['party'][self.pending_spell['actor']]
        self.frame('Cast spell', f"{actor['Name']}  ·  {spell['name']}  ·  {spell['cost']} Magica")
        self.text(spell['effect'], 58, 165, MUTED, self.body)
        self.text('Choose a party member to target:', 58, 220, GREEN, self.small)
        for index, member in enumerate(self.game['party']):
            rect = pygame.Rect(58, 254 + index * 75, 590, 63)
            enabled = member['health'] > 0 and actor['magica_now'] >= spell['cost'] and spell['target'] == 'ally'
            self.box(rect, WHITE if enabled else PANEL, GOLD if enabled else LINE)
            self.text(member['Name'], rect.x + 14, rect.y + 8, INK, self.body)
            self.text(
                f"HP {member['health']}/{member['max_health']}  ·  Magica {member['magica_now']}/{member['max_magica']}",
                rect.x + 14, rect.y + 35, MUTED, self.tiny,
            )
            if enabled:
                self.buttons.append((rect, ('cast_outside_target', index)))
        if spell['target'] == 'foe':
            self.wrapped('Hostile-target spells can only be cast during combat.', pygame.Rect(58, 560, 590, 35), CORAL, self.small)
        self.button(pygame.Rect(58, 635, 190, 40), 'Back to inventory', 'spell_target_back', primary=True)
        if self.message:
            self.wrapped(self.message, pygame.Rect(270, 645, 620, 30), CORAL, self.tiny, 1)

    def draw_sandbox(self):
        sandbox = self.config['sandbox']
        position = self.game['position']
        self.frame(
            f"SANDBOX  /  DAY {self.game['day']}",
            f"TRAVELING AS {', '.join(member['Name'] for member in self.game['party'])}",
        )
        self.draw_party()
        self.draw_resources()
        self.text(sandbox['text']['title'], 292, 231, INK, pygame.font.SysFont('georgia', 30))
        self.wrapped(sandbox['text']['description'], pygame.Rect(292, 269, 590, 35), MUTED, self.small, 2)

        rows = sandbox['map']
        map_width = len(rows[0])
        font_size = max(12, min(24, 590 // map_width, 290 // len(rows)))
        map_font = pygame.font.SysFont('consolas', font_size, bold=True)
        cell_width = map_font.size('M')[0]
        map_x = 310 + max(0, (590 - cell_width * map_width) // 2)
        map_y = 309
        blocked = set(sandbox['blocked_symbols'])
        colors = {'#': MUTED, '~': (74, 119, 139), '^': (133, 103, 78), '.': GREEN}
        for y, row in enumerate(rows):
            for x, symbol in enumerate(row):
                glyph = '@' if (x, y) == (position['x'], position['y']) else symbol
                color = GOLD if glyph == '@' else colors.get(symbol, INK if symbol not in blocked else MUTED)
                rendered = map_font.render(glyph, True, color)
                self.screen.blit(rendered, (map_x + x * cell_width, map_y + y * map_font.get_linesize()))

        self.text(sandbox['text']['coordinates'].format(x=position['x'], y=position['y']), 310, 576, GREEN, self.small)
        for index, legend in enumerate(sandbox['legend']):
            column, row = divmod(index, 2)
            self.text(legend, 310 + column * 190, 598 + row * 18, MUTED, self.tiny)

        direction_buttons = (
            (pygame.Rect(790, 360, 48, 36), '↑', 'up'),
            (pygame.Rect(790, 402, 48, 36), '↓', 'down'),
            (pygame.Rect(738, 402, 48, 36), '←', 'left'),
            (pygame.Rect(842, 402, 48, 36), '→', 'right'),
        )
        self.text('MOVE', 792, 333, MUTED, self.tiny)
        for rect, label, direction in direction_buttons:
            self.button(rect, label, ('sandbox_move', direction))
        self.wrapped('Use the arrow keys or click a direction.', pygame.Rect(722, 452, 190, 45), MUTED, self.tiny, 2)
        if self.message:
            self.wrapped(self.message, pygame.Rect(310, 650, 590, 24), CORAL, self.tiny, 1)
        self.draw_quit_prompt()

    def draw_combat(self):
        battle = self.game['battle']
        self.wrapped(self.texts['combat_intro'], pygame.Rect(292, 272, 610, 38), MUTED, self.small, 2)
        living_party = [i for i, person in enumerate(self.game['party']) if person['health'] > 0]
        plans = battle.setdefault('plans', {})
        actor_index = battle.get('planning_actor')
        if actor_index not in living_party or str(actor_index) in plans:
            actor_index = next((index for index in living_party if str(index) not in plans), None)
            battle['planning_actor'] = actor_index
        current = self.game['party'][actor_index] if actor_index is not None else None
        if battle.get('targeting'):
            prompt = 'Choose a foe' if battle['targeting']['target_type'] == 'foe' else 'Choose an ally'
            self.text(f"{prompt} for {current['Name'] if current else 'the party'}’s move.", 292, 319, GREEN, self.body)
        elif current:
            self.text(f"Planning: {current['Name']}  ·  one move", 292, 319, GREEN, self.body)
        else:
            self.text('Every living party member has chosen a move.', 292, 319, GREEN, self.body)
        enemies = battle['enemies']
        enemy_start = battle.get('target_scroll', 0)
        visible_enemies = enemies[enemy_start:enemy_start + 6]
        for visible_index, enemy in enumerate(visible_enemies):
            index = enemy_start + visible_index
            column, row = visible_index % 3, visible_index // 3
            rect = pygame.Rect(292 + column * 203, 352 + row * 43, 195, 38)
            is_alive = enemy['health_now'] > 0
            self.box(rect, WHITE if is_alive else (220, 220, 210), CORAL if is_alive else LINE)
            self.text(enemy['name'][:20], rect.x + 8, rect.y + 4, INK if is_alive else MUTED, self.small)
            self.text(f"HP {max(0, enemy['health_now'])}/{enemy['health']} · DEF {enemy['defense']}", rect.x + 8, rect.y + 22, CORAL, self.tiny)
            if is_alive and (battle.get('targeting') or {}).get('target_type') == 'foe':
                self.buttons.append((rect, ('combat_target_foe', index)))
        if len(enemies) > 6:
            self.text(f"Targets {enemy_start + 1}–{min(len(enemies), enemy_start + 6)} of {len(enemies)} · scroll to view more",
                      292, 439, MUTED, self.tiny)
        if battle.get('targeting'):
            self.button(pygame.Rect(292, 474, 155, 36), 'Cancel target', 'combat_cancel_target')
        elif current:
            self.button(pygame.Rect(292, 474, 120, 36), 'Attack', 'combat_choose_attack')
            self.button(pygame.Rect(422, 474, 130, 36), 'Guard', 'combat_choose_guard')
            self.text(f"Magica {current.get('magica_now', 0)}/{current.get('max_magica', 0)}", 566, 486, MUTED, self.tiny)
        ready = bool(living_party) and all(str(index) in plans for index in living_party)
        self.button(
            pygame.Rect(687, 474, 215, 36), 'Lock & resolve party moves',
            'combat_resolve', primary=True, enabled=ready and battle.get('phase') == 'planning' and not battle.get('targeting'),
        )
        spell_items = [
            self.item_by_id('spells', spell_id)
            for spell_id in (current.get('known_spells', []) if current else [])
        ]
        spell_items = [spell for spell in spell_items if spell]
        for index, spell in enumerate(spell_items[:6]):
            column, row = index % 3, index // 3
            rect = pygame.Rect(292 + column * 201, 511 + row * 34, 190, 29)
            self.button(
                rect, f"{spell['name']} · {spell['cost']} M",
                ('combat_choose_spell', spell['id']),
                enabled=bool(current and current.get('magica_now', 0) >= spell['cost'] and not battle.get('targeting')),
            )
        if not spell_items:
            self.text('No known spells. Choose Inventory to learn spells.', 292, 530, MUTED, self.tiny)
        if len(spell_items) > 6:
            self.text(f'{len(spell_items) - 6} more spells available in Inventory.', 292, 599, MUTED, self.tiny)

    def draw_event(self):
        event = self.game['event']
        choices = event['choices']
        rect = pygame.Rect(292, 277, 610, 100 + 58 * len(choices))
        self.box(rect, WHITE)
        self.text(event['title'], rect.x + 20, rect.y + 20, INK, self.font)
        self.wrapped(event['description'], pygame.Rect(rect.x + 20, rect.y + 56, 565, 44), MUTED, self.body, 2)
        for index, choice in enumerate(choices):
            karma = choice['reputation']
            details = f"Supply {choice['supply']:+d} · Wealth {choice['wealth']:+d} · Reputation {karma:+d}"
            self.button(pygame.Rect(rect.x + 20, rect.y + 106 + index * 58, 565, 48), choice['label'], ('event_choice', index), subtitle=details)

    def draw_journey_actions(self):
        travel_cost = self.journey['supply_per_travel']
        camp_cost = self.journey['supply_per_camp']
        remaining = self.game.get('travel_remaining')
        if remaining is None:
            self.wrapped(self.texts['journey_intro'], pygame.Rect(292, 277, 590, 54), MUTED, self.body)
            self.button(
                pygame.Rect(292, 352, 280, 52), 'Choose a destination',
                'depart', primary=True, enabled=self.game['supply'] >= travel_cost,
            )
            return
        destination = self.game.get('travel_destination') or {}
        self.wrapped(
            f"Travel toward {destination.get('name', 'the next stop')}. "
            f"{remaining} travel day(s) remain; each costs {travel_cost} Supply.",
            pygame.Rect(292, 277, 590, 54), MUTED, self.body,
        )
        self.button(
            pygame.Rect(292, 352, 280, 52), self.texts['travel_button'], 'travel',
            primary=True, enabled=self.game['supply'] >= travel_cost,
            subtitle=f'{remaining} DAYS LEFT · COSTS {travel_cost} SUPPLY',
        )
        recovery = self.game.get('camp_recovery', 'health')
        needs_recovery = {
            'health': lambda member: member['health'] < member['max_health'],
            'magica': lambda member: member['magica_now'] < member['max_magica'],
            'stamina': lambda member: member['stamina_now'] < member['max_stamina'],
        }
        can_rest = self.game['supply'] >= camp_cost and (
            any(needs_recovery.get(recovery, needs_recovery['health'])(member) for member in self.game['party'])
            or any(
                member.get('armor_ap_now', 0) < member.get('armor_ap_max', 0)
                for member in self.game['party']
            )
        )
        recovery_labels = (('health', 'Recover Health'), ('magica', 'Recover Magica'), ('stamina', 'Recover Stamina'))
        self.text('Choose one recovery during camp:', 292, 417, MUTED, self.tiny)
        for index, (key, label) in enumerate(recovery_labels):
            self.button(
                pygame.Rect(292 + index * 192, 435, 180, 34), label,
                ('camp_recovery', key), primary=recovery == key,
            )
        heal_detail = f'HEAL {self.journey["camp_heal_per_member"]}' if recovery == 'health' else 'RECOVER BY DICE'
        self.button(pygame.Rect(592, 352, 280, 52), self.texts['camp_button'], 'rest', enabled=can_rest, subtitle=f'COSTS {camp_cost} SUPPLY · {heal_detail}')
        if self.game['supply'] < travel_cost and self.game['supply'] < camp_cost:
            self.text(self.texts['supply_shortage'], 292, 479, CORAL, self.small)

    def draw_settlement_actions(self):
        game = self.game
        location = game['location']
        is_town = location['type'] == 'town'
        level = location.get('level', 1)
        allowed = not is_town or level + game['reputation'] > 0
        can_resupply = not is_town or game['reputation'] > -3
        rate = max(1, self.journey['supply_per_wealth_base'] + game['reputation'])
        self.wrapped(
            f"{'Town' if is_town else 'Waystation'}: replenish provisions or depart when ready. "
            + (f"Level {level}; equipment trade access is {('open' if allowed else 'refused')}. "
               f"Resupply is {('available' if can_resupply else 'refused')} at your Reputation."
               if is_town else 'Waystations resupply travelers regardless of reputation.'),
            pygame.Rect(292, 277, 590, 66), MUTED, self.body,
        )
        wealth_cost = 1
        self.button(
            pygame.Rect(292, 360, 280, 48),
            f"Buy {rate} Supply",
            'settlement_supply', primary=True,
            enabled=can_resupply and game['wealth'] >= wealth_cost,
            subtitle='COSTS 1 WEALTH',
        )
        if is_town:
            self.button(
                pygame.Rect(592, 360, 280, 48), 'Browse town equipment',
                'town_inventory',
                subtitle='WEAPONS · ARMOR · GEAR',
            )
        self.button(
            pygame.Rect(292, 426, 280, 48), 'Depart for next stop',
            'depart', primary=not is_town,
            subtitle='TRAVEL COSTS SUPPLY PER DAY',
        )
        if is_town:
            upkeep = self.journey['town_upkeep_wealth_per_turn']
            self.button(
                pygame.Rect(592, 426, 280, 48), 'Rest in town',
                'town_rest', enabled=game['wealth'] >= upkeep,
                subtitle=f'COSTS {upkeep} WEALTH UPKEEP',
            )
        self.text(
            f"Supply exchange: 1 Wealth → {rate} Supply  ·  Wealth {game['wealth']}  ·  Supply {game['supply']}",
            292, 500, GREEN if can_resupply else CORAL, self.small,
        )
        if is_town and (not allowed or not can_resupply):
            self.wrapped(
                f"Your reputation ({game['reputation']:+d}) is too low for "
                f"{'town trade' if not allowed else 'resupply here'}. "
                "Waystations do not refuse resupply.",
                pygame.Rect(292, 524, 590, 32), CORAL, self.tiny, 1,
            )

    def draw_ending(self):
        rect = pygame.Rect(292, 282, 610, 152)
        self.box(rect, (226, 227, 215), (200, 203, 190))
        if self.game['mode'] == 'won':
            title = self.texts['win_title']
            summary = self.texts['win_summary']
        else:
            title = self.texts['loss_title']
            summary = self.texts['loss_summary']
        self.text(title, rect.x + 18, rect.y + 23, INK, self.font)
        self.wrapped(summary, pygame.Rect(rect.x + 18, rect.y + 60, 570, 38), MUTED, self.body)
        self.text(f"Final reputation: {self.game['reputation']:+d}   ·   Wealth: {self.game['wealth']}", rect.x + 18, rect.y + 110, GREEN, self.small)
        self.button(pygame.Rect(292, 456, 245, 46), 'Form another party', 'new', primary=True)

    def draw_journal(self):
        self.text(self.texts['journal_heading'], 292, 579, MUTED, self.tiny)
        pygame.draw.line(self.screen, LINE, (292, 596), (902, 596), 1)
        for index, entry in enumerate(self.game['log'][:3]):
            y = 606 + index * 20
            pygame.draw.rect(self.screen, GOLD, (292, y + 2, 2, 11))
            self.wrapped(entry, pygame.Rect(303, y, 590, 18), MUTED, self.tiny, 0)

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
        party_initiatives = []
        for member in self.alive_party():
            rolls = [random.randint(1, 20)]
            if self.is_encumbered(member):
                rolls.append(random.randint(1, 20))
            party_initiatives.append(min(rolls) + modifier(member, 'AGI'))
        party_initiative = max(party_initiatives)
        enemy_initiative = max(
            random.randint(1, 20) + int(enemy.get('agility', 0))
            for enemy in battle['enemies']
        )
        battle['party_initiative'] = party_initiative
        battle['enemy_initiative'] = enemy_initiative
        self.game['battle'] = battle
        self.game['mode'] = 'combat'
        if enemy_initiative > party_initiative:
            self.game['log'].insert(0, 'The creatures seize the initiative.')
            self.enemy_turn()

    def save_new_character(self):
        creator = self.creator
        name = creator['name'].strip()
        race = creator['race'].strip() or 'Human'
        try:
            level = int(creator['level'])
        except (TypeError, ValueError):
            self.message = 'Level must be a whole number from 1 to 100.'
            return
        if not name:
            self.message = 'Enter a character name.'
            return
        if not 1 <= level <= 100:
            self.message = 'Level must be a whole number from 1 to 100.'
            return
        if race not in self.races or creator['sex'] not in SEX_OPTIONS:
            self.message = 'Choose a listed race and sex.'
            return
        stats = dict(creator['stats'])
        traits = dict(creator['traits'])
        point_limit = character_point_limit(level, race)
        character_value = sum(map(int, stats.values())) + sum(map(int, traits.values()))
        if character_value > point_limit:
            self.message = f'Character uses {character_value} points; level {level} allows {point_limit}.'
            return
        physical = sorted((int(stats['STR']), int(stats['AGI']), int(stats['CON'])))
        derived = {
            'Health': int(stats['CON']) + max(int(stats['STR']), int(stats['WIL'])),
            'Stamina': physical[-1] + physical[1],
            'Magica': int(stats['WIL']) + max(int(stats['CHA']), int(stats['WIS'])),
        }
        new_character = {'Race': race, 'Stats': stats, 'Traits': traits}
        derived['Max Spells'] = spell_capacity(new_character)
        character = {
            'Id': uuid.uuid4().hex,
            'Name': name,
            'Race': race,
            'Sex': creator['sex'],
            'Level': level,
            'Stats': stats,
            'Derived': derived,
            'Max Spells': derived['Max Spells'],
            'Traits': traits,
            'Notes': creator['notes'].strip(),
            'Meta': {
                'Customized': True,
                'Character Value': character_value,
                'Character Value Limit': point_limit,
                'Allocated Points': character_value,
            },
        }
        try:
            if CHARACTERS_FILE.exists():
                with CHARACTERS_FILE.open(encoding='utf-8') as file:
                    saved = json.load(file)
                if not isinstance(saved, list):
                    raise ValueError('Character archive must contain a list.')
            else:
                saved = []
            saved.insert(0, character)
            temporary = CHARACTERS_FILE.with_suffix('.tmp')
            with temporary.open('w', encoding='utf-8') as file:
                json.dump(saved, file, indent=2, ensure_ascii=False)
            os.replace(temporary, CHARACTERS_FILE)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            self.message = f'Could not save character: {error}'
            return
        self.characters.insert(0, character)
        if self.selected:
            self.selected = [index + 1 for index in self.selected]
        if len(self.selected) < MAX_PARTY:
            self.selected.insert(0, 0)
        self.character_offset = 0
        self.view = 'selection'
        self.creator = None
        self.dropdown = None
        self.message = f'{name} has been added to your roster.'

    def edit_creator_text(self, text):
        key = self.creator['focus']
        if not key:
            return
        current = self.creator[key]
        limit = 240 if key == 'notes' else 80
        if len(current) + len(text) <= limit:
            self.creator[key] += text

    def alive_party(self):
        return [member for member in self.game['party'] if member['health'] > 0]

    def finish_battle_if_needed(self):
        battle = self.game['battle']
        if not self.alive_party():
            self.game['mode'] = 'lost'
            self.game['battle'] = None
            self.game['log'].insert(0, 'The party falls in battle.')
        elif all(enemy['health_now'] <= 0 for enemy in battle['enemies']):
            self.game['battle'] = None
            self.game['wealth'] += self.journey['victory_wealth']
            self.game['reputation'] += self.journey['victory_reputation']
            self.game['log'].insert(0, self.texts['victory_log'].format(
                wealth=self.journey['victory_wealth'],
                reputation=self.journey['victory_reputation'],
            ))
            self.continue_after_travel_turn()

    def enemy_turn(self):
        battle = self.game['battle']
        guarded = {
            int(index) for index, plan in battle.get('plans', {}).items()
            if plan.get('kind') == 'guard'
        }
        for enemy in battle['enemies']:
            if enemy['health_now'] <= 0 or not self.alive_party():
                continue
            if enemy.get('blinded') or enemy.get('calmed'):
                self.game['log'].insert(0, f"{enemy['name']} cannot attack this round.")
                continue
            target = random.choice(self.alive_party())
            target_index = self.game['party'].index(target)
            defense_bonus = max(modifier(target, 'STR'), modifier(target, 'AGI'))
            defense_rolls = [random.randint(1, 20)]
            encumbered = self.is_encumbered(target)
            if target_index in guarded and not encumbered:
                defense_rolls.append(random.randint(1, 20))
                defense_roll = max(defense_rolls) + defense_bonus
            elif encumbered and target_index not in guarded:
                defense_rolls.append(random.randint(1, 20))
                defense_roll = min(defense_rolls) + defense_bonus
            else:
                defense_roll = defense_rolls[0] + defense_bonus
            if defense_roll >= 10 + enemy['attack']:
                self.game['log'].insert(0, f"{target['Name']} avoids {enemy['name']}'s attack.")
                continue
            damage = max(
                self.combat['minimum_damage'],
                enemy['attack'] - max(0, modifier(target, 'CON') // self.combat['constitution_reduction_divisor']),
            )
            if target_index in guarded:
                damage = max(self.combat['minimum_damage'], damage // self.combat['guard_reduction_divisor'])
            if target_index in battle.get('shielded', []):
                damage = max(self.combat['minimum_damage'], damage - 1)
            if target.get('armor_ap_now', 0) > 0:
                target['armor_ap_now'] -= 1
                self.game['log'].insert(0, f"{target['Name']}'s armor absorbs {enemy['name']}'s attack (1 AP broken).")
                continue
            temporary = min(target.get('temporary_health', 0), damage)
            target['temporary_health'] = target.get('temporary_health', 0) - temporary
            damage -= temporary
            target['health'] -= damage
            self.game['log'].insert(0, self.texts['enemy_hit_log'].format(
                monster=enemy['name'], character=target['Name'], damage=damage,
            ))
        battle['guarding'] = []
        battle['shielded'] = []
        battle['elemental_shielded'] = []
        self.finish_battle_if_needed()
        if self.game['mode'] == 'combat':
            battle['plans'] = {}
            battle['targeting'] = None
            battle['planning_actor'] = next(
                (index for index, member in enumerate(self.game['party']) if member['health'] > 0),
                None,
            )
            battle['phase'] = 'planning'
            battle['round'] = battle.get('round', 1) + 1

    @staticmethod
    def roll_dice(expression):
        try:
            count_text, sides_text = expression.lower().split('d', 1)
            count = int(count_text) if count_text else 1
            sides = int(sides_text)
        except (AttributeError, ValueError):
            return 1
        return sum(random.randint(1, sides) for _ in range(max(1, count)))

    def resolve_attack(self, actor_index, enemy_index):
        battle = self.game.get('battle')
        if not battle or not 0 <= enemy_index < len(battle['enemies']):
            return
        actor = self.game['party'][actor_index]
        enemy = battle['enemies'][enemy_index]
        if enemy['health_now'] <= 0:
            self.game['log'].insert(0, f"{enemy['name']} is no longer a valid target.")
            return
        weapon = self.item_by_id('weapons', actor.get('equipment', {}).get('weapon'))
        attack_stat = weapon.get('attack_stat', 'STR') if weapon else 'STR'
        roll = random.randint(1, 20)
        if self.is_encumbered(actor):
            roll = min(roll, random.randint(1, 20))
        damage = self.roll_dice(weapon['damage']) if weapon else (
            self.combat['attack_base_damage'] + random.randint(
                self.combat['attack_damage_min'], self.combat['attack_damage_max'],
            )
        )
        if not weapon or attack_stat == 'STR':
            damage += modifier(actor, 'STR')
        damage = max(self.combat['minimum_damage'], damage)
        if roll + modifier(actor, attack_stat) >= enemy['defense']:
            enemy['health_now'] -= damage
            self.game['log'].insert(0, self.texts['player_hit_log'].format(
                character=actor['Name'], monster=enemy['name'], damage=damage,
            ))
        else:
            self.game['log'].insert(0, self.texts['player_miss_log'].format(
                character=actor['Name'], monster=enemy['name'],
            ))

    def resolve_spell(self, spell_id, actor_index, target_index, in_combat):
        actor = self.game['party'][actor_index]
        spell = self.item_by_id('spells', spell_id)
        battle = self.game.get('battle') if in_combat else None
        if not spell or spell_id not in actor.get('known_spells', []) or actor['magica_now'] < spell['cost']:
            return False
        if spell['target'] == 'ally':
            if target_index is None or not 0 <= target_index < len(self.game['party']):
                return False
            target = self.game['party'][target_index]
            if target['health'] <= 0:
                return False
        else:
            if not battle or target_index is None or not 0 <= target_index < len(battle['enemies']):
                return False
            target = battle['enemies'][target_index]
            if target['health_now'] <= 0:
                return False

        effect = spell_id
        if effect == 'heal_wounds':
            restored = min(self.roll_dice('1d8'), target['max_health'] - target['health'])
            if restored <= 0:
                return False
            target['health'] += restored
            result = f"{actor['Name']} heals {target['Name']} for {restored} Health."
        elif effect == 'respite':
            restored = min(self.roll_dice('1d8'), target['max_stamina'] - target['stamina_now'])
            if restored <= 0:
                return False
            target['stamina_now'] += restored
            result = f"{actor['Name']} restores {restored} Stamina to {target['Name']}."
        elif effect == 'fortify_health':
            restored = self.roll_dice('1d6')
            target['temporary_health'] = target.get('temporary_health', 0) + restored
            result = f"{target['Name']} gains {restored} temporary Health."
        elif effect == 'absorb_health':
            drained = min(target['health_now'], self.roll_dice('1d6'))
            if drained <= 0:
                return False
            target['health_now'] -= drained
            restored = min(drained, actor['max_health'] - actor['health'])
            actor['health'] += restored
            result = f"{actor['Name']} drains {drained} Health from {target['name']}."
        elif effect in ('harm', 'flame', 'frost', 'lightning', 'repel_undead'):
            attack_roll = random.randint(1, 20)
            if self.is_encumbered(actor):
                attack_roll = min(attack_roll, random.randint(1, 20))
            if attack_roll + modifier(actor, 'WIL') < target['defense']:
                result = f"{actor['Name']}'s {spell['name']} misses {target['name']}."
            else:
                dice = {
                    'harm': '2d4', 'flame': '2d4', 'frost': '1d6',
                    'lightning': '1d6', 'repel_undead': '1d8',
                }[effect]
                damage = self.roll_dice(dice)
                target['health_now'] -= damage
                result = f"{spell['name']} deals {damage} damage to {target['name']}."
        elif effect in ('exhaust', 'depress'):
            pool = 'stamina_now' if effect == 'exhaust' else 'magica_now'
            maximum = max(0, target.get(pool, target.get('attack', 1) * 2))
            drained = min(maximum, self.roll_dice('2d4'))
            target[pool] = maximum - drained
            result = f"{spell['name']} drains {drained} {pool.removesuffix('_now').title()} from {target['name']}."
        elif effect == 'blind':
            target['blinded'] = True
            result = f"{target['name']} is blinded."
        elif effect == 'calm':
            target['calmed'] = True
            result = f"{target['name']} is calmed and ceases fighting."
        elif effect in ('shield', 'elemental_shield'):
            target.setdefault('effects', []).append(effect)
            if in_combat:
                battle.setdefault(effect, []).append(target_index)
            result = f"{spell['name']} protects {target['Name']}."
        elif effect == 'antidote':
            effects = target.setdefault('effects', [])
            if 'poisoned' not in effects:
                return False
            effects.remove('poisoned')
            result = f"{actor['Name']} cures poison on {target['Name']}."
        elif effect == 'rally':
            target['effects'] = [
                value for value in target.get('effects', [])
                if value not in ('fear', 'charm', 'frenzy', 'demoralize', 'calm')
            ]
            result = f"{actor['Name']} rallies {target['Name']}."
        elif effect == 'dispel_magic':
            target['effects'] = []
            result = f"{actor['Name']} dispels magic from {target['Name']}."
        else:
            return False

        actor['magica_now'] -= spell['cost']
        self.game['log'].insert(0, result)
        return True

    def cast_spell(self, spell_id, actor_index, target_index, in_combat=False):
        if self.resolve_spell(spell_id, actor_index, target_index, in_combat):
            if in_combat:
                self.finish_battle_if_needed()
            self.message = 'Spell cast.'
            self.save()
            return True
        self.message = 'That spell cannot affect the selected target or the character lacks Magica.'
        return False

    def plan_move(self, actor_index, kind, target_index=None, spell_id=None):
        battle = self.game.get('battle')
        if not battle or battle.get('phase') != 'planning' or actor_index is None:
            return
        plan = {'kind': kind}
        if target_index is not None:
            plan['target'] = target_index
        if spell_id:
            plan['spell_id'] = spell_id
        plans = battle.setdefault('plans', {})
        plans[str(actor_index)] = plan
        battle['targeting'] = None
        battle['planning_actor'] = next(
            (
                index for index, member in enumerate(self.game['party'])
                if member['health'] > 0 and str(index) not in plans
            ),
            None,
        )
        self.save()

    def resolve_party_moves(self):
        battle = self.game.get('battle')
        if not battle or battle.get('phase') != 'planning':
            return
        living = [index for index, member in enumerate(self.game['party']) if member['health'] > 0]
        if not living or not all(str(index) in battle.get('plans', {}) for index in living):
            return
        battle['phase'] = 'resolving'
        battle['targeting'] = None
        for actor_index in living:
            plan = battle['plans'][str(actor_index)]
            if plan['kind'] == 'attack':
                self.resolve_attack(actor_index, plan['target'])
            elif plan['kind'] == 'spell':
                self.resolve_spell(plan['spell_id'], actor_index, plan['target'], in_combat=True)
            if self.game['mode'] != 'combat':
                break
            self.finish_battle_if_needed()
            if self.game['mode'] != 'combat':
                break
        if self.game['mode'] == 'combat':
            self.enemy_turn()
        self.save()

    def buy_inventory_item(self):
        item = next((entry for entry in self.rules[self.inventory_category]
                     if entry['id'] == self.inventory_selected), None)
        if not item:
            return
        if self.inventory_category == 'spells':
            self.learn_inventory_spell()
            return
        location = self.game.get('location', {})
        if location.get('type') != 'town':
            self.message = 'Equipment can only be purchased in towns.'
            return
        if location.get('level', 1) + self.game.get('reputation', 0) <= 0:
            self.message = 'The town refuses to trade with the party at its current reputation.'
            return
        total_cost = item.get('cost', 0)
        if self.game['wealth'] < total_cost:
            self.message = f"Need {total_cost} Wealth for this purchase."
            return
        if self.inventory_owner is not None:
            member = self.game['party'][self.inventory_owner]
            capacity = max(1, int(member.get('Stats', {}).get('STR', 10))) * 2
            if self.inventory_slots(member.setdefault('inventory', [])) + item.get('slots', 1) > capacity:
                self.message = f"{member['Name']} cannot carry any more."
                return
            member['inventory'].append(item['id'])
        else:
            self.game.setdefault('party_inventory', []).append(item['id'])
        self.game['wealth'] -= total_cost
        self.game['day'] += 1
        self.message = f"Bought {item['name']} for {total_cost} Wealth."
        self.inventory_owned_index = None
        self.save()

    def learn_inventory_spell(self):
        if self.inventory_owner is None:
            self.message = 'Choose a character to learn a spell.'
            return
        spell = self.item_by_id('spells', self.inventory_selected)
        member = self.game['party'][self.inventory_owner]
        if not spell or spell['id'] in member.setdefault('known_spells', []):
            return
        if member.get('max_spells', 0) <= 0:
            self.message = f"{member['Name']} needs Shei ancestry or Sorcery rank 5 to learn spells."
            return
        if len(member['known_spells']) >= member['max_spells']:
            self.message = f"{member['Name']} already knows the maximum {member['max_spells']} spells."
            return
        member['known_spells'].append(spell['id'])
        self.message = f"{member['Name']} learned {spell['name']}; casting costs {spell['cost']} Magica."
        self.save()

    def transfer_inventory_item(self):
        if self.inventory_owned_index is None:
            return
        source = self.current_inventory()
        index = self.inventory_owned_index
        if index >= len(source):
            return
        item_id = source[index]
        item = self.find_item(item_id)
        if not item:
            return
        if self.inventory_owner is None:
            recipient = self.game['party'][self.inventory_recipient]
            capacity = max(1, int(recipient.get('Stats', {}).get('STR', 10))) * 2
            if self.inventory_slots(recipient.setdefault('inventory', [])) + item.get('slots', 1) > capacity:
                self.message = f"{recipient['Name']} cannot carry any more."
                return
            recipient['inventory'].append(source.pop(index))
            self.message = f"Gave {item['name']} to {recipient['Name']}."
        else:
            self.game.setdefault('party_inventory', []).append(source.pop(index))
            self.message = f"Moved {item['name']} to the party inventory."
        self.inventory_owned_index = None
        self.save()

    def equip_inventory_item(self):
        if self.inventory_owner is None or self.inventory_owned_index is None:
            return
        owned = self.current_inventory()
        if self.inventory_owned_index >= len(owned):
            return
        item_id = owned[self.inventory_owned_index]
        member = self.game['party'][self.inventory_owner]
        equipment = member.setdefault('equipment', {'weapon': None, 'armor': None, 'helmet': None, 'shield': None})
        weapon = self.item_by_id('weapons', item_id)
        armor = self.item_by_id('armor', item_id)
        if weapon:
            equipment['weapon'] = item_id
        elif armor:
            equipment[armor['kind']] = item_id
        else:
            return
        self.refresh_armor_points(member, fill_increase=True)
        self.message = f"{self.find_item(item_id)['name']} equipped."
        self.save()

    def unequip_inventory_item(self):
        if self.inventory_owner is None or self.inventory_owned_index is None:
            return
        owned = self.current_inventory()
        if self.inventory_owned_index >= len(owned):
            return
        item_id = owned[self.inventory_owned_index]
        member = self.game['party'][self.inventory_owner]
        equipment = member.get('equipment', {})
        for slot, equipped_id in equipment.items():
            if equipped_id == item_id:
                equipment[slot] = None
                self.refresh_armor_points(member)
                self.message = f"{self.find_item(item_id)['name']} unequipped."
                self.save()
                return

    def refresh_armor_points(self, member, fill_increase=False):
        equipment = member.get('equipment', {})
        armor_points = sum(
            (self.item_by_id('armor', equipment.get(slot)) or {}).get('ap', 0)
            for slot in ('armor', 'helmet', 'shield')
        )
        old_max = member.get('armor_ap_max', 0)
        member['armor_ap_now'] = min(member.get('armor_ap_now', old_max), armor_points)
        if fill_increase and armor_points > old_max:
            member['armor_ap_now'] += armor_points - old_max
        member['armor_ap_max'] = armor_points

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
        if action == 'inventory':
            if game.get('mode') == 'town':
                self.message = 'Use Browse town equipment to shop here.'
                return
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
            if self.game['party']:
                self.inventory_recipient = (self.inventory_recipient + action[1]) % len(self.game['party'])
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
            self.message = f"Rested in town and paid {upkeep} Wealth upkeep."
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
        elif action == 'travel' and game['mode'] == 'journey' and game.get('travel_remaining') and game['supply'] >= self.journey['supply_per_travel']:
            game['supply'] -= self.journey['supply_per_travel']
            game['day'] += 1
            game['step'] += 1
            game['travel_remaining'] -= 1
            if random.random() < self.journey['combat_chance']:
                self.start_battle()
                game['log'].insert(0, self.texts['battle_start_log'])
            elif random.random() < self.journey['event_chance']:
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
            recovered = 0
            recovery = game.get('camp_recovery', 'health')
            for member in game['party']:
                if recovery == 'health':
                    amount = min(self.journey['camp_heal_per_member'], member['max_health'] - member['health'])
                    member['health'] += amount
                elif recovery == 'magica':
                    amount = min(self.roll_dice('2d4'), member['max_magica'] - member['magica_now'])
                    member['magica_now'] += amount
                else:
                    amount = min(self.roll_dice('2d6'), member['max_stamina'] - member['stamina_now'])
                    member['stamina_now'] += amount
                recovered += amount
                armor = member.get('equipment', {}).get('armor')
                base_ap = (self.item_by_id('armor', armor) or {}).get('ap', 0)
                broken = member.get('armor_ap_max', 0) - member.get('armor_ap_now', 0)
                for _ in range(max(0, broken)):
                    if random.randint(1, 6) > base_ap:
                        member['armor_ap_now'] = min(member['armor_ap_max'], member.get('armor_ap_now', 0) + 1)
            game['log'].insert(0, f"The party camps, spends {self.journey['supply_per_camp']} Supply, and recovers {recovered} {recovery.title()}.")
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
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.MOUSEWHEEL and self.game is None and self.view == 'creator' and self.dropdown == 'trait':
                    self.dropdown_offset = min(max(0, self.dropdown_offset - event.y), max(0, len(self.trait_catalog) - 7))
                elif event.type == pygame.MOUSEWHEEL and self.game is not None and self.game['mode'] == 'combat' and self.view == 'game':
                    enemies = self.game['battle'].get('enemies', [])
                    self.game['battle']['target_scroll'] = min(
                        max(0, self.game['battle'].get('target_scroll', 0) - event.y),
                        max(0, len(enemies) - 6),
                    )
                elif event.type == pygame.MOUSEWHEEL and self.game is not None and self.view == 'inventory':
                    if pygame.mouse.get_pos()[0] >= 444:
                        if self.inventory_category == 'spells' and self.inventory_owner is not None:
                            owned_count = len(self.game['party'][self.inventory_owner].get('known_spells', []))
                            self.inventory_owned_scroll = min(max(0, self.inventory_owned_scroll - event.y), max(0, owned_count - 5))
                        else:
                            owned_count = len(self.current_inventory())
                            self.inventory_owned_scroll = min(max(0, self.inventory_owned_scroll - event.y), max(0, owned_count - 6))
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
                    for rect, action in reversed(self.buttons):
                        if rect.collidepoint(event.pos):
                            self.handle_action(action)
                            break
            if self.game is None and self.view == 'creator':
                self.draw_creator()
            elif self.game is None:
                self.draw_selection()
            else:
                self.draw_game()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()


if __name__ == '__main__':
    Hiraeth().run()
