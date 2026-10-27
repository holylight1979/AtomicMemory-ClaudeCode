"""verify_evasion_guard.py — wg_evasion helpers + hook integration tests.

Pure-function tests for wg_evasion (no state/hook mocking needed).
Hook integration smoke-tested via plan §5.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make hooks/ importable
HOOKS_DIR = Path(__file__).resolve().parent.parent  # hooks/verify/ → hooks/
sys.path.insert(0, str(HOOKS_DIR))

from wg_evasion import (  # noqa: E402
    strip_quoted_spans,
    is_test_command,
    detect_test_failure,
    claims_completion,
    detect_evasion,
    is_dismiss_prompt,
    get_last_assistant_text,
    tail_lines,
    is_core_file,
    detect_missing_scan_report,
)


# ─── is_test_command ─────────────────────────────────────────────────

@pytest.mark.parametrize("cmd, expected", [
    ("pytest tests/", True),
    ("python -m pytest tests/ -q", True),
    ("npm test", True),
    ("npm run test", True),
    ("jest --watch", True),
    ("node --check src/foo.js", True),
    ("tsc --noEmit", True),
    ("go test ./...", True),
    ("cargo test", True),
    ("ls -la", False),
    ("git log --oneline", False),
    ("python script.py", False),
    ("", False),
])
def test_is_test_command(cmd, expected):
    assert is_test_command(cmd) is expected


# ─── detect_test_failure ─────────────────────────────────────────────

def test_pytest_failure_detected():
    stdout = "tests/test_foo.py::test_bar FAILED\n======= 5 failed, 10 passed in 0.5s ======="
    r = detect_test_failure(stdout, "", False)
    assert r is not None
    assert "5 failed" in r


def test_pytest_failure_short_summary():
    stdout = "tests/a.py::t FAILED\ntests/b.py::t FAILED\n2 failed, 3 passed"
    assert detect_test_failure(stdout, "", False) is not None


def test_pytest_success_no_flag():
    stdout = "======= 15 passed in 0.5s ======="
    assert detect_test_failure(stdout, "", False) is None


def test_node_check_syntax_error():
    stderr = "/path/to/foo.js:3\nconst x = {\n         ^\nSyntaxError: Unexpected token"
    r = detect_test_failure("", stderr, False)
    assert r is not None
    assert "SyntaxError" in r


def test_tsc_error():
    stdout = "src/foo.ts(5,12): error TS2322: Type 'string' is not assignable to type 'number'."
    r = detect_test_failure(stdout, "", False)
    assert r is not None


def test_jest_failure():
    stdout = "Tests:       3 failed, 12 passed, 15 total"
    assert detect_test_failure(stdout, "", False) is not None


def test_go_test_failure():
    stdout = "--- FAIL: TestFoo (0.00s)\nFAIL\nFAIL\tfoo\t0.001s"
    assert detect_test_failure(stdout, "", False) is not None


def test_cargo_test_failure():
    stdout = "test result: FAILED. 1 passed; 1 failed; 0 ignored"
    assert detect_test_failure(stdout, "", False) is not None


def test_interrupted_returns_tail():
    stdout = "line1\nline2\nline3"
    r = detect_test_failure(stdout, "", True)
    assert r is not None
    assert "line3" in r


def test_interrupted_empty_output():
    r = detect_test_failure("", "", True)
    assert r == "(interrupted, no output)"


def test_tail_lines_limits():
    s = "\n".join(f"line{i}" for i in range(50))
    r = tail_lines(s, 5)
    assert r.count("\n") == 4
    assert "line49" in r
    assert "line45" in r
    assert "line44" not in r


# ─── claims_completion ───────────────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("全部做完了，可以 commit 了", True),
    ("收尾階段，跑測試", True),
    ("done.", True),
    ("All set, moving on", True),
    ("大功告成", True),
    ("已解決 bug", True),
    ("我已修掉 3 個，剩 2 個", False),
    ("還在改", False),
    ("", False),
    (None, False),
])
def test_claims_completion(text, expected):
    assert claims_completion(text) is expected


@pytest.mark.parametrize("text", [
    # 進行式/否定修飾緊鄰完成詞 → 非真正終結宣告（實測 false-positive）
    "完成條件尚未滿足",
    "我總結一下但還沒做完",
    "尚未完成",
    "還沒做完",
    "先確認 X 再宣告完成",
    "細節待補",
    "這部分還沒解決",
])
def test_claims_completion_excludes_incomplete_modifier(text):
    assert claims_completion(text) is False


def test_claims_completion_only_scans_tail():
    # 前文有「完成」但 tail 2000 字沒有 → False
    head = "任務完成條件檢查。"
    filler = "x" * 2500
    text = head + filler
    assert claims_completion(text) is False


# ─── detect_evasion ──────────────────────────────────────────────────

def test_evasion_flags_out_of_scope():
    t = "這個 bug 是既有的 drift 非本次改動所致，留給未來 session 處理。"
    r = detect_evasion(t, [])
    assert r is not None
    # 文字中有多個可能命中：既有...drift / 非本次 / 留給未來 — 任一即可
    assert r["phrase"]
    assert "context_excerpt" in r


def test_evasion_flags_preexisting():
    r = detect_evasion("This is pre-existing behavior, skipping.", [])
    assert r is not None


@pytest.mark.parametrize("text", [
    "這個小問題下次再處理吧",
    "下回再修一下",
    "下一次再看",
    "之後再處理這個 drift",
    "晚點再補",
    "稍後再修",
    "有空再弄",
    "有時間再看",
    "未來處理這個",
    "未來再處理",
    "留給使用者自己處理",
    "待後續追蹤",
    "另行處理",
    "另外處理即可",
])
def test_evasion_flags_deferral_keywords(text):
    """時間性延後語（退避關鍵字）須被偵測到。"""
    r = detect_evasion(text, [])
    assert r is not None, f"未抓到退避語：{text!r}"


# ─── G6 階段 4（P7）：退避例外的入口接上——不做行＋理由、使用者引用對到事項（規則 NOT_DOING_DECLARED／USER_WAIVER_NEEDS_CITATION）────

def test_p7_dismiss_word_alone_no_longer_waives():
    """使用者近 3 則有「先這樣」不再整段關掉偵測（舊 escape hatch）：要 AI 引用原句對到事項才算。"""
    t = "既有的問題，非本次範圍。"
    assert detect_evasion(t, ["先這樣，留著吧"]) is not None
    assert detect_evasion(t, ["a", "先這樣", "b"]) is not None


def test_p7_not_doing_line_with_reason_not_flagged_and_audited():
    """退避語就在不做行裡、附了理由 → 不標，audit 記一筆（stop 落 guard-evasion_declared.jsonl）。"""
    t = "完成。\n不做｜registry 污染：既有的問題，修要動 wg_core 的 state 寫入，風險是並行競寫毀 state，這輪不碰。"
    audit = []
    assert detect_evasion(t, [], audit=audit) is None
    assert audit and audit[0]["rule"] == "NOT_DOING_DECLARED" and audit[0]["phrase"] == "既有的問題"
    assert "registry 污染" in audit[0]["why"]


def test_p7_not_doing_line_with_placeholder_reason_still_flagged():
    t = "完成。\n不做｜registry 污染：既有的問題，<不修的實際風險>"
    r = detect_evasion(t, [])
    assert r is not None and r["phrase"] == "既有的問題"


def test_p7_item_named_in_not_doing_line_covers_sentence_elsewhere():
    plain = "registry 污染留給未來處理。"
    assert detect_evasion(plain, []) is not None, "前置：沒有不做行時這句會標"
    audit = []
    assert detect_evasion(plain + "\n不做｜registry 污染：要動 state 寫入，並行競寫風險，這輪不碰。", [], audit=audit) is None
    assert len(audit) == 1 and audit[0]["rule"] == "NOT_DOING_DECLARED"


def test_p7_audit_one_entry_per_not_doing_line():
    """同一條不做行裡有兩個退避詞（既有的問題＋另行處理）→ 留帳一筆，不是兩筆（codex WARN）。"""
    audit = []
    assert detect_evasion("完成。\n不做｜registry 污染：既有的問題，另行處理，因為要動 state 寫入有並行競寫風險。", [], audit=audit) is None
    assert len(audit) == 1


def test_p7_user_citation_waives_only_the_cited_item():
    t = "A 清理先跳過。\nB 瘦身也先跳過。\n不做｜A 清理：使用者說「A 先這樣」"
    prompts = ["A 先這樣，B 要做"]
    audit = []
    r = detect_evasion(t, prompts, audit=audit)
    assert r is not None and "B 瘦身" in r["context_excerpt"]
    assert audit and audit[0]["rule"] == "NOT_DOING_DECLARED" and "A 清理" in audit[0]["why"]
    # 引用的原句不再比對近幾則使用者原話：寫了「不做｜」那一件就不標
    assert detect_evasion("A 清理先跳過。\n不做｜A 清理：使用者說「A 先這樣」", ["做 A", "x", "y"]) is None


def test_p7_flag_carries_category_and_hint():
    r = detect_evasion("這是 pre-existing 的問題。", [])
    assert r and r["category"] == "precedent-drift"
    assert "追蹤｜" in r["hint"] and "改得快又有效" in r["hint"]


def test_p7_ups_dismiss_no_longer_clears_failing_tests(monkeypatch):
    """ups_gates：使用者說「先這樣」不再清掉整份紅測清單（豁免改在 Stop 由不做行引用對到那一筆）。"""
    from handlers import ups_gates as ug
    state = {"failing_tests": [{"cmd": "pytest verify_a.py", "session_id": "s"}], "recent_user_prompts": []}
    ug.run_pre_gates("s", state, {}, "先這樣", "先這樣", [])
    assert state["failing_tests"]


def test_045_peer_message_is_not_a_turn_boundary():
    """退避預告切點：整則都是同伴訊息（不論內容）→ 不是回合起點（早段寫的預告不被切掉）；使用者打字 → 是；tool_result 延續 → 不是。"""
    from wg_evasion import _is_real_user_prompt
    peer = '<cross-session-message from="x" from-name="claude-ad">\n對帳過了，上GIT\n</cross-session-message>'
    dispatch = '<cross-session-message from="x" from-name="claude-aa">\n派工：接 B14\n</cross-session-message>'
    assert _is_real_user_prompt(peer) is False
    assert _is_real_user_prompt([{"type": "text", "text": peer}]) is False
    assert _is_real_user_prompt(dispatch) is False
    assert _is_real_user_prompt("請把這個修好") is True
    assert _is_real_user_prompt([{"type": "tool_result", "content": "x"}]) is False
    assert _is_real_user_prompt("<task-notification>done</task-notification>") is False


def test_zuo_wan_le_counts_as_completion_claim():
    """第二波 C′ 第二跑（C2 transcript:304）：收尾寫「折扣碼功能做完了：15 個測試全過，已 commit」，詞表只有「全部做完」，
    判成沒宣告完成，第二意見閘等收尾閘全部沒觸發。"""
    assert claims_completion("折扣碼功能做完了：15 個測試全過，已 commit（59298ec），沒有 push。") is True
    assert claims_completion("這樣就做完了嗎？我再確認一次") is False                    # 問句不算
    assert claims_completion("先把那個檢查做完再動手") is False                           # 沒有「了」：不是完成宣告
    assert claims_completion("還沒做完了的部分列在下面") is False                          # 否定照排除


@pytest.mark.parametrize("text, expected", [
    ("三件都做完了。中途被擋了兩次，都補上了。", True),                       # 實例：內文描述流程的「中途」讓整則不算，第二意見沒觸發
    ("我還沒動git：完成的三件列在下面。\n全部做完了，等你看 diff。", True),     # 開頭那句的否定只取消它自己
    ("三件都做完了，測試全過。\n目標樹：T2 [進行中｜明確｜使用者說的] 報表改版（下一個需求）", True),   # 貼出的樹節點狀態
    ("第一件完成，中途還卡著兩件。", False),                                   # 同一句：照排除
    ("A1 完成；整合尚未開始。", False),                                        # 分號不切句：中途狀態
    ("A2 已完成，仍在等 A1 回報。", False),
    ("A 完成。仍在等 B 回報。", False),                                        # 「還在等」是整則的狀態：句號分開也不算
    ("A1 完成。整合尚未開始。", False),
])
def test_completion_exclude_only_cancels_its_own_sentence(text, expected):
    """規則 COMPLETION_CLAIM_PER_SENTENCE：否定、待補、中途、進行中只取消同一句的完成詞，不再整則一刀切（舊碼前三列判 False）；
    講「這則之後工作還在繼續」的（仍在等、等待…回報、尚未開始）照舊整則不算（codex 一輪 BLOCK 1：句號分開的中途回報被當收尾）。"""
    assert claims_completion(text) is expected


def test_in_progress_text_not_midway_when_another_sentence_claims_done():
    """同一規則：收割待補閘的「中途狀態句不擋」也逐句看——另有一句宣告完成就是收尾（舊碼：有「中途」就當中途、不擋）；
    還在等別人的整則照舊是中途。"""
    from wg_harvest import in_progress_text
    assert in_progress_text("三件都做完了。中途被擋了兩次，都補上了。") is False
    assert in_progress_text("A2 已完成，仍在等 A1 回報。") is True
    assert in_progress_text("A 完成。仍在等 B 回報。") is True
    assert in_progress_text("搞定前半，目前中途，先回報進度。") is True


def _gate_texts():
    """hooks／lib（不含 verify）原始碼裡送得到 AI 眼前的字串：每個字串字面值（f-string 整條、插值換成 X；`+` 串起來的字面值併成
    一條）。不算：docstring、正則來源（`re.<函式>` 的第一個參數、lazy_re／_compile_union 的參數、名字以 _RE／PATTERNS 結尾的常數）、
    規則說明表 RULES（文件，不送出）、印到 sys.stderr 與留帳呼叫的參數。回 [(相對路徑, 行號, 文字)]。"""
    import ast
    pattern_calls = {"lazy_re", "_compile_union"}
    log_calls = {"log", "_log", "append_guard_log", "_atom_debug_error", "_atom_debug_log"}

    def name_of(node):
        return node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", "")

    def is_stderr(node):
        return isinstance(node, ast.Attribute) and node.attr == "stderr" and name_of(node.value) == "sys"

    def skipped_roots(tree):
        roots = []
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body:
                b = n.body[0]
                if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and isinstance(b.value.value, str):
                    roots.append(b.value)
            elif isinstance(n, ast.Call):
                fn = name_of(n.func)
                on_re = isinstance(n.func, ast.Attribute) and name_of(n.func.value) == "re"
                if on_re and n.args:
                    roots.append(n.args[0])
                stderr = fn == "print" and any(k.arg == "file" and is_stderr(k.value) for k in n.keywords)
                if fn in pattern_calls or fn in log_calls or stderr or (fn == "update" and name_of(n.func.value) == "RULES"):
                    roots.append(n)
            elif isinstance(n, (ast.Assign, ast.AnnAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                names = [name_of(t.value if isinstance(t, ast.Subscript) else t) for t in targets]
                if any(x.endswith("_RE") or x.upper().endswith("PATTERNS") or x == "RULES" for x in names):
                    roots.append(n.value)
        return {id(x) for r in roots for x in ast.walk(r)}

    def text_of(node):
        """字串字面值、f-string、全由這兩種用 + 串起來的式子 → 文字；其他 → None。"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return "".join(v.value if isinstance(v, ast.Constant) else "X" for v in node.values)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = text_of(node.left), text_of(node.right)
            return None if left is None or right is None else left + right
        return None

    out = []
    root = HOOKS_DIR.parent
    for base in ("hooks", "lib"):
        for p in sorted((root / base).rglob("*.py")):
            rel = p.relative_to(root).as_posix()
            if "/verify/" in rel:
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            skip = skipped_roots(tree)
            inner = set()
            for n in ast.walk(tree):
                if id(n) in skip or id(n) in inner:
                    continue
                text = text_of(n)
                if text is None:
                    continue
                inner |= {id(x) for x in ast.walk(n) if x is not n}     # 併進這一條的片段不再各算一次
                out.append((rel, n.lineno, text))
    return out


