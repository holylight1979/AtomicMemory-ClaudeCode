"""probe_verify_scope.py — 驗證範圍（該測哪些由 LLM 判斷並負責）的真 hook 入口情境探針。

做什麼：用 probe_release_rules 的沙箱（tmp 資料根、家目錄、系統暫存、Logs）與受測樹的真 hook 入口 hooks/workflow-guardian.py，
  餵造好的事件 JSON，走一遍「改程式 → 沒宣告被擋 → 宣告範圍 → 範圍內跑綠 → 收尾放行（結案）→ 下一回合範圍外的測試紅了 →
  記範圍漏判 → 新 session 開場列出 → 沒檢討的新宣告被退回 → 交了檢討收下」。
  S1 主流程；S2 部位表整把量尺只當參考（改到有量尺的部位，只跑宣告的一支就放行）。
不是 pytest 案例（檔名不以 verify_／test_ 開頭）；pytest 案例在 hooks/verify/verify_verify_scope.py。

怎麼跑：python -X utf8 hooks/verify/probe_verify_scope.py --tree <受測 worktree> [--keep]
尾行：VERIFY_SCOPE_PROBE DONE k=v（統計）之後，最後一行 VERIFY_SCOPE_PROBE_CHECK PASS|FAIL（全部檢查點符合才 PASS）。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_release_rules import Checks, Sandbox, Session, TEXT_DONE, git, reason_of  # noqa: E402

NG = "mcp__workflow-guardian__need_goal"
MAP = ("| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 量尺（量法｜指令｜門檻） | 類別 |\n|---|---|---|---|---|---|\n"
       "| `src/` | 程式層 | 無 | 無 | 全部測試｜`python -X utf8 -m pytest -q tests`｜全綠 | code |\n"
       "| `tests/` | 測試層 | 無 | 無 | 無 | code |\n")


def _scope_on(sb: Sandbox) -> None:
    """沙箱設定把驗證範圍打開（probe_release_rules 的沙箱預設關掉它）。"""
    p = sb.data / "workflow" / "config.json"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg["verify_scope"] = {"enabled": True, "runtime_gate_timeout_s": 2}
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _ctx(step: dict) -> str:
    j = step.get("json") or {}
    return str((j.get("hookSpecificOutput") or {}).get("additionalContext") or j.get("reason") or "")


def declare(s: Session, items: list, reviews: list | None = None) -> dict:
    ti = {"action": "verify_scope", "items": items, **({"reviews": reviews} if reviews is not None else {})}
    tid = s._id()
    s._rec({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": NG, "input": ti}]}})
    s._rec({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid,
                                                                     "content": "[NeedGoal] verify_scope 已收到"}]}})
    return s.hook({"hook_event_name": "PostToolUse", "tool_name": NG, "tool_use_id": tid, "tool_input": ti,
                   "tool_response": [{"type": "text", "text": "[NeedGoal] verify_scope 已收到"}]}, "PostToolUse need_goal verify_scope")


def _project(sb: Sandbox):
    proj = sb.project("proj", MAP)
    git(proj, "init", "-q")
    for rel, text in (("src/a.py", "A = 1\n"), ("tests/test_a.py", "def test_a():\n    pass\n"),
                      ("tests/test_b.py", "def test_b():\n    pass\n")):
        (proj / rel).parent.mkdir(parents=True, exist_ok=True)
        (proj / rel).write_text(text, encoding="utf-8", newline="\n")
    return proj


def s1(tree: Path, base: Path):
    c = Checks("S1", "主流程：沒宣告擋 → 宣告、範圍內跑綠 → 放行結案 → 下一回合範圍外紅記漏判 → 新 session 先檢討才收宣告")
    sb = Sandbox(tree, base, "s1")
    _scope_on(sb)
    proj = _project(sb)
    s = Session(sb, proj)
    s.session_start()
    s.prompt("改 src/a.py")
    s.bash("python -X utf8 -m pytest -q tests/test_b.py", ".\n1 passed in 0.01s\n")                # test_b 先綠過
    time.sleep(1.1)
    s.write(proj / "src" / "a.py", "A = 2\n")
    s.write(proj / "tests" / "test_a.py", "def test_a():\n    assert True\n")
    st = s.stop(TEXT_DONE)
    r = reason_of(st)
    c.add("改了程式沒宣告就 Stop", "block" if "SCOPE_DECLARED_FOR_CHANGE" in r else st["result"], "block", note=r[:90])
    c.add("擋訊息附部位整把量尺當參考", "yes" if "參考（不必全跑）" in r and "pytest -q tests" in r else "no", "yes")
    d = declare(s, [{"target": "tests/test_a.py", "why": "直接測 src/a.py 的常數"}])
    c.add("宣告收下", "yes" if "verify_scope 收下" in _ctx(d) else "no", "yes", note=_ctx(d)[:90])
    s.bash("python -X utf8 -m pytest -q tests/test_a.py", ".\n1 passed in 0.01s\n")
    st = s.stop(TEXT_DONE, active=True)
    c.add("範圍內跑綠後 Stop（只跑一支，不跑整把）", "block" if "VerifyScope" in reason_of(st) else "pass", "pass",
          note=reason_of(st)[:90])
    time.sleep(1.1)
    red = s.bash("python -X utf8 -m pytest -q tests/test_b.py", "F\nFAILED tests/test_b.py::test_b - assert 0\n1 failed in 0.01s\n",
                 exit_code=1)
    ctx = _ctx(red)
    c.add("下一回合範圍外的測試紅了 → 當下送回漏判", "yes" if "範圍漏判" in ctx and "tests/test_b.py::test_b" in ctx else "no", "yes",
          note=ctx[:90])
    s2_ = Session(sb, proj)
    start = s2_.session_start()
    c.add("新 session 開場列待檢討的漏判", "yes" if "範圍漏判待檢討" in json.dumps(start.get("json") or {}, ensure_ascii=False) else "no",
          "yes")
    s2_.prompt("改 src/a.py 第二輪")
    d = declare(s2_, [{"target": "tests/test_a.py", "why": "直接測"}])
    c.add("沒檢討就宣告 → 退回", "yes" if "SCOPE_LEAK_REVIEW_BEFORE_DECLARE" in _ctx(d) else "no", "yes", note=_ctx(d)[:90])
    m = re.search(r"(?<![0-9A-Za-z])L[0-9a-f]{6}(?![0-9a-f])", _ctx(d))
    lid = m.group(0) if m else ""
    d = declare(s2_, [{"target": "tests/test_a.py", "why": "直接測"}],
                [{"leak": lid, "verdict": "missed", "root_cause": "只看了 a.py 自己的測試，沒查 test_b 也讀 A",
                  "next_time": "改常數先搜所有讀它的測試"}])
    c.add("交了檢討 → 收下、數字更新", "yes" if "verify_scope 收下" in _ctx(d) and "該驗沒驗到 1" in _ctx(d) else "no", "yes",
          note=_ctx(d)[:120])
    return c, [s, s2_]


def s2(tree: Path, base: Path):
    c = Checks("S2", "部位整把量尺只當參考：改到有量尺的部位，只跑宣告的一支就放行")
    sb = Sandbox(tree, base, "s2")
    _scope_on(sb)
    proj = _project(sb)
    s = Session(sb, proj)
    s.session_start()
    s.prompt("改 src/a.py 一行")
    s.write(proj / "src" / "a.py", "A = 3\n")
    s.write(proj / "tests" / "test_a.py", "def test_a():\n    assert 3\n")
    declare(s, [{"target": "tests/test_a.py", "why": "直接測 src/a.py"}])
    s.bash("python -X utf8 -m pytest -q tests/test_a.py", ".\n1 passed in 0.01s\n")
    st = s.stop(TEXT_DONE)
    c.add("沒跑整把 `pytest -q tests` 也放行", "block" if "VerifyScope" in reason_of(st) else "pass", "pass", note=reason_of(st)[:90])
    return c, [s]


SCENARIOS = {"S1": s1, "S2": s2}


def main() -> int:
    ap = argparse.ArgumentParser(description="驗證範圍的真 hook 入口情境探針")
    ap.add_argument("--tree", required=True)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    tree = Path(a.tree).resolve()
    runs = tree.parent / f"{tree.name}-probe-runs"           # 不放系統暫存：暫存目錄下的改檔不當專案
    runs.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix=("keep-" if a.keep else "scope-") + time.strftime("%H%M%S-"), dir=str(runs)))
    print(f"受測樹 {tree}｜run 目錄 {base}")
    total = bad = 0
    for key, fn in SCENARIOS.items():
        try:
            checks, sessions = fn(tree, base)
        except Exception as e:  # noqa: BLE001
            print(f"\n== 情境 {key}：建構失敗 {type(e).__name__}: {e}")
            total, bad = total + 1, bad + 1
            continue
        print(f"\n== 情境 {checks.sid}：{checks.title}")
        for r in checks.rows:
            total += 1
            bad += not r["ok"]
            note = f"｜{r['note']}" if r["note"] else ""
            print(f"  - {r['what']}：實際 {r['actual']}｜規則 {r['rule']} → {'符合' if r['ok'] else '不符'}{note}")
        for s in sessions:
            for st in s.steps:
                if st["rc"] != 0 or any("Error in" in ln or "Traceback" in ln for ln in st["stderr_tail"]):
                    print(f"    ! hook 異常 {st['label']} rc={st['rc']} stderr={st['stderr_tail'][-2:]}")
    if not a.keep:
        shutil.rmtree(base, ignore_errors=True)
    print(f"\nVERIFY_SCOPE_PROBE DONE scenarios={len(SCENARIOS)} checks={total} failed={bad}")
    print("VERIFY_SCOPE_PROBE_CHECK PASS" if bad == 0 else "VERIFY_SCOPE_PROBE_CHECK FAIL")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
