"""verify_dir_target_root.py：刪整個資料夾時改檔閘看它所在的位置（DIR_TARGET_JUDGED_BY_CONTAINER），
Bash 與 PowerShell 的刪除寫法認得一樣（DELETE_FORMS_SAME_ACROSS_SHELLS）。

實際誤擋：工作樹已除名、資料夾刪不乾淨的殘留（裡面還有 .git 檔、_AIDocs、部位表），`rm -rf <殘留>` 被當成改那個「專案」的檔，
要求先讀「(outside)」目錄的檔（永遠讀不到）；換 PowerShell 的 rd／ri／del 寫法則整條沒被認成寫入、閘看不到。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_dir_target_root.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))   # worktree 內跑：wg_core 的 lib／workflow 指本樹
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_core  # noqa: E402
import wg_overview as wo  # noqa: E402

_NO_MIN_MAP = {"overview_hub": {"min_map": {"enabled": False}}}


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """假專案建在 pytest tmp 下：關掉暫存規則；不接公司層；守門紀錄寫到 tmp。"""
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")


def _leftover(base: Path) -> Path:
    """工作樹已除名的殘留資料夾：.git 檔指到不存在的管理目錄、還留著 _AIDocs 與程式檔，所在的上一層沒有任何專案標記。"""
    d = base / "wt-container" / "leftover"
    (d / "_AIDocs").mkdir(parents=True)
    (d / "src").mkdir()
    (d / ".git").write_text(f"gitdir: {base / 'gone' / '.git' / 'worktrees' / 'leftover'}\n", encoding="utf-8")
    (d / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    return d


def test_dir_target_judged_by_container(tmp_path):
    """殘留資料夾整個刪掉 → 看它所在的上一層（沒有專案）→ 放行；裡面的單一檔照舊看殘留自己的標記（還是要先讀）。
    cwd 這類「我在哪」的目錄照舊拿目錄自己當根。"""
    d = _leftover(tmp_path)
    assert wo.on_edit({}, "s", str(d), "", _NO_MIN_MAP) == (None, None, False)
    warn, deny, _ = wo.on_edit({}, "s", str(d / "src" / "new.py"), "", _NO_MIN_MAP)
    assert deny and "「src」至少 1 個檔" in deny
    assert wo._unmapped_root_of(str(d)) == d and wo.write_target_root(str(d)) is None


def test_dir_target_inside_real_project_still_gated(tmp_path):
    """反例：專案裡的子資料夾（自己也帶 _AIDocs 標記）整個刪 → 根是外面那個專案，照無表規則要先讀過根目錄一檔；讀了才放行。"""
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / "README.md").write_text("# p\n", encoding="utf-8")
    sub = proj / "sub"
    (sub / "_AIDocs").mkdir(parents=True)
    assert wo.write_target_root(str(sub)) == proj
    state: dict = {}
    warn, deny, _ = wo.on_edit(state, "s", str(sub), "", _NO_MIN_MAP)
    assert deny and str(proj) in deny and "「(root)」至少 1 個檔" in deny
    wo.on_read(state, "s", "Read", {"file_path": str(proj / "README.md")}, str(proj), "", {})
    assert wo.on_edit(state, "s", str(sub), "", _NO_MIN_MAP)[1] is None


def test_delete_forms_same_across_shells(tmp_path):
    """同一個資料夾，Bash 的 rm -rf／rmdir 與 PowerShell 的 Remove-Item 及別名 ri、del、erase、rd、rmdir、rm 認出同一個寫入目標；
    Set-Location 之後的相對目標照換過的目錄算；目標從管線進來、[System.IO.Directory]:: 判不出 → UNKNOWN（放行留帳，不是沒看到）。"""
    d = _leftover(tmp_path)
    win, posix = str(d), d.as_posix()
    bash = [f"rm -rf '{posix}'", f"rm -r '{posix}'", f"rm -r -f '{posix}'", f"rmdir '{posix}'"]   # rm -r 的 -r 不帶值
    ps = [f"Remove-Item -Recurse -Force '{win}'"] + [f"{a} -r '{win}'" for a in ("ri", "del", "erase", "rd", "rm")] + [
        f"rmdir '{win}' -Recurse -Force", f"Set-Location '{d.parent}'; Remove-Item leftover -Recurse -Force",
        f"Set-Location -LiteralPath '{d.parent}'; ri leftover -Recurse"]
    got = {c: wg_core.write_paths_from_tool("Bash", {"command": c}, cwd=str(tmp_path)) for c in bash}
    got.update({c: wg_core.write_paths_from_tool("PowerShell", {"command": c}, cwd=str(tmp_path)) for c in ps})
    bad = {c: t for c, t in got.items() if [os.path.normcase(x) for x in t] != [os.path.normcase(win)]}
    assert not bad, bad
    for c in (f"Get-Item '{win}' | Remove-Item -Recurse -Force", f"[System.IO.Directory]::Delete('{win}', $true)"):
        t = wg_core.write_paths_from_tool("PowerShell", {"command": c}, cwd=str(tmp_path))
        assert len(t) == 1 and t[0].startswith("UNKNOWN:"), (c, t)
