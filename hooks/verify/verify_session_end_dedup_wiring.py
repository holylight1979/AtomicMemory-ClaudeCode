"""verify_session_end_dedup_wiring.py — DedupStage 接線 SessionEnd 的契約守門。

釘死：① handle_session_end 真的呼叫去蕪 helper（不是死碼）；② helper 以 env='core' 呼
sweep_drafts（**非 project**——project 會啟動叢集去重，core 端不要）；③ **fail-soft**：sweep
拋例外絕不冒泡出 SessionEnd（吞 + log）。dry-run/lock/可逆/14 天閘等 sweep 自身行為已由
verify_dedup_stage.py 守，本檔只守『接線』這一層。pytest。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent   # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent                             # → ~/.claude
for _p in (str(CLAUDE), str(HOOKS_DIR), str(CLAUDE / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import handlers.session_end as se  # noqa: E402
import lib.dedup_stage as ds  # noqa: E402


@pytest.fixture(autouse=True)
def _noop_purge(monkeypatch):
    """預設讓 purge_expired_trash no-op，避免任何測試誤刪真實 _trash（個別測試可 override 為 spy）。"""
    monkeypatch.setattr(ds, "purge_expired_trash", lambda *a, **k: [])


# ── ① 接線存在：handler 主體真的呼叫 helper（非死碼）────────────────────────
def test_handler_invokes_dedup_helper():
    src = (CLAUDE / "hooks" / "handlers" / "session_end.py").read_text(encoding="utf-8")
    assert "_dedup_sweep_core()" in src, "handle_session_end 未呼叫 _dedup_sweep_core（死碼）"


# ── ② helper 以 env='core' 呼 sweep（非 project，避免 core 被叢集去重）────────
def test_helper_calls_sweep_with_env_core(monkeypatch):
    captured = {}

    def spy(drafts_root, memory_dir, *, env, **kw):
        captured["drafts_root"] = Path(drafts_root)
        captured["env"] = env
        return {"status": "ok", "truncated": []}

    monkeypatch.setattr(ds, "sweep_drafts", spy)   # patch 惰性 from-import 的源
    rep = se._dedup_sweep_core()
    assert captured["env"] == "core"               # 鎖死 core（非 project）
    assert captured["drafts_root"].name == "_drafts"  # 對 core _drafts 牢籠
    assert rep["status"] == "ok"


def test_helper_targets_real_core_memory(monkeypatch):
    """drafts_root 指向 ~/.claude/memory/_drafts（core 牢籠），不誤指他處。"""
    captured = {}
    monkeypatch.setattr(ds, "sweep_drafts",
                        lambda dr, md, *, env, **kw: captured.update(dr=Path(dr)) or {"status": "ok"})
    se._dedup_sweep_core()
    assert captured["dr"] == (CLAUDE / "memory" / "_drafts")


# ── ③ fail-soft：sweep 拋例外，helper 吞掉、不冒泡（SessionEnd 不被弄垮）──────
def test_helper_fail_soft_on_sweep_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("sweep 內爆")

    monkeypatch.setattr(ds, "sweep_drafts", boom)
    # 不得 raise；回 error 報告
    rep = se._dedup_sweep_core()
    assert rep == {"status": "error"}


def test_helper_fail_soft_on_import_error(monkeypatch):
    """連 sweep_drafts 都拿不到（import 失敗）也得 fail-soft。"""
    monkeypatch.delattr(ds, "sweep_drafts", raising=False)
    rep = se._dedup_sweep_core()       # from-import 取不到屬性 → ImportError → 吞
    assert rep == {"status": "error"}


# ── ④ 14 天閘接線：helper 呼 purge_expired_trash（唯一硬刪路徑）────────────────
def test_helper_calls_purge_on_core_drafts(monkeypatch):
    captured = {}
    monkeypatch.setattr(ds, "sweep_drafts",
                        lambda dr, md, *, env, **kw: {"status": "ok", "truncated": []})
    monkeypatch.setattr(ds, "purge_expired_trash",
                        lambda dr, **kw: captured.update(dr=Path(dr)) or [])
    se._dedup_sweep_core()
    assert captured["dr"] == (CLAUDE / "memory" / "_drafts")   # 對 core _drafts 跑 14 天閘


def test_report_includes_purged_count(monkeypatch):
    monkeypatch.setattr(ds, "sweep_drafts",
                        lambda dr, md, *, env, **kw: {"status": "ok", "truncated": []})
    monkeypatch.setattr(ds, "purge_expired_trash",
                        lambda dr, **kw: ["expired-a.md", "expired-b.md"])  # 假裝硬刪 2 筆
    rep = se._dedup_sweep_core()
    assert rep["purged"] == 2


def test_helper_fail_soft_on_purge_error(monkeypatch):
    """purge 出錯也 fail-soft（14 天閘硬刪炸了，SessionEnd 仍不被弄垮）。"""
    monkeypatch.setattr(ds, "sweep_drafts",
                        lambda dr, md, *, env, **kw: {"status": "ok", "truncated": []})

    def boom(*a, **k):
        raise RuntimeError("purge 內爆")

    monkeypatch.setattr(ds, "purge_expired_trash", boom)
    rep = se._dedup_sweep_core()
    assert rep == {"status": "error"}
