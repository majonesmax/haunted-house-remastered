# The screen, the switches and the sound

What a remaster needs to draw and play Haunted House the way the original does. Each part has its own check:
`tools/verify_screen.py`, `tools/verify_games.py` and `tools/verify_sounds.py`.

## Where things are drawn

The picture is 160×228. Everything is placed from its game position (x across, y up the floor) with these
rules, checked pixel for pixel by `tools/verify_screen.py`:

| | Rule |
|---|---|
| Kernel line of a y | `L = y − player y + $CB` (`$CB` is $26, mid-screen, except near the floor's top and bottom) |
| The view | lines 79 (top) down to 1: scanlines 15–171 |
| Walls and the eyes | line L starts at scanline `15 + 2 × (79 − L)`; two scanlines per line |
| Items and monsters | one scanline lower: `16 + 2 × (79 − L)`. A sprite's first ROM byte is its bottom row |
| x, for everything | pixel column = x. Sprites are 8 wide, the glow 32 |

**The walls drawn are the collision map**, pixel for pixel at five scroll positions, with one addition: a
4-pixel strip at each screen edge in the middle row (x 0–3 and 156–159), framing the front door and the side
stairs. The player can only reach x 4–155, so it's never felt.

**What you see in each game:**

- **Game 1:** the walls are always visible, in the floor's colour. Monsters show anywhere on your floor.
- **Games 2–9:** the walls are never drawn visibly, not even by a match. The floor's colour moves to the
  status line instead. A lit match shows a glow around the eyes, the items near you (light distance under
  17) and the monsters in your room. The walls are still there, drawn black and in front of the glow, so the
  glow lights only open floor and spills out through doorways. Nothing is drawn above or below your room's
  limits (`$8B`/`$8C`).
- **Lightning:** while a monster is in your room, the walls flash grey (`$0D`) on some frames. That's the
  only time you see walls in games 2–9. While you die the flashes come faster.
- **Flicker:** one item or monster is drawn per frame, in turn, and with a match lit the glow is drawn every
  other frame. The urn pieces shimmer, because their colour is taken from the frame clock.

## What the emulator does to the picture

This Stella core blends frames for Haunted House to soften the flicker. **Each colour channel shows the
larger of this frame and half of the previous picture.** That held for every pixel over 120 frames. It does
this even with its `stella_phosphor` option off. So pictures from the core have fading afterimages, and a
sprite drawn over the previous frame's glow can come out in a mixed colour. Pixel tests must allow for it:
`tools/verify_screen.py` finds sprites by the colour channels the blending can't change.

## The console switches

- **Left difficulty:** B (the default) lets lightning flash; A turns it off. That's all it does, in every
  game (checked in all nine).
- **Right difficulty:** unused.
- **Colour / B&W:** switches to the second half of the ROM's palette.
- **SELECT** steps the game number, repeating every 45 frames while held. **RESET** starts a new game.

In this Stella core, joypad button **L** sets the left switch to A and **L2** sets it back to B. The switch
stays where it's put, and **save states don't record it**, so an experiment must set it explicitly
(`tools/lab.py`: `LEFT_DIFFICULTY_A`, `LEFT_DIFFICULTY_B`).

## Sound

`game/sounds.py` is the game's sound code in Python: it gives the TIA sound registers for both channels,
every frame, from RAM. Fed to a TIA sound emulator, those registers sound exactly like the original. A
remaster can also use the events to play sounds of its own. `tools/verify_sounds.py` checks the model's
sound bytes against the game on every frame of a scene for each sound, and saves the audio to
`shots/sounds/` (from your ROM, so keep it to yourself).

| Sound | Channel | What it is |
|---|---|---|
| Monster in your room | 0 | Noise whose pitch and loudness wander at random (`$98`), then fade back to silence once it's gone |
| Dying | 0 | Thunder: noise rumbles of 16–44 frames, with a silent frame between |
| Winning | 0 | A four-note tune, 16 frames a note: 262, 276, 262, 218 Hz (roughly C, C♯, C, A). Measured in the real audio to within 1% |
| Footsteps | 1 | A click on 3 frames in 8 while the stick is pushed and no effect plays |
| Effects 2–11 | 1 | Blocked, bump, doorway, drop, pick up, urn pieces join, new room, stairs up, stairs down, urn whole: each with its own sound and length (`$93`, `$90`) |

Game 1 has no door sounds (doorway, new room, blocked at a locked door). Games 2–9 do (checked in all nine).
The same effect isn't restarted while it plays, and a bump never cuts another effect short.
