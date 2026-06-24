"""
wg_handoff.py — Auto-Handoff 自動無損交接（跨 session）

context 將壓縮 / token 將盡時，自動備妥六區塊 handoff stub 到 _staging，使下個
session `/continue` 無損接續。核心保底由 PreCompact 觸發（壓縮真的發生 = 最可靠
信號，**不依賴 token 量測**）；壓縮後由 PostToolBatch 注入提示叫模型補全主觀區塊。

設計：plans/wise-wobbling-gem.md。與 skills/handoff（手動六區塊）/ skills/continue
（讀取端）對齊；stub 第一行即 /continue 選單摘要。

Phase 1 提供：
- build_handoff_stub(state, cwd): 生成六區塊 stub（客觀區塊自動填 + 主觀區塊 TODO 佔位）
- should_write_stub(staging_dir, state, stub_filename): 無既有手寫 next-phase*.md
  + 有未完成工作才自動補（不覆蓋更佳的手寫版）

Phase 2 提供（供 Stop Layer 1 token 預警，piggyback 既有 block）：
- estimate_context_usage(transcript, window, overhead): context 佔用比率（僅信號）。
  主路徑讀 message.usage 真實 token + 自我校準 200k/1M 分母；無 usage 時 fallback char-proxy。
- token_warn_payload(state, config, transcript): 純函式決策是否回預警句（無副作用）
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from wg_core import _estimate_tokens, _now_iso

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _git(args: List[str], cwd: str, timeout: float = 1.5) -> str:
    """跑 git 子程序，fail-open 回空字串（git 不存在 / 非 repo / 逾時）。
    creationflags=_NO_WINDOW 防 Windows 閃 console（覆轍 commit 1d73e55）。"""
    if not cwd:
        return ""
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=cwd, capture_output=True, text=True,
            timeout=timeout, creationflags=_NO_WINDOW,
        )
        if r.returncode == 0:
            return (r.stdout or "").strip()
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        pass
    return ""


def _unique_paths(items: List[Any]) -> List[str]:
    """從 modified_files / accessed_files（dict 帶 path 或純 str）抽去重路徑清單。"""
    out: List[str] = []
    seen = set()
    for it in items or []:
        p = it.get("path", "") if isinstance(it, dict) else str(it or "")
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _bullets(items: List[Any], limit: int = 15, empty: str = "（無）") -> str:
    sliced = [str(x) for x in (items or [])[:limit]]
    if not sliced:
        return f"- {empty}"
    return "\n".join(f"- {s}" for s in sliced)


def should_write_stub(
    staging_dir: Path, state: Dict[str, Any], stub_filename: str,
) -> bool:
    """是否自動補 stub。

    True 條件：有未完成工作（modified_files 非空）且 staging 無既有「手寫」
    next-phase*.md（既有手寫 handoff 品質更佳，尊重不覆蓋；自身產出的 auto stub
    可被新 stub 更新，故排除自身檔名）。
    """
    if not (state.get("modified_files") or []):
        return False
    try:
        if staging_dir.exists():
            for f in staging_dir.glob("next-phase*.md"):
                if f.name == stub_filename:
                    continue  # 自身 auto stub，可更新
                return False   # 有手寫 handoff → 尊重之
    except OSError:
        pass
    return True


def build_handoff_stub(state: Dict[str, Any], cwd: str) -> str:
    """生成六區塊 handoff stub markdown。

    客觀區塊（前置脈絡部分 / 已完成 / 權威來源 / 產出位置）自動填；主觀區塊
    （why / 做法 / 決策依據）留 `<!-- TODO(模型補全) -->` 佔位，由 Layer 3 注入
    提示叫模型補全。第一行為 /continue 選單摘要。
    """
    sess = state.get("session", {}) or {}
    sid = sess.get("id", "") or ""
    phase = state.get("phase", "working")
    now = _now_iso()

    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd) or "(未知 / 非 git)"
    last_commit = _git(["log", "-1", "--format=%h %s"], cwd) or "(無 commit 記錄)"

    mod_paths = _unique_paths(state.get("modified_files", []))
    acc_paths = _unique_paths(state.get("accessed_files", []))
    kq = [str(x) for x in (state.get("knowledge_queue", []) or [])]
    injected = [str(x) for x in (state.get("injected_atoms", []) or [])]

    tt = state.get("topic_tracker", {}) or {}
    first_summary = tt.get("first_prompt_summary", "") or "(無記錄)"

    def _todo(txt: str) -> str:
        return f"<!-- TODO(模型補全)：{txt} -->"

    return f"""[續接] Auto-Handoff 自動交接（{now}）

> ⚠️ 此 stub 由 PreCompact 在 context 壓縮前自動生成：**客觀區塊已填、主觀區塊待補**。
> 下個 Claude：先補全 `TODO(模型補全)` 三區塊（why / 做法 / 決策依據）再動工。
> Session: `{sid[:12]}…`，phase=`{phase}`。

## 1.【前置脈絡】
- 專案根目錄：`{cwd or '(未知)'}`
- 工作分支：`{branch}`
- 首個任務摘要：{first_summary}
- {_todo('為什麼做這件事 — why，不只 what')}

## 2.【已完成】
- phase：`{phase}`
- 最近 commit：`{last_commit}`
- {_todo('已通過的驗證（測試/編譯/手測）+ push 狀態')}

## 3.【權威來源】（本 session 接觸的檔，下個 Claude 先讀）
{_bullets(acc_paths or mod_paths)}
- 注入記憶 atom：{', '.join(injected[:20]) or '（無）'}

