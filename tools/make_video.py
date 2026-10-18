"""Cut a gameplay video from a recording (the R key; app/recorder.py): 1920x1080, 60 fps, H.264 + AAC, so it
plays anywhere. (Adventure Forever's tools/make_video.py, for Haunted House.)

  1. Each stream is resampled to a steady 60 fps on the wall clock (log.jsonl's "t"), so it lines up with
     audio.wav, which was recorded in real time, even where the game stalled. Pixel art scales with
     nearest-neighbour, so it stays sharp.
  2. The edit list - <recording>/edit.json - keeps time ranges of the recording; inside each, the layout
     follows the player's own view switches from the log (side by side, the remaster alone, the 2600 alone,
     the grid with the live RAM).
  3. Captions, pane labels and the title and end cards are in the game's own pixel font (shared/hud.py).
  4. Each piece renders separately; jumps between kept ranges dip through black, view switches cut straight;
     then one join, where the sound is encoded once.

Usage: python tools/make_video.py recordings/<recording> [-o out.mp4]

edit.json:
  {"keep": [[from, to], ...],               seconds on the recording's clock (log.jsonl "t")
   "captions": [[at, seconds, "TEXT"], ...],   the font has A-Z 0-9 and  !',-./:<>?
   "title": [["TEXT", scale, [r, g, b], y], ...], "end": [...],    optional: the title and end cards
   "audio_lead": 0.15}                      optional: how much later the sound is than the picture
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Any, NamedTuple

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # the repo root
from app import recorder as REC  # noqa: E402
from app.ram_panel import SIZE as RAM_SIZE  # noqa: E402
from game import rom as R  # noqa: E402
from shared import hud  # noqa: E402
from shared.types import Picture, Rgb  # noqa: E402

WIDTH, HEIGHT, FPS = 1920, 1080, 60
BACKGROUND: Rgb = (11, 11, 20)
CLEAR: Rgb = (1, 2, 3)              # the colour that's see-through in an overlay picture
CAPTION_COLOUR: Rgb = (255, 236, 140)
CAPTION_Y, CAPTION_SCALE = 1032, 3
LABEL_COLOUR: Rgb = (232, 232, 240)
STREAM_SIZES: dict[str, tuple[int, int]] = {**REC.STREAMS, "ram": RAM_SIZE}
LOOK_NAMES = {"nes": "NES REMASTER", "snes": "SNES REMASTER"}
ORIGINAL = "ATARI 2600 - 1982"
MIN_PART = 0.6                       # a view shown shorter than this (V cycling past) keeps the last layout
DIP = 0.25                           # seconds of fade through black at a jump
TITLE_SECONDS, END_SECONDS = 4.0, 6.0

Line = tuple[str, int, Rgb, int]     # a card's line: (text, scale, colour, y)
Placement = tuple[str, int, int, int, int]   # (stream, x, y, width, height)
Label = tuple[str, int, int]         # (text, x, y)

TITLE: list[Line] = [("HAUNTED HOUSE", 6, (200, 150, 255), 330),
                     ("ATARI 2600 - 1982 - JAMES ANDREASEN", 3, (232, 232, 240), 470),
                     ("REMASTERED", 3, (232, 200, 72), 540)]
END: list[Line] = [("HAUNTED HOUSE BY JAMES ANDREASEN, ATARI 1982", 3, (232, 232, 240), 380),
                   ("A FAN PROJECT - NOT FOR SALE", 2, (200, 150, 255), 560)]


class Caption(NamedTuple):
    start: float       # seconds on the recording's clock
    seconds: float
    text: str


class Part(NamedTuple):
    start: float
    end: float
    layout: str        # both_<look> / remaster_<look> / 2600 / grid_<look>
    fade_in: bool      # the first part of a kept range: it comes in from black...
    fade_out: bool     # ...and the last goes out to black


class Edit(NamedTuple):
    keep: list[tuple[float, float]]
    captions: list[Caption]
    title: list[Line]
    end: list[Line]
    audio_lead: float


def load_edit(recording: str) -> Edit:
    with open(os.path.join(recording, "edit.json")) as edit_file:
        edit: dict[str, Any] = json.load(edit_file)
    def lines(key: str, default: list[Line]) -> list[Line]:
        return [(text, scale, tuple(colour), y) for text, scale, colour, y in edit.get(key, default)]
    return Edit(keep=[(start, end) for start, end in edit["keep"]],
                captions=[Caption(*caption) for caption in edit.get("captions", [])],
                title=lines("title", TITLE), end=lines("end", END),
                audio_lead=edit.get("audio_lead", 0.15))


def run(command: list[str], timeout: int = 300, tries: int = 4) -> None:
    """ffmpeg, never reading the terminal (it can freeze under a script otherwise), with one filter thread;
    a run that stalls anyway (ffmpeg occasionally deadlocks on graphs with many inputs) is retried."""
    full = [command[0], "-nostdin", "-filter_threads", "1", *command[1:]]
    for attempt in range(1, tries + 1):
        try:
            subprocess.run(full, check=True, stdin=subprocess.DEVNULL, timeout=timeout)
            return
        except subprocess.TimeoutExpired:
            print(f"  ffmpeg stalled ({timeout} s) - retry {attempt}/{tries - 1}", flush=True)
    raise RuntimeError("ffmpeg kept stalling: " + " ".join(command[:12]))


# --- pictures: text, labels ------------------------------------------------------------------------
def save_overlay(picture: Picture, path: str, opacity: int = 255) -> None:
    """A picture with CLEAR where it should be see-through, saved as an RGBA PNG."""
    clear = (picture == CLEAR).all(axis=2)
    alpha = np.where(clear, 0, opacity).astype(np.uint8)
    Image.fromarray(np.dstack([picture, alpha])).save(path)


def text_picture(lines: list[Line], path: str, background: Rgb | None = None) -> None:
    """Lines of text centred across the frame; on `background`, or see-through (an overlay) if None."""
    picture = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    picture[:] = background if background is not None else CLEAR
    for text, scale, colour, y in lines:
        left = (WIDTH - hud.text_width(text, scale)) // 2
        hud.draw_text(picture, text, left, y, colour, scale=scale, shadow=(0, 0, 0))
    if background is None:
        save_overlay(picture, path)
    else:
        Image.fromarray(picture).save(path)


def label_overlay(labels: list[Label], path: str) -> None:
    """The panes' small labels, each on a dark box."""
    picture = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    picture[:] = CLEAR
    for text, left, top in labels:
        width = hud.text_width(text, 2)
        picture[top - 6:top + 20, left - 8:left + width + 6] = (0, 0, 0)
        hud.draw_text(picture, text, left, top, LABEL_COLOUR, scale=2)
    save_overlay(picture, path, opacity=230)


