"""verify_verify_scope.py：驗證範圍（該測哪些由 LLM 判斷並負責；程式只管宣告、收據、事後對帳）。

怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_verify_scope.py
假專案在 tmp_path（.git 目錄當版控根）；帳本目錄換成 tmp_path 下的 verify-scope/。
段落：宣告收件 → 收尾閘（_verify_gates 端到端）→ 收據對不對得上一項 → 範圍漏判（記帳、歸因、反例、跨 worktree、背景全量）
→ 檢討與數字 → 子代理／裁判 → need_goal 參數對拍。
"""
from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import wg_verify_ledger as vl  # noqa: E402
import wg_overview as wo  # noqa: E402
from handlers import stop as st  # noqa: E402

_SID = "sid-scope-0001"
_RULER = "python -X utf8 -m pytest -q tools/verify"
_NOW = datetime.now(timezone.utc).replace(microsecond=0)
# 改檔與收據在「現在」之前；結案時刻是收尾閘通過的當下（現在）；之後才紅的放在現在之後
T0, T1, T2, T3, T4 = ((_NOW + timedelta(hours=h)).isoformat() for h in (-3, -2, -1, 1, 2))
_LATER_Z = (_NOW + timedelta(hours=1, minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _vs():
    """新模組；舊碼沒有 → ImportError（案例紅）。"""
    return importlib.import_module("wg_verify_scope")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    monkeypatch.setattr(vl, "load_self_runs", lambda: [])
    monkeypatch.setattr(st, "load_self_runs", lambda: [], raising=False)
    try:
        vs = _vs()
    except ImportError:
        return
    monkeypatch.setattr(vs, "SCOPE_DIR", tmp_path / "verify-scope")


@pytest.fixture()
def proj(tmp_path):
    root = tmp_path / "proj"
    for d in (".git", "hooks/verify", "tools/verify", "_AIDocs", "workflow/inbox"):
        (root / d).mkdir(parents=True)
    files = {
        "hooks/x.py": "X = 1\n",
        "tools/t.py": "T = 1\n",
        "tools/verify/verify_t.py": "def test_t():\n    pass\n",
        "hooks/verify/verify_x.py": "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n",
        "hooks/verify/verify_y.py": "def test_q():\n    pass\n",
        "_AIDocs/doc.md": "# d\n",
        "workflow/inbox/note.md": "n\n",
    }
    for rel, text in files.items():
        (root / rel).write_text(text, encoding="utf-8")
    return root


def _rows():
    """假部位表：tools 有整把量尺、_AIDocs 是有量尺的知識部位、workflow/inbox 是沒量尺的知識部位、hooks 沒量尺。"""
    return {
        "tools": {"part_short": "工具層", "part": "工具層", "measure": {"method": "tools verify", "cmd": _RULER, "threshold": "全綠"},
                  "category": "code"},
        "_AIDocs": {"part_short": "文件層", "part": "文件層", "category": "knowledge",
                    "measure": {"method": "文件計數", "cmd": "python -X utf8 tools/sync_doc_counts.py --check", "threshold": "exit 0"}},
        "workflow": {"part_short": "派工信箱", "part": "派工信箱", "measure": {}, "category": "knowledge"},
        "hooks": {"part_short": "hook 層", "part": "hook 層", "measure": {}, "category": "code"},
    }


@pytest.fixture()
def lookup(proj, monkeypatch):
    rows = _rows()

    def _lk(path, stop_at=None):
        try:
            rel = Path(path).resolve().relative_to(proj.resolve()).as_posix()
        except ValueError:
            return None
        head = rel.split("/", 1)[0]
        return (proj, rows[head]) if head in rows else None

    monkeypatch.setattr(wo, "_lookup", _lk)
    return _lk


def _mf(path, at, seq, turn=5, sid=_SID):
    return {"path": str(path), "tool": "Edit", "session_id": sid, "turn_seq": turn, "last_turn_seq": turn,
            "last_at": at, "last_seq": seq}


def _rcpt(root, cmd, at, seq, verdict="PASS", exit_code=0, env=None, turn=5, name="PYTEST", cwd=None):
    return {"turn_seq": turn, "tool": "Bash", "cmd": cmd, "cmd_full": True,
            "sentinels": [{"name": name, "verdict": verdict, "kv": {}}], "exit_code": exit_code, "at": at, "seq": seq,
            "project_root": str(root), "cwd": str(cwd or root), "env": env if env is not None else {}}


def _declare(state, root, items, reviews=None, key=_SID):
    """透過 need_goal(action=verify_scope) 的收件函式宣告；舊碼沒有這個模組 → 不宣告（讓舊閘的行為照實顯出來）。"""
    try:
        vs = _vs()
    except ImportError:
        return "（舊碼沒有 verify_scope）"
    inp = {"action": "verify_scope", "items": items}
    if reviews is not None:
        inp["reviews"] = reviews
    return vs.declare(state, key, inp, str(root), {})


def _gates(state, mods, receipts=(), key=_SID):
    """端到端：stop._verify_gates（對帳關掉，只看量尺／範圍這一段）。回 (擋訊息或 None, 種類)。"""
    rg = dict(vl.reconcile_cfg({}), enabled=False)
    state.setdefault("verify_receipts", {})[key] = list(receipts)
    reason, _report, kind, _advice = st._verify_gates(state, key, 5, "全部完成了。", None, "", list(mods), rg, {}, {}, False)
    return reason, kind


def _state():
    return {"turn_seq": 5, "modified_files": []}


# ─── 宣告收件 ─────────────────────────────────────────────────────────────

def test_declare_accepts_file_node_dir_and_command_items(proj, lookup):
    state = _state()
    text = _declare(state, proj, [
        {"target": "hooks/verify/verify_x.py", "why": "直接測 x.py"},
        {"target": "hooks/verify/verify_y.py::test_q", "why": "呼叫方 y 讀 x 的常數"},
        {"target": "tools/verify", "why": "工具層整組都讀這份設定"},
        {"target": "python -X utf8 tools/sync_doc_counts.py --check", "why": "改了文件計數段"},
    ])
    assert "收下" in text, text
    decl = state["verify_scope"][_SID][-1]
    assert [it["kind"] for it in decl["items"]] == ["file", "node", "dir", "cmd"]
    assert decl["id"].endswith("S1")


@pytest.mark.parametrize("item, word", [
    ({"target": "hooks/verify/verify_x.py", "why": "  "}, "理由"),
    ({"target": "hooks/verify/verify_nope.py", "why": "打錯字"}, "不存在"),
    ({"target": "hooks/verify/verify_x.py::test_zzz", "why": "沒有這個測試"}, "test_zzz"),
])
def test_declare_rejects_blank_why_and_missing_targets(proj, lookup, item, word):
    """SCOPE_ITEM_WELL_FORMED：理由空、檔不存在、節點查不到 def → 退回，不落宣告。"""
    state = _state()
    text = _declare(state, proj, [item])
    assert "SCOPE_ITEM_WELL_FORMED" in text and word in text, text
    assert not (state.get("verify_scope") or {}).get(_SID)


def test_declare_reply_shows_changed_files_and_rulers_as_reference_only(proj, lookup):
    state = _state()
    state["modified_files"] = [_mf(proj / "tools" / "t.py", T1, 3)]
    text = _declare(state, proj, [{"target": "tools/verify/verify_t.py", "why": "直接測 t.py"}])
    assert "t.py" in text and _RULER in text and "參考" in text and "不必" in text, text


# ─── 收尾閘（端到端）────────────────────────────────────────────────────────

def test_one_line_change_runs_only_declared_test_and_passes(proj, lookup):
    """改 tools 一支、宣告一支測試、改完之後跑綠 → 放行；舊碼要整把 tools 量尺 → 擋（紅）。"""
    state = _state()
    _declare(state, proj, [{"target": "tools/verify/verify_t.py", "why": "直接測 t.py"}])
    reason, _ = _gates(state, [_mf(proj / "tools" / "t.py", T1, 3)],
                       [_rcpt(proj, "python -X utf8 -m pytest -q tools/verify/verify_t.py", T2, 4)])
    assert reason is None, reason


def test_code_change_without_declaration_blocks_and_offers_reference(proj, lookup):
    """改了程式沒宣告 → 擋（SCOPE_DECLARED_FOR_CHANGE），列改到的檔；舊碼在沒量尺的部位只提醒 → 不擋（紅）。"""
    reason, kind = _gates(_state(), [_mf(proj / "hooks" / "x.py", T1, 3)])
    assert reason and "SCOPE_DECLARED_FOR_CHANGE" in reason and "x.py" in reason and "verify_scope" in reason, reason
    assert kind == "scope"


def test_two_items_one_run_blocks_naming_the_missing_item(proj, lookup):
    state = _state()
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測"},
                           {"target": "hooks/verify/verify_y.py", "why": "呼叫方"}])
    reason, _ = _gates(state, [_mf(proj / "hooks" / "x.py", T1, 3)],
                       [_rcpt(proj, "python -m pytest -q hooks/verify/verify_x.py", T2, 4)])
    assert reason and "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in reason, reason
    hits = [ln for ln in reason.splitlines() if "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in ln]
    assert len(hits) == 1 and "verify_y.py" in hits[0], hits


def test_knowledge_part_with_ruler_needs_scope_but_plain_material_does_not(proj, lookup):
    """要不要宣告是規則：改到有量尺的知識部位要宣告；沒量尺的知識素材不用。"""
    reason, _ = _gates(_state(), [_mf(proj / "_AIDocs" / "doc.md", T1, 3)])
    assert reason and "SCOPE_DECLARED_FOR_CHANGE" in reason, reason
    reason, _ = _gates(_state(), [_mf(proj / "workflow" / "inbox" / "note.md", T1, 3)])
    assert reason is None, reason


def test_legacy_modified_entry_without_any_time_is_not_required(proj, lookup):
    """升級前的舊改檔紀錄（turn、at、序號都沒記）看不出何時改的 → 不要求宣告（與 (d) 的舊格式規則一致）；有 turn 就照要求。"""
    legacy = {"path": str(proj / "hooks" / "x.py"), "tool": "Edit", "session_id": _SID}
    assert _gates(_state(), [legacy])[0] is None
    reason, _ = _gates(_state(), [{**legacy, "turn_seq": 5}])
    assert reason and "SCOPE_DECLARED_FOR_CHANGE" in reason


def test_declaration_must_have_an_item_in_every_changed_repo(proj, lookup, tmp_path):
    other = tmp_path / "other"
    (other / ".git").mkdir(parents=True)
    (other / "a.py").write_text("A = 1\n", encoding="utf-8")
    state = _state()
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測"}])
    reason, _ = _gates(state, [_mf(proj / "hooks" / "x.py", T1, 3), _mf(other / "a.py", T1, 4)],
                       [_rcpt(proj, "python -m pytest -q hooks/verify/verify_x.py", T2, 5)])
    assert reason and "SCOPE_DECLARED_FOR_CHANGE" in reason and "a.py" in reason, reason


# ─── 收據對不對得上一項 ──────────────────────────────────────────────────────

_X_RUN = "python -m pytest -q hooks/verify/verify_x.py"


@pytest.mark.parametrize("cmd, at, verdict, exit_code, env, word", [
    (_X_RUN, T0, "PASS", 0, {}, "之前"),                                                   # 先跑後改
    (_X_RUN, T2, "FAIL", 1, {}, "紅"),                                                     # 跑紅
    (_X_RUN + " -k test_a", T2, "PASS", 0, {}, "沒有跑這一項"),                            # 只跑一部分
    ("cd hooks && python -m pytest -q verify/verify_x.py", T2, "PASS", 0, {}, "沒有跑這一項"),  # 指令換目錄
    (_X_RUN, T2, "PASS", 0, {"PYTEST_ADDOPTS": "-k test_a"}, "沒有跑這一項"),              # 環境縮範圍
    ("python -m pytest -q hooks/verify/verify_y.py", T2, "PASS", 0, {}, "沒有跑這一項"),   # 跑的是別支
    (_X_RUN + " -ktest_a", T2, "PASS", 0, {}, "沒有跑這一項"),                             # 短選項連寫也是只跑一部分
    ("python -m pytest -q hooks/verify -o python_functions=test_a", T2, "PASS", 0, {}, "沒有跑這一項"),  # 改收集設定
    ("python -O -m pytest -q hooks/verify/verify_x.py", T2, "PASS", 0, {}, "沒有跑這一項"),  # -O 拿掉 assert
    ("python -m compileall -q hooks/verify/verify_x.py && python -m pytest -q hooks/verify/verify_y.py",
     T2, "PASS", 0, {}, "沒有跑這一項"),                                                   # 只編譯、綠的是別支
])
def test_item_receipt_that_does_not_count(proj, lookup, cmd, at, verdict, exit_code, env, word):
    state = _state()
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測"}])
    reason, _ = _gates(state, [_mf(proj / "hooks" / "x.py", T1, 3)],
                       [_rcpt(proj, cmd, at, 4 if at != T0 else 1, verdict, exit_code, env)])
    assert reason and "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in reason and word in reason, (cmd, reason)


def test_node_item_not_satisfied_when_run_was_narrowed(proj, lookup):
    """點名了節點、但同一條指令又用 -k 篩掉它 → 那個節點沒跑，不算（命令列點名不等於實際執行）。"""
    state = _state()
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py::test_b", "why": "直接測"}])
    cmd = "python -m pytest hooks/verify/verify_x.py::test_a hooks/verify/verify_x.py::test_b -k test_a"
    reason, _ = _gates(state, [_mf(proj / "hooks" / "x.py", T1, 3)], [_rcpt(proj, cmd, T2, 4)])
    assert reason and "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in reason, reason


def test_script_file_item_counts_when_the_script_itself_ran(proj, lookup):
    """檔案項目是一支驗證腳本：直接執行它（python 腳本）就算；拿它當別的程式的參數（compileall）不算。"""
    (proj / "tools" / "verify" / "smoke.py").write_text("print('SMOKE_CHECK PASS')\n", encoding="utf-8")
    state = _state()
    _declare(state, proj, [{"target": "tools/verify/smoke.py", "why": "冒煙檢查"}])
    mods = [_mf(proj / "hooks" / "x.py", T1, 3)]
    assert _gates(state, mods, [_rcpt(proj, "python tools/verify/smoke.py", T2, 4, name="SMOKE_CHECK")])[0] is None
    reason, _ = _gates(state, mods, [_rcpt(proj, "python -m py_compile tools/verify/smoke.py", T2, 4, name="X_CHECK")])
    assert reason and "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in reason


def test_receipt_from_other_tree_does_not_count(proj, lookup, tmp_path):
    state = _state()
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測"}])
    reason, _ = _gates(state, [_mf(proj / "hooks" / "x.py", T1, 3)],
                       [_rcpt(tmp_path / "elsewhere", _X_RUN, T2, 4)])
    assert reason and "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in reason, reason


@pytest.mark.parametrize("target, cmd", [
    ("hooks/verify/verify_x.py", "python -m pytest -q hooks/verify"),                     # 跑整個資料夾涵蓋其中一支
    ("hooks/verify/verify_x.py::test_a", _X_RUN),                                        # 跑整支涵蓋其中一個節點
    ("hooks/verify/verify_x.py::test_a", _X_RUN + "::test_a"),                           # 點名節點本身
    ("hooks/verify/verify_x.py", "python -X utf8 run_verify.py"),                        # 整體驗證涵蓋全部
    ("hooks/verify", "python -m pytest -q hooks/verify"),
    ("python -X utf8 tools/sync_doc_counts.py --check", "python -X utf8 tools/sync_doc_counts.py --check"),
])
def test_item_receipt_that_counts(proj, lookup, target, cmd):
    state = _state()
    _declare(state, proj, [{"target": target, "why": "有關"}])
    reason, _ = _gates(state, [_mf(proj / "hooks" / "x.py", T1, 3)], [_rcpt(proj, cmd, T2, 4, name="X_CHECK")])
    assert reason is None, (target, cmd, reason)


def test_redeclare_replaces_whole_scope(proj, lookup):
    """每次宣告是完整範圍：第二次只留 verify_x → 只要 verify_x 的收據。"""
    state = _state()
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測"},
                           {"target": "hooks/verify/verify_y.py", "why": "呼叫方"}])
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "重新判斷：y 不讀 x"}])
    assert state["verify_scope"][_SID][-1]["id"].endswith("S2")
    reason, _ = _gates(state, [_mf(proj / "hooks" / "x.py", T1, 3)], [_rcpt(proj, _X_RUN, T2, 4)])
    assert reason is None, reason


