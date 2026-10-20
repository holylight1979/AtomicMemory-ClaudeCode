"""verify_turn_metrics.py：函式級與類別級側面數據（lib/turn_metrics.py，純 ast、只算不判）。

正例：四層巢狀＋兩個各自巢狀的 if 區塊 → nesting=4、bumpy=2、cognitive ≥ 6、長度正確；直線函式全 0；elif 不加深度；
      只轉手（本體一句呼叫）記被呼叫的名字、連續轉手鏈數到底；繼承鏈每層列新增／覆寫、空層標 empty、接不到的基底記下；
      diff 行區間只挑命中的函式與類別；非 Python 檔標不支援；解析失敗記 error；CLI 尾行 TURN_METRICS DONE。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider lib/verify/verify_turn_metrics.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

import turn_metrics as tm  # noqa: E402

NESTED = """def f(a):
    if a:
        for x in a:
            if x:
                while x:
                    x -= 1
    if a:
        if a:
            pass
    return a
"""
STRAIGHT = "def g(n):\n    k = n + 1\n    return k\n"
ELIF = "def e(a):\n    if a:\n        return 1\n    elif a == 2:\n        return 2\n    else:\n        return 3\n"
HANDOFF = 'def w1(x):\n    """doc"""\n    return w2(x)\n\n\ndef w2(x):\n    return g(x)\n\n\ndef g(x):\n    k = x + 1\n    return k\n'
CLASSES = """class Base:
    LIMIT = 3

    def run(self):
        return 1

    def stop(self):
        return 0


class Mid(Base):
    pass


class Leaf(Mid):
    def run(self):
        return 2

    def extra(self):
        return 3


class Ext(SomethingOutside):
    def go(self):
        return 1
