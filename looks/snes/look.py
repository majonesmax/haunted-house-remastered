"""The SNES look: Haunted House as a 16-bit Super Nintendo game might have had it.

It keeps the NES look's layout and screens (looks/nes/look.py) and changes the console's rules to what the
SNES could do:
  colour    15-bit (32 levels a channel); sprites get soft outlines and at most 15 colours (outline.py)
  light     colour math instead of dithering: the match's light is a smooth warm gradient, hottest at the
            flame, with dust drifting in it; in game 1, unlit walls are moonlit blue and shafts of moonlight
            fall across the floor; lightning washes
            everything pale blue-white
  ghosts    see-through (a translucent sprite layer)
  sound     the orchestra synth (music/orchestra.py): organ, harpsichord, strings, timpani, in a hall
  screens   gradient status panels with bevelled edges; a title screen with a gradient night sky, the moon's
            halo, falling rain and lightning that fades out
Its own pack is packs/nocturne, drawn in 16-bit colour ramps.
"""

import numpy as np

from looks.base import FloorLook, flicker, light_reach_grid
from looks.layout import SCREEN_H, SCREEN_W, VIEW_H, VIEW_W, VIEW_Y
from looks.nes.look import MANSION_AT, MOON_AT, SUN_AT, SUN_SCALE, NesLook
from looks.snes.outline import recolour_outline
from shared.pixelart import snes_rgb

LIGHT_FULL, LIGHT_GONE = 0.55, 1.3      # fully lit inside this much of the reach; nothing past this
WARM = np.array([1.08, 0.94, 0.76])     # the match's light, warm
FLAME_GLOW = np.array([70, 34, 0])      # added close to the flame
MOONLIGHT = np.array([0.42, 0.48, 0.72])  # unlit walls (game 1): cold and blue
UNLIT_FLOOR = np.array([0.12, 0.13, 0.2])
MOON_SHAFTS = np.array([0.1, 0.12, 0.2])    # game 1: shafts of moonlight across the floor add this much...
SHAFT_EVERY, SHAFT_WIDTH = 104, 34          # ...a shaft every this many pixels along the floor, this wide
SHAFT_SLANT = 0.7                           # pixels across per pixel down: the light falls in at a slant
DIM = np.array([0.32, 0.34, 0.5])       # the edge of the light, and the shadows under the faces
LIGHTNING_WASH = np.array([150, 170, 220])
GHOST_OPACITY = 0.62
DYING_RED = np.array([1.0, 0.35, 0.35])
STATUS_TOP = (52, 24, 80)               # the status panels: a gradient from this...
STATUS_BOTTOM = (8, 4, 20)              # ...to this
BEVEL_LIGHT, BEVEL_DARK = (120, 96, 168), (20, 10, 36)
SKY_TOP, SKY_HORIZON = np.array([10, 6, 30]), np.array([60, 40, 110])
MOON_HALO = np.array([90, 96, 130])
RAIN = (110, 120, 170)
RAIN_DROPS = 70
FLASH_FRAMES = 14                        # the title's lightning fades out over this many frames
FLASH_EVERY = 330
DAWN_LIGHT = (255, 214, 160)             # the win: the view warms towards the light outside...
WARMING = 0.6                            # ...this far, as the game holds the moment
DAWN = [(0.0, (34, 40, 96)), (0.45, (150, 90, 150)), (0.75, (240, 150, 120)), (1.0, (255, 210, 140))]
SUN_GLOW = np.array([255, 220, 150])     # the sky round the rising sun
SUN_GLOW_REACH = 70                      # pixels
DUST_MOTES = 140                         # specks of dust over the whole view; only those in the light show
DUST = np.array([160, 135, 95])          # how much a speck in full light brightens its pixel
DUST_DRIFT = 0.15                        # pixels a frame they sink...
DUST_SWAY = 3                            # ...swaying this many pixels side to side


