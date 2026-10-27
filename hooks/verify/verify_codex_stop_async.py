"""verify_codex_stop_async.py — 收尾時的 Codex 裁判改背景（Stop 不等、不 block）。

契約：
1. AI 宣稱完成的那一刻，Stop hook 不同步呼叫裁判（assessor.run_assessment 不得在 hook 行程內跑），
   只起背景 audit 子程序後立即放行。
2. 不論裁判結果或收尾自檢（heuristics）嚴重度多高，Stop 永不回 decision=block；自檢結果落成
   assessment 檔，下一則再附。
3. 下一則 UserPromptSubmit：驗收裁判／收尾自檢結果一律附一行；fail 且 severity 達
   max_inject_severity 才附完整說明（摘要＋事證＋建議）。
4. codex_companion.enabled=false 整段關；v6 關時收尾不叫裁判，照舊。
怎麼跑：python -X utf8 -m pytest -q -p no:cacheprovider hooks/verify/verify_codex_stop_async.py
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
COMPANION_DIR = CLAUDE_DIR / "tools" / "codex-companion"
for _p in (HOOKS_DIR, COMPANION_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import acceptance as acc  # noqa: E402
import assessor  # noqa: E402
import codex_companion as cc  # noqa: E402
import heuristics  # noqa: E402
import state as companion_state  # noqa: E402

SID = "test-stop-async-0001"
CFG = {
    "enabled": True,
    "max_audits_per_session": 30,
    "score_threshold": 99,            # turn_audit 不觸發，只看驗收裁判那條路
    "silent_advisory": False,         # 舊碼在這個設定下會 block
    "max_inject_severity": "high",
    "soft_gate": {"completion_evidence": True, "block_severity_threshold": "high"},
    # enforce 鍵已無作用（舊碼讀到 true 會在 Stop 同步審）；留著當回歸守衛
    "acceptance_review": {"enabled": True, "max_per_spec": 2, "enforce": True},
}
CLAIM = {"session_id": SID, "last_assistant_message": "全部做完，已完成。"}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """隔離 workflow／sidecar／專案目錄；本 session 唯一 open 規格＋本回合有 Edit；v6 開。"""
    workflow = tmp_path / "workflow"
    sidecar = workflow / "acceptance-spec"
    sidecar.mkdir(parents=True)
    proj = tmp_path / "proj"
    (proj / ".claude" / "verify").mkdir(parents=True)
    (proj / ".claude" / "verify" / "acceptance-task-a.md").write_text(
        f"---\ntask_slug: task-a\nsession_id: {SID}\ncreated_at: 2026-10-27\n"
        "source: plan\nstatus: open\n---\n## 必須發生\n- 做 A\n## 驗證指令\n- pytest -q\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(acc, "WORKFLOW_DIR", workflow)
    monkeypatch.setattr(acc, "SIDECAR_DIR", sidecar)
    monkeypatch.setattr(acc, "AUDIT_JSONL", workflow / "acceptance-audit.jsonl")
    monkeypatch.setattr(companion_state, "WORKFLOW_DIR", workflow)
    monkeypatch.setattr(cc, "WORKFLOW_DIR", workflow)
    monkeypatch.setenv("WG_V6", "1")
    companion_state.ensure_state(SID, str(proj))
    companion_state.append_event(SID, {"tool": "Edit", "file": "x.py"})

    spawned: list = []
    monkeypatch.setattr(cc, "_spawn_audit_subprocess", lambda td: spawned.append(td))

    def _never_sync(*a, **k):
        raise AssertionError("Stop hook 行程內不得同步呼叫裁判")

    monkeypatch.setattr(assessor, "run_assessment", _never_sync)
    assert not hasattr(cc, "_output_block"), "codex_companion 不該再有 block 出口"
    return {"workflow": workflow, "proj": proj, "spawned": spawned}


def _stop(capsys, cfg=CFG) -> tuple[int, str, float]:
    t0 = time.monotonic()
    with pytest.raises(SystemExit) as ex:
        cc.handle_stop(dict(CLAIM), cfg)
    return int(ex.value.code or 0), capsys.readouterr().out, time.monotonic() - t0


def _prompt(capsys, cfg=CFG) -> str:
    with pytest.raises(SystemExit):
        cc.handle_user_prompt_submit({"session_id": SID, "prompt": "下一題"}, cfg)
    out = capsys.readouterr().out.strip()
    return json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""


# ─── 1. Stop 不等 ────────────────────────────────────────────────────────────


def test_stop_does_not_wait_for_assessment(world, capsys):
    code, out, elapsed = _stop(capsys)
    assert code == 0 and "block" not in out
    assert elapsed < 2.0, f"Stop 等了 {elapsed:.1f}s"
    kinds = [td["assessment_type"] for td in world["spawned"]]
    assert kinds == ["acceptance_review"], kinds          # 背景審起了、且只起一次
    assert world["spawned"][0]["context"]["trigger"] == "stop_claim"


# ─── 2. Stop 永不 block ──────────────────────────────────────────────────────


def test_stop_never_blocks_on_assessment_result(world, monkeypatch, capsys):
    """收尾自檢命中 high 也只落說明檔，不 block。"""
    high = [heuristics.HeuristicResult("no_verification", True, "high", "改了檔沒跑測試")]
    monkeypatch.setattr(heuristics, "triggered_results", lambda *a, **k: high)
    code, out, _ = _stop(capsys)
    assert code == 0 and "block" not in out
    notes = list(world["workflow"].glob(f"companion-assessment-{SID}-t*-completion_evidence.json"))
    assert len(notes) == 1
    data = json.loads(notes[0].read_text(encoding="utf-8"))
    assert data["assessment"]["severity"] == "high"
    assert "改了檔沒跑測試" in data["assessment"]["evidence"]


# ─── 3./4. 下一則注入：一行 vs 完整說明 ─────────────────────────────────────


def test_result_injected_one_line_next_prompt(world, capsys):
    companion_state.write_assessment(SID, 3, "acceptance_review", {
        "verdict": "pass", "status": "ok", "severity": "low", "delivery": "ignore",
        "summary": "驗收清單逐條均有對應證據", "corrective_prompt": "",
    })
    ctx = _prompt(capsys)
    assert ctx, "pass 也要一行回報"
    assert "\n" not in ctx
    assert "驗收裁判" in ctx and "pass" in ctx and "t3" in ctx
    assert _prompt(capsys) == ""                           # 注過就標掉，不重複


def test_high_severity_gets_full_note_next_prompt(world, capsys):
    companion_state.write_assessment(SID, 4, "acceptance_review", {
        "verdict": "fail", "status": "needs_followup", "severity": "high", "delivery": "inject",
        "summary": "驗收未過：1 項未達標",
        "evidence": "- 做 A｜事證：diff 無 A｜沒做",
        "corrective_prompt": "請自行判斷是否屬實：真的漏做就補。",
    })
    ctx = _prompt(capsys)
    lines = ctx.splitlines()
    assert len(lines) >= 4, ctx
    assert "severity=high" in lines[0] and "摘要：" in ctx and "事證：" in ctx and "建議：" in ctx
    assert "diff 無 A" in ctx


def test_medium_fail_stays_one_line(world, capsys):
    companion_state.write_assessment(SID, 5, "acceptance_review", {
        "verdict": "fail", "status": "needs_followup", "severity": "medium", "delivery": "inject",
        "summary": "驗收未過：1 項未達標", "evidence": "- c｜事證：e｜x",
        "corrective_prompt": "請自行判斷。",
    })
    ctx = _prompt(capsys)
    assert ctx and "\n" not in ctx and "fail" in ctx


# ─── 5./6. 開關照舊 ──────────────────────────────────────────────────────────


def test_disabled_passes_through(world, monkeypatch, capsys):
    monkeypatch.setattr(cc, "_load_config", lambda: {"enabled": False})
    monkeypatch.setattr(cc, "HANDLERS", {"Stop": lambda *a: pytest.fail("enabled=false 不得進 handler")})
    payload = json.dumps({"hook_event_name": "Stop", **CLAIM}).encode("utf-8")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload)))
    with pytest.raises(SystemExit) as ex:
        cc.main()
    assert int(ex.value.code or 0) == 0
    assert capsys.readouterr().out == ""


def test_v6_off_unchanged_path(world, monkeypatch, capsys):
    monkeypatch.setenv("WG_V6", "0")
    calls: list = []
    monkeypatch.setattr(cc, "_maybe_spawn_acceptance_review", lambda *a, **k: calls.append(a))
    code, out, _ = _stop(capsys)
    assert code == 0 and out == ""
    assert calls == [] and world["spawned"] == []
