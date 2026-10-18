"""Check game/sounds.py against the running game, and save what each sound sounds like.

Plays a short scene for every sound the game makes. In each, every frame, the model must predict the sound
bytes the game writes: the effect playing and its timer ($93, $90), the monster-near pitch and its
direction ($98, $92) and the thunder ($8F). Effects are started by game events at different moments of the
game's frame, so for a frame where an effect starts, the model may start it either before or after that
frame's sound update; which one fits is reported.

Each scene's audio is saved to shots/sounds/<scene>.wav (from your ROM - keep it to yourself), and the win
tune's notes are measured and compared with the pitches the model's registers give.

Usage: python tools/verify_sounds.py        (exit code 1 if anything disagrees)
"""

import copy
import os
import sys
import wave
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import BUTTON, HERE, JOY_DOWN, JOY_LEFT, JOY_RIGHT, JOY_UP, SELECT, SHOTS, Lab  # noqa: E402

sys.path.insert(0, HERE)
from game import monsters as model  # noqa: E402
from game import ram_map as M  # noqa: E402
from game import rom as R  # noqa: E402
from game import sounds as S  # noqa: E402

SOUND_BYTES = [S.EFFECT, S.EFFECT_TIME, S.MOOD_PITCH, S.MOOD_DIRECTION, S.THUNDER]
SOUNDS_FOLDER = os.path.join(SHOTS, "sounds")
NOTE_FRAMES = 16

rom = R.load()
problems = []
fits = Counter()          # (effect, "before"/"after") -> frames where that order fitted
effects_heard = Counter()


# --- the per-frame check -----------------------------------------------------------------------------
def candidates(before, after):
    """The sound bytes the model allows after this frame: no effect started, or the effect the game shows
    started before or after the sound update."""
    base = model.State(before)
    base[0xEB] = after[0xEB - 0x80]          # the random byte is stirred before the sound update
    plain = copy.deepcopy(base)
    S.sound_frame(plain, rom, False)
    options = [("none", plain)]
    started = after[S.EFFECT - 0x80]
    if started:
        first = copy.deepcopy(base)
        S.start_effect(first, rom, started)
        S.sound_frame(first, rom, False)
        options.append(("before", first))
        second = copy.deepcopy(base)
        S.sound_frame(second, rom, False)
        S.start_effect(second, rom, started)
        options.append(("after", second))
    return options


def check_frame(scene, before, after):
    for label, state in candidates(before, after):
        if all(state[address] == after[address - 0x80] for address in SOUND_BYTES):
            if label != "none":
                fits[(after[S.EFFECT - 0x80], label)] += 1
            effects_heard[after[S.EFFECT - 0x80]] += 1
            return
    problems.append((scene, {f"${a:02X}": (before[a - 0x80], after[a - 0x80]) for a in SOUND_BYTES}))


