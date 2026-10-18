"""The SNES look's sound effects: the same events as music/effects.py, played by the orchestra
(music/orchestra.py) - harp, bell, strings, harpsichord, timpani - in its hall. What isn't music (a match, a
door, a knock on a wall) is made the way the house's own sounds are (music/house.py).

Usage: python -m music.orchestral_effects     -> shots/effects/<name>-orchestra.wav, to listen to
"""

import os
import wave

import numpy as np

from music import house
from music.ambience import one_off_pcm
from music.chiptune import RATE, midi_hz
from music.effects import QUIET, decay, place, seconds
from music.orchestra import bell, harp, harpsichord, hall, organ, strings, timpani, violin

LEVEL = 6400            # each effect's loudness while it sounds: a little under the NES's square waves


def notes(midis, gap, voice, ring=0.6):
    """A run of notes `gap` seconds apart on one instrument, each ringing `ring` seconds."""
    length = seconds(ring)
    return place([(index * gap, voice(midi_hz(midi), length)) for index, midi in enumerate(midis)],
                  gap * len(midis) + ring)


def chord(midis, length_seconds, voice):
    length = seconds(length_seconds)
    return sum(voice(midi_hz(midi), length) for midi in midis) / len(midis)


def scrape(seed, length_seconds, low_hz, high_hz, time_constant):
    """A burst of filtered noise dying away: a scratch, a puff, a rattle."""
    length = seconds(length_seconds)
    burst = house.filtered(house.noise(length, seed)[:, :1], low_hz, high_hz)[:, 0]
    return burst * decay(length, time_constant)


# --- the effects ---------------------------------------------------------------------------------------
def match_strike():
    """The head scraping the box, then the flame catching with a soft roar."""
    scratch = scrape(1, 0.09, 1500, 7000, 0.03)
    flare_length = seconds(0.4)
    flare = house.filtered(house.noise(flare_length, 2)[:, :1], 200, 2500)[:, 0]
    flare *= np.minimum(1, np.arange(flare_length) / seconds(0.04)) * decay(flare_length, 0.15)
    return place([(0, scratch), (0.07, flare * 0.7)], 0.5)


def match_out():
    """Blown out: a breath."""
    return scrape(3, 0.3, 300, 1800, 0.08) * 0.7


def door_open():
    """Old hinges: a slow creak."""
    return house.creak(4, 0.55, 140) * 0.6


def door_close():
    """The door swinging to behind you: a wooden knock with the hall's ring."""
    return house.wood(5, 110, 0.04)


def locked():
    """The handle rattles; a low string says no."""
    rattles = [(index * 0.07, scrape(6 + index, 0.03, 900, 4000, 0.01)) for index in range(3)]
    refusal = notes([38, 37], 0.14, lambda freq, length: strings(freq, length, attack=0.02), ring=0.3)
    return place(rattles + [(0.22, refusal * 0.7)], 0.8)


def bump():
    """Walking into a wall."""
    return house.wood(7, 80, 0.03) * 0.8


def stairs(going_up):
    """Steps, each a soft footfall and a harp note, climbing - or going down - the scale."""
    scale = [57, 60, 62, 64, 67, 69] if going_up else [69, 67, 64, 62, 60, 57]
    parts = []
    for index, midi in enumerate(scale):
        parts.append((index * 0.11, house.wood(10 + index, 120, 0.015) * 0.3))
        parts.append((index * 0.11, harp(midi_hz(midi), seconds(0.5)) * 0.7))
    return place(parts, 1.1)


def pickup_key():
    """Bells: a small, bright jingle."""
    return notes([84, 88, 84, 88], 0.06, bell, ring=0.5) * 0.7


def pickup_scepter():
    """A harp sweeping up a major chord, a bell on top."""
    sweep = notes([60, 64, 67, 72, 76, 79], 0.04, harp, ring=0.7)
    return place([(0, sweep), (0.24, bell(midi_hz(84), seconds(1.0)) * 0.5)], 1.3)


def pickup_urn():
    """A low harp chord, broken, under strings."""
    broken = notes([48, 55, 60, 64], 0.07, harp, ring=0.9)
    return place([(0, broken), (0.05, chord([48, 55, 64], 1.0, strings) * 0.4)], 1.3)


