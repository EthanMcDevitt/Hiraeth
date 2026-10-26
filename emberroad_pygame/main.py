import json
import random
from pathlib import Path

import pygame


ROOT = Path(__file__).resolve().parent
CHARACTERS_FILE = ROOT.parent / 'characters.json'
SAVE_FILE = ROOT / 'journey.json'
WIDTH, HEIGHT = 1000, 720
ROAD_LENGTH = 6

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

ENCOUNTERS = [
    {
        'title': 'The flooded crossing',
        'description': 'A swollen river has swallowed the ford. The current is swift, and the old bridge is gone.',
        'choices': [
            {
                'label': 'Scout for a safer crossing',
                'stat': 'WIS',
                'dc': 11,
                'success': 'You find a shallow passage and guide the party across.',
                'failure': 'The crossing turns treacherous. You reach the far bank bruised.',
                'damage': 3,
            },
            {
                'label': 'Wade through together',
                'stat': 'CON',
                'dc': 10,
                'success': 'You keep the party together and make it across.',
                'failure': 'The current knocks you down before you reach the far bank.',
                'damage': 4,
            },
        ],
    },
    {
        'title': 'A hungry forest beast',
        'description': 'A horned shadow steps between the trees, blocking the trail and eyeing your provisions.',
        'choices': [
            {
                'label': 'Stand your ground',
                'stat': 'STR',
                'dc': 12,
                'success': 'A show of strength sends the beast retreating into the woods.',
                'failure': 'The beast lunges before you can drive it off.',
                'damage': 5,
            },
            {
                'label': 'Calm it with a steady voice',
                'stat': 'WIL',
                'dc': 11,
                'success': 'Your calm presence settles the beast and it lets you pass.',
                'failure': 'The beast charges. You escape, but not unhurt.',
                'damage': 4,
            },
        ],
    },
    {
        'title': 'The trail disappears',
        'description': 'Fresh rockfall has buried the path. Somewhere beyond it lies the road west.',
        'choices': [
            {
                'label': 'Read the land and find a way around',
                'stat': 'WIS',
                'dc': 10,
                'success': 'You find an old hunters’ track and rejoin the road.',
                'failure': 'The detour leads through thorny scrub.',
                'damage': 2,
            },
            {
                'label': 'Climb over the rubble',
                'stat': 'AGI',
                'dc': 12,
                'success': 'You scramble over the stones without losing a step.',
                'failure': 'Loose rocks give way beneath you.',
                'damage': 4,
            },
        ],
    },
    {
        'title': 'A roadside peddler',
        'description': 'A peddler offers a few rations in exchange for a good story and a little coin.',
        'choices': [
            {
                'label': 'Win them over with a tale',
                'stat': 'CHA',
                'dc': 10,
                'success': 'The peddler is charmed and gives you 4 rations.',
                'failure': 'The peddler stays guarded. You carry on without a trade.',
                'food_success': 4,
            },
            {
                'label': 'Politely decline and keep moving',
                'stat': 'WIL',
                'dc': 8,
                'success': 'You move on without trouble.',
                'failure': 'A rough detour costs you 2 rations.',
                'food_failure': -2,
            },
        ],
    },
]


def read_characters():
    if not CHARACTERS_FILE.exists():
        return [], 'No character archive found. Create a character in the workshop first.'
    try:
        with CHARACTERS_FILE.open(encoding='utf-8') as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        return [], f'Could not read the character archive: {error}'
    if not isinstance(data, list):
        return [], 'The character archive must contain a list.'
    usable = [
        character for character in data
        if isinstance(character, dict)
        and character.get('Id')
        and character.get('Name')
        and isinstance(character.get('Stats'), dict)
        and isinstance(character.get('Derived'), dict)
    ]
    if not usable:
        return [], 'No usable characters found. Create a character in the workshop first.'
    return usable, ''


