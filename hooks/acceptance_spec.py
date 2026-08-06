"""acceptance_spec.py — 驗收規格工件 hook（standalone PostToolUse）。

問題：任務的「做完的定義」只活在對話與 plan 文字裡，session 結束即蒸發；
收尾自核與獨立裁判（Codex acceptance_review 接線點）手上沒有這個任務的
驗收標準可對，只能憑通用直覺。

機制（分級啟動，小任務零打擾）：
  (1) ExitPlanMode（plan 獲同意）→ additionalContext 指示模型從 plan 內容落
      驗收規格檔 `<專案根>/.claude/verify/acceptance-<slug>.md`：frontmatter
      供任務↔規格綁定（task_slug / session_id / created_at / source / status），
      內文三段列表（必須發生 / 禁止發生 / 驗證指令），不造 schema 巨獸。
  (2) 無 plan 但同 session 修改檔數 ≥ min_files_trigger（讀 guardian state
      modified_files——已去重、已濾 ephemeral）→ 一次性建議補規格檔。
  (3) 規格檔本身被寫入 → sidecar 記路徑，抑制 (2) 的重複提醒。

每 session 每型提醒至多一次（sidecar `workflow/acceptance-spec/<sid>.json`）。
advisory-only 不阻斷；hook 只發指令，規格內容由模型生成（hook 無 LLM）。
裁判無授權副作用；規格檔與任務無法唯一對應時消費端必回 uncertain 不得 block。
config: workflow/config.json → acceptance_spec；enabled=false 一鍵關。
standalone 仿 version_guard.py；never-crash 降級靜默。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

CLAUDE_DIR = Path.home() / ".claude"
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
CONFIG_PATH = WORKFLOW_DIR / "config.json"
SIDECAR_DIR = WORKFLOW_DIR / "acceptance-spec"

# 規格檔路徑指紋：<專案根>/.claude/verify/acceptance-*.md
_SPEC_PATH_RE = re.compile(r"/\.claude/verify/acceptance-[^/]+\.md$", re.IGNORECASE)

_WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}

_SPEC_FORMAT_GUIDE = (
    "格式（極簡三段，勿加章節）：\n"
    "```\n"
    "---\n"
    "task_slug: <任務主題 kebab-case>\n"
    "session_id: {sid}\n"
    "created_at: <今日 YYYY-MM-DD>\n"
    "source: {source}\n"
    "status: open\n"
    "---\n"
    "## 必須發生\n"
    "- <需求的每一項，逐條可核對>\n"
    "## 禁止發生\n"
    "- <紅線，例：不動某檔 / 不翻案已定決策>\n"
    "## 驗證指令\n"
    "- <可直接執行的指令或檢查步驟>\n"
    "```\n"
    "收尾時逐項自核：全過 → status 改 done 並移入同目錄 done/ 子資料夾；"
    "未全過 → 收尾報告誠實列出未過項。"
)


# ─── Config ──────────────────────────────────────────────────────────────────


def _load_config() -> Dict[str, Any]:
    try:
        full = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return full.get("acceptance_spec", {})
    except (json.JSONDecodeError, OSError):
        return {}


# ─── Sidecar（每 session 每型提醒至多一次）────────────────────────────────────


def _sidecar_path(session_id: str) -> Path:
    return SIDECAR_DIR / f"{session_id}.json"


def read_sidecar(session_id: str) -> Dict[str, Any]:
    try:
        return json.loads(_sidecar_path(session_id).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_sidecar(session_id: str, data: Dict[str, Any]) -> None:
    try:
        SIDECAR_DIR.mkdir(parents=True, exist_ok=True)
        p = _sidecar_path(session_id)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except OSError as e:
        sys.stderr.write(f"[acceptance_spec] sidecar write: {e}\n")


# ─── 判定 ────────────────────────────────────────────────────────────────────


def is_spec_file_path(file_path: str) -> bool:
    if not file_path:
        return False
    return bool(_SPEC_PATH_RE.search(file_path.replace("\\", "/")))


def count_session_modified_files(
    session_id: str, exclude_substrings: List[str]
) -> int:
    """讀 guardian state 的 modified_files（已去重/已濾 ephemeral），
    數本 session、非排除路徑的相異檔數。state 缺 → 0（fail-open 不提醒）。"""
    try:
        state = json.loads(
            (WORKFLOW_DIR / f"state-{session_id}.json").read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return 0
    seen = set()
    for m in state.get("modified_files", []):
        if not isinstance(m, dict):
            continue
        if m.get("session_id", session_id) != session_id:
            continue
        norm = str(m.get("path", "")).replace("\\", "/")
        if not norm or any(part in norm for part in exclude_substrings):
            continue
        seen.add(norm)
    return len(seen)


def plan_looks_rejected(tool_response: Any) -> bool:
    """ExitPlanMode 被否決的保守偵測（正常情況否決不會走到 PostToolUse，防禦性）。"""
    text = (
        json.dumps(tool_response, ensure_ascii=False)
        if isinstance(tool_response, (dict, list))
        else str(tool_response or "")
    )
    return "reject" in text.lower()


# ─── Advisory 文案 ────────────────────────────────────────────────────────────


def build_plan_advisory(session_id: str, cwd: str) -> str:
    guide = _SPEC_FORMAT_GUIDE.format(sid=session_id or "<session_id>", source="plan")
    return (
        "[Guardian:AcceptanceSpec] 本任務經 plan-mode 確認 → 屬分級線以上。"
        "動工前先把「做完的定義」落成驗收規格檔（跨 session 不蒸發、收尾自核依據）：\n"
        f"路徑：`<專案根>/.claude/verify/acceptance-<task-slug>.md`"
        f"（專案根以 git root 為準；目前 cwd：{cwd or '<未知>'}）\n"
        "內容從剛獲同意的 plan 逐項轉出，不重問 user、不加互動輪。\n"
        + guide
        + "\n例外：純研究/問答型 plan（不產生 repo 修改）可不落檔，說明一句即可。"
    )


def build_multifile_advisory(session_id: str, cwd: str, n_files: int) -> str:
    guide = _SPEC_FORMAT_GUIDE.format(sid=session_id or "<session_id>", source="multifile")
    return (
        f"[Guardian:AcceptanceSpec] 本任務已修改 {n_files} 個檔案且尚無驗收規格檔 → "
        "建議現在補一份（事後補仍有價值：收尾逐項自核 + 跨 session 接手時「做完的定義」不蒸發）。\n"
        f"路徑：`<專案根>/.claude/verify/acceptance-<task-slug>.md`"
        f"（專案根以 git root 為準；目前 cwd：{cwd or '<未知>'}）\n"
        + guide
        + "\n本提醒每 session 僅此一次；若當前任務性質不需驗收清單（如批量機械修改），可忽略。"
    )


# ─── PostToolUse handler ─────────────────────────────────────────────────────


def handle_post_tool_use(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    session_id = input_data.get("session_id", "")
    tool_name = input_data.get("tool_name", "")
    cwd = input_data.get("cwd", "")
    if not session_id:
        sys.exit(0)

    if tool_name == "ExitPlanMode":
        if plan_looks_rejected(input_data.get("tool_response", "")):
            sys.exit(0)
        sc = read_sidecar(session_id)
        if sc.get("plan_prompted"):
            sys.exit(0)
        sc["plan_prompted"] = True
        write_sidecar(session_id, sc)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": build_plan_advisory(session_id, cwd),
            }
        }, ensure_ascii=False))
        sys.exit(0)

    if tool_name not in _WRITE_TOOLS:
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = ""
    if isinstance(tool_input, dict):
        file_path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")

    # (3) 規格檔落盤 → 記 sidecar，永久抑制本 session 的 multifile 提醒
    if is_spec_file_path(file_path):
        sc = read_sidecar(session_id)
        paths = sc.setdefault("spec_paths", [])
        norm = file_path.replace("\\", "/")
        if norm not in paths:
            paths.append(norm)
            write_sidecar(session_id, sc)
        sys.exit(0)

    # (2) 多檔任務一次性建議（plan 型已提醒過 / 已有規格檔 / 已建議過 → 不再提）
    sc = read_sidecar(session_id)
    if sc.get("plan_prompted") or sc.get("multifile_advised") or sc.get("spec_paths"):
        sys.exit(0)
    min_files = int(config.get("min_files_trigger", 3))
    excludes = config.get("count_exclude_substrings", []) or []
    n = count_session_modified_files(session_id, excludes)
    if n < min_files:
        sys.exit(0)
    sc["multifile_advised"] = True
    write_sidecar(session_id, sc)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": build_multifile_advisory(session_id, cwd, n),
        }
    }, ensure_ascii=False))
    sys.exit(0)


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")

    config = _load_config()
    if not config.get("enabled", False):
        sys.exit(0)

    try:
        input_data = json.loads(sys.stdin.buffer.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if input_data.get("hook_event_name", "") != "PostToolUse":
        sys.exit(0)

    try:
        handle_post_tool_use(input_data, config)
    except SystemExit:
        raise
    except Exception as e:  # never crash — 降級靜默
        sys.stderr.write(f"[acceptance_spec] {type(e).__name__}: {e}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