# ─── 收據只被跟這一項有關的改動作廢（SCOPE_EDIT_RELATED_TO_ITEM） ─────────────────────

_DOC_RULER = "python -X utf8 tools/sync_doc_counts.py --check"
_T_DOC = (_NOW - timedelta(minutes=30)).isoformat()            # 文件改在測試收據之後（T1 之後、現在之前）


def test_doc_edit_after_code_test_does_not_void_its_receipt(proj, lookup):
    """改程式 → 跑測試綠 → 再改一段有量尺部位的文件：測試那一項不用重跑（文件跟它無關），文件那一項照要改完之後的收據。
    舊碼拿全部要宣告的改檔比先後 → 測試收據早於文件修改 → 擋（紅）。"""
    state = _state()
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測 x.py"},
                           {"target": _DOC_RULER, "why": "改了文件計數段"}])
    mods = [_mf(proj / "hooks" / "x.py", T0, 1), _mf(proj / "_AIDocs" / "doc.md", _T_DOC, 5)]
    receipts = [_rcpt(proj, _X_RUN, T1, 3), _rcpt(proj, _DOC_RULER, _NOW.isoformat(), 6, name="DOC_CHECK")]
    reason, _ = _gates(state, mods, receipts)
    assert reason is None, reason


@pytest.mark.parametrize("item, run, doc", [
    (_DOC_RULER, _DOC_RULER, "_AIDocs/doc.md"),                                         # 這一項就是文件部位的量尺
    ("tools/verify/verify_t.py", "python -m pytest -q tools/verify/verify_t.py", "tools/verify/data.md"),   # 同部位的資料檔
    ("python -m pytest -q", "python -m pytest -q", "_AIDocs/doc.md"),                    # 整體驗證：什麼都算
])
def test_related_non_code_edit_still_voids_the_receipt(proj, lookup, item, run, doc):
    """反例：文件跟這一項有關（它就是那個部位的量尺、和它點名的檔同部位、整體驗證）→ 收據早於文件修改照擋。"""
    (proj / doc).write_text("d\n", encoding="utf-8")
    state = _state()
    _declare(state, proj, [{"target": item, "why": "有關"}])
    reason, _ = _gates(state, [_mf(proj / doc, _T_DOC, 5)], [_rcpt(proj, run, T1, 3, name="X_CHECK")])
    assert reason and "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in reason and Path(doc).name in reason, (item, reason)


