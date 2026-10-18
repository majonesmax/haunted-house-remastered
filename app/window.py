"""The game window: runs the emulator, asks the look for a picture, and shows it.

One frame (GameWindow.run):
    1. input     keys -> the joystick and the console's switches, or window commands (app/controls.py)
    2. the game  one emulator frame (unless paused), and its sound to the speakers
    3. picture   a GameState snapshot of the RAM -> the look draws it
    4. show      the current view: the remaster beside the 2600 original, the remaster alone, or the
                 original alone; with the help overlay (H) on top if it's open
    5. pace      at the game's 60 frames a second
"""

import os
import time

import numpy as np
import pygame
from PIL import Image

import looks
from app.controls import CONTROLS
from game import emulator as E
from game import paths
from game.state import Game
from looks.base import SCREEN_H, SCREEN_W
from shared import hud

JOYSTICK = {pygame.K_UP: E.JOY_UP, pygame.K_DOWN: E.JOY_DOWN, pygame.K_LEFT: E.JOY_LEFT,
            pygame.K_RIGHT: E.JOY_RIGHT, pygame.K_SPACE: E.JOY_B,
            pygame.K_TAB: E.JOY_SELECT, pygame.K_RETURN: E.JOY_START}
KEYS = {pygame.K_d: "toggle_lightning", pygame.K_v: "next_view", pygame.K_p: "toggle_pause",
        pygame.K_s: "screenshot", pygame.K_f: "toggle_fullscreen", pygame.K_h: "toggle_help"}
LEFT_DIFFICULTY_A, LEFT_DIFFICULTY_B = 10, 12  # the Stella core's buttons for the left switch (docs)
SWITCH_FRAMES = 3                              # hold a switch button this long for the core to see it
VIEWS = ("both", "remaster", "2600")
ORIGINAL_W = 320                               # the 2600's 160 x 228 picture, shown at the TV's shape
GAP = 8
FPS = 60
WHITE, GREY = (236, 238, 236), (152, 150, 152)


class GameWindow:
    def __init__(self, rom_path, look_name="nes", pack_name=None):
        self.game = Game(rom_path)
        self.look = looks.make(look_name, self.game.rom, pack_name)
        pygame.display.init()  # not pygame.init(): that opens pygame's own mixer too, a second sound stream
        self.core = E.Core()
        self.core.load(rom_path)
        self.audio = E.AudioOut(int(self.core.av_info().timing.sample_rate))
        self.view = "both"
        self.paused = self.help = self.fullscreen = False
        self.lightning = True          # the left difficulty switch at B, the console's default
        self.switch_held = 0
        self.frame_no = 0
        self.picture = None
        self.screen = self.set_mode()

    # --- the loop ------------------------------------------------------------------------------------
    def run(self):
        clock = pygame.time.Clock()
        while self.handle_input():
            if not self.paused:
                self.step_game()
                self.picture = self.look.draw(self.game.state(self.core.ram), self.frame_no)
                self.frame_no += 1
            self.show()
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
        return True

    def step_game(self):
        pressed = pygame.key.get_pressed()
        held = {button for key, button in JOYSTICK.items() if pressed[key]}
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
        if self.help:
            draw_help(canvas)
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

    def next_view(self):
        self.view = VIEWS[(VIEWS.index(self.view) + 1) % len(VIEWS)]
        self.screen = self.set_mode()

    def toggle_pause(self):
        self.paused = not self.paused

    def toggle_help(self):
        self.help = not self.help

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.screen = self.set_mode()

    def screenshot(self):
        os.makedirs(paths.SCREENSHOTS, exist_ok=True)
        name = time.strftime("haunted-%Y%m%d-%H%M%S.png")
        Image.fromarray(self.canvas()).save(os.path.join(paths.SCREENSHOTS, name))


def draw_help(canvas):
    """The keys, over the top-left of the picture."""
    height = 16 + len(CONTROLS) * 12
    canvas[8:8 + height, 8:SCREEN_W - 8] = canvas[8:8 + height, 8:SCREEN_W - 8] // 4
    for row, (key, what) in enumerate(CONTROLS):
        top = 16 + row * 12
        hud.draw_text(canvas, key, 16, top, WHITE)
        hud.draw_text(canvas, what, 80, top, GREY)
