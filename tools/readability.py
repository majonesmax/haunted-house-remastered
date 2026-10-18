"""Readability check: code that's easy for a person to read, whoever (or whatever) wrote it.

Three kinds of issue, counted per file:
  ruff's readability rules (ruff.toml): long lines, two statements on a line, named lambdas, functions with
      too many branches, statements or arguments, blocks nested too deep
  names shorter than 3 letters (N001), outside a few everyone knows: i, j, k, x, y, dx, dy, w, h, f, e, ...
  type errors (TYPE): pyright's findings (pyrightconfig.json) - a type hint the code doesn't keep to

The code already has some of these. Rather than fix everything at once, the counts are a ratchet: each file's
count of each kind is saved in tools/readability_baseline.json, and a file may not get worse. Clean a file up,
then run --update to lock the improvement in.

Usage: python tools/readability.py              every file against the baseline (exit 1 if one got worse)
       python tools/readability.py FILE...      list the issues in these files
       python tools/readability.py --update     save the current counts as the baseline
       python tools/readability.py --hook       for a Claude Code PostToolUse hook (.claude/settings.json):
                                                reads the edited file from stdin; exit 2 + the issues if worse
Needs ruff and pyright (pip install -r requirements-dev.txt); without them only names are checked.
"""

import ast
import collections
import json
import os
import shutil
import subprocess
import sys
from typing import Iterator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "tools", "readability_baseline.json")
SKIP = {".venv", "private", "reference", "shots", "recordings", "art", "lib", "build", "dist", "stage",
        "__pycache__", ".git"}
SHORT_NAMES_OK = {"_", "i", "j", "k", "x", "y", "z", "dx", "dy", "x0", "y0", "x1", "y1", "xx", "yy", "w", "h",
                  "f", "e", "ok", "id"}
MIN_NAME = 3
Issue = tuple[str, int, str, str]   # (file, line, code, message)
Counts = dict[str, dict[str, int]]  # {file: {code: count}}


def python_files() -> Iterator[str]:
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [sub for sub in dirs if sub not in SKIP]
        for name in files:
            if name.endswith(".py"):
                yield os.path.relpath(os.path.join(folder, name), ROOT)


def find_tool(name: str) -> str | None:
    """A development tool (ruff, pyright): the project's own, else one on the PATH."""
    candidates = (os.path.join(ROOT, ".venv", "bin", name),
                  os.path.join(ROOT, ".venv", "Scripts", f"{name}.exe"),
                  shutil.which(name))
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def ruff_issues(files: list[str]) -> list[Issue]:
    """[(file, line, code, message)] from ruff's readability rules."""
    ruff = find_tool("ruff")
    if ruff is None or not files:
        return []
    result = subprocess.run([ruff, "check", "--output-format", "json", "--no-cache", *files],
                            cwd=ROOT, capture_output=True, text=True)
    issues: list[Issue] = []
    for item in json.loads(result.stdout or "[]"):
        path = os.path.relpath(item["filename"], ROOT)
        issues.append((path, item["location"]["row"], item["code"], item["message"]))
    return issues


