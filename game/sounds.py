"""The game's sound, rewritten in Python: which TIA sound registers it sets each frame, and why.

The 2600 makes sound with two channels, each set by three registers: control (the kind of sound: pure
tone, buzz, noise), frequency (a divider - higher = lower pitch) and volume (0-15). Haunted House sets them
once a frame ($F75E-$F88B). A remaster can feed these numbers to a TIA sound emulator to sound exactly like
the original, or use the events to trigger sounds of its own.

Channel 0 - the mood:
  - a monster in your room: noise whose pitch and loudness wander at random ($98), dying away after
  - while you die: a thunder rumble of random length ($8F)
  - when you win: a four-note tune, each note 16 frames
Channel 1 - the effects ($93, timed by $90; numbers are the game's own):
  2 blocked (locked door, or the front door without the urn), 3 bump into a wall, 4 into a doorway,
  5 drop, 6 pick up, 7 urn pieces join, 8 into a new room, 9 stairs up, 10 stairs down, 11 the urn whole;
  and when no effect plays, footsteps: a click on 3 frames in 8 while the stick is pushed.

tools/verify_sounds.py checks the model against the running game.
"""

from game import ram_map as M
from game import rom as R

EFFECT, EFFECT_TIME = 0x93, 0x90
MOOD_PITCH, MOOD_DIRECTION, THUNDER = 0x98, 0x92, 0x8F
MOOD_SILENT = 0x7F
BLOCKED, BUMP, DOORWAY, DROP, PICK_UP, JOIN, NEW_ROOM, STAIRS_UP, STAIRS_DOWN, URN_WHOLE = range(2, 12)
EFFECT_NAMES = {BLOCKED: "blocked", BUMP: "bump", DOORWAY: "doorway", DROP: "drop", PICK_UP: "pick up",
                JOIN: "urn pieces join", NEW_ROOM: "new room", STAIRS_UP: "stairs up",
                STAIRS_DOWN: "stairs down", URN_WHOLE: "urn whole"}
NOISE, PURE_TONE_6, BUZZ_31, SILENT_HIGH = 8, 12, 6, 11  # TIA control values used here
WON = 0x44
TIA_CLOCK = 31440        # Hz, the NTSC sound clock (colour clock / 114)


def start_effect(state, rom, effect):
    """Start an effect ($F88C): the same one already playing isn't restarted, and a bump never cuts
    another effect short."""
    if effect == state[EFFECT]:
        return
    if effect == BUMP and state[EFFECT]:
        return
    state[EFFECT] = effect
    state[EFFECT_TIME] = R.table(rom, "SOUND_LENGTHS")[effect]


def sound_frame(state, rom, stick_pushed):
    """One frame of sound: update the sound bytes in RAM and return the registers it sets:
    ((control 0, frequency 0, volume 0), (control 1, frequency 1, volume 1))."""
    channel_0 = mood(state, rom)
    channel_1 = effects(state, rom, stick_pushed)
    return channel_0, channel_1


# --- channel 0 ---------------------------------------------------------------------------------------
def mood(state, rom):
    game_state = state[M.GAME_STATE]
    if game_state:
        return thunder_or_tune(state, rom)
    if not state[M.MONSTERS_HERE]:
        if state[MOOD_PITCH] == MOOD_SILENT:
            return (0, 0, 0)
        state[MOOD_DIRECTION] = 0  # nobody here: drift back up to silence
    pitch = state[MOOD_PITCH]       # the sound uses the value from before this frame's step
    wander_mood(state, rom)
    frequency = (pitch >> 3 | 0x10) & 0xFF
    return (NOISE, frequency & 0x1F, (frequency ^ 0x0F) & 0x0F)


def wander_mood(state, rom):
    """$98 walks up or down a step a frame; at every multiple of 16 it may turn, at random ($F773)."""
    pitch = state[MOOD_PITCH]
    if pitch == MOOD_SILENT or (pitch & 0x0F == 0 and (pitch == 0 or pitch & 0x80)):
        state[MOOD_DIRECTION] = pitch
    elif pitch & 0x0F == 0:
        state[MOOD_DIRECTION] = R.byte_at(rom, R.ROM_START + state[0xEB]) & 1  # a random bit from the code
    if state[MOOD_DIRECTION]:
        state[MOOD_PITCH] = pitch - 1
    else:
        state[MOOD_PITCH] = pitch + 1


def thunder_or_tune(state, rom):
    game_state = state[M.GAME_STATE]
    if game_state & 1:  # dying: rumbles of random length, with a silent frame between
        if state[THUNDER] == 0:
            state[THUNDER] = ((state[0xEB] & 0x70) >> 2) + 0x10
            return (0, 0, 0)
        frequency = state[THUNDER] ^ 0xFF
        state[THUNDER] -= 1
        return (NOISE, frequency & 0x1F, 0x0C)
    if game_state == WON:
        note = state[M.CLOCK] >> 4 & 3
        return (PURE_TONE_6, R.table(rom, "WIN_TUNE")[note], 9)
    return (0, 0, 0)


# --- channel 1 ---------------------------------------------------------------------------------------
def effects(state, rom, stick_pushed):
    if state[M.GAME_STATE]:
        return (0, 0, 0)
    effect, time = state[EFFECT], state[EFFECT_TIME]
    if time == 0:
        state[EFFECT] = 0
        return footsteps(state, stick_pushed)
    state[EFFECT_TIME] = time - 1
    time -= 1
    return effect_registers(rom, effect, time)


# Each effect's registers, as (control, frequency, volume) worked out from `time`, the frames left:
SIMPLE_EFFECTS = {
    BLOCKED: lambda time: (6, 8, (time ^ 3) & 0x0F),        # a buzz fading in and out
    BUMP: lambda time: (2, 8, time & 0x0F),                 # a short fading thud
    DOORWAY: lambda time: (NOISE, 6, 0x0F),                 # one frame of loud noise
    DROP: lambda time: (BUZZ_31, (time ^ 3) & 0x1F, 8),     # a quick pitch blip
    PICK_UP: lambda time: (BUZZ_31, time & 0x1F, 8),        # the same blip, the other way
    JOIN: lambda time: (4, 8, time & 0x0F),                 # a fading tone
    NEW_ROOM: lambda time: (NOISE, 8, time & 0x0F),         # a fading hiss
}


def effect_registers(rom, effect, time):
    """(control, frequency, volume) of an effect, `time` frames from its end."""
    if effect in SIMPLE_EFFECTS:
        return SIMPLE_EFFECTS[effect](time)
    if effect in (STAIRS_UP, STAIRS_DOWN):
        step = time >> 4                       # four notes of 16 frames each...
        if effect == STAIRS_DOWN:
            step ^= 3                          # ...played the other way round going down
        return (BUZZ_31, R.table(rom, "STAIRS_TONES")[step], 0x0A)
    if effect == URN_WHOLE and time & 4:       # pulses: 4 frames on, 4 off
        return (BUZZ_31, 1, time & 0x0F)
    return (0, 0, 0)


def footsteps(state, stick_pushed):
    if stick_pushed and state[M.CLOCK] & 7 < 3:
        return (SILENT_HIGH, 0x18, 0x0F)  # control 11 holds the output high: each step is a click
    return (0, 0, 0)


# --- what the registers sound like -------------------------------------------------------------------
def pitch(control, frequency):
    """The note (Hz) a pure-tone setting plays, or None for noise and buzz-like settings."""
    dividers = {4: 2, 5: 2, 12: 6, 13: 6, 6: 31, 10: 31}
    if control not in dividers:
        return None
    return TIA_CLOCK / (dividers[control] * (frequency + 1))