class SnesLook(NesLook):
    platform = "snes"
    name = "SNES REMASTER"
    pack_name = "nocturne"
    synth = "orchestra"

    # --- colours -------------------------------------------------------------------------------------
    def adapt(self, picture):
        """15-bit colour, then soft outlines and at most 15 colours (a sprite palette)."""
        return recolour_outline(self.adapt_scenery(picture))

    def adapt_scenery(self, picture):
        out = picture.copy()
        out[..., :3] = snes_rgb(out[..., :3])
        return out

    def distant_flash(self, screen, level):
        return snes_rgb(FloorLook.distant_flash(self, screen, level))  # not the NES's palette

    def dimmed(self, rgb):
        return snes_rgb(np.clip(rgb * DIM, 0, 255).astype(np.uint8))

    def lightning_colour(self, rgb):
        return snes_rgb(np.clip(rgb * 0.5 + LIGHTNING_WASH, 0, 255).astype(np.uint8))

    def outline_colour(self):
        return (12, 6, 20)

    def opacity(self, name):
        return GHOST_OPACITY if name.startswith("ghost") else 1.0

    # --- the light: colour math ----------------------------------------------------------------------
    def light(self, state, layers, rows, frame_no):
        """A smooth, warm gradient around the match (hottest at the flame) over the unlit scene: moonlit
        walls in game 1, black in games 2-9, the walls washed pale in a lightning flash."""
        if state.lights_on:   # the player's cheat: every lamp in the house lit
            return snes_rgb(layers.full)
        full, walls = layers.full.astype(float), layers.walls[..., None]
        reach = light_reach_grid(state, rows) / flicker(frame_no)
        if not state.dark:
            unlit = np.where(walls, full * MOONLIGHT, full * (UNLIT_FLOOR + MOON_SHAFTS * moon_shafts(rows)))
        elif state.lightning:
            unlit = np.where(walls, layers.flash.astype(float), full * UNLIT_FLOOR)
        else:
            unlit = np.zeros_like(full)
        glow = np.clip((LIGHT_GONE - reach) / (LIGHT_GONE - LIGHT_FULL), 0, 1)[..., None]
        heat = np.clip(1 - reach / LIGHT_FULL, 0, 1)[..., None]
        lit = full * WARM + FLAME_GLOW * heat
        picture = unlit * (1 - glow) + lit * glow
        add_dust(picture, glow[..., 0], frame_no)
        return snes_rgb(np.clip(picture, 0, 255).astype(np.uint8))

    def view(self, state, frame_no):
        picture = FloorLook.view(self, state, frame_no)  # not the NES's: its dying flicker is palette-bound
        if state.mode == "dying":
            pulse = 0.5 + 0.5 * np.sin(frame_no / 4)
            tint = 1 - (1 - DYING_RED) * pulse
            picture = snes_rgb(np.clip(picture * tint, 0, 255).astype(np.uint8))
        return picture

    # --- the endings -----------------------------------------------------------------------------------
    def draw_dawn_sky(self, screen):
        """A smooth dawn, deep blue overhead to gold at the hill, glowing round the sun."""
        rows = np.linspace(0, 1, SCREEN_H)
        stops, colours = zip(*DAWN)
        sky = np.stack([np.interp(rows, stops, [colour[channel] for colour in colours])
                        for channel in range(3)], axis=1)
        screen[:] = sky[:, None, :].astype(np.uint8)
        sun_size = 20 * SUN_SCALE
        centre_x, centre_y = SUN_AT[0] + sun_size / 2, SUN_AT[1] + sun_size / 2
        rows, columns = np.mgrid[:SCREEN_H, :SCREEN_W]
        glow = np.clip(1 - np.hypot(columns - centre_x, rows - centre_y) / SUN_GLOW_REACH, 0, 1)[..., None]
        screen[:] = (screen * (1 - glow * 0.7) + SUN_GLOW * glow * 0.7).astype(np.uint8)

    def lighten(self, screen, amount):
        """The win at the door (and the ending fading in): the screen warming smoothly towards the light
        outside, `amount` (0-1) of the way to WARMING."""
        warmed = screen * (1 - WARMING * amount) + np.array(DAWN_LIGHT) * WARMING * amount
        screen[:] = snes_rgb(np.clip(warmed, 0, 255).astype(np.uint8))

    # --- the status panels ----------------------------------------------------------------------------
    def draw_status(self, screen, state, frame_no):
        panel(screen, 0, VIEW_Y - 4)
        panel(screen, VIEW_Y + VIEW_H + 4, SCREEN_H)
        super().draw_status(screen, state, frame_no)

    # --- the title screen -----------------------------------------------------------------------------
    def draw_title(self, screen, state, frame_no):
        """The NES title's night, with what 16 bits allow: a gradient sky, the moon's halo, rain, and
        lightning that fades. After a win, the NES ending's dawn in smooth colour."""
        super().draw_title(screen, state, frame_no)
        if state.escaped:
            screen[:] = snes_rgb(screen)
            return
        mansion_top = MANSION_AT[1]
        flash = lightning_level(frame_no)
        sky = sky_gradient(mansion_top + 40)
        sky = sky + (255 - sky) * flash
        is_sky = (screen[:mansion_top + 40] == screen[0, 0]).all(axis=2)  # what the NES title left as sky
        screen[:mansion_top + 40][is_sky] = sky[is_sky].astype(np.uint8)
        add_moon_halo(screen, is_sky)
        add_rain(screen, frame_no)
        screen[:] = snes_rgb(screen)


