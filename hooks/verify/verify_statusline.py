"""verify_statusline.py — tools/statusline.py（statusLine 渲染器）行為驗證。

覆蓋：
  - state 正常 → 改N/讀M（+佇K 條件段）
  - state 缺失/壞 JSON → 顯示 WG:?（fail-open 必告知，不裝沒事）
  - vector_ready.flag 有/無 → vec✓ / vec✗
  - aec-report 取本 session 最大 turn 的 severity；無報告 → 不顯示
  - stdin 壞 JSON → 印最小降級行、不拋例外

對應：tools/statusline.py（資料源 workflow/state-<sid>.json / vector_ready.flag /
aec-report/<sid>-t*.json）。
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[2] / "tools"


@pytest.fixture()
def sl(tmp_path, monkeypatch):
    """載入 statusline 模組並把 WORKFLOW_DIR 指到 tmp_path。"""
    spec = importlib.util.spec_from_file_location(
        "statusline_under_test", _TOOLS / "statusline.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "WORKFLOW_DIR", tmp_path)
    return mod


_SID = "sess-sl-test"


def _write_state(tmp_path, **over):
    d = {"modified_files": [{"path": "a.py"}], "accessed_files": ["a", "b"],
         "knowledge_queue": []}
    d.update(over)
    (tmp_path / f"state-{_SID}.json").write_text(
        json.dumps(d, ensure_ascii=False), encoding="utf-8"
    )


def test_state_ok_counts(sl, tmp_path):
    _write_state(tmp_path)
    out = " ".join(sl._guardian_segments(_SID))
    assert "改1" in out and "讀2" in out
    assert "佇" not in out  # 空佇列不顯示


def test_knowledge_queue_segment(sl, tmp_path):
    _write_state(tmp_path, knowledge_queue=[{"content": "x"}] * 3)
    assert "佇3" in " ".join(sl._guardian_segments(_SID))


def test_state_missing_shows_degraded(sl):
    assert "WG:?" in " ".join(sl._guardian_segments("no-such"))


def test_state_corrupt_shows_degraded(sl, tmp_path):
    (tmp_path / f"state-{_SID}.json").write_text("{bad", encoding="utf-8")
    assert "WG:?" in " ".join(sl._guardian_segments(_SID))


def test_vector_flag(sl, tmp_path):
    _write_state(tmp_path)
    assert "vec✗" in " ".join(sl._guardian_segments(_SID))
    (tmp_path / "vector_ready.flag").write_text("", encoding="utf-8")
    assert "vec✓" in " ".join(sl._guardian_segments(_SID))


def test_aec_latest_turn_wins(sl, tmp_path):
    d = tmp_path / "aec-report"
    d.mkdir()
    for turn, sev in ((1, "routine"), (12, "notable"), (3, "routine")):
        (d / f"{_SID}-t{turn}.json").write_text(
            json.dumps({"severity": sev}), encoding="utf-8"
        )
    assert sl._latest_aec_severity(_SID) == "notable"


def test_aec_absent_is_none(sl, tmp_path):
    assert sl._latest_aec_severity(_SID) is None


def test_bad_stdin_degrades(sl, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not-json"))
    sl.main()
    assert "no input" in capsys.readouterr().out
