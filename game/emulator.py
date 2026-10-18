"""The emulator: the Stella (Atari 2600) libretro core, loaded as a library and run one frame at a time.

Between frames the console is ours to read. The 2600 has no screen memory (the game draws each scanline as
the TV beam passes), so the whole machine state is just 128 bytes of RAM ($80-$FF) - the standard libretro
call retro_get_memory_data(SYSTEM_RAM) hands us a pointer to it, no core-specific symbols needed.

    core = Core(); core.load(rom_path)
    core.joy.add(JOY_UP); core.run()       # one frame with the joystick pushed up
    core.ram                               # the 128 bytes, live (indexed from $80)
    core.frame                             # the 2600's picture, 160x228 RGB
    AudioOut(rate).push(core.take_audio()) # play the game's sound

The core binary goes in cores/ (tools/get_core.sh). tools/ram_viewer.py is a raw viewer built on this.
"""

import atexit
import ctypes as C
import os
import threading
import time

import numpy as np
import sounddevice as sd

from game import paths

HERE, CORE, FROZEN = paths.ROOT, paths.CORE, paths.FROZEN
USER_DIR, SHOTS_DIR = paths.USER_DIR, paths.SCREENSHOTS
SYSTEM_DIR = os.fsencode(os.path.join(USER_DIR, "cores", "system"))
SAVE_DIR = os.fsencode(os.path.join(USER_DIR, "cores", "save"))
for _folder in (SYSTEM_DIR, SAVE_DIR):
    os.makedirs(_folder, exist_ok=True)

# libretro constants (libretro.h)
ENV_SET_ROTATION, ENV_GET_CAN_DUPE, ENV_GET_SYSTEM_DIRECTORY, ENV_SET_PIXEL_FORMAT = 1, 3, 9, 10
ENV_GET_VARIABLE, ENV_SET_VARIABLES, ENV_GET_VARIABLE_UPDATE = 15, 16, 17
ENV_GET_LOG_INTERFACE, ENV_GET_CORE_ASSETS_DIRECTORY, ENV_GET_SAVE_DIRECTORY = 27, 30, 31
OPTION_OVERRIDES = {}
PIXEL_0RGB1555, PIXEL_XRGB8888, PIXEL_RGB565 = 0, 1, 2
DEVICE_JOYPAD = 1
JOY_B, JOY_SELECT, JOY_START, JOY_UP, JOY_DOWN, JOY_LEFT, JOY_RIGHT = 0, 2, 3, 4, 5, 6, 7
MEMORY_SYSTEM_RAM = 2


class GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t), ("meta", C.c_char_p)]


class Geometry(C.Structure):
    _fields_ = [("base_width", C.c_uint), ("base_height", C.c_uint), ("max_width", C.c_uint),
                ("max_height", C.c_uint), ("aspect_ratio", C.c_float)]


class Timing(C.Structure):
    _fields_ = [("fps", C.c_double), ("sample_rate", C.c_double)]


class AVInfo(C.Structure):
    _fields_ = [("geometry", Geometry), ("timing", Timing)]


class Variable(C.Structure):
    _fields_ = [("key", C.c_char_p), ("value", C.c_char_p)]


class SystemInfo(C.Structure):
    _fields_ = [("name", C.c_char_p), ("version", C.c_char_p), ("extensions", C.c_char_p),
                ("need_fullpath", C.c_bool), ("block_extract", C.c_bool)]


ENV_CB = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
VIDEO_CB = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
AUDIO_CB = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
AUDIO_BATCH_CB = C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)
POLL_CB = C.CFUNCTYPE(None)
STATE_CB = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)
# retro_log_printf_t is variadic; on arm64 the named args (level, fmt) arrive in registers: log the format
LOG_CB = C.CFUNCTYPE(None, C.c_int, C.c_char_p)
LOG_LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")


class LogInterface(C.Structure):
    _fields_ = [("log", LOG_CB)]


@LOG_CB
def _core_log(level, fmt):
    if level >= 2 and fmt:
        print(f"[core {LOG_LEVELS[min(level, 3)]}] {fmt.decode(errors='replace').rstrip()}", flush=True)


