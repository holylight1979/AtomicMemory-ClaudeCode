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
     - 根層衍生索引檔（各層 _INDEX.md、_local_catalog.md；同樣由 sync-memory-index 產生）：通用表格文件三方——
       每張表以表頭為鍵，列表以第 0 欄為鍵聯集、計數表 o+t−b，骨架文字逐行三方（根層 .gitattributes 綁定）
  2. 行尾：驅動一律輸出 LF，與 repo 的 LF 規則一致。

為什麼不「合併時從磁碟重建索引」：merge driver 執行當下，工作樹只有「目前 HEAD 那側」的 atom 檔
（merge 時缺 theirs 新檔、rebase 時缺自己的新檔；tools/verify/verify_merge_atom_index.py 有實測），
重建會把另一側的 atom 從索引弄丟。三份 blob 已含全部資訊，不必碰磁碟。

git 呼叫（--install 寫進 global git config）：
  python merge-atom-index.py <base> <ours> <theirs> [<path>]   結果寫回 <ours>；exit 0 乾淨、1 仍有衝突
人工／hook 呼叫：
  --install [--quiet]          各機一次：寫全域 attributes + global git config 的 merge.atomindex（先 attributes 後 config，
                               config 存在即代表整套裝好）。--quiet 時 stdout 單行 JSON {"installed":bool,...}。
                               PreToolUse hook 在第一次合併類 git 指令前會自動跑，通常不必手動。
  --is-installed [--cwd <dir>] exit 0＝完整有效（driver 設定＋直譯器與腳本存在＋attributes 標記＋該 repo check-attr）。
  --status [--cwd <dir>]       人讀狀態；exit 1＝未裝/失效。
  --resolve [--cwd <dir>] [--quiet]
      備案：git 已停在衝突時（驅動沒裝、或 Fork 等 CC 以外的 pull），把同一套語意合併套在 index 的三個 stage
      （:1 base／:2 HEAD／:3 對方）上，寫回工作樹並 git add。只碰 check-attr merge=atomindex 且位於 memory/
      或 .claude/memory/ 的三檔；只在工作樹仍等於 git 原始衝突輸出（或驅動上一輪輸出）時覆蓋，人解到一半不碰；
      工作樹已無標記且格式合法 → 直接 stage 使用者版本；缺 :2/:3（一側刪檔）→ skipped；手寫段兩側同改 →
      寫回含標記結果、不 add、列 remaining。stdout 單行 JSON
      {"resolved":[],"staged_user_version":[],"skipped":[{"path","reason"}],"remaining":[],"installed":bool,"error":null}
      exit 0＝三檔已無 unmerged stage。順手 --install。
      stage 方向：merge 時 :2＝自己、:3＝對方；rebase／cherry-pick 時 :2＝upstream、:3＝正在重放的自己的 commit。
      SVN 工作副本（cwd 最近的 VCS 根是 .svn）：update 停在索引三檔衝突後，拿 svn 留下的 X.mine（ours）／
      X.r舊（base）／X.r新（theirs；路徑取自 svn info --xml）跑同一套驅動，寫回並 svn resolve --accept working；
      仍含 <<<<<<< 標記就當未動過；只掃 memory dir 候選不掃整個 WC；JSON 契約同 git。PreToolUse 在
      svn commit／resolve 前自動跑。
根層 repo（~/.claude）自帶 .gitattributes 指到同一驅動；專案 repo 靠全域 attributes 覆蓋 **/.claude/memory/。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
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


def textual_merge(base: str, ours: str, theirs: str, style: str = "") -> Tuple[str, int]:
    """git merge-file 逐行三方（＝沒裝驅動時 git 的做法）。回 (結果, 衝突數)。style 可為 --diff3／--zdiff3。"""
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, text in (("ours", ours), ("base", base), ("theirs", theirs)):
            p = Path(d, name)
            p.write_bytes(text.encode("utf-8"))
            paths.append(str(p))
        cmd = ["git", "merge-file", "-p"] + ([style] if style else []) + ["-L", "ours", "-L", "base", "-L", "theirs", *paths]
        r = subprocess.run(cmd, capture_output=True, timeout=10, **_NO_WINDOW)
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


