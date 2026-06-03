"""atom_locations.py — atom 物理位置與路由的單一規則來源。

設計切分：
  - lib.atom_spec     : what is a valid atom（slugify, is_atom_file, REQUIRED_METADATA...）
  - lib.atom_locations: where atoms physically live + routing decisions（本檔）
  - lib.atom_io       : write funnel（消費上述兩者）

V5+ feedback-* atoms 物理居 `_AIDocs/Failures/`（commit 082f791），索引仍在
`memory/_atom_index.json`。本模組封裝這條規則 + 多 root 掃描 + 白名單常數，
caller 統一走 API；JS 端在 server.js 維護對拍 mirror。

JS mirror：tools/workflow-guardian-mcp/server.js:applyFeedbackRouting
   — Py 改了 JS 也要動，反之亦然。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


# ─── Constants ────────────────────────────────────────────────────────────────

CLAUDE_DIR = Path.home() / ".claude"
GLOBAL_MEMORY_DIR = CLAUDE_DIR / "memory"
FAILURES_DIR = CLAUDE_DIR / "_AIDocs" / "Failures"
FAILURES_REL = "_AIDocs/Failures"
FEEDBACK_TITLE_PREFIX = "feedback-"

# V5+ local realm（範疇限定）：~/.claude 本地知識物理落 _AIDocs/_atoms/<domain>/，
# 索引仍在 memory/_atom_index.json。realm **不存欄位**——由 index path 前綴推導
# （is_local_realm_path）。注入閘門只在 cwd∈~/.claude 時才納入 local（見 session_start）。
# JS mirror：server.js:applyLocalRouting / LOCAL_ATOMS_* 常數 — keep in sync。
LOCAL_ATOMS_DIR = CLAUDE_DIR / "_AIDocs" / "_atoms"
LOCAL_ATOMS_REL = "_AIDocs/_atoms"
LOCAL_REALM_DOMAINS = frozenset({"World", "Tools", "MemDev"})
LOCAL_REALM_DEFAULT_DOMAIN = "Misc"

# wg_core 既有白名單 base（原 wg_core._WHITELIST_DIR_SEGMENTS 主體搬入）
# 注意：含 V4 **按需建立** 目錄（_pending_review=敏感待審路由、personal/_archived/_rejected=
# 專案層 scope 與生命週期）。部分目錄在某些 memory tree 下尚未實體存在，但**不得剪除**——
# 它們在 atom_write 走到對應 scope/路由時才被建立。剪掉會弄壞 V4 專案層寫入與待審。
_BASE_WRITABLE_DIR_SEGMENTS = frozenset({
    "_meta", "_staging", "_archived", "_distant", "_reference", "_pending_review",
    "_vectordb", "_rejected", "templates", "episodic", "wisdom", "personal",
})


# ─── Predicates ───────────────────────────────────────────────────────────────


def is_failures_routed_title(title: Optional[str]) -> bool:
    """title slugify 後檢查 feedback- 前綴。對拍 server.js:applyFeedbackRouting。"""
    if not title:
        return False
    from .atom_spec import slugify  # lazy import: atom_spec 不 import 本模組，避免任何 cycle 風險
    return slugify(title).startswith(FEEDBACK_TITLE_PREFIX)


def is_in_failures_path(rel_path: str) -> bool:
    """rel_path（POSIX 風格）是否落在 _AIDocs/Failures/ 之下。"""
    return rel_path.startswith(FAILURES_REL + "/")


def is_local_realm_path(rel_path: str) -> bool:
    """rel_path（POSIX 風格）是否落在 _AIDocs/_atoms/ 之下 ⇒ local realm（範疇限定）。

    realm 的單一判定來源：path 前綴。與 feedback-* 的 _AIDocs/Failures/ 是不同前綴、零衝突。
    注入閘門（session_start）即用此前綴在外部專案濾掉 local。
    """
    return rel_path.startswith(LOCAL_ATOMS_REL + "/")


# ─── Search / scan（從 atom_spec 搬入，本檔為唯一源） ─────────────────────────


def atom_search_roots(include_failures: bool = True, include_local: bool = True) -> List[Path]:
    """全域 atom 搜尋根目錄（V5+: memory + _AIDocs/Failures/ + _AIDocs/_atoms/）。

    include_local 預設 True：local atom 必須被 self-iterate / audit / index-rebuild 掃到，
    否則無 decay/promote/usefulness 歸屬而凍結。dir 不存在時由 caller（iter_atom_files_multi）
    的 `is_dir()` 守門略過，故空目錄無副作用。
    """
    roots = [GLOBAL_MEMORY_DIR]
    if include_failures:
        roots.append(FAILURES_DIR)
    if include_local:
        roots.append(LOCAL_ATOMS_DIR)
    return roots


def failures_atom_stems(mem_dir: Path = GLOBAL_MEMORY_DIR) -> set:
    """從 _atom_index.json 抽出 path 以 _AIDocs/Failures/ 開頭的 atom stems。

    用於區分 Failures 目錄內「atom」vs「參考文件」（如 _INDEX.md / README.md）。
    例外吞掉回 set()（沿用既有三份 reimplementation 的 graceful fallback）。

    Import dual-safe：本模組可被當 `lib.atom_locations`（相對 import 生效）或
    被 hooks 以 `sys.path.insert(lib)` 後當頂層 `atom_locations` 載入（相對 import
    會 ImportError）。後者是 wg_core guard 的載入方式，故 fallback 絕對 import。
    """
    try:
        from .atom_index_json import load_atom_index_json
    except ImportError:  # 頂層模組載入（wg_core）：無 parent package，退絕對 import
        from atom_index_json import load_atom_index_json
    try:
        data = load_atom_index_json(mem_dir)
        return {
            (a.get("path") or "").rsplit("/", 1)[-1].removesuffix(".md")
            for a in data.get("atoms", [])
            if (a.get("path") or "").startswith(FAILURES_REL + "/")
        }
    except (OSError, ValueError):
        return set()


def iter_atom_files_multi(
    roots: Optional[Iterable[Path]] = None,
    *,
    apply_failures_filter: bool = True,
) -> Iterable[Path]:
    """yield 多 root 下合法 atom .md。

    判定統一走 atom_spec.is_atom_file（避免三份手刻 filter 分歧）。
    若 root == FAILURES_DIR 且 apply_failures_filter=True，
    額外用 failures_atom_stems() 過濾 Failures 內的參考文件。

    Args:
        roots: 自訂搜尋根；None → 用 atom_search_roots() 預設
        apply_failures_filter: 對 FAILURES_DIR root 是否套 stems 過濾
    """
    from .atom_spec import is_atom_file
    roots_list = list(roots) if roots is not None else atom_search_roots()
    stems_cache: Optional[set] = None
    try:
        failures_resolved = FAILURES_DIR.resolve()
    except OSError:
        failures_resolved = FAILURES_DIR
    for root in roots_list:
        if not root.is_dir():
            continue
        try:
            root_resolved = root.resolve()
        except OSError:
            root_resolved = root
        is_failures_root = (root_resolved == failures_resolved)
        if is_failures_root and apply_failures_filter and stems_cache is None:
            stems_cache = failures_atom_stems()
        for md in sorted(root.rglob("*.md")):
            if not is_atom_file(md, root):
                continue
            if is_failures_root and apply_failures_filter and md.stem not in (stems_cache or set()):
                continue
            yield md


# ─── Resolution ───────────────────────────────────────────────────────────────


def failures_write_target() -> Dict[str, Any]:
    """V5+ feedback 路由：失敗 atom 物理落 _AIDocs/Failures/，索引仍在 memory/_atom_index.json。

    回 {dir, base, index_dir, index_root} — caller 自行疊加 scope_label / error / routed_* 旗標。
    副作用：FAILURES_DIR.mkdir(parents=True, exist_ok=True)（對拍既有 atom_io 行為）。
    """
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "dir": FAILURES_DIR,
        "base": FAILURES_DIR,
        "index_dir": GLOBAL_MEMORY_DIR,
        "index_root": CLAUDE_DIR,
    }


def local_write_target(domain: Optional[str] = None) -> Dict[str, Any]:
    """V5+ local-realm 路由：本地範疇 atom 物理落 _AIDocs/_atoms/<domain>/，
    索引仍在 memory/_atom_index.json（index_root=CLAUDE_DIR → rel_path 以 _AIDocs/_atoms/ 開頭）。

    domain 未知 → warn 不擋（避免白名單變摩擦）；空 → LOCAL_REALM_DEFAULT_DOMAIN。
    回 {dir, base, index_dir, index_root} — caller 自行疊加 scope_label / routed_* 旗標。
    MIRROR: server.js:applyLocalRouting — keep in sync。
    """
    dom = (domain or "").strip() or LOCAL_REALM_DEFAULT_DOMAIN
    if dom not in LOCAL_REALM_DOMAINS:
        print(f"[atom_locations] warn: unknown local domain {dom!r} "
              f"(known: {sorted(LOCAL_REALM_DOMAINS)})", file=sys.stderr)
    target = LOCAL_ATOMS_DIR / dom
    target.mkdir(parents=True, exist_ok=True)
    return {
        "dir": target,
        "base": target,
        "index_dir": GLOBAL_MEMORY_DIR,
        "index_root": CLAUDE_DIR,
    }


# ─── Whitelist（從 wg_core 搬入；含 dormant Failures entry） ──────────────────


def atom_writable_dir_segments() -> frozenset:
    """wg_core._atom_path_whitelisted 用的 dir segments（funnel guard 的白名單豁免）。

    **不得**含 'Failures'。`_AIDocs/Failures/` 下的 atom 現由 wg_core
    `_is_failures_atom_path()`（以 failures_atom_stems() 精準比對 index）主動 funnel
    gate 攔截 —— 若把 'Failures' 放進本白名單，未來一旦有人把 caller 的 intersect
    改 case-insensitive，整個 Failures 目錄會被豁免、反而廢掉該 guard（覆蓋缺口復發）。
    Failures 內的 _INDEX.md / legacy 參考文件由「stem 不在 index」與 '_' 前綴自然放行，
    不靠本白名單。
    """
    return _BASE_WRITABLE_DIR_SEGMENTS


# ─── Index rendering classifier ───────────────────────────────────────────────


def atom_index_row_kind(rel_path: str, name: str) -> str:
    """sync-memory-index 分類器。回 'feedback_aggregate' | 'failures_other' | 'individual'。

    保留 sync-memory-index 原語意：name 以 'feedback' 開頭（含可能的 feedbacky-x）
    且 path 在 Failures 下 → 聚合行；其他 Failures 內 atom → 獨立行；
    其餘 → 一般行。
    """
    if name.startswith("feedback") and is_in_failures_path(rel_path):
        return "feedback_aggregate"
    if is_in_failures_path(rel_path):
        return "failures_other"
    return "individual"
