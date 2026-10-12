"""verify_tracking_readback.py：AEC (k) 追蹤項的帳本命名、結案、讀回注入與 SessionStart 一次性提示。

正例：子目錄 cwd 與部位表根同一本帳本；有 open 項的部位第一次注入時附「【未結追蹤項】」；超過 5 筆附「另有 N 筆」；
      `[部位] 結案：<開頭≥8 字>` 補 closes 後該項不再列；未標部位的項目只在全新 session 的 SessionStart 列一次（compact 不再列）。
反例：已結案的不列；別部位的不列；未標部位的不進部位注入；結案前綴不足 8 字或找不到對象 → stderr、不寫；
      帳本壞行跳過並 stderr、注入照常；cwd 空 → _no-cwd 並 stderr；疑似分裂的舊帳本只 stderr、不合併。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_tracking_readback.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_harvest as wh  # noqa: E402
import wg_overview as wo  # noqa: E402

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
MAP = ("| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
       "| `Game/Battle/` | 戰鬥 | `戰鬥知識導讀` | 有 |\n| `Game/UI/` | 介面 | 無 | 無 |\n")


@pytest.fixture
def world(tmp_path, monkeypatch):
    """tmp 專案（部位表＋戰鬥卡）＋ tmp 的 workflow（帳本落這裡，不碰 live）。"""
    proj = tmp_path / "proj"
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(MAP, encoding="utf-8", newline="\n")
    (proj / ".claude" / "memory" / "shared" / "戰鬥知識導讀.md").write_text("# 戰鬥導讀\n病灶：共用字典", encoding="utf-8")
    for d in ("Game/Battle/Sub", "Game/UI"):
        (proj / d).mkdir(parents=True)
    wf = tmp_path / "workflow"
    monkeypatch.setattr(wh, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    return proj, wf


def _k(text: str, at: str, sid: str = "s1"):
    return wh.tracking_entries(sid, 1, text, at=at)


# ─── 帳本命名 ────────────────────────────────────────────────────────────────

def test_tracking_slug_subdir_maps_to_table_root_and_edge_cases(world, capsys):
    proj, _ = world
    root_slug = wh.tracking_slug(str(proj))
    assert wh.tracking_slug(str(proj / "Game" / "Battle" / "Sub")) == root_slug        # 子目錄 cwd 不分裂
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", root_slug)
    assert wh.tracking_slug("") == "_no-cwd" and "_no-cwd" in capsys.readouterr().err  # 反例：cwd 空
    deep = proj.parent / ("中文資料夾 " * 12).strip()
    deep.mkdir()
    s = wh.tracking_slug(str(deep))
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", s) and len(s) <= 64                     # 非 ASCII／超長也是合法檔名
    live = Path.home() / ".claude"
    if (live / ".claude" / "overview-map.md").is_file():                                 # 唯讀：根層帳本名與現存檔同名
        assert wh.tracking_slug(str(live)) == wh.tracking_slug(str(live / "hooks"))


def _git_worktree_of(repo: Path, wt: Path, name: str) -> None:
    """把 wt 接成 repo 的 git worktree 結構（repo/.git/worktrees/<name>/＋wt/.git 檔指回去），表複製一份。"""
    (repo / ".git" / "worktrees" / name).mkdir(parents=True, exist_ok=True)
    (wt / ".claude").mkdir(parents=True, exist_ok=True)
    (wt / ".git").write_text(f"gitdir: {repo / '.git' / 'worktrees' / name}\n", encoding="utf-8")
    (wt / ".claude" / "overview-map.md").write_bytes((repo / ".claude" / "overview-map.md").read_bytes())


def test_root_worktree_ledger_follows_live_but_project_worktree_keeps_own(world, tmp_path, monkeypatch):
    import wg_core
    proj, _ = world
    live = tmp_path / "live-claude"
    (live / ".claude").mkdir(parents=True)
    (live / ".claude" / "overview-map.md").write_text(MAP, encoding="utf-8", newline="\n")
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", live)
    root_wt = tmp_path / "claude-wt" / "track-x"
    _git_worktree_of(live, root_wt, "track-x")
    (root_wt / "Game" / "Battle").mkdir(parents=True)
    assert wh.tracking_slug(str(root_wt / "Game" / "Battle")) == wh.tracking_slug(str(live))   # 根層 worktree → live 的帳本
    assert wh.tracking_slug(str(live)) != wh.tracking_slug(str(proj))
    proj_wt = tmp_path / "proj-wt"
    _git_worktree_of(proj, proj_wt, "proj-wt")
    assert wh.tracking_slug(str(proj_wt)) not in (wh.tracking_slug(str(live)), wh.tracking_slug(str(proj)))   # 反例：一般專案的 worktree 用自己的根


# ─── 結案 ────────────────────────────────────────────────────────────────────

def test_close_line_resolves_and_hides_item(world, capsys):
    proj, wf = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, _k("[戰鬥] 傷害公式在暴擊時溢位要再查\n[戰鬥] 技能冷卻表讀錯欄位", "2026-10-01T00:00:00"))
    wh.append_tracking(slug, _k("[介面] 按鈕文字被截斷要改字型\n未標部位的雜項追蹤一則", "2026-10-02T00:00:00"))
    wh.append_tracking(slug, _k("[戰鬥] 結案：傷害公式在暴擊時", "2026-10-03T00:00:00", sid="s2"))
    rows = wh.read_tracking(slug)
    closed = [r for r in rows if r["status"] == "closed"]
    assert len(closed) == 1 and closed[0]["closes"] == {"at": "2026-10-01T00:00:00", "text_prefix": "傷害公式在暴擊時"}
    open_texts = [r["text"] for r in wh.open_tracking_items(rows)]
    assert "傷害公式在暴擊時溢位要再查" not in open_texts                                   # 已結案的不列
    assert open_texts == ["技能冷卻表讀錯欄位", "按鈕文字被截斷要改字型", "未標部位的雜項追蹤一則"]
    wh.append_tracking(slug, _k("[戰鬥] 結案：技能冷卻", "2026-10-04T00:00:00"))           # 反例：前綴不足 8 字
    wh.append_tracking(slug, _k("[戰鬥] 結案：完全不存在的追蹤項目文字", "2026-10-04T00:00:00"))   # 反例：找不到對象
    err = capsys.readouterr().err
    assert "結案前綴不足 8 字" in err and "結案找不到對應的未結追蹤項" in err
    assert len(wh.read_tracking(slug)) == len(rows)                                     # 兩筆都沒寫進帳本
    wh.append_tracking(slug, _k("[介面] 結案：按鈕文字被截斷要改", "2026-10-05T00:00:00"))
    wh.append_tracking(slug, _k("結案：未標部位的雜項追蹤", "2026-10-05T00:00:00"))        # 未標部位的用不帶部位的結案行
    assert [r["text"] for r in wh.open_tracking_items(wh.read_tracking(slug))] == ["技能冷卻表讀錯欄位"]


# ─── 讀回注入 ────────────────────────────────────────────────────────────────

def test_first_injection_lists_open_items_for_that_part_only(world):
    proj, _ = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, _k("[戰鬥] 傷害公式在暴擊時溢位要再查\n[戰鬥] 技能冷卻表讀錯欄位\n"
                                "[介面] 按鈕文字被截斷\n未標部位的雜項追蹤一則", "2026-10-01T00:00:00"))
    wh.append_tracking(slug, _k("[戰鬥] 結案：技能冷卻表讀錯欄位", "2026-10-02T00:00:00"))
    state = {}
    txt = wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "A.cs")}, str(proj), "", {})
    assert "戰鬥導讀" in txt and "【未結追蹤項】" in txt and "傷害公式在暴擊時溢位要再查" in txt
    assert "技能冷卻表讀錯欄位" not in txt                                                # 反例：已結案
    assert "按鈕文字被截斷" not in txt                                                    # 反例：別部位
    assert "未標部位的雜項追蹤一則" not in txt                                            # 反例：未標部位不進部位注入
    assert wo.on_read(state, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "B.cs")}, str(proj), "", {}) is None
    txt2 = wo.on_read({}, "s", "Read", {"file_path": str(proj / "Game" / "UI" / "x.cs")}, str(proj), "", {})
    assert "按鈕文字被截斷" in txt2 and "傷害公式" not in txt2                              # part_short 不分大小寫對上


def test_more_than_five_items_shows_rest_count_and_part_case_insensitive(world):
    proj, _ = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, _k("\n".join(f"[戰鬥] 第{i}項追蹤" + "長" * 300 for i in range(7)), "2026-10-01T00:00:00"))
    txt = wo.on_read({}, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "A.cs")}, str(proj), "", {})
    block = txt[txt.index("【未結追蹤項】"):]
    assert block.count("\n- 第") == 5 and "- 另有 2 筆" in block
    assert all(len(l) <= 2 + wh.TRACK_INJECT_ITEM_CHARS + 14 for l in block.splitlines()[1:6])   # 每筆截 200 字（＋日期括號）


def test_bad_ledger_line_skipped_with_stderr_injection_still_works(world, capsys):
    proj, wf = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, _k("[戰鬥] 傷害公式在暴擊時溢位要再查", "2026-10-01T00:00:00"))
    with open(wf / "tracking" / f"{slug}.jsonl", "a", encoding="utf-8", newline="\n") as fh:
        fh.write("{not json\n[1, 2]\n")
    txt = wo.on_read({}, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "A.cs")}, str(proj), "", {})
    assert "傷害公式在暴擊時溢位要再查" in txt and "戰鬥導讀" in txt
    assert "追蹤帳本有 2 行壞掉已跳過" in capsys.readouterr().err


def test_unreadable_ledger_does_not_block_injection(world, monkeypatch, capsys):
    proj, _ = world

    def boom(*a, **kw):
        raise OSError("disk gone")
    monkeypatch.setattr(wh, "read_tracking", boom)
    txt = wo.on_read({}, "s", "Read", {"file_path": str(proj / "Game" / "Battle" / "A.cs")}, str(proj), "", {})
    assert "戰鬥導讀" in txt and "【未結追蹤項】" not in txt
    assert "讀追蹤項失敗" in capsys.readouterr().err


# ─── SessionStart 一次性提示（真 hook 進程：startup 列、compact 不列）───────────────────

def _run_hook(home: Path, payload: dict) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("WG_CLAUDE_DIR", "PYTHONPATH")}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8"})
    return subprocess.run([sys.executable, "-X", "utf8", str(HOOKS_DIR / "workflow-guardian.py")], input=json.dumps(payload),
                          env=env, cwd=payload["cwd"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=120, creationflags=NO_WINDOW)


def test_session_start_lists_unparted_items_once_and_flags_split_ledgers(world, tmp_path):
    proj, _ = world
    home = tmp_path / "home"
    tdir = home / ".claude" / "workflow" / "tracking"
    tdir.mkdir(parents=True)
    slug = wh.tracking_slug(str(proj))
    rows = _k("未標部位的雜項追蹤第一則\n未標部位的雜項追蹤第二則\n[戰鬥] 有部位的不在這裡列", "2026-10-01T00:00:00")
    rows += _k("未標部位的雜項追蹤最新一則\n未標部位的雜項追蹤再新一則", "2026-10-09T00:00:00")
    (tdir / f"{slug}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (tdir / f"{slug}-game-battle.jsonl").write_text("", encoding="utf-8")               # 舊算法子目錄 cwd 的帳本
    base = {"session_id": "trk-a3", "cwd": str(proj), "transcript_path": str(tmp_path / "t.jsonl")}
    r = _run_hook(home, {**base, "hook_event_name": "SessionStart", "source": "startup"})
    assert r.returncode == 0, r.stderr[-2000:]
    ctx = json.loads(r.stdout.strip().splitlines()[-1])["hookSpecificOutput"]["additionalContext"]
    assert "本專案未結追蹤項 4 筆" in ctx and "未標部位的雜項追蹤第一則" in ctx and "未標部位的雜項追蹤最新一則" in ctx
    assert "未標部位的雜項追蹤再新一則" not in ctx                                        # 只列最舊 3 筆
    assert "有部位的不在這裡列" not in ctx                                                # 反例：有部位的不在這裡
    assert f"{slug}-game-battle.jsonl" in r.stderr and "不自動合併" in r.stderr           # 疑似分裂只 stderr
    assert f"{slug}-game-battle.jsonl" not in ctx
    r2 = _run_hook(home, {**base, "hook_event_name": "SessionStart", "source": "compact"})
    assert r2.returncode == 0, r2.stderr[-2000:]
    assert "本專案未結追蹤項" not in r2.stdout                                             # 壓縮後不再列（一次性）
