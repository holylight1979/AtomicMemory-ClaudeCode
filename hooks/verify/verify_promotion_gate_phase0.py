"""verify_promotion_gate_phase0.py — Phase 0 地基 + Phase 2 效用晉升守門.

守住曾是已驗證缺陷 / 漂移的不變式（Phase 2 已強化第 2 條）：
1. `wg_episodic.py` 必須 `import time` —— 缺它，cross-session Confirmations 加計
   （L~369 `time.time()`）會 NameError 被 except 吞掉，主軌晉升從未真正累加。
2. **ReadHits（純注入次數）不得單獨晉升**。Phase 0 過渡為「readhits 需 confirmations≥1」；
   Phase 2 (#2) 正式取代為「真實 Confirmations OR 效用 Wilson 下界」，ReadHits 降為純曝光、
   完全退出晉升路徑。py（`wg_atoms._self_iterate_atoms`）與 js（`server.js`）雙鏡像都要守。
   依據：Xiong 2505.16067 —— 純檢索/注入頻率晉升會傳播錯誤、劣化品質。
3. `workflow/config.json` `self_iteration.promote_confirmations_threshold` 必須顯式存在。

純檔案讀取 + 純邏輯，無重依賴。
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


def test_wg_episodic_cross_session_dead_code_gone():
    """cross-session confirm 分支（原守門對象）已判死碼移除——worker 另有實作。
    此測改守「死碼不得回流」：_check_cross_session_patterns 不得重現於 wg_episodic。"""
    src = _read("hooks/wg_episodic.py")
    assert "_check_cross_session_patterns" not in src, (
        "死碼 _check_cross_session_patterns 不得回流 wg_episodic（無 caller，"
        "cross-session 實作在 extract-worker）"
    )
    assert "_update_memory_index" not in src, (
        "死碼 _update_memory_index 不得回流 wg_episodic（index upsert 走 funnel）"
    )


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
    """Phase 2：晉升鏡像改由 usefulnessStats / Wilson 下界驅動（拆檔後居 lib/atom-access.js + lib/atom-tools.js）。"""
    src = (_read("tools/workflow-guardian-mcp/lib/atom-access.js")
           + _read("tools/workflow-guardian-mcp/lib/atom-tools.js"))
    assert "usefulnessStats" in src and "wilsonLowerBound" in src, "atom-access.js 缺效用 Wilson 鏡像"
    assert not re.search(
        r"readhits\s*>=\s*reqRH\s*&&\s*confirmations\s*>\s*0", src
    ), "Phase 2 應移除 readhits 輔助晉升門（lib/atom-tools.js toolAtomPromote）"


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


def _wilson_lb(successes: int, n: int, z: float) -> float:
    """複刻 py↔js 鏡像公式（lib/atom_access.py wilson_lower_bound /
    atom-access.js wilsonLowerBound）——測試端獨立實作，防兩邊同時漂。"""
    if n <= 0:
        return 0.0
    phat = successes / n
    denom = 1.0 + (z * z) / n
    centre = phat + (z * z) / (2.0 * n)
    margin = z * ((phat * (1.0 - phat) + (z * z) / (4.0 * n)) / n) ** 0.5
    return max(0.0, min(1.0, (centre - margin) / denom))


def test_js_wilson_z_128():
    """z 校準 1.96→1.28（~80% 單尾）：js 側常數與 fallback 都要是 1.28。
    z=1.28 下 3 連勝 lb≈0.647 ≥ promote_lb 0.6（1.96 時僅 0.438 → 永遠晉升不了）。"""
    access_src = _read("tools/workflow-guardian-mcp/lib/atom-access.js")
    tools_src = _read("tools/workflow-guardian-mcp/lib/atom-tools.js")
    assert "POWER_WILSON_Z = 1.28" in access_src, "atom-access.js POWER_WILSON_Z 應為 1.28"
    assert re.search(r"uconf\.wilson_z\s*!=\s*null\s*\?\s*uconf\.wilson_z\s*:\s*1\.28", tools_src), \
        "atom-tools.js wilson_z fallback 應為 1.28"
    assert "1.96" not in access_src and "1.96" not in tools_src, "js 側殘留 z=1.96"
    # 期望值（與 node 實算對拍，見公式鏡像）
    assert abs(_wilson_lb(3, 3, 1.28) - 0.6468) < 5e-4
    assert abs(_wilson_lb(4, 4, 1.28) - 0.7094) < 5e-4
    assert abs(_wilson_lb(2, 3, 1.28) - 0.3215) < 5e-4
    assert _wilson_lb(3, 3, 1.28) >= 0.6, "z=1.28 下 3 連勝應過 promote_lb=0.6"


def test_js_promote_replace_scoped_to_knowledge_section():
    """[臨]→[觀] 條目改寫必須限定 ## 知識 段落且行首錨定——
    全文全域替換會誤改 ## 行動 區與引文中的同字樣。"""
    src = _read("tools/workflow-guardian-mcp/lib/atom-tools.js")
    assert not re.search(r"new RegExp\(`- \$\{meta\.confidence[^`]*`,\s*\"g\"\)", src), \
        "promote 不得再用全文 g-flag 替換知識條目"
    assert "confLineRe" in src and "inKnowledge" in src and "## 知識" in src, \
        "promote 應以 ## 知識 段落邊界 + 行首錨定改寫條目"


def test_gate_semantics():
    # 純曝光（無 confirmations、無效用證據）不得晉升
    assert _eligible(0, {"useful_hits": 1, "used_fail": 1}) is False
    # primary confirmations 達標應晉升
    assert _eligible(4, {"useful_hits": 1, "used_fail": 1}) is True
    # 效用 Wilson 達標（z=1.28 下 3 連勝 lb≈0.647）應晉升
    assert _eligible(0, {"useful_hits": 4, "used_fail": 1}) is True
    # 效用未達下界（2 勝 1 敗，lb≈0.32<0.6）不得晉升
    assert _eligible(0, {"useful_hits": 3, "used_fail": 2}) is False
    # 樣本不足（n=2<3）不得晉升——即使 2 連勝
    assert _eligible(0, {"useful_hits": 3, "used_fail": 1}) is False
