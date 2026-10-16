"""conftest.py（repo 根）：測試預設隔離使用者資料根；整組量尺跑完自寫驗證收據。

做什麼：
1. 隔離：每個 pytest session 開始時（pytest_configure，早於任何測試模組匯入）建一個暫存目錄，把
   - WG_CLAUDE_DIR → <暫存>/data：資料根（workflow、Logs、memory、projects）全落這裡。
     先放進本樹受版控的資料檔（memory/、_AIDocs/_atoms/、workflow/config.json），等同剛 clone 好的資料根：
     測試讀到的是本樹這一版的 taxonomy、詞庫、config 與 atom，寫入只落暫存目錄；
   - TEMP／TMP／TMPDIR → <暫存>/tmp：tempfile 與子行程的暫存目錄，和資料根分開放，資料根不會被當成暫存路徑。
   子行程繼承 os.environ，走真 hook 入口的測試一起隔離。session 結束時（pytest_unconfigure）還原這四個變數並刪掉暫存目錄
   （run_verify.py 在同一行程呼叫 pytest.main，之後還要算資料根）；唯讀檔照刪，被別的行程占用刪不掉就在 stderr 列路徑。
   暫存目錄一建好就登記：初始化到一半被中斷（Ctrl+C、複製出錯）也清得到；收尾可重複呼叫。
   刻意讀 live 資料根的案：標 @pytest.mark.live_data，該案執行期間 WG_CLAUDE_DIR 還原成 pytest 啟動時的值；
   模組層常數在匯入時已算好、不會跟著變，這種案要在執行期呼叫 claude_data_dir() 或開子行程。
   隔離只在這裡做：claude_data_dir() 不判斷自己是不是在 pytest 裡。
   pytest 開始前已載入的本樹模組（同一行程先 import 再 pytest.main、或第二次 pytest.main）常數改不到 → stderr 列出來。
2. 自寫收據：這次 pytest 的目標恰好是 SUITES 裡某一整組（部位量尺就是整組 pytest，例 `pytest -q tools/verify`）時，
   跑完照 run_verify 的機制（lib/self_receipt.write_self_receipt）寫一份收據到 pytest 啟動時的資料根，
   量尺閘（hooks/wg_verify_ledger.load_self_runs）從那裡讀；背景跑、看不到結尾輸出也認得到。
   只跑其中幾支、用 -k／-m／--deselect／--lf 篩過、--ignore、--collect-only、中途停下（-x）、
   用 -o 覆寫收集設定（python_files 等）、改用別的 ini（-c）都不寫。
3. git_cassette fixture：測試的 git／svn 子程序錄製一次、之後重播（lib/git_cassette.py），平常跑測試不開 git；
   `--git-record` 選項（或 WG_GIT_CASSETTE=record）強制重錄。
怎麼跑：不用另外跑；rootdir 是本檔所在目錄（有 pytest.ini），pytest 自動載入。
"""
from __future__ import annotations

import hashlib
import itertools
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import pytest

TREE = Path(__file__).resolve().parent
SEED = ("memory", "_AIDocs/_atoms", "workflow/config.json")   # 本樹受版控的使用者資料
SUITES = ("tools/verify", "lib/verify")                         # 部位量尺是「整組 pytest」的目錄：跑完自寫收據
COLLECT_INI = ("python_files", "python_classes", "python_functions", "norecursedirs", "testpaths")   # 覆寫了＝收集範圍變了
KEYS = ("WG_CLAUDE_DIR", "TEMP", "TMP", "TMPDIR")
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
SESSION: Dict[str, Any] = {}   # 本次 session：base（一建好就登記）、original（四個變數原值）、data_root／temp_root、started、receipt


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


def _remove_tree(path: Path) -> None:
    """刪暫存目錄：先關掉本行程裡寫進暫存目錄的 log handler（例 wg_atoms 的向量觀測紀錄開著檔，Windows 刪不掉）；
    唯讀檔（測試建的 git 物件在 Windows 是唯讀）先清唯讀再刪；還刪不掉（別的行程占用、或刪除當下還有背景寫入）就在 stderr 說一聲。"""
    import logging
    prefix = _n(path) + os.sep
    loggers = [logging.getLogger(), *(x for x in logging.Logger.manager.loggerDict.values() if isinstance(x, logging.Logger))]
    for lg in loggers:
        for h in [h for h in lg.handlers if isinstance(h, logging.FileHandler) and _n(h.baseFilename).startswith(prefix)]:
            h.close()
            lg.removeHandler(h)

    def force(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass                                    # 下面統一檢查有沒有刪乾淨

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=force)
    else:
        shutil.rmtree(path, onerror=force)
    if path.exists():
        print(f"[conftest] 暫存目錄沒刪乾淨（有檔被其他行程占用，或刪除當下還有背景寫入）：{path}", file=sys.stderr)


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
                              r["cwd"], str(TREE), r["started"], time.time(), failed_cases=r.get("failed_cases"))
    except Exception as e:  # noqa: BLE001
        print(f"[conftest] 自寫驗證收據失敗：{type(e).__name__}: {e}", file=sys.stderr)


