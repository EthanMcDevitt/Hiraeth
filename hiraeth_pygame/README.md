# Hiraeth

A storybook-style, turn-based fantasy journey built with Pygame. Hiraeth uses characters saved by the parent Character Workshop in `characters.json`; it saves the current journey to `hiraeth.json` in this folder.

From the workspace root, install the dependency and launch:

```powershell
py -m pip install -r hiraeth_pygame\requirements.txt
py hiraeth_pygame\main.py
```

Create characters from the opening menu with dropdowns for races and traits from the shared character catalog, plus the available sex options; or choose a distinct party of one to four saved characters. Character cards on the road open an overview of attributes, derived values, traits, and notes. The journey tracks **Supply**, **Wealth**, and **Reputation** separately.

Choose **Begin the journey** for the staged adventure or **Sandbox adventure** to explore a configurable ASCII map with the arrow keys or on-screen cardinal-direction buttons. In sandbox mode, `#`, `~`, and `^` are blocked by default; change the map, start coordinates, blocked symbols, and legend in the configuration.

During a session, choose **Quit to menu** to save and return later, delete the saved session, or keep playing. A saved session appears on the opening menu as **Resume saved session**; it is not automatically resumed when the game launches.

Game content and balance live in **`game_config.json`** next to `main.py`; edit it with any text editor—no Python changes are needed. You can change:

- `journey`: travel-day stage count, starting resources, wilderness and town upkeep, combat/event chances, settlement names and levels, and independently configurable minimum/maximum travel distances between towns and waystations.
- `combat`: attack damage, constitution mitigation, guard mitigation, and minimum damage.
- `sandbox`: map rows, start coordinates, blocked terrain, legend, and movement text.
- `monsters`: add, remove, rename, or rebalance monsters using `name`, `description`, `health`, `attack`, and `defense`.
- `events`: add or rewrite events and their choices. Each choice has a `label`, `result`, and integer `supply`, `wealth`, and `reputation` changes. Events support one to four choices and require a positive integer `rarity` weight; higher weights make an event more likely when an event roll succeeds. `journey.event_chance` sets the per-travel-day event probability separately from `combat_chance`.
- `text`: change the opening copy, journey and combat descriptions, button labels, endings, and journal messages. Keep the existing `{placeholders}` in formatted messages.

The game checks the configuration at startup and reports invalid values or missing fields. `README.md` describes how to launch the game; `config.py` validates and loads the editable JSON, while `main.py` handles gameplay.

## Rules, equipment, and inventory

Open **Inventory** from the road or a character overview to browse the rules catalog. The party shares Wealth and a common stash; each character also has a personal inventory with Strength-based carrying capacity (encumbrance begins above Strength, and carrying more than twice Strength is not allowed). Items can be bought for Wealth, moved between the stash and characters, and weapons or armor can be equipped. Spell knowledge belongs to individual characters; learning is free, while casting spends Magica.

Journeys begin in a town and then alternate between waystations and towns. Each travel day consumes the configured wilderness Supply cost; the distance to each next stop is randomly generated from `journey.distance`. Towns sell equipment and charge the configured Wealth upkeep only when the party chooses **Rest in town**; shopping and resupply do not incur that upkeep. Town trade access depends on settlement level plus party Reputation; towns refuse resupply at Reputation -3 or lower. Both towns and waystations exchange 1 Wealth for `max(1, supply_per_wealth_base + Reputation)` Supply, and waystations never refuse resupply for low Reputation.

Combat is round-based: choose one move for every living party member, choose a target for attacks or spells, then lock the plan. The party's moves resolve together before the enemies take their turn. Characters without Shei ancestry or Sorcery rank 5 have a maximum spell capacity of zero; eligible characters can know up to their Willpower modifier in spells, and Shei gain one additional spell slot from their Magical Bloodline. Human characters have a `62 + (2 × level)` point budget for Ambitious; other ancestries use `60 + (2 × level)`. The creator includes selected traits in that budget, and the character sheet shows spell capacity and recorded ancestry features. Outside combat, cast learned ally-target spells from Inventory and select a party member as the target.

The included catalog draws from the supplied rules references: weapons use their listed damage dice and attack attributes, armor/helmets/shields provide breakable Armor Points, and guard improves defense. Encumbered characters roll checks with disadvantage. Spells provide a selection of combat healing, protection, control, and damage effects. During camp, choose one recovery per character (Health, 2d4 Magica, or 2d6 Stamina); broken Armor Points can also be repaired by rolling above the armor's base AP on a d6. The catalog currently includes representative gear and spells; descriptions preserve their reference traits for the game master/player.

Edit **`rules_catalog.json`** to change the available weapons, armor, adventuring gear, and spells. Each item has a stable `id` and display `name`; Wealth costs for gear are Hiraeth's configurable defaults, while a spell's `cost` is its casting cost in Magica. Weapon entries also define damage dice, damage type, range, attack attribute, and reference traits. Armor entries define their kind, AP, inventory slots, and traits. Spell entries define school, target, effect summary, and Magica cost. Existing save files are upgraded with empty inventories and default equipment when resumed.
