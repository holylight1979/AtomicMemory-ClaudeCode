"""git_cassette.py：測試裡 git／svn 子程序的錄製與重播——平常跑測試不開 git，只重播一次真實執行留下的紀錄。

做什麼：
- 錄製（record）：照常呼叫真 git／svn。每次呼叫前後各掃一次受測目錄（測試的 tmp_path），記下這次呼叫的指令、目錄、
  結束碼、輸出，以及它對檔案造成的變化（新增／修改／刪除的檔與目錄）；兩次呼叫之間測試或受測程式自己寫的檔，
  只記內容雜湊（重播時由它們自己再寫一次）。測試通過才寫成錄製檔。
- 重播（replay）：不開 git／svn。每次呼叫先核對三件事和錄製的那一筆一樣：指令（含參數）、執行目錄、呼叫前受測目錄的
  內容；一樣才交回當時的輸出、把當時的檔案變化原樣寫回。任何一項不同就讓測試失敗並說哪裡不同、要重錄。
  所以一次重播等於那次真實執行的完整複本：受測程式的判斷照常跑，git 看到的輸入一點不差，回答也一字不差。
- 錄製檔記下「會被 git 叫起來的本專案程式」（例：合併驅動）的雜湊，以及錄製時用的 git／svn 版本：程式改了、或這台
  機器現在的 git／svn 版本和錄製時不同 → 錄製檔作廢、自動重錄（跑真 git）。版本每個測試行程每種工具只問一次。
正規化：受測目錄的絕對路徑在指令、輸出、檔案內容裡都換成 <TMP>（程式碼樹 <CODE>、直譯器 <PY> 同理，換台機器也對得上），
  重播時換回這一次的實際路徑；指令裡的日期換成 <DATE>（commit 訊息帶當天日期）；比對檔案內容時日期也不算差異。
不比對的檔：git 的 index、svn 的 wc.db 內含檔案時間戳，受測程式的 .log／.jsonl 帶時間，重播與錄製不會一樣，照樣寫回但不拿來比對。
不適用：git 在受測程式開的子程序裡跑（攔不到）、repo 建在每案 tmp_path 之外（例：整個模組共用的目錄）。
  另可指定整個排除的子目錄（例：同步程式自己的鎖檔與時間戳檔），不掃、不比、不寫。
怎麼用：測試模組 autouse 一個 fixture 呼叫根 conftest 的 `git_cassette`（見 hooks/verify/verify_vcs_sync_worker.py）。
  模式（環境變數 WG_GIT_CASSETTE 或 pytest --git-record）：auto（預設：有有效錄製檔就重播，沒有或作廢就錄）、
  record（一律重錄）、off（跑真 git、不錄不播）。重播核對不過 → 用 --git-record 重跑那支測試（會跑真 git）。
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

FORMAT = 2
VCS_EXES = {"git", "svn", "svnadmin"}
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DIR = "<dir>"                       # 掃描結果裡目錄的記號（檔案記內容雜湊）


class CassetteMismatch(AssertionError):
    """重播核對不過：這次執行和錄製時不同，要用 --git-record 重錄。"""


def is_vcs_call(cmd: Any) -> bool:
    if isinstance(cmd, (str, bytes)) or not cmd:
        return False
    name = Path(str(cmd[0])).name.lower()
    return (name[:-4] if name.endswith(".exe") else name) in VCS_EXES


_VERSIONS: Dict[str, str] = {}
_VERSION_ARGS = {"git": ["--version"], "svn": ["--version", "--quiet"], "svnadmin": ["--version", "--quiet"]}


def tool_version(exe: str, path: str = "", run=None) -> str:
    """git／svn 的版本字串：同一個行程每種工具只問一次；錄製時那支執行檔還在就問它，否則問 PATH 上的。問不到回空字串。
    在一次性暫存目錄裡問、家目錄類變數都指過去：svn 一啟動就會在家目錄建設定檔，不能落進測試的受測目錄。"""
    if exe in _VERSIONS:
        return _VERSIONS[exe]
    target = path if path and (Path(path).exists() or shutil.which(path)) else exe
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch:
            env = {**os.environ, "HOME": scratch, "USERPROFILE": scratch, "APPDATA": scratch, "XDG_CONFIG_HOME": scratch}
            r = (run or subprocess.run)([target, *_VERSION_ARGS.get(exe, ["--version"])], capture_output=True,
                                        text=True, timeout=10, cwd=scratch, env=env)
        out = (r.stdout or "").strip()
        version = out.splitlines()[0] if r.returncode == 0 and out else ""
    except (OSError, subprocess.SubprocessError):
        version = ""
    _VERSIONS[exe] = version
    return version


def code_hashes(tree: Path, rels: Iterable[str]) -> Dict[str, str]:
    """會被 git 叫起來的本專案程式：相對路徑 → 內容雜湊（不存在記空字串）。"""
    out = {}
    for rel in rels:
        p = tree / rel
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else ""
    return out


def _is_volatile(rel: str) -> bool:
    """不拿來比對的檔：git 的 index、svn 的 wc.db 內含檔案時間戳；.log／.jsonl 是受測程式自己的日誌與帳本（帶時間）。"""
    parts = rel.split("/")
    return ((parts[-1] == "index" and ".git" in parts) or (parts[-1].startswith("wc.db") and ".svn" in parts)
            or parts[-1].endswith((".log", ".jsonl")))


class _Paths:
    """受測目錄（<TMP>）與其他會出現在指令、輸出裡、隨機器不同的路徑（例：<CODE> 程式碼樹、<PY> 直譯器）↔ 記號。
    每種寫法各一個記號（原樣、原樣改正斜線、長檔名、長檔名改正斜線），重播時還原成這次同一種寫法：git 照原樣回聲的
    路徑（check-ignore --stdin）才和受測程式手上的字串一致。Windows 不分大小寫；長的先換。"""

    def __init__(self, root: Path, extra: Optional[Dict[str, Path]] = None):
        self.values: Dict[str, str] = {}
        forms: Dict[str, str] = {}
        for mark, p in [("<TMP>", root), *(extra or {}).items()]:
            orig, full = str(p), str(Path(p).resolve())
            for suffix, value in (("", orig), (":/", orig.replace("\\", "/")),
                                  (":L", full), (":L/", full.replace("\\", "/"))):
                tag = mark if not suffix else f"{mark[:-1]}{suffix}>"
                if value.lower() not in {f.lower() for f in forms}:     # 寫法重複（沒有短檔名、本來就正斜線）只留第一個
                    forms[value] = tag
                self.values[tag] = value
        self._re = re.compile("|".join(re.escape(f) for f in sorted(forms, key=len, reverse=True)),
                              re.IGNORECASE if os.name == "nt" else 0)
        self._lower = {k.lower(): v for k, v in forms.items()}

    def norm(self, s: str) -> str:
        return self._re.sub(lambda m: self._lower[m.group(0).lower()], s)

    def denorm(self, s: str) -> str:
        for mark in sorted(self.values, key=len, reverse=True):         # <TMP:L/> 先於 <TMP>
            s = s.replace(mark, self.values[mark])
        return s


def _encode(data: bytes, paths: _Paths) -> Dict[str, str]:
    try:
        return {"t": paths.norm(data.decode("utf-8"))}
    except UnicodeDecodeError:
        return {"b": base64.b64encode(data).decode("ascii")}


def _decode(rec: Dict[str, str], paths: _Paths) -> bytes:
    return paths.denorm(rec["t"]).encode("utf-8") if "t" in rec else base64.b64decode(rec["b"])


def _digest(data: bytes, paths: _Paths) -> str:
    try:
        data = _DATE_RE.sub("<DATE>", paths.norm(data.decode("utf-8"))).encode("utf-8")
    except UnicodeDecodeError:
        pass
    return hashlib.sha256(data).hexdigest()[:16]


class _Tree:
    """掃受測目錄：相對路徑（/ 分隔）→ 內容雜湊或 DIR。用 (大小, 修改時間) 快取，沒變的檔不重讀。"""

    def __init__(self, root: Path, exclude: Iterable[str], paths: _Paths):
        self.root, self.paths = root, paths
        self.exclude = tuple(e.strip("/") for e in exclude)
        self._cache: Dict[str, Tuple[int, int, str]] = {}

    def _skip(self, rel: str) -> bool:
        return any(rel == e or rel.startswith(e + "/") for e in self.exclude)

    def scan(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        stack = [(self.root, "")]
        while stack:
            d, prefix = stack.pop()
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                rel = prefix + e.name
                if self._skip(rel):
                    continue
                if e.is_dir(follow_symlinks=False):
                    out[rel] = DIR
                    stack.append((Path(e.path), rel + "/"))
                elif e.is_file(follow_symlinks=False):
                    st = e.stat()
                    hit = self._cache.get(rel)
                    if hit and hit[0] == st.st_size and hit[1] == st.st_mtime_ns:
                        out[rel] = hit[2]
                        continue
                    try:
                        h = _digest(Path(e.path).read_bytes(), self.paths)
                    except OSError:
                        continue
                    self._cache[rel] = (st.st_size, st.st_mtime_ns, h)
                    out[rel] = h
        return out

    def read(self, rel: str) -> bytes:
        return (self.root / rel).read_bytes()


def _delta(before: Dict[str, str], after: Dict[str, str]) -> Dict[str, Optional[str]]:
    """before → after 的差異：路徑 → 新雜湊／DIR，刪掉的記 None。"""
    out: Dict[str, Optional[str]] = {k: v for k, v in after.items() if before.get(k) != v}
    out.update({k: None for k in before if k not in after})
    return out


def _apply_state(state: Dict[str, str], delta: Dict[str, Optional[str]]) -> Dict[str, str]:
    new = dict(state)
    for k, v in delta.items():
        if v is None:
            new.pop(k, None)
        else:
            new[k] = v
    return new


def _diff_report(expected: Dict[str, str], actual: Dict[str, str], limit: int = 6) -> str:
    keys = sorted(k for k in set(expected) | set(actual)
                  if expected.get(k) != actual.get(k) and not _is_volatile(k))
    lines = []
    for k in keys[:limit]:
        if k not in actual:
            lines.append(f"少了 {k}")
        elif k not in expected:
            lines.append(f"多了 {k}")
        else:
            lines.append(f"內容不同 {k}")
    return "；".join(lines) + (f"…（共 {len(keys)} 處）" if len(keys) > limit else "")


def _same(expected: Dict[str, str], actual: Dict[str, str]) -> bool:
    keys = set(expected) | set(actual)
    return all(expected.get(k) == actual.get(k) for k in keys if not _is_volatile(k))


def _force_remove(p: Path) -> None:
    def onerror(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p, onerror=onerror)
    elif p.exists():
        os.chmod(p, stat.S_IWRITE)
        p.unlink()


class Cassette:
    """一支測試的錄製／重播。mode：record 或 replay。install(monkeypatch) 之後攔 subprocess.run 的 git／svn 呼叫。"""

    def __init__(self, path: Path, root: Path, mode: str, exclude: Iterable[str] = (),
                 code: Optional[Dict[str, str]] = None, extra_paths: Optional[Dict[str, Path]] = None):
        self.path, self.root, self.mode = path, root, mode
        self.paths = _Paths(root, extra_paths)
        self.tree = _Tree(root, exclude, self.paths)
        self.code = code or {}
        self.calls: List[Dict[str, Any]] = []
        self.versions: Dict[str, str] = {}          # 錄製時用到的工具 → 版本字串
        self.exe_paths: Dict[str, str] = {}         # 錄製時用到的工具 → 執行檔（重播前問版本用）
        self.pos = 0
        self._orig = subprocess.run
        self.state = self.tree.scan()
        self.start = dict(self.state)
        if mode == "replay":
            data = load(path)
            self.calls = data["calls"]
            self.state = data["start"]
            if not _same(self.state, self.start):
                raise CassetteMismatch(f"[git_cassette] 測試開始時受測目錄就和錄製時不同（{_diff_report(self.state, self.start)}）"
                                       f"；用 --git-record 重錄：{path}")

    def install(self, monkeypatch) -> None:
        monkeypatch.setattr(subprocess, "run", self._record if self.mode == "record" else self._replay)

    # ── 共用 ──
    def _key(self, cmd, kw) -> Dict[str, Any]:
        argv = [_DATE_RE.sub("<DATE>", self.paths.norm(str(a))) for a in cmd[1:]]
        name = Path(str(cmd[0])).name.lower()
        cwd = kw.get("cwd")
        return {"exe": name[:-4] if name.endswith(".exe") else name, "argv": argv,
                "cwd": self.paths.norm(str(cwd)).replace("\\", "/") if cwd else None,
                "text": bool(kw.get("text") or kw.get("universal_newlines") or kw.get("encoding"))}

    def _out(self, v) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            return {"t": self.paths.norm(v)}
        return _encode(v, self.paths)

    def _back(self, rec, text: bool) -> Any:
        if rec is None:
            return None
        if "t" in rec:
            s = self.paths.denorm(rec["t"])
            return s if text else s.encode("utf-8")
        data = base64.b64decode(rec["b"])
        return data.decode("utf-8", errors="replace") if text else data

    # ── 錄製 ──
    def _record(self, cmd, *args, **kw):
        if not is_vcs_call(cmd):
            return self._orig(cmd, *args, **kw)
        key = self._key(cmd, kw)
        if key["exe"] not in self.versions:
            self.exe_paths[key["exe"]] = str(cmd[0])
            self.versions[key["exe"]] = tool_version(key["exe"], str(cmd[0]), self._orig)
        pre = self.tree.scan()
        entry: Dict[str, Any] = {**key, "pre": _delta(self.state, pre)}
        check = kw.pop("check", False)              # 先錄下非零結束碼，再照 check 丟例外（重播同一條路）
        try:
            res = self._orig(cmd, *args, **kw)
        except subprocess.TimeoutExpired as e:
            entry["exc"] = {"type": "timeout", "timeout": e.timeout}
            res = None
        except OSError as e:
            entry["exc"] = {"type": "oserror", "errno": e.errno, "msg": str(e)}
            res = None
        post = self.tree.scan()
        effect = _delta(pre, post)
        entry["effect"] = {k: (None if v is None else DIR if v == DIR else _encode(self.tree.read(k), self.paths))
                           for k, v in effect.items()}
        entry["post"] = {k: v for k, v in effect.items()}
        self.state = post
        if res is not None:
            entry.update(rc=res.returncode, out=self._out(res.stdout), err=self._out(res.stderr))
        self.calls.append(entry)
        if res is None:
            self._raise(entry, cmd, kw)
        if check and res.returncode:
            raise subprocess.CalledProcessError(res.returncode, cmd, res.stdout, res.stderr)
        return res

    # ── 重播 ──
    def _replay(self, cmd, *args, **kw):
        if not is_vcs_call(cmd):
            return self._orig(cmd, *args, **kw)
        key = self._key(cmd, kw)
        n = self.pos + 1
        if self.pos >= len(self.calls):
            raise CassetteMismatch(f"[git_cassette] 第 {n} 筆 git／svn 呼叫在錄製裡沒有（錄製只有 {len(self.calls)} 筆）："
                                   f"{key['exe']} {' '.join(key['argv'])}；行為改了 → 用 --git-record 重錄：{self.path}")
        rec = self.calls[self.pos]
        want = {k: rec[k] for k in ("exe", "argv", "cwd", "text")}
        if want != key:
            raise CassetteMismatch(f"[git_cassette] 第 {n} 筆呼叫和錄製不同\n  錄製：{want}\n  這次：{key}\n"
                                   f"行為改了 → 用 --git-record 重錄：{self.path}")
        expected = _apply_state(self.state, rec["pre"])
        actual = self.tree.scan()
        if not _same(expected, actual):
            raise CassetteMismatch(f"[git_cassette] 第 {n} 筆呼叫（{key['exe']} {' '.join(key['argv'][:4])}）之前受測目錄和錄製時不同："
                                   f"{_diff_report(expected, actual)}；用 --git-record 重錄：{self.path}")
        self._write_effect(rec["effect"])
        self.state = _apply_state(expected, rec["post"])
        self.pos += 1
        if "exc" in rec:
            self._raise(rec, cmd, kw)
        text = key["text"]
        res = subprocess.CompletedProcess(cmd, rec["rc"], self._back(rec.get("out"), text), self._back(rec.get("err"), text))
        if kw.get("check") and res.returncode:
            raise subprocess.CalledProcessError(res.returncode, cmd, res.stdout, res.stderr)
        return res

    def _write_effect(self, effect: Dict[str, Any]) -> None:
        gone = sorted((k for k, v in effect.items() if v is None), key=len, reverse=True)
        for k in gone:
            _force_remove(self.root / k)
        for k in sorted(k for k, v in effect.items() if v == DIR):
            (self.root / k).mkdir(parents=True, exist_ok=True)
        for k, v in effect.items():
            if v is None or v == DIR:
                continue
            p = self.root / k
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.exists():
                os.chmod(p, stat.S_IWRITE)
            p.write_bytes(_decode(v, self.paths))

    def _raise(self, rec, cmd, kw):
        exc = rec["exc"]
        if exc["type"] == "timeout":
            raise subprocess.TimeoutExpired(cmd, exc["timeout"])
        raise OSError(exc.get("errno"), exc.get("msg"))

    # ── 收尾 ──
    def finish(self, passed: bool) -> None:
        """錄製：測試通過才寫檔。重播：通過的測試要把錄製的呼叫用完（少呼叫也是行為改了）。"""
        if self.mode == "record":
            if passed and self.calls:                 # 沒叫 git 的案不留檔：下次照樣直接跑，本來就不開 git
                save(self.path, {"format": FORMAT, "code": self.code, "versions": self.versions, "exe": self.exe_paths,
                                 "start": self.start, "calls": self.calls})
            return
        if passed and self.pos != len(self.calls):
            raise CassetteMismatch(f"[git_cassette] 錄製有 {len(self.calls)} 筆 git／svn 呼叫，這次只用了 {self.pos} 筆；"
                                   f"行為改了 → 用 --git-record 重錄：{self.path}")


def load(path: Path) -> Dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def save(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    with open(path, "wb") as f:                                   # mtime=0：同樣內容重錄出同樣位元組，版控不起假差異
        with gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0) as g:
            g.write(raw)


def choose_mode(path: Path, requested: str, code: Dict[str, str]) -> Tuple[str, str]:
    """回 (模式, 理由)。requested：auto／record／replay／off。auto：錄製檔存在、格式對、程式雜湊相同才重播。"""
    if requested in ("record", "off"):
        return requested, requested
    if not path.exists():
        if requested == "replay":
            raise CassetteMismatch(f"[git_cassette] 沒有錄製檔：{path}")
        return "record", "沒有錄製檔"
    try:
        data = load(path)
    except (OSError, ValueError, EOFError) as e:
        return "record", f"錄製檔讀不動（{type(e).__name__}）"
    if data.get("format") != FORMAT:
        return "record", "錄製檔格式舊"
    if data.get("code") != code:
        stale = sorted(k for k in set(code) | set(data.get("code") or {}) if code.get(k) != (data.get("code") or {}).get(k))
        return "record", f"被 git 叫起來的程式改了（{'、'.join(stale)}）"
    if "versions" not in data:
        return "record", "錄製檔沒記 git／svn 版本"
    for name, recorded in sorted(data["versions"].items()):
        now = tool_version(name, (data.get("exe") or {}).get(name, ""))
        if now != recorded:
            return "record", f"{name} 版本不同（錄製時 {recorded or '問不到'}，現在 {now or '問不到'}）"
    return "replay", "重播"
