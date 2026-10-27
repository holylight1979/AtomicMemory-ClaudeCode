"""verify_g11_turns.py：G11 拐彎判斷——程式只算側面數據、把那一題送到眼前、核對「拐彎判斷｜」五欄齊；判臭是 AI 的事。

正例：改了函式讓巢狀到 4、條件塊 2 → 背景量完的結果列函式級數據、標「要人看」、附那一題（問這一層存在的理由）與尺度原文、
      填好函式名的範例行；收尾文字沒有拐彎判斷行 → 擋一次（規則 TURN_JUDGMENT_REQUIRED，訊息列缺的那幾條與範例行），同一個
      使用者回合不再擋，下一回合再擋；寫了四欄 → 擋並點名缺哪欄；五欄齊 → 放行、guard log reading_path 記 judged；
      入口拐彎到門檻的變差／新增路徑也是一條；繼承鏈有空層、連續轉手鏈 ≥2 也是一條；真 Stop 入口擋到補齊為止。
擋點：排在寫碼查核（對帳）之後、SecondOpinion 之前——對帳先擋時尾段「後面還會擋」列拐彎判斷缺幾條（預覽只讀、不吃這回合
      那一次）；拐彎判斷擋時尾段預告第二意見；同回合第二次收尾不再擋；子代理 Stop 入口不觸發。
C#：改了 .cs → 不列函式級數據表，走一跳範圍的閱讀路徑（lib/reading_path_cs），超線才問（只轉手的一層、繼承鏈有空層；巢狀深不問），
      那一題與五欄核對共用；沒超線、或只有解析不到 → 沒有字（解析不到只進 stderr）；基底的基底在一跳外 → 標接不到、不往上讀；
      C# 量不出來不牽連同一批的 Python 數據。案例細節見 lib/verify/verify_reading_path_cs.py。
反例：數據全低於門檻 → 不問、不擋、結果文字沒有那個根的數據（數據只印 stderr、guard log 記 measured）；Python 與 C# 以外的檔
      標不支援、不問（同樣只在 stderr）；還沒 git add 的新檔不列函式級數據（只報個數）。
思考的彎：reconcile turns ≥4 沒寫「重找最短路：」→ 拒收；turns=2 收下；沒給 turns → 收下並提醒一句。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_g11_turns.py
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_core  # noqa: E402
import wg_need_goal as ng  # noqa: E402
import wg_reading_path as rph  # noqa: E402
import wg_release_rules as rr  # noqa: E402
import wg_verify_ledger as vl  # noqa: E402
import wg_evasion as ev  # noqa: E402
from handlers import stop as st  # noqa: E402

_SID = "sid-g11"
_BODY = "def {0}(n):\n    k = n + 1\n    k *= 2\n    return k\n"
APP = {"app.py": "from x import a\nfrom y import b\n\n\ndef main():\n    n = a(1)\n    n += b(2)\n    return n\n\n\n"
                 'if __name__ == "__main__":\n    main()\n',
       "x.py": _BODY.format("a"), "y.py": _BODY.format("b"), "z.py": _BODY.format("c"), "w.py": _BODY.format("d"),
       "a.cs": "class A { int F() { return 1; } }\n"}
NESTED_B = """def b(n):
    if n:
        for x in range(n):
            if x:
                while x:
                    x -= 1
    if n:
        if n > 1:
            n += 1
    return n
