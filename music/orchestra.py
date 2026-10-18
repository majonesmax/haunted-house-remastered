"""The SNES look's sound chip: a small gothic orchestra, in the spirit of the sampled instruments 16-bit games
had - pipe organ, harpsichord, strings, harp, bell, brass and timpani, in a hall.

It plays the same songs as music/chiptune.py (the same notation and the same style names), so any pack's
soundtrack sounds 16-bit in the SNES look. The instruments are made by FM and by adding up harmonics (the
FM helpers are from Adventure Forever's engine/fm.py).

    organ     an organ holds the chord over a pedal note; the melody on a brighter organ
    drive     a harpsichord arpeggiates; strings hold the chord; pizzicato bass; violin melody; timpani
    march     harpsichord chords on the off-beats over a walking bass; violin melody (a minuet)
    creep     a harp's broken chord over low strings; the melody on a bell
    tremolo   strings tremble on the root and the semitone above; violin melody
    fanfare   brass chords and timpani; a brass melody

Usage: python -m music.orchestra [PACK]   -> shots/music/<song>-orchestra.wav to listen to
"""

import os
import sys
import wave
from collections.abc import Sequence

import numpy as np

from music.chiptune import RATE, Song, Timing, chord_notes, load_songs, midi_hz, note_hz
from shared.types import Floats, Instrument, Samples

Pitch = float | Floats   # Hz: one, or one per sample

LEVEL = 12000
ORGAN_STOPS = ((1, 1.0), (2, 0.6), (3, 0.35), (4, 0.3), (6, 0.12), (8, 0.1))   # (harmonic, loudness)
STRING_HARMONICS = 8
JINGLE_RING = 2.0


# --- the instruments --------------------------------------------------------------------------------------
def envelope(length: int, attack: float = 0.005, decay: float = 0.6, sustain: float = 0.0,
             release: float = 0.05) -> Floats:
    seconds = np.arange(length) / RATE
    after_attack = sustain + (1 - sustain) * np.exp(-(seconds - attack) / decay)
    loudness = np.where(seconds < attack, seconds / max(attack, 1e-6), after_attack)
    release_samples = min(length, int(release * RATE))
    if release_samples:
        loudness[-release_samples:] *= np.linspace(1, 0, release_samples)
    return loudness


def fm(freq: Pitch, length: int, ratio: float = 1.0, index: float = 1.0, index_decay: float | None = None,
       detune: float = 0.0) -> Floats:
    """Two-operator FM: a sine carrier phase-modulated by a sine at freq * ratio."""
    seconds = np.arange(length) / RATE
    carrier = freq * (1 + detune)
    depth = index * (np.exp(-seconds / index_decay) if index_decay else 1.0)
    return np.sin(2 * np.pi * carrier * seconds + depth * np.sin(2 * np.pi * carrier * ratio * seconds))


def harmonics(freq: Pitch, length: int, stops: Sequence[tuple[int, float]], vibrato: float = 0.0,
              detune: float = 0.0) -> Floats:
    """A tone made by adding up harmonics (an organ's stops, a string's overtones)."""
    seconds = np.arange(length) / RATE
    wobble = 1 + vibrato * np.sin(2 * np.pi * 5.2 * seconds) * np.clip((seconds - 0.2) / 0.3, 0, 1)
    phase = 2 * np.pi * np.cumsum(freq * (1 + detune) * wobble) / RATE
    tone: Floats = np.zeros(length)
    for number, weight in stops:
        tone = tone + weight * np.sin(phase * number)
    return tone / sum(weight for _number, weight in stops)


def organ(freq: Pitch, length: int) -> Floats:
    chorus = 0.5 * (harmonics(freq, length, ORGAN_STOPS, detune=-0.002)
                    + harmonics(freq, length, ORGAN_STOPS, detune=0.002))
    return chorus * envelope(length, attack=0.03, decay=1.0, sustain=0.9, release=0.12)


def harpsichord(freq: Pitch, length: int) -> Floats:
    pluck = fm(freq, length, ratio=1.0, index=3.0, index_decay=0.05)
    buzz = 0.3 * fm(freq, length, ratio=3.0, index=1.5, index_decay=0.03)
    return (pluck + buzz) * envelope(length, attack=0.002, decay=0.35, sustain=0.05, release=0.03)


def strings(freq: Pitch, length: int, attack: float = 0.12) -> Floats:
    stops = [(number, 1 / number) for number in range(1, STRING_HARMONICS + 1)]  # a softened sawtooth
    tone = harmonics(freq, length, stops, vibrato=0.006, detune=0.001)
    return tone * envelope(length, attack=attack, decay=1.5, sustain=0.8, release=0.15)


def violin(freq: Pitch, length: int) -> Floats:
    return strings(freq, length, attack=0.04)


