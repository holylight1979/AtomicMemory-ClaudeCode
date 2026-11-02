"""hooks/verify 共用的 pytest 設定。

做什麼：
1. 每一案自動設 WG_TEMP_RULES=off，關掉暫存目錄類放行規則（TEMP_COPY_NOT_PROJECT、TEMP_REPO_COMMIT_EXEMPT、暫存收據不採信）。
   為什麼：案例的假專案都建在 pytest 的 tmp（系統暫存目錄）下，規則開著會把它們整批當暫存副本，不注入導讀卡、不擋、收據不認。
   要測暫存規則本身的案例自己用 monkeypatch.delenv("WG_TEMP_RULES") 開回來。子行程的 env 若從 os.environ 複製也一併吃到。
2. 每一案給產出物帳本（handlers/aec_ledger 的 WORKFLOW_DIR/aec-tempfiles/<session>.jsonl）一個自己的空資料夾，放在受測目錄外。
   為什麼：同一次 pytest 的資料根是共用的、案例的 session id 又都一樣，前面案例建的暫存 repo 會留在帳上，後面每次收尾都去查
   它們的 git 狀態——案例變慢，錄製檔還錄進別案的路徑，單跑那一案就對不上。要測帳本本身的案例自己再換資料夾。
3. 每一案預設 WG_V6=1（v6 守門總開關打開）：這些案例測的是 v6 守門本身，總開關出廠預設關；外面明設 WG_V6 就照外面。
   測開關本身的案例（verify_v6_switch.py）自己設或清 WG_V6。
怎麼跑：pytest 自動載入，不用另外呼叫。
"""
import os
import sys

import pytest


@pytest.fixture(autouse=True)
def _wg_temp_rules_off(monkeypatch):
    monkeypatch.setenv("WG_TEMP_RULES", "off")


@pytest.fixture(autouse=True)
def _own_artifact_ledger(monkeypatch, tmp_path_factory):
    ledger = sys.modules.get("handlers.aec_ledger")   # 測試模組匯入 handlers 時載入；沒載入＝這支測試碰不到帳本
    if ledger is not None:
        monkeypatch.setattr(ledger, "WORKFLOW_DIR", tmp_path_factory.mktemp("aec-ledger"))


@pytest.fixture(autouse=True)
def _wg_v6_default_on(monkeypatch):
    if "WG_V6" not in os.environ:   # 外面明設 WG_V6 就照它
        monkeypatch.setenv("WG_V6", "1")
