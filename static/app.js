const api = async (url, options = {}) => {
  const response = await fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'The request could not be completed.');
  return body;
};

const state = { characters: [], options: { races: [], traits: [] }, selectedId: null, draft: null, dirty: false, toastTimer: null, manualTraits: {} };
const statNames = { STR: 'Strength', AGI: 'Agility', CON: 'Constitution', CHA: 'Charisma', WIS: 'Wisdom', WIL: 'Willpower' };
const sexOptions = ['Male', 'Female', 'Agender', 'Gender fluid'];
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const sheetArea = document.querySelector('#sheet-area');

function showToast(message) {
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove('visible'), 2600);
}

function markDirty() {
  state.dirty = true;
  const saveButton = document.querySelector('#save-character');
  if (saveButton) {
    saveButton.disabled = false;
    saveButton.textContent = 'Save changes';
  }
}

function renderRoster() {
  const roster = document.querySelector('#roster-list');
  roster.innerHTML = state.characters.map((character) => `
    <div class="roster-item ${character.Id === state.selectedId ? 'active' : ''}">
      <button class="roster-select" type="button" data-select="${escapeHtml(character.Id)}">
        <span class="roster-name">${escapeHtml(character.Name || `${character.Race} Character`)}</span>
        <span class="roster-sub">${escapeHtml(character.Race)} &nbsp;·&nbsp; LEVEL ${escapeHtml(character.Level)}</span>
      </button>
    </div>`).join('');
  document.querySelector('#roster-count').textContent = state.characters.length;
  document.querySelector('#roster-empty').hidden = state.characters.length > 0;
}

function traitOptionMarkup() {
  const grouped = new Map();
  state.options.traits.forEach((trait) => {
    if (!grouped.has(trait.Type)) grouped.set(trait.Type, []);
    grouped.get(trait.Type).push(trait);
  });
  return [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([type, traits]) => `
    <optgroup label="${escapeHtml(type)}">${traits.map((trait) => `
      <option value="${escapeHtml(trait.Name)}">${escapeHtml(trait.Name)}</option>`).join('')}
    </optgroup>`).join('');
}

