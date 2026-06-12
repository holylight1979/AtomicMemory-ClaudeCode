"""verify_usefulness_loop_phase2.py — Phase 2 (#2) 注入→使用→結果 閉環守門 (2026-06-01).

守住 hook 層 Phase 2 不變式：
1. detect_atom_use（詞彙重疊）：used 場景（code/CJK 稀有 token 交集）True、無關 False、空 atom no_rare。
2. _detect_turn_outcome（3 值）：failing/evasion/retry→0、完成宣告且乾淨→+1、其餘→unknown(None)。
3. get_current_turn_text：turn 邊界 = 最後一則真實 user prompt（非 tool_result）之後的 assistant 活動。
4. 端到端 _attribute_usefulness：
   - used+success → α++；unused → 不動；used+fail → β++；unknown → 不動。
   - per-turn 一次性（turn_seq 守門，重呼不重複計）。
   - sub-agent 注入（subagent_injections）一併歸因，agent error 覆寫為 fail。

受控 tmp atom + tmp 轉錄，不依賴磁碟既有 atom。Design: plans/typed-purring-stearns.md Phase 2。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
import wg_evasion  # noqa: E402
from lib import atom_access as A  # noqa: E402
from handlers.stop import _attribute_usefulness, _detect_turn_outcome  # noqa: E402


ATOM_BODY = (
    "# atom-x\n"
    "- [臨] atom_write 兩個防護缺口：mode=replace 無閘 silent upsert；"
    "server.js 新增 findSeparatorVariant(memDir, slug) 守門，create 命中變體即擋。"
    "lib/atom_spec.py 規則唯一來源，改全域 MCP server 需重啟生效。\n"
)
USED_TURN = (
    "我新增了 findSeparatorVariant 到 server.js 並守住 atom_write 的 replace 路徑，"
    "編輯 tools/workflow-guardian-mcp/server.js 與 lib/atom_spec.py。"
)
UNUSED_TURN = (
    "我重構了 React 元件 state，修了 dashboard widget 的 CSS flexbox 版面，"
    "更新 styles.css 與 App.jsx。"
)


@pytest.fixture(autouse=True)
def _silence_audit(monkeypatch):
    monkeypatch.setattr(A, "_audit_log", lambda *a, **k: None)


@pytest.fixture
def atom_md(tmp_path):
    p = tmp_path / "atom-x.md"
    p.write_text(ATOM_BODY, encoding="utf-8")
    return p


def _write_transcript(tmp_path, records):
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    return p


def _user(text):
    return {"type": "user", "message": {"content": text}}


def _assistant(text, tool=None):
    content = [{"type": "text", "text": text}]
    if tool:
        content.append({"type": "tool_use", "name": tool[0], "input": tool[1]})
    return {"type": "assistant", "message": {"content": content}}


def _tool_result():
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}


# ─── 1. detect_atom_use（詞彙重疊）────────────────────────────────────────────


def test_detect_use_positive():
    det = wg_atoms.detect_atom_use(ATOM_BODY, USED_TURN)
    assert det["used"] is True and det["shared"] >= 2 and det["method"] == "lexical"


def test_detect_use_negative():
    det = wg_atoms.detect_atom_use(ATOM_BODY, UNUSED_TURN)
    assert det["used"] is False


def test_detect_use_empty_atom():
    det = wg_atoms.detect_atom_use("", USED_TURN)
    assert det["used"] is False and det["method"] == "no_rare"


def test_detect_use_cjk_overlap():
    atom = "# r\n- [固] 大型任務分階段執行，每階段完成驗證後上版控，commit message 繁體中文。\n"
    used = "本次把大型任務拆成三階段，每階段完成後驗證並上版控，commit message 用繁體中文。"
    unused = "今天天氣很好去公園散步看到很多花朵盛開非常漂亮心情愉快。"
    assert wg_atoms.detect_atom_use(atom, used)["used"] is True
    assert wg_atoms.detect_atom_use(atom, unused)["used"] is False


def test_detect_use_embed_tiebreak_stub():
    # 差一個 token 的邊界（shared==1，且 containment<overlap_min）→ embed_fn 高 cosine 救回。
    # 6 個 ≥7 字無分隔的稀有 token，turn 只共享 1 個 → containment=1/6≈0.167<0.18。
    atom = "# t\n- [臨] qwertyu asdfghj zxcvbnm poiuytr lkjhgfd mnbvcxz handle caches.\n"
    turn = "I touched qwertyu once."  # 只共享 1 個稀有 token
    base = wg_atoms.detect_atom_use(atom, turn, rare_token_min=2, overlap_min=0.18)
    assert base["used"] is False and base["shared"] == 1
    saved = wg_atoms.detect_atom_use(atom, turn, rare_token_min=2, overlap_min=0.18, embed_fn=lambda a, b: 0.9)
    assert saved["used"] is True and saved["method"] == "embed"
    # 低 cosine 不救
    nope = wg_atoms.detect_atom_use(atom, turn, rare_token_min=2, overlap_min=0.18, embed_fn=lambda a, b: 0.3)
    assert nope["used"] is False


# ─── 2. _detect_turn_outcome（3 值）───────────────────────────────────────────


def test_outcome_fail_on_failing_tests():
    assert _detect_turn_outcome({"failing_tests": [{"cmd": "pytest"}]}, "完成") is False


def test_outcome_fail_on_evasion():
    assert _detect_turn_outcome({"evasion_flag": {"phrase": "x"}}, "完成") is False


def test_outcome_fail_on_retry():
    assert _detect_turn_outcome({"wisdom_retry_count": 2}, "完成") is False


def test_outcome_success_on_clean_completion():
    assert _detect_turn_outcome({}, "已全部完成並驗證") is True


def test_outcome_unknown_when_no_signal():
    assert _detect_turn_outcome({}, "我繼續看一下這段程式碼") is None


# ─── 3. get_current_turn_text（turn 邊界）─────────────────────────────────────


def test_turn_text_extracts_current_turn(tmp_path):
    tr = _write_transcript(tmp_path, [
        _user("請修 atom_write 的防護"),
        _assistant("我來改 atom_access", ("Edit", {"file_path": "server.js", "new_string": "findSeparatorVariant"})),
        _tool_result(),
        _assistant("完成 findSeparatorVariant 修復"),
    ])
    txt = wg_evasion.get_current_turn_text(tr)
    assert "atom_access" in txt and "findSeparatorVariant" in txt and "server.js" in txt


def test_turn_text_boundary_is_last_real_prompt(tmp_path):
    tr = _write_transcript(tmp_path, [
        _user("第一個任務"),
        _assistant("處理 FIRSTTOKEN 第一段"),
        _user("第二個任務"),  # 新的真實 prompt → 邊界
        _assistant("處理 SECONDTOKEN 第二段"),
    ])
    txt = wg_evasion.get_current_turn_text(tr)
    assert "SECONDTOKEN" in txt and "FIRSTTOKEN" not in txt


def test_turn_text_empty_on_missing():
    assert wg_evasion.get_current_turn_text(None) == ""


# ─── 4. 端到端 _attribute_usefulness ─────────────────────────────────────────

CONFIG = {"usefulness": {"enabled": True, "rare_token_min": 2, "lexical_overlap_min": 0.18}}


def _state(atom_md, **extra):
    s = {"turn_seq": 1, "turn_injected": [{"name": "atom-x", "path": str(atom_md)}]}
    s.update(extra)
    return s


def test_attr_used_success_increments_alpha(tmp_path, atom_md):
    tr = _write_transcript(tmp_path, [_user("修 atom_write"), _assistant(USED_TURN)])
    state = _state(atom_md)
    _attribute_usefulness(state, CONFIG, "sess", tr, "已完成")
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 2 and acc["used_fail"] == 1
    assert state["usefulness_attributed_seq"] == 1


def test_attr_unused_no_change(tmp_path, atom_md):
    tr = _write_transcript(tmp_path, [_user("改 CSS"), _assistant(UNUSED_TURN)])
    _attribute_usefulness(_state(atom_md), CONFIG, "sess", tr, "已完成")
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 1 and acc["used_fail"] == 1  # 未使用 → 不動


def test_attr_used_fail_increments_beta(tmp_path, atom_md):
    tr = _write_transcript(tmp_path, [_user("修 atom_write"), _assistant(USED_TURN)])
    state = _state(atom_md, failing_tests=[{"cmd": "pytest"}])
    _attribute_usefulness(state, CONFIG, "sess", tr, "已完成")
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 1 and acc["used_fail"] == 2


def test_attr_unknown_outcome_no_change(tmp_path, atom_md):
    tr = _write_transcript(tmp_path, [_user("修 atom_write"), _assistant(USED_TURN)])
    # last_text 無完成宣告、state 無 fail 訊號 → outcome unknown → no-op
    _attribute_usefulness(_state(atom_md), CONFIG, "sess", tr, "我再看看這段")
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 1 and acc["used_fail"] == 1


def test_attr_once_per_turn_guard(tmp_path, atom_md):
    tr = _write_transcript(tmp_path, [_user("修 atom_write"), _assistant(USED_TURN)])
    state = _state(atom_md)
    _attribute_usefulness(state, CONFIG, "sess", tr, "已完成")
    _attribute_usefulness(state, CONFIG, "sess", tr, "已完成")  # 同 turn_seq 重呼
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 2  # 不重複計


def test_attr_disabled_noop(tmp_path, atom_md):
    tr = _write_transcript(tmp_path, [_user("修 atom_write"), _assistant(USED_TURN)])
    _attribute_usefulness(_state(atom_md), {"usefulness": {"enabled": False}}, "sess", tr, "已完成")
    assert A.read_access(atom_md)["useful_hits"] == 1


def test_attr_subagent_injection(tmp_path, atom_md, monkeypatch):
    monkeypatch.setattr(wg_atoms, "resolve_atom_path", lambda name: atom_md if name == "atom-x" else None)
    tr = _write_transcript(tmp_path, [_user("派 agent"), _assistant("派發子任務")])
    state = {
        "turn_seq": 1, "turn_injected": [],
        "subagent_injections": [{
            "agent_id": "a1", "agent_type": "Explore", "atoms": ["atom-x"],
            "status": "success", "output_summary": USED_TURN, "attributed": False,
        }],
    }
    _attribute_usefulness(state, CONFIG, "sess", tr, "已完成")
    acc = A.read_access(atom_md)
    assert acc["useful_hits"] == 2  # sub-agent 用上 + 成功 → α++
    assert state["subagent_injections"][0]["attributed"] is True


def test_attr_subagent_error_forces_fail(tmp_path, atom_md, monkeypatch):
    monkeypatch.setattr(wg_atoms, "resolve_atom_path", lambda name: atom_md if name == "atom-x" else None)
    tr = _write_transcript(tmp_path, [_user("派 agent"), _assistant("派發子任務")])
    state = {
        "turn_seq": 1, "turn_injected": [],
        "subagent_injections": [{
            "agent_id": "a1", "agent_type": "Explore", "atoms": ["atom-x"],
            "status": "error", "output_summary": USED_TURN, "attributed": False,
        }],
    }
    _attribute_usefulness(state, CONFIG, "sess", tr, "已完成")  # 即使宣告完成，agent error → fail
    acc = A.read_access(atom_md)
    assert acc["used_fail"] == 2 and acc["useful_hits"] == 1


# ─── 5. usefulness_hint_tier（UPS 注入晉升提示分級）──────────────────────────


def test_hint_tier_eligible():
    # 6 連勝 lb≈0.61 ≥ promote_lb(0.6) → eligible
    assert A.usefulness_hint_tier({"useful_hits": 7, "used_fail": 1}) == "eligible"


def test_hint_tier_near():
    # 4 連勝 lb≈0.51 ∈ [0.5, 0.6) → near（接近升門）
    assert A.usefulness_hint_tier({"useful_hits": 5, "used_fail": 1}) == "near"


def test_hint_tier_none_low_lb():
    # 多次失敗 lb≈0（離升門遠）→ None
    assert A.usefulness_hint_tier({"useful_hits": 1, "used_fail": 5}) is None


def test_hint_tier_none_insufficient_n():
    # n=2 < min_n=3 → None（樣本不足不提示）
    assert A.usefulness_hint_tier({"useful_hits": 3, "used_fail": 1}) is None


def test_hint_tier_pure_exposure_none():
    # 純 prior(α=β=1，無任何使用證據) → None，杜絕純曝光（ReadHits）雜訊
    assert A.usefulness_hint_tier({"useful_hits": 1, "used_fail": 1}) is None


# ─── 6. UPS 注入晉升提示：效用導向，ReadHits 退場 ─────────────────────────────


def test_ups_hint_is_usefulness_driven():
    """UPS 注入提示改由效用 Wilson 下界驅動；stale ReadHits 晉升提示須完全退場。

    2026-06-12 熱點重構後注入段移至 handlers/ups_inject.py，orchestrator 一併掃描
    確認 stale 邏輯沒有殘留在任何一邊。
    """
    src = (CLAUDE / "hooks" / "handlers" / "ups_inject.py").read_text(encoding="utf-8")
    src += (CLAUDE / "hooks" / "handlers" / "user_prompt_submit.py").read_text(encoding="utf-8")
    assert "usefulness_hint_tier" in src, "UPS 未接 usefulness_hint_tier"
    assert "READHIT_THRESHOLDS" not in src, "UPS 應移除 ReadHits 晉升提示門檻字典"
    assert "ReadHits 已達" not in src, "UPS 應移除 stale ReadHits 晉升提示語"
