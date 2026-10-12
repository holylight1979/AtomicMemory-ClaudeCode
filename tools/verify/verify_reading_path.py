"""verify_reading_path.py：閱讀路徑掃描器 tools/reading-path.py（＋ reading_path_lang.py）。

正例：入口→三層包裝→落地 數出跳檔／轉手／拐彎；Python 與 C# 各一組 callback／事件／繼承分派被認成轉手；
      partial 檔名有責任軸 → 標「分檔有責任軸」不算彎；前後比較（兩個目錄、git rev）差異正確；尾行哨兵。
反例：拿掉包裝的直線版數字較小；無責任軸的 partial 照算跳檔；同版本比較全部不變；
      反證：一次拿掉一種轉手偵測（callback／event／inherit／dynamic／責任軸），對應案例就紅；
      不確定的連線必須標候選、不該存在的邊不存在、看不到的不能被比較成變好。
假專案都在 tmp 現建。怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider tools/verify/verify_reading_path.py
"""
from __future__ import annotations

import codecs
import importlib.util
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "reading-path.py"


def _load():
    spec = importlib.util.spec_from_file_location("reading_path", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["reading_path"] = mod
    spec.loader.exec_module(mod)
    return mod


rp = _load()


def _write(root: Path, files: dict) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    return root


def _route(report: dict, landing: str) -> dict:
    hits = [r for r in itertools.chain.from_iterable(e["routes"] for e in report["entries"]) if r["landing"] == landing]
    assert hits, f"沒有走到 {landing}"
    return hits[0]


def _kinds(route: dict) -> list:
    return [s["kind"] for s in route["steps"][1:]]


# ─── 假專案 ──────────────────────────────────────────────────────────────────

PY_CORE = "def work(n):\n    total = 0\n    for i in range(n):\n        total += i\n    return total\n"
PY_WRAPPED = {
    "app.py": 'import w1\n\nif __name__ == "__main__":\n    w1.start(3)\n',
    "w1.py": "import w2\n\n\ndef start(n):\n    return w2.relay(n)\n",
    "w2.py": "from w3 import pass_on\n\n\ndef relay(n):\n    return pass_on(n)\n",
    "w3.py": "from core import work\n\n\ndef pass_on(n):\n    return work(n)\n",
    "core.py": PY_CORE,
}
PY_STRAIGHT = {
    "app.py": 'from core import work\n\nif __name__ == "__main__":\n    work(3)\n',
    "core.py": PY_CORE,
}

PY_KINDS = {
    "main.py": '''from bus import Bus
from shapes import Circle
import jobs


def on_item(i):
    total = i * 2
    total += 1
    return total


def on_saved(key):
    print("saved", key)
    label = key.upper()
    return label


def on_table(x):
    y = x + 1
    y *= 2
    return y


HANDLERS = {"x": on_table}

if __name__ == "__main__":
    jobs.schedule(on_item)
    bus = Bus()
    bus.on("saved", on_saved)
    bus.emit("saved", "k1")
    shape = Circle()
    shape.render()
    HANDLERS["x"](1)
''',
    "jobs.py": "def schedule(cb):\n    items = [1, 2, 3]\n    for i in items:\n        cb(i)\n",
    "bus.py": '''class Bus:
    def __init__(self):
        self.handlers = {}

    def on(self, key, fn):
        self.handlers.setdefault(key, []).append(fn)

    def emit(self, key, *args):
        for fn in self.handlers.get(key, []):
            fn(*args)
''',
    "shapes.py": '''class Shape:
    def render(self):
        for _ in range(2):
            self.draw()

    def draw(self):
        raise NotImplementedError


class Circle(Shape):
    def draw(self):
        r = 3
        return 3.14 * r * r
''',
}

CS_CORE = """static class Core {
    public static int Work(int n) {
        int total = 0;
        for (int i = 0; i < n; i++) total += i;
        return total;
    }
}
"""
CS_WRAPPED = {
    "Program.cs": "class Program {\n    static void Main() {\n        var api = new Api();\n        api.Start(3);\n    }\n}\n",
    "Api.cs": "class Api {\n    private readonly Relay _relay = new Relay();\n    public void Start(int n) => _relay.Pass(n);\n}\n",
    "Relay.cs": "class Relay {\n    private Hop _hop = new Hop();\n    public void Pass(int n) { _hop.Forward(n); }\n}\n",
    "Hop.cs": "class Hop {\n    // 只轉給靜態類別\n    public void Forward(int n) { Core.Work(n); }\n}\n",
    "Core.cs": CS_CORE,
}
CS_STRAIGHT = {
    "Program.cs": "class Program {\n    static void Main() {\n        Core.Work(3);\n    }\n}\n",
    "Core.cs": CS_CORE,
}

CS_KINDS = {
    "Program.cs": """using System;
class Program {
    static void Main() {
        var jobs = new Jobs();
        jobs.Schedule(OnItem);
        var game = new Game();
        game.Saved += OnSaved;
        game.Save();
        var shape = new Circle();
        shape.Render();
    }
    static void OnItem(int i) {
        int x = i * 2;
        x += 1;
        x *= 3;
        Console.WriteLine("item {0}", x);
    }
    static void OnSaved() {
        int a = 1;
        a += 2;
        a *= 3;
    }
}
""",
    "Jobs.cs": """using System;
class Jobs {
    public void Schedule(Action<int> cb) {
        for (int i = 0; i < 3; i++) {
            cb(i);
        }
    }
}
""",
    "Game.cs": """using System;
class Game {
    public event Action Saved;
    private int _count;
    public void Save() {
        _count++;
        if (_count > 0) {
            Saved?.Invoke();
        }
    }
}
""",
    "Shapes.cs": """abstract class Shape {
    public void Render() {
        for (int i = 0; i < 2; i++) {
            Draw();
        }
    }
    protected abstract void Draw();
}
class Circle : Shape {
    protected override void Draw() {
        int r = 3;
        r *= r;
        r += 1;
    }
}
""",
}

CS_GAME_MAIN = "class Game {\n    static void Main() {\n        var p = new Player();\n        p.Fire();\n    }\n}\n"
CS_PART_API = ("public partial class Player {\n    public void Fire() {\n        int ammo = 3;\n        ammo -= 1;\n"
               "        ammo *= 2;\n        Apply(ammo);\n    }\n}\n")
CS_PART_CORE = """public partial class Player {
    private int _hp = 10;
    void Apply(int a) {
        if (a > 0) {
            Resolve(a);
        }
    }
    void Commit(int a) {
        _hp -= a;
        _hp += 1;
        _hp *= 2;
    }
}
"""
CS_PART_LOGIC = "public partial class Player {\n    void Resolve(int a) {\n        _hp -= a;\n        if (_hp < 0) _hp = 0;\n        Commit(a);\n    }\n}\n"
CS_PARTIAL_AXIS = {"Game.cs": CS_GAME_MAIN, "Player.PublicApi.cs": CS_PART_API,
                   "Player.Core.cs": CS_PART_CORE, "Player.GameLogic.cs": CS_PART_LOGIC}
CS_PARTIAL_NO_AXIS = {"Game.cs": CS_GAME_MAIN, "Player.cs": CS_PART_API,
                      "PlayerMore.cs": CS_PART_CORE, "PlayerExtra.cs": CS_PART_LOGIC}


# ─── 入口 → 三層包裝 → 落地（正）／直線版（反） ───────────────────────────────

def test_python_three_wrappers_counted_and_straight_is_smaller(tmp_path):
    wrapped = rp.analyze(_write(tmp_path / "wrapped", PY_WRAPPED), "app.py")
    r = _route(wrapped, "core.py::work")
    assert [s["func"] for s in r["steps"]] == ["app.py::<main>", "w1.py::start", "w2.py::relay", "w3.py::pass_on", "core.py::work"]
    assert _kinds(r) == ["wrapper", "wrapper", "wrapper", "direct"]
    assert (r["turns"], r["file_jumps"], r["handoffs"], r["depth"], r["grade"]) == (4, 4, 3, 4, "臭掉")
    assert wrapped["entries"][0]["landings"] == 1, "包裝層只轉傳，不是落點"

    straight = rp.analyze(_write(tmp_path / "straight", PY_STRAIGHT), "app.py")
    s = _route(straight, "core.py::work")
    assert (s["turns"], s["file_jumps"], s["handoffs"], s["grade"]) == (1, 1, 0, "順")
    assert s["turns"] < r["turns"] and s["file_jumps"] < r["file_jumps"] and s["handoffs"] < r["handoffs"]


def test_csharp_three_wrappers_counted_and_straight_is_smaller(tmp_path):
    wrapped = rp.analyze(_write(tmp_path / "wrapped", CS_WRAPPED))
    r = _route(wrapped, "Core.cs::Core.Work")
    assert r["entry"] == "Program.cs::Program.Main"
    assert [s["func"] for s in r["steps"][1:]] == ["Api.cs::Api.Start", "Relay.cs::Relay.Pass",
                                                  "Hop.cs::Hop.Forward", "Core.cs::Core.Work"]
    assert _kinds(r) == ["delegate", "delegate", "wrapper", "direct"], "經欄位物件轉交＝委派，經靜態類別＝包裝"
    assert (r["turns"], r["file_jumps"], r["handoffs"], r["grade"]) == (4, 4, 3, "臭掉")

    straight = rp.analyze(_write(tmp_path / "straight", CS_STRAIGHT))
    s = _route(straight, "Core.cs::Core.Work")
    assert (s["turns"], s["file_jumps"], s["handoffs"], s["grade"]) == (1, 1, 0, "順")


# ─── callback／事件／繼承分派／分派表 被認成轉手（正）＋反證 ────────────────

def _check_last_step(report: dict, landing: str, kind: str) -> None:
    r = _route(report, landing)
    assert _kinds(r)[-1] == kind, f"{landing} 最後一步應是 {kind}，實得 {_kinds(r)}"
    assert r["handoffs"] >= 1 and r["turns"] >= 1


PY_CASES = {"callback": ("main.py::on_item", "callback"), "event": ("main.py::on_saved", "event"),
            "inherit": ("shapes.py::Circle.draw", "inherit"), "dynamic": ("main.py::on_table", "dynamic")}
CS_CASES = {"callback": ("Program.cs::Program.OnItem", "callback"), "event": ("Program.cs::Program.OnSaved", "event"),
            "inherit": ("Shapes.cs::Circle.Draw", "inherit")}
DETECTORS = {"callback": "callback_targets", "event": "event_targets", "inherit": "override_targets"}


@pytest.mark.parametrize("case", sorted(PY_CASES))
def test_python_handoff_kinds_recognized(tmp_path, case):
    report = rp.analyze(_write(tmp_path, PY_KINDS), "main.py")
    _check_last_step(report, *PY_CASES[case])


@pytest.mark.parametrize("case", sorted(CS_CASES))
def test_csharp_handoff_kinds_recognized(tmp_path, case):
    report = rp.analyze(_write(tmp_path, CS_KINDS), "Program.cs")
    _check_last_step(report, *CS_CASES[case])


@pytest.mark.parametrize("case", sorted(DETECTORS))
def test_counter_proof_removing_one_detector_turns_its_case_red(tmp_path, monkeypatch, case):
    monkeypatch.setattr(rp, DETECTORS[case], lambda *a, **k: [])
    py = rp.analyze(_write(tmp_path / "py", PY_KINDS), "main.py")
    cs = rp.analyze(_write(tmp_path / "cs", CS_KINDS), "Program.cs")
    with pytest.raises(AssertionError):
        _check_last_step(py, *PY_CASES[case])
    with pytest.raises(AssertionError):
        _check_last_step(cs, *CS_CASES[case])
    others = [c for c in DETECTORS if c != case]
    for other in others:
        _check_last_step(py, *PY_CASES[other])


PY_LAZY = {
    "entry.py": '''import importlib

HANDLERS = {"a": ("handlers.alpha", "handle_alpha")}


def main(event):
    spec = HANDLERS.get(event)
    module = importlib.import_module(spec[0])
    getattr(module, spec[1])(event)


def poke(obj, name):
    getattr(obj, name)()
''',
    "handlers/alpha.py": "def handle_alpha(x):\n    y = [x]\n    y.append(x)\n    return y\n",
}


def test_python_lazy_import_table_is_dynamic_and_bare_getattr_is_ambiguous(tmp_path):
    report = rp.analyze(_write(tmp_path, PY_LAZY), "entry.py::main")
    _check_last_step(report, "handlers/alpha.py::handle_alpha", "dynamic")
    assert report["stats"]["unresolved"] == 1, "poke 的 getattr 沒有分派表可對 → 計入專案內解析不了，不亂連"


PY_LOCAL_TABLE = {
    "router.py": '''class Router:
    def route(self, kind):
        handler = {"a": self._on_a, "b": self._on_b}
        handler[kind]()

    def _on_a(self):
        x = 1
        x += 1
        return x

    def _on_b(self):
        y = 2
        y *= 2
        return y


if __name__ == "__main__":
    Router().route("a")
''',
}


def test_python_dispatch_table_inside_method_is_dynamic(tmp_path):
    report = rp.analyze(_write(tmp_path, PY_LOCAL_TABLE), "router.py")
    _check_last_step(report, "router.py::Router._on_a", "dynamic")
    _check_last_step(report, "router.py::Router._on_b", "dynamic")


def test_counter_proof_removing_table_dispatch_turns_dynamic_red(tmp_path, monkeypatch):
    monkeypatch.setattr(rp.Graph, "_dynamic", lambda self, *a, **k: [])
    report = rp.analyze(_write(tmp_path / "kinds", PY_KINDS), "main.py")
    with pytest.raises(AssertionError):
        _check_last_step(report, *PY_CASES["dynamic"])
    local = rp.analyze(_write(tmp_path / "local", PY_LOCAL_TABLE), "router.py")
    with pytest.raises(AssertionError):
        _check_last_step(local, "router.py::Router._on_a", "dynamic")


# ─── partial 責任軸（正）／無責任軸（反）／拿掉責任軸偵測（反證） ─────────────

def _check_axis(report: dict) -> None:
    r = _route(report, "Player.Core.cs::Player.Commit")
    axes = [s["axis"] for s in r["steps"][1:]]
    assert axes == ["", "PublicApi→Core", "Core→GameLogic", "GameLogic→Core"]
    assert (r["turns"], r["file_jumps"], r["axis_jumps"]) == (1, 1, 3)
    assert r["grade"] != "臭掉"
    assert report["stats"]["axis_classes"] == {"Player": ["Core", "GameLogic", "PublicApi"]}


def test_partial_with_responsibility_axis_is_marked_not_smelly(tmp_path):
    report = rp.analyze(_write(tmp_path, CS_PARTIAL_AXIS))
    _check_axis(report)
    assert "≋分檔有責任軸（依檔名推測）PublicApi→Core" in rp.render(report, 3)


def test_partial_without_axis_naming_counts_file_jumps(tmp_path):
    report = rp.analyze(_write(tmp_path, CS_PARTIAL_NO_AXIS))
    r = _route(report, "PlayerMore.cs::Player.Commit")
    assert all(not s["axis"] for s in r["steps"])
    assert (r["turns"], r["file_jumps"], r["grade"]) == (4, 4, "臭掉")


def test_partial_with_meaningless_suffixes_is_not_an_axis(tmp_path):
    files = {"Game.cs": CS_GAME_MAIN, "Player.Part1.cs": CS_PART_API,
             "Player.Part2.cs": CS_PART_CORE, "Player.Part3.cs": CS_PART_LOGIC}
    r = _route(rp.analyze(_write(tmp_path, files)), "Player.Part2.cs::Player.Commit")
    assert (r["axis_jumps"], r["turns"]) == (0, 4), "改個 Part1/2/3 檔名不能洗掉跳檔"


def test_counter_proof_removing_axis_detection_turns_partial_case_red(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "partial_axis", lambda cls: {})
    report = rp.analyze(_write(tmp_path, CS_PARTIAL_AXIS))
    with pytest.raises(AssertionError):
        _check_axis(report)


# ─── 前後比較 ────────────────────────────────────────────────────────────────

def _row(res: dict, landing: str) -> dict:
    return next(r for r in res["rows"] if r["landing"] == landing)


def test_compare_two_directories(tmp_path):
    old = _write(tmp_path / "old", PY_WRAPPED)
    new = _write(tmp_path / "new", PY_STRAIGHT)
    res = rp.run_compare(new, str(old), None, "app.py", None)
    row = _row(res, "core.py::work")
    assert row["status"] == "better" and row["entry"] == "app.py::<main>"
    assert (row["before"]["turns"], row["after"]["turns"]) == (4, 1)
    assert res["counts"]["better"] == 1 and res["counts"]["worse"] == 0
    assert (res["max_turns_before"], res["max_turns_after"]) == (4, 1)

    back = rp.run_compare(old, str(new), None, "app.py", None)
    assert _row(back, "core.py::work")["status"] == "worse" and back["counts"]["worse"] == 1
    assert "[變差]" in rp.render_compare(back, 3) and "wrapper" in rp.render_compare(back, 3)


def test_compare_same_version_reports_no_change(tmp_path):
    a = _write(tmp_path / "a", PY_KINDS)
    b = _write(tmp_path / "b", PY_KINDS)
    res = rp.run_compare(b, str(a), None, None, None)
    assert res["counts"]["same"] >= 4
    assert all(res["counts"][k] == 0 for k in ("better", "worse", "new", "gone"))


def test_compare_git_rev_against_working_tree(tmp_path):
    repo = _write(tmp_path / "repo", PY_WRAPPED)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "wrapped"], check=True)
    _write(repo, PY_STRAIGHT)
    res = rp.run_compare(repo, "HEAD", None, "app.py", None)
    assert _row(res, "core.py::work")["status"] == "better"
    with pytest.raises(rp.ReadingPathError):
        rp.run_compare(repo, "no-such-rev", None, "app.py", None)


