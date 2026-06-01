"""verify_promotion_gate_phase0.py — Phase 0 地基修復守門 (2026-06-01).

守住三件曾是已驗證缺陷 / 漂移的不變式：
1. `wg_episodic.py` 必須 `import time` —— 缺它，cross-session Confirmations 加計
   （L~369 `time.time()`）會 NameError 被 except 吞掉，主軌晉升從未真正累加。
2. 晉升 auxiliary gate：ReadHits（純注入次數）不得**單獨**晉升，需 Confirmations ≥1。
   py（`wg_atoms._self_iterate_atoms`）與 js（`server.js`）雙鏡像都要守。
   依據：Xiong 2505.16067 —— 純檢索/注入頻率晉升會傳播錯誤、劣化品質。
3. `workflow/config.json` `self_iteration.promote_confirmations_threshold` 必須顯式存在
   （否則 wg_atoms 永遠用隱性 default 4）。

純檔案讀取 + 純邏輯，無重依賴。Design: plans/typed-purring-stearns.md Phase 0。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[2]  # hooks/verify/ → ~/.claude


def _read(rel: str) -> str:
    return (CLAUDE / rel).read_text(encoding="utf-8")


def test_wg_episodic_imports_time():
    """缺 import time → cross-session confirm 分支 NameError（主軌晉升死）。"""
    src = _read("hooks/wg_episodic.py")
    assert re.search(r"^import time$", src, re.MULTILINE), "wg_episodic.py 缺 import time"
    assert "time.time()" in src, "守門點 time.time() 不在 → 測試前提失效"


def test_config_has_promote_confirmations_threshold():
    si = json.loads(_read("workflow/config.json")).get("self_iteration", {})
    assert "promote_confirmations_threshold" in si, "config 缺 promote_confirmations_threshold"
    assert isinstance(si["promote_confirmations_threshold"], int)


def test_py_aux_gate_requires_confirmation():
    """wg_atoms 晉升 readhits 路徑須 `and confirmations > 0`（防純注入晉升回歸）。"""
    src = _read("hooks/wg_atoms.py")
    assert re.search(
        r"readhits\s*>=\s*promote_min_conf\s*and\s*confirmations\s*>\s*0", src
    ), "wg_atoms aux gate 未要求 confirmations > 0"


def test_js_aux_gate_requires_confirmation():
    """server.js 晉升 aux gate 鏡像：`readhits >= reqRH && confirmations > 0`。"""
    src = _read("tools/workflow-guardian-mcp/server.js")
    assert re.search(
        r"readhits\s*>=\s*reqRH\s*&&\s*confirmations\s*>\s*0", src
    ), "server.js aux gate 未要求 confirmations > 0"


def _eligible(confirmations: int, readhits: int, req_conf: int = 4, req_rh: int = 20) -> bool:
    """複刻 Phase 0 晉升判定（py↔js 共同語義），純邏輯守門。"""
    return confirmations >= req_conf or (readhits >= req_rh and confirmations > 0)


def test_gate_semantics():
    assert _eligible(0, 999) is False, "純注入次數（confirmations=0）不得晉升"
    assert _eligible(1, 20) is True, "readhits 達標 + 至少 1 confirm 應晉升"
    assert _eligible(4, 0) is True, "primary confirmations 達標應晉升"
    assert _eligible(0, 19) is False
    assert _eligible(3, 19) is False, "兩軌皆未達不得晉升"
