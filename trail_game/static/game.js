const root = document.querySelector('#game');
const SAVE_KEY = 'hiraeth-emberroad-save';
const ROAD_LENGTH = 6;
const statNames = { STR: 'Strength', AGI: 'Agility', CON: 'Constitution', CHA: 'Charisma', WIS: 'Wisdom', WIL: 'Willpower' };
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
let characters = [];
let game = null;
let notice = '';

function loadGame() {
  try {
    const saved = localStorage.getItem(SAVE_KEY);
    if (!saved) return;
    const parsed = JSON.parse(saved);
    if (parsed && parsed.character?.Stats && Array.isArray(parsed.log)) game = parsed;
    else notice = 'The saved journey was invalid and could not be restored.';
  } catch (error) {
    notice = 'The saved journey could not be read.';
  }
}

function saveGame() {
  if (game) localStorage.setItem(SAVE_KEY, JSON.stringify(game));
  else localStorage.removeItem(SAVE_KEY);
}

function renderIntro() {
  root.innerHTML = `<section class="intro">
    <p class="section-kicker">A FANTASY WILDERNESS JOURNEY</p>
    <h1>The Emberroad</h1>
    <p class="intro-copy">The frontier lies six stretches west. Keep your party fed, make hard choices, and see who reaches the far side of the wilds.</p>
    ${characters.length
      ? `<label class="character-picker" for="traveler">CHOOSE YOUR TRAVELER
          <select id="traveler">${characters.map((character) => `<option value="${escapeHtml(character.Id)}">${escapeHtml(character.Name)} — ${escapeHtml(character.Race)}, Level ${escapeHtml(character.Level)}</option>`).join('')}</select>
        </label>
        <button class="button button-primary" type="button" data-action="start">Begin the journey <span aria-hidden="true">→</span></button>`
      : `<div class="empty"><h1>No travelers yet</h1><p>Generate or create a character in the Character Workshop, then return here to begin.</p><a href="http://127.0.0.1:5000/">Open the Character Workshop ↗</a></div>`}
    ${notice ? `<p class="warning">${escapeHtml(notice)}</p>` : ''}
  </section>`;
}

function renderGame() {
  if (!game) {
    renderIntro();
    return;
  }
  const traveler = game.character;
  const finished = game.ended;
  const progress = Math.min(100, Math.round(game.leg / ROAD_LENGTH * 100));
  const pending = game.pending;
  root.innerHTML = `<div class="trail-header">
    <div><p class="section-kicker">THE EMBERROAD <span>/ DAY ${game.day}</span></p>
      <h1>${finished ? (game.won ? 'A new horizon.' : 'The road goes quiet.') : `Leg ${Math.min(game.leg + 1, ROAD_LENGTH)} of ${ROAD_LENGTH}`}</h1>
      <p>${finished ? (game.won ? `${escapeHtml(traveler.Name)} and their party reached the frontier.` : `${escapeHtml(traveler.Name)} could travel no farther.`) : `Traveling as ${escapeHtml(traveler.Name)} the ${escapeHtml(traveler.Race)}.`}</p>
    </div>
    <button class="button button-quiet" type="button" data-action="new">${finished ? 'Start another journey' : 'Abandon journey'}</button>
  </div>
  <div class="progress" role="progressbar" aria-label="Journey progress" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100"><span style="width:${progress}%"></span></div>
  <section class="resources" aria-label="Journey resources">
    <div class="resource"><span>FOOD</span><strong>${game.food}</strong><small>rations</small></div>
    <div class="resource"><span>HEALTH</span><strong>${game.health}<i> / ${game.maxHealth}</i></strong><small>${game.health === 0 ? 'fallen' : 'vitality'}</small></div>
    <div class="resource"><span>JOURNEY</span><strong>${game.leg}<i> / ${ROAD_LENGTH}</i></strong><small>stretches crossed</small></div>
  </section>
  ${pending ? `<section class="event">
      <p class="section-kicker">ON THE ROAD</p><h2>${escapeHtml(pending.title)}</h2><p>${escapeHtml(pending.description)}</p>
      <div class="choices">${pending.choices.map((choice, index) => `<button class="trail-choice" type="button" data-action="choice" data-choice="${index}"><strong>${escapeHtml(choice.label)}</strong><span>${escapeHtml(statNames[choice.stat])} check · DC ${choice.dc}</span></button>`).join('')}</div>
    </section>` : !finished ? `<section class="trail-section">
      <h2>Make camp or move on</h2><p>Travel costs 3 food and brings a new challenge. Forage for food or rest to recover before setting out.</p>
      <div class="actions">
        <button class="button button-primary" type="button" data-action="travel" ${game.food < 3 ? 'disabled' : ''}>Travel onward <span aria-hidden="true">→</span></button>
        <button class="button button-secondary" type="button" data-action="forage">Forage <span aria-hidden="true">⌕</span></button>
        <button class="button button-secondary" type="button" data-action="rest" ${game.food < 2 || game.health >= game.maxHealth ? 'disabled' : ''}>Rest <span aria-hidden="true">＋</span></button>
      </div>
      ${game.food < 3 ? '<p class="warning">Not enough food to travel. Forage before moving on.</p>' : ''}
    </section>` : `<section class="ending"><h2>${game.won ? 'The journey ends in triumph' : 'The journey ends here'}</h2><p>${game.won ? 'The road was long, but your party made it through.' : 'The wilderness claimed the last of your strength.'}</p></section>`}
  <section class="journal"><h2>Road journal</h2><ol>${game.log.map((entry) => `<li>${escapeHtml(entry)}</li>`).join('')}</ol></section>`;
}

