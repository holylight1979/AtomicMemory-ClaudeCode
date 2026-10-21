"""verify_entrypoint_contract.py — 切入點契約（hooks/wg_entrypoint.py＋workflow/entrypoints.json＋卡的 Entry 欄）。

cases：
  ① 登錄表
    1. 真登錄表：代號不重複、每列欄位齊、寫的規則名 RULES 都有（打錯或改名會認不到）
    2. 查表不寫死代號：假登錄表的 X99 照樣認得；路不對不認；問句沒字樣不認
    3. 健檢：RULES 少登一條 → 列出；補上 → 不列；卡片 Entry 寫了沒登錄的代號 → 列出；只進 info
    4. 週健檢接線：health-weekly.collect() 帶出登錄表區塊；區塊炸了 → 黃燈一行，不擋其他區塊
  ② 卡綁切入點
    5. build_atom_content：給 entry → `- Entry:` 在 Depends 之後、Related 之前；不給 → 與原本逐字相同
    6. write_index 讀落檔的 Entry 行進索引；upsert_atom entry None 沿用、[] 移除鍵
    7. edit_metadata(entry=…)：檔頭與索引一起改；[] 清空；只改 entry 時 trigger 不動
    8. carry_replace_header：replace 沒給 entry → 舊卡 Entry 行帶回；給 [] → 清掉
    9. sync-atom-index 重建／補登：索引 entry 跟著 atom 檔的 Entry 行
   10. cards_for_entry：Entry 命中的卡排前面；沒 Entry 但 trigger 對得上識別字樣 → 退路；都沒有 → 空
   11. judgment_cards：只取知識段、標「判準卡（E04）：<卡名>」；沒卡 → note 空字串；三張卡超預算 → 截斷、truncated
   12. 真卡：總控台代寫的兩張卡 Entry 補成 E04／E08，索引也帶；PickOne 問句挑到 E04 那張（via=entry）
怎麼跑：pytest -q tools/verify/verify_entrypoint_contract.py，或 python tools/verify/verify_entrypoint_contract.py（尾行 ENTRYPOINT_CONTRACT_CHECK PASS|FAIL）
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for p in (_ROOT / "hooks", _ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import wg_entrypoint as ep  # noqa: E402
import wg_release_rules  # noqa: E402
from lib import atom_index_json, atom_io  # noqa: E402
from lib.atom_spec import build_atom_content  # noqa: E402

PICK_ONE_TEXT = "[Guardian:PickOne] 這次交付改了程式。收尾前順手掃一眼：哪一件最該修？\n順手看到最該修：[部位] <哪一件>"
REAL_E04 = "挑最該修的一件時-分數最高那條先問為什麼不是它-實害比數字重要"
REAL_E08 = "紅測不准用skip躲-使用者說跳過是這件不做-先寫不做行讓程式留帳"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _reg(*rows, not_entry=None):
    return {"entrypoints": list(rows), "not_entrypoints": dict(not_entry or {})}


def _card(tmp: Path, name: str, *, triggers, entry=None, knowledge=None) -> dict:
    f = tmp / f"{name}.md"
    body = "\n".join(knowledge or [f"- [臨] {name} 的判準。"])
    f.write_text(f"# {name}\n\n- Scope: global\n- Confidence: [臨]\n- Trigger: {', '.join(triggers)}\n\n"
                 f"## 知識\n\n{body}\n\n## 行動\n\n- 照判準做\n", encoding="utf-8")
    return {"name": name, "file": f, "triggers": [t.lower() for t in triggers], "entry": list(entry or [])}


@pytest.fixture()
def mem(tmp_path, monkeypatch):
    """暫存記憶根：memory/_atom_index.json（先建好，免觸發索引誕生的版控設定）；稽核紀錄改寫到暫存。"""
    m = tmp_path / "memory"
    (m / "cat").mkdir(parents=True)
    atom_index_json.save_atom_index_json(m, {"version": "1.0", "atoms": []})
    monkeypatch.setattr(atom_io, "AUDIT_LOG", tmp_path / "audit.jsonl")
    return m


def _atom_file(mem: Path, name: str, extra_meta: str = "") -> Path:
    f = mem / "cat" / f"{name}.md"
    f.write_text(f"# {name}\n\n- Scope: global\n- Confidence: [臨]\n- Trigger: alpha, beta\n{extra_meta}"
                 f"- Created-at: 2026-10-21\n\n## 知識\n\n- [臨] 內容\n\n## 行動\n\n- 做\n", encoding="utf-8")
    return f


def _row(mem: Path, name: str) -> dict:
    return next(a for a in atom_index_json.load_atom_index_json(mem)["atoms"] if a["name"] == name)


# ─── ① 登錄表 ────────────────────────────────────────────────────────────────

def test_real_registry_well_formed():
    reg = ep.load_registry()
    ids = [r["id"] for r in reg["entrypoints"]]
    assert len(ids) >= 27 and len(ids) == len(set(ids))
    for r in reg["entrypoints"]:
        assert set(r) >= {"id", "name", "rules", "markers", "paths", "feeds", "asks", "expects"}, r["id"]
    registered = {s for r in reg["entrypoints"] for s in r["rules"]}
    assert registered - set(wg_release_rules.RULES) == set()
    assert set(reg["not_entrypoints"]) - set(wg_release_rules.RULES) == set()
    assert registered & set(reg["not_entrypoints"]) == set()


def test_match_is_table_driven():
    fake = _reg({"id": "X99", "rules": ["SOME_RULE"], "markers": ["【假字樣】"], "paths": ["pretool_deny"]})
    assert [r["id"] for r in ep.match_entries("擋：✗ SOME_RULE：…", "pretool_deny", fake)] == ["X99"]
    assert [r["id"] for r in ep.match_entries("前面【假字樣】後面", "pretool_deny", fake)] == ["X99"]
    assert ep.match_entries("擋：✗ SOME_RULE", "stop_piggyback", fake) == []      # 那列沒登這條路
    assert ep.match_entries("完全無關的訊息", "pretool_deny", fake) == []
    assert ep.match_entries("", "pretool_deny", fake) == []
    # 真登錄表：PickOne 的 Stop 續跑提醒認成 E04；同一段字放在 PreToolUse deny 不認（E04 沒登那條路）
    assert [r["id"] for r in ep.match_entries(PICK_ONE_TEXT, "stop_piggyback")] == ["E04"]
    assert ep.match_entries(PICK_ONE_TEXT, "pretool_deny") == []


def test_registry_unreadable_is_empty_and_loud(tmp_path, capsys):
    bad = tmp_path / "entrypoints.json"
    bad.write_text("{not json", encoding="utf-8")
    assert ep.load_registry(bad) == {"entrypoints": [], "not_entrypoints": {}}
    assert "格式壞了" in capsys.readouterr().err
    assert ep.load_registry(tmp_path / "nope.json")["entrypoints"] == []
    assert "讀不到" in capsys.readouterr().err
    # 合法 JSON、欄位型別錯（Codex 重現：{"entrypoints":1} 會拋 TypeError）→ 一樣回空表、浮 stderr
    for i, body in enumerate(('{"entrypoints": 1}', '{"not_entrypoints": 1}', '[1, 2]')):
        f = tmp_path / f"shape{i}.json"
        f.write_text(body, encoding="utf-8")
        assert ep.load_registry(f) == {"entrypoints": [], "not_entrypoints": {}}
        assert "格式壞了" in capsys.readouterr().err


def test_health_lists_unregistered_rule_then_clears():
    rules = ["RULE_A", "RULE_B", "RULE_C"]
    reg = _reg({"id": "E01", "rules": ["RULE_A"], "markers": [], "paths": ["pretool_deny"]}, not_entry={"RULE_B": "判法定義"})
    info = ep.health_block(reg, rules, [])["info"]
    assert len(info) == 1 and "沒登錄" in info[0] and "RULE_C" in info[0] and "RULE_A" not in info[0] and "RULE_B" not in info[0]
    reg["entrypoints"][0]["rules"].append("RULE_C")
    assert ep.health_block(reg, rules, [])["info"] == []
    # 卡片寫了沒登錄的代號、登錄表寫了 RULES 沒有的規則名、代號重複，各列一行；健檢只回 info
    reg["entrypoints"].append({"id": "E01", "rules": ["RULE_GONE"], "markers": [], "paths": []})
    out = ep.health_block(reg, rules, [{"name": "card-x", "entry": ["E77"]}])
    assert set(out) == {"info"}
    text = "\n".join(out["info"])
    assert "card-x→E77" in text and "RULE_GONE" in text and "代號重複" in text


@pytest.fixture()
def hw(tmp_path, monkeypatch):
    mod = _load("health_weekly_entry_ut", _ROOT / "tools" / "health-weekly.py")
    for k, v in (("MEMORY", tmp_path / "memory"), ("WORKFLOW", tmp_path / "workflow"),
                 ("REPORT_DIR", tmp_path / "workflow" / "health-reports"),
                 ("LAST_RUN", tmp_path / "workflow" / "health-last-run.json")):
        monkeypatch.setattr(mod, k, v)
    (tmp_path / "workflow").mkdir()
    (tmp_path / "memory" / "_vectordb").mkdir(parents=True)
    monkeypatch.setattr(mod, "_load_config", lambda: {"tool_selftests": [], "depends_coverage_min": 0,
                                                       "provenance": {"enabled": False}})
    monkeypatch.setattr(mod, "_run_json", lambda args, timeout=300: {})
    monkeypatch.setattr(mod, "_run_check", lambda args, timeout=120: (True, ""))
    monkeypatch.setattr(mod, "_episodic_status", lambda cut: (None, {"counts": {"generated": 0, "skipped": 0, "failed": 0}, "reasons": {}}))
    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    return mod


def test_health_weekly_carries_entry_block(hw, monkeypatch):
    monkeypatch.setattr(ep, "health_block", lambda: {"info": ["切入點登錄表：假的一行"]})
    res = hw.collect()
    assert "切入點登錄表：假的一行" in res["info"]
    assert not any("切入點登錄表" in x for x in res["red"] + res["yellow"])

    def boom():
        raise RuntimeError("登錄表炸了")
    monkeypatch.setattr(ep, "health_block", boom)
    res = hw.collect()
    assert any(x.startswith("切入點登錄表區塊執行失敗：RuntimeError") for x in res["yellow"])
    assert not any("切入點登錄表" in x for x in res["red"])


# ─── ② 卡綁切入點：Entry 欄 ─────────────────────────────────────────────────

_BUILD = dict(title="t", scope="global", confidence="[臨]", triggers=["a"], knowledge=["k"],
              created_at="2026-10-21", depends=["path:x"], related=["r"])


def test_build_renders_entry_between_depends_and_related():
    plain = build_atom_content(**_BUILD)
    with_entry = build_atom_content(**_BUILD, entry=["E04", "E08"])
    lines = with_entry.split("\n")
    i = lines.index("- Entry: E04, E08")
    assert lines[i - 1] == "- Depends: path:x" and lines[i + 1] == "- Related: r"
    assert with_entry.replace("- Entry: E04, E08\n", "") == plain
    assert build_atom_content(**_BUILD, entry=[]) == plain and "Entry" not in plain


def test_write_index_reads_entry_line_and_upsert_semantics(mem):
    f = _atom_file(mem, "card-a", "- Entry: E04, E08\n")
    assert atom_io.write_index(mem, "card-a", "memory/cat/card-a.md", ["alpha", "beta"], "test").ok
    assert _row(mem, "card-a")["entry"] == ["E04", "E08"]
    atom_index_json.upsert_atom(mem, "card-a", "memory/cat/card-a.md", ["alpha", "beta"])          # entry 沒給 → 沿用
    assert _row(mem, "card-a")["entry"] == ["E04", "E08"]
    atom_index_json.upsert_atom(mem, "card-a", "memory/cat/card-a.md", ["alpha", "beta"], entry=[])  # [] → 移除鍵
    assert "entry" not in _row(mem, "card-a")
    f.write_text(f.read_text(encoding="utf-8").replace("- Entry: E04, E08\n", ""), encoding="utf-8")
    assert atom_io.write_index(mem, "card-a", "memory/cat/card-a.md", ["alpha", "beta"], "test").ok
    assert "entry" not in _row(mem, "card-a")


def test_edit_metadata_entry_updates_file_and_index(mem):
    f = _atom_file(mem, "card-b")
    assert atom_io.write_index(mem, "card-b", "memory/cat/card-b.md", ["alpha", "beta"], "test").ok
    r = atom_io.edit_metadata(f, entry=["E20"], source="test")
    assert r.ok, r.error
    text = f.read_text(encoding="utf-8")
    assert "- Entry: E20\n" in text and "- Trigger: alpha, beta\n" in text
    row = _row(mem, "card-b")
    assert row["entry"] == ["E20"] and row["triggers"] == ["alpha", "beta"]
    assert atom_io.edit_metadata(f, entry=[], source="test").ok
    assert "entry" not in _row(mem, "card-b")
    assert "E20" not in f.read_text(encoding="utf-8")


def test_replace_carries_or_clears_entry():
    old = build_atom_content(**_BUILD, entry=["E04"])
    built = build_atom_content(**{**_BUILD, "knowledge": ["新內容"]})
    kept = atom_io.carry_replace_header(old, built, atom_io.given_header_keys({}))
    assert "- Entry: E04" in kept and "新內容" in kept
    cleared = atom_io.carry_replace_header(old, built, atom_io.given_header_keys({"entry": []}))
    assert "Entry" not in cleared


def test_sync_atom_index_carries_entry(mem):
    sai = _load("sync_atom_index_entry_ut", _ROOT / "tools" / "sync-atom-index.py")
    _atom_file(mem, "card-c", "- Entry: E10\n")
    _atom_file(mem, "card-d")
    atoms = sai.scan_atom_files(mem, mem.parent)
    assert {a.name: a.entry for a in atoms.values()} == {"card-c": ["E10"], "card-d": []}
    sai.rebuild_index(mem, mem.parent, atoms)
    assert _row(mem, "card-c")["entry"] == ["E10"] and "entry" not in _row(mem, "card-d")
    # 補登路徑：索引有列但 entry 跟檔不同 → 對齊檔
    atom_index_json.upsert_atom(mem, "card-c", "memory/cat/card-c.md", ["alpha", "beta"], entry=[])
    sai.add_to_index_from_frontmatter(atoms, sai.load_index_rows(mem), mem)
    assert _row(mem, "card-c")["entry"] == ["E10"]


# ─── ② 依切入點查卡 ─────────────────────────────────────────────────────────

E04_ROW = {"id": "E04", "rules": [], "markers": ["[Guardian:PickOne]", "順手看到最該修："], "paths": ["stop_piggyback"]}


def test_cards_for_entry_entry_first_then_keyword(tmp_path):
    bound = _card(tmp_path, "bound", triggers=["無關詞"], entry=["E04"])
    kw = _card(tmp_path, "kw", triggers=["順手看到最該修"])
    other = _card(tmp_path, "other", triggers=["完全不相干"], entry=["E99"])
    got = ep.cards_for_entry(E04_ROW, [kw, other, bound])
    assert [(c["name"], via) for c, via in got] == [("bound", "entry"), ("kw", "keyword")]
    assert ep.cards_for_entry(E04_ROW, [other]) == []


def test_judgment_cards_note_and_empty(tmp_path):
    reg = _reg(E04_ROW)
    bound = _card(tmp_path, "bound", triggers=["x"], entry=["E04"], knowledge=["- [臨] 判準：先問數字最高那條的實害。"])
    out = ep.judgment_cards(PICK_ONE_TEXT, "stop_piggyback", registry=reg, pool=[bound], config={})
    assert out["entries"] == ["E04"] and out["truncated"] is False
    assert out["note"] == "判準卡（E04）：bound\n- [臨] 判準：先問數字最高那條的實害。"
    assert "## 行動" not in out["note"] and "Trigger" not in out["note"]
    none = ep.judgment_cards(PICK_ONE_TEXT, "stop_piggyback", registry=reg, pool=[], config={})
    assert none["entries"] == ["E04"] and none["note"] == "" and none["cards"] == []
    miss = ep.judgment_cards("別的訊息", "stop_piggyback", registry=reg, pool=[bound], config={})
    assert miss == {"entries": [], "cards": [], "truncated": False, "note": ""}


def test_judgment_cards_budget_truncates(tmp_path):
    reg = _reg(E04_ROW)
    long = [f"- [臨] 第 {i} 條判準：數字只是參考，先看實害、看誰會痛、多快會痛。" for i in range(12)]
    cards = [_card(tmp_path, f"c{i}", triggers=["x"], entry=["E04"], knowledge=long) for i in range(3)]
    full = ep._estimate_tokens("\n".join(long))
    budget = int(full * 1.5)
    out = ep.judgment_cards(PICK_ONE_TEXT, "stop_piggyback", registry=reg, pool=cards,
                            config={"entrypoint": {"inject_budget_tokens": budget}})
    assert out["truncated"] is True
    assert [c["name"] for c in out["cards"]] == ["c0", "c1"]          # 第三張沒送
    assert "已截斷" in out["note"] and "判準卡（E04）：c2" not in out["note"]
    assert ep.inject_budget({}) == 400 and ep.inject_budget({"entrypoint": {"inject_budget_tokens": "x"}}) == 400


def test_bound_cards_beat_earlier_rows_keyword_cards(tmp_path):
    """同一問句認出 A、B 兩列：A 只有關鍵字退路卡、B 有 Entry 綁定卡，預算只夠一張 → 送 B 的綁定卡。"""
    reg = _reg({"id": "A1", "rules": [], "markers": ["【甲】"], "paths": ["stop_piggyback"]},
               {"id": "B1", "rules": [], "markers": ["【乙】"], "paths": ["stop_piggyback"]})
    body = [f"- [臨] 判準第 {i} 條，數字只是參考，先看實害。" for i in range(6)]
    kw = _card(tmp_path, "kw-a", triggers=["【甲】"], knowledge=body)
    bound = _card(tmp_path, "bound-b", triggers=["無關"], entry=["B1"], knowledge=body)
    one = ep._estimate_tokens("\n".join(body)) + 5
    out = ep.judgment_cards("【甲】……【乙】", "stop_piggyback", registry=reg, pool=[kw, bound],
                            config={"entrypoint": {"inject_budget_tokens": one}})
    assert out["entries"] == ["A1", "B1"]
    assert [c["name"] for c in out["cards"]] == ["bound-b"] and out["cards"][0]["via"] == "entry"
    assert out["truncated"] is True and "kw-a" not in out["note"]


def test_real_registry_markers_not_too_generic():
    """識別字樣不能是十幾處訊息都當範例用的字（Codex：E07 的「不做｜」會讓 E08 訊息裡的範例誤配 E07）。"""
    texts = {r["id"]: r["markers"] for r in ep.load_registry()["entrypoints"]}
    assert "不做｜" not in texts["E07"]
    assert [r["id"] for r in ep.match_entries("[Guardian:TestFailGate] 範例：不做｜x", "stop_piggyback")] == ["E08"]


def test_card_pool_visibility_and_superseded(tmp_path, monkeypatch):
    m = tmp_path / "memory"
    (m / "personal" / "someone").mkdir(parents=True)
    (m / "cat").mkdir()
    for rel in ("cat/pub.md", "personal/someone/mine.md", "cat/old.md"):
        (m / rel).write_text("# x\n\n## 知識\n\n- k\n", encoding="utf-8")
    atom_index_json.save_atom_index_json(m, {"version": "1.0", "atoms": [
        {"name": "pub", "path": "memory/cat/pub.md", "triggers": ["A"], "scope": "global", "entry": ["E04"]},
        {"name": "mine", "path": "memory/personal/someone/mine.md", "triggers": ["a"], "scope": "personal"},
        {"name": "old", "path": "memory/cat/old.md", "triggers": ["a"], "scope": "global"},
    ]})
    monkeypatch.setattr(ep, "MEMORY_DIR", m)
    state = {"atom_index": {"superseded": ["old"]}}
    names = {c["name"]: c for c in ep.card_pool(state)}
    assert set(names) == {"pub"} and names["pub"]["entry"] == ["E04"] and names["pub"]["triggers"] == ["a"]
    state["user_identity"] = {"user": "someone", "roles": []}
    assert {c["name"] for c in ep.card_pool(state)} == {"pub", "mine"}


# ─── ② 真卡（總控台代寫的兩張，Entry 由 edit_metadata 補）─────────────────────

def test_real_cards_bound_and_picked(monkeypatch):
    mem_dir = _ROOT / "memory"
    text = {n: next(mem_dir.rglob(f"{n}.md")).read_text(encoding="utf-8") for n in (REAL_E04, REAL_E08)}
    assert "\n- Entry: E04\n" in text[REAL_E04] and "\n- Entry: E08\n" in text[REAL_E08]
    rows = {a["name"]: a for a in atom_index_json.load_atom_index_json(mem_dir)["atoms"]}
    assert rows[REAL_E04].get("entry") == ["E04"] and rows[REAL_E08].get("entry") == ["E08"]
    monkeypatch.setattr(ep, "MEMORY_DIR", mem_dir)
    out = ep.judgment_cards(PICK_ONE_TEXT, "stop_piggyback", state={}, config={})
    assert out["cards"] and out["cards"][0] == {"name": REAL_E04, "entries": ["E04"], "via": "entry"}
    assert out["note"].startswith(f"判準卡（E04）：{REAL_E04}\n- [臨] 判準：")


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q"])
    print(f"ENTRYPOINT_CONTRACT_CHECK {'PASS' if rc == 0 else 'FAIL'}")
    sys.exit(0 if rc == 0 else 1)
