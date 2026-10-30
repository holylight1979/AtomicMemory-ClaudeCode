"""
wg_core.py — Workflow Guardian 共用基礎模組（V5）

統合：
- 常數 / 設定載入 / State I/O / Output helpers / Debug logging
- 路徑集中管理（前 wg_paths）
- PreToolUse 路徑/指令防呆（前 wg_pretool_guards）
- MCP server 健檢（前 wg_intent._check_mcp_servers）
- Log rotation
- Promotion audit log
"""

import fnmatch
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple
from wg_lazy_re import lazy_re  # 模組層樣式第一次用到才編譯（HOOK_IMPORT_ON_USE）

# ─── 全域路徑常數 ────────────────────────────────────────────────────────────

# CLAUDE_DIR＝使用者資料根（memory、workflow、config、Logs）：WG_CLAUDE_DIR 可覆蓋，未設＝家目錄 ~/.claude。
# CODE_DIR＝程式碼根（hooks、lib、tools）：一律由本檔位置推，不吃 WG_CLAUDE_DIR、不看家目錄。
CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR / "lib"))
from project_root import claude_config_dir, claude_data_dir  # noqa: E402  資料根的唯一算法（tools 也呼叫它）
from harness_text import HOOK_RESIDUE_LINE_RE, strip_harness_blocks, user_typed_text  # noqa: E402,F401  使用者原話規則唯一一份
from config_local import merge_local  # noqa: E402  config.local.json 蓋到 config.json 的規則唯一一份
CLAUDE_DIR = claude_data_dir()
MEMORY_DIR = CLAUDE_DIR / "memory"
EPISODIC_DIR = MEMORY_DIR / "episodic"
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
CONFIG_PATH = WORKFLOW_DIR / "config.json"
CONFIG_LOCAL_PATH = WORKFLOW_DIR / "config.local.json"   # 這台機器專屬覆寫（不進版控），同名鍵蓋過 config.json
# V5+ Realm 維度：SessionEnd 自動搬移的待提示 marker（永不靜默；session_start 讀+清）
REALM_AUTOMOVE_MARKER = WORKFLOW_DIR / "realm_automove_pending.json"
MEMORY_INDEX = "MEMORY.md"
ATOM_INDEX = "_ATOM_INDEX.md"
REGISTRY_PATH = MEMORY_DIR / "project-registry.json"

# atom 物理位置 / 白名單規則來源（單一來源 lib.atom_locations）
sys.path.insert(0, str(CODE_DIR / "lib"))
try:
    from atom_locations import (
        atom_writable_dir_segments, failures_atom_stems, is_local_realm_path,
        is_cross_project_local, iter_realm_category_dirs, FAILURES_DIR,
    )
except ImportError:
    atom_writable_dir_segments = None
    failures_atom_stems = None
    is_local_realm_path = None
    is_cross_project_local = None
    iter_realm_category_dirs = None
    FAILURES_DIR = CLAUDE_DIR / "memory" / "Failures"
# 專案根判定單一來源（宣告認領 + 舊四標記 fallback）；import 失敗 → 下方 find_project_root 走內建舊規則
try:
    from project_root import (
        resolve_project_root, has_project_marker, DECLARED_KINDS as _ROOT_DECLARED_KINDS,
    )
except ImportError:
    resolve_project_root = None
    has_project_marker = None
    _ROOT_DECLARED_KINDS = ()

# ─── Token budget 單一來源─────────────────────────
# 三個 budget 概念各司其職，數值不互相推導：
#   compute_token_budget(prompt) — 每輪 additionalContext 總額（隨 prompt 長度 1000/2000/3000）
#   CONTEXT_BUDGET_DEFAULT       — _truncate_context_by_activation 的 fallback 上限
#   TURN_BUDGET_LIMIT            — atom 注入段 per-turn 硬頂（wg_atoms re-export 舊名 _TURN_BUDGET_LIMIT）
# token 估算器單一口徑：wg_core._estimate_tokens — CJK-aware（中文 ~1.5 tok/字 + ASCII word），
# transcript/handoff/debug 摘要與 atom 注入預算共用（wg_atoms import 複用）
CONTEXT_BUDGET_DEFAULT = 3000
TURN_BUDGET_LIMIT = 1200  # atom 注入段 per-turn 硬頂（atom 全文中位數 ~360 tok → 約 3 顆全文；總額仍由 compute_token_budget 夾住）


TOKEN_BUDGET_TIERS = ((15, 1000), (80, 2000))  # (prompt 估算 tok 上限, 總額)；超過最後一級 → 3000
TOKEN_BUDGET_MAX = 3000


def compute_token_budget(prompt: str) -> int:
    """每輪注入總額：短 prompt 少注入，長 prompt 多注入。

    分級依 prompt 的估算 token 數（CJK-aware），不依字元數——中文 37 字≈33 tok 是實質
    問題，英文 37 字≈9 tok 只是短句；用字元數分級會把中文問句壓在最低額度。

    注意：此為起始額度；build_context 會逐段扣減（session context 注入輪 −reserved_tokens
    預設 200、JIT 參考注入 −250），故 [Context budget: x/y] 尾行的 y 常見 750（1000−250）
    或 2550（3000−200−250）等扣減後數字，非固定常數。"""
    ptok = _estimate_tokens(prompt or "")
    for cap, budget in TOKEN_BUDGET_TIERS:
        if ptok < cap:
            return budget
    return TOKEN_BUDGET_MAX


# ─── 覆轍信號（same_file_3x）檔名白名單 ─────────────────────────────────────
# 索引/編年/說明/驗收工件本來就每 session 高頻反覆更新（README、_CHANGELOG、
# DocIndex-*、各種 _INDEX、MEMORY.md、acceptance-*），「同檔改 ≥3 次」proxy 對
# 這類檔必然過度警報 → 警報疲勞。命中白名單者不產生 / 不採計 rut 信號。
# 降噪非關警報：各過濾點必落 atom-debug log（可觀測性鐵律）。
# config self_iteration.rut_file_whitelist 覆寫；fnmatch、不分大小寫。
RUT_FILE_WHITELIST_DEFAULT = [
    "readme*", "_changelog*", "docindex-*", "*_index*",
    "memory.md", "_atom_index*", "acceptance-*",
]


