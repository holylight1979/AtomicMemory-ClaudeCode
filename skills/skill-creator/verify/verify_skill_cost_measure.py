"""verify_skill_cost_measure.py — skill-cost-measure.py 的計數契約。

守住規則：
- 同一則回覆拆成多行（同 message.id）usage 只算一次；assistant_turns＝不重複回覆數。
- tool_uses 逐行數（每行是不同的內容區塊）。
- --skill 的 before／after 兩桶加起來等於 total。
怎麼跑：python -X utf8 -m pytest -q skills/skill-creator/verify/verify_skill_cost_measure.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "skill-cost-measure.py"
U1 = {"input_tokens": 10, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 50, "output_tokens": 5}
U2 = {"input_tokens": 1, "cache_read_input_tokens": 200, "cache_creation_input_tokens": 0, "output_tokens": 7}


def _row(msg_id: str, usage: dict, block: dict) -> dict:
    return {"type": "assistant", "message": {"id": msg_id, "content": [block], "usage": usage}}


def test_split_reply_counted_once_and_buckets_add_up(tmp_path):
    tx = tmp_path / "s.jsonl"
    rows = [
        _row("m1", U1, {"type": "text", "text": "a"}),
        _row("m1", U1, {"type": "tool_use", "name": "Skill", "input": {"skill": "demo"}}),
        _row("m1", U1, {"type": "tool_use", "name": "Read", "input": {}}),
        _row("m2", U2, {"type": "tool_use", "name": "Read", "input": {}}),
    ]
    tx.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(SCRIPT), "--session", str(tx), "--skill", "demo"], env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["total"] == {"input_tokens": 11, "output_tokens": 12, "cache_creation": 50, "cache_read": 300,
                            "assistant_turns": 2, "tool_uses": 3}
    assert out["skill_triggered"] is True
    for k in out["total"]:
        assert out["before_trigger"][k] + out["after_trigger"][k] == out["total"][k], k
