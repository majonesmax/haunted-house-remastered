"""The house's own sounds, made from shaped noise, plinks and knocks: rain, wind, distant thunder,
floorboards, and the things you hear when you stand still in the dark. music/ambience.py plays them.

Noise is shaped in the frequency domain, so a loop of it joins up without a seam. Low sounds (thunder, thuds)
keep some of themselves above 150 Hz, where small speakers can play them. Everything is stereo: each
side gets its own noise, so rain is wide, and one-off sounds are placed left or right.
"""

import numpy as np

from music.chiptune import RATE

LOOP_SECONDS = 16       # a bed's length; it loops


def seconds(count):
    return int(count * RATE)


def decay(length, time_constant):
    return np.exp(-np.arange(length) / RATE / time_constant)


def fade_in_out(length, rise, fall):
    """An envelope rising over `rise` seconds and falling over the last `fall`."""
    t = np.arange(length) / RATE
    return np.minimum(1, t / rise) * np.minimum(1, (length / RATE - t) / fall).clip(0, 1)


def filtered(signal, low_hz, high_hz, tilt=0.0):
    """Only the frequencies from low_hz to high_hz of each column, louder low down by `tilt` (0 flat, 1 a
    deep rumble); circular, so a loop stays a loop. Peak about 1."""
    length = len(signal)
    frequencies = np.fft.rfftfreq(length, 1 / RATE)
    keep = (frequencies >= low_hz) & (frequencies <= high_hz)
    shape = keep / np.maximum(frequencies, low_hz) ** tilt
    out = np.fft.irfft(np.fft.rfft(signal, axis=0) * shape[:, None], length, axis=0)
    return out / max(1e-9, np.abs(out).max())


def noise(length, seed):
    return np.random.default_rng(seed).normal(size=(length, 2))


def panned(sound, pan):
    """A mono sound as stereo, from -1 (left) to 1 (right)."""
    return np.stack([sound * (1 - pan) / 2, sound * (1 + pan) / 2], axis=1)


def at(track, start, sound):
    """Add a stereo sound into a looping track at `start` seconds, wrapping round its end."""
    positions = (seconds(start) + np.arange(len(sound))) % len(track)
    track[positions] += sound


# --- beds: loops ----------------------------------------------------------------------------------------
def swell(cycles, depth, phase=0.0):
    """A slow rise and fall in loudness, a whole number of times a loop (so it loops too)."""
    t = np.linspace(0, 1, seconds(LOOP_SECONDS), endpoint=False)
    return (1 - depth + depth * (0.5 + 0.5 * np.sin(2 * np.pi * cycles * t + phase)))[:, None]


def rain(seed, drops_a_second=40):
    """Rain: separate drops - each a tiny ping, some near and clear, many far and soft - over a low murmur.
    (A wash of plain noise, however filtered, sounds like static.)"""
    length = seconds(LOOP_SECONDS)
    rng = np.random.default_rng(seed)
    near = scatter_drops(rng, length, drops_a_second, 0.6)
    far = filtered(scatter_drops(rng, length, drops_a_second * 6, 0.25), 200, 2500)
    murmur = filtered(noise(length, seed), 60, 900, tilt=1.0)
    return (near + 0.35 * far + 0.12 * murmur) * swell(3, 0.3, phase=seed)


def scatter_drops(rng, length, a_second, loudness):
    """`a_second` drops a second on each side, at random, mostly small; looping round the end."""
    pings = [drop_ping(hz) for hz in np.geomspace(1500, 5000, 12)]
    track = np.zeros((length + len(pings[0]), 2))
    for side in range(2):
        count = a_second * LOOP_SECONDS
        for start, size, ping in zip(rng.integers(0, length, count), rng.uniform(0.1, 1, count) ** 2,
                                     rng.integers(len(pings), size=count)):
            track[start:start + len(pings[ping]), side] += pings[ping] * size
    track[:len(pings[0])] += track[length:]          # what ran past the end comes round to the start
    return track[:length] * loudness


def drop_ping(hz):
    """One raindrop: a ping a few milliseconds long that rises a little."""
    length = seconds(0.008)
    rising = hz * (1 + 0.3 * np.linspace(0, 1, length))
    return np.sin(2 * np.pi * np.cumsum(rising) / RATE) * decay(length, 0.002)


def wind(seed):
    """Wind: low noise that rises and falls, with a thin whistle on top as it gusts."""
    length = seconds(LOOP_SECONDS)
    body = filtered(noise(length, seed), 80, 700, tilt=0.8) * swell(2, 0.85, phase=seed)
    whistle = filtered(noise(length, seed + 1), 400, 600) * swell(2, 1.0, phase=seed) ** 3 * 0.15
    return body + whistle


def ticking(track, pan):
    """A clock: tick, tock, every second."""
    for second in range(LOOP_SECONDS):
        at(track, second, panned(knock(2600 if second % 2 else 2000, 0.004) * 0.15, pan))