"""
EXAMPLE_B = rr.JUDGMENT_EXAMPLE.format(name="y.py::b")
FIVE = "拐彎判斷｜y.py::b｜會：第 4 個彎在 while｜四層巢狀兩塊各自巢狀，讀的人要同時記四個條件｜改直：把 for 內的 if/while 抽成 _drain(x)"
FOUR = "拐彎判斷｜y.py::b｜會：第 4 個彎在 while｜四層巢狀"


def _write(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return root


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _repo(root: Path, files: dict = APP) -> Path:
    _write(root, files)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _mf(path, turn=5):
    return {"path": str(path), "tool": "Edit", "session_id": _SID, "turn_seq": turn, "last_turn_seq": turn}


def _state(*mods, **extra) -> dict:
    return {"turn_seq": 5, "modified_files": list(mods), **extra}


def _inline(path):
    """背景量測換成同一個行程直接跑完、照寫結果檔。"""
    job = json.loads(Path(path).read_text(encoding="utf-8"))
    rph.write_result(Path(job["out"]), rph.run_job(job))


def _note(state, config=None):
    """收尾兩次：第一次交給背景量（不附），第二次附上量完的結果。回第二次附的文字。"""
    first, _ = rph.reading_path_note(state, _SID, config or {}, spawn=_inline)
    assert first is None and state["reading_path"][_SID].get("job")
    second, _ = rph.reading_path_note(state, _SID, config or {}, spawn=_inline)
    assert second and not state["reading_path"][_SID].get("job")
    return second


@pytest.fixture(autouse=True)
def _jobs(tmp_path_factory, monkeypatch):
    monkeypatch.setattr(rph, "JOB_DIR", tmp_path_factory.mktemp("g11-jobs"))


@pytest.fixture()
def logs(monkeypatch):
    out: list = []
    monkeypatch.setattr(rph, "append_guard_log", lambda guard, payload: out.append((guard, payload)))
    return out


# ─── 背景量完：函式級數據、那一題、到門檻的條目 ─────────────────────────────────────

def test_nested_function_lists_metrics_question_scale_and_example_then_owed(tmp_path):
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": NESTED_B})
    state = _state(_mf(root / "y.py"))
    note = _note(state)
    assert "函式級側面數據" in note and "y.py::b｜巢狀 4｜條件塊 2｜認知 " in note and "← 要人看" in note, note
    assert rph.JUDGMENT_QUESTION in note and f"尺度原文：「{rph.SCALE_QUOTE}」" in note, "那一題問這一層存在的理由，尺度原文照抄"
    assert "這一層／這個彎存在的理由" in note and "抄" in note, "問的是理由與作用，不只報巢狀 N 層"
    assert EXAMPLE_B in note, "範例行填好函式名"
    owed = state["reading_path"][_SID]["owed"]
    assert [it["kind"] + " " + it["name"] for it in owed["items"]] == ["函式 y.py::b"] and owed["turn"] == 5


def _quiet(state, capsys, config=None) -> str:
    """收尾兩次、第二次量完但沒超線：結果文字是空的（不送模型）→ 回 stderr（沒附的數據只在這裡看得到）。"""
    first, _ = rph.reading_path_note(state, _SID, config or {}, spawn=_inline)
    assert first is None and state["reading_path"][_SID].get("job")
    capsys.readouterr()
    second, _ = rph.reading_path_note(state, _SID, config or {}, spawn=_inline)
    assert second is None and not state["reading_path"][_SID].get("job"), second
    return capsys.readouterr().err


def test_all_below_threshold_sends_no_text_and_asks_nothing(tmp_path, capsys, logs):
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": _BODY.format("b").replace("k *= 2", "k *= 3")})
    state = _state(_mf(root / "y.py"))
    err = _quiet(state, capsys)
    assert "y.py::b｜巢狀 0｜條件塊 0" in err and "沒有到門檻的條目，這段數據不附在收尾" in err, err
    assert "owed" not in state["reading_path"][_SID]
    assert rph.turn_judgment_note(state, _SID, "全部完成了。", 1, 6) == (None, False)
    measured = [p for g, p in logs if p.get("event") == "measured"]
    assert measured and measured[0]["lang"] == "py" and measured[0]["items"] == 0 and measured[0]["rows"] > 0, logs


def test_other_language_file_is_marked_unsupported_and_not_asked(tmp_path, capsys):
    root = _repo(tmp_path / "r", {**APP, "a.lua": "local x = 1\n"})
    _write(root, {"a.lua": "local x = 2\n"})
    err = _quiet(_state(_mf(root / "a.lua")), capsys)
    assert "a.lua：不支援（只算 Python 與 C#）" in err and rph.JUDGMENT_QUESTION not in err, err


CS_TURNS = """public abstract class Unit
{
    public virtual void Tick() { }
}

public class Mid : Unit
{
    public override void Tick() { base.Tick(); }
}

public class Leaf : Mid
{
    public int Walk(int[] xs, bool deep)
    {
        int n = 0;
        if (deep)
        {
            foreach (var x in xs)
            {
                if (x > 0) { n += x; }
            }
        }
        return n;
    }
}

public interface IStore { void Save(string key); }

public class FileStore : IStore
{
    public void Save(string key) { if (key.Length > 0) { key = key.Trim(); } }
}

