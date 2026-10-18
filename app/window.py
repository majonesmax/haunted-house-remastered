"""The game window: runs the emulator, asks the look for a picture, and shows it.

One frame (GameWindow.run):
    0. loading   at launch, until every look's floors, soundtrack and the ambience are made (a few
                 seconds), a quiet loading screen - so the background work is done before any sound plays
    1. input     keys -> the joystick and the console's switches, or window commands (app/controls.py); at
                 launch, the story shows until any key is pressed
    2. the game  one emulator frame (unless paused), and its sound to the speakers
    3. picture   a GameState snapshot of the RAM -> the look draws it (with the story, or the storm's distant
                 lightning: shared/storm.py), and the soundtrack follows it
    4. extras    the grid's RAM pane follows the game; the recorder (R) saves every look's picture
    5. show      the current view (app/views.py): the remaster beside the 2600 original, either alone, or
                 the grid - what you're playing over the other look, the 2600 over its live RAM; with the
                 help (H) on top if it's open. The window fits any screen; on macOS, fullscreen keeps one
                 window whatever the view (elsewhere each view gets a new window, which Windows needs)
    6. pace      at the game's 60 frames a second
"""

import os
import sys
import threading
import time

import numpy as np
import pygame
from PIL import Image

import looks
from app import views as V
from app.controls import CONTROLS
from app.ram_panel import RamPanel
from app.recorder import Recorder
from game import guide
from music import chiptune
from music.board import SoundBoard
from music.player import MusicPlayer
from game import emulator as E
from game import paths
from game.state import Game
from looks.base import SCREEN_W, Extras
from shared import hud
from shared.storm import Storm

JOYSTICK = {pygame.K_UP: E.JOY_UP, pygame.K_DOWN: E.JOY_DOWN, pygame.K_LEFT: E.JOY_LEFT,
            pygame.K_RIGHT: E.JOY_RIGHT, pygame.K_SPACE: E.JOY_B,
            pygame.K_TAB: E.JOY_SELECT, pygame.K_RETURN: E.JOY_START}
KEYS = {pygame.K_l: "next_look", pygame.K_d: "toggle_lightning", pygame.K_m: "toggle_music",
        pygame.K_e: "toggle_effects",
        pygame.K_v: "next_view",
        pygame.K_p: "toggle_pause", pygame.K_s: "screenshot", pygame.K_f: "toggle_fullscreen",
        pygame.K_h: "toggle_help", pygame.K_r: "toggle_recording"}
LEFT_DIFFICULTY_A, LEFT_DIFFICULTY_B = 10, 12  # the Stella core's buttons for the left switch (docs)
SWITCH_FRAMES = 3                              # hold a switch button this long for the core to see it
FPS = 60
FIT = 0.9                       # a view bigger than this much of the screen opens smaller (the grid)
KEEP_WINDOW_IN_FULLSCREEN = sys.platform == "darwin"   # Windows needed a new window for each view
NOTE_FRAMES = 120               # how long a message stays on screen
NOTE_Y = 182                    # where it goes: the bottom of the view
WHITE, GREY, RED = (236, 238, 236), (152, 150, 152), (230, 40, 40)


