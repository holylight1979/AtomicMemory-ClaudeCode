"""probe_retry_cycles.py — 規則 RETRY_COUNTS_RERUN_CYCLES 的真 hook 入口探針（hooks/workflow-guardian.py 吃造好的事件 JSON）。

做什麼：沿用 probe_release_rules.py 的沙箱（tmp 資料根、家目錄、系統暫存、Logs），跑兩個情境：
  R1 紅案例先行：跑紅 → 同檔 Write 5 次 → 跑綠 → 下一則使用者訊息不跳 FixEscalation、重試 0 輪
  R2 反覆修不好：跑紅 → 改 → 跑仍紅 → 改 → 跑仍紅 → 下一則使用者訊息跳 FixEscalation，印第 2 輪與兩輪的指令＋紅案
不是 pytest 案例（檔名不以 verify_／test_ 開頭）；pytest 案例在 verify_release_rules.py。

怎麼跑：python -X utf8 hooks/verify/probe_retry_cycles.py --tree <受測樹> [--keep]
尾行：RETRY_CYCLES_PROBE_CHECK PASS|FAIL（兩個情境的檢查點全對才 PASS）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_release_rules import Sandbox, Session  # noqa: E402

PYTEST = "python -m pytest -q tests/test_a.py"


def _red(case: str) -> str:
    return f"FAILED {case} - assert 1 == 2\n1 failed in 0.1s\n"


def _ctx(step: dict) -> str:
    j = step.get("json") or {}
    return str((j.get("hookSpecificOutput") or {}).get("additionalContext") or "")


def _state(sb: Sandbox, sid: str) -> dict:
    hits = sorted((sb.data / "workflow").glob(f"state-*{sid}*.json"))
    return json.loads(hits[-1].read_text(encoding="utf-8")) if hits else {}


def run(tree: Path, base: Path) -> list:
    rows = []

    sb = Sandbox(tree, base, "r1")
    s = Session(sb, sb.project("proj"))
    s.session_start()
    s.prompt("把 a 的邏輯修好")
    s.bash(PYTEST, stdout=_red("tests/test_a.py::t1"), exit_code=1)
    for i in range(5):
        s.write(s.cwd / "src" / "a.py", f"x = {i}\n")
    s.bash(PYTEST, stdout="3 passed in 0.1s\n")
    after = s.prompt("下一步")
    st = _state(sb, s.sid)
    rows.append(("R1 紅→改 5 次→綠：重試輪數", int(st.get("wisdom_retry_count", 0) or 0), 0))
    rows.append(("R1 下一則訊息跳 FixEscalation", "[Guardian:FixEscalation]" in _ctx(after), False))

    sb = Sandbox(tree, base, "r2")
    s = Session(sb, sb.project("proj"))
    s.session_start()
    s.prompt("把 a 的邏輯修好")
    s.bash(PYTEST, stdout=_red("tests/test_a.py::t1"), exit_code=1)
    s.write(s.cwd / "src" / "a.py", "x = 1\n")
    s.bash(PYTEST + " -k t2", stdout=_red("tests/test_a.py::t2"), exit_code=1)
    s.write(s.cwd / "src" / "a.py", "x = 2\n")
    s.bash(PYTEST + " -k t3", stdout=_red("tests/test_a.py::t3"), exit_code=1)
    after = s.prompt("還是不行，下一步")
    st = _state(sb, s.sid)
    text = _ctx(after)
    rows.append(("R2 兩輪紅：重試輪數", int(st.get("wisdom_retry_count", 0) or 0), 2))
    rows.append(("R2 下一則訊息跳 FixEscalation", "[Guardian:FixEscalation]" in text, True))
    rows.append(("R2 訊息印規則名與第 2 輪", "RETRY_COUNTS_RERUN_CYCLES" in text and "第 2 輪" in text, True))
    rows.append(("R2 訊息印兩輪的指令與紅案",
                 all(k in text for k in ("-k t2", "tests/test_a.py::t2", "-k t3", "tests/test_a.py::t3")), True))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tree", required=True, help="受測樹（含 hooks/workflow-guardian.py）")
    ap.add_argument("--keep", action="store_true", help="留下沙箱目錄")
    a = ap.parse_args()
    base = Path(tempfile.mkdtemp(prefix="probe-retry-"))
    try:
        rows = run(Path(a.tree).resolve(), base)
    finally:
        if not a.keep:
            shutil.rmtree(base, ignore_errors=True)
    ok = all(actual == want for _, actual, want in rows)
    for what, actual, want in rows:
        print(f"{'OK ' if actual == want else 'BAD'} {what}：實際 {actual}／預期 {want}")
    print(f"RETRY_CYCLES_PROBE_CHECK {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