def _teardown(state: Dict[str, Any]) -> None:
    """收尾，初始化到一半或重複呼叫都可以：環境改過才還原、該寫收據才寫、暫存目錄建了才刪，最後清空 state。"""
    original = state.pop("original", None)
    if original is not None:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        tempfile.tempdir = None
    receipt = state.pop("receipt", None)
    if receipt:
        _write_suite_receipt(receipt)
    base = state.pop("base", None)
    if base is not None:
        _remove_tree(base)
    state.clear()


def pytest_configure(config):
    config.addinivalue_line("markers", "live_data: 刻意讀 live 資料根的案；執行期間 WG_CLAUDE_DIR 還原成 pytest 啟動時的值")
    preloaded = sorted(n for n, m in list(sys.modules.items())                  # 常數在匯入時算好，換環境變數改不到
                       if not n.startswith("_") and getattr(m, "__file__", None)
                       and Path(m.__file__).name != "conftest.py"             # pytest 自己先載的各層 conftest 不算
                       and _n(m.__file__).startswith(_n(TREE) + os.sep))
    if preloaded:
        print("[conftest] 這些本樹模組在 pytest 開始前已載入，模組層的資料根常數不會跟著隔離（要隔離就開新行程跑）："
              + "、".join(preloaded[:8]) + ("…" if len(preloaded) > 8 else ""), file=sys.stderr)
    _teardown(SESSION)                                  # 同一行程上一輪沒收乾淨的先收
    SESSION.update(base=Path(tempfile.mkdtemp(prefix="wg-iso-")),   # 前綴不含 test：有案要「路徑不含 test 字樣」的暫存目錄
                   started=time.time(), receipt=None, deselected=0, finished=0)
    try:
        data_root, temp_root = SESSION["base"] / "data", SESSION["base"] / "tmp"
        data_root.mkdir()
        temp_root.mkdir()
        for rel in _seed_files():
            if (TREE / rel).is_file():              # 索引裡有、工作樹已刪的檔跳過
                (data_root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(TREE / rel, data_root / rel)
        SESSION.update(data_root=data_root, temp_root=temp_root, original={k: os.environ.get(k) for k in KEYS})
        os.environ["WG_CLAUDE_DIR"] = str(data_root)
        for k in ("TEMP", "TMP", "TMPDIR"):
            os.environ[k] = str(temp_root)
        tempfile.tempdir = None   # gettempdir() 有快取：清掉讓它改讀上面三個變數
    except BaseException:
        _teardown(SESSION)
        raise


@pytest.fixture(autouse=True)
def _live_data_exemption(request, monkeypatch):
    if request.node.get_closest_marker("live_data") is None:
        return
    original = SESSION["original"]["WG_CLAUDE_DIR"]
    if original is None:
        monkeypatch.delenv("WG_CLAUDE_DIR", raising=False)
    else:
        monkeypatch.setenv("WG_CLAUDE_DIR", original)


def pytest_addoption(parser):
    parser.addoption("--git-record", action="store_true",
                     help="git_cassette：重錄 git／svn 錄製檔（跑真 git；同 WG_GIT_CASSETTE=record）")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    rep = (yield).get_result()
    if rep.when == "call":
        item._git_cassette_passed = rep.passed          # git_cassette 收尾要知道本體過了沒（沒過不寫錄製檔）


# hook 在測試沒導走資料根時寫的守門紀錄與需求目標檔（wg_core.logs_dir、wg_need_goal.goal_dir 的暫存去處，暫存目錄已改到
# tmp_path/_tmp）：內容帶時間戳與這次的暫存路徑、每次都不同，git 也從不讀它們 → 錄製重播不比對
RUNTIME_EXCLUDE = ("_tmp/wg-test-logs", "_tmp/wg-test-need-goal")


@pytest.fixture
def git_cassette(request, tmp_path, monkeypatch):
    """git／svn 子程序錄製重播（lib/git_cassette.py）。回 use(exclude=(), code=())：在受測目錄準備好之後呼叫，
    之後這支測試的 git／svn 呼叫平常重播、不開 git。錄製檔在測試模組旁的 cassettes/<模組>/<測試>.json.gz。
    exclude：tmp_path 下不掃不比的子目錄；code：會被 git 叫起來的本專案程式（相對本樹），改了就自動重錄。
    為了讓錄製與重播逐筆對得上：暫存目錄改成 tmp_path/_tmp（受測程式交給 git 的暫存檔也在受測目錄內、內容受比對），
    暫存檔名與 uuid4 改成這支測試從頭起算的序號（指令參數每次相同）。"""
    gc = sys.modules.get("_git_cassette") or _load_by_path("_git_cassette", "lib/git_cassette.py")
    module = Path(request.module.__file__)
    name = request.node.name
    safe = re.sub(r"[^\w.-]+", "_", name)[:80] + "-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:6]
    path = module.parent / "cassettes" / module.stem / f"{safe}.json.gz"
    requested = "record" if request.config.getoption("--git-record") else os.environ.get("WG_GIT_CASSETTE", "auto")
    holder: Dict[str, Any] = {}

    def use(exclude=(), code=()):
        hashes = gc.code_hashes(TREE, code)
        mode, why = gc.choose_mode(path, requested, hashes)
        if mode == "off":
            return
        if mode == "record" and requested == "auto":
            print(f"[git_cassette] 錄製（跑真 git）：{why}｜{path.name}", file=sys.stderr)
        session_temp = Path(tempfile.gettempdir())
        (tmp_path / "_tmp").mkdir(exist_ok=True)
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "_tmp"))
        names = (f"t{n:06d}" for n in itertools.count(1))
        monkeypatch.setattr(tempfile, "_get_candidate_names", lambda: names)
        seq = itertools.count(1)
        monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=next(seq)))
        exclude = tuple(exclude) + RUNTIME_EXCLUDE
        holder["c"] = gc.Cassette(path, tmp_path, mode, exclude, hashes,
                                  extra_paths={"<CODE>": TREE, "<PY>": Path(sys.executable), "<TEMP>": session_temp})
        holder["c"].install(monkeypatch)

    yield use
    if "c" in holder:
        holder["c"].finish(bool(getattr(request.node, "_git_cassette_passed", False)))


