# Working on the Haunted House remaster with an AI assistant

Notes for Claude Code (or any coding assistant) working in this repository. People: the same notes are a quick
tour.

Atari 2600 *Haunted House* runs unmodified in the Stella emulator; every frame, the game's 128 bytes of RAM are
read and the scene is redrawn. It's the sister project of
[Adventure Forever](https://github.com/majonesmax/adventure-forever) (`../adventure-nes` beside this one, if you
have it), which it copies its generic pieces from. How the game was worked out:
[docs/taking-it-apart.md](docs/taking-it-apart.md); how the code fits together:
[docs/architecture.md](docs/architecture.md); everything else: [docs/README.md](docs/README.md).

## The words

- **look**: the console - colour rules, light, status line, title and win screens, and its sound chip for the
  music (`looks/`: nes, snes).
- **cast**: who - the eyes, the ghost, the bat, the tarantulas, the key, the scepter, the urn, the stairs.
- **world**: where - each floor's wall tops, faces, floor tiles and decorations, the front door, the title
  screen's mansion and moon; and a soundtrack (`music.json`).
- **pack**: a folder with a cast and/or a world (`packs/`, `private/packs/`).

Any look shows any pack. A look never knows about a particular pack, and a pack never assumes a look.

## Commands

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
python tools/get_core.py                   # the pinned Stella core (or copy cores/ from adventure-nes)
python play.py                             # play (your ROM: roms/haunted_house.a26, or drop it on the window)
python play.py --grid                      # ...in the grid: both looks, the 2600 and its live RAM
python tools/preview.py                    # the look in every situation, as one PNG - look at it
python tests/golden.py                     # every look still draws the same pixels
python tests/test_facing.py                # monsters face the way they walk
python tests/test_hints.py                 # G's hints fit the screen and point the right way
python packs/classic/source/draw.py        # regenerate the classic pack's PNGs from its text art
python packs/nocturne/source/draw.py       # ...and the nocturne pack's (the SNES look's own)
python music/chiptune.py                   # the classic soundtrack as WAVs in shots/music/, to listen to
python -m music.orchestra                  # ...and on the SNES look's orchestra
python -m music.effects                    # the remastered sound effects as WAVs in shots/effects/
python -m music.orchestral_effects         # ...and the SNES look's, played by the orchestra
python -m music.ambience                   # the house's ambience (rain, thunder, floorboards, noises) in shots/ambience/
python tests/test_events.py                # each effect fires on the right event in the running game
python tools/readme_media.py               # the README's pictures (the looks' own art only)
python play.py --check                     # the app plays itself for a few seconds and says whether it works
python package/build.py                    # the download for this system, in package/dist/ (then run it --check)
gh workflow run downloads.yml              # ...or GitHub builds Windows and macOS; a v* tag makes the release
ruff check --config ruff.toml .            # the readability rules
python tools/readability.py                # ...and no short names; no file may get harder to read (a hook runs it)
```

The research checks (`tools/verify_*.py`) prove what the RAM and ROM mean; run them after changing anything in
`game/` that they cover.

## Rules

- **Never change the game.** No ROM patches, no RAM writes during play. Looks only read a `GameState`. (The
  research lab and the preview tool poke RAM to set up scenes; play never does.)
- **Draw things where the game has them.** Positions come from RAM; the view follows the game's own camera.
- **Reveal what the original reveals.** What may be seen - the dark, the match's reach, monsters only in your
  room - is `game/visibility.py`, the original's rules. A look decides how things look, not whether they're
  seen.
- **Never commit** the ROM, the emulator core, `private/`, `reference/`, or anything from the ROM: its tables
  and graphics are read from the user's copy at run time. The sound recordings in `shots/sounds/` are from the
  ROM too.
- **Prove nothing else moved.** Run `tests/golden.py` after any change to `looks/`, `content/`, `packs/` or
  `shared/`. If only what you meant to change differs, `--update` it, and say what changed.
- **Look at your work.** After changing art, a pack or a look, run `tools/preview.py` and read the PNG before
  saying it's done.
- **Art is text.** Pack pictures are drawn as text art in the pack's `source/` and generated into PNGs. Don't
  hand-edit the PNGs.
- **Public packs are original.** No names, logos, likenesses or exact designs from someone else's work.

## Readable code

The person who owns this code reads it rather than writes it, and isn't a Python specialist. Write for them:

- **Names say what things are.** `state`, not `st`; `monster`, not `m`. Short names only for loop counters and
  coordinates (`x`, `y`, `dx`, `dy`).
- **One idea per line.** Name the steps instead of nesting calls.
- **Name the numbers.** `UNIT = 1.5` with a comment, not a bare `1.5`.
- **Short functions:** about 40 lines at most, with few branches.
- Lines up to 110 characters (`ruff.toml`).
- `tools/readability.py` checks all of this (ruff's rules and names under 3 letters) against
  `tools/readability_baseline.json` - every file is at zero; keep it there. `.claude/settings.json` runs it
  after every edit, so an assistant hears about a slip straight away.

## Style

Match the code around you: short modules with a docstring saying what they are, plain names, comments that say
why. Docs are plain English for people - short sentences, no hype words. When adding a key, add it to
`app/controls.py`.
