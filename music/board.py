"""Everything heard: the game's own 2600 sound or the remastered sound - the player's choice (E) - and the
soundtrack under either. The remastered sound is the effects and the house's ambience (music/ambience.py).

    board = SoundBoard(MusicPlayer(songs))
    board.follow(state, intro, thunder)   # once a frame: the music follows the game; events trigger effects
    AudioOut(rate, mixer=board.mixer)   # the sound card's callback asks for the mix

Each look's sound chip has its own effects: NES-style (music/effects.py) or the orchestra's
(music/orchestral_effects.py), switching with the look. With the remastered effects on, the game's own sound
is left out (its buzzes say the same things less clearly); music/events.py works out what happened.
"""

import threading

import numpy as np

from music import effects, orchestral_effects
from music.ambience import Ambience
from music.events import EventWatcher
from game.state import GameState
from music.player import MusicPlayer, mix
from shared.types import Samples

MAX_VOICES = 8          # effects playing at once; the oldest gives way
EFFECT_SETS = {"chiptune": effects, "orchestra": orchestral_effects}   # a sound chip -> its effects


class SoundBoard:
    def __init__(self, music: MusicPlayer, background: bool = True):
        """background: the ambience is made in a thread (the app); False makes it now (the browser build)."""
        self.music = music
        self.sound_sets = {chip: maker.render_all() for chip, maker in EFFECT_SETS.items()}
        self.watcher = EventWatcher()
        self.ambience = Ambience(background)
        self.remastered = True
        self.holding = True     # silent while the app loads (app/window.py); nothing is mixed
        self.voices: list[list] = []   # [samples, position] of each effect playing
        self.lock = threading.Lock()

    def follow(self, state: GameState, intro: bool = False, thunder: bool = False) -> None:
        """Once a frame: the music follows the game (and the story, while it shows), what just happened is
        heard, and the storm's thunder when it arrives (shared/storm.py)."""
        self.music.follow(state, intro)
        self.ambience.follow(state, intro, quiet=self.music.silent)
        events = self.watcher.update(state)  # always watched, so switching back finds it up to date
        if not self.remastered:
            return
        if thunder:
            self.ambience.thunder()
        for name in events:
            if name == "footstep" and self.ambience.quiet:
                self.ambience.step()   # where it's quiet, the floorboards are heard
            else:
                self.play(name)

    @property
    def ready(self) -> bool:
        """Is everything heard made: the ambience, and the music for the current look?"""
        return self.ambience.ready and self.music.ready

    def play(self, name: str) -> None:
        with self.lock:
            self.voices.append([self.sound_sets[self.music.synth_name][name], 0])  # the look's own
            del self.voices[:-MAX_VOICES]

    def toggle_effects(self) -> bool:
        """Remastered effects <-> the game's own sound. Returns True for remastered."""
        self.remastered = not self.remastered
        with self.lock:
            self.voices = []
        self.ambience.hush()
        return self.remastered

    def mixer(self, game_sound: Samples) -> Samples:
        """The sound card's callback: the chosen effects (with the ambience under them), then the music."""
        if self.holding:
            return np.zeros_like(game_sound)
        sound = np.zeros_like(game_sound) if self.remastered else game_sound
        if self.remastered and not self.music.paused:
            sound = mix(self.ambience.render(len(game_sound)), self.next_effects(len(game_sound)))
        return self.music.mixer(sound)

    def next_effects(self, count: int) -> Samples:
        out = np.zeros((count, 2), np.int32)
        with self.lock:
            for voice in self.voices:
                samples, position = voice
                take = min(count, len(samples) - position)
                out[:take] += samples[position:position + take]
                voice[1] = position + take
            self.voices = [voice for voice in self.voices if voice[1] < len(voice[0])]
        return np.clip(out, -32767, 32767).astype(np.int16)
