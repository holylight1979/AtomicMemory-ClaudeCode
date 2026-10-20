"""verify_ollama_trace.py：tools/ollama_client 呼叫追蹤 log（旗標檔 workflow/.ollama_trace 控制）。

正例：旗標開 → 成功請求寫 ok 行（含 backend、model、caller）；指定模型與 backend 設定不符 → 寫 skip 行；
      第一台失敗切第二台 → 先 fail 再 ok；--trace on/off 建立／刪除旗標檔。
反例：旗標關 → 請求照常成功但不產生 log 檔（先斷言旗標確實不存在）。
不打真網路：_check_health／_do_request 換成假的。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_ollama_trace.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # tools/verify/ → repo 根
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ollama_client as oc  # noqa: E402


@pytest.fixture
def trace_paths(tmp_path, monkeypatch):
    flag = tmp_path / "workflow" / ".ollama_trace"
    log = tmp_path / "Logs" / "ollama-backend.log"
    monkeypatch.setattr(oc, "TRACE_FLAG", flag)
    monkeypatch.setattr(oc, "TRACE_LOG", log)
    return flag, log


def _client(monkeypatch, fail_names=()):
    backends = [
        oc.OllamaBackend(name="rdchat-direct", base_url="http://remote", llm_model="gemma4:e4b",
                         embedding_model="qwen3-embedding:latest", priority=1),
        oc.OllamaBackend(name="local", base_url="http://local", llm_model="qwen3:1.7b",
                         embedding_model="qwen3-embedding", priority=3),
    ]
    c = oc.OllamaClient(backends)
    monkeypatch.setattr(c, "_check_health", lambda b: True)

    def fake_request(backend, endpoint, payload, timeout):
        if backend.name in fail_names:
            return None
        if endpoint == "/api/embed":
            return {"embeddings": [[0.1]]}
        return {"message": {"content": "OK"}}

    monkeypatch.setattr(c, "_do_request", fake_request)
    return c


def _lines(log: Path):
    return log.read_text(encoding="utf-8").splitlines()


def test_flag_off_writes_nothing(trace_paths, monkeypatch):
    flag, log = trace_paths
    assert not flag.exists()
    c = _client(monkeypatch)
    assert c.generate("hi") == "OK"
    assert c.embed(["x"]) == [[0.1]]
    assert not log.exists()


def test_flag_on_records_ok(trace_paths, monkeypatch):
    flag, log = trace_paths
    oc._trace_cli("on")
    assert flag.exists()
    c = _client(monkeypatch)
    c.generate("hi")
    c.embed(["x"])
    lines = _lines(log)
    assert len(lines) == 2
    assert " ok backend=rdchat-direct model=gemma4:e4b endpoint=/api/chat " in lines[0]
    assert " ok backend=rdchat-direct model=qwen3-embedding:latest endpoint=/api/embed " in lines[1]
    assert "caller=" in lines[0] and "ms " in lines[0]


def test_explicit_model_mismatch_records_skip(trace_paths, monkeypatch):
    flag, log = trace_paths
    oc._trace_cli("on")
    c = _client(monkeypatch)
    c.generate("hi", model="qwen3:1.7b")
    lines = _lines(log)
    assert " skip:config_model=gemma4:e4b backend=rdchat-direct model=qwen3:1.7b " in lines[0]
    assert " ok backend=local model=qwen3:1.7b " in lines[1]


def test_failover_records_fail_then_ok(trace_paths, monkeypatch):
    flag, log = trace_paths
    oc._trace_cli("on")
    c = _client(monkeypatch, fail_names=("rdchat-direct",))
    assert c.generate("hi") == "OK"
    lines = _lines(log)
    assert " fail backend=rdchat-direct model=gemma4:e4b " in lines[0]
    assert " ok backend=local model=qwen3:1.7b " in lines[1]


def test_cli_off_removes_flag(trace_paths, capsys):
    flag, _ = trace_paths
    oc._trace_cli("on")
    assert flag.exists()
    oc._trace_cli("off")
    assert not flag.exists()
    assert "trace: OFF" in capsys.readouterr().out
