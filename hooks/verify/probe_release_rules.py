"""probe_release_rules.py — 放行／欠帳判定規則（hooks/wg_release_rules.py，045）的真 hook 入口情境探針。

做什麼：每個情境建自己的 tmp 資料根（WG_CLAUDE_DIR）、tmp 家目錄（HOME／USERPROFILE）、tmp 系統暫存（TEMP／TMP／TMPDIR）、
tmp Logs（WG_TEST_LOGS_DIR）與專案，用受測樹的真 hook 入口 hooks/workflow-guardian.py 餵造好的事件 JSON，對照「規則」預期：
  P1 先紅後綠不擋（CASE_GREEN_AFTER_EDIT）        P2 worktree 移除後 Stop 不擋（GONE_OUTSIDE_VCS）
  P3 merge 時 checkout --theirs 不擋（CONTENT_EQUALS_COMMITTED）   P4 python -c 唯讀放行、node -e 擋且指路（INLINE_PY_READONLY）
  P5 唯讀 git 放行、會寫的擋且留 guard-crossrealm.jsonl（GIT_READONLY_SUBCMD）   P6 擋滿訊息列全部條目（BLOCK_BUDGET_PER_RULE）
  P7 暫存目錄 repo 的 commit 免口令（TEMP_REPO_COMMIT_EXEMPT）   P8 暫存目錄副本不注入不擋（TEMP_COPY_NOT_PROJECT）
  P9 刪執行期資料目錄免綜觀（RUNTIME_DATA_NO_OVERVIEW）
不是 pytest 案例（檔名不以 verify_／test_ 開頭）；pytest 案例在 verify_release_rules.py 與各閘 verify 檔。

怎麼跑：python -X utf8 hooks/verify/probe_release_rules.py --tree <受測 worktree> [--only P1,P4] [--keep] [--json <輸出檔>]
尾行：RELEASE_RULES_PROBE DONE k=v（統計）之後，最後一行 RELEASE_RULES_PROBE_CHECK PASS|FAIL（全部檢查點符合規則才 PASS）。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

CONFIG_OFF = {
    "vector_search": {"enabled": False, "auto_start_service": False, "auto_index_on_change": False},
    "vcs_sync": {"enabled": False},
    "codex_companion": {"enabled": False},
    "provenance": {"enabled": False},
    "response_capture": {"enabled": False},
    # 需求目標流程（改程式前要有目標樹）不是本探針的對象：沙箱裡關掉，免得 P3 的 checkout --theirs 被它擋
    "overview_hub": {"need_goal": {"enabled": False}},
}
SIMPLE_MAP = """# 部位表（探針用）

| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 量尺（量法｜指令｜門檻） |
|---|---|---|---|---|
| `src/` | 程式層 | 無 | 無 | 單元測試｜`python -X utf8 -m pytest -q tests`｜全綠 |
"""
TEXT_DONE = "全部完成了。所有工作都已經處理完畢，請直接參考上方的說明內容即可。"
TEXT_FIXED = "修好了，全部完成了。a.py 的問題已經處理掉，後續不需要再做任何其他事情。"


def slug_of(cwd: str) -> str:
    return cwd.replace(":", "-").replace("\\", "-").replace("/", "-").replace(".", "-").lower()


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "user.email=p@p", "-c", "user.name=p", "-C", str(cwd), *args],
                          capture_output=True, text=True, encoding="utf-8", check=check)


class Sandbox:
    def __init__(self, tree: Path, base: Path, name: str):
        self.tree, self.dir = tree, base / name
        self.data, self.home, self.systmp, self.logs = self.dir / "data", self.dir / "home", self.dir / "systmp", self.dir / "logs"
        for d in (self.data / "workflow", self.home / ".claude" / "memory" / "_meta", self.systmp, self.logs):
            d.mkdir(parents=True, exist_ok=True)
        cfg = json.loads((tree / "workflow" / "config.json").read_text(encoding="utf-8"))
        for sec, vals in CONFIG_OFF.items():
            cfg.setdefault(sec, {})
            if isinstance(cfg[sec], dict):
                cfg[sec].update(vals)
        (self.data / "workflow" / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.home / ".claude" / "workflow").mkdir(parents=True, exist_ok=True)
        (self.home / ".claude" / "workflow" / "config.json").write_text(json.dumps({"vector_search": {"ollama_backends": {
            "probe-remote": {"enabled": True, "base_url": "http://127.0.0.1:1"}}}}), encoding="utf-8")
        for dst in (self.home / ".claude" / "memory" / "_meta", self.data / "memory" / "_meta"):
            shutil.copytree(tree / "memory" / "_meta", dst, dirs_exist_ok=True)
        if (tree / "prompts").is_dir():
            shutil.copytree(tree / "prompts", self.data / "prompts", dirs_exist_ok=True)

    def env(self) -> dict:
        e = dict(os.environ)
        e.pop("CLAUDE_COMPANION_JUDGE", None)
        e.pop("WG_TEMP_RULES", None)
        e.update({
            "WG_CLAUDE_DIR": str(self.data), "HOME": str(self.home), "USERPROFILE": str(self.home),
            "TEMP": str(self.systmp), "TMP": str(self.systmp), "TMPDIR": str(self.systmp),
            "WG_TEST_LOGS_DIR": str(self.logs),
            "PYTHONPATH": os.pathsep.join([str(self.tree / "lib"), str(self.tree / "tools"), str(self.tree)]),
            "CLAUDE_CODE_ENTRYPOINT": "cli", "PYTHONIOENCODING": "utf-8",
        })
        return e

    def project(self, rel: str, map_text: str = "") -> Path:
        p = self.dir / rel
        (p / "_AIDocs").mkdir(parents=True, exist_ok=True)
        if map_text:
            (p / ".claude").mkdir(parents=True, exist_ok=True)
            (p / ".claude" / "overview-map.md").write_text(map_text, encoding="utf-8")
        return p


def reason_of(step: dict) -> str:
    j = step.get("json") or {}
    hso = j.get("hookSpecificOutput") or {}
    return str(j.get("reason") or hso.get("permissionDecisionReason") or "")


def classify(step: dict) -> str:
    if any("[workflow-guardian] Error in" in ln for ln in step.get("stderr_tail") or []):
        return "hook-error"
    j = step.get("json") or {}
    if (j.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny":
        return "deny"
    if j.get("decision") == "block":
        return "block"
    return "pass"


class Session:
    def __init__(self, sb: Sandbox, cwd: Path):
        self.sb, self.cwd = sb, cwd
        self.sid = f"probe-{uuid.uuid4().hex[:12]}"
        self.transcript = sb.data / "projects" / slug_of(str(cwd)) / f"{self.sid}.jsonl"
        self.transcript.parent.mkdir(parents=True, exist_ok=True)
        self.transcript.touch()
        self.steps, self.last_pre, self._n = [], {"result": "none"}, 0

    def _id(self) -> str:
        self._n += 1
        return f"toolu_probe_{self._n:03d}"

    def _rec(self, obj: dict) -> None:
        obj.setdefault("entrypoint", "cli")
        obj.setdefault("sessionId", self.sid)
        obj.setdefault("isSidechain", False)
        obj.setdefault("uuid", uuid.uuid4().hex)
        with open(self.transcript, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def hook(self, event: dict, label: str) -> dict:
        payload = {"session_id": self.sid, "cwd": str(self.cwd), "transcript_path": str(self.transcript), **event}
        t0 = time.monotonic()
        run_cwd = str(self.cwd) if self.cwd.is_dir() else str(self.sb.dir)      # worktree 被移除後 hook 行程仍要起得來
        r = subprocess.run([sys.executable, "-X", "utf8", str(self.sb.tree / "hooks" / "workflow-guardian.py")],
                           input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), capture_output=True,
                           env=self.sb.env(), cwd=run_cwd, timeout=180)
        out = r.stdout.decode("utf-8", "replace").strip()
        parsed = None
        for line in reversed(out.splitlines()):
            if line.strip().startswith("{"):
                try:
                    parsed = json.loads(line)
                    break
                except ValueError:
                    continue
        step = {"label": label, "event": event.get("hook_event_name"), "rc": r.returncode, "ms": int((time.monotonic() - t0) * 1000),
                "json": parsed, "stderr_tail": r.stderr.decode("utf-8", "replace").strip().splitlines()[-8:]}
        step["result"] = classify(step)
        self.steps.append(step)
        return step

    def session_start(self) -> dict:
        return self.hook({"hook_event_name": "SessionStart", "source": "startup"}, "SessionStart")

    def prompt(self, text: str) -> dict:
        self._rec({"type": "user", "message": {"role": "user", "content": text}})
        return self.hook({"hook_event_name": "UserPromptSubmit", "prompt": text}, "UserPromptSubmit")

    def write_gated(self, path: Path, content: str, tool: str = "Write") -> dict:
        """PreToolUse（OverviewHub 閘）→ 沒被 deny 才真的寫檔並送 PostToolUse。回 Post 那步；被 deny 回 Pre 那步。"""
        tid = self._id()
        ti = {"file_path": str(path), "content": content}
        pre = self.hook({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_use_id": tid, "tool_input": ti}, f"PreToolUse Write {path.name}")
        self.last_pre = pre
        if pre["result"] == "deny":
            return pre
        return self._write_post(path, content, tool, tid)

    def write(self, path: Path, content: str, tool: str = "Write") -> dict:
        """寫檔並只送 PostToolUse（當作 OverviewHub 已放行；那道閘不是本探針的對象，P8 另用 write_gated 驗它）。"""
        return self._write_post(path, content, tool, self._id())

    def _write_post(self, path: Path, content: str, tool: str, tid: str) -> dict:
        ti = {"file_path": str(path), "content": content}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        self._rec({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": tool, "input": ti}]}})
        self._rec({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": "ok"}]}})
        return self.hook({"hook_event_name": "PostToolUse", "tool_name": tool, "tool_use_id": tid, "tool_input": ti,
                          "tool_response": {"type": "create", "filePath": str(path), "content": content}}, f"PostToolUse Write {path.name}")

    def read(self, path: Path) -> dict:
        """Read 工具的 PostToolUse（OverviewHub 的讀檔證據）。"""
        tid = self._id()
        ti = {"file_path": str(path)}
        self._rec({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": "Read", "input": ti}]}})
        self._rec({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": "…"}]}})
        return self.hook({"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_use_id": tid, "tool_input": ti,
                          "tool_response": {"type": "text", "file": {"filePath": str(path), "content": "…"}}}, f"PostToolUse Read {path.name}")

    def bash(self, cmd: str, stdout: str = "", exit_code: int = 0, run: bool = False) -> dict:
        """PreToolUse → 沒被 deny 才（run=True 時真的執行）記 transcript 並送 PostToolUse。"""
        tid = self._id()
        pre = self.hook({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_use_id": tid, "tool_input": {"command": cmd}},
                        f"PreToolUse Bash `{cmd[:70]}`")
        self.last_pre = pre
        if pre["result"] == "deny":
            return pre
        if run:
            r = subprocess.run(cmd, shell=True, cwd=str(self.cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")
            stdout, exit_code = (r.stdout or "") + (r.stderr or ""), r.returncode
        self._rec({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": cmd}}]}})
        resp = {"stdout": stdout, "stderr": "", "interrupted": False, "isImage": False} if exit_code == 0 else f"Error: Exit code {exit_code}\n{stdout}"
        self._rec({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": stdout}]}})
        return self.hook({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_use_id": tid, "tool_input": {"command": cmd},
                          "tool_response": resp}, f"PostToolUse Bash `{cmd[:70]}`")

    def stop(self, text: str, active: bool = False) -> dict:
        self._rec({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}})
        return self.hook({"hook_event_name": "Stop", "stop_hook_active": active, "last_assistant_message": text}, f"Stop「{text[:20]}…」")


class Checks:
    def __init__(self, sid: str, title: str):
        self.sid, self.title, self.rows = sid, title, []

    def add(self, what: str, actual: str, rule: str, note: str = "") -> None:
        self.rows.append({"what": what, "actual": actual, "rule": rule, "ok": actual == rule, "note": note})


CODE_TAGS = ("[Guardian:ReconcileGate]", "[Guardian:MeasureGate]", "[Guardian:TestFailGate]")


def _d(step: dict) -> str:
    """Stop 的寫碳查核結果：pass（放行，或只被排在寫碼查核後面的閘擋，例：KnowledgeHarvest）／block(d)／block(a)／
    block(TestFailGate)／deny／hook-error。"""
    r = reason_of(step)
    if step["result"] == "block":
        if not any(t in r for t in CODE_TAGS):
            return "pass"
        if "OWED_AFTER_LAST_CASE" in r or "(d)" in r:
            return "block(d)"
        if "CLAIM_FIXED_NEEDS_PASS" in r:
            return "block(a)"
        return "block(" + r.split("]")[0].strip("[").replace("Guardian:", "") + ")"
    return step["result"]


# ── 情境 ──

def p1(tree, base):
    c = Checks("P1", "先紅後綠：加案例跑紅 → 改程式 → 跑綠 → Stop 不擋（CASE_GREEN_AFTER_EDIT）；改程式後沒跑 → 照擋")
    sb = Sandbox(tree, base, "p1")
    proj = sb.project("proj")
    s = Session(sb, proj)
    s.session_start()
    s.prompt("修 src/a.py 並先寫會紅的案例")
    s.write(proj / "src" / "a.py", "def f(x):\n    return x\n")
    s.write(proj / "tests" / "test_a.py", "from src.a import f\n\n\ndef test_f():\n    assert f(1) == 2\n")
    s.bash("python -X utf8 -m pytest -q tests/test_a.py", "F\nFAILED tests/test_a.py::test_f - assert 1 == 2\n1 failed in 0.02s\n", exit_code=1)
    s.write(proj / "src" / "a.py", "def f(x):\n    return x + 1\n")
    st = s.stop(TEXT_DONE)
    c.add("改程式後還沒跑綠就 Stop（TestFailGate 或 (d) 都算擋）", st["result"], "block", note=_d(st))
    s.bash("python -X utf8 -m pytest -q tests/test_a.py", ".\n1 passed in 0.01s\n")
    st = s.stop(TEXT_DONE, active=True)
    c.add("跑綠後 Stop（案例 mtime 早於程式）", _d(st), "pass", note=reason_of(st)[:100] if st["result"] != "pass" else "")
    return c, [s]


def p2(tree, base):
    c = Checks("P2", "worktree 移除後 Stop 不擋（GONE_OUTSIDE_VCS）")
    sb = Sandbox(tree, base, "p2")
    wt = sb.project("wt")
    git(wt, "init", "-q")
    s = Session(sb, wt)
    s.session_start()
    s.prompt("改 lib/x.py 並補案例")
    s.write(wt / "lib" / "x.py", "x = 1\n")
    s.write(wt / "tools" / "verify" / "verify_x.py", "def test_x():\n    pass\n")
    shutil.rmtree(wt)
    st = s.stop(TEXT_DONE)
    c.add("整根消失後 Stop", _d(st), "pass", note=reason_of(st)[:100] if st["result"] != "pass" else "")
    return c, [s]


def p3(tree, base):
    c = Checks("P3", "merge main 衝突時 checkout --theirs 取 main 版 → Stop 不擋（CONTENT_EQUALS_COMMITTED）；自己改內容 → 照擋")
    sb = Sandbox(tree, base, "p3")
    repo = sb.project("repo")
    git(repo, "init", "-q")
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8", newline="\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    main = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    git(repo, "checkout", "-q", "-b", "feat")
    (repo / "src" / "a.py").write_text("def a():\n    return 'feat'\n", encoding="utf-8", newline="\n")
    git(repo, "commit", "-qam", "feat")
    git(repo, "checkout", "-q", main)
    (repo / "src" / "a.py").write_text("def a():\n    return 'main'\n", encoding="utf-8", newline="\n")
    git(repo, "commit", "-qam", "main side")
    git(repo, "checkout", "-q", "feat")
    git(repo, "merge", main, check=False)
    s = Session(sb, repo)
    s.session_start()
    s.prompt("merge main 解衝突")
    s.read(repo / "src" / "a.py")                                                              # 無表專案：改前先讀同目錄一個檔
    st = s.bash("git checkout --theirs -- src/a.py", run=True)
    c.add("checkout --theirs 的 PreToolUse", s.last_pre["result"], "pass")
    st = s.stop(TEXT_DONE)
    c.add("取 main 版後 Stop", _d(st), "pass", note=reason_of(st)[:100] if st["result"] != "pass" else "")
    s.write(repo / "src" / "a.py", "def a():\n    return 'mine'\n")
    st = s.stop(TEXT_DONE, active=True)
    c.add("改成自己的內容後 Stop", _d(st), "block(d)")
    return c, [s]


def p4(tree, base):
    c = Checks("P4", "python -c 唯讀放行；寫檔的 python -c 與 node -e 擋，node 的擋訊息指路（INLINE_PY_READONLY）")
    sb = Sandbox(tree, base, "p4")
    proj = sb.project("proj", SIMPLE_MAP)
    s = Session(sb, proj)
    s.session_start()
    s.prompt("查 state")
    s.bash("python -X utf8 -c \"import json;print(json.dumps({'a': 1}))\"", "{\"a\": 1}\n")
    c.add("python -c 只讀的 PreToolUse", s.last_pre["result"], "pass")
    s.bash("python -c \"open('src/a.py','w').write('x')\"")
    c.add("python -c 寫檔的 PreToolUse", s.last_pre["result"], "deny")
    s.bash("node -e \"console.log(1)\"")
    r = reason_of(s.last_pre)
    c.add("node -e 的 PreToolUse", s.last_pre["result"], "deny")
    c.add("node -e 擋訊息指路（腳本檔）", "yes" if "腳本檔" in r and "node -e" in r else "no", "yes")
    return c, [s]


def p5(tree, base):
    c = Checks("P5", "專案 session 對根層 repo：唯讀 git 放行；會寫的擋且留 guard-crossrealm.jsonl（GIT_READONLY_SUBCMD）")
    sb = Sandbox(tree, base, "p5")
    root = sb.home / ".claude"
    (root / "hooks").mkdir(parents=True, exist_ok=True)
    (root / "hooks" / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "root")
    proj = sb.project("proj")
    s = Session(sb, proj)
    s.session_start()
    s.prompt("比對根層檔案")
    hc = "~/.claude"                                                                              # 根層路徑的辨識認 ~／$HOME／C:/Users/<名>，沙箱家目錄只能用 ~
    s.bash(f"git -C {hc} hash-object {hc}/hooks/x.py", "abc\n")
    c.add("git hash-object <live 檔> 的 PreToolUse", s.last_pre["result"], "pass", note=reason_of(s.last_pre)[:80])
    s.bash(f"git -C {hc} show HEAD:hooks/x.py > {str(sb.systmp).replace(chr(92), '/')}/x.py", "")
    c.add("git show 重導到 scratchpad 的 PreToolUse", s.last_pre["result"], "pass", note=reason_of(s.last_pre)[:80])
    s.bash(f"git -C {hc} hash-object -w {hc}/hooks/x.py")
    c.add("git hash-object -w 的 PreToolUse", s.last_pre["result"], "deny")
    s.bash(f"git -C {hc} show HEAD:hooks/x.py > {hc}/hooks/y.py")
    c.add("git show 重導到 live 的 PreToolUse", s.last_pre["result"], "deny")
    log = sb.logs / "guard-crossrealm.jsonl"
    n = len(log.read_text(encoding="utf-8").splitlines()) if log.is_file() else 0
    c.add("擋下的次數有留 guard-crossrealm.jsonl", str(n), "2")
    return c, [s]


def p6(tree, base):
    c = Checks("P6", "擋滿訊息列出全部命中條目（BLOCK_BUDGET_PER_RULE：(a) 與 (d) 各自計次）")
    sb = Sandbox(tree, base, "p6")
    proj = sb.project("proj")
    s = Session(sb, proj)
    s.session_start()
    s.prompt("修 src/a.py")
    s.write(proj / "src" / "a.py", "def f(x):\n    return x - 1\n")
    for i in range(1, 3):
        st = s.stop(TEXT_FIXED, active=i > 1)
        r = reason_of(st)
        c.add(f"第 {i} 次 Stop 命中 (a) 與 (d)", "yes" if "CLAIM_FIXED_NEEDS_PASS" in r and "OWED_AFTER_LAST_CASE" in r else _d(st), "yes")
    st = s.stop(TEXT_FIXED, active=True)
    r = reason_of(st)
    head = r.split("原擋訊息")[0]
    c.add("第 3 次擋滿要問使用者", "yes" if "【收尾放行確認】" in r else _d(st), "yes")
    c.add("擋滿摘要列全部條目", "yes" if "(a) CLAIM_FIXED_NEEDS_PASS" in head and "(d) OWED_AFTER_LAST_CASE" in head else "no", "yes",
          note=head[:160])
    return c, [s]


def p7(tree, base):
    c = Checks("P7", "暫存目錄 repo 的 git commit 免口令（TEMP_REPO_COMMIT_EXEMPT）；專案 repo 照擋")
    sb = Sandbox(tree, base, "p7")
    proj = sb.project("proj")
    tmp_repo = sb.systmp / "exp"
    tmp_repo.mkdir(parents=True, exist_ok=True)
    git(tmp_repo, "init", "-q")
    s = Session(sb, proj)
    s.session_start()
    s.prompt("做反證實驗")
    tr = str(tmp_repo).replace("\\", "/")
    s.bash(f"git -C {tr} add -A && git -C {tr} commit -m x")
    c.add("暫存 repo commit 的 PreToolUse（無口令）", s.last_pre["result"], "pass")
    git(proj, "init", "-q")
    pr = str(proj).replace("\\", "/")
    s.bash(f"git -C {pr} add -A && git -C {pr} commit -m x")
    c.add("專案 repo commit 的 PreToolUse（無口令）", s.last_pre["result"], "deny")
    return c, [s]


def p8(tree, base):
    c = Checks("P8", "暫存目錄副本含部位表：Edit 副本不注入不擋（TEMP_COPY_NOT_PROJECT）；本體照要求")
    sb = Sandbox(tree, base, "p8")
    proj = sb.project("proj", SIMPLE_MAP)
    copy = sb.systmp / "archive" / "proj"
    shutil.copytree(proj, copy)
    s = Session(sb, proj)
    s.session_start()
    s.prompt("比對 archive 副本")
    st = s.write_gated(copy / "src" / "a.py", "x = 1\n")
    c.add("寫暫存副本裡的部位檔", s.last_pre["result"], "pass")
    st = s.write_gated(proj / "src" / "a.py", "x = 1\n")
    c.add("寫本體的部位檔（沒讀過、沒三行）", s.last_pre["result"], "deny")
    return c, [s]


def p9(tree, base):
    c = Checks("P9", "刪執行期資料目錄免綜觀（RUNTIME_DATA_NO_OVERVIEW）；改程式檔照要求先讀同目錄")
    sb = Sandbox(tree, base, "p9")
    proj = sb.project("proj")
    git(proj, "init", "-q")
    (proj / ".gitignore").write_text("state/\n", encoding="utf-8")
    (proj / "workflow" / "need-goal").mkdir(parents=True)
    (proj / "state").mkdir()
    (proj / "hooks").mkdir()
    (proj / "hooks" / "x.py").write_text("x = 1\n", encoding="utf-8")
    s = Session(sb, proj)
    s.session_start()
    s.prompt("清掉測試漏寫的執行期目錄")
    s.bash("rm -rf workflow/need-goal/")
    c.add("rm -rf workflow/need-goal/ 的 PreToolUse", s.last_pre["result"], "pass")
    s.bash("rm -rf state/")
    c.add("rm -rf state/（gitignored）的 PreToolUse", s.last_pre["result"], "pass")
    s.bash("echo y > hooks/x.py")
    c.add("改 hooks/x.py 的 PreToolUse（沒讀過同目錄）", s.last_pre["result"], "deny")
    return c, [s]


SCENARIOS = {"P1": p1, "P2": p2, "P3": p3, "P4": p4, "P5": p5, "P6": p6, "P7": p7, "P8": p8, "P9": p9}


def main() -> int:
    ap = argparse.ArgumentParser(description="放行／欠帳判定規則的真 hook 入口情境探針")
    ap.add_argument("--tree", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    want = [x.strip().upper() for x in a.only.split(",") if x.strip()] or list(SCENARIOS)
    tree = Path(a.tree).resolve()
    # run 目錄放受測樹旁邊、不放系統暫存：hook 把暫存目錄下的改檔當暫存（_is_ephemeral_path／TEMP_COPY_NOT_PROJECT），
    # 情境裡的「專案」要是正式路徑才驗得到閘
    runs = tree.parent / f"{tree.name}-probe-runs"
    runs.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix=("keep-" if a.keep else "run-") + time.strftime("%H%M%S-"), dir=str(runs)))
    head = git(tree, "log", "--oneline", "-1", check=False).stdout.strip()
    print(f"受測樹 {tree}｜HEAD {head}｜run 目錄 {base}")
    dump, total, bad = [], 0, 0
    for key in want:
        try:
            checks, sessions = SCENARIOS[key](tree, base)
        except Exception as e:  # noqa: BLE001
            print(f"\n== 情境 {key}：建構失敗 {type(e).__name__}: {e}")
            total += 1
            bad += 1
            continue
        print(f"\n== 情境 {checks.sid}：{checks.title}")
        for r in checks.rows:
            total += 1
            bad += not r["ok"]
            note = f"｜{r['note']}" if r["note"] else ""
            print(f"  - {r['what']}：實際 {r['actual']}｜規則 {r['rule']} → {'符合' if r['ok'] else '不符'}{note}")
        for s in sessions:
            for st in s.steps:
                if st["rc"] != 0 or any("Error in" in ln or "Traceback" in ln for ln in st["stderr_tail"]):
                    print(f"    ! hook 異常 {st['label']} rc={st['rc']} stderr={st['stderr_tail'][-2:]}")
        dump.append({"scenario": checks.sid, "title": checks.title, "checks": checks.rows,
                     "sessions": [{"sid": s.sid, "cwd": str(s.cwd), "steps": s.steps} for s in sessions]})
    if a.json:
        Path(a.json).write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
    if not a.keep:
        shutil.rmtree(base, ignore_errors=True)
    print(f"\nRELEASE_RULES_PROBE DONE scenarios={len(want)} checks={total} failed={bad}")
    print("RELEASE_RULES_PROBE_CHECK PASS" if bad == 0 else "RELEASE_RULES_PROBE_CHECK FAIL")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
