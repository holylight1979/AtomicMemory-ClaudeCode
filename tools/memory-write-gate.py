#!/usr/bin/env python3
"""
memory-write-gate.py — Atomic Memory Write Gate (v2.1)

寫入前品質評估 + 去重檢查。用於 session-end 同步前過濾低品質知識。

Usage:
    python memory-write-gate.py --content "知識文字" [--classification "[觀]"] [--trigger-context "..."]
    python memory-write-gate.py --content "知識" --explicit-user
    python memory-write-gate.py --batch items.jsonl

Output: JSON {action, quality_score, reason, dedup_match?, kind, route_to, budget, missing_sections, depends_missing, how}
stdin JSON 另收 mode/existing_path/actions/depends/kind_hint/skip_gate（v6 分型；舊呼叫端不給＝create 全檢）
與 dedupe（去重宣告 {verdict, of, why}：相似度達門檻時不再直接拒寫，回要宣告（need_declaration）＋候選卡，
等 AI 宣告同一條／取代／不同；config write_gate.dedupe_declaration=false 退回舊行為）

Requirements: Python 3.8+. Vector dedup needs Memory Vector Service @ port 3849.
"""

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─── Constants ───────────────────────────────────────────────────────────────

# lib 一律從本腳本所在 repo 根載入（worktree 內跑 verify 不得撈到 live 的 lib）；CLAUDE_DIR 只管 config／audit 落點
_SELF_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SELF_ROOT))
from lib.project_root import claude_data_dir  # noqa: E402

CLAUDE_DIR = claude_data_dir()   # 使用者資料根（WG_CLAUDE_DIR 或 ~/.claude），和 hooks 同一支算法
CONFIG_PATH = CLAUDE_DIR / "workflow" / "config.json"
AUDIT_LOG = CLAUDE_DIR / "memory" / "_vectordb" / "audit.log"

# 大小預算 + 樣式警告：規則單一來源 lib/atom_spec；import 失敗時退最小 fallback
# （預算常數內建、樣式警告停用）並照舊放行其餘檢查——本 gate 不因依賴缺失而更擋人。
try:
    from lib.atom_spec import (
        KNOWLEDGE_BUDGET_BYTES as _BUDGET_DEFAULT,
        knowledge_style_warnings as _style_warnings,
        knowledge_sections_bytes as _knowledge_bytes,
    )
except Exception as _e:  # pragma: no cover
    print(f"[write-gate] lib.atom_spec unavailable, minimal fallback ({_e})",
          file=sys.stderr)
    _BUDGET_DEFAULT = 3072

    def _style_warnings(text):
        return []

    def _knowledge_bytes(text):
        return len((text or "").encode("utf-8"))

# 分型（指標／互補／現況帳／導讀／一般）的五段表與 hub 預算：lib/hub_card 單一來源。
# import 失敗時退最小 fallback（沒有 hub 判定＝全部當一般卡、預算照舊），但訊號必浮出。
try:
    from lib.hub_card import (
        HUB_CARD_BUDGET, HUB_STANDARD_NAMES, check_hub_card_sections, is_hub_card, missing_labels,
        depends_paths, route_doc_for, ROUTE_FALLBACK, budget_limit_for,
    )
except Exception as _e:  # pragma: no cover
    print(f"[write-gate] lib.hub_card unavailable, kind detection degraded ({_e})",
          file=sys.stderr)
    HUB_CARD_BUDGET = 4096
    HUB_STANDARD_NAMES = "做什麼／部位與權威／動手前必問／已知病灶／驗法"
    ROUTE_FALLBACK = "_AIDocs"

    def check_hub_card_sections(text):
        return {"found": [], "missing": [], "headings": []}

    def is_hub_card(text, title="", kind_hint=None):
        return kind_hint == "hub"

    def budget_limit_for(text, default_limit, title="", kind_hint=None):
        return HUB_CARD_BUDGET if kind_hint == "hub" else int(default_limit)

    def missing_labels(keys):
        return list(keys)

    def depends_paths(depends):
        return [str(d) for d in (depends or [])]

    def route_doc_for(paths):
        return ROUTE_FALLBACK

# Quality score components
QUALITY_RULES = {
    "length_20": 0.15,       # content length > 20 chars
    "length_50": 0.10,       # content length > 50 chars
    "tech_terms": 0.15,      # >= 2 technical terms
    "explicit_user": 0.35,   # user explicitly triggered
    "concrete_value": 0.15,  # contains version/path/config value
    "non_transient": 0.10,   # not transient (no timeout/retry/暫時)
    "actionable": 0.15,      # contains action pattern (when X → do Y)
}

# Technical term patterns (common in dev context)
TECH_TERM_PATTERNS = [
    r"\b(?:API|SDK|CLI|HTTP|REST|gRPC|SQL|JSON|YAML|XML|CSV)\b",
    r"\b(?:Git|Docker|Kubernetes|Node|Python|TypeScript|Rust|Go)\b",
    r"\b(?:hook|middleware|endpoint|schema|migration|deploy|build)\b",
    r"\b(?:vector|embedding|LLM|RAG|token|chunk|index)\b",
    r"\b(?:protobuf|flatbuffers|WebSocket|SSE|OAuth|JWT)\b",
    r"\b(?:VRAM|GPU|CUDA|ONNX|model|inference)\b",
    r"(?:版本|設定|路徑|配置|參數|模組|元件|架構|框架)",
]

