"""verify_pull_dev_residue.py — 只對原設計者本機或開發期才有意義的東西，同事的 CC 不再碰到。

用真的 workflow/config.json（本 worktree 那份）判，退回舊碼或舊設定會紅：
1. 驗收裁判歸 v6 開關：關 → 收尾宣稱完成也不叫裁判；開 → 只走背景審（Stop 不等、不擋），沒有同步擋這條路；
   驗收規格提示同一個開關。
2. 文件漂移：別的專案改 tools/x.py 不記；改 ~/.claude 自己的 tools/x.py 照記。
3. 回訪表：host 存電腦代號（電腦名小寫後 sha256 前 12 碼），對不上的機器不跑不顯示、那台照顯示；登記表找不到電腦名原文；
   開場跑一次回訪檢查後登記表內容不變（執行期紀錄寫本機 followups.local.json）。
5. 文字評分：出廠不列 docs，改 checklist 類文件不起背景評分；工具端直接叫 --auto-kind docs 也不評。
6. codex 本機路徑與旗標不在共用設定；config.local.json 有 codex_extra_args 時，裁判與 tools/codex-call.py 都讀得到，沒有就是空。
7. 收割擋訊息的「記憶系統開發面 → realm=local」只在 ~/.claude 之下附。
8. HUD 不再從對話紀錄推名字：一律 session 前 8 碼，API 不帶 track 欄。
9. console skill 只能手動叫；console.spawn 不在共用設定。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_pull_dev_residue.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1]
ROOT = HOOKS.parent
for p in (HOOKS, ROOT / "lib", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import codex_companion as cc  # noqa: E402
import acceptance_spec as asp  # noqa: E402
import wg_core  # noqa: E402
import wg_docdrift  # noqa: E402
import wg_harvest  # noqa: E402
from verify_text_score_stop import spawned, world, wts  # noqa: E402,F401  文字評分沿用那支的資料根與 Popen 替身

CONFIG = json.loads((ROOT / "workflow" / "config.json").read_text(encoding="utf-8"))
NODE = shutil.which("node")
SID = "residue-0000-1111"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ─── 1. 驗收裁判與驗收規格歸 v6 開關 ──────────────────────────────────────────

def _stop_calls(monkeypatch, v6: str) -> list:
    """跑 codex_companion.handle_stop：本回合有 Edit、最後一句宣稱完成；記下驗收裁判被叫了哪一條路。"""
    import state as companion_state
    monkeypatch.setenv("WG_V6", v6)
    calls: list = []
    monkeypatch.setattr(cc, "_maybe_spawn_acceptance_review", lambda *a, **k: calls.append("record"))
    monkeypatch.setattr(companion_state, "read_state", lambda sid: {"tool_trace": [{"tool": "Edit"}], "turn_index": 1})
    monkeypatch.setattr(companion_state, "update_last_assistant_tail", lambda *a: None)
    monkeypatch.setattr(companion_state, "increment_turn", lambda *a: None)
    cfg = {**CONFIG["codex_companion"], "soft_gate": {"completion_evidence": False}, "score_threshold": 99}
    with pytest.raises(SystemExit):
        cc.handle_stop({"session_id": SID, "last_assistant_message": "全部做完，已完成。"}, cfg)
    return calls


def test_acceptance_review_not_triggered_when_v6_off(monkeypatch):
    assert _stop_calls(monkeypatch, "0") == []          # 舊碼：不看 v6，照叫裁判


def test_acceptance_review_records_only_when_v6_on(monkeypatch):
    assert "enforce" not in CONFIG["codex_companion"]["acceptance_review"]   # 同步擋的設定鍵已拔
    assert not hasattr(cc, "_enforce_acceptance_gate")                       # 同步擋的程式路徑已拔
    assert _stop_calls(monkeypatch, "1") == ["record"]   # 只剩背景審這一條


def test_spec_done_trigger_follows_v6(monkeypatch):
    monkeypatch.setenv("WG_V6", "0")
    assert cc._acceptance_enabled(CONFIG["codex_companion"]) is False
    monkeypatch.setenv("WG_V6", "1")
    assert cc._acceptance_enabled(CONFIG["codex_companion"]) is True


@pytest.mark.parametrize("v6,expect", [("0", 0), ("1", 1)])
def test_acceptance_spec_advisory_follows_v6(tmp_path, monkeypatch, v6, expect):
    monkeypatch.setattr(asp, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(asp, "SIDECAR_DIR", tmp_path / "acceptance-spec")
    monkeypatch.setenv("WG_V6", v6)
    msgs = asp.run({"session_id": SID, "tool_name": "ExitPlanMode", "tool_response": "ok", "cwd": str(tmp_path)},
                   CONFIG["acceptance_spec"])
    assert len(msgs) == expect                           # 舊碼：v6 關也叫 AI 寫規格檔


# ─── 2. 文件漂移對應表只對記憶系統自己的目錄 ─────────────────────────────────

def _drift(path: Path, root: Path) -> dict:
    state = {"aidocs": {"project_root": str(root)}}
    wg_docdrift.check_source_drift(str(path), state, CONFIG)
    return state.get("docdrift_pending", {})


def test_docdrift_colleague_project_not_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", tmp_path / "home" / ".claude")
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path / "Logs")
    proj = tmp_path / "proj"
    assert _drift(proj / "tools" / "x.py", proj) == {}  # 舊設定：tools/*.py → DocIndex-System.md 照記


def test_docdrift_memory_system_itself_still_recorded(tmp_path, monkeypatch):
    home = tmp_path / "home" / ".claude"
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", home)
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", tmp_path / "Logs")
    pending = _drift(home / "tools" / "x.py", home)
    assert [v["doc"] for v in pending.values()] == ["DocIndex-System.md"]


# ─── 3. 回訪表：本機限定 ─────────────────────────────────────────────────────

@pytest.fixture
def fc(tmp_path, monkeypatch):
    mod = _load("followup_check_residue", ROOT / "tools" / "followup-check.py")
    monkeypatch.setattr(mod, "FOLLOWUPS", tmp_path / "followups.json")
    monkeypatch.setattr(mod, "CHECKS", {"fake": lambda item: {"status": "INSUFFICIENT", "turns": 0, "min_turns": 1}})
    return mod


def _due(**extra) -> dict:
    d = (date.today() - timedelta(days=1)).isoformat()
    return {"id": "x", "title": "量測回訪", "since": d, "due": d, "check": "fake", "done": False, **extra}


def _host_id(name: str) -> str:
    return hashlib.sha256(name.lower().encode("utf-8")).hexdigest()[:12]


@pytest.mark.parametrize("host,shown", [(_host_id("另一台-PC"), False), (_host_id(platform.node().upper()), True), ("", True)])
def test_followup_shown_only_on_registered_machine(fc, host, shown):
    fc.save({"followups": [_due(host=host)]})
    lines, _ = fc.run_all(brief=True, mark_shown=True)
    assert bool(lines) is shown                          # 舊碼：沒有 host 欄，別台機器也整份推
    assert fc.host_id(platform.node()) == _host_id(platform.node())   # 電腦名小寫後 sha256 前 12 碼


def test_registry_dev_measurements_are_machine_local_without_machine_name():
    raw = (ROOT / "workflow" / "followups.json").read_text(encoding="utf-8")
    hosts = {f["id"]: f.get("host") for f in json.loads(raw)["followups"]}
    me = _host_id(platform.node())
    assert hosts["closing-gates-trim-2026-10-20"] == me and hosts["injection-budget-2026-08-28"] == me
    assert platform.node().lower() not in raw.lower()   # 登記表找不到電腦名原文（舊版直接寫原名）


def test_session_start_run_leaves_registry_unchanged(fc):
    fc.save({"followups": [_due(), _due(id="y", title="會結案的那筆", check="pass")]})
    fc.CHECKS["pass"] = lambda item: {"status": "PASS", "rows": []}
    before = fc.FOLLOWUPS.read_bytes()
    lines, _ = fc.run_all(auto_close=True, brief=True, mark_shown=True)   # 開場那一次的參數
    assert lines and fc.FOLLOWUPS.read_bytes() == before                  # 舊碼：last_shown／result／done 寫回登記表
    rt = json.loads(fc.FOLLOWUPS.with_name("followups.local.json").read_text(encoding="utf-8"))
    assert rt["y"]["done"] is True and rt["x"]["result"].endswith("INSUFFICIENT")
    again, _ = fc.run_all(auto_close=True, brief=True, mark_shown=True)   # 本機紀錄生效：y 已結不再推；x 樣本不足照推
    assert len(again) == 1 and "會結案的那筆" not in again[0] and fc.FOLLOWUPS.read_bytes() == before



def test_followup_owner_mismatch_hidden(fc):
    assert fc.for_me({"owner": "someone-else"}, {"owner": "me", "host": "h"}) is False
    assert fc.for_me({"owner": "ME", "host": "H"}, {"owner": "me", "host": "h"}) is True


# ─── 5. 文字評分 docs 出廠不評 ───────────────────────────────────────────────

def test_text_score_docs_default_not_scored(world, tmp_path, spawned):  # noqa: F811
    assert "docs" not in CONFIG["text_score"]["auto_targets"]
    doc = tmp_path / "proj" / "memory" / "_staging" / "x-checklist.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("清單\n" * 200, encoding="utf-8")
    mods = [{"path": str(doc), "session_id": SID, "last_turn_seq": 2}]
    cfg = {"text_score": {**CONFIG["text_score"], "reply_scope": "all"}}
    wts.on_stop({"turn_seq": 2}, SID, "短", mods, 2, cfg)
    assert spawned == []                                 # 舊碼／舊設定：checklist 文件起背景評分


def test_text_score_tool_docs_off_by_default():
    ts = _load("text_score_residue", ROOT / "tools" / "text-score.py")
    long = "說明文字。" * 200
    for section in (CONFIG["text_score"], {}):           # 共用設定、工具預設都不評文件
        assert ts.auto_skip_reason("docs", long, section, "C:/project/README.md") == "docs 不在 text_score.auto_targets"
    assert ts.auto_skip_reason("final_reply", long, CONFIG["text_score"], None) == ""


# ─── 6. codex 本機設定搬 config.local ────────────────────────────────────────

def test_no_machine_paths_in_shared_codex_config():
    c = CONFIG["codex_companion"]
    assert "codex_binary" not in c and c["codex_extra_args"] == []
    assert "console" not in CONFIG


def _write_cfg(d: Path, local: dict | None) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps({"codex_companion": {"codex_extra_args": [], "model": "m"}}), encoding="utf-8")
    if local is not None:
        (d / "config.local.json").write_text(json.dumps(local), encoding="utf-8")
    return d / "config.json"


LOCAL = {"codex_companion": {"codex_extra_args": ["-c", "mcp_servers.x.enabled=false"]}}


@pytest.mark.parametrize("local,expect", [(LOCAL, ["-c", "mcp_servers.x.enabled=false"]), (None, [])])
def test_judge_and_codex_call_read_config_local(tmp_path, monkeypatch, local, expect):
    cfg = _write_cfg(tmp_path / "wf", local)
    call = _load("codex_call_residue", ROOT / "tools" / "codex-call.py")
    monkeypatch.setattr(call, "CONFIG_PATH", cfg)
    assert call.load_config()["codex_extra_args"] == expect
    sys.path.insert(0, str(ROOT / "tools" / "codex-companion"))
    audit = _load("audit_residue", ROOT / "tools" / "codex-companion" / "audit.py")
    monkeypatch.setattr(audit, "CONFIG_PATH", cfg)
    assert audit._load_config()["codex_extra_args"] == expect
    monkeypatch.setattr(cc, "CONFIG_PATH", cfg)
    assert cc._load_config()["codex_extra_args"] == expect


# ─── 7. 收割擋訊息 ───────────────────────────────────────────────────────────

def test_harvest_memdev_hint_only_under_claude_dir(tmp_path, monkeypatch):
    home = tmp_path / ".claude"
    monkeypatch.setattr(wg_core, "CLAUDE_DIR", home)
    assert "realm=local/MemDev" not in wg_harvest.harvest_block_message(cwd=str(tmp_path / "proj"))   # 舊碼：一律附
    assert "realm=local/MemDev" in wg_harvest.harvest_block_message(cwd=str(home))


# ─── 8. HUD 只印 session 短號 ────────────────────────────────────────────────

_API = r"""
const ae = require(process.argv[1]);
const out = [];
const res = () => ({ writeHead() {}, end(s) { out.push(JSON.parse(s)); } });
ae.apiAecReports({}, res(), null);
console.log(JSON.stringify(out));
"""
_CARD = r"""
const h = require(process.argv[1]);
const s = h.render().match(/<script>([\s\S]*?)<\/script>/)[1];
const el = () => ({ addEventListener() {}, style: {}, innerHTML: "", textContent: "", className: "", querySelectorAll: () => [] });
const document = { getElementById: el, querySelectorAll: () => [] };
const window = { confirm: () => true };
const fetch = () => new Promise(() => {});
const setInterval = () => 0;
function Worker() { throw new Error("no worker"); }
function EventSource() {}
const URL = { createObjectURL: () => "" };
function Blob() {}
const location = { origin: "http://x" };
eval(s);
console.log(JSON.stringify(JSON.parse(process.argv[2]).map((r) => tipOf(r))));
"""


@pytest.mark.skipif(not NODE, reason="node not available")
def test_hud_shows_session_short_id_not_track(tmp_path):
    sid = "aaaaaaaa-1111-2222-3333-444444444444"
    rep = tmp_path / "workflow" / "aec-report"
    rep.mkdir(parents=True)
    (rep / f"{sid}-t3.json").write_text(json.dumps({"session_id": sid, "turn_seq": 3, "severity": "routine"}),
                                        encoding="utf-8")
    tr = tmp_path / "projects" / "C--x--claude-wt-foo" / f"{sid}.jsonl"
    tr.parent.mkdir(parents=True)
    tr.write_text(json.dumps({"type": "user", "cwd": "C:\\x\\.claude-wt\\foo",
                              "message": {"content": "track-foo：你是工作軌 track-foo"}}) + "\n", encoding="utf-8")
    lib = ROOT / "tools" / "workflow-guardian-mcp" / "lib"
    env = dict(os.environ, WG_CLAUDE_DIR=str(tmp_path))
    r = subprocess.run([NODE, "-e", _API, str(lib / "anti-evasion.js")], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    listing = json.loads(r.stdout.strip().splitlines()[-1])[0]
    assert [("track" in x) for x in listing["reports"]] == [False]        # 舊碼：track=track-foo
    r = subprocess.run([NODE, "-e", _CARD, str(lib / "aec-hud-html.js"),
                        json.dumps([{"session_id": sid, "turn_seq": 3, "track": "track-foo"}])],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    tip = json.loads(r.stdout.strip().splitlines()[-1])[0]
    assert tip.startswith("session aaaaaaaa") and "track-foo" not in tip


# ─── 9. console skill ───────────────────────────────────────────────────────

def test_console_skill_manual_only_and_tools_moved():
    head = (ROOT / "skills" / "console" / "SKILL.md").read_text(encoding="utf-8").split("---")[1]
    assert "disable-model-invocation: true" in head
    assert not (ROOT / "tools" / "console-spawn.py").exists() and not (ROOT / "tools" / "console-status.py").exists()
    assert (ROOT / "skills" / "console" / "scripts" / "console-spawn.py").is_file()
    spawn = json.loads((ROOT / "skills" / "console" / "spawn.json").read_text(encoding="utf-8"))
    assert spawn["default_model"] and spawn["max_parallel"] == 5