"""


def _funcs(src):
    return {f["name"]: f for f in tm.function_metrics(src, "s.py")[0]}


def test_nested_function_counts_depth_bumps_and_cognitive_points():
    f = _funcs(NESTED)["f"]
    assert (f["nesting"], f["bumpy"]) == (4, 2)
    assert f["cognitive"] >= 6 and f["length"] == 10 and f["handoff"] is None


def test_straight_line_function_is_all_zero():
    g = _funcs(STRAIGHT)["g"]
    assert (g["nesting"], g["bumpy"], g["cognitive"], g["length"]) == (0, 0, 0, 3)


def test_elif_chain_does_not_deepen_but_each_branch_scores_one():
    e = _funcs(ELIF)["e"]
    assert e["nesting"] == 1 and e["bumpy"] == 0 and e["cognitive"] == 3


def test_try_with_and_nested_def_counted_the_same_way():
    src = ("def t(a):\n    try:\n        with a:\n            if a:\n                pass\n    except ValueError:\n        pass\n"
           "    def inner(b):\n        if b:\n            if b:\n                pass\n    return a\n")
    fs = _funcs(src)
    assert fs["t"]["nesting"] == 3 and fs["t"]["bumpy"] == 1 and fs["t"]["cognitive"] == 1 + 1   # with 不加巢狀：if +1、except +1
    assert fs["t.inner"]["nesting"] == 2 and fs["t.inner"]["bumpy"] == 1, "巢狀定義各自一筆，不算進外層"


def test_handoff_records_callee_and_chain_length(tmp_path):
    p = tmp_path / "h.py"
    p.write_text(HANDOFF, encoding="utf-8")
    rows = {r["name"]: r for r in tm.metrics_for_files([str(p)]) if r["kind"] == "func"}
    assert rows["w1"]["handoff"] == "w2" and rows["w1"]["handoff_chain"] == 2, "w1 → w2 → g：連續轉手 2 個"
    assert rows["w2"]["handoff"] == "g" and rows["w2"]["handoff_chain"] == 1
    assert rows["g"]["handoff"] is None and rows["g"]["handoff_chain"] == 0
    meth = _funcs("class C:\n    def a(self):\n        return self.b(1)\n\n    async def c(self):\n        await self.a()\n")
    assert meth["C.a"]["handoff"] == "self.b" and meth["C.c"]["handoff"] == "self.a"


def test_inherit_layers_list_added_overridden_and_empty_layers(tmp_path):
    p = tmp_path / "c.py"
    p.write_text(CLASSES, encoding="utf-8")
    rows = {r["name"]: r for r in tm.metrics_for_files([str(p)]) if r["kind"] == "class"}
    leaf = rows["Leaf"]
    assert leaf["depth"] == 3 and leaf["empty_layers"] == 1 and leaf["unresolved_base"] is None
    assert [l["name"] for l in leaf["layers"]] == ["Leaf", "Mid", "Base"]
    assert leaf["layers"][0]["added"] == ["extra"] and leaf["layers"][0]["overridden"] == ["run"]
    assert leaf["layers"][1]["empty"] and leaf["layers"][1]["added"] == []
    assert leaf["layers"][2]["added"] == ["LIMIT", "run", "stop"]
    assert rows["Ext"]["depth"] == 1 and rows["Ext"]["unresolved_base"] == "SomethingOutside"


def test_inherit_chain_resolves_bases_in_other_files_only_through_resolve_files(tmp_path):
    (tmp_path / "base.py").write_text("class Base:\n    def run(self):\n        return 1\n", encoding="utf-8")
    sub = tmp_path / "sub.py"
    sub.write_text("from base import Base\n\n\nclass Sub(Base):\n    pass\n", encoding="utf-8")
    alone = [r for r in tm.metrics_for_files([str(sub)]) if r["kind"] == "class"][0]
    assert alone["depth"] == 1 and alone["unresolved_base"] == "Base"
    joined = [r for r in tm.metrics_for_files([str(sub)], resolve_files=[str(tmp_path / "base.py")]) if r["kind"] == "class"]
    assert len(joined) == 1 and joined[0]["depth"] == 2 and joined[0]["empty_layers"] == 1, "resolve_files 只查對象、不列進結果"


def test_parse_diff_ranges_reads_new_side_hunks_including_pure_deletions():
    diff = ("diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -3,2 +3,4 @@\n+a\n+b\n@@ -20 +22,0 @@\n-gone\n"
            "--- a/y.py\n+++ b/y.py\n@@ -1 +1 @@\n-q\n+r\n")
    assert tm.parse_diff_ranges(diff) == {"x.py": [(3, 6), (22, 22)], "y.py": [(1, 1)]}


def test_ranges_pick_only_hit_functions_and_classes(tmp_path):
    p = tmp_path / "m.py"
    p.write_text(STRAIGHT + "\n\n" + NESTED + "\n\n" + CLASSES, encoding="utf-8")
    rows = tm.metrics_for_files([str(p)], {str(p): [(5, 6)]})
    assert [r["name"] for r in rows] == ["f"], "只有 f 落在第 5～6 行"
    rows = tm.metrics_for_files([str(p)], {str(p): [(28, 28)]})
    assert [(r["kind"], r["name"]) for r in rows] == [("class", "Mid")], "第 28 行是 class Mid"
    assert tm.metrics_for_files([str(p)], {}) == [], "有 ranges 但這個檔沒命中 → 不列"


def test_unsupported_and_broken_files_are_reported_not_raised(tmp_path):
    cs = tmp_path / "a.cs"
    cs.write_text("class A {}", encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_text("def (:\n", encoding="utf-8")
    rows = tm.metrics_for_files([str(cs), str(bad), str(tmp_path / "missing.py")])
    kinds = {r["file"]: r["kind"] for r in rows}
    assert kinds[str(cs)] == "unsupported" and next(r for r in rows if r["file"] == str(cs))["lang"] == "不支援"
    assert kinds[str(bad)] == "error" and "SyntaxError" in next(r["error"] for r in rows if r["file"] == str(bad))
    assert kinds[str(tmp_path / "missing.py")] == "error"


def test_cli_prints_one_json_per_row_and_a_done_tail(tmp_path):
    p = tmp_path / "s.py"
    p.write_text(NESTED + "\n\n" + CLASSES, encoding="utf-8")
    out = subprocess.run([sys.executable, "-X", "utf8", str(LIB / "turn_metrics.py"), str(p)],
                         capture_output=True, text=True, encoding="utf-8")
    lines = out.stdout.strip().splitlines()
    assert out.returncode == 0 and lines[-1] == "TURN_METRICS DONE funcs=6 classes=4", out.stdout[-300:]
    assert lines[0].startswith('{"kind": "func"') and '"nesting": 4' in lines[0]
