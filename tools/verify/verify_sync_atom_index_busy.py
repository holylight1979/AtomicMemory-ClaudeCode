"""verify_sync_atom_index_busy.py：索引換檔撞上別的行程開著檔、補登補不齊、半套鏡像。

背景：`sync-atom-index.py --add-from-frontmatter` 逐顆 upsert，每顆都整檔重寫 `_atom_index.json` 與 `_ATOM_INDEX.md`；
Windows 上別的行程（每回合讀索引的 hook、索引器）開著檔時 os.replace 會 PermissionError（WinError 5），
工具整支中斷、補到哪算哪（空索引 291 張補出 130／97／142）。
正例：開著讀鏡像時換檔會稍等重試成功；空索引補齊張數＝檔數、整批只落一次檔；有外部讀者時 CLI 照樣補齊；
反例：md 鏡像換不成時 JSON 不留半套、重跑會把鏡像補回；索引讀不到（損毀）時不拿空索引覆寫。
CLI 以 subprocess 跑 `--memory-dir <tmp>`（WG_CLAUDE_DIR 指 tmp），不碰 live 索引。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_sync_atom_index_busy.py
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

CLAUDE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(CLAUDE_ROOT) not in sys.path:
    sys.path.insert(0, str(CLAUDE_ROOT))

from lib import atom_index_json as aij  # noqa: E402

SYNC = CLAUDE_ROOT / "tools" / "sync-atom-index.py"
WIN = sys.platform == "win32"


def _load_sync():
    spec = importlib.util.spec_from_file_location("sync_atom_index_busy_ut", SYNC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod  # dataclass 需要 sys.modules 能找到定義模組
    spec.loader.exec_module(mod)
    return mod


def _card(title: str) -> str:
    return (f"# {title}\n\n- Scope: shared\n- Confidence: [臨]\n- Trigger: {title}, t2\n"
            f"- Created-at: 2026-10-01\n\n## 知識\n\n- [臨] k\n\n## 行動\n\n- a\n")


def _world(tmp_path: Path, n: int) -> Path:
    """專案記憶層 <tmp>/proj/.claude/memory/shared/catK/cardNNN.md，索引不存在（空索引）。"""
    mem = tmp_path / "proj" / ".claude" / "memory"
    for i in range(n):
        d = mem / "shared" / f"cat{i % 5}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"card{i:03d}.md").write_text(_card(f"card{i:03d}"), encoding="utf-8")
    return mem


def _add(mem: Path) -> list:
    sync = _load_sync()
    atoms = sync.scan_atom_files(mem, mem.parent)
    rows = sync.load_index_rows(mem)
    return sync.add_to_index_from_frontmatter(atoms, rows, mem)


def _hold_open(path: Path, seconds: float):
    """模擬別的行程正開著檔讀：Python open() 不帶 FILE_SHARE_DELETE，開著時對它 os.replace 會 WinError 5。"""
    fh = open(path, "rb")
    t = threading.Timer(seconds, fh.close)
    t.start()
    return fh, t


@pytest.mark.skipif(not WIN, reason="WinError 5 搶檔是 Windows 行為")
def test_upsert_waits_for_reader_holding_mirror(tmp_path):
    mem = tmp_path / "mem"
    aij.upsert_atom(mem, "a", "memory/a.md", ["a"], "shared")
    fh, t = _hold_open(mem / aij.ATOM_INDEX_MD, 0.4)
    try:
        assert aij.upsert_atom(mem, "b", "memory/b.md", ["b"], "shared")   # 修前：PermissionError WinError 5
    finally:
        t.join()
        fh.close()
    names = [a["name"] for a in aij.load_atom_index_json(mem)["atoms"]]
    assert names == ["a", "b"]
    assert "| b | memory/b.md |" in (mem / aij.ATOM_INDEX_MD).read_text(encoding="utf-8")


def test_add_from_frontmatter_fills_empty_index_in_one_write(tmp_path, monkeypatch):
    mem = _world(tmp_path, 60)
    writes = []
    real = aij._write_text_lf
    monkeypatch.setattr(aij, "_write_text_lf", lambda p, c: (writes.append(Path(p).name), real(p, c))[1])
    added = _add(mem)
    assert len(added) == 60
    assert len(aij.load_atom_index_json(mem)["atoms"]) == 60          # 補齊張數＝檔數
    assert sorted(writes) == sorted([aij.ATOM_INDEX_JSON, aij.ATOM_INDEX_MD])   # 修前：每顆兩份、共 120 次換檔
    md = (mem / aij.ATOM_INDEX_MD).read_text(encoding="utf-8")
    assert all(f"| card{i:03d} |" in md for i in range(60))


@pytest.mark.skipif(not WIN, reason="WinError 5 搶檔是 Windows 行為")
def test_add_from_frontmatter_waits_for_reader_holding_index(tmp_path):
    mem = _world(tmp_path, 40)
    aij.save_atom_index_json(mem, {"version": "1.0", "atoms": []})
    fh, t = _hold_open(mem / aij.ATOM_INDEX_JSON, 0.4)
    try:
        added = _add(mem)                                                 # 修前：第一顆就 PermissionError
    finally:
        t.join()
        fh.close()
    assert len(added) == 40 and len(aij.load_atom_index_json(mem)["atoms"]) == 40


_READER = r"""
import sys, time
from pathlib import Path
mem = Path(sys.argv[1]); end = time.time() + 60
while time.time() < end:
    for n in ("_atom_index.json", "_ATOM_INDEX.md"):
        try:
            with open(mem / n, "rb") as f:
                f.read(); time.sleep(0.002)
        except OSError:
            pass
        time.sleep(0.03)
