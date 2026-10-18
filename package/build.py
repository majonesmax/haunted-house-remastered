"""Build Haunted House for download, on the system it runs on (the Windows build has to be made on Windows,
and so on - PyInstaller can't cross-build). (Adapted from Adventure Forever's package/build.py.)

Usage: python package/build.py [--with-rom]

  -> package/dist/Haunted-House-<version>-<system>-<processor>.zip  (.tar.gz on Linux), holding a
     "Haunted House" folder: the app (macOS: Haunted House.app; Windows: Haunted House.exe; Linux: the
     "Haunted House" program - with its files in _internal/), README.txt and licenses/.

  The public build has the packs (their pictures and soundtracks, not their source/) and asks for the
  player's ROM. --with-rom bundles roms/haunted_house.a26, for your own copies only, never for publishing
  (the zip is named ...-PERSONAL-do-not-publish).

Needs: the requirements (pip install -r requirements-dev.txt: PyInstaller), and the emulator core
(python tools/get_core.py - run for you if it's missing). Every system gets the same Stella, b52ccb02e, built
by Adventure Forever's "Stella cores" workflow. Stella is GPL-2.0: its licence, and where the exact source of
the bundled version is, go into the download (licenses/STELLA.txt).
"""

import argparse
import ctypes
import os
import platform
import shutil
import subprocess
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from game import paths  # noqa: E402

NAME = paths.APP_NAME
PACKAGE = os.path.join(ROOT, "package")
STAGE, WORK, DIST = (os.path.join(PACKAGE, folder) for folder in ("stage", "build", "dist"))
STELLA_SOURCE = "https://github.com/stella-emu/stella"
STELLA_RELEASE = "https://github.com/majonesmax/adventure-forever/releases/tag/stella-b52ccb02e"
PACK_PARTS = ("pack.json", "music.json", "cast", "world")   # what a pack needs to play; source/ stays behind
PROCESSORS = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def stage_packs(source: str, destination: str) -> None:
    """Each pack's pack.json, music.json, cast/ and world/."""
    for name in sorted(os.listdir(source)):
        pack = os.path.join(source, name)
        if not os.path.exists(os.path.join(pack, "pack.json")):
            continue
        os.makedirs(os.path.join(destination, name))
        for part in PACK_PARTS:
            path = os.path.join(pack, part)
            if os.path.isdir(path):
                shutil.copytree(path, os.path.join(destination, name, part))
            elif os.path.isfile(path):
                shutil.copy(path, os.path.join(destination, name))


def core_version() -> str:
    """The bundled Stella core's version, as it reports itself (e.g. "7.0 b52ccb02e")."""
    class Info(ctypes.Structure):
        _fields_ = [("name", ctypes.c_char_p), ("version", ctypes.c_char_p), ("extensions", ctypes.c_char_p),
                    ("need_fullpath", ctypes.c_bool), ("block_extract", ctypes.c_bool)]
    info = Info()
    ctypes.CDLL(paths.CORE).retro_get_system_info(ctypes.byref(info))
    return info.version.decode()


def stella_notice(version: str) -> str:
    commit = version.split()[-1] if " " in version else ""
    source = f"{STELLA_SOURCE}/tree/{commit}" if commit else STELLA_SOURCE
    return (f"This download includes the Stella emulator core (version {version}), which runs the game.\n"
            f"Stella is free software under the GNU General Public License, version 2 or later\n"
            f"(Stella-License-GPL-2.0.txt, Stella-Copyright.txt).\n\n"
            f"Its source code, for exactly this version: {source}\n"
            f"(the libretro core is built from src/os/libretro; the build and its source archive:\n"
            f"{STELLA_RELEASE}).\n\n"
            f"Haunted House remastered is MIT-licensed (LICENSE); its art and music are CC BY 4.0\n"
            f"(LICENSE-ASSETS.md). Haunted House is (c) 1982 Atari - not included; bring your own ROM.\n")


def icon() -> str | None:
    """The app icon for this system (macOS .icns, Windows .ico made from the preview PNG), or None."""
    if paths.SYSTEM == "macos":
        return os.path.join(PACKAGE, "icon.icns")
    if paths.SYSTEM == "windows":
        from PIL import Image
        ico = os.path.join(STAGE, "icon.ico")
        Image.open(os.path.join(PACKAGE, "icon_preview.png")).save(ico, sizes=ICO_SIZES)
        return ico
    return None


