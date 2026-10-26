import json
from pathlib import Path

from flask import Flask, jsonify, render_template

app = Flask(__name__)
CHARACTERS_FILE = Path(__file__).resolve().parent.parent / 'characters.json'


@app.get('/')
def index():
    return render_template('index.html')


@app.get('/api/characters')
def characters():
    if not CHARACTERS_FILE.exists():
        return jsonify([])
    try:
        with CHARACTERS_FILE.open(encoding='utf-8') as file:
            saved = json.load(file)
    except (OSError, json.JSONDecodeError):
        app.logger.exception('Unable to read the character archive.')
        return jsonify({'error': 'The character archive could not be read.'}), 500
    if not isinstance(saved, list):
        app.logger.error('The character archive must contain a list.')
        return jsonify({'error': 'The character archive has an invalid format.'}), 500
    return jsonify([
        character for character in saved
        if isinstance(character, dict)
        and character.get('Id')
        and character.get('Name')
        and character.get('Stats')
        and character.get('Derived')
    ])


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=False)