def moon_shafts(rows):
    """0-1 over the view: soft slanting bands of moonlight, fixed to the floor (so they scroll with it)."""
    row_numbers = np.arange(rows.start, rows.stop)[:, None]
    columns = np.arange(VIEW_W)[None, :]
    along = (columns + row_numbers * SHAFT_SLANT) % SHAFT_EVERY
    middle = np.abs(along - SHAFT_EVERY / 2) / (SHAFT_WIDTH / 2)   # 0 at a shaft's middle, 1 at its edge
    return np.clip(1 - middle, 0, 1)[..., None] ** 0.7


def panel(screen, top, bottom):
    """A gradient panel with a bevelled edge (light along the top, dark along the bottom)."""
    rows = np.linspace(0, 1, bottom - top)[:, None]
    gradient = np.array(STATUS_TOP) * (1 - rows) + np.array(STATUS_BOTTOM) * rows
    screen[top:bottom] = gradient[:, None, :].astype(np.uint8)
    screen[top] = BEVEL_LIGHT
    screen[bottom - 1] = BEVEL_DARK


def lightning_level(frame_no):
    """1 at a strike, fading to 0 over FLASH_FRAMES."""
    since = frame_no % FLASH_EVERY
    return max(0.0, 1 - since / FLASH_FRAMES) * 0.85


def sky_gradient(height):
    rows = np.linspace(0, 1, height)[:, None, None]
    gradient = SKY_TOP * (1 - rows) + SKY_HORIZON * rows
    return np.repeat(gradient, SCREEN_W, axis=1)


def add_moon_halo(screen, is_sky):
    """A soft glow around the moon, on the sky only."""
    centre_x, centre_y = MOON_AT[0] + 20, MOON_AT[1] + 20
    rows, columns = np.mgrid[:is_sky.shape[0], :SCREEN_W]
    distance = np.hypot(columns - centre_x, rows - centre_y)
    halo = np.clip(1 - (distance - 20) / 40, 0, 1)[..., None] * 0.6
    sky = screen[:is_sky.shape[0]].astype(float)
    glowing = sky + (MOON_HALO - sky) * halo
    screen[:is_sky.shape[0]] = np.where(is_sky[..., None], glowing, sky).astype(np.uint8)


def add_dust(picture, glow, frame_no):
    """Specks of dust sinking and swaying through the view, seen only where the match lights them. The
    same specks every time round, so pictures repeat."""
    rng = np.random.default_rng(7)
    height, width = glow.shape
    starts_x = rng.uniform(0, width, DUST_MOTES)
    starts_y = rng.uniform(0, height, DUST_MOTES)
    phases = rng.uniform(0, 2 * np.pi, DUST_MOTES)
    floor_xs = (starts_x + DUST_SWAY * np.sin(frame_no / 40 + phases)).astype(int) % width
    floor_ys = (starts_y + frame_no * DUST_DRIFT).astype(int) % height
    twinkle = 0.6 + 0.4 * np.sin(frame_no / 9 + phases)
    picture[floor_ys, floor_xs] += DUST * (glow[floor_ys, floor_xs] * twinkle)[:, None]


def add_rain(screen, frame_no):
    """Thin streaks falling at a slant, the same pattern every time round."""
    rng = np.random.default_rng(5)
    starts_x = rng.integers(0, SCREEN_W, RAIN_DROPS)
    starts_y = rng.integers(0, SCREEN_H, RAIN_DROPS)
    speeds = rng.integers(5, 9, RAIN_DROPS)
    for x, y, speed in zip(starts_x, starts_y, speeds):
        drop_y = (y + frame_no * speed) % SCREEN_H
        drop_x = (x - (frame_no * speed) // 3) % SCREEN_W
        for step in range(4):
            row, column = drop_y + step, (drop_x - step // 2) % SCREEN_W
            if row < SCREEN_H:
                screen[row, column] = RAIN
