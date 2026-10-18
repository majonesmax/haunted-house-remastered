"""An NES-style synth: renders a song written as text into sound. (From Adventure Forever's
engine/chiptune.py, with two more arrangement styles for a gothic score: organ and tremolo.)

Voices, like the NES sound chip: pulse 1 (melody, 25% duty, gentle vibrato), pulse 2 (the harmony: arpeggios,
stabs, held chords - by style), a 4-bit stepped triangle (bass, and the kick drum as a fast pitch drop),
noise (snare, hi-hat).

A song is a dict: bpm, style, loop (False for a jingle that plays once), chords (one per bar), a melody in
eighth notes and a drum pattern in sixteenths. Melody tokens: a note like E5 / F#4 / Bb5, "-" holds the
previous note, "." rests; "|" between bars is only for reading. Drums (16 a bar): k kick, s snare, h hi-hat.

Styles (how the bass and harmony are played):
    drive     sixteenth-note arpeggios over a driving octave bass
    anthem    the same arpeggios over a walking bass
    march     off-beat chord stabs over a walking bass
    creep     a slow broken chord over a long low root
    organ     the chord held all bar, over a held pedal note
    tremolo   a shiver between the root and the note a semitone up, over pulsing eighths
    fanfare   arpeggios over a walking bass, ringing out at the end

Usage: python music/chiptune.py [PACK]     -> shots/music/<song>.wav for each of a pack's songs (twice
                                              round, if it loops), to listen to
"""

from __future__ import annotations

import json
import os
import sys
import wave
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:   # only for the type checker: this file also runs as a script, outside the package
    from shared.types import Floats, Samples

Song = dict[str, Any]   # a song, as a pack's music.json writes it (see above)

RATE = 31440  # the emulator's own sample rate, so music adds straight onto the game's sound
NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
CHORDS = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "dim": (0, 3, 6),
          "aug": (0, 4, 8), "sus4": (0, 5, 7)}
LEVEL = 12000           # a typical NES-music level, under the 2600's sound effects
JINGLE_RING = 1.5       # seconds a jingle rings on after its last bar


def note_hz(name: str) -> float:
    """'F#4' / 'Bb5' / 'C6' -> Hz (A4 = 440)."""
    letter, rest = name[0], name[1:]
    semitone = NOTE[letter]
    while rest and rest[0] in "#b":
        semitone += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    midi = 12 * (int(rest) + 1) + semitone
    return midi_hz(midi)


def chord_notes(symbol: str) -> tuple[int, tuple[int, ...]]:
    """'Am' -> (root as a MIDI note in octave 3, intervals); 'Bb' / 'F#m' / 'D#dim' work too."""
    root = symbol[0]
    accidental = symbol[1] if len(symbol) > 1 and symbol[1] in "#b" else ""
    quality = symbol[1 + len(accidental):]
    semitone = NOTE[root] + {"#": 1, "b": -1, "": 0}[accidental]
    return 48 + semitone, CHORDS[quality]


def midi_hz(midi: float) -> float:
    """A MIDI note number (69 = A4) -> Hz."""
    return 440.0 * 2 ** ((midi - 69) / 12)


def pulse(freq: float | Floats, length: int, duty: float, vibrato: float = 0.0) -> Floats:
    """A square-ish wave, high for `duty` of each cycle; vibrato fades in after 0.15 s."""
    seconds = np.arange(length) / RATE
    wobble = vibrato * np.sin(2 * np.pi * 5.5 * seconds) * np.clip((seconds - 0.15) / 0.2, 0, 1)
    phase = (np.cumsum(freq * (1 + wobble)) / RATE) % 1.0
    return np.where(phase < duty, 1.0, -1.0)


def triangle(freq: float | Floats, length: int) -> Floats:
    """The NES triangle: 16 steps up and down."""
    if np.ndim(freq) == 0:
        freq = np.full(length, freq)
    phase = (np.cumsum(freq) / RATE) % 1.0
    wave_shape = 1 - 4 * np.abs(phase - 0.5)
    return np.round((wave_shape + 1) * 7.5) / 7.5 - 1


def envelope(length: int, attack: float = 0.004, decay: float = 0.18, sustain: float = 0.55,
             release: float = 0.03) -> Floats:
    """A note's loudness over time: a rise, a fall to `sustain`, a short fade at the end."""
    seconds = np.arange(length) / RATE
    after_attack = sustain + (1 - sustain) * np.exp(-(seconds - attack) / decay)
    loudness = np.where(seconds < attack, seconds / attack, after_attack)
    release_samples = int(release * RATE)
    if length > release_samples:
        loudness[-release_samples:] *= np.linspace(1, 0, release_samples)
    return loudness


