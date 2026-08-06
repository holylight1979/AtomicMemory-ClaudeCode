"""verify_acceptance_review.py — Phase 2 影子驗收裁判契約。

1. 綁定四分流（INV-CASE-BINDING-OR-UNCERTAIN）：
   bound / ambiguous_multiple / other_session / none；綁不到絕不猜「最新一份」
2. 案卷 diff 採樣（INV-EVIDENCE-PIPE-HONESTY）：頭尾採樣必附標記、
   超預算檔案列「未採樣清單」、untracked 新檔入卷
3. verdict 映射：pass/fail/uncertain → 既有 assessment 欄位；
   binding≠bound 程式化強制 uncertain；fail 無證據 problem 降 uncertain
4. Q8 配額分桶：acceptance_review 有保底名額也有上限，與既有審查互不餓死
5. 稽核落盤：jsonl append + human_label 預留 + Q5 promotion_stats
6. hook 觸發：spec 標 done 偵測、bound → spawn、unbound → 落 uncertain 不 spawn
7. 影子紅線：任何路徑不產生 block decision
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
COMPANION_DIR = CLAUDE_DIR / "tools" / "codex-companion"
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(COMPANION_DIR))

import acceptance as acc  # noqa: E402
import assessor  # noqa: E402
import codex_companion as cc  # noqa: E402
import state as companion_state  # noqa: E402

SID = "test-acc-session"


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """隔離 workflow / sidecar / audit jsonl / 專案目錄。"""
    workflow = tmp_path / "workflow"
    sidecar = workflow / "acceptance-spec"
    sidecar.mkdir(parents=True)
    proj = tmp_path / "proj"
    (proj / ".claude" / "verify").mkdir(parents=True)
    monkeypatch.setattr(acc, "WORKFLOW_DIR", workflow)
    monkeypatch.setattr(acc, "SIDECAR_DIR", sidecar)
    monkeypatch.setattr(acc, "AUDIT_JSONL", workflow / "acceptance-audit.jsonl")
    monkeypatch.setattr(companion_state, "WORKFLOW_DIR", workflow)
    monkeypatch.setattr(cc, "WORKFLOW_DIR", workflow)
    return {"workflow": workflow, "sidecar": sidecar, "proj": proj}


def _write_spec(proj: Path, name: str, sid: str = SID, status: str = "open") -> Path:
    p = proj / ".claude" / "verify" / f"acceptance-{name}.md"
    p.write_text(
        f"---\ntask_slug: {name}\nsession_id: {sid}\ncreated_at: 2026-08-06\n"
        f"source: plan\nstatus: {status}\n---\n"
        "## 必須發生\n- 做 A\n## 禁止發生\n- 動 B\n## 驗證指令\n- pytest -q\n",
        encoding="utf-8",
    )
    return p


# ─── 1. 綁定四分流 ────────────────────────────────────────────────────────────


def test_binding_bound_unique_open(sandbox):
    _write_spec(sandbox["proj"], "task-a")
    info = acc.resolve_binding(SID, str(sandbox["proj"]))
    assert info["binding"] == acc.BINDING_BOUND
    assert info["task_slug"] == "task-a"
    assert info["spec_path"].endswith("acceptance-task-a.md")


def test_binding_ambiguous_multiple_open(sandbox):
    _write_spec(sandbox["proj"], "task-a")
    _write_spec(sandbox["proj"], "task-b")
    info = acc.resolve_binding(SID, str(sandbox["proj"]))
    assert info["binding"] == acc.BINDING_AMBIGUOUS
    assert info["spec_path"] == ""
    assert "task-a" in info["uncertain_reason"] and "task-b" in info["uncertain_reason"]


def test_binding_other_session_only(sandbox):
    _write_spec(sandbox["proj"], "task-x", sid="another-session")
    info = acc.resolve_binding(SID, str(sandbox["proj"]))
    assert info["binding"] == acc.BINDING_OTHER_SESSION
    assert info["spec_path"] == ""


def test_binding_none_when_no_open_spec(sandbox):
    _write_spec(sandbox["proj"], "task-done", status="done")  # done 不算活規格
    info = acc.resolve_binding(SID, str(sandbox["proj"]))
    assert info["binding"] == acc.BINDING_NONE


def test_binding_bound_ignores_done_sibling(sandbox):
    _write_spec(sandbox["proj"], "task-open")
    _write_spec(sandbox["proj"], "task-old", status="done")
    info = acc.resolve_binding(SID, str(sandbox["proj"]))
    assert info["binding"] == acc.BINDING_BOUND
    assert "task-open" in info["spec_path"]


def test_binding_sidecar_path_counted_once(sandbox):
    """sidecar 記過的路徑與目錄掃描重複 → 去重，不得誤判 ambiguous。"""
    p = _write_spec(sandbox["proj"], "task-a")
    (sandbox["sidecar"] / f"{SID}.json").write_text(
        json.dumps({"spec_paths": [str(p).replace("\\", "/")]}), encoding="utf-8"
    )
    info = acc.resolve_binding(SID, str(sandbox["proj"]))
    assert info["binding"] == acc.BINDING_BOUND


def test_frontmatter_parse():
    fm = acc.parse_frontmatter("---\ntask_slug: x\nstatus: open\n---\nbody")
    assert fm == {"task_slug": "x", "status": "open"}
    assert acc.parse_frontmatter("no frontmatter") == {}


# ─── 2. diff 採樣與截斷標記 ───────────────────────────────────────────────────


def test_sample_marks_truncation():
    text = "A" * 3000
    out = acc._sample(text, 1000, 300, "測試段")
    assert "中段省略" in out and "3000 字" in out
    assert out.startswith("A" * 100) and out.endswith("A" * 100)
    # 不超預算 → 原文返回，零標記
    assert acc._sample("short", 1000, 300, "x") == "short"


def test_split_diff_by_file():
    diff = (
        "diff --git a/f1.py b/f1.py\n@@ -1 +1 @@\n-old\n+new\n"
        "diff --git a/f2.py b/f2.py\n@@ -2 +2 @@\n-x\n+y\n"
    )
    chunks = acc._split_diff_by_file(diff)
    assert [c[0] for c in chunks] == ["f1.py", "f2.py"]
    assert "+new" in chunks[0][1] and "+y" in chunks[1][1]


@pytest.fixture()
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
            + list(args),
            check=True, capture_output=True,
        )

    git("init", "-q")
    (repo / "a.py").write_text("line1\n" * 5, encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "init")
    return repo


def test_diff_digest_tracked_untracked_and_marks(git_repo):
    (git_repo / "a.py").write_text("changed\n" * 5, encoding="utf-8")
    (git_repo / "new_file.py").write_text("NEWCONTENT\n" * 3, encoding="utf-8")
    digest, truncated = acc.collect_diff_digest(str(git_repo))
    assert "變更檔案清單" in digest and "a.py" in digest
    assert "+changed" in digest                      # 逐檔內容真的入卷
    assert "new_file.py（新增檔）" in digest          # untracked 不漏
    assert "NEWCONTENT" in digest


def test_diff_digest_budget_overflow_lists_skipped(git_repo, monkeypatch):
    (git_repo / "a.py").write_text("x\n" * 400, encoding="utf-8")
    (git_repo / "b.py").write_text("orig\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(git_repo), "add", "b.py"], check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "-C", str(git_repo), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-qm", "add b"], check=True, capture_output=True)
    (git_repo / "b.py").write_text("changed-b\n", encoding="utf-8")
    monkeypatch.setattr(acc, "DIFF_BUDGET_CHARS", 50)  # 逼出超預算
    digest, truncated = acc.collect_diff_digest(str(git_repo))
    assert truncated
    assert "未採樣的變更檔案" in digest
    assert "勿因未見內容就判定沒做" in digest


def test_diff_digest_no_cwd_says_so():
    digest, truncated = acc.collect_diff_digest("")
    assert truncated and "無法取得工作目錄" in digest


def test_verification_evidence_includes_output():
    trace = [
        {"tool": "Bash", "input": "python -m pytest hooks/verify -q",
         "output_summary": "stdout: 953 passed"},
        {"tool": "Bash", "input": "ls -la", "output_summary": "stdout: files"},
    ]
    out = acc.collect_verification_evidence(trace)
    assert "pytest" in out and "953 passed" in out
    assert "ls -la" not in out
    # 空 trace → in-band 說明非空字串
    assert "找不到" in acc.collect_verification_evidence([])


# ─── 3. verdict 映射 ─────────────────────────────────────────────────────────


def test_map_pass():
    r = assessor.map_acceptance_verdict({"verdict": "pass", "score": 10})
    assert r["status"] == "ok" and r["delivery"] == "ignore"
    assert r["problems"] == []


def test_map_fail_with_evidence_injects_advisory():
    r = assessor.map_acceptance_verdict({
        "verdict": "fail", "score": 4, "severity": "medium",
        "problems": [{"criterion": "做 A", "evidence": "diff 無 A 相關變更",
                      "explanation": "沒做"}],
    })
    assert r["status"] == "needs_followup" and r["delivery"] == "inject"
    assert "不阻斷收尾" in r["corrective_prompt"]     # 影子模式明示
    assert "diff 無 A 相關變更" in r["evidence"]


def test_map_fail_without_evidence_degrades_to_uncertain():
    """扣分必引證據：無 evidence 的 problem 全被濾掉 → fail 降 uncertain。"""
    r = assessor.map_acceptance_verdict({
        "verdict": "fail",
        "problems": [{"criterion": "做 A", "evidence": "", "explanation": "感覺沒做"}],
    })
    assert r["verdict"] == "uncertain"
    assert r["delivery"] == "ignore"


def test_map_unbound_forces_uncertain_regardless_of_verdict():
    """INV-CASE-BINDING-OR-UNCERTAIN 程式化執行點。"""
    for b in (acc.BINDING_AMBIGUOUS, acc.BINDING_OTHER_SESSION, acc.BINDING_NONE):
        r = assessor.map_acceptance_verdict(
            {"verdict": "fail", "problems": [
                {"criterion": "x", "evidence": "y", "explanation": "z"}]},
            binding=b, binding_reason="綁不到",
        )
        assert r["verdict"] == "uncertain"
        assert r["delivery"] == "ignore"
        assert r["uncertain_reason"] == "綁不到"


def test_map_invalid_verdict_is_uncertain():
    r = assessor.map_acceptance_verdict({"status": "ok"})  # 舊 schema 誤回
    assert r["verdict"] == "uncertain"


def test_judge_failure_maps_to_uncertain(monkeypatch, sandbox):
    """裁判逾時/空回 → uncertain 揭露，不靜默通過（INV-JUDGE-FAILURE-IS-DISCLOSE）。"""
    monkeypatch.setattr(
        assessor, "_run_codex_with_retry", lambda *a, **k: ("", "timeout after 60s", 2)
    )
    spec = _write_spec(sandbox["proj"], "task-a")
    result = assessor.run_assessment(
        "acceptance_review", SID, [], str(sandbox["proj"]),
        {"spec_path": str(spec), "binding": "bound", "turn_index": 3},
        {"codex_binary": "nonexistent"},
    )
    assert result["verdict"] == "uncertain"
    assert result["notify_next_turn"] is True
    assert "timeout" in result["uncertain_reason"]


# ─── 4. Q8 配額分桶 ──────────────────────────────────────────────────────────

_QCFG = {"audit_quota": {"acceptance_review_min": 6, "acceptance_review_max": 8}}


def _seed_counts(total: int, acc_used: int):
    companion_state.write_state(SID, {
        **companion_state.new_state(SID, ""),
        "assessments_requested": total,
        "assessments_by_type": {"acceptance_review": acc_used,
                                "turn_audit": total - acc_used},
    })


def test_quota_acceptance_capped_at_max(sandbox):
    _seed_counts(total=10, acc_used=8)
    assert not cc._within_audit_cap(SID, 30, _QCFG, "acceptance_review")
    _seed_counts(total=10, acc_used=7)
    assert cc._within_audit_cap(SID, 30, _QCFG, "acceptance_review")


def test_quota_others_reserve_min_for_acceptance(sandbox):
    # 其他審查用滿 24（=30-6）→ 停；acceptance 仍有名額
    _seed_counts(total=24, acc_used=0)
    assert not cc._within_audit_cap(SID, 30, _QCFG, "turn_audit")
    assert cc._within_audit_cap(SID, 30, _QCFG, "acceptance_review")


def test_quota_total_cap_still_absolute(sandbox):
    _seed_counts(total=30, acc_used=5)
    assert not cc._within_audit_cap(SID, 30, _QCFG, "acceptance_review")
    assert not cc._within_audit_cap(SID, 30, _QCFG, "turn_audit")


# ─── 5. 稽核落盤 + Q5 統計 ───────────────────────────────────────────────────


def test_append_and_read_audit(sandbox):
    acc.append_audit({"session_id": SID, "verdict": "fail", "problems_count": 1})
    acc.append_audit({"session_id": SID, "verdict": "pass"})
    recs = acc.read_audits()
    assert len(recs) == 2 and recs[0]["verdict"] == "pass"  # 新到舊
    assert recs[1]["human_label"] is None                   # 標註欄預留


def test_promotion_stats_thresholds():
    def mk(verdict, label=None):
        return {"verdict": verdict, "human_label": label}

    # 20 筆、fail 全標 true_hit、uncertain 4 筆（20%）→ ready
    recs = ([mk("pass")] * 10 + [mk("fail", "true_hit")] * 6 + [mk("uncertain")] * 4)
    s = acc.promotion_stats(recs)
    assert s["samples"] == 20 and s["precision"] == 1.0
    assert s["promotion_ready"] and not s["kill_switch"]

    # 未標註的 fail 不計入 precision，也不 ready
    s2 = acc.promotion_stats([mk("pass")] * 14 + [mk("fail")] * 6)
    assert s2["precision"] is None and not s2["promotion_ready"]
    assert s2["unlabeled_fails"] == 6

    # 標註後 precision < 50%（≥10 筆標註）→ 殺閘
    s3 = acc.promotion_stats(
        [mk("fail", "false_alarm")] * 6 + [mk("fail", "true_hit")] * 4
        + [mk("pass")] * 10
    )
    assert s3["kill_switch"]


# ─── 6. hook 觸發 ────────────────────────────────────────────────────────────


def test_spec_marked_done_detection():
    spec = "D:/p/.claude/verify/acceptance-t.md"
    assert cc._spec_marked_done(
        "Write", spec, {"content": "---\nstatus: done\n---\n## ok"})
    assert cc._spec_marked_done("Edit", spec, {"new_string": "status: done"})
    assert not cc._spec_marked_done(
        "Write", spec, {"content": "---\nstatus: open\n---"})
    assert not cc._spec_marked_done(
        "Write", "D:/p/other.md", {"content": "status: done"})
    assert not cc._spec_marked_done("Read", spec, {"content": "status: done"})


def test_bound_spawns_audit_with_binding_context(sandbox, monkeypatch):
    _write_spec(sandbox["proj"], "task-a")
    companion_state.ensure_state(SID, str(sandbox["proj"]))
    spawned = []
    monkeypatch.setattr(cc, "_spawn_audit_subprocess", spawned.append)
    cc._maybe_spawn_acceptance_review(
        SID, 5, str(sandbox["proj"]),
        {"max_audits_per_session": 30, **_QCFG}, "stop_claim",
    )
    assert len(spawned) == 1
    ctx = spawned[0]["context"]
    assert spawned[0]["assessment_type"] == "acceptance_review"
    assert ctx["binding"] == "bound" and ctx["trigger"] == "stop_claim"
    assert ctx["spec_path"].endswith("acceptance-task-a.md")
    # per-type / per-spec 計數已累加
    st = companion_state.read_state(SID)
    assert st["assessments_by_type"]["acceptance_review"] == 1
    assert list(st["acceptance_reviews"].values()) == [1]


def test_ambiguous_writes_uncertain_audit_no_spawn(sandbox, monkeypatch):
    _write_spec(sandbox["proj"], "task-a")
    _write_spec(sandbox["proj"], "task-b")
    companion_state.ensure_state(SID, str(sandbox["proj"]))
    spawned = []
    monkeypatch.setattr(cc, "_spawn_audit_subprocess", spawned.append)
    cc._maybe_spawn_acceptance_review(
        SID, 5, str(sandbox["proj"]), {"max_audits_per_session": 30}, "stop_claim",
    )
    assert spawned == []                       # 不猜最新一份、不發審計
    recs = acc.read_audits()
    assert len(recs) == 1
    assert recs[0]["verdict"] == "uncertain"
    assert recs[0]["binding"] == acc.BINDING_AMBIGUOUS


def test_binding_none_silent_no_audit_noise(sandbox, monkeypatch):
    companion_state.ensure_state(SID, str(sandbox["proj"]))
    spawned = []
    monkeypatch.setattr(cc, "_spawn_audit_subprocess", spawned.append)
    cc._maybe_spawn_acceptance_review(
        SID, 5, str(sandbox["proj"]), {"max_audits_per_session": 30}, "stop_claim",
    )
    assert spawned == [] and acc.read_audits() == []


def test_spec_done_hint_binds_despite_status_done(sandbox, monkeypatch):
    """spec_done 觸發：規格檔當下已是 done（非 open），必須經 hint 直接綁定，
    不得因 open 掃描掃不到而靜默流失（審過的死路 bug 回歸測試）。"""
    spec = _write_spec(sandbox["proj"], "task-a", status="done")
    companion_state.ensure_state(SID, str(sandbox["proj"]))
    spawned = []
    monkeypatch.setattr(cc, "_spawn_audit_subprocess", spawned.append)
    cc._maybe_spawn_acceptance_review(
        SID, 5, str(sandbox["proj"]), {"max_audits_per_session": 30},
        "spec_done", spec_path_hint=str(spec),
    )
    assert len(spawned) == 1
    assert spawned[0]["context"]["binding"] == "bound"
    assert spawned[0]["context"]["trigger"] == "spec_done"


def test_spec_done_hint_other_session_uncertain(sandbox, monkeypatch):
    spec = _write_spec(sandbox["proj"], "task-x", sid="another", status="done")
    companion_state.ensure_state(SID, str(sandbox["proj"]))
    spawned = []
    monkeypatch.setattr(cc, "_spawn_audit_subprocess", spawned.append)
    cc._maybe_spawn_acceptance_review(
        SID, 5, str(sandbox["proj"]), {"max_audits_per_session": 30},
        "spec_done", spec_path_hint=str(spec),
    )
    assert spawned == []
    recs = acc.read_audits()
    assert len(recs) == 1 and recs[0]["verdict"] == "uncertain"
    assert recs[0]["binding"] == acc.BINDING_OTHER_SESSION


def test_read_spec_done_fallback(sandbox):
    """audit 子程序讀檔時規格可能已移入 done/ → 退 done/ 同名檔，不退化 uncertain。"""
    spec = _write_spec(sandbox["proj"], "task-a", status="done")
    done_dir = spec.parent / "done"
    done_dir.mkdir()
    moved = done_dir / spec.name
    spec.replace(moved)
    fm, text = acc.read_spec_with_done_fallback(str(spec))  # 用原路徑
    assert fm.get("task_slug") == "task-a" and "必須發生" in text


def test_per_spec_review_cap(sandbox, monkeypatch):
    _write_spec(sandbox["proj"], "task-a")
    companion_state.ensure_state(SID, str(sandbox["proj"]))
    spawned = []
    monkeypatch.setattr(cc, "_spawn_audit_subprocess", spawned.append)
    cfg = {"max_audits_per_session": 30, "acceptance_review": {"max_per_spec": 2}}
    for turn in (5, 6, 7):
        cc._maybe_spawn_acceptance_review(
            SID, turn, str(sandbox["proj"]), cfg, "stop_claim")
    assert len(spawned) == 2  # 第 3 次撞 per-spec 上限


# ─── 7. 影子紅線：不產生 block ────────────────────────────────────────────────


def test_acceptance_prompt_has_honesty_rules(sandbox):
    """案卷模板自帶「只憑案卷/證據不足回 uncertain/採樣截斷非缺漏」紀律。"""
    spec = _write_spec(sandbox["proj"], "task-a")
    prompt = assessor.build_prompt(
        "acceptance_review", [], str(sandbox["proj"]),
        {"spec_path": str(spec), "diff_digest": "### 變更檔案清單\nx", "turn_index": 1},
    )
    for token in ("只憑案卷", "uncertain", "不是文件缺漏", "做 A", "沒有 BLOCK 權"):
        assert token in prompt


def test_no_block_in_any_acceptance_mapping():
    """影子模式窮舉：所有 verdict × binding 組合，映射結果永無 block decision。"""
    for verdict in ("pass", "fail", "uncertain", "garbage"):
        for binding in (acc.BINDING_BOUND, acc.BINDING_AMBIGUOUS,
                        acc.BINDING_OTHER_SESSION, acc.BINDING_NONE):
            r = assessor.map_acceptance_verdict(
                {"verdict": verdict, "problems": [
                    {"criterion": "c", "evidence": "e", "explanation": "x"}]},
                binding=binding,
            )
            assert "decision" not in r
            assert r["status"] in ("ok", "warning", "needs_followup")
