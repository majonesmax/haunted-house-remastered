"""What a new player needs to be told: the story, how to play, and what each of the nine games changes.

The original kept all this in its manual. Every rule here was checked in the running game
(tools/verify_games.py, docs/rom-elements.md). Lines are short enough for the looks' 8 px font: at most 30
characters (a whole screen's width), the game rules at most 20 (beside the title's moon).
"""

STORY = [
    "OLD ZACHARY GRAVES IS DEAD.",
    "HIS MAGIC URN LIES BROKEN,",
    "ITS THREE PIECES HIDDEN IN",
    "HIS DARK MANSION.",
    "",
    "FIND THEM. JOIN THEM.",
    "CARRY THE URN OUT OF THE",
    "FRONT DOOR - IF YOU CAN.",
]

HOW_TO_PLAY = [
    ("HOW TO PLAY", "title"),
    ("FIND THE 3 PIECES OF THE URN.", ""),
    ("WALK ONE INTO ANOTHER TO JOIN", ""),
    ("THEM. CARRY THE WHOLE URN OUT", ""),
    ("OF THE FRONT DOOR: FLOOR 1,", ""),
    ("ON THE RIGHT, WHERE YOU START.", ""),
    ("", ""),
    ("TIPS", "title"),
    ("SPACE LIGHTS A MATCH. THINGS", ""),
    ("ONLY SHOW IN ITS LIGHT, CLOSE.", ""),
    ("A MONSTER IN THE ROOM PUTS IT", ""),
    ("OUT. THE SCEPTER KEEPS THEM", ""),
    ("OFF. THE KEY OPENS LOCKED", ""),
    ("DOORS. YOU HOLD ONE THING:", ""),
    ("SPACE, WITH A MATCH LIT,", ""),
    ("PUTS IT DOWN.", ""),
    ("STAIRS ARE AT ROOMS' EDGES:", ""),
    ("WALK OFF THEM TO CLIMB.", ""),
    ("FEWER MATCHES, BETTER SCORE.", ""),
]


VERDICTS = [(5, "YOU HARDLY NEEDED A LIGHT"), (15, "A STEADY HAND"), (30, "THE HOUSE TESTED YOU"),
            (None, "BUT YOU GOT OUT")]   # by matches used, fewest first: fewer is better


def verdict(matches):
    """A line on how you did: the fewer matches, the better."""
    for most, line in VERDICTS:
        if most is None or matches <= most:
            return line
    return ""


def game_rules(game):
    """Short lines saying what game `game` (1-9) is like."""
    rules = ["THE WALLS SHOW" if game == 1 else "THE HOUSE IS DARK"]
    rules.append("LOCKED DOORS" if game >= 3 else "NO LOCKED DOORS")
    if game == 3:
        rules.append("THE KEY IS NEARBY")
    rules.append(f"{3 if game <= 4 else 5} MONSTERS")
    if game >= 6:
        rules.append("THEY FOLLOW YOU")
    if game >= 7:
        rules.append("THE BAT STEALS")
    if game >= 8:
        rules.append("A FEARLESS GHOST")
    if game == 9:
        rules.append("A DIFFERENT HOUSE")
    return rules