def test_item_inputs_declare_cross_part_data_the_test_reads(proj, lookup):
    """codex BLOCK：測試讀別的部位的資料（tools 的測試讀 _AIDocs 的文件）是判斷題，交 LLM 宣告（inputs）。沒宣告 → 文件改動
    不算進這一項，宣告回應把「不算進任何一項的文件改動」列出來問；宣告了 → 改完沒重跑就擋；inputs 指到不存在的檔 → 退回。"""
    doc = proj / "_AIDocs" / "doc.md"
    state = _state()
    state["modified_files"] = [_mf(proj / "tools" / "t.py", T0, 1), _mf(doc, _T_DOC, 5)]
    text = _declare(state, proj, [{"target": "tools/verify/verify_t.py", "why": "讀文件計數"}])
    assert "收下" in text and "doc.md" in text and "inputs" in text, text
    mods = state["modified_files"]
    run = _rcpt(proj, "python -m pytest -q tools/verify/verify_t.py", T1, 3)
    assert _gates(state, mods, [run])[0] is None                                   # 沒宣告 inputs：文件改動不作廢
    text = _declare(state, proj, [{"target": "tools/verify/verify_t.py", "why": "讀文件計數", "inputs": ["_AIDocs/doc.md"]}])
    assert "收下" in text, text
    reason, _ = _gates(state, mods, [run])
    assert reason and "SCOPE_ITEM_RECEIPT_AFTER_EDIT" in reason and "doc.md" in reason, reason
    text = _declare(state, proj, [{"target": "tools/verify/verify_t.py", "why": "x", "inputs": ["_AIDocs/nope.md"]}])
    assert "SCOPE_ITEM_WELL_FORMED" in text and "nope.md" in text, text


