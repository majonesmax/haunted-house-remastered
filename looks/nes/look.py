"""The NES look: Haunted House as an 8-bit cartridge might have had it.

Its rules: every colour is one of the NES's 64 (shared/palettes.py); it dims and brightens the way NES games
fade, a row of the palette at a time (the same hue, darker or lighter); the urn pieces shimmer through a cycle
of colours as they do on the 2600; and the status line is drawn in the NES pixel font. Its own pack is
packs/classic.
"""

import numpy as np

from looks.base import FloorLook
from looks.layout import SCREEN_H, SCREEN_W, VIEW_H, VIEW_W, VIEW_X, VIEW_Y
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
LABEL_Y, VALUE_Y = 6, 18                       # the status band above the view: labels, then values
NAME_Y = VIEW_Y + VIEW_H + 14                  # the floor's name, below the view
SLOT = 18                                      # an item box / urn slot
URN_PIECES = {2: (2,), 3: (3,), 4: (4,), 5: (2, 3), 6: (2, 4), 7: (3, 4), 8: (2, 3, 4)}  # shape -> pieces
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
        """Above the view: matches used (and the one burning), what's carried, the urn so far, lives.
        Below it: the floor's name (from the pack), the game and the floor number."""
        hud.draw_text(screen, "MATCHES", VIEW_X, LABEL_Y, GREY)
        hud.draw_text(screen, f"{state.matches_used:02d}", VIEW_X, VALUE_Y, WHITE)
        self.draw_match(screen, state, VIEW_X + 22, VALUE_Y)
        carried_x = SCREEN_W // 2 - SLOT - 12
        hud.draw_text(screen, "HOLD", carried_x - 4, LABEL_Y, GREY)
        self.draw_carried(screen, state, frame_no, carried_x, VALUE_Y - 4)
        self.draw_urn(screen, state, frame_no, SCREEN_W // 2 + 4, VALUE_Y - 4)
        hud.draw_text(screen, "LIVES", VIEW_X + VIEW_W - 40, LABEL_Y, GREY)
        self.draw_lives(screen, state, frame_no, VIEW_X + VIEW_W - 40, VALUE_Y)
        floors = self.pack.info.get("floors") or [f"FLOOR {number}" for number in range(1, 5)]
        name = floors[state.floor].upper()
        hud.draw_text(screen, name, centred(name), NAME_Y, WHITE)
        hud.draw_text(screen, f"GAME {state.game}", VIEW_X, SCREEN_H - 14, DIM_GREY)
        floor = f"FLOOR {state.floor + 1}"
        hud.draw_text(screen, floor, VIEW_X + VIEW_W - hud.text_width(floor), SCREEN_H - 14, DIM_GREY)

    def draw_match(self, screen, state, x, y):
        """A match burning down while lit: a flame over a stick as long as the seconds left."""
        if not state.match_lit:
            return
        length = max(1, state.match_seconds)
        screen[y + 3:y + 5, x:x + length] = EMBER
        screen[y + 1:y + 7, x + length:x + length + 3] = FLAME

    def draw_carried(self, screen, state, frame_no, x, y):
        hud.frame_box(screen, x, y, x + SLOT + 1, y + SLOT + 1, DIM_GREY)
        if state.carried is None:
            return
        item = state.items[state.carried]
        name = "key" if item.number == 0 else "scepter" if item.number == 1 else f"urn{item.shape}"
        self.draw_in_slot(screen, self.picture(name, frame_no), x, y)

    def draw_urn(self, screen, state, frame_no, x, y):
        """The urn so far: three slots, one per piece. Filled: the pieces you hold, or else the biggest group
        of pieces joined together (a lone piece on the floor doesn't count)."""
        joined = ()
        if state.carried is not None and state.carried >= 2:
            joined = URN_PIECES.get(state.items[state.carried].shape, ())
        else:
            groups = [URN_PIECES.get(item.shape, ()) for item in state.items[2:]]
            biggest = max(groups, key=len)
            joined = biggest if len(biggest) > 1 else ()
        for slot, piece in enumerate((2, 3, 4)):
            left = x + slot * (SLOT + 2)
            hud.frame_box(screen, left, y, left + SLOT + 1, y + SLOT + 1, DIM_GREY)
            if piece in joined:
                self.draw_in_slot(screen, self.picture(f"urn{piece}", frame_no), left, y)

    def draw_lives(self, screen, state, frame_no, x, y):
        eyes = self.picture("eyes_centre", frame_no)
        if eyes is not None:
            blit(screen, eyes, x, y + 1)
        hud.draw_text(screen, f"X{state.lives}", x + 16, y, WHITE)

    def draw_in_slot(self, screen, sprite, x, y):
        if sprite is not None:
            blit(screen, sprite, x + 1 + (SLOT - sprite.shape[1]) // 2, y + 1 + (SLOT - sprite.shape[0]) // 2)

    def outline_colour(self):
        return BLACK

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
