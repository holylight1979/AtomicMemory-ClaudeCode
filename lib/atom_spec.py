"""atom_spec.py — 全系統「什麼是合法 atom」的唯一規則來源

純資料 + 純函式，零 IO（除 resolve_scope_dir 需訪問 fs 標記）。
被 memory-audit / atom-health-check / atom_io 共用 import，避免規則漂移。

行為等價對拍 server.js: slugify / buildAtomContent / validateAtomContent / resolveMemDir
（V4 SPEC §4 metadata 順序、§8 scope dir 結構）。
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional


# ─── Constants（單一規則來源） ───────────────────────────────────────────────

# 子目錄跳過清單（rglob 掃描時用）
# - feedback/: 行為 atom，必掃
# - personal/: V4 user role 宣告檔（role.md），非 atom
# - wisdom/: Wisdom Engine 設計文件（DESIGN.md），非 atom（用設計文件章節）
# - episodic/: auto-generated session 摘要，使用 ## 摘要 章節，與 atom 格式不同
# - _pending_review/: shared 敏感原子待裁決區，非活躍 atom
SKIP_DIRS = frozenset({
    "_meta", "_reference", "_staging", "_vectordb", "_distant",
    "episodic", "templates", "personal", "wisdom", "_pending_review",
})

# 系統檔前綴（檔名等級跳過）
SKIP_PREFIXES = ("SPEC_", "_")

# 索引檔名稱
MEMORY_INDEX = "MEMORY.md"
ATOM_INDEX = "_ATOM_INDEX.md"

# Last-used / Confirmations / ReadHits 居 <atom>.access.json，
# 故 atom .md 不再 require 這些欄位（OPTIONAL_METADATA 仍接受 legacy 欄位過渡）。
REQUIRED_METADATA = frozenset({"Scope", "Confidence", "Trigger"})
OPTIONAL_METADATA = frozenset({
    "Last-used", "Confirmations", "ReadHits",  # legacy 過渡欄；migration 後清空
    "Privacy", "Source", "Type", "Created", "TTL",
    "Expires-at", "Tags", "Related", "Supersedes", "Quality",
    "Audience", "Author", "Pending-review-by", "Merge-strategy", "Created-at",
    "Depends", "Evidence",  # 壞滅緣（validity conditions）/ 證據等級（了義裁決）
})

# 行動 always required; 知識 or 印象（指標型 atom 變體）二選一
REQUIRED_SECTIONS = frozenset({"行動"})
KNOWLEDGE_SECTIONS = frozenset({"知識", "印象"})

VALID_CONFIDENCE = frozenset({"[固]", "[觀]", "[臨]"})
VALID_SCOPES = frozenset({"global", "shared", "role", "personal"})

# ─── Depends（壞滅緣 validity conditions）/ Evidence（證據等級） ────────────────
# 兩欄皆 optional：既有 atom 缺欄位一律靜默通過（向後相容鐵則）。
# Depends 條目兩型：
#   - path 型 `path:<相對或~路徑>` — 機器可驗（存在性）；相對路徑以 ~/.claude 為根
#   - 自由文字型（如 `decision:xxx`、版本描述）— 不可驗，僅展示
DEPENDS_PATH_PREFIX = "path:"

# Evidence：實證（實際跑過/測過）> 引述（文件/網路來源）> 推測（模型推斷）> 未標
VALID_EVIDENCE = frozenset({"實證", "引述", "推測"})
EVIDENCE_RANK = {"實證": 3, "引述": 2, "推測": 1}  # 未標/非法 = 0

TRIGGER_MIN = 3
TRIGGER_MAX = 12
ATOM_MAX_LINES = 200
INDEX_MAX_LINES = 40


# ─── Pure functions ───────────────────────────────────────────────────────────


_SLUG_SPACE_RE = re.compile(r"[\s_]+")
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9一-鿿㐀-䶿-]")
_SLUG_DASH_RE = re.compile(r"-+")


def slugify(title: str) -> str:
    """Atom 檔名 slug。對拍 server.js:655-663 行為等價。

    規則：lowercase → 空白/底線→`-` → 非 ascii/cjk/dash 剝除 → 連續 dash 合併 → trim dash
    """
    s = (title or "").lower()
    s = _SLUG_SPACE_RE.sub("-", s)
    s = _SLUG_STRIP_RE.sub("", s)
    s = _SLUG_DASH_RE.sub("-", s)
    s = s.strip("-")
    return s or "untitled"


def is_atom_file(path: Path, memory_root: Path) -> bool:
    """判斷一個 .md 是否為合法 atom 檔（會被 audit/health/index 計入）。

    排除：MEMORY.md / _ATOM_INDEX.md / SPEC_* / _* 前綴 / SKIP_DIRS 中間目錄。
    """
    if not path.is_file() or path.suffix != ".md":
        return False
    if path.name == MEMORY_INDEX or path.name == ATOM_INDEX:
        return False
    if any(path.name.startswith(p) for p in SKIP_PREFIXES):
        return False
    try:
        rel_parts = path.relative_to(memory_root).parts
    except ValueError:
        return False
    # rel_parts: directory parts + filename. Check intermediate dirs only.
    if any(part in SKIP_DIRS for part in rel_parts[:-1]):
        return False
    return True


_META_LINE_RE = re.compile(r"^-\s+([\w-]+):\s*(.+)$")


def parse_frontmatter(content: str) -> Dict[str, str]:
    """解析 atom-style metadata block（`- Key: Value` 列表）。

    從 # 標題後的連續 `- Key: Value` 區塊抽 metadata；遇空行/`##` 結束。
    支援 BOM。回傳 dict（無 `_format` key — atom_spec 不關心 Claude-native YAML）。
    """
    if content.startswith("﻿"):
        content = content[1:]
    fm: Dict[str, str] = {}
    in_meta = False
    for line in content.splitlines():
        if line.startswith("- "):
            m = _META_LINE_RE.match(line)
            if m:
                fm[m.group(1)] = m.group(2).strip()
                in_meta = True
        elif in_meta and (line.strip() == "" or line.startswith("##")):
            break
    return fm


def parse_depends(raw: Optional[str]) -> List[Dict[str, str]]:
    """解析 `- Depends:` 值（逗號分隔）為 typed 條目清單。

    回傳 [{"type": "path"|"free", "value": str}, ...]：
      - path 型：`path:<路徑>` → value 為去前綴後的路徑字串（可為空 → 格式警告）
      - free 型：其他任何條目（decision:xxx、版本描述等）原文保留
    空/None 輸入回傳空清單（欄位 optional，缺欄靜默）。
    """
    entries: List[Dict[str, str]] = []
    for item in re.split(r"[,，]", raw or ""):
        item = item.strip()
        if not item:
            continue
        if item.startswith(DEPENDS_PATH_PREFIX):
            entries.append({"type": "path",
                            "value": item[len(DEPENDS_PATH_PREFIX):].strip()})
        else:
            entries.append({"type": "free", "value": item})
    return entries


def resolve_depends_path(value: str, claude_dir: Optional[Path] = None) -> Path:
    """path 型 Depends 條目 → 絕對路徑。

    - `~` 開頭 → expanduser
    - 絕對路徑 → 原樣
    - 相對路徑 → 以 claude_dir（預設 ~/.claude）為根
    """
    claude_dir = claude_dir or Path.home() / ".claude"
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = claude_dir / p
    return p


def depends_warnings(raw: Optional[str]) -> List[str]:
    """Depends 值的格式警告（warning 級，不 fail；缺欄/空值不警告）。"""
    warns: List[str] = []
    for e in parse_depends(raw):
        if e["type"] == "path" and not e["value"]:
            warns.append("Depends 條目 `path:` 缺路徑值")
    return warns


def parse_evidence(raw: Optional[str]) -> Optional[str]:
    """解析 `- Evidence:` 值。合法值原樣回傳；缺欄/空/非法 → None（視同未標）。"""
    v = (raw or "").strip()
    return v if v in VALID_EVIDENCE else None


def evidence_warning(raw: Optional[str]) -> Optional[str]:
    """Evidence 非法值警告（warning 級，不 fail）。缺欄/空值回 None（optional）。"""
    v = (raw or "").strip()
    if v and v not in VALID_EVIDENCE:
        return f"Evidence 值無效: {v}（應為 實證/引述/推測）"
    return None


def evidence_rank(raw: Optional[str]) -> int:
    """Evidence 裁決權重：實證3 > 引述2 > 推測1 > 未標/非法0。"""
    return EVIDENCE_RANK.get((raw or "").strip(), 0)


def validate_atom_content(content: str) -> Optional[str]:
    """驗證 atom 內容結構。回傳 None 表通過；錯誤字串表第一個違規。

    對拍 server.js:724-742 validateAtomContent 行為等價。
    （注意：不檢 REQUIRED_METADATA 完整性，那是 audit 報告層級的檢查；
      此函式只驗 build_atom_content 產出契約。）
    """
    if "---\n" in content and content.index("---\n") < 5:
        return "YAML frontmatter (---) is forbidden in atom files"
    if not re.search(r"^# .+", content, re.MULTILINE):
        return "Missing # title heading"
    # 知識 / 印象 二選一（KNOWLEDGE_SECTIONS；指標型 atom 用 ## 印象 取代 ## 知識，
    # 對齊 memory-audit validate_format 的判定）
    if not any(f"## {sec}" in content for sec in KNOWLEDGE_SECTIONS):
        return "Missing ## 知識 or ## 印象 section"
    if "## 行動" not in content:
        return "Missing ## 行動 section"
    m = re.search(r"^- Confidence:\s*(.+)$", content, re.MULTILINE)
    if not m or m.group(1).strip() not in VALID_CONFIDENCE:
        return "Missing or invalid Confidence metadata"
    return None


def _is_block_knowledge(item: str) -> bool:
    """knowledge 元素是否為原樣輸出 block（markdown 表格列，或三反引號 fence）。"""
    s = item.lstrip()
    return s.startswith("|") or s.startswith("```")


def render_knowledge_lines(knowledge: Iterable[str]) -> List[str]:
    """渲染 knowledge 為 ## 知識 區行清單（block-aware）。

    - 一般元素：首行補 `- ` bullet（已 `- ` 開頭不重複），維持多行巢狀 bullet。
    - block 元素（表格/fence）：整段原樣輸出，前後補空行（GFM 渲染需要）。
    對拍 server.js renderKnowledgeLines —— 須 byte-identical。
    """
    out: List[str] = []
    for k in knowledge:
        if _is_block_knowledge(k):
            if out and out[-1] != "":
                out.append("")
            out.extend(k.split("\n"))
            out.append("")
        else:
            out.append(k if k.startswith("- ") else f"- {k}")
    while out and out[-1] == "":
        out.pop()
    return out


def build_atom_content(
    *,
    title: str,
    scope: str,
    confidence: str,
    triggers: Iterable[str],
    knowledge: Iterable[str],
    actions: Optional[Iterable[str]] = None,
    related: Optional[Iterable[str]] = None,
    audience: Optional[Iterable[str]] = None,
    author: Optional[str] = None,
    pending_review_by: Optional[str] = None,
    merge_strategy: Optional[str] = None,
    created_at: Optional[str] = None,
    today: Optional[str] = None,
) -> str:
    """從結構化參數構造 atom 檔內容。

    對拍 server.js:669-721 buildAtomContent —— byte-identical 等價契約。
    SPEC §4 metadata 順序：Scope → Audience → Author → Confidence → Trigger →
    Last-used → Confirmations → ReadHits → Pending-review-by → Merge-strategy →
    Created-at → Related。空值欄位省略。
    """
    today = today or date.today().isoformat()
    triggers_list = list(triggers)
    knowledge_list = list(knowledge)
    actions_list = list(actions) if actions else []
    related_list = list(related) if related else []
    audience_list = list(audience) if audience else []

    lines: List[str] = [f"# {title}", ""]
    lines.append(f"- Scope: {scope}")
    if audience_list:
        lines.append(f"- Audience: {', '.join(audience_list)}")
    if author:
        lines.append(f"- Author: {author}")
    lines.append(f"- Confidence: {confidence}")
    lines.append(f"- Trigger: {', '.join(triggers_list)}")
    # Last-used / Confirmations / ReadHits 居 <atom>.access.json，不再寫入 .md 檔頭
    if pending_review_by:
        lines.append(f"- Pending-review-by: {pending_review_by}")
    if merge_strategy and merge_strategy != "ai-assist":
        lines.append(f"- Merge-strategy: {merge_strategy}")
    lines.append(f"- Created-at: {created_at or today}")
    if related_list:
        lines.append(f"- Related: {', '.join(related_list)}")
    lines.extend(["", "## 知識", ""])
    lines.extend(render_knowledge_lines(knowledge_list))
    lines.extend(["", "## 行動", ""])
    if actions_list:
        for a in actions_list:
            lines.append(a if a.startswith("- ") else f"- {a}")
    else:
        lines.append("- （依知識內容判斷）")
    lines.append("")
    return "\n".join(lines)


def resolve_scope_dir(
    scope: str,
    base_dir: Path,
    role: Optional[str] = None,
    user: Optional[str] = None,
) -> Optional[Path]:
    """V4 scope → 子目錄解析。對拍 server.js:777-824 resolveMemDir 結構部分。

    base_dir 含義：
      - global: ~/.claude/memory/  → 直接回傳 base_dir
      - shared/role/personal: {project_root}/.claude/memory/ → 回傳對應子層

    這支函式只負責結構映射，不做 fs marker 檢查（那是 atom_io 呼叫端職責）。
    無效輸入（unknown scope / 必填欄位缺）回傳 None；caller 自行 raise。
    """
    if scope == "global":
        return base_dir
    if scope == "shared":
        return base_dir / "shared"
    if scope == "role":
        if not role:
            return None
        return base_dir / "roles" / role
    if scope == "personal":
        if not user:
            return None
        return base_dir / "personal" / user
    return None


# ─── Helpers used by audit/health-check ───────────────────────────────────────


def iter_atom_files(memory_root: Path):
    """yield memory_root 下所有合法 atom .md（遞迴）。

    audit/health-check 共用，以 is_atom_file 為唯一判定。
    """
    if not memory_root.is_dir():
        return
    for md in sorted(memory_root.rglob("*.md")):
        if is_atom_file(md, memory_root):
            yield md


# V5+ 多 root atom 搜尋與物理位置規則已搬到 lib/atom_locations.py
# （atom_spec 只負責「什麼是合法 atom」；路徑/路由屬 atom_locations 範疇）
