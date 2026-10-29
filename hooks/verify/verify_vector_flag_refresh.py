"""verify_vector_flag_refresh.py — SessionStart 冷啟動關窗 flag 刷新契約。

_refresh_vector_flag（handlers.session_start）：
- 服務 health 200 → 寫/保留 vector_ready.flag（回 'kept'），首個 prompt 即可用 vector，
  消掉舊「無條件拆 flag → async 重建」之間的 no_flag 空窗
- 服務無回應（urlopen raise）→ 拆 flag（回 'cleared'，fail-closed，防信任指向死服務的舊 flag）
- flag 不存在時拆亦不報錯（missing_ok）
- config 無 service_port → 預設 3849

受控 tmp flag_path，不動真實 workflow/ flag；monkeypatch urlopen 不打真實 port。
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import urllib.request  # noqa: E402
from handlers import session_start  # noqa: E402

CONFIG = {"vector_search": {"service_port": 3849}}


def _mock_ok(*a, **k):
    return None  # helper 忽略回傳值，只在意有無 raise


def _mock_fail(*a, **k):
    raise OSError("connection refused")


def test_healthy_writes_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _mock_ok)
    flag = tmp_path / "vector_ready.flag"
    assert not flag.exists()
    assert session_start._refresh_vector_flag(CONFIG, flag_path=flag) == "kept"
    assert flag.read_text(encoding="utf-8") == "ready"


def test_healthy_keeps_existing_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _mock_ok)
    flag = tmp_path / "vector_ready.flag"
    flag.write_text("ready", encoding="utf-8")
    assert session_start._refresh_vector_flag(CONFIG, flag_path=flag) == "kept"
    assert flag.exists()


def test_down_clears_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _mock_fail)
    flag = tmp_path / "vector_ready.flag"
    flag.write_text("ready", encoding="utf-8")
    assert session_start._refresh_vector_flag(CONFIG, flag_path=flag) == "cleared"
    assert not flag.exists()


def test_down_missing_flag_no_error(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _mock_fail)
    flag = tmp_path / "vector_ready.flag"
    assert not flag.exists()
    assert session_start._refresh_vector_flag(CONFIG, flag_path=flag) == "cleared"
    assert not flag.exists()


def test_default_port_when_config_empty(tmp_path, monkeypatch):
    captured = {}

    def _cap(url, *a, **k):
        captured["url"] = url
        return None

    monkeypatch.setattr(urllib.request, "urlopen", _cap)
    flag = tmp_path / "vector_ready.flag"
    assert session_start._refresh_vector_flag({}, flag_path=flag) == "kept"
    assert "3849" in captured["url"]


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_index_error_surfaces_advisory(monkeypatch):
    """服務活著但上次索引失敗（/status 的 index_job.error）→ 一行 [Guardian:Vector]，帶錯誤原文。"""
    body = '{"index_job": {"running": false, "error": "\'cp950\' codec can\'t encode character"}}'.encode("utf-8")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(body))
    out = session_start._vector_index_advisory(CONFIG)
    assert len(out) == 1 and out[0].startswith("[Guardian:Vector]") and "cp950" in out[0]


def test_index_ok_or_service_down_no_advisory(monkeypatch):
    """上次索引成功 → 不出；服務沒回應 → 不出（那是 vec✗ 的事）。"""
    ok = b'{"index_job": {"running": false, "result": {"chunks": 10}}}'
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp(ok))
    assert session_start._vector_index_advisory(CONFIG) == []
    monkeypatch.setattr(urllib.request, "urlopen", _mock_fail)
    assert session_start._vector_index_advisory(CONFIG) == []
