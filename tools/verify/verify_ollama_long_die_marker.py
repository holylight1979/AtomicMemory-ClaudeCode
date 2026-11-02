"""verify_ollama_long_die_marker.py：遠端 Ollama 長期停用後「要不要永久停用」的待問標記，過了恢復時刻就自己消失。

正例：標記的恢復時刻已過 → check_long_die_status 回 None、標記檔被刪（已自動重試，不再問使用者）；
      恢復時刻還沒到 → 照樣回標記內容、檔還在；連續失敗升到長期停用時寫的標記帶 until_at。
反例：沒記恢復時刻的舊標記 → 照舊回內容（問到使用者回覆為止），不誤刪。
不打真網路：直接呼叫寫標記與失敗計數。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_ollama_long_die_marker.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # tools/verify/ → repo 根
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ollama_client as oc  # noqa: E402


@pytest.fixture
def marker(tmp_path, monkeypatch):
    path = tmp_path / "workflow" / ".backend_long_die.json"
    monkeypatch.setattr(oc.OllamaClient, "LONG_DIE_MARKER", path)
    return path


def _backend():
    return oc.OllamaBackend(name="rdchat-direct", base_url="http://192.0.2.1:11434", llm_model="m", embedding_model="e")


def test_past_recovery_time_clears_marker(marker):
    oc.OllamaClient._write_long_die_marker(_backend(), "00:00", time.time() - 60)
    assert marker.exists()
    assert oc.check_long_die_status() is None
    assert not marker.exists()


def test_future_recovery_time_keeps_asking(marker):
    oc.OllamaClient._write_long_die_marker(_backend(), "23:59", time.time() + 3600)
    info = oc.check_long_die_status()
    assert info["backend"] == "rdchat-direct"
    assert marker.exists()


def test_old_marker_without_until_at_still_asks(marker):
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({"type": "long_die", "backend": "rdchat-direct", "until": "00:00"}), encoding="utf-8")
    assert oc.check_long_die_status()["backend"] == "rdchat-direct"
    assert marker.exists()


def test_escalation_writes_until_at(marker):
    client = oc.OllamaClient.__new__(oc.OllamaClient)
    client._state, client._health_cache = {}, {}
    backend = _backend()
    for _ in range(4):
        client._record_failure(backend)
    info = json.loads(marker.read_text(encoding="utf-8"))
    assert datetime.fromisoformat(info["until_at"]) > datetime.now()
