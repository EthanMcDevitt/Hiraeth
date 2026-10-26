# The Emberroad (Pygame)

An independent desktop version of the fantasy trail game, built with Python and Pygame. It reads characters from the parent project's `characters.json`; journey saves are kept in this folder as `journey.json`.

From the repository root, install the dependency and launch:

```powershell
py -m pip install -r emberroad_pygame\requirements.txt
py emberroad_pygame\main.py
```

The game supports selecting a saved character, traveling through six encounter-filled legs, stat checks, foraging, resting, and resuming a locally saved journey. Its early storybook-style graphics are drawn directly with Pygame, including a traveling wagon and distinct river, beast, rockfall, and peddler scenes. Use the mouse for choices and Escape to quit.
