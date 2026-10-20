#!/usr/bin/env python3
"""project-smells.py：把專案的壞味道報告變成「前 N 筆＋分類＋理由」候選池（給 MCP `project_smells` 與注入用）；
另有 commit 前病形檢查（PreToolUse commit 段呼叫，見下方「commit 前病形檢查」段）。

怎麼跑：
  python tools/project-smells.py --cwd <專案內任一路徑> --part <部位名> [--top-n 5] [--json]
  結果最後一行哨兵：PROJECT_SMELLS DONE n=<k>（失敗則 PROJECT_SMELLS FAIL reason=<...>，exit 1）
  python tools/project-smells.py --commit-check --cwd <repo 或 svn 工作副本>
  照「現在下 git commit／svn commit」會提交的內容查病形；尾行 SMELL_GATE_CHECK PASS|FAIL（有新寫進的病＝FAIL，exit 1）

來源三選一（讀四層合併後的設定，與導讀卡同一份：lib/hub_config.merge_hub_cfg＝預設 < workflow/config.json 的 overview_hub
< <公司根>/.claude/overview-hub.json < <專案根>/.claude/overview-hub.json；相對路徑一律以專案根為基準；設定有錯 → FAIL）：
  smells_report  報告檔（JSON：list 或 {rows|items|smells:[...]}；每列 path／category|kind／reason／score?／part?）
                 超過 smells_max_age_days（預設 7）只在表頭加一行 stale，資料照回
  smells_cmd     沒報告（或報告不存在）就跑這條指令，stdout 要是同格式 JSON；逾時 smells_timeout_s（預設 20）回錯誤附指示
                 可給陣列（建議）或字串；字串在 Windows 交 CommandLineToArgvW 切（與 shell 同語意：--root="C:\\A B\\src" 一個 token、
                 a\\" 保護引號、不認單引號），非 Windows 走 shlex.split
  builtin        都沒有：檔案大小 ＋ 近 60 天 git fix 提交熱點（T2 重修量尺接上前的暫代）
分類只收 hotspot|size|complexity|duplication|coupling|stale|custom；其他名稱要在 smells_category_map 映射，
沒映射的列丟棄並回報 unknown_categories；沒 reason 的列丟棄並計 dropped。
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATEGORIES = ("hotspot", "size", "complexity", "duplication", "coupling", "stale", "custom")
DEFAULT_CFG: Dict[str, Any] = {
    "smells_cmd": None,
    "smells_report": None,
    "smells_max_age_days": 7,
    "smells_timeout_s": 20,
    "smells_category_map": {},
    "candidate_top_n": 5,
}
SKIP_DIRS = {".git", ".svn", "node_modules", "__pycache__", ".claude", "_AIDocs", "obj", "bin",
             "Library", "Temp", "Logs", ".vs", ".idea", "dist", "build"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".dll", ".exe", ".pdb", ".zip", ".7z", ".pdf", ".mp4",
            ".wav", ".ogg", ".ttf", ".otf", ".woff", ".woff2", ".lance", ".jsonl", ".log", ".meta", ".asset"}
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class SmellsError(Exception):
    """來源跑不動（指令逾時／報告壞掉）；訊息要附使用者能做什麼。"""


# ─── 專案根與設定 ─────────────────────────────────────────────────────────────


_CLAUDE_DIR = Path(__file__).resolve().parents[1]    # 本工具所在的 repo 根（檔案相對，不吃 HOME）


def find_root(cwd: str) -> Path:
    """專案根，與導讀卡端（hooks/wg_overview._lookup）、量尺帳本同一套：最近的部位表 `<root>/.claude/overview-map.md`
    （lib/overview_hub.find_map）就是專案根；祖先目錄的 overview-hub.json（公司覆蓋層）不改變專案身分，公司層另由
    merge_hub_cfg 取。沒有部位表的專案照舊：最近的 `.claude/overview-hub.json`，再來 .git／.svn，再沒有就 cwd 本身。"""
    start = Path(cwd).resolve()
    lib = str(_CLAUDE_DIR / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    from overview_hub import find_map
    found = find_map(str(start))
    if found:
        return found[0]
    chain = [start] + list(start.parents)
    for p in chain:
        if (p / ".claude" / "overview-hub.json").is_file():
            return p
    for p in chain:
        if (p / ".git").exists() or (p / ".svn").exists():
            return p
    return start


def _hub_inputs() -> Tuple[Dict[str, Any], Optional[Path]]:
    """合併要的兩個外部輸入：workflow/config.json 全文與公司根。讀法與 hooks 同一份（wg_core.load_config／org_memory_root），
    以檔案相對路徑載入；載不到就是環境壞了，照實拋出。"""
    hooks = str(_CLAUDE_DIR / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    from wg_core import load_config, org_memory_root
    return load_config(), org_memory_root()


def load_hub_cfg(root: Path) -> Dict[str, Any]:
    """四層合併後的設定（lib/hub_config.merge_hub_cfg：預設 < config.json overview_hub < 公司根 < 專案根 overview-hub.json），
    只取本工具要的鍵（DEFAULT_CFG）。設定有錯（未知鍵、型別錯，與導讀卡端同一套驗證）→ SmellsError，不悄悄用預設。"""
    lib = str(_CLAUDE_DIR / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    from hub_config import merge_hub_cfg
    config, org = _hub_inputs()
    merged = merge_hub_cfg(config, org, root)
    if merged["_errors"]:
        raise SmellsError(f"overview-hub 設定錯誤（{root}）：" + "；".join(merged["_errors"][:5])
                          + "（修正 overview-hub.json／config.json 的 overview_hub 段）")
    return {k: merged.get(k, v) for k, v in DEFAULT_CFG.items()}


# ─── 三種來源 ─────────────────────────────────────────────────────────────────


def _rows_of(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = next((data[k] for k in ("rows", "items", "smells") if isinstance(data.get(k), list)), [])
    else:
        rows = []
    return [r for r in rows if isinstance(r, dict)]


def read_report(path: Path, max_age_days: int) -> Tuple[List[Dict[str, Any]], int, bool]:
    """回 (rows, age_days, stale)。年齡先看 generated_at（ISO 日期），沒有就看檔案 mtime。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SmellsError(f"報告讀不動：{path}：{e}（修正報告或把 smells_report 指到正確檔）") from e
    ts = path.stat().st_mtime
    if isinstance(data, dict) and isinstance(data.get("generated_at"), str):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", data["generated_at"])
        if m:
            ts = time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)), 0, 0, 0, 0, 0, -1))
    age_days = max(0, int((time.time() - ts) // 86400))
    return _rows_of(data), age_days, age_days > int(max_age_days)


def _split_windows(cmd: str) -> List[str]:
    """Windows 用：交給系統原生 `CommandLineToArgvW`（與 shell／CreateProcess 同一套語意：`--root="C:\\A B"` 一個 token、
    `a\\"` 的反斜線保護引號、不認單引號）。不自己寫切法：shlex 非 POSIX 只認 token 開頭的引號，自家狀態機又會把
    `a\\" --json b\\"` 吞成一個 token。"""
    cmd = cmd.strip()  # 前導空白會讓 API 回空的 argv[0]（官方明載），先去掉
    if not cmd:
        return []
    import ctypes
    from ctypes import wintypes
    shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    shell32.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    n = ctypes.c_int(0)
    p = shell32.CommandLineToArgvW(cmd, ctypes.byref(n))
    if not p:
        raise SmellsError(f"smells_cmd 切參數失敗（CommandLineToArgvW 回 NULL）：{cmd}")
    try:
        argv = [p[i] for i in range(n.value)]
    finally:
        kernel32.LocalFree(p)
    if argv and argv[0] == "":  # 再保險一層：空 argv[0] 到 subprocess 是 WinError 87
        argv = argv[1:]
    return argv


def _split_cmd(cmd: Any) -> List[str]:
    if isinstance(cmd, list):
        return [str(c) for c in cmd]
    if os.name == "nt":
        return _split_windows(str(cmd))
    return shlex.split(str(cmd))


def run_smells_cmd(cmd: Any, cwd: Path, timeout_s: int) -> List[Dict[str, Any]]:
    argv = _split_cmd(cmd)
    try:
        r = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=int(timeout_s), creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired as e:
        raise SmellsError(
            f"smells_cmd 逾時（{timeout_s}s）：{' '.join(argv)}。"
            f"把產生器改成寫報告檔並設 smells_report，或調高 smells_timeout_s") from e
    except OSError as e:
        raise SmellsError(f"smells_cmd 跑不起來：{' '.join(argv)}：{e}（檢查指令路徑與直譯器）") from e
    if r.returncode != 0:
        raise SmellsError(f"smells_cmd exit={r.returncode}：{(r.stderr or '')[-300:]}")
    try:
        return _rows_of(json.loads(r.stdout or "null"))
    except ValueError as e:
        raise SmellsError(f"smells_cmd 輸出不是 JSON：{e}；stdout 頭：{(r.stdout or '')[:200]}") from e


def _git_fix_hotspots(root: Path, since_days: int, timeout_s: int) -> Dict[str, int]:
    if not (root / ".git").exists():
        return {}
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "log", f"--since={since_days}.days", "-i", "--grep=fix",
             "--name-only", "--pretty=format:"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_s,
            creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if r.returncode != 0:
        return {}
    counts: Dict[str, int] = {}
    for line in r.stdout.splitlines():
        s = line.strip().replace("\\", "/")
        if s:
            counts[s] = counts.get(s, 0) + 1
    return counts


def builtin_candidates(root: Path, part: str, top_n: int, timeout_s: int = 20) -> List[Dict[str, Any]]:
    """沒 cmd 沒報告的暫代：近 60 天 git fix 熱點（hotspot）＋掃描範圍最大檔（size）。"""
    scope = root / part if part and (root / part).is_dir() else root
    rows: List[Dict[str, Any]] = []
    hot = _git_fix_hotspots(root, 60, timeout_s)
    rel_scope = scope.relative_to(root).as_posix() if scope != root else ""
    hot_items = [(p, n) for p, n in hot.items() if not rel_scope or p.startswith(rel_scope + "/")]
    for p, n in sorted(hot_items, key=lambda x: -x[1])[:top_n]:
        rows.append({"path": p, "category": "hotspot", "reason": f"近 60 天有 {n} 次 fix 提交觸及（builtin 代理量，非判決）", "score": n})
    sizes: List[Tuple[str, int]] = []
    for dirpath, dirnames, filenames in os.walk(scope):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if Path(fn).suffix.lower() in SKIP_EXT:
                continue
            fp = Path(dirpath) / fn
            try:
                sizes.append((fp.relative_to(root).as_posix(), fp.stat().st_size))
            except OSError:
                continue
    for i, (p, b) in enumerate(sorted(sizes, key=lambda x: -x[1])[:top_n], 1):
        rows.append({"path": p, "category": "size", "reason": f"{b // 1024} KB，掃描範圍第 {i} 大檔（builtin 代理量，大≠壞）", "score": b / 1e6})
    return rows


# ─── 正規化 ───────────────────────────────────────────────────────────────────


def normalize_rows(rows: List[Dict[str, Any]], category_map: Dict[str, str], source: str,
                   age_days: int, part: str, top_n: int) -> Dict[str, Any]:
    """過濾＋排序＋編 rank。回 {rows, dropped, dropped_unknown_category, unknown_categories, filtered_part}。"""
    cmap = {str(k).lower(): str(v).lower() for k, v in (category_map or {}).items()}
    out: List[Dict[str, Any]] = []
    dropped = 0
    unknown: Dict[str, int] = {}
    filtered_part = 0
    for r in rows:
        path = str(r.get("path") or "").strip().replace("\\", "/")
        reason = str(r.get("reason") or "").strip()
        if not path or not reason:
            dropped += 1
            continue
        row_part = str(r.get("part") or "").strip()
        if row_part and part and row_part.lower() != part.lower():
            filtered_part += 1
            continue
        cat = str(r.get("category") or r.get("kind") or "").strip().lower()
        if cat not in CATEGORIES:
            mapped = cmap.get(cat)
            if mapped not in CATEGORIES:
                unknown[cat or "(空)"] = unknown.get(cat or "(空)", 0) + 1
                continue
            cat = mapped
        try:
            score = float(r.get("score")) if r.get("score") is not None else None
        except (TypeError, ValueError):
            score = None
        out.append({"path": path, "category": cat, "reason": reason, "source": source,
                    "age_days": int(age_days), "_score": score})
    out.sort(key=lambda x: (-(x["_score"] if x["_score"] is not None else float("-inf")), x["path"]))
    out = out[:top_n]
    for i, r in enumerate(out, 1):
        r.pop("_score", None)
        r["rank"] = i
    return {"rows": out, "dropped": dropped, "dropped_unknown_category": sum(unknown.values()),
            "unknown_categories": sorted(unknown), "filtered_part": filtered_part}


# ─── 入口 ─────────────────────────────────────────────────────────────────────


def collect(cwd: str, part: str, top_n: Optional[int] = None) -> Dict[str, Any]:
    root = find_root(cwd)
    cfg = load_hub_cfg(root)
    n = int(top_n or cfg.get("candidate_top_n") or 5)
    age_days, stale, source = 0, False, "builtin"
    rows: List[Dict[str, Any]] = []
    report = cfg.get("smells_report")
    report_path = (root / report) if report and not Path(str(report)).is_absolute() else (Path(str(report)) if report else None)
    if report_path and report_path.is_file():
        rows, age_days, stale = read_report(report_path, int(cfg.get("smells_max_age_days", 7)))
        source = "report"
    elif cfg.get("smells_cmd"):
        rows = run_smells_cmd(cfg["smells_cmd"], root, int(cfg.get("smells_timeout_s", 20)))
        source = "cmd"
    else:
        rows = builtin_candidates(root, part, n, int(cfg.get("smells_timeout_s", 20)))
    norm = normalize_rows(rows, cfg.get("smells_category_map") or {}, source, age_days, part, n)
    return {"part": part, "root": str(root), "source": source, "stale": stale, "age_days": age_days,
            "max_age_days": int(cfg.get("smells_max_age_days", 7)), **norm}


def render_text(res: Dict[str, Any]) -> str:
    lines: List[str] = []
    if res["stale"]:
        lines.append(f"stale: 報告已 {res['age_days']} 天（上限 {res['max_age_days']}），資料照回，請重產報告")
    lines.append(f"part={res['part']} source={res['source']} dropped={res['dropped']} "
                 f"unknown_category={res['dropped_unknown_category']}")
    if res["unknown_categories"]:
        lines.append("未映射類別（加進 overview-hub.json 的 smells_category_map）：" + ", ".join(res["unknown_categories"]))
    lines.append("rank | path | category | reason")
    for r in res["rows"]:
        lines.append(f"{r['rank']} | {r['path']} | {r['category']} | {r['reason']}")
    return "\n".join(lines)


# ─── commit 前病形檢查（G2：帶病的改動上不了版）──────────────────────────────────
# 查的是「這次真的會進版的內容」：git 的暫存區、commit -a 的已追蹤改動、commit <路徑>、同一條指令前面 git add 才要加進來的檔；
# svn commit 的工作副本改動。每個程式檔取舊版（HEAD／BASE）與新版（要提交的那份）逐行比對：病形落在這次改到的行、而且
# 同一行（去空白後）不在任何一個提交檔的舊版裡 → 新寫進的病（擋）；其餘 → 舊碼原本就有、這次沒碰（只列出）。
# 病形兩種來源：內建（原設計者點名的匿名函式疊用、回呼套層、過度物件化；寫得保守，寧漏不誤擋）與專案部位表「病灶清單」欄
# 指的病灶文件（每條 `shape:` 是專案判斷過的病）。那一行寫 `smell-ok: <理由>` → 不擋、列進放行清單（判斷交 AI、理由留在 diff）。

SHAPES: Dict[str, Tuple[str, str, str]] = {   # 規則 → (病名, 為什麼是病, 怎麼改)
    "anon-stack": ("匿名函式疊用", "匿名函式裡再套匿名函式（同一行裡套、或 Python 的 lambda 套 lambda），讀的人要同時在腦中展開好幾層",
                   "把內層抽成有名字的函式"),
    "anon-nest": ("匿名回呼套三層以上", "回呼裡再套回呼到第三層，流程被拆進一層層沒名字的函式，讀的人要拐好幾個彎才看得到先後",
                  "每層抽成有名字的函式，或改成直線的 async／await 流程"),
    "one-method-class": ("只有建構子加一個方法的類別", "類別只是把一個函式包起來（過度物件化），多一層建構與 self，沒換到任何狀態管理",
                         "直接寫成函式，建構參數改成函式參數"),
}
_PY_EXTS = (".py", ".pyw")
_ARROW_ANON = r"=>|\bfunction\s*\(|\bdelegate\s*[({]"
_ANON_BY_EXT: Dict[str, str] = {   # 副檔名 → 這個語言的匿名函式寫法；不在表上的語言只查病灶清單
    **dict.fromkeys((".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte", ".cs", ".dart"), _ARROW_ANON),
    ".java": r"->",
    ".php": r"\bfunction\s*\(|\bfn\s*\(",
    ".lua": r"\bfunction\s*\(",
}
_STR_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`')
_SWITCH_RE = re.compile(r"\bswitch\b")
_SMELL_OK_RE = re.compile(r"smell-ok\s*[:：]\s*(.*?)\s*(?:\*/|-->)?\s*$")
_REDIRECT_RE = re.compile(r"^\d*[<>]")
_ROW_SPLIT = re.compile(r"(?<!\\)\|")
NEST_LIMIT = 3
MAX_COMMIT_FILES = 2000
VCS_TIMEOUT_S = 20


def _blank_keep_newlines(m: "re.Match[str]") -> str:
    return "``" + "\n" * m.group(0).count("\n")


def _code_lines(text: str, ext: str) -> List[str]:
    """逐行去掉字串內容與註解，行數與原文相同（只為數匿名函式與括號）。跨行的只處理反引號字串（JS 樣板字串常整段包 HTML／JS）。"""
    line_comment = "--" if ext == ".lua" else "//"
    text = re.sub(r"`(?:\\.|[^`\\])*`", _blank_keep_newlines, text)
    out: List[str] = []
    in_block = False
    for raw in text.splitlines():
        s = _STR_RE.sub('""', raw)
        buf: List[str] = []
        i = 0
        while i < len(s):
            if in_block:
                j = s.find("*/", i)
                if j < 0:
                    break
                in_block, i = False, j + 2
                continue
            if ext != ".lua" and s.startswith("/*", i):
                in_block, i = True, i + 2
                continue
            if s.startswith(line_comment, i):
                break
            buf.append(s[i])
            i += 1
        out.append("".join(buf))
    return out


def _anon_tokens(line: str, anon_re: "re.Pattern[str]") -> List["re.Match[str]"]:
    """這行的匿名函式記號；有 switch 的行（C#／Java switch 運算式的 `=>`／`->` 是分支不是函式）只認 function／delegate。"""
    found = list(anon_re.finditer(line))
    if _SWITCH_RE.search(line):
        found = [m for m in found if m.group(0) not in ("=>", "->")]
    return found


def _nested_on_line(line: str, anon_re: "re.Pattern[str]") -> bool:
    """同一行裡，匿名函式的本體內又出現匿名函式（`a(x => b(y => y))`）；並列的（`.Where(r => …).Select(r => …)`）不算。
    本體從記號所在的括號深度開始，到深度掉到它以下、或同深度遇到 `,`／`;` 為止。"""
    ends = {m.start(): m.end() for m in _anon_tokens(line, anon_re)}
    bodies: List[int] = []      # 還沒結束的匿名函式本體各在哪個括號深度
    depth = i = 0
    while i < len(line):
        if i in ends:
            if bodies:
                return True
            bodies.append(depth)
            i = ends[i] - 1 if line[ends[i] - 1] in "({" else ends[i]    # `function(`／`delegate {` 的括號照常算深度
            continue
        ch = line[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            while bodies and depth < bodies[-1]:
                bodies.pop()
        elif ch in ",;":
            while bodies and depth <= bodies[-1]:
                bodies.pop()
        i += 1
    return False


def _brace_hits(text: str, ext: str) -> List[Tuple[str, int]]:
    """大括號語言：同一行匿名函式套匿名函式（anon-stack）、匿名函式本體跨行套到第三層（anon-nest，錨在第三層開頭那行）。"""
    pattern = _ANON_BY_EXT.get(ext)
    if not pattern:
        return []
    anon_re = re.compile(pattern)
    token_re = re.compile(pattern + r"|[{};]")
    hits: List[Tuple[str, int]] = []
    stack: List[bool] = []      # 每個還開著的 { 是不是匿名函式的本體
    pending = False             # 看到匿名函式記號、還在等它的 {
    for no, line in enumerate(_code_lines(text, ext), 1):
        if _nested_on_line(line, anon_re):
            hits.append(("anon-stack", no))
        anon_here = {m.start() for m in _anon_tokens(line, anon_re)}
        for m in token_re.finditer(line):
            t = m.group(0)
            if t == "{":
                stack.append(pending)
                if pending and sum(stack) >= NEST_LIMIT:
                    hits.append(("anon-nest", no))
                pending = False
            elif t == "}":
                if stack:
                    stack.pop()
                pending = False
            elif t == ";":
                pending = False
            elif m.start() in anon_here:
                rest = line[m.end():].lstrip()
                if t in ("=>", "->") and rest and not rest.startswith("{"):
                    if sum(stack) + 1 >= NEST_LIMIT:    # 表達式本體的匿名函式：自己算一層，不開大括號
                        hits.append(("anon-nest", no))
                    continue
                pending = True
    return hits


def _one_method_class(node: ast.ClassDef) -> bool:
    """沒繼承、沒裝飾、本體只有 __init__ 加一個方法（其餘只有 docstring／pass）。有繼承的多半是框架要求，不算。"""
    if node.decorator_list or node.keywords or any(not (isinstance(b, ast.Name) and b.id == "object") for b in node.bases):
        return False
    funcs = [s.name for s in node.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))]
    others = [s for s in node.body if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Pass))
              and not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    return not others and len(funcs) == 2 and "__init__" in funcs and not any(f.startswith("__") and f != "__init__" for f in funcs)


def _py_hits(text: str, is_test: bool) -> Optional[List[Tuple[str, int, int, int]]]:
    """Python 用語法樹判（字串、註解裡的字不會算）：lambda 套 lambda（錨在內層、範圍是外層整段）、單方法類別（範圍是整個類別；
    測試檔不查：替身類別就長這樣）。同一行並列的 lambda（dict 裡一排替身）不算。回 (規則, 錨點行, 範圍起, 範圍迄)；
    語法錯回 None（判不了，由呼叫端記一筆）。"""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    hits: List[Tuple[str, int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            inner = next((n for n in ast.walk(node.body) if isinstance(n, ast.Lambda)), None)
            if inner is not None:
                hits.append(("anon-stack", inner.lineno, node.lineno, node.end_lineno or node.lineno))
        elif isinstance(node, ast.ClassDef) and not is_test and _one_method_class(node):
            hits.append(("one-method-class", node.lineno, node.lineno, node.end_lineno or node.lineno))
    return hits


def _is_test_file(abs_path: str) -> bool:
    """跟寫碼查核同一份測試檔定義（hooks/wg_verify_ledger 的 verify_case_globs 預設）。"""
    hooks = str(_CLAUDE_DIR / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    from wg_verify_ledger import RECONCILE_DEFAULTS, is_verify_case
    return is_verify_case(abs_path, RECONCILE_DEFAULTS["verify_case_globs"])


def parse_defect_shapes(text: str, doc: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """病灶文件（templates/defects.template.md 的格式；同步：templates/prebuild-check.template.py parse_shapes）→
    ([{name, fix, regex}], 問題清單)。表格列的「形狀」欄 `shape: <regex>`（`\\|` 讀成 `|`），病名取「症狀」欄、怎麼改取「修法」欄；
    表外單獨一行 `shape: <regex>` 病名用形狀本身。不合法的 regex 不用，記進問題清單。"""
    shapes: List[Dict[str, str]] = []
    problems: List[str] = []
    cols = {"症狀": 1, "修法": 3}
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in _ROW_SPLIT.split(line.strip().strip("|"))]
            if "症狀" in cells:
                cols = {k: cells.index(k) for k in ("症狀", "修法") if k in cells}
                continue
            for cell in cells:
                body = cell.strip("`").strip()
                if body.startswith("shape:"):
                    regex = body[len("shape:"):].strip().strip("`").replace("\\|", "|")
                    name, fix = (cells[cols[k]].strip("`") if cols.get(k, 99) < len(cells) else "" for k in ("症狀", "修法"))
                    shapes.append({"name": name or f"病灶清單形狀 {regex}", "fix": fix, "regex": regex})
            continue
        m = re.match(r"^\s*(?:[-*]\s*)?shape:\s*(.+?)\s*$", line)
        if m:
            regex = m.group(1).strip("`")
            shapes.append({"name": f"病灶清單形狀 {regex}", "fix": "", "regex": regex})
    out = []
    for s in shapes:
        if not s["regex"] or s["regex"] == "無":
            continue
        try:
            re.compile(s["regex"])
        except re.error as e:
            problems.append(f"病灶清單 {doc} 的形狀 {s['regex']!r} 不是合法 regex（{e}），沒拿來查")
            continue
        out.append(s)
    return out, problems


def _defect_shapes(abs_path: str, cache: Dict[str, Any], notes: List[str]) -> List[Dict[str, str]]:
    """這個檔所屬部位在部位表「病灶清單」欄指的病灶文件裡的形狀；沒部位表、沒填、填「無」→ 空。"""
    lib = str(_CLAUDE_DIR / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    from overview_hub import find_map, match_row, parse_map
    found = find_map(abs_path)
    if not found:
        return []
    root, map_path = found
    key = str(map_path)
    if key not in cache:
        cache[key] = parse_map(map_path.read_text(encoding="utf-8", errors="replace"))
    row = match_row(abs_path, root, cache[key], anchored=True)
    doc = (row or {}).get("defects_doc") or ""
    if not doc or doc == "無":
        return []
    doc_path = root / doc
    dkey = "doc:" + str(doc_path)
    if dkey not in cache:
        if not doc_path.is_file():
            notes.append(f"部位表指的病灶清單 {doc} 不存在，這個部位只查了內建病形（補檔或改部位表）")
            cache[dkey] = []
        else:
            shapes, problems = parse_defect_shapes(doc_path.read_text(encoding="utf-8", errors="replace"), doc)
            notes.extend(problems)
            cache[dkey] = shapes
    return cache[dkey]


def scan_text(abs_path: str, text: str, cache: Dict[str, Any], notes: List[str]) -> List[Dict[str, Any]]:
    """一個檔的一個版本 → 病形命中 [{rule, name, why, fix, line, start, end, text}]：line 是點名的那一行，
    start～end 是整個病形的範圍（改到範圍裡任一行，都算這次碰到這個病形）。"""
    ext = Path(abs_path).suffix.lower()
    lines = text.splitlines()
    found: List[Tuple[str, int, int, int]] = []
    if ext in _PY_EXTS:
        py = _py_hits(text, _is_test_file(abs_path))
        if py is None:
            notes.append(f"{Path(abs_path).name} 有語法錯，內建病形沒查（語法樹建不起來）")
        found = py or []
    else:
        found = [(rule, no, no, no) for rule, no in _brace_hits(text, ext)]
    hits = []
    seen = set()
    for rule, no, start, end in found:
        if (rule, no) in seen:
            continue
        seen.add((rule, no))
        name, why, fix = SHAPES[rule]
        hits.append({"rule": rule, "name": name, "why": why, "fix": fix, "line": no, "start": start, "end": end,
                     "text": lines[no - 1] if 0 < no <= len(lines) else ""})
    for s in _defect_shapes(abs_path, cache, notes):
        pat = re.compile(s["regex"])
        for no, line in enumerate(lines, 1):
            if pat.search(line):
                hits.append({"rule": "defect:" + s["regex"], "name": s["name"], "why": "專案病灶清單列的病",
                             "fix": s["fix"] or "照病灶清單的修法改", "line": no, "start": no, "end": no, "text": line})
    return hits


def changed_lines(old: str, new: str) -> set:
    """新版裡這次新增或改寫的行號（1 起算）；刪掉的行算碰到刪除處前後兩行（類別刪掉一個方法也是改了這個類別）。"""
    sm = difflib.SequenceMatcher(None, old.splitlines(), new.splitlines(), autojunk=False)
    out = set()
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            out.update(range(j1 + 1, j2 + 1))
        elif tag == "delete":
            out.update((j1, j1 + 1))
    return out


def _squash(line: str) -> str:
    return " ".join(line.split())


def classify(files: List[Dict[str, Any]], cache: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """files：[{path（顯示用）, abs, old, new}]；new 為 None＝這次刪掉的檔（只拿舊版當「原本就有」的比對來源）。
    回 {new, old, allowed, notes}：new＝新寫進的病、old＝舊碼原本就有或原樣搬動、allowed＝寫了 smell-ok 理由放行的。
    新舊對帳一份抵一份：所有提交檔舊版裡每個（規則, 點名那行）各有幾份；範圍沒被碰到的病先各抵掉一份，碰到的再拿剩下的抵，
    抵得到＝原樣搬動，抵不到＝新寫進的（原行保留又複製一份，多的那份抵不到）。"""
    cache = {} if cache is None else cache
    notes: List[str] = []
    before: Dict[Tuple[str, str], int] = {}
    for f in files:
        for h in scan_text(f["abs"], f["old"], cache, []) if f["old"] else []:
            key = (h["rule"], _squash(h["text"]))
            before[key] = before.get(key, 0) + 1
    res: Dict[str, Any] = {"new": [], "old": [], "allowed": [], "notes": notes}
    touched_hits = []
    for f in files:
        if f["new"] is None:
            continue
        touched = changed_lines(f["old"] or "", f["new"])
        for h in scan_text(f["abs"], f["new"], cache, notes):
            h["path"] = f["path"]
            key = (h["rule"], _squash(h["text"]))
            if touched.isdisjoint(range(h["start"], h["end"] + 1)):
                before[key] = max(0, before.get(key, 0) - 1)
                res["old"].append(h)
            else:
                touched_hits.append((key, h))
    for key, h in touched_hits:
        if before.get(key, 0) > 0:
            before[key] -= 1
            res["old"].append(h)
            continue
        ok = _SMELL_OK_RE.search(h["text"])
        if ok and len(ok.group(1)) >= 2:
            h["reason"] = ok.group(1)
            res["allowed"].append(h)
            continue
        res["new"].append(h)
    return res


def _vcs(argv: List[str], cwd: str, data: Optional[bytes] = None) -> subprocess.CompletedProcess:
    """跑 git／svn（bytes 輸出）；起不來或逾時 → SmellsError（判不了，呼叫端擋）。"""
    try:
        return subprocess.run(argv, cwd=cwd, input=data, capture_output=True, timeout=VCS_TIMEOUT_S,
                              creationflags=_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise SmellsError(f"{' '.join(argv[:3])} 跑不動（{type(e).__name__}）：{e}") from e


def _vcs_z(argv: List[str], cwd: str) -> List[str]:
    """跑帶 `-z` 的 git 列舉指令，回 NUL 分隔的欄位（拿到真檔名：不帶 -z 時中文檔名會被引號加八進位跳脫）。"""
    r = _vcs(argv, cwd)
    if r.returncode != 0:
        raise SmellsError(f"{' '.join(argv)} 失敗：{r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return [f for f in r.stdout.decode("utf-8", "replace").split("\0") if f]


def _cat_blobs(root: str, specs: List[str]) -> Dict[str, Optional[bytes]]:
    """一次 `git cat-file --batch` 取多個 `<rev>:<path>`；不存在回 None。"""
    if not specs:
        return {}
    r = _vcs(["git", "cat-file", "--batch"], root, ("\n".join(specs) + "\n").encode("utf-8"))
    out, pos, res = r.stdout, 0, {}
    for spec in specs:
        nl = out.find(b"\n", pos)
        if nl < 0:
            raise SmellsError(f"git cat-file 輸出不完整（讀到 {spec} 時斷了）")
        head = out[pos:nl].rsplit(b" ", 2)
        pos = nl + 1
        if len(head) == 3 and head[2].isdigit():
            size = int(head[2])
            res[spec] = out[pos:pos + size] if head[1] == b"blob" else None
            pos += size + 1
        else:
            res[spec] = None
    return res


def _not_args(tokens: List[str]):
    """跳過 shell 轉向（`<<EOF`、`2>&1`、`> f` 與它的檔名），其餘照順序交出。"""
    it = iter(tokens)
    for t in it:
        if t in ("<", ">", ">>", "<<", "<<<", "2>", "&>"):
            next(it, None)
        elif not _REDIRECT_RE.match(t):
            yield t


_COMMIT_VALUE_SHORT = set("mFCct")
_COMMIT_VALUE_LONG = {"--message", "--file", "--reuse-message", "--reedit-message", "--template", "--author", "--date",
                      "--cleanup", "--fixup", "--squash", "--trailer", "--pathspec-from-file"}


def commit_options(tokens: List[str]) -> Dict[str, Any]:
    """`git commit …` 的 tokens（tokens[0]＝commit）→ {all, amend, include, paths, unjudgeable}。
    unjudgeable＝用了預讀不到提交範圍的選項（路徑清單放在檔案或 stdin），呼叫端判不了就擋。"""
    opts: Dict[str, Any] = {"all": False, "amend": False, "include": False, "paths": [], "unjudgeable": ""}
    it = _not_args(tokens[1:])
    for t in it:
        if t == "--":
            opts["paths"] += list(it)
            break
        if t.startswith("--"):
            name = t.split("=", 1)[0]
            opts["all"] |= name == "--all"
            opts["amend"] |= name == "--amend"
            opts["include"] |= name == "--include"
            if name in ("--pathspec-from-file", "--pathspec-file-nul"):
                opts["unjudgeable"] = name
            if name in _COMMIT_VALUE_LONG and "=" not in t:
                next(it, None)
            continue
        if t.startswith("-") and len(t) > 1:
            for k, ch in enumerate(t[1:], 1):
                opts["all"] |= ch == "a"
                opts["include"] |= ch == "i"
                if ch in _COMMIT_VALUE_SHORT:
                    if k == len(t) - 1:
                        next(it, None)
                    break
            continue
        opts["paths"].append(t)
    return opts


def add_specs(tokens: List[str]) -> Tuple[List[str], bool]:
    """`git add …` 的 tokens → (路徑規格, 只收已追蹤的檔)。`-A`／`-u` 沒給路徑＝整個 repo。"""
    specs: List[str] = []
    whole = tracked_only = False
    it = _not_args(tokens[1:])
    for t in it:
        if t == "--":
            specs += list(it)
            break
        if t in ("-A", "--all", "--no-ignore-removal"):
            whole = True
        elif t in ("-u", "--update"):
            whole = tracked_only = True
        elif not t.startswith("-"):
            specs.append(t)
    return (specs or ([":/"] if whole else [])), tracked_only


def _is_code(abs_path: str, config: Dict[str, Any]) -> bool:
    """跟寫碼查核同一份判法（hooks/wg_need_goal.is_code_path：程式副檔名清單＋知識類部位不算）。"""
    hooks = str(_CLAUDE_DIR / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    from wg_need_goal import is_code_path
    return is_code_path(abs_path, config)


def _take_status(fields: List[str], src: str, into: Dict[str, Tuple[str, str]]) -> None:
    """`--name-status -z` 的欄位 → into[新路徑] = (來源, 舊路徑)；改名取舊名當舊版。刪除：工作樹這邊刪了（commit -a、
    git add 會把刪除帶進去）就蓋成 gone；暫存區的刪除只在還沒有別的來源時記。"""
    i = 0
    while i + 1 < len(fields):
        code = fields[i][:1]
        if code in ("R", "C") and i + 2 < len(fields):
            into[fields[i + 2]] = (src, fields[i + 1])
            i += 3
            continue
        path = fields[i + 1]
        if code != "D":
            into[path] = (src, path)
        elif src == "work":
            into[path] = ("gone", path)
        else:
            into.setdefault(path, ("gone", path))
        i += 2


def _take_added(paths: List[str], into: Dict[str, Tuple[str, str]]) -> None:
    for p in paths:
        into[p] = ("work", p)


def commit_entries(run_cwd: str, commit_tokens: List[str],
                   adds: List[Tuple[str, List[str]]]) -> Optional[Tuple[str, str, bool, Dict[str, Tuple[str, str]]]]:
    """這次 git commit 真的會提交哪些檔（commit 前病形閘與隱私閘共用）。adds＝同一條指令裡排在這個 commit 前面的
    git add（執行目錄, tokens）：PreToolUse 時它們還沒跑，要把它們會加進來的檔算進去。
    回 (repo 根, 舊版 rev, 有沒有 HEAD, {repo 相對路徑: (新版來源 index|work|gone, 舊版路徑)})；不是 git repo → None。"""
    top = _vcs(["git", "rev-parse", "--show-toplevel"], run_cwd)
    if top.returncode != 0:
        return None
    root = top.stdout.decode("utf-8", "replace").strip()
    opts = commit_options(commit_tokens)
    if opts["unjudgeable"]:
        raise SmellsError(f"git commit 用了 {opts['unjudgeable']}（路徑清單在檔案或 stdin 裡），預讀不到這次提交範圍，"
                          "病形檢查判不了；把路徑直接寫在 git commit 後面，或先 git add 再 commit")
    has_head = _vcs(["git", "rev-parse", "--verify", "-q", "HEAD"], root).returncode == 0
    base = "HEAD^" if opts["amend"] else "HEAD"
    entries: Dict[str, Tuple[str, str]] = {}

    def worktree(cwd: str, specs: List[str], tracked_only: bool) -> None:
        """這些路徑會以工作樹內容進版（git add 之後、commit <路徑>）：暫存區已有的也改成工作樹那份（工作樹改回 HEAD 就沒差異）。"""
        if has_head:
            for cmd in (["diff", "--cached"], ["diff"]):
                _take_status(_vcs_z(["git", *cmd, "--name-status", "-z", "--no-renames", "HEAD", "--", *specs], cwd),
                             "work", entries)
        else:
            _take_added(_vcs_z(["git", "ls-files", "-z", "-c", "--full-name", "--", *specs], cwd), entries)
        if not tracked_only:
            _take_added(_vcs_z(["git", "ls-files", "-z", "-o", "--exclude-standard", "--full-name", "--", *specs], cwd),
                        entries)

    if opts["paths"] and not opts["include"]:
        worktree(run_cwd, opts["paths"], True)          # commit <路徑>：只提交這些路徑的工作樹內容
    else:
        rev = [base] if has_head else []
        _take_status(_vcs_z(["git", "diff", "--cached", "--name-status", "-z", "-M", *rev], root), "index", entries)
        if opts["all"]:
            _take_status(_vcs_z(["git", "diff", "--name-status", "-z", "--no-renames"], root), "work", entries)
        if opts["include"] and opts["paths"]:
            worktree(run_cwd, opts["paths"], True)
        for add_cwd, add_tokens in adds:
            add_top = _vcs(["git", "rev-parse", "--show-toplevel"], add_cwd)
            if add_top.returncode != 0 or add_top.stdout.decode("utf-8", "replace").strip() != root:
                continue
            specs, tracked_only = add_specs(add_tokens)
            if specs:
                worktree(add_cwd, specs, tracked_only)
    return root, base, has_head, entries


def git_commit_files(run_cwd: str, commit_tokens: List[str], adds: List[Tuple[str, List[str]]],
                     config: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """這次 git commit 會提交的程式檔，各取新舊兩版；不是 git repo → None（commit 自己會失敗，沒東西可查）。"""
    found = commit_entries(run_cwd, commit_tokens, adds)
    if found is None:
        return None
    root, base, has_head, entries = found
    code = {rel: v for rel, v in entries.items() if _is_code(os.path.join(root, rel), config)}
    _check_size(len(code))
    old_specs = [f"{base}:{old}" for _src, old in code.values()] if has_head else []
    idx_specs = [f":{rel}" for rel, (src, _old) in code.items() if src == "index"]
    blobs = _cat_blobs(root, old_specs + idx_specs)
    files = []
    for rel, (src, old_rel) in code.items():
        old = blobs.get(f"{base}:{old_rel}")
        if src == "gone":
            new = None
        elif src == "index":
            new = blobs.get(f":{rel}")
        else:
            try:
                new = (Path(root) / rel).read_bytes()
            except OSError:
                continue
        files.append({"path": rel, "abs": os.path.join(root, rel),
                      "old": (old or b"").decode("utf-8", "replace"),
                      "new": None if new is None else new.decode("utf-8", "replace")})
    return files


def _check_size(n: int) -> None:
    """程式檔太多就判不了（擋），不能只查一部分就說沒有新病。"""
    if n > MAX_COMMIT_FILES:
        raise SmellsError(f"這次提交 {n} 個程式檔，超過一次能查的 {MAX_COMMIT_FILES} 個，病形檢查判不了；"
                          "拆成幾次較小的 commit 再提交")


_SVN_VALUE_FLAGS = {"-m", "--message", "-F", "--file", "--with-revprop", "--encoding", "--editor-cmd", "--config-dir",
                    "--config-option", "--username", "--password"}
_SVN_SCOPE_FLAGS = {"--depth", "--changelist", "--cl"}    # 照原樣帶進 svn status，查的範圍才跟提交範圍一樣


def svn_commit_files(run_cwd: str, commit_tokens: List[str], config: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """這次 svn commit 會提交的程式檔：`svn status` 的修改、新增、取代（BASE 當舊版）；刪除的只當舊版比對來源。
    提交範圍選項（--depth、--changelist、--targets 清單檔）照樣套到 status。不是工作副本 → None。"""
    paths: List[str] = []
    scope: List[str] = []
    it = _not_args(commit_tokens[1:])
    for t in it:
        name, eq, val = t.partition("=")
        if name in _SVN_SCOPE_FLAGS:
            scope += [name, val if eq else next(it, "")]
        elif name == "--targets":
            target_file = Path(run_cwd) / (val if eq else next(it, ""))
            try:
                paths += [ln.strip() for ln in target_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
            except OSError as e:
                raise SmellsError(f"svn commit --targets 的清單檔讀不到（{e}），病形檢查判不了") from e
        elif name in _SVN_VALUE_FLAGS:
            if not eq:
                next(it, None)
        elif not t.startswith("-"):
            paths.append(t)
    r = _vcs(["svn", "--non-interactive", "status", "--xml", "-q", *scope, *(paths or ["."])], run_cwd)
    if r.returncode != 0:
        return None
    files = []
    for entry in ET.fromstring(r.stdout).iter("entry"):
        st = entry.find("wc-status")
        item = st.get("item") if st is not None else ""
        if item not in ("modified", "added", "replaced", "deleted"):
            continue
        rel = (entry.get("path") or "").replace("\\", "/")
        abs_path = os.path.join(run_cwd, rel)
        if not _is_code(abs_path, config):
            continue
        old = b""
        if item != "added":
            cat = _vcs(["svn", "--non-interactive", "cat", "-r", "BASE", abs_path], run_cwd)
            old = cat.stdout if cat.returncode == 0 else b""
        try:
            new = None if item == "deleted" else Path(abs_path).read_bytes()
        except OSError:
            continue
        files.append({"path": rel, "abs": abs_path, "old": old.decode("utf-8", "replace"),
                      "new": None if new is None else new.decode("utf-8", "replace")})
        _check_size(len(files))
    return files


def _report_rows(files: List[Dict[str, Any]], notes: List[str]) -> List[Dict[str, Any]]:
    """專案的壞味道報告（smells_report）裡、這次提交到的檔的列：整檔層級、沒有行號，一律算舊碼原本就有。
    只讀報告檔，不在 commit 前跑 smells_cmd 或 builtin（太慢，而且大小／熱點不是病形）。"""
    rows: List[Dict[str, Any]] = []
    by_root: Dict[str, List[Dict[str, Any]]] = {}
    for f in files:
        if f["new"] is None:
            continue
        root = find_root(os.path.dirname(f["abs"]))
        key = str(root)
        if key not in by_root:
            by_root[key] = []
            try:
                report = load_hub_cfg(root).get("smells_report")
                rp = (root / report) if report and not Path(str(report)).is_absolute() else (Path(str(report)) if report else None)
                if rp and rp.is_file():
                    by_root[key] = read_report(rp, 10 ** 6)[0]
            except SmellsError as e:
                notes.append(f"壞味道報告沒讀到：{e}")
        rel = os.path.relpath(f["abs"], str(root)).replace("\\", "/").lower()
        for r in by_root[key]:
            if str(r.get("path") or "").replace("\\", "/").strip().lower() == rel and r.get("reason"):
                rows.append({"name": str(r.get("category") or r.get("kind") or "報告"), "path": f["path"], "line": 0,
                             "text": str(r["reason"])})
    return rows


def check_commit(vcs: str, run_cwd: str, commit_tokens: List[str], adds: List[Tuple[str, List[str]]],
                 config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """PreToolUse commit 段的入口：一個 git／svn commit → classify 的結果（加上壞味道報告列）；不是 repo → None。"""
    files = (git_commit_files(run_cwd, commit_tokens, adds, config) if vcs == "git"
             else svn_commit_files(run_cwd, commit_tokens, config))
    if files is None:
        return None
    res = classify(files)
    res["checked"] = [f["path"] for f in files if f["new"] is not None]
    res["old"] += _report_rows(files, res["notes"])
    return res


def _clip(s: str, n: int = 120) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n] + "…"


def _where(h: Dict[str, Any]) -> str:
    return f"{h['path']} 第 {h['line']} 行" if h.get("line") else f"{h['path']}（整檔）"


def render_commit_report(results: List[Dict[str, Any]], repo_hint: str = "<repo>") -> Tuple[Optional[str], Optional[str]]:
    """多個 commit 的結果 → (擋的訊息, 只提醒的訊息)；有新寫進的病就只回擋的訊息（舊病與放行一起列在裡面）。"""
    new = [h for r in results for h in r["new"]]
    old = [h for r in results for h in r["old"]]
    allowed = [h for r in results for h in r["allowed"]]
    notes = list(dict.fromkeys(n for r in results for n in r["notes"]))
    if not (new or old or allowed or notes):
        return None, None
    lines: List[str] = []
    if new:
        lines.append(f"[Guardian:SmellGate] 這次要提交的程式新寫進了舊碼的病（{len(new)} 處），commit 已擋下。"
                     "下面每一行都是這次新增或改寫、而且提交前的舊版裡沒有同一行的程式：")
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for h in new:
            groups.setdefault(h["name"], []).append(h)
        for name, hs in groups.items():
            lines.append(f"  ✗ {name}：{hs[0]['why']}。怎麼改：{hs[0]['fix']}")
            lines += [f"      {_where(h)}：{_clip(h['text'])}" for h in hs[:8]]
            if len(hs) > 8:
                lines.append(f"      …另有 {len(hs) - 8} 處")
    else:
        lines.append("[Guardian:SmellGate] commit 前病形檢查：這次沒有新寫進的病。")
    if allowed:
        lines.append("寫了 smell-ok 理由放行的（理由跟著 diff 給使用者看）：")
        lines += [f"  · {h['name']}｜{_where(h)}：smell-ok：{h['reason']}" for h in allowed]
    if old:
        lines.append(f"舊碼原本就有、這次沒碰的（不擋，只列出；共 {len(old)} 處）：")
        lines += [f"  · {h['name']}｜{_where(h)}：{_clip(h['text'], 80)}" for h in old[:10]]
        if len(old) > 10:
            lines.append(f"  …另有 {len(old) - 10} 處")
    if notes:
        lines += [f"注意：{n}" for n in notes]
    if new:
        lines.append("處置：把 ✗ 那幾行改掉再 commit。判斷過確實該這樣寫（例如外部 API 只收這種寫法）→ 在那一行加註解 "
                     "`smell-ok: <為什麼>`，理由會留在 diff 裡給使用者看。手動重查："
                     f"python ~/.claude/tools/project-smells.py --commit-check --cwd {repo_hint}")
        return "\n".join(lines), None
    return None, "\n".join(lines)


def _commit_check_cli(cwd: str) -> int:
    config = _hub_inputs()[0]
    try:
        res = check_commit("git", cwd, ["commit"], [], config)
        if res is None:
            res = check_commit("svn", cwd, ["commit"], [], config)
    except SmellsError as e:
        print(f"error: {e}")
        print("SMELL_GATE_CHECK FAIL")
        return 1
    if res is None:
        print(f"error: {cwd} 不是 git repo 也不是 svn 工作副本")
        print("SMELL_GATE_CHECK FAIL")
        return 1
    deny, advice = render_commit_report([res], cwd)
    print(f"查了這次要提交的程式檔 {len(res['checked'])} 個：" + ("、".join(res["checked"][:20]) or "（無）"))
    print(deny or advice or "都沒有病形。")
    print("SMELL_GATE_CHECK " + ("FAIL" if deny else "PASS"))
    return 1 if deny else 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cwd", required=True, help="專案內任一路徑（往上找 .claude/overview-hub.json）")
    ap.add_argument("--part", help="部位名（過濾報告的 part 欄；builtin 以 <root>/<part> 當掃描範圍）；候選池模式必填")
    ap.add_argument("--top-n", type=int, default=None)
    ap.add_argument("--json", action="store_true", help="輸出 JSON（最後一行仍是哨兵）")
    ap.add_argument("--commit-check", action="store_true", help="照現在下 commit 會提交的內容查病形（尾行 SMELL_GATE_CHECK）")
    args = ap.parse_args(argv)
    if not Path(args.cwd).is_dir():
        print(f"PROJECT_SMELLS FAIL reason=cwd 不是目錄：{args.cwd}")
        return 1
    if args.commit_check:
        return _commit_check_cli(args.cwd)
    if not args.part:
        ap.error("候選池模式要給 --part")
    try:
        res = collect(args.cwd, args.part, args.top_n)
    except SmellsError as e:
        if args.json:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            print(f"error: {e}")
        print(f"PROJECT_SMELLS FAIL reason={str(e).splitlines()[0][:120]}")
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else render_text(res))
    print(f"PROJECT_SMELLS DONE n={len(res['rows'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
