"""overview_hub — 「第一次改某部位的檔之前，整張注入該部位導讀卡」的查表與判定（純函式）。

做什麼：專案在 `<專案根>/.claude/overview-map.md` 放一張「路徑前綴 → 部位 → 導讀卡」表（專案自己寫，
根層只讀）。hook 碰到 Read／Edit／提示詞裡的路徑時，往上找最近的那張表，用最長前綴命中決定部位，
把導讀卡整張原文組成注入文字；Edit 前再查 AI 有沒有在回覆裡交出「定位三行」。

表格式（兩個專案各自的寫法都吃）：markdown 表格，每列至少有一格含反引號路徑（前綴）、緊接的一格是部位名、
某格含反引號的卡名（無路徑分隔符）、某格以「有／部分／索引／無」開頭當狀態；「同上」「同第 N 列」沿用別列的卡。

定位三行（AI 在回覆裡寫的）：
    定位｜部位：<部位>——這次改的是哪一塊
    定位｜根因層：修根因還是症狀；根因在哪層
    定位｜前例：這個部位以前摔過什麼
"""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAP_REL = ".claude/overview-map.md"
LOCATE_RE = re.compile(r"^\s*定位\s*[｜|]\s*(部位|根因層?|前例)\s*[:：]\s*(.+)$", re.MULTILINE)
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_SAME_ROW_RE = re.compile(r"同第\s*(\d+)\s*列")
_STATUS_HEADS = ("有", "部分", "索引", "無")
# bypass 模式下讀檔走 Bash：cat / head / tail / sed -n / less 後面的路徑也算 Read
_BASH_READ_RE = re.compile(
    r'(?:^|[;&|(]\s*)(?:cat|head|tail|less|sed\s+-n\s+\S+)\s+(?:-[a-zA-Z0-9]+\s+)*"?([^"\s;|&)]+)"?'
)


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip().lower()


# ─── 找表 ───────────────────────────────────────────────────────────

def find_map(path: str) -> Optional[Tuple[Path, Path]]:
    """從 path 往上找最近的 `<root>/.claude/overview-map.md`；回 (root, map_path)，沒有回 None。"""
    if not path:
        return None
    try:
        cur = Path(path)
        if not cur.is_absolute():
            return None
        cur = cur if cur.is_dir() else cur.parent
    except OSError:
        return None
    while True:
        cand = cur / MAP_REL
        try:
            if cand.is_file():
                return (cur, cand)
        except OSError:
            return None
        if cur.parent == cur:
            return None
        cur = cur.parent


# ─── 解析表 ─────────────────────────────────────────────────────────

def _is_path_token(tok: str) -> bool:
    return ("/" in tok or "\\" in tok) and not tok.startswith("http")


def _is_card_token(tok: str) -> bool:
    return not _is_path_token(tok) and "*" not in tok and not tok.endswith((".cs", ".ps1", ".md", ".json"))


def parse_map(text: str) -> List[Dict[str, Any]]:
    """表 → rows：[{prefixes, part, part_short, card, status, line}]。前綴已正規化（小寫、/、去尾斜線）。"""
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or all(set(c) <= set("-: ") for c in cells):
            continue
        prefix_idx = next(
            (i for i, c in enumerate(cells) if any(_is_path_token(t) for t in _BACKTICK_RE.findall(c))),
            None,
        )
        if prefix_idx is None:
            continue
        prefixes = [
            _norm(t).rstrip("/") for t in _BACKTICK_RE.findall(cells[prefix_idx]) if _is_path_token(t)
        ]
        part = cells[prefix_idx + 1] if prefix_idx + 1 < len(cells) else ""
        part = part.replace("（", "(").split("(")[0].strip()
        part_short = re.split(r"[／/]", part)[0].strip() or part
        card: Optional[str] = None
        status = ""
        for i, c in enumerate(cells):
            if i == prefix_idx:
                continue
            if card is None:
                for t in _BACKTICK_RE.findall(c):
                    if _is_card_token(t):
                        card = t.replace("…", "*")
                        break
                if card is None:
                    m = _SAME_ROW_RE.search(c)
                    if m and 0 < int(m.group(1)) <= len(rows):
                        card = rows[int(m.group(1)) - 1]["card"]
                    elif c.startswith("同上") and rows:
                        card = rows[-1]["card"]
            if not status and c.startswith(_STATUS_HEADS) and len(c) <= 24:
                status = c[:2] if c.startswith(("部分", "索引")) else c[0]
        rows.append({
            "prefixes": [p for p in prefixes if p],
            "part": part,
            "part_short": part_short,
            "card": card,
            "status": status,
            "line": line.strip(),
        })
    return rows


# ─── 命中 ───────────────────────────────────────────────────────────