## 4.【產出位置】（本 session 修改的檔）
{_bullets(mod_paths)}

## 5.【做法】
- {_todo('步驟清單 + 指明工具選擇，避免下個 Claude 重新評估')}

## 6.【決策依據】
- {_todo('為什麼選此做法 / 拒絕了哪些 alternatives / 已知坑')}
- 知識待辦（knowledge_queue）：
{_bullets(kq, empty='（無）')}

---
> 補全後可直接續工；或人工檢視後刪除。標準接續：下個 session 打 `/continue`。
"""


# ─── Phase 2: Stop token 預警（Layer 1，piggyback 既有 block）─────────────────


def _usage_totals_from_text(text: str) -> List[int]:
    """逐 assistant turn 的真實 context 佔用 token（input+cache_creation+cache_read）。

    讀 transcript jsonl 每行的 `message.usage`（API 真的算給這輪的量，已含 system
    prompt / 工具定義 / CLAUDE.md / 注入 atom，故無須再加 base_overhead）。回各輪
    總量 list（依序）；無可解析 usage 回 `[]`（呼叫端 fallback 回 char-proxy）。
    """
    totals: List[int] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or '"usage"' not in line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        msg = obj.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        u = msg.get("usage")
        if not isinstance(u, dict):
            continue
        total = (
            int(u.get("input_tokens", 0) or 0)
            + int(u.get("cache_creation_input_tokens", 0) or 0)
            + int(u.get("cache_read_input_tokens", 0) or 0)
        )
        if total > 0:
            totals.append(total)
    return totals


def _calibrated_window(peak_observed: int, default_window: int) -> int:
    """自我校準 context 視窗上限（分母），無須知道模型或 [1m] beta。

    物理事實：200k 視窗的 session 在逼近 200k 前 harness 就先 auto-compact，usage
    總量永遠摸不到 200k；故**只要曾觀測到 >200k → 數學上必為 1M 視窗**。未破 200k
    時無從反推、用 `default_window`（預設 1M，貼合常跑 1M 的現實）。取 `max` 確保
    default 調低（如 200k）時仍會在真突破後自動升 1M、不會反而縮小。
    """
    calibrated = 1_000_000 if peak_observed > 200_000 else 0
    return max(int(default_window), calibrated)


def estimate_context_usage(
    transcript_path: Any,
    window_tokens: int = 1_000_000,
    base_overhead: int = 15000,
) -> float:
    """context 佔用比率（0.0 起；可能 >1.0）。

    **主路徑**：讀 transcript 每輪 `message.usage` 的真實 token 佔用（input+
    cache_creation+cache_read）。分子 = 最近一輪佔用（= 現在 context 實塞多少）；
    分母 = `_calibrated_window`（自我校準 200k/1M，見該函式）。usage 已含常駐
    開銷，**不另加 base_overhead**。
    **Fallback**（transcript 無任何可解析 usage：全新 session / 讀取失敗 / 舊格式）
    → 退回原 char-proxy（`_estimate_tokens` + base_overhead）/ `window_tokens`。

    ⚠️ **僅觸發信號、非硬決策**：回 `0.0` 表無法量測（transcript 不存在 / 讀取
    失敗 / window 非正）→ 自然落在門檻下、不誤觸發。核心保底（PreCompact 自動
    stub）完全不依賴本量測，估值不準不影響正確性。
    """
    if not transcript_path or window_tokens <= 0:
        return 0.0
    try:
        text = Path(transcript_path).read_text(encoding="utf-8", errors="ignore")
    except (OSError, ValueError):
        return 0.0
    if not text:
        return 0.0
    totals = _usage_totals_from_text(text)
    if totals:
        return totals[-1] / _calibrated_window(max(totals), window_tokens)
    # fallback：無 usage → 原 char-proxy（degrade gracefully、與舊行為一致）
    tokens = _estimate_tokens(text) + max(0, int(base_overhead))
    return tokens / window_tokens


def token_warn_payload(
    state: Dict[str, Any], config: Dict[str, Any], transcript_path: Any,
) -> Optional[str]:
    """Layer 1 預警句決策（**純函式、無副作用**，方便單元測試）。

    回非空字串 = 應 piggyback 到既有 Stop block 的 reason 末尾；回 None = 不警。
    一次性（token_warn_emitted）/ config 開關（enabled、token_warn）/ 門檻
    （token_warn_ratio）全在此判定。**不設旗標**——旗標由呼叫端在「實際 append
    到會 output_block 的 reason」時才標，避免 warning 未顯示就被當成已發。
    """
    ah = config.get("auto_handoff", {}) or {}
    if not ah.get("enabled", True) or not ah.get("token_warn", True):
        return None
    if state.get("token_warn_emitted"):
        return None
    ratio = estimate_context_usage(
        transcript_path,
        ah.get("context_window_tokens", 1_000_000),
        ah.get("context_base_overhead_tokens", 15000),
    )
    if ratio < float(ah.get("token_warn_ratio", 0.85)):
        return None
    pct = int(ratio * 100)
    return (
        f"\n[Auto-Handoff] context 估佔 ~{pct}%（依 API 實際 token 用量），接近自動壓縮點。"
        "建議主動 `/handoff` 備妥六區塊交接、或開新 session 前先存檔（壓縮真發生時"
        "系統會自動備 stub 保底）。是否已『處理失真』由你語意判斷。"
    )