# ─── 根層衍生索引檔：各層 _INDEX.md／_local_catalog.md（通用「表格文件」三方）──────────
#
# sync-memory-index --write 產生：`| Atom | 說明 |` 列表（鍵＝第 0 欄）與 `| 子層 | atom 數 | 深入 |`／
# `| 範疇根 | atom 數 | 深入 |` 計數表（第 1 欄全數字 → o+t−b）。兩人同範疇各加一顆 atom 就在同區塊各多一列。
# 做法同 MEMORY.md：表格以表頭為鍵換成佔位符，骨架（標題／註解）走 git merge-file；一側才有的表（第一個子層
# 出現時多出的「## 子層」段）跟著骨架單側插入。骨架真衝突 → 整檔逐行、留標記。

TABLE_DOC_FILES = ("_INDEX.md", "_local_catalog.md")
RESOLVE_FILES = INDEX_FILES + TABLE_DOC_FILES
TABLE_PH = "@@ATOM-TABLE:{}@@"
TABLE_PH_RE = re.compile(r"@@ATOM-TABLE:(.*?)@@")
TABLE_DOC_HEADER_RE = re.compile(r"^\|\s*(Atom|子層|範疇根)\s*\|", re.M)


def _split_tables(text: str):
    """回 (骨架行[每張表換成佔位符], {表頭鍵: (表頭兩行, {第0欄: cells})})。"""
    lines = text.split("\n")
    skel: List[str] = []
    tables: Dict[str, Tuple[List[str], Dict[str, List[str]]]] = {}
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not (ln.startswith("|") and i + 1 < len(lines) and TABLE_SEP_RE.match(lines[i + 1])):
            skel.append(ln)
            i += 1
            continue
        key = "|".join(_split_cells(ln))
        rows: Dict[str, List[str]] = {}
        j = i + 2
        while j < len(lines) and lines[j].startswith("|"):
            cells = _split_cells(lines[j])
            rows[cells[0] if cells else lines[j]] = cells
            j += 1
        tables[key] = ([ln, lines[i + 1]], rows)
        skel.append(TABLE_PH.format(key))
        i = j
    return skel, tables


def _is_count_table(*row_dicts: Dict[str, List[str]]) -> bool:
    seen = False
    for rd in row_dicts:
        for cells in rd.values():
            seen = True
            if len(cells) < 2 or not cells[1].isdigit():
                return False
    return seen


def _merge_one_table(bt, ot, tt) -> Tuple[List[str], str]:
    bh, br = bt if bt else (None, {})
    oh, orw = ot if ot else (None, {})
    th, trw = tt if tt else (None, {})
    head = merge_scalar(bh, oh, th) or oh or th
    if _is_count_table(br, orw, trw):
        rows, st = merge_catalog_rows(br, orw, trw)
        return list(head) + [_join_cells(c) for c in rows], st
    merged, stt = merge_keyed(br, orw, trw, lambda b, o, t: merge_cells_row(b, o, t, trigger_col=None))
    return list(head) + [_join_cells(c) for _, c in merged], _fmt_stats(len(br), len(merged), stt)


def merge_table_doc(base_t: str, ours_t: str, theirs_t: str) -> Tuple[str, int, str]:
    bs, bt = _split_tables(base_t)
    os_, ot = _split_tables(ours_t)
    ts, tt = _split_tables(theirs_t)
    if not ot and not tt:
        text, n = textual_merge(base_t, ours_t, theirs_t)
        return text, n, "無表格，逐行三方"
    skel, n = textual_merge("\n".join(bs), "\n".join(os_), "\n".join(ts))
    keys = TABLE_PH_RE.findall(skel)
    if n or len(keys) != len(set(keys)) or any(k not in ot and k not in tt for k in keys):
        text, n = textual_merge(base_t, ours_t, theirs_t)
        return text, max(n, 1), "表格以外的文字真衝突，留標記"
    parts = []
    for k in keys:
        lines, st = _merge_one_table(bt.get(k), ot.get(k), tt.get(k))
        skel = skel.replace(TABLE_PH.format(k), "\n".join(lines), 1)
        parts.append(f"{k.split('|')[0]}表 {st}")
    return skel, 0, "；".join(parts)


