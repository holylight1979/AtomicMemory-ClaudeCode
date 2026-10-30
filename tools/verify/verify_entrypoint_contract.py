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
  ③ 問的那一刻注入（真跑 handler；原訊息逐字不變、卡接在最後）
   13. Stop PickOne：Entry=E04 的卡 → 接「判準卡（E04）」；只有關鍵字命中的卡 → 退路也接；都沒有 → 訊息原樣
   14. Stop 擋訊息（TestFailGate 經 _piggyback）→ 接 E08 的卡；後面附加的預覽不拿來認切入點
   15. PreToolUse deny（USER_DATA_FILE_NEEDS_DECLARATION）→ reason 後接 E20 的卡
   16. MCP need_goal 回覆（樹根對不到原話）→ 回覆後接 E23 的卡
   17. 子代理 prompt：登錄表有 subagent_prompt 路的列 → 卡接在原 prompt 前；沒認出 → 照舊不改 prompt
  ④ 切入點留帳
   18. 每次問 guard-entry.jsonl 多一筆、欄位齊；三張卡超預算 → 帳記 truncated
   19. AI 隨後宣告 → 回應型 declared；又被擋 → denied；沒下文 → none（真跑資料檔閘兩次，照它自己的留帳推）
   20. entry-stats 對假帳算出正確計數、尾行格式對
   21. 入口炸了 → 回空字串＋stderr，問句照原樣送
