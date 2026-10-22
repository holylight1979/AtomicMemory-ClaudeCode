"""config_local.py — 把 workflow/config.local.json（這台機器專屬、不進版控）蓋到共用設定 workflow/config.json 上。

規則和 hooks/wg_core.load_config 同一套：頂層同名鍵兩邊都是物件就淺合併（本機的鍵蓋過共用的），否則本機的值整個取代；
檔案不存在＝沒有本機覆寫；讀壞了 stderr 一行、照共用設定跑。
呼叫端傳 config.json 旁邊的 config.local.json（測試把 config.json 換到暫存目錄時，本機覆寫也跟著換掉）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


def merge_local(config: Dict[str, Any], local_path: Path, tag: str = "config") -> Dict[str, Any]:
    """local_path 的內容蓋到 config（原地改並回傳）。"""
    try:
        local = json.loads(local_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return config
    except (OSError, ValueError) as e:   # ValueError 含 JSON 壞與 UTF-8 解不開
        print(f"[{tag}] {local_path} 讀取失敗，略過本機覆寫：{e}", file=sys.stderr)
        return config
    for key, value in (local if isinstance(local, dict) else {}).items():
        base = config.get(key)
        config[key] = {**base, **value} if isinstance(base, dict) and isinstance(value, dict) else value
    return config