def test_compare_flags_parse_regression_instead_of_calling_it_better(tmp_path):
    old = _write(tmp_path / "old", PY_WRAPPED)
    new = _write(tmp_path / "new", PY_WRAPPED)
    (new / "w3.py").write_text("def pass_on(n:\n", encoding="utf-8")
    res = rp.run_compare(new, str(old), None, "app.py", None)
    assert res["coverage_drop"] is True
    assert "⚠ after 的解析涵蓋變差" in rp.render_compare(res, 3) and "coverage_drop=1" in rp.compare_done_line(res)


# ─── codex 初審抓到的反例（修正後的回歸） ─────────────────────────────────────

PY_B_WORK = "static class B {\n    public static int Work(int n) {\n        int t = n;\n        for (int i = 0; i < n; i++) t += i;\n        return t;\n    }\n}\n"


def test_same_callee_called_twice_keeps_both_callbacks_marked_candidate(tmp_path):
    files = {"app.py": '''def run(cb):
    for i in range(2):
        cb(i)


def first(i):
    a = i + 1
    a *= 2
    return a


def second(i):
    b = i - 1
    b *= 3
    return b


if __name__ == "__main__":
    run(first)
    run(second)
'''}
    report = rp.analyze(_write(tmp_path, files), "app.py")
    for landing in ("app.py::first", "app.py::second"):
        r = _route(report, landing)
        assert _kinds(r)[-1] == "callback" and r["steps"][-1]["guess"].startswith("候選")


