"""verify_mcp_write_gate.py — 寫卡的衝突宣告／去重宣告：照退件訊息改一次就收，不再退件循環。

做什麼：
1. 衝突宣告（tools/memory-conflict-detector.py write-check）：要宣告的範圍是這次向量前幾名、不隨本地模型標籤翻面；
   多宣告不在名單的卡不算錯；守門總開關關 → 照門檻判、不要求宣告。
2. 去重宣告（tools/memory-write-gate.py）：of 不在這次前 3 名、但在這次比對的層裡存在 → 收；沒候選但宣告 same／supersedes →
   照宣告走（找不到那張卡就拒寫說明，不另建新卡）；舊卡已滿 → 訊息直接給「壓縮舊卡（replace）或改寫進文件」。
3. 流程級：第一次被退 → 照退件訊息改一次重送 → 收（退件只有一次）。
不碰 live：向量服務與本地模型一律替身；留帳收進 list；去重比對層裡的卡建在 pytest 的隔離資料根、案例結束刪掉。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_mcp_write_gate.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.parse
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CODE_ROOT = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CODE_ROOT))

import wg_core  # noqa: E402
from lib.project_root import claude_data_dir  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, CODE_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


det = _load("mcp_write_gate_detector", "tools/memory-conflict-detector.py")
gate = _load("mcp_write_gate_gate", "tools/memory-write-gate.py")


# ─── 1. 衝突宣告 ─────────────────────────────────────────────────────────────

def _hit(atom, sim):
    return {"atom_name": atom, "score": sim, "text": f"fact of {atom}", "file_path": f"/p/.claude/memory/shared/{atom}.md",
            "confidence": "[觀]", "layer": "shared"}


@pytest.fixture
def ledger(monkeypatch):
    got = []
    monkeypatch.setattr(wg_core, "append_guard_log", lambda guard, payload: got.append((guard, dict(payload))))
    return got


def _check(monkeypatch, hits, labels, declared=None):
    """labels：{卡名: [本地模型逐次回的標籤]}——同一張卡 CONTRADICT 會複驗一次，要給兩個。"""
    queues = {k: list(v) for k, v in labels.items()}
    monkeypatch.setattr(det, "vector_search", lambda *a, **k: hits)
    monkeypatch.setattr(det, "_classify_match", lambda content, h: queues[h["atom_name"]].pop(0))
    return det.run_write_check("incoming fact", None, "shared", declared=declared, title="new-card")


TOP3 = [_hit("a", 0.92), _hit("b", 0.90), _hit("c", 0.88)]


def test_flow_conflict_refused_once_then_accepted_although_small_model_flips(monkeypatch, ledger):
    """會紅：舊碼只列本地模型標出的卡（這次是 a）要宣告；重送時模型改標 b、c → a「不在候選」、b c「沒宣告」→ 再退，永遠對不上。
    現在：名單是向量前 3 名，照第一次退件訊息逐張宣告，重送不管模型怎麼翻都收。"""
    first = _check(monkeypatch, TOP3, {"a": ["CONTRADICT", "CONTRADICT"], "b": ["UNRELATED"], "c": ["AGREE"]})
    assert first["verdict"] == "need_declaration"
    names = [c["atom_name"] for c in first["candidates"]]
    assert names == ["a", "b", "c"]
    decl = [{"of": n, "verdict": "not_conflict", "why": "舊卡講另一個專案的設定，範圍不同"} for n in names]
    second = _check(monkeypatch, TOP3, {"a": ["UNRELATED"], "b": ["EXTEND"], "c": ["CONTRADICT", "CONTRADICT"]}, declared=decl)
    assert second["verdict"] == "ok", second
    assert [d["of"] for d in second["declared"]] == ["a", "b", "c"]
    assert [p["of"] for g, p in ledger if g == "conflict_declared"] == ["a", "b", "c"]


def test_extra_declaration_not_in_top_is_accepted(monkeypatch, ledger):
    """會紅：舊碼多寫一張不在候選的卡 → 「不在候選」退件。現在略過那條、浮 warning，照收。"""
    decl = [{"of": "a", "verdict": "not_conflict", "why": "範圍不同"}, {"of": "zzz", "verdict": "conflict", "why": "上一輪名單裡的卡"}]
    out = _check(monkeypatch, [_hit("a", 0.9)], {"a": ["CONTRADICT", "CONTRADICT"]}, declared=decl)
    assert out["verdict"] == "ok" and [d["of"] for d in out["declared"]] == ["a"]
    assert any("zzz" in w and "not in this run's vector top" in w for w in out["warnings"])


def test_same_name_in_two_layers_judged_separately(monkeypatch, ledger):
    """不同層同名卡各判一次：名單寫成 <layer>:<卡名>，只宣告卡名不算涵蓋（不讓排前面那張遮住後面那張衝突卡）。"""
    hits = [{**_hit("settings", 0.93), "layer": "global"}, {**_hit("settings", 0.91), "layer": "shared:proj"}]
    labels = {"settings": ["UNRELATED", "CONTRADICT", "CONTRADICT"]}
    out = _check(monkeypatch, hits, labels, declared=[{"of": "settings", "verdict": "not_conflict", "why": "工具不同"}])
    assert out["verdict"] == "need_declaration"
    assert [c["ref"] for c in out["candidates"]] == ["global:settings", "shared:proj:settings"]
    decl = [{"of": "global:settings", "verdict": "not_conflict", "why": "講工具 A"},
            {"of": "shared:proj:settings", "verdict": "conflict", "why": "同一設定鍵說法相反"}]
    out = _check(monkeypatch, hits, {"settings": ["UNRELATED", "CONTRADICT", "CONTRADICT"]}, declared=decl)
    assert out["verdict"] == "contradict" and out["primary"] == "settings"
    assert [(p["of"], p["event"]) for g, p in ledger if g == "conflict_declared"] == [
        ("global:settings", "not_conflict"), ("shared:proj:settings", "conflict")]


def test_v6_off_threshold_verdict_without_declaration(monkeypatch, ledger):
    """會紅：舊碼不看守門總開關，關著也要 AI 宣告。關時回到門檻判：EXTEND≥0.85 → extend_overlap（MCP 端改道待審草稿）、
    穩定 CONTRADICT → contradict（待審報告）；帶了宣告也不採用。"""
    monkeypatch.setenv("WG_V6", "0")
    out = _check(monkeypatch, [_hit("a", 0.9)], {"a": ["EXTEND"]})
    assert out["verdict"] == "extend_overlap" and "candidates" not in out and "detector_verdict" not in out
    out = _check(monkeypatch, [_hit("a", 0.9)], {"a": ["CONTRADICT", "CONTRADICT"]},
                 declared=[{"of": "a", "verdict": "not_conflict", "why": "範圍不同"}])
    assert out["verdict"] == "contradict" and out["primary"] == "a" and "declared" not in out
    assert not [p for g, p in ledger if g == "conflict_declared"]


# ─── 2. 去重宣告 ─────────────────────────────────────────────────────────────

CFG = {"enabled": True, "dedup_score": 0.80, "knowledge_budget_bytes": 3072}
LAYERS = ["global", "extra:local-atoms"]
CONTENT = "[臨] hook 的 PreToolUse 在 Edit payload 生成後才觸發 → 寫前提醒要放 PostToolUse，路徑 ~/.claude/hooks/x.py"
TARGET = "mcp-write-gate-loop-target"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def audits(monkeypatch):
    seen = []
    monkeypatch.setattr(gate, "write_audit_log", lambda action, *a, **k: seen.append({"action": action, **k}))
    return seen


@pytest.fixture
def target_card():
    """這次比對的層（extra:local-atoms）裡的一張真卡：建在隔離資料根，案例結束刪掉。"""
    p = claude_data_dir() / "_AIDocs" / "_atoms" / "MemDev" / f"{TARGET}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"# {TARGET}\n\n- Scope: global\n\n## 知識\n\n- [臨] hook 時序：PreToolUse 拿到的是已生成的 payload\n\n## 行動\n\n- 行動行\n",
                 encoding="utf-8", newline="\n")
    yield p
    p.unlink()


def _vector(monkeypatch, hits):
    """假向量服務：照真服務先濾 min_score 再截 top_k。"""
    def fake_urlopen(req, timeout=0):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)
        min_score, top_k = float(q["min_score"][0]), int(q["top_k"][0])
        rows = sorted((h for h in hits if h["score"] >= min_score), key=lambda h: -h["score"])[:top_k]
        return _Resp(json.dumps(rows).encode("utf-8"))
    monkeypatch.setattr(gate.urllib.request, "urlopen", fake_urlopen)


def _vhit(name, score, layer="global"):
    return {"atom_name": name, "score": score, "text": f"{name} 的命中段", "file_path": "", "layer": layer}


OTHERS = [_vhit("other-1", 0.90), _vhit("other-2", 0.86), _vhit("other-3", 0.83)]


def _eval(content=CONTENT, **kw):
    return gate.evaluate(content, config=CFG, layers=LAYERS, title="新卡", **kw)


def test_same_of_card_in_layers_but_not_top3_accepted(monkeypatch, audits, target_card):
    """會紅：舊碼 of 只認這次前 3 名 → 「不在這次列出的候選卡裡」退件。現在那張卡在這次比對的層裡就收。"""
    _vector(monkeypatch, OTHERS)
    r = _eval(dedupe={"verdict": "same", "of": TARGET, "why": "同一條：上一輪候選裡的那張"})
    assert r["action"] == "append", r
    assert r["append_to"] == {"atom_name": TARGET, "layer": "extra:local-atoms"}
    assert r["dedupe_declared"] == {"verdict": "same", "of": TARGET, "why": "同一條：上一輪候選裡的那張", "score": None}
    assert "score=" not in r["reason"]


def test_of_missing_everywhere_still_refused_with_where(monkeypatch, audits, target_card):
    _vector(monkeypatch, OTHERS)
    r = _eval(dedupe={"verdict": "same", "of": "no-such-card", "why": "同一條"})
    assert r["action"] == "skip" and r["need_declaration"] and [c["atom_name"] for c in r["candidates"]] == ["other-1", "other-2", "other-3"]
    assert "of「no-such-card」不在這次列出的候選卡裡，這次比對的層（global、extra:local-atoms）也沒有這張卡" in r["reason"]
    r = _eval(dedupe={"verdict": "same", "of": f"shared:c--x:{TARGET}", "why": "同一條"})   # 寫的層不在這次比對範圍
    assert r["action"] == "skip" and r["need_declaration"]


def test_no_candidates_same_follows_declaration(monkeypatch, audits, target_card):
    """會紅：舊碼沒候選時宣告整份忽略、另建新卡（宣告 same 卻多一張卡）。現在照宣告併入那張卡。"""
    _vector(monkeypatch, [_vhit(TARGET, 0.5, "extra:local-atoms")])   # 相似度沒到門檻
    r = _eval(dedupe={"verdict": "same", "of": TARGET, "why": "同一條"})
    assert r["action"] == "append" and r["append_to"]["atom_name"] == TARGET and "dedupe_note" not in r
    r = _eval(dedupe={"verdict": "supersedes", "of": TARGET, "why": "新卡取代舊卡"})
    assert r["action"] == "add" and r["dedupe_declared"]["verdict"] == "supersedes" and r["dedupe_declared"]["of"] == TARGET
    assert [a["of"] for a in audits if a["action"] == "dedupe_declared"] == [TARGET, TARGET]


def test_no_candidates_declared_card_missing_refuses_not_new_card(monkeypatch, audits):
    """沒候選、宣告 same 但那張卡不在比對的層 → 拒寫說明（不悄悄另建新卡）；different 照常寫、附 note。"""
    _vector(monkeypatch, [])
    r = _eval(dedupe={"verdict": "same", "of": "no-such-card", "why": "同一條"})
    assert r["action"] == "skip" and r["need_declaration"] and r["candidates"] == []
    assert r["reason"].startswith("宣告不收：of「no-such-card」") and "這次沒有相似候選" in r["reason"] and "拿掉 dedupe" in r["reason"]
    r = _eval(dedupe={"verdict": "different", "of": "whatever", "why": "不同的事"})
    assert r["action"] == "add" and r["dedupe_note"].startswith("dedupe 宣告已忽略")


def test_supersedes_ambiguous_name_across_layers_refused(monkeypatch, audits, target_card):
    """Supersedes 只記卡名：比對的層裡兩張同名 → 拒收並說明（不讓取代落到另一張）；只有一張照收。"""
    twin = claude_data_dir() / "memory" / "工作流" / f"{TARGET}.md"
    twin.write_text(target_card.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    try:
        _vector(monkeypatch, [])
        r = _eval(dedupe={"verdict": "supersedes", "of": f"extra:local-atoms:{TARGET}", "why": "新卡取代"})
        assert r["action"] == "skip" and r["need_declaration"]
        assert "extra:local-atoms、global 都有同名卡" in r["reason"] and "Supersedes 只記卡名" in r["reason"]
        r = _eval(dedupe={"verdict": "same", "of": f"extra:local-atoms:{TARGET}", "why": "同一條"})
        assert r["action"] == "append" and r["append_to"] == {"atom_name": TARGET, "layer": "extra:local-atoms"}
    finally:
        twin.unlink()
    r = _eval(dedupe={"verdict": "supersedes", "of": TARGET, "why": "新卡取代"})
    assert r["action"] == "add" and r["dedupe_declared"]["of"] == TARGET


def test_full_card_append_message_gives_exits(tmp_path):
    """會紅：舊碼舊卡滿了只說「個案事實移文件」，縮了內容重送還是滿。現在直接講壓縮舊卡（replace）或改寫進文件。"""
    old = tmp_path / "full-card.md"
    pad = "這段是部位的真相與邊界說明" * 24
    lines = "".join(f"- [臨] {i} {pad}\n" for i in range(4))   # 一行約 940 bytes，四行已過 3072
    old.write_text(f"# full-card\n\n## 知識\n\n{lines}\n## 行動\n\n- 行動\n", encoding="utf-8", newline="\n")
    r = gate.evaluate("[臨] 補一條短的", config=CFG, title="full-card", mode="append", existing_path=str(old))
    assert r["action"] == "skip"
    assert "既有卡 full-card 的 knowledge 區已滿" in r["reason"] and "壓縮舊卡（mode=replace" in r["reason"]
    assert f"改寫進文件 {r['route_to']}" in r["reason"] and "不截斷" in r["reason"]


def test_flow_dedupe_refused_once_then_shrunk_resend_accepted(monkeypatch, audits, target_card):
    """流程級，會紅：第一次相似被退、列出候選（含 TARGET）；照訊息宣告 same of=TARGET，順手縮了內容重送 →
    舊碼重算的前 3 名換了、TARGET 不在 → 再退。現在 TARGET 還在比對的層裡就收，退件只有一次。"""
    _vector(monkeypatch, [_vhit(TARGET, 0.91, "extra:local-atoms"), *OTHERS])
    first = _eval()
    assert first["action"] == "skip" and first["need_declaration"] and first["candidates"][0]["atom_name"] == TARGET
    _vector(monkeypatch, OTHERS)   # 縮過的內容：相似的鄰居換了一批
    second = _eval(content="[臨] PreToolUse 拿到的是已生成的 payload", dedupe={"verdict": "same", "of": TARGET, "why": "同一條"})
    assert second["action"] == "append" and second["append_to"]["atom_name"] == TARGET
    assert [a["action"] for a in audits if a["action"] in ("need_declaration", "dedupe_declared")] == ["need_declaration", "dedupe_declared"]
