"""cs_roslyn — C# 的 Roslyn 解析前端：本機有 .NET SDK（內附 Roslyn）就用它把 .cs 解析成 reading_path_lang 的 Module，跟輕量解析同一個形狀。

做什麼：find_roslyn 找 `dotnet --version` 選中的那版 SDK 附的 Roslyn（sdk/<版本>/Roslyn/bincore）；parse_many 第一次用時把 lib/cs_roslyn/
  的小程式編進 <repo>/cache/cs-roslyn/<雜湊>/（SDK 版本與原始碼沒變就重用），把一批檔的文字從 stdin 送進去，拿回語法事實
  （呼叫、讀屬性、區域變數、指定、訂閱…），再照輕量解析同一套規則（reading_path_lang 的 _cs_call_kind、_cs_arg、_cs_ref、
  _cs_sign_overloads）組成 Module。Roslyn 只換掉「從原始碼抓語法」這一段，分類規則與建圖不變。
  與輕量解析刻意不同的地方：大括號、字串、泛型、lambda 範圍靠語法樹認，不靠正規式；被指定次數只數指定給名字本身的（this.x = x
  不算參數 x 被改）；欄位型別推導只收 x = new Foo() 與 this.x = new Foo()，不收區域變數。#if／#elif／#else／#endif 行先換成空白，
  兩支都當成程式（同輕量解析）。
找不到 SDK → find_roslyn 回 None；編不起來、跑失敗、逾時 → 丟 RoslynError（呼叫端退回輕量解析並註明）。
怎麼跑：import 後呼叫 find_roslyn()／parse_many({相對路徑: 文字})；不單獨跑。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Optional

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.append(str(_TOOLS))
import reading_path_lang as lang  # noqa: E402

HELPER = Path(__file__).resolve().parent / "cs_roslyn"
CACHE = Path(__file__).resolve().parents[1] / "cache" / "cs-roslyn"
BUILD_TIMEOUT_S = 180.0    # 第一次編譯小程式最多等多久
RUN_TIMEOUT_S = 60.0       # 解析一批最多等多久
_ENV = {**os.environ, "DOTNET_NOLOGO": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "DOTNET_CLI_UI_LANGUAGE": "en", "MSBUILDDISABLENODEREUSE": "1", "DOTNET_CLI_USE_MSBUILD_SERVER": "0"}
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_DIRECTIVE = re.compile(r"^[ \t]*#[ \t]*(?:if|elif|else|endif)\b[^\r\n]*", re.M)
_LOWER = re.compile(r"[a-z_]\w*")
_FOUND: Dict[str, Any] = {}


class RoslynError(Exception):
    """Roslyn 小程式編不起來、跑失敗或逾時。"""


def find_roslyn() -> Optional[Dict[str, str]]:
    """本機 SDK 附的 Roslyn → {"dotnet", "sdk", "dir", "tfm"}；沒裝 dotnet、找不到那版 SDK 的 Roslyn → None。一個行程只查一次。"""
    if "info" not in _FOUND:
        _FOUND["info"] = _probe()
    return _FOUND["info"]


def _probe() -> Optional[Dict[str, str]]:
    exe = shutil.which("dotnet")
    if not exe:
        return None
    try:
        ver = _run([exe, "--version"], None, 30.0, HELPER).decode("utf-8", "replace").strip()
        sdks = _run([exe, "--list-sdks"], None, 30.0, HELPER).decode("utf-8", "replace")
    except RoslynError:
        return None
    for line in sdks.splitlines():
        got, _, where = line.partition(" [")
        roslyn = Path(where.rstrip("]").strip()) / ver / "Roslyn" / "bincore"
        if got.strip() == ver and (roslyn / "Microsoft.CodeAnalysis.CSharp.dll").is_file():
            return {"dotnet": exe, "sdk": ver, "dir": str(roslyn), "tfm": f"net{ver.split('.')[0]}.0"}
    return None


def parse_many(texts: Dict[str, str], deadline: float = float("inf")) -> Dict[str, Any]:
    """{相對路徑: 原始碼} → {相對路徑: Module 或 ValueError（這個檔 Roslyn 解析丟例外）}。deadline：time.monotonic 的期限。"""
    if not texts:
        return {}
    info = find_roslyn()
    if info is None:
        raise RoslynError("找不到 .NET SDK 附的 Roslyn")
    dll = _built(info, deadline)
    files = [{"rel": rel, "text": _DIRECTIVE.sub(lambda m: " " * len(m.group()), text)} for rel, text in texts.items()]
    out = _run([info["dotnet"], str(dll)], json.dumps({"files": files}, ensure_ascii=False).encode("utf-8"),
               min(RUN_TIMEOUT_S, deadline - time.monotonic()))
    try:                                    # 輸出形狀不對（小程式與這支對不上）：整批退回輕量解析，不當成單檔解析失敗
        got = {m["file"]: m for m in json.loads(out.decode("utf-8"))["modules"]}
        return {rel: _module(got[rel]) if rel in got and "error" not in got[rel]
                else ValueError((got.get(rel) or {}).get("error") or "Roslyn 沒回這個檔") for rel in texts}
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise RoslynError(f"小程式的輸出讀不懂：{type(e).__name__}: {e}") from None


# ─── 編譯與執行小程式 ─────────────────────────────────────────────────────────

def _built(info: Dict[str, str], deadline: float) -> Path:
    """lib/cs_roslyn/ 編好的 dll（原始碼＋SDK 版本＋Roslyn 位置的雜湊當快取鍵）；沒有就編：複製到暫存夾編（obj／bin 不落進 repo），
    編好換名成快取資料夾；兩個行程同時編，後到的丟掉自己那份、用先換名成功的。"""
    src = [HELPER / "Program.cs", HELPER / "cs_roslyn.csproj"]
    try:                                       # 讀原始碼、建暫存夾、複製失敗也當 Roslyn 跑不動（呼叫端退回輕量解析）
        key = hashlib.sha1(b"".join(p.read_bytes() for p in src) + f"{info['sdk']}|{info['dir']}".encode()).hexdigest()[:12]
        dll = CACHE / key / "out" / "cs_roslyn.dll"
        if dll.is_file():
            return dll
        tmp = CACHE / f"{key}.{os.getpid()}.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        (tmp / "src").mkdir(parents=True)
        for p in src:
            shutil.copy2(p, tmp / "src" / p.name)
    except OSError as e:
        raise RoslynError(f"準備編譯失敗：{e}") from None
    try:
        _run([info["dotnet"], "build", str(tmp / "src"), "-c", "Release", "-o", str(tmp / "out"), "--nologo", "-v", "q",
              "-nodeReuse:false", "-p:UseSharedCompilation=false", f"-p:RoslynDir={info['dir']}", f"-p:CsRoslynTfm={info['tfm']}"],
             None, min(BUILD_TIMEOUT_S, deadline - time.monotonic()), tmp)
        shutil.rmtree(tmp / "src", ignore_errors=True)
        os.replace(tmp, CACHE / key)
    except OSError:
        pass                                    # 別的行程先換名成功了（或換名失敗：下面找不到 dll 就報錯）
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not dll.is_file():
        raise RoslynError("編完找不到小程式")
    for old in CACHE.iterdir():                 # 舊版原始碼編的（一份約 30MB）不再用：清掉；別的行程正在編的暫存夾不動
        if old.name != key and not old.name.endswith(".tmp"):
            shutil.rmtree(old, ignore_errors=True)
    return dll


def _run(args: list, data: Optional[bytes], timeout: float, cwd: Optional[Path] = None) -> bytes:
    if timeout <= 0:
        raise RoslynError("時間預算用完")
    try:
        proc = subprocess.run(args, input=data, capture_output=True, timeout=timeout, cwd=cwd, env=_ENV, creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise RoslynError(f"{Path(args[1] if len(args) > 1 else args[0]).name} 超過 {timeout:.0f} 秒") from None
    except OSError as e:
        raise RoslynError(f"跑不起來：{e}") from None
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr).decode("utf-8", "replace").strip().splitlines()
        raise RoslynError(f"結束碼 {proc.returncode}：{(tail or [''])[-1][:200]}")
    return proc.stdout


# ─── 語法事實 → Module（規則照 reading_path_lang 的 C# 段） ───────────────────────────

def _module(m: Dict[str, Any]) -> lang.Module:
    rel = m["file"]
    mod = lang.Module(rel, "cs", static_usings=list(m.get("static_usings") or []))
    for c in m["classes"]:
        cls = lang.Cls(c["name"], "cs", [rel], list(c["bases"]), partial=c["partial"])
        for name, t in c["fields"].items():
            cls.fields[name] = cls.declared_fields[name] = t
        cls.events.update(c["events"])
        first = len(mod.funcs)
        for fj in c["funcs"]:
            _func(mod, cls, fj)
        lang._cs_sign_overloads(mod, cls, mod.funcs[first:])
        mod.classes.append(cls)
    return mod


def _func(mod: lang.Module, cls: lang.Cls, fj: Dict[str, Any]) -> None:
    name = fj["name"]
    base = f"{mod.file}::{cls.name}.{name}"
    fid = base if all(f.id != base for f in mod.funcs) else f"{base}#{fj['line']}"   # 暫用；多載在整個類別讀完後改成簽章 id
    params = [(p["name"], p["type"]) for p in fj["params"]]
    f = lang.Func(fid, mod.file, f"{cls.name}.{name}", name, cls.name, "cs", fj["line"], fj["end"],
                  params=[p for p, _ in params], param_types={p: t for p, t in params if t}, prop=fj["prop"],
                  sig=",".join(p["text"] for p in fj["params"]))
    f.abstract = "abstract" in fj["mods"] or fj["declared"]
    f.hollow = not f.abstract and fj["empty"]
    f.conditional = fj["conditional"]
    f.entry = name == "Main" and "static" in fj["mods"]
    if not fj["declared"]:
        _body(mod, cls, f, fj)
    cls.methods.setdefault(name, []).append(fid)
    mod.funcs.append(f)


def _body(mod: lang.Module, cls: lang.Cls, f: lang.Func, fj: Dict[str, Any]) -> None:
    for c in fj["calls"]:
        if c["name"] in lang.CS_KEYWORDS and not c["new"]:
            continue
        call = lang._cs_call_kind(c["new"], c["name"], c["recv"], c["on_result"])
        call.line = f.line
        parsed = [lang._cs_arg(idx, text) for idx, text in enumerate(c["args"])]
        call.refs = [(key, ref) for key, ref, _, _ in parsed if ref]
        call.blind = {key for key, _, blind, _ in parsed if blind}
        call.nargs = sum(1 for *_, named in parsed if not named)
        call.kwargs = {key for key, *_, named in parsed if named}
        call.scoped = c["scoped"]
        call.shadowed = c["scoped"] and call.kind == "name" and call.name in c["shadow"]
        f.calls.append(call)
    f.calls += [lang.Call("opaque", "", line=f.line) for _ in range(fj["opaque"])]
    f.calls += [lang.Call("prop", p["name"], recv=p["recv"], line=f.line) for p in fj["props"]]
    f.simple = fj["stmts"] - fj["moves"] - sum(1 for c in f.calls if c.noise) <= 2 and not fj["compound"]
    for v in fj["locals"]:                 # 同輕量解析：小寫開頭、var 或大寫開頭的具名型別才算區域變數
        typed = v["type"] if v["type"][:1].isupper() else ""
        if not _LOWER.fullmatch(v["var"]) or not (v["var_kw"] or typed):
            continue
        if v["new"] or typed:
            f.local_types[v["var"]] = v["new"] or typed
        if typed:
            f.declared[v["var"]] = typed
        if v["new"]:
            f.constructed[v["var"]] = v["new"]
        ref = lang._cs_ref(v["init"]) if v["init"] else None
        if ref:
            f.aliases[v["var"]] = ref
        f.locals.add(v["var"])
    f.inline = {n for n in fj["inline"] if n not in lang.CS_KEYWORDS}
    stores = Counter({k: n for k, n in fj["stores"].items() if _LOWER.fullmatch(k)})
    stores.update(f.params)
    f.reassigned = {name for name, k in stores.items() if k > 1}
    for a in fj["assigns"]:               # lhs＝欄位寫法（x、this.x）；空＝別的物件的成員或下標
        if a["lhs"] in f.locals:
            continue                      # 指定給區域變數
        if a["lhs"] and a["new"]:
            cls.fields.setdefault(a["lhs"], a["new"])
        elif a["lhs"] and a["rhs"] in f.params:
            cls.stored[a["lhs"]] = (f.id, a["rhs"])
        if a["rhs"] in f.locals:
            f.escaped.add(a["rhs"])
    f.escaped |= set(fj["escaped"])
    f.receiver_only = set(fj["receiver_only"]) & set(f.constructed)
    for s in fj["subs"]:
        ref = lang._cs_ref(s["rhs"])
        recv, _, key = s["lhs"].rpartition(".")
        if ref:
            mod.subs.append((key, ref, f.id, mod.file, recv))