def test_events_are_never_certain_even_on_the_same_instance(tmp_path):
    files = dict(PY_KINDS)
    files["main.py"] = files["main.py"].replace('bus.on("saved", on_saved)',
                                                'bus.on("saved", on_saved)\n    bus.on("saved", on_item)')
    r = _route(rp.analyze(_write(tmp_path, files), "main.py"), "main.py::on_saved")
    assert r["steps"][-1]["kind"] == "event" and not r["certain"], "事件不在確定白名單：同一實例也只是候選"


def test_function_local_import_does_not_leak_to_other_functions(tmp_path):
    files = {
        "app.py": ('def main():\n    from b import work\n    return work(1)\n\n\n'
                   'def unused():\n    from c import work\n    return work(2)\n\n\n'
                   'if __name__ == "__main__":\n    main()\n'),
        "b.py": "from deep import work as deep_work\n\n\ndef work(n):\n    m = n + 1\n    m *= 2\n    return deep_work(m) + m\n",
        "c.py": "def work(n):\n    k = n * 3\n    k -= 1\n    return k\n",
        "deep.py": "def work(n):\n    z = n * n\n    z += 1\n    return z\n",
    }
    report = rp.analyze(_write(tmp_path, files), "app.py")
    landings = {r["landing"] for r in report["entries"][0]["routes"]}
    assert {"b.py::work", "deep.py::work"} <= landings and "c.py::work" not in landings


def test_nested_function_finds_sibling_in_enclosing_scope(tmp_path):
    files = {"app.py": ('def main():\n    def work(n):\n        t = n + 1\n        t *= 2\n        return t\n\n'
                        '    def relay(n):\n        return work(n)\n\n    return relay(1)\n\n\n'
                        'if __name__ == "__main__":\n    main()\n')}
    r = _route(rp.analyze(_write(tmp_path, files), "app.py"), "app.py::main.work")
    assert _kinds(r) == ["direct", "wrapper", "direct"]


def test_variable_shuffles_do_not_hide_wrappers(tmp_path):
    hop = "def {name}(n):\n    x = n\n    y = x\n    return {nxt}(y)\n\n\n"
    text = ("def end(n):\n    s = n * 2\n    s += 1\n    return s\n\n\n"
            + hop.format(name="c", nxt="end") + hop.format(name="b", nxt="c") + hop.format(name="a", nxt="b")
            + 'if __name__ == "__main__":\n    a(1)\n')
    r = _route(rp.analyze(_write(tmp_path, {"app.py": text}), "app.py"), "app.py::end")
    assert _kinds(r) == ["wrapper", "wrapper", "wrapper", "direct"] and r["turns"] == 3


def test_csharp_property_getter_is_followed(tmp_path):
    files = {
        "Program.cs": ("class Program {\n    static void Main() {\n        var h = new Holder();\n"
                       "        int v = h.Value;\n        System.Console.WriteLine(v);\n    }\n}\n"),
        "Holder.cs": "class Holder {\n    public int Value {\n        get { int a = B.Work(2); a += 1; return a; }\n    }\n}\n",
        "B.cs": PY_B_WORK,
    }
    report = rp.analyze(_write(tmp_path, files))
    assert _route(report, "Holder.cs::Holder.Value")["entry"] == "Program.cs::Program.Main"
    assert _kinds(_route(report, "B.cs::B.Work")) == ["direct", "direct"]


def test_csharp_interpolated_string_keeps_calls_inside_braces(tmp_path):
    files = {
        "Program.cs": ('class Program {\n    static void Main() {\n        Run();\n    }\n    static void Run() {\n'
                       '        var s = $"total {B.Work(3)} done";\n        var n = s.Length * 2;\n'
                       '        n += 1;\n        n *= 3;\n    }\n}\n'),
        "B.cs": PY_B_WORK,
    }
    _route(rp.analyze(_write(tmp_path, files)), "B.cs::B.Work")


def test_python_file_with_bom_is_parsed(tmp_path):
    root = _write(tmp_path, PY_STRAIGHT)
    (root / "core.py").write_bytes(b"\xef\xbb\xbf" + PY_CORE.encode("utf-8"))
    report = rp.analyze(root, "app.py")
    assert report["stats"]["parse_errors"] == []
    _route(report, "core.py::work")


CS_W_INT = "    void Work(int a) { a += 1; a *= 2; a -= 3; }\n"
CS_W_STR = '    void Work(string s) { s += "x"; s += "y"; s += "z"; }\n'
CS_W_TWO = "    void Work(int a, int b) { a += b; a *= 2; a -= 3; }\n"
CS_K_MAIN = "    static void Main() { var k = new K(); k.Work(1); }\n}\n"


def _k(*members) -> str:
    return "class K {\n" + "".join(members) + CS_K_MAIN


def _work_ids(text: str) -> list:
    return sorted(f.id for f in rp.lang.parse_csharp("K.cs", text).funcs if f.name == "Work")


def test_csharp_overload_ids_are_signatures_regardless_of_order_or_layout():
    expect = ["K.cs::K.Work(int)", "K.cs::K.Work(string)"]
    assert _work_ids(_k(CS_W_INT, CS_W_STR)) == _work_ids(_k(CS_W_STR, CS_W_INT)) == expect
    assert _work_ids("\n\n" + _k(CS_W_INT, CS_W_STR)) == expect
    assert _work_ids(_k(CS_W_INT, CS_W_TWO, CS_W_STR)) == ["K.cs::K.Work(int)", "K.cs::K.Work(int,int)", "K.cs::K.Work(string)"]
    assert _work_ids(_k(CS_W_INT)) == ["K.cs::K.Work"], "沒有多載維持裸名"


@pytest.mark.parametrize("after", [_k(CS_W_STR, CS_W_INT), _k(CS_W_INT, CS_W_TWO, CS_W_STR), _k(CS_W_INT)],
                         ids=["swap", "insert", "delete-to-one"])
def test_compare_matches_the_same_overload_after_reorder_insert_delete(tmp_path, after):
    old = _write(tmp_path / "old", {"K.cs": _k(CS_W_INT, CS_W_STR)})
    new = _write(tmp_path / "new", {"K.cs": after})
    res = rp.run_compare(new, str(old), None, None, None)
    row = next(r for r in res["rows"] if r["landing"].startswith("K.cs::K.Work") and (r["before"] or {}).get("sig") == "int")
    assert row["after"] is not None and row["after"]["sig"] == "int", "Work(int) 前後要對到同一個方法"
    assert row["status"] == "same"


# ─── 退件 003：看不到的不能被當成變好、不確定的要標候選、編碼不能靜默（修正後的回歸） ──

PY_HOP = {
    "main.py": 'import hop\n\nif __name__ == "__main__":\n    hop.a(1)\n',
    "hop.py": ("import end\n\n\ndef a(n):\n    return b(n)\n\n\ndef b(n):\n    return c(n)\n\n\n"
               "def c(n):\n    return end.done(n)\n"),
    "end.py": "def done(n):\n    t = n * 2\n    t += 1\n    return t\n",
}


def _hop_variant(body: str, extra: str = "") -> dict:
    return {**PY_HOP, "hop.py": PY_HOP["hop.py"].replace("    return b(n)", body, 1) + extra}


def test_function_alias_is_followed_and_compare_stays_same(tmp_path):
    b1 = _write(tmp_path / "b1", PY_HOP)
    b2 = _write(tmp_path / "b2", _hop_variant("    next_fn = b\n    return next_fn(n)"))
    r = _route(rp.analyze(b2, "main.py"), "end.py::done")
    assert _kinds(r) == ["wrapper", "wrapper", "wrapper", "direct"] and r["certain"] and not r["incomplete"]
    res = rp.run_compare(b2, str(b1), None, "main.py", None)
    assert _row(res, "end.py::done")["status"] == "same"
    assert res["coverage_drop"] is False and res["max_turns_before"] == res["max_turns_after"] == 4


def test_csharp_delegate_alias_is_followed(tmp_path):
    files = {"Program.cs": "using System;\nclass Program {\n    static void Main() {\n"
                           "        Func<int, int> next = Core.Work;\n        next(3);\n    }\n}\n", "Core.cs": CS_CORE}
    r = _route(rp.analyze(_write(tmp_path, files)), "Core.cs::Core.Work")
    assert r["certain"] and r["steps"][-1]["kind"] == "direct"


def test_unresolvable_call_is_incomplete_and_compare_is_undecidable_not_better(tmp_path):
    b1 = _write(tmp_path / "b1", PY_HOP)
    b3 = _write(tmp_path / "b3", _hop_variant("    next_fn = pick()\n    return next_fn(n)",
                                               "\n\ndef pick():\n    return b\n"))
    report = rp.analyze(b3, "main.py")
    a = _route(report, "hop.py::a")
    assert a["incomplete"] and a["unresolved"] == 1 and report["stats"]["unresolved"] == 1
    assert report["entries"][0]["grades"]["順"] == 1, "未讀到底的落點不算進刻度分布（只剩 pick）"
    assert "（未讀到底" in rp.render(report, 3) and "incomplete=1" in rp.done_line(report)
    res = rp.run_compare(b3, str(b1), None, "main.py", None)
    assert _row(res, "end.py::done")["status"] == "undecidable", "看不到了不能報成消失或變好"
    assert res["coverage_drop"] is True and res["counts"]["better"] == 0 and res["counts"]["gone"] == 0
    assert res["undecidable_entries"] == ["main.py::<main>"]
    assert "coverage_drop=1" in rp.compare_done_line(res) and "不可判定" in rp.render_compare(res, 3)


