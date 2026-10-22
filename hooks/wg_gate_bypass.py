"""wg_gate_bypass.py：T2.19 繞閘嫌疑——被病形閘擋過之後讓同一批內容過關的指令要宣告；教怎麼繞閘的知識卡拒寫。

做什麼：
(a) 病形閘（handlers/pre_tool_use.check_smell_gate）擋下 commit 時，note_smell_deny 從擋訊息解析被點名的檔與病名，記進
    state["smell_deny_last"]（時間、repo 根、點名的檔與病、當時要提交的檔、transcript 長度；同一個 repo 還沒成功 commit 又被擋，
    點名的檔合併、不覆蓋，先前被點名又被排除在提交外的照留）。之後在同一個 repo 根底下，
    check 看這條 Bash／PowerShell 指令是不是嫌疑序列：
      · git restore --staged／reset／rm --cached／stash、svn revert／changelist 動到被點名的檔；
      · git／svn commit 的提交範圍不含被點名的檔；
      · git commit 帶 --no-verify（-n）或 -c core.hooksPath=。
    是嫌疑、或同一個 repo 根又要 commit，才重掃被點名的檔（暫存區與工作樹兩份都看）：同一條病都不在了＝病修掉了 → 清帳（cleared），不問。
    病還在 → 找宣告行「不是繞閘｜<理由>」（這條指令本身、或擋下之後 transcript 的回覆文字／工具參數／thinking，
    三管道同 lib/overview_hub.assistant_text_after）：有 → 放行、留帳 declared（理由全文）、同一組被點名的檔不再問；
    沒有 → 擋（規則 GATE_BYPASS_NEEDS_DECLARATION；同一個使用者回合同一組檔擋滿兩次就放行、留帳 cap_released）。成功 commit（post_tool_use）→ note_commit_done 清掉 smell_deny_last。
    --git-dir／GIT_DIR 的 commit 病形閘本身已擋（判不了），走不到這裡。state 是 session 級：上個 session 被擋、這個 session 繞不算。
(b) atom_refusal：卡片內容同時提到 Guardian 的閘、又含改暫存區／改提交範圍的做法字樣 → 拒寫（規則 ATOM_BYPASS_HOWTO_REFUSED）；
    AI 判斷不是在教繞法（寫的是禁止怎麼繞、在分析誤擋）→ 知識段第一行寫「不是教繞閘｜<理由>」就寫入、留帳 atom_declared；
    入口在 tools/memory-write-gate.py（MCP atom_write 的 create／append／replace 都經過）與 lib/atom_io.write_atom（程式寫手）。
是不是繞閘由 AI 判並寫理由；程式只核對序列事實與宣告行在不在，留帳 Logs/guard-gate_bypass.jsonl 給人抽查
（事件 suspect／declared／denied／cap_released／atom_refused／cleared）。開關 guard.gate_bypass.enabled（預設 True），做法字樣
guard.gate_bypass.staging_words。
怎麼跑案例：python -X utf8 -m pytest -q hooks/verify/verify_gate_bypass.py
"""
from __future__ import annotations

import fnmatch
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import wg_core

