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
（estimate_context_usage 於 Phase 2 加入，供 Stop token 預警）
"""

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from wg_core import _now_iso

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
