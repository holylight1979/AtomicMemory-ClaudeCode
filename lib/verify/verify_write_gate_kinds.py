"""verify_write_gate_kinds.py：Q1：寫入閘分型（pointer／complement／ledger／hub／plain）與「超預算不截斷、告訴你該去哪」。

做什麼：
1. 12 張真導讀卡（段落名抄在 hooks/verify/fixtures/v6/q1/hub_cards.json）五段映射 found 數與預核一致；普通卡不是 hub（反例）。
2. 七案：pointer／complement（append 預算內）／ledger 路由文件／hub 缺段／hub 無 Depends／append 超預算 skip＋route／
   explicit_user 仍超預算 skip；反例「教訓語義被截」；超預算結果不得含改寫過的內容、reason 寫明不截斷。
3. route_to 從部位表（overview-map）取病灶清單；mode≠create 不跑 dedup。
免向量服務（check_dedup 以 monkeypatch 關掉）；不碰 live（audit log 也關掉）。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_write_gate_kinds.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("mwg_kinds", ROOT / "tools" / "memory-write-gate.py")
mwg = importlib.util.module_from_spec(_spec)
sys.modules["mwg_kinds"] = mwg
_spec.loader.exec_module(mwg)

from lib.hub_card import (  # noqa: E402
    HUB_CARD_BUDGET, HUB_SECTIONS, check_hub_card_sections, is_hub_card, route_doc_for,
)

FIX = ROOT / "hooks" / "verify" / "fixtures" / "v6" / "q1"
CFG = {"enabled": True, "auto_threshold": 0.5, "ask_threshold": 0.3, "dedup_score": 0.8,
       "knowledge_budget_bytes": 3072}


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(mwg, "check_dedup", lambda *a, **k: None)
    monkeypatch.setattr(mwg, "write_audit_log", lambda *a, **k: None)


def _fix(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _filler(n: int, seed: str = "這一行是個案細節") -> str:
    """產生約 n bytes 的 CJK 內容（每字 3 bytes）。"""
    line = seed * 6
    out = []
    while sum(len(x.encode("utf-8")) + 1 for x in out) < n:
        out.append(f"[臨] {line}")
    return "\n".join(out)


def _hub(sections=("做什麼", "權威在哪", "動手前必問", "已知病灶", "最近驗證"), pad: int = 60) -> str:
    return "\n".join(f"[臨] **{h}**：{'內容' * pad}" for h in sections)


# ─── 1. 12 張真卡映射 ───────────────────────────────────────────────────────


def test_12_real_hub_cards_section_mapping_matches_precheck():
    data = json.loads((FIX / "hub_cards.json").read_text(encoding="utf-8"))
    assert len(data["cards"]) == 12
    for card in data["cards"]:
        content = "\n".join(f"- [臨] **{h}**：略" for h in card["headings"])
        r = check_hub_card_sections(content)
        assert r["found"] == card["expected_found"], card["id"]
        assert len(r["found"]) == card["precheck_found_count"], card["id"]
        assert r["missing"] == card["expected_missing"], card["id"]
        assert is_hub_card(content), card["id"]
    # 12 張裡 8 張五段齊、4 張缺段（缺的也是 hub，只是寫入時會被要求補齊）
    full = [c["id"] for c in data["cards"] if not c["expected_missing"]]
    assert len(full) == 8


def test_plain_card_is_not_hub():
    plain = ("[臨] Windows 文字模式寫檔沒給 newline 會翻成 CRLF，索引多機合併必衝突\n"
             "[臨] 修法：open(..., newline=\"\\n\")；verify_lf_writes 守門\n"
             "[臨] 驗證：python tools/normalize-eol.py --root --check")
    r = check_hub_card_sections(plain)
    assert len(r["found"]) <= 1 and not is_hub_card(plain)
    res = mwg.evaluate(plain, config=CFG, skip_gate=True)
    assert res["action"] == "add" and res["kind"] == "plain"
    assert res["budget"]["limit"] == 3072 and res["missing_sections"] == [] and res["depends_missing"] is False
    assert set(HUB_SECTIONS) == {"what", "authority", "ask", "defects", "verify"}


# ─── 2. 七案 ──────────────────────────────────────────────────────────────


def test_case1_pointer_kind():
    res = mwg.evaluate(_fix("pointer.md"), title="設計表知識導讀-hub索引", config=CFG, skip_gate=True)
    assert res["action"] == "add" and res["kind"] == "pointer"
    assert "一行指標" in res["how"]
    # kind_hint 也能宣告指標卡（標題沒有導讀字樣）
    res2 = mwg.evaluate("[臨] 見 memory/工作流/_INDEX.md", title="x", config=CFG, skip_gate=True, kind_hint="pointer")
    assert res2["kind"] == "pointer"


def test_case2_complement_append_within_budget(tmp_path):
    existing = tmp_path / "card.md"
    existing.write_text(_fix("complement_existing.md"), encoding="utf-8", newline="\n")
    res = mwg.evaluate("[臨] 補一條結論", mode="append", existing_path=str(existing), config=CFG)
    assert res["action"] == "add" and res["kind"] == "complement"
    assert res["budget"]["existing_bytes"] > 0 and res["budget"]["limit"] == 3072
    assert res["budget"]["bytes"] + res["budget"]["existing_bytes"] <= 3072
    assert "預算" in res["how"]


def test_case3_ledger_routes_to_doc():
    res = mwg.evaluate(_fix("ledger.md"), config=CFG, skip_gate=True)
    assert res["action"] == "skip" and res["kind"] == "ledger"
    assert res["route_to"] and res["route_to"] in res["reason"]
    assert "現況帳" in res["reason"]
    # 也不吃 explicit_user 捷徑
    res2 = mwg.evaluate(_fix("ledger.md"), config=CFG, explicit_user=True)
    assert res2["action"] == "skip" and res2["kind"] == "ledger"


def test_case4_hub_missing_sections_skip():
    res = mwg.evaluate(_fix("hub_missing.md"), title="x部位導讀", config=CFG,
                       depends=["path:C:/x/y.py"], skip_gate=True)
    assert res["action"] == "skip" and res["kind"] == "hub"
    assert len(res["missing_sections"]) == 2
    assert any("已知病灶" in m for m in res["missing_sections"])
    assert any("驗法" in m for m in res["missing_sections"])
    assert res["depends_missing"] is False
    assert "五段缺 2 段" in res["reason"]


def test_case5_hub_without_depends_skip():
    res = mwg.evaluate(_fix("hub_full.md"), title="x部位導讀", config=CFG, skip_gate=True)
    assert res["action"] == "skip" and res["kind"] == "hub"
    assert res["depends_missing"] is True and res["missing_sections"] == []
    assert "Depends" in res["reason"]
    # 給了 Depends 就過，且預算上限是 hub 的 4096
    ok = mwg.evaluate(_fix("hub_full.md"), title="x部位導讀", config=CFG, depends=["path:C:/x/y.py"], skip_gate=True)
    assert ok["action"] == "add" and ok["kind"] == "hub" and ok["budget"]["limit"] == HUB_CARD_BUDGET


def test_case6_append_over_budget_skip_route_no_truncation(tmp_path):
    """反例「教訓語義被截」：超預算只能 skip＋route_to，不得回改寫／截斷的內容。"""
    existing = tmp_path / "card.md"
    existing.write_text(_fix("complement_existing.md"), encoding="utf-8", newline="\n")
    lesson = "[臨] 教訓：這個部位的常數有兩份正本，改一份必漏另一份；驗法 shared_enum_sync_check.py"
    new = lesson + "\n" + _filler(1400)
    res = mwg.evaluate(new, mode="append", existing_path=str(existing), config=CFG)
    assert res["action"] == "skip" and res["kind"] == "complement"
    assert res["route_to"] and res["route_to"] in res["reason"]
    assert "不截斷" in res["reason"] and "既有" in res["reason"]
    assert res["budget"]["bytes"] + res["budget"]["existing_bytes"] > res["budget"]["limit"] == 3072
    # 結果不帶任何改寫後的內容；教訓原句不會被摘進 reason 當替代品
    assert "content" not in res and lesson not in res["reason"]


def test_case7_explicit_user_still_skips_over_budget():
    big = _filler(3500)
    res = mwg.evaluate(big, config=CFG, explicit_user=True)
    assert res["action"] == "skip" and res["kind"] == "plain"
    assert res["budget"]["bytes"] > 3072 and "超過預算 3072" in res["reason"]
    assert res["route_to"] in res["reason"]


# ─── 3. route_to／mode≠create ─────────────────────────────────────────────


def test_route_to_from_overview_map(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / "src").mkdir()
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 病灶清單 | 量尺（量法｜指令｜門檻） | 檢查器清單 | 讀路徑樣本 | 第四問 | 層 | 權威地圖 | 上游 | 下游 |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| `src/` | 主程式 | 無 | 無 | `_AIDocs/defects.md` | 無 | 無 | 無 | 無 | 單層 | `_AIDocs/_INDEX.md` | 無 | 無 |\n",
        encoding="utf-8", newline="\n")
    dep = str(proj / "src" / "x.py")
    assert route_doc_for([dep]) == str(proj / "_AIDocs" / "defects.md")
    res = mwg.evaluate(_filler(3500), config=CFG, depends=[f"path:{dep}"], skip_gate=True)
    assert res["action"] == "skip" and res["route_to"] == str(proj / "_AIDocs" / "defects.md")
    # 找不到表 → 回層名（不是空字串）
    assert route_doc_for([str(tmp_path / "nowhere" / "z.py")]) == "_AIDocs"


def test_mode_append_skips_dedup_and_quality(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("dedup must not run for mode=append")
    monkeypatch.setattr(mwg, "check_dedup", boom)
    existing = tmp_path / "card.md"
    existing.write_text(_fix("complement_existing.md"), encoding="utf-8", newline="\n")
    res = mwg.evaluate("[臨] 短句", mode="append", existing_path=str(existing), config=CFG)
    assert res["action"] == "add"
    # create 仍跑 dedup（確認 monkeypatch 真的會炸）
    with pytest.raises(AssertionError):
        mwg.evaluate("[臨] 短句", mode="create", config=CFG)


def test_old_keys_unchanged_on_add():
    res = mwg.evaluate("[臨] hook 的 systemMessage 模型讀不到，要回饋模型用 additionalContext，否則提醒無效",
                       config=CFG)
    for k in ("action", "quality_score", "reason"):
        assert k in res
    for k in ("kind", "route_to", "budget", "missing_sections", "depends_missing", "how"):
        assert k in res
    assert res["kind"] == "plain"
