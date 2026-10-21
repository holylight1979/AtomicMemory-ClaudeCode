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


_CODE_DIR = Path(__file__).resolve().parents[1]    # 本工具所在的 repo 根（檔案相對，不吃 HOME）


def find_root(cwd: str) -> Path:
    """專案根，與導讀卡端（hooks/wg_overview._lookup）、量尺帳本同一套：最近的部位表 `<root>/.claude/overview-map.md`
    （lib/overview_hub.find_map）就是專案根；祖先目錄的 overview-hub.json（公司覆蓋層）不改變專案身分，公司層另由
    merge_hub_cfg 取。沒有部位表的專案照舊：最近的 `.claude/overview-hub.json`，再來 .git／.svn，再沒有就 cwd 本身。"""
    start = Path(cwd).resolve()
    lib = str(_CODE_DIR / "lib")
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
    hooks = str(_CODE_DIR / "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    from wg_core import load_config, org_memory_root
    return load_config(), org_memory_root()


def load_hub_cfg(root: Path) -> Dict[str, Any]:
    """四層合併後的設定（lib/hub_config.merge_hub_cfg：預設 < config.json overview_hub < 公司根 < 專案根 overview-hub.json），
    只取本工具要的鍵（DEFAULT_CFG）。設定有錯（未知鍵、型別錯，與導讀卡端同一套驗證）→ SmellsError，不悄悄用預設。"""
    lib = str(_CODE_DIR / "lib")
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
# 病形兩種來源：內建（原設計者點名的匿名函式疊用與過長、回呼套層、lambda 指派、巢狀過深、巢狀三元、過度物件化、Unity 每幀
# 浪費；寫得保守，寧漏不誤擋，依據見 workflow/inbox/from-track-g2/002 提案）與專案部位表「病灶清單」欄指的病灶文件（每條 `shape:`
# 是專案判斷過的病）。形狀判不準（大括號語言的字串、註解剝不乾淨）或還在提醒區間的只列不擋；「判不了一律擋」只用在查不到
# 這次要提交什麼。那一行寫 `smell-ok: <理由>` → 不擋、列進放行清單（判斷交 AI、理由留在 diff）。

SHAPES: Dict[str, Tuple[str, str, str]] = {   # 規則 → (病名, 為什麼是病, 怎麼改)
    "anon-stack": ("匿名函式疊用", "匿名函式裡再套匿名函式（同一行裡套、或 Python 的 lambda 套 lambda），讀的人要同時在腦中展開好幾層",
                   "把內層抽成有名字的函式"),
    "anon-nest": ("匿名回呼套三層以上", "回呼裡再套回呼到第三層，流程被拆進一層層沒名字的函式，讀的人要拐好幾個彎才看得到先後",
                  "每層抽成有名字的函式，或改成直線的 async／await 流程"),
    "one-method-class": ("只有建構子加一個方法的類別", "類別只是把一個函式包起來（過度物件化），多一層建構與 self，沒換到任何狀態管理",
                         "直接寫成函式，建構參數改成函式參數"),
    "anon-long": ("匿名函式本體過長", "一整段邏輯塞進沒名字的回呼／lambda／匿名類別，讀外層流程時要跳進去讀完才回得來",
                  "抽成有名字的函式或類別，回呼只留一行呼叫"),
    "lambda-assign": ("lambda 指派給變數", "把 lambda 存進變數就失去它唯一的好處（嵌在運算式裡），還讓錯誤追蹤看不到函式名（PEP 8）",
                      "改寫成 def"),
    "deep-nesting": ("控制結構巢狀太深", "if／for／while／try 一層套一層，讀的人要同時記住每一層的條件",
                     "先踢掉例外情況提早 return／continue，或把內層抽成有名字的函式"),
    "nested-ternary": ("巢狀三元", "三元運算裡再套三元，一行裡要同時解好幾個條件分支", "改成 if／elif 或查表"),
    "unity-empty-message": ("空的 Unity 訊息方法", "空的 Update() 等方法 Unity 每幀照樣呼叫，白耗效能", "刪掉這個空方法"),
    "unity-hot-lookup": ("每幀方法裡做昂貴查找", "在 Update 這類每幀都跑的方法裡做 Find／AddComponent／反射，每幀都付一次查找或配置的成本",
                         "移到 Awake／Start 查一次存起來；真的要每幀查就先判 null 只在第一次查"),
}
# 門檻預設值（可由 workflow/config.json 的 guard.smell_gate 覆蓋）：匿名本體 >20 行擋、≥10 行提醒取自 Sonar S1188（匿名類別 20 行）
# 與 S5612／Checkstyle LambdaBodyLength（10 行）；巢狀 ≥4 層取自寫碼規矩「巢狀 ≥4 一律重構」與 Sonar S134（Python 4）
DEFAULT_LIMITS: Dict[str, int] = {"anon_body_block_lines": 20, "anon_body_list_lines": 10, "nesting_block_depth": 4}
_PY_EXTS = (".py", ".pyw")
_ARROW_ANON = r"=>|\bfunction\s*\(|\bdelegate\s*(?=[({])"
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


_MEMBER_ARROW_RE = re.compile(   # C#「型別 名稱 =>」「型別 名稱(參數) =>」是運算式主體的成員，不是 lambda
    r"^\s*(?:(?:public|private|protected|internal|static|override|virtual|abstract|sealed|new|async|readonly|unsafe|extern)\s+)*"
    r"[\w.]+(?:<[^=]*>)?(?:\[\])?\??\s+[A-Za-z_]\w*\s*(?:\([^()]*\))?\s*$")


def _anon_tokens(line: str, anon_re: "re.Pattern[str]") -> List["re.Match[str]"]:
    """這行的匿名函式記號。有 switch 的行（C#／Java switch 運算式的 `=>`／`->` 是分支不是函式）只認 function／delegate；
    行首就是「型別 名稱 =>」的那個 `=>` 是運算式主體的屬性或方法，不算。"""
    found = list(anon_re.finditer(line))
    if _SWITCH_RE.search(line):
        found = [m for m in found if m.group(0) not in ("=>", "->")]
    return [m for m in found if not (m.group(0) == "=>" and _MEMBER_ARROW_RE.match(line[:m.start()]))]


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


_TEST_CALLBACK_RE = re.compile(r"\b(?:describe|it|test|context|suite|beforeEach|afterEach|beforeAll|afterAll)"
                               r"(?:\.\w+)?\s*\((?:[^()]|\([^()]*\))*$")
_PROMISE_CALLBACK_RE = re.compile(r"\.\s*(?:then|catch|finally)\s*\(\s*$")
_JAVA_ANON_CLASS_RE = re.compile(r"\bnew\s+[A-Za-z_][\w.]*(?:<[^>]*>)?\s*\([^()]*\)\s*$")
_WORD_RE = re.compile(r"[A-Za-z_]\w*")


def _brace_map(lines: List[str]) -> Tuple[Dict[Tuple[int, int], int], bool]:
    """剝過字串與註解的各行 → ({開大括號 (行, 欄): 對應收大括號的行}, 剝得乾不乾淨)。大括號或小括號對不上 ＝ 有字串、註解、
    正則字面值沒剝乾淨，大括號類病形判不準。"""
    ends: Dict[Tuple[int, int], int] = {}
    stack: List[Tuple[int, int]] = []
    parens = 0
    clean = True
    for no, line in enumerate(lines, 1):
        for m in re.finditer(r"[{}()]", line):
            ch = m.group(0)
            if ch == "{":
                stack.append((no, m.start()))
            elif ch == "}" and stack:
                ends[stack.pop()] = no
            elif ch == "}":
                clean = False
            else:
                parens += 1 if ch == "(" else -1
    return ends, clean and not stack and parens == 0


def _anon_params(line: str, m: "re.Match[str]") -> set:
    """匿名函式的參數名（`function (a, b)`、`(a, b) =>`、`a =>`、`delegate (int x)`、Java `(a) ->`）。"""
    if m.group(0) in ("=>", "->"):
        before = line[:m.start()].rstrip()
        got = re.search(r"\(([^()]*)\)$", before) or re.search(r"([A-Za-z_]\w*)$", before)
    else:
        got = re.match(r"[^(]*\(([^()]*)\)", line[m.start():])
    if not got:
        return set()
    names = set()
    for part in got.group(1).split(","):
        words = _WORD_RE.findall(part.split("=")[0])
        if words:
            names.add(words[-1])
    return names


def _span_text(lines: List[str], start: Tuple[int, int], end_line: int) -> str:
    """從 (行, 欄) 開的大括號到 end_line 那行為止的程式文字。"""
    no, col = start
    return "\n".join([lines[no - 1][col:]] + lines[no:end_line])


def _anon_frame(line: str, m: "re.Match[str]", no: int) -> Dict[str, Any]:
    """匿名函式記號 → 它的一層：參數、是不是測試框架的回呼（describe／it…）、是不是 promise 的 then／catch 回呼。
    箭頭函式的參數寫在記號前面，判它被誰呼叫要先把參數那段剝掉。"""
    prefix = line[:m.start()]
    if m.group(0) in ("=>", "->"):
        prefix = re.sub(r"(?:\([^()]*\)|[A-Za-z_]\w*)\s*$", "", prefix)
    return {"anon": True, "line": no, "params": _anon_params(line, m),
            "test_cb": bool(_TEST_CALLBACK_RE.search(prefix)), "then_cb": bool(_PROMISE_CALLBACK_RE.search(prefix))}


def _brace_hits(text: str, ext: str, limits: Dict[str, int], is_test: bool) -> Tuple[List[Dict[str, Any]], bool]:
    """大括號語言 → (命中, 剝得乾不乾淨)。同一行匿名函式套匿名函式（anon-stack）；匿名函式本體跨行套到第三層（anon-nest，錨在
    第三層開頭那行）；匿名本體行數（anon-long，超過擋的門檻擋、到提醒門檻只列）。測試框架的回呼（describe／it…）不算一層、
    不量長度；promise 的 then／catch 回呼用到外層回呼的參數也不算一層（eslint-plugin-promise no-nesting 同一判法）。"""
    pattern = _ANON_BY_EXT.get(ext)
    if not pattern:
        return [], True
    anon_re = re.compile(pattern)
    token_re = re.compile(pattern + r"|[{};]")
    lines = _code_lines(text, ext)
    ends, clean = _brace_map(lines)
    hits: List[Dict[str, Any]] = []
    frames: List[Dict[str, Any]] = []      # 每個還開著的 {：是不是匿名本體、算不算一層、參數
    state: Dict[str, Any] = {"pending": None, "depth": 0}    # 看到匿名記號、還在等它的 {；目前算到第幾層

    def counts(frame: Dict[str, Any], body: str) -> bool:
        if frame["test_cb"]:
            return False
        outer = set().union(*(f["params"] for f in frames if f["anon"]))    # 還在作用域裡的所有外層匿名函式參數
        return not (frame["then_cb"] and any(re.search(rf"\b{re.escape(p)}\b", body) for p in outer))

    def open_brace(no: int, col: int) -> None:
        frame = state["pending"] or {"anon": False}
        if not state["pending"] and ext == ".java" and _JAVA_ANON_CLASS_RE.search(lines[no - 1][:col]):
            frame = {"anon": True, "line": no, "params": set(), "test_cb": False, "then_cb": False}
        state["pending"] = None
        end = ends.get((no, col))
        frame["counts"] = frame["anon"] and counts(frame, _span_text(lines, (no, col), end or no))
        frames.append(frame)
        state["depth"] += frame["counts"]
        if frame["counts"] and state["depth"] >= NEST_LIMIT:
            hits.append({"rule": "anon-nest", "line": no})
        body = (end - no - 1) if end else 0
        if not frame["anon"] or frame["test_cb"] or is_test or body < limits["anon_body_list_lines"]:
            return
        hits.append({"rule": "anon-long", "line": frame["line"], "start": frame["line"], "end": end,
                     "detail": f"本體 {body} 行（超過 {limits['anon_body_block_lines']} 行擋）",
                     "list_only": body <= limits["anon_body_block_lines"],
                     "ckey": ("anon-long", _squash(lines[frame["line"] - 1])), "cval": body,
                     "legacy_over": limits["anon_body_block_lines"]})

    def anon_token(no: int, line: str, m: "re.Match[str]") -> None:
        frame = _anon_frame(line, m, no)
        rest = line[m.end():].lstrip()
        if m.group(0) not in ("=>", "->") or not rest or rest.startswith("{"):
            state["pending"] = frame
            return
        if counts(frame, rest) and state["depth"] + 1 >= NEST_LIMIT:    # 表達式本體的匿名函式：自己算一層，不開大括號
            hits.append({"rule": "anon-nest", "line": no})

    for no, line in enumerate(lines, 1):
        if _nested_on_line(line, anon_re):
            hits.append({"rule": "anon-stack", "line": no})
        anon_here = {m.start() for m in _anon_tokens(line, anon_re)}
        for m in token_re.finditer(line):
            t = m.group(0)
            if t == "{":
                open_brace(no, m.start())
            elif t == "}" and frames:
                state["depth"] -= frames.pop()["counts"]
                state["pending"] = None
            elif t in ("}", ";"):
                state["pending"] = None
            elif m.start() in anon_here:
                anon_token(no, line, m)
    return hits, clean


_UNITY_MESSAGE_RE = re.compile(
    r"^\s*(?P<mods>(?:(?:public|private|protected|internal|static|override|virtual|abstract|sealed|new|async|unsafe)\s+)*)"
    r"(?:void|IEnumerator)\s+(?P<name>Awake|Start|Update|FixedUpdate|LateUpdate|OnGUI|OnEnable|OnDisable|OnDestroy|"
    r"OnApplicationQuit|OnApplicationPause|OnApplicationFocus|Reset|OnValidate|OnDrawGizmos|OnDrawGizmosSelected)\s*\(\s*\)")
_PER_FRAME = {"Update", "FixedUpdate", "LateUpdate", "OnGUI"}
_HOT_LOOKUP_RE = re.compile(
    r"\bGameObject\s*\.\s*Find\w*\s*\(|\bFind(?:Objects?|AnyObject|FirstObject)\w*\s*[<(]|\bAddComponent\s*[<(]|"
    r"\bSystem\s*\.\s*Reflection\b|\.\s*Get(?:Method|Property|Field)s?\s*\(|\bActivator\s*\.\s*CreateInstance\b")
_NULL_GUARD_RE = re.compile(r"\?\?=|\bif\s*\(\s*(?:!\s*[\w.]+|[\w.]+\s*==\s*null|null\s*==\s*[\w.]+)\s*\)")
_DERIVED_CLASS_RE = re.compile(r"\bclass\s+\w+(?:<[^>]*>)?\s*:\s*\w")
_UNITY_FILE_RE = re.compile(r"\bUnityEngine\b")


_EDITOR_FLIP = {"editor": "player", "player": "editor", "other": "other"}


def _editor_only_lines(raw_lines: List[str]) -> set:
    """只在編輯器裡跑的行號：`#if UNITY_EDITOR` 那段、`#if !UNITY_EDITOR` 的 #else 段（巢狀 #if 照層數配對）。
    其他條件、#elif 一律當不確定（不算編輯器限定，照查）。"""
    out, stack = set(), []
    for no, raw in enumerate(raw_lines, 1):
        s = " ".join(raw.split())
        if s.startswith("#if "):
            stack.append({"#if UNITY_EDITOR": "editor", "#if !UNITY_EDITOR": "player"}.get(s, "other"))
        elif s.startswith("#elif") and stack:
            stack[-1] = "other"
        elif s.startswith("#else") and stack:
            stack[-1] = _EDITOR_FLIP[stack[-1]]
        elif s.startswith("#endif") and stack:
            stack.pop()
        elif "editor" in stack:
            out.add(no)
    return out


def _brace_header(lines: List[str], open_line: int) -> str:
    """大括號開頭那行；C# 慣用換行大括號（那行只有 `{`）就往上找到條件那一行。"""
    at = open_line
    while at > 1 and lines[at - 1].strip() in ("{", ""):
        at -= 1
    return lines[at - 1] + lines[open_line - 1]


def _unity_hits(text: str) -> List[Dict[str, Any]]:
    """C#（Unity）：空的訊息方法（virtual／override／abstract 是留給子類別的，不算；所在檔要有繼承別的類別）、
    每幀方法（Update 系列）本體裡直接做 Find／AddComponent／反射（先判 null 只在第一次查的寫法、UNITY_EDITOR 區段不算）。
    檔裡沒用到 UnityEngine 就不是 Unity 腳本（伺服器的模組類別也常有 Update()），整檔不查。"""
    lines = _code_lines(text, ".cs")
    if not (_UNITY_FILE_RE.search(text) and _DERIVED_CLASS_RE.search("\n".join(lines))):
        return []
    ends, _clean = _brace_map(lines)
    editor_only = _editor_only_lines(text.splitlines())
    opens = sorted(ends)
    hits: List[Dict[str, Any]] = []
    for no, line in enumerate(lines, 1):
        msg = _UNITY_MESSAGE_RE.match(line)
        if not msg:
            continue
        body_open = next(((l, c) for l, c in opens if (l, c) > (no, msg.end()) and l <= no + 2), None)
        if body_open is None:
            continue
        close = ends[body_open]
        body = _span_text(lines, body_open, close)[1:].rsplit("}", 1)[0]
        if not body.strip() and not re.search(r"\b(?:virtual|override|abstract)\b", msg.group("mods")):
            hits.append({"rule": "unity-empty-message", "line": no, "start": no, "end": close})
        if msg.group("name") in _PER_FRAME:
            hits += _hot_lookups(lines, ends, opens, body_open, editor_only)
    return hits


def _hot_lookups(lines: List[str], ends: Dict[Tuple[int, int], int], opens: List[Tuple[int, int]],
                 body_open: Tuple[int, int], editor_only: set) -> List[Dict[str, Any]]:
    """每幀方法本體裡直接做昂貴查找的行；這一行、上一行、或包住它的那個大括號開頭是「先判 null」就是延遲快取，不算。"""
    hits = []
    for at in range(body_open[0], ends[body_open] + 1):
        if at in editor_only or not _HOT_LOOKUP_RE.search(lines[at - 1]):
            continue
        inner = max(((l, c) for l, c in opens if (l, c) > body_open and l < at <= ends[(l, c)]), default=None)
        guards = [lines[at - 1], lines[at - 2] if at >= 2 else "", _brace_header(lines, inner[0]) if inner else ""]
        if not any(_NULL_GUARD_RE.search(g) for g in guards):
            hits.append({"rule": "unity-hot-lookup", "line": at})
    return hits


def _one_method_class(node: ast.ClassDef) -> bool:
    """沒繼承、沒裝飾、本體只有 __init__ 加一個方法（其餘只有 docstring／pass）。有繼承的多半是框架要求，不算。"""
    if node.decorator_list or node.keywords or any(not (isinstance(b, ast.Name) and b.id == "object") for b in node.bases):
        return False
    funcs = [s.name for s in node.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))]
    others = [s for s in node.body if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Pass))
              and not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    return not others and len(funcs) == 2 and "__init__" in funcs and not any(f.startswith("__") and f != "__init__" for f in funcs)


