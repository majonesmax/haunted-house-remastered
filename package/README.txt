HAUNTED HOUSE, REMASTERED  (version {version})
==========================

Atari 2600 Haunted House (James Andreasen, 1982) running unmodified in an emulator (Stella), with
every frame redrawn live from the game's 128 bytes of RAM - as an NES game or a Super NES one. The
2600 picture runs alongside so you can compare. Gameplay is 100% the original.

You need your own copy of the Haunted House ROM (a 4 KB .a26 or .bin file). The first time the
game starts, it asks you to drag the ROM onto its window, and remembers it after that. Once it's
running, press H for every key - and H again for what you're trying to do and the rules the
original never explains.

STARTING IT
  macOS     Open "Haunted House.app". The app isn't signed with an Apple developer ID, so the
            first time macOS refuses to open it. Then open System Settings -> Privacy & Security,
            scroll down to '"Haunted House" was blocked', click "Open Anyway" and confirm.
            After that it opens normally. (Or, in Terminal, in this folder:
              xattr -dr com.apple.quarantine "Haunted House.app"  )
  Windows   Open "Haunted House.exe". The app isn't signed, so the first time Windows may show
            "Windows protected your PC": click "More info" -> "Run anyway".
  Linux     Run the "Haunted House" program in this folder. If there's no sound, install your
            distribution's PortAudio package (e.g. libportaudio2).

KEYS (in the game, H shows them all)
  Arrows           move
  Space            light a match; with one lit, put down what you carry
  Tab              GAME SELECT (games 1-9)
  Enter            GAME RESET (start)
  L                look: NES -> SNES
  V                view: side by side with the original -> remaster only -> 2600 only
                   -> 4-way grid: your game, the other look, the original and its live RAM
  M                music on/off (off leaves the house's own sounds)
  E                sound: remastered -> the original 2600 sound
  D                lightning on/off (the left difficulty switch)
  F                fullscreen on/off (or resize the window: the picture keeps its shape)
  S                screenshot (saved to your Pictures folder, in "Haunted House")
  R                record gameplay on/off (saved to your Movies / Videos folder, in "Haunted
                   House"; needs ffmpeg installed: https://ffmpeg.org/download.html)
  P                pause
  G                a hint: which way to the nearest piece of the urn - or, once it's whole, to
                   the front door
  O                lights on: the whole floor lit, everything on it shown (a cheat)
  H                the keys, then how to play
  Esc              quit

The remembered ROM and your own packs are kept in:
    macOS     ~/Library/Application Support/Haunted House
    Windows   %APPDATA%\Haunted House
    Linux     ~/.local/share/Haunted House

The music is original, written for this project. Licences: licenses/ (the game is MIT, its art and
music CC BY 4.0; the Stella emulator is GPL - licenses/STELLA.txt says where its source is).
