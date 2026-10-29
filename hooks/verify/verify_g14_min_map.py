"""verify_g14_min_map.py — G14 最小地圖：沒有部位表的專案第一次改程式檔前擋一次，要 AI 先寫三行最小地圖（讀了／上游／下游）。

規則 UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP（hooks/wg_release_rules.py 檔尾 G14 段）；閘在 hooks/wg_overview._unmapped_edit；
擋訊息附 lib/overview_scaffold.preview_lines 的掃表預覽（子程序、每根一次、快取在 state["min_map"]）；開關 lib/hub_config min_map。
用 tmp_path 造無表假專案與假 transcript，直接呼叫 wg_overview.on_read／on_edit。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_g14_min_map.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))   # worktree 內跑：wg_core 的 lib／workflow 指本樹
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

import hub_config as hc  # noqa: E402
import overview_scaffold as sc  # noqa: E402
import wg_overview as wo  # noqa: E402
import wg_release_rules as rr  # noqa: E402

RULE = "UNMAPPED_FIRST_EDIT_NEEDS_MIN_MAP"
FAST = {"overview_hub": {"min_map": {"enabled": True, "preview_timeout_s": 5}}}   # 成功預覽的案給足時間（冷啟動 pyc 編譯）


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    """假專案建在 pytest tmp 下：關掉暫存規則；不接公司層；hub log 寫進 tmp。"""
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")


def _bare(tmp_path):
    """無表專案：有 .git 標記、沒有 .claude/overview-map.md；src、lib 各有既有程式檔。"""
    root = tmp_path / "bare"
    (root / ".git").mkdir(parents=True)
    for rel in ("src/a.py", "src/b.py", "lib/c.py", "lib/d.py", "README.md"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x\n", encoding="utf-8")
    return root


def _say(tp, text, block="text"):
    content = {"type": "thinking", "thinking": text} if block == "thinking" else (
        {"type": "tool_use", "name": "Bash", "input": {"command": text}} if block == "tool_input" else {"type": "text", "text": text})
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [content]}}, ensure_ascii=False) + "\n")


def _transcript(tmp_path):
    tp = tmp_path / "t.jsonl"
    _say(tp, "先看看。")
    return str(tp)


def _read(state, root, rel):
    wo.on_read(state, "s", "Read", {"file_path": str(root / rel)}, str(root), "", {})


MAP = "地圖｜讀了：src/b.py（入口）\n地圖｜上游：無，因為是入口腳本\n地圖｜下游：lib/c.py"


# ─── 紅案例（改前紅、改後綠） ──────────────────────────────────────────

def test_first_code_edit_blocks_with_rule_entry_and_preview(tmp_path):
    """無表專案、只讀過 1 個檔、Edit 程式檔 → 擋；訊息含規則名、三行入口、放哪裡那句、掃表預覽（含落表格式）。"""
    root, tp, state = _bare(tmp_path), _transcript(tmp_path), {}
    _read(state, root, "src/b.py")
    warn, deny, changed = wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, FAST)
    assert deny and RULE in deny and changed is True
    for s in ("地圖｜讀了：", "地圖｜上游：", "地圖｜下游：", "同一則回覆裡先發一條不寫檔的 Bash／PowerShell 指令", "照常用 Edit／Write",
              "掃表預覽（", "`src/` 檔 2", "`lib/` 檔 2", "路徑前綴用反引號包", "病灶清單欄填病灶文件路徑"):
        assert s in deny, s
    assert deny.rstrip().splitlines()[-1].startswith("同一則回覆裡先發")              # 入口在訊息末尾；只教 # 註解一條路
    assert "  # 地圖｜讀了：" in deny and "  git diff --stat" in deny and "早一則" not in deny   # 範例能照抄成一條不寫檔指令
    assert "下一個 Bash 開頭" not in deny            # 規則 DECL_HINT_KEEPS_EDIT_TOOLS：不把 AI 引去用 Bash 寫檔
    slot = state["min_map"][wo._root_key(root)]
    assert slot["preview_ok"] is True and "掃表預覽（" in slot["preview"]
    log = [json.loads(l) for l in (tmp_path / "hub.log").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["deny_reason"] == "min_map" and log[-1]["rule"] == RULE and log[-1]["preview_ran"] is True


def test_map_with_read_files_passes_and_same_key_not_blocked_again(tmp_path):
    """交了三行、讀了列的檔本 session 都讀過 → 放行；state 記 min_map_done；同鍵第二次 Edit 不再查（transcript 給空也放）。
    上游寫「無，因為是入口腳本」→ 算交。"""
    root, tp, state = _bare(tmp_path), _transcript(tmp_path), {}
    _read(state, root, "src/b.py")
    _say(tp, MAP)
    assert wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, FAST) == (None, None, True)
    rec = state["overview_hub"][wo._unmapped_key(root, str(root / "src" / "a.py"))]
    assert rec["min_map_done"] is True and rec["min_map_via"] == "text"
    assert "preview" not in state["min_map"][wo._root_key(root)]                    # 沒擋就不跑預覽
    assert wo.on_edit(state, "s", str(root / "src" / "a.py"), "", FAST) == (None, None, True)


def _reply(tp, mid, text="…"):
    """AI 的一則回覆 mid 整則落進 transcript：之後的呼叫屬下一則（批次鍵＝這則的 message.id）。"""
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"id": mid, "content": [{"type": "text", "text": text}]}},
                           ensure_ascii=False) + "\n")


def test_parallel_unmapped_edits_in_one_reply_count_once(tmp_path):
    """規則 DENY_CAP_PER_REPLY（最小地圖）：同一則回覆平行送出 3 個改同一頂層目錄程式檔的 Edit、都沒交地圖三行 → 3 個都擋
    （擋次照則數；舊碼照每個呼叫算，第 3 個記 edit_unmapped_capped、沒交地圖就放行）；下一則交了三行 → 放行。"""
    root, tp, state = _bare(tmp_path), _transcript(tmp_path), {"turn_seq": 3}
    _read(state, root, "src/b.py")
    _reply(tp, "m1")
    outs = [wo.on_edit(state, "s", str(root / "src" / name), tp, FAST, tool_use_id=f"tu_{i}")
            for i, name in enumerate(("a.py", "b.py", "a.py"))]
    assert [bool(deny) for _, deny, _ in outs] == [True] * 3, outs
    assert "edit_unmapped_capped" not in (tmp_path / "hub.log").read_text(encoding="utf-8")
    _reply(tp, "m2")
    _reply(tp, "m3", MAP)
    assert wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, FAST, tool_use_id="tu_4") == (None, None, True)


def test_listed_file_not_read_is_named(tmp_path):
    """三行列了 src/x.py 但本 session 沒讀過 → 擋並點名那個檔。"""
    root, tp, state = _bare(tmp_path), _transcript(tmp_path), {}
    _read(state, root, "src/b.py")
    _say(tp, "地圖｜讀了：src/b.py、src/x.py\n地圖｜上游：main.py\n地圖｜下游：無，因為是葉節點")
    _, deny, _ = wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, FAST)
    assert deny and RULE in deny and "src/x.py 本 session 沒讀過" in deny and "src/b.py 本 session" not in deny


@pytest.mark.parametrize("up, owed", [("", True), ("無", True), ("<誰餵這一塊（檔或模組）／無，因為…>", True),
                                      ("無，因為是入口腳本", False), ("無鎖佇列 queue.py", False)])
def test_upstream_empty_or_bare_none_blocks(tmp_path, up, owed):
    """上游寫空字串、光禿的「無」、照抄範例佔位 → 擋；「無，因為…」或寫了名字（含以「無」開頭的名字）→ 放行。"""
    root, tp, state = _bare(tmp_path), _transcript(tmp_path), {}
    _read(state, root, "src/b.py")
    _say(tp, f"地圖｜讀了：src/b.py\n地圖｜上游：{up}\n地圖｜下游：lib/c.py")
    warn, deny, _ = wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, FAST)
    assert bool(deny) is owed
    if owed:
        assert "地圖｜上游" in deny


def test_exempt_targets_keep_existing_behaviour(tmp_path):
    """gitignored、執行期資料、快取目錄、非程式檔 → 本規則不查（既有判式不變）。"""
    root = tmp_path / "g"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "b.py").write_text("x\n", encoding="utf-8")
    tp, state = _transcript(tmp_path), {}
    assert wo.on_edit(state, "s", str(root / "build" / "gen.py"), tp, FAST) == (None, None, False)     # gitignored
    assert wo.on_edit(state, "s", str(root / "workflow" / "state-1.json"), tp, FAST) == (None, None, False)
    assert wo.on_edit(state, "s", str(root / "src" / "__pycache__" / "a.pyc"), tp, FAST) == (None, None, False)
    _read(state, root, "src/b.py")
    assert wo.on_edit(state, "s", str(root / "src" / "notes.md"), tp, FAST) == (None, None, True)      # 非程式檔
    assert "min_map" not in state


def test_mapped_project_never_triggers(tmp_path):
    """有部位表：表上列到的檔走原本的導讀卡／定位三行；表上沒列的檔只照 UNMAPPED_EDIT_NEEDS_READABLE_FILES，不要地圖。"""
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n| `src/` | 源碼 | 無 | 無 |\n", encoding="utf-8")
    for rel in ("src/a.py", "other/y.py"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x\n", encoding="utf-8")
    tp, state = _transcript(tmp_path), {}
    _, deny, _ = wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, FAST)
    assert deny and "導讀卡" in deny and RULE not in deny
    _, deny, _ = wo.on_edit(state, "s", str(root / "other" / "x.py"), tp, FAST)       # 前提：表外檔真的走 _unmapped_edit
    assert deny and "UNMAPPED_EDIT_NEEDS_READABLE_FILES" in deny and RULE not in deny
    _read(state, root, "other/y.py")
    assert wo.on_edit(state, "s", str(root / "other" / "x.py"), tp, FAST) == (None, None, True)
    assert "min_map" not in state


def test_preview_timeout_blocks_and_is_cached(tmp_path, monkeypatch):
    """掃表預覽子程序逾時 → 照擋、訊息含「掃表預覽失敗：逾時」；同根第二次擋不再跑（用快取），state 有紀錄。"""
    root, tp, state = _bare(tmp_path), _transcript(tmp_path), {}
    cfg = {"overview_hub": {"min_map": {"enabled": True, "preview_timeout_s": 0.001}}}
    _read(state, root, "src/b.py")
    _, deny, changed = wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, cfg)
    assert deny and RULE in deny and "掃表預覽失敗：逾時" in deny and changed is True
    slot = state["min_map"][wo._root_key(root)]
    assert slot["preview_ok"] is False and slot["preview"].startswith("掃表預覽失敗：逾時")

    real_run = subprocess.run

    def _no_preview(args, *a, **k):
        assert wo._PREVIEW_CODE not in args, "同根第二次擋不該再跑預覽"
        return real_run(args, *a, **k)
    monkeypatch.setattr(wo.subprocess, "run", _no_preview)
    _read(state, root, "lib/d.py")
    _, deny2, changed2 = wo.on_edit(state, "s", str(root / "lib" / "c.py"), tp, cfg)
    assert deny2 and "掃表預覽失敗：逾時" in deny2 and changed2 is True             # 預覽沒重跑；state 變的是擋次（GATE_DENY_CAP）


def test_disabled_switch_skips_rule_and_keeps_readable_files_gate(tmp_path):
    """min_map.enabled=false → 整條不觸發；UNMAPPED_EDIT_NEEDS_READABLE_FILES 照舊（沒讀照擋、讀了放行）。"""
    root, tp, state = _bare(tmp_path), _transcript(tmp_path), {}
    off = {"overview_hub": {"min_map": {"enabled": False, "preview_timeout_s": 2}}}
    _, deny, _ = wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, off)
    assert deny and "UNMAPPED_EDIT_NEEDS_READABLE_FILES" in deny and RULE not in deny
    _read(state, root, "src/b.py")
    assert wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, off) == (None, None, True)
    assert "min_map" not in state


# ─── 細節：兩條都欠、管道、同根換頂層目錄、設定驗證、純函式 ───────────────

def test_both_owed_listed_in_one_message(tmp_path):
    """一個檔都沒讀：讀檔數與最小地圖兩條同一則訊息列，入口仍在末尾。"""
    root, tp = _bare(tmp_path), _transcript(tmp_path)
    _, deny, _ = wo.on_edit({}, "s", str(root / "src" / "a.py"), tp, FAST)
    assert "UNMAPPED_EDIT_NEEDS_READABLE_FILES" in deny and RULE in deny
    assert deny.rstrip().splitlines()[-1].startswith("同一則回覆裡先發")


def test_bash_comment_channel_and_thinking_warns(tmp_path):
    """三行放在 Bash 開頭 # 註解（工具參數管道）→ 放行；只在 thinking → 放行附提醒。"""
    root, tp, state = _bare(tmp_path), _transcript(tmp_path), {}
    _read(state, root, "src/b.py")
    _say(tp, "# " + MAP.replace("\n", "\n# ") + "\nls src", block="tool_input")
    assert wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, FAST) == (None, None, True)
    assert state["overview_hub"][wo._unmapped_key(root, str(root / "src" / "a.py"))]["min_map_via"] == "tool_input"
    root2 = tmp_path / "two"
    (root2 / ".git").mkdir(parents=True)
    (root2 / "src").mkdir()
    (root2 / "src" / "b.py").write_text("x\n", encoding="utf-8")
    tp2, state2 = str(tmp_path / "t2.jsonl"), {}
    _say(tp2, MAP, block="thinking")
    _read(state2, root2, "src/b.py")
    warn, deny, _ = wo.on_edit(state2, "s", str(root2 / "src" / "a.py"), tp2, FAST)
    assert deny is None and warn and "thinking" in warn


