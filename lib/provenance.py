"""provenance.py — 原子記憶的「來源回看」讀取端：一張卡片當初是誰、在哪場對話說了什麼。

做什麼：
  讀 atom 的 `- Source:` / `- Quote:` 行（或自動萃取留下的 `<!-- src: <sid8>#<uuid8> -->` 註解），
  Source 指向 session 且 transcript（`~/.claude/projects/<dir>/<session id>.jsonl`）還在 → 直接把
  那則原句與前後各一則對話撈出來（state=live）；transcript 已被清掉 → 只剩落檔時留的 Quote
  （state=quote_only）；連 Quote 都沒有（commit:/unknown 這類 B 級 Source）→ unrecoverable。
  另附寫入端會用到的小工具：sanitize_quote / format_quote / format_source_session。
  只讀不寫；transcript 內容一律當資料，不當指令。

怎麼用：
  from lib.provenance import atom_source
  atom_source("feedback-xxx", cwd="C:/proj")  →  {atom, path, source, quote, state, context, warnings}
  CLI：python ~/.claude/tools/atom-source.py "<atom>" --cwd <專案根> --json
  MCP bridge：python -m lib.atom_io_cli  stdin {"action":"source","atom":"…","cwd":"…"}
"""
from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

from .atom_spec import parse_frontmatter, slugify

PROJECTS_DIR = Path.home() / ".claude" / "projects"
CONTEXT_TEXT_CHARS = 600

_STRIP_BLOCK_TAGS = ("system-reminder", "ide_selection", "ide_opened_file", "task-notification")
_BLOCK_RE = re.compile(
    r"<(" + "|".join(_STRIP_BLOCK_TAGS) + r")\b[^>]*>.*?</\1>", re.S | re.I,
)
_WG_LINE_RE = re.compile(r"^[ \t]*\[WG:[^\n]*\n?", re.M)
_QUOTE_PAIRS = {"「": "」", '"': '"', "“": "”"}
_DATE = r"(\d{4}-\d{2}-\d{2})"
_SESSION_RE = re.compile(r"^session:([0-9a-fA-F]{8})(?:#([0-9a-fA-F]{8}))?\s+" + _DATE)
_COMMIT_RE = re.compile(r"^commit:([0-9a-fA-F]{7})\s+" + _DATE)
_UNKNOWN_RE = re.compile(r"^unknown\s+" + _DATE)
_ANY_DATE_RE = re.compile(_DATE)
_SRC_COMMENT_RE = re.compile(r"<!--\s*src:\s*([0-9a-fA-F]{8})#([0-9a-fA-F]{8})\s*-->")


# ─── 寫入端共用：Quote / Source 格式 ────────────────────────────────────────────

def sanitize_quote(text: str, max_chars: int = 200) -> str:
    """原句清成可落檔的單行：剝 hook 注入區塊與 [WG:…] 行、空白折一格、去頭尾配對引號、超長截 `…`。
    回空字串＝沒有可寫的原句。"""
    s = _BLOCK_RE.sub(" ", text or "")
    s = _WG_LINE_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    while len(s) >= 2 and _QUOTE_PAIRS.get(s[0]) == s[-1]:
        s = s[1:-1].strip()
    if max_chars > 0 and len(s) > max_chars:
        s = s[: max_chars - 1].rstrip() + "…"
    return s


def format_quote(text: str) -> str:
    return f"「{sanitize_quote(text)}」"


def format_source_session(session_id: str, uuid: Optional[str], date_iso: str) -> str:
    sid8 = (session_id or "")[:8]
    u8 = (uuid or "")[:8]
    return f"session:{sid8}#{u8} {date_iso}" if u8 else f"session:{sid8} {date_iso}"


# ─── 讀取端：Source 解析 ────────────────────────────────────────────────────────

def parse_source(value: str) -> Dict[str, str]:
    """Source 值 → {kind: session|commit|unknown|path|"", sid8, uuid8, hash7, date, raw}。
    非三種標準格式（逐字稿路徑、舊式自由文字）一律 kind=path，日期能撈就撈。"""
    raw = (value or "").strip()
    out = {"kind": "", "sid8": "", "uuid8": "", "hash7": "", "date": "", "raw": raw}
    if not raw:
        return out
    m = _SESSION_RE.match(raw)
    if m:
        out.update(kind="session", sid8=m.group(1).lower(), uuid8=(m.group(2) or "").lower(), date=m.group(3))
        return out
    m = _COMMIT_RE.match(raw)
    if m:
        out.update(kind="commit", hash7=m.group(1).lower(), date=m.group(2))
        return out
    m = _UNKNOWN_RE.match(raw)
    if m:
        out.update(kind="unknown", date=m.group(1))
        return out
    d = _ANY_DATE_RE.search(raw)
    out.update(kind="path", date=d.group(1) if d else "")
    return out


