"""verify_pick_one.py：寫碼交付時順手點出最該修的一件（v6 G4／G5／G13）。

做什麼：本 session 改了程式、到交付邊界 → Stop 用 additionalContext 送一次「哪一件最該修、為什麼、為什麼不是數字最高的那個」
（只提醒、不擋；同一批改動只問一次）；AI 回覆裡的「順手看到最該修」段記成追蹤項（另存建議怎麼解、該誰解）；
下個 session 開場先列附了建議的未結項；(k) 行尾的「｜建議：…｜該誰解：…」也進同兩欄。
正例：交付邊界＋新改的程式 → 送一次（不是 block）；回覆裡的那段 → 帳本一筆 open 附四欄、同段不重記；開場列建議與該誰解（有部位的也列）；
      材料依部位分組、壞味道分數與行數標「只當參考」。
反例：同一批改動第二次不送；沒到交付邊界、只改文件、設定沒開、AI 自己先寫了那段 → 不送；句中提到、code block 裡、照抄範本、
      只有標頭 → 不記；「無，因為…」不進帳本；(k) 的「問題｜建議：…」不把問題當部位。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_pick_one.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_harvest as wh  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import stop as st  # noqa: E402

_SID = "sid-pick"
MAP = ("| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 病灶清單 | 量尺 | 檢查器 | 讀路徑 | 第四問 | 層 | 權威 | 上游 | 下游 | 類別 |\n"
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
       "| `Game/Battle/` | 戰鬥 | `戰鬥知識導讀` | 有 | 無 | 無 | 無 | 無 | 無 | 單層 | 無 | 無 | 傷害結算、存檔 | code |\n"
       "| `Game/UI/` | 介面 | 無 | 無 | 無 | 無 | 無 | 無 | 無 | 單層 | 無 | 無 | 玩家畫面 | code |\n"
       "| `docs/` | 文件 | 無 | 無 | 無 | 無 | 無 | 無 | 無 | 單層 | 無 | 無 | 無 | knowledge |\n")
CARD = "# 戰鬥導讀\n\n## 已知病灶\n- 傷害公式的共用字典被三處各自改\n- 技能冷卻表讀錯欄位\n- 第三條不會列\n"
PICK = """改好了，全部完成。

