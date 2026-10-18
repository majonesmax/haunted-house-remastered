"""The soundtrack, following the game: which piece plays when, mixed under the 2600's own sound.

The pack's songs (music/chiptune.py renders them, once) are named by the moment they're for:
    title       game select              floor1-4    walking a floor
    tension     a monster in your room   dying       a life lost (once)
    game_over   the last life lost (once) win        the urn out of the front door (once)

The game loop calls follow(state) each frame; the sound card's callback calls mixer(samples)
(game/emulator.py, AudioOut(mixer=...)), which adds the music to the game's sound. Each looping piece
keeps its place, so a floor's theme carries on where it was after a monster has gone. A pack without
music.json plays no music.
"""

import threading

import numpy as np

from music import chiptune, orchestra

SYNTHS = {"chiptune": chiptune, "orchestra": orchestra}   # a look's sound chip (Look.synth) -> its synth

CALM_FRAMES = 120   # the tension music keeps on this long after the last monster has left the room
KNEE, TOP = 28000.0, 32767.0  # mixing: above the knee, peaks are rounded off instead of clipping


def moment(state):
    """Which piece belongs to this moment of the game."""
    if state.mode == "select":
        return "game_over" if state.lives == 0 else "title"
    if state.won:
        return "win"
    if state.mode == "dying":
        return "dying"
    if state.monsters_here:
        return "tension"
    return f"floor{state.floor + 1}"


class Piece:
    """A rendered song, played from memory: loops, or plays once."""

    def __init__(self, samples, loop):
        self.samples, self.loop, self.position = samples, loop, 0

    def render(self, count):
        out = np.zeros((count, 2), np.int16)
        done = 0
        while done < count:
            if self.position >= len(self.samples):
                if not self.loop:
                    break
                self.position = 0
            take = min(count - done, len(self.samples) - self.position)
            out[done:done + take] = self.samples[self.position:self.position + take]
            done += take
            self.position += take
        return out


class MusicPlayer:
    """A pack's songs, played on a look's sound chip ("chiptune" for the NES, "orchestra" for the SNES).

    The songs are rendered in the background, the title and first floor first, so making a player costs
    nothing; a piece that isn't ready yet starts as soon as it is."""

    def __init__(self, songs, synth="chiptune"):
        self.songs = songs
        self.synth = SYNTHS[synth]
        self.rendered = {}       # name -> its samples, as the background renders them
        self.loops = {}          # name -> its Piece, kept so it resumes where it was
        self.lock = threading.Lock()
        self.current = None
        self.playing = None
        self.calm_for = 0
        self.on = True
        self.paused = False      # the window's pause: the music waits too
        self.waiting = False     # the piece wanted isn't rendered yet
        threading.Thread(target=self.render_all, daemon=True).start()

    def render_all(self):
        """In the background: every song, those heard first first."""
        first = [name for name in ("title", "floor1") if name in self.songs]
        rest = [name for name in self.songs if name not in first]
        for name in first + rest:
            self.rendered[name] = self.synth.render(self.songs[name])

    @property
    def ready(self):
        return len(self.rendered) == len(self.songs)

    def follow(self, state):
        """Called once a frame: switch pieces when the moment changes."""
        wanted = moment(state)
        if self.playing == "tension" and wanted.startswith("floor"):
            self.calm_for += 1
            if self.calm_for < CALM_FRAMES:
                return
        self.calm_for = 0
        if wanted != self.playing or (self.waiting and wanted in self.rendered):
            self.play(wanted)

    def play(self, name):
        self.playing = name
        self.waiting = name in self.songs and name not in self.rendered
        piece = None
        if name in self.rendered:
            song = self.songs[name]
            if song.get("loop", True):
                piece = self.loops.setdefault(name, Piece(self.rendered[name], loop=True))
            else:
                piece = Piece(self.rendered[name], loop=False)  # a jingle starts from the top each time
        with self.lock:
            self.current = piece

    def toggle(self):
        self.on = not self.on
        return self.on

    def mixer(self, game_sound):
        """The sound card's callback: the game's sound plus the music."""
        if not self.on or self.paused or self.current is None:
            return game_sound
        with self.lock:
            music = self.current.render(len(game_sound))
        return mix(game_sound, music)


def mix(game_sound, music):
    """Add the two in float; round off the rare peaks where both are loud, instead of clipping."""
    mixed = game_sound.astype(np.float32) + music.astype(np.float32)
    over = np.abs(mixed) > KNEE
    if over.any():
        above = np.abs(mixed[over]) - KNEE
        mixed[over] = np.sign(mixed[over]) * (KNEE + (TOP - KNEE) * np.tanh(above / (TOP - KNEE)))
    return mixed.astype(np.int16)
