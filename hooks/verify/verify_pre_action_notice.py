"""verify_pre_action_notice.py — PAN 實作前預告閘門（Hermes 技轉）契約。

1. pan_validate_notice：雙標籤 + 實質內容 + 時間冒充防禦 + code fence 剝除
2. get_current_turn_visible_text：只收 text block（tool_use input 不冒充）、
   turn 邊界（tool_result 延續不重置）、isSidechain 跳過、fail-open
3. pan_is_readonly_bash：白名單前綴 + redirect/heredoc/複合指令保守判定
4. _check_pre_action_notice：observe 恆不 deny 只落 log、enabled=false 全靜默、
   state 缺 fail-open、deny 模式攔 + 計數 + force-release、pass 寫 marker、
   config deny_template 消費 + 壞模板 fallback、lenient_first_miss 首 miss 降
   warn、compaction continuation 回合豁免
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from handlers import pre_tool_use as ptu  # noqa: E402
import wg_evasion  # noqa: E402


# ─── helpers ─────────────────────────────────────────────────────────────────

def _pan_cfg(mode: str = "observe", **overrides):
    cfg = {
        "enabled": True,
        "mode": mode,
        "max_denies_per_turn": 2,
        "max_turn_text_chars": 12000,
        "exempt_path_substrings": ["/plans/", "/_staging/"],
        "bash_readonly_prefixes": [
            "git status", "git log", "git diff", "git ls-remote", "ls", "cat",
            "head", "rg", "pytest", "python -m pytest", "python run_verify.py",
            "get-childitem", "get-content", "select-object", "test-path",
        ],
    }
    cfg.update(overrides)
    return {"guard": {"pre_action_notice": cfg}}


def _transcript(tmp_path: Path, records) -> Path:
    p = tmp_path / "transcript.jsonl"
    p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    return p


def _user(text: str, **extra):
    return {"type": "user", "message": {"role": "user", "content": text}, **extra}


def _user_tool_result():
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "x", "content": "ok"},
    ]}}


def _asst_text(text: str, **extra):
    return {"type": "assistant",
            "message": {"content": [{"type": "text", "text": text}]}, **extra}


def _asst_tool(name: str = "Write", inp=None, **extra):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": inp or {"file_path": "x.py"}},
    ]}, **extra}


@pytest.fixture
def gate_env(tmp_path, monkeypatch):
    """PAN 流程測試環境：tmp WORKFLOW_DIR + 假 state + 捕捉 guard log。"""
    logs = []
    monkeypatch.setattr(ptu, "WORKFLOW_DIR", tmp_path / "workflow")
    monkeypatch.setattr(ptu, "read_state", lambda sid: {"turn_seq": 3})
    monkeypatch.setattr(ptu, "append_guard_log", lambda g, p: logs.append((g, p)))
    return logs


def _input(tpath: Path, tool: str = "Write", tool_input=None):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input or {"file_path": "C:/proj/src/main.py"},
        "session_id": "pansid01",
        "transcript_path": str(tpath),
        "cwd": "C:/proj",
    }


NOTICE = "執行目標：修正登入驗證並補測試；預估約 3 分鐘。"


# ─── 1. pan_validate_notice ─────────────────────────────────────────────────

@pytest.mark.parametrize("text, ok", [
    ("執行目標：修正登入驗證；預估約 3 分鐘。", True),
    ("執行目標：重構 config 載入。概估 5 分鐘", True),
    ("執行目標：修X（預估3分）", True),
    ("預估 3 分鐘就好", False),
    ("執行目標：修正登入驗證，做完再說", False),
    ("執行目標：預估約 1 分鐘。", False),
    ("執行目標:3 分鐘。預估:3 分鐘", False),
    ("執行目標：……；預估：……", False),
    ("執行目標：<一句話目標>；預估：<時間>", False),
])
def test_validator_table(text, ok):
    """Hermes 規則表：雙標籤合格/缺標籤/時間冒充/填充/佔位複誦。"""
    got, _ = ptu.pan_validate_notice(text)
    assert got is ok


def test_validator_fail_codes():
    """fail_code 對映正確（deny 訊息 {fail_detail} 消費）。"""
    assert ptu.pan_validate_notice("隨便講") == (False, "no_goal_label")
    assert ptu.pan_validate_notice("執行目標：修 bug")[1] == "no_est_label"
    assert ptu.pan_validate_notice("執行目標:預估 1 分")[1] == "goal_time_masq"
    assert ptu.pan_validate_notice("執行目標：修好；預估：）")[1] == "est_blank"


def test_validator_code_fence_not_counted():
    """code fence 內的標籤不算（引用範例不冒充）。"""
    ok, _ = ptu.pan_validate_notice("```\n執行目標：X；預估 3 分\n```")
    assert not ok


def test_validator_retry_combo_passes():
    """R7：先寫壞一組、後補好一組 → 全文任一組合通過即 pass。"""
    ok, _ = ptu.pan_validate_notice("執行目標：預估 1 分。\n" + NOTICE)
    assert ok


# ─── 2. get_current_turn_visible_text ───────────────────────────────────────

def test_visible_text_excludes_tool_use_input(tmp_path):
    """tool_use input 內的預告字串不得冒充可見文字。"""
    tp = _transcript(tmp_path, [
        _user("修一下"),
        _asst_tool(inp={"file_path": "x.py", "content": NOTICE}),
    ])
    text, probe = wg_evasion.get_current_turn_visible_text(tp)
    assert NOTICE not in text
    assert probe["tooluse_blocks"] == 1 and probe["text_blocks"] == 0


def test_visible_text_turn_boundary(tmp_path):
    """tool_result 延續不重置 turn；新真實 user prompt 重置。"""
    tp = _transcript(tmp_path, [
        _user("舊回合"), _asst_text("舊預告：" + NOTICE),
        _user("新回合開始"),
        _asst_text("A段"), _user_tool_result(), _asst_text("B段"),
    ])
    text, probe = wg_evasion.get_current_turn_visible_text(tp)
    assert "A段" in text and "B段" in text and NOTICE not in text
    assert probe["first_user_head"].startswith("新回合")


def test_visible_text_skips_sidechain(tmp_path):
    """isSidechain==True 的 record 跳過；欄位存在性記入 probe。"""
    tp = _transcript(tmp_path, [
        _user("主線"),
        _asst_text(NOTICE, isSidechain=True),
        _asst_text("主線文字", isSidechain=False),
    ])
    text, probe = wg_evasion.get_current_turn_visible_text(tp)
    assert NOTICE not in text and "主線文字" in text
    assert probe["sidechain_field"] == "present"


def test_visible_text_fail_open():
    """無路徑無文字 → ("", {})。"""
    assert wg_evasion.get_current_turn_visible_text(None) == ("", {})


def test_visible_text_boundary_lost(tmp_path):
    """tail 截斷吃掉 turn 起點（無 user record）→ 全尾段視為 turn + 標記。"""
    tp = _transcript(tmp_path, [_asst_text(NOTICE)])
    text, probe = wg_evasion.get_current_turn_visible_text(tp)
    assert NOTICE in text and probe["boundary_lost"] is True


def test_visible_text_overflow_keeps_head_and_tail(tmp_path):
    """超長 turn（如 plan mode 全程同 turn）超過 max_chars → 保留頭+尾各半，
    動手前夕的預告不被頭部累積截掉。"""
    tp = _transcript(tmp_path, [
        _user("修"), _asst_text("填" * 500), _asst_text(NOTICE),
    ])
    text, _ = wg_evasion.get_current_turn_visible_text(tp, max_chars=200)
    assert NOTICE in text and text.startswith("填")


# ─── 3. pan_is_readonly_bash ────────────────────────────────────────────────

PAN_CFG = _pan_cfg()["guard"]["pre_action_notice"]


@pytest.mark.parametrize("cmd, readonly", [
    ("git status", True),
    ("git log --oneline -5 | head -3", True),
    ("pytest hooks/verify -v", True),
    ("python -m pytest hooks/verify/verify_x.py -q 2>/dev/null", True),
    ("cd C:/proj && git status", True),
    ("git commit -m 'x'", False),
    ("git status && rm -rf build", False),
    ("cat a.txt > b.txt", False),
    ("cat <<EOF > f\nhi\nEOF", False),
    ("python -c \"open('x','w')\"", False),
])
def test_bash_readonly_table(cmd, readonly):
    """白名單前綴 + redirect/heredoc/複合段保守判定。"""
    assert ptu.pan_is_readonly_bash(cmd, PAN_CFG) is readonly


@pytest.mark.parametrize("cmd, readonly", [
    ("Get-Content x.log -Tail 5", True),
    ("Get-Content x.log | Select-Object -First 3", True),
    ("git ls-remote origin main", True),
    ("Test-Path C:/x && Get-ChildItem C:/x", True),
    ("Remove-Item build -Recurse -Force", False),
    ("Get-Content a.txt > b.txt", False),
    ("New-Item -ItemType File x.txt", False),
    ("$env:X = 'y'; Get-Content a.txt", False),
    ("git commit -m @'\nmsg\n'@", False),
])
def test_powershell_readonly_table(cmd, readonly):
    """PowerShell 共用 Bash 白名單分類器：cmdlet 前綴小寫比對、redirect/
    賦值段/here-string commit 保守 gated。"""
    assert ptu.pan_is_readonly_bash(cmd, PAN_CFG) is readonly


def test_powershell_gated_scope():
    """PowerShell 納入 gated 名單：非唯讀指令 gate、唯讀指令不 gate。"""
    assert ptu.pan_is_gated("PowerShell", {"command": "Remove-Item x"}, PAN_CFG)
    assert not ptu.pan_is_gated(
        "PowerShell", {"command": "Get-ChildItem C:/proj"}, PAN_CFG)


def test_gated_scope():
    """唯讀工具不 gate；豁免路徑不 gate；NotebookEdit 看 notebook_path。"""
    assert not ptu.pan_is_gated("Read", {"file_path": "x"}, PAN_CFG)
    assert not ptu.pan_is_gated("Grep", {}, PAN_CFG)
    assert ptu.pan_is_gated("Write", {"file_path": "C:/proj/a.py"}, PAN_CFG)
    assert not ptu.pan_is_gated(
        "Write", {"file_path": "C:/Users/x/.claude/plans/p.md"}, PAN_CFG)
    assert not ptu.pan_is_gated(
        "NotebookEdit", {"notebook_path": "C:/x/_staging/n.ipynb"}, PAN_CFG)
    assert ptu.pan_is_gated("NotebookEdit", {"notebook_path": "C:/x/n.ipynb"}, PAN_CFG)


# ─── 4. _check_pre_action_notice 流程 ───────────────────────────────────────

def test_observe_never_denies_but_logs(gate_env, tmp_path):
    """observe：無預告也不擋，log 記 would_deny + payload_keys + turn_probe。"""
    tp = _transcript(tmp_path, [_user("修"), _asst_text("我看看喔")])
    deny, warn = ptu._check_pre_action_notice(_input(tp), _pan_cfg("observe"))
    assert deny is None and warn is None
    assert len(gate_env) == 1
    g, p = gate_env[0]
    assert g == "pre-action-notice" and p["would_deny"] is True
    assert "payload_keys" in p and "turn_probe" in p
    assert not ptu._pan_pass_marker("pansid01", 3).exists()  # miss 不寫 marker


def test_observe_pass_writes_marker(gate_env, tmp_path):
    """observe：有預告 → marker 落地（後續同回合零 transcript I/O）。"""
    tp = _transcript(tmp_path, [_user("修"), _asst_text(NOTICE)])
    deny, warn = ptu._check_pre_action_notice(_input(tp), _pan_cfg("observe"))
    assert (deny, warn) == (None, None)
    assert gate_env[0][1]["would_deny"] is False
    assert ptu._pan_pass_marker("pansid01", 3).exists()


def test_disabled_fully_silent(gate_env, tmp_path):
    """enabled=false → 不讀 transcript、不落 log。"""
    tp = _transcript(tmp_path, [_user("修")])
    cfg = _pan_cfg("observe")
    cfg["guard"]["pre_action_notice"]["enabled"] = False
    assert ptu._check_pre_action_notice(_input(tp), cfg) == (None, None)
    assert gate_env == []


def test_missing_state_fail_open(gate_env, tmp_path, monkeypatch):
    """state 缺 / turn_seq 0 → fail-open + log（sidechain/resume 保底）。"""
    monkeypatch.setattr(ptu, "read_state", lambda sid: None)
    tp = _transcript(tmp_path, [_user("修")])
    assert ptu._check_pre_action_notice(_input(tp), _pan_cfg("deny")) == (None, None)
    assert gate_env[0][1]["outcome"] == "fail_open_no_state"


def test_deny_mode_blocks_then_force_releases(gate_env, tmp_path):
    """deny：無預告 → 攔 + 模板 + 計數；超過上限 force-release + marker。"""
    tp = _transcript(tmp_path, [_user("修"), _asst_text("直接動手")])
    cfg = _pan_cfg("deny")
    d1, _ = ptu._check_pre_action_notice(_input(tp), cfg)
    assert d1 and "[Guardian:PreActionNotice]" in d1 and "1/2" in d1
    d2, _ = ptu._check_pre_action_notice(_input(tp), cfg)
    assert d2 and "2/2" in d2
    d3, w3 = ptu._check_pre_action_notice(_input(tp), cfg)
    assert (d3, w3) == (None, None)  # 第 3 次強制放行
    assert ptu._pan_pass_marker("pansid01", 3).exists()
    assert gate_env[-1][1]["outcome"] == "force_release"


def test_deny_mode_pass_and_armed_fastpath(gate_env, tmp_path):
    """deny：有預告 → 放行 + marker；marker 存在後不再讀 transcript。"""
    tp = _transcript(tmp_path, [_user("修"), _asst_text(NOTICE)])
    cfg = _pan_cfg("deny")
    assert ptu._check_pre_action_notice(_input(tp), cfg) == (None, None)
    assert gate_env[-1][1]["outcome"] == "pass"
    tp.unlink()  # transcript 消失也不影響 armed 快路徑
    assert ptu._check_pre_action_notice(_input(tp), cfg) == (None, None)


def test_warn_mode_returns_warn_not_deny(gate_env, tmp_path):
    """warn：無預告 → warn 訊息（systemMessage 通道），不 deny。"""
    tp = _transcript(tmp_path, [_user("修"), _asst_text("先做")])
    deny, warn = ptu._check_pre_action_notice(_input(tp), _pan_cfg("warn"))
    assert deny is None and warn and "[Guardian:PreActionNotice]" in warn


def test_fail_open_log_throttled(gate_env, tmp_path):
    """fail-open 路徑同 (sid, turn) log 上限 3 筆——外部專案 session 每呼叫
    落一筆會洗版。"""
    missing = tmp_path / "no-such-transcript.jsonl"
    for _ in range(5):
        assert ptu._check_pre_action_notice(
            _input(missing), _pan_cfg("observe")) == (None, None)
    assert len(gate_env) == 3
    assert all(p["outcome"] == "fail_open_no_transcript" for _, p in gate_env)


def test_deny_uses_config_template_and_fallback(gate_env, tmp_path):
    """deny 訊息消費 config deny_template；模板佔位符寫壞 → fallback 模板。"""
    tp = _transcript(tmp_path, [_user("修"), _asst_text("直接動手")])
    cfg = _pan_cfg("deny", deny_template="自訂模板：{fail_detail}（{n}/{max}）")
    d1, _ = ptu._check_pre_action_notice(_input(tp), cfg)
    assert d1 == "自訂模板：缺「執行目標」標籤（1/2）"
    bad = _pan_cfg("deny", deny_template="壞模板 {no_such_key}")
    d2, _ = ptu._check_pre_action_notice(_input(tp), bad)
    assert d2 and "[Guardian:PreActionNotice]" in d2  # fallback


def test_lenient_first_miss_warns_then_denies(gate_env, tmp_path):
    """lenient_first_miss：deny 模式首 miss 降 warn（同回合快路徑偵測不可靠
    的緩衝，發現 3），第 2 次 deny，第 3 次 force-release。"""
    tp = _transcript(tmp_path, [_user("修"), _asst_text("直接動手")])
    cfg = _pan_cfg("deny", lenient_first_miss=True)
    d1, w1 = ptu._check_pre_action_notice(_input(tp), cfg)
    assert d1 is None and w1 and "[Guardian:PreActionNotice]" in w1
    assert gate_env[-1][1]["outcome"] == "lenient_warn"
    d2, w2 = ptu._check_pre_action_notice(_input(tp), cfg)
    assert d2 and w2 is None and gate_env[-1][1]["outcome"] == "deny"
    d3, w3 = ptu._check_pre_action_notice(_input(tp), cfg)
    assert (d3, w3) == (None, None)
    assert gate_env[-1][1]["outcome"] == "force_release"


def test_continuation_turn_exempt(gate_env, tmp_path):
    """compaction continuation 回合：turn 首 user 訊息命中續接敘述特徵 →
    整回合豁免（log exempt_continuation + marker 落地），無預告也不擋。"""
    tp = _transcript(tmp_path, [
        _user("This session is being continued from a previous conversation"
              " that ran out of context. Summary below:"),
        _asst_text("直接動手"),
    ])
    deny, warn = ptu._check_pre_action_notice(_input(tp), _pan_cfg("deny"))
    assert (deny, warn) == (None, None)
    assert gate_env[-1][1]["outcome"] == "exempt_continuation"
    assert ptu._pan_pass_marker("pansid01", 3).exists()