def test_fix_evidence_reads_declared_scope_not_file_names(proj, lookup):
    """對帳 (a) 的證據（fix_evidence）：沒宣告 → None（退回檔名對應）；宣告範圍內一項改完之後跑綠 → 認（指令不必提到改的檔）；
    跑在改動之前 → 不認，附每項為什麼。"""
    vs = _vs()
    rg = vl.reconcile_cfg({})
    mods = [_mf(proj / "hooks" / "x.py", T1, 3)]
    state = _state()
    assert vs.fix_evidence(state, _SID, mods, [], rg, lookup) is None
    _declare(state, proj, [{"target": "tools/verify/verify_t.py", "why": "x.py 的呼叫方"}])
    ok, notes = vs.fix_evidence(state, _SID, mods, [_rcpt(proj, "python -m pytest -q tools/verify/verify_t.py", T2, 4)], rg, lookup)
    assert ok and "verify_t.py" in notes[0], notes
    ok, notes = vs.fix_evidence(state, _SID, mods, [_rcpt(proj, "python -m pytest -q tools/verify/verify_t.py", T0, 1)], rg, lookup)
    assert not ok and "之前" in notes[0], notes


# ─── 範圍漏判 ────────────────────────────────────────────────────────────

_Y_RUN = "python -m pytest -q hooks/verify/verify_y.py"
_Y_RED = "FAILED hooks/verify/verify_y.py::test_q - AssertionError\n1 failed in 0.1s"


