# To do

What's next for the remaster, roughly in order. Tick items off as they're done.

## 1. Help new players understand what's happening

- [x] **How to play**, in the game: the goal (find the three urn pieces, join them, carry the whole urn out
      of the front door) and the rules the original never explains - a match shows only what's near, monsters
      blow it out, the scepter keeps them off, the key opens locked doors, stairs are at the rooms' edges
- [x] **Explain each game on the select screen**: what game 1-9 change (dark or not, locked doors, how many
      monsters, monsters that follow, the bat stealing, the fearless ghost, game 9's different house)
- [x] **A floor banner on the stairs**: "THE DINING HALL - FLOOR 2" for a moment as you arrive
- [x] **A short intro**: the story in a few lines before the title

## 2. Make the house feel alive

- [x] Candles flicker; windows flash with the lightning; dust in the SNES match light
- [x] Portraits whose eyes follow you
- [x] An ambient soundscape: distant thunder (and its lightning) under the music; where it's quiet - the
      attic, the story once its music ends - rain, floorboards underfoot, and the house's noises when you
      stand still
- [x] Livelier monsters: the bat's three-frame flap; tarantulas' legs move only while they walk

## 3. A proper ending

- [x] The win: the mansion at dawn, the urn whole, the eyes walking away, your score in matches
- [x] Game over: the window going dark

## 4. Finish the SNES layer

- [x] Orchestral sound effects (made from the orchestra's own voices)
- [x] An art pass: the hood, and how much of the floor shows in moonlight

## 5. Show it off, as Adventure Forever does

- [x] The four-way grid view: your game, the other look, the 2600 original and a live RAM panel with an
      event log
- [x] Recording; dropping your ROM on the window
- [x] A README, and a guide to all the documentation (docs/README.md)
- [x] Packaged downloads: package/build.py, as Adventure Forever's, with the same pinned Stella core
- [x] The Windows download, built by GitHub (.github/workflows/downloads.yml)
- [x] The first release, v1.0: both downloads built and run (--check) by GitHub
- [x] A captioned playthrough video (tools/make_video.py), on YouTube and linked from the README

## 6. What playing it taught us (v1.1)

- [x] **G for a hint**: which way to the nearest piece, how to take it, and with the whole urn, which way
      to the front door; a reminder when the urn comes together that it isn't won yet
- [x] **O to turn the lights on** - a cheat, for seeing where everything is (you still need a match to
      pick things up)
- [x] **Urn pieces you can find**: broken across instead of down the middle, and glinting now and then
- [x] **Say how to pick things up**: walk into them with a match lit (help, hints, README "How to play")
- [x] Fix: losing the last life holding the whole urn showed the win's ending
- [x] Fix: the sound stuttered walking out of the front door (the NES look's fade)

## 7. Code anyone can read

- [x] tools/readability.py at zero, run by a hook after every edit (as in Adventure Forever)
- [x] Type hints on every signature (shared/types.py), checked by pyright, required by ruff's ANN rules
- [x] GitHub runs the checks on every push (.github/workflows/checks.yml)

## Maybe later

- [ ] Brighter urn pieces in the SNES look, if they're still hard to spot on its checkered floor
- [ ] pyright's stricter "standard" mode
- [ ] Proper types for songs and pack.json (TypedDicts instead of "a dict of anything")

## Housekeeping

- [x] Merge the `feel` branch into `main`
