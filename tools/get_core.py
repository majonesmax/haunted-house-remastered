"""Download the Stella (Atari 2600) libretro core into cores/ - the emulator the game runs on (GPL-2.0,
https://github.com/stella-emu/stella).

Every computer gets the SAME Stella: commit STELLA_COMMIT below, built for each platform by this repository's
"Stella cores" workflow (.github/workflows/stella-cores.yml) and published as the release stella-<commit>,
with checksums and that commit's source. The tests' reference pictures were made with it.

Why not libretro's nightly builds: their servers only keep "latest", and it differs per platform. Since
March 2026 Stella needs macOS 26 to compile (std::from_chars for floats), so libretro's macOS build has
been stuck at b52ccb02e while Windows and Linux moved on. b52ccb02e is also the last Stella that runs on
older Macs (macOS 11+ here).

Usage: python tools/get_core.py             the pinned core for this system (checksum verified)
       python tools/get_core.py --force     download it again even if it's there
       python tools/get_core.py --nightly   libretro's latest instead (for trying newer Stella; untested)

To try a different core without replacing this one, point HAUNTED_CORE at it:
       HAUNTED_CORE=/path/to/stella_libretro.dylib python play.py
"""

import hashlib
import io
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # the repo root
from game import paths

STELLA_COMMIT = "b52ccb02e"
REPO = "majonesmax/adventure-forever"
RELEASE = f"stella-{STELLA_COMMIT}"
NAMES = {("macos", "arm64"): "macos-arm64", ("macos", "x86_64"): "macos-x64",
         ("windows", "x86_64"): "windows-x64", ("linux", "x86_64"): "linux-x64"}
NIGHTLY = {("macos", "arm64"): "apple/osx/arm64", ("macos", "x86_64"): "apple/osx/x86_64",
           ("windows", "x86_64"): "windows/x86_64", ("linux", "x86_64"): "linux/x86_64"}


def processor():
    machine = platform.machine().lower()
    return {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(machine, machine)


def fetch(asset):
    """An asset of the pinned release: from GitHub directly, else (a private repository) through `gh`."""
    url = f"https://github.com/{REPO}/releases/download/{RELEASE}/{asset}"
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError:
        if not shutil.which("gh"):
            raise SystemExit(f"couldn't download {url} (if the repository is private, install the GitHub CLI "
                             f"and run `gh auth login` first)")
    with tempfile.TemporaryDirectory() as tmp:
        download = ["gh", "release", "download", RELEASE, "--repo", REPO, "--pattern", asset, "--dir", tmp]
        subprocess.run(download, check=True)
        with open(os.path.join(tmp, asset), "rb") as f:
            return f.read()


def pinned(system, cpu):
    name = NAMES.get((system, cpu))
    if name is None:
        raise SystemExit(f"no ready-made core for {system} on {cpu}: build Stella {STELLA_COMMIT} "
                         f"(src/os/libretro) and put {paths.CORE_FILE} in cores/")
    asset = f"stella-{STELLA_COMMIT}-{name}.zip"
    data = fetch(asset)
    lines = [line for line in fetch("SHA256SUMS.txt").decode().splitlines() if line]
    sums = dict(reversed(line.split(maxsplit=1)) for line in lines)
    if hashlib.sha256(data).hexdigest() != sums.get(asset):
        raise SystemExit(f"{asset} doesn't match its SHA-256 in the release - not installed")
    print(f"Stella {STELLA_COMMIT} for {name}: checksum OK")
    return data


def nightly(system, cpu):
    folder = NIGHTLY.get((system, cpu))
    if folder is None:
        raise SystemExit(f"libretro has no nightly core for {system} on {cpu}")
    url = f"https://buildbot.libretro.com/nightly/{folder}/latest/{paths.CORE_FILE}.zip"
    print(f"downloading {url} (libretro's latest - not the tested version)")
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def main():
    target = os.path.join(paths.ROOT, "cores", paths.CORE_FILE)
    if os.path.exists(target) and "--force" not in sys.argv and "--nightly" not in sys.argv:
        print(f"already there: {target}")
        return 0
    get = nightly if "--nightly" in sys.argv else pinned
    data = get(paths.SYSTEM, processor())
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as out:
            out.write(z.read(paths.CORE_FILE))  # only the core itself, whatever else the zip holds
    if paths.SYSTEM != "windows":
        os.chmod(target, 0o755)
    print(f"-> {target} ({os.path.getsize(target) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
