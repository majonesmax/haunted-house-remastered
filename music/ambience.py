"""The house's ambience: what you hear when the music stops, and the storm under everything.

    where it's quiet   (no song for the moment - the attic in the packs here - the story once its music has
                       played, or the music switched off): rain, wind, a clock in the foyer, drips in the
                       conservatory; floorboards under your feet as you walk; and stand still a while and the
                       house makes its noises - a creak, a moan, knocking, a whisper, a far door, a gust
    everywhere         distant thunder, a moment after the storm's lightning (shared/storm.py)

Rain under music sounds like static, so the beds fade out whenever a song plays. The remastered sound (E)
brings the ambience with it; the 2600's own sound plays alone. music/house.py makes the sounds.

Usage: python -m music.ambience     -> shots/ambience/: each place's bed, the thunder, steps and noises
"""

import os
import threading
import wave

import numpy as np

from music.chiptune import RATE
from music.house import (NOISES, at, drip, floorboard, panned, rain, seconds, thunder, ticking, wind)

BED_LEVEL = 700         # a bed's average loudness: a background, under what happens in it
BED_PEAK = 4000         # a bed's loudest moments are rounded off towards this
THUNDER_LEVEL = 2800    # the one-offs' average loudness while they sound, well above the bed...
STEP_LEVEL = 3000
NOISE_LEVEL = 2600
ONE_OFF_PEAK = 16000    # ...their loudest moments rounded off towards this
FADE_SECONDS = 1.5      # the beds fade in as the music stops (and out as it starts), and between places
IDLE_FRAMES = 90        # stand still this long and the house starts to make its noises...
NOISE_GAP = (3 * 60, 8 * 60)    # ...one every this many frames
STEP_EVERY = 2          # a floorboard for every second footstep (music/events.py's are quick)


# --- the beds -------------------------------------------------------------------------------------------
def outside():
    return rain(1) + 0.6 * wind(2)


def foyer():
    track = rain(3)
    ticking(track, pan=0.5)
    return track


def dining_hall():
    return rain(4)


def conservatory():
    track = rain(5, drops_a_second=140)
    rng = np.random.default_rng(6)
    for seed in range(14):
        at(track, rng.uniform(0, 16), panned(drip(seed) * rng.uniform(0.3, 0.6), rng.uniform(-0.8, 0.8)))
    return track


def attic():
    return 0.6 * rain(7, drops_a_second=60) + wind(8)


PLACES = {"outside": outside, "floor1": foyer, "floor2": dining_hall, "floor3": conservatory,
          "floor4": attic}


def bed_pcm(track):
    """To int16 at BED_LEVEL on average, peaks rounded off below BED_PEAK."""
    average = np.sqrt((track ** 2).mean())
    scaled = track / max(1e-9, average) * BED_LEVEL
    return (BED_PEAK * np.tanh(scaled / BED_PEAK)).astype(np.int16)


def one_off_pcm(sound, level, pan=0.0):
    """A one-off sound (mono or stereo) to int16 stereo at `level` on average while it sounds (its quiet
    tail not counted), peaks rounded off below ONE_OFF_PEAK."""
    stereo = sound if sound.ndim == 2 else panned(sound, pan)
    loudness = np.abs(stereo).max(axis=1)
    sounding = stereo[loudness > loudness.max() * 0.1]
    average = np.sqrt((sounding ** 2).mean() * 2)   # both sides together, as a centred sound
    scaled = stereo / max(1e-9, average) * level
    return (ONE_OFF_PEAK * np.tanh(scaled / ONE_OFF_PEAK)).astype(np.int16)


