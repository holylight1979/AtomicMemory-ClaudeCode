"""verify_aec_decision_drain.py — AEC HUD 決策 drain（注入端）。

驗證 handlers/user_prompt_submit._drain_aec_decisions：HUD (d) 保留/刪除鈕落於
workflow/aec-decision/<sid>-t<turn>-<idx>.json 的決策（Node 寫），由 UserPromptSubmit
Python 端讀取 → 聚合注入 additionalContext → 標 injected（防重注入）。

  - 本 session 決策（delete + keep）→ 注入含刪除/保留項 + 檔標 injected:true
  - foreign session（檔名前綴≠本）→ 不注入、檔不動
  - session_id 欄位不符（防禦性再校驗）→ 不注入
  - 已 injected:true → 跳過
  - 空目錄 / 壞 JSON → fail-open 不炸

決策檔由 Node（tools/workflow-guardian-mcp/lib/anti-evasion.js apiAecDecisionPost）落；
本測 fabricate 檔模擬之，只測 Python 讀端（Node 寫端走 restart+curl smoke）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from handlers import user_prompt_submit as ups  # noqa: E402

_SID = "sid-abc"


@pytest.fixture
def ddir(tmp_path, monkeypatch):
    """把 ups.WORKFLOW_DIR 導向 tmp，回傳 aec-decision 目錄（未預建，測 fail-open）。"""
    monkeypatch.setattr(ups, "WORKFLOW_DIR", tmp_path)
    return tmp_path / "aec-decision"


def _write(ddir, sid, turn, idx, action, item, injected=False, session_id=None):
    ddir.mkdir(parents=True, exist_ok=True)
    rec = {
        "session_id": session_id if session_id is not None else sid,
        "turn_seq": turn, "idx": idx, "item": item,
        "action": action, "at": "2026-07-06T00:00:00Z", "injected": injected,
    }
    p = ddir / f"{sid}-t{turn}-{idx}.json"
    p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return p


def test_own_delete_and_keep_injected(ddir):
    """本 session delete + keep → 注入含兩項 + 檔標 injected:true。"""
    pd = _write(ddir, _SID, 1, 0, "delete", "tmp/a.txt")
    pk = _write(ddir, _SID, 1, 1, "keep", "tmp/keep.md")
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert len(lines) == 1
    blob = lines[0]
    assert "[Guardian:AEC-Decision]" in blob
    assert "🗑 刪除：tmp/a.txt" in blob
    assert "📌 保留：tmp/keep.md" in blob
    # 檔已標 injected（防下回合重注入）
    assert json.loads(pd.read_text(encoding="utf-8"))["injected"] is True
    assert json.loads(pk.read_text(encoding="utf-8"))["injected"] is True


def test_foreign_filename_not_injected(ddir):
    """他 session 檔名前綴（other-）→ glob 不匹配本 session → 不注入、檔不動。"""
    pf = _write(ddir, "other", 1, 0, "delete", "tmp/x.txt")
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert lines == []
    assert json.loads(pf.read_text(encoding="utf-8"))["injected"] is False


def test_session_id_field_mismatch_skipped(ddir):
    """檔名前綴符本 session、但 session_id 欄位不符 → 防禦性再校驗擋下、不注入。"""
    _write(ddir, _SID, 1, 0, "delete", "tmp/x.txt", session_id="someone-else")
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert lines == []


def test_already_injected_skipped(ddir):
    """已 injected:true → 跳過、不重注入。"""
    _write(ddir, _SID, 2, 0, "delete", "tmp/old.txt", injected=True)
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert lines == []


def test_empty_dir_fail_open(ddir):
    """目錄不存在 → fail-open 不炸、不注入。"""
    lines = []
    ups._drain_aec_decisions(_SID, lines)   # ddir 尚未建立
    assert lines == []


def test_corrupt_json_skipped(ddir):
    """壞 JSON → skip、不炸；同批合法檔仍注入。"""
    ddir.mkdir(parents=True, exist_ok=True)
    (ddir / f"{_SID}-t3-0.json").write_text("{ not json", encoding="utf-8")
    _write(ddir, _SID, 3, 1, "keep", "tmp/ok.md")
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert len(lines) == 1
    assert "📌 保留：tmp/ok.md" in lines[0]


def test_empty_session_id_noop(ddir):
    """session_id 空 → 直接返回、不注入。"""
    _write(ddir, _SID, 4, 0, "delete", "tmp/x.txt")
    lines = []
    ups._drain_aec_decisions("", lines)
    assert lines == []


# ─── 刪除決策後驗（exists() 實查，不信宣告）──────────────────────────────────


def test_delete_still_exists_reinjects_once(ddir, tmp_path):
    """已注入的 delete 項，檔案仍在 → 🔁 重注入一次 + 標 reinjected。"""
    target = tmp_path / "leftover.tmp"
    target.write_text("x", encoding="utf-8")
    p = _write(ddir, _SID, 1, 0, "delete", str(target), injected=True)
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert len(lines) == 1
    assert "刪除決策後驗" in lines[0] and "🔁" in lines[0]
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["reinjected"] is True and not data.get("verified")


def test_delete_still_exists_second_time_warns_and_closes(ddir, tmp_path):
    """重注入過仍在 → ⚠ 告警 + verified 結案（不無限 nag）。"""
    target = tmp_path / "stubborn.tmp"
    target.write_text("x", encoding="utf-8")
    p = _write(ddir, _SID, 1, 0, "delete", str(target), injected=True)
    d = json.loads(p.read_text(encoding="utf-8"))
    d["reinjected"] = True
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert len(lines) == 1 and "⚠" in lines[0]
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["verified"] is True
    # 結案後不再產訊息
    lines2 = []
    ups._drain_aec_decisions(_SID, lines2)
    assert lines2 == []


def test_delete_gone_verified_silently(ddir, tmp_path):
    """檔案已消失 → 靜默 verified 結案、無告警。"""
    p = _write(ddir, _SID, 1, 0, "delete", str(tmp_path / "gone.tmp"), injected=True)
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert lines == []
    assert json.loads(p.read_text(encoding="utf-8"))["verified"] is True


def test_delete_prose_item_not_checked(ddir):
    """(d) 項為 prose（無路徑分隔符）→ 無從定位 → 靜默結案不誤告警。"""
    p = _write(ddir, _SID, 1, 0, "delete", "三個暫存檔已清", injected=True)
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert lines == []
    assert json.loads(p.read_text(encoding="utf-8"))["verified"] is True


def test_keep_action_not_verified(ddir, tmp_path):
    """keep 決策不做後驗（保留本來就該存在）。"""
    target = tmp_path / "keep.md"
    target.write_text("x", encoding="utf-8")
    p = _write(ddir, _SID, 1, 0, "keep", str(target), injected=True)
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert lines == []
    assert "verified" not in json.loads(p.read_text(encoding="utf-8"))


def test_delete_with_structured_path_verified_by_path(ddir, tmp_path):
    """新式決策檔（HUD 殘檔面板）帶 path 欄：後驗直接用 path，item 為 prose 也能真驗。"""
    target = tmp_path / "leftover.tmp"
    target.write_text("x")
    ddir.mkdir(parents=True, exist_ok=True)
    p = ddir / f"{_SID}-pabc123def456.json"
    p.write_text(json.dumps({
        "session_id": _SID, "path": str(target), "item": f"{target} — 一次性輸出",
        "action": "delete", "at": "2026-01-01T00:00:00", "injected": True,
    }), encoding="utf-8")
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert any("仍存在" in ln for ln in lines)          # 仍在 → 重注入
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["reinjected"] is True and not data.get("verified")
    target.unlink()
    lines = []
    ups._drain_aec_decisions(_SID, lines)
    assert lines == []                                   # 已刪 → 靜默結案
    assert json.loads(p.read_text(encoding="utf-8"))["verified"] is True
