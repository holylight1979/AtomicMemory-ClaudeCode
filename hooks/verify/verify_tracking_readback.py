"""verify_tracking_readback.py：追蹤帳本（workflow/tracking，寫入端是退縮閘那一問的「追蹤｜…」行）的命名、結案、同一件合併與讀檔防呆。

正例：子目錄 cwd 與部位表根同一本帳本；`[部位] 結案：<開頭≥8 字>` 補 closes 後該項不再算未結；行尾「｜建議：…｜該誰解：…」另存兩欄；
      「｜同追蹤項：<那筆裡至少 8 字>」恰好對到一筆就換成新說法（規則 TRACKING_SAME_ITEM_NOT_REWRITTEN）；同一句不重記。
反例：結案前綴不足 8 字或找不到對象 → stderr、不寫；字面相近但沒宣告的照記兩筆；宣告對不到唯一一筆不合併；
      帳本壞行跳過並 stderr、讀回照常；cwd 空 → _no-cwd 並 stderr；寫碼守門開時開場也不列帳上的未結項。
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
    """把 wt 接成 repo 的 git worktree 結構（git worktree add 寫的同一組檔：管理目錄的 gitdir 反向指回 wt/.git、commondir、
    wt/.git 檔指到管理目錄），表複製一份。"""
    adm = repo / ".git" / "worktrees" / name
    adm.mkdir(parents=True, exist_ok=True)
    (adm / "gitdir").write_text(f"{wt / '.git'}\n", encoding="utf-8")
    (adm / "commondir").write_text("../..\n", encoding="utf-8")
    (wt / ".claude").mkdir(parents=True, exist_ok=True)
    (wt / ".git").write_text(f"gitdir: {adm}\n", encoding="utf-8")
    (wt / ".claude" / "overview-map.md").write_bytes((repo / ".claude" / "overview-map.md").read_bytes())


def test_root_and_project_worktree_ledgers_follow_main_tree(world, tmp_path, monkeypatch):
    """git worktree 裡寫的追蹤項落在主工作樹那本帳（根層 worktree → live；一般專案 worktree → 該專案）：
    worktree 刪掉後未結項不會留在用 worktree 路徑命名的孤兒帳本。"""
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
    (proj_wt / "Game" / "UI").mkdir(parents=True)
    assert wh.tracking_slug(str(proj_wt)) == wh.tracking_slug(str(proj))                    # 一般專案 worktree → 該專案的帳本
    assert wh.tracking_slug(str(proj_wt / "Game" / "UI")) == wh.tracking_slug(str(proj))
    assert wh.tracking_slug(str(proj_wt)) != wh.tracking_slug(str(live))


def test_unregistered_worktree_or_plain_copy_keeps_own_ledger(world, tmp_path):
    """反例：只寫一個 .git 檔指過去、管理目錄沒反向登記這棵樹 → 不算那個 repo 的 worktree；沒有 .git 的複本也用自己的根。"""
    proj, _ = world
    fake = tmp_path / "fake-wt"
    adm = proj / ".git" / "worktrees" / "fake"
    adm.mkdir(parents=True)
    (adm / "gitdir").write_text(f"{tmp_path / 'elsewhere' / '.git'}\n", encoding="utf-8")   # 管理目錄登記的是別棵樹
    (adm / "commondir").write_text("../..\n", encoding="utf-8")
    (fake / ".claude").mkdir(parents=True)
    (fake / ".git").write_text(f"gitdir: {adm}\n", encoding="utf-8")
    (fake / ".claude" / "overview-map.md").write_bytes((proj / ".claude" / "overview-map.md").read_bytes())
    plain = tmp_path / "plain-copy"
    (plain / ".claude").mkdir(parents=True)
    (plain / ".claude" / "overview-map.md").write_bytes((proj / ".claude" / "overview-map.md").read_bytes())
    assert wh.tracking_slug(str(fake)) != wh.tracking_slug(str(proj))
    assert wh.tracking_slug(str(plain)) != wh.tracking_slug(str(proj))


# ─── 結案 ────────────────────────────────────────────────────────────────────

def test_close_line_resolves_and_hides_item(world, capsys):
    proj, wf = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, _k("[戰鬥] 傷害公式在暴擊時溢位要再查\n[戰鬥] 技能冷卻表讀錯欄位", "2026-10-01T00:00:00"))
    wh.append_tracking(slug, _k("[介面] 按鈕文字被截斷要改字型\n未標部位的雜項追蹤一則", "2026-10-02T00:00:00"))
    wh.append_tracking(slug, _k("[戰鬥] 結案：傷害公式在暴擊時", "2026-10-03T00:00:00", sid="s2"))
    rows = wh.read_tracking(slug)
    closed = [r for r in rows if r["status"] == "closed"]
    target = next(r for r in rows if r["text"] == "傷害公式在暴擊時溢位要再查")
    assert len(closed) == 1 and closed[0]["closes"] == {"id": wh.tracking_entry_id(target), "at": "2026-10-01T00:00:00",
                                                        "text_prefix": "傷害公式在暴擊時"}
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


def test_bad_ledger_line_skipped_with_stderr_items_still_read(world, capsys):
    proj, wf = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, _k("[戰鬥] 傷害公式在暴擊時溢位要再查", "2026-10-01T00:00:00"))
    with open(wf / "tracking" / f"{slug}.jsonl", "a", encoding="utf-8", newline="\n") as fh:
        fh.write("{not json\n[1, 2]\n")
    assert [e["text"] for e in wh.open_tracking_items(wh.read_tracking(slug))] == ["傷害公式在暴擊時溢位要再查"]
    assert "追蹤帳本有 2 行壞掉已跳過" in capsys.readouterr().err


# ─── SessionStart 不列追蹤帳本（真 hook 進程）───────────────────────────────────

def _run_hook(home: Path, payload: dict) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("WG_CLAUDE_DIR", "PYTHONPATH")}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "PYTHONIOENCODING": "utf-8", "WG_CODING_GUARD": "1"})
    return subprocess.run([sys.executable, "-X", "utf8", str(HOOKS_DIR / "workflow-guardian.py")], input=json.dumps(payload),
                          env=env, cwd=payload["cwd"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=120, creationflags=NO_WINDOW)


def test_session_start_does_not_list_open_items(world, tmp_path):
    """寫碼守門開、帳上有未標部位、標了部位、附了建議的未結項，還有疑似分裂的舊帳本：開場一行都不列、stderr 也不提
    （舊碼開場先列附了建議的、再列未標部位與標了部位的各一段，要 AI 第一則回覆轉述）。"""
    proj, _ = world
    home = tmp_path / "home"
    tdir = home / ".claude" / "workflow" / "tracking"
    tdir.mkdir(parents=True)
    slug = wh.tracking_slug(str(proj))
    rows = _k("未標部位的雜項追蹤第一則\n[戰鬥] 有部位的一則\n舊月報照要求保留｜建議：改月報｜該誰解：使用者決定",
              "2026-10-01T00:00:00")
    (tdir / f"{slug}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (tdir / f"{slug}-game-battle.jsonl").write_text("", encoding="utf-8")
    r = _run_hook(home, {"session_id": "trk-a3", "cwd": str(proj), "transcript_path": str(tmp_path / "t.jsonl"),
                         "hook_event_name": "SessionStart", "source": "startup"})
    assert r.returncode == 0, r.stderr[-2000:]
    ctx = json.loads(r.stdout.strip().splitlines()[-1])["hookSpecificOutput"]["additionalContext"]
    assert ctx.startswith("[Workflow Guardian] Active.")
    for text in ("[Guardian:Tracking]", "未標部位的雜項追蹤第一則", "有部位的一則", "舊月報照要求保留"):
        assert text not in ctx, text
    assert "[Guardian:Tracking]" not in r.stderr


# ─── 退件 015：一筆結案只消一筆、短項可結、中文路徑不撞本、worktree 帳本不看部位表、結構錯的列要報 ───────

def _open_texts(slug):
    return [r["text"] for r in wh.open_tracking_items(wh.read_tracking(slug))]


def test_one_close_removes_exactly_one_item_even_same_batch_same_prefix(world):
    proj, _ = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, _k("[hooks] PowerShell 讀取失敗待查\n[hooks] PowerShell 寫入失敗待查", "2026-10-01T00:00:00"))
    rows = wh.read_tracking(slug)
    assert len({r["id"] for r in rows}) == 2                                            # 同批同時間也各有 id
    wh.append_tracking(slug, _k("[hooks] 結案：PowerShell", "2026-10-02T00:00:00"))
    assert _open_texts(slug) == ["PowerShell 寫入失敗待查"]                              # 反例：舊碼兩筆一起消失
    wh.append_tracking(slug, _k("[hooks] 結案：PowerShell", "2026-10-03T00:00:00"))
    assert _open_texts(slug) == []


def test_legacy_rows_without_id_close_one_at_a_time(world):
    proj, wf = world
    slug = wh.tracking_slug(str(proj))
    (wf / "tracking").mkdir(parents=True, exist_ok=True)
    legacy = [{"session_id": "old", "turn_seq": 3, "at": "2026-09-01T00:00:00", "part": "hooks", "text": t, "status": "open"}
              for t in ("舊格式追蹤項目第一則內容", "舊格式追蹤項目第二則內容")]
    (wf / "tracking" / f"{slug}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in legacy),
                                                  encoding="utf-8")
    wh.append_tracking(slug, _k("[hooks] 結案：舊格式追蹤項目第", "2026-10-02T00:00:00"))   # 兩筆都對得上，只結最舊那筆
    assert _open_texts(slug) == ["舊格式追蹤項目第二則內容"]
    closer = [r for r in wh.read_tracking(slug) if r["status"] == "closed"][0]
    assert closer["closes"]["id"] == wh.tracking_entry_id(legacy[0])                    # 舊列的 id 是由欄位算出來的固定值


def test_short_item_closes_with_full_text_but_not_with_short_prefix(world, capsys):
    proj, _ = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, _k("[hooks] 補測試\n[hooks] 補文件", "2026-10-01T00:00:00"))
    wh.append_tracking(slug, _k("[hooks] 結案：補測試", "2026-10-02T00:00:00"))            # 全文（不足 8 字）可結
    assert _open_texts(slug) == ["補文件"]
    wh.append_tracking(slug, _k("[hooks] 結案：補", "2026-10-03T00:00:00"))                # 反例：短前綴又不是全文
    assert _open_texts(slug) == ["補文件"] and "也不是原項目全文" in capsys.readouterr().err


def test_slug_lossy_paths_get_full_path_hash_ascii_unchanged(tmp_path):
    a, b = tmp_path / "專案甲", tmp_path / "專案乙"
    a.mkdir()
    b.mkdir()
    sa, sb = wh.tracking_slug(str(a)), wh.tracking_slug(str(b))
    assert sa != sb and all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", s) for s in (sa, sb))
    short_a, short_b = wh.tracking_slug("D:\\專案甲"), wh.tracking_slug("D:\\專案乙")       # 短路徑不會截短：只靠有損時加雜湊
    assert short_a != short_b, (short_a, short_b)                                        # 反例：舊碼兩者都是 d-----
    live = Path.home() / ".claude"
    if (live / ".claude" / "overview-map.md").is_file():                                 # 唯讀：根層 slug 逐字不變
        assert wh.tracking_slug(str(live)) == "c--" + str(live).split(":\\", 1)[1].replace("\\", "-").replace(".", "-").lower()
    long_ascii = tmp_path / ("a" * 80)
    long_ascii.mkdir()
    s = wh.tracking_slug(str(long_ascii))
    import wg_core
    raw = wg_core.cwd_to_project_slug(str(long_ascii))
    assert len(s) == 64 and s[:55] == raw[:55] and s[55] == "-"                          # 超長 ASCII：截 55＋雜湊


def test_root_worktree_ledger_ignores_map_content_fixture_does_not_use_live(world, tmp_path, monkeypatch):
    import wg_core
    live = tmp_path / "live-claude"
    (live / ".claude").mkdir(parents=True)
    (live / ".claude" / "overview-map.md").write_text(MAP, encoding="utf-8", newline="\n")
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", live)
    wt = tmp_path / "claude-wt" / "x"
    _git_worktree_of(live, wt, "x")
    (wt / ".claude" / "overview-map.md").write_text(MAP + "| `new/` | 新部位 | 無 | 無 |\n", encoding="utf-8")   # 表與 live 不同
    assert wh.tracking_slug(str(wt)) == wh.tracking_slug(str(live))                    # 仍是 live 的帳本（反例：舊碼換本）
    fixture = live / "fixture"
    (fixture / ".claude").mkdir(parents=True)
    (fixture / ".claude" / "overview-map.md").write_text(MAP, encoding="utf-8", newline="\n")   # 表相同但不是 worktree
    assert wh.tracking_slug(str(fixture)) != wh.tracking_slug(str(live))


def test_structurally_bad_rows_are_skipped_with_stderr(world, capsys):
    proj, wf = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, _k("[戰鬥] 好好的一筆追蹤項目文字", "2026-10-01T00:00:00"))
    with open(wf / "tracking" / f"{slug}.jsonl", "a", encoding="utf-8", newline="\n") as fh:
        fh.write("{}\n")
        fh.write(json.dumps({"status": "opened", "text": "x", "at": "y"}) + "\n")
        fh.write(json.dumps({"status": "closed", "text": "x", "at": "y", "closes": "not-a-dict"}) + "\n")
    assert _open_texts(slug) == ["好好的一筆追蹤項目文字"]
    assert "追蹤帳本有 3 行壞掉已跳過" in capsys.readouterr().err                          # 反例：舊碼靜默收下


# ─── 退件 017：帳本列型別與逐行編碼 ─────────────────────────────────────────────────

def test_ledger_rows_with_wrong_types_or_broken_bytes_report_line_numbers(world, capsys):
    proj, wf = world
    slug = wh.tracking_slug(str(proj))
    wh.append_tracking(slug, _k("[戰鬥] 第一行是好好的追蹤項目", "2026-10-01T00:00:00"))
    good = json.dumps({"status": "open", "text": "第五行文字壞位元組", "at": "2026-10-02T00:00:00", "part": "戰鬥"},
                      ensure_ascii=False).encode("utf-8")
    broken = good.replace("壞位元組".encode("utf-8"), b"\xff\xfe")                          # JSON 結構完好、文字有損壞位元組
    with open(wf / "tracking" / f"{slug}.jsonl", "ab") as fh:
        for row in ({"status": "closed", "text": "結案：x", "at": "y", "closes": {}},          # 第 2 行：closes 沒有 id
                    {"status": "open", "text": None, "at": "y"},                           # 第 3 行：text=null
                    {"status": "open", "text": "z", "at": []}):                            # 第 4 行：at 不是字串
            fh.write(json.dumps(row, ensure_ascii=False).encode("utf-8") + b"\n")
        fh.write(broken + b"\n")                                                           # 第 5 行
    texts = _open_texts(slug)
    assert texts[0] == "第一行是好好的追蹤項目" and len(texts) == 2 and texts[1].startswith("第五行文字")   # 損壞行照收
    err = capsys.readouterr().err
    assert "追蹤帳本有 3 行壞掉已跳過" in err and "第 2, 3, 4 行" in err                      # 反例：舊碼三列都收下、不出聲
    assert "第 5 行編碼損壞" in err                                                          # 反例：舊碼 replace 解碼不出聲


# ─── 行尾提議欄與同一件合併（規則 TRACKING_SAME_ITEM_NOT_REWRITTEN）──────────────────────────────
_SID = "sid-track"


def _opens(proj):
    return wh.open_tracking_items(wh.read_tracking(wh.tracking_slug(str(proj))))


def _append_k(proj, text, sid=_SID, at=None):
    return wh.append_tracking(wh.tracking_slug(str(proj)), wh.tracking_entries(sid, 1, text, at=at))


def test_k_line_proposal_and_owner_split_before_part():
    rows = wh.tracking_entries("s", 1, "gitlab 鏡像 push 憑證失效｜建議：換 token 後重推｜該誰解：使用者\n"
                                       "[hooks] 寫入失敗待查｜該誰解：根層｜建議：加重試\n"
                                       "hooks｜舊格式部位行\n[hooks] 結案：寫入失敗待查", at="2026-10-20T00:00:00")
    assert (rows[0]["part"], rows[0]["text"]) == ("", "gitlab 鏡像 push 憑證失效")   # 反例：舊碼把問題當成部位、本文剩「建議：…」
    assert (rows[0]["proposal"], rows[0]["owner"]) == ("換 token 後重推", "使用者")
    assert (rows[1]["part"], rows[1]["text"], rows[1]["proposal"], rows[1]["owner"]) == ("hooks", "寫入失敗待查", "加重試", "根層")
    assert (rows[2]["part"], rows[2]["text"]) == ("hooks", "舊格式部位行") and "proposal" not in rows[2]   # 沒寫提議照舊
    assert rows[3]["status"] == "closed" and "proposal" not in rows[3]


# 第二波第五跑 B5（workflow/tracking/c--w4-qb2-sales.jsonl）同一件記成 3 筆的原文
_B5_FOLLOWUP = "需求目標 T1.4（部分）：monthly 走 UTC 違反 README，改不改要使用者跟財務確認後拍板（已在收尾報告提出）"
_B5_K = ("[銷售報表] monthly 用 UTC 切月份違反 README 台北時間規則（2026-09 報 520、應為 205；2026-10 報 420、應為 735），"
         "需財務確認後修 month_of 與 test_monthly_cli_output 期望值")
_B5_THIRD = "[銷售報表] `sales/periods.py` 的 `month_of` 用 UTC 判斷月份，monthly 報表整條路都靠它"


def test_006_b5_paraphrases_need_ai_declaration(world):
    """前置：B5 三筆措辭全不同，字面規則併不掉（程式不猜語意）——照原樣寫還是 3 筆未結。"""
    proj, _ = world
    for text in (_B5_FOLLOWUP, _B5_K, _B5_THIRD):
        _append_k(proj, text)
    assert len(_opens(proj)) == 3


def test_006_b5_same_item_declared_keeps_one_open(world):
    """行尾寫「同追蹤項：<那筆裡至少 8 字>」→ 換成新說法，帳上始終只留 1 筆未結（最新那句、帶部位）。"""
    proj, _ = world
    _append_k(proj, _B5_FOLLOWUP)
    _append_k(proj, _B5_K + "｜同追蹤項：monthly 走 UTC 違反 README")
    opens = _opens(proj)
    assert len(opens) == 1 and opens[0]["text"].startswith("monthly 用 UTC 切月份") and opens[0]["part"] == "銷售報表"
    _append_k(proj, _B5_THIRD + "｜同追蹤項：monthly 用 UTC 切月份違反 README")
    opens = _opens(proj)
    assert len(opens) == 1 and opens[0]["text"].startswith("`sales/periods.py`") and opens[0].get("supersedes")
    closed = [r for r in wh.read_tracking(wh.tracking_slug(str(proj))) if r["status"] == "closed"]
    assert len(closed) == 2 and all(r.get("superseded_by") for r in closed)


def test_006_exact_repeat_is_not_rewritten(world, capsys):
    """同一句第二次不重記、照回帳本路徑（不算寫入失敗）、stderr 說一聲。"""
    proj, _ = world
    assert _append_k(proj, _B5_FOLLOWUP) and _append_k(proj, _B5_FOLLOWUP)
    assert len(_opens(proj)) == 1 and "帳上已有同一件未結項，不重記" in capsys.readouterr().err


@pytest.mark.parametrize("first, second, sid2", [
    ("匯出按鈕沒有反應", "[財務介面] 匯出按鈕沒有反應", "other-sid"),             # 舊的沒標部位：分不出是不是同一件
    ("[登入] 登入流程發生錯誤（密碼過期）", "[登入] 登入流程發生錯誤（帳號鎖定）", _SID),   # 只差括號註：可能是兩件
    ("[登入] 驗證碼逾時未處理上限", "[登入] 驗證碼逾時未處理下限", _SID),           # 開頭相同的不同問題
], ids=["unpartitioned-old", "aside-differs", "prefix-same"])
def test_006_similar_but_not_declared_is_kept(world, first, second, sid2):
    """沒宣告時程式只併「部位相同、原文相同」；字面相近的照記兩筆（併錯會吞掉一件，比多記一筆更糟）。"""
    proj, _ = world
    _append_k(proj, first)
    _append_k(proj, second, sid=sid2)
    assert len(_opens(proj)) == 2


@pytest.mark.parametrize("first, line", [
    ("[銷售報表] 匯出 monthly 報表用 UTC 切月\n[銷售報表] 匯入 monthly 報表用 UTC 切月",
     "[銷售報表] 新說法｜同追蹤項：monthly 報表用 UTC 切月"),                  # 對到兩筆：分不出是哪一筆
    ("[戰鬥] 暴擊分支把共用字典當暫存", "[介面] 按鈕狀態｜同追蹤項：暴擊分支把共用字典"),   # 部位不同：不是同一件
    ("[戰鬥] 暴擊分支把共用字典當暫存", "[戰鬥] 新說法｜同追蹤項：共用字典"),               # 去標點不足 8 字
], ids=["ambiguous", "other-part", "too-short"])
def test_006_same_as_not_merged_when_unclear(world, capsys, first, line):
    """宣告對不到唯一一筆 → 不合併（不悄悄關掉別件）、照記新的、stderr 說原因。"""
    proj, _ = world
    _append_k(proj, first)
    before = len(_opens(proj))
    _append_k(proj, line)
    assert len(_opens(proj)) == before + 1 and "沒有合併、照記新的" in capsys.readouterr().err


def test_006_same_as_merges_when_part_is_refined(world):
    """部位寫細（「合服」→「合服工具 DataHandler」）又明寫「同追蹤項」且唯一命中 → 換成新說法、只留 1 筆、部位用新的。
    部位不相干（戰鬥／介面）仍不併，見 other-part 案。"""
    proj, _ = world
    _append_k(proj, "[合服] ClientDataHandlerEx.InitOp 對 Hero、Bag 四個模組用 get-or-new，來源沒有的角色被長出空模組")
    _append_k(proj, "[合服工具 DataHandler] ClientDataHandlerEx.cs 的 InitOp 缺席模組補空模組｜同追蹤項：InitOp 對 Hero、Bag 四個模組")
    opens = _opens(proj)
    assert len(opens) == 1 and opens[0]["part"] == "合服工具 DataHandler" and opens[0].get("supersedes")


def test_superseded_row_stays_closed_after_ledger_pruning(world):
    """清理器（handlers/_shared._prune_tracking_pairs）把結案超過 90 天的「結案列＋開項」成對拿掉；被取代的那筆不會因此又變回未結。"""
    from datetime import datetime
    from handlers import _shared
    proj, wf = world
    _append_k(proj, "[pricing] catalog.py 的 PRICES 價格表寫死在程式裡（defects.md 剩下的唯一一項）", at="2026-01-01T00:00:00+08:00")
    _append_k(proj, "[pricing] catalog.py 的 PRICES 價格表寫死在程式裡｜同追蹤項：PRICES 價格表寫死在程式裡",
              at="2026-01-01T00:00:10+08:00")
    res = {"deleted": [], "compacted": {}, "failed": []}
    _shared._prune_tracking_pairs(wf / "tracking", 90, datetime(2026, 10, 21).timestamp(), False, res)
    assert res["compacted"], "前置：清理器真的拿掉了那一對"
    assert [r["text"] for r in wh.read_tracking(wh.tracking_slug(str(proj)))] == ["catalog.py 的 PRICES 價格表寫死在程式裡"]
    assert [r["text"] for r in _opens(proj)] == ["catalog.py 的 PRICES 價格表寫死在程式裡"]
