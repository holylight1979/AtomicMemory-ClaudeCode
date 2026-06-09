#!/usr/bin/env python
"""Run a bash hook script windowless on Windows.

settings.json invokes:  pythonw run-bash-hidden.py <script.sh> [args...]

Why this exists
---------------
`bash.exe` is a console-subsystem program. When the console-less `claude.exe`
spawns it directly, Windows allocates a visible console window each time — the
per-hook "閃 console" flash. There is no `bashw` (windowless bash), and simply
spawning bash with CREATE_NO_WINDOW breaks it: MSYS2 bash mishandles a
console-less *inherited native pipe* on stdin (`cat` errors → exit 1, no I/O —
proven by combo diagnostics B vs C/D).

Solution: run the launcher under `pythonw` (GUI-subsystem → never allocates a
console). Python reads our stdin itself (it handles native pipes fine), feeds
bash through a *managed* pipe via input=, captures bash's stdout/stderr,
re-emits them, and propagates the exit code. Bash is spawned with
CREATE_NO_WINDOW so it, too, gets no console. Net: zero console windows, hook
I/O contract preserved.

See atom `windows-cc-hook-閃-console-pythonw-修-layer-1…` for the full diagnosis.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW


def _resolve_bash():
    # The MSYS "real" bash handles our mediated pipes cleanly; the bin/ launcher
    # wrapper does not (diagnostic combo A failed even for a plain echo).
    for p in (r"C:\Program Files\Git\usr\bin\bash.exe",
              r"C:\Program Files\Git\bin\bash.exe"):
        if os.path.exists(p):
            return p
    return shutil.which("bash") or "bash"


def main():
    if len(sys.argv) < 2:
        return 0  # nothing to run; fail-open, never wedge the session
    # basename guard: callers pass a bare script name, no path traversal
    name = os.path.basename(sys.argv[1])
    script = HOOKS_DIR / name
    if not script.is_file():
        sys.stderr.write(f"[run-bash-hidden] script not found: {name}\n")
        return 0  # fail-open

    data = b""
    try:
        if sys.stdin is not None:
            data = sys.stdin.buffer.read()
    except Exception:
        data = b""

    try:
        r = subprocess.run(
            [_resolve_bash(), str(script), *sys.argv[2:]],
            input=data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=NO_WINDOW,
        )
    except Exception as e:  # infra failure (bash missing etc.) — fail-open
        sys.stderr.write(f"[run-bash-hidden] {e}\n")
        return 0

    if r.stdout:
        sys.stdout.buffer.write(r.stdout)
        sys.stdout.buffer.flush()
    if r.stderr:
        sys.stderr.buffer.write(r.stderr)
        sys.stderr.buffer.flush()
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