def _close_x(proj, state, key=_SID):
    """宣告 verify_x、改 x.py、跑綠、收尾通過（結案）。"""
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測 x.py"}], key=key)
    reason, _ = _gates(state, [_mf(proj / "hooks" / "x.py", T1, 3)], [_rcpt(proj, _X_RUN, T2, 4)], key=key)
    assert reason is None, reason


def _observe(vs, state, proj, cmd, out, at, seq, verdict="PASS", exit_code=0, key=_SID):
    return vs.observe_run(state, key, _rcpt(proj, cmd, at, seq, verdict, exit_code), out, vl.reconcile_cfg({}))


def test_out_of_scope_red_after_close_is_recorded_and_linked(proj, lookup):
    vs = _vs()
    state = _state()
    _observe(vs, state, proj, _Y_RUN, "1 passed in 0.1s", T0, 1)                      # verify_y 上次綠
    _close_x(proj, state)
    msg = _observe(vs, _state(), proj, _Y_RUN, _Y_RED, T3, 9, "FAIL", 1, key="sid-other")
    assert msg and "verify_y.py::test_q" in msg and "S1" in msg, msg
    pend = vs.pending_leaks(vs.repo_key(str(proj)))
    assert len(pend) == 1 and pend[0]["scope_id"].endswith("S1") and pend[0]["test"].endswith("verify_y.py::test_q")


def test_narrowed_green_run_does_not_reset_last_green(proj, lookup):
    """結案之後只跑了同檔的一部分（-k）而且綠 → 不能當成 test_q 又綠過；之後 test_q 紅了照樣連回那次宣告。"""
    vs = _vs()
    _observe(vs, _state(), proj, _Y_RUN, "1 passed", T0, 1)
    _close_x(proj, _state())
    _observe(vs, _state(), proj, _Y_RUN + " -k other", "1 passed, 1 deselected", T3, 8, key="sid-other")
    _observe(vs, _state(), proj, _Y_RUN, _Y_RED, T4, 9, "FAIL", 1, key="sid-other")
    assert [p["scope_id"][-2:] for p in vs.pending_leaks(vs.repo_key(str(proj)))] == ["S1"]