def drop():
    """Setting something down: a low harp note."""
    return harp(midi_hz(43), seconds(0.4)) * 0.8


def urn_join():
    """Two pieces join: a harp glissando, up."""
    return notes([67, 69, 71, 74, 76, 79, 81, 83, 86, 88, 91], 0.03, harp, ring=0.8)


def urn_whole():
    """The urn is whole: the glissando, then strings and a bell ringing out."""
    glissando = notes([67, 69, 71, 74, 76, 79, 81, 83, 86, 88, 91, 95], 0.03, harp, ring=0.8)
    swell = chord([55, 67, 71, 74], 1.6, strings) * 0.6
    return place([(0, glissando), (0.3, swell), (0.36, bell(midi_hz(91), seconds(1.4)) * 0.4)], 2.0)


def caught():
    """Caught: a stab of clashing strings and a timpani hit, sliding away."""
    stab = chord([50, 51, 56, 57], 0.7, violin) * 0.8
    hit = timpani(seconds(0.9))
    fall_length = seconds(0.8)
    fall = strings(midi_hz(62), fall_length, attack=0.01) * np.linspace(1, 0, fall_length)
    return place([(0, stab), (0, hit), (0.15, fall * 0.4)], 1.1)


def thunder():
    """A crack and a roll: timpani under the storm's own rumble."""
    crack = scrape(30, 0.12, 400, 5000, 0.03)
    roll = sum(np.roll(timpani(seconds(1.6)), seconds(0.08) * hit) * (0.8 ** hit) for hit in range(5))
    rumble = house.thunder(31)[:seconds(1.8), 0]
    return place([(0, crack * 0.6), (0.02, roll * 0.5), (0.02, rumble)], 1.9)


def ghost():
    """Oooo: an organ chord that swells and sinks a semitone."""
    length = seconds(1.1)
    rising = np.minimum(1, np.arange(length) / seconds(0.4))
    first = chord([57, 60, 64], 0.55, organ)
    second = chord([56, 59, 63], 0.55, organ)
    return np.concatenate([first, second])[:length] * rising * 0.8


def bat():
    """Wings: a flurry on the harpsichord, high."""
    return notes([84, 81, 84, 81, 84, 81], 0.045, harpsichord, ring=0.15) * 0.7


def tarantula():
    """Legs: low strings plucked, scurrying."""
    return notes([40, 41, 40, 43, 41, 40, 41, 43, 44], 0.04, plucked, ring=0.12)


def plucked(freq, length):
    """Pizzicato: a string plucked, dying at once."""
    return strings(freq, length, attack=0.003) * decay(length, 0.04)


def footstep():
    """One step on old boards, quiet."""
    return house.wood(40, 120, 0.02)


EFFECTS = {"match_strike": match_strike, "match_out": match_out, "door_open": door_open,
           "door_close": door_close, "locked": locked, "bump": bump,
           "stairs_up": lambda: stairs(going_up=True), "stairs_down": lambda: stairs(going_up=False),
           "pickup_key": pickup_key, "pickup_scepter": pickup_scepter, "pickup_urn": pickup_urn,
           "drop": drop, "urn_join": urn_join, "urn_whole": urn_whole, "caught": caught, "thunder": thunder,
           "monster_ghost": ghost, "monster_bat": bat, "monster_tarantula": tarantula, "footstep": footstep}


def render_all():
    """Every effect, in the hall, at LEVEL (footsteps quieter)."""
    return {name: one_off_pcm(in_the_hall(make()), LEVEL * (QUIET if name == "footstep" else 1))
            for name, make in EFFECTS.items()}


def in_the_hall(track):
    """The orchestra's hall, with room for the echoes to ring out."""
    ringing = np.concatenate([track, np.zeros(seconds(0.3))])
    return hall(ringing[:, None])[:, 0]


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "shots", "effects")
    os.makedirs(out, exist_ok=True)
    for name, pcm in render_all().items():
        path = os.path.join(out, f"{name}-orchestra.wav")
        with wave.open(path, "wb") as out_file:
            out_file.setnchannels(2)
            out_file.setsampwidth(2)
            out_file.setframerate(RATE)
            out_file.writeframes(pcm.tobytes())
        print(f"{path}  {len(pcm) / RATE:.2f} s")


if __name__ == "__main__":
    main()