class Scene:
    """Runs frames for one scene, checking each and keeping the audio."""

    def __init__(self, lab, name):
        self.lab, self.name = lab, name
        self.audio = []
        lab.core.take_audio()

    def run(self, frames=1, held=(), park=True):
        for _ in range(frames):
            if park:
                far = (self.lab.peek(M.FLOOR) + 2) & 3
                for monster in range(5):
                    self.lab.poke(M.MONSTER_FLOOR + monster, far)
            before = self.lab.snapshot()
            self.lab.run(1, held)
            check_frame(self.name, before, self.lab.snapshot())
            self.audio.append(self.lab.core.take_audio())

    def walk_until(self, button, test, limit=300, park=True):
        for _ in range(limit):
            if test(self.lab):
                return True
            self.run(1, [button], park)
        return False

    def save(self):
        samples = np.concatenate(self.audio)
        rate = int(self.lab.core.av_info().timing.sample_rate)
        os.makedirs(SOUNDS_FOLDER, exist_ok=True)
        path = os.path.join(SOUNDS_FOLDER, f"{self.name}.wav")
        with wave.open(path, "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(samples.astype(np.int16).tobytes())
        return samples, rate


# --- the scenes --------------------------------------------------------------------------------------
def new_game(lab, game):
    while lab.peek(M.GAME_NUMBER) != game:
        lab.hold(SELECT, frames=2)
        lab.run(2)
    lab.reset()
    lab.run(3)
    return lab.save()


def scene_walls_and_doors(lab, start):
    """Game 2: game 1 makes no door sounds at all ($FCD1)."""
    lab.load(start)
    scene = Scene(lab, "bump-doorway-new-room")
    scene.walk_until(JOY_LEFT, lambda l: l.peek(M.POS_X) <= 0x60)
    scene.run(20, [JOY_LEFT])                                  # bumping the middle wall
    scene.walk_until(JOY_RIGHT, lambda l: l.peek(M.POS_X) >= 0x74)
    scene.walk_until(JOY_DOWN, lambda l: l.peek(M.ROOM) == 0)  # doorway, then the new room
    scene.run(30)
    scene.save()


def scene_stairs(lab, start):
    lab.load(start)
    scene = Scene(lab, "stairs-up-and-down")
    scene.walk_until(JOY_LEFT, lambda l: l.peek(M.POS_X) <= 0x74)
    scene.walk_until(JOY_DOWN, lambda l: l.peek(M.FLOOR) == 1)
    scene.run(70)
    scene.run(15, [JOY_UP])
    scene.walk_until(JOY_DOWN, lambda l: l.peek(M.FLOOR) == 0)
    scene.run(70)
    scene.save()


def scene_blocked(lab, start):
    lab.load(start)
    scene = Scene(lab, "blocked-by-a-locked-door")
    scene.walk_until(JOY_LEFT, lambda l: l.peek(M.POS_X) <= 0x74)
    scene.run(60, [JOY_DOWN])
    scene.save()


def place_item(lab, item, dx, dy):
    lab.poke(M.ITEM_FLOOR + item, lab.peek(M.FLOOR))
    lab.poke(M.ITEM_X + item, lab.peek(M.POS_X) + dx)
    lab.poke(M.ITEM_Y + item, lab.peek(M.POS_Y) + dy)


def scene_items(lab, start):
    lab.load(start)
    scene = Scene(lab, "pick-up-and-drop")
    place_item(lab, 1, 6, -2)
    scene.run(2, [BUTTON])
    scene.walk_until(JOY_RIGHT, lambda l: l.peek(M.CARRIED) == 1, limit=30)
    scene.run(20)
    scene.run(15, [JOY_LEFT])
    scene.run(2, [BUTTON])
    scene.run(30)
    scene.save()


def scene_urn(lab, start):
    lab.load(start)
    scene = Scene(lab, "urn-pieces-join-then-whole")
    lab.poke(M.CARRIED, 2)
    place_item(lab, 3, 6, -2)
    scene.run(2, [BUTTON])
    scene.walk_until(JOY_RIGHT, lambda l: l.peek(M.URN_SHAPES) == 5, limit=30)
    scene.run(40)
    place_item(lab, 4, 6, -2)
    lab.poke(M.FLAGS, lab.peek(M.FLAGS) | 0x40)  # keep the match lit
    lab.poke(M.MATCH_TIME, 20)
    scene.walk_until(JOY_RIGHT, lambda l: l.peek(M.URN_SHAPES) == 8, limit=40)
    scene.run(60)
    scene.save()


def scene_win(lab, start):
    lab.load(start)
    scene = Scene(lab, "win-tune")
    lab.poke(M.CARRIED, 2)
    for offset, shape in enumerate((8, 0xFF, 0xFF)):
        lab.poke(M.URN_SHAPES + offset, shape)
    scene.walk_until(JOY_RIGHT, lambda l: l.peek(M.GAME_STATE) == S.WON, limit=60)
    first_frame = len(scene.audio)
    clock_at_start = lab.peek(M.CLOCK)
    scene.run(NOTE_FRAMES * 8)
    samples, rate = scene.save()
    check_win_notes(scene, first_frame, clock_at_start, rate)


def check_win_notes(scene, first_frame, clock_at_start, rate):
    """Measure each note's pitch with an FFT and compare with the model's register values."""
    for note_number in range(4):
        frames = []
        for frame_index in range(first_frame, len(scene.audio)):
            clock = (clock_at_start + frame_index - first_frame + 1) & 0xFF
            if clock >> 4 & 3 == note_number and clock & 15 not in (0, 15):  # skip the edges of a note
                frames.append(scene.audio[frame_index])
        samples = np.concatenate(frames)[:, 0].astype(float)
        samples -= samples.mean()
        spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
        heard = np.fft.rfftfreq(len(samples), 1 / rate)[spectrum.argmax()]
        expected = S.pitch(S.PURE_TONE_6, R.table(rom, "WIN_TUNE")[note_number])
        close = abs(heard - expected) / expected < 0.03
        note_results.append((note_number, expected, heard, close))


def scene_thunder(lab, start):
    lab.load(start)
    scene = Scene(lab, "caught-thunder")
    for _ in range(120):
        lab.poke(M.MONSTER_FLOOR + 2, lab.peek(M.FLOOR))
        lab.poke(M.MONSTER_ROOM + 2, lab.peek(M.ROOM))
        lab.poke(M.MONSTER_X + 2, lab.peek(M.POS_X))
        lab.poke(M.MONSTER_Y + 2, lab.peek(M.POS_Y))
        scene.run(1, park=False)
        if lab.peek(M.GAME_STATE) == 1:
            break
    scene.run(300, park=False)
    scene.save()


def scene_monster_near(lab, start):
    lab.load(start)
    scene = Scene(lab, "monster-in-the-room")
    for frame in range(900):
        lab.poke(M.CARRIED, model.SCEPTER)  # so it stays without catching the player
        if frame < 600:
            lab.poke(M.MONSTER_FLOOR + 2, lab.peek(M.FLOOR))
            lab.poke(M.MONSTER_ROOM + 2, lab.peek(M.ROOM))
        else:
            lab.poke(M.MONSTER_FLOOR + 2, (lab.peek(M.FLOOR) + 2) & 3)
        scene.run(1, park=False)
    scene.save()


note_results = []


def report():
    print("effects seen in the scenes (frames):")
    for effect, count in sorted(effects_heard.items()):
        name = S.EFFECT_NAMES.get(effect, "none (footsteps / quiet)")
        orders = [order for (fitted, order), _count in fits.items() if fitted == effect]
        when = ", ".join(sorted(set(orders))) or "-"
        print(f"  {effect:2d} {name:26s} {count:5d}   starts {when} the sound update")
    for note_number, expected, heard, close in note_results:
        mark = "ok" if close else "WRONG"
        print(f"win tune note {note_number + 1}: model {expected:6.1f} Hz, heard {heard:6.1f} Hz  {mark}")
    for scene, detail in problems[:8]:
        print(f"MISMATCH in {scene}: (before, after) {detail}")
    total = sum(effects_heard.values()) + len(problems)
    print(f"\n{total - len(problems)}/{total} frames' sound bytes predicted; WAVs in {SOUNDS_FOLDER}")
    return len(problems) + sum(not close for *_rest, close in note_results)


def main():
    lab = Lab()
    game_1 = new_game(lab, 0)
    scene_walls_and_doors(lab, new_game(lab, 1))
    scene_stairs(lab, game_1)
    scene_items(lab, game_1)
    scene_urn(lab, game_1)
    scene_win(lab, game_1)
    scene_thunder(lab, game_1)
    scene_monster_near(lab, game_1)
    scene_blocked(lab, new_game(lab, 2))
    sys.exit(1 if report() else 0)


if __name__ == "__main__":
    main()