public class Saver
{
    private IStore store;
    public void Save(string key) => store.Save(key);
}
"""


def test_cs_file_asks_only_over_line_layers_not_the_nesting_table(tmp_path):
    root = _repo(tmp_path / "r")
    _write(root, {"a.cs": CS_TURNS})
    state = _state(_mf(root / "a.cs"))
    note = _note(state)
    assert "函式級側面數據" not in note and "Leaf.Walk" not in note, "C# 巢狀深不問、不列數據表"
    assert "空層 a.cs::Saver.Save｜只轉手 → FileStore.Save：這一層沒加東西" in note, note
    assert ("類別 a.cs::Leaf｜繼承 3 層（Leaf → Mid → Unit）｜空層 1：Mid｜每層加了什麼：Leaf +Walk；"
            "Mid 無（只有空覆寫：~Tick 只呼叫上層同名方法、引數照傳）；Unit +Tick") in note, note
    names = [it["name"] for it in state["reading_path"][_SID]["owed"]["items"]]
    assert names == ["a.cs::Saver.Save", "a.cs::Mid", "a.cs::Leaf"], names
    assert rph.JUDGMENT_QUESTION in note and rr.JUDGMENT_EXAMPLE.format(name="a.cs::Saver.Save") in note


def test_cs_unparsed_parts_go_to_stderr_not_the_text(tmp_path, capsys):
    root = _repo(tmp_path / "r")
    _write(root, {"a.cs": "class A { int F() { return 2; } }\n}\n"})
    state = _state(_mf(root / "a.cs"))
    assert rph.reading_path_note(state, _SID, {}, spawn=_inline)[0] is None
    assert rph.reading_path_note(state, _SID, {}, spawn=_inline)[0] is None, "沒超線：沒有字"
    assert "a.cs：大括號不成對（第 2 行），之後的成員範圍可能錯位" in capsys.readouterr().err


def test_big_cs_project_reads_only_one_hop_up_the_base_chain(tmp_path):
    """C# 繼承鏈只讀一跳：改到的 Leaf 的基底 Mid 讀進來，Mid 的基底 Base 在兩跳外，標接不到、不往上讀。"""
    files = {"game/Leaf.cs": "public class Leaf : Mid\n{\n    public void Go() { }\n}\n",
             "core/Mid.cs": "public class Mid : Base\n{\n}\n",
             "base/Base.cs": "public class Base\n{\n    public virtual void Run() { }\n}\n",
             **{f"fill/F{i}.cs": f"public class F{i}\n{{\n}}\n" for i in range(10)}}
    root = _repo(tmp_path / "r", {**APP, **files})
    _write(root, {"game/Leaf.cs": files["game/Leaf.cs"].replace("Go() { }", "Go() { Run(); }")})
    note = _note(_state(_mf(root / "game/Leaf.cs")))
    assert "類別 game/Leaf.cs::Leaf｜繼承 2 層（Leaf → Mid，再上去 Base 接不到）｜空層 1：Mid" in note, note
    assert "共 2 檔" in note, "範圍＝Leaf 加一跳的 Mid"


def test_cs_failure_keeps_python_rows_in_the_same_batch(tmp_path, monkeypatch):
    import reading_path_cs

    def boom(*_a, **_k):
        raise ValueError("壞掉了")
    monkeypatch.setattr(reading_path_cs, "measure", boom)
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": NESTED_B, "a.cs": "class A { int F() { return 3; } }\n"})
    note = _note(_state(_mf(root / "y.py"), _mf(root / "a.cs")))
    assert "y.py::b｜巢狀 4｜條件塊 2" in note and "C# 閱讀路徑量不出來（ValueError: 壞掉了）" in note, note


def test_untracked_new_file_is_counted_not_listed(tmp_path, capsys):
    """還沒 git add 的新檔只報個數、不列檔名與函式名；這批沒有條目超線 → 這句只在 stderr（remind_only_over_threshold 開），關了才送。"""
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": _BODY.format("b") + "\n", "new.py": NESTED_B.replace("def b", "def nb")})
    err = _quiet(_state(_mf(root / "y.py"), _mf(root / "new.py")), capsys)
    assert "還沒 git add 的新檔 1 個" in err and "new.py" not in err and "nb" not in err, err
    note = _note(_state(_mf(root / "y.py"), _mf(root / "new.py")), {"reading_path": {"remind_only_over_threshold": False}})
    assert "還沒 git add 的新檔 1 個" in note and "new.py" not in note and "nb" not in note, note


def test_entry_turns_at_threshold_becomes_an_item(tmp_path):
    """改了 y.py 讓入口 main 多了一條 y→z→w 的新路：after 拐彎 ≥2 → 入口那一條也要人看。"""
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": "from z import c\n\n\ndef b(n):\n    return c(n)\n", "z.py": "from w import d\n\n\ndef c(n):\n    return d(n)\n"})
    state = _state(_mf(root / "y.py"), _mf(root / "z.py"))
    note = _note(state)
    items = state["reading_path"][_SID]["owed"]["items"]
    entry = [it for it in items if it["kind"] == "入口"]
    assert entry and "w.py::d" in entry[0]["name"] and "拐彎" in entry[0]["nums"], (items, note)
    assert any(k == "w.py::d" for k in entry[0]["keys"]) and rr.JUDGMENT_EXAMPLE.format(name=entry[0]["name"]) in note
    hand = [it for it in items if it["kind"] == "函式"]
    assert hand and "只轉手 → c（連續 2）" in hand[0]["nums"], "y.py::b 只轉手給 c、c 再轉手給 d：連續 2 個到門檻"


