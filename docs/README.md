# A guide to the documentation

What's written down, and where to start for what you want to know.

## Playing

- **[The README](../README.md)**: what this is, how to run it, the keys.
- **In the game, H twice**: what you're trying to do, and the rules the original never explains
  (`game/guide.py`). Each game number's rules show on the title screen.
- **[Reading the RAM](reading-the-ram.md)**: the grid view's INTERNALS pane - the game's 128 bytes, live.

## How the game works (the research)

The research came first: what every byte of RAM means, what's in the ROM, and how the game works, each claim
checked against the running game.

- **[How we took Haunted House apart](taking-it-apart.md)**: start here. How the game was worked out, the
  methods and why, what went wrong, and how it compares with the commented disassembly.
- **[What's in the ROM](rom-elements.md)**: everything in the ROM, grouped by look, world, cast and rules.
- **[The screen, the switches and the sound](screen-and-sound.md)**: where everything is drawn, what each
  game shows, the switches, and every sound - with the emulator's frame blending explained.
- **[How the monsters move](monsters.md)**: how they wander, chase, follow you and get scattered - checked
  by a model that predicts the real game frame for frame.
- **[The ROM's layout](generated/rom-layout.md)**: which bytes are code and which are data (generated).
- **`game/ram_map.py`**: all 128 bytes of RAM - each one's name, meaning, and how sure we are. Run
  `python tools/xref.py` for `docs/generated/ram-xref.md`, which adds every instruction that reads or writes
  each byte (it's made from your ROM's code, so it isn't published).

In short: the player is a pair of eyes on one of four floors. Each floor is a single tall map that scrolls,
with six rooms joined by seven doors and stairs at the outer edges. The positions of the player, the five
items and up to five monsters sit in parallel tables in RAM ($A0-$C9). The urn is three pieces that join
into one; carry the whole urn out of the front door to win.

## How the remaster works (the code)

- **[How it fits together](architecture.md)**: a frame from start to finish, the look contract, packs,
  sound, and the window.
- **[Making a pack](making-a-pack.md)**: a cast, a world and a soundtrack of your own.
- **[CLAUDE.md](../CLAUDE.md)**: the words, the commands and the rules for working on it - for people and
  AI assistants alike.
- **[TODO.md](../TODO.md)**: what's been done, and what's next.

## The tools

Run each with Python from the repository's root.

| Command | What it does |
|---|---|
| `play.py` | plays the game (`--look`, `--pack`, `--grid`) |
| `tools/preview.py` | every look in every scripted situation, beside the original, as one picture in `shots/` |
| `tests/golden.py` | every look still draws exactly the same pixels in those situations (`--update` after a change you meant) |
| `tests/test_facing.py` | monsters face the way they walk |
| `tests/test_events.py` | each sound effect fires on the right event in the running game |
| `tools/verify_ram.py` | plays scripted experiments and checks each claim about RAM and the ROM's tables |
| `tools/verify_games.py` | checks every rule that changes with the game number, in all nine games |
| `tools/verify_screen.py` | checks where walls, eyes and sprites are drawn, pixel for pixel |
| `tools/verify_sounds.py` | checks the sound model frame by frame, and measures the win tune's pitch |
| `tools/verify_monsters.py` | runs the game beside `game/monsters.py` and checks it predicts every monster byte, every frame |
| `tools/monster_paths.py` | draws the monsters' waypoints and the paths they really walked |
| `tools/xref.py` | traces the ROM's code; regenerates `docs/generated/` |
| `tools/rom_sheet.py` | draws the ROM's sprites, palette and floor plans into `shots/` (from your ROM - not published) |
| `tools/lab.py` | the lab the others use: the emulator plus save states and RAM pokes, for experiments |
| `tools/readme_media.py` | the README's pictures |
| `packs/<pack>/source/draw.py` | turns a pack's text art into its PNGs |
| `python -m music.chiptune`, `music.orchestra` | the soundtrack as WAVs in `shots/music/`, to listen to |
| `python -m music.effects`, `music.orchestral_effects`, `music.ambience` | the sound effects and the house's sounds as WAVs |
| `python -m app.recorder <folder>` | turns a recording's RAM into a video of the INTERNALS pane |

Pokes are for experiments only. A remaster never writes the game's RAM while someone plays.

## Sources

- Brandon Roberts' commented disassembly of Haunted House (a work in progress; our own trace and experiments
  correct it in places, noted in [rom-elements.md](rom-elements.md)). It isn't included here.
- The running game, through the tools above.
