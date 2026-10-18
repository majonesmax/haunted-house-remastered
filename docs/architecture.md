# How it fits together

The game runs unmodified in the Stella emulator. Every frame, the remaster reads the game's 128 bytes of RAM
and draws the whole screen its own way. Nothing it does reaches back into the game.

## One frame

`app/window.py` runs the loop, 60 times a second:

1. **Input.** Keys become the joystick and the console's switches (`app/controls.py` lists them all), or
   window commands: change the look, the view, the sound; record; take a screenshot.
2. **The game.** One emulator frame (`game/emulator.py`, the Stella libretro core loaded with ctypes). Its
   sound goes to a ring buffer the sound card reads from.
3. **The state.** `game/state.py` turns the RAM into a `GameState`: the mode, the game number, the floor and
   room, the eyes, the matches and lives, what's carried, the five items and up to five monsters, the
   stairs, the lightning. It reads the ROM's tables from your copy (`game/rom.py`) - the mansion's plan, its
   doors, its stairs - and the RAM's meaning from `game/ram_map.py`.
4. **The pictures.** The look draws the state (`looks/`). The grid view and the recorder need the other look
   too, so it draws as well.
5. **The sound.** The soundtrack follows the moment, the sound effects follow what just happened, and the
   house's ambience fills the quiet (`music/`).
6. **Show.** The current view (`app/views.py`): the remaster beside the 2600 original, either alone, or the
   grid with the live RAM (`app/ram_panel.py`). The recorder (`app/recorder.py`) saves every look's picture.

At launch, a loading screen shows while every look's floors, every soundtrack and the ambience are made in
the background. Nothing runs in the background after that, so nothing competes with the sound card.

## Looks: the consoles

A **look** is a console: its colour rules, its light, its status line, its title and ending screens, and its
sound chip for the music. The app uses a look only through the contract in `looks/base.py`:
`draw(state, frame_no, extras)` returns a 256 x 240 picture. `extras` are what the app adds to the game:
the story at launch, and the storm's distant lightning (`shared/storm.py`).

Both looks are `FloorLook`s: they show the original's window onto the floor, scrolling with the eyes exactly
as the game's own camera does.

- `looks/layout.py`: where things go - floor units to pixels, the view's place on the screen.
- `looks/scenery.py`: each floor built once as pictures, from the ROM's wall plan: walls in 3/4 view,
  their faces and trim, shadows, decorations (some of them living: portraits' eyes, candle flames, windows
  in the lightning), the front door.
- `game/visibility.py`: the original's rules for what may be seen - the dark, the match's reach, monsters
  only in your room. A look decides how things look, never whether they're seen.
- `looks/base.py`: placing everything, the matchlight, monsters facing the way they walk, the hood and the
  hand holding the match, the floor's name as you arrive, the endings' timing.
- `looks/nes/look.py` and `looks/snes/look.py`: the platform parts - palette, light, status, title, story,
  endings. The SNES look builds on the NES one.

## Packs: who and where

What's drawn comes from a **pack** (`packs/`): a **cast** (who: the eyes, the ghost, the bat, the
tarantulas, the key, the scepter, the urn pieces, the stairs, the hood and hand) and a **world** (where: each
floor's wall tops, faces, trim, floor tiles and decorations, the front door, the title's mansion and moon),
plus a soundtrack (`music.json`). Any look shows any pack, adapting its pictures to the console's rules.
Anything a pack leaves out is the original 2600 graphic, read from your ROM (`content/original.py`).

Pack art is text: each pack's `source/` holds its pictures as text art, and `source/draw.py` turns them into
the PNGs. See [making a pack](making-a-pack.md).

## Sound

- **The soundtrack** (`music/player.py`): a piece per moment - the story, the title, a theme per floor
  (bar the attic, which is quiet), tension when a monster is in your room, jingles for a lost life, game
  over and the win. A pack's songs are written as text (`music.json`) and played on the look's sound chip:
  `music/chiptune.py` (NES) or `music/orchestra.py` (SNES).
- **The sound effects** (`music/board.py`): `music/events.py` works out what just happened from two frames
  of state - a match struck, a door, the stairs, a pick-up, the urn joining, a monster arriving, being
  caught. Each look's chip has its own set (`music/effects.py`, `music/orchestral_effects.py`). E switches to
  the 2600's own sound.
- **The ambience** (`music/ambience.py`, sounds made in `music/house.py`): rain, wind, a clock, drips,
  floorboards and the house's noises where no music plays; distant thunder with the storm's lightning
  everywhere; birdsong at dawn after a win.

## The window and its views

`app/views.py` lays out each view at its own size; the window shows it scaled to fit, keeping its shape. A
view bigger than the screen (the grid, on a laptop) opens smaller. On macOS, fullscreen keeps one window
whatever the view; elsewhere each view gets a new window.

`app/rom.py` finds your ROM, or asks for it to be dropped on a window and remembers it.

## Checking it

- `tools/preview.py` draws every look in every scripted situation as one picture; `tests/golden.py` checks
  every look still draws exactly the same pixels in them. The lab (`tools/lab.py`) sets the scenes up with
  save states and RAM pokes - only ever for checks, never in play.
- `tests/test_facing.py` and `tests/test_events.py` check monsters' facing and the sound events against the
  running game.
- The research checks (`tools/verify_*.py`) prove what the RAM and the ROM mean.
