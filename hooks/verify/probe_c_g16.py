"""probe_c_g16.py：用真的 hook 入口（hooks/workflow-guardian.py，一個事件一個行程、stdin 餵 JSON）走提問閘（C-G16）。

情境：
  P1 沒推薦的提問照放行，下一個工具結果附一行提醒（印 ASK_NEEDS_RECOMMENDATION 與照抄範例）；照抄加 (Recommended) 也放行
  P2 【收尾放行確認】固定兩選項的放行題不因推薦被擋
  P5 部位表兩部位：讀了 A 部位的檔、問 B 部位某檔的改法 → 下一個工具結果照提醒（讀了別的部位不算）；讀過 B 再問 → 不提醒（裁定 #39）
寫碼守門明開（WG_V6=1；提問閘只在守門開時跑，送法照 RULE_MODE＝提醒）。
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
RELEASE_TAG, OPT_RELEASE, OPT_KEEP = "【收尾放行確認】", "放行這一回合", "繼續擋，先修好"


def hook(event: str, **fields) -> dict:
    payload = {"hook_event_name": event, "session_id": SID, "cwd": str(PROJ), "transcript_path": str(TP), **fields}
    env = {**os.environ, "WG_CLAUDE_DIR": str(ROOT), "WG_TEST_LOGS_DIR": str(BASE / "logs"),
           "USERPROFILE": str(BASE / "home"), "HOME": str(BASE / "home"), "PYTHONIOENCODING": "utf-8", "WG_V6": "1"}
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


def after() -> dict:
    """提問之後的下一個工具結果（唯讀 Bash 的 PostToolUse）：提問閘的提醒在這裡送。"""
    return hook("PostToolUse", tool_name="Bash", tool_input={"command": "git status"}, tool_response={"stdout": ""})


def ask(question: str, labels) -> dict:
    return {"questions": [{"question": question, "header": "選擇", "multiSelect": False,
                           "options": [{"label": l, "description": f"{l} 的說明"} for l in labels]}]}


def main() -> int:
    if BASE.exists():
        shutil.rmtree(BASE)
    (ROOT / "workflow").mkdir(parents=True)
    (ROOT / "workflow" / "config.json").write_text(json.dumps({"vector_search": {"enabled": False}}), encoding="utf-8")
    (BASE / "home" / ".claude" / "Logs").mkdir(parents=True)
    (BASE / "logs").mkdir()
    (PROJ / ".git").mkdir(parents=True)
    (PROJ / ".claude").mkdir()
    (PROJ / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        "| `src/a/` | 甲部位 | 無 | 無 |\n| `src/b/` | 乙部位 | 無 | 無 |\n", encoding="utf-8")
    for rel in ("src/a/one.py", "src/a/two.py", "src/b/x.py", "src/b/y.py"):
        (PROJ / rel).parent.mkdir(parents=True, exist_ok=True)
        (PROJ / rel).write_text("x = 1\n", encoding="utf-8")
    TP.write_text("", encoding="utf-8")
    steps = []

    def step(name: str, ok: bool, detail: str = "") -> None:
        steps.append((name, ok))
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f"\n       {detail[:500]}" if not ok and detail else ""))

    hook("UserPromptSubmit", prompt="幫我決定匯出要先做哪個格式")

    out = hook("PreToolUse", tool_name="AskUserQuestion", tool_input=ask("要先做哪個格式？", ["CSV", "XLSX"]), tool_use_id="p1a")
    nxt = after()
    step("P1 沒推薦照放行、下一個工具結果提醒規則名與照抄範例",
         not deny(out) and "ASK_NEEDS_RECOMMENDATION" in ctx(nxt) and '"label": "CSV (Recommended)"' in ctx(nxt),
         json.dumps([out, nxt], ensure_ascii=False))
    ok_ask = ask("要先做哪個格式？", ["CSV (Recommended)", "XLSX"])
    out = hook("PreToolUse", tool_name="AskUserQuestion", tool_input=ok_ask, tool_use_id="p1b")
    step("P1 照抄加 (Recommended) 放行", not deny(out), json.dumps(out, ensure_ascii=False))

    rel = ask(f"{RELEASE_TAG} 要放行這一回合嗎？", [OPT_RELEASE, OPT_KEEP])
    out = hook("PreToolUse", tool_name="AskUserQuestion", tool_input=rel, tool_use_id="p2")
    step("P2 放行確認題不因推薦被擋", not deny(out), json.dumps(out, ensure_ascii=False))

    def read(rel: str) -> None:
        hook("PostToolUse", tool_name="Read", tool_input={"file_path": str(PROJ / rel)}, tool_response={"type": "text"})

    for rel in ("src/a/one.py", "src/a/two.py"):          # 第一次讀注入導讀卡，第二次才記進 part_files_read
        read(rel)
    q5 = ask(f"{PROJ / 'src' / 'b' / 'x.py'} 要用哪個改法？", ["A (Recommended)", "B"])
    out = hook("PreToolUse", tool_name="AskUserQuestion", tool_input=q5, tool_use_id="p5a")
    nxt = after()
    step("P5 讀 A 問 B：照放行，下一個工具結果照提醒（只讀了別的部位不算讀過）",
         not deny(out) and "ASK_OVERVIEW_BEFORE_DECISION" in ctx(nxt) and "先讀過部位檔再問" in ctx(nxt),
         json.dumps([out, nxt], ensure_ascii=False))
    for rel in ("src/b/x.py", "src/b/y.py"):
        read(rel)
    out = hook("PreToolUse", tool_name="AskUserQuestion", tool_input=q5, tool_use_id="p5b")
    nxt = after()
    step("P5 讀過 B 再問：不提醒", not deny(out) and "先讀過部位檔再問" not in ctx(out) + ctx(nxt),
         json.dumps([out, nxt], ensure_ascii=False))

    fails = sum(1 for _n, ok in steps if not ok)
    print(f"C_G16_PROBE DONE steps={len(steps)} fail={fails} sid={SID}")
    print(f"C_G16_PROBE_CHECK {'PASS' if not fails else 'FAIL'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