class Emberroad:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption('The Emberroad')
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('georgia', 20)
        self.body = pygame.font.SysFont('segoeui', 15)
        self.small = pygame.font.SysFont('segoeui', 11, bold=True)
        self.tiny = pygame.font.SysFont('segoeui', 9, bold=True)
        self.characters, self.archive_message = read_characters()
        self.selected = 0
        self.game = None
        self.message = ''
        self.buttons = []
        self.load_save()

    def load_save(self):
        if not SAVE_FILE.exists():
            return
        try:
            with SAVE_FILE.open(encoding='utf-8') as file:
                saved = json.load(file)
            character = saved['character']
            if not isinstance(character.get('Stats'), dict):
                raise ValueError('saved character is missing attributes')
            if saved.get('leg', -1) < 0 or saved.get('food', -1) < 0:
                raise ValueError('saved journey has invalid resources')
            self.game = saved
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            self.message = f'Saved journey could not be restored: {error}'

    def save(self):
        if self.game is None:
            if SAVE_FILE.exists():
                SAVE_FILE.unlink()
            return
        try:
            with SAVE_FILE.open('w', encoding='utf-8') as file:
                json.dump(self.game, file, indent=2, ensure_ascii=False)
            self.message = ''
        except OSError as error:
            self.message = f'Could not save the journey: {error}'

    def text(self, value, x, y, color=INK, font=None):
        rendered = (font or self.body).render(str(value), True, color)
        self.screen.blit(rendered, (x, y))
        return rendered.get_height()

    def wrapped(self, value, rect, color=MUTED, font=None, line_gap=5):
        font = font or self.body
        words = str(value).split()
        lines = []
        line = ''
        for word in words:
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
            self.text(line, rect.x, y, color, font)
            y += font.get_linesize() + line_gap
        return y

    def box(self, rect, color=WHITE, border=LINE, radius=4):
        pygame.draw.rect(self.screen, color, rect, border_radius=radius)
        if border:
            pygame.draw.rect(self.screen, border, rect, width=1, border_radius=radius)

    def illustration(self, rect, scene='road'):
        """Draw a small storybook landscape from simple, resolution-independent shapes."""
        sx = rect.width / 240
        sy = rect.height / 112

        def point(x, y):
            return rect.x + int(x * sx), rect.y + int(y * sy)

        def polygon(color, points):
            pygame.draw.polygon(self.screen, color, [point(x, y) for x, y in points])

        old_clip = self.screen.get_clip()
        self.screen.set_clip(rect)
        pygame.draw.rect(self.screen, (183, 209, 207), rect)
        pygame.draw.circle(self.screen, (242, 210, 132), point(195, 20), max(3, int(9 * min(sx, sy))))

        polygon((128, 159, 151), [(0, 57), (28, 24), (49, 48), (79, 15), (113, 55), (148, 27), (180, 57), (208, 30), (240, 59), (240, 85), (0, 85)])
        polygon((94, 132, 108), [(0, 69), (34, 42), (72, 71), (113, 43), (160, 75), (197, 47), (240, 72), (240, 95), (0, 95)])
        polygon((104, 133, 91), [(0, 75), (52, 60), (96, 78), (149, 57), (190, 79), (240, 65), (240, 112), (0, 112)])
        polygon((132, 151, 101), [(0, 87), (55, 74), (102, 89), (154, 70), (201, 91), (240, 77), (240, 112), (0, 112)])

        if scene == 'river':
            polygon((87, 163, 173), [(0, 77), (74, 74), (118, 82), (177, 73), (240, 77), (240, 104), (178, 100), (120, 106), (72, 99), (0, 103)])
            for x, y, length in ((28, 88, 20), (97, 96, 27), (168, 85, 21), (212, 94, 17)):
                pygame.draw.line(self.screen, (195, 222, 210), point(x, y), point(x + length, y), max(1, int(1 * sy)))
            for x, y in ((68, 79), (130, 80), (190, 76)):
                pygame.draw.ellipse(self.screen, (112, 111, 94), (*point(x, y), max(4, int(14 * sx)), max(3, int(7 * sy))))
        elif scene == 'beast':
            polygon((49, 57, 48), [(136, 82), (137, 68), (145, 63), (157, 64), (162, 71), (173, 70), (181, 78), (178, 84), (163, 85), (157, 95), (151, 95), (153, 84), (145, 86), (141, 96), (135, 96), (137, 84)])
            polygon((49, 57, 48), [(146, 64), (141, 53), (150, 60), (155, 53), (157, 64)])
            pygame.draw.circle(self.screen, GOLD, point(158, 70), max(1, int(1.5 * min(sx, sy))))
        elif scene == 'rockfall':
            polygon((119, 116, 101), [(109, 77), (128, 54), (148, 72), (167, 49), (187, 77), (210, 63), (240, 81), (240, 104), (104, 104)])
            for x, y, radius in ((132, 87, 8), (158, 94, 11), (184, 85, 9), (210, 96, 8)):
                pygame.draw.circle(self.screen, (142, 130, 108), point(x, y), max(3, int(radius * min(sx, sy))))
                pygame.draw.arc(self.screen, (177, 162, 130), (*point(x - radius, y - radius), int(radius * 2 * sx), int(radius * 2 * sy)), 3.2, 5.8, max(1, int(sy)))
        elif scene == 'peddler':
            polygon((167, 102, 67), [(150, 77), (178, 49), (209, 77)])
            pygame.draw.rect(self.screen, (222, 185, 116), (*point(158, 77), int(43 * sx), int(25 * sy)))
            pygame.draw.rect(self.screen, (104, 69, 49), (*point(173, 83), int(13 * sx), int(19 * sy)))
            for x in (162, 184, 197):
                pygame.draw.circle(self.screen, (209, 173, 108), point(x, 72), max(2, int(3 * min(sx, sy))))
        else:
            # A little covered wagon and two travelers make the road feel inhabited.
            polygon((174, 151, 115), [(0, 91), (63, 87), (103, 77), (150, 85), (183, 104), (240, 111), (0, 112)])
            pygame.draw.line(self.screen, (103, 72, 54), point(55, 82), point(82, 82), max(2, int(2 * sy)))
            pygame.draw.rect(self.screen, (137, 86, 58), (*point(58, 69), int(24 * sx), int(13 * sy)))
            pygame.draw.arc(self.screen, (229, 211, 172), (*point(61, 60), int(18 * sx), int(18 * sy)), 3.14, 6.28, max(1, int(2 * min(sx, sy))))
            for x in (63, 78):
                pygame.draw.circle(self.screen, (63, 58, 48), point(x, 85), max(2, int(3 * min(sx, sy))))
            for x, y in ((98, 82), (112, 78)):
                pygame.draw.circle(self.screen, (54, 62, 51), point(x, y - 8), max(2, int(3 * min(sx, sy))))
                pygame.draw.line(self.screen, (54, 62, 51), point(x, y - 5), point(x, y + 5), max(1, int(2 * min(sx, sy))))
                pygame.draw.line(self.screen, (54, 62, 51), point(x, y), point(x - 4, y + 5), max(1, int(2 * min(sx, sy))))
                pygame.draw.line(self.screen, (54, 62, 51), point(x, y), point(x + 4, y + 5), max(1, int(2 * min(sx, sy))))

        pygame.draw.rect(self.screen, (92, 97, 78), rect, width=1, border_radius=3)
        self.screen.set_clip(old_clip)

    def button(self, rect, label, action, primary=False, enabled=True, subtitle=None):
        mouse = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse)
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
        text = font.render(label, True, label_color)
        label_y = (4 if rect.height <= 38 else 11) if subtitle else (rect.height - text.get_height()) // 2
        self.screen.blit(text, (rect.x + 12, rect.y + label_y))
        if subtitle:
            sub = self.tiny.render(subtitle, True, GOLD if primary else MUTED)
            self.screen.blit(sub, (rect.x + 12, rect.y + (20 if rect.height <= 38 else 33)))
        if enabled:
            self.buttons.append((rect, action))

    def frame(self, kicker, subtitle=''):
        self.screen.fill((17, 27, 27))
        pygame.draw.rect(self.screen, (20, 32, 31), (0, 0, WIDTH, 60))
        self.text('✦  HIRAETH  /  THE EMBERROAD', 32, 21, GOLD, self.small)
        self.text('ESC  QUIT', WIDTH - 98, 23, (196, 203, 190), self.tiny)
        pygame.draw.rect(self.screen, PAPER, (25, 75, WIDTH - 50, HEIGHT - 100), border_radius=3)
        pygame.draw.rect(self.screen, (110, 116, 99), (25, 75, WIDTH - 50, HEIGHT - 100), width=1, border_radius=3)
        self.buttons = []
        self.text(kicker.upper(), 58, 101, CORAL, self.tiny)
        if subtitle:
            self.text(subtitle, 58, 122, MUTED, self.tiny)

    def draw_selection(self):
        self.frame('A fantasy wilderness journey', 'CHOOSE A TRAVELER FROM YOUR CHARACTER WORKSHOP')
        self.text('The Emberroad', 58, 160, INK, pygame.font.SysFont('georgia', 48))
        self.illustration(pygame.Rect(680, 150, 228, 112), 'road')
        self.wrapped(
            'The frontier lies six stretches west. Keep your party fed, make hard choices, and see who reaches the far side of the wilds.',
            pygame.Rect(60, 222, 560, 45),
            MUTED,
            self.body,
        )
        if not self.characters:
            self.box(pygame.Rect(58, 300, 840, 112), (242, 238, 223), (213, 197, 165))
            self.wrapped(self.archive_message, pygame.Rect(78, 320, 790, 50), CORAL)
            self.text('Run the Character Workshop and create a character, then reopen this game.', 78, 365, MUTED, self.small)
            self.text('Archive path: ' + str(CHARACTERS_FILE), 58, 442, MUTED, self.tiny)
            return

        self.text('YOUR TRAVELERS', 60, 293, MUTED, self.tiny)
        card_height = 74
        visible = min(len(self.characters), 4)
        for index, character in enumerate(self.characters[:visible]):
            y = 316 + index * (card_height + 8)
            selected = index == self.selected
            rect = pygame.Rect(58, y, 565, card_height)
            self.box(rect, (246, 244, 232) if selected else (226, 227, 215), GOLD if selected else LINE)
            self.buttons.append((rect, ('select', index)))
            self.text(character.get('Name', 'Traveler'), rect.x + 16, rect.y + 13, INK, self.font)
            self.text(f"{character.get('Race', 'Unknown')}   ·   LEVEL {character.get('Level', 1)}", rect.x + 16, rect.y + 45, MUTED, self.tiny)
            stats = character.get('Stats', {})
            stat_line = '   '.join(f'{key} {stats.get(key, "—")}' for key in STATS)
            width = self.body.size(stat_line)[0]
            self.text(stat_line, rect.right - width - 14, rect.y + 29, GREEN, self.tiny)

        if len(self.characters) > visible:
            self.text(f'Showing first {visible} of {len(self.characters)} characters.', 58, 646, MUTED, self.tiny)
        start_y = min(316 + visible * (card_height + 8) + 15, 616)
        self.button(pygame.Rect(665, start_y, 245, 52), 'Begin the journey', 'start', primary=True)
        self.text('Starting provisions', 665, start_y + 83, MUTED, self.tiny)
        self.text('18 rations', 665, start_y + 101, INK, self.font)
        self.wrapped('Travel costs 3 rations. Foraging and resting take a day.', pygame.Rect(665, start_y + 137, 225, 60), MUTED, self.small)
        if self.message:
            self.wrapped(self.message, pygame.Rect(58, 614, 850, 35), CORAL, self.tiny, 2)

    def draw_game(self):
        game = self.game
        character = game['character']
        leg = game['leg']
        ended = game['ended']
        title = 'A new horizon.' if ended and game['won'] else 'The road goes quiet.' if ended else f'Leg {min(leg + 1, ROAD_LENGTH)} of {ROAD_LENGTH}'
        self.frame(f"THE EMBERROAD  /  DAY {game['day']}", f"TRAVELING AS {character['Name']} THE {character.get('Race', 'TRAVELER')}")
        self.text(title, 58, 159, INK, pygame.font.SysFont('georgia', 38))
        self.illustration(pygame.Rect(720, 145, 188, 78), self.current_scene())
        progress_rect = pygame.Rect(58, 216, 850, 5)
        pygame.draw.rect(self.screen, LINE, progress_rect)
        progress = min(1, leg / ROAD_LENGTH)
        pygame.draw.rect(self.screen, GREEN, (progress_rect.x, progress_rect.y, int(progress_rect.width * progress), progress_rect.height))

        resource_x = [58, 348, 638]
        resource_data = [
            ('FOOD', str(game['food']), 'rations'),
            ('HEALTH', f"{game['health']} / {game['max_health']}", 'vitality'),
            ('JOURNEY', f'{leg} / {ROAD_LENGTH}', 'stretches crossed'),
        ]
        for x, (label, value, detail) in zip(resource_x, resource_data):
            rect = pygame.Rect(x, 236, 270, 76)
            self.box(rect, PANEL)
            pygame.draw.rect(self.screen, CORAL, (rect.x, rect.y, rect.width, 2))
            self.text(label, rect.x + 14, rect.y + 12, MUTED, self.tiny)
            self.text(value, rect.x + 14, rect.y + 29, DARK_GREEN, pygame.font.SysFont('georgia', 25))
            self.text(detail, rect.right - self.small.size(detail)[0] - 13, rect.y + 50, MUTED, self.tiny)

        pending = game.get('pending')
        if pending and not ended:
            self.draw_encounter(pending)
        elif ended:
            self.draw_ending()
        else:
            self.draw_actions()
        self.draw_journal()
        if self.message:
            self.text(self.message, 58, 674, CORAL, self.tiny)

    def draw_encounter(self, encounter):
        rect = pygame.Rect(58, 332, 850, 198)
        self.box(rect, WHITE, (185, 196, 183))
        scene = self.current_scene(encounter)
        self.illustration(pygame.Rect(rect.x + 14, rect.y + 14, 218, 132), scene)
        self.text('ON THE ROAD', rect.x + 248, rect.y + 15, CORAL, self.tiny)
        self.text(encounter['title'], rect.x + 248, rect.y + 36, INK, self.font)
        self.wrapped(encounter['description'], pygame.Rect(rect.x + 248, rect.y + 67, 575, 45), MUTED, self.small, 3)
        choices = encounter['choices']
        for index, choice in enumerate(choices):
            button_rect = pygame.Rect(rect.x + 248, rect.y + 117 + index * 38, 575, 36)
            modifier = (int(self.game['character']['Stats'].get(choice['stat'], 10)) - 10) // 2
            check = f"{STATS[choice['stat']]}  ·  d20 + {modifier:+d}  ·  DC {choice['dc']}"
            self.button(button_rect, choice['label'], ('choice', index), subtitle=check)

    def current_scene(self, encounter=None):
        title = (encounter or self.game.get('pending') or {}).get('title', '').lower()
        if 'flood' in title or 'river' in title:
            return 'river'
        if 'beast' in title:
            return 'beast'
        if 'trail' in title or 'rock' in title:
            return 'rockfall'
        if 'peddler' in title:
            return 'peddler'
        return 'road'

    def draw_actions(self):
        self.text('Make camp or move on', 58, 342, INK, self.font)
        self.text('Travel costs 3 food and reveals a new challenge. Forage or rest before setting out.', 58, 373, MUTED, self.small)
        self.button(pygame.Rect(58, 411, 270, 52), 'Travel onward', 'travel', primary=True, enabled=self.game['food'] >= 3)
        self.button(pygame.Rect(348, 411, 270, 52), 'Forage', 'forage', subtitle='WISDOM CHECK  ·  TAKES A DAY')
        can_rest = self.game['food'] >= 2 and self.game['health'] < self.game['max_health']
        self.button(pygame.Rect(638, 411, 270, 52), 'Rest', 'rest', enabled=can_rest, subtitle='2 RATIONS  ·  RECOVER UP TO 5 HEALTH')
        if self.game['food'] < 3:
            self.text('Not enough food to travel. Forage before moving on.', 58, 478, CORAL, self.small)

    def draw_ending(self):
        rect = pygame.Rect(58, 340, 850, 105)
        self.box(rect, (226, 227, 215), (200, 203, 190))
        if self.game['won']:
            title = 'The journey ends in triumph'
            description = 'The road was long, but your party made it through.'
        else:
            title = 'The journey ends here'
            description = 'The wilderness claimed the last of your strength.'
        self.text(title, rect.x + 18, rect.y + 18, INK, self.font)
        self.text(description, rect.x + 18, rect.y + 54, MUTED, self.small)
        self.button(pygame.Rect(58, 461, 245, 48), 'Start another journey', 'new', primary=True)

    def draw_journal(self):
        self.text('ROAD JOURNAL', 58, 548, MUTED, self.tiny)
        pygame.draw.line(self.screen, LINE, (58, 565), (908, 565), 1)
        for index, entry in enumerate(self.game['log'][:4]):
            y = 578 + index * 22
            pygame.draw.rect(self.screen, GOLD, (58, y + 2, 2, 12))
            self.wrapped(entry, pygame.Rect(70, y, 825, 18), MUTED, self.tiny, 0)

    def begin_journey(self):
        if not self.characters:
            return
        character = self.characters[self.selected]
        try:
            max_health = max(1, int(character['Derived']['Health']))
        except (KeyError, TypeError, ValueError):
            self.message = f"{character.get('Name', 'Traveler')} has no valid Health value."
            return
        self.game = {
            'character': character,
            'day': 1,
            'leg': 0,
            'food': 18,
            'health': max_health,
            'max_health': max_health,
            'log': [f"{character['Name']} sets out toward the western frontier with 18 rations."],
            'pending': None,
            'ended': False,
            'won': False,
        }
        self.message = ''
        self.save()

    def end_if_needed(self):
        if self.game['health'] <= 0:
            self.game['health'] = 0
            self.game['ended'] = True
            self.game['won'] = False
        elif self.game['leg'] >= ROAD_LENGTH:
            self.game['ended'] = True
            self.game['won'] = True

    def resolve_choice(self, index):
        game = self.game
        choice = game['pending']['choices'][index]
        stat = int(game['character']['Stats'].get(choice['stat'], 10))
        modifier = (stat - 10) // 2
        roll = random.randint(1, 20)
        success = roll + modifier >= choice['dc']
        if not success:
            game['health'] -= choice.get('damage', 0)
        game['food'] = max(0, game['food'] + choice.get('food_success' if success else 'food_failure', 0))
        game['leg'] += 1
        game['pending'] = None
        result = choice['success'] if success else choice['failure']
        game['log'].insert(0, f"{'Success' if success else 'Setback'} ({roll} {modifier:+d}): {result}")
        self.end_if_needed()
        self.save()

    def handle_action(self, action):
        if isinstance(action, tuple) and action[0] == 'select':
            self.selected = action[1]
        elif action == 'start':
            self.begin_journey()
        elif action == 'new':
            self.game = None
            self.save()
        elif action == 'travel' and self.game['food'] >= 3:
            self.game['food'] -= 3
            self.game['day'] += 1
            self.game['log'].insert(0, 'The party spends 3 rations and presses on.')
            self.game['pending'] = random.choice(ENCOUNTERS)
            self.save()
        elif isinstance(action, tuple) and action[0] == 'choice':
            self.resolve_choice(action[1])
        elif action == 'forage':
            game = self.game
            game['day'] += 1
            wisdom = int(game['character']['Stats'].get('WIS', 10))
            modifier = (wisdom - 10) // 2
            roll = random.randint(1, 20)
            success = roll + modifier >= 10
            found = random.randint(4, 6) if success else 1
            game['food'] += found
            if not success:
                game['health'] -= 1
            summary = f'you find {found} rations.' if success else 'you find 1 ration and take 1 damage.'
            game['log'].insert(0, f"{'Foraging succeeds' if success else 'Foraging yields little'} ({roll} {modifier:+d}): {summary}")
            self.end_if_needed()
            self.save()
        elif action == 'rest' and self.game['food'] >= 2 and self.game['health'] < self.game['max_health']:
            game = self.game
            game['day'] += 1
            game['food'] -= 2
            recovered = min(5, game['max_health'] - game['health'])
            game['health'] += recovered
            game['log'].insert(0, f'The party rests, spends 2 rations, and recovers {recovered} health.')
            self.save()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, action in reversed(self.buttons):
                        if rect.collidepoint(event.pos):
                            self.handle_action(action)
                            break
            if self.game is None:
                self.draw_selection()
            else:
                self.draw_game()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()


if __name__ == '__main__':
    Emberroad().run()
