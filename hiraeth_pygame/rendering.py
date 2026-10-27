if __package__:
    from .shared import (
        CORAL,
        DARK_GREEN,
        DOWNTIME_LABELS,
        GOLD,
        GREEN,
        HEIGHT,
        INK,
        LINE,
        MAX_PARTY,
        MUTED,
        PANEL,
        PAPER,
        SEX_OPTIONS,
        STATS,
        WHITE,
        WIDTH,
        character_point_limit,
        pygame,
    )
else:
    from shared import (
        CORAL,
        DARK_GREEN,
        DOWNTIME_LABELS,
        GOLD,
        GREEN,
        HEIGHT,
        INK,
        LINE,
        MAX_PARTY,
        MUTED,
        PANEL,
        PAPER,
        SEX_OPTIONS,
        STATS,
        WHITE,
        WIDTH,
        character_point_limit,
        pygame,
    )


class RenderingMixin:

    def text(self, value, x, y, color=INK, font=None):
        rendered = (font or self.body).render(str(value), True, color)
        self.screen.blit(rendered, (x, y))
        return rendered.get_height()

    def wrapped(self, value, rect, color=MUTED, font=None, line_gap=5):
        font = font or self.body
        lines = self.wrap_lines(value, rect.width, font)
        y = rect.y
        for line in lines:
            if y + font.get_linesize() > rect.bottom:
                break
            self.text(line, rect.x, y, color, font)
            y += font.get_linesize() + line_gap
        return y

    @staticmethod
    def wrap_lines(value, width, font):
        lines = []
        line = ''
        for word in str(value).split():
            candidate = f'{line} {word}'.strip()
            if line and font.size(candidate)[0] > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        return lines

    def journal_lines(self):
        return [
            line
            for entry in self.game['log']
            for line in self.wrap_lines(entry, 586, self.tiny)
        ]

    def box(self, rect, color=WHITE, border=LINE, radius=4):
        pygame.draw.rect(self.screen, color, rect, border_radius=radius)
        if border:
            pygame.draw.rect(self.screen, border, rect, width=1, border_radius=radius)

    def button(self, rect, label, action, primary=False, enabled=True, subtitle=None):
        hovered = enabled and rect.collidepoint(self.mouse_position())
        if hovered:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
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
        font = self.tiny if rect.height <= 22 else self.small if subtitle else self.body
        rendered = font.render(label, True, label_color)
        label_y = 4 if subtitle else (rect.height - rendered.get_height()) // 2
        self.screen.blit(rendered, (rect.x + 12, rect.y + label_y))
        if subtitle:
            self.text(subtitle, rect.x + 12, rect.y + 21, GOLD if primary else MUTED, self.tiny)
        if enabled:
            self.buttons.append((rect, action))

    def frame(self, kicker, subtitle=''):
        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
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
            self.button(
                pygame.Rect(660, 14, 112, 32), 'Inventory', 'inventory',
                primary=self.view == 'inventory',
            )
            self.button(pygame.Rect(790, 14, 112, 32), 'Quit to menu', 'quit_prompt')

    def logical_size(self):
        display_width, display_height = self.display.get_size()
        scale = min(display_width / WIDTH, display_height / HEIGHT)
        width, height = round(WIDTH * scale), round(HEIGHT * scale)
        return scale, pygame.Rect(
            (display_width - width) // 2,
            (display_height - height) // 2,
            width,
            height,
        )

    def mouse_position(self, position=None):
        scale, viewport = self.logical_size()
        x, y = pygame.mouse.get_pos() if position is None else position
        if scale <= 0:
            return -1, -1
        return round((x - viewport.x) / scale), round((y - viewport.y) / scale)

    def present(self):
        _, viewport = self.logical_size()
        self.display.fill((17, 27, 27))
        scaled = pygame.transform.smoothscale(self.screen, viewport.size)
        self.display.blit(scaled, viewport.topleft)

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
            hovered = rect.collidepoint(self.mouse_position())
            self.box(
                rect,
                (246, 244, 232) if selected or hovered else PANEL,
                GOLD if selected or hovered else LINE,
            )
            self.text(item['name'], rect.x + 9, rect.y + 5, INK, self.small)
            cost_label = f"Cast {item['cost']} Magica" if self.inventory_category == 'spells' else f"Wealth {item.get('cost', 0)}"
            self.text(cost_label, rect.x + 9, rect.y + 22, MUTED, self.tiny)
            if hovered:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
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
            owned = self.game.setdefault('party_inventory', [])
            self.text('Party stash', 462, 281, GREEN, self.small)
            self.text(f'{len(owned)} shared items', 462, 301, MUTED, self.tiny)
        else:
            member = self.game['party'][self.inventory_owner]
            owned = member.setdefault('inventory', [])
            capacity = max(1, int(member.get('Stats', {}).get('STR', 10)))
            slots = self.inventory_slots(owned)
            self.text(
                f"{member['Name']}  ·  carried {slots}/{capacity} slots",
                462, 281, GREEN, self.small,
            )
            equipment = member.setdefault(
                'equipment',
                {'weapon': None, 'armor': None, 'helmet': None, 'shield': None},
            )
            equipment_slots = (
                ('weapon', '1 · WEAPON'),
                ('armor', '2 · ARMOR'),
                ('helmet', '3 · HELMET'),
                ('shield', '4 · SHIELD'),
            )
            for slot_index, (slot, label) in enumerate(equipment_slots):
                column, row = slot_index % 2, slot_index // 2
                rect = pygame.Rect(462 + column * 215, 307 + row * 32, 207, 27)
                self.box(rect, PANEL, LINE)
                item_name = self.item_name(
                    'weapons' if slot == 'weapon' else 'armor',
                    equipment.get(slot),
                ) or 'Empty'
                self.text(f'{label}  ·  {item_name[:16]}', rect.x + 7, rect.y + 6, INK, self.tiny)

        transfer_choices = self.transfer_choices()
        target_index = None
        target_label = 'Party stash'
        if transfer_choices:
            target_index = transfer_choices[self.inventory_recipient % len(transfer_choices)]
            target_label = (
                'Party stash' if target_index is None
                else self.game['party'][target_index]['Name']
            )
            action_label = 'Send to' if self.inventory_owner is None else 'Move to'
            self.button(
                pygame.Rect(462, 376, 224, 27),
                f'{action_label} {target_label[:12]}  ›',
                ('inventory_recipient', 1),
            )
            if self.inventory_owner is not None:
                self.text(
                    f'{slots}/{capacity} carry slots used',
                    700, 383, MUTED, self.tiny,
                )

        if self.inventory_category == 'spells' and self.inventory_owner is not None:
            member = self.game['party'][self.inventory_owner]
            known_ids = member.setdefault('known_spells', [])
            known = [
                spell for spell in (
                    self.item_by_id('spells', spell_id) for spell_id in known_ids
                ) if spell
            ]
            self.text(
                f"KNOWN SPELLS  ·  {len(known)}/{member.get('max_spells', 0)}",
                462, 410, MUTED, self.tiny,
            )
            visible_owned = known[self.inventory_owned_scroll:self.inventory_owned_scroll + 5]
            for row_index, spell in enumerate(visible_owned):
                rect = pygame.Rect(458, 424 + row_index * 22, 435, 20)
                self.box(rect, PANEL, LINE)
                self.text(
                    f"{spell['name']}  ·  {spell['school']}  ·  {spell['cost']} Magica",
                    rect.x + 8, rect.y + 4, INK, self.tiny,
                )
        else:
            self.text('ITEMS IN THIS INVENTORY', 462, 410, MUTED, self.tiny)
            visible_owned = owned[self.inventory_owned_scroll:self.inventory_owned_scroll + 5]
            for row_index, item_id in enumerate(visible_owned):
                item = self.find_item(item_id)
                label = item['name'] if item else item_id
                if self.inventory_owner is not None:
                    equipped = item_id in member.get('equipment', {}).values()
                    label += '  · equipped' if equipped else ''
                rect = pygame.Rect(458, 424 + row_index * 22, 435, 20)
                hovered = rect.collidepoint(self.mouse_position())
                selected_owned = self.inventory_owned_index == row_index + self.inventory_owned_scroll
                self.box(
                    rect,
                    (246, 244, 232) if selected_owned or hovered else PANEL,
                    GOLD if selected_owned or hovered else LINE,
                )
                self.text(label, rect.x + 8, rect.y + 4, INK, self.tiny)
                if hovered:
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                self.buttons.append((rect, ('inventory_owned', row_index + self.inventory_owned_scroll)))

        selected = next((item for item in items if item['id'] == self.inventory_selected), None)
        if selected:
            detail_y = 535
            self.text(selected['name'], 462, detail_y, INK, self.body)
            if self.inventory_category == 'weapons':
                detail = f"{selected['range']} range  ·  {selected['damage']} {selected['damage_type']}  ·  {selected['traits']}"
            elif self.inventory_category == 'armor':
                detail = f"{selected['kind'].title()}  ·  {selected['ap']} AP  ·  {selected['slots']} slots  ·  {selected['traits']}"
            elif self.inventory_category == 'spells':
                detail = f"{selected['school']}  ·  {selected['cost']} Magica  ·  {selected['effect']}"
            else:
                detail = f"{selected['slots']} slots  ·  {selected['traits']}"
            self.wrapped(detail, pygame.Rect(462, detail_y + 21, 425, 25), MUTED, self.tiny, 1)

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
                    pygame.Rect(758, 584, 136, 32), f'Move to {target_label[:12]}',
                    'inventory_transfer', enabled=can_move and not equipped and bool(transfer_choices),
                )
        self.button(
            pygame.Rect(58, 646, 190, 40),
            'Back to settlement' if self.game.get('mode') in ('town', 'waystation') else 'Back to the road',
            'inventory_back', primary=True,
        )
        if self.message:
            self.wrapped(self.message, pygame.Rect(270, 650, 630, 32), CORAL, self.tiny, 1)

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
        self.text('W weapon · A armor · H helmet · S shield', 58, 160, MUTED, self.tiny)
        battle = self.game.get('battle') if self.game['mode'] == 'combat' else None
        targeting = battle.get('targeting') if battle else None
        for index, member in enumerate(self.game['party']):
            rect = pygame.Rect(58, 169 + index * 100, 215, 94)
            living = member['health'] > 0
            active = bool(battle and battle.get('planning_actor') == index and living)
            target_spell = (
                self.item_by_id('spells', targeting.get('spell_id'))
                if targeting and targeting.get('kind') == 'spell'
                else None
            )
            target_available = not (
                target_spell
                and target_spell['id'] == 'heal_wounds'
                and member['health'] >= member['max_health']
            )
            ally_target = bool(
                targeting
                and targeting.get('target_type') == 'ally'
                and living
                and target_available
            )
            clickable = ally_target or bool(
                battle and not targeting
                and battle.get('phase') == 'planning' and living
            ) or not battle
            hovered = clickable and rect.collidepoint(self.mouse_position())
            self.box(
                rect,
                (246, 244, 232) if active or hovered else (226, 227, 215),
                GOLD if active or hovered else LINE,
            )
            self.text(member['Name'], rect.x + 12, rect.y + 7, INK if living else MUTED, self.body)
            self.text(
                f"HP {max(0, member['health'])}/{member['max_health']}"
                f"  ·  MP {member.get('magica_now', 0)}/{member.get('max_magica', 0)}",
                rect.x + 12, rect.y + 27, GREEN if living else CORAL, self.tiny,
            )
            if targeting and targeting.get('target_type') == 'ally' and living:
                target_hint = (
                    'Already at full Health'
                    if not target_available
                    else f"Click to target with {target_spell['name']}"
                    if target_spell else 'Click to choose target'
                )
                self.text(target_hint[:30], rect.x + 12, rect.y + 44, GREEN, self.tiny)
                if ally_target:
                    self.buttons.append((rect, ('combat_target_party', index)))
            elif battle:
                plan = battle.get('plans', {}).get(str(index))
                status = 'Choose move' if plan is None else self.plan_description(plan, battle)
                self.text(status[:30], rect.x + 12, rect.y + 44, GOLD if plan else MUTED, self.tiny)
                if (
                    living and battle.get('phase') == 'planning'
                    and not targeting
                ):
                    self.buttons.append((rect, ('plan_member', index)))
            else:
                self.buttons.append((rect, ('overview', index)))
            equipment = member.get('equipment', {})
            slot_values = (
                ('W', self.item_name('weapons', equipment.get('weapon'))),
                ('A', self.item_name('armor', equipment.get('armor'))),
                ('H', self.item_name('armor', equipment.get('helmet'))),
                ('S', self.item_name('armor', equipment.get('shield'))),
            )
            for slot_index, (slot_label, item_name) in enumerate(slot_values):
                slot_rect = pygame.Rect(rect.x + 8 + slot_index * 49, rect.y + 60, 46, 14)
                self.box(slot_rect, WHITE, LINE, radius=2)
                value = item_name[:4] if item_name else '—'
                self.text(
                    f'{slot_label}:{value}', slot_rect.x + 3, slot_rect.y + 2,
                    INK, self.tiny,
                )
            if hovered:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
            next_rank = 'back' if member.get('rank') == 'front' else 'front'
            rank_label = f"{member.get('rank', 'front').title()} → {next_rank.title()}"
            rank_enabled = living and (
                not battle
                or (
                    battle.get('phase') == 'planning'
                    and battle.get('planning_actor') == index
                    and str(index) not in battle.get('plans', {})
                    and not battle.get('targeting')
                )
            )
            self.button(
                pygame.Rect(rect.x + 8, rect.y + 76, 99, 16),
                rank_label, ('party_rank', index),
                enabled=rank_enabled,
            )
            activity = member.get('downtime_activity', 'health')
            self.button(
                pygame.Rect(rect.x + 112, rect.y + 76, 95, 16),
                f"Rest: {DOWNTIME_LABELS[activity]} >",
                ('cycle_downtime', index),
                enabled=living and not battle and self.game['mode'] not in ('won', 'lost'),
            )

    def plan_description(self, plan, battle):
        if plan['kind'] == 'guard':
            return 'Guard locked'
        if plan['kind'] == 'switch_rank':
            return 'Switch rank'
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
        self.draw_combat_animations()
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
            already_full = (
                spell['id'] == 'heal_wounds'
                and member['health'] >= member['max_health']
            )
            enabled = (
                member['health'] > 0
                and actor['magica_now'] >= spell['cost']
                and spell['target'] == 'ally'
                and not already_full
            )
            hovered = enabled and rect.collidepoint(self.mouse_position())
            self.box(
                rect,
                (246, 244, 232) if hovered else WHITE if enabled else PANEL,
                GOLD if hovered else GREEN if enabled else LINE,
            )
            self.text(member['Name'], rect.x + 14, rect.y + 8, INK, self.body)
            self.text(
                f"HP {member['health']}/{member['max_health']}  ·  Magica {member['magica_now']}/{member['max_magica']}",
                rect.x + 14, rect.y + 35, MUTED, self.tiny,
            )
            if member['health'] > 0 and spell['target'] == 'ally':
                hint = (
                    'FULL HEALTH'
                    if already_full else 'CLICK TO HEAL'
                    if spell['id'] == 'heal_wounds' else 'CLICK TO TARGET'
                )
                self.text(
                    hint, rect.right - 110, rect.y + 22,
                    MUTED if already_full else GREEN if hovered else MUTED, self.tiny,
                )
                if enabled:
                    if hovered:
                        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
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
            self.text(
                f"HP {max(0, enemy['health_now'])}/{enemy['health']}"
                f" · DEF {enemy['defense']} · HIT {enemy['chance_to_hit']}%"
                f" · DMG {enemy['damage']}",
                rect.x + 8, rect.y + 22, CORAL, self.tiny,
            )
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
                'depart', primary=True,
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
            primary=True,
            subtitle=(
                f'{remaining} DAYS LEFT · COSTS {travel_cost} SUPPLY'
                if self.game['supply'] >= travel_cost
                else f'{remaining} DAYS LEFT · UNSUPPLIED (STAMINA, THEN HEALTH)'
            ),
        )
        can_rest = self.game['supply'] >= camp_cost and any(
            self.can_take_downtime(member) for member in self.game['party']
        )
        self.button(
            pygame.Rect(592, 352, 280, 52), self.texts['camp_button'],
            'rest', enabled=can_rest,
            subtitle=f'COSTS {camp_cost} SUPPLY · ACTIVITIES SET ON PARTY CARDS',
        )
        self.text('Downtime activities · choose each character on their party card', 292, 418, MUTED, self.tiny)
        for index, member in enumerate(self.game['party']):
            activity = DOWNTIME_LABELS[member.get('downtime_activity', 'health')]
            self.text(
                f"{member['Name']}: {activity}",
                292, 439 + index * 25, INK if member['health'] > 0 else MUTED, self.small,
            )
        if self.game['supply'] == 0:
            self.button(
                pygame.Rect(292, 541, 280, 34), 'Forage for supplies',
                'forage', primary=True, subtitle='TAKES A DAY · WISDOM CHECKS',
            )

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
                'town_rest',
                enabled=game['wealth'] >= upkeep and any(
                    self.can_take_downtime(member) for member in game['party']
                ),
                subtitle=f'COSTS {upkeep} WEALTH UPKEEP',
            )
            repairable = [
                (index, member)
                for index, member in enumerate(game['party'])
                if (
                    self.town_repair_limit(member) is not None
                    and self.town_repair_limit(member) <= level
                    and member.get('armor_ap_total', member['armor_ap_max']) > member['armor_ap_now']
                )
            ]
            if repairable:
                self.text('Professional armor repair · 1 Wealth each · AP restored up to town level', 292, 533, MUTED, self.tiny)
                for position, (index, member) in enumerate(repairable):
                    self.button(
                        pygame.Rect(292 + position * 151, 552, 143, 38),
                        f"Repair {member['Name'][:10]}",
                        ('town_repair', index),
                        enabled=game['wealth'] >= 1,
                        subtitle=f"UP TO {level} AP · 1 WEALTH",
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
                pygame.Rect(292, 600, 590, 32), CORAL, self.tiny, 1,
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
        lines = self.journal_lines()
        max_scroll = max(0, len(lines) - 5)
        self.log_scroll = min(self.log_scroll, max_scroll)
        start = self.log_scroll
        end = min(len(lines), start + 5)
        self.text(f'{start + 1 if lines else 0}–{end} / {len(lines)}', 782, 580, MUTED, self.tiny)
        self.button(
            pygame.Rect(852, 576, 22, 19), '↑', ('log_scroll', -1),
            enabled=start > 0,
        )
        self.button(
            pygame.Rect(879, 576, 22, 19), '↓', ('log_scroll', 1),
            enabled=end < len(lines),
        )
        pygame.draw.rect(self.screen, (226, 227, 215), pygame.Rect(292, 598, 610, 76), border_radius=3)
        pygame.draw.line(self.screen, LINE, (292, 598), (902, 598), 1)
        for index, line in enumerate(lines[start:end]):
            y = 602 + index * 14
            pygame.draw.rect(self.screen, GOLD, (298, y + 2, 2, 9))
            self.text(line, 307, y, MUTED, self.tiny)

    def draw_combat_animations(self):
        if self.game.get('mode') != 'combat':
            self.attack_animations.clear()
            return
        now = pygame.time.get_ticks()
        battle = self.game.get('battle') or {}
        target_scroll = battle.get('target_scroll', 0)
        visible_enemy_count = min(6, len(battle.get('enemies', [])) - target_scroll)
        active = []
        for animation in self.attack_animations:
            if now >= animation['end_at']:
                continue
            active.append(animation)
            if now < animation['start_at']:
                continue
            if animation['source_type'] == 'party':
                source = (165, 208 + animation['source_index'] * 90)
            else:
                source_index = animation['source_index'] - target_scroll
                if not 0 <= source_index < visible_enemy_count:
                    continue
                source = (
                    389 + (source_index % 3) * 203,
                    371 + (source_index // 3) * 43,
                )
            if animation['target_type'] == 'party':
                target = (165, 208 + animation['target_index'] * 90)
            else:
                target_index = animation['target_index'] - target_scroll
                if not 0 <= target_index < visible_enemy_count:
                    continue
                target = (
                    389 + (target_index % 3) * 203,
                    371 + (target_index // 3) * 43,
                )
            duration = animation['end_at'] - animation['start_at']
            progress = min(1.0, (now - animation['start_at']) / duration)
            pygame.draw.line(self.screen, GOLD, source, target, 3)
            impact = (
                animation['result'] is not None
                and progress >= 0.7
            )
            marker_progress = min(progress / 0.7, 1.0)
            direction = (target[0] - source[0], target[1] - source[1])
            perpendicular = (direction[1], -direction[0])
            direction_length = max(
                1,
                (perpendicular[0] ** 2 + perpendicular[1] ** 2) ** 0.5,
            )
            miss_offset = (
                72 * (marker_progress - 0.75)
                if animation['result'] is False and marker_progress > 0.75
                else 0
            )
            marker = (
                round(source[0] + direction[0] * marker_progress
                      + perpendicular[0] / direction_length * miss_offset),
                round(source[1] + direction[1] * marker_progress
                      + perpendicular[1] / direction_length * miss_offset),
            )
            pygame.draw.circle(self.screen, CORAL, marker, 7)
            if impact:
                result = animation['result']
                result_color = CORAL if result is False else GREEN
                pygame.draw.circle(self.screen, result_color, target, 17, width=3)
                label = (
                    'MISS' if result is False
                    else 'CAST' if result == 'CAST'
                    else 'HIT'
                )
                label_surface = self.small.render(label, True, WHITE)
                label_rect = label_surface.get_rect(center=(target[0], target[1] - 25))
                background = label_rect.inflate(12, 6)
                pygame.draw.rect(self.screen, result_color, background, border_radius=4)
                self.screen.blit(label_surface, label_rect)
        self.attack_animations = active