def test_gate_texts_do_not_trip_evasion_detector():
    """規則 GATE_TEXT_AVOIDS_EVASION_WORDS：閘的擋訊息與提示裡的字句，AI 照抄進回覆時不能被退避偵測判成 AI 退避
    （實例：DataFileAsk 擋訊息「(c) 非本 session 建」，AI 在交付裡原樣貼出被擋的那則，判分兩跑都記成退避）。
    偵測面不開引用豁免，改擋訊息的說法；每則字串直接跑 detect_evasion（引號內、宣稱行、有理由的不做行照偵測本身的規則不算）。"""
    hits = []
    for rel, line, text in _gate_texts():
        ev = detect_evasion(text, [])
        if ev:
            hits.append(f"{rel}:{line}：「{ev['phrase']}」← {text[:80]}")
    assert not hits, "\n".join(hits)


def test_stop_hook_feedback_is_not_a_turn_boundary():
    """Claude Code 把 Stop hook 的擋訊息寫成 user 紀錄「Stop hook feedback:…」：不是使用者打字，不是回合起點
    （第二意見閘與退避預告切點共用這個判定；C-1 被別的閘擋一次，已跑完的第二意見就被切掉）。"""
    from wg_evasion import is_turn_start
    fb = "Stop hook feedback:\n[Guardian:ReadingPath] ✗ (t) TURN_JUDGMENT_REQUIRED：側面數據到門檻"
    rec = lambda content, meta: {"type": "user", "isMeta": meta, "message": {"role": "user", "content": content}}  # noqa: E731
    assert is_turn_start(rec(fb, True)) is False
    assert is_turn_start(rec([{"type": "text", "text": fb}], True)) is False
    assert is_turn_start(rec(fb + "\n照這個錯誤幫我改", False)) is True                 # 使用者自己貼的（沒有 isMeta）照算新回合（Codex）
    assert is_turn_start(rec("我看了 Stop hook feedback: 那段，照它改", None)) is True
    assert is_turn_start({"type": "assistant", "message": {"content": "x"}}) is False