def pytest_deselected(items):
    SESSION["deselected"] += len(items)                 # -k、-m、--deselect、--lf 篩掉的案


def pytest_runtest_logreport(report):
    if report.when == "teardown":
        SESSION["finished"] += 1                        # 每個案最後都有 teardown（setup 就跳過的也有）
    if report.failed and report.nodeid not in SESSION.setdefault("failed_cases", []):
        SESSION["failed_cases"].append(report.nodeid)   # 收據記紅掉的測試名（驗證範圍拿去找範圍漏判）


def _narrowed(session) -> bool:
    """這次收集或執行比整組少嗎：篩掉了案、--ignore／--deselect、只收集、有案沒跑完、
    用 -o 覆寫了收集設定（COLLECT_INI）、或用的不是本樹的 pytest.ini（-c）。"""
    config = session.config
    overridden = {o.split("=", 1)[0].strip() for o in (getattr(config.option, "override_ini", None) or [])}
    return bool(SESSION["deselected"] or config.option.collectonly or SESSION["finished"] != session.testscollected
                or any(getattr(config.option, k, None) for k in ("ignore", "ignore_glob", "deselect"))
                or overridden & set(COLLECT_INI)
                or config.inipath is None or _n(config.inipath) != _n(TREE / "pytest.ini"))


def pytest_sessionfinish(session, exitstatus):
    """整組才寫收據：目標恰好是 SUITES 某一整組，而且沒有縮小（_narrowed）。"""
    inv_dir = Path(session.config.invocation_params.dir)
    targets = {_n(inv_dir / a) for a in session.config.args}
    suite = next((s for s in SUITES if targets == {_n(TREE / s)}), None)
    if suite and not _narrowed(session):
        SESSION["receipt"] = {"suite": suite, "exit_code": int(exitstatus), "cases": session.testscollected,
                              "failed": session.testsfailed, "cwd": str(inv_dir), "started": SESSION["started"],
                              "failed_cases": list(SESSION.get("failed_cases") or [])}


def pytest_unconfigure(config):
    _teardown(SESSION)
