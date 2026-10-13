"""conftest.py（repo 根）：測試預設隔離使用者資料根；整組量尺跑完自寫驗證收據。

做什麼：
1. 隔離：每個 pytest session 開始時（pytest_configure，早於任何測試模組匯入）建一個暫存目錄，把
   - WG_CLAUDE_DIR → <暫存>/data：資料根（workflow、Logs、memory、projects）全落這裡。
     先放進本樹受版控的資料檔（memory/、_AIDocs/_atoms/、workflow/config.json），等同剛 clone 好的資料根：
     測試讀到的是本樹這一版的 taxonomy、詞庫、config 與 atom，寫入只落暫存目錄；
   - TEMP／TMP／TMPDIR → <暫存>/tmp：tempfile 與子行程的暫存目錄，和資料根分開放，資料根不會被當成暫存路徑。
   子行程繼承 os.environ，走真 hook 入口的測試一起隔離。session 結束時（pytest_unconfigure）還原這四個變數並刪掉暫存目錄
   （run_verify.py 在同一行程呼叫 pytest.main，之後還要算資料根）。
   刻意讀 live 資料根的案：標 @pytest.mark.live_data，該案執行期間 WG_CLAUDE_DIR 還原成 pytest 啟動時的值；
   模組層常數在匯入時已算好、不會跟著變，這種案要在執行期呼叫 claude_data_dir() 或開子行程。
   隔離只在這裡做：claude_data_dir() 不判斷自己是不是在 pytest 裡。
   pytest 開始前已載入的本樹模組（同一行程先 import 再 pytest.main、或第二次 pytest.main）常數改不到 → stderr 列出來。
2. 自寫收據：這次 pytest 的目標恰好是 SUITES 裡某一整組（部位量尺就是整組 pytest，例 `pytest -q tools/verify`）時，
   跑完照 run_verify 的機制（lib/self_receipt.write_self_receipt）寫一份收據到 pytest 啟動時的資料根，
   量尺閘（hooks/wg_verify_ledger.load_self_runs）從那裡讀；背景跑、看不到結尾輸出也認得到。
   只跑其中幾支、用 -k／-m／--deselect／--lf 篩過、--ignore、--collect-only、中途停下（-x）都不寫。
怎麼跑：不用另外跑；rootdir 是本檔所在目錄（有 pytest.ini），pytest 自動載入。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

TREE = Path(__file__).resolve().parent
SEED = ("memory", "_AIDocs/_atoms", "workflow/config.json")   # 本樹受版控的使用者資料
SUITES = ("tools/verify", "lib/verify")                         # 部位量尺是「整組 pytest」的目錄：跑完自寫收據
KEYS = ("WG_CLAUDE_DIR", "TEMP", "TMP", "TMPDIR")
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
SESSION: Dict[str, Any] = {}   # 本次 session：original（四個變數原值）、base／data_root／temp_root、started、receipt


def _n(p) -> str:
    return os.path.normcase(os.path.realpath(str(p)))


def _seed_files() -> List[str]:
    """本樹受版控的資料檔（相對路徑；live 裡沒版控的向量庫、稽核紀錄不拷）。git 不可用 → 只放系統設定，並在 stderr 說一聲。"""
    try:
        r = subprocess.run(["git", "-C", str(TREE), "ls-files", "-z", "--", *SEED],
                           capture_output=True, timeout=30, creationflags=NO_WINDOW)
        if r.returncode == 0:
            return [p for p in r.stdout.decode("utf-8").split("\0") if p]
        err = r.stderr.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError) as e:
        err = f"{type(e).__name__}: {e}"
    print(f"[conftest] git ls-files 取不到受版控資料檔，測試資料根只放 memory/_meta/*.json 與 workflow/config.json：{err}",
          file=sys.stderr)
    return [p.relative_to(TREE).as_posix()
            for p in [*(TREE / "memory" / "_meta").glob("*.json"), TREE / "workflow" / "config.json"]]


def _load_by_path(name: str, rel: str):
    """用檔案路徑載入本樹 lib 的模組：不受 sys.modules 裡別處的 `lib` 套件影響（同 run_verify.py）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, TREE / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_suite_receipt(r: Dict[str, Any]) -> None:
    """寫收據到 pytest 啟動時的資料根（呼叫前環境已還原）；寫不進去只在 stderr 浮一行，不改 exit code。"""
    try:
        for p in (str(TREE), str(TREE / "lib")):    # self_receipt 寫檔時 import lib.atom_io
            if p not in sys.path:
                sys.path.insert(0, p)
        data_root = _load_by_path("_conftest_project_root", "lib/project_root.py").claude_data_dir()
        sr = _load_by_path("_conftest_self_receipt", "lib/self_receipt.py")
        verdict = "DONE" if r["exit_code"] == 0 and r["failed"] == 0 else "FAIL"
        sentinel = f"{r['suite'].replace('/', '_').upper()}_CHECK {verdict} cases={r['cases']} failed={r['failed']}"
        argv = list(getattr(sys, "orig_argv", None) or [sys.executable, *sys.argv])
        sr.write_self_receipt(data_root, argv, sentinel, r["exit_code"], r["cases"], r["failed"],
                              r["cwd"], str(TREE), SESSION["started"], time.time())
    except Exception as e:  # noqa: BLE001
        print(f"[conftest] 自寫驗證收據失敗：{type(e).__name__}: {e}", file=sys.stderr)


