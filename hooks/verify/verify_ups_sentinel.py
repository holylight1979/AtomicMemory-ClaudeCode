"""verify_ups_sentinel.py — UPS 被 kill 哨兵（timeout 砍注入不再靜默）。

驗證 handlers/user_prompt_submit 的哨兵閉環：UPS 開頭 arm（touch 哨兵檔）、
正常結尾 clear；本輪見殘留哨兵＝上輪 UPS 未跑完（harness timeout / 例外）→
浮一行 [Guardian:UPS-Sentinel] 告警（可觀測性鐵律）。

  - 首輪 arm：無殘留 → 不告警、哨兵檔建立
  - clear：哨兵檔移除
  - 殘留偵測：arm 後不 clear（模擬被砍）→ 下輪 arm 告警且帶上輪 turn 資訊
  - 空 session_id → noop；壞哨兵 JSON → 仍告警不炸（fail-open）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from handlers import user_prompt_submit as ups  # noqa: E402

_SID = "sid-sentinel"


@pytest.fixture
def wdir(tmp_path, monkeypatch):
    monkeypatch.setattr(ups, "WORKFLOW_DIR", tmp_path)
    return tmp_path


def test_first_arm_no_warning(wdir):
    """首輪：無殘留 → 不告警、哨兵檔建立且含 turn_seq。"""
    lines = []
    ups._ups_sentinel_check_and_arm(_SID, {"turn_seq": 4}, lines)
    assert lines == []
    p = wdir / "ups-sentinel" / f"{_SID}.json"
    assert p.exists()
    assert json.loads(p.read_text(encoding="utf-8"))["turn_seq"] == 5  # 本輪=上輪+1


def test_clear_removes_sentinel(wdir):
    lines = []
    ups._ups_sentinel_check_and_arm(_SID, {}, lines)
    ups._ups_sentinel_clear(_SID)
    assert not (wdir / "ups-sentinel" / f"{_SID}.json").exists()


def test_leftover_sentinel_warns(wdir):
    """arm 後不 clear（模擬 harness timeout 砍掉）→ 下輪 arm 浮告警。"""
    ups._ups_sentinel_check_and_arm(_SID, {"turn_seq": 4}, [])
    lines = []
    ups._ups_sentinel_check_and_arm(_SID, {"turn_seq": 5}, lines)
    assert len(lines) == 1
    assert "[Guardian:UPS-Sentinel]" in lines[0]
    assert "turn 5" in lines[0]  # 上輪哨兵記的 turn_seq（4+1）


def test_normal_cycle_no_warning(wdir):
    """arm → clear → 下輪 arm：正常循環不告警。"""
    ups._ups_sentinel_check_and_arm(_SID, {"turn_seq": 4}, [])
    ups._ups_sentinel_clear(_SID)
    lines = []
    ups._ups_sentinel_check_and_arm(_SID, {"turn_seq": 5}, lines)
    assert lines == []


def test_empty_session_id_noop(wdir):
    lines = []
    ups._ups_sentinel_check_and_arm("", {}, lines)
    ups._ups_sentinel_clear("")
    assert lines == []
    assert not (wdir / "ups-sentinel").exists()


def test_corrupt_sentinel_still_warns(wdir):
    """壞 JSON 哨兵 → 仍告警（帶 ? 佔位）、不炸。"""
    d = wdir / "ups-sentinel"
    d.mkdir(parents=True)
    (d / f"{_SID}.json").write_text("{ not json", encoding="utf-8")
    lines = []
    ups._ups_sentinel_check_and_arm(_SID, {"turn_seq": 1}, lines)
    assert len(lines) == 1
    assert "[Guardian:UPS-Sentinel]" in lines[0]