# --- layouts -----------------------------------------------------------------------------------------
def other_look(look: str) -> str:
    return "snes" if look == "nes" else "nes"


def layout(name: str) -> tuple[list[Placement], list[Label]]:
    """Where each stream goes on the 1920 x 1080 frame, and the labels, for a layout name."""
    kind, _, look = name.partition("_")
    if kind == "both":
        return ([(look, 64, 60, 1024, 960), ("a2600", 1176, 312, 640, 456)],
                [(LOOK_NAMES[look], 64, 24), (ORIGINAL, 1176, 276)])
    if kind == "remaster":
        return [(look, 448, 60, 1024, 960)], [(LOOK_NAMES[look], 448, 24)]
    if kind == "2600":
        return [("a2600", 320, 70, 1280, 912)], [(ORIGINAL, 320, 34)]
    lower = other_look(look)   # the grid as the game shows it: your look over the other, the 2600 over RAM
    lower_name = LOOK_NAMES[lower]
    return ([(look, 448, 60, 512, 480), (lower, 448, 540, 512, 480), ("a2600", 960, 117, 512, 365),
             ("ram", 960, 540, 512, 480)],
            [(LOOK_NAMES[look], 448, 24), (ORIGINAL, 960, 24),
             (lower_name, 448 - hud.text_width(lower_name, 2) - 24, 548), ("INTERNALS", 1472 + 24, 548)])


# --- the streams, at a steady 60 fps --------------------------------------------------------------------
def frame_times(recording: str) -> np.ndarray:
    with open(os.path.join(recording, "log.jsonl")) as log:
        return np.array([json.loads(line)["t"] for line in log])


def steady_streams(recording: str, work: str) -> dict[str, str]:
    """Each stream at a steady 60 fps on the wall clock: frames repeated or skipped by the log's times."""
    times = frame_times(recording)
    wanted = np.arange(int(times[-1] * FPS) + 1) / FPS
    source_frames = np.clip(np.searchsorted(times, wanted, side="right") - 1, 0, len(times) - 1)
    if not os.path.exists(os.path.join(recording, "ram.mp4")):
        print("drawing the RAM pane from ram.bin...", flush=True)
        REC.render_ram_video(recording, R.DEFAULT_ROM)
    streams = {}
    for name, size in STREAM_SIZES.items():
        streams[name] = os.path.join(work, f"{name}_steady.mp4")
        if not os.path.exists(streams[name]):
            source = os.path.join(recording, f"{name}.mp4")
            resample(source, streams[name], size, source_frames, lossy=name == "ram")
    return streams


