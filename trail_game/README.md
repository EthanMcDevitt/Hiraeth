# The Emberroad

A small, standalone fantasy trail game that uses characters saved by the Character Workshop in the parent project.

Run the existing Character Workshop on port 5000, then start this subproject from the repository root:

```powershell
python trail_game\app.py
```

Open <http://127.0.0.1:5001>. The game reads the shared `characters.json` archive and saves the current journey in the browser's local storage.