def test_evasion_no_phrase_no_flag():
    assert detect_evasion("一切正常，已完成修復", []) is None


def test_evasion_empty_text():
    assert detect_evasion("", []) is None
    assert detect_evasion(None, []) is None


# ─── is_dismiss_prompt ──────────────────────────────────────────────

@pytest.mark.parametrize("prompt, expected", [
    ("先這樣吧", True),
    ("留著", True),
    ("跳過", True),
    ("known regression", True),
    ("continue", False),
    ("", False),
])
def test_is_dismiss_prompt(prompt, expected):
    assert is_dismiss_prompt(prompt) is expected


# ─── get_last_assistant_text ────────────────────────────────────────

def test_get_last_assistant_text_reads_jsonl(tmp_path):
    p = tmp_path / "transcript.jsonl"
    p.write_text(
        '{"type":"user","message":{"content":[]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"'
        + ("First assistant reply with enough length to count here." * 2)
        + '"}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"text","text":"'
        + ("Second LAST reply long enough body abc" * 2)
        + '"}]}}\n',
        encoding="utf-8",
    )
    r = get_last_assistant_text(p)
    assert "Second LAST" in r
    assert "First assistant" not in r


def test_get_last_assistant_text_missing_file(tmp_path):
    assert get_last_assistant_text(tmp_path / "nope.jsonl") == ""


