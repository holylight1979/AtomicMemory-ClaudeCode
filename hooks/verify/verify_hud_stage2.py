"""verify_hud_stage2.py — HUD 改版第 2 階段：內容白話、報告不進聊天、紅燈精準、刪 (c) 欄。

契約：
  - 紅燈精準（規則 EVASION_CONTEXT_EXEMPT）：退避軟偵測在 context 用量超過門檻、命中的是「下個／新 session、之後／下次再」
    這類延後語、被推的事有落地（本回合 (k) 有內容或寫了交接檔）、本回合使用者原話在而且沒叫現在做——四件都有證據才豁免；
    判不出（量不出 context、turn_prompts 缺／空／不是這回合）一律不豁免。門檻邊界和 DeferralGate 一致（剛好等於門檻不豁免）。
  - 詞表不把技術事實（「新 session 才會載入」）與驗證範圍自己的用語（「範圍外的測試」）當退避。
  - 報告不進聊天：HUD 開不起來時 Stop 不擋、只印一行指出報告檔；MCP 回條一行。
  - 收尾檢核不再有 (c) Token 警示欄；(d) 寫「見收割報告」要本回合真的交過核對過的收割報告。
  - HUD 卡片：燈號＋一句話 → 要你處理 → 這輪做了什麼 → 記住了／之後要追；欄位字母收進「細節」。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_hud_stage2.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
TREE = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_evasion as ev  # noqa: E402
import wg_release_rules as rr  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from handlers import stop as st  # noqa: E402

_SID = "sid-stage2"
_LIB = TREE / "tools" / "workflow-guardian-mcp" / "lib"


# ─── EVASION_CONTEXT_EXEMPT（純判定） ─────────────────────────────────────────

_OK = dict(exempt_phrase=True, ratio=0.82, max_ratio=0.75, landed=True, prompts=["繼續把第 2 階段做完"], prompts_current=True)


@pytest.mark.parametrize("change, exempt, why", [
    ({}, True, "四件都有證據 → 豁免"),
    ({"ratio": 0.75}, False, "剛好等於門檻：和 DeferralGate 一樣算 context 還夠，不豁免"),
    ({"ratio": 0.5}, False, "context 還夠"),
    ({"ratio": 0.0}, False, "量不出 context"),
    ({"exempt_phrase": False}, False, "命中的不是延後語（例如範圍推諉）"),
    ({"landed": False}, False, "被推的事沒落地（(k) 沒內容、也沒寫交接檔）"),
    ({"prompts": None}, False, "turn_prompts 不存在＝判不出"),
    ({"prompts": []}, False, "turn_prompts 是空的＝判不出"),
    ({"prompts_current": False}, False, "turn_prompts 不是這一回合的＝判不出"),
    ({"prompts": ["現在把它做完"]}, False, "使用者叫現在做"),
    ({"prompts": ["還有下一個 session ? 這邊做不完嗎?"]}, False, "使用者問這邊做不完嗎＝要在這裡做"),
])
def test_evasion_context_exempt(change, exempt, why):
    v = rr.evasion_context_exempt_verdict(**{**_OK, **change})
    assert v.rule == "EVASION_CONTEXT_EXEMPT" and v.owed is (not exempt), why


def test_exempt_phrase_subset_and_false_positives():
    """可豁免的只有延後到下個／新 session、之後／下次再；技術事實與驗證範圍用語不算退避；真退避照抓。"""
    assert ev.is_context_exempt_phrase("下個 session") and ev.is_context_exempt_phrase("之後再處理")
    assert not ev.is_context_exempt_phrase("非本次改動") and not ev.is_context_exempt_phrase("pre-existing")
    for text in ("Node 端改動要開新 session 才會載入，所以請重開視窗。",
                 "範圍外的測試因這次改動紅了，已查明和改動無關。"):
        assert ev.detect_evasion(text, []) is None, text
    for text in ("這塊範圍外，先不處理。", "剩下的留給下個 session 處理。", "其餘的開新 session 再做。"):
        assert ev.detect_evasion(text, []) is not None, text


# ─── Stop：退避偵測接上 context 豁免 ─────────────────────────────────────────

@pytest.fixture
def stop_run(monkeypatch):
    logged: list = []
    for name, val in (("_find_session_transcript", lambda *a, **k: None), ("token_warn_payload", lambda *a, **k: ""),
                      ("write_state", lambda *a, **k: None), ("_attribute_usefulness", lambda *a, **k: None),
                      ("_detect_uncommitted_files", lambda mf: []), ("_git_unpushed_roots", lambda mf: []),
                      ("_should_deep_postmortem", lambda *a, **k: False),
                      ("_maybe_spawn_user_extract_worker", lambda *a, **k: None), ("_hud_alive", lambda *a, **k: (True, {}))):
        monkeypatch.setattr(st, name, val)
    monkeypatch.setattr(st, "append_guard_log", lambda kind, payload: logged.append((kind, payload)))

    monkeypatch.setattr(st, "coding_turn", lambda *a, **k: True)   # 測閘本身：當成寫碼回合（CODING_TURN_ONLY 的案在 verify_gate_trim）

    def run(capsys, state, text, ratio):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: text)
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        monkeypatch.setattr(st, "estimate_context_usage", lambda *a, **k: ratio)
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": ""}, {})
        capsys.readouterr()
        return logged

    return run


def _landed_state(**extra):
    s = {"phase": "working", "modified_files": [], "failing_tests": [], "recent_user_prompts": ["繼續"],
         "stop_blocked_count": 0, "turn_seq": 9, "turn_prompts": ["繼續"], "turn_prompts_seq": 9,
         "anti_evasion_report": {"session_id": _SID, "turn_seq": 9, "k_followups": "[HUD] 第 2 階段的彈窗設定"}}
    s.update(extra)
    return s


def test_stop_exempts_landed_deferral_when_context_is_full(stop_run, capsys):
    text = "第 2 階段剩下的彈窗設定留給下個 session 處理，已寫進追蹤項。"
    state = _landed_state()
    logged = stop_run(capsys, state, text, 0.86)
    assert not state.get("evasion_flag") and not state.get("evasion_events")
    assert any(k == "evasion_exempt" for k, _ in logged), logged


def test_stop_still_flags_when_context_is_plenty_or_k_is_placeholder(stop_run, capsys):
    text = "第 2 階段剩下的彈窗設定留給下個 session 處理，已寫進追蹤項。"
    state = _landed_state()
    stop_run(capsys, state, text, 0.4)
    assert state.get("evasion_flag"), "context 還夠 → 照標"
    state = _landed_state(anti_evasion_report={"session_id": _SID, "turn_seq": 9, "k_followups": "無"})
    stop_run(capsys, state, text, 0.86)
    assert state.get("evasion_flag"), "(k) 只寫「無」不算落地"


def test_stop_handoff_file_written_this_turn_counts_as_landed(stop_run, capsys):
    """(k) 沒內容，但本回合寫了 memory/_staging/next-phase-*.md → 也算落地；別回合寫的不算。"""
    text = "第 2 階段剩下的彈窗設定留給下個 session 處理，已寫進交接單。"
    hand = {"path": r"C:\Users\u\.claude\memory\_staging\next-phase-hud-3.md", "tool": "Write",
            "session_id": _SID, "turn_seq": 9, "last_turn_seq": 9}
    state = _landed_state(anti_evasion_report={}, modified_files=[hand])
    stop_run(capsys, state, text, 0.86)
    assert not state.get("evasion_flag")
    state = _landed_state(anti_evasion_report={}, modified_files=[{**hand, "turn_seq": 3, "last_turn_seq": 3}])
    stop_run(capsys, state, text, 0.86)
    assert state.get("evasion_flag"), "交接檔是更早的回合寫的 → 不算這回合落地"


# ─── PostToolUse：刪 (c)、(d) 見收割報告 ─────────────────────────────────────

def _emit(monkeypatch, tmp_path, tool_input, **extra):
    state = {"turn_seq": 7, **extra}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "_hud_alive", lambda *a, **k: (True, {}))
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    monkeypatch.setattr(pt, "_spawn_hud_edge", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"session_id": _SID, "tool_name": "mcp__workflow-guardian__anti_evasion_report",
                                 "tool_input": tool_input, "tool_response": {}},
                                {"docdrift": {"enabled": False}, "aec": {}})
    return state["anti_evasion_report"]


_BASE = {k: "無" for k in "abdefgi"} | {"h": "可關閉", "j_evidence_path": "無", "k_followups": "無"}


def test_report_has_no_c_field_and_schema_dropped_it(monkeypatch, tmp_path):
    rep = _emit(monkeypatch, tmp_path, {**_BASE, "c": "舊客戶端還會送"})
    assert "c" not in rep
    src = (_LIB / "mcp.js").read_text(encoding="utf-8")
    block = src[src.index('name: "anti_evasion_report"'):src.index('name: "anti_evasion_report"') + 6000]
    assert '"c"' not in block[block.index("required"):block.index("]", block.index("required"))]
    assert "\n        c: {" not in block


def test_d_see_harvest_needs_a_validated_harvest_this_turn(monkeypatch, tmp_path):
    rep = _emit(monkeypatch, tmp_path, {**_BASE, "d": "見收割報告"})
    assert any("見收割報告" in x for x in rep.get("d_pending", [])), rep
    monkeypatch.setattr(pt, "validated_this_turn", lambda *a, **k: True)
    rep = _emit(monkeypatch, tmp_path, {**_BASE, "d": "見收割報告"})
    assert "d_pending" not in rep


# ─── 報告不進聊天：Stop 的 HUD 備援、MCP 回條 ─────────────────────────────────

def test_stop_hud_unreachable_prints_one_line_and_does_not_block(stop_run, capsys, monkeypatch):
    monkeypatch.setattr(st, "_hud_alive", lambda *a, **k: (False, {"reason": "URLError: refused"}))
    state = _landed_state(aec_hud_fallback=True,
                          anti_evasion_report={"session_id": _SID, "turn_seq": 9, "severity": "notable",
                                               "a": "- x.py:1 — 修了 y", "b": "無", "k_followups": "無"})
    with pytest.raises(SystemExit):
        monkeypatch.setattr(st, "get_last_assistant_text", lambda *a, **k: "好了。")
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        st.handle_stop({"session_id": _SID, "cwd": ""}, {})
    out = capsys.readouterr()
    assert '"decision": "block"' not in out.out and "修了 y" not in out.out + out.err
    lines = [x for x in out.err.splitlines() if "[Guardian:AEC]" in x]
    assert len(lines) == 1 and "aec-report" in lines[0] and "URLError" in lines[0]
    assert state["aec_hud_fallback"] is False and state["stop_blocked_count"] == 0


_CHIP = r"""
const ae = require(process.argv[1]);
const out = {
  routine: ae.aecChipText({a: "無", b: "無"}),
  notable: ae.aecChipText({a: "- x.py:1 — 修了 y\n- z.py:2 — 修了 w", b: "無", d: "- X → 尚未寫"}),
  real: ae.aecChipText({a: "無", b: "偷懶了"}),
  hasPending: typeof ae.aecPendingItems,
};
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_mcp_chip_is_one_line_and_js_pending_rule_is_gone():
    r = subprocess.run(["node", "-e", _CHIP, str(_LIB / "anti-evasion.js")], capture_output=True, text=True, encoding="utf-8")
    got = json.loads(r.stdout.strip().splitlines()[-1])
    for k in ("routine", "notable", "real"):
        assert "\n" not in got[k] and "HUD" in got[k], got[k]
    assert "修了 y" not in got["notable"] and "待核對" in got["real"]
    assert got["hasPending"] == "undefined", "推後判定只留 Python 一份"