# Actionable patterns (indicates knowledge that tells you what to do/avoid)
# Note: CJK text has no spaces, so use \s* (optional) for CJK patterns
ACTIONABLE_PATTERNS = [
    r"(?:需要|必須)\s*.{5,}",                                 # CJK directive
    r"(?:不要|避免)\s*.{5,}",                                 # CJK prohibition
    r"(?:否則|不然)\s*.{3,}",                                 # CJK consequence
    r"(?:因為|由於|原因是)\s*.{5,}",                           # CJK causal
    r"(?:如果|when|if)\s*.{3,}(?:就|then|→)",                 # conditional
    r"(?:should|must|need to)\s+.{5,}",                       # EN directive
    r"(?:don't|avoid|never)\s+.{5,}",                         # EN prohibition
    r"(?:because|otherwise)\s+.{5,}",                         # EN causal
    r"→|->|＝>",                                               # arrow = causation
]

# Transient patterns (suggests ephemeral issue, not worth storing)
TRANSIENT_PATTERNS = [
    r"\b(?:timeout|retry|retried|timed?\s*out)\b",
    r"(?:暫時|臨時|偶發|一次性|retry|重試)",
    r"\b(?:pip install .* timeout|npm ERR! network)\b",
]

# Concrete value patterns (version, path, config)
CONCRETE_VALUE_PATTERNS = [
    r"\bv?\d+\.\d+(?:\.\d+)?\b",                    # version numbers
    r"[~/\\][\w./\\-]{5,}",                          # file paths
    r"\b\d{4,5}\b",                                   # port numbers
    r"\b(?:true|false|null|none)\b",                  # config values
    r'["\'][\w./-]+["\']',                            # quoted identifiers
    r"\b\w+=\w+\b",                                   # key=value
]

# Explicit user trigger phrases
EXPLICIT_TRIGGERS = [
    "記住", "以後都這樣", "永遠不要", "永遠", "always", "never",
    "remember", "from now on", "以後",
]

# 可再生內容（Compound Engineering 反事實）：能從最終程式碼／測試／既有文件直接讀出的
# 內容不該進 atom——拿掉它，未來不會重犯、也不用付昂貴重查成本。只加警告訊息，不進分數。
REGENERABLE_LINE_PATTERNS = {
    # `path/file.ext` — 摘要   （檔案索引／導覽目錄）
    "file_listing": re.compile(r"^\s*(?:[-*|]\s*)?`[^`\n]+\.[A-Za-z0-9]{1,5}`\s*(?:—|–|-|:|：|\|)", re.MULTILINE),
    # - `--flag` / `-x`：說明     （CLI 參數逐項）
    "option_listing": re.compile(r"^\s*(?:[-*|]\s*)?`?--?[A-Za-z][\w-]*`?\s*(?::|：|\|)", re.MULTILINE),
    # def foo(...) / function bar(...) / class Baz  （簽名清單）
    "signature_listing": re.compile(r"^\s*(?:[-*|]\s*)?`?(?:def|function|func|class|fn|public|private|static)\s+[A-Za-z_]\w*", re.MULTILINE),
}
REGENERABLE_LINE_MIN = 3
REGENERABLE_TITLE_WORDS = re.compile(
    r"(?:文件索引|目錄結構|檔案清單|檔案索引|函式清單|函數清單|參數一覽|參數說明|API 一覽|欄位說明|doc[- ]?index|file list|directory tree)",
    re.IGNORECASE,
)
REGENERABLE_CODE_FENCE_LINES = 8
REGENERABLE_HINT = (
    "能從最終程式碼／測試／既有文件直接讀出的內容不收——反事實自問：拿掉這顆 atom，"
    "未來會重犯或付昂貴重查成本嗎？不會 → 改寫成文件路徑一行＋只留結論／決策／踩坑"
)


def regenerable_signals(content: str) -> List[str]:
    """回可再生內容的訊號名清單（空＝沒命中）。純啟發式，只用來出警告，不擋。"""
    signals: List[str] = []
    for name, pat in REGENERABLE_LINE_PATTERNS.items():
        n = len(pat.findall(content))
        if n >= REGENERABLE_LINE_MIN:
            signals.append(f"{name}x{n}")
    if REGENERABLE_TITLE_WORDS.search(content):
        signals.append("index_title")
    fenced = 0
    in_fence = False
    for line in content.split("\n"):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            fenced += 1
    if fenced >= REGENERABLE_CODE_FENCE_LINES:
        signals.append(f"code_dump_{fenced}l")
    return signals


# ─── 分型（v6 M1：寫進去的東西要有用）─────────────────────────────────────────
# kind ∈ pointer（指標卡：只留一行指標）／complement（互補：append 前算預算）／
# ledger（現況帳：放文件）／hub（導讀卡：五段齊＋Depends、預算 4096）／plain（一般）。
# 超預算不截斷內容，改告訴寫入者該去哪（route_to）、缺哪段（missing_sections）。

KINDS = ("pointer", "complement", "ledger", "hub", "plain")
MODES = ("create", "append", "replace")

