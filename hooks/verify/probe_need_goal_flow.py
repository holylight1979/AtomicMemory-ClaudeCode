"""probe_need_goal_flow.py：用真的 hook 入口（hooks/workflow-guardian.py，一個事件一個行程、stdin 餵 JSON）走一遍需求目標流程。

情境：使用者提需求 → 沒目標樹改程式被擋 → need_goal set／add → 第一次碰部位（導讀卡附樹）→ 讀部位檔 → 定位四行 → 放行 →
改檔欠對照 → Stop 擋 (f1) → update 交一句進度 → 跑驗證印哨兵（收據蓋號）→ reconcile 完整對照 → 宣告完成時 (f1)(f2) 都不再擋。
資料根（WG_CLAUDE_DIR）、守門紀錄（WG_TEST_LOGS_DIR）、家目錄（USERPROFILE／HOME）與探針專案都放在
<本樹>/workflow/need-goal/_probe/（不進版控、不在系統暫存目錄，所以改檔不會被當暫存檔），向量檢索關掉；每次跑前清空；
程式碼用本檔所在的樹。不碰 live：跑完用尾行的 sid 搜 live 的 Logs／workflow 應該搜不到。
怎麼跑：python -X utf8 hooks/verify/probe_need_goal_flow.py   （尾行 NEED_GOAL_PROBE_CHECK PASS|FAIL）
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

TREE = Path(__file__).resolve().parents[2]
GUARDIAN = TREE / "hooks" / "workflow-guardian.py"
BASE = TREE / "workflow" / "need-goal" / "_probe"
ROOT = BASE / "root"
PROJ = BASE / "proj"
SID = f"probe-{uuid.uuid4().hex[:8]}"
TP = BASE / "transcript.jsonl"
FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
NG = "mcp__workflow-guardian__need_goal"


def hook(event: str, **fields) -> dict:
    payload = {"hook_event_name": event, "session_id": SID, "cwd": str(PROJ), "transcript_path": str(TP), **fields}
    # 資料根、守門紀錄、家目錄都換到探針目錄：守門紀錄預設寫家目錄的 .claude/Logs，向量服務啟動器用家目錄找 Logs
    env = {**os.environ, "WG_CLAUDE_DIR": str(ROOT), "WG_TEST_LOGS_DIR": str(BASE / "logs"),
           "USERPROFILE": str(BASE / "home"), "HOME": str(BASE / "home"), "PYTHONIOENCODING": "utf-8"}
    env.pop("CLAUDE_COMPANION_JUDGE", None)
    r = subprocess.run([sys.executable, "-X", "utf8", str(GUARDIAN)], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       capture_output=True, env=env, cwd=str(PROJ), creationflags=FLAGS, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"{event} hook exit {r.returncode}：{r.stderr.decode('utf-8', 'replace')[-600:]}")
    lines = [ln for ln in r.stdout.decode("utf-8", "replace").splitlines() if ln.strip().startswith("{")]
    return json.loads(lines[-1]) if lines else {}


def ctx(out: dict) -> str:
    return (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""


def deny(out: dict) -> str:
    hs = out.get("hookSpecificOutput") or {}
    return hs.get("permissionDecisionReason") or "" if hs.get("permissionDecision") == "deny" else ""


def say(text: str) -> None:
    with open(TP, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}},
                           ensure_ascii=False) + "\n")


def user(text: str) -> None:
    with open(TP, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"content": text}}, ensure_ascii=False) + "\n")


def main() -> int:
    if BASE.exists():
        shutil.rmtree(BASE)
    (ROOT / "workflow").mkdir(parents=True)
    (ROOT / "workflow" / "config.json").write_text(json.dumps({"vector_search": {"enabled": False}}), encoding="utf-8")
    (BASE / "home" / ".claude" / "Logs").mkdir(parents=True)
    (BASE / "logs").mkdir()
    (PROJ / ".git").mkdir(parents=True)
    (PROJ / ".claude" / "memory" / "shared").mkdir(parents=True)
    (PROJ / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n| `src\\` | 匯出 | `匯出導讀` | 有 |\n", encoding="utf-8")
    (PROJ / ".claude" / "memory" / "shared" / "匯出導讀.md").write_text(
        "# 匯出導讀\n\n## 知識\n\n- [臨] **已知病灶**：欄位順序寫死在兩處\n", encoding="utf-8")
    (PROJ / "src").mkdir()
    target = PROJ / "src" / "export.py"
    target.write_text("def export():\n    return []\n", encoding="utf-8")
    TP.write_text("", encoding="utf-8")
    steps = []

    def step(name: str, ok: bool, detail: str = "") -> None:
        steps.append((name, ok))
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f"\n       {detail[:400]}" if not ok and detail else ""))

    prompt = "幫我讓匯出功能支援 CSV，舊的 JSON 匯出不能壞"
    user(prompt)
    out = hook("UserPromptSubmit", prompt=prompt)
    step("UPS 第一則訊息提醒先寫目標", "need_goal(action=set" in ctx(out), ctx(out))
    edit = {"file_path": str(target), "old_string": "return []", "new_string": "return ['csv']"}
    out = hook("PreToolUse", tool_name="Edit", tool_input=edit)
    step("沒樹改程式被擋", deny(out).startswith("[NeedGoal]"), json.dumps(out, ensure_ascii=False))
    say("先寫目標")
    out = hook("PostToolUse", tool_name=NG, tool_input={"action": "set", "goal": "匯出能出 CSV，JSON 照舊"},
               tool_response={"content": [{"type": "text", "text": "[NeedGoal] set 已收到"}]})
    step("set 收下並送回樹", "set 收下" in ctx(out) and "T1" in ctx(out), ctx(out))
    out = hook("PostToolUse", tool_name=NG, tool_input={"action": "add", "items": [{"text": "CSV 欄位跟 JSON 同一份定義"},
                                                                                  {"text": "舊 JSON 匯出不變"}]},
               tool_response={"content": [{"type": "text", "text": "[NeedGoal] add 已收到"}]})
    step("add 收下 T1.1 T1.2", "T1.1" in ctx(out) and "T1.2" in ctx(out), ctx(out))
    out = hook("PreToolUse", tool_name="Edit", tool_input=edit)
    step("第一次碰部位：導讀卡注入並附目標樹", "[NeedGoal] 目前的需求目標" in deny(out) and "匯出導讀" in deny(out), deny(out))
    hook("PostToolUse", tool_name="Read", tool_input={"file_path": str(target)}, tool_response={"type": "text"})
    say("定位｜部位：匯出：export.py\n定位｜根因層：欄位定義層\n定位｜前例：欄位順序寫死在兩處")
    out = hook("PreToolUse", tool_name="Edit", tool_input=edit)
    step("只交三行：要第四行並列出節點", "沒交第四行" in deny(out) and "T1.1" in deny(out), deny(out))
    say("定位｜部位：匯出：export.py\n定位｜根因層：欄位定義層\n定位｜前例：欄位順序寫死在兩處\n定位｜目標：T1.1（欄位定義只留一份）")
    out = hook("PreToolUse", tool_name="Edit", tool_input=edit)
    step("定位四行後放行", not deny(out), json.dumps(out, ensure_ascii=False))
    target.write_text("def export():\n    return ['csv']\n", encoding="utf-8")
    hook("PostToolUse", tool_name="Edit", tool_input=edit, tool_response={"filePath": str(target)})
    say("改好了一半，先停")
    out = hook("Stop", last_assistant_message="改好了一半，先停", stop_hook_active=False)
    step("Stop 擋 (f1) 改了程式還沒回頭對照（不看措辭）", "(f1)" in (out.get("reason") or ""), json.dumps(out, ensure_ascii=False))
    out = hook("PostToolUse", tool_name=NG, tool_input={"action": "update", "items": [
        {"id": "T1.1", "status": "doing", "why": "export.py 改成同一份欄位定義，CSV 更接近了"}]},
               tool_response={"content": [{"type": "text", "text": "[NeedGoal] update 已收到"}]})
    step("update 清掉待對照", "清掉 1 筆待對照" in ctx(out), ctx(out))
    user("繼續")
    hook("UserPromptSubmit", prompt="繼續")
    cmd = "python -X utf8 -m pytest -q tests"
    hook("PostToolUse", tool_name="Bash", tool_input={"command": cmd},
         tool_response={"stdout": "3 passed\nEXPORT_CHECK PASS\n", "stderr": "", "exit_code": 0})
    doc = json.loads((ROOT / "workflow" / "need-goal" / f"{SID}.json").read_text(encoding="utf-8"))
    rno = doc["receipts"][-1]["seq"] if doc.get("receipts") else None
    step("收據蓋號", rno is not None, json.dumps(doc.get("receipts"), ensure_ascii=False))
    ev = [{"kind": "receipt", "ref": f"R{rno}", "level": "measured"}]
    out = hook("PostToolUse", tool_name=NG, tool_input={"action": "reconcile", "items": [
        {"id": "T1", "status": "done", "evidence": ev},
        {"id": "T1.1", "status": "done", "evidence": ev},
        {"id": "T1.2", "status": "partial", "evidence": [{"kind": "file", "ref": str(target), "level": "read"}],
         "followup": "補一個 JSON 匯出不變的案例"}]},
               tool_response={"content": [{"type": "text", "text": "[NeedGoal] reconcile 已收到"}]})
    step("reconcile 收下", "完整對照收下" in ctx(out), ctx(out))
    say("全部完成。")
    out = hook("Stop", last_assistant_message="全部完成。", stop_hook_active=False)
    reason = out.get("reason") or ""
    step("宣告完成時 (f1)(f2) 都不擋", "(f1)" not in reason and "(f2)" not in reason, reason)
    passed = sum(1 for _, ok in steps if ok)
    print(f"NEED_GOAL_PROBE DONE steps={len(steps)} passed={passed} sid={SID}")
    print("NEED_GOAL_PROBE_CHECK " + ("PASS" if passed == len(steps) else "FAIL"))
    return 0 if passed == len(steps) else 1


if __name__ == "__main__":
    sys.exit(main())
