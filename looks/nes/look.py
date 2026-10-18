"""The NES look: Haunted House as an 8-bit cartridge might have had it.

Its rules: every colour is one of the NES's 64 (shared/palettes.py); it dims and brightens the way NES games
fade, a row of the palette at a time (the same hue, darker or lighter); the urn pieces shimmer through a cycle
of colours as they do on the 2600; and the status line is drawn in the NES pixel font. Its own pack is
packs/classic.
"""

import numpy as np

from looks.base import CELL_PX, SCREEN_W, VIEW_H, VIEW_W, VIEW_X, VIEW_Y, FloorLook
from shared import hud
from shared import palettes as PAL
from shared.pixelart import blit

NES_COLOURS = np.array(PAL.NES, int)
BLACK = PAL.NES[PAL.BLACK]
WHITE = PAL.NES[0x30]
GREY = PAL.NES[0x10]
DIM_GREY = PAL.NES[0x00]
EMBER = PAL.NES[0x27]
FLAME = PAL.NES[0x28]
BLOOD = PAL.NES[0x16]
DIM_ROWS = 1                                   # what's seen but not lit: a palette row darker
LIGHTNING_ROWS = 2                             # walls in a lightning flash: two rows lighter
ROW = 0x10                                     # the NES palette: 4 rows of 16, darkest first
FIRST_BLACK_HUE = 0x0D                         # hues $D-$F of each row are black (and $2D, $3D greys)
URN_SHADES = 2                                 # the urn art's two colours: its fill and its shade
STATUS_Y = VIEW_Y + VIEW_H + 12
MATCH_SECONDS = 20