def test_event_on_a_different_instance_must_be_candidate(tmp_path):
    py = dict(PY_KINDS)
    py["main.py"] = py["main.py"].replace('bus.on("saved", on_saved)', 'other = Bus()\n    other.on("saved", on_saved)')
    r = _route(rp.analyze(_write(tmp_path / "py", py), "main.py"), "main.py::on_saved")
    assert r["steps"][-1]["kind"] == "event" and r["steps"][-1]["guess"].startswith("候選") and not r["certain"]
    cs = {"Program.cs": """using System;
class Bus {
    public event Action Fired;
    public void Fire() {
        int n = 1;
        n += 1;
        if (n > 0) { Fired?.Invoke(); }
    }
}
class Program {
    static void Main() {
        var a = new Bus();
        var b = new Bus();
        b.Fired += Handler;
        a.Fire();
    }
    static void Handler() {
        int x = 1;
        x += 2;
        x *= 3;
    }
}
"""}
    r = _route(rp.analyze(_write(tmp_path / "cs", cs)), "Program.cs::Program.Handler")
    assert r["steps"][-1]["kind"] == "event" and not r["certain"]


CS_INHERIT = """class Base {
    public virtual void Work() { int a = 1; a += 1; a *= 2; }
}
class Child : Base {
    public override void Work() { int b = 2; b += 1; b *= 3; }
}
class Program {
    static void Main() {
        var x = new Base();
        x.Work();
        Run(new Child());
    }
    static void Run(Base y) {
        y.Work();
        y.Work();
        y.Work();
    }
}
"""


def test_exact_new_type_has_no_override_edge_and_declared_type_is_candidate(tmp_path):
    root = _write(tmp_path, {"Program.cs": CS_INHERIT})
    g = rp.build_graph(root)
    assert [(e.dst, e.guess) for e in g.edges["Program.cs::Program.Main"] if "Work" in e.dst] == [("Program.cs::Base.Work", "")], \
        "明確 new Base() 後呼叫 Work：不該連到 Child.Work"
    run_edges = {e.dst: e for e in g.edges["Program.cs::Program.Run"]}
    assert set(run_edges) == {"Program.cs::Base.Work", "Program.cs::Child.Work"}
    assert all(e.kind == "inherit" and e.guess.startswith("候選") for e in run_edges.values())
    report = rp.analyze(root)
    assert _route(report, "Program.cs::Base.Work")["certain"] and not _route(report, "Program.cs::Child.Work")["certain"]


def test_reassigned_locals_lose_alias_exact_type_and_same_instance(tmp_path):
    hop = _write(tmp_path / "alias", _hop_variant("    next_fn = b\n    next_fn = c\n    return next_fn(n)"))
    a = _route(rp.analyze(hop, "main.py"), "hop.py::a")
    assert a["incomplete"], "fn = b 之後又 fn = c：不追別名、計入未解，不可以當成確定連到 b"
    cs = CS_INHERIT.replace("var x = new Base();\n        x.Work();", "var x = new Base();\n        x = new Child();\n        x.Work();")
    g = rp.build_graph(_write(tmp_path / "cs", {"Program.cs": cs}))
    main_work = {e.dst: e.guess for e in g.edges["Program.cs::Program.Main"] if "Work" in e.dst}
    assert set(main_work) == {"Program.cs::Base.Work", "Program.cs::Child.Work"} and all(main_work.values()), \
        "x 被重新指定成 Child：實際型別不確定，兩個都連且標候選"
    py = dict(PY_KINDS)
    py["main.py"] = py["main.py"].replace('bus.emit("saved", "k1")', 'bus = Bus()\n    bus.emit("saved", "k1")')
    r = _route(rp.analyze(_write(tmp_path / "py", py), "main.py"), "main.py::on_saved")
    assert not r["certain"], "bus 被換成新的實例後才發事件：不能算同一實例"


def test_production_callback_ignores_fakes_passed_from_test_files(tmp_path):
    files = {
        "app.py": ('def snapshot(rev=None):\n    for i in range(2):\n        rev(i)\n\n\n'
                   'def real_rev(i):\n    k = i + 1\n    k *= 2\n    return k\n\n\n'
                   'if __name__ == "__main__":\n    snapshot(real_rev)\n'),
        "tests/test_app.py": ("from app import snapshot\n\n\ndef test_snapshot():\n    def fake_rev(i):\n"
                              "        z = i\n        z += 9\n        return z\n    snapshot(fake_rev)\n"),
    }
    report = rp.analyze(_write(tmp_path, files), "app.py")
    landings = {r["landing"]: r for r in report["entries"][0]["routes"]}
    assert "app.py::real_rev" in landings and landings["app.py::real_rev"]["certain"]
    assert not any(k.startswith("tests/") for k in landings), "測試檔傳進來的假函式不是 production 會跑的路"


def test_overload_call_must_be_candidate(tmp_path):
    report = rp.analyze(_write(tmp_path, {"K.cs": _k(CS_W_INT, CS_W_STR)}))
    for landing in ("K.cs::K.Work(int)", "K.cs::K.Work(string)"):
        r = _route(report, landing)
        assert not r["certain"] and r["steps"][-1]["guess"].startswith("候選")
    text = rp.render(report, 3)
    assert "最差 0 條路徑（全確定）" in text and "最差 2 條路徑（含候選）" in text


def test_dispatch_tables_are_never_certain(tmp_path):
    report = rp.analyze(_write(tmp_path, PY_LAZY), "entry.py::main")
    r = _route(report, "handlers/alpha.py::handle_alpha")
    assert not r["certain"] and r["steps"][-1]["guess"].startswith("候選：分派表"), "分派表不在確定白名單：只有一項也是候選"
    fixed = rp.analyze(_write(tmp_path / "kinds", PY_KINDS), "main.py")
    assert not _route(fixed, "main.py::on_table")["certain"], "寫死鍵也只是縮小候選範圍"


def test_utf16_bom_is_decoded_and_bad_bytes_are_listed_not_silent(tmp_path):
    root = _write(tmp_path / "proj", PY_STRAIGHT)
    (root / "core.py").write_bytes(codecs.BOM_UTF16_LE + PY_CORE.encode("utf-16-le"))
    (root / "be.py").write_bytes(codecs.BOM_UTF16_BE + "def be(n):\n    return n + 1\n".encode("utf-16-be"))
    (root / "bad.py").write_bytes("def f():\n    return 'caf\xe9'\n".encode("latin-1"))
    (root / "Top.cs").write_text("System.Console.WriteLine(1);\nstatic int Add(int a, int b) { return a + b; }\n",
                                 encoding="utf-8")
    report = rp.analyze(root, "app.py")
    _route(report, "core.py::work")
    assert report["stats"]["file_funcs"]["be.py"] == 1
    assert [e.split("（")[0] for e in report["stats"]["parse_errors"]] == ["bad.py"]
    assert report["stats"]["empty_files"] == ["Top.cs"] and "有定義卻解析出零函式" in rp.render(report, 3)


def test_compare_marks_every_row_through_a_failed_file_undecidable(tmp_path):
    old = _write(tmp_path / "old", PY_STRAIGHT)
    new = _write(tmp_path / "new", PY_STRAIGHT)
    (new / "core.py").write_bytes(PY_CORE.replace("total = 0", "total = 'caf\xe9'").encode("latin-1"))
    res = rp.run_compare(new, str(old), None, "app.py", None)
    assert res["emptied_files"] == ["core.py"] and res["coverage_drop"] is True
    assert _row(res, "core.py::work")["status"] == "undecidable", "落點所在檔解析失敗：那一列不可判定，不是消失"


def test_report_and_json_carry_the_caveats_that_apply(tmp_path):
    report = rp.analyze(_write(tmp_path / "w", CS_WRAPPED))
    assert any("只轉傳的層 3 步" in c for c in report["caveats"])
    assert "本次涉及的限制與可能誤報：" in rp.render(report, 3)
    partial = rp.analyze(_write(tmp_path / "p", CS_PARTIAL_NO_AXIS))
    assert any("無責任後綴的 partial：Player" in c for c in partial["caveats"])
    kinds = rp.analyze(_write(tmp_path / "k", PY_KINDS), "main.py")
    assert any("繼承／介面分派" in c for c in kinds["caveats"]) and any("含候選的路徑" in c for c in kinds["caveats"])


# ─── codex 二次初審（fcd1176）抓到的反例：不得出現確定捷徑、不得報成變好 ─────────

PY_CHAIN = {
    "app.py": ('from mid import b\nfrom end import done\n\n\ndef main():\n    return b(1)\n\n\n'
               'if __name__ == "__main__":\n    main()\n'),
    "mid.py": "from end import done\n\n\ndef b(n):\n    k = n + 1\n    k *= 2\n    return c(k)\n\n\ndef c(n):\n    m = n - 1\n    m *= 3\n    return done(m)\n",
    "end.py": "def done(n):\n    t = n * 2\n    t += 1\n    return t\n",
}