def resample(source: str, target: str, size: tuple[int, int], source_frames: np.ndarray, lossy: bool) -> None:
    """Re-time one stream: output frame n is source frame source_frames[n]."""
    width, height = size
    decoder = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", source, "-f", "rawvideo",
                                "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    encoder = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                "-s", f"{width}x{height}", "-r", str(FPS), "-i", "-", "-c:v", "libx264rgb",
                                "-preset", "ultrafast", "-crf", "12" if lossy else "0", target],
                               stdin=subprocess.PIPE)
    assert decoder.stdout is not None and encoder.stdin is not None   # both were opened as pipes
    frame_bytes, current, current_index = width * height * 3, b"", -1
    for want in source_frames:
        while current_index < want:
            frame = decoder.stdout.read(frame_bytes)
            if len(frame) < frame_bytes:
                break
            current, current_index = frame, current_index + 1
        encoder.stdin.write(current)
    encoder.stdin.close()
    encoder.wait()
    decoder.stdout.close()
    decoder.wait()


# --- the plan: kept ranges, cut where the view changes -------------------------------------------------
def layout_at(rows: list[dict[str, Any]], times: np.ndarray, moment: float) -> str:
    row = rows[max(0, int(np.searchsorted(times, moment, side="right")) - 1)]
    view, look = row["view"], row["look"]
    return "2600" if view == "2600" else f"{view}_{look}"


def plan(recording: str, keep: list[tuple[float, float]]) -> list[Part]:
    """The kept ranges, split where the player switched view or look (a brief flash keeps the last)."""
    with open(os.path.join(recording, "log.jsonl")) as log:
        rows = [json.loads(line) for line in log]
    times = np.array([row["t"] for row in rows])
    parts = []
    for start, end in keep:
        pieces = merged_pieces(rows, times, start, end)
        for index, (piece_start, piece_end, name) in enumerate(pieces):
            parts.append(Part(piece_start, piece_end, name, index == 0, index == len(pieces) - 1))
    return parts


def merged_pieces(rows: list[dict[str, Any]], times: np.ndarray, start: float,
                  end: float) -> list[tuple[float, float, str]]:
    cuts, current = [start], layout_at(rows, times, start)
    for moment in np.arange(start, end, 1 / FPS):
        name = layout_at(rows, times, moment)
        if name != current:
            cuts.append(round(float(moment), 4))
            current = name
    cuts.append(end)
    pieces: list[tuple[float, float, str]] = []
    for piece_start, piece_end in zip(cuts, cuts[1:]):
        name = layout_at(rows, times, piece_start + 1e-3)
        too_brief = piece_end - piece_start < MIN_PART
        if pieces and (too_brief or name == pieces[-1][2]):
            pieces[-1] = (pieces[-1][0], piece_end, pieces[-1][2])
        else:
            pieces.append((piece_start, piece_end, name))
    return pieces


# --- rendering ---------------------------------------------------------------------------------------
def render_part(index: int, part: Part, streams: dict[str, str], recording: str, work: str,
                edit: Edit) -> str:
    """One part: the streams placed and scaled, labels, captions (fading in and out), the sound."""
    duration = part.end - part.start
    placements, labels = layout(part.layout)
    labels_png = os.path.join(work, f"labels_{part.layout}.png")
    if not os.path.exists(labels_png):
        label_overlay(labels, labels_png)
    showing = [caption for caption in edit.captions
               if caption.start < part.end and caption.start + caption.seconds > part.start]
    captions = [Caption(caption.start - part.start, caption.seconds, caption.text) for caption in showing]
    inputs = ["-f", "lavfi", "-i", "color=c=0x{:02x}{:02x}{:02x}:s={}x{}:r={}:d={:.3f}".format(
        *BACKGROUND, WIDTH, HEIGHT, FPS, duration)]
    for stream, *_ in placements:
        inputs += ["-ss", f"{part.start:.3f}", "-t", f"{duration:.3f}", "-i", streams[stream]]
    inputs += ["-loop", "1", "-t", f"{duration:.3f}", "-i", labels_png]
    for caption_number, caption in enumerate(captions):
        png = os.path.join(work, f"caption_{index}_{caption_number}.png")
        text_picture([(caption.text, CAPTION_SCALE, CAPTION_COLOUR, CAPTION_Y)], png)
        inputs += ["-loop", "1", "-t", f"{duration:.3f}", "-i", png]
    inputs += ["-ss", f"{part.start + edit.audio_lead:.3f}", "-t", f"{duration:.3f}",
               "-i", os.path.join(recording, "audio.wav")]
    graph = filter_graph(placements, captions, part, duration)
    out = os.path.join(work, f"part_{index:03d}.mkv")
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
         "-t", f"{duration:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "16",
         "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", out])
    return out