def harp(freq: Pitch, length: int) -> Floats:
    return fm(freq, length, ratio=1.0, index=0.8, index_decay=0.3) * envelope(length, decay=0.9, release=0.05)


def bell(freq: Pitch, length: int) -> Floats:
    return fm(freq, length, ratio=3.5, index=2.0, index_decay=0.9) * envelope(length, decay=2.0, release=0.2)


def brass(freq: Pitch, length: int) -> Floats:
    tone = fm(freq, length, ratio=1.0, index=2.6) * 0.7 + fm(freq, length, ratio=2.0, index=0.8) * 0.3
    return tone * envelope(length, attack=0.05, decay=0.8, sustain=0.75, release=0.08)


def timpani(length: int) -> Floats:
    seconds = np.arange(length) / RATE
    freqs = 58 + 30 * np.exp(-seconds / 0.05)
    return np.sin(2 * np.pi * np.cumsum(freqs) / RATE) * np.exp(-seconds / 0.35)


def snare(length: int, rng: np.random.Generator) -> Floats:
    seconds = np.arange(length) / RATE
    return np.convolve(rng.uniform(-1, 1, length), np.ones(4) / 4, "same") * np.exp(-seconds / 0.08) * 0.5


def hat(length: int, rng: np.random.Generator) -> Floats:
    seconds = np.arange(length) / RATE
    return np.diff(rng.uniform(-1, 1, length), prepend=0) * np.exp(-seconds / 0.02) * 0.15


MELODY_VOICE = {"organ": organ, "drive": violin, "march": violin, "creep": bell, "tremolo": violin,
                "fanfare": brass}


# --- arranging a song ---------------------------------------------------------------------------------------
class Parts:
    """The song's four layers, each a track of samples."""

    def __init__(self, length: int):
        self.melody: Floats = np.zeros(length)
        self.chords: Floats = np.zeros(length)
        self.bass: Floats = np.zeros(length)
        self.drums: Floats = np.zeros(length)

    def add(self, track_name: str, start: int, sound: Floats) -> None:
        track = getattr(self, track_name)
        end = min(len(track), start + len(sound))
        track[start:end] += sound[:end - start]


def render(song: Song) -> Samples:
    """A song (chiptune.py's notation) -> int16 stereo samples of one pass; a loop loops cleanly."""
    song = {"drums": "", "style": "march", "loop": True, **song}
    timing = Timing(song)
    chords = song["chords"].split()
    total = len(chords) * timing.bar
    parts = Parts(total + int(JINGLE_RING * RATE))
    rng = np.random.default_rng(13)
    tokens = [token for bar in song["melody"].split("|") for token in bar.split()]
    add_melody(parts, tokens, MELODY_VOICE.get(song["style"], violin), timing)
    for bar, symbol in enumerate(chords):
        root, intervals = chord_notes(symbol)
        tones = [root + interval for interval in intervals]
        accompany(parts, song["style"], root, tones, bar * timing.bar, timing)
        add_drums(parts, song["drums"], bar * timing.bar, timing, rng)
    return mix_down(parts, total, song["loop"])


def add_melody(parts: Parts, tokens: list[str], voice: Instrument, timing: Timing) -> None:
    index = 0
    while index < len(tokens):
        after = index + 1
        while after < len(tokens) and tokens[after] == "-":
            after += 1
        if tokens[index] not in ("-", "."):
            start = timing.at(2 * index)
            length = timing.at(2 * after) - start + int(0.15 * RATE)  # let each note ring a little
            parts.add("melody", start, voice(note_hz(tokens[index]), length))
        index = after


def accompany(parts: Parts, style: str, root: int, tones: list[int], bar_start: int, timing: Timing) -> None:
    """Everything but the melody and drums for one bar, in the style's arrangement."""
    ARRANGEMENTS.get(style, creep)(parts, root, tones, bar_start, timing, style)


def held_organ(parts: Parts, root: int, tones: list[int], bar_start: int, timing: Timing,
               _style: str) -> None:
    for midi in tones:
        parts.add("chords", bar_start, organ(midi_hz(midi + 12), timing.bar) * 0.5)
    parts.add("bass", bar_start, organ(midi_hz(root - 12), timing.bar))


def driving(parts: Parts, root: int, tones: list[int], bar_start: int, timing: Timing, style: str) -> None:
    arpeggiate(parts, tones, bar_start, timing, brass if style == "fanfare" else harpsichord)
    for midi in tones:
        parts.add("chords", bar_start, strings(midi_hz(midi + 12), timing.bar) * 0.25)
    for sixteenth in range(0, 16, 4):
        parts.add("bass", bar_start + timing.at(sixteenth), harp(midi_hz(root - 12), timing.at(4)))


