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
import math
import re
import sys
import time
from collections import Counter
from functools import lru_cache
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wg_core import (
    CLAUDE_DIR, MEMORY_DIR, EPISODIC_DIR, WORKFLOW_DIR,
    MEMORY_INDEX, ATOM_INDEX, REALM_AUTOMOVE_MARKER,
    CONTEXT_BUDGET_DEFAULT, TURN_BUDGET_LIMIT,
    compute_token_budget,  # re-export：budget 單一來源在 wg_core，舊 caller 仍從本模組 import
    _estimate_tokens,  # CJK-aware 估算器（單一口徑，中文 ~1.5 tok/字）
    discover_all_project_memory_dirs, resolve_access_json, resolve_staging_dir,
    get_project_memory_dir, log_promotion_audit, log_promotion_heartbeat,
    _atom_debug_log, _atom_debug_error,
    sanitize_harness_noise,
)

# prefer _atom_index.json (machine source of truth)
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
    from atom_locations import is_in_failures_path
except ImportError:
    is_in_failures_path = None

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
    優先 _atom_index.json，fallback _ATOM_INDEX.md → MEMORY.md。
    """
    # prefer JSON
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
            # 表內容忍（2026-05 silent-failure 真因防線 direction 1）：空行 skip 不結束表
            #（寫入端意外留空行不該 silent 掉後續 atom）；重複表頭 skip（多區塊表不誤收
            # 表頭為 atom）。僅「非空且非 |」的真內容才視為表結束。
            if stripped == "":
                continue
            if stripped.startswith("| Atom") or stripped.startswith("|Atom"):
                continue
            if stripped.startswith("|---") or stripped.startswith("| ---"):
                continue
            if not stripped.startswith("|"):
                in_table = False
                continue
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if len(cells) >= 3:
                name = cells[0]
                rel_path = cells[1]
                # lowercase + strip + 保序去重（大小寫重複會讓 count_trigger_hits 灌水）
                triggers = list(dict.fromkeys(t.strip().lower() for t in cells[2].split(",") if t.strip()))
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


# ─── Per-turn 讀取快取原語 ───────────────────────────────────────────────────
# UPS 管線同一顆 atom 每 prompt 會被讀 3-4 次（supersedes 掃描 / related 擴散 /
# assemble / usefulness hints），access sidecar 更多（activation / rank / hot-cold /
# hints）。cache 參數皆可選：None 時自讀（各函式保持可獨測），呼叫端傳同一 dict
# 即得單次讀取共用（hook 行程 per-event 短命，無跨 prompt 失效問題）。


def read_atom_text(
    atom_path: Path, cache: Optional[Dict[str, Optional[str]]] = None,
) -> Optional[str]:
    """讀 atom 內文（utf-8-sig）；cache 提供時同 path 只實讀一次（含失敗 None 也快取）。"""
    key = str(atom_path)
    if cache is not None and key in cache:
        return cache[key]
    try:
        text = atom_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        text = None
    if cache is not None:
        cache[key] = text
    return text


def load_access_cached(
    atom_md_path: Path, cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """讀 atom 的 access sidecar（正規化 dict；檔缺/損毀回 defaults）。

    優先走 lib.atom_access.read_access（v3 正規化，timestamps/α/β 欄位齊）；
    lib 不可用時退直讀 raw JSON（caller 以 .get 容忍缺欄）。cache 同 read_atom_text。
    """
    key = str(atom_md_path)
    if cache is not None and key in cache:
        return cache[key]
    data: Dict[str, Any] = {}
    try:
        from lib.atom_access import read_access
        data = read_access(atom_md_path)
    except Exception:
        acc = atom_md_path.parent / f"{atom_md_path.stem}.access.json"
        try:
            raw = json.loads(acc.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except (OSError, json.JSONDecodeError, ValueError):
            data = {}
    if cache is not None:
        cache[key] = data
    return data


def _find_atom_path(name: str, all_atoms: List[Tuple[AtomEntry, Path]]) -> Optional[Path]:
    for (aname, rel_path, _triggers), base_dir in all_atoms:
        if aname == name:
            return (base_dir / rel_path) if rel_path else (base_dir / "memory" / f"{name}.md")
    return None


# ─── Scope 可見性（SPEC §8.1）────────────────────────────────────────────────
# 候選池在 SessionStart 只裝「本人看得到的」atom：global + 本專案 shared/failures +
# 本人 roles + 本人 personal。之後 trigger / BM25 / vector / related 全從這個池取，
# 不各自再過濾。scope 由索引 path 推導、不信 index 的 scope 欄（自動萃取曾把
# 專案層條目寫成 global）。他專案的 atom 從不進池；他專案只靠 alias 帶入 MEMORY.md。


def scope_from_rel_path(rel_path: str, layer: str = "shared") -> str:
    """索引 path → scope 標籤：personal:<user> / role:<role>；其餘回 layer（global|shared）。
    單一來源在 lib.atom_locations.scope_from_index_path（寫入端 write_index 缺省 scope、
    sync-atom-index --fix-scope-from-path 同用）；lib 不可用時本地退化實作同規則。"""
    try:
        from atom_locations import scope_from_index_path
        return scope_from_index_path(rel_path, layer)
    except ImportError:
        pass
    parts = [p for p in str(rel_path).replace("\\", "/").split("/") if p]
    dirs = parts[:-1]
    for i, seg in enumerate(dirs):
        if seg == "personal" and i + 1 < len(dirs):
            owner = dirs[i + 1]
            if owner == "auto" and i + 2 < len(dirs):
                owner = dirs[i + 2]  # personal/auto/<user>/：自動萃取候選，仍屬該使用者
            return f"personal:{owner}"
        if seg == "roles" and i + 1 < len(dirs):
            return f"role:{dirs[i + 1]}"
    return layer


def entry_visible(rel_path: str, user: Optional[str], roles: Optional[List[str]]) -> bool:
    """personal 只給本人、role 只給持有者；shared / global 對全員可見。"""
    label = scope_from_rel_path(rel_path)
    if label.startswith("personal:"):
        return bool(user) and label[len("personal:"):] == user
    if label.startswith("role:"):
        return label[len("role:"):] in set(roles or ())
    return True


def filter_visible(
    entries: List[AtomEntry], user: Optional[str], roles: Optional[List[str]],
) -> List[AtomEntry]:
    return [e for e in entries if entry_visible(e[1], user, roles)]


def visible_vector_layers(
    project_slug: str, user: Optional[str], roles: Optional[List[str]],
    include_local: bool = False,
) -> List[str]:
    """向量服務 layer 標籤白名單，與候選池同一套可見性（indexer 標籤：global /
    extra:local-atoms / shared:<slug> / role:<slug>:<r> / personal:<slug>:<u>）。"""
    layers = ["global"]
    if include_local:
        layers.append("extra:local-atoms")
    if user:
        layers.append(f"personal:global:{user}")  # 本人跨專案 personal（~/.claude/memory/personal/<u>/）
    if project_slug:
        layers.append(f"shared:{project_slug}")
        for r in roles or ():
            layers.append(f"role:{project_slug}:{r}")
        if user:
            layers.append(f"personal:{project_slug}:{user}")
    return layers


# ─── Atom Matching & Activation ──────────────────────────────────────────────


def spread_related(
    matched_names: set,
    all_atoms: List[Tuple[AtomEntry, Path]],
    already_injected: List[str],
    max_depth: int = 1,
    content_cache: Optional[Dict[str, Optional[str]]] = None,
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
            text = read_atom_text(atom_path, content_cache)
            if text is None:
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


# 個別化 decay 旋鈕預設（config usefulness.stability_gamma；0=關閉退回固定 d=0.5）
_STABILITY_GAMMA_DEFAULT = 0.3
_DECAY_D_MIN = 0.3
_DECAY_D_MAX = 0.5


def _decay_exponent(access: Dict[str, Any], config: Optional[Dict[str, Any]]) -> float:
    """ACT-R decay 指數 d 的個別化：d = clamp(0.5 − γ·wilson_lb, 0.3, 0.5)。

    被效用閉環證明有用的 atom（Wilson 下界高）衰減更慢（記憶更穩固）。
    無 config（legacy caller）/ γ≤0 / 無效用樣本（n=0）→ 0.5 不變。fail-open。
    """
    if not config:
        return _DECAY_D_MAX
    u = config.get("usefulness") or {}
    try:
        gamma = float(u.get("stability_gamma", _STABILITY_GAMMA_DEFAULT))
    except (TypeError, ValueError):
        return _DECAY_D_MAX
    if gamma <= 0:
        return _DECAY_D_MAX
    try:
        from lib.atom_access import usefulness_stats
        st = usefulness_stats(access, z=float(u.get("wilson_z", 1.28)))
        if st.get("n", 0) <= 0:
            return _DECAY_D_MAX
        return min(_DECAY_D_MAX, max(_DECAY_D_MIN, _DECAY_D_MAX - gamma * st["lower_bound"]))
    except Exception:
        return _DECAY_D_MAX


def compute_activation(
    atom_name: str, atom_dir: Path,
    config: Optional[Dict[str, Any]] = None,
    access_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> float:
    """ACT-R base-level activation: B_i = ln(Σ t_k^{-d})。

    d 預設 0.5；config 給定時走 _decay_exponent 個別化（效用高者衰減慢）。
    無 access log（新 atom / sidecar 缺失）回中性 0.0——不當「最低分」
    讓新 atom 在排序/截斷時優先被犧牲（曝光都還沒開始就被壓死）。
    """
    data = load_access_cached(atom_dir / f"{atom_name}.md", access_cache)
    timestamps = data.get("timestamps") or []
    if not timestamps:
        return 0.0
    d = _decay_exponent(data, config)
    now = time.time()
    total = 0.0
    for ts in timestamps:
        try:
            t_k = max(now - float(ts), 1.0)
        except (TypeError, ValueError):
            continue
        total += t_k ** -d
    return math.log(total) if total > 0 else 0.0


def compute_injection_rank(
    atom_name: str, atom_dir: Path, config: Optional[Dict[str, Any]] = None,
    access_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> float:
    """注入排序鍵 = ACT-R activation − 分心懲罰（高曝光低效用者降權）。

    憲法 Context Distraction 對策（_AIDocs/context-memory-governance.md）：read_hits 是
    純曝光、不代表有用；對「已有足夠效用樣本(n≥min_n)但 Wilson 下界低」的 atom 課
    penalty = w·log10(read_hits+1)·(1−lb)，降其注入優先序。
    寧漏勿誤殺：n<min_n（新 atom / 樣本不足）一律不罰；關閉 / 資料缺失 → 退回純
    activation（fail-open）。config usefulness.distraction_{enabled,weight} 旋鈕。
    """
    activation = compute_activation(atom_name, atom_dir, config, access_cache)
    if not config:
        return activation  # 無 config（讀取失敗）→ fail-open 不罰
    u = config.get("usefulness") or {}
    if not u.get("distraction_enabled", True):
        return activation
    weight = float(u.get("distraction_weight", 0.5) or 0.0)
    if weight <= 0:
        return activation
    # 核心策展 atom（decisions/workflow-*/preferences/toolchain/feedback-* ...）豁免
    # distraction penalty。turn-global 歸因下高頻核心 atom 系統性累積無辜 β，penalty 反把最重的
    # 懲罰打在最該注入的人工策展知識上（曝光越高罰越重＝頻率 artifact，與策展價值反相關）＝止血。
    try:
        from lib.atom_locations import is_core_protected_name
        if is_core_protected_name(atom_name):
            return activation
    except Exception:
        pass
    try:
        from lib.atom_access import usefulness_stats
        acc = load_access_cached(atom_dir / f"{atom_name}.md", access_cache)
        read_hits = int(acc.get("read_hits") or 0)
        if read_hits <= 0:
            return activation
        st = usefulness_stats(acc, z=float(u.get("wilson_z", 1.96)))
        if st.get("n", 0) < int(u.get("min_n", 3)):
            return activation  # 樣本不足不罰（保守，防壓新 atom）
        penalty = weight * math.log10(read_hits + 1) * (1.0 - st.get("lower_bound", 0.0))
        return activation - penalty
    except Exception:
        return activation


@lru_cache(maxsize=4096)
def _kw_pattern(kw: str) -> "re.Pattern":
    """trigger keyword → 編譯後 word-boundary pattern（memoized）。

    全索引 trigger 詞彙量超過 re 模組內建 512 條 pattern cache 上限時，每次
    _kw_match 觸發整包重編譯（實測佔 UPS 主路徑 ~85% CPU）；以本地 lru_cache
    釘住（詞彙量由索引大小自然封頂，4096 綽綽有餘）。
    """
    return re.compile(r'(?<![\w-])' + re.escape(kw) + r'(?![\w-])')


def _kw_match(kw: str, prompt_lower: str) -> bool:
    """Match a trigger keyword against prompt. ASCII uses word-boundary, CJK uses substring."""
    if kw.isascii():
        # 廉價預篩：literal kw 非子字串則 pattern 必不中——絕大多數 keyword 未出現在
        # prompt，免掉 per-kw regex 編譯/搜尋（冷行程全索引 ~千餘詞的編譯是 UPS
        # 主路徑最大 CPU 項）。語意零變：子字串包含是 word-boundary match 的必要條件。
        if kw not in prompt_lower:
            return False
        return bool(_kw_pattern(kw).search(prompt_lower))
    return kw in prompt_lower


def any_trigger_hit(keywords, prompt_lower: str) -> bool:
    """keyword 清單 vs prompt 的單一比對原語（trigger match / AIDocs sweep 共用）。"""
    return any(_kw_match(kw, prompt_lower) for kw in keywords)


def count_trigger_hits(keywords, prompt_lower: str) -> int:
    """命中數版本（RRF trigger 路排序依據）。"""
    return sum(1 for kw in keywords if _kw_match(kw, prompt_lower))


def match_triggers(prompt: str, atoms: List[AtomEntry]) -> List[AtomEntry]:
    prompt_lower = prompt.lower()
    matched = []
    for name, rel_path, triggers in atoms:
        if any_trigger_hit(triggers, prompt_lower):
            matched.append((name, rel_path, triggers))
    return matched


# ─── BM25 Match ─────────────────────────────────────────────────────
# Hand-rolled BM25 over atom trigger lists. ~30 lines, no external dep.
# Use case: global layer (~17 atoms) — replaces vector service round-trip
# (200-500ms) with in-memory <10ms scoring.

_BM25_K1 = 1.2
_BM25_B = 0.75
# min_score 預設單一來源（簽名預設 / UPS fallback / sub-agent blob 三處同值）
# 7.0 由回歸集調參定案：負例誤注入 21.4%→0%、R@3 -1.5pt（漏網由 vector fallback 補位）
BM25_MIN_SCORE_DEFAULT = 7.0


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
    min_score: float = BM25_MIN_SCORE_DEFAULT,
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


# ─── RRF 融合（多路檢索 rank 融合）───────────────────────────────────────────
# 多路（trigger / bm25 / vector）都有結果時，排序以 Reciprocal Rank Fusion 取代
# 「各路各自門檻 + 串接」：score = Σ_routes 1/(k + rank)。只決定排序；各路既有
# min_score（BM25 3.5 / vector 0.65）仍是入場過濾，不因融合放寬。
# config: vector_search.fusion = "rrf"（預設）| "legacy"（回退原排序）。

RRF_K_DEFAULT = 60
# activation（記憶強度）作為融合後排序的乘性調節：final = rrf · exp(gain·rank)。
# gain=0.25 → activation ±2 對應 ×0.61…×1.65 調節——相關性（RRF）為主、
# 記憶強度為輔，不讓 activation 的大值域反客為主。
RRF_ACTIVATION_GAIN = 0.25


def rrf_fuse(
    route_ranked: Dict[str, List[str]], k: int = RRF_K_DEFAULT,
) -> Dict[str, float]:
    """RRF rank 融合：route_ranked = {route: [name 依該路排序]} → {name: score}。

    純函式；rank 1-based（清單首位 rank=1 → 1/(k+1)）。多路命中者分數相加。
    """
    scores: Dict[str, float] = {}
    for names in route_ranked.values():
        for i, nm in enumerate(names):
            scores[nm] = scores.get(nm, 0.0) + 1.0 / (k + i + 1)
    return scores


# ─── Token Budget & Atom Loading ─────────────────────────────────────────────
# budget 常數/計算已集中 wg_core（見該檔「Token budget 單一來源」註解）；
# compute_token_budget 由上方 import re-export。


_STRIP_META_RE = re.compile(
    r"^- (?:Scope|Type|Trigger|Last-used|Created|Confirmations|ReadHits|Tags|TTL|Expires-at):\s.*$\n?",
    re.MULTILINE,
)

_STRIP_SECTION_RE = re.compile(
    r"^## (?:行動|演化日誌)\s*\n[\s\S]*?(?=^## |\Z)",
    re.MULTILINE,
)

_FRONTMATTER_KEEP_RE = re.compile(
    r"^- (?:Confidence|Trigger|Last-used|Status):\s*.+$",
    re.MULTILINE,
)

_KNOWLEDGE_CAP_TOKENS_DEFAULT = 200


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
    # 依實際 token/char 密度換算截斷字元數（CJK 密度高、chars/token 低）
    chars_per_token = len(full) / full_tokens if full_tokens else 4.0
    target_chars = int(max_tokens * chars_per_token) - len(header) - len(marker)
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


_FALLBACK_KNOWLEDGE_LINES = 2   # 無「印象」段時保留的知識條數（[固]/[觀] 優先）
_FALLBACK_LINE_CHARS = 160      # 每條節錄上限字元（長條目截尾加 …，避免降級版逼近全文大小）


def _strip_atom_for_injection_impression_only(content: str) -> str:
    """budget fallback 用的最小注入：表頭 + 印象段；無印象段則補知識段前幾條，
    讓降級注入仍帶最低知識量（只剩標題+trigger 等於沒唸卻照樣佔 token）。"""
    parts: List[str] = []
    header = _extract_title_and_frontmatter(content)
    if header:
        parts.append(header)
    impression = _extract_named_section(content, "印象")
    if impression:
        parts.append(impression)
    else:
        knowledge = _extract_named_section(content, "知識")
        if knowledge:
            bullets = [ln for ln in knowledge.splitlines() if ln.lstrip().startswith("- ")]
            ranked = ([b for b in bullets if "[固]" in b or "[觀]" in b]
                      + [b for b in bullets if "[固]" not in b and "[觀]" not in b])
            picked = [
                (b if len(b) <= _FALLBACK_LINE_CHARS else b[:_FALLBACK_LINE_CHARS].rstrip() + "…")
                for b in ranked[:_FALLBACK_KNOWLEDGE_LINES]
            ]
            if picked:
                parts.append("## 知識（節錄）\n" + "\n".join(picked))
    return "\n\n".join(parts).strip()


_TURN_BUDGET_LIMIT = TURN_BUDGET_LIMIT  # 舊名 re-export（caller/verify 鎖定此名）


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

_STATUS_LINE_RE = re.compile(r"^- Status:\s*(.+)$", re.MULTILINE)
_STATUS_CAP = 40


def atom_status_suffix(raw_content: str) -> str:
    """atom 選填 `- Status:` 現況行 → 一行注入（cold / budget skip）的附帶字串。

    肥 atom 被降為一行路標時，不展開也保有最低現況資訊量（如「案結」＝
    收尾期非爭議期）。無 Status 行回空字串。"""
    m = _STATUS_LINE_RE.search(raw_content or "")
    if not m:
        return ""
    val = m.group(1).replace("\n", " ").replace("\r", " ").strip()
    if not val:
        return ""
    if len(val) > _STATUS_CAP:
        val = val[:_STATUS_CAP].rstrip() + "…"
    return f" [Status: {val}]"


def _recent_count(timestamps: Any) -> int:
    """timestamps 清單中落在 7d 窗內的筆數（_recent_reads_7d / cache 路徑共用）。"""
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


def _recent_reads_7d(access_file: Path) -> int:
    if not access_file.exists():
        return 0
    try:
        data = json.loads(access_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    timestamps = data.get("timestamps", []) if isinstance(data, dict) else []
    return _recent_count(timestamps)


def classify_hot_cold(
    atom_path: Path, source: str, hot_recent_threshold: int = 3,
    access_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    if source == "trigger":
        return "hot"
    if access_cache is not None:
        data = load_access_cached(atom_path, access_cache)
        recent = _recent_count(data.get("timestamps"))
    else:
        access_file = atom_path.parent / f"{atom_path.stem}.access.json"
        recent = _recent_reads_7d(access_file)
    return "hot" if recent >= hot_recent_threshold else "cold"


def pointer_path(
    atom_path: Optional[Path] = None, rel_path: str = "", name: str = "",
) -> str:
    """一行路標的路徑渲染：有實檔路徑就給絕對路徑（正斜線）。

    atom 分屬多個 realm root（~/.claude 與各專案 .claude），rel_path 只相對它自己
    那顆 root；消費端（模型）拿到裸相對路徑只能以 cwd 解析 → 跨 realm 必斷鏈，
    最壞是解析到同名的另一顆檔。故路標一律絕對化；atom_path 缺席（legacy caller）
    才退回 rel_path。
    """
    if atom_path is not None:
        return Path(atom_path).as_posix()
    return rel_path or f"{name}.md"


def format_cold_inject_line(
    name: str, raw_content: str, rel_path: str, atom_path: Optional[Path] = None,
) -> str:
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

    display_path = pointer_path(atom_path, rel_path, name)
    status = atom_status_suffix(raw_content)
    return f"[Atom:{name}] (cold) {summary}{status} (full: Read {display_path})"


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
        content_tokens = _estimate_tokens(content)
        if used + content_tokens <= budget_tokens:
            lines.append(f"[Atom:{name}]\n{content}")
            injected.append(name)
            used += content_tokens
        else:
            first_line = content.split("\n", 1)[0].strip("# ").strip()
            lines.append(f"[Atom:{name}] {first_line} (full: Read {pointer_path(atom_path)})")
            injected.append(name)
            break

    return lines, injected, used


# ─── Sub-agent Injection Orchestrator ──────────────────────────
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
        try:
            from wg_core import load_config
            _bm25_ms = float(
                (load_config().get("vector_search") or {})
                .get("bm25_min_score", BM25_MIN_SCORE_DEFAULT)
            )
        except Exception:
            _bm25_ms = BM25_MIN_SCORE_DEFAULT
        for entry in bm25_match(prompt_str, entries, min_score=_bm25_ms, top_k=_SUBAGENT_TOP_K):
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


# ─── Use 偵測：詞彙重疊 ────────────────────────────────────────
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
    import urllib.request

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


# 截斷指標行數量上限（config injection.truncated_pointer_max 覆寫）：超支犧牲的
# atom 中只有 activation 最高的前 N 顆留一行指標，其餘整塊不注入——寧缺勿截，
# 截到只剩路標的條目幾乎零效用卻照樣耗 budget，數量必須有頂。
TRUNCATED_POINTER_MAX_DEFAULT = 3


def _resolve_block_activation(
    atom_name: str, src_dir: Optional[Path], fallback_roots: List[Path],
) -> Tuple[float, Optional[Path]]:
    """回 (activation, src_dir)。src_dir 給定直接算；否則只採「access sidecar 實際
    存在」的 root 取最高分（compute_activation 對缺檔回中性 0.0，不過濾會讓缺檔
    root 的 0.0 蓋掉真實負值 activation）。"""
    if src_dir:
        return compute_activation(atom_name, src_dir), src_dir
    best: Optional[float] = None
    best_dir: Optional[Path] = None
    for cand in fallback_roots:
        if not (cand / f"{atom_name}.access.json").exists():
            continue
        score = compute_activation(atom_name, cand)
        if best is None or score > best:
            best = score
            best_dir = cand
    return (0.0 if best is None else best), best_dir


def _truncate_context_by_activation(
    lines: List[str], limit: int = CONTEXT_BUDGET_DEFAULT,
    source_dirs: Optional[Dict[str, Path]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Truncate additionalContext lines to fit within token budget.

    超支時按 ACT-R activation 由低到高犧牲 atom 區塊。activation 是近期存取強度
    （log 尺度天然跨零），負值≠不相關——相關性已由 trigger/BM25/vector 入場閘
    把關，故不做 activation<=0 過濾（會誤殺低近期性但高相關的策展 atom）。
    寧缺勿截：被犧牲者中 activation 較高的前 N 顆（injection.truncated_pointer_max）
    降級成一行指標，其餘整塊移除；兩者皆落 atom-debug log，且尾行 budget 標記
    附裁切統計（可觀測性鐵律：降級必浮出訊號）。"""
    full_text = "\n".join(lines)
    used = _estimate_tokens(full_text)
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
                "tokens": _estimate_tokens(block_text),
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
        ab["activation"], ab["src_dir"] = _resolve_block_activation(
            ab["name"],
            source_dirs.get(ab["name"]) if source_dirs else None,
            fallback_roots,
        )

    atom_blocks.sort(key=lambda x: x["activation"])

    def _display_path(ab: dict) -> str:
        """截斷提示的真實路徑：src_dir 優先，否則掃 roots 找實檔（絕對路徑，跨 realm 可解析）。"""
        name = ab["name"]
        src = ab.get("src_dir")
        if src is None:
            for cand in fallback_roots:
                if (cand / f"{name}.md").exists():
                    src = cand
                    break
        if src is None:
            return (MEMORY_DIR / f"{name}.md").as_posix()  # 找不到實檔的最後退路
        return pointer_path(Path(src) / f"{name}.md")

    pointer_max = int(
        ((config or {}).get("injection") or {})
        .get("truncated_pointer_max", TRUNCATED_POINTER_MAX_DEFAULT)
    )

    # Phase A：由低 activation 到高標記需犧牲的區塊（以指標行節省量估算，直到夠用）
    reduce_list: List[dict] = []
    projected = used
    for ab in atom_blocks:
        if projected <= limit:
            break
        summary = f"[Atom:{ab['name']}] (truncated) Read {_display_path(ab)}"
        saved = ab["tokens"] - _estimate_tokens(summary)
        if saved <= 0:
            continue
        ab["summary"] = summary
        ab["pointer_saved"] = saved
        reduce_list.append(ab)
        projected -= saved

    # Phase B：從 activation 高到低回填——塞得下全文就恢復全文；塞不下且指標行
    # 未達上限就留一行指標；再不行整塊移除。Phase A 以「指標行節省量」估算犧牲
    # 名單，若直接把名單外的全丟，整塊移除省下的遠多於估算，預算會被砍到遠低於
    # 上限（實測 359/1000 卻丟 5 顆）；回填讓預算用滿、犧牲最少。
    truncated_indices: set = set()
    dropped_indices: set = set()
    used_now = used - sum(ab["tokens"] for ab in reduce_list)
    pointers = 0
    for ab in reversed(reduce_list):
        ptr_tokens = ab["tokens"] - ab["pointer_saved"]
        if used_now + ab["tokens"] <= limit:
            used_now += ab["tokens"]
            _atom_debug_log(
                "BUDGET",
                f"final-trim atom={ab['name']} activation={ab['activation']:.2f} form=restored-full",
                config,
            )
        elif pointers < pointer_max and used_now + ptr_tokens <= limit:
            truncated_indices.add(ab["start"])
            used_now += ptr_tokens
            pointers += 1
            _atom_debug_log(
                "BUDGET",
                f"final-trim atom={ab['name']} activation={ab['activation']:.2f} form=pointer",
                config,
            )
        else:
            dropped_indices.add(ab["start"])
            _atom_debug_log(
                "BUDGET",
                f"final-trim atom={ab['name']} activation={ab['activation']:.2f} "
                "form=dropped（塞不下全文也塞不下指標，或指標行已達上限）",
                config,
            )
    used = used_now

    new_lines: List[str] = []
    skip_until = -1
    for idx, line in enumerate(lines):
        if idx < skip_until:
            continue
        found = False
        for ab in atom_blocks:
            if ab["start"] != idx:
                continue
            if idx in truncated_indices:
                new_lines.append(ab["summary"])
                skip_until = ab["end"]
                found = True
            elif idx in dropped_indices:
                skip_until = ab["end"]
                found = True
            break
        if not found and idx >= skip_until:
            new_lines.append(line)

    # 尾行附裁切統計：降級不得無聲（可觀測性鐵律），明細在 atom-debug log
    trim_note = ""
    if reduce_list:
        n_ptr = len(truncated_indices)
        n_drop = len(dropped_indices)
        trim_note = f" | trim: {n_ptr} pointer, {n_drop} dropped"
    new_lines.append(f"[Context budget: {used}/{limit} tokens{trim_note}]")
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
            # 表內容忍（同 _parse_trigger_table，silent-failure direction 1）：空行 skip
            # 不結束表；重複表頭 skip。僅「非空且非 |」真內容才視為表結束。
            if stripped == "":
                continue
            if stripped.startswith("| #") or stripped.startswith("|#"):
                continue
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
                    keywords = list(dict.fromkeys(k.strip().lower() for k in cells[3].split(",") if k.strip()))
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
    """Rule-based intent classifier. Zero LLM overhead (~1ms)。

    _kw_match：ASCII 詞 word-boundary（防 "fix" 誤中 "prefix" 類子字串）、
    CJK 維持子字串比對。
    """
    prompt_lower = prompt.lower()
    scores = {}
    for intent, keywords in INTENT_PATTERNS.items():
        scores[intent] = sum(1 for kw in keywords if _kw_match(kw, prompt_lower))
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

    # harness 標籤/hook 殘渣先剔——first_prompt_summary 會進 episodic 摘要與
    # handoff 提示，殘留 <ide_opened_file> 等雜訊會污染跨 session 記憶。
    # 首 prompt 若剔完全空（純 IDE 事件），留空讓下一個真 prompt 補位。
    clean_prompt = sanitize_harness_noise(prompt)
    if not tracker.get("first_prompt_summary") and clean_prompt:
        tracker["first_prompt_summary"] = clean_prompt[:200]

    existing_kw = set(tracker.get("keyword_signals", []))
    words = re.findall(r"[a-zA-Z一-鿿]{4,}", clean_prompt)
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
        import logging.handlers

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


