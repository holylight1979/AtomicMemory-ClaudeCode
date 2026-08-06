"""smoke_plan_review.py — plan_review 端到端冒煙（真打 codex，手動執行）。

刻意不用 verify_ 前綴：run_verify/pytest 不收集，保持離線確定性。

用法：
  python tools/codex-companion/verify/smoke_plan_review.py [plan_md_path]

流程：建臨時 session state（trace 含指向計畫檔的 Write 事件，模擬 plan-mode
工作流）→ 組 turn_data 以 stdin 餵 audit.py（與 hook spawn 同協定）→ 讀
assessment JSON 印 codex 原話 → 斷言回報不是「未收到正文」型 → 清理臨時檔。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path(__file__).resolve().parents[3]
COMP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(COMP_DIR))

import state as companion_state  # noqa: E402

WORKFLOW_DIR = CLAUDE_DIR / "workflow"
AUDIT_SCRIPT = COMP_DIR / "audit.py"

# codex 收到的輸入若仍缺正文，回報會落在這些型態（歷史實案原話）
_BAD_PHRASES = (
    "未提供實作計畫", "未提供計畫正文", "未收到", "no plan content",
    "只顯示寫入", "僅是探索性", "未呈現檔案內容", "尚無可執行的實作計畫",
)


def main() -> int:
    plan_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        CLAUDE_DIR / "plans" / "peaceful-yawning-shannon.md"
    )
    if not plan_path.is_file():
        print(f"FAIL: plan file not found: {plan_path}")
        return 1
    size = len(plan_path.read_text(encoding="utf-8-sig"))
    print(f"plan artifact: {plan_path} ({size} chars)")

    sid = f"smoke-plan-review-{os.getpid()}"
    turn_index = 1
    try:
        companion_state.ensure_state(sid, str(CLAUDE_DIR))
        companion_state.set_user_goal(sid, "冒煙測試：驗證 plan_review 收到計畫正文")
        companion_state.append_event(sid, {
            "type": "tool_use", "tool": "Bash",
            "input": "git status", "output_summary": "stdout: clean", "path": "",
        })
        companion_state.append_event(sid, {
            "type": "tool_use", "tool": "Write",
            "input": str(plan_path), "output_summary": "", "path": str(plan_path),
        })

        turn_data = {
            "session_id": sid,
            "turn_index": turn_index,
            "assessment_type": "plan_review",
            "cwd": str(CLAUDE_DIR),
            "context": {"artifact_path": str(plan_path)},
        }
        print("invoking audit.py (codex exec, ~60-130s)…")
        proc = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            input=json.dumps(turn_data, ensure_ascii=False).encode("utf-8"),
            capture_output=True, timeout=180,
        )
        sys.stderr.write(proc.stderr.decode("utf-8", errors="replace"))

        out_path = WORKFLOW_DIR / f"companion-assessment-{sid}-t{turn_index}-plan_review.json"
        if not out_path.is_file():
            print(f"FAIL: assessment file not written: {out_path}")
            return 1
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assessment = data.get("assessment", {})

        print("\n── codex 原話（人工複核）──")
        print(json.dumps(assessment, ensure_ascii=False, indent=2))

        if assessment.get("status") == "error":
            print("\nFAIL: assessment status=error（codex 未成功執行，非輸入問題）")
            return 1
        blob = json.dumps(assessment, ensure_ascii=False)
        hits = [ph for ph in _BAD_PHRASES if ph in blob]
        if hits:
            print(f"\nFAIL: codex 仍回報「未收到正文」型內容：{hits}")
            return 1
        print("\nPASS: codex 收到計畫正文（回報非「未收到正文」型）")
        return 0
    finally:
        companion_state.cleanup(sid)


if __name__ == "__main__":
    sys.exit(main())
