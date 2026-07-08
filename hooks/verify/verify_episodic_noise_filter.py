"""verify_episodic_noise_filter.py — episodic 生成品質（B 組補充項）驗證。

1. sanitize_harness_noise：剔 harness 標籤（成對/未閉合）與 hook 注入殘渣行，
   保留使用者實際文字；fail-open
2. topic tracker：first_prompt_summary 記錄端即為乾淨文字；純 IDE 事件 prompt
   剔完為空 → 留給下一個真 prompt 補位
3. episodic atom：摘要不含 harness 標籤；知識段只含具體行動知識（LLM 萃取項 +
   覆轍信號），無「修改 N 個檔案」類流水帳；統計歸摘要工作範圍行

對應：wg_core.sanitize_harness_noise + wg_atoms._update_topic_tracker +
      wg_episodic._build_episodic_summary / _generate_episodic_atom。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_atoms as wa  # noqa: E402
import wg_episodic as we  # noqa: E402
from wg_core import sanitize_harness_noise  # noqa: E402

_IDE_TAG = (
    "<ide_opened_file>The user opened the file c:\\x\\IDENTITY.md in the IDE. "
    "This may or may not be related to the current task.</ide_opened_file>"
)


# ─── 1. sanitize_harness_noise ───────────────────────────────────────


def test_strips_paired_and_unclosed_tags():
    assert sanitize_harness_noise(f"{_IDE_TAG}接續 B 組批次") == "接續 B 組批次"
    # 未閉合（截斷）→ 吃到字串尾
    assert sanitize_harness_noise("修 bug<system-reminder>injected stuff") == "修 bug"
    assert sanitize_harness_noise(
        "<system-reminder>a</system-reminder>x<ide_selection>s</ide_selection>y"
    ) == "x y"


def test_strips_hook_residue_lines_keeps_user_text():
    text = "做 X 任務\n[Guardian:AIDocs] Relevant docs\n[Atom:workflow-rules]\n繼續 Y"
    assert sanitize_harness_noise(text) == "做 X 任務 繼續 Y"


def test_sanitize_fail_open():
    assert sanitize_harness_noise("") == ""
    assert sanitize_harness_noise("普通文字") == "普通文字"


# ─── 2. topic tracker 記錄端 ─────────────────────────────────────────


def test_tracker_first_prompt_recorded_clean():
    state = {}
    wa._update_topic_tracker(state, f"{_IDE_TAG}接續原子記憶批次", "build", [])
    assert state["topic_tracker"]["first_prompt_summary"] == "接續原子記憶批次"


def test_tracker_pure_noise_prompt_yields_to_next_real_prompt():
    state = {}
    wa._update_topic_tracker(state, _IDE_TAG, "general", [])
    assert state["topic_tracker"]["first_prompt_summary"] == ""
    wa._update_topic_tracker(state, "真正的第一個任務描述", "build", [])
    assert state["topic_tracker"]["first_prompt_summary"] == "真正的第一個任務描述"


# ─── 3. episodic atom 產出 ──────────────────────────────────────────


def _make_state():
    t0 = datetime.now() - timedelta(minutes=30)
    return {
        "session": {"cwd": "C:/proj", "started_at": t0.isoformat()},
        "ended_at": datetime.now().isoformat(),
        "modified_files": [
            {"path": "C:/proj/src/a.py", "tool": "Edit"},
            {"path": "C:/proj/src/b.py", "tool": "Edit"},
        ],
        "accessed_files": [{"path": "C:/proj/docs/readme.md"}],
        "knowledge_queue": [
            {"content": "API /v1/x 需帶 user 欄位而非 email", "classification": "[臨]"},
        ],
        "injected_atoms": ["decisions"],
        "vcs_queries": [{"command": "git log"}],
        "edit_counts": {"C:/proj/src/a.py": 3},
        "topic_tracker": {
            "intent_distribution": {"build": 3},
            "prompt_count": 3,
            "first_prompt_summary": f"{_IDE_TAG}修 API 欄位",  # 舊 state 殘留污染
        },
    }


def _generate(tmp_path, monkeypatch, state):
    monkeypatch.setattr(we, "_resolve_episodic_dir", lambda st: (tmp_path, "global"))
    monkeypatch.setattr(
        we, "write_raw",
        lambda p, content, **kw: Path(p).write_text(content, encoding="utf-8"),
    )
    name = we._generate_episodic_atom("noise-test", state, {"episodic": {}})
    assert name
    return (tmp_path / f"{name}.md").read_text(encoding="utf-8")


def test_episodic_summary_sanitized_and_knowledge_concrete(tmp_path, monkeypatch):
    content = _generate(tmp_path, monkeypatch, _make_state())
    # 摘要：舊 state 的 harness 標籤被防禦性剔除，使用者文字保留
    assert "<ide_opened_file>" not in content and "<system-reminder>" not in content
    assert "修 API 欄位" in content
    # 知識段：具體知識 + 覆轍信號保留；流水帳統計不再出現在知識段
    knowledge = content.split("## 知識", 1)[1].split("##", 1)[0]
    assert "API /v1/x" in knowledge
    assert "覆轍信號" in knowledge
    for banned in ("修改 2 個檔案", "閱讀 1 個檔案", "引用 atoms", "版控查詢", "閱讀區域"):
        assert banned not in knowledge
    # 統計歸摘要工作範圍行
    assert "- 工作範圍:" in content and "（修改 2 檔）" in content


def test_episodic_no_knowledge_placeholder(tmp_path, monkeypatch):
    state = _make_state()
    state["knowledge_queue"] = []
    state["edit_counts"] = {}
    content = _generate(tmp_path, monkeypatch, state)
    knowledge = content.split("## 知識", 1)[1].split("##", 1)[0]
    assert "無具體行動知識" in knowledge