# --- playing it -----------------------------------------------------------------------------------------
class Ambience:
    """The beds and one-offs, made in the background; each bed keeps its place in its loop."""

    def __init__(self):
        self.beds, self.positions = {}, {}
        self.thunders, self.steps, self.noises = [], [], []
        self.place, self.leaving, self.crossfade = None, None, 0
        self.quiet, self.gain = False, 0.0
        self.voices = []         # [samples, position] of each one-off playing
        self.idle, self.last_player, self.steps_taken = 0, None, 0
        self.rng = np.random.default_rng()
        self.until_noise = self.rng.integers(*NOISE_GAP)
        self.lock = threading.Lock()
        threading.Thread(target=self.make_all, daemon=True).start()

    def make_all(self):
        """A second or two of work, done once in the background."""
        self.thunders = [one_off_pcm(thunder(seed), THUNDER_LEVEL) for seed in range(4)]
        self.steps = [one_off_pcm(floorboard(seed), STEP_LEVEL) for seed in range(8)]
        pans = iter(np.random.default_rng(1).uniform(-0.8, 0.8, 2 * len(NOISES)))
        self.noises = [one_off_pcm(make(seed), NOISE_LEVEL, next(pans))
                       for make in NOISES.values() for seed in (1, 2)]
        for name, make in PLACES.items():
            self.beds[name] = bed_pcm(make())

    # --- following the game ---
    def follow(self, state, intro, quiet):
        """Once a frame. quiet: no music is playing."""
        self.quiet = quiet
        place = "outside" if intro or state.mode == "select" else f"floor{state.floor + 1}"
        if place != self.place:
            with self.lock:
                self.place, self.leaving, self.crossfade = place, self.place, seconds(FADE_SECONDS)
        self.listen_for_stillness(state, intro)

    def listen_for_stillness(self, state, intro):
        """Stand still where it's quiet, and every few seconds the house makes a noise."""
        still = intro or (state.mode == "playing" and state.player == self.last_player)
        self.last_player = state.player
        if not still:
            self.idle, self.until_noise = 0, self.rng.integers(*NOISE_GAP)
            return
        self.idle += 1
        if self.quiet and self.idle >= IDLE_FRAMES:
            self.until_noise -= 1
            if self.until_noise <= 0 and self.noises:
                self.play(self.noises[self.rng.integers(len(self.noises))])
                self.until_noise = self.rng.integers(*NOISE_GAP)

    def thunder(self):
        if self.thunders:
            self.play(self.thunders[self.rng.integers(len(self.thunders))])

    def step(self):
        """A footstep where it's quiet: an old floorboard."""
        self.steps_taken += 1
        if self.steps and self.steps_taken % STEP_EVERY == 1:
            self.play(self.steps[self.rng.integers(len(self.steps))])

    def play(self, samples):
        with self.lock:
            self.voices.append([samples, 0])

    def hush(self):
        """Stop the one-offs (the player chose the 2600's sound)."""
        with self.lock:
            self.voices = []

    # --- the sound card's callback ---
    def render(self, count):
        """The next `count` stereo samples: the bed (as loud as the quiet allows) and the one-offs."""
        with self.lock:
            out = self.bed(count) * self.fade_gain(count)[:, None]
            for voice in self.voices:
                samples, position = voice
                take = min(count, len(samples) - position)
                out[:take] += samples[position:position + take]
                voice[1] = position + take
            self.voices = [voice for voice in self.voices if voice[1] < len(voice[0])]
        return np.clip(out, -32767, 32767).astype(np.int16)

    def fade_gain(self, count):
        """The beds' loudness through these samples, moving towards full when quiet, none when not."""
        target = 1.0 if self.quiet else 0.0
        most = count / seconds(FADE_SECONDS)
        start, self.gain = self.gain, self.gain + float(np.clip(target - self.gain, -most, most))
        return np.linspace(start, self.gain, count)

    def bed(self, count):
        out = self.take(self.place, count).astype(np.float32)
        if self.crossfade:
            done = seconds(FADE_SECONDS) - self.crossfade + np.arange(count)
            fade_in = np.clip(done / seconds(FADE_SECONDS), 0, 1)[:, None]
            out = out * fade_in + self.take(self.leaving, count) * (1 - fade_in)
            self.crossfade = max(0, self.crossfade - count)
        return out

    def take(self, place, count):
        """`count` samples of a place's bed from where it left off; silence if it isn't made yet."""
        bed = self.beds.get(place)
        if bed is None:
            return np.zeros((count, 2), np.int16)
        start = self.positions.get(place, 0)
        self.positions[place] = (start + count) % len(bed)
        return bed[(start + np.arange(count)) % len(bed)]


def attic_visit():
    """To listen to: 30 seconds in the attic - walking for 8, then standing still while the house speaks."""
    track = np.tile(bed_pcm(attic()), (2, 1))[:seconds(30)].astype(np.float32)
    steps = [one_off_pcm(floorboard(seed), STEP_LEVEL) for seed in range(8)]
    for number in range(17):
        begin = seconds(1 + number * 0.45)
        track[begin:begin + len(steps[number % 8])] += steps[number % 8]
    for number, make in enumerate(NOISES.values()):
        noise = one_off_pcm(make(number), NOISE_LEVEL, pan=(-0.6, 0.6)[number % 2])
        begin = seconds(10 + number * 3.3)
        take = min(len(noise), len(track) - begin)
        track[begin:begin + take] += noise[:take]
    return np.clip(track, -32767, 32767).astype(np.int16)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "shots", "ambience")
    os.makedirs(out, exist_ok=True)
    sounds = {name: bed_pcm(make()) for name, make in PLACES.items()}
    sounds.update({f"thunder_{seed}": one_off_pcm(thunder(seed), THUNDER_LEVEL) for seed in range(4)})
    steps = [one_off_pcm(floorboard(seed), STEP_LEVEL) for seed in range(8)]
    sounds["floorboards"] = np.concatenate(steps)
    sounds.update({f"noise_{name}": one_off_pcm(make(1), NOISE_LEVEL) for name, make in NOISES.items()})
    sounds["attic_visit"] = attic_visit()
    for name, pcm in sounds.items():
        path = os.path.join(out, f"{name}.wav")
        with wave.open(path, "wb") as out_file:
            out_file.setnchannels(2)
            out_file.setsampwidth(2)
            out_file.setframerate(RATE)
            out_file.writeframes(pcm.tobytes())
        print(f"{path}  {len(pcm) / RATE:.1f} s")


if __name__ == "__main__":
    main()