def test_same_test_path_in_two_repos_records_two_leaks(proj, lookup, tmp_path):
    """同一份宣告涉及兩個 repo，兩邊同名測試都在範圍外又都紅了 → 各記一筆（去重要分 repo）。"""
    vs = _vs()
    other = tmp_path / "other"
    (other / ".git").mkdir(parents=True)
    (other / "hooks" / "verify").mkdir(parents=True)
    (other / "hooks" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (other / "hooks" / "verify" / "verify_x.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    (other / "hooks" / "verify" / "verify_y.py").write_text("def test_q():\n    pass\n", encoding="utf-8")
    for root in (proj, other):
        _observe(vs, _state(), root, _Y_RUN, "1 passed", T0, 1)
    state = _state()
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測 x"},
                           {"target": str(other / "hooks" / "verify" / "verify_x.py"), "why": "直接測 a"}])
    mods = [_mf(proj / "hooks" / "x.py", T1, 3), _mf(other / "hooks" / "a.py", T1, 3)]
    reason, _ = _gates(state, mods, [_rcpt(proj, _X_RUN, T2, 4), _rcpt(other, _X_RUN, T2, 5)])
    assert reason is None, reason
    for root in (proj, other):
        _observe(vs, _state(), root, _Y_RUN, _Y_RED, T3, 9, "FAIL", 1, key="sid-other")
    assert len(vs.pending_leaks(vs.repo_key(str(proj)))) == 1 and len(vs.pending_leaks(vs.repo_key(str(other)))) == 1


def test_in_scope_red_is_not_a_leak(proj, lookup):
    vs = _vs()
    state = _state()
    _observe(vs, state, proj, _X_RUN, "2 passed in 0.1s", T0, 1)
    _close_x(proj, state)
    _observe(vs, _state(), proj, _X_RUN, "FAILED hooks/verify/verify_x.py::test_a\n1 failed", T3, 9, "FAIL", 1, key="sid-other")
    assert vs.pending_leaks(vs.repo_key(str(proj))) == []


def test_never_green_test_is_not_attributed(proj, lookup):
    vs = _vs()
    _close_x(proj, _state())
    _observe(vs, _state(), proj, _Y_RUN, _Y_RED, T3, 9, "FAIL", 1, key="sid-other")
    assert vs.pending_leaks(vs.repo_key(str(proj))) == []


def test_observer_with_open_changes_still_links_back_to_old_declaration(proj, lookup):
    """下一個 session 正在改無關的檔（還沒結案）時跑到範圍外的紅 → 不憑 session 狀態丟掉：照記、連回當初的宣告，
    標出「看到紅時自己還有沒結案的改動」，檢討時先查明。"""
    vs = _vs()
    _observe(vs, _state(), proj, _Y_RUN, "1 passed", T0, 1)
    _close_x(proj, _state())
    busy = _state()
    busy["modified_files"] = [_mf(proj / "tools" / "t.py", T2, 5, sid="sid-busy")]
    msg = _observe(vs, busy, proj, _Y_RUN, _Y_RED, T3, 9, "FAIL", 1, key="sid-busy")
    pend = vs.pending_leaks(vs.repo_key(str(proj)))
    assert len(pend) == 1 and pend[0]["scope_id"].endswith("S1") and pend[0]["observer_open"] is True
    assert msg and "先查明是不是它這次改動造成的" in msg


def _real_git(proj):
    """把 proj 換成真 git repo，全部檔在上次綠（T0）之前提交（提交時間 T0 前一小時）。"""
    import shutil
    import subprocess
    shutil.rmtree(proj / ".git")
    when = (_NOW + timedelta(hours=-4)).isoformat()
    env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"], ["add", "-A"],
                 ["commit", "-qm", "base"]):
        subprocess.run(["git", "-C", str(proj), *args], check=True, capture_output=True, env=env)