def test_get_last_assistant_text_none_path():
    assert get_last_assistant_text(None) == ""


def test_get_last_assistant_text_skips_short():
    p = HOOKS_DIR  # placeholder; override with tmp
    import tempfile, json as _j
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        _j.dump({"type": "assistant", "message": {"content": [{"type": "text", "text": "short"}]}}, f)
        f.write("\n")
        _j.dump({"type": "assistant", "message": {"content": [{"type": "text", "text": "a" * 100}]}}, f)
        f.write("\n")
        fp = f.name
    r = get_last_assistant_text(Path(fp))
    assert len(r) >= 100
    Path(fp).unlink()


# ─── is_core_file ───────────────────────────────────────────

@pytest.mark.parametrize("path, expected", [
    (r"c:\Users\x\.claude\hooks\wg_evasion.py", True),
    ("c:/Users/x/.claude/lib/atom_access.py", True),
    ("c:/Users/x/.claude/tools/foo.py", True),
    (r"c:\Users\x\.claude\rules\core.md", True),
    (r"c:\Users\x\.claude\IDENTITY.md", True),
    (r"c:\Users\x\.claude\USER.md", True),
    (r"c:\Users\x\.claude\CLAUDE.md", True),
    (r"c:\Users\x\.claude\settings.json", True),
    (r"c:\Users\x\.claude\IDENTITY-holylight.md", True),
    # 非 core：純內容 / 文件
    (r"c:\Users\x\.claude\memory\foo.md", False),
    (r"c:\proj\_AIDocs\bar.md", False),
    (r"c:\proj\src\app.py", False),
    ("", False),
])
def test_is_core_file(path, expected):
    assert is_core_file(path) is expected