const encounters = [
  { title: 'The flooded crossing', description: 'A swollen river has swallowed the ford. The current is swift, and the old bridge is gone.', choices: [
    { label: 'Scout for a safer crossing', stat: 'WIS', dc: 11, success: 'You find a shallow passage and guide the party across.', failure: 'The crossing turns treacherous. You reach the far bank bruised.', damage: 3 },
    { label: 'Wade through together', stat: 'CON', dc: 10, success: 'You keep the party together and make it across.', failure: 'The current knocks you down before you reach the far bank.', damage: 4 },
  ] },
  { title: 'A hungry forest beast', description: 'A horned shadow steps between the trees, blocking the trail and eyeing your provisions.', choices: [
    { label: 'Stand your ground', stat: 'STR', dc: 12, success: 'A show of strength sends the beast retreating into the woods.', failure: 'The beast lunges before you can drive it off.', damage: 5 },
    { label: 'Calm it with a steady voice', stat: 'WIL', dc: 11, success: 'Your calm presence settles the beast and it lets you pass.', failure: 'The beast charges. You escape, but not unhurt.', damage: 4 },
  ] },
  { title: 'The trail disappears', description: 'Fresh rockfall has buried the path. Somewhere beyond it lies the road west.', choices: [
    { label: 'Read the land and find a way around', stat: 'WIS', dc: 10, success: 'You find an old hunters’ track and rejoin the road.', failure: 'The detour leads through thorny scrub.', damage: 2 },
    { label: 'Climb over the rubble', stat: 'AGI', dc: 12, success: 'You scramble over the stones without losing a step.', failure: 'Loose rocks give way beneath you.', damage: 4 },
  ] },
  { title: 'A roadside peddler', description: 'A peddler offers a few rations in exchange for a good story and a little coin.', choices: [
    { label: 'Win them over with a tale', stat: 'CHA', dc: 10, success: 'The peddler is charmed and gives you 4 rations.', failure: 'The peddler stays guarded. You carry on without a trade.', foodSuccess: 4 },
    { label: 'Politely decline and keep moving', stat: 'WIL', dc: 8, success: 'You move on without trouble.', failure: 'A rough detour costs you 2 rations.', foodFailure: -2 },
  ] },
];

function endIfNeeded() {
  if (game.health <= 0) {
    game.health = 0;
    game.ended = true;
    game.won = false;
  } else if (game.leg >= ROAD_LENGTH) {
    game.ended = true;
    game.won = true;
  }
}

function resolveChoice(index) {
  const choice = game.pending?.choices[index];
  if (!choice) return;
  const stat = Number(game.character.Stats[choice.stat]) || 10;
  const modifier = Math.floor((stat - 10) / 2);
  const roll = Math.floor(Math.random() * 20) + 1;
  const success = roll + modifier >= choice.dc;
  if (!success) game.health -= choice.damage || 0;
  game.food = Math.max(0, game.food + (success ? (choice.foodSuccess || 0) : (choice.foodFailure || 0)));
  game.leg += 1;
  game.pending = null;
  game.log.unshift(`${success ? 'Success' : 'Setback'} (${roll} + ${modifier}): ${success ? choice.success : choice.failure}`);
  endIfNeeded();
  saveGame();
  renderGame();
}

root.addEventListener('click', (event) => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const action = button.dataset.action;
  if (action === 'start') {
    const character = characters.find((item) => item.Id === document.querySelector('#traveler').value);
    if (!character) return;
    const maxHealth = Number(character.Derived.Health);
    game = { character, day: 1, leg: 0, food: 18, health: maxHealth, maxHealth, log: [`${character.Name} sets out toward the western frontier with 18 rations.`], pending: null, ended: false, won: false };
    saveGame();
    renderGame();
  } else if (action === 'new') {
    game = null;
    saveGame();
    renderGame();
  } else if (action === 'travel' && !game.pending && game.food >= 3) {
    game.food -= 3;
    game.day += 1;
    game.log.unshift('The party spends 3 rations and presses on.');
    game.pending = encounters[Math.floor(Math.random() * encounters.length)];
    saveGame();
    renderGame();
  } else if (action === 'choice') {
    resolveChoice(Number(button.dataset.choice));
  } else if (action === 'forage' && !game.pending) {
    game.day += 1;
    const stat = Number(game.character.Stats.WIS) || 10;
    const modifier = Math.floor((stat - 10) / 2);
    const roll = Math.floor(Math.random() * 20) + 1;
    const success = roll + modifier >= 10;
    const gathered = success ? 4 + Math.floor(Math.random() * 3) : 1;
    game.food += gathered;
    if (!success) game.health -= 1;
    game.log.unshift(`${success ? 'Foraging succeeds' : 'Foraging yields little'} (${roll} + ${modifier}): ${success ? `you find ${gathered} rations.` : `you find 1 ration and take 1 damage.`}`);
    endIfNeeded();
    saveGame();
    renderGame();
  } else if (action === 'rest' && !game.pending && game.food >= 2 && game.health < game.maxHealth) {
    game.day += 1;
    game.food -= 2;
    const recovered = Math.min(5, game.maxHealth - game.health);
    game.health += recovered;
    game.log.unshift(`The party rests, spends 2 rations, and recovers ${recovered} health.`);
    saveGame();
    renderGame();
  }
});

async function start() {
  loadGame();
  try {
    const response = await fetch('/api/characters');
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'The character archive could not be loaded.');
    characters = body;
    renderGame();
  } catch (error) {
    root.innerHTML = `<section class="empty"><h1>Archive unavailable</h1><p>${escapeHtml(error.message)}</p><p>Start the Character Workshop and try again.</p></section>`;
  }
}

start();
