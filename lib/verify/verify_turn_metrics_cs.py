"""verify_turn_metrics_cs.py：C# 的函式級與類別級側面數據（lib/turn_metrics_cs.py，括號配對＋小型本體解析，只算不判）。

正例：繼承 4 層其中 2 層只有「只呼叫 base 同名方法」或「空本體」的覆寫 → 那兩層標空層、每層新增／覆寫算對；只轉手的包裝與連續轉手鏈；
      介面只有一個實作 → 經過它的包裝標分派、轉手鏈多算一手、介面那筆列實作；巢狀 3 層 if／foreach → 深度 3；else if 不加深度、
      沒大括號的 if、switch、try／catch、區塊 lambda 加一層、初始化子的大括號不算；Unity MonoBehaviour 樣本（Awake／Update 巢狀、
      GetComponent 鏈）；欄位名與 turn_metrics 一致；diff 行區間只挑命中的；CLI 尾行 TURN_METRICS_CS DONE。
反例（看起來像、但有真正作用）：覆寫裡 base 呼叫改了引數、或 base 之外還做事 → 不算空；介面有兩個實作 → 不標分派；
      本體一句但不是單純呼叫（讀屬性再運算、呼叫後再運算）→ 不算只轉手。
解析不到：partial（只併得到掃到的分檔）、#else 兩支都算、大括號不成對、沒認出的頂層程式 → unparsed 有列、confidence=partial，
      數字不比同一段乾淨寫法小；泛型、帶大括號的 attribute、原始字串、插值洞裡的字串、@"" 跳脫、建構子串接、帶別名的介面成員、
      箭頭本體帶初始化子、只有 #if 沒有 #else → 解析得到，不列 unparsed、數字與乾淨寫法相同。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider lib/verify/verify_turn_metrics_cs.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

import turn_metrics_cs as tmc  # noqa: E402

INHERIT = """public abstract class Unit
{
    protected int hp;
    public virtual void Tick() { hp--; }
    public abstract void Hit(int damage);
}

public abstract class Soldier : Unit
{
    public override void Tick() { base.Tick(); }
}

public class Guard : Soldier
{
    public override void Hit(int damage) { }
}

public class Captain : Guard
{
    public void Shout() { hp += 1; }
    public override void Tick()
    {
        base.Tick();
        Shout();
    }
}

public class Heavy : Guard
{
    public override void Tick() { base.Tick(); hp++; }
}

public class Armored : Guard
{
    public override void Hit(int damage) { base.Hit(damage / 2); }
}
"""

HANDOFF = """public class Facade
{
    private Service service;
    public int Run(int x) { return Step(x); }
    private int Step(int x) => service.Exec(x);
    public void Fire() { Run(1); }
    public int Score(int x) => service.Total + x;
    public int Twice(int x) { return Step(x) * 2; }
    public string Label(int x) { return $"{Step(x)} pts"; }
    public void Note() { Log("saved"); }
    private void Log(string m) { var s = m; }
}

public class Service
{
    public int Total;
    public int Exec(int x)
    {
        var y = x + 1;
        return y * 2;
    }
}
"""

DISPATCH = """public interface IStore
{
    void Save(string key);
    int Count { get; }
}

public class FileStore : IStore
{
    public int Count => 0;
    public void Save(string key)
    {
        if (key.Length > 0) { Write(key); }
    }
    private void Write(string key) { }
}

public class Saver
{
    private readonly IStore store;
    public Saver(IStore store) { this.store = store; }
    public void Save(string key) => store.Save(key);
    public void SaveVia(IStore other, string key) { other.Save(key); }
}
"""
SECOND_IMPL = """public class MemoryStore : IStore
{
    private string cache;
    public int Count => 1;
    public void Save(string key) { cache = key; }
}
"""

NESTED = """public class Grid
{
    public int Walk(int[] cells, bool deep)
    {
        int n = 0;
        if (deep)
        {
            foreach (var c in cells)
            {
                if (c > 0)
                    n += c;
                else if (c < -5)
                    n -= 1;
                else
                    n = 0;
            }
        }
        var opts = new Options { Depth = 1, Tags = new[] { "a", "b" } };
        return n;
    }

    public int Mixed(int a)
    {
        switch (a)
        {
            case 1:
                return 1;
            case 2:
            default:
                try { a++; }
                catch (System.Exception) { if (a > 0) { a--; } }
                break;
        }
        System.Action act = () => { if (a > 1) { a = 0; } };
        return a > 0 && a < 9 || a == 42 ? a : 0;
    }

    public int Flat(int a)
    {
        var b = a + 1;
        return b;
    }
}
"""

UNITY = """using UnityEngine;

