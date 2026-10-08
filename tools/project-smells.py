#!/usr/bin/env python3
"""project-smells.py：把專案的壞味道報告變成「前 N 筆＋分類＋理由」候選池（給 MCP `project_smells` 與注入用）。

怎麼跑：
  python tools/project-smells.py --cwd <專案內任一路徑> --part <部位名> [--top-n 5] [--json]
  結果最後一行哨兵：PROJECT_SMELLS DONE n=<k>（失敗則 PROJECT_SMELLS FAIL reason=<...>，exit 1）

來源三選一（讀 `<專案根>/.claude/overview-hub.json`）：
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
import json
import os
import re
import shlex
import subprocess
import sys
import time
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


def find_root(cwd: str) -> Path:
    """最近的 `<root>/.claude/overview-hub.json`；沒有則最近的 .git／.svn；再沒有就 cwd 本身。"""
    start = Path(cwd).resolve()
    chain = [start] + list(start.parents)
    for p in chain:
        if (p / ".claude" / "overview-hub.json").is_file():
            return p
    for p in chain:
        if (p / ".git").exists() or (p / ".svn").exists():
            return p
    return start


def load_hub_cfg(root: Path) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CFG)
    hub = root / ".claude" / "overview-hub.json"
    if hub.is_file():
        try:
            data = json.loads(hub.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if k in DEFAULT_CFG})
        except (OSError, ValueError) as e:
            sys.stderr.write(f"[project-smells] overview-hub.json 讀取失敗（用預設）：{e}\n")
    if not isinstance(cfg.get("smells_category_map"), dict):
        cfg["smells_category_map"] = {}
    return cfg


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
    if not cmd.strip():
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
        return [p[i] for i in range(n.value)]
    finally:
        kernel32.LocalFree(p)


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


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cwd", required=True, help="專案內任一路徑（往上找 .claude/overview-hub.json）")
    ap.add_argument("--part", required=True, help="部位名（過濾報告的 part 欄；builtin 以 <root>/<part> 當掃描範圍）")
    ap.add_argument("--top-n", type=int, default=None)
    ap.add_argument("--json", action="store_true", help="輸出 JSON（最後一行仍是哨兵）")
    args = ap.parse_args(argv)
    if not Path(args.cwd).is_dir():
        print(f"PROJECT_SMELLS FAIL reason=cwd 不是目錄：{args.cwd}")
        return 1
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