# ─── detect_missing_scan_report (降條件觸發) ──────────────────

def _mf(*paths):
    return [{"path": p, "tool": "Edit"} for p in paths]


def test_scan_report_single_noncore_not_triggered():
    # 純單檔 / 文件小改 → 不觸發（4.8 過度觸發修正）
    assert detect_missing_scan_report(
        "全部完成了", _mf(r"c:\a\.claude\memory\foo.md"), [], 2
    ) is False


def test_scan_report_single_core_triggered():
    # 動 core 檔 → 觸發
    assert detect_missing_scan_report(
        "全部完成了", _mf(r"c:\a\.claude\hooks\x.py"), [], 2
    ) is True


def test_scan_report_multi_noncore_triggered():
    # 多檔（≥min_files）→ 觸發
    assert detect_missing_scan_report(
        "全部完成了", _mf("a/x.md", "a/y.md"), [], 2
    ) is True


def test_scan_report_dupe_paths_below_min_not_triggered():
    # 同一非 core 檔重複算一次 → unique<min → 不觸發
    assert detect_missing_scan_report(
        "全部完成了", _mf("a/x.md", "a/x.md"), [], 2
    ) is False


def test_scan_report_has_report_not_triggered():
    assert detect_missing_scan_report(
        "全部完成了 缺失發現：無", _mf(r"c:\a\.claude\hooks\x.py"), [], 2
    ) is False