def test_inherit_chain_with_empty_layer_lists_each_layer(tmp_path):
    root = _repo(tmp_path / "r", {**APP, "k.py": "class Base:\n    def run(self):\n        return 1\n"})
    _write(root, {"k.py": "class Base:\n    def run(self):\n        return 1\n\n\nclass Mid(Base):\n    pass\n\n\n"
                          "class Leaf(Mid):\n    def run(self):\n        return 2\n\n    def extra(self):\n        return 3\n"})
    state = _state(_mf(root / "k.py"))
    note = _note(state)
    assert "k.py::Leaf｜繼承 3 層（Leaf → Mid → Base）｜空層 1：Mid｜每層加了什麼：Leaf +extra ~run；Mid 無；Base +run" in note, note
    names = [it["name"] for it in state["reading_path"][_SID]["owed"]["items"]]
    assert "k.py::Leaf" in names and "k.py::Mid" in names and "k.py::Base" not in names, "Mid 2 層但有空層也要人看；Base 1 層不問"


# ─── 收尾核對：擋一次、點名缺欄、五欄齊放行留帳 ───────────────────────────────────

def _owed_state(tmp_path):
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": NESTED_B})
    state = _state(_mf(root / "y.py"))
    _note(state)
    return state


def test_missing_judgment_blocks_once_per_user_turn_with_named_example(tmp_path, logs):
    state = _owed_state(tmp_path)
    msg, changed = rph.turn_judgment_note(state, _SID, "全部完成了。", 1, 6)
    assert changed and msg.startswith("[Guardian:ReadingPath] ✗ (t) TURN_JUDGMENT_REQUIRED：") and "y.py::b" in msg, msg
    assert f"- 函式 y.py::b｜巢狀 4｜條件塊 2" in msg and EXAMPLE_B in msg and rph.JUDGMENT_QUESTION in msg and rph.SCALE_QUOTE in msg
    assert logs[-1][0] == "reading_path" and logs[-1][1]["event"] == "judgment_block"
    assert rph.turn_judgment_note(state, _SID, "全部完成了。", 1, 7) == (None, False), "同一個使用者回合不再擋"
    again, _ = rph.turn_judgment_note(state, _SID, "全部完成了。", 2, 8)
    assert again and "TURN_JUDGMENT_REQUIRED" in again, "下一個使用者回合還缺 → 再擋一次"


def test_four_columns_block_and_name_the_missing_column(tmp_path):
    state = _owed_state(tmp_path)
    msg, _ = rph.turn_judgment_note(state, _SID, f"完成。\n{FOUR}\n", 1, 6)
    assert msg and "缺「怎麼改直／合理，因為…」欄" in msg and "已寫但缺欄" in msg, msg
    msg, _ = rph.turn_judgment_note(state, _SID, f"完成。\n{EXAMPLE_B}\n", 2, 7)
    assert msg and "缺「" in msg, "照抄範例（角括號佔位）不算填"


def test_five_columns_pass_clear_owed_and_log_judged(tmp_path, logs):
    state = _owed_state(tmp_path)
    assert rph.turn_judgment_note(state, _SID, f"完成。\n{FIVE}\n", 1, 6) == (None, True)
    assert "owed" not in state["reading_path"][_SID]
    assert logs[-1] == ("reading_path", {"event": "judged", "session_id": _SID, "turn_seq": 6, "job_turn": 5,
                                         "items": ["y.py::b"], "lines": [FIVE]})
    other = _owed_state(tmp_path / "2")
    text = "完成。\n拐彎判斷 | y.py::b | 這一層沒有作用，因為只是把 while 包起來 | 四層巢狀 | 合理，因為迴圈體本來就要兩層"
    assert rph.turn_judgment_note(other, _SID, text, 1, 6) == (None, True), "第二欄答「這一層沒有作用，因為…」也算有答；半形 | 也收"
    assert rr.judgment_names("y.py::b", ["y.py::b", "b"]) and not rr.judgment_names("b", ["y.py::b", "b"]), "對象欄至少 2 字才認"


def test_judgment_target_matches_whole_names_not_substrings():
    """codex 審 G11 BLOCK 1：對象欄只認整名或邊界結尾，y.py::load_config 的那一行不能替 y.py::load 清帳。"""
    load = {"kind": "函式", "name": "svc.py::load", "keys": ["svc.py::load", "load"], "nums": "巢狀 3"}
    cfgf = {"kind": "函式", "name": "svc.py::load_config", "keys": ["svc.py::load_config", "load_config"], "nums": "巢狀 3"}
    js = rr.parse_turn_judgments("拐彎判斷｜svc.py::load_config｜不會｜一層｜合理，因為短")
    v = rr.turn_judgment_verdict([load, cfgf], js)
    assert v.owed and "svc.py::load｜" in "".join(v.evidence) and "load_config｜" not in "".join(v.evidence)
    assert rr.judgment_names("hooks/svc.py::load", ["svc.py::load"]) and rr.judgment_names("Cls.load", ["load"])
    assert not rr.judgment_names("reload", ["load"]) and not rr.judgment_names("svc.py::loader", ["svc.py::load"])


