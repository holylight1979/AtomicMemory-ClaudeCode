"""wg_code_path：判斷一個檔算不算程式檔（寫碼類判準，各閘共用同一份）。

做什麼：is_code_path 看單一路徑（部位類別是 knowledge 的不算；其餘看寫碼查核閘那份副檔名清單，沒副檔名看 `#!`）。
  使用者：wg_core.coding_turn、收尾與提醒（stop、post_tool_batch）、動資料檔先問（wg_data_file）、
  順手看到最該修（wg_harvest）、tools/project-smells.py。
怎麼驗：python -X utf8 -m pytest -q hooks/verify/verify_code_path.py
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from wg_verify_ledger import is_code_file, reconcile_cfg


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
