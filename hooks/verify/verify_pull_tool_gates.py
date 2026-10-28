"""verify_pull_tool_gates.py：工具前的宣告閘不再「交了看不到就一直擋」——擋次上限、svn 測試路徑閘、判準卡不算雜湊、
commit 前核對出錯不擋。

每條都是會紅案例（改前的碼跑會紅），除了 deny_cap 單元案都走 handlers/pre_tool_use.handle_pre_tool_use 真入口：
- 擋次上限（wg_core.deny_cap）：動資料檔、改舊測試（當場擋與事後欠帳兩條路）、不是繞閘三道宣告閘，同一個使用者回合同一件
  缺宣告擋第 1、2 次，第 3 次放行並留帳 cap_released；換回合重算；擋訊息先講「早一則訊息送出、或指令開頭 `#` 註解」。
- 繞閘閘：病形閘擋 A → 只交 B 又被擋 → 修好 B 再交 → 被排除的 A 仍要宣告（同一個 repo 的點名檔合併、不覆蓋）。
- svn 測試路徑閘：預設關；專案 overview-hub.json 開了之後只看 commit 的路徑參數（-m 訊息不看）、PowerShell 也查、
  使用者本回合原句出口；overview-hub.json 寫 svn_test_block 不是未知鍵。
- 判準卡：跑直譯器不記雜湊快照、事後不比對；改判準卡不擋。
- 閘自己出錯（GATE_SELF_ERROR）：commit 前目標對照核對、動資料檔閘、改舊測試閘拋例外 → 不擋、留帳。
- 耗重：動資料檔閘整次呼叫只讀一次 transcript；改舊測試閘不另讀 state。
- config.local 合併：wg_core.load_config 走 lib/config_local.merge_local，跟它結果相同、不再自己合併。
git 子程序走錄製重播（lib/git_cassette.py）；改了呼叫 git 的方式要 `pytest --git-record` 重錄。
live 檔全 monkeypatch：WORKFLOW_DIR（state 落 tmp）、GUARD_LOG_DIR（留帳落 tmp）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_pull_tool_gates.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
REPO = HOOKS_DIR.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(REPO))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(REPO / "lib"))
sys.path.insert(0, str(HOOKS_DIR / "verify"))

import wg_chain  # noqa: E402
import wg_core  # noqa: E402
import wg_data_file as df  # noqa: E402
import wg_judge_card as jc  # noqa: E402
import wg_oldtest as ot  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402
import verify_gate_bypass as vgb  # noqa: E402  病形閘擋下的真實材料與環境（只取模組，不把它的案例收進來）

SID = "sess-pull-tool-gates-0001"
PROMPT = "幫 calc 加一個減法，設定檔裡的精度照舊"
TEST_SRC = "def test_add():\n    assert 1 + 1 == 2\n"
TEST_EDIT = {"old_string": "assert 1 + 1 == 2", "new_string": "assert 1 + 1 == 3"}
DATA_EDIT = {"old_string": '"precision": 2', "new_string": '"precision": 3'}
CARD = "# 卡\n\n- Scope: global\n- Confidence: [臨]\n- Trigger: 測試\n- Entry: E99\n## 知識\n\n- [臨] 原本的判準\n"
OT_HIT = "✗ (ot) OLD_TEST_CHANGE_NEEDS_DECLARATION"


@pytest.fixture
def world(tmp_path, monkeypatch):
    """假專案 proj（既有的 settings.json、tests/test_calc.py）＋ tmp workflow／Logs；state 檔先建好（第 1 個使用者回合）。"""
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "settings.json").write_text('{"precision": 2}\n', encoding="utf-8")
    (proj / "tests" / "test_calc.py").write_text(TEST_SRC, encoding="utf-8")
    wf = tmp_path / "wf"
    wf.mkdir()
    logs = tmp_path / "Logs"
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", logs)
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    outputs = []

    def _out(d):
        outputs.append(d)
        raise SystemExit(0)

    def _nothing():
        outputs.append(None)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _nothing)
    wg_core.write_state(SID, {"session": {"id": SID, "cwd": str(proj)}, "turn_seq": 1,
                              "recent_user_prompts": [PROMPT], "turn_prompts": [PROMPT]})
    tp = tmp_path / "t.jsonl"
    tp.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": PROMPT}}, ensure_ascii=False) + "\n"
                  + json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "先看看"}]}},
                               ensure_ascii=False) + "\n", encoding="utf-8")
    return {"proj": proj, "tp": str(tp), "outputs": outputs, "logs": logs, "tmp": tmp_path}


def _pre(w, tool, tool_input, tool_use_id="toolu_1"):
    """跑一次 PreToolUse；回擋訊息（沒擋回空字串）。"""
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": tool, "tool_input": tool_input, "session_id": SID, "cwd": str(w["proj"]),
                                 "transcript_path": w["tp"], "tool_use_id": tool_use_id}, {})
    hso = (w["outputs"][-1] or {}).get("hookSpecificOutput") or {}
    return hso.get("permissionDecisionReason", "") if hso.get("permissionDecision") == "deny" else ""


def _events(w, guard):
    p = w["logs"] / f"guard-{guard}.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def _next_user_turn():
    st = wg_core.read_state(SID)
    st["turn_seq"] = int(st.get("turn_seq", 0)) + 1
    wg_core.write_state(SID, st)


# ─── 擋次上限 ─────────────────────────────────────────────────────────────

def test_deny_cap_counts_each_item_per_user_turn():
    st = {"turn_seq": 3}
    assert [wg_core.deny_cap(st, "g", ["a"]) for _ in range(4)] == [(["a"], []), (["a"], []), ([], ["a"]), ([], [])]
    assert wg_core.deny_cap(st, "g", ["b", "c"]) == (["b", "c"], [])
    assert wg_core.deny_cap(st, "g", ["b", "c"]) == (["b", "c"], [])
    assert wg_core.deny_cap(st, "g", ["b", "d"]) == (["d"], [])          # d 照擋整條還是被擋：b 這次不算放行
    assert wg_core.deny_cap(st, "g", ["b"]) == ([], ["b"])
    assert wg_core.deny_cap(st, "other", ["a"]) == (["a"], [])           # 別道閘另算
    st["turn_prompts_seq"] = 4                                           # 使用者開了新回合：重算
    assert wg_core.deny_cap(st, "g", ["a"]) == (["a"], [])
    assert wg_core.deny_cap(None, "g", ["a"]) == (["a"], [])             # 沒有 state 可記：照擋


def _reply(tp, mid, *tids):
    """AI 的一則回覆 mid 整則落進 transcript（含它送出的 tool_use）：之後的呼叫屬下一則（批次鍵＝這則的 message.id）。"""
    blocks = [{"type": "tool_use", "id": t, "name": "Edit", "input": {}} for t in tids] or [{"type": "text", "text": "…"}]
    with open(tp, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"type": "assistant", "message": {"id": mid, "content": blocks}}, ensure_ascii=False) + "\n")


def test_deny_cap_per_reply_counts_one_reply_once(world):
    """規則 DENY_CAP_PER_REPLY：同一則回覆平行送出的呼叫（批次鍵同 CHAIN_SAME_BATCH）只算一次擋次——那一則全照第一次的結果擋、
    不加次數，下一則才加；放行那一則的其他呼叫不重回放行。判不出是哪一則（子代理）照每個呼叫算、留帳 batch_unknown。"""
    tp = Path(world["tp"])
    _reply(tp, "m0")

    def call(tid, **kw):
        return {"tool_use_id": tid, "transcript_path": str(tp), "session_id": SID, **kw}
    st = {"turn_seq": 3}
    assert [wg_core.deny_cap(st, "g", ["a"], call=call(t)) for t in ("t1", "t2", "t3", "t4")] == [(["a"], [])] * 4
    _reply(tp, "m1", "t1", "t2", "t3", "t4")
    assert wg_core.deny_cap(st, "g", ["a"], call=call("t5")) == (["a"], [])                # 第二則：第 2 次
    _reply(tp, "m2", "t5")
    assert wg_core.deny_cap(st, "g", ["a"], call=call("t6")) == ([], ["a"])                # 第三則：放行、回給呼叫端留帳
    assert wg_core.deny_cap(st, "g", ["a"], call=call("t7")) == ([], [])                   # 同一則的下一個呼叫：不重回
    assert not _events(world, "deny_cap")
    sub = {"turn_seq": 3}
    assert [wg_core.deny_cap(sub, "g", ["a"], call=call(f"s{i}", agent_id="ag1")) for i in range(3)] == \
        [(["a"], []), (["a"], []), ([], ["a"])]                                             # 子代理：照每個呼叫算
    assert {(e["event"], e["rule"]) for e in _events(world, "deny_cap")} == {("batch_unknown", "DENY_CAP_PER_REPLY")}
    # 一次缺兩件：a 剛到上限、b 照擋 → 整條擋、a 不算放行也不算「這一則算過」；同一則下一個呼叫只缺 a → a 放行（codex 一輪 BLOCK 1）
    two = {"turn_seq": 3, "decl_deny_counts": {"turn": 3, "counts": {"g|a": 2, "g|b": 0}, "batch": {}}}
    _reply(tp, "m3", "t6", "t7")
    assert wg_core.deny_cap(two, "g", ["a", "b"], call=call("t8")) == (["b"], [])
    assert wg_core.deny_cap(two, "g", ["a"], call=call("t9")) == ([], ["a"])
    assert wg_core.deny_cap(two, "g", ["a", "b"], call=call("t10")) == (["b"], [])      # b 同一則照第一次擋；a 已放行過不重回


def test_data_file_gate_parallel_edits_in_one_reply_count_once(world):
    """規則 DENY_CAP_PER_REPLY（動資料檔）：同一則回覆平行送出 3 個改同一個資料檔的 Edit、都沒宣告 → 3 個都擋（舊碼第 3 個放行）；
    下一則再擋一次（第 2 則），第三則才放行留帳 cap_released。"""
    ti = {"file_path": str(world["proj"] / "settings.json"), **DATA_EDIT}
    tp = Path(world["tp"])
    _reply(tp, "msg_1")
    reasons = [_pre(world, "Edit", ti, f"tu_{i}") for i in range(3)]
    assert all("[Guardian:DataFileAsk]" in r for r in reasons), reasons
    _reply(tp, "msg_2", "tu_0", "tu_1", "tu_2")
    assert "[Guardian:DataFileAsk]" in _pre(world, "Edit", ti, "tu_3")
    _reply(tp, "msg_3", "tu_3")
    assert "[Guardian:DataFileAsk]" not in _pre(world, "Edit", ti, "tu_4")
    assert [e["event"] for e in _events(world, "data_file")] == ["denied"] * 4 + ["cap_released"]


def test_data_file_gate_releases_after_two_denies_in_same_turn(world):
    ti = {"file_path": str(world["proj"] / "settings.json"), **DATA_EDIT}
    reasons = [_pre(world, "Edit", ti) for _ in range(3)]
    assert all("[Guardian:DataFileAsk]" in r for r in reasons[:2]), reasons
    assert "[Guardian:DataFileAsk]" not in reasons[2]
    assert [e["event"] for e in _events(world, "data_file")] == ["denied", "denied", "cap_released"]
    first = reasons[0].splitlines()[0]
    assert "`#` 註解" in first and first.index("`#` 註解") < first.index("早一則")   # 先 # 註解、其次早一則的回覆文字
    _next_user_turn()
    assert "[Guardian:DataFileAsk]" in _pre(world, "Edit", ti)            # 換回合重算


def test_old_test_gate_releases_after_two_denies_in_same_turn(world):
    ti = {"file_path": str(world["proj"] / "tests" / "test_calc.py"), **TEST_EDIT}
    reasons = [_pre(world, "Edit", ti) for _ in range(3)]
    assert all(OT_HIT in r for r in reasons[:2]), reasons
    assert OT_HIT not in reasons[2] and "[Guardian:OldTestDeclare]" not in reasons[2]
    assert [e["event"] for e in _events(world, "old_test") if e["event"] in ("denied", "cap_released")] == \
        ["denied", "denied", "cap_released"]
    tag, hit, hint = reasons[0].split("\n", 2)
    assert hint.startswith("宣告行放哪：同一則回覆裡先發一條不寫檔的") and "`#` 註解" in hint.split("。", 1)[0]
    assert wg_chain.gate_name(tag, "PreToolUse") == "OldTestDeclare"   # 連鎖斷路器認得出閘名（CHAIN_GATE_NAME），標記自成一行
    assert hit.startswith(OT_HIT)                                       # ✗ 條目照舊在行首（parse_hits 這類行首解析認得到）


def test_old_test_late_debt_releases_after_two_denies(world):
    """Bash 改了既有測試（寫之前看不到改後內容，事後記欠帳）：之後每個呼叫都擋到補宣告——同回合擋兩次後放行、欠帳拿掉。"""
    fp = world["proj"] / "tests" / "test_calc.py"
    ti = {"command": f"sed -i 's/== 2/== 3/' {fp.as_posix()}"}
    assert OT_HIT not in _pre(world, "Bash", ti)                         # 拍快照放行
    fp.write_text(TEST_SRC.replace("== 2", "== 3"), encoding="utf-8")    # 指令真的改了
    st = wg_core.read_state(SID)
    assert ot.after_tool(st, {"tool_name": "Bash", "tool_input": ti, "session_id": SID, "transcript_path": world["tp"],
                              "cwd": str(world["proj"])}, {})
    wg_core.write_state(SID, st)
    assert st.get("old_test_undeclared"), "前置：事後比對記了欠帳"
    reasons = [_pre(world, "Bash", {"command": "ls"}, f"toolu_ls{i}") for i in range(3)]
    assert all(OT_HIT in r for r in reasons[:2]), reasons
    assert wg_chain.gate_name(reasons[0], "PreToolUse") == "OldTestDeclare"   # 事後欠帳那條擋路也帶標記
    assert OT_HIT not in reasons[2]
    assert not wg_core.read_state(SID).get("old_test_undeclared")
    assert "cap_released" in [e["event"] for e in _events(world, "old_test")]


@pytest.fixture
def gb_env(git_cassette, monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "project_smells", vgb.ps)
    monkeypatch.setattr(vgb.ps, "_hub_inputs", lambda: ({}, None))
    git_cassette(exclude=("Logs",))
    return vgb.Env(tmp_path, monkeypatch)


def test_gate_bypass_releases_after_two_denies_in_same_turn(gb_env, tmp_path):
    repo = vgb._qa_notify(tmp_path)
    vgb._blocked(gb_env, repo)
    reasons = [gb_env.run(repo, "git restore --staged notify/retry.py") for _ in range(3)]
    assert all("GATE_BYPASS_NEEDS_DECLARATION" in (r or "") for r in reasons[:2]), reasons
    assert reasons[2] is None
    assert [e["event"] for e in gb_env.events()] == ["suspect", "denied", "suspect", "denied", "suspect", "cap_released"]
    assert reasons[0].splitlines()[1].startswith("宣告行要比這條指令早一則訊息送出")


# ─── 繞閘閘：同一個 repo 的點名檔合併 ───────────────────────────────────────

PICK_OLD = "def pick(xs):\n    return abs(xs)\n"
PICK_SICK = "def pick(xs):\n    return (lambda f: (lambda x: f(x)))(abs)(xs)\n"
PICK_FIXED = "def pick(xs):\n    return abs(xs) + 0\n"


def test_excluded_named_file_still_needs_declaration_after_other_file_fixed(gb_env, tmp_path):
    """病形閘擋 A（retry.py）→ 只交 B（pick.py）又被擋 → 修好 B 再交：A 被排除在提交外、病還在，仍要宣告。"""
    repo = vgb._qa_notify(tmp_path)
    vgb._write(repo, "notify/pick.py", PICK_OLD)
    vgb._git(repo, "add", "notify/pick.py")
    vgb._git(repo, "commit", "-q", "-m", "pick", "--", "notify/pick.py")
    vgb._blocked(gb_env, repo)
    vgb._write(repo, "notify/pick.py", PICK_SICK)
    deny = gb_env.run(repo, 'git commit -m "y" -- notify/pick.py')
    assert deny and "[Guardian:SmellGate]" in deny and "notify/pick.py" in deny, deny
    assert set(gb_env.state["smell_deny_last"]["files"]) == {"notify/retry.py", "notify/pick.py"}
    vgb._write(repo, "notify/pick.py", PICK_FIXED)
    deny = gb_env.run(repo, 'git commit -m "y" -- notify/pick.py')
    assert deny and "GATE_BYPASS_NEEDS_DECLARATION" in deny and "notify/retry.py" in deny, deny


def _a_declared_then_b_blocked(gb_env, tmp_path):
    """A（retry.py）被點名 → 寫宣告 → 只交 B（pick.py，也帶病）又被病形閘擋（宣告還沒被哪條指令用掉）。"""
    repo = vgb._qa_notify(tmp_path)
    vgb._write(repo, "notify/pick.py", PICK_OLD)
    vgb._git(repo, "add", "notify/pick.py")
    vgb._git(repo, "commit", "-q", "-m", "pick", "--", "notify/pick.py")
    vgb._blocked(gb_env, repo)
    gb_env.say("不是繞閘｜retry.py 是別人留在暫存區的改動，不屬本次需求；病交原作者修")
    vgb._write(repo, "notify/pick.py", PICK_SICK)
    assert "[Guardian:SmellGate]" in (gb_env.run(repo, 'git commit -m "y" -- notify/pick.py') or "")
    return repo


def test_declaration_after_a_named_still_counts_for_a(gb_env, tmp_path):
    """宣告寫在 A 被點名之後：修好 B 再交（排除 A），這筆宣告照樣替 A 算數，不多擋一次。"""
    repo = _a_declared_then_b_blocked(gb_env, tmp_path)
    vgb._write(repo, "notify/pick.py", PICK_FIXED)
    assert gb_env.run(repo, 'git commit -m "y" -- notify/pick.py') is None
    assert [e["files"] for e in gb_env.events() if e["event"] == "declared"] == [{"notify/retry.py": ["匿名函式疊用"]}]


def test_declaration_before_b_named_does_not_cover_b(gb_env, tmp_path):
    """宣告寫在 B 被點名之前：B 病還在、也被排除在提交外 → 那筆宣告不替 B 放行，要在 B 被點名之後重新宣告。"""
    repo = _a_declared_then_b_blocked(gb_env, tmp_path)
    deny = gb_env.run(repo, 'git commit -m "y" -- notify/channels.py')
    assert deny and "GATE_BYPASS_NEEDS_DECLARATION" in deny and "notify/pick.py" in deny, deny


# ─── svn 測試路徑閘 ─────────────────────────────────────────────────────

def _svn_proj(w, on: bool) -> Path:
    proj = w["proj"]
    (proj / ".svn").mkdir(exist_ok=True)
    if on:
        (proj / ".claude").mkdir(exist_ok=True)
        (proj / ".claude" / "overview-hub.json").write_text(json.dumps({"svn_test_block": {"enabled": True}}), encoding="utf-8")
    return proj


SVN_TEST_COMMIT = 'svn commit Assets/Tests/FooTest.cs -m "add"'


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_svn_test_block_off_by_default(world, tool):
    _svn_proj(world, on=False)
    assert "[Guardian:SvnTestBlock]" not in _pre(world, tool, {"command": SVN_TEST_COMMIT})


def test_svn_test_block_on_looks_only_at_commit_paths(world):
    _svn_proj(world, on=True)
    assert "[Guardian:SvnTestBlock]" not in _pre(world, "Bash", {"command": 'svn commit src/Foo.cs -m "add test for X"'})
    r = _pre(world, "Bash", {"command": SVN_TEST_COMMIT})
    assert "[Guardian:SvnTestBlock]" in r and "Assets/Tests/FooTest.cs" in r
    assert "[Guardian:SvnTestBlock]" in _pre(world, "PowerShell", {"command": 'svn commit "Assets/Tests/FooTest.cs" -m "add"'})


def test_svn_test_block_user_sentence_this_turn_allows(world):
    _svn_proj(world, on=True)
    st = wg_core.read_state(SID)
    st["turn_prompts"] = ["FooTest 寫好了，單元測試也一起提交上 svn"]
    wg_core.write_state(SID, st)
    ok = "# 測試上 svn 原句：「單元測試也一起提交上 svn」\n" + SVN_TEST_COMMIT
    assert "[Guardian:SvnTestBlock]" not in _pre(world, "Bash", {"command": ok})
    assert [(e["event"], e["quote"]) for e in _events(world, "svn_test_block")] == [("user_quote", "單元測試也一起提交上 svn")]
    made_up = "# 測試上 svn 原句：「使用者沒說過這一句」\n" + SVN_TEST_COMMIT
    assert "[Guardian:SvnTestBlock]" in _pre(world, "Bash", {"command": made_up})
    st["turn_prompts"] = ["程式先上，這次不要提交測試"]                     # 原句在原話裡但被否定：引用了也不算
    wg_core.write_state(SID, st)
    negated = "# 測試上 svn 原句：「不要提交測試」\n" + SVN_TEST_COMMIT
    assert "[Guardian:SvnTestBlock]" in _pre(world, "Bash", {"command": negated})


def test_project_hub_cfg_accepts_svn_test_block(tmp_path):
    """專案的 overview-hub.json 寫 svn_test_block 不是未知鍵（未知鍵＝_errors 非空＝OverviewHub 擋所有改檔）；寫錯型別照報錯。"""
    import hub_config as hc
    root = tmp_path / "p"
    (root / ".claude").mkdir(parents=True)
    hub = root / ".claude" / "overview-hub.json"
    hub.write_text(json.dumps({"svn_test_block": {"enabled": True}}), encoding="utf-8")
    c = hc.merge_hub_cfg({}, None, root)
    assert c["_errors"] == [] and c["svn_test_block"] == {"enabled": True}
    hub.write_text(json.dumps({"svn_test_block": {"enabled": "yes"}}), encoding="utf-8")
    assert any("svn_test_block.enabled" in e for e in hc.merge_hub_cfg({}, None, root)["_errors"])
    assert hc.HUB_DEFAULTS["svn_test_block"] == {"enabled": False}


# ─── 判準卡：不算雜湊 ───────────────────────────────────────────────────

def test_interpreter_bash_takes_no_judge_card_snapshot(world, monkeypatch):
    """資料根索引裡有綁 Entry 的卡、指令跑直譯器：PreToolUse 不記雜湊快照；腳本改了卡，事後也不比對、不留帳；改卡不擋。"""
    proj = world["proj"]
    card = proj / "memory" / "版控" / "測試判準卡-綁e99.md"
    card.parent.mkdir(parents=True)
    card.write_text(CARD, encoding="utf-8")
    (proj / "memory" / "_atom_index.json").write_text(json.dumps({"version": 1, "atoms": [
        {"name": card.stem, "path": "memory/版控/測試判準卡-綁e99.md", "entry": ["E99"]}]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(wg_core, "MEMORY_DIR", proj / "memory")
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", proj)
    ti = {"command": "python tools/fix_cards.py"}
    assert "[Guardian:JudgeCardDeclare]" not in _pre(world, "Bash", ti, "toolu_interp")
    snap = Path(wg_core.WORKFLOW_DIR) / "judge-card-snap"
    assert not (snap.is_dir() and any(snap.glob("*.json")))
    with open(card, "a", encoding="utf-8") as f:
        f.write("- [臨] 腳本補一條\n")
    assert jc.after_tool(wg_core.read_state(SID), {"tool_name": "Bash", "tool_input": ti, "session_id": SID,
                                                   "transcript_path": world["tp"], "tool_use_id": "toolu_interp"}, {}) is False
    assert [e for e in _events(world, "judge_card") if e.get("channel") == "interpreter"] == []
    edit = {"file_path": str(card), "old_string": "原本的判準", "new_string": "改過的判準"}
    assert "[Guardian:JudgeCardDeclare]" not in _pre(world, "Edit", edit)


# ─── commit 前目標對照核對出錯 ───────────────────────────────────────────

def test_commit_gate_exception_does_not_block(world, monkeypatch):
    import wg_need_goal

    def boom(*a, **k):
        raise RuntimeError("目標檔讀壞了")
    monkeypatch.setattr(wg_need_goal, "commit_gate", boom)
    for name in ("check_git_commit_order", "check_git_privacy", "check_merge_driver"):
        monkeypatch.setattr(ptu, name, lambda *a, **k: None)
    monkeypatch.setattr(ptu, "check_smell_gate", lambda *a, **k: (None, None))
    assert "[NeedGoal]" not in _pre(world, "Bash", {"command": 'svn commit src/Foo.cs -m "x"'})
    assert [(e["event"], e.get("rule"), "目標檔讀壞了" in e["error"]) for e in _events(world, "need_goal")
            if e["event"] == "commit_gate_error"] == [("commit_gate_error", "GATE_SELF_ERROR", True)]


# ─── 閘自己出錯（GATE_SELF_ERROR）：不擋、留帳 ─────────────────────────────

def _boom(*a, **k):
    raise RuntimeError("模擬閘內部錯誤")


def test_data_file_gate_self_error_does_not_block(world, monkeypatch):
    monkeypatch.setattr(df, "_judge", _boom)
    r = _pre(world, "Edit", {"file_path": str(world["proj"] / "settings.json"), **DATA_EDIT})
    assert "[Guardian:DataFileAsk]" not in r, r
    assert [(e["event"], e.get("rule"), "模擬閘內部錯誤" in e["error"]) for e in _events(world, "data_file")] == \
        [("error", "GATE_SELF_ERROR", True)]


def test_old_test_gate_self_error_does_not_block(world, monkeypatch):
    monkeypatch.setattr(ot, "gate", _boom)
    r = _pre(world, "Edit", {"file_path": str(world["proj"] / "tests" / "test_calc.py"), **TEST_EDIT})
    assert "[Guardian:OldTestDeclare]" not in r and OT_HIT not in r, r
    assert [(e["event"], e.get("rule"), "模擬閘內部錯誤" in e["error"]) for e in _events(world, "old_test")] == \
        [("error", "GATE_SELF_ERROR", True)]


# ─── 耗重 ─────────────────────────────────────────────────────────────

def test_data_file_gate_reads_transcript_once(world, monkeypatch):
    calls = []
    real = df._transcript_user_entries
    monkeypatch.setattr(df, "_transcript_user_entries", lambda tp: calls.append(tp) or real(tp))
    assert "[Guardian:DataFileAsk]" in _pre(world, "Edit", {"file_path": str(world["proj"] / "settings.json"), **DATA_EDIT})
    assert len(calls) == 1


def test_old_test_gate_reads_no_extra_state(world, monkeypatch):
    callers = []
    real = wg_core.read_state

    def spy(sid):
        callers.append(sys._getframe(1).f_globals.get("__name__"))
        return real(sid)
    monkeypatch.setattr(wg_core, "read_state", spy)
    assert OT_HIT in _pre(world, "Edit", {"file_path": str(world["proj"] / "tests" / "test_calc.py"), **TEST_EDIT})
    assert "wg_oldtest" not in callers, callers


# ─── config.local 合併只有一份（lib/config_local.merge_local）─────────────────

def test_load_config_local_merge_goes_through_merge_local(tmp_path, monkeypatch, capsys):
    """config.local 有巢狀鍵：wg_core.load_config 與 merge_local 結果相同（頂層淺合併，巢狀那層整個取代）；
    load_config 不再自己合併——換掉 merge_local 會改變它的結果；本機覆寫讀壞照舊 stderr 一行、照共用設定跑。"""
    from config_local import merge_local
    wf = tmp_path / "wf"
    wf.mkdir()
    shared = {"guard": {"data_file_ask": {"enabled": True}, "gate_bypass": {"enabled": True, "staging_words": ["x"]}},
              "v6": {"enabled": False}, "x": 1}
    local = {"guard": {"gate_bypass": {"enabled": False}}, "v6": {"enabled": True}, "x": {"y": 2}, "only_local": [1]}
    (wf / "config.json").write_text(json.dumps(shared), encoding="utf-8")
    (wf / "config.local.json").write_text(json.dumps(local), encoding="utf-8")
    monkeypatch.setattr(wg_core, "CONFIG_PATH", wf / "config.json")
    monkeypatch.setattr(wg_core, "CONFIG_LOCAL_PATH", wf / "config.local.json")
    got = wg_core.load_config()
    assert got == merge_local({**wg_core.DEFAULTS, **shared}, wf / "config.local.json")
    assert got["guard"] == {"data_file_ask": {"enabled": True}, "gate_bypass": {"enabled": False}}
    assert got["x"] == {"y": 2} and got["only_local"] == [1] and got["v6"] == {"enabled": True}
    monkeypatch.setattr(wg_core, "merge_local", lambda config, path, tag="": {**config, "_merged_by": tag})
    assert wg_core.load_config()["_merged_by"] == "workflow-guardian"
    monkeypatch.undo()
    monkeypatch.setattr(wg_core, "CONFIG_PATH", wf / "config.json")
    monkeypatch.setattr(wg_core, "CONFIG_LOCAL_PATH", wf / "config.local.json")
    capsys.readouterr()
    (wf / "config.local.json").write_text("{broken", encoding="utf-8")
    assert wg_core.load_config() == {**wg_core.DEFAULTS, **shared}
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 1 and err[0].startswith(f"[workflow-guardian] {wf / 'config.local.json'} 讀取失敗，略過本機覆寫：")
    (wf / "config.local.json").write_text("[1, 2]", encoding="utf-8")       # 不是物件：不合併、不出聲
    assert wg_core.load_config() == {**wg_core.DEFAULTS, **shared} and capsys.readouterr().err == ""
