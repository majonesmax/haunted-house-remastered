"""The house's own sounds, under the music: a quiet bed that loops for each place.

    outside   the title: rain and wind, thunder far off
    floor1    the foyer: rain at the windows, a clock ticking, a floorboard now and then
    floor2    the dining hall: rain, the house settling, a far roll of thunder
    floor3    the conservatory: rain on the glass, drips into puddles
    floor4    the attic: wind under the roof, rain on the slates, a creaking beam

Everything is made from shaped noise and a few plinks and knocks, in stereo (each side its own noise, so the
rain is wide). Noise is shaped in the frequency domain, so each bed loops without a seam. The remastered
sound (E) brings the ambience with it; the 2600's own sound plays alone.

Usage: python -m music.ambience     -> shots/ambience/<name>.wav, to listen to
"""

import os
import threading
import wave

import numpy as np

from music.chiptune import RATE

LOOP_SECONDS = 16       # each bed's length; it loops
LEVEL = 700             # each bed's average loudness: well under the music (12000) and the effects (14000)
PEAK = 4000             # loud moments (a creak, thunder) are rounded off towards this
FADE_SECONDS = 1.0      # moving to another place: the old bed fades out as the new one fades in


def seconds(count):
    return int(count * RATE)


# --- the raw sounds -------------------------------------------------------------------------------------
def shaped_noise(low_hz, high_hz, seed, length=None):
    """Stereo noise with only the frequencies from low_hz to high_hz, looping seamlessly; peak about 1."""
    length = length or seconds(LOOP_SECONDS)
    rng = np.random.default_rng(seed)
    frequencies = np.fft.rfftfreq(length, 1 / RATE)
    keep = (frequencies >= low_hz) & (frequencies <= high_hz)
    sides = []
    for _side in range(2):
        spectrum = rng.normal(size=len(frequencies)) + 1j * rng.normal(size=len(frequencies))
        sides.append(np.fft.irfft(spectrum * keep, length))
    noise = np.stack(sides, axis=1)
    return noise / np.abs(noise).max()


def swell(cycles, depth, phase=0.0):
    """A slow rise and fall in loudness, a whole number of times a loop (so it loops too)."""
    t = np.linspace(0, 1, seconds(LOOP_SECONDS), endpoint=False)
    return (1 - depth + depth * (0.5 + 0.5 * np.sin(2 * np.pi * cycles * t + phase)))[:, None]


def decay(length, time_constant):
    return np.exp(-np.arange(length) / RATE / time_constant)


def at(track, start, sound, pan=0.0):
    """Add a mono sound into a stereo track at `start` seconds, panned from -1 (left) to 1 (right),
    wrapping round the loop's end."""
    begin = seconds(start) % len(track)
    positions = (begin + np.arange(len(sound))) % len(track)
    track[positions, 0] += sound * (1 - pan) / 2
    track[positions, 1] += sound * (1 + pan) / 2


def drip(pitch_hz):
    """A drop into a puddle: a short plink that bends up."""
    length = seconds(0.12)
    hz = pitch_hz * (1 + 0.6 * np.linspace(0, 1, length))
    return np.sin(2 * np.pi * np.cumsum(hz) / RATE) * decay(length, 0.025)


def tick(pitch_hz):
    """A clock's tick: a tiny bright knock."""
    length = seconds(0.03)
    return np.sin(2 * np.pi * pitch_hz * np.arange(length) / RATE) * decay(length, 0.004)


def creak(seed, length_seconds=0.7, low_hz=90):
    """Old wood giving: a buzz of quick, uneven clicks whose pitch wanders."""
    rng = np.random.default_rng(seed)
    length = seconds(length_seconds)
    wander = np.interp(np.arange(length), np.linspace(0, length, 6), rng.uniform(0.8, 1.5, 6))
    phase = np.cumsum(low_hz * wander) / RATE
    clicks = (np.sin(2 * np.pi * phase) > 0.92) * 1.0
    body = np.convolve(clicks, decay(seconds(0.004), 0.001), mode="same")
    envelope = np.sin(np.pi * np.linspace(0, 1, length)) ** 2
    return body * envelope / max(1e-9, np.abs(body).max())


def rumble(seed, length_seconds=5.0):
    """Thunder a long way off: a low roll that swells and dies away."""
    length = seconds(length_seconds)
    noise = shaped_noise(25, 160, seed, length)[:, 0]
    envelope = np.minimum(np.linspace(0, 6, length), 1) * decay(length, 1.2)
    return noise * envelope