def test_quoted_or_fenced_judgment_lines_do_not_count():
    """codex 審 G11 BLOCK 2：引用上一版的行（> 引言、圍欄程式碼）不算這次的回答；清單記號開頭的算。"""
    text = "> 拐彎判斷｜y.py::b｜不會｜一層｜合理，因為短\n```\n拐彎判斷｜y.py::b｜不會｜一層｜合理，因為短\n```\n上面是引用。"
    assert rr.parse_turn_judgments(text) == []
    assert len(rr.parse_turn_judgments("- 拐彎判斷｜y.py::b｜不會｜一層｜合理，因為短\n1. 拐彎判斷｜y.py::c｜會：第 4 個彎｜四層｜抽函式")) == 2
    assert rr.parse_turn_judgments("擋訊息說：拐彎判斷｜y.py::b｜<不會／會>｜<理由>｜<怎麼改直>") == [], "行中間提到的不算"


def test_new_code_batch_holds_stale_owed_without_blocking(tmp_path):
    state = _owed_state(tmp_path)
    root = Path(state["modified_files"][0]["path"]).parent
    _write(root, {"y.py": _BODY.format("b") + "\n"})
    state["turn_seq"] = 6
    state["modified_files"] = [_mf(root / "y.py", 6)]
    assert rph.reading_path_note(state, _SID, {}, spawn=lambda p: None) == (None, True)
    assert state["reading_path"][_SID]["owed"].get("stale"), "又改了碼：上一批的條目標 stale，新的一批量完換掉"
    assert rph.turn_judgment_note(state, _SID, "全部完成了。", 1, 6) == (None, False), "stale 的條目不擋"
    assert rph.turn_judgment_missing(state, _SID, "全部完成了。", 1) == [], "預覽也不列"


def test_threshold_config_and_item_cap(tmp_path, capsys):
    cfg = {"reading_path": {"turn_judgment": {"nesting": 9, "bumpy": 9, "turns": 9, "max_items": 1, "bad": "x"}}}
    assert rph.turn_judgment_cfg(cfg) == {**rph.TURN_JUDGMENT_DEFAULTS, "nesting": 9, "bumpy": 9, "turns": 9, "max_items": 1}
    root = _repo(tmp_path / "r")
    _write(root, {"y.py": NESTED_B})
    state = _state(_mf(root / "y.py"))
    err = _quiet(state, capsys, cfg)
    assert "y.py::b｜巢狀 4" in err and "要人看" not in err and "owed" not in state["reading_path"][_SID], "門檻調高就不問、不附字"
    items = [{"kind": "函式", "name": f"f{i}", "keys": [f"f{i}"], "nums": "巢狀 3"} for i in range(3)]
    block = "\n".join(rph.judgment_block(items[:1], rph.turn_judgment_cfg(cfg), dropped=2))
    assert "要人看的 1 條" in block and "另 2 條也到門檻，一批最多問 1 條" in block, "超過上限的條數要說出來，不當成低於門檻"


# ─── 真 Stop 入口 ─────────────────────────────────────────────────────────────

@pytest.fixture()
def driven(monkeypatch):
    """驅動 handle_stop（同 verify_stop_reconcile 的夾具）：回 drive(text, capsys, state 欄位…) → (stdout, state, guard log)。"""
    logs: list = []
    monkeypatch.setattr(st, "_find_session_transcript", lambda *a, **k: None)
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "detect_evasion", lambda *a, **k: None)
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "_attribute_usefulness", lambda *a, **k: None)
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    monkeypatch.setattr(st, "_maybe_spawn_user_extract_worker", lambda *a, **k: None)
    monkeypatch.setattr(st, "_hud_alive", lambda *a, **k: (True, {}))
    monkeypatch.setattr(st, "harvest_gate_reason", lambda *a, **k: None)
    monkeypatch.setattr(st, "pending_gate_reason", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(rph, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(rph, "_spawn_worker", _inline)
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)

    def drive(text, capsys, **extra):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: text)
        monkeypatch.setattr(st, "get_current_turn_visible_text", lambda *a, **k: ("", {"turn_tool_names_all": []}))
        state = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": [],
                 "stop_blocked_count": 0, "turn_seq": 5}
        state.update(extra)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        logs.clear()
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, {"verify_scope": {"enabled": False}})
        return capsys.readouterr().out, state, list(logs)

    return drive