class NesLook(FloorLook):
    platform = "nes"
    name = "NES REMASTER"
    pack_name = "classic"

    def __init__(self, pack, rom):
        super().__init__(pack, rom)
        self.nearest = {}  # (r, g, b) -> its NES colour

    # --- colours -------------------------------------------------------------------------------------
    def to_nes(self, rgb):
        """An array of colours (..., 3) snapped to the NES palette."""
        flat = rgb.reshape(-1, 3)
        colours, where = np.unique(flat, axis=0, return_inverse=True)
        snapped = np.array([self.nearest_colour(tuple(colour)) for colour in colours], np.uint8)
        return snapped[where.reshape(-1)].reshape(rgb.shape)

    def nearest_colour(self, rgb):
        if rgb not in self.nearest:
            distances = ((NES_COLOURS - np.array(rgb, int)) ** 2).sum(axis=1)
            self.nearest[rgb] = tuple(int(channel) for channel in NES_COLOURS[distances.argmin()])
        return self.nearest[rgb]

    def adapt(self, picture):
        adapted = picture.copy()
        adapted[..., :3] = self.to_nes(picture[..., :3])
        return adapted

    def dimmed(self, rgb):
        return self.shift_rows(rgb, -DIM_ROWS)

    def lightning_colour(self, rgb):
        return self.shift_rows(rgb, LIGHTNING_ROWS)

    def shift_rows(self, rgb, rows):
        """Every colour moved `rows` rows up (lighter) or down (darker) the NES palette, keeping its hue."""
        flat = rgb.reshape(-1, 3)
        colours, where = np.unique(flat, axis=0, return_inverse=True)
        moved = np.array([PAL.NES[shifted(PAL.nearest_nes(colour), rows)] for colour in colours], np.uint8)
        return moved[where.reshape(-1)].reshape(rgb.shape)

    def background(self):
        return BLACK

    # --- the view: the urn shimmers, and dying turns it red ------------------------------------------
    def picture(self, name, frame_no):
        sprite = super().picture(name, frame_no)
        if sprite is None or not name.startswith("urn"):
            return sprite
        return shimmer(sprite, frame_no)

    def view(self, state, frame_no):
        picture = super().view(state, frame_no)
        if state.mode == "dying" and frame_no // 4 % 2:
            tinted = picture.astype(int)
            tinted[..., 1:] //= 3
            picture = self.to_nes(tinted.astype(np.uint8))
        return picture

    # --- the status line, title and win ---------------------------------------------------------------
    def draw_status(self, screen, state, frame_no):
        hud.draw_text(screen, f"GAME {state.game}", VIEW_X, 12, GREY)
        floor = f"FLOOR {state.floor + 1}"
        hud.draw_text(screen, floor, VIEW_X + VIEW_W - hud.text_width(floor), 12, GREY)
        top = STATUS_Y
        hud.frame_box(screen, VIEW_X, top - 6, VIEW_X + VIEW_W - 1, top + 38, DIM_GREY)
        hud.draw_text(screen, "MATCHES", VIEW_X + 8, top, GREY)
        hud.draw_text(screen, f"{state.matches_used:02d}", VIEW_X + 8, top + 14, WHITE, scale=2)
        self.draw_match(screen, state, VIEW_X + 48, top + 14)
        self.draw_carried(screen, state, frame_no, SCREEN_W // 2 - CELL_PX // 2, top + 2)
        hud.draw_text(screen, "LIVES", VIEW_X + VIEW_W - 48, top, GREY)
        hud.draw_text(screen, str(state.lives), VIEW_X + VIEW_W - 32, top + 14, WHITE, scale=2)

    def draw_match(self, screen, state, x, y):
        """A match burning down while lit: a flame over a stick as long as the seconds left."""
        if not state.match_lit:
            return
        length = max(1, state.match_seconds)
        screen[y + 6:y + 8, x:x + length] = EMBER
        screen[y + 4:y + 10, x + length:x + length + 3] = FLAME

    def draw_carried(self, screen, state, frame_no, x, y):
        hud.frame_box(screen, x - 4, y - 4, x + CELL_PX + 3, y + CELL_PX + 3, DIM_GREY)
        if state.carried is None:
            return
        item = state.items[state.carried]
        name = "key" if item.number == 0 else "scepter" if item.number == 1 else f"urn{item.shape}"
        sprite = self.picture(name, frame_no)
        if sprite is not None:
            blit(screen, sprite, x + (CELL_PX - sprite.shape[1]) // 2, y + (CELL_PX - sprite.shape[0]) // 2)

    def draw_title(self, screen, state, frame_no):
        game_over = state.lives == 0
        title = "GAME OVER" if game_over else "HAUNTED HOUSE"
        hud.draw_text(screen, title, centred(title, 2), 64, WHITE, scale=2)
        eyes = self.picture("eyes_centre", frame_no)
        blinking = frame_no % 180 < 6
        if eyes is not None and not blinking:
            blit(screen, eyes, (SCREEN_W - eyes.shape[1]) // 2, 108)
        game = f"GAME {state.game}"
        hud.draw_text(screen, game, centred(game), 140, GREY)
        if game_over:
            matches = f"MATCHES USED {state.matches_used}"
            hud.draw_text(screen, matches, centred(matches), 160, GREY)
        hint = "SELECT: TAB   START: ENTER"
        hud.draw_text(screen, hint, centred(hint), 200, DIM_GREY)

    def draw_win(self, screen, state, frame_no):
        banner = "YOU ESCAPED!"
        hud.draw_text(screen, banner, centred(banner, 2), VIEW_Y + 20, flash_colour(frame_no), scale=2)
        matches = f"WITH {state.matches_used} MATCHES"
        hud.draw_text(screen, matches, centred(matches), VIEW_Y + 44, WHITE)


def shifted(index, rows):
    """A NES colour index `rows` rows lighter (+) or darker (-); off the bottom is black, off the top the
    lightest row."""
    if index & 0x0F >= FIRST_BLACK_HUE:
        return PAL.BLACK
    row = (index >> 4) + rows
    if row < 0:
        return PAL.BLACK
    return min(row, 3) * ROW + (index & 0x0F)


def shimmer(sprite, frame_no):
    """Recolour the urn: its brightest colour and its shade follow the NES flash cycle."""
    solid = sprite[..., 3] > 0
    colours = np.unique(sprite[solid][:, :3], axis=0)
    if len(colours) == 0:
        return sprite
    brightness = colours.sum(axis=1)
    order = np.argsort(-brightness)[:URN_SHADES]
    flash = np.array(PAL.NES[PAL.flash_colour(frame_no)])
    shimmered = sprite.copy()
    for rank, index in enumerate(order):
        match = solid & (sprite[..., :3] == colours[index]).all(axis=2)
        shimmered[match, :3] = flash if rank == 0 else flash // 2
    return shimmered


def flash_colour(frame_no):
    return PAL.NES[PAL.flash_colour(frame_no)]


def centred(text, scale=1):
    return (SCREEN_W - hud.text_width(text, scale)) // 2
