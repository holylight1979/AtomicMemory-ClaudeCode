"""verify_rescue_log.py — 救援日誌（wg_rescue）契約。

extract_specific_tokens：
- 抓：檔案路徑（含分隔符+副檔名）、inline code span、ALL_CAPS 常數、snake_case ≥8
- 不抓：泛詞黑名單、<6 字元短詞、純數字/符號；去重、上限 20/atom

record_rescue_watch：
- token 首見 → 歸屬該 atom；同 token 出現在第二個 atom → 歸因模糊整個剔除且不再收
- watch 總量硬頂 200

check_rescue_hits：
- tool_input 命中 → 落 jsonl（atom/token/evidence/turn_seq/tool），每 (atom,token) 每 session 一次
- Agent/Task 的 prompt 欄不掃（自動注入自我命中）；寫 memory/_atoms .md 不掃
- 大小寫不敏感比對；無 watch → 0 且不動 state
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_rescue  # noqa: E402
from wg_rescue import (  # noqa: E402
    check_rescue_hits, extract_specific_tokens, record_rescue_watch,
)

SAMPLE = """
# 某 atom

- 修 flag 用 `hooks/version_guard.py` 程式化 warn
- 常數 TURN_BUDGET_LIMIT 控制預算；索引在 memory/_atom_index.json
- 跑 `python run_verify.py` 驗證；欄位 sync_completed 由 Stop 閘標
- 泛詞:python memory config session atom（不該收）
- 短詞:`abc` x1 y2（不該收）
"""


# ── extract_specific_tokens ─────────────────────────────────────────────────

def test_extract_paths_consts_snake_and_spans():
    toks = extract_specific_tokens(SAMPLE)
    lower = [t.lower() for t in toks]
    assert "hooks/version_guard.py" in lower
    assert "memory/_atom_index.json" in lower
    assert "turn_budget_limit" in lower
    assert "python run_verify.py" in lower  # code span 指令
    assert "sync_completed" in lower


def test_extract_rejects_generic_and_short():
    toks = [t.lower() for t in extract_specific_tokens(SAMPLE)]
    for bad in ("python", "memory", "config", "session", "atom", "abc", "x1"):
        assert bad not in toks


def test_extract_dedup_and_cap():
    content = "\n".join(f"`unique_token_{i:02d}_zz`" for i in range(40))
    toks = extract_specific_tokens(content + "\n" + content)
    assert len(toks) == wg_rescue._MAX_TOKENS_PER_ATOM
    assert len(set(t.lower() for t in toks)) == len(toks)


# ── record_rescue_watch ─────────────────────────────────────────────────────

def test_watch_ambiguous_token_dropped():
    state = {}
    record_rescue_watch(state, [("atom-a", "`shared_specific_token` 說明")])
    assert "shared_specific_token" in state["rescue_watch"]
    record_rescue_watch(state, [("atom-b", "`shared_specific_token` 另一個")])
    assert "shared_specific_token" not in state["rescue_watch"]
    assert "shared_specific_token" in state["rescue_ambiguous"]
    # 之後任何 atom 再帶同 token 也不再收
    record_rescue_watch(state, [("atom-c", "`shared_specific_token`")])
    assert "shared_specific_token" not in state["rescue_watch"]


def test_watch_same_atom_reinject_keeps_owner():
    state = {}
    record_rescue_watch(state, [("atom-a", "`my_special_thing_x`")])
    record_rescue_watch(state, [("atom-a", "`my_special_thing_x`")])
    assert state["rescue_watch"]["my_special_thing_x"].startswith("atom-a\t")


# ── check_rescue_hits ───────────────────────────────────────────────────────

def _state_with_watch():
    state = {"turn_seq": 7}
    record_rescue_watch(state, [("atom-a", "見 `hooks/version_guard.py` 與 TURN_BUDGET_LIMIT")])
    return state


def test_hit_writes_jsonl_once(tmp_path):
    state = _state_with_watch()
    log = tmp_path / "rescue.jsonl"
    n = check_rescue_hits(state, "sid", "Bash",
                          {"command": "cat hooks/version_guard.py"}, log_path=log)
    assert n == 1
    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert rec["atom"] == "atom-a"
    assert rec["token"].lower() == "hooks/version_guard.py"
    assert rec["turn_seq"] == 7 and rec["tool"] == "Bash"
    assert "version_guard" in rec["evidence"]
    # 同 token 再命中不重複落檔
    n2 = check_rescue_hits(state, "sid", "Bash",
                           {"command": "python hooks/version_guard.py"}, log_path=log)
    assert n2 == 0


def test_hit_case_insensitive(tmp_path):
    state = _state_with_watch()
    log = tmp_path / "rescue.jsonl"
    assert check_rescue_hits(state, "sid", "Bash",
                             {"command": "echo turn_budget_limit"}, log_path=log) == 1


def test_agent_prompt_not_scanned(tmp_path):
    state = _state_with_watch()
    log = tmp_path / "rescue.jsonl"
    n = check_rescue_hits(state, "sid", "Agent",
                          {"prompt": "check hooks/version_guard.py"}, log_path=log)
    assert n == 0 and not log.exists()
    # 非 prompt 欄照掃
    n2 = check_rescue_hits(state, "sid", "Agent",
                           {"description": "audit hooks/version_guard.py"}, log_path=log)
    assert n2 == 1


def test_memory_md_write_not_scanned(tmp_path):
    state = _state_with_watch()
    log = tmp_path / "rescue.jsonl"
    n = check_rescue_hits(state, "sid", "Write", {
        "file_path": "C:/Users/x/.claude/memory/foo.md",
        "content": "TURN_BUDGET_LIMIT hooks/version_guard.py",
    }, log_path=log)
    assert n == 0 and not log.exists()


def test_no_watch_noop():
    assert check_rescue_hits({}, "sid", "Bash", {"command": "ls"}) == 0
