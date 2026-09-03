"""Execute Unity in batch mode and return exit code + log output.

Usage:
    python unity_batch.py --project "c:/Projects/sgi_client/client" --method "ClaudeEditorHelper.RefreshAssets"
    python unity_batch.py --project "c:/Projects/sgi_client/client" --method "ClaudeEditorHelper.DuplicatePrefab" --extra-args "-src Assets/Prefabs/a.prefab -dst Assets/Prefabs/b.prefab"
"""
import argparse
import subprocess
import sys
import os
import glob


def find_unity_exe():
    """Find Unity.exe from Hub default paths, registry, or PATH."""

    # 1. Unity Hub default install paths
    hub_base = os.path.expandvars(r"%ProgramFiles%\Unity\Hub\Editor")
    if os.path.isdir(hub_base):
        versions = sorted(os.listdir(hub_base), reverse=True)
        for ver in versions:
            exe = os.path.join(hub_base, ver, "Editor", "Unity.exe")
            if os.path.isfile(exe):
                return exe

    hub_base2 = r"C:\Program Files\Unity\Hub\Editor"
    if hub_base2 != hub_base and os.path.isdir(hub_base2):
        versions = sorted(os.listdir(hub_base2), reverse=True)
        for ver in versions:
            exe = os.path.join(hub_base2, ver, "Editor", "Unity.exe")
            if os.path.isfile(exe):
                return exe

    # 2. Windows Registry
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Unity Technologies\Installer\Unity")
        val, _ = winreg.QueryValueEx(key, "Location x64")
        winreg.CloseKey(key)
        exe = os.path.join(val, "Editor", "Unity.exe")
        if os.path.isfile(exe):
            return exe
    except (OSError, FileNotFoundError, ImportError):
        pass

    # 3. PATH
    import shutil
    path_exe = shutil.which("Unity.exe") or shutil.which("Unity")
    if path_exe:
        return path_exe

    return None


def read_project_unity_version(project_path):
    """Read Unity version from ProjectSettings/ProjectVersion.txt."""
    ver_file = os.path.join(project_path, "ProjectSettings", "ProjectVersion.txt")
    if os.path.isfile(ver_file):
        with open(ver_file, "r") as f:
            for line in f:
                if line.startswith("m_EditorVersion:"):
                    return line.split(":")[1].strip()
    return None


def find_unity_for_project(project_path):
    """Try to find the exact Unity version the project uses."""
    version = read_project_unity_version(project_path)
    if version:
        hub_base = os.path.expandvars(r"%ProgramFiles%\Unity\Hub\Editor")
        exe = os.path.join(hub_base, version, "Editor", "Unity.exe")
        if os.path.isfile(exe):
            return exe
        print(f"[WARN] Project uses Unity {version} but not found at {exe}", file=sys.stderr)
    return None


def main():
    parser = argparse.ArgumentParser(description="Run Unity in batch mode")
    parser.add_argument("--find-unity", action="store_true", help="Just find and print Unity.exe path")
    parser.add_argument("--project", "-p", default=None, help="Unity project path")
    parser.add_argument("--method", "-m", default=None, help="Static method to execute")
    parser.add_argument("--unity-path", type=str, default=None, help="Explicit path to Unity.exe")
    parser.add_argument("--logfile", type=str, default=None, help="Log file path (default: c:/tmp/unity_batch.log)")
    parser.add_argument("--extra-args", type=str, default="", help="Additional command line args")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds (default: 300)")
    args = parser.parse_args()

    # --find-unity mode: just locate and print
    if args.find_unity:
        exe = find_unity_exe()
        if exe:
            print(exe)
            sys.exit(0)
        else:
            print("NOT FOUND")
            sys.exit(1)

    # Normal batch mode requires --project and --method
    if not args.project or not args.method:
        parser.error("--project and --method are required (unless using --find-unity)")

    # Resolve Unity.exe
    unity_exe = args.unity_path
    if not unity_exe:
        unity_exe = find_unity_for_project(args.project)
    if not unity_exe:
        unity_exe = find_unity_exe()
    if not unity_exe:
        print("[ERROR] Cannot find Unity.exe. Use --unity-path to specify.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Unity: {unity_exe}", file=sys.stderr)

    logfile = args.logfile or "c:/tmp/unity_batch.log"
    os.makedirs(os.path.dirname(os.path.abspath(logfile)), exist_ok=True)

    # Build command
    cmd = [
        unity_exe,
        "-batchmode",
        "-quit",
        "-projectPath", os.path.abspath(args.project),
        "-executeMethod", args.method,
        "-logFile", logfile,
    ]
    if args.extra_args:
        cmd.extend(args.extra_args.split())

    print(f"[INFO] Command: {' '.join(cmd)}", file=sys.stderr)

    try:
        result = subprocess.run(cmd, timeout=args.timeout, capture_output=True, text=True)
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Unity timed out after {args.timeout}s", file=sys.stderr)
        exit_code = -1
    except Exception as e:
        print(f"[ERROR] Failed to run Unity: {e}", file=sys.stderr)
        sys.exit(1)

    # Read log
    if os.path.isfile(logfile):
        with open(logfile, "r", encoding="utf-8", errors="replace") as f:
            log_content = f.read()
        lines = log_content.splitlines()
        tail = lines[-100:] if len(lines) > 100 else lines
        print(f"\n--- Log tail ({len(tail)}/{len(lines)} lines) ---")
        for line in tail:
            print(line)
    else:
        print(f"[WARN] Log file not found: {logfile}", file=sys.stderr)

    print(f"\n[RESULT] Exit code: {exit_code}")
    sys.exit(0 if exit_code == 0 else 1)


if __name__ == "__main__":
    main()
