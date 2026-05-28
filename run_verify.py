#!/usr/bin/env python
"""統一 verify 入口 — scan source 同層 verify/ + skills/{name}/verify/"""
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
fixed = [
    ROOT / "hooks" / "verify",
    ROOT / "tools" / "verify",
    ROOT / "tools" / "codex-companion" / "verify",
    ROOT / "lib" / "verify",
]
skills = ROOT / "skills"
if skills.exists():
    fixed += [d / "verify" for d in skills.iterdir() if d.is_dir() and (d / "verify").exists()]

paths = [str(p) for p in fixed if p.exists()]
if not paths:
    print("No verify/ directories found.")
    sys.exit(0)

print("verify paths:")
for p in paths:
    print(f"  {p}")

result = subprocess.run([sys.executable, "-m", "pytest", *paths, "-v", "--tb=short"])
sys.exit(result.returncode)
