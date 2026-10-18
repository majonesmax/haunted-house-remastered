"""The INTERNALS pane of the grid view: the game's whole state - 128 bytes of RAM - live, what those bytes
mean, and a log of what happened, read from how they change. Real data only: the emulator doesn't expose the
CPU, so there is no running disassembly.

    RAM        $80-$FF, 16 a row; a byte flashes when it changes and cools over a second; zeros dim
    spotlight  the last of the game's story bytes (STORY: not counters or the drawing's workings) to change,
               if it changes rarely: its name and meaning (game/ram_map.py)
    decoded    the game, floor, room, eyes, matches, lives, what's held, the urn, each monster
    events     what happened (music/events.py works them out, as it does for the sound effects)
"""

from collections import deque

import numpy as np
import pygame

from app.fonts import mono
from game import ram_map as M
from game.state import MONSTER_KINDS, GameState
from music.events import EventWatcher
from shared.types import Floats, Picture, Rgb

SIZE = (512, 480)
BACKGROUND, GREEN, DIM, HOT = (4, 10, 6), (90, 230, 130), (40, 96, 56), (255, 255, 190)
AMBER, GREY, PALE = (255, 190, 80), (120, 150, 128), (200, 225, 205)
COOL = 60                  # frames for a changed byte to cool from HOT to GREEN
EVENT_LINES = 9
DRAW_EVERY = 2             # frames: text is redrawn 30 times a second, plenty to read and half the cost
RATE_MEMORY = 0.97         # how often each byte changes: an average that forgets over a second or two
RARELY = 0.05              # ...changing on fewer than this share of frames: worth naming when it does
STORY = ({0x80, 0x82, 0x83, 0x88, 0x8D, 0x93, 0x94, 0x96, 0x97, 0x99, 0x9A, 0x9B, 0x9C, 0xCA, 0xCC, 0xDF}
         | set(range(0x9D, 0xAA)) | set(range(0xC0, 0xCA)))   # the bytes that say what's happening
ITEMS = {0: "KEY", 1: "SCEPTER", 2: "URN PIECE", 3: "URN PIECE", 4: "URN PIECE"}
URN_SHAPES = {2: "1", 3: "2", 4: "3", 5: "1+2", 6: "1+3", 7: "2+3", 8: "WHOLE", 0xFF: "-"}
EVENT_WORDS = {"match_strike": "match lit", "match_out": "match out", "door_open": "into a doorway",
               "door_close": "into a new room", "locked": "locked door", "bump": "bumped a wall",
               "stairs_up": "up the stairs", "stairs_down": "down the stairs",
               "pickup_key": "picked up the key",
               "pickup_scepter": "picked up the scepter", "pickup_urn": "picked up an urn piece",
               "drop": "put something down", "urn_join": "urn pieces joined", "urn_whole": "THE URN IS WHOLE",
               "caught": "CAUGHT", "thunder": "lightning", "monster_ghost": "the ghost is here",
               "monster_bat": "the bat is here", "monster_tarantula": "a tarantula is here"}
MODE_WORDS: dict[str, str | None] = {"playing": "game started", "dying": None,
                                     "select": "back to game select", "won": "YOU ESCAPED"}