def test_next_top_dir_needs_map_after_last_pass(tmp_path):
    """同根換頂層目錄＝新鍵：上次放行之前交的地圖不算，要再交一份（取放行時的 transcript 位置之後）。"""
    root, tp, state = _bare(tmp_path), _transcript(tmp_path), {}
    _read(state, root, "src/b.py")
    _say(tp, MAP)
    assert wo.on_edit(state, "s", str(root / "src" / "a.py"), tp, FAST) == (None, None, True)
    _read(state, root, "lib/d.py")
    _, deny, _ = wo.on_edit(state, "s", str(root / "lib" / "c.py"), tp, FAST)
    assert deny and RULE in deny
    _say(tp, "地圖｜讀了：lib/d.py\n地圖｜上游：src/a.py\n地圖｜下游：無，因為還沒有呼叫端")
    assert wo.on_edit(state, "s", str(root / "lib" / "c.py"), tp, FAST) == (None, None, True)


def test_hub_config_defaults_and_validation():
    assert hc.HUB_DEFAULTS["min_map"] == {"enabled": True, "preview_timeout_s": 2}
    assert hc.validate_min_map({"enabled": True, "preview_timeout_s": 2}) == []
    errs = hc.validate_min_map({"enabled": "yes", "preview_timeout_s": 0, "x": 1})
    assert len(errs) == 3 and any("未知鍵「x」" in e for e in errs)
    assert hc.validate_min_map({"enabled": True, "preview_timeout_s": 6})            # 超過 hook 整體預算
    bad = {"overview_hub": {"min_map": {"enabled": 1, "preview_timeout_s": 2}}}
    _, deny, _ = wo.on_edit({}, "s", str(Path(__file__)), "", bad)
    assert deny and "min_map.enabled" in deny                                       # 設定壞了一律擋