# --- the places -----------------------------------------------------------------------------------------
def rain(loudness, seed):
    return shaped_noise(900, 7000, seed) * swell(3, 0.25) * loudness


def wind(loudness, seed):
    return shaped_noise(120, 500, seed) * swell(2, 0.8, phase=seed) * loudness


def outside():
    track = rain(0.5, 1) + wind(0.5, 2)
    at(track, 9.0, rumble(3), pan=-0.4)
    return track


def foyer():
    track = rain(0.25, 4)
    for second in range(LOOP_SECONDS):
        at(track, second, tick(2600 if second % 2 else 2000) * 0.5, pan=0.5)
    at(track, 6.5, creak(5) * 0.4, pan=-0.6)
    return track


def dining_hall():
    track = rain(0.3, 6)
    at(track, 3.0, creak(7, 0.5, 70) * 0.35, pan=0.6)
    at(track, 10.0, rumble(8) * 0.8, pan=0.3)
    return track


def conservatory():
    track = rain(0.55, 9)
    rng = np.random.default_rng(10)
    for _drop in range(14):
        at(track, rng.uniform(0, LOOP_SECONDS), drip(rng.uniform(900, 1600)) * rng.uniform(0.3, 0.6),
           pan=rng.uniform(-0.8, 0.8))
    return track


def attic():
    track = wind(0.8, 11) + rain(0.3, 12)
    at(track, 5.0, creak(13, 1.2, 55) * 0.5, pan=-0.3)
    at(track, 12.5, creak(14, 0.8, 65) * 0.4, pan=0.5)
    return track


PLACES = {"outside": outside, "floor1": foyer, "floor2": dining_hall, "floor3": conservatory,
          "floor4": attic}


def place_for(state):
    """Which bed belongs to this moment: outside on the title, else the floor you're on."""
    if state.mode == "select":
        return "outside"
    return f"floor{state.floor + 1}"


def to_pcm(track):
    """To int16 at LEVEL on average, peaks rounded off below PEAK."""
    average = np.sqrt((track ** 2).mean())
    scaled = track / max(1e-9, average) * LEVEL
    return (PEAK * np.tanh(scaled / PEAK)).astype(np.int16)


def render_all():
    return {name: to_pcm(make()) for name, make in PLACES.items()}


# --- playing it -----------------------------------------------------------------------------------------
class Ambience:
    """The beds, rendered in the background, each keeping its place in its loop; moving to another place
    crossfades."""

    def __init__(self):
        self.beds = {}           # place -> its samples, as the background renders them
        self.positions = {}      # place -> where its loop is
        self.place, self.leaving = None, None
        self.fade = 0            # samples left of the crossfade
        self.lock = threading.Lock()
        threading.Thread(target=self.render_all, daemon=True).start()

    def render_all(self):
        for name, make in PLACES.items():
            self.beds[name] = to_pcm(make())   # a fraction of a second each

    def follow(self, state):
        place = place_for(state)
        if place != self.place:
            with self.lock:
                self.place, self.leaving = place, self.place
                self.fade = seconds(FADE_SECONDS)

    def render(self, count):
        """The next `count` stereo samples."""
        with self.lock:
            out = self.take(self.place, count).astype(np.float32)
            if self.fade:
                fade_in = np.clip(1 - (self.fade - np.arange(count)) / seconds(FADE_SECONDS), 0, 1)[:, None]
                leaving = self.take(self.leaving, count).astype(np.float32)
                out = out * fade_in + leaving * (1 - fade_in)
                self.fade = max(0, self.fade - count)
        return out.astype(np.int16)

    def take(self, place, count):
        """`count` samples of a place's bed from where it left off; silence if it isn't ready."""
        bed = self.beds.get(place)
        if bed is None:
            return np.zeros((count, 2), np.int16)
        start = self.positions.get(place, 0)
        indices = (start + np.arange(count)) % len(bed)
        self.positions[place] = (start + count) % len(bed)
        return bed[indices]


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "shots", "ambience")
    os.makedirs(out, exist_ok=True)
    for name, pcm in render_all().items():
        path = os.path.join(out, f"{name}.wav")
        with wave.open(path, "wb") as out_file:
            out_file.setnchannels(2)
            out_file.setsampwidth(2)
            out_file.setframerate(RATE)
            out_file.writeframes(pcm.tobytes())
        print(f"{path}  {len(pcm) / RATE:.1f} s")


if __name__ == "__main__":
    main()
