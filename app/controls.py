"""Every key, listed once: the window (app/window.py) handles them, and the help overlay (H) shows this list.

The joystick and the console's switches go to the game; the rest are the window's own.
"""

CONTROLS = [
    ("ARROWS", "MOVE"),
    ("SPACE", "MATCH / DROP"),
    ("TAB", "GAME SELECT"),
    ("ENTER", "GAME RESET"),
    ("D", "LIGHTNING ON/OFF"),
    ("M", "MUSIC ON/OFF"),
    ("E", "SOUND: NEW / 2600"),
    ("V", "VIEW"),
    ("P", "PAUSE"),
    ("S", "SCREENSHOT"),
    ("F", "FULLSCREEN"),
    ("H", "HELP"),
    ("ESC", "QUIT"),
]
