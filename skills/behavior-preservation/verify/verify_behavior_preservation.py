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


# ─── 001 退回的三條 BLOCK 反例 ──────────────────────────────────────

def test_json_without_cases_rejected():
    """BLOCK 1：.json 預期表零 case 不能 PASS，要拒收 exit 2。"""
    hub = FIX.parents[0] / "prebuild" / "hub.json"
    code, tail, out = run("new_ok.py", "side_effect", expected=hub)
    assert (code, tail) == (2, "PRESERVE_CHECK FAIL") and "沒有任何 case" in out


def test_cmd_runner_nonzero_exit_rejected():
    """BLOCK 2：外部執行器先印對的值再非零 exit，不得當成功。"""
    cmd = f'"{sys.executable}" -X utf8 -c "import sys; sys.path.insert(0, r\'{FIX}\'); import new_ok as m; print(m.grade(int(sys.argv[1]))); sys.exit(7)" {{key}}'
    code, tail, out = run("new_ok.py", "boundary", extra=("--actual-cmd", cmd))
    assert (code, tail) == (2, "PRESERVE_CHECK FAIL") and "exit 7" in out


def test_unparsed_branch_form_rejected(tmp_path):
    """WARN：函式體裡有解析器不認的分支寫法（`if x in …`）→ 拒收，不靜默略過。"""
    old = tmp_path / "old_in.py"
    old.write_text("def grade(score):\n    if score == 1:\n        return 'D'\n    elif score in (2, 3):\n        return 'C'\n    else:\n        return '?'\n",
                   encoding="utf-8", newline="\n")
    code, tail, out = run("new_ok.py", "boundary", expected=old)
    assert (code, tail) == (2, "PRESERVE_CHECK FAIL") and "不認的分支寫法" in out


# ─── 002 退回的兩條 BLOCK 反例（解析器改走 ast） ───────────────────

NESTED_OLD = '''def grade(score):
    if score == 1:
        return "D"
    elif score == 2:
        if score == 3:
            return "B"
        return "C"
    else:
        return "?"
'''
NESTED_NEW = '''def grade(score):
    return {1: "D", 3: "B"}.get(score, "?")
'''


def test_nested_branch_rejected(tmp_path):
    """BLOCK 1：巢狀 if 不能被當平面表收進去（舊 score=2 回 C、新回 ?，若收進去會錯誤 PASS）；要拒收並印行號。"""
    old, new = tmp_path / "old_nested.py", tmp_path / "new_flat.py"
    old.write_text(NESTED_OLD, encoding="utf-8", newline="\n")
    new.write_text(NESTED_NEW, encoding="utf-8", newline="\n")
    cmd = [sys.executable, "-X", "utf8", str(SCRIPT), "--expected-from", str(old), "--actual-from", str(new),
           "--mutation", "boundary", "--func", "grade"]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    tail = [ln for ln in p.stdout.splitlines() if ln.strip()][-1]
    assert (p.returncode, tail) == (2, "PRESERVE_CHECK FAIL"), p.stdout
    assert "第 5 行" in p.stdout and "巢狀" in p.stdout


def test_docstring_branch_text_ignored(tmp_path):
    """BLOCK 2：docstring 裡寫 `if score in (2, 3): example only` 不是分支，不得誤拒收；對 new_ok 要 PASS。"""
    src = (FIX / "old.py").read_text(encoding="utf-8").replace(
        "def grade(score):\n", 'def grade(score):\n    """\n    if score in (2, 3): example only\n    """\n', 1)
    old = tmp_path / "old_doc.py"
    old.write_text(src, encoding="utf-8", newline="\n")
    for mutation in PC.MUTATIONS:
        code, tail, out = run("new_ok.py", mutation, expected=old)
        assert (code, tail) == (0, "PRESERVE_CHECK PASS"), out


def test_non_python_source_rejected(tmp_path):
    """非 Python 源碼不猜：要先解析成 .json。"""
    cs = tmp_path / "Old.cs"
    cs.write_text("int Grade(int s){ switch(s){ case 1: return 1; default: return 0; } }\n", encoding="utf-8", newline="\n")
    code, tail, out = run("new_ok.py", "boundary", expected=cs)
    assert (code, tail) == (2, "PRESERVE_CHECK FAIL") and ".json" in out


# ─── 003 退回的兩條 BLOCK 反例 ──────────────────────────────────────

def _pair(tmp_path, old_src: str, new_src: str, mutation: str, extra=()) -> tuple:
    old, new = tmp_path / "old_x.py", tmp_path / "new_x.py"
    old.write_text(old_src, encoding="utf-8", newline="\n")
    new.write_text(new_src, encoding="utf-8", newline="\n")
    cmd = [sys.executable, "-X", "utf8", str(SCRIPT), "--expected-from", str(old), "--actual-from", str(new),
           "--mutation", mutation, "--func", "grade", "--order-func", "merit_order", *extra]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    tail = [ln for ln in p.stdout.splitlines() if ln.strip()][-1]
    return p.returncode, tail, p.stdout


def test_unreachable_tail_after_else_rejected(tmp_path):
    """BLOCK 1：`else: return None` 後接不可達 `return "WRONG"`，不得把 WRONG 當預設；要拒收並印行號。"""
    old = 'def grade(x):\n    if x == 1:\n        return "A"\n    else:\n        return None\n    return "WRONG"\n\n\ndef merit_order():\n    return [1]\n'
    new = 'def grade(x):\n    return "A" if x == 1 else "WRONG"\n\n\ndef merit_order():\n    return [1]\n'
    for mutation in ("boundary", "side_effect"):
        code, tail, out = _pair(tmp_path, old, new, mutation)
        assert (code, tail) == (2, "PRESERVE_CHECK FAIL"), out
        assert "第 6 行" in out and "不可達" in out


def test_duplicate_key_rejected(tmp_path):
    """BLOCK 2：重複 `elif x == 1` 的第二分支不可達，不得拿它的副作用當預期；要拒收並印兩個行號。"""
    old = ('def log(*args):\n    pass\n\n\ndef grade(x):\n    if x == 1:\n        log("first")\n        return "A"\n'
           '    elif x == 1:\n        log("unreachable")\n        return "A"\n    else:\n        return "?"\n\n\ndef merit_order():\n    return [1]\n')
    new = ('def log(*args):\n    pass\n\n\ndef grade(x):\n    if x == 1:\n        log("unreachable")\n        return "A"\n    return "?"\n\n\n'
           'def merit_order():\n    return [1]\n')
    for mutation in PC.MUTATIONS:
        code, tail, out = _pair(tmp_path, old, new, mutation)
        assert (code, tail) == (2, "PRESERVE_CHECK FAIL"), out
        assert "第 9 行" in out and "第 6 行" in out and "重複 case" in out


def test_else_returning_none_is_a_real_default(tmp_path):
    """None 是合法預設值：舊 else 回 None、新碼也回 None 要 PASS，不能把 None 當「沒設」。"""
    old = 'def grade(x):\n    if x == 1:\n        return "A"\n    else:\n        return None\n\n\ndef merit_order():\n    return [1]\n'
    new = 'def grade(x):\n    return {1: "A"}.get(x)\n\n\ndef merit_order():\n    return [1]\n'
    code, tail, out = _pair(tmp_path, old, new, "boundary")
    assert (code, tail) == (0, "PRESERVE_CHECK PASS"), out
