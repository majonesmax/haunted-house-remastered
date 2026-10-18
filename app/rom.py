"""Finding the player's Haunted House ROM (never included - bring your own). (Adapted from Adventure Forever's
app/rom.py.)

Looked for in order: a path given on the command line, roms/haunted_house.a26, then the copy remembered in the
player's folder. Failing all three, a small window asks for the ROM to be dropped onto it, and keeps a copy
for next time.
"""

import hashlib
import os
import shutil

import pygame

from app.fonts import mono
from game import paths

ROM_SIZE = 4096   # Haunted House is a 4K cartridge
KNOWN_MD5 = "f0a6e99f5875891246c3dbecbf2d2cea"   # the NTSC cartridge (CX2654) everything here was checked on
REMEMBERED = os.path.join(paths.USER_DIR, "haunted_house.a26") if paths.FROZEN else paths.ROM
WINDOW = (640, 360)


def check(path):
    """None if `path` looks like Haunted House, else what's wrong with it."""
    if not os.path.isfile(path):
        return "That isn't a file."
    if os.path.getsize(path) != ROM_SIZE:
        return f"That's {os.path.getsize(path)} bytes - the Haunted House ROM is exactly {ROM_SIZE}."
    return None


def is_known(path):
    """Is it the exact cartridge the remaster was worked out on? (Others may still play.)"""
    with open(path, "rb") as rom_file:
        return hashlib.md5(rom_file.read()).hexdigest() == KNOWN_MD5


def remember(path):
    """Keep a copy in the player's folder, so it's found next time."""
    if os.path.abspath(path) != os.path.abspath(REMEMBERED):
        os.makedirs(os.path.dirname(REMEMBERED), exist_ok=True)
        shutil.copyfile(path, REMEMBERED)
    return REMEMBERED


def find_rom(given=None):
    """The ROM's path, or None if the player closes the window without giving one."""
    if given:
        problem = check(given)
        if problem:
            print(f"{given}: {problem}", flush=True)
            return None
        return remember(given)
    for path in (paths.ROM, REMEMBERED):
        if os.path.exists(path):
            return path
    return ask()


def ask():
    """A window that waits for the ROM to be dragged onto it. Esc, or closing it, gives up."""
    pygame.display.init()
    pygame.font.init()
    screen = pygame.display.set_mode(WINDOW)
    pygame.display.set_caption(f"{paths.APP_NAME} - your ROM, please")
    problem = None
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.display.quit()
                return None
            if event.type == pygame.DROPFILE:
                problem = check(event.file)
                if problem is None:
                    pygame.display.quit()
                    return remember(event.file)
        draw_ask(screen, problem)
        pygame.display.flip()
        clock.tick(30)


def draw_ask(screen, problem):
    big, small = mono(22, bold=True), mono(15)
    lines = [(big, "Drop your Haunted House ROM here", (240, 200, 80)), (small, "", None),
             (small, "Atari 2600 Haunted House (1982): a 4 KB .a26 or .bin file.", (220, 220, 235)),
             (small, "It's remembered after the first time.", (150, 150, 175)), (small, "", None),
             (small, problem or "", (240, 110, 110)), (small, "", None),
             (small, "Esc to quit", (110, 110, 135))]
    screen.fill((16, 12, 24))
    y = 70
    for font, text, colour in lines:
        if text:
            rendered = font.render(text, True, colour)
            screen.blit(rendered, ((WINDOW[0] - rendered.get_width()) // 2, y))
        y += font.get_linesize() + 4
    pygame.draw.rect(screen, (90, 80, 120), (24, 24, WINDOW[0] - 48, WINDOW[1] - 48), 2, border_radius=10)
