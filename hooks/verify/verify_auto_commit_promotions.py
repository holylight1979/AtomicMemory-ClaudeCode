"""verify_auto_commit_promotions.py — 晉升 sweep 的上版控已整併進 vcs-sync worker。

不變式：
1. session_end 不再有 `_auto_commit_promotions`（舊路徑：只做根層、不 add 新檔、push 寫死 origin main）。
2. SessionEnd 只 spawn 一次 `spawn_vcs_sync`（同 root 的請求落 `.req/` 由持鎖者合併消費，兩次 spawn 只多一個立刻退出的行程），
   且包在 try 內——worker 起不來絕不拖垮 SessionEnd。
3. 有晉升時 reason 標 promotion、否則 session_end。
4. config 相容：`vcs_sync` 缺省時讀舊鍵 self_iteration.auto_commit_promotions / auto_push_promotions；
   `vcs_sync` 存在則舊鍵無效。
5. 關閉／無目標時 spawn 回 0 且不起子行程。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

CLAUDE = Path(__file__).resolve().parent.parent.parent  # hooks/verify/ → ~/.claude
sys.path.insert(0, str(CLAUDE / "hooks"))

from handlers import session_end as se  # noqa: E402
import wg_vcs_sync as vs  # noqa: E402

SE_SRC = (CLAUDE / "hooks" / "handlers" / "session_end.py").read_text(encoding="utf-8")


def test_old_auto_commit_path_removed():
    assert not hasattr(se, "_auto_commit_promotions")
    assert "auto-commit.log" not in SE_SRC
    assert "auto_commit_promotions" not in SE_SRC


def test_session_end_spawns_vcs_sync_once_inside_try():
    tree = ast.parse(SE_SRC)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "spawn_vcs_sync"]
    assert len(calls) == 1, "SessionEnd 應只 spawn 一次 vcs-sync"
    call = calls[0]
    guarded = any(isinstance(n, ast.Try) and any(call in ast.walk(stmt) for stmt in n.body)
                  for n in ast.walk(tree))
    assert guarded, "spawn_vcs_sync 必須包在 try 內（fail-open）"
    kw = {k.arg: k.value for k in call.keywords}
    assert isinstance(kw["reason"], ast.Name) and kw["reason"].id == "vcs_sync_reason"


def test_reason_marks_promotion():
    assert 'vcs_sync_reason = "session_end"' in SE_SRC
    assert 'vcs_sync_reason = "promotion"' in SE_SRC
    assert SE_SRC.index('vcs_sync_reason = "promotion"') < SE_SRC.index("spawn_vcs_sync(session_id")


def test_legacy_keys_alias_when_vcs_sync_missing():
    cfg = vs.vcs_sync_config({"self_iteration": {"auto_commit_promotions": False,
                                                 "auto_push_promotions": False}})
    assert cfg["enabled"] is False and cfg["push"] is False
    assert cfg["root_pathspecs"] == ["memory", "_AIDocs/_atoms"]
    cfg = vs.vcs_sync_config({"self_iteration": {"auto_commit_promotions": False},
                              "vcs_sync": {"enabled": True, "push": False}})
    assert cfg["enabled"] is True and cfg["push"] is False
    assert vs.vcs_sync_config({})["enabled"] is True


def test_spawn_disabled_or_no_targets_returns_zero(monkeypatch, tmp_path):
    import subprocess

    def boom(*a, **k):
        raise AssertionError("不得起子行程")
    monkeypatch.setattr(subprocess, "Popen", boom)
    assert vs.spawn_vcs_sync("sid", str(tmp_path), "test",
                             config={"vcs_sync": {"enabled": False}}) == 0
    monkeypatch.setattr(vs, "collect_sync_targets", lambda cwd, cfg, claude_dir=None: [])
    assert vs.spawn_vcs_sync("sid", str(tmp_path), "test", config={"vcs_sync": {"enabled": True}}) == 0
