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
