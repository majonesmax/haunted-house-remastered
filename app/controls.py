"""Every key, listed once: the window (app/window.py) handles them, and the help overlay (H) shows this list.

The joystick and the console's switches go to the game; the rest are the window's own.
"""

CONTROLS = [
    ("ARROWS", "MOVE"),
    ("SPACE", "MATCH / DROP"),
    ("TAB", "GAME SELECT"),
    ("ENTER", "GAME RESET"),
    ("L", "NES / SNES LOOK"),
    ("D", "LIGHTNING ON/OFF"),
    ("M", "MUSIC ON/OFF"),
    ("E", "SOUND: NEW / 2600"),
    ("V", "VIEW, GRID"),
    ("P", "PAUSE"),
    ("S", "SCREENSHOT"),
    ("R", "RECORD"),
    ("F", "FULLSCREEN"),
    ("G", "A HINT (AGAIN: MORE)"),
    ("O", "LIGHTS ON (A CHEAT)"),
    ("H", "HELP, HOW TO PLAY"),
    ("ESC", "QUIT"),
]