STATE_KEY = "smell_deny_last"
DECLARED_KEY = "bypass_declared"
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def gb_cfg(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return ((config or {}).get("guard") or {}).get("gate_bypass") or {}


def enabled(config: Optional[Dict[str, Any]]) -> bool:
    return bool(gb_cfg(config).get("enabled", True))


def _log(event: str, session_id: str, **kw: Any) -> None:
    wg_core.append_guard_log("gate_bypass", {"event": event, "session_id": session_id, **kw})


def _warn(msg: str) -> None:
    try:
        sys.stderr.write(f"[Guardian:GateBypass] {msg}\n")
    except OSError:
        pass


def _ptu():
    """拆指令沿用病形閘那一套（handlers/pre_tool_use）；惰性 import，避免與 pre_tool_use 互相 import。"""
    from handlers import pre_tool_use
    return pre_tool_use


def _canon(p: str) -> str:
    """比對用路徑鍵：與暫存判斷同一份正規化（handlers/_shared._comparable：8.3 短路徑轉長、`\\\\?\\` 前綴、`..`），再轉小寫。
    git rev-parse 回長路徑、hook 的 cwd 可能是短路徑，不轉會對不上同一個根。"""
    from handlers._shared import _comparable
    return _comparable(str(p)).rstrip("/").lower()


def _under(path: str, root: str) -> bool:
    a, b = _canon(path), _canon(root)
    return a == b or a.startswith(b + "/")


def _same_repo(run_cwd: str, last: Dict[str, Any]) -> bool:
    """這段指令落的 repo 就是上次被擋的那個：先看目錄在不在根底下（不在就不用問 git），在的話再問實際的版控根
    （根底下另開的 repo、submodule 是別的 repo）。"""
    root = last.get("root", "")
    return _under(run_cwd, root) and _canon(_repo_root(last.get("vcs", "git"), run_cwd)) == _canon(root)


# ─── (a) 記上一次病形閘擋了什麼 ───────────────────────────────────────────────

_SMELL_HEAD_RE = re.compile(r"^  ✗ ([^：\n]+)：")
_SMELL_FILE_RE = re.compile(r"^ {6}(.+?)(?: 第 \d+ 行|（整檔）)：")


def parse_smell_deny(message: str) -> Dict[str, List[str]]:
    """病形閘擋訊息 → {被點名的檔（git 為 repo 相對、svn 為 commit 目錄相對）: [病名…]}。
    解析的是 tools/project-smells.py render_commit_report 的新病段：`  ✗ <病名>：<為什麼>。怎麼改：…` 開一段，底下六格縮排
    一行一處 `<檔> 第 N 行：…` 或 `<檔>（整檔）：…`。病名取 ✗ 到第一個全形冒號；只提醒、舊病、放行段（`  · ` 開頭）不算。
    check_smell_gate 只回訊息字串、沒有結構化結果；擋訊息字樣改了要一起改這裡（verify_gate_bypass 用真實擋訊息釘住）。"""
    out: Dict[str, List[str]] = {}
    name = ""
    for ln in str(message or "").splitlines():
        m = _SMELL_HEAD_RE.match(ln)
        if m:
            name = m.group(1).strip()
            continue
        m = _SMELL_FILE_RE.match(ln) if name else None
        if m:
            names = out.setdefault(m.group(1).strip(), [])
            if name not in names:
                names.append(name)
        elif not ln.startswith(" " * 6):
            name = ""
    return out


def _repo_root(vcs: str, run_cwd: str) -> str:
    """commit 落的 repo 根：git rev-parse --show-toplevel／svn info wc-root；查不到用執行目錄本身。"""
    argv = (["git", "rev-parse", "--show-toplevel"] if vcs == "git"
            else ["svn", "--non-interactive", "info", "--show-item", "wc-root"])
    try:
        r = subprocess.run(argv, cwd=run_cwd or None, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=5, creationflags=_NO_WINDOW)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return run_cwd


def _commit_runs(command: str, tool_name: str, cwd: str) -> List[Tuple[str, str, List[str], List[Tuple[str, List[str]]]]]:
    """指令裡每個 commit 段 → (vcs, 執行目錄, tokens, 同一條指令前面的 git add)；拆法與病形閘相同。"""
    p = _ptu()
    shell = p._tool_shell(tool_name)
    body = p._strip_heredoc_bodies(command)
    out = []
    adds: List[Tuple[str, List[str]]] = []
    for repo_cd, tokens in p._git_segments(body, {"add", "commit"}, shell):
        run_cwd = p._resolve_run_cwd(repo_cd, cwd, shell)
        if tokens[0].lower() == "add":
            adds.append((run_cwd, tokens))
            continue
        out.append(("git", run_cwd, tokens, list(adds)))
    for repo_cd, tokens in p._svn_segments(body, {"commit", "ci"}, shell):
        out.append(("svn", p._resolve_run_cwd(repo_cd, cwd, shell), tokens, []))
    return out


def note_smell_deny(state: Optional[Dict[str, Any]], session_id: str, cwd: str, message: str, tool_name: str,
                    tool_input: Dict[str, Any], transcript_path: str, config: Dict[str, Any]) -> None:
    """病形閘 deny 分支呼叫：記 state["smell_deny_last"] 並寫回 state 檔。沒點名到檔（包裝、寫法拆不準、檢查出錯那幾種擋）不記：
    那幾種的修法是改寫指令，不是換提交範圍。永不拋例外（出錯只 stderr），不影響病形閘照擋。"""
    try:
        if not enabled(config):
            return
        if state is None:
            _warn("讀不到這個 session 的 state，病形閘這次擋了什麼記不下來（之後的繞閘嫌疑判不到）")
            return
        named = parse_smell_deny(message)
        runs = _commit_runs(tool_input.get("command", "") or "", tool_name, cwd) if named else []
        if not runs:
            return
        vcs, run_cwd, tokens, adds, root, files = _owner_run(runs, named)
        committing: List[str] = []
        if vcs == "git":
            try:
                found = _ptu()._smells_tool().commit_entries(run_cwd, tokens, adds)
                committing = sorted(found[3]) if found else []
            except Exception as e:  # noqa: BLE001
                _warn(f"記當時要提交的檔失敗（只少這筆證據）：{type(e).__name__}: {e}")
        here = {"offset": _transcript_size(transcript_path), "offsets": wg_core.transcript_sizes(transcript_path)}  # 主檔＋各子代理檔各記一個起點
        named_at = {rel: here for rel in files}
        prev = state.get(STATE_KEY)
        if isinstance(prev, dict) and prev.get("vcs") == vcs and _canon(str(prev.get("root") or "")) == _canon(root):
            # 同一個 repo 還沒成功 commit 又被擋：先前點名的檔（可能已被排除在這次提交外）照留，病名合併；
            # 每個檔記自己第一次被點名的起點（_named_since），宣告要寫在被點名之後才替它算數
            merged = {rel: list(names) for rel, names in (prev.get("files") or {}).items()}
            for rel, names in files.items():
                merged[rel] = list(dict.fromkeys(merged.get(rel, []) + list(names)))
            named_at = {rel: _named_at(prev, rel) or here for rel in merged}
            files = merged
        state[STATE_KEY] = {
            "at": time.strftime("%Y-%m-%d %H:%M:%S"), "vcs": vcs, "root": root, "files": files,
            "committing": committing[:200], "command": (tool_input.get("command", "") or "")[:300],
            "transcript_offset": here["offset"], "transcript_offsets": here["offsets"], "named_at": named_at,
        }
        _persist(session_id, state)
    except Exception as e:  # noqa: BLE001
        _warn(f"記病形閘擋下的檔失敗（繞閘嫌疑這次判不到）：{type(e).__name__}: {e}")


def _owner_run(runs, named: Dict[str, List[str]]):
    """擋訊息點名的檔屬於哪一段 commit（一條指令可能提交好幾個 repo）：被點名的檔都在那段的 repo 裡找得到（工作樹或暫存區）
    的第一段。回 (vcs, 執行目錄, tokens, adds, repo 根, {repo 根相對路徑: 病名})；svn 擋訊息的路徑相對 commit 目錄，這裡換成
    相對工作副本根。都對不上 → 第一段，stderr 說一聲。"""
    for vcs, run_cwd, tokens, adds in runs:
        root = _repo_root(vcs, run_cwd)
        base = run_cwd if vcs == "svn" else root
        files = {os.path.relpath(os.path.join(base, rel), root).replace("\\", "/"): names for rel, names in named.items()}
        if all(os.path.lexists(os.path.join(root, rel)) or _in_index(vcs, root, rel) for rel in files):
            return vcs, run_cwd, tokens, adds, root, files
    vcs, run_cwd, tokens, adds = runs[0]
    _warn("擋訊息點名的檔在這條指令的每個 commit 落點都找不到，記在第一段的 repo（繞閘嫌疑可能判不準）")
    return vcs, run_cwd, tokens, adds, _repo_root(vcs, run_cwd), named


def _in_index(vcs: str, root: str, rel: str) -> bool:
    if vcs != "git":
        return False
    return bool(_ptu()._git_lines(["ls-files", "--", rel], root))


def _named_at(last: Dict[str, Any], rel: str) -> Optional[Dict[str, Any]]:
    """帳上被點名的檔 rel 第一次被點名時 transcript 的起點 {"offset", "offsets"}；沒有 named_at 的舊紀錄用整筆的起點；
    不在帳上回 None。"""
    if rel not in (last.get("files") or {}):
        return None
    hit = (last.get("named_at") or {}).get(rel)
    return hit if isinstance(hit, dict) else {"offset": int(last.get("transcript_offset") or 0),
                                              "offsets": last.get("transcript_offsets")}


def _transcript_size(transcript_path: str) -> int:
    try:
        return Path(transcript_path).stat().st_size if transcript_path else 0
    except OSError:
        return 0


def _persist(session_id: str, state: Dict[str, Any]) -> None:
    if session_id:
        wg_core.write_state(session_id, state)


# ─── (a) 這條指令動到／排除了哪些被點名的檔 ─────────────────────────────────

_REV_RE = re.compile(r"^(?:HEAD|ORIG_HEAD|FETCH_HEAD|MERGE_HEAD|@)(?:[~^]\d*)*$|^[0-9a-f]{7,40}$", re.IGNORECASE)
_STASH_NOT_SAVE = {"list", "show", "pop", "apply", "drop", "clear", "branch", "create", "store"}
_VALUE_OPTS = {"restore": {"-s", "--source"}, "stash": {"-m", "--message", "--pathspec-from-file"},
               "reset": {"--pathspec-from-file"}, "rm": {"--pathspec-from-file"}}


def _split_args(sub: str, args: List[str]) -> Tuple[List[str], List[str]]:
    """git 子命令的參數 → (選項, 路徑)；`--` 之後全是路徑，帶值選項的值不算路徑。"""
    opts: List[str] = []
    paths: List[str] = []
    it = iter(args)
    for t in it:
        if t == "--":
            paths += list(it)
            break
        if t.startswith("-") and len(t) > 1:
            opts.append(t)
            if t in _VALUE_OPTS.get(sub, ()):
                next(it, None)
            continue
        paths.append(t)
    return opts, paths


def unstage_paths(tokens: List[str], run_cwd: str = "") -> Optional[List[str]]:
    """git restore --staged／reset／rm --cached／stash 段（tokens[0]＝子命令）→ 它動到暫存區的路徑規格（[]＝整個 repo）；
    不是改暫存區的寫法回 None（restore 沒帶 --staged 只動工作樹、rm 沒帶 --cached 是刪檔、stash list／pop… 不移出暫存）。
    reset 沒有 `--` 時，第一個參數在工作樹找不到檔就當 revision（HEAD、分支名、tag、雜湊），跟 git 自己的歧義規則同向。"""
    sub = tokens[0].lower()
    if sub not in _VALUE_OPTS:
        return None
    args = list(tokens[1:])
    if sub == "stash":
        head = args[0].lower() if args and not args[0].startswith("-") else ""
        if head in _STASH_NOT_SAVE:
            return None
        if head == "save":
            return []
        if head == "push":
            args = args[1:]
    opts, paths = _split_args(sub, args)
    if sub == "restore" and not any(o in ("--staged", "-S") or (not o.startswith("--") and "S" in o) for o in opts):
        return None
    if sub == "rm" and "--cached" not in opts:
        return None
    if sub == "reset" and "--" not in args and paths:
        first = paths[0]
        if _REV_RE.match(first) or not os.path.lexists(os.path.join(run_cwd, first)):
            paths = paths[1:]
    return paths


def _hit_files(specs: List[str], run_cwd: str, root: str, files: Sequence[str]) -> List[str]:
    """路徑規格（相對 run_cwd；[]＝整個 repo）命中哪些被點名的檔（相對 root）：同一個檔、它的上層目錄、萬用字元都算。
    git 的 magic pathspec（`:(top)…`、`:!…`、`:(exclude)…`，`:/` 除外）這裡不模擬：判不了範圍就當動到（寧可多問一次宣告）。"""
    if not specs:
        return list(files)
    if any(s.startswith(":") and s not in (":/", ":/*") for s in specs):
        return list(files)
    hits = []
    for rel in files:
        target = _canon(os.path.join(root, rel))
        for spec in specs:
            base = root if spec in (":/", ":/*") else os.path.join(run_cwd, spec)
            pat = _canon(base)
            if target == pat or target.startswith(pat + "/") or fnmatch.fnmatchcase(target, pat):
                hits.append(rel)
                break
    return hits


def _no_verify(tokens: List[str]) -> bool:
    """git commit 的 tokens 帶 --no-verify 或短旗標組裡的 -n（-m／-F 這類帶值旗標之後的字是值，不算）。"""
    for t in tokens[1:]:
        if t == "--":
            return False
        if t == "--no-verify":
            return True
        if t.startswith("-") and not t.startswith("--") and "n" in re.split(r"[mFCct]", t[1:], maxsplit=1)[0]:
            return True
    return False


_HOOKSPATH_RE = re.compile(r"-c\s*['\"]?core\.hookspath\s*=", re.IGNORECASE)


def sequence_facts(command: str, tool_name: str, cwd: str, last: Dict[str, Any], files: Sequence[str]) -> List[str]:
    """這條指令對被點名的檔做了什麼（一行一件；空清單＝不是嫌疑序列）。只看落在上次被擋那個 repo 根底下的段。"""
    p = _ptu()
    shell = p._tool_shell(tool_name)
    body = p._strip_heredoc_bodies(command)
    root, vcs = last["root"], last.get("vcs", "git")
    facts: List[str] = []
    if vcs == "git":
        for repo_cd, tokens in p._git_segments(body, set(_VALUE_OPTS), shell):
            run_cwd = p._resolve_run_cwd(repo_cd, cwd, shell)
            specs = unstage_paths(tokens, run_cwd)
            hits = _hit_files(specs, run_cwd, root, files) if specs is not None and _same_repo(run_cwd, last) else []
            if hits:
                facts.append(f"git {tokens[0]} 把 {'、'.join(hits)} 移出暫存區")
    else:
        for repo_cd, tokens in p._svn_segments(body, {"revert", "changelist", "cl"}, shell):
            run_cwd = p._resolve_run_cwd(repo_cd, cwd, shell)
            paths = [t for t in tokens[1:] if not t.startswith("-")]
            hits = _hit_files(paths or ["."], run_cwd, root, files) if _same_repo(run_cwd, last) else []
            if hits:
                facts.append(f"svn {tokens[0]} 動到 {'、'.join(hits)}")
    for kind, run_cwd, tokens, adds in _commit_runs(command, tool_name, cwd):
        if kind != vcs or not _same_repo(run_cwd, last):
            continue
        if kind == "git" and _no_verify(tokens):
            facts.append("git commit 帶 --no-verify（跳過 git hook）")
        elif kind == "git" and _HOOKSPATH_RE.search(body):
            facts.append("git commit 帶 -c core.hooksPath=（換掉 git hook）")
        left = _excluded(kind, run_cwd, tokens, adds, root, files)
        if left:
            facts.append(f"{kind} commit 的提交範圍不含 {'、'.join(left)}")
    return facts


def _excluded(vcs: str, run_cwd: str, tokens: List[str], adds: List[Tuple[str, List[str]]], root: str,
              files: Sequence[str]) -> List[str]:
    """commit 的提交範圍沒包含的被點名檔。git 用病形閘同一份 commit_entries（暫存區、-a、pathspec、前面的 git add）；
    svn 看 commit 後面的路徑（沒給＝整個工作副本，都包含）。拆不出範圍（病形閘也會擋）回空。"""
    tool = _ptu()._smells_tool()
    if vcs == "svn":
        paths = tool.svn_commit_args(tokens)[0]
        return [rel for rel in files if paths and not _hit_files(paths, run_cwd, root, [rel])]
    try:
        found = tool.commit_entries(run_cwd, tokens, adds)
    except Exception as e:  # noqa: BLE001
        _warn(f"拆 commit 範圍失敗（這段不判）：{type(e).__name__}: {e}")
        return []
    if not found:
        return []
    entries = {_canon(os.path.join(found[0], rel)) for rel, (src, _old) in found[3].items() if src != "gone"}
    return [rel for rel in files if _canon(os.path.join(root, rel)) not in entries]


def still_sick(last: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, List[str]]:
    """被點名的檔重掃：暫存區與工作樹兩份（svn 只有工作樹）各跟 HEAD／BASE 比，仍有上次點名的同一條病的 → {檔: [病名]}。
    用病形閘同一份判法（project-smells classify）。拋例外＝判不了，呼叫端照「病還在」處理。
    替身的落差：病改成另一種病形就不算同一條病（再提交時病形閘本身會擋）；檔刪掉＝兩份都沒有＝病不在。"""
    tool = _ptu()._smells_tool()
    root, vcs = last["root"], last.get("vcs", "git")
    limits = tool.limits_of(config)
    has_head = vcs == "git" and tool._vcs(["git", "rev-parse", "--verify", "-q", "HEAD"], root).returncode == 0
    out: Dict[str, List[str]] = {}
    for rel, names in (last.get("files") or {}).items():
        abs_path = os.path.join(root, rel)
        if vcs == "git":
            blobs = tool._cat_blobs(root, ([f"HEAD:{rel}"] if has_head else []) + [f":{rel}"])
            old, versions = blobs.get(f"HEAD:{rel}"), [blobs.get(f":{rel}")]
        else:
            cat = tool._vcs(["svn", "--non-interactive", "cat", "-r", "BASE", abs_path], root)
            old, versions = (cat.stdout if cat.returncode == 0 else b""), []
        if os.path.lexists(abs_path):                 # 檔不在＝工作樹沒這份；在卻讀不到就拋出去（判不了，不能當病修掉了）
            versions.append(Path(abs_path).read_bytes())
        for new in versions:
            if new is None or new == old:
                continue
            res = tool.classify([{"path": rel, "abs": abs_path, "old": (old or b"").decode("utf-8", "replace"),
                                  "new": new.decode("utf-8", "replace")}], limits=limits)
            hit = sorted({h["name"] for h in res["new"]} & set(names))
            if hit:
                out[rel] = hit
                break
    return out


# ─── (a) 宣告行與判定 ─────────────────────────────────────────────────────────

DECLARE_EXAMPLE = "不是繞閘｜<理由：這批檔是誰的、為什麼不該進這筆、病要誰修>"
# 宣告要自成一行：指令與工具參數裡是 `#` 註解行；回覆文字與 thinking 是行首（可帶清單符號 - 或 *，或寫成 `#` 註解）。
# 句子中間提到、引號或 `>` 引用裡的範例都不算。
_DECLARE_COMMENT_RE = re.compile(r"^[ \t]*#[ \t]*不是繞閘[ \t]*[｜|][ \t]*(.+)$", re.MULTILINE)
_DECLARE_LINE_RE = re.compile(r"^[ \t]*(?:[-*][ \t]+|#[ \t]*)?不是繞閘[ \t]*[｜|][ \t]*(.+)$", re.MULTILINE)


def find_declaration(command: str, transcript_path: str, offset: int, agent_id: str = "",
                     offsets: Optional[Dict[str, int]] = None) -> Optional[Tuple[str, str]]:
    """宣告行「不是繞閘｜<理由>」→ (理由, 管道)：先看這條指令本身，再看擋下之後 transcript 的三管道——主檔與子代理檔都看
    （wg_core.assistant_texts_since；起點 offsets 各檔各記，沒有就用舊的單一 offset）；
    理由要有文字內容、不是擋訊息範例的角括號佔位（wg_release_rules.reason_present）。沒有回 None。
    理由合不合理、是不是在否定語境裡引用，程式不判：宣告與理由全文留帳 declared 給人抽查。"""
    import wg_release_rules as rr
    lib = str(Path(__file__).resolve().parents[1] / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    from overview_hub import LOCATE_CHANNELS
    sources = [("command", command, _DECLARE_COMMENT_RE)] + [
        (ch, wg_core.assistant_texts_since(transcript_path, agent_id, ch, offsets, offset),
         _DECLARE_COMMENT_RE if ch == "tool_input" else _DECLARE_LINE_RE)
        for ch in LOCATE_CHANNELS]
    for via, text, rx in sources:
        for m in reversed(list(rx.finditer(text or ""))):
            reason = m.group(1).strip()
            if rr.reason_present(reason):
                return reason, via
    return None


def _declared_key(last: Dict[str, Any], files: Sequence[str]) -> str:
    """宣告記帳的鍵：repo 根＋被點名的檔＋它們此刻工作樹內容的雜湊。內容變了（又改了那個檔）就是另一批內容，要重新宣告。"""
    import hashlib
    parts = []
    for rel in sorted(files):
        p = Path(last["root"]) / rel
        try:
            digest = hashlib.sha1(p.read_bytes()).hexdigest()[:12] if p.exists() else "-"
        except OSError:
            digest = "?"
        parts.append(f"{rel}@{digest}")
    return _canon(last["root"]) + "|" + "|".join(parts)


def _deny_text(v, last: Dict[str, Any]) -> str:
    import wg_release_rules as rr
    return "\n".join((
        "[Guardian:GateBypass] 繞閘嫌疑：上次被病形閘點名的檔病還在，這條指令把它移出暫存或排除在提交之外，已先擋下。"
        "是不是在繞閘由你判斷並寫理由（例如這批檔是別人的、你是在撤掉一整批錯誤改動）。",
        "宣告行要比這條指令早一則訊息送出（跟指令同一則送出的文字，這裡還看不到），或寫成這條 Bash／PowerShell 指令開頭的 `#` 註解：",
        f"  {DECLARE_EXAMPLE}",
        rr.format_hit("gb", v),
        "閘擋了之後能做的是修掉病，或說明為什麼這批內容不該進這筆，不是找路繞過：",
        "- 病還在就修病（修完重掃沒病自動清帳，不用宣告）；",
        "- 是別人的檔、不屬這次需求 → 照上面的寫法寫明是誰的；",
        "- 確定閘誤擋 → 寫追蹤項（「｜建議：…｜該誰解：…」）而不是繞。",
        f"（上次擋在 {last.get('at', '?')}，repo {last.get('root', '?')}）",
    ))


def _merged_offsets(records: Sequence[Any]) -> Optional[Dict[str, int]]:
    """擋下那筆與之後各次宣告記的各檔起點，每個檔取最晚的；都沒有各檔起點（舊紀錄）回 None。"""
    dicts = [r for r in records if isinstance(r, dict)]
    if not dicts:
        return None
    out: Dict[str, int] = {}
    for d in dicts:
        for k, v in d.items():
            out[k] = max(out.get(k, 0), int(v or 0))
    return out


def check(tool_name: str, tool_input: Dict[str, Any], cwd: str, config: Dict[str, Any],
          state: Optional[Dict[str, Any]], session_id: str, transcript_path: str, agent_id: str = "") -> Optional[str]:
    """PreToolUse GateBypass 段：嫌疑序列沒宣告 → 擋訊息；其餘 None。state 有改（清帳、記宣告）就寫回 state 檔。
    重掃判不了當病還在；其他非預期錯誤 stderr 後放行（本閘守的是繞法，帶病的提交病形閘本身照擋）。"""
    if tool_name not in ("Bash", "PowerShell") or not enabled(config) or not state:
        return None
    last = state.get(STATE_KEY)
    command = tool_input.get("command", "") or ""
    if not isinstance(last, dict) or not last.get("files") or not command:
        return None
    try:
        facts = sequence_facts(command, tool_name, cwd, last, list(last["files"]))
        commits_here = any(_same_repo(run_cwd, last) for _v, run_cwd, _t, _a in _commit_runs(command, tool_name, cwd))
        if not facts and not commits_here:
            return None
        try:
            sick = still_sick(last, config)
        except Exception as e:  # noqa: BLE001
            _warn(f"重掃被點名的檔失敗，當成病還在：{type(e).__name__}: {e}")
            sick = dict(last["files"])
        if not sick:
            state.pop(STATE_KEY, None)
            _log("cleared", session_id, reason="rescan_clean", root=last.get("root"), files=list(last["files"]))
            _persist(session_id, state)
            return None
        if facts and set(sick) != set(last["files"]):
            facts = sequence_facts(command, tool_name, cwd, last, list(sick))
        key = _declared_key(last, sick)
        group = _canon(last["root"]) + "|" + "|".join(sorted(sick))
        prior = [d for d in state.get(DECLARED_KEY) or [] if isinstance(d, dict) and d.get("group") == group]
        if not facts or any(d.get("key") == key for d in prior):
            return None
        import wg_release_rules as rr
        denied = "；".join(f"{f}（{'、'.join(n)}）" for f, n in sick.items())
        _log("suspect", session_id, root=last.get("root"), files=sick, facts=facts, command=command[:300])
        # 宣告只認還病著的每個檔都被點名之後寫的；同一組檔宣告過、內容又變了（另一批內容）：只認上一次宣告之後新寫的
        since = [_named_at(last, rel) or {} for rel in sick]
        offset = max([int(s.get("offset") or 0) for s in since] + [int(d.get("offset") or 0) for d in prior])
        offsets = _merged_offsets([s.get("offsets") for s in since] + [d.get("offsets") for d in prior])
        decl = find_declaration(command, transcript_path, offset, agent_id, offsets)
        v = rr.gate_bypass_verdict(denied, facts, decl[0] if decl else "")
        if not v.owed:
            state.setdefault(DECLARED_KEY, []).append({"key": key, "group": group, "reason": decl[0], "via": decl[1],
                                                        "offset": _transcript_size(transcript_path),
                                                        "offsets": wg_core.transcript_sizes(transcript_path),
                                                        "at": time.strftime("%Y-%m-%d %H:%M:%S")})
            _log("declared", session_id, root=last.get("root"), files=sick, facts=facts, reason=decl[0], via=decl[1])
            _persist(session_id, state)
            return None
        # 擋次上限（wg_core.deny_cap）：缺件＝這組被點名的檔；同一個使用者回合擋滿兩次就放行、留帳 cap_released
        denied, released = wg_core.deny_cap(state, "gate_bypass", [group])
        _persist(session_id, state)
        if released:
            _log("cap_released", session_id, root=last.get("root"), files=sick, facts=facts, rule=v.rule)
        if not denied:
            return None
        _log("denied", session_id, root=last.get("root"), files=sick, facts=facts, rule=v.rule)
        return _deny_text(v, last)
    except Exception as e:  # noqa: BLE001
        _warn(f"檢查異常（這次不判）：{type(e).__name__}: {e}")
        return None


def note_commit_done(state: Dict[str, Any], session_id: str, command: str, tool_name: str, cwd: str) -> bool:
    """post_tool_use：commit 跑完了、落在上次被擋的 repo 根底下 → 清掉 smell_deny_last（只改 dict，寫檔由呼叫端）。回有沒有清。"""
    last = state.get(STATE_KEY)
    if not isinstance(last, dict):
        return False
    try:
        runs = _commit_runs(command, tool_name, cwd)
    except Exception as e:  # noqa: BLE001
        _warn(f"commit 之後判落點失敗（不清帳）：{type(e).__name__}: {e}")
        return False
    if not any(_same_repo(run_cwd, last) for _v, run_cwd, _t, _a in runs):
        return False
    state.pop(STATE_KEY, None)
    _log("cleared", session_id, reason="commit", root=last.get("root"), files=list(last.get("files") or {}))
    return True


# ─── (b) 教怎麼繞閘的知識卡拒寫 ───────────────────────────────────────────────

GATE_WORDS = ("SmellGate", "病形閘", "隱私閘", "PrivacyGate", "CommitOrder", "NeedGoal")
_GUARDIAN_TAG_RE = re.compile(r"\[Guardian:([A-Za-z0-9_-]+)")
# 做法字樣：改暫存區、改提交範圍、跳過 hook 的寫法。只提「pathspec」「暫存區」「reset」這種名詞不算（記閘的機制、
# 記 git 用法都會用到），要帶動作或指令形
DEFAULT_STAGING_WORDS = (
    "restore --staged", "rm --cached", "git stash", "git reset", "reset head", "--no-verify", "hookspath",
    "改 pathspec", "改用 pathspec", "pathspec commit", "pathspec 提交", "commit -- ",
    "移出暫存", "拆三步", "分開提交", "stage 回", "放回暫存",
)


def bypass_signals(text: str, config: Optional[Dict[str, Any]] = None) -> Tuple[List[str], List[str]]:
    """(提到的 Guardian 閘, 命中的做法字樣)。閘：[Guardian: 標籤、GATE_WORDS、wg_release_rules.RULES 的規則名（整詞）；
    做法字樣：guard.gate_bypass.staging_words（沒設用 DEFAULT_STAGING_WORDS），不分大小寫子字串。"""
    import wg_release_rules as rr
    text = str(text or "")
    low = text.lower()
    gates = [f"[Guardian:{m}]" for m in dict.fromkeys(_GUARDIAN_TAG_RE.findall(text))]
    gates += [w for w in GATE_WORDS if w.lower() in low]
    gates += [name for name in rr.RULES if re.search(rf"(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])", text)]
    words = gb_cfg(config).get("staging_words")
    words = [str(w) for w in words] if isinstance(words, list) else list(DEFAULT_STAGING_WORDS)
    return list(dict.fromkeys(gates)), [w for w in words if w and w.lower() in low]


ATOM_DECLARE_EXAMPLE = "不是教繞閘｜<理由：這張卡在教什麼>"


def atom_declaration(knowledge: Sequence[str]) -> str:
    """知識段第一行的「不是教繞閘｜<理由>」→ 理由；沒有回空字串（有沒有填、是不是佔位交 wg_release_rules 判）。
    宣告放第一行（可帶 [臨] 這類信心前綴）：MCP atom_write 不用加欄位、js 零改動；宣告的樣子與落檔前的剝除共用
    lib/atom_spec.BYPASS_DECLARATION_RE，宣告行不會留在卡裡。"""
    lib = str(Path(__file__).resolve().parents[1] / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    from atom_spec import BYPASS_DECLARATION_RE
    first = str((list(knowledge or []) or [""])[0]).splitlines()
    m = BYPASS_DECLARATION_RE.match(first[0]) if first else None
    return m.group(1) if m else ""


def atom_refusal(title: str, knowledge: Sequence[str], actions: Optional[Sequence[str]] = None,
                 config: Optional[Dict[str, Any]] = None, source: str = "") -> Optional[str]:
    """寫卡前呼叫：兩訊號同時命中、知識段第一行沒有「不是教繞閘｜理由」→ 拒寫訊息（留帳 atom_refused，訊息末尾印宣告入口）；
    有宣告 → 寫入、留帳 atom_declared（理由全文＋卡名）；其餘 None。是不是真的在教繞法由 AI 判並寫理由，程式只核對有沒有寫。
    config 沒給讀 workflow/config.json。"""
    if config is None:
        config = wg_core.load_config()
    if not enabled(config):
        return None
    import wg_release_rules as rr
    text = "\n".join([str(title or "")] + [str(k) for k in knowledge or []] + [str(a) for a in actions or []])
    gates, words = bypass_signals(text, config)
    reason = atom_declaration(knowledge)
    v = rr.atom_bypass_verdict(gates, words, reason)
    if not v.owed:
        if gates and words:
            _log("atom_declared", "", title=str(title)[:120], reason=reason, gates=gates, words=words, source=source)
        return None
    _log("atom_refused", "", title=str(title)[:120], gates=gates, words=words, declared=reason, source=source)
    return (f"這張卡在教怎麼繞 {'、'.join(gates)}。閘誤擋要修判定（加規則＋紅案例），不寫繞法；確定誤擋就寫追蹤項。"
            "要記的是「為什麼那批檔不該進這筆」就改寫成那句再寫。\n" + rr.format_hit("gb", v) + "\n"
            "先問：讀完這張卡的人，能不能照著做，讓閘擋下的內容不經修正就過關（例如把被點名的帶病檔送進版控）？"
            "能 → 就是在教繞法，即使你認為那次是誤擋：改寫成「為什麼那批檔不該進這筆」或寫追蹤項，不要宣告；"
            "不能（寫的是禁止怎麼繞、教的是修病）→ 知識段第一行寫"
            f"「{ATOM_DECLARE_EXAMPLE}」再寫一次，會寫入並留帳給人抽查。")
