"""
wg_atoms.py — Atom 索引解析 / Trigger / Intent / Vector search / Activation / 自我晉升（V5）

統合：
- Memory Index 解析、atom 載入、ACT-R activation、budget 控制（原 wg_atoms）
- Intent classification、Topic Tracker、Session Context、Proactive（前 wg_intent）
- Semantic search / vector observation log / incremental index（前 wg_intent）
- _self_iterate_atoms（前 wg_iteration — atom 晉升非自評）
"""

import json
import logging
import logging.handlers
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    CLAUDE_DIR, MEMORY_DIR, EPISODIC_DIR, WORKFLOW_DIR,
    MEMORY_INDEX, ATOM_INDEX, REALM_AUTOMOVE_MARKER,
    CONTEXT_BUDGET_DEFAULT,
    discover_all_project_memory_dirs, resolve_access_json, resolve_staging_dir,
    get_project_memory_dir, log_promotion_audit,
    _atom_debug_log, _atom_debug_error,
)

# V5 P3b: prefer _atom_index.json (machine source of truth)
sys.path.insert(0, str(CLAUDE_DIR / "lib"))
try:
    from atom_index_json import load_atom_index_json, to_atom_entries, ATOM_INDEX_JSON
except ImportError:
    load_atom_index_json = None
    to_atom_entries = None
    ATOM_INDEX_JSON = "_atom_index.json"

try:
    from atom_locations import iter_atom_files_multi
except ImportError:
    iter_atom_files_multi = None

try:
    from atom_locations import (
        classify_realm, is_local_realm_path,
        enumerate_local_paths, load_learned_lexicon, append_learned_terms,
        LOCAL_REALM_DEFAULT_DOMAIN,
    )
except ImportError:
    classify_realm = None
    is_local_realm_path = None
    enumerate_local_paths = None
    load_learned_lexicon = None
    append_learned_terms = None
    LOCAL_REALM_DEFAULT_DOMAIN = "Else"


# ─── Memory Index Parsing ────────────────────────────────────────────────────

TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")
ALIAS_RE = re.compile(r"^>\s*Project-Aliases:\s*(.+)", re.MULTILINE)

AtomEntry = Tuple[str, str, List[str]]


def parse_memory_index(memory_dir: Path) -> List[AtomEntry]:
    """Parse atom index, return list of (name, path, triggers).
    V5 P3b: 優先 _atom_index.json，fallback _ATOM_INDEX.md → MEMORY.md。
    """
    # V5 P3b: prefer JSON
    if load_atom_index_json is not None:
        json_path = memory_dir / ATOM_INDEX_JSON
        if json_path.exists():
            data = load_atom_index_json(memory_dir)
            entries = to_atom_entries(data)
            if entries:
                return entries

    atom_index_path = memory_dir / ATOM_INDEX
    if atom_index_path.exists():
        try:
            text = atom_index_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            text = None
        if text:
            return _parse_trigger_table(text)

    index_path = memory_dir / MEMORY_INDEX
    if not index_path.exists():
        return []
    try:
        text = index_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []

    if "Status: migrated-v2.21" in text:
        root_m = re.search(r"^-\s+Root:\s*(.+)$", text, re.MULTILINE)
        if root_m:
            redirect_dir = Path(root_m.group(1).strip()) / ".claude" / "memory"
            if redirect_dir.is_dir() and redirect_dir != memory_dir:
                return parse_memory_index(redirect_dir)
        return []

    return _parse_trigger_table(text)


def _parse_trigger_table(text: str) -> List[AtomEntry]:
    atoms: List[AtomEntry] = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_table:
            if stripped.startswith("| Atom") or stripped.startswith("|Atom"):
                in_table = True
                continue
        else:
            if stripped.startswith("|---") or stripped.startswith("| ---"):
                continue
            if not stripped.startswith("|"):
                in_table = False
                continue
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if len(cells) >= 3:
                name = cells[0]
                rel_path = cells[1]
                triggers = [t.strip().lower() for t in cells[2].split(",") if t.strip()]
                atoms.append((name, rel_path, triggers))
            elif cells:
                atoms.append((cells[0], "", []))
    return atoms


def _parse_atom_index_file(file_path: Path) -> List[AtomEntry]:
    """Parse a standalone atom index file."""
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []
    return _parse_trigger_table(text)


def parse_project_aliases(memory_dir: Path) -> List[str]:
    """Parse > Project-Aliases: line from MEMORY.md."""
    index_path = memory_dir / MEMORY_INDEX
    if not index_path.exists():
        return []
    try:
        text = index_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []
    m = ALIAS_RE.search(text)
    if not m:
        return []
    return [a.strip().lower() for a in m.group(1).split(",") if a.strip()]


