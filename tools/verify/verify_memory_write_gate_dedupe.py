"""verify_memory_write_gate_dedupe.py — 寫入閘去重交 AI 判（判斷入口盤點 P8）。

做什麼：相似度達門檻不再直接拒寫，回「要宣告」（action=skip＋need_declaration，舊 js 照拒）＋候選卡（最多 3 張：卡名、分數、知識段前 2 行）
與三種寫法；AI 帶 dedupe={verdict, of, why} 重送 → 程式只核 verdict 三選一、of 是候選卡名、why 有字，
收下就記 audit dedupe_declared 並照宣告路由（same→append_to、supersedes／different 照常往下判）。
另守：沒命中／向量服務沒起照舊直接寫、給了宣告但沒命中附 note、write_gate.dedupe_declaration=false 回舊行為、
品質分數只分寫／不寫（舊 ask 級拿掉）、pitfall 捷徑不豁免宣告。
真實輸入：拿本樹一張真卡改名重送（等同「改名取代舊卡」），打 live 向量服務（唯讀 GET；服務沒起就 skip）。
不寫 live：audit 一律 monkeypatch 收進記憶體；假向量命中用 monkeypatch urlopen。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_memory_write_gate_dedupe.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("mwg_dedupe", ROOT / "tools" / "memory-write-gate.py")
WG = importlib.util.module_from_spec(_spec)
sys.modules["mwg_dedupe"] = WG
_spec.loader.exec_module(WG)

CFG = {"enabled": True, "dedup_score": 0.80, "knowledge_budget_bytes": 3072}
# 品質過線的新內容（tech_terms＋concrete_value＋actionable），讓「往下判」的結果是 add 而不是品質 skip
CONTENT = "[臨] hook 的 PreToolUse 在 Edit payload 生成後才觸發 → 寫前提醒要放 PostToolUse，路徑 ~/.claude/hooks/x.py"
REAL_CARD = (ROOT / "_AIDocs" / "_atoms" / "MemDev"
             / "mcp的node端程式改了要開新session才載到-同機其他session的mcp程序仍跑舊碼-python端每次spawn立即生效.md")


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def audits(monkeypatch):
    seen = []
    monkeypatch.setattr(WG, "write_audit_log", lambda action, *a, **k: seen.append({"action": action, **k}))
    return seen


@pytest.fixture
def old_card(tmp_path):
    p = tmp_path / "old-card.md"
    p.write_text("# old card\n\n- Scope: global\n\n## 知識\n\n- [臨] 第一行：hook 時序\n- [臨] 第二行：payload 已生成\n"
                 "- [臨] 第三行不該被節錄\n\n## 行動\n\n- 行動行\n", encoding="utf-8")
    return p


def _vector(monkeypatch, hits):
    """假向量服務：照真服務的 min_score／top_k 過濾（searcher.search 也是先濾分再截 top_k）。"""
    seen = []

    def fake_urlopen(req, timeout=0):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)
        seen.append(q)
        min_score, top_k = float(q["min_score"][0]), int(q["top_k"][0])
        rows = sorted((h for h in hits if h["score"] >= min_score), key=lambda h: -h["score"])[:top_k]
        return _Resp(json.dumps(rows).encode("utf-8"))

    monkeypatch.setattr(WG.urllib.request, "urlopen", fake_urlopen)
    return seen


def _hits(old_card):
    return [
        {"atom_name": "old-card", "score": 0.912, "text": "chunk", "file_path": str(old_card), "layer": "global"},
        {"atom_name": "second-card", "score": 0.85, "text": "第二張的命中段\n第二行", "file_path": "", "layer": "extra:local-atoms"},
        {"atom_name": "third-card", "score": 0.82, "text": "第三張", "file_path": "C:/nope/missing.md", "layer": "global"},
        {"atom_name": "fourth-card", "score": 0.81, "text": "第四張", "file_path": "", "layer": "global"},
    ]


def _eval(**kw):
    return WG.evaluate(CONTENT, config={**CFG, **kw.pop("cfg", {})}, title="新卡", **kw)


def _needs_declaration(r):
    """要宣告＝拒寫（action=skip，還沒 Reload 的舊 js 也照拒）＋need_declaration 旗標（新 js 轉述）。"""
    return r["action"] == "skip" and r.get("need_declaration") is True and r["candidates"]


# ─── 1. 命中、沒宣告：不放行，列候選與三種寫法 ────────────────────────────────


def test_hit_without_declaration_lists_candidates(monkeypatch, audits, old_card):
    seen = _vector(monkeypatch, _hits(old_card))
    r = _eval()
    assert seen and seen[0]["top_k"] == ["3"] and seen[0]["min_score"] == ["0.8"]
    assert _needs_declaration(r)
    assert [c["atom_name"] for c in r["candidates"]] == ["old-card", "second-card", "third-card"]
    assert r["candidates"][0]["excerpt"] == ["[臨] 第一行：hook 時序", "[臨] 第二行：payload 已生成"]
    assert r["candidates"][1]["excerpt"] == ["第二張的命中段", "第二行"]   # 沒檔 → 退用命中段
    assert r["candidates"][2]["excerpt"] == ["第三張"]                     # 檔不存在 → 退用命中段
    reason = r["reason"]
    assert "這次不寫檔" in reason and "old-card（score=0.912，layer=global）" in reason
    assert "｜[臨] 第一行：hook 時序" in reason and "第三行不該被節錄" not in reason and "fourth-card" not in reason
    for verdict in ("same", "supersedes", "different"):
        assert f'"verdict":"{verdict}"' in reason
    assert "宣告不收" not in reason
    assert set(r["dedup_match"]) == {"atom_name", "score", "text_preview", "verdict"}
    assert audits[-1]["action"] == "need_declaration" and audits[-1]["candidates"][0] == "old-card"


# ─── 2. 宣告收下：照宣告路由、留帳 ────────────────────────────────────────────


def test_supersedes_declared_continues_with_audit(monkeypatch, audits, old_card):
    _vector(monkeypatch, _hits(old_card))
    why = "舊卡的 trigger 寫法已改、本卡取代"
    r = _eval(dedupe={"verdict": "supersedes", "of": "old-card", "why": why})
    assert r["action"] == "add"
    assert r["dedupe_declared"] == {"verdict": "supersedes", "of": "old-card", "why": why, "score": 0.912}
    declared = [a for a in audits if a["action"] == "dedupe_declared"]
    assert declared == [{"action": "dedupe_declared", "verdict": "supersedes", "of": "old-card", "why": why, "score": 0.912}]


def test_same_declared_routes_to_append(monkeypatch, audits, old_card):
    _vector(monkeypatch, _hits(old_card))
    r = _eval(dedupe={"verdict": "same", "of": " second-card ", "why": "同一條：只是多一個實例"})
    assert r["action"] == "append"
    assert r["append_to"] == {"atom_name": "second-card", "layer": "extra:local-atoms"}
    assert r["dedupe_declared"]["of"] == "second-card" and r["dedupe_declared"]["score"] == 0.85
    assert "triggers／actions 不併" in r["reason"]
    assert audits[-1]["action"] == "dedupe_declared" and audits[-1]["verdict"] == "same"


def test_different_with_reason_writes(monkeypatch, audits, old_card):
    _vector(monkeypatch, _hits(old_card))
    r = _eval(dedupe={"verdict": "different", "of": "old-card", "why": "舊卡講 MCP 重載，本卡講 hook 時序"})
    assert r["action"] == "add" and r["dedupe_declared"]["verdict"] == "different"


# ─── 3. 宣告不收：點名哪一欄、重列候選、不放行 ────────────────────────────────


@pytest.mark.parametrize("why", ["", "   ", "....", "。。！", "<一句理由>", None])
def test_why_without_content_rejected(monkeypatch, audits, old_card, why):
    _vector(monkeypatch, _hits(old_card))
    r = _eval(dedupe={"verdict": "different", "of": "old-card", "why": why})
    assert _needs_declaration(r)
    assert r["reason"].startswith("宣告不收：why 要寫一句理由") and "old-card（score=0.912" in r["reason"]
    assert not [a for a in audits if a["action"] == "dedupe_declared"]


def test_of_not_in_candidates_rejected(monkeypatch, audits, old_card):
    _vector(monkeypatch, _hits(old_card))
    r = _eval(dedupe={"verdict": "same", "of": "fourth-card", "why": "我覺得是同一條"})
    assert _needs_declaration(r)
    assert "of「fourth-card」不在這次列出的候選卡裡" in r["reason"] and "1. old-card" in r["reason"]


@pytest.mark.parametrize("dedupe,needle", [
    ({"verdict": "merge", "of": "old-card", "why": "同一條知識"}, "verdict 要是 same／supersedes／different"),
    ("same", "dedupe 要是物件"),
    ({"verdict": "same"}, "of「」不在"),
])
def test_bad_shape_rejected(monkeypatch, audits, old_card, dedupe, needle):
    _vector(monkeypatch, _hits(old_card))
    r = _eval(dedupe=dedupe)
    assert _needs_declaration(r) and needle in r["reason"]


def test_why_any_real_text_accepted(monkeypatch, audits, old_card):
    """why 只核「有字」，不設字數下限（多短算夠是 AI 的事，抽查靠 audit）。"""
    _vector(monkeypatch, _hits(old_card))
    r = _eval(dedupe={"verdict": "different", "of": "old-card", "why": "異"})
    assert r["action"] == "add" and r["dedupe_declared"]["why"] == "異"


def test_same_name_in_two_layers_both_listed(monkeypatch, audits, old_card):
    """不同層同名卡兩張都列，of 要寫 <layer>:<卡名>；只寫卡名 → 點名兩種寫法；寫對 → 路由到那一層。"""
    hits = [{**_hits(old_card)[0]},
            {"atom_name": "old-card", "score": 0.87, "text": "專案層那張", "file_path": "", "layer": "shared:c--proj"}]
    _vector(monkeypatch, hits)
    r = _eval()
    assert [c["ref"] for c in r["candidates"]] == ["global:old-card", "shared:c--proj:old-card"]
    assert "1. global:old-card（score=0.912" in r["reason"] and "2. shared:c--proj:old-card（score=0.87" in r["reason"]
    r = _eval(dedupe={"verdict": "same", "of": "old-card", "why": "同一條"})
    assert _needs_declaration(r) and "寫成 global:old-card 或 shared:c--proj:old-card" in r["reason"]
    r = _eval(dedupe={"verdict": "same", "of": "shared:c--proj:old-card", "why": "同一條"})
    assert r["action"] == "append" and r["append_to"] == {"atom_name": "old-card", "layer": "shared:c--proj"}
    assert r["dedupe_declared"]["of"] == "old-card" and r["dedupe_declared"]["score"] == 0.87


def test_pitfall_does_not_skip_declaration(monkeypatch, audits, old_card):
    """pitfall 捷徑只豁免品質分，不豁免去重宣告。"""
    _vector(monkeypatch, _hits(old_card))
    r = WG.evaluate("這是一個坑：Windows 下 Path.write_text 會翻整檔行尾", config=CFG)
    assert _needs_declaration(r)


# ─── 4. 沒命中／服務沒起／開關關掉：行為同舊碼 ────────────────────────────────


def test_below_threshold_writes_directly(monkeypatch, audits, old_card):
    _vector(monkeypatch, [{**_hits(old_card)[0], "score": 0.5}])
    r = _eval()
    assert r["action"] == "add" and "dedup_match" not in r and "dedupe_note" not in r
    r = _eval(dedupe={"verdict": "same", "of": "old-card", "why": "同一條"})
    assert r["action"] == "add" and r["dedupe_note"].startswith("dedupe 宣告已忽略") and "dedupe_declared" not in r


def test_vector_service_down_fail_open(monkeypatch, audits, capsys):
    def boom(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(WG.urllib.request, "urlopen", boom)
    r = _eval(dedupe={"verdict": "different", "of": "x", "why": "不同的事"})
    assert r["action"] == "add" and "dedupe 宣告已忽略" in r["dedupe_note"]
    assert any(a["action"] == "dedup_skipped_service_down" for a in audits)
    assert "vector service unavailable" in capsys.readouterr().err


def test_skip_gate_ignores_declaration_with_note(monkeypatch, audits, old_card):
    _vector(monkeypatch, _hits(old_card))
    r = _eval(skip_gate=True, dedupe={"verdict": "same", "of": "old-card", "why": "同一條"})
    assert r["action"] == "add" and "skip_gate 不跑去重" in r["dedupe_note"]


@pytest.mark.parametrize("score,action,reason", [
    (0.97, "skip", "duplicate of old-card (score=0.97)"),
    (0.88, "update", "similar to old-card (score=0.88), suggest update"),
])
def test_flag_off_is_old_behavior(monkeypatch, audits, old_card, score, action, reason):
    _vector(monkeypatch, [{**_hits(old_card)[0], "score": score}])
    for dedupe in (None, {"verdict": "different", "of": "old-card", "why": "不同的事"}):
        r = _eval(cfg={"dedupe_declaration": False}, dedupe=dedupe)
        assert r["action"] == action and r["reason"] == reason
        assert r["dedup_match"] == {"atom_name": "old-card", "score": score, "text_preview": "chunk",
                                    "verdict": "duplicate" if score > 0.95 else "similar"}
        assert "candidates" not in r and "dedupe_declared" not in r
    assert [a["action"] for a in audits] == [action, action]


# ─── 5. 品質分數只分寫／不寫（ask 級拿掉） ─────────────────────────────────────


def test_quality_has_no_ask_tier(monkeypatch, audits):
    _vector(monkeypatch, [])
    mid = "使用者原話寫在這裡，只是一段很普通的敘述文字，句子裡頭沒有任何技術名詞，也沒有具體的數值或者檔案位置可以參考。"
    q, _ = WG.compute_quality_score(mid)
    assert 0.3 <= q < 0.5                                  # 舊碼這裡回 ask
    assert WG.evaluate(mid, config=CFG)["action"] == "add"
    assert WG.evaluate(mid, config={**CFG, "quality_floor": 0.4})["action"] == "skip"
    assert WG.evaluate("短句一則", config=CFG)["action"] == "skip"
    # 沒設 quality_floor 的舊 config：沿用實際生效的寫入線 ask_threshold（舊碼 ask 級照寫、低於它才 skip）；auto_threshold 不再有作用
    assert WG.evaluate(mid, config={**CFG, "auto_threshold": 0.9})["action"] == "add"
    assert WG.evaluate(mid, config={**CFG, "ask_threshold": 0.4})["action"] == "skip"   # codex BLOCK：自訂 0.4 舊碼 skip
    assert WG.evaluate(mid, config={**CFG, "ask_threshold": 0.4, "quality_floor": 0.3})["action"] == "add"


# ─── 6. 真實輸入：一張真卡改名重送（live 向量服務，唯讀） ─────────────────────


def _live_vector_up() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:3849/health", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


@pytest.mark.skipif(not _live_vector_up(), reason="live 向量服務沒起（port 3849）")
def test_real_card_renamed_needs_declaration_then_writes(monkeypatch, audits):
    text = REAL_CARD.read_text(encoding="utf-8")
    body = text.split("## 知識", 1)[1].split("## 行動", 1)[0]
    knowledge = "\n".join(ln[2:] for ln in body.splitlines() if ln.startswith("- "))
    slug = REAL_CARD.stem
    layers = ["global", "extra:local-atoms"]
    cfg = {**CFG, "dedup_score": 0.80}
    title = "MCP node 端改碼後要 Reload Window 才載入新碼"   # 改名：同一份知識換新標題
    old = WG.evaluate(knowledge, config={**cfg, "dedupe_declaration": False}, layers=layers, title=title)
    assert old["action"] in ("skip", "update") and old["dedup_match"]["atom_name"] == slug   # 舊碼：拒寫
    r = WG.evaluate(knowledge, config=cfg, layers=layers, title=title)
    assert _needs_declaration(r)
    assert r["candidates"][0]["atom_name"] == slug and r["candidates"][0]["score"] >= 0.8
    assert r["candidates"][0]["excerpt"][0].startswith("[臨] 實踩：R6 改了")
    why = "同一份知識改名：新標題直接講 Reload Window，本卡取代舊卡"
    w = WG.evaluate(knowledge, config=cfg, layers=layers, title=title,
                    dedupe={"verdict": "supersedes", "of": slug, "why": why})
    assert w["action"] == "add" and w["dedupe_declared"]["of"] == slug and w["dedupe_declared"]["why"] == why
    assert any(a["action"] == "dedupe_declared" and a["of"] == slug and a["why"] == why for a in audits)
    print(f"real input: score={r['candidates'][0]['score']} old={old['action']} new={r['action']}→{w['action']}")
