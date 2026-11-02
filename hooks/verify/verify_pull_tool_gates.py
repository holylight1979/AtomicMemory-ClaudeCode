"""verify_pull_tool_gates.py：工具前的閘不再「交了看不到就一直擋」——擋次上限、svn 測試路徑閘。

每條都是會紅案例（改前的碼跑會紅），除了 deny_cap 單元案都走 handlers/pre_tool_use.handle_pre_tool_use 真入口：
- 擋次上限（wg_core.deny_cap，案例給 cap=2）：同一個使用者回合同一件缺件擋第 1、2 次，第 3 次放行；同一則回覆平行送出的呼叫算一次；換回合重算。
- 改資料檔、改舊測試不用先宣告：寫碼守門開著、這個 session 寫過程式，Edit 既有設定檔、刪既有測試的斷言、Bash 改測試檔之後的
  下一個工具呼叫都不擋，也不留 guard-data_file／guard-old_test 帳。
- svn 測試路徑閘：預設關；專案 overview-hub.json 開了之後只看 commit 的路徑參數（-m 訊息不看）、PowerShell 也查、
  使用者本回合原句出口；overview-hub.json 寫 svn_test_block 不是未知鍵。
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

import wg_core  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402

SID = "sess-pull-tool-gates-0001"
PROMPT = "幫 calc 加一個減法，設定檔裡的精度照舊"
TEST_SRC = "def test_add():\n    assert 1 + 1 == 2\n"
TEST_EDIT = {"old_string": "assert 1 + 1 == 2", "new_string": "assert 1 + 1 == 3"}
DATA_EDIT = {"old_string": '"precision": 2', "new_string": '"precision": 3'}


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


def _wrote_code(w):
    """這個 session 改過程式檔（寫碼回合，wg_core.coding_turn）。只給改資料檔／改舊測試的案例用；共用 fixture 不放，
    免得其他閘的案例也變成寫碼回合。"""
    st = wg_core.read_state(SID)
    st["modified_files"] = [{"path": str(w["proj"] / "app.py"), "last_turn_seq": 1}]
    wg_core.write_state(SID, st)


# ─── 擋次上限 ─────────────────────────────────────────────────────────────

def test_deny_cap_counts_each_item_per_user_turn():
    st = {"turn_seq": 3}
    assert [wg_core.deny_cap(st, "g", ["a"], cap=2) for _ in range(4)] == [(["a"], []), (["a"], []), ([], ["a"]), ([], [])]
    assert wg_core.deny_cap(st, "g", ["b", "c"], cap=2) == (["b", "c"], [])
    assert wg_core.deny_cap(st, "g", ["b", "c"], cap=2) == (["b", "c"], [])
    assert wg_core.deny_cap(st, "g", ["b", "d"], cap=2) == (["d"], [])          # d 照擋整條還是被擋：b 這次不算放行
    assert wg_core.deny_cap(st, "g", ["b"], cap=2) == ([], ["b"])
    assert wg_core.deny_cap(st, "other", ["a"], cap=2) == (["a"], [])           # 別道閘另算
    st["turn_prompts_seq"] = 4                                           # 使用者開了新回合：重算
    assert wg_core.deny_cap(st, "g", ["a"], cap=2) == (["a"], [])
    assert wg_core.deny_cap(None, "g", ["a"], cap=2) == (["a"], [])             # 沒有 state 可記：照擋


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
    assert [wg_core.deny_cap(st, "g", ["a"], cap=2, call=call(t)) for t in ("t1", "t2", "t3", "t4")] == [(["a"], [])] * 4
    _reply(tp, "m1", "t1", "t2", "t3", "t4")
    assert wg_core.deny_cap(st, "g", ["a"], cap=2, call=call("t5")) == (["a"], [])                # 第二則：第 2 次
    _reply(tp, "m2", "t5")
    assert wg_core.deny_cap(st, "g", ["a"], cap=2, call=call("t6")) == ([], ["a"])                # 第三則：放行、回給呼叫端留帳
    assert wg_core.deny_cap(st, "g", ["a"], cap=2, call=call("t7")) == ([], [])                   # 同一則的下一個呼叫：不重回
    assert not _events(world, "deny_cap")
    sub = {"turn_seq": 3}
    assert [wg_core.deny_cap(sub, "g", ["a"], cap=2, call=call(f"s{i}", agent_id="ag1")) for i in range(3)] == \
        [(["a"], []), (["a"], []), ([], ["a"])]                                             # 子代理：照每個呼叫算
    assert {(e["event"], e["rule"]) for e in _events(world, "deny_cap")} == {("batch_unknown", "DENY_CAP_PER_REPLY")}
    # 一次缺兩件：a 剛到上限、b 照擋 → 整條擋、a 不算放行也不算「這一則算過」；同一則下一個呼叫只缺 a → a 放行（codex 一輪 BLOCK 1）
    two = {"turn_seq": 3, "decl_deny_counts": {"turn": 3, "counts": {"g|a": 2, "g|b": 0}, "batch": {}}}
    _reply(tp, "m3", "t6", "t7")
    assert wg_core.deny_cap(two, "g", ["a", "b"], cap=2, call=call("t8")) == (["b"], [])
    assert wg_core.deny_cap(two, "g", ["a"], cap=2, call=call("t9")) == ([], ["a"])
    assert wg_core.deny_cap(two, "g", ["a", "b"], cap=2, call=call("t10")) == (["b"], [])      # b 同一則照第一次擋；a 已放行過不重回


# ─── 改資料檔、改舊測試不用先宣告 ─────────────────────────────────────────────────

def test_data_file_and_old_test_edits_are_not_blocked(world):
    """寫碼守門開（conftest 預設 WG_V6=1）、這個 session 寫過程式：Edit 使用者既有的設定檔、改既有測試的斷言、
    Bash 改測試檔之後的下一個工具呼叫，都不擋，也不留改資料檔／改舊測試的帳。"""
    _wrote_code(world)
    assert _pre(world, "Edit", {"file_path": str(world["proj"] / "settings.json"), **DATA_EDIT}) == ""
    assert _pre(world, "Edit", {"file_path": str(world["proj"] / "tests" / "test_calc.py"), **TEST_EDIT}) == ""
    fp = world["proj"] / "tests" / "test_calc.py"
    assert _pre(world, "Bash", {"command": f"sed -i 's/== 2/== 3/' {fp.as_posix()}"}, "toolu_sed") == ""
    fp.write_text(TEST_SRC.replace("== 2", "== 3"), encoding="utf-8")
    assert _pre(world, "Bash", {"command": "ls"}, "toolu_ls") == ""
    assert not _events(world, "data_file") and not _events(world, "old_test")
    st = wg_core.read_state(SID)
    assert not any(k in st for k in ("old_test_undeclared", "data_file_declared", "data_file_pending_new"))


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