class RamPanel:
    def __init__(self) -> None:
        pygame.font.init()
        self.font, self.bold = mono(12), mono(13, bold=True)
        self.small = mono(11)
        self.heat: Floats = np.zeros(128)
        self.change_rate: Floats = np.zeros(128)  # the share of recent frames each byte changed on
        self.previous: np.ndarray | None = None
        self.spotlight: int | None = None          # the last interesting byte to change
        self.events: deque[str] = deque(maxlen=EVENT_LINES)
        self.watcher = EventWatcher()
        self.mode: str | None = None
        self.drawn: Picture | None = None          # the pane as last drawn...
        self.draws = 0                             # ...and how many times it's been asked for

    # --- following the game ---
    def update(self, state: GameState, frame_no: int) -> None:
        """Once a game frame: what changed, and what happened."""
        ram = np.frombuffer(bytes(state.ram), np.uint8).copy()
        self.heat = np.maximum(self.heat - 1, 0)
        if self.previous is not None:
            changed = ram != self.previous
            self.heat[changed] = COOL
            story = np.isin(np.arange(0x80, 0x100), list(STORY))
            interesting = np.nonzero(changed & story & (self.change_rate < RARELY))[0]
            self.change_rate = self.change_rate * RATE_MEMORY + changed * (1 - RATE_MEMORY)
            if len(interesting):
                self.spotlight = 0x80 + int(interesting[-1])
        self.previous = ram
        for name in self.watcher.update(state):
            if name != "footstep":
                self.log(frame_no, EVENT_WORDS.get(name, str(name)))
        words = MODE_WORDS.get(state.mode)
        if state.mode != self.mode and words:
            self.log(frame_no, words if self.mode else f"game {state.game}")
        self.mode = state.mode

    def log(self, frame_no: int, text: str) -> None:
        seconds = frame_no / 60
        self.events.append(f"{int(seconds // 60)}:{seconds % 60:04.1f}  {text}")

    # --- drawing ---
    def draw(self, state: GameState) -> Picture:
        """The pane as an RGB array, SIZE: redrawn every DRAW_EVERY times it's asked for."""
        self.draws += 1
        if self.drawn is None or self.draws % DRAW_EVERY == 0:
            self.drawn = self.draw_now(state)
        return self.drawn

    def draw_now(self, state: GameState) -> Picture:
        surface = pygame.Surface(SIZE)
        surface.fill(BACKGROUND)
        y = self.text(surface, "INTERNALS - THE GAME'S 128 BYTES OF RAM", 12, 8, AMBER, self.bold)
        y = self.draw_bytes(surface, state.ram, y + 6)
        y = self.draw_spotlight(surface, y + 6)
        y = self.draw_decoded(surface, state, y + 8)
        self.draw_events(surface, y + 8)
        return pygame.surfarray.array3d(surface).swapaxes(0, 1)

    def text(self, surface: pygame.Surface, words: str, x: int, y: int, colour: Rgb,
             font: pygame.font.Font | None = None) -> int:
        font = font or self.font
        surface.blit(font.render(words, True, colour), (x, y))
        return y + font.get_linesize()

    def draw_bytes(self, surface: pygame.Surface, ram: bytes, top: int) -> int:
        """$80-$FF, 16 bytes a row, each coloured by how lately it changed."""
        step = self.font.size("00 ")[0]
        for row in range(8):
            y = top + row * self.font.get_linesize()
            self.text(surface, f"${0x80 + row * 16:02X}", 12, y, GREY)
            for column in range(16):
                index = row * 16 + column
                value = int(ram[index])
                surface.blit(self.font.render(f"{value:02X}", True, self.byte_colour(index, value)),
                             (52 + column * step, y))
        return top + 8 * self.font.get_linesize()

    def byte_colour(self, index: int, value: int) -> Rgb:
        heat = self.heat[index] / COOL
        resting = GREEN if value else DIM
        red, green, blue = (int(rest + (hot - rest) * heat) for rest, hot in zip(resting, HOT))
        return red, green, blue

    def draw_spotlight(self, surface: pygame.Surface, y: int) -> int:
        """The byte that changed last (bar the busy ones): what it is."""
        if self.spotlight is None:
            return self.text(surface, "Play, and the bytes that change are named here.", 12, y, GREY)
        name, meaning, _sure = M.describe(self.spotlight)
        y = self.text(surface, f"${self.spotlight:02X} {name}", 12, y, HOT, self.bold)
        for line in wrapped(meaning, 68)[:3]:
            y = self.text(surface, line, 12, y, PALE, self.small)
        return y

    def draw_decoded(self, surface: pygame.Surface, state: GameState, y: int) -> int:
        held = "nothing" if state.carried is None else ITEMS[state.carried].lower()
        urn = " ".join(URN_SHAPES.get(item.shape, "?") for item in state.items[2:])
        lit = f"lit, {state.match_seconds}s left" if state.match_lit else "out"
        lines = [f"{state.mode.upper():8s} game {state.game}   lives {state.lives}   matches used "
                 f"{state.matches_used}",
                 f"floor {state.floor + 1}  room {state.room}  eyes at {state.player[0]},{state.player[1]}"
                 f"   match {lit}",
                 f"holding {held}   urn pieces: {urn}"]
        for line in lines:
            y = self.text(surface, line, 12, y, GREEN)
        for monster in state.monsters:
            kind = MONSTER_KINDS[monster.number]
            here = "  IN YOUR ROOM" if monster.floor == state.floor and monster.room == state.room else ""
            follows = "  following" if monster.following else ""
            line = (f"{kind:9s} floor {monster.floor + 1} room {monster.room}  at {monster.x},{monster.y}"
                    f"  {monster.heading}{follows}{here}")
            y = self.text(surface, line, 12, y, AMBER if here else GREY, self.small)
        return y

    def draw_events(self, surface: pygame.Surface, y: int) -> None:
        y = self.text(surface, "WHAT HAPPENED", 12, y, AMBER, self.bold)
        for line in self.events:
            y = self.text(surface, line, 12, y, PALE, self.small)


def wrapped(text: str, width: int) -> list[str]:
    """Words in lines of at most `width` characters."""
    lines: list[str] = []
    line = ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + ([line] if line else [])
