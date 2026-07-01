"""verify_auto_handoff.py — Auto-Handoff 自動無損交接守門（Phase 1-3）.

守住 plans/wise-wobbling-gem.md 的不變式：
1. **PreCompact 自動 stub**：壓縮前 build_handoff_stub 寫入 resolve_staging_dir，設
   pending_handoff_emit + handoff_stub_path（核心保底，不依賴 token 量測）。
2. **stub 六區塊**：含 6 個區塊標題 + 客觀區塊自動填（branch/commit/modified）+ 主觀
   區塊 TODO 佔位；第一行為 /continue 選單摘要。
3. **pending_handoff_emit 生命週期**：PreCompact 設 → PostToolBatch 清（一次性）。
4. **Layer 3 合流**：pending_reinjection 與 pending_handoff_emit 同時 pending 時，兩段
   合進同一 additionalContext，不互搶。
5. **should_write_stub**：有手寫 next-phase*.md 則不覆蓋；自身 auto stub 可更新；無工作不寫。
6. **行為相容**：auto_handoff.enabled=false 不介入；既有壓縮還原 / idle early-exit 不變。
7. **Phase 2 Layer 1（Stop token 預警）**：estimate_context_usage proxy ratio 計算 + 無法
   量測回 0.0 + overhead 補償；token_warn_payload 門檻/一次性/disabled/純函式無副作用。
8. **Phase 3 Layer 4（SessionEnd 兜底）**：session 直接結束有工作且無手寫 handoff 時寫客觀
   stub（不設 pending_handoff_emit）；sessionend_fallback=false 不寫；尊重手寫；無工作不寫。

受控 tmp staging + monkeypatch state I/O + resolve_staging_dir + _git，不依賴磁碟/真實 git。
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
import handlers.post_tool_batch as ptb  # noqa: E402
import handlers.session_end as se  # noqa: E402
import wg_handoff as wh  # noqa: E402

STUB_NAME = "next-phase-auto.md"
SIX_BLOCKS = ["【前置脈絡】", "【已完成】", "【權威來源】",
              "【產出位置】", "【做法】", "【決策依據】"]


# ─── fixtures ────────────────────────────────────────────────────────────────


def _state(cwd="/proj", mod=None, injected=None):
    return {
        "session": {"id": "test-sid-123456789", "cwd": cwd},
        "phase": "working",
        "modified_files": mod if mod is not None else [{"path": "/proj/foo.py", "tool": "Edit"}],
        "accessed_files": [{"path": "/proj/bar.py"}],
        "knowledge_queue": ["待記 X 知識"],
        "injected_atoms": injected if injected is not None else ["alpha", "beta"],
        "topic_tracker": {"first_prompt_summary": "做 foo 重構"},
        "episodic_checkpoint_done": True,   # 跳過 pre_compact 的 episodic 生成
    }


def _setup(tmp_path, monkeypatch, state):
    """monkeypatch state I/O + resolve_staging_dir + _git。回 (holder, staging_dir)。"""
    staging = tmp_path / "_staging"
    staging.mkdir(parents=True, exist_ok=True)
    holder = {"state": state}

    def fake_ensure(sid, inp, cfg):
        return holder["state"]

    def fake_write(sid, st):
        holder["state"] = st

    for mod in (prc, ptb):
        monkeypatch.setattr(mod, "_ensure_state", fake_ensure, raising=False)
        monkeypatch.setattr(mod, "write_state", fake_write, raising=False)
    monkeypatch.setattr(prc, "resolve_staging_dir", lambda cwd: staging)
    return holder, staging


def _run(handler, input_data, config=None):
    with pytest.raises(SystemExit):
        handler(input_data, config or {})


@pytest.fixture(autouse=True)
def _stub_git(monkeypatch):
    """所有測試統一 stub git（branch/commit 回固定值，不依賴測試環境是否 git repo）。"""
    monkeypatch.setattr(wh, "_git", lambda args, cwd, timeout=1.5:
                        "feat-x" if "rev-parse" in args else "abc1234 做了某事")


# ─── 不變式 1：PreCompact 自動 stub ──────────────────────────────────────────


def test_precompact_writes_stub_and_sets_flag(tmp_path, monkeypatch, capsys):
    holder, staging = _setup(tmp_path, monkeypatch, _state())
    _run(prc.handle_pre_compact, {"session_id": "test-sid", "cwd": "/proj"})
    stub = staging / STUB_NAME
    assert stub.exists(), "PreCompact 未寫 stub"
    st = holder["state"]
    assert st.get("pending_handoff_emit") is True, "未設 pending_handoff_emit"
    assert st.get("handoff_stub_path") == str(stub)
    assert st.get("handoff_stub_at")


# ─── 不變式 2：stub 六區塊 + 客觀填入 + TODO 佔位 ────────────────────────────


def test_stub_has_six_blocks_objective_and_todo(tmp_path, monkeypatch):
    md = wh.build_handoff_stub(_state(), "/proj")
    for b in SIX_BLOCKS:
        assert b in md, f"stub 缺區塊 {b}"
    # 客觀區塊自動填
    assert "feat-x" in md, "未填 git branch"
    assert "abc1234" in md, "未填最近 commit"
    assert "/proj/foo.py" in md, "未填 modified 檔"
    assert "alpha" in md and "beta" in md, "未填 injected atom 名單"
    assert "/proj" in md, "未填專案根目錄"
    # 主觀區塊留 TODO
    assert "TODO(模型補全)" in md, "主觀區塊缺 TODO 佔位"
    assert md.count("TODO(模型補全)") >= 3, "應有 ≥3 個 TODO（why/做法/決策依據）"


def test_stub_first_line_is_continue_summary(tmp_path, monkeypatch):
    md = wh.build_handoff_stub(_state(), "/proj")
    first = md.lstrip().splitlines()[0]
    assert first.startswith("[續接]"), f"第一行非 /continue 選單摘要格式: {first}"


# ─── 不變式 3：pending_handoff_emit 生命週期 ─────────────────────────────────


def test_pending_handoff_emit_cleared_by_postbatch(tmp_path, monkeypatch, capsys):
    st = _state()
    st["pending_handoff_emit"] = True
    st["handoff_stub_path"] = "/proj/.claude/memory/_staging/next-phase-auto.md"
    holder, _ = _setup(tmp_path, monkeypatch, st)
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Read"}]})
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "Auto-Handoff" in ctx and "TODO(模型補全)" in ctx, "未注入補全提示"
    assert holder["state"].get("pending_handoff_emit") is False, "未清 flag（會重複注入）"


# ─── 不變式 4：Layer 3 與 pending_reinjection 合流 ───────────────────────────


def test_layer3_merges_with_reinjection(tmp_path, monkeypatch, capsys):
    st = _state()
    st["pending_reinjection"] = True
    st["pending_reinjection_blob"] = "[Atom:alpha]\nX 內文"
    st["pending_reinjection_atoms"] = ["alpha"]
    st["pending_handoff_emit"] = True
    st["handoff_stub_path"] = "/proj/_staging/next-phase-auto.md"
    holder, _ = _setup(tmp_path, monkeypatch, st)
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Bash"}]})
    ctx = json.loads(capsys.readouterr().out.strip())["hookSpecificOutput"]["additionalContext"]
    assert "[Atom:alpha]" in ctx, "合流後缺 atom 復原內文"
    assert "Auto-Handoff" in ctx, "合流後缺 handoff 提示"
    s = holder["state"]
    assert s.get("pending_reinjection") is False and s.get("pending_handoff_emit") is False


def test_layer3_handoff_only_no_reinjection(tmp_path, monkeypatch, capsys):
    st = _state()
    st["pending_handoff_emit"] = True
    st["handoff_stub_path"] = "/proj/_staging/next-phase-auto.md"
    holder, _ = _setup(tmp_path, monkeypatch, st)
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Read"}]})
    ctx = json.loads(capsys.readouterr().out.strip())["hookSpecificOutput"]["additionalContext"]
    assert "Auto-Handoff" in ctx
    assert "[Atom:" not in ctx, "無 reinjection 時不應有 atom 復原內文"


# ─── 不變式 5：should_write_stub ─────────────────────────────────────────────


def test_should_write_stub_respects_handwritten(tmp_path):
    staging = tmp_path / "_staging"
    staging.mkdir()
    (staging / "next-phase-myfeature.md").write_text("手寫 handoff", encoding="utf-8")
    assert wh.should_write_stub(staging, _state(), STUB_NAME) is False, \
        "有手寫 next-phase*.md 時不應覆蓋"


def test_should_write_stub_allows_auto_update(tmp_path):
    staging = tmp_path / "_staging"
    staging.mkdir()
    (staging / STUB_NAME).write_text("舊 auto stub", encoding="utf-8")
    assert wh.should_write_stub(staging, _state(), STUB_NAME) is True, \
        "僅自身 auto stub 應可更新"


def test_should_write_stub_no_work(tmp_path):
    staging = tmp_path / "_staging"
    staging.mkdir()
    assert wh.should_write_stub(staging, _state(mod=[]), STUB_NAME) is False, \
        "無 modified_files 不應寫 stub"


# ─── 不變式 6：行為相容 ──────────────────────────────────────────────────────


def test_disabled_no_stub(tmp_path, monkeypatch, capsys):
    holder, staging = _setup(tmp_path, monkeypatch, _state())
    _run(prc.handle_pre_compact, {"session_id": "test-sid", "cwd": "/proj"},
         {"auto_handoff": {"enabled": False}})
    assert not (staging / STUB_NAME).exists(), "disabled 時不應寫 stub"
    assert holder["state"].get("pending_handoff_emit") is not True


def test_disabled_postbatch_clears_flag_no_emit(tmp_path, monkeypatch, capsys):
    st = _state()
    st["pending_handoff_emit"] = True
    holder, _ = _setup(tmp_path, monkeypatch, st)
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Read"}]},
         {"auto_handoff": {"postbatch_emit": False}})
    assert capsys.readouterr().out.strip() == "", "postbatch_emit=false 不應注入"
    assert holder["state"].get("pending_handoff_emit") is False, "仍應清旗標（一次性）"


def test_idle_early_exit_unchanged(tmp_path, monkeypatch, capsys):
    holder, _ = _setup(tmp_path, monkeypatch, _state())  # 無任何 pending
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": []})
    assert capsys.readouterr().out.strip() == "", "idle PostToolBatch 不得有輸出（行為相容）"


def test_reinjection_only_still_works(tmp_path, monkeypatch, capsys):
    st = _state()
    st["pending_reinjection"] = True
    st["pending_reinjection_blob"] = "[Atom:alpha]\nX"
    st["pending_reinjection_atoms"] = ["alpha"]
    st["injected_atoms"] = []
    holder, _ = _setup(tmp_path, monkeypatch, st)
    _run(ptb.handle_post_tool_batch, {"session_id": "test-sid", "tool_calls": [{"name": "Edit"}]})
    ctx = json.loads(capsys.readouterr().out.strip())["hookSpecificOutput"]["additionalContext"]
    assert "[Atom:alpha]" in ctx, "既有壓縮還原回歸：應注入 atom 內文"
    assert "Auto-Handoff" not in ctx, "無 handoff pending 時不應有 handoff 提示"
    assert set(holder["state"].get("injected_atoms", [])) == {"alpha"}, "未 merge 回 injected_atoms"


# ─── Phase 2：estimate_context_usage（proxy 量測，僅觸發信號）─────────────────


def test_estimate_context_usage_ratio(tmp_path):
    """ratio = (_estimate_tokens(transcript 原文) + overhead) / window，自洽計算。"""
    from wg_core import _estimate_tokens
    text = "hello world 中文測試 " * 200
    t = tmp_path / "t.jsonl"
    t.write_text(text, encoding="utf-8")
    expected = (_estimate_tokens(text) + 5000) / 100000
    got = wh.estimate_context_usage(str(t), 100000, 5000)
    assert abs(got - expected) < 1e-9, f"ratio 計算錯：{got} != {expected}"


def test_estimate_context_usage_unmeasurable_returns_zero(tmp_path):
    """無法量測（None / 不存在 / window 非正）一律回 0.0，自然落門檻下不誤觸發。"""
    assert wh.estimate_context_usage(None, 200000, 15000) == 0.0
    assert wh.estimate_context_usage(str(tmp_path / "missing.jsonl"), 200000, 15000) == 0.0
    t = tmp_path / "z.jsonl"
    t.write_text("x", encoding="utf-8")
    assert wh.estimate_context_usage(str(t), 0, 15000) == 0.0, "window 非正應回 0"


def test_estimate_context_usage_overhead_compensates(tmp_path):
    """base_overhead 補 proxy 低估：補償量恰為 overhead/window。"""
    t = tmp_path / "t.jsonl"
    t.write_text("x", encoding="utf-8")
    r0 = wh.estimate_context_usage(str(t), 100000, 0)
    r1 = wh.estimate_context_usage(str(t), 100000, 20000)
    assert r1 > r0, "base_overhead 應拉高 ratio"
    assert abs((r1 - r0) - 0.2) < 1e-6, "補償量應 = overhead/window"


def _usage_transcript(tmp_path, totals):
    """寫一份每輪帶 message.usage 的 transcript（整數佔用塞 cache_read 即可）。"""
    import json as _json
    lines = []
    for n in totals:
        lines.append(_json.dumps({
            "type": "assistant",
            "message": {"role": "assistant", "usage": {
                "input_tokens": 0, "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": int(n), "output_tokens": 1,
            }},
        }))
    t = tmp_path / "u.jsonl"
    t.write_text("\n".join(lines), encoding="utf-8")
    return str(t)


def test_estimate_usage_based_uses_last_turn_over_window(tmp_path):
    """主路徑：分子 = 最近一輪真實 usage，分母 = 預設 1M；忽略 base_overhead。"""
    tr = _usage_transcript(tmp_path, [50_000, 120_000])
    got = wh.estimate_context_usage(tr, 1_000_000, 999_999)  # overhead 應被忽略
    assert abs(got - 0.12) < 1e-9, f"應為 120000/1M=0.12，得 {got}"


def test_estimate_usage_self_calibrates_to_1m(tmp_path):
    """usage 曾破 200k → 分母數學上必為 1M，即使 default_window 傳 200k 也不誤用。"""
    tr = _usage_transcript(tmp_path, [150_000, 250_000])
    got = wh.estimate_context_usage(tr, 200_000, 0)  # 故意給低 default
    assert abs(got - 0.25) < 1e-9, f"應自我校準成 250000/1M=0.25，得 {got}（誤用 200k 會得 1.25）"


def test_estimate_usage_below_200k_uses_default_window(tmp_path):
    """未破 200k → 無從反推，用 default_window（此處 1M）。"""
    tr = _usage_transcript(tmp_path, [80_000])
    assert abs(wh.estimate_context_usage(tr, 1_000_000, 0) - 0.08) < 1e-9


def test_estimate_usage_takes_precedence_over_charproxy(tmp_path):
    """有 usage 時走真實 token、不退 char-proxy（即使文字很長）。"""
    import json as _json
    line = _json.dumps({"type": "assistant", "message": {"role": "assistant",
            "usage": {"cache_read_input_tokens": 100_000}}})
    t = tmp_path / "mix.jsonl"
    t.write_text(line + "\n" + ("中文" * 50_000), encoding="utf-8")  # 長尾文字
    got = wh.estimate_context_usage(str(t), 1_000_000, 0)
    assert abs(got - 0.1) < 1e-9, f"應用 usage 100000/1M=0.1、非 char-proxy，得 {got}"


# ─── Phase 2：token_warn_payload（門檻 / 一次性 / disabled）───────────────────


def _ah_cfg(**over):
    ah = {
        "enabled": True, "token_warn": True, "token_warn_ratio": 0.85,
        "context_window_tokens": 200000, "context_base_overhead_tokens": 15000,
    }
    ah.update(over)
    return {"auto_handoff": ah}


def _transcript(tmp_path, text="x"):
    t = tmp_path / "tr.jsonl"
    t.write_text(text, encoding="utf-8")
    return str(t)


def test_token_warn_payload_above_threshold(tmp_path):
    # window=10k + overhead=9k → ratio≈0.9 > 0.85，即使 transcript 極小也達標
    cfg = _ah_cfg(context_window_tokens=10000, context_base_overhead_tokens=9000)
    out = wh.token_warn_payload({}, cfg, _transcript(tmp_path))
    assert out, "達門檻應回預警句"
    assert "Auto-Handoff" in out and "/handoff" in out, "預警句應引導主動 handoff"


def test_token_warn_payload_below_threshold(tmp_path):
    cfg = _ah_cfg(context_window_tokens=10_000_000, context_base_overhead_tokens=0)  # ratio≈0
    assert wh.token_warn_payload({}, cfg, _transcript(tmp_path)) is None, "未達門檻不應警"


def test_token_warn_payload_one_time(tmp_path):
    cfg = _ah_cfg(context_window_tokens=10000, context_base_overhead_tokens=9000)
    assert wh.token_warn_payload({"token_warn_emitted": True}, cfg, _transcript(tmp_path)) is None, \
        "已提醒過（一次性）不應再警"


def test_token_warn_payload_disabled(tmp_path):
    over = {"context_window_tokens": 10000, "context_base_overhead_tokens": 9000}
    tr = _transcript(tmp_path)
    assert wh.token_warn_payload({}, _ah_cfg(enabled=False, **over), tr) is None, \
        "auto_handoff.enabled=false 不應警"
    assert wh.token_warn_payload({}, _ah_cfg(token_warn=False, **over), tr) is None, \
        "token_warn=false 不應警"


def test_token_warn_payload_pure_no_side_effect(tmp_path):
    """純函式契約：不可自設 token_warn_emitted（旗標由 stop.py append 時才標）。"""
    cfg = _ah_cfg(context_window_tokens=10000, context_base_overhead_tokens=9000)
    st = {}
    wh.token_warn_payload(st, cfg, _transcript(tmp_path))
    assert "token_warn_emitted" not in st, "token_warn_payload 不應有副作用設旗標"


# ─── Phase 3：Layer 4 SessionEnd 兜底 ────────────────────────────────────────


def _setup_session_end(tmp_path, monkeypatch, state):
    """neutralize SessionEnd 重型協作者（worker/評估/episodic/conflict/索引/子程序），
    只留 Layer 4 邏輯與 state I/O。回 (holder, staging)。"""
    import types
    staging = tmp_path / "_staging"
    holder = {"state": state}
    monkeypatch.setattr(se, "_ensure_state", lambda sid, inp, cfg: holder["state"])
    monkeypatch.setattr(se, "write_state", lambda sid, st: holder.__setitem__("state", st))
    monkeypatch.setattr(se, "resolve_staging_dir", lambda cwd: staging)
    monkeypatch.setattr(se, "get_project_memory_dir", lambda cwd: None)
    monkeypatch.setattr(se, "_cleanup_old_states", lambda: None)
    monkeypatch.setattr(se, "_spawn_extract_worker", lambda ctx: 0)
    monkeypatch.setattr(se, "_maybe_spawn_user_extract_worker", lambda sid, st, cfg: False)
    monkeypatch.setattr(se, "_collect_iteration_metrics", lambda st: {})
    monkeypatch.setattr(se, "_detect_oscillation", lambda st, cfg: [])
    monkeypatch.setattr(se, "_save_oscillation_state", lambda x: None)
    monkeypatch.setattr(se, "_self_iterate_atoms", lambda st, cfg: {})
    monkeypatch.setattr(se, "_sweep_realm_auto_migrate", lambda cfg: [])
    monkeypatch.setattr(se, "_detect_atom_conflicts", lambda st, cfg: [])
    monkeypatch.setattr(se, "_trigger_incremental_index", lambda cfg: None)
    monkeypatch.setattr(se, "DOCDRIFT_AVAILABLE", False)
    monkeypatch.setattr(se, "WISDOM_AVAILABLE", False)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    return holder, staging


def test_sessionend_writes_stub_when_work(tmp_path, monkeypatch):
    """有未完成工作 + 無既有手寫 handoff + sessionend_fallback 預設開 → 寫客觀 stub。
    session 已結束、無 PostToolBatch 可消費 → 不設 pending_handoff_emit。"""
    holder, staging = _setup_session_end(tmp_path, monkeypatch, _state())
    _run(se.handle_session_end, {"session_id": "test-sid"}, {})
    stub = staging / STUB_NAME
    assert stub.exists(), "SessionEnd 兜底未寫 stub"
    body = stub.read_text(encoding="utf-8")
    assert "feat-x" in body and "TODO(模型補全)" in body, "stub 缺客觀填入 / TODO 佔位"
    st = holder["state"]
    assert st.get("handoff_stub_path") == str(stub)
    assert st.get("handoff_stub_at")
    assert st.get("pending_handoff_emit") is not True, "SessionEnd 不應設 pending_handoff_emit"


def test_sessionend_fallback_disabled_no_stub(tmp_path, monkeypatch):
    holder, staging = _setup_session_end(tmp_path, monkeypatch, _state())
    _run(se.handle_session_end, {"session_id": "test-sid"},
         {"auto_handoff": {"sessionend_fallback": False}})
    assert not (staging / STUB_NAME).exists(), "sessionend_fallback=false 不應寫 stub"


def test_sessionend_respects_handwritten(tmp_path, monkeypatch):
    state = _state()
    holder, staging = _setup_session_end(tmp_path, monkeypatch, state)
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "next-phase-myfeature.md").write_text("手寫 handoff", encoding="utf-8")
    _run(se.handle_session_end, {"session_id": "test-sid"}, {})
    assert not (staging / STUB_NAME).exists(), "有手寫 next-phase*.md 時不應自動補 stub"


def test_sessionend_no_work_no_stub(tmp_path, monkeypatch):
    holder, staging = _setup_session_end(tmp_path, monkeypatch, _state(mod=[]))
    _run(se.handle_session_end, {"session_id": "test-sid"}, {})
    assert not (staging / STUB_NAME).exists(), "無 modified_files 不應寫 stub"