# ─── 驅動入口 ──────────────────────────────────────────────────────────────

def detect_kind(path_hint: str, *texts: str) -> str:
    name = Path(path_hint).name if path_hint and path_hint != "%P" else ""
    if name in RESOLVE_FILES:
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
        elif kind in TABLE_DOC_FILES:
            text, conflicts, summary = merge_table_doc(base, ours, theirs)
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


# ─── 共用：子行程／輸出（pythonw 下 stdout/stderr 可能是 None）────────────────

def _out(msg: str) -> None:
    try:
        if sys.stdout:
            sys.stdout.write(msg + "\n")
            sys.stdout.flush()
    except Exception:
        pass


def _say(msg: str, quiet: bool = False) -> None:
    if quiet:
        return
    try:
        if sys.stderr:
            sys.stderr.write(msg + "\n")
    except Exception:
        pass


def _git(*args: str, cwd: Optional[Path] = None, timeout: float = 5.0) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=str(cwd) if cwd else None, timeout=timeout, **_NO_WINDOW)


def _git_bytes(*args: str, cwd: Optional[Path] = None, timeout: float = 5.0) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, cwd=str(cwd) if cwd else None, timeout=timeout,
                          **_NO_WINDOW)


def _fwd(p: Path) -> str:
    return str(p).replace("\\", "/")


# ─── 安裝 / 狀態 ───────────────────────────────────────────────────────────

def _interpreter() -> Path:
    """寫進 git config 的直譯器：venv 裡取底層真 Python（venv 刪了驅動不跟著失效）；
    pythonw.exe（hook 環境）換同目錄 python.exe（pythonw 沒有 stdout/stderr，驅動診斷會消失）。"""
    exe = Path(sys.executable)
    if sys.prefix != sys.base_prefix:
        base = getattr(sys, "_base_executable", None)
        if base and Path(base).exists():
            exe = Path(base)
    if exe.name.lower() == "pythonw.exe":
        cand = exe.with_name("python.exe")
        if cand.exists():
            exe = cand
    return exe


def driver_command() -> str:
    return f'"{_fwd(_interpreter())}" "{_fwd(SCRIPT)}" %O %A %B %P'


def attributes_file() -> Tuple[Path, bool]:
    """回 (全域 attributes 檔路徑, core.attributesFile 是否已設)。未設 → git 預設位置。
    已設但是相對路徑 → 對 home 解析（git 自己是對執行目錄解析，安裝時一律改寫成絕對路徑）。"""
    v = _git("config", "--global", "core.attributesFile").stdout.strip()
    if v:
        p = Path(os.path.expanduser(v))
        return (p if p.is_absolute() else Path.home() / p), True
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "git" / "attributes", False


def _attr_block() -> str:
    return "\n".join([f"{ATTR_MARK}（python ~/.claude/tools/merge-atom-index.py --install 寫入；重跑會整段換新）",
                      *ATTR_LINES]) + "\n"


def _driver_paths(drv: str) -> List[str]:
    return re.findall(r'"([^"]+)"', drv)[:2]


def is_installed(cwd: Optional[Path] = None) -> bool:
    """完整有效狀態：global driver 設定存在、引號內直譯器與腳本都在、attributes 標記在、
    （若 cwd 是 repo）該 repo 的 check-attr merge 為 atomindex。任一不成立就算沒裝。"""
    try:
        drv = _git("config", "--global", "--get", f"merge.{DRIVER_NAME}.driver").stdout.strip()
        if not drv:
            return False
        paths = _driver_paths(drv)
        if len(paths) < 2 or not all(Path(p).exists() for p in paths):
            return False
        attr, _ = attributes_file()
        if not attr.exists() or ATTR_MARK not in attr.read_text(encoding="utf-8", errors="replace"):
            return False
        if cwd is not None:
            chk = _git("check-attr", "merge", "--", ".claude/memory/_atom_index.json", "memory/_atom_index.json",
                       cwd=cwd)
            if chk.returncode == 0 and ": merge: atomindex" not in chk.stdout:
                return False
        return True
    except Exception:
        return False