class Core:
    def __init__(self, path=CORE):
        self.lib = C.CDLL(path)
        self.pixel_format = PIXEL_0RGB1555
        self.frame = None
        self.audio = []
        self.joy = set()  # joypad ids held (port 0 = left joystick + console switches)
        self.options = {}
        self._optbuf = {}
        self._keep = [ENV_CB(self._env), VIDEO_CB(self._video), AUDIO_CB(self._audio),
                      AUDIO_BATCH_CB(self._audio_batch), POLL_CB(lambda: None), STATE_CB(self._state)]
        lib = self.lib
        lib.retro_set_environment(self._keep[0])
        lib.retro_set_video_refresh(self._keep[1])
        lib.retro_set_audio_sample(self._keep[2])
        lib.retro_set_audio_sample_batch(self._keep[3])
        lib.retro_set_input_poll(self._keep[4])
        lib.retro_set_input_state(self._keep[5])
        lib.retro_get_memory_data.restype = C.c_void_p
        lib.retro_get_memory_size.restype = C.c_size_t
        info = SystemInfo()
        lib.retro_get_system_info(C.byref(info))
        self.need_fullpath = info.need_fullpath
        lib.retro_init()
        self.ram = None  # numpy view of the 128 bytes, valid after load()
        atexit.register(self.shutdown)  # before C++'s own exit-time cleanup - see shutdown()

    # --- callbacks -------------------------------------------------------------------------
    def _env(self, cmd, data):
        """The core asking about the frontend (folders, settings, pixel format...): ENV_HANDLERS says which
        method answers which question. True = answered."""
        cmd &= 0xFFFF  # strip the "experimental" flag
        handler = ENV_HANDLERS.get(cmd)
        if handler is None:
            return False  # everything else: use the core's defaults
        return handler(self, cmd, data)

    def _can_dupe(self, cmd, data):  # yes: a frame may be "the same as last time"
        C.cast(data, C.POINTER(C.c_bool))[0] = True
        return True

    def _directory(self, cmd, data):
        C.cast(data, C.POINTER(C.c_char_p))[0] = SAVE_DIR if cmd == ENV_GET_SAVE_DIRECTORY else SYSTEM_DIR
        return True

    def _log_interface(self, cmd, data):
        C.cast(data, C.POINTER(LogInterface))[0].log = _core_log
        return True

    def _pixel_format(self, cmd, data):
        self.pixel_format = C.cast(data, C.POINTER(C.c_int))[0]
        return self.pixel_format in (PIXEL_XRGB8888, PIXEL_RGB565)

    def _set_variables(self, cmd, data):
        """The core's settings, each "Description; default|other|..." -> we take the default (first)."""
        variables = C.cast(data, C.POINTER(Variable))
        i = 0
        while variables[i].key:
            description = (variables[i].value or b"").decode(errors="replace")
            choices = description.split("; ", 1)[1].split("|") if "; " in description else [""]
            key = variables[i].key.decode()
            self.options[key] = OPTION_OVERRIDES.get(key, choices[0]).encode()
            i += 1
        return True

    def _get_variable(self, cmd, data):
        variable = C.cast(data, C.POINTER(Variable))[0]
        key = variable.key.decode() if variable.key else ""
        if key not in self.options:
            return False
        self._optbuf[key] = C.c_char_p(self.options[key])  # keep the bytes alive for the core
        variable.value = self._optbuf[key].value
        return True

    def _no_variable_update(self, cmd, data):  # settings never change while running
        C.cast(data, C.POINTER(C.c_bool))[0] = False
        return True

    def _accept(self, cmd, data):
        return True

    def _video(self, data, w, h, pitch):
        if not data:
            return  # duped frame: keep the last one
        if self.pixel_format == PIXEL_XRGB8888:  # 4 bytes a pixel: blue, green, red, unused
            buf = np.ctypeslib.as_array(C.cast(data, C.POINTER(C.c_uint8)), shape=(h, pitch))
            pixels = buf[:, :w * 4].reshape(h, w, 4)
            self.frame = pixels[..., [2, 1, 0]].copy()
        else:  # RGB565: 16 bits a pixel, 5 red, 6 green, 5 blue
            buf = np.ctypeslib.as_array(C.cast(data, C.POINTER(C.c_uint16)), shape=(h, pitch // 2))[:, :w]
            red, green, blue = (buf >> 11) & 31, (buf >> 5) & 63, buf & 31
            self.frame = np.dstack([red << 3, green << 2, blue << 3]).astype(np.uint8)

    def _audio(self, left, right):
        self.audio.append(np.array([[left, right]], np.int16))

    def _audio_batch(self, data, frames):
        self.audio.append(np.ctypeslib.as_array(data, shape=(frames * 2,)).reshape(frames, 2).copy())
        return frames

    def _state(self, port, device, index, ident):
        if device == DEVICE_JOYPAD and port == 0:
            return 1 if ident in self.joy else 0
        return 0

    # --- API ------------------------------------------------------------------------------
    def av_info(self):
        info = AVInfo()
        self.lib.retro_get_system_av_info(C.byref(info))
        return info

    def load(self, path):
        # need_fullpath: the core opens the path itself. Otherwise it wants the bytes already in memory
        # (the path is kept too, for cores that still key off its extension).
        if self.need_fullpath:
            game = GameInfo(path.encode(), None, 0, None)
        else:
            with open(path, "rb") as f:
                raw = f.read()
            buf = self._rom = C.create_string_buffer(raw, len(raw))  # kept: a core may read it after loading
            game = GameInfo(path.encode(), C.cast(buf, C.c_void_p), len(raw), None)
        if not self.lib.retro_load_game(C.byref(game)):
            raise RuntimeError(f"core refused {path}")
        self.lib.retro_set_controller_port_device(0, DEVICE_JOYPAD)
        ptr = self.lib.retro_get_memory_data(MEMORY_SYSTEM_RAM)
        size = self.lib.retro_get_memory_size(MEMORY_SYSTEM_RAM)
        if not ptr or size < 128:
            raise RuntimeError(f"core exposes no system RAM (ptr={ptr}, size={size})")
        # a live view: reading it between retro_run() calls sees the current state, no copying, no pausing
        self.ram = np.ctypeslib.as_array(C.cast(ptr, C.POINTER(C.c_uint8)), shape=(128,))

    def shutdown(self):
        """Shut the core down while the program is still running. Left to the C++ cleanup at exit, Stella's
        emulator object is destroyed after its logger's timer thread is gone, and its destructor can wait for
        that thread forever (TimerManager::clear): the program then hangs instead of quitting, now and then.
        Destroying it here, first (retro_deinit), leaves nothing for that cleanup to do."""
        if getattr(self, "_shut", False):
            return
        self._shut = True
        try:
            self.lib.retro_unload_game()
            self.lib.retro_deinit()
        except Exception:  # never let shutting down get in the way of quitting
            pass

    def run(self):
        self.lib.retro_run()

    def take_audio(self):
        samples = np.concatenate(self.audio) if self.audio else np.zeros((0, 2), np.int16)
        self.audio = []
        return samples


ENV_HANDLERS = {  # the core's questions (libretro "environment" commands) -> Core's answer
    ENV_GET_CAN_DUPE: Core._can_dupe,
    ENV_GET_SYSTEM_DIRECTORY: Core._directory, ENV_GET_SAVE_DIRECTORY: Core._directory,
    ENV_GET_CORE_ASSETS_DIRECTORY: Core._directory,
    ENV_GET_LOG_INTERFACE: Core._log_interface,
    ENV_SET_PIXEL_FORMAT: Core._pixel_format,
    ENV_SET_VARIABLES: Core._set_variables,
    ENV_GET_VARIABLE: Core._get_variable,
    ENV_GET_VARIABLE_UPDATE: Core._no_variable_update,
    ENV_SET_ROTATION: Core._accept,
}


class AudioOut:
    """Ring buffer between the emulator (pushes each frame's samples) and the sound card (pulls at its pace).
    mixer(block) -> block, if given, runs INSIDE the sound card's callback on every block it asks for - so a
    source like the music (music.MusicPlayer) is rendered exactly when and as much as the card needs, and
    never stutters with the video loop's timing. Only the emulator's own samples go through the buffer.

    Fixed 512-frame blocks (~16 ms): with blocksize=0 the card asked for 15 frames at a time - ~2000 Python
    callbacks a second, which the game loop starved (clicks). The emulator side keeps a cushion: after it
    runs dry it isn't played again until `prime` samples are queued, so it never comes out in crumbs.
    The emulator makes 524 samples per frame; ~31423/s against the card's 31440/s at a 59.97 Hz loop."""

    def __init__(self, rate, max_ms=150, prime_ms=50, mixer=None, block=512):
        self.buf, self.lock = np.zeros((0, 2), np.int16), threading.Lock()
        self.max, self.prime = int(rate * max_ms / 1000), int(rate * prime_ms / 1000)
        self.mixer = mixer
        self.priming = True
        self.expect = True        # False while the game deliberately makes no sound (paused / room scroll)
        self.missing = 0          # samples the card wanted but didn't get when expected (diagnostics)
        self.dropped = 0          # emulator samples thrown away because the buffer was full (diagnostics)
        self.xruns = 0            # the sound card's own "callback was late" flag = audible dropouts
        self.tap = None           # tap(block): sees every block exactly as played (recorder.py)
        try:
            self.stream = sd.OutputStream(samplerate=rate, channels=2, dtype="int16", callback=self._pull,
                                          blocksize=block, latency="high")
            self.stream.start()
        except sd.PortAudioError as error:   # no sound card (a build server): play on, silently
            print(f"no sound: {error}", flush=True)
            self.stream = None

    @property
    def underruns(self):  # old name, kept for callers
        return self.missing

    def _pull(self, out, frames, _time, status):
        if status.output_underflow:
            self.xruns += 1
        block = np.zeros((frames, 2), np.int16)
        with self.lock:
            if self.priming and len(self.buf) >= self.prime:
                self.priming = False
            if not self.priming:
                available = min(frames, len(self.buf))
                block[:available] = self.buf[:available]
                self.buf = self.buf[available:]
                if available < frames:
                    self.priming = True  # ran dry: refill the cushion before playing on
                    if self.expect:
                        self.missing += frames - available
        if self.mixer is not None:
            block = self.mixer(block)
        out[:] = block
        if self.tap is not None:
            self.tap(block)

    def push(self, samples):
        with self.lock:
            buf = np.concatenate([self.buf, samples])
            if len(buf) > self.max:  # never let latency grow
                self.dropped += len(buf) - self.max
                buf = buf[-self.max:]
            self.buf = buf
