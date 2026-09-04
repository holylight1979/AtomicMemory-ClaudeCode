#!/usr/bin/env python3
"""
memory-audit.py — Atomic Memory System Health Checker

掃描 Claude Code 記憶層（全域 + 專案），驗證 atom 格式、
檢查過期、建議晉升/降級、驗證索引一致性、偵測重複。

Usage:
    python memory-audit.py
    python memory-audit.py --global-only
    python memory-audit.py --project c--Projects
    python memory-audit.py --search-distant handler
    python memory-audit.py --restore path/to/atom.md
    python memory-audit.py --move-distant path/to/atom.md
    python memory-audit.py --json

Requirements: Python 3.8+, no external dependencies.
"""

import sys, io
# Force UTF-8 stdout on Windows (cp950 codepage causes mojibake in JSON output)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# route memory-audit atom writes through funnel
_CLAUDE_DIR = Path.home() / ".claude"
if str(_CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(_CLAUDE_DIR))
from lib.atom_io import write_raw, write_index_full  # noqa: E402

_AUDIT_SOURCE = "tool:memory-audit"

# ─── Single source of truth: lib/atom_spec.py（規則收束） ────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.atom_spec import (
    SKIP_DIRS, SKIP_PREFIXES, REQUIRED_METADATA, OPTIONAL_METADATA,
    REQUIRED_SECTIONS, KNOWLEDGE_SECTIONS, VALID_CONFIDENCE,
    INDEX_MAX_LINES, PROJECT_INDEX_MAX_LINES, ATOM_MAX_LINES, TRIGGER_MIN, TRIGGER_MAX,
    MEMORY_INDEX,
    parse_depends, resolve_depends_path, depends_warnings, evidence_warning,
)
from lib.atom_locations import (
    GLOBAL_MEMORY_DIR, FAILURES_DIR, LEGACY_FAILURES_DIR,
    failures_atom_stems, iter_atom_files_multi,
)
# 晉升判定權威來源（server.js 的 py 鏡像）：confirmations 主軌 + usefulness Wilson 下界軌。
# ReadHits 已退役（純曝光、不參與晉升）。
from lib.atom_access import read_access, usefulness_promote_eligible, move_atom_pair
# _atom_index.json 為索引唯一機器源：delete/restore 必同步（含 _ATOM_INDEX.md mirror regen）
from lib.atom_index_json import (
    delete_atom as index_delete_atom,
    upsert_atom as index_upsert_atom,
    load_atom_index_json,
)
# 範疇資料夾硬規則：memory/ 根下散檔須歸入 memory/<範疇>/。gate 由 workflow/config.json
# taxonomy.gate_enabled 控制；模組缺席時視為關閉（不報 layout error）。
from lib.atom_locations import is_flat_core_path
try:
    from lib.atom_taxonomy import gate_enabled
except ImportError:  # pragma: no cover
    def gate_enabled() -> bool:
        return False

def _failures_file_exists(file_name: str) -> bool:
    """失敗家族檔存在性：memory/Failures/ 樹（含 <主題>/ 子夾）優先，再退舊址 _AIDocs/Failures/。"""
    for root in (FAILURES_DIR, LEGACY_FAILURES_DIR):
        if not root.is_dir():
            continue
        if (root / file_name).exists() or any(root.rglob(file_name)):
            return True
    return False


# ─── Audit-specific constants（atom_spec 不需共享的） ────────────────────────

# 遺忘政策只有一套：hooks/wg_atoms 的 selective forget（score = 0.5·recency + 0.5·usage，
# score < self_iteration.archive_score_threshold 且非核心保護 → 候選）。本工具的降級候選與
# --enforce 都委派它，不另設天數門檻。
# SYNC: server.js atom_promote — confirmations 主軌（suggest only, not gate）。
# ReadHits 已退役（純曝光、不參與晉升）；usefulness 軌走 lib.atom_access（自帶 lb/min_n 預設）。
PROMOTION_THRESHOLDS = {
    "[臨]": {"confirmations": 4},
    "[觀]": {"confirmations": 10},
}
DISTANT_DIR = "_distant"
VALID_TYPES = {"semantic", "episodic", "procedural"}
VALID_PRIVACY = {"public", "internal", "sensitive"}


def iter_atom_files(mem_dir: Path):
    """yield 合法 atom .md（mem_dir == 全域 memory 時多根掃描：memory/ 含 memory/Failures/、
    舊址 _AIDocs/Failures/、_AIDocs/_atoms/）。

    判定統一委派 lib.atom_locations.iter_atom_files_multi（內部用 lib.atom_spec.is_atom_file
    + failures_atom_stems 過濾參考文件）。非全域 mem_dir 只掃單根。
    """
    try:
        is_global = mem_dir.resolve() == GLOBAL_MEMORY_DIR.resolve()
    except OSError:
        is_global = False
    if is_global:
        yield from iter_atom_files_multi()
    else:
        yield from iter_atom_files_multi([mem_dir])


# ─── Data Classes ────────────────────────────────────────────────────────────


@dataclass
class AtomMetadata:
    file_path: Path
    layer_name: str
    title: str = ""
    scope: str = ""
    scope_label: str = ""  # dedup 用（frontmatter 優先，缺則由路徑推斷；對齊 lib/atom_spec.VALID_SCOPES）
    confidence: str = ""
    trigger: List[str] = field(default_factory=list)
    last_used: Optional[date] = None
    confirmations: int = 0
    privacy: str = ""
    source: str = ""
    line_count: int = 0
    sections_found: Set[str] = field(default_factory=set)
    has_evolution_log: bool = False
    evolution_entries: int = 0
    raw_metadata: Dict[str, str] = field(default_factory=dict)
    is_claude_native: bool = False    # True if --- YAML frontmatter (Claude auto-memory)
    had_bad_eol: bool = False         # Fix B: 原始檔含 \r\r\n（雙CR）損壞行尾 → emit warning
    # Optional fields (all with graceful fallback)
    atom_type: str = "semantic"       # semantic/episodic/procedural
    created: Optional[date] = None
    ttl: Optional[str] = None         # e.g. "30d"
    expires_at: Optional[date] = None
    tags: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    supersedes: List[str] = field(default_factory=list)
    quality: Optional[float] = None


@dataclass
class IndexEntry:
    atom_name: str
    path: str
    trigger: str
    confidence: str = ""


@dataclass
class Issue:
    file: str
    level: str  # "error", "warning", "info"
    category: str
    message: str


@dataclass
class Suggestion:
    file: str
    current: str
    suggested: str
    reason: str


@dataclass
class DuplicatePair:
    file_a: str
    file_b: str
    shared_triggers: List[str]
    title_match: bool


@dataclass
class HealthReport:
    scan_date: date = field(default_factory=date.today)
    layers_scanned: List[str] = field(default_factory=list)
    total_atoms: int = 0
    confidence_counts: Dict[str, int] = field(default_factory=dict)
    issues: List[Issue] = field(default_factory=list)
    promotions: List[Suggestion] = field(default_factory=list)
    demotions: List[Suggestion] = field(default_factory=list)
    duplicates: List[DuplicatePair] = field(default_factory=list)
    distant_count: int = 0
    audit_stats: Dict[str, Any] = field(default_factory=dict)
    # 壞滅緣（validity conditions）：path 型 Depends 指向已消失路徑的 atoms
    stale_deps: List[Dict[str, str]] = field(default_factory=list)


# ─── Parsing ─────────────────────────────────────────────────────────────────

