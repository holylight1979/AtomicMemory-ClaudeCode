"""hooks/verify 共用的 pytest 設定。

做什麼：每一案自動設 WG_TEMP_RULES=off，關掉暫存目錄類放行規則（TEMP_COPY_NOT_PROJECT、TEMP_REPO_COMMIT_EXEMPT、暫存收據不採信）。
為什麼：案例的假專案都建在 pytest 的 tmp（系統暫存目錄）下，規則開著會把它們整批當暫存副本，不注入導讀卡、不擋、收據不認。
要測暫存規則本身的案例自己用 monkeypatch.delenv("WG_TEMP_RULES") 開回來。子行程的 env 若從 os.environ 複製也一併吃到。
怎麼跑：pytest 自動載入，不用另外呼叫。
"""
import pytest


@pytest.fixture(autouse=True)
def _wg_temp_rules_off(monkeypatch):
    monkeypatch.setenv("WG_TEMP_RULES", "off")