def install(quiet: bool = False) -> Dict[str, Any]:
    """各機一次。先寫 attributes 再寫 config（config 存在 ⇒ attributes 已成功），冪等。"""
    rep: Dict[str, Any] = {"installed": False, "driver": driver_command(), "attributes": "", "error": None}
    attr, was_set = attributes_file()
    rep["attributes"] = str(attr)
    try:
        attr.parent.mkdir(parents=True, exist_ok=True)
        raw = attr.read_bytes() if attr.exists() else b""
        try:
            cur = raw.decode("utf-8")
        except UnicodeDecodeError:
            rep["error"] = f"attributes 檔不是 UTF-8，請手動加入規則：{attr}"
            _say(f"[merge-atom-index] {rep['error']}", quiet)
            return rep
        cur = cur.replace("\r\n", "\n")
        if ATTR_MARK in cur:
            head, _, rest = cur.partition(ATTR_MARK)
            rest_lines = rest.split("\n")[1:]
            while rest_lines and rest_lines[0].startswith("**/.claude/memory/"):
                rest_lines.pop(0)
            cur = head + "\n".join(rest_lines)
        cur = cur.rstrip("\n")
        new = (cur + "\n\n" if cur else "") + _attr_block()
        tmp = attr.with_suffix(attr.suffix + f".tmp.{os.getpid()}")
        tmp.write_bytes(new.encode("utf-8"))
        os.replace(tmp, attr)
        if not was_set:
            r = _git("config", "--global", "core.attributesFile", _fwd(attr))
            if r.returncode:
                rep["error"] = f"git config core.attributesFile 失敗：{r.stderr.strip()}"
                return rep
        # 先 driver 後 name：只有 name 沒 driver 時 git 會 fatal「custom merge driver atomindex lacks command line」
        r2 = _git("config", "--global", f"merge.{DRIVER_NAME}.driver", driver_command())
        r1 = _git("config", "--global", f"merge.{DRIVER_NAME}.name", "AtomicMemory 索引三檔語意三方合併")
        if r1.returncode or r2.returncode:
            rep["error"] = f"git config 失敗：{(r1.stderr or r2.stderr).strip()}"
            return rep
        rep["installed"] = True
        _say(f"[merge-atom-index] 已安裝：merge.{DRIVER_NAME}.driver = {driver_command()}", quiet)
        _say(f"[merge-atom-index] attributes：{attr}（{len(ATTR_LINES)} 條 **/.claude/memory/* 規則）", quiet)
    except Exception as e:  # noqa: BLE001
        rep["error"] = f"{type(e).__name__}: {e}"
    if rep["error"]:
        _say(f"[merge-atom-index] 安裝失敗：{rep['error']}", quiet)
    return rep


def _load_toggles() -> Dict[str, Any]:
    try:
        cfg = json.loads((SCRIPT.parent.parent / "workflow" / "config.json").read_text(encoding="utf-8-sig"))
        return cfg.get("merge_driver") or {}
    except Exception:
        return {}


def status(cwd: Optional[Path] = None) -> int:
    drv = _git("config", "--global", "--get", f"merge.{DRIVER_NAME}.driver").stdout.strip()
    _out(f"merge.{DRIVER_NAME}.driver = {drv or '(未設)'}")
    for p in _driver_paths(drv) if drv else []:
        _out(f"  {'OK ' if Path(p).exists() else 'ERR'} {p}")
    attr, was_set = attributes_file()
    has = attr.exists() and ATTR_MARK in attr.read_text(encoding="utf-8", errors="replace")
    _out(f"attributes = {attr}（core.attributesFile {'已設' if was_set else '未設，用 git 預設位置'}）"
         f" → {'含' if has else '缺'}索引三檔規則")
    chk = _git("check-attr", "merge", "text", "eol", "--", ".claude/memory/_atom_index.json",
               "memory/_atom_index.json", cwd=cwd)
    if chk.returncode == 0:
        _out("check-attr（目前 repo）:\n  " + chk.stdout.strip().replace("\n", "\n  "))
    tg = _load_toggles()
    _out(f"hook 自動化：auto_install={tg.get('auto_install', True)} auto_resolve={tg.get('auto_resolve', True)}"
         "（workflow/config.json merge_driver）")
    ok = is_installed(cwd)
    _out("狀態：" + ("已安裝" if ok else "未安裝或失效 → python tools/merge-atom-index.py --install"))
    return 0 if ok else 1


