"""verify_auto_continue.py — Auto-Handoff Phase 4 watcher guard 驗證

以注入的 spawn/sleep/now/confirm + tmp_path 模擬 stub，驗四道 guard、single-stub
不變式、idle 退出、stub 穩定門檻、JSON 解析、組態優先序。全程不真起 model session。
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

TOOL_DIR = Path(__file__).resolve().parent.parent  # verify/ → tools/auto-continue/
SPEC = importlib.util.spec_from_file_location("auto_continue", TOOL_DIR / "auto_continue.py")
AC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AC)


# ─── helpers ──────────────────────────────────────────────────────────────────
def base_config(watch_dir, **over):
    cfg = dict(AC.DEFAULTS)
    cfg.update({
        "watch_dir": str(watch_dir),
        "claude_bin": "fake-claude",
        "stub_stable_sec": 0.0,      # 測試免等穩定
        "poll_interval_sec": 0.0,
        "idle_timeout_sec": 60.0,
        "max_consecutive_spawns": 100,
        "budget_usd": 1e9,
        "confirm_every_n": 0,
    })
    cfg.update(over)
    return cfg


def write_stub(watch_dir, name="next-phase-test.md", body="task"):
    p = Path(watch_dir) / name
    p.write_text(body, encoding="utf-8")
    return p


def make_chaining_spawn(watch_dir, cost=1.0, error=False, num_turns=2):
    """模擬 /continue：刪舊 stub、寫新 stub（讓鏈持續），回 JSON result。"""
    calls = {"n": 0}

    def spawn(target_cwd, config, log):
        calls["n"] += 1
        for f in Path(watch_dir).glob("next-phase*.md"):
            f.unlink()
        write_stub(watch_dir, body=f"phase {calls['n']}")
        return {"exit": 1 if error else 0, "stdout": "", "stderr": "",
                "data": {"type": "result", "is_error": error, "total_cost_usd": cost,
                         "num_turns": num_turns, "session_id": f"s{calls['n']}",
                         "result": "ok"}}
    return spawn, calls


def noop_sleep(_):
    pass


def run(cfg, watch_dir, spawn_fn, **kw):
    kw.setdefault("sleep_fn", noop_sleep)
    kw.setdefault("max_iter", 200)
    kw.setdefault("log", lambda *_: None)
    return AC.run_watch_loop(cfg, str(watch_dir), spawn_fn=spawn_fn, **kw)


# ─── guard 1：max_consecutive_spawns ──────────────────────────────────────────
def test_guard_max_spawns(tmp_path):
    write_stub(tmp_path)
    cfg = base_config(tmp_path, max_consecutive_spawns=3)
    spawn, calls = make_chaining_spawn(tmp_path)
    state = run(cfg, tmp_path, spawn)
    assert state["spawns"] == 3
    assert calls["n"] == 3
    assert "max_consecutive_spawns" in state["stop_reason"]


# ─── guard 2：budget_usd ──────────────────────────────────────────────────────
def test_guard_budget(tmp_path):
    write_stub(tmp_path)
    cfg = base_config(tmp_path, budget_usd=2.5)
    spawn, calls = make_chaining_spawn(tmp_path, cost=1.0)
    state = run(cfg, tmp_path, spawn)
    # 1.0+1.0+1.0=3.0 ≥ 2.5 → 第三次後停
    assert state["spawns"] == 3
    assert state["cost_usd"] == pytest.approx(3.0)
    assert "budget_usd" in state["stop_reason"]


# ─── guard 4：kill switch ─────────────────────────────────────────────────────
def test_guard_kill_switch_blocks_immediately(tmp_path):
    write_stub(tmp_path)
    (tmp_path / "STOP").write_text("", encoding="utf-8")
    cfg = base_config(tmp_path)
    spawn, calls = make_chaining_spawn(tmp_path)
    state = run(cfg, tmp_path, spawn)
    assert state["spawns"] == 0
    assert calls["n"] == 0
    assert "kill switch" in state["stop_reason"]


def test_kill_switch_absolute_path(tmp_path):
    ks = tmp_path / "elsewhere" / "halt.flag"
    ks.parent.mkdir()
    ks.write_text("", encoding="utf-8")
    write_stub(tmp_path)
    cfg = base_config(tmp_path, kill_switch=str(ks))
    spawn, _ = make_chaining_spawn(tmp_path)
    state = run(cfg, tmp_path, spawn)
    assert state["spawns"] == 0


# ─── guard 3：confirm_every_n ─────────────────────────────────────────────────
def test_guard_confirm_decline_stops(tmp_path):
    write_stub(tmp_path)
    cfg = base_config(tmp_path, confirm_every_n=1)
    spawn, calls = make_chaining_spawn(tmp_path)
    state = run(cfg, tmp_path, spawn, confirm_fn=lambda *a, **k: False)
    # 第一次 spawn 後 spawns=1，1%1==0 → 確認 → 拒 → 停
    assert state["spawns"] == 1
    assert "人工確認" in state["stop_reason"]


def test_guard_confirm_approve_then_other_guard(tmp_path):
    write_stub(tmp_path)
    cfg = base_config(tmp_path, confirm_every_n=2, max_consecutive_spawns=4)
    spawn, _ = make_chaining_spawn(tmp_path)
    seen = {"confirms": 0}

    def approve(*a, **k):
        seen["confirms"] += 1
        return True
    state = run(cfg, tmp_path, spawn, confirm_fn=approve)
    assert state["spawns"] == 4               # 確認皆通過 → 跑到 max
    assert seen["confirms"] >= 1              # 至少觸發過確認點（spawns=2）
    assert "max_consecutive_spawns" in state["stop_reason"]


# ─── single-stub 不變式 ───────────────────────────────────────────────────────
def test_multiple_stub_invariant(tmp_path):
    write_stub(tmp_path, "next-phase-a.md")
    write_stub(tmp_path, "next-phase-b.md")
    cfg = base_config(tmp_path)
    spawn, calls = make_chaining_spawn(tmp_path)
    state = run(cfg, tmp_path, spawn)
    assert state["spawns"] == 0
    assert calls["n"] == 0
    assert "歧義" in state["stop_reason"]


# ─── dry-run ──────────────────────────────────────────────────────────────────
def test_dry_run_no_spawn(tmp_path):
    write_stub(tmp_path)
    cfg = base_config(tmp_path, dry_run=True)
    spawn, calls = make_chaining_spawn(tmp_path)
    state = run(cfg, tmp_path, spawn)
    assert state["spawns"] == 0
    assert calls["n"] == 0
    assert "dry-run" in state["stop_reason"]


# ─── idle 退出 ────────────────────────────────────────────────────────────────
def test_idle_timeout_exit(tmp_path):
    cfg = base_config(tmp_path, idle_timeout_sec=60.0)
    spawn, calls = make_chaining_spawn(tmp_path)  # 不會被呼叫
    clock = {"v": 0.0}

    def now():
        clock["v"] += 10.0
        return clock["v"]
    state = run(cfg, tmp_path, spawn, now_fn=now)
    assert state["spawns"] == 0
    assert "idle" in state["stop_reason"]


# ─── 出錯即停鏈 ───────────────────────────────────────────────────────────────
def test_error_stops_chain(tmp_path):
    write_stub(tmp_path)
    cfg = base_config(tmp_path)
    spawn, calls = make_chaining_spawn(tmp_path, error=True)
    state = run(cfg, tmp_path, spawn)
    assert state["spawns"] == 1
    assert state["errors"] == 1
    assert "出錯" in state["stop_reason"]


def test_exit_nonzero_counts_as_error(tmp_path):
    write_stub(tmp_path)
    cfg = base_config(tmp_path)

    def bad_spawn(target_cwd, config, log):
        for f in Path(tmp_path).glob("next-phase*.md"):
            f.unlink()
        write_stub(tmp_path)
        return {"exit": 2, "data": {"type": "result", "is_error": False,
                                    "total_cost_usd": 0.5}, "stdout": "", "stderr": ""}
    state = run(cfg, tmp_path, bad_spawn)
    assert state["errors"] == 1
    assert "出錯" in state["stop_reason"]


# ─── find_stub 穩定門檻 ───────────────────────────────────────────────────────
def test_find_stub_respects_stability(tmp_path):
    p = write_stub(tmp_path)
    now = 1000.0
    os.utime(p, (now, now))
    # 才剛寫（now 緊接 mtime）→ 不穩定 → None
    assert AC.find_stub(tmp_path, stable_sec=100.0, now_fn=lambda: now + 1) is None
    # 過了穩定窗 → 回傳
    assert AC.find_stub(tmp_path, stable_sec=100.0, now_fn=lambda: now + 200) == p


def test_find_stub_returns_oldest(tmp_path):
    a = write_stub(tmp_path, "next-phase-a.md")
    b = write_stub(tmp_path, "next-phase-b.md")
    os.utime(a, (1000, 1000))
    os.utime(b, (2000, 2000))
    assert AC.find_stub(tmp_path, stable_sec=0.0, now_fn=lambda: 9999) == a


# ─── JSON 解析 ────────────────────────────────────────────────────────────────
def test_parse_result_json_skips_warning_lines():
    stdout = ('Warning: no stdin data received in 3s, proceeding without it.\n'
              '{"type":"result","is_error":false,"total_cost_usd":0.27,"num_turns":3}\n')
    obj = AC.parse_result_json(stdout)
    assert obj["type"] == "result"
    assert obj["total_cost_usd"] == 0.27


def test_parse_result_json_empty_on_garbage():
    assert AC.parse_result_json("not json at all\nstill not\n") == {}


def test_parse_result_json_picks_result_type_not_other():
    stdout = ('{"type":"system","subtype":"init"}\n'
              '{"type":"result","is_error":false,"num_turns":1}\n')
    assert AC.parse_result_json(stdout).get("num_turns") == 1


# ─── 組態優先序 ───────────────────────────────────────────────────────────────
def test_load_config_override_precedence(tmp_path):
    cfgfile = tmp_path / "c.json"
    cfgfile.write_text('{"budget_usd": 9.0, "max_consecutive_spawns": 7}', encoding="utf-8")
    cfg = AC.load_config(str(cfgfile), {"budget_usd": 2.0, "max_consecutive_spawns": None})
    assert cfg["budget_usd"] == 2.0           # CLI override 贏
    assert cfg["max_consecutive_spawns"] == 7  # None override 不蓋掉檔案值
    assert cfg["confirm_every_n"] == AC.DEFAULTS["confirm_every_n"]  # 未提供 → 預設


def test_resolve_watch_dir_override(tmp_path):
    cfg = dict(AC.DEFAULTS, watch_dir=str(tmp_path))
    assert AC.resolve_watch_dir("C:\\whatever", cfg) == tmp_path


# ─── claude binary 偵測（環境寬鬆）────────────────────────────────────────────
def test_detect_claude_bin_type():
    got = AC.detect_claude_bin()
    assert got is None or isinstance(got, str)
    if got:
        assert "claude" in got.lower()


def test_parse_ver():
    assert AC._parse_ver("anthropic.claude-code-2.1.169-win32-x64") == (2, 1, 169)
    assert AC._parse_ver("no-version-here") == (0, 0, 0)