public class EnemySpawner : MonoBehaviour
{
    [SerializeField] private GameObject prefab;
    [SerializeField, Range(0f, 10f)] private float interval = 2f;
    [SerializeField] private SpawnPoint[] spawnPoints;
    private Rigidbody body;
    private float timer;

    void Awake()
    {
        body = GetComponent<Rigidbody>();
        if (body == null)
        {
            body = gameObject.AddComponent<Rigidbody>();
        }
    }

    void Update()
    {
        timer += Time.deltaTime;
        if (timer >= interval)
        {
            timer = 0f;
            foreach (var p in spawnPoints)
            {
                if (p.gameObject.activeInHierarchy && !p.Blocked)
                {
                    Spawn(p);
                }
            }
        }
    }

    void OnDisable() => GetComponent<Animator>().StopPlayback();

    private void Spawn(SpawnPoint p)
    {
        var go = Instantiate(prefab, p.transform.position, Quaternion.identity);
        go.GetComponent<Enemy>().Init(p.Level);
    }
}
"""

FILL_BODY = """    {
        int n = 0;
        foreach (var x in xs)
        {
            if (x.GetHashCode() > 0)
            {
                while (n < 3) { n++; }
            }
        }
        return n;
    }
"""
PLAIN_POOL = ("public class BasePool { public int Size; }\n\npublic class Pool : BasePool\n{\n"
              "    public int Fill(int[] xs)\n" + FILL_BODY + "}\n")
MESSY_POOL_A = ('[System.Serializable, Category(new[] { "a", "b" })]\n'
                "public partial class Pool<T> : BasePool<T> where T : class, new()\n{\n"
                '    [Tooltip("x"), Range(0, 10)]\n    [Obsolete("use FillFast", false)]\n'
                "    public int Fill<TItem>(TItem[] xs) where TItem : struct\n" + FILL_BODY + "}\n")
MESSY_POOL_B = "public partial class Pool<T>\n{\n    private int extra;\n}\n"
GENERIC_BASE = "public class BasePool<T> { public int Size; }\n"

PREPROCESSOR = """public class Build
{
    public int Pick(int a)
    {
#if UNITY_EDITOR
        if (a > 0)
        {
            if (a > 1) { a++; }
        }
#else
        if (a > 2) { a--; }
#endif
        return a;
    }
}
"""

RAW_STRING = '''public class Text
{
    public string Show(int a)
    {
        var s = """
            {
            """;
        if (a > 0) { if (a > 1) { a++; } }
        return s;
    }
}
'''

CUT = """public class Cut
{
    public void A(int a)
    {
#if X
        if (a > 0) {
#else
        if (a > 1) {
#endif
            a++;
        }
    }
}
"""

SHAPES = '''public class Shapes : pb::IMessage
{
    private string name;
    public Shapes(string n, int t) : this(n, (float)t * 1000, null) { }
    public Shapes(string n, float t, object o) { name = n; }
    pbr::MessageDescriptor pb::IMessage.Descriptor { get { return null; } }
    private static Label MiniLabel(string text) =>
        new Label(text) { style = { color = 1 } };
    public string Quote(string v) { return $"\\"{v.Replace("\\"", "\\"\\"")}\\""; }
    public string Path() { return @"""" + name + @""""; }
#if UNITY_EDITOR
    public void EditorOnly() { if (name != null) { name = ""; } }
#endif
    public void After() { }
}
'''

LAYERS2 = """public class Body
{
    protected int hp;
    public virtual void Hit(int d) { hp -= d; }
    public void Heal(int n) { hp += n; }
    public Body(int start) { hp = start; }
}

public class Invulnerable : Body
{
    public Invulnerable(int start) : base(start) { }
    public override void Hit(int d) { }
}

public class Scaled : Body
{
    public Scaled(int start) : base(start * 10) { }
}

public class Overloaded : Body
{
    public Overloaded(int start) : base(start) { }
    public void Heal(int n, string why) { hp += n; }
}

public abstract class Shape
{
    public virtual double Area() { return 0; }
}

public class Circle : Shape
{
    double r;
    public override double Area() { return 3.14 * r * r; }
}

public class Board
{
    private Shape shape;
    private Inner inner;
    public double Total() => shape.Area();
    public void Go() => inner.Step();
}

public class Inner
{
    public void Step() => helper.Run();
    public void Run() { var a = 1; }
    public string Show(bool a, bool b) { return $\"\"\"{(a && b ? 1 : 2)}\"\"\"; }
}
"""

EQ_PY = """def f(a):
    if a:
        for x in a:
            if x:
                while x:
                    x -= 1
    if a:
        if a:
            pass
    return a


def e(a):
    if a == 1:
        return 1
    elif a == 2:
        return 2
    else:
        return 3


def t(a):
    try:
        with a:
            if a:
                pass
    except ValueError:
        pass
    return a
"""

EQ_CS = """public class Eq
{
    public int F(int[] a)
    {
        if (a != null)
        {
            foreach (var x in a)
            {
                if (x > 0)
                {
                    while (x > 0) { Step(); }
                }
            }
        }
        if (a != null)
        {
            if (a.Length > 0) { }
        }
        return 0;
    }

    public int E(int a)
    {
        if (a == 1)
            return 1;
        else if (a == 2)
            return 2;
        else
            return 3;
    }

    public int T(int a)
    {
        try
        {
            using (var s = Open())
            {
                if (a > 0) { a++; }
            }
        }
        catch (System.Exception)
        {
        }
        return a;
    }
}
"""

TOP_LEVEL = """using System;

Console.WriteLine("hi");
if (args.Length > 0) { Console.WriteLine(args[0]); }

public class Tool
{
    public void Go() { }
}
"""


def _write(root: Path, name: str, text: str) -> str:
    root.mkdir(parents=True, exist_ok=True)
    p = root / name
    p.write_text(text, encoding="utf-8", newline="\n")
    return str(p)


def _rows(root: Path, files: dict, resolve: dict | None = None, ranges=None):
    listed = [_write(root, n, t) for n, t in files.items()]
    extra = [_write(root, n, t) for n, t in (resolve or {}).items()]
    return tmc.metrics_for_files(listed, ranges, extra)


def _by(rows, kind):
    return {r["name"]: r for r in rows if r["kind"] == kind}


# ─── 繼承鏈：每層新增／覆寫、空層（只呼叫 base、空本體的覆寫） ─────────────────────────

def test_inherit_four_layers_two_hollow_layers_are_empty(tmp_path):
    cls = _by(_rows(tmp_path, {"Units.cs": INHERIT}), "class")
    cap = cls["Captain"]
    assert [l["name"] for l in cap["layers"]] == ["Captain", "Guard", "Soldier", "Unit"]
    assert cap["depth"] == 4 and cap["empty_layers"] == 2 and cap["unresolved_base"] is None
    me, guard, soldier, unit = cap["layers"]
    assert me["added"] == ["Shout"] and me["overridden"] == ["Tick"] and not me["empty"], "Tick 有 base 之外的事 → 不算空"
    assert guard["empty"] and guard["overridden"] == ["Hit"] and set(guard["hollow"]) == {"Hit"}
    assert "空本體" in guard["hollow"]["Hit"] and "抽象" in guard["hollow"]["Hit"], guard["hollow"]
    assert soldier["empty"] and set(soldier["hollow"]) == {"Tick"} and "上層同名" in soldier["hollow"]["Tick"]
    assert unit["added"] == ["hp", "Tick", "Hit"] and not unit["empty"]


def test_override_that_does_more_than_base_or_changes_args_is_not_hollow(tmp_path):
    cls = _by(_rows(tmp_path, {"Units.cs": INHERIT}), "class")
    heavy, armored = cls["Heavy"], cls["Armored"]
    assert not heavy["layers"][0]["empty"] and heavy["layers"][0]["hollow"] == {}, "base.Tick(); hp++; 有真正作用"
    assert heavy["empty_layers"] == 2, "上面 Guard、Soldier 兩層照樣是空層"
    assert not armored["layers"][0]["empty"] and armored["layers"][0]["hollow"] == {}, "base.Hit(damage / 2) 改了引數"
    assert cls["Unit"]["implementations"] == ["Armored", "Captain", "Guard", "Heavy"], "實作經由父類別也算；abstract 的 Soldier 不算"
    assert cls["Soldier"]["implementations"] == ["Armored", "Captain", "Guard", "Heavy"]


def test_hollow_members_that_change_behavior_do_not_make_an_empty_layer(tmp_path):
    """空覆寫擋掉上層有本體的實作（無敵）、建構子串接時引數有加工（乘 10）都是有作用的層；同名但參數個數不同是新增的多載。"""
    cls = _by(_rows(tmp_path, {"Body.cs": LAYERS2}), "class")
    inv = cls["Invulnerable"]["layers"][0]
    assert not inv["empty"] and cls["Invulnerable"]["empty_layers"] == 0, inv
    assert "擋掉上層的實作" in inv["hollow"]["Hit"] and "base" in inv["hollow"][".ctor"], "照列擋掉什麼，交給 LLM 判"
    scaled = cls["Scaled"]["layers"][0]
    assert not scaled["empty"] and scaled["hollow"] == {}, "base(start * 10) 有加工"
    ov = cls["Overloaded"]["layers"][0]
    assert ov["added"] == ["Heal"] and ov["overridden"] == [".ctor"], ov


# ─── 只轉手與連續轉手鏈 ─────────────────────────────────────────────────────────

def test_handoff_records_callee_and_chain_across_classes(tmp_path):
    fn = _by(_rows(tmp_path, {"Facade.cs": HANDOFF}), "func")
    assert fn["Facade.Fire"]["handoff"] == "Run" and fn["Facade.Fire"]["handoff_chain"] == 3, "Fire → Run → Step → Service.Exec"
    assert fn["Facade.Run"]["handoff"] == "Step" and fn["Facade.Run"]["handoff_chain"] == 2
    assert fn["Facade.Step"]["handoff"] == "service.Exec" and fn["Facade.Step"]["handoff_chain"] == 1
    assert fn["Service.Exec"]["handoff"] is None and fn["Service.Exec"]["handoff_chain"] == 0


def test_single_statement_that_is_not_a_bare_call_is_not_handoff(tmp_path):
    fn = _by(_rows(tmp_path, {"Facade.cs": HANDOFF}), "func")
    assert fn["Facade.Score"]["handoff"] is None, "讀屬性再加：有運算"
    assert fn["Facade.Twice"]["handoff"] is None, "呼叫後再乘 2：有運算"
    assert fn["Facade.Label"]["handoff"] is None, "插值字串 $\"{Step(x)} pts\" 有接字串，不是只轉手"
    assert fn["Facade.Note"]["handoff"] == "Log" and fn["Facade.Note"]["handoff_chain"] == 1, "字串在引數裡照算轉手"


# ─── 介面＋單一實作：分派多繞一手 ──────────────────────────────────────────────────

def test_interface_with_single_impl_marks_dispatch_and_counts_one_more_hop(tmp_path):
    rows = _rows(tmp_path, {"Store.cs": DISPATCH})
    fn, cls = _by(rows, "func"), _by(rows, "class")
    save = fn["Saver.Save"]
    assert save["handoff"] == "store.Save" and save["dispatch"] == [{"via": "IStore.Save", "impl": "FileStore.Save"}]
    assert save["handoff_chain"] == 2, "Saver.Save 轉手 1 ＋ 經過只有一個實作的介面 1"
    via = fn["Saver.SaveVia"]
    assert via["handoff"] == "other.Save" and via["dispatch"] and via["handoff_chain"] == 2, "參數型別是介面也算"
    assert cls["IStore"]["type_kind"] == "interface" and cls["IStore"]["implementations"] == ["FileStore"]
    impl = cls["FileStore"]
    assert [l["name"] for l in impl["layers"]] == ["FileStore", "IStore"] and impl["interfaces"] == {"IStore": ["FileStore"]}
    assert impl["layers"][0]["overridden"] == ["Count", "Save"] and impl["layers"][0]["added"] == ["Write"]
    assert fn["Saver..ctor"]["handoff"] is None, "建構子存欄位不是轉手"


def test_abstract_base_with_body_and_single_override_is_dispatch(tmp_path):
    fn = _by(_rows(tmp_path, {"Body.cs": LAYERS2}), "func")
    total = fn["Board.Total"]
    assert total["dispatch"] == [{"via": "Shape.Area", "impl": "Circle.Area"}] and total["handoff_chain"] == 2, total


def test_stuck_hop_later_in_the_chain_is_noted_on_the_start(tmp_path):
    fn = _by(_rows(tmp_path, {"Body.cs": LAYERS2}), "func")
    assert any(u.startswith("轉手對象 helper 的型別看不出來") for u in fn["Inner.Step"]["unparsed"]), fn["Inner.Step"]
    go = fn["Board.Go"]
    assert go["handoff_chain"] == 2 and go["confidence"] == "partial" and any("Inner.Step 那一手" in u for u in go["unparsed"]), go


def test_raw_interpolated_holes_and_unreadable_lookup_files_are_listed(tmp_path):
    (tmp_path / "Gone.cs").mkdir()
    rows = _rows(tmp_path, {"Body.cs": LAYERS2}, ranges=None)
    show = _by(rows, "func")["Inner.Show"]
    assert show["confidence"] == "partial" and any("原始插值字串" in u for u in show["unparsed"]), show
    rows = tmc.metrics_for_files([str(tmp_path / "Body.cs")], {str(tmp_path / "Body.cs"): [(1, 1)]}, [str(tmp_path / "Gone.cs")])
    lost = [r for r in rows if r["kind"] == "unparsed"]
    assert lost and "查找用的 1 個檔讀不了" in lost[0]["unparsed"][0], rows


def test_same_shape_in_python_and_csharp_gives_same_numbers(tmp_path):
    import turn_metrics as tm
    py = {f["name"]: f for f in tm.function_metrics(EQ_PY, "eq.py")[0]}
    cs = _by(_rows(tmp_path, {"Eq.cs": EQ_CS}), "func")
    for p, c in (("f", "Eq.F"), ("e", "Eq.E"), ("t", "Eq.T")):
        want = tuple(py[p][k] for k in ("nesting", "bumpy", "cognitive"))
        assert tuple(cs[c][k] for k in ("nesting", "bumpy", "cognitive")) == want, (p, want, cs[c])


def test_cut_lookup_pool_does_not_claim_a_single_implementation(tmp_path):
    """查找池是從更多檔裡挑出來的：池裡只看到一個實作不代表只有一個，不算分派、註明原因，介面的實作數標成下限。"""
    p = _write(tmp_path, "Store.cs", DISPATCH)
    rows = tmc.metrics_for_files([p], None, [], partial_pool=True)
    fn, cls = _by(rows, "func"), _by(rows, "class")
    save = fn["Saver.Save"]
    assert save["dispatch"] == [] and save["handoff_chain"] == 1 and any("沒算分派" in u for u in save["unparsed"]), save
    assert any("下限" in u for u in cls["IStore"]["unparsed"]) and cls["IStore"]["confidence"] == "partial"


def test_interface_with_two_impls_is_not_dispatch(tmp_path):
    rows = _rows(tmp_path, {"Store.cs": DISPATCH, "Memory.cs": SECOND_IMPL})
    fn, cls = _by(rows, "func"), _by(rows, "class")
    assert fn["Saver.Save"]["dispatch"] == [] and fn["Saver.Save"]["handoff_chain"] == 1
    assert cls["IStore"]["implementations"] == ["FileStore", "MemoryStore"]


# ─── 巢狀、條件塊、認知複雜度 ───────────────────────────────────────────────────

def test_nested_if_foreach_depth_three_with_else_if_and_braceless_bodies(tmp_path):
    fn = _by(_rows(tmp_path, {"Grid.cs": NESTED}), "func")
    walk = fn["Grid.Walk"]
    assert (walk["nesting"], walk["bumpy"], walk["cognitive"]) == (3, 1, 8), walk
    assert walk["length"] == 18 and walk["handoff"] is None and walk["confidence"] == "full", "初始化子的大括號不算區塊"


def test_switch_try_catch_lambda_bool_sequences_and_ternary(tmp_path):
    fn = _by(_rows(tmp_path, {"Grid.cs": NESTED}), "func")
    m = fn["Grid.Mixed"]
    assert m["nesting"] == 3 and m["bumpy"] == 2, m
    assert m["cognitive"] == 11, "switch 1＋catch 2＋if 3＋lambda 裡的 if 2＋&&／|| 2＋三元 1"
    flat = fn["Grid.Flat"]
    assert (flat["nesting"], flat["bumpy"], flat["cognitive"]) == (0, 0, 0)


def test_unity_monobehaviour_awake_update_and_getcomponent_chain(tmp_path):
    rows = _rows(tmp_path, {"EnemySpawner.cs": UNITY})
    fn, cls = _by(rows, "func"), _by(rows, "class")
    up = fn["EnemySpawner.Update"]
    assert (up["nesting"], up["bumpy"], up["cognitive"]) == (3, 1, 7), up
    aw = fn["EnemySpawner.Awake"]
    assert (aw["nesting"], aw["cognitive"], aw["handoff"]) == (1, 1, None)
    assert fn["EnemySpawner.OnDisable"]["handoff"] == "StopPlayback" and fn["EnemySpawner.OnDisable"]["handoff_chain"] == 1
    assert fn["EnemySpawner.Spawn"]["handoff"] is None
    sp = cls["EnemySpawner"]
    assert sp["depth"] == 1 and sp["unresolved_base"] == "MonoBehaviour"
    assert sp["layers"][0]["added"] == ["prefab", "interval", "spawnPoints", "body", "timer", "Awake", "Update", "OnDisable", "Spawn"]
    assert all(r["confidence"] == "full" for r in rows), [r for r in rows if r["confidence"] != "full"]


def test_row_fields_match_python_turn_metrics(tmp_path):
    rows = _rows(tmp_path, {"Grid.cs": NESTED, "Units.cs": INHERIT})
    func = next(r for r in rows if r["kind"] == "func")
    cls = next(r for r in rows if r["kind"] == "class")
    assert {"file", "name", "lineno", "end_lineno", "length", "nesting", "bumpy", "cognitive", "handoff", "handoff_chain",
            "unparsed", "confidence"} <= set(func)
    assert {"file", "name", "lineno", "end_lineno", "depth", "empty_layers", "unresolved_base", "layers",
            "unparsed", "confidence"} <= set(cls)
    assert {"name", "file", "added", "overridden", "empty"} <= set(cls["layers"][0])


# ─── 解析不到：照實列、數字不變小 ───────────────────────────────────────────────

def test_partial_generic_and_braced_attributes_keep_numbers_and_list_partial(tmp_path):
    plain = _by(_rows(tmp_path / "plain", {"Pool.cs": PLAIN_POOL}), "func")
    rows = _rows(tmp_path / "messy", {"Pool.Fill.cs": MESSY_POOL_A, "Pool.State.cs": MESSY_POOL_B}, {"BasePool.cs": GENERIC_BASE})
    fn = _by(rows, "func")
    want = {k: plain["Pool.Fill"][k] for k in ("nesting", "bumpy", "cognitive")}
    assert want == {"nesting": 3, "bumpy": 1, "cognitive": 6}
    assert {k: fn["Pool.Fill"][k] for k in want} == want, "泛型、帶大括號的 attribute 不讓數字變小"
    assert fn["Pool.Fill"]["unparsed"] == [] and fn["Pool.Fill"]["confidence"] == "full", "解析得到就不列"
    pool = [r for r in rows if r["kind"] == "class" and r["name"] == "Pool"]
    assert len(pool) == 2 and all(r["depth"] == 2 and r["layers"][1]["name"] == "BasePool" for r in pool)
    assert pool[0]["layers"][0]["added"] == ["Fill", "extra"], "兩個分檔的成員併在一起"
    assert all(r["confidence"] == "partial" and any("partial" in u for u in r["unparsed"]) for r in pool), pool[0]["unparsed"]
    assert sorted(fn) == ["Pool.Fill"], "attribute 裡的大括號不切出假成員"


def test_preprocessor_branches_both_counted_and_listed(tmp_path):
    pick = _by(_rows(tmp_path, {"Build.cs": PREPROCESSOR}), "func")["Build.Pick"]
    assert pick["nesting"] == 2 and pick["cognitive"] >= 3, "不小於編輯器那支單獨的數字"
    assert pick["confidence"] == "partial" and any("#if" in u for u in pick["unparsed"]), pick["unparsed"]


def test_raw_string_parses_and_unbalanced_braces_are_listed_not_shrunk(tmp_path):
    show = _by(_rows(tmp_path / "raw", {"Text.cs": RAW_STRING}), "func")["Text.Show"]
    assert (show["nesting"], show["cognitive"], show["confidence"]) == (2, 3, "full"), show
    rows = _rows(tmp_path / "cut", {"Cut.cs": CUT})
    a = _by(rows, "func")["Cut.A"]
    assert a["nesting"] >= 1 and a["confidence"] == "partial" and any("#else" in u for u in a["unparsed"]), a
    files = [r for r in rows if r["kind"] == "unparsed"]
    assert files and any("大括號不成對" in u for u in files[0]["unparsed"]), files


def test_real_world_shapes_parse_without_unparsed(tmp_path):
    """真打 sgi_client 時讀錯的幾種寫法：建構子串接括號裡還有括號、pb:: 別名的介面屬性、箭頭本體帶初始化子、
    插值洞裡有跳脫引號的字串、@"" 跳脫、只有 #if 沒有 #else。"""
    rows = _rows(tmp_path, {"Shapes.cs": SHAPES})
    fn, cls = _by(rows, "func"), _by(rows, "class")
    assert sorted(fn) == ["Shapes..ctor(string,float,object)", "Shapes..ctor(string,int)", "Shapes.After",
                          "Shapes.Descriptor.get", "Shapes.EditorOnly", "Shapes.MiniLabel", "Shapes.Path", "Shapes.Quote"], sorted(fn)
    assert all(r["confidence"] == "full" for r in rows), [(r["name"], r["unparsed"]) for r in rows if r["confidence"] != "full"]
    assert fn["Shapes.Quote"]["handoff"] is None and fn["Shapes.MiniLabel"]["handoff"] is None
    assert fn["Shapes.EditorOnly"]["nesting"] == 1
    sh = cls["Shapes"]
    assert sh["layers"][0]["added"] == ["name", ".ctor", "Descriptor", "MiniLabel", "Quote", "Path", "EditorOnly", "After"]
    assert sh["unresolved_base"] == "IMessage"


def test_top_level_statements_outside_types_are_listed(tmp_path):
    rows = _rows(tmp_path, {"Program.cs": TOP_LEVEL})
    files = [r for r in rows if r["kind"] == "unparsed"]
    assert files and any("不在任何型別裡" in u for u in files[0]["unparsed"]), files
    assert any("第 3 行" in u for u in files[0]["unparsed"]), files[0]["unparsed"]
    assert _by(rows, "func")["Tool.Go"]["confidence"] == "full", "沒算到的程式只標在檔案那一行；Tool.Go 自己完整解析到"


# ─── 範圍、非 C#、CLI ─────────────────────────────────────────────────────────

def test_ranges_pick_only_hit_rows_and_non_cs_is_unsupported(tmp_path):
    p = _write(tmp_path, "Grid.cs", NESTED)
    rows = tmc.metrics_for_files([p], {p: [(6, 6)]})
    assert [(r["kind"], r["name"]) for r in rows] == [("func", "Grid.Walk"), ("class", "Grid")], "第 6 行在 Walk 裡、也在 Grid 裡"
    rows = tmc.metrics_for_files([p], {p: [(21, 21)]})
    assert [(r["kind"], r["name"]) for r in rows] == [("class", "Grid")], "方法之間的空行只命中類別"
    assert tmc.metrics_for_files([p], {}) == []
    py = _write(tmp_path, "x.py", "def f():\n    return 1\n")
    assert tmc.metrics_for_files([py]) == [{"kind": "unsupported", "file": py, "lang": "不支援"}]
    missing = str(tmp_path / "Gone.cs")
    assert [r["kind"] for r in tmc.metrics_for_files([missing])] == ["error"]


def test_cli_prints_rows_and_done_tail(tmp_path):
    p = _write(tmp_path, "Units.cs", INHERIT)
    out = subprocess.run([sys.executable, "-X", "utf8", str(LIB / "turn_metrics_cs.py"), p],
                         capture_output=True, text=True, encoding="utf-8")
    lines = out.stdout.strip().splitlines()
    assert out.returncode == 0 and lines[-1] == "TURN_METRICS_CS DONE funcs=7 classes=6 partial=0 unparsed_files=0", out.stdout[-400:]
    assert lines[0].startswith('{"kind": "func"')
