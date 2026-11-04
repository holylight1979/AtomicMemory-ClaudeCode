"""verify_post_compact_reinjection_phase4.py — 壓縮後把卡片內文送回去的守門。

壓縮的事件順序：PreCompact → SessionStart(source=compact) → PostCompact → 之後的 PostToolBatch。守住：
1. **SessionStart(compact) 主路**（規則 COMPACT_REINJECT_AT_SESSION_START）：讀 PreCompact 快照，輸出含每張卡的
   卡名與內文、記 compact_reinjected_at、送出的卡算回 injected_atoms；之後 PostCompact 不暫存、PostToolBatch 不重送。
   壓縮時 cwd 變了走重建分支也照舊 state 組卡（組卡在分岔前）。
2. **PostCompact 不注入**：post_compact.py 絕不走 output_json（官方 hooks.md：PostCompact 無決策控制、不收
   additionalContext）；沒有記號時才暫存內文＋pending 旗標。
3. **PreCompact 快照**：壓縮前把 injected_atoms 存進 pre_compact_injected_atoms，並清上一輪的記號。
4. **PostToolBatch 補位**：pending 且沒記號 → 一次性送出、清旗標；有記號 → 只清旗標；idle 零輸出。
5. **端到端**：PreCompact→PostCompact→PostToolBatch（SessionStart 沒跑的補位路）送得出內文。
6. **接線**：dispatcher.HANDLERS 與 settings.json 皆註冊 PostCompact + PostToolBatch。
7. **budget 守紅線**：印象式 strip + budget 上限，blob 不爆量。
8. **重建 state 照搬**：session_start _CARRY_ON_REBUILD 帶讀檔帳、意圖、Depends 已提示與權威地圖旗標。

受控 tmp 索引 + monkeypatch state I/O，不依賴磁碟既有 atom / 真實 state。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_post_compact_reinjection_phase4.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE / "lib"))

import handlers.pre_compact as prc  # noqa: E402
import handlers.post_compact as pc  # noqa: E402
import handlers.post_tool_batch as ptb  # noqa: E402


# ─── fixtures ────────────────────────────────────────────────────────────────


def _atom_text(name: str) -> str:
    return (
        f"# {name}\n\n"
        f"- Confidence: [固]\n"
        f"- Trigger: t-{name}\n\n"
        f"## 印象\n\n- {name} 的印象重點一句話，供壓縮後復原。\n\n"
        f"## 行動\n\n- 做 {name} 對應動作。\n"
    )


def _setup(tmp_path, monkeypatch, injected):
    """建受控 memory（tmp/memory/{name}.md）+ state（atom_index global）+ monkeypatch state I/O。

    rel_path 'memory/{name}.md' 相對 MEMORY_DIR.parent（=tmp）→ 與 build_injection_blob 同基準。
    回 holder（{'state': dict}），三 handler 共用以模擬跨事件持久化。
    """
    mem = tmp_path / "memory"
    mem.mkdir(parents=True, exist_ok=True)
    for n in injected:
        (mem / f"{n}.md").write_text(_atom_text(n), encoding="utf-8")

    state = {
        "session": {"id": "test-sid"},
        "injected_atoms": list(injected),
        "episodic_checkpoint_done": True,   # 跳過 pre_compact 的 episodic 生成
        "atom_index": {
            "global": [[n, f"memory/{n}.md", [f"t-{n}"]] for n in injected],
            "project": [],
            "project_memory_dir": "",
        },
    }
    holder = {"state": state}

    def fake_ensure(sid, inp, cfg):
        return holder["state"]

    def fake_write(sid, st):
        holder["state"] = st

    monkeypatch.setattr(pc, "MEMORY_DIR", mem)
    for mod in (prc, pc, ptb):
        monkeypatch.setattr(mod, "_ensure_state", fake_ensure, raising=False)
        monkeypatch.setattr(mod, "write_state", fake_write, raising=False)
    return holder


def _run(handler, input_data, config=None):
    """呼叫 handler（output_* 會 sys.exit）→ 捕捉 SystemExit。回不適用（stdout 由 capsys 取）。"""
    with pytest.raises(SystemExit):
        handler(input_data, config or {})


# ─── 不變式 1：PostCompact 絕不注入（純檔案守門）─────────────────────────────


def test_post_compact_never_injects_additional_context():
    src = (CLAUDE / "hooks" / "handlers" / "post_compact.py").read_text(encoding="utf-8")
    assert "output_json" not in src, "PostCompact 不得 output_json（官方：PostCompact 不收 additionalContext）"
    assert "pending_reinjection" in src, "PostCompact 應 stash pending_reinjection flag"


# ─── 不變式 1：SessionStart(compact) 主路 ─────────────────────────────────────


def _run_session_start_compact(tmp_path, monkeypatch, holder):
    """跑 handle_session_start(source=compact) 的沿用舊 state 那條路；會碰真實環境的段落
    （清舊 state、向量服務、標記檔、MCP／必載檔檢查、log 輪替）全換成不做事。"""
    from handlers import session_start as ss
    import wg_core
    env = tmp_path / "env"
    monkeypatch.setenv("WG_CODING_GUARD", "0")
    monkeypatch.setattr(wg_core, "rotate_log_if_oversized", lambda *a, **k: None)
    monkeypatch.setattr(ss, "resolve_project_root", None)        # 不算專案根指紋 → 走沿用舊 state 那條
    monkeypatch.setattr(ss, "read_state", lambda sid: holder["state"])
    monkeypatch.setattr(ss, "write_state", lambda sid, st: holder.__setitem__("state", st))
    for name in ("MEMORY_DIR", "WORKFLOW_DIR", "CLAUDE_DIR"):
        monkeypatch.setattr(ss, name, env)
    monkeypatch.setattr(ss, "REALM_AUTOMOVE_MARKER", env / "realm-automove.json")
    monkeypatch.setattr(ss, "WISDOM_AVAILABLE", False)
    stubs = (("_check_se_sentinel_residual", None), ("_check_periodic_review_due", None),
             ("_load_oscillation_warnings", None), ("check_long_die_status", None), ("_check_mcp_servers", []),
             ("check_always_load_contracts", []), ("_cleanup_old_states", None), ("_refresh_vector_flag", None))
    for name, value in stubs:
        monkeypatch.setattr(ss, name, lambda *a, _v=value, **k: _v)
    with pytest.raises(SystemExit):
        ss.handle_session_start({"session_id": "test-sid", "cwd": str(tmp_path), "source": "compact"},
                                {"vector_search": {"auto_start_service": False}})


def test_session_start_compact_sends_cards_then_nothing_resends(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, ["alpha", "beta"])
    _run(prc.handle_pre_compact, {"session_id": "test-sid"})
    capsys.readouterr()
    holder["state"]["injected_atoms"] = ["gamma"]    # 快照之後名單又變：SessionStart 要照快照送，不照現存名單

    _run_session_start_compact(tmp_path, monkeypatch, holder)
    hso = json.loads(capsys.readouterr().out.strip())["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart"
    ctx = hso["additionalContext"]
    for n in ("alpha", "beta"):
        assert f"[Atom:{n}]" in ctx, f"SessionStart(compact) 輸出缺卡名 {n}"
        assert f"{n} 的印象重點" in ctx, f"SessionStart(compact) 輸出缺 {n} 的內文"
    assert "壓縮前已載入: " not in ctx, "內文已含卡名，不該再列一行卡名"
    st = holder["state"]
    assert st.get("compact_reinjected_at"), "送出後要記 compact_reinjected_at"
    assert st.get("injected_atoms") == ["alpha", "beta"], "送出的卡要算回 injected_atoms"

    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "manual"})
    assert capsys.readouterr().out.strip() == ""
    assert not holder["state"].get("pending_reinjection"), "SessionStart 送過，PostCompact 不該再暫存"
    assert holder["state"].get("post_compact_at"), "壓縮時間點照記（ups_inject 判壓縮後送過用）"

    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Read"}]})
    assert "[Atom:" not in capsys.readouterr().out, "SessionStart 送過，PostToolBatch 不該重送"


def test_compact_recovery_reads_old_state_before_branching(tmp_path, monkeypatch):
    """壓縮時 cwd 跟開場不同（磁碟代號大小寫、cd 進子目錄）會走重建分支、新 state 沒有快照——組卡要在分岔前從舊 state 做。"""
    from handlers import session_start as ss
    holder = _setup(tmp_path, monkeypatch, ["alpha", "beta"])
    holder["state"]["pre_compact_injected_atoms"] = ["alpha", "beta"]
    blob, sent, unresolved = ss._compact_recovery(holder["state"], {})
    assert "[Atom:alpha]" in blob and "[Atom:beta]" in blob and sent == ["alpha", "beta"] and unresolved == []
    assert ss._compact_recovery(None, {}) == ("", [], [])
    src = (HOOKS_DIR / "handlers" / "session_start.py").read_text(encoding="utf-8")
    assert src.index("_compact_recovery(existing, config)") < src.index("root_rebuilt = True"), \
        "組卡要在判斷走哪條路之前（重建分支的新 state 沒有 PreCompact 快照）"


def test_pre_compact_clears_last_round_marker(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, ["alpha"])
    holder["state"]["compact_reinjected_at"] = "2026-01-01T00:00:00"
    _run(prc.handle_pre_compact, {"session_id": "test-sid"})
    assert "compact_reinjected_at" not in holder["state"], "記號只代表這一輪壓縮，PreCompact 要清"


def test_post_tool_batch_drops_stash_when_session_start_sent(tmp_path, monkeypatch, capsys):
    """PostCompact 先暫存、SessionStart 後送（順序反過來）也不重送：PostToolBatch 看到記號只清旗標。"""
    holder = _setup(tmp_path, monkeypatch, ["alpha"])
    holder["state"].update({"pending_reinjection": True, "pending_reinjection_blob": "[Atom:alpha]\nX",
                            "pending_reinjection_atoms": ["alpha"], "compact_reinjected_at": "2026-01-01T00:00:00"})
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Read"}]})
    assert "[Atom:alpha]" not in capsys.readouterr().out
    assert holder["state"].get("pending_reinjection") is False and "pending_reinjection_blob" not in holder["state"]


# ─── 不變式 2：PreCompact 快照 ───────────────────────────────────────────────


def test_pre_compact_snapshots_injected(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, ["alpha", "beta"])
    _run(prc.handle_pre_compact, {"session_id": "test-sid"})
    snap = holder["state"].get("pre_compact_injected_atoms")
    assert snap == ["alpha", "beta"], f"PreCompact 未快照 injected_atoms: {snap}"


# ─── 不變式 3：PostCompact stash blob + flag，零 stdout ───────────────────────


def test_post_compact_stashes_blob_and_flag(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, ["alpha", "beta"])
    holder["state"]["pre_compact_injected_atoms"] = ["alpha", "beta"]
    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "auto",
                                  "compact_summary": "做了 alpha 與 beta 的事"})
    st = holder["state"]
    assert st.get("pending_reinjection") is True, "未設 pending_reinjection"
    blob = st.get("pending_reinjection_blob", "")
    assert "[Atom:alpha]" in blob and "[Atom:beta]" in blob, "blob 缺復原 atom 內文"
    assert "Atom Recovery" in blob
    assert set(st.get("pending_reinjection_atoms", [])) == {"alpha", "beta"}
    # PostCompact 本身零注入
    assert capsys.readouterr().out.strip() == "", "PostCompact 不應有 stdout 輸出"


def test_post_compact_empty_when_no_atoms(tmp_path, monkeypatch, capsys):
    """無 atom 就什麼都不 stash；有讀檔帳（overview_hub）也一樣，部位紀錄不重注。"""
    holder = _setup(tmp_path, monkeypatch, [])
    holder["state"]["injected_atoms"] = []
    holder["state"].pop("pre_compact_injected_atoms", None)
    holder["state"]["overview_hub"] = {"c:/p|戰鬥": {"root": "c:/p", "part": "戰鬥", "part_files_read": ["c:/p/a.cs"]}}
    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "manual"})
    assert holder["state"].get("pending_reinjection") is not True
    assert not any(k.startswith("pending_reinjection_") for k in holder["state"])
    assert capsys.readouterr().out.strip() == ""


# ─── 重建 state 照搬 ──────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_org(monkeypatch):
    import wg_overview as wo
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())


def test_rebuild_carry_keeps_one_shot_flags_so_nothing_resends(tmp_path, monkeypatch):   # 退件 BLOCK 8
    """照 session_start 重建分支的搬法（for key in _CARRY_ON_REBUILD）搬舊 state，權威地圖不得重送。"""
    from handlers import session_start as ss
    import wg_depends as wd
    existing = {"authority_map_injected": True, "depends_hints": ["c"], "turn_intent": "general", "overview_hub": {}}
    rebuilt = {"session": {"cwd": str(tmp_path)}}
    for key in ss._CARRY_ON_REBUILD:
        if key in existing:
            rebuilt[key] = existing[key]
    assert rebuilt["authority_map_injected"] is True
    assert wd._authority_map_text(rebuilt, "s", str(tmp_path / "a.md"), {"authority_map": {"*.md": "m.md"},
                                                                         "max_card_chars": 100}, tmp_path) is None


def test_session_start_carry_on_rebuild_includes_overview_keys():
    from handlers import session_start as ss
    for key in ("overview_hub", "turn_intent", "depends_hints", "authority_map_injected", "pre_compact_injected_atoms"):
        assert key in ss._CARRY_ON_REBUILD, key
    assert isinstance(ss._CARRY_ON_REBUILD, tuple)
    src = (HOOKS_DIR / "handlers" / "session_start.py").read_text(encoding="utf-8")
    assert "_first_session_hint_lines(root_res, cwd)" in src                                  # d2 的 first_session_hint 掛上


# ─── 不變式 4：PostToolBatch idle 極輕 + 一次性注入 ──────────────────────────


def test_post_tool_batch_idle_early_exit(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, ["alpha"])
    holder["state"].pop("pending_reinjection", None)
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": []})
    assert capsys.readouterr().out.strip() == "", "idle PostToolBatch 不得有輸出"
    assert "pending_reinjection_blob" not in holder["state"]


def test_post_tool_batch_injects_once_and_clears(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, ["alpha", "beta"])
    holder["state"]["pending_reinjection"] = True
    holder["state"]["pending_reinjection_blob"] = "[Atom:alpha]\nX\n\n[Atom:beta]\nY"
    holder["state"]["pending_reinjection_atoms"] = ["alpha", "beta"]
    holder["state"]["injected_atoms"] = []   # 模擬 SessionStart(compact) 已清空
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Read"}]})

    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    hso = payload["hookSpecificOutput"]
    assert hso["hookEventName"] == "PostToolBatch"
    assert "[Atom:alpha]" in hso["additionalContext"]

    st = holder["state"]
    assert st.get("pending_reinjection") is False, "未清 pending flag（會重複注入）"
    assert "pending_reinjection_blob" not in st
    # 復原名單 merge 回 injected_atoms（維持 use 偵測 / Phase 2 歸因）
    assert set(st.get("injected_atoms", [])) == {"alpha", "beta"}


# ─── 不變式 5：端到端 round-trip ─────────────────────────────────────────────


def test_roundtrip_precompact_postcompact_posttoolbatch(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, ["alpha", "beta"])
    _run(prc.handle_pre_compact, {"session_id": "test-sid"})
    capsys.readouterr()
    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "auto"})
    capsys.readouterr()
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Bash"}]})
    out = capsys.readouterr().out.strip()
    hso = json.loads(out)["hookSpecificOutput"]
    assert hso["hookEventName"] == "PostToolBatch"
    ctx = hso["additionalContext"]
    assert "[Atom:alpha]" in ctx and "[Atom:beta]" in ctx, "round-trip 未注入復原內文"
    # 注入後 pending 已清
    assert holder["state"].get("pending_reinjection") is False


# ─── 不變式 6：budget 守紅線 ─────────────────────────────────────────────────


def test_budget_bounded(tmp_path, monkeypatch, capsys):
    many = [f"atom{i}" for i in range(40)]
    holder = _setup(tmp_path, monkeypatch, many)
    holder["state"]["pre_compact_injected_atoms"] = many
    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "auto"},
         {"atoms": {"post_compact_budget": 300}})
    blob = holder["state"].get("pending_reinjection_blob", "")
    # 粗估 token（~4 char/tok）受 budget 約束（含 header 餘裕，放寬到 2x）
    assert len(blob) // 4 <= 300 * 2, f"blob 超出 budget 過多: ~{len(blob)//4} tok"


# ─── 不變式 7：接線（dispatcher + settings）──────────────────────────────────


def test_dispatcher_registers_new_events():
    import dispatcher
    assert "PostCompact" in dispatcher.HANDLERS, "dispatcher 未註冊 PostCompact"
    assert "PostToolBatch" in dispatcher.HANDLERS, "dispatcher 未註冊 PostToolBatch"


def test_settings_has_postcompact_posttoolbatch():
    settings = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))
    hooks = settings.get("hooks", {})
    assert "PostCompact" in hooks, "settings.json 缺 PostCompact hook"
    assert "PostToolBatch" in hooks, "settings.json 缺 PostToolBatch hook"
