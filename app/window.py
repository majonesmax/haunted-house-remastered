"""The game window: runs the emulator, asks the look for a picture, and shows it.

One frame (GameWindow.run):
    1. input     keys -> the joystick and the console's switches, or window commands (app/controls.py); at
                 launch, the story shows until any key is pressed
    2. the game  one emulator frame (unless paused), and its sound to the speakers
    3. picture   a GameState snapshot of the RAM -> the look draws it (with the story, or the storm's distant
                 lightning: shared/storm.py), and the soundtrack follows it
    4. show      the current view: the remaster beside the 2600 original, the remaster alone, or the
                 original alone; with the help overlay (H) on top if it's open
    5. pace      at the game's 60 frames a second
"""

import os
import threading
import time

import numpy as np
import pygame
from PIL import Image

import looks
from app.controls import CONTROLS
from game import guide
from music import chiptune
from music.board import SoundBoard
from music.player import MusicPlayer
from game import emulator as E
from game import paths
from game.state import Game
from looks.base import SCREEN_H, SCREEN_W, Extras
from shared import hud
from shared.storm import Storm

JOYSTICK = {pygame.K_UP: E.JOY_UP, pygame.K_DOWN: E.JOY_DOWN, pygame.K_LEFT: E.JOY_LEFT,
            pygame.K_RIGHT: E.JOY_RIGHT, pygame.K_SPACE: E.JOY_B,
            pygame.K_TAB: E.JOY_SELECT, pygame.K_RETURN: E.JOY_START}
KEYS = {pygame.K_l: "next_look", pygame.K_d: "toggle_lightning", pygame.K_m: "toggle_music",
        pygame.K_e: "toggle_effects",
        pygame.K_v: "next_view",
        pygame.K_p: "toggle_pause", pygame.K_s: "screenshot", pygame.K_f: "toggle_fullscreen",
        pygame.K_h: "toggle_help"}
LEFT_DIFFICULTY_A, LEFT_DIFFICULTY_B = 10, 12  # the Stella core's buttons for the left switch (docs)
SWITCH_FRAMES = 3                              # hold a switch button this long for the core to see it
VIEWS = ("both", "remaster", "2600")
ORIGINAL_W = 320                               # the 2600's 160 x 228 picture, shown at the TV's shape
GAP = 8
FPS = 60
NOTE_FRAMES = 120               # how long a message stays on screen
NOTE_Y = 182                    # where it goes: the bottom of the view
WHITE, GREY = (236, 238, 236), (152, 150, 152)


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
        self.audio = E.AudioOut(int(self.core.av_info().timing.sample_rate), mixer=self.sound.mixer)
        self.note, self.note_frames = "", 0   # a moment's message on screen ("SOUND: ORIGINAL")
        self.view = "both"
        self.paused = self.fullscreen = False
        self.help = 0   # H: 0 hidden, 1 the keys, 2 how to play
        self.lightning = True          # the left difficulty switch at B, the console's default
        self.switch_held = 0
        self.frame_no = 0
        self.intro = True              # the story, at launch, until a key is pressed
        self.keys_held_off = False     # after the story: the key that ended it isn't passed to the game
        self.storm = Storm()
        self.picture = None
        self.screen = self.set_mode()
        threading.Thread(target=self.prepare_looks, daemon=True).start()

    def prepare_looks(self):
        """In the background: every look's picture of every floor, so no floor's first visit hitches."""
        for look in self.looks.values():
            for floor in range(4):
                look.scene(floor)

    # --- the loop ------------------------------------------------------------------------------------
    def run(self):
        clock = pygame.time.Clock()
        while self.handle_input():
            if not self.paused:
                self.step_game()
                state = self.game.state(self.core.ram)
                flash, thunder = self.weather(state)
                self.sound.follow(state, self.intro, thunder)
                self.picture = self.look.draw(state, self.frame_no, Extras(self.intro, flash))
                self.frame_no += 1
            self.show()
            self.note_frames = max(0, self.note_frames - 1)
            clock.tick(FPS)
        pygame.quit()

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
        not on the title (it has its own), and only while the lightning switch is on (D)."""
        if not self.lightning or (state.mode == "select" and not self.intro):
            return 0.0, False
        return self.storm.flash(self.frame_no), self.storm.thunder(self.frame_no)

    def step_game(self):
        pressed = pygame.key.get_pressed()
        held = {button for key, button in JOYSTICK.items() if pressed[key]}
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

    # --- showing it ----------------------------------------------------------------------------------
    def canvas(self):
        """The current view as one RGB array."""
        original = self.original()
        if self.view == "remaster":
            canvas = self.picture.copy()
        elif self.view == "2600":
            canvas = original
        else:
            gap = np.zeros((SCREEN_H, GAP, 3), np.uint8)
            canvas = np.concatenate([self.picture, gap, original], axis=1)
        if self.help == 1:
            draw_help(canvas)
        elif self.help == 2:
            draw_how_to_play(canvas)
        if self.note_frames:
            draw_note(canvas, self.note)
        return canvas

    def original(self):
        """The emulator's own picture at the remaster's height, in the TV's proportions."""
        frame = Image.fromarray(np.asarray(self.core.frame))
        return np.array(frame.resize((ORIGINAL_W, SCREEN_H), Image.NEAREST))

    def show(self):
        if self.picture is None:
            return
        canvas = self.canvas()
        surface = pygame.surfarray.make_surface(canvas.swapaxes(0, 1))
        if surface.get_size() != self.screen.get_size():
            self.screen = self.set_mode()
        self.screen.blit(surface, (0, 0))
        pygame.display.flip()

    def size(self):
        widths = {"both": SCREEN_W + GAP + ORIGINAL_W, "remaster": SCREEN_W, "2600": ORIGINAL_W}
        return widths[self.view], SCREEN_H

    def set_mode(self):
        """The window for the current view, drawn at a fixed size and shown scaled (SCALED). pygame-ce can
        crash or hang re-calling set_mode with SCALED, so each new size gets a new window (as Adventure
        Forever found)."""
        if pygame.display.get_surface() is not None:
            pygame.display.quit()
            pygame.display.init()
        pygame.display.set_caption(f"{paths.APP_NAME} - {self.look.name}")
        flags = pygame.SCALED | pygame.RESIZABLE | (pygame.FULLSCREEN if self.fullscreen else 0)
        return pygame.display.set_mode(self.size(), flags)

    # --- window commands -----------------------------------------------------------------------------
    def toggle_lightning(self):
        """The left difficulty switch: B lets lightning flash (the default), A stops it."""
        self.lightning = not self.lightning
        self.switch_held = SWITCH_FRAMES
        self.show_note("LIGHTNING: " + ("ON (B)" if self.lightning else "OFF (A)"))

    def next_view(self):
        self.view = VIEWS[(VIEWS.index(self.view) + 1) % len(VIEWS)]
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
        self.show_note("MUSIC: " + ("ON" if self.music.toggle() else "OFF"))

    def toggle_effects(self):
        remastered = self.sound.toggle_effects()
        self.show_note("SOUND: " + ("REMASTERED" if remastered else "ORIGINAL 2600"))

    def show_note(self, text):
        self.note, self.note_frames = text, NOTE_FRAMES

    def toggle_help(self):
        """H: the keys, then how to play, then neither."""
        self.help = (self.help + 1) % 3

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.screen = self.set_mode()

    def screenshot(self):
        os.makedirs(paths.SCREENSHOTS, exist_ok=True)
        name = time.strftime("haunted-%Y%m%d-%H%M%S.png")
        Image.fromarray(self.canvas()).save(os.path.join(paths.SCREENSHOTS, name))


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