def test_real_stop_blocks_with_the_data_until_judgment_lines_arrive(driven, capsys, tmp_path, monkeypatch):
    """改碼回合交給背景量；量完那次收尾缺拐彎判斷行 → 擋（規則名、數據、那一題、範例行都在訊息裡）；補五欄行 → 不再擋、留帳 judged。"""
    monkeypatch.setattr(ev, "get_last_assistant_text", lambda *a, **k: "", raising=False)
    # 拐彎判斷排在寫碼查核之後：這案真的改了 y.py，(d) 會先擋；本案只看拐彎判斷這條路，寫碼查核換成全過
    monkeypatch.setattr(st, "_verify_gates", lambda *a, **k: (None, None, "", None))
    root = _repo(tmp_path / "rp")
    _write(root, {"y.py": NESTED_B})
    mods = [_mf(str(root / "y.py"), 5)]
    out, state, _ = driven("全部完成了。", capsys, modified_files=mods)
    assert "TURN_JUDGMENT_REQUIRED" not in out and state["reading_path"][_SID]["job"], "交給背景量的那次還沒有數據"
    out, state, logs = driven("全部完成了。", capsys, modified_files=mods, reading_path=state["reading_path"])
    reason = json.loads(out)["reason"]
    assert "✗ (t) TURN_JUDGMENT_REQUIRED" in reason and EXAMPLE_B in reason and rph.SCALE_QUOTE in reason, reason[-1500:]
    assert "[Guardian:ReadingPath] 第 5 回合改動對閱讀路徑的影響（背景量完" in reason and "y.py::b｜巢狀 4" in reason
    assert ("reading_path", {**logs[-1][1]}) in logs and logs[-1][1]["event"] == "judgment_block"
    assert state["stop_blocked_count"] == 0, "不吃 stop_gate_max_blocks"
    out, state, logs = driven(f"全部完成了。\n{FIVE}", capsys, modified_files=mods, reading_path=state["reading_path"])
    assert "TURN_JUDGMENT_REQUIRED" not in out and "owed" not in state["reading_path"][_SID]
    assert any(g == "reading_path" and p.get("event") == "judged" for g, p in logs)


# ─── 擋點在寫碼查核（對帳）之後、與 G9／G7 同序同預覽 ─────────────────────────────────────

_ITEM_B = {"kind": "函式", "name": "y.py::b", "keys": ["y.py::b", "b"], "nums": "巢狀 4｜條件塊 2"}


def _owed():
    """背景量完、y.py::b 一條到門檻還沒判：直接放進 state（不改檔、不起背景量測，對帳不會因為改碼而擋）。"""
    return {_SID: {"owed": {"turn": 5, "items": [dict(_ITEM_B)]}}}


def _reason(out: str) -> str:
    return json.loads(out)["reason"] if out.strip() else ""


def _also(reason: str) -> str:
    return next((ln for ln in reason.splitlines() if ln.startswith("[Guardian:AlsoOwed]")), "")


def test_reconcile_blocks_first_and_its_preview_lists_turn_judgment(driven, capsys):
    """同一回合「宣稱修好沒收據」＋「缺拐彎判斷行」→ 擋的是對帳 (a)，尾段「後面還會擋」列拐彎判斷缺 1 條；預覽只讀，
    這回合拐彎判斷的那一次還在：下一次收尾對帳過了才輪到它擋。舊碼先被拐彎判斷擋、訊息裡沒有 (a)。"""
    out, state, logs = driven("閘修好了，完成。", capsys, reading_path=_owed())
    reason = _reason(out)
    assert "[Guardian:ReconcileGate]" in reason and "(a)" in reason and "TURN_JUDGMENT_REQUIRED" not in reason, reason[:800]
    assert "拐彎判斷：缺 1 條，" in _also(reason) and "y.py" not in _also(reason), reason[-800:]   # 預覽只報個數、不列檔名
    assert "blocked_turn" not in state["reading_path"][_SID] and not [g for g, _ in logs if g == "reading_path"], \
        "預覽不記擋、不留帳"
    out, _, logs = driven("全部完成了。", capsys, reading_path=state["reading_path"])
    assert "✗ (t) TURN_JUDGMENT_REQUIRED" in _reason(out) and "[Guardian:ReconcileGate]" not in _reason(out)
    assert [p["event"] for g, p in logs if g == "reading_path"] == ["judgment_block"]


def test_reconcile_clear_missing_judgment_blocks_with_items_and_named_example(driven, capsys):
    """對帳全過、缺拐彎判斷行 → 擋的是拐彎判斷：列缺的條目與填好名字的範例行（同 001），不吃 stop_gate_max_blocks。"""
    out, state, logs = driven("全部完成了。", capsys, reading_path=_owed())
    reason = _reason(out)
    assert reason.startswith("[Guardian:ReadingPath] ✗ (t) TURN_JUDGMENT_REQUIRED："), reason[:400]
    assert "- 函式 y.py::b｜巢狀 4｜條件塊 2" in reason and EXAMPLE_B in reason and rph.JUDGMENT_QUESTION in reason
    assert "blocked_turn" in state["reading_path"][_SID] and state["stop_blocked_count"] == 0
    assert [p["event"] for g, p in logs if g == "reading_path"] == ["judgment_block"]


