"""verify_svn_unicode_paths.py — vcs-sync worker 的 svn 通道對非 ASCII 路徑的重現矩陣。

背景：TSLG 工作副本曾出現 `shared/UIºt¥X`（＝`UI演出` 的 Big5 位元組被當 cp1252 解碼）。
本檔用 tmp 的 `svnadmin create` 實倉，讓 wg_vcs_sync 的 svn 路徑（`_Svn.run` → add --parents → commit -F）
對含非 ASCII 名字的目錄提交 .md，矩陣三格：
  - `UI演出`（ANSI code page 內的中文，TSLG 實際出事的名字）：全程通過——磁碟名不變、`svn status --xml -v`
    與 `svn ls --xml` 回原名、第二個 checkout 拿到原名。
  - `ゔ外字`（U+3094，cp950 外；注意「ヴ」U+30F4 其實在 cp950 內）與 `é外字`（best-fit 會被 svn 改成 `e外字`）：
    svn.exe 以 ANSI code page 收 argv，`--targets` 檔也走原生編碼，兩者都定址不到真正的路徑；
    `add --parents` 還會照 best-fit 後的名字在磁碟建出亂碼目錄。worker 必須在呼叫 svn 前就停下
    （status=unpushed、last_error 說明路徑），磁碟不得多出任何東西。
  - 原生 svn 證據題：直接 `svn add --parents memory/é外字/n.md` 真的建出 `e外字`——這是上面守門存在的理由；
    svn 哪天改成 Unicode argv 這題會紅，屆時可拆守門。
只在 win32 跑（亂碼來自 Windows 的 ANSI code page 轉換）；svn 不在本機 → skip。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CLAUDE / "hooks"))

import wg_vcs_sync as vs  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="亂碼路徑問題只出在 Windows code page")

SVN = vs._svn_exe()
HAS_SVN = shutil.which(SVN) is not None or Path(SVN).exists()
CFG = {"vcs_sync": {"enabled": True, "push": True, "exclude": ["**/*.access.json"], "timeout_s": 60}}


@pytest.fixture(autouse=True)
def sync_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(vs, "SYNC_DIR", tmp_path / "_sync")
    monkeypatch.setattr(vs, "LEDGER_DIR", tmp_path / "_ledger")
    import wg_atoms
    monkeypatch.setattr(wg_atoms, "_trigger_incremental_index", lambda cfg: None)
    vs._held_locks.clear()


def _svn(cwd: Path, *args, check=True) -> subprocess.CompletedProcess:
    r = subprocess.run([SVN, "--non-interactive", *args], cwd=str(cwd), capture_output=True, env=vs.worker_env())
    if check:
        assert r.returncode == 0, f"svn {' '.join(args)} failed: {r.stderr.decode(vs._SVN_ARGV_ENCODING, 'replace')}"
    return r


def _url(repo_dir: Path) -> str:
    return "file:///" + repo_dir.resolve().as_posix().lstrip("/")


@pytest.fixture
def svn_wc(tmp_path):
    if not HAS_SVN:
        pytest.skip("svn 不在本機")
    repo_dir = tmp_path / "svnrepo"
    subprocess.run([str(Path(SVN).with_name("svnadmin" + Path(SVN).suffix)), "create", str(repo_dir)],
                   check=True, capture_output=True)
    wc = tmp_path / "wc"
    _svn(tmp_path, "checkout", "-q", _url(repo_dir), str(wc))
    (wc / "memory").mkdir()
    (wc / "memory" / "seed.md").write_text("# seed\n", encoding="utf-8")
    _svn(wc, "add", "-q", "memory")
    _svn(wc, "commit", "-q", "-m", "seed", "memory")
    return wc, repo_dir


def _put(wc: Path, name: str) -> None:
    (wc / "memory" / name).mkdir()
    (wc / "memory" / name / f"{name}-note.md").write_text(f"# {name}\n", encoding="utf-8")


def _sync(wc: Path):
    logs = []
    t = vs.SyncTarget("svn", wc.resolve(), ["memory"], [(wc / "memory").resolve()])
    return vs.sync_targets_inline([t], CFG, log=logs.append), logs


def _disk_dirs(wc: Path) -> set:
    return {p.name for p in (wc / "memory").iterdir() if p.is_dir()}


def _status_items(wc: Path) -> dict:
    """`svn status --xml -v memory` → {相對 memory/ 的路徑: item}。"""
    out = {}
    for ent in ET.fromstring(_svn(wc, "status", "--xml", "-v", "memory").stdout).iter("entry"):
        p = Path(ent.get("path", ""))
        if p.parts[:1] == ("memory",) and len(p.parts) > 1:
            out[Path(*p.parts[1:]).as_posix()] = ent.find("wc-status").get("item")
    return out


def _ls_names(repo_dir: Path) -> set:
    root = ET.fromstring(_svn(repo_dir, "ls", "--xml", f"{_url(repo_dir)}/memory").stdout)
    return {e.text for e in root.iter("name")}


def test_cp950_cjk_dir_round_trips_through_worker(svn_wc, tmp_path):
    wc, repo_dir = svn_wc
    name = "UI演出"
    _put(wc, name)
    res, logs = _sync(wc)
    assert res[0]["status"] == "ok" and res[0]["added"] == 1, (res, logs)
    assert _disk_dirs(wc) == {name}
    assert _status_items(wc)[name] == "normal"
    assert name in _ls_names(repo_dir), _ls_names(repo_dir)
    wc2 = tmp_path / "wc2"
    _svn(tmp_path, "checkout", "-q", _url(repo_dir), str(wc2))
    f = wc2 / "memory" / name / f"{name}-note.md"
    assert f.is_file() and f.read_text(encoding="utf-8") == f"# {name}\n"


@pytest.mark.parametrize("name", ["ゔ外字", "é外字"])
def test_non_ansi_dir_worker_stops_before_svn_no_garbage(svn_wc, name):
    wc, repo_dir = svn_wc
    if vs._svn_argv_encodable(name):
        pytest.skip(f"本機 ANSI code page {vs._SVN_ARGV_ENCODING} 編得出 {name}，不是本題要的外字元")
    _put(wc, name)
    res, logs = _sync(wc)
    assert res[0]["status"] == "unpushed", (res, logs)
    err = res[0].get("reason") or ""
    assert "無法定址" in err and name in err, (res, logs)
    assert _disk_dirs(wc) == {name}                       # 沒多出 best-fit 亂碼目錄
    assert _status_items(wc).get(name) == "unversioned"   # 沒被半套 add
    assert name not in _ls_names(repo_dir)
    assert vs.marker_path(wc, "unpushed").exists()


def test_raw_svn_add_parents_best_fit_creates_garbage_dir(svn_wc):
    """守門存在的證據：svn.exe 自己對 `é外字` 做 best-fit → 在磁碟建出 `e外字`。"""
    wc, _repo_dir = svn_wc
    if vs._svn_argv_encodable("é外字"):
        pytest.skip(f"本機 ANSI code page {vs._SVN_ARGV_ENCODING} 編得出 é，無 best-fit 可證")
    _put(wc, "é外字")
    r = _svn(wc, "add", "--depth", "empty", "--parents", "--", "memory/é外字/é外字-note.md", check=False)
    assert r.returncode != 0
    assert _disk_dirs(wc) == {"é外字", "e外字"}, _disk_dirs(wc)
