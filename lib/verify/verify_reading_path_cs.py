"""verify_reading_path_cs.py：C# 改動的閱讀路徑（lib/reading_path_cs.py＋hooks/wg_reading_path.py 的 C# 分流）。

量什麼：本回合改到的 .cs 加一跳上下游（沿呼叫或繼承）建圖，從改到的函式與它的直接呼叫者出發找路，跟 before 比；
  超線才問（路上拐彎超過 3 個、本次改到的函式只轉手、繼承鏈有空層），沒超線結果文字是空的，不送模型。
正例：4 層換檔的呼叫鏈 → 一條「入口」標跳 4 層、材料列那幾層；只轉手的一層 → 一條「空層」；繼承鏈中間一層只有空覆寫 → 一條「類別」。
反例：2 層換檔 → 沒有條目、沒有文字（零 token）；本回合沒改 .cs → 不量；v6 總開關關 → 收尾不量。
批次：同一個使用者回合交工作後又改同一個 .cs（回合號不變）→ 下一批照檔案指紋照樣量，沒再變的不重量。
範圍：大 fixture（300 個無關檔、兩跳外的上下游）→ 解析只碰改到的檔與一跳上下游；檔名對上卻不是定義所在 → 照樣找到定義的檔。
材料：超線條目只列那幾層，一條有長度上限，範圍裡其他函式不出現。
分析器：本機有 .NET SDK 附的 Roslyn 就用 Roslyn，沒有用輕量解析；兩種跑同一批案例結果相同；Roslyn 跑不動（含快取目錄建不起來）
        退回輕量並註明。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider lib/verify/verify_reading_path_cs.py
        python -X utf8 lib/verify/verify_reading_path_cs.py（尾行 READING_PATH_CS_CHECK PASS／FAIL）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "hooks", ROOT / "lib", ROOT / "tools"):
    sys.path.insert(0, str(_p))

import reading_path_lang as lang  # noqa: E402
import turn_metrics_cs as tmc  # noqa: E402
import wg_reading_path as rph  # noqa: E402

_SID = "sid-cs-rp"
EXTS = [".py", ".cs"]


def _layer(name: str, nxt: str) -> str:
    """一層有實質內容（多一句運算、同檔的檢查）再往下一層呼叫：不是只轉手。"""
    return (f"public class {name}\n{{\n    private {nxt} _next = new {nxt}();\n"
            f"    public int Run(int x)\n    {{\n        int y = x * 2;\n        Check(y);\n        return _next.Run(y);\n    }}\n"
            f"    private void Check(int v) {{ if (v < 0) {{ v = 0; }} }}\n}}\n")


LANDING = "public class {0}\n{{\n    public int Run(int x)\n    {{\n        int s = 0;\n        for (int i = 0; i < x; i++) {{ s += i; }}\n        return s;\n    }}\n}}\n"
CHAIN4 = {"A.cs": _layer("A", "B"), "B.cs": _layer("B", "C"), "C.cs": _layer("C", "D"), "D.cs": _layer("D", "E")}
CHAIN2 = {"P.cs": _layer("P", "Q"), "Q.cs": _layer("Q", "R")}
SVC_BEFORE = ("public class Svc\n{\n    private Repo _repo = new Repo();\n"
              "    public void Save(int x)\n    {\n        if (x < 0) { return; }\n        _repo.Save(x);\n    }\n}\n")
SVC_AFTER = "public class Svc\n{\n    private Repo _repo = new Repo();\n    public void Save(int x) { _repo.Save(x); }\n}\n"
REPO = ("public class Repo\n{\n    public void Save(int x)\n    {\n        if (x > 0) { Write(x); }\n    }\n"
        "    private void Write(int x) { if (x > 9) { x = 9; } }\n}\n")
UNIT = "public abstract class Unit\n{\n    public virtual void Tick() { if (hp > 0) { hp--; } }\n    protected int hp;\n}\n"
MID = "public class Mid : Unit\n{\n    public override void Tick() { base.Tick(); }\n}\n"
LEAF = "public class Leaf : Mid\n{\n    public int Walk(int n)\n    {\n        if (n > 1) { n--; }\n        return n;\n    }\n}\n"


# ─── 夾具：真 git repo、背景量測同一個行程跑完 ─────────────────────────────────────

def _write(root: Path, files: dict) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def _vcs(root: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _repo(root: Path, base: dict, after: dict) -> Path:
    """base 先 commit；after 寫進工作樹並 git add（新檔也進追蹤，量得到）。"""
    _write(root, base)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _vcs(root, "add", "-A")
    _vcs(root, "commit", "-q", "-m", "base")
    _write(root, after)
    _vcs(root, "add", "-A")
    return root


def _job(root: Path, files: list, turn_files=None) -> dict:
    files = [str(root / f) for f in files]
    job = {"turn": 5, "plans": [[str(root), str(root), files, "HEAD", []]], "outside": 0, "slow": [],
           "code_exts": EXTS, "case_globs": [], "turn_judgment": dict(rph.TURN_JUDGMENT_DEFAULTS), "budget": 240}
    job["turn_files"] = files if turn_files is None else [str(root / f) for f in turn_files]
    return job


@pytest.fixture(params=["light", "roslyn"])
def analyzer(request, monkeypatch):
    """兩種分析器各跑一遍：light＝把 Roslyn 偵測換成找不到；roslyn＝本機沒有 .NET SDK 就略過。"""
    try:
        import cs_roslyn
    except ImportError:          # 還沒有 Roslyn 前端：light 照舊跑（拿舊程式比出紅），roslyn 這一遍直接紅
        assert request.param == "light", "沒有 lib/cs_roslyn.py"
        return request.param
    if request.param == "light":
        monkeypatch.setattr(cs_roslyn, "find_roslyn", lambda: None)
    elif cs_roslyn.find_roslyn() is None:
        pytest.skip("本機找不到 .NET SDK 附的 Roslyn")
    return request.param


def _items(res: dict, kind: str) -> list:
    return [it for it in res.get("judgment") or [] if it["kind"] == kind]


# ─── 超線：跳 4 層、只轉手的空層、繼承空層 ─────────────────────────────────────────

def test_four_layer_chain_is_over_line_with_only_those_layers(tmp_path, analyzer):
    root = _repo(tmp_path / "r", {"E.cs": LANDING.format("E")}, CHAIN4)
    res = rph.run_job(_job(root, list(CHAIN4)))
    routes = _items(res, "入口")
    assert [it["name"] for it in routes] == ["A.cs::A.Run → E.cs::E.Run"], res.get("text")
    nums = routes[0]["nums"]
    assert nums.startswith("跳 4 層（換檔 4、轉手 0）") and "A.Run → B.Run → C.Run → D.Run → E.Run" in nums, nums
    assert "Check" not in nums, "材料只列路上那幾層"
    assert "要人看的 1 條" in (res["text"] or "") or res["judgment"], res
    assert not _items(res, "空層"), "每一層都有實質內容，不算只轉手"


def test_forwarding_only_layer_is_flagged_empty(tmp_path, analyzer):
    root = _repo(tmp_path / "r", {"Svc.cs": SVC_BEFORE, "Repo.cs": REPO}, {"Svc.cs": SVC_AFTER})
    res = rph.run_job(_job(root, ["Svc.cs"]))
    empty = _items(res, "空層")
    assert [it["name"] for it in empty] == ["Svc.cs::Svc.Save"], res.get("text")
    assert "只轉手 → Repo.Save" in empty[0]["nums"], empty[0]["nums"]
    assert not _items(res, "入口"), "只跳 1 層，不超線"


def test_hollow_inherit_layer_is_flagged_once_as_class(tmp_path, analyzer):
    root = _repo(tmp_path / "r", {"Unit.cs": UNIT, "Mid.cs": "public class Mid : Unit\n{\n}\n"},
                 {"Mid.cs": MID, "Leaf.cs": LEAF})
    res = rph.run_job(_job(root, ["Mid.cs", "Leaf.cs"]))
    names = [it["name"] for it in _items(res, "類別")]
    assert names == ["Mid.cs::Mid", "Leaf.cs::Leaf"], res.get("text")
    assert not _items(res, "空層"), "只呼叫上層同名方法的覆寫已算在類別空層裡，不再單獨問"


# ─── 不打擾：2 層、沒改 .cs、v6 關 ─────────────────────────────────────────────

def test_two_layer_chain_is_quiet_and_sends_nothing(tmp_path, analyzer):
    root = _repo(tmp_path / "r", {"R.cs": LANDING.format("R")}, CHAIN2)
    res = rph.run_job(_job(root, list(CHAIN2)))
    assert res["judgment"] == [] and not res["text"], res
    rec = {"job": {"out": str(tmp_path / "out.json"), "path": str(tmp_path / "job.json"), "turn": 5, "at": 0}}
    rph.write_result(Path(rec["job"]["out"]), res)
    assert rph._collect(rec) is None and "owed" not in rec, "沒超線：收尾不附字、不欠判斷"


def test_turn_without_cs_change_does_not_measure_cs(tmp_path, monkeypatch):
    import reading_path_cs
    calls = []
    monkeypatch.setattr(reading_path_cs, "measure", lambda *a, **k: calls.append(a) or {})
    root = _repo(tmp_path / "r", {"E.cs": LANDING.format("E"), "m.md": "x\n"}, CHAIN4)
    res = rph.run_job(_job(root, list(CHAIN4), turn_files=[]))
    assert calls == [] and res["judgment"] == [] and not res["text"], "這回合沒改 .cs：C# 不量"
    state = {"turn_seq": 6, "modified_files": [{"path": str(root / "m.md"), "session_id": _SID, "turn_seq": 6,
                                                 "last_turn_seq": 6}]}
    assert rph.reading_path_note(state, _SID, {}, spawn=lambda p: calls.append(p)) == (None, False) and calls == []


def test_v6_switch_off_skips_reading_path_at_stop(tmp_path, monkeypatch):
    from handlers import stop as st
    seen = []
    monkeypatch.setattr(st, "reading_path_note", lambda *a, **k: seen.append(a) or (None, False))
    for name in ("_find_session_transcript", "detect_evasion", "write_state", "_attribute_usefulness",
                 "_maybe_spawn_user_extract_worker", "harvest_gate_reason", "pending_gate_reason"):
        monkeypatch.setattr(st, name, lambda *a, **k: None)
    monkeypatch.setattr(st, "token_warn_payload", lambda *a, **k: "")
    monkeypatch.setattr(st, "_detect_uncommitted_files", lambda mf: [])
    monkeypatch.setattr(st, "_hud_alive", lambda *a, **k: (True, {}))
    monkeypatch.setattr(st, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: "改好了。")
    monkeypatch.setattr(st, "get_current_turn_visible_text", lambda *a, **k: ("", {"turn_tool_names_all": []}))
    cs = str(tmp_path / "A.cs")
    for v6 in ("0", "1"):
        monkeypatch.setenv("WG_V6", v6)
        state = {"phase": "working", "failing_tests": [], "recent_user_prompts": [], "stop_blocked_count": 0, "turn_seq": 5,
                 "modified_files": [{"path": cs, "tool": "Edit", "session_id": _SID, "turn_seq": 5, "last_turn_seq": 5}]}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        try:
            st.handle_stop({"session_id": _SID, "cwd": ""}, {"verify_scope": {"enabled": False}})
        except SystemExit:
            pass
        assert len(seen) == (0 if v6 == "0" else 1), f"WG_V6={v6}：閱讀路徑量測 {'不該' if v6 == '0' else '要'}跑"


# ─── 材料上限、範圍只到一跳 ─────────────────────────────────────────────────────

def test_over_line_material_has_a_length_cap_and_no_other_functions(tmp_path, analyzer):
    names = [f"VeryLongLayerNameForReadingPathNumber{i:02d}Handler" for i in range(12)]
    chain = {f"{n}.cs": _layer(n, names[i + 1]) for i, n in enumerate(names[:-1])}
    side = {"Helper.cs": "public class Helper\n{\n    public int Unrelated(int x) { if (x > 0) { x--; } return x; }\n}\n"}
    root = _repo(tmp_path / "r", {f"{names[-1]}.cs": LANDING.format(names[-1]), **side}, chain)
    res = rph.run_job(_job(root, list(chain)))
    routes = _items(res, "入口")
    assert routes and all(len(it["nums"]) <= rph.CS_MATERIAL_MAX for it in routes), [len(it["nums"]) for it in routes]
    assert "跳 11 層" in routes[0]["nums"] and "…" in routes[0]["nums"], routes[0]["nums"]
    assert "Unrelated" not in (res["text"] or "") and len(res["judgment"]) <= rph.TURN_JUDGMENT_DEFAULTS["max_items"]


def test_scope_is_changed_files_plus_one_hop_on_a_big_project(tmp_path, analyzer, monkeypatch):
    import cs_roslyn
    import reading_path_cs
    filler = {f"fill/F{i:03d}.cs": f"public class F{i:03d}\n{{\n    public int V() {{ return {i}; }}\n}}\n" for i in range(300)}
    base = {**filler,
            "Manager.cs": "public class Manager\n{\n    private Clerk _c = new Clerk();\n    public void Open() { _c.Serve(1); _c.Serve(2); }\n}\n",
            "Clerk.cs": "public class Clerk\n{\n    private Shop _s = new Shop();\n    public void Serve(int n) { if (n > 0) { _s.Sell(n); } }\n}\n",
            "Shop.cs": "public class Shop\n{\n    private Till _t = new Till();\n    public void Sell(int n) { if (n > 1) { _t.Ring(n); } }\n}\n",
            "Till.cs": "public class Till\n{\n    private Ledger _l = new Ledger();\n    public void Ring(int n) { if (n > 2) { _l.Book(n); } }\n}\n",
            "Ledger.cs": "public class Ledger\n{\n    public void Book(int n) { if (n > 3) { n--; } }\n}\n"}
    after = {"Shop.cs": base["Shop.cs"].replace("if (n > 1)", "if (n > 5)")}
    root = _repo(tmp_path / "r", base, after)
    parsed: list = []
    real_light, real_many = lang.parse_csharp, cs_roslyn.parse_many
    monkeypatch.setattr(lang, "parse_csharp", lambda rel, text: parsed.append(rel) or real_light(rel, text))
    monkeypatch.setattr(cs_roslyn, "parse_many", lambda texts, *a, **k: parsed.extend(texts) or real_many(texts, *a, **k))
    real_tmc = tmc._parse
    monkeypatch.setattr(tmc, "_parse", lambda path, text: parsed.append(Path(path).name) or real_tmc(path, text))

    def vcs(args, data=None):
        p = subprocess.run(["git", "-C", str(root), *args], input=data, capture_output=True)
        return p.returncode, p.stdout

    got = reading_path_cs.measure(root, "HEAD", [str(root / "Shop.cs")], vcs)
    assert got["scope"] == ["Clerk.cs", "Shop.cs", "Till.cs"], got["scope"]
    assert got["analyzer"] == analyzer, got["notes"]
    touched = {Path(p).name for p in parsed}
    assert touched == {"Clerk.cs", "Shop.cs", "Till.cs"}, sorted(touched)[:10]


def test_same_user_turn_re_edit_after_handoff_is_measured_next_batch(tmp_path):
    """同一個使用者回合（回合號不變）交工作後又改同一個 .cs：下一批照檔案指紋認得它變了，照樣量（不照回合號就漏掉）。"""
    root = _repo(tmp_path / "r", {"E.cs": LANDING.format("E")}, CHAIN4)
    jobs: list = []

    def spawn(path):
        job = json.loads(Path(path).read_text(encoding="utf-8"))
        jobs.append(job)
        rph.write_result(Path(job["out"]), rph.run_job(job))

    mods = [{"path": str(root / f), "session_id": _SID, "turn_seq": 5, "last_turn_seq": 5} for f in CHAIN4]
    state = {"turn_seq": 5, "modified_files": mods}
    rph.reading_path_note(state, _SID, {}, spawn=spawn)
    _write(root, {"A.cs": CHAIN4["A.cs"].replace("x * 2", "x * 22")})
    rph.reading_path_note(state, _SID, {}, spawn=spawn)
    assert len(jobs) == 2 and str(root / "A.cs") in jobs[1]["turn_files"], [j["turn_files"] for j in jobs]
    assert str(root / "B.cs") not in jobs[1]["turn_files"], "沒再變的檔不重量"


def test_downstream_finds_the_definition_when_the_file_name_misleads(tmp_path):
    """Store.cs 裡其實是別的型別、Store 定義在 Services.cs：照檔名對上不算數，照樣找到定義所在的檔。"""
    import reading_path_cs
    base = {"Store.cs": "public class StoreConfig\n{\n    public int N;\n}\n",
            "Services.cs": "public class Store\n{\n    public void Put(int n) { if (n > 0) { n--; } }\n}\n",
            "Shop.cs": "public class Shop\n{\n    private Store _s = new Store();\n    public void Sell(int n) { _s.Put(n); }\n}\n"}
    root = _repo(tmp_path / "r", base, {"Shop.cs": base["Shop.cs"].replace("_s.Put(n);", "if (n > 1) { _s.Put(n); }")})

    def vcs(args, data=None):
        p = subprocess.run(["git", "-C", str(root), *args], input=data, capture_output=True)
        return p.returncode, p.stdout

    assert "Services.cs" in reading_path_cs.measure(root, "HEAD", [str(root / "Shop.cs")], vcs)["scope"]


def test_roslyn_build_setup_failure_falls_back_to_light(tmp_path, monkeypatch):
    """快取目錄建不起來（OSError）也算 Roslyn 跑不動：退回輕量解析並註明，不是整批量不出來。"""
    import cs_roslyn
    import reading_path_cs
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(cs_roslyn, "find_roslyn", lambda: {"sdk": "9.9.9", "dir": "x", "tfm": "net9.0", "dotnet": "dotnet"})
    monkeypatch.setattr(cs_roslyn, "CACHE", blocker / "cache")
    root = _repo(tmp_path / "r", {"Svc.cs": SVC_BEFORE, "Repo.cs": REPO}, {"Svc.cs": SVC_AFTER})

    def vcs(args, data=None):
        p = subprocess.run(["git", "-C", str(root), *args], input=data, capture_output=True)
        return p.returncode, p.stdout

    got = reading_path_cs.measure(root, "HEAD", [str(root / "Svc.cs")], vcs)
    assert got["analyzer"] == "light" and any("Roslyn 跑不動" in n for n in got["notes"]), got["notes"]


# ─── 分析器：Roslyn 跑不動退回輕量並註明 ─────────────────────────────────────────

def test_roslyn_failure_falls_back_to_light_with_a_note(tmp_path, monkeypatch):
    import cs_roslyn
    import reading_path_cs
    monkeypatch.setattr(cs_roslyn, "find_roslyn", lambda: {"sdk": "9.9.9", "dir": "x", "tfm": "net9.0", "dotnet": "dotnet"})

    def boom(*a, **k):
        raise cs_roslyn.RoslynError("編不起來")
    monkeypatch.setattr(cs_roslyn, "parse_many", boom)
    root = _repo(tmp_path / "r", {"Svc.cs": SVC_BEFORE, "Repo.cs": REPO}, {"Svc.cs": SVC_AFTER})

    def vcs(args, data=None):
        p = subprocess.run(["git", "-C", str(root), *args], input=data, capture_output=True)
        return p.returncode, p.stdout

    got = reading_path_cs.measure(root, "HEAD", [str(root / "Svc.cs")], vcs)
    assert got["analyzer"] == "light" and any("Roslyn 跑不動" in n and "編不起來" in n for n in got["notes"]), got
    assert [f["func"] for f in got["forwarders"]] == ["Svc.cs::Svc.Save"], "退回輕量照樣量得到"


if __name__ == "__main__":
    rc = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", __file__, "-q", "-p", "no:cacheprovider"]).returncode
    print("READING_PATH_CS_CHECK PASS" if rc == 0 else "READING_PATH_CS_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
