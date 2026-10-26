import json
import os
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from character_generator import create_character

app = Flask(__name__)
DATA_FILE = Path(__file__).with_name('characters.json')
TRAITS_FILE = Path(__file__).with_name('traits.json')
DATA_LOCK = threading.Lock()
CORE_TYPES = {'General', 'Drawback', 'Martial', 'Sorcery', 'Magic'}
with TRAITS_FILE.open(encoding='utf-8-sig') as file:
    TRAIT_CATALOG = json.load(file)
for trait in TRAIT_CATALOG:
    trait['Levels'].sort(key=lambda level: level['Level'])
TRAITS = {
    trait['Name']: trait
    for trait in TRAIT_CATALOG
    if not trait['PlayerOnly']
}
RACES = ['Human'] + sorted({
    trait['Type'] for trait in TRAIT_CATALOG
    if trait['Type'] not in CORE_TYPES
})
SEX_OPTIONS = ('Male', 'Female', 'Agender', 'Gender fluid')


def read_characters():
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open(encoding='utf-8') as file:
        characters = json.load(file)
    return characters if isinstance(characters, list) else []


def json_safe(value):
    return json.loads(json.dumps(
        value,
        default=lambda item: item.item() if hasattr(item, 'item') else str(item),
    ))


def write_characters(characters):
    temporary_file = DATA_FILE.with_suffix('.tmp')
    with temporary_file.open('w', encoding='utf-8') as file:
        json.dump(json_safe(characters), file, indent=2, ensure_ascii=True)
    os.replace(temporary_file, DATA_FILE)


def derived_stats(stats):
    strength, agility, constitution = stats['STR'], stats['AGI'], stats['CON']
    charisma, wisdom, willpower = stats['CHA'], stats['WIS'], stats['WIL']
    physical = sorted([constitution, strength, agility])
    return {
        'Health': constitution + max(strength, willpower),
        'Stamina': physical[-1] + physical[1],
        'Magica': willpower + max(charisma, wisdom),
    }


def whole_number(value, label):
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        raise ValueError(f'{label} must be a whole number.')
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a whole number.') from None


def normalize_stats(raw_stats):
    stat_keys = {'STR', 'AGI', 'CON', 'CHA', 'WIS', 'WIL'}
    if not isinstance(raw_stats, dict) or set(raw_stats) != stat_keys:
        raise ValueError('Provide all six attributes.')
    try:
        stats = {key: whole_number(value, 'Attributes') for key, value in raw_stats.items()}
    except ValueError:
        raise ValueError('Attributes must be whole numbers.') from None
    if any(value < 6 or value > 20 for value in stats.values()):
        raise ValueError('Each attribute must be between 6 and 20.')
    return stats


def normalize_traits(raw_traits):
    if not isinstance(raw_traits, dict):
        raise ValueError('Traits must be supplied as a name and cost list.')
    traits = {}
    for trait_name, raw_cost in raw_traits.items():
        if trait_name not in TRAITS:
            raise ValueError(f'Unknown trait: {trait_name}.')
        try:
            cost = whole_number(raw_cost, f'{trait_name} cost')
        except ValueError:
            raise ValueError(f'{trait_name} needs a whole-number cost.') from None
        trait = TRAITS[trait_name]
        if not trait['MinCost'] <= cost <= trait['MaxCost']:
            raise ValueError(f'{trait_name} cost must be between {trait["MinCost"]} and {trait["MaxCost"]}.')
        if trait['Levels'] and cost not in {level['Cost'] for level in trait['Levels']}:
            raise ValueError(f'{trait_name} cost must match one of its listed levels.')
        traits[trait_name] = cost
    return traits


def character_value(stats, traits):
    return sum(stats.values()) + sum(traits.values())


def character_value_limit(level, race):
    return 60 + (2 * level) + (2 if race == 'Human' else 0)


def error_response(message, status=400):
    return jsonify({'error': message}), status


def normalize_sex(value):
    sex = str(value or SEX_OPTIONS[0])
    if sex not in SEX_OPTIONS:
        raise ValueError('Choose a listed sex.')
    return sex


@app.get('/')
def index():
    return render_template('index.html')


@app.get('/api/options')
def options():
    return jsonify({'races': RACES, 'traits': list(TRAITS.values())})


@app.get('/api/characters')
def characters_index():
    with DATA_LOCK:
        return jsonify(read_characters())