# ─── --resolve：git 已停在衝突時，把語意驅動套在 index 的三個 stage 上 ─────────
#
# stage 方向：merge 時 :2＝自己（HEAD）、:3＝對方；rebase／cherry-pick 時 :2＝upstream／新基底、
# :3＝正在重放的自己的 commit。驅動的 merge_keyed 對兩側一視同仁，方向只影響「兩側異改取 ours」的細節。

_MARKER_RE = re.compile(r"^(<{7}|={7}|>{7}|\|{7})(?: .*)?$", re.MULTILINE)


def _strip_marker_labels(text: str) -> str:
    return _MARKER_RE.sub(lambda m: m.group(1), text)


def _path_ok(rel: str) -> bool:
    return rel.startswith(("memory/", "_AIDocs/_atoms/")) or "/.claude/memory/" in ("/" + rel)


def _valid_format(rel: str, text: str) -> bool:
    name = Path(rel).name
    try:
        if name == "_atom_index.json":
            d = json.loads(text)
            return isinstance(d, dict) and isinstance(d.get("atoms"), list)
        if name == "_ATOM_INDEX.md":
            return bool(re.search(ATOM_TABLE_HEADER_RE.pattern, text, re.I | re.M))
        if name in TABLE_DOC_FILES:
            return bool(TABLE_DOC_HEADER_RE.search(text))
        return bool(re.search(CATALOG_HEADER_RE.pattern, text, re.M)) or "<!-- atom-catalog -->" in text
    except Exception:
        return False


def _driver_on_texts(base: str, ours: str, theirs: str, rel: str) -> Tuple[str, int]:
    """把三份文字丟進 run_driver（走實體 tmp 檔，與 git 呼叫路徑相同）。回 (結果, 衝突 0/1)。"""
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, text in (("base", base), ("ours", ours), ("theirs", theirs)):
            p = Path(d, name)
            p.write_bytes(text.encode("utf-8"))
            paths.append(str(p))
        saved = sys.stderr
        try:
            rc = run_driver(paths[0], paths[1], paths[2], rel)
        finally:
            sys.stderr = saved
        return _read(paths[1]), rc


def _blobs_batch(root: Path, shas: List[str]) -> Dict[str, str]:
    """一次 `git cat-file --batch` 讀所有 blob（每個子行程約 0.1 秒，hook 預算只有 2.5 秒）。"""
    if not shas:
        return {}
    r = subprocess.run(["git", "cat-file", "--batch"], input=("\n".join(shas) + "\n").encode(), capture_output=True,
                       cwd=str(root), timeout=5, **_NO_WINDOW)
    out: Dict[str, str] = {}
    buf = r.stdout
    pos = 0
    while pos < len(buf):
        nl = buf.find(b"\n", pos)
        if nl < 0:
            break
        header = buf[pos:nl].decode("ascii", "replace").split()
        if len(header) < 3:
            break
        sha, size = header[0], int(header[2])
        body = buf[nl + 1:nl + 1 + size]
        out[sha] = body.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        pos = nl + 1 + size + 1
    return out


def _driver_config_ok() -> bool:
    """比 is_installed 便宜的安裝判定（一個 git 子行程）：config 有驅動、引號內路徑存在、attributes 標記在。"""
    try:
        drv = _git("config", "--global", "--get", f"merge.{DRIVER_NAME}.driver", timeout=2).stdout.strip()
        paths = _driver_paths(drv) if drv else []
        if len(paths) < 2 or not all(Path(p).exists() for p in paths):
            return False
        attr, _ = attributes_file()
        return attr.exists() and ATTR_MARK in attr.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False


