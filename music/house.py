"""The house's own sounds, made from shaped noise, plinks and knocks: rain, wind, distant thunder,
floorboards, and the things you hear when you stand still in the dark. music/ambience.py plays them.

Noise is shaped in the frequency domain, so a loop of it joins up without a seam. Low sounds (thunder, thuds)
keep some of themselves above 150 Hz, where small speakers can play them. Everything is stereo: each
side gets its own noise, so rain is wide, and one-off sounds are placed left or right.
"""

import numpy as np

from music.chiptune import RATE
from shared.types import Floats

LOOP_SECONDS = 16       # a bed's length; it loops


def seconds(count: float) -> int:
    return int(count * RATE)


def decay(length: int, time_constant: float) -> Floats:
    return np.exp(-np.arange(length) / RATE / time_constant)


def fade_in_out(length: int, rise: float, fall: float) -> Floats:
    """An envelope rising over `rise` seconds and falling over the last `fall`."""
    time = np.arange(length) / RATE
    return np.minimum(1, time / rise) * np.minimum(1, (length / RATE - time) / fall).clip(0, 1)


def filtered(signal: Floats, low_hz: float, high_hz: float, tilt: float = 0.0) -> Floats:
    """Only the frequencies from low_hz to high_hz of each column, louder low down by `tilt` (0 flat, 1 a
    deep rumble); circular, so a loop stays a loop. Peak about 1."""
    length = len(signal)
    frequencies = np.fft.rfftfreq(length, 1 / RATE)
    keep = (frequencies >= low_hz) & (frequencies <= high_hz)
    shape = keep / np.maximum(frequencies, low_hz) ** tilt
    out = np.fft.irfft(np.fft.rfft(signal, axis=0) * shape[:, None], length, axis=0)
    return out / max(1e-9, np.abs(out).max())


def noise(length: int, seed: int) -> Floats:
    return np.random.default_rng(seed).normal(size=(length, 2))


def panned(sound: Floats, pan: float) -> Floats:
    """A mono sound as stereo, from -1 (left) to 1 (right)."""
    return np.stack([sound * (1 - pan) / 2, sound * (1 + pan) / 2], axis=1)


def at(track: Floats, start: float, sound: Floats) -> None:
    """Add a stereo sound into a looping track at `start` seconds, wrapping round its end."""
    positions = (seconds(start) + np.arange(len(sound))) % len(track)
    track[positions] += sound


# --- beds: loops ----------------------------------------------------------------------------------------
def swell(cycles: int, depth: float, phase: float = 0.0) -> Floats:
    """A slow rise and fall in loudness, a whole number of times a loop (so it loops too)."""
    time = np.linspace(0, 1, seconds(LOOP_SECONDS), endpoint=False)
    return (1 - depth + depth * (0.5 + 0.5 * np.sin(2 * np.pi * cycles * time + phase)))[:, None]


def rain(seed: int, taps_a_second: int = 30) -> Floats:
    """Rain heard from inside the house: a muffled rush that's never quite steady (on the roof and walls),
    with soft taps on the windows. No pitch anywhere - pitched drops sound like bubbles - and nothing
    bright - a bright, steady hiss sounds like static."""
    length = seconds(LOOP_SECONDS)
    rush = filtered(noise(length, seed), 80, 1400, tilt=0.5)
    unsteady = 0.55 + 0.45 * filtered(noise(length, seed + 1), 4, 30)   # heavier and lighter by turns
    taps = filtered(scattered(seed + 2, length, taps_a_second), 600, 3000)
    return (rush * unsteady + 0.5 * taps) * swell(3, 0.3, phase=seed)


def scattered(seed: int, length: int, a_second: int) -> Floats:
    """Single-sample taps at random on each side, mostly faint - shaped into sound by filtered()."""
    rng = np.random.default_rng(seed)
    taps = np.zeros((length, 2))
    count = a_second * LOOP_SECONDS
    for side in range(2):
        taps[rng.integers(0, length, count), side] = rng.uniform(0.1, 1, count) ** 3
    return taps


