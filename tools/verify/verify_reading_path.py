"""verify_reading_path.py：閱讀路徑掃描器 tools/reading-path.py（＋ reading_path_lang.py）。

正例：入口→三層包裝→落地 數出跳檔／轉手／拐彎；Python 與 C# 各一組 callback／事件／繼承分派被認成轉手；
      partial 檔名有責任軸 → 標「分檔有責任軸」不算彎；前後比較（兩個目錄、git rev）差異正確；尾行哨兵。
反例：拿掉包裝的直線版數字較小；無責任軸的 partial 照算跳檔；同版本比較全部不變；
      反證——一次拿掉一種轉手偵測（callback／event／inherit／dynamic／責任軸），對應案例就紅。
假專案都在 tmp 現建。怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider tools/verify/verify_reading_path.py
"""
from __future__ import annotations

import importlib.util
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
    hits = [r for e in report["entries"] for r in e["routes"] if r["landing"] == landing]
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
    assert report["stats"]["ambiguous"] == 1, "poke 的 getattr 沒有分派表可對 → 記成對不到，不亂連"


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


def test_same_event_name_with_two_handlers_is_marked_candidate(tmp_path):
    files = dict(PY_KINDS)
    files["main.py"] = files["main.py"].replace('bus.on("saved", on_saved)',
                                                'bus.on("saved", on_saved)\n    bus.on("saved", on_item)')
    r = _route(rp.analyze(_write(tmp_path, files), "main.py"), "main.py::on_saved")
    assert r["steps"][-1]["kind"] == "event" and r["steps"][-1]["guess"].startswith("候選")


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


def test_csharp_overload_ids_survive_layout_changes():
    body = ("class K {\n    void Work(int a) { a += 1; a *= 2; a -= 3; }\n"
            '    void Work(string s) { s += "x"; s += "y"; s += "z"; }\n}\n')
    ids = lambda text: sorted(f.id for f in rp.lang.parse_csharp("K.cs", text).funcs)
    assert ids(body) == ids("\n\n" + body) == ["K.cs::K.Work", "K.cs::K.Work(string)"]


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
    assert payload["entries"][0]["routes"][0]["turns"] == 4

    bad = run("--entry", "no_such_func")
    assert bad.returncode == 1 and bad.stdout.strip().splitlines()[-1].startswith("READING_PATH FAIL reason=")

    helped = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPT), "--help"], capture_output=True, text=True,
                            encoding="utf-8")
    assert helped.returncode == 0 and "--before" in helped.stdout and "抓不到" in helped.stdout