# --- one-offs -------------------------------------------------------------------------------------------
def knock(hz, time_constant, length=None):
    """A short knock at a pitch: a tick (high, short) or a thud (low, longer)."""
    length = length or seconds(time_constant * 8)
    return np.sin(2 * np.pi * hz * np.arange(length) / RATE) * decay(length, time_constant)


def wood(seed, hz, time_constant=0.025):
    """A knock on wood: a low note with the clack of the surface on top."""
    length = seconds(time_constant * 8)
    body = knock(hz, time_constant, length) + 0.5 * knock(hz * 2.7, time_constant / 2, length)
    clack = filtered(noise(length, seed)[:, :1], 700, 3500)[:, 0] * decay(length, 0.004)
    return body + 0.6 * clack


def creak(seed, length_seconds=0.7, low_hz=90):
    """Old wood giving: a buzz of quick, uneven clicks whose pitch wanders. Peak 1."""
    rng = np.random.default_rng(seed)
    length = seconds(length_seconds)
    wander = np.interp(np.arange(length), np.linspace(0, length, 6), rng.uniform(0.8, 1.5, 6))
    phase = np.cumsum(low_hz * wander) / RATE
    clicks = (np.sin(2 * np.pi * phase) > 0.92) * 1.0
    body = np.convolve(clicks, decay(seconds(0.004), 0.001), mode="same")
    shaped = body * np.sin(np.pi * np.linspace(0, 1, length)) ** 2
    return shaped / max(1e-9, np.abs(shaped).max())


def thunder(seed):
    """Thunder a long way off: two or three low rolls, the first the loudest, dying away."""
    rng = np.random.default_rng(seed)
    length = seconds(7)
    rumble = filtered(noise(length, seed), 30, 700, tilt=0.7)
    t = np.arange(length) / RATE
    rolls = np.zeros(length)
    start = 0.0
    for roll in range(rng.integers(2, 4)):
        width = rng.uniform(0.6, 1.4)
        rolls += np.exp(-((t - start - width) / width) ** 2) * 0.7 ** roll
        start += rng.uniform(0.8, 1.6)
    return rumble * (rolls * fade_in_out(length, 0.2, 1.5))[:, None]


def drip(seed):
    """A drop into a puddle: a short plink that bends up."""
    rng = np.random.default_rng(seed)
    length = seconds(0.12)
    hz = rng.uniform(900, 1600) * (1 + 0.6 * np.linspace(0, 1, length))
    return np.sin(2 * np.pi * np.cumsum(hz) / RATE) * decay(length, 0.025)


def floorboard(seed):
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


def moan(seed):
    """A low voice somewhere in the house: a breathy tone that sinks, wavering."""
    rng = np.random.default_rng(seed)
    length = seconds(rng.uniform(2.0, 3.0))
    t = np.arange(length) / RATE
    hz = rng.uniform(180, 260) * (1 - 0.25 * t / t[-1]) * (1 + 0.02 * np.sin(2 * np.pi * 5 * t))
    tone = np.sin(2 * np.pi * np.cumsum(hz) / RATE)
    breath = filtered(noise(length, seed)[:, :1], 300, 1200)[:, 0] * 0.4
    return (tone * 0.6 + breath) * fade_in_out(length, 0.6, 1.0)


def far_door(seed):
    """A door shutting somewhere far off: a dull thud and a rattle."""
    thud = wood(seed, 90, 0.06)
    rattle = filtered(noise(seconds(0.15), seed)[:, :1], 800, 3000)[:, 0] * decay(seconds(0.15), 0.03)
    door = np.zeros(seconds(0.6))
    door[:len(thud)] += thud
    door[seconds(0.03):seconds(0.03) + len(rattle)] += rattle * 0.3
    return door


def knocking(seed):
    """Three slow knocks behind a wall."""
    rng = np.random.default_rng(seed)
    gap = rng.uniform(0.45, 0.7)
    sound = np.zeros(seconds(gap * 3))
    for number in range(3):
        thud = wood(seed + number, rng.uniform(160, 190))
        begin = seconds(number * gap)
        sound[begin:begin + len(thud)] += thud[:len(sound) - begin]
    return sound


def whisper(seed):
    """Breath, shaped into a few syllables - too faint to make out."""
    rng = np.random.default_rng(seed)
    length = seconds(1.6)
    hiss = filtered(noise(length, seed)[:, :1], 2000, 6000)[:, 0]
    t = np.arange(length) / RATE
    syllables = np.clip(np.sin(2 * np.pi * rng.uniform(2.5, 4.0) * t), 0, 1) ** 2
    return hiss * syllables * fade_in_out(length, 0.3, 0.4)


def gust(seed):
    """Wind rising round the house, then dropping."""
    length = seconds(3.5)
    body = filtered(noise(length, seed), 100, 900, tilt=0.6)
    return body * (np.sin(np.pi * np.linspace(0, 1, length)) ** 2)[:, None]


NOISES = {"creak": lambda seed: creak(seed, 0.8, 80), "moan": moan, "far_door": far_door,
          "knocking": knocking, "whisper": whisper, "gust": gust}   # heard when you stand still
