"""verify_opening_notice.py：開場的系統提示不寫成待辦口吻（規則 OPENING_NOTICE_NOT_TODO）。

做什麼：開場「[Harvest] N 張背景收割候選待審」那一行要寫清誰決定、要不要現在處理；使用者這回合要的是別的事時只轉述、不動手。
實例：提示寫「…值得留的用 atom_write 落卡，不要的刪掉」，使用者說「先告訴我、再等我說要做什麼」，AI 照提示刪了資料根的收割草稿
（004 現況2、重新判分 R2 各一次）。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_opening_notice.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("WG_CLAUDE_DIR", str(HOOKS_DIR.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent / "lib"))

from handlers import session_start as ss  # noqa: E402


def test_harvest_staged_line_says_who_decides_and_relay_only_when_user_wants_else():
    line = ss._harvest_staged_line(3)
    assert line.startswith("[Harvest] 3 張背景收割候選待審")
    assert "由使用者決定" in line and "只在回覆裡轉述這一行、不動這些檔" in line
    # 處置（落卡／刪掉）只在「使用者說要處理」之後才出現
    assert line.index("使用者說要處理") < line.index("不要的刪掉")


def test_session_start_emits_harvest_line_only_through_the_function():
    """開場只從 _harvest_staged_line 送這一行：原始碼裡不再有另一份直接寫成處置句的 [Harvest] 字串。"""
    src = (HOOKS_DIR / "handlers" / "session_start.py").read_text(encoding="utf-8")
    assert "lines.append(_harvest_staged_line(_staged))" in src
    assert not re.search(r"f\"\[Harvest\] \{_staged\}", src)