def match_row(path: str, root: Path, rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """最長前綴命中；錨在專案根的命中優先於子字串命中；同分取先列。"""
    p = _norm(path)
    r = _norm(str(root)).rstrip("/")
    best, best_score = None, -1
    for row in rows:
        for pre in row["prefixes"]:
            if "*" in pre:
                score = len(pre) if fnmatch.fnmatch(p, "*/" + pre) else -1
            elif p.startswith(r + "/" + pre + "/") or p == r + "/" + pre:
                score = 1000 + len(pre)
            elif ("/" + pre + "/") in p or p.endswith("/" + pre):
                score = len(pre)
            else:
                score = -1
            if score > best_score:
                best, best_score = row, score
    return best


# ─── 卡片 ───────────────────────────────────────────────────────────

def resolve_card(root: Path, card: Optional[str]) -> Optional[Path]:
    """卡名 → `<root>/.claude/memory/**/<卡名>.md`；SGI 的底線會被索引正規化成連字號，兩種都試。"""
    if not card:
        return None
    mem = root / ".claude" / "memory"
    try:
        for name in (card, card.replace("_", "-")):
            hits = sorted(mem.rglob(name + ".md"))
            if hits:
                return hits[0]
    except OSError:
        return None
    return None


def build_injection(row: Dict[str, Any], card_path: Optional[Path], hit_path: str, max_chars: int) -> str:
    part = row["part"] or row["part_short"]
    head = (
        f"[Guardian:OverviewHub] 本 session 第一次碰到【{part}】部位的檔（{hit_path}）。"
        f"改這個部位的檔之前先把下面的導讀卡讀完，並在回覆裡交出定位三行（三行都要，格式照抄）：\n"
        f"定位｜部位：{row['part_short']}——這次改的是哪一塊\n"
        f"定位｜根因層：修根因還是症狀；根因在哪層\n"
        f"定位｜前例：這個部位以前摔過什麼（卡片病灶段對得上哪條）"
    )
    if card_path is None:
        why = f"卡片狀態「{row['status'] or '未標'}」" if row["card"] else "表上沒有卡"
        return f"{head}\n---- 此部位目前沒有可注入的導讀卡（{why}）；表列原文：{row['line']} ----"
    try:
        body = card_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"{head}\n---- 導讀卡讀取失敗：{card_path}（{e}）----"
    if len(body) > max_chars:
        body = body[:max_chars] + f"\n…（超過 {max_chars} 字截斷，整張見 {card_path}）"
    note = "" if row["status"] == "有" else f"（注意：表上標此卡狀態「{row['status']}」，不是完整導讀，注入前專案要求先補驗）"
    return f"{head}\n---- 導讀卡{note}：{row['card']}（{card_path}）----\n{body}"


# ─── 定位三行 ───────────────────────────────────────────────────────

def locate_present(text: str, part_short: str) -> bool:
    """text 裡有沒有完整的定位三行（部位／根因／前例），且部位那行提到這個部位。"""
    found: Dict[str, str] = {}
    for m in LOCATE_RE.finditer(text):
        key = m.group(1)[:2]
        found[key] = m.group(2)
    if not {"部位", "根因", "前例"} <= set(found):
        return False
    return part_short.lower() in found["部位"].lower()


def assistant_text_after(transcript_path: str, byte_offset: int) -> str:
    """transcript（jsonl）從 byte_offset 之後的所有 assistant 文字塊，串成一段。fail-open 回 ""。"""
    if not transcript_path:
        return ""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(max(0, byte_offset))
            data = f.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""
    out: List[str] = []
    for raw in data.splitlines():
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict) or obj.get("type") != "assistant":
            continue
        for block in obj.get("message", {}).get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                out.append(block.get("text", ""))
    return "\n".join(out)


def transcript_size(transcript_path: str) -> int:
    try:
        return Path(transcript_path).stat().st_size if transcript_path else 0
    except OSError:
        return 0


# ─── 工具呼叫裡的讀檔路徑 ──────────────────────────────────────────

def read_paths_from_tool(tool_name: str, tool_input: Dict[str, Any], cwd: str) -> List[str]:
    """Read 的 file_path；Bash 裡 cat/head/tail/sed -n 的路徑（相對路徑補 cwd）。"""
    if tool_name == "Read":
        fp = tool_input.get("file_path", "")
        return [fp] if fp else []
    if tool_name != "Bash":
        return []
    out: List[str] = []
    for m in _BASH_READ_RE.finditer(tool_input.get("command", "") or ""):
        tok = m.group(1)
        if tok.startswith("$") or not _is_path_token(tok):
            continue
        if not Path(tok).is_absolute() and cwd:
            tok = str(Path(cwd) / tok)
        out.append(tok)
    return out


def top_dir(path: str, root: Path) -> str:
    """量測用：檔案相對專案根的第一段目錄。"""
    p, r = _norm(path), _norm(str(root)).rstrip("/")
    if p.startswith(r + "/"):
        rel = p[len(r) + 1:]
        return rel.split("/")[0] if "/" in rel else "(root)"
    return "(outside)"