_NEST_NODES = tuple(getattr(ast, n) for n in ("If", "For", "AsyncFor", "While", "Try", "TryStar", "Match") if hasattr(ast, n))
_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _nest_depth(node: ast.AST, depth: int = 0) -> int:
    """函式本體裡控制結構最深套幾層；elif 跟 if 同一層，內層函式、類別、lambda 各自另算。"""
    best = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPE_NODES):
            continue
        is_elif = isinstance(node, ast.If) and isinstance(child, ast.If) and node.orelse == [child]
        best = max(best, _nest_depth(child, depth + (isinstance(child, _NEST_NODES) and not is_elif)))
    return best


def _functions(node: ast.AST, prefix: str = "") -> List[Tuple[str, ast.AST]]:
    """所有函式（含類別方法、內層函式）與它的完整名稱（類別.方法）。"""
    out: List[Tuple[str, ast.AST]] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((prefix + child.name, child))
            out += _functions(child, prefix + child.name + ".")
        elif isinstance(child, ast.ClassDef):
            out += _functions(child, prefix + child.name + ".")
        else:
            out += _functions(child, prefix)
    return out


def _py_hits(text: str, is_test: bool, limits: Dict[str, int]) -> Optional[List[Dict[str, Any]]]:
    """Python 用語法樹判（字串、註解裡的字不會算）。同一行並列的 lambda（dict 裡一排替身）不算。語法錯回 None（判不了，由呼叫端記一筆）。
    - lambda 套 lambda：錨在內層，範圍是外層整段。
    - 單方法類別、lambda 指派給變數：測試檔不查（替身就長這樣）；except 區塊裡的 lambda 指派是載入失敗時的替身，不算。
    - 巢狀三元：只報最外層。
    - 巢狀太深：函式級指標，帶 ckey／cval（同名函式改前改後比深度，沒變深就算舊病）。"""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    in_except = set()
    for handler in ast.walk(tree):
        if isinstance(handler, ast.ExceptHandler):
            in_except.update(id(n) for n in ast.walk(handler))
    hits: List[Dict[str, Any]] = []
    inner_ternaries = set()
    for node in ast.walk(tree):
        span = {"start": node.lineno, "end": node.end_lineno or node.lineno} if hasattr(node, "lineno") else {}
        if isinstance(node, ast.Lambda):
            inner = next((n for n in ast.walk(node.body) if isinstance(n, ast.Lambda)), None)
            if inner is not None:
                hits.append({"rule": "anon-stack", "line": inner.lineno, **span})
        elif isinstance(node, ast.ClassDef) and not is_test and _one_method_class(node):
            hits.append({"rule": "one-method-class", "line": node.lineno, **span})
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Lambda):
            if not is_test and id(node) not in in_except:
                hits.append({"rule": "lambda-assign", "line": node.lineno, **span})
        elif isinstance(node, ast.IfExp) and id(node) not in inner_ternaries:
            inner = [n for n in ast.walk(node) if n is not node and isinstance(n, ast.IfExp)]
            inner_ternaries.update(id(n) for n in inner)
            if inner:
                hits.append({"rule": "nested-ternary", "line": node.lineno, **span})
    limit = limits["nesting_block_depth"]
    for qualname, func in _functions(tree):
        depth = _nest_depth(func)
        if depth >= limit:
            hits.append({"rule": "deep-nesting", "line": func.lineno, "start": func.lineno, "end": func.end_lineno or func.lineno,
                         "ckey": ("deep-nesting", qualname), "cval": depth,
                         "detail": f"{qualname} 巢狀 {depth} 層（{limit} 層以上擋）"})
    return hits


