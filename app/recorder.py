"""Recording (R starts and stops): everything a video editor needs, as separate clean streams. (Adapted from
Adventure Forever's app/recorder.py.)

recordings/<date-time>/
    a2600.mp4   the 2600's picture, 160 x 228       } lossless H.264 at their own sizes - scale them up with
    nes.mp4     the NES look's screen, 256 x 240     } nearest-neighbour when editing; one video frame per
    snes.mp4    the SNES look's screen, 256 x 240    } game frame (60 a second), whichever look is showing
    audio.wav   exactly what the sound card played (the remastered sound or the 2600's, and the music)
    ram.bin     the 128 RAM bytes of every frame - `python -m app.recorder <folder>` turns it into ram.mp4,
                the grid's INTERNALS pane (drawing it live would cost the game its 60 frames a second)
    log.jsonl   a line a frame: the frame, the time, the floor, the eyes, the look showing, and events
    meta.json   frames a second, sizes, the sound's sample rate, when it started

Needs ffmpeg (on the PATH, or Homebrew's). Encoding and writing happen on worker threads; the game loop only
copies pictures into queues.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import wave

import numpy as np

FPS = 60
STREAMS = {"a2600": (160, 228), "nes": (256, 240), "snes": (256, 240)}
QUEUE_FRAMES = 240


def find_ffmpeg():
    """ffmpeg on the PATH - or, as apps started from the macOS Finder get a bare PATH, in Homebrew's places.
    None if it isn't installed."""
    for path in (shutil.which("ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if path and os.path.exists(path):
            return path
    return None


class Video:
    """One ffmpeg process, fed raw RGB frames from a queue on its own thread."""

    def __init__(self, ffmpeg, path, size, quality=0):
        width, height = size
        self.size = size
        command = [ffmpeg, "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                   "-s", f"{width}x{height}", "-r", str(FPS), "-i", "-", "-c:v", "libx264rgb",
                   "-preset", "ultrafast", "-crf", str(quality), path]
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE)
        self.frames = queue.Queue(maxsize=QUEUE_FRAMES)
        self.thread = threading.Thread(target=self.write_all, daemon=True)
        self.thread.start()

    def write_all(self):
        while (frame := self.frames.get()) is not None:
            self.process.stdin.write(frame.tobytes())
        self.process.stdin.close()
        self.process.wait()

    def put(self, frame):
        width, height = self.size
        if frame is None or frame.shape[:2] != (height, width):   # a missing frame never stops the video
            frame = np.zeros((height, width, 3), np.uint8)
        self.frames.put(np.ascontiguousarray(frame, np.uint8))

    def close(self):
        self.frames.put(None)
        self.thread.join()


class Recorder:
    def __init__(self, root, rate):
        self.root, self.rate = root, rate
        self.active = False

    def start(self):
        """Start recording: the folder being written, or None if ffmpeg isn't installed."""
        ffmpeg = find_ffmpeg()
        if ffmpeg is None:
            return None
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.folder = os.path.join(self.root, stamp)
        os.makedirs(self.folder, exist_ok=True)
        self.videos = {name: Video(ffmpeg, os.path.join(self.folder, f"{name}.mp4"), size)
                       for name, size in STREAMS.items()}
        self.ram_file = open(os.path.join(self.folder, "ram.bin"), "wb")
        self.log = open(os.path.join(self.folder, "log.jsonl"), "w")
        self.open_audio()
        self.frames, self.started, self.pending = 0, time.perf_counter(), []
        self.write_meta({"fps": FPS, "streams": STREAMS, "audio_rate": self.rate, "started": stamp})
        self.active = True
        return self.folder

    def open_audio(self):
        self.wav = wave.open(os.path.join(self.folder, "audio.wav"), "wb")
        self.wav.setnchannels(2)
        self.wav.setsampwidth(2)
        self.wav.setframerate(self.rate)
        self.audio_blocks = queue.Queue()
        self.audio_thread = threading.Thread(target=self.write_audio, daemon=True)
        self.audio_thread.start()

    def write_audio(self):
        while (block := self.audio_blocks.get()) is not None:
            self.wav.writeframes(block.tobytes())

    def audio_tap(self, block):
        """From the sound card's callback, each block as it's played: only a copy is queued."""
        if self.active:
            self.audio_blocks.put(block.copy())

    def event(self, text):
        if self.active:
            self.pending.append(text)

    def frame(self, pictures, details, ram):
        """pictures: {stream: RGB array}; details: the log line's fields; ram: the 128 bytes."""
        if not self.active:
            return
        self.ram_file.write(bytes(ram))
        for name, video in self.videos.items():
            video.put(pictures.get(name))
        line = {"f": self.frames, "t": round(time.perf_counter() - self.started, 4), **details}
        if self.pending:
            line["events"], self.pending = self.pending, []
        self.log.write(json.dumps(line) + "\n")
        self.frames += 1

    def stop(self):
        """Finish the files: (the folder, how many frames), or None if it wasn't recording."""
        if not self.active:
            return None
        self.active = False
        for video in self.videos.values():
            video.close()
        self.audio_blocks.put(None)
        self.audio_thread.join()
        self.wav.close()
        self.log.close()
        self.ram_file.close()
        seconds = time.perf_counter() - self.started
        measured = round(self.frames / seconds, 3) if seconds else None   # editing retimes the videos by it
        self.write_meta({"frames": self.frames, "seconds": round(seconds, 3), "measured_fps": measured})
        return self.folder, self.frames

    def write_meta(self, fields):
        path = os.path.join(self.folder, "meta.json")
        meta = {}
        if os.path.exists(path):
            with open(path) as meta_file:
                meta = json.load(meta_file)
        with open(path, "w") as meta_file:
            json.dump({**meta, **fields}, meta_file, indent=1)


def render_ram_video(folder, rom_path):
    """At editing time: ram.mp4, the INTERNALS pane exactly as the grid draws it, from ram.bin."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from app.ram_panel import SIZE, RamPanel
    from game.state import Game
    pygame.display.init()
    ram = np.fromfile(os.path.join(folder, "ram.bin"), np.uint8).reshape(-1, 128)
    game, panel = Game(rom_path), RamPanel()
    video = Video(find_ffmpeg(), os.path.join(folder, "ram.mp4"), SIZE, quality=12)
    for frame_no, frame_ram in enumerate(ram):
        state = game.state(frame_ram)
        panel.update(state, frame_no)
        video.put(panel.draw_now(state))
    video.close()
    return os.path.join(folder, "ram.mp4")


if __name__ == "__main__":
    from game import paths
    print(render_ram_video(sys.argv[1], paths.ROM))