def pyinstaller_command(with_rom: bool) -> list[str]:
    """PyInstaller, told what to bundle: the packs, the fonts, the palette, the core (and the ROM)."""
    separator = os.pathsep   # PyInstaller's "source<separator>destination"
    data = [(os.path.join(STAGE, "packs"), "packs"), (paths.FONTS, "shared/fonts"),
            (os.path.join(ROOT, "game", "palette_ntsc.json"), "game")]
    if with_rom:
        data.append((paths.ROM, "roms"))
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
               "--log-level", "WARN", "--name", NAME, "--distpath", os.path.join(STAGE, "app"),
               "--workpath", WORK, "--specpath", WORK,
               "--exclude-module", "tkinter", "--exclude-module", "tools", "--exclude-module", "tests"]
    if paths.SYSTEM == "macos":
        command += ["--osx-bundle-identifier", "com.haunted-house-remastered.app"]
    app_icon = icon()
    if app_icon:
        command += ["--icon", app_icon]
    for source, destination in data:
        command += ["--add-data", f"{source}{separator}{destination}"]
    command += ["--add-binary", f"{paths.CORE}{separator}cores"]
    return command + [os.path.join(ROOT, "play.py")]


def assemble() -> str:
    """The download's folder: the app, the README and the licences."""
    folder = os.path.join(DIST, NAME)
    if paths.SYSTEM == "macos":
        os.makedirs(folder)
        shutil.move(os.path.join(STAGE, "app", f"{NAME}.app"), folder)
    else:   # the program at the top, its files in _internal/ beside it
        shutil.move(os.path.join(STAGE, "app", NAME), folder)
    with open(os.path.join(PACKAGE, "README.txt")) as readme:
        text = readme.read().replace("{version}", paths.APP_VERSION)
    newline = "\r\n" if paths.SYSTEM == "windows" else "\n"
    with open(os.path.join(folder, "README.txt"), "w", newline=newline) as readme:
        readme.write(text)
    licences = os.path.join(folder, "licenses")
    shutil.copytree(os.path.join(PACKAGE, "licenses"), licences)
    for name in ("LICENSE", "LICENSE-ASSETS.md"):
        shutil.copy(os.path.join(ROOT, name), licences)
    with open(os.path.join(licences, "STELLA.txt"), "w") as notice:
        notice.write(stella_notice(core_version()))
    return folder


def archive(folder: str, personal: bool) -> str:
    """The zip (macOS, Windows) or .tar.gz (Linux) to publish."""
    machine = platform.machine().lower()
    processor = PROCESSORS.get(machine, machine)
    label = "-PERSONAL-do-not-publish" if personal else ""
    base = os.path.join(DIST, f"Haunted-House-{paths.APP_VERSION}-{paths.SYSTEM}-{processor}{label}")
    if paths.SYSTEM == "linux":
        with tarfile.open(base + ".tar.gz", "w:gz") as tar:
            tar.add(folder, arcname=NAME)
        return base + ".tar.gz"
    if paths.SYSTEM == "macos":   # ditto keeps the .app's links and signature intact
        subprocess.run(["ditto", "-c", "-k", "--keepParent", folder, base + ".zip"], check=True)
        return base + ".zip"
    return shutil.make_archive(base, "zip", DIST, NAME)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Haunted House for download on this system.")
    parser.add_argument("--with-rom", action="store_true", help="bundle your ROM (personal builds only)")
    args = parser.parse_args()
    if not os.path.exists(paths.CORE):
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "get_core.py")], check=True)
    for folder in (STAGE, WORK, DIST):
        shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(STAGE)
    stage_packs(paths.PACKS, os.path.join(STAGE, "packs"))
    subprocess.run(pyinstaller_command(args.with_rom), check=True)
    out = archive(assemble(), args.with_rom)
    print(f"{out}  ({os.path.getsize(out) // (1024 * 1024)} MB, Stella {core_version()})")


if __name__ == "__main__":
    main()