def _resolve_git(root: Path, rep: Dict[str, Any]) -> None:
    """git：把驅動套在索引三檔的 unmerged stage 上，寫回工作樹並 git add；順手 install。"""
    to_add: List[str] = []
    ls = _git_bytes("ls-files", "-u", "-z", cwd=root)
    stages: Dict[str, Dict[int, str]] = {}
    for ent in ls.stdout.split(b"\0"):
        if not ent:
            continue
        meta, _, path = ent.partition(b"\t")
        mode, sha, stage = meta.decode().split()
        stages.setdefault(path.decode("utf-8", "surrogateescape"), {})[int(stage)] = sha
    targets = [p for p in stages if Path(p).name in RESOLVE_FILES and _path_ok(p)]
    if targets:
        chk = _git("check-attr", "merge", "--", *targets, cwd=root)
        ok_paths = {ln.split(": merge: ")[0] for ln in chk.stdout.splitlines() if ln.endswith(": merge: atomindex")}
        targets = [p for p in targets if p in ok_paths]
    blobs = _blobs_batch(root, sorted({sha for p in targets for sha in stages[p].values()}))
    for rel in targets:
        st = stages[rel]
        if 2 not in st or 3 not in st:
            rep["skipped"].append({"path": rel, "reason": "一側刪除了此檔（缺 stage 2 或 3），請人工決定去留"})
            rep["remaining"].append(rel)
            continue
        base = blobs.get(st[1], "") if 1 in st else ""
        ours, theirs = blobs.get(st[2], ""), blobs.get(st[3], "")
        fp = root / rel
        wt = fp.read_bytes().decode("utf-8-sig", errors="replace").replace("\r\n", "\n") if fp.exists() else None
        merged, conflicts = _driver_on_texts(base, ours, theirs, rel)
        untouched = wt is None
        if wt is not None:
            wt_n = _strip_marker_labels(wt)
            # git 原始衝突輸出：依工作樹的標記風格只算需要的那種（有 ||||||| 才算 diff3/zdiff3）
            styles = ("--diff3", "--zdiff3") if "|||||||" in wt else ("",)
            candidates = [merged]  # 驅動自己上一輪留下的結果（表格已合、手寫段留標記）
            for style in styles:
                try:
                    candidates.append(textual_merge(base, ours, theirs, style)[0])
                except Exception:
                    pass
            untouched = any(wt_n == _strip_marker_labels(c) for c in candidates)
        if untouched:
            _write(str(fp), merged)
            if conflicts == 0:
                to_add.append(rel)
                rep["resolved"].append(rel)
            else:  # 表格已語意合併、手寫段兩側同改留標記；不 add，交 CC 判斷
                rep["remaining"].append(rel)
                rep["skipped"].append({"path": rel, "reason": "表格已合併，表外手寫文字兩側同改，已留 <<<<<<< 標記待判斷"})
        elif "<<<<<<<" not in wt:
            if _valid_format(rel, wt):
                to_add.append(rel)
                rep["staged_user_version"].append(rel)
            else:
                rep["remaining"].append(rel)
                rep["skipped"].append({"path": rel, "reason": "工作樹版本無標記但格式不合法，未 stage"})
        else:
            rep["remaining"].append(rel)
            rep["skipped"].append({"path": rel, "reason": "工作樹已被手動改過且仍有衝突標記，不覆蓋"})
    if to_add:
        add = _git("add", "--", *to_add, cwd=root)
        if add.returncode:
            rep["error"] = f"git add 失敗：{add.stderr.strip()}"
            for p in to_add:
                rep["remaining"].append(p)
            rep["resolved"], rep["staged_user_version"] = [], []
    rep["installed"] = _driver_config_ok() or bool(install(quiet=True).get("installed"))