def test_scan_report_no_completion_not_triggered():
    assert detect_missing_scan_report(
        "還在做", _mf(r"c:\a\.claude\hooks\x.py"), [], 2
    ) is False


def test_scan_report_dismiss_prompt_not_triggered():
    """使用者說「先這樣」＝這次收尾檢核整批不做：不用再逐項引用原話。"""
    assert detect_missing_scan_report(
        "全部完成了", _mf(r"c:\a\.claude\hooks\x.py"), ["先這樣"], 2
    ) is False
    assert detect_missing_scan_report(
        "全部完成了\n不做｜收尾檢核：使用者說「先這樣」", _mf(r"c:\a\.claude\hooks\x.py"), ["先這樣"], 2
    ) is False


def test_scan_report_empty_files_not_triggered():
    assert detect_missing_scan_report("全部完成了", [], [], 2) is False


# ─── strip_quoted_spans / 引號內轉述不觸發 ───────────────────────────────

def test_quoted_phrase_not_flagged_unquoted_is():
    """引用 hook 判定原文（引號內）不標；同詞寫在自己敘述句照標。"""
    quoted = "hook 標的「下個 session」是我引用它的判定原文，沒有推遲。"
    assert detect_evasion(quoted, []) is None
    plain = "這個小問題留到下個 session 再處理。"
    assert detect_evasion(plain, []) is not None


def test_strip_quoted_spans_preserves_length_and_unpaired():
    s = "前「中間」後 `code` 尾『引』端"
    out = strip_quoted_spans(s)
    assert len(out) == len(s)
    assert "中間" not in out and "code" not in out and "引" not in out
    unpaired = "只有開「引號沒關 下個 session 也在外面"
    assert strip_quoted_spans(unpaired) == unpaired
