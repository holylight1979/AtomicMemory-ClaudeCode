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
    assert all(res["counts"][k] == 0 for k in ("better", "worse", "new", "gone"))
    assert res["counts"]["undecidable"] >= 4 and res["undecidable_entries"] == ["main.py::<main>"], \
        "Bus.emit 裡 fn(*args) 解析不了、入口可達：兩側一樣沒觀測完整也只能不可判定，不報不變（021）"
    full = rp.run_compare(_write(tmp_path / "d", PY_WRAPPED), str(_write(tmp_path / "c", PY_WRAPPED)), None, None, None)
    assert full["counts"]["same"] == len(full["rows"]) >= 1 and full["undecidable_entries"] == [], "全部解析得了才報不變"


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
    pick = _route(report, "hop.py::pick")
    assert pick["incomplete"] and pick["unresolved"] == 0 and pick["unresolved_path"] == 1, "經過 a 才到 pick：整條路未讀到底（019）"
    assert report["entries"][0]["grades"]["順"] == 0 and not report["entries"][0]["ratable"], "未讀到底的路不算進刻度分布"
    assert "（未讀到底" in rp.render(report, 3) and "incomplete=2" in rp.done_line(report)
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
    assert [(e.dst, e.guess, _rule_of(e)) for e in g.edges["Program.cs::Program.Main"] if "Work" in e.dst] == \
        [("Program.cs::Base.Work", "", 2)]


def _rules(r: dict) -> list:
    return [s.get("rule") for s in r["steps"][1:]]


def _rule_of(e):
    """邊的白名單條號；用 getattr 讀，新案退回沒有 rule 的舊版時紅在斷言、不是紅在屬性。"""
    return getattr(e, "rule", None)


def _sure(e) -> bool:
    """這條邊確定嗎：有 rule 欄的版本只看 rule；沒有 rule 欄的舊版看有沒有不確定原因（舊版的口徑）。"""
    return _rule_of(e) is not None if hasattr(e, "rule") else not e.guess


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
    events = [e for e in g.edges["Bus.cs::Bus.Check"] if e.kind == "event"]
    assert events, "要先有連到 Work 的事件邊，空集合的 all() 不算驗到"
    assert all(e.guess and _rule_of(e) is None for e in events)


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
    return {(name, src, e.dst) for name, g in graphs.items() for src, es in g.edges.items() for e in es
            if _rule_of(e) == n}


def test_certain_only_comes_from_a_rule(tmp_path):
    """每條邊：有 rule ⇔ 沒有不確定原因；rule 只會是 1～5；路線的「全確定」＝每一步都有 rule。"""
    for name, files in _corpus().items():
        root = _write(tmp_path / name, files)
        g = rp.build_graph(root)
        for src, es in g.edges.items():
            for e in es:
                assert _rule_of(e) in (None, 1, 2, 3, 4, 5), (name, src, e)
                assert (_rule_of(e) is None) == bool(e.guess), f"{name} {src}→{e.dst}：確定與否只看 rule，原因只是說明"
        for r in itertools.chain.from_iterable(entry["routes"] for entry in rp.analyze(root)["entries"]):
            assert r["certain"] == all(s.get("rule") is not None for s in r["steps"][1:]), (name, r["landing"])


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_removing_one_rule_makes_its_edges_uncertain(tmp_path, monkeypatch, n):
    """臨時拿掉第 n 條的判斷：原本靠它確定的邊全部變成不確定、也沒有改由別條補上，證明確定只從 rule 來。"""
    before = _rule_edges(_graphs(tmp_path / "before"), n)
    assert before, f"語料裡要有靠第 {n} 條確定的邊"
    monkeypatch.setattr(rp.Graph, f"_rule{n}", lambda self, *a: False, raising=False)
    after = _graphs(tmp_path / "after")
    still = {(name, src, e.dst) for name, g in after.items() for src, es in g.edges.items() for e in es
             if _sure(e) and (name, src, e.dst) in before}
    assert not still, f"拿掉第 {n} 條後仍確定：{sorted(still)[:3]}"
    assert not _rule_edges(after, n)


