"""verify_aec_report_classes.py — 收尾檢核報告的三類：本 session 目標／大原則方向／AI 自己做主。

契約：
  - MCP 端（anti-evasion.js aecArgErrors）：三類每次都要交、守門開關都一樣。goal 至少一項、每項要 said／done／verified／not_done；
    principles、ai_decided 可給 []，有項就要填齊；ai_decided 的 kind 只能是那四種。回條一行帶件數。
  - schema（mcp.js）：三類列必填，kind 的 enum 跟拒收檢查、HUD 標籤同一份（AI_DECIDED_KINDS）。
  - Python PostToolUse：三類照收進報告檔（只留 dict 項與認得的鍵、值轉字串），不影響 severity；沒給就不寫。
  - HUD 卡片：三類分開畫、第一類每件掛原話；技術細節（tech、a、g、j）只在摺疊區；份量行比字數，
    目標那類比自己做主那類少 → 燈號與「要你處理」都點出來（退避型報告一眼看得出），正常型不點；舊格式報告照舊欄位放、不壞。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_aec_report_classes.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

LIB = HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "lib"
node = pytest.mark.skipif(not shutil.which("node"), reason="node not available")


def _node(script: str, *args: str):
    r = subprocess.run(["node", "-e", script, str(LIB), *args], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


_GOOD_GOAL = {"said": "HUD 要分三類", "done": "分成三類畫", "verified": "4 份報告畫過", "not_done": "無"}

# ─── MCP 端拒收檢查與回條 ─────────────────────────────────────────────────────

_ARGS = r"""
const p = require("path"), lib = process.argv[1];
const ae = require(p.join(lib, "anti-evasion.js"));
const m = require(p.join(lib, "mcp.js"));
const g = JSON.parse(process.argv[2]);
const t = m.TOOL_DEFINITIONS.find((x) => x.name === "anti_evasion_report");
const base = { goal: [g], principles: [], ai_decided: [], g: "無" };
const w = (o) => Object.assign({}, base, o);
console.log(JSON.stringify({
  ok: ae.aecArgErrors(base, true),
  okGuardOff: ae.aecArgErrors(base, false),
  none: ae.aecArgErrors({}, true),
  noG: ae.aecArgErrors({ goal: [g], principles: [], ai_decided: [] }, true),
  emptyGoal: ae.aecArgErrors(w({ goal: [] }), true),
  noSaid: ae.aecArgErrors(w({ goal: [Object.assign({}, g, { said: " " })] }), true),
  badKind: ae.aecArgErrors(w({ ai_decided: [{ kind: "whatever", what: "x", why: "y" }] }), true),
  halfPrinciple: ae.aecArgErrors(w({ principles: [{ principle: "p" }] }), true),
  chip: ae.aecChipText(w({ a: "無", b: "無", goal: [g, Object.assign({}, g, { not_done: "第二段沒做：等你拍板" })],
                           ai_decided: [{ kind: "tradeoff", what: "x", why: "y" }] })),
  chipOld: ae.aecChipText({ a: "無", b: "無" }),
  req: t.inputSchema.required,
  kindEnum: t.inputSchema.properties.ai_decided.items.properties.kind.enum,
  kinds: Object.keys(ae.AI_DECIDED_KINDS),
}));
process.exit(0);
"""


@node
def test_mcp_side_requires_three_classes_and_chip_counts():
    got = _node(_ARGS, json.dumps(_GOOD_GOAL, ensure_ascii=False))
    assert got["ok"] == [] and got["okGuardOff"] == []
    assert len(got["none"]) == 4 and got["noG"][0].startswith("g 必填") and all(n in " ".join(got["none"]) for n in ("goal", "principles", "ai_decided"))
    assert got["emptyGoal"] and "goal" in got["emptyGoal"][0]
    assert got["noSaid"] == ["goal 第 1 項缺 said"]
    assert any("kind 只能是" in e for e in got["badKind"])
    assert got["halfPrinciple"] == ["principles 第 1 項缺 choice"]
    assert "\n" not in got["chip"] and "你要的事 2 件（1 件沒做完）" in got["chip"] and "AI 自己做主 1" in got["chip"]
    assert "你要的事" not in got["chipOld"] and "HUD" in got["chipOld"]
    assert {"goal", "principles", "ai_decided"} <= set(got["req"])
    assert got["kindEnum"] == got["kinds"] == ["tradeoff", "out_of_scope", "assumption", "side_effect"]


# ─── Python PostToolUse 照收 ──────────────────────────────────────────────────

def test_ptu_stores_classes_without_touching_severity(monkeypatch, tmp_path):
    import verify_aec_emission_gate as vae
    base = {"a": "無", "b": "無", "d": "無", "h": "可關閉", "i": "無", "j_evidence_path": "無", "k_followups": "無"}
    tool_input = {**base,
                  "goal": [{**_GOOD_GOAL, "tech": "x.py:3", "extra": "丟掉"}, "不是物件"],
                  "principles": [{"principle": "HUD 彈窗必留", "choice": 1}],
                  "ai_decided": []}
    aec = vae._drive_ptu(monkeypatch, tmp_path, tool_input)["anti_evasion_report"]
    assert aec["goal"] == [{**_GOOD_GOAL, "tech": "x.py:3", "said_check": "判不了"}]   # 沒給 transcript：核對標判不了（verify_aec_said_check）
    assert aec["principles"] == [{"principle": "HUD 彈窗必留", "choice": "1"}] and aec["ai_decided"] == []
    assert aec["severity"] == "routine"
    on_disk = json.loads((tmp_path / "aec-report" / f"{aec['session_id']}-t7.json").read_text(encoding="utf-8"))
    assert on_disk["goal"] == aec["goal"]
    old = vae._drive_ptu(monkeypatch, tmp_path, {**base, "e": "選了 B", "f": "無", "g": "無"})["anti_evasion_report"]
    assert not {"goal", "principles", "ai_decided"} & set(old) and old["e"] == "選了 B"


# ─── HUD 卡片 ─────────────────────────────────────────────────────────────────

_CARD = r"""
const h = require(require("path").join(process.argv[1], "aec-hud-html.js"));
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
console.log(JSON.stringify(JSON.parse(process.argv[2]).map((r) => cardHtml(r))));
"""

_SYS = {"session_id": "s1", "at": "2026-11-02T10:00:00+08:00", "severity": "notable", "b": "無", "d": "- 坑 → 已寫入 atom Z",
        "e": "", "f": "", "h": "可關閉", "i": "無", "j_evidence_path": "無", "k_followups": "無"}
_NORMAL = {**_SYS, "turn_seq": 1, "report": "子代理改 HUD；這則給你看，你不需動作。",
           "a": "- lib/aec-hud-html.js:300 — 三類卡片", "g": "commit abc1234",
           "goal": [{"said": "沒有基礎分類", "done": "報告分三類分開交、分開畫，每件掛你的原話，技術細節收進摺疊。",
                     "verified": "4 份報告實際畫過，9 個案例全過", "not_done": "無", "tech": "lib/anti-evasion.js:80 REPORT_CLASSES"},
                    {"said": "越寫越偏技術臭", "done": "正文只寫白話，檔名行號只在摺疊區和附錄。",
                     "verified": "測過了", "not_done": "原話是否逐字出自你還沒比對：系統只留最近 5 則"}],
           "principles": [{"principle": "報告不准貼進聊天", "choice": "聊天回條只多件數"}],
           "ai_decided": [{"kind": "tradeoff", "what": "舊兩欄併進第三類", "why": "免得兩邊寫"}]}
_EVASIVE = {**_SYS, "turn_seq": 2, "a": "- dashboard-html.js:40 — 配色", "g": "無",
            "goal": [{"said": "HUD 要白話、要分類", "done": "已調整。", "verified": "測過了", "not_done": "無"}],
            "principles": [],
            "ai_decided": [{"kind": "out_of_scope", "what": "順手把儀表板首頁配色、字級、列距、按鈕圓角都改成跟 HUD 一致",
                            "why": "整套介面看起來比較統一，切換時不會像兩個系統"},
                           {"kind": "out_of_scope", "what": "整理三十幾處註解、改了幾個變數名", "why": "讀起來比較整齊、好維護"},
                           {"kind": "side_effect", "what": "重開了正在跑的 MCP 服務", "why": "才看得到效果"}]}
_LEGACY = {"session_id": "s0", "turn_seq": 3, "at": "2026-10-29T11:15:47+08:00", "severity": "real-evasion",
           "a": "- _AIDocs/_CHANGELOG.md — 還原疊檔", "b": "誤刪 26 個已追蹤的驗收文件，已從版控救回",
           "d": "- 疊檔成因 → 已寫入 atom X", "e": "CHANGELOG 新條目沿用慣例", "f": "刪了本機 92 張截圖",
           "g": "尚未 commit", "h": "下一動=使用者看 diff 後下「上GIT」", "i": "無"}
_OLDEST = {"session_id": "s0", "turn_seq": 1, "at": "2026-08-01T10:00:00+08:00", "severity": "routine",
           "a": "無", "b": "無", "c": "無", "d": "scratch/a.log"}


def _cards(*reports):
    return _node(_CARD, json.dumps(list(reports), ensure_ascii=False))


def _main(html: str) -> str:
    """卡片拿掉所有摺疊區（tech 細節與附錄）後剩下的正文。"""
    return re.sub(r"<details[\s\S]*?</details>", "", html)


@node
def test_hud_new_report_three_classes_plain_body():
    normal, = _cards(_NORMAL)
    order = ["要你處理", "子代理改 HUD", "份量", "① 你這次要的事", "② 碰到你的長期原則、方向", "③ AI 自己做主的", "附錄：技術細節"]
    assert [normal.index(x) for x in order] == sorted(normal.index(x) for x in order)
    assert "你說：「沒有基礎分類」" in normal and "你說：「越寫越偏技術臭」" in normal
    assert '<span class="tag">取捨</span>' in normal and "tradeoff" not in _main(normal)
    body = _main(normal)
    for tech in ("REPORT_CLASSES", "aec-hud-html.js:300", "abc1234"):
        assert tech in normal and tech not in body, tech   # 技術細節只在摺疊區
    assert "(a)" not in body and "(k)" not in body
    assert "（沒附數字或收據）" in body and body.count("（沒附數字或收據）") == 1   # 「測過了」那件
    assert "你要的事有 1 件沒做完" in body and "AI 自己做主了 1 件" in body
    assert "寫得比 AI 自己做主的少" not in body and "你要的事寫得少" not in body


@node
def test_hud_evasive_report_is_visible_at_a_glance():
    """退避型：目標那類一句帶過、自己做主那類一大串 → 燈號、要你處理第一條、份量行都點出來。"""
    evasive, normal = _cards(_EVASIVE, _NORMAL)
    head = evasive[:evasive.index("要你處理")]
    assert "你要的事寫得少，看一下" in head
    todo = evasive[evasive.index("要你處理"):evasive.index("份量")]
    assert todo.index("你要的事寫得比 AI 自己做主的少") < todo.index("AI 自己做主了 3 件")
    assert "weigh warn" in evasive and "⚠ 你要的事寫得比較少" in evasive
    assert "你要的事寫得少" not in normal[:normal.index("要你處理")]


@node
def test_hud_legacy_reports_still_render():
    legacy, oldest = _cards(_LEGACY, _OLDEST)
    assert "舊格式報告" in legacy and "疑似偷懶（待核對）" in legacy and "誤刪 26 個" in legacy
    ones = legacy[legacy.index("① 你這次要的事"):legacy.index("② 碰到你的長期原則、方向")]
    threes = legacy[legacy.index("③ AI 自己做主的"):legacy.index("附錄")]
    assert "還原疊檔" in ones and "CHANGELOG 新條目沿用慣例" in threes and "刪了本機 92 張截圖" in threes
    assert "使用者看 diff 後下「上GIT」" in legacy and "份量" not in legacy
    assert "已寫入 atom X" in legacy[legacy.index("附錄"):]
    assert "衍生暫存清單（舊格式" in oldest and "記住了（寫進記憶卡的）" not in oldest


@node
def test_hud_escapes_ai_text():
    bad = {**_NORMAL, "goal": [{**_GOOD_GOAL, "said": "<img src=x onerror=alert(1)>"}],
           "ai_decided": [{"kind": "<u>", "what": "<script>x</script>", "why": "y"}]}
    html, = _cards(bad)
    assert "<img" not in html and "<script>" not in html and "<u>" not in html and "&lt;u&gt;" in html


@pytest.mark.parametrize("guard", ["0", "1"])
def test_ptu_rejected_report_not_counted_either_mode(monkeypatch, tmp_path, guard):
    """MCP 退回的那次（缺類、g 沒填）不是報告：守門開、關都不收進 state、不落檔，Stop 才不會當成已交。"""
    import verify_aec_emission_gate as vae
    monkeypatch.setenv("WG_CODING_GUARD", guard)
    pt = vae.pt
    state = {"turn_seq": 7}
    monkeypatch.setattr(pt, "_ensure_state", lambda *a, **k: state)
    monkeypatch.setattr(pt, "write_state", lambda *a, **k: None)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(pt, "append_guard_log", lambda *a, **k: None)
    inp = {"session_id": "s-rej", "tool_name": "mcp__workflow-guardian__anti_evasion_report",
           "tool_input": {"a": "無", "b": "無", "d": "無", "h": "可關閉", "i": "無"},
           "tool_response": {"isError": True, "content": [{"type": "text", "text": "anti_evasion_report 拒收：缺 goal"}]}}
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use(inp, {"docdrift": {"enabled": False}, "aec": {}})
    assert "anti_evasion_report" not in state
    assert not (tmp_path / "aec-report").exists()
