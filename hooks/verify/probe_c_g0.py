"""probe_c_g0.py：用真的 hook 入口（hooks/workflow-guardian.py，一個事件一個行程、stdin 餵 JSON）走 G0 綜觀的兩道閘。

情境：需求目標樹 T1（T1.1、T1.2）→ 改【匯出】部位：第四行沒寫角色被擋（LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES）→
補交有角色、兩個根因候選＋理由的四行放行 → 改【介面】部位（掛 T1.2）→ T1.2 後來放棄，介面的改動等於沒掛目標 →
完整對照交齊後宣告完成，Stop 擋 (f3)（EDITED_PART_NEEDS_GOAL_NODE，列沒掛的部位與檔）→ 補交介面的四行指到 T1.1 → 放行。
資料根（WG_CLAUDE_DIR）、守門紀錄（WG_TEST_LOGS_DIR）、家目錄（USERPROFILE／HOME）與探針專案都放在
<本樹>/workflow/need-goal/_probe_cg0/（不進版控、不在系統暫存目錄），向量檢索關掉；每次跑前清空；程式碼用本檔所在的樹。
不碰 live：跑完用尾行的 sid 搜 live 的 Logs／workflow 應該搜不到。
怎麼跑：python -X utf8 hooks/verify/probe_c_g0.py   （尾行 C_G0_PROBE_CHECK PASS|FAIL）
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
BASE = TREE / "workflow" / "need-goal" / "_probe_cg0"
ROOT = BASE / "root"
PROJ = BASE / "proj"
SID = f"probe-cg0-{uuid.uuid4().hex[:8]}"
TP = BASE / "transcript.jsonl"
FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
NG = "mcp__workflow-guardian__need_goal"
RULE_LOCATE = "LOCATE_LINES_NEED_ROLE_AND_TWO_CANDIDATES"
RULE_PART = "EDITED_PART_NEEDS_GOAL_NODE"


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


def ng(action: str, **kw) -> str:
    return ctx(hook("PostToolUse", tool_name=NG, tool_input={"action": action, **kw},
                    tool_response={"content": [{"type": "text", "text": f"[NeedGoal] {action} 已收到"}]}))


def setup() -> dict:
    if BASE.exists():
        shutil.rmtree(BASE)
    (ROOT / "workflow").mkdir(parents=True)
    (ROOT / "workflow" / "config.json").write_text(json.dumps({"vector_search": {"enabled": False}}), encoding="utf-8")
    (BASE / "home" / ".claude" / "Logs").mkdir(parents=True)
    (BASE / "logs").mkdir()
    (PROJ / ".git").mkdir(parents=True)
    shared = PROJ / ".claude" / "memory" / "shared"
    shared.mkdir(parents=True)
    (PROJ / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
        "| `src\\` | 匯出 | `匯出導讀` | 有 |\n| `ui\\` | 介面 | `介面導讀` | 有 |\n", encoding="utf-8")
    for name, sick in (("匯出導讀", "欄位順序寫死在兩處"), ("介面導讀", "結果表格自己排欄位")):
        (shared / f"{name}.md").write_text(f"# {name}\n\n## 知識\n\n- [臨] **已知病灶**：{sick}\n", encoding="utf-8")
    files = {"src": PROJ / "src" / "export.py", "ui": PROJ / "ui" / "view.py"}
    for p in files.values():
        p.parent.mkdir()
        p.write_text("def f():\n    return []\n", encoding="utf-8")
    TP.write_text("", encoding="utf-8")
    return files


def main() -> int:
    files = setup()
    steps = []

    def step(name: str, ok: bool, detail: str = "") -> None:
        steps.append((name, ok))
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f"\n       {detail[:500]}" if not ok and detail else ""))

    prompt = "匯出要支援 CSV，介面顯示匯出結果"
    user(prompt)
    hook("UserPromptSubmit", prompt=prompt)
    say("先寫目標")
    ng("set", goal="匯出能出 CSV，介面看得到結果")
    out = ng("add", items=[{"text": "CSV 欄位跟 JSON 同一份定義"}, {"text": "介面顯示匯出結果"}])
    step("目標樹 T1.1 T1.2", "T1.1" in out and "T1.2" in out, out)

    def edit(key: str) -> dict:
        return {"file_path": str(files[key]), "old_string": "return []", "new_string": "return ['csv']"}

    out = hook("PreToolUse", tool_name="Edit", tool_input=edit("src"))
    step("第一次碰匯出：導讀卡附樹與兩候選寫法", "[NeedGoal] 目前的需求目標" in deny(out) and "候選 A" in deny(out), deny(out))
    hook("PostToolUse", tool_name="Read", tool_input={"file_path": str(files["src"])}, tool_response={"type": "text"})
    say("定位｜部位：匯出：export.py\n定位｜根因層：候選 A 欄位定義層；候選 B 輸出格式層；選 A 因為順序寫死在兩處\n"
        "定位｜前例：欄位順序寫死在兩處\n定位｜目標：T1.1")
    d = deny(hook("PreToolUse", tool_name="Edit", tool_input=edit("src")))
    step("第四行沒角色被擋（印規則名、缺哪項、範例四行）",
         RULE_LOCATE in d and "角色" in d and "定位｜目標：T1.1（" in d, d)
    say("定位｜部位：匯出：export.py\n定位｜根因層：欄位定義層\n定位｜前例：欄位順序寫死在兩處\n定位｜目標：T1.1（欄位定義只留一份的地方）")
    d = deny(hook("PreToolUse", tool_name="Edit", tool_input=edit("src")))
    step("根因層只一個候選被擋", RULE_LOCATE in d and "只辨識出 0 個" in d, d)
    say("定位｜部位：匯出：export.py\n定位｜根因層：候選 A 欄位定義層；候選 B 輸出格式層；選 A 因為順序寫死在兩處\n"
        "定位｜前例：欄位順序寫死在兩處\n定位｜目標：T1.1（欄位定義只留一份的地方）")
    out = hook("PreToolUse", tool_name="Edit", tool_input=edit("src"))
    step("補齊四行放行", not deny(out), json.dumps(out, ensure_ascii=False))
    files["src"].write_text("def f():\n    return ['csv']\n", encoding="utf-8")
    hook("PostToolUse", tool_name="Edit", tool_input=edit("src"), tool_response={"filePath": str(files["src"])})

    hook("PreToolUse", tool_name="Edit", tool_input=edit("ui"))                     # 第一次碰介面：注入
    hook("PostToolUse", tool_name="Read", tool_input={"file_path": str(files["ui"])}, tool_response={"type": "text"})
    say("定位｜部位：介面：view.py\n定位｜根因層：候選 A 表格欄位順序；候選 B 刷新時機；選 A 因為表格自己排欄位\n"
        "定位｜前例：結果表格自己排欄位\n定位｜目標：T1.2（把匯出結果顯示出來的那一塊）")
    out = hook("PreToolUse", tool_name="Edit", tool_input=edit("ui"))
    step("介面四行放行（掛 T1.2）", not deny(out), json.dumps(out, ensure_ascii=False))
    files["ui"].write_text("def f():\n    return ['csv']\n", encoding="utf-8")
    hook("PostToolUse", tool_name="Edit", tool_input=edit("ui"), tool_response={"filePath": str(files["ui"])})

    ng("update", items=[{"id": "T1.1", "status": "doing", "why": "export.py 改成同一份欄位定義"},
                        {"id": "T1.2", "status": "dropped", "why": "介面這次不做，另開需求"}])
    user("繼續")
    hook("UserPromptSubmit", prompt="繼續")
    hook("PostToolUse", tool_name="Bash", tool_input={"command": "python -X utf8 -m pytest -q tests"},
         tool_response={"stdout": "2 passed\nEXPORT_CHECK PASS\n", "stderr": "", "exit_code": 0})
    doc = json.loads((ROOT / "workflow" / "need-goal" / f"{SID}.json").read_text(encoding="utf-8"))
    rno = doc["receipts"][-1]["seq"] if doc.get("receipts") else None
    ev = [{"kind": "receipt", "ref": f"R{rno}", "level": "measured"}]
    out = ng("reconcile", items=[{"id": "T1", "status": "done", "evidence": ev},
                                 {"id": "T1.1", "status": "done", "evidence": ev},
                                 {"id": "T1.2", "status": "dropped", "note": "介面這次不做"}])
    step("完整對照收下", "完整對照收下" in out, out)
    say("全部完成。")
    reason = hook("Stop", last_assistant_message="全部完成。", stop_hook_active=False).get("reason") or ""
    step("收尾被擋 (f3)：列沒掛的介面與 view.py、指路",
         "(f3)" in reason and RULE_PART in reason and "介面：" in reason and "view.py" in reason
         and "T1.2 已放棄" in reason and "need_goal" in reason and "匯出：" not in reason.split("(f3)", 1)[-1], reason)
    say("定位｜部位：介面：view.py\n定位｜根因層：候選 A 表格欄位順序；候選 B 刷新時機；選 A 因為表格自己排欄位\n"
        "定位｜前例：結果表格自己排欄位\n定位｜目標：T1.1（介面跟匯出共用同一份欄位定義）")
    say("全部完成。")
    reason = hook("Stop", last_assistant_message="全部完成。", stop_hook_active=False).get("reason") or ""
    doc = json.loads((ROOT / "workflow" / "need-goal" / f"{SID}.json").read_text(encoding="utf-8"))
    tree = doc["trees"][doc["active"]]
    ui_link = next((v.get("node") for k, v in tree.get("links", {}).get("parts", {}).items() if k.endswith("|介面")), None)
    step("補掛後放行：(f3) 不再擋、介面掛到 T1.1", "(f3)" not in reason and ui_link == "T1.1", f"{ui_link}｜{reason}")
    passed = sum(1 for _, ok in steps if ok)
    print(f"C_G0_PROBE DONE steps={len(steps)} passed={passed} sid={SID}")
    print("C_G0_PROBE_CHECK " + ("PASS" if passed == len(steps) else "FAIL"))
    return 0 if passed == len(steps) else 1


if __name__ == "__main__":
    sys.exit(main())
