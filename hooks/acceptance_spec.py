"""acceptance_spec.py — 驗收規格檔登記（PostToolUse；由 guardian handlers/post_tool_use.py
呼叫 run()，同程序不另起 Python；保留 __main__ 可獨跑＝回滾路徑）。

做什麼：AI 寫入驗收規格檔 `<專案根>/.claude/verify/acceptance-<slug>.md` 時，把路徑記進
sidecar `workflow/acceptance-spec/<sid>.json` 的 spec_paths；驗收裁判（codex_companion）憑它找這個任務的
驗收標準。不送任何字給 AI：規格檔由 AI 自己決定寫不寫，這裡只記帳。
裁判無授權副作用；規格檔與任務無法唯一對應時消費端必回 uncertain 不得 block。
config: workflow/config.json → acceptance_spec；enabled=false 一鍵關。
never-crash 降級靜默（guardian 端 try/except 隔離、錯誤只進 debug log）。
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict

_LIB_DIR = str(Path(__file__).resolve().parents[1] / "lib")   # 程式碼：資料根算法從本樹載
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from project_root import claude_data_dir  # noqa: E402

CLAUDE_DIR = claude_data_dir()   # 使用者資料根（WG_CLAUDE_DIR 或 ~/.claude），和 hooks 同一支算法
WORKFLOW_DIR = CLAUDE_DIR / "workflow"
CONFIG_PATH = WORKFLOW_DIR / "config.json"
SIDECAR_DIR = WORKFLOW_DIR / "acceptance-spec"

# 規格檔路徑指紋：<專案根>/.claude/verify/acceptance-*.md
_SPEC_PATH_RE = re.compile(r"/\.claude/verify/acceptance-[^/]+\.md$", re.IGNORECASE)

_WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}


# ─── Config ──────────────────────────────────────────────────────────────────


def _load_config() -> Dict[str, Any]:
    try:
        full = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return full.get("acceptance_spec", {})
    except (json.JSONDecodeError, OSError):
        return {}


# ─── Sidecar（本 session 登記的規格檔路徑）────────────────────────────────────


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
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
        tmp.replace(p)
    except OSError as e:
        sys.stderr.write(f"[acceptance_spec] sidecar write: {e}\n")


# ─── 判定 ────────────────────────────────────────────────────────────────────


def is_spec_file_path(file_path: str) -> bool:
    if not file_path:
        return False
    return bool(_SPEC_PATH_RE.search(file_path.replace("\\", "/")))


# ─── PostToolUse 登記（不讀 stdin、不 print、不 exit）──────────────────────────


def run(input_data: Dict[str, Any], config: Dict[str, Any]) -> None:
    """寫入的是驗收規格檔 → 路徑記進本 session 的 sidecar spec_paths（同一路徑只記一次）。config＝config.json 的
    acceptance_spec 區塊，enabled 開關在此判定，standalone main 與 guardian PostToolUse 併入共用同一路徑。
    例外不在此攔——由呼叫端隔離（standalone：stderr；guardian：debug log）。"""
    if not config.get("enabled", False):
        return
    session_id = input_data.get("session_id", "")
    if not session_id or input_data.get("tool_name", "") not in _WRITE_TOOLS:
        return
    tool_input = input_data.get("tool_input", {})
    file_path = ""
    if isinstance(tool_input, dict):
        file_path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
    if not is_spec_file_path(file_path):
        return
    sc = read_sidecar(session_id)
    paths = sc.setdefault("spec_paths", [])
    norm = file_path.replace("\\", "/")
    if norm not in paths:
        paths.append(norm)
        write_sidecar(session_id, sc)


# ─── Main（standalone 入口；平時由 guardian PostToolUse 呼叫 run()，本入口供獨跑／回滾）──


def main() -> None:
    # 備援裁判子 session（headless claude judge）內不登記
    if os.environ.get("CLAUDE_COMPANION_JUDGE"):
        sys.exit(0)

    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")

    config = _load_config()

    try:
        input_data = json.loads(sys.stdin.buffer.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if input_data.get("hook_event_name", "") != "PostToolUse":
        sys.exit(0)

    try:
        run(input_data, config)
    except Exception as e:  # never crash — 降級靜默
        sys.stderr.write(f"[acceptance_spec] {type(e).__name__}: {e}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
