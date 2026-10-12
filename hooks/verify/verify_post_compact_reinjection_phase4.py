"""verify_post_compact_reinjection_phase4.py — 選配 #4 壓縮後 atom 內文復原守門.

守住壓縮後 atom 內文復原的不變式：
1. **PostCompact 不注入**：post_compact.py 絕不走 output_json / hookSpecificOutput（反編譯實證 PostCompact
   不支援 additionalContext）；只 stash blob + pending flag。違反 → 注入靜默失效。
2. **PreCompact 快照**：壓縮前把 injected_atoms 存進 pre_compact_injected_atoms（免受 SessionStart(compact)
   清空順序影響）。
3. **PostToolBatch 一次性注入**：pending 時輸出 hookEventName=PostToolBatch + additionalContext=blob，
   隨即清 flag；idle（無 pending）時極輕 early-exit、零輸出。
4. **端到端 round-trip**：PreCompact→PostCompact→PostToolBatch 後，注入內容含復原 atom 內文。
5. **接線**：dispatcher.HANDLERS 與 settings.json 皆註冊 PostCompact + PostToolBatch。
6. **budget 守紅線**：印象式 strip + budget 上限，blob 不爆量。
7. **A2／Q2 綜觀不丟**：PreCompact 快照 overview_hub 摘要與 turn_intent；PostCompact 無 atom **且**無 hub 才空，否則每部位組
   「主目標／層／卡／病灶前 N／定位三行已交否」截 post_compact_chars 存 pending_reinjection_overview；PostToolBatch 注入順序
   atom 先、綜觀後、兩個 pending 都一次性 pop；反例：只剩單一部位（單層視野）＝FAIL；session_start _CARRY_ON_REBUILD 帶四鍵。

受控 tmp 索引 + monkeypatch state I/O，不依賴磁碟既有 atom / 真實 state。
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
    assert "output_json" not in src, "PostCompact 不得 output_json（不支援 additionalContext 注入）"
    assert "pending_reinjection" in src, "PostCompact 應 stash pending_reinjection flag"


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


def test_post_compact_empty_only_when_no_atoms_and_no_hub(tmp_path, monkeypatch, capsys):
    """A2.2：無 atom **且**無 OverviewHub 注入紀錄才什麼都不 stash；只注入過導讀卡（atom 名單空）的 session 仍要 stash 綜觀。"""
    holder = _setup(tmp_path, monkeypatch, [])
    holder["state"]["injected_atoms"] = []
    holder["state"].pop("pre_compact_injected_atoms", None)
    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "manual"})
    assert holder["state"].get("pending_reinjection") is not True
    assert "pending_reinjection_overview" not in holder["state"]
    assert capsys.readouterr().out.strip() == ""
    # 只有 hub、沒 atom → 仍 stash 綜觀
    holder = _setup(tmp_path, monkeypatch, [])
    holder["state"]["injected_atoms"] = []
    holder["state"]["overview_hub"] = _q2_hub(tmp_path)
    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "manual"})
    st = holder["state"]
    assert st.get("pending_reinjection") is True and "pending_reinjection_blob" not in st
    assert "[Overview Recovery]" in st["pending_reinjection_overview"]
    assert capsys.readouterr().out.strip() == ""


# ─── A2（Q2）：壓縮後綜觀不丟 ──────────────────────────────────────────

Q2 = HOOKS_DIR / "verify" / "fixtures" / "v6" / "q2"
Q2_EXPECTED = json.loads((Q2 / "expected.json").read_text(encoding="utf-8"))


def _q2_hub(tmp_path):
    """兩個部位的 OverviewHub 注入紀錄（照 wg_overview._inject 的欄位），卡檔從 fixture 複製進假專案。"""
    import shutil
    root = tmp_path / "proj"
    cards = root / ".claude" / "memory" / "shared"
    cards.mkdir(parents=True, exist_ok=True)
    shutil.copy(Q2 / "overview-map.md", root / ".claude" / "overview-map.md")
    for c in (Q2 / "cards").glob("*.md"):
        shutil.copy(c, cards / c.name)
    rk = str(root).replace("\\", "/").lower()
    return {
        f"{rk}|戰鬥": {"injected_turn": 3, "intent": "debug", "slices": ["defects"], "card_paths": [str(cards / "戰鬥導讀.md")],
                       "reads_after": [], "part_files_read": [], "depends_files_read": [], "located": True, "edits": 2,
                       "edited_files": {f"{rk}/game/battle/a.cs": 2}, "root": str(root), "part": "戰鬥", "layer": "熱修／主程式集",
                       "locate_template": []},
        f"{rk}|UI 演出": {"injected_turn": 5, "intent": "debug", "slices": [], "card_paths": [str(cards / "ui導讀.md")],
                          "reads_after": [], "part_files_read": [], "depends_files_read": [], "located": False, "edits": 0,
                          "edited_files": {}, "root": str(root), "part": "UI 演出", "layer": "單層", "locate_template": []},
        f"{rk}|(unmapped)docs": {"part_files_read": ["x"], "edits": 0},
    }


def _assert_q2_both_parts(blob: str) -> None:
    """Q2 檢查器：兩部位的部位名、層、病灶都要在；少任何一部位＝只剩單層視野＝FAIL。"""
    for part, layer, marker in zip(Q2_EXPECTED["parts"], Q2_EXPECTED["layers"], Q2_EXPECTED["defect_markers"]):
        assert f"【{part}】" in blob, f"壓縮後只剩單層視野：缺部位 {part}"
        assert f"層：{layer}" in blob, f"缺 {part} 的層"
        assert marker in blob, f"缺 {part} 的病灶"


@pytest.fixture(autouse=True)
def _no_org(monkeypatch):
    import wg_overview as wo
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())


def test_pre_compact_snapshots_overview_and_intent(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, ["alpha"])
    holder["state"]["overview_hub"] = _q2_hub(tmp_path)
    holder["state"]["turn_intent"] = "debug"
    _run(prc.handle_pre_compact, {"session_id": "test-sid"})
    st = holder["state"]
    assert st["pre_compact_turn_intent"] == "debug"
    snap = st["pre_compact_overview_hub"]
    assert set(snap) == {k for k in st["overview_hub"] if "(unmapped)" not in k}          # 無表 key 不帶
    assert snap[next(k for k in snap if k.endswith("|戰鬥"))]["layer"] == "熱修／主程式集"
    assert all("reads_after" not in v for v in snap.values())                                 # 只留重注要用的欄


def test_q2_post_compact_keeps_both_parts_layers_cards_defects(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, [])
    holder["state"]["injected_atoms"] = []
    holder["state"]["overview_hub"] = _q2_hub(tmp_path)
    holder["state"]["turn_intent"] = "debug"
    _run(prc.handle_pre_compact, {"session_id": "test-sid"})
    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "auto"})
    st = holder["state"]
    blob = st["pending_reinjection_overview"]
    _assert_q2_both_parts(blob)
    assert "壓縮前意圖：debug" in blob and "主目標：debug（視角：目標視角；先問：幾份存法、有無訊號）" in blob
    assert "【戰鬥】層：熱修／主程式集｜定位三行：已交（本 session 改過 2 次）" in blob
    assert "【UI 演出】層：單層｜定位三行：未交（本 session 改過 0 次）" in blob
    assert "同檔多次：" in blob and "/game/battle/a.cs" in blob
    assert "ui導讀.md" in blob and "戰鬥導讀.md" in blob
    assert st["pending_reinjection_parts"] == ["戰鬥", "UI 演出"]
    assert all(rec.get("reinjected_after_compact") is True for k, rec in st["overview_hub"].items() if "(unmapped)" not in k)
    assert "reinjected_after_compact" not in st["overview_hub"][next(k for k in st["overview_hub"] if "(unmapped)" in k)]
    assert capsys.readouterr().out.strip() == ""


def test_q2_counterexample_single_layer_blob_fails_checker(tmp_path, monkeypatch):
    """反例：壓縮後只剩一個部位（舊行為／只重注單層）→ Q2 檢查器 FAIL。"""
    holder = _setup(tmp_path, monkeypatch, [])
    hub = _q2_hub(tmp_path)
    hub.pop(next(k for k in hub if k.endswith("|UI 演出")))
    holder["state"]["overview_hub"] = hub
    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "auto"})
    single = holder["state"]["pending_reinjection_overview"]
    assert "【戰鬥】" in single
    with pytest.raises(AssertionError, match="單層視野"):
        _assert_q2_both_parts(single)


def test_post_compact_chars_truncates_each_part(tmp_path, monkeypatch):
    holder = _setup(tmp_path, monkeypatch, [])
    holder["state"]["overview_hub"] = _q2_hub(tmp_path)
    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "auto"}, {"overview_hub": {"post_compact_chars": 80}})
    blob = holder["state"]["pending_reinjection_overview"]
    parts = blob.split("\n\n")[1:]
    assert len(parts) == 2 and all(len(p) <= 80 + 60 and "post_compact_chars=80 截斷" in p for p in parts)
    assert "【戰鬥】" in blob and "【UI 演出】" in blob                                        # 截斷也不丟部位
    # WARN 修：短欄在前，硬切也保住「層」與「三行已交否」
    assert "層：熱修／主程式集｜定位三行：已交" in blob and "層：單層｜定位三行：未交" in blob


def test_post_tool_batch_injects_atoms_before_overview_and_pops_both(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, ["alpha"])
    holder["state"]["pending_reinjection"] = True
    holder["state"]["pending_reinjection_blob"] = "[Atom:alpha]\nX"
    holder["state"]["pending_reinjection_atoms"] = ["alpha"]
    holder["state"]["pending_reinjection_overview"] = "[Overview Recovery] 【戰鬥】…"
    holder["state"]["pending_reinjection_parts"] = ["戰鬥"]
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Read"}]})
    ctx = json.loads(capsys.readouterr().out.strip())["hookSpecificOutput"]["additionalContext"]
    assert ctx.index("[Atom:alpha]") < ctx.index("[Overview Recovery]")                      # atom 先、overview 後
    st = holder["state"]
    assert "pending_reinjection_overview" not in st and "pending_reinjection_parts" not in st and st["pending_reinjection"] is False
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Read"}]})
    assert capsys.readouterr().out.strip() == ""                                             # 一次性
    # 只有 overview（沒 atom）也會醒來注入
    holder["state"]["pending_reinjection"] = True
    holder["state"]["pending_reinjection_overview"] = "[Overview Recovery] only"
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": []})
    assert "[Overview Recovery] only" in json.loads(capsys.readouterr().out.strip())["hookSpecificOutput"]["additionalContext"]


def test_rebuild_carry_keeps_one_shot_flags_so_nothing_resends(tmp_path, monkeypatch):   # 退件 BLOCK 8
    """照 session_start 重建分支的搬法（for key in _CARRY_ON_REBUILD）搬舊 state，idle 一行與權威地圖不得重送。"""
    from handlers import session_start as ss
    import wg_overview as wo
    import wg_depends as wd
    existing = {"idle_scan_sent": True, "authority_map_injected": True, "candidates_sent": ["k"],
                "depends_hints": ["c"], "turn_intent": "general", "overview_hub": {}}
    rebuilt = {"session": {"cwd": str(tmp_path)}}
    for key in ss._CARRY_ON_REBUILD:
        if key in existing:
            rebuilt[key] = existing[key]
    assert rebuilt["idle_scan_sent"] is True and rebuilt["authority_map_injected"] is True
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    assert wo.on_prompt(rebuilt, "s", "接下來做什麼？", "", {}, intent="general") is None
    assert wd._authority_map_text(rebuilt, "s", str(tmp_path / "a.md"), {"authority_map": {"*.md": "m.md"},
                                                                         "max_card_chars": 100}, tmp_path) is None


def test_session_start_carry_on_rebuild_includes_overview_keys():
    from handlers import session_start as ss
    for key in ("overview_hub", "turn_intent", "depends_hints", "candidates_sent", "idle_scan_sent", "authority_map_injected"):
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