def _find_atom_path(name: str, all_atoms: List[Tuple[AtomEntry, Path]]) -> Optional[Path]:
    for (aname, rel_path, _triggers), base_dir in all_atoms:
        if aname == name:
            return (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{name}.md")
    return None


# ─── Atom Matching & Activation ──────────────────────────────────────────────


def spread_related(
    matched_names: set,
    all_atoms: List[Tuple[AtomEntry, Path]],
    already_injected: List[str],
    max_depth: int = 1,
) -> List[Tuple[AtomEntry, Path]]:
    """沿 Related 邊擴散，回傳尚未匹配的相關 atoms (depth-limited BFS)."""
    _RELATED_RE = re.compile(r"^- Related:\s*(.+)", re.MULTILINE)
    visited = set(matched_names) | set(already_injected)
    wave = list(matched_names)
    result: List[Tuple[AtomEntry, Path]] = []

    for _depth in range(max_depth):
        next_wave: List[str] = []
        for name in wave:
            atom_path = _find_atom_path(name, all_atoms)
            if not atom_path or not atom_path.exists():
                continue
            try:
                text = atom_path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            rm = _RELATED_RE.search(text)
            if not rm:
                continue
            for rn in (r.strip() for r in rm.group(1).split(",") if r.strip()):
                if rn not in visited:
                    visited.add(rn)
                    for entry_tuple in all_atoms:
                        if entry_tuple[0][0] == rn:
                            result.append(entry_tuple)
                            next_wave.append(rn)
                            break
        wave = next_wave
    return result


def compute_activation(atom_name: str, atom_dir: Path) -> float:
    """ACT-R base-level activation: B_i = ln(Σ t_k^{-0.5})."""
    access_file = atom_dir / f"{atom_name}.access.json"
    if not access_file.exists():
        return -10.0
    try:
        data = json.loads(access_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return -10.0
    timestamps = data.get("timestamps", [])
    if not timestamps:
        return -10.0
    now = time.time()
    total = 0.0
    for ts in timestamps:
        t_k = max(now - ts, 1.0)
        total += t_k ** -0.5
    return math.log(total) if total > 0 else -10.0


def _kw_match(kw: str, prompt_lower: str) -> bool:
    """Match a trigger keyword against prompt. ASCII uses word-boundary, CJK uses substring."""
    if kw.isascii():
        return bool(re.search(r'(?<![\w-])' + re.escape(kw) + r'(?![\w-])', prompt_lower))
    return kw in prompt_lower


def match_triggers(prompt: str, atoms: List[AtomEntry]) -> List[AtomEntry]:
    prompt_lower = prompt.lower()
    matched = []
    for name, rel_path, triggers in atoms:
        if any(_kw_match(kw, prompt_lower) for kw in triggers):
            matched.append((name, rel_path, triggers))
    return matched


# ─── BM25 Match (V5 P5a) ─────────────────────────────────────────────────────
# Hand-rolled BM25 over atom trigger lists. ~30 lines, no external dep.
# Use case: global layer (~17 atoms) — replaces vector service round-trip
# (200-500ms) with in-memory <10ms scoring.

_BM25_K1 = 1.2
_BM25_B = 0.75


def _bm25_tokenize(text: str) -> List[str]:
    """Tokenize: ASCII words + Chinese char-bigrams."""
    text = text.lower()
    tokens: List[str] = re.findall(r"[a-z0-9]+", text)
    # Chinese char bigrams (CJK Unified)
    cjk = re.findall(r"[一-鿿]+", text)
    for run in cjk:
        if len(run) == 1:
            tokens.append(run)
        else:
            for i in range(len(run) - 1):
                tokens.append(run[i:i + 2])
    return tokens


def _bm25_score(prompt: str, atoms: List[AtomEntry]) -> List[Tuple[str, float]]:
    """Score each atom by BM25 over its trigger list + atom name. Returns sorted (name, score)."""
    if not atoms:
        return []
    # Each atom = one "document" = triggers + name
    docs: List[List[str]] = []
    for name, _rel, triggers in atoms:
        doc_text = " ".join(triggers) + " " + name.replace("-", " ")
        docs.append(_bm25_tokenize(doc_text))

    avgdl = sum(len(d) for d in docs) / max(len(docs), 1)
    N = len(docs)

    # Document frequency
    df: Dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1

    query_tokens = _bm25_tokenize(prompt)
    if not query_tokens:
        return []

    scored: List[Tuple[str, float]] = []
    for (name, _rel, _triggers), doc in zip(atoms, docs):
        if not doc:
            continue
        dl = len(doc)
        # Term frequency in doc
        tf_doc: Dict[str, int] = {}
        for t in doc:
            tf_doc[t] = tf_doc.get(t, 0) + 1
        score = 0.0
        for q in set(query_tokens):
            if q not in tf_doc:
                continue
            f = tf_doc[q]
            n_q = df.get(q, 0)
            idf = math.log(1 + (N - n_q + 0.5) / (n_q + 0.5))
            denom = f + _BM25_K1 * (1 - _BM25_B + _BM25_B * dl / avgdl)
            score += idf * (f * (_BM25_K1 + 1)) / max(denom, 1e-9)
        if score > 0:
            scored.append((name, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def bm25_match(
    prompt: str,
    atoms: List[AtomEntry],
    min_score: float = 1.0,
    top_k: int = 3,
) -> List[AtomEntry]:
    """Return top-k atoms whose BM25 score exceeds min_score."""
    scored = _bm25_score(prompt, atoms)
    if not scored:
        return []
    by_name = {a[0]: a for a in atoms}
    result: List[AtomEntry] = []
    for name, score in scored[:top_k]:
        if score < min_score:
            break
        if name in by_name:
            result.append(by_name[name])
    return result


# ─── Token Budget & Atom Loading ─────────────────────────────────────────────


def compute_token_budget(prompt: str) -> int:
    plen = len(prompt)
    if plen < 50:
        return 1500
    elif plen < 200:
        return 3000
    else:
        return 5000


_STRIP_META_RE = re.compile(
    r"^- (?:Scope|Type|Trigger|Last-used|Created|Confirmations|ReadHits|Tags|TTL|Expires-at):\s.*$\n?",
    re.MULTILINE,
)

_STRIP_SECTION_RE = re.compile(
    r"^## (?:行動|演化日誌)\s*\n[\s\S]*?(?=^## |\Z)",
    re.MULTILINE,
)

_FRONTMATTER_KEEP_RE = re.compile(
    r"^- (?:Confidence|Trigger|Last-used):\s*.+$",
    re.MULTILINE,
)

_KNOWLEDGE_CAP_TOKENS_DEFAULT = 200


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _extract_named_section(
    content: str, section_title: str, max_tokens: Optional[int] = None,
) -> Optional[str]:
    pattern = re.compile(
        r"^##[ \t]+" + re.escape(section_title) + r"[ \t]*\n([\s\S]*?)(?=^## |\Z)",
        re.MULTILINE,
    )
    m = pattern.search(content)
    if not m:
        return None
    body = m.group(1).rstrip()
    full = f"## {section_title}\n{body}"

    if max_tokens is None:
        return full

    full_tokens = _estimate_tokens(full)
    if full_tokens <= max_tokens:
        return full

    header = f"## {section_title}\n"
    marker = f"\n\n…（已截斷，原 {full_tokens} tokens）"
    target_chars = max_tokens * 4 - len(header) - len(marker)
    if target_chars < 50:
        target_chars = 50
    truncated = body[:target_chars]
    snap = truncated.rfind("\n\n")
    if snap < target_chars * 0.5:
        snap = truncated.rfind("\n")
    if snap > 0:
        truncated = truncated[:snap]
    return f"{header}{truncated.rstrip()}{marker}"


def _detect_atom_type(content: str) -> str:
    has_knowledge = _extract_named_section(content, "知識") is not None
    if has_knowledge:
        return "knowledge_mixed"
    has_impression = _extract_named_section(content, "印象") is not None
    if has_impression:
        return "impression_action"
    return "fallback"


def _extract_title_and_frontmatter(content: str) -> str:
    title_line = ""
    for line in content.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            title_line = line.rstrip()
            break

    keep_lines = [m.group(0) for m in _FRONTMATTER_KEEP_RE.finditer(content)]
    parts: List[str] = []
    if title_line:
        parts.append(title_line)
    if keep_lines:
        if title_line:
            parts.append("")
        parts.extend(keep_lines)
    return "\n".join(parts)


def _legacy_strip_atom_for_injection(content: str) -> str:
    content = _STRIP_META_RE.sub("", content)
    content = _STRIP_SECTION_RE.sub("", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def _strip_atom_for_injection(
    content: str, knowledge_cap_tokens: int = _KNOWLEDGE_CAP_TOKENS_DEFAULT,
) -> str:
    atom_type = _detect_atom_type(content)

    if atom_type == "fallback":
        return _legacy_strip_atom_for_injection(content)

    parts: List[str] = []
    header = _extract_title_and_frontmatter(content)
    if header:
        parts.append(header)

    impression = _extract_named_section(content, "印象")
    if impression:
        parts.append(impression)

    if atom_type == "knowledge_mixed":
        knowledge = _extract_named_section(content, "知識", max_tokens=knowledge_cap_tokens)
        if knowledge:
            parts.append(knowledge)

    action = _extract_named_section(content, "行動")
    if action:
        parts.append(action)

    return "\n\n".join(parts).strip()


def _strip_atom_for_injection_impression_only(content: str) -> str:
    parts: List[str] = []
    header = _extract_title_and_frontmatter(content)
    if header:
        parts.append(header)
    impression = _extract_named_section(content, "印象")
    if impression:
        parts.append(impression)
    return "\n\n".join(parts).strip()


_TURN_BUDGET_LIMIT = 800


def decide_atom_injection(
    raw_content: str,
    full_content: str,
    used_tokens: int,
    budget_limit: int = _TURN_BUDGET_LIMIT,
) -> Tuple[str, str, int]:
    """Decide ok / fallback / skip for an atom against per-turn budget."""
    full_tokens = _estimate_tokens(full_content)
    if used_tokens + full_tokens <= budget_limit:
        return ("ok", full_content, full_tokens)

    fb_content = _strip_atom_for_injection_impression_only(raw_content)
    fb_tokens = _estimate_tokens(fb_content)
    if fb_tokens >= full_tokens:
        return ("skip", "", 0)
    if used_tokens + fb_tokens <= budget_limit:
        return ("fallback", fb_content, fb_tokens)
    return ("skip", "", 0)


_HOT_RECENT_DAYS = 7
_HOT_RECENT_WINDOW_SEC = _HOT_RECENT_DAYS * 86400
_COLD_LINE_CAP = 80


def _recent_reads_7d(access_file: Path) -> int:
    if not access_file.exists():
        return 0
    try:
        data = json.loads(access_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    timestamps = data.get("timestamps", []) if isinstance(data, dict) else []
    if not isinstance(timestamps, list):
        return 0
    now = time.time()
    count = 0
    for ts in timestamps:
        try:
            if now - float(ts) <= _HOT_RECENT_WINDOW_SEC:
                count += 1
        except (TypeError, ValueError):
            continue
    return count


def classify_hot_cold(
    atom_path: Path, source: str, hot_recent_threshold: int = 3,
) -> str:
    if source == "trigger":
        return "hot"
    access_file = atom_path.parent / f"{atom_path.stem}.access.json"
    return "hot" if _recent_reads_7d(access_file) >= hot_recent_threshold else "cold"


def format_cold_inject_line(name: str, raw_content: str, rel_path: str) -> str:
    summary = ""
    impression = _extract_named_section(raw_content, "印象")
    if impression:
        for line in impression.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("##") or stripped.startswith(">"):
                continue
            if stripped.startswith("- "):
                summary = stripped[2:].strip()
            else:
                summary = stripped
            if summary:
                break
    if not summary:
        for line in raw_content.split("\n"):
            if line.startswith("# ") and not line.startswith("## "):
                summary = line[2:].strip()
                break
    if not summary:
        summary = name

    summary = summary.replace("\n", " ").replace("\r", " ").strip()
    if len(summary) > _COLD_LINE_CAP:
        summary = summary[:_COLD_LINE_CAP].rstrip() + "…"

    display_path = rel_path or f"{name}.md"
    return f"[Atom:{name}] (cold) {summary} (full: Read {display_path})"


def load_atoms_within_budget(
    matched: List[AtomEntry],
    memory_dir: Path,
    budget_tokens: int,
    already_injected: List[str],
) -> Tuple[List[str], List[str], int]:
    lines: List[str] = []
    injected: List[str] = []
    used = 0

    for name, rel_path, triggers in matched:
        if name in already_injected:
            continue
        atom_path = (memory_dir / rel_path) if rel_path else (memory_dir / f"{name}.md")
        if not atom_path.exists():
            continue
        try:
            content = atom_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue

        content = _strip_atom_for_injection(content)
        content_tokens = len(content) // 4
        if used + content_tokens <= budget_tokens:
            lines.append(f"[Atom:{name}]\n{content}")
            injected.append(name)
            used += content_tokens
        else:
            first_line = content.split("\n", 1)[0].strip("# ").strip()
            lines.append(f"[Atom:{name}] {first_line} (full: Read {rel_path or name + '.md'})")
            injected.append(name)
            break

    return lines, injected, used


# ─── Sub-agent Injection Orchestrator (Phase 1, #1) ──────────────────────────
# 可重用注入 orchestrator：parent → sub-agent 記憶注入（PreToolUse updatedInput）。
# 包裝既有純函式（parse_memory_index / match_triggers / bm25_match /
# load_atoms_within_budget / _strip_atom_for_injection）。全域層 only，
# 不依賴 session state["atom_index"]。緊湊 top-k（印象式 strip）守 token 紅線。

SUBAGENT_INJECT_MARKER = "[WG:SubagentMemory]"
_SUBAGENT_TOP_K = 3


def build_injection_blob(
    prompt_str: str,
    *,
    budget: int,
    already_injected: Optional[List[str]] = None,
) -> Tuple[str, List[str]]:
    """為 sub-agent prompt 組緊湊記憶注入 blob。

    回傳 (blob_str, injected_names)。無匹配時回 ("", [])（caller 應保留原 prompt 不改）。
    冪等：若 prompt 已帶本 marker（巢狀 sub-agent）→ 回 ("", [])，不重複注入。

    blob 內含可解析 header `[WG:SubagentMemory] ... atoms=a,b,c`，
    供 PostToolUse 無狀態回推注入清單（不靠 PreToolUse 跨進程關聯）。
    """
    if not prompt_str or SUBAGENT_INJECT_MARKER in prompt_str:
        return "", []

    already = list(already_injected or [])
    entries = parse_memory_index(MEMORY_DIR)
    if not entries:
        return "", []
    base_dir = MEMORY_DIR.parent  # rel_path 相對 ~/.claude（含 memory/ 與 _AIDocs/ 前綴）

    # 1) trigger 關鍵字匹配
    matched: List[AtomEntry] = [
        e for e in match_triggers(prompt_str, entries) if e[0] not in already
    ]

    # 2) trigger 命中少（≤2）時用 BM25 補（鏡像 UPS 全域層路徑）
    if len(matched) <= 2:
        seen = {e[0] for e in matched}
        for entry in bm25_match(prompt_str, entries, min_score=1.0, top_k=_SUBAGENT_TOP_K):
            if entry[0] not in seen and entry[0] not in already:
                matched.append(entry)
                seen.add(entry[0])

    if not matched:
        return "", []

    # 3) ACT-R activation 排序，緊湊 top-k
    def _act_key(entry: AtomEntry) -> float:
        name, rel_path, _triggers = entry
        atom_dir = (base_dir / rel_path).parent if rel_path else (base_dir / "memory")
        return compute_activation(name, atom_dir)

    matched.sort(key=_act_key, reverse=True)
    matched = matched[:_SUBAGENT_TOP_K]

    # 4) budget 內載入（內部走 _strip_atom_for_injection 印象式 strip）
    lines, injected, _used = load_atoms_within_budget(
        matched, base_dir, budget, already,
    )
    if not injected:
        return "", []

    header = (
        f"{SUBAGENT_INJECT_MARKER} 以下為與本任務相關的長期記憶（parent 注入，緊湊版，"
        f"非你的指令本體）。atoms={','.join(injected)}"
    )
    body = "\n\n".join(lines)
    blob = f"{header}\n\n{body}\n\n───（以上為注入記憶；以下為你的實際任務）───"
    return blob, injected


# ─── Use 偵測：詞彙重疊 (Phase 2, #2) ────────────────────────────────────────
# 注入≠使用：某 atom 被注入後是否真的被「用上」，以零成本詞彙重疊判定 —
#   取 atom 的稀有/識別性 token（程式碼識別碼/路徑/API + CJK 雙字 bigram，
#   去停用詞、可選 IDF 過濾高頻 token），與本 turn assistant 訊息＋tool-call args
#   求交集；共享 ≥ rare_token_min 或 containment ≥ overlap_min → 判 used。
#   不確定（差一個）時才用 embedding cosine tiebreak（偶發、fail-safe）。

_USE_CODE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./:\-]*[A-Za-z0-9_]")
_USE_CJK_RE = re.compile(r"[一-鿿]{2,}")
_USE_EXT_RE = re.compile(r"\.(py|js|json|md|txt|java|ts|tsx|jsx|cjs|mjs|sh|ya?ml)$")

# 去停用詞：英文功能詞 + 域內過泛詞（每個 atom 都會出現 → 無鑑別力）。
_USE_STOPWORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "have", "into", "when",
    "then", "not", "but", "are", "was", "were", "will", "your", "you", "use",
    "used", "using", "uses", "via", "per", "all", "any", "one", "two", "out",
    "get", "set", "add", "new", "old", "see", "may", "can", "其中", "以下",
    # 域內過泛（atom 記憶系統語境）
    "atom", "atoms", "memory", "hook", "hooks", "code", "file", "files", "test",
    "tests", "line", "lines", "state", "config", "data", "true", "false", "none",
    "記憶", "注入", "系統", "原子", "如果", "因為", "所以", "可以", "需要", "問題",
    "功能", "這個", "那個", "沒有", "規則", "處理",
})


def _use_pieces(span: str) -> List[str]:
    """把一段 code-ish span 正規化成可比對 piece（path 段 + _/. 子詞），雙側一致。"""
    out: List[str] = []
    for raw in re.split(r"[/\s:,;()\[\]<>\"'`、，。]+", span.strip().lower()):
        p = raw.strip("._-")
        if not p:
            continue
        p = _USE_EXT_RE.sub("", p)
        if not p:
            continue
        out.append(p)
        for sub in re.split(r"[._]+", p):
            if len(sub) >= 5:
                out.append(sub)
    return out


def extract_distinctive_tokens(text: str) -> set:
    """抽 text 的稀有/識別性 token 集合（雙側同一函式 → 比對一致）。

    - code-ish：含 `_./-`/數字 或 長度≥7 的識別碼/路徑/API（含 path 段與 _ 子詞）
    - CJK：雙字 bigram（去過泛雙字）
    去停用詞、長度<4 丟棄。
    """
    if not text:
        return set()
    toks: set = set()
    for span in _USE_CODE_RE.findall(text):
        for p in _use_pieces(span):
            if len(p) < 4 or p in _USE_STOPWORDS:
                continue
            code_like = bool(re.search(r"[_.\d/\-]", p))
            if code_like or len(p) >= 7 or (5 <= len(p) <= 6):
                toks.add(p)
    for run in _USE_CJK_RE.findall(text):
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg not in _USE_STOPWORDS:
                toks.add(bg)
    return toks


def build_atom_df(atom_texts: List[str]) -> Tuple[Counter, int]:
    """跨 atom 語料的 document frequency（近似 IDF）：token→出現於幾顆 atom。

    回傳 (df_counter, n_docs)。供 detect_atom_use 過濾「出現在過多 atom」的低鑑別 token。
    """
    df: Counter = Counter()
    n = 0
    for t in atom_texts:
        n += 1
        for tok in extract_distinctive_tokens(t):
            df[tok] += 1
    return df, n


def resolve_atom_path(name: str) -> Optional[Path]:
    """atom name → .md Path（全域層，含 _AIDocs/Failures feedback-*）。找不到回 None。

    僅迭代檔路徑（不讀內容），供 Stop 端解析 sub-agent 注入清單的 atom 名 → 路徑。
    """
    target = f"{name}.md"
    if iter_atom_files_multi is not None:
        try:
            for p in iter_atom_files_multi():
                if p.name == target:
                    return p
        except Exception as e:
            _atom_debug_error("usefulness:atom_lookup_multi", e)
    cand = MEMORY_DIR / target
    return cand if cand.exists() else None


def detect_atom_use(
    atom_content: str,
    turn_text: str,
    *,
    rare_token_min: int = 2,
    overlap_min: float = 0.18,
    df_map: Optional[Counter] = None,
    n_docs: int = 0,
    max_df_ratio: float = 0.5,
    embed_fn=None,
    embed_min: float = 0.62,
) -> Dict[str, Any]:
    """判定 atom 是否在本 turn 被使用。回 {used, shared, containment, method}。

    主判：稀有 token 交集 |shared| ≥ rare_token_min 或 containment ≥ overlap_min。
    IDF 過濾：df_map/n_docs 提供時，丟棄 df/n_docs > max_df_ratio 的過泛 token。
    Tiebreak：差一個（|shared| == rare_token_min-1 且 ≥1）時，若 embed_fn 提供 →
      cosine ≥ embed_min 判 used（method=embed）。embed_fn 失敗回 None → 不影響主判。
    """
    rare = extract_distinctive_tokens(atom_content)
    if df_map is not None and n_docs > 0 and max_df_ratio < 1.0:
        cutoff = max_df_ratio * n_docs
        rare = {t for t in rare if df_map.get(t, 0) <= cutoff}
    if not rare:
        return {"used": False, "shared": 0, "containment": 0.0, "method": "no_rare"}

    turn_tokens = extract_distinctive_tokens(turn_text)
    shared = rare & turn_tokens
    n_shared = len(shared)
    containment = n_shared / len(rare)

    if n_shared >= rare_token_min or containment >= overlap_min:
        return {"used": True, "shared": n_shared, "containment": round(containment, 3),
                "method": "lexical"}

    # tiebreak：差一個才動 embedding（偶發）
    if embed_fn is not None and n_shared == max(0, rare_token_min - 1) and n_shared >= 1:
        try:
            cos = embed_fn(atom_content, turn_text)
        except Exception as e:
            _atom_debug_error("usefulness:embed_tiebreak", e)
            cos = None
        if cos is not None and cos >= embed_min:
            return {"used": True, "shared": n_shared, "containment": round(containment, 3),
                    "method": "embed", "cosine": round(float(cos), 3)}

    return {"used": False, "shared": n_shared, "containment": round(containment, 3),
            "method": "lexical"}


def make_embed_tiebreak_fn(config: Dict[str, Any]):
    """構造 fail-safe 的 embedding cosine tiebreak callable（或 None）。

    僅當 config.usefulness.embedding_tiebreak 為真才回 callable；任何失敗（服務未起、
    逾時、格式異常）回 None → detect_atom_use 視同無 tiebreak，不污染主判。
    走既有 Ollama /api/embeddings（短逾時、截斷輸入），屬偶發呼叫（僅邊界 case）。
    """
    uconf = (config or {}).get("usefulness", {}) or {}
    if not uconf.get("embedding_tiebreak", False):
        return None
    vs = (config or {}).get("vector_search", {}) or {}
    base = vs.get("ollama_base_url", "http://127.0.0.1:11434")
    model = vs.get("embedding_model", "qwen3-embedding")
    timeout_s = float(uconf.get("embed_timeout_s", 1.5))

    def _embed_one(text: str) -> Optional[List[float]]:
        payload = json.dumps({"model": model, "prompt": text[:1500]}).encode("utf-8")
        req = urllib.request.Request(
            f"{base.rstrip('/')}/api/embeddings", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
        vec = obj.get("embedding")
        return vec if isinstance(vec, list) and vec else None

    def _cosine(a: str, b: str) -> Optional[float]:
        try:
            va, vb = _embed_one(a), _embed_one(b)
            if not va or not vb or len(va) != len(vb):
                return None
            dot = sum(x * y for x, y in zip(va, vb))
            na = math.sqrt(sum(x * x for x in va))
            nb = math.sqrt(sum(y * y for y in vb))
            if na == 0 or nb == 0:
                return None
            return dot / (na * nb)
        except Exception as e:
            _atom_debug_error("usefulness:embed_cosine", e)
            return None

    return _cosine


def _truncate_context_by_activation(
    lines: List[str], limit: int = CONTEXT_BUDGET_DEFAULT,
    source_dirs: Optional[Dict[str, Path]] = None,
) -> List[str]:
    """V2.11: Truncate additionalContext lines to fit within token budget."""
    full_text = "\n".join(lines)
    used = len(full_text) // 4
    if used <= limit:
        lines.append(f"[Context budget: {used}/{limit} tokens]")
        return lines

    ATOM_LINE_RE = re.compile(r"^\[Atom:(\S+)\]")
    atom_blocks: List[dict] = []
    i = 0
    while i < len(lines):
        m = ATOM_LINE_RE.match(lines[i])
        if m:
            name = m.group(1)
            end = i + 1
            while end < len(lines) and not ATOM_LINE_RE.match(lines[end]):
                end += 1
            block_text = "\n".join(lines[i:end])
            atom_blocks.append({
                "name": name,
                "start": i,
                "end": end,
                "tokens": len(block_text) // 4,
                "first_line": lines[i].split("\n", 1)[0] if "\n" in lines[i] else lines[i],
            })
            i = end
        else:
            i += 1

    if not atom_blocks:
        lines.append(f"[Context budget: {used}/{limit} tokens (over)]")
        return lines

    fallback_roots: List[Path] = [MEMORY_DIR, EPISODIC_DIR]
    try:
        for _slug, mem_dir in discover_all_project_memory_dirs():
            fallback_roots.append(mem_dir)
            ep = mem_dir / "episodic"
            if ep.is_dir():
                fallback_roots.append(ep)
    except Exception as e:
        _atom_debug_error("usefulness:project_roots_discover", e)

    for ab in atom_blocks:
        atom_name = ab["name"]
        src_dir = source_dirs.get(atom_name) if source_dirs else None
        if src_dir:
            ab["activation"] = compute_activation(atom_name, src_dir)
        else:
            best = -10.0
            for cand in fallback_roots:
                score = compute_activation(atom_name, cand)
                if score > best:
                    best = score
            ab["activation"] = best

    atom_blocks.sort(key=lambda x: x["activation"])

    truncated_indices: set = set()
    for ab in atom_blocks:
        if used <= limit:
            break
        summary = f"[Atom:{ab['name']}] (truncated, activation={ab['activation']:.2f}) Read memory/{ab['name']}.md"
        saved = ab["tokens"] - (len(summary) // 4)
        if saved > 0:
            truncated_indices.add(ab["start"])
            ab["summary"] = summary
            used -= saved

    new_lines: List[str] = []
    skip_until = -1
    for idx, line in enumerate(lines):
        if idx < skip_until:
            continue
        found = False
        for ab in atom_blocks:
            if ab["start"] == idx and idx in truncated_indices:
                new_lines.append(ab["summary"])
                skip_until = ab["end"]
                found = True
                break
        if not found and idx >= skip_until:
            new_lines.append(line)

    new_lines.append(f"[Context budget: {used}/{limit} tokens]")
    return new_lines


# ─── Section-Level Extraction ───────────────────────────────────────────────

SECTION_INJECT_THRESHOLD = 200

_SECTION_HEADER_RE = re.compile(r"^(#{2,3})\s+(.+)", re.MULTILINE)
_RELATED_LINE_RE = re.compile(r"^- Related:\s*.+", re.MULTILINE)


def _extract_sections(
    content: str,
    section_hints: List[Dict[str, Any]],
) -> Optional[str]:
    """Extract matching sections from atom content based on vector search hints."""
    if not section_hints:
        return None

    lines = content.split("\n")
    total_lines = len(lines)

    section_map: List[Dict[str, Any]] = []
    for m in _SECTION_HEADER_RE.finditer(content):
        level = len(m.group(1))
        header_text = m.group(2).strip()
        line_no = content[:m.start()].count("\n")
        section_map.append({
            "header": header_text,
            "level": level,
            "start": line_no,
            "end": total_lines,
        })

    for i in range(len(section_map) - 1):
        section_map[i]["end"] = section_map[i + 1]["start"]

    hint_names = set()
    for h in section_hints:
        s = h.get("section", "").strip()
        if s:
            hint_names.add(s.lower())

    matched_sections: List[Dict[str, Any]] = []
    matched_indices: set = set()

    for idx, sec in enumerate(section_map):
        header_lower = sec["header"].lower()
        if header_lower in hint_names:
            matched_sections.append(sec)
            matched_indices.add(idx)

    unmatched_hints = hint_names - {sec["header"].lower() for sec in matched_sections}
    if unmatched_hints:
        for idx, sec in enumerate(section_map):
            if idx in matched_indices:
                continue
            header_lower = sec["header"].lower()
            for hint in unmatched_hints:
                if hint in header_lower or header_lower in hint:
                    matched_sections.append(sec)
                    matched_indices.add(idx)
                    break

    if not matched_sections:
        return None

    parent_indices: set = set()
    for sec in matched_sections:
        if sec["level"] == 3:
            sec_start = sec["start"]
            candidate_idx = None
            for idx, s in enumerate(section_map):
                if s["level"] == 2 and s["start"] < sec_start:
                    candidate_idx = idx
            if candidate_idx is not None and candidate_idx not in matched_indices:
                parent_indices.add(candidate_idx)

    include_lines: set = set()

    for i, line in enumerate(lines):
        if line.startswith("# ") and not line.startswith("## "):
            include_lines.add(i)
            break
    rm = _RELATED_LINE_RE.search(content)
    if rm:
        rel_line_no = content[:rm.start()].count("\n")
        include_lines.add(rel_line_no)

    for sec in matched_sections:
        for i in range(sec["start"], sec["end"]):
            include_lines.add(i)

    for pidx in parent_indices:
        include_lines.add(section_map[pidx]["start"])

    if len(include_lines) >= total_lines * 0.70:
        return None

    omitted = len(section_map) - len(matched_sections) - len(parent_indices)
    output_lines: List[str] = []
    sorted_lines = sorted(include_lines)

    prev = -1
    for i in sorted_lines:
        if prev >= 0 and i > prev + 1:
            pass
        output_lines.append(lines[i])
        prev = i

    if omitted > 0:
        output_lines.append(f"\n[+{omitted} sections omitted]")

    return "\n".join(output_lines)


# ─── _AIDocs Index Parsing ──────────────────────────────────────────────────

AiDocsEntry = Tuple[str, str, List[str]]


def parse_aidocs_index(project_root: Path) -> List[AiDocsEntry]:
    """Parse _AIDocs/_INDEX.md table."""
    index_path = project_root / "_AIDocs" / "_INDEX.md"
    if not index_path.exists():
        return []
    try:
        text = index_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []

    entries: List[AiDocsEntry] = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_table:
            if stripped.startswith("| #") or stripped.startswith("|#"):
                in_table = True
                continue
        else:
            if stripped.startswith("|---") or stripped.startswith("| ---"):
                continue
            if not stripped.startswith("|"):
                in_table = False
                continue
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if len(cells) >= 3:
                fname = cells[1].strip("[]() ")
                link_match = re.match(r"\[([^\]]+)\]", cells[1])
                if link_match:
                    fname = link_match.group(1)
                desc = cells[2]
                if fname.startswith("~~") or "淘汰" in desc:
                    continue
                keywords: List[str] = []
                if len(cells) >= 4 and cells[3].strip():
                    keywords = [k.strip().lower() for k in cells[3].split(",") if k.strip()]
                entries.append((fname, desc, keywords))
    return entries


def extract_aidocs_keywords(entries: List[AiDocsEntry]) -> Dict[str, List[str]]:
    STOP = {"的", "與", "和", "等", "個", "含", "—", "md", "分析", "說明", "文件", "專案"}
    result: Dict[str, List[str]] = {}
    for fname, desc, explicit_kw in entries:
        if explicit_kw:
            result[fname] = explicit_kw[:15]
        else:
            words = re.findall(r"[一-鿿]{2,}|[a-zA-Z_]{3,}", desc.lower())
            keywords = [w for w in words if w not in STOP]
            stem = Path(fname).stem.lower().replace("_", " ").replace("-", " ")
            keywords.extend(stem.split())
            result[fname] = list(set(keywords))[:10]
    return result


# ─── Intent Classifier (was wg_intent.classify_intent) ──────────────────────

INTENT_PATTERNS = {
    "debug": ["crash", "error", "bug", "失敗", "壞", "exception", "為什麼",
              "why", "問題", "traceback", "報錯", "修復", "fix"],
    "build": ["build", "deploy", "建置", "部署", "安裝", "install", "啟動",
              "setup", "config", "設定", "配置", "環境"],
    "design": ["設計", "架構", "design", "architecture", "重構", "refactor",
               "新增", "planning", "實作", "implement", "方案"],
    "recall": ["之前", "上次", "記得", "決策", "決定", "為什麼選",
               "remember", "previous", "history"],
    "handoff": ["下 session", "下次繼續", "交接", "續接", "下一個 session",
                "resume prompt", "給下次", "next-phase", "handoff", "下個 claude"],
}


def classify_intent(prompt: str) -> str:
    """Rule-based intent classifier. Zero LLM overhead (~1ms)."""
    prompt_lower = prompt.lower()
    scores = {}
    for intent, keywords in INTENT_PATTERNS.items():
        scores[intent] = sum(1 for kw in keywords if kw in prompt_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


# ─── Topic Tracker ──────────────────────────────────────────────────────────

_TOPIC_STOP_WORDS = frozenset({
    "this", "that", "with", "from", "have", "been", "will", "what", "when",
    "which", "where", "about", "into", "also", "should", "could", "would",
    "these", "those", "them", "your", "make", "just", "only", "some", "very",
    "here", "there", "then", "than", "more", "most", "like", "each", "want",
    "need", "keep", "does", "done", "doing", "help", "sure", "good", "well",
    "okay", "know", "think", "look", "take", "give", "come", "back", "over",
    "after", "before", "other", "file", "line", "code", "true", "false",
})


def _update_topic_tracker(
    state: Dict[str, Any], prompt: str, intent: str, newly_injected: List[str]
) -> None:
    """Accumulate topic signals in state. Pure CPU, < 1ms, zero network."""
    tracker = state.setdefault("topic_tracker", {
        "intent_distribution": {},
        "prompt_count": 0,
        "first_prompt_summary": "",
        "keyword_signals": [],
        "related_episodic": [],
    })

    dist = tracker["intent_distribution"]
    dist[intent] = dist.get(intent, 0) + 1
    tracker["prompt_count"] = tracker.get("prompt_count", 0) + 1

    if not tracker.get("first_prompt_summary"):
        tracker["first_prompt_summary"] = prompt[:200]

    existing_kw = set(tracker.get("keyword_signals", []))
    words = re.findall(r"[a-zA-Z一-鿿]{4,}", prompt)
    for w in words:
        wl = w.lower()
        if wl not in _TOPIC_STOP_WORDS and wl not in existing_kw:
            existing_kw.add(wl)
    sa_config = state.get("_sa_config", {})
    max_kw = sa_config.get("max_keyword_signals", 20)
    tracker["keyword_signals"] = sorted(existing_kw)[:max_kw]

    related = tracker.get("related_episodic", [])
    for name in newly_injected:
        if name.startswith("episodic-") and name not in related:
            related.append(name)
    tracker["related_episodic"] = related


# ─── Vector Observation Log + Semantic Search (was wg_intent) ───────────────

_RANKED_FLOOR = 0.55
_VECTOR_OBS_LOG = CLAUDE_DIR / "Logs" / "vector-observation.log"
_vector_obs_logger: Optional[logging.Logger] = None
_vector_obs_logger_failed: bool = False


def _get_vector_obs_logger() -> Optional[logging.Logger]:
    global _vector_obs_logger, _vector_obs_logger_failed
    if _vector_obs_logger is not None:
        return _vector_obs_logger
    if _vector_obs_logger_failed:
        return None
    try:
        _VECTOR_OBS_LOG.parent.mkdir(parents=True, exist_ok=True)
        lg = logging.getLogger("wg.vector_obs")
        lg.setLevel(logging.INFO)
        lg.propagate = False
        if not lg.handlers:
            h = logging.handlers.RotatingFileHandler(
                str(_VECTOR_OBS_LOG),
                maxBytes=2_000_000,
                backupCount=3,
                encoding="utf-8",
                delay=True,
            )
            h.setFormatter(logging.Formatter("%(message)s"))
            lg.addHandler(h)
        _vector_obs_logger = lg
        return lg
    except Exception as e:
        _atom_debug_error("vector_obs:logger_init", e)
        _vector_obs_logger_failed = True
        return None


def _log_vector_obs(
    session_id: Optional[str],
    fn: str,
    flag_state: str,
    result_count: int,
    fallback_used: bool,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    lg = _get_vector_obs_logger()
    if lg is None:
        return
    rec: Dict[str, Any] = {
        "ts": time.time(),
        "session_id": session_id or "",
        "fn": fn,
        "flag_state": flag_state,
        "result_count": result_count,
        "fallback_used": fallback_used,
    }
    if extra:
        rec.update(extra)
    try:
        lg.info(json.dumps(rec, ensure_ascii=False))
    except Exception as e:
        _atom_debug_error("vector_obs:write", e)


def _search_episodic_context(
    prompt: str, config: Dict[str, Any], session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Query /search/episodic for related past sessions. First-prompt only."""
    vs_config = config.get("vector_search", {})
    if not vs_config.get("enabled", True):
        _log_vector_obs(session_id, "_search_episodic_context", "disabled", 0, True)
        return []
    sc_config = config.get("session_context", {})
    if not sc_config.get("enabled", True):
        _log_vector_obs(session_id, "_search_episodic_context", "disabled", 0, True)
        return []
    if not (WORKFLOW_DIR / "vector_ready.flag").exists():
        _log_vector_obs(session_id, "_search_episodic_context", "no_flag", 0, True)
        return []

    port = vs_config.get("service_port", 3849)
    top_k = sc_config.get("max_episodic", 3)
    min_score = sc_config.get("min_score", 0.35)
    timeout_s = sc_config.get("search_timeout_ms", 8000) / 1000.0

    try:
        params = urllib.parse.urlencode({
            "q": prompt, "top_k": top_k, "min_score": min_score,
        })
        url = f"http://127.0.0.1:{port}/search/episodic?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            results = json.loads(resp.read())
        _log_vector_obs(
            session_id, "_search_episodic_context", "ready",
            len(results) if isinstance(results, list) else 0, False,
        )
        return results
    except Exception as e:
        _atom_debug_error("注入:_search_episodic_context", e)
        _log_vector_obs(
            session_id, "_search_episodic_context", "error", 0, True,
            extra={"err": str(e)[:120]},
        )
        return []


def _build_session_context(episodic_results: List[Dict[str, Any]]) -> List[str]:
    """Build compact [Session:Context] block from episodic search results."""
    if not episodic_results:
        return []

    context_lines = ["[Session:Context] Related past sessions:"]
    char_budget = 600

    for ep in episodic_results:
        name = ep.get("atom_name", "")
        created = ep.get("created", ep.get("last_used", ""))
        summary = ep.get("summary", "")

        slug = name
        if name.startswith("episodic-") and len(name) > 18:
            slug = name[18:]

        line = f"- [{created}] {slug}: {summary[:120]}"
        if len(line) > char_budget:
            break
        context_lines.append(line)
        char_budget -= len(line)

    return context_lines if len(context_lines) > 1 else []


def _detect_cross_session_patterns(
    episodic_results: List[Dict[str, Any]], prompt: str
) -> List[str]:
    if len(episodic_results) < 2:
        return []

    topic_counts: Counter = Counter()
    for ep in episodic_results:
        for kw in ep.get("triggers", []):
            if kw not in ("session", "episodic"):
                topic_counts[kw] += 1

    prompt_kw = set(
        w.lower() for w in re.findall(r"[a-zA-Z一-鿿]{4,}", prompt)
        if w.lower() not in _TOPIC_STOP_WORDS
    )

    recurring = [kw for kw in prompt_kw if topic_counts.get(kw, 0) >= 2]
    return recurring


def _proactive_classify(
    state: Dict[str, Any],
    episodic_results: List[Dict[str, Any]],
    prompt: str,
    config: Dict[str, Any],
) -> List[str]:
    pro_config = config.get("proactive", {})
    lines: List[str] = []

    recurring = _detect_cross_session_patterns(episodic_results, prompt)
    pattern_threshold = pro_config.get("pattern_threshold", 2)
    if recurring:
        atom_index = state.get("atom_index", {})
        existing_names = set()
        for entry in atom_index.get("global", []):
            existing_names.add(entry[0].lower())
        for entry in atom_index.get("project", []):
            existing_names.add(entry[0].lower())

        novel_themes = [kw for kw in recurring if kw not in existing_names]
        if novel_themes:
            themes_str = ", ".join(novel_themes[:3])
            ep_count = len(episodic_results)
            lines.append(
                f"\U0001f4a1 [Proactive] 主題 \"{themes_str}\" 在最近 {ep_count} 個 session 反覆出現。"
                " 建議建立專屬 semantic atom 來長期保存相關知識。"
            )

    migration_threshold = pro_config.get("migration_hint_threshold", 3)
    for ep in episodic_results:
        name = ep.get("atom_name", "")
        confirms = 0
        try:
            confirms = int(ep.get("confirmations", 0) if ep.get("confirmations") else 0)
        except (ValueError, TypeError):
            pass
        if confirms >= migration_threshold:
            lines.append(
                f"❓ {name} 已被 {confirms}+ 次 session 引用。"
                " 核心知識是否應遷移到專屬 atom？"
            )

    return lines


def _semantic_search(
    prompt: str, config: Dict[str, Any], intent: str = "general",
    user: Optional[str] = None,
    roles: Optional[List[str]] = None,
    session_id: Optional[str] = None,
) -> List[Tuple[str, str, List[str], List[Dict]]]:
    """Query Memory Vector Service with intent-aware ranked search."""
    vs_config = config.get("vector_search", {})
    if not vs_config.get("enabled", True):
        _log_vector_obs(session_id, "_semantic_search", "disabled", 0, True,
                        extra={"intent": intent})
        return []
    if not (WORKFLOW_DIR / "vector_ready.flag").exists():
        _log_vector_obs(session_id, "_semantic_search", "no_flag", 0, True,
                        extra={"intent": intent})
        return []
    port = vs_config.get("service_port", 3849)
    top_k = vs_config.get("search_top_k", 5)
    min_score = vs_config.get("search_min_score", 0.65)
    timeout_s = vs_config.get("search_timeout_ms", 8000) / 1000.0

    try:
        def _add_identity(p: Dict[str, Any]) -> Dict[str, Any]:
            if user:
                p["user"] = user
            if roles:
                p["roles"] = ",".join(roles)
            return p

        use_sections = True
        params_dict = _add_identity({
            "q": prompt, "top_k": top_k,
            "min_score": min(min_score, _RANKED_FLOOR),
            "intent": intent,
            "max_sections": 3,
        })
        params = urllib.parse.urlencode(params_dict)
        url = f"http://127.0.0.1:{port}/search/ranked-sections?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                results = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                use_sections = False
                params_dict = _add_identity({
                    "q": prompt, "top_k": top_k,
                    "min_score": min(min_score, _RANKED_FLOOR),
                    "intent": intent,
                })
                params = urllib.parse.urlencode(params_dict)
                url = f"http://127.0.0.1:{port}/search/ranked?{params}"
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    results = json.loads(resp.read())
            else:
                raise

        entries: List[Tuple[str, str, List[str], List[Dict]]] = []
        seen = set()
        for r in results:
            name = r.get("atom_name", "")
            if name and name not in seen:
                sections = r.get("sections", []) if use_sections else []
                entries.append((name, r.get("file_path", ""), [], sections))
                seen.add(name)
        _log_vector_obs(
            session_id, "_semantic_search", "ready", len(entries), False,
            extra={"intent": intent, "use_sections": use_sections},
        )
        return entries
    except Exception as e:
        _atom_debug_error("注入:_semantic_search", e)
        _log_vector_obs(
            session_id, "_semantic_search", "error", 0, True,
            extra={"intent": intent, "err": str(e)[:120]},
        )
        return []


def _trigger_incremental_index(config: Dict[str, Any]) -> None:
    """Non-blocking request to re-index changed atoms."""
    vs_config = config.get("vector_search", {})
    if not vs_config.get("auto_index_on_change", True):
        return
    port = vs_config.get("service_port", 3849)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/index/incremental",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=1)
    except Exception as e:
        _atom_debug_error("注入:_trigger_incremental_index", e)


# ─── V5+ Realm 維度：SessionEnd 自動歸類搬移 sweep ──────────────────────────


def _load_tool_module(filename: str, mod_name: str):
    """以 spec_from_file_location 載 tools/ 下單檔模組（self-sufficient sys.path）。失敗→None。"""
    try:
        import importlib.util
        p = CLAUDE_DIR / "tools" / filename
        spec = importlib.util.spec_from_file_location(mod_name, p)
        if spec is None or spec.loader is None:
            return None
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    except Exception as e:
        _atom_debug_error(f"realm:load_{mod_name}", e)
        return None


def _read_atom_excerpt(rel_path: str, limit: int = 800) -> str:
    """讀 atom 內文摘要供 LLM 判定（utf-8-sig 容 BOM）。失敗→''。"""
    try:
        return (CLAUDE_DIR / rel_path).read_text(encoding="utf-8-sig")[:limit]
    except OSError:
        return ""


def _trigger_sync_memory_index() -> None:
    """搬移後 fire-and-forget 重產 MEMORY.md / _local_catalog.md / per-level _INDEX.md。

    set_realm 只改 _atom_index.json，不重產 catalog；故搬移後須補觸發（對拍 server.js 行為）。
    """
    try:
        import subprocess
        # Windows: 不帶 CREATE_NO_WINDOW 會讓 fire-and-forget 子行程另開可見 console 視窗
        _no_window = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(
            [sys.executable, str(CLAUDE_DIR / "tools" / "sync-memory-index.py"), "--write"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(CLAUDE_DIR),
            creationflags=_no_window,
        )
    except Exception as e:
        _atom_debug_error("realm:sync_index", e)


def _scan_doc_refs(moved: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """搬移後掃**人面向說明文件**是否仍含舊 path/檔名引用（移檔非建檔特有；user 補充）。

    回 {slug: [需同步的 rel 文件...]}。只掃 _AIDocs/（排除 atom 物理區 Failures/_atoms，
    那裡的 slug 引用是 atom-atom Related、搬 path 不斷）＋根層 README/TECH。advisory only。
    """
    docs: List[Path] = []
    aidocs = CLAUDE_DIR / "_AIDocs"
    if aidocs.is_dir():
        for p in aidocs.rglob("*.md"):
            rel = p.relative_to(CLAUDE_DIR).as_posix()
            if rel.startswith("_AIDocs/Failures/") or rel.startswith("_AIDocs/_atoms/"):
                continue
            docs.append(p)
    for fn in ("README.md", "TECH.md"):
        p = CLAUDE_DIR / fn
        if p.exists():
            docs.append(p)
    cache = {}
    for p in docs:
        try:
            cache[p] = p.read_text(encoding="utf-8")
        except OSError:
            continue
    refs: Dict[str, List[str]] = {}
    for m in moved:
        slug, frm = m.get("slug", ""), m.get("from", "")
        fname = frm.rsplit("/", 1)[-1] if frm else f"{slug}.md"
        hits = sorted({
            p.relative_to(CLAUDE_DIR).as_posix()
            for p, txt in cache.items() if (frm and frm in txt) or fname in txt
        })
        if hits:
            refs[slug] = hits
    return refs


def _sweep_realm_auto_migrate(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """SessionEnd：掃全域 core atom，自動歸 local（drift 補捉）。非熱路徑。

    兩段判定：① 詞庫（deterministic，含 py-only learned 補 recall）命中 local → 搬；
    ② 詞庫 miss 的「unknown core」（非 protected）→ 喚 LLM（計畫 Fail-safe 表）：
      error（基礎設施失敗）→ defer 留原地（**防 Ollama 離線把全部掃進 Else**）；
      core → 留；local≥門檻 → 搬 canon domain + 學詞；unsure/低信心 → Else。
    安全網：核心保護硬擋（protected）永不喚 LLM、永不搬；set_realm 原子搬（含 .access.json）/
      可 undo（--to-core）；max_per_session 限額；搬移寫 marker（含 via + doc-ref）不靜默。
    回 list of {slug, domain, from, to, via}（空 = 無搬移）。
    """
    if classify_realm is None or is_local_realm_path is None or load_atom_index_json is None:
        return []
    realm_cfg = config.get("realm", {})
    if not realm_cfg.get("auto_migrate", True):
        return []

    llm_cfg = realm_cfg.get("llm_fallback", {})
    llm_enabled = bool(llm_cfg.get("enabled", False))
    max_llm = int(llm_cfg.get("max_per_session", 5))
    min_conf = float(llm_cfg.get("min_confidence", 0.7))
    learned = load_learned_lexicon() if load_learned_lexicon else {}
    default_dom = LOCAL_REALM_DEFAULT_DOMAIN

    moved: List[Dict[str, Any]] = []
    learned_add: Dict[str, str] = {}
    llm_calls = 0
    try:
        mod = _load_tool_module("atom-set-realm.py", "atom_set_realm")
        if mod is None:
            return []
        llm_mod = _load_tool_module("realm_llm_classify.py", "realm_llm_classify") if llm_enabled else None
        existing_paths = list(enumerate_local_paths(MEMORY_DIR)) if enumerate_local_paths else []

        data = load_atom_index_json(MEMORY_DIR)
        for a in data.get("atoms", []):
            name = a.get("name", "")
            path = a.get("path", "")
            if not name or is_local_realm_path(path):
                continue  # 已 local，跳過（idempotent）
            rc = classify_realm(name, a.get("triggers", []), extra_lexicon=learned or None)

            target_dom: Optional[str] = None
            via: Optional[str] = None
            if rc.get("realm") == "local":
                target_dom, via = rc.get("domain"), "lex"
            elif rc.get("protected"):
                continue  # 核心保護硬擋：永不喚 LLM、永不搬
            elif llm_mod is not None and llm_calls < max_llm:
                llm_calls += 1
                lr = llm_mod.llm_classify_realm(
                    name, a.get("triggers", []), _read_atom_excerpt(path), existing_paths, config)
                realm = lr.get("realm")
                if realm in ("error", "core"):
                    continue  # 基礎設施失敗→defer / LLM 確信核心→留
                if realm == "local" and lr.get("confidence", 0.0) >= min_conf:
                    target_dom, via = lr.get("domain_path") or default_dom, "LLM"
                    for t in lr.get("terms", []):
                        learned_add[t] = target_dom
                    if target_dom:  # 新分支同 session 後續可複用
                        existing_paths = sorted(set(existing_paths) | {target_dom})
                else:  # unsure / 低信心 local → catch-all
                    target_dom, via = default_dom, "Else"
            else:
                continue  # LLM 未啟用 / 額度用罄 → 留 core（defer）

            if not target_dom:
                continue
            res = mod.set_realm(name, domain=target_dom)
            if res.get("ok") and not res.get("noop"):
                moved.append({
                    "slug": name, "domain": target_dom, "via": via,
                    "from": res.get("from"), "to": res.get("to"),
                })
    except Exception as e:
        _atom_debug_error("realm:auto_sweep", e)

    # 收尾：學詞回寫 → marker（含 via + doc-ref）→ 補觸發 catalog 重產
    if learned_add and append_learned_terms:
        try:
            append_learned_terms(learned_add)
        except Exception as e:
            _atom_debug_error("realm:learned_append", e)

    if moved:
        doc_refs = {}
        try:
            doc_refs = _scan_doc_refs(moved)
        except Exception as e:
            _atom_debug_error("realm:doc_ref_scan", e)
        try:
            REALM_AUTOMOVE_MARKER.parent.mkdir(parents=True, exist_ok=True)
            existing: List[Dict[str, Any]] = []
            if REALM_AUTOMOVE_MARKER.exists():
                try:
                    prev = json.loads(REALM_AUTOMOVE_MARKER.read_text(encoding="utf-8"))
                    if isinstance(prev, list):
                        existing = prev
                except (OSError, json.JSONDecodeError):
                    existing = []
            payload = list(moved)
            if doc_refs:  # 附在首筆，SessionStart 統一呈現
                payload[0] = {**payload[0], "doc_refs": doc_refs}
            existing.extend(payload)
            REALM_AUTOMOVE_MARKER.write_text(
                json.dumps(existing, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            _atom_debug_error("realm:automove_marker", e)
        _trigger_sync_memory_index()
    return moved


# ─── Self-Iteration: atom 晉升 (was wg_iteration._self_iterate_atoms) ────────


def _self_iterate_atoms(
    state: Dict[str, Any], config: Dict[str, Any]
) -> Dict[str, Any]:
    """V2.16/Phase 2: Atom decay scoring + 效用驅動 [臨]→[觀] auto-promotion.

    Runs at SessionEnd. Scans all atom files, calculates health scores,
    auto-promotes [臨] items in mature atoms, reports archive/demote candidates.

    Phase 2 (#2)：
      - 慢衰減：每顆 atom α←1+λ(α−1); β←1+λ(β−1)（λ≈0.97），把效用證據往 prior 拉。
      - 晉升閘改由「真實 Confirmations 主軌 + 效用 Wilson 下界」驅動；
        ReadHits 降為純曝光計數，不再單獨觸發晉升（取代 Phase 0 過渡）。
      - Wilson 下界 ≤ demote_lb 且 n≥min_n → 列降級候選（不自動降，留裁決）。
    """
    si_config = config.get("self_iteration", {})
    u_config = config.get("usefulness", {}) or {}
    decay_half_life = si_config.get("decay_half_life_days", 30)
    promote_conf_threshold = si_config.get("promote_confirmations_threshold", 4)
    archive_threshold = si_config.get("archive_score_threshold", 0.3)
    # Phase 2 效用旋鈕（py↔js 鏡像：server.js）
    decay_lambda = float(u_config.get("decay_lambda", 0.97))
    promote_lb = float(u_config.get("promote_lb", 0.6))
    demote_lb = float(u_config.get("demote_lb", 0.35))
    min_n = int(u_config.get("min_n", 3))
    wilson_z = float(u_config.get("wilson_z", 1.96))

    results = {"promoted": [], "archive_candidates": [],
               "demote_candidates": [], "scanned": 0}
    today = datetime.now()

    # V5+: 全域 atom 搜尋（memory + _AIDocs/Failures/）統一委派 lib.atom_locations。
    # 判定走 is_atom_file（同 MEMORY.md/_*/SPEC_* skip）+ failures stems 過濾參考文件。
    if iter_atom_files_multi is not None:
        md_files_iter = iter_atom_files_multi()
    else:
        md_files_iter = (m for m in MEMORY_DIR.glob("*.md")
                         if m.name not in ("MEMORY.md", "SPEC_Atomic_Memory_System.md")
                         and not m.name.startswith("_"))

    for md_file in md_files_iter:
        try:
            text = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        results["scanned"] += 1

        try:
            from lib.atom_access import (
                read_access, decay_usefulness,
                usefulness_stats, usefulness_promote_eligible,
                usefulness_demote_candidate,
            )
            acc = read_access(md_file)
            # Step 6 慢衰減（SessionEnd）：把 (α,β) 往 prior 拉，回填衰減後值供晉升判定
            try:
                na, nb = decay_usefulness(
                    md_file, lam=decay_lambda, source="hook:atom-decay")
                acc["useful_hits"], acc["used_fail"] = na, nb
            except (OSError, ValueError):
                pass
        except (ImportError, OSError):
            acc = {}
            usefulness_stats = None  # type: ignore
            usefulness_promote_eligible = None  # type: ignore
            usefulness_demote_candidate = None  # type: ignore
        last_used_raw = acc.get("last_used")
        confirmations = int(acc.get("confirmations") or 0)
        readhits = int(acc.get("read_hits") or 0)
        u_stats = usefulness_stats(acc, z=wilson_z) if usefulness_stats else {"n": 0}
        has_use_evidence = u_stats.get("n", 0) > 0

        # 無任何活動訊號（注入/確認/效用）→ 跳過
        if not last_used_raw or (
            confirmations == 0 and readhits == 0 and not has_use_evidence
        ):
            continue
        try:
            last_used = datetime.strptime(last_used_raw, "%Y-%m-%d")
        except ValueError:
            continue

        days_since = (today - last_used).days
        recency = math.exp(-math.log(2) * max(days_since, 0) / decay_half_life)
        usage = min(1.0, math.log10(max(confirmations, readhits) + 1) / 2)
        score = 0.5 * recency + 0.5 * usage

        if score < archive_threshold:
            results["archive_candidates"].append({
                "atom": md_file.stem,
                "score": round(score, 3),
                "last_used": last_used_raw,
                "confirmations": confirmations,
            })

        # Phase 2: 晉升 = 真實 Confirmations 主軌 OR 效用 Wilson 下界（升≥promote_lb 且 n≥min_n）。
        # ReadHits 降為純曝光，不再參與晉升（取代 Phase 0 readhits 輔助門）。
        # py↔js 鏡像：server.js toolAtomPromote usefulness gate。
        util_eligible = bool(
            usefulness_promote_eligible
            and usefulness_promote_eligible(
                acc, promote_lb=promote_lb, min_n=min_n, z=wilson_z)
        )
        promote_method = "confirmations" if confirmations >= promote_conf_threshold else "usefulness"
        if confirmations >= promote_conf_threshold or util_eligible:
            lines = text.split("\n")
            promoted_in_file = []
            changed = False
            for i, line in enumerate(lines):
                if re.match(r"^- \[臨\]", line):
                    lines[i] = line.replace("- [臨]", "- [觀]", 1)
                    desc = line.split("[臨]", 1)[-1].strip()[:60]
                    promoted_in_file.append(desc)
                    changed = True

            if changed:
                prefixes = set()
                for L in lines:
                    pm = re.match(r"^- \[([臨觀固])\]", L)
                    if pm:
                        prefixes.add(pm.group(1))
                header_promoted = False
                if prefixes == {"觀"}:
                    for i, line in enumerate(lines):
                        hm = re.match(r"^(- Confidence:\s*)\[臨\]\s*$", line)
                        if hm:
                            lines[i] = f"{hm.group(1)}[觀]"
                            header_promoted = True
                            break

                tmp = md_file.with_suffix(".tmp")
                try:
                    tmp.write_text("\n".join(lines), encoding="utf-8")
                    tmp.replace(md_file)
                except OSError:
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
                results["promoted"].append({
                    "atom": md_file.stem,
                    "items": promoted_in_file,
                    "confirmations": confirmations,
                    "method": promote_method,
                    "lower_bound": round(u_stats.get("lower_bound", 0.0), 3),
                })
                log_promotion_audit(
                    "auto_observe", md_file.stem,
                    items=len(promoted_in_file),
                    confirmations=confirmations,
                    header_promoted=header_promoted,
                    method=promote_method,
                    lower_bound=round(u_stats.get("lower_bound", 0.0), 3),
                )

        # Phase 2: 效用 Wilson 下界 ≤ demote_lb 且 n≥min_n、且仍有非[臨]條目 → 降級候選
        # （不自動降，屬敏感裁決；列入 staging 報告供管理職審視）。
        if (usefulness_demote_candidate
                and usefulness_demote_candidate(
                    acc, demote_lb=demote_lb, min_n=min_n, z=wilson_z)
                and re.search(r"^- \[(觀|固)\]", text, re.MULTILINE)):
            results["demote_candidates"].append({
                "atom": md_file.stem,
                "lower_bound": round(u_stats.get("lower_bound", 0.0), 3),
                "alpha": u_stats.get("alpha"),
                "beta": u_stats.get("beta"),
                "n": u_stats.get("n"),
            })

    if results["archive_candidates"] or results["demote_candidates"]:
        cwd = state.get("session", {}).get("cwd", "")
        staging = resolve_staging_dir(cwd)
        staging.mkdir(exist_ok=True)
        out_lines = [
            f"# Archive / Demote Candidates ({today.strftime('%Y-%m-%d')})\n",
        ]
        if results["archive_candidates"]:
            out_lines.append(f"## 封存候選（score < {archive_threshold}）\n")
            for c in results["archive_candidates"]:
                out_lines.append(
                    f"- **{c['atom']}** — score={c['score']}, "
                    f"last_used={c['last_used']}, confirmations={c['confirmations']}"
                )
        if results["demote_candidates"]:
            out_lines.append(
                f"\n## 降級候選（效用 Wilson 下界 ≤ {demote_lb}，n≥{min_n}；需裁決）\n")
            for c in results["demote_candidates"]:
                out_lines.append(
                    f"- **{c['atom']}** — lower_bound={c['lower_bound']}, "
                    f"α={c['alpha']}, β={c['beta']}, n={c['n']}"
                )
        (staging / "archive-candidates.md").write_text(
            "\n".join(out_lines), encoding="utf-8"
        )

    return results
