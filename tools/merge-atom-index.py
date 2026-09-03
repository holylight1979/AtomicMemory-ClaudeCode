#!/usr/bin/env python3
"""merge-atom-index.py — 記憶索引三檔的 git 合併驅動（多機共享記憶庫用）

問題：兩台機器各自新增 atom 後 rebase/merge，atom 本體（各自新檔）不衝突，但索引三檔
（MEMORY.md 範疇計數表 / _ATOM_INDEX.md 表列 / _atom_index.json）都在同一區塊各加一列，
git 逐行三方合併必衝突。另一種整檔衝突：兩側行尾不同（一側 CRLF）→ 每行都算改過 → 整檔衝突；
repo 全部 LF（.gitattributes eol=lf + lib 寫檔一律 LF）之後這型不再發生。

解法：
  1. 語意三方合併——索引是「一列一 atom」的集合，不是文章：
     - _atom_index.json：以 path 為 key 逐條合併。單側改取單側；兩側都改逐欄位合、triggers 取聯集；
       一側刪一側改 → 留改的那側（不丟資料，懸空條目交 sync-atom-index --fix-scope-from-path 清）
     - _ATOM_INDEX.md：表列同上（key=Path 欄），表頭取 ours
     - MEMORY.md：「| 範疇 | atom 數 | 深入 |」表的計數 = ours + theirs − base（各自新增互不知情，差量可加）；
       表以外的人寫文字仍走 git merge-file 逐行三方，真衝突照留 <<<<<<< 標記並 exit 1
  2. 行尾：驅動一律輸出 LF，與 repo 的 LF 規則一致。

為什麼不「合併時從磁碟重建索引」：merge driver 執行當下，工作樹只有「目前 HEAD 那側」的 atom 檔
（merge 時缺 theirs 新檔、rebase 時缺自己的新檔；tools/verify/verify_merge_atom_index.py 有實測），
重建會把另一側的 atom 從索引弄丟。三份 blob 已含全部資訊，不必碰磁碟。

git 呼叫（--install 會寫進 global git config）：
  python merge-atom-index.py <base> <ours> <theirs> [<path>]   結果寫回 <ours>；exit 0 乾淨、1 仍有衝突
人工：
  python merge-atom-index.py --install   各機一次：寫 global git config 的 merge.atomindex + 全域 attributes
  python merge-atom-index.py --status    檢查本機是否已裝、直譯器是否還在（exit 1 = 未裝/失效）
根層 repo（~/.claude）自帶 .gitattributes 指到同一驅動；專案 repo 靠全域 attributes 覆蓋 **/.claude/memory/。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPT = Path(__file__).resolve()
DRIVER_NAME = "atomindex"
INDEX_FILES = ("MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json")
ATTR_MARK = "# AtomicMemory index merge driver"
ATTR_LINES = [f"**/.claude/memory/{n} merge={DRIVER_NAME} text eol=lf" for n in INDEX_FILES]
PLACEHOLDER = "@@ATOM-CATALOG-TABLE-PLACEHOLDER@@"  # 純文字：含 NUL 會被 git merge-file 當 binary 拒合
CATALOG_HEADER_RE = re.compile(r"^\|\s*範疇\s*\|")
ATOM_TABLE_HEADER_RE = re.compile(r"^\|\s*Atom\s*\|\s*Path\s*\|", re.I)
TABLE_SEP_RE = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")
_NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}
_MISSING = object()


# ─── 檔案 I/O（全部正規化成 LF 的 str） ─────────────────────────────────────

def _read(path: str) -> str:
    text = Path(path).read_bytes().decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _write(path: str, text: str) -> None:
    Path(path).write_bytes(text.encode("utf-8"))


def _split_cells(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _join_cells(cells: List[str]) -> str:
    return "| " + " | ".join(cells) + " |"


# ─── 通用三方規則 ───────────────────────────────────────────────────────────

def merge_scalar(b: Any, o: Any, t: Any) -> Any:
    """單一值三方：兩側同 → 取；單側改 → 取改的；兩側異改 → 取 ours。"""
    if o == t:
        return o
    if o == b:
        return t
    return o


def merge_keyed(base: Dict, ours: Dict, theirs: Dict, merge_both) -> Tuple[List[Tuple[Any, Any]], Dict[str, int]]:
    """以 key 逐條三方合併。順序 = ours 順序 + theirs 新增。

    單側改（含新增/刪除）取單側；兩側同 → 取；兩側異改 → merge_both(b,o,t)；
    一側刪一側改 → 留改的那側（不丟資料）。回 ([(key, value)...], 統計)。
    """
    order = list(ours) + [k for k in theirs if k not in ours]
    out: List[Tuple[Any, Any]] = []
    st = {"ours_add": 0, "theirs_add": 0, "deleted": 0, "both": 0}
    for k in order:
        b, o, t = base.get(k, _MISSING), ours.get(k, _MISSING), theirs.get(k, _MISSING)
        if o == t:
            v = o
        elif o == b:
            v = t
        elif t == b:
            v = o
        elif o is _MISSING:
            v = t
        elif t is _MISSING:
            v = o
        else:
            v = merge_both(b, o, t)
            st["both"] += 1
        if v is _MISSING:
            st["deleted"] += 1
            continue
        if b is _MISSING:
            if t is _MISSING:
                st["ours_add"] += 1
            elif o is _MISSING:
                st["theirs_add"] += 1
        out.append((k, v))
    return out, st


def merge_trigger_lists(b: Any, o: List[str], t: List[str]) -> List[str]:
    """triggers 兩側異改：任一側刪掉的不回來，兩側新增的都留，順序 ours 優先。"""
    bl = b if isinstance(b, list) else []
    removed = {x for x in bl if x not in o or x not in t}
    merged = [x for x in o if x not in removed] + [x for x in t if x not in o and x not in removed]
    seen: set = set()
    return [x for x in merged if not (x in seen or seen.add(x))]


def _fmt_stats(before: int, after: int, st: Dict[str, int]) -> str:
    return (f"{before}→{after} 條（ours +{st['ours_add']}, theirs +{st['theirs_add']}, "
            f"刪 {st['deleted']}, 兩側同改 {st['both']}）")


def textual_merge(base: str, ours: str, theirs: str) -> Tuple[str, int]:
    """git merge-file 逐行三方（＝沒裝驅動時 git 的做法）。回 (結果, 衝突數)。"""
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, text in (("ours", ours), ("base", base), ("theirs", theirs)):
            p = Path(d, name)
            p.write_bytes(text.encode("utf-8"))
            paths.append(str(p))
        r = subprocess.run(["git", "merge-file", "-p", "-L", "ours", "-L", "base", "-L", "theirs", *paths],
                           capture_output=True, **_NO_WINDOW)
    out = r.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
    return out, (0 if r.returncode == 0 else max(1, r.returncode))


# ─── _atom_index.json ──────────────────────────────────────────────────────

def _load_index(text: str) -> Dict[str, Any]:
    if not text.strip():
        return {"version": "1.0", "atoms": []}
    d = json.loads(text)
    if not isinstance(d, dict) or not isinstance(d.get("atoms"), list):
        raise ValueError("not an atom index (need dict with atoms list)")
    return d


def _by_path(d: Dict[str, Any]) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    for i, a in enumerate(d["atoms"]):
        key = a.get("path") if isinstance(a, dict) else None
        out[key or f"#{i}"] = a
    return out


def merge_entry(b: Any, o: Dict, t: Dict) -> Dict:
    """同一 atom 兩側都改：逐欄位三方，triggers 取聯集。"""
    b = b if isinstance(b, dict) else {}
    out: Dict[str, Any] = {}
    for f in list(o) + [k for k in t if k not in o]:
        bv, ov, tv = b.get(f, _MISSING), o.get(f, _MISSING), t.get(f, _MISSING)
        if (f == "triggers" and isinstance(ov, list) and isinstance(tv, list)
                and ov != tv and ov != bv and tv != bv):
            v = merge_trigger_lists(bv, ov, tv)
        else:
            v = merge_scalar(bv, ov, tv)
        if v is not _MISSING:
            out[f] = v
    return out


def merge_json(base_t: str, ours_t: str, theirs_t: str) -> Tuple[str, str]:
    b, o, t = _load_index(base_t), _load_index(ours_t), _load_index(theirs_t)
    merged, st = merge_keyed(_by_path(b), _by_path(o), _by_path(t), merge_entry)
    out: Dict[str, Any] = {}
    keys = list(o) + [k for k in t if k not in o]
    if "atoms" not in keys:
        keys.append("atoms")
    for k in keys:
        if k == "atoms":
            out[k] = [v for _, v in merged]
            continue
        v = merge_scalar(b.get(k, _MISSING), o.get(k, _MISSING), t.get(k, _MISSING))
        if v is not _MISSING:
            out[k] = v
    # 與 lib.atom_index_json.save_atom_index_json 同格式（indent=2、不轉 ASCII、無尾換行）
    text = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=False)
    if ours_t.endswith("\n"):
        text += "\n"
    return text, _fmt_stats(len(b["atoms"]), len(out["atoms"]), st)


# ─── _ATOM_INDEX.md ────────────────────────────────────────────────────────

def _parse_atom_table(text: str) -> Tuple[List[str], Dict[str, List[str]]]:
    """回 (表頭前所有行含表頭/分隔線, {Path: cells})。表後尾行忽略（重組時補單一尾換行）。"""
    head: List[str] = []
    rows: Dict[str, List[str]] = {}
    for ln in text.split("\n"):
        if ln.startswith("|") and not ATOM_TABLE_HEADER_RE.match(ln) and not TABLE_SEP_RE.match(ln):
            cells = _split_cells(ln)
            rows[cells[1] if len(cells) > 1 else ln] = cells
        elif not rows:
            head.append(ln)
    return head, rows


def merge_cells_row(b: Any, o: List[str], t: List[str], trigger_col: Optional[int] = 2) -> List[str]:
    b = b if isinstance(b, list) else []
    n = max(len(o), len(t))
    out: List[str] = []
    for i in range(n):
        bv = b[i] if i < len(b) else _MISSING
        ov = o[i] if i < len(o) else _MISSING
        tv = t[i] if i < len(t) else _MISSING
        if i == trigger_col and ov is not _MISSING and tv is not _MISSING and ov != tv and ov != bv and tv != bv:
            split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
            v = ", ".join(merge_trigger_lists(split(bv) if bv is not _MISSING else [], split(ov), split(tv)))
        else:
            v = merge_scalar(bv, ov, tv)
        out.append("" if v is _MISSING else v)
    return out


def merge_atom_index_md(base_t: str, ours_t: str, theirs_t: str) -> Tuple[str, str]:
    bh, br = _parse_atom_table(base_t)
    oh, orw = _parse_atom_table(ours_t)
    th, trw = _parse_atom_table(theirs_t)
    merged, st = merge_keyed(br, orw, trw, merge_cells_row)
    head = merge_scalar(bh, oh, th)
    lines = list(head) + [_join_cells(cells) for _, cells in merged] + [""]
    return "\n".join(lines), _fmt_stats(len(br), len(merged), st)


# ─── MEMORY.md ─────────────────────────────────────────────────────────────

def _extract_catalog(text: str):
    """找「| 範疇 |」表；回 (骨架行[表換成 PLACEHOLDER], 表頭兩行, {範疇: cells})，找不到 → (None, None, None)。"""
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if CATALOG_HEADER_RE.match(ln) and i + 1 < len(lines) and TABLE_SEP_RE.match(lines[i + 1]):
            j = i + 2
            rows: Dict[str, List[str]] = {}
            while j < len(lines) and lines[j].startswith("|"):
                cells = _split_cells(lines[j])
                rows[cells[0]] = cells
                j += 1
            return lines[:i] + [PLACEHOLDER] + lines[j:], lines[i:i + 2], rows
    return None, None, None


def _count(cells: Optional[List[str]]) -> Optional[int]:
    if cells is None:
        return 0  # 該側沒這列 = 0 顆
    if len(cells) > 1 and cells[1].isdigit():
        return int(cells[1])
    return None  # 非數字計數欄，走通用規則


def merge_catalog_rows(br: Dict, orw: Dict, trw: Dict) -> Tuple[List[List[str]], str]:
    """計數 = ours + theirs − base（缺列當 0）；≤0 的列移除；其餘欄位走通用規則。"""
    out: List[List[str]] = []
    keys = list(orw) + [k for k in trw if k not in orw]
    summed = 0
    for k in keys:
        b, o, t = br.get(k), orw.get(k), trw.get(k)
        bc, oc, tc = _count(b), _count(o), _count(t)
        if None in (bc, oc, tc):
            v = merge_keyed({k: b} if b else {}, {k: o} if o else {}, {k: t} if t else {},
                            lambda bb, oo, tt: merge_cells_row(bb, oo, tt, trigger_col=None))[0]
            if v:
                out.append(v[0][1])
            continue
        n = oc + tc - bc
        if n <= 0:
            continue
        cells = merge_cells_row(b, o or t, t or o, trigger_col=None)
        cells[1] = str(n)
        if oc != tc or bc != oc:
            summed += 1
        out.append(cells)
    return out, f"{len(out)} 範疇列（{summed} 列計數以差量相加）"


def merge_memory_md(base_t: str, ours_t: str, theirs_t: str) -> Tuple[str, int, str]:
    os_, ohd, orw = _extract_catalog(ours_t)
    ts_, thd, trw = _extract_catalog(theirs_t)
    if os_ is None or ts_ is None:
        text, n = textual_merge(base_t, ours_t, theirs_t)
        return text, n, "無範疇表，逐行三方"
    bs_, bhd, br = _extract_catalog(base_t)
    if bs_ is None:
        bs_, bhd, br = base_t.split("\n"), ohd, {}
    skel, n = textual_merge("\n".join(bs_), "\n".join(os_), "\n".join(ts_))
    if n or skel.count(PLACEHOLDER) != 1:
        text, n = textual_merge(base_t, ours_t, theirs_t)
        return text, max(n, 1), "範疇表以外的文字真衝突，留標記"
    rows, summary = merge_catalog_rows(br, orw, trw)
    table = "\n".join(list(merge_scalar(bhd, ohd, thd)) + [_join_cells(c) for c in rows])
    return skel.replace(PLACEHOLDER, table), 0, summary


# ─── 驅動入口 ──────────────────────────────────────────────────────────────

def detect_kind(path_hint: str, *texts: str) -> str:
    name = Path(path_hint).name if path_hint and path_hint != "%P" else ""
    if name in INDEX_FILES:
        return name
    for t in texts:
        if t.lstrip().startswith("{"):
            return "_atom_index.json"
        if re.search(ATOM_TABLE_HEADER_RE.pattern, t, re.I | re.M):
            return "_ATOM_INDEX.md"
        if re.search(CATALOG_HEADER_RE.pattern, t, re.M):
            return "MEMORY.md"
    return ""


def run_driver(base_p: str, ours_p: str, theirs_p: str, path_hint: str = "") -> int:
    base, ours, theirs = _read(base_p), _read(ours_p), _read(theirs_p)
    kind = detect_kind(path_hint, ours, theirs, base)
    label = path_hint if path_hint and path_hint != "%P" else (kind or ours_p)
    conflicts = 0
    try:
        if kind == "_atom_index.json":
            text, summary = merge_json(base, ours, theirs)
        elif kind == "_ATOM_INDEX.md":
            text, summary = merge_atom_index_md(base, ours, theirs)
        elif kind == "MEMORY.md":
            text, conflicts, summary = merge_memory_md(base, ours, theirs)
        else:
            text, conflicts = textual_merge(base, ours, theirs)
            summary = "非索引檔，逐行三方"
    except Exception as e:  # 語意合併失敗 → 退回 git 逐行三方（＝沒裝驅動的結果），但要浮出訊號
        text, conflicts = textual_merge(base, ours, theirs)
        summary = f"語意合併失敗（{type(e).__name__}: {e}），退回逐行三方"
        if kind == "_atom_index.json" and not conflicts:
            try:
                json.loads(text)
            except ValueError:
                conflicts = 1  # 逐行拼出來的不是合法 JSON，寧可留給人看
    _write(ours_p, text)
    tail = f" → 仍有 {conflicts} 處衝突，留標記交人處理" if conflicts else ""
    print(f"[merge-atom-index] {label}: {summary}{tail}", file=sys.stderr)
    return 1 if conflicts else 0


# ─── 安裝 / 狀態 ───────────────────────────────────────────────────────────

def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **_NO_WINDOW)


def _fwd(p: Path) -> str:
    return str(p).replace("\\", "/")


def _interpreter() -> Path:
    """寫進 git config 的直譯器：在 venv 裡跑 --install 時取底層真 Python（venv 刪了驅動不跟著失效）。"""
    if sys.prefix != sys.base_prefix:
        base = getattr(sys, "_base_executable", None)
        if base and Path(base).exists():
            return Path(base)
    return Path(sys.executable)


def driver_command() -> str:
    return f'"{_fwd(_interpreter())}" "{_fwd(SCRIPT)}" %O %A %B %P'


def attributes_file() -> Tuple[Path, bool]:
    """回 (全域 attributes 檔路徑, core.attributesFile 是否已設)。未設 → git 預設位置。"""
    v = _git("config", "--global", "core.attributesFile").stdout.strip()
    if v:
        return Path(os.path.expanduser(v)), True
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "git" / "attributes", False


def _attr_block() -> str:
    return "\n".join([f"{ATTR_MARK}（python ~/.claude/tools/merge-atom-index.py --install 寫入；重跑會整段換新）",
                      *ATTR_LINES]) + "\n"


def install() -> int:
    r1 = _git("config", "--global", f"merge.{DRIVER_NAME}.name", "AtomicMemory 索引三檔語意三方合併")
    r2 = _git("config", "--global", f"merge.{DRIVER_NAME}.driver", driver_command())
    if r1.returncode or r2.returncode:
        print(f"[merge-atom-index] git config 失敗：{(r1.stderr or r2.stderr).strip()}", file=sys.stderr)
        return 1
    attr, was_set = attributes_file()
    attr.parent.mkdir(parents=True, exist_ok=True)
    cur = attr.read_text(encoding="utf-8") if attr.exists() else ""
    if ATTR_MARK in cur:
        head, _, rest = cur.partition(ATTR_MARK)
        rest_lines = rest.split("\n")[1:]
        while rest_lines and rest_lines[0].startswith("**/.claude/memory/"):
            rest_lines.pop(0)
        cur = head + "\n".join(rest_lines)
    cur = cur.rstrip("\n")
    new = (cur + "\n\n" if cur else "") + _attr_block()
    attr.write_text(new, encoding="utf-8", newline="\n")
    if not was_set:
        _git("config", "--global", "core.attributesFile", _fwd(attr))
    print(f"[merge-atom-index] 已安裝：merge.{DRIVER_NAME}.driver = {driver_command()}")
    print(f"[merge-atom-index] attributes：{attr}（{len(ATTR_LINES)} 條 **/.claude/memory/* 規則）")
    return 0


def status() -> int:
    ok = True
    drv = _git("config", "--global", f"merge.{DRIVER_NAME}.driver").stdout.strip()
    print(f"merge.{DRIVER_NAME}.driver = {drv or '(未設)'}")
    if not drv:
        ok = False
    else:
        parts = re.findall(r'"([^"]+)"', drv)
        for p in parts[:2]:
            exists = Path(p).exists()
            print(f"  {'OK ' if exists else 'ERR'} {p}")
            ok = ok and exists
    attr, was_set = attributes_file()
    has = attr.exists() and ATTR_MARK in attr.read_text(encoding="utf-8", errors="replace")
    print(f"attributes = {attr}（core.attributesFile {'已設' if was_set else '未設，用 git 預設位置'}）"
          f" → {'含' if has else '缺'}索引三檔規則")
    ok = ok and has
    chk = _git("check-attr", "merge", "text", "eol", "--", ".claude/memory/_atom_index.json", "memory/_atom_index.json")
    if chk.returncode == 0:
        print("check-attr（目前 repo）:\n  " + chk.stdout.strip().replace("\n", "\n  "))
    print("狀態：" + ("已安裝" if ok else "未安裝或失效 → python tools/merge-atom-index.py --install"))
    return 0 if ok else 1


def main(argv: List[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if "--install" in argv:
        return install()
    if "--status" in argv:
        return status()
    if len(argv) < 3:
        print(__doc__)
        return 2
    return run_driver(argv[0], argv[1], argv[2], argv[3] if len(argv) > 3 else "")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