def bound_names(node: ast.AST) -> Iterator[tuple[str, int]]:
    """(name, line) for every name a piece of code introduces: parameters, assignments, loop variables..."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        args = node.args
        for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
            if arg is not None and arg.arg not in ("self", "cls"):
                yield arg.arg, arg.lineno
    elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        yield node.id, node.lineno


def short_names(path: str) -> list[Issue]:
    """[(file, line, "N001", message)] - each too-short name once per function."""
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    issues: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    for scope in ast.walk(tree):
        if not isinstance(scope, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for node in ast.walk(scope):
            for name, line in bound_names(node):
                key = (getattr(scope, "name", "<module>"), name)
                if len(name) < MIN_NAME and name not in SHORT_NAMES_OK and key not in seen:
                    seen.add(key)
                    issues.append((path, line, "N001", f"short name `{name}`: say what it is"))
    return issues


def project_python() -> str:
    """The Python whose packages pyright should see: the project's .venv, else this one (a build server's)."""
    candidates = (os.path.join(ROOT, ".venv", "bin", "python"),
                  os.path.join(ROOT, ".venv", "Scripts", "python.exe"))
    for path in candidates:
        if os.path.exists(path):
            return path
    return sys.executable


def type_issues(files: list[str]) -> list[Issue]:
    """[(file, line, "TYPE", message)] from pyright, the type checker."""
    pyright = find_tool("pyright")
    if pyright is None or not files:
        return []
    command = [pyright, "--outputjson", "--pythonpath", project_python(), *files]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    report = json.loads(result.stdout or "{}")
    issues: list[Issue] = []
    for item in report.get("generalDiagnostics", []):
        if item["severity"] == "error":
            path = os.path.relpath(item["file"], ROOT)
            message = item["message"].split("\n")[0]
            issues.append((path, item["range"]["start"]["line"] + 1, "TYPE", message))
    return issues


def all_issues(files: list[str]) -> list[Issue]:
    issues = ruff_issues(files) + type_issues(files)
    for path in files:
        issues += short_names(path)
    return sorted(set(issues))


def counts(issues: list[Issue]) -> Counts:
    """{file: {code: count}}"""
    out: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for path, _, code, _ in issues:
        out[path][code] += 1
    return {path: dict(per_code) for path, per_code in out.items()}


def load_baseline() -> Counts:
    if not os.path.exists(BASELINE):
        return {}
    with open(BASELINE) as f:
        return json.load(f)


def worse(path: str, now: Counts, baseline: Counts) -> dict[str, tuple[int, int]]:
    """The codes whose count in this file went up: {code: (before, now)}."""
    before = baseline.get(path, {})
    went_up: dict[str, tuple[int, int]] = {}
    for code, count in now.get(path, {}).items():
        if count > before.get(code, 0):
            went_up[code] = (before.get(code, 0), count)
    return went_up


def show(issues: list[Issue]) -> None:
    for path, line, code, message in issues:
        print(f"{path}:{line}: {code} {message}")


def hook() -> int:
    """Claude Code PostToolUse: after an edit to a Python file, exit 2 (the issues go back to the assistant)
    if the file got less readable."""
    event = json.load(sys.stdin)
    path = event.get("tool_input", {}).get("file_path", "")
    if not path.endswith(".py"):
        return 0
    path = os.path.relpath(os.path.abspath(path), ROOT)
    if path.startswith("..") or set(path.split(os.sep)) & SKIP:
        return 0
    issues = all_issues([path])
    grew = worse(path, counts(issues), load_baseline())
    if not grew:
        return 0
    change = ", ".join(f"{code} {before} -> {now}" for code, (before, now) in grew.items())
    print(f"{path} is less readable than before ({change}).", file=sys.stderr)
    print("Fix the new ones (CLAUDE.md, 'Readable code'):", file=sys.stderr)
    for issue in [i for i in issues if i[2] in grew][:30]:
        print(f"  line {issue[1]}: {issue[2]} {issue[3]}", file=sys.stderr)
    return 2


def main() -> int:
    args = sys.argv[1:]
    if args == ["--hook"]:
        return hook()
    if args and args[0] != "--update":
        show(all_issues(args))
        return 0
    issues = all_issues(sorted(python_files()))
    now = counts(issues)
    if args == ["--update"]:
        with open(BASELINE, "w") as f:
            json.dump(now, f, indent=1, sort_keys=True)
        print(f"baseline saved: {len(issues)} issues in {len(now)} files")
        return 0
    baseline = load_baseline()
    got_worse = {path: worse(path, now, baseline) for path in now}
    got_worse = {path: grew for path, grew in got_worse.items() if grew}
    total = collections.Counter(code for _, _, code, _ in issues)
    summary = ", ".join(f"{code} {count}" for code, count in total.most_common())
    print(f"readability: {summary}  ({len(issues)} total)")
    for path, grew in got_worse.items():
        changes = ", ".join(f"{code} {before} -> {after}" for code, (before, after) in grew.items())
        print(f"  WORSE: {path}: {changes}")
    return 1 if got_worse else 0


if __name__ == "__main__":
    sys.exit(main())
