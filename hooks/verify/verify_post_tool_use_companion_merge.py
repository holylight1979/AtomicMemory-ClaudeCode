"""verify_post_tool_use_companion_merge.py — PostToolUse 兩支 standalone hook 併入 guardian 的等價回放。

GOLDEN 來源：合併前的 hooks/version_guard.py 與 hooks/acceptance_spec.py（各自獨立程序、stdin 餵 JSON）
對同一事件矩陣實跑所得 stdout／stderr／rc／sidecar 原文，逐 byte 保存。守四件事：
1. 新 standalone 入口（main()，子程序）輸出與 GOLDEN 逐 byte 相同 → 回滾路徑（settings.json 加回兩行）等價
2. guardian 併入路徑（handlers.post_tool_use._run_companion_hooks，同程序）訊息與 sidecar 與 GOLDEN 相同
3. 隔離：任一支拋例外只進 debug log、另一支照常；輸出封裝 systemMessage／stderr 與 additionalContext 各就其位
4. settings.json：PostToolUse 不再起兩支獨立程序；guardian matcher 涵蓋原兩支 matcher 聯集
事件覆蓋：Edit／Write／MultiEdit／NotebookEdit／ExitPlanMode、第三個修改檔、已有驗收規格檔、計畫遭拒、
各開關關閉（enabled／mode off／min_matches）、whitelist 路徑與 token、排除路徑不計數、缺 session_id。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import acceptance_spec  # noqa: E402
import version_guard  # noqa: E402
import handlers.post_tool_use as ptu  # noqa: E402
from wg_core import load_config  # noqa: E402


# ─── 事件矩陣（與 GOLDEN 擷取時完全相同的輸入）───────────────────────────────

CLAUDE_HOOK_PATH = str(Path.home() / ".claude" / "hooks" / "wg_parallel.py")
CLAUDE_TECH_PATH = str(Path.home() / ".claude" / "TECH.md")
SID = "equiv-sess-0001"
VG_ON = {"enabled": True, "mode": "warn", "min_matches": 1}
ASP_ON = {"enabled": True, "min_files_trigger": 3,
          "count_exclude_substrings": ["/memory/", "/_staging/", "/workflow/"]}


def ev(tool, tool_input=None, tool_response="", sid=SID, cwd="D:/proj"):
    return {"session_id": sid, "cwd": cwd, "hook_event_name": "PostToolUse",
            "tool_name": tool, "tool_input": tool_input or {}, "tool_response": tool_response}


SPEC_PATH_BACKSLASH = "D:" + "\\" + "proj" + "\\" + ".claude" + "\\" + "verify" + "\\" + "acceptance-my-task.md"

# name → dict(vg=cfg, asp=cfg, state=[paths], sidecar=dict|None, events=[...])
SCENARIOS = {
    "edit_remnant_in_claude": dict(
        vg=VG_ON, asp=ASP_ON, state=["D:/proj/a.py"], sidecar=None,
        events=[ev("Edit", {"file_path": CLAUDE_HOOK_PATH, "old_string": "x", "new_string": "V5 P3 里程碑遺留"})]),
    "write_clean_small_task": dict(
        vg=VG_ON, asp=ASP_ON, state=["D:/proj/a.py", "D:/proj/b.py"], sidecar=None,
        events=[ev("Write", {"file_path": CLAUDE_HOOK_PATH, "content": "def f():\n    return 1\n"})]),
    "multiedit_two_remnants": dict(
        vg=VG_ON, asp=ASP_ON, state=["D:/proj/a.py", "D:/proj/b.py", "D:/proj/c.py"], sidecar=None,
        events=[ev("MultiEdit", {"file_path": CLAUDE_HOOK_PATH,
                                 "edits": [{"old_string": "a", "new_string": "Sprint 4 完成"},
                                           {"old_string": "b", "new_string": "採方案甲 / [F12]"}]})]),
    "notebookedit_third_file": dict(
        vg=VG_ON, asp=ASP_ON, state=["D:/proj/a.py", "D:/proj/b.py", "D:/proj/n.ipynb"], sidecar=None,
        events=[ev("NotebookEdit", {"notebook_path": "D:/proj/n.ipynb", "new_source": "Wave 2"})]),
    "edit_third_file_outside_claude": dict(
        vg=VG_ON, asp=ASP_ON, state=["D:/proj/a.py", "D:/proj/b.py", "D:/proj/c.py"], sidecar=None,
        events=[ev("Edit", {"file_path": "D:/proj/c.py", "old_string": "x", "new_string": "Sprint 9"}),
                ev("Edit", {"file_path": "D:/proj/c.py", "old_string": "x", "new_string": "y"})]),
    "exitplan_approved_then_repeat": dict(
        vg=VG_ON, asp=ASP_ON, state=[], sidecar=None,
        events=[ev("ExitPlanMode", {}, "approved"), ev("ExitPlanMode", {}, "approved")]),
    "exitplan_rejected": dict(
        vg=VG_ON, asp=ASP_ON, state=[], sidecar=None,
        events=[ev("ExitPlanMode", {}, {"result": "User rejected the plan"})]),
    "plan_prompted_suppresses_multifile": dict(
        vg=VG_ON, asp=ASP_ON, state=["D:/proj/a.py", "D:/proj/b.py", "D:/proj/c.py"], sidecar={"plan_prompted": True},
        events=[ev("Edit", {"file_path": "D:/proj/c.py", "old_string": "x", "new_string": "y"})]),
    "spec_file_written_then_third_file": dict(
        vg=VG_ON, asp=ASP_ON, state=["D:/proj/a.py", "D:/proj/b.py", "D:/proj/c.py"], sidecar=None,
        events=[ev("Write", {"file_path": SPEC_PATH_BACKSLASH, "content": "---\nstatus: open\n---\n"}),
                ev("Edit", {"file_path": "D:/proj/c.py", "old_string": "x", "new_string": "y"})]),
    "vg_disabled": dict(
        vg={"enabled": False, "mode": "warn", "min_matches": 1}, asp=ASP_ON, state=[], sidecar=None,
        events=[ev("Edit", {"file_path": CLAUDE_HOOK_PATH, "old_string": "x", "new_string": "V5 P3"})]),
    "vg_mode_off": dict(
        vg={"enabled": True, "mode": "off", "min_matches": 1}, asp=ASP_ON, state=[], sidecar=None,
        events=[ev("Edit", {"file_path": CLAUDE_HOOK_PATH, "old_string": "x", "new_string": "V5 P3"})]),
    "vg_min_matches_2_one_hit": dict(
        vg={"enabled": True, "mode": "warn", "min_matches": 2}, asp=ASP_ON, state=[], sidecar=None,
        events=[ev("Edit", {"file_path": CLAUDE_HOOK_PATH, "old_string": "x", "new_string": "V5 P3"})]),
    "vg_whitelisted_path_and_token": dict(
        vg=VG_ON, asp=ASP_ON, state=[], sidecar=None,
        events=[ev("Edit", {"file_path": CLAUDE_TECH_PATH, "old_string": "x", "new_string": "V5 P3"}),
                ev("Edit", {"file_path": CLAUDE_HOOK_PATH, "old_string": "x", "new_string": "SCHEMA_VERSION = 3  # Sprint 2"})]),
    "asp_disabled_exitplan": dict(
        vg=VG_ON, asp={"enabled": False, "min_files_trigger": 3, "count_exclude_substrings": []}, state=[], sidecar=None,
        events=[ev("ExitPlanMode", {}, "approved")]),
    "asp_missing_session_id": dict(
        vg=VG_ON, asp=ASP_ON, state=[], sidecar=None,
        events=[ev("ExitPlanMode", {}, "approved", sid="")]),
    "asp_excluded_paths_not_counted": dict(
        vg=VG_ON, asp=ASP_ON, state=["D:/proj/a.py", "D:/proj/memory/x.md", "D:/proj/_staging/y.md", "D:/proj/b.py"], sidecar=None,
        events=[ev("Edit", {"file_path": "D:/proj/b.py", "old_string": "x", "new_string": "y"})]),
}


# ─── 合併前實跑所得（逐 byte）────────────────────────────────────────────────

GOLDEN = {'edit_remnant_in_claude': [{'vg': {'stdout': '{"systemMessage": "[版本守衛] `wg_parallel.py` 疑含版本操作脈絡殘留：V5 P3。live '
                                              '檔/atom 只寫 timeless 現況——版本演進歸 _CHANGELOG，非埋進碼。（規則 '
                                              'rules/core.md「版本與文件治理」；誤判可調 config.version_guard）"}\r\n',
                                    'stderr': '[版本守衛] `wg_parallel.py` 疑含版本操作脈絡殘留：V5 P3。live 檔/atom 只寫 timeless '
                                              '現況——版本演進歸 _CHANGELOG，非埋進碼。（規則 rules/core.md「版本與文件治理」；誤判可調 '
                                              'config.version_guard）\r\n',
                                    'rc': 0},
                             'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                             'sidecar': None}],
 'write_clean_small_task': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                             'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                             'sidecar': None}],
 'multiedit_two_remnants': [{'vg': {'stdout': '{"systemMessage": "[版本守衛] `wg_parallel.py` 疑含版本操作脈絡殘留：Sprint 4, 方案甲, '
                                              '[F12]。live 檔/atom 只寫 timeless 現況——版本演進歸 _CHANGELOG，非埋進碼。（規則 '
                                              'rules/core.md「版本與文件治理」；誤判可調 config.version_guard）"}\r\n',
                                    'stderr': '[版本守衛] `wg_parallel.py` 疑含版本操作脈絡殘留：Sprint 4, 方案甲, [F12]。live 檔/atom '
                                              '只寫 timeless 現況——版本演進歸 _CHANGELOG，非埋進碼。（規則 rules/core.md「版本與文件治理」；誤判可調 '
                                              'config.version_guard）\r\n',
                                    'rc': 0},
                             'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                             'sidecar': None}],
 'notebookedit_third_file': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                              'asp': {'stdout': '{"hookSpecificOutput": {"hookEventName": "PostToolUse", '
                                                '"additionalContext": "[Guardian:AcceptanceSpec] 本任務已修改 3 '
                                                '個檔案且尚無驗收規格檔 → 建議現在補一份（事後補仍有價值：收尾逐項自核 + 跨 session '
                                                '接手時「做完的定義」不蒸發）。\\n路徑：`<專案根>/.claude/verify/acceptance-<task-slug>.md`（專案根以 '
                                                'git root 為準；目前 '
                                                'cwd：D:/proj）\\n格式（極簡三段，勿加章節）：\\n```\\n---\\ntask_slug: <任務主題 '
                                                'kebab-case>\\nsession_id: equiv-sess-0001\\ncreated_at: <今日 '
                                                'YYYY-MM-DD>\\nsource: multifile\\nstatus: open\\n---\\n## 必須發生\\n- '
                                                '<需求的每一項，逐條可核對>\\n## 禁止發生\\n- <紅線，例：不動某檔 / 不翻案已定決策>\\n## 驗證指令\\n- '
                                                '<可直接執行的指令或檢查步驟>\\n```\\n收尾時逐項自核：全過 → status 改 done 並移入同目錄 done/ '
                                                '子資料夾；未全過 → 收尾報告誠實列出未過項。\\n本提醒每 session '
                                                '僅此一次；若當前任務性質不需驗收清單（如批量機械修改），可忽略。"}}\r\n',
                                      'stderr': '',
                                      'rc': 0},
                              'sidecar': '{"multifile_advised": true}'}],
 'edit_third_file_outside_claude': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                                     'asp': {'stdout': '{"hookSpecificOutput": {"hookEventName": "PostToolUse", '
                                                       '"additionalContext": "[Guardian:AcceptanceSpec] 本任務已修改 3 '
                                                       '個檔案且尚無驗收規格檔 → 建議現在補一份（事後補仍有價值：收尾逐項自核 + 跨 session '
                                                       '接手時「做完的定義」不蒸發）。\\n路徑：`<專案根>/.claude/verify/acceptance-<task-slug>.md`（專案根以 '
                                                       'git root 為準；目前 '
                                                       'cwd：D:/proj）\\n格式（極簡三段，勿加章節）：\\n```\\n---\\ntask_slug: <任務主題 '
                                                       'kebab-case>\\nsession_id: equiv-sess-0001\\ncreated_at: <今日 '
                                                       'YYYY-MM-DD>\\nsource: multifile\\nstatus: open\\n---\\n## '
                                                       '必須發生\\n- <需求的每一項，逐條可核對>\\n## 禁止發生\\n- <紅線，例：不動某檔 / '
                                                       '不翻案已定決策>\\n## 驗證指令\\n- <可直接執行的指令或檢查步驟>\\n```\\n收尾時逐項自核：全過 → '
                                                       'status 改 done 並移入同目錄 done/ 子資料夾；未全過 → 收尾報告誠實列出未過項。\\n本提醒每 '
                                                       'session 僅此一次；若當前任務性質不需驗收清單（如批量機械修改），可忽略。"}}\r\n',
                                             'stderr': '',
                                             'rc': 0},
                                     'sidecar': '{"multifile_advised": true}'},
                                    {'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                                     'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                                     'sidecar': '{"multifile_advised": true}'}],
 'exitplan_approved_then_repeat': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                                    'asp': {'stdout': '{"hookSpecificOutput": {"hookEventName": "PostToolUse", '
                                                      '"additionalContext": "[Guardian:AcceptanceSpec] 本任務經 '
                                                      'plan-mode 確認 → 屬分級線以上。動工前先把「做完的定義」落成驗收規格檔（跨 session '
                                                      '不蒸發、收尾自核依據）：\\n路徑：`<專案根>/.claude/verify/acceptance-<task-slug>.md`（專案根以 '
                                                      'git root 為準；目前 cwd：D:/proj）\\n內容從剛獲同意的 plan 逐項轉出，不重問 '
                                                      'user、不加互動輪。\\n格式（極簡三段，勿加章節）：\\n```\\n---\\ntask_slug: <任務主題 '
                                                      'kebab-case>\\nsession_id: equiv-sess-0001\\ncreated_at: <今日 '
                                                      'YYYY-MM-DD>\\nsource: plan\\nstatus: open\\n---\\n## 必須發生\\n- '
                                                      '<需求的每一項，逐條可核對>\\n## 禁止發生\\n- <紅線，例：不動某檔 / 不翻案已定決策>\\n## '
                                                      '驗證指令\\n- <可直接執行的指令或檢查步驟>\\n```\\n收尾時逐項自核：全過 → status 改 done '
                                                      '並移入同目錄 done/ 子資料夾；未全過 → 收尾報告誠實列出未過項。\\n例外：純研究/問答型 plan（不產生 '
                                                      'repo 修改）可不落檔，說明一句即可。"}}\r\n',
                                            'stderr': '',
                                            'rc': 0},
                                    'sidecar': '{"plan_prompted": true}'},
                                   {'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                                    'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                                    'sidecar': '{"plan_prompted": true}'}],
 'exitplan_rejected': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                        'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                        'sidecar': None}],
 'plan_prompted_suppresses_multifile': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                                         'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                                         'sidecar': '{"plan_prompted": true}'}],
 'spec_file_written_then_third_file': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                                        'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                                        'sidecar': '{"spec_paths": '
                                                   '["D:/proj/.claude/verify/acceptance-my-task.md"]}'},
                                       {'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                                        'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                                        'sidecar': '{"spec_paths": '
                                                   '["D:/proj/.claude/verify/acceptance-my-task.md"]}'}],
 'vg_disabled': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                  'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                  'sidecar': None}],
 'vg_mode_off': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                  'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                  'sidecar': None}],
 'vg_min_matches_2_one_hit': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                               'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                               'sidecar': None}],
 'vg_whitelisted_path_and_token': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                                    'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                                    'sidecar': None},
                                   {'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                                    'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                                    'sidecar': None}],
 'asp_disabled_exitplan': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                            'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                            'sidecar': None}],
 'asp_missing_session_id': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                             'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                             'sidecar': None}],
 'asp_excluded_paths_not_counted': [{'vg': {'stdout': '', 'stderr': '', 'rc': 0},
                                     'asp': {'stdout': '', 'stderr': '', 'rc': 0},
                                     'sidecar': None}]}


# ─── standalone 子程序 bootstrap：只換 config 與 sidecar／state 目錄，其餘走真 main() ──

BOOT = (
    "import json,sys,importlib;from pathlib import Path;"
    "sys.path.insert(0, {moddir!r});m=importlib.import_module({mod!r});"
    "cfg=json.loads({cfg!r});m._load_config=lambda: cfg;"
    "wf=Path({wf!r});"
    "setattr(m,'WORKFLOW_DIR',wf) if hasattr(m,'WORKFLOW_DIR') else None;"
    "setattr(m,'SIDECAR_DIR',wf/'acceptance-spec') if hasattr(m,'SIDECAR_DIR') else None;"
    "m.main()"
)


def prepare_sandbox(wf: Path, sc: dict, sid: str = SID) -> None:
    wf.mkdir(parents=True, exist_ok=True)
    state = {"modified_files": [{"path": p, "session_id": sid, "tool": "Edit"} for p in sc["state"]]}
    (wf / f"state-{sid}.json").write_text(json.dumps(state), encoding="utf-8")
    if sc["sidecar"] is not None:
        (wf / "acceptance-spec").mkdir(parents=True, exist_ok=True)
        (wf / "acceptance-spec" / f"{sid}.json").write_text(
            json.dumps(sc["sidecar"], ensure_ascii=False), encoding="utf-8", newline="\n")


def read_sidecar_text(wf: Path, sid: str = SID):
    p = wf / "acceptance-spec" / f"{sid}.json"
    return p.read_bytes().decode("utf-8") if p.exists() else None


def run_standalone(mod: str, cfg: dict, wf: Path, event: dict) -> dict:
    code = BOOT.format(moddir=str(HOOKS_DIR), mod=mod, cfg=json.dumps(cfg), wf=str(wf))
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", code],
                       input=json.dumps(event).encode("utf-8"), capture_output=True, timeout=60)
    return {"stdout": p.stdout.decode("utf-8"), "stderr": p.stderr.decode("utf-8"), "rc": p.returncode}


def _golden_sys_msgs(row: dict) -> list:
    out = row["vg"]["stdout"]
    return [json.loads(out)["systemMessage"]] if out.strip() else []


def _golden_ctx_msgs(row: dict) -> list:
    out = row["asp"]["stdout"]
    return [json.loads(out)["hookSpecificOutput"]["additionalContext"]] if out.strip() else []


# ─── 1. 新 standalone 入口 == 合併前 golden（逐 byte）────────────────────────


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_standalone_entry_bytes_equal_pre_merge_golden(name, tmp_path):
    sc = SCENARIOS[name]
    wf = tmp_path / "workflow"
    prepare_sandbox(wf, sc)
    for i, event in enumerate(sc["events"]):
        got_vg = run_standalone("version_guard", sc["vg"], wf, event)
        got_asp = run_standalone("acceptance_spec", sc["asp"], wf, event)
        exp = GOLDEN[name][i]
        assert got_vg == exp["vg"], f"{name}[{i}] version_guard standalone 輸出與合併前不同"
        assert got_asp == exp["asp"], f"{name}[{i}] acceptance_spec standalone 輸出與合併前不同"
        assert read_sidecar_text(wf) == exp["sidecar"], f"{name}[{i}] sidecar 內容與合併前不同"


# ─── 2. guardian 併入路徑 == 合併前 golden ───────────────────────────────────


@pytest.fixture()
def asp_sandbox(tmp_path, monkeypatch):
    wf = tmp_path / "workflow"
    monkeypatch.setattr(acceptance_spec, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(acceptance_spec, "SIDECAR_DIR", wf / "acceptance-spec")
    return wf


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_merged_guardian_path_equals_pre_merge_golden(name, asp_sandbox, capsys):
    sc = SCENARIOS[name]
    prepare_sandbox(asp_sandbox, sc)
    config = {"version_guard": sc["vg"], "acceptance_spec": sc["asp"]}
    for i, event in enumerate(sc["events"]):
        sys_msgs, ctx_msgs = ptu._run_companion_hooks(event, config)
        exp = GOLDEN[name][i]
        assert sys_msgs == _golden_sys_msgs(exp), f"{name}[{i}] version_guard 訊息與合併前不同"
        assert ctx_msgs == _golden_ctx_msgs(exp), f"{name}[{i}] acceptance_spec 訊息與合併前不同"
        assert read_sidecar_text(asp_sandbox) == exp["sidecar"], f"{name}[{i}] sidecar 內容與合併前不同"
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "", "_run_companion_hooks 本身不得 print（輸出交 _emit）"


def test_guardian_config_sections_equal_standalone_loaders():
    """guardian 傳給 run() 的區塊（load_config 含 DEFAULTS 合併）必須與兩支自己的 _load_config 相同。"""
    cfg = load_config()
    assert cfg.get("version_guard", {}) == version_guard._load_config()
    assert cfg.get("acceptance_spec", {}) == acceptance_spec._load_config()


# ─── 3. 隔離與輸出封裝 ──────────────────────────────────────────────────────


def _boom(*_a, **_k):
    raise RuntimeError("boom")


def test_version_guard_exception_isolated(asp_sandbox, monkeypatch):
    logged = []
    monkeypatch.setattr(version_guard, "run", _boom)
    monkeypatch.setattr(ptu, "_atom_debug_error", lambda src, e: logged.append(src))
    sc = SCENARIOS["exitplan_approved_then_repeat"]
    prepare_sandbox(asp_sandbox, sc)
    sys_msgs, ctx_msgs = ptu._run_companion_hooks(
        sc["events"][0], {"version_guard": sc["vg"], "acceptance_spec": sc["asp"]})
    assert sys_msgs == []
    assert ctx_msgs == _golden_ctx_msgs(GOLDEN["exitplan_approved_then_repeat"][0])
    assert logged == ["post_tool_use:version_guard"]


def test_acceptance_spec_exception_isolated(asp_sandbox, monkeypatch):
    logged = []
    monkeypatch.setattr(acceptance_spec, "run", _boom)
    monkeypatch.setattr(ptu, "_atom_debug_error", lambda src, e: logged.append(src))
    sc = SCENARIOS["edit_remnant_in_claude"]
    prepare_sandbox(asp_sandbox, sc)
    sys_msgs, ctx_msgs = ptu._run_companion_hooks(
        sc["events"][0], {"version_guard": sc["vg"], "acceptance_spec": sc["asp"]})
    assert sys_msgs == _golden_sys_msgs(GOLDEN["edit_remnant_in_claude"][0])
    assert ctx_msgs == []
    assert logged == ["post_tool_use:acceptance_spec"]


def test_emit_places_system_message_and_additional_context(capsys):
    with pytest.raises(SystemExit) as ei:
        ptu._emit_post_tool_output(["[Guardian:X] ctx-1", "[Guardian:AcceptanceSpec] ctx-2"], ["[版本守衛] sys-1"])
    assert ei.value.code == 0
    cap = capsys.readouterr()
    out = json.loads(cap.out)
    assert out["systemMessage"] == "[版本守衛] sys-1"
    assert out["hookSpecificOutput"] == {"hookEventName": "PostToolUse",
                                         "additionalContext": "[Guardian:X] ctx-1\n[Guardian:AcceptanceSpec] ctx-2"}
    assert cap.err == "[版本守衛] sys-1\n"


def test_emit_nothing_when_silent(capsys):
    with pytest.raises(SystemExit) as ei:
        ptu._emit_post_tool_output([], [])
    assert ei.value.code == 0
    cap = capsys.readouterr()
    assert cap.out == "" and cap.err == ""


def test_emit_context_only_has_no_system_message(capsys):
    with pytest.raises(SystemExit):
        ptu._emit_post_tool_output(["ctx"], [])
    out = json.loads(capsys.readouterr().out)
    assert "systemMessage" not in out and out["hookSpecificOutput"]["additionalContext"] == "ctx"


# ─── 4. settings.json：兩支獨立程序已拿掉、matcher 取聯集 ─────────────────────


def test_settings_post_tool_use_merged_into_guardian():
    settings = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))
    entries = settings["hooks"]["PostToolUse"]
    all_cmds = " ".join(h.get("command", "") for e in entries for h in e.get("hooks", []))
    assert "version_guard.py" not in all_cmds, "version_guard 仍以獨立程序掛在 PostToolUse"
    assert "acceptance_spec.py" not in all_cmds, "acceptance_spec 仍以獨立程序掛在 PostToolUse"
    guardian = [e for e in entries
                if any("workflow-guardian.py" in h.get("command", "") for h in e.get("hooks", []))]
    assert len(guardian) == 1
    tools = set(guardian[0]["matcher"].split("|"))
    # 原兩支 matcher：Write|Edit|MultiEdit 與 Write|Edit|NotebookEdit|ExitPlanMode
    assert {"Write", "Edit", "MultiEdit", "NotebookEdit", "ExitPlanMode"} <= tools
