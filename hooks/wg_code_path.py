"""wg_code_path：判斷一次寫入算不算改程式（寫碼類判準，各閘共用同一份）。

做什麼：is_code_path 看單一路徑（部位類別是 knowledge 的不算；其餘看寫碼查核閘那份副檔名清單，沒副檔名看 `#!`）；
  writes_code 再加上 cp／mv 的來源與新建腳本的內容。使用者：wg_core.coding_turn、收尾與提醒（stop、post_tool_batch）、
  動資料檔先問（wg_data_file）、順手看到最該修（wg_harvest）、OverviewHub（wg_overview）、tools/project-smells.py。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_code_path.py
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from wg_verify_ledger import is_code_file, reconcile_cfg

DIR_SCAN_CAP = 5000     # 搬移／複製的來源是目錄時最多看幾個檔；超過還沒看完就當成有程式檔


def _in_knowledge_part(path: str) -> bool:
    """部位類別是 knowledge（文件、記憶、信件匣）。真源是 overview_hub.path_kind；這支函式不在時當不是。"""
    try:
        from overview_hub import KIND_KNOWLEDGE, path_kind
    except ImportError:
        return False
    return path_kind(str(path)) == KIND_KNOWLEDGE


def is_code_path(path: str, config: Optional[Dict[str, Any]]) -> bool:
    """寫碼類判準：部位類別是 knowledge 的不算；其餘看寫碼查核閘那份副檔名清單（聯集合併，沒副檔名看 `#!`）。"""
    if not path or str(path).startswith("UNKNOWN:") or _in_knowledge_part(path):
        return False
    return is_code_file(str(path), reconcile_cfg(config or {})["code_exts"])


def _has_code(path: str, config: Optional[Dict[str, Any]]) -> bool:
    """搬移或複製的來源有沒有寫碼類檔：檔案照 is_code_path；目錄往下找（略過 .git），看超過 DIR_SCAN_CAP 個檔還沒找到
    也當有（判不了就擋）。"""
    if is_code_path(path, config):
        return True
    if not os.path.isdir(path) or _in_knowledge_part(path):
        return False
    seen = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            seen += 1
            if seen > DIR_SCAN_CAP or is_code_path(os.path.join(root, f), config):
                return True
    return False


def writes_code(path: str, config: Optional[Dict[str, Any]], sources: Any = (), content: Optional[str] = None) -> bool:
    """這次寫入算不算改程式：目標本身是程式檔；或 cp／mv 的來源含程式檔（目的地還不存在，光看路徑分不出來）；
    或要寫進沒副檔名檔案的內容以 `#!` 開頭（新建的腳本磁碟上還沒有，讀不到 shebang）。目標在知識類部位一律不算。"""
    if is_code_path(path, config):
        return True
    if not path or str(path).startswith("UNKNOWN:") or _in_knowledge_part(path):
        return False
    if any(_has_code(str(s), config) for s in sources or ()):
        return True
    return isinstance(content, str) and content.startswith("#!") and not Path(str(path)).suffix