def minuet(parts: Parts, root: int, tones: list[int], bar_start: int, timing: Timing, _style: str) -> None:
    for sixteenth in (2, 6, 10, 14):
        for midi in tones:
            chord_note = harpsichord(midi_hz(midi + 12), timing.at(2)) * 0.45
            parts.add("chords", bar_start + timing.at(sixteenth), chord_note)
    for sixteenth, offset in ((0, -12), (4, -5), (8, -12), (12, -5)):
        parts.add("bass", bar_start + timing.at(sixteenth), harp(midi_hz(root + offset), timing.at(4)))


def trembling(parts: Parts, root: int, tones: list[int], bar_start: int, timing: Timing, _style: str) -> None:
    for sixteenth in range(16):
        midi = tones[0] + 12 + sixteenth % 2
        shiver = strings(midi_hz(midi), timing.at(1), attack=0.01) * 0.5
        parts.add("chords", bar_start + timing.at(sixteenth), shiver)
    parts.add("bass", bar_start, strings(midi_hz(root - 12), timing.bar))


def creep(parts: Parts, root: int, tones: list[int], bar_start: int, timing: Timing, _style: str) -> None:
    for sixteenth in range(0, 16, 2):
        midi = tones[(sixteenth // 2) % len(tones)] + 12
        parts.add("chords", bar_start + timing.at(sixteenth), harp(midi_hz(midi), timing.at(6)) * 0.6)
    parts.add("bass", bar_start, strings(midi_hz(root - 12), timing.bar) * 0.8)


ARRANGEMENTS = {"organ": held_organ, "drive": driving, "fanfare": driving, "march": minuet,
                "tremolo": trembling, "creep": creep}


def arpeggiate(parts: Parts, tones: list[int], bar_start: int, timing: Timing, voice: Instrument) -> None:
    sequence = tones + [tones[0] + 12, tones[1] + 12]
    for sixteenth in range(16):
        midi = sequence[sixteenth % len(sequence)] + 12
        parts.add("chords", bar_start + timing.at(sixteenth), voice(midi_hz(midi), timing.at(2)) * 0.4)


def add_drums(parts: Parts, pattern: str, bar_start: int, timing: Timing, rng: np.random.Generator) -> None:
    for sixteenth, kind in enumerate(pattern):
        start = bar_start + timing.at(sixteenth)
        length = int(0.4 * RATE)
        if kind == "k":
            parts.add("drums", start, timpani(length))
        elif kind == "s":
            parts.add("drums", start, snare(length, rng))
        elif kind == "h":
            parts.add("drums", start, hat(length, rng))


def hall(pcm: Floats, delays: tuple[float, ...] = (0.031, 0.047, 0.071, 0.113, 0.173), feedback: float = 0.45,
         mix: float = 0.28) -> Floats:
    """A small hall: a few echoes at uneven delays, each fed back a few times."""
    out = pcm.copy()
    for delay_seconds in delays:
        delay = int(delay_seconds * RATE)
        echo = np.zeros_like(pcm)
        for repeat in range(1, 5):
            shift = delay * repeat
            if shift >= len(pcm):
                break
            echo[shift:] += pcm[:-shift] * feedback ** repeat
        out += echo * mix / len(delays)
    return out


def mix_down(parts: Parts, total: int, loop: bool) -> Samples:
    left = 0.34 * parts.melody + 0.26 * parts.chords * 0.9 + 0.3 * parts.bass + 0.22 * parts.drums
    right = 0.3 * parts.melody + 0.26 * parts.chords * 1.1 + 0.3 * parts.bass + 0.22 * parts.drums
    pcm = hall(np.stack([left, right], axis=1))
    if loop:  # the ringing tail wraps onto the start, so the loop is seamless
        tail = len(pcm) - total
        body = pcm[:total].copy()
        body[:tail] += pcm[total:total + tail][:total]
        pcm = body
        fade_out, fade_in = int(0.008 * RATE), int(0.002 * RATE)
        pcm[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
        pcm[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    else:
        pcm[-int(0.6 * RATE):] *= np.linspace(1, 0, int(0.6 * RATE))[:, None]
    pcm *= LEVEL / max(1e-9, np.abs(pcm).max())
    return pcm.astype(np.int16)


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pack = sys.argv[1] if len(sys.argv) > 1 else "classic"
    out = os.path.join(root, "shots", "music")
    os.makedirs(out, exist_ok=True)
    for name, song in load_songs(os.path.join(root, "packs", pack)).items():
        pcm = render(song)
        if song.get("loop", True):
            pcm = np.concatenate([pcm, pcm])
        path = os.path.join(out, f"{name}-orchestra.wav")
        with wave.open(path, "wb") as out_file:
            out_file.setnchannels(2)
            out_file.setsampwidth(2)
            out_file.setframerate(RATE)
            out_file.writeframes(pcm.tobytes())
        print(f"{path}  {len(pcm) / RATE:.1f} s")


if __name__ == "__main__":
    main()