# ─── SVN 工作副本：update 停在索引三檔衝突後，套同一套驅動 ─────────────────────
#
# SVN 沒有 merge driver 可裝，只有這條備案。update（CLI 或 TortoiseSVN）留下 X.mine（更新前自己的
# 工作版＝ours）、X.r<舊>（base）、X.r<新>（theirs）；三個路徑由 `svn info --xml` 的 <conflict type="text">
# 直接給，不猜檔名。解完 `svn resolve --accept working`（.mine/.rN 隨之刪除）。
# 只掃 memory dir 候選（hooks/wg_core.memory_dir_candidates），不掃整個工作副本：大 WC 的 svn status
# 要 3～6 秒，超出 hook 預算。svn 只用 --xml 輸出（一律 UTF-8；純文字輸出走 locale，非 ASCII 路徑會壞）。
# 沒有 stage 可重建「原始衝突輸出」→ 工作檔仍含 <<<<<<< 標記就當未動過（含驅動上一輪留下的殘留），
# 人解到一半但還留著標記的版本會被覆蓋——SVN 邊界，文件明列。

def _wg_core():
    hooks = SCRIPT.parent.parent / "hooks"
    if str(hooks) not in sys.path:
        sys.path.insert(0, str(hooks))
    import wg_core  # noqa: E402
    return wg_core


def _svn(*args: str, cwd: Optional[Path] = None, timeout: float = 5.0) -> subprocess.CompletedProcess:
    return subprocess.run(["svn", "--non-interactive", *args], capture_output=True,
                          cwd=str(cwd) if cwd else None, timeout=timeout, **_NO_WINDOW)


def _svn_err(r: subprocess.CompletedProcess) -> str:
    lines = r.stderr.decode("utf-8", "replace").strip().splitlines()
    return lines[-1] if lines else f"rc={r.returncode}"


def _svn_entries(r: subprocess.CompletedProcess):
    return ET.fromstring(r.stdout).iter("entry") if r.stdout.strip() else iter(())


def _rel_to(root: Path, p: str) -> Optional[str]:
    """svn --xml 的 path 屬性（相對 cwd 或絕對、反斜線）→ 相對 root 的正斜線路徑；不在 root 下回 None。"""
    try:
        fp = Path(p)
        return (fp if fp.is_absolute() else root / fp).resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _svn_conflicted_index_files(root: Path, dirs: List[Path]) -> List[str]:
    r = _svn("status", "--xml", "--", *[str(d) for d in dirs], cwd=root)
    if r.returncode:
        raise RuntimeError(f"svn status 失敗：{_svn_err(r)}")
    out: List[str] = []
    for ent in _svn_entries(r):
        ws = ent.find("wc-status")
        if ws is None or ws.get("item") != "conflicted":
            continue
        rel = _rel_to(root, ent.get("path", ""))
        if rel and Path(rel).name in RESOLVE_FILES and _path_ok(rel) and rel not in out:
            out.append(rel)
    return out


def _svn_conflict_sources(root: Path, rels: List[str]) -> Dict[str, Tuple[str, str, str]]:
    """每檔 (mine＝ours, base, theirs) 的絕對路徑。部分 target 失敗時 svn rc≠0 但其餘照列，能解多少算多少。"""
    r = _svn("info", "--xml", "--", *rels, cwd=root)
    out: Dict[str, Tuple[str, str, str]] = {}
    for ent in _svn_entries(r):
        rel = _rel_to(root, ent.get("path", ""))
        for c in ent.findall("conflict"):
            if c.get("type") != "text":
                continue
            mine, base, theirs = (c.findtext(k) for k in ("prev-wc-file", "prev-base-file", "cur-base-file"))
            if rel and mine and base and theirs:
                out[rel] = (mine, base, theirs)
    return out


