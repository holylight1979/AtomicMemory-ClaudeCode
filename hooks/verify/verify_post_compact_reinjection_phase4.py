"""verify_post_compact_reinjection_phase4.py — 選配 #4 壓縮後 atom 內文復原守門 (2026-06-01).

守住 Option B 的不變式（plans/deep-wobbling-bentley.md）：
1. **PostCompact 不注入**：post_compact.py 絕不走 output_json / hookSpecificOutput（反編譯實證 PostCompact
   不支援 additionalContext）；只 stash blob + pending flag。違反 → 注入靜默失效。
2. **PreCompact 快照**：壓縮前把 injected_atoms 存進 pre_compact_injected_atoms（免受 SessionStart(compact)
   清空順序影響）。
3. **PostToolBatch 一次性注入**：pending 時輸出 hookEventName=PostToolBatch + additionalContext=blob，
   隨即清 flag；idle（無 pending）時極輕 early-exit、零輸出。
4. **端到端 round-trip**：PreCompact→PostCompact→PostToolBatch 後，注入內容含復原 atom 內文。
5. **接線**：dispatcher.HANDLERS 與 settings.json 皆註冊 PostCompact + PostToolBatch。
6. **budget 守紅線**：印象式 strip + budget 上限，blob 不爆量。

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


def test_post_compact_empty_when_no_injected(tmp_path, monkeypatch, capsys):
    holder = _setup(tmp_path, monkeypatch, [])
    holder["state"]["injected_atoms"] = []
    holder["state"].pop("pre_compact_injected_atoms", None)
    _run(pc.handle_post_compact, {"session_id": "test-sid", "trigger": "manual"})
    assert holder["state"].get("pending_reinjection") is not True
    assert capsys.readouterr().out.strip() == ""


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