_LEDGER_DATE_RE = re.compile(r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b|\b\d{1,2}/\d{1,2}\b")
# 帳目數字＝「數字＋量詞或單位」；純技術名詞裡的數字（HTTP 429、UTF-8、TLS 1.2、v1.2.3）不算
_LEDGER_QTY_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:筆|次|個|項|行|檔|張|顆|條|件|列|人|天|日|週|月|年|萬|倍|分鐘|小時|秒|"
    r"%|％|ms|s|m|h|KB|MB|GB|k|K|px|tok|tokens?|errors?|warnings?|fails?|failed|pass(?:ed)?|tests?|cases?)"
    r"(?![A-Za-z0-9.])",
    re.IGNORECASE,
)
_LEDGER_HEADER_RE = re.compile(r"^\s*\|[^\n]*(?:現況|狀態|進度|日期|結果|完成度)[^\n]*\|", re.MULTILINE)
LEDGER_MIN_ROWS = 3

HOW_BY_KIND = {
    "pointer": "指標卡只留一行指標：位置＋動手前必問，不複述本體；本體住內容卡或文件",
    "complement": "互補卡 append 前先算預算（既有＋新增 ≤ 上限）；超了把個案細節寫進 route_to 的文件，卡只留結論一行＋路徑",
    "ledger": "現況帳（逐筆日期／數字、狀態表）放 route_to 的文件；卡只留「現況見 <路徑>」一行",
    "hub": "導讀卡五段必齊（做什麼／權威在哪／動手前必問／已知病灶／驗法）＋ Depends 指主要檔；預算 4096 bytes",
    "plain": "一般卡：結論／判斷／教訓一行一條；個案事實與逐筆清單移文件，卡留路徑一行",
}


def ledger_signals(content: str) -> List[str]:
    """現況帳訊號：≥LEDGER_MIN_ROWS 行「日期＋（數字＋量詞／單位）」、或表格列、或現況表頭；空＝不是帳。
    日期去掉後只剩技術名詞裡的數字（HTTP 429、UTF-8、TLS 1.2）不算帳目行。"""
    rows = 0
    for line in (content or "").splitlines():
        if not _LEDGER_DATE_RE.search(line):
            continue
        rest = _LEDGER_DATE_RE.sub(" ", line)
        if line.lstrip().startswith("|") or _LEDGER_QTY_RE.search(rest):
            rows += 1
    out: List[str] = []
    if rows >= LEDGER_MIN_ROWS:
        out.append(f"dated_rows x{rows}")
    if _LEDGER_HEADER_RE.search(content or ""):
        out.append("status_table")
    return out


def _read_existing(existing_path: Optional[str]) -> str:
    if not existing_path:
        return ""
    try:
        return Path(existing_path).read_text(encoding="utf-8-sig")
    except (OSError, ValueError):
        return ""