META_PATTERN = re.compile(r"^-\s+([\w-]+):\s*(.+)$")
SECTION_PATTERN = re.compile(r"^##\s+(.+)$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TABLE_ROW_PATTERN = re.compile(r"^\|(.+)\|$")
CONFIDENCE_EXTRACT = re.compile(r"\[(固|觀|臨)\]")


def parse_atom_file(path: Path, layer_name: str) -> AtomMetadata:
    """Parse a .md atom file into AtomMetadata.

    Supports two formats:
    1. Atom-style: `- Key: Value` metadata block (project standard)
    2. Claude-native: `---\\nname:...\\n---` YAML frontmatter (auto-memory system)
    """
    atom = AtomMetadata(file_path=path, layer_name=layer_name)
    try:
        # 讀 raw bytes 自行 decode（utf-8-sig 仍處理 BOM）：read_text 會做 universal-newline
        # 翻譯，會在偵測前就把 \r\r\n 吃掉 → Fix B 的雙CR偵測必須看原始位元組。
        text = path.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return atom

    # Fix B: 偵測並修復 \r\r\n（雙CR）損壞行尾。
    # 不正規化的話 splitlines 會把雙CR拆成假空行 → metadata 迴圈遇假空行 break
    # → 只讀到第一個欄位 → 後續必填欄誤判缺失。先記旗標（emit warning），再正規化。
    atom.had_bad_eol = "\r\r\n" in text
    text = text.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")

    lines = text.splitlines()
    atom.line_count = len(lines)

    # Detect Claude-native YAML frontmatter — skip atom-style validation
    if lines and lines[0].strip() == "---":
        atom.is_claude_native = True
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                break
            m = re.match(r"^([\w-]+):\s*(.*)$", lines[i])
            if m:
                atom.raw_metadata[m.group(1)] = m.group(2).strip().strip('"').strip("'")
        # Use 'name' as title, fall back to file stem
        atom.title = atom.raw_metadata.get("name", path.stem)
        return atom

    # Title (first # heading)
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            atom.title = line[2:].strip()
            break

    # Metadata block (lines starting with "- Key: Value")
    # 空行不結束區塊：conflict-review 核可會在標題下插 `- Decided-by:` 再接原空行，
    # 舊版在此 break 只讀到一欄 → Scope/Confidence/Trigger 全誤報缺失。
    # 區塊終點 = 第一個非空、非 `- Key:` 的行（通常是 `## 知識`）。
    in_meta = False
    for line in lines:
        if line.strip() == "":
            continue
        m = META_PATTERN.match(line) if line.startswith("- ") else None
        if m:
            key, val = m.group(1), m.group(2).strip()
            atom.raw_metadata[key] = val
            in_meta = True
        elif in_meta:
            break  # end of metadata block

    # Extract structured fields
    atom.scope = atom.raw_metadata.get("Scope", "")
    # scope_label — frontmatter 優先，缺則路徑推斷（對齊 tools/migrate-scope-field.py:infer_scope）
    atom.scope_label = atom.scope or _infer_scope_from_path(path)
    raw_conf = atom.raw_metadata.get("Confidence", "")
    cm = CONFIDENCE_EXTRACT.search(raw_conf)
    atom.confidence = f"[{cm.group(1)}]" if cm else raw_conf

    raw_trigger = atom.raw_metadata.get("Trigger", "")
    atom.trigger = [t.strip() for t in re.split(r"[,，]", raw_trigger) if t.strip()]

    # Last-used / Confirmations / ReadHits 從 <atom>.access.json 讀
    # （legacy 過渡：若 .md 仍有 frontmatter 欄則作為 fallback，access 優先）
    try:
        from lib.atom_access import read_access
        acc = read_access(path)
    except (ImportError, OSError):
        acc = {}

    raw_date = acc.get("last_used") or atom.raw_metadata.get("Last-used", "").strip()
    if raw_date and DATE_PATTERN.match(raw_date):
        try:
            atom.last_used = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    if "confirmations" in acc:
        atom.confirmations = int(acc.get("confirmations") or 0)
    else:
        try:
            atom.confirmations = int(atom.raw_metadata.get("Confirmations", "0"))
        except ValueError:
            atom.confirmations = 0

    atom.privacy = atom.raw_metadata.get("Privacy", "public")
    atom.source = atom.raw_metadata.get("Source", "")

    # Optional fields — graceful fallback to defaults
    atom.atom_type = atom.raw_metadata.get("Type", "semantic").strip().lower()
    if atom.atom_type not in VALID_TYPES:
        atom.atom_type = "semantic"

    raw_created = atom.raw_metadata.get("Created", "").strip()
    if DATE_PATTERN.match(raw_created):
        try:
            atom.created = datetime.strptime(raw_created, "%Y-%m-%d").date()
        except ValueError:
            pass

    atom.ttl = atom.raw_metadata.get("TTL", None)
    if atom.ttl:
        atom.ttl = atom.ttl.strip()

    raw_expires = atom.raw_metadata.get("Expires-at", "").strip()
    if DATE_PATTERN.match(raw_expires):
        try:
            atom.expires_at = datetime.strptime(raw_expires, "%Y-%m-%d").date()
        except ValueError:
            pass

    raw_tags = atom.raw_metadata.get("Tags", "")
    atom.tags = [t.strip() for t in re.split(r"[,，]", raw_tags) if t.strip()]

    raw_related = atom.raw_metadata.get("Related", "")
    atom.related = [r.strip() for r in re.split(r"[,，]", raw_related) if r.strip()]

    raw_supersedes = atom.raw_metadata.get("Supersedes", "")
    atom.supersedes = [s.strip() for s in re.split(r"[,，]", raw_supersedes) if s.strip()]

    raw_quality = atom.raw_metadata.get("Quality", "")
    if raw_quality:
        try:
            atom.quality = float(raw_quality)
        except ValueError:
            pass

    # Sections
    for line in lines:
        sm = SECTION_PATTERN.match(line)
        if sm:
            section_name = sm.group(1).strip()
            atom.sections_found.add(section_name)
            if "演化日誌" in section_name:
                atom.has_evolution_log = True

    # Count evolution log entries
    if atom.has_evolution_log:
        in_log = False
        for line in lines:
            if "演化日誌" in line:
                in_log = True
                continue
            if in_log and TABLE_ROW_PATTERN.match(line):
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2 and DATE_PATTERN.match(cells[0]):
                    atom.evolution_entries += 1

    return atom


def parse_memory_index(path: Path) -> Tuple[List[IndexEntry], int]:
    """Parse MEMORY.md index file. Returns (entries, line_count)."""
    entries: List[IndexEntry] = []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return entries, 0

    lines = text.splitlines()
    line_count = len(lines)

    # Find the table
    in_table = False
    header_seen = False
    for line in lines:
        stripped = line.strip()
        if not in_table:
            if stripped.startswith("| Atom") or stripped.startswith("|Atom"):
                in_table = True
                header_seen = True
                continue
            # CC 原生 auto-memory 清單格式：`- [標題](檔.md) — 說明`
            # （projects/<slug>/memory/MEMORY.md 用此格式，非 atom 表格）
            m = re.match(r"^- \[[^\]]*\]\(([^)]+\.md)\)", stripped)
            if m:
                rel = m.group(1)
                entries.append(IndexEntry(
                    atom_name=Path(rel).stem, path=rel,
                    trigger="", confidence="",
                ))
                continue
        else:
            if stripped.startswith("|---") or stripped.startswith("| ---"):
                continue  # separator
            if not stripped.startswith("|"):
                break  # end of table
            cells = [c.strip() for c in stripped.split("|")]
            cells = [c for c in cells if c]  # remove empties from leading/trailing |
            if len(cells) >= 3:
                # 3-col format: | Atom | Path | Trigger | [Confidence]
                # 範疇聚合表（| 範疇 | atom 數 | 深入 |）第二欄是數字或 drill 字串、不是 .md
                # → 不是 atom 列，跳過不產 entry（atom 真相由 _atom_index.json 提供）
                if not cells[1].endswith(".md"):
                    continue
                entry = IndexEntry(
                    atom_name=cells[0],
                    path=cells[1],
                    trigger=cells[2],
                    confidence=cells[3] if len(cells) >= 4 else "",
                )
                entries.append(entry)
            elif len(cells) == 2:
                # Compact 2-col format: | Atom | 說明 |
                # Path is inferred from atom name (supports wildcards like "feedback-*")
                name = cells[0]
                entry = IndexEntry(
                    atom_name=name,
                    path=f"{name}.md",
                    trigger="",
                    confidence="",
                )
                entries.append(entry)

    return entries, line_count


# ─── Validation ──────────────────────────────────────────────────────────────


def validate_format(atom: AtomMetadata) -> List[Issue]:
    """Validate atom file format compliance."""
    issues: List[Issue] = []
    rel = _rel_path(atom.file_path)

    # Claude-native YAML frontmatter has its own schema — skip atom-style validation
    if atom.is_claude_native:
        return issues

    # Fix B: 行尾損壞（\r\r\n）— 修而不掩，emit warning 讓使用者知曉並修原始檔
    if atom.had_bad_eol:
        issues.append(Issue(rel, "warning", "format", "行尾損壞（\\r\\r\\n 雙CR）— 已容錯解析，建議修復原始檔行尾"))

    # Title
    if not atom.title:
        issues.append(Issue(rel, "error", "format", "缺少 # 標題"))

    # Required metadata
    for key in REQUIRED_METADATA:
        if key not in atom.raw_metadata:
            issues.append(Issue(rel, "error", "format", f"缺少必要欄位: {key}"))

    # 清單外欄位（拼錯的欄名會被讀取端靜默忽略，這裡浮出）
    for key in atom.raw_metadata:
        if key not in REQUIRED_METADATA and key not in OPTIONAL_METADATA:
            issues.append(Issue(rel, "warning", "format", f"未知欄位: {key}（lib/atom_spec.OPTIONAL_METADATA 未登記）"))

    # Confidence value
    if atom.confidence and atom.confidence not in VALID_CONFIDENCE:
        issues.append(
            Issue(rel, "error", "format", f"Confidence 值無效: {atom.confidence}（應為 [固]/[觀]/[臨]）")
        )

    # Last-used date
    if "Last-used" in atom.raw_metadata and atom.last_used is None:
        issues.append(
            Issue(rel, "warning", "format", f"Last-used 日期格式無效: {atom.raw_metadata['Last-used']}")
        )

    # Required sections
    for section in REQUIRED_SECTIONS:
        if section not in atom.sections_found:
            issues.append(Issue(rel, "warning", "format", f"缺少建議區段: ## {section}"))
    # 知識 / 印象 二選一（指標型 atom 用 ## 印象 取代 ## 知識）
    if not (atom.sections_found & KNOWLEDGE_SECTIONS):
        issues.append(Issue(rel, "warning", "format", "缺少建議區段: ## 知識 或 ## 印象"))

    # Line count
    if atom.line_count > ATOM_MAX_LINES:
        issues.append(
            Issue(rel, "warning", "size", f"Atom 超過 {ATOM_MAX_LINES} 行（目前 {atom.line_count} 行）")
        )

    # Trigger count
    trigger_count = len(atom.trigger)
    if trigger_count > 0 and (trigger_count < TRIGGER_MIN or trigger_count > TRIGGER_MAX):
        issues.append(
            Issue(rel, "info", "trigger", f"Trigger 數量 {trigger_count}（建議 {TRIGGER_MIN}~{TRIGGER_MAX}）")
        )

    # Depends / Evidence（皆 optional；缺欄靜默，格式錯誤僅 warning 不 fail）
    if "Depends" in atom.raw_metadata:
        for w in depends_warnings(atom.raw_metadata["Depends"]):
            issues.append(Issue(rel, "warning", "format", w))
    if "Evidence" in atom.raw_metadata:
        ew = evidence_warning(atom.raw_metadata["Evidence"])
        if ew:
            issues.append(Issue(rel, "warning", "format", ew))

    return issues


def check_stale_deps(atom: AtomMetadata) -> List[Dict[str, str]]:
    """壞滅緣檢查：path 型 Depends 條目指向不存在的路徑（warning 級）。

    無 Depends 欄一律靜默（optional，向後相容）；自由文字型條目不可驗、跳過。
    """
    raw = atom.raw_metadata.get("Depends", "")
    if not raw or atom.is_claude_native:
        return []
    out: List[Dict[str, str]] = []
    for e in parse_depends(raw):
        if e["type"] != "path" or not e["value"]:
            continue
        resolved = resolve_depends_path(e["value"])
        if not resolved.exists():
            out.append({
                "file": _rel_path(atom.file_path),
                "dep": e["value"],
                "resolved": str(resolved),
            })
    return out


def _forget_config() -> Dict[str, Any]:
    """workflow/config.json（selective forget 旋鈕：self_iteration.decay_half_life_days /
    archive_score_threshold / forget.*）。缺檔或壞檔 → 空 dict，各處用預設值。"""
    try:
        return json.loads((CLAUDE_DIR / "workflow" / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _archive_candidate(atom: AtomMetadata, today: date, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """同 hooks/wg_atoms._self_iterate_atoms 的封存判定：archive_score < archive_score_threshold。
    回 wg_atoms.apply_selective_forget 吃的候選 dict（atom/path/score/last_used/confirmations）。"""
    from lib.atom_access import read_access, usefulness_stats
    try:
        from wg_atoms import archive_score
    except ImportError:
        _hooks = CLAUDE_DIR / "hooks"
        if str(_hooks) not in sys.path:
            sys.path.insert(0, str(_hooks))
        from wg_atoms import archive_score
    si = config.get("self_iteration", {}) or {}
    half_life = float(si.get("decay_half_life_days", 30))
    threshold = float(si.get("archive_score_threshold", 0.3))
    acc = read_access(atom.file_path)
    has_use = usefulness_stats(acc).get("n", 0) > 0
    sc = archive_score(acc, datetime.combine(today, datetime.min.time()), half_life,
                       has_use_evidence=has_use)
    if sc is None or sc["score"] >= threshold:
        return None
    return {"atom": atom.file_path.stem, "path": str(atom.file_path),
            "score": round(sc["score"], 3), "days_since": sc["days_since"],
            "last_used": acc.get("last_used"), "confirmations": sc["confirmations"],
            "threshold": threshold}


def check_staleness(atom: AtomMetadata, today: date,
                    config: Optional[Dict[str, Any]] = None) -> Optional[Suggestion]:
    """降級候選 = selective forget 的封存候選（與 --enforce 同一判定）。"""
    if not atom.confidence:
        return None
    c = _archive_candidate(atom, today, config if config is not None else _forget_config())
    if c is None:
        return None
    reason = (f"封存分數 {c['score']} < {c['threshold']}（{c['days_since']} 天未用、"
              f"confirmations={c['confirmations']}）")
    rel = _rel_path(atom.file_path)
    if atom.confidence == "[固]":
        return Suggestion(rel, atom.confidence, "建議人工檢視", reason)
    return Suggestion(rel, atom.confidence, "遙遠記憶（--enforce 隔離）", reason)


def suggest_promotions(atom: AtomMetadata) -> Optional[Suggestion]:
    """Suggest promotion aligned with server.js atom_promote (authoritative).

    真閘只有兩軌（ReadHits 純曝光、已退役、不參與）：
      - confirmations 主軌：≥ 閾值（[臨]→[觀]=4、[觀]→[固]=10）
      - usefulness 軌：Wilson 下界 lb≥0.6 且 n≥3（委派 lib.atom_access，不抄公式）
    """
    thresholds = PROMOTION_THRESHOLDS.get(atom.confidence)
    if thresholds is None:
        return None

    conf_ok = atom.confirmations >= thresholds["confirmations"]
    util_ok = usefulness_promote_eligible(read_access(atom.file_path))
    if not conf_ok and not util_ok:
        return None

    if conf_ok:
        reason = f"Conf={atom.confirmations}（閾值 {thresholds['confirmations']}）"
    else:
        reason = "Usefulness Wilson 下界達標（lb≥0.6, n≥3）"
    rel = _rel_path(atom.file_path)
    if atom.confidence == "[臨]":
        return Suggestion(rel, "[臨]", "[觀]", reason)
    elif atom.confidence == "[觀]":
        return Suggestion(rel, "[觀]", "[固]", reason)
    return None


def _index_json_entries(mem_dir: Path) -> Optional[List[IndexEntry]]:
    """從 mem_dir/_atom_index.json 建 IndexEntry 清單；檔不存在 → None（呼叫端退回 MEMORY.md）。
    檔存在但損壞時 load 回空清單 → 所有 atom 會被報「未在索引中列出」，讓損壞浮出而非靜默。"""
    if not (mem_dir / "_atom_index.json").exists():
        return None
    data = load_atom_index_json(mem_dir)
    entries: List[IndexEntry] = []
    for a in data.get("atoms") or []:
        if not isinstance(a, dict) or not a.get("name") or not a.get("path"):
            continue
        entries.append(IndexEntry(
            atom_name=str(a["name"]),
            path=str(a["path"]),
            trigger=", ".join(a.get("triggers") or []),
            confidence="",
        ))
    return entries


_FLAT_SHARED_RE = re.compile(r"^memory/shared/[^/]+\.md$")


def _has_flat_shared_entries(index_entries: List[IndexEntry]) -> bool:
    """專案 index 是否仍含平鋪 shared atom（memory/shared/<slug>.md，無範疇段）＝尚未遷移。"""
    return any(_FLAT_SHARED_RE.match(e.path.replace("\\", "/")) for e in index_entries)


def validate_index(index_path: Path, memory_dir: Path, index_entries: List[IndexEntry]) -> List[Issue]:
    """Cross-reference index entries with actual files."""
    issues: List[Issue] = []
    rel_index = _rel_path(index_path)

    # 實際 atom 檔（遞迴；與其餘掃描同源）：atom 實體可居子目錄（memory/<範疇>/、
    # memory/Failures/<主題>/、專案 shared/<domain>/）或樹外（舊址 _AIDocs/Failures/、
    # _AIDocs/_atoms/）。global=多根、非 global=rglob 單根。以檔名比對；未登記索引的
    # atom 一律 warning「未在索引中列出」。
    actual_files: Set[str] = set()
    tree_stems: Set[str] = set()
    for p in iter_atom_files(memory_dir):
        # Claude-native YAML 檔（`---` 開頭）不是 atom：不進 atom 索引、注入端不讀，不報「未在索引中列出」
        try:
            if p.read_bytes()[:8].lstrip(b"\xef\xbb\xbf").startswith(b"---"):
                continue
        except OSError:
            pass
        actual_files.add(p.name)
        tree_stems.add(p.stem)

    try:
        is_global_mem = memory_dir.resolve() == GLOBAL_MEMORY_DIR.resolve()
    except OSError:
        is_global_mem = False
    layout_gate = bool(gate_enabled())

    # personal/ 在 SKIP_DIRS（掃描報表不計入），但 personal atom 可正式登記於
    # _atom_index.json 且由 wg_atoms 注入——index→file 存在性檢查必須看得到它們，
    # 否則每次健檢固定誤報「索引指向不存在的檔案」。僅補存在性口徑，不進掃描報表。
    personal_root = memory_dir / "personal"
    if personal_root.is_dir():
        tree_stems |= {p.stem for p in personal_root.rglob("*.md") if p.is_file()}

    # Check index → file
    indexed_files: Set[str] = set()
    for entry in index_entries:
        entry_path = Path(entry.path)
        file_name = entry_path.name

        # Wildcard entries (e.g. "feedback-*.md") — expand against actual files
        if "*" in file_name:
            prefix = file_name.split("*")[0].rstrip("-_.")
            matched_any = False
            for fname in actual_files:
                stem = fname[:-3] if fname.endswith(".md") else fname  # strip .md
                if stem == prefix or stem.startswith(f"{prefix}_") or stem.startswith(f"{prefix}-"):
                    indexed_files.add(fname)
                    matched_any = True
            if not matched_any:
                issues.append(
                    Issue(rel_index, "warning", "index", f"索引 wildcard '{entry.atom_name}' 無匹配檔案")
                )
            continue

        indexed_files.add(file_name)

        # entry.path 相對 memory_dir.parent（memory/x.md、memory/版控/Git/x.md、
        # _AIDocs/_atoms/…）。依序認：完整相對路徑 → memory_dir 根下同名 → 遞迴 stem 集
        # → 失敗家族（memory/Failures/<主題>/ 或舊址 _AIDocs/Failures/）；全落空才算不存在
        entry_stem = file_name[:-3] if file_name.endswith(".md") else file_name
        exists = (
            (memory_dir.parent / entry.path).exists()
            or (memory_dir / file_name).exists()
            or entry_stem in tree_stems
            or _failures_file_exists(file_name)
        )
        if not exists:
            issues.append(
                Issue(rel_index, "error", "index", f"索引指向不存在的檔案: {entry.path}")
            )

        # 範疇資料夾硬規則（gate 開啟時才報）：全域 memory/ 根下散檔須歸入 memory/<範疇>/
        if layout_gate and is_global_mem and is_flat_core_path(entry.path):
            issues.append(
                Issue(rel_index, "error", "layout", f"memory/ 根下散檔（需歸入 memory/<範疇>/）: {entry.path}")
            )

    # Check file → index
    for fname in actual_files:
        if fname not in indexed_files:
            issues.append(
                Issue(rel_index, "warning", "index", f"檔案 {fname} 未在索引中列出")
            )

    return issues


def detect_duplicates(all_atoms: List[AtomMetadata]) -> List[DuplicatePair]:
    """Detect potential duplicate atoms across layers."""
    pairs: List[DuplicatePair] = []

    for i in range(len(all_atoms)):
        for j in range(i + 1, len(all_atoms)):
            a, b = all_atoms[i], all_atoms[j]
            # Same layer skip
            if a.file_path.parent == b.file_path.parent:
                continue
            # 兩個不同專案層之間不算重複：注入候選池只含「全域 + 當前專案」，
            # 他專案 atom 永遠不會與本專案同時出現在模型眼前
            if a.layer_name != b.layer_name and "global" not in (a.layer_name, b.layer_name):
                continue

            # Title match — 同 (scope_label, normalized title) 才算重複；
            # 跨 scope 同名 atom（如 global/decisions vs shared/decisions）不該誤判
            key_a = (a.scope_label, _normalize(a.title)) if a.title else None
            key_b = (b.scope_label, _normalize(b.title)) if b.title else None
            title_match = bool(key_a and key_b and key_a == key_b)

            # Trigger overlap
            set_a = {t.lower() for t in a.trigger}
            set_b = {t.lower() for t in b.trigger}
            shared = set_a & set_b

            if title_match or len(shared) >= 3:
                pairs.append(
                    DuplicatePair(
                        _rel_path(a.file_path),
                        _rel_path(b.file_path),
                        sorted(shared),
                        title_match,
                    )
                )

    return pairs


# ─── Distant Memory Operations ───────────────────────────────────────────────


def search_distant(memory_dir: Path, keyword: str) -> List[Tuple[Path, str]]:
    """Search every _distant/ under the layer for atoms matching keyword."""
    results: List[Tuple[Path, str]] = []
    kw_lower = keyword.lower()
    if True:
        for md_file in _distant_md_files(memory_dir):
            try:
                text = md_file.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            if kw_lower in text.lower() or kw_lower in md_file.stem.lower():
                # Extract title
                title = ""
                for line in text.splitlines():
                    if line.startswith("# ") and not line.startswith("## "):
                        title = line[2:].strip()
                        break
                results.append((md_file, title or md_file.stem))

    return results


def restore_from_distant(atom_path: Path) -> Tuple[bool, str]:
    """Move atom from _distant/ back to active area, reset Confidence to [臨]."""
    if not atom_path.exists():
        return False, f"檔案不存在: {atom_path}"

    # Find the memory/ dir (go up until we leave _distant)
    parts = atom_path.parts
    distant_idx = None
    for i, p in enumerate(parts):
        if p == DISTANT_DIR:
            distant_idx = i
            break

    if distant_idx is None:
        return False, f"路徑不在 _distant/ 下: {atom_path}"

    memory_dir = Path(*parts[:distant_idx])
    dest = memory_dir / atom_path.name

    if dest.exists():
        return False, f"活躍區已有同名檔案: {dest}"

    # Read, reset Confidence, write to dest
    try:
        text = atom_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        return False, f"讀取失敗: {e}"

    # Reset confidence to [臨]
    text = re.sub(
        r"^(-\s+Confidence:\s*).*$",
        r"\g<1>[臨]",
        text,
        count=1,
        flags=re.MULTILINE,
    )

    # Last-used / Confirmations / ReadHits 存於 access.json（非 .md），
    # restore 後在 dest path 改寫 access 旁路檔（重置為 0、last_used 設今天）
    today_str = date.today().isoformat()

    try:
        # 走 funnel
        _r = write_raw(dest, text, source=_AUDIT_SOURCE, op="audit_demote")
        if not _r.ok:
            raise OSError(_r.error)
        # 同步 access 旁路檔重置
        try:
            from lib.atom_access import write_access_field
            write_access_field(dest, field="confirmations", value=0,
                               source="tool:memory-audit")
            write_access_field(dest, field="read_hits", value=0,
                               source="tool:memory-audit")
            write_access_field(dest, field="last_used", value=today_str,
                               source="tool:memory-audit")
        except (ImportError, OSError, ValueError):
            pass
        atom_path.unlink()
        # _distant 側殘留的 access sidecar 一併清除（計數已在 dest 重置歸零）
        old_access = atom_path.with_suffix(".access.json")
        if old_access.exists():
            try:
                old_access.unlink()
            except OSError:
                pass
        # Clean up empty year_month dir
        parent = atom_path.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
        # _atom_index.json SoT 同步（唯一機器源；含 mirror regen）——
        # 失敗不回滾檔案，但必浮訊號（可觀測性鐵律）
        index_note = ""
        try:
            from lib.atom_spec import parse_frontmatter
            fm = parse_frontmatter(text)
            triggers = [t.strip() for t in re.split(r"[,，]", fm.get("Trigger", ""))
                        if t.strip()]
            rel = dest.relative_to(memory_dir.parent).as_posix()
            index_upsert_atom(memory_dir, dest.stem, rel, triggers,
                              scope=fm.get("Scope", "global") or "global")
        except (OSError, ValueError) as e:
            index_note = f"；_atom_index.json 更新失敗: {e}"
        return True, f"已拉回: {dest}（Confidence 重置為 [臨]）{index_note}"
    except OSError as e:
        return False, f"寫入失敗: {e}"


def _append_evolution_entry(atom_path: Path, change: str, source: str = "memory-audit --enforce") -> None:
    """Append an entry to the atom's evolution log."""
    try:
        text = atom_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return
    today_str = date.today().isoformat()
    entry_line = f"| {today_str} | {change} | {source} |"

    if "## 演化日誌" in text:
        # Find the last table row and append after it
        lines = text.splitlines()
        insert_idx = None
        in_log = False
        for i, line in enumerate(lines):
            if "演化日誌" in line:
                in_log = True
                continue
            if in_log:
                if TABLE_ROW_PATTERN.match(line.strip()):
                    insert_idx = i
                elif line.strip().startswith("##"):
                    break
        if insert_idx is not None:
            lines.insert(insert_idx + 1, entry_line)
        else:
            # Table header exists but no data rows; append after separator
            for i, line in enumerate(lines):
                if "演化日誌" in line:
                    # Find separator
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if lines[j].strip().startswith("|---"):
                            lines.insert(j + 1, entry_line)
                            break
                    break
        # 走 funnel
        write_raw(atom_path, "\n".join(lines), source=_AUDIT_SOURCE, op="audit_evolution_insert")
    else:
        # No evolution log section; append one
        text += f"\n\n## 演化日誌\n\n| 日期 | 變更 | 來源 |\n|------|------|------|\n{entry_line}\n"
        # 走 funnel
        write_raw(atom_path, text, source=_AUDIT_SOURCE, op="audit_evolution_create")


def compact_evolution_logs(
    atom_path: Path, max_entries: int = 10, dry_run: bool = False
) -> Optional[str]:
    """Compact evolution log: merge oldest entries into a summary if > max_entries."""
    try:
        text = atom_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None

    if "## 演化日誌" not in text:
        return None

    lines = text.splitlines()
    # Find data rows in evolution log table
    in_log = False
    log_end = len(lines)
    entries: List[Tuple[int, str]] = []  # (line_index, date_str)

    for i, line in enumerate(lines):
        if "演化日誌" in line:
            in_log = True
            continue
        if in_log:
            if line.strip().startswith("##"):
                log_end = i
                break
            stripped = line.strip()
            if TABLE_ROW_PATTERN.match(stripped):
                cells = [c.strip() for c in stripped.split("|") if c.strip()]
                if len(cells) >= 2 and DATE_PATTERN.match(cells[0]):
                    entries.append((i, cells[0]))
                elif len(cells) >= 2 and cells[0].startswith("[合併]"):
                    entries.append((i, cells[0]))  # already-merged line

    if len(entries) <= max_entries:
        return None

    # Merge oldest entries, keep newest (max_entries - 1)
    merge_count = len(entries) - (max_entries - 1)
    to_merge = entries[:merge_count]

    # Extract date range from merge targets
    dates = [d for _, d in to_merge if DATE_PATTERN.match(d)]
    earliest = dates[0] if dates else to_merge[0][1]
    latest = dates[-1] if dates else to_merge[-1][1]
    summary_line = f"| [合併] | {merge_count} 筆歷史記錄 ({earliest}~{latest}) | auto-compact |"

    rel = _rel_path(atom_path)
    if dry_run:
        return f"[DRY-RUN] Would compact {rel}: merge {merge_count} entries ({earliest}~{latest})"

    merged_indices = {idx for idx, _ in to_merge}
    new_lines = []
    summary_inserted = False
    for i, line in enumerate(lines):
        if i in merged_indices:
            if not summary_inserted:
                new_lines.append(summary_line)
                summary_inserted = True
        else:
            new_lines.append(line)

    # 走 funnel
    write_raw(atom_path, "\n".join(new_lines), source=_AUDIT_SOURCE, op="audit_compact")
    return f"COMPACTED: {rel} — merged {merge_count} entries ({earliest}~{latest})"


def delete_atom(
    atom_name: str, layer: str = "global", purge: bool = False, dry_run: bool = False
) -> Tuple[bool, str]:
    """Delete an atom with full chain propagation.

    Steps:
    1. Locate atom file
    2. LanceDB: delete all chunks for this atom
    3. Scan Related references in other atoms → remove
    4. Update MEMORY.md index → remove row
    5. Move to _distant/ (or permanent delete if purge)
    6. Trigger incremental re-index
    7. Write audit.log
    """
    import urllib.request
    import urllib.error

    # 1. Locate atom file
    layers = discover_layers()
    atom_path = None
    mem_dir = None
    for layer_name, mdir in layers:
        if layer_name == layer:
            # atom 住在範疇資料夾（memory/<範疇>/…），不在層根；以 stem 遍歷整層找
            for candidate in iter_atom_files(mdir):
                if candidate.stem == atom_name:
                    atom_path = candidate
                    mem_dir = mdir
                    break
            break

    if atom_path is None:
        return False, f"Atom '{atom_name}' not found in layer '{layer}'"

    actions = []
    mode = "PURGE" if purge else "DELETE"

    if dry_run:
        actions.append(f"[DRY-RUN] Would {mode.lower()} atom: {atom_name} (layer: {layer})")
    else:
        actions.append(f"[{mode}] Processing atom: {atom_name} (layer: {layer})")

    # 2. LanceDB cleanup
    try:
        VECTORDB_DIR = CLAUDE_DIR / "memory" / "_vectordb"
        if VECTORDB_DIR.exists():
            import lancedb
            db = lancedb.connect(str(VECTORDB_DIR))
            try:
                table = db.open_table("atom_chunks")
                if dry_run:
                    # Count rows that would be deleted
                    rows = table.search().select(["atom_name", "layer"]).limit(10000).to_list()
                    count = sum(1 for r in rows if r.get("atom_name") == atom_name and r.get("layer") == layer)
                    actions.append(f"  [DRY-RUN] Would delete {count} LanceDB chunks")
                else:
                    table.delete(f"atom_name = '{atom_name}' AND layer = '{layer}'")
                    actions.append("  LanceDB chunks deleted")
            except Exception as e:
                actions.append(f"  LanceDB: {e}")
    except ImportError:
        actions.append("  LanceDB: not installed (skipped)")

    # 3. Scan Related references in other atoms → remove
    related_cleaned = 0
    for layer_name, mdir in layers:
        for md_file in iter_atom_files(mdir):
            if md_file == atom_path:
                continue
            try:
                text = md_file.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            changed = False
            new_lines = []
            for line in text.splitlines():
                if line.strip().startswith("- Related:"):
                    m = re.match(r"^(- Related:\s*)(.+)$", line)
                    if m:
                        related_list = [r.strip() for r in m.group(2).split(",")]
                        filtered = [r for r in related_list if r and r != atom_name]
                        if len(filtered) != len(related_list):
                            changed = True
                            related_cleaned += 1
                            if filtered:
                                new_lines.append(f"- Related: {', '.join(filtered)}")
                            # else: remove the line entirely
                            continue
                if line.strip().startswith("- Supersedes:"):
                    m = re.match(r"^(- Supersedes:\s*)(.+)$", line)
                    if m:
                        sup_list = [s.strip() for s in m.group(2).split(",")]
                        if atom_name in sup_list:
                            actions.append(f"  WARNING: {md_file.stem} supersedes deleted atom {atom_name}")
                new_lines.append(line)
            if changed and not dry_run:
                # 走 funnel：EOL-preserving + audit（裸 write_text 會翻整檔行尾且無稽核）
                _r = write_raw(md_file, "\n".join(new_lines),
                               source=_AUDIT_SOURCE, op="audit_related_clean")
                if not _r.ok:
                    actions.append(f"  Related cleanup FAILED for {md_file.stem}: {_r.error}")
    if related_cleaned:
        actions.append(f"  Related references cleaned: {related_cleaned} atom(s)")

    # 4. Update MEMORY.md index
    if mem_dir:
        index_path = mem_dir / "MEMORY.md"
        if index_path.exists():
            try:
                idx_text = index_path.read_text(encoding="utf-8-sig")
                new_idx_lines = []
                removed = False
                for line in idx_text.splitlines():
                    # Match table row containing atom name
                    if line.strip().startswith("|") and f"| {atom_name} " in line:
                        removed = True
                        continue
                    new_idx_lines.append(line)
                if removed:
                    if dry_run:
                        actions.append("  [DRY-RUN] Would remove MEMORY.md index row")
                    else:
                        # 走 funnel（索引整檔覆寫入口）：EOL-preserving + audit
                        _r = write_index_full(index_path, "\n".join(new_idx_lines),
                                              source=_AUDIT_SOURCE)
                        if not _r.ok:
                            actions.append(f"  MEMORY.md update failed: {_r.error}")
                        else:
                            actions.append("  MEMORY.md index row removed")
            except (OSError, UnicodeDecodeError) as e:
                actions.append(f"  MEMORY.md update failed: {e}")

    # 5. Move/remove file
    if not dry_run:
        _append_evolution_entry(atom_path, f"{'永久刪除' if purge else '刪除移入 _distant/'}", "memory-audit --delete")
        if purge:
            try:
                os.remove(str(atom_path))
                actions.append(f"  File permanently deleted: {atom_path.name}")
            except OSError as e:
                actions.append(f"  File delete failed: {e}")
                return False, "\n".join(actions)
        else:
            ok, msg = move_to_distant(atom_path)
            actions.append(f"  {msg}")
            if not ok:
                return False, "\n".join(actions)

    # 5b. _atom_index.json SoT 同步（唯一機器源；含 _ATOM_INDEX.md mirror 自動 regen）
    if dry_run:
        actions.append("  [DRY-RUN] Would remove _atom_index.json entry")
    else:
        try:
            if index_delete_atom(mem_dir, atom_name):
                actions.append("  _atom_index.json entry removed (mirror regenerated)")
            else:
                actions.append("  _atom_index.json: no entry found (unchanged)")
        except (OSError, ValueError) as e:
            actions.append(f"  _atom_index.json update FAILED: {e}")

    # 6. Trigger incremental re-index
    if not dry_run:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:3849/index/incremental",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2)
            actions.append("  Incremental re-index triggered")
        except Exception:
            actions.append("  Incremental re-index: service not available (skipped)")

    # 7. Audit log
    if not dry_run:
        _write_audit_entry({
            "action": "purge" if purge else "delete",
            "atom": atom_name,
            "layer": layer,
        })
        actions.append("  Audit log entry written")

    return True, "\n".join(actions)


def _project_dir_from_args(args: argparse.Namespace) -> Optional[Path]:
    """Helper: extract project_dir from parsed args."""
    val = getattr(args, "project_dir", None)
    return Path(val) if val else None


def enforce_decay(args: argparse.Namespace) -> None:
    """--enforce：呼叫 hooks/wg_atoms.apply_selective_forget（唯一遺忘機制）。
    候選 = 封存分數 < archive_score_threshold 且不在核心保護清單；隔離到原範疇資料夾下的
    _distant/（含 .access.json sidecar），索引同步移除條目。--dry-run 只列候選不搬。"""
    today = date.today()
    dry_run = bool(args.dry_run)
    config = _forget_config()
    try:
        from wg_atoms import apply_selective_forget
    except ImportError:
        _hooks = CLAUDE_DIR / "hooks"
        if str(_hooks) not in sys.path:
            sys.path.insert(0, str(_hooks))
        from wg_atoms import apply_selective_forget
    # CLI 明示 --enforce = 操作者要求真隔離；config 的 enabled/dry_run 是 SessionEnd 自動跑的預設
    run_cfg = dict(config)
    run_cfg["self_iteration"] = dict(config.get("self_iteration", {}) or {})
    run_cfg["self_iteration"]["forget"] = {
        **(run_cfg["self_iteration"].get("forget") or {}),
        "enabled": True, "dry_run": dry_run,
    }

    layers = discover_layers(global_only=args.global_only, project_filter=args.project,
                             project_dir=_project_dir_from_args(args))
    actions: List[str] = []
    for layer_name, mem_dir in layers:
        cands = []
        for md_file in iter_atom_files(mem_dir):
            atom = parse_atom_file(md_file, layer_name)
            c = _archive_candidate(atom, today, config)
            if c is not None:
                cands.append(c)
        if not cands:
            continue
        fr = apply_selective_forget(cands, run_cfg, atoms_dir=mem_dir, staging_dir=None)
        by_name = {c["atom"]: c for c in cands}
        if fr["mode"] == "dry_run":
            for name in fr["candidates"]:
                c = by_name[name]
                actions.append(f"[DRY-RUN] Would isolate {_rel_path(Path(c['path']))} "
                               f"(score {c['score']} < {c['threshold']}, {c['days_since']}d)")
            continue
        for name in fr["forgotten"]:
            c = by_name[name]
            actions.append(f"OK: 已隔離 {_rel_path(Path(c['path']))} → {Path(c['path']).parent.name}/_distant/ "
                           f"(score {c['score']}, {c['days_since']}d)")
            try:
                if index_delete_atom(mem_dir, name):
                    actions.append(f"  _atom_index.json entry removed: {name}")
            except (OSError, ValueError) as e:
                actions.append(f"  _atom_index.json update FAILED: {name} — {e}")
            _write_audit_entry({"action": "decay", "atom": name, "layer": layer_name,
                                "score": c["score"], "days_stale": c["days_since"]})
        for name in fr["skipped"]:
            actions.append(f"SKIP: {name}（檔不存在或搬移失敗，見 hook debug log）")
        protected = [n for n in by_name if n not in fr["candidates"]]
        for name in protected:
            actions.append(f"PROTECTED: {name}（核心保護清單，不隔離）")

    if actions:
        print("\n".join(actions))
    else:
        print("No archive candidates (score >= threshold or no activity signal).")


def move_to_distant(atom_path: Path) -> Tuple[bool, str]:
    """Move an active atom to _distant/{year}_{month}/."""
    if not atom_path.exists():
        return False, f"檔案不存在: {atom_path}"

    memory_dir = atom_path.parent
    today = date.today()
    year_month = f"{today.year}_{today.month:02d}"
    distant_target = memory_dir / DISTANT_DIR / year_month

    distant_target.mkdir(parents=True, exist_ok=True)
    dest = distant_target / atom_path.name

    if dest.exists():
        return False, f"遙遠記憶已有同名檔案: {dest}"

    try:
        # .md + .access.json sidecar 原子搬移（lib.atom_access 單一來源；
        # 只搬 .md 會讓計數 sidecar 變孤兒）
        moved_sidecar = move_atom_pair(atom_path, dest)
        note = "（含 access sidecar）" if moved_sidecar else ""
        return True, f"已移入遙遠記憶: {dest}{note}"
    except OSError as e:
        return False, f"移動失敗: {e}"


# ─── Layer Discovery ─────────────────────────────────────────────────────────

CLAUDE_DIR = Path.home() / ".claude"
AUDIT_LOG_PATH = CLAUDE_DIR / "memory" / "_vectordb" / "audit.log"


def _write_audit_entry(entry: Dict[str, Any]) -> None:
    """Append a JSONL entry to audit.log."""
    entry["ts"] = datetime.now().isoformat(timespec="seconds")
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def parse_audit_log() -> Dict[str, Any]:
    """Parse audit.log JSONL and aggregate statistics."""
    stats: Dict[str, Any] = {
        "total_entries": 0,
        "by_action": {},
        "conflicts": 0,
        "deletes": 0,
        "purges": 0,
        "adds": 0,
        "skips": 0,
        "decays": 0,
    }
    if not AUDIT_LOG_PATH.exists():
        return stats

    try:
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                action = entry.get("action", "unknown")
                stats["total_entries"] += 1
                stats["by_action"][action] = stats["by_action"].get(action, 0) + 1
                if "conflict" in action:
                    stats["conflicts"] += 1
                elif action == "delete":
                    stats["deletes"] += 1
                elif action == "purge":
                    stats["purges"] += 1
                elif action == "add":
                    stats["adds"] += 1
                elif action == "skip":
                    stats["skips"] += 1
                elif action in ("decay", "enforce"):
                    stats["decays"] += 1
    except OSError:
        pass

    return stats


def discover_layers(
    global_only: bool = False,
    project_filter: Optional[str] = None,
    project_dir: Optional[Path] = None,
) -> List[Tuple[str, Path]]:
    """Discover all memory layers.

    project_dir 若提供，優先列在 global 之前（專案層優先）。
    """
    layers: List[Tuple[str, Path]] = []

    # 專案自治層（{project_root}/.claude/memory/）
    # global_only=True 時跳過專案層
    if not global_only and project_dir and project_dir.is_dir() and (project_dir / MEMORY_INDEX).exists():
        layers.append(("project", project_dir))

    # Global layer
    global_mem = CLAUDE_DIR / "memory"
    if global_mem.is_dir():
        layers.append(("global", global_mem))

    if global_only:
        return layers

    # 專案層：與執行期同一套判定（hooks/wg_core.discover_all_project_memory_dirs：
    # registry 優先 + projects/ 舊址須有 atom 索引標記）。自掃 projects/*/memory 會把
    # CC harness 原生 auto-memory 目錄（grok / hermes / Temp 測試夾）誤當記憶層。
    try:
        _hooks = CLAUDE_DIR / "hooks"
        if str(_hooks) not in sys.path:
            sys.path.insert(0, str(_hooks))
        from wg_core import discover_all_project_memory_dirs  # noqa: E402
        for slug, mem_dir in discover_all_project_memory_dirs():
            if project_filter and project_filter not in slug:
                continue
            if project_dir is not None and mem_dir.resolve() == Path(project_dir).resolve():
                continue  # 已以 "project" 身分列在最前
            layers.append((slug, mem_dir))
    except Exception as e:  # noqa: BLE001 — 判定器不可用時退回舊址掃描（並告知）
        print(f"[memory-audit] wg_core discovery unavailable ({e!r}); fallback to projects/ scan",
              file=sys.stderr)
        projects_dir = CLAUDE_DIR / "projects"
        if projects_dir.is_dir():
            for proj_dir in sorted(projects_dir.iterdir()):
                if not proj_dir.is_dir():
                    continue
                if project_filter and project_filter not in proj_dir.name:
                    continue
                mem_dir = proj_dir / "memory"
                if mem_dir.is_dir() and (mem_dir / "_atom_index.json").exists():
                    layers.append((proj_dir.name, mem_dir))

    return layers


# ─── Report Generation ───────────────────────────────────────────────────────


def generate_markdown_report(report: HealthReport) -> str:
    """Generate a Markdown health report."""
    lines: List[str] = []
    lines.append("# Atomic Memory Health Report")
    lines.append(f"> Generated: {report.scan_date.isoformat()}")
    lines.append("")

    # Summary
    errors = sum(1 for i in report.issues if i.level == "error")
    warnings = sum(1 for i in report.issues if i.level == "warning")
    conf_str = " | ".join(f"{k}: {v}" for k, v in sorted(report.confidence_counts.items()))

    lines.append("## Summary")
    lines.append(f"- Layers: {len(report.layers_scanned)} ({', '.join(report.layers_scanned)})")
    lines.append(f"- Active atoms: {report.total_atoms} | Distant: {report.distant_count}")
    lines.append(f"- {conf_str}" if conf_str else "- (no atoms)")
    lines.append(f"- Errors: {errors} | Warnings: {warnings}")
    lines.append(f"- Promotion candidates: {len(report.promotions)} | Demotion candidates: {len(report.demotions)}")
    if report.duplicates:
        lines.append(f"- Duplicate suspects: {len(report.duplicates)}")
    if report.stale_deps:
        lines.append(f"- Stale depends（壞滅緣觸發）: {len(report.stale_deps)}")
    lines.append("")

    # Issues
    if report.issues:
        lines.append("## Issues")
        lines.append("")
        lines.append("| Level | File | Category | Message |")
        lines.append("|-------|------|----------|---------|")
        for i in report.issues:
            lines.append(f"| {i.level} | {i.file} | {i.category} | {i.message} |")
        lines.append("")

    # Staleness / Demotions
    if report.demotions:
        lines.append("## Staleness / Demotion Suggestions")
        lines.append("")
        lines.append("| File | Current | Suggested | Reason |")
        lines.append("|------|---------|-----------|--------|")
        for s in report.demotions:
            lines.append(f"| {s.file} | {s.current} | {s.suggested} | {s.reason} |")
        lines.append("")

    # Promotions
    if report.promotions:
        lines.append("## Promotion Suggestions")
        lines.append("")
        lines.append("| File | Current → Suggested | Reason |")
        lines.append("|------|---------------------|--------|")
        for s in report.promotions:
            lines.append(f"| {s.file} | {s.current}→{s.suggested} | {s.reason} |")
        lines.append("")

    # Duplicates
    if report.duplicates:
        lines.append("## Duplicate Suspects")
        lines.append("")
        lines.append("| File A | File B | Shared Triggers | Title Match |")
        lines.append("|--------|--------|-----------------|-------------|")
        for d in report.duplicates:
            triggers = ", ".join(d.shared_triggers[:5])
            lines.append(f"| {d.file_a} | {d.file_b} | {triggers} | {'Yes' if d.title_match else 'No'} |")
        lines.append("")

    # 壞滅緣（validity conditions）— 有觸發才出現
    if report.stale_deps:
        lines.append("## 壞滅緣（Stale Depends）")
        lines.append("")
        for d in report.stale_deps:
            lines.append(f"- 壞滅緣觸發：atom {d['file']} 依賴 {d['dep']} 已不存在")
        lines.append("")

    # Audit Trail Summary
    if report.audit_stats and report.audit_stats.get("total_entries", 0) > 0:
        stats = report.audit_stats
        lines.append("## Audit Trail Summary")
        lines.append("")
        lines.append(f"- Total log entries: {stats['total_entries']}")
        lines.append(f"- Write Gate adds: {stats.get('adds', 0)} | skips: {stats.get('skips', 0)}")
        lines.append(f"- Deletes: {stats.get('deletes', 0)} | Purges: {stats.get('purges', 0)}")
        lines.append(f"- Conflicts detected: {stats.get('conflicts', 0)}")
        lines.append(f"- Decay actions: {stats.get('decays', 0)}")
        lines.append("")

    return "\n".join(lines)


def generate_json_report(report: HealthReport) -> str:
    """Generate a JSON health report."""
    data = {
        "scan_date": report.scan_date.isoformat(),
        "layers": report.layers_scanned,
        "total_atoms": report.total_atoms,
        "distant_count": report.distant_count,
        "confidence_counts": report.confidence_counts,
        "issues": [
            {"file": i.file, "level": i.level, "category": i.category, "message": i.message}
            for i in report.issues
        ],
        "promotions": [
            {"file": s.file, "current": s.current, "suggested": s.suggested, "reason": s.reason}
            for s in report.promotions
        ],
        "demotions": [
            {"file": s.file, "current": s.current, "suggested": s.suggested, "reason": s.reason}
            for s in report.demotions
        ],
        "duplicates": [
            {
                "file_a": d.file_a,
                "file_b": d.file_b,
                "shared_triggers": d.shared_triggers,
                "title_match": d.title_match,
            }
            for d in report.duplicates
        ],
        "audit_stats": report.audit_stats,
        "stale_deps": report.stale_deps,
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _rel_path(p: Path) -> str:
    """Return a short relative path for display."""
    try:
        return str(p.relative_to(CLAUDE_DIR))
    except ValueError:
        return str(p)


def _normalize(s: str) -> str:
    """Normalize string for comparison."""
    return re.sub(r"\s+", " ", s.strip().lower())


def _infer_scope_from_path(atom_path: Path) -> str:
    """由路徑推斷 scope（fallback when frontmatter 缺 Scope:）。

    對齊 tools/migrate-scope-field.py:infer_scope 與 lib/atom_spec.VALID_SCOPES。
    支援 ~/.claude/memory/ 與 {project}/.claude/memory/ 兩種根層。
    """
    parts = atom_path.parts
    # 找 memory/ 在 parts 的位置（global / project 共用此規則）
    for i, p in enumerate(parts):
        if p == "memory" and i + 1 < len(parts):
            sub_parts = parts[i + 1:]  # memory/ 之下的 rel parts
            if sub_parts and sub_parts[0] == "shared":
                return "shared"
            if len(sub_parts) >= 2 and sub_parts[0] == "roles":
                return "role"
            if len(sub_parts) >= 2 and sub_parts[0] == "personal":
                return "personal"
            return "global"
    return "global"


def _distant_dirs(memory_dir: Path) -> List[Path]:
    """該層所有 `_distant/` 目錄：move_to_distant 把 atom 移到「原範疇資料夾」下的 _distant/，
    所以 memory/<範疇>/_distant/ 與 memory/_distant/ 都可能存在；全域層另含 _AIDocs/_atoms/**。"""
    roots = [memory_dir]
    try:
        if memory_dir.resolve() == GLOBAL_MEMORY_DIR.resolve():
            roots.append(CLAUDE_DIR / "_AIDocs" / "_atoms")
    except OSError:
        pass
    found: List[Path] = []
    for root in roots:
        if root.is_dir():
            found.extend(p for p in root.rglob(DISTANT_DIR) if p.is_dir())
    return found


def _distant_md_files(memory_dir: Path) -> List[Path]:
    """該層 _distant/ 內所有 atom .md：直接放在 _distant/ 下（selective forget）或
    _distant/<year_month>/ 下（舊版 move_to_distant）兩種布局都算。"""
    files: List[Path] = []
    for distant_dir in _distant_dirs(memory_dir):
        files.extend(distant_dir.glob("*.md"))
        for ym_dir in distant_dir.iterdir():
            if ym_dir.is_dir():
                files.extend(ym_dir.glob("*.md"))
    return sorted(files)


def _count_distant(memory_dir: Path) -> int:
    """Count atoms isolated under the layer's _distant/ dirs."""
    return len(_distant_md_files(memory_dir))


# ─── Main ────────────────────────────────────────────────────────────────────


def run_audit(args: argparse.Namespace) -> HealthReport:
    """Run the full audit and return a HealthReport."""
    today = date.today()
    report = HealthReport(scan_date=today)

    layers = discover_layers(
        global_only=args.global_only,
        project_filter=args.project,
        project_dir=Path(args.project_dir) if getattr(args, "project_dir", None) else None,
    )

    all_atoms: List[AtomMetadata] = []

    for layer_name, mem_dir in layers:
        report.layers_scanned.append(layer_name)
        report.distant_count += _count_distant(mem_dir)

        # Parse index
        index_path = mem_dir / MEMORY_INDEX
        if index_path.exists():
            index_entries, idx_lines = parse_memory_index(index_path)
            # _atom_index.json 是唯一機器真相；存在時 entries 由它建，MEMORY.md 只作
            # 人讀索引（僅取行數做上限檢查）。缺 json 才退回 MEMORY.md 表格解析。
            json_entries = _index_json_entries(mem_dir)
            if json_entries is not None:
                index_entries = json_entries

            # Check index line count。專案層 index 仍含平鋪 shared atom（memory/shared/<slug>.md，
            # 尚未跑 atom-categorize 遷移）→ 只報 info：手寫分區規則＋逐顆列表本來就超 40 行，
            # 遷移完成（index 無平鋪 shared 路徑）才套上限報 warning。
            # 全域 40（各範疇有 _INDEX.md 可 drill）；專案層 150（逐顆列表就住在 MEMORY.md）
            max_lines = INDEX_MAX_LINES if layer_name == "global" else PROJECT_INDEX_MAX_LINES
            if idx_lines > max_lines:
                level, note = "warning", ""
                if layer_name != "global" and _has_flat_shared_entries(index_entries):
                    level = "info"
                    note = "；專案仍含平鋪 shared atom（未遷移）→ 只報 info，遷移後才套上限"
                report.issues.append(
                    Issue(
                        _rel_path(index_path),
                        level,
                        "size",
                        f"MEMORY.md {idx_lines} 行（上限 {max_lines}）{note}",
                    )
                )

            # Validate index ↔ files
            report.issues.extend(validate_index(index_path, mem_dir, index_entries))
        else:
            # Skip "missing MEMORY.md" error if directory has no atom files anywhere
            # in its tree (orphan/empty memory dir from deleted project — harmless)
            has_atoms = any(True for _ in iter_atom_files(mem_dir))
            if has_atoms:
                report.issues.append(
                    Issue(str(mem_dir), "error", "index", "缺少 MEMORY.md 索引檔")
                )

        # Parse all atom files
        for md_file in iter_atom_files(mem_dir):
            atom = parse_atom_file(md_file, layer_name)
            all_atoms.append(atom)
            report.total_atoms += 1

            # Count confidence
            if atom.confidence in VALID_CONFIDENCE:
                report.confidence_counts[atom.confidence] = (
                    report.confidence_counts.get(atom.confidence, 0) + 1
                )

            # Validate format
            report.issues.extend(validate_format(atom))

            # Check staleness
            stale = check_staleness(atom, today)
            if stale:
                report.demotions.append(stale)

            # Check promotions
            promo = suggest_promotions(atom)
            if promo:
                report.promotions.append(promo)

            # 壞滅緣（path 型 Depends 存在性）
            report.stale_deps.extend(check_stale_deps(atom))

    # Detect cross-layer duplicates
    report.duplicates.extend(detect_duplicates(all_atoms))

    # Audit trail statistics
    report.audit_stats = parse_audit_log()

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Atomic Memory System Health Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Scan options
    parser.add_argument("--global-only", action="store_true", help="只掃描全域層")
    parser.add_argument("--project", type=str, default=None, help="指定專案名稱過濾（舊路徑過濾）")
    parser.add_argument("--project-dir", type=str, default=None,
                        help="專案記憶目錄（{project_root}/.claude/memory/），列在全域層之前")
    parser.add_argument("--json", action="store_true", help="JSON 格式輸出")
    parser.add_argument("--verbose", action="store_true", help="含逐 atom 詳細資訊")

    # Decay enforce
    parser.add_argument("--enforce", action="store_true",
                        help="自動淘汰：走 selective forget（score < archive_score_threshold 且非核心保護）"
                             "把候選隔離到原範疇資料夾下的 _distant/；搭配 --dry-run 只列候選")
    parser.add_argument("--dry-run", action="store_true",
                        help="搭配 --enforce/--compact-logs，只報告不執行")

    # Evolution log compaction
    parser.add_argument("--compact-logs", action="store_true",
                        help="壓縮演化日誌：超過 10 筆合併為摘要")

    # Delete propagation
    parser.add_argument("--delete", type=str, metavar="ATOM_NAME",
                        help="刪除 atom（移入 _distant/），全鏈清除 LanceDB + Related 引用 + MEMORY.md 索引")
    parser.add_argument("--purge", type=str, metavar="ATOM_NAME",
                        help="永久刪除 atom（不移入 _distant/），全鏈清除")
    parser.add_argument("--layer", type=str, default="global",
                        help="搭配 --delete/--purge 指定層（default: global）")

    # Distant memory operations
    parser.add_argument("--search-distant", type=str, metavar="KEYWORD", help="搜尋遙遠記憶區")
    parser.add_argument("--restore", type=str, metavar="PATH", help="從遙遠記憶拉回活躍區")
    parser.add_argument("--move-distant", type=str, metavar="PATH", help="手動移入遙遠記憶")

    args = parser.parse_args()

    # Handle delete/purge
    if args.delete or args.purge:
        atom_name = args.delete or args.purge
        purge = bool(args.purge)
        ok, msg = delete_atom(atom_name, args.layer, purge=purge, dry_run=args.dry_run)
        print(msg)
        sys.exit(0 if ok else 1)

    # Handle distant memory operations
    if args.search_distant:
        keyword = args.search_distant
        layers = discover_layers(global_only=args.global_only, project_filter=args.project,
                                 project_dir=_project_dir_from_args(args))
        found_any = False
        for layer_name, mem_dir in layers:
            results = search_distant(mem_dir, keyword)
            if results:
                found_any = True
                print(f"\n[{layer_name}] _distant/ 搜尋結果:")
                for path, title in results:
                    print(f"  {title}")
                    print(f"    路徑: {path}")
        if not found_any:
            print(f"遙遠記憶中找不到包含 '{keyword}' 的 atom。")
        return

    if args.restore:
        path = Path(args.restore)
        ok, msg = restore_from_distant(path)
        print(msg)
        sys.exit(0 if ok else 1)

    if args.move_distant:
        path = Path(args.move_distant)
        ok, msg = move_to_distant(path)
        print(msg)
        sys.exit(0 if ok else 1)

    # Enforce decay
    if args.enforce:
        enforce_decay(args)
        return

    # Compact evolution logs
    if args.compact_logs:
        layers = discover_layers(global_only=args.global_only, project_filter=args.project,
                                 project_dir=_project_dir_from_args(args))
        actions: List[str] = []
        for layer_name, mem_dir in layers:
            for md_file in iter_atom_files(mem_dir):
                result = compact_evolution_logs(md_file, dry_run=args.dry_run)
                if result:
                    actions.append(result)
        if actions:
            print("\n".join(actions))
        else:
            print("No evolution logs require compaction.")
        return

    # Run audit
    report = run_audit(args)

    if args.json:
        print(generate_json_report(report))
    else:
        print(generate_markdown_report(report))

    # Exit code: 1 if any errors
    has_errors = any(i.level == "error" for i in report.issues)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
