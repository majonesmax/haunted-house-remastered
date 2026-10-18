"""The NES look: Haunted House as an 8-bit cartridge might have had it.

Its rules: every colour is one of the NES's 64 (shared/palettes.py); it dims and brightens the way NES games
fade, a row of the palette at a time (the same hue, darker or lighter); the urn pieces shimmer through a cycle
of colours as they do on the 2600; and the status line is drawn in the NES pixel font. Its own pack is
packs/classic.
"""

import numpy as np

from game import guide
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

# the title screen
SKY, SKY_FLASH = PAL.NES[0x01], PAL.NES[0x31]
STARS = [(14, 18), (40, 9), (61, 30), (88, 14), (117, 24), (139, 8), (165, 33), (231, 15), (248, 44),
         (25, 52), (73, 61), (150, 55), (241, 90), (9, 99), (108, 44)]
MOON_AT, MOON_SCALE = (184, 52), 2
MANSION_SCALE = 3
MANSION_AT = (32, 120)                          # 64 x 40 art at three times: the hill meets the bottom
LOGO_Y, GAME_Y, HINT_Y = 22, 46, 226
RULES_X, RULES_Y, RULE_SPACING = 12, 62, 10     # the game's rules, down the left (clear of the moon)
INTRO_Y, INTRO_SPACING, INTRO_EYES_Y = 48, 14, 176
INTRO_LINE_FRAMES = 45                          # the story appears a line at a time
NES_SKY_FLASH = np.array([0, 36, 150])        # distant lightning: towards the deep blue ($01/$02)
BANNER_TOP, BANNER_H = 10, 30                   # a floor's name, near the top of the view
TITLE_LIGHTNING_EVERY, TITLE_LIGHTNING_FRAMES = 330, 4
TITLE_LOOKS = ("centre", "left", "centre", "right", "up", "centre")
TITLE_LOOK_FRAMES = 40
# game over: the eyes look out a last time, close, the window's light flickers and goes out; then the words
EYES_CLOSE, LIGHT_FLICKER, LIGHT_OUT, GAME_OVER_WORDS = 90, 110, 150, 170
FLICKER_PATTERN = (1, 0, 1, 1, 0, 1, 0, 0, 1, 0)   # the light, 4 frames a step, as it fails
# the win: the screen lightens at the door; then dawn, the eyes walking off downhill with the urn
WON_ROWS = 2                                    # this many palette rows lighter, a row at a time
WON_FRAMES = 240                                # the game holds the win about this long
FADE_FROM_LIGHT = 40                            # the ending fades in from the light outside
DAWN_BANDS = [(0, 0x01), (28, 0x02), (56, 0x13), (84, 0x14), (112, 0x24), (140, 0x26), (168, 0x27),
              (196, 0x37)]                      # (from this row down, this colour): the NES dawn sky