_REKICK_MARKER = WORKFLOW_DIR / "vector_rekick.marker"
_REKICK_COOLDOWN_S = 120.0


def _ensure_vector_ready(
    session_id: Optional[str],
    *,
    flag_path: Optional[Path] = None,
    marker_path: Optional[Path] = None,
    spawn: bool = True,
    wait_s: float = 0.3,
) -> Tuple[bool, bool]:
    """flag 缺失時的 UPS 端自癒。回 (ready, kicked)。

    fire-and-forget spawn starter.py（cooldown 防同 session 連環 spawn），再短等
    ≤wait_s 一次性補救「服務活著只是 flag 遺失」類（starter 首次 health 成功即回寫
    flag，毫秒級）；真冷啟動秒級以上，本輪照舊 fallback、下一 prompt 收割。
    """
    flag = flag_path or (WORKFLOW_DIR / "vector_ready.flag")
    if flag.exists():
        return True, False
    marker = marker_path or _REKICK_MARKER
    kicked = False
    try:
        stale = (
            not marker.exists()
            or time.time() - marker.stat().st_mtime > _REKICK_COOLDOWN_S
        )
        if stale and spawn:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(str(time.time()), encoding="utf-8")
            import subprocess
            starter = CLAUDE_DIR / "tools" / "memory-vector-service" / "starter.py"
            kw: Dict[str, Any] = {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if sys.platform == "win32":
                kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
            else:
                kw["start_new_session"] = True
            subprocess.Popen(
                [sys.executable, str(starter),
                 "--phase", "ups_rekick", "--session-id", session_id or ""],
                **kw,
            )
            kicked = True
    except Exception as e:
        _atom_debug_error("vector:rekick", e)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        time.sleep(0.1)
        if flag.exists():
            return True, kicked
    return False, kicked


def _search_episodic_context(
    prompt: str, config: Dict[str, Any], session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Query /search/episodic for related past sessions. First-prompt only."""
    import urllib.parse
    import urllib.request

    vs_config = config.get("vector_search", {})
    if not vs_config.get("enabled", True):
        _log_vector_obs(session_id, "_search_episodic_context", "disabled", 0, True)
        return []
    sc_config = config.get("session_context", {})
    if not sc_config.get("enabled", True):
        _log_vector_obs(session_id, "_search_episodic_context", "disabled", 0, True)
        return []
    _ready, _kicked = _ensure_vector_ready(session_id)
    if not _ready:
        _log_vector_obs(session_id, "_search_episodic_context", "no_flag", 0, True,
                        extra={"rekicked": _kicked})
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
    layers: Optional[List[str]] = None,
) -> List[Tuple[str, str, List[str], List[Dict]]]:
    """Query Memory Vector Service with intent-aware ranked search.

    layers：可見 layer 白名單（visible_vector_layers），服務端只在這幾層查；
    user/roles 仍一併送，給尚未支援 layers 的舊服務退回 role clause。"""
    import urllib.error
    import urllib.parse
    import urllib.request

    vs_config = config.get("vector_search", {})
    if not vs_config.get("enabled", True):
        _log_vector_obs(session_id, "_semantic_search", "disabled", 0, True,
                        extra={"intent": intent})
        return []
    _ready, _kicked = _ensure_vector_ready(session_id)
    if not _ready:
        _log_vector_obs(session_id, "_semantic_search", "no_flag", 0, True,
                        extra={"intent": intent, "rekicked": _kicked})
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
            if layers:
                p["layers"] = ",".join(layers)
            return p

        use_sections = True
        params_dict = _add_identity({
            "q": prompt, "top_k": top_k,
            "min_score": min_score,
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
                    "min_score": min_score,
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
    import urllib.request

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


def _is_unconfirmed_autocapture(entry: Dict[str, Any]) -> bool:
    """index entry 是否為『未確認的 auto-capture 萃取碎片』→ drift sweep defer（不搬、不喚 LLM 學詞）。

    auto-captured 碎片本是未經人確認的 [臨] 萃取，sweep 卻當穩定 core atom
    處理 → LLM 對其吐專案/標籤詞污染學習詞庫（外部專案知識被搬進根層 _atoms/、碎片被塞進
    名為 "auto-capture" 的葉夾即此）。整體 defer 斷源頭，待人工確認 / 晉升（[臨]→[觀]）後才正常
    sweep 歸檔。

    判定（index-only 優先，零 file I/O）：triggers 含 'auto-capture'（extract-worker 預設標籤，
    涵蓋現存全部污染）。次判（frontmatter，非熱路徑）：Author==auto-captured 且 Confidence==[臨]
    ——catch『domain_tags 已填、trigger 非預設』但仍未確認的碎片；晉升後 Confidence 變 → 不再 defer。
    """
    for t in (entry.get("triggers") or []):
        if "auto-capture" in str(t).lower():
            return True
    author = conf = ""
    for line in _read_atom_excerpt(entry.get("path") or "", limit=400).splitlines():
        s = line.strip()
        if s.startswith("- Author:"):
            author = s.split(":", 1)[1].strip().lower()
        elif s.startswith("- Confidence:"):
            conf = s.split(":", 1)[1].strip()
        if author and conf:
            break
    return author == "auto-captured" and conf == "[臨]"


def _autocapture_unconfirmed_from_text(text: str) -> bool:
    """body 全文判『未確認 auto-capture 碎片』（晉升掃描面用，零額外 file I/O）。

    規則與 _is_unconfirmed_autocapture **同一條**，只是輸入適配器不同（index entry vs 已載入
    body 全文）：① `- Trigger:` 行含 'auto-capture'（index triggers 即由此行建，已實證 byte-mirror
    → 等價）；② Author==auto-captured 且 Confidence==[臨]。兩者皆 catch 未經人確認的 [臨] 萃取碎片。
    改動判定規則時兩函式須同步（adapter 並存、規則單源）。
    """
    trig = author = conf = ""
    for line in text.splitlines():
        s = line.strip()
        if not trig and s.startswith("- Trigger:"):
            trig = s.split(":", 1)[1].lower()
        elif not author and s.startswith("- Author:"):
            author = s.split(":", 1)[1].strip().lower()
        elif not conf and s.startswith("- Confidence:"):
            conf = s.split(":", 1)[1].strip()
        if trig and author and conf:
            break
    if "auto-capture" in trig:
        return True
    return author == "auto-captured" and conf == "[臨]"


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


def select_forget_candidates(archive_candidates, config):
    """Phase D selective forgetting：從封存候選篩出可隔離者（憲法 Forgetting 對策）。

    規則：score < isolate_threshold 且 atom 名不在核心保護清單
    （LOCAL_REALM_CORE_PROTECTED_EXACT）。純函式、可測。
    """
    fcfg = ((config or {}).get("self_iteration") or {}).get("forget") or {}
    threshold = float(fcfg.get("isolate_threshold", 0.3))
    try:
        from lib.atom_locations import LOCAL_REALM_CORE_PROTECTED_EXACT as _protected
    except Exception:
        _protected = frozenset()
    out = []
    for c in (archive_candidates or []):
        if float(c.get("score", 1.0)) >= threshold:
            continue
        if c.get("atom") in _protected:
            continue
        out.append(c)
    return out


def apply_selective_forget(archive_candidates, config, *, atoms_dir=None,
                           staging_dir=None):
    """Phase D selective forgetting：stale+低用+非保護 atom 隔離到 `_distant/`。

    `_distant/` 已被 sync-atom-index EXCLUDED_DIR_PARTS 排除 → 搬入即不入索引/不注入、
    且可逆（搬回即復原），無需手改 index row。**預設 dry-run**（forget.enabled=false
    或 dry_run=true）→ 只寫候選清單到 _staging、不搬。憲法 selective forgetting 對策。
    回 {mode, candidates, forgotten, skipped}。
    """
    atoms_dir = atoms_dir or MEMORY_DIR
    fcfg = ((config or {}).get("self_iteration") or {}).get("forget") or {}
    cands = select_forget_candidates(archive_candidates, config)
    if staging_dir is not None and cands:  # 候選清單寫 _staging（always；bare count → 可行動）
        try:
            staging_dir.mkdir(parents=True, exist_ok=True)
            lines = ["# Selective-Forget 候選（stale + 低用 + 非核心保護）", ""]
            lines += [f"- {c.get('atom')} (score={c.get('score')}, "
                      f"last_used={c.get('last_used')})" for c in cands]
            (staging_dir / "forget-candidates.md").write_text(
                "\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            _atom_debug_error("forget:write_candidates", e)
    cand_names = [c.get("atom") for c in cands]
    if not bool(fcfg.get("enabled", False)) or bool(fcfg.get("dry_run", True)):
        return {"mode": "dry_run", "candidates": cand_names, "forgotten": [], "skipped": []}
    import shutil
    distant = atoms_dir / "_distant"
    forgotten, skipped = [], []
    for c in cands:
        slug = c.get("atom")
        md = atoms_dir / f"{slug}.md"
        if not md.exists():
            skipped.append(slug)
            continue
        try:
            distant.mkdir(parents=True, exist_ok=True)
            shutil.move(str(md), str(distant / md.name))
            acc = atoms_dir / f"{slug}.access.json"
            if acc.exists():
                shutil.move(str(acc), str(distant / acc.name))
            forgotten.append(slug)
        except OSError as e:
            _atom_debug_error("forget:isolate", e)
            skipped.append(slug)
    if forgotten:
        _trigger_sync_memory_index()  # 重產索引/catalog（_distant 已排除，移除其列）
    return {"mode": "isolated", "candidates": cand_names,
            "forgotten": forgotten, "skipped": skipped}


def _is_atom_physical_rel(rel: str) -> bool:
    """rel（相對 ~/.claude、POSIX）落在 atom 物理區（失敗家族新舊址 / _AIDocs/_atoms/）⇒ True。"""
    if is_in_failures_path is not None and is_local_realm_path is not None:
        return is_in_failures_path(rel) or is_local_realm_path(rel)
    return (rel.startswith("memory/Failures/") or rel.startswith("_AIDocs/Failures/")
            or rel.startswith("_AIDocs/_atoms/"))


def _scan_doc_refs(moved: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """搬移後掃**人面向說明文件**是否仍含舊 path/檔名引用（移檔非建檔特有；user 補充）。

    回 {slug: [需同步的 rel 文件...]}。只掃 _AIDocs/（排除 atom 物理區：舊址 Failures/ 與 _atoms/，
    那裡的 slug 引用是 atom-atom Related、搬 path 不斷）＋根層 README/TECH。advisory only。
    """
    docs: List[Path] = []
    aidocs = CLAUDE_DIR / "_AIDocs"
    if aidocs.is_dir():
        for p in aidocs.rglob("*.md"):
            rel = p.relative_to(CLAUDE_DIR).as_posix()
            if _is_atom_physical_rel(rel):
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
            if scope_from_rel_path(path, "global").startswith("personal:"):
                continue  # 本人跨專案 personal：只給本人，不進 realm 搬移
            if _is_unconfirmed_autocapture(a):
                continue  # P2: 未確認 auto-capture 碎片 → defer（不搬、不喚 LLM 學詞，斷詞庫污染源）
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
    """Atom decay scoring + 效用驅動 [臨]→[觀] auto-promotion.

    Runs at SessionEnd. Scans all atom files, calculates health scores,
    auto-promotes [臨] items in mature atoms, reports archive/demote candidates.

    效用驅動：
      - 慢衰減：每顆 atom α←1+λ(α−1); β←1+λ(β−1)（λ≈0.97），把效用證據往 prior 拉。
      - 晉升閘改由「真實 Confirmations 主軌 + 效用 Wilson 下界」驅動；
        ReadHits 降為純曝光計數，不再單獨觸發晉升。
      - Wilson 下界 ≤ demote_lb 且 n≥min_n → 列降級候選（不自動降，留裁決）。
    """
    si_config = config.get("self_iteration", {})
    u_config = config.get("usefulness", {}) or {}
    decay_half_life = si_config.get("decay_half_life_days", 30)
    promote_conf_threshold = si_config.get("promote_confirmations_threshold", 4)
    archive_threshold = si_config.get("archive_score_threshold", 0.3)
    # 效用旋鈕（py↔js 鏡像：server.js）
    decay_lambda = float(u_config.get("decay_lambda", 0.97))
    promote_lb = float(u_config.get("promote_lb", 0.6))
    demote_lb = float(u_config.get("demote_lb", 0.35))
    min_n = int(u_config.get("min_n", 3))
    # demote 側門檻較嚴（n≥5）：67-75% 成功率的 atom 不因小樣本波動列降級候選
    demote_min_n = int(u_config.get("demote_min_n", 5))
    wilson_z = float(u_config.get("wilson_z", 1.28))

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

        # 晉升 = 真實 Confirmations 主軌 OR 效用 Wilson 下界（升≥promote_lb 且 n≥min_n）。
        # ReadHits 降為純曝光，不再參與晉升。
        # py↔js 鏡像：server.js toolAtomPromote usefulness gate。
        util_eligible = bool(
            usefulness_promote_eligible
            and usefulness_promote_eligible(
                acc, promote_lb=promote_lb, min_n=min_n, z=wilson_z)
        )
        promote_method = "confirmations" if confirmations >= promote_conf_threshold else "usefulness"
        # INV-PROMOTION-GATE-ON-SCAN-FACE：未確認 auto-capture 碎片不得自動晉升（與 realm sweep
        # 路徑 _sweep_realm_auto_migrate:1768 同源規則：碎片是未經人確認的 [臨] 萃取，confirmations
        # 達標也不算數，待人工確認/晉升後才算）。斷『佔位符碎片被當穩定 atom 自動晉升』漏洞——
        # 該過濾原僅在 realm sweep，晉升掃描面缺，故碎片曾被算晉升。手動 atom_promote（js）為
        # 人工確認路徑、不受此限。
        if (confirmations >= promote_conf_threshold or util_eligible) \
                and not _autocapture_unconfirmed_from_text(text):
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
                    # 實體路徑：SessionEnd 的自動提交要按檔名清單選擇性 stage，
                    # 只有 stem 無法定位（atom 散在 memory/ 與 _AIDocs/ 多根）。
                    "path": str(md_file),
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

        # 效用 Wilson 下界 ≤ demote_lb 且 n≥demote_min_n、且仍有非[臨]條目 → 降級候選
        # （不自動降，屬敏感裁決；列入 staging 報告供管理職審視）。
        if (usefulness_demote_candidate
                and usefulness_demote_candidate(
                    acc, demote_lb=demote_lb, min_n=demote_min_n, z=wilson_z)
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
                f"\n## 降級候選（效用 Wilson 下界 ≤ {demote_lb}，n≥{demote_min_n}；需裁決）\n")
            for c in results["demote_candidates"]:
                out_lines.append(
                    f"- **{c['atom']}** — lower_bound={c['lower_bound']}, "
                    f"α={c['alpha']}, β={c['beta']}, n={c['n']}"
                )
        (staging / "archive-candidates.md").write_text(
            "\n".join(out_lines), encoding="utf-8"
        )

        # Phase D — selective forgetting（預設 dry-run：只寫候選；enabled+!dry_run 才隔離 _distant/）
        try:
            results["forget"] = apply_selective_forget(
                results["archive_candidates"], config, staging_dir=staging)
        except Exception as e:
            _atom_debug_error("forget:apply", e)

    # 無晉升事件的掃描也要留活性證據，週健檢才能分辨「無事件」與「管線停擺」
    if not results["promoted"]:
        log_promotion_heartbeat(scanned=results["scanned"])

    return results
