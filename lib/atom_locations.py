"""atom_locations.py — atom 物理位置與路由的單一規則來源。

設計切分：
  - lib.atom_spec     : what is a valid atom（slugify, is_atom_file, REQUIRED_METADATA...）
  - lib.atom_locations: where atoms physically live + routing decisions（本檔）
  - lib.atom_io       : write funnel（消費上述兩者）

V5+ feedback-* atoms 物理居 `_AIDocs/Failures/`，索引仍在
`memory/_atom_index.json`。本模組封裝這條規則 + 多 root 掃描 + 白名單常數，
caller 統一走 API；JS 端在 server.js 維護對拍 mirror。

JS mirror：tools/workflow-guardian-mcp/server.js:applyFeedbackRouting
   — Py 改了 JS 也要動，反之亦然。
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# score_by_lexicon：統一計分核心（lib.atom_classify）。realm 端不再手刻累分骨架，
# 與 project taxonomy 共用單一計分來源（INV-LOGIC-SINGLE-PY-SOURCE）。決策語意
# （無命中=留 core / sorted-domain tiebreak / 段字元集 guard）仍由本檔的 RealmStrategy 詮釋。
# dual-safe import：容 `lib.atom_locations`（相對）與 wg_core sys.path.insert 後頂層
# `atom_locations`（絕對）兩種載入路徑；atom_classify 為 leaf（不 import 本模組）→ 無 cycle。
try:
    from .atom_classify import score_by_lexicon
except ImportError:  # 頂層模組載入（wg_core / CLI sys.path.insert）
    from atom_classify import score_by_lexicon


# ─── Constants ────────────────────────────────────────────────────────────────

CLAUDE_DIR = Path.home() / ".claude"
GLOBAL_MEMORY_DIR = CLAUDE_DIR / "memory"
CORE_ATOMS_REL = "memory"
# 失敗家族（feedback-* / cognitive-patterns / memory-pipeline-*）是核心層的一個 Lv1 範疇
# 資料夾：memory/Failures/<主題>/。舊址 _AIDocs/Failures/ 僅供讀端相容（遷移期間兩處都認），
# 寫端一律落新址。JS mirror：realm.js FAILURES_* / LEGACY_FAILURES_*。
FAILURES_ROOT_NAME = "Failures"
FAILURES_DIR = GLOBAL_MEMORY_DIR / FAILURES_ROOT_NAME
FAILURES_REL = f"{CORE_ATOMS_REL}/{FAILURES_ROOT_NAME}"
LEGACY_FAILURES_DIR = CLAUDE_DIR / "_AIDocs" / "Failures"
LEGACY_FAILURES_REL = "_AIDocs/Failures"
FAILURES_RELS = (FAILURES_REL, LEGACY_FAILURES_REL)
FEEDBACK_TITLE_PREFIX = "feedback-"

# V5+ local realm（範疇限定）：~/.claude 本地知識物理落 _AIDocs/_atoms/<domain>/，
# 索引仍在 memory/_atom_index.json。realm **不存欄位**——由 index path 前綴推導
# （is_local_realm_path）。注入閘門只在 cwd∈~/.claude 時才納入 local（見 session_start）。
# JS mirror：server.js:applyLocalRouting / LOCAL_ATOMS_* 常數 — keep in sync。
LOCAL_ATOMS_DIR = CLAUDE_DIR / "_AIDocs" / "_atoms"
LOCAL_ATOMS_REL = "_AIDocs/_atoms"
# Lv1 已知根（canon 種子 + js mirror parity，test_14）；非 allow-list（深層 free-form）。
LOCAL_REALM_DOMAINS = frozenset({"World", "Tools", "MemDev"})
# catch-all / fail-safe domain（取代舊 "Misc"；LLM 低信心·unsure 歸此，py+js 鏡像 test_14）。
LOCAL_REALM_DEFAULT_DOMAIN = "Else"
# 跨專案注入的 local 範疇（解開「儲存位置綁死注入範圍」）：storage 仍在 _atoms（write 路由不變），
# 但 injection 全專案。注入閘門（session_start）對清單內 Lv1 根的 local atom 例外放行。
# **僅影響注入範圍**，不改 realm/path/write 路由/catalog 歸類。py-only（注入是 Python hook，
# 無 js 對拍面）。目前清單為空：跨專案通用的知識一律住 memory/<範疇>/（core），local 只留
# 「只在 ~/.claude 有用」的；機制保留供未來需要時填入 Lv1 根名。
CROSS_PROJECT_LOCAL_DOMAINS: frozenset = frozenset()
# 階層 domain 路徑最大深度（user 拍板：深=內容多需細分、非範疇廣；
# 擴大根因＝「窄範疇但已知內容量龐大」→ 必須加層）。canon 超此→截尾（絕對天花板）。
LOCAL_REALM_MAX_DEPTH = 7
# 新分支起始封頂：全新（無既有 atom）的路徑最多這麼深；之後只能比「既有已積 atom 的最深
# 匹配前綴」深 1 層 → 深度**隨內容量增長**而非被 LLM 一次灌深（deterministic 落實 depth=volume）。
LOCAL_REALM_NEW_BRANCH_DEPTH = 3
# 詞庫自學檔（py-only supplement；js 維持 base-only 以保 classify_realm parity / test_17）。
LEARNED_LEXICON_PATH = GLOBAL_MEMORY_DIR / "_meta" / "realm-lexicon-learned.json"
# 核心層範疇分類器（classify_category）的自學詞庫 {term: "<Lv1>[/<Lv2>]"}；base 詞庫在 taxonomy.json terms。
TAXONOMY_LEARNED_PATH = GLOBAL_MEMORY_DIR / "_meta" / "taxonomy-lexicon-learned.json"

# ─── Local-realm 分類器詞庫（單一來源：memory/_meta/realm-lexicon.json）────────
#
# 詞庫/核心保護清單/權重由 realm-lexicon.json 供給，py（本檔）與 js
# （tools/workflow-guardian-mcp/lib/realm.js）兩端讀同一份——取代舊「兩份手抄
# 常數 + MIRROR 註解」模式（同 forbidden-phrases.json 先例）。演算法仍雙實作
# 鏡像（classifyRealm，parity test_17）；資料不再手抄。
#
# 收詞守則（改 JSON 前必讀；防誤殺核心；計畫「分類器」節 + 必驗 #1）：
#   1. 核心保護清單「硬擋」——名稱命中即強制 core，永不判 local（先於詞庫）。
#      反覆被 sweep/LLM 誤搬的 core atom 列 exact 集根治（protected 永不喚 LLM、永不搬）。
#   2. 詞庫只用「實例專屬名」（綁定特定 app/工具/環境的詞）；**絕不用記憶系統通用詞**
#      （server.js/wg_/hook/atom_/記憶系統…）——核心 atom 本身充滿這些詞，會誤殺。
#   3. 只掃 name + triggers（高訊號低雜訊）；不掃知識內文（核心 atom 可能以這些實例
#      當例子提及，掃內文擴大誤判面）。
#   4. 安全預設 core：詞庫無命中 → core；僅命中實例詞才判 local。
#   5. 絕不靠 _AIDocs/ 路徑前綴判 local——feedback-* 就在 _AIDocs/Failures/ 卻是 core。
REALM_LEXICON_PATH = GLOBAL_MEMORY_DIR / "_meta" / "realm-lexicon.json"

# fallback 內建最小保護清單（JSON 缺失/損毀時仍硬擋最關鍵核心名；詞庫停用 → 全判 core）
_FALLBACK_CORE_PROTECTED_PREFIXES = (
    "decisions", "workflow-", "toolchain", "feedback-", "memory-pipeline-", "atom-",
)
_FALLBACK_CORE_PROTECTED_EXACT = frozenset({"preferences", "cognitive-patterns"})


def _load_realm_lexicon():
    """讀 realm-lexicon.json → (prefixes, exact, lexicon, name_w, trig_w)。模組載入時執行一次（快取）。

    fail-open：缺失/損毀/缺鍵 → 內建最小保護清單 + 空詞庫（安全預設 core，分類不阻斷）
    ＋ stderr 浮訊號（可觀測性鐵律：降級不阻斷但要告知）。
    """
    try:
        data = json.loads(REALM_LEXICON_PATH.read_text(encoding="utf-8"))
        prefixes = tuple(str(p) for p in data["core_protected_prefixes"])
        exact = frozenset(str(n) for n in data["core_protected_exact"])
        lexicon = {str(k): str(v) for k, v in data["lexicon"].items()}
        name_w, trig_w = int(data["name_weight"]), int(data["trigger_weight"])
        if not (prefixes and exact and lexicon):
            raise ValueError("empty section")
        return prefixes, exact, lexicon, name_w, trig_w
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print(
            f"[atom_locations] realm-lexicon.json unavailable ({e!r}); "
            "fallback to built-in minimal core-protected list; lexicon disabled (all->core)",
            file=sys.stderr,
        )
        return _FALLBACK_CORE_PROTECTED_PREFIXES, _FALLBACK_CORE_PROTECTED_EXACT, {}, 10, 1


(LOCAL_REALM_CORE_PROTECTED_PREFIXES,
 LOCAL_REALM_CORE_PROTECTED_EXACT,
 LOCAL_REALM_LEXICON,
 # name 命中權重 > trigger 命中權重（domain 消歧用；見 classify_realm）
 LOCAL_REALM_NAME_WEIGHT,
 LOCAL_REALM_TRIGGER_WEIGHT) = _load_realm_lexicon()

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
    """title 是否該路由到 _AIDocs/Failures/。對拍 server.js:applyFeedbackRouting。

    兩類：(1) feedback- 前綴（create 起即路由）；(2) 已註冊在索引、path 落
    Failures 的非 feedback- atom（cognitive-patterns 等）——缺 (2) 時這些 atom 的
    append/replace 會在 memory/ 找不到檔而失敗。

    顯式守衛：index path 已在 local 範疇（_AIDocs/_atoms/）的 feedback- atom
    （開發面 post-mortem 住 MemDev）→ False，不回搬——append/replace 在 local 樹找檔。
    """
    if not title:
        return False
    # lazy import: atom_spec 不 import 本模組，避免任何 cycle 風險（dual-safe 同 line 211）
    try:
        from .atom_spec import slugify
    except ImportError:  # 頂層模組載入（wg_core / CLI sys.path.insert）
        from atom_spec import slugify
    slug = slugify(title)
    if slug.startswith(FEEDBACK_TITLE_PREFIX):
        return not _indexed_in_local_realm(slug)
    try:
        return slug in failures_atom_stems()
    except Exception:
        return False


def _indexed_in_local_realm(slug: str, mem_dir: Optional[Path] = None) -> bool:
    """slug 已註冊在 index 且 path 落 _AIDocs/_atoms/ ⇒ True。index 缺/壞/未註冊 → False。"""
    try:
        from .atom_index_json import load_atom_index_json
    except ImportError:
        from atom_index_json import load_atom_index_json
    try:
        data = load_atom_index_json(mem_dir or GLOBAL_MEMORY_DIR)
    except (OSError, ValueError):
        return False
    for a in data.get("atoms", []):
        if a.get("name") == slug:
            return is_local_realm_path(a.get("path") or "")
    return False


def is_in_failures_path(rel_path: str) -> bool:
    """rel_path（POSIX 風格）是否屬失敗家族：memory/Failures/ 之下，或舊址 _AIDocs/Failures/。"""
    return any(rel_path.startswith(r + "/") for r in FAILURES_RELS)


def is_legacy_failures_path(rel_path: str) -> bool:
    """rel_path 仍在舊址 _AIDocs/Failures/（尚未遷入 memory/Failures/）。"""
    return rel_path.startswith(LEGACY_FAILURES_REL + "/")


def is_local_realm_path(rel_path: str) -> bool:
    """rel_path（POSIX 風格）是否落在 _AIDocs/_atoms/ 之下 ⇒ local realm（範疇限定）。

    realm 的單一判定來源：path 前綴。與 feedback-* 的 _AIDocs/Failures/ 是不同前綴、零衝突。
    注入閘門（session_start）即用此前綴在外部專案濾掉 local。
    """
    return rel_path.startswith(LOCAL_ATOMS_REL + "/")


def is_core_protected_name(name: str) -> bool:
    """name 命中核心保護清單（EXACT 或 PREFIXES）⇒ 核心 atom：永不判 local、跨 realm 不歸業務夾。

    **單一來源**——classify_realm 的核心保護硬擋與「跨 realm 逃逸閘」（INV-CROSS-REALM-ESCAPE-HATCH）
    共用本判定，杜絕兩處各自維護保護清單而漂移。逃逸閘語意：專案分類遇此回 True ⇒ 該 atom 是
    逃進專案的核心跨專案規則（decisions/workflow-/toolchain/feedback-/memory-pipeline-/atom- 前綴，
    或 EXACT 名單），應送人工 /refile 而非歸專案業務夾。MIRROR: server.js:classifyRealm 保護硬擋。
    """
    nm = (name or "").strip().lower()
    return nm in LOCAL_REALM_CORE_PROTECTED_EXACT or nm.startswith(LOCAL_REALM_CORE_PROTECTED_PREFIXES)


def classify_realm(name: str, triggers: Optional[Iterable[str]] = None,
                   extra_lexicon: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """新 atom / drift sweep 的 realm 分類器（安全預設 core，僅高信心判 local）。

    回 {"realm": "core"|"local", "domain": str|None, "matched": [str], "protected": bool}：
      - protected=True：名稱命中核心保護清單（永不 local）。
      - realm="local" 時 domain 為命中分數最高的範疇（name 命中權重 > trigger）。

    `extra_lexicon`（py-only 自學詞庫 {term: domain_path}）：**None 時行為與 base 完全相同**
    （js 對拍面 / test_17 永遠跑 base→不破）；SessionEnd sweep 才注入 learned 補 recall。
    learned 值可為多段路徑（domain 因而可能是 "OS/Windows/WSL"）。
    只掃 name + triggers（不掃知識內文）。MIRROR: server.js:classifyRealm（僅 base 部分）。
    """
    # 1) 核心保護硬擋（先於詞庫）：退用單源 is_core_protected_name，與跨 realm 逃逸閘共用、不漂移
    if is_core_protected_name(name):
        return {"realm": "core", "domain": None, "matched": [], "protected": True}
    # 2) 實例詞庫掃描（base ＋ 可選 learned）→ 委派統一計分核心 score_by_lexicon
    #    （name 權重 > trigger 的累分骨架不再手刻；INV-LOGIC-SINGLE-PY-SOURCE）。
    #    決策語意（無命中=留 core / sorted-domain tiebreak / 段 guard）仍為 RealmStrategy；
    #    js classifyRealm 維持手寫 mirror（INV-...-JS-MIRROR，parity test_17）。
    lexicon = LOCAL_REALM_LEXICON if not extra_lexicon else {**LOCAL_REALM_LEXICON, **extra_lexicon}
    scores, matched_by = score_by_lexicon(
        name, triggers, lexicon.items(),
        name_w=LOCAL_REALM_NAME_WEIGHT, trig_w=LOCAL_REALM_TRIGGER_WEIGHT)
    if not scores:
        return {"realm": "core", "domain": None, "matched": [], "protected": False}
    # 平手 → 依 sorted(命中 domain) 固定序首位（base 子集與 js 對拍同序；亦容多段 learned domain）
    best_dom = max(sorted(scores), key=lambda d: scores[d])
    # Domain 段字元集 guard（base lexicon 恆過；learned 可能已被污染，如韓文等
    # 跨文字系統亂碼）：任一段非法 → 降 fail-safe Else。MIRROR: server.js:classifyRealm。
    if any(not _clean_segment(s) for s in best_dom.split("/") if s.strip()):
        best_dom = LOCAL_REALM_DEFAULT_DOMAIN
    # matched 攤平回扁平去重排序集（test_17 比 matched）
    matched = sorted({t for terms in matched_by.values() for t in terms})
    return {
        "realm": "local", "domain": best_dom,
        "matched": matched, "protected": False,
    }


# ─── Search / scan（從 atom_spec 搬入，本檔為唯一源） ─────────────────────────


def atom_search_roots(include_failures: bool = True, include_local: bool = True) -> List[Path]:
    """全域 atom 搜尋根目錄（V5+: memory + _AIDocs/Failures/ + _AIDocs/_atoms/）。

    include_local 預設 True：local atom 必須被 self-iterate / audit / index-rebuild 掃到，
    否則無 decay/promote/usefulness 歸屬而凍結。dir 不存在時由 caller（iter_atom_files_multi）
    的 `is_dir()` 守門略過，故空目錄無副作用。
    """
    roots = [GLOBAL_MEMORY_DIR]  # memory/Failures/ 在 memory/ 樹下，rglob 自然涵蓋
    if include_failures:
        roots.append(LEGACY_FAILURES_DIR)  # 舊址讀端相容；不存在時由 caller is_dir() 略過
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
            if is_in_failures_path(a.get("path") or "")
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
    try:
        from .atom_spec import is_atom_file
    except ImportError:  # 頂層模組載入（wg_core / CLI sys.path.insert）
        from atom_spec import is_atom_file
    roots_list = list(roots) if roots is not None else atom_search_roots()
    stems_cache: Optional[set] = None
    failures_resolved = set()
    for fd in (FAILURES_DIR, LEGACY_FAILURES_DIR):
        try:
            failures_resolved.add(fd.resolve())
        except OSError:
            failures_resolved.add(fd)
    for root in roots_list:
        if not root.is_dir():
            continue
        try:
            root_resolved = root.resolve()
        except OSError:
            root_resolved = root
        is_failures_root = (root_resolved in failures_resolved)
        if is_failures_root and apply_failures_filter and stems_cache is None:
            stems_cache = failures_atom_stems()
        for md in sorted(root.rglob("*.md")):
            if not is_atom_file(md, root):
                continue
            if is_failures_root and apply_failures_filter and md.stem not in (stems_cache or set()):
                continue
            yield md


# ─── Resolution ───────────────────────────────────────────────────────────────


def failures_write_target(topic: Optional[str] = None) -> Dict[str, Any]:
    """失敗家族路由：物理落 memory/Failures/[<主題>/]，索引在 memory/_atom_index.json。

    `topic`＝主題範疇（與核心 Lv1 同名，如「驗證與實證」）；經 validate_category_path 沙盒化，
    非法/空 → 落 Failures 根（寫入閘啟用後由 caller 要求必填）。
    回 {dir, base, index_dir, index_root} — caller 自行疊加 scope_label / error / routed_* 旗標。
    MIRROR: realm.js applyFeedbackRouting — keep in sync。
    """
    target = FAILURES_DIR
    segs, _err = validate_category_path(topic or "")
    if segs:
        target = FAILURES_DIR.joinpath(*segs)
    target.mkdir(parents=True, exist_ok=True)
    return {
        "dir": target,
        "base": target,
        "index_dir": GLOBAL_MEMORY_DIR,
        "index_root": CLAUDE_DIR,
    }


def local_write_target(domain: Optional[str] = None) -> Dict[str, Any]:
    """V5+ local-realm 路由：本地範疇 atom 物理落 _AIDocs/_atoms/<domain_path>/，
    索引仍在 memory/_atom_index.json（index_root=CLAUDE_DIR → rel_path 以 _AIDocs/_atoms/ 開頭）。

    domain 支援**多段階層路徑**（如 "OS/Windows/WSL"，mkdir-p 全鏈）；空/全非法 →
    LOCAL_REALM_DEFAULT_DOMAIN。每段過 `_clean_segment`（拒 `..`/分隔符/`_`前綴等），
    防寫到樹外（path traversal）。回 {dir, base, index_dir, index_root}。
    MIRROR: server.js:applyLocalRouting — keep in sync。
    """
    dom = (domain or "").strip() or LOCAL_REALM_DEFAULT_DOMAIN
    safe = [_clean_segment(s) for s in dom.split("/") if s.strip()]
    safe = [s for s in safe if s][:LOCAL_REALM_MAX_DEPTH]
    if not safe:  # 全非法/空 → fail-safe 落 catch-all，永不寫到樹外
        safe = [LOCAL_REALM_DEFAULT_DOMAIN]
    target = LOCAL_ATOMS_DIR.joinpath(*safe)
    target.mkdir(parents=True, exist_ok=True)
    return {
        "dir": target,
        "base": target,
        "index_dir": GLOBAL_MEMORY_DIR,
        "index_root": CLAUDE_DIR,
    }


def project_subdir_target(base: Path, subdir: str) -> tuple:
    """scope=shared + subdir 的 create 落點：`<memory root>/<subdir>/`（相對 base，多段斜線）。

    支援「一 repo 多專案分區」佈局（memory/projects/<專案名>/）一次寫到位。
    逐段 _clean_segment 沙盒化（拒 `..`/分隔符/`_`前綴/非法字元），再拒
    _LOCATE_SKIP_DIRS 保護段（personal/roles/episodic…）——subdir 不得寫進
    受保護子樹。回 (target_dir|None, error|None)；合法時 mkdir-p。
    MIRROR: atom-tools.js resolveSubdirTarget — keep in sync。
    """
    raw_segs = [s for s in (subdir or "").replace("\\", "/").split("/") if s.strip()]
    if not raw_segs:
        return (None, "subdir is empty")
    segs = []
    for raw in raw_segs:
        seg = _clean_segment(raw)
        if not seg:
            return (None, f"subdir segment invalid: {raw!r}")
        if seg in _LOCATE_SKIP_DIRS:
            return (None, f"subdir segment protected: {seg!r}")
        segs.append(seg)
    target = Path(base).joinpath(*segs)
    target.mkdir(parents=True, exist_ok=True)
    return (target, None)


# ─── Locate existing atom（append/replace 的實體檔定位） ─────────────────────

# 定位時不得下探的目錄：草稿牢籠（_drafts/auto-capture、personal/auto/<user>）、封存、
# 非 atom 子族（episodic/templates/wisdom…）。這些不是 curated atom，不該成為
# append/replace 的目標。SYNC: server.js findAtomFileRecursive 的 SKIP 集合。
_LOCATE_SKIP_DIRS = frozenset({
    "_meta", "_reference", "_staging", "_vectordb", "_distant",
    "episodic", "templates", "personal", "roles", "wisdom", "_pending_review",
    "_drafts",
})


def _is_under(child: Path, roots: List[Path]) -> bool:
    """child 落在任一 root 內，且相對路徑不含 skip 段/_archive* 段。

    段層級防護：search_roots 放寬到整個 memory root 後（shared atom 可被歸位到
    projects/<X>/ 等兄弟子夾），跨 scope 保護改由「路徑段」把關——personal/roles/
    草稿/封存子樹內的檔即使被索引指到也不當定位目標。
    """
    try:
        c = child.resolve()
    except OSError:
        c = child
    for r in roots:
        try:
            rel = c.relative_to(r)
        except ValueError:
            continue
        segs = rel.parts[:-1]  # 目錄段（去檔名）
        if any(s in _LOCATE_SKIP_DIRS or s.startswith("_archive") for s in segs):
            return False
        return True
    return False


def _rglob_locate(root: Path, slug: str) -> List[Path]:
    """BFS root 找 <slug>.md，跳過 _LOCATE_SKIP_DIRS / _archive* 子樹。"""
    hits: List[Path] = []
    target = f"{slug}.md"
    queue = [root]
    while queue:
        cur = queue.pop(0)
        try:
            entries = sorted(cur.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_dir():
                if e.name in _LOCATE_SKIP_DIRS or e.name.startswith("_archive"):
                    continue
                queue.append(e)
            elif e.name == target:
                hits.append(e)
    return hits


def find_separator_variant(search_roots: Iterable[Path], slug: str) -> Optional[str]:
    """既有檔名 slugify 後與 slug 相同、但字面不同（舊底線檔 client_il.md vs 新 slug
    client-il）→ 回該檔相對 root 的 posix 路徑，否則 None。create 前守門：不擋會叉出
    append/replace 永遠碰不到的近重複 atom。跳過 `_`/`.` 前綴目錄。"""
    try:
        from .atom_spec import slugify as _slugify
    except ImportError:  # 頂層模組載入
        from atom_spec import slugify as _slugify  # type: ignore
    for root in search_roots:
        try:
            if not root.is_dir():
                continue
        except OSError:
            continue
        queue = [root]
        while queue:
            cur = queue.pop(0)
            try:
                entries = sorted(cur.iterdir())
            except OSError:
                continue
            for e in entries:
                if e.is_dir():
                    if e.name.startswith("_") or e.name.startswith("."):
                        continue
                    queue.append(e)
                elif e.suffix == ".md":
                    base = e.stem
                    if base != slug and _slugify(base) == slug:
                        try:
                            return e.relative_to(root).as_posix()
                        except ValueError:
                            return e.as_posix()
    return None


def locate_existing_atom(
    slug: str,
    *,
    index_dir: Path,
    index_root: Path,
    search_roots: Iterable[Path],
) -> tuple:
    """定位既有 atom 的實體檔（append/replace 用）。回 (path|None, error|None)。

    為何需要：atom 的**寫入預設落點是扁平的**（scope=shared → `memory/shared/`），
    但實體檔常被事後歸位到主題子夾（專案 classifier sweep → `shared/<Domain>/`；
    local realm → `_AIDocs/_atoms/<domain 多段>/`）。只看預設落點會誤判 not-found。

    定位順序（抄 tools/atom-move.py:locate_md 的既有正解）：
      1. `_atom_index.json` 的 path 欄位（權威，含子夾）——需檔案存在且落在 search_roots
         之內（跨 scope 保護：scope=shared 不得改到 personal 的檔）。
      2. 落空 → 逐一 rglob search_roots。

    撞名（多個 root/子夾各有同 slug .md 且索引無條目）→ 回 error 明確報出所有候選，
    **不靜默取第一個**。找不到 → (None, None)，由 caller 給既有 not-found 訊息。
    """
    roots: List[Path] = []
    for r in search_roots:
        try:
            if r.is_dir():
                roots.append(r.resolve())
        except OSError:
            continue
    if not roots:
        return (None, None)

    # 1) index path 優先
    try:
        from .atom_index_json import load_atom_index_json
    except ImportError:  # 頂層模組載入（wg_core / CLI sys.path.insert）
        from atom_index_json import load_atom_index_json
    try:
        for a in load_atom_index_json(index_dir).get("atoms", []):
            if a.get("name") != slug or not a.get("path"):
                continue
            p = Path(index_root) / a["path"]
            if p.exists() and _is_under(p, roots):
                return (p, None)
            break
    except (OSError, ValueError):
        pass

    # 2) rglob fallback
    hits: List[Path] = []
    seen = set()
    for r in roots:
        for h in _rglob_locate(r, slug):
            key = str(h.resolve()).lower() if sys.platform == "win32" else str(h.resolve())
            if key not in seen:
                seen.add(key)
                hits.append(h)
    if len(hits) > 1:
        return (None,
                f"Ambiguous atom {slug}.md — {len(hits)} files match and "
                f"_atom_index.json has no entry to disambiguate: "
                + ", ".join(str(h) for h in hits)
                + ". Merge or rename the duplicates first.")
    return (hits[0] if hits else None, None)


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
    """sync-memory-index 分類器。回 'feedback_aggregate' | 'failures_other' | 'local_realm' | 'individual'。

    保留 sync-memory-index 原語意：name 以 'feedback' 開頭（含可能的 feedbacky-x）
    且 path 在 Failures 下 → 聚合行；其他 Failures 內 atom → 獨立行；
    V5+ realm：path 落 _AIDocs/_atoms/ → 'local_realm'（本地範疇，render 收進獨立段，
    保留 R4 印象層指標、避免人在 ~/.claude 找不到被歸走的 atom）；其餘 → 一般行。
    Failures 與 _atoms 是不同前綴、互斥，分支順序不影響結果。
    """
    if name.startswith("feedback") and is_in_failures_path(rel_path):
        return "feedback_aggregate"
    if is_in_failures_path(rel_path):
        return "failures_other"
    if is_local_realm_path(rel_path):
        return "local_realm"
    return "individual"


def local_realm_domain(rel_path: str) -> str:
    """從 _AIDocs/_atoms/<domain>/<slug>.md 抽出 <domain>；非 local 路徑回 ''。

    缺 domain 段（理論上不應發生，路由一律帶 domain 子夾）→ LOCAL_REALM_DEFAULT_DOMAIN。
    供 sync-memory-index 把 local atom 依範疇分組渲染用。
    """
    if not is_local_realm_path(rel_path):
        return ""
    rest = rel_path[len(LOCAL_ATOMS_REL) + 1:]
    head, _, tail = rest.partition("/")
    return head if (head and tail) else LOCAL_REALM_DEFAULT_DOMAIN


def local_realm_path_segments(rel_path: str) -> List[str]:
    """_AIDocs/_atoms/<a>/<b>/.../<slug>.md → ['a','b',...]（去尾檔名）；非 local → []。

    扁平 'Tools/slug.md' → ['Tools']；多段 'OS/Windows/WSL/slug.md' → ['OS','Windows','WSL']。
    供階層 catalog 建樹 / Lv1 抽取 / existing_paths 枚舉。
    """
    if not is_local_realm_path(rel_path):
        return []
    rest = rel_path[len(LOCAL_ATOMS_REL) + 1:]
    parts = [p for p in rest.split("/") if p]
    return parts[:-1]  # 去檔名（最後一段）


def local_realm_lv1_root(rel_path: str) -> str:
    """抽 Lv1 根（最廣範疇，always-load catalog 用）；缺 → LOCAL_REALM_DEFAULT_DOMAIN。"""
    segs = local_realm_path_segments(rel_path)
    return segs[0] if segs else LOCAL_REALM_DEFAULT_DOMAIN


def is_cross_project_local(rel_path: str) -> bool:
    """local-realm atom 但 Lv1 根 ∈ CROSS_PROJECT_LOCAL_DOMAINS ⇒ 外部專案仍注入。

    解開「儲存位置（_atoms）綁死注入範圍（僅 ~/.claude）」：清單內範疇 storage 在 _atoms、
    injection 全專案（如 Continuity），對偶 feedback-*。非 local 路徑一律 False。
    """
    if not is_local_realm_path(rel_path):
        return False
    return local_realm_lv1_root(rel_path) in CROSS_PROJECT_LOCAL_DOMAINS


def enumerate_local_paths(mem_dir: Path = GLOBAL_MEMORY_DIR) -> List[str]:
    """從 index 抽所有 local atom 的去重 domain 路徑（多段 join，如 'OS/Windows/WSL'）。

    供 LLM canon 種子（既有路徑清單）與 normalize_domain_path 的 snap 來源。
    例外吞掉回 []（沿用本模組 graceful fallback 慣例）。
    """
    try:
        from .atom_index_json import load_atom_index_json
    except ImportError:  # 頂層模組載入（wg_core / CLI sys.path.insert）
        from atom_index_json import load_atom_index_json
    try:
        data = load_atom_index_json(mem_dir)
    except (OSError, ValueError):
        return []
    paths = set()
    for a in data.get("atoms", []):
        rp = a.get("path") or ""
        if is_local_realm_path(rp):
            segs = local_realm_path_segments(rp)
            if segs:
                paths.add("/".join(segs))
    return sorted(paths)


# ─── 核心層範疇資料夾（memory/<範疇>/…；分類由 index path 推導，與 local realm 同原理）────
#
# 兩根：memory/（core，全專案注入；含 Failures 家族 Lv1）與 _AIDocs/_atoms/（local，僅 ~/.claude）。
# realm 仍由 _AIDocs/_atoms/ 前綴推導（is_local_realm_path 不動）；範疇＝path 在根之後的目錄段。
REALM_ROOTS = ((CORE_ATOMS_REL, "core"), (LOCAL_ATOMS_REL, "local"))


def realm_root_for(rel_path: str) -> Optional[str]:
    """rel_path 所屬的根（'memory' / '_AIDocs/_atoms'）；舊址 _AIDocs/Failures 視為 core 根；皆非 → None。"""
    for root, _realm in REALM_ROOTS:
        if rel_path.startswith(root + "/"):
            return root
    if is_legacy_failures_path(rel_path):
        return LEGACY_FAILURES_REL
    return None


def path_segments_under(rel_path: str, root_rel: str) -> List[str]:
    """<root>/<a>/<b>/<slug>.md → ['a','b']（去檔名）；不在 root 下 → []。"""
    prefix = root_rel + "/"
    if not rel_path.startswith(prefix):
        return []
    parts = [p for p in rel_path[len(prefix):].split("/") if p]
    return parts[:-1]


def core_category_segments(rel_path: str) -> List[str]:
    """核心層範疇段：memory/<Lv1>/<Lv2>/<slug>.md → ['Lv1','Lv2']；根下散檔 → []。

    舊址 _AIDocs/Failures/<slug>.md 視為 ['Failures']（遷移期間 catalog 計數一致）。
    """
    if is_legacy_failures_path(rel_path):
        return [FAILURES_ROOT_NAME] + path_segments_under(rel_path, LEGACY_FAILURES_REL)
    return path_segments_under(rel_path, CORE_ATOMS_REL)


def is_flat_core_path(rel_path: str) -> bool:
    """memory/<slug>.md（根下散檔、無範疇資料夾）⇒ True。範疇資料夾必備的硬規則就看這個。"""
    return rel_path.startswith(CORE_ATOMS_REL + "/") and not core_category_segments(rel_path)


# 範疇資料夾禁用名（casefold）：撞 atom 掃描 skip 名單、定位 skip、funnel 白名單段、dashboard 層名、
# 舊址小寫 failures。命中即拒——否則 atom 會被掃描器跳過或整樹被 funnel 豁免。
# `Failures`（正名大寫）由 taxonomy 明列放行（validate_category_segment 的 allow 參數）。
def _category_reserved_segments() -> frozenset:
    try:
        from .atom_spec import SKIP_DIRS
    except ImportError:  # 頂層模組載入
        from atom_spec import SKIP_DIRS
    extra = {"shared", "roles", "projects", "unity", "memory", "failures"}
    return frozenset(s.lower() for s in (set(SKIP_DIRS) | _LOCATE_SKIP_DIRS | _BASE_WRITABLE_DIR_SEGMENTS | extra))


CATEGORY_RESERVED_SEGMENTS = _category_reserved_segments()


def validate_category_segment(seg: str, allow: Iterable[str] = ()) -> str:
    """單段範疇名驗證：_clean_segment 沙盒 + 保留名拒絕（casefold）+ `_archive*` 拒。合法回正規化段，否則 ''。"""
    s = _clean_segment(seg)
    if not s:
        return ""
    low = s.lower()
    if low.startswith("_archive"):
        return ""
    if low in CATEGORY_RESERVED_SEGMENTS and s not in set(allow):
        return ""
    return s


def validate_category_path(path: str, max_depth: int = LOCAL_REALM_MAX_DEPTH,
                           allow_first: Iterable[str] = (FAILURES_ROOT_NAME,)) -> tuple:
    """範疇路徑 'Lv1[/Lv2…]' → (segs, error)。任一段非法 → ([], error)。空 → ([], None)。"""
    raw = [s for s in (path or "").replace("\\", "/").split("/") if s.strip()]
    if not raw:
        return ([], None)
    segs: List[str] = []
    for i, r in enumerate(raw[:max_depth]):
        seg = validate_category_segment(r, allow=allow_first if i == 0 else ())
        if not seg:
            return ([], f"category segment invalid or reserved: {r!r}")
        segs.append(seg)
    return (segs, None)


def iter_realm_category_dirs(root: Path) -> List[Path]:
    """root 直屬的範疇資料夾（名稱通過 validate_category_segment；`_`/skip 名單目錄剪掉）。"""
    out: List[Path] = []
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return out
    for e in entries:
        if e.is_dir() and validate_category_segment(e.name, allow=(FAILURES_ROOT_NAME,)):
            out.append(e)
    return out


def enumerate_category_paths(mem_dir: Path = GLOBAL_MEMORY_DIR) -> List[str]:
    """從 index 抽核心層所有去重範疇路徑（'版控/Git' 等；含 'Failures/<主題>'）。例外回 []。"""
    try:
        from .atom_index_json import load_atom_index_json
    except ImportError:
        from atom_index_json import load_atom_index_json
    try:
        data = load_atom_index_json(mem_dir)
    except (OSError, ValueError):
        return []
    paths = set()
    for a in data.get("atoms", []):
        segs = core_category_segments(a.get("path") or "")
        if segs:
            paths.add("/".join(segs))
    return sorted(paths)


def known_category_paths(mem_dir: Path = GLOBAL_MEMORY_DIR) -> List[str]:
    """Lv2 snap 的兄弟來源：index 既有範疇路徑 ∪ taxonomy 宣告的 sub（'版控/Git' 等）。

    宣告過的 Lv2 就算目前還沒有 atom 住進去，也要能把輸入 'vcs/git' snap 成 '版控/Git'
    （Windows 不分大小寫：同名異案的資料夾會撞在一起、index path 卻分岔）。
    """
    paths = set(enumerate_category_paths(mem_dir))
    try:
        from .atom_taxonomy import load_taxonomy
    except ImportError:
        from atom_taxonomy import load_taxonomy
    try:
        core = load_taxonomy()["core"]
    except Exception:
        return sorted(paths)
    for name, info in core.items():
        for sub in (info or {}).get("sub") or []:
            if sub:
                paths.add(f"{name}/{sub}")
    return sorted(paths)


def unclassified_error(raw: Optional[str], categories: Iterable[str], layer: str = "core") -> str:
    """寫入閘拒寫訊息的單一出口：列出全部合法 Lv1、別名提示、新類旗標。"""
    cats = ", ".join(categories)
    return (
        f"unclassified {layer} atom rejected: domain={raw!r} (missing or unknown). "
        f"Valid Lv1: {cats}. Aliases/EN slugs accepted (e.g. vcs→版控); Lv2 free (e.g. 版控/Git). "
        "To create a new Lv1 pass allow_new_category=true."
    )


def core_write_target(domain: Optional[str], allow_new: bool = False,
                      existing_paths: Optional[Iterable[str]] = None) -> tuple:
    """核心層 create 落點：memory/<Lv1>[/<Lv2>]/。回 (target_dict|None, error|None)。

    Lv1 必須在 taxonomy 閉合清單（正名／slug／別名皆可，snap 回正名）；未知 Lv1 → 拒，
    除非 allow_new=True（仍須通過保留名／字元集）。Lv2 自由，對既有同深度兄弟 snap
    （normalize_domain_path）。`Failures` 走 failures_write_target，不由此函式處理。
    不做 mkdir 以外的副作用；不猜、不落 Else。
    """
    try:
        from .atom_taxonomy import core_categories, match_lv1, TaxonomyUnavailable
    except ImportError:
        from atom_taxonomy import core_categories, match_lv1, TaxonomyUnavailable
    try:
        cats = core_categories()
    except TaxonomyUnavailable as e:
        return (None, f"taxonomy.json unavailable: {e}")
    raw = (domain or "").strip().replace("\\", "/")
    if not raw:
        return (None, unclassified_error(domain, cats))
    head, _, rest = raw.partition("/")
    if head.casefold() == FAILURES_ROOT_NAME.casefold():
        return (None, "use failures routing (feedback- title / topic) for the Failures family")
    lv1 = match_lv1(head)
    if lv1 is None:
        if not allow_new:
            return (None, unclassified_error(domain, cats))
        lv1 = validate_category_segment(head)
        if not lv1:
            return (None, f"new category name invalid or reserved: {head!r}")
    existing = list(existing_paths) if existing_paths is not None else known_category_paths()
    full = lv1 if not rest else f"{lv1}/{rest}"
    canon = normalize_domain_path(full, existing)
    segs, err = validate_category_path(canon, allow_first=())
    if err or not segs or segs[0] != lv1:
        return (None, err or f"category path invalid: {canon!r}")
    target = GLOBAL_MEMORY_DIR.joinpath(*segs)
    target.mkdir(parents=True, exist_ok=True)
    return ({
        "dir": target, "base": target,
        "index_dir": GLOBAL_MEMORY_DIR, "index_root": CLAUDE_DIR,
        "category": "/".join(segs),
    }, None)


def failures_topic_target(domain: Optional[str], allow_new: bool = False) -> tuple:
    """失敗家族 create 落點：memory/Failures/<主題>[/<Lv2>]/。回 (target_dict|None, error|None)。

    `domain` 可為 "驗證與實證"、"verify"（別名 snap）或 "Failures/驗證與實證"（前導 Failures 段
    自動剝掉）。主題必須在 taxonomy Lv1 閉合清單（failures.topics="same-as-core"）；未知主題
    → 拒，除非 allow_new（仍過保留名／字元集）。空 → 拒（寫入閘：feedback- 標題 domain 必填）。
    """
    try:
        from .atom_taxonomy import failures_topics, match_lv1, TaxonomyUnavailable
    except ImportError:
        from atom_taxonomy import failures_topics, match_lv1, TaxonomyUnavailable
    try:
        topics = failures_topics()
    except TaxonomyUnavailable as e:
        return (None, f"taxonomy.json unavailable: {e}")
    raw = (domain or "").strip().replace("\\", "/").strip("/")
    head, _, rest = raw.partition("/")
    if head.casefold() == FAILURES_ROOT_NAME.casefold():
        raw = rest
        head, _, rest = raw.partition("/")
    if not head:
        return (None, unclassified_error(domain, topics, layer="failures"))
    topic = match_lv1(head, topics)
    if topic is None:
        if not allow_new:
            return (None, unclassified_error(domain, topics, layer="failures"))
        topic = validate_category_segment(head)
        if not topic:
            return (None, f"new failures topic invalid or reserved: {head!r}")
    full = topic if not rest else f"{topic}/{rest}"
    segs, err = validate_category_path(full, allow_first=())
    if err or not segs:
        return (None, err or f"failures topic path invalid: {full!r}")
    t = failures_write_target("/".join(segs))
    t["category"] = f"{FAILURES_ROOT_NAME}/" + "/".join(segs)
    return (t, None)


def project_taxonomy_lv1(base: Path) -> List[str]:
    """專案層 Lv1 擴充：<base>/shared/_taxonomy.json 的 domains 鍵（缺/壞 → []）。

    這是專案自訂範疇的**唯一**資料面入口（與 `taxonomy_term_pairs` 同一檔）。
    `project_hooks.py` delegate（`action="taxonomy"`）刻意不接：每次 create 熱路徑多一次
    5s 逾時的子程序、且目前無專案使用；真有需求的專案再開，不為想像需求長枝葉。
    """
    try:
        data = json.loads((base / "shared" / "_taxonomy.json").read_text(encoding="utf-8-sig"))
        domains = data.get("domains") or {}
        return [str(k) for k in domains.keys() if str(k).strip()] if isinstance(domains, dict) else []
    except (OSError, ValueError, AttributeError):
        return []


def project_category_target(base: Path, domain: Optional[str], allow_new: bool = False,
                            root_dir: Optional[Path] = None) -> tuple:
    """專案層 create 落點：<root_dir or base/shared>/<Lv1>[/<Lv2>]/。回 (target_dict|None, error|None)。

    Lv1 閉合清單＝核心 taxonomy Lv1（正名／slug／別名 snap）∪ 專案 `shared/_taxonomy.json`
    domains 鍵（專案自訂 Lv1，casefold 比對）。未知 → 拒，除非 allow_new。Lv2 自由，對
    root_dir 下既有兄弟資料夾 snap。`root_dir` 給了（subdir 分區）→ 範疇落在該分區之下。
    """
    try:
        from .atom_taxonomy import core_categories, match_lv1, TaxonomyUnavailable
    except ImportError:
        from atom_taxonomy import core_categories, match_lv1, TaxonomyUnavailable
    try:
        cats = core_categories()
    except TaxonomyUnavailable as e:
        return (None, f"taxonomy.json unavailable: {e}")
    extra = project_taxonomy_lv1(base)
    all_cats = cats + [x for x in extra if x not in cats]
    raw = (domain or "").strip().replace("\\", "/").strip("/")
    if not raw:
        return (None, unclassified_error(domain, all_cats, layer="shared"))
    head, _, rest = raw.partition("/")
    lv1 = match_lv1(head, cats)
    if lv1 is None:
        for x in extra:
            if x.casefold() == head.casefold():
                lv1 = x
                break
    if lv1 is None:
        if not allow_new:
            return (None, unclassified_error(domain, all_cats, layer="shared"))
        lv1 = validate_category_segment(head)
        if not lv1:
            return (None, f"new category name invalid or reserved: {head!r}")
    root = root_dir if root_dir is not None else (base / "shared")
    # Lv2 snap 的兄弟來源：分區根下既有範疇資料夾 ∪ taxonomy 宣告的 sub（Windows 不分大小寫：
    # 'vcs/git' 沒 snap 成 '版控/Git' 會落小寫資料夾、index path 分岔）。
    existing = [
        "/".join(p.relative_to(root).parts)
        for d in iter_realm_category_dirs(root)
        for p in [d, *[c for c in iter_realm_category_dirs(d)]]
    ] if root.is_dir() else []
    try:
        from .atom_taxonomy import load_taxonomy
    except ImportError:
        from atom_taxonomy import load_taxonomy
    for name, info in load_taxonomy()["core"].items():
        existing.extend(f"{name}/{sub}" for sub in ((info or {}).get("sub") or []) if sub)
    full = lv1 if not rest else f"{lv1}/{rest}"
    canon = normalize_domain_path(full, existing)
    segs, err = validate_category_path(canon, allow_first=())
    if err or not segs or segs[0].casefold() != lv1.casefold():
        return (None, err or f"category path invalid: {canon!r}")
    segs[0] = lv1
    target = root.joinpath(*segs)
    target.mkdir(parents=True, exist_ok=True)
    return ({
        "dir": target, "base": base,
        "index_dir": base, "index_root": base.parent,
        "category": "/".join(segs),
    }, None)


# ─── 階層 domain 路徑：segment 正規化 + canonicalization（OPEN 2）──────────────
#
# 防 free-form 樹分歧（OS/Win vs OS/Windows）：主防線是 LLM 拿既有路徑清單優先複用；
# 本層為次防線——逐段對「同深度既有兄弟段」snap（大小寫無視 ∨ 前綴包含 ∨ difflib）。

_SEG_SNAP_RATIO = 0.85
_SEG_PREFIX_MIN = 3
_SEG_UNSAFE_CHARS = set('<>:"|?*')
# Domain 段允許字元集：ASCII 可印字元 + CJK 統一表意文字（含 Ext-A）。
# LLM 生成的 domain 視為不可信輸入：跨文字系統字元（如 Hangul「자동화」、
# 西里爾 homoglyph…）穿透 snap 防線造成重複亂碼資料夾 → 整段判非法、降 fail-safe。
# MIRROR: server.js:cleanRealmSegment — keep in sync（parity test_22）。
_SEG_ALLOWED_RE = re.compile(r"^[\x20-\x7e㐀-䶿一-鿿]+$")


def _clean_segment(seg: str) -> str:
    """單段正規化：trim + collapse 內部空白。非法 → ''（caller 截斷/退 fail-safe）。

    拒：空、含路徑分隔（/ \\）、`_`/`.` 前綴（避免 _INDEX/_meta 衝突、隱藏檔、`..` 上跳）、
    檔名不安全字元、非 CJK/ASCII 字元（_SEG_ALLOWED_RE，防跨文字系統亂碼 domain）。
    **path traversal 的最後防線**（local_write_target / set_realm 共用）。
    """
    s = " ".join((seg or "").split()).strip()
    if not s or "/" in s or "\\" in s:
        return ""
    if s[0] in "_.":
        return ""
    if any(c in _SEG_UNSAFE_CHARS for c in s):
        return ""
    if not _SEG_ALLOWED_RE.match(s):
        return ""
    return s


def _snap_segment(seg: str, siblings: Dict[str, str]) -> str:
    """把 seg snap 到同深度既有兄弟段 canonical。siblings: {lower: canonical}。

    規則序：大小寫無視精確 → 前綴包含(雙向, len≥3，治 'Win'↔'Windows') → difflib≥0.85；
    皆不中 → 回 seg（新層）。
    """
    low = seg.lower()
    if low in siblings:
        return siblings[low]
    for cl, canon in siblings.items():
        if len(low) >= _SEG_PREFIX_MIN and len(cl) >= _SEG_PREFIX_MIN and \
                (low.startswith(cl) or cl.startswith(low)):
            return canon
    best, best_ratio = None, 0.0
    for cl, canon in siblings.items():
        r = difflib.SequenceMatcher(None, low, cl).ratio()
        if r > best_ratio:
            best, best_ratio = canon, r
    return best if (best is not None and best_ratio >= _SEG_SNAP_RATIO) else seg


def _build_children_map(existing_paths: Iterable[str]) -> Dict[str, Dict[str, str]]:
    """existing_paths（多段 domain）→ {parent_lower: {child_lower: canonical}}（逐層兄弟表）。"""
    children: Dict[str, Dict[str, str]] = {}
    for ep in existing_paths or []:
        parent = ""
        for s in (x for x in (ep or "").split("/") if x):
            children.setdefault(parent.lower(), {}).setdefault(s.lower(), s)
            parent = f"{parent}/{s}" if parent else s
    return children


def normalize_domain_path(path: str, existing_paths: Optional[Iterable[str]] = None) -> str:
    """LLM 回的 domain 路徑 → canonical（OPEN 2 雙層 canon 的次防線）。

    逐段 _clean_segment → _snap_segment（對同深度既有兄弟）；遇非法段即截斷；
    超 LOCAL_REALM_MAX_DEPTH 截尾；全空/全非法 → LOCAL_REALM_DEFAULT_DOMAIN。
    """
    children = _build_children_map(existing_paths or [])
    out: List[str] = []
    parent = ""
    for raw in (path or "").split("/"):
        seg = _clean_segment(raw)
        if not seg:
            break  # 截斷於第一個非法段（保前綴可用部分）
        canon = _snap_segment(seg, children.get(parent.lower(), {}))
        out.append(canon)
        parent = f"{parent}/{canon}" if parent else canon
        if len(out) >= LOCAL_REALM_MAX_DEPTH:
            break
    # 增量深度閘（depth=volume，user 拍板）：新分支封頂 LOCAL_REALM_NEW_BRANCH_DEPTH；
    # 只能比「既有已積 atom 的最深匹配前綴」深 1 層 → 深度隨內容量長，不被 LLM 一次灌深。
    if out:
        prefixes = set()
        for ep in (existing_paths or []):
            segs = [s for s in (ep or "").split("/") if s]
            for i in range(1, len(segs) + 1):
                prefixes.add("/".join(segs[:i]).lower())
        prefix_depth = 0
        for i in range(len(out), 0, -1):
            if "/".join(out[:i]).lower() in prefixes:
                prefix_depth = i
                break
        out = out[:max(LOCAL_REALM_NEW_BRANCH_DEPTH, prefix_depth + 1)]
    return "/".join(out) if out else LOCAL_REALM_DEFAULT_DOMAIN


# ─── 詞庫自學（py-only supplement；js 維持 base-only 保 parity / test_17）──────

# 泛用詞 token 黑名單（sink 端防線，蓋所有 append_learned_terms caller）：
# 泛用詞污染案例：LLM sweep 曾把「寫程式 / refactor / fix bug / verify」等泛用詞學進
# 詞庫，core atom goal-driven-verify-loop 因 trigger 命中被誤降 local。
# 上游 realm_llm_classify._GENERIC_TERMS 只擋系統詞，擋不住開發泛用動詞 → 此處補閘。
# 判定：term 以空白/連字號切 token，**全部** token 落在本集合 → 拒收
# （"fix bug"/"verify loop" 拒；"auto-handoff"/"verify-gate-x" 因含非泛用 token 收）。
_LEXICON_GENERIC_TOKENS = frozenset({
    # 英文開發泛用動詞/名詞
    "fix", "bug", "bugs", "fixbug", "bugfix", "debug", "debugging",
    "refactor", "refactoring", "rewrite", "verify", "verification", "validate",
    "test", "tests", "testing", "loop", "code", "coding", "program", "programming",
    "develop", "development", "dev", "build", "run", "deploy", "deployment",
    "commit", "push", "pull", "merge", "review", "release", "patch",
    "install", "setup", "config", "configuration", "update", "upgrade",
    "error", "errors", "fail", "failure", "plan", "planning", "task", "todo",
    "doc", "docs", "document", "documentation", "workflow", "pipeline",
    "git", "svn", "ci", "cd", "api", "cli", "log", "logs", "file", "files",
    # 記憶系統/harness 通用詞（核心 atom 滿是這些詞）
    "atom", "atoms", "memory", "hook", "hooks", "mcp", "agent", "agents",
    "session", "prompt", "token", "tokens", "index", "trigger", "triggers",
    "guardian", "sweep", "realm", "scope", "inject", "injection",
    # context-engineering / memory-governance 概念詞（通用學術/業界術語，非 ~/.claude 實例詞；
    # governance atom 曾被 sweep 學進 "context rot"/"context engineering"/
    # "selective forgetting"/"context poisoning" → 污染未來同詞 atom。這些是概念維度、絕非分類詞）
    "context", "contexts", "rot", "poison", "poisoning", "distraction", "distract",
    "distractor", "confusion", "clash", "engineering", "governance", "forget",
    "forgetting", "selective", "relevance", "relevant", "extract", "extraction",
    "retrieval", "recall", "rerank", "salience", "anchoring", "drift", "gating",
    "gate", "minimal", "signal", "rag", "embedding", "semantic",
    "萃取", "上下文", "汙染", "污染", "分心", "遺忘", "腐化", "上下文工程",
    # 中文開發泛用詞
    "寫程式", "程式", "程式碼", "重構", "除錯", "修bug", "測試", "驗證",
    "部署", "設定", "開發", "完成", "收尾", "同步", "索引", "文件",
    "記憶", "記憶系統", "工作流", "規劃", "升級", "安裝", "錯誤", "上git",
    "可驗證目標", "成功標準", "驗證目標",  # 泛用目標詞（曾致 goal-driven 誤降）
    # 品質完整性判定 atom 被誤降時學進詞庫的概念詞：品質/驗證/紀錄/取樣類
    # 概念維度詞，非實例專屬——命中會把任何提及它們的 atom 誤拉進 MemDev（詞庫自我強化污染）。
    "excerpt", "post", "mortem", "截斷", "品質判定", "源根驗證", "取樣", "採樣",
})
_LEXICON_TOKEN_SPLIT_RE = re.compile(r"[\s\-_/]+")

# 保留標籤 / realm 自名 / 已知外部專案 token：learned 詞庫**絕不收**（exact-match 拒收）。
# 外部專案知識與系統自身 trigger 標籤 "auto-capture" 曾雙雙被學進
# 詞庫，drift sweep 據此把外部專案 core atom 搬進根層 _atoms/、把碎片塞進名為 "auto-capture"
# 的葉夾（trigger 標籤被當分類維度）。三類絕不該成為實例分類詞：
#   - 系統 trigger 標籤（auto-capture/auto-captured/觸發詞）：extract-worker 預設標籤，非實例詞。
#   - realm 自名（memdev/world/tools/continuity）：分類『維度』本身，不該回頭當分類『詞』。
#   - 已知外部專案（sgi/uba…）：其知識屬專案層、非 ~/.claude-local；**新外部專案在此擴充**。
# 主防線是 SessionEnd sweep 對 auto-captured 碎片整體 defer（wg_atoms._is_unconfirmed_autocapture，
# 斷『學詞』來源）；本集合為 sink 端 belt-and-suspenders，蓋非 auto-capture 途徑寫入的詞。
_RESERVED_LEXICON_TERMS = frozenset({
    "auto-capture", "auto-captured", "觸發詞",
    "memdev", "world", "tools", "continuity",
    "sgi", "uba",
})


def is_generic_lexicon_term(term: str) -> bool:
    """term 是否泛用詞 / 保留標籤（不具實例辨識度）→ 詞庫拒收。空字串視為泛用。"""
    tl = (term or "").strip().lower()
    if tl in _RESERVED_LEXICON_TERMS:
        return True  # 保留標籤 / realm 自名 / 已知外部專案：絕不收
    tokens = [t for t in _LEXICON_TOKEN_SPLIT_RE.split(tl) if t]
    return not tokens or all(t in _LEXICON_GENERIC_TOKENS for t in tokens)


def load_learned_lexicon(path: Optional[Path] = None) -> Dict[str, str]:
    """讀自學詞庫 {term_lower: domain_path}。缺/壞 → {}（fail-safe，永不拋）。
    `path` 預設 realm 自學檔；傳 TAXONOMY_LEARNED_PATH 讀核心層範疇自學檔。"""
    try:
        data = json.loads((path or LEARNED_LEXICON_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    terms = data.get("terms", {}) if isinstance(data, dict) else {}
    return {str(k).strip().lower(): str(v).strip()
            for k, v in terms.items() if str(k).strip() and str(v).strip()}


def append_learned_terms(new_terms: Dict[str, str],
                         path: Optional[Path] = None) -> Dict[str, str]:
    """併 {term: domain_path} 入 learned.json（atomic temp+rename + 去重）。回合併後全集。

    LLM sweep 判 local 後寫入 → 下次 deterministic 直接命中、免再喚 LLM。
    讀-改-寫全程持 advisory lock（仿 wg_core.write_state）：兩個 session 同時
    SessionEnd 時防 lost-update（學到的詞被互蓋永久遺失）。

    輸入護欄（詞庫污染防線，sink 端蓋所有 caller）：
      - 泛用詞拒收（is_generic_lexicon_term）——防 core atom 被泛用 trigger 誤降 local
      - domain path 任一段非法（含非 CJK/ASCII 字元，_clean_segment）→ 整條拒收
        ——防亂碼 domain 經詞庫自我強化

    `path` 預設 realm 自學檔；核心層範疇分類器的自學檔（TAXONOMY_LEARNED_PATH）
    共用同一把鎖／同一套護欄（值＝"<Lv1>[/<Lv2>]"，同樣逐段 _clean_segment）。
    """
    learned_path = path or LEARNED_LEXICON_PATH
    learned_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = learned_path.with_suffix(".lock")
    lock_fh = None
    if sys.platform == "win32":
        try:
            import msvcrt
            lock_fh = open(lock_path, "ab")
            msvcrt.locking(lock_fh.fileno(), msvcrt.LK_LOCK, 1)
        except OSError:
            if lock_fh:
                lock_fh.close()
            lock_fh = None
    try:
        merged = load_learned_lexicon(learned_path)
        for k, v in (new_terms or {}).items():
            kk, vv = str(k).strip().lower(), str(v).strip()
            if not kk or not vv:
                continue
            if is_generic_lexicon_term(kk):
                continue  # 泛用詞拒收
            if any(not _clean_segment(s) for s in vv.split("/") if s.strip()):
                continue  # domain 段非法（亂碼/traversal）拒收
            merged[kk] = vv
        tmp = learned_path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({"terms": merged}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(learned_path)
        return merged
    finally:
        if lock_fh is not None:
            try:
                import msvcrt
                msvcrt.locking(lock_fh.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            lock_fh.close()
            try:
                lock_path.unlink()
            except OSError:
                pass


# ─── 核心層範疇自動分類器（程式寫手用；MCP 來源永不走這條——AI 必給 domain）────────
#
# 四態：lex（詞庫命中）／llm（本地 LLM 閉合清單命中）→ caller 用 category 落地；
# unsure／error → caller **拒寫**（core 不設 Else；error 另標，可延後重試）。
# 詞庫＝taxonomy.json 各 Lv1 terms ∪ TAXONOMY_LEARNED_PATH（LLM 命中後回寫的實例詞）。
# LLM 由 config `taxonomy.llm_fallback{enabled,max_per_session,min_confidence}` 管：
# 預設關；開了也 per-process 計數封頂（hook 一次 process ≈ 一次 session）。

_LLM_CATEGORY_CALLS = 0


def taxonomy_llm_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """taxonomy.llm_fallback 段（config 未給則讀 workflow/config.json；缺 → 關）。"""
    cfg = config
    if cfg is None:
        try:
            from .atom_taxonomy import CONFIG_PATH
        except ImportError:
            from atom_taxonomy import CONFIG_PATH
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            cfg = {}
    llm = ((cfg or {}).get("taxonomy") or {}).get("llm_fallback") or {}
    return {
        "enabled": bool(llm.get("enabled", False)),
        "max_per_session": int(llm.get("max_per_session", 5) or 0),
        "min_confidence": float(llm.get("min_confidence", 0.7) or 0.0),
    }


def _lexicon_category(name: str, triggers: Iterable[str], layer: str) -> Dict[str, Any]:
    """詞庫計分：回 {category|None, matched, reason}。Lv1 平手 → None（保守，不猜）。"""
    try:
        from .atom_taxonomy import category_term_pairs, weights, match_lv1, TaxonomyUnavailable
    except ImportError:
        from atom_taxonomy import category_term_pairs, weights, match_lv1, TaxonomyUnavailable
    try:
        pairs = list(category_term_pairs(layer))
        name_w, trig_w = weights()
    except TaxonomyUnavailable as e:
        return {"category": None, "matched": [], "reason": f"taxonomy unavailable: {e}", "error": True}
    for term, cat in load_learned_lexicon(TAXONOMY_LEARNED_PATH).items():
        lv1 = match_lv1(cat.split("/", 1)[0])
        if lv1 is None:
            continue  # learned 指向已不存在的 Lv1 → 忽略（taxonomy 是單一真相）
        rest = cat.partition("/")[2]
        pairs.append((term, f"{lv1}/{rest}" if rest else lv1))
    scores, matched = score_by_lexicon(name, list(triggers or []), pairs,
                                       name_w=name_w, trig_w=trig_w)
    if not scores:
        return {"category": None, "matched": [], "reason": "lexicon miss"}
    lv1_scores: Dict[str, int] = {}
    for bucket, sc in scores.items():
        lv1 = bucket.split("/", 1)[0]
        lv1_scores[lv1] = lv1_scores.get(lv1, 0) + sc
    ranked = sorted(lv1_scores.items(), key=lambda kv: -kv[1])
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return {"category": None, "matched": [],
                "reason": f"lexicon tie: {ranked[0][0]}={ranked[0][1]} vs {ranked[1][0]}={ranked[1][1]}"}
    best_lv1 = ranked[0][0]
    # 同 Lv1 內取最高分 bucket（learned 可能指到 Lv2）；平手取較深者（實例詞比 Lv1 泛詞更具體）
    inner = sorted(((b, s) for b, s in scores.items() if b.split("/", 1)[0] == best_lv1),
                   key=lambda kv: (-kv[1], -kv[0].count("/")))
    best = inner[0][0]
    hits = sorted({t for b, ts in matched.items() if b.split("/", 1)[0] == best_lv1 for t in ts})
    return {"category": best, "matched": hits, "reason": f"lexicon hit: {', '.join(hits)}"}


def _default_llm_category_classifier():
    """lazy 取 tools/realm_llm_classify.llm_classify_category（tools 反依賴 lib，故不在模組頂層 import）。
    取不到 → None（caller 視同 LLM 不可用 → error 態）。"""
    for p in (CLAUDE_DIR / "tools", CLAUDE_DIR):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    try:
        from realm_llm_classify import llm_classify_category  # type: ignore
        return llm_classify_category
    except Exception as e:  # noqa: BLE001 — 任何載入失敗都只降級
        print(f"[classify_category] llm classifier unavailable: {e!r}", file=sys.stderr)
        return None


def classify_category(name: str, triggers: Optional[Iterable[str]] = None, layer: str = "core",
                      *, excerpt: str = "", config: Optional[Dict[str, Any]] = None,
                      llm=None) -> Dict[str, Any]:
    """程式寫手的範疇自動分類：詞庫 → 本地 LLM（閉合清單）→ 四態。

    回 {status: lex|llm|unsure|error, category: "<Lv1>[/<Lv2>]"|None, matched: [...],
        confidence: float, reason: str}。layer="failures" 時 category＝主題（同核心 Lv1 名）。
    `llm`：注入的分類 callable（測試 stub）；None → lazy 取 tools/realm_llm_classify。
    只掃 name + triggers（高訊號）；excerpt 只餵 LLM。**MCP 來源不得呼叫本函式**（AI 必給）。
    """
    global _LLM_CATEGORY_CALLS
    lex = _lexicon_category(name or "", triggers or [], layer)
    if lex.get("error"):
        return {"status": "error", "category": None, "matched": [], "confidence": 0.0,
                "reason": lex["reason"]}
    if lex["category"]:
        return {"status": "lex", "category": lex["category"], "matched": lex["matched"],
                "confidence": 1.0, "reason": lex["reason"]}
    llm_cfg = taxonomy_llm_config(config)
    if not llm_cfg["enabled"]:
        return {"status": "unsure", "category": None, "matched": [], "confidence": 0.0,
                "reason": f"{lex['reason']}; llm_fallback disabled"}
    if _LLM_CATEGORY_CALLS >= llm_cfg["max_per_session"]:
        return {"status": "unsure", "category": None, "matched": [], "confidence": 0.0,
                "reason": f"{lex['reason']}; llm_fallback max_per_session reached"}
    fn = llm if llm is not None else _default_llm_category_classifier()
    if fn is None:
        return {"status": "error", "category": None, "matched": [], "confidence": 0.0,
                "reason": f"{lex['reason']}; llm classifier unavailable"}
    try:
        from .atom_taxonomy import failures_topics, core_categories, match_lv1
    except ImportError:
        from atom_taxonomy import failures_topics, core_categories, match_lv1
    cats = failures_topics() if layer == "failures" else core_categories()
    _LLM_CATEGORY_CALLS += 1
    try:
        r = fn(name or "", list(triggers or []), excerpt or "", cats, layer=layer) or {}
    except Exception as e:  # noqa: BLE001 — LLM 任何炸法都是 error 態
        r = {"status": "error", "reason": f"llm raised: {e!r}"}
    status = str(r.get("status") or "unsure")
    if status == "error":
        return {"status": "error", "category": None, "matched": [], "confidence": 0.0,
                "reason": f"{lex['reason']}; llm error: {r.get('reason', '')}"}
    cat = match_lv1(str(r.get("category") or ""), cats)
    conf = float(r.get("confidence") or 0.0)
    if status != "hit" or cat is None or conf < llm_cfg["min_confidence"]:
        return {"status": "unsure", "category": None, "matched": [], "confidence": conf,
                "reason": f"{lex['reason']}; llm unsure: {r.get('reason', '')}"}
    terms = [str(t) for t in (r.get("terms") or []) if str(t).strip()]
    if terms:
        try:
            append_learned_terms({t: cat for t in terms}, path=TAXONOMY_LEARNED_PATH)
        except OSError as e:
            print(f"[classify_category] learned lexicon write failed: {e}", file=sys.stderr)
    return {"status": "llm", "category": cat, "matched": terms, "confidence": conf,
            "reason": f"llm hit: {r.get('reason', '')}"}