function renderSheet() {
  if (!state.draft) {
    sheetArea.innerHTML = '<div class="empty-sheet"><div class="empty-mark">CW</div><p class="section-kicker">THE CHARACTER ARCHIVE</p><h2>A story starts<br>with a person.</h2><p>Generate someone new, or choose a character from your roster.</p></div>';
    return;
  }
  const character = state.draft;
  const traitRows = Object.entries(character.Traits || {}).map(([name, cost]) => {
    const details = state.options.traits.find((trait) => trait.Name === name);
    const safeName = escapeHtml(name);
    const levels = details?.Levels || [];
    const selectedLevel = levels.find((level) => Number(level.Cost) === Number(cost));
    const costControl = levels.length
      ? `<select aria-label="${safeName} level" data-trait-cost="${safeName}">${levels.map((level) => `<option value="${level.Cost}" ${Number(level.Cost) === Number(cost) ? 'selected' : ''}>Level ${level.Level} | Cost ${level.Cost}</option>`).join('')}</select>`
      : `<input aria-label="${safeName} cost" type="number" value="${escapeHtml(cost)}" min="${details?.MinCost ?? cost}" max="${details?.MaxCost ?? cost}" data-trait-cost="${safeName}">`;
    const description = details?.Description
      ? `<p class="trait-description">${escapeHtml(details.Description)}</p>`
      : '';
    const effect = selectedLevel
      ? `<p class="trait-effect">${escapeHtml(selectedLevel.Effect)}</p>`
      : '';
    return `<article class="trait-row">
      <div><div class="trait-title">${safeName}<span class="trait-type">${escapeHtml(details?.Type || 'Custom')}</span></div>
      ${description}${effect}</div>
      ${costControl}
      <button class="trait-remove" type="button" title="Remove ${safeName}" aria-label="Remove ${safeName}" data-remove-trait="${safeName}">&times;</button>
    </article>`;
  }).join('');
  const ancestryFeatures = Array.isArray(character['Ancestry Features'])
    ? character['Ancestry Features'].map((feature) => {
      const separator = feature.indexOf(' (');
      const name = separator < 0 ? feature : feature.slice(0, separator);
      const description = separator < 0 ? 'Granted automatically by ancestry.' : feature.slice(separator + 2, -1);
      return `<article class="trait-row ancestry-trait-row">
        <div><div class="trait-title">${escapeHtml(name)}<span class="trait-type">FREE · ${escapeHtml(character.Race)} ANCESTRY</span></div>
        <p class="trait-description">${escapeHtml(description)}</p></div>
      </article>`;
    }).join('')
    : '';
  const knownSpells = Array.isArray(character.known_spells)
    ? character.known_spells
    : [];
  const sorceryRank = Number(character.Traits?.Sorcery || 0);
  const canLearnSpells = character.Race === 'Shei' || sorceryRank >= 5;
  const spellCapacity = canLearnSpells
    ? Math.max(0, Math.floor((Number(character.Stats?.WIL || 10) - 10) / 2) + (character.Race === 'Shei' ? 1 : 0))
    : 0;
  const knownSpellText = knownSpells.length
    ? knownSpells.map((spell) => typeof spell === 'string' ? spell : spell?.name).filter(Boolean).join(' · ')
    : 'None learned. Learn spells during a Hiraeth journey.';
  const points = `<div class="points-note" id="point-allocation" aria-live="polite">
      <strong>POINT ALLOCATION</strong>
      <span id="point-total"></span>
      <span id="point-status"></span>
    </div>`;

  sheetArea.innerHTML = `<div class="sheet-heading">
    <div><p class="section-kicker">CHARACTER SHEET <span>/ ${escapeHtml(character.Id.slice(0, 6).toUpperCase())}</span></p><h2>${escapeHtml(character.Name)}</h2><p class="sheet-subtitle">Changes are kept in your local character archive.</p></div>
    <div class="heading-actions"><button id="save-character" class="button button-save" type="button" ${state.dirty ? '' : 'disabled'}>${state.dirty ? 'Save changes' : 'Saved'}</button><button id="delete-character" class="button button-delete" type="button">Delete</button></div>
  </div>
  <div class="identity-row">
    <label><span class="field-label">Name</span><input id="edit-name" type="text" maxlength="80" value="${escapeHtml(character.Name)}"></label>
    <label><span class="field-label">Race</span><select id="edit-race">${state.options.races.map((race) => `<option value="${escapeHtml(race)}" ${race === character.Race ? 'selected' : ''}>${escapeHtml(race)}</option>`).join('')}</select></label>
    <label><span class="field-label">Sex</span><select id="edit-sex">${sexOptions.map((sex) => `<option value="${escapeHtml(sex)}" ${sex === (character.Sex || 'Male') ? 'selected' : ''}>${escapeHtml(sex)}</option>`).join('')}</select></label>
    <label><span class="field-label">Level</span><input id="edit-level" type="number" min="1" max="100" value="${escapeHtml(character.Level)}"></label>
  </div>
  <section class="sheet-block">
    <div class="block-heading"><h3>Attributes</h3><span>EDIT VALUES FROM 6 TO 20</span></div>
    <div class="stats-grid">${Object.entries(statNames).map(([key, label]) => `<div class="stat-tile"><label for="stat-${key}">${label}</label><input id="stat-${key}" type="number" min="6" max="20" value="${escapeHtml(character.Stats[key])}" data-stat="${key}"></div>`).join('')}</div>
  </section>
  <section class="sheet-block">
    <div class="block-heading"><h3>Stats</h3><span>CALCULATED FROM ATTRIBUTES</span></div>
    <div class="derived-grid">${Object.entries(character.Derived).filter(([label]) => label !== 'Max Spells').map(([label, value]) => `<div class="derived-tile"><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join('')}</div>
  </section>
  <section class="sheet-block known-spells-block">
    <div class="block-heading"><h3>Known Spells</h3><span>${knownSpells.length} LEARNED · ${spellCapacity} MAX</span></div>
    <div class="traits-list"><article class="trait-row ancestry-trait-row"><p class="trait-description">${escapeHtml(knownSpellText)}</p></article></div>
  </section>
  <section class="sheet-block">
    <div class="block-heading"><h3>Traits</h3><span>${Object.keys(character.Traits || {}).length} SELECTED · ANCESTRY FEATURES ARE FREE</span></div>
    <div class="traits-list">${traitRows}${ancestryFeatures}${traitRows || ancestryFeatures ? '' : '<p class="roster-empty">No traits selected yet. Add one below.</p>'}</div>
    <div class="add-trait"><select id="trait-picker" aria-label="Choose a trait">${traitOptionMarkup()}</select><div id="new-trait-cost-control"><input id="new-trait-cost" type="number" aria-label="Trait cost" value="1"></div><button id="add-trait" class="button" type="button">Add trait <span aria-hidden="true">+</span></button></div>
    <p id="new-trait-effect" class="trait-effect-preview" hidden></p>
  </section>${points}`;
  configureTraitCost();
  updatePointAllocation();
}

function updatePointAllocation() {
  const totalElement = document.querySelector('#point-total');
  const statusElement = document.querySelector('#point-status');
  if (!totalElement || !statusElement || !state.draft) return;

  const levelInput = document.querySelector('#edit-level');
  const level = Number(levelInput.value);
  const statInputs = [...sheetArea.querySelectorAll('[data-stat]')];
  const traitInputs = [...sheetArea.querySelectorAll('[data-trait-cost]')];
  const allocationInputs = [...statInputs, ...traitInputs];
  const values = allocationInputs.map((input) => Number(input.value));
  const valid = Number.isInteger(level) && level >= 1 && level <= 100
    && levelInput.value.trim() !== ''
    && allocationInputs.every((input) => input.value.trim() !== '')
    && values.every(Number.isInteger);
  const race = document.querySelector('#edit-race')?.value || state.draft.Race;
  const allowed = 60 + (2 * level) + (race === 'Human' ? 2 : 0);

  if (!valid || !Number.isFinite(allowed)) {
    totalElement.textContent = 'Current value: —';
    statusElement.textContent = 'Check level, attributes, and trait costs.';
    statusElement.classList.add('over');
    return;
  }

  const current = values.reduce((sum, value) => sum + value, 0);
  const remaining = allowed - current;
  totalElement.textContent = `Current value: ${current} / ${allowed}`;
  statusElement.textContent = remaining >= 0
    ? `${remaining} point${remaining === 1 ? '' : 's'} remaining`
    : `${Math.abs(remaining)} point${remaining === -1 ? '' : 's'} over budget`;
  statusElement.classList.toggle('over', remaining < 0);
}

function configureTraitCost() {
  const picker = document.querySelector('#trait-picker');
  const costControl = document.querySelector('#new-trait-cost-control');
  const effectPreview = document.querySelector('#new-trait-effect');
  if (!picker || !costControl || !effectPreview) return;
  const updatePreview = () => {
    const trait = state.options.traits.find((item) => item.Name === picker.value);
    const selectedCost = Number(costControl.querySelector('#new-trait-cost')?.value);
    const selectedLevel = trait?.Levels?.find((level) => Number(level.Cost) === selectedCost);
    effectPreview.textContent = selectedLevel?.Effect || '';
    effectPreview.hidden = !selectedLevel;
  };
  const updateCostControl = () => {
    const trait = state.options.traits.find((item) => item.Name === picker.value);
    if (!trait) return;
    if (trait.Levels?.length) {
      costControl.innerHTML = `<select id="new-trait-cost" aria-label="Trait level">${trait.Levels.map((level) => `<option value="${level.Cost}">Level ${level.Level} | Cost ${level.Cost}</option>`).join('')}</select>`;
    } else {
      costControl.innerHTML = `<input id="new-trait-cost" type="number" aria-label="Trait cost" value="${trait.Cost}" min="${trait.MinCost}" max="${trait.MaxCost}">`;
    }
    updatePreview();
  };
  picker.addEventListener('change', updateCostControl);
  costControl.addEventListener('input', updatePreview);
  costControl.addEventListener('change', updatePreview);
  updateCostControl();
}

function renderManualTraits() {
  const list = document.querySelector('#manual-selected-traits');
  if (!list) return;
  list.innerHTML = Object.entries(state.manualTraits).map(([name, cost]) => {
    const trait = state.options.traits.find((item) => item.Name === name);
    const safeName = escapeHtml(name);
    const level = trait?.Levels?.find((item) => Number(item.Cost) === Number(cost));
    const costControl = trait?.Levels?.length
      ? `<select aria-label="${safeName} level" data-manual-trait-cost="${safeName}">${trait.Levels.map((item) => `<option value="${item.Cost}" ${Number(item.Cost) === Number(cost) ? 'selected' : ''}>Level ${item.Level} | Cost ${item.Cost}</option>`).join('')}</select>`
      : `<input aria-label="${safeName} cost" type="number" min="${trait?.MinCost ?? cost}" max="${trait?.MaxCost ?? cost}" value="${escapeHtml(cost)}" data-manual-trait-cost="${safeName}">`;
    return `<article class="manual-trait-row">
      <div><strong>${safeName}</strong><span>${escapeHtml(trait?.Type || 'Custom')}</span>${level ? `<p class="trait-effect">${escapeHtml(level.Effect)}</p>` : ''}</div>
      ${costControl}
      <button type="button" class="trait-remove" aria-label="Remove ${safeName}" data-remove-manual-trait="${safeName}">&times;</button>
    </article>`;
  }).join('');
}

function updateManualBudget() {
  const form = document.querySelector('#manual-form');
  if (!form) return;
  const level = Number(form.elements.level.value);
  const statInputs = [...form.querySelectorAll('[data-manual-stat]')];
  const stats = statInputs.map((input) => Number(input.value));
  const statsValid = stats.length === 6 && stats.every((value) => Number.isInteger(value) && value >= 6 && value <= 20);
  const levelValid = Number.isInteger(level) && level >= 1 && level <= 100;
  const value = stats.reduce((total, stat) => total + (Number.isFinite(stat) ? stat : 0), 0)
    + Object.values(state.manualTraits).reduce((total, cost) => total + Number(cost), 0);
  const limit = levelValid
    ? 60 + (2 * level) + (form.elements.race.value === 'Human' ? 2 : 0)
    : 0;
  const overLimit = value > limit;
  document.querySelector('#manual-value').textContent = value;
  document.querySelector('#manual-limit').textContent = limit;
  const status = document.querySelector('#manual-budget-status');
  status.textContent = !statsValid || !levelValid
    ? 'CHECK ATTRIBUTES AND LEVEL'
    : overLimit
      ? `OVER LIMIT BY ${value - limit}`
      : `${limit - value} POINTS REMAINING`;
  status.classList.toggle('over', overLimit || !statsValid || !levelValid);
  document.querySelector('#manual-submit').disabled = !statsValid || !levelValid || overLimit;
}

function configureManualTraitPicker() {
  const picker = document.querySelector('#manual-trait-picker');
  const costControl = document.querySelector('#manual-trait-cost-control');
  const preview = document.querySelector('#manual-trait-effect');
  if (!picker || !costControl || !preview) return;
  const updatePreview = () => {
    const trait = state.options.traits.find((item) => item.Name === picker.value);
    const cost = Number(costControl.querySelector('[data-manual-cost]')?.value);
    const level = trait?.Levels?.find((item) => Number(item.Cost) === cost);
    preview.textContent = level?.Effect || '';
    preview.hidden = !level;
  };
  const updateCostControl = () => {
    const trait = state.options.traits.find((item) => item.Name === picker.value);
    if (!trait) return;
    costControl.innerHTML = trait.Levels?.length
      ? `<select data-manual-cost aria-label="Selected trait level">${trait.Levels.map((level) => `<option value="${level.Cost}">Level ${level.Level} | Cost ${level.Cost}</option>`).join('')}</select>`
      : `<input data-manual-cost type="number" aria-label="Selected trait cost" value="${trait.Cost}" min="${trait.MinCost}" max="${trait.MaxCost}">`;
    updatePreview();
  };
  picker.addEventListener('change', updateCostControl);
  costControl.addEventListener('input', updatePreview);
  costControl.addEventListener('change', updatePreview);
  updateCostControl();
}

function captureDraft() {
  if (!state.draft) return;
  state.draft.Name = document.querySelector('#edit-name').value;
  state.draft.Race = document.querySelector('#edit-race').value;
  state.draft.Sex = document.querySelector('#edit-sex').value;
  state.draft.Level = document.querySelector('#edit-level').value;
  state.draft.Stats = Object.fromEntries([...sheetArea.querySelectorAll('[data-stat]')].map((input) => [input.dataset.stat, input.value]));
  state.draft.Traits = Object.fromEntries([...sheetArea.querySelectorAll('[data-trait-cost]')].map((input) => [input.dataset.traitCost, input.value]));
}

function selectCharacter(id) {
  const selected = state.characters.find((character) => character.Id === id);
  if (!selected) return;
  state.selectedId = id;
  state.draft = structuredClone(selected);
  state.dirty = false;
  renderRoster();
  renderSheet();
}

async function refreshCharacters(selectId = state.selectedId) {
  state.characters = await api('/api/characters');
  renderRoster();
  if (selectId && state.characters.some((character) => character.Id === selectId)) selectCharacter(selectId);
  else if (state.characters.length) selectCharacter(state.characters[0].Id);
  else {
    state.selectedId = null;
    state.draft = null;
    renderSheet();
  }
}

document.querySelector('#roster-list').addEventListener('click', (event) => {
  const button = event.target.closest('[data-select]');
  if (button) selectCharacter(button.dataset.select);
});

document.querySelector('#generator-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  const message = document.querySelector('#generator-message');
  const submit = formElement.querySelector('button[type="submit"]');
  message.textContent = '';
  submit.disabled = true;
  try {
    const character = await api('/api/characters', { method: 'POST', body: JSON.stringify({
      name: form.get('name'), level: form.get('level'), race: form.get('race'),
      sex: form.get('sex'),
      martial: form.has('martial'), sorcery: form.has('sorcery'), teenager: form.has('teenager'),
    }) });
    formElement.querySelector('[name="name"]').value = '';
    await refreshCharacters(character.Id);
    showToast(`${character.Name} added to your roster.`);
  } catch (error) {
    message.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

document.querySelector('.procedure-switch').addEventListener('click', (event) => {
  const tab = event.target.closest('[data-mode]');
  if (!tab) return;
  const manual = tab.dataset.mode === 'manual';
  document.querySelectorAll('.procedure-tab').forEach((item) => {
    const selected = item === tab;
    item.classList.toggle('active', selected);
    item.setAttribute('aria-selected', String(selected));
  });
  document.querySelector('#generator-form').hidden = manual;
  document.querySelector('#manual-form').hidden = !manual;
});

const manualForm = document.querySelector('#manual-form');
manualForm.addEventListener('input', updateManualBudget);
manualForm.addEventListener('change', (event) => {
  const costInput = event.target.closest('[data-manual-trait-cost]');
  if (costInput) {
    state.manualTraits[costInput.dataset.manualTraitCost] = Number(costInput.value);
    renderManualTraits();
  }
  updateManualBudget();
});
manualForm.addEventListener('click', (event) => {
  if (event.target.id === 'manual-add-trait') {
    const name = document.querySelector('#manual-trait-picker').value;
    const cost = Number(document.querySelector('[data-manual-cost]').value);
    const message = document.querySelector('#manual-message');
    if (Object.hasOwn(state.manualTraits, name)) {
      message.textContent = 'That trait is already selected.';
      return;
    }
    state.manualTraits[name] = cost;
    message.textContent = '';
    renderManualTraits();
    updateManualBudget();
    return;
  }
  const removeButton = event.target.closest('[data-remove-manual-trait]');
  if (removeButton) {
    delete state.manualTraits[removeButton.dataset.removeManualTrait];
    renderManualTraits();
    updateManualBudget();
  }
});
manualForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = document.querySelector('#manual-submit');
  const message = document.querySelector('#manual-message');
  submit.disabled = true;
  message.textContent = '';
  try {
    const stats = Object.fromEntries([...form.querySelectorAll('[data-manual-stat]')].map((input) => [input.dataset.manualStat, input.value]));
    const character = await api('/api/characters/manual', { method: 'POST', body: JSON.stringify({
      name: form.elements.name.value,
      race: form.elements.race.value,
      sex: form.elements.sex.value,
      level: form.elements.level.value,
      stats,
      traits: state.manualTraits,
    }) });
    state.manualTraits = {};
    await refreshCharacters(character.Id);
    showToast(`${character.Name} added to your roster.`);
  } catch (error) {
    message.textContent = error.message;
  } finally {
    updateManualBudget();
  }
});

sheetArea.addEventListener('input', (event) => {
  if (event.target.matches('input, select')) {
    markDirty();
    updatePointAllocation();
  }
});
sheetArea.addEventListener('change', (event) => {
  if (event.target.matches('input, select')) {
    markDirty();
    updatePointAllocation();
  }
  if (event.target.matches('[data-trait-cost]')) {
    const row = event.target.closest('.trait-row');
    const name = event.target.dataset.traitCost;
    const trait = state.options.traits.find((item) => item.Name === name);
    const level = trait?.Levels?.find((item) => Number(item.Cost) === Number(event.target.value));
    const effect = row?.querySelector('.trait-effect');
    if (effect) effect.textContent = level?.Effect || '';
  }
});

sheetArea.addEventListener('click', async (event) => {
  const removeButton = event.target.closest('[data-remove-trait]');
  if (removeButton) {
    captureDraft();
    delete state.draft.Traits[removeButton.dataset.removeTrait];
    markDirty();
    renderSheet();
    return;
  }
  if (event.target.id === 'add-trait') {
    captureDraft();
    const name = document.querySelector('#trait-picker').value;
    const cost = Number(document.querySelector('#new-trait-cost').value);
    state.draft.Traits[name] = cost;
    markDirty();
    renderSheet();
    return;
  }
  if (event.target.id === 'save-character') {
    const stats = Object.fromEntries([...sheetArea.querySelectorAll('[data-stat]')].map((input) => [input.dataset.stat, input.value]));
    const traits = Object.fromEntries([...sheetArea.querySelectorAll('[data-trait-cost]')].map((input) => [input.dataset.traitCost, input.value]));
    try {
      const saved = await api(`/api/characters/${encodeURIComponent(state.selectedId)}`, { method: 'PUT', body: JSON.stringify({
        name: document.querySelector('#edit-name').value,
        race: document.querySelector('#edit-race').value,
        sex: document.querySelector('#edit-sex').value,
        level: document.querySelector('#edit-level').value,
        stats, traits,
      }) });
      state.draft = saved;
      state.dirty = false;
      state.characters = state.characters.map((character) => character.Id === saved.Id ? saved : character);
      renderRoster();
      renderSheet();
      showToast('Character changes saved.');
    } catch (error) {
      showToast(error.message);
    }
    return;
  }
  if (event.target.id === 'delete-character') {
    if (!window.confirm(`Delete ${state.draft.Name} from your roster?`)) return;
    try {
      await api(`/api/characters/${encodeURIComponent(state.selectedId)}`, { method: 'DELETE' });
      const next = state.characters.find((character) => character.Id !== state.selectedId)?.Id || null;
      await refreshCharacters(next);
      showToast('Character deleted.');
    } catch (error) {
      showToast(error.message);
    }
  }
});

async function start() {
  try {
    state.options = await api('/api/options');
    const raceOptions = state.options.races.map((race) => `<option value="${escapeHtml(race)}">${escapeHtml(race)}</option>`).join('');
    document.querySelector('#new-race').innerHTML = raceOptions;
    document.querySelector('#manual-race').innerHTML = raceOptions;
    document.querySelector('#manual-trait-picker').innerHTML = traitOptionMarkup();
    formStatInputs();
    configureManualTraitPicker();
    updateManualBudget();
    await refreshCharacters();
  } catch (error) {
    sheetArea.innerHTML = `<div class="empty-sheet"><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function formStatInputs() {
  document.querySelectorAll('#manual-form .manual-stats input').forEach((input) => {
    input.dataset.manualStat = input.name;
  });
}

start();