"""verify_second_opinion_new_files.py：第二意見的 diff 材料要帶未追蹤的新檔。

git diff HEAD（與 main...HEAD、svn diff）都不含沒加進版控的檔：新建的程式與測試審查者看不到，只審得到改舊檔那半。
現在 collect_diff 把未追蹤新檔（git ls-files --others --exclude-standard、svn status 的 `?`）接成 new file patch 段；
被 .gitignore 排除的不帶，二進位與過大的只列檔名。
怎麼跑：python -X utf8 -m pytest -q tools/codex-companion/verify/verify_second_opinion_new_files.py
（真 git 在 tmp_path 建一個小 repo，不碰任何工作副本）
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]  # tools/codex-companion/verify/ → repo 根
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("so_pack_new_files", ROOT / "tools" / "second-opinion" / "pack.py")
pack = importlib.util.module_from_spec(_spec)
sys.modules["so_pack_new_files"] = pack
_spec.loader.exec_module(pack)  # type: ignore[union-attr]

VCS = "g" + "it"


def _vcs(repo: Path, *args: str) -> None:
    subprocess.run([VCS, "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "proj"
    r.mkdir()
    _vcs(r, "init", "-q")
    _vcs(r, "config", "user.email", "t@example.com")
    _vcs(r, "config", "user.name", "t")
    _vcs(r, "config", "core.autocrlf", "false")
    (r / "old.py").write_text("def f():\n    return 1\n", encoding="utf-8", newline="\n")
    (r / ".gitignore").write_text("*.log\n", encoding="utf-8", newline="\n")
    _vcs(r, "add", "old.py", ".gitignore")
    _vcs(r, "commit", "-q", "-m", "base")
    return r


def test_untracked_new_file_is_in_diff_material(repo):
    (repo / "old.py").write_text("def f():\n    return 2\n", encoding="utf-8", newline="\n")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "新模組.py").write_text("def g():\n    return '新'\n", encoding="utf-8", newline="\n")
    (repo / "run.log").write_text("noise\n", encoding="utf-8")
    out = pack.collect_diff(str(repo))
    assert "+    return 2" in out, "改舊檔的 diff 照舊在"
    assert "diff --git a/pkg/新模組.py b/pkg/新模組.py\nnew file mode 100644\n--- /dev/null\n+++ b/pkg/新模組.py\n" in out, out
    assert "@@ -0,0 +1,2 @@\n+def g():\n+    return '新'\n" in out, f"未追蹤新檔的內容沒進材料：\n{out}"
    assert "run.log" not in out, ".gitignore 排除的檔不帶"


def test_new_files_only_still_produce_material(repo):
    """沒改舊檔、只新建檔（git diff HEAD 與 main...HEAD 都空）：材料不能是空的。"""
    (repo / "tests").mkdir()
    (repo / "tests" / "test_new.py").write_text("def test_x():\n    assert True\n", encoding="utf-8", newline="\n")
    out = pack.collect_diff(str(repo))
    assert "+++ b/tests/test_new.py" in out and "+    assert True" in out, out


def test_binary_and_oversize_new_files_list_name_only(repo, monkeypatch):
    (repo / "img.bin").write_bytes(b"\x89PNG\0\0data")
    out = pack.collect_diff(str(repo))
    assert "+++ b/img.bin\n（二進位新檔，未附內容）\n" in out, out
    (repo / "big.txt").write_text("x" * 50 + "\n", encoding="utf-8", newline="\n")
    monkeypatch.setattr(pack, "NEW_FILES_BUDGET", 20)
    seg = pack._new_file_patch(repo, "big.txt")
    assert seg.endswith("+++ b/big.txt\n（未追蹤新檔過大，未附內容：51 bytes）\n"), seg


def test_new_files_budget_is_a_hard_cap(tmp_path, monkeypatch):
    for name in ("a.txt", "b.txt", "c.txt"):
        (tmp_path / name).write_text("line\n", encoding="utf-8", newline="\n")
    one = len(pack._new_file_patch(tmp_path, "a.txt"))
    monkeypatch.setattr(pack, "NEW_FILES_BUDGET", one + 5)
    out = pack._new_files_patch(tmp_path, ["c.txt", "a.txt", "b.txt", "gone.txt"])
    assert out.startswith("diff --git a/a.txt b/a.txt") and "b.txt" not in out.split("（另有")[0]
    assert len(out.split("（另有")[0]) <= one + 5, "累計不得超過上限（放不下就停）"
    assert "（另有 2 個未追蹤新檔未附：新檔材料累計會超過" in out, "放不下的只報個數；列了但不存在的檔不算"


def test_new_file_patch_marks_missing_eol_and_empty_file(tmp_path):
    (tmp_path / "noeol.txt").write_bytes(b"x")
    (tmp_path / "crlf.txt").write_bytes(b"a\r\nb\r\n")
    (tmp_path / "empty.txt").write_bytes(b"")
    assert pack._new_file_patch(tmp_path, "noeol.txt").endswith("@@ -0,0 +1,1 @@\n+x\n\\ No newline at end of file\n")
    assert pack._new_file_patch(tmp_path, "crlf.txt").endswith("@@ -0,0 +1,2 @@\n+a\n+b\n")
    assert pack._new_file_patch(tmp_path, "empty.txt").endswith("+++ b/empty.txt\n"), "空檔只有檔頭、沒有內容段"


def test_svn_unversioned_lists_dirs_by_name_only(tmp_path, monkeypatch):
    """svn 只列未加入的目錄本身，裡面哪些檔被 ignore 判不了：目錄只列名、不展開（不把被忽略的檔帶進材料）。"""
    (tmp_path / ".svn").mkdir()
    (tmp_path / "newdir").mkdir()
    (tmp_path / "newdir" / "x.py").write_text("x = 1\n", encoding="utf-8", newline="\n")
    (tmp_path / "newdir" / "private.log").write_text("secret\n", encoding="utf-8", newline="\n")
    (tmp_path / "y.py").write_text("y = 1\n", encoding="utf-8", newline="\n")
    status = "M       old.py\n?       y.py\n?       newdir\n!       ignored.tmp\n"
    assert pack._svn_unversioned(tmp_path, status) == (["y.py"], ["newdir"])
    fake = {"diff": "Index: old.py\n", "status": status}
    monkeypatch.setattr(pack, "_run", lambda cmd, cwd, t: fake.get(cmd[1], "") if cmd[0] == "svn" else "")
    out = pack.collect_diff(str(tmp_path))
    assert out.startswith("Index: old.py\n") and "+++ b/y.py\n@@ -0,0 +1,1 @@\n+y = 1\n" in out, out
    assert "未加入版控的目錄 newdir/" in out and "secret" not in out and "x = 1" not in out, out
