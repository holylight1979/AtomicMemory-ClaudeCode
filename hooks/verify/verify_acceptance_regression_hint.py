"""verify_acceptance_regression_hint.py — 迴歸累積提示（驗收真命中 → 補測試/落 atom）

覆蓋驗收：
  H1: 本 session fail/high 判定 → 提示文含 (a)(b) 與 task_slug；計數正確
  H2: 過濾——他 session / severity<high / verdict≠fail 皆不觸發
  H3: 一次性——acceptance_hint_emitted 已設 → None
  H4: config enabled:false → None；audit 檔不存在 → None
  H5: fail-open——損毀 jsonl 行跳過不炸；混雜損毀行仍能命中有效行
  H6: 接線——_piggyback 附掛提示並設 acceptance_hint_emitted 旗標
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import handlers.stop as stop_mod  # noqa: E402
from handlers.stop import _acceptance_regression_hint  # noqa: E402

SID = "sess-hint-test"


def _audit(session_id=SID, verdict="fail", severity="high", slug="demo-task"):
    return {
        "session_id": session_id, "verdict": verdict, "severity": severity,
        "task_slug": slug, "spec_path": f".claude/verify/acceptance-{slug}.md",
    }


def _write_jsonl(tmp: Path, records, raw_extra=""):
    tmp.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
    if raw_extra:
        body = raw_extra + "\n" + body
    (tmp / "acceptance-audit.jsonl").write_text(body + "\n", encoding="utf-8")


def _run(tmp: Path, records, state=None, config=None, raw_extra=""):
    _write_jsonl(tmp, records, raw_extra=raw_extra)
    orig = stop_mod.WORKFLOW_DIR
    stop_mod.WORKFLOW_DIR = tmp
    try:
        return _acceptance_regression_hint(state or {}, SID, config or {})
    finally:
        stop_mod.WORKFLOW_DIR = orig


# ── H1：真命中觸發 ────────────────────────────────────────────────


def test_fail_high_fires_with_slug_and_options(tmp_path):
    out = _run(tmp_path, [_audit(), _audit(slug="demo-task")])
    assert out is not None
    assert "2 筆" in out
    assert "demo-task" in out
    assert "(a)" in out and "(b)" in out
    assert "非強制" in out


def test_slug_fallback_to_spec_stem(tmp_path):
    rec = _audit()
    rec["task_slug"] = ""
    out = _run(tmp_path, [rec])
    assert out is not None
    assert "acceptance-demo-task" in out


# ── H2：過濾 ─────────────────────────────────────────────────────


def test_other_session_not_counted(tmp_path):
    assert _run(tmp_path, [_audit(session_id="other-sess")]) is None


def test_medium_severity_not_counted(tmp_path):
    assert _run(tmp_path, [_audit(severity="medium")]) is None


def test_pass_uncertain_not_counted(tmp_path):
    assert _run(
        tmp_path, [_audit(verdict="pass"), _audit(verdict="uncertain")]
    ) is None


# ── H3：一次性 ───────────────────────────────────────────────────


def test_one_shot_flag_suppresses(tmp_path):
    out = _run(tmp_path, [_audit()], state={"acceptance_hint_emitted": True})
    assert out is None


# ── H4：開關與缺檔 ───────────────────────────────────────────────


def test_disabled_config(tmp_path):
    out = _run(
        tmp_path, [_audit()],
        config={"acceptance_regression_hint": {"enabled": False}},
    )
    assert out is None


def test_missing_audit_file(tmp_path):
    orig = stop_mod.WORKFLOW_DIR
    stop_mod.WORKFLOW_DIR = tmp_path / "nonexistent"
    try:
        assert _acceptance_regression_hint({}, SID, {}) is None
    finally:
        stop_mod.WORKFLOW_DIR = orig


# ── H5：fail-open ────────────────────────────────────────────────


def test_corrupt_lines_skipped_valid_still_hit(tmp_path):
    out = _run(tmp_path, [_audit()], raw_extra=f"{{broken json {SID}")
    assert out is not None
    assert "1 筆" in out


def test_corrupt_only_returns_none(tmp_path):
    out = _run(tmp_path, [], raw_extra=f"not-json {SID}")
    assert out is None


# ── H6：_piggyback 接線（源碼結構檢核，比照 AtomAudit wiring 慣例）──


def test_piggyback_wiring():
    src = Path(stop_mod.__file__).read_text(encoding="utf-8")
    assert "_accept_hint = _acceptance_regression_hint(" in src
    assert 'state["acceptance_hint_emitted"] = True' in src
    # 提示只走 piggyback，不得有獨立 output_block 呼叫掛在 hint 上
    assert "output_block(_accept_hint" not in src


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
