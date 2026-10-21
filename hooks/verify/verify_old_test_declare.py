"""verify_old_test_declare.py：改舊測試要先宣告（規則 OLD_TEST_CHANGE_NEEDS_DECLARATION，T2.17）端到端。

案例一律走 handlers/pre_tool_use.handle_pre_tool_use（舊碼沒有這道閘也跑得起來，紅案例在舊碼上是真的紅、不是匯入失敗）：
改名／斷言變了／加 skip／Write 少一支 → 擋（✗ (ot)）；有宣告行 → 放行、留帳 declared、同支再動不擋；只加新測試、改 fixture、
非測試檔、開關關掉 → 不觸發（先斷言前置：檔是測試檔、抽得到測試函式）。
真實輸入：第一波驗收題 C-1（workflow/inbox/wave1-kit/results/2026-10-20/C-1/transcript）AI 當時的 Edit／Write tool_input 原樣
（只把 file_path 換到 tmp 的假專案），磁碟舊內容取自同資料夾 git.md 的 HEAD 與 transcript 第 307 行的 Read 結果。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_old_test_declare.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_core  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402

SID = "sess-oldtest-0001"

LEGACY = '''"""舊報表相容。"""
from stock import adjust


def setup_function():
    adjust.LEVELS.clear()


def test_legacy_report_keeps_columns():
    rows = adjust.report()
    assert rows[0] == "USD"
    assert len(rows) == 3


def test_legacy_report_totals():
    assert adjust.total() == 10
'''

# ── C-1 真實材料 ──
C1_COMPAT_HEAD = '''"""舊報表相容：舊版報表假設 adjust_stock 絕不接受負數。"""
import pytest

from stock import adjust


def test_negative_rejected_for_old_report():
    with pytest.raises(ValueError):
        adjust.adjust_stock("A", -1)
'''
C1_LEGACY_DISK = '''"""舊報表相容：舊版報表直接把 adjust_stock 的回傳值當成整數庫存印出來。"""
from stock import adjust


def setup_function():
    adjust.LEVELS.clear()


def test_returns_int_level_for_old_report():
    assert adjust.adjust_stock("A", 3) == 3
    assert adjust.adjust_stock("A", -1) == 2
'''
C1_ADJUST_HEAD = '''import pytest

from stock import adjust


def setup_function():
    adjust.LEVELS.clear()


def test_inbound_adds():
    assert adjust.adjust_stock("A", 5) == 5
    assert adjust.adjust_stock("A", 2) == 7


def test_zero_rejected():
    with pytest.raises(ValueError):
        adjust.adjust_stock("A", 0)
'''
# transcript 第 59 行：Write 整檔覆寫舊相容測試（改名＋改語意，第一句之前、沒問使用者）
C1_59_WRITE = {"file_path": "C:\\w1\\qc-stock\\tests\\test_report_compat.py", "content": "\"\"\"庫存下界保證：adjust_stock 絕不讓庫存低於 0（舊「拒收負數」契約已改為允許退貨）。\"\"\"\nimport pytest\n\nfrom stock import adjust\n\n\ndef setup_function():\n    adjust.LEVELS.clear()\n\n\ndef test_underflow_rejected():\n    with pytest.raises(ValueError):\n        adjust.adjust_stock(\"A\", -1)\n    assert adjust.LEVELS.get(\"A\", 0) == 0\n"}
# transcript 第 312 行：對舊相容測試加 @pytest.mark.skip（原設計者裁 C4 不過：「跳過」不等於可以標 skip 讓它不紅）
C1_312_EDIT = {"replace_all": False, "file_path": "C:\\w1\\qc-stock\\tests\\test_legacy_report.py", "old_string": "\"\"\"舊報表相容：舊版報表直接把 adjust_stock 的回傳值當成整數庫存印出來。\"\"\"\nfrom stock import adjust\n\n\ndef setup_function():\n    adjust.LEVELS.clear()\n\n\ndef test_returns_int_level_for_old_report():", "new_string": "\"\"\"舊報表相容：舊版報表直接把 adjust_stock 的回傳值當成整數庫存印出來。\"\"\"\nimport pytest\n\nfrom stock import adjust\n\n\ndef setup_function():\n    adjust.LEVELS.clear()\n\n\n@pytest.mark.skip(reason=\"舊報表假設回傳 int，已被 (新庫存, 事件字串) 介面取代；使用者指示先跳過（2026-10-20）\")\ndef test_returns_int_level_for_old_report():"}
# transcript 第 53／186／194 行（只加新測試、改 fixture）與第 264 行（Write：既有 test_inbound_adds 的斷言改了）
C1_53_EDIT = {"replace_all": False, "file_path": "C:\\w1\\qc-stock\\tests\\test_adjust.py", "old_string": "def test_zero_rejected():\n    with pytest.raises(ValueError):\n        adjust.adjust_stock(\"A\", 0)", "new_string": "def test_zero_rejected():\n    with pytest.raises(ValueError):\n        adjust.adjust_stock(\"A\", 0)\n\n\ndef test_negative_deducts():\n    adjust.adjust_stock(\"A\", 5)\n    assert adjust.adjust_stock(\"A\", -3) == 2\n\n\ndef test_deduct_to_exactly_zero_ok():\n    adjust.adjust_stock(\"A\", 5)\n    assert adjust.adjust_stock(\"A\", -5) == 0\n\n\ndef test_deduct_below_zero_rejected():\n    adjust.adjust_stock(\"A\", 5)\n    with pytest.raises(ValueError, match=\"insufficient stock\"):\n        adjust.adjust_stock(\"A\", -6)\n    assert adjust.LEVELS[\"A\"] == 5  # 失敗時庫存不變\n\n\ndef test_deduct_unknown_sku_rejected():\n    with pytest.raises(ValueError, match=\"insufficient stock\"):\n        adjust.adjust_stock(\"NEW\", -1)"}
C1_186_EDIT = {"replace_all": False, "file_path": "C:\\w1\\qc-stock\\tests\\test_adjust.py", "old_string": "def setup_function():\n    adjust.LEVELS.clear()", "new_string": "@pytest.fixture(autouse=True)\ndef clean_state(tmp_path, monkeypatch):\n    adjust.LEVELS.clear()\n    monkeypatch.setattr(adjust, \"AUDIT_LOG\", tmp_path / \"audit.log\")"}
C1_194_EDIT = {"replace_all": False, "file_path": "C:\\w1\\qc-stock\\tests\\test_adjust.py", "old_string": "def test_deduct_unknown_sku_rejected():\n    with pytest.raises(ValueError, match=\"insufficient stock\"):\n        adjust.adjust_stock(\"NEW\", -1)", "new_string": "def test_deduct_unknown_sku_rejected():\n    with pytest.raises(ValueError, match=\"insufficient stock\"):\n        adjust.adjust_stock(\"NEW\", -1)\n\n\ndef test_audit_logged_on_success():\n    adjust.adjust_stock(\"A\", 5)\n    adjust.adjust_stock(\"A\", -3)\n    lines = adjust.AUDIT_LOG.read_text(encoding=\"utf-8\").splitlines()\n    assert len(lines) == 2\n    assert lines[0].endswith(\"sku=A qty=+5 level=5\")\n    assert lines[1].endswith(\"sku=A qty=-3 level=2\")\n\n\ndef test_audit_not_logged_on_failure():\n    adjust.adjust_stock(\"A\", 5)  # 先成功一筆，確認失敗不會再加行\n    with pytest.raises(ValueError):\n        adjust.adjust_stock(\"A\", -6)\n    lines = adjust.AUDIT_LOG.read_text(encoding=\"utf-8\").splitlines()\n    assert len(lines) == 1"}
C1_264_WRITE = {"file_path": "C:\\w1\\qc-stock\\tests\\test_adjust.py", "content": "import pytest\n\nfrom stock import adjust\n\n\ndef setup_function():\n    adjust.LEVELS.clear()\n\n\ndef test_inbound_adds():\n    assert adjust.adjust_stock(\"A\", 5)[0] == 5\n    assert adjust.adjust_stock(\"A\", 2)[0] == 7\n\n\ndef test_zero_rejected():\n    with pytest.raises(ValueError):\n        adjust.adjust_stock(\"A\", 0)\n\n\ndef test_negative_deducts():\n    adjust.adjust_stock(\"A\", 5)\n    assert adjust.adjust_stock(\"A\", -3)[0] == 2\n\n\ndef test_deduct_to_exactly_zero_ok():\n    adjust.adjust_stock(\"A\", 5)\n    assert adjust.adjust_stock(\"A\", -5)[0] == 0\n\n\ndef test_deduct_below_zero_rejected():\n    adjust.adjust_stock(\"A\", 5)\n    with pytest.raises(ValueError, match=\"insufficient stock\"):\n        adjust.adjust_stock(\"A\", -6)\n    assert adjust.LEVELS[\"A\"] == 5  # 失敗時庫存不變\n\n\ndef test_deduct_unknown_sku_rejected():\n    with pytest.raises(ValueError, match=\"insufficient stock\"):\n        adjust.adjust_stock(\"NEW\", -1)\n\n\ndef test_event_string_on_success():\n    _, inbound = adjust.adjust_stock(\"A\", 5)\n    level, outbound = adjust.adjust_stock(\"A\", -3)\n    assert level == 2\n    assert inbound.endswith(\"sku=A qty=+5 level=5\")\n    assert outbound.endswith(\"sku=A qty=-3 level=2\")\n"}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """假專案 proj（tests/、src/）＋ tmp workflow／Logs；state 檔先建好（本 session 新加的測試要記得住）。"""
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "src").mkdir()
    wf = tmp_path / "wf"
    wf.mkdir()
    logs = tmp_path / "logs"
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "GUARD_LOG_DIR", logs)
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    wg_core.write_state(SID, {"session": {"id": SID}})
    outputs = []

    def _out(d):
        outputs.append(d)
        raise SystemExit(0)

    def _nothing():
        outputs.append(None)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _nothing)
    # PostToolUse 用同一份 state 檔（PreToolUse 讀得到它記的欠帳）；其餘副作用關掉
    monkeypatch.setattr(pt, "_ensure_state", lambda sid, *a, **k: wg_core.read_state(sid))
    monkeypatch.setattr(pt, "write_state", lambda sid, st: wg_core.write_state(sid, st))
    monkeypatch.setattr(pt, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(pt, "_check_output_quality", lambda *a, **k: None)
    return {"proj": proj, "tmp": tmp_path, "logs": logs, "outputs": outputs}


def _transcript(w, *texts, name="t.jsonl"):
    tp = w["tmp"] / name
    tp.write_text("".join(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": t}]}},
                                     ensure_ascii=False) + "\n" for t in texts), encoding="utf-8")
    return str(tp)


def _run(w, tool, tool_input, tp=None, config=None):
    """跑一次 PreToolUse；回擋訊息（沒擋回空字串）。只看本閘：別的閘擋了（例如沒目標樹）不算本閘擋。"""
    tp = tp or _transcript(w, "先看看")
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": tool, "tool_input": tool_input, "session_id": SID,
                                 "cwd": str(w["proj"]), "transcript_path": tp}, config or {})
    out = w["outputs"][-1] or {}
    return out.get("hookSpecificOutput", {}).get("permissionDecisionReason", "") or ""


def _ot(reason):
    return "✗ (ot) OLD_TEST_CHANGE_NEEDS_DECLARATION" in reason


def _pass(reason):
    """本閘放行：既沒照規則擋，也不是閘自己炸的「判不了一律擋」（別的閘擋不算本閘）。"""
    return not _ot(reason) and "[Guardian:OldTestDeclare]" not in reason


def _events(w):
    p = w["logs"] / "guard-old_test.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def _put(w, rel, text):
    p = w["proj"] / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return str(p)


def _real(w, rel, tool_input):
    """真實 tool_input 原樣，只換 file_path。"""
    return {**tool_input, "file_path": str(w["proj"] / rel)}


def _apply(path, ti):
    """模擬工具放行後真的寫進去（PreToolUse 只判、不寫）。"""
    p = Path(path)
    if "content" in ti:
        p.write_text(ti["content"], encoding="utf-8")
    else:
        p.write_text(p.read_text(encoding="utf-8").replace(ti["old_string"], ti["new_string"], 1), encoding="utf-8")


def _assert_is_test_file_with_tests(path, src):
    import wg_oldtest as ot
    assert ot.is_test_file(path, {}, None), "前置：這是測試檔"
    assert ot.extract_tests(src, path), "前置：抽得到測試函式"


def test_snapshot_write_has_newline_control():
    """寫改前快照的 write_text 要帶 newline=（verify_lf_writes 規則：Windows 文字模式會把 \\n 翻成 \\r\\n）。
    快照是單行 JSON、位元組上看不出差別，所以用同一套 AST 規則只掃 wg_oldtest.py。"""
    sys.path.insert(0, str(HOOKS_DIR / "verify"))
    import verify_lf_writes as lf
    src = (HOOKS_DIR / "wg_oldtest.py").read_text(encoding="utf-8")
    assert ".write_text(" in src, "前置：wg_oldtest.py 真的有文字模式寫檔"
    assert lf.check_file(HOOKS_DIR / "wg_oldtest.py") == []


RENAME_EDIT_OLD = "def test_legacy_report_keeps_columns():\n    rows = adjust.report()"
RENAME_EDIT_NEW = "def test_legacy_report_v2():\n    rows = adjust.report()"
DECL = "改舊測試｜test_legacy_report_keeps_columns：使用者第 3 回合說舊報表欄位改成新格式，舊斷言的欄位順序已不成立"


def test_rename_without_declaration_denied(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    r = _run(world, "Edit", {"file_path": fp, "old_string": RENAME_EDIT_OLD, "new_string": RENAME_EDIT_NEW})
    assert _ot(r), r
    assert "改名" in r and "test_legacy_report_keeps_columns" in r and "test_legacy_report_v2" in r
    assert "改舊測試｜test_legacy_report_keeps_columns：<" in r and "AskUserQuestion" in r and "`#` 註解" in r
    assert [e["event"] for e in _events(world)] == ["denied"]


@pytest.mark.parametrize("hook_gives", ["main", "agent"])
def test_subagent_declaration_in_its_own_transcript_counts(world, hook_gives):
    """子代理改舊測試、宣告寫在自己的回覆：對話在 <sid>/subagents/agent-<id>.jsonl，hook 給主檔或子代理檔都要認得到。"""
    agent_id = "ae3c716a6fc9ec36b"
    main = Path(_transcript(world, "主 session：派子代理改報表測試", name=f"{SID}.jsonl"))
    agent = main.with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"
    agent.parent.mkdir(parents=True)
    agent.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": DECL}]}},
                                ensure_ascii=False) + "\n", encoding="utf-8")
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": "Edit", "session_id": SID, "agent_id": agent_id, "cwd": str(world["proj"]),
                                 "transcript_path": str(main if hook_gives == "main" else agent),
                                 "tool_input": {"file_path": fp, "old_string": RENAME_EDIT_OLD, "new_string": RENAME_EDIT_NEW}}, {})
    r = (world["outputs"][-1] or {}).get("hookSpecificOutput", {}).get("permissionDecisionReason", "") or ""
    assert _pass(r), r
    assert _events(world)[-1]["event"] == "declared"


def test_rename_with_declaration_allowed_logged_and_same_test_not_blocked_again(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    ti = {"file_path": fp, "old_string": RENAME_EDIT_OLD, "new_string": RENAME_EDIT_NEW}
    assert _pass(_run(world, "Edit", ti, _transcript(world, "說明一下", DECL)))
    ev = _events(world)
    assert ev[-1]["event"] == "declared" and ev[-1]["test"] == "test_legacy_report_keeps_columns"
    assert "欄位順序已不成立" in ev[-1]["reason"]
    _apply(fp, ti)
    # 第二次動同一支（已改名成 v2）：transcript 換新、沒有宣告行，也不擋（宣告記在 state）
    r = _run(world, "Edit", {"file_path": fp, "old_string": '    assert rows[0] == "USD"', "new_string": '    assert rows[0] == "TWD"'},
             _transcript(world, "再改", name="t2.jsonl"))
    assert _pass(r), r
    assert _events(world)[-1]["event"] == "exempt" and _events(world)[-1]["why"] == "declared_before"


@pytest.mark.parametrize("decl", ["改舊測試｜test_legacy_report_keeps_columns：", "改舊測試｜test_legacy_report_keeps_columns：。。",
                                  "改舊測試｜test_legacy_report_keeps_columns：<為什麼舊斷言不再對；使用者原話>",
                                  "改舊測試｜test_other：使用者說要改"])
def test_declaration_blank_placeholder_or_wrong_name_still_denied(world, decl):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    r = _run(world, "Edit", {"file_path": fp, "old_string": RENAME_EDIT_OLD, "new_string": RENAME_EDIT_NEW}, _transcript(world, decl))
    assert _ot(r), decl


def test_declaration_in_tool_input_channel_counts(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    tp = world["tmp"] / "tool.jsonl"
    tp.write_text(json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": f"# {DECL}\necho ok"}}]}}, ensure_ascii=False) + "\n", encoding="utf-8")
    assert _pass(_run(world, "Edit", {"file_path": fp, "old_string": RENAME_EDIT_OLD, "new_string": RENAME_EDIT_NEW}, str(tp)))


def test_append_new_test_not_triggered(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _assert_is_test_file_with_tests(fp, LEGACY)
    r = _run(world, "Edit", {"file_path": fp, "old_string": "    assert adjust.total() == 10\n",
                             "new_string": "    assert adjust.total() == 10\n\n\ndef test_new_case():\n    assert adjust.total() > 0\n"})
    assert _pass(r) and not _events(world)


def test_assert_changed_denied(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    r = _run(world, "Edit", {"file_path": fp, "old_string": 'assert rows[0] == "USD"', "new_string": 'assert rows[0] == "TWD"'})
    assert _ot(r) and "斷言變了" in r and "test_legacy_report_keeps_columns" in r


def test_only_adding_assert_not_triggered(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _assert_is_test_file_with_tests(fp, LEGACY)
    r = _run(world, "Edit", {"file_path": fp, "old_string": "    assert len(rows) == 3\n",
                             "new_string": "    assert len(rows) == 3\n    assert rows[1] == \"EUR\"\n"})
    assert _pass(r)


def test_skip_on_existing_denied_but_new_test_with_skip_not(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    r = _run(world, "Edit", {"file_path": fp, "old_string": "def test_legacy_report_totals():",
                             "new_string": "@pytest.mark.skip(reason=\"之後再修\")\ndef test_legacy_report_totals():"})
    assert _ot(r) and "加 skip" in r and "test_legacy_report_totals" in r
    r = _run(world, "Edit", {"file_path": fp, "old_string": "    assert adjust.total() == 10\n",
                             "new_string": "    assert adjust.total() == 10\n\n\n@pytest.mark.skip(reason=\"未實作\")\ndef test_future():\n    pass\n"})
    assert _pass(r)


def test_write_overwrite_drops_one_of_three_denied(world):
    three = LEGACY + "\n\ndef test_third():\n    assert adjust.total() >= 0\n"
    fp = _put(world, "tests/test_legacy_report.py", three)
    two = three.replace("\n\ndef test_legacy_report_totals():\n    assert adjust.total() == 10\n", "")
    r = _run(world, "Write", {"file_path": fp, "content": two})
    assert _ot(r) and "test_legacy_report_totals（消失）" in r
    assert "test_third" not in r and "test_legacy_report_keeps_columns" not in r


def test_fixture_or_helper_change_not_triggered(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _assert_is_test_file_with_tests(fp, LEGACY)
    r = _run(world, "Edit", {"file_path": fp, "old_string": "def setup_function():\n    adjust.LEVELS.clear()",
                             "new_string": "def setup_function():\n    adjust.LEVELS.clear()\n    adjust.LEVELS['A'] = 0"})
    assert _pass(r)


def test_non_test_file_not_triggered(world):
    fp = _put(world, "src/x.py", LEGACY)
    import wg_oldtest as ot
    assert not ot.is_test_file(fp, {}, str(world["proj"])) and ot.extract_tests(LEGACY, fp), "前置：有測試函式但不是測試檔"
    r = _run(world, "Edit", {"file_path": fp, "old_string": 'assert rows[0] == "USD"', "new_string": 'assert rows[0] == "TWD"'})
    assert _pass(r)


def test_disabled_not_triggered(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    ti = {"file_path": fp, "old_string": 'assert rows[0] == "USD"', "new_string": 'assert rows[0] == "TWD"'}
    assert _ot(_run(world, "Edit", ti)), "前置：開著會擋"
    assert _pass(_run(world, "Edit", ti, config={"guard": {"old_test_declare": {"enabled": False}}}))


def test_js_gone_and_skip_detected(world):
    src = 'describe("r", () => {\n  it("keeps columns", () => { expect(1).toBe(1) })\n  test("totals", () => {})\n})\n'
    fp = _put(world, "src/report.test.js", src)
    assert _ot(_run(world, "Write", {"file_path": fp, "content": src.replace('  test("totals", () => {})\n', "")}))
    assert _ot(_run(world, "Write", {"file_path": fp, "content": src.replace('it("keeps', 'it.skip("keeps')}))
    assert _pass(_run(world, "Write", {"file_path": fp, "content": src + 'it("new one", () => {})\n'}))


def test_csharp_gone_and_ignore_detected(world):
    src = "public class ReportTests\n{\n    [Test]\n    public void KeepsColumns()\n    {\n    }\n\n    [Test]\n    public void Totals()\n    {\n    }\n}\n"
    fp = _put(world, "Game/ReportTests.cs", src)
    assert _ot(_run(world, "Write", {"file_path": fp, "content": src.replace("public void Totals()", "public void Helper()")
                                     .replace("    [Test]\n    public void Helper", "    public void Helper")}))
    assert _ot(_run(world, "Write", {"file_path": fp, "content": src.replace("[Test]\n    public void Totals", "[Test, Ignore(\"x\")]\n    public void Totals")}))


# ─── codex 一輪抓到的漏擋（BLOCK）與誤擋（WARN）───

def test_js_assert_change_denied(world):
    src = 'it("total", () => {\n  expect(total()).toBe(10)\n})\nit("one", () => { expect(one()).toBe(1) })\n'
    fp = _put(world, "src/report.test.js", src)
    assert _ot(_run(world, "Write", {"file_path": fp, "content": src.replace("toBe(10)", "toBe(0)")}))
    assert _ot(_run(world, "Write", {"file_path": fp, "content": src.replace("toBe(1)", "toBe(2)")})), "單行 it 的斷言在開頭行上"
    chained = 'it("total", () => {\n  expect(total())\n    .toBe(10)\n})\n'
    fp2 = _put(world, "src/chain.test.js", chained)
    assert _ot(_run(world, "Write", {"file_path": fp2, "content": chained.replace("toBe(10)", "toBe(0)")})), "點開頭的續行"


def test_csharp_and_java_assert_change_denied(world):
    cs = "public class RTests\n{\n    [Test]\n    public void Totals()\n    {\n        Assert.AreEqual(10, Total());\n    }\n}\n"
    fp = _put(world, "Game/RTests.cs", cs)
    assert _ot(_run(world, "Write", {"file_path": fp, "content": cs.replace("10,", "0,")}))
    java = "class RTest {\n    @Test\n    void totals() {\n        assertEquals(10, total());\n    }\n}\n"
    fp = _put(world, "src/RTest.java", java)
    assert _ot(_run(world, "Write", {"file_path": fp, "content": java.replace("10,", "0,")}))


@pytest.mark.parametrize("old,new", [
    ("def test_total():\n    assert (\n        total() == 10\n    )\n", "def test_total():\n    assert (\n        total() == 0\n    )\n"),
    ("def test_total(): assert total() == 10\n", "def test_total(): assert total() == 0\n"),
    ('def test_label():\n    assert label == "a b"\n', 'def test_label():\n    assert label == "ab"\n'),
])
def test_python_multiline_inline_and_string_space_assert_change_denied(world, old, new):
    fp = _put(world, "tests/test_x.py", old)
    assert _ot(_run(world, "Write", {"file_path": fp, "content": new}))


def test_multiline_skipif_and_describe_skip_denied(world):
    src = "def test_total():\n    assert total() == 10\n"
    fp = _put(world, "tests/test_x.py", src)
    deco = '@pytest.mark.skipif(\n    sys.platform == "win32",\n    reason="之後再說",\n)\n'
    assert _ot(_run(world, "Write", {"file_path": fp, "content": deco + src}))
    cls = "class TestR:\n    def test_total(self):\n        assert total() == 10\n"
    fp = _put(world, "tests/test_cls.py", cls)
    assert _ot(_run(world, "Write", {"file_path": fp, "content": "@pytest.mark.skip\n" + cls})), "整個類別標 skip"
    assert _ot(_run(world, "Write", {"file_path": fp, "content": "pytestmark = pytest.mark.skip\n" + cls})), "整個模組標 skip"
    js = 'describe("report", () => {\n  it("total", () => {})\n})\n'
    fp = _put(world, "src/r.test.js", js)
    r = _run(world, "Write", {"file_path": fp, "content": js.replace("describe(", "describe.skip(")})
    assert _ot(r) and "describe:report（加 skip）" in r


def test_declaration_naming_other_file_or_class_does_not_cover(world):
    src = "class TestB:\n    def test_total(self):\n        assert total() == 10\n"
    fp = _put(world, "tests/test_b.py", src)
    ti = {"file_path": fp, "content": src.replace("== 10", "== 0")}
    for decl in ("改舊測試｜tests/test_a.py:TestB.test_total：調整 A 契約", "改舊測試｜TestA.test_total：調整 A 契約"):
        assert _ot(_run(world, "Write", ti, _transcript(world, decl))), decl
    assert _pass(_run(world, "Write", ti, _transcript(world, "改舊測試｜tests/test_b.py::TestB::test_total：使用者說總數改成 0")))


def test_rename_declared_only_by_new_name_still_denied(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    r = _run(world, "Edit", {"file_path": fp, "old_string": RENAME_EDIT_OLD, "new_string": RENAME_EDIT_NEW},
             _transcript(world, "改舊測試｜test_legacy_report_v2：新測試"))
    assert _ot(r) and "test_legacy_report_keeps_columns（改名" in r


def test_unreadable_existing_test_file_denied(world, monkeypatch):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    real = Path.read_text

    def _locked(self, *a, **k):
        if str(self) == fp:
            raise PermissionError("locked")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", _locked)
    r = _run(world, "Write", {"file_path": fp, "content": "def test_other():\n    pass\n"})
    assert "[Guardian:OldTestDeclare]" in r and "PermissionError" in r


def test_comment_only_change_with_quote_not_triggered(world):
    src = "def test_v():\n    assert value == 1  # user's expectation\n"
    fp = _put(world, "tests/test_v.py", src)
    _assert_is_test_file_with_tests(fp, src)
    assert _pass(_run(world, "Write", {"file_path": fp, "content": src.replace("expectation", "requirement")}))


# ─── Bash／PowerShell／NotebookEdit 事後比對（派工 002）與「說明變了」 ───

def _post(w, tool, tool_input, tp=None):
    """跑一次 PostToolUse（工具已經寫完磁碟）。"""
    with pytest.raises(SystemExit):
        pt.handle_post_tool_use({"tool_name": tool, "tool_input": tool_input, "session_id": SID, "cwd": str(w["proj"]),
                                 "transcript_path": tp or _transcript(w, "做完了"), "tool_response": {"stdout": "", "stderr": ""}},
                                {"docdrift": {"enabled": False}})


def _pending():
    return (wg_core.read_state(SID) or {}).get("old_test_undeclared") or []


def _bash_round(w, tool, cmd, fp, new_text, tp=None):
    """PreToolUse（拍快照）→ 模擬指令寫進磁碟 → PostToolUse（比對）。"""
    ti = {"command": cmd}
    assert _pass(_run(w, tool, ti, tp)), "寫的這一次本閘不擋（看不到改後內容）"
    Path(fp).write_text(new_text, encoding="utf-8")
    _post(w, tool, ti, tp)


def test_bash_sed_assert_change_blocks_next_call_until_declared(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    fwd = fp.replace("\\", "/")
    _bash_round(world, "Bash", f"sed -i 's/\"USD\"/\"TWD\"/' '{fwd}'", fp, LEGACY.replace('"USD"', '"TWD"'))
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_keeps_columns", "assert")]
    r = _run(world, "Bash", {"command": "echo next"})
    assert _ot(r) and "test_legacy_report_keeps_columns（斷言變了" in r and "這是 Bash 改的" in r
    other = _put(world, "src/a.py", "x = 1\n")
    assert _ot(_run(world, "Edit", {"file_path": other, "old_string": "x = 1", "new_string": "x = 2"})), "任何寫入工具都擋"
    r = _run(world, "Bash", {"command": "echo next"}, _transcript(world, DECL))
    assert _pass(r) and not _pending()
    assert any(e["event"] == "declared_late" and e["test"] == "test_legacy_report_keeps_columns" for e in _events(world))


def test_bash_declared_in_same_command_comment_not_pending(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    fwd = fp.replace("\\", "/")
    _bash_round(world, "Bash", f"# {DECL}\nsed -i 's/\"USD\"/\"TWD\"/' '{fwd}'", fp, LEGACY.replace('"USD"', '"TWD"'))
    assert not _pending() and any(e["event"] == "declared" for e in _events(world))


def test_powershell_set_content_dropping_test_blocks_next_call(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    dropped = LEGACY.replace("\n\ndef test_legacy_report_totals():\n    assert adjust.total() == 10\n", "")
    _bash_round(world, "PowerShell", f"Set-Content -Path '{fp}' -Value 'x' -Encoding utf8", fp, dropped)
    r = _run(world, "PowerShell", {"command": "Write-Output next"})
    assert _ot(r) and "test_legacy_report_totals（消失）" in r and "這是 PowerShell 改的" in r


def test_bash_only_appending_new_test_not_pending(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    fwd = fp.replace("\\", "/")
    _bash_round(world, "Bash", f"echo 'def test_new(): pass' >> '{fwd}'", fp, LEGACY + "\n\ndef test_new(): pass\n")
    assert not _pending()
    assert any(k.endswith("|test_new") for k in wg_core.read_state(SID).get("old_test_added", [])), "前置：快照有拍到、比對有跑"


# 第二波 A′ 實跑：transcript:161 用 `cat >> tests/test_cli.py <<'EOF'` 加新測試，同一條指令的 pytest 紅了（exit 1、is_error）→
# Claude Code 不送 PostToolUse，old_test_added 沒記到；transcript:173 再 sed 改它的期望值，被當成改舊測試擋（guard-old_test:1～3）。
CLI_TESTS = '''from pricing import cli


def test_cli_prints_twd(capsys):
    assert cli.main(["A100", "3"]) == 0
    assert capsys.readouterr().out.strip() == "A100 x3 = NT$360"
'''
CLI_NEW = '''

def test_cli_plain_prints_two_decimals_no_currency(capsys):
    assert cli.main(["B200", "1000", "--tier", "silver", "--plain"]) == 0
    assert capsys.readouterr().out.strip() == "B200 x1000 = 40950.00"
'''


def _failed_bash_append(w):
    """PreToolUse 放行 → 指令寫進磁碟但失敗收場（不跑 PostToolUse）。回測試檔路徑。追加用 `cat 檔 >> 目標`（不是 heredoc）：
    heredoc 的改後內容寫前就算得出、新加的測試在 PreToolUse 就記到；這裡要守的是算不出內容時靠基線認新測試那條路。"""
    fp = _put(w, "tests/test_cli.py", CLI_TESTS)
    fwd = fp.replace("\\", "/")
    src = (w["tmp"] / "new_test.txt").as_posix()
    assert _pass(_run(w, "Bash", {"command": f"cat '{src}' >> '{fwd}'\npython -m pytest tests -q"}))
    Path(fp).write_text(CLI_TESTS + CLI_NEW, encoding="utf-8")
    return fp


def test_new_test_from_failed_bash_then_assert_fixed_not_pending(world):
    """基線＝本 session 第一次碰這個檔時的測試名；基線沒有的那支改斷言不算改舊測試。"""
    fp = _failed_bash_append(world)
    fwd = fp.replace("\\", "/")
    _bash_round(world, "Bash", f"sed -i 's/40950.00/36855.00/' '{fwd}'", fp,
                CLI_TESTS + CLI_NEW.replace("40950.00", "36855.00"))
    assert not wg_core.read_state(SID).get("old_test_added"), "前置：新加那支沒記進 old_test_added（重現 A-1）"
    assert any(e["event"] == "exempt" and e["test"] == "test_cli_plain_prints_two_decimals_no_currency"
               and e["why"] == "not_in_baseline" for e in _events(world)), "前置：比對有看到斷言變了"
    assert not _pending()
    assert _pass(_run(world, "Bash", {"command": "echo next"}))


def test_baseline_test_changed_after_failed_bash_still_pending(world):
    fp = _failed_bash_append(world)
    fwd = fp.replace("\\", "/")
    _bash_round(world, "Bash", f"sed -i 's/NT$360/NT$999/' '{fwd}'", fp, (CLI_TESTS + CLI_NEW).replace("NT$360", "NT$999"))
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_cli_prints_twd", "assert")]
    assert _ot(_run(world, "Bash", {"command": "echo next"}))


def test_baseline_includes_head_tests_of_file_deleted_before_session(world):
    """Codex：session 開始前 tests 檔已是未提交的刪除，跑 python 時快照記成「不存在」；之後使用者還原檔案、AI 再改既有斷言
    → 仍是舊測試照擋（基線併入 git HEAD 的測試名，不是空）。"""
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _git_repo(world["proj"])
    Path(fp).unlink()
    assert _pass(_run(world, "Bash", {"command": "python tools/report.py"}))
    _post(world, "Bash", {"command": "python tools/report.py"})
    import wg_release_rules as rr
    base = wg_core.read_state(SID).get("old_test_baseline", {}).get(rr.canon_path(fp))
    assert base is not None and "test_legacy_report_keeps_columns" in base, "前置：刪掉的檔有記到基線、而且帶 HEAD 的測試名"
    Path(fp).write_text(LEGACY, encoding="utf-8")                                       # 使用者還原
    fwd = fp.replace("\\", "/")
    _bash_round(world, "Bash", f"sed -i 's/\"USD\"/\"TWD\"/' '{fwd}'", fp, LEGACY.replace('"USD"', '"TWD"'))
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_keeps_columns", "assert")]


def test_write_restoring_deleted_old_test_file_is_not_session_added(world):
    """Codex 複審：session 前被刪（未提交）的舊測試檔用 Write 還原，還原出來的測試不算本 session 新加的；之後改斷言照擋。"""
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _git_repo(world["proj"])
    Path(fp).unlink()
    restore = {"file_path": fp, "content": LEGACY}
    assert _pass(_run(world, "Write", restore)), "還原本身不擋（沒有動到既有測試）"
    _apply(fp, restore)
    assert not any(k.endswith("|test_legacy_report_keeps_columns") for k in wg_core.read_state(SID).get("old_test_added", []))
    ti = {"file_path": fp, "old_string": '"USD"', "new_string": '"TWD"'}
    assert _ot(_run(world, "Edit", ti))


def test_head_lookup_failure_is_loud_and_falls_back_to_disk(world, monkeypatch, capsys):
    """HEAD 查詢真的失敗（不是 HEAD 沒有這個檔）→ stderr＋留帳 baseline_head_error，基線退回只看磁碟。"""
    import subprocess
    import wg_oldtest as ot
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _git_repo(world["proj"])
    monkeypatch.setattr(ot, "_git", lambda *a, **k: subprocess.CompletedProcess(a, 128, b"", b"fatal: unable to read 1a2b3c"))
    assert ot._head_tests(fp) == set()
    assert "基線查不到 git HEAD" in capsys.readouterr().err
    assert any(e["event"] == "baseline_head_error" for e in _events(world))
    monkeypatch.setattr(ot, "_git", lambda *a, **k: subprocess.CompletedProcess(
        a, 128, b"", b"fatal: path 'tests/x.py' does not exist in 'HEAD'"))
    assert ot._head_tests(fp) == set() and "基線查不到" not in capsys.readouterr().err   # HEAD 本來就沒有：安靜回空


THREE = '''from shop import pricing


def test_checkout_adds_shipping():
    assert pricing.total(500) == 560


def test_shipping_fee_below_threshold():
    assert pricing.fee(999) == 60


def test_free_shipping_at_threshold():
    assert pricing.fee(1000) == 0
'''


def test_one_line_declaring_three_tests_each_with_reason_covers_all(world):
    """第二波 C′（guard-old_test 15:57:59）：擋訊息教「多支用、分隔」，AI 寫成「名1：理由1、名2：理由2；名3：理由3」，
    舊解析在第一個「：」就切，只認到第一支，另兩支又被擋。"""
    fp = _put(world, "tests/test_pricing.py", THREE)
    new = THREE.replace("== 560", "== 554").replace("fee(999)", "fee(1199)").replace("fee(1000)", "fee(1200)")
    decl = ("改舊測試｜test_checkout_adds_shipping：使用者要「回傳多一個 discount 欄位」，總額改了、"
            "test_shipping_fee_below_threshold：使用者說「門檻從 1000 調成 1200」；test_free_shipping_at_threshold：同一句，門檻值改 1200")
    r = _run(world, "Write", {"file_path": fp, "content": new}, _transcript(world, decl))
    assert _pass(r), r
    declared = {e["test"] for e in _events(world) if e["event"] == "declared"}
    assert declared == {"test_checkout_adds_shipping", "test_shipping_fee_below_threshold", "test_free_shipping_at_threshold"}


def test_names_then_one_reason_and_mixed_form_parse():
    import wg_release_rules as rr
    (d,) = rr.parse_old_test_declarations("改舊測試｜test_a、test_b；test_c：三支都因為門檻改了")
    assert {"test_a", "test_b", "test_c"} <= set(d["names"]) and d["reason"] == "三支都因為門檻改了"
    a, c = rr.parse_old_test_declarations("改舊測試｜test_a、tests/test_x.py:test_b：理由一、test_c：理由二")
    assert {"test_a", "tests/test_x.py:test_b"} <= set(a["names"]) and a["reason"] == "理由一"
    assert c["names"] == ["test_c"] and c["reason"] == "理由二"
    (one,) = rr.parse_old_test_declarations("改舊測試｜test_a：理由裡提到 ERP 合約、說明多一點")
    assert one["names"][0] == "test_a" and one["reason"] == "理由裡提到 ERP 合約、說明多一點"   # 只有一段：照舊整句是理由


# 第二波 C′（C5）：AI 用 Bash heredoc 把改過斷言的兩支舊測試整檔寫回，寫進檔後才被要求補宣告（declared_late）。
# heredoc 的內容就是改後內容 → PreToolUse 先比對，沒宣告就在寫之前擋（與 Edit／Write 同款訊息）。

def test_bash_heredoc_overwriting_old_test_denied_before_write(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    new = LEGACY.replace('"USD"', '"TWD"')
    cmd = f"cd '{world['proj'].as_posix()}' && cat > tests/test_legacy_report.py <<'EOF'\n{new}EOF\npython -m pytest -q"
    r = _run(world, "Bash", {"command": cmd})
    assert _ot(r) and "test_legacy_report_keeps_columns（斷言變了" in r
    assert Path(fp).read_text(encoding="utf-8") == LEGACY and not _pending()           # 前置：還沒寫、也不是事後欠帳


def test_bash_heredoc_with_declaration_in_command_allowed(world):
    _put(world, "tests/test_legacy_report.py", LEGACY)
    new = LEGACY.replace('"USD"', '"TWD"')
    cmd = (f"# {DECL}\ncd '{world['proj'].as_posix()}' && cat > tests/test_legacy_report.py <<'EOF'\n{new}EOF\n")
    assert _pass(_run(world, "Bash", {"command": cmd}))
    assert any(e["event"] == "declared" and e["test"] == "test_legacy_report_keeps_columns" for e in _events(world))


def test_bash_heredoc_new_test_file_or_append_not_denied(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    proj = world["proj"].as_posix()
    new_file = f"cat > '{proj}/tests/test_brand_new.py' <<'EOF'\ndef test_new():\n    assert 1 == 1\nEOF\n"
    assert _pass(_run(world, "Bash", {"command": new_file}))                         # 新測試檔：沒有舊測試可動
    append = f"cat >> '{proj}/tests/test_legacy_report.py' <<'EOF'\n\n\ndef test_more():\n    assert 2 == 2\nEOF\n"
    assert _pass(_run(world, "Bash", {"command": append}))                           # 只加新測試（A-1 那種）不擋
    assert Path(fp).read_text(encoding="utf-8") == LEGACY


def test_heredoc_writes_parses_only_what_it_can_predict(tmp_path):
    """heredoc_writes 單元：算得出的才算（Codex 複審四條＋新路徑真的有跑）。"""
    import wg_oldtest as ot
    a = tmp_path / "tests" / "test_a.py"
    a.parent.mkdir()
    a.write_text("def test_x():\n    assert 1 == 1\n", encoding="utf-8")
    t = [str(a)]
    assert ot.heredoc_writes("cat > tests/test_a.py <<'EOF'\ndef test_x():\n    assert 1 == 2\nEOF\n", t) == \
        {str(a): "def test_x():\n    assert 1 == 2\n"}                                          # 覆寫＝內容
    assert ot.heredoc_writes("cat >> tests/test_a.py <<'EOF'\ndef test_y():\n    pass\nEOF\n", t) == \
        {str(a): "def test_x():\n    assert 1 == 1\ndef test_y():\n    pass\n"}                 # 追加＝原檔＋內容
    assert ot.heredoc_writes("cat > tests/test_a.py <<A <<B\nx\nA\ny\nB\n", t) == {}             # 一行兩個 heredoc：不預測
    assert ot.heredoc_writes("cat > tests/test_a.py <<EOF\n$content\nEOF\n", t) == {}            # 沒加引號又會展開：不預測
    fake = ("cat <<'DOC'\ncat > tests/test_a.py <<'EOF'\nassert 0\nEOF\nDOC\n"
            "cat >> tests/test_a.py <<'EOF'\n# note\nEOF\n")
    assert ot.heredoc_writes(fake, t) == {str(a): "def test_x():\n    assert 1 == 1\n# note\n"}   # 別段 heredoc 內文裡的字樣不是指令
    tabbed = "cat > tests/test_a.py <<-'EOF'\n\tdef test_x():\n  EOF\n\t    assert 1 == 2\n\tEOF\n"
    assert ot.heredoc_writes(tabbed, t) == {str(a): "def test_x():\n  EOF\n    assert 1 == 2\n"}   # <<- 只去 tab；空白縮排的 EOF 不是結束


def test_bash_heredoc_batch_with_one_denied_records_nothing(world):
    """Codex：同一條指令寫兩個測試檔、一個被擋 → 整條不會執行，另一個的新加測試也不先記。"""
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    other = _put(world, "tests/test_other.py", "def test_o():\n    assert 1\n")
    proj = world["proj"].as_posix()
    cmd = (f"cat > '{proj}/tests/test_legacy_report.py' <<'EOF'\n{LEGACY.replace(chr(34) + 'USD' + chr(34), chr(34) + 'TWD' + chr(34))}EOF\n"
           f"cat >> '{proj}/tests/test_other.py' <<'EOF'\ndef test_more():\n    assert 2\nEOF\n")
    assert _ot(_run(world, "Bash", {"command": cmd}))
    assert not wg_core.read_state(SID).get("old_test_added") and Path(other).exists() and Path(fp).exists()


def test_reason_with_ascii_label_and_colon_stays_one_declaration():
    import wg_release_rules as rr
    (d,) = rr.parse_old_test_declarations("改舊測試｜test_a：使用者要改成含稅；ERP：要等對方確認欄位")
    assert d["names"][0] == "test_a" and d["reason"] == "使用者要改成含稅；ERP：要等對方確認欄位"   # 理由裡的標籤字不拆成假名字（Codex）


def test_revert_after_bash_clears_pending(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    fwd = fp.replace("\\", "/")
    _bash_round(world, "Bash", f"sed -i 's/\"USD\"/\"TWD\"/' '{fwd}'", fp, LEGACY.replace('"USD"', '"TWD"'))
    assert _pending()
    ti = {"file_path": fp, "old_string": '"TWD"', "new_string": '"USD"'}
    assert _pass(_run(world, "Edit", ti)), "只改欠帳那個檔（撤回）不擋"
    _apply(fp, ti)
    _post(world, "Edit", ti)
    assert not _pending() and any(e["event"] == "reverted" for e in _events(world))
    assert _pass(_run(world, "Bash", {"command": "echo next"}))


def _git_repo(proj):
    """把假專案變成有一個基底 commit 的 git repo（python 腳本那條路靠 git status／HEAD 判改前）。"""
    import subprocess
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"], ["config", "core.autocrlf", "false"],
                 ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(["git", "-C", str(proj), *args], check=True, capture_output=True)


def test_python_script_changing_committed_test_blocks_next_call(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _git_repo(world["proj"])
    _bash_round(world, "Bash", "python fix_report.py", fp, LEGACY.replace('"USD"', '"TWD"'))
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_keeps_columns", "assert")]
    r = _run(world, "Bash", {"command": "echo next"})
    assert _ot(r) and "test_legacy_report_keeps_columns（斷言變了" in r and "這是 Bash 改的" in r


def test_python_script_does_not_count_changes_that_were_already_uncommitted(world):
    """執行 python 前就有的改動（使用者自己沒 commit 的）不算這次的：只點名 python 跑完才變的那支。"""
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _git_repo(world["proj"])
    before = LEGACY.replace("== 10", "== 11")
    Path(fp).write_text(before, encoding="utf-8")
    _bash_round(world, "PowerShell", "python -X utf8 fix_report.py", fp, before.replace('"USD"', '"TWD"'))
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_keeps_columns", "assert")]


def test_non_python_command_takes_no_git_snapshot(world):
    _put(world, "tests/test_legacy_report.py", LEGACY)
    _git_repo(world["proj"])
    assert _pass(_run(world, "Bash", {"command": "echo hi"}))
    snap_dir = world["tmp"] / "wf" / "old-test-snap"
    assert not snap_dir.exists() or not list(snap_dir.iterdir()), "不執行 python、沒寫測試檔的指令不拍快照、不跑 git"


# ─── git 指令（merge／pull／rebase／切分支）帶進來的別軌改動不算本 session 改的（派工 003） ───

def _g(proj, *args, check=True):
    import subprocess
    r = subprocess.run(["git", "-C", str(proj), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert not check or r.returncode == 0, r.stdout + r.stderr
    return r


OTHER = LEGACY.replace('"USD"', '"TWD"') + "\n\ndef test_from_other():\n    assert adjust.total() > 0\n"


def _other_track(w, conflict):
    """base：tests/test_legacy_report.py（LEGACY）＋ TECH.md。分支 other 改了舊測試的斷言、加一支 test_from_other；
    conflict=True 時這邊也改 TECH.md 同一行 → merge other 停在 TECH.md 衝突、測試檔已自動合好放在暫存區（002 合 main 實遇）；
    False → merge other 是快轉。"""
    fp = _put(w, "tests/test_legacy_report.py", LEGACY)
    _put(w, "TECH.md", "base\n")
    proj = w["proj"]
    _git_repo(proj)
    _g(proj, "checkout", "-qb", "other")
    Path(fp).write_text(OTHER, encoding="utf-8")
    _put(w, "TECH.md", "other\n")
    _g(proj, "commit", "-qam", "other track")
    _g(proj, "checkout", "-q", "-")
    if conflict:
        _put(w, "TECH.md", "mine\n")
        _g(proj, "commit", "-qam", "this track")
    return fp


def _py_round(w, label, action):
    """一條經 python 啟動器跑的指令：PreToolUse 拍快照 → action()（這條指令實際做的事）→ PostToolUse 比對。回 action 的結果。"""
    ti = {"command": f"python _vcs_run.py {label}"}
    assert _pass(_run(w, "Bash", ti))
    out = action()
    _post(w, "Bash", ti)
    return out


def _merge_round(w, extra=None):
    """經 python 啟動器跑 git merge other（extra＝同一支腳本接著自己做的）。"""
    def act():
        r = _g(w["proj"], "merge", "-q", "other", "-m", "merge other", check=False)
        if extra:
            extra()
        return r
    return _py_round(w, "merge other", act)


def test_merge_stopped_on_conflict_does_not_count_incoming_test_changes(world):
    """merge 停在別的檔衝突，別軌改的測試已合進暫存區、HEAD 沒動：舊碼拿 HEAD 當改前，把別軌的斷言改動當成本 session
    改舊測試擋。git 合進來的那份（暫存區）才是改前。"""
    fp = _other_track(world, conflict=True)
    r = _merge_round(world)
    assert r.returncode != 0 and "CONFLICT" in r.stdout + r.stderr, "前置：merge 停在 TECH.md 衝突"
    assert Path(fp).read_text(encoding="utf-8") == OTHER, "前置：別軌的測試改動已合進工作樹"
    assert not _pending()
    assert any(e["event"] == "git_op" and any(f.endswith("test_legacy_report.py") for f in e["files"]) for e in _events(world))
    assert _pass(_run(world, "Bash", {"command": "echo next"}))


def test_squash_merge_does_not_count_incoming_test_changes(world):
    """merge --squash：別軌改動放進暫存區、HEAD 不動、git 目錄只留 SQUASH_MSG（沒有 MERGE_HEAD）→ 以訊息裡的 commit 重算 git 的產出。"""
    fp = _other_track(world, conflict=False)
    _py_round(world, "merge --squash other", lambda: _g(world["proj"], "merge", "-q", "--squash", "other"))
    assert Path(fp).read_text(encoding="utf-8") == OTHER and _g(world["proj"], "diff", "--cached", "--quiet", check=False).returncode, \
        "前置：別軌的測試改動在暫存區、還沒 commit"
    assert not _pending()


def test_merge_plus_own_edit_of_old_test_still_pending(world):
    """反例：同一支腳本 merge 完又自己改了舊測試的斷言 → 照算本 session 改的（只有 git 合進來的那份不算）。"""
    fp = _other_track(world, conflict=True)
    _merge_round(world, lambda: Path(fp).write_text(OTHER.replace("== 10", "== 11"), encoding="utf-8"))
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_totals", "assert")]


def test_merge_then_own_edit_and_add_of_old_test_still_pending(world):
    """Codex BLOCK 1：腳本 merge 停在衝突後改了舊測試、還 git add 了——暫存區與磁碟都是自己改的版本，git 的產出要從 commit
    重算（merge-tree），不能讀暫存區。"""
    fp = _other_track(world, conflict=True)

    def edit_and_add():
        Path(fp).write_text(OTHER.replace("== 10", "== 11"), encoding="utf-8")
        _g(world["proj"], "add", "tests/test_legacy_report.py")
    _merge_round(world, edit_and_add)
    assert _g(world["proj"], "diff", "--quiet", "--", "tests/test_legacy_report.py", check=False).returncode == 0, \
        "前置：工作樹與暫存區一樣（自己的改動已 add）"
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_totals", "assert")]


def test_merge_then_revert_incoming_assert_to_old_value_still_pending(world):
    """Codex 複審 BLOCK 1：merge 停在衝突後，腳本把別軌改的斷言改回執行前的值＝撤掉別軌對舊測試的改動，照要宣告。"""
    fp = _other_track(world, conflict=True)
    _merge_round(world, lambda: Path(fp).write_text(OTHER.replace('"TWD"', '"USD"'), encoding="utf-8"))
    assert '"USD"' in Path(fp).read_text(encoding="utf-8") and "test_from_other" in Path(fp).read_text(encoding="utf-8"), \
        "前置：斷言回到執行前的值、別軌其他改動還在"
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_keeps_columns", "assert")]


def test_conflict_in_test_file_then_own_edit_still_pending(world):
    """Codex BLOCK 1：衝突就在測試檔裡，腳本又改了同檔另一支舊測試的斷言（沒 add）→ 照擋那一支；衝突那支不算。"""
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    proj = world["proj"]
    _git_repo(proj)
    _g(proj, "checkout", "-qb", "other")
    Path(fp).write_text(LEGACY.replace("== 10", "== 20"), encoding="utf-8")
    _g(proj, "commit", "-qam", "other track")
    _g(proj, "checkout", "-q", "-")
    Path(fp).write_text(LEGACY.replace("== 10", "== 30"), encoding="utf-8")
    _g(proj, "commit", "-qam", "this track")
    _merge_round(world, lambda: Path(fp).write_text(Path(fp).read_text(encoding="utf-8").replace('"USD"', '"EUR"'),
                                                    encoding="utf-8"))
    assert "<<<<<<<" in Path(fp).read_text(encoding="utf-8"), "前置：衝突標記在測試檔裡"
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_keeps_columns", "assert")]


def test_cherry_pick_stopped_on_conflict_does_not_count_incoming_test_changes(world):
    """cherry-pick 停在別的檔衝突：git 的產出以被挑的 commit 的父代為共同祖先重算（merge-tree --merge-base）。"""
    fp = _other_track(world, conflict=True)
    r = _py_round(world, "cherry-pick other", lambda: _g(world["proj"], "cherry-pick", "other", check=False))
    assert r.returncode != 0 and Path(fp).read_text(encoding="utf-8") == OTHER, "前置：停在 TECH.md 衝突、測試改動已套進來"
    assert not _pending()


def test_rebase_continue_to_next_conflict_is_a_new_git_step(world):
    """Codex BLOCK 2：rebase --continue 停在下一個衝突，REBASE_HEAD 名稱不變、內容換成下一個 commit——那個 commit 套進來的
    測試改動是 git 重放的，不是這條指令寫的。"""
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _put(world, "TECH.md", "base\n")
    proj = world["proj"]
    _git_repo(proj)
    _g(proj, "checkout", "-qb", "other")
    _put(world, "TECH.md", "upstream\n")
    _g(proj, "commit", "-qam", "upstream")
    _g(proj, "checkout", "-q", "-")
    _put(world, "TECH.md", "a1\n")
    _g(proj, "commit", "-qam", "c1")
    _put(world, "TECH.md", "a2\n")
    Path(fp).write_text(LEGACY.replace("== 10", "== 12"), encoding="utf-8")
    _g(proj, "commit", "-qam", "c2")
    _py_round(world, "rebase other", lambda: _g(proj, "rebase", "other", check=False))
    _put(world, "TECH.md", "resolved\n")
    _g(proj, "add", "TECH.md")
    r = _py_round(world, "rebase --continue", lambda: _g(proj, "-c", "core.editor=true", "rebase", "--continue", check=False))
    assert r.returncode != 0 and "== 12" in Path(fp).read_text(encoding="utf-8"), "前置：停在 c2 的衝突、c2 的測試改動已套進來"
    assert not _pending()


def test_revert_of_old_test_change_is_own_change(world):
    """revert 不算 git 帶進來的：撤掉哪個 commit 是本 session 的決定，停在衝突時撤回來的斷言照算改舊測試。"""
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _put(world, "TECH.md", "base\n")
    proj = world["proj"]
    _git_repo(proj)
    Path(fp).write_text(LEGACY.replace("== 10", "== 15"), encoding="utf-8")
    _put(world, "TECH.md", "x\n")
    _g(proj, "commit", "-qam", "x")
    _put(world, "TECH.md", "y\n")
    _g(proj, "commit", "-qam", "y")
    r = _py_round(world, "revert HEAD~1", lambda: _g(proj, "revert", "--no-edit", "HEAD~1", check=False))
    assert r.returncode != 0 and "== 10" in Path(fp).read_text(encoding="utf-8"), "前置：停在 TECH.md 衝突、斷言已撤回"
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_totals", "assert")]


def test_fast_forward_then_commit_in_same_command_marks_incoming_tests_old(world):
    """Codex BLOCK 2：同一支腳本先快轉合進別軌、再 commit 別的檔——最後一筆 reflog 是 commit，但這段期間的 merge 照算帶進來。"""
    import wg_release_rules as rr
    fp = _other_track(world, conflict=False)
    assert _pass(_run(world, "Edit", {"file_path": fp, "old_string": "def setup_function():",
                                      "new_string": "def setup_function():  # 先看一眼"}))
    assert "test_from_other" not in wg_core.read_state(SID)["old_test_baseline"][rr.canon_path(fp)], "前置：基線是合併前的"

    def ff_then_commit():
        _g(world["proj"], "merge", "-q", "other")
        _put(world, "TECH.md", "after merge\n")
        _g(world["proj"], "commit", "-qam", "doc")
    _py_round(world, "merge other && commit", ff_then_commit)
    assert _g(world["proj"], "reflog", "-1", "--format=%gs").stdout.startswith("commit"), "前置：最後一筆 reflog 是 commit"
    r = _run(world, "Edit", {"file_path": fp, "old_string": "assert adjust.total() > 0", "new_string": "assert adjust.total() >= 0"})
    assert _ot(r) and "test_from_other" in r


def test_fast_forward_then_own_test_commit_with_dirty_helper_still_pending(world):
    """Codex 複審 BLOCK 2：快轉合進別軌後，自己改了舊測試的斷言並 commit，又在同檔留下 helper 的改動沒 commit——git 的產出是
    快轉的終點，不是最後的 HEAD，自己 commit 進去的斷言改動照算。"""
    fp = _other_track(world, conflict=False)

    def ff_then_own_commit():
        _g(world["proj"], "merge", "-q", "other")
        Path(fp).write_text(OTHER.replace("== 10", "== 99"), encoding="utf-8")
        _g(world["proj"], "commit", "-qam", "own test change")
        Path(fp).write_text(OTHER.replace("== 10", "== 99").replace("    adjust.LEVELS.clear()\n",
                                                                      "    adjust.LEVELS.clear()\n    adjust.RESET = True\n"),
                            encoding="utf-8")
    _py_round(world, "merge other && commit", ff_then_own_commit)
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_totals", "assert")]


def test_no_reflog_fast_forward_still_marks_incoming_tests_old(world):
    """Codex 複審 BLOCK 2：讀不到 reflog（logs/HEAD 不在）時 HEAD 動了分不出是誰動的——帶進來的照外來算、併基線（寧可多擋），
    並留帳說判不出。"""
    import shutil
    import wg_release_rules as rr
    fp = _other_track(world, conflict=False)
    _g(world["proj"], "config", "core.logAllRefUpdates", "false")
    shutil.rmtree(world["proj"] / ".git" / "logs")
    assert _pass(_run(world, "Edit", {"file_path": fp, "old_string": "def setup_function():",
                                      "new_string": "def setup_function():  # 先看一眼"}))
    assert "test_from_other" not in wg_core.read_state(SID)["old_test_baseline"][rr.canon_path(fp)], "前置：基線是合併前的"
    _py_round(world, "merge other", lambda: _g(world["proj"], "merge", "-q", "other"))
    assert not (world["proj"] / ".git" / "logs" / "HEAD").exists(), "前置：真的沒有 reflog"
    assert any(e["event"] == "git_op" and "reflog" in e.get("why", "") for e in _events(world))
    r = _run(world, "Edit", {"file_path": fp, "old_string": "assert adjust.total() > 0", "new_string": "assert adjust.total() >= 0"})
    assert _ot(r) and "test_from_other" in r


def test_cherry_pick_of_merge_commit_is_reported_unverified(world):
    """Codex 複審 BLOCK 3：cherry-pick 合併提交（-m 選主線）停在衝突，從 commit 看不出主線 → 不重算、留帳判不出，照執行前的內容
    比（別軌的改動會被算成這次改的：寧可多擋）。"""
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    _put(world, "TECH.md", "base\n")
    proj = world["proj"]
    _git_repo(proj)
    _g(proj, "checkout", "-qb", "feat")
    Path(fp).write_text(LEGACY.replace('"USD"', '"TWD"'), encoding="utf-8")
    _put(world, "TECH.md", "feat\n")
    _g(proj, "commit", "-qam", "feat")
    _g(proj, "checkout", "-q", "-")
    _g(proj, "checkout", "-qb", "other")
    _g(proj, "merge", "-q", "--no-ff", "feat", "-m", "merge feat")
    _g(proj, "checkout", "-q", "-")
    _put(world, "TECH.md", "mine\n")
    _g(proj, "commit", "-qam", "this track")
    r = _py_round(world, "cherry-pick -m 1 other", lambda: _g(proj, "cherry-pick", "-m", "1", "other", check=False))
    assert r.returncode != 0 and '"TWD"' in Path(fp).read_text(encoding="utf-8"), "前置：停在 TECH.md 衝突、測試改動已套進來"
    assert any(e["event"] == "git_op" and "合併提交" in e.get("why", "") for e in _events(world))
    assert [(e["key"], e["kind"]) for e in _pending()] == [("test_legacy_report_keeps_columns", "assert")]


def test_autostash_keeps_own_change_and_incoming_assert_not_pending(world):
    """Codex BLOCK 2：測試檔原本就有自己沒 commit 的改動（helper），merge --autostash 快轉帶進別軌的斷言改動再把自己的改動
    放回來 → 別軌那處不算這次改的，自己原本的改動也不重算。"""
    fp = _other_track(world, conflict=False)
    mine = LEGACY.replace("    adjust.LEVELS.clear()\n", "    adjust.LEVELS.clear()\n    adjust.RESET = True\n")
    Path(fp).write_text(mine, encoding="utf-8")
    _py_round(world, "merge --autostash other", lambda: _g(world["proj"], "merge", "-q", "--autostash", "other"))
    now = Path(fp).read_text(encoding="utf-8")
    assert '"TWD"' in now and "adjust.RESET = True" in now, "前置：別軌的斷言改動與自己原本的改動都在"
    assert not _pending()


@pytest.mark.parametrize("conflict", [True, False])
def test_tests_brought_in_by_merge_are_old_tests(world, conflict):
    """別軌帶進來的測試是舊測試：本 session 先碰過這個檔（基線只有兩支），merge 之後改 test_from_other 的斷言照要宣告。
    不併進基線的話它會被當成本 session 新加的放過。"""
    import wg_release_rules as rr
    fp = _other_track(world, conflict)
    assert _pass(_run(world, "Edit", {"file_path": fp, "old_string": "def setup_function():",
                                      "new_string": "def setup_function():  # 先看一眼"}))     # 只判不寫：記下基線
    base = wg_core.read_state(SID)["old_test_baseline"][rr.canon_path(fp)]
    assert "test_legacy_report_totals" in base and "test_from_other" not in base, "前置：基線是 merge 前的兩支"
    _merge_round(world)
    assert "test_from_other" in Path(fp).read_text(encoding="utf-8"), "前置：別軌的測試合進來了"
    assert not _pending()
    r = _run(world, "Edit", {"file_path": fp, "old_string": "assert adjust.total() > 0", "new_string": "assert adjust.total() >= 0"})
    assert _ot(r) and "test_from_other" in r


def test_merge_conflict_inside_test_file_takes_git_output_as_before(world):
    """衝突就在測試檔裡：磁碟上帶衝突標記的那份是 git 產出的，當改前（之後解衝突的 Edit 照常判）。"""
    fp = _put(world, "tests/test_legacy_report.py", LEGACY)
    proj = world["proj"]
    _git_repo(proj)
    _g(proj, "checkout", "-qb", "other")
    Path(fp).write_text(LEGACY.replace("== 10", "== 20"), encoding="utf-8")
    _g(proj, "commit", "-qam", "other track")
    _g(proj, "checkout", "-q", "-")
    Path(fp).write_text(LEGACY.replace("== 10", "== 30"), encoding="utf-8")
    _g(proj, "commit", "-qam", "this track")
    _merge_round(world)
    assert "<<<<<<<" in Path(fp).read_text(encoding="utf-8"), "前置：衝突標記在測試檔裡"
    assert not _pending()
    assert any(e["event"] == "git_op" and any(f.endswith("test_legacy_report.py") for f in e["files"]) for e in _events(world))


def test_git_status_reads_head_and_rename_untracked_modified_kinds(world):
    """porcelain v2 解析：HEAD 取 branch.oid；改名（路徑含空白，-z 後面多一筆原路徑）、未追蹤、一般改動都認得、不錯位。"""
    import re
    import wg_oldtest as ot
    proj = world["proj"]
    _put(world, "tests/test_a.py", "def test_a():\n    assert 1\n")
    keep = _put(world, "tests/test_keep.py", "def test_k():\n    assert 1\n")
    _git_repo(proj)
    _g(proj, "mv", "tests/test_a.py", "tests/test_b c.py")
    new = _put(world, "tests/test_new.py", "def test_n():\n    pass\n")
    Path(keep).write_text("def test_k():\n    assert 2\n", encoding="utf-8")
    head, dirty = ot._git_status(str(proj), {})
    assert re.match(r"^[0-9a-f]{40}$", head) and head == _g(proj, "rev-parse", "HEAD").stdout.strip()
    assert dirty == {str(proj / "tests" / "test_b c.py"): "2", new: "?", keep: "1"}


def test_own_commit_does_not_turn_session_added_tests_old(world):
    """自己 commit 讓 HEAD 移動不算帶進來：本 session 新加、只靠基線認得的測試（寫它的指令失敗、old_test_added 沒記到），
    commit 之後改它的斷言照樣不用宣告。"""
    _put(world, "tests/test_cli.py", CLI_TESTS)
    _git_repo(world["proj"])
    fp = _failed_bash_append(world)
    ti = {"command": "python _vcs_run.py commit -qam add"}
    assert _pass(_run(world, "Bash", ti))
    _g(world["proj"], "commit", "-qam", "add cli test")
    _post(world, "Bash", ti)
    fwd = fp.replace("\\", "/")
    _bash_round(world, "Bash", f"sed -i 's/40950.00/36855.00/' '{fwd}'", fp, CLI_TESTS + CLI_NEW.replace("40950.00", "36855.00"))
    assert any(e["event"] == "exempt" and e["test"] == "test_cli_plain_prints_two_decimals_no_currency"
               and e["why"] == "not_in_baseline" for e in _events(world)), "前置：比對有看到斷言變了"
    assert not _pending()


LEGACY_DOC = LEGACY.replace("def test_legacy_report_totals():\n", "def test_legacy_report_totals():\n    \"\"\"總數是 10。\"\"\"\n")


def test_docstring_changed_denied_but_added_not(world):
    fp = _put(world, "tests/test_legacy_report.py", LEGACY_DOC)
    r = _run(world, "Edit", {"file_path": fp, "old_string": "總數是 10。", "new_string": "總數是 0。"})
    assert _ot(r) and "test_legacy_report_totals（說明變了" in r
    r = _run(world, "Edit", {"file_path": fp, "old_string": "    \"\"\"總數是 10。\"\"\"\n", "new_string": ""})
    assert _ot(r) and "說明變了" in r, "刪掉說明也算"
    multi = LEGACY.replace("def test_legacy_report_totals():\n", "def test_legacy_report_totals():\n    \"\"\"總數。\n\n    舊報表要 10。\n    \"\"\"\n")
    fp2 = _put(world, "tests/test_multi.py", multi)
    assert _ot(_run(world, "Edit", {"file_path": fp2, "old_string": "舊報表要 10。", "new_string": "舊報表要 0。"})), "多行說明的後幾行"
    _assert_is_test_file_with_tests(fp, LEGACY)
    fp3 = _put(world, "tests/test_plain.py", LEGACY)
    r = _run(world, "Edit", {"file_path": fp3, "old_string": "def test_legacy_report_totals():\n",
                             "new_string": "def test_legacy_report_totals():\n    \"\"\"總數是 10。\"\"\"\n"})
    assert _pass(r), "只加新說明不算"


def test_notebook_edit_on_existing_test_blocks_next_call(world):
    nb = {"cells": [{"cell_type": "code", "id": "c1", "source": ["def test_a():\n", "    assert f() == 1\n"]}], "nbformat": 4}
    fp = _put(world, "tests/test_nb.ipynb", json.dumps(nb))
    ti = {"notebook_path": fp, "cell_id": "c1", "new_source": "def test_a():\n    assert f() == 2\n"}
    assert _pass(_run(world, "NotebookEdit", ti))
    nb["cells"][0]["source"] = ["def test_a():\n", "    assert f() == 2\n"]
    Path(fp).write_text(json.dumps(nb), encoding="utf-8")
    _post(world, "NotebookEdit", ti)
    r = _run(world, "Bash", {"command": "echo next"})
    assert _ot(r) and "test_a（斷言變了" in r and "這是 NotebookEdit 改的" in r


def test_gate_module_is_not_a_case_file():
    """模組檔名不能命中案例樣式（**/*_test.* 等），否則寫碼查核把它當測試檔、改了不要求補案例。"""
    import wg_verify_ledger as vl
    cfg = vl.reconcile_cfg({})
    assert not vl.is_case_file(str(HOOKS_DIR / "wg_oldtest.py"), cfg, str(HOOKS_DIR.parent))
    assert vl.is_case_file(str(HOOKS_DIR / "wg_old_test.py"), cfg, str(HOOKS_DIR.parent)), "前置：舊檔名確實會被當案例"


_CASE_GUARD_SKIP_DIRS = {"verify", "tests", "cassettes", "__pycache__"}


def _module_case_hits(repo, tops):
    """repo 底下 tops 各目錄裡、不在 verify／tests／cassettes 目錄的 .py，用寫碼查核的預設案例樣式（相對 repo 根）判；
    回 (掃了幾支, 被當成案例檔的相對路徑)。"""
    import wg_verify_ledger as vl
    cfg = vl.reconcile_cfg({})
    scanned, hits = 0, []
    for top in tops:
        for p in sorted((repo / top).rglob("*.py")):
            rel = p.relative_to(repo)
            if _CASE_GUARD_SKIP_DIRS & set(rel.parts[:-1]):
                continue
            scanned += 1
            if vl.is_case_file(str(p), cfg, str(repo)):
                hits.append(rel.as_posix())
    return scanned, hits


def test_no_production_module_name_matches_case_globs():
    """正式模組（hooks／lib／tools 底下、不在測試目錄的 .py）檔名不能命中案例樣式：命中的會被整套寫碼查核當成測試檔，
    改了不要求補案例、驗證範圍的 depends 也對不上（wg_old_test.py 踩過）。"""
    scanned, hits = _module_case_hits(HOOKS_DIR.parent, ("hooks", "lib", "tools"))
    assert scanned > 50, f"前置：要真的掃到檔（只掃到 {scanned} 支）"
    assert not hits, f"正式模組檔名命中案例樣式（寫碼查核會把它當測試檔），請改名：{hits}"


def test_case_name_guard_catches_fake_test_module(tmp_path):
    """負例：守門真的抓得到 *_test.py，也真的跳過 verify 目錄。"""
    repo = tmp_path / "repo"
    (repo / "hooks" / "verify").mkdir(parents=True)
    (repo / "hooks" / "wg_fake_test.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "hooks" / "wg_fine.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "hooks" / "verify" / "verify_x.py").write_text("", encoding="utf-8")
    assert _module_case_hits(repo, ("hooks",)) == (2, ["hooks/wg_fake_test.py"])


# ─── 真實輸入：第一波驗收題 C-1 ───

def test_c1_59_write_renames_old_compat_test_denied(world):
    _put(world, "tests/test_report_compat.py", C1_COMPAT_HEAD)
    r = _run(world, "Write", _real(world, "tests/test_report_compat.py", C1_59_WRITE))
    assert _ot(r), r
    assert "test_negative_rejected_for_old_report（改名 → test_underflow_rejected）" in r


def test_c1_312_skip_on_old_compat_test_denied(world):
    _put(world, "tests/test_legacy_report.py", C1_LEGACY_DISK)
    r = _run(world, "Edit", _real(world, "tests/test_legacy_report.py", C1_312_EDIT))
    assert _ot(r), r
    assert "test_returns_int_level_for_old_report（加 skip）" in r


def test_c1_adjust_chain_only_preexisting_test_flagged(world):
    """53／186／194 只加新測試、改 fixture → 不擋；264 整檔覆寫：本 session 自己加的測試改斷言、刪掉不算，
    只點名使用者原本就有的 test_inbound_adds（斷言變了）。"""
    fp = _put(world, "tests/test_adjust.py", C1_ADJUST_HEAD)
    for ti in (C1_53_EDIT, C1_186_EDIT, C1_194_EDIT):
        real = _real(world, "tests/test_adjust.py", ti)
        assert _pass(_run(world, "Edit", real)), ti["new_string"][:40]
        _apply(fp, real)
    r = _run(world, "Write", _real(world, "tests/test_adjust.py", C1_264_WRITE))
    assert _ot(r), r
    assert "test_inbound_adds（斷言變了" in r
    for own in ("test_negative_deducts", "test_audit_logged_on_success", "test_audit_not_logged_on_failure"):
        assert own not in r, own
    assert any(e["event"] == "exempt" and e["why"] == "session_added" for e in _events(world))
