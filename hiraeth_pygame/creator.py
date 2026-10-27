if __package__:
    from .shared import (
        CHARACTERS_FILE,
        GOLD,
        INK,
        LINE,
        MAX_PARTY,
        SEX_OPTIONS,
        TRAITS_FILE,
        WHITE,
        character_point_limit,
        json,
        os,
        spell_capacity,
        uuid,
    )
else:
    from shared import (
        CHARACTERS_FILE,
        GOLD,
        INK,
        LINE,
        MAX_PARTY,
        SEX_OPTIONS,
        TRAITS_FILE,
        WHITE,
        character_point_limit,
        json,
        os,
        spell_capacity,
        uuid,
    )


class CreatorMixin:

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