def drum(kind: str, length: int, rng: np.random.Generator) -> Floats:
    seconds = np.arange(length) / RATE
    if kind == "k":  # the triangle, its pitch dropping fast
        freqs = 55 + 120 * np.exp(-seconds / 0.03)
        return triangle(freqs, length) * np.exp(-seconds / 0.09) * 1.1
    noise = rng.choice([-1.0, 1.0], length)
    if kind == "s":
        return noise * np.exp(-seconds / 0.07) * 0.7
    if kind == "h":
        return noise * np.exp(-seconds / 0.018) * 0.35
    return np.zeros(length)


class Timing:
    """A song's tempo in samples: a sixteenth note, a bar."""

    def __init__(self, song: Song):
        self.step: float = 60.0 / song["bpm"] / 4  # a sixteenth note, in seconds
        self.bar: int = int(round(16 * self.step * RATE))

    def at(self, sixteenth: float) -> int:
        """A sixteenth-note index -> the sample it starts on."""
        return int(round(sixteenth * self.step * RATE))


def render(song: Song) -> Samples:
    """A song (a dict, as above) -> int16 stereo samples of one pass; a looping song loops cleanly."""
    song = {"drums": "", "style": "march", "loop": True, **song}
    timing = Timing(song)
    chords = song["chords"].split()
    total = len(chords) * timing.bar
    tail = 0 if song["loop"] else int(JINGLE_RING * RATE)
    lead, harmony, bass, drums = (np.zeros(total + tail) for _ in range(4))
    rng = np.random.default_rng(7)
    melody = [token for bar in song["melody"].split("|") for token in bar.split()]
    add_melody(lead, melody, timing, total + tail)
    for bar, symbol in enumerate(chords):
        root, intervals = chord_notes(symbol)
        start = bar * timing.bar
        tones = [root + interval for interval in intervals]
        add_bass(bass, song["style"], root, start, timing)
        add_harmony(harmony, song["style"], tones, start, timing)
        last_bar_of_jingle = not song["loop"] and bar == len(chords) - 1
        if not last_bar_of_jingle:
            add_drums(drums, song["drums"], start, timing, rng)
    return mix_down(lead, harmony, bass, drums, song["loop"])


