"""verify_user_extract_l1_backend.py：萃取 L1（是非快篩）走 backend 預設模型，rdchat 可用時不先等 local。

正例：rdchat 正常 → L1 只送一次、打 rdchat-direct、模型是它設定的 gemma4:e4b，local 一次都沒碰。
正例：rdchat 掛了 → 自動換 local，模型跟著換成 local 設定的 qwen3:1.7b，仍拿到答案。
反例（退回舊碼會紅）：L1 指定 model=qwen3:1.7b → rdchat 被跳過、先打 local。
不打真網路：用真的 OllamaClient 路由，_check_health／_do_request 換成假的。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_user_extract_l1_backend.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_ROOT = HOOKS_DIR.parent
for p in (HOOKS_DIR, CLAUDE_ROOT, CLAUDE_ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import ollama_client as oc  # noqa: E402


def _load_worker():
    spec = importlib.util.spec_from_file_location("uew_l1_backend", HOOKS_DIR / "user-extract-worker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _client(monkeypatch, sent, down=()):
    c = oc.OllamaClient([
        oc.OllamaBackend(name="rdchat-direct", base_url="http://remote", llm_model="gemma4:e4b",
                         embedding_model="qwen3-embedding:latest", priority=1),
        oc.OllamaBackend(name="local", base_url="http://local", llm_model="qwen3:1.7b",
                         embedding_model="qwen3-embedding", priority=3),
    ])
    monkeypatch.setattr(c, "_check_health", lambda b: True)

    def fake_request(backend, endpoint, payload, timeout):
        sent.append((backend.name, payload["model"]))
        if backend.name in down:
            return None
        return {"message": {"content": '{"is_decision": true}'}}

    monkeypatch.setattr(c, "_do_request", fake_request)
    return c


def test_l1_uses_rdchat_default_model(monkeypatch):
    m = _load_worker()
    sent = []
    c = _client(monkeypatch, sent)
    monkeypatch.setattr(m, "get_client", lambda: c)
    assert m._call_l1("值得記嗎？") is True
    assert sent == [("rdchat-direct", "gemma4:e4b")]


def test_l1_falls_back_to_local_model_when_rdchat_down(monkeypatch):
    m = _load_worker()
    sent = []
    c = _client(monkeypatch, sent, down=("rdchat-direct",))
    monkeypatch.setattr(m, "get_client", lambda: c)
    assert m._call_l1("值得記嗎？") is True
    assert sent == [("rdchat-direct", "gemma4:e4b"), ("local", "qwen3:1.7b")]