def limits_of(config: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """workflow/config.json 的 guard.smell_gate 覆蓋門檻預設值；不是正整數的設定照預設。"""
    sec = ((config or {}).get("guard") or {}).get("smell_gate") or {}
    out = dict(DEFAULT_LIMITS)
    for key in out:
        value = sec.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            out[key] = value
    return out


def _is_test_file(abs_path: str) -> bool:
    """跟寫碼查核同一份測試檔定義（hooks/wg_verify_ledger 的 verify_case_globs 預設）。"""
    hooks = str(_CODE_DIR / "hooks")
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
    lib = str(_CODE_DIR / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    from overview_hub import find_map, match_row, parse_map, unread_rows_note
    found = find_map(abs_path)
    if not found:
        return []
    root, map_path = found
    key = str(map_path)
    if key not in cache:
        cache[key] = parse_map(map_path.read_text(encoding="utf-8", errors="replace"))
    row = match_row(abs_path, root, cache[key], anchored=True)
    if row is None:                 # 對不到部位：可能是表的寫法讓整列沒讀到，不能靜默當成沒有病灶清單
        note = unread_rows_note(map_path)
        if note:
            notes.append(note)
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


def scan_text(abs_path: str, text: str, cache: Dict[str, Any], notes: List[str],
              limits: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    """一個檔的一個版本 → 病形命中 [{rule, name, why, fix, line, start, end, text, detail?, list_only?, ckey?, cval?}]：
    line 是點名的那一行，start～end 是整個病形的範圍（改到範圍裡任一行，都算這次碰到這個病形）；list_only＝判不準或在提醒區間，
    只列不擋；ckey／cval＝函式級指標（同名函式改前改後比大小）。大括號語言的字串、註解剝不乾淨時，整檔的內建病形都只列不擋。"""
    limits = limits or DEFAULT_LIMITS
    ext = Path(abs_path).suffix.lower()
    lines = text.splitlines()
    is_test = _is_test_file(abs_path)
    if ext in _PY_EXTS:
        found = _py_hits(text, is_test, limits)
        if found is None:
            notes.append(f"{Path(abs_path).name} 有語法錯，內建病形沒查（語法樹建不起來）")
            found = []
    else:
        found, clean = _brace_hits(text, ext, limits, is_test)
        if ext == ".cs":
            found += _unity_hits(text)
        if not clean and found:
            notes.append(f"{Path(abs_path).name} 的字串或註解剝不乾淨（正則字面值、跨行字串之類），大括號類病形判不準，這個檔只提醒不擋")
            for f in found:
                f["list_only"] = True
    hits = []
    seen = set()
    for f in found:
        if (f["rule"], f["line"]) in seen:
            continue
        seen.add((f["rule"], f["line"]))
        if "ckey" in f:     # 函式級與長度級指標只跟同一個檔的同一處比（別的檔的同名函式不能抵）
            f["ckey"] = (abs_path, *f["ckey"])
        name, why, fix = SHAPES[f["rule"]]
        no = f["line"]
        hits.append({"start": no, "end": no, **f, "name": name, "why": why, "fix": fix,
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


def classify(files: List[Dict[str, Any]], cache: Optional[Dict[str, Any]] = None,
             limits: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """files：[{path（顯示用）, abs, old, new}]；new 為 None＝這次刪掉的檔（只拿舊版當「原本就有」的比對來源）。
    回 {new, listed, old, allowed, notes}：new＝新寫進的病（擋）、listed＝新寫進但判不準或在提醒區間（只列）、
    old＝舊碼原本就有或原樣搬動、allowed＝寫了 smell-ok 理由放行的。
    新舊對帳一份抵一份：所有提交檔舊版裡每個（規則, 點名那行）各有幾份；範圍沒被碰到的病先各抵掉一份，碰到的再拿剩下的抵，
    抵得到＝原樣搬動，抵不到＝新寫進的（原行保留又複製一份，多的那份抵不到）。函式級指標（巢狀深度）另用同名函式改前改後比：
    改後沒有比改前大＝舊病。"""
    cache = {} if cache is None else cache
    notes: List[str] = []
    before: Dict[Tuple[str, str], int] = {}
    before_val: Dict[Any, int] = {}
    for f in files:
        for h in scan_text(f["abs"], f["old"], cache, [], limits) if f["old"] else []:
            if "ckey" in h:
                before_val[h["ckey"]] = max(before_val.get(h["ckey"], 0), h["cval"])
                continue
            key = (h["rule"], _squash(h["text"]))
            before[key] = before.get(key, 0) + 1
    res: Dict[str, Any] = {"new": [], "listed": [], "old": [], "allowed": [], "notes": notes}
    touched_hits = []
    for f in files:
        if f["new"] is None:
            continue
        touched = changed_lines(f["old"] or "", f["new"])
        for h in scan_text(f["abs"], f["new"], cache, notes, limits):
            h["path"] = f["path"]
            key = (h["rule"], _squash(h["text"]))
            if not touched.isdisjoint(range(h["start"], h["end"] + 1)):
                touched_hits.append((key, h))
                continue
            if "ckey" not in h:
                before[key] = max(0, before.get(key, 0) - 1)
            res["old"].append(h)
    for key, h in touched_hits:
        prev = before_val.get(h.get("ckey"))
        if prev is not None and (h["cval"] <= prev or prev > h.get("legacy_over", float("inf"))):
            res["old"].append(h)    # 沒變嚴重；或舊版本來就過了擋的門檻（舊病，只列）
            continue
        if "ckey" not in h and before.get(key, 0) > 0:
            before[key] -= 1
            res["old"].append(h)
            continue
        ok = _SMELL_OK_RE.search(h["text"])
        if ok and len(ok.group(1)) >= 2:
            h["reason"] = ok.group(1)
            res["allowed"].append(h)
            continue
        res["listed" if h.get("list_only") else "new"].append(h)
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
    hooks = str(_CODE_DIR / "hooks")
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


def svn_commit_args(commit_tokens: List[str]) -> Tuple[List[str], List[str], List[str]]:
    """`svn commit …` 的 tokens（tokens[0]＝commit）→ (路徑, 照樣帶進 svn status 的範圍選項, --targets 清單檔)。"""
    paths: List[str] = []
    scope: List[str] = []
    targets: List[str] = []
    it = _not_args(commit_tokens[1:])
    for t in it:
        name, eq, val = t.partition("=")
        if name in _SVN_SCOPE_FLAGS:
            scope += [name, val if eq else next(it, "")]
        elif name == "--targets":
            targets.append(val if eq else next(it, ""))
        elif name in _SVN_VALUE_FLAGS:
            if not eq:
                next(it, None)
        elif not t.startswith("-"):
            paths.append(t)
    return paths, scope, targets


def svn_commit_files(run_cwd: str, commit_tokens: List[str], config: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """這次 svn commit 會提交的程式檔：`svn status` 的修改、新增、取代（BASE 當舊版）；刪除的只當舊版比對來源。
    提交範圍選項（--depth、--changelist、--targets 清單檔）照樣套到 status。不是工作副本 → None。"""
    paths, scope, targets = svn_commit_args(commit_tokens)
    for name in targets:
        try:
            text = (Path(run_cwd) / name).read_text(encoding="utf-8")
        except OSError as e:
            raise SmellsError(f"svn commit --targets 的清單檔讀不到（{e}），病形檢查判不了") from e
        paths += [ln.strip() for ln in text.splitlines() if ln.strip()]
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
    res = classify(files, limits=limits_of(config))
    res["checked"] = [f["path"] for f in files if f["new"] is not None]
    res["old"] += _report_rows(files, res["notes"])
    return res


def _clip(s: str, n: int = 120) -> str:
    s = s.strip()
    return s if len(s) <= n else s[:n] + "…"


def _where(h: Dict[str, Any]) -> str:
    return f"{h['path']} 第 {h['line']} 行" if h.get("line") else f"{h['path']}（整檔）"


def _shown(h: Dict[str, Any], n: int = 120) -> str:
    """擋訊息裡那一行的樣子：原文，加上量出來的細節（幾層、幾行）。"""
    return _clip(h["text"], n) + (f"（{h['detail']}）" if h.get("detail") else "")


def render_commit_report(results: List[Dict[str, Any]], repo_hint: str = "<repo>") -> Tuple[Optional[str], Optional[str]]:
    """多個 commit 的結果 → (擋的訊息, 只提醒的訊息)；有新寫進的病就只回擋的訊息（只提醒、舊病、放行一起列在裡面）。"""
    new = [h for r in results for h in r["new"]]
    listed = [h for r in results for h in r.get("listed", [])]
    old = [h for r in results for h in r["old"]]
    allowed = [h for r in results for h in r["allowed"]]
    notes = list(dict.fromkeys(n for r in results for n in r["notes"]))
    if not (new or listed or old or allowed or notes):
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
            lines += [f"      {_where(h)}：{_shown(h)}" for h in hs[:8]]
            if len(hs) > 8:
                lines.append(f"      …另有 {len(hs) - 8} 處")
    else:
        lines.append("[Guardian:SmellGate] commit 前病形檢查：這次沒有新寫進的病。")
    if listed:
        lines.append("這次新寫、只提醒不擋的（形狀判不準，或還在提醒區間沒到擋的門檻）：")
        lines += [f"  · {h['name']}｜{_where(h)}：{_shown(h, 80)}" for h in listed[:10]]
    if allowed:
        lines.append("寫了 smell-ok 理由放行的（理由跟著 diff 給使用者看）：")
        lines += [f"  · {h['name']}｜{_where(h)}：smell-ok：{h['reason']}" for h in allowed]
    if old:
        lines.append(f"舊碼原本就有的（這次沒碰、原樣搬動、或碰了但沒變嚴重；不擋，只列出；共 {len(old)} 處）：")
        lines += [f"  · {h['name']}｜{_where(h)}：{_shown(h, 80)}" for h in old[:10]]
        if len(old) > 10:
            lines.append(f"  …另有 {len(old) - 10} 處")
    if notes:
        lines += [f"注意：{n}" for n in notes]
    if new:
        lines.append("處置先分清被點名的檔是不是你這次改的：是你改的 → 把 ✗ 那幾行改掉再 commit；判斷過確實該這樣寫"
                     "（例如外部 API 只收這種寫法）→ 在那一行加註解 `smell-ok: <為什麼>`，理由會留在 diff 裡給使用者看。"
                     "不是你改的（session 開始前就在暫存區、別人留的）→ 不修、不動它的暫存，只提交你自己的檔"
                     "（git：git commit -- <你的檔>），被問到時寫明是誰的、病要誰修。手動重查："
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
