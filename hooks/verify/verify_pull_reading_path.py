"""verify_pull_reading_path.py：拐彎判斷只問這次改到的函式（hooks/wg_reading_path.py）。

答過的條目記名字＋內容指紋，之後同名同內容的不再問；擋的記號放在欠項外層，改碼起新一批也不清。
① f、g 都判過 → 只改 f → 下一批只問 f，不問 g；量完的結果說明幾條已判過不再問。
② 同一則回覆判了 f、g 又改了 f → 那次收尾的判斷行照收、不擋（新一批起量時舊欠項只收答案）；同一個使用者回合量完
   不再擋；下一個使用者回合只問新的 f 一次，同回合不問第二次，答完清掉。
③ 反例：新增函式 h 過門檻 → 要問 h；f、g 被擠到後面的行號、內容沒變，不算改到。
④ 同一個使用者回合擋過一次 → AI 改碼 → 同回合不再擋（「後面還會擋」的預覽也不列）；下一個使用者回合才問。
⑤ 同名的兩個函式（property 的 getter／setter）一行答完兩個都記住，改別處後不互相擠掉再問。
⑥ 每行文字一樣、只改相對縮排（換了巢狀層）→ 算改到、要再問；入口數字一樣但換了經過的函式、類別在顯示上限外多了成員 → 指紋不同；
   函式讀不到本體 → 沒有指紋、一律照問。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_pull_reading_path.py
     或 python -X utf8 hooks/verify/verify_pull_reading_path.py（尾行 PULL_READING_PATH_CHECK PASS／FAIL）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_reading_path as rph  # noqa: E402

_SID = "sid-reask"


def _fn(name: str, extra: str = "") -> str:
    """巢狀 3 層（到門檻）的函式；extra 插在最內層，用來改本體。"""
    return f"def {name}(n):\n    if n:\n        for x in range(n):\n            if x:\n                n += x{extra}\n    return n\n"


FLAT = "def f(n):\n    return n\n\n\ndef g(n):\n    return n\n"
F, G = _fn("f"), _fn("g")
F2 = _fn("f", "\n                n -= 1")   # AI 改過的 f：還是 3 層
PROP = ("class C:\n    @property\n    def x(self):\n        if self:\n            for i in self:\n                if i:\n"
        "                    return i\n        return 0\n\n    @x.setter\n    def x(self, v):\n        if v:\n"
        "            for i in v:\n                if i:\n                    self.v = i\n")


def _write(root: Path, files: dict) -> None:
    for rel, text in files.items():
        (root / rel).write_text(text, encoding="utf-8", newline="\n")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   capture_output=True, text=True, check=True)


def _repo(root: Path, base: str) -> Path:
    root.mkdir(parents=True)
    _write(root, {"y.py": base})
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _inline(path):
    """背景量測換成同一個行程直接跑完、照寫結果檔。"""
    job = json.loads(Path(path).read_text(encoding="utf-8"))
    rph.write_result(Path(job["out"]), rph.run_job(job))


def _edit(state: dict, root: Path, text: str, turn: int) -> None:
    """AI 在第 turn 回合改了 y.py。"""
    _write(root, {"y.py": text})
    state["turn_seq"] = turn
    state["modified_files"] = [{"path": str(root / "y.py"), "tool": "Edit", "session_id": _SID,
                                "turn_seq": turn, "last_turn_seq": turn}]


def _note(state: dict) -> str:
    """收尾兩次：第一次交給背景量（不附），第二次附上量完的結果。"""
    first, _ = rph.reading_path_note(state, _SID, {}, spawn=_inline)
    assert first is None and _rec(state).get("job")
    second, _ = rph.reading_path_note(state, _SID, {}, spawn=_inline)
    assert second and not _rec(state).get("job")
    return second


def _rec(state: dict) -> dict:
    return state["reading_path"][_SID]


def _owed_funcs(state: dict) -> list:
    return [it["name"] for it in (_rec(state).get("owed") or {}).get("items") or [] if it["kind"] == "函式"]


def _line(name: str, verdict: str = "不會：三層各守一個條件") -> str:
    return f"拐彎判斷｜{name}｜{verdict}｜迴圈裡只多一層判斷｜合理，因為條件只有一個"


def _answer_all(state: dict) -> str:
    return "完成。\n" + "\n".join(_line(it["name"]) for it in _rec(state)["owed"]["items"])


def _owed_fg(tmp_path: Path):
    """f、g 都從平的改成 3 層 → 量完欠 f、g。"""
    root = _repo(tmp_path / "r", FLAT)
    state: dict = {}
    _edit(state, root, F + "\n\n" + G, 5)
    _note(state)
    assert _owed_funcs(state) == ["y.py::f", "y.py::g"], "前置：f、g 都到門檻"
    return state, root


@pytest.fixture(autouse=True)
def _isolate(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(rph, "JOB_DIR", tmp_path_factory.mktemp("reask-jobs"))
    monkeypatch.setattr(rph, "append_guard_log", lambda guard, payload: None)


def test_only_the_changed_function_is_asked_again(tmp_path):
    state, root = _owed_fg(tmp_path)
    assert rph.turn_judgment_note(state, _SID, _answer_all(state), 1, 5) == (None, True)
    assert "owed" not in _rec(state)
    _edit(state, root, F2 + "\n\n" + G, 6)
    note = _note(state)
    assert _owed_funcs(state) == ["y.py::f"], "只改了 f：g 判過、內容沒變，不再問"
    assert "已判過、內容沒變的 1 條不再問" in note, note[-600:]


def test_judged_and_changed_in_one_reply_asks_only_the_new_f_once_next_user_turn(tmp_path):
    state, root = _owed_fg(tmp_path)
    msg, _ = rph.turn_judgment_note(state, _SID, "完成。", 1, 5)
    assert msg and "TURN_JUDGMENT_REQUIRED" in msg, "前置：使用者回合 1 擋過一次"
    _edit(state, root, F2 + "\n\n" + G, 6)                                   # 同一則回覆：判 f 該壓平、判 g，並改了 f
    assert rph.reading_path_note(state, _SID, {}, spawn=_inline)[0] is None and _rec(state).get("job")
    reply = "完成。\n" + _line("y.py::f", "會：第 3 個彎在內層 if，該壓平") + "\n" + _line("y.py::g")
    assert rph.turn_judgment_note(state, _SID, reply, 1, 6) == (None, True), "改碼那次收尾的判斷行照收"
    state["turn_seq"] = 7                                                    # 同一個使用者回合再收尾：量完附上
    rph.reading_path_note(state, _SID, {}, spawn=_inline)
    assert _owed_funcs(state) == ["y.py::f"], "g 判過沒動不再問；f 改過要問新的"
    assert rph.turn_judgment_note(state, _SID, "完成。", 1, 7) == (None, False), "這個使用者回合已擋過"
    msg, _ = rph.turn_judgment_note(state, _SID, "完成。", 2, 8)
    assert msg and "y.py::f" in msg and "y.py::g" not in msg, msg
    assert rph.turn_judgment_note(state, _SID, "完成。", 2, 9) == (None, False), "同回合不問第二次"
    assert rph.turn_judgment_note(state, _SID, "完成。\n" + _line("y.py::f"), 2, 10) == (None, True)
    assert "owed" not in _rec(state)


def test_new_function_over_threshold_is_asked_and_moved_ones_are_not(tmp_path):
    state, root = _owed_fg(tmp_path)
    assert rph.turn_judgment_note(state, _SID, _answer_all(state), 1, 5) == (None, True)
    _edit(state, root, _fn("h") + "\n\n" + F + "\n\n" + G, 6)               # h 插在最前面，f、g 往後移
    _note(state)
    assert _owed_funcs(state) == ["y.py::h"]


def test_blocked_once_then_code_change_does_not_block_again_in_the_same_user_turn(tmp_path):
    state, root = _owed_fg(tmp_path)
    msg, _ = rph.turn_judgment_note(state, _SID, "完成。", 1, 5)
    assert msg, "前置：使用者回合 1 擋過一次"
    _edit(state, root, F2 + "\n\n" + G, 6)                                   # 沒答、直接改 f
    rph.reading_path_note(state, _SID, {}, spawn=_inline)
    assert rph.turn_judgment_note(state, _SID, "完成。", 1, 6) == (None, False), "量完前不拿舊條目擋"
    state["turn_seq"] = 7
    rph.reading_path_note(state, _SID, {}, spawn=_inline)
    assert _owed_funcs(state) == ["y.py::f", "y.py::g"], "都還沒答：f 改過、g 沒答，兩條都還欠"
    assert rph.turn_judgment_note(state, _SID, "完成。", 1, 7) == (None, False), "同一個使用者回合不再擋"
    assert rph.turn_judgment_missing(state, _SID, "完成。", 1) == [], "預覽也不列這回合不會再擋的"
    msg, _ = rph.turn_judgment_note(state, _SID, "完成。", 2, 8)
    assert msg and "y.py::f" in msg and "y.py::g" in msg, "下一個使用者回合才問"


def test_same_name_getter_and_setter_both_remembered(tmp_path):
    root = _repo(tmp_path / "r", "class C:\n    pass\n")
    state: dict = {}
    _edit(state, root, PROP, 5)
    _note(state)
    assert _owed_funcs(state) == ["y.py::C.x", "y.py::C.x"], "前置：getter、setter 同名都到門檻"
    assert rph.turn_judgment_note(state, _SID, "完成。\n" + _line("y.py::C.x"), 1, 5) == (None, True)
    _edit(state, root, PROP + "\n\ndef z(n):\n    return n\n", 6)            # 只改別處
    _note(state)
    assert _owed_funcs(state) == [], "兩個同名的都記住了，不互相擠掉再問"


def test_moving_a_line_to_another_nesting_level_counts_as_changed(tmp_path):
    """每行文字一樣、只改相對縮排（n -= 1 從內層 if 搬到外層 for）→ Python 的結構變了，要再問；g 沒動不問。"""
    root = _repo(tmp_path / "r", FLAT)
    state: dict = {}
    _edit(state, root, F2 + "\n\n" + G, 5)
    _note(state)
    assert rph.turn_judgment_note(state, _SID, _answer_all(state), 1, 5) == (None, True)
    _edit(state, root, _fn("f", "\n            n -= 1") + "\n\n" + G, 6)
    _note(state)
    assert _owed_funcs(state) == ["y.py::f"]


def test_entry_class_and_unreadable_fingerprints():
    """入口：拐彎、跳檔、轉手數字一樣但換了經過的函式 → 指紋不同；類別：顯示的數據截在 6 個成員，指紋看全部成員；
    函式讀不到本體 → 沒有指紋（一律照問，不拿數據頂替）。"""
    cfg = rph.turn_judgment_cfg({})

    def route(*funcs):
        steps = [{"func": f, "kind": "direct"} for f in funcs]
        return {"rows": [{"status": "new", "certain": True, "entry": "app.py::main", "landing": "z.py::c", "before": {},
                          "after": {"turns": 2, "file_jumps": 1, "handoffs": 0, "steps": steps}}]}
    a, b, a2 = (rph.entry_items(route(*p), cfg)[0]["fp"] for p in (("main", "x.a", "z.c"), ("main", "y.b", "z.c"),
                                                                    ("main", "x.a", "z.c")))
    assert a != b and a == a2

    root = Path(__file__).resolve().parent

    def leaf(extra):
        layers = [{"name": "Leaf", "empty": False, "added": [f"m{i}" for i in range(6)] + [extra], "overridden": []},
                  {"name": "Mid", "empty": True, "added": [], "overridden": []},
                  {"name": "Base", "empty": False, "added": ["run"], "overridden": []}]
        return {"kind": "class", "file": str(root / "k.py"), "name": "Leaf", "depth": 3, "layers": layers}
    (_, one), (_, two) = (rph.function_rows([leaf(x)], root, cfg) for x in ("m6", "m7"))
    assert one[0]["nums"] == two[0]["nums"] and one[0]["fp"] != two[0]["fp"]

    fn = {"kind": "func", "file": str(root / "y.py"), "name": "f", "nesting": 3, "bumpy": 0, "cognitive": 3, "length": 5}
    assert rph.function_rows([fn], root, cfg)[1][0]["fp"] is None


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q", "-p", "no:cacheprovider"])
    print("PULL_READING_PATH_CHECK PASS" if rc == 0 else "PULL_READING_PATH_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