@pytest.mark.parametrize("change, red, leak", [
    ("add_case", "test_r", False),      # 自己新寫的案例先紅（先紅後綠）→ 自己進行中的工作
    ("edit_case", "test_q", False),     # 自己改了這個案例的內容 → 自己的
    ("add_case", "test_q", True),       # codex BLOCK：自己在同檔加了別的案例，紅的 test_q 沒動過 → 照記（可能是別人留下的退化）
    ("no_git", "test_q", True),         # 查不了 git（判不出案例有沒有被改過）→ 照記
])
def test_observer_changing_the_red_case_is_its_own_work(proj, lookup, change, red, leak):
    """盤點 P1（10-15 實遇：照 G3 先寫新案例、先跑紅，被記成兩個已關 session 共 44 筆漏判，還擋住自己的宣告）：看到紅的 session
    還沒結案地改過紅的那個案例（上次綠時的 git 版本裡沒有它、或它的內容和現在不同）→ 是它進行中的工作，不記別人的範圍漏判，
    改成告訴它（紅照樣進紅測清單，收尾前要綠）。只看「改過同一份測試檔」不夠：同檔別的案例被別人弄紅會被丟掉。"""
    if change != "no_git":
        _real_git(proj)
        (proj / "hooks" / "x.py").write_text("X = 2\n", encoding="utf-8")       # 上一個 session 真的改了 x.py（不是原樣還原）
    vs = _vs()
    _observe(vs, _state(), proj, _Y_RUN, "1 passed", T0, 1)
    _close_x(proj, _state())
    assert vs.stats(vs.repo_key(str(proj)))["closed"] == 1                      # 那份範圍確實結案了，下面的判定才有對象
    y = proj / "hooks" / "verify" / "verify_y.py"
    if change == "edit_case":
        y.write_text("def test_q():\n    assert 1 == 2\n", encoding="utf-8")
    else:
        y.write_text("def test_q():\n    pass\n\n\ndef test_r():\n    assert 1 == 2\n", encoding="utf-8")
    busy = _state()
    busy["modified_files"] = [_mf(y, T2, 5, sid="sid-busy")]
    out = f"FAILED hooks/verify/verify_y.py::{red} - AssertionError\n1 failed in 0.1s"
    msg = _observe(vs, busy, proj, _Y_RUN, out, T3, 9, "FAIL", 1, key="sid-busy")
    assert bool(vs.pending_leaks(vs.repo_key(str(proj)))) is leak, (change, red)
    if not leak:
        assert msg and f"verify_y.py::{red}" in msg and "不記範圍漏判" in msg, msg


def test_red_caused_by_current_change_reviewed_unrelated_is_not_a_confirmed_miss(proj, lookup):
    """紅其實是看到它的 session 自己這次改動造成的：檢討判 unrelated 寫理由 → 不算確認漏判（數字分開記）。"""
    vs = _vs()
    _observe(vs, _state(), proj, _Y_RUN, "1 passed", T0, 1)
    _close_x(proj, _state())
    busy = _state()
    busy["modified_files"] = [_mf(proj / "tools" / "t.py", T2, 5, sid="sid-busy")]
    _observe(vs, busy, proj, _Y_RUN, _Y_RED, T3, 9, "FAIL", 1, key="sid-busy")
    lid = vs.pending_leaks(vs.repo_key(str(proj)))[0]["id"]
    text = _declare(busy, proj, [{"target": "tools/verify/verify_t.py", "why": "直接測 t.py"}], key="sid-busy",
                    reviews=[{"leak": lid, "verdict": "unrelated", "reason": "是我這次改 t.py 弄壞 verify_y 讀的設定，不是 S1 漏驗"}])
    assert "收下" in text, text
    s = vs.stats(vs.repo_key(str(proj)))
    assert (s["missed"], s["unrelated"], s["pending"]) == (0, 1, 0)


def test_same_session_next_turn_red_is_a_leak(proj, lookup):
    """自己結案之後、沒有新改動，下一回合跑到範圍外的紅 → 記在自己那次宣告上。"""
    vs = _vs()
    state = _state()
    state["modified_files"] = [_mf(proj / "hooks" / "x.py", T1, 3)]
    _observe(vs, state, proj, _Y_RUN, "1 passed", T0, 1)
    _close_x(proj, state)
    _observe(vs, state, proj, _Y_RUN, _Y_RED, T3, 9, "FAIL", 1)
    assert [p["scope_id"][-2:] for p in vs.pending_leaks(vs.repo_key(str(proj)))] == ["S1"]


def test_worktree_and_main_checkout_are_one_repo(tmp_path):
    vs = _vs()
    main = tmp_path / "live"
    (main / ".git" / "worktrees" / "wt1").mkdir(parents=True)
    wt = tmp_path / "wt1"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'wt1'}\n", encoding="utf-8")
    (main / ".git" / "worktrees" / "wt1" / "commondir").write_text("../..\n", encoding="utf-8")
    assert vs.repo_key(str(wt)) == vs.repo_key(str(main))


def test_background_full_run_failed_cases_are_attributed(proj, lookup):
    """背景全量的自寫收據帶紅掉的測試名 → 入帳並歸因；同一份不重複入帳。"""
    vs = _vs()
    _observe(vs, _state(), proj, _Y_RUN, "1 passed", T0, 1)
    _close_x(proj, _state())
    run = {"source": "run_verify_self", "argv": ["python", "run_verify.py"], "cmd": "python run_verify.py", "exit_code": 1,
           "cases": 10, "failed": 1, "failed_cases": ["hooks/verify/verify_y.py::test_q"], "project_root": str(proj),
           "cwd": str(proj), "started_at": _LATER_Z, "at": _LATER_Z, "env": {}}
    notes = vs.sync_runs([run])
    assert notes and vs.pending_leaks(vs.repo_key(str(proj)))
    assert vs.sync_runs([run]) == []