def pytest_configure(config):
    config.addinivalue_line("markers", "live_data: 刻意讀 live 資料根的案；執行期間 WG_CLAUDE_DIR 還原成 pytest 啟動時的值")
    preloaded = sorted(n for n, m in list(sys.modules.items())                  # 常數在匯入時算好，換環境變數改不到
                       if not n.startswith("_") and getattr(m, "__file__", None) and _n(m.__file__) != _n(__file__)
                       and _n(m.__file__).startswith(_n(TREE) + os.sep))
    if preloaded:
        print("[conftest] 這些本樹模組在 pytest 開始前已載入，模組層的資料根常數不會跟著隔離（要隔離就開新行程跑）："
              + "、".join(preloaded[:8]) + ("…" if len(preloaded) > 8 else ""), file=sys.stderr)
    base = Path(tempfile.mkdtemp(prefix="wg-iso-"))   # 前綴不含 test：有案要「路徑不含 test 字樣」的暫存目錄
    data_root, temp_root = base / "data", base / "tmp"
    data_root.mkdir()
    temp_root.mkdir()
    for rel in _seed_files():
        if (TREE / rel).is_file():                  # 索引裡有、工作樹已刪的檔跳過
            (data_root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TREE / rel, data_root / rel)
    SESSION.clear()
    SESSION.update(original={k: os.environ.get(k) for k in KEYS}, base=base, data_root=data_root,
                   temp_root=temp_root, started=time.time(), receipt=None, deselected=0, finished=0)
    os.environ["WG_CLAUDE_DIR"] = str(data_root)
    for k in ("TEMP", "TMP", "TMPDIR"):
        os.environ[k] = str(temp_root)
    tempfile.tempdir = None   # gettempdir() 有快取：清掉讓它改讀上面三個變數


@pytest.fixture(autouse=True)
def _live_data_exemption(request, monkeypatch):
    if request.node.get_closest_marker("live_data") is None:
        return
    original = SESSION["original"]["WG_CLAUDE_DIR"]
    if original is None:
        monkeypatch.delenv("WG_CLAUDE_DIR", raising=False)
    else:
        monkeypatch.setenv("WG_CLAUDE_DIR", original)


def pytest_deselected(items):
    SESSION["deselected"] += len(items)                 # -k、-m、--deselect、--lf 篩掉的案


def pytest_runtest_logreport(report):
    if report.when == "teardown":
        SESSION["finished"] += 1                        # 每個案最後都有 teardown（setup 就跳過的也有）


def pytest_sessionfinish(session, exitstatus):
    """整組才寫收據：目標恰好是 SUITES 某一整組，沒篩掉、沒忽略任何案，不是只收集，收集到的每一案都跑完。"""
    config = session.config
    inv_dir = Path(config.invocation_params.dir)
    targets = {_n(inv_dir / a) for a in config.args}
    suite = next((s for s in SUITES if targets == {_n(TREE / s)}), None)
    narrowed = (SESSION["deselected"] or config.option.collectonly or SESSION["finished"] != session.testscollected
                or any(getattr(config.option, k, None) for k in ("ignore", "ignore_glob", "deselect")))
    if suite and not narrowed:
        SESSION["receipt"] = {"suite": suite, "exit_code": int(exitstatus), "cases": session.testscollected,
                              "failed": session.testsfailed, "cwd": str(inv_dir)}


def pytest_unconfigure(config):
    if not SESSION:
        return
    for key, value in SESSION["original"].items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    tempfile.tempdir = None
    if SESSION["receipt"]:
        _write_suite_receipt(SESSION["receipt"])
    shutil.rmtree(SESSION["base"], ignore_errors=True)