def is_rut_whitelisted(filename: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """same_file_3x 覆轍信號的檔名白名單判定（僅比對檔名，不含路徑）。"""
    patterns = ((config or {}).get("self_iteration") or {}).get(
        "rut_file_whitelist", RUT_FILE_WHITELIST_DEFAULT
    )
    name = Path(str(filename)).name.lower()
    return any(fnmatch.fnmatch(name, str(p).lower()) for p in patterns)


# Defaults（可被 config.json 覆寫）
DEFAULTS = {
    "enabled": True,
    "coding_guard": {"enabled": False},    # 寫碼守門總開關（v6_enabled；舊鍵 v6 仍認，見 coding_guard_opt）
    "stop_gate_max_blocks": 2,
    "min_files_to_block": 2,
    "sync_keywords": ["同步", "sync", "commit", "提交", "結束", "收工"],
    "session_context": {
        "enabled": True,
        "max_episodic": 3,
        "reserved_tokens": 200,
        "min_score": 0.35,
        "search_timeout_ms": 1500,
    },
    "aidocs": {
        "enabled": True,
        "max_prompt_matches": 1,      # 每則最多指幾份；min_prompt_hits：關鍵字命中數門檻（1 個命中不算明顯）
        "min_prompt_hits": 2,
    },
    "sync_reminder": {
        "enabled": True,
        "max_reminders": 1,
    },
    "docdrift": {
        "enabled": True,
        "path_mappings": {},
        "exclude_patterns": [
            "_aidocs/", "memory/", "_staging/", ".git/",
            "node_modules/", "__pycache__/", ".claude/workflow/",
        ],
        "keyword_match_threshold": 2,
        "max_pending_display": 5,
    },
    "proactive": {
        "pattern_threshold": 2,
        "migration_hint_threshold": 3,
    },
    "guard": {
        "cross_realm_write": {
            "enabled": True,
            "allowlist": [],
        },
    },
    "entrypoint": {
        "inject_budget_tokens": 400,      # 每個認出的切入點各一份
        "inject_budget_total": 1200,      # 同一則問句所有切入點加起來的上限
    },
    "hook_timing": {                      # wg_hook_timing：分段計時；累計過上限的 degrade_ratio 就降級（後面的段落不跑）
        "enabled": True,
        "degrade_ratio": 0.8,
        "fallback_limit_s": {"SessionStart": 20, "UserPromptSubmit": 8, "PreToolUse": 5,   # settings.json 讀不到 timeout 時用；
                             "PostToolUse": 5, "Stop": 10},                                # 只計這裡列到的事件
    },
}


# ─── Config 載入 ─────────────────────────────────────────────────────────────


def load_config() -> Dict[str, Any]:
    """Load config with defaults fallback。

    config.json 損毀時退 DEFAULTS 但不得靜默（可觀測性鐵律）：log +
    `_config_parse_failed` 旗標，UPS/SessionStart 見旗標注入一行告警。
    """
    config = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config.update(user_config)
        except (json.JSONDecodeError, OSError) as e:
            _atom_debug_error("config:parse_failed", e)
            config["_config_parse_failed"] = True
    return merge_local(config, CONFIG_LOCAL_PATH, "workflow-guardian")


def coding_guard_env() -> Optional[str]:
    """寫碼守門的環境變數開關值："1"開、"0"關、None 沒設。WG_CODING_GUARD 優先，沒設（或不是 0/1）才看舊名 WG_V6。"""
    for name in ("WG_CODING_GUARD", "WG_V6"):
        v = os.environ.get(name, "").strip()
        if v in ("0", "1"):
            return v
    return None


def coding_guard_opt(config: Optional[Dict[str, Any]], key: str, default: Any = None) -> Any:
    """寫碼守門設定的子鍵（coding_turn_only、slim_reminders…）：coding_guard 段有寫這個鍵就用它，沒寫才讀舊鍵 v6 段
    （相容還寫 {"v6": {...}} 的 config.local.json）；兩段都沒寫回 default。段不是物件當沒寫。"""
    for name in ("coding_guard", "v6"):
        sec = (config or {}).get(name)
        if isinstance(sec, dict) and key in sec:
            return sec[key]
    return default


def v6_enabled(config: Dict[str, Any]) -> bool:
    """寫碼守門總開關，預設關：關時 hook 只跑寫碼守門關時也跑的（9e476fd0 就有的）處理。函式名沿用、不改。

    判法（先到先贏）：
    1. 環境變數 WG_CODING_GUARD=1 開、=0 關；沒設才看舊名 WG_V6（同義，coding_guard_env）。
    2. config：coding_guard.enabled 是 JSON true 就開；不是（出廠 false）再看舊鍵 v6.enabled 是 JSON true 也開——
       舊的 workflow/config.local.json 寫 {"v6": {"enabled": true}} 照樣能開，不必改鍵。要強制關用環境變數 =0。
    只認 JSON 的 true：寫成字串 "false"、段不是物件，一律當關。
    """
    env = coding_guard_env()
    if env is not None:
        return env == "1"
    return any(isinstance(config.get(k), dict) and config[k].get("enabled") is True for k in ("coding_guard", "v6"))


# 規則 CODING_TURN_ONLY：寫碼類意圖（wg_atoms.INTENT_PATTERNS 的鍵）；其餘（general、design、recall、handoff）不算。
# 只當提示的開關（第一則「先立樹」一行、讀程式檔附的定位提示），不當守門開關（coding_turn 不看它）
CODE_INTENTS = frozenset({"debug", "feature", "refactor", "perf", "new_project", "build"})
def coding_turn(state: Optional[Dict[str, Any]], config: Optional[Dict[str, Any]] = None) -> bool:
    """規則 CODING_TURN_ONLY：這個使用者回合是不是寫碼回合，三層：
    ① 實質行為（最高位）：這個使用者回合已經有改程式檔的工具行為——Edit／Write／NotebookEdit 或 Bash／PowerShell 寫進程式檔
       （modified_files 有一筆，程式照 wg_code_path.writes_code 判，.bat／.cmd 也算；只改文件不算），或判不出寫入目標的指令
       （unknown_writes，不知道寫了什麼，保守算）。
    ② 改碼之前的入口：本使用者回合 LLM 呼叫了 need_goal set／add／update，而且那棵樹是寫碼類（state need_goal_code_decl_turn）。
       樹只是前幾回合留著、本回合沒宣告不算。
    ③ 使用者 prompt 的關鍵字分類（turn_intent）不當開關：只決定要不要送一行「要改碼先立樹」（wg_need_goal.CODE_TREE_HINT）與記憶選片。
    判錯會漏的：LLM 沒立樹就直接改碼，動手前的守門晚到第一次改程式檔才啟動（由 ① 補上）。
    寫碼守門的每回合守門（目標樹提示、目標視角重看、退避偵測、退縮閘、收尾檢核、文字評分、閱讀路徑）只在寫碼回合啟動；寫碼守門關時也跑的
    處理（記憶注入、導讀卡、收割、vcs-sync、語言守門）照舊每回合跑。config coding_guard.coding_turn_only=false 退回每回合都啟動。"""
    st = state or {}
    if coding_guard_opt(config, "coding_turn_only", True) is False:
        return True
    v = st.get("turn_prompts_seq")
    since = int(v) if isinstance(v, int) and not isinstance(v, bool) and v > 0 else int(st.get("turn_seq", 0) or 0)
    if any(isinstance(u, dict) and int(u.get("turn_seq") or 0) >= since for u in st.get("unknown_writes") or []):
        return True
    d = st.get("need_goal_code_decl_turn")
    if isinstance(d, int) and not isinstance(d, bool) and d >= since:
        return True
    from wg_code_path import writes_code
    return any(isinstance(m, dict) and int(m.get("last_turn_seq") or m.get("turn_seq") or 0) >= since
               and writes_code(str(m.get("path") or ""), config)
               for m in st.get("modified_files") or [])


ORG_LOCAL_NAME = "org-memory.local.json"


def org_local_path() -> Path:
    return WORKFLOW_DIR / ORG_LOCAL_NAME


def load_org_local() -> Dict[str, Any]:
    """這台機器專屬的公司層狀態（workflow/org-memory.local.json，不進版控）。

    鍵：enabled／roots（這台接上沒、根在哪，形狀同 config `org_memory`）、declined（使用者答過「先不接」，
    SessionStart 不再問）。舊鍵 advised 已不讀（曾表示「提示出過一次」，留著無害）。
    沒檔 → {}（未接上，正常狀態）；壞檔 → {} 且 stderr 一行。
    """
    path = org_local_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as e:
        print(f"[org_memory] {path} 讀取失敗，視為未接上：{e}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def save_org_local(**changes: Any) -> None:
    """把 changes 併進本機公司層狀態檔（其他鍵保留）。"""
    data = {**load_org_local(), **changes}
    path = org_local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def org_memory_root() -> Optional[Path]:
    """公司層記憶 repo 根的單一來源：共用 workflow/config.json `org_memory` 被本機狀態檔同名鍵蓋過。

    共用 config 只帶 repo_url／default_root（全公司相同）；「這台接上沒、根在哪」在本機檔（load_org_local）。
    enabled 且 roots 恰 1 個 → Path(roots[0].root)；關閉 → None（正常狀態，不出聲）。
    缺鍵／config 壞／roots 空或 >1 → None 且 stderr 一行（fail-open 必浮訊號）。
    """
    config = load_config()
    if config.get("_config_parse_failed"):
        print("[org_memory] workflow/config.json 解析失敗，已停用 org", file=sys.stderr)
        return None
    org = config.get("org_memory")
    if not isinstance(org, dict):
        print("[org_memory] workflow/config.json 缺 org_memory 鍵，已停用 org", file=sys.stderr)
        return None
    org = {**org, **load_org_local()}
    if not org.get("enabled"):
        return None
    roots = org.get("roots") or []
    if len(roots) > 1:
        print("[org_memory] org_memory.roots 只支援 1 個，已停用 org", file=sys.stderr)
        return None
    root = (roots[0] or {}).get("root") if roots else ""
    if not root:
        print("[org_memory] org_memory.enabled=true 但 roots 為空，已停用 org", file=sys.stderr)
        return None
    return Path(root)


# ─── Utility ─────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _estimate_tokens(text: str) -> int:
    """CJK-aware token estimation. Chinese ~1.5 tok/char, ASCII ~0.25 tok/word."""
    if not text:
        return 0
    cjk = sum(1 for c in text if '一' <= c <= '鿿' or '　' <= c <= '〿')
    ascii_part = len(text) - cjk
    return int(cjk * 1.5 + ascii_part * 0.25)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """以 _estimate_tokens 口徑把 text 截到 ≤ max_tokens（字元邊界二分）。

    取代 `text[:budget*4]` 這類 chars/4 換算切片（CJK 下嚴重超額）。
    """
    if _estimate_tokens(text) <= max_tokens:
        return text
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _estimate_tokens(text[:mid]) <= max_tokens:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo]


# 「使用者本人打的字」的規則（harness 區塊、同伴訊息邊界、系統通知標記行、hook 殘渣行、殘留標籤字樣整則不認）
# 只有一份：lib/harness_text.user_typed_text（頂部 import），這裡的 user_typed_text 就是它。


def is_harness_generated_prompt(text: str) -> bool:
    """整則 prompt 裡沒有使用者打的字（user_typed_text 為空；空訊息也算）。"""
    return not user_typed_text(text)


def user_typed_prompts(prompts: Optional[List[str]]) -> List[str]:
    """近期 prompt 清單逐則取 user_typed_text（清理後的文字），不是使用者的話的那幾則丟掉；豁免詞與口令只認這些。"""
    out: List[str] = []
    for p in prompts or []:
        typed = user_typed_text(p or "")
        if typed:
            out.append(typed)
    return out


def sanitize_harness_noise(text: str) -> str:
    """剔除 harness 標籤區塊與 hook 注入殘渣行，回收使用者/模型的實際文字。

    用途：topic tracker 的 first_prompt_summary / keyword 訊號、episodic 摘要等
    「給人看或給 LLM 吃」的文字源頭。純文字處理、fail-open（異常回原文）。
    """
    if not text:
        return ""
    try:
        cleaned = strip_harness_blocks(text)
        cleaned = HOOK_RESIDUE_LINE_RE.sub(" ", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()
    except Exception:
        return text


def rotate_log_if_oversized(log_path: Path, max_mb: int = 10, keep: int = 3) -> bool:
    """Size-based log rotation. Fail-open.

    Rotates `log_path` to `log_path.1` (.1->.2, .2->.3) when > max_mb.
    Keeps last `keep` rotated copies. Returns True if rotated.
    Handles Windows-locked / corrupt files gracefully (returns False).
    """
    try:
        if not log_path.exists():
            return False
        size_mb = log_path.stat().st_size / (1024 * 1024)
        if size_mb < max_mb:
            return False
        for i in range(keep - 1, 0, -1):
            src = log_path.with_suffix(log_path.suffix + f".{i}")
            dst = log_path.with_suffix(log_path.suffix + f".{i+1}")
            if src.exists():
                try:
                    if dst.exists():
                        dst.unlink()
                    src.rename(dst)
                except OSError:
                    pass
        rotated = log_path.with_suffix(log_path.suffix + ".1")
        try:
            if rotated.exists():
                rotated.unlink()
            log_path.rename(rotated)
            log_path.touch()
            return True
        except OSError as e:
            _atom_debug_error("log_rotation:rename", e)
            return False
    except Exception as e:
        _atom_debug_error("log_rotation", e)
        return False


# ─── Path Helpers (was wg_paths.py) ──────────────────────────────────────────


def cwd_to_project_slug(cwd: str) -> str:
    """Convert CWD to Claude Code project slug. All-lowercase to avoid C: vs c: slug split."""
    slug = cwd.replace(":", "-").replace("\\", "-").replace("/", "-").replace(".", "-")
    return slug.lower()


def _has_project_marker(root: Path) -> bool:
    if has_project_marker is not None:
        return has_project_marker(root)
    return (
        (root / ".claude" / "memory" / MEMORY_INDEX).exists()
        or (root / "_AIDocs").is_dir()
        or (root / ".git").exists() or (root / ".svn").exists()
    )


def find_project_root(cwd: str) -> Optional[Path]:
    """cwd 所屬的專案根（lib/project_root：宣告認領優先，否則最近標記）。找不到回 Path(cwd)。

    無宣告認領時取 `Resolution.nearest`——判定只有 lib/project_root._legacy_nearest 一份，
    這裡不再自己掃一次。兩份各自實作沒有編譯期關聯，改一邊忘了另一邊就會靜默分岔。
    """
    if not cwd:
        return None
    if resolve_project_root is not None:
        res = resolve_project_root(cwd)
        if res.claimed_by in _ROOT_DECLARED_KINDS and res.path:
            return res.path
        return res.nearest or res.path or Path(cwd)
    p = Path(cwd)
    for _ in range(4):
        if _has_project_marker(p):
            return p
        parent = p.parent
        if parent == p:
            break
        p = parent
    return Path(cwd)


def _root_is_declared(cwd: str) -> bool:
    """cwd 的專案根是否來自宣告認領（此時記憶目錄可以尚未存在）。"""
    if resolve_project_root is None:
        return False
    return resolve_project_root(cwd).claimed_by in _ROOT_DECLARED_KINDS


def _is_under_claude_dir(cwd: str) -> bool:
    """cwd 是否在 ~/.claude（含本身）之下 — V5+ local-realm 注入閘門用。

    用 resolved parents 比對（非 startswith），避免 `~/.claude-foo` 之類旁系路徑
    被誤判為內部。對拍 server.js:resolveMemDir 的 isUnderClaudeDir（語意一致；
    JS 端以 startswith+sep 達同效）。resolve 失敗 → False（保守：當外部專案，
    寧可少注入 local 也不誤注入到外部）。
    """
    if not cwd:
        return False
    try:
        c = Path(cwd).resolve()
        cd = CLAUDE_DIR.resolve()
    except (OSError, ValueError):
        return False
    return c == cd or cd in c.parents


# ─── 判層（H9）：只看 cwd 與設定，不讀 transcript、不叫模型 ─────────────────────

class LayerInfo(NamedTuple):
    """kind ∈ {root, org, project_mapped, project_unmapped, none}；root＝該層的根目錄；map_path＝該層的
    <root>/.claude/overview-map.md（不存在為 None）。"""
    kind: str
    root: Optional[Path]
    map_path: Optional[Path]


_LAYER_NONE = LayerInfo("none", None, None)


def _is_under(path: Path, root: Path) -> bool:
    """path 在 root（含本身）之下；用 resolve 後的 parents 比對，旁系目錄（~/.claude-foo）不算。"""
    try:
        p, r = path.resolve(), root.resolve()
    except (OSError, ValueError):
        return False
    return p == r or r in p.parents


def _map_path_of(root: Path) -> Optional[Path]:
    mp = root / ".claude" / "overview-map.md"
    try:
        return mp if mp.is_file() else None
    except OSError:
        return None


def _layer_kind_for_root(root: Path, org: Optional[Path]) -> str:
    """已知根目錄 → 層名。根層＝~/.claude 之下；公司層＝公司記憶 repo 根之下；其餘依有沒有表分兩個狀態。"""
    if _is_under(root, CLAUDE_DIR):
        return "root"
    if org is not None and _is_under(root, org):
        return "org"
    return "project_mapped" if _map_path_of(root) else "project_unmapped"


def _layer_of(cwd: str) -> LayerInfo:
    """cwd 屬於哪一層。根層與公司層的 root 是該層的根；專案層的 root 走 resolve_project_root；
    cwd 空、解析不到專案根（家目錄、磁碟根、無四標記）、路徑碰不得（UNC 權限等 OSError）→ none。
    只做路徑包含比對與標記檔存在性檢查，不驗 cwd 本身存在、不讀 transcript、不叫模型。"""
    if not cwd:
        return _LAYER_NONE
    try:
        c = Path(cwd)
        c.resolve()
    except (OSError, ValueError):
        return _LAYER_NONE
    if _is_under(c, CLAUDE_DIR):
        return LayerInfo("root", CLAUDE_DIR, _map_path_of(CLAUDE_DIR))
    org = org_memory_root()
    if org is not None and _is_under(c, org):
        return LayerInfo("org", org, _map_path_of(org))
    if resolve_project_root is None:
        return _LAYER_NONE
    try:
        root = resolve_project_root(cwd).path
    except OSError:
        return _LAYER_NONE
    if root is None:
        return _LAYER_NONE
    mp = _map_path_of(root)
    return LayerInfo("project_mapped" if mp else "project_unmapped", root, mp)


def _deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    """over 疊在 base 上：兩邊都是 dict 才往下併，其餘（含 list）整個取 over；不改 base。"""
    out = dict(base)
    for key, value in over.items():
        both_dict = isinstance(value, dict) and isinstance(out.get(key), dict)
        out[key] = _deep_merge(out[key], value) if both_dict else value
    return out


def get_project_memory_dir(cwd: str) -> Optional[Path]:
    """Get project-level memory dir. New path ({project_root}/.claude/memory/) preferred."""
    if not cwd:
        return None
    root = find_project_root(cwd)
    if root:
        try:
            if root.resolve() == CLAUDE_DIR.resolve():
                return MEMORY_DIR
        except OSError:
            pass
        new_mem = root / ".claude" / "memory"
        if _root_is_declared(cwd):
            # 宣告認領的根：記憶目錄可能還沒建（只 pull 到宣告檔）；讀者對空目錄回空、寫者寫入時才 mkdir
            return new_mem
        if new_mem.is_dir():
            if (new_mem / MEMORY_INDEX).exists():
                return new_mem
            if any((new_mem / d).is_dir() for d in ("shared", "roles", "personal")):
                return new_mem
    slug = cwd_to_project_slug(cwd)
    old_mem = CLAUDE_DIR / "projects" / slug / "memory"
    if old_mem.exists():
        return old_mem
    return None


def get_transcript_path(session_id: str, cwd: str) -> Optional[Path]:
    """Locate session transcript JSONL. Claude Code-managed path."""
    if not session_id or not cwd:
        return None
    slug = cwd_to_project_slug(cwd)
    candidate = CLAUDE_DIR / "projects" / slug / f"{session_id}.jsonl"
    return candidate if candidate.exists() else None


def transcripts_of(transcript_path: str, agent_id: str) -> Tuple[str, List[str]]:
    """(主 session 的 transcript, 要找 AI 宣告／定位行的 transcript 清單)。子代理的對話在 <sid>/subagents/agent-<agent_id>.jsonl、
    主 session 是同層的 <sid>.jsonl：hook 給哪一份都一樣——AI 寫的行兩份都讀（子代理寫在自己回覆裡的也算），
    使用者原話只認主檔（子代理檔裡的 user 訊息是 AI 寫給子代理的任務 prompt）。"""
    if not transcript_path:
        return "", []
    p = Path(transcript_path)
    if p.parent.name == "subagents":
        main = str(p.parent.parent) + ".jsonl"
        return main, [main, str(p)]
    agent = p.with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl" if agent_id else None
    return str(p), [str(p)] + ([str(agent)] if agent is not None and agent.exists() else [])


def transcript_sizes(transcript_path: str) -> Dict[str, int]:
    """主 session transcript 與它底下現在每一份子代理 transcript 的大小（byte），鍵是正斜線小寫路徑。
    記「從這一刻起才算」的起點用：之後才出現的子代理檔不在裡面，整份都算這一刻之後。"""
    main, _ = transcripts_of(transcript_path, "")
    if not main:
        return {}
    files = [Path(main)] + sorted((Path(main).with_suffix("") / "subagents").glob("agent-*.jsonl"))
    out: Dict[str, int] = {}
    for f in files:
        try:
            out[str(f).replace("\\", "/").lower()] = f.stat().st_size
        except OSError:
            continue
    return out


def assistant_texts_since(transcript_path: str, agent_id: str, channel: str, offsets: Any = None, legacy_offset: int = 0) -> str:
    """要找 AI 宣告／定位行的那幾份 transcript（transcripts_of：主檔＋子代理檔）在起點之後的 assistant 內容，主檔在前。
    起點各檔各算：offsets（transcript_sizes 記下的）有記的照記；沒記的檔＝記的時候還不存在，整份都在起點之後。
    offsets 不是 dict（只有舊紀錄的單一 byte offset）時，legacy_offset 只套在 hook 給的那一份、其他檔從頭。"""
    from overview_hub import assistant_text_after
    parts: List[str] = []
    for f in transcripts_of(transcript_path, agent_id)[1]:
        if isinstance(offsets, dict):
            off = int(offsets.get(f.replace("\\", "/").lower(), 0))
        else:
            off = int(legacy_offset) if f == transcript_path else 0
        parts.append(assistant_text_after(f, off, channel))
    return "\n".join(p for p in parts if p)


def resolve_episodic_dir(cwd: str) -> Tuple[Path, str]:
    mem = get_project_memory_dir(cwd)
    if mem:
        return mem / "episodic", f"project:{cwd_to_project_slug(cwd)}"
    return EPISODIC_DIR, "global"


def resolve_failures_dir(cwd: str) -> Path:
    mem = get_project_memory_dir(cwd)
    if mem:
        try:
            is_root_layer = mem.resolve() == MEMORY_DIR.resolve()
        except OSError:
            is_root_layer = mem == MEMORY_DIR
        if not is_root_layer:
            d = mem / "failures"
            d.mkdir(parents=True, exist_ok=True)   # 宣告認領的根層 memory 可能還沒建
            return d
        # cwd 在 ~/.claude 本身：get_project_memory_dir 回 MEMORY_DIR，但根層失敗家族不走
        # 專案佈局（memory/failures/ 小寫舊址），要落全域家族目錄。
    # 全域 failures 家族物理居 memory/Failures/<主題>/（單一來源 atom_locations.FAILURES_DIR）；
    # 小寫 memory/failures/ 是更早的舊址，寫進去會被健檢當 atom 掃到而報格式錯（缺 Trigger）。
    return FAILURES_DIR


def resolve_staging_dir(cwd: str) -> Path:
    mem = get_project_memory_dir(cwd)
    if mem:
        d = mem / "_staging"
        d.mkdir(exist_ok=True)
        return d
    return MEMORY_DIR / "_staging"


def resolve_access_json(atom_name: str, atom_path: Path) -> Path:
    return atom_path.parent / f"{atom_name}.access.json"


# ─── Project Registry ────────────────────────────────────────────────────────


def _today() -> str:
    return date.today().isoformat()


def _load_registry() -> Dict[str, Any]:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"projects": {}}


def _save_registry(reg: Dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    tmp.replace(REGISTRY_PATH)


def _transient_temp_dirs() -> List[Path]:
    """系統暫存根（tempfile + TEMP/TMP 環境變數）；測試 harness 的假專案都住這裡。"""
    import tempfile
    cands = [tempfile.gettempdir(), os.environ.get("TEMP", ""), os.environ.get("TMP", "")]
    out: List[Path] = []
    for c in cands:
        if c:
            try:
                out.append(Path(c).resolve())
            except OSError:
                pass
    return out


# 路徑含這些片段即視為暫存專案（pytest tmp_path 的固定命名）；測試可 monkeypatch 為空以驗登記路徑
_TRANSIENT_PATH_MARKERS = ("pytest-of-",)


def is_transient_project_root(root: Path) -> bool:
    """暫存區內的專案根（pytest tmp_path、系統 Temp）不得登記進 project-registry。

    測試用真 dispatcher 跑假專案時 SessionStart 會呼叫 register_project；不擋會讓
    registry 每跑一次測試長兩筆、dashboard「已知專案」被垃圾淹掉。
    """
    try:
        r = root.resolve()
    except OSError:
        r = root
    if any(m in str(r) for m in _TRANSIENT_PATH_MARKERS):
        return True
    for t in _transient_temp_dirs():
        if r == t or t in r.parents:
            return True
    return False


def register_project(cwd: str) -> None:
    root = find_project_root(cwd)
    if not root:
        return
    # 8.3 短檔名（C:\Users\HOLYLI~1）展開成長名，否則同一專案登記成兩個 slug
    try:
        root = root.resolve()
    except OSError:
        pass
    if is_transient_project_root(root):
        return
    # ~/.claude 本身與家目錄不是「專案」：家目錄的 .claude/memory 就是全域記憶、
    # ~/.claude 的記憶在 memory/ 而非 .claude/memory/；登記只會讓專案清單多兩筆假項目
    try:
        if root.resolve() in (CLAUDE_DIR.resolve(), CLAUDE_DIR.resolve().parent):
            return
    except OSError:
        pass
    if not _has_project_marker(root):
        return
    slug = cwd_to_project_slug(str(root))
    reg = _load_registry()
    entry = reg.setdefault("projects", {}).setdefault(slug, {})
    entry["root"] = str(root)
    entry["last_seen"] = _today()
    _save_registry(reg)


def get_slug_pointer_path(cwd: str) -> Path:
    slug = cwd_to_project_slug(cwd)
    return CLAUDE_DIR / "projects" / slug / "memory" / MEMORY_INDEX


# per-process memoize：同一 hook 行程內多次 discover（UPS 跨專案掃描 + 截斷
# fallback roots 等）只實掃一次。簽章 = registry 檔 + projects/ 目錄的
# (path, mtime)——任一變動（登錄新專案 / 新增專案夾）即失效重掃。
# hook 行程 per-event 短命，cache 生命週期即單次 hook 呼叫，無跨 prompt 過期問題。
_DISCOVER_CACHE: Optional[Tuple[tuple, List[Tuple[str, Path]]]] = None


def _discover_signature() -> tuple:
    def _mt(p: Path) -> int:
        try:
            return p.stat().st_mtime_ns
        except OSError:
            return 0
    reg = REGISTRY_PATH
    projects = CLAUDE_DIR / "projects"
    return (str(reg), _mt(reg), str(projects), _mt(projects))


def discover_all_project_memory_dirs() -> List[Tuple[str, Path]]:
    """Discover all project memory directories. Registry-first + old-path fallback.

    Per-process memoized（見 _DISCOVER_CACHE）；回傳 list 為淺拷貝，caller 可安全變異。
    """
    global _DISCOVER_CACHE
    sig = _discover_signature()
    if _DISCOVER_CACHE is not None and _DISCOVER_CACHE[0] == sig:
        return list(_DISCOVER_CACHE[1])
    results = _discover_all_project_memory_dirs_uncached()
    _DISCOVER_CACHE = (sig, list(results))
    return results


def hook_python_exe() -> str:
    """hook 要起 Python 子行程時用的直譯器：hook 本身在 pythonw.exe 下跑（無 console）時，spawn sys.executable 會沒有 stdout
    → 改用同目錄的 python.exe；其他情況就是 sys.executable。pre_tool_use（合併驅動／svn 工具）與 wg_reading_path 共用這一支。"""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        sib = exe.with_name("python.exe")
        if sib.exists():
            return str(sib)
    return str(exe)


def find_vcs_root_ex(start: Path) -> Tuple[Optional[Tuple[str, Path]], str]:
    """從 start 往上找最近的 VCS 根：.git（dir 或 worktree/submodule 的 file）或 .svn 目錄。回 (命中, 錯誤原因)：
    命中＝("git"|"svn", root)，不在工作區＝None；檔案系統出錯（權限、網路路徑斷、路徑太長）→ (None, "OSError: …")，
    讀不到和「不在版控」是兩回事（規則 VCS_ROOT_UNREADABLE：讀不到照欠）。純檔案系統 walk-up、零 subprocess。
    巢狀時取最近的那個（svn WC 住在 git repo 裡，如 svn 工作副本 <repo>/Tools 在 git repo <repo> 之下）。"""
    cur = Path(start)
    while True:
        try:
            if (cur / ".git").exists():
                return ("git", cur), ""
            if (cur / ".svn").is_dir():
                return ("svn", cur), ""
        except OSError as e:
            return None, f"{type(e).__name__}: {e}"
        if cur.parent == cur:
            return None, ""
        cur = cur.parent


def find_vcs_root(start: Path) -> Optional[Tuple[str, Path]]:
    """find_vcs_root_ex 不帶錯誤原因的版本（讀不到當不在工作區；要分辨的呼叫端用 _ex）。"""
    return find_vcs_root_ex(start)[0]


def find_svn_root(start: Path) -> Optional[Path]:
    """從 start 往上找最近的 .svn 目錄所在層（svn 工作副本根）；不在 svn 工作副本內回 None。

    find_vcs_root 在同一層同時有 .git 與 .svn（git 疊在 svn 上）時回 git，
    處理 svn 狀態（衝突、resolve）的呼叫端要改用這支，否則 svn 那一側永遠看不到。零 subprocess。
    """
    cur = Path(start)
    while True:
        try:
            if (cur / ".svn").is_dir():
                return cur
        except OSError:
            return None
        if cur.parent == cur:
            return None
        cur = cur.parent


def memory_dir_candidates(start: Path, root: Path) -> List[Path]:
    """VCS 根 root 之下可能的記憶樹——不掃整個工作區（大 SVN WC 的 svn status 要 3～6 秒，hook 預算只有 2.5 秒）。

    收：start 往上到 root 每層的 `.claude/memory`、root 的根層佈局 `memory/`（須有 _atom_index.json）、
    登記專案中位於 root 之下者。回存在的目錄，去重、保序。
    """
    out: List[Path] = []
    seen: set = set()

    def _add(p: Path) -> None:
        try:
            key = p.resolve()
        except OSError:
            return
        if p.is_dir() and key not in seen:
            seen.add(key)
            out.append(p)

    try:
        root_r = Path(root).resolve()
        cur = Path(start).resolve()
        cur.relative_to(root_r)
    except (OSError, ValueError):
        cur, root_r = Path(root), Path(root)
    while True:
        _add(cur / ".claude" / "memory")
        if cur == root_r or cur.parent == cur:
            break
        cur = cur.parent
    if (Path(root) / "memory" / "_atom_index.json").exists():
        _add(Path(root) / "memory")
    for _slug, mem in discover_all_project_memory_dirs():
        try:
            mem.resolve().relative_to(root_r)
        except (OSError, ValueError):
            continue
        _add(mem)
    return out


def _discover_all_project_memory_dirs_uncached() -> List[Tuple[str, Path]]:
    # 全域記憶目錄不得被當「專案記憶」回傳：registry 若有 root=家目錄 的條目
    # （root/.claude/memory == 全域 MEMORY_DIR），cross-project 掃描會把全域 atom
    # 再補進候選一次造成同 atom 雙注入。
    try:
        _global_mem = MEMORY_DIR.resolve()
    except OSError:
        _global_mem = MEMORY_DIR

    def _is_global_mem(mem: Path) -> bool:
        try:
            return mem.resolve() == _global_mem
        except OSError:
            return False

    def _has_atom_index_marker(mem: Path) -> bool:
        # CC harness 原生 file-based memory（projects/<slug>/memory/）也自建 MEMORY.md
        # （`- [Title](file.md) — hook` 清單），與 atom 索引撞名。辨識依據：
        # atom 索引必有 _atom_index.json / _ATOM_INDEX.md，或 MEMORY.md 含
        # 「| Atom」trigger 表頭 / migrated-v2.21 slug-pointer stub（get_slug_pointer_path）。
        if (mem / "_atom_index.json").exists() or (mem / ATOM_INDEX).exists():
            return True
        idx = mem / MEMORY_INDEX
        if not idx.is_file():
            return False
        try:
            text = idx.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            return False
        return "| Atom" in text or "|Atom" in text or "Status: migrated-v2.21" in text

    seen_slugs: set = set()
    results: List[Tuple[str, Path]] = []
    reg = _load_registry()
    for slug, info in reg.get("projects", {}).items():
        root = Path(info.get("root", ""))
        if not root.is_dir():
            continue
        new_mem = root / ".claude" / "memory"
        if new_mem.is_dir() and (new_mem / MEMORY_INDEX).exists():
            if not _is_global_mem(new_mem):
                results.append((slug, new_mem))
            seen_slugs.add(slug)
            continue
        old_mem = CLAUDE_DIR / "projects" / slug / "memory"
        if old_mem.is_dir():
            # registry old-path 同樣要過 atom marker：harness 原生 memory dir 與
            # 此路徑完全重合。
            if not _is_global_mem(old_mem) and _has_atom_index_marker(old_mem):
                results.append((slug, old_mem))
            seen_slugs.add(slug)
    projects_dir = CLAUDE_DIR / "projects"
    if projects_dir.is_dir():
        for proj_dir in sorted(projects_dir.iterdir()):
            if not proj_dir.is_dir():
                continue
            slug = proj_dir.name
            if slug in seen_slugs:
                continue
            mem = proj_dir / "memory"
            # 要求 atom 索引 marker 才納入。MEMORY.md 僅存在不夠——
            # 新版 CC harness file-based memory 也在此路徑自建 MEMORY.md，
            # 需內容辨識（_has_atom_index_marker）區分兩套系統。
            if mem.is_dir() and not _is_global_mem(mem) and _has_atom_index_marker(mem):
                results.append((slug, mem))
    return results


def discover_v4_sublayers(slug: str, mem_dir: Path) -> List[Tuple[str, Path, str]]:
    """V4: enumerate sub scope layers under a project memory dir."""
    out: List[Tuple[str, Path, str]] = []
    shared_label = f"shared:{slug}"

    def _is_legacy_atom(p: Path) -> bool:
        if not (p.is_file() and p.suffix == ".md"):
            return False
        if p.name in (MEMORY_INDEX, ATOM_INDEX):
            return False
        if p.name.startswith("_") or p.name.startswith("SPEC_"):
            return False
        return True
    has_flat_legacy = any(_is_legacy_atom(p) for p in mem_dir.iterdir()) if mem_dir.is_dir() else False
    if has_flat_legacy:
        out.append((shared_label, mem_dir, "flat-legacy"))

    shared_dir = mem_dir / "shared"
    if shared_dir.is_dir():
        out.append((shared_label, shared_dir, "recursive"))

    # 專案層失敗家族（memory/failures/<主題>/；scope=shared 的 feedback-* 落點，
    # resolve_failures_dir 同址）屬 shared 層——向量索引／去重層清單靠這裡才看得到。
    failures_dir = mem_dir / "failures"
    if failures_dir.is_dir():
        out.append((shared_label, failures_dir, "recursive"))

    roles_root = mem_dir / "roles"
    if roles_root.is_dir():
        for rd in sorted(roles_root.iterdir()):
            if rd.is_dir() and not rd.name.startswith("_"):
                out.append((f"role:{slug}:{rd.name}", rd, "recursive"))

    personal_root = mem_dir / "personal"
    if personal_root.is_dir():
        for pd in sorted(personal_root.iterdir()):
            if pd.is_dir() and not pd.name.startswith("_"):
                out.append((f"personal:{slug}:{pd.name}", pd, "recursive"))

    return out


def discover_memory_layers(
    layer_filter: Optional[str] = None,
    user: Optional[str] = None,
    role: Optional[str] = None,
) -> List[Tuple[str, Path]]:
    """Discover memory layers with optional role filter (SPEC §8.1)."""
    layers: List[Tuple[str, Path]] = []

    def _accept(label: str) -> bool:
        if not layer_filter or layer_filter == "all":
            return True
        if layer_filter == label:
            return True
        if layer_filter == "global":
            return label == "global"
        if layer_filter == "shared":
            return label.startswith("shared:")
        if layer_filter == "role":
            return label.startswith("role:")
        if layer_filter.startswith("role:") and ":" not in layer_filter[5:]:
            r = layer_filter.split(":", 1)[1]
            return label.startswith("role:") and label.endswith(f":{r}")
        if layer_filter == "personal":
            return label.startswith("personal:")
        if layer_filter.startswith("personal:") and ":" not in layer_filter[9:]:
            u = layer_filter.split(":", 1)[1]
            return label.startswith("personal:") and label.endswith(f":{u}")
        return False

    if _accept("global"):
        layers.append(("global", MEMORY_DIR))

    role_set = set()
    if role:
        role_set = {r.strip() for r in role.split(",") if r.strip()}

    user_aware = bool(user or role)

    for slug, mem_dir in discover_all_project_memory_dirs():
        for label, path, _kind in discover_v4_sublayers(slug, mem_dir):
            if user_aware:
                if label.startswith("shared:"):
                    pass
                elif label.startswith("role:"):
                    r = label.rsplit(":", 1)[1]
                    if r not in role_set:
                        continue
                elif label.startswith("personal:"):
                    u = label.rsplit(":", 1)[1]
                    if u != user:
                        continue
            if not _accept(label):
                continue
            layers.append((label, path))

    return layers


def state_file_path(session_id: str) -> Path:
    return WORKFLOW_DIR / f"state-{session_id}.json"


# ─── State File I/O ──────────────────────────────────────────────────────────
#
# 規則 STATE_RMW_LOCKED：同一個 session 的 hook 行程（同一則回覆的平行工具呼叫、共用 session_id 的子代理）讀改寫 state 要排隊。
# dispatcher 進 handler 前呼叫 begin_state_rmw(期限)：之後第一次讀某個 session 的 state 就拿它的鎖（state-<sid>.lock），
# 握到 end_state_rmw。讀 → 改 → 寫整段在鎖裡：寫回的一定是看過別人最新那份之後的結果，序號（event_seq）也在鎖裡配。
# 等到期限（hook 上限的一半）仍拿不到鎖：這次照讀沒上鎖的那份讓閘照判，寫回不整份覆蓋，改留一份待併帳
# （state-<sid>.<時間>-<pid>.pending：這次改了哪些鍵、改前、改後；副檔名不是 .json，各處掃 state-*.json 不會當成 session），
# stderr 與 Logs/guard-state_lock.jsonl 留訊號；同一支 hook 再寫回只記上一份帳之後的變動。
# 下一支拿到鎖的行程讀 state 時照欄位分型併回（子規則 STATE_PENDING_MERGED）：併過的帳名跟合併結果同一次寫進 state
# （_state_pending_applied），刪不掉的帳下次跳過再刪，不會套兩次。
# 沒進 hook 模式的寫者（測試、工具）寫回時才拿鎖；鎖裡發現檔在自己讀到之後被換過 → 照欄位分型三方合併（_merge_state），不整份覆蓋。
# 每支行程對每個 state 檔記一份「基準」：讀到的原文（讀到檔不在＝空 state）與讀到那刻的檔案指紋；寫回、留帳後推進到自己寫出的那份。


def state_path(session_id: str) -> Path:
    """Alias kept for backward compat with callers."""
    return state_file_path(session_id)


def read_state(session_id: str) -> Optional[Dict[str, Any]]:
    """讀 state；檔不存在或讀壞都回 None（呼叫端要分辨請用 read_state_status）。"""
    return read_state_status(session_id)[0]


def read_state_status(session_id: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """回 (state, status)：status ∈ {"ok", "missing", "error"}。

    Windows 上 tmp+replace 的瞬間、或另一支 hook 正持有檔案時，read 會拋 PermissionError／
    sharing violation——那是「暫時讀不到」不是「檔不見了」，呼叫端不得當遺失去重建（_ensure_state 只重試、不覆蓋）。
    hook 模式（begin_state_rmw 之後）先拿這個 session 的鎖再讀，握到 end_state_rmw（規則 STATE_RMW_LOCKED）。
    讀到檔不在，基準記成空 state：之後寫回是「從空的建起」，跟別人同時建的照欄位合併，不當成整份換掉。
    """
    path = state_path(session_id)
    key = str(path)
    if _RMW["on"]:
        _rmw_lock(path)
    if not path.exists():
        _STATE_READ_TEXT[key] = _EMPTY_BASE
        _STATE_READ_SIG.pop(key, None)
        _APPLIED_BASE.pop(key, None)
        return None, "missing"
    try:
        with open(path, "r", encoding="utf-8") as f:
            sig = _sig_of(os.fstat(f.fileno()))
            text = f.read()
        state = json.loads(text)
    except (json.JSONDecodeError, OSError):
        return None, "error"
    _STATE_READ_TEXT[key] = text
    _STATE_READ_SIG[key] = sig
    _APPLIED_BASE[key] = list(state.get(_PENDING_APPLIED_KEY) or []) if isinstance(state, dict) else []
    return state, "ok"


# STATE_WRITE_SKIP_UNCHANGED：這個行程讀到的 state 原文（路徑 → 原文）；write_state 寫出來跟它一樣（只差 last_updated）就不重寫，
# 只在檔快過跨 session 協調的掃描窗口時碰一下 mtime（wg_coordination 用 mtime 挑活著的 session）。
# 同一份原文也是三方合併的「自己讀到的那份」。
_STATE_READ_TEXT: Dict[str, str] = {}
_STATE_READ_SIG: Dict[str, Tuple[int, int]] = {}   # 路徑 → 基準那份在磁碟上的 (mtime_ns, 大小)：寫回前先比，對不上或沒有才比全文
_EMPTY_BASE = "{}"                                 # 讀到檔不在時的基準
_STATE_TOUCH_AFTER_S = 300.0
_STATE_LOCK_POLL_S = 0.01      # 鎖拿不到每 10 ms 再試
_STATE_LOCK_WAIT_S = 2.0       # 沒給期限時最多等幾秒（hook 模式的期限由 dispatcher 給：hook 上限的一半）
_STATE_REPLACE_RETRIES = 10    # replace 失敗（目標被別的讀者開著）的重試次數
_STATE_REPLACE_RETRY_S = 0.02
_PENDING_MAX_PER_MERGE = 20    # 一次拿到鎖最多併幾份帳（其餘留給下一支）
_PENDING_APPLIED_KEY = "_state_pending_applied"   # state 裡記「併過、檔還在的帳名」：併帳與記帳名同一次落盤
_FALLBACK_KEY = "_fallback_state_rebuilt"
_RMW: Dict[str, Any] = {"on": False, "deadline": 0.0}
_HELD_LOCKS: Dict[str, Any] = {}       # state 檔路徑 → 鎖檔 handle（hook 模式握到 end_state_rmw）
_LOCKLESS: set = set()                 # hook 模式等到期限仍沒拿到鎖的 state 檔（訊號只浮一次）
_OWN_PENDING: Dict[str, List[str]] = {}   # 路徑 → 這支行程留過、還沒確認落盤的帳名：全落盤之前寫回只能再留帳
_APPLIED_BASE: Dict[str, List[str]] = {}   # 路徑 → 基準那份裡的併過帳名（呼叫端整份重建 state 時照帶，不讓帳重套）
_MISSING = object()                    # 三方合併裡「沒有這個鍵」


def _dump_state(state: Dict[str, Any]) -> str:
    """state 落檔格式：緊湊 JSON（不縮排；state 動輒幾百 KB，縮排多四成大小與序列化時間）。"""
    return json.dumps(state, ensure_ascii=False, separators=(",", ":"))


def _sig_of(st: os.stat_result) -> Tuple[int, int]:
    return (st.st_mtime_ns, st.st_size)


def begin_state_rmw(deadline: Optional[float] = None) -> None:
    """hook 行程進 handler 前呼叫（dispatcher）：之後讀到的每個 session state 都先拿鎖、握到 end_state_rmw（STATE_RMW_LOCKED）。
    deadline＝等鎖等到幾點（epoch 秒）；沒給就從現在起最多等 _STATE_LOCK_WAIT_S。"""
    _RMW["on"] = True
    _RMW["deadline"] = deadline if deadline is not None else time.time() + _STATE_LOCK_WAIT_S


def end_state_rmw() -> None:
    """handler 結束（含 sys.exit）：放掉握著的 state 鎖、離開 hook 模式。"""
    for key, fh in list(_HELD_LOCKS.items()):
        _release_state_lock(fh, Path(key).with_suffix(".lock"))
    _HELD_LOCKS.clear()
    _LOCKLESS.clear()
    _OWN_PENDING.clear()        # 下一支 hook 重讀基準；這支留的帳對它就是一般的待併帳
    _RMW["on"] = False


def _acquire_state_lock(lock_path: Path, deadline: float):
    """拿 state 鎖（Windows msvcrt 鎖 1 byte、其他平台 fcntl.flock；行程結束系統自動放）：拿不到每 10 ms 再試到 deadline
    （至少試一次），仍拿不到回 None。"""
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    while True:
        fh = None
        try:
            fh = open(lock_path, "ab")
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except OSError:
            if fh is not None:
                fh.close()
        if time.time() >= deadline:
            return None
        time.sleep(_STATE_LOCK_POLL_S)


def _release_state_lock(fh, lock_path: Path) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    fh.close()
    if sys.platform == "win32":    # Windows 有人開著就刪不掉：刪得掉＝沒人在等；其他平台刪了會讓等的人鎖到另一個檔，留著
        try:
            lock_path.unlink()
        except OSError:
            pass


def _rmw_lock(path: Path) -> bool:
    """hook 模式：拿 path 的鎖並握著（已握著直接回 True）；拿到時先併回別人留的待併帳（不動這支行程的基準）。
    等到期限仍沒拿到回 False。"""
    key = str(path)
    if key in _HELD_LOCKS:
        return True
    fh = _acquire_state_lock(path.with_suffix(".lock"), _RMW["deadline"])
    if fh is None:
        if key not in _LOCKLESS:
            _LOCKLESS.add(key)
            print(f"[state:lock-timeout] {path.name}：等到期限仍拿不到 state 鎖，這次照讀沒上鎖的那份；"
                  "寫回不整份覆蓋，改留待併帳給下一支拿到鎖的 hook 併回", file=sys.stderr)
        return False
    _HELD_LOCKS[key] = fh
    _LOCKLESS.discard(key)
    _merge_pending(path)
    return True


def _replace_text(path: Path, text: str) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    """tmp（每行程唯一：<檔名>.<pid>.tmp）寫好再 os.replace 換上，檔永遠是某一方的完整內容；replace 失敗（目標被別的讀者
    開著）重試。回 (失敗原因或 None, 換上那份的檔案指紋)：指紋取自 tmp（換檔保留時間與大小），換上之後才被別人換掉也認得出來。
    失敗原因是「replace-failed／write-failed：原因」（tmp 清掉、原檔不動）。"""
    tmp_path = path.with_name(f"{path.stem}.{os.getpid()}.tmp")
    err = None
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        sig = _sig_of(os.stat(tmp_path))
        for _ in range(_STATE_REPLACE_RETRIES):
            try:
                tmp_path.replace(path)
                return None, sig
            except OSError as e:
                err = f"replace-failed：{e}"
                time.sleep(_STATE_REPLACE_RETRY_S)
    except OSError as e:
        err = f"write-failed：{e}"
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError as e:
                print(f"[state:tmp-left] {tmp_path.name}：{e}（另一行程握著，殘檔留下）", file=sys.stderr)
    return err, None


def _remember(path: Path, text: str, sig: Optional[Tuple[int, int]], state: Optional[Dict[str, Any]] = None) -> None:
    """基準推進到剛寫出的那份：下次寫回比對有沒有被換過、STATE_WRITE_SKIP_UNCHANGED 都拿它比；state 給了就一併記它的併過帳名。"""
    _STATE_READ_TEXT[str(path)] = text
    if state is not None:
        _APPLIED_BASE[str(path)] = list(state.get(_PENDING_APPLIED_KEY) or [])
    if sig is None:
        _STATE_READ_SIG.pop(str(path), None)
    else:
        _STATE_READ_SIG[str(path)] = sig


def _disk_since_read(path: Path, base_text: str, base_sig: Optional[Tuple[int, int]]) -> Tuple[bool, Optional[str]]:
    """（鎖裡）檔跟基準比有沒有被換過：指紋對得上就沒換；對不上或沒有指紋再比全文。
    回 (換過沒, 磁碟上的原文；檔不在或讀不到回 None)。同指紋不同內容（同一個 100ns、同大小）認不出來。"""
    try:
        sig = _sig_of(os.stat(path))
    except OSError:
        return True, None
    if base_sig is not None and base_sig == sig:
        return False, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            disk = f.read()
    except OSError:
        return True, None
    return disk != base_text, disk


def write_state(session_id: str, state: Dict[str, Any]) -> None:
    """寫回 state（規則 STATE_RMW_LOCKED）：在這個 session 的鎖裡寫，tmp 每行程唯一＋os.replace 換檔，state 檔永遠是完整 JSON。

    鎖裡先看檔跟這支行程的基準比有沒有被換過：沒有 → 整份寫；有（沒全程握鎖、拿鎖時併了別人的帳、不守鎖的寫者寫過）
    → 基準、自己改成的、磁碟上現在的三方照欄位分型合併再寫（_merge_state），寫成功才把合併結果同步回呼叫端的 dict。
    拿不到鎖（等到期限）或換檔失敗：不無鎖寫、不整份覆蓋，改留待併帳（_write_pending），下一支拿到鎖的行程併回。
    沒讀過這個檔就寫（合併轉址、測試造檔）＝呼叫端要整份換掉，照整份寫；fallback 重建的 state（_ensure_state 以為檔不在才建）
    遇到鎖裡檔已存在時不寫，改把磁碟那份同步回呼叫端（讀不到不等於遺失）。
    為什麼：平行 hook 各自讀到同一份舊 state、各自加上自己那筆再整份寫回，後寫的會蓋掉先寫的（讀檔、改檔紀錄掉了）。
    """
    WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)

    canonical_id = state.get("session", {}).get("id")
    if canonical_id and canonical_id != session_id:
        session_id = canonical_id

    path = state_path(session_id)
    key = str(path)
    carried = [n for n in _APPLIED_BASE.get(key, []) if n not in (state.get(_PENDING_APPLIED_KEY) or [])]
    if carried:                                  # 呼叫端整份重建時丟了併過名單：照基準帶回去（那幾份帳不能再套）
        state[_PENDING_APPLIED_KEY] = [*(state.get(_PENDING_APPLIED_KEY) or []), *carried]
    old_stamp, stamp = state.get("last_updated"), _now_iso()
    state["last_updated"] = stamp
    text = _dump_state(state)
    base_text, base_sig = _STATE_READ_TEXT.get(key), _STATE_READ_SIG.get(key)
    if base_text is not None and old_stamp is not None and path.exists():
        unstamped = text.replace(f'"last_updated":{json.dumps(stamp)}', f'"last_updated":{json.dumps(old_stamp)}', 1)
        if unstamped == base_text:
            state["last_updated"] = old_stamp
            try:
                if time.time() - path.stat().st_mtime > _STATE_TOUCH_AFTER_S:
                    os.utime(path)
            except OSError:
                pass
            return

    lock_fh = None
    if _RMW["on"]:
        locked = _rmw_lock(path)
    else:
        lock_fh = _acquire_state_lock(path.with_suffix(".lock"), time.time() + _STATE_LOCK_WAIT_S)
        locked = lock_fh is not None
        if not locked:
            print(f"[state:lock-timeout] {path.name}：等 {_STATE_LOCK_WAIT_S:g}s 仍拿不到 state 鎖", file=sys.stderr)
    if not locked:
        _write_pending(path, base_text, state, "lock-timeout")
        return
    try:
        if lock_fh is not None or key in _OWN_PENDING:   # 剛拿到鎖、或自己留過帳：先併掉，磁碟才含那些變動，下面三方合併才對
            done = _merge_pending(path)
            own_left = [n for n in _OWN_PENDING.pop(key, []) if n not in done and (path.parent / n).exists()]
            if own_left:                                 # 自己先前的帳還沒落盤（併不進去、超過一次的份數）：這次也只能留帳
                _OWN_PENDING[key] = own_left
                _write_pending(path, base_text, state, "own-pending-left")
                return
        merged = None
        if base_text in (None, _EMPTY_BASE) and state.get(_FALLBACK_KEY) and path.exists():
            _adopt_disk(path, state)
            return
        if base_text is not None:
            changed, disk = _disk_since_read(path, base_text, base_sig)
            if changed and disk is not None:
                try:
                    theirs = json.loads(disk)
                except ValueError:
                    theirs = None
                    print(f"[state:disk-unreadable] {path.name}：磁碟上那份不是合法 JSON，整份換成這次的", file=sys.stderr)
                if isinstance(theirs, dict):
                    merged, conflicts = _merge_state(json.loads(base_text), state, theirs)
                    merged["last_updated"] = stamp
                    text = _dump_state(merged)
        err, sig = _replace_text(path, text)
        if err:
            tag, _, why = err.partition("：")
            print(f"[state:{tag}] {path.name}：{why}；這次改的改留待併帳", file=sys.stderr)
            _write_pending(path, base_text, state, tag)
            return
        _remember(path, text, sig, merged if merged is not None else state)
        if merged is not None:
            state.clear()
            state.update(merged)
            print(f"[state:merged] {path.name}：基準之後被別人寫過，三方合併後寫回"
                  + (f"；兩邊都改、留磁碟那份的鍵：{', '.join(conflicts[:8])}" if conflicts else ""), file=sys.stderr)
            append_guard_log("state_lock", {"kind": "merged", "file": path.name, "conflicts": conflicts[:30]})
    finally:
        if lock_fh is not None:
            _release_state_lock(lock_fh, path.with_suffix(".lock"))


def _adopt_disk(path: Path, state: Dict[str, Any]) -> None:
    """（鎖裡）fallback 重建的 state 不蓋掉已存在的檔：讀磁碟那份、同步回呼叫端並記成基準；讀不到就這次不寫（stderr）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            sig = _sig_of(os.fstat(f.fileno()))
            text = f.read()
        disk = json.loads(text)
    except (OSError, ValueError) as e:
        print(f"[state:fallback-skipped] {path.name}：檔已存在但讀不到（{type(e).__name__}），這次不寫、不覆蓋", file=sys.stderr)
        return
    state.clear()
    state.update(disk)
    _remember(path, text, sig, disk)
    print(f"[state:fallback-skipped] {path.name}：以為檔不在才建的 fallback state，鎖裡發現檔已存在，改用磁碟那份", file=sys.stderr)


def _write_pending(path: Path, base_text: Optional[str], ours: Dict[str, Any], why: str) -> None:
    """拿不到鎖或換不了檔：這次跟基準比改到的鍵（改前、改後）寫成一份待併帳，下一支拿到鎖的行程併回（子規則 STATE_PENDING_MERGED）；
    寫成了就把基準推進到這次的內容，同一支行程再寫回只記之後的變動。沒讀過就整份寫的（base_text 是 None）記成整份換掉；
    讀到檔不在的記成「從空的建起」。跟基準一樣就不留；帳也寫不出去 → stderr＋guard log（這次的變動真的沒進去）。"""
    try:
        base = json.loads(base_text) if base_text is not None else None
    except ValueError:
        base = {}
    keys: Dict[str, Dict[str, Any]] = {}
    for k in dict.fromkeys([*(base or {}), *ours]):
        b, o = (base or {}).get(k, _MISSING), ours.get(k, _MISSING)
        if k in ("last_updated", _PENDING_APPLIED_KEY) or b == o:
            continue
        keys[k] = {**({"base": b} if b is not _MISSING else {}), **({"ours": o} if o is not _MISSING else {})}
    if not keys:
        return
    body: Dict[str, Any] = {"why": why, "pid": os.getpid()}
    if base is None:
        body["whole"] = ours
    else:
        body.update({"keys": keys, "from_empty": base_text == _EMPTY_BASE})
    dest = path.with_name(f"{path.stem}.{time.time_ns()}-{os.getpid()}.pending")
    err, _sig = _replace_text(dest, json.dumps(body, ensure_ascii=False, separators=(",", ":")))
    rec = {"file": path.name, "pending": dest.name, "why": why, "whole": base is None, "keys": sorted(keys)[:30]}
    if err:
        print(f"[state:pending-failed] {dest.name}：{err}；這次改的 {len(keys)} 個鍵沒寫進 state", file=sys.stderr)
        append_guard_log("state_lock", {"kind": "pending_failed", "error": err, **rec})
        return
    _remember(path, _dump_state(ours), None, ours)
    _OWN_PENDING.setdefault(str(path), []).append(dest.name)
    print(f"[state:pending-written] {path.name}：{why}，這次改的 {len(keys)} 個鍵留在 {dest.name}，"
          "下一支拿到鎖的 hook 併回", file=sys.stderr)
    append_guard_log("state_lock", {"kind": "pending_written", **rec})


def _pending_files(path: Path) -> List[Path]:
    """這個 state 檔的待併帳（照留帳時間排）；檔名精確比對 <state 檔名>.<時間>-<pid>.pending，別的 session 的帳不會混進來。"""
    import glob as _glob
    pat = re.compile(re.escape(path.stem) + r"\.\d+-\d+\.pending")
    return sorted(p for p in path.parent.glob(_glob.escape(path.stem) + ".*.pending") if pat.fullmatch(p.name))


def _merge_pending(path: Path) -> set:
    """（鎖裡）把別的行程留下的待併帳照時間先後、照欄位分型併回 state、寫回後刪帳（子規則 STATE_PENDING_MERGED）。
    併過的帳名跟合併結果同一次寫進 state（_state_pending_applied，只留檔還在的），刪不掉的下次跳過再刪，不會套兩次；
    一次最多新併 _PENDING_MAX_PER_MERGE 份（刪不掉的舊帳不佔名額）。整份換掉的帳直接換成它那份；fallback 重建的帳遇到已存在的
    state 不覆蓋，旗標也不會被帳加到既有的 state 上。state 是轉址 stub（merged_into）也照併進 stub 本身、不碰目標（帳的基準是這個
    session 的歷史，套到別的 session 會算錯），另浮訊號＋留帳：讀的人會轉去目標，看不到這幾筆。state 檔不在時只套整份與「從空的建起」的帳，其餘留著；state 讀壞或寫不回 → 帳留著等下一次；
    壞掉的帳改名 .corrupt（照 workflow 清理規則清）並浮訊號。回「磁碟上已記成併過」的帳名（呼叫端拿來確認自己的帳落盤了沒）。"""
    pend = _pending_files(path)
    if not pend:
        return set()
    existed = path.exists()
    try:
        cur = json.loads(path.read_text(encoding="utf-8")) if existed else None
    except (OSError, ValueError) as e:
        print(f"[state:pending-wait] {path.name}：state 讀不到（{type(e).__name__}），待併帳 {len(pend)} 份留著下次再併",
              file=sys.stderr)
        return set()
    stub_of = str(cur.get("merged_into") or "") if isinstance(cur, dict) else ""
    had_flag = isinstance(cur, dict) and _FALLBACK_KEY in cur
    applied = [n for n in (cur or {}).get(_PENDING_APPLIED_KEY) or [] if (path.parent / n).exists()]
    used, done_before, conflicts, dropped = [], [], [], []
    for p in pend:
        if p.name in applied:
            done_before.append(p)
            continue
        if len(used) >= _PENDING_MAX_PER_MERGE:
            break
        try:
            body = json.loads(p.read_text(encoding="utf-8"))
            whole = body.get("whole")
            items = [] if isinstance(whole, dict) else list(body["keys"].items())
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            print(f"[state:pending-corrupt] {p.name}：{type(e).__name__}: {e}；改名 .corrupt、不併", file=sys.stderr)
            try:
                p.replace(p.with_name(p.name + ".corrupt"))
            except OSError:
                pass
            continue
        if isinstance(whole, dict):
            if cur is not None and whole.get(_FALLBACK_KEY):
                dropped.append(p.name)
            else:
                cur = dict(whole)
        elif cur is None and not body.get("from_empty"):
            continue                                   # 沒有 state 可併：留著等 state 建好
        else:
            cur = cur if cur is not None else {}
            for k, ent in items:
                v = _merge3(k, ent.get("base", _MISSING), ent.get("ours", _MISSING), cur.get(k, _MISSING), conflicts)
                if v is _MISSING:
                    cur.pop(k, None)
                else:
                    cur[k] = v
        used.append(p)
    if used and cur is not None:
        if existed and not had_flag:
            cur.pop(_FALLBACK_KEY, None)
        cur[_PENDING_APPLIED_KEY] = list(dict.fromkeys([*applied, *(p.name for p in used)]))
        cur["last_updated"] = _now_iso()
        err, _sig = _replace_text(path, _dump_state(cur))
        if err:
            print(f"[state:pending-wait] {path.name}：併好寫不回（{err}），待併帳留著下次再併", file=sys.stderr)
            return set(applied)
    elif not done_before:
        return set(applied)
    left = []
    for p in [*used, *done_before]:
        try:
            p.unlink()
        except OSError:
            left.append(p.name)
    print(f"[state:pending-merged] {path.name}：併回 {len(used)} 份待併帳"
          + (f"；之前併過、這次補刪 {len(done_before)} 份" if done_before else "")
          + (f"；兩邊都改、留磁碟那份的鍵：{', '.join(conflicts[:8])}" if conflicts else "")
          + (f"；fallback 重建的帳遇到已存在的 state、不覆蓋：{', '.join(dropped)}" if dropped else "")
          + (f"；刪不掉的帳（已記成併過）：{', '.join(left)}" if left else "")
          + (f"；這是轉址 stub（讀的人轉去 {stub_of}），併進來的 {len(used)} 份看不到" if stub_of and used else ""),
          file=sys.stderr)
    append_guard_log("state_lock", {"kind": "pending_merged", "file": path.name, "merged": [p.name for p in used],
                                    "done_before": [p.name for p in done_before], "conflicts": conflicts[:30],
                                    "dropped": dropped, "left": left, **({"redirect_stub_of": stub_of} if stub_of else {})})
    return {*applied, *(p.name for p in used)}


# 三方合併的欄位分型（鍵路徑：頂層鍵、`.子鍵`、`[]`＝清單裡的一筆紀錄；fnmatch 比對，先列先中）。沒列的照值的型別：
# 物件逐鍵合併、清單取聯集、數字取大（回合、序號、門檻計數）、時間字串取新；其餘兩邊都改就留磁碟那份、記進 conflicts。
_MERGE_TYPES: Tuple[Tuple[str, str], ...] = (
    ("modified_files", "keyed"),                 # 業務鍵紀錄：(canon 路徑, session_id) 一筆，count＝讀到的＋兩邊各自加的
    ("agent_modified_files.*", "keyed"),
    ("*[].count", "add"),
    ("edit_counts.*", "add"),                    # 累加計數：讀到的＋兩邊各自加的；有一邊變小（歸零）就取小的
    ("stop_blocked_count", "add"),
    ("sync_reminder_count", "add"),
    ("topic_tracker.prompt_count", "add"),
    ("tool_result_advisories", "add"),
    ("wisdom_retry_count", "add"),
    ("overview_hub.*.edits", "add"),
    ("overview_hub.*.edited_files.*", "add"),
    ("decl_deny_counts.counts.*", "add"),
    ("overview_hub.*", "version:injected_turn"),   # 分版本整組：版本新的整組勝（重新注入整筆換掉），同版本才逐欄併
    ("decl_deny_counts", "version:turn"),          # 換使用者回合整組歸零
    ("commit_snapshot", "atomic"),                 # 整組換掉、欄位互相綁定：兩邊都改留磁碟那份
    ("anti_evasion_report", "atomic"),
    ("knowledge_harvest.*", "atomic"),             # validated 不能跟 items／pending 拆開
)
_ISO_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def _merge_kind(key: str) -> str:
    return next((kind for pat, kind in _MERGE_TYPES if fnmatch.fnmatchcase(key, pat)), "")


def _merge_state(base: Dict[str, Any], ours: Dict[str, Any], theirs: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """三方合併整份 state（base＝自己的基準、ours＝自己改成的、theirs＝磁碟上現在的），回 (合併結果, 兩邊都改、判不出而留磁碟那份的鍵)。"""
    conflicts: List[str] = []
    out: Dict[str, Any] = {}
    for k in dict.fromkeys([*theirs, *ours, *base]):
        v = _merge3(k, base.get(k, _MISSING), ours.get(k, _MISSING), theirs.get(k, _MISSING), conflicts)
        if v is not _MISSING:
            out[k] = v
    return out, conflicts


def _merge3(key: str, b: Any, o: Any, t: Any, conflicts: List[str]) -> Any:
    """一個鍵的三方合併（_MISSING＝沒有這個鍵）。只有一方改 → 取改的那方；兩方都改 → 一方刪、一方改留改的（新的一筆不丟），
    其餘照 _MERGE_TYPES 與值的型別。兩邊改成同一個值不算沒衝突（各自 +1 長得一樣）：累加型照加，物件與清單照樣往下併。"""
    if key == _PENDING_APPLIED_KEY:              # 併過帳名不是業務欄位：兩邊都留（任一邊記過就不再套）
        return list(dict.fromkeys([*(t if isinstance(t, list) else []), *(o if isinstance(o, list) else [])]))
    if o == b:
        return t
    if t == b:
        return o
    if o is _MISSING or t is _MISSING:
        return t if o is _MISSING else o
    kind = _merge_kind(key)
    nums = all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (o, t))
    if kind == "add" and nums:
        bn = b if isinstance(b, (int, float)) and not isinstance(b, bool) else 0
        if o >= bn and t >= bn:
            return t + o - bn
        if o != t:
            conflicts.append(key)
        return min(o, t)
    if o == t and (kind == "atomic" or not isinstance(o, (dict, list))):
        return o
    if kind == "atomic":
        conflicts.append(key)
        return t
    if kind == "keyed" and isinstance(o, list) and isinstance(t, list):
        return _merge_keyed(key, b if isinstance(b, list) else [], o, t, conflicts)
    if kind.startswith("version:") and isinstance(o, dict) and isinstance(t, dict):
        field = kind.split(":", 1)[1]
        vo, vt = o.get(field), t.get(field)
        if vo != vt:
            try:
                return o if vo > vt else t
            except TypeError:
                pass
    if isinstance(o, dict) and isinstance(t, dict):
        bd = b if isinstance(b, dict) else {}
        out = {}
        for k in dict.fromkeys([*t, *o, *bd]):
            v = _merge3(f"{key}.{k}", bd.get(k, _MISSING), o.get(k, _MISSING), t.get(k, _MISSING), conflicts)
            if v is not _MISSING:
                out[k] = v
        return out
    if isinstance(o, list) and isinstance(t, list):
        return _merge_list(b if isinstance(b, list) else [], o, t)
    if nums:
        return max(o, t)
    if isinstance(o, str) and isinstance(t, str) and _ISO_TIME_RE.match(o) and _ISO_TIME_RE.match(t):
        return max(o, t)
    conflicts.append(key)
    return t


def _item_key(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def _merge_list(b: List[Any], o: List[Any], t: List[Any]) -> List[Any]:
    """集合取聯集：照磁碟那份的順序，拿掉自己刪掉的（讀到時有、自己改成沒有），補上自己新加的（讀到時沒有、磁碟也沒有）。
    截斷長度交給下一次寫入時各欄位自己的上限。"""
    bk, ok = {_item_key(x) for x in b}, {_item_key(x) for x in o}
    out = [x for x in t if not (_item_key(x) in bk and _item_key(x) not in ok)]
    seen = {_item_key(x) for x in out}
    for x in o:
        k = _item_key(x)
        if k not in bk and k not in seen:
            out.append(x)
            seen.add(k)
    return out


def _record_key(r: Any) -> Optional[Tuple[str, str]]:
    if not isinstance(r, dict) or not r.get("path"):
        return None
    from wg_release_rules import canon_path
    return canon_path(r["path"]), str(r.get("session_id", ""))


def _with_count(r: Dict[str, Any]) -> Dict[str, Any]:
    """沒有 count 的舊紀錄算 1 次（post_tool_use._upsert_modified 的預設）。"""
    return r if "count" in r else {**r, "count": 1}


def _merge_keyed(key: str, b: List[Any], o: List[Any], t: List[Any], conflicts: List[str]) -> List[Any]:
    """業務鍵紀錄清單（modified_files）：同一個 (canon 路徑, session_id) 的紀錄逐欄三方合併（count 相加），
    沒有業務鍵的照集合聯集；順序照磁碟那份，自己新加的接在後面。"""
    bm = {k: _with_count(r) for r in b if (k := _record_key(r))}
    om = {k: _with_count(r) for r in o if (k := _record_key(r))}
    tm = {k: _with_count(r) for r in t if (k := _record_key(r))}
    out = []
    for k in dict.fromkeys([*tm, *om]):
        v = _merge3(f"{key}[]", bm.get(k, _MISSING), om.get(k, _MISSING), tm.get(k, _MISSING), conflicts)
        if v is not _MISSING:
            out.append(v)
    return out + _merge_list([r for r in b if not _record_key(r)], [r for r in o if not _record_key(r)],
                             [r for r in t if not _record_key(r)])


def new_state(session_id: str, cwd: str, source: str) -> Dict[str, Any]:
    return {
        "schema_version": "1.1",
        "session": {
            "id": session_id,
            "started_at": _now_iso(),
            "cwd": cwd,
            "source": source,
        },
        "phase": "init",
        "modified_files": [],
        "accessed_files": [],
        "vcs_queries": [],
        "knowledge_queue": [],
        "sync_pending": False,
        "stop_blocked_count": 0,
        "topic_tracker": {
            "intent_distribution": {},
            "prompt_count": 0,
            "first_prompt_summary": "",
            "keyword_signals": [],
            "related_episodic": [],
        },
        "session_context_injected": False,
        "last_updated": _now_iso(),
    }


def _find_active_sibling_state(
    cwd: str, current_session_id: str, window_seconds: int = 60
) -> Optional[Dict[str, Any]]:
    """SessionStart 去重：同 cwd + 近期活躍的兄弟 state。挑中的那份用 read_state_status 重讀（hook 模式下拿它的鎖、
    記下基準），之後寫回兄弟的 state 才有三方合併的基準、不整份覆蓋（規則 STATE_RMW_LOCKED）；重讀後已不是 working 或已被合併
    → 不認領（回 None）；重讀不到 → 用掃描時那份當基準。"""
    try:
        norm_cwd = cwd.lower().replace("\\", "/")
        best: Optional[Dict[str, Any]] = None
        best_fp: Optional[Path] = None
        best_text = ""
        best_mtime: float = 0.0
        now = datetime.now(timezone.utc).astimezone()

        for fp in WORKFLOW_DIR.glob("state-*.json"):
            if current_session_id in fp.name:
                continue
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    text = f.read()
                candidate = json.loads(text)
            except (json.JSONDecodeError, OSError):
                continue

            candidate_cwd = candidate.get("session", {}).get("cwd", "")
            if candidate_cwd.lower().replace("\\", "/") != norm_cwd:
                continue

            if candidate.get("phase") != "working":
                continue
            if candidate.get("merged_into"):
                continue

            started_at_str = candidate.get("session", {}).get("started_at", "")
            if not started_at_str:
                continue
            try:
                started_at = datetime.fromisoformat(started_at_str)
                delta = (now - started_at).total_seconds()
                if delta < 0 or delta > window_seconds:
                    continue
            except (ValueError, TypeError):
                continue

            mtime = fp.stat().st_mtime
            if mtime > best_mtime:
                best, best_fp, best_text = candidate, fp, text
                best_mtime = mtime

        if best_fp is not None:
            fresh, status = read_state_status(best_fp.stem[len("state-"):])
            if status != "ok" or not isinstance(fresh, dict):
                _remember(best_fp, best_text, None)      # 重讀不到：用掃描時讀到的那份當基準，寫回時照三方合併、不整份覆蓋
                return best
            if fresh.get("phase") != "working" or fresh.get("merged_into"):
                return None                               # 等鎖期間它收尾或被合併了：不再認領
            return fresh
        return best
    except Exception as e:
        _atom_debug_error("state:sibling_scan", e)
        return None


def _rebuild_min_atom_index(cwd: str) -> Dict[str, Any]:
    """Fallback state 用最小 atom_index 重建（SessionStart 完整版的廉價子集）。

    復用 session_start 同一套原料：parse_memory_index(global) + realm 過濾 +
    專案層 index。不含 V4 role sublayer / AIDocs（那些需要 role bootstrap，
    fallback 場景成本不划算）。失敗回 {}（caller 保持無 index、advisory 仍浮出）。
    """
    try:
        from wg_atoms import parse_memory_index  # lazy：避免模組層循環 import
        global_atoms = parse_memory_index(MEMORY_DIR)
        if is_local_realm_path is not None and not _is_under_claude_dir(cwd):
            global_atoms = [
                (n, p, t) for (n, p, t) in global_atoms
                if not is_local_realm_path(p) or is_cross_project_local(p)
            ]
        project_mem_dir = get_project_memory_dir(cwd)
        project_atoms = parse_memory_index(project_mem_dir) if project_mem_dir else []
        project_root = find_project_root(cwd)
        return {
            "global": [(n, p, t) for n, p, t in global_atoms],
            "project": [(n, p, t) for n, p, t in project_atoms],
            "project_memory_dir": str(project_mem_dir) if project_mem_dir else "",
            "project_root": str(project_root) if project_root else "",
        }
    except Exception as e:
        _atom_debug_error("state:min_index_rebuild", e)
        return {}


def _ensure_state(
    session_id: str, input_data: Dict[str, Any], config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Read state; if missing (SessionStart was skipped), auto-create one.

    讀取失敗（檔在、但 JSON 壞或被另一支 hook 短暫鎖住）≠ 遺失：重試三次，仍失敗就**這一次
    hook 呼叫放棄**（回 None，呼叫端 output_nothing），絕不建 fallback 覆蓋既有 state。
    多支 sub-agent 與主 session 共用同一 session_id、同時跑 PostToolUse 時最容易撞到。"""
    state, status = read_state_status(session_id)
    if status == "error":
        for _ in range(3):
            time.sleep(0.03)
            state, status = read_state_status(session_id)
            if status != "error":
                break
        if status == "error":
            _atom_debug_log(
                "ERROR",
                f"[state:unreadable] {session_id[:12]}… state 檔存在但讀不到（鎖住或 JSON 壞），"
                "本次 hook 跳過、不建 fallback 覆蓋",
                config,
            )
            return None
    if state:
        merged_into = state.get("merged_into")
        if merged_into:
            target = read_state(merged_into)
            if target:
                return target
            state.pop("merged_into", None)
            state["phase"] = "working"
            write_state(session_id, state)
            _atom_debug_log(
                "MergeSelfHeal",
                f"{session_id[:12]}… merged_into={merged_into[:12]}… target missing "
                f"→ self-heal to active",
                config,
            )
        return state

    cwd = input_data.get("cwd", "")

    sibling = _find_active_sibling_state(cwd, session_id, window_seconds=86400)
    if sibling:
        real_id = sibling.get("session", {}).get("id", "")
        _atom_debug_log(
            "Fallback→Sibling",
            f"{session_id[:12]}… → existing {real_id[:12] if real_id else '?'}…",
            config,
        )
        return sibling

    state = new_state(session_id, cwd, "fallback")
    state["phase"] = "working"
    # 無 atom_index 的 fallback state 會讓本 session 餘生 trigger/BM25 全空——
    # 重建最小 index + 標 advisory（UPS 消費注入一行，可觀測性鐵律：不得靜默降級）。
    min_index = _rebuild_min_atom_index(cwd)
    if min_index:
        state["atom_index"] = min_index
    state["_fallback_state_rebuilt"] = True
    write_state(session_id, state)
    if state.get("merged_into"):                  # 鎖裡發現檔已在、改用磁碟那份，而它是轉址 stub：照一般路徑跟到目標
        target = read_state(str(state["merged_into"]))
        if target:
            return target
    _atom_debug_log(
        "Fallback",
        f"SessionStart missed for {session_id[:12]}… — auto-created state "
        f"(min atom_index: global={len(min_index.get('global', []))} "
        f"project={len(min_index.get('project', []))})",
        config,
    )
    return state


# ─── Output Helpers ──────────────────────────────────────────────────────────


def output_json(data: Dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False))
    sys.exit(0)


def output_nothing() -> None:
    sys.exit(0)


def output_block(reason: str) -> None:
    output_json({"decision": "block", "reason": reason})


# ─── Promotion Audit Log ─────────────────────────────────────────────────────


def log_promotion_audit(action: str, atom: str, **fields: Any) -> None:
    """Append one JSONL entry to memory/_promotion_audit.jsonl."""
    try:
        entry = {"ts": datetime.now().isoformat(timespec="seconds"),
                 "action": action, "atom": atom}
        entry.update(fields)
        audit_path = MEMORY_DIR / "_promotion_audit.jsonl"
        with open(audit_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        _atom_debug_error("promotion:audit_append", e)


def log_promotion_heartbeat(scanned: int, min_gap_hours: float = 20.0) -> None:
    """晉升掃描完成但無事件時落一筆 heartbeat（尾筆距今 < min_gap_hours 則跳過）。

    週健檢鮮度檢查以 _promotion_audit.jsonl 最後一筆 ts 判斷管線死活；
    沒有 heartbeat 時「長期無晉升事件」與「管線靜默停擺」不可分（誤報紅燈）。
    節流讓 audit 檔不被 heartbeat 洗版：正常使用約每日一筆。"""
    try:
        p = MEMORY_DIR / "_promotion_audit.jsonl"
        try:
            with open(p, "rb") as f:
                f.seek(max(0, p.stat().st_size - 4096))
                lines = f.read().decode("utf-8", errors="replace").strip().splitlines()
            for line in reversed(lines):
                try:
                    last = datetime.fromisoformat(json.loads(line)["ts"])
                except (ValueError, KeyError):
                    continue
                if (datetime.now() - last).total_seconds() < min_gap_hours * 3600:
                    return
                break
        except OSError:
            pass  # 檔不存在 → 首筆 heartbeat 直接寫
        log_promotion_audit("heartbeat", "-", scanned=scanned)
    except Exception as e:
        _atom_debug_error("promotion:heartbeat", e)


# ─── Guard Trigger Log（可觀測性：各護欄觸發計數 JSONL）─────────────────────

_DEFAULT_LOGS_DIR = CLAUDE_DIR / "Logs"
GUARD_LOG_DIR = _DEFAULT_LOGS_DIR


def logs_dir() -> Path:
    """正式 Logs/ 目錄；pytest 內（PYTEST_CURRENT_TEST）或 WG_TEST_LOGS_DIR 指定時改寫到
    暫存目錄——測試 fixture 曾把 session_id="sid" 的假資料寫進正式 guard log，污染遙測統計。
    測試以 monkeypatch 改 GUARD_LOG_DIR 時（≠ 預設）尊重該值。"""
    if GUARD_LOG_DIR != _DEFAULT_LOGS_DIR:
        return GUARD_LOG_DIR
    override = os.environ.get("WG_TEST_LOGS_DIR")
    if override:
        return Path(override)
    if os.environ.get("PYTEST_CURRENT_TEST"):
        import tempfile
        return Path(tempfile.gettempdir()) / "wg-test-logs"
    return GUARD_LOG_DIR


def append_guard_log(guard: str, payload: Dict[str, Any]) -> None:
    """護欄觸發事件落一行 JSONL 到 Logs/guard-<guard>.jsonl（含時間戳+觸發摘要）。

    用途：量測誤攔率——evasion / docdrift / lang 等 fail-open 護欄過去只進
    stderr（不可稽核），本 log 供事後統計觸發頻率與內容分布。
    每護欄獨立檔＝多 Stop hook 並行時無同檔競寫。fail-open。"""
    try:
        log_dir = logs_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"guard-{guard}.jsonl"
        rotate_log_if_oversized(log_path, max_mb=5, keep=2)
        entry = {"at": _now_iso()}
        entry.update(payload)
        with open(log_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        _atom_debug_error(f"guard_log:{guard}", e)


# ─── 宣告閘擋次上限（定位閘、最小地圖、動資料檔、改舊測試、不是繞閘共用）───────────
DECL_DENY_CAP = 2                     # 同一個使用者回合、同一道閘、同一件缺件最多擋幾則回覆；再來就放行、由呼叫端留帳
_DECL_DENY_KEY = "decl_deny_counts"   # state：{"turn": 使用者回合, "counts": {"<閘>|<缺件>": 已擋則數}, "batch": {同鍵: 上次算次的那則}}


def deny_cap(state: Optional[Dict[str, Any]], gate: str, items: List[str],
             cap: int = DECL_DENY_CAP, call: Optional[Dict[str, Any]] = None) -> Tuple[List[str], List[str]]:
    """宣告閘這次缺宣告的每一件（呼叫端給穩定的鍵，例：檔的 canon 路徑）→ (照擋的, 這次起放行的)。
    同一個使用者回合（wg_release_rules.user_turn）裡同一件已經擋滿 cap 次就放行：越過上限那一次回在「放行」裡給呼叫端
    留帳，同回合之後再遇到既不擋也不重回；照擋的各記一次。換回合整份歸零。state 就地改、寫檔由呼叫端；
    state 是 None（沒有 session 可記）照擋、不計次。
    次數照「則」數（規則 DENY_CAP_PER_REPLY）：call＝這次工具呼叫的 hook 輸入（tool_use_id、transcript_path、agent_id、session_id），
    跟這一件上一次算次的呼叫是同一則回覆平行送出的（批次鍵同 CHAIN_SAME_BATCH，lib/chain_store.batch_of）→ 照那一次的結果
    （那次擋就照擋）、不加次數；判不出是哪一則（子代理、transcript 讀不到…）照每個呼叫算，留帳 guard-deny_cap event=batch_unknown。
    call 沒給照每個呼叫算、不留帳。"""
    if state is None:
        return list(items), []
    from wg_release_rules import user_turn
    turn = user_turn(state, int(state.get("turn_seq", 0) or 0))
    book = state.get(_DECL_DENY_KEY)
    if not isinstance(book, dict) or book.get("turn") != turn or not isinstance(book.get("counts"), dict):
        book = state[_DECL_DENY_KEY] = {"turn": turn, "counts": {}}
    if not isinstance(book.get("batch"), dict):
        book["batch"] = {}
    batch = ""
    if call is not None and items:
        try:
            from chain_store import batch_of
            batch, why = batch_of(call)
        except Exception as e:  # noqa: BLE001  判不出批次只是退回照每個呼叫算，不能讓閘跟著壞
            why = f"{type(e).__name__}: {e}"
        if not batch:
            append_guard_log("deny_cap", {"event": "batch_unknown", "rule": "DENY_CAP_PER_REPLY", "gate": gate,
                                          "session_id": str(call.get("session_id") or ""), "why": why})
    counts, seen = book["counts"], book["batch"]
    deny: List[str] = []
    released: List[str] = []
    before: Dict[str, Any] = {}
    for item in dict.fromkeys(items):
        key = f"{gate}|{item}"
        n = int(counts.get(key, 0) or 0)
        if batch and n and seen.get(key) == batch:   # 同一則回覆裡這一件已經算過：照那一次（≤cap＝那次擋），不加次數
            if n <= cap:
                deny.append(item)
            continue
        if n < cap:
            deny.append(item)
        elif n == cap:
            released.append(item)
        before[key] = seen.get(key)
        counts[key] = n + 1 if n <= cap else n
        seen[key] = batch
    if deny:                          # 這次照擋：放行的那幾件不算越過上限（整條還是被擋），留到下一次再放；也不算這一則算過它
        for item in released:
            key = f"{gate}|{item}"
            counts[key] = cap
            if before[key] is None:
                seen.pop(key, None)
            else:
                seen[key] = before[key]
        released = []
    return deny, released


# ─── Atom Debug Log ──────────────────────────────────────────────────────────


def _atom_debug_log(tag: str, content: str, config: Dict[str, Any] = None) -> None:
    """Write to atom-debug.log when atom_debug flag is on. ERROR always writes."""
    if tag != "ERROR" and not (config or {}).get("atom_debug", False):
        return
    if not content or not content.strip():
        return
    try:
        log_dir = logs_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"atom-debug-{datetime.now().strftime('%Y-%m-%d_%H')}.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(f"[{ts}][{tag}] {content.strip()}\n\n")
    except Exception:
        pass


def _atom_debug_error(source: str, exc: Exception) -> None:
    """Log error with source context. Network errors get one-line summary."""
    if isinstance(exc, (TimeoutError, OSError, ConnectionError)):
        msg = f"{type(exc).__name__}: {exc}"
    else:
        import traceback
        msg = traceback.format_exc()
        if "NoneType" in msg:
            msg = f"{type(exc).__name__}: {exc}"
    _atom_debug_log("ERROR", f"[{source}] {msg}", {"atom_debug": True})


# ─── PreToolUse Path / Command Guards (was wg_pretool_guards.py) ─────────────

_PROJECT_MEMORY_PATH_RE = lazy_re(
    r"[/\\]\.claude[/\\]projects[/\\](?!_)[^/\\]+[/\\]memory[/\\]",
    re.IGNORECASE,
)
_NESTED_PROJECTS_RE = lazy_re(
    r"[/\\]\.claude[/\\]projects[/\\][^/\\]+[/\\]projects[/\\][^/\\]+[/\\]memory[/\\]",
    re.IGNORECASE,
)
_DOUBLE_CLAUDE_RE = lazy_re(
    r"[/\\]\.claude[/\\]\.claude[/\\]memory[/\\]",
    re.IGNORECASE,
)

_WHITELIST_BASENAMES = frozenset({
    "MEMORY.md", "_ATOM_INDEX.md", "_CHANGELOG.md", "_CHANGELOG_ARCHIVE.md",
    "_roles.md", "atom_io_audit.jsonl",
    "_promotion_audit.jsonl", "project-registry.json", "session_score.json",
    "DESIGN.md", "role.md",
})
if atom_writable_dir_segments is not None:
    _WHITELIST_DIR_SEGMENTS = atom_writable_dir_segments()
else:
    # Fallback（lib import 失敗的極端情況；與 atom_locations 保持一致）。
    # 不含 'Failures'：Failures atom 由 _is_failures_atom_path 主動 gate，非白名單豁免。
    _WHITELIST_DIR_SEGMENTS = frozenset({
        "_meta", "_staging", "_archived", "_distant", "_reference", "_pending_review",
        "_vectordb", "_rejected", "templates", "episodic", "wisdom", "personal",
    })


def _path_under_memory_dir(fp: Path) -> bool:
    parts = [p.lower() for p in fp.parts]
    for i in range(len(parts) - 1):
        if parts[i] == ".claude" and parts[i + 1] == "memory":
            return True
    return False


def _atom_path_whitelisted(fp: Path) -> bool:
    """memory 樹內的豁免判定：只看 `memory` 段**之後**的目錄段是否命中白名單。

    上層目錄名不參與比對——`<proj>/templates/.claude/memory/x.md` 這種「外層資料夾剛好叫
    templates」不得讓整棵 memory 樹被豁免。範疇資料夾（memory/<範疇>/…）不在白名單，
    照常走 funnel。
    """
    if fp.name in _WHITELIST_BASENAMES:
        return True
    if fp.name.startswith("_") or fp.name.startswith("SPEC_"):
        return True
    parts_lower = [p.lower() for p in fp.parts]
    try:
        start = parts_lower.index("memory") + 1
    except ValueError:
        start = 0
    inner = set(parts_lower[start:-1])  # memory 之後、檔名之前的目錄段
    if inner & _WHITELIST_DIR_SEGMENTS:
        return True
    return False


def _is_failures_atom_path(fp: Path) -> bool:
    """fp 是否為失敗家族目錄下「已註冊的 atom」(.md)。

    失敗家族有兩個家：新址 `memory/Failures/[<主題>/]`（在 memory 樹下，上游
    _path_under_memory_dir 本就會攔）與舊址 `_AIDocs/Failures/`（樹外，讀端相容期間仍需
    本函式補攔，否則 feedback-* / cognitive-patterns / memory-pipeline-* 直接 Write/Edit
    會繞過 funnel + audit）。

    目錄內混居「註冊 atom」與「參考文件」（env-traps / silent-failures / _INDEX.md…
    未進 index，不可誤擋），故以 failures_atom_stems()（index SoT）精準比對 stem。

    failures_atom_stems 在 lib import 失敗時為 None → 退化為「不攔」。
    """
    if failures_atom_stems is None or fp.suffix != ".md":
        return False
    parts_lower = [p.lower() for p in fp.parts]
    for i in range(len(parts_lower) - 1):
        if parts_lower[i] in ("_aidocs", "memory") and parts_lower[i + 1] == "failures":
            break
    else:
        return False
    try:
        return fp.stem in failures_atom_stems()
    except Exception as e:
        _atom_debug_error("guard:failures_atom_path", e)
        return False


def check_memory_path_block(
    tool_name: str, tool_input: Dict[str, Any]
) -> Optional[str]:
    """阻擋三類 memory 違規寫入：projects/{slug}/memory / 雙層 .claude / atom 直 Write。"""
    if tool_name not in ("Write", "Edit"):
        return None
    fp_str = tool_input.get("file_path", "") or ""
    if not fp_str:
        return None

    if _PROJECT_MEMORY_PATH_RE.search(fp_str) or _NESTED_PROJECTS_RE.search(fp_str):
        return (
            "[Guardian:MemoryPathBlock] 禁止寫入 `~/.claude/projects/{slug}/memory/`。"
            "原子記憶專案自治層已覆寫此路徑。\n"
            "正確做法：(1) 全域記憶 → 用 MCP `atom_write` (scope=global) 寫到 "
            "~/.claude/memory/；(2) 專案記憶 → 用 MCP `atom_write` "
            "(scope=shared/role/personal) 寫到 {project_root}/.claude/memory/。\n"
            "詳見 atom [[feedback-memory-system-doc-sync]]。"
        )

    if _DOUBLE_CLAUDE_RE.search(fp_str):
        return (
            "[Guardian:DoubleClaudeBlock] 禁止寫入 `~/.claude/.claude/memory/` 雙層路徑。"
            "這是雙層 bug 的殘骸 — 應寫到 `~/.claude/memory/`。"
        )

    if os.environ.get("WG_DISABLE_ATOM_GUARD") == "1":
        return None
    fp = Path(fp_str)
    # memory/ 樹下 atom（含 memory/Failures/），或舊址 _AIDocs/Failures/ 下「註冊 atom」
    # 皆須走 funnel；後者不在 memory 樹下，需 _is_failures_atom_path 補攔。
    if not _path_under_memory_dir(fp) and not _is_failures_atom_path(fp):
        return None
    if fp.suffix != ".md":
        return None
    if _atom_path_whitelisted(fp):
        return None
    return (
        "[Guardian:AtomFunnelBlock] 直接 Write/Edit atom .md 不走 funnel 被禁止。\n"
        f"路徑：{fp_str}\n"
        "正確做法：\n"
        "  (1) 用 MCP `atom_write` / `atom_promote` / `atom_move` 工具；\n"
        "      只改 Trigger/Related/Tags 元資料 → `atom_edit_meta`（外科編輯，byte-stable）\n"
        "  (2) 程式碼端：知識內容寫 lib.atom_io.write_atom() / write_raw() / edit_metadata()；\n"
        "      計數欄位（read_hits / last_used / confirmations）寫 lib.atom_access\n"
        "緊急 bypass：set 環境變數 `WG_DISABLE_ATOM_GUARD=1` 後重試。"
    )


# ─── Cross-Realm Write Guard ──────────────
# 守門對象：~/.claude 核心層（skills/tools/hooks/lib/rules 子目錄 + 根層敏感檔
# settings.json/CLAUDE.md/IDENTITY*.md/USER*.md）+ Bash `claude mcp add/remove`
# 全域 scope 操作。判別子＝session cwd：外部專案 session → deny（跨層污染
# 教訓）；~/.claude 自身的開發 session 完全不受影響。deterministic、零 LLM。

_CORE_GUARDED_SUBDIRS = ("skills", "tools", "hooks", "lib", "rules")
_CORE_GUARDED_ROOT_FILES = ("settings.json", "claude.md", "user.md")  # lower
_MCP_MUTATE_RE = lazy_re(
    r"\bclaude(?:\.exe|\.cmd)?\s+mcp\s+(add(?:-json|-from-claude-desktop)?|remove)\b",
    re.IGNORECASE,
)
_MCP_SCOPE_USER_RE = lazy_re(r"(?:-s|--scope)[\s=]+user\b", re.IGNORECASE)
_MCP_SCOPE_PROJECT_LOCAL_RE = lazy_re(
    r"(?:-s|--scope)[\s=]+(?:project|local)\b", re.IGNORECASE)


def _is_core_session(cwd: str) -> Optional[bool]:
    """cwd 是否落在資料根（CLAUDE_DIR，一般安裝就是 ~/.claude）下。None＝無法判定（caller fail-open）。"""
    if not cwd:
        return None
    home_claude = CLAUDE_DIR.resolve()
    try:
        cwd_p = Path(cwd).resolve()
    except (OSError, ValueError):
        return None
    return cwd_p == home_claude or home_claude in cwd_p.parents


def _is_root_sensitive_name(name_lower: str) -> bool:
    return (
        name_lower in _CORE_GUARDED_ROOT_FILES
        or (name_lower.startswith("identity") and name_lower.endswith(".md"))
        or (name_lower.startswith("user-") and name_lower.endswith(".md"))
    )


def check_cross_realm_write(
    tool_name: str, tool_input: Dict[str, Any], cwd: str,
    config: Dict[str, Any],
) -> Optional[str]:
    """外部專案 session 寫入 ~/.claude 核心層 → deny。cwd 缺失 fail-open。"""
    if tool_name not in ("Write", "Edit", "NotebookEdit"):
        return None
    g = (config.get("guard") or {}).get("cross_realm_write") or {}
    if not g.get("enabled", True):
        return None
    # NotebookEdit 的路徑欄位是 notebook_path
    fp_str = tool_input.get("file_path", "") or tool_input.get("notebook_path", "") or ""
    if not fp_str or not cwd:
        return None
    home_claude = CLAUDE_DIR.resolve()
    try:
        fp = Path(fp_str).resolve()
        rel = fp.relative_to(home_claude)
    except (OSError, ValueError):
        return None  # 目標不在 ~/.claude 下 → 與本閘無關
    if not rel.parts:
        return None
    top = rel.parts[0].lower()
    is_core_subdir = top in _CORE_GUARDED_SUBDIRS
    # v1.1 ①：根層敏感檔（settings.json 可注入任意 hook 指令，比 skills 更敏感）
    is_root_sensitive = len(rel.parts) == 1 and _is_root_sensitive_name(top)
    if not is_core_subdir and not is_root_sensitive:
        return None
    if _is_core_session(cwd) is not False:
        return None  # 核心開發 session 放行；無法判定 → fail-open
    fp_norm = str(fp).replace("\\", "/").lower()
    for pat in g.get("allowlist", []) or []:
        if pat and str(pat).replace("\\", "/").lower() in fp_norm:
            return None
    target_desc = (
        f"~/.claude/{rel.parts[0]}/" if is_core_subdir
        else f"核心根層敏感檔 ~/.claude/{rel.parts[0]}"
    )
    return (
        f"[Guardian:CrossRealmWriteBlock] 偵測到外部專案 session 寫入核心層 "
        f"{target_desc}。\n"
        f"路徑：{fp_str}\n"
        f"session cwd：{cwd}\n"
        "核心層（skills/tools/hooks/lib/rules + settings.json/CLAUDE.md/"
        "IDENTITY*.md/USER*.md）只接受 ~/.claude session 的修改。\n"
        "正確做法：\n"
        "  (1) 專案專屬 skill/tool → 寫到 {專案根}/.claude/skills/ 或 "
        ".claude/tools/（Claude Code 原生支援專案層疊加）\n"
        "  (2) 暫存產物（截圖/log/dump）→ 寫到專案目錄或系統 temp\n"
        "  (3) user 明確要求改核心層 → 請在 ~/.claude 開 session 操作，或於 "
        "workflow/config.json guard.cross_realm_write.allowlist 加入路徑"
    )


# ─── 跨層 Bash 寫入閘 ─────────────────────────────────────────────────────────
# CrossRealmWriteBlock 只看 Write/Edit/NotebookEdit；實證（2026-09-01）專案 session 以
# `cd ~/.claude && python - <<EOF … write_text` 改根層 hooks、再 `git add && git commit`，
# 整條沒被看到。這裡補 Bash/PowerShell：根層上下文（cd 進 ~/.claude、git -C、或命令列直接
# 指到核心路徑）× 會動手的操作（heredoc／內嵌 python／redirect／sed -i／cp mv rm／
# git add commit push…／PowerShell 寫入 cmdlet）→ deny。純跑根層工具
# （`python ~/.claude/tools/x.py …`，不 cd 進去）與唯讀命令照常放行。
# 「跑根層工具」不構成根層上下文：判定前先把 `python <root>/.claude/tools|hooks|lib|skills/x.py`
# 這段抹掉，剩下的命令再找根層路徑。否則專案 session 一條命令裡同時「跑根層索引工具」＋
# 「用 python/cp/rm/git 動自己專案的 .claude/memory」會被當成改根層而誤擋。
_ROOT_CORE_SUBDIRS_RE = r"(?:hooks|lib|tools|skills|rules|prompts)"
_ROOT_SENSITIVE_FILES_RE = r"(?:settings\.json|CLAUDE\.md|IDENTITY[^/\\\s]*\.md|USER[^/\\\s]*\.md|TECH\.md|README\.md|Install[^/\\\s]*\.md)"
_ROOT_HOME_RE = r"(?:~|\$HOME|\$\{HOME\}|%USERPROFILE%|\$env:USERPROFILE|/[a-zA-Z]/Users/[^/\s\"']+|[a-zA-Z]:[\\/]Users[\\/][^\\/\s\"']+)"
_ROOT_CD_RE = lazy_re(
    rf"(?:\bcd\s+|\bgit\s+-C\s+|\bSet-Location\s+|\bpushd\s+)[\"']?{_ROOT_HOME_RE}[\\/]\.claude(?:[\\/]{_ROOT_CORE_SUBDIRS_RE})?[\\/]?[\"']?(?=\s|;|&&|\|\||$)",
    re.IGNORECASE,
)
# 核心子目錄後面不必接斜線：`TEMP=~/.claude/hooks;`、`cp a.py ~/.claude/hooks` 也是根層（hooks.bak、hooks-old 不算）
_ROOT_CORE_PATH_RE = lazy_re(
    rf"{_ROOT_HOME_RE}[\\/]\.claude[\\/](?:{_ROOT_CORE_SUBDIRS_RE}(?![\w.-])|{_ROOT_SENSITIVE_FILES_RE}\b)",
    re.IGNORECASE,
)
_ROOT_TOOL_INVOKE_RE = lazy_re(
    rf"\b(?:python3?|pythonw|py)(?:\.exe)?\s+[\"']?{_ROOT_HOME_RE}[\\/]\.claude[\\/](?:tools|hooks|lib|skills)[\\/][^\s\"']*?\.py[\"']?",
    re.IGNORECASE,
)
# heredoc 是 `<<EOF`／`<<'EOF'`／`<<-EOF`；`<<<`（here-string）與 grep 樣式裡的 `<<<<<<<` 衝突標記不算
_BASH_WRITE_OP_RE = lazy_re(
    r"(?:<<(?!<)-?\s*[\"']?\w|>>|(?<![<>=!])>(?!&?/dev/null|\s*\$null|\s*NUL\b|&\d)|\btee\b|\bsed\s+(?:-[a-zA-Z]*i|--in-place)"
    r"|\b(?:python3?|pythonw|py)(?:\.exe)?\s+-(?:\s|c\b)|\b(?:cp|mv|rm|rmdir|del|erase|copy|move|ren|rename|truncate|install)\b"
    r"|\bgit\s+(?:-C\s+\S+\s+)?(?:add|commit|push|mv|rm|checkout|reset|stash|rebase|cherry-pick|merge|apply|am)\b"
    r"|\b(?:Set-Content|Out-File|Add-Content|Copy-Item|Move-Item|Remove-Item|New-Item|Rename-Item)\b)",
    re.IGNORECASE,
)

# ─── 工具呼叫的寫入目標（OverviewHub 閘逐目標 on_edit；post_tool_use 記改過的檔）─────────
# 對外介面：write_paths_from_tool(tool_name, tool_input, cwd=None) -> List[str]，只回絕對路徑。
# 規則 R0～R5：
#   R0 整條沒有寫入訊號（重導向／寫檔命令／直譯器內嵌碼／子 shell 或替換裡的寫入）一律回 []，不回 UNKNOWN。
#   R1 先接 `\`＋換行續行；剝引號外的 # 註解；heredoc 只認引號外、token 開頭的 <<，本文整段跳過；引號內容是一個 token。
#   R2 `>`／`>>`／`>|`／`&>`／`&>>` 黏連也算；fd 複製（2>&1、>&2）與 /dev/null、$null、NUL 不算目標。
#   R3 寫檔命令表（第一個非 env 賦值 token）：tee／cp／mv／install／rsync／ln／dd of=／touch／mkdir／rm／truncate／
#      sed（旗標含 i，或 expression 的 w 指令）／sort -o／Set-Content／Out-File／Add-Content／Copy-Item／Move-Item／New-Item／Remove-Item；
#      cp 家族目標是目錄（尾 / 或既存目錄、或多來源）→ 目錄/basename(src)。
#   R4 UNKNOWN 只在「有寫入訊號但算不出目標」：目標含展不開的變數（$HOME／~ 除外）、$(…)／反引號／eval 裡含寫入、
#      直譯器內嵌碼（python -c／python -／node -e／pwsh -Command／[IO.File]::／open(…,'w')／fs.writeFile）、
#      cd 之後用 |／|| 接寫入、cd 到變數或 cd - 之後的相對目標。算得出的目標照列、再加一筆 "UNKNOWN:<該段前 40 字>"
#      （UNKNOWN_PART_KEEPS_KNOWN_TARGETS），on_edit 對那一筆照 UNKNOWN_TARGET_LOGGED 放行留帳。
#   R5 `;`／`&&`／換行的 cd 生效到後段；||／| 右側的 cd 不外溢；(…) 子 shell 的 cd 不外溢，裡面的目標照算。
_WRITE_CMDS = frozenset({
    "tee", "cp", "mv", "install", "rsync", "ln", "dd", "touch", "mkdir", "rm", "rmdir", "truncate", "sed", "sort",
    "set-content", "out-file", "add-content", "copy-item", "move-item", "new-item", "remove-item",
    "rename-item", "tee-object",
})
# PowerShell 寫檔 cmdlet 的內建別名（只在 PowerShell 工具下換成正式名；cp／mv／rm 在 Bash 分支已處理）。
# 規則 DELETE_FORMS_SAME_ACROSS_SHELLS：刪除的別名（ri、del、erase、rd、rmdir）跟 Remove-Item 同一條路，不然同一件事換個寫法閘就看不到
_PS_WRITE_ALIASES = {
    "cpi": "copy-item", "copy": "copy-item", "mi": "move-item", "move": "move-item", "ac": "add-content",
    "sc": "set-content", "ni": "new-item", "rni": "rename-item", "ren": "rename-item", "tee": "tee-object",
    "ri": "remove-item", "del": "remove-item", "erase": "remove-item", "rd": "remove-item", "rmdir": "remove-item",
}
_PS_CD_NAMES = frozenset({"set-location", "sl", "chdir", "push-location"})     # PowerShell 換目錄（cd／pushd 跟 Bash 同名）
# 位置參數都是寫入目標的命令，與它們會吃掉下一個字的旗標
_TARGET_VALUE_FLAGS = {
    "touch": frozenset({"-r", "--reference", "-d", "--date", "-t"}), "truncate": frozenset({"-s", "--size", "-r", "--reference"}),
    "mkdir": frozenset({"-m", "--mode"}), "rm": frozenset(), "rmdir": frozenset(),
}
_PS_CD_PATH_PARAMS = frozenset({"-path", "-literalpath"})
_COPY_CMDS = frozenset({"cp", "mv", "install", "rsync", "ln", "copy-item", "move-item"})
_COPY_VALUE_FLAGS = frozenset({"-m", "-o", "-g", "-t", "-e", "--mode", "--owner", "--group", "--target-directory", "--suffix", "-S"})
_PS_VALUE_PARAMS = frozenset({
    "-value", "-encoding", "-itemtype", "-filter", "-include", "-exclude", "-destination", "-path", "-literalpath",
    "-filepath", "-name", "-width", "-stream", "-delimiter", "-newname",
})
_PS_PATH_PARAMS = frozenset({"-path", "-literalpath", "-filepath", "-destination"})
_INTERPRETERS = {
    "python": ("-c", "-"), "python3": ("-c", "-"), "py": ("-c", "-"), "pythonw": ("-c", "-"),
    "node": ("-e", "--eval", "-p", "--print"), "nodejs": ("-e", "--eval", "-p", "--print"),
    "pwsh": ("-command", "-c", "-encodedcommand", "-e", "-ec"), "powershell": ("-command", "-c", "-encodedcommand", "-e", "-ec"),
}
_PY_NAMES = frozenset({"python", "python3", "py", "pythonw"})
_PY_VALUE_OPTS = frozenset({"-X", "-W", "--check-hash-based-pycs"})     # 帶值的直譯器選項：值不是腳本
_NODE_VALUE_OPTS = frozenset({"-r", "--require", "--import", "--loader", "--experimental-loader", "-C", "--conditions",
                              "--env-file", "--input-type", "--title"})
_INLINE_CODE_RE = lazy_re(r"\[(?:System\.)?IO\.(?:File|Directory)\]::|\bopen\([^)]*['\"][wa]\+?['\"]|fs\.write(?:File|FileSync)\b", re.IGNORECASE)
_SED_W_RE = lazy_re(r"(?:^|[;{\n]\s*|/)w\s+(\S+)")
_ENV_ASSIGN_RE = lazy_re(r"^[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPERS = frozenset({"sudo", "exec", "nohup", "command", "builtin", "time"})
_WRITE_TARGET_NULLS = frozenset({"/dev/null", "$null", "nul"})
_WRITE_TARGET_UNKNOWN = "UNKNOWN"
_HEREDOC_TAG_RE = lazy_re(r"^-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


class _Tok:
    """lexer 的一個 token。kind：W（字）／OUT（輸出重導向）／DUP（fd 複製，跳過）／IN（輸入重導向，跳過下一字）／
    SEP（; && || | & 換行）／LP／RP／HD（heredoc 內文，不是指令字；quoted＝定界符加了引號、shell 不展開）。
    W 的 quoted＝任一部分被引號包過；subst＝字裡 $(…) 與反引號的內文；sq_dollar＝單引號裡有 `$`（字面的錢字號，不能代換變數）。"""
    __slots__ = ("kind", "text", "quoted", "subst", "sq_dollar")

    def __init__(self, kind: str, text: str = "", quoted: bool = False, subst: Optional[List[str]] = None,
                 sq_dollar: bool = False) -> None:
        self.kind, self.text, self.quoted, self.subst, self.sq_dollar = kind, text, quoted, subst or [], sq_dollar


def _lex_shell(cmd: str) -> List[_Tok]:
    """R1／R2 的詞法：續行、註解、heredoc、引號、$(…)／反引號、重導向運算子黏連、( ) 子 shell。"""
    cmd = cmd.replace("\\\n", " ")
    toks: List[_Tok] = []
    buf: List[str] = []
    quoted = sq_dollar = False
    subst: List[str] = []
    pending_heredocs: List[str] = []
    depth = 0
    i, n = 0, len(cmd)

    def flush() -> None:
        nonlocal buf, quoted, subst, sq_dollar
        if buf or quoted:
            toks.append(_Tok("W", "".join(buf), quoted, subst, sq_dollar))
        buf, quoted, subst, sq_dollar = [], False, [], False

    def read_subst(start: int, open_ch: str, close_ch: str) -> int:
        """從 start（指在 $( 的 ( 或反引號後）讀到配對結束，回結束位置（含結尾字元）。"""
        lvl = 1
        j = start
        while j < n:
            c = cmd[j]
            if open_ch != "`" and c == open_ch:
                lvl += 1
            elif c == close_ch:
                lvl -= 1
                if lvl == 0:
                    return j
            j += 1
        return n - 1

    while i < n:
        c = cmd[i]
        at_token_start = not buf and not quoted
        if c == "'":
            j = cmd.find("'", i + 1)
            j = n if j < 0 else j
            buf.append(cmd[i + 1:j])
            quoted = True
            sq_dollar = sq_dollar or "$" in cmd[i + 1:j]
            i = j + 1
            continue
        if c == '"':
            j = i + 1
            while j < n and cmd[j] != '"':
                if cmd[j] == "\\" and j + 1 < n and cmd[j + 1] in '"$`\\':   # 雙引號內只有這幾個字元被跳脫；Windows 路徑的 \ 原樣保留
                    buf.append(cmd[j + 1])
                    j += 2
                    continue
                if cmd[j] == "$" and j + 1 < n and cmd[j + 1] == "(":
                    k = read_subst(j + 2, "(", ")")
                    subst.append(cmd[j + 2:k])
                    buf.append(cmd[j:k + 1])
                    j = k + 1
                    continue
                buf.append(cmd[j])
                j += 1
            quoted = True
            i = j + 1
            continue
        if c == "`":
            k = read_subst(i + 1, "`", "`")
            subst.append(cmd[i + 1:k])
            buf.append(cmd[i:k + 1])
            i = k + 1
            continue
        if c == "$" and i + 1 < n and cmd[i + 1] == "(":
            k = read_subst(i + 2, "(", ")")
            subst.append(cmd[i + 2:k])
            buf.append(cmd[i:k + 1])
            i = k + 1
            continue
        if c == "#" and at_token_start:
            j = cmd.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "\n":
            flush()
            if pending_heredocs:
                lines = cmd[i + 1:].split("\n")
                skip = 0
                for tag, ph in pending_heredocs:
                    start = skip
                    while skip < len(lines) and lines[skip].strip() != tag:
                        skip += 1
                    ph.text = "\n".join(lines[start:skip])
                    skip += 1
                pending_heredocs = []
                consumed = sum(len(l) + 1 for l in lines[:skip])
                i += 1 + consumed
                toks.append(_Tok("SEP", "\n"))
                continue
            toks.append(_Tok("SEP", "\n"))
            i += 1
            continue
        if c.isspace():
            flush()
            i += 1
            continue
        if c == ";":
            flush()
            toks.append(_Tok("SEP", ";"))
            i += 1
            continue
        if c == "|":
            flush()
            if i + 1 < n and cmd[i + 1] == "|":
                toks.append(_Tok("SEP", "||"))
                i += 2
            else:
                toks.append(_Tok("SEP", "|"))
                i += 1
            continue
        if c == "&":
            nxt = cmd[i + 1] if i + 1 < n else ""
            if nxt == ">":
                flush()
                if i + 2 < n and cmd[i + 2] == ">":
                    toks.append(_Tok("OUT", "&>>"))
                    i += 3
                else:
                    toks.append(_Tok("OUT", "&>"))
                    i += 2
                continue
            flush()
            if nxt == "&":
                toks.append(_Tok("SEP", "&&"))
                i += 2
            else:
                toks.append(_Tok("SEP", "&"))
                i += 1
            continue
        if c == ">":
            fd_prefix = bool(buf) and not quoted and "".join(buf).isdigit()
            if fd_prefix:
                buf = []
            flush()
            op = ">"
            j = i + 1
            if j < n and cmd[j] == ">":
                op = ">>"
                j += 1
            elif j < n and cmd[j] == "|":
                op = ">|"
                j += 1
            if j < n and cmd[j] == "&":
                k = j + 1
                while k < n and cmd[k].isdigit():
                    k += 1
                if k > j + 1 or (k < n and cmd[k] == "-"):
                    toks.append(_Tok("DUP", cmd[i:k + 1]))
                    i = k + (1 if k < n and cmd[k] == "-" else 0)
                    continue
                j += 1                                  # `>&file`：兩路都導到檔
            toks.append(_Tok("OUT", op))
            i = j
            continue
        if c == "<":
            fd_prefix = bool(buf) and not quoted and "".join(buf).isdigit()
            if fd_prefix:
                buf = []
            j = i + 1
            if j < n and cmd[j] == "<":
                j += 1
                if j < n and cmd[j] == "<":
                    flush()
                    toks.append(_Tok("IN", "<<<"))
                    i = j + 1
                    continue
                if at_token_start or fd_prefix:
                    m = _HEREDOC_TAG_RE.match(cmd[j:])
                    if m:
                        flush()
                        ph = _Tok("HD", "", quoted=bool(m.group(1)))     # heredoc 內文的位子：換行吞內文時填進來
                        toks.append(ph)
                        pending_heredocs.append((m.group(2), ph))
                        i = j + m.end()
                        continue
                flush()
                toks.append(_Tok("IN", "<<"))
                i = j
                continue
            if j < n and cmd[j] == "&":
                flush()
                k = j + 1
                while k < n and cmd[k].isdigit():
                    k += 1
                toks.append(_Tok("DUP", cmd[i:k]))
                i = k
                continue
            flush()
            toks.append(_Tok("IN", "<"))
            i = j
            continue
        if c == "(" and at_token_start:
            toks.append(_Tok("LP"))
            depth += 1
            i += 1
            continue
        if c == ")" and depth > 0:
            flush()
            toks.append(_Tok("RP"))
            depth -= 1
            i += 1
            continue
        buf.append(c)
        i += 1
    flush()
    return toks


class _Scan:
    """一次解析的累積結果：targets（絕對路徑）、signal（有沒有寫入訊號）、unknown（算不出目標的那段文字）、
    sources（cp／mv 家族：目標 → 它的來源絕對路徑）、vars（這條指令裡指定過的字面變數）、
    env（可照 hook 行程環境代換的變數，見 _env_for_expansion）、gits（每段 git：(repo 目錄或 None＝判不出, git 後的參數)）。"""
    __slots__ = ("targets", "signal", "unknown", "ps", "sources", "why", "vars", "env", "gits")

    def __init__(self, ps: bool = False) -> None:
        self.targets: List[str] = []
        self.signal = False
        self.unknown: Optional[str] = None
        self.why = ""                       # 內嵌碼被 ast 判成可能寫檔的原因（擋訊息帶出來，不叫人亂改寫法）
        self.ps = ps                        # PowerShell 工具：寫檔 cmdlet 的別名才生效（Bash 下 sc 是 sc.exe，不是 Set-Content）
        self.sources: Dict[str, List[str]] = {}
        self.vars: Dict[str, str] = {}       # 規則 SHELL_LITERAL_VAR_EXPANDED：`S='字面' &&` 之後的 $S／${S} 代換成字面
        self.env: Dict[str, str] = {}        # 規則 SHELL_ENV_VAR_EXPANDED：沒碰過的 $TEMP 這類照環境值代換；空＝不代換
        self.gits: List[Tuple[Optional[str], List[str]]] = []


def _write_target_abs(tok: str, cwd: Optional[str]) -> Optional[str]:
    """目標 token → 絕對路徑；fd／空裝置／旗標回 None；展不開的變數、或 cwd 不確定時的相對路徑回 "UNKNOWN"。MSYS `/c/x` 轉 `C:/x`。"""
    tok = tok.strip()
    if not tok or tok.startswith(("&", "-")) or tok.lower() in _WRITE_TARGET_NULLS:
        return None
    home = str(Path.home())
    tok = tok.replace("${HOME}", home).replace("$HOME", home)
    if tok.startswith("~"):
        tok = os.path.expanduser(tok)
    if "$" in tok or "%" in tok or "`" in tok:
        return _WRITE_TARGET_UNKNOWN
    m = re.match(r"^/([A-Za-z])/(.*)$", tok)
    if m:
        tok = f"{m.group(1).upper()}:/{m.group(2)}"
    if not (re.match(r"^[A-Za-z]:[\\/]", tok) or tok.startswith(("/", "\\\\"))):
        if cwd is None:
            return _WRITE_TARGET_UNKNOWN
        tok = os.path.join(cwd, tok)
    return os.path.normpath(tok)


def _copy_targets(srcs: List[str], dst: str, cwd: Optional[str]) -> List[Optional[str]]:
    """cp 家族：目標以 / 結尾、是既存目錄、或來源多於一個 → 目錄/來源檔名；否則就是那個檔。"""
    d = _write_target_abs(dst, cwd)
    if d is None or d == _WRITE_TARGET_UNKNOWN:
        return [d]
    if dst.endswith(("/", "\\")) or os.path.isdir(d) or len(srcs) > 1:
        return [os.path.join(d, os.path.basename(s.rstrip("/\\"))) for s in srcs]
    return [d]


def _sed_targets(args: List[str]) -> Tuple[bool, List[str], List[str]]:
    """sed 參數 → (就地改, 檔案清單, expression 裡 w 指令寫的檔)。短旗標串：i 在 e／f 之前才算 -i（-es/i/x/ 的 i 是 expression）。"""
    inplace = False
    scripts: List[str] = []
    files: List[str] = []
    skip = False
    for a in args:
        if skip:
            scripts.append(a)
            skip = False
            continue
        if a.startswith("--"):
            if a == "--in-place" or a.startswith("--in-place="):
                inplace = True
            elif a.startswith(("--expression=", "--file=")):
                scripts.append(a.split("=", 1)[1])
            elif a in ("--expression", "--file"):
                skip = True
            continue
        if a.startswith("-") and len(a) > 1:
            for idx, ch in enumerate(a[1:]):
                if ch == "i":
                    inplace = True
                    break
                if ch in "ef":
                    rest = a[idx + 2:]
                    if rest:
                        scripts.append(rest)
                    else:
                        skip = True
                    break
            continue
        files.append(a)
    if not scripts and files:
        scripts, files = [files[0]], files[1:]
    w_files = [m.group(1) for s in scripts for m in _SED_W_RE.finditer(s)]
    return inplace, files, w_files


def _ps_targets(name: str, args: List[str]) -> List[str]:
    """PowerShell 寫檔 cmdlet 的目標：-Path／-LiteralPath／-FilePath／-Destination，否則位置參數（Copy／Move 取第二個，其餘第一個）。"""
    named: Dict[str, str] = {}
    positional: List[str] = []
    j = 0
    while j < len(args):
        a = args[j]
        low = a.lower()
        if a.startswith("-"):
            if low in _PS_VALUE_PARAMS and j + 1 < len(args):
                named[low] = args[j + 1]
                j += 2
            else:
                j += 1
            continue
        positional.append(a)
        j += 1
    if name in ("copy-item", "move-item"):
        dst = named.get("-destination") or (positional[1] if len(positional) > 1 else "")
        src = named.get("-path") or named.get("-literalpath") or (positional[0] if positional else "")
        return [f"{dst}\x00{src}"] if dst else []
    if name == "rename-item":                        # 舊路徑與改名後的新路徑都是目標（新名字落在舊路徑的同一個目錄）
        src_named = named.get("-path") or named.get("-literalpath")
        src = src_named or (positional[0] if positional else "")
        rest = positional if src_named else positional[1:]          # 來源已具名綁定：新名字是第一個位置參數
        new = named.get("-newname") or (rest[0] if rest else "")
        if src and new:
            return [src, os.path.join(os.path.dirname(src.rstrip("/\\")), os.path.basename(new.rstrip("/\\")))]
        return [src] if src else []
    for key in ("-path", "-literalpath", "-filepath"):
        if key in named:
            path = named[key]
            return [os.path.join(path, named["-name"]) if name == "new-item" and "-name" in named else path]
    return positional[:1]


def _scan_tokens(toks: List[_Tok], cwd: Optional[str], out: _Scan) -> Optional[str]:
    """逐段掃 token（R3／R4／R5）；回最後的 cwd（None＝不確定）。子 shell 遞迴、不外溢 cwd。"""
    seg: List[_Tok] = []
    prev_sep = ""
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.kind == "LP":
            lvl, j = 1, i + 1
            while j < len(toks) and lvl:
                lvl += {"LP": 1, "RP": -1}.get(toks[j].kind, 0)
                j += 1
            saved = dict(out.vars)                       # 子 shell 裡的指定不外溢
            _scan_tokens(toks[i + 1:j - 1], cwd, out)
            out.vars = saved
            i = j
            continue
        if t.kind == "SEP":
            cwd = _scan_segment(seg, cwd, prev_sep, t.text, out)
            seg, prev_sep = [], t.text
            i += 1
            continue
        seg.append(t)
        i += 1
    return _scan_segment(seg, cwd, prev_sep, "", out)


_VAR_REF_RE = lazy_re(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
_VAR_SURE_BEFORE = frozenset({"", ";", "\n", "&"})          # 前面接這些：這段一定會跑
_VAR_STAYS_AFTER = frozenset({"", ";", "\n", "&&", "||"})    # 後面接這些：在目前的 shell 跑（不是管線、不是背景）


def _remember_vars(words: List[_Tok], prev_sep: str, next_sep: str, out: _Scan, unset: bool = False) -> None:
    """規則 SHELL_LITERAL_VAR_EXPANDED 的記帳：獨立一段的 `NAME=值`（或 export／unset）一定會跑、而且在目前的 shell 生效才記；
    前面接 &&／||（跑不跑看前一段成敗）、在管線或背景裡的，把舊值拿掉（之後照判不出，寧可多擋）：
    `false && S=/scratchpad; printf x > "$S/卡.md"` 實際寫的是舊的 S。值是字面（沒有 $、反引號、$(…)）才記。
    PowerShell 的變數語法不同，不記。"""
    if out.ps:
        return
    keep = prev_sep in _VAR_SURE_BEFORE and next_sep in _VAR_STAYS_AFTER
    for w in words:
        name, eq, val = w.text.partition("=")
        if not name.isidentifier():
            continue
        if keep and eq and not unset and not (w.subst or "$" in val or "`" in val):
            out.vars[name] = val
        else:
            out.vars.pop(name, None)


def _expand_vars(t: _Tok, out: _Scan) -> _Tok:
    """這條指令前面指定過的字面變數（out.vars）、沒碰過的環境變數（out.env）代換進字裡（$S、${S}）；
    都不是的照留（之後判不出）；單引號裡的 $ 是字面、不代換。"""
    if t.sq_dollar or "$" not in t.text:
        return t

    def value(m: "re.Match[str]") -> str:
        name = m.group(1) or m.group(2)
        return out.vars.get(name, out.env.get(name, m.group(0)))

    text = _VAR_REF_RE.sub(value, t.text)
    return t if text == t.text else _Tok("W", text, t.quoted, t.subst)


_IDENT_RE = lazy_re(r"[A-Za-z_][A-Za-z0-9_]*")
# shell 自己會在指令中途改、或已有專屬規則的變數：不照 hook 行程的環境值代換（cd 改 PWD／OLDPWD；$HOME 由 _write_target_abs 管）
_SHELL_OWN_VARS = frozenset({"PWD", "OLDPWD", "_", "REPLY", "OPTARG", "OPTIND", "HOME"})


def _env_for_expansion(cmd: str) -> Dict[str, str]:
    """規則 SHELL_ENV_VAR_EXPANDED：這條 Bash 指令裡沒碰過的環境變數（$TEMP、$TMP…）照 hook 行程的 os.environ 代換（同 $HOME 理）。
    碰過＝名字在指令裡以 $NAME／${NAME} 以外的樣子出現（NAME=、export／unset／read／for NAME in、${NAME:=…}，
    條件式的、子 shell 裡的也算）→ 照舊判不出。名字大小寫要和環境裡一模一樣；環境裡沒有的照舊判不出。"""
    touched = set(_IDENT_RE.findall(_VAR_REF_RE.sub(" ", cmd)))
    return {k: v for k, v in os.environ.items() if k not in touched and k not in _SHELL_OWN_VARS}


def _mark_unknown(out: _Scan, seg: List[_Tok]) -> None:
    out.signal = True
    if out.unknown is None:
        out.unknown = " ".join(t.text for t in seg if t.text and t.kind != "HD")


def _inline_flag_at(name: str, args: List[str]) -> int:
    """規則 INLINE_FLAG_BEFORE_PROGRAM：內嵌碼旗標（python -c／-、node -e／-p、pwsh -Command／-c／-e）只認直譯器自己的選項位置——
    程式（腳本、-m 模組、pwsh 的 -File）之後的參數是程式的，`python x.py -C <路徑>` 的 -C 不是 python -c。
    python／node 的選項分大小寫（node -C 是條件旗標）、帶值的選項連值一起跳過；PowerShell 參數本來就不分大小寫、遇到 -File 才停。
    回旗標在 args 的位置，沒有回 -1。"""
    flags = _INTERPRETERS[name]
    if name in ("pwsh", "powershell"):
        for i, a in enumerate(args):
            low = a.lower()
            if low in ("-file", "-f"):
                return -1
            if low in flags:
                return i
        return -1
    valued = _PY_VALUE_OPTS if name in _PY_NAMES else _NODE_VALUE_OPTS
    i = 0
    while i < len(args):
        a = args[i]
        if a in flags:
            return i
        if a in ("-m", "--") or not a.startswith("-"):
            return -1
        i += 2 if a in valued else 1
    return -1


def _inline_python_code(args: List[str], at: int, seg: List[_Tok]) -> str:
    """python -c 的程式字串（at＝_inline_flag_at 找到的旗標位置）；`python -`（從 stdin 讀程式）取同一段 heredoc 的內文——
    只有一份 heredoc、沒有別的輸入重導向（多份時 stdin 是最後那份、`<` 也會換掉它），而且定界符加了引號或內文沒有 $／反引號
    （否則 shell 會先展開）才算得準。都不是回空字串（判不了）。"""
    if args[at] == "-c":
        return args[at + 1] if at + 1 < len(args) else ""
    hds = [t for t in seg if t.kind == "HD"]
    if (args[at] == "-" and len(hds) == 1 and not any(t.kind == "IN" for t in seg)
            and (hds[0].quoted or not re.search(r"[$`]", hds[0].text))):
        return hds[0].text
    return ""


def _add(out: _Scan, seg: List[_Tok], resolved: Optional[str]) -> None:
    if resolved == _WRITE_TARGET_UNKNOWN:
        _mark_unknown(out, seg)
    elif resolved and resolved not in out.targets:
        out.targets.append(resolved)


def _add_copy(out: _Scan, seg: List[_Tok], srcs: List[str], dst: str, cwd: Optional[str]) -> None:
    """cp 家族：目標照 _copy_targets 算，每個目標記下來源（給「搬的是不是程式」判斷；目的地還不存在時路徑看不出來）。
    srcs 空字串＝來源不明，只收目標。"""
    tgts = _copy_targets([s or "x" for s in srcs], dst, cwd)
    pairs = list(zip(tgts, srcs)) if len(tgts) == len(srcs) else [(t, s) for t in tgts for s in srcs]
    for t in tgts:
        _add(out, seg, t)
    for t, s in pairs:
        src = _write_target_abs(s, cwd) if s else None
        if t and t != _WRITE_TARGET_UNKNOWN and src and src != _WRITE_TARGET_UNKNOWN:
            got = out.sources.setdefault(t, [])
            if src not in got:
                got.append(src)


def _inner_has_signal(text: str, cwd: Optional[str]) -> bool:
    inner = _Scan()
    _scan_tokens(_lex_shell(text), cwd, inner)
    return inner.signal


_GIT_VALUE_OPTS = frozenset({"-c", "--namespace", "--exec-path", "--config-env"})   # 帶一個值的 git 全域選項（-C 另算）
_GIT_TREE_OPTS = ("--git-dir", "--work-tree")                                        # 改了 repo／工作樹位置：路徑判不出來
_PATHSPEC_MAGIC_RE = lazy_re(r"[*?\[]|^:")


def _git_checkout_paths(rest: List[str], base: Optional[str]) -> Optional[List[str]]:
    """git checkout 的參數 → 會被改寫的路徑 token：`-- <路徑>…` 之後全是路徑；沒有 `--` 時 `<rev> <路徑>…` 第二個起是路徑，
    只有一個參數且它是現存的檔（`git checkout x.py`）也是路徑。切分支、建分支（-b／-B／--orphan、`git checkout <分支>`）→ []。
    只有一個參數且它是現存的目錄（`git checkout .`、`git -C src checkout .`）會還原整個目錄、不知道動了哪些檔，
    與 --pathspec-from-file 一樣 → None（判不出來）。"""
    if any(a.startswith("--pathspec-from-file") for a in rest):
        return None
    if "--" in rest:
        return rest[rest.index("--") + 1:]
    if any(a in ("-b", "-B", "--orphan") for a in rest):
        return []
    pos = [a for a in rest if not a.startswith("-")]
    if len(pos) >= 2:
        return pos[1:]
    if len(pos) == 1:
        r = _write_target_abs(pos[0], base) if base is not None or os.path.isabs(pos[0]) else None
        if r in (None, _WRITE_TARGET_UNKNOWN):
            return []
        if os.path.isdir(r):
            return None
        return pos if os.path.isfile(r) else []
    return []


def _git_restore_paths(rest: List[str]) -> Optional[List[str]]:
    """git restore 的參數 → 會被改寫的路徑 token。`--staged`（-S）沒有 `--worktree`（-W）只動暫存區、不寫檔 → []；
    --source／-s 的值不是路徑；--pathspec-from-file → None（判不出來）。"""
    staged = worktree = after_dd = False
    paths: List[str] = []
    i = 0
    while i < len(rest):
        a = rest[i]
        if after_dd or not a.startswith("-"):
            paths.append(a)
        elif a == "--":
            after_dd = True
        elif a.startswith("--pathspec-from-file"):
            return None
        elif a in ("-s", "--source"):
            i += 1                                   # 下一個是來源版本
        elif a in ("-S", "--staged"):
            staged = True
        elif a in ("-W", "--worktree"):
            worktree = True
        elif re.match(r"^-[A-Za-z]+$", a) and not a.startswith("-s"):
            staged, worktree = staged or "S" in a, worktree or "W" in a
        i += 1
    return [] if staged and not worktree else paths


def _git_restore_targets(args: List[str], cwd: Optional[str], seg: List[_Tok], out: _Scan) -> None:
    """git 指定路徑還原檔案內容（R3 補）：`git checkout [<rev>] -- <路徑>…`、`git checkout <rev> <路徑>…`、
    `git restore [--source <rev>] [--worktree] <路徑>…` 會改寫工作樹的檔 → 目標＝那些路徑（照 `-C <目錄>` 或 cwd 解析）。
    寫碼查核靠它記下「最後一次改這個檔」的時間：反證時用 git 把程式與案例退回舊版、最後只還原程式，時間序才查得到。
    只認字面檔案路徑：萬用字元、pathspec 魔術字（`:` 開頭）、目錄、--pathspec-from-file、--git-dir／--work-tree、算不出的 -C → UNKNOWN。
    `git mv 來源… 目標` 的目標同 mv 算寫入（目標是現存目錄就是目錄/來源檔名）：寫碼查核對「已不存在的程式檔不欠案例」，
    搬走的程式要在新路徑照算。其他 git 子指令（commit、log、switch…）照舊不算寫入目標。
    每段 git 都記進 out.gits：(repo 目錄＝cwd 照 -C 推，--git-dir／--work-tree 或推不出 → None, git 後的參數)，給跨層閘分哪幾段在根層 repo。"""
    base, tree, i = cwd, False, 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a == "-C" and i + 1 < len(args):
            r = _write_target_abs(args[i + 1], base)
            base = None if r in (None, _WRITE_TARGET_UNKNOWN) else r
            i += 2
        elif a in _GIT_VALUE_OPTS and i + 1 < len(args):
            i += 2
        elif a.startswith(_GIT_TREE_OPTS):
            tree = True
            i += 1 if "=" in a else 2
        else:
            i += 1
    out.gits.append((None if tree else base, list(args)))
    if i >= len(args):
        return
    sub, rest = args[i].lower(), args[i + 1:]
    if sub == "mv":                                  # git mv 來源… 目標：目標是寫入（同 mv）；來源不在了，寫碼查核另有刪除的規則
        pos = [a for a in rest if a != "--" and not a.startswith("-")]
        if len(pos) < 2:
            return
        out.signal = True
        if tree or (base is None and not all(os.path.isabs(a) for a in pos)):
            _mark_unknown(out, seg)
            return
        for r in _copy_targets(pos[:-1], pos[-1], base):
            _add(out, seg, r)
        return
    if sub == "checkout":
        paths = _git_checkout_paths(rest, base)
    elif sub == "restore":
        paths = _git_restore_paths(rest)
    else:
        return
    if paths == []:
        return
    if paths is None or tree:
        _mark_unknown(out, seg)
        return
    out.signal = True
    for p in paths:
        r = _WRITE_TARGET_UNKNOWN if _PATHSPEC_MAGIC_RE.search(p) else _write_target_abs(p, base)
        if r not in (None, _WRITE_TARGET_UNKNOWN) and os.path.isdir(r):
            r = _WRITE_TARGET_UNKNOWN                # 目錄：不知道還原了其中哪些檔
        _add(out, seg, r)


def _scan_segment(seg: List[_Tok], cwd: Optional[str], prev_sep: str, next_sep: str, out: _Scan) -> Optional[str]:
    """一個子段：先收重導向目標，再看第一個命令字是不是寫檔命令／直譯器／eval／cd。回之後的 cwd。"""
    if not seg:
        return cwd
    if out.vars or out.env:
        seg = [_expand_vars(t, out) if t.kind == "W" else t for t in seg]
    words: List[_Tok] = []
    i = 0
    while i < len(seg):
        t = seg[i]
        if t.kind == "OUT":
            out.signal = True
            if i + 1 >= len(seg) or seg[i + 1].kind != "W":
                _mark_unknown(out, seg)
                return cwd
            tgt = seg[i + 1]
            _add(out, seg, _WRITE_TARGET_UNKNOWN if tgt.subst else _write_target_abs(tgt.text, cwd))
            i += 2
            continue
        if t.kind == "IN":
            i += 2
            continue
        if t.kind in ("DUP", "HD"):
            i += 1
            continue
        words.append(t)
        i += 1
    # 規則 UNKNOWN_PART_KEEPS_KNOWN_TARGETS：某個字判不出（$(…) 裡有寫入、[IO.File]:: 這類內嵌碼）只多記一筆 UNKNOWN，
    # 同一段看得懂的目標照算（`rm -rf <核心檔> '[IO.File]::'` 不能讓後面那個參數蓋掉前面明確的刪除）
    if any((w.subst and any(_inner_has_signal(s, cwd) for s in w.subst)) or _INLINE_CODE_RE.search(w.text) for w in words):
        _mark_unknown(out, seg)
    from wg_release_rules import SHELL_PREFIX_KEYWORDS    # 規則 SHELL_KEYWORD_PREFIX_STRIPPED：do／then／{ 後面才是命令
    k = 0
    while k < len(words) and (_ENV_ASSIGN_RE.match(words[k].text) or words[k].text.lower() in _WRAPPERS
                              or (not words[k].quoted and words[k].text in SHELL_PREFIX_KEYWORDS)):
        k += 1
    if k >= len(words):
        _remember_vars(words, prev_sep, next_sep, out)     # 整段只有指定：之後的段看得到（指令前綴的指定不算）
        return cwd
    if words[k].text in ("export", "unset"):
        _remember_vars(words[k + 1:], prev_sep, next_sep, out, unset=words[k].text == "unset")
        return cwd
    name = words[k].text.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    if name.endswith(".exe"):
        name = name[:-4]
    if out.ps:
        name = _PS_WRITE_ALIASES.get(name, name)
    if name in ("source", ".", "eval"):
        out.env = {}                                     # 讀進來的檔、eval 的字串可能改任何變數：之後不再照環境值代換
    args = [w.text for w in words[k + 1:]]
    at = _inline_flag_at(name, args) if name in _INTERPRETERS else -1
    if at >= 0:
        # 規則 INLINE_PY_READONLY：python -c 的程式碼、`python -` 從 heredoc 讀的程式用 ast 靜態判只讀 → 沒有寫入訊號；
        # 判出可能寫檔的原因記在 out.why（擋訊息帶出）；其他直譯器內嵌碼（node -e、pwsh -Command）判不了照 UNKNOWN
        code = _inline_python_code(args, at, seg) if name in _PY_NAMES else ""
        if code:
            from wg_release_rules import inline_python_verdict
            v = inline_python_verdict(code)
            if not v.owed:
                return cwd
            if out.unknown is None:                      # 原因只跟著它自己那段：前面已有判不出的段，原因不能黏過去
                out.why = v.why
        _mark_unknown(out, seg)
        return cwd
    if name == "eval":
        if _inner_has_signal(" ".join(args), cwd):
            _mark_unknown(out, seg)
        return cwd
    if name in ("cd", "pushd") or (out.ps and name in _PS_CD_NAMES):
        if out.ps:                                       # Set-Location -Path X／-LiteralPath X：參數名不是目錄
            args = [a for a in args if a.lower() not in _PS_CD_PATH_PARAMS]
        if prev_sep in ("|", "||"):
            return cwd                                   # ||／| 右側的 cd 不外溢
        if not args:
            new = str(Path.home())
        elif args[0] == "-":
            new = None
        else:
            r = _write_target_abs(args[0], cwd)
            new = None if r in (None, _WRITE_TARGET_UNKNOWN) else r
        return None if next_sep in ("|", "||") else new    # cd 之後接 |／||：成功與否不確定
    if name == "git":
        _git_restore_targets(args, cwd, seg, out)
        return cwd
    if name not in _WRITE_CMDS:
        return cwd
    out.signal = True
    positional = [a for a in args if not a.startswith("-")]
    if name == "tee":
        for a in positional:
            _add(out, seg, _write_target_abs(a, cwd))
    elif name in _TARGET_VALUE_FLAGS:
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a in _TARGET_VALUE_FLAGS[name]:           # 帶值旗標各命令自己的：rm -r 的 -r 不帶值（touch -r 才帶）
                skip = True
                continue
            if not a.startswith("-"):
                _add(out, seg, _write_target_abs(a, cwd))
    elif name == "dd":
        for a in args:
            if a.startswith("of="):
                _add(out, seg, _write_target_abs(a[3:], cwd))
    elif name == "sort":
        for j, a in enumerate(args):
            if a == "-o" and j + 1 < len(args):
                _add(out, seg, _write_target_abs(args[j + 1], cwd))
            elif a.startswith("--output="):
                _add(out, seg, _write_target_abs(a.split("=", 1)[1], cwd))
            elif a.startswith("-o") and len(a) > 2:
                _add(out, seg, _write_target_abs(a[2:], cwd))
    elif name == "sed":
        inplace, files, w_files = _sed_targets(args)
        for f in (files if inplace else []) + w_files:
            _add(out, seg, _write_target_abs(f, cwd))
    elif name in _COPY_CMDS and name in ("cp", "mv", "install", "rsync", "ln"):
        pos: List[str] = []
        tdir = ""
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a in ("-t", "--target-directory"):
                tdir = "\x01"                        # 下一個字就是目標目錄
                continue
            if a.startswith("--target-directory="):
                tdir = a.split("=", 1)[1]
                continue
            if a in _COPY_VALUE_FLAGS:
                skip = True
                continue
            if a.startswith("-"):
                continue
            if tdir == "\x01":
                tdir = a
                continue
            pos.append(a)
        if tdir:
            _add_copy(out, seg, pos, tdir + "/", cwd)
        elif len(pos) >= 2:
            _add_copy(out, seg, pos[:-1], pos[-1], cwd)
    else:
        items = _ps_targets(name, args)
        if not items:                                    # 目標從管線進來（Get-Item x | Remove-Item）：有寫入、算不出目標
            _mark_unknown(out, seg)
        for item in items:
            if "\x00" in item:
                dst, src = item.split("\x00", 1)
                _add_copy(out, seg, [src], dst, cwd)
            else:
                _add(out, seg, _write_target_abs(item, cwd))
    return cwd


def write_paths_from_tool(tool_name: str, tool_input: Dict[str, Any], cwd: Optional[str] = None) -> List[str]:
    """工具呼叫會寫到哪些檔（絕對路徑、去重、保序）。Edit／Write／NotebookEdit／MultiEdit 取 file_path（相對以 cwd 補）；
    Bash／PowerShell 依 R0～R5：沒有寫入訊號回 []；有訊號但算不出目標回 ["UNKNOWN:<該段前 40 字>"]（呼叫端自己決定怎麼處理）；其他工具回 []。"""
    base = cwd or os.getcwd()
    if tool_name in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        fp = tool_input.get("file_path", "") or tool_input.get("notebook_path", "") or ""
        if not fp:
            return []
        p = _write_target_abs(fp, base)
        return [p if p and p != _WRITE_TARGET_UNKNOWN else f"{_WRITE_TARGET_UNKNOWN}:{fp[:40]}"]
    return _shell_write_paths(_scan_shell_tool(tool_name, tool_input, base))


def _shell_write_paths(out: Optional[_Scan]) -> List[str]:
    """掃描結果 → 寫入目標：沒有寫入訊號回 []；有段算不出目標 → 算得出的目標照列，最後加一筆 "UNKNOWN:<第一個判不出那段前 40 字>"
    （規則 UNKNOWN_PART_KEEPS_KNOWN_TARGETS：一段判不出不能蓋掉別段明確的目標，`rm <核心檔>; echo x > "$VAR/out"` 照擋）。"""
    if out is None or not out.signal:
        return []
    if out.unknown is not None:
        why = f"｜內嵌碼：{out.why[:60]}" if out.why else ""
        return [*out.targets, f"{_WRITE_TARGET_UNKNOWN}:{out.unknown[:40]}{why}"]
    return out.targets


def _scan_shell_tool(tool_name: str, tool_input: Dict[str, Any], base: str) -> Optional[_Scan]:
    if tool_name not in ("Bash", "PowerShell"):
        return None
    cmd = tool_input.get("command", "") or ""
    out = _Scan(ps=tool_name == "PowerShell")
    if not out.ps:                                       # PowerShell 的 $TEMP 是 PS 變數、不是環境變數
        out.env = _env_for_expansion(cmd)
    _scan_tokens(_lex_shell(cmd), base, out)
    return out


def write_sources_from_tool(tool_name: str, tool_input: Dict[str, Any], cwd: Optional[str] = None) -> Dict[str, List[str]]:
    """Bash／PowerShell 的 cp／mv／install／rsync／ln／Copy-Item／Move-Item：寫入目標 → 它的來源（絕對路徑）。
    目的地還不存在時光看目標路徑分不出搬的是不是程式，來源才看得出來。其他工具、沒有來源的目標不在裡面。"""
    out = _scan_shell_tool(tool_name, tool_input, cwd or os.getcwd())
    return dict(out.sources) if out is not None and out.unknown is None else {}


# 規則 DOT_GIT_PATH_NOT_GIT_CALL：路徑裡的 `.git`（`ls repo/.git/hooks`）不是在叫 git，不算 git 字樣
_GIT_WORD_RE = lazy_re(r"(?<!\.)\bgit(?:\.exe)?\b", re.IGNORECASE)
_GIT_REPO_ENV_RE = lazy_re(r"\bGIT_(?:DIR|WORK_TREE|COMMON_DIR)\b")


def _in_root_realm(path: str) -> bool:
    """路徑在根層底下（含本身）：Claude Code 設定目錄（claude_config_dir：settings.json、CLAUDE.md 所在，一般安裝就是家目錄的
    .claude）、資料根 CLAUDE_DIR、程式碼根 CODE_DIR。解析失敗算在（寧可多擋）。"""
    try:
        p = Path(path).resolve()
        roots = [r.resolve() for r in (claude_config_dir(), CLAUDE_DIR, CODE_DIR)]
    except (OSError, ValueError):
        return True
    return any(p == r or r in p.parents for r in roots)


def _git_arg_reaches_root(arg: str, repo: str) -> bool:
    """非根層 repo 的 git 參數會不會碰到根層（archive -o、diff --output=、clone／worktree add 的目錄）：相對路徑落在 repo 底下碰不到，
    ~、絕對路徑、..、展不開的變數才可能。旗標取 = 後面、或黏在短旗標後面的值。"""
    if arg.startswith("--"):
        arg = arg.split("=", 1)[1] if "=" in arg else ""
    elif arg.startswith("-"):
        arg = arg.split("=", 1)[1] if "=" in arg else arg[2:]
    r = _write_target_abs(arg, repo) if arg else None
    return r == _WRITE_TARGET_UNKNOWN or (r is not None and _in_root_realm(r))


def _root_git_segments(scan: _Scan, cmd: str) -> Optional[List[List[str]]]:
    """規則 GIT_READONLY_SUBCMD 的範圍：只判 repo 在根層的 git 段（repo 用掃描器的 cd／-C 追蹤推；推不出、參數碰到根層也算）。
    掃描器看不全 → None（照舊整條判）：有命令替換、git 字樣（註解行除外）比掃描器認到的 git 段多（eval、bash -c、xargs、heredoc 裡）、
    GIT_DIR／GIT_WORK_TREE 改了 repo 位置。"""
    from wg_release_rules import strip_comment_lines
    if (re.search(r"\$\(|`", cmd) or _GIT_REPO_ENV_RE.search(cmd)
            or len(_GIT_WORD_RE.findall(strip_comment_lines(cmd))) > len(scan.gits)):
        return None
    return [args for repo, args in scan.gits
            if repo is None or _in_root_realm(repo) or any(_git_arg_reaches_root(a, repo) for a in args)]


def check_cross_realm_bash(
    tool_name: str, tool_input: Dict[str, Any], cwd: str,
    config: Dict[str, Any], session_id: str = "",
) -> Optional[str]:
    """外部專案 session 經 Bash/PowerShell 改 ~/.claude 核心層或操作根層 repo → deny（擋紀錄帶 session_id）。cwd 缺失 fail-open。"""
    if tool_name not in ("Bash", "PowerShell"):
        return None
    g = (config.get("guard") or {}).get("cross_realm_bash") or {}
    if not g.get("enabled", True):
        return None
    cmd = tool_input.get("command", "") or ""
    if not cmd or not cwd:
        return None
    if _is_core_session(cwd) is not False:
        return None  # 核心開發 session 放行；無法判定 → fail-open
    ctx_cmd = _ROOT_TOOL_INVOKE_RE.sub(" ", cmd)  # 跑根層工具本身不算根層上下文
    root_ctx = bool(_ROOT_CD_RE.search(ctx_cmd) or _ROOT_CORE_PATH_RE.search(ctx_cmd))
    if not root_ctx:
        return None
    has_git = _GIT_WORD_RE.search(cmd) is not None
    scan = _scan_shell_tool(tool_name, tool_input, cwd)
    if not _BASH_WRITE_OP_RE.search(cmd) and not has_git and not (scan and scan.signal):
        return None  # 唯讀（sed -n / grep / cat / python ~/.claude/tools/x.py …）放行；mkdir／touch 這類 regex 沒列的看掃描器的寫入訊號
    cmd_norm = cmd.replace("\\", "/").lower()
    for pat in g.get("allowlist", []) or []:
        if pat and str(pat).replace("\\", "/").lower() in cmd_norm:
            return None
    # 規則 GIT_READONLY_SUBCMD：根層上下文裡有 git（不論寫入訊號 regex 有沒有列到那個子命令：hash-object -w、worktree add、
    # branch -m 這類也算）或有寫入訊號時，每段 git 都要是唯讀子命令（show、hash-object 無 -w、rev-parse、diff、log、status、
    # ls-files、cat-file…）、且算得出的寫入目標沒有落在根層核心路徑（重導到 scratchpad 可以）→ 放行；
    # 任一目標在根層、任一段 git 會寫 → 照擋並留 guard-crossrealm.jsonl；目標判不出（UNKNOWN、PowerShell 換過目錄的相對目標）
    # → 放行並留帳（規則 UNKNOWN_TARGET_LOGGED，event=unknown_allowed）。
    # 「每段 git」只算 repo 在根層的（Bash：cd 到專案 repo 之後的 git archive 不算）；掃描器看不全就照舊每段都算
    from wg_release_rules import git_readonly_verdict
    targets = _shell_write_paths(scan)
    unknown = [t for t in targets if t.startswith(_WRITE_TARGET_UNKNOWN)]
    root_targets = [t for t in targets if not t.startswith(_WRITE_TARGET_UNKNOWN)
                    and (_ROOT_CORE_PATH_RE.search(t) or _is_core_session(t) is True)]
    git_segs = _root_git_segments(scan, cmd) if has_git and scan and not scan.ps else None
    if git_segs is not None:
        has_git = bool(git_segs)
    verdict = git_readonly_verdict(cmd, root_targets, git_segs)
    # PowerShell 的 Set-Location／Push-Location 不在寫入目標解析器的追蹤裡（bash 的 cd 有）：換過目錄的相對目標算不準，照舊擋
    ps_cd = tool_name == "PowerShell" and re.search(r"\b(?:Set-Location|Push-Location|sl|cd|chdir|pushd)\b", cmd, re.IGNORECASE)
    if not has_git and not root_targets and not ps_cd and verdict.owed:
        verdict = verdict._replace(owed=False, why="沒有 git、寫入目標也不在根層", evidence=tuple(str(t)[:60] for t in targets[:3]) or ("無目標",))
    if (unknown or ps_cd) and not verdict.owed:
        append_guard_log("crossrealm", {"cwd": cwd, "session_id": session_id, "cmd": cmd[:200], "event": "unknown_allowed",
                                        "rule": "UNKNOWN_TARGET_LOGGED", "allowed": True,
                                        "targets": unknown[:3] or ["PowerShell 換過目錄的相對目標"]})
    if not verdict.owed:
        print(f"[Guardian:CrossRealmBashBlock] 規則 {verdict.rule}：{verdict.why}｜證據：{'；'.join(verdict.evidence)}",
              file=sys.stderr)
        return None
    append_guard_log("crossrealm", {"cwd": cwd, "session_id": session_id, "cmd": cmd[:200], "rule": verdict.rule, "why": verdict.why,
                                    "evidence": list(verdict.evidence)[:3], "targets": root_targets[:3]})
    return (
        "[Guardian:CrossRealmBashBlock] 專案 session 不得經 Bash/PowerShell 修改 ~/.claude 核心層"
        "（hooks/lib/tools/skills/rules/prompts、根層設定與文件）或操作根層 repo（git add/commit/push）。\n"
        f"命令：{cmd[:160]!r}\n"
        f"session cwd：{cwd}\n"
        f"命中規則：{verdict.rule}：{verdict.why}｜證據：{'；'.join(verdict.evidence)}\n"
        "規則：專案層遇到要改根層的需求 → 不動手，把需求寫成一段可貼上的 prompt 交給使用者，"
        "請他到 ~/.claude 開 session 執行（那裡會跑 verify、選擇性 staging、push）。\n"
        "專案自己的需求 → 寫 {專案根}/.claude/hooks/project_hooks.py 或 .claude/skills/。\n"
        "只是要跑根層工具（唯讀、或針對本專案）→ 不要 cd 進 ~/.claude，直接 "
        "`python ~/.claude/tools/<tool>.py …`。"
    )


def check_cross_realm_mcp_cmd(
    tool_name: str, tool_input: Dict[str, Any], cwd: str,
    config: Dict[str, Any],
) -> Optional[str]:
    """v1.1 ②：外部專案 session 的 Bash `claude mcp add/remove` 全域 scope → deny。

    deny 條件：add 帶 `-s/--scope user`（寫 ~/.claude.json 全域區）、或 remove
    未限定 `-s project|local`（可能移除全域 server）。project/local scope 放行
    （效果限於該專案）。core session / cwd 無法判定 → fail-open。
    """
    if tool_name != "Bash":
        return None
    g = (config.get("guard") or {}).get("cross_realm_write") or {}
    if not g.get("enabled", True):
        return None
    cmd = tool_input.get("command", "") or ""
    m = _MCP_MUTATE_RE.search(cmd)
    if not m:
        return None
    if _is_core_session(cwd) is not False:
        return None
    sub = m.group(1).lower()
    if sub.startswith("add"):
        if not _MCP_SCOPE_USER_RE.search(cmd):
            return None  # 預設 local / 顯式 project|local：效果限本專案，放行
        reason = "add 帶 `-s user`（寫入全域 ~/.claude.json mcpServers）"
    else:  # remove
        if _MCP_SCOPE_PROJECT_LOCAL_RE.search(cmd):
            return None
        reason = "remove 未限定 `-s project|local`（可能移除全域 server）"
    return (
        f"[Guardian:CrossRealmMcpBlock] 偵測到外部專案 session 的全域 MCP 變更：\n"
        f"指令：{cmd[:200]}\n"
        f"session cwd：{cwd}\n"
        f"攔截原因：{reason}。\n"
        "正確做法：\n"
        "  (1) 專案要用的 MCP → `claude mcp add <name> -s project ...`"
        "（寫專案 .mcp.json，可版控共享）\n"
        "  (2) 確要全域註冊/移除 → 請在 ~/.claude 開 session 操作，"
        "或 config guard.cross_realm_write.enabled=false 暫關本閘"
    )


# ─── MCP Server Health Check (was wg_intent._check_mcp_servers) ──────────────


def _check_mcp_servers() -> List[str]:
    """Verify .mcp.json server entries: command + script must exist on disk."""
    issues: List[str] = []
    mcp_path = CLAUDE_DIR / ".mcp.json"
    if not mcp_path.exists():
        return []
    try:
        with open(mcp_path, "r", encoding="utf-8") as f:
            mcp_cfg = json.loads(f.read())
        servers = mcp_cfg.get("mcpServers", {})
        import shutil
        for name, srv in servers.items():
            cmd = srv.get("command", "")
            args = srv.get("args", [])
            if cmd and not Path(cmd).exists() and not shutil.which(cmd):
                issues.append(f"{name}: command not found ({cmd})")
            if args:
                script = args[0]
                if not Path(script).exists():
                    issues.append(f"{name}: script not found ({script})")
    except Exception as e:
        issues.append(f"parse error: {e}")
    return issues