def test_self_receipt_records_failed_cases(tmp_path):
    from self_receipt import write_self_receipt
    p = write_self_receipt(tmp_path, ["python", "run_verify.py"], "VERIFY_CHECK FAIL cases=2 failed=1", 1, 2, 1,
                           str(tmp_path), str(tmp_path), 0.0, 1.0, failed_cases=["hooks/verify/verify_y.py::test_q"])
    import json
    assert json.loads(p.read_text(encoding="utf-8"))["failed_cases"] == ["hooks/verify/verify_y.py::test_q"]


# ─── 檢討與數字 ─────────────────────────────────────────────────────────────

def _one_leak(proj):
    vs = _vs()
    _observe(vs, _state(), proj, _Y_RUN, "1 passed", T0, 1)
    _close_x(proj, _state())
    _observe(vs, _state(), proj, _Y_RUN, _Y_RED, T3, 9, "FAIL", 1, key="sid-other")
    return vs, vs.pending_leaks(vs.repo_key(str(proj)))[0]["id"]


def test_pending_leak_must_be_reviewed_before_next_declaration(proj, lookup):
    vs, lid = _one_leak(proj)
    state = _state()
    text = _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測"}])
    assert "SCOPE_LEAK_REVIEW_BEFORE_DECLARE" in text and lid in text, text
    assert not (state.get("verify_scope") or {}).get(_SID)
    text = _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測"}],
                    reviews=[{"leak": lid, "verdict": "missed", "root_cause": "", "next_time": "看呼叫方"}])
    assert "SCOPE_LEAK_REVIEW_BEFORE_DECLARE" in text and "根因" in text, text
    text = _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測"}],
                    reviews=[{"leak": lid, "verdict": "missed", "root_cause": "只看了 x.py 自己的測試，沒查誰讀它的常數",
                              "next_time": "改常數先搜讀它的呼叫方"}])
    assert "收下" in text and vs.pending_leaks(vs.repo_key(str(proj))) == [], text


def test_stats_count_closes_leaks_and_reviews(proj, lookup):
    vs, lid = _one_leak(proj)
    _declare(_state(), proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測"}],
             reviews=[{"leak": lid, "verdict": "unrelated", "reason": "verify_y 是讀環境變數壞的，與 x.py 無關"}])
    s = vs.stats(vs.repo_key(str(proj)))
    assert (s["closed"], s["leaks"], s["missed"], s["unrelated"], s["pending"]) == (1, 1, 0, 1, 0)
    assert "結案 1" in vs.stats_line(vs.repo_key(str(proj)))


def test_session_start_lists_pending_leaks(proj, lookup):
    vs, lid = _one_leak(proj)
    lines = vs.advisory(str(proj))
    assert lines and lid in lines[0] and "檢討" in lines[0]


# ─── 子代理與裁判 ─────────────────────────────────────────────────────────

def test_subagent_reuses_main_declaration_with_own_receipts(proj, lookup):
    state = _state()
    _declare(state, proj, [{"target": "hooks/verify/verify_x.py", "why": "直接測"}])
    akey = vl.agent_receipt_key(_SID, "ag1")
    reason, _ = _gates(state, [_mf(proj / "hooks" / "x.py", T1, 3)], [_rcpt(proj, _X_RUN, T2, 4)], key=akey)
    assert reason is None, reason
    reason, _ = _gates(_state(), [_mf(proj / "hooks" / "x.py", T1, 3)], [_rcpt(proj, _X_RUN, T2, 4)], key=akey)
    assert reason and "SCOPE_DECLARED_FOR_CHANGE" in reason


def test_judge_post_tool_use_takes_declaration(proj, lookup, monkeypatch):
    from handlers import post_tool_use as ptu
    import wg_core
    saved = {}
    monkeypatch.setattr(ptu, "write_state", lambda sid, s: saved.update(s), raising=False)
    monkeypatch.setattr(wg_core, "read_state", lambda sid: {"session": {"id": sid}, "turn_seq": 1, "judge": True})
    monkeypatch.setattr(ptu, "output_nothing", lambda: None)
    ptu.handle_judge_post_tool_use({"session_id": "judge-1", "cwd": str(proj),
                                    "tool_name": "mcp__workflow-guardian__need_goal",
                                    "tool_input": {"action": "verify_scope",
                                                   "items": [{"target": "hooks/verify/verify_x.py", "why": "直接測"}]},
                                    "tool_response": "[NeedGoal] verify_scope 已收到"}, {})
    assert saved.get("verify_scope", {}).get("judge-1"), saved


# ─── need_goal 參數對拍 ──────────────────────────────────────────────────────

def test_need_goal_validates_verify_scope_shape():
    import wg_need_goal as ng
    assert ng.validate_input({"action": "verify_scope", "items": [{"target": "a.py", "why": "w"}]}) == []
    assert ng.validate_input({"action": "verify_scope", "items": []})
    assert ng.validate_input({"action": "verify_scope", "items": [{"target": "a.py"}]})
    assert ng.validate_input({"action": "verify_scope", "items": [{"target": "a.py", "why": "w"}],
                              "reviews": [{"leak": "L1", "verdict": "maybe"}]})