def test_alias_assignment_order_cannot_create_a_certain_shortcut(tmp_path):
    old = _write(tmp_path / "old", PY_CHAIN)
    new = _write(tmp_path / "new", {**PY_CHAIN, "app.py": PY_CHAIN["app.py"].replace(
        "    return b(1)", "    f = done\n    f = b\n    return f(1)")})
    g = rp.build_graph(new)
    assert not g.edges["app.py::main"], "f 被指定兩次：不挑一個當確定目標（尤其不能直接連到 done）"
    res = rp.run_compare(new, str(old), None, "app.py", None)
    assert res["counts"]["better"] == 0 and res["coverage_drop"] is True


def test_rebinding_a_constructed_variable_drops_exact_type(tmp_path):
    files = {"app.py": ("class Base:\n    def work(self):\n        a = 1\n        a += 1\n        return a\n\n\n"
                        "class Child(Base):\n    def work(self):\n        b = 2\n        b += 1\n        return b\n\n\n"
                        "def main(obj: Base):\n    x = Base()\n    x = obj\n    return x.work()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    assert not [e for e in g.edges["app.py::main"] if e.dst == "app.py::Base.work" and not e.guess], \
        "x 改指向 obj（可能是 Child）：不能確定只連 Base.work"


def test_guessed_reference_stays_uncertain_through_callback_and_event(tmp_path):
    files = {
        "app.py": ('def run(cb):\n    for i in range(2):\n        cb()\n\n\n'
                   'def main(obj):\n    run(obj.work)\n    bus = Bus()\n    bus.on("x", obj.work)\n    bus.emit("x")\n\n\n'
                   'class Bus:\n    def on(self, key, fn):\n        self.k = key\n        self.f = fn\n        self.n = 0\n\n'
                   '    def emit(self, key):\n        self.n += 1\n        self.k = key\n        return self.n\n'),
        "w.py": "class W:\n    def work(self):\n        q = 1\n        q += 1\n        return q\n",
    }
    g = rp.build_graph(_write(tmp_path, files))
    cb = [e for e in g.edges["app.py::run"] if e.kind == "callback"]
    ev = [e for e in g.edges["app.py::main"] if e.kind == "event"]
    assert cb and all(e.guess for e in cb), "obj 型別不明、靠同名猜到 W.work：轉成 callback 邊也要帶著不確定"
    assert ev and all(e.guess for e in ev), "同一 bus 訂閱又發出，但處理函式本身是猜的：事件邊也要帶著不確定"


def test_event_receiver_rebound_from_parameter_is_not_same_instance(tmp_path):
    files = {"app.py": ('class Bus:\n    def on(self, key, fn):\n        self.k = key\n        self.f = fn\n        self.n = 0\n\n'
                        '    def emit(self, key):\n        self.n += 1\n        self.k = key\n        return self.n\n\n\n'
                        'def handler():\n    h = 1\n    h += 1\n    return h\n\n\n'
                        'def run(bus):\n    bus.on("x", handler)\n    bus = Bus()\n    bus.emit("x")\n')}
    g = rp.build_graph(_write(tmp_path, files))
    ev = [e for e in g.edges["app.py::run"] if e.kind == "event"]
    assert ev and all(e.guess.startswith("候選") for e in ev)


def test_base_call_and_constructor_overloads_are_candidates(tmp_path):
    cs = """class B {
    public B(int a) { a += 1; a *= 2; a -= 3; }
    public B(string s) { s += "x"; s += "y"; s += "z"; }
    public void Work(int a) { a += 1; a *= 2; a -= 3; }
    public void Work(string s) { s += "x"; s += "y"; s += "z"; }
}
class C : B {
    public C() : base(1) { }
    public void Go() { base.Work(1); var b = new B(1); b.Work(2); }
}
"""
    g = rp.build_graph(_write(tmp_path, {"C.cs": cs}))
    edges = g.edges["C.cs::C.Go"]
    assert {e.dst for e in edges} >= {"C.cs::B.Work(int)", "C.cs::B.Work(string)", "C.cs::B.B(int)", "C.cs::B.B(string)"}
    assert all(e.guess.startswith("候選") for e in edges)


def test_generic_overloads_keep_full_signatures_and_compare_by_them(tmp_path):
    k = lambda *ms: "using System.Collections.Generic;\n" + _k(*ms)
    w_int = "    void Work(List<int> xs) { int a = 1; a += 1; a *= 2; }\n"
    w_str = "    void Work(List<string> xs) { int b = 2; b += 1; b *= 3; }\n"
    ids = sorted(f.id for f in rp.lang.parse_csharp("K.cs", k(w_int, w_str)).funcs if f.name == "Work")
    assert ids == ["K.cs::K.Work(List<int>)", "K.cs::K.Work(List<string>)"]
    old = _write(tmp_path / "old", {"K.cs": k(w_int, w_str)})
    new = _write(tmp_path / "new", {"K.cs": k(w_str, w_int)})
    res = rp.run_compare(new, str(old), None, None, None)
    work_rows = [r for r in res["rows"] if "Work" in r["landing"]]
    assert len(work_rows) == 2 and all(r["status"] == "same" for r in work_rows)


def test_unresolvable_invoke_is_not_external_and_compare_is_undecidable(tmp_path):
    before = {"P.cs": ("class P {\n    static void Main() { Relay(); }\n    static void Relay() { Work(); }\n"
                       "    static void Work() { int a = 1; a += 1; a *= 2; }\n}\n")}
    after = {"P.cs": ("using System;\nclass P {\n    static void Main() { Action a = Pick(); a.Invoke(); }\n"
                      "    static Action Pick() { int k = 1; k += 1; return Work; }\n"
                      "    static void Work() { int a = 1; a += 1; a *= 2; }\n}\n")}
    res = rp.run_compare(_write(tmp_path / "new", after), str(_write(tmp_path / "old", before)), None, None, None)
    assert res["coverage_drop"] is True and res["counts"]["gone"] == 0 and res["counts"]["better"] == 0
    assert res["undecidable_entries"] == ["P.cs::P.Main"]


def test_external_aliases_and_static_usings_are_not_unresolved(tmp_path):
    files = {
        "app.py": ('import json\n\n\ndef work(s):\n    parse = json.loads\n    data = parse(s)\n    data["k"] = 1\n    return data\n\n\n'
                   'if __name__ == "__main__":\n    work("{}")\n'),
        "M.cs": ("using static System.Math;\nusing static Util;\nclass M {\n    static void Main() { Work(2.0); }\n"
                 "    static double Work(double x) { var r = Sqrt(x); r += Twice(x); return r * 2; }\n}\n"
                 "static class Util {\n    public static double Twice(double v) { var t = v; t *= 2; return t + 0; }\n}\n"),
    }
    report = rp.analyze(_write(tmp_path, files))
    assert report["stats"]["unresolved"] == 0
    assert _route(report, "M.cs::Util.Twice")["certain"], "using static 專案類別：裸名連得到"


def test_zero_function_warning_covers_custom_types_and_top_level_statements(tmp_path):
    files = {"Top.cs": "class Widget { }\nstatic Widget Create() { return new Widget(); }\n",
             "Script.cs": "System.Console.WriteLine(1);\nSystem.Console.WriteLine(2);\n",
             "Data.cs": "enum Color { Red, Green }\n", "consts.py": "LIMIT = 3\nNAMES = ['a', 'b']\n"}
    report = rp.analyze(_write(tmp_path, files))
    assert report["stats"]["empty_files"] == ["Script.cs", "Top.cs"], "純資料檔（enum、常數）不警示"


# ─── codex 三次初審（5de7780）抓到的反例 ─────────────────────────────────────

PY_WORK = "def work():\n    w = 1\n    w += 1\n    return w\n\n\ndef alternate():\n    a = 2\n    a *= 3\n    return a\n\n\n"


def test_default_callback_is_followed_and_compare_stays_same(tmp_path):
    old = _write(tmp_path / "old", {"app.py": PY_WORK + "def run():\n    for i in range(2):\n        work()\n\n\n"
                                              'if __name__ == "__main__":\n    run()\n'})
    new = _write(tmp_path / "new", {"app.py": PY_WORK + "def run(cb=work):\n    for i in range(2):\n        cb()\n\n\n"
                                              'if __name__ == "__main__":\n    run()\n'})
    _route(rp.analyze(new, "app.py"), "app.py::work")
    res = rp.run_compare(new, str(old), None, "app.py", None)
    assert res["counts"]["gone"] == 0 and res["counts"]["better"] == 0


def test_calling_a_computed_callable_counts_as_unresolved(tmp_path):
    old = _write(tmp_path / "old", {"app.py": PY_WORK + "def main():\n    return work()\n\n\n"
                                              'if __name__ == "__main__":\n    main()\n'})
    new = _write(tmp_path / "new", {"app.py": PY_WORK + "def factory():\n    return work\n\n\n"
                                              "def main():\n    return factory()()\n\n\n"
                                              'if __name__ == "__main__":\n    main()\n'})
    assert rp.build_graph(new).unres["app.py::main"] == 1
    res = rp.run_compare(new, str(old), None, "app.py", None)
    assert res["coverage_drop"] is True and res["counts"]["gone"] == 0 and res["counts"]["better"] == 0


def test_callback_with_an_unseen_source_is_candidate_and_unresolved(tmp_path):
    files = {"app.py": PY_WORK + ("def choose():\n    return alternate\n\n\n"
                                  "def run(cb):\n    for i in range(2):\n        cb()\n\n\n"
                                  "def warmup():\n    run(work)\n\n\n"
                                  "def main():\n    warmup()\n    run(choose())\n\n\n"
                                  'if __name__ == "__main__":\n    main()\n')}
    g = rp.build_graph(_write(tmp_path, files))
    cb = [e for e in g.edges["app.py::run"] if e.kind == "callback"]
    assert cb and all(e.guess.startswith("候選：有呼叫處傳進看不到的函式") for e in cb)
    assert g.unres["app.py::run"] >= 1


def test_reassigned_callback_parameter_is_candidate(tmp_path):
    files = {"app.py": PY_WORK + ("def run(cb, offline):\n    if offline:\n        cb = alternate\n    cb()\n\n\n"
                                  "def main():\n    run(work, True)\n\n\n"
                                  'if __name__ == "__main__":\n    main()\n')}
    g = rp.build_graph(_write(tmp_path, files))
    edges = {e.dst: e.guess for e in g.edges["app.py::run"]}
    assert set(edges) >= {"app.py::work", "app.py::alternate"} and all(edges.values())


def test_event_on_a_field_receiver_is_not_same_instance(tmp_path):
    files = {"app.py": ('class Bus:\n    def on(self, key, fn):\n        self.k = key\n        self.f = fn\n        self.n = 0\n\n'
                        '    def emit(self, key):\n        self.n += 1\n        self.k = key\n        return self.n\n\n\n'
                        + PY_WORK +
                        'class Svc:\n    def go(self):\n        self.bus = Bus()\n        self.bus.on("x", work)\n'
                        '        self.bus = Bus()\n        self.bus.emit("x")\n')}
    g = rp.build_graph(_write(tmp_path, files))
    ev = [e for e in g.edges["app.py::Svc.go"] if e.kind == "event"]
    assert ev and all(e.guess.startswith("候選") for e in ev)


def test_csharp_ref_argument_drops_exact_type(tmp_path):
    cs = CS_INHERIT.replace("var x = new Base();\n        x.Work();",
                            "var x = new Base();\n        Replace(ref x);\n        x.Work();") \
        .replace("    static void Run(Base y) {", "    static void Replace(ref Base b) { b = new Child(); }\n    static void Run(Base y) {")
    g = rp.build_graph(_write(tmp_path, {"Program.cs": cs}))
    main_work = {e.dst: e.guess for e in g.edges["Program.cs::Program.Main"] if "Work" in e.dst}
    assert "Program.cs::Child.Work" in main_work and all(main_work.values()), "x 傳 ref 出去後可能變成 Child"


def test_multiple_static_usings_with_same_name_are_candidates(tmp_path):
    cs = ("using static A;\nusing static B;\nclass M {\n    static void Main() { Work(1); }\n}\n"
          "static class A {\n    public static void Work(string s) { s += \"x\"; s += \"y\"; s += \"z\"; }\n}\n"
          "static class B {\n    public static void Work(int n) { n += 1; n *= 2; n -= 3; }\n}\n")
    g = rp.build_graph(_write(tmp_path, {"M.cs": cs}))
    edges = {e.dst: e.guess for e in g.edges["M.cs::M.Main"]}
    assert set(edges) == {"M.cs::A.Work", "M.cs::B.Work"} and all(edges.values())


def test_python_union_annotation_is_not_narrowed_to_its_first_member(tmp_path):
    files = {"app.py": ("from typing import Union\n\n\nclass Disk:\n    def save(self):\n        d = 1\n        d += 1\n        return d\n\n\n"
                        "class Cloud:\n    def save(self):\n        c = 2\n        c += 1\n        return c\n\n\n"
                        "def main(store: Union[Disk, Cloud], other: Disk | Cloud, maybe: Disk | None):\n"
                        "    store.save()\n    other.save()\n    maybe.save()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    certain = [e.dst for e in g.edges["app.py::main"] if not e.guess]
    assert certain == ["app.py::Disk.save"], "只有 Disk | None 能確定是 Disk；兩種聯集都不能只挑 Disk"
    assert g.unres["app.py::main"] == 2


# ─── codex 四次初審（813a401）抓到的反例 ─────────────────────────────────────

def _run_main(body: str) -> dict:
    return {"app.py": PY_WORK + body + '\n\nif __name__ == "__main__":\n    main()\n'}


def test_computed_default_callback_is_unresolved_not_gone(tmp_path):
    old = _write(tmp_path / "old", _run_main("def run():\n    for i in range(2):\n        work()\n\n\ndef main():\n    run()\n"))
    new = _write(tmp_path / "new", _run_main("def choose():\n    return work\n\n\ndef run(cb=choose()):\n"
                                             "    for i in range(2):\n        cb()\n\n\ndef main():\n    run()\n"))
    assert rp.build_graph(new).unres["app.py::run"] == 1
    res = rp.run_compare(new, str(old), None, "app.py", None)
    assert res["coverage_drop"] is True and res["counts"]["gone"] == 0


def test_csharp_subscript_and_named_arguments_are_bound_by_parameter(tmp_path):
    cs = ("using System;\nclass P {\n    static Action[] handlers;\n"
          "    static void Run(int n, Action cb) { for (int i = 0; i < n; i++) { cb(); } }\n"
          "    static void Show(string s, Action cb) { for (int i = 0; i < 2; i++) { cb(); } }\n"
          "    static Action Choose() { int k = 1; k += 1; return Alternate; }\n"
          "    static void Work() { int a = 1; a += 1; a *= 2; }\n"
          "    static void Alternate() { int b = 2; b += 1; b *= 3; }\n"
          "    static void Main() {\n        Run(0, Work);\n        Run(cb: Choose(), n: 1);\n"
          "        Run(1, handlers[0]);\n        Show(\"x\", Work);\n    }\n}\n")
    g = rp.build_graph(_write(tmp_path, {"P.cs": cs}))
    run_cb = [e for e in g.edges["P.cs::P.Run"] if e.kind == "callback"]
    assert run_cb and all(e.guess.startswith("候選：有呼叫處傳進看不到的函式") for e in run_cb)
    show_cb = [(e.dst, e.guess) for e in g.edges["P.cs::P.Show"] if e.kind == "callback"]
    assert show_cb == [("P.cs::P.Work", "")], "字串引數被抹成空白也不能讓後面的引數位置錯位"


def test_callback_also_fed_an_external_function_is_candidate(tmp_path):
    files = _run_main("import json\n\n\ndef run(cb):\n    for i in range(2):\n        cb(\"1\")\n\n\n"
                      "def main():\n    run(work)\n    run(json.loads)\n    run(lambda s: s)\n")
    g = rp.build_graph(_write(tmp_path, files))
    cb = [e for e in g.edges["app.py::run"] if e.kind == "callback"]
    assert cb and all(e.guess.startswith("候選：也有呼叫處傳 lambda 或外部函式") for e in cb)
    assert g.unres["app.py::run"] == 0, "外部函式與 lambda 不是專案內看不到的東西"


def test_csharp_bare_field_receiver_event_is_candidate(tmp_path):
    cs = ("using System;\nclass Bus {\n    public Action Fired;\n}\nclass App {\n    Bus bus = new Bus();\n"
          "    void Work() { int a = 1; a += 1; a *= 2; }\n    void Reset() { bus = new Bus(); }\n"
          "    void Run() {\n        bus.Fired += Work;\n        Reset();\n        bus.Fired?.Invoke();\n    }\n}\n")
    g = rp.build_graph(_write(tmp_path, {"App.cs": cs}))
    ev = [e for e in g.edges["App.cs::App.Run"] if e.kind == "event"]
    assert ev and all(e.guess.startswith("候選") for e in ev)


def test_inherited_classmethod_factory_is_candidate(tmp_path):
    files = {"app.py": ("class Base:\n    def __init__(self):\n        self.x = 1\n        self.y = 2\n        self.z = 3\n\n"
                        "    @classmethod\n    def create(cls):\n        return cls()\n\n\n"
                        "class Child(Base):\n    def __init__(self):\n        self.x = 2\n        self.y = 3\n        self.z = 4\n\n\n"
                        "def main():\n    return Child.create()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    edges = {e.dst: e.guess for e in g.edges["app.py::Base.create"]}
    assert set(edges) == {"app.py::Base.__init__", "app.py::Child.__init__"} and all(edges.values())


def test_normal_code_is_not_flagged_default_same_name_and_args_spread(tmp_path):
    files = _run_main("def run(work=work):\n    for i in range(2):\n        work()\n\n\n"
                      "def call(cb, *args):\n    for i in range(2):\n        cb()\n\n\n"
                      "def main(*args):\n    run()\n    call(alternate, *args)\n")
    g = rp.build_graph(_write(tmp_path, files))
    assert [(e.dst, e.guess) for e in g.edges["app.py::run"]] == [("app.py::work", "")]
    assert [(e.dst, e.guess) for e in g.edges["app.py::call"]] == [("app.py::alternate", "")]
    assert g.unres["app.py::run"] == 0 and g.unres["app.py::call"] == 0


# ─── 退件 005：確定只來自白名單 ──────────────────────────────────────────────

EX_A = {"app.py": ("class Runner:\n    def run(self, cb):\n        for n in range(2):\n            cb(n)\n\n\n"
                   "class Api:\n    def start(self, worker: Runner):\n        return worker.run(done)\n\n\n"
                   "def done(n):\n    x = n + 1\n    x *= 2\n    return x\n\n\n"
                   "def main():\n    a = Api()\n    w = Runner()\n    a.start(w)\n")}
EX_B = {
    "app.py": "from hop import a\n\n\ndef main():\n    return a(2)\n",
    "hop.py": ("from end import done\n\n\ndef c(n):\n    return done(n)\n\n\ndef b(n):\n    return c(n)\n\n\n"
               "def a(n):\n    next_fn = b\n    return next_fn(n)\n"),
    "end.py": "def done(n):\n    for i in range(n):\n        n += i\n    return n\n",
}


def _numbers(r: dict) -> tuple:
    return r["file_jumps"], r["handoffs"], r["turns"], r["depth"]


def test_whitelist_examples_stay_certain_with_the_same_numbers(tmp_path):
    a = _route(rp.analyze(_write(tmp_path / "a", EX_A), "app.py::main"), "app.py::done")
    assert a["certain"] and _numbers(a) == (0, 2, 2, 3), "例 A：委派＋單一來源 callback"
    assert _rules(a) == [2, 3, 5], "剛 new 的 a.start → 2；標註 Runner 的 worker.run → 3；單一來源 callback → 5"
    b = _route(rp.analyze(_write(tmp_path / "b", EX_B), "app.py::main"), "end.py::done")
    assert b["certain"] and _numbers(b) == (2, 3, 4, 4), "例 B：簡單區域別名"
    assert _rules(b) == [1, 4, 1, 1], "import 的 a → 1；next_fn = b → 4；c、done → 1"
    g = rp.build_graph(_write(tmp_path / "c", {"Program.cs": CS_INHERIT}))
    assert [(e.dst, e.guess, e.rule) for e in g.edges["Program.cs::Program.Main"] if "Work" in e.dst] == \
        [("Program.cs::Base.Work", "", 2)]


def _rules(r: dict) -> list:
    return [s["rule"] for s in r["steps"][1:]]


def test_module_alias_overwritten_by_a_factory_is_not_certain(tmp_path):
    hop = EX_B["hop.py"].replace("def a(n):\n    next_fn = b\n    return next_fn(n)\n",
                                 "def a(n):\n    return NEXT(n)\n\n\ndef pick():\n    return b\n\n\nNEXT = done\nNEXT = pick()\n")
    old = _write(tmp_path / "old", EX_B)
    new = _write(tmp_path / "new", {**EX_B, "hop.py": hop})
    g = rp.build_graph(new)
    assert not [e for e in g.edges["hop.py::a"] if not e.guess], "NEXT 被工廠覆寫：不能沿用 NEXT = done 當確定"
    assert g.unres["hop.py::a"] == 1
    res = rp.run_compare(new, str(old), None, "app.py::main", None)
    assert res["counts"]["better"] == 0 and res["coverage_drop"] is True


def test_unsubscribed_event_is_not_certain(tmp_path):
    cs = ("using System;\nclass Bus {\n    public event Action Fired;\n    public void Check() {\n        var bus = new Bus();\n"
          "        bus.Fired += Work;\n        bus.Fired -= Work;\n        bus.Fired?.Invoke();\n    }\n"
          "    void Work() { int n = 1; n += 1; n *= 2; }\n}\n")
    g = rp.build_graph(_write(tmp_path, {"Bus.cs": cs}))
    assert all(e.guess for e in g.edges["Bus.cs::Bus.Check"] if e.kind == "event")


def test_entry_single_to_overload_aligns_by_signature(tmp_path):
    a_fn = "    static void A() { int a = 1; a += 1; a *= 2; }\n"
    one = "class P {\n    static void Run(int n) { A(); n += 1; n *= 2; }\n" + a_fn + "}\n"
    two = ("class P {\n    static void Run(int n) { A(); n += 1; n *= 2; }\n"
           '    static void Run(string s) { A(); s += "x"; s += "y"; }\n' + a_fn + "}\n")
    res = rp.run_compare(_write(tmp_path / "two", {"P.cs": two}), str(_write(tmp_path / "one", {"P.cs": one})),
                         None, "P.Run", None)
    assert (res["entries"], res["counts"]["same"], res["counts"]["new"], res["counts"]["gone"]) == (2, 1, 1, 0)
    back = rp.run_compare(_write(tmp_path / "one2", {"P.cs": one}), str(tmp_path / "two"), None, "P.Run", None)
    assert (back["counts"]["same"], back["counts"]["gone"], back["counts"]["new"]) == (1, 1, 0)


def test_utf16_without_bom_is_decoded_or_listed(tmp_path):
    cs = "class P {\n    static void Main() { A(); }\n    static void A() { int a = 1; a += 1; a *= 2; }\n}\n"
    root = tmp_path / "proj"
    root.mkdir()
    (root / "P.cs").write_bytes(cs.encode("utf-16-le"))
    (root / "Q.cs").write_bytes(cs.replace("P", "Q").encode("utf-16-be"))
    (root / "Bad.cs").write_bytes(b"class B { }\x00\x00\x01\x00\x00\x02")
    report = rp.analyze(root)
    assert report["stats"]["file_funcs"]["P.cs"] == 2 and report["stats"]["file_funcs"]["Q.cs"] == 2
    assert [e.split("（")[0] for e in report["stats"]["parse_errors"]] == ["Bad.cs"]


def test_callback_without_known_callers_is_unresolved_entry(tmp_path):
    report = rp.analyze(_write(tmp_path, {"api.py": "def run(cb):\n    cb()\n"}), "api.py::run")
    e = report["entries"][0]
    assert e["unresolved_reach"] == 1 and e["certain_routes"] == 0
    assert "無法評級" in rp.render(report, 3), "沒有確定路徑時不能顯示 0 彎、順"
    g = rp.build_graph(tmp_path)
    assert g.hits["api.py::run"] == 0 and g.unres["api.py::run"] == 1


def test_compare_text_carries_caveats(tmp_path):
    old = _write(tmp_path / "old", PY_STRAIGHT)
    new = _write(tmp_path / "new", PY_WRAPPED)
    text = rp.render_compare(rp.run_compare(new, str(old), None, "app.py", None), 3)
    assert "本次涉及的限制與可能誤報：" in text and "只轉傳的層" in text


# ─── 白名單初審（be45e1f）抓到的：白名單外卻確定（A）、白名單內被誤標（B） ─────────

def _certain_edges(g, fid: str) -> list:
    return sorted(e.dst for e in g.edges[fid] if not e.guess)


def test_a_module_import_rebound_by_a_factory_is_not_certain(tmp_path):
    files = {"a.py": "def work():\n    w = 1\n    w += 1\n    return w\n",
             "app.py": ("import a\n\n\ndef pick_backend():\n    return object()\n\n\na = pick_backend()\n\n\n"
                        "def main():\n    a.work()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    assert _certain_edges(g, "app.py::main") == []


def test_a_one_uncertain_callback_source_keeps_the_edge_candidate(tmp_path):
    files = {"app.py": ("class Base:\n    def work(self):\n        raise NotImplementedError\n\n\n"
                        "class Child(Base):\n    def work(self):\n        q = 1\n        q += 1\n        return q\n\n\n"
                        "def run(cb):\n    cb()\n\n\ndef install(b: Base):\n    run(b.work)\n\n\n"
                        "def main():\n    c = Child()\n    run(c.work)\n    install(c)\n")}
    g = rp.build_graph(_write(tmp_path, files))
    assert _certain_edges(g, "app.py::run") == [], "b.work 是候選：同一目標的確定來源不能抹掉它"


def test_a_callback_stored_in_a_field_is_candidate(tmp_path):
    files = {"app.py": ("def work():\n    w = 1\n    w += 1\n    return w\n\n\n"
                        "class Runner:\n    def __init__(self, cb):\n        self.cb = cb\n\n"
                        "    def run(self):\n        self.cb()\n\n\n"
                        "def main():\n    r = Runner(work)\n    r.run()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    edges = [(e.dst, e.guess) for e in g.edges["app.py::Runner.run"]]
    assert edges and all(guess.startswith("候選：經由欄位存下的 callback") for _, guess in edges)


def test_a_csharp_delegate_compound_assignment_is_not_a_simple_alias(tmp_path):
    cs = ("using System;\nclass P {\n    static void A() { int x = 1; x++; x *= 2; }\n"
          "    static void B() { int x = 2; x++; x *= 3; }\n"
          "    static void Main() {\n        Action cb = A;\n        cb += B;\n        cb();\n    }\n}\n")
    g = rp.build_graph(_write(tmp_path, {"P.cs": cs}))
    assert _certain_edges(g, "P.cs::P.Main") == []


def test_b_annotation_without_value_is_not_a_binding(tmp_path):
    files = {"app.py": ("from typing import Callable\n\n\ndef work():\n    w = 1\n    w += 1\n    return w\n\n\n"
                        "handler: Callable\nhandler = work\n\n\ndef main():\n    handler()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    assert _certain_edges(g, "app.py::main") == ["app.py::work"]


def test_b_annotated_construction_is_exact(tmp_path):
    files = {"app.py": ("class Base:\n    def run(self):\n        return 1\n\n\n"
                        "class Child(Base):\n    def run(self):\n        return 2\n\n\n"
                        "def main():\n    w: Base = Base()\n    w.run()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    assert [(e.dst, e.guess) for e in g.edges["app.py::main"] if "run" in e.dst] == [("app.py::Base.run", "")]


# ─── 退件 007：確定改成由白名單主動證明（Edge.rule） ─────────────────────────

def _corpus() -> dict:
    """結構守門用的夾具語料：每一種轉手與白名單 1～5 都有。"""
    return {"ex_a": EX_A, "ex_b": EX_B, "cs_inherit": {"Program.cs": CS_INHERIT}, "py_kinds": PY_KINDS,
            "cs_kinds": CS_KINDS, "py_wrapped": PY_WRAPPED}


def _graphs(tmp_path) -> dict:
    return {name: rp.build_graph(_write(tmp_path / name, files)) for name, files in _corpus().items()}


def _rule_edges(graphs: dict, n: int) -> set:
    return {(name, src, e.dst) for name, g in graphs.items() for src, es in g.edges.items() for e in es if e.rule == n}


def test_certain_only_comes_from_a_rule(tmp_path):
    """每條邊：有 rule ⇔ 沒有不確定原因；rule 只會是 1～5；路線的「全確定」＝每一步都有 rule。"""
    for name, files in _corpus().items():
        root = _write(tmp_path / name, files)
        g = rp.build_graph(root)
        for src, es in g.edges.items():
            for e in es:
                assert e.rule in (None, 1, 2, 3, 4, 5), (name, src, e)
                assert (e.rule is None) == bool(e.guess), f"{name} {src}→{e.dst}：確定與否只看 rule，原因只是說明"
        for r in itertools.chain.from_iterable(entry["routes"] for entry in rp.analyze(root)["entries"]):
            assert r["certain"] == all(s["rule"] is not None for s in r["steps"][1:]), (name, r["landing"])


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_removing_one_rule_makes_its_edges_uncertain(tmp_path, monkeypatch, n):
    """臨時拿掉第 n 條的判斷：原本靠它確定的邊全部變成不確定、也沒有改由別條補上——證明確定只從 rule 來。"""
    before = _rule_edges(_graphs(tmp_path / "before"), n)
    assert before, f"語料裡要有靠第 {n} 條確定的邊"
    monkeypatch.setattr(rp.Graph, f"_rule{n}", lambda self, *a: False)
    after = _graphs(tmp_path / "after")
    still = {(name, src, e.dst) for name, g in after.items() for src, es in g.edges.items() for e in es
             if e.rule is not None and (name, src, e.dst) in before}
    assert not still, f"拿掉第 {n} 條後仍確定：{sorted(still)[:3]}"
    assert not _rule_edges(after, n)


def test_c2_nested_function_name_reassigned_in_outer_scope_is_not_certain(tmp_path):
    files = {"app.py": ("def outer():\n    def work():\n        x = 1\n        y = x + 1\n        return y\n\n"
                        "    def inner():\n        work()\n\n    work = lambda: 2\n    inner()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    edges = [(e.dst, e.rule) for e in g.edges["app.py::outer.inner"]]
    assert edges == [("app.py::outer.work", None)], "work 在 outer 裡被改指成 lambda：白名單 1 不成立"


def test_c2_closure_over_an_outer_parameter_is_not_certain(tmp_path):
    files = {"app.py": ("def work():\n    x = 1\n    x += 1\n    return x\n\n\n"
                        "def outer(work):\n    def inner():\n        work()\n    inner()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    assert all(e.rule is None for e in g.edges["app.py::outer.inner"]), "inner 呼叫的是 outer 的參數，不是模組層的 work"


WORKER = "class Worker:\n    def run(self):\n        x = 1\n        y = x + 1\n        return y\n"


def test_c1_class_name_rebound_by_a_factory_is_not_certain(tmp_path):
    files = {"app.py": WORKER + "\n\ndef factory():\n    return object\n\n\nWorker = factory()\n\n\n"
                                "def main():\n    w = Worker()\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert all(e.rule is None for e in g.edges["app.py::main"]), "Worker 被工廠覆寫：建構者名稱不穩定，第 2 條不成立"


def test_c3_constructed_local_stored_to_a_field_is_not_certain(tmp_path):
    files = {"app.py": WORKER + "\n\ndef main(holder):\n    w = Worker()\n    holder.worker = w\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    edges = [(e.dst, e.rule) for e in g.edges["app.py::main"]]
    assert edges == [("app.py::Worker.run", None)], "w 存進欄位：第 2 條不成立；沒有宣告型別，也不能轉用第 3 條"


@pytest.mark.parametrize("store", ["    items = [w]\n", "    pool = []\n    pool.append(w)\n", '    d = {"k": w}\n'])
def test_constructed_local_put_into_a_container_is_not_certain(tmp_path, store):
    files = {"app.py": WORKER + "\n\ndef main():\n    w = Worker()\n" + store + "    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert all(e.rule is None for e in g.edges["app.py::main"] if e.dst == "app.py::Worker.run")


def test_c5_annotated_self_field_in_init_is_certain_by_rule_3(tmp_path):
    files = {"app.py": WORKER + "\n\nclass App:\n    def __init__(self, worker):\n        self.worker: Worker = worker\n\n"
                                "    def run(self):\n        self.worker.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert [(e.dst, e.rule) for e in g.edges["app.py::App.run"]] == [("app.py::Worker.run", 3)]
    assert g.unres["app.py::App.run"] == 0


def test_c4_constructor_through_an_import_alias_is_certain_by_rule_2(tmp_path):
    files = {"worker.py": WORKER, "app.py": "from worker import Worker as W\n\n\ndef main():\n    w = W()\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    run = [(e.dst, e.rule) for e in g.edges["app.py::main"] if e.dst.endswith("run")]
    assert run == [("worker.py::Worker.run", 2)], "W 經 import 別名唯一解析到 worker.Worker，剛 new 的區域變數"


def test_import_alias_annotation_and_reexport_resolve_to_the_original_class(tmp_path):
    files = {"worker.py": WORKER, "pkg.py": "from worker import Worker\n",
             "app.py": "from pkg import Worker as W\n\n\ndef main(w: W):\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert [(e.dst, e.rule) for e in g.edges["app.py::main"]] == [("worker.py::Worker.run", 3)]


def test_constructor_alias_rebound_in_the_importing_module_is_not_certain(tmp_path):
    files = {"worker.py": WORKER,
             "app.py": "from worker import Worker as W\n\nW = object\n\n\ndef main():\n    w = W()\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert all(e.rule is None for e in g.edges["app.py::main"])


def test_json_steps_carry_the_rule_number(tmp_path):
    root = _write(tmp_path, EX_B)
    out = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--root", str(root), "--entry", "app.py::main", "--json"],
                         capture_output=True, text=True, encoding="utf-8")
    payload = json.loads("\n".join(out.stdout.strip().splitlines()[:-1]))
    route = next(r for r in payload["entries"][0]["routes"] if r["landing"] == "end.py::done")
    assert [s["rule"] for s in route["steps"]] == [None, 1, 4, 1, 1], "入口那一步沒有條號；之後每一步附憑哪一條確定"


def test_compare_same_numbers_are_undecidable_when_coverage_got_worse(tmp_path):
    old = _write(tmp_path / "old", PY_HOP)
    worse = "def pick():\n    return 1\n\n\ndef done(n):\n    t = n * 2\n    h = pick()\n    h()\n    return t\n"
    new = _write(tmp_path / "new", {**PY_HOP, "end.py": worse})
    res = rp.run_compare(new, str(old), None, "main.py", None)
    row = _row(res, "end.py::done")
    assert _numbers(row["before"])[:3] == _numbers(row["after"])[:3], "這一列前後數字相同"
    assert row["status"] == "undecidable", "可達範圍內看不到的呼叫變多：數字是下限，相同也不能報成不變"


def test_constructed_self_field_is_found_but_not_certain(tmp_path):
    files = {"app.py": WORKER + "\n\nclass App:\n    def __init__(self):\n        self.worker = Worker()\n\n"
                                "    def run(self):\n        self.worker.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert [(e.dst, e.rule) for e in g.edges["app.py::App.run"]] == [("app.py::Worker.run", None)], \
        "self.x = Foo() 是推導的欄位型別（欄位可能被換）：找得到目標，但第 3 條只吃宣告型別"


# ─── 入口自動偵測、CLI 與哨兵 ────────────────────────────────────────────────

def test_auto_entry_skips_test_files_even_when_root_lives_under_tests_dir(tmp_path):
    root = _write(tmp_path / "tests" / "proj", {**PY_STRAIGHT,
                                                 "tests/test_app.py": 'if __name__ == "__main__":\n    print(1)\n'})
    report = rp.analyze(root)
    assert [e["entry"] for e in report["entries"]] == ["app.py::<main>"]


def test_unity_lifecycle_methods_are_entries(tmp_path):
    root = _write(tmp_path, {"Mover.cs": "class Mover : MonoBehaviour {\n    void Update() { Tick(); Tick(); }\n"
                                         "    void Tick() { int a = 1; a += 1; a *= 2; }\n}\n"})
    report = rp.analyze(root)
    assert [e["entry"] for e in report["entries"]] == ["Mover.cs::Mover.Update"]


def test_cli_text_json_and_sentinels(tmp_path):
    root = _write(tmp_path, PY_WRAPPED)
    run = lambda *a: subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--root", str(root), *a],
                                    capture_output=True, text=True, encoding="utf-8")
    text = run("--entry", "app.py")
    assert text.returncode == 0, text.stderr
    last = text.stdout.strip().splitlines()[-1]
    assert re.fullmatch(r"READING_PATH DONE( \w+=\S+)*", last) and "max_turns=4" in last and "smelly=1" in last
    assert "尺不是判決" in text.stdout and "[臭掉]" in text.stdout

    js = run("--entry", "app.py", "--json")
    payload = json.loads("\n".join(js.stdout.strip().splitlines()[:-1]))
    assert payload["entries"][0]["routes"][0]["turns"] == 4 and "caveats" in payload

    bad = run("--entry", "no_such_func")
    assert bad.returncode == 1 and bad.stdout.strip().splitlines()[-1].startswith("READING_PATH FAIL reason=")

    helped = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--help"], capture_output=True, text=True,
                            encoding="utf-8")
    assert helped.returncode == 0 and "--before" in helped.stdout and "抓不到" in helped.stdout