def classify_kind(
    content: str,
    title: str = "",
    mode: str = "create",
    existing_content: str = "",
    kind_hint: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    actions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """回 {kind, hub:{found,missing}, ledger:[訊號], existing_hub:bool}。
    優先序：pointer（明給或指標標題且無段）> hub > ledger > complement（append）> plain。kind_hint 只在合法時採用，
    且 hub 仍要過五段檢查（hint 不能把缺段卡變成合格 hub）。"""
    config = config or {}
    hint = kind_hint if kind_hint in KINDS else None
    scan = content + ("\n" + "\n".join(str(a) for a in (actions or [])) if actions else "")
    hub = check_hub_card_sections(scan)
    existing_hub = bool(existing_content) and is_hub_card(existing_content)
    ledger = ledger_signals(content)
    # 指標卡優先：明給 kind_hint=pointer，或標題帶指標詞（導讀／hub索引…）且內容一段都沒有（一行指標）
    if hint == "pointer" or (mode != "append" and is_pointer_title(title, config) and not hub["found"]):
        kind = "pointer"
    elif mode != "append" and is_hub_card(scan, title, hint):
        kind = "hub"
    elif ledger or hint == "ledger":
        kind = "ledger"
    elif mode == "append" or hint == "complement":
        kind = "complement"
    else:
        kind = hint or "plain"
    return {"kind": kind, "hub": hub, "ledger": ledger, "existing_hub": existing_hub, "scan": scan}


# ─── Config ──────────────────────────────────────────────────────────────────


def load_config() -> Dict[str, Any]:
    """Load write_gate config from workflow config."""
    defaults = {
        "enabled": True,
        # 品質分數只分寫／不寫：舊的 ask 級（0.3～0.5）呼叫端從沒接過、一律照寫，故拿掉，線留在原 ask 線
        "quality_floor": 0.3,
        "dedup_score": 0.80,
        "dedupe_declaration": True,   # 相似度達門檻 → 要 AI 宣告（false＝舊行為：>0.95 skip、其餘 suggest update）
        "skip_on_explicit_user": True,
        "knowledge_budget_bytes": _BUDGET_DEFAULT,  # <=0 停用大小硬拒
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            defaults.update(cfg.get("write_gate", {}))
        except (json.JSONDecodeError, OSError):
            pass
    return defaults


# ─── Quality Score ───────────────────────────────────────────────────────────


def compute_quality_score(
    content: str,
    explicit_user: bool = False,
    trigger_context: str = "",
) -> Tuple[float, List[str]]:
    """Compute rule-based quality score. Returns (score, reasons)."""
    score = 0.0
    reasons: List[str] = []

    # Length checks
    if len(content) > 20:
        score += QUALITY_RULES["length_20"]
        reasons.append(f"length>{20}")
    if len(content) > 50:
        score += QUALITY_RULES["length_50"]
        reasons.append(f"length>{50}")

    # Technical terms
    tech_count = 0
    combined = content + " " + trigger_context
    for pattern in TECH_TERM_PATTERNS:
        tech_count += len(re.findall(pattern, combined, re.IGNORECASE))
    if tech_count >= 2:
        score += QUALITY_RULES["tech_terms"]
        reasons.append(f"tech_terms={tech_count}")

    # Explicit user trigger
    if explicit_user:
        score += QUALITY_RULES["explicit_user"]
        reasons.append("explicit_user")
    else:
        # Check if trigger_context contains explicit phrases
        for phrase in EXPLICIT_TRIGGERS:
            if phrase in trigger_context.lower():
                score += QUALITY_RULES["explicit_user"]
                reasons.append(f"explicit_phrase={phrase}")
                break

    # Concrete values
    for pattern in CONCRETE_VALUE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            score += QUALITY_RULES["concrete_value"]
            reasons.append("concrete_value")
            break

    # Non-transient
    is_transient = False
    for pattern in TRANSIENT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            is_transient = True
            reasons.append("transient_content")
            break
    if not is_transient:
        score += QUALITY_RULES["non_transient"]
        reasons.append("non_transient")

    # Actionability check
    for pattern in ACTIONABLE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            score += QUALITY_RULES["actionable"]
            reasons.append("actionable")
            break

    return min(score, 1.0), reasons


# ─── Dedup Check ─────────────────────────────────────────────────────────────


_POINTER_MARKERS_DEFAULT = ["導讀", "hub索引", "指標卡", "索引卡", "知識地圖"]


def is_pointer_title(title: str, config: Dict[str, Any]) -> bool:
    """指標卡（導讀／hub 索引／知識地圖）：只列位置與必問、不複述本體，跟內容卡的詞彙天生重疊。"""
    markers = config.get("pointer_markers") or _POINTER_MARKERS_DEFAULT
    t = (title or "").lower()
    return any(m.lower() in t for m in markers)


def dedup_threshold_for(config: Dict[str, Any], title: str = "") -> float:
    """一般卡用 dedup_score（0.80）；指標卡用 dedup_pointer_score（0.95，只擋真重複）。"""
    if is_pointer_title(title, config):
        return float(config.get("dedup_pointer_score", 0.95))
    return float(config.get("dedup_score", 0.80))


# ─── 去重宣告（相似 → AI 判同一條／取代／不同；程式只核形狀、照宣告路由、留帳）──────────
# 判斷交 AI：程式不判「像到什麼程度算同一條」，門檻只決定要不要問。
# 核對只看三件事：verdict 三選一、of 是這次列出的候選卡名（原字）、why 有字（不是空白／佔位／純標點）。

DEDUPE_VERDICTS = ("same", "supersedes", "different")
DEDUPE_FORMS = (
    ("same", "同一條（知識段改併入那張卡；triggers／actions 不併）"),
    ("supersedes", "取代（寫新卡，Supersedes 標那張；舊卡留檔、不再注入）"),
    ("different", "不同（照常寫新卡）"),
)
DEDUPE_CANDIDATES_MAX = 3   # 候選張數＝向量查詢 top_k：要逐張對照，3 張已涵蓋同主題的改名／拆卡，再多只是雜訊
DEDUPE_EXCERPT_LINES = 2    # 每張節錄知識段前 2 行：認得出那張卡在講什麼就夠判；要細看 AI 自己開檔
_DEDUPE_WHY_TEMPLATE = "一句理由"   # 寫法範本裡的佔位字，照抄回來不算理由
_KNOWLEDGE_BODY_RE = re.compile(r"^##[ \t]+(?:知識|印象)[ \t]*\n([\s\S]*?)(?=^## |\Z)", re.MULTILINE)
_BULLET_RE = re.compile(r"^[-*]\s+")


def _knowledge_excerpt(file_path: str, fallback_text: str) -> List[str]:
    """候選卡知識段前 DEDUPE_EXCERPT_LINES 行（去 bullet、每行 ≤120 字）；檔讀不到就退用向量命中的那段文字。"""
    body = ""
    if file_path:
        try:
            m = _KNOWLEDGE_BODY_RE.search(Path(file_path).read_text(encoding="utf-8-sig"))
            body = m.group(1) if m else ""
        except (OSError, ValueError):
            body = ""
    lines = (_BULLET_RE.sub("", ln.strip()) for ln in (body or fallback_text or "").splitlines())
    return [ln[:120] for ln in lines if ln][:DEDUPE_EXCERPT_LINES]


def _dedupe_candidates(results: List[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
    """門檻以上的命中，依分數排、取前 DEDUPE_CANDIDATES_MAX 張（同層同名只留一次）。
    ref＝of 要照抄的名字：卡名在候選裡唯一就是卡名；不同層有同名卡就寫成 <layer>:<卡名>，兩張都列、交 AI 選。"""
    out: List[Dict[str, Any]] = []
    seen = set()
    for r in sorted(results, key=lambda r: r.get("score", 0), reverse=True):
        name, layer = r.get("atom_name", ""), r.get("layer", "")
        if not name or (layer, name) in seen or r.get("score", 0) < threshold:
            continue
        seen.add((layer, name))
        out.append({
            "atom_name": name,
            "score": round(r.get("score", 0), 3),
            "layer": layer,
            "excerpt": _knowledge_excerpt(r.get("file_path", ""), r.get("text", "")),
        })
    out = out[:DEDUPE_CANDIDATES_MAX]
    names = [c["atom_name"] for c in out]
    for c in out:
        c["ref"] = c["atom_name"] if names.count(c["atom_name"]) == 1 else f"{c['layer']}:{c['atom_name']}"
    return out


def _why_has_content(why: Any) -> bool:
    """why 去掉標點／符號／空白／控制字元後還有字，且不是範本佔位字照抄。"""
    core = "".join(ch for ch in str(why or "") if unicodedata.category(ch)[0] not in "PSZC")
    return bool(core) and core != _DEDUPE_WHY_TEMPLATE


def dedupe_problems(dedupe: Any, candidates: List[Dict[str, Any]]) -> List[str]:
    """核對 AI 的去重宣告形狀，回問題清單（空＝收）。不判宣告內容對不對——那是 AI 的判斷，抽查靠 audit。"""
    if not isinstance(dedupe, dict):
        return ["dedupe 要是物件 {verdict, of, why}"]
    problems = []
    verdict = dedupe.get("verdict")
    if verdict not in DEDUPE_VERDICTS:
        problems.append(f"verdict 要是 same／supersedes／different 其中一個（收到 {verdict!r}）")
    of = str(dedupe.get("of") or "").strip()
    refs = [c["ref"] for c in candidates]
    if of not in refs:
        same_name = [r for r, c in zip(refs, candidates) if c["atom_name"] == of]
        problems.append(f"of「{of}」在不同層各有一張，寫成 {' 或 '.join(same_name)}" if same_name
                        else f"of「{of}」不在這次列出的候選卡裡（卡名原字照抄）")
    if not _why_has_content(dedupe.get("why")):
        problems.append("why 要寫一句理由（收到空白、佔位或純標點）")
    return problems


def declaration_request(candidates: List[Dict[str, Any]], threshold: float, problems: List[str]) -> str:
    """要宣告（need_declaration）的 reason：（宣告不收的原因）＋候選卡（名、分數、層、知識段節錄）＋三種寫法。js 原文轉述。"""
    lines = [f"宣告不收：{'；'.join(problems)}。"] if problems else []
    lines.append(f"需要宣告（這次不寫檔）：新內容和既有卡相似度達 {threshold:.2f}，"
                 "請判斷是同一條、取代、還是不同，帶 dedupe 欄位重送。")
    lines.append("候選卡：")
    for i, c in enumerate(candidates, 1):
        layer = f"，layer={c['layer']}" if c.get("layer") else ""
        lines.append(f"{i}. {c['ref']}（score={c['score']}{layer}）")
        lines.extend(f"   ｜{ln}" for ln in c["excerpt"])
    lines.append("三種寫法（of 照抄上面一張卡名）：")
    for verdict, meaning in DEDUPE_FORMS:
        lines.append(f'- {meaning}：dedupe={{"verdict":"{verdict}","of":"<卡名>","why":"<{_DEDUPE_WHY_TEMPLATE}>"}}')
    lines.append("（atom_write 沒有 dedupe 欄位＝這個 session 的 MCP 還是舊碼：Reload Window 後重送）")
    return "\n".join(lines)


def check_dedup(
    content: str,
    config: Dict[str, Any],
    layers: Optional[List[str]] = None,
    title: str = "",
) -> Optional[Dict[str, Any]]:
    """Check for duplicate knowledge via Vector Service. Returns match info or None.

    layers：只跟這幾層比（global + 當前專案自己的層）。不傳 = 全庫比對，會撞到
    別的專案／別人 personal 層的 atom（寫入者根本不能 append 到那裡）。
    title：指標卡（見 is_pointer_title）門檻提高，避免導讀卡撞內容卡。
    """
    try:
        port = 3849
        # Load vector config from main config
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                full_cfg = json.load(f)
            vs_cfg = full_cfg.get("vector_search", {})
            port = vs_cfg.get("service_port", 3849)
    except Exception:
        pass

    dedup_threshold = dedup_threshold_for(config, title)

    try:
        query: Dict[str, Any] = {"q": content, "top_k": DEDUPE_CANDIDATES_MAX, "min_score": dedup_threshold}
        if layers:
            query["layers"] = ",".join(layers)
        params = urllib.parse.urlencode(query)
        url = f"http://127.0.0.1:{port}/search?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            results = json.loads(resp.read())

        if not results:
            return None

        top = results[0]
        score = top.get("score", 0)
        if score < dedup_threshold:
            return None

        return {
            "atom_name": top.get("atom_name", ""),
            "score": round(score, 3),
            "text_preview": top.get("text", "")[:80],
            "verdict": "duplicate" if score > 0.95 else "similar",
            "candidates": _dedupe_candidates(results, dedup_threshold),
        }
    except Exception as e:
        # Vector service unavailable — fail-open skip dedup，但必留訊號（可觀測性鐵律）
        write_audit_log("dedup_skipped_service_down", content, 0, error=str(e)[:120])
        print(f"[write-gate] dedup skipped: vector service unavailable ({e})",
              file=sys.stderr)
        return None


# ─── Audit Log ───────────────────────────────────────────────────────────────


def write_audit_log(action: str, content_preview: str, quality: float, **extra: Any) -> None:
    """Append to audit.log (JSONL)."""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "content": content_preview[:80],
        "quality": round(quality, 2),
    }
    entry.update(extra)
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Log rotation: >10MB → rotate
        if AUDIT_LOG.stat().st_size > 10 * 1024 * 1024:
            _rotate_log()
    except OSError:
        pass


def _rotate_log() -> None:
    """Simple log rotation: keep 3 copies."""
    for i in range(2, 0, -1):
        src = AUDIT_LOG.with_suffix(f".log.{i}")
        dst = AUDIT_LOG.with_suffix(f".log.{i + 1}")
        if src.exists():
            if i == 2:
                try:
                    src.unlink()
                except OSError:
                    pass
            else:
                try:
                    src.rename(dst)
                except OSError:
                    pass
    try:
        AUDIT_LOG.rename(AUDIT_LOG.with_suffix(".log.1"))
    except OSError:
        pass


# ─── Gate Decision ───────────────────────────────────────────────────────────


def evaluate(
    content: str,
    classification: str = "[臨]",
    trigger_context: str = "",
    explicit_user: bool = False,
    config: Optional[Dict[str, Any]] = None,
    layers: Optional[List[str]] = None,
    title: str = "",
    mode: str = "create",
    existing_path: Optional[str] = None,
    actions: Optional[List[str]] = None,
    depends: Optional[List[str]] = None,
    kind_hint: Optional[str] = None,
    skip_gate: bool = False,
    dedupe: Any = None,
) -> Dict[str, Any]:
    """Main Write Gate evaluation. Returns decision dict.

    舊鍵不變：action／quality_score／reason／dedup_match?／warnings?／regenerable_signals?。
    新鍵（每次都回）：kind ∈ KINDS、route_to（部位文件路徑或層名）、budget{bytes,limit,existing_bytes}、
    missing_sections[]（hub 缺段白話名）、depends_missing（hub 無 Depends）、how（一句怎麼做）。
    layers：去重只比這幾層（見 check_dedup）。title：指標卡去重門檻提高。
    mode≠create 或 skip_gate：跳 dedup／quality，只做預算與分型（append 預算＝既有 knowledge 區＋新增）。
    dedupe：去重宣告（見 dedupe_problems）。相似度達門檻時：沒宣告或宣告不收 → 拒寫要宣告（action=skip＋
    need_declaration=true、candidates[]、reason 列候選與三種寫法）；收 → audit dedupe_declared，same 回 action=append＋append_to{atom_name,layer}，
    supersedes／different 照常往下判，結果帶 dedupe_declared{verdict,of,why,score}。沒命中仍給 → dedupe_note。
    """
    if config is None:
        config = load_config()
    mode = mode if mode in MODES else "create"
    existing = _read_existing(existing_path) if mode != "create" else ""
    cls = classify_kind(content, title, mode, existing, kind_hint, config, actions)
    kind = cls["kind"]
    hub_check = cls["hub"]

    # 預算：hub（或 append 到既有 hub 卡）用 HUB_CARD_BUDGET（根層固定）；其餘用 config。
    try:
        budget = int(config.get("knowledge_budget_bytes", _BUDGET_DEFAULT))
    except (TypeError, ValueError):
        budget = _BUDGET_DEFAULT
    # 預算上限與落檔端同源（lib/hub_card.budget_limit_for）：append 看既有卡全文（H1 含導讀／五段齊），
    # create／replace 看新內容＋標題＋kind_hint
    hint = kind_hint if kind_hint in KINDS else None
    limit = (budget_limit_for(existing, budget) if mode == "append"
             else budget_limit_for(cls["scan"], budget, title, hint))
    nbytes = len(content.encode("utf-8"))
    existing_bytes = _knowledge_bytes(existing) if (mode == "append" and existing) else 0
    total = nbytes + existing_bytes
    route_paths = depends_paths(depends) + ([existing_path] if existing_path else [])
    route_to = route_doc_for(route_paths)
    missing = missing_labels(hub_check["missing"]) if kind == "hub" else []
    # Depends 三態：None＝未提供（replace 沿用舊檔的 Depends 行）；[]＝明給清空（視為沒有）；非空＝用新的
    if depends is None:
        has_depends = _existing_depends(existing)
    else:
        has_depends = bool(depends_paths(depends))
    depends_missing = kind == "hub" and not has_depends

    def _kinded(result: Dict[str, Any]) -> Dict[str, Any]:
        result.update({
            "kind": kind,
            "route_to": route_to,
            "budget": {"bytes": nbytes, "limit": limit, "existing_bytes": existing_bytes},
            "missing_sections": missing,
            "depends_missing": bool(depends_missing),
            "how": HOW_BY_KIND[kind],
        })
        return result

    # 現況帳：不進 atom，路由到文件（不看預算、不看 explicit_user）
    if kind == "ledger":
        write_audit_log("skip", content, 0, reason="ledger", signals=cls["ledger"], route_to=route_to)
        return _kinded({
            "action": "skip",
            "quality_score": 0,
            "reason": (
                f"現況帳（{', '.join(cls['ledger']) or kind_hint}）不進 atom；放文件 {route_to}；"
                f"卡只留「現況見 {route_to}」一行"
            ),
        })

    # 大小預算硬拒：排最前：explicit_user / pitfall 捷徑皆不豁免（「記住」不等於
    # 可以把個案敘事整坨塞進 atom）。不截斷內容：告訴寫入者該去哪、剩多少。
    # 落檔端 lib/atom_io_cli 另有同源 floor 檢查（skip_gate 繞過本 gate 時仍會被攔）。
    if 0 < limit < total:
        if mode == "append":
            kind = "complement"
        write_audit_log("skip", content, 0, reason="over_budget",
                        bytes=total, budget=limit, kind=kind, route_to=route_to)
        detail = (f"（既有 {existing_bytes}＋新增 {nbytes}）" if existing_bytes else "")
        hub_hint = (
            f"。若這是導讀卡：補齊五段標準名（{HUB_STANDARD_NAMES}）或帶 kind_hint=hub"
            if kind == "plain" else ""
        )
        return _kinded({
            "action": "skip",
            "quality_score": 0,
            "reason": (
                f"knowledge 區 {total} bytes{detail} 超過預算 {limit} bytes；個案事實移文件"
                f"（不截斷：個案細節寫進 {route_to}；atom 只留結論/判斷/教訓/檔案錨點，"
                "大段逐筆內容改為文件路徑一行）" + hub_hint
            ),
        })

    # 導讀卡：五段齊＋Depends 必填（缺的列出來，不放行）
    if kind == "hub" and (missing or depends_missing):
        parts = []
        if missing:
            parts.append(f"五段缺 {len(missing)} 段：{'、'.join(missing)}")
        if depends_missing:
            parts.append("缺 Depends（path:<主要檔>，健檢靠它驗過期）")
        write_audit_log("skip", content, 0, reason="hub_incomplete",
                        missing=hub_check["missing"], depends_missing=bool(depends_missing))
        return _kinded({
            "action": "skip",
            "quality_score": 0,
            "reason": "導讀卡不合格；" + "；".join(parts) + "；補齊再寫（不截斷、不代填）",
        })

    # mode≠create／skip_gate：只做預算與分型，不跑 dedup／quality
    if mode != "create" or skip_gate:
        write_audit_log("add", content, 1.0, reason=f"{mode}_budget_only", kind=kind)
        result = {
            "action": "add",
            "quality_score": 1.0,
            "reason": f"{mode}: budget {total}/{limit} ok, kind={kind}",
        }
        if dedupe is not None:
            result["dedupe_note"] = f"dedupe 宣告已忽略：{'skip_gate' if skip_gate else 'mode=' + mode} 不跑去重"
        return _kinded(result)

    # 內容樣式軟警 + 可再生內容判準（都不擋、不進分數，附掛在放行結果上；caller 端轉述給寫入者）
    style_warns = list(_style_warnings(content))
    regen = regenerable_signals(content)
    soft_warns = style_warns + (
        [f"可再生內容疑似（{', '.join(regen)}）：{REGENERABLE_HINT}"] if regen else []
    )

    declared: Optional[Dict[str, Any]] = None   # 收下的去重宣告（supersedes／different 往下判時帶出去）
    dedupe_note: Optional[str] = None

    def _with_warnings(result: Dict[str, Any]) -> Dict[str, Any]:
        if soft_warns and result.get("action") == "add":
            result["warnings"] = soft_warns
        if regen:
            result["regenerable_signals"] = regen
        if declared:
            result["dedupe_declared"] = declared
        if dedupe_note:
            result["dedupe_note"] = dedupe_note
        return _kinded(result)

    # Fast path: explicit user trigger → always add
    # Note: [固] no longer fast-paths here — 移除反向激勵，[固] 也需過 dedup/quality
    if explicit_user:
        write_audit_log("add", content, 1.0, classification=classification, reason="explicit_user")
        return _with_warnings({
            "action": "add",
            "quality_score": 1.0,
            "reason": "explicit user trigger",
        })

    # Dedup check（先於 pitfall 捷徑：pitfall 只豁免品質評分，不豁免去重——
    # 相似的坑知識照樣要宣告；舊行為 >0.95 skip、相似建議 update）
    dedup = check_dedup(content, config, layers, title)
    dedup_match = {k: v for k, v in (dedup or {}).items() if k != "candidates"}   # 舊鍵形狀不變
    if dedup and not config.get("dedupe_declaration", True):
        if dedup["verdict"] == "duplicate":
            write_audit_log("skip", content, 0, reason="duplicate", dedup_match=dedup["atom_name"])
            return _kinded({
                "action": "skip",
                "quality_score": 0,
                "reason": f"duplicate of {dedup['atom_name']} (score={dedup['score']})",
                "dedup_match": dedup_match,
            })
        # Similar but not identical → suggest update
        write_audit_log("update", content, 0.6, dedup_match=dedup["atom_name"])
        return _kinded({
            "action": "update",
            "quality_score": 0.6,
            "reason": f"similar to {dedup['atom_name']} (score={dedup['score']}), suggest update",
            "dedup_match": dedup_match,
        })
    candidates = (dedup or {}).get("candidates") or []   # 命中卻沒卡名＝無從宣告，當沒命中
    if candidates:
        problems = [] if dedupe is None else dedupe_problems(dedupe, candidates)
        if dedupe is None or problems:
            write_audit_log("need_declaration", content, 0,
                            candidates=[c["ref"] for c in candidates], problems=problems)
            # action 用 skip（不用新動作名）：合併後 py 立即生效、各 session 的 MCP js 要 Reload 才換新碼，
            # 舊 js 只認 skip／update 為拒寫，新動作名會被它當放行直接落檔；新 js 認 need_declaration 轉述
            return _kinded({
                "action": "skip",
                "need_declaration": True,
                "quality_score": 0,
                "reason": declaration_request(candidates, dedup_threshold_for(config, title), problems),
                "dedup_match": dedup_match,
                "candidates": candidates,
            })
        target = next(c for c in candidates if c["ref"] == str(dedupe["of"]).strip())
        declared = {"verdict": dedupe["verdict"], "of": target["atom_name"],
                    "why": str(dedupe["why"]).strip(), "score": target["score"]}
        write_audit_log("dedupe_declared", content, 0, **declared)
        if declared["verdict"] == "same":
            return _kinded({
                "action": "append",
                "quality_score": 1.0,
                "reason": (f"dedupe 宣告 same：知識段改併入既有卡 {target['atom_name']}"
                           f"（score={target['score']}；triggers／actions 不併）"),
                "append_to": {"atom_name": target["atom_name"], "layer": target["layer"]},
                "dedupe_declared": declared,
            })
    elif dedupe is not None:
        dedupe_note = "dedupe 宣告已忽略：這次沒有候選卡（相似度未達門檻，或向量服務沒回應）"

    # Pitfall/trap detection → add with [觀]（僅豁免品質評分；dedup 已在上方跑過）
    pitfall_keywords = ["陷阱", "坑", "pitfall", "gotcha", "注意", "caution", "bug", "重入"]
    if any(kw in content.lower() or kw in trigger_context.lower() for kw in pitfall_keywords):
        quality = 0.7
        write_audit_log("add", content, quality, classification="[觀]", reason="pitfall_detected")
        return _with_warnings({
            "action": "add",
            "quality_score": quality,
            "reason": "pitfall/trap detected, auto-add as [觀]",
        })

    # Quality score：只分寫／不寫（寫的人就是要寫的 AI，沒有「再問一次」的中間級）
    quality, reasons = compute_quality_score(content, explicit_user, trigger_context)
    # 沒設 quality_floor 的舊 config：實際生效的寫入線一直是 ask_threshold（ask 級照寫），沿用它
    quality_floor = config.get("quality_floor", config.get("ask_threshold", 0.3))
    action = "add" if quality >= quality_floor else "skip"

    write_audit_log(action, content, quality, classification=classification, reasons=reasons)

    return _with_warnings({
        "action": action,
        "quality_score": round(quality, 2),
        "reason": f"quality={quality:.2f} ({'>=' if action == 'add' else '<'}floor {quality_floor}), factors: {', '.join(reasons)}",
    })


_DEPENDS_LINE_RE = re.compile(r"^- Depends:\s*(.+)$", re.MULTILINE)


def _existing_depends(existing: str) -> bool:
    """既有卡檔頭已有 `- Depends:` 行（replace 未給 depends 時沿用原行，不算缺）。"""
    m = _DEPENDS_LINE_RE.search(existing or "")
    return bool(m and m.group(1).strip())


_GATE_OPT_KEYS = ("mode", "existing_path", "actions", "depends", "kind_hint", "skip_gate", "dedupe")


def _gate_opts(item: Dict[str, Any]) -> Dict[str, Any]:
    """stdin／batch 的分型選項：只取有給的鍵（舊呼叫端不給＝create 全檢，行為不變）。"""
    out: Dict[str, Any] = {}
    for k in _GATE_OPT_KEYS:
        if item.get(k) is not None:
            out[k] = item[k]
    return out


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Atomic Memory Write Gate (v2.1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--content", type=str, help="要評估的知識文字")
    parser.add_argument("--classification", type=str, default="[臨]",
                        help="知識分類 [固]/[觀]/[臨]")
    parser.add_argument("--trigger-context", type=str, default="",
                        help="觸發此知識的上下文")
    parser.add_argument("--explicit-user", action="store_true",
                        help="使用者明確要求記住")
    parser.add_argument("--batch", type=str, metavar="FILE",
                        help="批次處理 JSONL 檔案")

    args = parser.parse_args()
    config = load_config()

    if args.batch:
        # Batch mode: process JSONL
        try:
            with open(args.batch, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    result = evaluate(
                        content=item.get("content", ""),
                        classification=item.get("classification", "[臨]"),
                        trigger_context=item.get("trigger_context", ""),
                        explicit_user=item.get("explicit_user", False),
                        config=config,
                        layers=item.get("layers") or None,
                        title=item.get("title", "") or "",
                        **_gate_opts(item),
                    )
                    print(json.dumps(result, ensure_ascii=False))
        except (OSError, json.JSONDecodeError) as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)
    elif args.content:
        result = evaluate(
            content=args.content,
            classification=args.classification,
            trigger_context=args.trigger_context,
            explicit_user=args.explicit_user,
            config=config,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # Read from stdin (for pipe usage)
        raw = sys.stdin.read().strip()
        if raw:
            try:
                item = json.loads(raw)
                result = evaluate(
                    content=item.get("content", ""),
                    classification=item.get("classification", "[臨]"),
                    trigger_context=item.get("trigger_context", ""),
                    explicit_user=item.get("explicit_user", False),
                    config=config,
                    layers=item.get("layers") or None,
                    title=item.get("title", "") or "",
                    **_gate_opts(item),
                )
                print(json.dumps(result, ensure_ascii=False, indent=2))
            except json.JSONDecodeError:
                # Treat as plain text
                result = evaluate(content=raw, config=config)
                print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
