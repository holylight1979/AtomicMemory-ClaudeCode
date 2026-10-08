"""pack.py：第二意見的材料打包：把要審的東西複製進 job 的 materials/，算可重現的總雜湊。

做什麼：同一份材料不管來源行尾（CRLF／LF）、不管餵進來的順序，打包出來的 manifest.hash 都相同；
manifest 只記相對路徑，不含沙箱外的絕對路徑（replay-guard 的洩題規則）。

怎麼用（由 run.py prepare 呼叫；單獨跑只為除錯）：
    items = gather_items(request, cfg)                 # 從 cwd／part 蒐材料：卡、病灶前 N、diff、帳本尾 K、草稿
    manifest = pack_materials(job_dir, items, mode, model)
雜湊規則：每檔內容統一 LF → sha256；files 依 rel 排序；總雜湊 = sha256("rel\\nsha\\n" 逐檔串接)。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CLAUDE_DIR = Path(__file__).resolve().parents[2]
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

# 材料檔名固定（提示詞只引這些相對路徑）
REL_CARD = "card.md"
REL_DEFECTS = "defects.md"
REL_DIFF = "diff.patch"
REL_LEDGER = "ledger.jsonl"
REL_DRAFT = "draft.md"

_ABS_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]{1,2})")
_HEADING_RE = re.compile(r"^#{1,3}\s", re.MULTILINE)


class PackError(Exception):
    """材料相對路徑不合法或寫檔失敗。"""


def normalize_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalize_lf(text).encode("utf-8")).hexdigest()


def top_n_sections(text: str, n: int) -> str:
    """病灶文件取前 N 節：以「出現最多次的標題層級」當一節（通常是 ##；文件標題 # 留在前言）；不足兩節就整份回。"""
    text = normalize_lf(text)
    heads = list(_HEADING_RE.finditer(text))
    if len(heads) < 2 or n <= 0:
        return text
    by_level: Dict[int, int] = {}
    for m in heads:
        lvl = len(m.group(0).rstrip())
        by_level[lvl] = by_level.get(lvl, 0) + 1
    level = max(by_level, key=lambda k: (by_level[k], -k))
    starts = [m.start() for m in heads if len(m.group(0).rstrip()) == level]
    if len(starts) < 2:
        return text
    preamble = text[:starts[0]]
    cut = starts[n] if n < len(starts) else len(text)
    body = text[starts[0]:cut]
    note = "" if n >= len(starts) else f"\n\n（只取前 {n} 節，共 {len(starts)} 節）\n"
    return preamble + body + note


def tail_lines(text: str, k: int) -> str:
    lines = normalize_lf(text).rstrip("\n").split("\n")
    if k <= 0 or len(lines) <= k:
        return "\n".join(lines) + "\n"
    return "\n".join(lines[-k:]) + "\n"


def check_rel(rel: str) -> str:
    """相對路徑守門：禁絕對路徑、`..`、空段；統一正斜線。"""
    r = (rel or "").strip().replace("\\", "/")
    if not r or _ABS_RE.match(r) or any(seg in ("", "..") for seg in r.split("/")):
        raise PackError(f"材料路徑不合法（只收相對、不得含 ..）：{rel!r}")
    return r


