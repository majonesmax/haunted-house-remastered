# Haunted House, remastered

Atari 2600 *Haunted House* (James Andreasen, 1982) running *unmodified* in the Stella emulator, with every
frame redrawn live from the game's 128 bytes of RAM, in the spirit of [Adventure Forever](../adventure-nes).
Two looks, with the 2600 original alongside: **NES**, an 8-bit remaster, and **SNES**, a 16-bit one - smooth
warm matchlight, moonlit walls, a see-through ghost, art in 16-bit colour ramps, and the soundtrack on a
small gothic orchestra. L switches between them while you play.

The research came first: what every byte of RAM means, what's in the ROM, and how the game works, each claim
checked against the running game. That's below, under *What we know*.

## Playing it

You need your own copy of the ROM at `roms/haunted_house.a26`, and the Stella emulator core in `cores/`
(`python tools/get_core.py` downloads the pinned one, or copy it from `../adventure-nes/cores`).

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python play.py
```

| Key | |
|---|---|
| Arrows, Space | the joystick: move; light a match (with one lit, drop what you carry) |
| Tab / Enter | GAME SELECT / GAME RESET |
| L | the next look: NES or SNES (each with its own pack, and its own sound chip for the music) |
| D | the left difficulty switch: lightning on (B, the default) or off (A) |
| M | the soundtrack on or off |
| E | the sound effects: remastered (the default) or the original 2600 sound |
| V | view: side by side, remaster only, 2600 only |
| P / S / F / H / Esc | pause, screenshot, fullscreen, help, quit |

How it's built: the game runs in `game/emulator.py`; `game/state.py` turns its RAM into a `GameState`;
`game/visibility.py` holds the original's rules for what may be seen; a look in `looks/` draws it, with a
pack's cast and world from `packs/` (the original 2600 graphics for anything a pack leaves out). A pack's
soundtrack (`music.json`, original chiptune) is rendered by `music/chiptune.py` and follows the game
(`music/player.py`): a theme per floor, tension when a monster is in your room, jingles for a lost life, game
over and the win. The game's own sound effects are replaced by remastered ones (`music/effects.py`) that
say what happened - a match striking, a door creaking, steps going up or down the stairs, a key's jingle -
worked out from the game's state (`music/events.py`); E brings back the original 2600 sound. The rules for
working on it are in [CLAUDE.md](CLAUDE.md).

## What we know

- **[docs/taking-it-apart.md](docs/taking-it-apart.md)**: start here. How the game was worked out, the
  methods and why, what went wrong, and how it compares with the disassembly.
- **[docs/generated/ram-xref.md](docs/generated/ram-xref.md)**: all 128 bytes, each with its name, meaning,
  how sure we are, and every routine that reads or writes it. Generated from `game/ram_map.py`.
- **[docs/rom-elements.md](docs/rom-elements.md)**: everything in the ROM, grouped by look, world, cast and
  rules, plus what's still to learn.
- **[docs/screen-and-sound.md](docs/screen-and-sound.md)**: where everything is drawn, what each game shows,
  the switches, and every sound - with the emulator's frame blending explained.
- **[docs/monsters.md](docs/monsters.md)**: how the monsters wander, chase, follow you and get scattered -
  checked by a model that predicts the real game frame for frame.
- **`shots/rom_cast.png`** and **`shots/rom_mansion.png`**: every sprite, and the plan of every floor, drawn
  from the ROM's own tables.

In short: the player is a pair of eyes on one of four floors. Each floor is a single tall map that scrolls,
with six rooms joined by seven doors and stairs at the outer edges. The positions of the player, the five
items and up to five monsters sit in parallel tables in RAM ($A0–$C9). The urn is three pieces that join
into one; carry the whole urn out of the front door to win.

## Tools

Run with `.venv/bin/python`:

| Command | What it does |
|---|---|
| `tools/verify_ram.py` | Plays scripted experiments and checks each claim about RAM and the ROM tables (65 so far) |
| `tools/verify_games.py` | Checks every rule that changes with the game number, in all nine games (153 checks) |
| `tools/verify_screen.py` | Checks where walls, eyes and sprites are drawn, pixel for pixel, against the formulas |
| `tools/verify_sounds.py` | Checks `game/sounds.py` frame by frame, measures the win tune's pitch, saves each sound to `shots/sounds/` |
| `tools/verify_monsters.py` | Runs the game beside `game/monsters.py` and checks it predicts every monster byte, every frame |
| `tools/monster_paths.py` | Draws the monsters' waypoints and the paths they really walked into `shots/monster_paths.png` |
| `tools/xref.py` | Traces the ROM's code; regenerates `docs/generated/` |
| `tools/rom_sheet.py` | Draws the ROM's sprites, palette and floor plans into `shots/` |
| `tools/lab.py` | The lab the others use: the emulator plus save states and RAM pokes, for experiments |
| `tools/preview.py` | The look in twelve scripted situations, beside the original, as one picture |
| `tests/golden.py` | Every look still draws exactly the same pixels in those situations |

Pokes are for experiments only. A remaster must never write the game's RAM while someone plays.

## Sources

- `reference/disassembly`: Brandon Roberts' commented disassembly (a work in progress; our own trace and
  experiments correct it in places, noted in `docs/rom-elements.md`).
- The running game, through `tools/verify_ram.py`.
