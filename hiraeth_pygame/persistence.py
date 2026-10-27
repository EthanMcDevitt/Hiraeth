if __package__:
    from .shared import (
        MAX_PARTY,
        SAVE_FILE,
        json,
    )
else:
    from shared import (
        MAX_PARTY,
        SAVE_FILE,
        json,
    )


class PersistenceMixin:

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
                for enemy in battle.get('enemies', []):
                    template = next(
                        (
                            monster for monster in self.config['monsters']
                            if monster['name'] == enemy.get('name')
                        ),
                        None,
                    )
                    legacy_attack = enemy.get('attack', 1)
                    enemy.setdefault(
                        'chance_to_hit',
                        template['chance_to_hit'] if template else 60,
                    )
                    enemy.setdefault(
                        'damage',
                        template['damage'] if template else max(1, legacy_attack),
                    )
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
