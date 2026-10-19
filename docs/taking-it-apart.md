# How we took Haunted House apart

This is the story of how the Atari 2600 *Haunted House* (James Andreasen, 1982) was worked out, before
any remaster code was written: the methods, why we chose them, what went wrong, and what we ended up
knowing. The detail is in the other pages; this one ties them together.

The work was done by Claude (an AI model, working in Claude Code) at the direction of the project's owner,
over four requests:

1. map out the meaning of the RAM, and the parts of the ROM a remaster needs;
2. dig into how the monsters move;
3. check the rules that change with the game number;
4. answer the remaining questions (screen, switches, sound, start positions).

## The question

The sister project, [Adventure Forever](https://github.com/majonesmax/adventure-forever), remasters *Adventure* without changing the game
([how Adventure was worked out](https://github.com/majonesmax/adventure-forever/blob/main/docs/taking-it-apart.md)).
The real game runs in the Stella emulator, and every frame the remaster reads the 2600's 128 bytes of RAM and
draws the scene its own way. Graphics and maps are read from the player's own copy of the ROM. That only works
if you know what every byte means. So the question was: **can we learn Haunted House well enough to do the
same?**

## Where we started

Two things: the ROM, and Brandon Roberts' [commented disassembly](../reference/disassembly), a work in
progress last updated in 2020. It's a careful piece of work. It turns the 4K of machine code back into
assembly source that rebuilds the identical ROM, with notes on the kernel, the sprites and the playfield.
It names 13 RAM addresses, three of them `UNKNOWN`, and it lists what it hadn't found yet: the random
scattering of objects, the sound routines, and the rules behind the nine game variations.

We used it as a map. It told us where to look and what the code's author probably meant, and we checked
everything it said rather than taking it on trust. That was the first habit, and it paid off more than
once.

## The method

One loop, run over and over:

> **Read the code, write down what you think it does, predict what the running game will do, and check.**

A person would do this too. The difference here is cost. Each check is a small program that plays the real
game in the emulator, so it can run on every frame, in every game, in every room, and run again after each
correction. Checks were cheap enough to stop sampling and start covering everything. The checks also stayed
in the project (`tools/verify_*.py`), so every claim in these pages can be re-proved by running one command.

## The tools, and why each one

**A lab** (`tools/lab.py`). The emulator from the Adventure project, plus two things experiments need: *save
states*, to rewind and try again, and *RAM pokes*, to set up a scene fast (put an item next to the player,
send a monster into the room). Pokes only set a scene up. What gets checked is always what the game does
next. A remaster must never poke the game, and this one won't.

**Our own tracer** (`tools/xref.py`). Instead of trusting the disassembly's split of code from data, a small
6502 tracer follows every jump and branch from the reset vector. It found 1,797 instructions in 3,446 bytes of
code, and 650 bytes of data (tables, sprites, the wall plan). That matched the disassembly exactly, which made
its addresses trustworthy. The tracer also lists, for every RAM byte, every instruction that reads or writes
it. That table ([generated/ram-xref.md](generated/ram-xref.md)) is where most guesses started.

**Decoders that draw what they decode** (`game/rom.py`, `tools/rom_sheet.py`). Every table we decoded is drawn
into a picture: the sprites, the palette, the plan of each floor with its doors and stairs. A wrong guess about
a table usually looks wrong. One picture answered a question the disassembly had wrong: its README draws the
urn upside down. A frame from the running game showed which way up it really is, and that settled how all the
sprites are stored.

**Claims checked one by one** (`tools/verify_ram.py`, 65 claims). "RESET sets 9 lives." "Walking into the
bottom edge of room 0 takes the stairs up." "A monster in your room blows out the match." Each claim is a scene
and a test. Every byte the RAM map marks as *live* is backed by one of these.

**Models that predict the game frame by frame** (`game/monsters.py`, `game/sounds.py`). This is the strongest
evidence we have. For the monsters, the game's code was rewritten in Python. Then the real game and the model
ran side by side: after every frame, the model gets the RAM from before the frame and must produce exactly the
bytes the game wrote. It got all 30,000 frames right, across five games, through chases, catches, stairs,
locked doors and monsters following the player. You can't predict 30,000 frames by luck. Getting every byte
right means we know what every byte means.

**Breaking the model on purpose.** A check that always passes proves nothing. So the monster model was broken
seven ways, one rule at a time (no following, wrong speeds, the scepter ignored, and so on), to make sure the
check failed each time. Six breaks were caught at once. The seventh wasn't, which showed the test bot never
happened to summon the two monsters that rule affects. The bot was changed to summon them in turn, and then
the check caught that break too.

**A bot, scene setups, and counting what happened** (`tools/verify_monsters.py`). Random play misses rare
events. The first clean run turned out never to have tested monsters following the player at all, and the
only reason we noticed is that the harness counts what happened. So the bot was given errands: walk the game's
own waypoints out through a door, with a monster just behind. The final run covers 470 door crossings, 180
monster stair trips, 26 catches, and 28 times monsters followed the player out of a room. It also covers 31
times in games 1 and 3 where a monster was in the room and correctly did *not* follow.

**Sweeps of everything** (`tools/verify_games.py`, 153 checks). The rules that change with the game number
were checked in all nine games, not a sample: every door on every floor with and without the key, every room's
stairs, walking down every stairway, and where items start after RESET.

**Pixel checks** (`tools/verify_screen.py`). Where things are drawn, as formulas, checked pixel for pixel:
the walls on screen match the collision map exactly at five scroll positions.

## What went wrong, and how it was caught

Most of the time when a check failed, the check was wrong. Sometimes the game was doing something we didn't
expect. The only way to tell which is to look closer, and several real discoveries came out of failed
checks.

| What happened | What it really was |
|---|---|
| The match timer seemed stuck | A **real quirk**: the per-second counter is never reset, so the first match after RESET lasts about 4 seconds longer. |
| A test item stayed invisible next to the player | A **real rule**: items show only within a light distance under 17, and the test had put both items at exactly 17. |
| Door sounds were missing in the sound test | A **real rule**: game 1 has no door sounds. |
| The wall check ran forever | The model, not the game: it didn't know the player stops at the floor's edges. |
| Every top and bottom stairway "failed" in all nine games | The test, not the game: it walked straight into a wall on the way. |
| Both shoulder buttons seemed to turn lightning off | The test: the emulator keeps switch positions outside save states, so each experiment inherited the last one's switch. A fresh process per test gave the real answer: only one button does. |
| Sprites seemed to lag a frame, then to be clipped beside the eyes | The emulator, not the game: Stella blends each picture with half of the previous one. One odd pink pixel gave the exact rule away. This wrong theory survived several experiments. |
| Sound effect 6 was labelled "caught" | A misreading of the code. Rereading it showed it's the pick-up sound. |
| A mutation of the model went undetected | The test bot never summoned the monsters that rule affects. |

Without the checks, at least four of these wrong ideas would be in the documentation now, stated with
confidence.

## What we know now

- **The RAM:** all 128 bytes have a name and a meaning, each marked by how sure we are: 46 entries checked in
  the running game, 18 read from the code (mostly the drawing kernel's scratch bytes and the CPU stack). See
  [generated/ram-xref.md](generated/ram-xref.md).
- **The world:** four floors with one shared wall plan, six rooms each, seven doors, locks per floor, stairs
  per floor, and game 9's own layout. All of it is read from the ROM, and every door and stairway is checked
  in every game. See [rom-elements.md](rom-elements.md).
- **The cast:** every sprite, colour and animation, read from the ROM. See [rom-elements.md](rom-elements.md).
- **The monsters:** how they wander a network of waypoints, chase, follow you, and are scattered, down to
  the order of arrivals within a frame. See [monsters.md](monsters.md).
- **The rules of all nine games:** confirmed live, as one table. See [rom-elements.md](rom-elements.md).
- **The screen and the sound:** where everything is drawn, what each game lets you see, the switches, every
  sound effect, and the win tune's notes measured in the real audio. See
  [screen-and-sound.md](screen-and-sound.md).

What's left unchecked is small, and says why: two blocks the kernel places in the middle wall's gap that
never show in play, and the B&W palette.

## How this compares with the disassembly

They answer different questions, and each needs the other.

| | The disassembly | This project |
|---|---|---|
| Answers | *What is the code?* | *What does the game do, and what does each byte mean?* |
| Form | Commented assembly that rebuilds the ROM byte for byte | Python models, decoders, a RAM map, and plain-English pages |
| RAM | 13 addresses named, 3 marked unknown | All 128 bytes, each with a meaning and a level of certainty |
| Evidence | The author's reading of the code | Each claim checked against the running game; the models predict it frame by frame |
| Open questions it listed | The scatter, the sounds, the game variations | Each one answered and checked |
| Best for | Changing the game, building a new ROM, studying the kernel's timing | Remastering it, porting it, explaining it |

We couldn't have moved this fast without the disassembly as a starting map. In return, a few of its notes are
now known to be wrong or incomplete: the urn's orientation, the floor range (0–3, not 0–4), the three unknown
bytes, and the missing routines. Those corrections could go back to that repository as an issue or pull
request, if the owner of this project wants to offer them.

## Was this an AI doing something a person couldn't?

No: every method here is one a careful person would use, and the steps are the logical ones. Three things are
different in practice.

- **Iterations are cheap.** A new tracer, a 30,000-frame comparison, or a sweep of 252 door walks is a few
  minutes' work, so nothing had to be sampled. When a check failed, the next idea could be tested at once.
- **Reading a whole program at once.** All 2,800 lines of the disassembly could be held in mind together.
  That's how, for example, the parallel position tables 11 bytes apart were spotted on the first read.
- **Throwaway tools.** About 2,900 lines of Python were written for this. Many one-off scripts were written and
  thrown away along the way, which a person would think twice about.

And the limits:

- **The guesses were often wrong at first.** What made the results reliable was the habit of predicting and
  checking, not the reading.
- **No direct eyes or ears on the game.** The game was seen through screenshots and pixel tests, and heard
  through frequency measurements of recorded audio. Nobody watched it play.
- **The direction came from the person.** What mattered (keeping the look, the world and the cast), which
  question to take next, and when it was good enough to move on.

## What it means for the remaster

The remaster can work the way Adventure Forever does. The game runs unchanged; each frame we read RAM, take
the walls and sprites from the ROM, and draw. One thin layer decides what the player is allowed to see:
darkness, the reach of the match, monsters only in your room. Those rules are written down here and checked.
The models of monster movement and sound aren't needed to play. They stay as tests: if the remaster ever draws
something in the wrong place, they tell us whether the mistake is in our reading of the RAM or in our drawing.

## Could this be done without the disassembly?

Yes. Two different things get called "the disassembly", and only one is essential:

1. **The ROM's machine code, turned back into readable instructions.** That's mechanical. `tools/xref.py` does
   it from the raw ROM in about 200 lines, and long-standing tools do it too: Stella's built-in debugger and
   dedicated 2600 disassemblers such as Distella. This part is essential, and it's the easy part.
2. **A person's comments and labels on top.** That's the valuable human work in Brandon Roberts' repository.
   Here it gave orientation: about a dozen RAM labels, notes on the screen-drawing code, and a guess at the
   random number generator. That saved an hour or two. The parts that mattered most (the monster plans, the
   door, lock and stairs tables, the rules of the nine games) were uncommented, and came from reading the
   instructions and testing.

It was easy here for specific reasons. The cartridge is 4K with no bank switching, every jump goes to a fixed
address, and the tracer needed only one special case: branches that always go the same way, used as short
jumps. Bigger 2600 games swap banks of ROM in and out, some jump through tables of addresses, and some use
undocumented instructions. Those take more care, with known techniques.

Neither half works alone. Watching RAM finds the obvious bytes (positions, lives, the floor) but not why they
change, the quirks behind them, or anything RAM never holds, such as the sound registers. Reading the code
without checking leaves confident mistakes, as the table of wrong ideas above shows.

**The minimum kit:**

- the ROM
- an emulator you can read RAM from, with save states (and RAM writes, for setting up scenes)
- a disassembler: write one or use an existing one

**A useful extra:** a debugger that can stop the game when a byte is written and show which instruction wrote
it. Stella has one. The emulator core used here doesn't expose it, so we compared RAM before and after each
frame instead. With one, finding which routine changes a byte would be a single step.

## Running the checks yourself

With your own ROM at `roms/haunted_house.a26`, the emulator core in `cores/`, and the environment from the README:

```sh
.venv/bin/python tools/xref.py            # trace the ROM, regenerate docs/generated/
.venv/bin/python tools/rom_sheet.py       # draw the sprites and floor plans into shots/
.venv/bin/python tools/verify_ram.py      # 65 claims about RAM and the ROM tables
.venv/bin/python tools/verify_games.py    # 153 checks across all nine games
.venv/bin/python tools/verify_monsters.py # the monster model, 30,000 frames
.venv/bin/python tools/verify_sounds.py   # the sound model, and the win tune's pitch
.venv/bin/python tools/verify_screen.py   # where things are drawn, pixel for pixel
```
