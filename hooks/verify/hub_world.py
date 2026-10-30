"""hub_world.py — OverviewHub／PreToolUse 案例共用的資料根隔離與部位世界（verify_gate_mode_pre、verify_locate_hint、
verify_pull_goal_locate、verify_read_fast_path 匯入；本檔不是案例檔，pytest 不收）。

env：資料根、state、守門紀錄、OverviewHub log 都在 tmp；pytest 暫存目錄不當成暫存檔（暫存檔判定換成 /eph/）。
hooked：在 env 之上攔 PreToolUse 的輸出，給一份 transcript。_mapped_world／_two_part_world：有部位表的假專案。
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
from handlers import _shared  # noqa: E402
from handlers import post_tool_use as pt  # noqa: E402
from handlers import pre_tool_use as ptu  # noqa: E402

SID = "sess-hub-0001"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """tmp 資料根：state、守門紀錄、OverviewHub log 都在 tmp；pytest 暫存目錄不當成暫存檔（測的就是正式檔的行為：
    暫存檔判定換成 /eph/，OverviewHub 的 TEMP_COPY_NOT_PROJECT 關掉）。"""
    monkeypatch.setenv("WG_TEMP_RULES", "off")
    wf = tmp_path / "wf"
    wf.mkdir()
    guard = []
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", wf)
    # 匯入時就存了一份資料夾的模組也導走（追蹤帳本、工具結果帳）：同一行程先載入模組再跑 pytest 時常數指到正式資料根
    import wg_harvest
    monkeypatch.setattr(wg_harvest, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(pt, "WORKFLOW_DIR", wf)
    monkeypatch.setattr(wg_core, "append_guard_log", lambda g, p: guard.append((g, p)))
    monkeypatch.setattr(wg_core, "_rebuild_min_atom_index", lambda cwd: {})
    monkeypatch.setattr(wg_core, "_find_active_sibling_state", lambda *a, **k: None)
    monkeypatch.setattr(wg_core, "_atom_debug_log", lambda *a, **k: None)
    monkeypatch.setattr(_shared, "_is_ephemeral_path", lambda p: "/eph/" in str(p).replace("\\", "/"))
    monkeypatch.setattr(pt, "_is_ephemeral_path", lambda p: "/eph/" in str(p).replace("\\", "/"))
    monkeypatch.setattr(wo, "LOG_PATH", tmp_path / "hub.log")
    monkeypatch.setattr(wo, "org_memory_root", lambda: None)
    monkeypatch.setattr(wo, "_ORG_ROOT_CACHE", [])
    monkeypatch.setattr(wo, "_WARNED", set())
    proj = tmp_path / "proj"
    proj.mkdir()
    return {"wf": wf, "guard": guard, "proj": proj, "tmp": tmp_path}


def _ptu_run(tool, tool_input, cwd, tp, outputs, sid=SID, config=None):
    with pytest.raises(SystemExit):
        ptu.handle_pre_tool_use({"tool_name": tool, "tool_input": tool_input, "session_id": sid, "cwd": str(cwd),
                                 "transcript_path": tp}, config or {})
    return outputs[-1]


def _deny_text(out):
    hs = (out or {}).get("hookSpecificOutput", {})
    return hs.get("permissionDecisionReason") if hs.get("permissionDecision") == "deny" else None


@pytest.fixture
def hooked(env, monkeypatch):
    outputs = []

    def _out(d):
        outputs.append(d)
        raise SystemExit(0)

    def _nothing():
        outputs.append(None)
        raise SystemExit(0)
    monkeypatch.setattr(ptu, "output_json", _out)
    monkeypatch.setattr(ptu, "output_nothing", _nothing)
    tp = env["tmp"] / "t.jsonl"
    tp.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "先看"}]}}) + "\n",
                  encoding="utf-8")
    env.update(outputs=outputs, tp=str(tp))
    return env


@pytest.fixture
def block_mode(monkeypatch):
    """送法固定成擋（gate_mode 全回 block）：這些案例測的是判定與擋訊息內容，不是送法；v6 開時改提醒的送法在 verify_gate_mode_pre.py。"""
    monkeypatch.setattr(ptu._rr, "gate_mode", lambda rule, v6: ptu._rr.BLOCK)


def _tool_call(tp, name, inp):
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}},
                           ensure_ascii=False) + "\n")


def _mapped_world(env):
    proj = env["proj"]
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 |\n|---|---|---|---|\n| `Game\\Battle\\` | 戰鬥 | `戰鬥導讀` | 有 |\n", encoding="utf-8")
    (proj / ".claude" / "memory" / "shared" / "戰鬥導讀.md").write_text(
        "# 戰鬥導讀\n\n## 知識\n\n- [臨] **已知病灶**：共用字典\n", encoding="utf-8")
    (proj / "Game" / "Battle").mkdir(parents=True)
    f1 = proj / "Game" / "Battle" / "A.cs"
    f1.write_text("x", encoding="utf-8")
    return str(f1)


def _say(tp, text):
    with open(tp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}},
                           ensure_ascii=False) + "\n")


def _read_part(f1, proj, tp):
    state = json.loads(wg_core.state_file_path(SID).read_text(encoding="utf-8"))
    wo.on_read(state, SID, "Read", {"file_path": f1}, str(proj), tp, {})
    wg_core.write_state(SID, state)


THREE = "定位｜部位：戰鬥：A.cs\n定位｜根因層：邏輯層\n定位｜前例：共用字典"
THREE2 = "定位｜部位：戰鬥：A.cs\n定位｜根因層：候選 A 邏輯層；候選 B 存檔時序；選 A 因為字典只在邏輯層被寫\n定位｜前例：共用字典"


def _two_part_world(env):
    """兩個寫碼部位（戰鬥、介面）＋一個知識類部位（文件，放 .py 也不算程式）。回 {子目錄: 檔路徑}。"""
    proj = env["proj"]
    (proj / ".claude" / "memory" / "shared").mkdir(parents=True)
    (proj / ".claude" / "overview-map.md").write_text(
        "| 路徑前綴 | 部位 | 導讀卡 | 狀態 | 類別 |\n|---|---|---|---|---|\n"
        "| `Game\\Battle\\` | 戰鬥 | `戰鬥導讀` | 有 | code |\n"
        "| `Game\\UI\\` | 介面 | `介面導讀` | 有 | code |\n"
        "| `Game\\Docs\\` | 文件 | 無 | 無 | knowledge |\n", encoding="utf-8")
    for name in ("戰鬥導讀", "介面導讀"):
        (proj / ".claude" / "memory" / "shared" / f"{name}.md").write_text(
            f"# {name}\n\n## 知識\n\n- [臨] **已知病灶**：x\n", encoding="utf-8")
    files = {}
    for sub, fn in (("Battle", "A.cs"), ("UI", "B.cs"), ("Docs", "gen.py")):
        (proj / "Game" / sub).mkdir(parents=True, exist_ok=True)
        files[sub] = str(proj / "Game" / sub / fn)
        Path(files[sub]).write_text("x", encoding="utf-8")
    return files
