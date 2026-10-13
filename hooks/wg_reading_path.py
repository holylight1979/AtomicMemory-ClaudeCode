"""wg_reading_path — 收尾檢核附「這次對閱讀路徑的影響」（閱讀路徑量尺 tools/reading-path.py 接進 Stop）。

做什麼：改了程式碼的回合，對本 session 改過的檔所在的入口跑量尺的比較模式（before＝本 session 第一次改檔前的 HEAD、
after＝工作樹、--scope git），組成一段文字：尾行（READING_PATH DONE mode=compare …）、可評級與否（不可評級附原因）、
變差／新增最差一條。數字是尺不是判決：只量、只附（stop.py 併進這次擋的訊息與 stderr），不擋、不計預算；
量不出來（不在 git、還沒有 commit、沒有入口、工具失敗、逾時）就附一句原因與手動指令。
入口：部位表（overview-map.md）命中那一列「讀路徑樣本」欄的第一個程式檔（寫死的路徑存在就用它；帶 <佔位> 的照樣式
比對改過的檔，對得上就用那個檔）；有任何一個改檔拿不到入口，就不給 --entry，交給量尺自動偵測整個專案的入口
（main、__main__，都沒有才用沒人呼叫的公開函式）。測試檔與還沒 git add 的新檔不拿來找入口（後者附一句沒量到）。
before：本 session 在這個 git 根 commit 過（state committed_new_code）→ 第一筆的父提交；沒 commit 過 → HEAD。
時間：整支（git 與量尺子行程）共用 BUDGET_S 秒，逾時附「逾時」；逾時過的根這個 session 不再自動量，只附手動指令。
同一批輸入（根、before、改檔大小與時間、哪些還沒 git add）只量一次、只附一次（state["reading_path"][session_id]）。
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from wg_verify_ledger import _git_root_of, is_code_file, is_verify_case, reconcile_cfg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))   # 程式碼用本檔位置找，不用 CLAUDE_DIR
from overview_hub import find_map, match_row, parse_map  # noqa: E402

BUDGET_S = 3.0
TOOL = Path(__file__).resolve().parents[1] / "tools" / "reading-path.py"
TAG = "[Guardian:ReadingPath]"
STATUS_LABEL = {"worse": "變差", "new": "新增"}
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_SAMPLE_SPLIT = re.compile(r"\s+[>＞]\s+")   # 箭頭兩側要有空白：<佔位> 裡的 > 不算
_NOTE_RE = re.compile(r"[（(][^（）()]*[）)]")
_PLACEHOLDER = re.compile(r"<[^<>]*>")


class _Timeout(Exception):
    """整支預算用完。"""


def _python_exe() -> str:
    """hook 在 pythonw.exe 下跑，子行程用 pythonw 會拿不到 stdout → 改用同目錄 python.exe。"""
    exe = Path(sys.executable)
    sib = exe.with_name("python.exe")
    return str(sib) if exe.name.lower() == "pythonw.exe" and sib.exists() else str(exe)


def _spawn(args: List[str], deadline: float, run: Callable[..., Any]) -> Any:
    left = deadline - time.monotonic()
    if left <= 0:
        raise _Timeout
    try:
        return run(args, capture_output=True, timeout=left, creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise _Timeout from None


def _quote(arg: str) -> str:
    return f'"{arg}"' if " " in arg else arg


def code_files(mods: List[Dict[str, Any]], code_exts: List[str], turn: Optional[int] = None) -> List[str]:
    """modified_files 裡的程式檔（給 turn 就只取這個回合改過的）。"""
    out = []
    for m in mods:
        path = str((m or {}).get("path") or "")
        last = (m or {}).get("last_turn_seq", (m or {}).get("turn_seq"))
        if path and is_code_file(path, code_exts) and (turn is None or last == turn):
            out.append(path)
    return list(dict.fromkeys(out))


def base_spec(root_key: str, committed_new_code: Dict[str, Any]) -> str:
    """本 session 第一次改檔前的 HEAD：在這個根 commit 過 → 第一筆的父提交；沒 commit 過 → HEAD（改動都還在工作樹）。"""
    shas = ((committed_new_code or {}).get(root_key) or {}).get("shas") or []
    return f"{shas[0]}^" if shas else "HEAD"


def sample_entry(cell: str, map_root: Path, prefixes: List[str], path: str, code_exts: List[str]) -> Optional[str]:
    """「讀路徑樣本」欄的入口＝第一個程式檔 token：寫死的路徑（相對部位表的專案根或該列前綴）存在就是它；帶 <佔位> 或 *
    的照樣式比對改過的檔，對得上就是那個檔；都不成立 → None（交給量尺自動找）。"""
    for raw in _SAMPLE_SPLIT.split(_NOTE_RE.sub("", cell or "")):
        words = raw.strip().strip("`").split()
        tok = words[0].strip("`") if words else ""
        if not tok or not is_code_file(tok, code_exts):
            continue
        try:
            rel = Path(path).resolve().relative_to(map_root.resolve()).as_posix().lower()
        except ValueError:
            return None
        if _PLACEHOLDER.search(tok) or "*" in tok:
            pat = _PLACEHOLDER.sub("*", tok).lower()
            hits = [rel] + [rel[len(p) + 1:] for p in prefixes if rel.startswith(p + "/")]
            return path if any(fnmatch.fnmatchcase(h, pat) for h in hits) else None
        for base in [map_root] + [map_root / p for p in prefixes]:
            if (base / tok).is_file():
                return str(base / tok)
        return None
    return None


def entries_for(files: List[str], code_exts: List[str]) -> Tuple[Optional[List[str]], Optional[str]]:
    """改過的檔 → (入口清單, 部位表路徑或 None)。每個檔都從部位表樣本拿到入口 → 那些入口；有任何一個檔拿不到
    → 入口清單 None：不給 --entry，交給量尺自動偵測（main、__main__，都沒有才用沒人呼叫的公開函式）。"""
    entries, layers, tables = [], None, {}
    for f in files:
        found = find_map(f)
        entry = None
        if found:
            map_root, map_path = found
            layers = layers or str(map_path)
            if map_path not in tables:
                tables[map_path] = parse_map(map_path.read_text(encoding="utf-8"))
            row = match_row(f, map_root, tables[map_path])
            if row:
                entry = sample_entry(row.get("sample_paths") or "", map_root, row["prefixes"], f, code_exts)
        entries.append(entry)
    return (None if None in entries else list(dict.fromkeys(entries))), layers


def unratable_reasons(res: Dict[str, Any]) -> List[str]:
    out = []
    if res.get("scope_mismatch"):
        out.append("前後掃描母體政策不同")
    if res.get("emptied_files"):
        out.append(f"解析失敗或有函式↔零函式 {len(res['emptied_files'])} 檔")
    sides = [s for s, k in (("before", "ratable_before"), ("after", "ratable_after")) if not res.get(k)]
    if sides:
        out.append(f"{'／'.join(sides)} 有入口沒有全確定的路或可達範圍內有解析不了的呼叫")
    if res.get("coverage_drop"):
        out.append("after 的解析涵蓋變差")
    return out


def worst_row(rows: List[Dict[str, Any]]) -> Optional[str]:
    """變差／新增裡最差的一條（全確定優先，再比 after 的拐彎、跳檔、轉手）。"""
    picked = [r for r in rows if r.get("status") in STATUS_LABEL]
    if not picked:
        return None
    key = lambda r: (r["certain"], *((r.get("after") or {}).get(k, 0) for k in ("turns", "file_jumps", "handoffs")))
    r = max(picked, key=key)
    b, a = r.get("before") or {}, r.get("after") or {}
    nums = "｜".join(f"{name} {b.get(k, '-')}→{a.get(k, '-')}"
                    for name, k in (("拐彎", "turns"), ("跳檔", "file_jumps"), ("轉手", "handoffs")))
    mark = "" if r["certain"] else "（含候選：探索路徑變化）"
    return f"[{STATUS_LABEL[r['status']]}]{mark} {r['entry']} → {r['landing']}｜{nums}"


def summarize(res: Dict[str, Any], tail: str) -> List[str]:
    """量尺比較的 JSON 與尾行 → 附在收尾檢核的幾行：尾行、可評級與否、變差／新增最差一條、找不到的入口。"""
    lines = [f"    {tail}"]
    if res.get("ratable"):
        lines.append("    可評級：是")
    else:
        why = "、".join(unratable_reasons(res)) or "見尾行"
        lines.append(f"    可評級：否（觀測值，不能當改善或退步：{why}）")
    worst = worst_row(res.get("rows") or [])
    lines.append(f"    變差／新增最差一條：{worst}" if worst else "    沒有變差或新增的路徑")
    if res.get("entry_misses"):
        lines.append(f"    兩版都找不到函式的入口（略過）：{'、'.join(Path(e).name for e in res['entry_misses'])}")
    return lines


def _measure_root(root: Path, base: str, entries: Optional[List[str]], layers: Optional[str], deadline: float,
                  run: Callable[..., Any], slow: bool) -> Tuple[List[str], bool]:
    """量一個 git 根 → (幾行文字, 這次有沒有逾時)。entries 為 None：不給 --entry，量尺自動偵測入口。"""
    head = f"  {root}"
    tool_args = lambda before: ["--root", str(root), "--before", before, *[x for e in entries or [] for x in ("--entry", e)],
                                *(["--layers", layers] if layers else [])]
    manual_for = lambda before: "手動：python " + " ".join(_quote(a) for a in [str(TOOL), *tool_args(before)])
    if slow:   # 不再起任何子行程
        return [f"{head}：這個 session 先前 {BUDGET_S:g} 秒內量不完，不再自動量。{manual_for(base)}"], False
    try:
        sha_proc = _spawn(["git", "-C", str(root), "rev-parse", "--verify", "--short=12", f"{base}^{{commit}}"],
                          deadline, run)
    except _Timeout:
        return [f"{head}：逾時（{BUDGET_S:g} 秒預算在呼叫 git 時就用完，這個 session 這個根不再自動量）。{manual_for(base)}"], True
    if sha_proc.returncode != 0:
        return [f"{head}：量不出來，before（{base}）解不出：這個根還沒有任何 commit 或歷史不完整"], False
    sha = sha_proc.stdout.decode("utf-8", "replace").strip()
    args, manual = tool_args(sha), manual_for(sha)
    try:
        proc = _spawn([_python_exe(), "-X", "utf8", str(TOOL), *args, "--json", "--top", "1"], deadline, run)
    except _Timeout:
        return [f"{head}：逾時（{BUDGET_S:g} 秒內量不完，這個 session 這個根不再自動量）。{manual}"], True
    out = proc.stdout.decode("utf-8", "replace").strip().splitlines()
    tail = out[-1] if out else ""
    if proc.returncode != 0 or not tail.startswith("READING_PATH DONE"):
        why = tail or (proc.stderr.decode("utf-8", "replace").strip().splitlines() or [f"exit {proc.returncode}"])[-1]
        return [f"{head}：量不出來，量尺失敗：{why[:200]}。{manual}"], False
    try:
        res = json.loads("\n".join(out[:-1]))
    except json.JSONDecodeError as e:
        return [f"{head}：量不出來，量尺輸出解析失敗：{e}。{manual}"], False
    where = f"部位表給的入口 {len(entries)} 個" if entries else "入口自動偵測（有改檔在部位表上沒給入口）"
    return [f"{head}：before={sha}（本 session 第一次改檔前的 HEAD）→ 工作樹｜{where}", *summarize(res, tail)], False


def _fingerprint(files: List[str]) -> List[Any]:
    out = []
    for f in files:
        try:
            st = Path(f).stat()
            out.append([f, st.st_mtime_ns, st.st_size])
        except OSError:
            out.append([f, None, None])
    return out


def reading_path_note(state: Dict[str, Any], session_id: str, config: Dict[str, Any],
                      run: Callable[..., Any] = subprocess.run) -> Optional[str]:
    """改了程式碼的回合 → 附在收尾檢核的一段文字；這回合沒改程式碼、或同一批輸入已附過 → None。
    會更新 state["reading_path"][session_id]（呼叫端負責寫回 state）。"""
    cfg = reconcile_cfg(config)
    exts = cfg.get("code_exts") or []
    turn = int(state.get("turn_seq", 0))
    own = [m for m in state.get("modified_files") or [] if (m or {}).get("session_id", session_id) == session_id]
    if not code_files(own, exts, turn):
        return None
    deadline = time.monotonic() + BUDGET_S
    rec = state.setdefault("reading_path", {}).setdefault(session_id, {})
    groups: Dict[str, Tuple[Path, List[str]]] = {}
    outside = []
    for f in code_files(own, exts):
        hit = _git_root_of(f)
        if hit:
            groups.setdefault(hit[0], (hit[1], []))[1].append(f)
        else:
            outside.append(f)
    plans = []
    for key, (root, files) in sorted(groups.items()):
        slow = key in rec.get("slow", [])   # 逾時過的根：不再起 git 子行程
        tracked = {_norm(f) for f in files} if slow else _tracked(root, files, deadline, run)
        fresh = [f for f in files if Path(f).exists() and _norm(f) not in tracked]   # 還沒 git add 的新檔
        plans.append((key, root, files, base_spec(key, state.get("committed_new_code") or {}), fresh))
    # 同一批輸入＝根、before、改檔大小與時間、哪些還沒 git add 都相同（只 git add 不改檔也算新的一批）
    cache = json.dumps([[k, b, fr, _fingerprint(fs)] for k, _, fs, b, fr in plans] + [outside], ensure_ascii=False)
    if rec.get("key") == cache:
        return None
    rec["key"] = cache
    lines, notes = [f"{TAG} 這次對閱讀路徑的影響（尺不是判決，只量不擋）："], []
    if outside:
        lines.append(f"  不在 git 工作區，比較要 git 歷史當 before，沒量：{'、'.join(Path(f).name for f in outside)}")
    if not TOOL.is_file():
        return "\n".join(lines + [f"  量不出來：找不到量尺 {TOOL}"])
    for key, root, files, base, fresh in plans:
        notes += fresh
        product = [f for f in files if not is_verify_case(f, cfg.get("verify_case_globs") or [], str(root))]
        measurable = [f for f in product if f not in fresh]
        if not measurable:
            why = "改的都是還沒 git add 的新檔" if product else "這次只改了測試檔"
            lines.append(f"  {root}：{why}，沒有產品入口可量")
            continue
        entries, layers = entries_for(measurable, exts)
        try:
            got, timed_out = _measure_root(root, base, entries, layers, deadline, run, key in rec.get("slow", []))
        except OSError as e:
            got, timed_out = [f"  {root}：量不出來，跑不動子行程：{e}"], False
        if timed_out:
            rec["slow"] = sorted(set(rec.get("slow", [])) | {key})
        lines += got
    if notes:
        lines.append(f"  還沒 git add 的新檔不在掃描母體（--scope git），沒量到：{'、'.join(Path(f).name for f in notes)}")
    return "\n".join(lines)


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _tracked(root: Path, files: List[str], deadline: float, run: Callable[..., Any]) -> set:
    """git 追蹤中的檔（正規化絕對路徑）；查不到（預算用完、git 失敗）→ 全當有追蹤：只少一句提示，入口照給。"""
    every = {_norm(f) for f in files}
    try:
        proc = _spawn(["git", "-C", str(root), "ls-files", "-z", "--", *files], deadline, run)
    except (_Timeout, OSError):
        return every
    if proc.returncode != 0:
        return every
    return {_norm(str(root / n)) for n in proc.stdout.decode("utf-8", "replace").split("\0") if n}
