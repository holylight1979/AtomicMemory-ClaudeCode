"""verify_behavior_preservation.py: preserve-check.py 的契約。

守住：
- 正例 new_ok 三類變異全 PASS（exit 0）。
- 反例 new_const 常數改壞：三類任一都 FAIL（exit 1）。
- 反例 new_order／new_side／new_boundary 各在自己那類 FAIL，在別類不 FAIL（類別分得開）。
- expected 與 actual 同一路徑被拒（exit 2，尾行仍是 PRESERVE_CHECK FAIL）。
- 預期來源可換：.json 表餵進去與源碼解析同結果。
- 執行器可換：--actual-cmd 跑 boundary 得同結果；side_effect 在它身上明說不支援（exit 2）。
- 尾行哨兵符合 `^[A-Z][A-Z0-9_]*_CHECK (PASS|FAIL)$`。
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "preserve-check.py"
FIX = SKILL_DIR.parents[1] / "hooks" / "verify" / "fixtures" / "v6" / "behavior"
SENTINEL = re.compile(r"^[A-Z][A-Z0-9_]*_CHECK (PASS|FAIL)$")

_spec = importlib.util.spec_from_file_location("preserve_check", SCRIPT)
PC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PC)


def run(actual: str, mutation: str, expected: Path = FIX / "old.py", extra=()) -> tuple:
    cmd = [sys.executable, "-X", "utf8", str(SCRIPT), "--expected-from", str(expected),
           "--actual-from", str(FIX / actual), "--mutation", mutation,
           "--func", "grade", "--order-func", "merit_order", *extra]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    tail = [ln for ln in p.stdout.splitlines() if ln.strip()][-1]
    assert SENTINEL.match(tail), f"尾行不是合格哨兵：{tail!r}\n{p.stdout}\n{p.stderr}"
    return p.returncode, tail, p.stdout


@pytest.mark.parametrize("mutation", PC.MUTATIONS)
def test_new_ok_passes_all_three(mutation):
    code, tail, _ = run("new_ok.py", mutation)
    assert (code, tail) == (0, "PRESERVE_CHECK PASS")


@pytest.mark.parametrize("mutation", PC.MUTATIONS)
def test_new_const_fails_in_every_mutation(mutation):
    code, tail, out = run("new_const.py", mutation)
    assert (code, tail) == (1, "PRESERVE_CHECK FAIL")
    assert "值不同 key=3" in out


@pytest.mark.parametrize("actual,own", [("new_order.py", "order"), ("new_side.py", "side_effect"),
                                        ("new_boundary.py", "boundary")])
def test_each_mutation_class_caught_only_by_its_own_mode(actual, own):
    for mutation in PC.MUTATIONS:
        code, tail, _ = run(actual, mutation)
        if mutation == own:
            assert (code, tail) == (1, "PRESERVE_CHECK FAIL"), f"{actual} 在 {mutation} 應 FAIL"
        else:
            assert (code, tail) == (0, "PRESERVE_CHECK PASS"), f"{actual} 在 {mutation} 不該 FAIL"


def test_same_path_rejected():
    code, tail, out = run("old.py", "order", expected=FIX / "old.py")
    assert code == 2 and tail == "PRESERVE_CHECK FAIL"
    assert "同一路徑" in out


def test_expected_source_replaceable_json(tmp_path):
    table = PC.parse_expected_source((FIX / "old.py").read_text(encoding="utf-8"), "grade", "merit_order", "log")
    assert table["values"] == {1: "D", 2: "C", 3: "B", 4: "A"} and table["default"] == "?"
    assert table["effects"] == {1: ["grade:low"], 4: ["grade:top"]} and table["order"] == ["A", "B", "C", "D"]
    j = tmp_path / "expected.json"
    j.write_text(json.dumps({"values": {str(k): v for k, v in table["values"].items()}, "default": "?",
                             "effects": {"1": ["grade:low"], "4": ["grade:top"]}, "order": table["order"]}),
                 encoding="utf-8", newline="\n")
    for mutation in PC.MUTATIONS:
        assert run("new_ok.py", mutation, expected=j)[0] == 0
    assert run("new_boundary.py", "boundary", expected=j)[0] == 1
    assert run("new_side.py", "side_effect", expected=j)[0] == 1


def test_executor_replaceable_cmd():
    cmd = f'"{sys.executable}" -X utf8 -c "import sys; sys.path.insert(0, r\'{FIX}\'); import new_boundary as m; print(m.grade(int(sys.argv[1])))" {{key}}'
    code, tail, out = run("new_boundary.py", "boundary", extra=("--actual-cmd", cmd))
    assert (code, tail) == (1, "PRESERVE_CHECK FAIL") and "邊界不同" in out
    code, _, out = run("new_boundary.py", "side_effect", extra=("--actual-cmd", cmd))
    assert code == 2 and "不支援" in out