@app.post('/api/characters')
def create_saved_character():
    payload = request.get_json(silent=True) or {}
    try:
        level = whole_number(payload.get('level', 1), 'Level')
    except ValueError as error:
        return error_response(str(error))
    race = str(payload.get('race', 'Human'))
    name = str(payload.get('name', '')).strip()[:80]
    try:
        sex = normalize_sex(payload.get('sex'))
    except ValueError as error:
        return error_response(str(error))
    if not 1 <= level <= 100:
        return error_response('Level must be between 1 and 100.')
    if race not in RACES:
        return error_response('Choose a listed race.')
    character = create_character(
        level,
        race=race,
        start_with_martial_training=bool(payload.get('martial')),
        start_with_sorcery=bool(payload.get('sorcery')),
        teenager=bool(payload.get('teenager')),
    )
    character = json_safe(character)
    generated_meta = character['Meta']
    generated_meta['Character Value'] = character_value(character['Stats'], character['Traits'])
    limit = character_value_limit(level, race)
    generated_meta['Character Value Limit'] = limit
    generated_meta['Target'] = limit - 60
    generated_meta['Starting Spread'] = 60
    generated_meta['Spread Offset'] = 0
    generated_meta['Allocated Points'] = generated_meta['Character Value'] - 60
    character['Id'] = uuid.uuid4().hex
    character['Name'] = name or f'{race} Character'
    character['Sex'] = sex
    with DATA_LOCK:
        saved = read_characters()
        saved.insert(0, character)
        write_characters(saved)
    return jsonify(character), 201


@app.post('/api/characters/manual')
def create_manual_character():
    payload = request.get_json(silent=True) or {}
    try:
        level = whole_number(payload.get('level', 1), 'Level')
    except ValueError as error:
        return error_response(str(error))
    race = str(payload.get('race', 'Human'))
    name = str(payload.get('name', '')).strip()[:80] or f'{race} Character'
    try:
        sex = normalize_sex(payload.get('sex'))
    except ValueError as error:
        return error_response(str(error))
    if not 1 <= level <= 100:
        return error_response('Level must be between 1 and 100.')
    if race not in RACES:
        return error_response('Choose a listed race.')
    try:
        stats = normalize_stats(payload.get('stats'))
        traits = normalize_traits(payload.get('traits', {}))
    except ValueError as error:
        return error_response(str(error))

    limit = character_value_limit(level, race)
    value = character_value(stats, traits)
    if value > limit:
        return error_response(f'Character value {value} exceeds the level {level} limit of {limit}.')

    character = {
        'Id': uuid.uuid4().hex,
        'Name': name,
        'Race': race,
        'Sex': sex,
        'Level': level,
        'Stats': stats,
        'Derived': derived_stats(stats),
        'Traits': traits,
        'Meta': {
            'Target': limit - 60,
            'Allocated Points': value - 60,
            'Spread Offset': 0,
            'Starting Spread': 60,
            'Has Martial Training': traits.get('Martial Training', 0) == 5,
            'Has Sorcery': traits.get('Sorcery', 0) == 5,
            'Teenager': 'Teenager' in traits,
            'Manual': True,
            'Character Value': value,
            'Character Value Limit': limit,
        },
    }
    with DATA_LOCK:
        saved = read_characters()
        saved.insert(0, character)
        write_characters(saved)
    return jsonify(character), 201


@app.put('/api/characters/<character_id>')
def update_saved_character(character_id):
    payload = request.get_json(silent=True) or {}
    with DATA_LOCK:
        saved = read_characters()
        character = next((item for item in saved if item.get('Id') == character_id), None)
        if character is None:
            return error_response('Character not found.', 404)
        name = str(payload.get('name', character.get('Name', ''))).strip()
        race = str(payload.get('race', character['Race']))
        try:
            sex = normalize_sex(payload.get('sex', character.get('Sex')))
        except ValueError as error:
            return error_response(str(error))
        try:
            level = whole_number(payload.get('level', character['Level']), 'Level')
        except ValueError as error:
            return error_response(str(error))
        if not name or len(name) > 80:
            return error_response('Name must be between 1 and 80 characters.')
        if race not in RACES or not 1 <= level <= 100:
            return error_response('Choose a listed race and a level from 1 to 100.')
        try:
            stats = normalize_stats(payload.get('stats', character['Stats']))
            clean_traits = normalize_traits(payload.get('traits', character['Traits']))
        except ValueError as error:
            return error_response(str(error))
        meta = character.setdefault('Meta', {})
        value = character_value(stats, clean_traits)
        limit = character_value_limit(level, race)
        if value > limit:
            return error_response(f'Character value {value} exceeds the level {level} limit of {limit}.')
        character.update({
            'Name': name,
            'Race': race,
            'Sex': sex,
            'Level': level,
            'Stats': stats,
            'Derived': derived_stats(stats),
            'Traits': clean_traits,
        })
        meta.update({
            'Target': limit - 60,
            'Allocated Points': value - 60,
            'Starting Spread': 60,
            'Spread Offset': 0,
            'Character Value': value,
            'Character Value Limit': limit,
            'Customized': True,
        })
        write_characters(saved)
    return jsonify(character)


@app.delete('/api/characters/<character_id>')
def delete_saved_character(character_id):
    with DATA_LOCK:
        saved = read_characters()
        remaining = [item for item in saved if item.get('Id') != character_id]
        if len(remaining) == len(saved):
            return error_response('Character not found.', 404)
        write_characters(remaining)
    return jsonify({'deleted': character_id})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)