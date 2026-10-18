"""Everything heard: the game's own 2600 sound or the remastered effects - the player's choice (E) - and the
soundtrack under either.

    board = SoundBoard(MusicPlayer(songs))
    board.follow(state)          # once a frame: the music follows the game; events trigger effects
    AudioOut(rate, mixer=board.mixer)   # the sound card's callback asks for the mix

With the remastered effects on, the game's own sound is left out (its buzzes say the same things less
clearly); music/events.py works out what happened, music/effects.py has the sounds.
"""

import threading

import numpy as np

from music import effects
from music.events import EventWatcher
from music.player import mix

MAX_VOICES = 8          # effects playing at once; the oldest gives way


class SoundBoard:
    def __init__(self, music):
        self.music = music
        self.sounds = effects.render_all()
        self.watcher = EventWatcher()
        self.remastered = True
        self.voices = []        # [samples, position] of each effect playing
        self.lock = threading.Lock()

    def follow(self, state):
        """Once a frame: the music follows the game, and what just happened is heard."""
        self.music.follow(state)
        for name in self.watcher.update(state):  # always watched, so switching back finds it up to date
            if self.remastered:
                self.play(name)

    def play(self, name):
        with self.lock:
            self.voices.append([self.sounds[name], 0])
            del self.voices[:-MAX_VOICES]

    def toggle_effects(self):
        """Remastered effects <-> the game's own sound. Returns True for remastered."""
        self.remastered = not self.remastered
        with self.lock:
            self.voices = []
        return self.remastered

    def mixer(self, game_sound):
        """The sound card's callback: the chosen effects, then the music."""
        sound = np.zeros_like(game_sound) if self.remastered else game_sound
        if self.remastered and not self.music.paused:
            sound = mix(sound, self.next_effects(len(game_sound)))
        return self.music.mixer(sound)

    def next_effects(self, count):
        out = np.zeros((count, 2), np.int32)
        with self.lock:
            for voice in self.voices:
                samples, position = voice
                take = min(count, len(samples) - position)
                out[:take] += samples[position:position + take]
                voice[1] = position + take
            self.voices = [voice for voice in self.voices if voice[1] < len(voice[0])]
        return np.clip(out, -32767, 32767).astype(np.int16)