def test_reconcile_clear_five_columns_pass_and_log_judged(driven, capsys):
    """對帳全過、五欄行齊 → 不擋拐彎判斷、清掉條目、guard log 記 judged（確認搬段沒丟留帳）。"""
    state0 = _owed()
    assert state0[_SID]["owed"]["items"], "前置：有到門檻的條目"
    out, state, logs = driven(f"全部完成了。\n{FIVE}", capsys, reading_path=state0)
    assert "TURN_JUDGMENT_REQUIRED" not in out and "owed" not in state["reading_path"][_SID]
    assert [p for g, p in logs if g == "reading_path"] == [
        {"event": "judged", "session_id": _SID, "turn_seq": 5, "job_turn": 5, "items": ["y.py::b"], "lines": [FIVE]}]


def test_second_stop_in_same_user_turn_still_missing_is_not_blocked_again(driven, capsys):
    """每個使用者回合擋一次：同回合第二次收尾仍缺 → 不再擋（預算沒因搬段變兩次）；使用者開了下一回合還缺 → 再擋一次。"""
    out, state, _ = driven("全部完成了。", capsys, reading_path=_owed())
    assert "TURN_JUDGMENT_REQUIRED" in _reason(out), "前置：第一次有擋"
    out, state, logs = driven("全部完成了。", capsys, reading_path=state["reading_path"])
    assert "TURN_JUDGMENT_REQUIRED" not in out and state["reading_path"][_SID].get("owed"), "還缺，但這回合不再擋"
    assert not [g for g, _ in logs if g == "reading_path"]
    out, _, _ = driven("全部完成了。", capsys, reading_path=state["reading_path"], turn_seq=7, turn_prompts_seq=7)
    assert "TURN_JUDGMENT_REQUIRED" in _reason(out), "下一個使用者回合還缺 → 再擋一次"


def test_turn_judgment_sits_before_second_opinion_and_shares_its_preview(driven, capsys, monkeypatch):
    """與 G9 同一序列：對帳過、缺判斷行、也還欠第二意見 → 先擋拐彎判斷，尾段預告第二意見（舊碼這裡還沒掛預覽）；
    同回合再收尾 → 拐彎判斷這回合不會再擋，輪到第二意見擋，它的預覽不再列拐彎判斷。"""
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.delenv("CLAUDE_COMPANION_JUDGE", raising=False)
    so = rr.Verdict("SECOND_OPINION_REQUIRED", True, "本回合沒有跑第二意見", ("程式檔 5 個",))
    monkeypatch.setattr(st, "_so_facts", lambda *a, **k: (so, {"code_files": 5}))
    out, state, _ = driven("全部完成了。", capsys, reading_path=_owed())
    reason = _reason(out)
    assert reason.startswith("[Guardian:ReadingPath] ✗ (t) TURN_JUDGMENT_REQUIRED") and "[Guardian:SecondOpinion]" not in reason
    assert "第二意見：" in _also(reason) and "拐彎判斷" not in _also(reason), reason[-800:]
    out, state, _ = driven("全部完成了。", capsys, reading_path=state["reading_path"])
    reason = _reason(out)
    assert reason.startswith("[Guardian:SecondOpinion]") and "TURN_JUDGMENT_REQUIRED" not in reason, reason[:400]
    assert "拐彎判斷" not in _also(reason)


def test_one_time_piggyback_flags_are_written_with_the_block(driven, capsys, monkeypatch):
    """_piggyback 標的一次性旗標（token 預警整個 session 附一次）要跟擋一起寫進 state：拐彎判斷閘照 TestFail 的順序（先 _piggyback
    再 write_state）；同類的等值閘（G7）原本先寫 state 再 _piggyback，旗標沒落地、下次擋又附一次 → 一起改順序。"""
    writes: list = []
    monkeypatch.setattr(st, "write_state", lambda sid, s: writes.append(copy.deepcopy(s)))
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "\n[token 預警]")
    out, _, _ = driven("全部完成了。", capsys, reading_path=_owed())
    assert "TURN_JUDGMENT_REQUIRED" in _reason(out) and "[token 預警]" in _reason(out), "前置：拐彎判斷擋、附了預警"
    assert writes and writes[-1].get("token_warn_emitted") is True, "拐彎判斷閘：旗標隨擋寫進 state"
    monkeypatch.setattr(st, "_equivalence_gate", lambda *a, **k: "[Guardian:Equivalence] 收尾核對沒過：（測試）")
    writes.clear()
    out, _, _ = driven("全部完成了。", capsys)
    assert _reason(out).startswith("[Guardian:Equivalence]") and "[token 預警]" in _reason(out), "前置：等值閘擋、附了預警"
    assert writes and writes[-1].get("token_warn_emitted") is True, "等值閘：旗標隨擋寫進 state"


