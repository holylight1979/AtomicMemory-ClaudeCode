"""tools/verify 共用的 pytest 設定。

做什麼：每一案自動設 WG_TEMP_RULES=off，關掉暫存目錄類放行規則（hooks/wg_release_rules.py 的 TEMP_* 規則）。
為什麼：案例的假專案建在 pytest 的 tmp（系統暫存目錄）下，規則開著會把它們當暫存副本處理。
要測暫存規則本身的案例自己用 monkeypatch.delenv("WG_TEMP_RULES") 開回來。
另外每一案預設 WG_V6=1（v6 守門總開關打開；出廠預設關）：這些案例測的是 v6 行為；外面明設 WG_V6 就照外面。
怎麼跑：pytest 自動載入，不用另外呼叫。
"""
import os

import pytest


@pytest.fixture(autouse=True)
def _wg_temp_rules_off(monkeypatch):
    monkeypatch.setenv("WG_TEMP_RULES", "off")


@pytest.fixture(autouse=True)
def _wg_v6_default_on(monkeypatch):
    if "WG_V6" not in os.environ:   # 外面明設 WG_V6 就照它
        monkeypatch.setenv("WG_V6", "1")