def _resolve_svn(root: Path, start: Path, rep: Dict[str, Any]) -> None:
    dirs = _wg_core().memory_dir_candidates(start, root)
    targets = _svn_conflicted_index_files(root, dirs) if dirs else []
    sources = _svn_conflict_sources(root, targets) if targets else {}
    to_resolve: List[str] = []
    for rel in targets:
        src = sources.get(rel)
        if not src or not all(Path(p).exists() for p in src):
            rep["skipped"].append({"path": rel, "reason": "非文字衝突或衝突來源檔（.mine/.rN）已不在，請人工處理"})
            rep["remaining"].append(rel)
            continue
        mine, base, theirs = (_read(p) for p in src)
        fp = root / rel
        wt = _read(str(fp)) if fp.exists() else None
        merged, conflicts = _driver_on_texts(base, mine, theirs, rel)
        if wt is None or "<<<<<<<" in wt:
            _write(str(fp), merged)
            if conflicts == 0:
                to_resolve.append(rel)
                rep["resolved"].append(rel)
            else:
                rep["remaining"].append(rel)
                rep["skipped"].append({"path": rel, "reason": "表格已合併，表外手寫文字兩側同改，已留 <<<<<<< 標記待判斷"})
        elif _valid_format(rel, wt):
            to_resolve.append(rel)
            rep["staged_user_version"].append(rel)
        else:
            rep["remaining"].append(rel)
            rep["skipped"].append({"path": rel, "reason": "工作副本版本無標記但格式不合法，未標記 resolved"})
    if to_resolve:
        r = _svn("resolve", "--accept", "working", "--", *to_resolve, cwd=root)
        if r.returncode:
            rep["error"] = f"svn resolve 失敗：{_svn_err(r)}"
            rep["remaining"].extend(to_resolve)
            rep["resolved"], rep["staged_user_version"] = [], []
    rep["installed"] = _driver_config_ok()  # svn 無驅動可裝；只回報 git 端現況


def resolve(cwd: Path, quiet: bool = False) -> Tuple[Dict[str, Any], int]:
    rep: Dict[str, Any] = {"resolved": [], "staged_user_version": [], "skipped": [], "remaining": [],
                           "installed": False, "error": None}
    try:
        vcs = _wg_core().find_vcs_root(cwd)  # 最近的 VCS 根：svn WC 住在 git repo 裡時要走 svn
        if vcs is None:
            rep["error"] = "不在 git repo 或 svn 工作副本內"
            return rep, 1
        if vcs[0] == "svn":
            _resolve_svn(vcs[1], cwd, rep)
        else:
            top = _git("rev-parse", "--show-toplevel", cwd=cwd)
            if top.returncode:
                rep["error"] = "不在 git repo 內"
                return rep, 1
            _resolve_git(Path(top.stdout.strip()), rep)
    except subprocess.TimeoutExpired as e:
        rep["error"] = f"git/svn 逾時：{e}"
    except Exception as e:  # noqa: BLE001
        rep["error"] = f"{type(e).__name__}: {e}"
    rc = 0 if (not rep["remaining"] and not rep["error"]) else 1
    if rep["resolved"]:
        _say(f"[merge-atom-index] 已合併並 add／resolve：{', '.join(rep['resolved'])}", quiet)
    for s in rep["skipped"]:
        _say(f"[merge-atom-index] 未解：{s['path']} — {s['reason']}", quiet)
    if rep["error"]:
        _say(f"[merge-atom-index] 錯誤：{rep['error']}", quiet)
    return rep, rc


# ─── CLI ──────────────────────────────────────────────────────────────────

def main(argv: List[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    quiet = "--quiet" in argv
    cwd: Optional[Path] = None
    if "--cwd" in argv:
        i = argv.index("--cwd")
        if i + 1 < len(argv):
            cwd = Path(argv[i + 1])
    if "--install" in argv:
        rep = install(quiet=quiet)
        if quiet:
            _out(json.dumps(rep, ensure_ascii=False))
        return 0 if rep["installed"] else 1
    if "--is-installed" in argv:
        return 0 if is_installed(cwd or Path.cwd()) else 1
    if "--status" in argv:
        return status(cwd or Path.cwd())
    if "--resolve" in argv:
        rep, rc = resolve(cwd or Path.cwd(), quiet=quiet)
        _out(json.dumps(rep, ensure_ascii=False))
        return rc
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 3:
        _out(__doc__ or "")
        return 2
    return run_driver(pos[0], pos[1], pos[2], pos[3] if len(pos) > 3 else "")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