def wind(seed: int) -> Floats:
    """Wind: low noise that rises and falls, with a thin whistle on top as it gusts."""
    length = seconds(LOOP_SECONDS)
    body = filtered(noise(length, seed), 80, 700, tilt=0.8) * swell(2, 0.85, phase=seed)
    whistle = filtered(noise(length, seed + 1), 400, 600) * swell(2, 1.0, phase=seed) ** 3 * 0.15
    return body + whistle


def ticking(track: Floats, pan: float) -> None:
    """A clock: tick, tock, every second."""
    for second in range(LOOP_SECONDS):
        at(track, second, panned(knock(2600 if second % 2 else 2000, 0.004) * 0.15, pan))


# --- one-offs -------------------------------------------------------------------------------------------
def knock(pitch: float, time_constant: float, length: int | None = None) -> Floats:
    """A short knock at a pitch: a tick (high, short) or a thud (low, longer)."""
    length = length or seconds(time_constant * 8)
    return np.sin(2 * np.pi * pitch * np.arange(length) / RATE) * decay(length, time_constant)


def wood(seed: int, pitch: float, time_constant: float = 0.025) -> Floats:
    """A knock on wood: a low note with the clack of the surface on top."""
    length = seconds(time_constant * 8)
    body = knock(pitch, time_constant, length) + 0.5 * knock(pitch * 2.7, time_constant / 2, length)
    clack = filtered(noise(length, seed)[:, :1], 700, 3500)[:, 0] * decay(length, 0.004)
    return body + 0.6 * clack


def creak(seed: int, length_seconds: float = 0.7, low_hz: float = 90) -> Floats:
    """Old wood giving: a buzz of quick, uneven clicks whose pitch wanders. Peak 1."""
    rng = np.random.default_rng(seed)
    length = seconds(length_seconds)
    wander = np.interp(np.arange(length), np.linspace(0, length, 6), rng.uniform(0.8, 1.5, 6))
    phase = np.cumsum(low_hz * wander) / RATE
    clicks = (np.sin(2 * np.pi * phase) > 0.92) * 1.0
    body = np.convolve(clicks, decay(seconds(0.004), 0.001), mode="same")
    shaped = body * np.sin(np.pi * np.linspace(0, 1, length)) ** 2
    return shaped / max(1e-9, np.abs(shaped).max())


def thunder(seed: int) -> Floats:
    """Thunder a long way off: two or three low rolls, the first the loudest, dying away."""
    rng = np.random.default_rng(seed)
    length = seconds(7)
    rumble = filtered(noise(length, seed), 30, 700, tilt=0.7)
    time = np.arange(length) / RATE
    rolls = np.zeros(length)
    start = 0.0
    for roll in range(rng.integers(2, 4)):
        width = rng.uniform(0.6, 1.4)
        rolls += np.exp(-((time - start - width) / width) ** 2) * 0.7 ** roll
        start += rng.uniform(0.8, 1.6)
    return rumble * (rolls * fade_in_out(length, 0.2, 1.5))[:, None]


def birdsong(seed: int) -> Floats:
    """A small bird: a phrase of quick chirps, each a whistle that swoops and trills."""
    rng = np.random.default_rng(seed)
    phrase = np.zeros(seconds(1.6))
    start = 0.0
    for _chirp in range(rng.integers(3, 7)):
        length = seconds(rng.uniform(0.05, 0.13))
        time = np.arange(length) / RATE
        swoop = np.linspace(rng.uniform(2500, 4200), rng.uniform(2800, 5000), length)
        trill = 1 + 0.06 * np.sin(2 * np.pi * rng.uniform(25, 45) * time)
        chirp = np.sin(2 * np.pi * np.cumsum(swoop * trill) / RATE) * np.sin(np.pi * time / time[-1]) ** 2
        begin = seconds(start)
        phrase[begin:begin + length] += chirp[:len(phrase) - begin]
        start += rng.uniform(0.09, 0.22)
    return phrase