DAWN_DITHER = 4                                 # rows where two bands mix, alternate rows
DAWN_STARS = [(40, 9), (139, 8), (231, 15)]     # the last few
SUN_AT, SUN_SCALE = (158, 136), 2               # behind the right wing, half risen
SUN_TINT = np.array([1.25, 0.95, 0.45])
WALK_START, WALK_SPEED = 40, 0.45               # the eyes leave the door this many frames in, this fast
LOOK_BACK_AT, LOOK_BACK_FRAMES = 172, 60        # ...stopping here for one last look back at the house
GROUND_Y = 232                                  # on the hill, below the house: where the eyes walk
ENDING_WORDS, ENDING_VERDICT = 60, 110          # when the words appear
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
        """An array of colours (..., 3) snapped to the NES palette: each distinct colour matched once."""
        red, green, blue = (rgb[..., channel].astype(np.int32) for channel in range(3))
        colours, where = np.unique((red << 16) | (green << 8) | blue, return_inverse=True)
        unpacked = np.stack([colours >> 16, (colours >> 8) & 255, colours & 255], axis=1)
        snapped = np.array([self.nearest_colour(tuple(int(c) for c in colour)) for colour in unpacked],
                           np.uint8).reshape(-1, 3)
        return snapped[where.reshape(rgb.shape[:-1])]

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

    def distant_flash(self, screen, level):
        """Lightened towards the palette's deep blue, then back into the palette: black steps through the
        blues as it fades (a grey-blue would snap to grey)."""
        return self.to_nes(np.clip(screen + NES_SKY_FLASH * level, 0, 255).astype(np.uint8))

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
        """Game select: the mansion on its hill under the moon, the eyes looking out of the tower window,
        lightning now and then. Game over: the eyes look out a last time, close, and the window's light
        flickers and goes out. After a win: the ending (draw_ending)."""
        if state.escaped:
            self.draw_ending(screen, state, self.frames_into("escaped", frame_no))
            return
        game_over = state.lives == 0
        since = self.frames_into("game_over" if game_over else "title", frame_no)
        flash = frame_no % TITLE_LIGHTNING_EVERY < TITLE_LIGHTNING_FRAMES
        screen[:] = SKY_FLASH if flash else SKY
        for x, y in STARS:
            screen[y, x] = WHITE
        self.draw_world_picture(screen, "title_moon", MOON_AT, MOON_SCALE)
        mansion = self.draw_world_picture(screen, "title_mansion", MANSION_AT, MANSION_SCALE)
        if mansion is not None and game_over and not window_lit(since):
            self.darken_window(screen)
        elif mansion is not None:
            self.draw_window_eyes(screen, frame_no, closed=game_over and since >= EYES_CLOSE)
        if game_over and since < GAME_OVER_WORDS:
            return
        self.draw_logo(screen, "GAME OVER" if game_over else "HAUNTED HOUSE")
        game = f"GAME {state.game}"
        hud.draw_text(screen, game, centred(game), GAME_Y, WHITE)
        if game_over:
            matches = f"MATCHES USED {state.matches_used}"
            hud.draw_text(screen, matches, centred(matches), GAME_Y + 12, GREY)
        else:
            for row, rule in enumerate(guide.game_rules(state.game)):
                hud.draw_text(screen, rule, RULES_X, RULES_Y + row * RULE_SPACING, GREY)
        hint = "TAB GAME   ENTER PLAY   H HELP"
        hud.draw_text(screen, hint, centred(hint), HINT_Y, GREY)

    def draw_logo(self, screen, title):
        hud.draw_text(screen, title, centred(title, 2) + 1, LOGO_Y + 2, BLOOD, scale=2, shadow=None)
        hud.draw_text(screen, title, centred(title, 2), LOGO_Y, WHITE, scale=2)

    # --- the endings ---------------------------------------------------------------------------------
    def draw_ending(self, screen, state, since):
        """After a win: dawn behind the mansion, the sun coming up behind it, the tower window dark - and
        the eyes walking off down the hill with the whole urn. Then how you did. It fades in from the
        light outside the front door."""
        self.draw_dawn_sky(screen)
        self.draw_sun(screen)
        if self.draw_world_picture(screen, "title_mansion", MANSION_AT, MANSION_SCALE) is not None:
            self.darken_window(screen)
            self.draw_eyes_leaving(screen, since)
        if since >= ENDING_WORDS:
            self.draw_score(screen, state, since)
        if since < FADE_FROM_LIGHT:
            self.lighten(screen, 1 - since / FADE_FROM_LIGHT)   # from where the win at the door left off

    def draw_dawn_sky(self, screen):
        """Bands of the NES's blues, purples, pinks and oranges, mixing on alternate rows where they meet."""
        for (top, colour), (bottom, _next) in zip(DAWN_BANDS, DAWN_BANDS[1:] + [(SCREEN_H, None)]):
            screen[top:bottom] = PAL.NES[colour]
        for (_top, upper), (top, _lower) in zip(DAWN_BANDS, DAWN_BANDS[1:]):
            screen[top:top + DAWN_DITHER:2] = PAL.NES[upper]
        for x, y in DAWN_STARS:
            screen[y, x] = WHITE

    def draw_sun(self, screen):
        """The pack's moon, warmed into a rising sun."""
        frames = self.pack.world.get("title_moon")
        if not frames:
            return
        sun = frames[0].copy()
        shade = sun[..., :3].astype(float).mean(axis=2, keepdims=True) / 255
        sun[..., :3] = np.clip(shade * 255 * SUN_TINT, 0, 255).astype(np.uint8)
        sun = self.adapt(sun).repeat(SUN_SCALE, axis=0).repeat(SUN_SCALE, axis=1)
        blit(screen, sun, *SUN_AT)

    def draw_eyes_leaving(self, screen, since):
        """From the front door, the eyes walk off down the hill to the right carrying the urn, stopping
        once to look back at the house."""
        door = self.pack.info.get("title_door")
        if not door:
            return
        start_x = MANSION_AT[0] + (door[0] + door[2] / 2) * MANSION_SCALE
        walked, looking_back = walk(since, start_x)
        eyes = self.picture("eyes_left" if looking_back else "eyes_right", since)
        urn = self.picture("urn8", since)
        if eyes is None:
            return
        x = int(start_x + walked)
        bob = 0 if looking_back else (since // 8) % 2
        blit(screen, eyes, x - eyes.shape[1] // 2, GROUND_Y - eyes.shape[0] - bob)
        if urn is not None:
            blit(screen, urn, x + eyes.shape[1] // 2 + 2, GROUND_Y - urn.shape[0] + 2 - bob)

    def draw_score(self, screen, state, since):
        self.draw_logo(screen, "YOU ESCAPED!")
        with_urn = f"WITH THE URN - GAME {state.game}"
        hud.draw_text(screen, with_urn, centred(with_urn), GAME_Y, WHITE)
        used = f"{state.matches_used} MATCH USED" if state.matches_used == 1 else \
            f"{state.matches_used} MATCHES USED"
        hud.draw_text(screen, used, centred(used), GAME_Y + 12, WHITE)
        if since >= ENDING_VERDICT:
            verdict = guide.verdict(state.matches_used)
            hud.draw_text(screen, verdict, centred(verdict), GAME_Y + 26, GREY)
            hint = "TAB GAME   ENTER PLAY   H HELP"
            hud.draw_text(screen, hint, centred(hint), GAME_Y + 44, WHITE)   # clear of the eyes' path

    def lighten(self, screen, amount):
        """The win at the door: the screen lightening `amount` (0-1) of the way - on the NES, the way its
        games fade to white, a palette row at a time."""
        rows = int(amount * (WON_ROWS + 1))
        if rows:
            screen[:] = self.shift_rows(screen, min(rows, WON_ROWS))

    def draw_intro(self, screen, frame_no):
        """The story, a line at a time, over the dark; the eyes watching from below."""
        screen[:] = BLACK
        shown = frame_no // INTRO_LINE_FRAMES + 1
        for row, line in enumerate(guide.STORY[:shown]):
            hud.draw_text(screen, line, centred(line), INTRO_Y + row * INTRO_SPACING, WHITE)
        eyes = self.picture("eyes_blink" if frame_no % 120 < 6 else "eyes_centre", frame_no)
        if eyes is not None:
            blit(screen, eyes, (SCREEN_W - eyes.shape[1]) // 2, INTRO_EYES_Y)
        if shown >= len(guide.STORY):
            hint = "PRESS ANY KEY"
            hud.draw_text(screen, hint, centred(hint), HINT_Y, DIM_GREY)

    def draw_banner(self, screen, name, subtitle, left):
        """The floor's name in a box across the top of the view."""
        width = max(hud.text_width(name), hud.text_width(subtitle)) + 24
        x0, y0 = (SCREEN_W - width) // 2, VIEW_Y + BANNER_TOP
        screen[y0:y0 + BANNER_H, x0:x0 + width] = BLACK
        hud.frame_box(screen, x0, y0, x0 + width - 1, y0 + BANNER_H - 1, GREY)
        hud.draw_text(screen, name, centred(name), y0 + 6, WHITE)
        hud.draw_text(screen, subtitle, centred(subtitle), y0 + 18, GREY)

    def draw_world_picture(self, screen, name, at, scale):
        """A world picture (the pack's own title art), scaled up, at (x, y); None if the pack has none."""
        frames = self.pack.world.get(name)
        if not frames:
            return None
        picture = self.adapt(frames[0]).repeat(scale, axis=0).repeat(scale, axis=1)
        blit(screen, picture, *at)
        return picture

    def darken_window(self, screen):
        window = self.pack.info.get("title_window")
        if window:
            x, y, width, height = (value * MANSION_SCALE for value in window)
            top, left = MANSION_AT[1] + y, MANSION_AT[0] + x
            screen[top:top + height, left:left + width] = BLACK

    def draw_window_eyes(self, screen, frame_no, closed=False):
        """The eyes in the lit tower window: looking around, and blinking (or closed)."""
        window = self.pack.info.get("title_window")
        if not window:
            return
        x, y, width, height = (value * MANSION_SCALE for value in window)
        look = TITLE_LOOKS[frame_no // TITLE_LOOK_FRAMES % len(TITLE_LOOKS)]
        blinking = closed or frame_no % 180 < 8
        eyes = self.picture("eyes_blink" if blinking else f"eyes_{look}", frame_no)
        if eyes is not None:
            screen_x = MANSION_AT[0] + x + (width - eyes.shape[1]) // 2
            screen_y = MANSION_AT[1] + y + (height - eyes.shape[0]) // 2
            height, width = eyes.shape[:2]
            screen[screen_y - 1:screen_y + height + 1, screen_x - 1:screen_x + width + 1] = BLACK  # the room
            blit(screen, eyes, screen_x, screen_y)

    def draw_win(self, screen, state, frame_no):
        """Out of the front door with the urn: the light outside grows as the game holds the moment."""
        since = self.frames_into("won", frame_no)
        self.lighten(screen, min(1.0, since / WON_FRAMES))
        banner = "YOU ESCAPED!"
        hud.draw_text(screen, banner, centred(banner, 2), VIEW_Y + 20, flash_colour(frame_no), scale=2)


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


def window_lit(since):
    """Game over: is the tower window still lit, `since` frames in? Lit, then flickering, then out."""
    if since < LIGHT_FLICKER:
        return True
    if since >= LIGHT_OUT:
        return False
    return bool(FLICKER_PATTERN[(since - LIGHT_FLICKER) // 4 % len(FLICKER_PATTERN)])


def walk(since, start_x):
    """The eyes leaving from start_x: (pixels walked, looking back?) `since` frames into the ending."""
    walking = max(0, since - WALK_START)
    stop_at = (LOOK_BACK_AT - start_x) / WALK_SPEED   # frames of walking to the look-back spot
    if walking < stop_at:
        return walking * WALK_SPEED, False
    if walking < stop_at + LOOK_BACK_FRAMES:
        return stop_at * WALK_SPEED, True
    return (walking - LOOK_BACK_FRAMES) * WALK_SPEED, False


def flash_colour(frame_no):
    return PAL.NES[PAL.flash_colour(frame_no)]


def centred(text, scale=1):
    return (SCREEN_W - hud.text_width(text, scale)) // 2
