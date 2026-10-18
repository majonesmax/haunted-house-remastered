"""Remastered sound effects: NES-style sounds that say what just happened, made with the same voices as the
music (music/chiptune.py: pulse, triangle, noise).

The 2600's own effects are buzzes and static that sound much alike; these are meant to be told apart by ear -
a match striking, a door creaking open, steps going up or down the stairs, a key's jingle. music/events.py
decides when each plays.

Usage: python music/effects.py     -> shots/effects/<name>.wav, to listen to
"""

import os
import wave

import numpy as np

from music.chiptune import RATE, envelope, midi_hz, pulse, triangle

LEVEL = 14000          # effects sit a little above the music (12000)
QUIET = 0.25           # footsteps: a quarter of that


def seconds(count):
    return int(count * RATE)


def sweep(start_hz, end_hz, length):
    """A pitch gliding from start_hz to end_hz (evenly in pitch, not in Hz)."""
    return start_hz * (end_hz / start_hz) ** np.linspace(0, 1, length)


def noise(length, pitch=1.0, seed=1):
    """NES-style noise: a random level held for 1/pitch of the time - lower pitch, lower rumble."""
    rng = np.random.default_rng(seed)
    hold = max(1, int(round(1 / pitch)))
    levels = rng.choice([-1.0, 1.0], length // hold + 1)
    return np.repeat(levels, hold)[:length]


def decay(length, time_constant):
    return np.exp(-np.arange(length) / RATE / time_constant)


def place(parts, total):
    """[(start in seconds, samples), ...] -> one track of `total` seconds."""
    track = np.zeros(seconds(total))
    for start, samples in parts:
        begin = seconds(start)
        end = min(len(track), begin + len(samples))
        track[begin:end] += samples[:end - begin]
    return track


def notes(midis, note_length, duty=0.25, shape="pulse"):
    """A quick run of notes (an arpeggio), each note_length seconds."""
    parts = []
    for index, midi in enumerate(midis):
        length = seconds(note_length)
        voice = triangle(midi_hz(midi), length) if shape == "triangle" else pulse(midi_hz(midi), length, duty)
        parts.append((index * note_length, voice * envelope(length, decay=0.06, sustain=0.4)))
    return place(parts, note_length * len(midis) + 0.1)


# --- the effects ---------------------------------------------------------------------------------------
def match_strike():
    """A scratch, then the flare catching."""
    scratch = noise(seconds(0.08), pitch=1.0) * decay(seconds(0.08), 0.03)
    flare_length = seconds(0.35)
    flare_shape = envelope(flare_length, attack=0.05, decay=0.12, sustain=0.2)
    flare = noise(flare_length, pitch=0.5, seed=2) * flare_shape
    return place([(0, scratch), (0.06, flare * 0.6)], 0.45)


def match_out():
    """A puff: the match going out."""
    length = seconds(0.25)
    return noise(length, pitch=0.25, seed=3) * envelope(length, attack=0.02, decay=0.08, sustain=0.0) * 0.6


def door_open():
    """A creak: a thin pulse wavering down."""
    length = seconds(0.45)
    pitch = sweep(330, 210, length) * (1 + 0.04 * np.sin(np.arange(length) / RATE * 2 * np.pi * 9))
    phase = np.cumsum(pitch) / RATE % 1.0
    creak = np.where(phase < 0.125, 1.0, -1.0)
    return creak * envelope(length, attack=0.03, decay=0.3, sustain=0.3) * 0.5


def door_close():
    """A soft thud as you're through: the triangle dropping."""
    length = seconds(0.2)
    return triangle(sweep(120, 55, length), length) * decay(length, 0.06)


def locked():
    """A door that won't open: three rattles of the handle."""
    rattles = [(index * 0.07, noise(seconds(0.03), pitch=0.5, seed=4 + index) * decay(seconds(0.03), 0.01))
               for index in range(3)]
    clunk_length = seconds(0.15)
    clunk = triangle(sweep(90, 60, clunk_length), clunk_length) * decay(clunk_length, 0.05)
    return place(rattles + [(0.22, clunk)], 0.4)


def bump():
    """Walking into a wall: a dull knock."""
    length = seconds(0.09)
    return triangle(sweep(100, 70, length), length) * decay(length, 0.03) * 0.8


def stairs(going_up):
    """Six steps, each a footfall and a note, climbing - or going down - the scale."""
    scale = [57, 60, 62, 64, 67, 69] if going_up else [69, 67, 64, 62, 60, 57]
    parts = []
    for index, midi in enumerate(scale):
        step = noise(seconds(0.025), pitch=0.5, seed=10 + index) * decay(seconds(0.025), 0.008)
        length = seconds(0.09)
        tone = pulse(midi_hz(midi), length, 0.25) * envelope(length, decay=0.05, sustain=0.3)
        parts.append((index * 0.1, step + 0.0))
        parts.append((index * 0.1, tone * 0.7))
    return place(parts, 0.75)


def pickup_key():
    """A jingle: two bright notes, twice."""
    return notes([84, 88, 84, 88], 0.05, duty=0.125)


def pickup_scepter():
    """A shimmer up a major chord."""
    return notes([72, 76, 79, 84, 88, 91], 0.045, duty=0.125)


def pickup_urn():
    """A warm, low chord, broken."""
    return notes([60, 64, 67, 72], 0.07, shape="triangle")


def drop():
    """Setting something down."""
    length = seconds(0.12)
    return triangle(sweep(180, 90, length), length) * decay(length, 0.04) * 0.8


def urn_join():
    """Two pieces join: a magical rising run."""
    return notes([67, 71, 74, 79, 83, 86, 91], 0.05, duty=0.125)


def urn_whole():
    """The urn is whole: the run, then a ringing chord."""
    run = notes([67, 71, 74, 79, 83, 86, 91, 95], 0.05, duty=0.125)
    chord_length = seconds(0.8)
    chord = sum(pulse(midi_hz(midi), chord_length, 0.25) for midi in (79, 83, 86)) / 3
    return place([(0, run), (0.4, chord * envelope(chord_length, decay=0.3, sustain=0.2))], 1.3)


def caught():
    """A scream sliding down, and a crash."""
    length = seconds(0.6)
    scream = pulse(sweep(900, 150, length), length, 0.25) * envelope(length, decay=0.4, sustain=0.3)
    crash_length = seconds(0.5)
    crash = noise(crash_length, pitch=0.3, seed=20) * decay(crash_length, 0.15)
    return place([(0, scream * 0.6), (0.05, crash)], 0.7)


def thunder():
    """A long, low rumble."""
    length = seconds(1.4)
    rumble = noise(length, pitch=0.06, seed=30) * envelope(length, attack=0.05, decay=0.5, sustain=0.0)
    crack = noise(seconds(0.08), pitch=1.0, seed=31) * decay(seconds(0.08), 0.02)
    return place([(0, crack * 0.5), (0.02, rumble)], 1.5)


def ghost():
    """Oooo: a slow, wavering moan."""
    length = seconds(0.9)
    pitch = sweep(220, 160, length) * (1 + 0.05 * np.sin(np.arange(length) / RATE * 2 * np.pi * 4))
    phase = np.cumsum(pitch) / RATE % 1.0
    moan = 1 - 4 * np.abs(phase - 0.5)
    return moan * envelope(length, attack=0.2, decay=0.6, sustain=0.4)


def bat():
    """Wings: quick flutters."""
    flaps = [(index * 0.06, noise(seconds(0.03), pitch=0.3, seed=40 + index) * decay(seconds(0.03), 0.01))
             for index in range(6)]
    return place(flaps, 0.4)


def tarantula():
    """Legs: a dry skitter."""
    click = seconds(0.012)
    clicks = [(index * 0.035, noise(click, pitch=1.0, seed=50 + index) * decay(click, 0.004))
              for index in range(9)]
    return place(clicks, 0.4)


def footstep():
    """One step on old boards: a soft knock, quiet."""
    length = seconds(0.05)
    knock = triangle(sweep(140, 90, length), length) * decay(length, 0.015)
    return knock * QUIET


EFFECTS = {"match_strike": match_strike, "match_out": match_out, "door_open": door_open,
           "door_close": door_close, "locked": locked, "bump": bump,
           "stairs_up": lambda: stairs(going_up=True), "stairs_down": lambda: stairs(going_up=False),
           "pickup_key": pickup_key, "pickup_scepter": pickup_scepter, "pickup_urn": pickup_urn,
           "drop": drop, "urn_join": urn_join, "urn_whole": urn_whole, "caught": caught, "thunder": thunder,
           "monster_ghost": ghost, "monster_bat": bat, "monster_tarantula": tarantula, "footstep": footstep}


def to_pcm(track, level=LEVEL):
    """One track -> int16 stereo at the effects' level (quieter ones keep their own share)."""
    loudest = max(1e-9, np.abs(track).max())
    scale = level * min(1.0, loudest) / loudest
    return np.repeat((track * scale)[:, None], 2, axis=1).astype(np.int16)


def render_all():
    return {name: to_pcm(make()) for name, make in EFFECTS.items()}


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "shots", "effects")
    os.makedirs(out, exist_ok=True)
    for name, pcm in render_all().items():
        path = os.path.join(out, f"{name}.wav")
        with wave.open(path, "wb") as out_file:
            out_file.setnchannels(2)
            out_file.setsampwidth(2)
            out_file.setframerate(RATE)
            out_file.writeframes(pcm.tobytes())
        print(f"{path}  {len(pcm) / RATE:.2f} s")


if __name__ == "__main__":
    main()
