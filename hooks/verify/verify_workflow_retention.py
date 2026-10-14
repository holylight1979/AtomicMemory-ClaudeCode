"""verify_workflow_retention.py — workflow/ 執行紀錄保留規則表（handlers/_shared.WORKFLOW_RETENTION）照表清理。

驗 handlers/_shared.prune_workflow_records(wf, current_sid, now, dry_run)：
  - 表上每列都有理由與已知的規則種類
  - 新管的資料夾：舊檔刪、新檔留（acceptance-spec、harvest-ledger、verify-ledger、second-opinion、usage-snapshots、scorecard）
  - 搬進表的既有規則照舊（根目錄殘檔、companion、session-coordination、dpm-done、ups-sentinel、aec-report 補 .tmp）
  - 目前 session 的檔不動；「不清」清單與「另由別支程式清」的列不動
  - need-goal 鎖檔只在同名目標檔不在、且夠舊時才刪
  - tracking 只拿掉結案超過 90 天的「開項＋結案」一對；改寫途中檔案被別人改過就這一輪不動
  - _overview-hub.log 超過門檻輪替
  - dry_run 不刪；刪不掉的檔列進 failed 並寫 atom-debug 一行
跑法：python -X utf8 -m pytest -q hooks/verify/verify_workflow_retention.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

from handlers import _shared  # noqa: E402

DAY = 86400
NOW = datetime(2026, 10, 14, 12, 0, 0).timestamp()
CUR = "cur00000-0000-0000-0000-000000000000"


@pytest.fixture
def wf(tmp_path):
    d = tmp_path / "workflow"
    d.mkdir()
    return d


def put(p: Path, age_days: float, body: str = "x") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    t = NOW - age_days * DAY
    os.utime(p, (t, t))
    return p


def run(wf: Path, **kw):
    return _shared.prune_workflow_records(wf=wf, current_sid=CUR, now=NOW, **kw)


def test_every_row_has_reason_and_known_kind():
    assert _shared.WORKFLOW_RETENTION
    for row in _shared.WORKFLOW_RETENTION:
        assert row["why"].strip(), row
        assert row["kind"] in _shared.RETENTION_KINDS, row
        assert row["dir"] is not None and row["patterns"], row


def test_new_dirs_old_deleted_fresh_kept(wf):
    old = [put(wf / "acceptance-spec" / "a.json", 31), put(wf / "harvest-ledger" / "a.jsonl", 31),
           put(wf / "verify-ledger" / "a.jsonl", 15), put(wf / "verify-ledger" / "a.agents.jsonl", 15),
           put(wf / "usage-snapshots" / "usage-20260801-acc-FAILED.png", 31)]
    fresh = [put(wf / "acceptance-spec" / "b.json", 29), put(wf / "harvest-ledger" / "b.jsonl", 29),
             put(wf / "verify-ledger" / "b.jsonl", 13), put(wf / "usage-snapshots" / "usage-20261013-acc-FAILED.png", 1)]
    products = [put(wf / "usage-snapshots" / "usage-log.jsonl", 400), put(wf / "usage-snapshots" / "usage-last-run.json", 400),
                put(wf / "usage-snapshots" / "usage-20250101-acc.png", 400)]
    res = run(wf)
    assert [p.name for p in old if p.exists()] == []
    assert all(p.exists() for p in fresh + products)
    assert set(res["deleted"]) >= {str(p) for p in old}


def test_moved_rules_behave_as_before(wf):
    old = [put(wf / "companion-state-s1.json", 8), put(wf / "state-s1.123.tmp", 8), put(wf / "companion-state-s1.tmp", 8),
           put(wf / "state-s1.json.corrupt", 8), put(wf / "state-s1.json.corrupt-20261001", 8),
           put(wf / "coord-warn-cache-s1.json", 8), put(wf / "coord-warn-cache-s1.tmp", 8),
           put(wf.parent / "Logs" / "session-coordination" / "a.jsonl", 31),
           put(wf / "dpm-done" / "s1.flag", 8), put(wf / "ups-sentinel" / "s1.json", 8),
           put(wf / "aec-report" / "s1-t3.json", 8), put(wf / "aec-report" / "s1-t3.tmp", 8),
           put(wf / "aec-decision" / "s1-t3.json", 8)]
    fresh = [put(wf / "companion-state-s2.json", 6), put(wf / "state-s2.456.tmp", 6),
             put(wf.parent / "Logs" / "session-coordination" / "b.jsonl", 29),
             put(wf / "dpm-done" / "s2.flag", 6), put(wf / "ups-sentinel" / "s2.json", 6),
             put(wf / "aec-report" / "s2-t1.tmp", 6)]
    live_state = put(wf / "state-live.json", 30, json.dumps({"phase": "working"}))
    run(wf)
    assert [p.name for p in old if p.exists()] == []
    assert all(p.exists() for p in fresh)
    assert live_state.exists()  # state-*.json 分級由 _cleanup_old_states 管，表上只登記


def test_current_session_files_untouched(wf):
    mine = [put(wf / "acceptance-spec" / f"{CUR}.json", 60), put(wf / "verify-ledger" / f"{CUR}.jsonl", 60),
            put(wf / "verify-ledger" / f"{CUR}.agents.jsonl", 60), put(wf / "ups-sentinel" / f"{CUR}.json", 60),
            put(wf / "dpm-done" / f"{CUR}.flag", 60), put(wf / "need-goal" / f"{CUR}.json", 60),
            put(wf / "harvest-ledger" / f"{CUR}.jsonl", 60)]
    run(wf)
    assert all(p.exists() for p in mine)


def test_need_goal_json_corrupt_and_lock(wf):
    ng = wf / "need-goal"
    old_goal = put(ng / "s1.json", 31)
    old_goal_lock = put(ng / "s1.lock", 31, "")
    live_goal, live_lock = put(ng / "s2.json", 1), put(ng / "s2.lock", 60, "")
    orphan_lock = put(ng / "s3.lock", 31, "")
    young_orphan_lock = put(ng / "s4.lock", 5, "")
    corrupt_old = put(ng / "s5.corrupt-20260901-101010.json", 31)
    corrupt_new = put(ng / "s6.corrupt-20261010-101010.json", 3)
    run(wf)
    assert not old_goal.exists() and not old_goal_lock.exists()   # 目標檔過期清掉，鎖也跟著清
    assert live_goal.exists() and live_lock.exists()              # 目標檔還在：鎖多舊都不動
    assert not orphan_lock.exists() and young_orphan_lock.exists()
    assert not corrupt_old.exists() and corrupt_new.exists()


def test_second_opinion_job_dirs(wf):
    so = wf / "second-opinion"
    old_job = so / "20260920-101010-aaaaaaaa-review"
    for n in ("request.json", "reply.md"):
        put(old_job / n, 15)
    os.utime(old_job, (NOW - 15 * DAY, NOW - 15 * DAY))
    sealed_old = put(so / "_sealed" / f"{old_job.name}.txt", 15)
    new_job = so / "20261013-101010-bbbbbbbb-review"
    put(new_job / "reply.md", 1)
    probe = put(so / "_probe" / "probe.log", 100)
    run(wf)
    assert not old_job.exists() and not sealed_old.exists()
    assert new_job.exists() and probe.exists()


def test_second_opinion_dir_with_recent_file_kept(wf):
    job = wf / "second-opinion" / "20260920-101010-cccccccc-review"
    put(job / "request.json", 30)
    put(job / "reply.md", 2)  # 最近才寫完的回覆：整個 job 還新
    os.utime(job, (NOW - 30 * DAY, NOW - 30 * DAY))
    run(wf)
    assert job.exists()


def test_scorecard_keeps_current_and_two_previous_months(wf):
    sc = wf / "scorecard"
    keep = [put(sc / f"{m}.jsonl", 1) for m in ("202610", "202609", "202608")]
    drop = [put(sc / f"{m}.jsonl", 1) for m in ("202607", "202512")]
    cand = put(sc / "candidates.json", 400)
    run(wf)
    assert all(p.exists() for p in keep) and cand.exists()
    assert [p.name for p in drop if p.exists()] == []


def _row(**kw):
    return json.dumps(kw, ensure_ascii=False)


def _iso(age_days: float) -> str:
    return datetime.fromtimestamp(NOW - age_days * DAY).astimezone().isoformat(timespec="seconds")


def test_tracking_compacts_only_old_closed_pairs(wf):
    lines = [
        _row(id="A", session_id="s", turn_seq=1, at=_iso(200), part="p", text="舊的已結案項目", status="open"),
        _row(id="Ac", session_id="s", turn_seq=2, at=_iso(100), part="p", text="舊的已結案", status="closed",
             closes={"id": "A", "at": _iso(200), "text_prefix": "舊的已結案"}),
        _row(id="B", session_id="s", turn_seq=3, at=_iso(200), part="p", text="最近才結案的項目", status="open"),
        _row(id="Bc", session_id="s", turn_seq=4, at=_iso(10), part="p", text="最近才結案", status="closed",
             closes={"id": "B", "at": _iso(200), "text_prefix": "最近才結案"}),
        _row(id="C", session_id="s", turn_seq=5, at=_iso(300), part="", text="一直沒結案的項目", status="open"),
        "not json at all",
    ]
    p = put(wf / "tracking" / "proj.jsonl", 1, "\n".join(lines) + "\n")
    run(wf)
    got = p.read_text(encoding="utf-8").splitlines()
    assert got == [lines[2], lines[3], lines[4], lines[5]]   # 只拿掉 A 那一對，其他原樣保留、順序不變


def test_tracking_untouched_when_nothing_to_drop(wf):
    body = _row(id="C", session_id="s", turn_seq=5, at=_iso(300), part="", text="一直沒結案的項目", status="open") + "\n"
    p = put(wf / "tracking" / "proj.jsonl", 1, body)
    before = p.stat().st_mtime_ns
    run(wf)
    assert p.read_text(encoding="utf-8") == body and p.stat().st_mtime_ns == before


def test_tracking_skips_when_file_changed_during_rewrite(wf, monkeypatch):
    lines = [
        _row(id="A", session_id="s", turn_seq=1, at=_iso(200), part="p", text="舊的已結案項目", status="open"),
        _row(id="Ac", session_id="s", turn_seq=2, at=_iso(100), part="p", text="舊的已結案", status="closed",
             closes={"id": "A", "at": _iso(200), "text_prefix": "舊的已結案"}),
    ]
    p = put(wf / "tracking" / "proj.jsonl", 1, "\n".join(lines) + "\n")
    real = _shared._file_sig
    calls = {"n": 0}

    def sig(path):
        calls["n"] += 1
        s = real(path)
        return s if calls["n"] == 1 else (s[0] + 1, s[1])   # 第二次看：檔案被別的 session 追加了
    monkeypatch.setattr(_shared, "_file_sig", sig)
    run(wf)
    assert p.read_text(encoding="utf-8").splitlines() == lines


def test_keep_list_and_elsewhere_rows_untouched(wf):
    keep = [put(wf / n, 400) for n in ("config.json", "followups.json", "org-memory.local.json",
                                        "health-last-run.json", "world-dev.json")]
    keep += [put(wf / "inbox" / "b5-kit" / "README.md", 400), put(wf / "vcs-sync" / "abc.lock", 400),
             put(wf / "verify-ledger" / "_runs" / "r.json", 400), put(wf / "tool-results" / "s.jsonl", 400),
             put(wf / "health-reports" / "health-20250101.md", 400), put(wf / "se-sentinel" / "s.json", 400),
             put(wf / "aec-tempfiles" / "s.jsonl", 400, json.dumps({"path": str(wf / "config.json")}) + "\n")]
    run(wf)
    assert [str(p) for p in keep if not p.exists()] == []


def test_overview_hub_log_rotates_over_threshold(wf, monkeypatch):
    log = put(wf / "_overview-hub.log", 1, "line\n" * 10)
    monkeypatch.setattr(_shared, "OVERVIEW_LOG_MAX_MB", 0)
    run(wf)
    assert (wf / "_overview-hub.log.1").exists()
    assert log.exists() and log.stat().st_size == 0


def test_dry_run_deletes_nothing(wf):
    a = put(wf / "acceptance-spec" / "a.json", 31)
    res = run(wf, dry_run=True)
    assert a.exists() and str(a) in res["deleted"]


def test_delete_failure_listed_and_signalled(wf, monkeypatch):
    stuck = put(wf / "acceptance-spec" / "stuck.json", 31)
    gone = put(wf / "acceptance-spec" / "gone.json", 31)
    real_unlink = Path.unlink

    def unlink(self, *a, **k):
        if self.name == "stuck.json":
            raise PermissionError("locked")
        return real_unlink(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", unlink)
    seen = []
    monkeypatch.setattr(_shared, "_atom_debug_error", lambda tag, e: seen.append((tag, str(e))))
    res = run(wf)
    assert stuck.exists() and not gone.exists()
    assert str(stuck) in res["failed"]
    assert seen and seen[0][0] == "workflow_retention" and "stuck.json" in seen[0][1]


def test_missing_workflow_dir_is_fine(tmp_path):
    res = _shared.prune_workflow_records(wf=tmp_path / "nope", current_sid=CUR, now=NOW)
    assert res["deleted"] == [] and res["failed"] == []