class GameWindow:
    def __init__(self, rom_path, look_name="nes", pack_name=None):
        self.game = Game(rom_path)
        self.looks = {}  # every look made once, so L switches at once (each with its own pack, bar the first)
        for platform in looks.LOOKS:
            pack = pack_name if platform == look_name else None
            self.looks[platform] = looks.make(platform, self.game.rom, pack)
        self.look = self.looks[look_name]
        pygame.display.init()  # not pygame.init(): that opens pygame's own mixer too, a second sound stream
        self.core = E.Core()
        self.core.load(rom_path)
        self.players = {platform: self.music_for(look) for platform, look in self.looks.items()}
        self.music = self.players[look_name]
        self.sound = SoundBoard(self.music)
        rate = int(self.core.av_info().timing.sample_rate)
        self.audio = E.AudioOut(rate, mixer=self.sound.mixer)
        self.recorder = Recorder(paths.RECORDINGS, rate)
        self.audio.tap = self.recorder.audio_tap
        self.panel = RamPanel()
        self.note, self.note_frames = "", 0   # a moment's message on screen ("SOUND: ORIGINAL")
        self.view = "both"
        self.paused = self.fullscreen = False
        self.help = 0   # H: 0 hidden, 1 the keys, 2 how to play
        self.lightning = True          # the left difficulty switch at B, the console's default
        self.switch_held = 0
        self.frame_no = 0
        self.intro = True              # the story, at launch, until a key is pressed
        self.keys_held_off = False     # after the story: the key that ended it isn't passed to the game
        self.pressed_by_check = set()  # keys held by play.py --check (app/self_check.py), as if pressed
        self.scenes_ready = False      # every look's floors drawn (prepare_looks)
        self.storm = Storm()
        self.state = None
        self.picture = None             # your look's screen this frame
        self.other_picture = None       # the other look's, when the grid or the recorder needs it
        self.screen = self.set_mode()
        threading.Thread(target=self.prepare_looks, daemon=True).start()

    def prepare_looks(self):
        """In the background: every look's picture of every floor, so no floor's first visit hitches."""
        for look in self.looks.values():
            for floor in range(4):
                look.scene(floor)
        self.scenes_ready = True

    @property
    def loading(self):
        """Still making things in the background? While it is, the game waits and nothing is heard."""
        players_ready = all(player.ready for player in self.players.values())
        return not (self.scenes_ready and players_ready and self.sound.ambience.ready)

    # --- the loop ------------------------------------------------------------------------------------
    def run(self):
        clock = pygame.time.Clock()
        loading_frames = 0
        while self.handle_input():
            if self.loading:
                self.picture = self.loading_screen(loading_frames)
                loading_frames += 1
                self.show(loading=True)
                clock.tick(FPS)
                continue
            self.sound.holding = False
            if not self.paused:
                self.play_frame()
            self.show()
            self.note_frames = max(0, self.note_frames - 1)
            clock.tick(FPS)
        self.stop_recording()
        pygame.quit()

    def play_frame(self):
        """One frame of the game: run it, hear it, draw it (each look that's needed), record it."""
        self.step_game()
        state = self.state = self.game.state(self.core.ram)
        flash, thunder = self.weather(state)
        extras = Extras(self.intro, flash)
        self.sound.follow(state, self.intro, thunder)
        self.picture = self.look.draw(state, self.frame_no, extras)
        if self.view == "grid" or self.recorder.active:
            self.other_picture = self.other_look.draw(state, self.frame_no, extras)
        self.panel.update(state, self.frame_no)
        self.record(state)
        self.frame_no += 1

    @property
    def other_look(self):
        """The grid's comparison: the next look after yours."""
        platforms = sorted(self.looks)
        return self.looks[platforms[(platforms.index(self.look.platform) + 1) % len(platforms)]]

    def handle_input(self):
        """Keys -> the joystick, or a window command. False = quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key in KEYS:
                    getattr(self, KEYS[event.key])()
                elif self.intro:
                    self.intro, self.keys_held_off = False, True
        return True

    def weather(self, state):
        """(the distant lightning's flash, 0-1; does its thunder arrive now?) - over the story and in play,
        not on the title (it has its own) or after a win (the storm has passed), and only while the
        lightning switch is on (D)."""
        if not self.lightning or state.won or (state.mode == "select" and not self.intro):
            return 0.0, False
        return self.storm.flash(self.frame_no), self.storm.thunder(self.frame_no)

    def step_game(self):
        pressed = pygame.key.get_pressed()
        held = {button for key, button in JOYSTICK.items() if pressed[key] or key in self.pressed_by_check}
        if self.keys_held_off and not held:
            self.keys_held_off = False
        if self.intro or self.keys_held_off:
            held = set()   # the story isn't the game's: its keys don't reach it
        if self.switch_held:
            held.add(LEFT_DIFFICULTY_B if self.lightning else LEFT_DIFFICULTY_A)
            self.switch_held -= 1
        self.core.joy.clear()
        self.core.joy.update(held)
        self.core.run()
        self.audio.push(self.core.take_audio())

    def record(self, state):
        if not self.recorder.active:
            return
        pictures = {"a2600": np.asarray(self.core.frame), self.look.platform: self.picture,
                    self.other_look.platform: self.other_picture}
        details = {"floor": state.floor + 1, "room": state.room, "eyes": list(state.player),
                   "mode": state.mode, "look": self.look.platform, "view": self.view}
        self.recorder.frame(pictures, details, state.ram)

    # --- showing it ----------------------------------------------------------------------------------
    def canvas(self):
        """The current view as one RGB array (app/views.py), the help and messages on your look."""
        playing = self.picture.copy()
        if self.help == 1:
            draw_help(playing)
        elif self.help == 2:
            draw_how_to_play(playing)
        if self.note_frames:
            draw_note(playing, self.note)
        grid_extras = None
        if self.view == "grid":
            other = self.other_picture if self.other_picture is not None else np.zeros_like(playing)
            ram_pane = self.panel.draw(self.state) if self.state is not None else None
            grid_extras = (other, ram_pane, (self.look.name, self.other_look.name))
        canvas = V.compose(self.view, playing, self.core.frame, grid_extras)
        if self.recorder.active and self.frame_no // 30 % 2 == 0:
            draw_recording_light(canvas)
        return canvas

    def show(self, loading=False):
        if self.picture is None:
            return
        canvas = self.picture if loading else self.canvas()
        surface = pygame.surfarray.make_surface(canvas.swapaxes(0, 1))
        if surface.get_size() == self.screen.get_size():
            self.screen.blit(surface, (0, 0))
        else:   # fullscreen, a screen too small for the view, or a view just changed: fit it in
            V.fit_into(surface, self.screen)
        pygame.display.flip()

    def loading_screen(self, frame_no):
        """While the app gets ready: the eyes in the dark, blinking, and a word."""
        width, height = self.size()
        screen = np.zeros((height, width, 3), np.uint8)
        eyes = self.look.picture("eyes_blink" if frame_no % 90 < 6 else "eyes_centre", frame_no)
        if eyes is not None:
            left, top = (width - eyes.shape[1]) // 2, height // 2 - eyes.shape[0]
            screen[top:top + eyes.shape[0], left:left + eyes.shape[1]] = np.where(
                eyes[..., 3:] > 0, eyes[..., :3], 0)
        word = "LOADING" + "." * (frame_no // 20 % 4)
        hud.draw_text(screen, word, (width - hud.text_width("LOADING...")) // 2, height // 2 + 16, GREY)
        return screen

    def size(self):
        return V.size(self.view)

    def set_mode(self):
        """The window for the current view, its picture shown scaled to fit (SCALED). A view bigger than the
        screen allows (the grid, on a laptop) opens at a size that fits, and show() shrinks the picture
        into it. On macOS, fullscreen keeps its window whatever the view: a new window would leave
        fullscreen and come back, animated, on every V. Elsewhere, and out of fullscreen, each new size
        gets a new window: pygame-ce can crash or hang re-calling set_mode with SCALED (as Adventure
        Forever found), and Windows needed it."""
        pygame.display.set_caption(f"{paths.APP_NAME} - {self.look.name}")
        if self.fullscreen and KEEP_WINDOW_IN_FULLSCREEN and pygame.display.get_surface() is not None:
            return self.screen
        if pygame.display.get_surface() is not None:
            pygame.display.quit()
            pygame.display.init()
            pygame.display.set_caption(f"{paths.APP_NAME} - {self.look.name}")
        width, height = self.size()
        screen_w, screen_h = pygame.display.get_desktop_sizes()[0]
        shrink = min(1.0, FIT * screen_w / width, FIT * screen_h / height)
        flags = pygame.SCALED | pygame.RESIZABLE
        if self.fullscreen and not KEEP_WINDOW_IN_FULLSCREEN:
            flags |= pygame.FULLSCREEN
        return pygame.display.set_mode((int(width * shrink), int(height * shrink)), flags)

    # --- window commands -----------------------------------------------------------------------------
    def toggle_lightning(self):
        """The left difficulty switch: B lets lightning flash (the default), A stops it."""
        self.lightning = not self.lightning
        self.switch_held = SWITCH_FRAMES
        self.show_note("LIGHTNING: " + ("ON (B)" if self.lightning else "OFF (A)"))

    def next_view(self):
        """V: side by side -> the remaster -> the 2600 -> the grid."""
        self.view = V.VIEWS[(V.VIEWS.index(self.view) + 1) % len(V.VIEWS)]
        self.screen = self.set_mode()

    def toggle_pause(self):
        self.paused = not self.paused
        self.audio.expect = not self.paused
        self.music.paused = self.paused

    def music_for(self, look):
        """The look's pack's soundtrack, on the look's sound chip."""
        return MusicPlayer(chiptune.load_songs(look.pack.folder), look.synth)

    def next_look(self):
        """The next look (each with its own pack), and its soundtrack on its own chip."""
        platforms = sorted(self.looks)
        platform = platforms[(platforms.index(self.look.platform) + 1) % len(platforms)]
        self.look = self.looks[platform]
        on, paused = self.music.on, self.music.paused
        self.music = self.players[platform]
        self.music.on, self.music.paused = on, paused
        self.music.playing = None  # pick up the moment afresh on the next frame
        self.sound.music = self.music
        pygame.display.set_caption(f"{paths.APP_NAME} - {self.look.name}")
        self.show_note(self.look.name)

    def toggle_music(self):
        self.show_note("MUSIC: ON" if self.music.toggle() else "MUSIC: OFF - JUST THE HOUSE")

    def toggle_effects(self):
        remastered = self.sound.toggle_effects()
        self.show_note("SOUND: " + ("REMASTERED" if remastered else "ORIGINAL 2600"))

    def show_note(self, text):
        self.note, self.note_frames = text, NOTE_FRAMES

    def toggle_help(self):
        """H: the keys, then how to play, then neither."""
        self.help = (self.help + 1) % 3

    def toggle_fullscreen(self):
        """F. On macOS the same window grows into fullscreen, and coming out, a new window opens at the view's
        own size (whatever views were chosen meanwhile). Elsewhere a new window either way."""
        self.fullscreen = not self.fullscreen
        if self.fullscreen and KEEP_WINDOW_IN_FULLSCREEN:
            pygame.display.toggle_fullscreen()
        else:
            self.screen = self.set_mode()

    def toggle_recording(self):
        """R: start or stop recording (app/recorder.py)."""
        if self.recorder.active:
            self.stop_recording()
            return
        folder = self.recorder.start()
        self.show_note("RECORDING" if folder else "RECORDING NEEDS FFMPEG")

    def stop_recording(self):
        finished = self.recorder.stop()
        if finished:
            folder, frames = finished
            print(f"recording saved: {folder} ({frames} frames)", flush=True)
            self.show_note(f"SAVED {frames} FRAMES")

    def screenshot(self):
        os.makedirs(paths.SCREENSHOTS, exist_ok=True)
        name = time.strftime("haunted-%Y%m%d-%H%M%S.png")
        Image.fromarray(self.canvas()).save(os.path.join(paths.SCREENSHOTS, name))


def draw_recording_light(canvas):
    """A blinking red dot and REC, top left: on the window, never in the recording."""
    canvas[6:14, 6:14] = RED
    hud.draw_text(canvas, "REC", 18, 6, RED)


def draw_note(canvas, text):
    """A message across the bottom of the view, on a dark band (clear of the status and the floor's name)."""
    top = NOTE_Y
    canvas[top - 4:top + 12, 8:SCREEN_W - 8] //= 4
    hud.draw_text(canvas, text, (SCREEN_W - hud.text_width(text)) // 2, top, WHITE)


def draw_how_to_play(canvas):
    """The goal and the rules the original never explains (game/guide.py), over the picture."""
    height = 12 + len(guide.HOW_TO_PLAY) * 11
    canvas[4:4 + height, 4:SCREEN_W - 4] //= 5
    for row, (line, kind) in enumerate(guide.HOW_TO_PLAY):
        colour = WHITE if kind == "title" else GREY
        hud.draw_text(canvas, line, 8, 10 + row * 11, colour)


def draw_help(canvas):
    """The keys, over the top-left of the picture."""
    height = 16 + len(CONTROLS) * 12
    canvas[8:8 + height, 8:SCREEN_W - 8] = canvas[8:8 + height, 8:SCREEN_W - 8] // 4
    for row, (key, what) in enumerate(CONTROLS):
        top = 16 + row * 12
        hud.draw_text(canvas, key, 16, top, WHITE)
        hud.draw_text(canvas, what, 80, top, GREY)