# ─── HUD 卡片：白話三段 ───────────────────────────────────────────────────────

_CARD = r"""
const h = require(process.argv[1]);
const s = h.render().match(/<script>([\s\S]*?)<\/script>/)[1];
const el = () => ({ addEventListener() {}, style: {}, innerHTML: "", textContent: "", className: "", querySelectorAll: () => [] });
const document = { getElementById: el, querySelectorAll: () => [] };
const window = { confirm: () => true };
const fetch = () => new Promise(() => {});
const setInterval = () => 0;
function Worker() { throw new Error("no worker"); }
function EventSource() {}
const URL = { createObjectURL: () => "" };
function Blob() {}
const location = { origin: "http://x" };
eval(s);
const cases = JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map((r) => cardHtml(r))));
"""

_REPORTS = [
    {"session_id": "s1", "turn_seq": 3, "at": "2026-10-16T10:00:00+08:00", "severity": "routine",
     "a": "無", "b": "無", "d": "無", "e": "無", "f": "無", "g": "無", "h": "可關閉", "i": "無", "j": "無", "k": "無"},
    {"session_id": "s1", "turn_seq": 4, "at": "2026-10-16T11:00:00+08:00", "severity": "notable",
     "a": "- x.py:1 — 修了 y", "b": "無", "d": "- 坑 → 已寫入 atom Z", "e": "預設選了方案 B", "f": "無",
     "g": "abc123 已推", "h": "下一動＝重開 HUD 視窗看新分頁", "i": "無",
     "j_evidence_path": "無", "k_followups": "[HUD] 追 X"},   # 報告檔實際存的欄位名（曾經 HUD 只讀 j／k，從沒顯示過）
    {"session_id": "s1", "turn_seq": 5, "at": "2026-10-16T12:00:00+08:00", "severity": "real-evasion",
     "severity_upgraded_by": "hook:evasion-crosscheck", "b_model": "無", "b": "hook 找到 1 處像在推託的說法：『之後再處理』",
     "a": "無", "d": "無", "e": "無", "f": "無", "g": "無", "h": "可關閉", "i": "無", "j": "無", "k": "無"},
    {"session_id": "s0", "turn_seq": 1, "at": "2026-08-01T10:00:00+08:00", "severity": "routine",
     "a": "無", "b": "無", "c": "無", "d": "scratch/a.log"},
]


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_hud_card_plain_sections():
    r = subprocess.run(["node", "-e", _CARD, str(_LIB / "aec-hud-html.js"), json.dumps(_REPORTS, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    routine, todo, real, old = json.loads(r.stdout.strip().splitlines()[-1])
    assert "可以關了" in routine and "沒有要你處理的事" in routine
    assert "有事要你決定" in todo and "重開 HUD 視窗看新分頁" in todo and "預設選了方案 B" in todo
    assert todo.index("要你處理") < todo.index("這輪做了什麼") < todo.index("記住了") < todo.index("細節")
    assert "修了 y" in todo and "已寫入 atom Z" in todo and "追 X" in todo
    assert "疑似偷懶（待核對）" in real and "之後再處理" in real
    for html in (routine, todo, real):
        head = html[:html.index("<details")]
        assert "(a)" not in head and "real-evasion" not in head and "routine" not in head.replace('class="', ""), head
    assert "細節" in old


_NO_REDRAW = r"""
const h = require(process.argv[1]);
const s = h.render().match(/<script>([\s\S]*?)<\/script>/)[1];
let sets = 0, lastDet = null;
function makeDet() { const d = { open: false, _l: null, addEventListener(ev, fn) { this._l = fn; } }; lastDet = d; return d; }
const slot = { _h: "", set innerHTML(v) { sets++; this._h = v; }, get innerHTML() { return this._h; },
               querySelector: () => makeDet(), querySelectorAll: () => [], addEventListener() {}, style: {} };
const generic = () => ({ addEventListener() {}, style: {}, innerHTML: "", textContent: "", className: "",
                         querySelectorAll: () => [], querySelector: () => null });
const document = { getElementById: (id) => (id === "card-slot" ? slot : generic()), querySelectorAll: () => [] };
const window = { confirm: () => true };
const fetch = () => new Promise(() => {});
const setInterval = () => 0;
function Worker() { throw new Error("no worker"); }
function EventSource() {}
const URL = { createObjectURL: () => "" };
function Blob() {}
const location = { origin: "http://x" };
eval(s);
const [r1, r2] = JSON.parse(process.argv[2]);
renderCard(r1); renderCard(r1); renderCard(r1);
const afterSame = sets;
lastDet.open = true; lastDet._l({ currentTarget: lastDet });   // 使用者點開「細節」
renderCard(r2);
console.log(JSON.stringify({ afterSame, total: sets, openAfterNew: lastDet.open }));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_hud_card_does_not_redraw_unchanged_and_keeps_detail_open():
    """使用者回報：HUD 一直刷新、點開的「細節」一直被關掉。每 1.5 秒輪詢同一份報告不重畫；換了報告重畫時「細節」照使用者上次的開合。"""
    r = subprocess.run(["node", "-e", _NO_REDRAW, str(_LIB / "aec-hud-html.js"), json.dumps(_REPORTS[:2], ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout.strip().splitlines()[-1])
    assert got == {"afterSame": 1, "total": 2, "openAfterNew": True}, got
