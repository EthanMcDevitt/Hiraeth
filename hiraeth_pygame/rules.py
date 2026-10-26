import json
import re
from pathlib import Path


CATALOG_FILE = Path(__file__).with_name('rules_catalog.json')
CATALOGS = ('weapons', 'armor', 'gear', 'spells')
STRING_FIELDS = {
    'weapons': ('range', 'damage', 'damage_type', 'attack_stat', 'traits'),
    'armor': ('kind', 'traits'),
    'gear': ('traits',),
    'spells': ('school', 'target', 'effect'),
}


class RulesDataError(ValueError):
    pass


def load_rules(path=CATALOG_FILE):
    try:
        with Path(path).open(encoding='utf-8') as file:
            catalogs = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise RulesDataError(f'Could not load rules catalog {path}: {error}') from error
    if not isinstance(catalogs, dict):
        raise RulesDataError('Rules catalog must be an object.')
    all_ids = set()
    for category in CATALOGS:
        items = catalogs.get(category)
        if not isinstance(items, list):
            raise RulesDataError(f'Rules catalog {category} must be a list.')
        seen = set()
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise RulesDataError(f'{category}[{index}] must be an object.')
            for field in ('id', 'name', 'traits' if category != 'spells' else 'effect'):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    raise RulesDataError(f'{category}[{index}].{field} must be non-empty text.')
            if item['id'] in seen:
                raise RulesDataError(f'Duplicate {category} id: {item["id"]}.')
            seen.add(item['id'])
            if item['id'] in all_ids:
                raise RulesDataError(f'Item ids must be unique across catalogs: {item["id"]}.')
            all_ids.add(item['id'])
            for field in STRING_FIELDS[category]:
                if not isinstance(item.get(field), str) or not item[field].strip():
                    raise RulesDataError(f'{category}[{index}].{field} must be non-empty text.')
            numeric_fields = ('cost',) if category == 'spells' else ('slots', 'cost')
            for field in numeric_fields:
                if isinstance(item.get(field), bool) or not isinstance(item.get(field), int) or item[field] < 0:
                    raise RulesDataError(f'{category}[{index}].{field} must be a non-negative integer.')
            if category == 'weapons':
                if not re.fullmatch(r'\d+d\d+', item['damage'].lower()):
                    raise RulesDataError(f'{category}[{index}].damage must use NdN dice notation.')
                if item['attack_stat'] not in ('STR', 'AGI'):
                    raise RulesDataError(f'{category}[{index}].attack_stat must be STR or AGI.')
            elif category == 'armor':
                if item.get('kind') not in ('armor', 'helmet', 'shield'):
                    raise RulesDataError(f'{category}[{index}].kind is invalid.')
                if isinstance(item.get('ap'), bool) or not isinstance(item.get('ap'), int) or item['ap'] < 0:
                    raise RulesDataError(f'{category}[{index}].ap must be a non-negative integer.')
            elif category == 'spells' and item.get('target') not in ('ally', 'foe'):
                raise RulesDataError(f'{category}[{index}].target is invalid.')
    return catalogs


RULES = load_rules()