"""


@pytest.mark.skipif(not WIN, reason="WinError 5 搶檔是 Windows 行為")
def test_cli_add_from_frontmatter_fills_all_while_other_process_reads(tmp_path):
    """端到端：另兩支行程不停讀索引（像別的 session 的 hook），CLI 照樣把空索引補齊、exit 0。修前探針 4/4 中斷、只補 1～7 張。"""
    mem = _world(tmp_path, 100)
    env = dict(os.environ, WG_CLAUDE_DIR=str(tmp_path / "data"))
    readers = [subprocess.Popen([sys.executable, "-c", _READER, str(mem)]) for _ in range(2)]
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", str(SYNC), "--memory-dir", str(mem), "--add-from-frontmatter"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=120)
    finally:
        for p in readers:
            p.kill()
            p.wait()
    assert "PermissionError" not in r.stderr, r.stderr[-800:]
    assert len(aij.load_atom_index_json(mem)["atoms"]) == 100
    assert r.returncode == 0, r.stderr[-800:]


def test_mirror_failure_leaves_json_whole_and_rerun_heals(tmp_path, monkeypatch):
    mem = _world(tmp_path, 30)
    real = aij._write_text_lf

    def mirror_denied(p, c):
        if Path(p).name == aij.ATOM_INDEX_MD:
            raise PermissionError(13, "模擬 md 鏡像一直被別的行程開著")
        return real(p, c)

    monkeypatch.setattr(aij, "_write_text_lf", mirror_denied)
    with pytest.raises(PermissionError):
        _add(mem)
    assert len(aij.load_atom_index_json(mem)["atoms"]) == 30          # 修前：只進了第一顆（半套）
    assert not (mem / aij.ATOM_INDEX_MD).exists()                      # 鏡像不會跑在真相前面
    monkeypatch.setattr(aij, "_write_text_lf", real)
    assert _add(mem) == []                                             # 沒有新卡要補
    md = (mem / aij.ATOM_INDEX_MD).read_text(encoding="utf-8")          # 修前：沒變動就不重生，鏡像永遠缺
    assert all(f"| card{i:03d} |" in md for i in range(30))


def test_locked_index_is_not_overwritten(tmp_path, monkeypatch):
    """索引檔在、卻一直讀不到（重試完仍被鎖著）→ 停手；修前讀成空索引，整份覆寫成掃到的那幾張。"""
    mem = _world(tmp_path, 5)
    aij.upsert_atom(mem, "外部根的卡", "_AIDocs/_atoms/外部根的卡.md", ["外部"], "global")
    before = (mem / aij.ATOM_INDEX_JSON).read_bytes()
    real = Path.read_text

    def locked(self, *a, **k):
        if self.name == aij.ATOM_INDEX_JSON:
            raise PermissionError(13, "一直被別的行程鎖著")
        return real(self, *a, **k)

    monkeypatch.setattr(aij, "BUSY_WAIT_S", 0)
    monkeypatch.setattr(Path, "read_text", locked)
    with pytest.raises(OSError, match="不拿空索引覆寫"):
        _add(mem)
    monkeypatch.setattr(Path, "read_text", real)
    assert (mem / aij.ATOM_INDEX_JSON).read_bytes() == before


def test_corrupt_index_is_rebuilt_from_frontmatter(tmp_path):
    """反例守門：內容壞掉（合併衝突標記）時照舊從 frontmatter 補齊——MultiMachineMemorySync.md 寫明的最後手段，不能被「停手」誤擋。"""
    mem = _world(tmp_path, 5)
    (mem / aij.ATOM_INDEX_JSON).write_text('<<<<<<< ours\n{"version": "1.0", "atoms": []}\n=======\n', encoding="utf-8")
    assert len(_add(mem)) == 5
    assert len(aij.load_atom_index_json(mem)["atoms"]) == 5


def test_load_retries_transient_permission_error(tmp_path, monkeypatch):
    mem = tmp_path / "mem"
    aij.upsert_atom(mem, "a", "memory/a.md", ["a"], "shared")
    real = Path.read_text
    left = {"n": 2}

    def flaky(self, *a, **k):
        if self.name == aij.ATOM_INDEX_JSON and left["n"]:
            left["n"] -= 1
            raise PermissionError(13, "剛被換掉的檔短暫拒絕存取")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", flaky)
    assert [a["name"] for a in aij.load_atom_index_json(mem)["atoms"]] == ["a"]   # 修前：讀成空索引
