"""verify_harvest_routing.py：Q3 路由：萃取 item 的 route／candidate_global／part 欄驗證、原樣入 ledger、
AEC 追蹤項（k）落 workflow/tracking/<slug>.jsonl。

做什麼：
- 三案 route 正反：part_doc 帶 part 過／無 part 擋；candidate_global 的 summary 帶專案名 → 擋並建議 scrub；
  global 乾淨過、bogus 擋。
- apply_report／append_ledger 原樣保留 route／candidate_global／part（不改寫、不補欄）。
- C8 兩案：k≠「無」→ 帳本一行、LF、欄位齊；k=「無」→ 不建檔。擋訊息含「追蹤項已入帳」一句。
不碰 live：帳本寫 tmp_path；專案名靠 monkeypatch realm_gate.known_project_names。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_harvest_routing.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_harvest as wh  # noqa: E402
# 本 repo 的 lib 放最前：wg_core 依 WG_CLAUDE_DIR 決定 lib 路徑，沒設會撈 live；測試驗的是本 repo 的 realm_gate
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))
import realm_gate as rg  # noqa: E402

_SID = "sid"


@pytest.fixture(autouse=True)
def _fake_projects(monkeypatch):
    monkeypatch.setattr(rg, "known_project_names", lambda: [("FooProj", "已登記專案", True)])
    monkeypatch.setattr(rg, "known_project_roots", lambda: ["d:/work/fooproj"])


def _item(**kw):
    base = {"source": "mechanism", "summary": "hook 的 systemMessage 模型讀不到", "action": "skip", "reason": "一次性"}
    base.update(kw)
    return base


# ─── route 三案 ───────────────────────────────────────────────────────────


def test_route_part_doc_requires_part():
    ok, pending = wh.validate_items([_item(route="part_doc", part="lib")], [])
    assert pending == [] and ok[0]["route"] == "part_doc" and ok[0]["part"] == "lib"
    _, pending = wh.validate_items([_item(route="part_doc")], [])
    assert len(pending) == 1 and "必填 part" in pending[0]


def test_route_candidate_global_with_project_name_blocked_suggest_scrub():
    _, pending = wh.validate_items([_item(route="candidate_global", candidate_global=True,
                                          summary="FooProj 的登入要先起假 Gate")], [])
    assert len(pending) == 1
    assert "FooProj" in pending[0] and "scrub" in pending[0]
    # 專案根底下的絕對路徑同樣擋
    _, pending2 = wh.validate_items([_item(route="global", summary=r"見 D:\work\FooProj\src\x.cs")], [])
    assert len(pending2) == 1 and "scrub" in pending2[0]
    # scrub 後過
    scrubbed = rg.scrub_project_details("FooProj 的登入要先起假 Gate")
    assert "FooProj" not in scrubbed
    _, pending3 = wh.validate_items([_item(route="candidate_global", candidate_global=True, summary=scrubbed)], [])
    assert pending3 == []


def test_route_global_clean_passes_and_bogus_blocked():
    _, pending = wh.validate_items([_item(route="global")], [])
    assert pending == []
    _, pending = wh.validate_items([_item(route="bogus")], [])
    assert len(pending) == 1 and "route=" in pending[0]
    # route 不給＝舊行為，不擋
    _, pending = wh.validate_items([_item()], [])
    assert pending == []


def test_items_kept_verbatim_in_state_and_ledger(tmp_path):
    state = {"turn_seq": 3}
    items = [_item(route="part_doc", part="hooks", candidate_global=False)]
    sec = wh.apply_report(state, _SID, 3, items)
    assert sec["validated"] and sec["items"][0]["route"] == "part_doc"
    assert sec["items"][0]["part"] == "hooks" and sec["items"][0]["candidate_global"] is False
    wh.append_ledger(_SID, {"turn_seq": 3, "items": sec["items"]}, base_dir=tmp_path)
    raw = (tmp_path / "harvest-ledger" / f"{_SID}.jsonl").read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    rec = json.loads(raw.decode("utf-8"))
    assert rec["items"][0]["route"] == "part_doc" and rec["items"][0]["part"] == "hooks"


# ─── C8：追蹤項帳本 ───────────────────────────────────────────────────────


def test_tracking_k_not_none_writes_one_line_lf(tmp_path):
    entries = wh.tracking_entries(_SID, 7, "[lib] atom_io.append_atom_file 的 limit 要用 is_hub_card 選", at="2026-10-08T21:00:00")
    assert len(entries) == 1
    e = entries[0]
    assert e == {"session_id": _SID, "turn_seq": 7, "at": "2026-10-08T21:00:00", "part": "lib",
                 "text": "atom_io.append_atom_file 的 limit 要用 is_hub_card 選", "status": "open"}
    p = wh.append_tracking("c--users-x--proj", entries, base_dir=tmp_path)
    assert p == tmp_path / "tracking" / "c--users-x--proj.jsonl"
    raw = p.read_bytes()
    assert raw.count(b"\n") == 1 and raw.endswith(b"\n") and b"\r" not in raw
    assert json.loads(raw.decode("utf-8")) == e
    # 多行 k：「部位｜」寫法與無部位各一筆
    more = wh.tracking_entries(_SID, 8, "tools｜smoke 加 route 案\n- 補 _AIDocs 說明\n無", at="t")
    assert [(m["part"], m["text"]) for m in more] == [("tools", "smoke 加 route 案"), ("", "補 _AIDocs 說明")]
    wh.append_tracking("c--users-x--proj", more, base_dir=tmp_path)
    assert p.read_bytes().count(b"\n") == 3


def test_tracking_k_none_writes_nothing(tmp_path):
    for k in ("無", "", None, "  無  "):
        assert wh.tracking_entries(_SID, 1, k) == []
        assert wh.append_tracking("slug", wh.tracking_entries(_SID, 1, k), base_dir=tmp_path) is None
    assert not (tmp_path / "tracking").exists()


def test_block_message_two_states_and_route():
    """BLOCK 5：追蹤項那句條件式：入帳了才說「已入帳」，沒接線時叫人填 k 欄。"""
    off = wh.harvest_block_message()
    assert "追蹤項請填進收尾檢核 k 欄" in off and "追蹤項已入帳" not in off
    on = wh.harvest_block_message(tracking_written=True)
    assert "追蹤項已入帳，有部位的同時寫進病灶文件" in on and "請填進收尾檢核 k 欄" not in on
    assert "route(part_doc|global|org|local|shared|candidate_global" in off


def test_tracking_slug_injection_rejected(tmp_path):
    """BLOCK 5：slug 只許 [A-Za-z0-9_-]；../ 與磁碟根會指到 tracking 外，一律 ValueError 且不建檔。"""
    entries = wh.tracking_entries(_SID, 1, "x")
    for bad in ("../escaped", "C:/escaped", "a/b", "", "slug with space", "slug.jsonl", "ok\n", "\nok", "a" * 65):
        with pytest.raises(ValueError):
            wh.append_tracking(bad, entries, base_dir=tmp_path)
    assert not (tmp_path / "tracking").exists() and not (tmp_path / "escaped.jsonl").exists()
    assert wh.append_tracking("c--users-x--proj_1", entries, base_dir=tmp_path).name == "c--users-x--proj_1.jsonl"
    assert wh.append_tracking("a" * 64, entries, base_dir=tmp_path).name == "a" * 64 + ".jsonl"