def test_pure_group_files_and_verdict():
    text = ("地圖｜讀了：a.py\n地圖｜上游：x\n"                                          # 不齊的一組
            "# 地圖｜讀了：`src/b.py`、lib/c.py（主程式）, README.md\n# 地圖｜上游：無，因為入口\n# 地圖｜下游：tests/t.py\n"
            "地圖｜讀了：z.py")                                                         # 最後一組不齊 → 取最後一組齊的
    g = rr.min_map_group(text)
    assert g == {"讀了": "`src/b.py`、lib/c.py（主程式）, README.md", "上游": "無，因為入口", "下游": "tests/t.py"}
    assert rr.min_map_files(g["讀了"]) == ["src/b.py", "lib/c.py", "README.md"]
    read = [os.path.join("C:/p", f) for f in ("src/b.py", "LIB/C.PY", "README.md")]
    assert rr.min_map_verdict(g, "C:/p", read).owed is False                         # 大小寫、斜線同一檔
    bare = {"讀了": "src/b.py c.py README.md", "上游": "x", "下游": "y"}             # 同目錄的檔只列檔名（011 實跑 AI 的寫法）
    assert rr.min_map_verdict(bare, "C:/p", read).owed is False
    v = rr.min_map_verdict({**bare, "讀了": "src/b.py nothere.py"}, "C:/p", read)
    assert v.owed and "nothere.py" in "；".join(v.evidence)                          # 沒讀過的檔名照樣點名
    v = rr.min_map_verdict(None, "C:/p", [], "transcript 讀不到（missing）")
    assert v.owed and v.rule == RULE and "transcript 讀不到" in v.evidence[0]
    v = rr.min_map_verdict({"讀了": "（只有附註）", "上游": "a", "下游": "b"}, "C:/p", [])
    assert v.owed and "沒列任何檔" in "；".join(v.evidence)
    assert RULE in rr.RULES


def test_preview_lines_shape(tmp_path):
    """預覽摘要：≤ 15 行、前綴反引號包、熱點前 N、附落表格式與指令；不落檔。"""
    root = _bare(tmp_path)
    for i in range(10):
        (root / f"d{i}").mkdir()
    lines = sc.preview_lines(root, {}, {}, top_n=8)
    assert len(lines) <= 15 and lines[0].startswith("掃表預覽（") and "頂層目錄 12 個" in lines[0]
    assert sum(1 for l in lines if l.startswith("  `")) == 8 and any("`src/` 檔 2" in l for l in lines)
    assert sc.PREVIEW_FORMAT_LINE in lines and "overview-map-scaffold.py --cwd" in lines[-1]
    assert not (root / ".claude").exists()