def test_subagent_stop_entry_does_not_check_turn_judgment(capsys, monkeypatch):
    """子代理 Stop 只跑寫碼查核（同 001）：主 session 欠著拐彎判斷，子代理收尾照判自己的對帳、不碰拐彎判斷。"""
    logs: list = []
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(rph, "append_guard_log", lambda guard, payload: logs.append((guard, payload)))
    monkeypatch.setattr(vl, "case_exists", lambda p: True, raising=False)
    monkeypatch.setattr(vl, "code_exists", lambda p: True, raising=False)
    state = {"turn_seq": 5, "modified_files": [], "verify_receipts": {}, "reading_path": _owed(),
             "agent_modified_files": {"ag1": [_mf(r"c:\proj\hooks\x.py")]}}
    monkeypatch.setattr(st, "read_state", lambda sid: state)
    with pytest.raises(SystemExit):
        st.handle_subagent_stop({"session_id": _SID, "agent_id": "ag1", "hook_event_name": "SubagentStop",
                                 "last_assistant_message": "全部完成了。"}, {"verify_scope": {"enabled": False}})
    out = capsys.readouterr().out
    assert "[Guardian:ReconcileGate]" in out, "前置：子代理收尾的寫碼查核有跑到"
    assert "TURN_JUDGMENT_REQUIRED" not in out and "拐彎判斷" not in out
    assert "blocked_turn" not in state["reading_path"][_SID] and not [g for g, _ in logs if g == "reading_path"]


# ─── 思考的彎：reconcile 的 turns ───────────────────────────────────────────────

def test_reconcile_turns_over_three_needs_a_rethink_note():
    items = [{"id": "T1", "status": "done"}]
    errs = ng.validate_input({"action": "reconcile", "items": items, "turns": 5})
    assert any("重找最短路" in e and "turns=5" in e for e in errs), errs
    assert not ng.validate_input({"action": "reconcile", "items": [{"id": "T1", "status": "done", "note": "重找最短路：改成一支純函式，少兩個檔"}],
                                  "turns": 5})
    assert not ng.validate_input({"action": "reconcile", "items": items, "turns": 2})
    assert not ng.validate_input({"action": "reconcile", "items": items, "turns": 4 - 1}), "三個彎是警戒極限，第四個才要求重找"
    assert any("重找最短路" in e for e in ng.validate_input({"action": "reconcile", "items": [{"id": "T1", "status": "done", "note": "重找最短路："}],
                                                             "turns": 4})), "只有標籤沒有結果不算"


def test_reconcile_without_turns_is_accepted_with_a_reminder(tmp_path, monkeypatch):
    wf = tmp_path / "wf"
    wf.mkdir()
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "append_guard_log", lambda g, p: None)
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    sid = "sess-g11-turns"
    assert ng.apply_op(sid, 1, {"action": "set", "goal": "G"}, str(tmp_path))["ok"]
    note = tmp_path / "n.md"
    note.write_text("x", encoding="utf-8")
    ev_ = [{"kind": "file", "ref": str(note), "level": "read"}]
    r = ng.apply_op(sid, 2, {"action": "reconcile", "items": [{"id": "T1", "status": "done", "evidence": ev_}]}, str(tmp_path))
    assert r["ok"] and ng.TURNS_HINT in r["text"], r["text"][:600]
    assert ng.apply_op(sid, 3, {"action": "set", "goal": "G2", "new_task": True, "why": "另一件"}, str(tmp_path))["ok"]
    r = ng.apply_op(sid, 4, {"action": "reconcile", "items": [{"id": "T2", "status": "done", "evidence": ev_}], "turns": 2}, str(tmp_path))
    assert r["ok"] and ng.TURNS_HINT not in r["text"] and ng.load(sid)["trees"]["T2"]["last_reconcile"]["turns"] == 2


@pytest.fixture(autouse=True)
def _block_mode(monkeypatch):
    """規則 GATE_MODE_TABLE：送法只讀 wg_release_rules.RULE_MODE。這個檔的案例驗的是判定與擋訊息內容，把送法釘成 block 讓它們照驗；
    v6 預設的提醒送法（Stop 只留帳、提醒掛改檔那則工具結果）由 verify_gate_mode_stop.py 驗。"""
    import wg_release_rules as _rr
    monkeypatch.setattr(_rr, "mode_of", lambda rule: _rr.BLOCK)
