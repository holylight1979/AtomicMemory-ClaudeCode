"""verify_promotion_gate_phase0.py — Phase 0 地基 + Phase 2 效用晉升守門 (2026-06-01).

守住曾是已驗證缺陷 / 漂移的不變式（Phase 2 已強化第 2 條）：
1. `wg_episodic.py` 必須 `import time` —— 缺它，cross-session Confirmations 加計
   （L~369 `time.time()`）會 NameError 被 except 吞掉，主軌晉升從未真正累加。
2. **ReadHits（純注入次數）不得單獨晉升**。Phase 0 過渡為「readhits 需 confirmations≥1」；
   Phase 2 (#2) 正式取代為「真實 Confirmations OR 效用 Wilson 下界」，ReadHits 降為純曝光、
   完全退出晉升路徑。py（`wg_atoms._self_iterate_atoms`）與 js（`server.js`）雙鏡像都要守。
   依據：Xiong 2505.16067 —— 純檢索/注入頻率晉升會傳播錯誤、劣化品質。
3. `workflow/config.json` `self_iteration.promote_confirmations_threshold` 必須顯式存在。

純檔案讀取 + 純邏輯，無重依賴。Design: plans/typed-purring-stearns.md Phase 0+2。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parents[2]  # hooks/verify/ → ~/.claude
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))


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


def test_py_gate_usefulness_driven():
    """Phase 2：wg_atoms 晉升改由 usefulness_promote_eligible（Wilson 下界）驅動。"""
    src = _read("hooks/wg_atoms.py")
    assert "usefulness_promote_eligible" in src, "wg_atoms 未接 usefulness_promote_eligible"
    # 已退場：readhits 不得再是晉升路徑
    assert not re.search(
        r"readhits\s*>=\s*promote_min_conf", src
    ), "Phase 2 應移除 readhits 晉升路徑（ReadHits 降純曝光）"


def test_js_gate_usefulness_driven():
    """Phase 2：server.js 晉升鏡像改由 usefulnessStats / Wilson 下界驅動。"""
    src = _read("tools/workflow-guardian-mcp/server.js")
    assert "usefulnessStats" in src and "wilsonLowerBound" in src, "server.js 缺效用 Wilson 鏡像"
    assert not re.search(
        r"readhits\s*>=\s*reqRH\s*&&\s*confirmations\s*>\s*0", src
    ), "Phase 2 應移除 server.js readhits 輔助晉升門"


def test_readhits_alone_not_promotion_trigger():
    """核心不變式（Phase 2 強化）：純注入頻率（readhits）絕不單獨晉升。"""
    from lib import atom_access as A
    # 只有 readhits、無 confirmations、無效用證據 → 不得晉升
    assert A.usefulness_promote_eligible({"useful_hits": 1, "used_fail": 1}) is False


def _eligible(confirmations, access, req_conf=4, promote_lb=0.6, min_n=3):
    """複刻 Phase 2 晉升判定（py↔js 共同語義）：Confirmations 主軌 OR 效用 Wilson 下界。"""
    from lib import atom_access as A
    return confirmations >= req_conf or A.usefulness_promote_eligible(
        access, promote_lb=promote_lb, min_n=min_n)


def test_gate_semantics():
    # 純曝光（無 confirmations、無效用證據）不得晉升
    assert _eligible(0, {"useful_hits": 1, "used_fail": 1}) is False
    # primary confirmations 達標應晉升
    assert _eligible(4, {"useful_hits": 1, "used_fail": 1}) is True
    # 效用 Wilson 達標（6 連勝，lb≈0.61）應晉升
    assert _eligible(0, {"useful_hits": 7, "used_fail": 1}) is True
    # 效用未達下界（lb≈0.51<0.6）不得晉升
    assert _eligible(0, {"useful_hits": 5, "used_fail": 1}) is False
    # 樣本不足（n=2<3）不得晉升
    assert _eligible(0, {"useful_hits": 3, "used_fail": 1}) is False
