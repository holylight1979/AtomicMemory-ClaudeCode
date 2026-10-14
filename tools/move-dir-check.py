"""move-dir-check.py — 搬了程式目錄之後的兩張收據（規則 MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE，hooks/wg_release_rules.py）。

做什麼：
  scan    全庫找舊路徑字串（絕對、相對、正斜線、反斜線都算），印命中清單，尾行 `MOVE_PATH_SCAN DONE hits=<n>`。
          命中要修碼後重掃到 0；刻意保留的（例：變更記錄）用 --allow 排除，指令本身就是保留的紀錄。
  sample  --for 點名這次抽樣涵蓋哪個新目錄（收尾只替點名到的搬移清帳），跑你選的抽樣驗證（--run，例：Python 被搬模組的
          import 煙霧或目標 verify）；C# 加 --csproj-check <新目錄>，檢查裡面每個 .cs 都被某個 .csproj 編進去（SDK 型
          預設收專案目錄底下、或明列 Compile Include），有 .sln 時那個 .csproj 也要被 .sln 提到。全過尾行
          `MOVE_SAMPLE_CHECK PASS`，否則 `MOVE_SAMPLE_CHECK FAIL`（exit 1）。

怎麼跑（在專案根；不在專案根就加 --root <專案根>）：
  python ~/.claude/tools/move-dir-check.py scan --old lib/pkg --new src/pkg [--allow CHANGELOG.md]
  python ~/.claude/tools/move-dir-check.py sample --for src/pkg --run "python -c \"import src.pkg\"" [--csproj-check src/pkg]
完整參數看 --help。
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterator, List, Optional

SKIP_DIRS = {".git", ".svn", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", "bin", "obj", ".mypy_cache"}
MAX_BYTES = 2_000_000
SHOWN = 50


def _files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


def _text_of(p: Path) -> Optional[str]:
    try:
        if p.stat().st_size > MAX_BYTES:
            return None
        raw = p.read_bytes()
    except OSError as e:
        print(f"[move-dir-check] 讀不到 {p}：{e}", file=sys.stderr)
        return None
    if b"\x00" in raw[:8192]:
        return None
    return raw.decode("utf-8", errors="replace")


def _patterns(old: str, root: Path) -> List["re.Pattern[str]"]:
    """舊路徑的各種寫法：絕對路徑（兩種斜線）與相對專案根的路徑（兩種斜線）。後面不能接名字字元（lib/pkg2 不算）。"""
    p = Path(old)
    absolute = (p if p.is_absolute() else root / p).resolve()
    try:
        rel = absolute.relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = ""
    end = r"(?![\w.-])"
    win = str(absolute).replace("/", "\\")
    forms = {absolute.as_posix(), win, win.replace("\\", "\\\\")}             # 雙反斜線：JSON／程式字串裡跳脫過的寫法
    pats = [re.compile(re.escape(s) + end, re.IGNORECASE) for s in forms]
    if rel and "/" in rel:
        rel_forms = {rel, rel.replace("/", "\\"), rel.replace("/", "\\\\")}
        pats += [re.compile(r"(?<![\w.-])" + re.escape(s) + end, re.IGNORECASE) for s in rel_forms]
    elif rel:                                  # 頂層單一名字：只認後面接斜線、或整個被引號包住
        pats.append(re.compile(r"(?<![\w.-])" + re.escape(rel) + r"(?=[/\\])|(?<=[\"'])" + re.escape(rel) + r"(?=[\"'])",
                               re.IGNORECASE))
    return pats


def cmd_scan(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve()
    pats = _patterns(a.old, root)
    hits: List[str] = []
    for f in _files(root):
        rel = f.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(rel, g) for g in a.allow or []):
            continue
        text = _text_of(f)
        if text is None:
            continue
        for no, line in enumerate(text.splitlines(), 1):
            if any(p.search(line) for p in pats):
                hits.append(f"{rel}:{no}: {line.strip()[:160]}")
    for h in hits[:SHOWN]:
        print(h)
    if len(hits) > SHOWN:
        print(f"…另有 {len(hits) - SHOWN} 筆")
    print(f"MOVE_PATH_SCAN DONE hits={len(hits)}")
    return 0


_COMPILE_RE = re.compile(r"<Compile\s+(Include|Remove)\s*=\s*\"([^\"]+)\"", re.IGNORECASE)


def _compiled_by(proj: Path, cs: Path) -> bool:
    """這個 .cs 會不會被這個 .csproj 編進去：SDK 型專案（`<Project Sdk=`）沒關掉預設項目就收專案目錄底下全部 .cs；
    另外看明列的 `<Compile Include=…>`（相對專案目錄、可用 ** 與 *、可指到專案目錄外），`<Compile Remove=…>` 排除。"""
    text = _text_of(proj) or ""
    base = proj.parent.resolve()
    cs_posix = cs.resolve().as_posix().lower()

    def matches(pattern: str) -> bool:
        pat = os.path.normpath((base / pattern.replace("\\", "/")).as_posix()).replace("\\", "/").lower()
        # MSBuild 的 **/ 可以是零層目錄，fnmatch 的不行：兩種都試
        return fnmatch.fnmatch(cs_posix, pat) or fnmatch.fnmatch(cs_posix, pat.replace("/**/", "/"))

    items = _COMPILE_RE.findall(text)
    if any(kind.lower() == "remove" and matches(pat) for kind, pat in items):
        return False
    sdk_default = re.search(r"<Project\s[^>]*Sdk=", text, re.IGNORECASE) is not None and \
        re.search(r"<EnableDefaultCompileItems>\s*false", text, re.IGNORECASE) is None
    if sdk_default and base in cs.resolve().parents:
        return True
    return any(kind.lower() == "include" and matches(pat) for kind, pat in items)


def _csproj_check(new: str, root: Path) -> List[str]:
    """新目錄裡的每個 .cs 都要被某個 .csproj 編進去（_compiled_by）；有 .sln 時那個 .csproj 要被 .sln 提到。回問題清單。"""
    target = (Path(new) if Path(new).is_absolute() else root / new).resolve()
    projs = [p for p in _files(root) if p.suffix.lower() == ".csproj"]
    sources = [f for f in _files(target) if f.suffix.lower() == ".cs"]
    if not sources:
        return [f"{new} 底下沒有 .cs 檔，C# 囊括檢查無從判斷"]
    owners = [p for p in projs if all(_compiled_by(p, f) for f in sources)]
    if not owners:
        missed = next(f for f in sources if not any(_compiled_by(p, f) for p in projs))
        return [f"{missed.relative_to(root).as_posix()} 沒有被任何 .csproj 編進去（共找到 {len(projs)} 個 .csproj），搬過去就編不到"]
    slns = [p for p in _files(root) if p.suffix.lower() == ".sln"]
    if slns:
        names = {o.name.lower() for o in owners}
        texts = [(_text_of(s) or "").lower() for s in slns]
        if not any(n in t for t in texts for n in names):
            return [f"{'、'.join(sorted(names))} 沒有被 {len(slns)} 個 .sln 任何一個提到"]
    print(f"[csproj] {new} 在 {owners[0].relative_to(root).as_posix()} 底下")
    return []


def cmd_sample(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve()
    if not a.run and not a.csproj_check:
        print("sample 至少要一個 --run 或 --csproj-check", file=sys.stderr)
        print("MOVE_SAMPLE_CHECK FAIL")
        return 1
    problems: List[str] = []
    for t in a.targets:
        if not (Path(t) if Path(t).is_absolute() else root / t).is_dir():
            problems.append(f"--for {t} 不是存在的目錄")
    for c in a.run or []:
        r = subprocess.run(c, shell=True, cwd=str(root))
        print(f"[run] {c} → exit {r.returncode}")
        if r.returncode != 0:
            problems.append(f"{c} exit {r.returncode}")
    for d in a.csproj_check or []:
        problems += _csproj_check(d, root)
    for p in problems:
        print(f"[問題] {p}")
    print("MOVE_SAMPLE_CHECK " + ("FAIL" if problems else "PASS"))
    return 1 if problems else 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="全庫找舊路徑字串")
    s.add_argument("--old", required=True, help="搬之前的目錄（相對專案根或絕對）")
    s.add_argument("--new", required=True, help="搬之後的目錄（紀錄用）")
    s.add_argument("--allow", action="append", help="刻意保留的檔（相對專案根的 glob），可重複")
    s.add_argument("--root", default=".", help="專案根，預設目前目錄")
    s.set_defaults(fn=cmd_scan)
    p = sub.add_parser("sample", help="抽樣驗證搬過去的功能還正常")
    p.add_argument("--for", dest="targets", action="append", required=True,
                   help="這次抽樣涵蓋的新目錄（搬之後的路徑），可重複；收尾只替點名到的搬移清帳")
    p.add_argument("--run", action="append", help="要跑的驗證指令（exit 0 算過），可重複")
    p.add_argument("--csproj-check", action="append", help="C#：新目錄要在某個 .csproj 底下（有 .sln 時也要被 .sln 提到）")
    p.add_argument("--root", default=".", help="專案根，預設目前目錄")
    p.set_defaults(fn=cmd_sample)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
