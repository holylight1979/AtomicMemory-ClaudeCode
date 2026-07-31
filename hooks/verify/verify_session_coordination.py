"""verify_session_coordination.py — 跨 session 衝突預警（wg_coordination）。

驗證：
  - 同檔衝突偵測（entry 級 session_id 歸屬：自寫不警、merged/done 排除、oversize 跳過）
  - warn-cache 去重（10min 抑制；cache 損毀只停用去重、警告照發）
  - late-collision 60s 窗（59s 命中 / 61s 不中 / 壞格式與未來時間跳過）
  - Bash 收尾指令 pattern（引號/註解/echo 誤報面 + cwd scope + 無 peer 靜默）
  - fail-open（壞 state JSON 不炸）+ observation log NDJSON per-session 檔
  - handler 層 warn/deny 互斥（stdout 恆單一 JSON、deny 優先、warn 不帶 permissionDecision）

對應：hooks/wg_coordination.py、handlers/pre_tool_use.py、workflow config coordination.*
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

import wg_coordination as wc  # noqa: E402

CFG = {"coordination": {"enabled": True, "warn_suppress_min": 10,
                        "scan_mtime_window_s": 1800, "max_scan_files": 10}}
SELF = "self-session-0000"


def _iso(offset_s: float = 0) -> str:
    return (datetime.now(timezone.utc).astimezone()
            + timedelta(seconds=offset_s)).isoformat(timespec="seconds")


def _mk_state(dir_: Path, sid: str, path_entries, phase="working", cwd="C:/w",
              merged=None, entry_sids=None):
    entries = []
    for i, (p, at) in enumerate(path_entries):
        entries.append({
            "path": p, "tool": "Edit", "at": at, "count": 2,
            "session_id": (entry_sids or [sid] * len(path_entries))[i],
        })
    data = {"phase": phase, "session": {"id": sid, "cwd": cwd},
            "modified_files": entries}
    if merged:
        data["merged_into"] = merged
    f = dir_ / f"state-{sid}.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


def _patch_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(wc, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(wc, "COORD_LOG_DIR", tmp_path / "coordlog")


# ─── 衝突偵測 ───────────────────────────────────────────────────────────────


def test_conflict_hit_and_log(tmp_path, monkeypatch):
    """peer working state 同檔 → 命中 + observation log 記完整 sid。"""
    _patch_dirs(tmp_path, monkeypatch)
    target = str(tmp_path / "shared.py")
    _mk_state(tmp_path, "peer-aaaa-1111", [(target, _iso(-5))])
    hit = wc.check_cross_session_conflict(SELF, target, CFG)
    assert hit and hit["peer_sid"] == "peer-aaaa-1111"
    rows = [json.loads(l) for l in
            (tmp_path / "coordlog" / f"{SELF}.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(r["ev"] == "conflict_warn" and r["peer"] == "peer-aaaa-1111" for r in rows)


def test_self_entries_not_warned(tmp_path, monkeypatch):
    """merged 工作樹：entry 級 session_id == 自己 → 不警（state owner 是別人也一樣）。"""
    _patch_dirs(tmp_path, monkeypatch)
    target = str(tmp_path / "mine.py")
    _mk_state(tmp_path, "peer-bbbb-2222", [(target, _iso(-5))], entry_sids=[SELF])
    assert wc.check_cross_session_conflict(SELF, target, CFG) is None


def test_merged_and_done_excluded(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    target = str(tmp_path / "x.py")
    _mk_state(tmp_path, "peer-cccc-3333", [(target, _iso(-5))], phase="done")
    _mk_state(tmp_path, "peer-dddd-4444", [(target, _iso(-5))], merged="other")
    assert wc.check_cross_session_conflict(SELF, target, CFG) is None


def test_oversize_state_skipped(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    target = str(tmp_path / "big.py")
    f = _mk_state(tmp_path, "peer-eeee-5555", [(target, _iso(-5))])
    f.write_text(f.read_text(encoding="utf-8") + " " * (600 * 1024), encoding="utf-8")
    assert wc.check_cross_session_conflict(SELF, target, CFG) is None
    rows = (tmp_path / "coordlog" / f"{SELF}.jsonl").read_text(encoding="utf-8")
    assert "skip_oversize" in rows


def test_warn_cache_dedup_and_corrupt(tmp_path, monkeypatch):
    """record 後同檔 10min 內 → 抑制；未 record 不抑制；cache 損毀 → 警告照發。"""
    _patch_dirs(tmp_path, monkeypatch)
    target = str(tmp_path / "dup.py")
    _mk_state(tmp_path, "peer-ffff-6666", [(target, _iso(-5))])
    assert wc.check_cross_session_conflict(SELF, target, CFG) is not None
    # check 本身不寫 cache（記錄由發警端負責）→ 再查仍命中
    assert wc.check_cross_session_conflict(SELF, target, CFG) is not None
    wc.record_warn_cache(SELF, target)
    assert wc.check_cross_session_conflict(SELF, target, CFG) is None  # suppressed
    wc._warn_cache_path(SELF).write_text("{corrupt", encoding="utf-8")
    assert wc.check_cross_session_conflict(SELF, target, CFG) is not None  # cache 壞→照警


def test_warn_cache_prunes_old_entries(tmp_path, monkeypatch):
    """寫入時修剪 >24h entry（單 session 長跑不無界增長）。"""
    _patch_dirs(tmp_path, monkeypatch)
    wc._warn_cache_path(SELF).write_text(
        json.dumps({"old/path": time.time() - 90000}), encoding="utf-8")
    wc.record_warn_cache(SELF, str(tmp_path / "new.py"))
    data = json.loads(wc._warn_cache_path(SELF).read_text(encoding="utf-8"))
    assert "old/path" not in data and len(data) == 1


def test_null_coordination_config_tolerated(tmp_path, monkeypatch):
    """config 'coordination': null（合法 JSON）→ 不炸、視同 disabled。"""
    _patch_dirs(tmp_path, monkeypatch)
    t = str(tmp_path / "n.py")
    _mk_state(tmp_path, "peer-null-0001", [(t, _iso(-5))])
    assert wc.check_cross_session_conflict(SELF, t, {"coordination": None}) is None
    assert wc.check_bash_git_finalize(SELF, "git add -A", "C:/w", {"coordination": None}) is None


def test_win32_namespace_path_normalized(tmp_path, monkeypatch):
    r"""\\?\C:\... 與 C:\... 視為同檔（peer entry 任一表示法都命中）。"""
    _patch_dirs(tmp_path, monkeypatch)
    plain = str(tmp_path / "ns.py")
    _mk_state(tmp_path, "peer-ns-00001", [(plain, _iso(-5))])
    assert wc.check_cross_session_conflict(SELF, "\\\\?\\" + plain, CFG) is not None


def test_scan_overflow_logged(tmp_path, monkeypatch):
    """候選超過 max_scan_files → 截斷必落 scan_overflow log（盲區可稽核）。"""
    _patch_dirs(tmp_path, monkeypatch)
    cfg = {"coordination": {**CFG["coordination"], "max_scan_files": 2}}
    for i in range(4):
        _mk_state(tmp_path, f"peer-ovfl-{i:04d}", [(str(tmp_path / f"f{i}.py"), _iso(-5))])
    wc.check_cross_session_conflict(SELF, str(tmp_path / "zz.py"), cfg)
    log = (tmp_path / "coordlog" / f"{SELF}.jsonl").read_text(encoding="utf-8")
    assert "scan_overflow" in log


# ─── late-collision 60s 窗 ──────────────────────────────────────────────────


def test_entry_window(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    t = str(tmp_path / "w.py")
    for sid, at in [("peer-1111-aaaa", _iso(-59)), ("peer-2222-bbbb", _iso(-61)),
                    ("peer-3333-cccc", "not-a-date"), ("peer-4444-dddd", _iso(+120))]:
        _mk_state(tmp_path, sid, [(t, at)])
    hit = wc.check_cross_session_conflict(SELF, t, CFG, entry_window_s=60, use_cache=False)
    assert hit and hit["peer_sid"] == "peer-1111-aaaa"  # 僅 59s 者命中
    # 只留 61s / 壞格式 / 未來 → 全跳過
    (tmp_path / "state-peer-1111-aaaa.json").unlink()
    assert wc.check_cross_session_conflict(SELF, t, CFG, entry_window_s=60,
                                           use_cache=False) is None


def test_late_collision_bypasses_cache(tmp_path, monkeypatch):
    """use_cache=False：抑制窗內仍回命中（log 不斷流）。"""
    _patch_dirs(tmp_path, monkeypatch)
    t = str(tmp_path / "bp.py")
    _mk_state(tmp_path, "peer-5555-eeee", [(t, _iso(-3))])
    assert wc.check_cross_session_conflict(SELF, t, CFG) is not None       # 記入 cache
    assert wc.check_cross_session_conflict(SELF, t, CFG, entry_window_s=60,
                                           use_cache=False) is not None    # 不受抑制


# ─── Bash 收尾指令 ──────────────────────────────────────────────────────────


def test_bash_danger_patterns():
    pos = ["git add -A", "git add .", "git add --all", "git reset --hard HEAD",
           "git -C C:/w add -A", "cd /x && git add -A", "git clean -fd",
           "git checkout -- .",
           # 紅隊：引號/前綴/子 shell 繞過面
           'git add "-A"', 'git reset "--hard"', 'git checkout -- "."',
           'git clean "-fd"', 'git -C "C:/repo" add -A',
           "command git add -A", "(git reset --hard)",
           "git --no-pager add -A", "git -c core.commentChar=# add -A"]
    neg = ['echo "git add -A"', "# git reset --hard", "git add file.py",
           "git log | grep 'reset --hard'", "printf 'git clean -f'",
           "git status", "git addendum",
           # 紅隊：誤報面（shell 語意 / dry-run）
           '"echo" git add -A', "git add -A --dry-run", "git clean -nf",
           "git clean -fn"]
    for c in pos:
        assert wc._command_has_danger(c), c
    for c in neg:
        assert not wc._command_has_danger(c), c


def test_bash_warn_requires_same_cwd_peer(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    _mk_state(tmp_path, "peer-6666-ffff", [(str(tmp_path / "a.py"), _iso(-5))],
              cwd="C:/other")
    assert wc.check_bash_git_finalize(SELF, "git add -A", "C:/w", CFG) is None  # 異 cwd
    _mk_state(tmp_path, "peer-7777-0000", [(str(tmp_path / "b.py"), _iso(-5))],
              cwd="C:/w")
    warn = wc.check_bash_git_finalize(SELF, "git add -A", "C:/w", CFG)
    assert warn and "peer-777" in warn


def test_bash_no_peer_silent(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    assert wc.check_bash_git_finalize(SELF, "git add -A", "C:/w", CFG) is None


# ─── fail-open + log ────────────────────────────────────────────────────────


def test_corrupt_state_fail_open(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    (tmp_path / "state-corrupt-9999.json").write_text("{bad json", encoding="utf-8")
    assert wc.check_cross_session_conflict(SELF, str(tmp_path / "z.py"), CFG) is None


def test_disabled_zero_scan(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    t = str(tmp_path / "d.py")
    _mk_state(tmp_path, "peer-8888-1111", [(t, _iso(-5))])
    assert wc.check_cross_session_conflict(SELF, t, {"coordination": {"enabled": False}}) is None


def test_coord_log_ndjson(tmp_path, monkeypatch):
    _patch_dirs(tmp_path, monkeypatch)
    wc.coord_log(SELF, "scan_clear", path="p", ms=1.2)
    wc.coord_log(SELF, "fail_open", degraded_reason="x")
    rows = [json.loads(l) for l in
            (tmp_path / "coordlog" / f"{SELF}.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2 and rows[0]["ts"] and rows[0]["sid"] == SELF


# ─── handler 層 warn/deny 互斥 ──────────────────────────────────────────────


def _run_handler(tmp_path, monkeypatch, tool_name, tool_input):
    import handlers.pre_tool_use as ptu
    _patch_dirs(tmp_path, monkeypatch)
    out = []
    monkeypatch.setattr(ptu, "output_json", lambda d: out.append(d))
    monkeypatch.setattr(ptu, "output_nothing", lambda: out.append(None))
    ptu.handle_pre_tool_use(
        {"tool_name": tool_name, "tool_input": tool_input,
         "session_id": SELF, "cwd": "C:/w"},
        CFG,
    )
    return out


def test_handler_warn_only(tmp_path, monkeypatch):
    """只 warn：單一 JSON、含 additionalContext、無 permissionDecision。"""
    target = str(tmp_path / "plain.py")
    _mk_state(tmp_path, "peer-9999-2222", [(target, _iso(-5))])
    out = _run_handler(tmp_path, monkeypatch, "Edit", {"file_path": target})
    assert len(out) == 1 and out[0] is not None
    hso = out[0]["hookSpecificOutput"]
    assert "additionalContext" in hso and "permissionDecision" not in hso
    assert out[0].get("systemMessage")


def test_handler_deny_wins_over_warn(tmp_path, monkeypatch):
    """warn+deny 同時：stdout 單一 JSON 且為 deny（warn 只留 stderr）。"""
    target = str(tmp_path / ".claude" / "memory" / "fake-atom.md")
    _mk_state(tmp_path, "peer-aaaa-3333", [(target, _iso(-5))])
    out = _run_handler(tmp_path, monkeypatch, "Write",
                       {"file_path": target, "content": "not an atom"})
    assert len(out) == 1 and out[0] is not None
    assert out[0]["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "additionalContext" not in out[0]["hookSpecificOutput"]


def test_handler_no_conflict_passthrough(tmp_path, monkeypatch):
    """無衝突無 deny → output_nothing。"""
    out = _run_handler(tmp_path, monkeypatch, "Edit",
                       {"file_path": str(tmp_path / "free.py")})
    assert out == [None]


def test_handler_deny_does_not_poison_cache(tmp_path, monkeypatch):
    """紅隊 #7：deny 回合不記 warn-cache → 修正後合法重試仍收到警告。"""
    atom_target = str(tmp_path / ".claude" / "memory" / "fake2.md")
    plain_target = str(tmp_path / "retry.py")
    _mk_state(tmp_path, "peer-bbbb-7777",
              [(atom_target, _iso(-5)), (plain_target, _iso(-5))])
    out1 = _run_handler(tmp_path, monkeypatch, "Write",
                        {"file_path": atom_target, "content": "bad"})
    assert out1[0]["hookSpecificOutput"]["permissionDecision"] == "deny"
    # 同 session 立即對另一衝突檔 warn-only：cache 未被 deny 回合污染 → 照警
    out2 = _run_handler(tmp_path, monkeypatch, "Edit", {"file_path": plain_target})
    assert "additionalContext" in out2[0]["hookSpecificOutput"]
    # 且 warn 回合有記 cache：同檔再來一次 → 抑制（passthrough）
    out3 = _run_handler(tmp_path, monkeypatch, "Edit", {"file_path": plain_target})
    assert out3 == [None]


def test_handler_null_coordination_deny_still_works(tmp_path, monkeypatch):
    """紅隊 #1：config coordination=null → 不炸，既有 deny gate 照常輸出。"""
    import handlers.pre_tool_use as ptu
    _patch_dirs(tmp_path, monkeypatch)
    out = []
    monkeypatch.setattr(ptu, "output_json", lambda d: out.append(d))
    monkeypatch.setattr(ptu, "output_nothing", lambda: out.append(None))
    ptu.handle_pre_tool_use(
        {"tool_name": "Write", "session_id": SELF, "cwd": "C:/w",
         "tool_input": {"file_path": str(tmp_path / ".claude" / "memory" / "x.md"),
                        "content": "bad"}},
        {"coordination": None},
    )
    assert len(out) == 1
    assert out[0]["hookSpecificOutput"]["permissionDecision"] == "deny"