def materials_hash(files: List[Dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for f in sorted(files, key=lambda x: x["rel"]):
        h.update(f"{f['rel']}\n{f['sha256']}\n".encode("utf-8"))
    return h.hexdigest()


def pack_materials(job_dir: Path, items: List[Tuple[str, str]], mode: str, model: str) -> Dict[str, Any]:
    """items=[(rel, text)] → 寫 materials/<rel>（LF）、寫 manifest.json、回 manifest。"""
    job_dir = Path(job_dir)
    mat = job_dir / "materials"
    mat.mkdir(parents=True, exist_ok=True)
    files: List[Dict[str, Any]] = []
    seen = set()
    for rel, text in items:
        r = check_rel(rel)
        if r in seen:
            raise PackError(f"材料重名：{r}")
        seen.add(r)
        body = normalize_lf(text if text is not None else "")
        dst = mat / r
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(body, encoding="utf-8", newline="\n")
        files.append({"rel": r, "sha256": sha256_text(body), "bytes": len(body.encode("utf-8"))})
    files.sort(key=lambda x: x["rel"])
    manifest = {
        "hash": materials_hash(files),
        "files": files,
        "mode": mode,
        "model": model,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (job_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def manifest_outside_paths(manifest: Dict[str, Any]) -> List[str]:
    """manifest 任何字串值裡出現磁碟絕對路徑就回報（不得含沙箱外路徑）。"""
    bad: List[str] = []

    def walk(v: Any) -> None:
        if isinstance(v, str):
            if re.search(r"[A-Za-z]:[\\/]", v) or v.startswith("//") or v.startswith("\\\\"):
                bad.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(manifest)
    return bad


# ─── 從專案蒐材料 ─────────────────────────────────────────────────────────────


def _read(p: Path) -> str:
    return normalize_lf(p.read_text(encoding="utf-8", errors="replace"))


def _run(cmd: List[str], cwd: str, timeout_s: int) -> str:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout if r.returncode == 0 else ""


def collect_diff(cwd: str, timeout_s: int = 20) -> str:
    """工作樹 vs HEAD；空則 main...HEAD；都不是 git 再試 svn diff。回空字串＝沒有差異或無版控。"""
    root = Path(cwd)
    if (root / ".git").exists() or _run(["git", "rev-parse", "--git-dir"], cwd, timeout_s).strip():
        out = _run(["git", "diff", "HEAD"], cwd, timeout_s)
        if not out.strip():
            out = _run(["git", "diff", "main...HEAD"], cwd, timeout_s)
        return out
    if (root / ".svn").exists():
        return _run(["svn", "diff"], cwd, timeout_s)
    return ""


def find_part_row(cwd: str, part: str) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
    """用 lib.overview_hub 找 `<root>/.claude/overview-map.md` 裡該部位的列；沒表或沒命中回 (root|None, None)。"""
    try:
        from lib.overview_hub import find_map, parse_map
    except ImportError:
        return None, None
    found = find_map(cwd)
    if not found:
        return None, None
    root, map_path = found
    want = (part or "").strip().lower()
    for row in parse_map(_read(map_path)):
        names = {str(row.get("part") or "").lower(), str(row.get("part_short") or "").lower()}
        if want and want in names:
            return root, row
    return root, None


def gather_items(request: Dict[str, Any], cfg: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], List[str]]:
    """request{cwd, part, mode, draft?, materials?{card,defects,diff,ledger,files[]}} → (items, notes)。

    materials 顯式指定的路徑優先（CLI／測試用）；否則從 overview-map 找卡與病灶文件、git/svn 取 diff、
    `<root>/.claude/verify/_ledger.jsonl` 取帳本尾 K。缺哪樣就在 notes 說，不靜默。
    """
    cwd = str(request.get("cwd") or "")
    part = str(request.get("part") or "")
    mode = str(request.get("mode") or "independent")
    spec = request.get("materials") or {}
    top_n = int(cfg.get("defects_top_n", 5))
    tail_k = int(cfg.get("ledger_tail", 20))
    items: List[Tuple[str, str]] = []
    notes: List[str] = []

    root, row = find_part_row(cwd, part) if cwd else (None, None)
    base = root or (Path(cwd) if cwd else None)

    card_src = spec.get("card")
    if not card_src and row and base is not None:
        try:
            from lib.overview_hub import resolve_card
            p = resolve_card(base, row.get("card"))
            card_src = str(p) if p else None
        except ImportError:
            card_src = None
    if card_src and Path(card_src).is_file():
        items.append((REL_CARD, _read(Path(card_src))))
    else:
        notes.append(f"找不到部位卡（part={part!r}）")

    defects_src = spec.get("defects") or (row or {}).get("defects_doc")
    if defects_src and base is not None and not Path(defects_src).is_absolute():
        defects_src = str(base / defects_src)
    if defects_src and Path(defects_src).is_file():
        items.append((REL_DEFECTS, top_n_sections(_read(Path(defects_src)), top_n)))
    else:
        notes.append("沒有病灶文件")

    diff_spec = spec.get("diff")
    if isinstance(diff_spec, dict) and "text" in diff_spec:
        diff_text = normalize_lf(str(diff_spec["text"]))
    elif diff_spec and Path(str(diff_spec)).is_file():
        diff_text = _read(Path(str(diff_spec)))
    else:
        diff_text = collect_diff(cwd, int(cfg.get("vcs_timeout_s", 20))) if cwd else ""
    if diff_text.strip():
        items.append((REL_DIFF, diff_text))
    else:
        notes.append("diff 為空（無改動或無版控）")

    ledger_src = spec.get("ledger") or (str(base / ".claude" / "verify" / "_ledger.jsonl") if base else None)
    if ledger_src and Path(ledger_src).is_file():
        items.append((REL_LEDGER, tail_lines(_read(Path(ledger_src)), tail_k)))
    else:
        notes.append("沒有驗證帳本")

    for extra in spec.get("files") or []:
        p = Path(str(extra))
        if p.is_file():
            items.append((f"files/{p.name}", _read(p)))
        else:
            notes.append(f"附加材料不存在：{extra}")

    if mode == "review":
        items.append((REL_DRAFT, normalize_lf(str(request.get("draft") or ""))))

    return items, notes