def drip(seed: int) -> Floats:
    """A drop into a puddle: a short plink that bends up."""
    rng = np.random.default_rng(seed)
    length = seconds(0.12)
    pitch = rng.uniform(900, 1600) * (1 + 0.6 * np.linspace(0, 1, length))
    return np.sin(2 * np.pi * np.cumsum(pitch) / RATE) * decay(length, 0.025)


def floorboard(seed: int) -> Floats:
    """A step on an old floorboard: a soft thud, and now and then a small creak after it."""
    rng = np.random.default_rng(seed)
    thud = wood(seed, rng.uniform(140, 170))
    step = np.zeros(seconds(0.6))
    step[:len(thud)] += thud
    if rng.random() < 0.4:
        bend = creak(seed, rng.uniform(0.25, 0.45), rng.uniform(110, 160)) * 0.35
        begin = seconds(0.05)
        step[begin:begin + len(bend)] += bend
    return panned(step, rng.uniform(-0.15, 0.15))


def moan(seed: int) -> Floats:
    """A low voice somewhere in the house: a breathy tone that sinks, wavering."""
    rng = np.random.default_rng(seed)
    length = seconds(rng.uniform(2.0, 3.0))
    time = np.arange(length) / RATE
    pitch = rng.uniform(180, 260) * (1 - 0.25 * time / time[-1]) * (1 + 0.02 * np.sin(2 * np.pi * 5 * time))
    tone = np.sin(2 * np.pi * np.cumsum(pitch) / RATE)
    breath = filtered(noise(length, seed)[:, :1], 300, 1200)[:, 0] * 0.4
    return (tone * 0.6 + breath) * fade_in_out(length, 0.6, 1.0)


def far_door(seed: int) -> Floats:
    """A door shutting somewhere far off: a dull thud and a rattle."""
    thud = wood(seed, 90, 0.06)
    rattle = filtered(noise(seconds(0.15), seed)[:, :1], 800, 3000)[:, 0] * decay(seconds(0.15), 0.03)
    door = np.zeros(seconds(0.6))
    door[:len(thud)] += thud
    door[seconds(0.03):seconds(0.03) + len(rattle)] += rattle * 0.3
    return door


def knocking(seed: int) -> Floats:
    """Three slow knocks behind a wall."""
    rng = np.random.default_rng(seed)
    gap = rng.uniform(0.45, 0.7)
    sound = np.zeros(seconds(gap * 3))
    for number in range(3):
        thud = wood(seed + number, rng.uniform(160, 190))
        begin = seconds(number * gap)
        sound[begin:begin + len(thud)] += thud[:len(sound) - begin]
    return sound


def whisper(seed: int) -> Floats:
    """Breath, shaped into a few syllables - too faint to make out."""
    rng = np.random.default_rng(seed)
    length = seconds(1.6)
    hiss = filtered(noise(length, seed)[:, :1], 2000, 6000)[:, 0]
    time = np.arange(length) / RATE
    syllables = np.clip(np.sin(2 * np.pi * rng.uniform(2.5, 4.0) * time), 0, 1) ** 2
    return hiss * syllables * fade_in_out(length, 0.3, 0.4)


def gust(seed: int) -> Floats:
    """Wind rising round the house, then dropping."""
    length = seconds(3.5)
    body = filtered(noise(length, seed), 100, 900, tilt=0.6)
    return body * (np.sin(np.pi * np.linspace(0, 1, length)) ** 2)[:, None]


NOISES = {"creak": lambda seed: creak(seed, 0.8, 80), "moan": moan, "far_door": far_door,
          "knocking": knocking, "whisper": whisper, "gust": gust}   # heard when you stand still
