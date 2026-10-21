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


HOLLOW_PY = """from abc import abstractmethod


class Unit:
    def tick(self):
        n = 1

    @abstractmethod
    def hit(self, damage):
        ...


class Soldier(Unit):
    def tick(self):
        super().tick()


class Guard(Soldier):
    def hit(self, damage):
        pass


class Captain(Guard):
    def shout(self):
        n = 2

    def tick(self):
        super().tick()
        self.shout()


class Invulnerable(Unit):
    def tick(self):
        pass

    def hit(self, damage):
        pass
"""

HOLLOW_CS = """public abstract class Unit
{
    public virtual void tick() { int n = 1; }
    public abstract void hit(int damage);
}

public abstract class Soldier : Unit
{
    public override void tick() { base.tick(); }
}

public class Guard : Soldier
{
    public override void hit(int damage) { }
}

public class Captain : Guard
{
    public void shout() { int n = 2; }
    public override void tick()
    {
        base.tick();
        shout();
    }
}

public class Invulnerable : Unit
{
    public override void tick() { }
    public override void hit(int damage) { }
}
"""

HOLLOW_EDGES = """class Base:
    def run(self, x, *args, **kw):
        return x

    def stop(self):
        raise NotImplementedError


class Old(Base):
    def run(self, x, *args, **kw):
        return super(Old, self).run(x, *args, **kw)


class Doubled(Base):
    def run(self, x, *args, **kw):
        return super().run(x * 2, *args, **kw)


class Fresh(Base):
    def extra(self):
        pass

    def stop(self):
        '''什麼都不做'''


class Outside(Thing):
    def go(self):
        pass
"""

HOLLOW_TRAPS = """from abc import abstractmethod


class Base:
    def run(self, x):
        return x


class Logged(Base):
    def run(self, x):
        print(x)
        return super().run(x)


class Skip(Logged):
    def run(self, x):
        return super(Logged, self).run(x)


class Swallow(Base):
    def run(self, x):
        super().run(x)


class Redef(Base):
    def run(self, x):
        return x + 1

    def run(self, x):
        return super().run(x)


class Kw:
    def go(self, *, a, b):
        return a


class KwOrder(Kw):
    def go(self, *, a, b):
        return super().go(b=b, a=a)


class Fetch:
    async def get(self, k):
        return k


class NoAwait(Fetch):
    async def get(self, k):
        return super().get(k)


class Awaited(Fetch):
    async def get(self, k):
        return await super().get(k)


class AbsBody:
    @abstractmethod
    def save(self):
        self.dirty = False


class SkipSave(AbsBody):
    def save(self):
        pass
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


def _classes(tmp_path, name, src):
    p = tmp_path / name
    p.write_text(src, encoding="utf-8", newline="\n")
    return {r["name"]: r for r in tm.metrics_for_files([str(p)]) if r["kind"] == "class"}


def test_hollow_layers_only_super_call_or_filling_an_abstract_count_as_empty(tmp_path):
    cls = _classes(tmp_path, "h.py", HOLLOW_PY)
    cap = cls["Captain"]
    assert [l["name"] for l in cap["layers"]] == ["Captain", "Guard", "Soldier", "Unit"]
    assert cap["depth"] == 4 and cap["empty_layers"] == 2, cap["layers"]
    me, guard, soldier, _ = cap["layers"]
    assert not me["empty"] and me["hollow"] == {}, "super().tick() 之外還做事 → 不算空"
    assert guard["empty"] and "抽象" in guard["hollow"]["hit"], "補抽象宣告的空本體"
    assert soldier["empty"] and "上層同名" in soldier["hollow"]["tick"], "只呼叫 super 同名方法、引數照傳"
    inv = cls["Invulnerable"]["layers"][0]
    assert not inv["empty"] and "擋掉上層的實作" in inv["hollow"]["tick"], "空覆寫擋掉上層有本體的實作：照列、不算空"


def test_hollow_edges_super_forms_changed_args_new_empty_method_and_outside_base(tmp_path):
    cls = _classes(tmp_path, "e.py", HOLLOW_EDGES)
    assert cls["Old"]["layers"][0]["empty"] and cls["Old"]["empty_layers"] == 1, "super(Old, self).run(x, *args, **kw) 也是照傳"
    assert not cls["Doubled"]["layers"][0]["empty"] and cls["Doubled"]["layers"][0]["hollow"] == {}, "x * 2 有加工"
    fresh = cls["Fresh"]["layers"][0]
    assert fresh["added"] == ["extra"] and "extra" not in fresh["hollow"], "上層沒有的空方法是新增，不是空殼"
    assert "抽象" in fresh["hollow"]["stop"] and not fresh["empty"], "raise NotImplementedError 的上層算抽象宣告；但 extra 是新增"
    out = cls["Outside"]["layers"][0]
    assert not out["empty"] and "掃不到的基底" in out["hollow"]["go"], "上層接不到：可能擋掉了什麼，照列不算空"


def test_super_shapes_that_change_behavior_are_not_hollow(tmp_path):
    """看起來像照傳、其實改了行為：super(別的類別) 跳過中間層、沒 return 吞掉上層回傳值、async 沒 await、抽象方法自己有本體被空覆寫擋掉；
    反過來，關鍵字換順序照傳、同名重定義時後面那個是照傳，仍是空殼。"""
    cls = _classes(tmp_path, "t.py", HOLLOW_TRAPS)
    for name in ("Skip", "Swallow", "NoAwait"):
        layer = cls[name]["layers"][0]
        assert not layer["empty"] and layer["hollow"] == {}, (name, layer)
    skip_save = cls["SkipSave"]["layers"][0]
    assert not skip_save["empty"] and "擋掉上層的實作" in skip_save["hollow"]["save"], skip_save
    for name in ("Redef", "KwOrder", "Awaited"):
        layer = cls[name]["layers"][0]
        assert layer["empty"] and list(layer["hollow"]) == [layer["overridden"][0]], (name, layer)


def test_same_hollow_shape_in_python_and_csharp_gives_same_layers(tmp_path):
    import turn_metrics_cs as tmc
    py = _classes(tmp_path, "h.py", HOLLOW_PY)
    cs_path = tmp_path / "H.cs"
    cs_path.write_text(HOLLOW_CS, encoding="utf-8", newline="\n")
    cs = {r["name"]: r for r in tmc.metrics_for_files([str(cs_path)]) if r["kind"] == "class"}
    for name in ("Captain", "Guard", "Soldier", "Invulnerable"):
        shape = lambda r: (r["depth"], r["empty_layers"],
                           [(l["name"], l["added"], l["overridden"], l["empty"], l["hollow"]) for l in r["layers"]])
        assert shape(py[name]) == shape(cs[name]), (name, shape(py[name]), shape(cs[name]))


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