def test_c2_nested_function_name_reassigned_in_outer_scope_is_not_certain(tmp_path):
    files = {"app.py": ("def outer():\n    def work():\n        x = 1\n        y = x + 1\n        return y\n\n"
                        "    def inner():\n        work()\n\n    work = lambda: 2\n    inner()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    edges = [(e.dst, _sure(e)) for e in g.edges["app.py::outer.inner"]]
    assert edges == [("app.py::outer.work", False)], "work 在 outer 裡被改指成 lambda：白名單 1 不成立"


def test_c2_closure_over_an_outer_parameter_is_not_certain(tmp_path):
    files = {"app.py": ("def work():\n    x = 1\n    x += 1\n    return x\n\n\n"
                        "def outer(work):\n    def inner():\n        work()\n    inner()\n")}
    g = rp.build_graph(_write(tmp_path, files))
    edges = g.edges["app.py::outer.inner"]
    assert not any(_sure(e) for e in edges), "inner 呼叫的是 outer 的參數，不是模組層的 work"
    assert "app.py::work" not in [e.dst for e in edges], "外層參數沒有來源（outer 沒有呼叫者）：不拿同名的模組函式補邊"
    assert g.unres["app.py::outer.inner"] == 1, "沒有來源就記未解"


WORKER = "class Worker:\n    def run(self):\n        x = 1\n        y = x + 1\n        return y\n"


def test_c1_class_name_rebound_by_a_factory_is_not_certain(tmp_path):
    files = {"app.py": WORKER + "\n\ndef factory():\n    return object\n\n\nWorker = factory()\n\n\n"
                                "def main():\n    w = Worker()\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert not any(_sure(e) for e in g.edges["app.py::main"]), "Worker 被工廠覆寫：建構者名稱不穩定，第 2 條不成立"


def test_c3_constructed_local_stored_to_a_field_is_not_certain(tmp_path):
    files = {"app.py": WORKER + "\n\ndef main(holder):\n    w = Worker()\n    holder.worker = w\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    edges = [(e.dst, _sure(e)) for e in g.edges["app.py::main"]]
    assert edges == [("app.py::Worker.run", False)], "w 存進欄位：第 2 條不成立；沒有宣告型別，也不能轉用第 3 條"


@pytest.mark.parametrize("store", ["    items = [w]\n", "    pool = []\n    pool.append(w)\n", '    d = {"k": w}\n'])
def test_constructed_local_put_into_a_container_is_not_certain(tmp_path, store):
    files = {"app.py": WORKER + "\n\ndef main():\n    w = Worker()\n" + store + "    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    run = [e for e in g.edges["app.py::main"] if e.dst == "app.py::Worker.run"]
    assert run and not any(_sure(e) for e in run), "放進容器也算存走：第 2 條不成立"


def test_c5_annotated_self_field_in_init_is_certain_by_rule_3(tmp_path):
    files = {"app.py": WORKER + "\n\nclass App:\n    def __init__(self, worker):\n        self.worker: Worker = worker\n\n"
                                "    def run(self):\n        self.worker.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert [(e.dst, _sure(e)) for e in g.edges["app.py::App.run"]] == [("app.py::Worker.run", True)], \
        "欄位型別已宣告（self.worker: Worker）、沒有子類覆寫：要連上而且確定"
    assert g.unres["app.py::App.run"] == 0
    assert [_rule_of(e) for e in g.edges["app.py::App.run"]] == [3]


def test_c4_constructor_through_an_import_alias_is_certain_by_rule_2(tmp_path):
    files = {"worker.py": WORKER, "app.py": "from worker import Worker as W\n\n\ndef main():\n    w = W()\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    run = [e for e in g.edges["app.py::main"] if e.dst.endswith("run")]
    assert [(e.dst, _sure(e)) for e in run] == [("worker.py::Worker.run", True)], \
        "W 經 import 別名唯一解析到 worker.Worker，剛 new 的區域變數：確定"
    assert g.unres["app.py::main"] == 0, "W() 建構沒有 __init__ 的類別：不是看不到的呼叫"
    assert [_rule_of(e) for e in run] == [2]


def test_import_alias_annotation_and_reexport_resolve_to_the_original_class(tmp_path):
    files = {"worker.py": WORKER, "pkg.py": "from worker import Worker\n",
             "app.py": "from pkg import Worker as W\n\n\ndef main(w: W):\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert [(e.dst, _sure(e)) for e in g.edges["app.py::main"]] == [("worker.py::Worker.run", True)]
    assert [_rule_of(e) for e in g.edges["app.py::main"]] == [3]


def test_constructor_alias_rebound_in_the_importing_module_is_not_certain(tmp_path):
    files = {"worker.py": WORKER,
             "app.py": "from worker import Worker as W\n\nW = object\n\n\ndef main():\n    w = W()\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert not any(_sure(e) for e in g.edges["app.py::main"])


def test_json_steps_carry_the_rule_number(tmp_path):
    root = _write(tmp_path, EX_B)
    out = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--root", str(root), "--entry", "app.py::main", "--json"],
                         capture_output=True, text=True, encoding="utf-8")
    payload = json.loads("\n".join(out.stdout.strip().splitlines()[:-1]))
    route = next(r for r in payload["entries"][0]["routes"] if r["landing"] == "end.py::done")
    assert [s.get("rule") for s in route["steps"]] == [None, 1, 4, 1, 1], "入口那一步沒有條號；之後每一步附憑哪一條確定"


def test_compare_same_numbers_are_undecidable_when_coverage_got_worse(tmp_path):
    old = _write(tmp_path / "old", PY_HOP)
    worse = "def pick():\n    return 1\n\n\ndef done(n):\n    t = n * 2\n    h = pick()\n    h()\n    return t\n"
    new = _write(tmp_path / "new", {**PY_HOP, "end.py": worse})
    res = rp.run_compare(new, str(old), None, "main.py", None)
    row = _row(res, "end.py::done")
    assert _numbers(row["before"])[2] == _numbers(row["after"])[2], "這一列前後拐彎相同"
    assert row["after"]["handoffs"] == row["before"]["handoffs"] + 1, "落到有未解的 done 那一步變成未知，轉手多 1"
    assert row["status"] == "undecidable", "可達範圍內看不到的呼叫變多：沒觀測完整，相同也不能報成不變"


def test_submodule_imported_from_a_package_is_certain_by_rule_1(tmp_path):
    files = {"pkg/__init__.py": "", "pkg/ledger.py": "def write():\n    w = 1\n    w += 1\n    return w\n",
             "app.py": "from pkg import ledger\n\n\ndef main():\n    ledger.write()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert [(e.dst, _sure(e)) for e in g.edges["app.py::main"]] == [("pkg/ledger.py::write", True)], \
        "from pkg import 子模組 是誠實寫法：子模組名只綁定一次"
    assert [_rule_of(e) for e in g.edges["app.py::main"]] == [1]


def test_constructed_self_field_is_found_but_not_certain(tmp_path):
    files = {"app.py": WORKER + "\n\nclass App:\n    def __init__(self):\n        self.worker = Worker()\n\n"
                                "    def run(self):\n        self.worker.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert [(e.dst, _sure(e)) for e in g.edges["app.py::App.run"]] == [("app.py::Worker.run", False)], \
        "self.x = Foo() 是推導的欄位型別（欄位可能被換）：找得到目標，但第 3 條只吃宣告型別"


# ─── 008 codex 初審與自查抓到的：白名單外卻確定（A）、白名單內被誤標（B） ─────────

def _sure_edges(files: dict, fid: str, tmp_path) -> list:
    g = rp.build_graph(_write(tmp_path, files))
    return [(e.dst, _sure(e)) for e in g.edges[fid]]


@pytest.mark.parametrize("store", ["    items = [[w]]\n", "    pairs = [(1, w)]\n", "    v = w\n    holder.x = v\n",
                                   "    items = [x for x in (w,)]\n"])
def test_a_constructed_local_escaping_through_nesting_or_alias_is_not_certain(tmp_path, store):
    files = {"app.py": WORKER + "\n\ndef main(holder):\n    w = Worker()\n" + store + "    w.run()\n"}
    run = [s for d, s in _sure_edges(files, "app.py::main", tmp_path) if d == "app.py::Worker.run"]
    assert run == [False], "巢狀容器、經別名再存走，都算存走：第 2 條不成立"


def test_a_csharp_constructed_local_in_an_array_initializer_is_not_certain(tmp_path):
    cs = ("class Worker {\n    public void Run() { int x = 1; x += 1; x *= 2; }\n}\n"
          "class Program {\n    static void Main() {\n        var w = new Worker();\n        var items = new[] { w };\n"
          "        w.Run();\n    }\n}\n")
    assert _sure_edges({"Program.cs": cs}, "Program.cs::Program.Main", tmp_path) == [("Program.cs::Worker.Run", False)]


def test_a_name_imported_twice_inside_a_function_is_not_certain(tmp_path):
    files = {"a.py": "def work():\n    x = 1\n    x += 1\n    return x\n",
             "b.py": "def work():\n    y = 2\n    y += 1\n    return y\n",
             "app.py": "def main():\n    from a import work\n    from b import work\n    work()\n"}
    assert not any(s for _, s in _sure_edges(files, "app.py::main", tmp_path)), "work 在 main 裡被 import 兩次"


def test_a_nested_function_rebound_through_nonlocal_is_not_certain(tmp_path):
    files = {"app.py": ("def outer():\n    def work():\n        x = 1\n        x += 1\n        return x\n\n"
                        "    def change():\n        nonlocal work\n        work = lambda: 2\n\n"
                        "    def inner():\n        work()\n\n    change()\n    inner()\n")}
    assert _sure_edges(files, "app.py::outer.inner", tmp_path) == [("app.py::outer.work", False)]


def test_a_module_function_reassigned_through_the_module_attribute_is_not_certain(tmp_path):
    files = {"worker.py": "def work():\n    x = 1\n    x += 1\n    return x\n",
             "app.py": "import worker\n\nworker.work = lambda: 2\n\n\ndef main():\n    worker.work()\n"}
    assert _sure_edges(files, "app.py::main", tmp_path) == [("worker.py::work", False)], \
        "模組層名字在別處被 模組.名字 = … 改掉：第 1 條不成立"


def test_a_method_replaced_by_an_instance_or_class_attribute_is_not_certain(tmp_path):
    other = "def other():\n    a = 1\n    a += 1\n    return a\n\n\n"
    method = "    def run(self):\n        q = 1\n        q += 1\n        return q\n"
    own = {"app.py": other + "class App:\n    def __init__(self):\n        self.run = other\n\n" + method
                     + "\n    def go(self):\n        self.run()\n"}
    assert _sure_edges(own, "app.py::App.go", tmp_path / "own") == [("app.py::App.run", False)], "self.run = other 蓋掉方法"
    typed = {"app.py": other + "class Worker:\n    def __init__(self):\n        self.run = other\n\n" + method
                       + "\n\ndef main(w: Worker):\n    w.run()\n"}
    assert _sure_edges(typed, "app.py::main", tmp_path / "typed") == [("app.py::Worker.run", False)]
    local = {"app.py": other + "class Worker:\n" + method + "\n\ndef main():\n    w = Worker()\n    w.run = other\n    w.run()\n"}
    assert ("app.py::Worker.run", True) not in _sure_edges(local, "app.py::main", tmp_path / "local")
    klass = {"app.py": other + "class Worker:\n" + method + "\n\nWorker.run = other\n\n\ndef main():\n    w = Worker()\n    w.run()\n"}
    assert ("app.py::Worker.run", True) not in _sure_edges(klass, "app.py::main", tmp_path / "klass")


def test_a_csharp_local_function_shadowing_a_method_is_not_certain(tmp_path):
    cs = ("class P {\n    static void Work() { int a = 1; a += 1; a *= 2; }\n"
          "    static void Main() {\n        void Work() { int b = 2; b += 1; }\n        Work();\n    }\n}\n")
    assert not any(s for _, s in _sure_edges({"P.cs": cs}, "P.cs::P.Main", tmp_path)), "Main 裡的區域函式 Work 遮住類別方法"


def test_b_module_qualified_constructor_is_certain_by_rule_2(tmp_path):
    files = {"worker.py": WORKER, "app.py": "import worker\n\n\ndef main():\n    w = worker.Worker()\n    w.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    run = [e for e in g.edges["app.py::main"] if e.dst.endswith("run")]
    assert [(e.dst, _sure(e)) for e in run] == [("worker.py::Worker.run", True)]
    assert [_rule_of(e) for e in run] == [2]


def test_b_static_method_through_an_import_alias_is_certain_by_rule_1(tmp_path):
    files = {"worker.py": "class Worker:\n    @staticmethod\n    def run():\n        x = 1\n        x += 1\n        return x\n",
             "app.py": "from worker import Worker as W\n\n\ndef main():\n    W.run()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert [(e.dst, _sure(e), _rule_of(e)) for e in g.edges["app.py::main"]] == [("worker.py::Worker.run", True, 1)]


# ─── 退件 009：四條證據家族規則（每條封住一整類；先驗行為，再驗條號） ─────────

BODY = "    x = 1\n    y = x + 1\n    return y\n"
OTHER_WORK = {"other.py": "def work():\n" + BODY}


def _edge_rules(files: dict, fid: str, tmp_path) -> list:
    g = rp.build_graph(_write(tmp_path, files))
    return [(e.dst, _rule_of(e)) for e in g.edges[fid]]


def test_r1_an_import_inside_the_inner_function_beats_a_nested_def_of_the_outer(tmp_path):
    """案 1：找目標與證明穩定共用同一次作用域查找；inner 自己 import 的 work 才是被呼叫的那個。"""
    files = {**OTHER_WORK, "app.py": ("def outer():\n    def work():\n        x = 1\n        return x\n\n"
                                      "    def inner():\n        from other import work\n        work()\n\n    inner()\n    work()\n")}
    assert _sure_edges(files, "app.py::outer.inner", tmp_path / "a") == [("other.py::work", True)], \
        "inner 裡 from other import work：目標是 other.py::work，不是 outer 的巢狀 def"
    assert _edge_rules(files, "app.py::outer.inner", tmp_path / "b") == [("other.py::work", 1)]
    outer = [(d, s) for d, s in _sure_edges(files, "app.py::outer", tmp_path / "c") if d.endswith("work")]
    assert outer == [("app.py::outer.work", True)], "同名的巢狀 def 與 import、呼叫在外層：仍指巢狀 def"
    assert [r for d, r in _edge_rules(files, "app.py::outer", tmp_path / "d") if d.endswith("work")] == [1]


@pytest.mark.parametrize("decl", ["global work", "nonlocal work"])
def test_r1_global_and_nonlocal_declarations_pick_the_scope(tmp_path, decl):
    """案 5：global work 直接跳模組層（外層同名參數不算）；nonlocal work 跳到最近綁定它的外層（這裡是 outer 的參數）。"""
    files = {"app.py": ("def work():\n" + BODY + "\n\ndef outer(work):\n    def inner():\n        " + decl
                        + "\n        work()\n\n    inner()\n")}
    edges = _sure_edges(files, "app.py::outer.inner", tmp_path / "a")
    if decl.startswith("global"):
        assert edges == [("app.py::work", True)], "模組層唯一的 def work、沒被改指：第 1 條"
        assert _edge_rules(files, "app.py::outer.inner", tmp_path / "b") == [("app.py::work", 1)]
    else:
        assert not any(s for _, s in edges), "nonlocal work 指的是 outer 的參數：裝的東西看不到"


@pytest.mark.parametrize("decl", ["global work", "nonlocal work"])
def test_r1_a_global_or_nonlocal_name_written_in_the_function_is_not_a_simple_alias(tmp_path, decl):
    """global／nonlocal 的名字不是區域變數：在函式裡 work = other 之後 work()，別的函式也能改它，不給第 4 條。"""
    outer = "def outer():\n    def work():\n        return 0\n\n    def change():\n" if decl.startswith("nonlocal") else \
        "def work():\n    return 0\n\n\ndef outer():\n    def change():\n"
    files = {"app.py": ("def other():\n" + BODY + "\n\n" + outer + "        " + decl + "\n        work = other\n"
                        "        work()\n\n    change()\n")}
    assert not any(s for _, s in _sure_edges(files, "app.py::outer.change", tmp_path)), f"{decl}：不是簡單區域別名"


R1_BINDERS = {
    "nested_class": "    class work:\n        pass\n",
    "except_as": "    try:\n        pass\n    except Exception as work:\n        pass\n",
    "match_capture": "    match 1:\n        case work:\n            pass\n",
}


@pytest.mark.parametrize("form", sorted(R1_BINDERS))
def test_r1_every_binding_form_is_seen_by_the_scope_lookup(tmp_path, form):
    """Name 指定以外的綁定（巢狀 class、except … as、match 擷取）也是這一層的綁定：遮住模組層的 work，不能確定連過去。"""
    files = {"app.py": "def work():\n" + BODY + "\n\ndef main():\n" + R1_BINDERS[form] + "    work()\n"}
    assert ("app.py::work", True) not in _sure_edges(files, "app.py::main", tmp_path), f"{form}：main 自己綁了 work"


@pytest.mark.parametrize("decl", ["global", "nonlocal"])
def test_r1_a_global_or_nonlocal_import_rebinding_is_not_stable(tmp_path, decl):
    """global／nonlocal 之後用 import 改綁（不是 Name 指定）：持有那個名字的作用域被改了，不能確定連到原本的 work。"""
    if decl == "global":
        app = ("def work():\n" + BODY + "\n\ndef change():\n    global work\n    from other import work\n\n\n"
               "def main():\n    change()\n    work()\n")
        fid, old = "app.py::main", "app.py::work"
    else:
        app = ("def outer():\n    def work():\n        return 1\n\n    def change():\n        nonlocal work\n"
               "        from other import work\n\n    change()\n    work()\n")
        fid, old = "app.py::outer", "app.py::outer.work"
    assert (old, True) not in _sure_edges({**OTHER_WORK, "app.py": app}, fid, tmp_path), f"{decl}＋import 改綁了 work"


def test_r1_nonlocal_marks_only_the_nearest_binding_scope(tmp_path):
    """nonlocal work 改的是最近持有 work 的那一層（middle）；outer 自己的 work 沒被改，仍是第 1 條。"""
    files = {"app.py": ("def outer():\n    def work():\n" + "    " + BODY.replace("\n    ", "\n        ") + "\n"
                        "    def middle():\n        def work():\n            return 2\n\n        def patch():\n"
                        "            nonlocal work\n            work = None\n\n        patch()\n\n    middle()\n    work()\n")}
    edges = [(d, s) for d, s in _sure_edges(files, "app.py::outer", tmp_path / "a") if d.endswith("work")]
    assert edges == [("app.py::outer.work", True)], "改的是 middle.work，不是 outer.work"
    assert [r for d, r in _edge_rules(files, "app.py::outer", tmp_path / "b") if d.endswith("work")] == [1]


R1_TWIN_IMPORTS = {
    "same": ("from .other import work", "from other import work"),
    "different": ("from .other import work", "from .alt import work"),
    "external": ("from fastlib import work", "from .other import work"),
}


def _twin_import_files(case: str, scope: str) -> dict:
    first, second = R1_TWIN_IMPORTS[case]
    pad = "        " if scope == "function" else "    "
    block = f"try:\n{pad}{first}\nexcept ImportError:\n{pad}{second}\n"
    if scope == "function":
        app = "def main():\n" + "".join("    " + line + "\n" for line in block.splitlines()) + "    work()\n"
    else:
        app = block + "\n\ndef main():\n    work()\n"
    return {"pkg/__init__.py": "", "pkg/other.py": "def work():\n" + BODY, "pkg/alt.py": "def work():\n    return 7\n",
            "pkg/app.py": app}


@pytest.mark.parametrize("scope", ["function", "module"])
@pytest.mark.parametrize("case", sorted(R1_TWIN_IMPORTS))
def test_r1_a_name_imported_several_times_is_stable_only_if_every_import_reaches_the_same_target(tmp_path, case, scope):
    """try/except ImportError 兩種寫法：每一次 import 沿綁定鏈都解析到同一個專案內目標才算唯一解析到（白名單 1）；
    指到不同函式、或一次外部 → 不確定。函式層與模組層同一個判斷。"""
    files = _twin_import_files(case, scope)
    edges = _sure_edges(files, "pkg/app.py::main", tmp_path / "a")
    if case == "same":
        assert edges == [("pkg/other.py::work", True)], f"{scope}：兩次 import 都指到 pkg/other.py::work"
        assert _edge_rules(files, "pkg/app.py::main", tmp_path / "b") == [("pkg/other.py::work", 1)]
    else:
        assert not any(s for _, s in edges), f"{scope}／{case}：兩次 import 指到的不是同一個專案內目標"


R2_USES = {
    "positional": "    use(w)\n",
    "keyword": "    use(item=w)\n",
    "keyword_container": "    holder.update(item=w)\n",
    "chained": "    holder.a = holder.b = w\n",
    "unpack": "    a, b = w, 1\n",
    "list": "    items = [1, w]\n",
    "dict": '    d = {"k": w}\n',
    "return": "    if holder:\n        return w\n",
    "yield": "    if holder:\n        yield w\n",
    "lambda": "    later = lambda: w\n",
    "nested_def": "    def later():\n        return w.run()\n",
    "attr_store": "    w.x = 1\n",
    "attr_read": "    n = w.x\n",
    "del": "    if holder:\n        del w\n        return\n",
    "import_rebind": "    from other import w\n",
    "except_rebind": "    try:\n        pass\n    except Exception as w:\n        pass\n",
}


@pytest.mark.parametrize("use", sorted(R2_USES))
def test_r2_any_use_besides_a_method_call_receiver_loses_rule_2(tmp_path, use):
    """案 2 一整類：建構後 w 的出現只要不是 w.m(…)，就沒有第 2 條的正向證明（不再列舉存走的寫法）。"""
    files = {"app.py": WORKER + "\n\ndef use(item=None):\n    return item\n\n\ndef main(holder):\n    w = Worker()\n"
                                + R2_USES[use] + "    w.run()\n"}
    run = [s for d, s in _sure_edges(files, "app.py::main", tmp_path) if d == "app.py::Worker.run"]
    assert run == [False], f"{use}：w 不只當方法呼叫的接收者，第 2 條不成立"


def test_r2_only_method_calls_on_the_constructed_local_stay_rule_2(tmp_path):
    files = {"app.py": ("class Worker:\n    def a(self):\n        x = 1\n        return x + 1\n\n"
                        "    def b(self):\n        y = 2\n        return y * 2\n\n\n"
                        "def main():\n    w = Worker()\n    w.a()\n    w.b()\n")}
    edges = sorted(_sure_edges(files, "app.py::main", tmp_path / "a"))
    assert edges == [("app.py::Worker.a", True), ("app.py::Worker.b", True)], "只做 w.a()、w.b() 兩次方法呼叫"
    assert sorted(_edge_rules(files, "app.py::main", tmp_path / "b")) == [("app.py::Worker.a", 2), ("app.py::Worker.b", 2)]


def test_r2_csharp_constructed_local_passed_as_an_argument_loses_rule_2(tmp_path):
    worker = "class Worker {\n    public void Run() { int x = 1; x += 1; x *= 2; }\n}\n"
    main = "class Program {\n    static void Use(Worker w) { }\n    static void Main() {\n        var w = new Worker();\n"
    passed = {"Program.cs": worker + main + "        Use(w);\n        w.Run();\n    }\n}\n"}
    run = [s for d, s in _sure_edges(passed, "Program.cs::Program.Main", tmp_path / "a") if d.endswith("Worker.Run")]
    assert run == [False], "w 當引數傳出去：第 2 條不成立"
    calls = {"Program.cs": worker + main + "        w.Run();\n        w?.Run();\n    }\n}\n"}
    assert [r for d, r in _edge_rules(calls, "Program.cs::Program.Main", tmp_path / "b") if d.endswith("Worker.Run")] == [2]


R3_EXTERNAL = {
    "pathlib_from": ("Path", "resolve", "from pathlib import Path\n\n\ndef main(p: Path):\n    p.resolve()\n"),
    "pathlib_module": ("Path", "resolve", "import pathlib\n\n\ndef main(p: pathlib.Path):\n    p.resolve()\n"),
    "typing": ("Mapping", "lookup", "from typing import Mapping\n\n\ndef main(m: Mapping):\n    m.lookup()\n"),
    "third_party": ("Session", "mount", "from requests import Session\n\n\ndef main(s: Session):\n    s.mount()\n"),
    "third_party_ctor": ("Session", "mount", "from requests import Session\n\n\ndef main():\n    s = Session()\n    s.mount()\n"),
}


@pytest.mark.parametrize("case", sorted(R3_EXTERNAL))
def test_r3_a_type_bound_outside_the_project_never_links_to_a_same_name_project_class(tmp_path, case):
    """案 3 一整類：標註、建構者沿綁定鏈指到專案外（標準庫、typing、第三方）→ 外部；不連到同名的專案類別，連候選都不連。"""
    cls, method, app = R3_EXTERNAL[case]
    files = {"other.py": f"class {cls}:\n    def {method}(self):\n        x = 1\n        return x + 1\n", "app.py": app}
    g = rp.build_graph(_write(tmp_path, files))
    assert f"other.py::{cls}.{method}" not in [e.dst for e in g.edges["app.py::main"]], f"{case}：連到了同名的專案類別"
    assert g.unres["app.py::main"] == 0, "型別確知在專案外：不是看不到的呼叫"


def test_r3_reexport_through_the_binding_chain_stays_rule_3_despite_a_same_name_decoy(tmp_path):
    files = {"worker.py": WORKER, "other.py": WORKER, "pkg.py": "from worker import Worker\n",
             "app.py": "from pkg import Worker\n\n\ndef main(w: Worker):\n    w.run()\n"}
    assert _sure_edges(files, "app.py::main", tmp_path / "a") == [("worker.py::Worker.run", True)], \
        "沿 import 鏈＋re-export 解析到 worker.Worker，不是同名的 other.Worker"
    assert _edge_rules(files, "app.py::main", tmp_path / "b") == [("worker.py::Worker.run", 3)]


R3_PREFIXED = {
    "string_external": ('import pathlib\n\n\nclass Path:\n    def resolve(self):\n        return 1\n\n\n'
                        'def main(p: "pathlib.Path"):\n    p.resolve()\n', "app.py::main", "app.py::Path.resolve"),
    "dotted_base": ("import collections\n\n\nclass UserDict:\n    def clear(self):\n        return 1\n\n\n"
                    "class Child(collections.UserDict):\n    def run(self):\n        return super().clear()\n",
                    "app.py::Child.run", "app.py::UserDict.clear"),
}


@pytest.mark.parametrize("case", sorted(R3_PREFIXED))
def test_r3_a_module_prefixed_external_type_or_base_never_links_to_a_same_name_project_class(tmp_path, case):
    """字串標註 "pathlib.Path"、父類 collections.UserDict：模組前綴保留下來沿綁定鏈解析，指到專案外就不連同名的專案類別。"""
    app, fid, decoy = R3_PREFIXED[case]
    g = rp.build_graph(_write(tmp_path, {"app.py": app}))
    assert decoy not in [e.dst for e in g.edges[fid]], f"{case}：連到了同名的專案類別"


def test_r3_a_module_prefixed_string_annotation_to_a_project_class_is_rule_3(tmp_path):
    files = {"worker.py": WORKER, "app.py": 'import worker\n\n\ndef main(w: "worker.Worker"):\n    w.run()\n'}
    assert _sure_edges(files, "app.py::main", tmp_path / "a") == [("worker.py::Worker.run", True)], \
        "字串標註 \"worker.Worker\" 沿 import worker 解析到專案內的類別"
    assert _edge_rules(files, "app.py::main", tmp_path / "b") == [("worker.py::Worker.run", 3)]


def test_r3_a_same_name_class_found_only_by_project_wide_search_is_a_candidate(tmp_path):
    files = {"other.py": WORKER, "app.py": "def main(w: Worker):\n    w.run()\n"}
    assert _sure_edges(files, "app.py::main", tmp_path) == [("other.py::Worker.run", False)], \
        "Worker 沒有匯入：退回全專案同名搜尋只能給候選"


R4_STATIC = "class Worker:\n    @staticmethod\n    def run():\n        x = 1\n        return x + 1\n"
R4_OTHER = "\n\ndef other():\n    a = 1\n    return a + 2\n"
R4_REWRITES = {
    "class_attr": R4_STATIC + R4_OTHER + "\n\nWorker.run = other\n\n\ndef main():\n    Worker.run()\n",
    "self_attr": ("class Worker:\n    def __init__(self):\n        self.run = other\n\n    def run(self):\n        x = 1\n"
                  "        return x + 1\n" + R4_OTHER + "\n\ndef main():\n    w = Worker()\n    w.run()\n"),
    "instance_attr": R4_STATIC + R4_OTHER + "\n\ndef patch(x):\n    x.run = other\n\n\ndef main():\n    w = Worker()\n    w.run()\n",
    "setattr": R4_STATIC + R4_OTHER + '\n\nsetattr(Worker, "run", other)\n\n\ndef main():\n    Worker.run()\n',
    "other_class_body": R4_STATIC + R4_OTHER + "\n\nclass Patch:\n    Worker.run = other\n\n\ndef main():\n    Worker.run()\n",
    "other_class_body_setattr": (R4_STATIC + R4_OTHER + '\n\nclass Patch:\n    setattr(Worker, "run", other)\n\n\n'
                                 "def main():\n    Worker.run()\n"),
}


@pytest.mark.parametrize("form", sorted(R4_REWRITES))
def test_r4_a_rewritten_method_binding_is_not_certain_under_any_rule(tmp_path, form):
    """案 4 一整類：類別.方法 = …、self.方法 = …、實例.方法 = …（型別看不出 → 同名方法都算）、setattr(類別, "方法", …)；
    第 1 條的「類別.靜態方法」與第 2、3 條在 certify 用同一個檢查。"""
    run = [s for d, s in _sure_edges({"app.py": R4_REWRITES[form]}, "app.py::main", tmp_path) if d == "app.py::Worker.run"]
    assert run == [False], f"{form}：方法在類別上的綁定被改寫，不能給條號"


def test_r4_an_unrewritten_static_method_stays_rule_1(tmp_path):
    plain = {"app.py": R4_STATIC + "\n\ndef main():\n    Worker.run()\n"}
    assert _sure_edges(plain, "app.py::main", tmp_path / "a") == [("app.py::Worker.run", True)]
    assert _edge_rules(plain, "app.py::main", tmp_path / "b") == [("app.py::Worker.run", 1)]
    typed = {"app.py": R4_STATIC + ("\n\nclass Other:\n    def run(self):\n        return 3\n\n\n"
                                    "def patch(x: Other):\n    x.run = None\n\n\ndef main():\n    Worker.run()\n")}
    assert _edge_rules(typed, "app.py::main", tmp_path / "c") == [("app.py::Worker.run", 1)], \
        "實例型別看得出（標註 Other）：只算 Other 的 run 被改寫，Worker.run 不受影響"


def test_r4_a_rewrite_of_a_same_name_class_in_another_module_does_not_touch_this_one(tmp_path):
    """方法改寫以類別身分（定義檔＋名字）記：b.Worker.run 被改，不影響沿綁定鏈確知的 a.Worker.run。"""
    files = {"a.py": R4_STATIC, "b.py": R4_STATIC + "\n\nWorker.run = None\n",
             "app.py": "from a import Worker\n\n\ndef main():\n    Worker.run()\n"}
    assert _sure_edges(files, "app.py::main", tmp_path / "a") == [("a.py::Worker.run", True)]
    assert _edge_rules(files, "app.py::main", tmp_path / "b") == [("a.py::Worker.run", 1)]


# ─── 退件 011：總原則（證明只在模型涵蓋的範圍內成立；碰到模型沒建的語法構件，該證明就不成立） ─────────

TWO_FUNCS = "def work():\n" + BODY + "\n\ndef other():\n" + BODY + "\n\n"
APP_RUN = WORKER + "\n\nclass App:\n    def run(self):\n        q = 1\n        return q + 1\n\n"


def test_p1_case1_lambda_parameter_shadows_the_module_function(tmp_path):
    """案 1：(lambda work: work())(other)：lambda 參數 work 遮住模組層的 work，實際呼叫的是 other。
    呼叫點在 lambda 裡（模型沒建那一層）→ 不給條號；名字是 lambda 自己的參數 → 不退回同名的模組函式，記未解。"""
    files = {"app.py": TWO_FUNCS + "def main():\n    return (lambda work: work())(other)\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert not any(_sure(e) for e in g.edges["app.py::main"]), "lambda 裡的呼叫不能確定"
    assert "app.py::work" not in [e.dst for e in g.edges["app.py::main"]], "lambda 參數 work 不是模組層的 work"
    assert g.unres["app.py::main"] == 1, "lambda 參數裝的東西看不到：記未解"


P1_CONSTRUCTS = {   # 構件 → (app.py, 呼叫所在函式, b1be2c0 照外層綁定給了條號的目標)
    "lambda": (TWO_FUNCS + "def main():\n    fn = work\n    return (lambda fn: fn())(other)\n", "app.py::main", "app.py::work"),
    "generator": (APP_RUN + "    def go(self):\n        return list(self.run() for self in [Worker()])\n",
                  "app.py::App.go", "app.py::App.run"),
    "comprehension": (APP_RUN + "    def go(self):\n        return [self.run() for self in [Worker()]]\n",
                      "app.py::App.go", "app.py::App.run"),
    "class_body": (TWO_FUNCS + "def main():\n    class Patch:\n        global work\n        work = other\n\n    work()\n",
                   "app.py::main", "app.py::work"),
}


@pytest.mark.parametrize("construct", sorted(P1_CONSTRUCTS))
def test_p1_a_binding_made_inside_an_unmodeled_scope_construct_never_gets_a_rule(tmp_path, construct):
    """總原則 1 四種構件各一反例：lambda 參數遮住別名 fn（實際呼叫 other）、生成器／推導式的迴圈變數改綁 self
    （實際呼叫 Worker.run）、類別本體裡 global 改綁模組層的 work。模型沒建這些構件的參數與綁定，照外層的綁定給條號就錯了。"""
    app, fid, wrong = P1_CONSTRUCTS[construct]
    assert (wrong, True) not in _sure_edges({"app.py": app}, fid, tmp_path / "a"), f"{construct}：連到 {wrong} 還確定"
    assert all(r is None for d, r in _edge_rules({"app.py": app}, fid, tmp_path / "b") if d == wrong)


P1_PROOF_TOUCHES = {
    "call_in_generator": "    return sum(work() for _ in range(2))\n",
    "call_in_comprehension": "    return [work() for _ in range(2)]\n",
    "call_in_lambda": "    later = lambda: work()\n    return later\n",
    "name_bound_as_lambda_param": "    later = lambda work: work\n    work()\n    return later\n",
}


@pytest.mark.parametrize("form", sorted(P1_PROOF_TOUCHES))
def test_p1_a_call_or_the_proven_name_inside_a_construct_gets_no_rule_1(tmp_path, form):
    """總原則 1 的另一半：呼叫點在 lambda／生成器／推導式裡，或被證明的名字 work 在構件裡被綁定（這裡是 lambda 參數），
    就算這次語意上剛好對，證明也只在模型涵蓋的範圍內成立：找得到 work，但第 1 條不給。"""
    files = {"app.py": TWO_FUNCS + "def main():\n" + P1_PROOF_TOUCHES[form]}
    edges = [(d, s) for d, s in _sure_edges(files, "app.py::main", tmp_path) if d == "app.py::work"]
    assert edges == [("app.py::work", False)], f"{form}：找得到 work，但不能確定"


P1_ALIAS = {
    "bound_as_lambda_param": "    fn = work\n    later = lambda fn: fn\n    fn()\n    return later\n",
    "class_body_nonlocal": "    fn = work\n\n    class Patch:\n        nonlocal fn\n        fn = other\n\n    fn()\n",
    "inner_nonlocal": "    fn = work\n\n    def change():\n        nonlocal fn\n        fn = other\n\n    change()\n    fn()\n",
}


@pytest.mark.parametrize("form", sorted(P1_ALIAS))
def test_p1_a_simple_alias_touched_outside_the_model_is_not_rule_4(tmp_path, form):
    """第 4 條（簡單區域別名）：別名 fn 在 lambda 裡被綁定成參數、在巢狀類別本體裡用 nonlocal 改綁、或被內層函式用
    nonlocal 改綁（同一家族：被證明的名字在這一層以外被綁定）→ 不給第 4 條。"""
    files = {"app.py": TWO_FUNCS + "def main():\n" + P1_ALIAS[form]}
    assert ("app.py::work", True) not in _sure_edges(files, "app.py::main", tmp_path / "a"), f"{form}：fn 不只這一層能動"
    assert all(r is None for d, r in _edge_rules(files, "app.py::main", tmp_path / "b") if d == "app.py::work")


def test_p1_a_class_body_nonlocal_two_levels_out_still_unsettles_the_nested_def(tmp_path):
    """patch 裡的類別本體 nonlocal work：改的是 outer 的巢狀 def work（patch 自己沒綁）→ outer 裡的 work() 不給第 1 條。"""
    files = {"app.py": ("def outer():\n    def work():\n" + "    " + BODY.replace("\n    ", "\n        ") + "\n"
                        "    def patch():\n        class K:\n            nonlocal work\n            work = None\n\n"
                        "    patch()\n    work()\n")}
    edges = [(d, s) for d, s in _sure_edges(files, "app.py::outer", tmp_path) if d.endswith("work")]
    assert edges == [("app.py::outer.work", False)], "outer.work 被 patch 裡的類別本體改綁了"


def test_p1_a_callback_called_inside_a_lambda_gets_no_rule_5(tmp_path):
    """呼叫點在 lambda 裡的 callback：參數被 lambda 遮住 → 看不到（記未解）；沒被遮住 → 沿呼叫者列候選，不給第 5 條。"""
    shadow = {"app.py": TWO_FUNCS + "def run(cb):\n    return (lambda cb: cb())(other)\n\n\ndef main():\n    run(work)\n"}
    g = rp.build_graph(_write(tmp_path / "a", shadow))
    assert "app.py::work" not in [e.dst for e in g.edges.get("app.py::run", [])], "lambda 參數 cb 不是 run 的 cb"
    plain = {"app.py": TWO_FUNCS + "def run(cb):\n    later = lambda: cb()\n    return later()\n\n\ndef main():\n    run(work)\n"}
    assert _sure_edges(plain, "app.py::run", tmp_path / "b") == [("app.py::work", False)], "呼叫點在 lambda 裡：只列候選"


def test_p1_a_certain_call_site_is_not_masked_by_an_earlier_one_inside_a_construct(tmp_path):
    """反方向：同一來源到同一目標有好幾處呼叫，推導式裡那處（不給條號）寫在前面，外面那處照第 3 條確定 →
    邊留確定的那條（確定與否不看呼叫點的先後）。"""
    files = {"app.py": APP_RUN + "    def go(self):\n        items = [self.run() for _ in range(2)]\n        self.run()\n"
                                 "        return items\n"}
    assert _edge_rules(files, "app.py::App.go", tmp_path) == [("app.py::App.run", 3)]


P1_READ_ONLY = {   # 構件裡只讀被證明的名字（讀取不改變外層綁定）→ 條號照給
    "module_read_in_comprehension": ("    names = [kit.func for _ in range(2)]\n    kit.func()\n    return names\n",
                                     "kit.py::func", 1),
    "name_read_in_comprehension": ("    names = [work for _ in range(2)]\n    work()\n    return names\n", "app.py::work", 1),
    "name_read_in_class_body": ("    class Holder:\n        fn = work\n\n    work()\n    return Holder\n", "app.py::work", 1),
    "alias_read_in_lambda": ("    fn = work\n    later = lambda: fn\n    fn()\n    return later\n", "app.py::work", 4),
}


@pytest.mark.parametrize("form", sorted(P1_READ_ONLY))
def test_p1_a_name_only_read_inside_a_construct_keeps_its_rule(tmp_path, form):
    """總控台裁定（反方向）：推導式、類別本體、lambda 裡只「讀」被證明的名字（模組名 kit、函式 work、別名 fn），
    不改變外層的綁定 → 外面的 kit.func()、work() 照給第 1 條，fn() 照給第 4 條。"""
    body, target, rule = P1_READ_ONLY[form]
    files = {"kit.py": "def func():\n" + BODY, "app.py": "import kit\n\n\n" + TWO_FUNCS + "def main():\n" + body}
    assert (target, rule) in _edge_rules(files, "app.py::main", tmp_path), f"{form}：只讀不改綁定，條號要照給"


def test_p1_a_walrus_inside_a_comprehension_rebinds_the_outer_name(tmp_path):
    """總控台裁定（正面）：推導式裡的 (work := other) 綁在外層函式作用域，work 已不是模組層的 work → 外面的 work() 不給條號。"""
    files = {"app.py": TWO_FUNCS + "def main():\n    names = [(work := other) for _ in range(2)]\n    work()\n    return names\n"}
    assert ("app.py::work", True) not in _sure_edges(files, "app.py::main", tmp_path / "a"), "work 被 := 改綁成 other"
    assert all(r is None for d, r in _edge_rules(files, "app.py::main", tmp_path / "b") if d.endswith("work"))


def test_p1_constructs_that_do_not_touch_the_proven_name_keep_rule_1(tmp_path):
    """反方向：構件裡沒讀到、沒綁定 work，外面的 work() 照樣是第 1 條（不因為函式裡有 lambda／推導式就整個降級）。"""
    files = {"app.py": TWO_FUNCS + "def main():\n    items = [x for x in range(3)]\n    key = lambda x: x\n    work()\n"
                                   "    return items, key\n"}
    assert [r for d, r in _edge_rules(files, "app.py::main", tmp_path) if d == "app.py::work"] == [1]


P2_CAPTURES = {   # 建構變數 w 的某一次出現在推導式／生成器裡（被那一層捕捉）；外面那次 w.run() 寫在前面，邊就是它的
    "case2_generator": "    pending = (w.run() for _ in range(2))\n    w.run()\n    return pending\n",
    "generator_after": "    w.run()\n    pending = (w.run() for _ in range(2))\n    return pending\n",
    "list_comprehension": "    w.run()\n    return [w.run() for _ in range(2)]\n",
    "set_comprehension": "    w.run()\n    return {w.run() for _ in range(2)}\n",
    "dict_comprehension": "    w.run()\n    return {k: w.run() for k in range(2)}\n",
}


@pytest.mark.parametrize("form", sorted(P2_CAPTURES))
def test_p2_a_constructed_local_captured_by_a_generator_or_comprehension_loses_rule_2(tmp_path, form):
    """案 2＋總原則 2：建構後 w 只要有一次出現在巢狀作用域（生成器、推導式）裡就算被捕捉，就算那次也只是 w.run()，
    外面的 w.run() 也不給第 2 條（生成器延後執行、把 w 帶出去）。"""
    files = {"app.py": WORKER + "\n\ndef main():\n    w = Worker()\n" + P2_CAPTURES[form]}
    run = [s for d, s in _sure_edges(files, "app.py::main", tmp_path) if d == "app.py::Worker.run"]
    assert run == [False], f"{form}：w 被巢狀作用域捕捉，第 2 條不成立"


def test_p3_case3_a_body_import_does_not_retarget_a_parameter_annotation(tmp_path):
    """案 3：參數標註 Path 在 def 的外層（模組層）求值＝pathlib.Path（外部）；函式本體裡的 from other import Path 不改它。"""
    files = {"other.py": "class Path:\n    def resolve(self):\n        x = 1\n        return x + 1\n",
             "app.py": "from pathlib import Path\n\n\ndef main(p: Path):\n    from other import Path\n    return p.resolve()\n"}
    g = rp.build_graph(_write(tmp_path, files))
    assert "other.py::Path.resolve" not in [e.dst for e in g.edges["app.py::main"]], "標註指到 pathlib.Path，不連專案的 Path"
    assert g.unres["app.py::main"] == 0, "型別確知在專案外：不是看不到的呼叫"


def test_p3_case5_a_same_name_parameter_does_not_hide_the_annotation(tmp_path):
    """案 5（正例）：def main(p: Worker, Worker)：標註在外層解析到模組層的 class Worker；同名參數只在本體裡遮住 → 第 3 條。"""
    files = {"app.py": WORKER + "\n\ndef main(p: Worker, Worker):\n    return p.run()\n"}
    assert _sure_edges(files, "app.py::main", tmp_path / "a") == [("app.py::Worker.run", True)]
    assert _edge_rules(files, "app.py::main", tmp_path / "b") == [("app.py::Worker.run", 3)]


P3_CLASS_BODY = {   # 方法的參數標註在類別本體求值：類別本體也綁了 Worker
    "class_attribute": "    Worker = Other\n\n",
    "class_import": "    from other import Worker\n\n",
}


@pytest.mark.parametrize("form", sorted(P3_CLASS_BODY))
def test_p3_a_method_annotation_name_bound_in_the_class_body_is_not_rule_3(tmp_path, form):
    """標註同名區域綁定（反例）：方法的參數標註在類別本體求值，類別本體裡的 Worker（類別屬性、import）遮住模組層的
    Worker，實際是 Other／other.Worker → 不給第 3 條。"""
    app = WORKER + "\n\nclass Other:\n    def run(self):\n        return 3\n\n\nclass App:\n" + P3_CLASS_BODY[form] + \
        "    def go(self, w: Worker):\n        w.run()\n"
    files = {"other.py": WORKER, "app.py": app}
    assert ("app.py::Worker.run", True) not in _sure_edges(files, "app.py::App.go", tmp_path / "a"), f"{form}：標註不是模組層的 Worker"
    assert all(r is None for d, r in _edge_rules(files, "app.py::App.go", tmp_path / "b") if d.endswith("Worker.run"))


def test_p3_a_nested_function_parameter_annotation_resolves_in_the_enclosing_scope(tmp_path):
    """標註在外層正確解析（正例）：inner 的參數標註 Worker 在 outer 求值＝模組層的 Worker；inner 本體裡的
    from other import Worker 只影響本體 → 連 app.py::Worker.run、第 3 條。"""
    files = {"other.py": WORKER, "app.py": WORKER + "\n\ndef outer(x):\n    def inner(w: Worker):\n        from other import Worker\n"
                                           "        return w.run()\n\n    return inner(x)\n"}
    assert _sure_edges(files, "app.py::outer.inner", tmp_path / "a") == [("app.py::Worker.run", True)]
    assert _edge_rules(files, "app.py::outer.inner", tmp_path / "b") == [("app.py::Worker.run", 3)]


def test_p3_a_field_annotation_in_a_method_body_resolves_in_that_body(tmp_path):
    """函式本體裡的區域標註在本體解析：__init__ 裡 from other import Worker 之後的 self.worker: Worker 是 other.py 的 Worker。"""
    files = {"other.py": WORKER, "app.py": WORKER + "\n\nclass App:\n    def __init__(self, worker):\n        from other import Worker\n"
                                           "        self.worker: Worker = worker\n\n    def go(self):\n        self.worker.run()\n"}
    assert _sure_edges(files, "app.py::App.go", tmp_path / "a") == [("other.py::Worker.run", True)]
    assert _edge_rules(files, "app.py::App.go", tmp_path / "b") == [("other.py::Worker.run", 3)]


def test_p3_a_parameter_default_resolves_in_the_enclosing_scope(tmp_path):
    """參數預設值跟參數標註一樣在 def 的外層求值：inner(cb=work) 的 work 是 outer 的巢狀 def，不是模組層的 work。"""
    files = {"app.py": "def work():\n" + BODY + "\n\ndef outer():\n    def work():\n        q = 2\n        return q * 2\n\n"
                       "    def inner(cb=work):\n        return cb()\n\n    return inner()\n"}
    edges = _sure_edges(files, "app.py::outer.inner", tmp_path / "a")
    assert "app.py::work" not in [d for d, _ in edges], "預設值 work 是 outer 的巢狀 def，不是模組層的 work"
    assert _edge_rules(files, "app.py::outer.inner", tmp_path / "b") == [("app.py::outer.work", 5)]


P4_REBOUND_WRITES = {   # 接收者的型別標註（pathlib.Path，外部）在寫入前就失效了：p 指的其實是 Worker
    "case4_param": "def change(p: Path):\n    p = Worker\n    p.run = other\n",
    "annotated_local": "def change(source):\n    p: Path = source\n    p = Worker\n    p.run = other\n",
    "nonlocal_param": "def change(p: Path):\n    def g():\n        nonlocal p\n        p = Worker\n\n    g()\n    p.run = other\n",
    "import_rebind": "def change(p: Path):\n    from kit import Worker as p\n    p.run = other\n",
    "nested_default_walrus": ("def change(p: Path):\n    def inner(x=[(p := Worker) for _ in (0,)]):\n        return x\n\n"
                              "    p.run = other\n"),
}


@pytest.mark.parametrize("form", sorted(P4_REBOUND_WRITES))
def test_p4_a_write_through_a_rebound_receiver_counts_as_a_possible_method_rewrite(tmp_path, form):
    """案 4＋總原則 4：參數或區域變數被重新指定過（任何一次，含內層 nonlocal），它的型別證據就失效；之後經它寫的
    p.run = other 照「接收者型別看不出」用名字保守記成可能改寫 → 別處 Worker().run() 不給條號。"""
    app = ("from pathlib import Path\n\n\n" + WORKER + "\n\ndef other(self):\n    return 2\n\n\n" + P4_REBOUND_WRITES[form]
           + "\n\ndef main():\n    w = Worker()\n    return w.run()\n")
    run = [s for d, s in _sure_edges({"app.py": app}, "app.py::main", tmp_path) if d == "app.py::Worker.run"]
    assert run == [False], f"{form}：p 已不是 Path，p.run = other 可能改寫了 Worker.run"


def test_p4_a_write_through_an_external_receiver_that_was_never_rebound_does_not_touch_project_methods(tmp_path):
    """反方向：p: Path 沒被重新指定，p.run = … 寫的是外部型別的屬性，不影響專案的 Worker.run（仍是第 2 條）。"""
    app = ("from pathlib import Path\n\n\n" + WORKER + "\n\ndef touch(p: Path):\n    p.run = None\n\n\n"
           "def main():\n    w = Worker()\n    return w.run()\n")
    assert [r for d, r in _edge_rules({"app.py": app}, "app.py::main", tmp_path) if d == "app.py::Worker.run"] == [2]


P4_REBOUND_RECEIVERS = {   # 宣告型別（第 3 條的證據）在呼叫前被改掉
    "nonlocal_param": ("def main(w: Worker):\n    def g():\n        nonlocal w\n        w = Other()\n\n    g()\n    w.run()\n",
                       "app.py::main", "app.py::Worker.run"),
    "self_reassigned": ("class App:\n    def run(self):\n        q = 1\n        return q + 1\n\n"
                        "    def go(self):\n        self = Other()\n        self.run()\n", "app.py::App.go", "app.py::App.run"),
}


@pytest.mark.parametrize("form", sorted(P4_REBOUND_RECEIVERS))
def test_p4_a_rebound_receiver_loses_its_declared_type(tmp_path, form):
    """總原則 4 對第 3 條：參數 w 被內層 nonlocal 改成 Other()、self 被重新指定：宣告的型別不再是證據，不給第 3 條。"""
    body, fid, wrong = P4_REBOUND_RECEIVERS[form]
    app = WORKER + "\n\nclass Other:\n    def run(self):\n        return 3\n\n\n" + body
    assert (wrong, True) not in _sure_edges({"app.py": app}, fid, tmp_path / "a"), f"{form}：接收者已被改指"
    assert all(r is None for d, r in _edge_rules({"app.py": app}, fid, tmp_path / "b") if d == wrong)


CLOSURE_PARAM = TWO_FUNCS + "def outer(work):\n    def inner():\n        return work()\n\n    return inner()\n"


def test_closure_over_an_outer_parameter_follows_what_the_outer_callers_pass(tmp_path):
    """閉包疑點（有來源）：inner 呼叫 outer 的參數 work；outer 的呼叫者傳 other → 沿來源列候選 other，不連同名的模組 work。"""
    g = rp.build_graph(_write(tmp_path, {"app.py": CLOSURE_PARAM + "\n\ndef main():\n    outer(other)\n"}))
    assert [(e.dst, _sure(e)) for e in g.edges["app.py::outer.inner"]] == [("app.py::other", False)], \
        "沿外層的呼叫者列候選；閉包不給條號"
    assert g.unres["app.py::outer.inner"] == 0


def test_closure_over_an_outer_parameter_without_a_source_is_unresolved(tmp_path):
    """閉包疑點（沒來源）：outer 沒有呼叫者、參數也沒預設值 → 記未解，不用同名的模組函式 work 補邊。"""
    g = rp.build_graph(_write(tmp_path, {"app.py": CLOSURE_PARAM}))
    assert "app.py::work" not in [e.dst for e in g.edges.get("app.py::outer.inner", [])], "同名不是來源證據"
    assert g.unres["app.py::outer.inner"] == 1


@pytest.mark.parametrize("assign", ["    work = other\n", "    work = pick()\n"])
def test_closure_over_an_outer_local_follows_its_assignment_or_is_unresolved(tmp_path, assign):
    """外層區域變數（閉包）同一套：outer 裡 work = other → 沿外層的指定列候選 other；work = pick()（算出來的）→ 記未解；
    兩種都不連同名的模組 work。"""
    app = TWO_FUNCS + "def pick():\n    return other\n\n\ndef outer():\n" + assign + \
        "\n    def inner():\n        return work()\n\n    return inner()\n"
    g = rp.build_graph(_write(tmp_path, {"app.py": app}))
    edges = [(e.dst, _sure(e)) for e in g.edges.get("app.py::outer.inner", [])]
    assert ("app.py::work", False) not in edges, "同名的模組 work 不是外層區域變數的來源"
    if "other" in assign:
        assert edges == [("app.py::other", False)]
    else:
        assert edges == [] and g.unres["app.py::outer.inner"] == 1


def test_p4_self_and_cls_count_only_when_they_are_the_methods_own_first_parameter(tmp_path):
    """self.m()／cls.m() 的接收者要真的是方法自己的第一個參數：區域變數剛好叫 cls（cls = Worker()）時 cls.run() 是
    Worker.run（第 2 條），不是本類別的 run；反過來，方法裡有個叫 cls 的區域變數不影響 self.run() 的第 3 條。"""
    local = {"app.py": APP_RUN + "    def go(self):\n        cls = Worker()\n        return cls.run()\n"}
    assert _edge_rules(local, "app.py::App.go", tmp_path / "a") == [("app.py::Worker.run", 2)]
    mixed = {"app.py": APP_RUN + "    def go(self, x):\n        cls = x\n        cls = cls or None\n        return self.run()\n"}
    assert _edge_rules(mixed, "app.py::App.go", tmp_path / "b") == [("app.py::App.run", 3)]


def test_p4_a_callback_parameter_rebound_through_nonlocal_is_not_rule_5(tmp_path):
    """總原則 4 對第 5 條：callback 參數 cb 被內層函式用 nonlocal 改成 other，呼叫者傳的 work 不一定是這次跑的 → 只列候選。"""
    app = TWO_FUNCS + ("def run(cb):\n    def g():\n        nonlocal cb\n        cb = other\n\n    g()\n    return cb()\n\n\n"
                       "def main():\n    run(work)\n")
    assert ("app.py::work", True) not in _sure_edges({"app.py": app}, "app.py::run", tmp_path), "cb 已被內層改掉"


def test_closure_over_an_outer_parameter_rebound_in_the_outer_lists_both_sources(tmp_path):
    """閉包疑點（外層改指）：outer 裡 work = other 之後 inner 呼叫 work → 外層改指的 other 與呼叫者傳的 work 都列候選。"""
    app = TWO_FUNCS + ("def outer(work):\n    work = other\n\n    def inner():\n        return work()\n\n    return inner()\n\n\n"
                       "def main():\n    outer(work)\n")
    edges = sorted(_sure_edges({"app.py": app}, "app.py::outer.inner", tmp_path))
    assert edges == [("app.py::other", False), ("app.py::work", False)], "兩個來源都只是候選"


# ─── 第七輪（codex 審 012）：def／class 定義時在外層求值的運算式算外層，本體才跳過 ─────────

DECO = "def deco(_):\n    return lambda f: f\n\n\n"
P7_DEF_TIME = {   # main 裡定義巢狀 def／class 時就執行的運算式把 work 綁成 other；main 的 work() 實際呼叫 other
    "default_comprehension": "    def inner(x=[(work := other) for _ in (0,)]):\n        return x\n\n",
    "default": "    def inner(x=(work := other)):\n        return x\n\n",
    "kwonly_default": "    def inner(*, x=(work := other)):\n        return x\n\n",
    "decorator": "    @deco(work := other)\n    def inner():\n        return 1\n\n",
    "annotation": "    def inner(x: (work := other)):\n        return x\n\n",
    "return_annotation": "    def inner() -> (work := other):\n        return 1\n\n",
    "class_base": "    class K(object if (work := other) else object):\n        pass\n\n",
    "class_keyword": "    class K(metaclass=type if (work := other) else type):\n        pass\n\n",
    "class_decorator": "    @deco(work := other)\n    class K:\n        pass\n\n",
}


@pytest.mark.parametrize("form", sorted(P7_DEF_TIME))
def test_p7_a_binding_in_a_definition_time_expression_belongs_to_the_outer_scope(tmp_path, form):
    """codex 第 2 項一整類：巢狀 def 的預設值（含推導式裡的 :=）、只限關鍵字預設值、裝飾器、參數與回傳標註，
    巢狀 class 的父類、keywords、裝飾器，都在 main 定義它的當下於 main 求值，裡面的綁定是 main 的綁定 → work() 不給條號。"""
    files = {"app.py": DECO + TWO_FUNCS + "def main():\n" + P7_DEF_TIME[form] + "    return work()\n"}
    assert ("app.py::work", True) not in _sure_edges(files, "app.py::main", tmp_path / "a"), f"{form}：work 已被改綁成 other"
    assert all(r is None for d, r in _edge_rules(files, "app.py::main", tmp_path / "b") if d.endswith("::work"))


def test_p7_a_binding_in_a_module_level_default_rebinds_the_module_name(tmp_path):
    """模組層 def 的預設值在模組層求值：def setup(x=(work := other)) 把模組層的 work 綁成 other → main 的 work() 不給條號。"""
    files = {"app.py": TWO_FUNCS + "def setup(x=(work := other)):\n    return x\n\n\ndef main():\n    return work()\n"}
    assert ("app.py::work", True) not in _sure_edges(files, "app.py::main", tmp_path / "a")
    assert all(r is None for d, r in _edge_rules(files, "app.py::main", tmp_path / "b") if d.endswith("::work"))


def test_p7_a_sibling_default_rebinding_the_annotation_name_is_not_rule_3(tmp_path):
    """codex 第 4 項：setup 的預設值在 main 裡把 Worker 綁成 Other；inner 的參數標註在 main 解析＝Other → 不給第 3 條。"""
    app = WORKER + ("\n\nclass Other:\n    def run(self):\n        return 2\n\n\ndef main():\n"
                    "    def setup(x=[(Worker := Other) for _ in (0,)]):\n        return x\n\n"
                    "    def inner(p: Worker):\n        return p.run()\n\n    return inner(Other())\n")
    assert ("app.py::Worker.run", True) not in _sure_edges({"app.py": app}, "app.py::main.inner", tmp_path / "a")
    assert all(r is None for d, r in _edge_rules({"app.py": app}, "app.py::main.inner", tmp_path / "b") if d.endswith("run"))


def test_p7_a_default_rebinding_the_nested_def_is_not_rule_5(tmp_path):
    """codex 第 7 項：setup 的預設值把 main 的巢狀 def work 改綁成 other；inner(cb=work) 的預設值存的是 other → 不給第 5 條。"""
    app = ("def other():\n" + BODY + "\n\ndef main():\n    def work():\n        q = 1\n        return q + 1\n\n"
           "    def setup(x=[(work := other) for _ in (0,)]):\n        return x\n\n"
           "    def inner(cb=work):\n        return cb()\n\n    return inner()\n")
    assert not any(s for _, s in _sure_edges({"app.py": app}, "app.py::main.inner", tmp_path / "a")), "預設值存的是 other"
    assert all(r is None for _, r in _edge_rules({"app.py": app}, "app.py::main.inner", tmp_path / "b"))


def test_p7_a_plain_function_parameter_named_self_uses_its_annotation(tmp_path):
    """codex 第 6 項（WARN）：一般函式的參數剛好叫 self、標註 Worker，不是方法自己的接收者 → 照一般參數標註給第 3 條。"""
    files = {"app.py": WORKER + "\n\ndef main(self: Worker):\n    return self.run()\n"}
    assert _edge_rules(files, "app.py::main", tmp_path) == [("app.py::Worker.run", 3)]


@pytest.mark.parametrize("order", ["inside_first", "outside_first"])
def test_p7_merging_keeps_each_target_on_its_own_evidence(tmp_path, order):
    """codex 第 7 項建議的回歸：同一來源兩處呼叫、目標不同：推導式裡呼叫 other（不給條號）、外面呼叫 work（第 1 條）；
    兩種先後順序結果相同，不跨目標升級。"""
    inside, outside = "    items = [other() for _ in range(2)]\n", "    work()\n"
    body = inside + outside if order == "inside_first" else outside + inside
    files = {"app.py": TWO_FUNCS + "def main():\n" + body + "    return items\n"}
    assert sorted(_edge_rules(files, "app.py::main", tmp_path)) == [("app.py::other", None), ("app.py::work", 1)]


# ─── 第八輪（codex 審 013）：標註不產生呼叫邊；被裝飾的函式只在保留身分的裝飾器下給條號 ─────────

META = "def make_metadata():\n" + BODY + "\n\n"
P8_ANNOTATION_CALLS = {   # 標註裡的呼叫：可能延後求值或根本不求值 → 不連邊（確定、候選都不給）
    "codex_future_annotated": ("from __future__ import annotations\nfrom typing import Annotated\n\n\n" + META
                               + "def main():\n    def inner(x: Annotated[int, make_metadata()]):\n        return x\n\n"
                               "    return inner(2)\n"),
    "param_annotation": META + "def main():\n    def inner(x: make_metadata()):\n        return x\n\n    return inner(2)\n",
    "return_annotation": META + "def main():\n    def inner() -> make_metadata():\n        return 1\n\n    return inner()\n",
    "local_variable_annotation": META + "def main():\n    x: make_metadata() = 1\n    return x\n",
}


@pytest.mark.parametrize("form", sorted(P8_ANNOTATION_CALLS))
def test_p8_a_call_inside_an_annotation_is_not_a_call(tmp_path, form):
    """codex 第 1 項＋總控台定死：參數標註、回傳標註（與函式裡的變數標註）一律不產生呼叫邊：from __future__ import
    annotations、3.14 以後標註延後求值，函式裡的變數標註根本不求值；標註只當型別證據。"""
    edges = _edge_rules({"app.py": P8_ANNOTATION_CALLS[form]}, "app.py::main", tmp_path)
    assert "app.py::make_metadata" not in [d for d, _ in edges], f"{form}：標註裡的 make_metadata() 不是 main 的呼叫"


def test_p8_defaults_and_decorator_factories_are_still_calls(tmp_path):
    """反方向（codex 第 5 項）：巢狀 def 的預設值 x=work() 與裝飾器工廠 @deco(1) 在定義當下真的執行 → 照常是第 1 條。"""
    app = DECO + TWO_FUNCS + "def main():\n    @deco(1)\n    def inner(x=work()):\n        return x\n\n    return inner\n"
    rules = _edge_rules({"app.py": app}, "app.py::main", tmp_path)
    assert ("app.py::work", 1) in rules and ("app.py::deco", 1) in rules, rules


LOGGED = ("from functools import wraps\n\n\ndef logged(fn):\n    @wraps(fn)\n    def wrapper(*a, **k):\n"
          "        return fn(*a, **k)\n\n    return wrapper\n\n\n")
RUN_BODY = "        x = 1\n        return x + 1\n"
P8_WRAPPED = {   # 寫法 → (app.py, 呼叫所在函式, 被包過的目標)：裝飾器不在保留身分清單 → 只給候選
    "codex_logged": (LOGGED + "@logged\ndef work():\n" + BODY + "\n\ndef main():\n    return work()\n",
                     "app.py::main", "app.py::work"),
    "lru_cache": ("import functools\n\n\n@functools.lru_cache(maxsize=None)\ndef work():\n" + BODY
                  + "\n\ndef main():\n    return work()\n", "app.py::main", "app.py::work"),
    "cache": ("from functools import cache\n\n\n@cache\ndef work():\n" + BODY + "\n\ndef main():\n    return work()\n",
              "app.py::main", "app.py::work"),
    "decorated_by_a_factory": (DECO + "@deco(1)\ndef work():\n" + BODY + "\n\ndef main():\n    return work()\n",
                               "app.py::main", "app.py::work"),
    "shadowed_staticmethod": ("def staticmethod(fn):\n    return lambda: 2\n\n\nclass Worker:\n    @staticmethod\n"
                              "    def run():\n" + RUN_BODY + "\n\ndef main():\n    return Worker.run()\n",
                              "app.py::main", "app.py::Worker.run"),
    "method_via_self": (LOGGED + "class Worker:\n    @logged\n    def run(self):\n" + RUN_BODY
                        + "\n    def go(self):\n        return self.run()\n", "app.py::Worker.go", "app.py::Worker.run"),
    "class_decorator": ("def register(cls):\n    return cls\n\n\n@register\nclass Worker:\n    def run(self):\n" + RUN_BODY
                        + "\n\ndef main():\n    return Worker().run()\n", "app.py::main", "app.py::Worker.run"),
    "callback_source": (LOGGED + "@logged\ndef work():\n" + BODY + "\n\ndef run(cb):\n    return cb()\n\n\n"
                        "def main():\n    return run(work)\n", "app.py::run", "app.py::work"),
}


@pytest.mark.parametrize("form", sorted(P8_WRAPPED))
def test_p8_a_function_behind_a_non_preserving_decorator_is_only_a_candidate(tmp_path, form):
    """codex 第 2 項＋總控台定死：被裝飾的函式（或方法所屬類別被裝飾），裝飾器不在保留原函式身分的清單裡
    （functools.lru_cache／cache、自訂裝飾器、被裝飾器工廠包過、自己定義的同名 staticmethod…）→ 呼叫先進的是裝飾器
    給的東西，連到原函式只給候選；callback 來源也一樣。"""
    app, fid, target = P8_WRAPPED[form]
    edges = _sure_edges({"app.py": app}, fid, tmp_path / "a")
    assert (target, False) in edges and (target, True) not in edges, f"{form}：{edges}"
    assert all(r is None for d, r in _edge_rules({"app.py": app}, fid, tmp_path / "b") if d == target)


P8_KEPT = {   # 寫法 → (app.py, 呼叫所在函式, 目標, 條號)：保留原函式身分的裝飾器照給條號
    "staticmethod": ("class Worker:\n    @staticmethod\n    def run():\n" + RUN_BODY + "\n\ndef main():\n    return Worker.run()\n",
                     "app.py::main", "app.py::Worker.run", 1),
    "classmethod": ("class Worker:\n    @classmethod\n    def make(cls):\n" + RUN_BODY
                    + "\n\ndef main():\n    return Worker.make()\n", "app.py::main", "app.py::Worker.make", 1),
    "typing_final": ("from typing import final\n\n\n@final\ndef work():\n" + BODY + "\n\ndef main():\n    return work()\n",
                     "app.py::main", "app.py::work", 1),
    "typing_module_override": ("import typing\n\n\nclass Worker:\n    @typing.override\n    def run(self):\n" + RUN_BODY
                               + "\n\ndef main(w: Worker):\n    return w.run()\n", "app.py::main", "app.py::Worker.run", 3),
    "dataclass": ("from dataclasses import dataclass\n\n\n@dataclass\nclass Worker:\n    n: int = 0\n\n    def run(self):\n"
                  + RUN_BODY + "\n\ndef main():\n    w = Worker()\n    return w.run()\n", "app.py::main", "app.py::Worker.run", 2),
    "dataclass_called": ("import dataclasses\n\n\n@dataclasses.dataclass(frozen=True)\nclass Worker:\n    n: int = 0\n\n"
                         "    def run(self):\n" + RUN_BODY + "\n\ndef main():\n    w = Worker()\n    return w.run()\n",
                         "app.py::main", "app.py::Worker.run", 2),
}


@pytest.mark.parametrize("form", sorted(P8_KEPT))
def test_p8_a_preserving_decorator_keeps_the_rule(tmp_path, form):
    """反方向：staticmethod、classmethod、typing 的 final／override、dataclass（含 dataclasses.dataclass(…)）保留原函式
    （與類別）身分，呼叫仍進原函式 → 條號照給。"""
    app, fid, target, rule = P8_KEPT[form]
    assert (target, rule) in _edge_rules({"app.py": app}, fid, tmp_path), f"{form}：保留身分的裝飾器不影響條號"


# ─── 015：查找經過的類別整條繼承鏈都要過類別裝飾器檢查 ─────────────────────────

DECO_CLS = "def deco(cls):\n    return cls\n\n\n"
BASE_INIT_M = "class Base:\n    def __init__(self):\n" + RUN_BODY + "\n    def m(self):\n" + RUN_BODY + "\n\n"
CHAIN_A = "class A:\n    def m(self):\n" + RUN_BODY + "\n\n"
P9_CHAIN = {   # 寫法 → (app.py, 呼叫所在函式, 目標)：呼叫點寫出的類別到定義方法的類別之間有清單外的類別裝飾器
    "d1_ctor_inherited_init": (DECO_CLS + BASE_INIT_M + "@deco\nclass Foo(Base):\n    pass\n\n\ndef main():\n    Foo()\n",
                               "app.py::main", "app.py::Base.__init__"),
    "d2_method_via_decorated_sub": (DECO_CLS + BASE_INIT_M + "@deco\nclass Foo(Base):\n    pass\n\n\n"
                                    "def main():\n    f = Foo()\n    f.m()\n", "app.py::main", "app.py::Base.m"),
    "d3_annot_receiver": (DECO_CLS + BASE_INIT_M + "@deco\nclass Foo(Base):\n    pass\n\n\ndef main(f: Foo):\n    f.m()\n",
                          "app.py::main", "app.py::Base.m"),
    "middle_layer": (DECO_CLS + CHAIN_A + "@deco\nclass B(A):\n    pass\n\n\nclass C(B):\n    pass\n\n\n"
                     "def main(c: C):\n    c.m()\n", "app.py::main", "app.py::A.m"),
    "super_through_decorated": (DECO_CLS + CHAIN_A + "@deco\nclass B(A):\n    pass\n\n\nclass C(B):\n    def m(self):\n"
                                "        return super().m()\n", "app.py::C.m", "app.py::A.m"),
    "static_via_decorated_sub": (DECO_CLS + "class Base:\n    @staticmethod\n    def s():\n" + RUN_BODY
                                 + "\n\n@deco\nclass Foo(Base):\n    pass\n\n\ndef main():\n    Foo.s()\n",
                                 "app.py::main", "app.py::Base.s"),
    "decorated_parent": (DECO_CLS + "@deco\nclass Base:\n    def m(self):\n" + RUN_BODY + "\n\nclass Foo(Base):\n    pass\n\n\n"
                         "def main(f: Foo):\n    f.m()\n", "app.py::main", "app.py::Base.m"),
}


@pytest.mark.parametrize("form", sorted(P9_CHAIN))
def test_p9_a_decorated_class_anywhere_on_the_lookup_chain_leaves_only_a_candidate(tmp_path, form):
    """總控台定死的家族規則：查找經過的每個類別，也就是呼叫點寫出的類別（建構的類別、接收者型別、類別.方法 的類別、super()
    用到的父類）到實際定義方法的類別之間整條繼承鏈，任一帶清單外類別裝飾器 → 只給候選，理由 DECORATED。
    含繼承來的 __init__（d1）、繼承來的方法（d2、d3）、多層繼承的中間層、super() 經過的父類、被裝飾類別當父類。"""
    app, fid, target = P9_CHAIN[form]
    edges = _sure_edges({"app.py": app}, fid, tmp_path / "a")
    assert (target, False) in edges and (target, True) not in edges, f"{form}：{edges}"
    g = rp.build_graph(_write(tmp_path / "b", {"app.py": app}))
    hit = [e for e in g.edges[fid] if e.dst == target]
    assert [_rule_of(e) for e in hit] == [None] and hit[0].guess == getattr(rp, "DECORATED", None), hit


P9_KEPT = {   # 寫法 → (app.py, 呼叫所在函式, 目標, 條號)：鏈上沒有清單外的類別裝飾器 → 條號照給
    "d4_dataclass": ("from dataclasses import dataclass\n\n\n" + BASE_INIT_M + "@dataclass\nclass Foo(Base):\n    pass\n\n\n"
                     "def main(f: Foo):\n    f.m()\n", "app.py::main", "app.py::Base.m", 3),
    "undecorated_chain": (CHAIN_A + "class B(A):\n    pass\n\n\nclass C(B):\n    pass\n\n\ndef main(c: C):\n    c.m()\n",
                          "app.py::main", "app.py::A.m", 3),
    "super_from_a_decorated_class": (DECO_CLS + CHAIN_A + "@deco\nclass C(A):\n    def m(self):\n        return super().m()\n",
                                     "app.py::C.m", "app.py::A.m", 1),
}


@pytest.mark.parametrize("form", sorted(P9_KEPT))
def test_p9_a_clean_lookup_chain_keeps_the_rule(tmp_path, form):
    """反方向：鏈上只有 dataclass、或完全沒有類別裝飾器 → 照給；被裝飾類別自己方法裡的 super().m() 走的是未裝飾的父類
    （零參數 super 用的是原本的類別），照給第 1 條。"""
    app, fid, target, rule = P9_KEPT[form]
    assert (target, rule) in _edge_rules({"app.py": app}, fid, tmp_path), f"{form}：鏈上沒有清單外的類別裝飾器"


# ─── 016（codex 第八輪）：dataclass 產生的方法、C3 MRO、裝飾器別名 ─────────────────────

def _guess_of(files: dict, fid: str, target: str, tmp_path) -> list:
    """fid → target 那條邊的 (條號, 不確定原因)。"""
    g = rp.build_graph(_write(tmp_path, files))
    return [(_rule_of(e), e.guess) for e in g.edges[fid] if e.dst == target]


DC_BASE = ("from dataclasses import dataclass\n\n\nclass Base:\n    def __init__(self):\n" + RUN_BODY
           + "\n    def __eq__(self, other):\n" + RUN_BODY + "\n\n")
P10_GENERATED = {   # 寫法 → (app.py, 呼叫所在函式, 目標)：dataclass 會自己產生這個方法，不從繼承鏈認證
    "codex_generated_init": (DC_BASE + "@dataclass\nclass Foo(Base):\n    n: int = 0\n\n\ndef main():\n    return Foo()\n",
                             "app.py::main", "app.py::Base.__init__"),
    "called_dataclass": (DC_BASE + "@dataclass(frozen=True)\nclass Foo(Base):\n    n: int = 0\n\n\ndef main():\n"
                         "    return Foo()\n", "app.py::main", "app.py::Base.__init__"),
    "super_into_dataclass": (DC_BASE + "@dataclass\nclass Foo(Base):\n    n: int = 0\n\n\nclass Sub(Foo):\n"
                             "    def __init__(self):\n        super().__init__()\n", "app.py::Sub.__init__", "app.py::Base.__init__"),
    "generated_eq": (DC_BASE + "@dataclass\nclass Foo(Base):\n    n: int = 0\n\n\ndef main(a: Foo, b):\n    return a.__eq__(b)\n",
                     "app.py::main", "app.py::Base.__eq__"),
}


@pytest.mark.parametrize("form", sorted(P10_GENERATED))
def test_p10_a_method_dataclass_generates_is_not_certified_from_the_parent(tmp_path, form):
    """codex 第八輪 BLOCK 1＋總控台定死：類別白名單只保證類別身分。dataclass（init 不是寫死 False）本體沒有自己的
    __init__ 時，建構式是它產生的（不呼叫父類的）；__eq__ 等它會產生的方法同理 → 經過它的查找只給候選，理由寫明。"""
    app, fid, target = P10_GENERATED[form]
    edges = _sure_edges({"app.py": app}, fid, tmp_path / "a")
    assert (target, False) in edges and (target, True) not in edges, f"{form}：{edges}"
    assert _guess_of({"app.py": app}, fid, target, tmp_path / "b") == [(None, getattr(rp, "GENERATED", None))]


P10_DATACLASS_KEPT = {   # dataclass 不產生的情況 → 照給
    "init_false": (DC_BASE + "@dataclass(init=False)\nclass Foo(Base):\n    n: int = 0\n\n\ndef main():\n    return Foo()\n",
                   "app.py::Base.__init__", 1),
    "own_init": (DC_BASE + "@dataclass\nclass Foo(Base):\n    n: int = 0\n\n    def __init__(self):\n" + RUN_BODY
                 + "\n\ndef main():\n    return Foo()\n", "app.py::Foo.__init__", 1),
}


@pytest.mark.parametrize("form", sorted(P10_DATACLASS_KEPT))
def test_p10_a_dataclass_that_does_not_generate_the_constructor_keeps_the_rule(tmp_path, form):
    """守門：@dataclass(init=False) 不產生建構式 → 照連父類 __init__、第 1 條；本體自己寫了 __init__ → dataclass 不蓋掉，照給。"""
    app, target, rule = P10_DATACLASS_KEPT[form]
    assert (target, rule) in _edge_rules({"app.py": app}, "app.py::main", tmp_path), form


MRO_CODEX = ("class B(A):\n    pass\n\n\nclass Mixin:\n    def run(self):\n        return 3\n\n\n"
             "class Worker(B, Mixin):\n    pass\n\n\ndef main():\n    w = Worker()\n    return w.run()\n")
A_RUN = "class A:\n    def run(self):\n" + RUN_BODY + "\n\n"


def test_p10_codex_multiple_inheritance_follows_c3_and_reaches_the_decorated_class(tmp_path):
    """codex 第八輪 BLOCK 2：Worker(B, Mixin)、B(A)：Python C3 MRO 是 Worker → B → A → Mixin，w.run() 跑的是 A.run，
    不是 Mixin.run。A 帶清單外類別裝飾器 → 候選、理由 DECORATED；拿掉裝飾器 → A.run 第 2 條。"""
    decorated = {"app.py": DECO_CLS + "@deco\n" + A_RUN + MRO_CODEX}
    edges = _sure_edges(decorated, "app.py::main", tmp_path / "a")
    assert "app.py::Mixin.run" not in [d for d, _ in edges], "C3 MRO 先走 B → A，不是 Mixin"
    assert _guess_of(decorated, "app.py::main", "app.py::A.run", tmp_path / "b") == [(None, getattr(rp, "DECORATED", None))]
    plain = {"app.py": A_RUN + MRO_CODEX}
    assert ("app.py::A.run", 2) in _edge_rules(plain, "app.py::main", tmp_path / "c"), "沒有裝飾器：照 C3 連 A.run、第 2 條"
    assert "app.py::Mixin.run" not in [d for d, _ in _edge_rules(plain, "app.py::main", tmp_path / "d")]


P10_MRO = {   # 寫法 → (app.py, 呼叫所在函式, 目標, 期望 (條號, 原因))
    "diamond": ("class A:\n    def m(self):\n        return 1\n\n\nclass B(A):\n    pass\n\n\nclass C(A):\n    def m(self):\n"
                + RUN_BODY + "\n\nclass D(B, C):\n    pass\n\n\ndef main():\n    d = D()\n    return d.m()\n",
                "app.py::main", "app.py::C.m", (2, "")),
    "decorated_in_the_middle": (DECO_CLS + "class A:\n    pass\n\n\n@deco\nclass B(A):\n    pass\n\n\nclass Mixin:\n"
                                "    def m(self):\n" + RUN_BODY + "\n\nclass W(B, Mixin):\n    pass\n\n\n"
                                "def main():\n    w = W()\n    return w.m()\n", "app.py::main", "app.py::Mixin.m", (None, "DECORATED")),
    "external_base_in_multiple": ("class Base:\n    def m(self):\n" + RUN_BODY + "\n\nclass W(Base, Exception):\n    pass\n\n\n"
                                  "def main():\n    w = W()\n    return w.m()\n", "app.py::main", "app.py::Base.m",
                                  (None, "MRO_UNPROVEN")),
    "own_method_despite_unprovable_mro": ("class Base:\n    pass\n\n\nclass W(Base, Exception):\n    def run(self):\n" + RUN_BODY
                                          + "\n    def go(self):\n        return self.run()\n", "app.py::W.go", "app.py::W.run", (3, "")),
}


@pytest.mark.parametrize("form", sorted(P10_MRO))
def test_p10_method_lookup_uses_c3_and_needs_a_provable_mro(tmp_path, form):
    """總控台定死：方法查找與裝飾器檢查共用 Python C3 MRO：菱形繼承照 C3 找對（D(B, C) 的 m 是 C.m）；被裝飾的類別在
    MRO 中段 → 候選；多重繼承裡有外部父類，MRO 證不出 → 查到的不是呼叫點寫出的類別自己時只給候選；
    查到的就是自己定義的方法，後面怎麼排都不影響 → 照給。"""
    app, fid, target, (rule, why) = P10_MRO[form]
    assert _guess_of({"app.py": app}, fid, target, tmp_path) == [(rule, getattr(rp, why, None) if why else "")], form


def test_p10_a_mixin_placed_before_the_base_in_a_subclass_overrides_self_calls(tmp_path):
    """第 3 條的子類覆寫照子孫自己的 C3 MRO 算：Child(Mixin, Base) 的實例在 Base.go 裡 self.m() 跑的是 Mixin.m
    （Mixin 不是 Base 的子孫，舊的覆寫檢查看不到）→ Base.go → Base.m 不給第 3 條。"""
    app = ("class Base:\n    def m(self):\n" + RUN_BODY + "\n    def go(self):\n        return self.m()\n\n\n"
           "class Mixin:\n    def m(self):\n        return 2\n\n\nclass Child(Mixin, Base):\n    pass\n")
    assert ("app.py::Base.m", True) not in _sure_edges({"app.py": app}, "app.py::Base.go", tmp_path / "a")
    assert "app.py::Mixin.m" in [d for d, _ in _edge_rules({"app.py": app}, "app.py::Base.go", tmp_path / "b")], "Mixin.m 也是可能跑到的地方"


P10_ALIASES = {   # 裝飾器用 import 別名：先還原原名再比白名單 → 照給
    "abstract_alias": ("from abc import abstractmethod as abstract\n\n\nclass Worker:\n    @abstract\n    def run(self):\n"
                       + RUN_BODY + "\n\ndef main(w: Worker):\n    return w.run()\n", "app.py::Worker.run", 3),
    "final_alias": ("from typing import final as preserve\n\n\n@preserve\ndef work():\n" + BODY
                    + "\n\ndef main():\n    return work()\n", "app.py::work", 1),
}


@pytest.mark.parametrize("form", sorted(P10_ALIASES))
def test_p10_a_decorator_imported_under_an_alias_is_recognized(tmp_path, form):
    """codex 第八輪 WARN（G5）：from abc import abstractmethod as abstract、from typing import final as preserve，
    沿 import 還原原名後在保留身分清單裡 → 條號照給（014 誤降成候選）。"""
    app, target, rule = P10_ALIASES[form]
    assert (target, rule) in _edge_rules({"app.py": app}, "app.py::main", tmp_path), form


P10_RARE = {   # 罕見構造：名字看起來在清單上，但綁定不是那個 → 只給候選
    "import_then_rebound": ("from typing import final\n\n\ndef final(fn):\n    return lambda: 2\n\n\n@final\ndef work():\n" + BODY
                            + "\n\ndef main():\n    return work()\n", "app.py::main", "app.py::work"),
    "getter_of_a_non_property": ("class Desc:\n    def getter(self, fn):\n        return lambda *a: 2\n\n\nrun = Desc()\n\n\n"
                                 "class Worker:\n    @run.getter\n    def run(self):\n" + RUN_BODY
                                 + "\n\ndef main(w: Worker):\n    return w.run()\n", "app.py::main", "app.py::Worker.run"),
}


@pytest.mark.parametrize("form", sorted(P10_RARE))
def test_p10_a_lookalike_decorator_that_is_not_the_real_one_is_only_a_candidate(tmp_path, form):
    """codex 第八輪 WARN 的兩個罕見構造：from typing import final 之後又 def final（綁定不再是那個 import）；
    @run.getter 的 run 不是同類別裡的 @property（自訂描述器）→ 都不是保留身分的裝飾器，只給候選。"""
    app, fid, target = P10_RARE[form]
    edges = _sure_edges({"app.py": app}, fid, tmp_path)
    assert (target, False) in edges and (target, True) not in edges, f"{form}：{edges}"


# ─── 017（codex 第九輪）：第 3 條逐一檢查子孫時套用與直接查找相同的否決 ─────────────────────

FACTORY_BASE = ("from dataclasses import dataclass\n\n\n" + DECO_CLS + "class Base:\n    def __init__(self):\n" + RUN_BODY
                + "\n    def __eq__(self, other):\n" + RUN_BODY + "\n    @classmethod\n    def create(cls):\n        return cls()\n\n\n")
P11_CHILDREN = {   # 子孫類別寫法 → (Base.create 裡的 cls() 連到 Base.__init__ 給不給第 3 條, main → Base.create 的條號)
    "codex_dataclass_child": ("@dataclass\nclass Child(Base):\n    n: int = 0\n", False, 1),
    "decorated_child": ("@deco\nclass Child(Base):\n    pass\n", False, None),
    "plain_child": ("class Child(Base):\n    pass\n", True, 1),
    "dataclass_init_false_child": ("@dataclass(init=False)\nclass Child(Base):\n    n: int = 0\n", True, 1),
}


@pytest.mark.parametrize("form", sorted(P11_CHILDREN))
def test_p11_a_classmethod_factory_sees_what_each_subclass_generates(tmp_path, form):
    """codex 第九輪 BLOCK＋總控台定死：Base.create 的 cls() 在 Child.create() 時建構的是 Child；第 3 條逐一檢查子孫時，
    從子孫沿自己的 C3 MRO 走到 Base，途中有 dataclass 產生 __init__、或清單外類別裝飾器 → 不給第 3 條。
    守門：沒裝飾的子類、@dataclass(init=False) 的子類照給。main → Base.create 照直接查找判（經過被清單外裝飾器包的
    Child 才不給，015 的家族規則）。"""
    child, sure, entry_rule = P11_CHILDREN[form]
    app = FACTORY_BASE + child + "\n\ndef main():\n    return Child.create()\n"
    edges = _sure_edges({"app.py": app}, "app.py::Base.create", tmp_path / "a")
    assert edges == [("app.py::Base.__init__", sure)], f"{form}：{edges}"
    rules = _edge_rules({"app.py": app}, "app.py::Base.create", tmp_path / "b")
    assert rules == [("app.py::Base.__init__", 3 if sure else None)], f"{form}：{rules}"
    assert ("app.py::Base.create", entry_rule) in _edge_rules({"app.py": app}, "app.py::main", tmp_path / "c")


def test_p11_a_dataclass_child_that_writes_its_own_init_is_an_ordinary_override(tmp_path):
    """守門：dataclass 子類本體自己寫了 __init__（dataclass 不產生、不蓋掉）：工廠的 cls() 照一般子類覆寫處理（兩個都是
    候選，理由不是 GENERATED），直接 Child() 照給第 1 條。"""
    child = "@dataclass\nclass Child(Base):\n    n: int = 0\n\n    def __init__(self):\n" + RUN_BODY
    app = FACTORY_BASE + child + "\n\ndef main():\n    return Child()\n"
    g = rp.build_graph(_write(tmp_path / "a", {"app.py": app}))
    factory = {e.dst: (_rule_of(e), e.guess) for e in g.edges["app.py::Base.create"]}
    assert set(factory) == {"app.py::Base.__init__", "app.py::Child.__init__"}, factory
    assert all(r is None and why != getattr(rp, "GENERATED", None) for r, why in factory.values()), factory
    assert ("app.py::Child.__init__", 1) in _edge_rules({"app.py": app}, "app.py::main", tmp_path / "b")


def test_p11_a_generated_eq_in_a_subclass_blocks_rule_3_through_a_base_typed_parameter(tmp_path):
    """codex 第九輪同根：Base 自訂 __eq__、dataclass 子類自動產生 __eq__；對標註成 Base 的參數呼叫 a.__eq__(b)，
    實際可能跑 Child 產生的 __eq__ → 不給第 3 條。"""
    app = FACTORY_BASE + "@dataclass\nclass Child(Base):\n    n: int = 0\n\n\ndef main(a: Base, b):\n    return a.__eq__(b)\n"
    edges = _sure_edges({"app.py": app}, "app.py::main", tmp_path / "a")
    assert edges == [("app.py::Base.__eq__", False)], edges
    assert _edge_rules({"app.py": app}, "app.py::main", tmp_path / "b") == [("app.py::Base.__eq__", None)]


MIXIN_M = "class Mixin:\n    def m(self):\n" + RUN_BODY + "\n\n"
P11_REGRESSIONS = {   # codex 第九輪建議固化的回歸：寫法 → (app.py, 呼叫所在函式, 目標, 期望 (條號, 原因))
    "userdict_and_mixin": ("import collections\n\n\n" + MIXIN_M + "class Store(collections.UserDict, Mixin):\n    pass\n\n\n"
                           "def main():\n    s = Store()\n    return s.m()\n", "app.py::main", "app.py::Mixin.m", (None, "MRO_UNPROVEN")),
    "userdict_via_parent_and_mixin": ("import collections\n\n\n" + MIXIN_M + "class Mid(collections.UserDict):\n    pass\n\n\n"
                                      "class Store(Mid, Mixin):\n    pass\n\n\ndef main():\n    s = Store()\n    return s.m()\n",
                                      "app.py::main", "app.py::Mixin.m", (None, "MRO_UNPROVEN")),
    "super_in_a_diamond": ("class A:\n    def run(self):\n        return 1\n\n\nclass B(A):\n    pass\n\n\nclass C(A):\n"
                           "    def run(self):\n" + RUN_BODY + "\n\nclass W(B, C):\n    def run(self):\n        return super().run()\n",
                           "app.py::W.run", "app.py::C.run", (1, "")),
    "super_with_a_multiple_inheritance_subclass": ("class A:\n    def run(self):\n" + RUN_BODY + "\n\nclass B(A):\n"
                                                   "    def run(self):\n        return super().run()\n\n\nclass C(A):\n"
                                                   "    def run(self):\n        return 2\n\n\nclass D(B, C):\n    pass\n",
                                                   "app.py::B.run", "app.py::A.run", (None, "MRO_UNPROVEN")),
    "c3_merge_failure": ("class A:\n    def m(self):\n" + RUN_BODY + "\n\nclass B(A):\n    pass\n\n\nclass C(A, B):\n    pass\n\n\n"
                         "def main():\n    c = C()\n    return c.m()\n", "app.py::main", "app.py::A.m", (None, "MRO_UNPROVEN")),
}


@pytest.mark.parametrize("form", sorted(P11_REGRESSIONS))
def test_p11_c3_regressions_stay_fixed(tmp_path, form):
    """codex 第九輪 PASS 項建議固化：外部祖先（直接繼承 UserDict＋mixin、經中間父類繼承 UserDict＋mixin）→ MRO 證不出；
    菱形裡 W.run 的 super().run() 照 C3 連 C.run、第 1 條；B.run 的 super() 在有多重繼承子孫 D(B, C) 時可能落到 C → 證不出；
    C3 合併失敗（C(A, B)、B(A)）→ 證不出。"""
    app, fid, target, (rule, why) = P11_REGRESSIONS[form]
    assert _guess_of({"app.py": app}, fid, target, tmp_path) == [(rule, getattr(rp, why, None) if why else "")], form


# ─── 018：codex 第十輪第 2 條的組合固化成回歸 ─────────────────────────────────────────

EQ_BASE = ("from dataclasses import dataclass\n\n\ndef invoke(cb, x):\n    return cb(x)\n\n\nclass Base:\n"
           "    def __eq__(self, other):\n        return \"BASE\"\n\n    def run(self, other):\n")
EQ_CHILDREN = {   # 子孫寫法：實際以它執行 Base.run
    "dataclass": "@dataclass\nclass Child(Base):\n    n: int = 0\n",
    "plain": "class Child(Base):\n    pass\n",
    "dataclass_via_custom_decorator": "def make(cls):\n    return dataclass(cls)\n\n\n@make\nclass Child(Base):\n    n: int = 0\n",
}
EQ_FORMS = {   # Base.run 裡的寫法 → (連到 Base.__eq__ 的邊在哪個函式, {子孫寫法: 期望條號})
    "self_call": ("        return self.__eq__(other)\n", "app.py::Base.run", {"dataclass": None, "plain": 3}),
    "alias": ("        f = self.__eq__\n        return f(other)\n", "app.py::Base.run", {"dataclass": None, "plain": 4}),
    "callback": ("        return invoke(self.__eq__, other)\n", "app.py::invoke", {"dataclass": None, "plain": 5}),
    "child_class_call": ("        return Child.__eq__(self, other)\n", "app.py::Base.run", {"dataclass": None}),
    "child_instance_call": ("        return Child().__eq__(other)\n", "app.py::Base.run", {"dataclass": None}),
    "base_class_call": ("        return Base.__eq__(self, other)\n", "app.py::Base.run", {"dataclass": 1}),
    "base_instance_call": ("        return Base().__eq__(other)\n", "app.py::Base.run", {"dataclass": 2}),
}
EQ_CASES = sorted((form, child) for form, (_, _, want) in EQ_FORMS.items() for child in want)


@pytest.mark.parametrize("form,child", EQ_CASES)
def test_p12_a_generated_eq_in_a_subclass_is_respected_by_every_rule(tmp_path, form, child):
    """codex 第十輪第 2 條：基底自訂 __eq__、run 寫在基底、實際以 dataclass 子類執行（它自己產生 __eq__）。
    self.__eq__(other) 不給第 3 條、f = self.__eq__; f(other) 不被第 4 條重新認證、invoke(self.__eq__, other) 的 callback
    不給第 5 條、Child.__eq__(self, other) 不給第 1 條、Child().__eq__(other) 不給第 2 條；明確選定基底的
    Base.__eq__(self, other)、Base().__eq__(other) 照給第 1、2 條。對照組：沒裝飾也沒覆寫的普通子類，前三種恢復 3／4／5。"""
    line, fid, want = EQ_FORMS[form]
    app = EQ_BASE + line + "\n\n" + EQ_CHILDREN[child]
    rules = [r for d, r in _edge_rules({"app.py": app}, fid, tmp_path) if d == "app.py::Base.__eq__"]
    assert rules == [want[child]], f"{form}／{child}：{rules}"


def test_p12_a_custom_decorator_that_applies_dataclass_blocks_rule_3_too(tmp_path):
    """codex 第十輪第 2 條另測：自訂類別裝飾器 make 透過 dataclass(cls) 產生方法（make 不在保留身分清單）→ 基底 run 裡的
    self.__eq__(other) 不給第 3 條。"""
    line, fid, _ = EQ_FORMS["self_call"]
    app = EQ_BASE + line + "\n\n" + EQ_CHILDREN["dataclass_via_custom_decorator"]
    edges = _sure_edges({"app.py": app}, fid, tmp_path)
    assert edges == [("app.py::Base.__eq__", False)], edges


# ─── 019（Codex 徹底檢核 C）：空實作覆寫、C# 作用域與委派、未知步、super 起點、掃描母體 ─────────

EMPTY_BASE = "class Base(ABC):\n    def run(self):\n        return 'BASE'\n\n\n"
P13_OVERRIDES = {   # 子類 run 的寫法 → Base.run 給不給第 3 條
    "pass_only": ("    def run(self):\n        pass\n", None),
    "docstring_only": ("    def run(self):\n        \"\"\"nothing\"\"\"\n", None),
    "nonempty": ("    def run(self):\n        return 1\n", None),
    "stub_ellipsis_in_concrete_class": ("    def run(self):\n        ...\n", None),
    "stub_raise_in_concrete_class": ("    def run(self):\n        raise NotImplementedError\n", None),
    "decorated_abstract": ("    @abstractmethod\n    def run(self):\n        ...\n", 3),
    "stub_in_abstract_class": ("    @abstractmethod\n    def other(self):\n        ...\n\n    def run(self):\n        ...\n", None),
}


@pytest.mark.parametrize("form", sorted(P13_OVERRIDES))
def test_p13_an_empty_override_is_still_an_override(tmp_path, form):
    """Codex C 第 1 條＋021 第 3 條＋023：子類 run 只有 pass、只有 docstring、只有 ...、raise NotImplementedError 都是存在的
    覆寫（實際跑子類實例回 None 或拋例外，不進基底），不論所在類別抽不抽象（抽象類別裡沒掛裝飾器的 stub 會被可實例化的
    孫類繼承）：main(x: Base) 的 x.run() 不給第 3 條；這些覆寫不當落點。真抽象只有方法本身掛 @abstractmethod（類別是
    ABCMeta）：那時這個類別與沒覆寫 run 的子孫都建不出實例，基底照給第 3 條。"""
    child, rule = P13_OVERRIDES[form]
    files = {"app.py": "from abc import ABC, abstractmethod\n\n\n" + EMPTY_BASE + "class Child(Base):\n" + child
                       + "\n\ndef main(x: Base):\n    return x.run()\n"}
    rules = dict(_edge_rules(files, "app.py::main", tmp_path / "a"))
    assert rules.get("app.py::Base.run", "missing") == rule, f"{form}：{rules}"
    report = rp.analyze(_write(tmp_path / "b", files), "app.py::main")
    landings = [r["landing"] for r in report["entries"][0]["routes"]]
    assert ("app.py::Child.run" in landings) == (form == "nonempty"), f"{form}：空實作與抽象都不當落點 {landings}"


@pytest.mark.parametrize("body", ["{}", "{ }", "{\n    }"])
def test_p13_a_csharp_empty_override_blocks_rule_3_regardless_of_whitespace(tmp_path, body):
    """Codex C 第 1 條（C#）：空大括號本體是空實作、不是分號宣告；{} 與 { } 結果要一樣：App.Go → Base.Run 不給第 3 條。"""
    cs = ("class Base {\n    public virtual void Run() { Work(); }\n    static void Work() { int n = 1; n++; }\n}\n"
          "class Child : Base {\n    public override void Run() " + body + "\n}\n"
          "class App {\n    static void Go(Base x) { x.Run(); }\n}\n")
    rules = dict(_edge_rules({"App.cs": cs}, "App.cs::App.Go", tmp_path))
    assert rules.get("App.cs::Base.Run", "missing") is None, rules
    g = rp.build_graph(_write(tmp_path / "g", {"App.cs": cs}))
    run = g.funcs["App.cs::Child.Run"]
    assert not run.abstract and getattr(run, "hollow", False), "空大括號是空實作，不是抽象"


def test_p13_a_csharp_declaration_without_body_is_still_abstract(tmp_path):
    """守門：分號宣告（abstract、介面）仍是抽象，不是空實作；Shape.Render → Shape.Draw 走 inherit 連到 Circle.Draw。"""
    g = rp.build_graph(_write(tmp_path, CS_KINDS))
    draw = g.funcs["Shapes.cs::Shape.Draw"]
    assert draw.abstract and not getattr(draw, "hollow", False)


CS_LOCAL = ("using System;\nclass P {\n    static void Run() { int n = 1; n++; }\n    static void Other() { int n = 2; n++; }\n"
            "    static void Main() {\n")


def test_p13_a_csharp_local_function_parameter_shadows_the_method(tmp_path):
    """Codex C 第 2 條：區域函式 void Wrap(Action Run) { Run(); } 裡的 Run 是參數，不是 P.Run：不連 P.Run、記未解。
    對照：Main 裡直接 Run() 照給第 3 條。"""
    shadow = {"P.cs": CS_LOCAL + "        void Wrap(Action Run) { Run(); }\n        Wrap(Other);\n    }\n}\n"}
    g = rp.build_graph(_write(tmp_path / "a", shadow))
    assert "P.cs::P.Run" not in [e.dst for e in g.edges["P.cs::P.Main"]], "區域函式的參數遮住同名方法"
    assert g.unres["P.cs::P.Main"] == 1
    plain = {"P.cs": CS_LOCAL + "        Run();\n    }\n}\n"}
    assert ("P.cs::P.Run", 3) in _edge_rules(plain, "P.cs::P.Main", tmp_path / "b")


@pytest.mark.parametrize("form", ["local_function_body", "lambda_variable", "lambda_argument"])
def test_p13_a_call_inside_a_csharp_local_function_or_lambda_gets_no_rule(tmp_path, form):
    """Codex C 第 2 條一整類：區域函式／lambda 的參數與綁定沒建模，裡面的呼叫一律模型外：連得到 P.Run，但不給條號。"""
    body = {"local_function_body": "        void Wrap() { Run(); }\n        Wrap();\n",
            "lambda_variable": "        Action act = () => Run();\n        act();\n",
            "lambda_argument": "        Use(() => Run());\n"}[form]
    cs = CS_LOCAL + body + "    }\n    static void Use(Action a) { a(); }\n}\n"
    rules = dict(_edge_rules({"P.cs": cs}, "P.cs::P.Main", tmp_path))
    assert rules.get("P.cs::P.Run", "missing") is None, f"{form}：{rules}"


def test_p13_a_csharp_invoke_through_a_receiver_does_not_borrow_a_same_name_parameter(tmp_path):
    """Codex C 第 3 條：h.cb.Invoke() 讀的是 h 的欄位 cb（值是 B），不是同名參數 cb（值是 A）：不連 P.A、記未解。
    對照：沒有接收者的 cb.Invoke() 照參數來源給第 5 條。"""
    head = ("using System;\nclass Holder { public Action cb; }\nclass P {\n    static void A() { int n = 1; n++; }\n"
            "    static void B() { int n = 2; n++; }\n")
    field = {"P.cs": head + "    static void Run(Holder h, Action cb) { h.cb.Invoke(); }\n"
                            "    static void Main() { Run(new Holder { cb = B }, A); }\n}\n"}
    g = rp.build_graph(_write(tmp_path / "a", field))
    assert [e.dst for e in g.edges.get("P.cs::P.Run", [])] == [], "欄位委派證不出，不能拿同名參數補"
    assert g.unres["P.cs::P.Run"] == 1
    param = {"P.cs": head + "    static void Run(Holder h, Action cb) { cb.Invoke(); }\n"
                            "    static void Main() { Run(new Holder { cb = B }, A); }\n}\n"}
    assert _edge_rules(param, "P.cs::P.Run", tmp_path / "b") == [("P.cs::P.A", 5)]


def test_p13_a_csharp_array_type_is_not_its_element_type(tmp_path):
    """Codex C 第 4 條：Worker[] workers 的接收者是陣列，不是 Worker：workers.ToString() 不連 Worker.ToString、也不算未解
    （陣列的成員是外部）。對照：Worker worker 照給第 3 條。"""
    worker = "class Worker {\n    public override string ToString() { int n = 1; n++; return \"w\"; }\n}\n"
    arr = {"P.cs": worker + "class P {\n    static string Work(Worker[] workers) { return workers.ToString(); }\n}\n"}
    g = rp.build_graph(_write(tmp_path / "a", arr))
    assert g.edges.get("P.cs::P.Work", []) == [] and g.unres["P.cs::P.Work"] == 0
    one = {"P.cs": worker + "class P {\n    static string Work(Worker worker) { return worker.ToString(); }\n}\n"}
    assert _edge_rules(one, "P.cs::P.Work", tmp_path / "b") == [("P.cs::Worker.ToString", 3)]


CS_HANDLERS = ("using System;\nclass P {\n    static Action[] handlers = { Work };\n    static void Main() { Relay(); }\n"
               "    static void Relay() { RELAY }\n    static void Work() { int n = 1; n++; n *= 2; }\n}\n")


def test_p13_a_csharp_indexed_delegate_call_counts_as_an_unresolved_call(tmp_path):
    """Codex C 第 5 條：handlers[0]() 是一次看不到對象的呼叫，計入未解；前後比較不能把 Work 落點報成消失、涵蓋也要標變差。
    對照：(int)(x) 這種轉型不算呼叫。"""
    before = _write(tmp_path / "b", {"P.cs": CS_HANDLERS.replace("RELAY", "Work();")})
    after = _write(tmp_path / "a", {"P.cs": CS_HANDLERS.replace("RELAY", "handlers[0]();")})
    g = rp.build_graph(after)
    assert g.unres["P.cs::P.Relay"] == 1, "handlers[0]() 是一次看不到對象的呼叫，要計入未解"
    res = rp.run_compare(after, str(before), None, "P.cs::P.Main", None)
    assert res["coverage_drop"] is True and res["counts"]["gone"] == 0 and res["counts"]["better"] == 0
    cast = rp.build_graph(_write(tmp_path / "c", {"P.cs": CS_HANDLERS.replace("RELAY", "int x = (int)(3.0); Work();")}))
    assert cast.unres["P.cs::P.Relay"] == 0


C6_CHAIN = ("def main(cb):\n    return a(cb)\n\n\ndef a(cb):\n    return A_BODY\n\n\ndef b(n):\n    return c(n)\n\n\n"
            "def c(n):\n    return end(n)\n\n\ndef end(n):\n    return n\n")


def test_p13_an_unresolved_call_mid_chain_is_an_unknown_step_and_taints_the_whole_route(tmp_path):
    """Codex C 第 6 條：a 裡多了看不到來源的 cb()，a 不再是證明過的轉傳，但也不是證明過的直接一步：那一步是「未知」，
    照算一個彎（3 彎不會變 2 彎），整條到 end 的路標未讀到底、不進刻度分布，入口只給觀測值、不可評級。"""
    ctrl = rp.analyze(_write(tmp_path / "ctrl", {"app.py": C6_CHAIN.replace("A_BODY", "b(0)")}), "app.py::main")
    end = _route(ctrl, "app.py::end")
    assert end["turns"] == 3 and end["certain"] and not end["incomplete"] and ctrl["entries"][0]["grades"]["警戒"] == 1
    assert ctrl["entries"][0].get("ratable", True) and "alert=1" in rp.done_line(ctrl)
    rep = rp.analyze(_write(tmp_path / "mid", {"app.py": C6_CHAIN.replace("A_BODY", "b(cb())")}), "app.py::main")
    end = _route(rep, "app.py::end")
    assert end["turns"] == 3 and end["incomplete"], "未知那一步照算彎（3 彎不會變 2 彎），整條路未讀到底"
    assert _kinds(end)[0] == "unknown" and end.get("unknown_steps") == 1 and end.get("unresolved_path") == 1
    e = rep["entries"][0]
    assert not e.get("ratable", True) and e["max_turns"] == 3 and sum(e["grades"].values()) == 0
    tail = rp.done_line(rep)
    assert "ratable=0" in tail and "max_turns=3*" in tail and "alert=0*" in tail, f"不可評級：尾行只給加 * 的觀測值 {tail}"
    assert re.fullmatch(r"READING_PATH DONE( \w+=\S+)*", tail)
    assert "不可評級" in rp.render(rep, 3) and "未知" in rp.render(rep, 3)


@pytest.mark.parametrize("mods", [("", "new"), ("virtual", "override")])
def test_p13_csharp_new_hiding_is_not_modeled_so_it_stays_a_candidate(tmp_path, mods):
    """Codex C 第 7 條（v6.0 不建模，守門）：virtual／override／new 不分，子類同名方法一律當覆寫：Go(Base x) 的 x.Run()
    在 new 隱藏與 override 兩種寫法下都只給候選、不給條號（new 的誠實寫法降級，列在抓不到清單）。"""
    base_mod, child_mod = mods
    cs = (f"class Base {{\n    public {base_mod} void Run() {{ int n = 1; n++; }}\n}}\n"
          f"class Child : Base {{\n    public {child_mod} void Run() {{ int n = 2; n++; }}\n}}\n"
          "class App {\n    static void Go(Base x) { x.Run(); }\n}\n")
    rules = dict(_edge_rules({"App.cs": cs}, "App.cs::App.Go", tmp_path))
    assert "App.cs::Base.Run" in rules and rules["App.cs::Base.Run"] is None, rules


def test_p13_csharp_generic_same_name_zero_parameter_methods_collide_and_both_stay_candidates(tmp_path):
    """Codex C 第 7 條（v6.0 不建模，守門）：Get() 與 Get<T>() 零參數同名，簽章撞在一起：兩個都是多載候選、不給條號，
    比較時只剩一列（列在抓不到清單）。"""
    cs = ("class K {\n    public int Get() { int n = 1; n++; return n; }\n    public T Get<T>() { int n = 2; n++; return default(T); }\n"
          "    public void Main() { Get(); Get<int>(); }\n}\n")
    rules = _edge_rules({"K.cs": cs}, "K.cs::K.Main", tmp_path)
    assert len(rules) == 2 and all(r is None for _, r in rules), rules


def test_p13_csharp_conditional_method_calls_are_not_certified(tmp_path):
    """Codex C 第 7 條：[Conditional("DEBUG")] 的方法，符號沒定義時編譯器會省略呼叫：連得到，但只給候選、理由寫明。"""
    cs = ("using System.Diagnostics;\nclass P {\n    [Conditional(\"DEBUG\")]\n    static void Log() { int n = 1; n++; }\n"
          "    static void Main() { Log(); }\n}\n")
    assert _guess_of({"P.cs": cs}, "P.cs::P.Main", "P.cs::P.Log", tmp_path) == [(None, getattr(rp, "CONDITIONAL", None))]


def test_p13_an_explicit_super_start_is_not_certified(tmp_path):
    """Codex C 第 8 條：super(B, self).run() 的起點沒建模（實際跳過 B 進 A）：A.run、B.run 都列候選、不給條號；
    對照：零參數 super().run() 照 MRO 連 B.run、第 1 條。"""
    base = "class A:\n    def run(self):\n        return 1\n\n\nclass B(A):\n    def run(self):\n        return 2\n\n\n"
    explicit = {"app.py": base + "class C(B):\n    def go(self):\n        return super(B, self).run()\n"}
    rules = sorted(_edge_rules(explicit, "app.py::C.go", tmp_path / "a"))
    assert rules == [("app.py::A.run", None), ("app.py::B.run", None)], rules
    assert _guess_of(explicit, "app.py::C.go", "app.py::A.run", tmp_path / "b") == [(None, getattr(rp, "SUPER_EXPLICIT", None))]
    plain = {"app.py": base + "class C(B):\n    def go(self):\n        return super().run()\n"}
    assert _edge_rules(plain, "app.py::C.go", tmp_path / "c") == [("app.py::B.run", 1)]


def test_p13_report_wording_is_observed_paths_not_bounds(tmp_path):
    """Codex C 第 9 條＋021 第 6 條：全確定的數字是「確定邊子圖上的最短觀測路徑」，報告與完整 --help（含白名單段）都不再
    寫成可信的下限／上限參考；partial 豁免只免換檔的彎。"""
    text = rp.render(rp.analyze(_write(tmp_path, PY_WRAPPED), "app.py"), 3)
    assert "最短觀測路徑" in text and "可信下限" not in text and "上限參考" not in text
    helped = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--help"], capture_output=True, text=True, encoding="utf-8")
    assert "豁免的只有換檔那個彎" in helped.stdout and "--scope" in helped.stdout
    assert "可信的下限" not in helped.stdout and "上限參考" not in helped.stdout and "最短觀測路徑" in helped.stdout


def _git_repo(root: Path, files: dict) -> Path:
    _write(root, files)
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "init"], check=True)
    return root


def test_p13_git_scope_is_the_tracked_list_and_marketplaces_are_never_scanned(tmp_path):
    """Codex C 第 10 條：預設 --scope git 只掃版本追蹤清單與原始碼副檔名的交集；未追蹤的副本不算；plugins/marketplaces
    兩種政策都不掃；報告附政策、檔數、清單雜湊；不在 git 裡退回 tree 並標明。"""
    repo = _git_repo(tmp_path / "repo", {".gitignore": "vendor_copy/\nplugins/\n", **PY_STRAIGHT})
    _write(repo, {"vendor_copy/extra.py": "def extra():\n    return 1\n",
                  "plugins/marketplaces/m/x.py": "def market():\n    return 2\n"})
    assert "scope" in rp.analyze(repo, "app.py")["stats"], "報告要附掃描母體（政策、檔數、清單雜湊）"
    git_scope = rp.analyze(repo, "app.py", scope="git")["stats"]["scope"]
    tree_scope = rp.analyze(repo, "app.py", scope="tree")["stats"]["scope"]
    assert git_scope["policy"] == "git" and git_scope["files"] == len(PY_STRAIGHT) and len(git_scope["digest"]) == 12
    assert tree_scope["policy"] == "tree" and tree_scope["files"] == len(PY_STRAIGHT) + 1, "tree 多掃到未追蹤的副本"
    funcs = set(rp.build_graph(repo, "tree").funcs)
    assert not any("marketplaces" in f for f in funcs), "marketplaces 在哪種政策下都不掃"
    loose = rp.analyze(_write(tmp_path / "loose", PY_STRAIGHT), "app.py")["stats"]["scope"]
    assert loose["policy"].startswith("tree(") and loose["files"] == len(PY_STRAIGHT)


def test_p13_compare_with_different_scope_policies_is_undecidable(tmp_path):
    """Codex C 第 10 條：前後掃描母體政策不同（追蹤清單 vs 目錄遞迴）→ 整份不可判定、涵蓋標變差，不報改善。"""
    repo = _git_repo(tmp_path / "repo", PY_WRAPPED)
    assert "scope" in rp.analyze(repo, "app.py")["stats"], "報告要附掃描母體政策，比較才有得比"
    res = rp.compare(rp.analyze(repo, "app.py", scope="git"), rp.analyze(repo, "app.py", scope="tree"))
    assert res["scope_mismatch"] and res["coverage_drop"] and res["counts"]["better"] == 0
    assert res["rows"] and all(r["status"] == "undecidable" for r in res["rows"])
    same = rp.compare(rp.analyze(repo, "app.py", scope="git"), rp.analyze(repo, "app.py", scope="git"))
    assert not same["scope_mismatch"] and same["counts"]["same"] == len(same["rows"])


# ─── 021（codex 審 020）：看不到不能變好、stub 覆寫、兩側同一套範圍政策 ─────────────────────

def test_p14_an_equivalent_rewrite_of_an_unobserved_function_is_not_better(tmp_path):
    """021 第 1 條：a 從 return b(cb()) 拆成區域變數寫法，兩版都有看不到來源的 cb()、都不可評級；未知不靠句數門檻
    （落到有未解呼叫的函式就是未知），比較守門先看兩側可評級與整路完整性：該列不可判定、better=0。"""
    chain = C6_CHAIN.replace("A_BODY", "b(cb())")
    split = C6_CHAIN.replace("    return A_BODY", "    x = cb()\n    y = b(x)\n    return y")
    before = _write(tmp_path / "b", {"app.py": chain})
    after = _write(tmp_path / "a", {"app.py": split})
    for root in (before, after):
        rep = rp.analyze(root, "app.py::main")
        end = _route(rep, "app.py::end")
        assert _kinds(end)[0] == "unknown" and end["turns"] == 3 and end["incomplete"], "長短都一樣：落到 a 是未知步"
        assert not rep["entries"][0]["ratable"]
    res = rp.run_compare(after, str(before), None, "app.py::main", None)
    assert res["counts"]["better"] == 0 and res["counts_candidate"]["better"] == 0
    assert _row(res, "app.py::end")["status"] == "undecidable" and res["coverage_drop"] is True
    assert "better=0" in rp.compare_done_line(res)


def test_p14_losing_the_tail_of_a_chain_cannot_lower_the_numbers(tmp_path):
    """021 第 2 條：a 改成 fn = [b][0]; fn(0)，後半條鏈看不到了：尾行 ratable=0、max_turns 與刻度加 * 標成觀測值，
    比較摘要 better=0、該入口不可判定；coverage_drop 時 better 必為 0。"""
    ctrl = _write(tmp_path / "ctrl", {"app.py": C6_CHAIN.replace("A_BODY", "b(0)")})
    lost = _write(tmp_path / "lost", {"app.py": C6_CHAIN.replace("    return A_BODY", "    fn = [b][0]\n    return fn(0)")})
    tail_ctrl, tail_lost = rp.done_line(rp.analyze(ctrl, "app.py::main")), rp.done_line(rp.analyze(lost, "app.py::main"))
    assert "ratable=1 max_turns=3 " in tail_ctrl and "alert=1 " in tail_ctrl
    assert "ratable=0" in tail_lost and "max_turns=1*" in tail_lost and "alert=0*" in tail_lost, tail_lost
    res = rp.run_compare(lost, str(ctrl), None, "app.py::main", None)
    assert res["counts"]["better"] == 0 and res["coverage_drop"] is True
    assert res["undecidable_entries"] == ["app.py::main"]
    assert all(r["status"] in ("undecidable", "gone") for r in res["rows"]), [r["status"] for r in res["rows"]]


def test_p14_tracked_build_dir_is_treated_the_same_on_both_sides_of_a_compare(tmp_path):
    """021 第 4 條：被追蹤的 build/worker.py 在工作樹（git 清單）與歷史快照（git archive）兩側套同一套目錄排除：
    兩側政策都是 git、檔數相同，同內容比較沒有消失、沒有不可判定；被追蹤的 marketplaces 兩側同樣不掃。"""
    files = {"app.py": "from lib import worker\n\n\ndef main():\n    worker.go()\n", "lib/__init__.py": "",
             "lib/worker.py": "def go():\n    x = 1\n    return x + 1\n",
             "build/gen.py": "def gen():\n    return 1\n",
             "plugins/marketplaces/m/x.py": "def market():\n    return 2\n"}
    repo = _git_repo(tmp_path / "repo", files)
    live = rp.analyze(repo, "app.py::main")["stats"]["scope"]
    assert live["policy"] == "git" and live["files"] == 3, live
    assert not any("marketplaces" in f or "build/" in f for f in rp.build_graph(repo).funcs)
    res = rp.run_compare(repo, "HEAD", None, "app.py::main", None)
    assert res["stats_before"]["scope"]["policy"] == res["stats_after"]["scope"]["policy"] == "git"
    assert res["stats_before"]["scope"]["files"] == res["stats_after"]["scope"]["files"] == 3
    assert res["stats_before"]["scope"]["digest"] == res["stats_after"]["scope"]["digest"]
    assert not res["scope_mismatch"] and res["counts"]["gone"] == 0 and res["undecidable_entries"] == []
    assert _row(res, "lib/worker.py::go")["status"] == "same"


def test_p14_csharp_calls_after_an_inner_block_in_a_local_function_still_get_no_rule(tmp_path):
    """021 第 5 條：區域函式裡先有一個 if {…} 區塊，之後的 Run()／cb.Invoke() 仍在區域函式裡：參數遮蔽記未解、
    callback 不給第 5 條（內層括號關掉不等於區域函式結束）。"""
    head = ("using System;\nclass P {\n    static void Run() { int n = 1; n++; }\n    static void Other() { int n = 2; n++; }\n")
    shadow = {"P.cs": head + "    static void Main() {\n        void Wrap(Action Run) {\n            if (true) { int x = 1; }\n"
                             "            Run();\n        }\n        Wrap(Other);\n    }\n}\n"}
    g = rp.build_graph(_write(tmp_path / "a", shadow))
    assert "P.cs::P.Run" not in [e.dst for e in g.edges["P.cs::P.Main"]] and g.unres["P.cs::P.Main"] == 1
    cb = {"P.cs": head + "    static void Go(Action cb) {\n        void Wrap() {\n            if (true) { int x = 1; }\n"
                         "            cb.Invoke();\n        }\n        Wrap();\n    }\n    static void Main() { Go(Other); }\n}\n"}
    rules = dict(_edge_rules(cb, "P.cs::P.Go", tmp_path / "b"))
    assert rules.get("P.cs::P.Other", "missing") is None, rules


def test_p14_an_unresolved_call_in_the_entry_taints_every_route(tmp_path):
    """021 第 6 條：未解呼叫在入口本身（main 回傳 a(cb())），後續鏈全可解：到 end 的路仍整條未讀到底、不進刻度，入口不可評級。"""
    app = ("def main(cb):\n    return a(cb())\n\n\ndef a(n):\n    return b(n)\n\n\ndef b(n):\n    return c(n)\n\n\n"
           "def c(n):\n    return end(n)\n\n\ndef end(n):\n    return n\n")
    rep = rp.analyze(_write(tmp_path, {"app.py": app}), "app.py::main")
    end = _route(rep, "app.py::end")
    assert end["incomplete"] and end["unresolved_path"] == 1 and end["unresolved"] == 0, "入口的未解也算整條路未讀到底"
    e = rep["entries"][0]
    assert not e["ratable"] and sum(e["grades"].values()) == 0 and "ratable=0" in rp.done_line(rep), "入口有未解：不可評級"


# ─── 023（codex 審 022）：抽象只看方法本身、候選欄是探索路徑、比較摘要的觀測標記 ─────────────

P15_GRANDCHILD = ("class Base(BASE_HEAD):\n    def run(self):\n        return 'BASE'\n\n\n"
                  "class Child(Base):\n    @abstractmethod\n    def other(self):\n        ...\n\n"
                  "    def run(self):\n        ...\n\n\n"
                  "class Concrete(Child):\n    def other(self):\n        return 1\n\n\n"
                  "def main(x: Base):\n    return x.run()\n")


@pytest.mark.parametrize("head,base", [("from abc import ABC, abstractmethod", "ABC"),
                                       ("from abc import ABCMeta, abstractmethod", "metaclass=ABCMeta")])
def test_p15_an_undecorated_stub_in_an_abstract_class_reaches_a_concrete_grandchild(tmp_path, head, base):
    """023 BLOCK（codex 重現）：Child 有別的 @abstractmethod，但 run 只是沒掛裝飾器的 ...；Concrete(Child) 補上 other 就建得出
    實例，x.run() 實際跑繼承來的 Child.run（回 None）。Base.run 不給第 3 條、Child.run 是候選目標；Child.run 是空實作不當落點。"""
    files = {"app.py": head + "\n\n\n" + P15_GRANDCHILD.replace("BASE_HEAD", base)}
    rules = dict(_edge_rules(files, "app.py::main", tmp_path / "a"))
    assert rules.get("app.py::Base.run", "missing") is None, rules
    assert rules.get("app.py::Child.run", "missing") is None, f"繼承給孫類的 stub 要列成候選目標：{rules}"
    landings = [r["landing"] for r in rp.analyze(_write(tmp_path / "b", files), "app.py::main")["entries"][0]["routes"]]
    assert "app.py::Child.run" not in landings, landings


P15_META = {   # 類別怎麼寫 → 子類 @abstractmethod run 擋不擋得住實例（Base.run 給不給第 3 條）
    "abc_base": ("from abc import ABC, abstractmethod\n\n\n", "class Base(ABC):\n", 3),
    "abcmeta_via_module": ("import abc\nfrom abc import abstractmethod\n\n\n", "class Base(metaclass=abc.ABCMeta):\n", 3),
    "abc_on_grandparent": ("from abc import ABC, abstractmethod\n\n\nclass Root(ABC):\n    pass\n\n\n",
                           "class Base(Root):\n", 3),
    "no_abc": ("from abc import abstractmethod\n\n\n", "class Base:\n", None),
    "abc_name_rebound": ("from abc import ABC, abstractmethod\n\nABC = object\n\n\n", "class Base(ABC):\n", None),
    "lookalike_from_elsewhere": ("from abc import abstractmethod\nfrom mylib import ABC\n\n\n", "class Base(ABC):\n", None),
}


@pytest.mark.parametrize("form", sorted(P15_META))
def test_p15_abstractmethod_only_blocks_instances_under_abcmeta(tmp_path, form):
    """023 BLOCK 同家族：@abstractmethod 只在類別的 metaclass 確定是 abc.ABCMeta（自己或祖先的父類是 abc.ABC、或
    metaclass=abc.ABCMeta）時擋得住建立實例；沒繼承 ABC、ABC 被改綁 → Child() 照樣建得出來、x.run() 跑的是 Child.run，
    Child.run 是存在的覆寫；ABC 從專案外來源來 → 證不出 ABCMeta，保守降為候選。兩種 Base.run 都不給第 3 條。"""
    head, cls_line, rule = P15_META[form]
    app = (head + cls_line + "    def run(self):\n        return 'BASE'\n\n\n"
           "class Child(Base):\n    @abstractmethod\n    def run(self):\n        ...\n\n\n"
           "def main(x: Base):\n    return x.run()\n")
    rules = dict(_edge_rules({"app.py": app}, "app.py::main", tmp_path))
    assert rules.get("app.py::Base.run", "missing") == rule, f"{form}：{rules}"


@pytest.mark.parametrize("annotate,want", [("Interface", {"app.py::Child.run": None}), ("Child", {"app.py::Child.run": 3})])
def test_p15_an_all_stub_interface_keeps_concrete_children_as_candidates(tmp_path, annotate, want):
    """codex 審 022 第 8 條（對照）：Interface.run 只有 ...（沒掛裝飾器，是空實作不當落點），Child.run 有實作。標註 Interface
    時 Child.run 是候選；標註 Child 時照給第 3 條。"""
    app = ("class Interface:\n    def run(self):\n        ...\n\n\n"
           "class Child(Interface):\n    def run(self):\n        return 1\n\n\n"
           f"def main(x: {annotate}):\n    return x.run()\n")
    rules = dict(_edge_rules({"app.py": app}, "app.py::main", tmp_path))
    assert {k: v for k, v in rules.items() if k == "app.py::Child.run"} == want, rules


P15_TABLE = ("def a(n):\n    return b(n)\n\n\ndef b(n):\n    return c(n)\n\n\ndef c(n):\n    return end(n)\n\n\n"
             "def end(n):\n    t = n * 2\n    t += 1\n    return t\n\n\nHANDLERS = TABLE\n\n\n"
             "def main(key):\n    return HANDLERS[key](0)\n")


def test_p15_a_candidate_only_shortcut_is_labelled_as_exploration_not_improvement(tmp_path):
    """023 WARN 1：只有候選路的入口（HANDLERS[key](0) 查表分派）新增一條直接指向 end 的捷徑：候選欄可以報變化，但要明寫
    「探索路徑變化（非實際呼叫鏈改善）」；全確定欄 better=0；兩側都不可評級，比較尾行印 ratable=0 並把數字標 *。"""
    before = _write(tmp_path / "b", {"app.py": P15_TABLE.replace("TABLE", '{"a": a}')})
    after = _write(tmp_path / "a", {"app.py": P15_TABLE.replace("TABLE", '{"a": a, "shortcut": end}')})
    res = rp.run_compare(after, str(before), None, "app.py::main", None)
    assert res["counts"]["better"] == 0 and res["counts_candidate"]["better"] == 1, (res["counts"], res["counts_candidate"])
    assert res.get("counts_candidate_meaning") == "探索路徑變化（非實際呼叫鏈改善）"
    text = rp.render_compare(res, 3)
    assert "含候選（探索路徑變化（非實際呼叫鏈改善））" in text and "（含候選：探索路徑變化）" in text, text
    tail = rp.compare_done_line(res)
    assert "ratable=0" in tail and re.search(r" max_turns_before=\d+\* max_turns_after=\d+\* ", tail), tail


def test_p15_compare_summary_marks_observed_numbers_when_unratable(tmp_path):
    """023 WARN 1：後半條鏈消失（fn = [b][0]）那案的比較尾行：max_turns_before／after、coverage_drop 加 * 並印 ratable=0，
    與一般尾行一致；兩側都可評級時印 ratable=1、不加 *。"""
    ctrl = _write(tmp_path / "ctrl", {"app.py": C6_CHAIN.replace("A_BODY", "b(0)")})
    lost = _write(tmp_path / "lost", {"app.py": C6_CHAIN.replace("    return A_BODY", "    fn = [b][0]\n    return fn(0)")})
    tail = rp.compare_done_line(rp.run_compare(lost, str(ctrl), None, "app.py::main", None))
    assert "ratable=0 max_turns_before=3* max_turns_after=1* coverage_drop=1*" in tail, tail
    assert re.fullmatch(r"READING_PATH DONE( \w+=\S+)*", tail), tail
    same = rp.run_compare(ctrl, str(ctrl), None, "app.py::main", None)
    clean = rp.compare_done_line(same)
    assert "ratable=1 max_turns_before=3 max_turns_after=3 coverage_drop=0" in clean and "*" not in clean, clean
    assert "觀測值・不可評級" not in rp.render_compare(same, 3)


def test_p16_a_parse_failure_in_the_longer_entry_makes_the_whole_summary_unratable(tmp_path):
    """025 BLOCK（G11）：不指定入口、自動偵測兩檔的 main：long.py 3 彎、short.py 0 彎；after 只把 long.py 弄成語法錯誤。
    列級本來就對（不報變好、消失那列不可判定），整份摘要也要對：JSON 的 ratable＝False，尾行 ratable=0 且
    max_turns_before／after 與 coverage_drop 帶 *，文字有觀測值註記（三處都看 compare_ratable 這一個判斷）。"""
    short = "def main():\n    return end()\n\n\ndef end():\n    return 1\n"
    before = _write(tmp_path / "b", {"long.py": C6_CHAIN.replace("A_BODY", "b(0)"), "short.py": short})
    after = _write(tmp_path / "a", {"long.py": "def main(:\n    pass\n", "short.py": short})
    res = rp.run_compare(after, str(before), None, None, None)
    assert res["entries"] == 2 and res["counts"]["better"] == 0
    assert res.get("ratable") is False, f"長入口那檔解析失敗：整份不可評級 {res.get('ratable')}"
    tail = rp.compare_done_line(res)
    assert "ratable=0 max_turns_before=3* max_turns_after=0* coverage_drop=1*" in tail, tail
    assert "觀測值・不可評級" in rp.render_compare(res, 3)


P15_MOVE = ("def pick():\n    return 1\n\n\ndef main():\n    return a(0)\n\n\n"
            "def a(n):\nA_BLIND    return b(n)\n\n\ndef b(n):\nB_BLIND    return c(n)\n\n\n"
            "def c(n):\n    return end(n)\n\n\ndef end(n):\n    t = n * 2\n    t += 1\n    return t\n")
BLIND = "    h = pick()\n    h()\n"


@pytest.mark.parametrize("after_a,after_b", [(BLIND + "    h()\n", ""), ("", BLIND)])
def test_p15_unresolved_count_or_place_changes_never_report_better(tmp_path, after_a, after_b):
    """codex 審 022 第 2 條（固化回歸）：兩側未解數量不同（1→2）、或數量相同但位置由 a 移到 b，確定與候選都不報變好，
    到 end 那列不可判定。"""
    before = _write(tmp_path / "b", {"app.py": P15_MOVE.replace("A_BLIND", BLIND).replace("B_BLIND", "")})
    after = _write(tmp_path / "a", {"app.py": P15_MOVE.replace("A_BLIND", after_a).replace("B_BLIND", after_b)})
    res = rp.run_compare(after, str(before), None, "app.py::main", None)
    assert res["counts"]["better"] == 0 and res["counts_candidate"]["better"] == 0
    assert _row(res, "app.py::end")["status"] == "undecidable"


# ─── g12w（hooks 接線）：掃描母體跳過 git 忽略目錄、宣告層次軸、比較的不變列、多入口 ─────────────

def _cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--root", str(root), *args],
                          capture_output=True, text=True, encoding="utf-8")


def _cli_json(root: Path, *args: str) -> dict:
    out = _cli(root, *args, "--json")
    assert out.returncode == 0, out.stdout[-500:] + out.stderr[-500:]
    return json.loads("\n".join(out.stdout.strip().splitlines()[:-1]))


def test_g12w_git_scope_skips_an_ignored_dir_and_unresolved_stays_the_same(tmp_path):
    """接線 1：預設 --scope git 用 git ls-files 的集合：.gitignore 忽略的目錄裡未追蹤的 .py 不進母體，unresolved、
    檔數、清單雜湊都和沒有那個目錄時一樣；同一棵樹改用目錄遞迴就掃得到（這個案擋得住退回目錄遞迴）。
    已追蹤的檔即使路徑符合 .gitignore 也照掃（與比較時 git archive 那一側一致）。"""
    files = {".gitignore": "ignored/\n", **PY_STRAIGHT}
    clean = _git_repo(tmp_path / "clean", files)
    dirty = _git_repo(tmp_path / "dirty", files)
    _write(dirty, {"ignored/extra.py": "def extra():\n    fn = make()\n    return fn()\n"})
    base, st = rp.analyze(clean, "app.py")["stats"], rp.analyze(dirty, "app.py")["stats"]
    assert st["scope"]["policy"] == "git" and st["scope"]["files"] == base["scope"]["files"] == len(PY_STRAIGHT)
    assert st["scope"]["digest"] == base["scope"]["digest"] and "ignored/extra.py" not in st["file_funcs"]
    assert st["unresolved"] == base["unresolved"], "忽略目錄裡解析不了的呼叫不能算進來"
    tree = rp.analyze(dirty, "app.py", scope="tree")["stats"]
    assert "ignored/extra.py" in tree["file_funcs"] and tree["unresolved"] > base["unresolved"], "反證：目錄遞迴會掃到"
    subprocess.run(["git", "-C", str(dirty), "add", "-f", "ignored/extra.py"], check=True)
    forced = rp.analyze(dirty, "app.py")["stats"]
    assert "ignored/extra.py" in forced["file_funcs"] and forced["scope"]["files"] == len(PY_STRAIGHT) + 1


LAYERED = {
    "entry/app.py": "from svc.service import run\n\n\ndef main():\n    total = 1\n    total += run(total)\n    return total\n",
    "entry/direct.py": "from repo.store import save\n\n\ndef jump():\n    total = 2\n    total += save(total)\n    return total\n",
    "svc/service.py": "from repo.store import save\nfrom svc.helper import tidy\n\n\ndef run(n):\n    value = tidy(n)\n"
                      "    value += save(value)\n    return value\n",
    "svc/helper.py": "def tidy(n):\n    out = n * 2\n    out += 1\n    return out\n",
    "repo/store.py": "def save(n):\n    kept = n + 1\n    kept *= 2\n    return kept\n",
}
LAYER_MAP = ("# 部位表\n\n| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 層 |\n|---|---|---|---|---|\n"
             "| `entry/` | 入口層 | 無 | 無 | 第1層 |\n| `svc/` | 服務層 | 無 | 無 | 第2層 |\n| `repo/` | 資料層 | 無 | 無 | 第3層 |\n")


def _layered(root: Path, table: str | None = LAYER_MAP, name: str = "overview-map.md") -> Path:
    _write(root, LAYERED)
    if table is not None:
        _write(root, {f".claude/{name}": table})
    return root


def _moves(route: dict) -> list:
    return [(s.get("layer_from"), s.get("layer_to"), s.get("counted")) for s in route["steps"][1:]]


def test_g12w_adjacent_and_same_layer_file_changes_are_not_jumps(tmp_path):
    """接線 2：--root 底下的部位表宣告第 1～3 層：入口層→服務層→資料層每一步都是相鄰層，服務層內換檔是同層，
    換檔都不算跳檔（拐彎 0、layer_jumps 2）；--json 每一步記 layer_from／layer_to／counted。"""
    root = _layered(tmp_path)
    rep = _cli_json(root, "--entry", "entry/app.py::main")
    save, tidy = _route(rep, "repo/store.py::save"), _route(rep, "svc/helper.py::tidy")
    assert (save["turns"], save["file_jumps"], save.get("layer_jumps")) == (0, 0, 2), save
    assert _moves(save) == [(1, 2, False), (2, 3, False)] and save["certain"]
    assert (tidy["file_jumps"], _moves(tidy)[-1]) == (0, (2, 2, False)), "同層換檔不算"
    assert (rep["stats"].get("layers") or {}).get("files") == len(LAYERED)
    text = _cli(root, "--entry", "entry/app.py::main").stdout
    assert "宣告層次軸" in text and "第1層→第2層（相鄰層" in text


def test_g12w_skipping_a_layer_or_an_undeclared_file_still_counts(tmp_path):
    """接線 2：入口層直接呼叫資料層（跨兩層）照算跳檔；檔不在任何宣告列（util/）照算；轉手照算彎（服務層的
    只轉傳函式 wrapper 在相鄰層也是 1 彎）。"""
    root = _layered(tmp_path)
    direct = _route(_cli_json(root, "--entry", "entry/direct.py::jump"), "repo/store.py::save")
    assert (direct["file_jumps"], direct["turns"], _moves(direct)) == (1, 1, [(1, 3, True)])
    _write(root, {"util/fmt.py": "def fmt(n):\n    s = str(n)\n    s += '!'\n    return s\n",
                  "entry/show.py": "from util.fmt import fmt\nfrom svc.relay import relay\n\n\ndef show():\n"
                                   "    out = fmt(1)\n    out += relay(2)\n    return out\n",
                  "svc/relay.py": "from repo.store import save\n\n\ndef relay(n):\n    return save(n)\n"})
    rep = _cli_json(root, "--entry", "entry/show.py::show")
    fmt = _route(rep, "util/fmt.py::fmt")
    assert (fmt["file_jumps"], _moves(fmt)) == (1, [(1, None, True)]), "沒宣告層的檔照算"
    via = _route(rep, "repo/store.py::save")
    assert _kinds(via) == ["wrapper", "direct"] and (via["file_jumps"], via["turns"]) == (0, 1), via


def test_g12w_without_a_declared_layer_axis_numbers_are_unchanged(tmp_path):
    """接線 2：沒有部位表、或部位表的層欄只寫「單層」（沒有第 N 層）→ 不套層次軸，數字與退回前一版相同
    （拐彎 2、跳檔 2、尾行一樣）；新欄位：layer_from／layer_to 為 None、換檔那一步 counted 為 True。"""
    plain = _layered(tmp_path / "plain", None)
    single = _layered(tmp_path / "single", re.sub(r"第\d層", "單層", LAYER_MAP))
    for root in (plain, single):
        save = _route(_cli_json(root, "--entry", "entry/app.py::main"), "repo/store.py::save")
        assert (save["turns"], save["file_jumps"]) == (2, 2), "沒宣告層次軸時每次換檔都算"
        assert "宣告層次軸" not in _cli(root, "--entry", "entry/app.py::main").stdout
        assert _moves(save) == [(None, None, True)] * 2
    tails = [_cli(r, "--entry", "entry/app.py::main").stdout.strip().splitlines()[-1] for r in (plain, single)]
    assert tails[0] == tails[1] and "max_file_jumps=2 " in tails[0]


def test_g12w_explicit_layers_flag_and_compare_use_the_axis_on_both_sides(tmp_path):
    """接線 2：--layers 指定別的部位表檔也吃；比較模式（git rev ↔ 工作樹）兩側都套同一個層次軸。"""
    root = _layered(tmp_path / "flag", name="alt-map.md")
    flagged = _cli_json(root, "--entry", "entry/app.py::main", "--layers", str(root / ".claude" / "alt-map.md"))
    assert _route(flagged, "repo/store.py::save")["file_jumps"] == 0
    assert _route(_cli_json(root, "--entry", "entry/app.py::main"), "repo/store.py::save")["file_jumps"] == 2, \
        "沒給 --layers 只看 .claude/overview-map.md"
    repo = _git_repo(tmp_path / "repo", {**LAYERED, ".claude/overview-map.md": LAYER_MAP})
    res = _cli_json(repo, "--before", "HEAD", "--entry", "entry/app.py::main")
    row = _row(res, "repo/store.py::save")
    assert row["status"] == "same" and row["before"]["file_jumps"] == row["after"]["file_jumps"] == 0


def test_g12w_root_map_declares_the_hook_layer_axis():
    """根層部位表（本 repo 的 .claude/overview-map.md）宣告的層次軸：hooks/handlers 第 1 層、hooks 第 2 層、lib 第 3 層、
    tools 自成第 4 層（只和 lib 相鄰）；其他列「單層」不在軸上。"""
    axis = rp.layer_axis(None, ROOT)
    assert axis, "根層部位表要宣告層次軸"
    files = ["hooks/handlers/stop.py", "hooks/wg_core.py", "lib/overview_hub.py", "tools/reading-path.py",
             "skills/x/scripts/y.py", "run_verify.py"]
    assert rp.file_layers(axis, files) == {"hooks/handlers/stop.py": 1, "hooks/wg_core.py": 2, "lib/overview_hub.py": 3,
                                           "tools/reading-path.py": 4}


def test_g12w_compare_text_says_all_unchanged_and_json_keeps_every_same_row(tmp_path):
    """接線 3：比較模式不變的列，文字只印一行計數（全部不變時說「全部不變」），--json 的 rows 完整保留每一列 same
    （含 before／after 的整條路）；有變動時變動列照列、不變的仍一行計數。"""
    a, b = _write(tmp_path / "a", PY_WRAPPED), _write(tmp_path / "b", PY_WRAPPED)
    res = rp.run_compare(b, str(a), None, None, None)
    text = rp.render_compare(res, 3)
    assert f"全部不變 {len(res['rows'])} 列" in text and "[不變]" not in text
    full = _cli_json(b, "--before", str(a))
    same = [r for r in full["rows"] if r["status"] == "same"]
    assert same and len(same) == len(full["rows"]) == full["counts"]["same"]
    assert all(r["before"]["steps"] and r["after"]["steps"] for r in same), "same 列要帶完整的前後路徑"
    body = "def {0}(n):\n    k = n + 1\n    k *= 2\n    return k\n"
    two = {"app.py": "from x import a\nfrom y import b\n\n\ndef main():\n    n = a(1)\n    n += b(2)\n    return n\n",
           "x.py": body.format("a"), "y.py": body.format("b")}
    moved = {**two, "y.py": "from z import c\n\n\ndef b(n):\n    return c(n)\n", "z.py": body.format("c")}
    mixed = rp.run_compare(_write(tmp_path / "e", moved), str(_write(tmp_path / "d", two)), None, "app.py::main", None)
    mtext = rp.render_compare(mixed, 3)
    assert [r["status"] for r in mixed["rows"]].count("same") == 1 and mixed["counts"]["new"] == 1
    assert "不變 1 列" in mtext and "全部不變" not in mtext and "[不變]" not in mtext and "[新增]" in mtext


def test_g12w_entry_can_be_given_several_times_and_misses_are_listed(tmp_path):
    """--entry 可給多次（聯集，hooks 接線一次量本 session 改過的檔所在的幾個入口）；找不到的那幾個列在輸出，
    全部都找不到才報錯；比較模式只有兩版都找不到的才算找不到（只在一版有的是新增／消失）。"""
    root = _write(tmp_path / "now", {**PY_WRAPPED, "solo.py": "from core import work\n\n\ndef solo():\n    n = work(1)\n"
                                                              "    n += 2\n    return n\n"})
    both = _cli(root, "--entry", "app.py", "--entry", "solo.py::solo", "--entry", "nope.py")
    assert both.returncode == 0 and "entries=2 " in both.stdout.strip().splitlines()[-1]
    assert "找不到入口（略過）：nope.py" in both.stdout
    assert _cli_json(root, "--entry", "app.py", "--entry", "nope.py")["entry_misses"] == ["nope.py"]
    none = _cli(root, "--entry", "nope.py", "--entry", "gone.py")
    assert none.returncode == 1 and none.stdout.strip().splitlines()[-1].startswith("READING_PATH FAIL")
    old = _write(tmp_path / "old", PY_WRAPPED)
    res = _cli_json(root, "--before", str(old), "--entry", "app.py", "--entry", "solo.py::solo", "--entry", "nope.py")
    assert res["entry_misses"] == ["nope.py"]
    assert [r["status"] for r in res["rows"] if r["entry"] == "solo.py::solo"] == ["new"], "只在 after 有的入口是新增"


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
