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