怎麼跑：pytest -q tools/verify/verify_entrypoint_contract.py，或 python tools/verify/verify_entrypoint_contract.py（尾行 ENTRYPOINT_CONTRACT_CHECK PASS|FAIL）
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("WG_CLAUDE_DIR", str(_ROOT))     # 資料根指本樹：hooks 讀的記憶、state 不碰 live
for p in (_ROOT / "hooks", _ROOT / "lib", _ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import wg_core  # noqa: E402
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


def test_004_edit_metadata_clear_entry_drops_the_line(mem):
    """004：entry=[] 刪掉整行 Entry（舊碼留一行空的「- Entry: 」，11 張規格卡現況就是）；本來沒有 Entry 行就不插。"""
    f = _atom_file(mem, "card-c", "- Entry: E04, E08\n")
    assert atom_io.write_index(mem, "card-c", "memory/cat/card-c.md", ["alpha", "beta"], "test").ok
    before = f.read_text(encoding="utf-8")
    assert atom_io.edit_metadata(f, entry=[], source="test").ok
    after = f.read_text(encoding="utf-8")
    assert "- Entry:" not in after and after == before.replace("- Entry: E04, E08\n", "")       # 只少那一行
    assert "entry" not in _row(mem, "card-c")
    assert atom_io.edit_metadata(f, entry=[], source="test").ok and f.read_text(encoding="utf-8") == after   # 冪等、不插空行
    from lib.atom_spec import ENTRY_LINE_RE
    m = ENTRY_LINE_RE.search("# x\n\n- Entry: \n- Trigger: a\n\n## 知識\n")                    # 解析器對空 Entry 行不炸、不跨行
    assert m and m.group(1).strip() == ""
    empty = _atom_file(mem, "card-d", "- Entry: \n")
    assert atom_io.write_index(mem, "card-d", "memory/cat/card-d.md", ["alpha", "beta"], "test").ok
    assert "entry" not in _row(mem, "card-d")


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
    assert miss == {"entries": [], "cards": [], "truncated": False, "truncated_entries": [], "repeated": [], "note": ""}


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
    """同一問句認出 A、B 兩列：A 只有關鍵字退路卡、B 有 Entry 綁定卡。每列各一份預算 → 兩張都送；
    總上限只夠一張 → 先送 B 的綁定卡（前一列的退路卡不擠掉後一列的專卡）。"""
    reg = _reg({"id": "A1", "rules": [], "markers": ["【甲】"], "paths": ["stop_piggyback"]},
               {"id": "B1", "rules": [], "markers": ["【乙】"], "paths": ["stop_piggyback"]})
    body = [f"- [臨] 判準第 {i} 條，數字只是參考，先看實害。" for i in range(6)]
    kw = _card(tmp_path, "kw-a", triggers=["【甲】"], knowledge=body)
    bound = _card(tmp_path, "bound-b", triggers=["無關"], entry=["B1"], knowledge=body)
    one = ep._estimate_tokens("\n".join(body)) + 5
    both = ep.judgment_cards("【甲】……【乙】", "stop_piggyback", registry=reg, pool=[kw, bound],
                             config={"entrypoint": {"inject_budget_tokens": one}})
    assert both["entries"] == ["A1", "B1"] and both["truncated"] is False
    assert [c["name"] for c in both["cards"]] == ["bound-b", "kw-a"]          # 綁定卡先送
    out = ep.judgment_cards("【甲】……【乙】", "stop_piggyback", registry=reg, pool=[kw, bound],
                            config={"entrypoint": {"inject_budget_tokens": one, "inject_budget_total": one}})
    # 總上限只夠一張：兩列平分，B 的綁定卡先送、A 的退路卡吃不到 B 的那一半
    assert [c["name"] for c in out["cards"]] == ["bound-b", "kw-a"] and out["cards"][0]["via"] == "entry"
    assert out["truncated_entries"] == ["B1", "A1"] and out["note"].count("已截斷") == 2


# ─── 004：預算每個切入點各一份＋總上限；每個切入點內綁定卡在前、短的先送 ───────────────────────
# 第二波題 A′：一句認出好幾個切入點時，第一個切入點把整句共用的 400 用光，後面切入點的專卡送不到（帳 18 筆全 truncated）

def _rows3():
    return _reg(*[{"id": i, "rules": [], "markers": [f"【{i}】"], "paths": ["stop_piggyback"]} for i in ("P1", "P2", "P3")])


def test_004_each_entry_gets_its_own_budget(tmp_path):
    body = [f"- [臨] 判準第 {i} 條，先看實害、誰會痛、多快會痛。" for i in range(8)]
    pool = [_card(tmp_path, f"card-{i}", triggers=["無關"], entry=[i], knowledge=body) for i in ("P1", "P2", "P3")]
    one = ep._estimate_tokens("\n".join(body)) + 5
    out = ep.judgment_cards("【P1】【P2】【P3】", "stop_piggyback", registry=_rows3(), pool=pool,
                            config={"entrypoint": {"inject_budget_tokens": one, "inject_budget_total": one * 3}})
    assert [c["name"] for c in out["cards"]] == ["card-P1", "card-P2", "card-P3"], out["cards"]   # 舊碼：只送 card-P1
    assert out["truncated"] is False and out["truncated_entries"] == []
    capped = ep.judgment_cards("【P1】【P2】【P3】", "stop_piggyback", registry=_rows3(), pool=pool,
                               config={"entrypoint": {"inject_budget_tokens": one, "inject_budget_total": int(one * 1.5)}})
    # 超總上限：平分給三個切入點，每個都送到半張（codex 審：不讓排後面的永遠落空），三個都記截斷
    assert [c["name"] for c in capped["cards"]] == ["card-P1", "card-P2", "card-P3"]
    assert capped["truncated_entries"] == ["P1", "P2", "P3"] and capped["note"].count("已截斷") == 3
    assert sum(ep._estimate_tokens(b.split("\n", 1)[1]) for b in capped["note"].split("\n\n判準卡")) <= int(one * 1.5) + 30
    tight = ep.judgment_cards("【P1】【P2】【P3】", "stop_piggyback", registry=_rows3(), pool=pool,
                              config={"entrypoint": {"inject_budget_tokens": one, "inject_budget_total": 60}})
    assert tight["cards"] == [] and tight["truncated_entries"] == ["P1", "P2", "P3"]        # 有卡被擠掉也留帳
    assert ep.inject_budget({}, "inject_budget_total") == 1200
    assert ep.inject_budget({"entrypoint": {"inject_budget_total": "x"}}, "inject_budget_total") == 1200


def test_004_bound_cards_short_first_keyword_by_hits_then_short(tmp_path):
    reg = _reg({"id": "P1", "rules": [], "markers": ["【P1】", "甲字", "乙字"], "paths": ["stop_piggyback"]})
    long = [f"- [臨] 長卡第 {i} 條判準，寫得很長很長很長。" for i in range(10)]
    short = ["- [臨] 短卡判準一條。"]
    pool = [_card(tmp_path, "bound-long", triggers=["無關"], entry=["P1"], knowledge=long),
            _card(tmp_path, "bound-short", triggers=["無關"], entry=["P1"], knowledge=short),
            _card(tmp_path, "kw-one-short", triggers=["甲字"], knowledge=short),
            _card(tmp_path, "kw-two-long", triggers=["甲字", "乙字"], knowledge=long),
            _card(tmp_path, "kw-one-long", triggers=["乙字"], knowledge=long)]
    got = [(c["name"], via) for c, via in ep.cards_for_entry(reg["entrypoints"][0], pool)]
    assert got == [("bound-short", "entry"), ("bound-long", "entry"),            # 綁定卡：短的先
                   ("kw-two-long", "keyword"), ("kw-one-short", "keyword"), ("kw-one-long", "keyword")]   # 退路：命中多先、同分短先


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
    """Entry 欄可多值（逗號分隔）：只驗卡上解析出的代號含 E04／E08、索引跟檔一致，不綁整行；
    卡上每個代號都拿登錄表那一列的識別字樣問一次，挑卡第一張要是綁定這個代號的專卡（不是關鍵字退路卡）。"""
    mem_dir = _ROOT / "memory"
    text = {n: next(mem_dir.rglob(f"{n}.md")).read_text(encoding="utf-8") for n in (REAL_E04, REAL_E08)}
    codes = {}
    for n, t in text.items():
        m = re.search(r"^- Entry:[ \t]*(.*)$", t, re.MULTILINE)
        codes[n] = [e.strip() for e in (m.group(1) if m else "").split(",") if e.strip()]
    assert "E04" in codes[REAL_E04] and "E08" in codes[REAL_E08], codes
    rows = {a["name"]: a for a in atom_index_json.load_atom_index_json(mem_dir)["atoms"]}
    assert all(sorted(rows[n].get("entry") or []) == sorted(codes[n]) for n in codes), {n: rows[n].get("entry") for n in codes}
    monkeypatch.setattr(ep, "MEMORY_DIR", mem_dir)
    out = ep.judgment_cards(PICK_ONE_TEXT, "stop_piggyback", state={}, config={})
    assert out["cards"] and out["cards"][0]["name"] == REAL_E04 and out["cards"][0]["via"] == "entry"
    assert out["note"].startswith(f"判準卡（{'、'.join(out['cards'][0]['entries'])}）：{REAL_E04}\n- [臨] 判準：")
    reg = {r["id"]: r for r in ep.load_registry()["entrypoints"]}
    pool = ep.card_pool({})
    wide = {"entrypoint": {"inject_budget_tokens": 100000}}            # 預算放大：只驗挑卡順序，不驗截斷
    for name, entries in codes.items():
        for eid in entries:
            row = reg[eid]
            bound = [c for c in pool if eid in c["entry"]]
            shortest = min(bound, key=lambda c: (ep._estimate_tokens(ep._knowledge(c)), c["name"]))["name"]   # ③ 綁定卡短的先
            got = ep.judgment_cards(row["markers"][0], row["paths"][0], pool=pool, config=wide)
            assert eid in got["entries"], (eid, got["entries"])
            assert got["cards"][0]["name"] == shortest and got["cards"][0]["via"] == "entry", (eid, got["cards"][:2])
            assert name in [c["name"] for c in got["cards"] if c["via"] == "entry"], (eid, name)


# ─── ③ 問的那一刻注入（真跑 handler）──────────────────────────────────────────

SID = "sess-entry-0001"
MAP = ("| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 病灶清單 | 量尺 | 檢查器 | 讀路徑 | 第四問 | 層 | 權威 | 上游 | 下游 | 類別 |\n"
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
       "| `Game/` | 戰鬥 | 無 | 無 | 無 | 無 | 無 | 無 | 無 | 單層 | 無 | 無 | 存檔 | code |\n")


@pytest.fixture()
def logs(tmp_path, monkeypatch):
    """guard log 全落 tmp（含 guard-entry.jsonl）；時鐘每筆加一秒，同一秒內寫的帳也分得出先後。"""
    d = tmp_path / "Logs"
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", d)
    tick = itertools.count()
    base = datetime(2026, 10, 21, 9, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(wg_core, "_now_iso", lambda: (base + timedelta(seconds=next(tick))).isoformat(timespec="seconds"))
    return d


def _ledger(d: Path, name: str = "entry") -> list:
    p = d / f"guard-{name}.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def _pool(monkeypatch, cards):
    monkeypatch.setattr(ep, "card_pool", lambda state=None: list(cards))


@pytest.fixture()
def stop_run(tmp_path, monkeypatch, capsys, logs):
    """驅動 handle_stop（照 hooks/verify/verify_pick_one.py 的做法：其他閘關掉或換掉）；回 run(message, **state) → stdout 的 JSON。"""
    import wg_harvest as wh
    import wg_overview as wo
    from handlers import stop as st
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(MAP, encoding="utf-8", newline="\n")
    (proj / "Game").mkdir()
    (proj / "Game" / "Damage.cs").write_text("a\nb\n", encoding="utf-8")
    monkeypatch.setattr(wh, "WORKFLOW_DIR", tmp_path / "workflow")
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    for name, fn in (("_find_session_transcript", lambda *a, **k: None), ("token_warn_payload", lambda *a, **k: ""),
                     ("detect_evasion", lambda *a, **k: None), ("write_state", lambda *a, **k: None),
                     ("_attribute_usefulness", lambda *a, **k: None), ("_detect_uncommitted_files", lambda mf: []),
                     ("_maybe_spawn_user_extract_worker", lambda *a, **k: None), ("_hud_alive", lambda *a, **k: (True, {})),
                     ("_should_deep_postmortem", lambda *a, **k: False), ("reading_path_note", lambda *a, **k: ("", False))):
        monkeypatch.setattr(st, name, fn)
    cfg = {"reconcile_gate": {"enabled": False}, "sync_reminder": {"enabled": False},
           "atom_audit": {"enabled": False}, "aec": {"scan_report_gate": False}, "pick_one": {"enabled": True}}
    mods = [{"path": str(proj / "Game" / "Damage.cs"), "session_id": SID, "turn_seq": 5, "last_turn_seq": 5}]

    def run(message, **extra):
        state = {"phase": "working", "modified_files": mods, "failing_tests": [], "recent_user_prompts": [],
                 "stop_blocked_count": 0, "turn_seq": 5, "session": {"cwd": str(proj)}, **extra}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": SID, "cwd": str(proj), "last_assistant_message": message}, cfg)
        cap = capsys.readouterr()
        run.err = cap.err                    # 斷言失敗時印出來看是哪道閘先走了
        out = cap.out.strip()
        return json.loads(out.splitlines()[-1]) if out else None   # 沒輸出＝放行（v6 提醒類的閘只留帳）
    return run


def test_stop_pickone_is_ledger_only_no_piggyback_card(stop_run, tmp_path, monkeypatch, logs):
    """規則 STOP_REMIND_LEDGER_ONLY：v6 開著「順手看到最該修」在 Stop 是提醒不是擋（GATE_MODE_TABLE 的 PICK_ONE_PRE_CLOSE＝remind）：
    Stop 不送文字（不 block、不 additionalContext），只在 guard-pick_one 留一筆 event=remind；
    因此 stop_piggyback 這條路不再問句、E04 的判準卡在 Stop 不會送、guard-entry 也不記帳（卡池有沒有對得上的卡都一樣）。"""
    bound = _card(tmp_path, "bound", triggers=["無關詞"], entry=["E04"], knowledge=["- [臨] 判準：先問分數最高那條的實害。"])
    kw = _card(tmp_path, "kw", triggers=["順手看到最該修"], knowledge=["- [臨] 退路卡的判準。"])
    for pool in ([], [bound], [kw]):
        _pool(monkeypatch, pool)
        ep.forget_sent(SID)
        assert stop_run("改好了，全部完成。") is None, stop_run.err
    rem = [r for r in _ledger(logs, "pick_one") if r.get("event") == "remind"]
    assert rem and all(r["rule"] == "PICK_ONE_PRE_CLOSE" and r["session_id"] == SID for r in rem), _ledger(logs, "pick_one")
    assert rem[0]["excerpt"].startswith("[Guardian:PickOne]")
    assert not [a for a in _ledger(logs) if a["path"] == "stop_piggyback"]      # 沒問句就沒切入點帳


def test_stop_block_via_piggyback_gets_card_after_previews(stop_run, tmp_path, monkeypatch, logs):
    failing = [{"cmd": "pytest -q tests/test_x.py", "summary": "1 failed", "turn_seq": 5, "session_id": SID}]
    _pool(monkeypatch, [])
    r0 = stop_run("改好了，全部完成。", failing_tests=failing)
    assert r0.get("decision") == "block" and r0["reason"].startswith("[Guardian:TestFailGate]"), r0
    card = _card(tmp_path, "skip-card", triggers=["x"], entry=["E08"], knowledge=["- [臨] 跳過＝這件不做。"])
    _pool(monkeypatch, [card])
    r1 = stop_run("改好了，全部完成。", failing_tests=failing)
    assert r1["reason"] == r0["reason"] + "\n判準卡（E08）：skip-card\n- [臨] 跳過＝這件不做。"
    # 擋訊息寫了引原話的豁免寫法（「：使用者說「」），同一則問句也認出 E09（使用者豁免要引原話）、各記一筆
    last = {a["entry"]: a for a in _ledger(logs) if a["path"] == "stop_piggyback"}
    assert last["E08"]["cards"] == ["skip-card"] and "E09" in last["E08"]["with"]
    assert last["E09"]["cards"] == [] and "E08" in last["E09"]["with"]


def test_subagent_stop_gets_card_but_judge_does_not(tmp_path, monkeypatch, logs):
    """子代理收尾（_code_gate_no_ask）接判準卡；裁判子 session 同一支函式不注入（防裁判觸發裁判）。"""
    from handlers import stop as st
    reason = "[Guardian:ReconcileGate] 寫碼查核\n✗ (a) CLAIM_FIXED_NEEDS_PASS：說修好但沒有改後跑綠的收據"
    blocks = []
    monkeypatch.setattr(st, "_verify_gates", lambda *a, **k: (reason, None, "reconcile"))
    monkeypatch.setattr(st, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(st, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(st, "output_block", blocks.append)
    _pool(monkeypatch, [_card(tmp_path, "claim-card", triggers=["x"], entry=["E10"], knowledge=["- [臨] 轉述不是自己的宣稱。"])])
    state = {"turn_seq": 3}
    own = [{"path": "a.py", "session_id": SID, "turn_seq": 3}]
    for extra in ({"event": "subagent_block", "agent_id": "ag1"}, {"event": "judge_block"}):
        st._code_gate_no_ask({"session_id": SID}, {}, state, SID, own, "", "測試", extra)
    sub, judge = blocks
    assert sub.endswith("\n判準卡（E10）：claim-card\n- [臨] 轉述不是自己的宣稱。") and reason in sub
    assert "判準卡" not in judge and reason in judge
    assert [a["entry"] for a in _ledger(logs)] == ["E10"]                             # 裁判那次不問也不記


@pytest.fixture()
def ptu_world(tmp_path, monkeypatch, logs):
    """照 hooks/verify/verify_data_file_ask.py：假專案 settings.json 已存在、原話沒點名 → DataFileAsk 會擋。回 run(transcript_text)。"""
    from handlers import pre_tool_use as ptu
    proj = tmp_path / "w1" / "qb-report"
    proj.mkdir(parents=True)
    (proj / "settings.json").write_text('{"decimals": 0,}\n', encoding="utf-8")
    (proj / "app.py").write_text("x = 1\n", encoding="utf-8")
    wf = tmp_path / "wf"
    wf.mkdir()
    prompt = "report 的 cli 加一個 --format csv"
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    outputs = []

    def _out(d):
        outputs.append(d)
        raise SystemExit(0)

    def _nothing():
        outputs.append(None)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _nothing)
    # DataFileAsk 只管寫過程式的 session（wg_data_file.coding_session）：state 先放一筆本 session 改過的 .py
    wg_core.write_state(SID, {"session": {"id": SID, "cwd": str(proj)}, "turn_seq": 1,
                              "recent_user_prompts": [prompt], "turn_prompts": [prompt],
                              "modified_files": [{"path": str(proj / "app.py"), "session_id": SID, "turn_seq": 1}]})
    tp = tmp_path / "t.jsonl"

    def run(assistant_text="先看設定怎麼讀"):
        tp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in (
            {"type": "user", "message": {"role": "user", "content": prompt}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": assistant_text}]}})), encoding="utf-8")
        with pytest.raises(SystemExit):
            ptu.handle_pre_tool_use({"tool_name": "Edit", "session_id": SID, "cwd": str(proj), "transcript_path": str(tp),
                                     "tool_input": {"file_path": str(proj / "settings.json"),
                                                    "old_string": '"decimals": 0,', "new_string": '"decimals": 0'}}, {})
        return outputs[-1]
    return run


def _deny_reason(out) -> str:
    hso = (out or {}).get("hookSpecificOutput") or {}
    return hso.get("permissionDecisionReason", "") if hso.get("permissionDecision") == "deny" else ""


def test_pretool_deny_data_file_gets_e20_card(ptu_world, tmp_path, monkeypatch, logs):
    _pool(monkeypatch, [])
    base = _deny_reason(ptu_world())
    assert base.startswith("[Guardian:DataFileAsk]") and "USER_DATA_FILE_NEEDS_DECLARATION" in base and "判準卡" not in base
    card = _card(tmp_path, "data-card", triggers=["x"], entry=["E20"], knowledge=["- [臨] 動資料檔先問使用者會看到什麼。"])
    _pool(monkeypatch, [card])
    got = _deny_reason(ptu_world())
    assert got == base + "\n判準卡（E20）：data-card\n- [臨] 動資料檔先問使用者會看到什麼。"
    asks = [a for a in _ledger(logs) if a["path"] == "pretool_deny"]
    assert [a["entry"] for a in asks] == ["E20", "E20"] and asks[-1]["cards"] == ["data-card"]


def test_pretool_hint_ask_overview_is_remind_not_card(tmp_path, monkeypatch, logs):
    """提問只提醒、不擋（ASK_OVERVIEW_BEFORE_DECISION）那條路：v6 開著改掛下一個工具結果（REMIND_ON_PRIOR_RESULT）——
    PreToolUse 什麼都不送（不 deny、不 additionalContext），guard-ask 留 event=remind；判準卡（E05）不在這裡接、
    guard-entry 也不記。v6 關時提示照舊從 PreToolUse 送，原文逐字、不接卡（判準卡是 v6 才有）。"""
    import wg_ask_gate
    from handlers import pre_tool_use as ptu
    hint = "[Guardian:Ask] ✗ (提問) ASK_OVERVIEW_BEFORE_DECISION：題目涉及改法選擇，但題目提到的部位還沒讀過檔：先讀過部位檔再問"
    hits = [{"rule": "ASK_OVERVIEW_BEFORE_DECISION", "what": "題目提到的部位還沒讀過檔", "fix": "先讀過部位檔再問", "block": False}]
    outputs = []

    def _out(d):
        outputs.append(d)
        raise SystemExit(0)

    def _nothing():
        outputs.append(None)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _nothing)
    monkeypatch.setattr(ptu, "read_state_status", lambda sid: ({"turn_seq": 4}, "missing"))
    monkeypatch.setattr(wg_ask_gate, "on_ask_full", lambda *a, **k: (None, hint, hits))
    _pool(monkeypatch, [_card(tmp_path, "ask-card", triggers=["x"], entry=["E05"], knowledge=["- [臨] 改法選擇先讀部位再問。"])])
    ask = {"session_id": SID, "tool_name": "AskUserQuestion", "tool_input": {"questions": []}}
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use(ask, {})
    assert outputs[-1] is None                                                        # v6 開：PreToolUse 不送
    rem = [r for r in _ledger(logs, "ask") if r.get("event") == "remind"]
    assert [r["rule"] for r in rem] == ["ASK_OVERVIEW_BEFORE_DECISION"] and rem[0]["session_id"] == SID
    assert not _ledger(logs)                                                          # 卡沒送就沒切入點帳
    monkeypatch.setenv("WG_V6", "0")
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use(ask, {})
    hso = outputs[-1]["hookSpecificOutput"]
    assert "permissionDecision" not in hso and hso["additionalContext"] == hint     # v6 關：提示原文、不接卡
    assert not _ledger(logs)


def test_shared_fallbacks_are_independent(monkeypatch):
    """handlers/_shared 的兩個保護匯入互不影響（Codex 002：docdrift 的備援一行曾被切進接卡的 except）。"""
    import importlib
    from handlers import _shared
    try:
        monkeypatch.setitem(sys.modules, "wg_docdrift", None)                         # docdrift 匯入失敗
        mod = importlib.reload(_shared)
        assert mod.DOCDRIFT_AVAILABLE is False and mod.prune_committed_entries is None
        assert mod.entry_note is ep.entry_note                                        # 接卡照常
        monkeypatch.undo()
        monkeypatch.setitem(sys.modules, "wg_entrypoint", None)                       # 接卡模組匯入失敗
        mod = importlib.reload(_shared)
        assert mod.DOCDRIFT_AVAILABLE is True and callable(mod.prune_committed_entries)
        assert mod.entry_note("[Guardian:PickOne] x", "stop_piggyback") == "" and mod.with_note("原文", "卡") == "原文"
    finally:
        monkeypatch.undo()
        importlib.reload(_shared)


def test_mcp_need_goal_reply_gets_e23_card(tmp_path, monkeypatch, capsys, logs):
    import wg_need_goal as ng
    import wg_overview as wo
    from handlers import post_tool_use as pt
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path / "wf")
    (tmp_path / "wf").mkdir()
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_run_companion_hooks", lambda *a: ([], []))
    ng.on_prompt(SID, "讓匯出變快", 1, {})

    def post(goal, cards):
        _pool(monkeypatch, cards)
        state = {"turn_seq": 2}
        monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
        with pytest.raises(SystemExit):
            pt.handle_post_tool_use({"session_id": SID, "tool_name": "mcp__workflow-guardian__need_goal",
                                     "tool_input": {"action": "set", "goal": goal, "new_task": True, "why": "測試換題"},
                                     "tool_response": {}}, {"docdrift": {"enabled": False}})
        return json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    base = post("把稽核紀錄全部留下來給週報", [])
    assert "[NeedGoal] 樹根這幾句原話裡沒有" in base and "判準卡" not in base
    card = _card(tmp_path, "origin-card", triggers=["x"], entry=["E23"], knowledge=["- [臨] 使用者親口說的才標 user。"])
    got = post("把稽核紀錄全部留下來給月報", [card])
    assert "[NeedGoal] 樹根這幾句原話裡沒有" in got
    assert got.endswith("\n判準卡（E23）：origin-card\n- [臨] 使用者親口說的才標 user。")
    assert any(a["entry"] == "E23" and a["path"] == "mcp_reply" and a["cards"] == ["origin-card"] for a in _ledger(logs))


def test_subagent_prompt_path(tmp_path, monkeypatch, logs):
    import wg_atoms
    from handlers import pre_tool_use as ptu
    outputs = []

    def _out(d):
        outputs.append(d)
        raise SystemExit(0)

    def _nothing():
        outputs.append(None)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _nothing)
    monkeypatch.setattr(wg_atoms, "build_injection_blob", lambda *a, **k: ("", []))
    monkeypatch.setattr(ep, "load_registry", lambda path=None: _reg(
        {"id": "X99", "rules": [], "markers": ["【派工單】"], "paths": ["subagent_prompt"]}))
    _pool(monkeypatch, [_card(tmp_path, "brief-card", triggers=["x"], entry=["X99"], knowledge=["- [臨] 派工先寫期望輸出。"])])

    def run(prompt):
        with pytest.raises(SystemExit):
            ptu.handle_pre_tool_use({"session_id": SID, "tool_name": "Agent",
                                     "tool_input": {"prompt": prompt, "subagent_type": "general-purpose"}}, {})
        return outputs[-1]
    out = run("【派工單】查一下 X")
    assert out["hookSpecificOutput"]["updatedInput"]["prompt"] == "判準卡（X99）：brief-card\n- [臨] 派工先寫期望輸出。\n\n【派工單】查一下 X"
    assert run("普通的任務") is None                                                  # 沒認出、也沒記憶 blob → 照舊不改 prompt
    assert [a["entry"] for a in _ledger(logs)] == ["X99"]


# ─── ④ 切入點留帳 ────────────────────────────────────────────────────────────

def test_ledger_fields_and_truncated(tmp_path, logs):
    reg = _reg(E04_ROW)
    long = [f"- [臨] 第 {i} 條判準：數字只是參考，先看實害、看誰會痛、多快會痛。" for i in range(12)]
    cards = [_card(tmp_path, f"c{i}", triggers=["x"], entry=["E04"], knowledge=long) for i in range(3)]
    budget = int(ep._estimate_tokens("\n".join(long)) * 1.5)
    ep.forget_sent(SID)        # 同一個 pytest 行程裡前面的案例用過這個 session（CARD_FULL_ONCE_PER_SESSION 會記它拿過卡）
    note = ep.entry_note(PICK_ONE_TEXT, "stop_piggyback", session_id=SID, registry=reg, pool=cards,
                         config={"entrypoint": {"inject_budget_tokens": budget}})
    assert "已截斷" in note
    (row,) = _ledger(logs)
    assert set(row) == {"at", "event", "session_id", "turn_seq", "entry", "path", "cards", "truncated", "with", "response", "repeated"}
    assert (row["event"], row["entry"], row["path"], row["cards"], row["truncated"], row["response"]) == \
        ("ask", "E04", "stop_piggyback", ["c0", "c1"], True, "none")
    assert ep.entry_note("別的訊息", "stop_piggyback", session_id=SID, registry=reg, pool=cards) == ""
    assert len(_ledger(logs)) == 1                                                    # 沒認出的問句不記帳


def test_response_types_follow_gate_logs(ptu_world, logs, monkeypatch):
    _pool(monkeypatch, [])
    assert _deny_reason(ptu_world())                                                  # 第一次問：擋
    assert _deny_reason(ptu_world())                                                  # 沒宣告又來 → 又擋（上一個回應 denied）
    assert not _deny_reason(ptu_world("動資料檔｜settings.json：修掉多逗號讓 cli 讀得到；幣別會變成檔內的值"))   # 宣告了 → 放行
    asks = [a for a in _ledger(logs) if a["entry"] == "E20"]
    assert len(asks) == 2
    res = ep.resolve_responses(asks, {"data_file": _ledger(logs, "data_file")})
    assert [r["response"] for r in res] == ["denied", "declared"]
    assert res[1]["response_by"] == "data_file:declared"
    lone = ep.resolve_responses([{**asks[0], "session_id": "other"}], {"data_file": _ledger(logs, "data_file")})
    assert lone[0]["response"] == "none"                                              # 別的 session 的帳不算
    # 換了回合才又被問、中間沒有對得上的閘紀錄 → none（可能是另一件事，不硬判 denied）；同回合又被問 → denied（Codex 002）
    a1 = {"at": "2026-10-21T10:00:00+08:00", "session_id": "s9", "entry": "E28", "turn_seq": 3}
    a2 = {**a1, "at": "2026-10-21T10:05:00+08:00", "turn_seq": 4}
    assert [r["response"] for r in ep.resolve_responses([a1, a2], {})] == ["none", "none"]
    a2["turn_seq"] = 3
    assert ep.resolve_responses([a1, a2], {})[0]["response"] == "denied"
    assert ep.resolve_responses([{**a1, "turn_seq": None}, {**a2, "turn_seq": None}], {})[0]["response"] == "none"


def test_entry_stats_counts_and_tail(tmp_path, capsys):
    stats = _load("entry_stats_ut", _ROOT / "tools" / "entry-stats.py")
    d = tmp_path / "Logs"
    d.mkdir()
    now = datetime.now().astimezone()
    at = lambda s: (now + timedelta(seconds=s)).isoformat(timespec="seconds")  # noqa: E731
    asks = [{"at": at(-30), "event": "ask", "session_id": "s1", "turn_seq": 1, "entry": "E20", "path": "pretool_deny",
             "cards": ["c"], "truncated": False, "with": [], "response": "none"},
            {"at": at(-20), "event": "ask", "session_id": "s1", "turn_seq": 1, "entry": "E20", "path": "pretool_deny",
             "cards": ["c", "d"], "truncated": True, "with": ["E26"], "response": "none"},
            {"at": at(-10), "event": "ask", "session_id": "s2", "entry": "E04", "path": "stop_piggyback", "cards": [],
             "truncated": False, "with": [], "response": "none"},
            {"at": (now - timedelta(days=30)).isoformat(timespec="seconds"), "event": "ask", "session_id": "s3",
             "entry": "E04", "path": "stop_piggyback", "cards": [], "truncated": False, "with": [], "response": "none"}]
    (d / "guard-entry.jsonl").write_text("".join(json.dumps(a, ensure_ascii=False) + "\n" for a in asks) + "{壞行\n",
                                         encoding="utf-8")
    (d / "guard-data_file.jsonl").write_text(json.dumps({"at": at(-15), "session_id": "s1", "event": "declared"}) + "\n",
                                             encoding="utf-8")
    (d / "guard-pick_one.jsonl").write_text(json.dumps({"at": at(-5), "session_id": "s2", "event": "recorded"}) + "\n",
                                            encoding="utf-8")
    assert stats.main(["--logs", str(d), "--json"]) == 0
    cap = capsys.readouterr()
    lines = cap.out.strip().splitlines()
    assert re.fullmatch(r"[A-Z][A-Z0-9_]* DONE( \w+=\S+)*", lines[-1])
    assert lines[-1] == "ENTRY_STATS DONE entries=2 asks=3 cards=3 truncated=1"
    data = json.loads("\n".join(lines[:-1]))
    e04, e20 = data["entries"]                                                        # 照登錄表順序
    assert (e20["id"], e20["asks"], e20["asks_with_cards"], e20["cards"], e20["truncated"]) == ("E20", 2, 2, 3, 1)
    assert e20["responses"]["denied"] == 1 and e20["responses"]["declared"] == 1 and e20["with"] == {"E26": 1}
    assert (e04["id"], e04["asks"], e04["responses"]["judged"]) == ("E04", 1, 1)
    assert "讀不懂" in cap.err                                                        # 壞行跳過並說出來
    assert stats.main(["--logs", str(tmp_path / "none")]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "ENTRY_STATS DONE entries=0 asks=0 cards=0 truncated=0"


def test_entry_note_failure_is_quiet_for_gates_but_loud(monkeypatch, capsys, logs):
    def boom(*a, **k):
        raise RuntimeError("卡池炸了")
    monkeypatch.setattr(ep, "judgment_cards", boom)
    assert ep.entry_note(PICK_ONE_TEXT, "stop_piggyback", session_id=SID) == ""
    assert "接判準卡失敗，問句照原樣送：RuntimeError" in capsys.readouterr().err
    assert ep.with_note("原訊息", "") == "原訊息" and ep.with_note("原訊息", "卡") == "原訊息\n卡"


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q"])
    print(f"ENTRYPOINT_CONTRACT_CHECK {'PASS' if rc == 0 else 'FAIL'}")
    sys.exit(0 if rc == 0 else 1)