def filter_graph(placements: list[Placement], captions: list[Caption], part: Part, duration: float) -> str:
    """ffmpeg's filter graph for a part: inputs are the background, the streams, the labels, the
    captions and the sound, in that order."""
    steps, last = [], "[0:v]"
    for number, (_stream, left, top, width, height) in enumerate(placements):
        steps.append(f"[{number + 1}:v]scale={width}:{height}:flags=neighbor,setpts=PTS-STARTPTS[s{number}]")
        steps.append(f"{last}[s{number}]overlay={left}:{top}:shortest=1[b{number}]")
        last = f"[b{number}]"
    labels_input = len(placements) + 1
    steps.append(f"{last}[{labels_input}:v]overlay=0:0:shortest=1[labelled]")
    last = "[labelled]"
    for number, caption in enumerate(captions):
        fades = []
        if caption.start >= 0:                                   # it starts in this part: fade in
            fades.append(f"fade=t=in:st={caption.start:.2f}:d=0.3:alpha=1")
        if caption.start + caption.seconds <= duration:          # it ends in this part: fade out
            fade_from = max(caption.start, 0, caption.start + caption.seconds - 0.4)
            fades.append(f"fade=t=out:st={fade_from:.2f}:d=0.4:alpha=1")
        faded = "".join("," + fade for fade in fades)
        steps.append(f"[{labels_input + 1 + number}:v]format=rgba{faded}[c{number}]")
        steps.append(f"{last}[c{number}]overlay=0:0:shortest=1[cc{number}]")
        last = f"[cc{number}]"
    picture_fades = ([f"fade=t=in:st=0:d={DIP}"] if part.fade_in else []) + \
                    ([f"fade=t=out:st={duration - DIP:.3f}:d={DIP}"] if part.fade_out else [])
    steps.append(f"{last}{','.join(picture_fades) or 'null'},format=yuv420p[v]")
    sound_in = labels_input + 1 + len(captions)
    fade_in, fade_out = (DIP if part.fade_in else 0.03), (DIP if part.fade_out else 0.03)
    steps.append(f"[{sound_in}:a]aresample=48000,asetpts=PTS-STARTPTS,afade=t=in:st=0:d={fade_in},"
                 f"afade=t=out:st={duration - fade_out:.3f}:d={fade_out}[a]")
    return ";".join(steps)


def card(lines: list[Line], seconds: float, path: str, work: str,
         sound: tuple[str, float] | None = None) -> str:
    """A title or end card: the lines on the background, fading in and out; silent, or a stretch of sound."""
    png = os.path.join(work, os.path.basename(path) + ".png")
    text_picture(lines, png, background=BACKGROUND)
    sound_input = (["-f", "lavfi", "-t", f"{seconds}", "-i", "anullsrc=r=48000:cl=stereo"] if sound is None
                   else ["-ss", f"{sound[1]:.3f}", "-t", f"{seconds}", "-i", sound[0]])
    graph = (f"[0:v]fade=t=in:st=0:d=0.6,fade=t=out:st={seconds - 0.6}:d=0.6,format=yuv420p[v];"
             f"[1:a]aresample=48000,afade=t=in:st=0:d=0.3,afade=t=out:st={seconds - 0.8}:d=0.8[a]")
    picture_input = ["-loop", "1", "-t", f"{seconds}", "-r", str(FPS), "-i", png]
    encoding = ["-c:v", "libx264", "-preset", "medium", "-crf", "16",
                "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]
    run(["ffmpeg", "-v", "error", "-y", *picture_input, *sound_input, "-filter_complex", graph,
         "-map", "[v]", "-map", "[a]", "-t", f"{seconds}", "-r", str(FPS), *encoding, path])
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Cut a video from a recording, following its edit.json.")
    parser.add_argument("recording")
    parser.add_argument("-o", "--out")
    args = parser.parse_args()
    recording = args.recording.rstrip("/")
    edit = load_edit(recording)
    work = os.path.join(recording, "edit")
    os.makedirs(work, exist_ok=True)
    print("resampling the streams to a steady 60 fps...", flush=True)
    streams = steady_streams(recording, work)
    audio = os.path.join(recording, "audio.wav")
    pieces = [card(edit.title, TITLE_SECONDS, os.path.join(work, "title.mkv"), work, sound=(audio, 0.0))]
    for index, part in enumerate(plan(recording, edit.keep)):
        print(f"part {index + 1}: {part.start:6.1f}-{part.end:6.1f} s  {part.layout}", flush=True)
        pieces.append(render_part(index, part, streams, recording, work, edit))
    pieces.append(card(edit.end, END_SECONDS, os.path.join(work, "end.mkv"), work))
    listing = os.path.join(work, "parts.txt")
    with open(listing, "w") as parts_file:
        parts_file.writelines(f"file '{os.path.abspath(piece)}'\n" for piece in pieces)
    out = args.out or os.path.join(recording, "haunted_house_remastered.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing, "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
    print(out)


if __name__ == "__main__":
    main()
