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
    MEMORY_INDEX, ATOM_INDEX,
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
    except Exception:
        pass

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
    except Exception:
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
    except Exception:
        pass


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


# ─── Self-Iteration: atom 晉升 (was wg_iteration._self_iterate_atoms) ────────


def _self_iterate_atoms(
    state: Dict[str, Any], config: Dict[str, Any]
) -> Dict[str, Any]:
    """V2.16: Automated atom decay scoring + [臨]→[觀] auto-promotion.

    Runs at SessionEnd. Scans all atom files, calculates health scores,
    auto-promotes [臨] items in mature atoms, reports archive candidates.
    """
    si_config = config.get("self_iteration", {})
    decay_half_life = si_config.get("decay_half_life_days", 30)
    promote_conf_threshold = si_config.get("promote_confirmations_threshold", 4)
    promote_min_conf = si_config.get("promote_min_confirmations", 20)
    archive_threshold = si_config.get("archive_score_threshold", 0.3)

    results = {"promoted": [], "archive_candidates": [], "scanned": 0}
    today = datetime.now()

    scan_dirs = [MEMORY_DIR]
    failure_dir = MEMORY_DIR / "failures"
    if failure_dir.exists():
        scan_dirs.append(failure_dir)
    feedback_dir = MEMORY_DIR / "feedback"
    if feedback_dir.exists():
        scan_dirs.append(feedback_dir)

    for atom_dir in scan_dirs:
        for md_file in atom_dir.glob("*.md"):
            if md_file.name in ("MEMORY.md", "SPEC_Atomic_Memory_System.md"):
                continue
            if md_file.name.startswith("_"):
                continue

            try:
                text = md_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            results["scanned"] += 1

            try:
                from lib.atom_access import read_access
                acc = read_access(md_file)
            except (ImportError, OSError):
                acc = {}
            last_used_raw = acc.get("last_used")
            confirmations = int(acc.get("confirmations") or 0)
            readhits = int(acc.get("read_hits") or 0)

            if not last_used_raw or (confirmations == 0 and readhits == 0):
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

            if confirmations >= promote_conf_threshold or readhits >= promote_min_conf:
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
                    })
                    log_promotion_audit(
                        "auto_observe", md_file.stem,
                        items=len(promoted_in_file),
                        confirmations=confirmations,
                        header_promoted=header_promoted,
                    )

    if results["archive_candidates"]:
        cwd = state.get("session", {}).get("cwd", "")
        staging = resolve_staging_dir(cwd)
        staging.mkdir(exist_ok=True)
        out_lines = [
            f"# Archive Candidates ({today.strftime('%Y-%m-%d')})\n",
            f"Score < {archive_threshold} — 考慮封存或刪除：\n",
        ]
        for c in results["archive_candidates"]:
            out_lines.append(
                f"- **{c['atom']}** — score={c['score']}, "
                f"last_used={c['last_used']}, confirmations={c['confirmations']}"
            )
        (staging / "archive-candidates.md").write_text(
            "\n".join(out_lines), encoding="utf-8"
        )

    return results