**順手看到最該修**：[戰鬥] Game/Battle/Damage.cs 的暴擊分支把共用字典當暫存
- 為什麼是它：傷害結算與存檔都讀這份字典，改一處另兩處跟著錯，已經修過兩次
- 為什麼不是數字最高的那個：Skill.cs 2000 行最長，但結構清楚、沒人改它出事
- 建議怎麼解：暴擊分支改用區域變數，字典只讀
- 該誰解：下一個寫碼 session
"""


@pytest.fixture
def world(tmp_path, monkeypatch):
    """tmp 專案（部位表＋戰鬥卡＋壞味道報告）＋ tmp 的 workflow（帳本落這裡，不碰 live）。"""
    proj = tmp_path / "proj"
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(MAP, encoding="utf-8", newline="\n")
    (proj / ".claude" / "overview-hub.json").write_text(json.dumps({"smells_report": "smells.json"}), encoding="utf-8")
    (proj / ".claude" / "memory" / "shared" / "戰鬥知識導讀.md").write_text(CARD, encoding="utf-8")
    (proj / "smells.json").write_text(json.dumps({"rows": [
        {"path": "Game/Battle/Skill.cs", "category": "長函式", "reason": "2000 行", "score": 95, "part": "戰鬥"},
        {"path": "Game/Battle/Damage.cs", "category": "共用可變狀態", "reason": "字典", "score": 12, "part": "戰鬥"},
        {"path": "Game/UI/Btn.cs", "category": "長函式", "reason": "x", "score": 99, "part": "介面"}]}), encoding="utf-8")
    for d in ("Game/Battle", "Game/UI", "docs"):
        (proj / d).mkdir(parents=True)
    (proj / "Game" / "Battle" / "Damage.cs").write_text("a\nb\nc\n", encoding="utf-8")
    (proj / "Game" / "Battle" / "Skill.cs").write_text("x\n" * 9, encoding="utf-8")
    (proj / "Game" / "UI" / "Btn.cs").write_text("y\n", encoding="utf-8")
    wf = tmp_path / "workflow"
    monkeypatch.setattr(wh, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    return proj, wf


def _rows(proj):
    return wh.read_tracking(wh.tracking_slug(str(proj)))


# ─── (k) 行尾的提議欄 ─────────────────────────────────────────────────────────

def test_k_line_proposal_and_owner_split_before_part():
    rows = wh.tracking_entries("s", 1, "gitlab 鏡像 push 憑證失效｜建議：換 token 後重推｜該誰解：使用者\n"
                                       "[hooks] 寫入失敗待查｜該誰解：根層｜建議：加重試\n"
                                       "hooks｜舊格式部位行\n[hooks] 結案：寫入失敗待查", at="2026-10-20T00:00:00")
    assert (rows[0]["part"], rows[0]["text"]) == ("", "gitlab 鏡像 push 憑證失效")   # 反例：舊碼把問題當成部位、本文剩「建議：…」
    assert (rows[0]["proposal"], rows[0]["owner"]) == ("換 token 後重推", "使用者")
    assert (rows[1]["part"], rows[1]["text"], rows[1]["proposal"], rows[1]["owner"]) == ("hooks", "寫入失敗待查", "加重試", "根層")
    assert (rows[2]["part"], rows[2]["text"]) == ("hooks", "舊格式部位行") and "proposal" not in rows[2]   # 沒寫提議照舊
    assert rows[3]["status"] == "closed" and "proposal" not in rows[3]


# ─── 解析回覆裡的那一段 ───────────────────────────────────────────────────────

def test_parse_pick_reads_all_fields_and_last_block_wins():
    p = wh.parse_pick("順手看到最該修：[介面] 舊的那件\n為什麼是它：舊理由\n\n" + PICK)
    assert p == {"none": False, "part": "戰鬥", "text": "Game/Battle/Damage.cs 的暴擊分支把共用字典當暫存",
                 "why": "傷害結算與存檔都讀這份字典，改一處另兩處跟著錯，已經修過兩次",
                 "not_top": "Skill.cs 2000 行最長，但結構清楚、沒人改它出事",
                 "proposal": "暴擊分支改用區域變數，字典只讀", "owner": "下一個寫碼 session"}
    none = wh.parse_pick("全部完成。\n順手看到最該修：無，因為這次只改了一行設定")
    assert none["none"] is True and none["text"].startswith("無")


@pytest.mark.parametrize("text", [
    "交付末尾會多一段「順手看到最該修：X，因為…」這樣。",                                  # 句中順帶提到
    "```\n順手看到最該修：[戰鬥] 範例\n為什麼是它：範例\n```",                               # code block 裡
    "格式範例如下：\n> 順手看到最該修：[戰鬥] Damage.cs 共用字典被覆寫\n> 為什麼是它：會影響存檔\n> 建議怎麼解：改區域變數",   # 引言裡（Codex BLOCK 1）
    "順手看到最該修：[部位] <哪一件、在哪個檔哪一段>\n為什麼是它：<它影響誰>",                # 照抄範本
    "順手看到最該修：[戰鬥] 只有標頭沒有理由",                                              # 只有標頭
    "全部完成。",
])
def test_parse_pick_counter_cases(text):
    assert wh.parse_pick(text) is None


# ─── 記進帳本 ────────────────────────────────────────────────────────────────

def test_record_pick_writes_one_open_item_with_proposal_and_owner(world):
    proj, _ = world
    state: dict = {}
    ev, p = wh.record_pick(state, _SID, 5, PICK, str(proj), at="2026-10-20T01:00:00")
    assert ev == "recorded" and p["part"] == "戰鬥"
    rows = _rows(proj)
    assert len(rows) == 1
    r = rows[0]
    assert (r["status"], r["source"], r["part"]) == ("open", "pick", "戰鬥")
    assert r["proposal"] == "暴擊分支改用區域變數，字典只讀" and r["owner"] == "下一個寫碼 session"
    assert r["why"].startswith("傷害結算") and r["not_top"].startswith("Skill.cs")
    assert state["pick_one"][_SID]["covered_turn"] == 5
    ev2, _ = wh.record_pick({}, "other-sid", 9, PICK, str(proj))                         # 下一批、甚至別的 session 又點出同一件
    assert ev2 == "repeat" and len(_rows(proj)) == 1                                     # 帳上已有未結的同一件 → 不重記
    wh.append_tracking(wh.tracking_slug(str(proj)), wh.tracking_entries("s2", 7, "[戰鬥] 結案：Game/Battle/Damage.cs 的暴擊"))
    assert wh.open_tracking_items(_rows(proj)) == []                                     # 照一般追蹤項結案
    assert wh.record_pick({}, _SID, 10, PICK, str(proj))[0] == "recorded"                # 結案後又出現 → 重新記


def test_record_pick_none_and_repeats_still_count_as_answered_for_new_batch(world):
    """Codex BLOCK 3：下一批改動又答出同一句（「無」或同一件）也要算這批答過，不能因為去重而再被問。"""
    proj, _ = world
    state: dict = {}
    assert wh.record_pick(state, _SID, 5, "順手看到最該修：無，因為只改了一行", str(proj))[0] == "none"
    assert _rows(proj) == [] and state["pick_one"][_SID]["covered_turn"] == 5
    assert wh.record_pick(state, _SID, 6, "順手看到最該修：無，因為只改了一行", str(proj))[0] == "none"
    assert not wh.pick_due(state, _SID, [{"path": "a.py", "last_turn_seq": 6}], boundary=True)
    wh.record_pick(state, _SID, 7, PICK, str(proj))
    assert wh.record_pick(state, _SID, 8, PICK, str(proj))[0] == "repeat"
    assert not wh.pick_due(state, _SID, [{"path": "a.py", "last_turn_seq": 8}], boundary=True)


def test_record_pick_write_failure_is_not_answered_and_retries(world, monkeypatch):
    """Codex BLOCK 2：帳本寫不進去 → 不算答過（下次照問）、同一段下次照記。"""
    proj, _ = world
    state: dict = {}
    real, broken = wh.append_tracking, [True]
    monkeypatch.setattr(wh, "append_tracking", lambda *a, **k: None if broken[0] else real(*a, **k))
    assert wh.record_pick(state, _SID, 5, PICK, str(proj))[0] == "write_failed"
    assert "covered_turn" not in state.get("pick_one", {}).get(_SID, {})
    assert wh.pick_due(state, _SID, [{"path": "a.py", "last_turn_seq": 5}], boundary=True)
    broken[0] = False                                                                    # 帳本恢復可寫
    assert wh.record_pick(state, _SID, 5, PICK, str(proj))[0] == "recorded" and len(_rows(proj)) == 1


# ─── 該不該問 ────────────────────────────────────────────────────────────────

def test_pick_due_only_for_new_code_changes_at_boundary():
    state: dict = {}
    mods = [{"path": "a.py", "last_turn_seq": 5}]
    assert wh.pick_due(state, _SID, mods, boundary=True)
    assert not wh.pick_due(state, _SID, mods, boundary=False)                           # 沒到交付邊界
    assert not wh.pick_due(state, _SID, [], boundary=True)                              # 沒改程式
    wh.mark_pick_asked(state, _SID, 5)
    assert not wh.pick_due(state, _SID, mods, boundary=True)                            # 同一批只問一次
    mods.append({"path": "b.py", "last_turn_seq": 6})
    assert wh.pick_due(state, _SID, mods, boundary=True)                                # 下一批又改了 → 再問
    state["pick_one"][_SID]["covered_turn"] = 6
    assert not wh.pick_due(state, _SID, mods, boundary=True)                            # AI 自己先寫了那段
    assert not wh.pick_due({}, _SID, [{"path": "c.py"}], boundary=True)                 # 沒有回合號的不算新改動


# ─── 材料：依部位分組、數字標參考 ─────────────────────────────────────────────

def test_material_groups_by_part_with_numbers_marked_reference(world):
    proj, _ = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, wh.tracking_entries("s", 1, "[戰鬥] 舊的未結項\n[戰鬥] 最新的未結項"))
    paths = [str(proj / "Game" / "Battle" / "Damage.cs"), str(proj / "Game" / "UI" / "Btn.cs"),
             str(proj / "Game" / "Battle" / "Skill.cs"), str(proj / "tools" / "x.py")]
    lines = wh.pick_material(paths, {})
    assert lines[0].startswith("- 【戰鬥】") and lines[1].startswith("- 【介面】")       # 照改檔先後、不按分數排
    battle = lines[0]
    assert "影響到：傷害結算、存檔" in battle
    assert "傷害公式的共用字典被三處各自改" in battle and "第三條不會列" not in battle
    assert "分數只當參考" in battle and battle.index("Skill.cs｜長函式｜分數 95") < battle.index("Damage.cs｜共用可變狀態｜分數 12")
    assert "Btn.cs" not in battle                                                        # 別部位的壞味道不混進來
    assert "行數只當參考" in battle and "Damage.cs 4 行" in battle and "Skill.cs 10 行" in battle
    assert "未結追蹤項 2 筆，最新一筆：最新的未結項" in battle
    assert lines[-1] == "- 部位表查不到的檔：x.py"
    prompt = wh.pick_prompt(lines)
    assert "只提醒、不擋" in prompt and "為什麼不是數字最高的那個：" in prompt and "該誰解：" in prompt


# ─── Stop 真流程：送一次、不是 block；記帳 ─────────────────────────────────────

_PASS_CFG = {"reconcile_gate": {"enabled": False}, "verify_scope": {"enabled": False}, "sync_reminder": {"enabled": False},
             "atom_audit": {"enabled": False}, "aec": {"scan_report_gate": False}, "pick_one": {"enabled": True}}


@pytest.fixture
def stop_run(world, monkeypatch, capsys):
    """驅動 handle_stop：其他閘都關或換掉，只看這一段。回 run(last_message, mods, config, state) → (stdout, state, guard 事件)。"""
    proj, _ = world
    logs: list = []
    for name, fn in (("_find_session_transcript", lambda *a, **k: None), ("token_warn_payload", lambda *a, **k: ""),
                     ("detect_evasion", lambda *a, **k: None), ("write_state", lambda *a, **k: None),
                     ("_attribute_usefulness", lambda *a, **k: None), ("_detect_uncommitted_files", lambda mf: []),
                     ("_maybe_spawn_user_extract_worker", lambda *a, **k: None), ("_hud_alive", lambda *a, **k: (True, {})),
                     ("_should_deep_postmortem", lambda *a, **k: False), ("reading_path_note", lambda *a, **k: ("", False)),
                     ("append_guard_log", lambda guard, payload: logs.append((guard, payload)))):
        monkeypatch.setattr(st, name, fn)

    def run(message, mods, config=None, **extra):
        state = {"phase": "working", "modified_files": mods, "failing_tests": [], "recent_user_prompts": [],
                 "stop_blocked_count": 0, "turn_seq": 5, "session": {"cwd": str(proj)}, **extra}
        monkeypatch.setattr(st, "_ensure_state", lambda *a, **k: state)
        logs.clear()
        with pytest.raises(SystemExit):
            st.handle_stop({"session_id": _SID, "cwd": str(proj), "last_assistant_message": message},
                           _PASS_CFG if config is None else config)
        cap = capsys.readouterr()
        run.err = cap.err                    # 斷言失敗時印出來看是哪道閘先走了
        return cap.out, state, [p for g, p in logs if g == "pick_one"]
    return proj, run


def _mod(path, turn=5):
    return {"path": str(path), "session_id": _SID, "turn_seq": turn, "last_turn_seq": turn}


def test_stop_sends_pick_once_as_context_not_block(stop_run):
    proj, run = stop_run
    mods = [_mod(proj / "Game" / "Battle" / "Damage.cs")]
    out, state, ev = run("改好了，全部完成。", mods)
    assert out.strip(), run.err
    payload = json.loads(out.strip().splitlines()[-1])
    assert "decision" not in payload                                                     # 不是擋
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert ctx.startswith("[Guardian:PickOne]") and "【戰鬥】" in ctx and "為什麼不是數字最高的那個：" in ctx
    assert state["pick_one"][_SID]["asked_turn"] == 5 and ev[-1]["event"] == "asked"
    out2, _, _ = run("改好了，全部完成。", mods, pick_one=state["pick_one"])                 # 同一批改動第二次
    assert "PickOne" not in out2


@pytest.mark.parametrize("message,mods_kind,config", [
    ("我先看一下這段在做什麼，接著改。", "code", None),                                    # 沒到交付邊界
    ("改好了，全部完成。", "doc", None),                                                  # 只改文件
    ("改好了，全部完成。", "code", {k: v for k, v in _PASS_CFG.items() if k != "pick_one"}),   # 設定沒開
])
def test_stop_does_not_send_pick(stop_run, message, mods_kind, config):
    proj, run = stop_run
    path = proj / ("Game/Battle/Damage.cs" if mods_kind == "code" else "docs/readme.md")
    out, state, _ = run(message, [_mod(path)], config)
    assert "PickOne" not in out and not (state.get("pick_one") or {}).get(_SID, {}).get("asked_turn")


def test_stop_records_pick_from_delivery_and_does_not_ask_again(stop_run):
    proj, run = stop_run
    out, state, ev = run(PICK, [_mod(proj / "Game" / "Battle" / "Damage.cs")])
    assert "PickOne" not in out                                                          # AI 自己先寫了 → 不再問
    rows = _rows(proj)
    assert len(rows) == 1 and rows[0]["source"] == "pick" and rows[0]["proposal"] and rows[0]["owner"]
    assert [e["event"] for e in ev] == ["recorded"]


# ─── 開場列出附了建議的未結項 ─────────────────────────────────────────────────

def test_session_start_lists_proposals_first_including_parted_items(world, monkeypatch):
    proj, wf = world
    from handlers import session_start as ss
    monkeypatch.setattr(ss, "WORKFLOW_DIR", wf)
    slug = wh.tracking_slug(str(proj))
    wh.record_pick({}, _SID, 5, PICK, str(proj), at="2026-10-19T00:00:00")
    wh.append_tracking(slug, wh.tracking_entries("s", 1, "沒部位沒建議的雜項追蹤一則\n"
                                                       "沒部位但有建議的一則｜建議：補一支測試", at="2026-10-20T00:00:00"))
    adv = ss._tracking_advisory(str(proj), {})
    assert len(adv) == 2
    head = adv[0]
    assert "之前交付時點出、還沒解的問題 2 件" in head                                     # 反例：舊碼不列有部位的項目
    assert head.index("沒部位但有建議的一則") < head.index("[戰鬥] Game/Battle/Damage.cs")   # 最新的先列
    assert "建議：暴擊分支改用區域變數，字典只讀｜該誰解：下一個寫碼 session" in head
    assert "第一則回覆開頭用一兩句白話告訴使用者" in head
    assert "本專案未結追蹤項 1 筆" in adv[1] and "沒部位沒建議的雜項追蹤一則" in adv[1]
    assert "沒部位但有建議的一則" not in adv[1]                                           # 不重複列
    assert ss._tracking_advisory(str(proj), {"tracking_advisory_sent": True}) == []


def test_part_injection_block_shows_proposal(world):
    block = wh.tracking_block([{"text": "暴擊分支把共用字典當暫存", "at": "2026-10-20T00:00:00", "part": "戰鬥",
                                "proposal": "改用區域變數", "owner": "下一個寫碼 session"}], 2000)
    assert "- 暴擊分支把共用字典當暫存（2026-10-20）｜建議：改用區域變數｜該誰解：下一個寫碼 session" in block
