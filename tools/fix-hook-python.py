"""fix-hook-python.py — 把 settings.json 內寫死的 Python 直譯器路徑校正成本機可用的一支。

為什麼需要：hook 指令必須指名一個直譯器，而 settings.json 進 git。
別台機器沿用原作者的絕對路徑 → 全部 hook 起不來（14 處指令一起死）。

為什麼不直接寫裸 `python`：PATH 上的 `python` 未必是你想要的那支
（實例：某機 PATH 首位是某 venv 的 3.11，而 hook 原本跑 3.14）。
無聲換直譯器不是修好，是換一種踩法。所以這裡走「明示校正 + 可驗證」：

  python tools/fix-hook-python.py            # 只檢查，印出現況與建議
  python tools/fix-hook-python.py --write    # 用「跑本腳本的這支 python」改寫
  python tools/fix-hook-python.py --write --use "D:/py/python.exe"

hook 全部只用標準函式庫，任何 CPython 3.9+ 皆可；本腳本會實際跑一次候選
直譯器驗證版本，不合格就拒絕寫入。原檔備份為 settings.json.bak。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

CLAUDE_DIR = Path(__file__).resolve().parent.parent
SETTINGS = CLAUDE_DIR / "settings.json"
MIN_VERSION = (3, 9)

# 指令開頭的直譯器（可帶引號、可為 Windows 絕對路徑或 POSIX 路徑或裸名）
_INTERP_RE = re.compile(
    r'^(?P<q>"?)(?P<path>[^"\s]*?(?P<name>pythonw?3?)(?P<ext>\.exe)?)(?P=q)(?=\s|$)'
)


def iter_command_slots(settings: dict):
    """yield (描述, getter, setter) 涵蓋所有帶指令的欄位。"""
    sl = settings.get("statusLine")
    if isinstance(sl, dict) and isinstance(sl.get("command"), str):
        yield ("statusLine", sl, "command")

    hooks = settings.get("hooks")
    if isinstance(hooks, dict):
        for event, matchers in hooks.items():
            if not isinstance(matchers, list):
                continue
            for mi, matcher in enumerate(matchers):
                entries = (matcher or {}).get("hooks")
                if not isinstance(entries, list):
                    continue
                for hi, entry in enumerate(entries):
                    if isinstance(entry, dict) and isinstance(entry.get("command"), str):
                        yield (f"hooks.{event}[{mi}][{hi}]", entry, "command")


def current_interpreters(settings: dict) -> List[Tuple[str, str]]:
    """回 [(欄位描述, 直譯器路徑)]，只取指令開頭那一段。"""
    found = []
    for desc, holder, key in iter_command_slots(settings):
        m = _INTERP_RE.match(holder[key].strip())
        if m:
            found.append((desc, m.group("path")))
    return found


def verify_interpreter(path: str) -> Tuple[bool, str]:
    """實跑候選直譯器確認版本，不靠檔名猜。"""
    try:
        out = subprocess.run(
            [path, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"無法執行：{type(e).__name__}: {e}"
    if out.returncode != 0:
        return False, f"exit={out.returncode} {out.stderr.strip()[:120]}"
    ver = (out.stdout or "").strip()
    try:
        parts = tuple(int(x) for x in ver.split("."))
    except ValueError:
        return False, f"版本輸出無法解析：{ver!r}"
    if parts < MIN_VERSION:
        return False, f"版本 {ver} 低於需求 {MIN_VERSION[0]}.{MIN_VERSION[1]}"
    return True, ver


def windowless_sibling(path: str) -> str:
    """給 pythonw 用的對應檔（Windows 無 console 版）；找不到就回原路徑。"""
    p = Path(path)
    if p.stem.endswith("w"):
        return str(p)
    cand = p.with_name(p.stem + "w" + p.suffix)
    return str(cand) if cand.is_file() else str(p)


def rewrite(settings: dict, new_interp: str) -> List[Tuple[str, str, str]]:
    """就地改寫所有指令開頭的直譯器。回 [(欄位, 舊, 新)]。"""
    changes = []
    win_variant = windowless_sibling(new_interp)
    for desc, holder, key in iter_command_slots(settings):
        cmd = holder[key]
        m = _INTERP_RE.match(cmd.strip())
        if not m:
            continue
        old = m.group("path")
        # 原本用 pythonw（不彈 console 視窗）→ 換成對應的 w 版，維持原意圖
        target = win_variant if m.group("name").endswith("w") else new_interp
        if old == target:
            continue
        quoted = f'"{target}"' if " " in target else target
        holder[key] = cmd.strip().replace(m.group(0), quoted, 1)
        changes.append((desc, old, target))
    return changes


def main() -> int:
    ap = argparse.ArgumentParser(description="校正 settings.json 的 Python 直譯器路徑")
    ap.add_argument("--write", action="store_true", help="實際改寫（預設只檢查）")
    ap.add_argument("--use", default="", help="指定直譯器；預設用跑本腳本的這支")
    args = ap.parse_args()

    if not SETTINGS.is_file():
        print(f"找不到 {SETTINGS}")
        return 1
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    print(f"settings.json：{SETTINGS}")
    broken = 0
    for desc, path in current_interpreters(settings):
        exists = Path(path).is_file() or shutil.which(path) is not None
        mark = "OK " if exists else "缺失"
        if not exists:
            broken += 1
        print(f"  [{mark}] {desc}: {path}")

    target = args.use or sys.executable
    ok, info = verify_interpreter(target)
    print(f"\n候選直譯器：{target}")
    print(f"  驗證：{'通過 Python ' + info if ok else '不合格 — ' + info}")
    if not ok:
        print("拒絕寫入。請用 --use 指定另一支可用的 Python。")
        return 2

    if broken == 0 and not args.use:
        print("\n現有路徑全部存在 → 無須改動（要強制改用他支請加 --use）。")
        return 0

    preview = json.loads(json.dumps(settings))  # deep copy，先算差異再決定寫不寫
    changes = rewrite(preview, target)
    if not changes:
        print("\n無可改動項。")
        return 0

    print(f"\n將改寫 {len(changes)} 處：")
    for desc, old, new in changes:
        print(f"  {desc}\n    - {old}\n    + {new}")

    if not args.write:
        print("\n（僅檢查模式。加 --write 實際寫入）")
        return 0

    backup = SETTINGS.with_suffix(".json.bak")
    shutil.copy2(SETTINGS, backup)
    SETTINGS.write_text(
        json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\n已寫入；原檔備份於 {backup}")
    print("重開 Claude Code session 後生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
