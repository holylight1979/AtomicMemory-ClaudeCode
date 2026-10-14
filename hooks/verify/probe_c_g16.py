"""probe_c_g16.py：用真的 hook 入口（hooks/workflow-guardian.py，一個事件一個行程、stdin 餵 JSON）走提問閘（C-G16）。

情境：
  P1 沒推薦的提問被 PreToolUse 擋（印 ASK_NEEDS_RECOMMENDATION 與照抄範例）→ 照抄加 (Recommended) 放行
  P2 【收尾放行確認】固定兩選項的放行題不因推薦被擋
  P3 還沒有目標樹（記憶知識類）提問不擋，PostToolBatch 審計記「提問未掛目標（知識類）」
  P4 寫碼類目標樹：題目沒指節點被擋（印 ASK_LINKED_TO_GOAL）→ 引用節點原文 8 字以上放行
資料根（WG_CLAUDE_DIR）、守門紀錄（WG_TEST_LOGS_DIR）、家目錄與探針專案都放在 <本樹>/workflow/need-goal/_probe_c_g16/
（不進版控），每次跑前清空；程式碼用本檔所在的樹，不碰 live。
怎麼跑：python -X utf8 hooks/verify/probe_c_g16.py   （尾行 C_G16_PROBE_CHECK PASS|FAIL）
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
BASE = TREE / "workflow" / "need-goal" / "_probe_c_g16"
ROOT = BASE / "root"
PROJ = BASE / "proj"
SID = f"probe-cg16-{uuid.uuid4().hex[:8]}"
TP = BASE / "transcript.jsonl"
FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
NG = "mcp__workflow-guardian__need_goal"
RELEASE_TAG, OPT_RELEASE, OPT_KEEP = "【收尾放行確認】", "放行這一回合", "繼續擋，先修好"


def hook(event: str, **fields) -> dict:
    payload = {"hook_event_name": event, "session_id": SID, "cwd": str(PROJ), "transcript_path": str(TP), **fields}
    env = {**os.environ, "WG_CLAUDE_DIR": str(ROOT), "WG_TEST_LOGS_DIR": str(BASE / "logs"),
           "USERPROFILE": str(BASE / "home"), "HOME": str(BASE / "home"), "PYTHONIOENCODING": "utf-8"}
    env.pop("CLAUDE_COMPANION_JUDGE", None)
    r = subprocess.run([sys.executable, "-X", "utf8", str(GUARDIAN)], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       capture_output=True, env=env, cwd=str(PROJ), creationflags=FLAGS, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"{event} hook exit {r.returncode}：{r.stderr.decode('utf-8', 'replace')[-600:]}")
    lines = [ln for ln in r.stdout.decode("utf-8", "replace").splitlines() if ln.strip().startswith("{")]
    return json.loads(lines[-1]) if lines else {}


def deny(out: dict) -> str:
    hs = out.get("hookSpecificOutput") or {}
    return hs.get("permissionDecisionReason") or "" if hs.get("permissionDecision") == "deny" else ""


def ask(question: str, labels) -> dict:
    return {"questions": [{"question": question, "header": "選擇", "multiSelect": False,
                           "options": [{"label": l, "description": f"{l} 的說明"} for l in labels]}]}


def audits() -> list:
    p = BASE / "logs" / "guard-need_goal.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    return [r for r in rows if r.get("event") == "ask_audit" and r.get("session_id") == SID]


def main() -> int:
    if BASE.exists():
        shutil.rmtree(BASE)
    (ROOT / "workflow").mkdir(parents=True)
    (ROOT / "workflow" / "config.json").write_text(json.dumps({"vector_search": {"enabled": False}}), encoding="utf-8")
    (BASE / "home" / ".claude" / "Logs").mkdir(parents=True)
    (BASE / "logs").mkdir()
    (PROJ / ".git").mkdir(parents=True)
    TP.write_text("", encoding="utf-8")
    steps = []

    def step(name: str, ok: bool, detail: str = "") -> None:
        steps.append((name, ok))
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f"\n       {detail[:500]}" if not ok and detail else ""))

    hook("UserPromptSubmit", prompt="幫我決定匯出要先做哪個格式")

    out = hook("PreToolUse", tool_name="AskUserQuestion", tool_input=ask("要先做哪個格式？", ["CSV", "XLSX"]), tool_use_id="p1a")
    d = deny(out)
    step("P1 沒推薦被擋、印規則名與照抄範例", "ASK_NEEDS_RECOMMENDATION" in d and '"label": "CSV (Recommended)"' in d,
         json.dumps(out, ensure_ascii=False))
    ok_ask = ask("要先做哪個格式？", ["CSV (Recommended)", "XLSX"])
    out = hook("PreToolUse", tool_name="AskUserQuestion", tool_input=ok_ask, tool_use_id="p1b")
    step("P1 照抄加 (Recommended) 放行", not deny(out), json.dumps(out, ensure_ascii=False))

    rel = ask(f"{RELEASE_TAG} 要放行這一回合嗎？", [OPT_RELEASE, OPT_KEEP])
    out = hook("PreToolUse", tool_name="AskUserQuestion", tool_input=rel, tool_use_id="p2")
    step("P2 放行確認題不因推薦被擋", not deny(out), json.dumps(out, ensure_ascii=False))

    hook("PostToolBatch", tool_calls=[{"tool_name": "AskUserQuestion", "tool_input": ok_ask, "tool_use_id": "p1b"}])
    notes = [a.get("note") for a in audits()]
    step("P3 沒樹提問不擋、審計記「提問未掛目標（知識類）」", notes == ["提問未掛目標（知識類）"], json.dumps(audits(), ensure_ascii=False))

    hook("PostToolUse", tool_name=NG, tool_input={"action": "set", "goal": "匯出能出 CSV，舊的 JSON 匯出不能壞"},
         tool_response={"content": [{"type": "text", "text": "[NeedGoal] set 已收到"}]})
    hook("PostToolUse", tool_name=NG, tool_input={"action": "add", "items": [{"text": "CSV 欄位跟 JSON 用同一份欄位定義"}]},
         tool_response={"content": [{"type": "text", "text": "[NeedGoal] add 已收到"}]})
    goal = ROOT / "workflow" / "need-goal" / f"{SID}.json"
    doc = json.loads(goal.read_text(encoding="utf-8"))
    doc["trees"][doc["active"]]["kind"] = "code"          # 改過程式檔的樹（探針直接標，不走改檔流程）
    goal.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    out = hook("PreToolUse", tool_name="AskUserQuestion", tool_input=ask("欄位要放哪？", ["A (Recommended)", "B"]), tool_use_id="p4a")
    step("P4 寫碼類題目沒指節點被擋、印 ASK_LINKED_TO_GOAL", "ASK_LINKED_TO_GOAL" in deny(out), json.dumps(out, ensure_ascii=False))
    out = hook("PreToolUse", tool_name="AskUserQuestion",
               tool_input=ask("為了「欄位跟 JSON 用同一份」，欄位要放哪？", ["A (Recommended)", "B"]), tool_use_id="p4b")
    step("P4 引用節點原文 8 字以上放行", not deny(out), json.dumps(out, ensure_ascii=False))

    fails = sum(1 for _n, ok in steps if not ok)
    print(f"C_G16_PROBE DONE steps={len(steps)} fail={fails} sid={SID}")
    print(f"C_G16_PROBE_CHECK {'PASS' if not fails else 'FAIL'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