def add_melody(lead: Floats, tokens: list[str], timing: Timing, length: int) -> None:
    """Pulse 1: eighth-note tokens; "-" holds the note before it, "." rests."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        after = index + 1
        while after < len(tokens) and tokens[after] == "-":
            after += 1
        if token not in ("-", "."):
            start, end = timing.at(2 * index), min(timing.at(2 * after), length)
            note = pulse(note_hz(token), end - start, 0.25, vibrato=0.004)
            lead[start:end] += note * envelope(end - start, sustain=0.6)
        index = after


BASS_PATTERNS = {  # style -> (sixteenth, semitones from the root) for each bass note of a bar
    "march": [(0, -12), (4, -5), (8, -12), (12, -5)],
    "anthem": [(0, -12), (4, -5), (8, -12), (12, -5)],
    "fanfare": [(0, -12), (4, -5), (8, -12), (12, -5)],
    "drive": [(step, -12 if step % 4 == 0 else 0) for step in range(0, 16, 2)],
    "tremolo": [(step, -12) for step in range(0, 16, 2)],
    "organ": [(0, -12)],
    "creep": [(0, -12), (12, -10)],
}


def add_bass(bass: Floats, style: str, root: int, bar_start: int, timing: Timing) -> None:
    """The triangle: the chord's root an octave down, in the style's pattern."""
    pattern = BASS_PATTERNS.get(style, BASS_PATTERNS["creep"])
    for index, (sixteenth, offset) in enumerate(pattern):
        until = pattern[index + 1][0] if index + 1 < len(pattern) else 16
        start = bar_start + timing.at(sixteenth)
        end = bar_start + timing.at(until) - int(0.01 * RATE)  # a tiny gap between notes
        note = triangle(midi_hz(root + offset), end - start)
        bass[start:end] += note * envelope(end - start, decay=0.5, sustain=0.85, release=0.01)


def add_harmony(harmony: Floats, style: str, tones: list[int], bar_start: int, timing: Timing) -> None:
    """Pulse 2, by style."""
    if style in ("anthem", "drive", "fanfare"):
        arpeggio(harmony, tones, bar_start, timing)
    elif style == "march":
        stabs(harmony, tones, bar_start, timing)
    elif style == "organ":
        held_chord(harmony, tones, bar_start, timing)
    elif style == "tremolo":
        shiver(harmony, tones, bar_start, timing)
    else:
        broken_chord(harmony, tones, bar_start, timing)


def arpeggio(harmony: Floats, tones: list[int], bar_start: int, timing: Timing) -> None:
    """Sixteenth notes up the chord and on, an octave up."""
    sequence = tones + [tones[0] + 12, tones[1] + 12]
    for sixteenth in range(16):
        midi = sequence[sixteenth % len(sequence)] + 12
        start, end = bar_start + timing.at(sixteenth), bar_start + timing.at(sixteenth + 1)
        note = pulse(midi_hz(midi), end - start, 0.125)
        harmony[start:end] += note * envelope(end - start, decay=0.05, sustain=0.3, release=0.005)


def stabs(harmony: Floats, tones: list[int], bar_start: int, timing: Timing) -> None:
    """Short chords on the off-beats."""
    for sixteenth in (2, 6, 10, 14):
        start, end = bar_start + timing.at(sixteenth), bar_start + timing.at(sixteenth + 1)
        for midi in tones:
            note = pulse(midi_hz(midi + 12), end - start, 0.125)
            harmony[start:end] += note * envelope(end - start, decay=0.04, sustain=0.2, release=0.005) * 0.5


def held_chord(harmony: Floats, tones: list[int], bar_start: int, timing: Timing) -> None:
    """The whole chord, held all bar like an organ: a slow swell, half-duty pulses."""
    start, end = bar_start, bar_start + timing.bar - int(0.02 * RATE)
    for midi in tones:
        note = pulse(midi_hz(midi + 12), end - start, 0.5)
        harmony[start:end] += note * envelope(end - start, attack=0.06, decay=0.8, sustain=0.8) * 0.4


def shiver(harmony: Floats, tones: list[int], bar_start: int, timing: Timing) -> None:
    """Sixteenths between the root and the note a semitone above: dread."""
    root = tones[0] + 12
    for sixteenth in range(16):
        midi = root + (sixteenth % 2)
        start, end = bar_start + timing.at(sixteenth), bar_start + timing.at(sixteenth + 1)
        note = pulse(midi_hz(midi), end - start, 0.125)
        harmony[start:end] += note * envelope(end - start, decay=0.04, sustain=0.35, release=0.005)


def broken_chord(harmony: Floats, tones: list[int], bar_start: int, timing: Timing) -> None:
    """The chord one note at a time, in eighths."""
    for sixteenth in range(0, 16, 2):
        midi = tones[(sixteenth // 2) % len(tones)] + 12
        start, end = bar_start + timing.at(sixteenth), bar_start + timing.at(sixteenth + 2)
        note = pulse(midi_hz(midi), end - start, 0.125)
        harmony[start:end] += note * envelope(end - start, decay=0.12, sustain=0.25)


def add_drums(drums: Floats, pattern: str, bar_start: int, timing: Timing, rng: np.random.Generator) -> None:
    """One bar of the drum pattern."""
    for sixteenth, kind in enumerate(pattern):
        if kind == ".":
            continue
        start = bar_start + timing.at(sixteenth)
        length = min(int(0.2 * RATE), len(drums) - start)
        drums[start:start + length] += drum(kind, length, rng)


def mix_down(lead: Floats, harmony: Floats, bass: Floats, drums: Floats, loop: bool) -> Samples:
    """The four voices -> int16 stereo, pulse 2 a touch to the right; faded so it loops (or ends) cleanly."""
    left = 0.24 * lead + 0.09 * harmony + 0.30 * bass + 0.16 * drums
    right = 0.24 * lead + 0.11 * harmony + 0.30 * bass + 0.16 * drums
    pcm = np.stack([left, right], axis=1)
    pcm *= LEVEL / max(1e-9, np.abs(pcm).max())
    if loop:  # no click where the loop wraps: 8 ms out at the end, 2 ms in at the start
        pcm[-int(0.008 * RATE):] *= np.linspace(1, 0, int(0.008 * RATE))[:, None]
        pcm[:int(0.002 * RATE)] *= np.linspace(0, 1, int(0.002 * RATE))[:, None]
    else:  # a jingle rings out, then fades to silence instead of stopping dead
        pcm[-int(0.3 * RATE):] *= np.linspace(1, 0, int(0.3 * RATE))[:, None]
    return pcm.astype(np.int16)


def load_songs(pack_folder: str) -> dict[str, Song]:
    """A pack's soundtrack (its music.json: {"songs": {moment: song}}), or {} if it has none."""
    path = os.path.join(pack_folder, "music.json")
    if not os.path.isfile(path):
        return {}
    with open(path) as music_file:
        return json.load(music_file)["songs"]


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = sys.argv[1] if len(sys.argv) > 1 else "classic"
    out = os.path.join(root, "shots", "music")
    os.makedirs(out, exist_ok=True)
    for name, song in load_songs(os.path.join(root, "packs", pack)).items():
        pcm = render(song)
        if song.get("loop", True):
            pcm = np.concatenate([pcm, pcm])
        path = os.path.join(out, f"{name}.wav")
        with wave.open(path, "wb") as out_file:
            out_file.setnchannels(2)
            out_file.setsampwidth(2)
            out_file.setframerate(RATE)
            out_file.writeframes(pcm.tobytes())
        print(f"{path}  {len(pcm) / RATE:.1f} s")


if __name__ == "__main__":
    main()
