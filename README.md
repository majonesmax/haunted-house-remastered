# Haunted House, remastered

![The same moment in the two looks: the NES remaster and the SNES remaster](docs/media/looks.png)

Atari 2600 **Haunted House** (James Andreasen, 1982) running *unmodified* in an emulator, with every frame
redrawn live from the game's 128 bytes of RAM. It's the sister project of
[Adventure Forever](https://github.com/majonesmax/adventure-forever), and works the same way.

Two **looks**, and **L** switches between them while you play:

- **NES**: an 8-bit remaster. A Victorian manor in the NES's 64 colours, a matchlight that dithers into the
  dark, and a gothic chiptune soundtrack.
- **SNES**: a 16-bit remaster. Smooth warm matchlight with dust drifting in it, moonlit walls, a see-through
  ghost, art in 16-bit colour ramps, and the soundtrack and sound effects on a small gothic orchestra.

Both bring the house to life without changing the game: portraits whose eyes follow you, candles that flicker,
a storm outside, rain and creaking floorboards in the quiet attic, a story at the start, and a real ending -
dawn behind the mansion as you walk away with the urn.

The original 2600 picture can run alongside, and a **four-way grid** shows your game, the other look, the
original, and the game's live RAM at once - every byte, what it means, and a log of what happened
([how to read it](docs/reading-the-ram.md)). Gameplay is 100% the original: the emulator runs the real game,
and the remasters only *draw* it.

![The ending, in both looks](docs/media/endings.png)

## Playing it

Needs Python 3.10 or newer, and your own copy of the game (the ROM isn't included).

```sh
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python tools/get_core.py               # downloads the Stella emulator core for your system into cores/
python play.py                         # drop your ROM onto the window the first time; it's remembered
```

**Which ROM:** the NTSC cartridge of Haunted House (Atari CX2654), MD5 `f0a6e99f5875891246c3dbecbf2d2cea`.
Everything here was worked out and checked on that one.

More: `python play.py --look snes`, `--grid`, `--pack <name>`, `--help`. Recording (R) needs
[ffmpeg](https://ffmpeg.org). On Linux, sound needs your distribution's PortAudio (e.g. `libportaudio2`).

New to the game? Press **H** twice in the game: what you're trying to do, and the rules the original never
explains. Each game number's rules show on the title screen.

## Controls

In the game, **H** shows all of these.

| Key | |
|---|---|
| Arrows | move |
| Space | light a match; with one lit, put down what you carry |
| Tab / Enter | GAME SELECT (games 1-9) / GAME RESET (start) |
| L | the next look: NES or SNES (each with its own pack and its own sound chip) |
| V | view: side by side with the 2600 -> the remaster alone -> the 2600 alone -> the grid |
| M | the soundtrack on or off (off leaves the house's own sounds) |
| E | sound: remastered (the default) or the original 2600 sound |
| D | the left difficulty switch: lightning on (the default) or off |
| R | record (videos of each look and the 2600, the sound, the RAM, a log) |
| S / P / F | screenshot / pause / fullscreen |
| H | the keys, then how to play |
| Esc | quit |

## How it works

The 2600 has no screen memory. Everything about the game - which floor and room you're in, where the five
items and five monsters are, what you carry, how long the match has left - lives in 128 bytes of RAM. Every
frame we read that RAM through the libretro API and draw our own picture from it, using the ROM's own wall
plan and tables, read from your ROM at run time. The remasters can't change how the game plays, and what
they show follows the original's own rules for what may be seen in the dark.

| Folder | What's in it |
|---|---|
| `game/` | the game itself: the emulator, the RAM map, the ROM's tables, the game's state (`GameState`), the rules for what can be seen, a Python copy of the monster code |
| `looks/` | how it's drawn (the consoles): the look contract (`base.py`), the floor in 3/4 view (`scenery.py`), the NES and SNES looks |
| `content/` | what's drawn: casts (who) and worlds (where), loaded from packs |
| `packs/` | the packs: `classic` (the NES look's) and `nocturne` (the SNES look's), each drawn as text art in `source/` |
| `music/` | the soundtrack (chiptune and orchestra synths), the sound effects, the ambience, and what triggers them |
| `app/` | the window: views, the grid's RAM pane, recording, the ROM |
| `shared/` | pixel-art helpers, palettes, the pixel font, the storm |
| `tools/` | the research checks, the preview, the art and media pipelines |
| `tests/` | pixel-exact "golden" tests of every look, and checks of facing and sound events |

**[A guide to all the documentation →](docs/README.md)**, starting with
[how the game was taken apart](docs/taking-it-apart.md) and [how the code fits together](docs/architecture.md).

## Working on it

The rules for working on it, for people and AI assistants alike, are in [CLAUDE.md](CLAUDE.md): the words
(look, cast, world, pack), the commands, and the rules - never change the game, draw things where the game has
them, reveal only what the original reveals, art is text, and prove nothing else moved.

```sh
pip install -r requirements-dev.txt
python tools/preview.py                # every look in every situation, as one picture - look at it
python tests/golden.py                 # every look still draws exactly the same pixels
ruff check --config ruff.toml .        # the readability rules
```

## Licence

The code is MIT ([LICENSE](LICENSE)); the art in `packs/` is CC BY 4.0 ([LICENSE-ASSETS.md](LICENSE-ASSETS.md)).
Not included: Haunted House itself (© 1982 Atari) - bring your own ROM - and the Stella emulator core (GPL-2.0,
downloaded by `tools/get_core.py`).