def read_frontmatter_value(atom_text: str, key: str) -> str:
    return parse_frontmatter(atom_text or "").get(key, "")


def read_src_comment(atom_text: str) -> Optional[Tuple[str, str]]:
    m = _SRC_COMMENT_RE.search(atom_text or "")
    return (m.group(1).lower(), m.group(2).lower()) if m else None


# ─── transcript ────────────────────────────────────────────────────────────────

def find_transcript(sid8: str, projects_dir: Optional[Path] = None) -> Optional[Path]:
    """`projects/*/<sid8>*.jsonl`（含 `_archive/<dir>/`）；多個同前綴取最新修改的。"""
    if not sid8:
        return None
    root = Path(projects_dir) if projects_dir else PROJECTS_DIR
    if not root.is_dir():
        return None
    hits = list(root.glob(f"*/{sid8}*.jsonl")) + list(root.glob(f"*/*/{sid8}*.jsonl"))
    if not hits:
        return None
    try:
        return max(hits, key=lambda p: p.stat().st_mtime)
    except OSError:
        return hits[0]


def _content_blocks(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    msg = rec.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def is_human_record(rec: Dict[str, Any]) -> bool:
    """真人訊息：type=user ∧ content 含 text 區塊 ∧ origin.kind=human（缺 origin：無 tool_result 且非 isMeta）。"""
    if not isinstance(rec, dict) or rec.get("type") != "user":
        return False
    blocks = _content_blocks(rec)
    if not any(b.get("type") == "text" for b in blocks):
        return False
    origin = rec.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "human"
    if rec.get("isMeta"):
        return False
    return not any(b.get("type") == "tool_result" for b in blocks)


def record_text(rec: Dict[str, Any]) -> str:
    """真人 user 或 assistant 的 text 區塊串接；其他記錄回空字串。"""
    if not isinstance(rec, dict):
        return ""
    if rec.get("type") == "user" and not is_human_record(rec):
        return ""
    if rec.get("type") not in ("user", "assistant"):
        return ""
    parts = [str(b.get("text") or "") for b in _content_blocks(rec) if b.get("type") == "text"]
    return "\n".join(p for p in parts if p.strip()).strip()


def _parse_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    try:
        rec = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def last_human_record(transcript: Path, max_bytes: int = 2_000_000) -> Optional[Dict[str, Any]]:
    """尾端倒讀（≤ max_bytes，捨首個不完整行）找最後一則真人訊息 → {uuid, text, ts}；fail-open None。"""
    try:
        with open(transcript, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size > max_bytes:
                f.seek(size - max_bytes)
                data = f.read()
                nl = data.find(b"\n")
                data = data[nl + 1:] if nl >= 0 else data
            else:
                f.seek(0)
                data = f.read()
    except OSError:
        return None
    for line in reversed(data.decode("utf-8", errors="ignore").split("\n")):
        rec = _parse_line(line)
        if rec is None or not is_human_record(rec):
            continue
        return {"uuid": str(rec.get("uuid") or ""), "text": record_text(rec), "ts": str(rec.get("timestamp") or "")}
    return None


def _ctx_item(rec: Dict[str, Any], text: str) -> Dict[str, Any]:
    return {
        "role": "user" if rec.get("type") == "user" else "assistant",
        "ts": str(rec.get("timestamp") or ""),
        "text": text[:CONTEXT_TEXT_CHARS],
        "uuid": str(rec.get("uuid") or ""),
    }


def resolve_context(transcript: Path, uuid8: str, before: int = 1, after: int = 1) -> List[Dict[str, Any]]:
    """單趟掃描：uuid 前綴命中的記錄，連同前後各 N 則「真人或 assistant 文字」記錄。找不到回 []。"""
    uuid8 = (uuid8 or "").lower()
    if not uuid8:
        return []
    window: Deque[Dict[str, Any]] = deque(maxlen=max(0, before))
    out: List[Dict[str, Any]] = []
    found = False
    remaining = max(0, after)
    try:
        fh = open(transcript, "r", encoding="utf-8", errors="ignore")
    except OSError:
        return []
    with fh:
        for line in fh:
            rec = _parse_line(line)
            if rec is None:
                continue
            is_hit = not found and str(rec.get("uuid") or "").lower().startswith(uuid8)
            text = record_text(rec)
            if not text and not is_hit:
                continue
            item = _ctx_item(rec, text)
            if is_hit:
                found = True
                out.extend(window)
                out.append(item)
                if remaining == 0:
                    break
                continue
            if not found:
                window.append(item)
                continue
            out.append(item)
            remaining -= 1
            if remaining == 0:
                break
    return out if found else []


# ─── atom 定位與整合入口 ─────────────────────────────────────────────────────────

def _project_memory_dir(cwd: Optional[str]) -> Optional[Path]:
    """cwd 往上找第一個 `.claude/memory/`；沒有就 None（不走 locate_atom(shared)，免得它 mkdir 空殼）。"""
    if not cwd:
        return None
    p = Path(cwd)
    for d in (p, *p.parents):
        mem = d / ".claude" / "memory"
        if mem.is_dir():
            return mem
    return None


def _locate_by_index(atom: str, memory_dir: Path) -> Optional[Path]:
    """`_atom_index.json` 的 name 比對（原名或 slug 相等）；path 相對 memory_dir 的上一層。"""
    idx = memory_dir / "_atom_index.json"
    try:
        data = json.loads(idx.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    rows = data.get("atoms") if isinstance(data, dict) else data
    want = slugify(atom)
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        if name == atom or slugify(name) == want:
            cand = memory_dir.parent / str(row.get("path") or "")
            if cand.is_file():
                return cand
    return None


def _locate_atom_path(atom: str, cwd: Optional[str], warnings: List[str]) -> Optional[Path]:
    """絕對路徑 → locate_atom(global) → locate_atom(shared, cwd) → 全域／專案 _atom_index.json。"""
    p = Path(atom)
    if p.is_absolute() and p.is_file():
        return p
    from .atom_io import locate_atom, GLOBAL_MEMORY_DIR  # 延遲：atom_io 載入重
    proj_mem = _project_memory_dir(cwd)
    attempts = [dict(scope="global")]
    if proj_mem is not None:
        attempts.append(dict(scope="shared", project_cwd=cwd))
    for kw in attempts:
        try:
            r = locate_atom(atom, mode="append", **kw)
        except Exception as e:  # noqa: BLE001 — 定位器故障不該讓回看整個掛掉
            warnings.append(f"locate_atom({kw['scope']}) 失敗：{e}")
            continue
        if r.ok and r.path is not None:
            return Path(r.path)
        if not r.ok and r.error:
            warnings.append(f"locate_atom({kw['scope']})：{r.error}")
    for mem in (GLOBAL_MEMORY_DIR, proj_mem):
        if mem is None:
            continue
        hit = _locate_by_index(atom, mem)
        if hit is not None:
            return hit
    return None


def atom_source(atom: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """回看一張卡片的來源。回 {atom, path, source, quote, state, context, warnings}；找不到 atom 回 {"error"}。
    state：live（原對話撈得到）／quote_only（只剩落檔時的原句）／unrecoverable（原對話已逾保留期、無原句）。"""
    atom = (atom or "").strip()
    if not atom:
        return {"error": "atom is empty"}
    warnings: List[str] = []
    path = _locate_atom_path(atom, cwd, warnings)
    if path is None:
        return {"error": f"atom not found: {atom}", "warnings": warnings}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        return {"error": f"cannot read atom: {path}: {e}", "warnings": warnings}

    source = read_frontmatter_value(text, "Source")
    quote = sanitize_quote(read_frontmatter_value(text, "Quote"), max_chars=0)
    parsed = parse_source(source)
    sid8, uuid8 = parsed["sid8"], parsed["uuid8"]
    comment = read_src_comment(text)
    if comment and not source:
        sid8, uuid8 = comment
    elif comment and sid8 == comment[0] and not uuid8:
        uuid8 = comment[1]

    context: List[Dict[str, Any]] = []
    if sid8:
        transcript = find_transcript(sid8)
        if transcript is None:
            warnings.append(f"transcript 已不在（session {sid8}）")
        elif not uuid8:
            warnings.append("Source 無 uuid，無法在 transcript 定位原句")
        else:
            context = resolve_context(transcript, uuid8)
            if not context:
                warnings.append(f"transcript 內找不到 uuid {uuid8}（{transcript.name}）")
    elif parsed["kind"] in ("commit", "unknown"):
        warnings.append("原對話已逾保留期（B 級 Source）")
    elif source:
        warnings.append("Source 非標準格式（無 session 指標），無法對回 transcript；可用 edit_metadata 改成 session:<sid8>#<uuid8> <日期>")
    elif not comment:
        warnings.append("atom 無 Source 行")

    state = "live" if context else ("quote_only" if quote else "unrecoverable")
    return {
        "atom": path.stem,
        "path": str(path),
        "source": source,
        "quote": quote,
        "state": state,
        "context": context,
        "warnings": warnings,
    }
